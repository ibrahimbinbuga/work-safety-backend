import { useState, useRef, useEffect } from 'react';
import { AlertTriangle, HardHat, Shirt, Camera, Calendar, Filter, Eye, ChevronDown, Clock } from 'lucide-react';
import { apiClient, addCompanyCodeToUrl } from '../utils/api';
import { useAuth } from '../context/AuthContext';

const formatTurkishDate = (raw) => {
  if (!raw) return '-';
  try {
    const d = new Date(raw);
    if (isNaN(d)) return raw;
    return d.toLocaleString('tr-TR', {
      timeZone: 'Europe/Istanbul',
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return raw;
  }
};

const getTimestampMs = (raw) => {
  if (!raw) return 0;
  const parsed = new Date(raw).getTime();
  return Number.isNaN(parsed) ? 0 : parsed;
};

// İhlal tipi görsel tanımları
const VIOLATION_TYPE_CONFIG = {
  head: {
    label: 'No Helmet',
    badge: 'bg-red-50 text-red-700 border-red-100',
    icon: HardHat,
    category: 'ppe',
  },
  vest: {
    label: 'No Vest',
    badge: 'bg-orange-50 text-orange-700 border-orange-100',
    icon: Shirt,
    category: 'ppe',
  },
  fallen: {
    label: 'Fall Detected',
    badge: 'bg-purple-50 text-purple-700 border-purple-100',
    icon: AlertTriangle,
    category: 'fall',
  },
};

function ViolationTypeBadge({ type }) {
  const config = VIOLATION_TYPE_CONFIG[type];
  if (!config) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-50 text-gray-600 border border-gray-200 capitalize">
        <AlertTriangle className="w-3 h-3" />
        {type}
      </span>
    );
  }
  const Icon = config.icon;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${config.badge}`}>
      <Icon className="w-3 h-3" />
      {config.label}
    </span>
  );
}

const statusOptions = [
  { value: 'pending',  label: 'Pending',  classes: 'bg-blue-50 text-blue-700 border-blue-100' },
  { value: 'reviewed', label: 'Reviewed', classes: 'bg-yellow-50 text-yellow-700 border-yellow-100' },
  { value: 'resolved', label: 'Resolved', classes: 'bg-green-50 text-green-700 border-green-100' },
];

function StatusDropdown({ violationId, currentStatus, onUpdate }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const current = statusOptions.find(o => o.value === currentStatus) || statusOptions[0];

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div className="relative inline-block" ref={ref}>
      <button
        onClick={() => setOpen(o => !o)}
        className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium capitalize border cursor-pointer hover:opacity-80 transition-opacity ${current.classes}`}
      >
        {current.label}
        <ChevronDown className="w-3 h-3" />
      </button>
      {open && (
        <div className="absolute z-50 mt-1 w-32 bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden">
          {statusOptions.map(opt => (
            <button
              key={opt.value}
              onClick={() => { onUpdate(violationId, opt.value); setOpen(false); }}
              className={`w-full text-left px-3 py-2 text-xs font-medium hover:bg-gray-50 transition-colors ${
                opt.value === currentStatus ? 'font-semibold bg-gray-50' : ''
              }`}
            >
              <span className={`inline-block px-2 py-0.5 rounded-full border ${opt.classes}`}>{opt.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function Violations() {
  const { isAdmin, activeCompanyCode } = useAuth();
  const [filterType, setFilterType] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  const [filterDateFrom, setFilterDateFrom] = useState('');
  const [filterDateTo, setFilterDateTo] = useState('');
  const [sortByDate, setSortByDate] = useState('newest');
  const [violations, setViolations] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchViolations();
  }, [activeCompanyCode]);

  const fetchViolations = async () => {
    setIsLoading(true);
    try {
      const url = addCompanyCodeToUrl('/api/violations', activeCompanyCode);
      const response = await apiClient.get(url);

      const processed = response.data.map(v => ({
        id: v.id,
        workerId: v.violation_id,
        camera: v.ihlal_yapilan_bolge,
        type: v.ihlal_cesidi,
        timestamp: v.tarih_saat,
        status: v.review_status || 'pending',
      }));

      setViolations(processed);
    } catch (error) {
      console.error('Violations fetch error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const updateStatus = async (violationId, newStatus) => {
    const previous = [...violations];
    setViolations(prev => prev.map(v => v.id === violationId ? { ...v, status: newStatus } : v));
    try {
      await apiClient.patch(`/api/violations/${violationId}/status`, { review_status: newStatus });
    } catch (error) {
      console.error('Status update error:', error);
      setViolations(previous);
    }
  };

  const filteredViolations = violations.filter(v => {
    const typeMatch = filterType === 'all' || v.type === filterType;
    const statusMatch = filterStatus === 'all' || v.status === filterStatus;
    const tsMs = getTimestampMs(v.timestamp);
    const fromMs = filterDateFrom ? new Date(`${filterDateFrom}T00:00:00`).getTime() : null;
    const toMs = filterDateTo ? new Date(`${filterDateTo}T23:59:59.999`).getTime() : null;
    return typeMatch && statusMatch && (fromMs === null || tsMs >= fromMs) && (toMs === null || tsMs <= toMs);
  });

  const filteredAndSorted = [...filteredViolations].sort((a, b) => {
    const diff = getTimestampMs(a.timestamp) - getTimestampMs(b.timestamp);
    return sortByDate === 'oldest' ? diff : -diff;
  });

  const stats = {
    total: violations.length,
    ppe: violations.filter(v => v.type === 'head' || v.type === 'vest').length,
    fall: violations.filter(v => v.type === 'fallen').length,
    pending: violations.filter(v => v.status === 'pending').length,
  };

  if (isAdmin && !activeCompanyCode) {
    return (
      <div className="space-y-6 p-6">
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-8 text-center">
          <p className="text-amber-900 text-lg font-semibold">Please select a company from the sidebar.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Safety Violations</h2>
        <p className="text-gray-500 text-sm mt-1">Monitor and manage detected safety violations</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex justify-between items-start">
          <div>
            <p className="text-gray-500 text-sm font-medium">Total Violations</p>
            <h3 className="text-3xl font-bold text-gray-900 mt-2">{stats.total}</h3>
          </div>
          <div className="w-12 h-12 bg-orange-100 rounded-lg flex items-center justify-center text-orange-600">
            <AlertTriangle className="w-6 h-6" />
          </div>
        </div>

        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex justify-between items-start">
          <div>
            <p className="text-gray-500 text-sm font-medium">PPE Violations</p>
            <p className="text-xs text-gray-400 mt-0.5">No Helmet / No Vest</p>
            <h3 className="text-3xl font-bold text-gray-900 mt-1">{stats.ppe}</h3>
          </div>
          <div className="w-12 h-12 bg-red-100 rounded-lg flex items-center justify-center text-red-600">
            <HardHat className="w-6 h-6" />
          </div>
        </div>

        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex justify-between items-start">
          <div>
            <p className="text-gray-500 text-sm font-medium">Fall Detections</p>
            <p className="text-xs text-gray-400 mt-0.5">Fallen workers</p>
            <h3 className="text-3xl font-bold text-gray-900 mt-1">{stats.fall}</h3>
          </div>
          <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center text-purple-600">
            <AlertTriangle className="w-6 h-6" />
          </div>
        </div>

        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex justify-between items-start">
          <div>
            <p className="text-gray-500 text-sm font-medium">Pending Review</p>
            <h3 className="text-3xl font-bold text-gray-900 mt-2">{stats.pending}</h3>
          </div>
          <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center text-blue-600">
            <Clock className="w-6 h-6" />
          </div>
        </div>
      </div>

      {/* Filters and Table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="p-6 border-b border-gray-100 space-y-4">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-lg font-bold text-gray-900">Violation Records</h3>
            <button
              onClick={() => {
                setFilterType('all');
                setFilterStatus('all');
                setFilterDateFrom('');
                setFilterDateTo('');
                setSortByDate('newest');
              }}
              className="flex items-center gap-2 border border-gray-300 px-3 py-2 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
            >
              <Filter className="w-4 h-4" />
              Reset
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-3">
            {/* Type filter */}
            <div className="space-y-1">
              <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Type</label>
              <div className="relative">
                <select
                  value={filterType}
                  onChange={(e) => setFilterType(e.target.value)}
                  className="w-full appearance-none bg-white border border-gray-300 text-gray-700 py-2 pl-3 pr-8 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="all">All Types</option>
                  <optgroup label="PPE Model">
                    <option value="head">No Helmet</option>
                    <option value="vest">No Vest</option>
                  </optgroup>
                  <optgroup label="Fall Detection Model">
                    <option value="fallen">Fall Detected</option>
                  </optgroup>
                </select>
                <ChevronDown className="w-4 h-4 text-gray-500 absolute right-2.5 top-3 pointer-events-none" />
              </div>
            </div>

            {/* Status filter */}
            <div className="space-y-1">
              <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Status</label>
              <div className="relative">
                <select
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                  className="w-full appearance-none bg-white border border-gray-300 text-gray-700 py-2 pl-3 pr-8 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="all">All Status</option>
                  <option value="pending">Pending</option>
                  <option value="reviewed">Reviewed</option>
                  <option value="resolved">Resolved</option>
                </select>
                <ChevronDown className="w-4 h-4 text-gray-500 absolute right-2.5 top-3 pointer-events-none" />
              </div>
            </div>

            {/* From date */}
            <div className="space-y-1">
              <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">From Date</label>
              <input
                type="date"
                value={filterDateFrom}
                onChange={(e) => setFilterDateFrom(e.target.value)}
                className="w-full bg-white border border-gray-300 text-gray-700 py-2 px-3 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            {/* To date */}
            <div className="space-y-1">
              <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">To Date</label>
              <input
                type="date"
                value={filterDateTo}
                onChange={(e) => setFilterDateTo(e.target.value)}
                className="w-full bg-white border border-gray-300 text-gray-700 py-2 px-3 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            {/* Sort */}
            <div className="space-y-1">
              <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Sort By Date</label>
              <div className="relative">
                <select
                  value={sortByDate}
                  onChange={(e) => setSortByDate(e.target.value)}
                  className="w-full appearance-none bg-white border border-gray-300 text-gray-700 py-2 pl-3 pr-8 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="newest">Newest First</option>
                  <option value="oldest">Oldest First</option>
                </select>
                <ChevronDown className="w-4 h-4 text-gray-500 absolute right-2.5 top-3 pointer-events-none" />
              </div>
            </div>
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead className="bg-gray-50/50">
              <tr>
                <th className="p-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">ID</th>
                <th className="p-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Worker</th>
                <th className="p-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Camera / Zone</th>
                <th className="p-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Violation Type</th>
                <th className="p-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Timestamp</th>
                <th className="p-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                <th className="p-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filteredAndSorted.map((violation) => (
                <tr key={violation.id} className="hover:bg-gray-50/50 transition-colors">
                  <td className="p-4 text-sm font-medium text-blue-600">#{violation.id}</td>
                  <td className="p-4">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 bg-gray-100 rounded-full flex items-center justify-center text-xs font-bold text-gray-600">
                        {violation.workerId ?? '?'}
                      </div>
                      <span className="text-sm text-gray-700">Worker #{violation.workerId ?? '-'}</span>
                    </div>
                  </td>
                  <td className="p-4">
                    <div className="flex items-center gap-2 text-gray-600">
                      <Camera className="w-4 h-4 text-gray-400 flex-shrink-0" />
                      <span className="text-sm">{violation.camera || '-'}</span>
                    </div>
                  </td>
                  <td className="p-4">
                    <ViolationTypeBadge type={violation.type} />
                  </td>
                  <td className="p-4">
                    <div className="flex items-center gap-2 text-gray-500">
                      <Calendar className="w-4 h-4 flex-shrink-0" />
                      <span className="text-sm">{formatTurkishDate(violation.timestamp)}</span>
                    </div>
                  </td>
                  <td className="p-4">
                    <StatusDropdown
                      violationId={violation.id}
                      currentStatus={violation.status}
                      onUpdate={updateStatus}
                    />
                  </td>
                  <td className="p-4">
                    <button className="flex items-center gap-1 text-gray-500 hover:text-blue-600 transition-colors border border-gray-200 px-2 py-1 rounded-md text-xs font-medium hover:border-blue-200 hover:bg-blue-50">
                      <Eye className="w-3 h-3" />
                      View
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {isLoading && (
            <div className="text-center py-10 text-gray-500">
              <p>Loading violations...</p>
            </div>
          )}

          {!isLoading && filteredAndSorted.length === 0 && (
            <div className="text-center py-10 text-gray-500">
              <p>No violations found matching the filters.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

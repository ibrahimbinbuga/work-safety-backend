import { useState } from 'react';
import { AlertTriangle, HardHat, Shirt, Camera, Calendar, Filter, Eye, ChevronDown, CheckCircle, Clock } from 'lucide-react';
import axios from "axios";
import { useEffect } from "react";

// Şimdilik statik veri (İleride Backend'den çekilecek)
/*const initialViolations = [
  {
    id: 'V-2025-1247',
    workerName: 'Worker #A342',
    camera: 'Warehouse A - Entry',
    type: 'helmet',
    timestamp: '2025-11-18 14:23:45',
    severity: 'high',
    status: 'pending',
  },
  {
    id: 'V-2025-1246',
    workerName: 'Worker #B128',
    camera: 'Construction Zone 3',
    type: 'vest',
    timestamp: '2025-11-18 14:15:22',
    severity: 'medium',
    status: 'reviewed',
  },
  {
    id: 'V-2025-1245',
    workerName: 'Worker #C567',
    camera: 'Manufacturing Floor',
    type: 'helmet',
    timestamp: '2025-11-18 13:58:11',
    severity: 'high',
    status: 'resolved',
  },
  {
    id: 'V-2025-1244',
    workerName: 'Worker #D891',
    camera: 'Loading Dock - North',
    type: 'both',
    timestamp: '2025-11-18 13:42:03',
    severity: 'critical',
    status: 'pending',
  },
  {
    id: 'V-2025-1243',
    workerName: 'Worker #E234',
    camera: 'Assembly Line 1',
    type: 'vest',
    timestamp: '2025-11-18 13:20:55',
    severity: 'medium',
    status: 'reviewed',
  },
  {
    id: 'V-2025-1242',
    workerName: 'Worker #F678',
    camera: 'Storage Area B',
    type: 'helmet',
    timestamp: '2025-11-18 12:55:34',
    severity: 'high',
    status: 'resolved',
  },
];*/




export function Violations() {
  const [filterType, setFilterType] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  const [violations, setViolations] = useState([]);

  useEffect(() => {
    fetchViolations();
  }, []);

  const fetchViolations = async () => {
    try {
      const response = await axios.get("http://127.0.0.1:8000/api/violations");

      const processed = response.data.map(v => ({
        id: v.violation_id,
        workerName: "Unknown Worker",
        camera: v.ihlal_yapilan_bolge,
        type: v.ihlal_cesidi,
        timestamp: v.tarih_saat,
        severity: "high",
        status: "pending"
      }));

      setViolations(processed);
    } catch (error) {
      console.error("Violations fetch error:", error);
    }
  };

  // Filtreleme Mantığı
  const filteredViolations = violations.filter(v => {
    const typeMatch = filterType === 'all' || (filterType === 'helmet' && v.type === 'head') || v.type === filterType;
    const statusMatch = filterStatus === 'all' || v.status === filterStatus;
    return typeMatch && statusMatch;
  });

  // İstatistikleri hesapla
  const stats = {
    total: violations.length,
    head: violations.filter(v => v.type === 'head').length,
    vest: violations.filter(v => v.type === 'vest').length,
    pending: violations.filter(v => v.status === 'pending').length
  };

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
                <p className="text-gray-500 text-sm font-medium">Total Today</p>
                <h3 className="text-3xl font-bold text-gray-900 mt-2">{stats.total}</h3>
            </div>
            <div className="w-12 h-12 bg-orange-100 rounded-lg flex items-center justify-center text-orange-600">
                <AlertTriangle className="w-6 h-6" />
            </div>
        </div>

        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex justify-between items-start">
            <div>
                <p className="text-gray-500 text-sm font-medium">Helmet Violations</p>
                <h3 className="text-3xl font-bold text-gray-900 mt-2">{stats.head}</h3>
            </div>
            <div className="w-12 h-12 bg-red-100 rounded-lg flex items-center justify-center text-red-600">
                <HardHat className="w-6 h-6" />
            </div>
        </div>

        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex justify-between items-start">
            <div>
                <p className="text-gray-500 text-sm font-medium">Vest Violations</p>
                <h3 className="text-3xl font-bold text-gray-900 mt-2">{stats.vest}</h3>
            </div>
            <div className="w-12 h-12 bg-orange-100 rounded-lg flex items-center justify-center text-orange-600">
                <Shirt className="w-6 h-6" />
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

      {/* Filters and Table Container */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        {/* Table Header & Filters */}
        <div className="p-6 border-b border-gray-100">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <h3 className="text-lg font-bold text-gray-900">Violation Records</h3>
            
            <div className="flex flex-wrap items-center gap-3">
              {/* Type Filter */}
              <div className="relative">
                <select 
                    value={filterType}
                    onChange={(e) => setFilterType(e.target.value)}
                    className="appearance-none bg-white border border-gray-300 text-gray-700 py-2 pl-3 pr-8 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                    <option value="all">All Types</option>
                    <option value="head">Helmet</option>
                    <option value="vest">Vest</option>
                    <option value="both">Both</option>
                </select>
                <ChevronDown className="w-4 h-4 text-gray-500 absolute right-2.5 top-3 pointer-events-none" />
              </div>

              {/* Status Filter */}
              <div className="relative">
                <select 
                    value={filterStatus}
                    onChange={(e) => setFilterStatus(e.target.value)}
                    className="appearance-none bg-white border border-gray-300 text-gray-700 py-2 pl-3 pr-8 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                    <option value="all">All Status</option>
                    <option value="pending">Pending</option>
                    <option value="reviewed">Reviewed</option>
                    <option value="resolved">Resolved</option>
                </select>
                <ChevronDown className="w-4 h-4 text-gray-500 absolute right-2.5 top-3 pointer-events-none" />
              </div>

              <button className="flex items-center gap-2 border border-gray-300 px-3 py-2 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors">
                <Filter className="w-4 h-4" />
                More
              </button>
            </div>
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead className="bg-gray-50/50">
              <tr>
                <th className="p-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Violation ID</th>
                <th className="p-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Worker</th>
                <th className="p-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Camera</th>
                <th className="p-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Type</th>
                <th className="p-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Timestamp</th>
                <th className="p-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Severity</th>
                <th className="p-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                <th className="p-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filteredViolations.map((violation) => (
                <tr key={violation.id} className="hover:bg-gray-50/50 transition-colors">
                  <td className="p-4 text-sm font-medium text-blue-600">{violation.id}</td>
                  <td className="p-4">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 bg-gray-100 rounded-full flex items-center justify-center text-xs font-bold text-gray-600">
                        {violation.workerName.split('#')[1]?.substring(0, 2)}
                      </div>
                      <span className="text-sm text-gray-900 font-medium">{violation.workerName}</span>
                    </div>
                  </td>
                  <td className="p-4">
                    <div className="flex items-center gap-2 text-gray-600">
                      <Camera className="w-4 h-4 text-gray-400" />
                      <span className="text-sm">{violation.camera}</span>
                    </div>
                  </td>
                  <td className="p-4">
                    {violation.type === 'head' && (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-50 text-red-700 border border-red-100">
                        <HardHat className="w-3 h-3" /> Helmet
                      </span>
                    )}
                    {violation.type === 'vest' && (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-orange-50 text-orange-700 border border-orange-100">
                        <Shirt className="w-3 h-3" /> Vest
                      </span>
                    )}
                    {violation.type === 'both' && (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-50 text-red-700 border border-red-100">
                        <AlertTriangle className="w-3 h-3" /> Both
                      </span>
                    )}
                  </td>
                  <td className="p-4">
                    <div className="flex items-center gap-2 text-gray-500">
                      <Calendar className="w-4 h-4" />
                      <span className="text-sm">{violation.timestamp}</span>
                    </div>
                  </td>
                  <td className="p-4">
                    <span className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium capitalize
                      ${violation.severity === 'critical' ? 'bg-red-100 text-red-700' : 
                        violation.severity === 'high' ? 'bg-orange-100 text-orange-700' : 
                        'bg-yellow-100 text-yellow-700'}`}>
                      {violation.severity}
                    </span>
                  </td>
                  <td className="p-4">
                    <span className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium capitalize border
                      ${violation.status === 'pending' ? 'bg-blue-50 text-blue-700 border-blue-100' : 
                        violation.status === 'reviewed' ? 'bg-yellow-50 text-yellow-700 border-yellow-100' : 
                        'bg-green-50 text-green-700 border-green-100'}`}>
                      {violation.status}
                    </span>
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
          
          {filteredViolations.length === 0 && (
              <div className="text-center py-10 text-gray-500">
                  <p>No violations found matching the filters.</p>
              </div>
          )}
        </div>
      </div>
    </div>
  );
}
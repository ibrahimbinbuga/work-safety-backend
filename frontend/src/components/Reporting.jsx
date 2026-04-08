import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Calendar, Download, FileText, TrendingUp, AlertTriangle,
  Camera, FileSpreadsheet, Shield, CheckCircle, Clock, Filter,
  ChevronDown, RefreshCw,
} from 'lucide-react';
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { useAuth } from '../context/AuthContext';
import { apiClient, addCompanyCodeToUrl } from '../utils/api';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TYPE_CONFIG = {
  head:   { label: 'No Helmet',      color: '#ef4444', bg: 'bg-red-50',    text: 'text-red-700',    border: 'border-red-100' },
  vest:   { label: 'No Vest',        color: '#f97316', bg: 'bg-orange-50', text: 'text-orange-700', border: 'border-orange-100' },
  fallen: { label: 'Fall Detected',  color: '#8b5cf6', bg: 'bg-purple-50', text: 'text-purple-700', border: 'border-purple-100' },
};

const STATUS_CONFIG = {
  pending:  { label: 'Pending',  bg: 'bg-yellow-50', text: 'text-yellow-700', border: 'border-yellow-100' },
  reviewed: { label: 'Reviewed', bg: 'bg-blue-50',   text: 'text-blue-700',   border: 'border-blue-100' },
  resolved: { label: 'Resolved', bg: 'bg-green-50',  text: 'text-green-700',  border: 'border-green-100' },
};

const PIE_COLORS = ['#ef4444', '#f97316', '#8b5cf6', '#3b82f6', '#10b981'];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso) {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleString('tr-TR', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function todayStr() {
  return new Date().toISOString().split('T')[0];
}

function daysAgoStr(n) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().split('T')[0];
}

// Violation type options grouped by model
const VIOLATION_TYPE_OPTIONS = [
  { group: 'PPE Model',             value: 'head',   label: 'No Helmet' },
  { group: 'PPE Model',             value: 'vest',   label: 'No Vest' },
  { group: 'Fall Detection Model',  value: 'fallen', label: 'Fall Detected' },
];

// Group keys → type values for "select whole model" shortcut
const MODEL_GROUPS = [
  { key: 'ppe',  label: 'PPE Model',            types: ['head', 'vest'] },
  { key: 'fall', label: 'Fall Detection Model',  types: ['fallen'] },
];

const STATUS_OPTIONS = [
  { value: 'pending',  label: 'Pending' },
  { value: 'reviewed', label: 'Reviewed' },
  { value: 'resolved', label: 'Resolved' },
];

function buildQueryString(fromDate, toDate, violationTypes, reviewStatuses) {
  const qs = new URLSearchParams();
  if (fromDate) qs.append('from_date', fromDate);
  if (toDate)   qs.append('to_date', toDate);
  violationTypes.forEach(t => qs.append('violation_types', t));
  reviewStatuses.forEach(s => qs.append('review_statuses', s));
  return qs.toString() ? '?' + qs.toString() : '';
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/**
 * Dropdown multi-select with checkbox items, grouped sections, and
 * "select whole group" shortcuts.
 *
 * Props:
 *   label        – placeholder text when nothing selected
 *   options      – [{ group?, value, label }]
 *   groups       – optional [{ key, label, types }] for group-select buttons
 *   selected     – string[]
 *   onChange     – (string[]) => void
 */
function MultiSelect({ label, options, groups, selected, onChange }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  // Close on outside click
  useEffect(() => {
    function handle(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, []);

  const toggle = (val) => {
    onChange(
      selected.includes(val) ? selected.filter(v => v !== val) : [...selected, val]
    );
  };

  const toggleGroup = (types) => {
    const allSelected = types.every(t => selected.includes(t));
    if (allSelected) {
      onChange(selected.filter(v => !types.includes(v)));
    } else {
      const merged = [...new Set([...selected, ...types])];
      onChange(merged);
    }
  };

  const selectedLabels = options
    .filter(o => selected.includes(o.value))
    .map(o => o.label);

  // Render grouped options
  const groupedOptions = () => {
    if (!options.some(o => o.group)) {
      return options.map(opt => (
        <label key={opt.value} className="flex items-center gap-2.5 px-3 py-2 hover:bg-gray-50 cursor-pointer text-sm">
          <input
            type="checkbox"
            checked={selected.includes(opt.value)}
            onChange={() => toggle(opt.value)}
            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          <span className="text-gray-700">{opt.label}</span>
        </label>
      ));
    }

    const groupNames = [...new Set(options.map(o => o.group))];
    return groupNames.map(groupName => {
      const groupOpts = options.filter(o => o.group === groupName);
      const groupTypes = groupOpts.map(o => o.value);
      const allGroupSelected = groupTypes.every(t => selected.includes(t));
      return (
        <div key={groupName}>
          <div
            className="flex items-center justify-between px-3 py-1.5 bg-gray-50 cursor-pointer group"
            onClick={() => toggleGroup(groupTypes)}
          >
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{groupName}</span>
            <span className={`text-xs font-medium transition-colors ${allGroupSelected ? 'text-blue-600' : 'text-gray-400 group-hover:text-blue-500'}`}>
              {allGroupSelected ? '✓ All' : 'Select all'}
            </span>
          </div>
          {groupOpts.map(opt => (
            <label key={opt.value} className="flex items-center gap-2.5 px-4 py-2 hover:bg-gray-50 cursor-pointer text-sm">
              <input
                type="checkbox"
                checked={selected.includes(opt.value)}
                onChange={() => toggle(opt.value)}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-gray-700">{opt.label}</span>
            </label>
          ))}
        </div>
      );
    });
  };

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between pl-3 pr-2.5 py-2 border border-gray-300 rounded-lg text-sm bg-white hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors"
      >
        <span className={selectedLabels.length ? 'text-gray-900' : 'text-gray-400'}>
          {selectedLabels.length === 0
            ? `All ${label}`
            : selectedLabels.length <= 2
              ? selectedLabels.join(', ')
              : `${selectedLabels.length} selected`}
        </span>
        <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform flex-shrink-0 ml-1 ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="absolute z-20 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden">
          {selected.length > 0 && (
            <div className="px-3 py-1.5 border-b border-gray-100">
              <button
                onClick={() => onChange([])}
                className="text-xs text-blue-600 hover:text-blue-800 font-medium"
              >
                Clear all
              </button>
            </div>
          )}
          <div className="max-h-56 overflow-y-auto">
            {groupedOptions()}
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, icon: Icon, iconBg, sub }) {
  return (
    <div className="bg-white p-5 rounded-xl shadow-sm border border-gray-100 flex items-start gap-4">
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-white flex-shrink-0 ${iconBg}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="text-gray-500 text-xs font-medium uppercase tracking-wide">{label}</p>
        <p className="text-2xl font-bold text-gray-900 mt-0.5">{value}</p>
        {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

function TypeBadge({ type }) {
  const cfg = TYPE_CONFIG[type] || { label: type, bg: 'bg-gray-50', text: 'text-gray-600', border: 'border-gray-200' };
  return (
    <span className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium border ${cfg.bg} ${cfg.text} ${cfg.border}`}>
      {cfg.label}
    </span>
  );
}

function StatusBadge({ status }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.pending;
  return (
    <span className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium border ${cfg.bg} ${cfg.text} ${cfg.border}`}>
      {cfg.label}
    </span>
  );
}

const CustomTooltipStyle = {
  backgroundColor: 'white',
  border: '1px solid #e5e7eb',
  borderRadius: '8px',
  boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)',
};

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function Reporting() {
  const { isAdmin, activeCompanyCode } = useAuth();

  // Filters
  const [fromDate, setFromDate] = useState(daysAgoStr(7));
  const [toDate, setToDate] = useState(todayStr());
  const [violationTypes, setViolationTypes] = useState([]);   // [] = all
  const [reviewStatuses, setReviewStatuses] = useState([]);   // [] = all
  const [quickPeriod, setQuickPeriod] = useState('week');

  // Data
  const [reportData, setReportData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [generated, setGenerated] = useState(false);

  // Export states
  const [exporting, setExporting] = useState({ pdf: false, csv: false, excel: false });

  const handleQuickSelect = (period) => {
    setQuickPeriod(period);
    const today = new Date();
    setToDate(today.toISOString().split('T')[0]);
    if (period === 'week') {
      setFromDate(daysAgoStr(7));
    } else if (period === 'month') {
      setFromDate(daysAgoStr(30));
    } else if (period === 'year') {
      setFromDate(daysAgoStr(365));
    }
  };

  const fetchReport = useCallback(async () => {
    if (!activeCompanyCode) return;
    setLoading(true);
    setError(null);
    try {
      const qs = buildQueryString(fromDate, toDate, violationTypes, reviewStatuses);
      const url = `/api/company/${activeCompanyCode}/reports/data${qs}`;
      const res = await apiClient.get(url);
      setReportData(res.data);
      setGenerated(true);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to load report data');
    } finally {
      setLoading(false);
    }
  }, [activeCompanyCode, fromDate, toDate, violationTypes, reviewStatuses]);

  // CSV / Excel download via backend
  const handleDownload = async (format) => {
    setExporting(prev => ({ ...prev, [format]: true }));
    try {
      const qs = buildQueryString(fromDate, toDate, violationTypes, reviewStatuses);
      const url = `/api/company/${activeCompanyCode}/reports/export/${format}${qs}`;
      const res = await apiClient.get(url, { responseType: 'blob' });
      const ext = format === 'excel' ? 'xlsx' : 'csv';
      const blob = new Blob([res.data]);
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `violations_${activeCompanyCode}_${todayStr()}.${ext}`;
      link.click();
      URL.revokeObjectURL(link.href);
    } catch {
      alert(`Failed to export ${format.toUpperCase()}`);
    } finally {
      setExporting(prev => ({ ...prev, [format]: false }));
    }
  };

  // PDF export — generated client-side with jsPDF
  const handlePdfExport = async () => {
    if (!reportData) return;
    setExporting(prev => ({ ...prev, pdf: true }));
    try {
      const { default: jsPDF } = await import('jspdf');
      const { default: autoTable } = await import('jspdf-autotable');

      const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
      const pageW = doc.internal.pageSize.getWidth();
      const pageH = doc.internal.pageSize.getHeight();
      const margin = 14;

      // ---- Header ----
      doc.setFillColor(30, 58, 95);
      doc.rect(0, 0, pageW, 28, 'F');
      doc.setTextColor(255, 255, 255);
      doc.setFontSize(16);
      doc.setFont('helvetica', 'bold');
      doc.text('Safety Violations Report', margin, 12);
      doc.setFontSize(9);
      doc.setFont('helvetica', 'normal');
      doc.text(`Company: ${activeCompanyCode?.toUpperCase()}`, margin, 20);
      doc.text(
        `Period: ${fromDate} → ${toDate}   |   Generated: ${new Date().toLocaleString('tr-TR')}`,
        margin, 25,
      );

      // ---- Summary cards ----
      const s = reportData.summary;
      const cards = [
        { label: 'Total Violations', value: String(s.total) },
        { label: 'No Helmet', value: String(s.by_type?.head || 0) },
        { label: 'No Vest', value: String(s.by_type?.vest || 0) },
        { label: 'Fall Detected', value: String(s.by_type?.fallen || 0) },
        { label: 'Pending Review', value: String(s.pending || 0) },
      ];
      const cardW = (pageW - margin * 2 - 4 * 4) / 5;
      let cardX = margin;
      const cardY = 34;
      cards.forEach(card => {
        doc.setFillColor(248, 250, 252);
        doc.setDrawColor(229, 231, 235);
        doc.roundedRect(cardX, cardY, cardW, 18, 2, 2, 'FD');
        doc.setTextColor(107, 114, 128);
        doc.setFontSize(6.5);
        doc.setFont('helvetica', 'normal');
        doc.text(card.label, cardX + cardW / 2, cardY + 6, { align: 'center' });
        doc.setTextColor(17, 24, 39);
        doc.setFontSize(13);
        doc.setFont('helvetica', 'bold');
        doc.text(card.value, cardX + cardW / 2, cardY + 14, { align: 'center' });
        cardX += cardW + 4;
      });

      // ---- Type distribution ----
      let curY = cardY + 24;
      doc.setTextColor(30, 58, 95);
      doc.setFontSize(11);
      doc.setFont('helvetica', 'bold');
      doc.text('Violation Distribution', margin, curY);
      curY += 4;

      const distData = (reportData.violation_distribution || []).map(d => [
        d.name,
        String(d.value),
        s.total > 0 ? `${((d.value / s.total) * 100).toFixed(1)}%` : '0%',
      ]);

      if (distData.length > 0) {
        autoTable(doc, {
          startY: curY,
          head: [['Violation Type', 'Count', 'Percentage']],
          body: distData,
          margin: { left: margin, right: margin },
          styles: { fontSize: 9, cellPadding: 3 },
          headStyles: { fillColor: [30, 58, 95], textColor: 255, fontStyle: 'bold' },
          alternateRowStyles: { fillColor: [249, 250, 251] },
          columnStyles: { 1: { halign: 'center' }, 2: { halign: 'center' } },
        });
        curY = doc.lastAutoTable.finalY + 8;
      } else {
        curY += 6;
      }

      // ---- Violations table ----
      doc.setTextColor(30, 58, 95);
      doc.setFontSize(11);
      doc.setFont('helvetica', 'bold');
      doc.text('Violation Details', margin, curY);
      curY += 4;

      const rows = (reportData.violations || []).slice(0, 200).map(v => [
        String(v.id),
        v.type_label || v.type,
        v.model || '—',
        v.camera_label || '—',
        v.datetime ? new Date(v.datetime).toLocaleString('tr-TR') : '—',
        (v.review_status || 'pending').charAt(0).toUpperCase() + (v.review_status || 'pending').slice(1),
      ]);

      autoTable(doc, {
        startY: curY,
        head: [['ID', 'Type', 'Model', 'Camera', 'Date & Time', 'Status']],
        body: rows,
        margin: { left: margin, right: margin },
        styles: { fontSize: 8, cellPadding: 3, overflow: 'linebreak' },
        headStyles: { fillColor: [30, 58, 95], textColor: 255, fontStyle: 'bold' },
        alternateRowStyles: { fillColor: [249, 250, 251] },
        columnStyles: {
          0: { cellWidth: 12 },
          1: { cellWidth: 28 },
          2: { cellWidth: 36 },
          3: { cellWidth: 26 },
          4: { cellWidth: 38 },
          5: { cellWidth: 22 },
        },
        didDrawCell: (data) => {
          if (data.section === 'body' && data.column.index === 5) {
            const status = (rows[data.row.index]?.[5] || '').toLowerCase();
            if (status === 'pending') {
              doc.setFillColor(254, 249, 195);
            } else if (status === 'reviewed') {
              doc.setFillColor(219, 234, 254);
            } else if (status === 'resolved') {
              doc.setFillColor(220, 252, 231);
            }
          }
        },
      });

      // ---- Footer ----
      const totalPages = doc.internal.getNumberOfPages();
      for (let i = 1; i <= totalPages; i++) {
        doc.setPage(i);
        doc.setFillColor(248, 250, 252);
        doc.rect(0, pageH - 10, pageW, 10, 'F');
        doc.setTextColor(156, 163, 175);
        doc.setFontSize(7);
        doc.setFont('helvetica', 'normal');
        doc.text(
          `SafetyWatch — Confidential   |   Page ${i} of ${totalPages}`,
          pageW / 2, pageH - 4,
          { align: 'center' },
        );
      }

      doc.save(`violations_${activeCompanyCode}_${todayStr()}.pdf`);
    } catch (err) {
      console.error('PDF export error:', err);
      alert('PDF export failed');
    } finally {
      setExporting(prev => ({ ...prev, pdf: false }));
    }
  };

  // Guard: admin must select a company
  if (isAdmin && !activeCompanyCode) {
    return (
      <div className="p-6">
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-8 text-center">
          <p className="text-amber-900 text-lg font-semibold">Please select a company from the sidebar.</p>
        </div>
      </div>
    );
  }

  const s = reportData?.summary;

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Reports & Analytics</h2>
        <p className="text-gray-500 text-sm mt-1">Generate and export corporate safety violation reports</p>
      </div>

      {/* Filter Panel */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <h3 className="text-base font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Filter className="w-4 h-4 text-gray-400" /> Report Filters
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
          {/* Date from */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1.5">From</label>
            <div className="relative">
              <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="date"
                value={fromDate}
                onChange={e => setFromDate(e.target.value)}
                className="w-full pl-9 pr-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Date to */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1.5">To</label>
            <div className="relative">
              <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="date"
                value={toDate}
                onChange={e => setToDate(e.target.value)}
                className="w-full pl-9 pr-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Violation type multi-select */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1.5">Violation Type</label>
            <MultiSelect
              label="Types"
              options={VIOLATION_TYPE_OPTIONS}
              selected={violationTypes}
              onChange={setViolationTypes}
            />
          </div>

          {/* Review status multi-select */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1.5">Review Status</label>
            <MultiSelect
              label="Statuses"
              options={STATUS_OPTIONS}
              selected={reviewStatuses}
              onChange={setReviewStatuses}
            />
          </div>
        </div>

        {/* Quick period + generate button */}
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-xs font-medium text-gray-500">Quick:</span>
          {[
            { key: 'week', label: 'Last 7 days' },
            { key: 'month', label: 'Last 30 days' },
            { key: 'year', label: 'Last 365 days' },
          ].map(({ key, label }) => (
            <button
              key={key}
              onClick={() => handleQuickSelect(key)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                quickPeriod === key
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
              }`}
            >
              {label}
            </button>
          ))}

          <button
            onClick={fetchReport}
            disabled={loading}
            className="ml-auto flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            {loading ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <FileText className="w-4 h-4" />
            )}
            {loading ? 'Generating…' : 'Generate Report'}
          </button>
        </div>

        {error && (
          <p className="mt-3 text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">{error}</p>
        )}
      </div>

      {/* --- REPORT CONTENT --- */}
      {!generated ? (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-14 text-center">
          <FileText className="w-14 h-14 text-gray-200 mx-auto mb-3" />
          <p className="text-gray-900 font-semibold">No report generated yet</p>
          <p className="text-gray-400 text-sm mt-1">Set filters above and click "Generate Report"</p>
        </div>
      ) : (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
            <StatCard label="Total Violations" value={s?.total ?? 0}        icon={TrendingUp}    iconBg="bg-blue-500" />
            <StatCard label="No Helmet"        value={s?.by_type?.head ?? 0} icon={AlertTriangle} iconBg="bg-red-500" />
            <StatCard label="No Vest"          value={s?.by_type?.vest ?? 0} icon={Shield}        iconBg="bg-orange-500" />
            <StatCard label="Fall Detected"    value={s?.by_type?.fallen ?? 0} icon={AlertTriangle} iconBg="bg-purple-500" />
            <StatCard label="Pending Review"   value={s?.pending ?? 0}       icon={Clock}         iconBg="bg-yellow-500"
              sub={`${s?.reviewed ?? 0} reviewed · ${s?.resolved ?? 0} resolved`}
            />
          </div>

          {/* Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Daily trend */}
            <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-gray-100 p-6">
              <h3 className="text-base font-bold text-gray-900 mb-1">Violation Trend</h3>
              <p className="text-gray-400 text-xs mb-5">Daily violations in selected period</p>
              {reportData?.daily_data?.length > 0 ? (
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={reportData.daily_data}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
                      <XAxis dataKey="date" stroke="#9ca3af" tickLine={false} axisLine={false} tick={{ fontSize: 11 }} />
                      <YAxis stroke="#9ca3af" tickLine={false} axisLine={false} tick={{ fontSize: 11 }} allowDecimals={false} />
                      <Tooltip contentStyle={CustomTooltipStyle} />
                      <Line type="monotone" dataKey="violations" stroke="#3b82f6" strokeWidth={2.5} dot={{ r: 3 }} name="Violations" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="h-64 flex items-center justify-center text-gray-300 text-sm">No data</div>
              )}
            </div>

            {/* Type distribution pie */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
              <h3 className="text-base font-bold text-gray-900 mb-1">By Type</h3>
              <p className="text-gray-400 text-xs mb-4">Distribution of violation types</p>
              {reportData?.violation_distribution?.length > 0 ? (
                <>
                  <div className="h-44">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={reportData.violation_distribution}
                          cx="50%"
                          cy="50%"
                          innerRadius={45}
                          outerRadius={70}
                          paddingAngle={4}
                          dataKey="value"
                        >
                          {reportData.violation_distribution.map((entry, i) => (
                            <Cell
                              key={i}
                              fill={TYPE_CONFIG[entry.type]?.color || PIE_COLORS[i % PIE_COLORS.length]}
                            />
                          ))}
                        </Pie>
                        <Tooltip contentStyle={CustomTooltipStyle} />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="space-y-2 mt-2">
                    {reportData.violation_distribution.map((d, i) => (
                      <div key={i} className="flex items-center justify-between text-sm">
                        <div className="flex items-center gap-2">
                          <span
                            className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                            style={{ backgroundColor: TYPE_CONFIG[d.type]?.color || PIE_COLORS[i % PIE_COLORS.length] }}
                          />
                          <span className="text-gray-600">{d.name}</span>
                        </div>
                        <span className="font-semibold text-gray-900">{d.value}</span>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="h-44 flex items-center justify-center text-gray-300 text-sm">No data</div>
              )}
            </div>
          </div>

          {/* Camera bar chart + status pie */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Camera distribution */}
            <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-gray-100 p-6">
              <h3 className="text-base font-bold text-gray-900 mb-1">Violations by Camera</h3>
              <p className="text-gray-400 text-xs mb-5">Top cameras with most violations</p>
              {reportData?.camera_data?.length > 0 ? (
                <div className="h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={reportData.camera_data} layout="vertical" margin={{ left: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" horizontal={false} />
                      <XAxis type="number" stroke="#9ca3af" tickLine={false} axisLine={false} tick={{ fontSize: 11 }} allowDecimals={false} />
                      <YAxis type="category" dataKey="camera" stroke="#9ca3af" tickLine={false} axisLine={false} tick={{ fontSize: 11 }} width={80} />
                      <Tooltip contentStyle={CustomTooltipStyle} cursor={{ fill: '#f3f4f6' }} />
                      <Bar dataKey="violations" fill="#3b82f6" radius={[0, 4, 4, 0]} name="Violations" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="h-56 flex items-center justify-center text-gray-300 text-sm">No data</div>
              )}
            </div>

            {/* Status breakdown */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
              <h3 className="text-base font-bold text-gray-900 mb-1">Review Status</h3>
              <p className="text-gray-400 text-xs mb-5">Breakdown by review progress</p>
              <div className="space-y-3">
                {[
                  { key: 'pending',  label: 'Pending',  color: '#eab308', value: s?.pending  ?? 0 },
                  { key: 'reviewed', label: 'Reviewed', color: '#3b82f6', value: s?.reviewed ?? 0 },
                  { key: 'resolved', label: 'Resolved', color: '#10b981', value: s?.resolved ?? 0 },
                ].map(item => {
                  const total = s?.total || 1;
                  const pct = Math.round((item.value / total) * 100);
                  return (
                    <div key={item.key}>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="text-gray-600">{item.label}</span>
                        <span className="font-semibold text-gray-900">{item.value}</span>
                      </div>
                      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all"
                          style={{ width: `${pct}%`, backgroundColor: item.color }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Violations table */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-gray-900">Violation Details</h3>
                <p className="text-gray-400 text-xs mt-0.5">{reportData?.violations?.length ?? 0} records in selected period</p>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-gray-50 border-b border-gray-100">
                  <tr>
                    <th className="px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">ID</th>
                    <th className="px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Type</th>
                    <th className="px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Model</th>
                    <th className="px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Camera</th>
                    <th className="px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Date & Time</th>
                    <th className="px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                    <th className="px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Worker</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {(reportData?.violations ?? []).length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-5 py-10 text-center text-gray-400">No violations found for the selected filters</td>
                    </tr>
                  ) : (
                    (reportData?.violations ?? []).map(v => (
                      <tr key={v.id} className="hover:bg-gray-50/60 transition-colors">
                        <td className="px-5 py-3 font-mono text-xs text-gray-500">#{v.id}</td>
                        <td className="px-5 py-3"><TypeBadge type={v.type} /></td>
                        <td className="px-5 py-3 text-gray-600">{v.model}</td>
                        <td className="px-5 py-3 text-gray-600 flex items-center gap-1.5">
                          <Camera className="w-3.5 h-3.5 text-gray-400" />{v.camera_label}
                        </td>
                        <td className="px-5 py-3 text-gray-500">{formatDate(v.datetime)}</td>
                        <td className="px-5 py-3"><StatusBadge status={v.review_status} /></td>
                        <td className="px-5 py-3 text-gray-500">#{v.worker_id}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Export section */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <div className="mb-4">
              <h3 className="text-base font-bold text-gray-900 flex items-center gap-2">
                <Download className="w-4 h-4 text-gray-400" /> Export Report
              </h3>
              <p className="text-gray-400 text-xs mt-0.5">Download the current report in your preferred format</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <button
                onClick={handlePdfExport}
                disabled={exporting.pdf}
                className="flex items-center justify-center gap-2 bg-red-600 hover:bg-red-700 disabled:opacity-60 text-white py-3 rounded-lg font-medium text-sm transition-colors"
              >
                {exporting.pdf ? <RefreshCw className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
                {exporting.pdf ? 'Generating PDF…' : 'Download PDF'}
              </button>
              <button
                onClick={() => handleDownload('excel')}
                disabled={exporting.excel}
                className="flex items-center justify-center gap-2 bg-green-600 hover:bg-green-700 disabled:opacity-60 text-white py-3 rounded-lg font-medium text-sm transition-colors"
              >
                {exporting.excel ? <RefreshCw className="w-4 h-4 animate-spin" /> : <FileSpreadsheet className="w-4 h-4" />}
                {exporting.excel ? 'Generating Excel…' : 'Download Excel'}
              </button>
              <button
                onClick={() => handleDownload('csv')}
                disabled={exporting.csv}
                className="flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white py-3 rounded-lg font-medium text-sm transition-colors"
              >
                {exporting.csv ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                {exporting.csv ? 'Generating CSV…' : 'Download CSV'}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

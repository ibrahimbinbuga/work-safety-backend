import { useState } from 'react';
import { Calendar, Download, FileText, TrendingUp, AlertTriangle, Camera, Clock, FileSpreadsheet } from 'lucide-react';
import { BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

// Rapor Verisi (Şimdilik Statik)
const reportData = {
  summary: {
    totalDetections: 8567,
    helmetViolations: 142,
    vestViolations: 98,
    topCamera: 'Warehouse A - Entry',
    peakHours: '14:00 - 16:00'
  },
  dailyData: [
    { date: 'Nov 11', detections: 1230, helmetViolations: 18, vestViolations: 12 },
    { date: 'Nov 12', detections: 1156, helmetViolations: 22, vestViolations: 15 },
    { date: 'Nov 13', detections: 1342, helmetViolations: 19, vestViolations: 14 },
    { date: 'Nov 14', detections: 1189, helmetViolations: 25, vestViolations: 18 },
    { date: 'Nov 15', detections: 1098, helmetViolations: 16, vestViolations: 11 },
    { date: 'Nov 16', detections: 876, helmetViolations: 21, vestViolations: 13 },
    { date: 'Nov 17', detections: 1676, helmetViolations: 21, vestViolations: 15 },
  ],
  violationDistribution: [
    { name: 'Helmet Violations', value: 142, color: '#ef4444' },
    { name: 'Vest Violations', value: 98, color: '#f97316' },
    { name: 'Both Violations', value: 34, color: '#dc2626' },
  ],
  hourlyActivity: [
    { hour: '00:00', count: 45 },
    { hour: '02:00', count: 23 },
    { hour: '04:00', count: 12 },
    { hour: '06:00', count: 156 },
    { hour: '08:00', count: 567 },
    { hour: '10:00', count: 892 },
    { hour: '12:00', count: 734 },
    { hour: '14:00', count: 1234 },
    { hour: '16:00', count: 1156 },
    { hour: '18:00', count: 678 },
    { hour: '20:00', count: 234 },
    { hour: '22:00', count: 89 },
  ],
  violations: [
    { id: 'V-2025-1247', worker: 'Worker #A342', camera: 'Warehouse A', type: 'helmet', date: '2025-11-17 14:23' },
    { id: 'V-2025-1246', worker: 'Worker #B128', camera: 'Construction Zone 3', type: 'vest', date: '2025-11-17 13:15' },
    { id: 'V-2025-1245', worker: 'Worker #C567', camera: 'Manufacturing Floor', type: 'helmet', date: '2025-11-17 12:58' },
    { id: 'V-2025-1244', worker: 'Worker #D891', camera: 'Loading Dock', type: 'both', date: '2025-11-17 11:42' },
    { id: 'V-2025-1243', worker: 'Worker #E234', camera: 'Assembly Line 1', type: 'vest', date: '2025-11-17 10:20' },
  ]
};

export function Reporting() {
  const [reportPeriod, setReportPeriod] = useState('week');
  const [startDate, setStartDate] = useState('2025-11-11');
  const [endDate, setEndDate] = useState('2025-11-17');
  const [reportGenerated, setReportGenerated] = useState(false);

  const handleGenerateReport = () => {
    setReportGenerated(true);
  };

  const handleQuickSelect = (period) => {
    setReportPeriod(period);
    const today = new Date('2025-11-18');
    
    if (period === 'week') {
      const weekStart = new Date(today);
      weekStart.setDate(today.getDate() - 7);
      setStartDate(weekStart.toISOString().split('T')[0]);
      setEndDate(today.toISOString().split('T')[0]);
    } else if (period === 'month') {
      const monthStart = new Date(today);
      monthStart.setMonth(today.getMonth() - 1);
      setStartDate(monthStart.toISOString().split('T')[0]);
      setEndDate(today.toISOString().split('T')[0]);
    } else if (period === 'year') {
      const yearStart = new Date(today);
      yearStart.setFullYear(today.getFullYear() - 1);
      setStartDate(yearStart.toISOString().split('T')[0]);
      setEndDate(today.toISOString().split('T')[0]);
    }
  };

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Reports & Analytics</h2>
        <p className="text-gray-500 text-sm mt-1">Generate comprehensive safety reports and analyze trends</p>
      </div>

      {/* Date Range Selector */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <div className="mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Generate Report</h3>
          <p className="text-gray-500 text-sm">Select a time period to generate detailed reports</p>
        </div>

        <div className="space-y-6">
          {/* Quick Options */}
          <div>
            <label className="text-gray-700 text-sm font-medium mb-3 block">Quick Select</label>
            <div className="flex flex-wrap gap-3">
              {['week', 'month', 'year'].map((period) => (
                <button
                    key={period}
                    onClick={() => handleQuickSelect(period)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors border ${
                        reportPeriod === period 
                        ? 'bg-blue-600 text-white border-blue-600' 
                        : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                    }`}
                >
                    This {period.charAt(0).toUpperCase() + period.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {/* Custom Date Range */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
            <div>
              <label className="text-gray-700 text-sm font-medium mb-2 block">Start Date</label>
              <div className="relative">
                <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            <div>
              <label className="text-gray-700 text-sm font-medium mb-2 block">End Date</label>
              <div className="relative">
                <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            <button 
              className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium flex items-center justify-center gap-2 transition-colors h-[42px]"
              onClick={handleGenerateReport}
            >
              <FileText className="w-4 h-4" />
              Generate Report
            </button>
          </div>
        </div>
      </div>

      {reportGenerated ? (
        <>
          {/* Report Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex justify-between items-start">
              <div>
                <p className="text-gray-500 text-sm font-medium">Total Detections</p>
                <h3 className="text-2xl font-bold text-gray-900 mt-2">{reportData.summary.totalDetections.toLocaleString()}</h3>
              </div>
              <div className="w-10 h-10 bg-blue-500 rounded-lg flex items-center justify-center text-white">
                <TrendingUp className="w-5 h-5" />
              </div>
            </div>

            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex justify-between items-start">
              <div>
                <p className="text-gray-500 text-sm font-medium">Helmet Violations</p>
                <h3 className="text-2xl font-bold text-gray-900 mt-2">{reportData.summary.helmetViolations}</h3>
              </div>
              <div className="w-10 h-10 bg-red-500 rounded-lg flex items-center justify-center text-white">
                <AlertTriangle className="w-5 h-5" />
              </div>
            </div>

            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex justify-between items-start">
              <div>
                <p className="text-gray-500 text-sm font-medium">Vest Violations</p>
                <h3 className="text-2xl font-bold text-gray-900 mt-2">{reportData.summary.vestViolations}</h3>
              </div>
              <div className="w-10 h-10 bg-orange-500 rounded-lg flex items-center justify-center text-white">
                <AlertTriangle className="w-5 h-5" />
              </div>
            </div>

            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
              <p className="text-gray-500 text-sm font-medium mb-2">Top Camera</p>
              <div className="flex items-center gap-2">
                <Camera className="w-4 h-4 text-gray-400 flex-shrink-0" />
                <p className="text-gray-900 text-sm font-semibold truncate">{reportData.summary.topCamera}</p>
              </div>
            </div>

            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
              <p className="text-gray-500 text-sm font-medium mb-2">Peak Hours</p>
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-gray-400 flex-shrink-0" />
                <p className="text-gray-900 text-sm font-semibold">{reportData.summary.peakHours}</p>
              </div>
            </div>
          </div>

          {/* Charts Section */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Detection Trend Chart */}
            <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-gray-100 p-6">
              <div className="mb-6">
                <h3 className="text-lg font-bold text-gray-900">Detection Trend</h3>
                <p className="text-gray-500 text-sm">Daily detections and violations over selected period</p>
              </div>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={reportData.dailyData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
                    <XAxis dataKey="date" stroke="#6b7280" tickLine={false} axisLine={false} />
                    <YAxis stroke="#6b7280" tickLine={false} axisLine={false} />
                    <Tooltip 
                      contentStyle={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderRadius: '8px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' }} 
                    />
                    <Legend />
                    <Line type="monotone" dataKey="detections" stroke="#3b82f6" strokeWidth={3} dot={{r: 4}} name="Total Detections" />
                    <Line type="monotone" dataKey="helmetViolations" stroke="#ef4444" strokeWidth={3} dot={{r: 4}} name="Helmet Violations" />
                    <Line type="monotone" dataKey="vestViolations" stroke="#f97316" strokeWidth={3} dot={{r: 4}} name="Vest Violations" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Violation Distribution */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
              <div className="mb-6">
                <h3 className="text-lg font-bold text-gray-900">Violation Distribution</h3>
                <p className="text-gray-500 text-sm">Breakdown by violation type</p>
              </div>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={reportData.violationDistribution}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={80}
                      paddingAngle={5}
                      dataKey="value"
                    >
                      {reportData.violationDistribution.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="space-y-3 mt-4">
                  {reportData.violationDistribution.map((item, index) => (
                    <div key={index} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: item.color }}></div>
                        <span className="text-gray-700 text-sm">{item.name}</span>
                      </div>
                      <span className="text-gray-900 font-semibold">{item.value}</span>
                    </div>
                  ))}
              </div>
            </div>
          </div>

          {/* Hourly Activity Heatmap */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <div className="mb-6">
              <h3 className="text-lg font-bold text-gray-900">Hourly Activity Pattern</h3>
              <p className="text-gray-500 text-sm">Detection activity throughout the day</p>
            </div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={reportData.hourlyActivity}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
                  <XAxis dataKey="hour" stroke="#6b7280" tickLine={false} axisLine={false} />
                  <YAxis stroke="#6b7280" tickLine={false} axisLine={false} />
                  <Tooltip 
                    cursor={{fill: '#F3F4F6'}}
                    contentStyle={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderRadius: '8px' }} 
                  />
                  <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Report Table */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <div className="p-6 border-b border-gray-100 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
               <div>
                  <h3 className="text-lg font-bold text-gray-900">Violation Details</h3>
                  <p className="text-gray-500 text-sm">Complete list of violations in selected period</p>
               </div>
            </div>
            
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead className="bg-gray-50/50">
                  <tr>
                    <th className="p-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Thumbnail</th>
                    <th className="p-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Violation ID</th>
                    <th className="p-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Worker</th>
                    <th className="p-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Camera</th>
                    <th className="p-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Type</th>
                    <th className="p-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Date & Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {reportData.violations.map((violation) => (
                    <tr key={violation.id} className="hover:bg-gray-50/50 transition-colors">
                      <td className="p-4">
                        <div className="w-12 h-12 bg-gray-100 rounded-lg flex items-center justify-center">
                          <Camera className="w-5 h-5 text-gray-400" />
                        </div>
                      </td>
                      <td className="p-4 text-sm font-medium text-blue-600">{violation.id}</td>
                      <td className="p-4">
                        <div className="flex items-center gap-2">
                          <div className="w-8 h-8 bg-gray-100 rounded-full flex items-center justify-center text-xs font-bold text-gray-600">
                            {violation.worker.split('#')[1]?.substring(0, 2)}
                          </div>
                          <span className="text-sm text-gray-900">{violation.worker}</span>
                        </div>
                      </td>
                      <td className="p-4 text-sm text-gray-600">{violation.camera}</td>
                      <td className="p-4">
                        <span className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium border
                          ${violation.type === 'helmet' ? 'bg-red-50 text-red-700 border-red-100' : 
                            violation.type === 'vest' ? 'bg-orange-50 text-orange-700 border-orange-100' : 
                            'bg-red-50 text-red-700 border-red-100'}`}>
                          {violation.type.charAt(0).toUpperCase() + violation.type.slice(1)}
                        </span>
                      </td>
                      <td className="p-4 text-sm text-gray-500">{violation.date}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* --- EXPORT REPORT CARD (SAYFANIN EN ALTINDA) --- */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <div className="mb-4">
                <h3 className="text-lg font-bold text-gray-900">Export Report</h3>
                <p className="text-gray-500 text-sm">Download this report in various formats</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <button className="flex items-center justify-center gap-2 bg-red-600 hover:bg-red-700 text-white py-3 rounded-lg font-medium transition-colors shadow-sm">
                    <FileText className="w-5 h-5" />
                    Download as PDF
                </button>
                <button className="flex items-center justify-center gap-2 bg-green-600 hover:bg-green-700 text-white py-3 rounded-lg font-medium transition-colors shadow-sm">
                    <FileSpreadsheet className="w-5 h-5" />
                    Download as Excel
                </button>
                <button className="flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white py-3 rounded-lg font-medium transition-colors shadow-sm">
                    <Download className="w-5 h-5" />
                    Download as CSV
                </button>
            </div>
          </div>

        </>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-12 text-center">
          <FileText className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-bold text-gray-900 mb-2">No Report Generated</h3>
          <p className="text-gray-500">Select a date range above and click "Generate Report" to view analytics</p>
        </div>
      )}
    </div>
  );
}
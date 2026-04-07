import { useEffect, useState } from 'react';
import { apiClient, addCompanyCodeToUrl } from '../utils/api';
import { Camera, Activity, AlertTriangle, CheckCircle, XCircle, Shirt, HardHat, Clock } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { useAuth } from '../context/AuthContext';

// Son 7 günün ihlal verilerinden grafik datası üret
const buildChartData = (violations) => {
  const now = new Date();
  return Array.from({ length: 7 }, (_, i) => {
    const day = new Date(now);
    day.setDate(now.getDate() - (6 - i));
    const label = day.toLocaleDateString('en-US', { weekday: 'short' });
    const startMs = new Date(day).setHours(0, 0, 0, 0);
    const endMs = new Date(day).setHours(23, 59, 59, 999);

    const dayV = violations.filter((v) => {
      const ts = new Date(v.tarih_saat).getTime();
      return ts >= startMs && ts <= endMs;
    });

    return {
      date: label,
      PPE: dayV.filter((v) => v.ihlal_cesidi === 'head' || v.ihlal_cesidi === 'vest').length,
      Fall: dayV.filter((v) => v.ihlal_cesidi === 'fallen').length,
    };
  });
};

export function Dashboard() {
  const { isAdmin, activeCompanyCode } = useAuth();
  const [cameras, setCameras] = useState([]);
  const [violations, setViolations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [chartData, setChartData] = useState([]);

  useEffect(() => {
    const fetchAll = async () => {
      try {
        setLoading(true);
        const [camerasRes, violationsRes] = await Promise.all([
          apiClient.get(addCompanyCodeToUrl('/api/cameras', activeCompanyCode)),
          apiClient.get(addCompanyCodeToUrl('/api/violations', activeCompanyCode)),
        ]);
        const cams = Array.isArray(camerasRes.data) ? camerasRes.data : [];
        const viols = Array.isArray(violationsRes.data) ? violationsRes.data : [];
        setCameras(cams);
        setViolations(viols);
        setChartData(buildChartData(viols));
      } catch (err) {
        console.error('Dashboard fetch error:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, [activeCompanyCode]);

  // Her 30 saniyede violations yenile (cameras'ı kesmemek için ayrı)
  useEffect(() => {
    const refresh = async () => {
      try {
        const res = await apiClient.get(addCompanyCodeToUrl('/api/violations', activeCompanyCode));
        const viols = Array.isArray(res.data) ? res.data : [];
        setViolations(viols);
        setChartData(buildChartData(viols));
      } catch {/* sessizce geç */}
    };
    const id = setInterval(refresh, 30000);
    return () => clearInterval(id);
  }, [activeCompanyCode]);

  // --- Hesaplamalar ---
  const onlineCameras = cameras.filter((c) => c.status === 'online').length;
  const ppeViolations = violations.filter((v) => v.ihlal_cesidi === 'head' || v.ihlal_cesidi === 'vest').length;
  const fallViolations = violations.filter((v) => v.ihlal_cesidi === 'fallen').length;
  const pendingCount = violations.filter((v) => (v.review_status || 'pending') === 'pending').length;

  // System Status — gerçek veriden türet
  const cameraStatus = cameras.length === 0
    ? { label: 'No cameras', status: 'warning' }
    : onlineCameras === cameras.length
    ? { label: `${onlineCameras}/${cameras.length} online`, status: 'online' }
    : onlineCameras === 0
    ? { label: `0/${cameras.length} online`, status: 'error' }
    : { label: `${onlineCameras}/${cameras.length} online`, status: 'warning' };

  const reviewStatus = pendingCount === 0
    ? { label: 'All reviewed', status: 'online' }
    : pendingCount <= 5
    ? { label: `${pendingCount} pending`, status: 'warning' }
    : { label: `${pendingCount} pending`, status: 'error' };

  const systemServices = [
    { name: 'Camera Network', ...cameraStatus },
    { name: 'Violation Review', ...reviewStatus },
    {
      name: 'Detection Activity',
      label: violations.length > 0 ? `${violations.length} total recorded` : 'No violations yet',
      status: 'online',
    },
  ];

  // Stats kartları — sadece aktif violation tipleri
  const statsCards = [
    {
      title: 'Active Cameras',
      value: cameras.length,
      sub: `${onlineCameras} online`,
      icon: Camera,
      color: 'bg-blue-500',
    },
    {
      title: 'Total Violations',
      value: violations.length,
      sub: `${pendingCount} pending review`,
      icon: Activity,
      color: 'bg-orange-500',
    },
    {
      title: 'PPE Violations',
      value: ppeViolations,
      sub: 'No helmet / No vest',
      icon: HardHat,
      color: 'bg-red-500',
    },
    {
      title: 'Fall Detections',
      value: fallViolations,
      sub: 'Fallen workers',
      icon: AlertTriangle,
      color: 'bg-purple-500',
    },
  ];

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

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {statsCards.map((stat, i) => {
          const Icon = stat.icon;
          return (
            <div key={i} className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex justify-between items-start">
              <div>
                <p className="text-gray-500 text-sm font-medium">{stat.title}</p>
                <h3 className="text-2xl font-bold text-gray-900 mt-2 mb-1">
                  {loading ? '—' : stat.value}
                </h3>
                <p className="text-gray-400 text-xs">{stat.sub}</p>
              </div>
              <div className={`${stat.color} w-12 h-12 rounded-lg flex items-center justify-center shadow-sm`}>
                <Icon className="w-6 h-6 text-white" />
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Chart — gerçek ihlal verisi */}
        <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <div className="mb-6">
            <h3 className="text-lg font-bold text-gray-900">Violations — Last 7 Days</h3>
            <p className="text-gray-500 text-sm">PPE and fall detection violations per day</p>
          </div>
          <div className="h-72">
            {loading ? (
              <div className="flex items-center justify-center h-full text-gray-400 text-sm">Loading...</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} barCategoryGap="30%">
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
                  <XAxis dataKey="date" stroke="#6b7280" tickLine={false} axisLine={false} />
                  <YAxis stroke="#6b7280" tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip
                    cursor={{ fill: '#F3F4F6' }}
                    contentStyle={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderRadius: '8px' }}
                  />
                  <Legend />
                  <Bar dataKey="PPE" fill="#ef4444" radius={[4, 4, 0, 0]} name="PPE Violation" />
                  <Bar dataKey="Fall" fill="#8b5cf6" radius={[4, 4, 0, 0]} name="Fall Detected" />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* System Status — dinamik */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <div className="mb-6">
            <h3 className="text-lg font-bold text-gray-900">System Status</h3>
            <p className="text-gray-500 text-sm">Live service overview</p>
          </div>
          <div className="space-y-4">
            {systemServices.map((svc, i) => (
              <div key={i} className="flex items-start justify-between pb-4 border-b border-gray-50 last:border-0 last:pb-0">
                <div className="flex items-start gap-3">
                  {svc.status === 'online' ? (
                    <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
                  ) : svc.status === 'warning' ? (
                    <AlertTriangle className="w-5 h-5 text-orange-400 flex-shrink-0 mt-0.5" />
                  ) : (
                    <XCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                  )}
                  <div>
                    <p className="text-gray-900 text-sm font-medium">{svc.name}</p>
                    <p className="text-gray-400 text-xs">{svc.label}</p>
                  </div>
                </div>
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium border ${
                  svc.status === 'online'
                    ? 'bg-green-50 text-green-700 border-green-100'
                    : svc.status === 'warning'
                    ? 'bg-orange-50 text-orange-700 border-orange-100'
                    : 'bg-red-50 text-red-700 border-red-100'
                }`}>
                  {svc.status}
                </span>
              </div>
            ))}

            {/* Kamera listesi özeti */}
            {!loading && cameras.length > 0 && (
              <div className="pt-2 space-y-1">
                {cameras.slice(0, 4).map((cam) => (
                  <div key={cam.id} className="flex items-center justify-between text-xs text-gray-500">
                    <span className="truncate max-w-[120px]">{cam.name}</span>
                    <span className={`flex items-center gap-1 font-medium ${
                      cam.status === 'online' ? 'text-green-600' : 'text-gray-400'
                    }`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${
                        cam.status === 'online' ? 'bg-green-500' : 'bg-gray-300'
                      }`} />
                      {cam.status}
                    </span>
                  </div>
                ))}
                {cameras.length > 4 && (
                  <p className="text-xs text-gray-400">+{cameras.length - 4} more</p>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Recent Violations */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <div className="mb-4">
          <h3 className="text-lg font-bold text-gray-900">Recent Violations</h3>
          <p className="text-gray-500 text-sm">Last 5 recorded violations</p>
        </div>
        {loading ? (
          <p className="text-gray-400 text-sm text-center py-6">Loading...</p>
        ) : violations.length === 0 ? (
          <p className="text-gray-400 text-sm text-center py-6">No violations recorded yet.</p>
        ) : (
          <div className="divide-y divide-gray-50">
            {violations.slice(0, 5).map((v) => {
              const typeLabels = {
                head: { label: 'No Helmet', color: 'bg-red-50 text-red-700 border-red-100' },
                vest: { label: 'No Vest', color: 'bg-orange-50 text-orange-700 border-orange-100' },
                fallen: { label: 'Fall Detected', color: 'bg-purple-50 text-purple-700 border-purple-100' },
                sitting: { label: 'Sitting', color: 'bg-blue-50 text-blue-700 border-blue-100' },
                standing: { label: 'Standing', color: 'bg-gray-50 text-gray-600 border-gray-200' },
              };
              const typeConf = typeLabels[v.ihlal_cesidi] || { label: v.ihlal_cesidi, color: 'bg-gray-50 text-gray-600 border-gray-200' };
              const statusConf = {
                pending: 'bg-blue-50 text-blue-700 border-blue-100',
                reviewed: 'bg-yellow-50 text-yellow-700 border-yellow-100',
                resolved: 'bg-green-50 text-green-700 border-green-100',
              }[v.review_status || 'pending'];

              return (
                <div key={v.id} className="flex items-center justify-between py-3">
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-gray-400 w-8">#{v.id}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${typeConf.color}`}>
                      {typeConf.label}
                    </span>
                    <span className="text-xs text-gray-500">{v.ihlal_yapilan_bolge || '—'}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-gray-400">
                      {new Date(v.tarih_saat).toLocaleString('tr-TR', {
                        day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'
                      })}
                    </span>
                    <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${statusConf}`}>
                      {v.review_status || 'pending'}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

    </div>
  );
}

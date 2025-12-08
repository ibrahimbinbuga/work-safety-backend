import { useEffect, useState } from 'react';
import axios from 'axios';
import { Camera, Activity, AlertTriangle, CheckCircle, XCircle, MoreVertical, Shirt, HardHat } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

// Grafik Verisi (Statik)
const chartData = [
  { date: 'Mon', detections: 856, violations: 42 },
  { date: 'Tue', detections: 932, violations: 38 },
  { date: 'Wed', detections: 1104, violations: 45 },
  { date: 'Thu', detections: 978, violations: 35 },
  { date: 'Fri', detections: 1247, violations: 40 },
  { date: 'Sat', detections: 654, violations: 18 },
  { date: 'Sun', detections: 423, violations: 12 },
];

// Sistem Durumu Verisi
const systemStatus = [
  { name: 'AI Detection Model', status: 'online', uptime: '99.8%' },
  { name: 'Database Server', status: 'online', uptime: '100%' },
  { name: 'Alert Service', status: 'online', uptime: '99.9%' },
  { name: 'Camera Network', status: 'warning', uptime: '95.2%' },
];

export function Dashboard() {
  const [cameras, setCameras] = useState([]);
  const [loading, setLoading] = useState(true);

  // Backend'den Kamera Verilerini Çek
  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await axios.get('http://127.0.0.1:8000/api/cameras');
        if (Array.isArray(response.data)) {
            setCameras(response.data);
        }
      } catch (err) {
        console.error("Backend Error:", err);
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  // İstatistik Kartları Verisi
  const statsData = [
    { 
      title: 'Total Cameras', 
      value: cameras.length || 0, // Backend'den gelen gerçek sayı
      icon: Camera, 
      color: 'bg-blue-500', 
      change: '+2 this week' 
    },
    { title: "Today's Detections", value: '1,247', icon: Activity, color: 'bg-green-500', change: '+18% from yesterday' },
    { title: 'Helmet Violations', value: '23', icon: HardHat, color: 'bg-orange-500', change: '-5% from yesterday' },
    { title: 'Vest Violations', value: '17', icon: Shirt, color: 'bg-red-500', change: '-12% from yesterday' },
  ];

  return (
    <div className="space-y-6 p-6">
      
      {/* --- STATS CARDS --- */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {statsData.map((stat, index) => {
          const Icon = stat.icon;
          return (
            <div key={index} className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex justify-between items-start">
              <div>
                <p className="text-gray-500 text-sm font-medium">{stat.title}</p>
                <h3 className="text-2xl font-bold text-gray-900 mt-2 mb-1">{stat.value}</h3>
                <p className="text-gray-500 text-xs">{stat.change}</p>
              </div>
              <div className={`${stat.color} w-12 h-12 rounded-lg flex items-center justify-center shadow-sm`}>
                <Icon className="w-6 h-6 text-white" />
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* --- DETECTION OVERVIEW CHART --- */}
        <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <div className="mb-6">
            <h3 className="text-lg font-bold text-gray-900">Detection Overview</h3>
            <p className="text-gray-500 text-sm">Daily detections and violations this week</p>
          </div>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
                <XAxis dataKey="date" stroke="#6b7280" tickLine={false} axisLine={false} />
                <YAxis stroke="#6b7280" tickLine={false} axisLine={false} />
                <Tooltip 
                  cursor={{fill: '#F3F4F6'}}
                  contentStyle={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderRadius: '8px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' }} 
                />
                <Bar dataKey="detections" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                <Bar dataKey="violations" fill="#ef4444" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* --- SYSTEM STATUS --- */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <div className="mb-6">
            <h3 className="text-lg font-bold text-gray-900">System Status</h3>
            <p className="text-gray-500 text-sm">All services monitoring</p>
          </div>
          <div className="space-y-4">
            {systemStatus.map((service, index) => (
              <div key={index} className="flex items-start justify-between pb-4 border-b border-gray-50 last:border-0 last:pb-0">
                <div className="flex items-start gap-3">
                  {service.status === 'online' ? (
                    <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
                  ) : (
                    <AlertTriangle className="w-5 h-5 text-orange-500 flex-shrink-0 mt-0.5" />
                  )}
                  <div>
                    <p className="text-gray-900 text-sm font-medium">{service.name}</p>
                    <p className="text-gray-500 text-xs">Uptime: {service.uptime}</p>
                  </div>
                </div>
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium border ${
                    service.status === 'online' 
                    ? 'bg-green-50 text-green-700 border-green-100' 
                    : 'bg-orange-50 text-orange-700 border-orange-100'
                }`}>
                  {service.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* --- LIVE CAMERA FEEDS (BACKEND DATA) --- */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <div className="mb-6">
          <h3 className="text-lg font-bold text-gray-900">Live Camera Feeds</h3>
          <p className="text-gray-500 text-sm">Real-time monitoring from active cameras</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {loading ? (
             <p className="text-gray-400 col-span-2 text-center py-10">Loading cameras...</p>
          ) : cameras.length === 0 ? (
             <p className="text-gray-400 col-span-2 text-center py-10">No cameras connected.</p>
          ) : (
             cameras.map((camera) => (
                <div key={camera.id} className="space-y-3 p-4 border border-gray-100 rounded-xl hover:shadow-md transition-shadow">
                  {/* Video/Image Placeholder */}
                  <div className="bg-gray-900 rounded-lg aspect-video flex items-center justify-center relative overflow-hidden group">
                    <div className="absolute inset-0 bg-gradient-to-br from-gray-800 to-gray-900 opacity-50"></div>
                    <Camera className="w-12 h-12 text-gray-600 relative z-10 group-hover:scale-110 transition-transform" />
                    
                    {/* Status Badge */}
                    {camera.status === 'online' ? (
                        <div className="absolute top-3 right-3 bg-green-500/90 text-white px-2 py-1 rounded text-xs font-bold flex items-center backdrop-blur-sm">
                            <div className="w-1.5 h-1.5 bg-white rounded-full mr-1.5 animate-pulse"></div>
                            LIVE
                        </div>
                    ) : (
                        <div className="absolute top-3 right-3 bg-gray-500/90 text-white px-2 py-1 rounded text-xs font-bold backdrop-blur-sm">
                            OFFLINE
                        </div>
                    )}
                  </div>

                  {/* Info */}
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-gray-900 font-semibold">{camera.name}</p>
                      <p className="text-gray-500 text-xs">{camera.location}</p>
                    </div>
                    <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium border ${
                        camera.status === 'online' 
                        ? 'bg-green-50 text-green-700 border-green-100' 
                        : 'bg-red-50 text-red-700 border-red-100'
                    }`}>
                      {camera.status.toUpperCase()}
                    </span>
                  </div>
                </div>
             ))
          )}
        </div>
      </div>
    </div>
  );
}
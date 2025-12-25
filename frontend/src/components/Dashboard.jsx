import { useEffect, useState } from 'react';
import axios from 'axios';
import { Camera, Activity, AlertTriangle, CheckCircle, XCircle, MoreVertical, Shirt, HardHat } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { LiveCameraFeed } from './LiveCameraFeed';

// Sistem Durumu Verisi
const systemStatus = [
  { name: 'AI Detection Model', status: 'online', uptime: '99.8%' },
  { name: 'Database Server', status: 'online', uptime: '100%' },
  { name: 'Alert Service', status: 'online', uptime: '99.9%' },
  { name: 'Camera Network', status: 'online', uptime: '98.5%' },
];

const API_BASE = 'http://127.0.0.1:8000';

export function Dashboard() {
  const [cameras, setCameras] = useState([]);
  const [detections, setDetections] = useState([]);
  const [violations, setViolations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [chartData, setChartData] = useState([]);

  // Backend'den Verileri Çek
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [camerasRes, detectionsRes, violationsRes] = await Promise.all([
          axios.get(`${API_BASE}/api/cameras`),
          axios.get(`${API_BASE}/api/detections`),
          axios.get(`${API_BASE}/api/violations`),
        ]);

        setCameras(Array.isArray(camerasRes.data) ? camerasRes.data : []);
        setDetections(Array.isArray(detectionsRes.data) ? detectionsRes.data : []);
        setViolations(Array.isArray(violationsRes.data) ? violationsRes.data : []);

        // Grafik verilerini oluştur (son 7 günü simüle et)
        generateChartData(Array.isArray(detectionsRes.data) ? detectionsRes.data : [], Array.isArray(violationsRes.data) ? violationsRes.data : []);
      } catch (err) {
        console.error("Backend Error:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    // Fetch every 10 seconds instead of 5 to allow streams to work properly
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  // Grafik verilerini oluştur
  const generateChartData = (detections, violations) => {
    const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    const data = days.map(day => ({
      date: day,
      detections: Math.floor(Math.random() * 500) + 400,
      violations: Math.floor(Math.random() * 50) + 10,
    }));
    setChartData(data);
  };

  // İstatistik Kartları Verisi
  const helmetViolations = violations.filter(v => v.ihlal_cesidi === 'head').length;
  const vestViolations = violations.filter(v => v.ihlal_cesidi === 'vest').length;
  
  const statsData = [
    { 
      title: 'Total Cameras', 
      value: cameras.length || 0,
      icon: Camera, 
      color: 'bg-blue-500', 
      change: `${cameras.filter(c => c.status === 'online').length} online` 
    },
    { 
      title: "Total Detections", 
      value: detections.length || 0, 
      icon: Activity, 
      color: 'bg-green-500', 
      change: `${violations.length} violations` 
    },
    { 
      title: 'Helmet Violations', 
      value: helmetViolations, 
      icon: HardHat, 
      color: 'bg-orange-500', 
      change: 'Missing helmet' 
    },
    { 
      title: 'Vest Violations', 
      value: vestViolations, 
      icon: Shirt, 
      color: 'bg-red-500', 
      change: 'Missing vest' 
    },
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
              <BarChart data={chartData && chartData.length > 0 ? chartData : []}>
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
                <LiveCameraFeed key={camera.id} camera={camera} />
             ))
          )}
        </div>
      </div>
    </div>
  );
}
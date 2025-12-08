import { useEffect, useState } from 'react';
import axios from 'axios';
import { Camera, AlertTriangle, ShieldCheck, Activity } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export const Dashboard = () => {
  const [cameras, setCameras] = useState([]);
  const [loading, setLoading] = useState(true);

  // Grafik için örnek veri (Backend endpoint'i yazılınca burası da dinamik olacak)
  const chartData = [
    { name: 'Mon', detections: 800 },
    { name: 'Tue', detections: 950 },
    { name: 'Wed', detections: 1100 },
    { name: 'Thu', detections: 900 },
    { name: 'Fri', detections: 1250 },
    { name: 'Sat', detections: 600 },
    { name: 'Sun', detections: 400 },
  ];

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Backend'den kameraları çekiyoruz
        const response = await axios.get('http://127.0.0.1:8000/api/cameras');
        if (Array.isArray(response.data)) setCameras(response.data);
      } catch (err) {
        console.error("Backend Error:", err);
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
    const interval = setInterval(fetchData, 5000); // 5 saniyede bir güncelle
    return () => clearInterval(interval);
  }, []);

  const stats = [
    { title: 'Total Cameras', value: cameras.length || 0, sub: '+2 this week', color: 'blue', icon: Camera },
    { title: 'Today\'s Detections', value: '1,247', sub: '+18% from yesterday', color: 'green', icon: Activity },
    { title: 'Helmet Violations', value: '23', sub: '-5% from yesterday', color: 'orange', icon: ShieldCheck },
    { title: 'Vest Violations', value: '17', sub: '-12% from yesterday', color: 'red', icon: AlertTriangle },
  ];

  return (
    <div className="space-y-6">
      {/* İstatistik Kartları */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat, index) => {
          const Icon = stat.icon;
          // Renk sınıfları
          const bgColors = {
            blue: 'bg-blue-50 text-blue-600',
            green: 'bg-green-50 text-green-600',
            orange: 'bg-orange-50 text-orange-600',
            red: 'bg-red-50 text-red-600'
          };
          
          return (
            <div key={index} className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex justify-between items-start">
              <div>
                <p className="text-sm font-medium text-gray-500">{stat.title}</p>
                <h3 className="text-2xl font-bold text-gray-900 mt-2 mb-1">{stat.value}</h3>
                <p className={`text-xs font-medium ${['red', 'orange'].includes(stat.color) ? 'text-red-500' : 'text-green-500'}`}>
                  {stat.sub}
                </p>
              </div>
              <div className={`p-3 rounded-lg ${bgColors[stat.color]}`}>
                <Icon className="w-6 h-6" />
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Grafik */}
        <div className="lg:col-span-2 bg-white p-6 rounded-xl shadow-sm border border-gray-100">
          <h3 className="text-lg font-bold text-gray-800 mb-4">Detection Overview</h3>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#eee" />
                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{fill: '#9CA3AF'}} />
                <YAxis axisLine={false} tickLine={false} tick={{fill: '#9CA3AF'}} />
                <Tooltip 
                  cursor={{fill: '#F3F4F6'}} 
                  contentStyle={{borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'}} 
                />
                <Bar dataKey="detections" fill="#3B82F6" radius={[4, 4, 0, 0]} barSize={40} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Canlı Kameralar Listesi (Backend Verisi) */}
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
          <h3 className="text-lg font-bold text-gray-800 mb-4">Active Cameras</h3>
          <div className="space-y-4">
            {loading ? (
                <p className="text-gray-400 text-center">Loading cameras...</p>
            ) : cameras.length === 0 ? (
              <p className="text-gray-500 text-center py-4">No cameras connected</p>
            ) : (
              cameras.map((cam) => (
                <div key={cam.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-100 hover:bg-gray-100 transition-colors">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-gray-900 rounded flex items-center justify-center text-gray-400">
                      <Camera className="w-5 h-5" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-gray-900">{cam.name}</p>
                      <p className="text-xs text-gray-500">{cam.location}</p>
                    </div>
                  </div>
                  <span className={`px-2 py-1 text-xs font-medium rounded-full ${cam.status === 'online' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                    {cam.status.toUpperCase()}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
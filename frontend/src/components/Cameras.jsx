import { useEffect, useState } from 'react';
import { apiClient } from '../utils/api';
import { Camera, Plus, Settings, Wifi, WifiOff, MoreVertical, RefreshCw } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const Cameras = () => {
  const { isAdmin, activeCompanyCode } = useAuth();
  const [cameras, setCameras] = useState([]);
  const [loading, setLoading] = useState(true);

  // Backend'den veri çekme
  const fetchCameras = async () => {
    try {
      setLoading(true);
      const response = await apiClient.get('/api/cameras');
      // Backend verisi ile UI için gerekli ek alanları birleştiriyoruz
      const processedData = response.data.map(cam => ({
        ...cam,
        lastDetection: '2 dk önce' // Backend'den gelmediği için şimdilik statik
      }));
      setCameras(processedData);
    } catch (error) {
      console.error("Kamera verisi çekilemedi:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCameras();
    // 10 saniyede bir güncelle
    const interval = setInterval(fetchCameras, 10000); 
    return () => clearInterval(interval);
  }, []);

  // Admin control - must select a company before viewing cameras
  if (isAdmin && !activeCompanyCode) {
    return (
      <div className="space-y-6 p-6">
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-8 text-center">
          <p className="text-amber-900 text-lg font-semibold">⚠️ Please select a company from the sidebar.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* --- HEADER --- */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Camera Management</h2>
          <p className="text-gray-500 text-sm mt-1">Monitor and manage all connected cameras</p>
        </div>
        <div className="flex gap-3">
            <button 
                onClick={fetchCameras} 
                className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                title="Yenile"
            >
                <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
            </button>
            <button className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium transition-colors">
            <Plus className="w-4 h-4" />
            Add Camera
            </button>
        </div>
      </div>

      {/* --- YÜKLENİYOR DURUMU --- */}
      {loading && cameras.length === 0 ? (
        <div className="flex justify-center items-center h-64">
           <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      ) : (
        /* --- CAMERA GRID --- */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {cameras.map((camera) => (
            <div key={camera.id} className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden hover:shadow-md transition-shadow">
                
                {/* Kamera Önizleme Alanı */}
                <div className="bg-gray-900 aspect-video flex items-center justify-center relative group overflow-hidden">
                    {/* Canlı Stream Görüntüsü */}
                    {camera.status === 'online' ? (
                        <img 
                            src={`http://127.0.0.1:8000/api/camera/${camera.id}/stream`}
                            alt={`${camera.name} live feed`}
                            className="w-full h-full object-contain"
                            style={{ minHeight: '100%' }}
                            onError={(e) => {
                                console.error(`Stream error for camera ${camera.id}:`, e);
                                // Stream yüklenemezse fallback göster
                                const parent = e.target.parentElement;
                                if (parent) {
                                    e.target.style.display = 'none';
                                    // Show placeholder
                                    if (!parent.querySelector('.stream-placeholder')) {
                                        const placeholder = document.createElement('div');
                                        placeholder.className = 'stream-placeholder absolute inset-0 flex items-center justify-center';
                                        placeholder.innerHTML = '<div class="text-white text-sm">Stream yükleniyor...</div>';
                                        parent.appendChild(placeholder);
                                    }
                                }
                            }}
                            onLoad={(e) => {
                                // Stream başarıyla yüklendi
                                const parent = e.target.parentElement;
                                if (parent) {
                                    const placeholder = parent.querySelector('.stream-placeholder');
                                    if (placeholder) {
                                        placeholder.remove();
                                    }
                                }
                            }}
                        />
                    ) : (
                        <>
                            {/* Gradient Overlay */}
                            <div className="absolute inset-0 bg-gradient-to-br from-gray-800 to-gray-900 opacity-50"></div>
                            
                            {/* Kamera İkonu */}
                            <Camera className="w-12 h-12 text-gray-600 relative z-10 group-hover:scale-110 transition-transform duration-300" />
                        </>
                    )}
                    
                    {/* Canlı/Offline Badge */}
                    {camera.status === 'online' ? (
                        <div className="absolute top-3 left-3 bg-green-500/90 text-white px-2 py-1 rounded text-xs font-bold flex items-center backdrop-blur-sm z-20">
                        <div className="w-1.5 h-1.5 bg-white rounded-full mr-1.5 animate-pulse"></div>
                        LIVE
                        </div>
                    ) : (
                        <div className="absolute top-3 left-3 bg-gray-500/90 text-white px-2 py-1 rounded text-xs font-bold backdrop-blur-sm z-20">
                        OFFLINE
                        </div>
                    )}

                    {/* Menü Butonu */}
                    <button className="absolute top-2 right-2 p-1.5 bg-black/20 hover:bg-black/40 text-white rounded-full transition-colors opacity-0 group-hover:opacity-100 z-20">
                        <MoreVertical className="w-4 h-4" />
                    </button>
                </div>

                {/* Alt Bilgi Alanı */}
                <div className="p-4">
                    <div className="space-y-3">
                        <div>
                            <h3 className="text-gray-900 font-semibold truncate" title={camera.name}>{camera.name}</h3>
                            <p className="text-gray-500 text-xs truncate">{camera.location}</p>
                        </div>

                        <div className="flex items-center justify-between pt-3 border-t border-gray-100">
                            <div className="flex items-center gap-2">
                                {camera.status === 'online' ? (
                                    <Wifi className="w-4 h-4 text-green-500" />
                                ) : (
                                    <WifiOff className="w-4 h-4 text-gray-400" />
                                )}
                                <span className={`text-xs font-medium ${camera.status === 'online' ? 'text-green-600' : 'text-gray-400'}`}>
                                    {camera.status.toUpperCase()}
                                </span>
                            </div>
                            <span className="text-gray-400 text-xs">{camera.lastDetection}</span>
                        </div>

                        <button className="w-full flex items-center justify-center gap-2 border border-gray-200 hover:bg-gray-50 text-gray-700 py-2 rounded-lg text-sm font-medium transition-colors">
                            <Settings className="w-4 h-4" />
                            Settings
                        </button>
                    </div>
                </div>
            </div>
            ))}
        </div>
      )}

      {/* Eğer hiç kamera yoksa */}
      {!loading && cameras.length === 0 && (
          <div className="text-center py-12 bg-gray-50 rounded-lg border border-dashed border-gray-300">
              <Camera className="w-12 h-12 text-gray-400 mx-auto mb-3" />
              <h3 className="text-gray-900 font-medium">No cameras found</h3>
              <p className="text-gray-500 text-sm">Start by adding a new camera to the system.</p>
          </div>
      )}
    </div>
  );
}
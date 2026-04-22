import { useEffect, useRef, useState, memo } from 'react';
import { Camera, PlayCircle, StopCircle } from 'lucide-react';
import { API_URL } from '../utils/api';

function LiveCameraFeedComponent({ camera }) {
  const imgRef = useRef(null);
  const streamUrlRef = useRef(null);
  const currentCameraIdRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const streamUrl = `${API_URL}/api/camera/${camera.id}/stream`;
    const cameraIdChanged = currentCameraIdRef.current !== camera.id;
    
    // Update refs
    currentCameraIdRef.current = camera.id;
    streamUrlRef.current = streamUrl;

    if (!imgRef.current) return;

    if (!isPlaying) {
      // Stop stream when isPlaying is false
      if (imgRef.current.src) {
        imgRef.current.src = '';
      }
      return;
    }

    // Don't restart stream if camera ID hasn't changed and already streaming with same URL
    if (!cameraIdChanged && imgRef.current.src === streamUrl && imgRef.current.src !== '') {
      return;
    }

    // Start or restart stream
    setIsLoading(true);
    setError(null);

    const handleImageLoad = () => {
      console.log(`[Camera ${camera.id}] Stream loaded successfully`);
      setIsLoading(false);
    };

    const handleImageError = () => {
      console.error(`[Camera ${camera.id}] Stream error`);
      setError('Failed to load stream');
      setIsLoading(false);
    };

    // Set the MJPEG stream URL directly to img tag
    imgRef.current.src = streamUrl;
    imgRef.current.addEventListener('load', handleImageLoad);
    imgRef.current.addEventListener('error', handleImageError);

    return () => {
      if (imgRef.current) {
        imgRef.current.removeEventListener('load', handleImageLoad);
        imgRef.current.removeEventListener('error', handleImageError);
      }
    };
  }, [isPlaying, camera.id]);

  const toggleStream = (e) => {
    e.preventDefault();
    setIsPlaying(!isPlaying);
  };

  return (
    <div className="space-y-3 p-4 border border-gray-100 rounded-xl hover:shadow-md transition-shadow">
      {/* Video Stream */}
      <div className="bg-gray-900 rounded-lg aspect-video flex items-center justify-center relative overflow-hidden group">
        {isLoading && (
          <div className="absolute inset-0 bg-gray-800 flex items-center justify-center z-20">
            <div className="animate-spin">
              <Camera className="w-8 h-8 text-gray-500" />
            </div>
          </div>
        )}

        <img
          ref={imgRef}
          className={`w-full h-full object-cover ${isPlaying ? '' : 'hidden'}`}
          alt={camera.name}
        />
        {!isPlaying && (
          <div className="absolute inset-0 bg-gradient-to-br from-gray-800 to-gray-900 opacity-50"></div>
        )}

        {!isPlaying && (
          <Camera className="w-12 h-12 text-gray-600 relative z-10 group-hover:scale-110 transition-transform" />
        )}

        {/* Status Badge */}
        <div className="absolute top-3 right-3 z-10">
          {camera.status === 'online' ? (
            <div className="bg-green-500/90 text-white px-2 py-1 rounded text-xs font-bold flex items-center backdrop-blur-sm">
              <div className="w-1.5 h-1.5 bg-white rounded-full mr-1.5 animate-pulse"></div>
              {isPlaying ? 'LIVE' : 'READY'}
            </div>
          ) : (
            <div className="bg-gray-500/90 text-white px-2 py-1 rounded text-xs font-bold backdrop-blur-sm">
              OFFLINE
            </div>
          )}
        </div>

        {/* Play/Stop Button */}
        <button
          type="button"
          onClick={toggleStream}
          disabled={camera.status !== 'online'}
          className="absolute bottom-3 right-3 z-10 bg-blue-500/90 hover:bg-blue-600/90 disabled:bg-gray-500/90 text-white p-2 rounded-lg transition-all backdrop-blur-sm"
        >
          {isPlaying ? (
            <StopCircle className="w-5 h-5" />
          ) : (
            <PlayCircle className="w-5 h-5" />
          )}
        </button>
      </div>

      {/* Info */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-gray-900 font-semibold">{camera.name}</p>
          <p className="text-gray-500 text-xs">{camera.location}</p>
        </div>
        <span
          className={`px-2.5 py-0.5 rounded-full text-xs font-medium border ${
            camera.status === 'online'
              ? 'bg-green-50 text-green-700 border-green-100'
              : 'bg-red-50 text-red-700 border-red-100'
          }`}
        >
          {camera.status.toUpperCase()}
        </span>
      </div>
    </div>
  );
}

// Memoize component to prevent re-renders from Dashboard updates
// Only re-render if camera.id, status, name, or location actually changes
export const LiveCameraFeed = memo(LiveCameraFeedComponent, (prevProps, nextProps) => {
  // Return true if props are equal (skip re-render), false if different (re-render)
  return (
    prevProps.camera.id === nextProps.camera.id &&
    prevProps.camera.status === nextProps.camera.status &&
    prevProps.camera.name === nextProps.camera.name &&
    prevProps.camera.location === nextProps.camera.location
  );
});

import { useState, useRef, useEffect } from 'react';
import { Bell, Menu, User, LogOut, AlertTriangle, HardHat, ShieldAlert, X, CheckCheck } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const VIOLATION_CONFIG = {
  head:   { label: 'No Helmet',   color: 'bg-red-100 text-red-600',    icon: HardHat },
  vest:   { label: 'No Vest',     color: 'bg-orange-100 text-orange-600', icon: ShieldAlert },
  fall:   { label: 'Worker Fell', color: 'bg-purple-100 text-purple-600', icon: AlertTriangle },
  fallen: { label: 'Worker Fell', color: 'bg-purple-100 text-purple-600', icon: AlertTriangle },
};

function timeAgo(date) {
  const secs = Math.floor((new Date() - new Date(date)) / 1000);
  if (secs < 60) return `${secs}s ago`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  return `${Math.floor(secs / 3600)}h ago`;
}

export const TopNav = ({ toggleSidebar, notifications = [], onDismiss }) => {
  const { logout, user } = useAuth();
  const [showDropdown, setShowDropdown] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const notifRef = useRef(null);
  const userRef = useRef(null);

  // Dışarı tıklanınca panelleri kapat
  useEffect(() => {
    const handler = (e) => {
      if (notifRef.current && !notifRef.current.contains(e.target)) {
        setShowNotifications(false);
      }
      if (userRef.current && !userRef.current.contains(e.target)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleLogout = () => {
    setShowDropdown(false);
    logout();
  };

  const unreadCount = notifications.length;

  return (
    <header className="bg-white border-b border-gray-200 flex flex-col sticky top-0 z-30">
      <div className="h-16 flex items-center justify-between px-6">
        <div className="flex items-center gap-4">
          <button onClick={toggleSidebar} className="lg:hidden p-1 hover:bg-gray-100 rounded-md">
            <Menu className="w-6 h-6 text-gray-600" />
          </button>
          <div>
            <h1 className="text-lg font-semibold text-gray-800">Workplace Safety Monitoring</h1>
            <p className="text-xs text-gray-500 hidden sm:block">Real-time detection system</p>
          </div>
        </div>

        <div className="flex items-center gap-4">

          {/* Bildirim Çanı */}
          <div className="relative" ref={notifRef}>
            <button
              onClick={() => setShowNotifications(!showNotifications)}
              className="relative p-2 hover:bg-gray-100 rounded-full"
            >
              <Bell className={`w-5 h-5 ${unreadCount > 0 ? 'text-red-500' : 'text-gray-600'}`} />
              {unreadCount > 0 && (
                <span
                  style={{ fontSize: 10 }}
                  className="absolute -top-0.5 -right-0.5 w-5 h-5 bg-red-500 text-white font-bold rounded-full flex items-center justify-center border-2 border-white"
                >
                  {unreadCount > 9 ? '9+' : unreadCount}
                </span>
              )}
            </button>

            {showNotifications && (
              <div className="absolute right-0 top-full mt-2 w-80 bg-white border border-gray-200 rounded-xl shadow-xl z-50 overflow-hidden">
                {/* Header */}
                <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
                  <span className="text-sm font-semibold text-gray-800">Violations</span>
                  {unreadCount > 0 && (
                    <button
                      onClick={() => notifications.forEach(n => onDismiss(n.id))}
                      className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600"
                    >
                      <CheckCheck className="w-3.5 h-3.5" />
                      Clear all
                    </button>
                  )}
                </div>

                {/* Liste */}
                <div className="max-h-80 overflow-y-auto">
                  {notifications.length === 0 ? (
                    <div className="px-4 py-8 text-center text-sm text-gray-400">
                      No new violations
                    </div>
                  ) : (
                    notifications.map((n) => {
                      const cfg = VIOLATION_CONFIG[n.violation_type] || {
                        label: n.violation_type,
                        color: 'bg-gray-100 text-gray-600',
                        icon: AlertTriangle,
                      };
                      const Icon = cfg.icon;
                      return (
                        <div key={n.id} className="flex items-start gap-3 px-4 py-3 hover:bg-gray-50 border-b border-gray-50 last:border-0">
                          <div className={`${cfg.color} rounded-lg p-1.5 shrink-0 mt-0.5`}>
                            <Icon className="w-4 h-4" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-gray-800">{cfg.label}</p>
                            <p className="text-xs text-gray-500 truncate">
                              Camera: {n.camera_location || n.camera_id}
                            </p>
                            <p className="text-xs text-gray-400 mt-0.5">{timeAgo(n.receivedAt)}</p>
                          </div>
                          <button
                            onClick={() => onDismiss(n.id)}
                            className="shrink-0 text-gray-300 hover:text-gray-500 mt-0.5"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Kullanıcı Menüsü */}
          <div className="flex items-center gap-3 pl-4 border-l border-gray-200 relative" ref={userRef}>
            <div className="text-right hidden sm:block">
              <p className="text-sm font-medium text-gray-700">{user?.email?.split('@')[0] || 'User'}</p>
              <p className="text-xs text-gray-500 capitalize">{user?.role === 'admin' ? '👨‍💼 Admin' : '👤 User'}</p>
            </div>
            <button
              onClick={() => setShowDropdown(!showDropdown)}
              className="w-9 h-9 bg-blue-100 rounded-full flex items-center justify-center text-blue-600 hover:bg-blue-200 transition-colors cursor-pointer"
            >
              <User className="w-5 h-5" />
            </button>

            {showDropdown && (
              <div className="absolute right-0 top-full mt-2 w-48 bg-white border border-gray-200 rounded-lg shadow-lg z-50">
                <div className="px-4 py-3 border-b border-gray-100">
                  <p className="text-xs font-semibold text-gray-500">Account</p>
                  <p className="text-sm font-medium text-gray-900 truncate mt-1">{user?.email}</p>
                </div>
                <button
                  onClick={handleLogout}
                  className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-red-600 hover:bg-red-50 transition-colors"
                >
                  <LogOut className="w-4 h-4" />
                  <span>Logout</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};

import { useState } from 'react';
import { Bell, Menu, User, LogOut } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const TopNav = ({ toggleSidebar }) => {
  const { logout, user } = useAuth();
  const [showDropdown, setShowDropdown] = useState(false);

  const handleLogout = () => {
    setShowDropdown(false);
    logout();
  };

  return (
    <header className="bg-white border-b border-gray-200 h-16 flex items-center justify-between px-6 sticky top-0 z-10">
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
        <button className="relative p-2 hover:bg-gray-100 rounded-full">
          <Bell className="w-5 h-5 text-gray-600" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full border-2 border-white"></span>
        </button>
        
        <div className="flex items-center gap-3 pl-4 border-l border-gray-200 relative">
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

          {/* Dropdown Menu */}
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
    </header>
  );
};
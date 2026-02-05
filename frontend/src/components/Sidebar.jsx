import { LayoutDashboard, Camera, BrainCircuit, AlertTriangle, FileText, Settings, X, LogOut } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import CompanySelector from './CompanySelector';

export const Sidebar = ({ activePage, setActivePage, isOpen, setIsOpen }) => {
  const { logout, user, isAdmin, activeCompanyCode } = useAuth();

  const menuItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, adminOnly: false },
    { id: 'cameras', label: 'Cameras', icon: Camera, adminOnly: false },
    { id: 'models', label: 'Models', icon: BrainCircuit, adminOnly: true },
    { id: 'model', label: 'Model Management', icon: BrainCircuit, adminOnly: true },
    { id: 'violations', label: 'Violations', icon: AlertTriangle, adminOnly: false },
    { id: 'reporting', label: 'Reporting', icon: FileText, adminOnly: false },
    { id: 'settings', label: 'Settings', icon: Settings, adminOnly: false },
  ];

  // Filter menu items based on admin role
  const visibleItems = menuItems.filter(item => !item.adminOnly || isAdmin);

  const handleLogout = () => {
    logout();
  };

  return (
    <>
      {/* Mobilde arka plan karartma */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-20 lg:hidden" 
          onClick={() => setIsOpen(false)} 
        />
      )}

      <div className={`fixed inset-y-0 left-0 z-30 w-64 bg-white border-r border-gray-200 transform transition-transform duration-200 ease-in-out lg:translate-x-0 lg:static lg:inset-0 flex flex-col ${isOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="flex items-center justify-between h-16 px-6 border-b border-gray-100">
          <div className="flex items-center gap-2 font-bold text-xl text-blue-600">
            <Camera className="w-6 h-6" />
            <span>SafetyWatch</span>
          </div>
          <button onClick={() => setIsOpen(false)} className="lg:hidden">
            <X className="w-6 h-6 text-gray-500" />
          </button>
        </div>

        <nav className="p-4 space-y-1 flex-1 overflow-y-auto">
          {visibleItems.map((item) => {
            const Icon = item.icon;
            const isActive = activePage === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  setActivePage(item.id);
                  if (window.innerWidth < 1024) setIsOpen(false);
                }}
                className={`flex items-center w-full gap-3 px-4 py-3 text-sm font-medium rounded-lg transition-colors ${
                  isActive 
                    ? 'bg-blue-50 text-blue-600' 
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`}
              >
                <Icon className="w-5 h-5" />
                {item.label}
              </button>
            );
          })}
        </nav>

        {/* User info and logout */}
        <div className="border-t border-gray-200 p-4">
          {/* Company info for admins */}
          {isAdmin && (
            <div className="mb-4">
              <CompanySelector onCompanySelect={() => setActivePage('dashboard')} />
            </div>
          )}

          {/* Company display for users */}
          {!isAdmin && activeCompanyCode && (
            <div className="mb-3 px-4 py-2 bg-blue-50 rounded-lg border border-blue-200">
              <p className="text-xs font-semibold text-gray-600">Company</p>
              <p className="text-sm font-medium text-blue-900 truncate">{activeCompanyCode}</p>
            </div>
          )}

          <div className="mb-3 px-4 py-2 bg-gray-50 rounded-lg">
            <p className="text-xs font-semibold text-gray-600">Logged in as</p>
            <p className="text-sm font-medium text-gray-900 truncate">{user?.email}</p>
            <p className="text-xs text-gray-500 mt-1 capitalize">
              {user?.role === 'admin' ? '👨‍💼 Administrator' : '👤 User'}
            </p>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center w-full gap-3 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 rounded-lg transition-colors"
          >
            <LogOut className="w-5 h-5" />
            Logout
          </button>
        </div>
      </div>
    </>
  );
};
import { LayoutDashboard, Camera, BrainCircuit, AlertTriangle, FileText, Settings, X } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import CompanySelector from './CompanySelector';

export const Sidebar = ({ activePage, setActivePage, isOpen, setIsOpen }) => {
  const { isAdmin, activeCompanyCode } = useAuth();

  const generalItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'model-camera-assignment', label: 'Model Camera Assignment', icon: BrainCircuit, companyDependent: true },
    { id: 'cameras', label: 'Cameras', icon: Camera, companyDependent: true },
    { id: 'violations', label: 'Violations', icon: AlertTriangle, companyDependent: true },
    { id: 'reporting', label: 'Reporting', icon: FileText, companyDependent: true },
    ...(!isAdmin ? [{ id: 'settings', label: 'Settings', icon: Settings }] : []),
  ];

  const adminItems = [
    { id: 'models', label: 'General Model Management', icon: BrainCircuit },
    { id: 'companies', label: 'Companies', icon: FileText },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

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
          <div className="flex items-center gap-2 font-bold text-xl text-primary-600">
            <Camera className="w-6 h-6" />
            <span>SafetyWatch</span>
          </div>
          <button onClick={() => setIsOpen(false)} className="lg:hidden">
            <X className="w-6 h-6 text-gray-500" />
          </button>
        </div>

        <nav className="p-4 space-y-1 flex-1 overflow-y-auto">
          {generalItems
            .filter(item => !item.companyDependent || !isAdmin || activeCompanyCode)
            .map((item) => {
              const Icon = item.icon;
              const isActive = activePage === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => {
                    setActivePage(item.id);
                    if (window.innerWidth < 1024) setIsOpen(false);
                  }}
                  className={`flex items-center w-full gap-3 px-4 py-3 text-sm font-medium rounded-lg transition-colors text-left ${
                    isActive 
                      ? 'bg-primary-50 text-primary-600'
                      : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                  }`}
                >
                  <Icon className="w-5 h-5 shrink-0" />
                  {item.label}
                </button>
              );
            })}

          {isAdmin && (
            <div className="pt-4">
              <p className="px-4 text-xs font-semibold text-gray-400 uppercase tracking-wider">Admin Management</p>
              <div className="mt-2 space-y-1">
                {adminItems.map((item) => {
                  const Icon = item.icon;
                  const isActive = activePage === item.id;
                  return (
                    <button
                      key={item.id}
                      onClick={() => {
                        setActivePage(item.id);
                        if (window.innerWidth < 1024) setIsOpen(false);
                      }}
                      className={`flex items-center w-full gap-3 px-4 py-3 text-sm font-medium rounded-lg transition-colors text-left ${
                        isActive 
                          ? 'bg-primary-50 text-primary-600'
                          : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                      }`}
                    >
                      <Icon className="w-5 h-5 shrink-0" />
                      {item.label}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </nav>

        {/* Bottom: company selector / company display */}
        <div className="border-t border-gray-200 p-4">
          {isAdmin && (
            <CompanySelector onCompanySelect={() => setActivePage('dashboard')} />
          )}
          {!isAdmin && activeCompanyCode && (
            <div className="px-4 py-2 bg-primary-50 rounded-lg border border-primary-200">
              <p className="text-xs font-semibold text-gray-600">Company</p>
              <p className="text-sm font-medium text-primary-900 truncate">{activeCompanyCode}</p>
            </div>
          )}
        </div>
      </div>
    </>
  );
};
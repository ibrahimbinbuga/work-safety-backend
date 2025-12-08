import { Bell, Menu, User } from 'lucide-react';

export const TopNav = ({ toggleSidebar }) => {
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
        
        <div className="flex items-center gap-3 pl-4 border-l border-gray-200">
          <div className="text-right hidden sm:block">
            <p className="text-sm font-medium text-gray-700">Admin User</p>
            <p className="text-xs text-gray-500">admin@safetywatch.com</p>
          </div>
          <div className="w-9 h-9 bg-blue-100 rounded-full flex items-center justify-center text-blue-600">
            <User className="w-5 h-5" />
          </div>
        </div>
      </div>
    </header>
  );
};
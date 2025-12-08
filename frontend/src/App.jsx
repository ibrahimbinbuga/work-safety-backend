import { useState } from 'react';
import { Dashboard } from './components/Dashboard';
import { Sidebar } from './components/Sidebar';
import { TopNav } from './components/TopNav';

// Diğer bileşenler henüz boşsa hata vermemesi için basitçe import edelim
// Eğer yukarıdaki 4. adımı yaptıysan bu importları açabilirsin:
import { Cameras } from './components/Cameras';
import { ModelManagement } from './components/ModelManagement'; 
import { Violations } from './components/Violations';
import { Reporting } from './components/Reporting';
import { Settings } from './components/Settings';

export default function App() {
  const [activePage, setActivePage] = useState('dashboard');
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  const renderPage = () => {
    switch (activePage) {
      case 'dashboard': return <Dashboard />;
      case 'cameras': return <Cameras />;
      case 'model': return <ModelManagement />;
      case 'violations': return <Violations />;
      case 'reporting': return <Reporting />;
      case 'settings': return <Settings />;
      default: return <Dashboard />;
    }
  };

  return (
    <div className="flex h-screen bg-gray-50 font-sans">
      <Sidebar 
        activePage={activePage} 
        setActivePage={setActivePage}
        isOpen={isSidebarOpen}
        setIsOpen={setIsSidebarOpen}
      />
      
      <div className="flex-1 flex flex-col overflow-hidden">
        <TopNav toggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)} />
        
        <main className="flex-1 overflow-y-auto p-4 lg:p-6">
          {renderPage()}
        </main>
      </div>
    </div>
  );
}
import { useState, useEffect } from 'react';
import { Dashboard } from './components/Dashboard';
import { Sidebar } from './components/Sidebar';
import { TopNav } from './components/TopNav';
import LoginPage from './components/LoginPage';
import { AuthProvider, useAuth } from './context/AuthContext';

// Diğer bileşenler henüz boşsa hata vermemesi için basitçe import edelim
// Eğer yukarıdaki 4. adımı yaptıysan bu importları açabilirsin:
import { Cameras } from './components/Cameras';
import { Models } from './components/Models';
import { ModelManagement } from './components/ModelManagement'; 
import { Violations } from './components/Violations';
import { Reporting } from './components/Reporting';
import { Settings } from './components/Settings';

function AppContent() {
  const { isAuthenticated, user, isAdmin, activeCompanyCode } = useAuth();
  const [activePage, setActivePage] = useState('dashboard');
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  if (!isAuthenticated) {
    return <LoginPage onLoginSuccess={() => setActivePage('dashboard')} />;
  }

  // Pages that require a company to be selected
  const companyDependentPages = ['cameras', 'violations', 'reporting'];

  // Check if current page requires company selection
  const pageRequiresCompany = companyDependentPages.includes(activePage);
  const noCompanySelected = isAdmin && !activeCompanyCode;

  // If admin hasn't selected a company and tries to access company-dependent page, block it
  if (pageRequiresCompany && noCompanySelected) {
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
            <div className="space-y-6 p-6">
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-8 text-center">
          <p className="text-amber-900 text-lg font-semibold">⚠️ Please select a company from the sidebar.</p>
        </div>
      </div>
          </main>
        </div>
      </div>
    );
  }

  const renderPage = () => {
    switch (activePage) {
      case 'dashboard': return <Dashboard />;
      case 'cameras': return <Cameras />;
      case 'models': return user?.role === 'admin' ? <Models /> : <Dashboard />;
      case 'model': return user?.role === 'admin' ? <ModelManagement /> : <Dashboard />;
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

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
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
import { Companies } from './components/Companies';
import { ModelCameraAssignment } from './components/ModelCameraAssignment';
import { Violations } from './components/Violations';
import { Reporting } from './components/Reporting';
import { Settings } from './components/Settings';

function AppContent() {
  const { isAuthenticated, user, isAdmin, activeCompanyCode, loading } = useAuth();
  const [activePage, setActivePage] = useState('dashboard');
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="mx-auto h-10 w-10 animate-spin rounded-full border-b-2 border-blue-600"></div>
          <p className="mt-4 text-sm text-gray-500">Restoring session...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage onLoginSuccess={() => setActivePage('dashboard')} />;
  }

  // Pages that require a company to be selected
  const companyDependentPages = ['cameras', 'violations', 'reporting', 'model-camera-assignment'];

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
      case 'companies': return user?.role === 'admin' ? <Companies /> : <Dashboard />;
      case 'model-camera-assignment': return <ModelCameraAssignment />;
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
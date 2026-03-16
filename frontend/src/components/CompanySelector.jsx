// frontend/src/components/CompanySelector.jsx
import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { getCompanies, selectAdminCompanyContext } from '../utils/api';
import './CompanySelector.css';

export default function CompanySelector({ onCompanySelect }) {
  const { isAdmin, activeCompanyCode, setActiveCompanyCode, companyCode } = useAuth();
  const [companies, setCompanies] = useState([]);
  const [selectedCompanyCode, setSelectedCompanyCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [error, setError] = useState(null);

  // Fetch companies when component mounts (only for admins)
  useEffect(() => {
    if (isAdmin) {
      fetchCompanies();
    }
  }, [isAdmin]);

  const fetchCompanies = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getCompanies();
      // Filter out system admin companies (ADMIN, SUPERADMIN, SYSTEM)
      const filteredCompanies = data.filter(
        company => !['ADMIN', 'SUPERADMIN', 'SYSTEM'].includes(company.code)
      );
      setCompanies(filteredCompanies);
    } catch (err) {
      setError('Failed to load companies');
      console.error('Error fetching companies:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCompanyChange = (e) => {
    setSelectedCompanyCode(e.target.value);
  };

  const handleSelectCompany = async () => {
    if (!selectedCompanyCode) {
      return;
    }

    setSwitching(true);
    setError(null);
    try {
      // Ensure backend starts camera/detection pipeline for selected company.
      await selectAdminCompanyContext(selectedCompanyCode);

      // Keep the brief switching effect for better UX.
      setTimeout(() => {
        setActiveCompanyCode(selectedCompanyCode);
        if (onCompanySelect) {
          onCompanySelect();
        }
        setSwitching(false);
      }, 500);
    } catch (err) {
      setError(err.message || 'Failed to switch company');
      setSwitching(false);
    }
  };

  // Admin view
  if (isAdmin) {
    return (
      <div className="company-selector">
        <div className="selector-content">
          <label htmlFor="company-select">Select Company:</label>
          <div className="selector-group">
            <select
              id="company-select"
              value={selectedCompanyCode}
              onChange={handleCompanyChange}
              disabled={loading}
              className="company-select"
            >
              <option value="">-- Choose a Company --</option>
              {companies.map((company) => (
                <option key={company.id} value={company.code}>
                  {company.name} ({company.code})
                </option>
              ))}
            </select>
            <button
              onClick={handleSelectCompany}
              disabled={!selectedCompanyCode || loading || switching}
              className="select-button"
            >
              {switching ? (
                <span className="flex items-center justify-center">
                  <svg className="animate-spin h-4 w-4 mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Switching...
                </span>
              ) : (
                'Select'
              )}
            </button>
          </div>
          {loading && <span className="loading-spinner">Loading...</span>}
          {error && <span className="error-text">{error}</span>}
        </div>
        
        {activeCompanyCode && (
          <div className="current-company">
            <span>Selected Company:</span> <strong>{activeCompanyCode}</strong>
          </div>
        )}
      </div>
    );
  }

  // User view
  if (companyCode) {
    return (
      <div className="company-selector">
        <div className="user-company-display">
          <strong>{companyCode}</strong>
        </div>
      </div>
    );
  }

  return null;
}

// frontend/src/context/AuthContext.jsx
import React, { createContext, useContext, useState, useEffect } from 'react';
import { logout as apiLogout } from '../utils/api';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [companyCode, setCompanyCode] = useState(null);
  const [activeCompanyCode, setActiveCompanyCode] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Initialize auth state from localStorage
  useEffect(() => {
    const storedToken = localStorage.getItem('accessToken');
    const storedUser = localStorage.getItem('user');
    const storedCompanyCode = localStorage.getItem('companyCode');
    
    if (storedToken && storedUser) {
      setToken(storedToken);
      try {
        const parsedUser = JSON.parse(storedUser);
        setUser(parsedUser);
        
        // Restore companyCode
        if (storedCompanyCode) {
          setCompanyCode(storedCompanyCode);
        }
        
        // For regular users, also restore activeCompanyCode
        if (parsedUser.role === 'user' && storedCompanyCode) {
          setActiveCompanyCode(storedCompanyCode);
        }
      } catch (e) {
        console.error('Failed to parse stored user:', e);
        localStorage.removeItem('user');
      }
    }
    setLoading(false);
  }, []);

  const login = async (email, password, companyCode) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email,
          password,
          company_code: companyCode,
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Login failed');
      }

      const data = await response.json();

      // Store token and user info
      localStorage.setItem('accessToken', data.access_token);
      localStorage.setItem('user', JSON.stringify({
        id: data.user_id,
        email: data.email,
        role: data.role,
      }));
      localStorage.setItem('companyCode', data.company_code);

      setToken(data.access_token);
      setUser({
        id: data.user_id,
        email: data.email,
        role: data.role,
      });
      setCompanyCode(data.company_code);
      
      // For regular users, set activeCompanyCode immediately to their company
      // For admins, activeCompanyCode will be set when they select a company
      if (data.role === 'user') {
        setActiveCompanyCode(data.company_code);
      }

      return true;
    } catch (err) {
      setError(err.message);
      console.error('Login error:', err);
      return false;
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    try {
      // Call backend logout endpoint
      await apiLogout();
    } catch (err) {
      console.error('Logout error:', err);
      // Continue with local logout even if API call fails
    } finally {
      // Always clear local state
      setToken(null);
      setUser(null);
      setCompanyCode(null);
      setActiveCompanyCode(null);
      setError(null);
      localStorage.removeItem('accessToken');
      localStorage.removeItem('user');
      localStorage.removeItem('companyCode');
    }
  };

  const isAuthenticated = !!token;
  const isAdmin = user?.role === 'admin';

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        companyCode,
        activeCompanyCode,
        setActiveCompanyCode,
        loading,
        error,
        login,
        logout,
        isAuthenticated,
        isAdmin,
        setError,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

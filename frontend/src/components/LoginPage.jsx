// frontend/src/components/LoginPage.jsx
import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import './LoginPage.css';

export default function LoginPage({ onLoginSuccess }) {
  const { login, loading, error } = useAuth();
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    companyCode: '',
  });
  const [localError, setLocalError] = useState('');

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value,
    }));
    setLocalError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLocalError('');

    // Validation
    if (!formData.email || !formData.password || !formData.companyCode) {
      setLocalError('All fields are required');
      return;
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      setLocalError('Please enter a valid email address');
      return;
    }

    if (formData.password.length < 1) {
      setLocalError('Please enter your password');
      return;
    }

    const success = await login(
      formData.email,
      formData.password,
      formData.companyCode
    );

    if (success) {
      onLoginSuccess();
    } else {
      setLocalError(error || 'Login failed. Please check your credentials.');
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <h1>🔒 SafetyWatch</h1>
          <p>Workplace Safety Monitoring System</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="companyCode">Company Code</label>
            <input
              type="text"
              id="companyCode"
              name="companyCode"
              placeholder="Enter your company code"
              value={formData.companyCode}
              onChange={handleChange}
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              type="email"
              id="email"
              name="email"
              placeholder="Enter your email"
              value={formData.email}
              onChange={handleChange}
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              type="password"
              id="password"
              name="password"
              placeholder="Enter your password"
              value={formData.password}
              onChange={handleChange}
              disabled={loading}
            />
          </div>

          {(localError || error) && (
            <div className="error-message">
              ⚠️ {localError || error}
            </div>
          )}

          <button
            type="submit"
            className="login-button"
            disabled={loading}
          >
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>

        <div className="login-footer">
          <p className="test-credentials">
            <strong>Demo Credentials:</strong>
            <br />
            Company: <code>COMPANY001</code>
            <br />
            Email: <code>admin@company.com</code>
            <br />
            Password: <code>admin123</code>
          </p>
        </div>
      </div>
    </div>
  );
}

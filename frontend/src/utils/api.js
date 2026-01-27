// frontend/src/utils/api.js
/**
 * API utility module for authenticated requests
 * Automatically includes JWT token in Authorization header
 */

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Get the current auth token from localStorage
 */
export const getAuthToken = () => {
  return localStorage.getItem('accessToken');
};

/**
 * Make an authenticated API request
 */
export const apiCall = async (endpoint, options = {}) => {
  const token = getAuthToken();
  
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  // Add Authorization header if token exists
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers,
  });

  // Handle 401 Unauthorized - clear token and redirect to login
  if (response.status === 401) {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('user');
    window.location.href = '/';
    throw new Error('Session expired. Please login again.');
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `HTTP Error: ${response.status}`);
  }

  return response.json();
};

/**
 * Helper for GET requests
 */
export const get = (endpoint, options = {}) => {
  return apiCall(endpoint, { ...options, method: 'GET' });
};

/**
 * Helper for POST requests
 */
export const post = (endpoint, data, options = {}) => {
  return apiCall(endpoint, {
    ...options,
    method: 'POST',
    body: JSON.stringify(data),
  });
};

/**
 * Helper for PUT requests
 */
export const put = (endpoint, data, options = {}) => {
  return apiCall(endpoint, {
    ...options,
    method: 'PUT',
    body: JSON.stringify(data),
  });
};

/**
 * Helper for DELETE requests
 */
export const del = (endpoint, options = {}) => {
  return apiCall(endpoint, { ...options, method: 'DELETE' });
};

/**
 * Helper for multipart form data (file uploads)
 */
export const uploadFile = async (endpoint, formData, options = {}) => {
  const token = getAuthToken();

  const headers = {
    ...options.headers,
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  // Don't set Content-Type for FormData - browser will set it with boundary
  
  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    method: 'POST',
    headers,
    body: formData,
  });

  if (response.status === 401) {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('user');
    window.location.href = '/';
    throw new Error('Session expired. Please login again.');
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `HTTP Error: ${response.status}`);
  }

  return response.json();
};

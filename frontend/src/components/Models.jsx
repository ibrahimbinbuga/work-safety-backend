import { useState, useRef, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { API_URL } from '../utils/api';

export function Models() {
  const { isAdmin, token } = useAuth();

  // Model yükleme state'leri
  const [modelFile, setModelFile] = useState(null);
  const [modelName, setModelName] = useState('');
  const [modelVersion, setModelVersion] = useState('');
  const [modelDesc, setModelDesc] = useState('');
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef();

  // General models list
  const [generalModels, setGeneralModels] = useState([]);
  const [loading, setLoading] = useState(true);

  // Metrikleri yönet state'leri
  const [metricsFile, setMetricsFile] = useState(null);
  const metricsFileInputRef = useRef();

  // General models yükle
  useEffect(() => {
    fetchGeneralModels();
  }, []);

  const fetchGeneralModels = async () => {
    if (!token) {
      setGeneralModels([]);
      setLoading(false);
      return;
    }
    
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/general-models`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();
      setGeneralModels(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Error loading general models:', err);
      setGeneralModels([]);
    }
    setLoading(false);
  };

  const handleModelFileChange = (e) => {
    setModelFile(e.target.files?.[0] || null);
  };

  const handleMetricsFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        try {
          const jsonData = JSON.parse(event.target?.result);
          setMetricsFile(file);
          alert('Metrics file loaded successfully.');
        } catch (err) {
          alert('Invalid JSON file.');
          setMetricsFile(null);
        }
      };
      reader.readAsText(file);
    }
  };

  const handleModelUpload = async () => {
    if (!modelFile || !modelVersion || !modelName) {
      alert('Please select a model file, enter a name, and enter a version.');
      return;
    }

    if (!token) {
      alert('Session expired. Please log in again.');
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append('file', modelFile);
    formData.append('name', modelName);
    formData.append('version', modelVersion);
    formData.append('description', modelDesc);

    try {
      const res = await fetch(`${API_URL}/api/model/upload`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
      });

      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || 'Upload failed');
      }

      const data = await res.json();
      if (data.status === 'success') {
        alert('Model uploaded successfully!');
        setModelFile(null);
        setModelName('');
        setModelVersion('');
        setModelDesc('');
        setMetricsFile(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
        if (metricsFileInputRef.current) metricsFileInputRef.current.value = '';
        
        // Güncel model listesini yükle
        await fetchGeneralModels();
      }
    } catch (err) {
      alert('Upload error: ' + err.message);
      console.error(err);
    }

    setUploading(false);
  };

  // Admin değilse erişim reddet
  if (!isAdmin) {
    return (
      <div className="space-y-6 p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-8 text-center">
          <p className="text-red-900 text-lg font-semibold">⛔ Access Denied</p>
          <p className="text-red-700 text-sm mt-2">Only administrators can access this page.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">General Model Management</h1>
        <p className="text-gray-600 mt-2">Upload and manage multiple detection models. Admin only.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Model Upload Section */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Upload New Model</h3>
          <div className="space-y-4">
            {/* File Upload */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Model File</label>
              <div
                className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer hover:border-blue-400 transition"
                onClick={() => fileInputRef.current?.click()}
              >
                <svg className="w-12 h-12 text-gray-400 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
                <p className="text-gray-900 font-medium">
                  {modelFile ? modelFile.name : 'Drop YOLO model files here'}
                </p>
                <p className="text-gray-500 text-sm mt-1">(.pt, .weights, .onnx)</p>
                <button
                  className="border border-gray-300 bg-white px-4 py-2 rounded-lg text-sm font-medium mt-3 hover:bg-gray-50"
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    fileInputRef.current?.click();
                  }}
                >
                  Select File
                </button>
                <input
                  type="file"
                  accept=".pt,.weights,.onnx"
                  className="hidden"
                  ref={fileInputRef}
                  onChange={handleModelFileChange}
                />
              </div>
            </div>

            {/* Version Input */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Model Name</label>
              <input
                type="text"
                placeholder="e.g., PPE Detection"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                value={modelName}
                onChange={e => setModelName(e.target.value)}
              />
            </div>

            {/* Version Input */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Version</label>
              <input
                type="text"
                placeholder="e.g., v3.3.0"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                value={modelVersion}
                onChange={e => setModelVersion(e.target.value)}
              />
            </div>

            {/* Description */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Description</label>
              <textarea
                placeholder="Model description, improvements, etc."
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                rows={3}
                value={modelDesc}
                onChange={e => setModelDesc(e.target.value)}
              />
            </div>

            {/* Metrics File */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Metrics (Optional)</label>
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center cursor-pointer hover:border-blue-400 transition">
                <p className="text-gray-900 text-sm font-medium">
                  {metricsFile ? metricsFile.name : 'Drop metrics JSON here'}
                </p>
                <button
                  className="border border-gray-300 bg-white px-3 py-1.5 rounded text-xs font-medium mt-2 hover:bg-gray-50"
                  type="button"
                  onClick={() => metricsFileInputRef.current?.click()}
                >
                  Select File
                </button>
                <input
                  type="file"
                  accept=".json"
                  className="hidden"
                  ref={metricsFileInputRef}
                  onChange={handleMetricsFileChange}
                />
              </div>
            </div>

            {/* Upload Button */}
            <button
              className="w-full bg-blue-600 hover:bg-blue-700 text-white py-3 rounded-lg font-semibold disabled:bg-gray-300 disabled:cursor-not-allowed transition"
              onClick={handleModelUpload}
              disabled={uploading || !modelFile || !modelVersion || !modelName}
            >
              {uploading ? (
                <span className="flex items-center justify-center">
                  <svg className="animate-spin h-5 w-5 mr-2" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Uploading...
                </span>
              ) : (
                'Upload Model'
              )}
            </button>
          </div>
        </div>

        {/* General Models List */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Uploaded Models</h3>
          {loading ? (
            <div className="text-gray-500">Loading...</div>
          ) : generalModels.length === 0 ? (
            <div className="text-gray-500">No models uploaded yet.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-3 px-4 font-semibold text-gray-700">Name</th>
                    <th className="text-left py-3 px-4 font-semibold text-gray-700">Version</th>
                    <th className="text-left py-3 px-4 font-semibold text-gray-700">Description</th>
                    <th className="text-left py-3 px-4 font-semibold text-gray-700">Uploaded</th>
                  </tr>
                </thead>
                <tbody>
                  {generalModels.map((model) => (
                    <tr key={model.id} className="border-b border-gray-100 hover:bg-gray-50 transition">
                      <td className="py-3 px-4 text-sm font-medium text-gray-900">{model.name}</td>
                      <td className="py-3 px-4 text-sm text-gray-700">{model.version}</td>
                      <td className="py-3 px-4 text-sm text-gray-600">{model.description || '-'}</td>
                      <td className="py-3 px-4 text-sm text-gray-500">
                        {model.uploaded_at ? new Date(model.uploaded_at).toLocaleDateString('tr-TR') : 'N/A'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Notes</h3>
          <button
            onClick={fetchGeneralModels}
            className="text-sm px-3 py-1.5 border border-gray-300 rounded-lg hover:bg-gray-50 font-medium"
            disabled={loading}
          >
            {loading ? 'Loading...' : 'Refresh'}
          </button>
        </div>
        <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
          <p className="text-gray-700 text-sm font-medium">ℹ️ Models can be assigned per company in Model Camera Assignment.</p>
        </div>
      </div>
    </div>
  );
}

import { useState, useRef, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';

export function ModelManagement() {
  const { isAdmin, activeCompanyCode, token } = useAuth();

  // Company seçimi (Admin için)
  const [selectedCompany, setSelectedCompany] = useState(activeCompanyCode || '');
  const [companies, setCompanies] = useState([]);
  const [loadingCompanies, setLoadingCompanies] = useState(false);

  // Model yükleme ve aktif etme için state'ler
  const [modelFile, setModelFile] = useState(null);
  const [modelVersion, setModelVersion] = useState('');
  const [modelDesc, setModelDesc] = useState('');
  const [uploading, setUploading] = useState(false);
  const [availableModels, setAvailableModels] = useState([]);
  const [companyModels, setCompanyModels] = useState([]);
  const [activating, setActivating] = useState(false);
  const [activeModelId, setActiveModelId] = useState(null);
  const [activeModelMeta, setActiveModelMeta] = useState(null);
  const fileInputRef = useRef();

  // Test detection için state'ler
  const [selectedImage, setSelectedImage] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const [detectionResults, setDetectionResults] = useState(null);
  const [detectionError, setDetectionError] = useState(null);
  
  // Metrikleri yönetmek için state'ler
  const [metricsFile, setMetricsFile] = useState(null);
  const [accuracyStats, setAccuracyStats] = useState([
    { label: 'Overall Accuracy', value: 0, color: 'bg-blue-600' },
    { label: 'Helmet Detection', value: 0, color: 'bg-green-500' },
    { label: 'Vest Detection', value: 0, color: 'bg-orange-500' },
    { label: 'Worker Detection', value: 0, color: 'bg-purple-500' },
  ]);
  const [modelStats, setModelStats] = useState({
    inferenceTime: '0ms',
    totalDetections: 0,
  });
  const metricsFileInputRef = useRef();

  // Admin ise şirketleri yükle
  useEffect(() => {
    if (!isAdmin) return;
    
    setLoadingCompanies(true);
    fetch('http://localhost:8000/api/companies', {
      headers: { 'Authorization': `Bearer ${token}` }
    })
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          setCompanies(data);
          if (!selectedCompany && data.length > 0) {
            setSelectedCompany(data[0].code);
          }
        }
      })
      .catch(err => {
        console.error('Companies loading error:', err);
        setCompanies([]);
      })
      .finally(() => setLoadingCompanies(false));
  }, [isAdmin]);

  // Seçilen şirkete atanan modelleri yükle
  useEffect(() => {
    if (!selectedCompany) return;

    fetch(`http://localhost:8000/api/company/${selectedCompany}/models`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          setCompanyModels(data);
          const active = data.find(cm => cm.is_active);
          if (active) {
            setActiveModelId(active.id);
            setActiveModelMeta(active.model);
          } else {
            setActiveModelId(null);
            setActiveModelMeta(null);
          }
        } else {
          setCompanyModels([]);
          setActiveModelId(null);
          setActiveModelMeta(null);
        }
      })
      .catch(err => {
        console.error('Company models loading error:', err);
        setCompanyModels([]);
      });
  }, [selectedCompany]);

  // Tüm available modelleri yükle (Admin için)
  useEffect(() => {
    if (!isAdmin) return;

    fetch('http://localhost:8000/api/models', {
      headers: { 'Authorization': `Bearer ${token}` }
    })
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          setAvailableModels(data);
        } else {
          setAvailableModels([]);
        }
      })
      .catch(err => {
        console.error('Models loading error:', err);
        setAvailableModels([]);
      });
  }, [isAdmin, uploading]);

  const handleModelFileChange = (e) => {
    setModelFile(e.target.files?.[0] || null);
  };

  const handleModelUpload = async () => {
    if (!modelFile || !modelVersion) return;
    setUploading(true);
    const formData = new FormData();
    formData.append('file', modelFile);
    formData.append('version', modelVersion);
    formData.append('description', modelDesc);

    try {
      const res = await fetch('http://localhost:8000/api/model/upload', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
      });
      if (!res.ok) throw new Error('Model upload error');
      const data = await res.json();
      if (data.status === 'success') {
        setModelFile(null);
        setModelVersion('');
        setModelDesc('');
        if (fileInputRef.current) fileInputRef.current.value = '';
        alert('Model successfully uploaded.');
      } else {
        alert('Model upload failed.');
      }
    } catch (err) {
      alert('Model upload error.');
      console.error(err);
    }
    setUploading(false);
  };

  const handleAssignModel = async (modelId) => {
    if (!selectedCompany) {
      alert('Please select a company');
      return;
    }

    try {
      const res = await fetch(
        `http://localhost:8000/api/company/${selectedCompany}/models/${modelId}/assign`,
        {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` },
        }
      );
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Model assignment error');
      }
      alert('Model successfully assigned!');
      const refreshRes = await fetch(
        `http://localhost:8000/api/company/${selectedCompany}/models`,
        {
          headers: { 'Authorization': `Bearer ${token}` }
        }
      );
      const updatedModels = await refreshRes.json();
      if (Array.isArray(updatedModels)) {
        setCompanyModels(updatedModels);
      }
    } catch (err) {
      alert('Model assignment error: ' + err.message);
    }
  };

  const handleActivateModel = async (companyModelId) => {
    if (!selectedCompany) {
      alert('Please select a company');
      return;
    }

    setActivating(true);
    try {
      const res = await fetch(
        `http://localhost:8000/api/company/${selectedCompany}/models/${companyModelId}/activate`,
        {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` },
        }
      );
      if (!res.ok) throw new Error('Activation error');
      const data = await res.json();
      alert(data.message || 'Model activated!');
      const refreshRes = await fetch(
        `http://localhost:8000/api/company/${selectedCompany}/models`,
        {
          headers: { 'Authorization': `Bearer ${token}` }
        }
      );
      const updatedModels = await refreshRes.json();
      if (Array.isArray(updatedModels)) {
        setCompanyModels(updatedModels);
        const active = updatedModels.find(cm => cm.is_active);
        if (active) {
          setActiveModelId(active.id);
          setActiveModelMeta(active.model);
        }
      }
    } catch (err) {
      alert('Activation error: ' + err.message);
    }
    setActivating(false);
  };

  const handleDeactivateModel = async (companyModelId) => {
    if (!selectedCompany) {
      alert('Please select a company');
      return;
    }

    setActivating(true);
    try {
      const res = await fetch(
        `http://localhost:8000/api/company/${selectedCompany}/models/${companyModelId}/deactivate`,
        {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` },
        }
      );
      if (!res.ok) throw new Error('Deactivation error');
      const data = await res.json();
      alert(data.message || 'Model deactivated!');
      const refreshRes = await fetch(
        `http://localhost:8000/api/company/${selectedCompany}/models`,
        {
          headers: { 'Authorization': `Bearer ${token}` }
        }
      );
      const updatedModels = await refreshRes.json();
      if (Array.isArray(updatedModels)) {
        setCompanyModels(updatedModels);
        setActiveModelId(null);
        setActiveModelMeta(null);
      }
    } catch (err) {
      alert('Deactivation error: ' + err.message);
    }
    setActivating(false);
  };

  const handleImageUpload = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        setSelectedImage(event.target?.result);
        setShowResults(false);
        setDetectionResults(null);
        setDetectionError(null);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleRunDetection = async () => {
    if (!selectedImage || !activeModelMeta) {
      alert('Please select an image and activate a model.');
      return;
    }

    setIsAnalyzing(true);
    setDetectionError(null);
    setDetectionResults(null);

    try {
      const response = await fetch(selectedImage);
      const blob = await response.blob();
      
      const formData = new FormData();
      formData.append('file', blob, 'image.jpg');
      formData.append('model_path', activeModelMeta.path);

      const res = await fetch('http://localhost:8000/api/detect', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
      });

      const data = await res.json();
      
      if (!res.ok) {
        throw new Error(data.message || data.detail || `HTTP Error: ${res.status}`);
      }
      
      if (data.status === 'success') {
        setDetectionResults(data);
        setShowResults(true);
      } else {
        setDetectionError(data.message || 'Detection failed');
      }
    } catch (err) {
      const errorMsg = err.message || 'Unknown error';
      setDetectionError('Detection error: ' + errorMsg);
      console.error('Detection error:', err);
    }
    
    setIsAnalyzing(false);
  };

  const handleMetricsFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        try {
          const jsonData = JSON.parse(event.target?.result);
          setMetricsFile(file);
          updateMetricsFromJSON(jsonData);
          alert('Metrics loaded successfully.');
        } catch (err) {
          alert('Invalid JSON file.');
          setMetricsFile(null);
        }
      };
      reader.readAsText(file);
    }
  };

  const updateMetricsFromJSON = (jsonData) => {
    try {
      const newStats = [
        { 
          label: 'Overall Accuracy', 
          value: jsonData.overall_accuracy || 0, 
          color: 'bg-blue-600' 
        },
        { 
          label: 'Helmet Detection', 
          value: jsonData.helmet_detection || 0, 
          color: 'bg-green-500' 
        },
        { 
          label: 'Vest Detection', 
          value: jsonData.vest_detection || 0, 
          color: 'bg-orange-500' 
        },
        { 
          label: 'Worker Detection', 
          value: jsonData.worker_detection || 0, 
          color: 'bg-purple-500' 
        },
      ];
      
      setAccuracyStats(newStats);
      setModelStats({
        inferenceTime: `${jsonData.inference_time_ms || 0}ms`,
        totalDetections: jsonData.total_detections || 0,
      });
    } catch (err) {
      alert('JSON parsing error: ' + err.message);
    }
  };

  let modelName = activeModelMeta?.version || 'No active model';
  let modelDescStr = activeModelMeta?.description || '';
  let modelPathStr = activeModelMeta?.path || '';

  if (isAdmin && !selectedCompany) {
    return (
      <div className="space-y-6 p-6">
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-8 text-center">
          <p className="text-amber-900 text-lg font-semibold">⚠️ Please select a company</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* Company Selection for Admin */}
      {isAdmin && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Select Company</h3>
          <div className="flex gap-4">
            <select
              value={selectedCompany}
              onChange={(e) => setSelectedCompany(e.target.value)}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg font-medium"
            >
              <option value="">-- Select Company --</option>
              {companies.map((company) => (
                <option key={company.id} value={company.code}>
                  {company.name} ({company.code})
                </option>
              ))}
            </select>
          </div>
          {selectedCompany && (
            <div className="mt-2 p-3 bg-blue-50 rounded-lg text-blue-900 text-sm">
              ✅ Selected company: <strong>{companies.find(c => c.code === selectedCompany)?.name}</strong>
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Model Upload (Admin only) */}
        {isAdmin && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Upload New Model</h3>
            <div className="space-y-4">
              <div
                className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer"
                onClick={() => fileInputRef.current && fileInputRef.current.click()}
              >
                <p className="text-gray-900 mb-1 font-medium">
                  {modelFile ? modelFile.name : 'Drop YOLO model files here'}
                </p>
                <button
                  className="border border-gray-300 bg-white px-4 py-2 rounded-lg text-sm font-medium"
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    fileInputRef.current && fileInputRef.current.click();
                  }}
                >
                  Select Files
                </button>
                <input
                  type="file"
                  accept=".pt,.weights,.onnx"
                  className="hidden"
                  ref={fileInputRef}
                  onChange={handleModelFileChange}
                />
              </div>
              <div>
                <input
                  type="text"
                  placeholder="Model Version (e.g., v3.3.0)"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  value={modelVersion}
                  onChange={e => setModelVersion(e.target.value)}
                />
              </div>
              <div>
                <textarea
                  placeholder="Description"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  rows={2}
                  value={modelDesc}
                  onChange={e => setModelDesc(e.target.value)}
                />
              </div>
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center">
                <p className="text-gray-900 mb-2 text-sm font-medium">
                  {metricsFile ? metricsFile.name : 'Drop metrics JSON here'}
                </p>
                <button
                  className="border border-gray-300 bg-white px-3 py-1.5 rounded text-xs font-medium"
                  type="button"
                  onClick={() => metricsFileInputRef.current && metricsFileInputRef.current.click()}
                >
                  Upload Metrics
                </button>
                <input
                  type="file"
                  accept=".json"
                  className="hidden"
                  ref={metricsFileInputRef}
                  onChange={handleMetricsFileChange}
                />
              </div>
              <button
                className="w-full bg-blue-600 hover:bg-blue-700 text-white py-2.5 rounded-lg font-medium"
                type="button"
                onClick={handleModelUpload}
                disabled={uploading || !modelFile || !modelVersion}
              >
                {uploading ? 'Uploading...' : 'Upload Model'}
              </button>
            </div>
          </div>
        )}

        {/* Current Model Performance */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Current Model Performance</h3>
          {activeModelMeta ? (
            <>
              <div className="mb-4">
                <div className="flex items-center gap-4 p-4 bg-blue-50 rounded-xl border border-blue-100">
                  <div className="w-12 h-12 bg-blue-600 rounded-lg flex items-center justify-center shadow-lg shadow-blue-200">
                    <span className="text-white text-xl font-bold">Y</span>
                  </div>
                  <div>
                    <p className="text-gray-900 font-bold">{modelName}</p>
                    <p className="text-blue-600 text-sm font-medium">Active</p>
                    <p className="text-gray-500 text-xs">{modelDescStr}</p>
                  </div>
                </div>
              </div>
              <div className="space-y-5">
                {accuracyStats.map((item, idx) => (
                  <div key={idx}>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-gray-700 text-sm font-medium">{item.label}</span>
                      <span className="text-gray-900 font-bold">{item.value.toFixed(1)}%</span>
                    </div>
                    <div className="h-2 w-full bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${item.color}`}
                        style={{ width: `${Math.min(item.value, 100)}%` }}
                      ></div>
                    </div>
                  </div>
                ))}
              </div>
              <div className="grid grid-cols-2 gap-4 pt-6 border-t border-gray-100 mt-6">
                <div>
                  <p className="text-gray-500 text-xs font-medium mb-1 uppercase tracking-wider">Inference Time</p>
                  <p className="text-gray-900 text-xl font-bold">{modelStats.inferenceTime}</p>
                </div>
                <div>
                  <p className="text-gray-500 text-xs font-medium mb-1 uppercase tracking-wider">Total Detections</p>
                  <p className="text-gray-900 text-xl font-bold">{modelStats.totalDetections.toLocaleString()}</p>
                </div>
              </div>
            </>
          ) : (
            <div className="text-gray-500 text-center py-12">
              <div className="text-2xl font-bold mb-2">No active model</div>
              <div className="text-sm">Please activate a model to start detection.</div>
            </div>
          )}
        </div>
      </div>

      {/* Manage Models */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          {selectedCompany ? `Manage Models for ${selectedCompany}` : 'Manage Models'}
        </h3>
        
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Assigned Models */}
          <div>
            <h4 className="font-semibold text-gray-900 mb-3">Assigned Models</h4>
            {companyModels.length > 0 ? (
              <div className="space-y-2">
                {companyModels.map((cm) => (
                  <div key={cm.id} className="flex flex-col sm:flex-row sm:items-center justify-between bg-gray-50 border border-gray-200 rounded px-3 py-2 gap-2">
                    <div className="flex-1">
                      <div className="font-bold text-gray-900">{cm.model.version}</div>
                      <div className="text-xs text-gray-500">{cm.model.description}</div>
                      {cm.is_active && (
                        <div className="text-xs text-green-600 font-semibold">✅ Active</div>
                      )}
                    </div>
                    <div className="flex gap-2">
                      {cm.is_active ? (
                        <button
                          className="px-3 py-1 rounded bg-red-600 text-white text-xs font-medium"
                          disabled={activating}
                          onClick={() => handleDeactivateModel(cm.id)}
                        >
                          {activating ? 'Processing...' : 'Deactivate'}
                        </button>
                      ) : (
                        <button
                          className="px-3 py-1 rounded bg-green-600 text-white text-xs font-medium"
                          disabled={activating}
                          onClick={() => handleActivateModel(cm.id)}
                        >
                          {activating ? 'Processing...' : 'Activate'}
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-gray-500 text-center py-6 bg-gray-50 rounded-lg">
                <p className="text-sm">No models assigned to this company yet</p>
              </div>
            )}
          </div>

          {/* Available Models (Admin only) */}
          {isAdmin && (
            <div>
              <h4 className="font-semibold text-gray-900 mb-3">Available Models</h4>
              {availableModels.length > 0 ? (
                <div className="space-y-2">
                  {availableModels.map((model) => {
                    const isAssigned = companyModels.some(cm => cm.model_id === model.id);
                    return (
                      <div key={model.id} className="flex flex-col sm:flex-row sm:items-center justify-between bg-gray-50 border border-gray-200 rounded px-3 py-2 gap-2">
                        <div className="flex-1">
                          <div className="font-bold text-gray-900">{model.version}</div>
                          <div className="text-xs text-gray-500">{model.description}</div>
                        </div>
                        {!isAssigned ? (
                          <button
                            className="px-3 py-1 rounded bg-blue-600 text-white text-xs font-medium"
                            onClick={() => handleAssignModel(model.id)}
                          >
                            Assign
                          </button>
                        ) : (
                          <span className="text-xs text-green-600 font-semibold">✓ Assigned</span>
                        )}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="text-gray-500 text-center py-6 bg-gray-50 rounded-lg">
                  <p className="text-sm">No models uploaded</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Test Detection */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Test Detection</h3>
        <div className="flex flex-col md:flex-row gap-6">
          <div className="flex-1 space-y-4">
            <div className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center">
              {selectedImage ? (
                <img src={selectedImage} alt="Test" className="max-h-64 mx-auto rounded-lg shadow-sm" />
              ) : (
                <p className="text-gray-900 mb-1 font-medium">Upload test image</p>
              )}
              <input
                type="file"
                accept="image/*"
                onChange={handleImageUpload}
                className="hidden"
                id="test-image"
              />
              <label htmlFor="test-image" className="inline-block mt-4">
                <span className="cursor-pointer border border-gray-300 bg-white px-4 py-2 rounded-lg text-sm font-medium">
                  {selectedImage ? 'Change Image' : 'Select Image'}
                </span>
              </label>
            </div>
            <button
              onClick={handleRunDetection}
              disabled={!selectedImage || isAnalyzing || !activeModelMeta}
              className={`w-full py-3 rounded-lg font-medium ${
                !selectedImage || isAnalyzing || !activeModelMeta
                  ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                  : 'bg-blue-600 hover:bg-blue-700 text-white'
              }`}
            >
              {isAnalyzing ? 'Running Analysis...' : 'Run Detection'}
            </button>
          </div>
          <div className="flex-1 bg-gray-50 rounded-xl p-6 border border-gray-100">
            <h4 className="text-gray-900 font-semibold mb-4">Detection Results</h4>
            {detectionError ? (
              <div className="text-red-600 text-sm">{detectionError}</div>
            ) : showResults && detectionResults ? (
              <div className="space-y-4">
                <div className="bg-white p-4 rounded-lg border border-gray-200">
                  <p className="text-sm text-gray-600 mb-2">
                    <span className="font-semibold">Status:</span> {detectionResults.status}
                  </p>
                  <p className="text-sm text-gray-600 mb-2">
                    <span className="font-semibold">Detections:</span> {detectionResults.detections || 0}
                  </p>
                  {detectionResults.processing_time && (
                    <p className="text-sm text-gray-600">
                      <span className="font-semibold">Processing Time:</span> {detectionResults.processing_time.toFixed(2)}ms
                    </p>
                  )}
                </div>
                
                {detectionResults.objects && detectionResults.objects.length > 0 && (
                  <div className="bg-white p-4 rounded-lg border border-gray-200">
                    <p className="font-semibold text-sm mb-3">Detected Objects:</p>
                    <div className="space-y-2">
                      {detectionResults.objects.map((obj, idx) => (
                        <div key={idx} className="text-sm bg-gray-50 p-2 rounded">
                          <p><span className="font-medium">{obj.class || 'Object'}:</span> {(obj.confidence * 100).toFixed(1)}% confidence</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {detectionResults.image_base64 && (
                  <div className="bg-white p-4 rounded-lg border border-gray-200">
                    <p className="font-semibold text-sm mb-3">Annotated Image:</p>
                    <img 
                      src={`data:image/jpeg;base64,${detectionResults.image_base64}`} 
                      alt="Detected" 
                      className="w-full rounded"
                    />
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-20 text-gray-400">
                {isAnalyzing ? (
                  <div>
                    <div className="animate-spin inline-block w-6 h-6 border-3 border-gray-300 border-t-blue-600 rounded-full mb-3"></div>
                    <p>Analyzing...</p>
                  </div>
                ) : (
                  'Upload an image and run detection to see results'
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

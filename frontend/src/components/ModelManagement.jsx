import { useState, useRef, useEffect } from 'react';

export function ModelManagement() {
  // Model yükleme ve aktif etme için state'ler
  const [modelFile, setModelFile] = useState(null);
  const [modelVersion, setModelVersion] = useState('');
  const [modelDesc, setModelDesc] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadedModels, setUploadedModels] = useState([]);
  const [activating, setActivating] = useState(false);
  const [activeModelPath, setActiveModelPath] = useState(null);
  const [activeModelMeta, setActiveModelMeta] = useState(null);
  const fileInputRef = useRef();

  // Test detection için state'ler
  const [selectedImage, setSelectedImage] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [showResults, setShowResults] = useState(false);

  // Aktif model bilgisini backend'den çek
  useEffect(() => {
    fetch('http://localhost:8000/api/model/active')
      .then(res => res.json())
      .then(data => {
        setActiveModelPath(data.active_model_path);
      })
      .catch(() => setActiveModelPath(null));
  }, [uploadedModels, activating]);

  // Aktif model meta bilgisini güncelle
  useEffect(() => {
    if (!activeModelPath) {
      setActiveModelMeta(null);
      return;
    }
    // uploadedModels içinde path eşleşen modelin meta verisini bul
    const meta = uploadedModels.find(m => m.path === activeModelPath);
    setActiveModelMeta(meta || null);
  }, [activeModelPath, uploadedModels]);

  // Modelleri backend'den çek
  useEffect(() => {
    fetch('http://localhost:8000/api/models')
      .then(res => res.json())
      .then(data => {
        // Eğer veri dizi değilse (ör: hata objesi), boş diziye fallback yap
        if (!Array.isArray(data)) {
          setUploadedModels([]);
          // İsterseniz burada hata mesajını gösterebilirsiniz
          console.error('Model listesi alınamadı:', data?.detail || data);
        } else {
          setUploadedModels(data);
        }
      })
      .catch((err) => {
        setUploadedModels([]);
        console.error('Model listesi alınamadı:', err);
      });
  }, [activating, uploading]);

  // Model dosyası seçildiğinde çağrılır
  const handleModelFileChange = (e) => {
    setModelFile(e.target.files?.[0] || null);
  };

  // Model yükleme fonksiyonu
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
        body: formData,
      });
      if (!res.ok) throw new Error('Model yükleme hatası');
      const data = await res.json();
      if (data.status === 'success') {
        setUploadedModels((prev) => [...prev, data]);
        setModelFile(null);
        setModelVersion('');
        setModelDesc('');
        if (fileInputRef.current) fileInputRef.current.value = '';
        alert('Model başarıyla yüklendi.');
      } else {
        alert('Model yüklenemedi.');
      }
    } catch (err) {
      alert('Model yükleme hatası.');
    }
    setUploading(false);
  };

  // Modeli aktif etme fonksiyonu
  const handleActivateModel = async (modelPath) => {
    setActivating(true);
    const formData = new FormData();
    formData.append('path', modelPath);
    try {
      const res = await fetch('http://localhost:8000/api/model/activate', {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) throw new Error('Aktif etme hatası');
      const data = await res.json();
      if (data.status === 'active') {
        alert('Model aktif edildi!');
      } else {
        alert('Model aktif edilemedi.');
      }
    } catch (err) {
      alert('Aktif etme hatası.');
    }
    setActivating(false);
  };

  // Modeli deaktif etme fonksiyonu
  const handleDeactivateModel = async () => {
    setActivating(true);
    // Backend'de aktif modeli "None" yapmak için özel bir endpoint veya mevcut activate endpoint'ine boş path gönderebilirsiniz.
    // Burada örnek olarak boş path gönderiyoruz:
    const formData = new FormData();
    formData.append('path', '');
    try {
      const res = await fetch('http://localhost:8000/api/model/activate', {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) throw new Error('Deaktif etme hatası');
      const data = await res.json();
      if (data.status === 'active') {
        alert('Model deaktif edildi!');
      } else {
        alert('Model deaktif edilemedi.');
      }
    } catch (err) {
      alert('Deaktif etme hatası.');
    }
    setActivating(false);
  };

  // Test detection için resim yükleme
  const handleImageUpload = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        setSelectedImage(event.target?.result);
        setShowResults(false);
      };
      reader.readAsDataURL(file);
    }
  };

  // Test detection simülasyonu
  const handleRunDetection = () => {
    setIsAnalyzing(true);
    setTimeout(() => {
      setIsAnalyzing(false);
      setShowResults(true);
    }, 1500);
  };

  // Aktif modelden isim ve versiyon çıkarımı
  let modelName = activeModelMeta?.version || 'No active model';
  let modelDescStr = activeModelMeta?.description || '';
  let modelVersionStr = activeModelMeta?.version || '';
  let modelPathStr = activeModelMeta?.path || '';

  // Demo accuracy değerleri
  const accuracyStats = [
    { label: 'Overall Accuracy', value: 96.8, color: 'bg-blue-600' },
    { label: 'Helmet Detection', value: 98.2, color: 'bg-green-500' },
    { label: 'Vest Detection', value: 95.4, color: 'bg-orange-500' },
    { label: 'Worker Detection', value: 97.6, color: 'bg-purple-500' },
  ];

  return (
    <div className="space-y-6 p-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Model Yükleme */}
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
            <button
              className="w-full bg-blue-600 hover:bg-blue-700 text-white py-2.5 rounded-lg font-medium"
              type="button"
              onClick={handleModelUpload}
              disabled={uploading || !modelFile || !modelVersion}
            >
              {uploading ? 'Uploading...' : 'Upload Model'}
            </button>
          </div>
          {/* Yüklenen modelleri göster */}
          {uploadedModels.length > 0 && (
            <div className="mt-6">
              <h4 className="text-sm font-semibold mb-2">Uploaded Models</h4>
              <ul className="space-y-2">
                {uploadedModels.map((m, i) => {
                  const isActive = m.path === activeModelPath;
                  return (
                    <li key={i} className={`flex flex-col sm:flex-row sm:items-center justify-between bg-gray-50 border border-gray-200 rounded px-3 py-2`}>
                      <div>
                        <div className="font-bold">{m.version}</div>
                        <div className="text-xs text-gray-500">{m.description}</div>
                        <div className="text-xs text-gray-400 break-all">{m.path}</div>
                      </div>
                      <div className="flex gap-2 mt-2 sm:mt-0">
                        {isActive ? (
                          <button
                            className="px-3 py-1 rounded bg-red-600 text-white text-xs font-medium"
                            disabled={activating}
                            onClick={handleDeactivateModel}
                          >
                            {activating ? 'Deactivating...' : 'Deactivate'}
                          </button>
                        ) : (
                          <button
                            className="px-3 py-1 rounded bg-green-600 text-white text-xs font-medium"
                            disabled={activating}
                            onClick={() => handleActivateModel(m.path)}
                          >
                            {activating ? 'Activating...' : 'Activate'}
                          </button>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </div>
        {/* Aktif Model Bilgisi ve Doğruluk */}
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
                    <p className="text-blue-600 text-sm font-medium">
                      {modelVersionStr ? `Version ${modelVersionStr}` : 'No version info'}
                    </p>
                    <p className="text-gray-400 text-xs break-all">{modelPathStr}</p>
                    <p className="text-gray-500 text-xs">{modelDescStr}</p>
                  </div>
                </div>
              </div>
              <div className="space-y-5">
                {accuracyStats.map((item, idx) => (
                  <div key={idx}>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-gray-700 text-sm font-medium">{item.label}</span>
                      <span className="text-gray-900 font-bold">{item.value}%</span>
                    </div>
                    <div className="h-2 w-full bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${item.color}`}
                        style={{ width: `${item.value}%` }}
                      ></div>
                    </div>
                  </div>
                ))}
              </div>
              <div className="grid grid-cols-2 gap-4 pt-6 border-t border-gray-100 mt-6">
                <div>
                  <p className="text-gray-500 text-xs font-medium mb-1 uppercase tracking-wider">Inference Time</p>
                  <p className="text-gray-900 text-xl font-bold">23ms <span className="text-sm font-normal text-gray-500">avg</span></p>
                </div>
                <div>
                  <p className="text-gray-500 text-xs font-medium mb-1 uppercase tracking-wider">Total Detections</p>
                  <p className="text-gray-900 text-xl font-bold">45,230</p>
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
            {showResults ? (
              <div>
                <div className="mb-2">Detection completed. (Demo)</div>
              </div>
            ) : (
              <div className="text-center py-20 text-gray-400">Upload an image and run detection to see results</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
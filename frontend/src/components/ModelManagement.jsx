import { useState } from 'react';
import { Upload, Brain, Activity, Image, FileText, CheckCircle, AlertCircle } from 'lucide-react';

const modelVersions = [
  { version: 'v3.2.1', date: '2025-11-15', accuracy: 96.8, status: 'active', detections: 45230 },
  { version: 'v3.2.0', date: '2025-11-01', accuracy: 95.4, status: 'archived', detections: 32104 },
  { version: 'v3.1.5', date: '2025-10-18', accuracy: 94.2, status: 'archived', detections: 28945 },
];

export function ModelManagement() {
  const [selectedImage, setSelectedImage] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [showResults, setShowResults] = useState(false);

  const handleImageUpload = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        setSelectedImage(event.target?.result);
        setShowResults(false); // Yeni resim seçince eski sonuçları gizle
      };
      reader.readAsDataURL(file);
    }
  };

  const handleRunDetection = () => {
    setIsAnalyzing(true);
    // Yapay zeka analizini simüle ediyoruz (1.5 saniye bekle)
    setTimeout(() => {
        setIsAnalyzing(false);
        setShowResults(true);
    }, 1500);
  };

  return (
    <div className="space-y-6 p-6">
      {/* --- HEADER --- */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Model Management</h2>
        <p className="text-gray-500 text-sm mt-1">Manage YOLO detection models and test performance</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* --- UPLOAD NEW MODEL --- */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <div className="mb-4">
            <h3 className="text-lg font-semibold text-gray-900">Upload New Model</h3>
            <p className="text-gray-500 text-sm">Deploy a new YOLO model version</p>
          </div>
          
          <div className="space-y-4">
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-blue-400 hover:bg-blue-50 transition-all cursor-pointer group">
              <Upload className="w-12 h-12 text-gray-400 mx-auto mb-3 group-hover:text-blue-500 transition-colors" />
              <p className="text-gray-900 mb-1 font-medium">Drop YOLO model files here</p>
              <p className="text-gray-500 text-sm mb-4">or click to browse</p>
              <button className="border border-gray-300 bg-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors">
                Select Files
              </button>
              <p className="text-gray-400 text-xs mt-4">Supported: .pt, .weights, .onnx</p>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-gray-700 text-sm font-medium mb-1 block">Model Version</label>
                <input
                  type="text"
                  placeholder="e.g., v3.3.0"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                />
              </div>
              <div>
                <label className="text-gray-700 text-sm font-medium mb-1 block">Description</label>
                <textarea
                  placeholder="Describe model improvements..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none transition-all"
                  rows={3}
                />
              </div>
            </div>

            <button className="w-full bg-blue-600 hover:bg-blue-700 text-white py-2.5 rounded-lg font-medium flex items-center justify-center gap-2 transition-colors">
              <Upload className="w-4 h-4" />
              Upload Model
            </button>
          </div>
        </div>

        {/* --- CURRENT MODEL PERFORMANCE --- */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <div className="mb-6">
            <h3 className="text-lg font-semibold text-gray-900">Current Model Performance</h3>
            <p className="text-gray-500 text-sm">Active model metrics and statistics</p>
          </div>
          
          <div className="space-y-6">
            <div className="flex items-center gap-4 p-4 bg-blue-50 rounded-xl border border-blue-100">
              <div className="w-12 h-12 bg-blue-600 rounded-lg flex items-center justify-center shadow-lg shadow-blue-200">
                <Brain className="w-6 h-6 text-white" />
              </div>
              <div>
                <p className="text-gray-900 font-bold">YOLOv11 Safety Detection</p>
                <p className="text-blue-600 text-sm font-medium">Version 3.2.1 (Active)</p>
              </div>
            </div>

            <div className="space-y-5">
              {[
                { label: 'Overall Accuracy', value: 96.8, color: 'bg-blue-600' },
                { label: 'Helmet Detection', value: 98.2, color: 'bg-green-500' },
                { label: 'Vest Detection', value: 95.4, color: 'bg-orange-500' },
                { label: 'Worker Detection', value: 97.6, color: 'bg-purple-500' },
              ].map((item, idx) => (
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

            <div className="grid grid-cols-2 gap-4 pt-6 border-t border-gray-100">
              <div>
                <p className="text-gray-500 text-xs font-medium mb-1 uppercase tracking-wider">Inference Time</p>
                <p className="text-gray-900 text-xl font-bold">23ms <span className="text-sm font-normal text-gray-500">avg</span></p>
              </div>
              <div>
                <p className="text-gray-500 text-xs font-medium mb-1 uppercase tracking-wider">Total Detections</p>
                <p className="text-gray-900 text-xl font-bold">45,230</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* --- MODEL VERSION HISTORY --- */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <div className="mb-4">
            <h3 className="text-lg font-semibold text-gray-900">Model Version History</h3>
            <p className="text-gray-500 text-sm">Previously deployed models</p>
        </div>
        
        <div className="space-y-3">
            {modelVersions.map((model, index) => (
                <div key={index} className="flex flex-col sm:flex-row items-start sm:items-center justify-between p-4 border border-gray-200 rounded-xl hover:border-blue-300 hover:shadow-sm transition-all">
                <div className="flex items-center gap-4 mb-3 sm:mb-0">
                    <div className="w-10 h-10 bg-gray-50 rounded-lg flex items-center justify-center border border-gray-100">
                        <Brain className="w-5 h-5 text-gray-600" />
                    </div>
                    <div>
                    <div className="flex items-center gap-2 mb-0.5">
                        <p className="text-gray-900 font-semibold">{model.version}</p>
                        {model.status === 'active' && (
                        <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded text-xs font-medium border border-green-200">
                            Active
                        </span>
                        )}
                    </div>
                    <p className="text-gray-500 text-xs">Deployed on {model.date}</p>
                    </div>
                </div>

                <div className="flex items-center justify-between w-full sm:w-auto gap-8">
                    <div className="text-right">
                        <p className="text-gray-500 text-xs mb-0.5">Accuracy</p>
                        <p className="text-gray-900 font-medium">{model.accuracy}%</p>
                    </div>
                    <div className="text-right">
                        <p className="text-gray-500 text-xs mb-0.5">Detections</p>
                        <p className="text-gray-900 font-medium">{model.detections.toLocaleString()}</p>
                    </div>
                    <button className="border border-gray-300 hover:bg-gray-50 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors">
                    {model.status === 'active' ? 'Deactivate' : 'Activate'}
                    </button>
                </div>
                </div>
            ))}
        </div>
      </div>

      {/* --- TEST DETECTION (INTERAKTİF) --- */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <div className="mb-4">
            <h3 className="text-lg font-semibold text-gray-900">Test Detection</h3>
            <p className="text-gray-500 text-sm">Upload an image to test the current model</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-4">
            <div className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center hover:border-blue-400 hover:bg-blue-50 transition-all">
              {selectedImage ? (
                <img src={selectedImage} alt="Test" className="max-h-64 mx-auto rounded-lg shadow-sm" />
              ) : (
                <>
                  <div className="w-16 h-16 bg-blue-50 text-blue-500 rounded-full flex items-center justify-center mx-auto mb-4">
                     <Image className="w-8 h-8" />
                  </div>
                  <p className="text-gray-900 mb-1 font-medium">Upload test image</p>
                  <p className="text-gray-500 text-sm mb-4">PNG, JPG up to 10MB</p>
                </>
              )}
              
              <input
                type="file"
                accept="image/*"
                onChange={handleImageUpload}
                className="hidden"
                id="test-image"
              />
              <label htmlFor="test-image" className="inline-block mt-4">
                <span className="cursor-pointer border border-gray-300 bg-white hover:bg-gray-50 px-4 py-2 rounded-lg text-sm font-medium transition-colors">
                  {selectedImage ? 'Change Image' : 'Select Image'}
                </span>
              </label>
            </div>

            <button 
                onClick={handleRunDetection}
                disabled={!selectedImage || isAnalyzing}
                className={`w-full py-3 rounded-lg font-medium flex items-center justify-center gap-2 transition-colors ${
                    !selectedImage || isAnalyzing 
                    ? 'bg-gray-100 text-gray-400 cursor-not-allowed' 
                    : 'bg-blue-600 hover:bg-blue-700 text-white shadow-md hover:shadow-lg'
                }`}
            >
              {isAnalyzing ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    Running Analysis...
                  </>
              ) : (
                  <>
                    <Activity className="w-4 h-4" />
                    Run Detection
                  </>
              )}
            </button>
          </div>

          <div className="bg-gray-50 rounded-xl p-6 border border-gray-100">
            <h4 className="text-gray-900 font-semibold mb-4 flex items-center gap-2">
                Detection Results
                {showResults && <span className="text-xs font-normal text-green-600 bg-green-100 px-2 py-0.5 rounded-full">Completed</span>}
            </h4>
            
            {showResults ? (
              <div className="space-y-3">
                {[
                    { label: 'Workers Detected', count: 3, color: 'bg-blue-100 text-blue-700' },
                    { label: 'With Helmet', count: 2, color: 'bg-green-100 text-green-700' },
                    { label: 'Without Helmet', count: 1, color: 'bg-red-100 text-red-700' },
                    { label: 'With Vest', count: 3, color: 'bg-green-100 text-green-700' },
                ].map((stat, i) => (
                    <div key={i} className="flex items-center justify-between p-3 bg-white rounded-lg border border-gray-200 shadow-sm">
                        <span className="text-gray-700 text-sm font-medium">{stat.label}</span>
                        <span className={`px-2.5 py-0.5 rounded-md text-sm font-bold ${stat.color}`}>{stat.count}</span>
                    </div>
                ))}
                
                <div className="flex items-center justify-between p-3 bg-white rounded-lg border border-gray-200 shadow-sm mt-4">
                  <span className="text-gray-700 text-sm font-medium">Model Confidence</span>
                  <span className="text-gray-900 font-bold">94.2%</span>
                </div>
              </div>
            ) : (
              <div className="text-center py-20 flex flex-col items-center justify-center h-full">
                <FileText className="w-12 h-12 text-gray-300 mb-3" />
                <p className="text-gray-500 text-sm">Upload an image and run detection to see results</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
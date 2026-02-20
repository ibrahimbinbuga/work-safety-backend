import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { apiClient } from '../utils/api';

export function ModelCameraAssignment() {
  const { isAdmin, activeCompanyCode } = useAuth();
  const [cameras, setCameras] = useState([]);
  const [selectedCameraIds, setSelectedCameraIds] = useState([]);
  const [savingCameras, setSavingCameras] = useState(false);
  const [loadingCameras, setLoadingCameras] = useState(false);
  const [models, setModels] = useState([]);
  const [assignedModels, setAssignedModels] = useState([]);
  const [selectedModelId, setSelectedModelId] = useState(null);
  const [selectedAssignedModelIds, setSelectedAssignedModelIds] = useState([]);
  const [savingModels, setSavingModels] = useState(false);

  const fetchGeneralModels = async () => {
    try {
      const response = await apiClient.get('/api/general-models');
      const list = Array.isArray(response.data) ? response.data : [];
      setModels(list);
    } catch (error) {
      console.error('General model load error:', error);
      setModels([]);
    }
  };

  const fetchAssignedModels = async () => {
    if (isAdmin && !activeCompanyCode) return;
    try {
      const response = await apiClient.get(`/api/company/${activeCompanyCode}/general-models`);
      const list = Array.isArray(response.data) ? response.data : [];
      setAssignedModels(list);
      setSelectedAssignedModelIds(list.map((m) => m.id));
      if (list.length > 0) {
        setSelectedModelId((prev) => (list.find(m => m.id === prev) ? prev : list[0].id));
      } else {
        setSelectedModelId(null);
      }
    } catch (error) {
      console.error('Assigned model load error:', error);
      setAssignedModels([]);
      setSelectedAssignedModelIds([]);
      setSelectedModelId(null);
    }
  };

  const fetchCameras = async () => {
    if (isAdmin && !activeCompanyCode) return;
    if (!selectedModelId) return;
    try {
      setLoadingCameras(true);
      const response = await apiClient.get(`/api/company/${activeCompanyCode}/model-cameras?model_id=${selectedModelId}`);
      const data = Array.isArray(response.data) ? response.data : [];
      setCameras(data);
      setSelectedCameraIds(data.filter(c => c.model_is_active).map(c => c.id));
    } catch (error) {
      console.error('Camera list load error:', error);
      setCameras([]);
      setSelectedCameraIds([]);
    } finally {
      setLoadingCameras(false);
    }
  };

  useEffect(() => {
    fetchGeneralModels();
  }, []);

  useEffect(() => {
    fetchAssignedModels();
  }, [activeCompanyCode]);

  useEffect(() => {
    fetchCameras();
  }, [activeCompanyCode, selectedModelId]);

  const handleToggleSelection = (cameraId) => {
    setSelectedCameraIds((prev) =>
      prev.includes(cameraId) ? prev.filter(id => id !== cameraId) : [...prev, cameraId]
    );
  };

  const handleSaveModels = async () => {
    if (!activeCompanyCode) return;
    try {
      setSavingModels(true);
      await apiClient.put(`/api/company/${activeCompanyCode}/general-models`, {
        model_ids: selectedAssignedModelIds,
      });
      await fetchAssignedModels();
    } catch (error) {
      console.error('Model assignment save error:', error);
    } finally {
      setSavingModels(false);
    }
  };

  const handleSaveCameras = async () => {
    if (!activeCompanyCode || !selectedModelId) return;
    try {
      setSavingCameras(true);
      await apiClient.put(`/api/company/${activeCompanyCode}/model-cameras`, {
        model_id: selectedModelId,
        camera_ids: selectedCameraIds,
      });
      await fetchCameras();
    } catch (error) {
      console.error('Camera assignment save error:', error);
    } finally {
      setSavingCameras(false);
    }
  };

  if (isAdmin && !activeCompanyCode) {
    return (
      <div className="space-y-6 p-6">
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-8 text-center">
          <p className="text-amber-900 text-lg font-semibold">⚠️ Please select a company from the sidebar.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Model Camera Assignment</h2>
        <p className="text-gray-500 text-sm mt-1">
          Select models for the company and configure which cameras they run on.
        </p>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Company Models</h3>
            <p className="text-xs text-gray-500">Only admins can edit company models.</p>
          </div>
          {isAdmin && (
            <button
              onClick={handleSaveModels}
              className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium disabled:bg-gray-300"
              disabled={savingModels}
            >
              {savingModels ? 'Saving...' : 'Save Models'}
            </button>
          )}
        </div>

        {isAdmin ? (
          models.length === 0 ? (
            <div className="text-sm text-gray-500">No models uploaded yet.</div>
          ) : (
            <div className="space-y-2">
              {models.map((model) => (
                <label key={model.id} className="flex items-center gap-3 p-3 border border-gray-100 rounded-lg">
                  <input
                    type="checkbox"
                    className="h-4 w-4"
                    checked={selectedAssignedModelIds.includes(model.id)}
                    onChange={() => {
                      setSelectedAssignedModelIds((prev) =>
                        prev.includes(model.id)
                          ? prev.filter(id => id !== model.id)
                          : [...prev, model.id]
                      );
                    }}
                  />
                  <div>
                    <p className="text-sm font-medium text-gray-900">{model.name}</p>
                    <p className="text-xs text-gray-500">{model.version} • {model.description || '-'}</p>
                  </div>
                </label>
              ))}
            </div>
          )
        ) : (
          assignedModels.length === 0 ? (
            <div className="text-sm text-gray-500">No models assigned to this company.</div>
          ) : (
            <div className="space-y-2">
              {assignedModels.map((model) => (
                <div key={model.id} className="flex items-center gap-3 p-3 border border-gray-100 rounded-lg">
                  <div>
                    <p className="text-sm font-medium text-gray-900">{model.name}</p>
                    <p className="text-xs text-gray-500">{model.version} • {model.description || '-'}</p>
                  </div>
                </div>
              ))}
            </div>
          )
        )}
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Select Model</h3>
            <p className="text-xs text-gray-500">Choose a company model to configure cameras.</p>
          </div>
          <button
            onClick={handleSaveCameras}
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium disabled:bg-gray-300"
            disabled={savingCameras || !selectedModelId}
          >
            {savingCameras ? 'Saving...' : 'Save Cameras'}
          </button>
        </div>

        {assignedModels.length === 0 ? (
          <div className="text-sm text-gray-500">No models assigned to this company.</div>
        ) : (
          <div className="space-y-2">
            {assignedModels.map((model) => (
              <label key={model.id} className="flex items-center gap-3 p-3 border border-gray-100 rounded-lg">
                <input
                  type="radio"
                  name="assigned-model"
                  className="h-4 w-4"
                  checked={selectedModelId === model.id}
                  onChange={() => setSelectedModelId(model.id)}
                />
                <div>
                  <p className="text-sm font-medium text-gray-900">{model.name}</p>
                  <p className="text-xs text-gray-500">{model.version} • {model.description || '-'}</p>
                </div>
              </label>
            ))}
          </div>
        )}
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Cameras</h3>
        {loadingCameras ? (
          <div className="text-center py-8 text-gray-500">Loading cameras...</div>
        ) : cameras.length === 0 ? (
          <div className="text-center py-8 text-gray-500">No cameras found.</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {cameras.map((camera) => (
              <label key={camera.id} className="flex items-center gap-3 p-3 border border-gray-100 rounded-lg hover:bg-gray-50">
                <input
                  type="checkbox"
                  className="h-4 w-4"
                  checked={selectedCameraIds.includes(camera.id)}
                  onChange={() => handleToggleSelection(camera.id)}
                />
                <div>
                  <p className="text-sm font-medium text-gray-900">{camera.name}</p>
                  <p className="text-xs text-gray-500">{camera.location}</p>
                </div>
              </label>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

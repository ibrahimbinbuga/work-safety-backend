import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { apiClient } from '../utils/api';

export function ModelCameraAssignment() {
  const { isAdmin, activeCompanyCode } = useAuth();
  const [cameras, setCameras] = useState([]);
  const [loadingCameras, setLoadingCameras] = useState(false);
  const [loadingModels, setLoadingModels] = useState(true);
  const [loadingAssignedModels, setLoadingAssignedModels] = useState(true);
  const [models, setModels] = useState([]);
  const [assignedModels, setAssignedModels] = useState([]);
  const [selectedAssignedModelIds, setSelectedAssignedModelIds] = useState([]);
  const [savingModels, setSavingModels] = useState(false);
  const [modelCameraOverview, setModelCameraOverview] = useState({});
  const [loadingOverview, setLoadingOverview] = useState(false);
  const [cameraSelectionByModel, setCameraSelectionByModel] = useState({});
  const [savingAssignments, setSavingAssignments] = useState(false);

  const fetchModelCameraOverview = async (modelList = assignedModels) => {
    if (!activeCompanyCode) return;
    if (!Array.isArray(modelList) || modelList.length === 0) {
      setModelCameraOverview({});
      setCameraSelectionByModel({});
      return;
    }

    try {
      setLoadingOverview(true);

      const entries = await Promise.all(
        modelList.map(async (model) => {
          const response = await apiClient.get(
            `/api/company/${activeCompanyCode}/model-cameras?model_id=${model.id}`
          );
          const data = Array.isArray(response.data) ? response.data : [];
          const activeCameras = data
            .filter((camera) => camera.model_is_active)
            .map((camera) => ({ id: camera.id, name: camera.name, location: camera.location }));

          return [model.id, activeCameras];
        })
      );

      const overviewMap = Object.fromEntries(entries);
      const selectionMap = Object.fromEntries(
        entries.map(([modelId, activeCameras]) => [
          modelId,
          activeCameras.map((camera) => camera.id),
        ])
      );

      setModelCameraOverview(overviewMap);
      setCameraSelectionByModel(selectionMap);
    } catch (error) {
      console.error('Model camera overview load error:', error);
      setModelCameraOverview({});
      setCameraSelectionByModel({});
    } finally {
      setLoadingOverview(false);
    }
  };

  const fetchCompanyCameras = async () => {
    if (!activeCompanyCode) return;
    try {
      setLoadingCameras(true);
      const response = await apiClient.get(`/api/cameras?company_code=${activeCompanyCode}`);
      const data = Array.isArray(response.data) ? response.data : [];
      setCameras(data);
    } catch (error) {
      console.error('Company camera load error:', error);
      setCameras([]);
    } finally {
      setLoadingCameras(false);
    }
  };

  const fetchGeneralModels = async () => {
    setLoadingModels(true);
    try {
      const response = await apiClient.get('/api/general-models');
      const list = Array.isArray(response.data) ? response.data : [];
      setModels(list);
    } catch (error) {
      console.error('General model load error:', error);
      setModels([]);
    } finally {
      setLoadingModels(false);
    }
  };

  const fetchAssignedModels = async () => {
    if (!activeCompanyCode) {
      setAssignedModels([]);
      setSelectedAssignedModelIds([]);
      setModelCameraOverview({});
      setCameraSelectionByModel({});
      setLoadingAssignedModels(false);
      return;
    }

    setLoadingAssignedModels(true);
    try {
      const response = await apiClient.get(`/api/company/${activeCompanyCode}/general-models`);
      const list = Array.isArray(response.data) ? response.data : [];
      setAssignedModels(list);
      setSelectedAssignedModelIds(list.map((m) => m.id));
      await fetchModelCameraOverview(list);
    } catch (error) {
      console.error('Assigned model load error:', error);
      setAssignedModels([]);
      setSelectedAssignedModelIds([]);
      setModelCameraOverview({});
      setCameraSelectionByModel({});
    } finally {
      setLoadingAssignedModels(false);
    }
  };

  useEffect(() => {
    fetchGeneralModels();
  }, []);

  useEffect(() => {
    fetchAssignedModels();
  }, [activeCompanyCode]);

  useEffect(() => {
    fetchCompanyCameras();
  }, [activeCompanyCode]);

  const handleToggleModelCamera = (modelId, cameraId) => {
    setCameraSelectionByModel((prev) => {
      const selected = prev[modelId] || [];
      const nextSelected = selected.includes(cameraId)
        ? selected.filter((id) => id !== cameraId)
        : [...selected, cameraId];

      return {
        ...prev,
        [modelId]: nextSelected,
      };
    });
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

  const handleSaveAllAssignments = async () => {
    if (!activeCompanyCode || assignedModels.length === 0) return;
    try {
      setSavingAssignments(true);

      await Promise.all(
        assignedModels.map((model) =>
          apiClient.put(`/api/company/${activeCompanyCode}/model-cameras`, {
            model_id: model.id,
            camera_ids: cameraSelectionByModel[model.id] || [],
          })
        )
      );

      await fetchModelCameraOverview();
    } catch (error) {
      console.error('Camera assignment save error:', error);
    } finally {
      setSavingAssignments(false);
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
          loadingModels ? (
            <div className="text-sm text-gray-500">Loading models...</div>
          ) : models.length === 0 ? (
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
          loadingAssignedModels ? (
            <div className="text-sm text-gray-500">Loading assigned models...</div>
          ) : assignedModels.length === 0 ? (
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
            <h3 className="text-lg font-semibold text-gray-900">Model Camera Assignment Overview</h3>
            <p className="text-xs text-gray-500">
              Select cameras for each model directly here. You can update multiple models at the same time.
            </p>
          </div>
          <button
            onClick={handleSaveAllAssignments}
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium disabled:bg-gray-300"
            disabled={savingAssignments || assignedModels.length === 0}
          >
            {savingAssignments ? 'Saving...' : 'Save All Assignments'}
          </button>
        </div>

        {loadingOverview || loadingCameras || loadingAssignedModels ? (
          <div className="text-center py-8 text-gray-500">Loading assignment overview...</div>
        ) : assignedModels.length === 0 ? (
          <div className="text-sm text-gray-500">No models assigned to this company.</div>
        ) : cameras.length === 0 ? (
          <div className="text-sm text-gray-500">No cameras found for this company.</div>
        ) : (
          <div className="space-y-3">
            {assignedModels.map((model) => {
              const overviewCameras = modelCameraOverview[model.id] || [];
              const selectedIds = cameraSelectionByModel[model.id] || [];

              return (
                <div key={model.id} className="rounded-lg border border-gray-100 p-4">
                  <div className="flex items-start justify-between gap-4 mb-3">
                    <div>
                      <p className="text-sm font-semibold text-gray-900">{model.name}</p>
                      <p className="text-xs text-gray-500">{model.version} • {model.description || '-'}</p>
                    </div>
                    <div className="text-right">
                      <span className="text-xs font-medium px-2 py-1 rounded-full bg-gray-100 text-gray-700">
                        {selectedIds.length} selected
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                    {cameras.map((camera) => (
                      <label
                        key={`${model.id}-${camera.id}`}
                        className="flex items-center gap-2 p-2 border border-gray-100 rounded-md hover:bg-gray-50"
                      >
                        <input
                          type="checkbox"
                          className="h-4 w-4"
                          checked={selectedIds.includes(camera.id)}
                          onChange={() => handleToggleModelCamera(model.id, camera.id)}
                        />
                        <div>
                          <p className="text-sm text-gray-900">{camera.name}</p>
                          <p className="text-xs text-gray-500">{camera.location || '-'}</p>
                        </div>
                      </label>
                    ))}
                  </div>

                  <div className="mt-3 flex flex-wrap gap-2">
                    {overviewCameras.length === 0 ? (
                      <p className="text-xs text-gray-400">Saved state: no camera linked yet.</p>
                    ) : (
                      overviewCameras.map((camera) => (
                        <span
                          key={`overview-${model.id}-${camera.id}`}
                          className="px-2 py-1 text-xs rounded-full border border-green-100 bg-green-50 text-green-700"
                        >
                          {camera.name}
                        </span>
                      ))
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

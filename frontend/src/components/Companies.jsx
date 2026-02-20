import { useEffect, useState } from 'react';
import { apiClient, addCompanyCodeToUrl } from '../utils/api';
import { Building2 } from 'lucide-react';

export const Companies = () => {
  const [companies, setCompanies] = useState([]);
  const [companyCameras, setCompanyCameras] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchCompanies = async () => {
    try {
      setLoading(true);
      const response = await apiClient.get('/api/companies');
      const companyList = Array.isArray(response.data) ? response.data : [];
      setCompanies(companyList);

      const cameraPromises = companyList.map(async (company) => {
        try {
          const url = addCompanyCodeToUrl('/api/cameras', company.code);
          const camerasRes = await apiClient.get(url);
          return [company.code, Array.isArray(camerasRes.data) ? camerasRes.data : []];
        } catch (err) {
          return [company.code, []];
        }
      });

      const cameraEntries = await Promise.all(cameraPromises);
      setCompanyCameras(Object.fromEntries(cameraEntries));
    } catch (err) {
      setError('Failed to load companies');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCompanies();
  }, []);

  return (
    <div className="space-y-6 p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Companies</h1>
        <p className="text-gray-600 mt-2">All registered companies in the system.</p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
          <p className="text-red-700">{error}</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 p-4">
            {companies.map((company) => (
              <div key={company.id} className="border border-gray-100 rounded-lg p-4 hover:shadow-sm transition-shadow">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center">
                    <Building2 className="w-5 h-5 text-blue-600" />
                  </div>
                  <div>
                    <p className="text-gray-900 font-semibold">{company.name}</p>
                    <p className="text-gray-500 text-sm">{company.code}</p>
                  </div>
                </div>

                <div className="mt-4 border-t border-gray-100 pt-3">
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Cameras</p>
                  <ul className="mt-2 space-y-1">
                    {(companyCameras[company.code] || []).length === 0 ? (
                      <li className="text-sm text-gray-400">No cameras</li>
                    ) : (
                      companyCameras[company.code].map((camera) => (
                        <li key={camera.id} className="text-sm text-gray-700">
                          • {camera.name}
                        </li>
                      ))
                    )}
                  </ul>
                </div>
              </div>
            ))}
          </div>
          {companies.length === 0 && (
            <div className="text-center py-10 text-gray-500">No companies found.</div>
          )}
        </div>
      )}
    </div>
  );
};

import { useState, useEffect } from 'react';
import { Bell, Mail, Users, Moon, Sun, Save } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useAppearance } from '../context/AppearanceContext';
import { apiClient } from '../utils/api';

const DEFAULT_NOTIF = {
  email_enabled: false,
  report_period: 'weekly',
  report_formats: ['pdf'],
  push_enabled: true,
  alert_critical: true,
  alert_camera_offline: true,
  alert_model_updates: false,
};

export function Settings() {
  const { isAdmin, activeCompanyCode } = useAuth();
  const { settings: appearance, updateSetting, COLOR_VARS } = useAppearance();
  const [activeTab, setActiveTab] = useState(isAdmin ? 'appearance' : 'notifications');
  const [users, setUsers] = useState([]);
  const [usersLoading, setUsersLoading] = useState(false);

  // Notification state
  const [notif, setNotif] = useState(DEFAULT_NOTIF);
  const [notifLoading, setNotifLoading] = useState(false);
  const [notifSaving, setNotifSaving] = useState(false);

  useEffect(() => {
    if (activeTab !== 'users' || !activeCompanyCode) return;
    setUsersLoading(true);
    apiClient
      .get(`/api/admin/users?company_code=${encodeURIComponent(activeCompanyCode)}`)
      .then((res) => setUsers(res.data))
      .catch(() => setUsers([]))
      .finally(() => setUsersLoading(false));
  }, [activeTab, activeCompanyCode]);

  useEffect(() => {
    if (activeTab !== 'notifications' || !activeCompanyCode) return;
    setNotifLoading(true);
    apiClient
      .get(`/api/company/${encodeURIComponent(activeCompanyCode)}/notification-settings`)
      .then((res) => setNotif(res.data))
      .catch(() => setNotif(DEFAULT_NOTIF))
      .finally(() => setNotifLoading(false));
  }, [activeTab, activeCompanyCode]);

  const handleSaveNotif = async () => {
    setNotifSaving(true);
    try {
      const res = await apiClient.put(
        `/api/company/${encodeURIComponent(activeCompanyCode)}/notification-settings`,
        notif
      );
      setNotif(res.data);
    } catch {
      // keep existing state
    } finally {
      setNotifSaving(false);
    }
  };

  const setNotifField = (field, value) => setNotif((prev) => ({ ...prev, [field]: value }));

  const toggleFormat = (fmt) => {
    setNotif((prev) => {
      const formats = prev.report_formats.includes(fmt)
        ? prev.report_formats.filter((f) => f !== fmt)
        : [...prev.report_formats, fmt];
      return { ...prev, report_formats: formats.length ? formats : [fmt] };
    });
  };

  const handleAddUser = () => {
    const to = 'developmentifd@gmail.com';
    const subject = encodeURIComponent(`Kullanıcı Ekleme Talebi - ${activeCompanyCode}`);
    const body = encodeURIComponent(
      `${activeCompanyCode} şirketimize [kullanıcı_emaili] mailinde [şifre] şifreli bir kullanıcı eklemek istiyoruz.`
    );
    window.location.href = `mailto:${to}?subject=${subject}&body=${body}`;
  };

  // Toggle Switch Bileşeni (Custom)
  const Switch = ({ checked, onCheckedChange }) => (
    <button 
      onClick={() => onCheckedChange(!checked)}
      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
        checked ? 'bg-blue-600' : 'bg-gray-200'
      }`}
    >
      <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
        checked ? 'translate-x-6' : 'translate-x-1'
      }`} />
    </button>
  );


  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Settings</h2>
        <p className="text-gray-500 text-sm mt-1">
          {isAdmin ? 'Manage your personal preferences' : 'Manage your system preferences and configurations'}
        </p>
      </div>

      {/* Tabs Navigation */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          {(isAdmin ? ['appearance'] : ['notifications', 'users', 'appearance']).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`whitespace-nowrap pb-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === tab
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </nav>
      </div>

      {/* --- NOTIFICATIONS TAB --- */}
      {!isAdmin && activeTab === 'notifications' && (
        <div className="space-y-6 max-w-4xl">
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <div className="mb-6">
              <h3 className="text-lg font-bold text-gray-900">Notification Settings</h3>
              <p className="text-gray-500 text-sm">Configure how you receive alerts and notifications</p>
            </div>

            {notifLoading ? (
              <p className="text-gray-500 text-sm text-center py-8">Loading settings...</p>
            ) : (
              <div className="space-y-6">

                {/* ── Email ── */}
                <div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                        <Mail className="w-5 h-5 text-blue-600" />
                      </div>
                      <div>
                        <label className="text-gray-900 font-medium block">Email Notifications</label>
                        <p className="text-gray-500 text-sm">Receive scheduled reports via email</p>
                      </div>
                    </div>
                    <Switch
                      checked={notif.email_enabled}
                      onCheckedChange={(v) => setNotifField('email_enabled', v)}
                    />
                  </div>

                  {/* Email sub-options — shown only when enabled */}
                  {notif.email_enabled && (
                    <div className="mt-4 ml-14 p-4 bg-gray-50 rounded-lg border border-gray-200 space-y-4">

                      {/* Report Period */}
                      <div>
                        <label className="text-sm font-semibold text-gray-700 mb-2 block">Report Period</label>
                        <div className="flex gap-3">
                          {[
                            { value: 'daily',   label: 'Daily' },
                            { value: 'weekly',  label: 'Weekly' },
                            { value: 'monthly', label: 'Monthly' },
                          ].map(({ value, label }) => (
                            <button
                              key={value}
                              onClick={() => setNotifField('report_period', value)}
                              className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
                                notif.report_period === value
                                  ? 'bg-blue-600 text-white border-blue-600'
                                  : 'bg-white text-gray-600 border-gray-300 hover:border-blue-400'
                              }`}
                            >
                              {label}
                            </button>
                          ))}
                        </div>
                        <p className="text-xs text-gray-400 mt-1">
                          {notif.report_period === 'daily'   && 'Sent every morning at 08:00 UTC'}
                          {notif.report_period === 'weekly'  && 'Sent every Monday morning at 08:00 UTC'}
                          {notif.report_period === 'monthly' && 'Sent on the 1st of each month at 08:00 UTC'}
                        </p>
                      </div>

                      {/* Report Formats */}
                      <div>
                        <label className="text-sm font-semibold text-gray-700 mb-2 block">Report Format</label>
                        <div className="flex gap-3">
                          {['pdf', 'excel', 'csv'].map((fmt) => (
                            <label key={fmt} className="flex items-center gap-2 cursor-pointer select-none">
                              <input
                                type="checkbox"
                                className="w-4 h-4 accent-blue-600 rounded"
                                checked={notif.report_formats.includes(fmt)}
                                onChange={() => toggleFormat(fmt)}
                              />
                              <span className="text-sm text-gray-700 uppercase font-medium">{fmt}</span>
                            </label>
                          ))}
                        </div>
                        <p className="text-xs text-gray-400 mt-1">Select at least one format</p>
                      </div>

                    </div>
                  )}
                </div>

                <hr className="border-gray-100" />

                {/* ── Push ── */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 bg-orange-100 rounded-lg flex items-center justify-center">
                      <Bell className="w-5 h-5 text-orange-600" />
                    </div>
                    <div>
                      <label className="text-gray-900 font-medium block">Push Notifications</label>
                      <p className="text-gray-500 text-sm">Browser push notifications</p>
                    </div>
                  </div>
                  <Switch
                    checked={notif.push_enabled}
                    onCheckedChange={(v) => setNotifField('push_enabled', v)}
                  />
                </div>

                <hr className="border-gray-100" />

                {/* ── Alert Preferences ── */}
                <div className="space-y-4 pt-2">
                  <h4 className="text-gray-900 font-semibold">Alert Preferences</h4>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <label className="text-gray-700 text-sm">Critical Violations</label>
                      <Switch
                        checked={notif.alert_critical}
                        onCheckedChange={(v) => setNotifField('alert_critical', v)}
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <label className="text-gray-700 text-sm">Camera Offline</label>
                      <Switch
                        checked={notif.alert_camera_offline}
                        onCheckedChange={(v) => setNotifField('alert_camera_offline', v)}
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <label className="text-gray-700 text-sm">Model Updates</label>
                      <Switch
                        checked={notif.alert_model_updates}
                        onCheckedChange={(v) => setNotifField('alert_model_updates', v)}
                      />
                    </div>
                  </div>
                </div>

                <button
                  onClick={handleSaveNotif}
                  disabled={notifSaving}
                  className="bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white px-4 py-2 rounded-lg font-medium flex items-center gap-2 transition-colors"
                >
                  <Save className="w-4 h-4" />
                  {notifSaving ? 'Saving…' : 'Save Notification Settings'}
                </button>

              </div>
            )}
          </div>
        </div>
      )}

{/* --- USERS TAB --- */}
      {!isAdmin && activeTab === 'users' && (
        <div className="space-y-6 max-w-4xl">
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
                <div className="flex items-center justify-between mb-6">
                    <div>
                        <h3 className="text-lg font-bold text-gray-900">User Management</h3>
                        <p className="text-gray-500 text-sm">Manage users</p>
                    </div>
                    <button
                        onClick={handleAddUser}
                        className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium flex items-center gap-2 transition-colors"
                    >
                        <Users className="w-4 h-4" />
                        Add User
                    </button>
                </div>

                <div className="space-y-3">
                    {usersLoading ? (
                        <p className="text-gray-500 text-sm text-center py-6">Loading users...</p>
                    ) : users.length === 0 ? (
                        <p className="text-gray-400 text-sm text-center py-6">No users found for this company.</p>
                    ) : (
                        users.map((user) => (
                            <div key={user.id} className="flex items-center justify-between p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
                                <div className="flex items-center gap-4">
                                    <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center text-blue-600">
                                        <Users className="w-5 h-5" />
                                    </div>
                                    <div>
                                        <p className="text-gray-900 font-medium">{user.email}</p>
                                    </div>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>
        </div>
      )}

      {/* --- APPEARANCE TAB --- */}
      {activeTab === 'appearance' && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 max-w-4xl">
            <div className="mb-6">
              <h3 className="text-lg font-bold text-gray-900">Appearance Settings</h3>
              <p className="text-gray-500 text-sm">Customize the look and feel of your dashboard</p>
            </div>

            <div className="space-y-6">
                {/* Dark Mode */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center text-gray-600">
                            {appearance.isDarkMode ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
                        </div>
                        <div>
                            <label className="text-gray-900 font-medium block">Dark Mode</label>
                            <p className="text-gray-500 text-sm">Switch between light and dark themes</p>
                        </div>
                    </div>
                    <Switch
                        checked={appearance.isDarkMode}
                        onCheckedChange={(v) => updateSetting('isDarkMode', v)}
                    />
                </div>

                <hr className="border-gray-100" />

                {/* Theme Color */}
                <div>
                    <label className="text-sm font-medium text-gray-700 mb-3 block">Theme Color</label>
                    <div className="flex gap-3">
                        {Object.entries(COLOR_VARS).map(([name, vars]) => (
                            <button
                                key={name}
                                onClick={() => updateSetting('themeColor', name)}
                                style={{ backgroundColor: vars.p600 }}
                                className={`w-10 h-10 rounded-lg border-2 hover:scale-105 transition-transform ${
                                    appearance.themeColor === name
                                        ? 'border-gray-900 ring-2 ring-gray-300'
                                        : 'border-transparent'
                                }`}
                            />
                        ))}
                    </div>
                </div>

            </div>
        </div>
      )}
    </div>
  );
}
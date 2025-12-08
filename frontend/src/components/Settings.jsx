import { useState } from 'react';
import { Bell, Mail, Smartphone, Camera, Users, Shield, Moon, Sun, Save } from 'lucide-react';

export function Settings() {
  const [activeTab, setActiveTab] = useState('notifications');
  const [isDarkMode, setIsDarkMode] = useState(false);
  
  // Notification States
  const [emailNotifications, setEmailNotifications] = useState(true);
  const [smsNotifications, setSmsNotifications] = useState(false); // Telegram -> SMS oldu
  const [pushNotifications, setPushNotifications] = useState(true);

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
        <p className="text-gray-500 text-sm mt-1">Manage your system preferences and configurations</p>
      </div>

      {/* Tabs Navigation */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          {['notifications', 'cameras', 'users', 'appearance'].map((tab) => (
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
      {activeTab === 'notifications' && (
        <div className="space-y-6 max-w-4xl">
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <div className="mb-6">
              <h3 className="text-lg font-bold text-gray-900">Notification Settings</h3>
              <p className="text-gray-500 text-sm">Configure how you receive alerts and notifications</p>
            </div>

            <div className="space-y-6">
              {/* Email */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                    <Mail className="w-5 h-5 text-blue-600" />
                  </div>
                  <div>
                    <label className="text-gray-900 font-medium block">Email Notifications</label>
                    <p className="text-gray-500 text-sm">Receive alerts via email</p>
                  </div>
                </div>
                <Switch checked={emailNotifications} onCheckedChange={setEmailNotifications} />
              </div>

              <hr className="border-gray-100" />

              {/* SMS (Eski Telegram Kısmı) */}
              <div>
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-4">
                    <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
                        <Smartphone className="w-5 h-5 text-purple-600" />
                    </div>
                    <div>
                        <label className="text-gray-900 font-medium block">SMS Notifications</label>
                        <p className="text-gray-500 text-sm">Get instant alerts via text message</p>
                    </div>
                    </div>
                    <Switch checked={smsNotifications} onCheckedChange={setSmsNotifications} />
                </div>

                {smsNotifications && (
                    <div className="ml-14 p-4 bg-gray-50 rounded-lg space-y-3 border border-gray-200">
                        <div>
                            <label className="text-sm font-medium text-gray-700 mb-1 block">Phone Number</label>
                            <input type="tel" placeholder="+90 5XX XXX XX XX" className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
                            <p className="text-xs text-gray-500 mt-1">International format required (e.g., +90)</p>
                        </div>
                        <div>
                            <label className="text-sm font-medium text-gray-700 mb-1 block">Provider API Key (Twilio/Netgsm)</label>
                            <input type="password" placeholder="Enter API Key" className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
                        </div>
                    </div>
                )}
              </div>

              <hr className="border-gray-100" />

              {/* Push */}
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
                <Switch checked={pushNotifications} onCheckedChange={setPushNotifications} />
              </div>

              <hr className="border-gray-100" />

              {/* Alert Preferences */}
              <div className="space-y-4 pt-2">
                <h4 className="text-gray-900 font-semibold">Alert Preferences</h4>
                <div className="space-y-3">
                    {[
                        { label: 'Critical Violations', default: true },
                        { label: 'Camera Offline', default: true },
                        { label: 'Model Updates', default: false },
                        { label: 'Daily Reports', default: true }
                    ].map((pref, i) => (
                        <div key={i} className="flex items-center justify-between">
                            <label className="text-gray-700 text-sm">{pref.label}</label>
                            <Switch checked={pref.default} onCheckedChange={()=>{}} />
                        </div>
                    ))}
                </div>
              </div>

              <button className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium flex items-center gap-2 transition-colors">
                <Save className="w-4 h-4" />
                Save Notification Settings
              </button>
            </div>
          </div>
        </div>
      )}

      {/* --- CAMERAS TAB --- */}
      {activeTab === 'cameras' && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 max-w-4xl">
            <div className="mb-6">
              <h3 className="text-lg font-bold text-gray-900">Camera Connection Settings</h3>
              <p className="text-gray-500 text-sm">Configure camera connection parameters</p>
            </div>

            <div className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <label className="text-sm font-medium text-gray-700 mb-1 block">Default Video Protocol</label>
                        <select className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white">
                            <option>RTSP</option>
                            <option>HTTP</option>
                            <option>RTMP</option>
                        </select>
                    </div>
                    <div>
                        <label className="text-sm font-medium text-gray-700 mb-1 block">Frame Rate (FPS)</label>
                        <input type="number" defaultValue={30} className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
                    </div>
                    <div>
                        <label className="text-sm font-medium text-gray-700 mb-1 block">Resolution</label>
                        <select className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white">
                            <option>1920x1080 (Full HD)</option>
                            <option>1280x720 (HD)</option>
                            <option>640x480 (SD)</option>
                        </select>
                    </div>
                    <div>
                        <label className="text-sm font-medium text-gray-700 mb-1 block">Recording Buffer (minutes)</label>
                        <input type="number" defaultValue={5} className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
                    </div>
                </div>

                <hr className="border-gray-100" />

                <div className="space-y-4">
                    <div className="flex items-center justify-between">
                        <label className="text-gray-700 text-sm font-medium">Auto Reconnect</label>
                        <Switch checked={true} onCheckedChange={()=>{}} />
                    </div>
                    <div className="flex items-center justify-between">
                        <label className="text-gray-700 text-sm font-medium">Motion Detection Only</label>
                        <Switch checked={false} onCheckedChange={()=>{}} />
                    </div>
                    <div className="flex items-center justify-between">
                        <label className="text-gray-700 text-sm font-medium">Night Vision Enhancement</label>
                        <Switch checked={true} onCheckedChange={()=>{}} />
                    </div>
                </div>

                <button className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium flex items-center gap-2 transition-colors">
                    <Save className="w-4 h-4" />
                    Save Camera Settings
                </button>
            </div>
        </div>
      )}

      {/* --- USERS TAB --- */}
      {activeTab === 'users' && (
        <div className="space-y-6 max-w-4xl">
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
                <div className="flex items-center justify-between mb-6">
                    <div>
                        <h3 className="text-lg font-bold text-gray-900">User Management</h3>
                        <p className="text-gray-500 text-sm">Manage users and their roles</p>
                    </div>
                    <button className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium flex items-center gap-2 transition-colors">
                        <Users className="w-4 h-4" />
                        Add User
                    </button>
                </div>

                <div className="space-y-3">
                    {[
                        { name: 'Admin User', email: 'admin@safetywatch.com', role: 'Administrator', active: true },
                        { name: 'John Doe', email: 'john@safetywatch.com', role: 'Supervisor', active: true },
                        { name: 'Jane Smith', email: 'jane@safetywatch.com', role: 'Viewer', active: true },
                        { name: 'Mike Johnson', email: 'mike@safetywatch.com', role: 'Viewer', active: false },
                    ].map((user, index) => (
                        <div key={index} className="flex items-center justify-between p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
                            <div className="flex items-center gap-4">
                                <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center text-blue-600">
                                    <Users className="w-5 h-5" />
                                </div>
                                <div>
                                    <p className="text-gray-900 font-medium">{user.name}</p>
                                    <p className="text-gray-500 text-sm">{user.email}</p>
                                </div>
                            </div>
                            <div className="flex items-center gap-6">
                                <div className="flex items-center gap-2 px-3 py-1 bg-gray-100 rounded-full">
                                    <Shield className="w-3 h-3 text-gray-500" />
                                    <span className="text-gray-700 text-xs font-medium">{user.role}</span>
                                </div>
                                <Switch checked={user.active} onCheckedChange={()=>{}} />
                                <button className="text-gray-500 hover:text-blue-600 text-sm font-medium">Edit</button>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
                <div className="mb-6">
                    <h3 className="text-lg font-bold text-gray-900">Role Permissions</h3>
                    <p className="text-gray-500 text-sm">Configure permissions for each role</p>
                </div>
                <div className="space-y-4">
                    {[
                        { role: 'Administrator', permissions: ['Full Access', 'User Management', 'System Settings'] },
                        { role: 'Supervisor', permissions: ['View Violations', 'Manage Cameras', 'Generate Reports'] },
                        { role: 'Viewer', permissions: ['View Cameras', 'View Violations'] },
                    ].map((role, index) => (
                        <div key={index} className="p-4 border border-gray-200 rounded-lg">
                            <div className="flex items-center justify-between mb-3">
                                <h4 className="text-gray-900 font-semibold">{role.role}</h4>
                                <button className="text-blue-600 hover:text-blue-700 text-sm font-medium">Edit Permissions</button>
                            </div>
                            <div className="flex flex-wrap gap-2">
                                {role.permissions.map((permission, pIndex) => (
                                    <span key={pIndex} className="px-3 py-1 bg-blue-50 text-blue-700 rounded-full text-xs font-medium border border-blue-100">
                                        {permission}
                                    </span>
                                ))}
                            </div>
                        </div>
                    ))}
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
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center text-gray-600">
                            {isDarkMode ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
                        </div>
                        <div>
                            <label className="text-gray-900 font-medium block">Dark Mode</label>
                            <p className="text-gray-500 text-sm">Switch between light and dark themes</p>
                        </div>
                    </div>
                    <Switch checked={isDarkMode} onCheckedChange={setIsDarkMode} />
                </div>

                <hr className="border-gray-100" />

                <div>
                    <label className="text-sm font-medium text-gray-700 mb-3 block">Theme Color</label>
                    <div className="grid grid-cols-6 gap-3 max-w-sm">
                        {['bg-blue-600', 'bg-green-600', 'bg-purple-600', 'bg-orange-600', 'bg-red-600', 'bg-pink-600'].map((color, index) => (
                            <button
                                key={index}
                                className={`${color} h-10 rounded-lg border-2 ${index === 0 ? 'border-gray-900 ring-2 ring-gray-200' : 'border-transparent'} hover:scale-105 transition-transform`}
                            />
                        ))}
                    </div>
                </div>

                <hr className="border-gray-100" />

                <div>
                    <label className="text-sm font-medium text-gray-700 mb-2 block">Dashboard Layout</label>
                    <select className="w-full max-w-xs px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white">
                        <option>Compact</option>
                        <option>Standard</option>
                        <option>Spacious</option>
                    </select>
                </div>

                <div className="space-y-4 pt-2">
                    <div className="flex items-center justify-between max-w-xs">
                        <label className="text-gray-700 text-sm font-medium">Enable Animations</label>
                        <Switch checked={true} onCheckedChange={()=>{}} />
                    </div>
                    <div className="flex items-center justify-between max-w-xs">
                        <label className="text-gray-700 text-sm font-medium">Compact Sidebar</label>
                        <Switch checked={false} onCheckedChange={()=>{}} />
                    </div>
                </div>

                <button className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium flex items-center gap-2 transition-colors">
                    <Save className="w-4 h-4" />
                    Save Appearance Settings
                </button>
            </div>
        </div>
      )}
    </div>
  );
}
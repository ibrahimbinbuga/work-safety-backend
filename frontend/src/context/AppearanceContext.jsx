import { createContext, useContext, useState, useEffect } from 'react';
import { useAuth } from './AuthContext';

const DEFAULTS = {
  isDarkMode: false,
  themeColor: 'blue',
};

const COLOR_VARS = {
  blue:   { p50: '#eff6ff', p100: '#dbeafe', p600: '#2563eb', p700: '#1d4ed8', p900: '#1e3a8a' },
  green:  { p50: '#f0fdf4', p100: '#dcfce7', p600: '#16a34a', p700: '#15803d', p900: '#14532d' },
  purple: { p50: '#faf5ff', p100: '#f3e8ff', p600: '#9333ea', p700: '#7e22ce', p900: '#581c87' },
  orange: { p50: '#fff7ed', p100: '#ffedd5', p600: '#ea580c', p700: '#c2410c', p900: '#7c2d12' },
  red:    { p50: '#fef2f2', p100: '#fee2e2', p600: '#dc2626', p700: '#b91c1c', p900: '#7f1d1d' },
  pink:   { p50: '#fdf2f8', p100: '#fce7f3', p600: '#db2777', p700: '#be185d', p900: '#831843' },
};

const AppearanceContext = createContext();

export function AppearanceProvider({ children }) {
  const { user } = useAuth();
  const storageKey = user ? `appearanceSettings_${user.id}` : null;

  const [settings, setSettings] = useState(DEFAULTS);

  // Load user-specific settings when user logs in, reset to defaults on logout
  useEffect(() => {
    if (!storageKey) {
      setSettings(DEFAULTS);
      return;
    }
    try {
      const stored = localStorage.getItem(storageKey);
      setSettings(stored ? { ...DEFAULTS, ...JSON.parse(stored) } : DEFAULTS);
    } catch {
      setSettings(DEFAULTS);
    }
  }, [storageKey]);

  useEffect(() => {
    const { isDarkMode, themeColor } = settings;

    document.documentElement.classList.toggle('dark', isDarkMode);

    const vars = COLOR_VARS[themeColor] ?? COLOR_VARS.blue;
    const root = document.documentElement;
    // In dark mode use neutral gray for active item bg, keep theme color only for text/icons
    root.style.setProperty('--p50',  isDarkMode ? '#374151' : vars.p50);
    root.style.setProperty('--p100', isDarkMode ? '#4b5563' : vars.p100);
    root.style.setProperty('--p600', vars.p600);
    root.style.setProperty('--p700', vars.p700);
    root.style.setProperty('--p900', isDarkMode ? vars.p50  : vars.p900);

    if (storageKey) {
      localStorage.setItem(storageKey, JSON.stringify(settings));
    }
  }, [settings, storageKey]);

  const updateSetting = (key, value) =>
    setSettings(prev => ({ ...prev, [key]: value }));

  return (
    <AppearanceContext.Provider value={{ settings, updateSetting, COLOR_VARS }}>
      {children}
    </AppearanceContext.Provider>
  );
}

export const useAppearance = () => useContext(AppearanceContext);

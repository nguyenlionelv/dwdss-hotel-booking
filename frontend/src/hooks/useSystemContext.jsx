import React, { createContext, useContext, useEffect, useState } from 'react';
import {
  fetchHealthStatus,
  fetchSystemMetadata,
  isDemoModeEnabled,
  setDemoModeEnabled,
} from '../services/apiClient';

const INITIAL_HEALTH = {
  status: 'loading',
  db_connected: false,
  mart_published: false,
  matches_active_dw: false,
  data_version: null,
  dataset_release_id: null,
  is_mock: false,
  demo_mode: false,
  api_error: false,
};

const INITIAL_METADATA = {
  hotel_name: 'City Hotel',
  location: 'Lisbon, Portugal',
  timezone: 'Europe/Lisbon',
  data_version: null,
  dataset_release_id: null,
  date_range: {
    actual_start: null,
    actual_end: null,
    min_date: null,
    max_date: null,
    total_days: 0,
  },
  countries: [
    { code: 'ALL', name: 'All Markets (Worldwide)', booking_count: null },
  ],
  is_mock: false,
  demo_mode: false,
  api_error: false,
};

function getSystemScheme() {
  if (typeof window === 'undefined' || !window.matchMedia) return 'light';
  return window.matchMedia('(prefers-color-scheme: dark)').matches
    ? 'dark'
    : 'light';
}

function getInitialRenderedScheme() {
  if (typeof window === 'undefined') return 'light';
  try {
    const saved = localStorage.getItem('color-scheme');
    if (saved === 'dark' || saved === 'light') return saved;
  } catch (e) {}
  return getSystemScheme();
}

function applyDocumentScheme(renderedScheme, metaValue) {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  root.classList.toggle('dark', renderedScheme === 'dark');
  root.classList.toggle('light', renderedScheme === 'light');
  const meta = document.querySelector('meta[name="color-scheme"]');
  if (meta) {
    meta.content = metaValue;
  }
}

const SystemContext = createContext({
  health: INITIAL_HEALTH,
  metadata: INITIAL_METADATA,
  loading: true,
  demoMode: false,
  toggleDemoMode: () => {},
  refreshSystemStatus: () => {},
  theme: 'light',
  toggleTheme: () => {},
});

export function SystemProvider({ children }) {
  const [health, setHealth] = useState(INITIAL_HEALTH);
  const [metadata, setMetadata] = useState(INITIAL_METADATA);
  const [loading, setLoading] = useState(true);
  const [demoMode, setDemoModeState] = useState(() => isDemoModeEnabled());
  const [theme, setThemeState] = useState(() => getInitialRenderedScheme());

  const loadStatus = async (overrideDemo = demoMode) => {
    setLoading(true);
    try {
      const [h, m] = await Promise.all([
        fetchHealthStatus({ demo: overrideDemo }),
        fetchSystemMetadata({ demo: overrideDemo }),
      ]);
      setHealth(h);
      setMetadata(m);
    } finally {
      setLoading(false);
    }
  };

  const toggleDemoMode = (nextVal) => {
    const target = typeof nextVal === 'boolean' ? nextVal : !demoMode;
    setDemoModeEnabled(target);
    setDemoModeState(target);
    loadStatus(target);
  };

  const toggleTheme = (explicitTarget) => {
    const target =
      explicitTarget === 'dark' || explicitTarget === 'light'
        ? explicitTarget
        : theme === 'dark'
          ? 'light'
          : 'dark';
    const sys = getSystemScheme();
    try {
      if (target === sys) {
        localStorage.removeItem('color-scheme');
        applyDocumentScheme(target, 'light dark');
      } else {
        localStorage.setItem('color-scheme', target);
        applyDocumentScheme(target, target);
      }
    } catch (e) {
      applyDocumentScheme(target, target);
    }
    setThemeState(target);
  };

  useEffect(() => {
    const rendered = getInitialRenderedScheme();
    let saved = null;
    try {
      saved = localStorage.getItem('color-scheme');
    } catch (e) {}
    const metaVal =
      saved === 'dark' || saved === 'light' ? saved : 'light dark';
    applyDocumentScheme(rendered, metaVal);
    setThemeState(rendered);

    if (typeof window === 'undefined' || !window.matchMedia) return undefined;
    const mql = window.matchMedia('(prefers-color-scheme: dark)');

    const handleMediaChange = () => {
      let currentSaved = null;
      try {
        currentSaved = localStorage.getItem('color-scheme');
      } catch (e) {}
      const nextSys = mql.matches ? 'dark' : 'light';
      if (currentSaved === nextSys) {
        try {
          localStorage.removeItem('color-scheme');
        } catch (e) {}
        applyDocumentScheme(nextSys, 'light dark');
        setThemeState(nextSys);
      } else if (currentSaved !== 'dark' && currentSaved !== 'light') {
        applyDocumentScheme(nextSys, 'light dark');
        setThemeState(nextSys);
      }
    };

    const handleStorageChange = (event) => {
      if (event.key === 'color-scheme') {
        const nextVal = event.newValue;
        if (nextVal === 'dark' || nextVal === 'light') {
          applyDocumentScheme(nextVal, nextVal);
          setThemeState(nextVal);
        } else {
          const sys = getSystemScheme();
          applyDocumentScheme(sys, 'light dark');
          setThemeState(sys);
        }
      }
    };

    mql.addEventListener('change', handleMediaChange);
    window.addEventListener('storage', handleStorageChange);
    return () => {
      mql.removeEventListener('change', handleMediaChange);
      window.removeEventListener('storage', handleStorageChange);
    };
  }, []);

  useEffect(() => {
    loadStatus(demoMode);
  }, []);

  return (
    <SystemContext.Provider
      value={{
        health,
        metadata,
        loading,
        demoMode,
        toggleDemoMode,
        refreshSystemStatus: () => loadStatus(demoMode),
        theme,
        toggleTheme,
      }}
    >
      {children}
    </SystemContext.Provider>
  );
}

export function useSystemContext() {
  return useContext(SystemContext);
}

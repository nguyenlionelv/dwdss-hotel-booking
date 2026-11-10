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
  countries: [{ code: 'ALL', name: 'All Markets (Worldwide)', booking_count: null }],
  is_mock: false,
  demo_mode: false,
  api_error: false,
};

const SystemContext = createContext({
  health: INITIAL_HEALTH,
  metadata: INITIAL_METADATA,
  loading: true,
  demoMode: false,
  toggleDemoMode: () => {},
  refreshSystemStatus: () => {},
});

export function SystemProvider({ children }) {
  const [health, setHealth] = useState(INITIAL_HEALTH);
  const [metadata, setMetadata] = useState(INITIAL_METADATA);
  const [loading, setLoading] = useState(true);
  const [demoMode, setDemoModeState] = useState(() => isDemoModeEnabled());

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
      }}
    >
      {children}
    </SystemContext.Provider>
  );
}

export function useSystemContext() {
  return useContext(SystemContext);
}

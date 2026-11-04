import React, { createContext, useContext, useEffect, useState } from 'react';
import { fetchHealthStatus, fetchSystemMetadata } from '../services/apiClient';
import { MOCK_HEALTH, MOCK_METADATA } from '../data/mockData';

const SystemContext = createContext({
  health: MOCK_HEALTH,
  metadata: MOCK_METADATA,
  loading: false,
  refreshSystemStatus: () => {},
});

export function SystemProvider({ children }) {
  const [health, setHealth] = useState({ ...MOCK_HEALTH, is_mock: true });
  const [metadata, setMetadata] = useState({ ...MOCK_METADATA, is_mock: true });
  const [loading, setLoading] = useState(true);

  const loadStatus = async () => {
    setLoading(true);
    try {
      const [h, m] = await Promise.all([fetchHealthStatus(), fetchSystemMetadata()]);
      setHealth(h);
      setMetadata(m);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
  }, []);

  return (
    <SystemContext.Provider
      value={{
        health,
        metadata,
        loading,
        refreshSystemStatus: loadStatus,
      }}
    >
      {children}
    </SystemContext.Provider>
  );
}

export function useSystemContext() {
  return useContext(SystemContext);
}

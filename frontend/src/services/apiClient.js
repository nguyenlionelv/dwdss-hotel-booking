import { MOCK_HEALTH, MOCK_METADATA } from '../data/mockData.js';

const API_BASE_URL = import.meta.env?.VITE_API_BASE_URL || '';

let runtimeDemoMode = import.meta.env?.VITE_DEMO_MODE === 'true';

/**
 * Check whether explicit Demo Mode is enabled.
 * Mock data is ONLY permitted when Demo Mode is explicitly turned on.
 */
export function isDemoModeEnabled(options = {}) {
  if (options?.demo === true) return true;
  if (typeof window !== 'undefined' && window.__DWDSS_DEMO_MODE__ === true) {
    return true;
  }
  return Boolean(runtimeDemoMode);
}

export function setDemoModeEnabled(enabled) {
  runtimeDemoMode = Boolean(enabled);
  if (typeof window !== 'undefined') {
    window.__DWDSS_DEMO_MODE__ = Boolean(enabled);
  }
}

/**
 * Lightweight fetch wrapper with timeout and error handling.
 */
export async function apiRequest(path, options = {}) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), options.timeout || 3500);

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));
      const error = new Error(errorBody.detail || `HTTP ${response.status}`);
      error.status = response.status;
      throw error;
    }

    return await response.json();
  } catch (err) {
    clearTimeout(timeoutId);
    throw err;
  }
}

export async function fetchHealthStatus(options = {}) {
  try {
    const data = await apiRequest('/health', options);
    const releaseId = data.data_version
      ? `v${String(data.data_version).slice(0, 8)}`
      : null;
    return {
      ...data,
      dataset_release_id: data.dataset_release_id || releaseId,
      is_mock: false,
      demo_mode: false,
      api_error: false,
    };
  } catch (err) {
    const errorMessage = err?.message || 'Backend API connection failed.';
    if (isDemoModeEnabled(options)) {
      return {
        ...MOCK_HEALTH,
        status: 'demo',
        db_connected: false,
        mart_published: false,
        matches_active_dw: false,
        message: `DEMO MODE: ${errorMessage}`,
        is_mock: true,
        demo_mode: true,
        api_error: true,
      };
    }
    return {
      status: 'offline',
      db_connected: false,
      mart_published: false,
      matches_active_dw: false,
      data_version: null,
      dw_run_id: null,
      dataset_release_id: null,
      published_at: null,
      message: `Connection error: ${errorMessage}`,
      is_mock: false,
      demo_mode: false,
      api_error: true,
    };
  }
}

export async function fetchSystemMetadata(options = {}) {
  try {
    const data = await apiRequest('/api/metadata', options);
    const releaseId = data.data_version
      ? `v${String(data.data_version).slice(0, 8)}`
      : null;

    const normalizedCountries = Array.isArray(data.countries)
      ? [
          { code: 'ALL', name: 'All Markets (Worldwide)', booking_count: null },
          ...data.countries
            .filter((c) => (c.code || c.country_code) !== 'ALL')
            .map((c) => {
              const code = c.code || c.country_code;
              const rawName = c.name || c.country_name || code;
              return {
                code,
                name: rawName.includes(`(${code})`) ? rawName : `${rawName} (${code})`,
                booking_count: c.booking_count ?? null,
              };
            }),
        ]
      : [];

    return {
      ...data,
      dataset_release_id: data.dataset_release_id || releaseId,
      date_range: {
        actual_start: data.date_range?.actual_start || null,
        actual_end: data.date_range?.actual_end || null,
        min_date: data.date_range?.actual_start || null,
        max_date: data.date_range?.actual_end || null,
        total_days: data.date_range?.total_days || 0,
      },
      countries: normalizedCountries,
      is_mock: false,
      demo_mode: false,
      api_error: false,
    };
  } catch (err) {
    const errorMessage = err?.message || 'Unable to load system metadata.';
    if (isDemoModeEnabled(options)) {
      return {
        ...MOCK_METADATA,
        is_mock: true,
        demo_mode: true,
        api_error: true,
        error_message: errorMessage,
      };
    }
    return {
      hotel_name: 'City Hotel',
      location: 'Lisbon, Portugal',
      timezone: 'Europe/Lisbon',
      data_version: null,
      dataset_release_id: null,
      published_at: null,
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
      api_error: true,
      error_message: errorMessage,
    };
  }
}

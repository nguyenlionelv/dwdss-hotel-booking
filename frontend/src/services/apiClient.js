import { MOCK_HEALTH, MOCK_METADATA } from '../data/mockData';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

/**
 * Lightweight fetch wrapper with timeout and graceful fallback support.
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

export async function fetchHealthStatus() {
  try {
    const data = await apiRequest('/health');
    const releaseId = data.data_version
      ? `v${String(data.data_version).slice(0, 8)}`
      : MOCK_HEALTH.dataset_release_id;
    return {
      ...data,
      dataset_release_id: data.dataset_release_id || releaseId,
      is_mock: false,
    };
  } catch {
    return { ...MOCK_HEALTH, is_mock: true };
  }
}

export async function fetchSystemMetadata() {
  try {
    const data = await apiRequest('/api/metadata');
    const releaseId = data.data_version
      ? `v${String(data.data_version).slice(0, 8)}`
      : MOCK_METADATA.dataset_release_id;

    const normalizedCountries = Array.isArray(data.countries)
      ? [
          { code: 'ALL', name: 'Tất cả quốc gia (All Markets)', booking_count: 79330 },
          ...data.countries
            .filter((c) => (c.code || c.country_code) !== 'ALL')
            .map((c) => {
              const code = c.code || c.country_code;
              const rawName = c.name || c.country_name || code;
              return {
                code,
                name: rawName.includes(`(${code})`) ? rawName : `${rawName} (${code})`,
                booking_count: c.booking_count ?? 1500,
              };
            }),
        ]
      : MOCK_METADATA.countries;

    return {
      ...MOCK_METADATA,
      ...data,
      dataset_release_id: data.dataset_release_id || releaseId,
      date_range: {
        min_date: data.date_range?.actual_start || MOCK_METADATA.date_range.min_date,
        max_date: data.date_range?.actual_end || MOCK_METADATA.date_range.max_date,
        total_days: data.date_range?.total_days || MOCK_METADATA.date_range.total_days,
      },
      countries: normalizedCountries,
      is_mock: false,
    };
  } catch {
    return { ...MOCK_METADATA, is_mock: true };
  }
}

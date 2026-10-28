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
    return { ...data, is_mock: false };
  } catch {
    return { ...MOCK_HEALTH, is_mock: true };
  }
}

export async function fetchSystemMetadata() {
  try {
    const data = await apiRequest('/api/metadata');
    return { ...data, is_mock: false };
  } catch {
    return { ...MOCK_METADATA, is_mock: true };
  }
}

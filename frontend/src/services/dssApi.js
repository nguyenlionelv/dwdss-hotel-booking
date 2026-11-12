import { apiRequest, isDemoModeEnabled } from './apiClient.js';
import { MOCK_DSS_FORECAST } from '../data/mockData.js';

export async function fetchForecastModels(options = {}) {
  if (isDemoModeEnabled(options)) return { models: [{ id: 'demo', label: 'DEMO — static sample', kind: 'daily', default: true }] };
  return apiRequest('/api/dss/models');
}

export async function fetchDemandForecast(params = {}, options = {}) {
  if (isDemoModeEnabled(options)) {
    return { ...MOCK_DSS_FORECAST, forecasts: MOCK_DSS_FORECAST.forecasts || MOCK_DSS_FORECAST.forecast_rows,
      is_mock: true, demo_mode: true };
  }
  const { as_of_date = '2017-08-31', model_name, horizon = 7, budget_units = 100 } = params;
  const query = new URLSearchParams({ as_of_date, horizon });
  if (model_name) query.set('model_name', model_name);
  query.set('budget_units', String(budget_units));
  const response = await apiRequest(`/api/dss/demand-forecast?${query}`);
  return { ...response, is_mock: false, demo_mode: false };
}

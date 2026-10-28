import { apiRequest } from './apiClient';
import { MOCK_DSS_FORECAST } from '../data/mockData';

export async function fetchDemandForecast(params = {}) {
  const { cutoff_date = '2017-08-24', horizon = 7, std_multiplier = 1.0 } = params;

  try {
    const query = new URLSearchParams({ cutoff_date, horizon }).toString();
    const res = await apiRequest(`/api/dss/operations/demand-forecast?${query}`);
    return { ...res, is_mock: false };
  } catch {
    const mean = MOCK_DSS_FORECAST.threshold_rule.rolling_8w_mean;
    const std = MOCK_DSS_FORECAST.threshold_rule.rolling_8w_std;
    const dynamicHighThreshold = Number((mean + std_multiplier * std).toFixed(1));

    const updatedRows = MOCK_DSS_FORECAST.forecast_rows.map((row) => {
      const isHigh = row.predicted_arrivals >= dynamicHighThreshold;
      return {
        ...row,
        demand_level: isHigh ? 'HIGH' : 'NORMAL',
        demand_label: isHigh
          ? row.is_peak
            ? 'Cao (Đỉnh tuần)'
            : `Cao (> ${dynamicHighThreshold})`
          : 'Bình thường',
      };
    });

    const highCount = updatedRows.filter((r) => r.demand_level === 'HIGH').length;

    return {
      ...MOCK_DSS_FORECAST,
      cutoff_date,
      horizon_days: Number(horizon),
      threshold_rule: {
        ...MOCK_DSS_FORECAST.threshold_rule,
        high_demand_threshold: dynamicHighThreshold,
      },
      summary_kpis: {
        ...MOCK_DSS_FORECAST.summary_kpis,
        high_alert_days_count: highCount,
      },
      forecast_rows: updatedRows,
      is_mock: true,
    };
  }
}

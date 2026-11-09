import { apiRequest } from './apiClient';
import { MOCK_DSS_FORECAST, DSS_ACTION_RULES } from '../data/mockData';

export async function fetchDemandForecast(params = {}) {
  const {
    cutoff_date = '2017-08-24',
    as_of_date,
    model_name = 'xgboost_regressor',
    horizon = 7,
    std_multiplier = 1.0,
  } = params;

  const effCutoff = as_of_date || cutoff_date;

  try {
    const query = new URLSearchParams({
      as_of_date: effCutoff,
      cutoff_date: effCutoff,
      model_name,
      horizon,
    }).toString();
    const res = await apiRequest(`/api/dss/demand-forecast?${query}`);
    return { ...res, is_mock: false };
  } catch {
    const mean = MOCK_DSS_FORECAST.dss_threshold_rule.mean_guests_8w;
    const std = MOCK_DSS_FORECAST.dss_threshold_rule.std_guests_8w;
    const dynamicHigh = Number((mean + std_multiplier * std).toFixed(1));
    const dynamicLow = Number(Math.max(0, mean - std_multiplier * std).toFixed(1));

    const selectedModelObj =
      MOCK_DSS_FORECAST.model_comparison.find((m) => m.model_name === model_name) ||
      MOCK_DSS_FORECAST.model_comparison[0];

    const modelOffset =
      model_name === 'seasonal_naive'
        ? -3
        : model_name === 'ridge_regression'
          ? 2
          : model_name === 'random_forest'
            ? -1
            : 0;

    const updatedRows = MOCK_DSS_FORECAST.forecast_rows.map((row, idx) => {
      const basePred = Number((row.predicted_guest_count + modelOffset * ((idx % 2) * 2 - 1)).toFixed(1));
      const predRounded = Math.round(basePred);
      const level =
        basePred >= dynamicHigh
          ? 'HIGH'
          : basePred <= dynamicLow
            ? 'LOW'
            : 'NORMAL';
      return {
        ...row,
        as_of_date: effCutoff,
        model_version: selectedModelObj.model_name,
        predicted_guest_count: basePred,
        predicted_guest_count_display: predRounded,
        predicted_arrivals: predRounded,
        predicted_room_nights: Math.round(basePred * 3.1),
        demand_level: level,
        demand_label: level,
        recommended_action: DSS_ACTION_RULES[level],
      };
    });

    const highCount = updatedRows.filter((r) => r.demand_level === 'HIGH').length;
    const lowCount = updatedRows.filter((r) => r.demand_level === 'LOW').length;
    const normalCount = updatedRows.length - highCount - lowCount;
    const totalGuests7d = Number(
      updatedRows.reduce((s, r) => s + r.predicted_guest_count, 0).toFixed(1)
    );
    const maxPred = Math.max(...updatedRows.map((r) => r.predicted_guest_count));
    const peakDays = updatedRows
      .filter((r) => r.predicted_guest_count === maxPred)
      .map((r) => ({
        forecast_date: r.forecast_date,
        predicted_guest_count: r.predicted_guest_count,
        demand_level: r.demand_level,
      }));

    return {
      ...MOCK_DSS_FORECAST,
      as_of_date: effCutoff,
      cutoff_date: effCutoff,
      model_version: selectedModelObj.model_name,
      model_metadata: {
        ...MOCK_DSS_FORECAST.model_metadata,
        selected_model_family: selectedModelObj.model_label,
        model_version: selectedModelObj.model_name,
        validation_mae: selectedModelObj.overall_mae,
        validation_rmse: selectedModelObj.overall_rmse,
      },
      dss_threshold_rule: {
        ...MOCK_DSS_FORECAST.dss_threshold_rule,
        high_threshold: dynamicHigh,
        low_threshold: dynamicLow,
      },
      threshold_rule: {
        ...MOCK_DSS_FORECAST.threshold_rule,
        high_demand_threshold: dynamicHigh,
        low_demand_threshold: dynamicLow,
      },
      summary: {
        total_predicted_guests_7d: totalGuests7d,
        total_predicted_guests_7d_rounded: Math.round(totalGuests7d),
        peak_forecast_days: peakDays,
        demand_level_counts: { HIGH: highCount, NORMAL: normalCount, LOW: lowCount },
      },
      summary_kpis: {
        ...MOCK_DSS_FORECAST.summary_kpis,
        total_predicted_arrivals: Math.round(totalGuests7d),
        total_predicted_room_nights: updatedRows.reduce((s, r) => s + r.predicted_room_nights, 0),
        peak_day_date: peakDays[0]?.forecast_date || '2017-08-26',
        peak_day_arrivals: Math.round(maxPred),
        high_alert_days_count: highCount,
      },
      forecasts: updatedRows,
      forecast_rows: updatedRows,
      model_comparison: MOCK_DSS_FORECAST.model_comparison.map((m) => ({
        ...m,
        is_selected: m.model_name === model_name,
      })),
      is_mock: true,
    };
  }
}

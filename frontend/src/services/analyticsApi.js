import { apiRequest } from './apiClient';
import {
  ANALYTICS_PRESETS,
  MOCK_ANALYTICS_TREND_BY_GRAIN,
  MOCK_ANALYTICS_PIVOT,
  MOCK_ANALYTICS_IMPACT,
} from '../data/mockData';

function resolvePresetDates(presetId) {
  const found = ANALYTICS_PRESETS.find((p) => p.id === presetId);
  if (found) {
    return { start_date: found.start_date, end_date: found.end_date };
  }
  return { start_date: '2015-07-01', end_date: '2017-08-31' };
}

export async function fetchOperationsTrend(params = {}) {
  const {
    preset = 'full_793',
    grain = 'month',
    country = 'ALL',
    day_type = 'ALL',
    is_holiday = 'ALL',
  } = params;

  const { start_date, end_date } = resolvePresetDates(preset);

  try {
    const queryObj = {
      grain,
      start_date,
      end_date,
      country_code: country,
      day_type,
      is_holiday,
    };
    const query = new URLSearchParams(queryObj).toString();
    const res = await apiRequest(`/api/analytics/operations/trend?${query}`);
    return { ...res, is_mock: false };
  } catch {
    const baseSeries =
      MOCK_ANALYTICS_TREND_BY_GRAIN[grain] || MOCK_ANALYTICS_TREND_BY_GRAIN.month;

    const countryFactor =
      country === 'ALL'
        ? 1.0
        : country === 'PRT'
        ? 0.362
        : country === 'FRA'
        ? 0.164
        : country === 'DEU'
        ? 0.122
        : country === 'GBR'
        ? 0.101
        : 0.074;

    const dayTypeFactor =
      day_type === 'ALL' ? 1.0 : day_type === 'Weekday' ? 0.68 : 0.32;

    const filteredSeries = baseSeries
      .filter((item) => {
        if (is_holiday === 'HOLIDAY_ONLY' && !item.is_holiday_period) return false;
        if (is_holiday === 'NON_HOLIDAY' && item.is_holiday_period) return false;
        return true;
      })
      .map((item) => {
        const multiplier = countryFactor * dayTypeFactor;
        return {
          ...item,
          arrivals: Math.max(12, Math.round(item.arrivals * multiplier)),
          room_nights: Math.max(36, Math.round(item.room_nights * multiplier)),
          active_guests: Math.max(64, Math.round(item.active_guests * multiplier)),
          adr: Number(
            (
              item.adr *
              (country === 'PRT' ? 0.96 : country === 'GBR' ? 1.08 : 1.0)
            ).toFixed(2)
          ),
        };
      });

    const total_arrivals = filteredSeries.reduce((acc, r) => acc + r.arrivals, 0);
    const total_room_nights = filteredSeries.reduce(
      (acc, r) => acc + r.room_nights,
      0
    );
    const total_guests = filteredSeries.reduce(
      (acc, r) => acc + r.active_guests,
      0
    );
    const avg_adr =
      filteredSeries.length > 0
        ? Number(
            (
              filteredSeries.reduce((acc, r) => acc + r.adr, 0) /
              filteredSeries.length
            ).toFixed(2)
          )
        : 0;
    const peakItem =
      filteredSeries.reduce(
        (max, r) => (r.room_nights > (max?.room_nights || 0) ? r : max),
        filteredSeries[0]
      ) || {};

    return {
      grain,
      series: filteredSeries,
      summary: {
        total_arrivals,
        total_room_nights,
        avg_daily_active_guests: Math.round(
          total_guests /
            Math.max(
              1,
              filteredSeries.length *
                (grain === 'month' ? 30 : grain === 'week' ? 7 : 1)
            )
        ),
        avg_adr,
        peak_period: peakItem.period_label || '2016-08',
        peak_room_nights: peakItem.room_nights || 14120,
      },
      is_mock: true,
    };
  }
}

export async function fetchOperationsPivot(params = {}) {
  const { col_dim = 'country', measure = 'room_nights' } = params;
  try {
    const query = new URLSearchParams({ col_dim, measure }).toString();
    const res = await apiRequest(`/api/analytics/operations/pivot?${query}`);
    return { ...res, is_mock: false };
  } catch {
    const matrix =
      col_dim === 'day_type'
        ? MOCK_ANALYTICS_PIVOT.day_type_by_quarter
        : MOCK_ANALYTICS_PIVOT.country_by_quarter;

    const factor =
      measure === 'arrivals' ? 0.31 : measure === 'active_guests' ? 1.96 : 1.0;

    const scaleValues = (vals) =>
      Object.fromEntries(
        Object.entries(vals).map(([k, v]) => [k, Math.round(v * factor)])
      );

    return {
      col_dim,
      measure,
      columns: matrix.columns,
      rows: matrix.rows.map((r) => ({
        ...r,
        values: scaleValues(r.values),
        total: Math.round(r.total * factor),
        children: r.children
          ? r.children.map((c) => ({
              ...c,
              values: scaleValues(c.values),
              total: Math.round(c.total * factor),
            }))
          : undefined,
      })),
      is_mock: true,
    };
  }
}

export async function fetchOperationsImpact(params = {}) {
  try {
    const query = new URLSearchParams(params).toString();
    const suffix = query ? `?${query}` : '';
    const res = await apiRequest(`/api/analytics/operations/impact${suffix}`);
    return { ...res, is_mock: false };
  } catch {
    return { ...MOCK_ANALYTICS_IMPACT, is_mock: true };
  }
}

import { apiRequest, isDemoModeEnabled } from './apiClient.js';
import {
  ANALYTICS_PRESETS,
  MOCK_ANALYTICS_TREND_BY_GRAIN,
  MOCK_ANALYTICS_PIVOT,
  MOCK_ANALYTICS_IMPACT,
} from '../data/mockData.js';

export function resolvePresetDates(presetId) {
  const found = ANALYTICS_PRESETS.find((p) => p.id === presetId);
  if (found) {
    return { start_date: found.start_date, end_date: found.end_date };
  }
  return { start_date: '2015-08-31', end_date: '2017-08-31' };
}

export async function fetchOperationsTrend(params = {}) {
  const {
    preset = 'full_793',
    grain = 'month',
    country = 'ALL',
    day_type = 'ALL',
    is_holiday = 'ALL',
    date_from = null,
    date_to = null,
    demo = false,
  } = params;

  const { start_date, end_date } =
    date_from && date_to
      ? { start_date: date_from, end_date: date_to }
      : resolvePresetDates(preset);

  if (!isDemoModeEnabled({ demo })) {
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
      return { ...res, is_mock: false, demo_mode: false, api_error: false };
    } catch (err) {
      const errorMessage =
        err?.message || 'Failed to fetch operations trend from backend API.';
      if (!isDemoModeEnabled({ demo })) {
        return {
          data_version: null,
          grain,
          filters_applied: {
            start_date,
            end_date,
            grain,
            country_code: country === 'ALL' ? null : country,
            day_type,
          },
          coverage: {
            calendar_days_count: 0,
            booking_complete_days: 0,
            guest_complete_days: 0,
            guest_partial_days: 0,
            overall_guest_status: 'UNAVAILABLE',
            rejected_booking_count: 0,
            guest_ineligible_booking_count: 0,
          },
          summary: {
            total_bookings: 0,
            non_canceled_bookings: 0,
            total_cancellations: 0,
            cancellation_rate: null,
            observed_total_adults: 0,
            observed_total_children: 0,
            observed_total_babies: 0,
            observed_total_guests: 0,
            target_guests: null,
            strict_avg_guests_per_day: null,
            observed_avg_guests_per_day: 0,
            observed_total_stay_nights: 0,
            avg_party_size: null,
            avg_stay_nights: null,
            avg_lead_time: null,
            avg_adr: null,
            peak_demand_days: [],
            total_arrivals: 0,
            total_room_nights: 0,
            avg_daily_active_guests: 0,
            peak_period: '—',
            peak_room_nights: 0,
          },
          series: [],
          is_mock: false,
          demo_mode: false,
          api_error: true,
          error_message: errorMessage,
        };
      }
    }
  }

  // Explicit Demo Mode only
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
              : country === 'UNK'
                ? 0.008
                : 0.074;

  const dayTypeFactor =
    day_type === 'ALL' ? 1.0 : day_type === 'Weekday' ? 0.68 : 0.32;

  const filteredSeries = baseSeries
    .filter((item) => {
      if (is_holiday === 'HOLIDAY_ONLY' && !item.is_holiday_period)
        return false;
      if (is_holiday === 'NON_HOLIDAY' && item.is_holiday_period) return false;
      if (
        start_date &&
        end_date &&
        item.period_start &&
        item.period_end &&
        (item.period_end < start_date || item.period_start > end_date)
      ) {
        return false;
      }
      return true;
    })
    .map((item) => {
      const multiplier = countryFactor * dayTypeFactor;
      const nonCanceled = Math.max(
        8,
        Math.round(item.non_canceled_bookings * multiplier)
      );
      const totalBookings = Math.max(
        nonCanceled,
        Math.round(item.total_bookings * multiplier)
      );
      const totalCancels = totalBookings - nonCanceled;
      const cancelRate =
        totalBookings > 0
          ? Number((totalCancels / totalBookings).toFixed(4))
          : 0;
      const stayNights = Math.max(
        24,
        Math.round(item.observed_total_stay_nights * multiplier)
      );
      const guests = Math.max(
        14,
        Math.round(item.observed_total_guests * multiplier)
      );
      const calDays =
        item.calendar_days_count ||
        (grain === 'month' ? 30 : grain === 'week' ? 7 : 1);
      const avgGuestsDay = Number((guests / Math.max(1, calDays)).toFixed(2));
      const adr = Number(
        (
          item.avg_adr *
          (country === 'PRT' ? 0.96 : country === 'GBR' ? 1.08 : 1.0)
        ).toFixed(2)
      );
      return {
        ...item,
        total_bookings: totalBookings,
        non_canceled_bookings: nonCanceled,
        total_cancellations: totalCancels,
        cancellation_rate: cancelRate,
        observed_total_guests: guests,
        target_guests: item.guest_data_status === 'COMPLETE' ? guests : null,
        strict_avg_guests_per_day:
          item.guest_data_status === 'COMPLETE' ? avgGuestsDay : null,
        observed_avg_guests_per_day: avgGuestsDay,
        observed_total_stay_nights: stayNights,
        avg_party_size:
          nonCanceled > 0 ? Number((guests / nonCanceled).toFixed(2)) : 1.93,
        avg_stay_nights:
          nonCanceled > 0
            ? Number((stayNights / nonCanceled).toFixed(2))
            : 3.05,
        avg_adr: adr,
        arrivals: nonCanceled,
        room_nights: stayNights,
        active_guests: guests,
        adr,
      };
    });

  const total_bookings = filteredSeries.reduce(
    (acc, r) => acc + r.total_bookings,
    0
  );
  const non_canceled_bookings = filteredSeries.reduce(
    (acc, r) => acc + r.non_canceled_bookings,
    0
  );
  const total_cancellations = total_bookings - non_canceled_bookings;
  const cancellation_rate =
    total_bookings > 0
      ? Number((total_cancellations / total_bookings).toFixed(4))
      : 0;
  const observed_total_guests = filteredSeries.reduce(
    (acc, r) => acc + r.observed_total_guests,
    0
  );
  const observed_total_stay_nights = filteredSeries.reduce(
    (acc, r) => acc + r.observed_total_stay_nights,
    0
  );
  const calendar_days_count = filteredSeries.reduce(
    (acc, r) => acc + (r.calendar_days_count || 30),
    0
  );
  const guest_partial_days = filteredSeries.reduce(
    (acc, r) =>
      acc +
      (r.guest_data_status === 'PARTIAL'
        ? Math.max(1, Math.round((r.calendar_days_count || 30) * 0.14))
        : 0),
    0
  );
  const guest_complete_days = Math.max(
    0,
    calendar_days_count - guest_partial_days
  );
  const overall_guest_status = guest_partial_days > 0 ? 'PARTIAL' : 'COMPLETE';
  const observed_avg_guests_per_day =
    calendar_days_count > 0
      ? Number((observed_total_guests / calendar_days_count).toFixed(2))
      : 0;

  const avg_adr =
    filteredSeries.length > 0
      ? Number(
          (
            filteredSeries.reduce(
              (acc, r) => acc + r.avg_adr * r.non_canceled_bookings,
              0
            ) / Math.max(1, non_canceled_bookings)
          ).toFixed(2)
        )
      : 0;

  const peakItem =
    filteredSeries.reduce(
      (max, r) =>
        r.observed_total_guests > (max?.observed_total_guests || 0) ? r : max,
      filteredSeries[0]
    ) || {};

  return {
    data_version: 'DEMO-MOCK',
    grain,
    filters_applied: {
      start_date,
      end_date,
      grain,
      country_code: country === 'ALL' ? null : country,
      day_type,
    },
    coverage: {
      calendar_days_count,
      booking_complete_days: calendar_days_count,
      guest_complete_days,
      guest_partial_days,
      overall_guest_status,
      rejected_booking_count: 0,
      guest_ineligible_booking_count: guest_partial_days > 0 ? 144 : 0,
    },
    summary: {
      total_bookings,
      non_canceled_bookings,
      total_cancellations,
      cancellation_rate,
      observed_total_adults: Math.round(observed_total_guests * 0.91),
      observed_total_children: Math.round(observed_total_guests * 0.08),
      observed_total_babies: Math.max(
        0,
        observed_total_guests - Math.round(observed_total_guests * 0.99)
      ),
      observed_total_guests,
      target_guests:
        overall_guest_status === 'COMPLETE' ? observed_total_guests : null,
      strict_avg_guests_per_day:
        overall_guest_status === 'COMPLETE'
          ? observed_avg_guests_per_day
          : null,
      observed_avg_guests_per_day,
      observed_total_stay_nights,
      avg_party_size:
        non_canceled_bookings > 0
          ? Number((observed_total_guests / non_canceled_bookings).toFixed(2))
          : 1.93,
      avg_stay_nights:
        non_canceled_bookings > 0
          ? Number(
              (observed_total_stay_nights / non_canceled_bookings).toFixed(2)
            )
          : 3.05,
      avg_lead_time: 95.4,
      avg_adr,
      peak_demand_days: [
        {
          full_date: peakItem.period_label || '2016-08',
          observed_total_guests: peakItem.observed_total_guests || 5140,
          observed_total_stay_nights:
            peakItem.observed_total_stay_nights || 8120,
          guest_data_status: peakItem.guest_data_status || 'COMPLETE',
        },
      ],
      total_arrivals: non_canceled_bookings,
      total_room_nights: observed_total_stay_nights,
      avg_daily_active_guests: Math.round(observed_avg_guests_per_day),
      peak_period: peakItem.period_label || '2016-08',
      peak_room_nights: peakItem.observed_total_stay_nights || 8120,
    },
    series: filteredSeries,
    is_mock: true,
    demo_mode: true,
  };
}

export async function fetchOperationsPivot(params = {}) {
  const {
    row_dim = 'quarter',
    col_dim = 'country',
    measure = 'observed_total_guests',
    start_date,
    end_date,
    demo = false,
  } = params;

  if (!isDemoModeEnabled({ demo })) {
    try {
      const queryObj = { row_dim, col_dim, measure };
      if (start_date) queryObj.start_date = start_date;
      if (end_date) queryObj.end_date = end_date;
      const query = new URLSearchParams(queryObj).toString();
      const res = await apiRequest(`/api/analytics/operations/pivot?${query}`);
      return { ...res, is_mock: false, demo_mode: false, api_error: false };
    } catch (err) {
      if (!isDemoModeEnabled({ demo })) {
        return {
          data_version: null,
          row_dim: (row_dim || 'quarter').toLowerCase(),
          col_dim,
          measure,
          columns: [],
          column_defs: [],
          rows: [],
          column_totals: {},
          grand_total: 0,
          is_mock: false,
          demo_mode: false,
          api_error: true,
          error_message:
            err?.message || 'Failed to fetch pivot matrix from backend API.',
        };
      }
    }
  }

  const effStart = start_date || '2015-08-31';
  const effEnd = end_date || '2017-08-31';
  const normRowDim = (row_dim || 'quarter').toLowerCase();
  const isDayTypeCol = col_dim === 'day_type' || col_dim === 'is_weekend';

  const columns = isDayTypeCol
    ? MOCK_ANALYTICS_PIVOT.day_type_by_quarter.columns
    : MOCK_ANALYTICS_PIVOT.country_by_quarter.columns;
  const column_defs = isDayTypeCol
    ? MOCK_ANALYTICS_PIVOT.day_type_by_quarter.column_defs
    : MOCK_ANALYTICS_PIVOT.country_by_quarter.column_defs;

  const colShares = isDayTypeCol
    ? { Weekday: 0.655, Weekend: 0.298, Holiday: 0.047 }
    : {
        PRT: 0.365,
        FRA: 0.212,
        DEU: 0.161,
        GBR: 0.129,
        ESP: 0.095,
        UNK: 0.038,
      };

  const getMonthMeasureVal = (mRow) => {
    if (measure === 'non_canceled_bookings' || measure === 'arrivals') {
      return mRow.non_canceled_bookings ?? mRow.arrivals ?? 0;
    }
    if (measure === 'total_bookings') {
      return mRow.total_bookings ?? 0;
    }
    if (measure === 'observed_total_stay_nights' || measure === 'room_nights') {
      return mRow.observed_total_stay_nights ?? mRow.room_nights ?? 0;
    }
    return mRow.observed_total_guests ?? mRow.active_guests ?? 0;
  };

  const splitIntoCols = (totalVal) => {
    const vals = {};
    let allocated = 0;
    columns.forEach((col, idx) => {
      if (idx === columns.length - 1) {
        vals[col] = Math.max(0, totalVal - allocated);
      } else {
        const v = Math.round(totalVal * (colShares[col] || 0));
        vals[col] = v;
        allocated += v;
      }
    });
    return vals;
  };

  const sumCellMaps = (items) => {
    const acc = Object.fromEntries(columns.map((c) => [c, 0]));
    items.forEach((it) => {
      columns.forEach((c) => {
        acc[c] += it.values[c] || 0;
      });
    });
    return acc;
  };

  const filteredMonths = (MOCK_ANALYTICS_TREND_BY_GRAIN.month || []).filter(
    (m) => !(m.period_end < effStart || m.period_start > effEnd)
  );

  const monthItems = filteredMonths.map((m) => {
    const [yStr, mStr] = m.period_label.split('-');
    const yr = Number(yStr);
    const mn = Number(mStr);
    const qt = Math.ceil(mn / 3);
    const totalVal = getMonthMeasureVal(m);
    const values = splitIntoCols(totalVal);
    return {
      year: yr,
      quarter: qt,
      month: mn,
      quarter_key: `${yr}-Q${qt}`,
      row_key: m.period_label,
      row_label: m.period_label,
      values,
      cells: values,
      total: totalVal,
      row_total: totalVal,
    };
  });

  let rows = [];
  if (normRowDim === 'month') {
    const maxTot = Math.max(...monthItems.map((m) => m.total), 0);
    rows = monthItems.map((m) => ({
      row_key: m.row_key,
      row_label: m.row_label,
      values: m.values,
      cells: m.values,
      total: m.total,
      row_total: m.total,
      is_expandable: false,
      is_highlighted: m.total === maxTot && maxTot > 0,
      children: undefined,
    }));
  } else if (normRowDim === 'year') {
    const yearsMap = new Map();
    monthItems.forEach((m) => {
      const yKey = String(m.year);
      if (!yearsMap.has(yKey)) {
        yearsMap.set(yKey, []);
      }
      yearsMap.get(yKey).push(m);
    });

    const yearRows = Array.from(yearsMap.entries()).map(([yKey, mList]) => {
      const qMap = new Map();
      mList.forEach((m) => {
        if (!qMap.has(m.quarter_key)) qMap.set(m.quarter_key, []);
        qMap.get(m.quarter_key).push(m);
      });
      const qChildren = Array.from(qMap.entries()).map(([qKey, qMonths]) => {
        const qVals = sumCellMaps(qMonths);
        const qTot = Object.values(qVals).reduce((a, b) => a + b, 0);
        return {
          row_key: qKey,
          row_label: qKey,
          values: qVals,
          cells: qVals,
          total: qTot,
          row_total: qTot,
        };
      });
      const yVals = sumCellMaps(qChildren);
      const yTot = Object.values(yVals).reduce((a, b) => a + b, 0);
      return {
        row_key: yKey,
        row_label: yKey,
        values: yVals,
        cells: yVals,
        total: yTot,
        row_total: yTot,
        is_expandable: qChildren.length > 0,
        children: qChildren,
      };
    });

    const maxTot = Math.max(...yearRows.map((r) => r.total), 0);
    rows = yearRows.map((r) => ({
      ...r,
      is_highlighted: r.total === maxTot && maxTot > 0,
    }));
  } else {
    const qMap = new Map();
    monthItems.forEach((m) => {
      if (!qMap.has(m.quarter_key)) qMap.set(m.quarter_key, []);
      qMap.get(m.quarter_key).push(m);
    });

    const qRows = Array.from(qMap.entries()).map(([qKey, qMonths]) => {
      const qVals = sumCellMaps(qMonths);
      const qTot = Object.values(qVals).reduce((a, b) => a + b, 0);
      const children = qMonths.map((m) => ({
        row_key: m.row_key,
        row_label: m.row_label,
        values: m.values,
        cells: m.values,
        total: m.total,
        row_total: m.total,
      }));
      return {
        row_key: qKey,
        row_label: qKey,
        values: qVals,
        cells: qVals,
        total: qTot,
        row_total: qTot,
        is_expandable: children.length > 0,
        children,
      };
    });

    const maxTot = Math.max(...qRows.map((r) => r.total), 0);
    rows = qRows.map((r) => ({
      ...r,
      is_highlighted: r.total === maxTot && maxTot > 0,
    }));
  }

  const column_totals = {};
  columns.forEach((col) => {
    column_totals[col] = rows.reduce((acc, r) => acc + (r.values[col] || 0), 0);
  });
  const grand_total = rows.reduce((acc, r) => acc + r.total, 0);

  return {
    data_version: 'DEMO-MOCK',
    row_dim: normRowDim,
    col_dim,
    measure,
    columns,
    column_defs,
    rows,
    column_totals,
    grand_total,
    is_mock: true,
    demo_mode: true,
  };
}

export async function fetchOperationsImpact(params = {}) {
  const { demo = false, ...queryParams } = params;
  if (!isDemoModeEnabled({ demo })) {
    try {
      const query = new URLSearchParams(queryParams).toString();
      const suffix = query ? `?${query}` : '';
      const res = await apiRequest(`/api/analytics/operations/impact${suffix}`);
      return { ...res, is_mock: false, demo_mode: false, api_error: false };
    } catch (err) {
      if (!isDemoModeEnabled({ demo })) {
        return {
          data_version: null,
          holiday_impact: {
            holiday_days_count: 0,
            non_holiday_days_count: 0,
            holiday_avg_room_nights: 0,
            non_holiday_avg_room_nights: 0,
            lift_pct: 0,
            holiday_avg_arrivals: 0,
            non_holiday_avg_arrivals: 0,
            holiday_avg_adr: 0,
            non_holiday_avg_adr: 0,
            upcoming_holidays: [],
            groups: [],
          },
          weather_impact: {
            bands: [],
            completeness_ratio: 0,
            missing_days: 0,
            insight: '',
          },
          top_countries: [],
          is_mock: false,
          demo_mode: false,
          api_error: true,
          error_message:
            err?.message || 'Failed to fetch impact analysis from backend API.',
        };
      }
    }
  }
  return { ...MOCK_ANALYTICS_IMPACT, is_mock: true, demo_mode: true };
}

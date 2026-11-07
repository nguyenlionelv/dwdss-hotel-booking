import { apiRequest } from './apiClient';
import { MOCK_REPORTS_BY_WEEK, MOCK_DSS_FORECAST } from '../data/mockData';

export async function fetchWeeklyOperationsReport(params = '2017-W32') {
  const queryParams =
    typeof params === 'string' ? { week: params } : { ...params };
  const weekKey = queryParams.week || '2017-W32';

  try {
    const qs = new URLSearchParams(
      Object.entries(queryParams).filter(([, v]) => v != null && v !== '')
    ).toString();
    const res = await apiRequest(`/api/reports/operations/weekly-demand?${qs}`);
    return { ...res, is_mock: false };
  } catch {
    const report =
      MOCK_REPORTS_BY_WEEK[weekKey] || MOCK_REPORTS_BY_WEEK['2017-W32'];
    return { ...report, is_mock: true };
  }
}

export async function fetchCapacitySummaryReport(params = '2017-W32') {
  const queryParams =
    typeof params === 'string' ? { week: params } : { ...params };
  const weekKey = queryParams.week || '2017-W32';

  try {
    const qs = new URLSearchParams(
      Object.entries(queryParams).filter(([, v]) => v != null && v !== '')
    ).toString();
    const res = await apiRequest(
      `/api/reports/operations/capacity-summary?${qs}`
    );
    return { ...res, is_mock: false };
  } catch {
    const report =
      MOCK_REPORTS_BY_WEEK[weekKey] || MOCK_REPORTS_BY_WEEK['2017-W32'];
    const rows = report.daily_rows || [];
    const totGuests = rows.reduce((a, r) => a + r.observed_total_guests, 0);
    const totAdults = rows.reduce((a, r) => a + r.observed_total_adults, 0);
    const totChildren = rows.reduce((a, r) => a + r.observed_total_children, 0);
    const totBabies = rows.reduce((a, r) => a + r.observed_total_babies, 0);
    const totStayNights = rows.reduce((a, r) => a + r.observed_total_stay_nights, 0);
    const totNonCanceled = rows.reduce((a, r) => a + r.non_canceled_bookings, 0);

    const weekdaySN = rows
      .filter((r) => !r.is_weekend)
      .reduce((a, r) => a + r.observed_total_stay_nights, 0);
    const weekendSN = rows
      .filter((r) => r.is_weekend)
      .reduce((a, r) => a + r.observed_total_stay_nights, 0);
    const holidaySN = rows
      .filter((r) => r.is_holiday)
      .reduce((a, r) => a + r.observed_total_stay_nights, 0);

    return {
      report_id: 'DO-R02',
      report_name: 'Operations Capacity Summary',
      hotel_name: 'City Hotel',
      data_version: report.data_version,
      historical_period: {
        start_date: report.period.start_date,
        end_date: report.period.end_date,
        calendar_days_count: rows.length,
        overall_guest_status: report.period.overall_guest_status,
        observed_total_guests: totGuests,
        observed_total_adults: totAdults,
        observed_total_children: totChildren,
        observed_total_babies: totBabies,
        avg_party_size: totNonCanceled > 0 ? Number((totGuests / totNonCanceled).toFixed(2)) : 1.95,
        observed_total_stay_nights: totStayNights,
        avg_stay_nights: totNonCanceled > 0 ? Number((totStayNights / totNonCanceled).toFixed(2)) : 3.4,
        stay_nights_by_arrival_group: {
          weekday_arrival_stay_nights: weekdaySN,
          weekend_arrival_stay_nights: weekendSN,
          holiday_arrival_stay_nights: holidaySN,
        },
      },
      forecast_7d_summary: {
        as_of_date: report.period.end_date,
        horizon_start: MOCK_DSS_FORECAST.forecast_rows[0]?.forecast_date || '2017-08-25',
        horizon_end: MOCK_DSS_FORECAST.forecast_rows[6]?.forecast_date || '2017-08-31',
        model_version: MOCK_DSS_FORECAST.model_version,
        predicted_total_guests_7d: MOCK_DSS_FORECAST.summary.total_predicted_guests_7d,
        demand_level_counts: { HIGH: 2, NORMAL: 4, LOW: 1 },
        forecasts: MOCK_DSS_FORECAST.forecast_rows,
      },
      capacity_summary: report.capacity_summary,
      capacity_disclaimer: report.capacity_disclaimer,
      is_mock: true,
    };
  }
}

export function exportWeeklyReportToCsv(reportData, displayedRows = null) {
  const rowsToExport = displayedRows || reportData?.daily_rows || [];
  if (!rowsToExport.length) return;

  const headers = [
    'full_date',
    'day_of_week',
    'is_weekend',
    'is_holiday',
    'holiday_names',
    'temperature_mean',
    'precipitation',
    'total_bookings',
    'non_canceled_bookings',
    'total_cancellations',
    'cancellation_rate',
    'observed_total_adults',
    'observed_total_children',
    'observed_total_babies',
    'observed_total_guests',
    'target_guests',
    'observed_total_stay_nights',
    'avg_party_size',
    'avg_stay_nights',
    'avg_lead_time',
    'avg_adr',
    'guest_data_status',
  ];

  const rows = rowsToExport.map((r) => [
    r.full_date || r.stay_date,
    r.day_of_week,
    Boolean(r.is_weekend ?? r.day_type === 'Weekend'),
    Boolean(r.is_holiday ?? r.is_pt_holiday),
    Array.isArray(r.holiday_names) && r.holiday_names.length
      ? r.holiday_names.join('; ')
      : r.holiday_local_name || '',
    r.temperature_mean ?? r.weather_temp_mean ?? '',
    r.precipitation ?? r.weather_precip_sum ?? 0,
    r.total_bookings ?? '',
    r.non_canceled_bookings ?? r.arrivals ?? '',
    r.total_cancellations ?? '',
    r.cancellation_rate != null ? (r.cancellation_rate * 100).toFixed(2) + '%' : '',
    r.observed_total_adults ?? '',
    r.observed_total_children ?? '',
    r.observed_total_babies ?? '',
    r.observed_total_guests ?? r.active_guests ?? '',
    r.target_guests ?? r.observed_total_guests ?? '',
    r.observed_total_stay_nights ?? r.room_nights ?? '',
    r.avg_party_size ?? '',
    r.avg_stay_nights ?? '',
    r.avg_lead_time ?? '',
    r.avg_adr ?? r.adr ?? '',
    r.guest_data_status || 'COMPLETE',
  ]);

  const csvContent =
    '\uFEFF' +
    [
      headers.join(','),
      ...rows.map((row) => row.map((cell) => `"${cell}"`).join(',')),
    ].join('\n');

  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  const start = reportData?.period?.start_date || reportData?.period_summary?.start_date || '2017-08-07';
  const end = reportData?.period?.end_date || reportData?.period_summary?.end_date || '2017-08-13';
  link.href = url;
  link.setAttribute('download', `city_hotel_DO-R01_${start}_${end}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

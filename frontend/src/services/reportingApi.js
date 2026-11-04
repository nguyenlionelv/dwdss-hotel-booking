import { apiRequest } from './apiClient';
import { MOCK_REPORTS_BY_WEEK } from '../data/mockData';

export async function fetchWeeklyOperationsReport(weekKey = '2017-W32') {
  try {
    const res = await apiRequest(
      `/api/reports/operations/weekly-demand?week=${encodeURIComponent(weekKey)}`
    );
    return { ...res, is_mock: false };
  } catch {
    const report =
      MOCK_REPORTS_BY_WEEK[weekKey] || MOCK_REPORTS_BY_WEEK['2017-W32'];
    return { ...report, is_mock: true };
  }
}

export async function fetchCapacitySummaryReport(weekKey = '2017-W32') {
  try {
    const res = await apiRequest(
      `/api/reports/operations/capacity-summary?week=${encodeURIComponent(weekKey)}`
    );
    return { ...res, is_mock: false };
  } catch {
    const report =
      MOCK_REPORTS_BY_WEEK[weekKey] || MOCK_REPORTS_BY_WEEK['2017-W32'];
    return { ...report.capacity_summary, is_mock: true };
  }
}

export function exportWeeklyReportToCsv(reportData) {
  if (!reportData || !reportData.daily_rows) return;
  const headers = [
    'Stay Date',
    'Day of Week',
    'Day Type',
    'Arrivals',
    'Departures',
    'Active Stays',
    'Room Nights',
    'Active Guests',
    'ADR (EUR)',
    'PT Holiday',
    'Weather Mean Temp (C)',
    'Weather Status',
  ];

  const rows = reportData.daily_rows.map((r) => [
    r.stay_date,
    r.day_of_week,
    r.day_type,
    r.arrivals,
    r.departures,
    r.active_stays,
    r.room_nights,
    r.active_guests,
    r.adr,
    r.is_pt_holiday ? r.holiday_local_name || 'Holiday' : 'Normal',
    r.weather_temp_mean,
    r.weather_status,
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
  link.href = url;
  link.setAttribute(
    'download',
    `DO-R01_City_Hotel_${reportData.period_summary?.iso_year || 2017}_W${
      reportData.period_summary?.iso_week || 32
    }.csv`
  );
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

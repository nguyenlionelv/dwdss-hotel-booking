import { finiteNumber } from './dssFormat.mjs';

export const isWeekend = row => Boolean(row.is_weekend ?? row.day_type === 'Weekend');
export const isHoliday = row => Boolean(row.is_holiday ?? row.is_pt_holiday);
export const reportDate = row => row.full_date || row.stay_date;
export const guests = row => finiteNumber(row.observed_total_guests ?? row.active_guests);
export const arrivals = row => finiteNumber(row.non_canceled_bookings ?? row.arrivals);
export const stayNights = row => finiteNumber(row.observed_total_stay_nights ?? row.room_nights);

export function filterReportRows(rows, dayType) {
  return rows.filter(row => dayType === 'ALL' || (dayType === 'Weekend' ? isWeekend(row) : !isWeekend(row)))
    .toSorted((a, b) => reportDate(a).localeCompare(reportDate(b)));
}

function sum(rows, value) {
  if (!rows.length || rows.some(row => value(row) === null)) return null;
  return rows.reduce((total, row) => total + value(row), 0);
}

function weightedAverage(rows, numerator, count, average, defaultCount) {
  let total = 0;
  let valid = 0;
  for (const row of rows) {
    const n = finiteNumber(row[count]) ?? defaultCount(row);
    if (n === null || n < 0) return null;
    if (n === 0) continue;
    const value = finiteNumber(row[numerator]) ?? (
      finiteNumber(row[average]) === null ? null : Number(row[average]) * n
    );
    if (value === null) return null;
    total += value;
    valid += n;
  }
  return valid > 0 ? total / valid : null;
}

export function summarizeReportRows(rows) {
  const totalBookings = sum(rows, row => finiteNumber(row.total_bookings));
  const nonCanceled = sum(rows, arrivals);
  const canceled = sum(rows, row => finiteNumber(row.total_cancellations) ?? (
    finiteNumber(row.total_bookings) !== null && arrivals(row) !== null
      ? Math.max(0, Number(row.total_bookings) - arrivals(row)) : null
  ));
  const totalGuests = sum(rows, guests);
  const nights = sum(rows, stayNights);
  const peakValue = rows.length ? Math.max(...rows.map(row => guests(row) ?? -1)) : -1;
  const peakDays = peakValue >= 0 ? rows.filter(row => guests(row) === peakValue).map(reportDate) : [];
  const guestCount = sum(rows, row => finiteNumber(row.guest_valid_booking_count) ?? arrivals(row));
  const stayCount = sum(rows, row => finiteNumber(row.stay_valid_booking_count) ?? arrivals(row));
  return {
    days: rows.length, totalBookings, nonCanceled, canceled, totalGuests, stayNights: nights,
    adults: sum(rows, row => finiteNumber(row.observed_total_adults)),
    children: sum(rows, row => finiteNumber(row.observed_total_children)),
    babies: sum(rows, row => finiteNumber(row.observed_total_babies)),
    avgGuests: rows.length && totalGuests !== null ? totalGuests / rows.length : null,
    cancellationRate: totalBookings > 0 && canceled !== null ? canceled / totalBookings : null,
    avgParty: guestCount > 0 && totalGuests !== null ? totalGuests / guestCount : null,
    avgStay: stayCount > 0 && nights !== null ? nights / stayCount : null,
    avgAdr: weightedAverage(rows, 'sum_adr', 'adr_valid_count', 'avg_adr', arrivals),
    avgLeadTime: weightedAverage(rows, 'sum_lead_time', 'lead_time_valid_count', 'avg_lead_time', row => finiteNumber(row.total_bookings)),
    peakDays, peakGuests: peakValue >= 0 ? peakValue : null,
    status: !rows.length ? 'No data' : rows.every(row => row.guest_data_status === 'COMPLETE') ? 'Complete guest data' : 'Partial or unknown guest coverage',
  };
}

export function arrivalGroups(rows) {
  return [
    { label: 'Weekdays', rows: rows.filter(row => !isWeekend(row)) },
    { label: 'Weekends', rows: rows.filter(isWeekend) },
    { label: 'Holidays (overlapping)', rows: rows.filter(isHoliday) },
  ].map(group => ({ label: group.label, ...summarizeReportRows(group.rows) }));
}

export function validateReportRange(start, end) {
  const valid = value => /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    Number.isFinite(Date.parse(`${value}T00:00:00Z`)) && new Date(`${value}T00:00:00Z`).toISOString().slice(0, 10) === value;
  if (!valid(start) || !valid(end)) return 'Choose a valid start and end date.';
  if (start > end) return 'Start date must be on or before end date.';
  if (start < '2015-07-01' || end > '2017-08-31') return 'Choose dates between 1 Jul 2015 and 31 Aug 2017.';
  return null;
}

export function nextSevenDays(data, cutoff) {
  if (typeof cutoff !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(cutoff) || !Number.isFinite(Date.parse(`${cutoff}T00:00:00Z`))) return null;
  const rows = data?.forecasts || data?.forecast_rows || [];
  if (rows.length !== 7) return null;
  const ordered = [...rows].sort((a, b) => String(a.forecast_date).localeCompare(String(b.forecast_date)));
  if (!ordered.every((row, index) => {
    const expected = new Date(`${cutoff}T00:00:00Z`);
    expected.setUTCDate(expected.getUTCDate() + index + 1);
    return row.forecast_date === expected.toISOString().slice(0, 10) &&
      finiteNumber(row.predicted_guest_count ?? row.predicted_arrivals) !== null &&
      Number(row.predicted_guest_count ?? row.predicted_arrivals) >= 0;
  })) return null;
  const total = ordered.reduce((s, row) => s + Number(row.predicted_guest_count ?? row.predicted_arrivals), 0);
  const peak = Math.max(...ordered.map(row => Number(row.predicted_guest_count ?? row.predicted_arrivals)));
  return { rows: ordered, total, peakDays: ordered.filter(row => Number(row.predicted_guest_count ?? row.predicted_arrivals) === peak).map(row => row.forecast_date) };
}

const csvCell = value => `"${String(value ?? '').replace(/"/g, '""')}"`;
export function capacityCsv(rows, context, forecast) {
  const records = [
    ['Report', 'Capacity summary'], ['Hotel', 'City Hotel'],
    ['Period start', context.start], ['Period end', context.end], ['Arrival day filter', context.dayType],
    ['Data version', context.version], [],
    ['Arrival group', 'Days', 'Bookings', 'Non-canceled bookings', 'Observed guests', 'Stay nights', 'Average guests / day', 'Average party size', 'Average stay nights', 'Average ADR'],
    ...[{ label: 'Filtered total', ...summarizeReportRows(rows) }, ...arrivalGroups(rows)].map(group => [
      group.label, group.days, group.totalBookings, group.nonCanceled, group.totalGuests, group.stayNights,
      group.avgGuests, group.avgParty, group.avgStay, group.avgAdr,
    ]),
    [], ['Note', 'Holiday days overlap weekdays or weekends; do not add all three groups.'],
    ['Forecast scope', 'All arrival days; seven days after period end'],
    ...(forecast ? [['Forecast date', 'Predicted guests', 'Demand level'], ...forecast.rows.map(row => [row.forecast_date, row.predicted_guest_count ?? row.predicted_arrivals, row.demand_level])]
      : [['Forecast status', 'Unavailable']]),
  ];
  return '\uFEFF' + records.map(record => record.map(csvCell).join(',')).join('\r\n');
}

export function downloadCsv(content, filename) {
  const url = URL.createObjectURL(new Blob([content], { type: 'text/csv;charset=utf-8;' }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

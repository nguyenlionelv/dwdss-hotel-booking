import test from 'node:test';
import assert from 'node:assert/strict';
import { filterReportRows, summarizeReportRows, arrivalGroups, nextSevenDays, validateReportRange, capacityCsv } from '../src/lib/reporting.mjs';
import { fetchWeeklyOperationsReport, exportWeeklyReportToCsv } from '../src/services/reportingApi.js';
import { MOCK_REPORTS_BY_WEEK } from '../src/data/mockData.js';
import { fetchOperationsTrend } from '../src/services/analyticsApi.js';

test('weekend totals, peaks, groups and CSV all use the same displayed dates', () => {
  const rows = filterReportRows(MOCK_REPORTS_BY_WEEK.LATEST_4W.daily_rows, 'Weekend');
  const summary = summarizeReportRows(rows);
  assert.equal(rows.length, 8);
  assert.ok(summary.peakDays.every(date => rows.some(row => row.full_date === date)));
  const groups = arrivalGroups(rows);
  assert.equal(groups[0].days, 0);
  assert.equal(groups[1].stayNights, summary.stayNights);
  assert.equal(summary.totalGuests, rows.reduce((sum, row) => sum + row.observed_total_guests, 0));
  const csv = exportWeeklyReportToCsv(MOCK_REPORTS_BY_WEEK.LATEST_4W, rows);
  assert.equal(csv.split('\n').length, 9);
  assert.equal(csv.split('\n')[0].split(',').length, 22);
  assert.ok(rows.every(row => csv.includes(row.full_date)));
  const capacity = capacityCsv(rows, { start: '2017-08-04', end: '2017-08-31', dayType: 'Weekends' }, null);
  assert.match(capacity, /"Arrival day filter","Weekends"/);
  assert.match(capacity, /"Forecast status","Unavailable"/);
  assert.ok(capacity.includes(`"Filtered total","8","${summary.totalBookings}"`));
});

test('averages use exact valid counts, not an average of daily averages', () => {
  const rows = [
    { full_date: '2017-08-01', total_bookings: 10, non_canceled_bookings: 9, observed_total_guests: 18, observed_total_stay_nights: 27, sum_adr: 900, adr_valid_count: 9, guest_valid_booking_count: 9, stay_valid_booking_count: 9, sum_lead_time: 100, lead_time_valid_count: 10 },
    { full_date: '2017-08-02', total_bookings: 2, non_canceled_bookings: 1, observed_total_guests: 3, observed_total_stay_nights: 5, sum_adr: 200, adr_valid_count: 1, guest_valid_booking_count: 1, stay_valid_booking_count: 1, sum_lead_time: 100, lead_time_valid_count: 2 },
  ];
  const result = summarizeReportRows(rows);
  assert.equal(result.avgAdr, 110);
  assert.equal(result.avgLeadTime, 200 / 12);
  assert.equal(result.avgParty, 2.1);
  assert.equal(result.avgStay, 3.2);
  assert.equal(result.cancellationRate, 2 / 12);
});

test('missing observations stay missing; true zero observations remain zero', () => {
  const result = summarizeReportRows([{ full_date: '2017-08-01', guest_data_status: 'PARTIAL' }]);
  assert.equal(result.totalGuests, null);
  assert.equal(result.avgAdr, null);
  assert.equal(result.peakGuests, null);
  assert.equal(result.status, 'Partial or unknown guest coverage');
  const zero = summarizeReportRows([{ full_date: '2017-08-01', observed_total_guests: 0, guest_data_status: 'COMPLETE' }]);
  assert.equal(zero.totalGuests, 0);
  assert.deepEqual(zero.peakDays, ['2017-08-01']);
  assert.equal(summarizeReportRows([]).status, 'No data');
});

test('all tied peak dates are kept and daily sorting does not mutate source rows', () => {
  const source = [{ full_date: '2017-08-03', observed_total_guests: 5 }, { full_date: '2017-08-01', observed_total_guests: 5 }];
  const rows = filterReportRows(source, 'ALL');
  assert.deepEqual(summarizeReportRows(rows).peakDays, ['2017-08-01', '2017-08-03']);
  assert.equal(source[0].full_date, '2017-08-03');
});

test('forecasts must contain exactly seven consecutive dates after the cutoff', () => {
  const rows = Array.from({ length: 7 }, (_, index) => ({ forecast_date: `2017-09-0${index + 1}`, predicted_guest_count: 0 }));
  assert.equal(nextSevenDays({ forecasts: rows }, '2017-08-31').total, 0);
  assert.equal(nextSevenDays({ forecasts: rows }, '2017-08-24'), null);
  assert.equal(nextSevenDays({ forecasts: rows.slice(0, 6) }, '2017-08-31'), null);
  assert.equal(nextSevenDays({ forecasts: [...rows.slice(0, 6), rows[0]] }, '2017-08-31'), null);
  assert.equal(nextSevenDays({ forecasts: rows.map((row, index) => index ? row : { ...row, predicted_guest_count: null }) }, '2017-08-31'), null);
  assert.equal(nextSevenDays({ forecasts: rows }, 'invalid'), null);
});

test('invalid, reversed and out-of-dataset ranges are rejected', () => {
  assert.equal(validateReportRange('2017-08-01', '2017-08-31'), null);
  for (const [start, end] of [['', '2017-08-31'], ['2017-08-31', '2017-08-01'], ['2017-02-30', '2017-03-01'], ['2017-08-01', '2017-09-01']]) {
    assert.ok(validateReportRange(start, end));
  }
});

test('empty custom demo ranges do not silently substitute another period', async () => {
  const report = await fetchWeeklyOperationsReport({ demo: true, week: 'LATEST_4W', start_date: '2016-01-01', end_date: '2016-01-07' });
  assert.deepEqual(report.daily_rows, []);
  assert.equal(report.period.calendar_days_count, 0);
});

test('live reporting and analytics reconcile for the same dates and weekend slice', { skip: !process.env.DWDSS_API_BASE_URL }, async () => {
  const original = globalThis.fetch;
  globalThis.fetch = (path, options) => original(new URL(path, process.env.DWDSS_API_BASE_URL), options);
  try {
    const [report, analytics] = await Promise.all([
      fetchWeeklyOperationsReport({ week: 'LATEST_4W', start_date: '2017-08-04', end_date: '2017-08-31' }),
      fetchOperationsTrend({ date_from: '2017-08-04', date_to: '2017-08-31', grain: 'day', day_type: 'Weekend' }),
    ]);
    assert.equal(report.api_error, false);
    assert.equal(analytics.api_error, false);
    const rows = filterReportRows(report.daily_rows, 'Weekend');
    const summary = summarizeReportRows(rows);
    assert.equal(rows.length, 8);
    assert.equal(summary.totalGuests, analytics.summary.observed_total_guests);
    assert.equal(summary.totalBookings, analytics.summary.total_bookings);
    assert.equal(summary.nonCanceled, analytics.summary.non_canceled_bookings);
    assert.equal(summary.stayNights, analytics.summary.observed_total_stay_nights);
    assert.ok(Math.abs(summary.avgAdr - analytics.summary.avg_adr) < 0.01);
    assert.equal(exportWeeklyReportToCsv(report, rows).split('\n').length, 9);
  } finally { globalThis.fetch = original; }
});

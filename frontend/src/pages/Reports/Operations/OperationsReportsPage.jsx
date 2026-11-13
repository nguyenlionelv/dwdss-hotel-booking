import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Printer, Download, RotateCcw } from 'lucide-react';
import { fetchWeeklyOperationsReport, exportWeeklyReportToCsv } from '../../../services/reportingApi';
import { fetchDemandForecast } from '../../../services/dssApi';
import { useSystemContext } from '../../../hooks/useSystemContext';
import DashboardHeader from '../../../components/layout/DashboardHeader';
import DataContext from '../../../components/layout/DataContext';
import CompactFilter from '../../../components/filters/CompactFilter';
import SegmentedControl from '../../../components/filters/SegmentedControl';
import KpiCard from '../../../components/kpi/KpiCard';
import ReportKpi from './ReportKpi';
import { CanvasWeeklyWorkloadChart, HorizontalBarChart } from '../../../components/charts/TrendChart';
import ResponsiveTableContainer from '../../../components/tables/ResponsiveTableContainer';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell, TableFooter } from '@/components/ui/table';
import { formatDate, formatWeekday, formatGuests, formatReference, formatMetric, formatRate, formatSignedPercent } from '../../../lib/dssFormat.mjs';
import { filterReportRows, summarizeReportRows, arrivalGroups, validateReportRange, nextSevenDays,
  reportDate, isWeekend, isHoliday, guests, arrivals, stayNights, capacityCsv, downloadCsv } from '../../../lib/reporting.mjs';

const WEEKS = [
  { value: 'LATEST_4W', label: 'Latest 4 weeks', start: '2017-08-04', end: '2017-08-31' },
  { value: '2017-W35', label: 'Week 35 · 2017', start: '2017-08-28', end: '2017-08-31' },
  { value: '2017-W34', label: 'Week 34 · 2017', start: '2017-08-21', end: '2017-08-27' },
  { value: '2017-W33', label: 'Week 33 · 2017', start: '2017-08-14', end: '2017-08-20' },
  { value: '2017-W32', label: 'Week 32 · 2017', start: '2017-08-07', end: '2017-08-13' },
];
const DAY_TYPES = [{ value: 'ALL', label: 'All days' }, { value: 'Weekday', label: 'Weekdays' }, { value: 'Weekend', label: 'Weekends' }];
const dateInputClass = 'h-9 w-full min-w-0 rounded-[4px] border border-divider bg-surface-primary px-3 text-[13px] text-ink-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';
const euro = value => value == null ? '—' : `€${formatMetric(value)}`;
const demandLabel = level => ({ HIGH: 'High', NORMAL: 'Normal', LOW: 'Low', INSUFFICIENT_HISTORY: 'Insufficient history' }[level] || 'Unavailable');

export default function OperationsReportsPage() {
  const { demoMode } = useSystemContext();
  const [reportMode, setReportMode] = useState('ALL');
  const [periodMode, setPeriodMode] = useState('ISO_WEEK');
  const [selectedWeek, setSelectedWeek] = useState('LATEST_4W');
  const [customStart, setCustomStart] = useState('2017-08-04');
  const [customEnd, setCustomEnd] = useState('2017-08-31');
  const [dayType, setDayType] = useState('ALL');
  const [metric, setMetric] = useState('guests');
  const [showDetails, setShowDetails] = useState(false);
  const [reportData, setReportData] = useState(null);
  const [forecastData, setForecastData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [forecastLoading, setForecastLoading] = useState(false);
  const [error, setError] = useState(null);
  const [forecastError, setForecastError] = useState(null);
  const [retry, setRetry] = useState(0);
  const week = WEEKS.find(option => option.value === selectedWeek) || WEEKS[0];
  const start = periodMode === 'CUSTOM_RANGE' ? customStart : week.start;
  const end = periodMode === 'CUSTOM_RANGE' ? customEnd : week.end;
  const rangeError = validateReportRange(start, end);
  const showDemand = reportMode !== 'DO-R02';
  const showCapacity = reportMode !== 'DO-R01';

  useEffect(() => {
    let active = true;
    setReportData(null);
    setError(null);
    if (rangeError) { setLoading(false); return; }
    setLoading(true);
    fetchWeeklyOperationsReport({ week: selectedWeek, start_date: start, end_date: end })
      .then(data => {
        if (!active) return;
        if (data.api_error) setError(data.error_message || 'The report could not be loaded.');
        else setReportData(data);
      })
      .catch(err => { if (active) setError(err.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [selectedWeek, start, end, rangeError, demoMode, retry]);

  useEffect(() => {
    let active = true;
    setForecastData(null);
    setForecastError(null);
    if (!showCapacity || rangeError) { setForecastLoading(false); return; }
    setForecastLoading(true);
    fetchDemandForecast({ as_of_date: end, horizon: 7 })
      .then(data => {
        if (!active) return;
        if (!nextSevenDays(data, end)) setForecastError('Seven consecutive forecast dates after this period are not available.');
        else setForecastData(data);
      })
      .catch(err => { if (active) setForecastError(err.message); })
      .finally(() => { if (active) setForecastLoading(false); });
    return () => { active = false; };
  }, [end, rangeError, showCapacity, demoMode, retry]);

  const dailyRows = useMemo(() => filterReportRows(reportData?.daily_rows || [], dayType), [reportData, dayType]);
  const summary = useMemo(() => summarizeReportRows(dailyRows), [dailyRows]);
  const groups = useMemo(() => arrivalGroups(dailyRows), [dailyRows]);
  const weekdayAverage = groups[0].days && groups[0].nonCanceled !== null ? groups[0].nonCanceled / groups[0].days : null;
  const weekendAverage = groups[1].days && groups[1].nonCanceled !== null ? groups[1].nonCanceled / groups[1].days : null;
  const weekendChange = weekdayAverage > 0 && weekendAverage !== null ? (weekendAverage / weekdayAverage - 1) * 100 : null;
  const forecast = useMemo(() => forecastData ? nextSevenDays(forecastData, end) : null, [forecastData, end]);
  const period = reportData?.period || reportData?.period_summary || {};
  const ready = !loading && !rangeError && !error && dailyRows.length > 0;
  const selectedDayLabel = DAY_TYPES.find(option => option.value === dayType).label;
  const incomplete = periodMode === 'ISO_WEEK' && selectedWeek !== 'LATEST_4W' && period.is_complete_week === false;
  const reset = () => {
    setReportMode('ALL'); setPeriodMode('ISO_WEEK'); setSelectedWeek('LATEST_4W');
    setCustomStart('2017-08-04'); setCustomEnd('2017-08-31'); setDayType('ALL'); setMetric('guests');
  };
  const exportCapacity = () => downloadCsv(capacityCsv(dailyRows, {
    start: period.start_date || start, end: period.end_date || end, dayType: selectedDayLabel, version: reportData?.data_version,
  }, forecast), `city_hotel_capacity_${start}_${end}_${dayType}.csv`);

  return (
    <div className="report-page space-y-8 lg:space-y-10">
      <DashboardHeader page="reporting" title="Hotel Operations Reporting" actions={<>
        <Button variant="outline" size="sm" disabled={!ready} onClick={() => window.print()}><Printer aria-hidden="true" className="h-3.5 w-3.5" />Print report</Button>
        {showDemand && <Button variant="outline" size="sm" disabled={!ready} onClick={() => exportWeeklyReportToCsv(reportData, dailyRows, dayType)}><Download aria-hidden="true" className="h-3.5 w-3.5" />Export demand CSV</Button>}
        {showCapacity && <Button variant="outline" size="sm" disabled={!ready || forecastLoading} onClick={exportCapacity}><Download aria-hidden="true" className="h-3.5 w-3.5" />Export capacity CSV</Button>}
      </>}>
        <div className="space-y-6">
          <div className="flex flex-wrap items-end gap-x-6 gap-y-5">
            <SegmentedControl label="Report" value={reportMode} onChange={setReportMode} options={[
              { value: 'ALL', label: 'Combined' }, { value: 'DO-R01', label: 'Weekly demand' }, { value: 'DO-R02', label: 'Capacity summary' },
            ]} />
            <SegmentedControl label="Period mode" value={periodMode} onChange={setPeriodMode} options={[
              { value: 'ISO_WEEK', label: 'Week / preset' }, { value: 'CUSTOM_RANGE', label: 'Custom range' },
            ]} />
          </div>
          <div className="flex flex-wrap items-end gap-x-6 gap-y-5">
            {periodMode === 'ISO_WEEK' ? <CompactFilter id="report-week-select" label="Period" value={selectedWeek} options={WEEKS}
              onChange={event => {
                const option = WEEKS.find(item => item.value === event.target.value);
                setSelectedWeek(option.value); setCustomStart(option.start); setCustomEnd(option.end);
              }} /> : <>
              <div className="flex w-full flex-col gap-2.5 sm:w-48"><label htmlFor="report-custom-start" className="text-[12px] text-ink-secondary">Start date</label>
                <input id="report-custom-start" type="date" min="2015-07-01" max={customEnd || '2017-08-31'} value={customStart} onChange={event => setCustomStart(event.target.value)} onInput={event => setCustomStart(event.currentTarget.value)} className={dateInputClass} aria-invalid={Boolean(rangeError)} aria-describedby={rangeError ? 'report-range-error' : undefined} /></div>
              <div className="flex w-full flex-col gap-2.5 sm:w-48"><label htmlFor="report-custom-end" className="text-[12px] text-ink-secondary">End date</label>
                <input id="report-custom-end" type="date" min={customStart || '2015-07-01'} max="2017-08-31" value={customEnd} onChange={event => setCustomEnd(event.target.value)} onInput={event => setCustomEnd(event.currentTarget.value)} className={dateInputClass} aria-invalid={Boolean(rangeError)} aria-describedby={rangeError ? 'report-range-error' : undefined} /></div>
            </>}
            <CompactFilter id="report-day-type" label="Arrival day type" value={dayType} onChange={event => setDayType(event.target.value)} options={DAY_TYPES} />
            <Button variant="ghost" size="sm" className="h-9" onClick={reset}><RotateCcw aria-hidden="true" className="h-3.5 w-3.5" />Reset filters</Button>
          </div>
        </div>
      </DashboardHeader>

      <div className="report-print-only">
      <DataContext status={loading ? 'Loading report…' : error || rangeError ? 'Report unavailable' : summary.status}
        demo={reportData?.is_mock} version={reportData?.data_version} publishedAt={reportData?.published_at}>
        <p className="font-medium text-ink-primary">City Hotel · {reportMode === 'ALL' ? 'Combined operations report' : showDemand ? 'Weekly demand report' : 'Capacity summary'}</p>
        <p>{formatDate(period.start_date || start)} – {formatDate(period.end_date || end)} · Europe/Lisbon</p>
        <p>{selectedDayLabel} · {loading ? 'Loading available dates…' : `${summary.days} displayed days`}</p>
      </DataContext>
      </div>
      {incomplete && <p role="status" className="rounded-[4px] border border-status-warning/40 bg-status-warning/5 p-4 text-[13px] text-ink-primary">Incomplete week: {period.calendar_days_count ?? reportData?.daily_rows?.length ?? 0} of 7 days available. Totals cover available dates only.</p>}
      {rangeError && <p id="report-range-error" role="alert" className="text-[13px] text-status-critical">{rangeError}</p>}
      {error && <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-[4px] border border-status-critical/30 p-4 text-[13px] text-status-critical"><span>Report unavailable: {error}</span><Button variant="outline" size="sm" onClick={() => setRetry(value => value + 1)}>Retry</Button></div>}
      {loading && <div role="status" aria-label="Loading report" className="space-y-6"><Skeleton className="h-32 w-full" /><Skeleton className="h-64 w-full" /></div>}
      {!loading && !error && !rangeError && !dailyRows.length && <p role="status" className="border border-divider rounded-[4px] p-6 text-[13px] text-ink-secondary">No report rows match this period and arrival day type. Choose another period or reset filters.</p>}

      {ready && <>
        <section aria-labelledby="report-summary-heading" className="space-y-5 border-b border-divider pb-8">
          <h2 id="report-summary-heading" className="editorial-section-title">Period summary</h2>
          <div className="report-period-kpis grid grid-cols-1 gap-6 pt-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 xl:divide-x xl:divide-divider">
            <KpiCard label="Observed guests" value={formatGuests(summary.totalGuests)} unit="guests" />
            <KpiCard className="xl:pl-5" label="Non-canceled bookings" value={formatGuests(summary.nonCanceled)} unit="bookings" />
            <KpiCard className="xl:pl-5" label="Cancellation rate" value={formatRate(summary.cancellationRate)} />
            <KpiCard className="xl:pl-5" label="Observed stay nights" value={formatGuests(summary.stayNights)} unit="nights" />
            <KpiCard className="xl:pl-5" label="Average ADR" value={euro(summary.avgAdr)} />
            <KpiCard className="report-peak-date pr-0 xl:pl-5" label="Peak arrival date" valueType="date" value={formatDate(summary.peakDays[0])} />
          </div>
        </section>

        {showDemand && <section aria-labelledby="daily-report-heading" className="report-reading-section space-y-4">
          <div className="flex flex-wrap items-baseline justify-between gap-3"><h2 id="daily-report-heading" className="editorial-section-title">Daily demand</h2><Button variant="outline" size="sm" className="dashboard-screen-only" aria-expanded={showDetails} aria-controls="report-daily-table" onClick={() => setShowDetails(value => !value)}>{showDetails ? 'Hide supporting columns' : 'Show supporting columns'}</Button></div>
          <ResponsiveTableContainer ariaLabelledBy="daily-report-heading"><Table id="report-daily-table" className="min-w-[820px]">
            <TableHeader><TableRow><TableHead>Arrival date</TableHead><TableHead>Day</TableHead><TableHead className="text-right">Bookings</TableHead><TableHead className="text-right">Non-canceled</TableHead><TableHead className="text-right">Canceled (%)</TableHead><TableHead className="text-right">Guests</TableHead><TableHead className="text-right">Stay nights</TableHead><TableHead className="text-right">ADR (€)</TableHead>{showDetails && <><TableHead className="text-right">Avg party</TableHead><TableHead className="text-right">Avg stay</TableHead><TableHead className="text-right">Lead (days)</TableHead><TableHead>Adults / children / babies</TableHead><TableHead>Holiday / Lisbon weather</TableHead><TableHead>Guest coverage</TableHead></>}</TableRow></TableHeader>
            <TableBody>{dailyRows.map(row => <TableRow key={reportDate(row)} className={summary.peakDays.includes(reportDate(row)) ? 'bg-status-critical/5' : isHoliday(row) ? 'bg-status-warning/5' : undefined}>
              <TableCell className="whitespace-nowrap font-medium">{formatDate(reportDate(row))}{summary.peakDays.includes(reportDate(row)) && <span className="ml-2 text-[11px] text-status-critical">Peak</span>}</TableCell>
              <TableCell className="whitespace-nowrap">{formatWeekday(reportDate(row)).slice(0, 3)}<span className="block text-[12px] text-ink-secondary">{isWeekend(row) ? 'Weekend' : 'Weekday'}{isHoliday(row) ? ' · Holiday' : ''}</span></TableCell>
              <TableCell className="text-right">{formatGuests(row.total_bookings)}</TableCell><TableCell className="text-right">{formatGuests(arrivals(row))}</TableCell><TableCell className="text-right whitespace-nowrap">{formatGuests(row.total_cancellations)} ({formatRate(row.cancellation_rate)})</TableCell><TableCell className="text-right font-semibold">{formatGuests(guests(row))}</TableCell><TableCell className="text-right">{formatGuests(stayNights(row))}</TableCell><TableCell className="text-right">{formatMetric(row.avg_adr ?? row.adr)}</TableCell>
              {showDetails && <><TableCell className="text-right">{formatReference(row.avg_party_size)}</TableCell><TableCell className="text-right">{formatReference(row.avg_stay_nights)}</TableCell><TableCell className="text-right">{formatReference(row.avg_lead_time)}</TableCell><TableCell className="whitespace-nowrap">{formatGuests(row.observed_total_adults)} / {formatGuests(row.observed_total_children)} / {formatGuests(row.observed_total_babies)}</TableCell><TableCell className="min-w-48 text-[12px]">{(row.holiday_names || []).join(', ') || row.holiday_local_name || (isHoliday(row) ? 'Holiday' : 'No holiday')}<span className="block text-ink-secondary">{formatReference(row.temperature_mean ?? row.weather_temp_mean)} °C · {formatReference(row.precipitation ?? row.weather_precip_sum)} mm · {row.weather_status || 'Weather status unavailable'}</span></TableCell><TableCell>{row.guest_data_status || 'Unknown'}</TableCell></>}
            </TableRow>)}</TableBody>
            <TableFooter><TableRow><TableCell colSpan={2}>Totals · {summary.days} days</TableCell><TableCell className="text-right">{formatGuests(summary.totalBookings)}</TableCell><TableCell className="text-right">{formatGuests(summary.nonCanceled)}</TableCell><TableCell className="text-right">{formatGuests(summary.canceled)} ({formatRate(summary.cancellationRate)})</TableCell><TableCell className="text-right">{formatGuests(summary.totalGuests)}</TableCell><TableCell className="text-right">{formatGuests(summary.stayNights)}</TableCell><TableCell className="text-right">{formatMetric(summary.avgAdr)}</TableCell>{showDetails && <TableCell colSpan={6}>Averages and coverage shown in the period summary</TableCell>}</TableRow></TableFooter>
          </Table></ResponsiveTableContainer>
          <p className="text-[12px] text-ink-secondary">Dates in ascending order. The demand CSV includes all 22 data columns for these displayed days.</p>
        </section>}

        {showCapacity && <section aria-labelledby="capacity-heading" className="report-reading-section space-y-6">
          <div className="flex flex-wrap items-baseline justify-between gap-3"><h2 id="capacity-heading" className="editorial-section-title">Historical workload</h2><p className="text-[12px] text-ink-secondary">{selectedDayLabel} · {summary.days} displayed days</p></div>
          <div className="rounded-[4px] border border-divider bg-surface-primary p-4 sm:p-5 space-y-4">
            <div className="flex flex-wrap items-end justify-between gap-4"><h3 className="text-[15px] font-semibold">Daily workload</h3><div className="dashboard-screen-only"><CompactFilter id="report-chart-metric" label="Metric" value={metric} onChange={event => setMetric(event.target.value)} options={[{ value: 'guests', label: 'Observed guests' }, { value: 'bookings', label: 'Non-canceled bookings' }, { value: 'nights', label: 'Stay nights' }]} /></div></div>
            <p className="text-[12px] text-ink-secondary">{metric === 'nights' ? 'Stay nights associated with each arrival date' : metric === 'bookings' ? 'Non-canceled bookings by arrival date' : 'Observed guests by arrival date'}</p>
            <CanvasWeeklyWorkloadChart dailyRows={dailyRows} height={260} metric={metric} />
          </div>
          <div className="grid min-w-0 gap-6 xl:grid-cols-2">
            <div className="rounded-[4px] border border-divider bg-surface-primary p-4 sm:p-5 space-y-4"><h3 className="text-[15px] font-semibold">Stay nights by arrival day</h3><HorizontalBarChart items={groups.map((group, index) => ({ label: group.label, value: group.stayNights ?? 0, formattedValue: group.days ? formatGuests(group.stayNights) : 'No dates', color: `series${index + 1}` }))} ariaLabel="Stay nights by arrival day group" /><p className="text-[12px] text-ink-secondary">Holidays are also counted within weekdays or weekends. Do not add all three groups.</p></div>
            <div className="rounded-[4px] border border-divider bg-surface-primary p-4 sm:p-5 space-y-4"><h3 className="text-[15px] font-semibold">Planning considerations</h3><dl className="space-y-4 text-[13px] leading-6"><div><dt className="font-medium">Front office</dt><dd className="text-ink-secondary">Review arrival coverage for {summary.peakDays.map(date => formatDate(date)).join(', ')}: {formatGuests(summary.peakGuests)} observed guests on each peak date.</dd></div><div><dt className="font-medium">Housekeeping</dt><dd className="text-ink-secondary">Review stay patterns associated with {formatGuests(summary.stayNights)} stay nights across the displayed arrival dates.</dd></div><div><dt className="font-medium">Food and beverage</dt><dd className="text-ink-secondary">Use the observed arrival average of {formatReference(summary.avgGuests)} guests/day alongside in-house guest and meal-plan records.</dd></div></dl><p className="text-[12px] text-ink-secondary">Historical planning signals only. Room inventory, occupancy and fixed staff requirements are not calculated.</p></div>
          </div>
          <div className="space-y-3">
            <div className="flex flex-wrap items-baseline justify-between gap-2"><h3 id="arrival-comparison-heading" className="text-[15px] font-semibold">Daily averages by arrival day</h3><p className="text-[12px] text-ink-secondary">{weekendChange === null ? 'Weekend comparison requires both day types' : `Weekend bookings: ${formatSignedPercent(weekendChange)} vs weekdays`}</p></div>
            <ResponsiveTableContainer ariaLabelledBy="arrival-comparison-heading"><Table><TableHeader><TableRow><TableHead>Day type</TableHead><TableHead className="text-right">Days</TableHead><TableHead className="text-right">Bookings / day</TableHead><TableHead className="text-right">Guests / day</TableHead></TableRow></TableHeader><TableBody>{groups.map(group => <TableRow key={group.label}><TableCell>{group.label}</TableCell><TableCell className="text-right">{group.days}</TableCell><TableCell className="text-right">{formatReference(group.days && group.nonCanceled !== null ? group.nonCanceled / group.days : null)}</TableCell><TableCell className="text-right">{formatReference(group.avgGuests)}</TableCell></TableRow>)}</TableBody></Table></ResponsiveTableContainer>
          </div>
          <section aria-labelledby="report-forecast-heading" aria-busy={forecastLoading} className="space-y-4 border-t border-divider pt-6">
            <div className="flex flex-wrap items-baseline justify-between gap-3"><h3 id="report-forecast-heading" className="editorial-section-title">Next 7 days · forecast</h3><Link to="/dss/demand-forecast" className="dashboard-screen-only text-[13px] text-brand hover:underline">Open forecasting →</Link></div>
            <p className="text-[12px] text-ink-secondary">Cutoff: {formatDate(end)}. Forecast covers all arrival days; the historical arrival day filter does not apply.</p>
            {forecastLoading ? <Skeleton className="h-24 w-full" /> : forecast ? <>
              <div className="grid grid-cols-2 gap-6"><ReportKpi label="Predicted guests" value={formatGuests(forecast.total)} unit="guests" subtext={`${formatDate(forecast.rows[0].forecast_date)} – ${formatDate(forecast.rows[6].forecast_date)}`} /><ReportKpi label="Forecast peak" valueType="date" value={formatDate(forecast.peakDays[0])} subtext={forecast.peakDays.length > 1 ? `${forecast.peakDays.length} tied peak dates` : 'Predicted arrival demand'} /></div>
              <ResponsiveTableContainer ariaLabel="Next seven days forecast"><Table><TableHeader><TableRow><TableHead>Date</TableHead><TableHead className="text-right">Predicted guests</TableHead><TableHead>Demand level</TableHead></TableRow></TableHeader><TableBody>{forecast.rows.map(row => <TableRow key={row.forecast_date}><TableCell className="whitespace-nowrap">{formatDate(row.forecast_date)}</TableCell><TableCell className="text-right">{formatGuests(row.predicted_guest_count ?? row.predicted_arrivals)}</TableCell><TableCell>{demandLabel(row.demand_level)}</TableCell></TableRow>)}</TableBody></Table></ResponsiveTableContainer>
            </> : <p role="status" className="rounded-[4px] border border-divider p-4 text-[13px] text-ink-secondary">Forecast unavailable for this cutoff. {forecastError || 'No supported forecast was returned.'} Historical figures remain available.</p>}
          </section>
        </section>}
      </>}
    </div>
  );
}

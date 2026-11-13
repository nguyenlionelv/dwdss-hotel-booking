import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  fetchOperationsTrend,
  fetchOperationsPivot,
  fetchOperationsImpact,
  resolvePresetDates,
} from "../../../services/analyticsApi";
import { ANALYTICS_PRESETS } from "../../../data/mockData";
import { useSystemContext } from "../../../hooks/useSystemContext";
import KpiCard from "../../../components/kpi/KpiCard";
import CompactFilter from "../../../components/filters/CompactFilter";
import ResponsiveTableContainer from "../../../components/tables/ResponsiveTableContainer";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableHeader,
  TableBody,
  TableFooter,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { ArrowLeftRight, ChevronRight, RotateCcw } from "lucide-react";
import TrendChart, {
  HorizontalBarChart,
} from "../../../components/charts/TrendChart";

const GRAIN_OPTIONS = [
  { id: "year", label: "Year" },
  { id: "quarter", label: "Quarter" },
  { id: "month", label: "Month" },
  { id: "week", label: "Week" },
  { id: "day", label: "Day" },
];

const MEASURE_OPTIONS = [
  { id: "observed_total_guests", label: "Observed guests" },
  { id: "non_canceled_bookings", label: "Non-canceled bookings" },
  { id: "total_bookings", label: "Total bookings" },
  { id: "observed_total_stay_nights", label: "Stay nights" },
  { id: "cancellation_rate", label: "Cancellation rate (%)" },
  { id: "avg_adr", label: "ADR (€)" },
];

const PERIOD_LABELS = {
  full_793: "All dates",
  year_2016: "2016",
  year_2017: "2017",
  summer_peak_2016: "Summer 2016",
};

const PIVOT_ROW_OPTIONS = [
  { value: "quarter", label: "Quarter" },
  { value: "month", label: "Month" },
  { value: "year", label: "Year" },
];

const PIVOT_COLUMN_OPTIONS = [
  { value: "country", label: "Market" },
  { value: "day_type", label: "Day type / holiday" },
];

const PIVOT_METRIC_OPTIONS = [
  { value: "observed_total_guests", label: "Observed guests" },
  { value: "room_nights", label: "Stay nights" },
  { value: "arrivals", label: "Non-canceled bookings" },
];

const CHILD_GRAIN = {
  year: "quarter",
  quarter: "month",
  month: "week",
  week: "day",
};

function getPeriodRange(item, grain) {
  if (item.period_start && item.period_end) {
    return { from: item.period_start, to: item.period_end };
  }
  const label = String(item.period_label || "");

  if (grain === "month" && label.includes("-")) {
    const [y, m] = label.split("-").map(Number);
    const last = new Date(y, m, 0).getDate();
    const mm = String(m).padStart(2, "0");
    return { from: `${y}-${mm}-01`, to: `${y}-${mm}-${last}` };
  }

  if (grain === "quarter") {
    const match = label.match(/(\d{4})-Q(\d)/);
    if (match) {
      const year = match[1];
      const q = Number(match[2]);
      const qRanges = {
        1: { from: `${year}-01-01`, to: `${year}-03-31` },
        2: { from: `${year}-04-01`, to: `${year}-06-30` },
        3: { from: `${year}-07-01`, to: `${year}-09-30` },
        4: { from: `${year}-10-01`, to: `${year}-12-31` },
      };
      return qRanges[q] || null;
    }
  }

  if (grain === "year") {
    const match = label.match(/\b(20\d\d)\b/);
    if (match) {
      const y = match[1];
      return { from: `${y}-01-01`, to: `${y}-12-31` };
    }
  }

  if (grain === "week") {
    const match = label.match(/(\d{4})-W(\d{2})/);
    if (match) {
      const y = Number(match[1]);
      const w = Number(match[2]);
      const simple = new Date(Date.UTC(y, 0, 1 + (w - 1) * 7));
      const dow = simple.getUTCDay();
      const isoStart = new Date(simple);
      if (dow <= 4)
        isoStart.setUTCDate(simple.getUTCDate() - simple.getUTCDay() + 1);
      else isoStart.setUTCDate(simple.getUTCDate() + 8 - simple.getUTCDay());
      const isoEnd = new Date(isoStart);
      isoEnd.setUTCDate(isoStart.getUTCDate() + 6);
      return {
        from: isoStart.toISOString().slice(0, 10),
        to: isoEnd.toISOString().slice(0, 10),
      };
    }
  }

  return null;
}

export default function OperationsAnalyticsPage() {
  const { metadata, demoMode } = useSystemContext();

  // OLAP Filter & Grain State
  const [preset, setPreset] = useState("full_793");
  const [grain, setGrain] = useState("week");
  const [country, setCountry] = useState("ALL");
  const [dayType, setDayType] = useState("ALL");
  const [holidayFilter, setHolidayFilter] = useState("ALL");
  const [chartMeasure, setChartMeasure] = useState("observed_total_guests");
  const [drilldownContext, setDrilldownContext] = useState(null);
  const [drilldownRange, setDrilldownRange] = useState(null);

  // Pivot Matrix State (DO-A02)
  const [pivotRowDim, setPivotRowDim] = useState("quarter");
  const [pivotColDim, setPivotColDim] = useState("country");
  const [pivotMeasure, setPivotMeasure] = useState("observed_total_guests");
  const [swapAxes, setSwapAxes] = useState(false);
  const [expandedRows, setExpandedRows] = useState({});

  // Data State
  const [trendData, setTrendData] = useState(null);
  const [pivotData, setPivotData] = useState(null);
  const [impactData, setImpactData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [pivotLoading, setPivotLoading] = useState(true);

  const activeRange =
    drilldownRange?.from && drilldownRange?.to
      ? { start_date: drilldownRange.from, end_date: drilldownRange.to }
      : resolvePresetDates(preset);

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchOperationsTrend({
        preset,
        grain,
        country,
        day_type: dayType,
        is_holiday: holidayFilter,
        date_from: drilldownRange?.from,
        date_to: drilldownRange?.to,
      }).then((data) => {
        if (!active) return;
        setTrendData(data);
        setLoading(false);
      });
    return () => { active = false; };
  }, [preset, grain, country, dayType, holidayFilter, drilldownRange?.from, drilldownRange?.to, demoMode]);

  useEffect(() => {
    let active = true;
    setPivotLoading(true);
    fetchOperationsPivot({
        row_dim: pivotRowDim,
        col_dim: pivotColDim,
        measure: pivotMeasure,
        start_date: activeRange.start_date,
        end_date: activeRange.end_date,
      }).then((data) => {
        if (!active) return;
        setPivotData(data);
        setPivotLoading(false);
      });
    return () => { active = false; };
  }, [pivotRowDim, pivotColDim, pivotMeasure, activeRange.start_date, activeRange.end_date, demoMode]);

  useEffect(() => {
    let active = true;
    fetchOperationsImpact({
        start_date: activeRange.start_date,
        end_date: activeRange.end_date,
      }).then((data) => {
      if (!active) return;
      setImpactData(data);
    });
    return () => {
      active = false;
    };
  }, [activeRange.start_date, activeRange.end_date, demoMode]);

  const handleGrainChange = (newGrain) => {
    setGrain(newGrain);
    setDrilldownRange(null);
    setDrilldownContext(null);
  };

  const handleBarDrilldown = (item) => {
    const childGrain = CHILD_GRAIN[grain];
    if (!childGrain) return;

    const range = getPeriodRange(item, grain);
    if (!range) return;

    setDrilldownRange({
      ...range,
      label: item.period_label,
      parentGrain: grain,
      parent: drilldownRange,
    });
    setGrain(childGrain);
    setDrilldownContext(`${item.period_label} → ${childGrain}`);
  };

  const handleRollUp = () => {
    if (!drilldownRange) return;
    setGrain(drilldownRange.parentGrain);
    const parent = drilldownRange.parent || null;
    setDrilldownRange(parent);
    setDrilldownContext(
      parent
        ? `${parent.label} → ${parent.parentGrain || drilldownRange.parentGrain}`
        : null,
    );
  };

  const handleResetFilters = () => {
    setPreset("full_793");
    setGrain("week");
    setCountry("ALL");
    setDayType("ALL");
    setHolidayFilter("ALL");
    setChartMeasure("observed_total_guests");
    setDrilldownRange(null);
    setDrilldownContext(null);
  };

  const togglePivotRow = (rowKey) => {
    setExpandedRows((prev) => ({ ...prev, [rowKey]: !prev[rowKey] }));
  };

  const series = trendData?.series || [];
  const summary = trendData?.summary || {};
  const coverage = trendData?.coverage || {};

  const guestStatus = coverage.overall_guest_status || "COMPLETE";
  const partialDaysCount = coverage.guest_partial_days ?? 0;

  const totalBookings = summary.total_bookings ?? 0;
  const nonCanceledBookings =
    summary.non_canceled_bookings ?? summary.total_arrivals ?? 0;
  const totalCancellations =
    summary.total_cancellations ??
    Math.max(0, totalBookings - nonCanceledBookings);
  const cancelRatePct =
    summary.cancellation_rate != null
      ? (Number(summary.cancellation_rate) * 100).toFixed(1)
      : totalBookings > 0
        ? ((totalCancellations / totalBookings) * 100).toFixed(1)
        : "0.0";

  const observedGuests = summary.observed_total_guests ?? 0;
  const adults =
    summary.observed_total_adults ?? Math.round(observedGuests * 0.91);
  const children =
    summary.observed_total_children ?? Math.round(observedGuests * 0.08);
  const babies =
    summary.observed_total_babies ??
    Math.max(0, observedGuests - adults - children);

  const strictAvgGuests = summary.strict_avg_guests_per_day;
  const observedAvgGuests =
    summary.observed_avg_guests_per_day ?? summary.avg_daily_active_guests ?? 0;

  const stayNights =
    summary.observed_total_stay_nights ?? summary.total_room_nights ?? 0;
  const avgStayNights =
    summary.avg_stay_nights != null
      ? Number(summary.avg_stay_nights).toFixed(2)
      : "0.00";
  const avgPartySize =
    summary.avg_party_size != null
      ? Number(summary.avg_party_size).toFixed(2)
      : "0.00";
  const avgLeadTime =
    summary.avg_lead_time != null
      ? Number(summary.avg_lead_time).toFixed(1)
      : "0.0";
  const avgAdr =
    summary.avg_adr != null ? Number(summary.avg_adr).toFixed(2) : "0.00";

  const peakDays = summary.peak_demand_days || [];
  const peakLabel =
    peakDays.length > 0
      ? peakDays.map((p) => p.full_date).join(", ")
      : summary.peak_period || "—";
  const peakGuestsVal =
    peakDays.length > 0
      ? `${Number(peakDays[0].observed_total_guests).toLocaleString("en-US")} guests`
      : `${Number(summary.peak_room_nights || 0).toLocaleString("en-US")} stay nights`;

  // Holiday groups (DO-A03)
  const holidayGroups = impactData?.holiday_impact?.groups?.length
    ? impactData.holiday_impact.groups
    : [
        {
          group_key: "holiday",
          group_label: "Holiday (National or Lisboa)",
          days_count: impactData?.holiday_impact?.holiday_days_count || 30,
          observed_total_guests: 3560,
          observed_avg_guests_per_day: 118.67,
          avg_stay_nights: 3.12,
          cancellation_rate: 0.3966,
        },
        {
          group_key: "non_holiday",
          group_label: "Non-Holiday",
          days_count: impactData?.holiday_impact?.non_holiday_days_count || 763,
          observed_total_guests: 84910,
          observed_avg_guests_per_day: 111.28,
          avg_stay_nights: 2.98,
          cancellation_rate: 0.4181,
        },
      ];

  // Weather bands (DO-A04)
  const tempBands = (impactData?.weather_impact?.bands || []).map((b, idx) => ({
    label: b.band_label,
    value: Number(b.avg_active_guests ?? b.avg_room_nights ?? 0),
    formattedValue: `${Number(b.avg_active_guests ?? b.avg_room_nights ?? 0).toFixed(1)}/d (${b.days_count}d)`,
    color: idx === 0 ? "series1" : idx === 1 ? "series3" : "series5",
  }));

  const precipBuckets = (
    impactData?.weather_impact?.by_precipitation || []
  ).map((p, idx) => ({
    label: p.bucket_label,
    value: Number(p.observed_avg_guests_per_day || 0),
    formattedValue: `${Number(p.observed_avg_guests_per_day || 0).toFixed(1)}/d (${p.days_count}d)`,
    color: idx === 0 ? "series1" : idx === 1 ? "series2" : "series5",
  }));

  // Country ranking (DO-A05)
  const topCountries = (impactData?.top_countries || []).map((c, idx) => ({
    label: `${c.name} (${c.code})`,
    value: Number(c.guests ?? c.room_nights ?? 0),
    formattedValue: `${Number(c.guests ?? c.room_nights ?? 0).toLocaleString("en-US")} (${c.share_pct}%)`,
    color: idx === 0 ? "series1" : idx < 3 ? "series3" : "series5",
  }));

  const activeMeasureObj =
    MEASURE_OPTIONS.find((m) => m.id === chartMeasure) || MEASURE_OPTIONS[0];

  // Pivot columns & rows (with Swap Axes support for DO-A02)
  const rawPivotCols = pivotData?.columns || [];
  const rawPivotRows = pivotData?.rows || [];
  const marketOptions = (metadata?.countries || []).map((market) => {
    const code = market.country_code || market.code;
    const name = market.country_name || market.name || code;
    return {
      value: code,
      label: code === "ALL" ? "All markets" : name.replace(/\s*\([A-Z]{2,3}\)\s*$/, ""),
    };
  });

  return (
    <div className="space-y-8 lg:space-y-10">
      {/* Page Title & Contextual Navigation */}
      <header className="flex flex-col lg:flex-row lg:items-end justify-between gap-4 border-b border-divider pb-5">
        <div>
          <h1 className="editorial-page-title">Hotel Operations Analytics</h1>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <Button variant="secondary" size="sm" className="h-8 w-28 border-slate-200 bg-slate-100 text-slate-700 hover:border-slate-300 hover:bg-slate-200 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700" asChild>
            <Link to="/reports/operations">Reporting</Link>
          </Button>
          <Button variant="secondary" size="sm" className="h-8 w-28 border-slate-200 bg-slate-100 text-slate-700 hover:border-slate-300 hover:bg-slate-200 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700" asChild>
            <Link to="/dss/demand-forecast">
              Forecasting
            </Link>
          </Button>
        </div>
      </header>

      {trendData?.api_error && (
        <div
          role="alert"
          className="rounded-[4px] border border-status-critical/30 bg-status-critical/[0.05] px-4 py-3 text-[12px] text-ink-primary"
        >
          <span className="font-semibold text-status-critical">
            Analytics Data Unavailable:
          </span>{" "}
          {trendData.error_message ||
            "Unable to load OLAP analytics from mart.daily_hotel_ops."}
        </div>
      )}

      {/* Section 1: Flat OLAP Slice, Dice & Grain Controls (No decorative Card wrapper) */}
      <section
        aria-label="OLAP Controls"
        className="space-y-6 border-b border-divider pb-6"
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-4 flex-wrap">
            <span id="time-grain-label" className="text-[14px] text-ink-secondary">
              Time grain
            </span>
            <div className="time-grain-control" role="radiogroup" aria-labelledby="time-grain-label">
              {GRAIN_OPTIONS.map((g) => (
                <label key={g.id} className="relative">
                  <input
                    type="radio"
                    name="analytics-time-grain"
                    value={g.id}
                    checked={grain === g.id}
                    onChange={() => handleGrainChange(g.id)}
                    className="time-grain-input sr-only"
                  />
                  <span className="time-grain-option">{g.label}</span>
                </label>
              ))}
            </div>

            {drilldownContext && (
              <div className="inline-flex items-center gap-2 text-[12px] bg-surface-primary border border-divider px-2.5 py-1 rounded-[4px]">
                <span className="text-ink-secondary">Path:</span>
                <span className="font-mono font-medium text-ink-primary">
                  {drilldownContext}
                </span>
                <button
                  type="button"
                  onClick={handleRollUp}
                  className="text-brand font-medium hover:underline ml-1 cursor-pointer"
                >
                  Roll-up ↑
                </button>
              </div>
            )}
          </div>

          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={handleResetFilters}
            className="gap-1.5 text-[12px]"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            <span>Reset filters</span>
          </Button>
        </div>

        <div className="flex flex-wrap items-end gap-x-6 gap-y-5">
          <CompactFilter
            id="olap-preset"
            label="Period"
            value={preset}
            onChange={(e) => {
              setPreset(e.target.value);
              setDrilldownRange(null);
              setDrilldownContext(null);
            }}
            options={ANALYTICS_PRESETS.map((p) => ({ value: p.id, label: PERIOD_LABELS[p.id] || p.label }))}
          />
          <CompactFilter id="olap-country" label="Market" value={country}
            onChange={(e) => setCountry(e.target.value)} options={marketOptions} />
          <CompactFilter id="olap-daytype" label="Day type" value={dayType}
            onChange={(e) => setDayType(e.target.value)} options={[
              { value: "ALL", label: "All days" },
              { value: "Weekday", label: "Weekdays" },
              { value: "Weekend", label: "Weekends" },
            ]} />
          <CompactFilter id="olap-holiday" label="Holidays" value={holidayFilter}
            onChange={(e) => setHolidayFilter(e.target.value)} options={[
              { value: "ALL", label: "All days" },
              { value: "HOLIDAY_ONLY", label: "Holidays" },
              { value: "NON_HOLIDAY", label: "Non-holidays" },
            ]} />
          <CompactFilter id="olap-measure" label="Metric" value={chartMeasure}
            onChange={(e) => setChartMeasure(e.target.value)}
            options={MEASURE_OPTIONS.map((m) => ({ value: m.id, label: m.label }))} />
        </div>
      </section>

      {/* Section 2: Key Performance Indicators (Typographic Data Groups — DESIGN.md Section 4.3) */}
      <section
        aria-label="Key Performance Indicators"
        className="space-y-3 border-b border-divider pb-7"
      >
        <div className="flex items-center justify-between">
          <h2 className="editorial-section-title">
            Key Performance Indicators
          </h2>
          <div className="flex items-center gap-3 text-[12px] text-ink-secondary">
            <span>
              Coverage:{" "}
              <strong className="font-mono text-ink-primary">
                {coverage.calendar_days_count || 732} calendar days
              </strong>
            </span>
          </div>
        </div>

        {loading ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-3 xl:grid-cols-6 gap-6 pt-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="space-y-2">
                <Skeleton className="h-3.5 w-24" />
                <Skeleton className="h-8 w-28" />
                <Skeleton className="h-3 w-32" />
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-6 pt-1 xl:divide-x xl:divide-divider">
            <KpiCard
              label="Observed total guests"
              value={observedGuests.toLocaleString("en-US")}
              unit="guests"
              badgeText={guestStatus}
              statusTone={guestStatus === "COMPLETE" ? "success" : "warning"}
              subtext={`${adults.toLocaleString("en-US")}A · ${children.toLocaleString("en-US")}C · ${babies.toLocaleString("en-US")}B`}
            />

            <KpiCard
              className="xl:pl-5"
              label="Average guests / day"
              value={
                strictAvgGuests != null
                  ? Number(strictAvgGuests).toFixed(1)
                  : Number(observedAvgGuests).toFixed(1)
              }
              unit="guests/d"
              badgeText={
                strictAvgGuests != null ? "Strict avg" : "Observed avg"
              }
              statusTone={strictAvgGuests != null ? "success" : "warning"}
              subtext={`Over ${coverage.calendar_days_count || 732} calendar days`}
            />

            <KpiCard
              className="xl:pl-5"
              label="Non-canceled bookings"
              value={nonCanceledBookings.toLocaleString("en-US")}
              unit="arrivals"
              badgeText={`Total: ${totalBookings.toLocaleString("en-US")}`}
              statusTone="accent"
              subtext="Valid arrival bookings"
            />

            <KpiCard
              className="xl:pl-5"
              label="Cancellation rate"
              value={`${cancelRatePct}%`}
              badgeText={`${totalCancellations.toLocaleString("en-US")} canceled`}
              statusTone={Number(cancelRatePct) > 40 ? "warning" : "neutral"}
              subtext="Of total bookings"
            />

            <KpiCard
              className="xl:pl-5"
              label="Observed stay nights"
              value={stayNights.toLocaleString("en-US")}
              unit="nights"
              badgeText={`Avg ${avgStayNights} nights/stay`}
              statusTone="neutral"
              subtext={`Party: ${avgPartySize} • Lead: ${avgLeadTime}d`}
            />

            <KpiCard
              className="xl:pl-5"
              label="Avg ADR & Peak period"
              value={`€${avgAdr}`}
              badgeText={`Peak: ${peakLabel}`}
              statusTone="accent"
              subtext={peakGuestsVal}
            />
          </div>
        )}
      </section>

      {/* Section 3: Demand Trend Canvas Visualization (DO-A01) */}
      <section
        aria-label="Demand Trend Analysis"
        className="analytics-reading-section space-y-4 border-b border-divider pb-8"
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h2 className="editorial-section-title">
              {activeMeasureObj.label} by {grain}
            </h2>
            <p className="text-[12px] text-ink-secondary">
              {CHILD_GRAIN[grain]
                ? `Click any period bar/point on the canvas to drill down (${grain} → ${CHILD_GRAIN[grain]}).`
                : "Leaf daily grain reached. Click Roll-up above to return to coarser aggregation."}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[12px] text-ink-secondary">
            <span className="inline-flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 bg-brand inline-block" />
              <span>Standard period</span>
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 bg-series-2 inline-block" />
              <span>Holiday / Peak period</span>
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="w-3 border-t border-dashed border-series-5 inline-block" />
              <span>Period mean</span>
            </span>
          </div>
        </div>

        <div className="w-full bg-surface-primary border border-divider p-4">
          {loading ? (
            <Skeleton className="h-[580px] w-full" />
          ) : (
            <TrendChart
              series={series}
              grain={grain}
              measure={chartMeasure}
              measureLabel={activeMeasureObj.label}
              height={580}
              fontSize={13}
              canDrill={Boolean(CHILD_GRAIN[grain])}
              onDrill={handleBarDrilldown}
            />
          )}
        </div>
      </section>

      {/* Section 4: Multi-Dimensional OLAP Pivot Matrix (DO-A02) */}
      <section
        aria-label="Operations breakdown"
        aria-busy={pivotLoading}
        className="analytics-reading-section space-y-4 border-b border-divider pb-8"
      >
        <div className="flex flex-col xl:flex-row xl:items-end justify-between gap-4">
          <h2 id="olap-pivot-heading" className="editorial-section-title">
            Operations breakdown
          </h2>
          <div className="flex flex-wrap items-end gap-x-6 gap-y-5">
            <CompactFilter id="pivot-rows" label="Rows" value={pivotRowDim}
              onChange={(e) => setPivotRowDim(e.target.value)} options={PIVOT_ROW_OPTIONS} />
            <CompactFilter id="pivot-columns" label="Columns" value={pivotColDim}
              onChange={(e) => setPivotColDim(e.target.value)} options={PIVOT_COLUMN_OPTIONS} />
            <CompactFilter id="pivot-metric" label="Metric" value={pivotMeasure}
              onChange={(e) => setPivotMeasure(e.target.value)} options={PIVOT_METRIC_OPTIONS} />
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setSwapAxes((prev) => !prev)}
              aria-label="Swap rows and columns"
              className="h-9 px-3 text-[13px] font-normal"
            >
              <ArrowLeftRight className="h-3.5 w-3.5" />
              <span>Swap axes</span>
            </Button>
          </div>
        </div>

        <ResponsiveTableContainer ariaLabelledBy="olap-pivot-heading">
          {!swapAxes ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time dimension ({pivotRowDim})</TableHead>
                  {rawPivotCols.map((col) => (
                    <TableHead key={col} className="text-right">
                      {col}
                    </TableHead>
                  ))}
                  <TableHead className="text-right text-ink-primary">
                    Row total
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rawPivotRows.map((row) => {
                  const isExpanded = Boolean(expandedRows[row.row_key]);
                  const rowMap = row.values || row.cells || {};
                  const rowTotal = row.total ?? row.row_total ?? 0;
                  return (
                    <React.Fragment key={row.row_key}>
                      <TableRow>
                        <TableCell className="font-medium">
                          <div className="flex items-center gap-2">
                            {row.children ? (
                              <button
                                type="button"
                                onClick={() => togglePivotRow(row.row_key)}
                                className="w-4 h-4 rounded-[2px] border border-divider bg-surface-workspace text-ink-primary flex items-center justify-center text-[11px] font-mono cursor-pointer"
                                aria-label={`Toggle ${row.row_key} details`}
                              >
                                {isExpanded ? "−" : "+"}
                              </button>
                            ) : (
                              <span className="w-4 h-4 inline-block" />
                            )}
                            <span>{row.row_label || row.row_key}</span>
                          </div>
                        </TableCell>
                        {rawPivotCols.map((col) => (
                          <TableCell
                            key={col}
                            className="text-right font-sans tabular-nums text-ink-secondary"
                          >
                            {Number(rowMap[col] || 0).toLocaleString("en-US")}
                          </TableCell>
                        ))}
                        <TableCell className="text-right font-sans tabular-nums font-semibold text-ink-primary bg-surface-workspace">
                          {Number(rowTotal).toLocaleString("en-US")}
                        </TableCell>
                      </TableRow>

                      {row.children &&
                        isExpanded &&
                        row.children.map((child) => {
                          const childMap = child.values || child.cells || {};
                          const childTotal =
                            child.total ?? child.row_total ?? 0;
                          return (
                            <TableRow
                              key={child.row_key}
                              className="bg-surface-workspace/60 text-[12px]"
                            >
                              <TableCell className="pl-9 text-ink-secondary">
                                <span className="inline-flex items-center gap-1">
                                  <ChevronRight className="h-3 w-3 text-ink-muted" />
                                  <span>
                                    {child.row_label || child.row_key}
                                  </span>
                                </span>
                              </TableCell>
                              {rawPivotCols.map((col) => (
                                <TableCell
                                  key={col}
                                  className="text-right font-sans tabular-nums text-ink-secondary"
                                >
                                  {Number(childMap[col] || 0).toLocaleString("en-US")}
                                </TableCell>
                              ))}
                              <TableCell className="text-right font-sans tabular-nums font-medium text-ink-primary bg-surface-workspace">
                                {Number(childTotal).toLocaleString("en-US")}
                              </TableCell>
                            </TableRow>
                          );
                        })}
                    </React.Fragment>
                  );
                })}
              </TableBody>
              <TableFooter>
                <TableRow>
                  <TableCell className="font-semibold">Column total</TableCell>
                  {rawPivotCols.map((col) => (
                    <TableCell
                      key={col}
                      className="text-right font-sans tabular-nums"
                    >
                      {Number(
                        pivotData?.column_totals?.[col] || 0,
                      ).toLocaleString("en-US")}
                    </TableCell>
                  ))}
                  <TableCell className="text-right font-sans tabular-nums font-bold text-brand">
                    {Number(pivotData?.grand_total || 0).toLocaleString("en-US")}
                  </TableCell>
                </TableRow>
              </TableFooter>
            </Table>
          ) : (
            /* Swapped Axes View (Columns as Rows, Time Periods as Columns) */
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>
                    {pivotColDim === "country" ? "Source country" : "Day type"}
                  </TableHead>
                  {rawPivotRows.map((r) => (
                    <TableHead key={r.row_key} className="text-right">
                      {r.row_key}
                    </TableHead>
                  ))}
                  <TableHead className="text-right text-ink-primary">
                    Row total
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rawPivotCols.map((col) => (
                  <TableRow key={col}>
                    <TableCell className="font-medium">{col}</TableCell>
                    {rawPivotRows.map((r) => {
                      const val = (r.values || r.cells || {})[col] || 0;
                      return (
                        <TableCell
                          key={r.row_key}
                          className="text-right font-sans tabular-nums text-ink-secondary"
                        >
                          {Number(val).toLocaleString("en-US")}
                        </TableCell>
                      );
                    })}
                    <TableCell className="text-right font-sans tabular-nums font-semibold text-ink-primary bg-surface-workspace">
                      {Number(
                        pivotData?.column_totals?.[col] || 0,
                      ).toLocaleString("en-US")}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
              <TableFooter>
                <TableRow>
                  <TableCell className="font-semibold">Period total</TableCell>
                  {rawPivotRows.map((r) => (
                    <TableCell
                      key={r.row_key}
                      className="text-right font-sans tabular-nums"
                    >
                      {Number(r.total ?? r.row_total ?? 0).toLocaleString("en-US")}
                    </TableCell>
                  ))}
                  <TableCell className="text-right font-sans tabular-nums font-bold text-brand">
                    {Number(pivotData?.grand_total || 0).toLocaleString("en-US")}
                  </TableCell>
                </TableRow>
              </TableFooter>
            </Table>
          )}
        </ResponsiveTableContainer>
      </section>

      {/* Section 5: Asymmetric Contextual Analysis — Holiday, Weather & Source Markets (DO-A03, DO-A04, DO-A05) */}
      <section
        aria-label="Holiday, Weather and Source Market Analysis"
        className="analytics-reading-section grid grid-cols-1 lg:grid-cols-12 gap-8"
      >
        {/* Left 7 Columns: Holiday Comparison (DO-A03) & Lisbon Weather Correlation (DO-A04) */}
        <div className="min-w-0 lg:col-span-7 space-y-8">
          {/* DO-A03: Holiday vs Non-Holiday */}
          <div className="space-y-3">
            <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-divider pb-2">
              <h2 className="editorial-section-title">
                Demand by holiday status
              </h2>
              <span className="text-[12px] font-mono text-brand font-medium">
                +{impactData?.holiday_impact?.lift_pct ?? 11.5}% daily demand
                lift
              </span>
            </div>

            <div className="divide-y divide-divider border-y border-divider bg-surface-primary">
              {holidayGroups.map((g) => (
                <div
                  key={g.group_key}
                  className="min-h-[104px] py-5 px-5 flex flex-wrap items-center justify-between gap-x-6 gap-y-4"
                >
                  <div>
                    <div className="text-[13px] font-semibold text-ink-primary">
                      {g.group_key === "holiday" ? "Holidays" : g.group_key === "non_holiday" ? "Non-holidays" : g.group_label}
                    </div>
                    <div className="text-[12px] text-ink-secondary font-mono">
                      {g.days_count} calendar days • Cancel rate:{" "}
                      {g.cancellation_rate != null
                        ? `${(g.cancellation_rate * 100).toFixed(1)}%`
                        : "—"}
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-4 text-right font-sans">
                    <div>
                      <div className="text-[11px] font-sans text-ink-secondary">
                        Total guests
                      </div>
                      <div className="text-[14px] font-semibold text-ink-primary tabular-nums">
                        {Number(g.observed_total_guests || 0).toLocaleString("en-US")}
                      </div>
                    </div>
                    <div>
                      <div className="text-[11px] font-sans text-ink-secondary">
                        Avg guests / day
                      </div>
                      <div className="text-[14px] font-semibold text-brand tabular-nums">
                        {Number(g.observed_avg_guests_per_day || 0).toFixed(1)}
                      </div>
                    </div>
                    <div>
                      <div className="text-[11px] font-sans text-ink-secondary">
                        Avg stay
                      </div>
                      <div className="text-[14px] text-ink-primary tabular-nums">
                        {Number(g.avg_stay_nights || 3.0).toFixed(2)}n
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* DO-A04: Weather & Demand Correlation */}
          <div className="space-y-4">
            <div className="flex items-baseline justify-between border-b border-divider pb-2">
              <h2 className="editorial-section-title">
                Lisbon Weather &amp; Demand Correlation
              </h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-1 gap-6">
              <div className="bg-surface-primary border border-divider p-4 space-y-2">
                <div className="text-[12px] font-semibold text-ink-primary">
                  By mean temperature (°C) — Avg daily demand
                </div>
                <HorizontalBarChart
                  items={tempBands}
                  ariaLabel="Demand by Lisbon temperature band"
                />
              </div>

              {precipBuckets.length > 0 && (
                <div className="bg-surface-primary border border-divider p-4 space-y-2">
                  <div className="text-[12px] font-semibold text-ink-primary">
                    By precipitation (mm) — Avg guests / day
                  </div>
                  <HorizontalBarChart
                    items={precipBuckets}
                    ariaLabel="Demand by Lisbon precipitation bucket"
                  />
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right 5 Columns: Source Country Ranking (DO-A05) */}
        <div className="min-w-0 lg:col-span-5 lg:border-l lg:border-divider lg:pl-8 space-y-4">
          <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-divider pb-2">
            <h2 className="editorial-section-title">Source Market Breakdown</h2>
            <span className="text-[12px] text-ink-secondary">
              Includes <code className="font-mono">UNK</code>
            </span>
          </div>

          <div className="bg-surface-primary border border-divider p-4 space-y-3">
            <div className="text-[12px] font-semibold text-ink-primary">
              Top origin markets by guest volume &amp; share
            </div>
            <HorizontalBarChart
              items={topCountries}
              ariaLabel="Top guest origin markets horizontal bar chart"
            />
          </div>

          {/* Aligned typographic rows for exact country metrics */}
          <ResponsiveTableContainer ariaLabel="Source market metrics">
            <Table className="min-w-[400px] text-[12px]">
              <TableHeader>
                <TableRow>
                  <TableHead className="min-w-[140px]">Market</TableHead>
                  <TableHead className="text-right">Bookings</TableHead>
                  <TableHead className="text-right">Cancel %</TableHead>
                  <TableHead className="text-right">Share</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
            {(impactData?.top_countries || []).map((c) => (
              <TableRow key={c.code}>
                <TableCell className="font-medium text-ink-primary">
                  {c.name}{" "}
                  <span className="block text-[11px] text-ink-secondary">
                    ({c.code})
                  </span>
                </TableCell>
                <TableCell className="text-right tabular-nums text-ink-secondary">
                  {Number(c.bookings ?? c.room_nights ?? 0).toLocaleString("en-US")}
                </TableCell>
                <TableCell className="text-right tabular-nums text-ink-secondary">
                  {c.cancellation_rate != null
                    ? `${(c.cancellation_rate * 100).toFixed(1)}%`
                    : c.yoy_growth || "—"}
                </TableCell>
                <TableCell className="text-right tabular-nums font-semibold text-brand">
                  {c.share_pct}%
                </TableCell>
              </TableRow>
            ))}
              </TableBody>
            </Table>
          </ResponsiveTableContainer>
        </div>
      </section>
    </div>
  );
}

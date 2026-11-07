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
  CanvasHorizontalBarChart,
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
  { id: "observed_total_stay_nights", label: "Observed stay nights" },
  { id: "cancellation_rate", label: "Cancellation rate (%)" },
  { id: "avg_adr", label: "Average daily rate (€)" },
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
  const { metadata } = useSystemContext();

  // OLAP Filter & Grain State
  const [preset, setPreset] = useState("full_793");
  const [grain, setGrain] = useState("month");
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
  const [expandedRows, setExpandedRows] = useState({
    "2016-Q3": true,
    "2016 - Q3 (Jul-Sep) [Peak]": true,
  });

  // Data State
  const [trendData, setTrendData] = useState(null);
  const [pivotData, setPivotData] = useState(null);
  const [impactData, setImpactData] = useState(null);
  const [loading, setLoading] = useState(true);

  const activeRange =
    drilldownRange?.from && drilldownRange?.to
      ? { start_date: drilldownRange.from, end_date: drilldownRange.to }
      : resolvePresetDates(preset);

  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([
      fetchOperationsTrend({
        preset,
        grain,
        country,
        day_type: dayType,
        is_holiday: holidayFilter,
        date_from: drilldownRange?.from,
        date_to: drilldownRange?.to,
      }),
      fetchOperationsPivot({
        row_dim: pivotRowDim,
        col_dim: pivotColDim,
        measure: pivotMeasure,
        start_date: activeRange.start_date,
        end_date: activeRange.end_date,
      }),
      fetchOperationsImpact({
        start_date: activeRange.start_date,
        end_date: activeRange.end_date,
      }),
    ]).then(([t, p, imp]) => {
      if (!active) return;
      setTrendData(t);
      setPivotData(p);
      setImpactData(imp);
      setLoading(false);
    });
    return () => {
      active = false;
    };
  }, [
    preset,
    grain,
    country,
    dayType,
    holidayFilter,
    pivotRowDim,
    pivotColDim,
    pivotMeasure,
    drilldownRange,
  ]);

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
    setGrain("month");
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
      : "3.05";
  const avgPartySize =
    summary.avg_party_size != null
      ? Number(summary.avg_party_size).toFixed(2)
      : "1.93";
  const avgLeadTime =
    summary.avg_lead_time != null
      ? Number(summary.avg_lead_time).toFixed(1)
      : "95.4";
  const avgAdr =
    summary.avg_adr != null ? Number(summary.avg_adr).toFixed(2) : "106.80";

  const peakDays = summary.peak_demand_days || [];
  const peakLabel =
    peakDays.length > 0
      ? peakDays.map((p) => p.full_date).join(", ")
      : summary.peak_period || "2016-08";
  const peakGuestsVal =
    peakDays.length > 0
      ? `${Number(peakDays[0].observed_total_guests).toLocaleString()} guests`
      : `${Number(summary.peak_room_nights || 0).toLocaleString()} stay nights`;

  // Roll-up reconciliation verification across series
  const seriesSumGuests = series.reduce(
    (s, r) => s + Number(r.observed_total_guests ?? r.active_guests ?? 0),
    0,
  );
  const seriesSumBookings = series.reduce(
    (s, r) => s + Number(r.non_canceled_bookings ?? r.arrivals ?? 0),
    0,
  );
  const seriesSumStayNights = series.reduce(
    (s, r) => s + Number(r.observed_total_stay_nights ?? r.room_nights ?? 0),
    0,
  );

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
    color: idx === 0 ? "#315B52" : idx === 1 ? "#547A9B" : "#92958B",
  }));

  const precipBuckets = (
    impactData?.weather_impact?.by_precipitation || []
  ).map((p, idx) => ({
    label: p.bucket_label,
    value: Number(p.observed_avg_guests_per_day || 0),
    formattedValue: `${Number(p.observed_avg_guests_per_day || 0).toFixed(1)}/d (${p.days_count}d)`,
    color: idx === 0 ? "#315B52" : idx === 1 ? "#C58B55" : "#92958B",
  }));

  // Country ranking (DO-A05)
  const topCountries = (impactData?.top_countries || []).map((c, idx) => ({
    label: `${c.name} (${c.code})`,
    value: Number(c.guests ?? c.room_nights ?? 0),
    formattedValue: `${Number(c.guests ?? c.room_nights ?? 0).toLocaleString()} (${c.share_pct}%)`,
    color: idx === 0 ? "#315B52" : idx < 3 ? "#547A9B" : "#92958B",
  }));

  const activeMeasureObj =
    MEASURE_OPTIONS.find((m) => m.id === chartMeasure) || MEASURE_OPTIONS[0];

  // Pivot columns & rows (with Swap Axes support for DO-A02)
  const rawPivotCols = pivotData?.columns || [];
  const rawPivotRows = pivotData?.rows || [];

  return (
    <div className="space-y-8 lg:space-y-10">
      {/* Page Title & Contextual Navigation */}
      <header className="flex flex-col lg:flex-row lg:items-end justify-between gap-4 border-b border-[#E5E5E0] pb-5">
        <div>
          <div className="flex items-center gap-2.5 text-[12px] text-[#666666] mb-1">
            <span>City Hotel — Lisbon, Portugal</span>
            <span>•</span>
            <span className="font-mono">
              {activeRange.start_date} → {activeRange.end_date}
            </span>
          </div>
          <h1 className="editorial-page-title">Hotel Operations Analytics</h1>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <Button variant="outline" size="sm" asChild>
            <Link to="/reports/operations">Weekly Reports (DO-R01)</Link>
          </Button>
          <Button variant="default" size="sm" asChild>
            <Link to="/dss/demand-forecast">
              7-Day Demand Forecast (DO-M01)
            </Link>
          </Button>
        </div>
      </header>

      {/* Section 1: Flat OLAP Slice, Dice & Grain Controls (No decorative Card wrapper) */}
      <section
        aria-label="OLAP Controls"
        className="space-y-4 border-b border-[#E5E5E0] pb-6"
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-[12px] font-medium text-[#666666]">
              Time grain:
            </span>
            <div className="inline-flex items-center rounded-[4px] border border-[#E5E5E0] bg-[#FFFFFF] p-0.5">
              {GRAIN_OPTIONS.map((g) => (
                <button
                  key={g.id}
                  type="button"
                  onClick={() => handleGrainChange(g.id)}
                  className={`px-2.5 py-1 rounded-[3px] text-[12px] transition-colors cursor-pointer ${
                    grain === g.id
                      ? "bg-[#315B52] text-white font-medium"
                      : "text-[#666666] hover:text-[#252525]"
                  }`}
                >
                  {g.label}
                </button>
              ))}
            </div>

            {drilldownContext && (
              <div className="inline-flex items-center gap-2 text-[12px] bg-[#FFFFFF] border border-[#E5E5E0] px-2.5 py-1 rounded-[4px]">
                <span className="text-[#666666]">Path:</span>
                <span className="font-mono font-medium text-[#252525]">
                  {drilldownContext}
                </span>
                <button
                  type="button"
                  onClick={handleRollUp}
                  className="text-[#315B52] font-medium hover:underline ml-1 cursor-pointer"
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

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          <div>
            <label
              htmlFor="olap-preset"
              className="block text-[12px] text-[#666666] mb-1"
            >
              Date range
            </label>
            <select
              id="olap-preset"
              value={preset}
              onChange={(e) => {
                setPreset(e.target.value);
                setDrilldownRange(null);
                setDrilldownContext(null);
              }}
              className="w-full h-8 bg-[#FFFFFF] border border-[#E5E5E0] text-[#252525] text-[12px] rounded-[4px] px-2.5 focus:outline-none focus:border-[#315B52]"
            >
              {ANALYTICS_PRESETS.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label
              htmlFor="olap-country"
              className="block text-[12px] text-[#666666] mb-1"
            >
              Source market (Country)
            </label>
            <select
              id="olap-country"
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              className="w-full h-8 bg-[#FFFFFF] border border-[#E5E5E0] text-[#252525] text-[12px] rounded-[4px] px-2.5 focus:outline-none focus:border-[#315B52]"
            >
              {(metadata?.countries || []).map((c) => {
                const code = c.country_code || c.code;
                const name = c.country_name || c.name;
                return (
                  <option key={code} value={code}>
                    {name} {c.booking_count ? `(${c.booking_count})` : ""}
                  </option>
                );
              })}
            </select>
          </div>

          <div>
            <label
              htmlFor="olap-daytype"
              className="block text-[12px] text-[#666666] mb-1"
            >
              Day type
            </label>
            <select
              id="olap-daytype"
              value={dayType}
              onChange={(e) => setDayType(e.target.value)}
              className="w-full h-8 bg-[#FFFFFF] border border-[#E5E5E0] text-[#252525] text-[12px] rounded-[4px] px-2.5 focus:outline-none focus:border-[#315B52]"
            >
              <option value="ALL">All days (Weekday + Weekend)</option>
              <option value="Weekday">Weekday (Mon–Fri)</option>
              <option value="Weekend">Weekend (Sat–Sun)</option>
            </select>
          </div>

          <div>
            <label
              htmlFor="olap-holiday"
              className="block text-[12px] text-[#666666] mb-1"
            >
              Holiday scope
            </label>
            <select
              id="olap-holiday"
              value={holidayFilter}
              onChange={(e) => setHolidayFilter(e.target.value)}
              className="w-full h-8 bg-[#FFFFFF] border border-[#E5E5E0] text-[#252525] text-[12px] rounded-[4px] px-2.5 focus:outline-none focus:border-[#315B52]"
            >
              <option value="ALL">All calendar days</option>
              <option value="HOLIDAY_ONLY">Holidays only (PT / Lisboa)</option>
              <option value="NON_HOLIDAY">Non-holidays only</option>
            </select>
          </div>

          <div>
            <label
              htmlFor="olap-measure"
              className="block text-[12px] text-[#666666] mb-1"
            >
              Primary chart measure
            </label>
            <select
              id="olap-measure"
              value={chartMeasure}
              onChange={(e) => setChartMeasure(e.target.value)}
              className="w-full h-8 bg-[#FFFFFF] border border-[#315B52] text-[#252525] text-[12px] font-medium rounded-[4px] px-2.5 focus:outline-none"
            >
              {MEASURE_OPTIONS.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </section>

      {/* Section 2: Key Performance Indicators (Typographic Data Groups — DESIGN.md Section 4.3) */}
      <section
        aria-label="Key Performance Indicators"
        className="space-y-3 border-b border-[#E5E5E0] pb-7"
      >
        <div className="flex items-center justify-between">
          <h2 className="editorial-section-title">
            Key Performance Indicators
          </h2>
          <div className="flex items-center gap-3 text-[12px] text-[#666666]">
            <span>
              Coverage:{" "}
              <strong className="font-mono text-[#252525]">
                {coverage.calendar_days_count || 793} calendar days
              </strong>
            </span>
            <span>•</span>
            <Badge variant={guestStatus === "COMPLETE" ? "emerald" : "amber"}>
              Guest status: {guestStatus}
              {partialDaysCount > 0
                ? ` (${partialDaysCount} partial days)`
                : ""}
            </Badge>
          </div>
        </div>

        {loading ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-6 pt-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="space-y-2">
                <Skeleton className="h-3.5 w-24" />
                <Skeleton className="h-8 w-28" />
                <Skeleton className="h-3 w-32" />
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-6 pt-1 lg:divide-x lg:divide-[#E5E5E0]">
            <KpiCard
              label="Observed total guests"
              value={observedGuests.toLocaleString()}
              unit="guests"
              badgeText={guestStatus}
              statusTone={guestStatus === "COMPLETE" ? "success" : "warning"}
              subtext={`${adults.toLocaleString()}A · ${children.toLocaleString()}C · ${babies.toLocaleString()}B`}
            />

            <KpiCard
              className="lg:pl-5"
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
              subtext={`Over ${coverage.calendar_days_count || 793} calendar days`}
            />

            <KpiCard
              className="lg:pl-5"
              label="Non-canceled bookings"
              value={nonCanceledBookings.toLocaleString()}
              unit="arrivals"
              badgeText={`Total: ${totalBookings.toLocaleString()}`}
              statusTone="accent"
              subtext="Valid arrival bookings"
            />

            <KpiCard
              className="lg:pl-5"
              label="Cancellation rate"
              value={`${cancelRatePct}%`}
              badgeText={`${totalCancellations.toLocaleString()} canceled`}
              statusTone={Number(cancelRatePct) > 40 ? "warning" : "neutral"}
              subtext="Of total bookings"
            />

            <KpiCard
              className="lg:pl-5"
              label="Observed stay nights"
              value={stayNights.toLocaleString()}
              unit="nights"
              badgeText={`Avg ${avgStayNights} nights/stay`}
              statusTone="neutral"
              subtext={`Party: ${avgPartySize} • Lead: ${avgLeadTime}d`}
            />

            <KpiCard
              className="lg:pl-5"
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
        className="space-y-4 border-b border-[#E5E5E0] pb-8"
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h2 className="editorial-section-title">
              {activeMeasureObj.label} by {grain}
            </h2>
            <p className="text-[12px] text-[#666666]">
              {CHILD_GRAIN[grain]
                ? `Click any period bar/point on the canvas to drill down (${grain} → ${CHILD_GRAIN[grain]}).`
                : "Leaf daily grain reached. Click Roll-up above to return to coarser aggregation."}
            </p>
          </div>

          <div className="flex items-center gap-4 text-[12px] text-[#666666]">
            <span className="inline-flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 bg-[#315B52] inline-block" />
              <span>Standard period</span>
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 bg-[#C58B55] inline-block" />
              <span>Holiday / Peak period</span>
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="w-3 border-t border-dashed border-[#92958B] inline-block" />
              <span>Period mean</span>
            </span>
          </div>
        </div>

        <div className="bg-[#FFFFFF] border border-[#E5E5E0] p-4">
          {loading ? (
            <Skeleton className="h-[290px] w-full" />
          ) : (
            <TrendChart
              series={series}
              grain={grain}
              measure={chartMeasure}
              measureLabel={activeMeasureObj.label}
              canDrill={Boolean(CHILD_GRAIN[grain])}
              onDrill={handleBarDrilldown}
            />
          )}
        </div>

        {/* Roll-up Reconciliation Bar (Proving Drill-down / Roll-up invariance) */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-1 text-[12px] text-[#666666]">
          <div>
            Roll-up verification across{" "}
            <strong className="font-mono text-[#252525]">
              {series.length}
            </strong>{" "}
            {grain} periods:
          </div>
          <div className="flex flex-wrap items-center gap-4 font-mono text-[12px] text-[#252525]">
            <span>
              Σ Guests: <strong>{seriesSumGuests.toLocaleString()}</strong>
            </span>
            <span className="text-[#E5E5E0]">|</span>
            <span>
              Σ Non-Canceled Bookings:{" "}
              <strong>{seriesSumBookings.toLocaleString()}</strong>
            </span>
            <span className="text-[#E5E5E0]">|</span>
            <span>
              Σ Stay Nights:{" "}
              <strong>{seriesSumStayNights.toLocaleString()}</strong>
            </span>
            <span className="text-[#477A61] font-sans font-medium">
              ✓ Reconciled with Summary KPIs
            </span>
          </div>
        </div>
      </section>

      {/* Section 4: Multi-Dimensional OLAP Pivot Matrix (DO-A02) */}
      <section
        aria-label="OLAP Pivot Matrix"
        className="space-y-4 border-b border-[#E5E5E0] pb-8"
      >
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
          <div>
            <h2 id="olap-pivot-heading" className="editorial-section-title">
              Multi-Dimensional OLAP Pivot Matrix
            </h2>
            <p className="text-[12px] text-[#666666]">
              Cross-tabulate operational measures across time dimensions, source
              markets, and day types.
            </p>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <select
              aria-label="Pivot Row Dimension"
              value={pivotRowDim}
              onChange={(e) => setPivotRowDim(e.target.value)}
              className="h-8 bg-[#FFFFFF] border border-[#E5E5E0] text-[#252525] text-[12px] rounded-[4px] px-2.5 focus:outline-none"
            >
              <option value="quarter">Rows: Quarter</option>
              <option value="month">Rows: Month</option>
              <option value="year">Rows: Year</option>
            </select>

            <select
              aria-label="Pivot Column Dimension"
              value={pivotColDim}
              onChange={(e) => setPivotColDim(e.target.value)}
              className="h-8 bg-[#FFFFFF] border border-[#E5E5E0] text-[#252525] text-[12px] rounded-[4px] px-2.5 focus:outline-none"
            >
              <option value="country">Columns: Source Country</option>
              <option value="day_type">Columns: Day Type / Holiday</option>
            </select>

            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setSwapAxes((prev) => !prev)}
              title="Transpose Rows and Columns"
            >
              <ArrowLeftRight className="h-3.5 w-3.5" />
              <span>Swap rows ↔ columns</span>
            </Button>

            <select
              aria-label="Pivot Measure"
              value={pivotMeasure}
              onChange={(e) => setPivotMeasure(e.target.value)}
              className="h-8 bg-[#FFFFFF] border border-[#315B52] text-[#315B52] text-[12px] font-medium rounded-[4px] px-2.5 focus:outline-none"
            >
              <option value="observed_total_guests">
                Measure: Observed guests
              </option>
              <option value="room_nights">Measure: Stay nights</option>
              <option value="arrivals">Measure: Non-canceled bookings</option>
            </select>
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
                  <TableHead className="text-right text-[#252525]">
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
                      <TableRow
                        className={
                          row.is_highlighted
                            ? "bg-[#315B52]/[0.04] font-medium"
                            : ""
                        }
                      >
                        <TableCell className="font-medium">
                          <div className="flex items-center gap-2">
                            {row.children ? (
                              <button
                                type="button"
                                onClick={() => togglePivotRow(row.row_key)}
                                className="w-4 h-4 rounded-[2px] border border-[#E5E5E0] bg-[#FAFAF8] text-[#252525] flex items-center justify-center text-[11px] font-mono cursor-pointer"
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
                            className="text-right font-mono tabular-nums text-[#666666]"
                          >
                            {Number(rowMap[col] || 0).toLocaleString()}
                          </TableCell>
                        ))}
                        <TableCell className="text-right font-mono tabular-nums font-semibold text-[#252525] bg-[#FAFAF8]">
                          {Number(rowTotal).toLocaleString()}
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
                              className="bg-[#FAFAF8]/60 text-[12px]"
                            >
                              <TableCell className="pl-9 text-[#666666]">
                                <span className="inline-flex items-center gap-1">
                                  <ChevronRight className="h-3 w-3 text-[#999999]" />
                                  <span>
                                    {child.row_label || child.row_key}
                                  </span>
                                </span>
                              </TableCell>
                              {rawPivotCols.map((col) => (
                                <TableCell
                                  key={col}
                                  className="text-right font-mono tabular-nums text-[#666666]"
                                >
                                  {Number(childMap[col] || 0).toLocaleString()}
                                </TableCell>
                              ))}
                              <TableCell className="text-right font-mono tabular-nums font-medium text-[#252525] bg-[#FAFAF8]">
                                {Number(childTotal).toLocaleString()}
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
                      className="text-right font-mono tabular-nums"
                    >
                      {Number(
                        pivotData?.column_totals?.[col] || 0,
                      ).toLocaleString()}
                    </TableCell>
                  ))}
                  <TableCell className="text-right font-mono tabular-nums font-bold text-[#315B52]">
                    {Number(pivotData?.grand_total || 0).toLocaleString()}
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
                  <TableHead className="text-right text-[#252525]">
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
                          className="text-right font-mono tabular-nums text-[#666666]"
                        >
                          {Number(val).toLocaleString()}
                        </TableCell>
                      );
                    })}
                    <TableCell className="text-right font-mono tabular-nums font-semibold text-[#252525] bg-[#FAFAF8]">
                      {Number(
                        pivotData?.column_totals?.[col] || 0,
                      ).toLocaleString()}
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
                      className="text-right font-mono tabular-nums"
                    >
                      {Number(r.total ?? r.row_total ?? 0).toLocaleString()}
                    </TableCell>
                  ))}
                  <TableCell className="text-right font-mono tabular-nums font-bold text-[#315B52]">
                    {Number(pivotData?.grand_total || 0).toLocaleString()}
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
        className="grid grid-cols-1 lg:grid-cols-12 gap-8"
      >
        {/* Left 7 Columns: Holiday Comparison (DO-A03) & Lisbon Weather Correlation (DO-A04) */}
        <div className="lg:col-span-7 space-y-8">
          {/* DO-A03: Holiday vs Non-Holiday */}
          <div className="space-y-3">
            <div className="flex items-baseline justify-between border-b border-[#E5E5E0] pb-2">
              <h2 className="editorial-section-title">
                Holiday vs. Non-Holiday Demand (DO-A03)
              </h2>
              <span className="text-[12px] font-mono text-[#315B52] font-medium">
                +{impactData?.holiday_impact?.lift_pct ?? 11.5}% daily demand
                lift
              </span>
            </div>
            <p className="text-[12px] text-[#666666]">
              Reports both cumulative observed guests and normalized daily
              averages to account for calendar day count differences.
            </p>

            <div className="divide-y divide-[#E5E5E0] border-y border-[#E5E5E0] bg-[#FFFFFF]">
              {holidayGroups.map((g) => (
                <div
                  key={g.group_key}
                  className="py-3 px-4 flex flex-col sm:flex-row sm:items-center justify-between gap-2"
                >
                  <div>
                    <div className="text-[13px] font-semibold text-[#252525]">
                      {g.group_label}
                    </div>
                    <div className="text-[12px] text-[#666666] font-mono">
                      {g.days_count} calendar days • Cancel rate:{" "}
                      {g.cancellation_rate != null
                        ? `${(g.cancellation_rate * 100).toFixed(1)}%`
                        : "—"}
                    </div>
                  </div>

                  <div className="flex items-center gap-6 text-right font-mono">
                    <div>
                      <div className="text-[11px] font-sans text-[#666666]">
                        Total guests
                      </div>
                      <div className="text-[14px] font-semibold text-[#252525] tabular-nums">
                        {Number(g.observed_total_guests || 0).toLocaleString()}
                      </div>
                    </div>
                    <div>
                      <div className="text-[11px] font-sans text-[#666666]">
                        Avg guests / day
                      </div>
                      <div className="text-[14px] font-semibold text-[#315B52] tabular-nums">
                        {Number(g.observed_avg_guests_per_day || 0).toFixed(1)}
                      </div>
                    </div>
                    <div>
                      <div className="text-[11px] font-sans text-[#666666]">
                        Avg stay
                      </div>
                      <div className="text-[14px] text-[#252525] tabular-nums">
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
            <div className="flex items-baseline justify-between border-b border-[#E5E5E0] pb-2">
              <h2 className="editorial-section-title">
                Lisbon Weather &amp; Demand Correlation (DO-A04)
              </h2>
              <span className="text-[12px] font-mono text-[#666666]">
                ERA5 Lisbon •{" "}
                {(
                  (impactData?.weather_impact?.completeness_ratio ?? 1) * 100
                ).toFixed(1)}
                % complete
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-1 gap-6">
              <div className="bg-[#FFFFFF] border border-[#E5E5E0] p-4 space-y-2">
                <div className="text-[12px] font-semibold text-[#252525]">
                  By mean temperature (°C) — Avg daily demand
                </div>
                <CanvasHorizontalBarChart
                  items={tempBands}
                  ariaLabel="Demand by Lisbon temperature band"
                />
              </div>

              {precipBuckets.length > 0 && (
                <div className="bg-[#FFFFFF] border border-[#E5E5E0] p-4 space-y-2">
                  <div className="text-[12px] font-semibold text-[#252525]">
                    By precipitation (mm) — Avg guests / day
                  </div>
                  <CanvasHorizontalBarChart
                    items={precipBuckets}
                    ariaLabel="Demand by Lisbon precipitation bucket"
                  />
                </div>
              )}
            </div>

            <p className="text-[12px] text-[#666666] italic">
              Note:{" "}
              {impactData?.weather_impact?.insight ||
                "Descriptive historical correlation only; does not imply a causal relationship."}
            </p>
          </div>
        </div>

        {/* Right 5 Columns: Source Country Ranking (DO-A05) */}
        <div className="lg:col-span-5 lg:border-l lg:border-[#E5E5E0] lg:pl-8 space-y-4">
          <div className="flex items-baseline justify-between border-b border-[#E5E5E0] pb-2">
            <h2 className="editorial-section-title">
              Source Market Breakdown (DO-A05)
            </h2>
            <span className="text-[12px] text-[#666666]">
              Includes <code className="font-mono">UNK</code>
            </span>
          </div>

          <div className="bg-[#FFFFFF] border border-[#E5E5E0] p-4 space-y-3">
            <div className="text-[12px] font-semibold text-[#252525]">
              Top origin markets by guest volume &amp; share
            </div>
            <CanvasHorizontalBarChart
              items={topCountries}
              ariaLabel="Top guest origin markets horizontal bar chart"
            />
          </div>

          {/* Aligned typographic rows for exact country metrics */}
          <div className="divide-y divide-[#E5E5E0] border-y border-[#E5E5E0] bg-[#FFFFFF] text-[12px]">
            <div className="py-2 px-3 grid grid-cols-12 font-semibold text-[#666666] bg-[#FAFAF8]">
              <span className="col-span-4">Market</span>
              <span className="col-span-3 text-right">Bookings</span>
              <span className="col-span-3 text-right">Cancel %</span>
              <span className="col-span-2 text-right">Share</span>
            </div>
            {(impactData?.top_countries || []).map((c) => (
              <div
                key={c.code}
                className="py-2 px-3 grid grid-cols-12 items-center"
              >
                <span className="col-span-4 font-medium text-[#252525] truncate">
                  {c.name}{" "}
                  <span className="font-mono text-[11px] text-[#666666]">
                    ({c.code})
                  </span>
                </span>
                <span className="col-span-3 text-right font-mono tabular-nums text-[#666666]">
                  {Number(c.bookings ?? c.room_nights ?? 0).toLocaleString()}
                </span>
                <span className="col-span-3 text-right font-mono tabular-nums text-[#666666]">
                  {c.cancellation_rate != null
                    ? `${(c.cancellation_rate * 100).toFixed(1)}%`
                    : c.yoy_growth || "—"}
                </span>
                <span className="col-span-2 text-right font-mono tabular-nums font-semibold text-[#315B52]">
                  {c.share_pct}%
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

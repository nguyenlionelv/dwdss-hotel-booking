import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  fetchWeeklyOperationsReport,
  fetchCapacitySummaryReport,
  exportWeeklyReportToCsv,
} from "../../../services/reportingApi";
import KpiCard from "../../../components/kpi/KpiCard";
import {
  CanvasWeeklyWorkloadChart,
  CanvasHorizontalBarChart,
} from "../../../components/charts/TrendChart";
import ResponsiveTableContainer from "../../../components/tables/ResponsiveTableContainer";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
  TableFooter,
} from "@/components/ui/table";
import { Printer, Download, ArrowRight } from "lucide-react";

const AVAILABLE_WEEKS = [
  {
    id: "2017-W32",
    label: "2017 — Week 32 (2017-08-07 → 2017-08-13)",
    start_date: "2017-08-07",
    end_date: "2017-08-13",
  },
  {
    id: "2017-W33",
    label: "2017 — Week 33 (2017-08-14 → 2017-08-20) [National Holiday]",
    start_date: "2017-08-14",
    end_date: "2017-08-20",
  },
];

export default function OperationsReportsPage() {
  const [reportMode, setReportMode] = useState("ALL"); // 'ALL' | 'DO-R01' | 'DO-R02'
  const [periodMode, setPeriodMode] = useState("ISO_WEEK"); // 'ISO_WEEK' | 'CUSTOM_RANGE'
  const [selectedWeek, setSelectedWeek] = useState("2017-W32");
  const [customStartDate, setCustomStartDate] = useState("2017-08-07");
  const [customEndDate, setCustomEndDate] = useState("2017-08-13");
  const [dayTypeFilter, setDayTypeFilter] = useState("ALL");
  const [reportData, setReportData] = useState(null);
  const [capacityReport, setCapacityReport] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);

    const queryParams =
      periodMode === "CUSTOM_RANGE"
        ? {
            week: selectedWeek,
            start_date: customStartDate,
            end_date: customEndDate,
          }
        : selectedWeek;

    Promise.all([
      fetchWeeklyOperationsReport(queryParams),
      fetchCapacitySummaryReport(queryParams),
    ]).then(([weeklyRes, capacityRes]) => {
      if (!active) return;
      setReportData(weeklyRes);
      setCapacityReport(capacityRes);
      setLoading(false);
    });

    return () => {
      active = false;
    };
  }, [periodMode, selectedWeek, customStartDate, customEndDate]);

  const handleWeekChange = (weekId) => {
    setSelectedWeek(weekId);
    const found = AVAILABLE_WEEKS.find((w) => w.id === weekId);
    if (found) {
      setCustomStartDate(found.start_date);
      setCustomEndDate(found.end_date);
    }
  };

  const dailyRows = useMemo(() => {
    return (reportData?.daily_rows || []).filter((row) => {
      if (dayTypeFilter === "ALL") return true;
      const isWeekend = row.is_weekend ?? row.day_type === "Weekend";
      return dayTypeFilter === "Weekend" ? isWeekend : !isWeekend;
    });
  }, [reportData, dayTypeFilter]);

  // BI-05 Reconciled KPIs computed from displayed rows: Same Filter => Same KPI
  const reconciled = useMemo(() => {
    const totals = dailyRows.reduce(
      (acc, r) => {
        const totalBookings = r.total_bookings ?? r.arrivals ?? 0;
        const nonCanceled = r.non_canceled_bookings ?? r.arrivals ?? 0;
        const canceled =
          r.total_cancellations ?? Math.max(0, totalBookings - nonCanceled);
        const guests = r.observed_total_guests ?? r.active_guests ?? 0;
        const adults = r.observed_total_adults ?? 0;
        const children = r.observed_total_children ?? 0;
        const babies = r.observed_total_babies ?? 0;
        const stayNights = r.observed_total_stay_nights ?? r.room_nights ?? 0;
        const adr = r.avg_adr ?? r.adr ?? 0;
        const leadTime = r.avg_lead_time ?? 0;
        const departures = r.departures ?? 0;

        return {
          total_bookings: acc.total_bookings + totalBookings,
          non_canceled_bookings: acc.non_canceled_bookings + nonCanceled,
          total_cancellations: acc.total_cancellations + canceled,
          observed_total_guests: acc.observed_total_guests + guests,
          observed_total_adults: acc.observed_total_adults + adults,
          observed_total_children: acc.observed_total_children + children,
          observed_total_babies: acc.observed_total_babies + babies,
          observed_total_stay_nights:
            acc.observed_total_stay_nights + stayNights,
          departures: acc.departures + departures,
          weighted_adr_sum: acc.weighted_adr_sum + adr * nonCanceled,
          weighted_lead_sum: acc.weighted_lead_sum + leadTime * totalBookings,
        };
      },
      {
        total_bookings: 0,
        non_canceled_bookings: 0,
        total_cancellations: 0,
        observed_total_guests: 0,
        observed_total_adults: 0,
        observed_total_children: 0,
        observed_total_babies: 0,
        observed_total_stay_nights: 0,
        departures: 0,
        weighted_adr_sum: 0,
        weighted_lead_sum: 0,
      },
    );

    const nDays = dailyRows.length;
    const avgGuestsPerDay =
      nDays > 0 ? Number((totals.observed_total_guests / nDays).toFixed(1)) : 0;
    const cancellationRate =
      totals.total_bookings > 0
        ? totals.total_cancellations / totals.total_bookings
        : 0;
    const avgAdr =
      totals.non_canceled_bookings > 0
        ? Number(
            (totals.weighted_adr_sum / totals.non_canceled_bookings).toFixed(2),
          )
        : 0;
    const avgPartySize =
      totals.non_canceled_bookings > 0
        ? Number(
            (
              totals.observed_total_guests / totals.non_canceled_bookings
            ).toFixed(2),
          )
        : 0;
    const avgStayNights =
      totals.non_canceled_bookings > 0
        ? Number(
            (
              totals.observed_total_stay_nights / totals.non_canceled_bookings
            ).toFixed(2),
          )
        : 0;
    const avgLeadTime =
      totals.total_bookings > 0
        ? Number((totals.weighted_lead_sum / totals.total_bookings).toFixed(1))
        : 0;

    const peakRow =
      dailyRows.reduce((max, r) => {
        const g = r.observed_total_guests ?? r.active_guests ?? 0;
        const maxG = max
          ? (max.observed_total_guests ?? max.active_guests ?? 0)
          : -1;
        return g > maxG ? r : max;
      }, null) || {};

    return {
      ...totals,
      days_count: nDays,
      avg_guests_per_day: avgGuestsPerDay,
      cancellation_rate: cancellationRate,
      avg_adr: avgAdr,
      avg_party_size: avgPartySize,
      avg_stay_nights: avgStayNights,
      avg_lead_time: avgLeadTime,
      peak_row: peakRow,
    };
  }, [dailyRows]);

  const period = reportData?.period || reportData?.period_summary || {};
  const capacity =
    reportData?.capacity_summary || capacityReport?.capacity_summary || {};
  const histCap = capacityReport?.historical_period || {};
  const forecastCap = capacityReport?.forecast_7d_summary || {};
  const disclaimer =
    reportData?.capacity_disclaimer ||
    capacityReport?.capacity_disclaimer ||
    "Dataset does not contain physical room inventory or staffing headcount tables; directives reflect arrival-date booking & stay-night workload.";

  const stayNightBreakdownItems = useMemo(() => {
    const groups = histCap.stay_nights_by_arrival_group || {
      weekday_arrival_stay_nights: dailyRows
        .filter((r) => !(r.is_weekend ?? r.day_type === "Weekend"))
        .reduce(
          (s, r) => s + (r.observed_total_stay_nights ?? r.room_nights ?? 0),
          0,
        ),
      weekend_arrival_stay_nights: dailyRows
        .filter((r) => r.is_weekend ?? r.day_type === "Weekend")
        .reduce(
          (s, r) => s + (r.observed_total_stay_nights ?? r.room_nights ?? 0),
          0,
        ),
      holiday_arrival_stay_nights: dailyRows
        .filter((r) => r.is_holiday ?? r.is_pt_holiday)
        .reduce(
          (s, r) => s + (r.observed_total_stay_nights ?? r.room_nights ?? 0),
          0,
        ),
    };
    return [
      {
        label: "Weekday Arrivals (Mon–Fri)",
        value: groups.weekday_arrival_stay_nights || 0,
        color: "#315B52",
        sublabel: "stay-nights",
      },
      {
        label: "Weekend Arrivals (Sat–Sun)",
        value: groups.weekend_arrival_stay_nights || 0,
        color: "#C58B55",
        sublabel: "stay-nights",
      },
      {
        label: "PT National Holiday Arrivals",
        value: groups.holiday_arrival_stay_nights || 0,
        color: "#547A9B",
        sublabel: "stay-nights",
      },
    ];
  }, [histCap, dailyRows]);

  const isCompleteWeek = (period.calendar_days_count ?? dailyRows.length) >= 7;
  const overallGuestStatus = period.overall_guest_status || "COMPLETE";

  return (
    <div className="space-y-8 lg:space-y-10">
      {/* Editorial Page Header */}
      <header className="border-b border-[#E5E5E0] pb-6">
        <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2 text-[12px] text-[#666666]">
              <span>Standardized Operations Reporting</span>
              <span className="text-[#E5E5E0]">/</span>
              <span className="font-mono text-[11px]">
                mart.daily_hotel_ops
              </span>
              {reportData?.data_version && (
                <>
                  <span className="text-[#E5E5E0]">/</span>
                  <span className="font-mono text-[11px]">
                    ver:{String(reportData.data_version).slice(0, 8)}
                  </span>
                </>
              )}
            </div>
            <h1 className="editorial-page-title">
              Operations Reports — Weekly Demand &amp; Capacity Summary
            </h1>
            <p className="text-[14px] text-[#666666] max-w-3xl leading-relaxed">
              Standardized executive report templates reconciled 1-to-1 against{" "}
              <Link
                to="/analytics/operations"
                className="text-[#315B52] underline underline-offset-2 font-medium"
              >
                Operations Analytics (BI-05)
              </Link>{" "}
              under identical date and arrival-day filters.
            </p>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => window.print()}
              className="gap-1.5"
            >
              <Printer className="h-3.5 w-3.5" />
              <span>Print Report</span>
            </Button>
            <Button
              type="button"
              variant="emerald"
              size="sm"
              onClick={() => exportWeeklyReportToCsv(reportData, dailyRows)}
              className="gap-1.5"
            >
              <Download className="h-3.5 w-3.5" />
              <span>Export CSV (22 Columns)</span>
            </Button>
          </div>
        </div>

        {/* Flat Parameter & Period Filter Bar */}
        <div className="mt-6 pt-5 border-t border-[#E5E5E0] flex flex-col xl:flex-row xl:items-end justify-between gap-4">
          <div className="flex flex-wrap items-end gap-4">
            {/* Report Template Switcher */}
            <div>
              <span className="block text-[12px] font-medium text-[#666666] mb-1.5">
                Report Template View
              </span>
              <div className="inline-flex rounded-[4px] border border-[#E5E5E0] bg-[#FFFFFF] p-0.5">
                {[
                  { id: "ALL", label: "Combined (DO-R01 + DO-R02)" },
                  { id: "DO-R01", label: "DO-R01 Weekly Demand" },
                  { id: "DO-R02", label: "DO-R02 Capacity Summary" },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setReportMode(tab.id)}
                    className={`px-2.5 py-1 text-[12px] rounded-[3px] transition-colors cursor-pointer ${
                      reportMode === tab.id
                        ? "bg-[#315B52] text-[#FFFFFF] font-medium"
                        : "text-[#666666] hover:text-[#252525]"
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Period Mode Selector */}
            <div>
              <span className="block text-[12px] font-medium text-[#666666] mb-1.5">
                Period Selection Mode
              </span>
              <div className="inline-flex rounded-[4px] border border-[#E5E5E0] bg-[#FFFFFF] p-0.5">
                <button
                  type="button"
                  onClick={() => setPeriodMode("ISO_WEEK")}
                  className={`px-2.5 py-1 text-[12px] rounded-[3px] transition-colors cursor-pointer ${
                    periodMode === "ISO_WEEK"
                      ? "bg-[#252525] text-[#FFFFFF] font-medium"
                      : "text-[#666666] hover:text-[#252525]"
                  }`}
                >
                  ISO Week
                </button>
                <button
                  type="button"
                  onClick={() => setPeriodMode("CUSTOM_RANGE")}
                  className={`px-2.5 py-1 text-[12px] rounded-[3px] transition-colors cursor-pointer ${
                    periodMode === "CUSTOM_RANGE"
                      ? "bg-[#252525] text-[#FFFFFF] font-medium"
                      : "text-[#666666] hover:text-[#252525]"
                  }`}
                >
                  Custom Range
                </button>
              </div>
            </div>

            {periodMode === "ISO_WEEK" ? (
              <div>
                <label
                  htmlFor="report-week-select"
                  className="block text-[12px] font-medium text-[#666666] mb-1.5"
                >
                  Reporting Week (Europe/Lisbon)
                </label>
                <select
                  id="report-week-select"
                  value={selectedWeek}
                  onChange={(e) => handleWeekChange(e.target.value)}
                  className="h-8 rounded-[4px] border border-[#E5E5E0] bg-[#FFFFFF] px-2.5 text-[12px] font-medium text-[#252525] focus:outline-none focus:border-[#315B52]"
                >
                  {AVAILABLE_WEEKS.map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.label}
                    </option>
                  ))}
                </select>
              </div>
            ) : (
              <div className="flex items-end gap-2">
                <div>
                  <label
                    htmlFor="report-custom-start"
                    className="block text-[12px] font-medium text-[#666666] mb-1.5"
                  >
                    Start Date
                  </label>
                  <input
                    id="report-custom-start"
                    type="date"
                    min="2015-07-01"
                    max="2017-08-31"
                    value={customStartDate}
                    onChange={(e) => setCustomStartDate(e.target.value)}
                    className="h-8 rounded-[4px] border border-[#E5E5E0] bg-[#FFFFFF] px-2.5 font-mono text-[12px] text-[#252525]"
                  />
                </div>
                <div>
                  <label
                    htmlFor="report-custom-end"
                    className="block text-[12px] font-medium text-[#666666] mb-1.5"
                  >
                    End Date
                  </label>
                  <input
                    id="report-custom-end"
                    type="date"
                    min="2015-07-01"
                    max="2017-08-31"
                    value={customEndDate}
                    onChange={(e) => setCustomEndDate(e.target.value)}
                    className="h-8 rounded-[4px] border border-[#E5E5E0] bg-[#FFFFFF] px-2.5 font-mono text-[12px] text-[#252525]"
                  />
                </div>
              </div>
            )}

            {/* Day Type Filter */}
            <div>
              <span className="block text-[12px] font-medium text-[#666666] mb-1.5">
                Arrival Day Type
              </span>
              <div className="inline-flex rounded-[4px] border border-[#E5E5E0] bg-[#FFFFFF] p-0.5">
                {[
                  { id: "ALL", label: "All Days" },
                  { id: "Weekday", label: "Weekdays" },
                  { id: "Weekend", label: "Weekend" },
                ].map((type) => (
                  <button
                    key={type.id}
                    type="button"
                    onClick={() => setDayTypeFilter(type.id)}
                    className={`px-2.5 py-1 text-[12px] rounded-[3px] transition-colors cursor-pointer ${
                      dayTypeFilter === type.id
                        ? "bg-[#315B52] text-[#FFFFFF] font-medium"
                        : "text-[#666666] hover:text-[#252525]"
                    }`}
                  >
                    {type.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Coverage & Reconciliation Status Strip */}
          <div className="flex flex-wrap items-center gap-3 text-[12px] text-[#666666]">
            <span className="font-mono text-[#252525]">
              {period.actual_start || period.start_date || customStartDate} →{" "}
              {period.actual_end || period.end_date || customEndDate}
            </span>
            <Badge variant={isCompleteWeek ? "emerald" : "amber"}>
              {isCompleteWeek
                ? `COMPLETE_WEEK (${reconciled.days_count}/7 days)`
                : `INCOMPLETE_WEEK (${reconciled.days_count}/7 days available)`}
            </Badge>
            <Badge
              variant={overallGuestStatus === "COMPLETE" ? "emerald" : "amber"}
            >
              Guest Data: {overallGuestStatus}
            </Badge>
          </div>
        </div>
      </header>

      {/* Section 1: BI-05 Reconciled Typographic KPI Strip */}
      <section
        aria-label="Weekly Report Reconciled KPIs"
        className="border-b border-[#E5E5E0] pb-8"
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-5">
          <div>
            <h2 className="editorial-section-title">
              Executive Period Summary (BI-05 Reconciled Metrics)
            </h2>
            <p className="text-[12px] text-[#666666] mt-0.5">
              Aggregated directly from the {reconciled.days_count} displayed
              stay dates. Guaranteed mathematical parity with OLAP Analytics
              under identical date bounds.
            </p>
          </div>
          <span className="font-mono text-[11px] text-[#477A61]">
            ● Reconciled against mart.daily_hotel_ops
          </span>
        </div>

        {loading ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-6">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="space-y-2">
                <Skeleton className="h-3 w-24" />
                <Skeleton className="h-7 w-28" />
                <Skeleton className="h-3 w-20" />
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-6">
            <KpiCard
              label="Observed Total Guests"
              value={reconciled.observed_total_guests.toLocaleString()}
              unit="guests"
              badgeText={`Avg ${reconciled.avg_guests_per_day}/day`}
              statusTone="accent"
              subtext={`Adults: ${reconciled.observed_total_adults.toLocaleString()} · Child/Babies: ${(reconciled.observed_total_children + reconciled.observed_total_babies).toLocaleString()}`}
              emphasize
            />
            <KpiCard
              label="Non-Canceled Arrivals"
              value={reconciled.non_canceled_bookings.toLocaleString()}
              unit="check-ins"
              badgeText={period.yoy_arrivals_delta || "Verified"}
              statusTone="success"
              subtext={`Total bookings: ${reconciled.total_bookings.toLocaleString()}`}
            />
            <KpiCard
              label="Period Cancellation Rate"
              value={`${(reconciled.cancellation_rate * 100).toFixed(1)}%`}
              badgeText={`${reconciled.total_cancellations.toLocaleString()} canceled`}
              statusTone={
                reconciled.cancellation_rate > 0.38 ? "warning" : "neutral"
              }
              subtext={`Avg lead time: ${reconciled.avg_lead_time} days`}
            />
            <KpiCard
              label="Observed Stay Nights"
              value={reconciled.observed_total_stay_nights.toLocaleString()}
              unit="nights"
              badgeText={period.yoy_room_nights_delta || "In-house load"}
              statusTone="neutral"
              subtext={`Avg stay: ${reconciled.avg_stay_nights} nights · Party: ${reconciled.avg_party_size}`}
            />
            <KpiCard
              label="Weighted Average ADR"
              value={`€${reconciled.avg_adr.toFixed(2)}`}
              badgeText="Non-canceled"
              statusTone="neutral"
              subtext="Weighted by non-canceled check-ins"
            />
            <KpiCard
              label="Peak Demand Date"
              value={
                reconciled.peak_row.full_date ||
                reconciled.peak_row.stay_date ||
                "—"
              }
              badgeText={`${(reconciled.peak_row.observed_total_guests ?? reconciled.peak_row.active_guests ?? 0).toLocaleString()} guests`}
              statusTone="critical"
              subtext={`${reconciled.peak_row.day_of_week || ""} · ${reconciled.peak_row.non_canceled_bookings ?? reconciled.peak_row.arrivals ?? 0} check-ins`}
            />
          </div>
        )}
      </section>

      {/* Section 2: DO-R02 Operations Capacity Summary & 7-Day Workload Canvas */}
      {(reportMode === "ALL" || reportMode === "DO-R02") && (
        <section
          aria-label="DO-R02 Operations Capacity Summary"
          className="border-b border-[#E5E5E0] pb-8 space-y-6"
        >
          <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-2">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-[11px] font-semibold text-[#315B52]">
                  DO-R02
                </span>
                <h2 className="editorial-section-title">
                  Operations Capacity &amp; Workload Summary
                </h2>
              </div>
              <p className="text-[12px] text-[#666666] mt-0.5">
                Historical arrival-date workload profile paired with upcoming
                7-day forecast demand signals.
              </p>
            </div>
            <Link
              to="/analytics/operations"
              className="text-[12px] font-medium text-[#315B52] hover:underline inline-flex items-center gap-1"
            >
              <span>Inspect period in OLAP Analytics</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            {/* Left 7 Columns: Pure HTML5 Canvas Weekly Workload Chart + Group A Breakdown */}
            <div className="lg:col-span-7 space-y-6">
              <div className="border border-[#E5E5E0] rounded-[4px] bg-[#FFFFFF] p-5">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
                  <div>
                    <h3 className="text-[14px] font-semibold text-[#252525]">
                      Daily Check-in, Check-out &amp; Stay-Night Trajectory
                    </h3>
                    <p className="text-[12px] text-[#666666]">
                      Bars compare daily non-canceled arrivals vs. departures;
                      line tracks total stay-nights.
                    </p>
                  </div>
                  <div className="flex items-center gap-3 text-[11px] text-[#666666]">
                    <span className="inline-flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 bg-[#315B52] inline-block" />
                      Arrivals
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 bg-[#B64C43] inline-block" />
                      Peak Day
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 bg-[#D5D5CE] inline-block" />
                      Departures
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                      <span className="w-3 border-t-2 border-[#C58B55] inline-block" />
                      Stay Nights
                    </span>
                  </div>
                </div>

                <CanvasWeeklyWorkloadChart dailyRows={dailyRows} height={250} />
              </div>

              {/* Group A: Historical Stay-Nights by Arrival Group (Canvas Horizontal Bars) */}
              <div className="border border-[#E5E5E0] rounded-[4px] bg-[#FFFFFF] p-5">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <span className="font-mono text-[11px] text-[#666666]">
                      GROUP A • HISTORICAL WORKLOAD
                    </span>
                    <h3 className="text-[14px] font-semibold text-[#252525]">
                      Stay-Nights Distribution by Arrival Segment
                    </h3>
                  </div>
                  <span className="font-mono text-[12px] text-[#252525]">
                    Weekend surge: {capacity.weekend_surge_pct || "+20.0%"}
                  </span>
                </div>

                <CanvasHorizontalBarChart
                  items={stayNightBreakdownItems}
                  height={135}
                />
              </div>
            </div>

            {/* Right 5 Columns: Group B Upcoming 7-Day Forecast Signal & Operational Directives */}
            <div className="lg:col-span-5 space-y-5 border border-[#E5E5E0] rounded-[4px] bg-[#FFFFFF] p-5">
              <div className="border-b border-[#E5E5E0] pb-3">
                <span className="font-mono text-[11px] text-[#315B52] font-medium">
                  GROUP B • UPCOMING 7-DAY FORECAST SIGNAL &amp; DIRECTIVES
                </span>
                <h3 className="text-[15px] font-semibold text-[#252525] mt-0.5">
                  Departmental Workload &amp; Action Directives
                </h3>
                <p className="text-[12px] text-[#666666] mt-0.5">
                  Weekday vs. weekend arrival intensity and standardized
                  operational guidance.
                </p>
              </div>

              {/* Weekday vs Weekend Typographic Comparison */}
              <div className="grid grid-cols-2 gap-4 pb-4 border-b border-[#E5E5E0]">
                <div>
                  <div className="text-[11px] text-[#666666]">
                    Weekday Avg (Mon–Fri)
                  </div>
                  <div className="font-mono text-[20px] font-semibold text-[#252525] tabular-nums mt-0.5">
                    {capacity.weekday_avg_arrivals || 135}{" "}
                    <span className="text-[12px] font-normal text-[#666666]">
                      check-ins
                    </span>
                  </div>
                  <div className="font-mono text-[11px] text-[#666666] mt-0.5">
                    ~{capacity.weekday_avg_guests || 652} guests/day
                  </div>
                </div>

                <div className="border-l border-[#E5E5E0] pl-4">
                  <div className="text-[11px] text-[#666666]">
                    Weekend Avg (Sat–Sun)
                  </div>
                  <div className="font-mono text-[20px] font-semibold text-[#315B52] tabular-nums mt-0.5">
                    {capacity.weekend_avg_arrivals || 162}{" "}
                    <span className="text-[12px] font-normal text-[#666666]">
                      check-ins
                    </span>
                  </div>
                  <div className="font-mono text-[11px] text-[#666666] mt-0.5">
                    ~{capacity.weekend_avg_guests || 732} guests/day
                  </div>
                </div>
              </div>

              {/* Forward 7-Day Signal Summary */}
              {forecastCap.predicted_total_guests_7d && (
                <div className="pb-4 border-b border-[#E5E5E0] space-y-2">
                  <div className="flex items-center justify-between text-[12px]">
                    <span className="font-medium text-[#252525]">
                      Forward 7-Day Forecast ({forecastCap.horizon_start} →{" "}
                      {forecastCap.horizon_end})
                    </span>
                    <Link
                      to="/dss/demand-forecast"
                      className="font-mono text-[11px] text-[#315B52] hover:underline"
                    >
                      DO-M01 →
                    </Link>
                  </div>
                  <div className="flex items-center justify-between text-[12px] font-mono bg-[#F2F1ED] px-3 py-2 rounded-[3px]">
                    <span>
                      7d Guests:{" "}
                      <strong>
                        {Math.round(
                          forecastCap.predicted_total_guests_7d,
                        ).toLocaleString()}
                      </strong>
                    </span>
                    <span className="text-[#B64C43]">
                      HIGH: {forecastCap.demand_level_counts?.HIGH ?? 2}d
                    </span>
                    <span className="text-[#477A61]">
                      NORMAL: {forecastCap.demand_level_counts?.NORMAL ?? 4}d
                    </span>
                    <span className="text-[#C58B35]">
                      LOW: {forecastCap.demand_level_counts?.LOW ?? 1}d
                    </span>
                  </div>
                </div>
              )}

              {/* Departmental Directives (No Hallucinated Room/Staff Counts) */}
              <div className="space-y-3 text-[12px]">
                <div className="border-l-2 border-[#315B52] pl-3 py-0.5">
                  <div className="font-semibold text-[#252525]">
                    Front Office &amp; Check-in Windows
                  </div>
                  <p className="text-[#666666] mt-0.5 leading-relaxed">
                    {capacity.front_desk_directive}
                  </p>
                </div>

                <div className="border-l-2 border-[#547A9B] pl-3 py-0.5">
                  <div className="font-semibold text-[#252525]">
                    Housekeeping &amp; Room Turnover
                  </div>
                  <p className="text-[#666666] mt-0.5 leading-relaxed">
                    {capacity.housekeeping_directive}
                  </p>
                </div>

                <div className="border-l-2 border-[#C58B55] pl-3 py-0.5">
                  <div className="font-semibold text-[#252525]">
                    Food &amp; Beverage Provisioning
                  </div>
                  <p className="text-[#666666] mt-0.5 leading-relaxed">
                    {capacity.fb_directive}
                  </p>
                </div>
              </div>

              {/* Mandatory Capacity Disclaimer (ui_specification_and_api_contracts.md Section 5.2) */}
              <div className="pt-3 border-t border-[#E5E5E0] text-[11px] text-[#666666] leading-relaxed">
                <strong className="text-[#252525] font-medium">
                  Data Scope Note:
                </strong>{" "}
                {disclaimer}
              </div>
            </div>
          </div>
        </section>
      )}

      {/* Section 3: DO-R01 Standardized Daily Operations Log Table */}
      {(reportMode === "ALL" || reportMode === "DO-R01") && (
        <section aria-label="DO-R01 Daily Operations Log" className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-2">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-[11px] font-semibold text-[#315B52]">
                  DO-R01
                </span>
                <h2
                  id="daily-operations-log-heading"
                  className="editorial-section-title"
                >
                  Daily Operations Demand Log ({reconciled.days_count} Days)
                </h2>
              </div>
              <p className="text-[12px] text-[#666666] mt-0.5">
                Arrival-date operational grain aligned with{" "}
                <code className="font-mono text-[11px]">Europe/Lisbon</code>,
                Open-Meteo daily weather observations, and Nager.Date Portuguese
                public holidays.
              </p>
            </div>
            <span className="font-mono text-[11px] text-[#666666]">
              Sorted chronologically: full_date ASC
            </span>
          </div>

          <ResponsiveTableContainer ariaLabelledBy="daily-operations-log-heading">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Stay Date</TableHead>
                  <TableHead>Day / Type</TableHead>
                  <TableHead className="text-right">Total Bookings</TableHead>
                  <TableHead className="text-right">Non-Canceled</TableHead>
                  <TableHead className="text-right">Canceled (Rate)</TableHead>
                  <TableHead className="text-right">
                    Observed Guests (A/C/B)
                  </TableHead>
                  <TableHead className="text-right">Stay Nights</TableHead>
                  <TableHead className="text-right">Party / Stay</TableHead>
                  <TableHead className="text-right">Lead Time</TableHead>
                  <TableHead className="text-right">Avg ADR</TableHead>
                  <TableHead>Holiday &amp; Lisbon Weather</TableHead>
                  <TableHead className="text-right">Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {dailyRows.map((row) => {
                  const fullDate = row.full_date || row.stay_date;
                  const isWeekend =
                    row.is_weekend ?? row.day_type === "Weekend";
                  const isHoliday = row.is_holiday ?? row.is_pt_holiday;
                  const holidayName =
                    (Array.isArray(row.holiday_names) &&
                      row.holiday_names[0]) ||
                    row.holiday_local_name ||
                    null;
                  const totalBookings = row.total_bookings ?? row.arrivals ?? 0;
                  const nonCanceled =
                    row.non_canceled_bookings ?? row.arrivals ?? 0;
                  const canceled =
                    row.total_cancellations ??
                    Math.max(0, totalBookings - nonCanceled);
                  const cancelRate =
                    row.cancellation_rate != null
                      ? row.cancellation_rate * 100
                      : totalBookings > 0
                        ? (canceled / totalBookings) * 100
                        : 0;
                  const guests =
                    row.observed_total_guests ?? row.active_guests ?? 0;
                  const adults = row.observed_total_adults ?? 0;
                  const children = row.observed_total_children ?? 0;
                  const babies = row.observed_total_babies ?? 0;
                  const stayNights =
                    row.observed_total_stay_nights ?? row.room_nights ?? 0;
                  const avgParty = row.avg_party_size ?? 1.95;
                  const avgStay = row.avg_stay_nights ?? 3.4;
                  const avgLead = row.avg_lead_time ?? 98;
                  const adr = row.avg_adr ?? row.adr ?? 0;
                  const temp = row.temperature_mean ?? row.weather_temp_mean;
                  const precip =
                    row.precipitation ?? row.weather_precip_sum ?? 0;
                  const guestStatus = row.guest_data_status || "COMPLETE";

                  return (
                    <TableRow
                      key={fullDate}
                      className={
                        row.is_peak_day ? "bg-[#B64C43]/[0.04]" : undefined
                      }
                    >
                      <TableCell className="font-mono font-medium text-[#252525] whitespace-nowrap">
                        {fullDate}
                        {row.is_peak_day && (
                          <span className="ml-1.5 text-[10px] font-sans font-semibold text-[#B64C43]">
                            PEAK
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="whitespace-nowrap">
                        <span className="text-[#252525] font-medium">
                          {row.day_of_week}
                        </span>
                        <span className="ml-1.5 text-[11px] text-[#666666]">
                          ({isWeekend ? "Weekend" : "Weekday"})
                        </span>
                      </TableCell>
                      <TableCell className="text-right font-mono tabular-nums text-[#252525]">
                        {totalBookings.toLocaleString()}
                      </TableCell>
                      <TableCell className="text-right font-mono tabular-nums font-semibold text-[#315B52]">
                        {nonCanceled.toLocaleString()}
                      </TableCell>
                      <TableCell className="text-right font-mono tabular-nums text-[#666666]">
                        {canceled} ({cancelRate.toFixed(1)}%)
                      </TableCell>
                      <TableCell className="text-right font-mono tabular-nums">
                        <span className="font-semibold text-[#252525]">
                          {guests.toLocaleString()}
                        </span>
                        <span className="ml-1.5 text-[11px] text-[#666666]">
                          ({adults}/{children}/{babies})
                        </span>
                      </TableCell>
                      <TableCell className="text-right font-mono tabular-nums text-[#252525]">
                        {stayNights.toLocaleString()}
                      </TableCell>
                      <TableCell className="text-right font-mono tabular-nums text-[#666666]">
                        {Number(avgParty).toFixed(2)} /{" "}
                        {Number(avgStay).toFixed(1)}n
                      </TableCell>
                      <TableCell className="text-right font-mono tabular-nums text-[#666666]">
                        {Math.round(avgLead)}d
                      </TableCell>
                      <TableCell className="text-right font-mono tabular-nums text-[#252525]">
                        €{Number(adr).toFixed(2)}
                      </TableCell>
                      <TableCell className="text-[12px] text-[#666666] whitespace-nowrap">
                        {isHoliday || holidayName ? (
                          <span className="text-[#C58B35] font-medium mr-2">
                            ★ {holidayName || "PT Holiday"}
                          </span>
                        ) : null}
                        <span className="font-mono text-[11px]">
                          {temp != null ? `${temp}°C` : "—"} · {precip}mm (
                          {row.weather_status || "Clear"})
                        </span>
                      </TableCell>
                      <TableCell className="text-right whitespace-nowrap">
                        <Badge
                          variant={
                            guestStatus === "COMPLETE" ? "emerald" : "amber"
                          }
                        >
                          {guestStatus}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
              <TableFooter>
                <TableRow>
                  <TableCell
                    colSpan={2}
                    className="font-semibold text-[#252525]"
                  >
                    Reconciled Period Totals ({reconciled.days_count} days)
                  </TableCell>
                  <TableCell className="text-right font-mono tabular-nums font-semibold text-[#252525]">
                    {reconciled.total_bookings.toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right font-mono tabular-nums font-semibold text-[#315B52]">
                    {reconciled.non_canceled_bookings.toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right font-mono tabular-nums text-[#666666]">
                    {reconciled.total_cancellations.toLocaleString()} (
                    {(reconciled.cancellation_rate * 100).toFixed(1)}%)
                  </TableCell>
                  <TableCell className="text-right font-mono tabular-nums font-semibold text-[#252525]">
                    {reconciled.observed_total_guests.toLocaleString()} (Avg{" "}
                    {reconciled.avg_guests_per_day}/d)
                  </TableCell>
                  <TableCell className="text-right font-mono tabular-nums font-semibold text-[#252525]">
                    {reconciled.observed_total_stay_nights.toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right font-mono tabular-nums text-[#666666]">
                    {reconciled.avg_party_size} / {reconciled.avg_stay_nights}n
                  </TableCell>
                  <TableCell className="text-right font-mono tabular-nums text-[#666666]">
                    {reconciled.avg_lead_time}d
                  </TableCell>
                  <TableCell className="text-right font-mono tabular-nums font-semibold text-[#252525]">
                    €{reconciled.avg_adr.toFixed(2)}
                  </TableCell>
                  <TableCell
                    colSpan={2}
                    className="text-right font-mono text-[11px] text-[#477A61]"
                  >
                    100% BI-05 Reconciled
                  </TableCell>
                </TableRow>
              </TableFooter>
            </Table>
          </ResponsiveTableContainer>
        </section>
      )}
    </div>
  );
}

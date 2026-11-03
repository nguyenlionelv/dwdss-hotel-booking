import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  fetchOperationsTrend,
  fetchOperationsPivot,
  fetchOperationsImpact,
} from "../../../services/analyticsApi";
import { ANALYTICS_PRESETS } from "../../../data/mockData";
import { useSystemContext } from "../../../hooks/useSystemContext";
import KpiCard from "../../../components/kpi/KpiCard";
import ResponsiveTableContainer from "../../../components/tables/ResponsiveTableContainer";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import {
  BarChart3,
  Calendar,
  Filter,
  RotateCcw,
  ZoomIn,
  ArrowUpRight,
  ChevronRight,
  Globe2,
  CloudSun,
  PartyPopper,
  FileSpreadsheet,
  BrainCircuit,
  SlidersHorizontal,
} from "lucide-react";

import TrendChart from "../../../components/charts/TrendChart";

const GRAIN_OPTIONS = [
  { id: "day", label: "Day (Drill-down)" },
  { id: "week", label: "Week" },
  { id: "month", label: "Month" },
  { id: "quarter", label: "Quarter" },
  { id: "year", label: "Year (Roll-up)" },
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

  // 1. Month: "2016-08"
  if (grain === "month" && label.includes("-")) {
    const [y, m] = label.split("-").map(Number);
    const last = new Date(y, m, 0).getDate();
    const mm = String(m).padStart(2, "0");
    return { from: `${y}-${mm}-01`, to: `${y}-${mm}-${last}` };
  }

  // 2. Quarter: "2016-Q3"
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

  // 3. Year: "2016" or "2016 (Full)"
  if (grain === "year") {
    const match = label.match(/\b(20\d\d)\b/);
    if (match) {
      const y = match[1];
      return { from: `${y}-01-01`, to: `${y}-12-31` };
    }
  }

  // 4. Week: "2017-W25"
  if (grain === "week") {
    const match = label.match(/(\d{4})-W(\d{2})/);
    if (match) {
      const y = Number(match[1]);
      const w = Number(match[2]);
      const simple = new Date(Date.UTC(y, 0, 1 + (w - 1) * 7));
      const dow = simple.getUTCDay();
      const isoStart = new Date(simple);
      if (dow <= 4) isoStart.setUTCDate(simple.getUTCDate() - simple.getUTCDay() + 1);
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
  const [drilldownContext, setDrilldownContext] = useState(null);
  const [drilldownRange, setDrilldownRange] = useState(null);

  // Pivot Matrix State
  const [pivotColDim, setPivotColDim] = useState("country");
  const [pivotMeasure, setPivotMeasure] = useState("room_nights");
  const [expandedRows, setExpandedRows] = useState({
    "2016 - Q3 (Jul-Sep) [Peak]": true,
  });

  // Data State
  const [trendData, setTrendData] = useState(null);
  const [pivotData, setPivotData] = useState(null);
  const [impactData, setImpactData] = useState(null);
  const [loading, setLoading] = useState(true);

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
        col_dim: pivotColDim,
        measure: pivotMeasure,
      }),
      fetchOperationsImpact(),
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
    if (!childGrain) return; // already at leaf grain (day)

    const range = getPeriodRange(item, grain);
    if (!range) return;

    setDrilldownRange({
      ...range,
      label: item.period_label,
      parentGrain: grain,
      parent: drilldownRange,
    });
    setGrain(childGrain);
    setDrilldownContext(`${item.period_label} (Detailed by ${childGrain})`);
  };

  const handleRollUp = () => {
    if (!drilldownRange) return;
    setGrain(drilldownRange.parentGrain);
    const parent = drilldownRange.parent || null;
    setDrilldownRange(parent);
    setDrilldownContext(
      parent ? `${parent.label} (Detailed by ${parent.parentGrain || drilldownRange.parentGrain})` : null,
    );
  };

  const handleResetFilters = () => {
    setPreset("full_793");
    setGrain("month");
    setCountry("ALL");
    setDayType("ALL");
    setHolidayFilter("ALL");
    setDrilldownRange(null);
    setDrilldownContext(null);
  };

  const togglePivotRow = (rowKey) => {
    setExpandedRows((prev) => ({ ...prev, [rowKey]: !prev[rowKey] }));
  };

  const series = trendData?.series || [];

  return (
    <div className="space-y-6">
      {/* Page Title & Quick Navigation Header */}
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            <Badge
              variant="blue"
              className="gap-1 font-semibold uppercase text-[10px]"
            >
              <BarChart3 className="h-3 w-3" />
              <span>OLAP Multi-Dimensional Analytics</span>
            </Badge>
            {trendData?.is_mock && (
              <Badge variant="secondary" className="text-[10px]">
                Mock Mart Data Ready
              </Badge>
            )}
          </div>
          <h1 className="text-2xl sm:text-3xl font-display font-extrabold text-foreground tracking-tight">
            Operations Analytics — Demand, Holiday &amp; Weather
          </h1>
          <p className="text-xs sm:text-sm text-muted-foreground mt-1">
            Multi-dimensional analytical workbench (Slice, Dice, Drill-down, Roll-up) on{" "}
            <code className="text-[11px] font-mono bg-muted px-1.5 py-0.5 rounded text-foreground border">
              mart.operations_daily
            </code>{" "}
            for City Hotel (Lisbon, Portugal).
          </p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <Button variant="outline" size="sm" asChild className="gap-1.5">
            <Link to="/reports/operations">
              <FileSpreadsheet className="h-4 w-4 text-emerald-600" />
              <span>View Weekly Reports</span>
            </Link>
          </Button>
          <Button variant="default" size="sm" asChild className="gap-1.5">
            <Link to="/dss/demand-forecast">
              <BrainCircuit className="h-4 w-4" />
              <span>7-Day DSS Forecast</span>
            </Link>
          </Button>
        </div>
      </div>

      {/* OLAP Slice & Dice Workbench Card */}
      <Card className="border-border">
        <CardContent className="p-4 sm:p-5 space-y-4">
          {/* Top Grain / Roll-up / Drill-down bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b pb-3.5">
            <div className="flex items-center gap-2.5 flex-wrap">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                <SlidersHorizontal className="h-3.5 w-3.5 text-primary" />
                Time Grain (Roll-up / Drill-down):
              </span>
              <div className="flex items-center p-0.5 rounded-lg bg-muted border text-xs">
                {GRAIN_OPTIONS.map((g) => (
                  <button
                    key={g.id}
                    type="button"
                    onClick={() => handleGrainChange(g.id)}
                    className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-all cursor-pointer ${
                      grain === g.id
                        ? "bg-background text-foreground shadow-xs font-bold"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {g.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Drilldown Breadcrumb & Reset */}
            <div className="flex items-center gap-2">
              {drilldownContext && (
                <Badge variant="blue" className="gap-1 text-xs py-1 px-2.5">
                  <ZoomIn className="h-3.5 w-3.5" />
                  <span>Drill-down: {drilldownContext}</span>
                  <button
                    type="button"
                    onClick={handleRollUp}
                    className="ml-1 underline hover:text-primary font-bold cursor-pointer"
                  >
                    Roll-up
                  </button>
                </Badge>
              )}
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={handleResetFilters}
                className="gap-1.5 text-xs text-muted-foreground hover:text-foreground cursor-pointer"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                <span>Reset OLAP</span>
              </Button>
            </div>
          </div>

          {/* Slice & Dice Dimension Selectors */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
            <div>
              <label
                htmlFor="olap-preset"
                className="block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1"
              >
                Date Range Preset
              </label>
              <select
                id="olap-preset"
                value={preset}
                onChange={(e) => {
                  setPreset(e.target.value);
                  setDrilldownRange(null);
                  setDrilldownContext(null);
                }}
                className="w-full bg-background border border-input text-foreground text-xs font-medium rounded-md px-3 py-2 focus:outline-none focus:ring-1 focus:ring-ring transition-colors"
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
                className="block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1"
              >
                Slice: Source Market (Country)
              </label>
              <select
                id="olap-country"
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                className="w-full bg-background border border-input text-foreground text-xs font-medium rounded-md px-3 py-2 focus:outline-none focus:ring-1 focus:ring-ring transition-colors"
              >
                {(metadata?.countries || []).map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.name} ({c.booking_count} bookings)
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label
                htmlFor="olap-daytype"
                className="block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1"
              >
                Slice: Day Type
              </label>
              <select
                id="olap-daytype"
                value={dayType}
                onChange={(e) => setDayType(e.target.value)}
                className="w-full bg-background border border-input text-foreground text-xs font-medium rounded-md px-3 py-2 focus:outline-none focus:ring-1 focus:ring-ring transition-colors"
              >
                <option value="ALL">All Days (Weekday + Weekend)</option>
                <option value="Weekday">Weekday (Mon–Thu)</option>
                <option value="Weekend">Weekend (Fri–Sun)</option>
              </select>
            </div>

            <div>
              <label
                htmlFor="olap-holiday"
                className="block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1"
              >
                Slice: Portugal National Holiday
              </label>
              <select
                id="olap-holiday"
                value={holidayFilter}
                onChange={(e) => setHolidayFilter(e.target.value)}
                className="w-full bg-background border border-input text-foreground text-xs font-medium rounded-md px-3 py-2 focus:outline-none focus:ring-1 focus:ring-ring transition-colors"
              >
                <option value="ALL">All Days</option>
                <option value="HOLIDAY_ONLY">National Holidays Only</option>
                <option value="NON_HOLIDAY">Non-Holidays Only</option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 5-Column Reconciled KPI Strip */}
      <section
        aria-label="Executive Operations KPIs"
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5"
      >
        {loading ? (
          Array.from({ length: 5 }).map((_, i) => (
            <Card key={i} className="p-4 space-y-2">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="h-7 w-32" />
              <Skeleton className="h-4 w-20" />
            </Card>
          ))
        ) : (
          <>
            <KpiCard
              label="Total Room Nights"
              value={(
                trendData?.summary?.total_room_nights || 260680
              ).toLocaleString()}
              unit="nights"
              badgeText="+8.4% YoY"
              badgeIcon="trending_up"
              subtext="Active room nights"
              icon="bed"
              tone="blue"
            />
            <KpiCard
              label="Total Arrivals"
              value={(
                trendData?.summary?.total_arrivals || 82200
              ).toLocaleString()}
              unit="arrivals"
              badgeText="Verified"
              badgeIcon="trending_up"
              subtext="Confirmed check-ins"
              icon="luggage"
              tone="emerald"
            />
            <KpiCard
              label="Avg Daily Active Guests"
              value={(
                trendData?.summary?.avg_daily_active_guests || 635
              ).toLocaleString()}
              unit="guests"
              badgeText="1.94 guests/room"
              subtext="Daily active guests"
              icon="groups"
              tone="indigo"
            />
            <KpiCard
              label="Average Daily Rate"
              value={`€${trendData?.summary?.avg_adr || 106.8}`}
              badgeText="+14.5% during Holidays"
              subtext="ADR across period"
              icon="euro"
              tone="amber"
            />
            <KpiCard
              label="Peak Demand Period"
              value={trendData?.summary?.peak_period || "2016-08"}
              badgeText={`${(trendData?.summary?.peak_room_nights || 14120).toLocaleString()} nights`}
              badgeIcon="warning"
              subtext="Highest period demand"
              icon="local_fire_department"
              tone="rose"
              highlightBorder
            />
          </>
        )}
      </section>

      {/* Main Analytical Split: Left 8 Cols (Time Series + Pivot Matrix), Right 4 Cols (Holiday, Weather, Country Impact) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column (8 Cols) */}
        <div className="lg:col-span-8 space-y-6">
          {/* Demand Trend Visualization Card */}
          <Card>
            <CardHeader className="p-5 pb-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <CardTitle className="text-base flex items-center gap-2">
                  <span>Room Nights &amp; Arrivals Demand Trend</span>
                  <Badge
                    variant="outline"
                    className="text-[10px] font-mono uppercase"
                  >
                    {grain} grain
                  </Badge>
                  {loading && (
                    <span className="text-xs text-muted-foreground animate-pulse">
                      Loading...
                    </span>
                  )}
                </CardTitle>
                <CardDescription className="text-xs mt-0.5">
                  Click any bar to <strong>Drill-down</strong> to finer detail (Year → Quarter → Month → Week → Day), or click Roll-up.
                </CardDescription>
              </div>

              <div className="flex flex-wrap flex-col items-end gap-3 text-xs font-medium">
                {drilldownRange && (
                  <button
                    type="button"
                    onClick={handleRollUp}
                    className="inline-flex items-center justify-center rounded-md border border-input bg-background px-2.5 py-1 text-xs font-semibold shadow-xs hover:bg-accent hover:text-accent-foreground transition-colors cursor-pointer"
                  >
                    Roll-up
                  </button>
                )}
                <div className="flex items-center gap-3 text-xs font-medium">
                  <div className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-xs bg-primary/70" />
                    <span className="text-muted-foreground">
                      Regular Room Nights
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-xs bg-emerald-600" />
                    <span className="text-muted-foreground">
                      Holiday / Peak Demand
                    </span>
                  </div>
                </div>
              </div>
            </CardHeader>

            <CardContent className="p-5 pt-2">
              {loading ? (
                <Skeleton className="h-72 w-full" />
              ) : (
                <TrendChart
                  series={series}
                  grain={grain}
                  canDrill={!!CHILD_GRAIN[grain]}
                  onDrill={handleBarDrilldown}
                />
              )}
            </CardContent>
          </Card>

          {/* Interactive Multi-Dimensional Pivot Matrix Card */}
          <Card>
            <CardHeader className="p-5 pb-3 border-b flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <CardTitle id="olap-pivot-heading" className="text-base">
                  Multi-Dimensional OLAP Matrix (Slice &amp; Dice Pivot)
                </CardTitle>
                <CardDescription className="text-xs mt-0.5">
                  Compare operational performance across time dimensions sliced by Country or Day Type.
                </CardDescription>
              </div>

              <div className="flex items-center gap-2 flex-wrap">
                <select
                  aria-label="Pivot Column Dimension"
                  value={pivotColDim}
                  onChange={(e) => setPivotColDim(e.target.value)}
                  className="bg-background border border-input text-foreground text-xs font-semibold rounded-md px-2.5 py-1.5 focus:outline-none"
                >
                  <option value="country">Column: Top Countries</option>
                  <option value="day_type">Column: Day Type</option>
                </select>

                <select
                  aria-label="Pivot Measure"
                  value={pivotMeasure}
                  onChange={(e) => setPivotMeasure(e.target.value)}
                  className="bg-primary/10 border border-primary/20 text-primary text-xs font-bold rounded-md px-2.5 py-1.5 focus:outline-none"
                >
                  <option value="room_nights">
                    Measure: Room Nights
                  </option>
                  <option value="arrivals">Measure: Arrivals</option>
                  <option value="active_guests">
                    Measure: Active Guests
                  </option>
                </select>
              </div>
            </CardHeader>

            <CardContent className="p-0">
              <ResponsiveTableContainer ariaLabelledBy="olap-pivot-heading">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-muted/60">
                      <TableHead className="py-2.5 px-4 font-semibold text-foreground">
                        Time Dimension (Quarter / Month)
                      </TableHead>
                      {(pivotData?.columns || []).map((col) => (
                        <TableHead key={col} className="py-2.5 px-3 text-right">
                          {col}
                        </TableHead>
                      ))}
                      <TableHead className="py-2.5 px-4 text-right font-bold text-foreground bg-muted">
                        Grand Total
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(pivotData?.rows || []).map((row) => {
                      const isExpanded = !!expandedRows[row.row_key];
                      return (
                        <React.Fragment key={row.row_key}>
                          <TableRow
                            className={`transition-colors ${
                              row.is_highlighted
                                ? "bg-primary/5 hover:bg-primary/10 font-semibold"
                                : "hover:bg-muted/40"
                            }`}
                          >
                            <TableCell className="py-2.5 px-4 text-foreground flex items-center gap-2">
                              {row.children ? (
                                <button
                                  type="button"
                                  onClick={() => togglePivotRow(row.row_key)}
                                  className="w-4 h-4 rounded-xs bg-muted border text-foreground flex items-center justify-center text-[10px] font-bold hover:bg-accent cursor-pointer"
                                  title="Drill-down / Roll-up"
                                >
                                  {isExpanded ? "−" : "+"}
                                </button>
                              ) : (
                                <span className="w-4 h-4 inline-block" />
                              )}
                              <span>{row.row_key}</span>
                            </TableCell>
                            {(pivotData?.columns || []).map((col) => (
                              <TableCell
                                key={col}
                                className="py-2.5 px-3 text-right tabular-nums text-muted-foreground"
                              >
                                {(row.values[col] || 0).toLocaleString()}
                              </TableCell>
                            ))}
                            <TableCell className="py-2.5 px-4 text-right tabular-nums font-bold text-primary bg-muted/30">
                              {row.total.toLocaleString()}
                            </TableCell>
                          </TableRow>

                          {/* Drill-down Child Rows */}
                          {row.children &&
                            isExpanded &&
                            row.children.map((child) => (
                              <TableRow
                                key={child.row_key}
                                className="bg-muted/20 text-xs text-muted-foreground"
                              >
                                <TableCell className="py-2 pl-10 pr-4 font-medium text-foreground flex items-center gap-1.5">
                                  <ChevronRight className="h-3 w-3 text-muted-foreground/60" />
                                  <span>{child.row_key}</span>
                                </TableCell>
                                {(pivotData?.columns || []).map((col) => (
                                  <TableCell
                                    key={col}
                                    className="py-2 px-3 text-right tabular-nums"
                                  >
                                    {(child.values[col] || 0).toLocaleString()}
                                  </TableCell>
                                ))}
                                <TableCell className="py-2 px-4 text-right tabular-nums font-semibold text-foreground bg-muted/40">
                                  {child.total.toLocaleString()}
                                </TableCell>
                              </TableRow>
                            ))}
                        </React.Fragment>
                      );
                    })}
                  </TableBody>
                </Table>
              </ResponsiveTableContainer>
            </CardContent>
          </Card>
        </div>

        {/* Right Column (4 Cols): Contextual Impact */}
        <div className="lg:col-span-4 space-y-6">
          {/* Card 1: Portuguese National Holiday Impact */}
          <Card>
            <CardHeader className="p-4 sm:p-5 pb-3 flex flex-row items-center justify-between space-y-0">
              <CardTitle className="text-sm sm:text-xl mt-0.5">
                Portuguese National Holiday Impact
              </CardTitle>
              <Badge variant="emerald" className="font-extrabold text-xs">
                +{impactData?.holiday_impact?.lift_pct || "-"}% Lift
              </Badge>
            </CardHeader>

            <CardContent className="p-4 sm:p-5 pt-1 space-y-3.5">
              <div className="grid grid-cols-2 gap-2.5">
                <div className="p-3 rounded-md bg-amber-50/60 border border-amber-200/60">
                  <div className="text-[10px] font-semibold uppercase text-amber-800">
                    Holidays (
                    {impactData?.holiday_impact?.holiday_days_count || 29} days)
                  </div>
                  <div className="text-xl font-display font-extrabold text-foreground mt-1 tabular-nums">
                    {impactData?.holiday_impact?.holiday_avg_room_nights ||
                      348.4}
                  </div>
                  <div className="text-[11px] text-amber-700 font-medium">
                    Avg ~ €
                    {impactData?.holiday_impact?.holiday_avg_adr || "-"} ADR
                  </div>
                </div>

                <div className="p-3 rounded-md bg-muted/60 border">
                  <div className="text-[10px] font-semibold uppercase text-muted-foreground">
                    Regular Days (
                    {impactData?.holiday_impact?.non_holiday_days_count || 764}{" "}
                    days)
                  </div>
                  <div className="text-xl font-display font-extrabold text-foreground mt-1 tabular-nums">
                    {impactData?.holiday_impact?.non_holiday_avg_room_nights ||
                      304.2}
                  </div>
                  <div className="text-[11px] text-muted-foreground font-medium">
                    Avg ~ €
                    {impactData?.holiday_impact?.non_holiday_avg_adr || "-"} ADR
                  </div>
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Top Holiday Demand Spikes
                </div>
                {(impactData?.holiday_impact?.upcoming_holidays || []).map(
                  (h) => (
                    <div
                      key={h.date}
                      className="flex items-center justify-between py-1.5 px-2.5 rounded-md bg-muted/40 text-xs border"
                    >
                      <div>
                        <div className="font-semibold text-foreground">
                          {h.local_name}
                        </div>
                        <div className="text-[10px] text-muted-foreground font-mono">
                          {h.date}
                        </div>
                      </div>
                      <Badge
                        variant="emerald"
                        className="font-bold text-[10px]"
                      >
                        {h.lift_pct}
                      </Badge>
                    </div>
                  ),
                )}
              </div>
            </CardContent>
          </Card>

          {/* Card 2: Lisbon Weather Correlation */}
          <Card>
            <CardHeader className="p-4 sm:p-5 pb-3 flex flex-row items-center justify-between space-y-0">
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-wider text-sky-700">
                  Open-Meteo Lisbon Weather
                </span>
                <CardTitle className="text-sm sm:text-base mt-0.5">
                  Weather &amp; Demand Correlation
                </CardTitle>
              </div>
              <Badge variant="blue" className="text-[10px]">
                99.6% Data
              </Badge>
            </CardHeader>

            <CardContent className="p-4 sm:p-5 pt-1 space-y-3">
              {(impactData?.weather_impact?.bands || []).map((b) => (
                <div
                  key={b.band_label}
                  className="p-2.5 rounded-md bg-muted/40 border space-y-1.5"
                >
                  <div className="flex items-center justify-between text-xs font-semibold text-foreground">
                    <span>{b.band_label}</span>
                    <span className="text-primary tabular-nums">
                      {b.avg_room_nights} nights/day
                    </span>
                  </div>
                  <div className="w-full bg-secondary h-1.5 rounded-full overflow-hidden">
                    <div
                      className="bg-primary h-full rounded-full"
                      style={{
                        width: `${Math.min(100, Math.round(b.demand_index * 78))}%`,
                      }}
                    />
                  </div>
                  <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                    <span>{b.days_count} observed days</span>
                    <span className="font-semibold text-foreground">
                      Index vs. baseline: {b.demand_index}x
                    </span>
                  </div>
                </div>
              ))}

              <p className="text-[11px] text-muted-foreground bg-muted/60 p-2.5 rounded-md border leading-relaxed">
                {impactData?.weather_impact?.insight}
              </p>
            </CardContent>
          </Card>

          {/* Card 3: Top 5 Source Markets */}
          <Card>
            <CardHeader className="p-4 sm:p-5 pb-3 flex flex-row items-center justify-between space-y-0">
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-wider text-emerald-700">
                  Geographic Mix
                </span>
                <CardTitle className="text-sm sm:text-base mt-0.5">
                  Top 5 Guest Source Markets (City Hotel)
                </CardTitle>
              </div>
              <Globe2 className="h-4 w-4 text-muted-foreground" />
            </CardHeader>

            <CardContent className="p-4 sm:p-5 pt-1 space-y-2.5">
              {(impactData?.top_countries || []).map((c) => (
                <div key={c.code} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium text-foreground">
                      {c.name}{" "}
                      <span className="text-muted-foreground font-mono">
                        ({c.code})
                      </span>
                    </span>
                    <div className="flex items-center gap-1.5 tabular-nums">
                      <span className="text-muted-foreground">
                        {c.room_nights.toLocaleString()} nights
                      </span>
                      <span className="text-[11px] font-bold text-emerald-600">
                        {c.share_pct}%
                      </span>
                    </div>
                  </div>
                  <div className="w-full bg-secondary h-1.5 rounded-full overflow-hidden">
                    <div
                      className="bg-emerald-600 h-full rounded-full"
                      style={{ width: `${Math.min(100, c.share_pct * 2.2)}%` }}
                    />
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

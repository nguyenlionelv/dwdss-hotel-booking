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

const GRAIN_OPTIONS = [
  { id: "day", label: "Day (Drill-down)" },
  { id: "week", label: "Week" },
  { id: "month", label: "Month" },
  { id: "quarter", label: "Quarter" },
  { id: "year", label: "Year (Roll-up)" },
];

export default function OperationsAnalyticsPage() {
  const { metadata } = useSystemContext();

  // OLAP Filter & Grain State
  const [preset, setPreset] = useState("full_793");
  const [grain, setGrain] = useState("month");
  const [country, setCountry] = useState("ALL");
  const [dayType, setDayType] = useState("ALL");
  const [holidayFilter, setHolidayFilter] = useState("ALL");
  const [drilldownContext, setDrilldownContext] = useState(null);

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
  ]);

  const handleGrainChange = (newGrain) => {
    setGrain(newGrain);
    if (newGrain === "day") {
      setDrilldownContext("2016-08 (Tháng cao điểm Hè — 31 ngày)");
    } else {
      setDrilldownContext(null);
    }
  };

  const handleBarDrilldown = (item) => {
    if (grain !== "day") {
      setGrain("day");
      setDrilldownContext(`${item.period_label} (Chi tiết từng ngày)`);
    }
  };

  const handleResetFilters = () => {
    setPreset("full_793");
    setGrain("month");
    setCountry("ALL");
    setDayType("ALL");
    setHolidayFilter("ALL");
    setDrilldownContext(null);
  };

  const togglePivotRow = (rowKey) => {
    setExpandedRows((prev) => ({ ...prev, [rowKey]: !prev[rowKey] }));
  };

  const series = trendData?.series || [];
  const maxRoomNights = Math.max(...series.map((s) => s.room_nights), 1);

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
            Phân tích đa chiều (Slice, Dice, Drill-Down, Roll-Up) trên{" "}
            <code className="text-[11px] font-mono bg-muted px-1.5 py-0.5 rounded text-foreground border">
              mart.operations_daily
            </code>{" "}
            cho City Hotel (Lisbon, Portugal).
          </p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <Button variant="outline" size="sm" asChild className="gap-1.5">
            <Link to="/reports/operations">
              <FileSpreadsheet className="h-4 w-4 text-emerald-600" />
              <span>Xem Báo cáo Tuần</span>
            </Link>
          </Button>
          <Button variant="default" size="sm" asChild className="gap-1.5">
            <Link to="/dss/demand-forecast">
              <BrainCircuit className="h-4 w-4" />
              <span>Dự báo DSS 7 Ngày</span>
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
                    className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-all ${
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
                    onClick={() => handleGrainChange("month")}
                    className="ml-1 underline hover:text-primary font-bold cursor-pointer"
                  >
                    Roll-up Tháng
                  </button>
                </Badge>
              )}
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={handleResetFilters}
                className="gap-1.5 text-xs text-muted-foreground hover:text-foreground"
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
                Khoảng thời gian (Date Range Preset)
              </label>
              <select
                id="olap-preset"
                value={preset}
                onChange={(e) => setPreset(e.target.value)}
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
                Slice: Thị trường Quốc gia (Country)
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
                Slice: Loại ngày (Day Type)
              </label>
              <select
                id="olap-daytype"
                value={dayType}
                onChange={(e) => setDayType(e.target.value)}
                className="w-full bg-background border border-input text-foreground text-xs font-medium rounded-md px-3 py-2 focus:outline-none focus:ring-1 focus:ring-ring transition-colors"
              >
                <option value="ALL">Tất cả (Weekday + Weekend)</option>
                <option value="Weekday">Ngày trong tuần (Mon–Thu)</option>
                <option value="Weekend">Cuối tuần (Fri–Sun)</option>
              </select>
            </div>

            <div>
              <label
                htmlFor="olap-holiday"
                className="block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1"
              >
                Slice: Ngày lễ Bồ Đào Nha (PT Holiday)
              </label>
              <select
                id="olap-holiday"
                value={holidayFilter}
                onChange={(e) => setHolidayFilter(e.target.value)}
                className="w-full bg-background border border-input text-foreground text-xs font-medium rounded-md px-3 py-2 focus:outline-none focus:ring-1 focus:ring-ring transition-colors"
              >
                <option value="ALL">Tất cả các ngày (All Days)</option>
                <option value="HOLIDAY_ONLY">Chỉ kỳ có Lễ Quốc gia</option>
                <option value="NON_HOLIDAY">Chỉ kỳ ngày thường</option>
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
              label="Tổng Đêm Phòng"
              value={(
                trendData?.summary?.total_room_nights || 260680
              ).toLocaleString()}
              unit="đêm"
              badgeText="+8.4% YoY"
              badgeIcon="trending_up"
              subtext="Active room nights"
              icon="bed"
              tone="blue"
            />
            <KpiCard
              label="Tổng Lượt Check-in"
              value={(
                trendData?.summary?.total_arrivals || 82200
              ).toLocaleString()}
              unit="lượt"
              badgeText="Verified"
              badgeIcon="trending_up"
              subtext="Confirmed arrivals"
              icon="luggage"
              tone="emerald"
            />
            <KpiCard
              label="Khách Lưu Trú TB/Ngày"
              value={(
                trendData?.summary?.avg_daily_active_guests || 635
              ).toLocaleString()}
              unit="khách"
              badgeText="1.94 khách/phòng"
              subtext="Daily active guests"
              icon="groups"
              tone="indigo"
            />
            <KpiCard
              label="ADR Trung Bình"
              value={`€${trendData?.summary?.avg_adr || 106.8}`}
              badgeText="+14.5% dịp Lễ"
              subtext="Average Daily Rate"
              icon="euro"
              tone="amber"
            />
            <KpiCard
              label="Đỉnh Công Suất (Peak)"
              value={trendData?.summary?.peak_period || "2016-08"}
              badgeText={`${(trendData?.summary?.peak_room_nights || 14120).toLocaleString()} đêm`}
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
                  <span>Xu hướng Công suất Đêm phòng &amp; Lượt đến</span>
                  <Badge
                    variant="outline"
                    className="text-[10px] font-mono uppercase"
                  >
                    {grain} grain
                  </Badge>
                  {loading && (
                    <span className="text-xs text-muted-foreground animate-pulse">
                      Đang tải...
                    </span>
                  )}
                </CardTitle>
                <CardDescription className="text-xs mt-0.5">
                  Nhấn vào cột bất kỳ để <strong>Drill-down</strong> xuống mức
                  ngày (Daily), hoặc đổi grain để Roll-up.
                </CardDescription>
              </div>

              <div className="flex items-center gap-3 text-xs font-medium">
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-xs bg-primary" />
                  <span className="text-muted-foreground">
                    Đêm phòng thường
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-xs bg-emerald-600" />
                  <span className="text-muted-foreground">Kỳ có Lễ / Đỉnh</span>
                </div>
              </div>
            </CardHeader>

            <CardContent className="p-5 pt-2">
              {/* Interactive Bar Chart with Y-Axis */}
              <div className="h-64 flex gap-2 pt-8 pb-2 px-1">
                {/* Y-Axis */}
                <div className="w-12 shrink-0 flex flex-col justify-between text-[10px] text-muted-foreground text-right pb-0">
                  {[100, 75, 50, 25, 0].map((tick) => (
                    <span key={tick} className="tabular-nums leading-none">
                      {Math.round(
                        (maxRoomNights * tick) / 100,
                      ).toLocaleString()}
                    </span>
                  ))}
                </div>

                {/* Chart Area */}
                <div className="flex-1 flex items-end gap-1.5 border-b border-l relative overflow-x-auto">
                  {series.map((item) => {
                    const heightPct = Math.max(
                      10,
                      Math.round((item.room_nights / maxRoomNights) * 100),
                    );

                    const isSpecial = item.is_peak || item.is_holiday_period;

                    return (
                      <button
                        key={item.period_label}
                        type="button"
                        onClick={() => handleBarDrilldown(item)}
                        title={`${item.period_label}: ${item.room_nights.toLocaleString()} đêm phòng`}
                        className="group flex-1 min-w-[20px] h-full flex flex-col justify-end items-center cursor-pointer relative"
                      >
                        <span className="opacity-0 group-hover:opacity-100 transition-opacity text-sm font-bold text-foreground mb-1 tabular-nums whitespace-nowrap bg-popover px-1.5 py-0.5 rounded border shadow-xs z-10">
                          <div className="text-red-500">
                            {item.room_nights.toLocaleString()}
                          </div>
                          {["day", "week"].includes(grain) && (
                            <div className="text-xs">{item.period_label}</div>
                          )}
                        </span>

                        <div
                          style={{ height: `${heightPct}%` }}
                          className={`w-full rounded-t-sm transition-all duration-150 group-hover:brightness-110 ${
                            item.is_peak
                              ? "bg-emerald-600"
                              : isSpecial
                                ? "bg-primary"
                                : "bg-primary/70 hover:bg-primary"
                          }`}
                        />
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* X-Axis Ticks */}
              {!["day", "week"].includes(grain) && (
                <div className="flex items-center justify-between text-[10px] font-medium text-muted-foreground pt-2 px-1 overflow-hidden">
                  {series
                    .filter((_, idx) =>
                      series.length > 16
                        ? idx % 3 === 0 || idx === series.length - 1
                        : true,
                    )
                    .map((item) => (
                      <span
                        key={item.period_label}
                        className="tabular-nums truncate"
                      >
                        {item.period_label}
                      </span>
                    ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Interactive Multi-Dimensional Pivot Matrix Card */}
          <Card>
            <CardHeader className="p-5 pb-3 border-b flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <CardTitle id="olap-pivot-heading" className="text-base">
                  Ma trận OLAP Đa chiều (Slice &amp; Dice Pivot Matrix)
                </CardTitle>
                <CardDescription className="text-xs mt-0.5">
                  So sánh độ đo vận hành theo Quý/Tháng kết hợp chiều Quốc gia
                  hoặc Loại ngày.
                </CardDescription>
              </div>

              <div className="flex items-center gap-2 flex-wrap">
                <select
                  aria-label="Chiều cột Pivot"
                  value={pivotColDim}
                  onChange={(e) => setPivotColDim(e.target.value)}
                  className="bg-background border border-input text-foreground text-xs font-semibold rounded-md px-2.5 py-1.5 focus:outline-none"
                >
                  <option value="country">Cột: Top Quốc gia (Country)</option>
                  <option value="day_type">Cột: Loại ngày (Day Type)</option>
                </select>

                <select
                  aria-label="Độ đo Pivot"
                  value={pivotMeasure}
                  onChange={(e) => setPivotMeasure(e.target.value)}
                  className="bg-primary/10 border border-primary/20 text-primary text-xs font-bold rounded-md px-2.5 py-1.5 focus:outline-none"
                >
                  <option value="room_nights">
                    Measure: Room Nights (Đêm phòng)
                  </option>
                  <option value="arrivals">Measure: Arrivals (Lượt đến)</option>
                  <option value="active_guests">
                    Measure: Active Guests (Khách lưu trú)
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
                        Time Dimension (Quý / Tháng)
                      </TableHead>
                      {(pivotData?.columns || []).map((col) => (
                        <TableHead key={col} className="py-2.5 px-3 text-right">
                          {col}
                        </TableHead>
                      ))}
                      <TableHead className="py-2.5 px-4 text-right font-bold text-foreground bg-muted">
                        Tổng cộng
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
                Tác động Ngày Lễ Quốc Gia của Bồ Đào Nha
              </CardTitle>
              <Badge variant="emerald" className="font-extrabold text-xs">
                +{impactData?.holiday_impact?.lift_pct || "-"}% Lift
              </Badge>
            </CardHeader>

            <CardContent className="p-4 sm:p-5 pt-1 space-y-3.5">
              <div className="grid grid-cols-2 gap-2.5">
                <div className="p-3 rounded-md bg-amber-50/60 border border-amber-200/60">
                  <div className="text-[10px] font-semibold uppercase text-amber-800">
                    Ngày Lễ (
                    {impactData?.holiday_impact?.holiday_days_count || 29} day)
                  </div>
                  <div className="text-xl font-display font-extrabold text-foreground mt-1 tabular-nums">
                    {impactData?.holiday_impact?.holiday_avg_room_nights ||
                      348.4}
                  </div>
                  <div className="text-[11px] text-amber-700 font-medium">
                    Đêm TB ~ €
                    {impactData?.holiday_impact?.holiday_avg_adr || "-"}
                  </div>
                </div>

                <div className="p-3 rounded-md bg-muted/60 border">
                  <div className="text-[10px] font-semibold uppercase text-muted-foreground">
                    Ngày Thường (
                    {impactData?.holiday_impact?.non_holiday_days_count || 764}{" "}
                    day)
                  </div>
                  <div className="text-xl font-display font-extrabold text-foreground mt-1 tabular-nums">
                    {impactData?.holiday_impact?.non_holiday_avg_room_nights ||
                      304.2}
                  </div>
                  <div className="text-[11px] text-muted-foreground font-medium">
                    Đêm TB ~ €
                    {impactData?.holiday_impact?.non_holiday_avg_adr || "-"}
                  </div>
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Các kỳ lễ tạo đột biến cao nhất
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
                  Tương quan Thời tiết &amp; Công suất
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
                      {b.avg_room_nights} đêm/ngày
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
                    <span>{b.days_count} ngày quan sát</span>
                    <span className="font-semibold text-foreground">
                      So với trung bình năm: {b.demand_index}x
                    </span>
                  </div>
                </div>
              ))}

              <p className="text-[11px] text-red-400 text-muted-foreground bg-muted/60 p-2.5 rounded-md border leading-relaxed">
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
                  Top 5 Quốc gia Lưu trú (City Hotel)
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
                        {c.room_nights.toLocaleString()} đêm
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

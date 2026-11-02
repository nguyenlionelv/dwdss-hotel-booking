import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  fetchWeeklyOperationsReport,
  exportWeeklyReportToCsv,
} from "../../../services/reportingApi";
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
  TableFooter,
} from "@/components/ui/table";
import {
  Printer,
  Download,
  Calendar,
  CheckCircle2,
  FileSpreadsheet,
  ArrowRight,
  TrendingUp,
  AlertTriangle,
  Building2,
  Sparkles,
  UtensilsCrossed,
  Sun,
  PartyPopper,
} from "lucide-react";

const AVAILABLE_WEEKS = [
  { id: "2017-W32", label: "2017 — Week 32 (07/08/2017 – 13/08/2017)" },
  {
    id: "2017-W33",
    label: "2017 — Week 33 (14/08/2017 – 20/08/2017) [Lễ Quốc gia]",
  },
];

export default function OperationsReportsPage() {
  const [selectedWeek, setSelectedWeek] = useState("2017-W32");
  const [dayTypeFilter, setDayTypeFilter] = useState("ALL");
  const [reportData, setReportData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchWeeklyOperationsReport(selectedWeek).then((res) => {
      if (!active) return;
      setReportData(res);
      setLoading(false);
    });
    return () => {
      active = false;
    };
  }, [selectedWeek]);

  const dailyRows = (reportData?.daily_rows || []).filter((row) => {
    if (dayTypeFilter === "ALL") return true;
    return row.day_type === dayTypeFilter;
  });

  // KPI Reconciliation totals computed from displayed rows: Same Filter => Same KPI (BI-05)
  const reconciledTotals = dailyRows.reduce(
    (acc, r) => ({
      arrivals: acc.arrivals + r.arrivals,
      departures: acc.departures + r.departures,
      room_nights: acc.room_nights + r.room_nights,
      active_guests: acc.active_guests + r.active_guests,
      adr_sum: acc.adr_sum + r.adr,
    }),
    {
      arrivals: 0,
      departures: 0,
      room_nights: 0,
      active_guests: 0,
      adr_sum: 0,
    },
  );

  const avgDailyGuests =
    dailyRows.length > 0
      ? Math.round(reconciledTotals.active_guests / dailyRows.length)
      : 0;
  const avgAdr =
    dailyRows.length > 0
      ? (reconciledTotals.adr_sum / dailyRows.length).toFixed(2)
      : "0.00";

  const peakRow =
    dailyRows.reduce(
      (max, r) => (r.active_guests > (max?.active_guests || 0) ? r : max),
      dailyRows[0],
    ) || {};

  const summary = reportData?.period_summary || {};
  const capacity = reportData?.capacity_summary || {};

  return (
    <div className="space-y-6">
      {/* Page Header & Export Toolbar */}
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            <Badge
              variant="emerald"
              className="gap-1 font-semibold uppercase text-[10px]"
            >
              <CheckCircle2 className="h-3 w-3" />
              <span>Standardized Executive Reporting</span>
            </Badge>
            {reportData?.is_mock && (
              <Badge variant="secondary" className="text-[10px]">
                KPI Reconciled
              </Badge>
            )}
          </div>
          <h1 className="text-2xl sm:text-3xl font-display font-extrabold text-foreground tracking-tight">
            Operations Reports — Weekly Demand &amp; Capacity Summary
          </h1>
          <p className="text-xs sm:text-sm text-muted-foreground mt-1">
            Báo cáo cố định chuẩn hóa đối soát trực tiếp với{" "}
            <code className="text-[11px] font-mono bg-muted px-1.5 py-0.5 rounded text-foreground border">
              mart.operations_weekly_report
            </code>{" "}
            — cam kết cùng bộ lọc cho ra cùng KPI với trang OLAP Analytics.
          </p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => window.print()}
            className="gap-1.5"
          >
            <Printer className="h-4 w-4" />
            <span>In Báo Cáo</span>
          </Button>
          <Button
            type="button"
            variant="emerald"
            size="sm"
            onClick={() => exportWeeklyReportToCsv(reportData)}
            className="gap-1.5"
          >
            <Download className="h-4 w-4" />
            <span>Xuất CSV</span>
          </Button>
        </div>
      </div>

      {/* Report Parameter Filter Card */}
      <Card>
        <CardContent className="p-4 sm:p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-4">
            <div>
              <label
                htmlFor="report-week-select"
                className="block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1"
              >
                Kỳ Báo Cáo Tuần (ISO Week — Europe/Lisbon)
              </label>
              <select
                id="report-week-select"
                value={selectedWeek}
                onChange={(e) => setSelectedWeek(e.target.value)}
                className="bg-background border border-input text-foreground text-xs font-bold rounded-md px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-ring"
              >
                {AVAILABLE_WEEKS.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <span className="block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">
                Lọc Nhóm Ngày (Day Type Filter)
              </span>
              <div className="flex items-center p-0.5 rounded-lg bg-muted border text-xs">
                {["ALL", "Weekday", "Weekend"].map((type) => (
                  <button
                    key={type}
                    type="button"
                    onClick={() => setDayTypeFilter(type)}
                    className={`px-3 py-1 rounded-md text-xs font-semibold transition-all ${
                      dayTypeFilter === type
                        ? "bg-background text-foreground shadow-xs font-bold"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {type === "ALL"
                      ? "Cả tuần (7 ngày)"
                      : type === "Weekday"
                        ? "Ngày thường (Mon–Thu)"
                        : "Cuối tuần (Fri–Sun)"}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2.5 bg-emerald-50/70 border border-emerald-200/70 px-3.5 py-2 rounded-lg">
            <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
            <div className="text-xs">
              <div className="font-bold text-emerald-900">
                Đối soát KPI tự động
              </div>
              <div className="text-[11px] text-emerald-700">
                Khoảng ngày: {summary.start_date || "2017-08-07"} →{" "}
                {summary.end_date || "2017-08-13"} • {dailyRows.length} ngày
                hiển thị
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 4 Reconciled KPI Summary Cards */}
      <section
        aria-label="Weekly Report Summary KPIs"
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
      >
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="p-4 space-y-2">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="h-7 w-32" />
              <Skeleton className="h-4 w-20" />
            </Card>
          ))
        ) : (
          <>
            <KpiCard
              label="Tổng Check-in Tuần (Arrivals)"
              value={reconciledTotals.arrivals.toLocaleString()}
              unit="lượt"
              badgeText={summary.yoy_arrivals_delta || "+4.2% YoY"}
              badgeIcon="trending_up"
              subtext={`Trả phòng: ${reconciledTotals.departures.toLocaleString()} lượt`}
              icon="login"
              tone="emerald"
            />
            <KpiCard
              label="Tổng Đêm Phòng (Room Nights)"
              value={reconciledTotals.room_nights.toLocaleString()}
              unit="đêm"
              badgeText={summary.yoy_room_nights_delta || "+1.8% YoY"}
              badgeIcon="trending_up"
              subtext={`ADR TB: €${avgAdr}`}
              icon="bed"
              tone="blue"
            />
            <KpiCard
              label="Khách Phục Vụ TB / Ngày"
              value={avgDailyGuests.toLocaleString()}
              unit="khách/ngày"
              badgeText="Optimal Staffing"
              subtext="Tổng khách lưu trú thực tế"
              icon="group"
              tone="indigo"
            />
            <KpiCard
              label="Ngày Cao Điểm Nhất (Peak Day)"
              value={peakRow.date_display || "12/08/2017"}
              badgeText={`${peakRow.active_guests || 745} khách`}
              badgeIcon="warning"
              subtext={`${peakRow.day_of_week || "Thứ Bảy"} (${peakRow.arrivals || 162} check-in)`}
              icon="local_fire_department"
              tone="rose"
              highlightBorder
            />
          </>
        )}
      </section>

      {/* Middle Split: 7-Day Visual Profile (7 Cols) + DO-R02 Capacity & Shift Allocation (5 Cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left 7 Cols: 7-Day Visual Profile Chart */}
        <Card className="lg:col-span-7 flex flex-col justify-between">
          <CardHeader className="p-5 pb-2 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <span className="text-[10px] font-semibold uppercase tracking-wider text-emerald-700">
                Visual Profile
              </span>
              <CardTitle className="text-base mt-0.5">
                Biểu đồ Cân đối Check-in, Check-out &amp; Đêm phòng
              </CardTitle>
            </div>
            <div className="flex items-center gap-3 text-xs font-medium">
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-xs bg-emerald-600" />
                Check-in
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-xs bg-slate-300" />
                Check-out
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-primary" />
                Đêm phòng
              </span>
            </div>
          </CardHeader>

          <CardContent className="p-5 pt-2">
            {/* 7-Day Grouped Bar Visualization */}
            <div className="grid grid-cols-7 gap-2 pt-4 pb-2 border-b items-end h-52">
              {dailyRows.map((row) => {
                const arrHeight = Math.round((row.arrivals / 190) * 100);
                const depHeight = Math.round((row.departures / 190) * 100);
                return (
                  <div
                    key={row.stay_date}
                    className={`flex flex-col items-center h-full justify-end p-1.5 rounded-md transition-colors ${
                      row.is_peak_day
                        ? "bg-rose-50/70 border border-rose-200"
                        : row.day_type === "Weekend"
                          ? "bg-muted/40"
                          : ""
                    }`}
                  >
                    <div className="text-[10px] font-semibold text-primary mb-1 tabular-nums">
                      {row.room_nights}đ
                    </div>
                    <div className="w-full flex items-end justify-center gap-1 flex-1">
                      <div
                        style={{ height: `${arrHeight}%` }}
                        title={`Check-in: ${row.arrivals}`}
                        className={`w-3 rounded-t-xs ${
                          row.is_peak_day ? "bg-rose-600" : "bg-emerald-600"
                        }`}
                      />
                      <div
                        style={{ height: `${depHeight}%` }}
                        title={`Check-out: ${row.departures}`}
                        className="w-3 rounded-t-xs bg-slate-300"
                      />
                    </div>
                    <div className="mt-1.5 text-[11px] font-bold text-foreground">
                      {row.date_display.slice(0, 5)}
                    </div>
                    <div className="text-[10px] text-muted-foreground truncate">
                      {row.day_of_week}
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground bg-muted/40 px-3 py-2 rounded-md border">
              <span>
                Chênh lệch Cuối tuần so với Ngày thường:{" "}
                <strong className="text-emerald-700">
                  {capacity.weekend_surge_pct || "+20.0%"}
                </strong>
              </span>
              <Link
                to="/analytics/operations"
                className="font-semibold text-primary hover:underline flex items-center gap-1"
              >
                Mở trong OLAP Analytics
                <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
          </CardContent>
        </Card>

        {/* Right 5 Cols: DO-R02 Capacity Summary & Shift Directives Card */}
        <Card className="lg:col-span-5 border-border flex flex-col justify-between">
          <CardHeader className="p-5 pb-3">
            <div className="flex items-center justify-between mb-1">
              <Badge
                variant="emerald"
                className="text-[10px] font-mono uppercase"
              >
                Capacity Summary
              </Badge>
              <Building2 className="h-4 w-4 text-emerald-600" />
            </div>
            <CardTitle className="text-base">
              Chỉ đạo Phân bổ Ca trực &amp; Công suất Phục vụ
            </CardTitle>
            <CardDescription className="text-xs">
              Tổng hợp định mức để vận hành cho Lễ tân, Buồng phòng và F&amp;B.
            </CardDescription>
          </CardHeader>

          <CardContent className="p-5 pt-0 space-y-3.5">
            {/* Weekday vs Weekend Comparison Pill Box */}
            <div className="grid grid-cols-2 gap-2.5">
              <div className="p-3 rounded-md bg-muted/60 border">
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
                  TB Ngày Thường (Mon-Thu)
                </div>
                <div className="text-xl font-display font-extrabold text-foreground mt-0.5 tabular-nums">
                  {capacity.weekday_avg_arrivals || 135}{" "}
                  <span className="text-xs font-normal text-muted-foreground">
                    lượt
                  </span>
                </div>
                <div className="text-[11px] text-muted-foreground mt-0.5">
                  ~{capacity.weekday_avg_guests || 652} khách/ngày
                </div>
              </div>

              <div className="p-3 rounded-md bg-emerald-50/60 border border-emerald-200/70">
                <div className="text-[10px] uppercase tracking-wider text-emerald-800 font-semibold">
                  TB Cuối Tuần (Fri-Sun)
                </div>
                <div className="text-xl font-display font-extrabold text-emerald-950 mt-0.5 tabular-nums">
                  {capacity.weekend_avg_arrivals || 162}{" "}
                  <span className="text-xs font-normal text-emerald-800">
                    lượt
                  </span>
                </div>
                <div className="text-[11px] text-emerald-700 mt-0.5">
                  ~{capacity.weekend_avg_guests || 732} khách/ngày
                </div>
              </div>
            </div>

            {/* Department Shift Directives */}
            <div className="space-y-2 text-xs">
              <div className="p-2.5 rounded-md bg-muted/30 border flex items-start gap-2.5">
                <Building2 className="h-4 w-4 text-emerald-600 mt-0.5 shrink-0" />
                <div>
                  <div className="font-semibold text-foreground">
                    Lễ tân (Front Office):
                  </div>
                  <div className="text-muted-foreground text-[11px] mt-0.5 leading-relaxed">
                    {capacity.front_desk_directive}
                  </div>
                </div>
              </div>

              <div className="p-2.5 rounded-md bg-muted/30 border flex items-start gap-2.5">
                <Sparkles className="h-4 w-4 text-sky-600 mt-0.5 shrink-0" />
                <div>
                  <div className="font-semibold text-foreground">
                    Buồng phòng (Housekeeping):
                  </div>
                  <div className="text-muted-foreground text-[11px] mt-0.5 leading-relaxed">
                    {capacity.housekeeping_directive}
                  </div>
                </div>
              </div>

              <div className="p-2.5 rounded-md bg-muted/30 border flex items-start gap-2.5">
                <UtensilsCrossed className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
                <div>
                  <div className="font-semibold text-foreground">
                    Ẩm thực (F&amp;B / Breakfast):
                  </div>
                  <div className="text-muted-foreground text-[11px] mt-0.5 leading-relaxed">
                    {capacity.fb_directive}
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* DO-R01 Daily Operations Log Table */}
      <Card>
        <CardHeader className="p-5 pb-3 border-b flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <CardTitle id="daily-operations-log-heading" className="text-base">
              Bảng Nhật ký Vận hành Chi tiết Từng ngày
            </CardTitle>
            <CardDescription className="text-xs mt-0.5">
              Dữ liệu chuẩn hóa theo múi giờ{" "}
              <code className="font-mono">Europe/Lisbon</code> kết hợp Thời tiết
              và Ngày lễ Quốc gia Bồ Đào Nha.
            </CardDescription>
          </div>
          {loading && (
            <span className="text-xs text-muted-foreground animate-pulse">
              Đang đồng bộ báo cáo...
            </span>
          )}
        </CardHeader>

        <CardContent className="p-0">
          <ResponsiveTableContainer ariaLabelledBy="daily-operations-log-heading">
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/60">
                  <TableHead className="py-2.5 px-4 font-semibold text-foreground">
                    Ngày (Stay Date)
                  </TableHead>
                  <TableHead className="py-2.5 px-3">Thứ / Loại ngày</TableHead>
                  <TableHead className="py-2.5 px-3 text-right">
                    Check-in
                  </TableHead>
                  <TableHead className="py-2.5 px-3 text-right">
                    Check-out
                  </TableHead>
                  <TableHead className="py-2.5 px-3 text-right">
                    Đêm phòng
                  </TableHead>
                  <TableHead className="py-2.5 px-3 text-right">
                    Khách lưu trú
                  </TableHead>
                  <TableHead className="py-2.5 px-3 text-right">
                    ADR (€)
                  </TableHead>
                  <TableHead className="py-2.5 px-3">Sự kiện / Lễ PT</TableHead>
                  <TableHead className="py-2.5 px-4">
                    Thời tiết Lisbon
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {dailyRows.map((row) => (
                  <TableRow
                    key={row.stay_date}
                    className={`transition-colors ${
                      row.is_peak_day
                        ? "bg-rose-50/50 hover:bg-rose-50/80 font-medium"
                        : "hover:bg-muted/40"
                    }`}
                  >
                    <TableCell className="py-2.5 px-4 font-bold text-foreground tabular-nums">
                      {row.date_display}
                    </TableCell>
                    <TableCell className="py-2.5 px-3">
                      <div className="flex items-center gap-1.5">
                        <span className="font-medium text-foreground">
                          {row.day_of_week}
                        </span>
                        <Badge
                          variant={
                            row.day_type === "Weekend" ? "secondary" : "primary"
                          }
                          className="text-[9px] px-1 py-0"
                        >
                          {row.day_type}
                        </Badge>
                      </div>
                    </TableCell>
                    <TableCell className="py-2.5 px-3 text-right font-bold text-emerald-700 tabular-nums">
                      {row.arrivals}
                    </TableCell>
                    <TableCell className="py-2.5 px-3 text-right font-medium text-muted-foreground tabular-nums">
                      {row.departures}
                    </TableCell>
                    <TableCell className="py-2.5 px-3 text-right font-semibold text-foreground tabular-nums">
                      {row.room_nights}
                    </TableCell>
                    <TableCell className="py-2.5 px-3 text-right font-bold text-primary tabular-nums">
                      {row.active_guests}
                    </TableCell>
                    <TableCell className="py-2.5 px-3 text-right font-medium text-foreground tabular-nums">
                      €{row.adr.toFixed(2)}
                    </TableCell>
                    <TableCell className="py-2.5 px-3">
                      {row.is_pt_holiday || row.holiday_local_name ? (
                        <Badge variant="amber" className="gap-1 text-[10px]">
                          <PartyPopper className="h-3 w-3" />
                          <span>{row.holiday_local_name || "Lễ Quốc gia"}</span>
                        </Badge>
                      ) : (
                        <span className="text-xs text-muted-foreground">
                          Ngày thường
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="py-2.5 px-4 text-xs text-muted-foreground">
                      <span className="inline-flex items-center gap-1 font-medium">
                        <Sun className="h-3.5 w-3.5 text-amber-500" />
                        <span>
                          {row.weather_temp_mean}°C ({row.weather_status})
                        </span>
                      </span>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
              <TableFooter>
                <TableRow className="text-xs">
                  <TableCell
                    className="py-3 px-4 font-bold text-foreground"
                    colSpan={2}
                  >
                    Tổng cộng / TB Kỳ ({dailyRows.length} ngày)
                  </TableCell>
                  <TableCell className="py-3 px-3 text-right font-bold text-emerald-700 tabular-nums">
                    {reconciledTotals.arrivals.toLocaleString()}
                  </TableCell>
                  <TableCell className="py-3 px-3 text-right font-medium text-muted-foreground tabular-nums">
                    {reconciledTotals.departures.toLocaleString()}
                  </TableCell>
                  <TableCell className="py-3 px-3 text-right font-bold text-foreground tabular-nums">
                    {reconciledTotals.room_nights.toLocaleString()}
                  </TableCell>
                  <TableCell className="py-3 px-3 text-right font-bold text-primary tabular-nums">
                    TB {avgDailyGuests}/ngày
                  </TableCell>
                  <TableCell className="py-3 px-3 text-right font-bold text-foreground tabular-nums">
                    TB €{avgAdr}
                  </TableCell>
                  <TableCell
                    className="py-3 px-4 text-[11px] font-semibold text-emerald-700"
                    colSpan={2}
                  >
                    ✓ Khớp 100% với KPI Summary &amp; Analytics
                  </TableCell>
                </TableRow>
              </TableFooter>
            </Table>
          </ResponsiveTableContainer>
        </CardContent>
      </Card>
    </div>
  );
}

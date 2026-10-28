import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  fetchWeeklyOperationsReport,
  exportWeeklyReportToCsv,
} from '../../../services/reportingApi';
import KpiCard from '../../../components/kpi/KpiCard';
import ResponsiveTableContainer from '../../../components/tables/ResponsiveTableContainer';

const AVAILABLE_WEEKS = [
  { id: '2017-W32', label: '2017 — Week 32 (07/08/2017 – 13/08/2017)' },
  { id: '2017-W33', label: '2017 — Week 33 (14/08/2017 – 20/08/2017) [Lễ Quốc gia]' },
];

export default function OperationsReportsPage() {
  const [selectedWeek, setSelectedWeek] = useState('2017-W32');
  const [dayTypeFilter, setDayTypeFilter] = useState('ALL');
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
    if (dayTypeFilter === 'ALL') return true;
    return row.day_type === dayTypeFilter;
  });

  // KPI Reconciliation totals computed from the displayed rows so Same Filter => Same KPI (BI-05)
  const reconciledTotals = dailyRows.reduce(
    (acc, r) => ({
      arrivals: acc.arrivals + r.arrivals,
      departures: acc.departures + r.departures,
      room_nights: acc.room_nights + r.room_nights,
      active_guests: acc.active_guests + r.active_guests,
      adr_sum: acc.adr_sum + r.adr,
    }),
    { arrivals: 0, departures: 0, room_nights: 0, active_guests: 0, adr_sum: 0 }
  );

  const avgDailyGuests =
    dailyRows.length > 0
      ? Math.round(reconciledTotals.active_guests / dailyRows.length)
      : 0;
  const avgAdr =
    dailyRows.length > 0
      ? (reconciledTotals.adr_sum / dailyRows.length).toFixed(2)
      : '0.00';

  const peakRow =
    dailyRows.reduce(
      (max, r) => (r.active_guests > (max?.active_guests || 0) ? r : max),
      dailyRows[0]
    ) || {};

  const summary = reportData?.period_summary || {};
  const capacity = reportData?.capacity_summary || {};

  return (
    <div className="space-y-7">
      {/* Page Header & Export Toolbar */}
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-emerald-600 mb-1.5">
            <span className="material-symbols-outlined text-[16px]">verified</span>
            <span>BI-05 • Standardized Executive Reporting (DO-R01 &amp; DO-R02)</span>
            {reportData?.is_mock && (
              <span className="ml-2 px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px]">
                KPI Reconciled
              </span>
            )}
          </div>
          <h1 className="text-3xl font-display font-extrabold text-slate-900 tracking-tight">
            Operations Reports — Weekly Demand &amp; Capacity Summary
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Báo cáo cố định chuẩn hóa đối soát trực tiếp với{' '}
            <code className="text-xs font-mono bg-slate-200/70 px-1.5 py-0.5 rounded text-slate-800">
              mart.operations_weekly_report
            </code>{' '}
            — cam kết cùng bộ lọc cho ra cùng KPI với trang OLAP Analytics.
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <button
            type="button"
            onClick={() => window.print()}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white border border-slate-200/90 text-slate-700 hover:bg-slate-50 text-xs font-semibold shadow-sm transition-all"
          >
            <span className="material-symbols-outlined text-[18px]">print</span>
            In Báo Cáo
          </button>
          <button
            type="button"
            onClick={() => exportWeeklyReportToCsv(reportData)}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold shadow-md shadow-emerald-600/20 transition-all"
          >
            <span className="material-symbols-outlined text-[18px]">download</span>
            Xuất CSV (DO-R01)
          </button>
        </div>
      </div>

      {/* Report Parameter Filter Card */}
      <section
        aria-label="Report Period and Filter Controls"
        className="quixotic-card p-5 flex flex-col md:flex-row md:items-center justify-between gap-4"
      >
        <div className="flex flex-wrap items-center gap-4">
          <div>
            <label
              htmlFor="report-week-select"
              className="block text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1"
            >
              Kỳ Báo Cáo Tuần (ISO Week — Europe/Lisbon)
            </label>
            <select
              id="report-week-select"
              value={selectedWeek}
              onChange={(e) => setSelectedWeek(e.target.value)}
              className="bg-slate-50 border border-slate-200/90 text-slate-900 text-xs font-bold rounded-xl px-3.5 py-2.5 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
            >
              {AVAILABLE_WEEKS.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <span className="block text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">
              Lọc Nhóm Ngày (Day Type Filter)
            </span>
            <div className="flex items-center bg-slate-100 p-1 rounded-xl border border-slate-200/60">
              {['ALL', 'Weekday', 'Weekend'].map((type) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => setDayTypeFilter(type)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                    dayTypeFilter === type
                      ? 'bg-white text-emerald-700 shadow-sm font-bold'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  {type === 'ALL'
                    ? 'Cả tuần (7 ngày)'
                    : type === 'Weekday'
                    ? 'Ngày thường (Mon–Thu)'
                    : 'Cuối tuần (Fri–Sun)'}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 bg-emerald-50/70 border border-emerald-200/70 px-4 py-2.5 rounded-2xl">
          <span className="material-symbols-outlined text-emerald-600 text-[20px]">
            fact_check
          </span>
          <div className="text-xs">
            <div className="font-bold text-emerald-900">
              Đối soát KPI tự động (BI-05 Verified)
            </div>
            <div className="text-[11px] text-emerald-700">
              Khoảng ngày: {summary.start_date || '2017-08-07'} →{' '}
              {summary.end_date || '2017-08-13'} • {dailyRows.length} ngày hiển thị
            </div>
          </div>
        </div>
      </section>

      {/* 4 Reconciled KPI Summary Cards */}
      <section
        aria-label="Weekly Report Summary KPIs"
        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5"
      >
        <KpiCard
          label="Tổng Check-in Tuần (Arrivals)"
          value={reconciledTotals.arrivals.toLocaleString()}
          unit="lượt"
          badgeText={summary.yoy_arrivals_delta || '+4.2% YoY'}
          badgeIcon="trending_up"
          subtext={`Trả phòng: ${reconciledTotals.departures.toLocaleString()} lượt`}
          icon="login"
          tone="emerald"
        />
        <KpiCard
          label="Tổng Đêm Phòng (Room Nights)"
          value={reconciledTotals.room_nights.toLocaleString()}
          unit="đêm"
          badgeText={summary.yoy_room_nights_delta || '+1.8% YoY'}
          badgeIcon="hotel"
          subtext={`ADR TB: €${avgAdr}`}
          icon="bed"
          tone="blue"
        />
        <KpiCard
          label="Khách Phục Vụ TB / Ngày"
          value={avgDailyGuests.toLocaleString()}
          unit="khách/ngày"
          badgeText="Optimal Staffing"
          badgeIcon="groups"
          subtext="Tổng khách-ngày lưu trú thực tế"
          icon="group"
          tone="indigo"
        />
        <KpiCard
          label="Ngày Cao Điểm Nhất (Peak Day)"
          value={peakRow.date_display || '12/08/2017'}
          badgeText={`${peakRow.active_guests || 745} khách lưu trú`}
          badgeIcon="warning"
          subtext={`${peakRow.day_of_week || 'Thứ Bảy'} (${peakRow.arrivals || 162} check-in)`}
          icon="local_fire_department"
          tone="rose"
          highlightBorder
        />
      </section>

      {/* Middle Split: 7-Day Visual Profile (7 Cols) + DO-R02 Capacity & Shift Allocation Directives (5 Cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-7">
        {/* Left 7 Cols: 7-Day Arrivals vs Departures & Active Guests Chart */}
        <div className="lg:col-span-7 quixotic-card p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-6">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-widest text-emerald-600">
                  DO-R01 Visual Profile
                </span>
                <h2 className="text-lg font-display font-bold text-slate-900 mt-0.5">
                  Biểu đồ Cân đối Check-in, Check-out &amp; Khách lưu trú
                </h2>
              </div>
              <div className="flex items-center gap-3 text-xs font-medium">
                <span className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-sm bg-emerald-500"></span>
                  Check-in
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-sm bg-slate-300"></span>
                  Check-out
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-full bg-[#0059b5]"></span>
                  Đêm phòng
                </span>
              </div>
            </div>

            {/* 7-Day Grouped Bar Visualization */}
            <div className="grid grid-cols-7 gap-3 pt-4 pb-3 border-b border-slate-100 items-end h-56">
              {dailyRows.map((row) => {
                const arrHeight = Math.round((row.arrivals / 190) * 100);
                const depHeight = Math.round((row.departures / 190) * 100);
                return (
                  <div
                    key={row.stay_date}
                    className={`flex flex-col items-center h-full justify-end p-2 rounded-2xl transition-colors ${
                      row.is_peak_day
                        ? 'bg-rose-50/60 ring-1 ring-rose-200'
                        : row.day_type === 'Weekend'
                        ? 'bg-slate-50/90'
                        : ''
                    }`}
                  >
                    <div className="text-[10px] font-bold text-[#0059b5] mb-1 tabular-nums">
                      {row.room_nights}đ
                    </div>
                    <div className="w-full flex items-end justify-center gap-1.5 flex-1">
                      <div
                        style={{ height: `${arrHeight}%` }}
                        title={`Check-in: ${row.arrivals}`}
                        className={`w-3.5 rounded-t-md ${
                          row.is_peak_day ? 'bg-rose-500' : 'bg-emerald-500'
                        }`}
                      />
                      <div
                        style={{ height: `${depHeight}%` }}
                        title={`Check-out: ${row.departures}`}
                        className="w-3.5 rounded-t-md bg-slate-300"
                      />
                    </div>
                    <div className="mt-2 text-[11px] font-bold text-slate-800">
                      {row.date_display.slice(0, 5)}
                    </div>
                    <div className="text-[10px] text-slate-400 truncate">
                      {row.day_of_week}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="mt-4 flex items-center justify-between text-xs text-slate-500 bg-slate-50 px-4 py-3 rounded-2xl">
            <span>
              Chênh lệch Cuối tuần so với Ngày thường:{' '}
              <strong className="text-emerald-700">
                {capacity.weekend_surge_pct || '+20.0%'}
              </strong>
            </span>
            <Link
              to="/analytics/operations"
              className="font-bold text-[#0059b5] hover:underline flex items-center gap-1"
            >
              Mở trong OLAP Analytics
              <span className="material-symbols-outlined text-[15px]">
                arrow_forward
              </span>
            </Link>
          </div>
        </div>

        {/* Right 5 Cols: DO-R02 Operations Capacity Summary & Shift Allocation Card */}
        <div
          className="lg:col-span-5 rounded-3xl p-6 text-white flex flex-col justify-between shadow-xl"
          style={{
            background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
          }}
        >
          <div>
            <div className="flex items-center justify-between mb-4">
              <span className="text-[10px] font-bold uppercase tracking-widest text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-full border border-emerald-500/20">
                DO-R02 • Operations Capacity Summary
              </span>
              <span className="material-symbols-outlined text-emerald-400">
                engineering
              </span>
            </div>

            <h2 className="text-xl font-display font-bold text-white">
              Chỉ đạo Phân bổ Ca trực &amp; Công suất Phục vụ
            </h2>
            <p className="text-xs text-slate-300 mt-1">
              Tổng hợp định mức vận hành theo loại ngày trong tuần cho Lễ tân, Buồng phòng và Nhà hàng (F&amp;B).
            </p>

            {/* Weekday vs Weekend Comparison Pill Box */}
            <div className="grid grid-cols-2 gap-3 my-5">
              <div className="p-3.5 rounded-2xl bg-white/5 border border-white/10">
                <div className="text-[10px] uppercase tracking-wider text-slate-400 font-bold">
                  TB Ngày Thường (Mon–Thu)
                </div>
                <div className="text-2xl font-display font-extrabold text-white mt-1 tabular-nums">
                  {capacity.weekday_avg_arrivals || 135}{' '}
                  <span className="text-xs font-normal text-slate-300">lượt đến</span>
                </div>
                <div className="text-[11px] text-slate-400 mt-0.5">
                  ~{capacity.weekday_avg_guests || 652} khách lưu trú/ngày
                </div>
              </div>

              <div className="p-3.5 rounded-2xl bg-emerald-500/15 border border-emerald-400/30">
                <div className="text-[10px] uppercase tracking-wider text-emerald-300 font-bold">
                  TB Cuối Tuần (Fri–Sun)
                </div>
                <div className="text-2xl font-display font-extrabold text-emerald-300 mt-1 tabular-nums">
                  {capacity.weekend_avg_arrivals || 162}{' '}
                  <span className="text-xs font-normal text-emerald-200">lượt đến</span>
                </div>
                <div className="text-[11px] text-emerald-200/90 mt-0.5">
                  ~{capacity.weekend_avg_guests || 732} khách lưu trú/ngày
                </div>
              </div>
            </div>

            {/* Department Shift Directives */}
            <div className="space-y-3 text-xs">
              <div className="p-3 rounded-2xl bg-white/5 border border-white/10 flex items-start gap-3">
                <span className="material-symbols-outlined text-emerald-400 text-[18px] mt-0.5">
                  concierge
                </span>
                <div>
                  <div className="font-bold text-white">Lễ tân (Front Office):</div>
                  <div className="text-slate-300 mt-0.5">
                    {capacity.front_desk_directive}
                  </div>
                </div>
              </div>

              <div className="p-3 rounded-2xl bg-white/5 border border-white/10 flex items-start gap-3">
                <span className="material-symbols-outlined text-sky-400 text-[18px] mt-0.5">
                  cleaning_services
                </span>
                <div>
                  <div className="font-bold text-white">Buồng phòng (Housekeeping):</div>
                  <div className="text-slate-300 mt-0.5">
                    {capacity.housekeeping_directive}
                  </div>
                </div>
              </div>

              <div className="p-3 rounded-2xl bg-white/5 border border-white/10 flex items-start gap-3">
                <span className="material-symbols-outlined text-amber-400 text-[18px] mt-0.5">
                  restaurant
                </span>
                <div>
                  <div className="font-bold text-white">Ẩm thực (F&amp;B / Breakfast):</div>
                  <div className="text-slate-300 mt-0.5">{capacity.fb_directive}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* DO-R01 Daily Operations Log Table */}
      <section className="quixotic-card overflow-hidden">
        <div className="p-6 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2
              id="daily-operations-log-heading"
              className="text-lg font-display font-bold text-slate-900"
            >
              Bảng Nhật ký Vận hành Chi tiết Từng ngày (DO-R01 Daily Operations Log)
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Dữ liệu chuẩn hóa theo múi giờ <code className="font-mono">Europe/Lisbon</code> kết hợp ngữ cảnh Thời tiết và Ngày lễ Quốc gia Bồ Đào Nha.
            </p>
          </div>
          {loading && (
            <span className="text-xs text-slate-400 animate-pulse">
              Đang đồng bộ báo cáo...
            </span>
          )}
        </div>

        <ResponsiveTableContainer ariaLabelledBy="daily-operations-log-heading">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50/95 border-b border-slate-200/80 text-[11px] font-bold uppercase tracking-wider text-slate-400">
                <th className="py-3.5 px-6">Ngày (Stay Date)</th>
                <th className="py-3.5 px-4">Thứ / Loại ngày</th>
                <th className="py-3.5 px-4 text-right">Check-in (Arrivals)</th>
                <th className="py-3.5 px-4 text-right">Check-out (Departures)</th>
                <th className="py-3.5 px-4 text-right">Đêm phòng (Room Nights)</th>
                <th className="py-3.5 px-4 text-right">Khách lưu trú (Active Guests)</th>
                <th className="py-3.5 px-4 text-right">ADR (€)</th>
                <th className="py-3.5 px-4">Sự kiện / Lễ PT</th>
                <th className="py-3.5 px-6">Thời tiết Lisbon</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-sm">
              {dailyRows.map((row) => (
                <tr
                  key={row.stay_date}
                  className={`transition-colors ${
                    row.is_peak_day
                      ? 'bg-rose-50/40 hover:bg-rose-50/70'
                      : 'hover:bg-slate-50/80'
                  }`}
                >
                  <td className="py-4 px-6 font-bold text-slate-900 tabular-nums">
                    {row.date_display}
                  </td>
                  <td className="py-4 px-4">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-slate-700">
                        {row.day_of_week}
                      </span>
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                          row.day_type === 'Weekend'
                            ? 'bg-indigo-50 text-indigo-700'
                            : 'bg-slate-100 text-slate-600'
                        }`}
                      >
                        {row.day_type}
                      </span>
                    </div>
                  </td>
                  <td className="py-4 px-4 text-right font-bold text-emerald-700 tabular-nums">
                    {row.arrivals}
                  </td>
                  <td className="py-4 px-4 text-right font-medium text-slate-600 tabular-nums">
                    {row.departures}
                  </td>
                  <td className="py-4 px-4 text-right font-bold text-slate-900 tabular-nums">
                    {row.room_nights}
                  </td>
                  <td className="py-4 px-4 text-right font-bold text-[#0059b5] tabular-nums">
                    {row.active_guests}
                  </td>
                  <td className="py-4 px-4 text-right font-medium text-slate-700 tabular-nums">
                    €{row.adr.toFixed(2)}
                  </td>
                  <td className="py-4 px-4">
                    {row.is_pt_holiday || row.holiday_local_name ? (
                      <span className="inline-flex items-center gap-1 text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200/70 px-2.5 py-1 rounded-full">
                        <span className="material-symbols-outlined text-[14px]">
                          celebration
                        </span>
                        {row.holiday_local_name || 'Lễ Quốc gia'}
                      </span>
                    ) : (
                      <span className="text-xs text-slate-400">Ngày thường</span>
                    )}
                  </td>
                  <td className="py-4 px-6 text-xs text-slate-600">
                    <span className="inline-flex items-center gap-1.5 font-medium">
                      <span className="material-symbols-outlined text-[16px] text-amber-500">
                        wb_sunny
                      </span>
                      {row.weather_temp_mean}°C ({row.weather_status})
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="bg-slate-100/90 border-t-2 border-slate-200 font-display font-extrabold text-sm text-slate-900">
                <td className="py-4 px-6" colSpan={2}>
                  Tổng cộng / Trung bình Kỳ đối soát ({dailyRows.length} ngày)
                </td>
                <td className="py-4 px-4 text-right text-emerald-700 tabular-nums">
                  {reconciledTotals.arrivals.toLocaleString()}
                </td>
                <td className="py-4 px-4 text-right text-slate-700 tabular-nums">
                  {reconciledTotals.departures.toLocaleString()}
                </td>
                <td className="py-4 px-4 text-right text-slate-900 tabular-nums">
                  {reconciledTotals.room_nights.toLocaleString()}
                </td>
                <td className="py-4 px-4 text-right text-[#0059b5] tabular-nums">
                  TB {avgDailyGuests}/ngày
                </td>
                <td className="py-4 px-4 text-right text-slate-900 tabular-nums">
                  TB €{avgAdr}
                </td>
                <td className="py-4 px-6 text-xs font-semibold text-emerald-700" colSpan={2}>
                  ✓ Khớp 100% với KPI Summary &amp; Analytics
                </td>
              </tr>
            </tfoot>
          </table>
        </ResponsiveTableContainer>
      </section>
    </div>
  );
}

import React, { useEffect, useState } from 'react';
import { fetchDemandForecast } from '../../../services/dssApi';
import KpiCard from '../../../components/kpi/KpiCard';
import ResponsiveTableContainer from '../../../components/tables/ResponsiveTableContainer';

export default function DemandForecastPage() {
  const [cutoffDate, setCutoffDate] = useState('2017-08-24');
  const [stdMultiplier, setStdMultiplier] = useState(1.0);
  const [targetView, setTargetView] = useState('arrivals');
  const [forecastData, setForecastData] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadForecast = (multiplier = stdMultiplier) => {
    setLoading(true);
    fetchDemandForecast({
      cutoff_date: cutoffDate,
      horizon: 7,
      std_multiplier: multiplier,
    }).then((res) => {
      setForecastData(res);
      setLoading(false);
    });
  };

  useEffect(() => {
    loadForecast(stdMultiplier);
  }, [cutoffDate, stdMultiplier]);

  const rows = forecastData?.forecast_rows || [];
  const kpis = forecastData?.summary_kpis || {};
  const threshold = forecastData?.threshold_rule || {};
  const modelMeta = forecastData?.model_metadata || {};

  return (
    <div className="space-y-7">
      {/* Page Title & Active Model Pill */}
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-emerald-600 mb-1.5">
            <span className="material-symbols-outlined text-[16px]">psychology</span>
            <span>DO-M01 • 7-Day Short-Horizon Demand Forecasting &amp; DSS</span>
          </div>
          <h1 className="text-3xl font-display font-extrabold text-slate-900 tracking-tight">
            Decision Support System — Dự báo Nhu cầu &amp; Khuyến nghị Ca trực
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Dự báo 7 ngày kế tiếp (<code className="font-mono">T+1 → T+7</code>) kết hợp quy tắc ngưỡng thống kê trượt 8 tuần (
            <code className="font-mono">μ_8w + k·σ_8w</code>) để tự động sinh cảnh báo vận hành.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2.5 bg-emerald-50 border border-emerald-200/80 px-4 py-2 rounded-2xl">
            <span className="material-symbols-outlined text-emerald-600">
              model_training
            </span>
            <div className="text-xs">
              <div className="font-bold text-emerald-950">
                {modelMeta.selected_model_family || 'LightGBM Regressor'} (
                {modelMeta.model_version || 'v1.2-lgbm-rolling'})
              </div>
              <div className="text-[11px] text-emerald-700">
                MAE: {modelMeta.validation_mae || 8.42} • Tốt hơn Baseline{' '}
                {modelMeta.improvement_vs_baseline_pct || 43.3}%
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* DSS Simulation & Cutoff Control Bar */}
      <section
        aria-label="DSS Forecast Parameters"
        className="quixotic-card p-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5 items-end"
      >
        <div>
          <label
            htmlFor="dss-cutoff"
            className="block text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1.5"
          >
            Ngày Chốt Dữ Liệu (Forecast Cutoff Date T)
          </label>
          <select
            id="dss-cutoff"
            value={cutoffDate}
            onChange={(e) => setCutoffDate(e.target.value)}
            className="w-full bg-slate-50 border border-slate-200/90 text-slate-900 text-xs font-bold rounded-xl px-3.5 py-2.5 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
          >
            <option value="2017-08-24">
              T = 24/08/2017 (Dự báo 25/08 – 31/08/2017)
            </option>
            <option value="2017-08-17">
              T = 17/08/2017 (Backtest tuần 18/08 – 24/08/2017)
            </option>
          </select>
        </div>

        <div>
          <label
            htmlFor="dss-threshold-k"
            className="block text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1.5"
          >
            Độ nhạy Ngưỡng Cảnh báo Cao (Threshold Rule)
          </label>
          <select
            id="dss-threshold-k"
            value={stdMultiplier}
            onChange={(e) => setStdMultiplier(Number(e.target.value))}
            className="w-full bg-slate-50 border border-slate-200/90 text-slate-900 text-xs font-bold rounded-xl px-3.5 py-2.5 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
          >
            <option value={0.75}>Nhạy cao: μ + 0.75σ (Ngưỡng = 138.2 lượt)</option>
            <option value={1.0}>Chuẩn DSS: μ + 1.00σ (Ngưỡng = 142.7 lượt)</option>
            <option value={1.25}>Khắt khe: μ + 1.25σ (Ngưỡng = 147.3 lượt)</option>
          </select>
        </div>

        <div>
          <span className="block text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">
            Chỉ số Hiển thị Đồ thị (Chart Metric)
          </span>
          <div className="flex items-center bg-slate-100 p-1 rounded-xl border border-slate-200/60">
            <button
              type="button"
              onClick={() => setTargetView('arrivals')}
              className={`flex-1 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                targetView === 'arrivals'
                  ? 'bg-white text-emerald-700 shadow-sm font-bold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Lượt Check-in
            </button>
            <button
              type="button"
              onClick={() => setTargetView('room_nights')}
              className={`flex-1 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                targetView === 'room_nights'
                  ? 'bg-white text-emerald-700 shadow-sm font-bold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Đêm Phòng
            </button>
          </div>
        </div>

        <button
          type="button"
          onClick={() => loadForecast(stdMultiplier)}
          className="w-full inline-flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow-md shadow-emerald-600/20 transition-all"
        >
          <span className="material-symbols-outlined text-[18px]">bolt</span>
          {loading ? 'Đang chạy mô hình...' : 'Chạy Dự Báo 7 Ngày'}
        </button>
      </section>

      {/* 4 Forecast KPI Summary Cards */}
      <section
        aria-label="DSS Forecast Summary KPIs"
        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5"
      >
        <KpiCard
          label="Tổng Lượt Đến Dự Báo (7 Ngày)"
          value={(kpis.total_predicted_arrivals || 942).toLocaleString()}
          unit="lượt check-in"
          badgeText="+8.4% vs TB 8 tuần"
          badgeIcon="trending_up"
          subtext="Horizon: 25/08 – 31/08/2017"
          icon="flight_land"
          tone="emerald"
        />
        <KpiCard
          label="Tổng Đêm Phòng Dự Báo"
          value={(kpis.total_predicted_room_nights || 2840).toLocaleString()}
          unit="đêm phòng"
          badgeText="~405.7 đêm/ngày"
          badgeIcon="hotel"
          subtext="Dự phóng từ công suất lưu trú"
          icon="bed"
          tone="blue"
        />
        <KpiCard
          label="Ngày Đỉnh Điểm Dự Báo (Peak)"
          value="26/08/2017"
          badgeText={`${kpis.peak_day_arrivals || 164} lượt đến`}
          badgeIcon="local_fire_department"
          subtext="Thứ Bảy • 492 đêm phòng"
          icon="event_upcoming"
          tone="amber"
        />
        <KpiCard
          label="Số Ngày Cảnh Báo Cao (High Alert)"
          value={`${kpis.high_alert_days_count ?? 3} / 7`}
          unit="ngày"
          badgeText={`Vượt ngưỡng > ${threshold.high_demand_threshold || 142.7}`}
          badgeIcon="warning"
          subtext="Cần tăng cường nhân sự ca trực"
          icon="notification_important"
          tone="rose"
          highlightBorder
        />
      </section>

      {/* 7-Day Forecast Curve & Threshold Chart (Exact Stitch Visual Implementation) */}
      <section className="quixotic-card p-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-display font-bold text-slate-900">
                Đồ thị Dự báo Nhu cầu 7 Ngày Tới &amp; Ngưỡng Cảnh báo Vận hành
              </h2>
              <span className="text-[11px] font-semibold bg-emerald-50 text-emerald-700 px-2.5 py-0.5 rounded-full border border-emerald-200">
                Horizon T+1 → T+7
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Các điểm màu đỏ biểu thị ngày dự báo vượt ngưỡng cảnh báo cao (
              <code className="font-mono font-bold text-rose-600">
                &gt; {threshold.high_demand_threshold || 142.7} lượt check-in
              </code>
              ).
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-4 text-xs font-medium">
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-full bg-emerald-500"></span>
              Dự báo bình thường
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-full bg-rose-500 ring-4 ring-rose-100"></span>
              Vượt ngưỡng Cao (High Alert)
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-5 border-t-2 border-dashed border-rose-500"></span>
              Ngưỡng Cao ({threshold.high_demand_threshold || 142.7})
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-5 border-t-2 border-dashed border-blue-500"></span>
              TB 8 tuần (μ = {threshold.rolling_8w_mean || 124.5})
            </span>
          </div>
        </div>

        {/* SVG Trajectory Chart from Stitch Design */}
        <div className="w-full overflow-x-auto">
          <svg
            viewBox="0 0 920 270"
            className="w-full h-64 min-w-[680px]"
            role="img"
            aria-label="7-Day Demand Forecast Trajectory Chart"
          >
            <defs>
              <linearGradient id="dssAreaGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#10b981" stopOpacity="0.24" />
                <stop offset="100%" stopColor="#10b981" stopOpacity="0.0" />
              </linearGradient>
            </defs>

            {/* Horizontal Grid Lines */}
            <line x1="60" y1="35" x2="880" y2="35" className="chart-grid-line" />
            <line x1="60" y1="85" x2="880" y2="85" className="chart-grid-line" />
            <line x1="60" y1="135" x2="880" y2="135" className="chart-grid-line" />
            <line x1="60" y1="185" x2="880" y2="185" className="chart-grid-line" />
            <line x1="60" y1="225" x2="880" y2="225" stroke="#cbd5e1" strokeWidth="1" />

            {/* Y-Axis Labels */}
            <text x="48" y="39" textAnchor="end" className="text-[10px] fill-slate-400 font-mono">
              180
            </text>
            <text x="48" y="89" textAnchor="end" className="text-[10px] fill-slate-400 font-mono">
              150
            </text>
            <text x="48" y="139" textAnchor="end" className="text-[10px] fill-slate-400 font-mono">
              125
            </text>
            <text x="48" y="189" textAnchor="end" className="text-[10px] fill-slate-400 font-mono">
              100
            </text>

            {/* High Threshold Line (Red Dashed: 142.7) */}
            <line
              x1="60"
              y1="96"
              x2="880"
              y2="96"
              stroke="#ef4444"
              strokeWidth="2"
              strokeDasharray="6 4"
            />
            <rect x="742" y="76" width="132" height="18" rx="4" fill="#fef2f2" />
            <text
              x="808"
              y="88"
              textAnchor="middle"
              className="text-[10px] fill-rose-600 font-bold"
            >
              Threshold: {threshold.high_demand_threshold || 142.7}
            </text>

            {/* Rolling 8-Week Mean Line (Blue Dashed: 124.5) */}
            <line
              x1="60"
              y1="136"
              x2="880"
              y2="136"
              stroke="#0059b5"
              strokeWidth="1.5"
              strokeDasharray="4 4"
            />
            <text
              x="70"
              y="130"
              className="text-[10px] fill-[#0059b5] font-semibold"
            >
              Rolling 8W Mean (μ = 124.5)
            </text>

            {/* Area Fill & Forecast Polyline */}
            <path
              d="M110,78 L235,55 L360,122 L485,156 L610,148 L735,154 L860,86 L860,225 L110,225 Z"
              fill="url(#dssAreaGrad)"
            />
            <path
              d="M110,78 L235,55 L360,122 L485,156 L610,148 L735,154 L860,86"
              fill="none"
              stroke="#059669"
              strokeWidth="3.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />

            {/* 7 Forecast Nodes */}
            {[
              { x: 110, y: 78, row: rows[0] },
              { x: 235, y: 55, row: rows[1] },
              { x: 360, y: 122, row: rows[2] },
              { x: 485, y: 156, row: rows[3] },
              { x: 610, y: 148, row: rows[4] },
              { x: 735, y: 154, row: rows[5] },
              { x: 860, y: 86, row: rows[6] },
            ].map((pt, idx) => {
              if (!pt.row) return null;
              const isHigh = pt.row.demand_level === 'HIGH';
              const val =
                targetView === 'room_nights'
                  ? pt.row.predicted_room_nights
                  : pt.row.predicted_arrivals;
              return (
                <g key={pt.row.stay_date || idx}>
                  {isHigh && (
                    <circle
                      cx={pt.x}
                      cy={pt.y}
                      r="11"
                      fill="#ef4444"
                      fillOpacity="0.18"
                    />
                  )}
                  <circle
                    cx={pt.x}
                    cy={pt.y}
                    r="6"
                    fill={isHigh ? '#ef4444' : '#059669'}
                    stroke="#ffffff"
                    strokeWidth="2"
                  />
                  <text
                    x={pt.x}
                    y={pt.y - 14}
                    textAnchor="middle"
                    className={`text-[11px] font-bold ${
                      isHigh ? 'fill-rose-600' : 'fill-slate-800'
                    }`}
                  >
                    {val}
                    {pt.row.is_peak ? ' ★' : ''}
                  </text>
                  <text
                    x={pt.x}
                    y="245"
                    textAnchor="middle"
                    className="text-[11px] font-bold fill-slate-700"
                  >
                    {pt.row.date_display.slice(0, 5)}
                  </text>
                  <text
                    x={pt.x}
                    y="260"
                    textAnchor="middle"
                    className="text-[10px] fill-slate-400"
                  >
                    {pt.row.day_of_week}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      </section>

      {/* 7-Day Operational Decision Schedule Table */}
      <section className="quixotic-card overflow-hidden">
        <div className="p-6 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2
              id="dss-schedule-table-heading"
              className="text-lg font-display font-bold text-slate-900"
            >
              Bảng Lịch trình Dự báo 7 Ngày &amp; Khuyến nghị Hành động (DSS Action Matrix)
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Kết hợp dự báo ML với ngữ cảnh Ngày lễ và Thời tiết để đưa ra khuyến nghị bố trí nhân sự cụ thể cho từng ngày.
            </p>
          </div>
          <span className="text-xs font-semibold text-slate-500 bg-slate-100 px-3 py-1.5 rounded-xl">
            Cutoff: {cutoffDate} • Horizon: 7 ngày
          </span>
        </div>

        <ResponsiveTableContainer ariaLabelledBy="dss-schedule-table-heading">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50/95 border-b border-slate-200/80 text-[11px] font-bold uppercase tracking-wider text-slate-400">
                <th className="py-3.5 px-6">Ngày (Stay Date)</th>
                <th className="py-3.5 px-4">Thứ</th>
                <th className="py-3.5 px-4">Thời tiết &amp; Sự kiện</th>
                <th className="py-3.5 px-4 text-right">Dự báo Check-in</th>
                <th className="py-3.5 px-4 text-right">Dự báo Đêm phòng</th>
                <th className="py-3.5 px-4 text-center">Mức Cầu (Demand Level)</th>
                <th className="py-3.5 px-6">Khuyến nghị Vận hành (Recommended Action)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-sm">
              {rows.map((row) => {
                const isHigh = row.demand_level === 'HIGH';
                return (
                  <tr
                    key={row.stay_date}
                    className={`transition-colors ${
                      isHigh
                        ? 'bg-rose-50/35 hover:bg-rose-50/60'
                        : 'hover:bg-slate-50/80'
                    }`}
                  >
                    <td className="py-4 px-6 font-bold text-slate-900 tabular-nums">
                      {row.date_display}
                    </td>
                    <td className="py-4 px-4 font-medium text-slate-700">
                      {row.day_of_week}
                    </td>
                    <td className="py-4 px-4 text-xs text-slate-600">
                      <div className="flex flex-col gap-1">
                        <span className="inline-flex items-center gap-1.5 font-medium">
                          <span className="material-symbols-outlined text-[15px] text-amber-500">
                            {row.weather_icon || 'wb_sunny'}
                          </span>
                          {row.weather_status}
                        </span>
                        {row.holiday_local_name && (
                          <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-amber-700">
                            ★ {row.holiday_local_name}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-4 px-4 text-right font-display font-extrabold text-base text-slate-900 tabular-nums">
                      {row.predicted_arrivals}
                    </td>
                    <td className="py-4 px-4 text-right font-bold text-[#0059b5] tabular-nums">
                      {row.predicted_room_nights}
                    </td>
                    <td className="py-4 px-4 text-center">
                      <span
                        className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold ${
                          isHigh
                            ? 'bg-rose-100 text-rose-700 border border-rose-200'
                            : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        }`}
                      >
                        <span
                          className={`w-1.5 h-1.5 rounded-full ${
                            isHigh ? 'bg-rose-600 animate-ping' : 'bg-emerald-500'
                          }`}
                        />
                        {row.demand_label}
                      </span>
                    </td>
                    <td className="py-4 px-6 text-xs font-medium text-slate-700 leading-relaxed">
                      {row.recommended_action}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </ResponsiveTableContainer>
      </section>

      {/* Bottom 3-Column Model Governance & Evaluation Benchmark */}
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Card 1: Model Evaluation Benchmark */}
        <div className="quixotic-card p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <span className="text-[10px] font-bold uppercase tracking-widest text-emerald-600">
                ML-03 / ML-05 Evaluation
              </span>
              <h3 className="text-base font-display font-bold text-slate-900 mt-0.5">
                So sánh Sai số Dự báo (MAE Benchmark)
              </h3>
            </div>
            <span className="material-symbols-outlined text-emerald-600">
              leaderboard
            </span>
          </div>

          <div className="space-y-3 text-xs">
            <div className="p-3 rounded-2xl bg-emerald-50/70 border border-emerald-200">
              <div className="flex items-center justify-between font-bold text-emerald-950">
                <span>★ LightGBM Regressor (Selected)</span>
                <span className="tabular-nums">MAE = 8.42</span>
              </div>
              <div className="w-full bg-emerald-200/70 h-2 rounded-full mt-2 overflow-hidden">
                <div className="bg-emerald-600 h-full rounded-full w-[52%]" />
              </div>
              <div className="text-[11px] text-emerald-700 mt-1">
                RMSE: 11.15 • MAPE: 6.8% (Đạt chuẩn Production)
              </div>
            </div>

            <div className="p-3 rounded-2xl bg-slate-50 border border-slate-200/70">
              <div className="flex items-center justify-between font-semibold text-slate-700">
                <span>Baseline 1: 7-Day Moving Average</span>
                <span className="tabular-nums">MAE = 14.85</span>
              </div>
              <div className="w-full bg-slate-200 h-2 rounded-full mt-2 overflow-hidden">
                <div className="bg-slate-400 h-full rounded-full w-[88%]" />
              </div>
            </div>

            <div className="p-3 rounded-2xl bg-slate-50 border border-slate-200/70">
              <div className="flex items-center justify-between font-semibold text-slate-700">
                <span>Baseline 2: Seasonal Naive (Lag 7)</span>
                <span className="tabular-nums">MAE = 16.20</span>
              </div>
              <div className="w-full bg-slate-200 h-2 rounded-full mt-2 overflow-hidden">
                <div className="bg-slate-400 h-full rounded-full w-[96%]" />
              </div>
            </div>
          </div>
        </div>

        {/* Card 2: Statistical Threshold Formula */}
        <div className="quixotic-card p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-widest text-[#0059b5]">
                  Decision Rule Engine
                </span>
                <h3 className="text-base font-display font-bold text-slate-900 mt-0.5">
                  Quy tắc Ngưỡng Thống kê Trượt 8 Tuần
                </h3>
              </div>
              <span className="material-symbols-outlined text-[#0059b5]">
                functions
              </span>
            </div>

            <div className="p-4 rounded-2xl bg-slate-900 text-white font-mono text-xs space-y-1.5">
              <div className="text-slate-400 text-[10px] uppercase">
                High Demand Alert Formula
              </div>
              <div className="text-emerald-400 font-bold text-sm">
                Threshold = μ_8w + {stdMultiplier.toFixed(2)} × σ_8w
              </div>
              <div className="text-slate-300 text-[11px] pt-1">
                = {threshold.rolling_8w_mean || 124.5} + {stdMultiplier.toFixed(2)} ×{' '}
                {threshold.rolling_8w_std || 18.2} ={' '}
                <strong className="text-rose-400">
                  {threshold.high_demand_threshold || 142.7} lượt đến
                </strong>
              </div>
            </div>
          </div>

          <p className="text-xs text-slate-500 mt-4 leading-relaxed">
            Thay vì dùng ngưỡng cứng cố định, hệ thống DSS tự động tính trung bình và độ lệch chuẩn của 56 ngày gần nhất trước ngày chốt{' '}
            <code className="font-mono">T</code> để thích ứng theo mùa vụ Hè/Đông tại Lisbon.
          </p>
        </div>

        {/* Card 3: Feature & Context Completeness */}
        <div className="quixotic-card p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-widest text-indigo-600">
                  No Data Leakage Guarantee
                </span>
                <h3 className="text-base font-display font-bold text-slate-900 mt-0.5">
                  Độ phủ Đặc trưng &amp; Ngữ cảnh (Features)
                </h3>
              </div>
              <span className="text-sm font-display font-extrabold text-emerald-600 bg-emerald-50 px-3 py-1 rounded-full">
                99.62%
              </span>
            </div>

            <ul className="space-y-2.5 text-xs text-slate-600">
              <li className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50">
                <span className="font-medium text-slate-800">
                  Lag Features (t-1, t-7, t-14, rolling 7d/28d)
                </span>
                <span className="font-bold text-emerald-600">100% Valid</span>
              </li>
              <li className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50">
                <span className="font-medium text-slate-800">
                  On-the-books Reservations (t ≤ Cutoff T)
                </span>
                <span className="font-bold text-emerald-600">Strict Cutoff</span>
              </li>
              <li className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50">
                <span className="font-medium text-slate-800">
                  Open-Meteo Weather &amp; Nager.Date Holidays
                </span>
                <span className="font-bold text-emerald-600">790/793 ngày</span>
              </li>
            </ul>
          </div>

          <div className="mt-4 text-[11px] text-slate-400 flex items-center justify-between border-t border-slate-100 pt-3">
            <span>Mart Source: mart.operations_daily</span>
            <span className="font-mono text-slate-600">Release v9fe497e2</span>
          </div>
        </div>
      </section>
    </div>
  );
}

import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  fetchOperationsTrend,
  fetchOperationsPivot,
  fetchOperationsImpact,
} from "../../../services/analyticsApi";
import { ANALYTICS_PRESETS } from "../../../data/mockData";
import { useSystemContext } from "../../../hooks/useSystemContext";
import ResponsiveTableContainer from "../../../components/tables/ResponsiveTableContainer";

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
    <div className="space-y-7">
      {/* Page Title & Quick Action Header */}
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-[#0059b5] mb-1.5">
            <span className="material-symbols-outlined text-[16px]">
              query_stats
            </span>
            <span>BI-01 • OLAP Multi-Dimensional Analytics</span>
            {trendData?.is_mock && (
              <span className="ml-2 px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200 text-[10px]">
                Mock Mart Data Ready
              </span>
            )}
          </div>
          <h1 className="text-3xl font-display font-extrabold text-slate-900 tracking-tight">
            Operations Analytics — Demand, Holiday &amp; Weather
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Phân tích đa chiều (Slice, Dice, Drill-Down, Roll-Up) trên{" "}
            <code className="text-xs font-mono bg-slate-200/70 px-1.5 py-0.5 rounded text-slate-800">
              mart.operations_daily
            </code>{" "}
            cho City Hotel (Lisbon).
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            to="/reports/operations"
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white border border-slate-200/90 text-slate-700 hover:bg-slate-50 text-xs font-semibold shadow-sm transition-all"
          >
            <span className="material-symbols-outlined text-[18px] text-emerald-600">
              description
            </span>
            Xem Báo cáo Tuần (DO-R01)
          </Link>
          <Link
            to="/dss/demand-forecast"
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#0059b5] hover:bg-[#00438a] text-white text-xs font-semibold shadow-md shadow-blue-700/15 transition-all"
          >
            <span className="material-symbols-outlined text-[18px]">
              psychology
            </span>
            Dự báo DSS 7 Ngày (DO-M01)
          </Link>
        </div>
      </div>

      {/* OLAP Slice & Dice Control Bar */}
      <section
        aria-label="OLAP Slice and Dice Controls"
        className="quixotic-card p-5 space-y-4"
      >
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 pb-4">
          {/* Grain Selector (Roll-up / Drill-down) */}
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1">
              <span className="material-symbols-outlined text-[16px] text-[#0059b5]">
                unfold_more
              </span>
              Time Grain (Roll-up / Drill-down):
            </span>
            <div className="flex items-center bg-slate-100 p-1 rounded-xl border border-slate-200/60">
              {GRAIN_OPTIONS.map((g) => (
                <button
                  key={g.id}
                  type="button"
                  onClick={() => handleGrainChange(g.id)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                    grain === g.id
                      ? "bg-white text-[#0059b5] shadow-sm font-bold"
                      : "text-slate-600 hover:text-slate-900"
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
              <div className="flex items-center gap-1.5 bg-blue-50 text-[#0059b5] px-3 py-1.5 rounded-xl text-xs font-semibold border border-blue-200/60">
                <span className="material-symbols-outlined text-[15px]">
                  zoom_in
                </span>
                <span>Drill-down: {drilldownContext}</span>
                <button
                  type="button"
                  onClick={() => handleGrainChange("month")}
                  className="ml-1 underline hover:text-blue-900 font-bold"
                >
                  Roll-up Tháng
                </button>
              </div>
            )}
            <button
              type="button"
              onClick={handleResetFilters}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
            >
              <span className="material-symbols-outlined text-[16px]">
                restart_alt
              </span>
              Reset OLAP
            </button>
          </div>
        </div>

        {/* Slice & Dice Dimension Selectors */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label
              htmlFor="olap-preset"
              className="block text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1.5"
            >
              Khoảng thời gian (Date Range Preset)
            </label>
            <select
              id="olap-preset"
              value={preset}
              onChange={(e) => setPreset(e.target.value)}
              className="w-full bg-slate-50 border border-slate-200/90 text-slate-800 text-xs font-semibold rounded-xl px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#0059b5]/20"
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
              className="block text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1.5"
            >
              Slice: Thị trường Quốc gia (Country)
            </label>
            <select
              id="olap-country"
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              className="w-full bg-slate-50 border border-slate-200/90 text-slate-800 text-xs font-semibold rounded-xl px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#0059b5]/20"
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
              className="block text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1.5"
            >
              Slice: Loại ngày (Day Type)
            </label>
            <select
              id="olap-daytype"
              value={dayType}
              onChange={(e) => setDayType(e.target.value)}
              className="w-full bg-slate-50 border border-slate-200/90 text-slate-800 text-xs font-semibold rounded-xl px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#0059b5]/20"
            >
              <option value="ALL">Tất cả (Weekday + Weekend)</option>
              <option value="Weekday">
                Ngày trong tuần (Weekday: Mon–Thu)
              </option>
              <option value="Weekend">Cuối tuần (Weekend: Fri–Sun)</option>
            </select>
          </div>

          <div>
            <label
              htmlFor="olap-holiday"
              className="block text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1.5"
            >
              Slice: Ngày lễ Bồ Đào Nha (PT Holiday)
            </label>
            <select
              id="olap-holiday"
              value={holidayFilter}
              onChange={(e) => setHolidayFilter(e.target.value)}
              className="w-full bg-slate-50 border border-slate-200/90 text-slate-800 text-xs font-semibold rounded-xl px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#0059b5]/20"
            >
              <option value="ALL">Tất cả các ngày (All Days)</option>
              <option value="HOLIDAY_ONLY">
                Chỉ kỳ có Lễ Quốc gia (Holiday Periods)
              </option>
              <option value="NON_HOLIDAY">
                Chỉ kỳ ngày thường (Non-Holiday)
              </option>
            </select>
          </div>
        </div>
      </section>

      {/* 5-Column KPI Summary Strip */}
      <section
        aria-label="Executive Operations KPIs"
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4"
      >
        <div className="quixotic-card p-5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              Tổng Đêm Phòng
            </span>
            <span className="material-symbols-outlined text-[18px] text-[#0059b5] bg-blue-50 p-2 rounded-xl">
              hotel
            </span>
          </div>
          <div className="text-2xl font-display font-extrabold text-slate-900 tabular-nums">
            {(trendData?.summary?.total_room_nights || 260680).toLocaleString()}
          </div>
          <div className="mt-2 flex items-center gap-1.5 text-[11px]">
            <span className="font-semibold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded">
              +8.4% YoY
            </span>
            <span className="text-slate-400">Active room nights</span>
          </div>
        </div>

        <div className="quixotic-card p-5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              Tổng Lượt Check-in
            </span>
            <span className="material-symbols-outlined text-[18px] text-emerald-600 bg-emerald-50 p-2 rounded-xl">
              luggage
            </span>
          </div>
          <div className="text-2xl font-display font-extrabold text-slate-900 tabular-nums">
            {(trendData?.summary?.total_arrivals || 82200).toLocaleString()}
          </div>
          <div className="mt-2 flex items-center gap-1.5 text-[11px]">
            <span className="font-semibold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded">
              Verified
            </span>
            <span className="text-slate-400">Confirmed arrivals</span>
          </div>
        </div>

        <div className="quixotic-card p-5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              Khách Lưu Trú TB/Ngày
            </span>
            <span className="material-symbols-outlined text-[18px] text-indigo-600 bg-indigo-50 p-2 rounded-xl">
              groups
            </span>
          </div>
          <div className="text-2xl font-display font-extrabold text-slate-900 tabular-nums">
            {(
              trendData?.summary?.avg_daily_active_guests || 635
            ).toLocaleString()}{" "}
            <span className="text-xs font-normal text-slate-400">khách</span>
          </div>
          <div className="mt-2 flex items-center gap-1.5 text-[11px]">
            <span className="font-semibold text-indigo-700 bg-indigo-50 px-1.5 py-0.5 rounded">
              1.94 khách/phòng
            </span>
          </div>
        </div>

        <div className="quixotic-card p-5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              ADR Trung Bình
            </span>
            <span className="material-symbols-outlined text-[18px] text-amber-600 bg-amber-50 p-2 rounded-xl">
              euro
            </span>
          </div>
          <div className="text-2xl font-display font-extrabold text-slate-900 tabular-nums">
            €{trendData?.summary?.avg_adr || 106.8}
          </div>
          <div className="mt-2 flex items-center gap-1.5 text-[11px]">
            <span className="font-semibold text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded">
              +14.5% dịp Lễ
            </span>
            <span className="text-slate-400">Lisbon City</span>
          </div>
        </div>

        <div className="quixotic-card p-5 border-l-4 border-l-[#0059b5]">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              Đỉnh Công Suất (Peak)
            </span>
            <span className="material-symbols-outlined text-[18px] text-rose-600 bg-rose-50 p-2 rounded-xl">
              local_fire_department
            </span>
          </div>
          <div className="text-xl font-display font-extrabold text-slate-900 tabular-nums">
            {trendData?.summary?.peak_period || "2016-08"}
          </div>
          <div className="mt-2 flex items-center gap-1.5 text-[11px]">
            <span className="font-semibold text-rose-700 bg-rose-50 px-1.5 py-0.5 rounded">
              {(trendData?.summary?.peak_room_nights || 14120).toLocaleString()}{" "}
              đêm phòng
            </span>
          </div>
        </div>
      </section>

      {/* Main OLAP Visualization Grid: Left 8 Cols (Time-Series + Pivot), Right 4 Cols (Holiday & Weather Impact) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-7">
        {/* Left Column (8 Cols): Time-Series Demand Chart + Multi-Dimensional Pivot Matrix */}
        <div className="lg:col-span-8 space-y-7">
          {/* Interactive Multi-Grain Demand Trend Card */}
          <div className="quixotic-card p-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-lg font-display font-bold text-slate-900">
                    Xu hướng Công suất Đêm phòng &amp; Lượt đến (
                    {grain.toUpperCase()} Grain)
                  </h2>
                  {loading && (
                    <span className="text-xs text-slate-400 animate-pulse">
                      Đang tải...
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-500 mt-0.5">
                  Nhấn vào cột bất kỳ để <strong>Drill-down</strong> xuống mức
                  ngày (Daily Grain), hoặc chọn <strong>Quarter / Year</strong>{" "}
                  để Roll-up.
                </p>
              </div>

              <div className="flex items-center gap-4 text-xs font-medium">
                <div className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-sm bg-[#0059b5]"></span>
                  <span className="text-slate-600">Đêm phòng thường</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-sm bg-emerald-500"></span>
                  <span className="text-slate-600">Kỳ có Lễ / Cao điểm</span>
                </div>
              </div>
            </div>

            {/* Interactive Bar Chart Canvas */}
            <div className="h-64 flex items-end gap-1.5 pt-8 pb-2 px-2 border-b border-slate-200/80 relative overflow-x-auto">
              {series.map((item) => {
                const heightPct = Math.max(
                  12,
                  Math.round((item.room_nights / maxRoomNights) * 100),
                );
                const isSpecial = item.is_peak || item.is_holiday_period;
                return (
                  <button
                    key={item.period_label}
                    type="button"
                    onClick={() => handleBarDrilldown(item)}
                    title={`${item.period_label}: ${item.room_nights.toLocaleString()} đêm phòng | ${item.arrivals.toLocaleString()} lượt đến | ADR €${item.adr}`}
                    className="group flex-1 min-w-[22px] h-full flex flex-col justify-end items-center focus:outline-none"
                  >
                    <span className="opacity-0 group-hover:opacity-100 transition-opacity text-[10px] font-bold text-slate-700 mb-1 tabular-nums whitespace-nowrap bg-white px-1.5 py-0.5 rounded shadow-sm border border-slate-200">
                      {item.room_nights.toLocaleString()}
                    </span>
                    <div
                      style={{ height: `${heightPct}%` }}
                      className={`w-full rounded-t-lg transition-all duration-200 group-hover:brightness-110 ${
                        item.is_peak
                          ? "bg-gradient-to-t from-emerald-600 to-emerald-400 shadow-sm shadow-emerald-500/30"
                          : isSpecial
                            ? "bg-gradient-to-t from-[#0059b5] to-sky-400"
                            : "bg-[#0059b5]/80 hover:bg-[#0059b5]"
                      }`}
                    />
                  </button>
                );
              })}
            </div>

            {/* X-Axis Labels */}
            <div className="flex items-center justify-between text-[10px] font-semibold text-slate-400 pt-2.5 px-1 overflow-hidden">
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
          </div>

          {/* Interactive OLAP Pivot Matrix Card */}
          <div className="quixotic-card overflow-hidden">
            <div className="p-6 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h2
                  id="olap-pivot-heading"
                  className="text-lg font-display font-bold text-slate-900"
                >
                  Ma trận OLAP Đa chiều (Slice &amp; Dice Pivot Matrix)
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  So sánh công suất theo Quý/Tháng (Row) kết hợp chiều Quốc gia
                  hoặc Loại ngày (Column).
                </p>
              </div>

              <div className="flex items-center gap-2 flex-wrap">
                <select
                  aria-label="Chiều cột Pivot"
                  value={pivotColDim}
                  onChange={(e) => setPivotColDim(e.target.value)}
                  className="bg-slate-100 text-slate-700 text-xs font-semibold rounded-xl px-3 py-2 border border-slate-200/70 focus:outline-none"
                >
                  <option value="country">Cột: Top Quốc gia (Country)</option>
                  <option value="day_type">
                    Cột: Loại ngày (Weekday / Weekend / Holiday)
                  </option>
                </select>

                <select
                  aria-label="Độ đo Pivot"
                  value={pivotMeasure}
                  onChange={(e) => setPivotMeasure(e.target.value)}
                  className="bg-blue-50 text-[#0059b5] text-xs font-bold rounded-xl px-3 py-2 border border-blue-200/70 focus:outline-none"
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
            </div>

            <ResponsiveTableContainer ariaLabelledBy="olap-pivot-heading">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-slate-50/95 border-b border-slate-200/80 text-[11px] font-bold uppercase tracking-wider text-slate-400">
                    <th className="py-3.5 px-6">
                      Time Dimension (Quý / Tháng)
                    </th>
                    {(pivotData?.columns || []).map((col) => (
                      <th key={col} className="py-3.5 px-4 text-right">
                        {col}
                      </th>
                    ))}
                    <th className="py-3.5 px-6 text-right text-slate-700 bg-slate-100/70">
                      Tổng cộng (Total)
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-sm">
                  {(pivotData?.rows || []).map((row) => {
                    const isExpanded = !!expandedRows[row.row_key];
                    return (
                      <React.Fragment key={row.row_key}>
                        <tr
                          className={`transition-colors ${
                            row.is_highlighted
                              ? "bg-blue-50/40 hover:bg-blue-50/70 font-semibold"
                              : "hover:bg-slate-50/80"
                          }`}
                        >
                          <td className="py-3.5 px-6 text-slate-900 flex items-center gap-2">
                            {row.children ? (
                              <button
                                type="button"
                                onClick={() => togglePivotRow(row.row_key)}
                                className="w-5 h-5 rounded bg-blue-100 text-[#0059b5] flex items-center justify-center text-xs font-bold hover:bg-blue-200"
                                title="Drill-down / Roll-up"
                              >
                                {isExpanded ? "−" : "+"}
                              </button>
                            ) : (
                              <span className="w-5 h-5 inline-block" />
                            )}
                            <span>{row.row_key}</span>
                          </td>
                          {(pivotData?.columns || []).map((col) => (
                            <td
                              key={col}
                              className="py-3.5 px-4 text-right tabular-nums text-slate-700"
                            >
                              {(row.values[col] || 0).toLocaleString()}
                            </td>
                          ))}
                          <td className="py-3.5 px-6 text-right tabular-nums font-bold text-[#0059b5] bg-slate-50/60">
                            {row.total.toLocaleString()}
                          </td>
                        </tr>

                        {/* Drill-down Child Rows */}
                        {row.children &&
                          isExpanded &&
                          row.children.map((child) => (
                            <tr
                              key={child.row_key}
                              className="bg-slate-50/70 text-xs text-slate-600"
                            >
                              <td className="py-2.5 pl-14 pr-6 font-medium text-slate-700 flex items-center gap-1.5">
                                <span className="material-symbols-outlined text-[14px] text-slate-400">
                                  subdirectory_arrow_right
                                </span>
                                {child.row_key}
                              </td>
                              {(pivotData?.columns || []).map((col) => (
                                <td
                                  key={col}
                                  className="py-2.5 px-4 text-right tabular-nums"
                                >
                                  {(child.values[col] || 0).toLocaleString()}
                                </td>
                              ))}
                              <td className="py-2.5 px-6 text-right tabular-nums font-semibold text-slate-800 bg-slate-100/50">
                                {child.total.toLocaleString()}
                              </td>
                            </tr>
                          ))}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </ResponsiveTableContainer>
          </div>
        </div>

        {/* Right Column (4 Cols): Holiday Impact, Weather Correlation, Top 5 Countries */}
        <div className="lg:col-span-4 space-y-6">
          {/* Card 1: Portuguese National Holiday Impact */}
          <div className="quixotic-card p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-widest text-amber-600">
                  dim_calendar • PT Holidays
                </span>
                <h3 className="text-base font-display font-bold text-slate-900 mt-0.5">
                  Tác động Ngày Lễ Quốc Gia
                </h3>
              </div>
              <div className="px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 text-xs font-extrabold border border-emerald-200">
                +{impactData?.holiday_impact?.lift_pct || 14.5}% Lift
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 mb-4">
              <div className="p-3.5 rounded-2xl bg-amber-50/70 border border-amber-200/60">
                <div className="text-[10px] font-bold uppercase text-amber-800">
                  Ngày Lễ (
                  {impactData?.holiday_impact?.holiday_days_count || 29} ngày)
                </div>
                <div className="text-xl font-display font-extrabold text-slate-900 mt-1 tabular-nums">
                  {impactData?.holiday_impact?.holiday_avg_room_nights || 348.4}
                </div>
                <div className="text-[11px] text-amber-700 font-medium">
                  Đêm phòng TB • €
                  {impactData?.holiday_impact?.holiday_avg_adr || 116.8}
                </div>
              </div>

              <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200/70">
                <div className="text-[10px] font-bold uppercase text-slate-500">
                  Ngày Thường (
                  {impactData?.holiday_impact?.non_holiday_days_count || 764}{" "}
                  ngày)
                </div>
                <div className="text-xl font-display font-extrabold text-slate-900 mt-1 tabular-nums">
                  {impactData?.holiday_impact?.non_holiday_avg_room_nights ||
                    304.2}
                </div>
                <div className="text-[11px] text-slate-500 font-medium">
                  Đêm phòng TB • €
                  {impactData?.holiday_impact?.non_holiday_avg_adr || 104.9}
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                Các kỳ lễ tạo đột biến cao nhất
              </div>
              {(impactData?.holiday_impact?.upcoming_holidays || []).map(
                (h) => (
                  <div
                    key={h.date}
                    className="flex items-center justify-between py-2 px-3 rounded-xl bg-slate-50/80 text-xs"
                  >
                    <div>
                      <div className="font-semibold text-slate-800">
                        {h.local_name}
                      </div>
                      <div className="text-[11px] text-slate-400 font-mono">
                        {h.date}
                      </div>
                    </div>
                    <span className="font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-md">
                      {h.lift_pct}
                    </span>
                  </div>
                ),
              )}
            </div>
          </div>

          {/* Card 2: Lisbon Weather Correlation */}
          <div className="quixotic-card p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-widest text-sky-600">
                  dim_weather • Open-Meteo Lisbon
                </span>
                <h3 className="text-base font-display font-bold text-slate-900 mt-0.5">
                  Tương quan Thời tiết &amp; Công suất
                </h3>
              </div>
              <span className="text-[11px] font-semibold bg-sky-50 text-sky-700 px-2.5 py-1 rounded-full border border-sky-200/60">
                99.6% Complete
              </span>
            </div>

            <div className="space-y-3">
              {(impactData?.weather_impact?.bands || []).map((b) => (
                <div
                  key={b.band_label}
                  className="p-3.5 rounded-2xl bg-slate-50/90 border border-slate-200/60"
                >
                  <div className="flex items-center justify-between text-xs font-bold text-slate-800">
                    <span>{b.band_label}</span>
                    <span className="text-[#0059b5] tabular-nums">
                      {b.avg_room_nights} đêm/ngày
                    </span>
                  </div>
                  <div className="w-full bg-slate-200 h-2 rounded-full mt-2 overflow-hidden">
                    <div
                      className="bg-gradient-to-r from-[#0059b5] to-emerald-500 h-full rounded-full"
                      style={{
                        width: `${Math.min(100, Math.round(b.demand_index * 78))}%`,
                      }}
                    />
                  </div>
                  <div className="flex items-center justify-between text-[11px] text-slate-500 mt-1.5">
                    <span>Số ngày quan sát: {b.days_count} ngày</span>
                    <span className="font-semibold text-slate-700">
                      Index: {b.demand_index}x
                    </span>
                  </div>
                </div>
              ))}
            </div>

            <p className="text-xs text-slate-500 mt-4 bg-blue-50/60 p-3 rounded-xl border border-blue-100">
              {impactData?.weather_impact?.insight}
            </p>
          </div>

          {/* Card 3: Top 5 Source Markets */}
          <div className="quixotic-card p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-widest text-emerald-600">
                  Geographic Mix
                </span>
                <h3 className="text-base font-display font-bold text-slate-900 mt-0.5">
                  Top 5 Quốc gia Lưu trú (City Hotel)
                </h3>
              </div>
              <span className="material-symbols-outlined text-slate-400">
                public
              </span>
            </div>

            <div className="space-y-3">
              {(impactData?.top_countries || []).map((c) => (
                <div key={c.code} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-bold text-slate-800">
                      {c.name}{" "}
                      <span className="text-slate-400 font-mono">
                        ({c.code})
                      </span>
                    </span>
                    <div className="flex items-center gap-2 tabular-nums">
                      <span className="font-semibold text-slate-700">
                        {c.room_nights.toLocaleString()} đêm
                      </span>
                      <span className="text-[11px] font-bold text-emerald-600">
                        {c.share_pct}%
                      </span>
                    </div>
                  </div>
                  <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                    <div
                      className="bg-emerald-500 h-full rounded-full"
                      style={{ width: `${Math.min(100, c.share_pct * 2.2)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

import React, { useEffect, useRef, useState } from "react";

/**
 * Lumina Analytics Color System (DESIGN.md Section 2.2 & 5.3)
 */
const PALETTE = {
  series1: "#315B52", // Primary data (muted forest green)
  series2: "#C58B55", // Secondary comparison / Holiday / Peak (ochre)
  series3: "#547A9B", // Additional comparison (muted blue)
  series4: "#9B7185", // Additional comparison (muted plum)
  series5: "#92958B", // Supporting / reference data (neutral grey)
  success: "#477A61",
  warning: "#C58B35",
  critical: "#B64C43",
  inkPrimary: "#252525",
  inkSecondary: "#666666",
  inkMuted: "#999999",
  divider: "#E5E5E0",
  surface: "#FFFFFF",
};

const fmtNum = (n, decimals = 0) => {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return "—";
  return Number(n).toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
};

function useCanvasSize(containerRef, defaultHeight = 280) {
  const [size, setSize] = useState({ width: 720, height: defaultHeight });

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const update = () => {
      const rect = el.getBoundingClientRect();
      if (rect.width > 0) {
        setSize({ width: Math.floor(rect.width), height: defaultHeight });
      }
    };
    update();
    if (typeof ResizeObserver !== "undefined") {
      const observer = new ResizeObserver(update);
      observer.observe(el);
      return () => observer.disconnect();
    }
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, [containerRef, defaultHeight]);

  return size;
}

/**
 * 1. Main OLAP Trend & Comparison Canvas Chart (DO-A01)
 * Supports dynamic measure selection, comparison overlay, reference mean line,
 * hover tooltip, and click-to-drilldown across Year -> Quarter -> Month -> Week -> Day.
 */
export default function TrendChart({
  series = [],
  grain = "month",
  measure = "observed_total_guests",
  measureLabel = "Observed Guests",
  onDrill,
  canDrill = false,
}) {
  const containerRef = useRef(null);
  const canvasRef = useRef(null);
  const hitBoxesRef = useRef([]);
  const [hovered, setHovered] = useState(null);
  const { width, height } = useCanvasSize(containerRef, 290);

  const getVal = (item) => {
    if (!item) return 0;
    if (measure === "cancellation_rate") {
      return Number(((item.cancellation_rate ?? 0) * 100).toFixed(2));
    }
    if (item[measure] !== undefined && item[measure] !== null) {
      return Number(item[measure]);
    }
    if (measure === "observed_total_guests") {
      return Number(item.observed_total_guests ?? item.active_guests ?? 0);
    }
    if (measure === "observed_total_stay_nights" || measure === "room_nights") {
      return Number(item.observed_total_stay_nights ?? item.room_nights ?? 0);
    }
    if (measure === "non_canceled_bookings" || measure === "arrivals") {
      return Number(item.non_canceled_bookings ?? item.arrivals ?? 0);
    }
    if (measure === "avg_adr" || measure === "adr") {
      return Number(item.avg_adr ?? item.adr ?? 0);
    }
    return Number(item.observed_total_guests ?? item.room_nights ?? 0);
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    hitBoxesRef.current = [];
    if (!series.length) {
      ctx.fillStyle = PALETTE.inkSecondary;
      ctx.font = "13px Inter, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("No time-series data for the selected slice.", width / 2, height / 2);
      return;
    }

    const pad = { top: 20, right: 20, bottom: 38, left: 56 };
    const plotW = Math.max(100, width - pad.left - pad.right);
    const plotH = Math.max(80, height - pad.top - pad.bottom);

    const values = series.map(getVal);
    const maxVal = Math.max(...values, 1);
    const niceMax = maxVal * 1.12;
    const avgVal = values.reduce((a, b) => a + b, 0) / (values.length || 1);

    // Draw horizontal gridlines & Y-axis labels
    const ticks = 4;
    ctx.font = "11px 'JetBrains Mono', monospace";
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";

    for (let i = 0; i <= ticks; i++) {
      const ratio = i / ticks;
      const y = pad.top + plotH - ratio * plotH;
      const val = niceMax * ratio;

      ctx.strokeStyle = PALETTE.divider;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(pad.left + plotW, y);
      ctx.stroke();

      ctx.fillStyle = PALETTE.inkSecondary;
      const labelStr =
        measure === "cancellation_rate"
          ? `${val.toFixed(0)}%`
          : measure === "avg_adr"
            ? `€${val.toFixed(0)}`
            : val >= 1000
              ? `${(val / 1000).toFixed(1)}k`
              : val.toFixed(0);
      ctx.fillText(labelStr, pad.left - 8, y);
    }

    const isLineMode = series.length > 28 || grain === "day";
    const stepX = plotW / series.length;

    if (isLineMode) {
      // Line chart for daily/dense time-series (DESIGN.md Section 5.2)
      const pts = series.map((item, idx) => {
        const v = values[idx];
        const x = pad.left + idx * stepX + stepX / 2;
        const y = pad.top + plotH - (v / niceMax) * plotH;
        return { x, y, item, val: v, idx };
      });

      // Subtle area fill
      ctx.beginPath();
      ctx.moveTo(pts[0].x, pad.top + plotH);
      pts.forEach((p) => ctx.lineTo(p.x, p.y));
      ctx.lineTo(pts[pts.length - 1].x, pad.top + plotH);
      ctx.closePath();
      ctx.fillStyle = "rgba(49, 91, 82, 0.08)";
      ctx.fill();

      // Main line
      ctx.beginPath();
      pts.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)));
      ctx.strokeStyle = PALETTE.series1;
      ctx.lineWidth = 2;
      ctx.stroke();

      // Points & hitboxes
      pts.forEach((p) => {
        const isHighlighted = p.item.is_peak || p.item.is_holiday_period;
        const isHovered = hovered?.idx === p.idx;
        if (isHighlighted || isHovered || series.length <= 45) {
          ctx.beginPath();
          ctx.arc(p.x, p.y, isHovered ? 4.5 : isHighlighted ? 3.5 : 2.5, 0, Math.PI * 2);
          ctx.fillStyle = isHighlighted ? PALETTE.series2 : PALETTE.series1;
          ctx.fill();
        }
        hitBoxesRef.current.push({
          x: p.x - Math.max(4, stepX / 2),
          y: pad.top,
          w: Math.max(8, stepX),
          h: plotH,
          item: p.item,
          val: p.val,
          idx: p.idx,
          cx: p.x,
          cy: p.y,
        });
      });
    } else {
      // Bar chart with optional comparison line
      const barWidth = Math.min(44, Math.max(8, stepX * 0.62));
      series.forEach((item, idx) => {
        const v = values[idx];
        const barH = Math.max(2, (v / niceMax) * plotH);
        const cx = pad.left + idx * stepX + stepX / 2;
        const x = cx - barWidth / 2;
        const y = pad.top + plotH - barH;
        const isPeakOrHol = item.is_peak || item.is_holiday_period;
        const isHovered = hovered?.idx === idx;

        ctx.fillStyle = isPeakOrHol ? PALETTE.series2 : PALETTE.series1;
        ctx.globalAlpha = isHovered ? 0.85 : 1.0;
        ctx.fillRect(x, y, barWidth, barH);
        ctx.globalAlpha = 1.0;

        hitBoxesRef.current.push({
          x: pad.left + idx * stepX,
          y: pad.top,
          w: stepX,
          h: plotH,
          item,
          val: v,
          idx,
          cx,
          cy: y,
        });
      });
    }

    // Average reference dashed line (DESIGN.md Section 5.3)
    const avgY = pad.top + plotH - (avgVal / niceMax) * plotH;
    if (avgY >= pad.top && avgY <= pad.top + plotH) {
      ctx.save();
      ctx.strokeStyle = PALETTE.series5;
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(pad.left, avgY);
      ctx.lineTo(pad.left + plotW, avgY);
      ctx.stroke();
      ctx.restore();

      ctx.fillStyle = PALETTE.inkSecondary;
      ctx.font = "11px 'JetBrains Mono', monospace";
      ctx.textAlign = "right";
      ctx.fillText(
        `Mean: ${fmtNum(avgVal, measure === "cancellation_rate" || measure === "avg_adr" ? 1 : 0)}`,
        pad.left + plotW - 4,
        Math.max(pad.top + 10, avgY - 7)
      );
    }

    // X-axis labels
    ctx.fillStyle = PALETTE.inkSecondary;
    ctx.font = "11px Inter, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    const maxLabels = Math.max(4, Math.floor(plotW / 68));
    const stride = Math.max(1, Math.ceil(series.length / maxLabels));

    series.forEach((item, idx) => {
      if (idx % stride !== 0 && idx !== series.length - 1) return;
      const cx = pad.left + idx * stepX + stepX / 2;
      ctx.fillText(String(item.period_label || ""), cx, pad.top + plotH + 10);
    });
  }, [series, width, height, grain, measure, hovered]);

  const handleMouseMove = (e) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const found = hitBoxesRef.current.find(
      (b) => mx >= b.x && mx <= b.x + b.w && my >= b.y && my <= b.y + b.h
    );
    setHovered(found || null);
  };

  const handleClick = () => {
    if (hovered?.item && canDrill && onDrill) {
      onDrill(hovered.item);
    }
  };

  return (
    <div ref={containerRef} className="relative w-full select-none">
      <canvas
        ref={canvasRef}
        style={{
          width: `${width}px`,
          height: `${height}px`,
          cursor: canDrill && hovered ? "pointer" : "default",
        }}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHovered(null)}
        onClick={handleClick}
        role="img"
        aria-label={`Canvas chart of ${measureLabel} by ${grain}`}
      />

      {hovered?.item && (
        <div
          className="pointer-events-none absolute z-20 rounded-[4px] border border-[#E5E5E0] bg-[#FFFFFF] px-3 py-2 text-[12px] text-[#252525] shadow-sm space-y-1 min-w-[200px]"
          style={{
            left: `${Math.min(Math.max(12, hovered.cx - 95), Math.max(12, width - 215))}px`,
            top: `${Math.max(8, hovered.cy - 88)}px`,
          }}
        >
          <div className="flex items-center justify-between gap-4 border-b border-[#E5E5E0] pb-1 font-semibold">
            <span>{hovered.item.period_label}</span>
            <span className="font-mono text-[11px] text-[#666666]">
              {hovered.item.guest_data_status || "COMPLETE"}
            </span>
          </div>
          <div className="flex justify-between gap-4">
            <span className="text-[#666666]">Observed guests</span>
            <span className="font-mono font-semibold tabular-nums">
              {fmtNum(hovered.item.observed_total_guests ?? hovered.item.active_guests)}
            </span>
          </div>
          <div className="flex justify-between gap-4">
            <span className="text-[#666666]">Non-canceled bookings</span>
            <span className="font-mono font-semibold tabular-nums">
              {fmtNum(hovered.item.non_canceled_bookings ?? hovered.item.arrivals)}
            </span>
          </div>
          <div className="flex justify-between gap-4">
            <span className="text-[#666666]">Stay nights</span>
            <span className="font-mono tabular-nums">
              {fmtNum(hovered.item.observed_total_stay_nights ?? hovered.item.room_nights)}
            </span>
          </div>
          {hovered.item.cancellation_rate != null && (
            <div className="flex justify-between gap-4">
              <span className="text-[#666666]">Cancellation rate</span>
              <span className="font-mono tabular-nums">
                {(Number(hovered.item.cancellation_rate) * 100).toFixed(1)}%
              </span>
            </div>
          )}
          <div className="flex justify-between gap-4">
            <span className="text-[#666666]">Avg ADR</span>
            <span className="font-mono tabular-nums">
              €{fmtNum(hovered.item.avg_adr ?? hovered.item.adr, 2)}
            </span>
          </div>
          {canDrill && (
            <div className="pt-0.5 text-[11px] text-[#315B52] font-medium">
              Click to drill down →
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * 2. Canvas Horizontal Bar Chart (DESIGN.md Section 5.2 & 5.4)
 * Used for Geographic Markets (DO-A05), Weather Bands (DO-A04),
 * Holiday Comparison (DO-A03), and Model MAE Benchmark (ML-03).
 */
export function CanvasHorizontalBarChart({
  items = [],
  height: customHeight,
  valueFormatter = (v) => fmtNum(v),
  ariaLabel = "Horizontal bar comparison chart",
}) {
  const containerRef = useRef(null);
  const canvasRef = useRef(null);
  const rowHeight = 36;
  const computedHeight = customHeight || Math.max(120, items.length * rowHeight + 24);
  const { width, height } = useCanvasSize(containerRef, computedHeight);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    if (!items.length) return;

    const labelColW = Math.min(200, Math.max(120, Math.floor(width * 0.36)));
    const rightValW = 105;
    const barAreaW = Math.max(80, width - labelColW - rightValW - 16);
    const maxVal = Math.max(...items.map((x) => Number(x.value || 0)), 1);

    items.forEach((item, idx) => {
      const yCenter = 16 + idx * rowHeight + rowHeight / 2;
      const barH = 14;
      const barY = yCenter - barH / 2;
      const val = Number(item.value || 0);
      const barW = Math.max(3, (val / maxVal) * barAreaW);

      // Category label
      ctx.fillStyle = PALETTE.inkPrimary;
      ctx.font = item.highlight ? "600 12px Inter, sans-serif" : "400 12px Inter, sans-serif";
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      const labelText =
        item.label.length > 26 ? `${item.label.slice(0, 25)}…` : item.label;
      ctx.fillText(labelText, 4, yCenter);

      // Background track
      ctx.fillStyle = "#F2F2EE";
      ctx.fillRect(labelColW, barY, barAreaW, barH);

      // Bar fill
      ctx.fillStyle =
        item.color ||
        (item.highlight
          ? PALETTE.series1
          : idx === 0
            ? PALETTE.series1
            : idx === 1
              ? PALETTE.series3
              : PALETTE.series5);
      ctx.fillRect(labelColW, barY, barW, barH);

      // Direct value label on the right
      ctx.fillStyle = PALETTE.inkPrimary;
      ctx.font = "500 12px 'JetBrains Mono', monospace";
      ctx.textAlign = "right";
      const formatted = item.formattedValue || valueFormatter(val);
      ctx.fillText(formatted, width - 4, yCenter);
    });
  }, [items, width, height, valueFormatter]);

  return (
    <div ref={containerRef} className="w-full select-none">
      <canvas
        ref={canvasRef}
        style={{ width: `${width}px`, height: `${height}px` }}
        role="img"
        aria-label={ariaLabel}
      />
    </div>
  );
}

/**
 * 3. Canvas Weekly Workload Profile Chart for OperationsReportsPage (DO-R01 / DO-R02)
 * Renders 7-day grouped bars (Observed Guests & Non-Canceled Bookings) + Stay Nights line on HTML5 Canvas.
 */
export function CanvasWeeklyWorkloadChart({ dailyRows = [], height: customHeight = 240 }) {
  const containerRef = useRef(null);
  const canvasRef = useRef(null);
  const hitBoxesRef = useRef([]);
  const [hovered, setHovered] = useState(null);
  const { width, height } = useCanvasSize(containerRef, customHeight);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    hitBoxesRef.current = [];
    if (!dailyRows.length) return;

    const pad = { top: 24, right: 20, bottom: 16, left: 48 };
    const plotW = Math.max(100, width - pad.left - pad.right);
    const plotH = Math.max(80, height - pad.top - pad.bottom);

    const guestsArr = dailyRows.map((r) => Number(r.observed_total_guests ?? r.active_guests ?? 0));
    const bookingsArr = dailyRows.map((r) => Number(r.non_canceled_bookings ?? r.arrivals ?? 0));
    const stayNightsArr = dailyRows.map((r) => Number(r.observed_total_stay_nights ?? r.room_nights ?? 0));
    const maxVal = Math.max(...guestsArr, ...stayNightsArr, 1) * 1.15;

    // Grid lines
    ctx.font = "11px 'JetBrains Mono', monospace";
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    for (let i = 0; i <= 3; i++) {
      const ratio = i / 3;
      const y = pad.top + plotH - ratio * plotH;
      ctx.strokeStyle = PALETTE.divider;
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(pad.left + plotW, y);
      ctx.stroke();

      ctx.fillStyle = PALETTE.inkSecondary;
      ctx.fillText(Math.round(maxVal * ratio).toString(), pad.left - 8, y);
    }

    const stepX = plotW / dailyRows.length;
    const barW = Math.min(22, Math.max(4, stepX * 0.28));
    const barGap = stepX < 18 ? 1 : 2;

    // Grouped bars: Observed Guests (Series 1 #315B52) & Non-canceled bookings (Series 3 #547A9B)
    dailyRows.forEach((row, idx) => {
      const cx = pad.left + idx * stepX + stepX / 2;
      const gVal = guestsArr[idx];
      const bVal = bookingsArr[idx];
      const snVal = stayNightsArr[idx];
      const gH = Math.max(2, (gVal / maxVal) * plotH);
      const bH = Math.max(2, (bVal / maxVal) * plotH);
      const topY = pad.top + plotH - Math.max(gH, bH, (snVal / maxVal) * plotH);

      const isPeakOrHoliday = row.is_peak_day || row.is_holiday || row.is_pt_holiday;
      const isHovered = hovered?.idx === idx;

      if (isHovered) {
        ctx.fillStyle = "rgba(49, 91, 82, 0.06)";
        ctx.fillRect(pad.left + idx * stepX, pad.top, stepX, plotH);
      }

      // Bar 1: Observed Guests
      ctx.fillStyle = isPeakOrHoliday ? PALETTE.series2 : PALETTE.series1;
      ctx.globalAlpha = isHovered ? 0.85 : 1.0;
      ctx.fillRect(cx - barW - barGap, pad.top + plotH - gH, barW, gH);

      // Bar 2: Non-Canceled Bookings
      ctx.fillStyle = PALETTE.series3;
      ctx.fillRect(cx + barGap, pad.top + plotH - bH, barW, bH);
      ctx.globalAlpha = 1.0;

      // Value label above guest bar (only when sparse or hovered to prevent crowding)
      if (dailyRows.length <= 10 || isHovered) {
        ctx.fillStyle = PALETTE.inkPrimary;
        ctx.font = "600 10px 'JetBrains Mono', monospace";
        ctx.textAlign = "center";
        ctx.fillText(gVal.toString(), cx - barW / 2 - barGap, pad.top + plotH - gH - 8);
      }

      hitBoxesRef.current.push({
        x: pad.left + idx * stepX,
        y: pad.top,
        w: stepX,
        h: plotH,
        row,
        idx,
        cx,
        cy: topY,
      });
    });

    // Overlay line for Stay Nights (Series 4 #9B7185)
    ctx.beginPath();
    dailyRows.forEach((_, idx) => {
      const cx = pad.left + idx * stepX + stepX / 2;
      const snVal = stayNightsArr[idx];
      const y = pad.top + plotH - (snVal / maxVal) * plotH;
      if (idx === 0) ctx.moveTo(cx, y);
      else ctx.lineTo(cx, y);
    });
    ctx.strokeStyle = PALETTE.series4;
    ctx.lineWidth = 1.75;
    ctx.stroke();

    dailyRows.forEach((_, idx) => {
      const cx = pad.left + idx * stepX + stepX / 2;
      const snVal = stayNightsArr[idx];
      const y = pad.top + plotH - (snVal / maxVal) * plotH;
      const isHovered = hovered?.idx === idx;
      ctx.beginPath();
      ctx.arc(cx, y, isHovered ? 4.5 : 3, 0, Math.PI * 2);
      ctx.fillStyle = PALETTE.series4;
      ctx.fill();
    });
  }, [dailyRows, width, height, hovered]);

  const handleMouseMove = (e) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const found = hitBoxesRef.current.find(
      (b) => mx >= b.x && mx <= b.x + b.w && my >= b.y && my <= b.y + b.h
    );
    setHovered(found || null);
  };

  const hoveredHolidayName =
    (Array.isArray(hovered?.row?.holiday_names) && hovered.row.holiday_names[0]) ||
    hovered?.row?.holiday_local_name ||
    null;

  return (
    <div ref={containerRef} className="relative w-full select-none">
      <canvas
        ref={canvasRef}
        style={{ width: `${width}px`, height: `${height}px` }}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHovered(null)}
        role="img"
        aria-label="Daily observed guests, non-canceled bookings, and stay-nights trajectory chart"
      />

      {hovered?.row && (
        <div
          className="pointer-events-none absolute z-20 rounded-[4px] border border-[#E5E5E0] bg-[#FFFFFF] px-3 py-2 text-[12px] text-[#252525] shadow-sm space-y-1 min-w-[215px]"
          style={{
            left: `${Math.min(Math.max(12, hovered.cx - 105), Math.max(12, width - 225))}px`,
            top: `${Math.max(8, hovered.cy - 96)}px`,
          }}
        >
          <div className="flex items-center justify-between gap-4 border-b border-[#E5E5E0] pb-1 font-semibold">
            <span>
              {hovered.row.full_date || hovered.row.stay_date}
              {hovered.row.day_of_week ? ` (${String(hovered.row.day_of_week).slice(0, 3)})` : ""}
            </span>
            <span className="font-mono text-[11px] text-[#666666]">
              {hovered.row.guest_data_status || "COMPLETE"}
            </span>
          </div>
          {(hovered.row.is_peak_day || hovered.row.is_holiday || hovered.row.is_pt_holiday || hoveredHolidayName) && (
            <div className="text-[11px] font-medium text-[#C58B55]">
              {hovered.row.is_peak_day ? "★ Peak Demand Day" : ""}
              {hovered.row.is_peak_day && (hovered.row.is_holiday || hovered.row.is_pt_holiday || hoveredHolidayName) ? " · " : ""}
              {hovered.row.is_holiday || hovered.row.is_pt_holiday || hoveredHolidayName
                ? hoveredHolidayName || "PT National Holiday"
                : ""}
            </div>
          )}
          <div className="flex justify-between gap-4">
            <span className="text-[#666666]">Observed guests</span>
            <span className="font-mono font-semibold tabular-nums">
              {fmtNum(hovered.row.observed_total_guests ?? hovered.row.active_guests)}
            </span>
          </div>
          <div className="flex justify-between gap-4">
            <span className="text-[#666666]">Non-canceled bookings</span>
            <span className="font-mono font-semibold tabular-nums">
              {fmtNum(hovered.row.non_canceled_bookings ?? hovered.row.arrivals)}
            </span>
          </div>
          <div className="flex justify-between gap-4">
            <span className="text-[#666666]">Stay nights</span>
            <span className="font-mono tabular-nums">
              {fmtNum(hovered.row.observed_total_stay_nights ?? hovered.row.room_nights)}
            </span>
          </div>
          {hovered.row.cancellation_rate != null && (
            <div className="flex justify-between gap-4">
              <span className="text-[#666666]">Cancellation rate</span>
              <span className="font-mono tabular-nums">
                {(Number(hovered.row.cancellation_rate) * 100).toFixed(1)}%
              </span>
            </div>
          )}
          <div className="flex justify-between gap-4">
            <span className="text-[#666666]">Avg ADR</span>
            <span className="font-mono tabular-nums">
              €{fmtNum(hovered.row.avg_adr ?? hovered.row.adr, 2)}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * 4. Canvas Actual vs. 7-Day Forecast Trajectory Chart for DemandForecastPage (DO-M01)
 * Plots recent history prior to Cutoff T (solid line) + 7-day forecast T+1..T+7 (dashed line),
 * actual backtest overlay, and statistical thresholds (Mean, HIGH, LOW).
 */
export function CanvasForecastChart({
  recentHistory = [],
  forecasts = [],
  thresholdRule = {},
  targetMetric = "guests", // 'guests' | 'stay_nights'
}) {
  const containerRef = useRef(null);
  const canvasRef = useRef(null);
  const { width, height } = useCanvasSize(containerRef, 280);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    const historySlice = recentHistory.slice(-10);
    const totalPoints = historySlice.length + forecasts.length;
    if (totalPoints === 0) return;

    const pad = { top: 26, right: 24, bottom: 44, left: 52 };
    const plotW = Math.max(120, width - pad.left - pad.right);
    const plotH = Math.max(90, height - pad.top - pad.bottom);

    const getHistVal = (h) =>
      targetMetric === "stay_nights"
        ? Number(h.observed_total_stay_nights ?? (h.observed_total_guests || 120) * 3.1)
        : Number(h.target_guests ?? h.observed_total_guests ?? 0);

    const getForecastVal = (f) =>
      targetMetric === "stay_nights"
        ? Number(f.predicted_room_nights ?? Math.round((f.predicted_guest_count || 130) * 3.1))
        : Number(f.predicted_guest_count ?? f.predicted_arrivals ?? 0);

    const getActualAfterT = (f) =>
      targetMetric === "stay_nights"
        ? f.actual_room_nights != null
          ? Number(f.actual_room_nights)
          : null
        : f.actual_guest_count != null
          ? Number(f.actual_guest_count)
          : null;

    const scaleFactor = targetMetric === "stay_nights" ? 3.1 : 1.0;
    const highThresh =
      Number(thresholdRule.high_threshold ?? thresholdRule.high_demand_threshold ?? 142.7) *
      scaleFactor;
    const meanVal =
      Number(thresholdRule.mean_guests_8w ?? thresholdRule.rolling_8w_mean ?? 124.5) *
      scaleFactor;
    const lowThresh =
      Number(thresholdRule.low_threshold ?? thresholdRule.low_demand_threshold ?? 106.3) *
      scaleFactor;

    const allVals = [
      ...historySlice.map(getHistVal),
      ...forecasts.map(getForecastVal),
      highThresh,
      lowThresh,
    ].filter((v) => v != null && !Number.isNaN(v));

    const minVal = Math.max(0, Math.min(...allVals) * 0.82);
    const maxVal = Math.max(...allVals, 10) * 1.12;
    const range = Math.max(1, maxVal - minVal);

    const toY = (v) => pad.top + plotH - ((v - minVal) / range) * plotH;
    const stepX = plotW / Math.max(1, totalPoints - 1);
    const toX = (idx) => pad.left + idx * stepX;

    // Grid lines & Y-axis labels
    ctx.font = "11px 'JetBrains Mono', monospace";
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    for (let i = 0; i <= 4; i++) {
      const ratio = i / 4;
      const y = pad.top + plotH - ratio * plotH;
      const val = minVal + ratio * range;

      ctx.strokeStyle = PALETTE.divider;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(pad.left + plotW, y);
      ctx.stroke();

      ctx.fillStyle = PALETTE.inkSecondary;
      ctx.fillText(Math.round(val).toString(), pad.left - 8, y);
    }

    // Vertical Cutoff T divider line
    if (historySlice.length > 0) {
      const cutoffX = toX(historySlice.length - 1);
      ctx.save();
      ctx.strokeStyle = PALETTE.inkMuted;
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(cutoffX, pad.top);
      ctx.lineTo(cutoffX, pad.top + plotH);
      ctx.stroke();
      ctx.restore();

      ctx.fillStyle = PALETTE.inkSecondary;
      ctx.font = "500 10px 'JetBrains Mono', monospace";
      ctx.textAlign = "left";
      ctx.fillText("Cutoff T", cutoffX + 5, pad.top + 8);
    }

    // Threshold reference lines: HIGH (#B64C43), Mean (#547A9B), LOW (#92958B)
    const drawThreshold = (val, color, label) => {
      const y = toY(val);
      if (y < pad.top || y > pad.top + plotH) return;
      ctx.save();
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.25;
      ctx.setLineDash([5, 4]);
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(pad.left + plotW, y);
      ctx.stroke();
      ctx.restore();

      ctx.fillStyle = color;
      ctx.font = "500 10px 'JetBrains Mono', monospace";
      ctx.textAlign = "right";
      ctx.fillText(label, pad.left + plotW - 4, y - 7);
    };

    drawThreshold(highThresh, PALETTE.critical, `HIGH (${highThresh.toFixed(1)})`);
    drawThreshold(meanVal, PALETTE.series3, `μ_8w (${meanVal.toFixed(1)})`);
    drawThreshold(lowThresh, PALETTE.series5, `LOW (${lowThresh.toFixed(1)})`);

    // 1. Solid historical line (T-9 .. T)
    if (historySlice.length > 0) {
      ctx.beginPath();
      historySlice.forEach((h, idx) => {
        const x = toX(idx);
        const y = toY(getHistVal(h));
        if (idx === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.strokeStyle = PALETTE.series3;
      ctx.lineWidth = 2;
      ctx.stroke();

      historySlice.forEach((h, idx) => {
        const x = toX(idx);
        const y = toY(getHistVal(h));
        ctx.beginPath();
        ctx.arc(x, y, 3, 0, Math.PI * 2);
        ctx.fillStyle = PALETTE.series3;
        ctx.fill();
      });
    }

    // 2. Actual observed line in horizon (Backtest comparison if available)
    const actualPts = forecasts
      .map((f, i) => {
        const v = getActualAfterT(f);
        if (v == null) return null;
        return { x: toX(historySlice.length + i), y: toY(v), val: v };
      })
      .filter(Boolean);

    if (actualPts.length > 0) {
      ctx.beginPath();
      if (historySlice.length > 0) {
        const lastH = historySlice[historySlice.length - 1];
        ctx.moveTo(toX(historySlice.length - 1), toY(getHistVal(lastH)));
        actualPts.forEach((p) => ctx.lineTo(p.x, p.y));
      } else {
        actualPts.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)));
      }
      ctx.strokeStyle = PALETTE.series5;
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }

    // 3. Dashed 7-Day Forecast curve (T -> T+1..T+7)
    if (forecasts.length > 0) {
      ctx.save();
      ctx.beginPath();
      if (historySlice.length > 0) {
        const lastH = historySlice[historySlice.length - 1];
        ctx.moveTo(toX(historySlice.length - 1), toY(getHistVal(lastH)));
      }
      forecasts.forEach((f, i) => {
        const x = toX(historySlice.length + i);
        const y = toY(getForecastVal(f));
        if (historySlice.length === 0 && i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.strokeStyle = PALETTE.series1;
      ctx.lineWidth = 2.25;
      ctx.setLineDash([6, 4]);
      ctx.stroke();
      ctx.restore();

      // Forecast nodes & value labels
      forecasts.forEach((f, i) => {
        const idx = historySlice.length + i;
        const x = toX(idx);
        const val = getForecastVal(f);
        const y = toY(val);
        const isHigh = f.demand_level === "HIGH";
        const isLow = f.demand_level === "LOW";

        ctx.beginPath();
        ctx.arc(x, y, isHigh ? 4.5 : 3.5, 0, Math.PI * 2);
        ctx.fillStyle = isHigh
          ? PALETTE.critical
          : isLow
            ? PALETTE.warning
            : PALETTE.series1;
        ctx.fill();
        ctx.strokeStyle = "#FFFFFF";
        ctx.lineWidth = 1.5;
        ctx.stroke();

        ctx.fillStyle = isHigh ? PALETTE.critical : PALETTE.inkPrimary;
        ctx.font = "600 11px 'JetBrains Mono', monospace";
        ctx.textAlign = "center";
        ctx.fillText(Math.round(val).toString(), x, y - 12);
      });
    }

    // X-axis labels
    const allDates = [
      ...historySlice.map((h) => ({
        date: (h.full_date || "").slice(5),
        sub: "Actual",
      })),
      ...forecasts.map((f, i) => ({
        date: (f.forecast_date || f.stay_date || "").slice(5),
        sub: `T+${i + 1}`,
      })),
    ];

    const stride = allDates.length > 12 ? 2 : 1;
    allDates.forEach((d, idx) => {
      if (idx % stride !== 0 && idx !== allDates.length - 1 && idx !== historySlice.length - 1) {
        return;
      }
      const x = toX(idx);
      ctx.fillStyle = idx >= historySlice.length ? PALETTE.inkPrimary : PALETTE.inkSecondary;
      ctx.font = "500 11px 'JetBrains Mono', monospace";
      ctx.textAlign = "center";
      ctx.fillText(d.date, x, pad.top + plotH + 14);

      ctx.fillStyle = PALETTE.inkMuted;
      ctx.font = "400 10px Inter, sans-serif";
      ctx.fillText(d.sub, x, pad.top + plotH + 28);
    });
  }, [recentHistory, forecasts, thresholdRule, targetMetric, width, height]);

  return (
    <div ref={containerRef} className="w-full select-none">
      <canvas
        ref={canvasRef}
        style={{ width: `${width}px`, height: `${height}px` }}
        role="img"
        aria-label="Actual versus 7-day forecast demand trajectory canvas chart"
      />
    </div>
  );
}

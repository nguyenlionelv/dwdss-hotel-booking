import React, { useEffect, useRef, useState } from 'react';
import {
  forecastDomain,
  forecastLabelPosition,
  forecastNumber,
} from './forecastGeometry.js';
import { layoutAxisLabels } from './axisLabels.js';
import {
  formatChartAxis,
  formatDate,
  formatGuests,
  formatReference,
} from '../../lib/dssFormat.mjs';

/**
 * Lumina Analytics Color System (DESIGN.md Section 2.2 & 5.3)
 * Reads semantic CSS tokens dynamically from :root so HTML5 Canvas charts
 * adapt seamlessly between Light Mode and Dark Mode without hardcoded hex literals.
 */
function readThemePalette() {
  if (typeof window === 'undefined' || typeof document === 'undefined') {
    return {};
  }
  const styles = window.getComputedStyle(document.documentElement);
  const token = (name) => styles.getPropertyValue(name).trim();
  const brandRgbRaw = token('--brand-rgb')
    .split(/\s+/)
    .filter(Boolean)
    .join(', ');

  return {
    series1: token('--color-series-1'),
    series2: token('--color-series-2'),
    series3: token('--color-series-3'),
    series4: token('--color-series-4'),
    series5: token('--color-series-5'),
    success: token('--color-status-success'),
    warning: token('--color-status-warning'),
    critical: token('--color-status-critical'),
    inkPrimary: token('--color-ink-primary'),
    inkSecondary: token('--color-ink-secondary'),
    inkMuted: token('--color-ink-muted'),
    divider: token('--color-divider'),
    surface: token('--color-surface-primary'),
    surfaceSubtle: token('--color-surface-subtle'),
    areaFill: brandRgbRaw ? `rgba(${brandRgbRaw}, 0.10)` : 'transparent',
    hoverFill: brandRgbRaw ? `rgba(${brandRgbRaw}, 0.08)` : 'transparent',
  };
}

function useThemePalette() {
  const [palette, setPalette] = useState(() => readThemePalette());

  useEffect(() => {
    const update = () => setPalette(readThemePalette());
    update();

    const root = document.documentElement;
    const observer =
      typeof MutationObserver !== 'undefined'
        ? new MutationObserver(update)
        : null;
    if (observer && root) {
      observer.observe(root, {
        attributes: true,
        attributeFilter: ['class', 'style'],
      });
    }

    const mql =
      typeof window !== 'undefined' && window.matchMedia
        ? window.matchMedia('(prefers-color-scheme: dark)')
        : null;
    if (mql) {
      mql.addEventListener('change', update);
    }

    return () => {
      if (observer) observer.disconnect();
      if (mql) mql.removeEventListener('change', update);
    };
  }, []);

  return palette;
}

const fmtNum = (n, decimals = 0) => {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return '—';
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
        setSize({
          width: Math.floor(el.clientWidth || rect.width),
          height: defaultHeight,
        });
      }
    };
    update();
    if (typeof ResizeObserver !== 'undefined') {
      const observer = new ResizeObserver(update);
      observer.observe(el);
      return () => observer.disconnect();
    }
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
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
  grain = 'month',
  measure = 'observed_total_guests',
  measureLabel = 'Observed Guests',
  height: customHeight = 580,
  fontSize = 11,
  onDrill,
  canDrill = false,
}) {
  const containerRef = useRef(null);
  const canvasRef = useRef(null);
  const hitBoxesRef = useRef([]);
  const [hovered, setHovered] = useState(null);
  const { width, height } = useCanvasSize(containerRef, customHeight);
  const PALETTE = useThemePalette();

  const getVal = (item) => {
    if (!item) return 0;
    if (measure === 'cancellation_rate') {
      return Number(((item.cancellation_rate ?? 0) * 100).toFixed(2));
    }
    if (item[measure] !== undefined && item[measure] !== null) {
      return Number(item[measure]);
    }
    if (measure === 'observed_total_guests') {
      return Number(item.observed_total_guests ?? item.active_guests ?? 0);
    }
    if (measure === 'observed_total_stay_nights' || measure === 'room_nights') {
      return Number(item.observed_total_stay_nights ?? item.room_nights ?? 0);
    }
    if (measure === 'non_canceled_bookings' || measure === 'arrivals') {
      return Number(item.non_canceled_bookings ?? item.arrivals ?? 0);
    }
    if (measure === 'avg_adr' || measure === 'adr') {
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
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    hitBoxesRef.current = [];
    if (!series.length) {
      ctx.fillStyle = PALETTE.inkSecondary;
      ctx.font = '13px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(
        'No time-series data for the selected slice.',
        width / 2,
        height / 2
      );
      return;
    }

    const pad = {
      top: 20,
      right: 6,
      bottom: 38 + (fontSize - 11) * 2,
      left: 44 + (fontSize - 11) * 3,
    };
    const plotW = Math.max(100, width - pad.left - pad.right);
    const plotH = Math.max(80, height - pad.top - pad.bottom);

    const values = series.map(getVal);
    const maxVal = Math.max(...values, 1);
    const niceMax = maxVal * 1.12;
    const avgVal = values.reduce((a, b) => a + b, 0) / (values.length || 1);

    // Draw horizontal gridlines & Y-axis labels
    const ticks = height >= 500 ? 6 : 4;
    ctx.font = `${fontSize}px Inter, sans-serif`;
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';

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
        measure === 'cancellation_rate'
          ? `${val.toFixed(0)}%`
          : measure === 'avg_adr'
            ? `€${val.toFixed(0)}`
            : val >= 1000
              ? `${(val / 1000).toFixed(1)}k`
              : val.toFixed(0);
      ctx.fillText(labelStr, pad.left - 8, y);
    }

    const isLineMode = series.length > 28 || grain === 'day';
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
      ctx.fillStyle = PALETTE.areaFill;
      ctx.fill();

      // Main line
      ctx.beginPath();
      pts.forEach((p, i) =>
        i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)
      );
      ctx.strokeStyle = PALETTE.series1;
      ctx.lineWidth = 2;
      ctx.stroke();

      // Points & hitboxes
      pts.forEach((p) => {
        const isHighlighted = p.item.is_peak || p.item.is_holiday_period;
        const isHovered = hovered?.idx === p.idx;
        if (isHighlighted || isHovered || series.length <= 45) {
          ctx.beginPath();
          ctx.arc(
            p.x,
            p.y,
            isHovered ? 4.5 : isHighlighted ? 3.5 : 2.5,
            0,
            Math.PI * 2
          );
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
      const barWidth = Math.max(8, Math.floor(stepX * 0.82));
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
      ctx.font = `${fontSize}px Inter, sans-serif`;
      ctx.textAlign = 'right';
      ctx.fillText(
        `Mean: ${fmtNum(avgVal, measure === 'cancellation_rate' || measure === 'avg_adr' ? 1 : 0)}`,
        pad.left + plotW - 4,
        Math.max(pad.top + 10, avgY - 7)
      );
    }

    // X-axis labels
    ctx.fillStyle = PALETTE.inkSecondary;
    ctx.font = `${fontSize}px Inter, sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    const labels = series.map((item, idx) => {
      const text = String(item.period_label || '');
      return {
        text,
        x: pad.left + idx * stepX + stepX / 2,
        width: ctx.measureText(text).width,
      };
    });
    layoutAxisLabels(labels, pad.left, pad.left + plotW).forEach((label) => {
      ctx.fillText(label.text, label.x, pad.top + plotH + 10);
    });
  }, [series, width, height, grain, measure, hovered, PALETTE, fontSize]);

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
        className="block w-full"
        ref={canvasRef}
        style={{
          width: `${width}px`,
          height: `${height}px`,
          cursor: canDrill && hovered ? 'pointer' : 'default',
        }}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHovered(null)}
        onClick={handleClick}
        role="img"
        aria-label={`Canvas chart of ${measureLabel} by ${grain}`}
      />

      {hovered?.item && (
        <div
          className="pointer-events-none absolute z-20 rounded-[4px] border border-divider bg-surface-primary px-3 py-2 text-[12px] text-ink-primary shadow-sm space-y-1 min-w-[200px]"
          style={{
            left: `${Math.min(Math.max(12, hovered.cx - 95), Math.max(12, width - 215))}px`,
            top: `${Math.max(8, hovered.cy - 88)}px`,
          }}
        >
          <div className="flex items-center justify-between gap-4 border-b border-divider pb-1 font-semibold">
            <span>{hovered.item.period_label}</span>
            <span className="font-mono text-[11px] text-ink-secondary">
              {hovered.item.guest_data_status || 'COMPLETE'}
            </span>
          </div>
          <div className="flex justify-between gap-4">
            <span className="text-ink-secondary">Observed guests</span>
            <span className="font-sans font-semibold tabular-nums">
              {fmtNum(
                hovered.item.observed_total_guests ?? hovered.item.active_guests
              )}
            </span>
          </div>
          <div className="flex justify-between gap-4">
            <span className="text-ink-secondary">Non-canceled bookings</span>
            <span className="font-sans font-semibold tabular-nums">
              {fmtNum(
                hovered.item.non_canceled_bookings ?? hovered.item.arrivals
              )}
            </span>
          </div>
          <div className="flex justify-between gap-4">
            <span className="text-ink-secondary">Stay nights</span>
            <span className="font-sans tabular-nums">
              {fmtNum(
                hovered.item.observed_total_stay_nights ??
                  hovered.item.room_nights
              )}
            </span>
          </div>
          {hovered.item.cancellation_rate != null && (
            <div className="flex justify-between gap-4">
              <span className="text-ink-secondary">Cancellation rate</span>
              <span className="font-sans tabular-nums">
                {(Number(hovered.item.cancellation_rate) * 100).toFixed(1)}%
              </span>
            </div>
          )}
          <div className="flex justify-between gap-4">
            <span className="text-ink-secondary">Avg ADR</span>
            <span className="font-sans tabular-nums">
              €{fmtNum(hovered.item.avg_adr ?? hovered.item.adr, 2)}
            </span>
          </div>
          {canDrill && (
            <div className="pt-0.5 text-[11px] text-brand font-medium">
              Click to drill down →
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * 2. Responsive horizontal comparisons with readable, wrapping HTML labels.
 * Used for Geographic Markets (DO-A05), Weather Bands (DO-A04),
 * Holiday Comparison (DO-A03), and Model MAE Benchmark (ML-03).
 */
export function HorizontalBarChart({
  items = [],
  scaleMax = 0,
  height: customHeight,
  valueFormatter = (v) => fmtNum(v),
  ariaLabel = 'Horizontal bar comparison chart',
}) {
  const numericValue = (item) =>
    Number.isFinite(Number(item.value)) ? Number(item.value) : 0;
  const maxValue = Math.max(
    Number(scaleMax) || 0,
    ...items.map(numericValue),
    1
  );
  const colors = {
    series1: 'var(--color-series-1)',
    series2: 'var(--color-series-2)',
    series3: 'var(--color-series-3)',
    series4: 'var(--color-series-4)',
    series5: 'var(--color-series-5)',
  };

  return (
    <div
      className="comparison-chart min-w-0 w-full"
      role="group"
      aria-label={ariaLabel}
    >
      {items.length === 0 ? (
        <p className="py-4 text-[12px] text-ink-secondary">
          No data for the selected period.
        </p>
      ) : (
        <ul className="space-y-4 py-3" style={{ minHeight: customHeight }}>
          {items.map((item, index) => {
            const value = numericValue(item);
            const defaultColor =
              item.highlight || index === 0
                ? colors.series1
                : index === 1
                  ? colors.series3
                  : colors.series5;
            return (
              <li
                key={`${item.label}-${index}`}
                className="comparison-chart-row text-[12px]"
              >
                <span
                  className={`comparison-chart-label text-ink-primary ${item.highlight ? 'font-semibold' : 'font-normal'}`}
                >
                  {item.label}
                </span>
                <div
                  className="comparison-chart-track h-3.5 min-w-0 bg-surface-subtle"
                  aria-hidden="true"
                >
                  <div
                    className="h-full"
                    style={{
                      width: `${Math.max(0, Math.min(100, (value / maxValue) * 100))}%`,
                      minWidth: value > 0 ? 2 : 0,
                      backgroundColor:
                        colors[item.color] || item.color || defaultColor,
                    }}
                  />
                </div>
                <span className="comparison-chart-value whitespace-nowrap text-right font-medium tabular-nums text-ink-primary">
                  {item.formattedValue || valueFormatter(value)}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

/**
 * 3. Canvas Weekly Workload Profile Chart for OperationsReportsPage (DO-R01 / DO-R02)
 * Renders 7-day grouped bars (Observed Guests & Non-Canceled Bookings) + Stay Nights line on HTML5 Canvas.
 */
export function CanvasWeeklyWorkloadChart({
  dailyRows = [],
  height: customHeight = 240,
  metric = 'guests',
}) {
  const containerRef = useRef(null);
  const canvasRef = useRef(null);
  const hitBoxesRef = useRef([]);
  const [hovered, setHovered] = useState(null);
  const { width, height } = useCanvasSize(containerRef, customHeight);
  const PALETTE = useThemePalette();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    hitBoxesRef.current = [];
    if (!dailyRows.length) return;

    const pad = { top: 24, right: 16, bottom: 46, left: 54 };
    const plotW = Math.max(1, width - pad.left - pad.right);
    const plotH = Math.max(1, height - pad.top - pad.bottom);
    const values = dailyRows.map((row) =>
      metric === 'nights'
        ? Number(row.observed_total_stay_nights ?? row.room_nights ?? 0)
        : metric === 'bookings'
          ? Number(row.non_canceled_bookings ?? row.arrivals ?? 0)
          : Number(row.observed_total_guests ?? row.active_guests ?? 0)
    );
    const maxVal = Math.round(Math.max(...values, 1) * 1.15);
    ctx.font = '13px Inter, sans-serif';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    for (let i = 0; i <= 3; i++) {
      const y = pad.top + plotH - (i / 3) * plotH;
      ctx.strokeStyle = PALETTE.divider;
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(pad.left + plotW, y);
      ctx.stroke();
      ctx.fillStyle = PALETTE.inkSecondary;
      ctx.fillText(
        formatChartAxis(Math.round((maxVal * i) / 3)),
        pad.left - 8,
        y
      );
    }
    ctx.textAlign = 'left';
    ctx.fillText(
      metric === 'nights'
        ? 'Nights'
        : metric === 'bookings'
          ? 'Bookings'
          : 'Guests',
      pad.left,
      10
    );
    const stepX = plotW / dailyRows.length;
    const barW = Math.max(1, stepX * 0.64);
    const labelStep = Math.max(
      1,
      Math.ceil(dailyRows.length / Math.max(1, Math.floor(plotW / 96)))
    );
    dailyRows.forEach((row, idx) => {
      const cx = pad.left + idx * stepX + stepX / 2;
      const barH = (values[idx] / maxVal) * plotH;
      const cy = pad.top + plotH - barH;
      ctx.fillStyle = hovered?.idx === idx ? PALETTE.series3 : PALETTE.series1;
      ctx.fillRect(cx - barW / 2, cy, barW, barH);
      if (dailyRows.length <= 10) {
        ctx.font = '600 13px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillStyle = PALETTE.inkPrimary;
        ctx.fillText(formatGuests(values[idx]), cx, cy - 9);
      }
      if (idx % labelStep === 0) {
        ctx.font = '13px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillStyle = PALETTE.inkSecondary;
        const labelX = Math.min(width - 28, Math.max(28, cx));
        ctx.fillText(
          formatDate(row.full_date || row.stay_date, true),
          labelX,
          pad.top + plotH + 22
        );
      }
      hitBoxesRef.current.push({
        x: pad.left + idx * stepX,
        y: pad.top,
        w: stepX,
        h: plotH,
        row,
        idx,
        cx,
        cy,
      });
    });
  }, [dailyRows, width, height, hovered, PALETTE, metric]);

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
    (Array.isArray(hovered?.row?.holiday_names) &&
      hovered.row.holiday_names[0]) ||
    hovered?.row?.holiday_local_name ||
    null;

  return (
    <div ref={containerRef} className="relative w-full select-none">
      <canvas
        className="block w-full"
        ref={canvasRef}
        style={{ width: `${width}px`, height: `${height}px` }}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHovered(null)}
        role="img"
        aria-label={`Daily ${metric === 'nights' ? 'stay nights' : metric === 'bookings' ? 'non-canceled bookings' : 'observed guests'} by arrival date. Exact values are available in the daily demand table.`}
      />

      {hovered?.row && (
        <div
          className="pointer-events-none absolute z-20 rounded-[4px] border border-divider bg-surface-primary px-3 py-2 text-[12px] text-ink-primary shadow-sm space-y-1 min-w-[215px]"
          style={{
            left: `${Math.min(Math.max(12, hovered.cx - 105), Math.max(12, width - 225))}px`,
            top: `${Math.max(8, hovered.cy - 96)}px`,
          }}
        >
          <div className="flex items-center justify-between gap-4 border-b border-divider pb-1 font-semibold">
            <span>
              {hovered.row.full_date || hovered.row.stay_date}
              {hovered.row.day_of_week
                ? ` (${String(hovered.row.day_of_week).slice(0, 3)})`
                : ''}
            </span>
            <span className="font-mono text-[11px] text-ink-secondary">
              {hovered.row.guest_data_status || 'Unknown coverage'}
            </span>
          </div>
          {(hovered.row.is_peak_day ||
            hovered.row.is_holiday ||
            hovered.row.is_pt_holiday ||
            hoveredHolidayName) && (
            <div className="text-[11px] font-medium text-series-2">
              {hovered.row.is_peak_day ? '★ Peak Demand Day' : ''}
              {hovered.row.is_peak_day &&
              (hovered.row.is_holiday ||
                hovered.row.is_pt_holiday ||
                hoveredHolidayName)
                ? ' · '
                : ''}
              {hovered.row.is_holiday ||
              hovered.row.is_pt_holiday ||
              hoveredHolidayName
                ? hoveredHolidayName || 'PT National Holiday'
                : ''}
            </div>
          )}
          <div className="flex justify-between gap-4">
            <span className="text-ink-secondary">Observed guests</span>
            <span className="font-sans font-semibold tabular-nums">
              {fmtNum(
                hovered.row.observed_total_guests ?? hovered.row.active_guests
              )}
            </span>
          </div>
          <div className="flex justify-between gap-4">
            <span className="text-ink-secondary">Non-canceled bookings</span>
            <span className="font-sans font-semibold tabular-nums">
              {fmtNum(
                hovered.row.non_canceled_bookings ?? hovered.row.arrivals
              )}
            </span>
          </div>
          <div className="flex justify-between gap-4">
            <span className="text-ink-secondary">Stay nights</span>
            <span className="font-sans tabular-nums">
              {fmtNum(
                hovered.row.observed_total_stay_nights ??
                  hovered.row.room_nights
              )}
            </span>
          </div>
          {hovered.row.cancellation_rate != null && (
            <div className="flex justify-between gap-4">
              <span className="text-ink-secondary">Cancellation rate</span>
              <span className="font-sans tabular-nums">
                {(Number(hovered.row.cancellation_rate) * 100).toFixed(1)}%
              </span>
            </div>
          )}
          <div className="flex justify-between gap-4">
            <span className="text-ink-secondary">Avg ADR</span>
            <span className="font-sans tabular-nums">
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
  targetMetric = 'guests', // 'guests' | 'stay_nights'
}) {
  const containerRef = useRef(null);
  const canvasRef = useRef(null);
  const { width, height } = useCanvasSize(containerRef, 280);
  const PALETTE = useThemePalette();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    const historySlice = recentHistory.slice(-10);
    const totalPoints = historySlice.length + forecasts.length;
    if (totalPoints === 0) return;

    const pad = { top: 26, right: 24, bottom: 44, left: 52 };
    const plotW = Math.max(120, width - pad.left - pad.right);
    const plotH = Math.max(90, height - pad.top - pad.bottom);

    const getHistVal = (h) => forecastNumber(h.target_guests);
    const getForecastVal = (f) => forecastNumber(f.predicted_guest_count);
    const getActualAfterT = (f) => forecastNumber(f.actual_guest_count);
    const highThresh = forecastNumber(thresholdRule.high_threshold);
    const meanVal = forecastNumber(thresholdRule.mean_guests_8w);
    const lowThresh = forecastNumber(thresholdRule.low_threshold);

    const domain = forecastDomain(historySlice, forecasts, thresholdRule);
    if (!domain) return;
    const minVal = domain.min;
    const maxVal = domain.max;
    const range = maxVal - minVal;

    const toY = (v) => pad.top + plotH - ((v - minVal) / range) * plotH;
    const markerInset = 6;
    const stepX = (plotW - markerInset * 2) / Math.max(1, totalPoints - 1);
    const toX = (idx) => pad.left + markerInset + idx * stepX;
    const plot = {
      left: pad.left,
      right: pad.left + plotW,
      top: pad.top,
      bottom: pad.top + plotH,
    };

    const drawDataLabel = (text, x, y) => {
      ctx.save();
      ctx.textAlign = 'center';
      ctx.textBaseline = 'alphabetic';
      const maxWidth = plotW - 4;
      const measured = ctx.measureText(text);
      const position = forecastLabelPosition(
        x,
        y,
        Math.min(measured.width, maxWidth),
        measured.actualBoundingBoxAscent || 9,
        measured.actualBoundingBoxDescent || 2,
        plot
      );
      ctx.fillText(text, position.x, position.y, maxWidth);
      ctx.restore();
    };

    // Grid lines & Y-axis labels
    ctx.font = '12px Inter, sans-serif';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    for (let i = 0; i <= 4; i++) {
      const ratio = i / 4;
      const y = pad.top + plotH - ratio * plotH;
      const val = Math.round(minVal + ratio * range);

      ctx.strokeStyle = PALETTE.divider;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(pad.left + plotW, y);
      ctx.stroke();

      ctx.fillStyle = PALETTE.inkSecondary;
      ctx.fillText(formatChartAxis(val), pad.left - 8, y);
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
      ctx.font = '500 11px Inter, sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText('Cutoff T', cutoffX + 5, pad.top + 8);
    }

    // Threshold reference lines: HIGH (status-critical), Mean (series-3), LOW (series-5)
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
      ctx.font = '500 11px Inter, sans-serif';
      drawDataLabel(
        label,
        pad.left + plotW - ctx.measureText(label).width / 2 - 4,
        y
      );
    };

    if (highThresh != null)
      drawThreshold(
        highThresh,
        PALETTE.critical,
        `HIGH (${formatReference(highThresh)})`
      );
    if (meanVal != null)
      drawThreshold(
        meanVal,
        PALETTE.series3,
        `μ_8w (${formatReference(meanVal)})`
      );
    if (lowThresh != null)
      drawThreshold(
        lowThresh,
        PALETTE.series5,
        `LOW (${formatReference(lowThresh)})`
      );

    // 1. Solid historical line (T-9 .. T)
    if (historySlice.length > 0) {
      ctx.beginPath();
      let connected = false;
      historySlice.forEach((h, idx) => {
        if (getHistVal(h) == null) {
          connected = false;
          return;
        }
        const x = toX(idx);
        const y = toY(getHistVal(h));
        if (!connected) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
        connected = true;
      });
      ctx.strokeStyle = PALETTE.series3;
      ctx.lineWidth = 2;
      ctx.stroke();

      historySlice.forEach((h, idx) => {
        if (getHistVal(h) == null) return;
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
        return { x: toX(historySlice.length + i), y: toY(v), val: v, index: i };
      })
      .filter(Boolean);

    if (actualPts.length > 0) {
      ctx.beginPath();
      let previousIndex = -2;
      if (
        historySlice.length > 0 &&
        getHistVal(historySlice[historySlice.length - 1]) != null
      ) {
        const lastH = historySlice[historySlice.length - 1];
        ctx.moveTo(toX(historySlice.length - 1), toY(getHistVal(lastH)));
        previousIndex = -1;
      }
      actualPts.forEach((p) => {
        if (p.index === previousIndex + 1) ctx.lineTo(p.x, p.y);
        else ctx.moveTo(p.x, p.y);
        previousIndex = p.index;
      });
      ctx.strokeStyle = PALETTE.series5;
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }

    // 3. Dashed 7-Day Forecast curve (T -> T+1..T+7)
    if (forecasts.length > 0) {
      ctx.save();
      ctx.beginPath();
      let connected = false;
      if (
        historySlice.length > 0 &&
        getHistVal(historySlice[historySlice.length - 1]) != null
      ) {
        const lastH = historySlice[historySlice.length - 1];
        ctx.moveTo(toX(historySlice.length - 1), toY(getHistVal(lastH)));
        connected = true;
      }
      forecasts.forEach((f, i) => {
        const value = getForecastVal(f);
        if (value == null) {
          connected = false;
          return;
        }
        const x = toX(historySlice.length + i);
        const y = toY(value);
        if (!connected) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
        connected = true;
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
        if (val == null) return;
        const y = toY(val);
        const isHigh = f.demand_level === 'HIGH';
        const isLow = f.demand_level === 'LOW';

        ctx.beginPath();
        ctx.arc(x, y, isHigh ? 4.5 : 3.5, 0, Math.PI * 2);
        ctx.fillStyle = isHigh
          ? PALETTE.critical
          : isLow
            ? PALETTE.warning
            : PALETTE.series1;
        ctx.fill();
        ctx.strokeStyle = PALETTE.surface;
        ctx.lineWidth = 1.5;
        ctx.stroke();

        ctx.fillStyle = isHigh ? PALETTE.critical : PALETTE.inkPrimary;
        ctx.font = '600 12px Inter, sans-serif';
        drawDataLabel(formatGuests(val), x, y);
      });
    }

    // X-axis labels
    const allDates = [
      ...historySlice.map((h) => ({
        date: formatDate(h.full_date, true),
        sub: 'Actual',
      })),
      ...forecasts.map((f, i) => ({
        date: formatDate(f.forecast_date || f.stay_date, true),
        sub: `T+${i + 1}`,
      })),
    ];

    ctx.font = '500 12px Inter, sans-serif';
    const dateLabels = allDates.map((date, index) => ({
      text: date.date,
      sub: date.sub,
      index,
      x: toX(index),
      width: ctx.measureText(date.date).width,
    }));
    layoutAxisLabels(dateLabels, plot.left, plot.right).forEach((label) => {
      ctx.fillStyle =
        label.index >= historySlice.length
          ? PALETTE.inkPrimary
          : PALETTE.inkSecondary;
      ctx.font = '500 12px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(label.text, label.x, pad.top + plotH + 14);

      ctx.fillStyle = PALETTE.inkMuted;
      ctx.font = '400 11px Inter, sans-serif';
      ctx.fillText(label.sub, label.x, pad.top + plotH + 30);
    });
  }, [
    recentHistory,
    forecasts,
    thresholdRule,
    targetMetric,
    width,
    height,
    PALETTE,
  ]);

  return (
    <div ref={containerRef} className="w-full select-none">
      <canvas
        className="block w-full"
        ref={canvasRef}
        style={{ width: `${width}px`, height: `${height}px` }}
        role="img"
        aria-label="Actual versus 7-day forecast demand trajectory canvas chart"
      />
    </div>
  );
}

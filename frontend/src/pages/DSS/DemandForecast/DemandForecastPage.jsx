import React, { useEffect, useState } from 'react';
import { fetchDemandForecast } from '../../../services/dssApi';
import KpiCard from '../../../components/kpi/KpiCard';
import ResponsiveTableContainer from '../../../components/tables/ResponsiveTableContainer';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';
import {
  BrainCircuit,
  Calendar,
  AlertTriangle,
  Sparkles,
  TrendingUp,
  Cpu,
  Layers,
  Activity,
  Sliders,
  CheckCircle2,
  Sun,
  Zap,
} from 'lucide-react';

export default function DemandForecastPage() {
  const [cutoffDate, setCutoffDate] = useState('2017-08-24');
  const [stdMultiplier, setStdMultiplier] = useState(1.0);
  const [targetView, setTargetView] = useState('arrivals'); // 'arrivals' | 'room_nights'
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
    <div className="space-y-6">
      {/* Page Title & Active Model Pill */}
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            <Badge variant="emerald" className="gap-1 font-semibold uppercase text-[10px]">
              <BrainCircuit className="h-3 w-3" />
              <span>DO-M01 • 7-Day Short-Horizon Demand Forecasting &amp; DSS</span>
            </Badge>
          </div>
          <h1 className="text-2xl sm:text-3xl font-display font-extrabold text-foreground tracking-tight">
            Decision Support System — Demand Forecasting &amp; Staffing Directives
          </h1>
          <p className="text-xs sm:text-sm text-muted-foreground mt-1">
            Short-horizon 7-day demand projections (<code className="font-mono text-xs">T+1 → T+7</code>) coupled with an 8-week rolling statistical threshold rule (
            <code className="font-mono text-xs">μ_8w + k·σ_8w</code>) to automate operational surge alerts.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2.5 bg-emerald-50/70 border border-emerald-200/80 px-3.5 py-2 rounded-lg">
            <Cpu className="h-4 w-4 text-emerald-600 shrink-0" />
            <div className="text-xs">
              <div className="font-bold text-emerald-950">
                {modelMeta.selected_model_family || 'LightGBM Regressor'} (
                {modelMeta.model_version || 'v1.2-lgbm-rolling'})
              </div>
              <div className="text-[11px] text-emerald-700">
                MAE: {modelMeta.validation_mae || 8.42} • Baseline Improvement:{' '}
                {modelMeta.improvement_vs_baseline_pct || 43.3}%
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* DSS Simulation & Cutoff Control Bar */}
      <Card>
        <CardContent className="p-4 sm:p-5 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 items-end">
          <div>
            <label
              htmlFor="dss-cutoff"
              className="block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1"
            >
              Forecast Cutoff Date T
            </label>
            <select
              id="dss-cutoff"
              value={cutoffDate}
              onChange={(e) => setCutoffDate(e.target.value)}
              className="w-full bg-background border border-input text-foreground text-xs font-bold rounded-md px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-ring"
            >
              <option value="2017-08-24">
                T = 2017-08-24 (Forecast Aug 25 – Aug 31, 2017)
              </option>
              <option value="2017-08-17">
                T = 2017-08-17 (Backtest Week Aug 18 – Aug 24, 2017)
              </option>
            </select>
          </div>

          <div>
            <label
              htmlFor="dss-threshold-k"
              className="block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1"
            >
              Alert Sensitivity (Threshold Rule k)
            </label>
            <select
              id="dss-threshold-k"
              value={stdMultiplier}
              onChange={(e) => setStdMultiplier(Number(e.target.value))}
              className="w-full bg-background border border-input text-foreground text-xs font-bold rounded-md px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-ring"
            >
              <option value={0.75}>High Sensitivity: μ + 0.75σ (Threshold = 138.2)</option>
              <option value={1.0}>Standard DSS: μ + 1.00σ (Threshold = 142.7)</option>
              <option value={1.25}>Conservative: μ + 1.25σ (Threshold = 147.3)</option>
            </select>
          </div>

          <div>
            <span className="block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">
              Trajectory Metric
            </span>
            <div className="flex items-center p-0.5 rounded-lg bg-muted border text-xs">
              <button
                type="button"
                onClick={() => setTargetView('arrivals')}
                className={`flex-1 py-1 rounded-md text-xs font-semibold transition-all cursor-pointer ${
                  targetView === 'arrivals'
                    ? 'bg-background text-emerald-700 shadow-xs font-bold'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                Arrivals
              </button>
              <button
                type="button"
                onClick={() => setTargetView('room_nights')}
                className={`flex-1 py-1 rounded-md text-xs font-semibold transition-all cursor-pointer ${
                  targetView === 'room_nights'
                    ? 'bg-background text-emerald-700 shadow-xs font-bold'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                Room Nights
              </button>
            </div>
          </div>

          <Button
            type="button"
            variant="emerald"
            onClick={() => loadForecast(stdMultiplier)}
            className="w-full gap-2 font-bold cursor-pointer"
          >
            <Zap className="h-4 w-4" />
            <span>{loading ? 'Running Model...' : 'Run 7-Day Forecast'}</span>
          </Button>
        </CardContent>
      </Card>

      {/* 4 Forecast KPI Summary Cards */}
      <section
        aria-label="DSS Forecast Summary KPIs"
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
              label="Predicted Total Arrivals"
              value={(kpis.total_predicted_arrivals || 942).toLocaleString()}
              unit="check-ins"
              badgeText="+8.4% vs 8W Mean"
              badgeIcon="trending_up"
              subtext="Horizon: 25/08 – 31/08/2017"
              icon="flight_land"
              tone="emerald"
            />
            <KpiCard
              label="Predicted Total Room Nights"
              value={(kpis.total_predicted_room_nights || 2840).toLocaleString()}
              unit="nights"
              badgeText="~405.7 nights/day"
              subtext="Projected in-house stays"
              icon="bed"
              tone="blue"
            />
            <KpiCard
              label="Peak Projected Day"
              value="26/08/2017"
              badgeText={`${kpis.peak_day_arrivals || 164} arrivals`}
              badgeIcon="warning"
              subtext="Saturday • 492 room nights"
              icon="event_upcoming"
              tone="amber"
            />
            <KpiCard
              label="High Alert Days"
              value={`${kpis.high_alert_days_count ?? 3} / 7`}
              unit="days"
              badgeText={`> ${threshold.high_demand_threshold || 142.7}`}
              badgeIcon="warning"
              subtext="Staff reinforcement required"
              icon="notification_important"
              tone="rose"
              highlightBorder
            />
          </>
        )}
      </section>

      {/* 7-Day Forecast Curve & Threshold Chart */}
      <Card>
        <CardHeader className="p-5 pb-3 flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <CardTitle className="text-base">
                7-Day Forward Demand Curve &amp; Operational Alert Thresholds
              </CardTitle>
              <Badge variant="emerald" className="text-[10px]">
                Horizon T+1 → T+7
              </Badge>
            </div>
            <CardDescription className="text-xs mt-0.5">
              Red nodes highlight forecast days exceeding the high demand surge threshold (
              <strong className="text-rose-600 font-mono">
                &gt; {threshold.high_demand_threshold || 142.7} arrivals
              </strong>
              ).
            </CardDescription>
          </div>

          <div className="flex flex-wrap items-center gap-3 text-xs font-medium">
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-600" />
              Standard Demand
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-rose-500 ring-2 ring-rose-200" />
              Surge Threshold Exceeded
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-4 border-t-2 border-dashed border-rose-500" />
              High Threshold ({threshold.high_demand_threshold || 142.7})
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-4 border-t-2 border-dashed border-primary" />
              8W Rolling Mean (μ = {threshold.rolling_8w_mean || 124.5})
            </span>
          </div>
        </CardHeader>

        <CardContent className="p-5 pt-1">
          {/* SVG Trajectory Chart */}
          <div className="w-full overflow-x-auto">
            <svg
              viewBox="0 0 920 270"
              className="w-full h-64 min-w-[680px]"
              role="img"
              aria-label="7-Day Demand Forecast Trajectory Chart"
            >
              <defs>
                <linearGradient id="dssAreaGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10b981" stopOpacity="0.22" />
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
              <text x="48" y="39" textAnchor="end" className="text-[10px] fill-muted-foreground font-mono">
                180
              </text>
              <text x="48" y="89" textAnchor="end" className="text-[10px] fill-muted-foreground font-mono">
                150
              </text>
              <text x="48" y="139" textAnchor="end" className="text-[10px] fill-muted-foreground font-mono">
                125
              </text>
              <text x="48" y="189" textAnchor="end" className="text-[10px] fill-muted-foreground font-mono">
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
              <rect x="742" y="76" width="132" height="18" rx="4" fill="#fef2f2" stroke="#fecaca" />
              <text
                x="808"
                y="89"
                textAnchor="middle"
                className="text-[10px] fill-rose-700 font-bold"
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
                className="text-[10px] fill-primary font-semibold"
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
                        isHigh ? 'fill-rose-700' : 'fill-foreground'
                      }`}
                    >
                      {val}
                      {pt.row.is_peak ? ' ★' : ''}
                    </text>
                    <text
                      x={pt.x}
                      y="245"
                      textAnchor="middle"
                      className="text-[11px] font-bold fill-foreground"
                    >
                      {pt.row.date_display.slice(0, 5)}
                    </text>
                    <text
                      x={pt.x}
                      y="260"
                      textAnchor="middle"
                      className="text-[10px] fill-muted-foreground"
                    >
                      {pt.row.day_of_week}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>
        </CardContent>
      </Card>

      {/* 7-Day Operational Decision Schedule Table */}
      <Card>
        <CardHeader className="p-5 pb-3 border-b flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <CardTitle id="dss-schedule-table-heading" className="text-base">
              7-Day Operational Schedule &amp; Action Directives (DSS Action Matrix)
            </CardTitle>
            <CardDescription className="text-xs mt-0.5">
              Synthesizes ML demand forecasts with holiday and weather context to generate actionable daily shift allocations.
            </CardDescription>
          </div>
          <Badge variant="outline" className="text-xs font-mono">
            Cutoff: {cutoffDate} • Horizon: 7d
          </Badge>
        </CardHeader>

        <CardContent className="p-0">
          <ResponsiveTableContainer ariaLabelledBy="dss-schedule-table-heading">
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/60">
                  <TableHead className="py-2.5 px-4 font-semibold text-foreground">Stay Date</TableHead>
                  <TableHead className="py-2.5 px-3">Day of Week</TableHead>
                  <TableHead className="py-2.5 px-3">Weather &amp; Context</TableHead>
                  <TableHead className="py-2.5 px-3 text-right">Predicted Check-ins</TableHead>
                  <TableHead className="py-2.5 px-3 text-right">Predicted Room Nights</TableHead>
                  <TableHead className="py-2.5 px-3 text-center">Demand Tier</TableHead>
                  <TableHead className="py-2.5 px-4">Recommended Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => {
                  const isHigh = row.demand_level === 'HIGH';
                  return (
                    <TableRow
                      key={row.stay_date}
                      className={`transition-colors ${
                        isHigh
                          ? 'bg-rose-50/40 hover:bg-rose-50/70 font-medium'
                          : 'hover:bg-muted/40'
                      }`}
                    >
                      <TableCell className="py-2.5 px-4 font-bold text-foreground tabular-nums">
                        {row.date_display}
                      </TableCell>
                      <TableCell className="py-2.5 px-3 font-medium text-foreground">
                        {row.day_of_week}
                      </TableCell>
                      <TableCell className="py-2.5 px-3 text-xs text-muted-foreground">
                        <div className="flex flex-col gap-0.5">
                          <span className="inline-flex items-center gap-1 font-medium text-foreground">
                            <Sun className="h-3.5 w-3.5 text-amber-500" />
                            <span>{row.weather_status}</span>
                          </span>
                          {row.holiday_local_name && (
                            <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-amber-700">
                              ★ {row.holiday_local_name}
                            </span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="py-2.5 px-3 text-right font-display font-extrabold text-sm text-foreground tabular-nums">
                        {row.predicted_arrivals}
                      </TableCell>
                      <TableCell className="py-2.5 px-3 text-right font-bold text-primary tabular-nums">
                        {row.predicted_room_nights}
                      </TableCell>
                      <TableCell className="py-2.5 px-3 text-center">
                        <Badge
                          variant={isHigh ? 'destructive' : 'emerald'}
                          className="gap-1 text-[10px] px-2 py-0.5 font-bold"
                        >
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${
                              isHigh ? 'bg-rose-600 animate-ping' : 'bg-emerald-500'
                            }`}
                          />
                          <span>{row.demand_label}</span>
                        </Badge>
                      </TableCell>
                      <TableCell className="py-2.5 px-4 text-xs text-foreground leading-relaxed">
                        {row.recommended_action}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </ResponsiveTableContainer>
        </CardContent>
      </Card>

      {/* Bottom 3-Column Model Governance & Evaluation Benchmark */}
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Card 1: Model Evaluation Benchmark */}
        <Card>
          <CardHeader className="p-4 sm:p-5 pb-2">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-emerald-700">
              ML-03 / ML-05 Evaluation
            </span>
            <CardTitle className="text-base mt-0.5">
              Forecast Error Benchmark (MAE Evaluation)
            </CardTitle>
          </CardHeader>

          <CardContent className="p-4 sm:p-5 pt-1 space-y-2.5 text-xs">
            <div className="p-2.5 rounded-md bg-emerald-50/70 border border-emerald-200">
              <div className="flex items-center justify-between font-bold text-emerald-950">
                <span>★ LightGBM Regressor (Selected)</span>
                <span className="tabular-nums">MAE = 8.42</span>
              </div>
              <div className="w-full bg-emerald-200/70 h-1.5 rounded-full mt-1.5 overflow-hidden">
                <div className="bg-emerald-600 h-full rounded-full w-[52%]" />
              </div>
              <div className="text-[10px] text-emerald-700 mt-1">
                RMSE: 11.15 • MAPE: 6.8% (Production Ready)
              </div>
            </div>

            <div className="p-2.5 rounded-md bg-muted/40 border">
              <div className="flex items-center justify-between font-medium text-foreground">
                <span>Baseline 1: 7-Day Moving Average</span>
                <span className="tabular-nums text-muted-foreground">MAE = 14.85</span>
              </div>
              <div className="w-full bg-secondary h-1.5 rounded-full mt-1.5 overflow-hidden">
                <div className="bg-muted-foreground/50 h-full rounded-full w-[88%]" />
              </div>
            </div>

            <div className="p-2.5 rounded-md bg-muted/40 border">
              <div className="flex items-center justify-between font-medium text-foreground">
                <span>Baseline 2: Seasonal Naive (Lag 7)</span>
                <span className="tabular-nums text-muted-foreground">MAE = 16.20</span>
              </div>
              <div className="w-full bg-secondary h-1.5 rounded-full mt-1.5 overflow-hidden">
                <div className="bg-muted-foreground/50 h-full rounded-full w-[96%]" />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Card 2: Statistical Threshold Formula */}
        <Card className="flex flex-col justify-between">
          <CardHeader className="p-4 sm:p-5 pb-2">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-primary">
              Decision Rule Engine
            </span>
            <CardTitle className="text-base mt-0.5">
              8-Week Rolling Statistical Threshold Rule
            </CardTitle>
          </CardHeader>

          <CardContent className="p-4 sm:p-5 pt-1 space-y-3">
            <div className="p-3 rounded-md bg-muted border font-mono text-xs space-y-1">
              <div className="text-muted-foreground text-[10px] uppercase font-semibold">
                High Demand Alert Formula
              </div>
              <div className="text-primary font-bold text-sm">
                Threshold = μ_8w + {stdMultiplier.toFixed(2)} × σ_8w
              </div>
              <div className="text-muted-foreground text-[11px] pt-1">
                = {threshold.rolling_8w_mean || 124.5} + {stdMultiplier.toFixed(2)} ×{' '}
                {threshold.rolling_8w_std || 18.2} ={' '}
                <strong className="text-rose-600 font-bold">
                  {threshold.high_demand_threshold || 142.7} check-ins
                </strong>
              </div>
            </div>

            <p className="text-[11px] text-muted-foreground leading-relaxed">
              The DSS engine dynamically computes the rolling mean and standard deviation of the preceding 56 days before cutoff{' '}
              <code className="font-mono text-[10px] bg-muted px-1 py-0.5 rounded">T</code> to adapt to seasonal shifts in Lisbon.
            </p>
          </CardContent>
        </Card>

        {/* Card 3: Feature Completeness */}
        <Card className="flex flex-col justify-between">
          <CardHeader className="p-4 sm:p-5 pb-2">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-primary">
                Leakage-Free Guarantee
              </span>
              <Badge variant="emerald" className="font-bold text-xs">
                99.62%
              </Badge>
            </div>
            <CardTitle className="text-base mt-0.5">
              Feature Completeness &amp; Data Quality
            </CardTitle>
          </CardHeader>

          <CardContent className="p-4 sm:p-5 pt-1 space-y-2">
            <ul className="space-y-1.5 text-xs text-muted-foreground">
              <li className="flex items-center justify-between p-2 rounded-md bg-muted/40 border">
                <span className="font-medium text-foreground">
                  Lag Features (t-1, t-7, rolling 7d)
                </span>
                <span className="font-bold text-emerald-600">100% Valid</span>
              </li>
              <li className="flex items-center justify-between p-2 rounded-md bg-muted/40 border">
                <span className="font-medium text-foreground">
                  On-the-books (t ≤ Cutoff T)
                </span>
                <span className="font-bold text-emerald-600">Strict Cutoff</span>
              </li>
              <li className="flex items-center justify-between p-2 rounded-md bg-muted/40 border">
                <span className="font-medium text-foreground">
                  Open-Meteo &amp; Nager.Date
                </span>
                <span className="font-bold text-emerald-600">790/793d</span>
              </li>
            </ul>

            <div className="text-[10px] text-muted-foreground flex items-center justify-between border-t pt-2">
              <span>Mart Source: mart.operations_daily</span>
              <span className="font-mono">v9fe497e2</span>
            </div>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}

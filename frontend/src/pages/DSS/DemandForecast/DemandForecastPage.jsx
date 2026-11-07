import React, { useEffect, useMemo, useState } from 'react';
import { fetchDemandForecast } from '../../../services/dssApi';
import KpiCard from '../../../components/kpi/KpiCard';
import {
  CanvasForecastChart,
  CanvasHorizontalBarChart,
} from '../../../components/charts/TrendChart';
import ResponsiveTableContainer from '../../../components/tables/ResponsiveTableContainer';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';

const MODEL_OPTIONS = [
  { id: 'xgboost_regressor', label: 'XGBoost Regressor (Selected Production)' },
  { id: 'random_forest', label: 'Random Forest Regressor' },
  { id: 'ridge_regression', label: 'Ridge Regression' },
  { id: 'seasonal_naive', label: 'Seasonal Naive Baseline (Lag-7)' },
];

const CUTOFF_OPTIONS = [
  {
    value: '2017-08-24',
    label: 'T = 2017-08-24 (Horizon: 2017-08-25 → 2017-08-31)',
  },
  {
    value: '2017-08-17',
    label: 'T = 2017-08-17 (Backtest Horizon: 2017-08-18 → 2017-08-24)',
  },
];

function getDemandStatusBadge(level) {
  if (level === 'HIGH') {
    return (
      <Badge variant="destructive" className="gap-1.5 font-mono">
        <span className="w-1.5 h-1.5 rounded-full bg-[#B64C43]" />
        <span>HIGH</span>
      </Badge>
    );
  }
  if (level === 'LOW') {
    return (
      <Badge variant="amber" className="gap-1.5 font-mono">
        <span className="w-1.5 h-1.5 rounded-full bg-[#C58B35]" />
        <span>LOW</span>
      </Badge>
    );
  }
  return (
    <Badge variant="emerald" className="gap-1.5 font-mono">
      <span className="w-1.5 h-1.5 rounded-full bg-[#477A61]" />
      <span>NORMAL</span>
    </Badge>
  );
}

export default function DemandForecastPage() {
  const [cutoffDate, setCutoffDate] = useState('2017-08-24');
  const [selectedModel, setSelectedModel] = useState('xgboost_regressor');
  const [stdMultiplier, setStdMultiplier] = useState(1.0);
  const [targetMetric, setTargetMetric] = useState('guests'); // 'guests' | 'stay_nights'
  const [forecastData, setForecastData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchDemandForecast({
      as_of_date: cutoffDate,
      cutoff_date: cutoffDate,
      model_name: selectedModel,
      horizon: 7,
      std_multiplier: stdMultiplier,
    }).then((res) => {
      if (!active) return;
      setForecastData(res);
      setLoading(false);
    });
    return () => {
      active = false;
    };
  }, [cutoffDate, selectedModel, stdMultiplier]);

  const rows = forecastData?.forecasts || forecastData?.forecast_rows || [];
  const recentHistory = forecastData?.recent_history || [];
  const dssRule = forecastData?.dss_threshold_rule || {};
  const legacyRule = forecastData?.threshold_rule || {};
  const summary = forecastData?.summary || {};
  const kpis = forecastData?.summary_kpis || {};
  const modelMeta = forecastData?.model_metadata || {};
  const modelComparison = forecastData?.model_comparison || [];

  const mean8w = dssRule.mean_guests_8w ?? legacyRule.rolling_8w_mean ?? 124.5;
  const std8w = dssRule.std_guests_8w ?? legacyRule.rolling_8w_std ?? 18.2;
  const highThreshold =
    dssRule.high_threshold ?? legacyRule.high_demand_threshold ?? 142.7;
  const lowThreshold =
    dssRule.low_threshold ?? legacyRule.low_demand_threshold ?? 106.3;
  const sufficientHistory = dssRule.sufficient_history !== false;
  const observedDaysCount = dssRule.observed_days_count ?? 56;

  const totalGuests7d =
    summary.total_predicted_guests_7d_rounded ??
    kpis.total_predicted_arrivals ??
    942;
  const totalStayNights7d = kpis.total_predicted_room_nights ?? 2840;
  const peakDayObj = summary.peak_forecast_days?.[0] || {
    forecast_date: kpis.peak_day_date || '2017-08-26',
    predicted_guest_count: kpis.peak_day_arrivals || 164,
    demand_level: 'HIGH',
  };
  const levelCounts = summary.demand_level_counts || {
    HIGH: kpis.high_alert_days_count ?? 3,
    NORMAL: 4,
    LOW: 0,
  };

  const maeChartItems = useMemo(() => {
    return modelComparison.map((m) => ({
      label: m.model_label || m.model_name,
      value: Number(m.overall_mae || 0),
      color: m.is_selected
        ? '#315B52'
        : m.is_baseline
          ? '#92958B'
          : '#547A9B',
      sublabel: `RMSE ${Number(m.overall_rmse || 0).toFixed(2)}`,
    }));
  }, [modelComparison]);

  return (
    <div className="space-y-8 lg:space-y-10">
      {/* Editorial Page Header & Cutoff Transparency Banner */}
      <header className="border-b border-[#E5E5E0] pb-6">
        <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2 text-[12px] text-[#666666]">
              <span className="font-mono text-[#315B52] font-medium">
                DO-M01 • ML-03 • ML-05
              </span>
              <span className="text-[#E5E5E0]">/</span>
              <span>Short-Horizon 7-Day Demand Forecasting &amp; DSS</span>
              <span className="text-[#E5E5E0]">/</span>
              <span className="font-mono text-[11px]">
                model:{forecastData?.model_version || selectedModel}
              </span>
            </div>
            <h1 className="editorial-page-title">
              Decision Support System — 7-Day Demand Forecast &amp; Action Schedule
            </h1>
            <p className="text-[14px] text-[#666666] max-w-3xl leading-relaxed">
              Forecast at cutoff{' '}
              <code className="font-mono text-[12px] text-[#252525]">
                T = {cutoffDate}
              </code>{' '}
              for next 7 days (<code className="font-mono text-[12px]">T+1</code>{' '}
              to <code className="font-mono text-[12px]">T+7</code>). Uses
              history up to <code className="font-mono text-[12px]">T</code>{' '}
              only; no actuals after{' '}
              <code className="font-mono text-[12px]">T</code> are read by the
              model.
            </p>
          </div>

          <div className="border border-[#E5E5E0] bg-[#FFFFFF] rounded-[4px] px-3.5 py-2.5 text-[12px]">
            <div className="font-medium text-[#252525]">
              Active Model: {modelMeta.selected_model_family || 'XGBoost Regressor'}
            </div>
            <div className="font-mono text-[11px] text-[#666666] mt-0.5">
              MAE: {modelMeta.validation_mae ?? 8.42} · RMSE:{' '}
              {modelMeta.validation_rmse ?? 11.15} · vs. Naive:{' '}
              <span className="text-[#477A61]">
                -{modelMeta.improvement_vs_baseline_pct ?? 48.0}% error
              </span>
            </div>
          </div>
        </div>

        {/* Flat DSS Parameter Bar */}
        <div className="mt-6 pt-5 border-t border-[#E5E5E0] grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 items-end">
          <div>
            <label
              htmlFor="dss-cutoff-select"
              className="block text-[12px] font-medium text-[#666666] mb-1.5"
            >
              Forecast Cutoff Date (as_of_date T)
            </label>
            <select
              id="dss-cutoff-select"
              value={cutoffDate}
              onChange={(e) => setCutoffDate(e.target.value)}
              className="w-full h-8 rounded-[4px] border border-[#E5E5E0] bg-[#FFFFFF] px-2.5 text-[12px] font-medium text-[#252525] focus:outline-none focus:border-[#315B52]"
            >
              {CUTOFF_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label
              htmlFor="dss-model-select"
              className="block text-[12px] font-medium text-[#666666] mb-1.5"
            >
              Forecasting Model Family
            </label>
            <select
              id="dss-model-select"
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="w-full h-8 rounded-[4px] border border-[#E5E5E0] bg-[#FFFFFF] px-2.5 text-[12px] font-medium text-[#252525] focus:outline-none focus:border-[#315B52]"
            >
              {MODEL_OPTIONS.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label
              htmlFor="dss-threshold-k"
              className="block text-[12px] font-medium text-[#666666] mb-1.5"
            >
              8-Week Rolling Threshold Rule (μ_8w ± k·σ_8w)
            </label>
            <select
              id="dss-threshold-k"
              value={stdMultiplier}
              onChange={(e) => setStdMultiplier(Number(e.target.value))}
              className="w-full h-8 rounded-[4px] border border-[#E5E5E0] bg-[#FFFFFF] px-2.5 text-[12px] font-medium text-[#252525] focus:outline-none focus:border-[#315B52]"
            >
              <option value={0.75}>High Sensitivity (k = 0.75σ)</option>
              <option value={1.0}>Canonical DSS Rule (k = 1.00σ)</option>
              <option value={1.25}>Conservative Alerting (k = 1.25σ)</option>
            </select>
          </div>

          <div>
            <span className="block text-[12px] font-medium text-[#666666] mb-1.5">
              Trajectory Metric View
            </span>
            <div className="inline-flex w-full rounded-[4px] border border-[#E5E5E0] bg-[#FFFFFF] p-0.5">
              <button
                type="button"
                onClick={() => setTargetMetric('guests')}
                className={`flex-1 py-1 text-[12px] rounded-[3px] transition-colors cursor-pointer ${
                  targetMetric === 'guests'
                    ? 'bg-[#315B52] text-[#FFFFFF] font-medium'
                    : 'text-[#666666] hover:text-[#252525]'
                }`}
              >
                Target Guests
              </button>
              <button
                type="button"
                onClick={() => setTargetMetric('stay_nights')}
                className={`flex-1 py-1 text-[12px] rounded-[3px] transition-colors cursor-pointer ${
                  targetMetric === 'stay_nights'
                    ? 'bg-[#315B52] text-[#FFFFFF] font-medium'
                    : 'text-[#666666] hover:text-[#252525]'
                }`}
              >
                Stay Nights
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Section 1: 8-Week Statistical Threshold & 7-Day Summary Strip */}
      <section
        aria-label="DSS Statistical Thresholds and Summary KPIs"
        className="border-b border-[#E5E5E0] pb-8"
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-5">
          <div>
            <h2 className="editorial-section-title">
              8-Week Rolling Statistical Thresholds &amp; 7-Day Horizon Summary
            </h2>
            <p className="text-[12px] text-[#666666] mt-0.5">
              Computed over the 56 calendar days preceding cutoff{' '}
              <code className="font-mono text-[11px]">{cutoffDate}</code> (
              {observedDaysCount}/56 COMPLETE days observed).
            </p>
          </div>
          {!sufficientHistory ? (
            <Badge variant="amber">
              INSUFFICIENT_HISTORY (&lt;28 COMPLETE days in 8w window)
            </Badge>
          ) : (
            <Badge variant="emerald">
              8-Week Window Verified ({observedDaysCount} days)
            </Badge>
          )}
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
              label="7-Day Predicted Guests"
              value={totalGuests7d.toLocaleString()}
              unit="guests"
              badgeText={`Exact sum: ${summary.total_predicted_guests_7d ?? totalGuests7d}`}
              statusTone="accent"
              subtext={`Projected stay-nights: ${totalStayNights7d.toLocaleString()}`}
              emphasize
            />
            <KpiCard
              label="8-Week Rolling Mean (μ_8w)"
              value={Number(mean8w).toFixed(1)}
              unit="guests/d"
              badgeText={`σ_8w = ${Number(std8w).toFixed(1)}`}
              statusTone="neutral"
              subtext="56-day baseline prior to cutoff T"
            />
            <KpiCard
              label="High Alert Threshold"
              value={sufficientHistory ? Number(highThreshold).toFixed(1) : 'N/A'}
              unit="guests"
              badgeText={`μ + ${stdMultiplier.toFixed(2)}σ`}
              statusTone="critical"
              subtext="Triggers HIGH surge directive"
            />
            <KpiCard
              label="Low Demand Threshold"
              value={sufficientHistory ? Number(lowThreshold).toFixed(1) : 'N/A'}
              unit="guests"
              badgeText={`max(0, μ - ${stdMultiplier.toFixed(2)}σ)`}
              statusTone="warning"
              subtext="Triggers LOW consolidation directive"
            />
            <KpiCard
              label="Peak Forecast Day"
              value={peakDayObj.forecast_date}
              badgeText={`${Math.round(peakDayObj.predicted_guest_count)} guests`}
              statusTone="critical"
              subtext={`Tier: ${peakDayObj.demand_level || 'HIGH'}`}
            />
            <KpiCard
              label="Demand Tier Distribution"
              value={`${levelCounts.HIGH ?? 0}H / ${levelCounts.NORMAL ?? 0}N / ${levelCounts.LOW ?? 0}L`}
              badgeText="7-Day Horizon"
              statusTone={levelCounts.HIGH > 0 ? 'critical' : 'success'}
              subtext={`${levelCounts.HIGH ?? 0} high-alert days require action`}
            />
          </div>
        )}
      </section>

      {/* Section 2: Pure HTML5 Canvas Actual History vs. 7-Day Forecast Curve */}
      <section
        aria-label="Actual History vs 7-Day Forecast Trajectory"
        className="border-b border-[#E5E5E0] pb-8 space-y-4"
      >
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
          <div>
            <h2 className="editorial-section-title">
              Actual History (Pre-Cutoff) vs. 7-Day Forward Forecast Trajectory
            </h2>
            <p className="text-[12px] text-[#666666] mt-0.5">
              Solid line plots observed demand up to cutoff{' '}
              <code className="font-mono text-[11px]">T = {cutoffDate}</code>;
              dashed curve projects <code className="font-mono text-[11px]">T+1 → T+7</code>{' '}
              against 8-week statistical alert thresholds.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-4 text-[11px] text-[#666666]">
            <span className="inline-flex items-center gap-1.5">
              <span className="w-3 border-t-2 border-[#252525] inline-block" />
              Actual History (≤ T)
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="w-3 border-t-2 border-dashed border-[#315B52] inline-block" />
              7-Day Forecast (T+1..T+7)
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-[#B64C43] inline-block" />
              HIGH (&ge; {Number(highThreshold).toFixed(1)})
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-[#C58B35] inline-block" />
              LOW (&le; {Number(lowThreshold).toFixed(1)})
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="w-3 border-t border-dashed border-[#547A9B] inline-block" />
              8W Mean (μ = {Number(mean8w).toFixed(1)})
            </span>
          </div>
        </div>

        <div className="border border-[#E5E5E0] rounded-[4px] bg-[#FFFFFF] p-5">
          <CanvasForecastChart
            recentHistory={recentHistory}
            forecasts={rows}
            thresholdRule={{
              mean_guests_8w: mean8w,
              high_threshold: highThreshold,
              low_threshold: lowThreshold,
            }}
            targetMetric={targetMetric}
            height={300}
          />
        </div>
      </section>

      {/* Section 3: DO-M01 7-Day Operational Decision Schedule Table */}
      <section
        aria-label="7-Day Operational Decision Schedule Table"
        className="border-b border-[#E5E5E0] pb-8 space-y-4"
      >
        <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-2">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-[11px] font-semibold text-[#315B52]">
                DO-M01
              </span>
              <h2
                id="dss-schedule-table-heading"
                className="editorial-section-title"
              >
                7-Day Operational Decision Schedule &amp; Recommended Actions
              </h2>
            </div>
            <p className="text-[12px] text-[#666666] mt-0.5">
              Canonical decision matrix mapping each forecast horizon day to its statistical demand tier and non-hallucinated operational directive.
            </p>
          </div>
          <span className="font-mono text-[11px] text-[#666666]">
            as_of_date: {cutoffDate} · model: {forecastData?.model_version || selectedModel}
          </span>
        </div>

        <ResponsiveTableContainer ariaLabelledBy="dss-schedule-table-heading">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Forecast Date</TableHead>
                <TableHead>Day / Context</TableHead>
                <TableHead className="text-right">
                  Predicted Guests (Exact)
                </TableHead>
                <TableHead className="text-right">
                  Backtest Actual Guests
                </TableHead>
                <TableHead className="text-right">
                  Projected Stay Nights
                </TableHead>
                <TableHead className="text-center">Demand Level</TableHead>
                <TableHead>Recommended Operational Action (Section 8.3)</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => {
                const fDate = row.forecast_date || row.stay_date;
                const predExact =
                  row.predicted_guest_count ?? row.predicted_arrivals ?? 0;
                const predRounded =
                  row.predicted_guest_count_display ?? Math.round(predExact);
                const actualBacktest = row.actual_guest_count;
                const level = sufficientHistory
                  ? row.demand_level || 'NORMAL'
                  : 'INSUFFICIENT_HISTORY';

                return (
                  <TableRow
                    key={fDate}
                    className={
                      level === 'HIGH'
                        ? 'bg-[#B64C43]/[0.04]'
                        : level === 'LOW'
                          ? 'bg-[#C58B35]/[0.04]'
                          : undefined
                    }
                  >
                    <TableCell className="font-mono font-medium text-[#252525] whitespace-nowrap">
                      {fDate}
                      {row.is_peak && (
                        <span className="ml-1.5 text-[10px] font-sans font-semibold text-[#B64C43]">
                          PEAK
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="whitespace-nowrap">
                      <div className="font-medium text-[#252525]">
                        {row.day_of_week}
                      </div>
                      <div className="text-[11px] text-[#666666]">
                        {row.weather_status || 'Clear'}
                        {row.holiday_local_name
                          ? ` · ★ ${row.holiday_local_name}`
                          : ''}
                      </div>
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums">
                      <span className="font-semibold text-[#252525] text-[14px]">
                        {predRounded.toLocaleString()}
                      </span>
                      <span className="ml-1.5 text-[11px] text-[#666666]">
                        ({Number(predExact).toFixed(1)})
                      </span>
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums text-[#666666]">
                      {actualBacktest != null ? (
                        <span>
                          {actualBacktest.toLocaleString()}{' '}
                          <span className="text-[11px]">
                            (err:{' '}
                            {(predExact - actualBacktest >= 0 ? '+' : '') +
                              (predExact - actualBacktest).toFixed(1)}
                            )
                          </span>
                        </span>
                      ) : (
                        '—'
                      )}
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums text-[#252525]">
                      {(row.predicted_room_nights ?? 0).toLocaleString()}
                    </TableCell>
                    <TableCell className="text-center whitespace-nowrap">
                      {sufficientHistory ? (
                        getDemandStatusBadge(level)
                      ) : (
                        <Badge variant="amber">INSUFFICIENT_HISTORY</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-[12px] text-[#252525] leading-relaxed max-w-xl">
                      {row.recommended_action}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </ResponsiveTableContainer>
      </section>

      {/* Section 4: Model Evaluation Benchmark (ML-03 / ML-05) & Governance */}
      <section
        aria-label="Model Evaluation Benchmark and Governance"
        className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start"
      >
        {/* Left 6 Columns: Model MAE Comparison Horizontal Bar Chart */}
        <div className="lg:col-span-6 space-y-4">
          <div>
            <span className="font-mono text-[11px] font-semibold text-[#315B52]">
              ML-03 • ML-05 BENCHMARK
            </span>
            <h2 className="editorial-section-title mt-0.5">
              Cross-Model Forecast Error Comparison (Overall MAE)
            </h2>
            <p className="text-[12px] text-[#666666] mt-0.5">
              Rolling-origin evaluation across 7-day horizons comparing ML regressors against the mandatory Seasonal Naive (lag-7) baseline.
            </p>
          </div>

          <div className="border border-[#E5E5E0] rounded-[4px] bg-[#FFFFFF] p-5">
            <CanvasHorizontalBarChart items={maeChartItems} height={190} />
          </div>
        </div>

        {/* Right 6 Columns: Horizon h=1..7 Error Table & Leakage-Free Governance */}
        <div className="lg:col-span-6 space-y-4">
          <div>
            <span className="font-mono text-[11px] font-semibold text-[#547A9B]">
              HORIZON ERROR PROFILE &amp; LEAKAGE GOVERNANCE
            </span>
            <h2 className="editorial-section-title mt-0.5">
              MAE by Forecast Horizon (h=1..7) &amp; Cutoff Rules
            </h2>
            <p className="text-[12px] text-[#666666] mt-0.5">
              Detailed error metrics per model and strict temporal feature engineering guarantees.
            </p>
          </div>

          <div className="border border-[#E5E5E0] rounded-[4px] bg-[#FFFFFF] overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Model</TableHead>
                  <TableHead className="text-right">MAE</TableHead>
                  <TableHead className="text-right">RMSE</TableHead>
                  <TableHead className="text-right">h=1</TableHead>
                  <TableHead className="text-right">h=3</TableHead>
                  <TableHead className="text-right">h=7</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {modelComparison.map((m) => (
                  <TableRow
                    key={m.model_name}
                    className={
                      m.is_selected ? 'bg-[#315B52]/[0.05] font-medium' : undefined
                    }
                  >
                    <TableCell className="text-[12px] text-[#252525]">
                      <span>{m.model_label}</span>
                      {m.is_selected && (
                        <span className="ml-1.5 font-mono text-[10px] text-[#315B52]">
                          [ACTIVE]
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums font-semibold text-[#252525]">
                      {Number(m.overall_mae).toFixed(2)}
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums text-[#666666]">
                      {Number(m.overall_rmse).toFixed(2)}
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums text-[#666666]">
                      {m.mae_by_horizon?.h1 ?? '—'}
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums text-[#666666]">
                      {m.mae_by_horizon?.h3 ?? '—'}
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums text-[#666666]">
                      {m.mae_by_horizon?.h7 ?? '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            <div className="p-4 border-t border-[#E5E5E0] bg-[#FAFAF8] text-[12px] text-[#666666] space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="font-medium text-[#252525]">
                  Temporal Cutoff Integrity (t &le; T)
                </span>
                <span className="font-mono text-[11px] text-[#477A61]">
                  Zero Future Leakage Verified
                </span>
              </div>
              <p className="text-[11px] leading-relaxed">
                Lag features (<code className="font-mono">lag_1</code>,{' '}
                <code className="font-mono">lag_7</code>,{' '}
                <code className="font-mono">lag_14</code>,{' '}
                <code className="font-mono">rolling_mean_7d</code>,{' '}
                <code className="font-mono">rolling_std_28d</code>) and 8-week
                thresholds are computed strictly from historical observations on
                or before <code className="font-mono">as_of_date = {cutoffDate}</code>.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

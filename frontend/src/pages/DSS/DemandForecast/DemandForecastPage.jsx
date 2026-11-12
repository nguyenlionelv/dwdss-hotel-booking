import React, { useEffect, useState } from "react";
import { fetchDemandForecast, fetchForecastModels } from "../../../services/dssApi";
import KpiCard from "../../../components/kpi/KpiCard";
import OperationalDecisionSupport from './OperationalDecisionSupport';
import OperationalDemandInsights from './OperationalDemandInsights';
import ModelDecisionEvaluation from './ModelDecisionEvaluation';
import { finiteNumber, formatDate, formatGuests, formatReference, formatWeekday } from '../../../lib/dssFormat.mjs';
import { CanvasForecastChart } from "../../../components/charts/TrendChart";
import ResponsiveTableContainer from "../../../components/tables/ResponsiveTableContainer";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";

const CUTOFF_OPTIONS = [
  {
    value: "2017-08-31",
    label: "T = 31 Aug 2017 (1-7 Sep forecast)",
  },
  {
    value: "2017-08-24",
    label: "T = 24 Aug 2017 (25–31 Aug backtest)",
  },
  {
    value: "2017-08-17",
    label: "T = 17 Aug 2017 (18–24 Aug backtest)",
  },
];

function getDemandStatusBadge(level) {
  if (level === "HIGH") {
    return (
      <Badge variant="destructive" className="gap-1.5 font-mono">
        <span className="w-1.5 h-1.5 rounded-full bg-status-critical" />
        <span>HIGH</span>
      </Badge>
    );
  }
  if (level === "LOW") {
    return (
      <Badge variant="amber" className="gap-1.5 font-mono">
        <span className="w-1.5 h-1.5 rounded-full bg-status-warning" />
        <span>LOW</span>
      </Badge>
    );
  }
  return (
    <Badge variant="emerald" className="gap-1.5 font-mono">
      <span className="w-1.5 h-1.5 rounded-full bg-status-success" />
      <span>NORMAL</span>
    </Badge>
  );
}

export default function DemandForecastPage() {
  const [cutoffDate, setCutoffDate] = useState("2017-08-31");
  const [selectedModel, setSelectedModel] = useState("");
  const [budgetUnits, setBudgetUnits] = useState(100);

  const [forecastData, setForecastData] = useState(null);
  const [modelOptions, setModelOptions] = useState([]);
  const [error, setError] = useState(null);
  useEffect(() => {
    let active = true;
    fetchForecastModels().then(({ models }) => {
      if (!active) return;
      const daily = models.filter((m) => m.kind === 'daily');
      if (!daily.length) throw new Error('No trained daily forecast artifacts available.');
      setModelOptions(daily);
      setSelectedModel((daily.find((m) => m.default) || daily[0]).id);
    }).catch((err) => { if (active) { setError(err.message); setLoading(false); } });
    return () => { active = false; };
  }, []);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!selectedModel) return;
    let active = true;
    setLoading(true);
    setError(null);
    setForecastData(null);
    fetchDemandForecast({
      as_of_date: cutoffDate,
      cutoff_date: cutoffDate,
      model_name: selectedModel,
      horizon: 7,
      budget_units: budgetUnits,
    }).then((res) => {
      if (!active) return;
      setForecastData(res);
      setLoading(false);
    }).catch((err) => { if (active) { setError(err.message); setLoading(false); } });
    return () => {
      active = false;
    };
  }, [cutoffDate, selectedModel, budgetUnits]);

  const rows = forecastData?.forecasts || forecastData?.forecast_rows || [];
  const recentHistory = forecastData?.recent_history || [];
  const dssRule = forecastData?.dss_threshold_rule || {};
  const legacyRule = forecastData?.threshold_rule || {};
  const summary = forecastData?.summary || {};
  const kpis = forecastData?.summary_kpis || {};
  const modelComparison = forecastData?.model_comparison || [];

  const mean8w = dssRule.mean_guests_8w ?? legacyRule.rolling_8w_mean ?? null;
  const std8w = dssRule.std_guests_8w ?? legacyRule.rolling_8w_std ?? null;
  const highThreshold =
    dssRule.high_threshold ?? legacyRule.high_demand_threshold ?? null;
  const lowThreshold =
    dssRule.low_threshold ?? legacyRule.low_demand_threshold ?? null;
  const sufficientHistory = dssRule.sufficient_history === true;

  const isNumber = (value) => finiteNumber(value) !== null;
  const totalGuests7d = summary.total_predicted_guests_7d_rounded ?? kpis.total_predicted_arrivals ?? null;
  const totalStayNights7d = kpis.total_predicted_room_nights ?? (
    rows.length > 0 && rows.every((row) => isNumber(row.predicted_room_nights))
      ? rows.reduce((total, row) => total + row.predicted_room_nights, 0)
      : null
  );
  const hasStayNights = rows.some((row) => isNumber(row.predicted_room_nights));
  const peakDayObj = summary.peak_forecast_days?.[0] ?? null;
  const lowDayObj = rows.reduce((lowest, row) => {
    if (!isNumber(row.predicted_guest_count)) return lowest;
    if (!lowest || row.predicted_guest_count < lowest.predicted_guest_count ||
        (row.predicted_guest_count === lowest.predicted_guest_count && row.forecast_date < lowest.forecast_date)) {
      return row;
    }
    return lowest;
  }, null);
  const levelCounts = summary.demand_level_counts ?? {};
  const hasMean = isNumber(mean8w);
  const hasStd = isNumber(std8w);
  const hasHighThreshold = isNumber(highThreshold);
  const hasLowThreshold = isNumber(lowThreshold);
  const hasThresholdMetrics = hasMean || hasStd || hasHighThreshold || hasLowThreshold;

  if (error) return <div role="alert" className="border border-divider rounded p-6 text-status-critical">Forecast unavailable: {error}</div>;

  return (
    <div className="space-y-8 lg:space-y-10">
      {/* Page introduction and forecast selectors */}
      <header className="border-b border-divider pb-5">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2 text-[12px] text-ink-secondary">
            <span>Short-Horizon 7-Day Demand Forecasting &amp; DSS</span>
            {forecastData?.is_mock && <Badge variant="amber">DEMO MODE - static sample</Badge>}
          </div>
          <h1 className="editorial-page-title">
            Decision Support System — 7-Day Demand Forecast &amp; Action
            Schedule
          </h1>
        </div>

        {/* Flat DSS Parameter Bar */}
        <div className="mt-5 pt-4 border-t border-divider grid grid-cols-1 sm:grid-cols-3 gap-4 items-end">
          <div>
            <label
              htmlFor="dss-cutoff-select"
              className="block text-[12px] font-medium text-ink-secondary mb-1.5"
            >
              Forecast Cutoff Date (as_of_date T)
            </label>
            <select
              id="dss-cutoff-select"
              value={cutoffDate}
              onChange={(e) => setCutoffDate(e.target.value)}
              className="w-full h-8 rounded-[4px] border border-divider bg-surface-primary px-2.5 text-[12px] font-medium text-ink-primary focus:outline-none focus:border-brand"
            >
              {CUTOFF_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="dss-budget-input" className="block text-[12px] font-medium text-ink-secondary mb-1.5">Weekly resource budget (abstract units)</label>
            <input id="dss-budget-input" type="number" min="0.01" max="10000" step="0.01" value={budgetUnits}
              onChange={(event) => {
                const next = Number(event.target.value);
                if (Number.isFinite(next) && next > 0 && next <= 10000) setBudgetUnits(next);
              }}
              className="w-full h-8 rounded-[4px] border border-divider bg-surface-primary px-2.5 text-[12px] font-medium text-ink-primary focus:outline-none focus:border-brand" />
          </div>

          <div>
            <label
              htmlFor="dss-model-select"
              className="block text-[12px] font-medium text-ink-secondary mb-1.5"
            >
              Forecasting Model Family
            </label>
            <select
              id="dss-model-select"
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="w-full h-8 rounded-[4px] border border-divider bg-surface-primary px-2.5 text-[12px] font-medium text-ink-primary focus:outline-none focus:border-brand"
            >
              {modelOptions.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </header>

      <section aria-labelledby="forecast-section-heading" className="space-y-8">
      <h2 id="forecast-section-heading" className="editorial-section-title">7-Day Demand Forecast</h2>

      {/* Forecast summary */}
      <section
        aria-label="DSS Statistical Thresholds and Summary KPIs"
        className="border-b border-divider pb-8"
      >
        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            {Array.from({ length: 2 }).map((_, i) => (
              <div key={i} className="space-y-2">
                <Skeleton className="h-3 w-24" />
                <Skeleton className="h-7 w-28" />
                <Skeleton className="h-3 w-20" />
              </div>
            ))}
          </div>
        ) : (
          <div data-testid="forecast-kpis" className="grid gap-6" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 220px), 1fr))' }}>
            {isNumber(totalGuests7d) && <KpiCard
              label="7-Day Predicted Guests"
              value={formatGuests(totalGuests7d)}
              unit="guests"
              statusTone="accent"
              subtext={isNumber(totalStayNights7d) ? `Projected stay-nights: ${formatGuests(totalStayNights7d)}` : undefined}
              emphasize
            />}
            {(hasMean || hasStd) && <KpiCard
              label={hasMean ? "8-Week Rolling Mean" : "8-Week Rolling Std"}
              value={formatReference(hasMean ? mean8w : std8w)}
              unit="guests/d"
              badgeText={hasMean && hasStd ? `Std = ${formatReference(std8w)}` : undefined}
              statusTone="neutral"
              subtext="56-day baseline through the latest available label"
            />}
            {hasHighThreshold && <KpiCard
              label="High Alert Threshold"
              value={formatReference(highThreshold)}
              unit="guests"
              badgeText="Mean + Std"
              statusTone="critical"
              subtext="Triggers HIGH surge directive"
            />}
            {hasLowThreshold && <KpiCard
              label="Low Demand Threshold"
              value={formatReference(lowThreshold)}
              unit="guests"
              badgeText="max(0, Mean - Std)"
              statusTone="warning"
              subtext="Triggers LOW consolidation directive"
            />}
            {peakDayObj && <KpiCard
              label="Peak Forecast Day"
              value={formatDate(peakDayObj.forecast_date)}
              badgeText={`${formatGuests(peakDayObj.predicted_guest_count)} guests`}
              statusTone="critical"
              subtext={sufficientHistory ? `Tier: ${peakDayObj.demand_level}` : undefined}
            />}
            {lowDayObj && <KpiCard
              label="Low Forecast Day"
              value={formatDate(lowDayObj.forecast_date)}
              badgeText={`${formatGuests(lowDayObj.predicted_guest_count)} guests`}
              statusTone="warning"
              subtext={sufficientHistory ? `Tier: ${lowDayObj.demand_level}` : undefined}
            />}
            {sufficientHistory && <KpiCard
              label="Demand Tier Distribution"
              value={`${levelCounts.HIGH ?? 0}H / ${levelCounts.NORMAL ?? 0}N / ${levelCounts.LOW ?? 0}L`}
              badgeText="7-Day Horizon"
              statusTone={levelCounts.HIGH > 0 ? "critical" : "success"}
              subtext={`${levelCounts.HIGH ?? 0} high-alert days require action`}
            />}
          </div>
        )}
      </section>

      {/* Section 2: Pure HTML5 Canvas Actual History vs. 7-Day Forecast Curve */}
      <section
        aria-label="Actual History vs 7-Day Forecast Trajectory"
        className="border-b border-divider pb-8 space-y-4"
      >
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
          <div>
            <h3 className="text-[15px] font-semibold text-ink-primary">
              Actual History (Pre-Cutoff) vs. 7-Day Forward Forecast Trajectory
            </h3>
            <p className="text-[12px] text-ink-secondary mt-0.5">
              Solid line plots observed demand up to cutoff{" "}
              <code className="font-mono text-[11px]">T = {formatDate(cutoffDate)}</code>;
              dashed curve projects{" "}
              <code className="font-mono text-[11px]">T+1 → T+7</code>
              {hasThresholdMetrics ? " against available 8-week statistical alert thresholds." : "."}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-4 text-[11px] text-ink-secondary">
            <span className="inline-flex items-center gap-1.5">
              <span className="w-3 border-t-2 border-ink-primary inline-block" />
              Actual History (≤ T)
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="w-3 border-t-2 border-dashed border-brand inline-block" />
              7-Day Forecast (T+1..T+7)
            </span>
            {hasHighThreshold && <span className="inline-flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-status-critical inline-block" />
              HIGH (&ge; {formatReference(highThreshold)})
            </span>}
            {hasLowThreshold && <span className="inline-flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-status-warning inline-block" />
              LOW (&le; {formatReference(lowThreshold)})
            </span>}
            {hasMean && <span className="inline-flex items-center gap-1.5">
              <span className="w-3 border-t border-dashed border-series-3 inline-block" />
              8W Mean ({formatReference(mean8w)})
            </span>}
          </div>
        </div>

        <div className="border border-divider rounded-[4px] bg-surface-primary p-5">
          <CanvasForecastChart
            recentHistory={recentHistory}
            forecasts={rows}
            thresholdRule={{
              mean_guests_8w: mean8w,
              high_threshold: highThreshold,
              low_threshold: lowThreshold,
            }}
            height={300}
          />
        </div>
      </section>

      {/* Section 3: DO-M01 7-Day Operational Decision Schedule Table */}
      <section
        aria-label="7-Day Operational Decision Schedule Table"
        className="border-b border-divider pb-8 space-y-4"
      >
        <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-2">
          <div>
            <div className="flex items-center gap-2">
              <h3
                id="dss-schedule-table-heading"
                className="text-[15px] font-semibold text-ink-primary"
              >
                {sufficientHistory ? "7-Day Operational Decision Schedule & Recommended Actions" : "7-Day Guest Forecast Schedule"}
              </h3>
            </div>
            <p className="text-[12px] text-ink-secondary mt-0.5">
              Daily guest forecasts and canonical backtest actuals.
              {sufficientHistory && " Demand tiers use the documented statistical rule and fixed actions."}
            </p>
          </div>
          <span className="font-mono text-[11px] text-ink-secondary">
            as_of_date: {formatDate(cutoffDate)} · model:{" "}
            {forecastData?.model_version || selectedModel}
          </span>
        </div>

        <ResponsiveTableContainer ariaLabelledBy="dss-schedule-table-heading">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Forecast Date</TableHead>
                <TableHead>Day / Context</TableHead>
                <TableHead className="text-right">
                  Predicted Guests
                </TableHead>
                <TableHead className="text-right">
                  Backtest Actual Guests
                </TableHead>
                {hasStayNights && <TableHead className="text-right">
                  Projected Stay Nights
                </TableHead>}
                {sufficientHistory && <TableHead className="text-center">Demand Level</TableHead>}
                {sufficientHistory && <TableHead>
                  Recommended Operational Action (Section 8.3)
                </TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => {
                const fDate = row.forecast_date || row.stay_date;
                const predExact = row.predicted_guest_count ?? row.predicted_arrivals;
                const actualBacktest = row.actual_guest_count;
                const level = sufficientHistory
                  ? row.demand_level || "NORMAL"
                  : "INSUFFICIENT_HISTORY";

                return (
                  <TableRow
                    key={fDate}
                    className={
                      level === "HIGH"
                        ? "bg-status-critical/[0.06]"
                        : level === "LOW"
                          ? "bg-status-warning/[0.06]"
                          : undefined
                    }
                  >
                    <TableCell className="font-mono font-medium text-ink-primary whitespace-nowrap">
                      {formatDate(fDate)}
                      {row.is_peak && (
                        <span className="ml-1.5 text-[10px] font-sans font-semibold text-status-critical">
                          PEAK
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="whitespace-nowrap">
                      <div className="font-medium text-ink-primary">
                        {formatWeekday(fDate)}
                      </div>
                      {(row.weather_status || row.holiday_local_name) && (
                        <div className="text-[11px] text-ink-secondary">
                          {[row.weather_status, row.holiday_local_name && `★ ${row.holiday_local_name}`].filter(Boolean).join(' · ')}
                        </div>
                      )}
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums">
                      <span className="font-semibold text-ink-primary text-[14px]">
                        {formatGuests(predExact)}
                      </span>
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums text-ink-secondary">
                      {actualBacktest != null ? (
                        <span>
                          {formatGuests(actualBacktest)}
                        </span>
                      ) : (
                        "—"
                      )}
                    </TableCell>
                    {hasStayNights && <TableCell className="text-right font-mono tabular-nums text-ink-primary">
                      {formatGuests(row.predicted_room_nights)}
                    </TableCell>}
                    {sufficientHistory && <TableCell className="text-center whitespace-nowrap">
                      {getDemandStatusBadge(level)}
                    </TableCell>}
                    {sufficientHistory && <TableCell className="text-[12px] text-ink-primary leading-relaxed max-w-xl">
                      {row.recommended_action}
                    </TableCell>}
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </ResponsiveTableContainer>
      </section>

      </section>

      {forecastData && <>
        <OperationalDecisionSupport forecastData={forecastData} />
        <OperationalDemandInsights insights={forecastData.decision_support?.insights ?? []} />
        <ModelDecisionEvaluation modelComparison={modelComparison} allocation={forecastData.resource_allocation} />
      </>}
    </div>
  );
}

import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import CompactFilter from "../../../components/filters/CompactFilter";
import { Button } from "@/components/ui/button";
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
    label: "31 Aug 2017",
  },
  {
    value: "2017-08-24",
    label: "24 Aug 2017",
  },
  {
    value: "2017-08-17",
    label: "17 Aug 2017",
  },
];

function getDemandStatusBadge(level) {
  if (level === "HIGH") {
    return (
      <Badge variant="destructive" className="gap-1.5 font-sans">
        <span className="w-1.5 h-1.5 rounded-full bg-status-critical" />
        <span>HIGH</span>
      </Badge>
    );
  }
  if (level === "LOW") {
    return (
      <Badge variant="amber" className="gap-1.5 font-sans">
        <span className="w-1.5 h-1.5 rounded-full bg-status-warning" />
        <span>LOW</span>
      </Badge>
    );
  }
  return (
    <Badge variant="emerald" className="gap-1.5 font-sans">
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
  const hasActuals = rows.some((row) => isNumber(row.actual_guest_count));
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


  const modelLabels = {
    imputed_canonical_history: "B4 weekday / Canonical",
    imputed_imputed_history: "B4 weekday / Imputed",
    causal_causal_history: "B4 matched / Causal",
  };

  return (
    <div className="space-y-8 lg:space-y-10">
      {/* Page introduction and forecast selectors */}
      <header className="border-b border-divider pb-5">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="space-y-2">
          {forecastData?.is_mock && <Badge variant="amber">DEMO MODE - static sample</Badge>}
          <h1 className="editorial-page-title">
            Hotel Operations Forecasting
          </h1>
          </div>
          <div className="flex flex-wrap gap-2">
            {[{ to: "/analytics/operations", label: "Analytics" }, { to: "/reports/operations", label: "Reporting" }].map((item) => (
              <Button key={item.to} variant="secondary" size="sm" className="h-8 w-28 border-slate-200 bg-slate-100 text-slate-700 hover:border-slate-300 hover:bg-slate-200 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700" asChild>
                <Link to={item.to}>{item.label}</Link>
              </Button>
            ))}
          </div>
        </div>

        <div className="mt-6 flex flex-wrap items-end gap-x-6 gap-y-5">
          <CompactFilter id="dss-cutoff-select" label="Cutoff date" value={cutoffDate}
            onChange={(event) => setCutoffDate(event.target.value)} options={CUTOFF_OPTIONS} />
          <div className="flex w-full min-w-0 flex-col gap-2.5 sm:w-48">
            <label htmlFor="dss-budget-input" className="text-[12px] text-ink-secondary">Weekly budget (units)</label>
            <input id="dss-budget-input" type="number" min="0.01" max="10000" step="0.01" value={budgetUnits}
              onChange={(event) => {
                const next = Number(event.target.value);
                if (Number.isFinite(next) && next > 0 && next <= 10000) setBudgetUnits(next);
              }}
              className="h-9 w-full min-w-0 rounded-[4px] border border-divider bg-surface-primary px-3 text-[13px] font-normal tabular-nums text-ink-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2" />
          </div>
          <CompactFilter id="dss-model-select" label="Model" value={selectedModel}
            onChange={(event) => setSelectedModel(event.target.value)}
            options={modelOptions.map((model) => ({ value: model.id, label: modelLabels[model.id] || model.label, title: model.label }))} />
        </div>
      </header>

      {error && <div role="alert" className="rounded-[4px] border border-status-critical/30 bg-status-critical/5 p-4 text-[13px] text-status-critical">Unable to update forecast: {error}</div>}

      <section aria-labelledby="forecast-section-heading" aria-busy={loading} className="space-y-8">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 id="forecast-section-heading" className="editorial-section-title">7-day forecast</h2>
        <span role="status" className="text-[12px] text-ink-secondary">
          {loading ? "Updating forecast…" : rows.length > 0 ? `${formatDate(rows[0].forecast_date || rows[0].stay_date)} – ${formatDate(rows[rows.length - 1].forecast_date || rows[rows.length - 1].stay_date)}` : "No forecast available"}
        </span>
      </div>

      {/* Forecast summary */}
      <section
        aria-label="DSS Statistical Thresholds and Summary KPIs"
        className="border-b border-divider pb-8"
      >
        {loading && !forecastData ? (
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
              label="Predicted guests"
              value={formatGuests(totalGuests7d)}
              unit="guests"
              statusTone="accent"
              subtext={isNumber(totalStayNights7d) ? `Projected stay-nights: ${formatGuests(totalStayNights7d)}` : undefined}
            />}
            {(hasMean || hasStd) && <KpiCard
              label={hasMean ? "8-week average" : "8-week deviation"}
              value={formatReference(hasMean ? mean8w : std8w)}
              unit="guests/d"
              badgeText={hasMean && hasStd ? `Std = ${formatReference(std8w)}` : undefined}
              statusTone="neutral"
              subtext="56-day baseline through the latest available label"
            />}
            {hasHighThreshold && <KpiCard
              label="High demand threshold"
              value={formatReference(highThreshold)}
              unit="guests"
              badgeText="Mean + Std"
              statusTone="critical"
              subtext="Triggers HIGH surge directive"
            />}
            {hasLowThreshold && <KpiCard
              label="Low demand threshold"
              value={formatReference(lowThreshold)}
              unit="guests"
              badgeText="max(0, Mean - Std)"
              statusTone="warning"
              subtext="Triggers LOW consolidation directive"
            />}
            {peakDayObj && <KpiCard
              label="Peak day"
              valueType="date"
              value={formatDate(peakDayObj.forecast_date)}
              badgeText={`${formatGuests(peakDayObj.predicted_guest_count)} guests`}
              statusTone="critical"
              subtext={sufficientHistory ? `Tier: ${peakDayObj.demand_level}` : undefined}
            />}
            {lowDayObj && <KpiCard
              label="Lowest day"
              valueType="date"
              value={formatDate(lowDayObj.forecast_date)}
              badgeText={`${formatGuests(lowDayObj.predicted_guest_count)} guests`}
              statusTone="warning"
              subtext={sufficientHistory ? `Tier: ${lowDayObj.demand_level}` : undefined}
            />}
            {sufficientHistory && <KpiCard
              label="Demand levels"
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
        className="forecast-reading-section border-b border-divider pb-8 space-y-4"
      >
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
          <div>
            <h3 className="text-[15px] font-semibold text-ink-primary">
              Demand outlook
            </h3>
            <p className="text-[12px] text-ink-secondary mt-0.5">
              Observed demand through {formatDate(forecastData?.as_of_date || cutoffDate)}, followed by the next seven days.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-4 text-[11px] text-ink-secondary">
            <span className="inline-flex items-center gap-1.5">
              <span className="w-3 border-t-2 border-ink-primary inline-block" />
              History
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="w-3 border-t-2 border-dashed border-brand inline-block" />
              Forecast
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

      {forecastData && <>
        <OperationalDecisionSupport forecastData={forecastData} />
        <OperationalDemandInsights insights={forecastData.decision_support?.insights ?? []} />
      </>}

      {/* Daily forecast details */}
      <section
        aria-label="7-Day Operational Decision Schedule Table"
        className="forecast-reading-section border-b border-divider pb-8 space-y-4"
      >
        <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-2">
          <div>
            <div className="flex items-center gap-2">
              <h3
                id="dss-schedule-table-heading"
                className="text-[15px] font-semibold text-ink-primary"
              >
                {sufficientHistory ? "Daily forecast and actions" : "Daily forecast"}
              </h3>
            </div>
            <p className="text-[12px] text-ink-secondary mt-0.5">
              {hasActuals ? "Actuals are available for these backtest dates." : "Actuals are not yet available for these forecast dates."}
            </p>
          </div>
          <details className="min-w-0 text-[12px] text-ink-secondary">
            <summary className="cursor-pointer">Forecast details</summary>
            <dl className="mt-2 space-y-1 max-w-sm break-words">
              <div><dt className="inline font-medium">Cutoff: </dt><dd className="inline">{formatDate(forecastData?.as_of_date || cutoffDate)}</dd></div>
              <div><dt className="inline font-medium">Model: </dt><dd className="inline">{forecastData?.model_version || selectedModel || "—"}</dd></div>
              <div><dt className="inline font-medium">Benchmarks: </dt><dd className="inline">{modelComparison.length} models in this protocol. Full comparison below.</dd></div>
            </dl>
          </details>
        </div>

        <ResponsiveTableContainer ariaLabelledBy="dss-schedule-table-heading">
          <Table className="min-w-[600px]">
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Day</TableHead>
                <TableHead className="text-right">
                  Predicted guests
                </TableHead>
                {hasActuals && <TableHead className="text-right">
                  Actual guests
                </TableHead>}
                {hasStayNights && <TableHead className="text-right">
                  Stay nights
                </TableHead>}
                {sufficientHistory && <TableHead className="text-center">Demand level</TableHead>}
                {sufficientHistory && <TableHead>
                  Recommended action
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
                    <TableCell className="font-sans font-medium tabular-nums text-ink-primary whitespace-nowrap">
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
                    <TableCell className="text-right font-sans tabular-nums">
                      <span className="font-semibold text-ink-primary text-[14px]">
                        {formatGuests(predExact)}
                      </span>
                    </TableCell>
                    {hasActuals && <TableCell className="text-right font-sans tabular-nums text-ink-secondary">
                      {actualBacktest != null ? (
                        <span>
                          {formatGuests(actualBacktest)}
                        </span>
                      ) : (
                        "—"
                      )}
                    </TableCell>}
                    {hasStayNights && <TableCell className="text-right font-sans tabular-nums text-ink-primary">
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
        <ModelDecisionEvaluation modelComparison={modelComparison} allocation={forecastData.resource_allocation} />
      </>}
    </div>
  );
}

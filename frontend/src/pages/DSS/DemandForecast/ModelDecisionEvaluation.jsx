import React from 'react';
import { finiteNumber, formatMetric, formatMrr, formatRate, formatRelativeImprovement } from '../../../lib/dssFormat.mjs';

const POLICY_NAMES = {
  uniform: 'Uniform',
  historical_weekday: 'Historical weekday',
  forecast_proportional: 'Forecast proportional',
};

function policyLabel(key) {
  return key.startsWith('blended_') ? `Blended (λ=${key.slice(8)})` : POLICY_NAMES[key] ?? key;
}

export default function ModelDecisionEvaluation({ modelComparison = [], allocation }) {
  const selectedModel = modelComparison.find(model => model.is_selected);
  const evaluation = allocation?.policy_evaluation;
  const results = evaluation?.validation_results;
  const policies = results?.policies ?? {};
  const selectedKey = results?.selected ?? allocation?.selected_policy;
  const selectedMetrics = policies[selectedKey];
  const policyRows = Object.entries(policies).filter(([key]) => key !== 'blended_0' && key !== 'blended_1');
  const canShowMrr = evaluation?.availability === 'available' && results?.status === 'available' && policyRows.length > 0;

  return (
    <details data-testid="model-decision-evaluation" className="group border border-[#E5E5E0] rounded-[4px] bg-white">
      <summary className="cursor-pointer p-5 sm:p-6 flex flex-wrap items-center justify-between gap-3 [&::-webkit-details-marker]:hidden">
        <div>
          <h2 className="editorial-section-title">Model &amp; Decision Evaluation</h2>
          <p className="text-[12px] text-[#666666] mt-1">Forecast error and allocation mismatch use different metrics and populations.</p>
        </div>
        <span className="text-[12px] text-[#315B52] font-medium group-open:rotate-90 transition-transform" aria-hidden="true">▸</span>
      </summary>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 p-5 sm:p-6 pt-0 sm:pt-0">
        <section aria-labelledby="ml-evaluation-heading" className="min-w-0 border-t border-[#E5E5E0] pt-5">
          <h3 id="ml-evaluation-heading" className="text-[15px] font-semibold text-[#252525]">ML Forecast Evaluation</h3>
          <p className="text-[11px] text-[#666666] mt-1">Validation MAE/RMSE · {selectedModel?.population ?? 'population unavailable'} · {selectedModel?.metric_protocol ?? 'protocol unavailable'}</p>

          <div className="grid grid-cols-2 gap-4 mt-4">
            <div className="bg-[#FAFAF8] p-3"><span className="block text-[11px] text-[#666666]">Selected model MAE</span><strong className="font-mono text-[19px] tabular-nums">{formatMetric(selectedModel?.overall_mae)}</strong><span className="block text-[11px] text-[#666666]">guests/day</span></div>
            <div className="bg-[#FAFAF8] p-3"><span className="block text-[11px] text-[#666666]">Selected model RMSE</span><strong className="font-mono text-[19px] tabular-nums">{formatMetric(selectedModel?.overall_rmse)}</strong><span className="block text-[11px] text-[#666666]">guests/day</span></div>
          </div>

          <div className="overflow-x-auto mt-4">
            <table className="w-full min-w-[660px] text-[12px] tabular-nums">
              <caption className="text-left font-medium text-[#252525] pb-2">Model comparison and horizon MAE (guests/day)</caption>
              <thead><tr className="border-b border-[#E5E5E0] text-left">
                <th className="py-2 pr-3">Model / protocol</th>
                <th className="py-2 text-right">MAE</th><th className="py-2 text-right">RMSE</th>
                {Array.from({ length: 7 }, (_, index) => <th key={index} className="py-2 text-right">h={index + 1}</th>)}
              </tr></thead>
              <tbody>{modelComparison.map(model => (
                <tr key={model.model_name} className={`border-b border-[#E5E5E0] last:border-0 ${model.is_selected ? 'bg-[#315B52]/[0.05]' : ''}`}>
                  <th scope="row" className="py-2 pr-3 text-left font-normal"><span className="block font-medium">{model.model_label ?? model.model_name}{model.is_selected ? ' · selected' : ''}</span><span className="block text-[10px] text-[#666666]">{model.population ?? '—'} · {model.metric_protocol ?? '—'}</span></th>
                  <td className="py-2 text-right">{formatMetric(model.overall_mae)}</td><td className="py-2 text-right">{formatMetric(model.overall_rmse)}</td>
                  {Array.from({ length: 7 }, (_, index) => <td key={index} className="py-2 text-right">{formatMetric(model.horizon_mae?.[String(index + 1)])}</td>)}
                </tr>
              ))}</tbody>
            </table>
          </div>
          <p className="text-[11px] text-[#666666] mt-3">Temporal cutoff: features use observations available at or before the model cutoff; publication timing is assumed.</p>
        </section>

        <section aria-labelledby="dss-evaluation-heading" className="min-w-0 border-t border-[#E5E5E0] pt-5">
          <h3 id="dss-evaluation-heading" className="text-[15px] font-semibold text-[#252525]">DSS Allocation Evaluation</h3>
          <p className="text-[11px] text-[#666666] mt-1">Development validation · causal proxy forecasts, not saved-model validation. Lower MRR is better; overlapping origins are dependent.</p>
          {canShowMrr ? <>
            <div className="grid grid-cols-2 gap-4 mt-4">
              <div className="bg-[#FAFAF8] p-3"><span className="block text-[11px] text-[#666666]">Selected mean MRR</span><strong className="font-mono text-[19px] tabular-nums">{formatMrr(selectedMetrics?.mean_mrr)}</strong></div>
              <div className="bg-[#FAFAF8] p-3"><span className="block text-[11px] text-[#666666]">Selected median MRR</span><strong className="font-mono text-[19px] tabular-nums">{formatMrr(selectedMetrics?.median_mrr)}</strong></div>
            </div>
            <p className="text-[11px] text-[#666666] mt-3">{results.eligible_origins} shared eligible seven-day origins · MRR is allocation mismatch, not cost.</p>
            <div className="overflow-x-auto mt-4">
              <table className="w-full min-w-[380px] text-[12px] tabular-nums">
                <caption className="text-left font-medium text-[#252525] pb-2">Policy comparison</caption>
                <thead><tr className="border-b border-[#E5E5E0] text-left"><th className="py-2 pr-3">Policy</th><th className="py-2 text-right">Mean MRR</th><th className="py-2 text-right">Median MRR</th></tr></thead>
                <tbody>{policyRows.map(([key, metrics]) => (
                  <tr key={key} className={`border-b border-[#E5E5E0] last:border-0 ${key === selectedKey ? 'bg-[#315B52]/[0.05]' : ''}`}>
                    <th scope="row" className="py-2 pr-3 text-left font-normal">{policyLabel(key)}{key === selectedKey ? ' · selected' : ''}</th>
                    <td className="py-2 text-right">{formatMrr(metrics.mean_mrr)}</td><td className="py-2 text-right">{formatMrr(metrics.median_mrr)}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4 text-[12px]">
              {['uniform', 'historical_weekday'].map(baseline => {
                const difference = selectedMetrics?.[`mean_improvement_vs_${baseline}`];
                const winRate = selectedKey === baseline ? null : selectedMetrics?.[`win_rate_vs_${baseline}`];
                return <div key={baseline} className="border border-[#E5E5E0] p-3">
                  <span className="block text-[#666666]">vs {POLICY_NAMES[baseline]}</span>
                  <strong className="block mt-1 font-mono tabular-nums">{formatRelativeImprovement(difference, policies[baseline]?.mean_mrr)} relative MRR improvement</strong>
                  {finiteNumber(winRate) !== null && <span className="block mt-1 text-[#666666]">Win rate: {formatRate(winRate)}</span>}
                </div>;
              })}
            </div>
            <p className="text-[11px] text-[#666666] mt-3">Policy selected on proxy validation. Differences are descriptive; no significance claim. Previously inspected retrospective holdout results are separate and were not used for policy selection.</p>
          </> : <p className="text-[12px] text-[#666666] mt-4">Allocation evaluation unavailable; no scores are inferred.</p>}
        </section>
      </div>
    </details>
  );
}

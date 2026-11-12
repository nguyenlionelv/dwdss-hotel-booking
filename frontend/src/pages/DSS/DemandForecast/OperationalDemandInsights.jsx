import React from 'react';
import { finiteNumber, formatDate, formatGuests, formatReference, formatSignedGuests, formatSignedPercent } from '../../../lib/dssFormat.mjs';

function insightEvidence(insight) {
  if (insight.analysis === 'weekday' && finiteNumber(insight.predicted_guests) !== null && finiteNumber(insight.historical_reference) !== null) {
    const deviation = finiteNumber(insight.deviation_pct);
    return `${formatGuests(insight.predicted_guests)} forecast vs ${formatReference(insight.historical_reference)} typical${deviation === null ? '' : ` · ${formatSignedPercent(deviation)} deviation`}.`;
  }
  if (insight.analysis === 'transition' && finiteNumber(insight.forecast_change) !== null && finiteNumber(insight.historical_reference) !== null) {
    return `${formatSignedGuests(insight.forecast_change)} forecast guests vs ${formatSignedGuests(insight.historical_reference)} typical change.`;
  }
  return insight.evidence;
}

export default function OperationalDemandInsights({ insights = [] }) {
  return (
    <section aria-labelledby="demand-insights-heading" data-testid="demand-insights" className="space-y-4 border-b border-[#E5E5E0] pb-8">
      <div>
        <h2 id="demand-insights-heading" className="editorial-section-title">Operational Demand Insights</h2>
        <p className="text-[12px] text-[#666666] mt-1">Context for the forecast, separate from the weekly resource allocation.</p>
      </div>
      {insights.length === 0 ? <p className="text-[12px] text-[#666666]">No supported planning insights for this forecast.</p> : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {insights.map(insight => (
            <article key={`${insight.forecast_date}-${insight.signal}`} aria-label={insight.title} className="border border-[#E5E5E0] bg-white rounded-[4px] p-4 min-w-0">
              <h3 className="text-[13px] font-medium text-[#315B52]">{insight.title}</h3>
              <time dateTime={insight.forecast_date} className="block font-mono text-[12px] text-[#666666] mt-2">{formatDate(insight.forecast_date)}</time>
              <p className="text-[12px] leading-relaxed text-[#252525] mt-2">{insightEvidence(insight)}</p>
              {insight.recommended_action && <p className="text-[12px] leading-relaxed text-[#252525] mt-2">{insight.recommended_action}</p>}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

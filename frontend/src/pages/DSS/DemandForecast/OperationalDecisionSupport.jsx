import React from 'react';
import { finiteNumber, formatDate, formatMetric, formatShare, formatSignedPoints, formatUnits } from '../../../lib/dssFormat.mjs';

const POLICY_NAMES = {
  uniform: 'Uniform',
  historical_weekday: 'Historical weekday',
  forecast_proportional: 'Forecast proportional',
  blended: 'Blended',
};

export default function OperationalDecisionSupport({ forecastData }) {
  if (!forecastData) return null;
  const allocation = forecastData.resource_allocation;
  const days = allocation?.daily_allocation ?? [];

  return (
    <section aria-labelledby="operational-support-heading" data-testid="operational-support" className="space-y-5 border-b border-[#E5E5E0] pb-8">
      <div>
        <h2 id="operational-support-heading" className="editorial-section-title">Weekly Resource Allocation</h2>
        <p className="text-[12px] text-[#666666] mt-1">Relative planning units across the next seven days. These are not staff, rooms, money or hours.</p>
      </div>

      {allocation?.status === 'ready' && days.length === 7 ? (
        <>
          <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2 border border-[#E5E5E0] rounded-[4px] bg-[#FAFAF8] p-4">
            <div><span className="block text-[11px] text-[#666666]">Selected policy</span><strong className="text-[15px] text-[#315B52]">{POLICY_NAMES[allocation.selected_policy] ?? allocation.selected_policy ?? '—'}</strong></div>
            <div><span className="block text-[11px] text-[#666666]">Weekly budget</span><strong className="font-mono text-[15px]">{formatUnits(allocation.budget_units)}</strong></div>
            {finiteNumber(allocation.lambda) !== null && <div><span className="block text-[11px] text-[#666666]">Forecast weight λ</span><strong className="font-mono text-[15px]">{formatMetric(allocation.lambda)}</strong></div>}
          </div>

          <div aria-label="Seven-day relative resource allocation chart" className="border border-[#E5E5E0] rounded-[4px] bg-white p-4 sm:p-5 space-y-3">
            {days.map(day => (
              <div key={day.date} className="grid grid-cols-[68px_minmax(0,1fr)_70px] sm:grid-cols-[100px_minmax(0,1fr)_80px_90px] items-center gap-x-2 gap-y-1 sm:gap-x-4 text-[12px]">
                <time dateTime={day.date} className="font-mono text-[#252525]">{formatDate(day.date, true)}</time>
                <div className="relative h-7 bg-[#F0F1ED] rounded-[3px] overflow-hidden" aria-hidden="true">
                  <div className="absolute top-0 left-0 h-full bg-[#315B52]" style={{ width: `${Math.max(0, Math.min(100, finiteNumber(day.allocation_pct) ?? 0))}%` }} />
                </div>
                <span className="text-right font-mono tabular-nums text-[#252525]">{formatShare(day.allocation_pct)}</span>
                <span className="col-start-2 col-span-2 sm:col-start-auto sm:col-span-1 text-right font-mono tabular-nums text-[#666666]">{formatUnits(day.allocation_units)}</span>
              </div>
            ))}
            <p className="text-[11px] text-[#666666]">Equal share reference: {formatShare(100 / 7)} per day. Percentages are rounded for display.</p>
          </div>

          {days.some(day => day.review_action) && <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {days.filter(day => day.review_action).map(day => (
              <div key={day.date} className="border border-[#E5E5E0] rounded-[4px] p-4 text-[12px]">
                <time dateTime={day.date} className="font-mono font-medium">{formatDate(day.date)}</time>
                <p className="mt-1 tabular-nums">{formatUnits(day.allocation_units)} · {formatSignedPoints(day.comparison_with_uniform_pct_points)} vs equal share</p>
                <p className="mt-1 text-[#666666]">{day.review_action}</p>
              </div>
            ))}
          </div>}
        </>
      ) : <p className="border border-[#E5E5E0] rounded-[4px] p-5 text-[13px] text-[#666666]">Seven valid forecast dates are required for resource allocation.</p>}
    </section>
  );
}

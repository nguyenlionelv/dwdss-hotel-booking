import React from 'react';
import { HorizontalBarChart } from '../../../components/charts/TrendChart';
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
    <section aria-labelledby="operational-support-heading" data-testid="operational-support" className="forecast-reading-section space-y-5 border-b border-divider pb-8">
      <div>
        <h2 id="operational-support-heading" className="editorial-section-title">Weekly allocation</h2>
        <p className="text-[12px] text-ink-secondary mt-1">Relative planning units, not staff, rooms, money or hours.</p>
      </div>

      {allocation?.status === 'ready' && days.length === 7 ? (
        <>
          <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2 border border-divider rounded-[4px] bg-surface-workspace p-4">
            <div><span className="block text-[12px] text-ink-secondary">Policy</span><strong className="text-[15px] font-medium text-ink-primary">{POLICY_NAMES[allocation.selected_policy] ?? allocation.selected_policy ?? '—'}</strong></div>
            <div><span className="block text-[11px] text-ink-secondary">Weekly budget</span><strong className="font-sans text-[15px] text-ink-primary">{formatUnits(allocation.budget_units)}</strong></div>
            {finiteNumber(allocation.lambda) !== null && <div><span className="block text-[11px] text-ink-secondary">Forecast weight λ</span><strong className="font-sans text-[15px] text-ink-primary">{formatMetric(allocation.lambda)}</strong></div>}
          </div>

          <div className="border border-divider rounded-[4px] bg-surface-primary p-4 sm:p-5 space-y-3">
            <HorizontalBarChart ariaLabel="Seven-day relative resource allocation chart" scaleMax={100}
              items={days.map(day => ({ label: formatDate(day.date, true), value: Math.max(0, Math.min(100, finiteNumber(day.allocation_pct) ?? 0)), formattedValue: `${formatShare(day.allocation_pct)} · ${formatUnits(day.allocation_units)}`, color: 'series1' }))} />
            <p className="text-[11px] text-ink-secondary">Equal share reference: {formatShare(100 / 7)} per day. Percentages are rounded for display.</p>
          </div>

          {days.some(day => day.review_action) && <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {days.filter(day => day.review_action).map(day => (
              <div key={day.date} className="border border-divider bg-surface-primary rounded-[4px] p-4 text-[12px]">
                <time dateTime={day.date} className="font-sans font-medium text-ink-primary">{formatDate(day.date)}</time>
                <p className="mt-1 tabular-nums text-ink-primary">{formatUnits(day.allocation_units)} · {formatSignedPoints(day.comparison_with_uniform_pct_points)} vs equal share</p>
                <p className="mt-1 text-ink-secondary">{day.review_action}</p>
              </div>
            ))}
          </div>}
        </>
      ) : <p className="border border-divider rounded-[4px] p-5 text-[13px] text-ink-secondary">Seven valid forecast dates are required for resource allocation.</p>}
    </section>
  );
}

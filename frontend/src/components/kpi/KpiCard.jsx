import React from 'react';
import { cn } from '@/lib/utils';

/**
 * Typographic KPI Data Group (DESIGN.md Section 4.3):
 * - Displays KPIs as typographic data groups rather than individual cards
 * - Bold Inter numerical value (32px, weight 700) with tabular numerals
 * - Medium-weight descriptive label (14px), allowed to wrap without truncation
 * - Optional status/delta indicator & concise supporting metadata (12px)
 * - No decorative icon containers or colored background boxes
 */
export default function KpiCard({
  label,
  value,
  unit,
  valueType = 'number',
  badgeText,
  subtext,
  statusTone = 'neutral', // 'neutral' | 'success' | 'warning' | 'critical' | 'accent'
  emphasize = false,
  className,
}) {
  return (
    <div
      className={cn(
        'kpi-data-group py-1 pr-4 flex flex-col gap-3 min-w-0',
        className
      )}
    >
      <div className="min-h-10 text-[14px] font-medium leading-5 text-ink-primary">
        {label}
      </div>

      <div className="flex flex-col items-start gap-1">
        <span
          className={cn(
            'editorial-metric-value tabular-nums',
            valueType === 'date' && 'editorial-metric-date',
            emphasize ? 'text-status-critical' : 'text-ink-primary'
          )}
        >
          {value}
        </span>
        {unit && (
          <span className="text-[13px] font-normal text-ink-secondary">
            {unit}
          </span>
        )}
      </div>
    </div>
  );
}

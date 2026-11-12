import React from "react";
import { cn } from "@/lib/utils";

/**
 * Typographic KPI Data Group (DESIGN.md Section 4.3):
 * - Displays KPIs as typographic data groups rather than individual cards
 * - Large tabular numerical value (28-32px, weight 600)
 * - Small sentence-case descriptive label (13px, ink-secondary)
 * - Optional status/delta indicator & concise supporting metadata (12px)
 * - No decorative icon containers or colored background boxes
 */
export default function KpiCard({
  label,
  value,
  unit,
  badgeText,
  subtext,
  statusTone = "neutral", // 'neutral' | 'success' | 'warning' | 'critical' | 'accent'
  emphasize = false,
  className,
}) {
  return (
    <div
      className={cn(
        "py-1 pr-4 flex flex-col justify-between min-w-0",
        className,
      )}
    >
      <div className="text-[13px] font-normal text-ink-secondary truncate">
        {label}
      </div>

      <div className="mt-1.5 flex items-baseline gap-1.5 flex-wrap">
        <span
          className={cn(
            "editorial-metric-value tabular-nums",
            emphasize ? "text-status-critical" : "text-ink-primary",
          )}
        >
          {value}
        </span>
        {unit && (
          <span className="text-[12px] font-normal text-ink-secondary">{unit}</span>
        )}
      </div>
    </div>
  );
}

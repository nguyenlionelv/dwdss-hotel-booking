import React from 'react';
import KpiCard from '../../../components/kpi/KpiCard';

export default function ReportKpi({ badgeText, subtext, ...props }) {
  return (
    <div className="min-w-0">
      <KpiCard {...props} />
      {(badgeText || subtext) && (
        <div className="mt-3 space-y-1 text-[12px] leading-5 text-ink-secondary">
          {badgeText && <p className="font-medium">{badgeText}</p>}
          {subtext && <p>{subtext}</p>}
        </div>
      )}
    </div>
  );
}

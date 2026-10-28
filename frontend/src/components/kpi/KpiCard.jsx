import React from 'react';

const TONE_MAP = {
  emerald: {
    iconBg: 'bg-emerald-50 text-emerald-600',
    badgeBg: 'bg-emerald-50 text-emerald-700',
  },
  blue: {
    iconBg: 'bg-blue-50 text-blue-600',
    badgeBg: 'bg-blue-50 text-blue-700',
  },
  indigo: {
    iconBg: 'bg-indigo-50 text-indigo-600',
    badgeBg: 'bg-indigo-50 text-indigo-700',
  },
  amber: {
    iconBg: 'bg-amber-50 text-amber-600',
    badgeBg: 'bg-amber-50 text-amber-700',
  },
  rose: {
    iconBg: 'bg-rose-50 text-rose-600',
    badgeBg: 'bg-rose-50 text-rose-700',
  },
};

export default function KpiCard({
  label,
  value,
  unit,
  badgeText,
  badgeIcon,
  subtext,
  icon = 'analytics',
  tone = 'emerald',
  highlightBorder = false,
}) {
  const palette = TONE_MAP[tone] || TONE_MAP.emerald;

  return (
    <div
      className={`quixotic-card p-6 relative overflow-hidden ${
        highlightBorder ? 'border-l-4 border-l-rose-500' : ''
      }`}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
          {label}
        </span>
        <div
          className={`w-10 h-10 rounded-2xl flex items-center justify-center ${palette.iconBg}`}
        >
          <span className="material-symbols-outlined text-[20px]">{icon}</span>
        </div>
      </div>

      <div className="flex items-baseline gap-2">
        <span className="text-3xl font-display font-extrabold text-slate-900 tabular-nums">
          {value}
        </span>
        {unit && (
          <span className="text-sm font-medium text-slate-500">{unit}</span>
        )}
      </div>

      {(badgeText || subtext) && (
        <div className="mt-3 flex items-center gap-2 text-xs flex-wrap">
          {badgeText && (
            <span
              className={`inline-flex items-center gap-1 font-semibold px-2 py-0.5 rounded-md ${palette.badgeBg}`}
            >
              {badgeIcon && (
                <span className="material-symbols-outlined text-[14px]">
                  {badgeIcon}
                </span>
              )}
              {badgeText}
            </span>
          )}
          {subtext && <span className="text-slate-400">{subtext}</span>}
        </div>
      )}
    </div>
  );
}

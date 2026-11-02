import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { TrendingUp, AlertTriangle, CheckCircle2, Zap } from 'lucide-react';

const TONE_STYLES = {
  emerald: {
    accentBar: 'border-l-emerald-600',
    iconBg: 'bg-emerald-50 text-emerald-700 border-emerald-100',
    badgeVariant: 'emerald',
  },
  blue: {
    accentBar: 'border-l-primary',
    iconBg: 'bg-blue-50 text-primary border-blue-100',
    badgeVariant: 'blue',
  },
  indigo: {
    accentBar: 'border-l-indigo-600',
    iconBg: 'bg-indigo-50 text-indigo-700 border-indigo-100',
    badgeVariant: 'secondary',
  },
  amber: {
    accentBar: 'border-l-amber-500',
    iconBg: 'bg-amber-50 text-amber-700 border-amber-100',
    badgeVariant: 'amber',
  },
  rose: {
    accentBar: 'border-l-rose-500',
    iconBg: 'bg-rose-50 text-rose-700 border-rose-100',
    badgeVariant: 'destructive',
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
  tone = 'blue',
  highlightBorder = false,
  className,
}) {
  const style = TONE_STYLES[tone] || TONE_STYLES.blue;

  return (
    <Card
      className={cn(
        'overflow-hidden transition-all duration-150 hover:border-slate-300 hover:shadow-xs',
        highlightBorder && cn('border-l-4', style.accentBar),
        className
      )}
    >
      <CardContent className="p-4 sm:p-5">
        <div className="flex items-start justify-between gap-2 mb-2">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground line-clamp-1">
            {label}
          </span>
          <div
            className={cn(
              'w-8 h-8 rounded-md flex items-center justify-center shrink-0 border text-xs',
              style.iconBg
            )}
          >
            {typeof icon === 'string' ? (
              <span className="material-symbols-outlined text-[18px]">{icon}</span>
            ) : (
              icon
            )}
          </div>
        </div>

        <div className="flex items-baseline gap-1.5">
          <span className="text-2xl sm:text-3xl font-display font-extrabold text-foreground tabular-nums tracking-tight">
            {value}
          </span>
          {unit && (
            <span className="text-xs font-medium text-muted-foreground">
              {unit}
            </span>
          )}
        </div>

        {(badgeText || subtext) && (
          <div className="mt-2.5 flex items-center gap-2 text-xs flex-wrap">
            {badgeText && (
              <Badge
                variant={style.badgeVariant}
                className="gap-1 font-semibold text-[10px] px-1.5 py-0.5"
              >
                {badgeIcon === 'trending_up' && <TrendingUp className="h-3 w-3" />}
                {badgeIcon === 'warning' && <AlertTriangle className="h-3 w-3" />}
                {badgeIcon && badgeIcon !== 'trending_up' && badgeIcon !== 'warning' && (
                  <span className="material-symbols-outlined text-[13px]">
                    {badgeIcon}
                  </span>
                )}
                {badgeText}
              </Badge>
            )}
            {subtext && (
              <span className="text-[11px] text-muted-foreground truncate">
                {subtext}
              </span>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

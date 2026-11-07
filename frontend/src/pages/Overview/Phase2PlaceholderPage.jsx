import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ArrowRight } from 'lucide-react';

const DOMAIN_INFO = {
  '/analytics/guest-customer': {
    title: 'Guest & Customer Composition Analytics',
    code: 'MART-02 / BI-02',
    desc: 'Analysis of guest composition (Single, Couple, Family), party size distribution, repeat guest behavior, and room type selection.',
  },
  '/analytics/revenue-cancellation': {
    title: 'Revenue & Cancellation Risk Analytics',
    code: 'MART-03 / BI-03',
    desc: 'Analysis of booking cancellation rates across lead-time brackets, deposit types, ADR tiers, and market segments.',
  },
  '/analytics/booking-performance': {
    title: 'Booking Channel & Segment Performance',
    code: 'MART-04 / BI-04',
    desc: 'Evaluation of distribution channels (OTA, Direct, Corporate) and travel agency booking velocity.',
  },
};

export default function Phase2PlaceholderPage() {
  const location = useLocation();
  const info = DOMAIN_INFO[location.pathname] || {
    title: 'Phase 2 Extended Hospitality Domain',
    code: 'PHASE-2',
    desc: 'Extended analytics domain planned beyond the current MVP operational scope.',
  };

  return (
    <div className="max-w-3xl py-8 space-y-8">
      <header className="border-b border-[#E5E5E0] pb-6 space-y-3">
        <div className="flex items-center gap-2.5">
          <Badge variant="amber" className="font-mono">
            {info.code} • Phase 2 Roadmap (Out of MVP Scope)
          </Badge>
          <span className="font-mono text-[11px] text-[#666666]">
            route: {location.pathname}
          </span>
        </div>

        <h1 className="editorial-page-title">{info.title}</h1>

        <p className="text-[14px] text-[#666666] leading-relaxed">
          {info.desc}
        </p>
      </header>

      <section className="border-b border-[#E5E5E0] pb-6 space-y-3 text-[13px] text-[#666666] leading-relaxed">
        <h2 className="editorial-section-title">
          MVP Architectural Scope Boundary
        </h2>
        <p>
          In accordance with{' '}
          <code className="font-mono text-[12px] text-[#252525]">
            docs/scope_assessment.md
          </code>{' '}
          and{' '}
          <code className="font-mono text-[12px] text-[#252525]">
            docs/detailed_plan.md
          </code>
          , the active MVP release focuses exclusively on{' '}
          <strong className="text-[#252525] font-medium">
            Daily Hotel Operations (City Hotel — Lisbon, Portugal)
          </strong>{' '}
          powered by the unified{' '}
          <code className="font-mono text-[12px] text-[#315B52]">
            mart.daily_hotel_ops
          </code>{' '}
          table (732 continuous days, 2015-08-31 → 2017-08-31).
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-[12px] font-semibold text-[#666666]">
          Active MVP Operational Views
        </h2>
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="default" size="sm" asChild className="gap-1.5">
            <Link to="/analytics/operations">
              <span>Operations Analytics (BI-01 to BI-04)</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </Button>
          <Button variant="outline" size="sm" asChild className="gap-1.5">
            <Link to="/reports/operations">
              <span>Operations Reports (DO-R01 &amp; DO-R02)</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </Button>
          <Button variant="outline" size="sm" asChild className="gap-1.5">
            <Link to="/dss/demand-forecast">
              <span>DSS 7-Day Demand Forecast (DO-M01)</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </Button>
        </div>
      </section>
    </div>
  );
}

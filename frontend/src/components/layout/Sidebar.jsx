import React from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { LockKeyhole } from 'lucide-react';

export const MAIN_NAV_ITEMS = [
  {
    to: '/analytics/operations',
    label: 'Operations Analytics',
    code: 'BI-01',
  },
  {
    to: '/reports/operations',
    label: 'Operations Reporting',
    code: 'DO-R01',
  },
  {
    to: '/dss/demand-forecast',
    label: 'Demand Forecasting',
    code: 'DO-M01',
  },
];

export const PHASE2_NAV_ITEMS = [
  {
    to: '/analytics/guest-customer',
    label: 'Guest & Customer',
    code: 'BI-02',
  },
  {
    to: '/analytics/revenue-cancellation',
    label: 'Revenue & Cancellation',
    code: 'BI-03',
  },
  {
    to: '/analytics/booking-performance',
    label: 'Booking Channel',
    code: 'BI-04',
  },
];

export function NavigationContent({ onNavClick }) {
  const location = useLocation();

  return (
    <div className="flex flex-col h-full justify-between text-[13px]">
      <div>
        {/* Editorial Brand Header (DESIGN.md Section 4.4) */}
        <Link
          to="/"
          onClick={onNavClick}
          className="block px-3 pb-5 mb-5 border-b border-divider focus:outline-none"
        >
          <div className="font-semibold text-ink-primary text-[15px] tracking-tight">
            Lumina Analytics
          </div>
          <div className="text-[12px] text-ink-secondary mt-0.5">
            City Hotel — Lisbon, Portugal
          </div>
        </Link>

        {/* Primary Operations Navigation */}
        <div className="px-3 mb-2 text-[12px] font-medium text-ink-primary">
          Operations views
        </div>
        <nav className="space-y-0.5" aria-label="Primary Navigation">
          {MAIN_NAV_ITEMS.map((item) => {
            const isActive =
              location.pathname === item.to ||
              (item.to === '/analytics/operations' &&
                (location.pathname === '/' ||
                  location.pathname === '/analytics')) ||
              (item.to === '/reports/operations' &&
                location.pathname === '/reports') ||
              (item.to === '/dss/demand-forecast' &&
                location.pathname === '/dss');

            return (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={onNavClick}
                className={() =>
                  cn(
                    'flex items-center justify-between px-3 py-2 rounded-[3px] text-[13px] text-ink-primary transition-colors relative',
                    isActive
                      ? 'font-medium bg-surface-subtle'
                      : 'font-normal hover:bg-surface-subtle'
                  )
                }
              >
                {isActive && (
                  <span className="absolute left-0 top-1.5 bottom-1.5 w-[2px] bg-ink-primary" />
                )}
                <span className="truncate">{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        <div className="my-5 border-t border-divider" />

        {/* Extended Roadmap Scope */}
        <div className="px-3 mb-2 flex items-center justify-between text-[12px] font-medium text-ink-primary">
          <span>Extended scope</span>
          <span className="text-[11px] font-mono text-ink-muted">Phase 2</span>
        </div>

        <nav className="space-y-0.5" aria-label="Extended Scope Navigation">
          {PHASE2_NAV_ITEMS.map((item) => (
            <button
              key={item.to}
              type="button"
              disabled
              title="Available in Phase 2"
              className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left rounded-[3px] text-[13px] text-ink-muted cursor-not-allowed"
            >
              <span className="truncate">{item.label}</span>
              <LockKeyhole
                aria-hidden="true"
                className="h-3.5 w-3.5 shrink-0"
              />
            </button>
          ))}
        </nav>
      </div>
    </div>
  );
}

export default function Sidebar({ open }) {
  return (
    <aside
      id="desktop-sidebar"
      aria-label="Main sidebar"
      className={cn(
        'fixed left-0 top-0 hidden h-screen w-[240px] bg-surface-primary border-r border-divider flex-col justify-between py-6 px-3 z-40 select-none transition-colors',
        open && 'lg:flex'
      )}
    >
      <NavigationContent />
    </aside>
  );
}

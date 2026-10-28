import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useSystemContext } from '../../hooks/useSystemContext';

export default function Header() {
  const { health, metadata } = useSystemContext();
  const location = useLocation();

  const totalDays = metadata?.date_range?.total_days || 793;
  const releaseId = metadata?.dataset_release_id || 'v9fe497e2';

  const getActiveSectionLabel = () => {
    if (location.pathname.startsWith('/reports')) return 'Reporting & KPI Reconciliation';
    if (location.pathname.startsWith('/dss')) return 'ML Decision Support System';
    return 'OLAP Multi-Dimensional Analytics';
  };

  return (
    <header className="sticky top-0 z-40 h-16 glass-header border-b border-slate-200/70 px-8 flex items-center justify-between">
      {/* Left Context Pills */}
      <div className="flex items-center gap-2.5 flex-wrap">
        <div className="flex items-center gap-2 bg-white px-3.5 py-1.5 rounded-full border border-slate-200/90 shadow-sm text-xs font-medium text-slate-700">
          <span className="material-symbols-outlined text-[16px] text-emerald-600">
            location_on
          </span>
          <span className="font-semibold text-slate-900">
            City Hotel — Lisbon, Portugal
          </span>
          <span className="text-slate-300">|</span>
          <span className="text-slate-500">Europe/Lisbon</span>
        </div>

        <div className="hidden xl:flex items-center gap-2 bg-white px-3.5 py-1.5 rounded-full border border-slate-200/90 shadow-sm text-xs font-medium text-slate-700">
          <span className="material-symbols-outlined text-[16px] text-blue-600">
            calendar_month
          </span>
          <span>01/07/2015 – 31/08/2017 ({totalDays} days actual)</span>
        </div>

        <div
          className="flex items-center gap-1.5 bg-emerald-50 text-emerald-700 px-3 py-1.5 rounded-full border border-emerald-200/70 text-xs font-semibold"
          title={`Dataset Release: ${releaseId}`}
        >
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          <span>
            {health?.mart_published ? 'Mart Healthy / Ready' : 'Mart Syncing'}
          </span>
        </div>
      </div>

      {/* Right Quick Navigation & Profile */}
      <div className="flex items-center gap-3">
        <span className="hidden lg:inline-flex items-center gap-1.5 text-[11px] font-semibold text-slate-500 bg-slate-100/90 px-3 py-1.5 rounded-full border border-slate-200/60">
          <span className="material-symbols-outlined text-[15px] text-slate-500">
            layers
          </span>
          {getActiveSectionLabel()}
        </span>

        <div className="flex items-center gap-1 bg-slate-100/90 p-1 rounded-full border border-slate-200/60">
          <Link
            to="/analytics/operations"
            className={`px-2.5 py-1 rounded-full text-[11px] font-bold transition-all ${
              location.pathname.startsWith('/analytics') || location.pathname === '/'
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            OLAP
          </Link>
          <Link
            to="/reports/operations"
            className={`px-2.5 py-1 rounded-full text-[11px] font-bold transition-all ${
              location.pathname.startsWith('/reports')
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            Reports
          </Link>
          <Link
            to="/dss/demand-forecast"
            className={`px-2.5 py-1 rounded-full text-[11px] font-bold transition-all ${
              location.pathname.startsWith('/dss')
                ? 'bg-emerald-600 text-white shadow-sm'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            DSS Forecast
          </Link>
        </div>

        <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-slate-800 to-slate-600 text-white flex items-center justify-center font-bold text-xs shadow-sm ring-2 ring-white">
          OP
        </div>
      </div>
    </header>
  );
}

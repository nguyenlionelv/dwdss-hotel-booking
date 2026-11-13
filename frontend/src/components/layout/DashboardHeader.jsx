import React from 'react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';

const destinations = [
  { id: 'analytics', to: '/analytics/operations', label: 'Analytics' },
  { id: 'reporting', to: '/reports/operations', label: 'Reporting' },
  { id: 'forecasting', to: '/dss/demand-forecast', label: 'Forecasting' },
];

export default function DashboardHeader({ page, title, actions, children }) {
  return (
    <header className="dashboard-page-header border-b border-divider pb-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="editorial-page-title">{title}</h1>
        <div className="dashboard-screen-only ml-auto flex flex-wrap items-center justify-end gap-3">
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
          <nav aria-label="Related dashboards" className="ml-auto flex flex-wrap gap-2">
            {destinations.filter(item => item.id !== page).map(item => (
              <Button key={item.id} variant="secondary" size="sm" className="h-8 w-28 border-slate-200 bg-slate-100 text-slate-700 hover:border-slate-300 hover:bg-slate-200 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700" asChild>
                <Link to={item.to}>{item.label}</Link>
              </Button>
            ))}
          </nav>
        </div>
      </div>
      {children && <div className="dashboard-screen-only mt-6">{children}</div>}
    </header>
  );
}

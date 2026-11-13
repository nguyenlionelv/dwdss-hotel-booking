import React from 'react';

export default function DataContext({ children, status, version, publishedAt, demo = false }) {
  const timestamp = publishedAt ? new Date(publishedAt) : null;
  return (
    <div className="report-context flex flex-wrap items-start justify-between gap-x-8 gap-y-3 rounded-[4px] border border-divider bg-surface-primary px-4 py-3 text-[12px] text-ink-secondary">
      <div className="min-w-0 space-y-1">{children}</div>
      <div className="min-w-0 space-y-1 sm:text-right">
        <p className="font-medium text-ink-primary">{demo ? 'Demo data' : status || 'Data status unavailable'}</p>
        {timestamp && Number.isFinite(timestamp.getTime()) && <p>Updated {timestamp.toLocaleString('en-GB', { timeZone: 'Europe/Lisbon' })} · Lisbon</p>}
        {version && <details className="max-w-sm break-all"><summary className="cursor-pointer">Data version</summary><code>{version}</code></details>}
      </div>
    </div>
  );
}

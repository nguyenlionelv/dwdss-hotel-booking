import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';
import { useSystemContext } from '../../hooks/useSystemContext';
import { Button } from '@/components/ui/button';

export default function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const {
    health,
    metadata,
    loading,
    demoMode,
    toggleDemoMode,
    refreshSystemStatus,
  } = useSystemContext();

  const isDemo = Boolean(
    demoMode || health?.is_mock || health?.demo_mode || metadata?.is_mock
  );
  const isOffline =
    !loading &&
    Boolean(
      health?.api_error ||
      metadata?.api_error ||
      health?.status === 'offline' ||
      health?.db_connected === false
    );

  return (
    <div className="min-h-screen bg-surface-workspace text-ink-primary flex flex-col transition-colors">
      <Sidebar open={sidebarOpen} />
      <div
        className={`flex-1 flex flex-col min-w-0 ${sidebarOpen ? 'lg:pl-[240px]' : ''}`}
      >
        <Header
          sidebarOpen={sidebarOpen}
          onToggleSidebar={() => setSidebarOpen((open) => !open)}
        />

        {isOffline && !isDemo && (
          <div
            role="alert"
            className="bg-status-critical/10 border-b border-status-critical/30 px-6 sm:px-8 lg:px-10 py-2.5 flex flex-wrap items-center justify-between gap-3 text-[12px] text-ink-primary"
          >
            <div>
              <strong className="font-semibold text-status-critical">
                Backend / Database Disconnected:
              </strong>{' '}
              <span>
                {health?.message ||
                  metadata?.error_message ||
                  'Unable to reach Operations Mart API. Live metrics are unavailable.'}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={refreshSystemStatus}
                className="h-7 text-[11px]"
              >
                Retry Connection
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => toggleDemoMode(true)}
                className="h-7 text-[11px] border-status-warning text-status-warning"
              >
                Enable Demo Mode (Sample Data)
              </Button>
            </div>
          </div>
        )}

        {isDemo && (
          <div
            role="status"
            className="bg-status-warning/10 border-b border-status-warning/30 px-6 sm:px-8 lg:px-10 py-2.5 flex flex-wrap items-center justify-between gap-3 text-[12px] text-ink-primary"
          >
            <div>
              <strong className="font-semibold text-status-warning">
                DEMO MODE (MOCK DATA):
              </strong>{' '}
              <span>
                Displaying static sample data for demonstration only — not live
                Operations Mart query results.
              </span>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => toggleDemoMode(false)}
              className="h-7 text-[11px]"
            >
              Exit Demo Mode &amp; Reconnect Live API
            </Button>
          </div>
        )}

        <main className="px-6 py-6 sm:px-8 lg:px-10 lg:py-8 max-w-[1600px] w-full mx-auto space-y-8 lg:space-y-10 flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

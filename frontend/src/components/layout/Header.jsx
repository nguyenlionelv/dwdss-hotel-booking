import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useSystemContext } from '../../hooks/useSystemContext';
import { NavigationContent } from './Sidebar';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import {
  Menu,
  MapPin,
  Calendar,
  CheckCircle2,
  RefreshCw,
  BarChart3,
  FileSpreadsheet,
  BrainCircuit,
} from 'lucide-react';

export default function Header() {
  const { health, metadata } = useSystemContext();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  const totalDays = metadata?.date_range?.total_days || 793;
  const releaseId = metadata?.dataset_release_id || 'v9fe497e2';

  const getActiveView = () => {
    if (location.pathname.startsWith('/reports')) {
      return {
        section: 'Reporting',
        title: 'Operations Reports (DO-R01)',
      };
    }
    if (location.pathname.startsWith('/dss')) {
      return {
        section: 'Decision Support',
        title: 'Demand Forecast (DO-M01)',
      };
    }
    return {
      section: 'Analytics',
      title: 'Operations Analytics (BI-01)',
    };
  };

  const activeView = getActiveView();

  return (
    <header className="sticky top-0 z-30 h-14 glass-header border-b px-4 sm:px-6 lg:px-8 flex items-center justify-between gap-4">
      {/* Left: Mobile Menu Trigger + Breadcrumb */}
      <div className="flex items-center gap-3 min-w-0">
        <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
          <SheetTrigger asChild>
            <Button
              variant="outline"
              size="icon"
              className="lg:hidden h-8 w-8 shrink-0"
              aria-label="Open Navigation Menu"
            >
              <Menu className="h-4 w-4" />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="p-4 w-72">
            <SheetHeader className="text-left mb-4">
              <SheetTitle className="text-sm font-bold text-foreground">
                Hotel Intelligence Platform
              </SheetTitle>
            </SheetHeader>
            <NavigationContent onNavClick={() => setMobileOpen(false)} />
          </SheetContent>
        </Sheet>

        <Breadcrumb className="hidden sm:flex">
          <BreadcrumbList>
            <BreadcrumbItem>
              <BreadcrumbLink asChild>
                <Link to="/" className="text-muted-foreground hover:text-foreground">
                  DWDSS
                </Link>
              </BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <span className="text-muted-foreground">{activeView.section}</span>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbPage className="font-semibold text-foreground">
                {activeView.title}
              </BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
      </div>

      {/* Middle: Context Badges */}
      <div className="hidden xl:flex items-center gap-2">
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-muted/60 border text-[11px] font-medium text-foreground">
          <MapPin className="h-3.5 w-3.5 text-emerald-600" />
          <span className="font-semibold">City Hotel — Lisbon</span>
          <span className="text-muted-foreground">• Europe/Lisbon</span>
        </div>

        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-muted/60 border text-[11px] font-medium text-muted-foreground">
          <Calendar className="h-3.5 w-3.5 text-primary" />
          <span>01/07/2015 – 31/08/2017 ({totalDays} days)</span>
        </div>

        <Badge
          variant={health?.mart_published ? 'emerald' : 'secondary'}
          className="gap-1.5 font-medium py-1 px-2.5"
          title={`Dataset Release: ${releaseId}`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 animate-pulse" />
          <span>{health?.mart_published ? 'Mart Ready' : 'Mart Syncing'}</span>
        </Badge>
      </div>

      {/* Right: View Switcher Tabs */}
      <div className="flex items-center gap-2">
        <div className="flex items-center p-0.5 rounded-md bg-muted border text-xs">
          <Link
            to="/analytics/operations"
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-[5px] text-xs font-semibold transition-all ${
              location.pathname.startsWith('/analytics') || location.pathname === '/'
                ? 'bg-background text-foreground shadow-xs'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            <BarChart3 className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">OLAP</span>
          </Link>
          <Link
            to="/reports/operations"
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-[5px] text-xs font-semibold transition-all ${
              location.pathname.startsWith('/reports')
                ? 'bg-background text-foreground shadow-xs'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            <FileSpreadsheet className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Reports</span>
          </Link>
          <Link
            to="/dss/demand-forecast"
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-[5px] text-xs font-semibold transition-all ${
              location.pathname.startsWith('/dss')
                ? 'bg-emerald-600 text-white shadow-xs'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            <BrainCircuit className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">DSS Forecast</span>
          </Link>
        </div>

        <div className="w-8 h-8 rounded-md bg-secondary text-secondary-foreground flex items-center justify-center font-bold text-xs border border-border shadow-2xs">
          OP
        </div>
      </div>
    </header>
  );
}

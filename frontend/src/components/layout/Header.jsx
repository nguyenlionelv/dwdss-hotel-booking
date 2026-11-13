import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useSystemContext } from '../../hooks/useSystemContext';
import { NavigationContent } from './Sidebar';
import { Button } from '@/components/ui/button';
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
import { Menu, Moon, Sun, PanelLeftClose, PanelLeftOpen } from 'lucide-react';

export default function Header({ sidebarOpen, onToggleSidebar }) {
  const { theme, toggleTheme } = useSystemContext();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const getActiveView = () => {
    if (location.pathname.startsWith('/reports')) {
      return {
        section: 'Reporting',
        title: 'Operations Reporting',
      };
    }
    if (location.pathname.startsWith('/dss')) {
      return {
        section: 'Decision Support',
        title: 'Demand Forecasting',
      };
    }
    if (
      location.pathname.startsWith('/analytics/guest') ||
      location.pathname.startsWith('/analytics/revenue') ||
      location.pathname.startsWith('/analytics/booking')
    ) {
      return {
        section: 'Extended Scope',
        title: 'Phase 2 Roadmap',
      };
    }
    return {
      section: 'Analytics',
      title: 'Operations Analytics',
    };
  };

  const activeView = getActiveView();

  return (
    <header className="sticky top-0 z-30 h-14 bg-surface-workspace border-b border-divider px-6 sm:px-8 lg:px-10 flex items-center justify-between gap-4 transition-colors">
      {/* Left: Mobile Menu Trigger + Breadcrumb */}
      <div className="flex items-center gap-3 min-w-0">
        <Button
          type="button"
          variant="outline"
          size="icon"
          className="hidden lg:inline-flex h-8 w-8 shrink-0"
          onClick={onToggleSidebar}
          aria-label={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
          title={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
          aria-expanded={sidebarOpen}
          aria-controls="desktop-sidebar"
        >
          {sidebarOpen ? (
            <PanelLeftClose aria-hidden="true" />
          ) : (
            <PanelLeftOpen aria-hidden="true" />
          )}
        </Button>
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
          <SheetContent
            side="left"
            className="p-4 w-[240px] bg-surface-primary border-divider"
          >
            <SheetHeader className="text-left sr-only">
              <SheetTitle>Navigation Menu</SheetTitle>
            </SheetHeader>
            <NavigationContent onNavClick={() => setMobileOpen(false)} />
          </SheetContent>
        </Sheet>

        <Breadcrumb>
          <BreadcrumbList className="text-[13px]">
            <BreadcrumbItem className="hidden sm:inline-flex">
              <BreadcrumbLink asChild>
                <Link
                  to="/"
                  className="text-ink-secondary hover:text-ink-primary"
                >
                  City Hotel DSS
                </Link>
              </BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator className="hidden sm:inline-flex" />
            <BreadcrumbItem className="hidden md:inline-flex">
              <span className="text-ink-secondary">{activeView.section}</span>
            </BreadcrumbItem>
            <BreadcrumbSeparator className="hidden md:inline-flex" />
            <BreadcrumbItem>
              <BreadcrumbPage className="font-semibold text-ink-primary">
                {activeView.title}
              </BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
      </div>

      <Button
        type="button"
        variant="outline"
        size="icon"
        onClick={() => toggleTheme()}
        aria-label={
          theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'
        }
        title={
          theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'
        }
        className="h-8 w-8 shrink-0 border-divider bg-surface-primary text-ink-primary hover:bg-surface-subtle"
      >
        {theme === 'dark' ? (
          <Sun aria-hidden="true" className="h-4 w-4" />
        ) : (
          <Moon aria-hidden="true" className="h-4 w-4" />
        )}
      </Button>
    </header>
  );
}

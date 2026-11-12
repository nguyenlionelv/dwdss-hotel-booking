import React, { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useSystemContext } from "../../hooks/useSystemContext";
import { NavigationContent } from "./Sidebar";
import { Button } from "@/components/ui/button";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Menu, Moon, Sun } from "lucide-react";

export default function Header() {
  const { health, metadata, theme, toggleTheme } = useSystemContext();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  const isDemo = Boolean(
    health?.is_mock ||
    health?.demo_mode ||
    metadata?.is_mock ||
    metadata?.demo_mode,
  );
  const isOffline = Boolean(
    health?.api_error ||
    metadata?.api_error ||
    health?.status === "offline" ||
    health?.db_connected === false,
  );
  const isHealthy =
    !isDemo &&
    !isOffline &&
    (health?.status === "healthy" || health?.status === "ok") &&
    Boolean(health?.db_connected) &&
    Boolean(health?.mart_published);

  const rawVersion =
    metadata?.data_version ||
    health?.data_version ||
    metadata?.dataset_release_id ||
    health?.dataset_release_id ||
    null;
  const shortVersion = rawVersion
    ? String(rawVersion).replace(/^v/, "").slice(0, 8)
    : isDemo
      ? "demo"
      : "offline";

  const statusLabel = isDemo
    ? "Demo Mode (Mock)"
    : isHealthy
      ? "Healthy"
      : isOffline
        ? "Offline / Error"
        : "Degraded";

  const statusColorClass = isHealthy
    ? "bg-status-success"
    : isDemo
      ? "bg-status-warning"
      : isOffline
        ? "bg-status-critical"
        : "bg-status-warning";

  const getActiveView = () => {
    if (location.pathname.startsWith("/reports")) {
      return {
        section: "Reporting",
        title: "Operations Reports",
      };
    }
    if (location.pathname.startsWith("/dss")) {
      return {
        section: "Decision Support",
        title: "Demand Forecast",
      };
    }
    if (
      location.pathname.startsWith("/analytics/guest") ||
      location.pathname.startsWith("/analytics/revenue") ||
      location.pathname.startsWith("/analytics/booking")
    ) {
      return {
        section: "Extended Scope",
        title: "Phase 2 Roadmap",
      };
    }
    return {
      section: "Analytics",
      title: "Operations Analytics",
    };
  };

  const activeView = getActiveView();

  return (
    <header className="sticky top-0 z-30 h-14 bg-surface-workspace border-b border-divider px-6 sm:px-8 lg:px-10 flex items-center justify-between gap-4 transition-colors">
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
          <SheetContent side="left" className="p-4 w-[240px] bg-surface-primary border-divider">
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
                <Link to="/" className="text-ink-secondary hover:text-ink-primary">
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

      {/* Right: Essential System Context (DESIGN.md Section 4.4 & Spec Section 3.1) */}
      <div className="flex items-center gap-3.5 text-[12px] text-ink-secondary">
        <span className="hidden xl:inline">
          City Hotel — Lisbon, Portugal (
          <span className="font-mono">Europe/Lisbon</span>)
        </span>
        <span className="hidden md:inline text-divider">|</span>
        <span
          className="hidden sm:inline font-mono text-ink-secondary"
          title="Active Mart Version"
        >
          running ver:{shortVersion}
        </span>
        <span className="hidden sm:inline text-divider">|</span>
        <span
          className="inline-flex items-center gap-1.5 font-medium text-ink-primary"
          title={
            health?.message ||
            `Mart published: ${String(Boolean(health?.mart_published))}`
          }
        >
          <span
            className={`relative inline-flex w-2 h-2 rounded-full ${statusColorClass}`}
          >
            <span
              className={`absolute inset-0 rounded-full animate-ping opacity-75 ${statusColorClass}`}
            />
          </span>
          <span>{statusLabel}</span>
        </span>
        <span className="text-divider">|</span>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => toggleTheme()}
          aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          className="h-7 px-2 text-[11px] gap-1.5 border-divider bg-surface-primary text-ink-primary hover:bg-surface-subtle"
        >
          {theme === "dark" ? (
            <>
              <Sun className="h-3.5 w-3.5 text-status-warning" />
              <span className="hidden sm:inline">Light</span>
            </>
          ) : (
            <>
              <Moon className="h-3.5 w-3.5 text-ink-secondary" />
              <span className="hidden sm:inline">Dark</span>
            </>
          )}
        </Button>
      </div>
    </header>
  );
}

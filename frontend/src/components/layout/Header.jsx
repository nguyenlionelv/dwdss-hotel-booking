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
import { Menu } from "lucide-react";

export default function Header() {
  const { health, metadata } = useSystemContext();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  const isDemo = Boolean(
    health?.is_mock || health?.demo_mode || metadata?.is_mock || metadata?.demo_mode
  );
  const isOffline = Boolean(
    health?.api_error ||
      metadata?.api_error ||
      health?.status === "offline" ||
      health?.db_connected === false
  );
  const isHealthy =
    !isDemo &&
    !isOffline &&
    (health?.status === "healthy" || health?.status === "ok") &&
    Boolean(health?.db_connected) &&
    Boolean(health?.mart_published);

  const actualStart =
    metadata?.date_range?.actual_start ||
    metadata?.date_range?.min_date ||
    "—";
  const actualEnd =
    metadata?.date_range?.actual_end ||
    metadata?.date_range?.max_date ||
    "—";
  const totalDays = metadata?.date_range?.total_days || 0;

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
    ? "bg-[#477A61]"
    : isDemo
      ? "bg-[#C58B35]"
      : isOffline
        ? "bg-[#B64C43]"
        : "bg-[#C58B35]";

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
    <header className="sticky top-0 z-30 h-14 bg-[#FAFAF8] border-b border-[#E5E5E0] px-6 sm:px-8 lg:px-10 flex items-center justify-between gap-4">
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
          <SheetContent side="left" className="p-4 w-[240px] bg-[#FFFFFF]">
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
                <Link to="/" className="text-[#666666] hover:text-[#252525]">
                  City Hotel DSS
                </Link>
              </BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator className="hidden sm:inline-flex" />
            <BreadcrumbItem className="hidden md:inline-flex">
              <span className="text-[#666666]">{activeView.section}</span>
            </BreadcrumbItem>
            <BreadcrumbSeparator className="hidden md:inline-flex" />
            <BreadcrumbItem>
              <BreadcrumbPage className="font-semibold text-[#252525]">
                {activeView.title}
              </BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
      </div>

      {/* Right: Essential System Context (DESIGN.md Section 4.4 & Spec Section 3.1) */}
      <div className="flex items-center gap-4 text-[12px] text-[#666666]">
        <span className="hidden xl:inline">
          City Hotel — Lisbon, Portugal (
          <span className="font-mono">Europe/Lisbon</span>)
        </span>
        <span className="hidden xl:inline text-[#E5E5E0]">|</span>
        <span className="hidden md:inline font-mono text-[#252525]">
          {actualStart} → {actualEnd}{" "}
          {totalDays > 0 && (
            <span className="font-sans text-[#666666]">({totalDays} days)</span>
          )}
        </span>
        <span className="hidden md:inline text-[#E5E5E0]">|</span>
        <span
          className="hidden sm:inline font-mono text-[#666666]"
          title="Active Mart Version"
        >
          running ver:{shortVersion}
        </span>
        <span className="hidden sm:inline text-[#E5E5E0]">|</span>
        <span
          className="inline-flex items-center gap-1.5 font-medium text-[#252525]"
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
      </div>
    </header>
  );
}

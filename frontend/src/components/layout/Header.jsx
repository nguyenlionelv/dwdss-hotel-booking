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

  const actualStart =
    metadata?.date_range?.actual_start ||
    metadata?.date_range?.min_date ||
    "2015-08-31";
  const actualEnd =
    metadata?.date_range?.actual_end ||
    metadata?.date_range?.max_date ||
    "2017-08-31";
  const totalDays = metadata?.date_range?.total_days || 732;

  const rawVersion =
    metadata?.data_version ||
    health?.data_version ||
    metadata?.dataset_release_id ||
    health?.dataset_release_id ||
    "9fe497e2";
  const shortVersion = String(rawVersion).replace(/^v/, "").slice(0, 8);

  const isHealthy =
    health?.status === "healthy" ||
    health?.status === "ok" ||
    Boolean(health?.mart_published);

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
          <span className="font-sans text-[#666666]">({totalDays} days)</span>
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
            className={`relative inline-flex w-2 h-2 rounded-full ${
              isHealthy ? "bg-[#477A61]" : "bg-[#C58B35]"
            }`}
          >
            <span
              className={`absolute inset-0 rounded-full animate-ping opacity-75 ${
                isHealthy ? "bg-[#477A61]" : "bg-[#C58B35]"
              }`}
            />
            <span
              className={`absolute inset-0 rounded-full ${
                isHealthy
                  ? "shadow-[0_0_6px_2px_rgba(71,122,97,0.65)]"
                  : "shadow-[0_0_6px_2px_rgba(197,139,53,0.65)]"
              }`}
            />
          </span>
          <span>{isHealthy ? "Healthy" : "Degraded"}</span>
        </span>
      </div>
    </header>
  );
}

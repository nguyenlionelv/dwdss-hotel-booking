import React from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { useSystemContext } from "../../hooks/useSystemContext";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import {
  BarChart3,
  FileSpreadsheet,
  BrainCircuit,
  Users,
  CreditCard,
  Network,
  Database,
  Lock,
  Layers,
} from "lucide-react";

export const MAIN_NAV_ITEMS = [
  {
    to: "/analytics/operations",
    icon: BarChart3,
    label: "Operations Analytics",
    code: "BI-01",
    desc: "OLAP Slice, Dice & Pivot",
  },
  {
    to: "/reports/operations",
    icon: FileSpreadsheet,
    label: "Operations Reports",
    code: "DO-R01",
    desc: "Weekly Demand & Directives",
  },
  {
    to: "/dss/demand-forecast",
    icon: BrainCircuit,
    label: "Decision Support (DSS)",
    code: "DO-M01",
    desc: "7-Day ML Demand Forecast",
  },
];

export const PHASE2_NAV_ITEMS = [
  {
    to: "/analytics/guest-customer",
    icon: Users,
    label: "Guest & Customer",
    code: "BI-02",
  },
  {
    to: "/analytics/revenue-cancellation",
    icon: CreditCard,
    label: "Revenue & Cancel",
    code: "BI-03",
  },
  {
    to: "/analytics/booking-performance",
    icon: Network,
    label: "Booking Channel",
    code: "BI-04",
  },
];

export function NavigationContent({ onNavClick }) {
  const location = useLocation();
  const { health, metadata } = useSystemContext();
  const releaseId =
    metadata?.dataset_release_id || health?.dataset_release_id || "v9fe497e2";

  return (
    <div className="flex flex-col h-full justify-between">
      <div>
        {/* Brand Identity Header */}
        <Link
          to="/"
          onClick={onNavClick}
          className="flex items-center gap-3 px-3 py-1 mb-6 group focus:outline-none"
        >
          <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center text-primary-foreground shadow-xs group-hover:scale-105 transition-transform">
            <Layers className="h-4 w-4" />
          </div>
          <div>
            <div className="font-display font-bold text-foreground text-sm tracking-tight leading-none flex items-center gap-1.5">
              <span>DWDSS</span>
              <span className="text-[10px] font-mono text-muted-foreground font-normal">
                v1.2
              </span>
            </div>
            <div className="text-[10px] font-semibold tracking-wider uppercase text-emerald-600 mt-1">
              Hotel Intelligence
            </div>
          </div>
        </Link>

        {/* Main Navigation (MVP Operations Domain) */}
        <div className="px-3 mb-2 flex items-center justify-between text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          <span>MVP Operations Scope</span>
          <span className="text-[9px] text-primary font-mono font-medium">3 active</span>
        </div>
        <nav className="space-y-1" aria-label="Main Navigation">
          {MAIN_NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive =
              location.pathname === item.to ||
              (item.to === "/analytics/operations" &&
                (location.pathname === "/" || location.pathname === "/analytics"));

            return (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={onNavClick}
                className={() =>
                  cn(
                    "flex items-center justify-between px-3 py-2 rounded-md text-xs font-medium transition-colors group relative",
                    isActive
                      ? "bg-primary/10 text-primary font-semibold"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted/60"
                  )
                }
              >
                {isActive && (
                  <span className="absolute left-0 top-1.5 bottom-1.5 w-1 bg-primary rounded-r-full" />
                )}
                <span className="flex items-center gap-2.5 min-w-0">
                  <Icon
                    className={cn(
                      "h-4 w-4 shrink-0 transition-colors",
                      isActive
                        ? "text-primary"
                        : "text-muted-foreground group-hover:text-foreground"
                    )}
                  />
                  <span className="truncate">{item.label}</span>
                </span>
                <span
                  className={cn(
                    "text-[10px] font-mono px-1.5 py-0.5 rounded transition-colors",
                    isActive
                      ? "bg-primary/15 text-primary font-semibold"
                      : "text-muted-foreground/80 bg-muted group-hover:text-foreground"
                  )}
                >
                  {item.code}
                </span>
              </NavLink>
            );
          })}
        </nav>

        <Separator className="my-5" />

        {/* Phase 2 Out-of-Scope Domains */}
        <div className="px-3 mb-2 flex items-center justify-between text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          <span>Phase 2 (Roadmap)</span>
          <Badge variant="secondary" className="text-[9px] py-0 px-1.5 font-normal">
            Locked
          </Badge>
        </div>

        <nav className="space-y-1" aria-label="Phase 2 Navigation">
          {PHASE2_NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.to;

            return (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={onNavClick}
                className={() =>
                  cn(
                    "flex items-center justify-between px-3 py-1.5 rounded-md text-xs transition-colors group",
                    isActive
                      ? "bg-muted text-foreground font-semibold"
                      : "text-muted-foreground/70 hover:text-muted-foreground hover:bg-muted/40"
                  )
                }
              >
                <span className="flex items-center gap-2.5">
                  <Icon className="h-3.5 w-3.5 shrink-0 opacity-70" />
                  <span className="truncate">{item.label}</span>
                </span>
                <Lock className="h-3 w-3 text-muted-foreground/50" />
              </NavLink>
            );
          })}
        </nav>
      </div>

      {/* Bottom Mart Engine Telemetry Card */}
      <div className="pt-4 space-y-2.5">
        <div className="rounded-lg border bg-muted/40 p-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold flex items-center gap-1.5">
              <Database className="h-3 w-3 text-primary" />
              <span>Mart Engine</span>
            </span>
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
            </span>
          </div>
          <div className="text-xs font-mono font-medium text-foreground truncate">
            mart.operations_daily
          </div>
          <div className="text-[10px] text-muted-foreground flex items-center justify-between border-t border-border/60 pt-2 font-mono">
            <span>Rel: {releaseId}</span>
            <Badge
              variant={health?.is_mock ? "secondary" : "emerald"}
              className="text-[9px] py-0 px-1 font-mono uppercase"
            >
              {health?.is_mock ? "Demo Mart" : "Live DW"}
            </Badge>
          </div>
        </div>

        <div className="px-1 flex items-center justify-between text-[10px] text-muted-foreground/80">
          <span>CO4031 • DW &amp; DSS</span>
          <span className="font-mono">Europe/Lisbon</span>
        </div>
      </div>
    </div>
  );
}

export default function Sidebar() {
  return (
    <aside className="fixed left-0 top-0 hidden lg:flex h-screen w-64 bg-card border-r flex-col justify-between p-4 z-40 select-none">
      <NavigationContent />
    </aside>
  );
}

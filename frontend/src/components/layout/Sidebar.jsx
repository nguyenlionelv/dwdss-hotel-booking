import React from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { useSystemContext } from "../../hooks/useSystemContext";
import { cn } from "@/lib/utils";

export const MAIN_NAV_ITEMS = [
  {
    to: "/analytics/operations",
    label: "Operations Analytics",
    code: "BI-01",
  },
  {
    to: "/reports/operations",
    label: "Operations Reports",
    code: "DO-R01",
  },
  {
    to: "/dss/demand-forecast",
    label: "Demand Forecast (DSS)",
    code: "DO-M01",
  },
];

export const PHASE2_NAV_ITEMS = [
  {
    to: "/analytics/guest-customer",
    label: "Guest & Customer",
    code: "BI-02",
  },
  {
    to: "/analytics/revenue-cancellation",
    label: "Revenue & Cancellation",
    code: "BI-03",
  },
  {
    to: "/analytics/booking-performance",
    label: "Booking Channel",
    code: "BI-04",
  },
];

export function NavigationContent({ onNavClick }) {
  const location = useLocation();
  const { health, metadata } = useSystemContext();

  const rawVersion =
    metadata?.data_version ||
    health?.data_version ||
    metadata?.dataset_release_id ||
    health?.dataset_release_id ||
    "9fe497e2";
  const shortVersion = String(rawVersion).replace(/^v/, "").slice(0, 8);
  const publishedAt = metadata?.published_at || health?.published_at;
  const formattedPublished = publishedAt
    ? String(publishedAt).slice(0, 10)
    : "2026-10-27";

  return (
    <div className="flex flex-col h-full justify-between text-[13px]">
      <div>
        {/* Editorial Brand Header (DESIGN.md Section 4.4) */}
        <Link
          to="/"
          onClick={onNavClick}
          className="block px-3 pb-5 mb-5 border-b border-[#E5E5E0] focus:outline-none"
        >
          <div className="font-semibold text-[#252525] text-[15px] tracking-tight">
            Lumina Analytics
          </div>
          <div className="text-[12px] text-[#666666] mt-0.5">
            City Hotel — Lisbon, Portugal
          </div>
        </Link>

        {/* Primary Operations Navigation */}
        <div className="px-3 mb-2 text-[12px] font-medium text-[#999999]">
          Operations views
        </div>
        <nav className="space-y-0.5" aria-label="Primary Navigation">
          {MAIN_NAV_ITEMS.map((item) => {
            const isActive =
              location.pathname === item.to ||
              (item.to === "/analytics/operations" &&
                (location.pathname === "/" ||
                  location.pathname === "/analytics")) ||
              (item.to === "/reports/operations" &&
                location.pathname === "/reports") ||
              (item.to === "/dss/demand-forecast" &&
                location.pathname === "/dss");

            return (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={onNavClick}
                className={() =>
                  cn(
                    "flex items-center justify-between px-3 py-2 rounded-[3px] text-[13px] transition-colors relative",
                    isActive
                      ? "text-[#315B52] font-semibold bg-[#315B52]/[0.06]"
                      : "-translate-x-1 text-[#666666] hover:text-[#252525] hover:bg-[#F4F4F0]",
                  )
                }
              >
                {isActive && (
                  <span className="absolute left-0 top-1.5 bottom-1.5 w-[2px] bg-[#315B52]" />
                )}
                <span className="truncate">{item.label}</span>
                <span
                  className={cn(
                    "text-[11px] font-mono",
                    isActive ? "text-[#315B52]" : "text-[#999999]",
                  )}
                >
                  {item.code}
                </span>
              </NavLink>
            );
          })}
        </nav>

        <div className="my-5 border-t border-[#E5E5E0]" />

        {/* Extended Roadmap Scope */}
        <div className="px-3 mb-2 flex items-center justify-between text-[12px] font-medium text-[#999999]">
          <span>Extended scope</span>
          <span className="text-[11px] font-mono text-[#999999]">Phase 2</span>
        </div>

        <nav className="space-y-0.5" aria-label="Extended Scope Navigation">
          {PHASE2_NAV_ITEMS.map((item) => {
            const isActive = location.pathname === item.to;

            return (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={onNavClick}
                className={() =>
                  cn(
                    "flex items-center justify-between px-3 py-1.5 rounded-[3px] text-[13px] transition-colors relative",
                    isActive
                      ? "text-[#252525] font-semibold bg-[#F4F4F0]"
                      : "text-[#999999] hover:text-[#666666] hover:bg-[#F4F4F0]/60",
                  )
                }
              >
                <span className="truncate">{item.label}</span>
                <span className="text-[11px] font-mono text-[#999999]">
                  {item.code}
                </span>
              </NavLink>
            );
          })}
        </nav>
      </div>
    </div>
  );
}

export default function Sidebar() {
  return (
    <aside className="fixed left-0 top-0 hidden lg:flex h-screen w-[240px] bg-[#FFFFFF] border-r border-[#E5E5E0] flex-col justify-between py-6 px-3 z-40 select-none">
      <NavigationContent />
    </aside>
  );
}

import React from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { useSystemContext } from "../../hooks/useSystemContext";

const MAIN_NAV_ITEMS = [
  {
    to: "/analytics/operations",
    matchPrefix: "/analytics/operations",
    icon: "analytics",
    label: "Operations Analytics",
    code: "BI-01",
  },
  {
    to: "/reports/operations",
    matchPrefix: "/reports/operations",
    icon: "assessment",
    label: "Operations Reports",
    code: "DO-R01",
  },
  {
    to: "/dss/demand-forecast",
    matchPrefix: "/dss/demand-forecast",
    icon: "psychology",
    label: "Decision Support (DSS)",
    code: "DO-M01",
  },
];

const PHASE2_NAV_ITEMS = [
  {
    to: "/analytics/guest-customer",
    icon: "group",
    label: "Guest & Customer",
  },
  {
    to: "/analytics/revenue-cancellation",
    icon: "payments",
    label: "Revenue & Cancel",
  },
  {
    to: "/analytics/booking-performance",
    icon: "hub",
    label: "Booking Channel",
  },
];

export default function Sidebar() {
  const location = useLocation();
  const { health, metadata } = useSystemContext();
  const releaseId =
    metadata?.dataset_release_id || health?.dataset_release_id || "v9fe497e2";

  return (
    <aside className="fixed left-0 top-0 h-screen w-[260px] bg-white border-r border-slate-200/80 flex flex-col justify-between py-6 px-4 z-50 select-none">
      <div>
        {/* Brand Identity Header */}
        <Link
          to="/"
          className="flex items-center gap-3 px-3 mb-8 group focus:outline-none"
        >
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-700 flex items-center justify-center text-white shadow-lg shadow-emerald-600/20 group-hover:scale-105 transition-transform">
            <span className="material-symbols-outlined text-[22px]">
              domain
            </span>
          </div>
          <div>
            <div className="font-display font-extrabold text-slate-900 text-base tracking-tight leading-none">
              DWDSS
            </div>
            <div className="text-[10px] font-bold tracking-widest uppercase text-emerald-600 mt-1">
              HOTEL INTELLIGENCE
            </div>
          </div>
        </Link>

        {/* Main Navigation (MVP Scope: Operations Domain) */}
        <div className="px-3 mb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">
          MVP Operations Scope
        </div>
        <nav className="space-y-1.5" aria-label="Main Navigation">
          {MAIN_NAV_ITEMS.map((item) => {
            const isActive =
              location.pathname === item.to ||
              (item.to === "/analytics/operations" &&
                (location.pathname === "/" ||
                  location.pathname === "/analytics"));

            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={() =>
                  `flex items-center justify-between px-3.5 py-2.5 rounded-xl font-medium text-sm transition-all ${
                    isActive
                      ? "bg-emerald-50/90 text-emerald-700 font-semibold shadow-sm ring-1 ring-emerald-500/20"
                      : "text-slate-600 hover:text-slate-900 hover:bg-slate-100/70"
                  }`
                }
              >
                <span className="flex items-center gap-3">
                  <span
                    className={`material-symbols-outlined text-[20px] ${
                      isActive ? "text-emerald-600" : "text-slate-400"
                    }`}
                  >
                    {item.icon}
                  </span>
                  <span>{item.label}</span>
                </span>
              </NavLink>
            );
          })}

          {/* Phase 2 Out-of-Scope Domains */}
          <div className="pt-5 pb-1.5 px-3">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              Phase 2 (Out of Scope)
            </span>
          </div>

          {PHASE2_NAV_ITEMS.map((item) => {
            const isActive = location.pathname === item.to;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={`flex items-center justify-between px-3.5 py-2 rounded-xl text-sm transition-all ${
                  isActive
                    ? "bg-slate-100 text-slate-800 font-semibold ring-1 ring-slate-300"
                    : "text-slate-400 hover:text-slate-600 hover:bg-slate-50"
                }`}
              >
                <span className="flex items-center gap-3">
                  <span className="material-symbols-outlined text-[19px]">
                    {item.icon}
                  </span>
                  <span>{item.label}</span>
                </span>
                <span className="text-[9px] bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded font-bold uppercase tracking-wider">
                  Locked
                </span>
              </NavLink>
            );
          })}
        </nav>
      </div>

      {/* Bottom Engine & Dataset Release Status Card */}
      <div className="space-y-3">
        <div className="p-3.5 rounded-2xl bg-slate-900 text-white relative overflow-hidden">
          <div className="absolute -right-4 -top-4 w-16 h-16 rounded-full bg-emerald-500/10 blur-xl pointer-events-none"></div>
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">
              Mart Engine
            </span>
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
          </div>
          <div className="text-xs font-semibold text-emerald-400 truncate">
            mart.operations_daily
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5 font-mono flex items-center justify-between">
            <span>Release: {releaseId}</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
              {health?.is_mock ? "Demo Mode" : "Live DB"}
            </span>
          </div>
        </div>

        <div className="px-2 flex items-center justify-between text-[11px] text-slate-400">
          <span>CO4031 — DW &amp; DSS</span>
          <span className="font-mono">Europe/Lisbon</span>
        </div>
      </div>
    </aside>
  );
}

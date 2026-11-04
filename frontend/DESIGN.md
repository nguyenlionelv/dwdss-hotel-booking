# Design System: Hotel Operations DSS (Lumina Analytics)
**Project ID:** `projects/16851751821645352227`
**Domain:** Hospitality Data Warehouse & Decision Support System (City Hotel — Lisbon, Portugal)

---

## 1. Visual Theme & Atmosphere

**Lumina Analytics (Quixotic / Apple HIG Enterprise Aesthetic)** is a high-craft, daylight-first hospitality intelligence interface engineered for executive clarity and operational precision. Rather than relying on heavy dark-mode chromes or stark black-and-white grid borders, the interface uses **tonal surface layering**—floating pure white elevated cards over a cool, soft alabaster-slate canvas (`#f4f5f8`) with subtle translucent glassmorphism in sticky navigation bars.

The atmosphere balances **editorial authority** with **analytical density**:
- **Tactile Card Elevation:** Cards sit on a whisper-soft ambient shadow (`0 16px 36px -8px rgba(15, 23, 42, 0.04)`) with generous `24px–28px` (`1.5rem–1.75rem`) border radii, eliminating visual clutter while separating functional domains (OLAP Slice & Dice, KPI Reconciliations, and 7-Day ML Forecast Schedules).
- **Dual-Accent Semantic Hierarchy:** High-trust **Executive Azure (`#0059b5` / `#0071e3`)** anchors analytical navigation, primary actions, and OLAP time-series curves, while **Hospitality Emerald (`#059669` / `#10b981`)** highlights operational health, verified mart states, and Decision Support System (DSS) forecast signals.
- **High-Scannability Data Surfaces:** Tabular logs, multi-dimensional OLAP pivot matrices, and 7-day staffing schedules pair uppercase micro-tracked headers with tabular numerals (`font-variant-numeric: tabular-nums`) and semantic pill badges.

---

## 2. Color Palette & Roles

### Surface & Canvas Tokens
- **Primary Canvas Background (`#f4f5f8`):** Cool alabaster-slate background behind the main workspace that provides gentle contrast for pure white cards.
- **Secondary Well / Filter Surface (`#f8fafc` to `#f1f5f9`):** Recessed container fill used for filter toolbars, pill selectors, table headers, and inactive tab wells.
- **Elevated Card Surface (`#ffffff`):** Pure crisp white used for KPI cards, chart containers, OLAP pivot tables, and executive summary blocks.
- **Translucent Glass Header (`rgba(255, 255, 255, 0.85)`):** Frosted top bar surface paired with `backdrop-filter: blur(20px)`.
- **Executive Dark Card Gradient (`linear-gradient(135deg, #0f172a 0%, #1e293b 100%)`):** High-contrast deep navy slate surface used for executive shift allocation directives and system engine status cards.

### Brand & Semantic Accents
- **Executive Azure Primary (`#0059b5` / `#0071e3`):** Primary interactive accent for active navigation indicators, primary CTA buttons, OLAP demand curves, and selected time-grain pills.
- **Azure Soft Tint (`#eff6ff` / `#dbeafe`):** Subtle highlight fill for active sidebar routes, holiday impact callouts, and info badges.
- **Hospitality Emerald Brand (`#059669`):** Primary operational accent for DSS forecast highlights, active model badges, and positive KPI deltas.
- **Emerald Vibrant Accent (`#10b981`):** Used for live status dots (`Mart Healthy / Ready`), forecast area gradients, and high-confidence completion bars.
- **Emerald Soft Tint (`#ecfdf5` / `#d1fae5`):** Background fill for normal capacity badges (`Bình thường`), verified mart pills, and DSS model banners.

### Typography & Ink Hierarchy
- **Primary Deep Ink (`#0f172a`):** High-contrast slate-navy for page titles, hero KPI numerals, and primary table row identifiers.
- **Secondary Body Ink (`#334155` / `#475569`):** Balanced slate for analytical descriptions, table data cells, and inactive navigation labels.
- **Muted Metadata Ink (`#64748b` / `#94a3b8`):** Subtle grey-slate for axis labels, timestamps, release hashes (`v9fe497e2`), and micro-captions.

### Alert & Threshold Status Tokens
- **High Alert / Surge Crimson (`#ef4444` / `#f43f5e`):** Semantic danger accent for high-demand threshold breaches (`Cao (> 142.7)`), peak surge dots, and critical staffing alerts.
- **High Alert Soft Fill (`#fef2f2` / `#fee2e2`):** Background tint for peak surge table rows and high-demand warning badges (`#b91c1c` text).
- **Amber Caution / Moderate Notice (`#f59e0b` / `#d97706`):** Used for weather anomaly notices, degraded mart states, or weekend transition markers (`#fffbeb` fill).
- **Border & Hairline Divider (`#e2e8f0` / `#f1f5f9`):** Delicate 1px structural borders (`rgba(226, 232, 240, 0.8)`) that define cards and table rows without visual heaviness.

---

## 3. Typography Rules

### Font Families
- **Display & Headlines (`Plus Jakarta Sans`):** Geometric, modern sans-serif used for page headers, section titles, and large KPI hero numerals.
- **UI, Controls & Data Tables (`Inter`):** High-legibility neo-grotesque sans-serif used for body copy, filter controls, badges, and dense multi-column tables.
- **Monospace / Technical Identifiers (`JetBrains Mono` / `monospace`):** Used for dataset release hashes (`v9fe497e2`), SQL mart view names (`mart.operations_daily`), and formula expressions.

### Typographic Scale & Weight Hierarchy
- **Page Hero Title:** `1.875rem` (`30px`), `font-weight: 800`, `letter-spacing: -0.025em`, line-height `1.2`, color `#0f172a`.
- **Card Section Header:** `1.125rem` (`18px`), `font-weight: 700`, `letter-spacing: -0.015em`, color `#0f172a`.
- **Hero KPI Metric Value:** `1.875rem` to `2.25rem` (`30px–36px`), `font-weight: 800`, `letter-spacing: -0.03em`, `font-variant-numeric: tabular-nums`.
- **Body & Analytical Copy:** `0.875rem` (`14px`), `font-weight: 400–500`, line-height `1.5`, color `#475569`.
- **Table & Filter Labels (Micro-Header):** `0.6875rem` (`11px`), `font-weight: 700`, uppercase, `letter-spacing: 0.08em`, color `#64748b`.

---

## 4. Component Stylings

### App Shell & Navigation
- **Fixed Left Sidebar (`260px` width):** Pure white surface (`#ffffff`) with a subtle right border (`1px solid rgba(226, 232, 240, 0.8)`). Features brand identity header (`DWDSS — HOTEL INTELLIGENCE`), primary navigation links with `12px` (`rounded-xl`) corners, a collapsible/clearly labeled `PHASE 2 (OUT OF SCOPE)` section with `LOCKED` pills, and a dark slate engine status card at the bottom.
- **Sticky Glass Topbar (`64px` height):** Translucent white header (`rgba(255, 255, 255, 0.85)`) with `backdrop-filter: blur(20px)`. Houses context pills (`City Hotel — Lisbon, Portugal | Europe/Lisbon`, `01/07/2015 – 31/08/2017 (793 days)`), live `Mart Healthy / Ready` indicator with pulsing emerald dot, quick search, and user profile.

### Cards & Containers
- **Elevated Analytical Card:** Background `#ffffff`, border-radius `24px–28px` (`1.5rem–1.75rem`), border `1px solid rgba(226, 232, 240, 0.8)`, ambient shadow `0 16px 36px -8px rgba(15, 23, 42, 0.04), 0 4px 12px -2px rgba(15, 23, 42, 0.02)`. Hover state gently lifts shadow (`0 20px 40px -12px rgba(15, 23, 42, 0.08)`).
- **KPI Summary Card:** Compact `p-6` (`24px`) card with a top row containing an uppercase tracking label (`11px`) and a `40px × 40px` (`rounded-2xl`) tinted icon badge, followed by the large tabular numeral and a bottom semantic pill badge (`+4.2% YoY`, `Peak Cap`, or `Optimal`).

### Interactive Filter Bar & Segmented Controls
- **Filter Toolbar Card:** Full-width rounded card (`rounded-[24px]`) containing labeled select dropdowns (`bg-[#f8fafc]`, `border-slate-200/80`, `rounded-xl`), segmented pill toggles (`Day | Week | Month | Quarter | Year`), and high-contrast action buttons (`Apply Filters`, `Export CSV`).
- **Segmented Pill Selector:** Recessed slate well (`bg-slate-100/90 p-1 rounded-xl`) where the active option receives an elevated white or primary-tinted pill (`bg-white text-[#0059b5] shadow-sm font-bold` or `bg-[#059669] text-white`).

### Data Tables & OLAP Matrices
- **Accessible Scroll Container:** Wrapped in a keyboard-focusable scroll container (`role="region"`, `tabIndex={0}`) with sticky `<thead>` (`position: sticky; top: 0; z-index: 10; background: rgba(248, 250, 252, 0.95)`).
- **Row Styling:** `1px solid #f1f5f9` horizontal dividers, generous `14px 24px` cell padding, right-aligned numeric columns with `tabular-nums`, and soft row hover highlight (`#f8fafc`). Peak alert rows receive a warm crimson tint (`bg-rose-50/40 hover:bg-rose-50/70`).

---

## 5. Layout Principles & Viewport Budget

- **Desktop-First Bento Grid:** Designed for `1440px` reference viewports with a fixed `260px` sidebar and a fluid main canvas (`margin-left: 260px`, `padding: 32px`, `max-width: 1600px`).
- **12-Column Analytical Grid:**
  - **KPI Row:** 4 equal columns (`grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5`) or 5-column KPI strip on Analytics.
  - **Asymmetric Split Views:** `8 / 4` or `7 / 5` column splits pairing wide time-series/pivot visualizations on the left with stacked contextual impact cards (Holiday Lift, Weather Correlation, Top 5 Geographic Markets) or executive staffing directives on the right.
- **Whitespace Mandate:** Maintain `24px–28px` (`gap-6` to `gap-7`) between major analytical groups and `24px–32px` internal card padding so dense hospitality metrics remain effortless to scan.

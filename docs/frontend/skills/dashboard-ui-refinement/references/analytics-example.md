# Hotel Operations dashboard conventions

Use this reference with the parent SKILL.md when refining this repository. These
are the accepted conventions for Analytics, Reporting, and Demand Forecasting.
They describe how to work on a requested page; they do not authorize changing all
three pages together. A current user instruction overrides these defaults.

## Shared presentation

- Keep the existing editorial layout, flat surfaces, subtle dividers, theme tokens,
  and 4px control corners. Avoid adding decorative cards or repeated icons.
- Use Inter for headings, body copy, and business values. JetBrains Mono remains
  available for technical identifiers; it is not the preferred business font.
- Keep parallel page titles: Hotel Operations Analytics, Hotel Operations
  Reporting, and Hotel Operations Forecasting.
- The application header retains hierarchical breadcrumbs, the accessible sidebar
  toggle, and an icon-only theme toggle. Hide routine health/version telemetry,
  but preserve error and explicit demo notices.
- Primary sidebar names are Operations Analytics, Operations Reporting, and Demand
  Forecasting. Available destinations use primary text; only unavailable entries
  are gray, disabled, and accompanied by a lock.
- Peer page buttons have matching 112px widths and 32px heights, a soft blue-gray
  treatment, and the far-right position in the title row. Reporting orders its
  Print/Export actions before Analytics and Forecasting. Keep that DOM order.
- Reuse CompactFilter for comparable selects: 192px desktop width, 36px height,
  10px label gap, 24px horizontal group gaps, and 20px wrapped-row gaps. Mobile
  controls use the available width. Preserve full selected labels in tooltips.
- All visible copy, chart text, tooltips, weekdays, weather labels, directives,
  and export presentation use English. Preserve business codes and numeric data.

## Terminology

| Previous text | Preferred visible text |
| --- | --- |
| Weekly Reports (DO-R01) | Reporting |
| 7-Day Demand Forecast (DO-M01) | Forecasting |
| Multi-Dimensional OLAP Pivot Matrix | Operations breakdown |
| Date range | Period |
| Source market (Country) | Market |
| Holiday scope | Holidays |
| Primary chart measure | Metric |
| Full 2 Years with dates and count | All dates |
| Year 2016 / Year 2017 | 2016 / 2017 |
| Summer Peak 2016 | Summer 2016 |
| All Markets (Worldwide) | All markets |
| Weekday (Mon–Fri) / Weekend (Sat–Sun) | Weekdays / Weekends |
| Holidays only / Non-holidays only | Holidays / Non-holidays |
| Average daily rate (€) | ADR (€) |
| Swap rows and columns | Swap axes |

Remove development task codes from visible UI, not from API values, internal
identifiers, or engineering documentation. Market and currency codes remain valid.

## Detail typography

Use page-scoped detail classes rather than increasing all dashboard typography.
Keep page titles at 28–32px, KPI labels around 14px, and numeric KPIs around 32px.

| Region | Accepted treatment |
| --- | --- |
| Analytics details | 20px section titles; 14px body/table values; 13px table headings; 12px secondary text; 13px trend-axis labels |
| Reporting details | 20px section titles; 16px subsection titles; 14px body/table values; 13px table headings and workload-chart labels |
| Forecasting details | 20px section titles; 16px subsections; 14px body/table values; 13px column headings; 12px notes; 11px dense protocol metadata |

Use the existing analytics-reading-section, report-reading-section, and
forecast-reading-section boundaries. These names are implementation anchors, not
requirements to introduce a new styling system. Include HTML comparison bars and
canvas fonts when enlarging detail text. Keep print-table typography independent.

## Analytics

Route: `/analytics/operations`.

- Default Time grain is **Week**; Reset filters also restores Week. Retain Year,
  Quarter, Month, Week, and Day, native radio selection, keyboard operation, and
  existing drill-down/roll-up behavior. Pivot row grain is a separate choice.
- Keep the page title free of a repeated introductory/date line. Period selection
  belongs in the controls.
- KPI cards remain minimal label/value/unit groups. A detail-font request does not
  authorize enlarging these KPIs or adding their unused supporting props to the UI.
- Operations breakdown uses external Rows, Columns, and Metric labels and has no
  redundant explanatory subtitle. Preserve the distinction between Market and
  Day type / holiday.
- Start all historical pivot rows collapsed. Do not automatically highlight or
  expand an old peak. Preserve user expansion, totals, child rows, and Swap axes.
- Trend, pivot, and impact requests remain independent. Changing local pivot
  controls must preserve the trend canvas, its geometry, and its loading state.
  Shared dates refresh the sections that actually depend on those dates.
- Existing trend/KPI filters and pivot/context filters have different scopes.
  A visual-only task must not silently unify those queries. Report a mismatch and
  change it only within an authorized behavior fix.
- Demand by holiday status uses Holidays and Non-holidays, with approximately 20px
  vertical padding and a minimum 104px row height.
- Dense weekly axis labels use measured widths, a visible gap, endpoint clamping,
  and reserved space for the last date. Never force the last tick on top of the
  previous one. Recompute after resizing or toggling the sidebar.

## Reporting

Route: `/reports/operations`.

- Keep Combined, Weekly demand, and Capacity summary as concise visible choices;
  preserve their existing internal values. Keep period and arrival-day filters.
- Hide the report metadata panel on screen. Retain that panel only for Print
  report: hotel/report identity, actual date range, timezone, selected day type,
  available-day count, guest coverage, publication time, and available data version.
  Do not restore the panel as part of a general dashboard cleanup.
- Keep Period summary visually aligned with Analytics: labels, primary values,
  optional units, responsive columns, and subtle desktop dividers. Do not add
  per-card average lines, explanatory subtext, verification badges, or a repeated
  calculation caption.
- Peak arrival date stays on one line and has visual weight comparable to the
  adjacent numeric KPIs. Allow the last desktop column extra width and use local
  responsive date sizing; preserve the year and avoid overflow.
- Keep Daily demand before Historical workload in Combined view. Supporting table
  columns remain available through the existing control and CSV.
- Historical summary, daily table, workload groups, planning considerations, and
  demand export use the same displayed rows after the arrival-day filter. Compute
  weighted averages from valid numerators/counts. Missing values remain unknown.
- Weekends mean Saturday–Sunday. Holidays overlap weekday/weekend groups; explain
  that the three group totals are not additive.
- Distinguish arrival-date stay-night workload from in-house occupancy. Do not infer
  occupied rooms, inventory, staffing counts, or breakfast headcount from arrivals.
- Forecasts use the selected period end as cutoff and require seven consecutive
  next-day dates. Their scope is all arrival days and is labeled separately from
  the historical day filter. Show an unavailable state for unsupported cutoffs;
  keep the historical report usable and do not substitute a different demo period.
- Export demand CSV for the displayed daily rows; export capacity CSV for the
  capacity view. Combined view may expose both explicitly named actions. Preserve
  active date/day-type context in filenames and relevant report metadata.
- Keep loading, error/retry, invalid-range, empty-data, and incomplete-week states.
  Disable unavailable actions. Do not display a fixed reconciliation claim as proof
  that a live or filtered result was verified.
- Scope print styles to Reporting. Hide navigation/controls, use the named A4
  landscape page layout, repeat table headings, and fit all visible columns.

## Demand Forecasting

Route: `/dss/demand-forecast`.

- A request for larger lower-section text targets Demand outlook, Weekly
  allocation, Demand insights, Daily forecast, and Model and policy evaluation.
  Preserve the top filters, page title, KPI values, and data/model behavior unless
  the user requests their modification too.
- Preserve cutoff/model/budget choices, relative allocation units, thresholds,
  supported insights, model protocols, and the collapsed evaluation disclosure.
- Keep forecast, actual/backtest observations, and historical reference signals
  distinguishable. Do not imply that forecasts are actuals or that missing
  observations, thresholds, scores, or demand classifications are zero/normal.
- Retain metric units and protocol/population explanations needed to interpret
  model and allocation scores. Typography cleanup is not permission to remove them.
- Enlarge canvas labels along with surrounding HTML. Use the shared axis-label
  layout to reduce date-label density at narrow widths without losing data points.

## Implementation anchors

Paths are relative to the repository root:

- `frontend/DESIGN.md`: editorial design direction and theme tokens.
- `frontend/src/pages/Analytics/Operations/OperationsAnalyticsPage.jsx`: initial
  grain, reset, trend filters, pivot controls, drill-down, and detail sections.
- `frontend/src/pages/Reports/Operations/OperationsReportsPage.jsx`: report modes,
  print-only context, minimal KPI strip, table, workload, and forecast scope.
- `frontend/src/pages/DSS/DemandForecast/`: forecast page and lower-section modules.
- `frontend/src/components/layout/Header.jsx` and `Sidebar.jsx`: shared application
  shell. `DashboardHeader.jsx` currently composes Reporting's title/actions.
- `frontend/src/components/filters/CompactFilter.jsx` and `SegmentedControl.jsx`:
  consistent filter treatments and native radio semantics.
- `frontend/src/components/kpi/KpiCard.jsx`: minimal shared KPI rendering.
  `frontend/src/pages/Reports/Operations/ReportKpi.jsx`: supporting copy for report
  forecast cards; it is not used for Period summary.
- `frontend/src/components/charts/TrendChart.jsx`: canvas text and comparison bars.
  `frontend/src/components/charts/axisLabels.js`: measured non-overlapping ticks.
- `frontend/src/lib/reporting.mjs`: filtering, weighted summaries, forecast-date
  validation, and capacity CSV. `frontend/src/services/reportingApi.js`: daily CSV.
- `frontend/src/index.css`: page-scoped detail typography and Reporting print CSS.

Inspect current callers before editing these anchors; their existence does not
make a shared change appropriate for every page.

## Verification

- Inspect affected views at desktop and narrow widths in supported themes. Check
  date KPIs, rightmost navigation, wrapped filters, table scrolling, and axis ends.
- Exercise Week defaults/reset, drill/roll-up, pivot expansion/transpose, and local
  loading independence when those behaviors are affected.
- For Reporting behavior changes, compare filtered KPI/table/export results and
  weighted averages against the API for the same dates and day type. Check an
  incomplete week, a reversed range, and unavailable forecasts when relevant.
- Verify screen-hidden metadata and print-visible metadata separately. A compiled
  stylesheet is not evidence that print pagination has been visually checked.
- Build with `npm run build` from `frontend`. If dependencies are available only in
  the running frontend container, use `docker compose exec -T frontend npm run build`.
- Run relevant existing tests with `node --test frontend/tests/*.test.mjs` from the
  repository root. Set DWDSS_API_BASE_URL to the local backend URL when live API
  integration checks are intended; otherwise report those checks as skipped.
- Geometry tests are in `frontend/tests/axisLabels.test.mjs` and
  `frontend/tests/forecastGeometry.test.mjs`; report behavior tests are in
  `frontend/tests/reporting.test.mjs`.
- If a Docker development server serves stale code after Windows bind-mount edits,
  inspect the active source and service before reloading only the frontend within
  the existing authorization. Do not rebuild the data pipeline or restart the
  database as part of a typography or navigation change.

This reference specifies target behavior and verification methods, not a record
that every listed check was performed in a previous task.

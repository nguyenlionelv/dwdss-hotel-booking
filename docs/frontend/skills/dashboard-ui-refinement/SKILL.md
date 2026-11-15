---
name: dashboard-ui-refinement
description: Refine existing analytics, reporting, and forecasting dashboards with consistent navigation, Inter typography, compact filters, readable charts and tables, and screen/print layouts. Preserve page scope, data semantics, and independent interactions.
---

# Dashboard UI refinement

Apply the user's dashboard preferences to the requested screens. This skill is
independent of a particular business domain, framework, route, or component name.
Its style defaults reflect the user's preferences and can be overridden by their
current instructions or an explicitly chosen product design system.

The general visual treatment is defined here. No prior conversation or screenshot
is required. In the Hotel Operations repository, also read
[Hotel Operations conventions](references/analytics-example.md) for the accepted
page-specific defaults, source locations, and verification commands. Do not apply
those domain-specific defaults to unrelated products.

## Establish the scope

Inspect the target screens, existing design tokens, and shared components before
editing. Identify which pages are requested and where shared changes will appear.
Refine the existing implementation; retain routes, query values, available choices,
calculations, and interactions unless a behavior change is also requested.

- Applicability to three dashboard types does not authorize editing all three
  pages. A Reporting request targets Reporting; extend it only when the user names
  another page or requests a shared change.
- Check the working tree before editing. Preserve changes that predate the task.
  If the user narrows the scope or asks for a rollback, reverse only this task's
  changes rather than restoring whole files from Git.
- Scope page-specific typography, KPI variants, and print CSS to the target page.
  A shared component change must preserve behavior in its other callers; prefer
  an optional prop or a local wrapper when the requirement is page-specific.

## Concise content and navigation

- Name a page or section for its business content, rather than its implementation
  technique or task identifier. Use short labels that remain accurate when users
  change the metric or dimension.
- Remove development task codes from visible navigation, buttons, headings,
  tooltips, and accessible names. Preserve meaningful business codes, recognized
  metric abbreviations, and internal identifiers in code or documentation.
- Give destination links concise names and actions clear verbs. Preserve their
  destinations and semantics. Do not add explanatory subtitles to navigation.
- Remove repeated introductions and descriptions that only paraphrase a heading.
  Retain explanations needed to interpret a metric, scope, unit, or uncertainty.
- Default user-facing copy to English and sentence case. Respect an explicitly
  chosen product language. Keep controls, tooltips, states, accessible names, and
  locale-generated dates consistent with that language.
- Treat API/database labels, chart canvas text, tooltips, recommendations, demo
  fixtures, and export content as user-facing copy too. Inspect populated data
  rather than only JSX literals. Translate presentation labels at their source
  or a shared localization boundary; preserve grouping conditions and numeric
  values. Check weather conditions, weekday names, and operational directives
  explicitly. An English page heading alone does not verify language consistency.

Examples of concise naming, to adapt to the actual content:

| Verbose text | Concise text |
| --- | --- |
| Weekly Reports (DO-R01) | Reporting |
| 7-Day Demand Forecast (DO-M01) | Forecasting |
| Multi-Dimensional OLAP Pivot Matrix | Operations breakdown |
| Source market (Country) | Market |
| Primary chart measure | Metric |
| All Markets (Worldwide) | All markets |
| All days (Weekday + Weekend) | All days |

These are examples, not required domain terminology. Remove a table section's
subtitle when it only restates that table's purpose; do not replace it with a
different redundant explanation.

For peer dashboard destinations, prefer matching one-word labels such as Reporting
and Forecasting. Use matching 112px widths and 32px heights, with the same surface,
border, text color, and hover treatment rather than making one green and primary.
Use a soft blue-gray treatment for these peer actions: pale slate-100 fill,
slate-200 border, and slate-700 text in light mode; muted slate-800 fill,
slate-600 border, and slate-200 text in dark mode. Hover gently deepens the fill.
Place peer navigation at the far right of the page-title row. When report actions
are present, order them before the destination pair: Print/Export, then Analytics
and Forecasting. Keep keyboard order consistent with the visible order, and retain
right alignment when the groups wrap.

Use content-based comparison titles such as `Demand by holiday status`, with clear
`Holidays` and `Non-holidays` row names. Allow approximately 20px vertical row
padding so descriptive text and metrics have room to breathe.

## Dashboard typography

Use a modern sans-serif family for both text and business numbers. Inter is the
preferred starting point; an equivalent existing family can be used when the
product specifies one. Load the required font weights explicitly.

- Page titles: approximately 28–32px, weight 700, tight tracking around `-0.025em`.
- Section headings: approximately 18px, weight 600.
- KPI labels: approximately 14px, weight 500, primary text color. Allow meaningful
  labels to wrap rather than truncating them. Align labels and values consistently.
- KPI numbers: approximately 32px, weight 700, tracking around `-0.025em`, and
  `font-variant-numeric: tabular-nums`. Adapt size to each cell's available width;
  long dates may need a wider column and modest responsive sizing to stay on one line.
- Supporting text and units: approximately 12–14px, weight 400, secondary gray.
- Business values in tables and charts use the same sans-serif family. Retain
  monospace for actual code and technical identifiers, not as the default for
  financial values, guest counts, percentages, or forecast scores.

For requests to make the lower sections slightly larger, use the following detail
scale within the requested page. Preserve the page title, top toolbar, and large
KPI values unless the user also asks to change them.

| Detail element | Preferred size |
| --- | --- |
| Section heading | 20px, weight 600 |
| Subsection heading | 16px, weight 500–600 |
| Table values, comparison labels, and explanatory text | 14px |
| Table column headings | 13px |
| Small notes and secondary identifiers | 12px; 11px for dense protocol metadata |
| Chart axes and date labels | 12–13px |

Use approximately 1.5 line height for supporting text. Include HTML comparison bars,
tooltips, and canvas-rendered text in a typography change; CSS cannot resize text
already drawn into a canvas. Keep the information hierarchy rather than enlarging
every descendant by the same amount.

This typography treatment does not require copying a reference dashboard's cards,
icons, colors, or layout. Keep the existing information and business behavior.

## Compact, consistent filters

Use one shared visual treatment for comparable filters across toolbars, tables,
and analysis sections. Reuse an existing component when possible.

Baseline styling for this user's dashboards:

| Property | Default |
| --- | --- |
| Label placement | Above the control |
| Label text | Short, regular weight, secondary text color |
| Label-to-control gap | 10px; keep a clear separation between caption and selected value |
| Filter group spacing | 24px horizontally, 20px between wrapped rows |
| Separate control rows | Approximately 24px between a mode/time selector and field filters |
| Control height | 36px on desktop; adapt for touch usability |
| Control text | Readable 13–14px, regular weight |
| Corner radius | 4px |
| Surface and border | Theme-aware neutral surface and subtle border |
| Focus | Visible keyboard focus, distinct from selected state |

Shorten selected values as well as labels. Put repeated date ranges, counts, and
explanations in appropriate page context or expanded options. Keep essential
distinctions and units such as `%` and currency symbols.

Use the same 192px desktop width for all Analytics filters, including Metric and
the breakdown controls. On mobile, use the available row width consistently.
Reserve space for text, padding, and the dropdown arrow; retain the full selected
label in the control's tooltip for long names. Let groups wrap without overlap.

For dimension-based tables, use labels such as `Rows`, `Columns`, and `Metric`
above the controls, with only the selected value inside. Use the same terminology
for the same concept across the page. Do not give an ordinary selector a permanent
accent border that resembles keyboard focus.

Visual consistency does not mean every filter has the same data scope. Preserve
existing filter independence, reset behavior, and expand/transpose interactions.
Keep requests and loading states independent for independent sections. Changing a
table's local Rows/Columns/Metric controls must not refetch, replace with a skeleton,
remount, or move an unaffected chart above it. Retain the table while its own data
updates and expose its busy state locally. Shared date-range changes should still
refresh all sections that depend on the range; stale responses must not overwrite
newer selections.
If a scope mismatch is found, report it; changing calculations or query scope is
a separate task unless the user has authorized that change.

## Neutral segmented selectors

Use a compact, flat group for short mutually exclusive choices such as Year,
Quarter, Month, Week, and Day.

- Outer container: neutral primary surface, subtle 1px border, 4px corner radius,
  and 2px inset padding. Size it to its contents instead of stretching the row.
- Total control height: 36px, matching the filter inputs. Items are 30px high
  inside the 2px padding and 1px border, with 12px horizontal padding, 3px corners,
  and 14px regular text. The Time grain label also uses 14px. Reduce item padding
  to 7px on narrow screens to keep all five options on one row without clipping.
- Inactive choices: transparent surface and secondary text. Selected choice:
  subtle neutral gray surface, primary text, and medium weight. No green or brand
  fill, raised white tile, shadow, underline, or large pill-shaped corners.
- Use corresponding neutral theme tokens in dark mode. Keep a visible neutral
  keyboard focus outline and programmatically exposed selected state.
- Preserve all choices, query values, and reset/drill-down behavior. A time filter
  remains a single-choice filter, not navigation.

## Sidebar behavior and navigation availability

Support an accessible desktop sidebar toggle. Collapse/expand the sidebar and
update the content offset together; charts and tables must adapt to the newly
available width without a reload. Keep sidebar state across internal navigation.
On mobile, retain a separate slide-out navigation menu that closes after choosing
a destination and supports Escape and focus return.

In Hotel Operations, the primary destination names are Operations Analytics,
Operations Reporting, and Demand Forecasting. All available destinations use the
normal primary text color (black in light mode, readable light text in dark mode),
including inactive links. Indicate the current page with a subtle neutral surface
or marker instead of green text. Only unavailable/locked destinations are gray;
mark them as disabled and show a lock icon rather than an active-looking link.

## Shared header and page titles

Retain useful hierarchical breadcrumbs such as `Product > Section > Page` in the
application header, alongside the theme toggle. Remove duplicate location/build
metadata and routine health indicators, not the navigation hierarchy.
Apply the same header component across Analytics, Reporting, and Forecasting.
Show only the sun/moon icon on the theme toggle; retain its accessible name and
tooltip, without visible Dark/Light text. Use concise parallel page titles, such
as Hotel Operations Analytics, Hotel Operations Reporting, and Hotel Operations
Forecasting. Do not place a repeated date range or introductory subtitle above
the Analytics page title; keep date selection in the filter controls.

Keep connection errors, demo-data notices, and relevant data-state messages
available. Removing routine header telemetry does not remove health checks or
error handling. Retain essential workspace/account controls in products that need
them; the simplified header is not permission to remove unrelated functionality.

## Minimal KPI summaries and print layouts

For minimal summaries matching Analytics, render each KPI as a label, value, and
optional unit. Omit per-card explanatory lines, decorative badges, and repeated
summary captions. Preserve the metric calculations and essential error/coverage
notices. Do not remove supported planning explanations from other sections merely
because the summary is minimal.

Keep date-valued KPIs visually comparable with adjacent numeric values. Preserve
the full date on one line; provide enough column width and use responsive sizing
instead of making the date conspicuously smaller or removing the year. Apply such
an adjustment locally rather than changing date typography across every page.

When metadata is requested only in Print report, retain it in the document but
hide its entire wrapper in screen media, including its layout space. Show it in
print media with the report identity, period, active filters, coverage, update
time, and available version. This does not authorize hiding connection failures,
demo notices, invalid ranges, incomplete-period warnings, or empty states.

Keep print styles page-scoped. Hide navigation and interactive controls, use a
readable light print surface, fit tables to the paper, repeat column headings,
and prevent clipped columns. Screen font increases must not override the smaller
print-table sizes. Do not claim a print preview was verified from a build alone.

## Historical breakdown tables

Historical breakdown tables should present periods neutrally. Do not automatically
highlight the largest historical period or expand a hardcoded old peak. Start with
rows collapsed and let users expand periods themselves. Preserve totals and the
subtle visual distinction between aggregate and child rows. Do not remove peak
indicators from unrelated views unless the user requests that change.

## Responsive charts and tables

For horizontal comparison charts, size the label, bar, and value regions to actual
content. Long labels must wrap without overlapping bars or values. At narrow
container widths, place the bar below a label/value row instead of forcing three
fixed columns. Prefer HTML/CSS for simple comparison bars so text remains readable
and available to assistive technology. Preserve values and relative bar scaling.
Let detail tables scroll within their own labeled region on small screens rather
than truncating names or causing the entire page to overflow.

For time-axis labels, measure text with the actual drawing font. Fit each label's
full bounding box inside the plot, keep a visible gap between labels, and reserve
space for the final date before placing intermediate labels. Do not append a final
label unconditionally after a fixed-stride loop: it can collide with the previous
tick or extend beyond the canvas. Show fewer complete labels on narrow plots;
retain underlying data points, tooltips, and drill-down behavior.

Recompute label placement when data, font size, container width, or sidebar width
changes. When changing a default time grain, align initial state and Reset filters
with that default while preserving the other grain choices and drill/roll-up rules.

## Verify the refinement

Inspect the affected screens at desktop and narrow widths, in supported light and
dark themes. Check readable selected values, consistent filter styling, wrapping,
navigation access, and the absence of leftover task codes or repetitive copy.
For axis changes, include a dense weekly series and inspect both endpoint labels.
For metadata changes, check screen and print separately.

Exercise affected choices, reset behavior, and any table operations. Verify
keyboard operation and that data still reaches the interface correctly. Run the
project's appropriate build/checks; use targeted behavioral checks rather than
adding tests that merely assert styling classes. Report what changed, what was
verified, and any unresolved issue outside the authorized presentation scope.

Use browser tooling when available, or the installed computer-use skill when it
is the appropriate supported fallback. Follow that skill's platform and tool
restrictions. If visual inspection is stopped or unavailable, report the specific
verification gap without treating it as a successful check.

Keep validation proportional to the change. A typography-only edit normally needs
a build and visual inspection; add behavioral tests for label placement, filter
scope, reconciliation, or export logic when those behaviors change. Distinguish
passed tests from skipped integration checks. Editing this skill alone does not
require restarting the application or rerunning the frontend test suite.

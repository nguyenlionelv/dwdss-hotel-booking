# Design System: Hotel Operations DSS

## Lumina Analytics — Anti-AI-Slop Design Guidelines

**Project ID:** `projects/16851751821645352227`  
**Domain:** Hospitality Data Warehouse & Decision Support System  
**Reference:** City Hotel — Lisbon, Portugal

---

## 1. Design Philosophy

### 1.1. Visual Direction

**Editorial Data Intelligence — Minimal, Functional, Data-Driven.**

Build a professional analytical interface inspired by editorial publications, financial research platforms, and enterprise data applications.

The interface must prioritize information hierarchy, data readability, and operational efficiency over decorative UI elements.

**Core principles:**

- **Content over decoration:** Every element must communicate information or provide functionality.
- **Layout over containers:** Use spacing, alignment, typography, and subtle dividers instead of wrapping everything in cards.
- **Data over decoration:** Charts and metrics are the primary visual elements.
- **Restraint over repetition:** Avoid repetitive colors, icons, badges, shadows, and rounded components.
- **Concise communication:** UI copy must be short, specific, and actionable.

### 1.2. Anti-AI-Slop Rules

Strictly avoid the following common AI-generated design patterns:

- Excessive card grids, Bento layouts, and nested containers.
- Rounded cards with `rounded-2xl`, `rounded-3xl`, or larger radii.
- Gradient backgrounds, decorative glows, and unnecessary glassmorphism.
- Repetitive blue-purple gradients and excessive emerald accents.
- Decorative icons inside every heading or metric.
- Excessive uppercase labels and letter spacing.
- Unnecessary descriptions, subtitles, and explanatory paragraphs.
- Repeated pill badges for ordinary information.
- Artificially symmetrical layouts when the content requires different visual priorities.
- Decorative charts that do not communicate meaningful data.

**Design test:** If removing an element does not reduce information clarity or functionality, remove it.

---

## 2. Color System

### 2.1. Core Palette

Use a restrained, neutral palette. Colors must have distinct semantic purposes.

| Role            | Color     | Usage                               |
| --------------- | --------- | ----------------------------------- |
| Main background | `#FAFAF8` | Overall workspace                   |
| Primary surface | `#FFFFFF` | Main content areas                  |
| Primary text    | `#252525` | Headlines and important values      |
| Secondary text  | `#666666` | Descriptions and supporting data    |
| Muted text      | `#999999` | Timestamps and metadata             |
| Divider         | `#E5E5E0` | Section separators                  |
| Primary accent  | `#315B52` | Selected states and primary actions |

### 2.2. Data Visualization Colors

Use a limited categorical palette for charts. Each color must represent a distinct data series.

| Data category | Color     | Purpose               |
| ------------- | --------- | --------------------- |
| Series 1      | `#315B52` | Primary data          |
| Series 2      | `#C58B55` | Secondary comparison  |
| Series 3      | `#547A9B` | Additional comparison |
| Series 4      | `#9B7185` | Additional comparison |
| Series 5      | `#92958B` | Supporting data       |

Semantic status colors:

- **Success:** `#477A61`
- **Warning:** `#C58B35`
- **Critical:** `#B64C43`

Rules:

- Do not use every color in every chart.
- Use neutral grey for secondary or historical data.
- Reserve accent colors for important series and meaningful comparisons.
- Maintain consistent color-to-category mapping across the application.
- Never use color as the only means of communicating status.

### 2.3. Background Rules

- Prefer solid backgrounds.
- Avoid gradients and decorative background patterns.
- Avoid placing every section inside a white card.
- Use whitespace and thin dividers to separate content.
- Dark backgrounds are reserved for exceptional use cases, not ordinary dashboard sections.

---

## 3. Typography

### 3.1. Font Families

- **Primary:** Inter
- **Alternative:** IBM Plex Sans
- **Technical identifiers:** JetBrains Mono

Use one primary font throughout the application. Do not mix multiple display fonts.

### 3.2. Type Scale

| Element         |    Size | Weight |
| --------------- | ------: | -----: |
| Page title      | 28–32px |    650 |
| Section heading | 18–20px |    600 |
| Metric value    | 28–36px |    600 |
| Body text       |    14px |    400 |
| Supporting text | 12–13px |    400 |
| Technical data  | 12–13px |    400 |

Typography rules:

- Use sentence case instead of excessive uppercase labels.
- Avoid unnecessary bold text.
- Keep line heights comfortable and consistent.
- Use tabular numerals for metrics, financial values, and time-series data.
- Use monospace only for SQL identifiers, technical values, and system metadata.

---

## 4. Layout & Composition

### 4.1. General Layout

Use an editorial, section-based layout rather than a card-based dashboard.

- Reference viewport: `1440px`.
- Sidebar width: `240px`.
- Main content: fluid width.
- Main content padding: `32px–40px`.
- Maximum content width: `1600px`.
- Section spacing: `32px–48px`.

### 4.2. Section-Based Composition

Organize the interface using:

1. Clear section headings.
2. Horizontal dividers.
3. Consistent alignment.
4. Intentional whitespace.
5. Asymmetric content distribution.

Do not wrap every chart, KPI, filter, or text block in an individual card.

Example composition:

```text
--------------------------------------------------
Page Title                         Date Selection
Short contextual information
--------------------------------------------------

KEY PERFORMANCE INDICATORS

  Total Bookings      Revenue       Occupancy
  12,450              €1.25M        78.4%

--------------------------------------------------

REVENUE PERFORMANCE

  [Large Canvas Chart]

  Supporting metrics / observations

--------------------------------------------------

OPERATIONAL ANALYSIS

  [Wide Visualization]     [Compact Insight]

--------------------------------------------------
```

### 4.3. KPI Presentation

Display KPIs as typographic data groups rather than individual cards.

- Large numerical values.
- Small descriptive labels.
- Optional percentage changes.
- Thin vertical or horizontal dividers when necessary.
- No decorative icon containers.
- No unnecessary background colors.

Only emphasize metrics that require immediate attention.

### 4.4. Navigation

**Sidebar:**

- Fixed width: `240px`.
- Solid background.
- Thin right divider.
- Simple text-based navigation.
- Active state indicated by text weight and a subtle accent indicator.
- Avoid icon-heavy navigation.

**Topbar:**

- Height: `56px–64px`.
- Solid background.
- Minimal bottom divider.
- Display only essential context: hotel, date range, system status, and user controls.
- No glassmorphism or excessive contextual pills.

---

## 5. Data Visualization

### 5.1. Rendering Requirements

Use HTML Canvas-based chart rendering for analytical visualizations, preferably through a suitable charting library.

Canvas charts must have:

- Clear axis labels.
- Readable tick values.
- Distinct series colors.
- Visible legends where needed.
- Tooltips for detailed values.
- Consistent scales.
- Appropriate number formatting.
- Responsive dimensions.

Do not use decorative charts merely to fill empty space.

### 5.2. Chart Design

**Line charts**

- Use for revenue trends, occupancy, and demand forecasting.
- Use clearly differentiated series.
- Avoid excessive gridlines.
- Highlight important dates and anomalies.

**Bar charts**

- Use for category comparisons, geographic markets, and operational performance.
- Prefer horizontal bars when category names are long.
- Display values directly when practical.

**Area charts**

- Use sparingly for cumulative trends and forecast intervals.
- Avoid excessive opacity and gradient fills.

**Heatmaps**

- Use for weekday/weekend patterns, seasonal demand, and operational intensity.
- Provide a clear color scale and readable labels.

### 5.3. Chart Color Rules

- Primary series: muted green.
- Comparison series: muted blue or ochre.
- Historical/reference series: neutral grey.
- Forecast series: distinguish using a dashed line or another visual treatment.
- Critical thresholds: muted red.

Do not assign random colors to datasets on each render.

### 5.4. Data Tables

Avoid using tables as the default layout for presenting information.

Prefer:

- Horizontal bar charts for rankings.
- Heatmaps for multidimensional comparisons.
- Canvas-based visualizations for trends and distributions.
- Aligned typographic rows for compact metric summaries.
- Section-based layouts for related information.

Use actual data tables only when users need precise row-by-row inspection, sorting, or comparison.

When necessary:

- Keep borders minimal.
- Use clear column alignment.
- Right-align numeric values.
- Use tabular numerals.
- Avoid decorative backgrounds and excessive rounded containers.

---

## 6. Component Styling

### 6.1. Borders & Containers

- Default border radius: `0px–4px`.
- Buttons and input controls: maximum `4px–6px`.
- Avoid large rounded card containers.
- Use `1px solid #E5E5E0` for structural dividers.
- Avoid shadows unless elevation is functionally necessary.

### 6.2. Buttons

- Primary: solid `#315B52`, white text.
- Secondary: transparent background, neutral border.
- Tertiary: text-only action.
- Avoid oversized buttons and pill-shaped buttons.
- Use concise action labels.

### 6.3. Inputs & Filters

- Simple rectangular input fields.
- Minimal borders.
- Clear labels.
- Consistent heights.
- Avoid nesting filters inside decorative toolbar cards.

### 6.4. Status Indicators

Use compact text labels with small semantic indicators.

Examples:

- `Healthy`
- `Warning`
- `Critical`
- `Forecast`
- `Verified`

Do not turn every status into a large colorful badge.

---

## 7. Content & Microcopy Rules

### 7.1. Writing Style

All UI content must be concise, factual, and directly relevant to the user's task.

**Forbidden:**

- Generic marketing language.
- Unnecessary introductions.
- Repeating information already visible in the interface.
- Descriptions that explain obvious functionality.
- Artificial AI-generated insights without supporting data.

**Preferred:**

| Avoid                                  | Prefer               |
| -------------------------------------- | -------------------- |
| Your hotel performance at a glance     | Hotel Performance    |
| Explore your revenue trends            | Revenue Trends       |
| Discover valuable operational insights | Operational Insights |
| Your system is running smoothly        | System Healthy       |
| Here is an overview of your bookings   | Bookings             |

### 7.2. AI-Generated Text

If the application generates analytical summaries:

- State the finding first.
- Include supporting numerical evidence.
- Explain the operational implication only when relevant.
- Avoid generic recommendations.
- Never invent explanations unsupported by the dataset.

Example:

**Bad:**  
"Your hotel is experiencing an impressive increase in booking performance, demonstrating strong operational efficiency."

**Good:**  
"Bookings increased 12.4% compared with the previous month."

---

## 8. Responsive Design

- Desktop: prioritize analytical density and wide visualizations.
- Tablet: reduce sidebar width and reorganize multi-column sections.
- Mobile: stack content vertically and simplify chart legends.
- Charts must resize without losing labels or readability.
- Avoid horizontal overflow except for genuinely wide data tables.

---

## 9. Final Design Constraints

Every implementation must follow these rules:

1. No excessive cards or Bento grids.
2. No decorative gradients or glassmorphism.
3. No unnecessary rounded containers.
4. No repetitive blue/green color combinations.
5. No decorative icons without functional meaning.
6. No redundant descriptions or AI-generated filler text.
7. No tables when charts or structured layouts communicate better.
8. Canvas-based rendering for analytical charts.
9. Consistent color mapping across all visualizations.
10. Use typography, spacing, and dividers to establish hierarchy.
11. Prioritize actual data over decorative UI.
12. Preserve accessibility, contrast, and readability.

**Final principle: Design the interface around the information, not around the components.**

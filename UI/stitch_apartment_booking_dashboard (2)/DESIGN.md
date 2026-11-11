---
name: Hospitality Operations Console
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#45474c'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#75777d'
  outline-variant: '#c5c6cd'
  surface-tint: '#545f73'
  primary: '#091426'
  on-primary: '#ffffff'
  primary-container: '#1e293b'
  on-primary-container: '#8590a6'
  inverse-primary: '#bcc7de'
  secondary: '#4b41e1'
  on-secondary: '#ffffff'
  secondary-container: '#645efb'
  on-secondary-container: '#fffbff'
  tertiary: '#00190e'
  on-tertiary: '#ffffff'
  tertiary-container: '#00301f'
  on-tertiary-container: '#24a375'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d8e3fb'
  primary-fixed-dim: '#bcc7de'
  on-primary-fixed: '#111c2d'
  on-primary-fixed-variant: '#3c475a'
  secondary-fixed: '#e2dfff'
  secondary-fixed-dim: '#c3c0ff'
  on-secondary-fixed: '#0f0069'
  on-secondary-fixed-variant: '#3323cc'
  tertiary-fixed: '#85f8c4'
  tertiary-fixed-dim: '#68dba9'
  on-tertiary-fixed: '#002114'
  on-tertiary-fixed-variant: '#005137'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  headline-xl:
    fontFamily: Plus Jakarta Sans
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-xl-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.015em
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.015em
  headline-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 26px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 15px
    fontWeight: '600'
    lineHeight: 22px
    letterSpacing: -0.005em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  tabular-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
  tabular-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
  code-sm:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: -0.01em
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.03em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-lg: 1.5rem
  margin: 1rem
  margin-md: 1.5rem
  margin-lg: 2rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
---

## Brand & Style

This design system serves property managers, booking operators, and developers maintaining high-turnover apartment portfolios. The interface merges the quiet poise of a boutique hospitality back-office with the precision and functional transparency of a developer operations console. 

The aesthetic is grounded in modern architectural clarity:
- **Clean Structure & Air:** Generous, organized whitespace framed by warm architectural neutrals (sand, stone, and slate), avoiding harsh digital starkness.
- **Operator-Grade Legibility:** Uncluttered layouts prioritize high-density occupancy calendars, reservation logs, and live availability over decorative illustration.
- **Operational HUD Touches:** Technical clarity via discrete REST endpoint indicators (`GET /api/v1/bookings`), HTTP status badges, and database health monitors (SQLite sync indicators, WAL checkpoints, and latency pings) seamlessly woven into operational views.
- **Calm Authority:** High contrast where decisions matter (bookings, cancellations, overcapacity alerts), but tranquil and low-friction during continuous day-to-day administrative use.

## Colors

The color palette establishes an executive, architectural baseline balanced with precise state indicators for high-stakes operational workflows.

### Primary & Slate Foundation
- **Primary (`#1E293B`):** Deep slate grounding navigation rails, top-level headings, primary button fills, and structural frames.
- **Accent Indigo (`#4F46E5`):** Expressive interactive highlight for active selection tabs, pagination controls, focused input outlines, and primary links.

### Status & State Semantics
- **Success & Availability (`#059669` / `#10B981`):** Applied to vacant units, confirmed check-ins, positive payout status, active Flask route states, and clean SQLite health badges.
- **Warning & Capacity Notice (`#D97706` / `#F59E0B`):** Flags pending payments, expiring reservation holds, high-occupancy thresholds, and API rate-limit throttles.
- **Danger & Destructive (`#E11D48` / `#BE123C`):** Reserved for overlapping booking conflicts, direct cancellations, refund overrides, failed background tasks, and database lock exceptions.

### Neutral & Surface Hierarchy
- **Canvas Base:** `#F8FAFC` (Slate 50) delivers an eye-friendly, warm-tinted working backdrop.
- **Sub-canvas / Panel Rails:** `#F1F5F9` (Slate 100) provides crisp structural separation for toolbars and table filter bars.
- **Surface Cards & Popovers:** Pure `#FFFFFF` elevates booking drawers, data tables, and modal dialogs.
- **Dividers & Structural Borders:** `#E2E8F0` (Slate 200) maintains crisp tabular boundaries without clutter.
- **Body & Secondary Copy:** Text steps down from `#0F172A` (primary text) to `#475569` (body) and `#64748B` (metadata, endpoint paths, timestamps).

## Typography

The typographic hierarchy enforces immediate legibility through distinct structural roles:

- **Headlines (Plus Jakarta Sans):** Introduces warm, welcoming curves to dashboard view titles, property portfolio headers, and reservation aggregate summaries, offsetting the density of operational tables.
- **Body & Tabular Interface (Inter):** Serves as the functional backbone. Crucially, all table cells displaying nightly rates, totals (e.g., `€1,420.00`), stay durations (`4 nights`), guest counts, and dates must enforce `font-feature-settings: "tnum" 1, "cv05" 1` to guarantee precise visual column alignment.
- **HUD & API Telemetry (JetBrains Mono):** Applied selectively to technical breadcrumbs, SQLite transaction logs, query response latencies (`12ms`), and REST route annotations (`POST /api/v1/apartments/:id/book`).

## Layout & Spacing

The layout model is a flexible desktop-first dashboard structure tailored to information-dense hospitality monitoring.

### Grid & Layout Structure
- **Persistent Side Rail:** Fixed `240px` navigation on desktop (`>=1024px`), collapsible to an icon-only `64px` rail on medium viewports (`768px - 1023px`), and hidden behind an off-canvas drawer on mobile (`<768px`).
- **Main Canvas:** A fluid 12-column layout with a maximum container width of `1600px` to maintain comfortable eye scanning across wide booking grids.
- **Data Densities:**
  - Standard view uses `space-md` (`1rem`) row height padding for standard list inspections.
  - Compact view toggles `space-sm` (`0.5rem`) for high-throughput availability matrix views.

### Breakpoints & Adaptive Reflow
- **Desktop (1024px+):** Multi-pane split views: Left listing/calendar view (8 columns) paired with real-time reservation detail drawer (4 columns).
- **Tablet (768px - 1023px):** Columns reflow to stacked view; table horizontal scrolling enabled with fixed sticky apartment name/ID columns.
- **Mobile (<768px):** Multi-column booking grids transition to card-based ledger items with sticky bottom action sheets for reservation check-ins and edits.

## Elevation & Depth

Visual hierarchy uses a refined hybrid of crisp 1px borders and soft ambient micro-shadows, maintaining a clean slate feel that minimizes visual fatigue.

### Surface Tiers
- **Tier 0 (Base Canvas):** `#F8FAFC` flat surface. No shadow, no border.
- **Tier 1 (Surface Cards & Grids):** `#FFFFFF` background with a crisp border (`1px solid #E2E8F0`) and an ambient shadow: `box-shadow: 0 1px 3px 0 rgba(15, 23, 42, 0.04), 0 1px 2px -1px rgba(15, 23, 42, 0.04)`.
- **Tier 2 (Hovered Rows & Active Unit Cards):** `#FFFFFF` with `box-shadow: 0 4px 6px -1px rgba(15, 23, 42, 0.06), 0 2px 4px -2px rgba(15, 23, 42, 0.04)` and border shifted to `#CBD5E1`.
- **Tier 3 (Modals, Slide-over Drawers, & Dropdowns):** `#FFFFFF` with `box-shadow: 0 20px 25px -5px rgba(15, 23, 42, 0.08), 0 8px 10px -6px rgba(15, 23, 42, 0.04)`. Borders remain razor-sharp at `1px solid #E2E8F0`.

### Developer/Telemetry Indicators
- Technical HUD panels (e.g., SQLite connection pools, Flask route debuggers) sit recessed within panels using `background: #F1F5F9`, an inset outline `inset 0 0 0 1px #E2E8F0`, and zero external elevation.

## Shapes

The design system adopts a balanced **Rounded (`2`)** curvature scale, pairing soft modern hospitality ergonomics with disciplined structural rectangles.

- **Base Components (Inputs, Buttons, Badges):** Standard `0.5rem` (`rounded`, 8px) corner radius. This softens operational tools while keeping them firm and precise.
- **Containers & Tables (Cards, Modals, Flyout Panels):** Standard `1rem` (`rounded-lg`, 16px) corner radius. Exterior table borders round at `16px` with inner header and row highlights clipped to match.
- **HUD Pills & Status Chips:** Fully pill-shaped (`9999px`) for micro-status indicators (e.g., `Confirmed`, `Vacant`, `Cleaned`) and technical status codes (`200 OK`, `409 Conflict`).

## Components

### Buttons
- **Primary:** Background `#1E293B`, text `#FFFFFF`, radius `0.5rem`, padding `0.5rem 1rem`. Hover: `#0F172A`. Active: `#334155`.
- **Secondary (Action):** Background `#4F46E5`, text `#FFFFFF`. Hover: `#4338CA`. Focused outline: `2px solid #818CF8` with `2px` offset.
- **Tertiary / Ghost:** Border `1px solid #E2E8F0`, background `#FFFFFF`, text `#334155`. Hover: `#F8FAFC` and border `#CBD5E1`.
- **Destructive:** Background `#E11D48`, text `#FFFFFF`. Hover: `#BE123C`. Used strictly for irrevocable booking deletions or unit deactivations.

### Status Chips & Badges
- **Confirmed / Available:** Background `#ECFDF5`, text `#065F46`, border `1px solid #A7F3D0`. Includes a 6px circular green status pip (`#10B981`).
- **Notice / Capacity Warning:** Background `#FFFBEB`, text `#92400E`, border `1px solid #FDE68A`.
- **Conflict / Cancelled:** Background `#FFF1F2`, text `#9F1239`, border `1px solid #FECDD3`.
- **API / Protocol Badge:** Font `JetBrains Mono`, text `11px`, background `#F1F5F9`, text `#475569`, border `1px solid #E2E8F0`. Displays HTTP verbs (`GET`, `POST`) and DB modes (`WAL`, `RO`, `RW`).

### Data Tables & Booking Grids
- **Header:** Background `#F8FAFC`, uppercase label style (`label-sm`), text `#64748B`, height `40px`, bottom border `1px solid #E2E8F0`.
- **Cells:** Tabular numbers enabled for price and date values, height `52px`, vertical alignment centered, border bottom `1px solid #F1F5F9`.
- **Hover State:** Row background `#F8FAFC` with smooth transition (`150ms ease-in-out`).

### Input Fields & Controls
- **Text Inputs & Selects:** Height `40px`, border `1px solid #CBD5E1`, background `#FFFFFF`, typography `body-md`. Focus ring: `2px solid #4F46E5` with `#EEF2FF` ambient spread.
- **Checkboxes & Radios:** Size `18px`, border `1.5px solid #94A3B8`, active fill `#4F46E5` with crisp white check glyph.

### Cards & Reservation Drawers
- **Unit Summary Card:** White canvas (`#FFFFFF`), `1px solid #E2E8F0` border, `16px` padding. Contains unit title, capacity meter (amber if >= 90%), nightly EUR rate, and instant "Quick Book" trigger.
- **Telemetry Drawer:** Positioned at page bottom or slide-over right. Outlines active SQLite query metrics, response payload latency, and sync timestamps in `JetBrains Mono` and muted slate neutrals.
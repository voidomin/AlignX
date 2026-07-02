---
version: "3.0"
theme: "Editorial Instrument"
colors:
  bg: "#100E0B"
  surface: "#171310"
  surface_raised: "#1E1813"
  border: "#2C2620"
  border_subtle: "#221D18"
  text_primary: "#EDE7DC"
  text_secondary: "#A79E8E"
  text_muted: "#625B4E"
  accent: "#E2846A"
  accent_muted: "#35281F"
  highlight: "#F59E0B"           # Selection/highlight, distinct from accent
  success: "#8FAE83"
  error: "#EF4444"
  warning: "#F59E0B"
typography:
  font_heading: "Georgia, 'Iowan Old Style', 'Times New Roman', serif"
  font_body: "Segoe UI, -apple-system, sans-serif"
  font_data: "ui-monospace, 'SF Mono', Consolas, monospace"
  size_base: "16px"
---

# Design System Manifest: AlignX Web Application

This document defines the visual rules and styling system for the AlignX web frontend (`web-frontend/`). It maintains visual consistency across all components.

---

## 🎨 Overview & Aesthetic Vibe

The visual aesthetic is **"Editorial Instrument"** — a synthesis of three references, each contributing one specific thing rather than being blended indiscriminately:

- **Scientific journal** (serif headings, `Fig./Table` eyebrow labels, right-aligned captions) — the app reads like the output document, not just a control panel.
- **Organic biotech warmth** (a warm near-black ground instead of a cold neutral one, generous section spacing) — softens the journal reference so it doesn't feel clinical.
- **Brutalism, spent in exactly one place** (a hard, non-blurred offset shadow) — reserved for the single primary "Run Alignment" button. Nowhere else. This is what keeps that one button reading as *deliberate* rather than the whole UI reading as loud.

Everything else stays quiet: flat surfaces, one accent color, no gradients, no backdrop blur, no decorative icons next to their own label.

> **Historical note**: v2.0 ("Minimal Dark Mode") used cyan (`#4CD7F6`) as the single brand accent on a cool near-black ground with Montserrat headings. v3.0 replaces cyan with coral (`#E2846A`) as the accent, warms the entire ground, and switches headings to a serif face. Violet/cyan (`#8B5CF6`/`#06B6D4`) remain **only** as data-encoding colors inside the 3D viewer and one `LigandTab.js` interaction-type dot — this rule carries over unchanged from v2.0. Do not reintroduce cyan as UI chrome; if you see it outside the 3D viewer/legend dots, it's a regression.
>
> **N-structure chain palette** (`Viewer3D.js`): the viewer superimposes any number of input structures, not just two, so chain-identity color is a 6-color qualitative cycle — `#8B5CF6` (violet), `#06B6D4` (cyan), `#EC4899` (pink), `#A3E635` (lime), `#FB923C` (orange), `#2DD4BF` (teal) — assigned in input order and cycling by index modulo 6 beyond 6 structures. This palette deliberately avoids amber `#F59E0B` (reserved for the residue-selection highlight, `.row-selected`) and the coral brand accent (reserved for UI chrome), so the three semantic uses of color — chain identity, selection highlight, brand accent — never collide.
>
> **Conservation palette** (`SequenceTab.js`'s sequence alignment grid): per-residue background colors (`#ff4757` fully conserved, `#ffa502` high similarity, `#2f3542` gap, white glyph text) encode conservation degree, not brand or chain identity — a fourth intentional exception alongside the two above. Don't fold these into the semantic token set; the traffic-light meaning is the point.

---

## 🎨 Core Color Palette

| Token | Value | Usage |
|---|---|---|
| `bg` | `#100E0B` | Page background |
| `surface` | `#171310` | Card background, top bar |
| `surface-raised` | `#1E1813` | Nested elements (stat backgrounds, inputs, chips) |
| `border` | `#2C2620` | Section rules, card/panel borders |
| `border-subtle` | `#221D18` | Borders on nested/raised elements |
| `primary` (→ `text-primary`) | `#EDE7DC` | Primary text |
| `secondary` (→ `text-secondary`) | `#A79E8E` | Secondary/muted text, captions |
| `muted` (→ `text-muted`) | `#625B4E` | Placeholder/disabled text |
| `accent` | `#E2846A` | The one brand accent — active tab, primary button, links, focus rings, eyebrow labels |
| `accent-muted` | `#35281F` | Accent background for active/selected states |
| `tertiary` / `warning` | `#F59E0B` | Selection/highlight semantic — see note below |
| `success` | `#8FAE83` | Positive status (sage, not brand-accent) |
| `error` | `#EF4444` | Negative status / destructive actions |

**A deliberate second color**: amber (`#F59E0B`) is used for **selection/highlight** — `.row-selected` and the selected-residue highlight in the 3D viewer. Not a second brand accent; kept separate from `accent` on purpose (same rule as v2.0, unchanged).

---

## 🔤 Typography — three roles, not two

- **Serif (`Georgia`/`Iowan Old Style` stack)** — section titles only (`.section-title`), via `font-headline-*`. This is the "journal" reference. Don't use serif for body copy, labels, or buttons — it's reserved for the one heading-per-section moment.
- **Sans (`Segoe UI`/system stack)** — everything else: body copy, buttons, labels, nav.
- **Monospace (`ui-monospace`/`SF Mono` stack)** — every data value: stat numbers, run IDs, RMSD/coordinates, table cells with numeric or ID content. If it's a measurement or identifier, it's mono; if it's prose, it's sans.

---

## 📐 Layout — no sidebar, persistent viewer, sectioned tab content

- **Shell**: a single sticky top bar (`TopBar.js`) containing the brand, the 7 tab pills (6 analysis tabs + History), workspace actions (New Workspace, Export), and a slim system-status strip (engine health + RAM + Free RAM). There is **no persistent left sidebar** — that was v2.0's structure; v2.0's nav links, reset button, and health strip all now live in the top bar.
- **Below the top bar**: two columns. Left = the active tab's content (scrollable). Right = the 3D structure viewer, **persistent across all 7 tabs** (rendered once, never re-rendered by tab switching) — this is what lets you switch to Ligands and watch a binding site highlight live in 3D without losing the model.
- **History is a tab**, not an overlay panel. Clicking a past run reloads it and switches to the Sequence tab, same as before.
- **Base Grid Unit**: `8px`, enforced concretely:
  - `gap-2` (8px) — within a tight cluster (chip groups)
  - `gap-4`–`gap-6` (16–24px) — between fields/rows
  - Sections (`.editorial-section`) get `56px` top/bottom padding with a hairline rule between them — this is deliberately more generous than a card's internal padding, because a section is a whole "page" of content, not a widget.

---

## 📦 Component Styling

### 1. The section pattern (replaces "cards" as the primary content wrapper)
Every tab body's outermost element is `.editorial-section`, not a boxed `.card`:
```html
<section class="editorial-section">
  <header class="section-head">
    <div>
      <span class="eyebrow">Fig. — Short Label</span>
      <h2 class="section-title">Section Heading</h2>
    </div>
    <div class="section-caption">Optional right-aligned one-liner.</div>
  </header>
  <div class="section-body"> ... </div>
</section>
```
`.card` still exists (`web-frontend/src/style.css`) and is used for the 3D viewer panel and truly boxed sub-elements, but it is no longer the default wrapper for tab content.

### 2. Stat readouts — top-rule rows, not boxed cards
Numbers (RMSD, identity, aligned length, etc.) use `.stat-row`: a top hairline + label + monospace value, not a bordered box. The primary/most-important stat in a group gets `.stat-primary`, which colors its top rule accent instead of the whole box — this marks it without adding a second color.

### 3. Buttons
- **Primary** (`.btn-primary`): solid `#E2846A` fill, `#100E0B` text, no shadow.
- **Primary-hard** (`.btn-primary-hard`): the one brutalist device in the system — same coral fill, plus a hard 5px offset shadow (`box-shadow: 5px 5px 0 #35281F`, no blur) that shifts on hover/active to fake a physical press. **Reserved for exactly one button app-wide**: Overview's "Run Structural Alignment". Do not apply this class anywhere else — if two buttons have the hard shadow, neither reads as deliberate anymore.
- **Secondary** (`.btn-secondary`): transparent background, `1px solid #2C2620` border.

### 4. Badges & Chips
Same rule as v2.0: purely decorative counts are plain colored text, no container. Genuine discrete chips (cluster members, history PDB-id tags) use a small square-ish container (`rounded-md bg-surface-raised border border-border-subtle`), never a pill.

### 5. Data Tables & Lists
Rows are separated by `border-b border-border-subtle`, hover background `surface-raised`. Prefer flat row lists over boxed-card-per-item (see `HistoryPanel.js`/`ClustersTab.js`) — this reads as one continuous document, matching the journal reference, rather than a stack of separate widgets.

### 6. 3D Viewport Panel
Unchanged from v2.0: flat HUD chips (`bg-surface border border-border`, no blur), no decorative grid/reticle/animated placeholder — the empty state is plain muted text. The 3Dmol.js mount div (`#viewer-canvas-3dmol`) is owned by the 3Dmol library; never restyle its box model, only sibling overlay elements. It now lives in the right-hand persistent column rather than the left side — if repositioning it further, verify window-resize still calls `viewer.resize()` correctly, since 3Dmol reads its container's computed size at init and on resize.

---

## 🔤 Icon Usage Policy

Unchanged from v2.0: icons are load-bearing (kept) only when they're the sole affordance for an action with no visible text label — the 3D viewer's surface-toggle/reset-view buttons, a per-row delete button, the loading spinner, `play_arrow` on the one primary Run button. Icons are decorative (removed) when they sit next to a text label that already says the same thing. The TopBar's logo glyph is the one exception, functioning as a wordmark rather than a redundant label.

---

## 🧩 Component Inventory (post-v3.0)

`TopBar.js` replaces `TopNav.js` + `Sidebar.js` + `TabPanel.js` (all three deleted). It owns: brand, the 7-tab nav strip, New Workspace, Export, and the system-status strip. `Viewer3D.js`, `HistoryPanel.js`, and the six tab-body components (`OverviewTab`, `LigandTab`, `SequenceTab`, `AnalyticsTab`, `ClustersTab`, `ComparisonTab`) are unchanged in file identity, restyled internally to the section pattern. `main.js` owns the two-column shell and renders `Viewer3D` exactly once, outside the tab-switching logic, so it survives every tab change including History.

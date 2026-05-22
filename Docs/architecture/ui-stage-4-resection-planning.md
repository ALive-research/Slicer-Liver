# UI architecture — Stage 4: Resection Planning

Reference companion to [ADR-0023 §Stage 4][adr-0023]. Captures the
resection-table inline-column layout, the per-row state machine
controls, the distance-map status section, the classification
overlay binding, and the resectogram-view invocation.

[adr-0023]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0023-unified-gui-stage-workflow.md
[adr-0019]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0019-resection-state-machine.md

## What this stage does

Define one or more resection surfaces via Bezier control polygons. Each resection cycles through a state machine (Init → Planning → Confirmed per [ADR-0019][adr-0019]). Multi-resection workflows (two-stage hepatectomy, RFA + resection) are first-class.

Module home: `LiverResections/`.

## Panel layout

```
┌─ 4. Resection Planning ────────────────────────────────────────────────┐
│                                                                        │
│ ┌─ Resections ─────────────────────────────────────────────────────┐  │
│ │ ☰│●│👁│■│ Name        │ State    │ Init     │ Safety│ Risk     │⋯│  │
│ │ ─┼─┼──┼─┼─────────────┼──────────┼──────────┼───────┼──────────┼─│  │
│ │ ☰│●│👁│■│Right hep.   │ ✓ Conf.  │ S.Plane  │ 10 mm │avg spc.  │⋯│  │
│ │ ☰│○│👁│■│Tumor wedge  │ Planning │ Spheroid │  8 mm │Custom 2 m│🔒│  │
│ │ ☰│○│⊘│■│Wedge 3      │ Init 1/N │ Spheroid │ 10 mm │avg spc.  │⋯│  │
│ │ [+ Add resection]                                                │  │
│ └──────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│ ┌─ Active resection: Tumor wedge ──────────────────────────────────┐  │
│ │   Init  ─▶  [Planning]  ─▶  Confirmed                            │  │
│ │  Bezier:     4×4 grid  [⋯ Change grid]                           │  │
│ │  Editing:    drag control points in 3D                           │  │
│ │  [◀ Unlock to Init]   [Commit Planning → Confirmed ▶]            │  │
│ │  [Open resectogram view ▶]                                       │  │
│ └──────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│ ┌─ Distance maps ──────────────────────────────────────────────────┐  │
│ │  Status: ✓ Computed 2 min ago                                    │  │
│ │  ✓ Tumor   ✓ Portal   ✓ Hepatic                                  │  │
│ │  [Recompute distance maps]                                       │  │
│ └──────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│ ┌─ Classification overlay ─────────────────────────────────────────┐  │
│ │  Classification: [▼ Couinaud (auto, TotalSegmentator)         ]  │  │
│ │  ☑ Show segments in 3D view  ☐ Show in slice views               │  │
│ │  Opacity: ─────────●─── 30%                                      │  │
│ └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

## Resections table

### Inline columns

| Column | Affordance |
|--------|-----------|
| `☰` | Drag handle for re-ordering (the order is semantically load-bearing — surgical order + locator-overlap precedence on the resectogram). |
| `●` | Active radio (only one resection editable at a time). |
| `👁/⊘` | Visibility toggle. Non-active confirmed resections render semi-transparent; non-active editing-state resections hide. |
| `■` | Color swatch — click opens color picker; stored on `vtkMRMLBezierSurfaceDisplayNode`. |
| Name | Inline-editable. Click to rename. |
| State | Badge (`Init <n>/<N>` / `Planning` / `✓ Conf.`). |
| Init mode | `S.Plane` / `Spheroid` — locked at creation, requires Reset-to-Init to switch. |
| Safety | Numeric mm input (free value, default 10 mm). |
| Risk | Dropdown preset (`avg spacing` / `largest spacing` / `Custom N mm`). |
| `⋯` | Menu: Rename, Delete (confirmation required for Confirmed), Duplicate, Unlock-from-Confirmed. |
| `🔒` | Per-row Confirm button (shown when Planning state is ready to commit; replaces the `⋯` menu for that row). |

### Re-order semantic

Drag-to-reorder updates the resection list. The list order has weight:

- **Surgical order** — typically reflects the planned operative sequence (two-stage hepatectomy: Stage 1 resection first row, Stage 2 resection second).
- **`.lrp.json` schema v3** — persisted as a list (ordered).
- **Locator precedence on resectogram overlap** — when multiple resection surfaces project onto the resectogram view (Stage 4 detail panel), top of table wins.

## Active resection detail panel

### State breadcrumb

`Init ─▶ [Planning] ─▶ Confirmed` — the **bracketed** state is the current state; non-current states render as plain labels. In the actual Qt UI the indicator is a **colour code** on the current state's label (e.g. accent foreground + bracket glyph) — the ASCII mockup uses brackets `[...]` to convey the same idea without colour. No separate "↑ current" annotation line; the bracket/colour *is* the indicator.

Visualised as a non-interactive breadcrumb — surgeon advances via the bottom-row transition buttons (or the per-row `🔒` in the resection table). Stepping back uses `[◀ Unlock to ...]`.

### State-specific contents

**Init state** (breadcrumb: `[Init] ─▶ Planning ─▶ Confirmed`):

```
Init mode:    ◉ Slicing Plane   ○ Distance Spheroid
Init points:  2 / 2 placed
              [Reset init points]
              [Commit init → Planning ▶]
```

**Planning state** (breadcrumb: `Init ─▶ [Planning] ─▶ Confirmed`):

```
Bezier:       4 × 4 grid  (per ADR-0018 — 3×3 also possible via [⋯ → Change grid])
Editing:      drag control points in 3D view (vtkLiverBezierWidget)
              [◀ Unlock to Init]   [Commit Planning → Confirmed ▶]
[Open resectogram view ▶]
```

**Confirmed state** (breadcrumb: `Init ─▶ Planning ─▶ [Confirmed]`):

```
Confirmed at: 2026-05-21 14:32 by current session
For volumes + verification → continue to Stage 5.
              [◀ Unlock to re-plan]
[Open resectogram view ▶]
```

No numeric readouts in any state. Volume / margin / vessel-cut numbers live in Stage 5 per the 2026-05-21 compute-on-stable-state pushback.

### Resectogram view button

`[Open resectogram view ▶]` is visible per active resection across Planning and Confirmed states. Clicking it switches Slicer to a Slicer-Liver-registered custom layout (Hyperprobe-style separate view per the 2026-05-15 resectogram decision) showing the unrolled resection surface for the active resection. Closing the resectogram returns to Conventional layout.

## Distance maps section

```
Status: ✓ Computed 2 min ago | ⚠ Not computed — margin visualization disabled
[Recompute distance maps]
```

- Auto-triggers on Stage 4 entry per the 2026-05-14 decision (background infrastructure).
- `[Recompute]` is the manual-recompute affordance (also per 2026-05-14).
- When distance maps don't exist (fresh entry without computation, or after data invalidation), UI elements depending on them disable:
  - Tumor-margin visualization on the resection-surface shader.
  - Safety/Risk band coloring on the surface.
  - (Stage 5's verification consumers are unaffected here.)
- Status banner explains the disable state ("⚠ Not computed — margin visualization disabled").

## Classification overlay section

```
Classification: [▼ Couinaud (auto, TotalSegmentator)] [None]
☑ Show segments in 3D view  ☐ Show in slice views
Opacity: ─────────●─── 30%
```

- `qMRMLNodeComboBox` filtered on `vtkMRMLAbstractTerritoriesNode` (both subtypes from Stage 3 surface here).
- `addEnabled=false` / `removeEnabled=false` — Stage 4 doesn't create or delete classifications (that's Stage 3's responsibility). Independent binding per ADR-0023 — Stage 4's selection doesn't sync to Stages 3 or 5.
- `noneEnabled=true` — selecting "None" disables the overlay cleanly.
- Opacity slider applies to the segment overlay; resection surfaces render fully opaque on top.

## Multi-resection visualization

- All Confirmed resections render in 3D simultaneously (per the 2026-05-21 settlement).
- Non-active Confirmed resections are semi-transparent.
- Active resection's Bezier widget is the only interactive surface — other surfaces render but don't pick.
- Per-row `👁/⊘` lets surgeon explicitly hide any resection.

## Add-resection workflow

`[+ Add resection]` immediately enters Init mode with auto-name (`Resection 1`, `Resection 2`, ...). Defaults: Slicing Plane init, Safety 10 mm, Risk = image-spacing-average. Surgeon renames via the table row's name cell. Friction-free start; per the 2026-05-21 settlement.

## Cross-stage interactions

| Direction | Surface |
|-----------|---------|
| Stage 1 → Stage 4 | Provides the CT volume the Bezier-surface mapper renders against. |
| Stage 2 → Stage 4 | Canonical Segmentation node provides liver / tumor / portal / hepatic structures for the distance-map computation. |
| Stage 3 → Stage 4 | Classification overlay combobox surfaces both `Std` and `Custom` Territories subtypes. Independent binding. |
| Stage 4 → Stage 5 | Confirmed resections become barriers for Stage 5's volumetry partition. |
| Stage 4 → Stage 6 | Confirmed resections + their per-row name / margins / state persist into `.lrp.json` schema v3. |
| Sidebar | Stage 4 state indicator turns ✓ when at least one resection reaches Confirmed state. |

## See also

- [ADR-0023 §Stage 4][adr-0023]
- [ADR-0019 — Resection state machine][adr-0019]
- [Resection state machine diagram](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/architecture/resection-state-machine.md)
- [GUI stage flow](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/architecture/gui-stage-flow.md)
- [Stage 3 — Vascular Territories](ui-stage-3-vascular-territories.md) — supplies the classification overlay.
- [Stage 5 — Volumetry](ui-stage-5-volumetry.md) — consumes Confirmed resections as barriers.

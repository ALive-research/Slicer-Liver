# UI architecture — Stage 5: Volumetry

Reference companion to [ADR-0023 §Stage 5][adr-0023]. Captures the
flexible seed-and-category builder, the categories master + seeds
control-points detail, the barriers checkbox list, and the
explicit-compute output table.

[adr-0023]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0023-unified-gui-stage-workflow.md

## What this stage does

Compute per-category volumes by partitioning the liver parenchyma via the seed-and-category framework (2026-05-15 decision). Categories are surgeon-defined; seeds are fiducial points; barriers are Confirmed resection surfaces from Stage 4. Pure analytical workbench — **no verification card** in v2.0 (research-tool-grade per ADR-0023).

Module home: `LiverVolumetry/`.

## Panel layout

```
┌─ 5. Volumetry ─────────────────────────────────────────────────────┐
│                                                                    │
│  Partition: [▼ Resected vs Remnant] [+][-][⋮]                      │
│                                                                    │
│  ┌─ Categories ───────────────────────────────────────────────┐   │
│  │  Name              Color   Seeds   Actions                 │   │
│  │  Resected      ●   ■         2     [⋯]                     │   │
│  │  Remnant           ■         1     [⋯]                     │   │
│  │  [+ Add category]                                          │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                    │
│  ┌─ Seeds of: Resected ───────────────────────────────────────┐   │
│  │  qMRMLMarkupsControlPointTableWidget (Slicer-core, reused) │   │
│  │  # │ Name      │ R (mm)│ A (mm)│ S (mm) │ Vis │ Actions    │   │
│  │  1 │ Reseed-1  │ ⋯     │ ⋯     │ ⋯      │ 👁  │ [⋯][×]     │   │
│  │  2 │ Reseed-2  │ ⋯     │ ⋯     │ ⋯      │ 👁  │ [⋯][×]     │   │
│  │  [+ Add seed]                                              │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                    │
│  ┌─ Barriers ─────────────────────────────────────────────────┐   │
│  │  Resections as barriers:                                   │   │
│  │   ☑ Right hemihepatectomy                                  │   │
│  │   ☑ Tumor 2 wedge                                          │   │
│  │   ☐ Wedge 3 (not Confirmed — disabled)                     │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                    │
│  ┌─ Compute ──────────────────────────────────────────────────┐   │
│  │  ROI: [▼ Liver (resolved via SCT)]                         │   │
│  │  [Compute partition]    Last: 30 s ago                     │   │
│  │                                                            │   │
│  │  Volumes:                                                  │   │
│  │   Resected    330 mL   (22 %)                              │   │
│  │   Remnant    1210 mL   (78 %)                              │   │
│  │                                                            │   │
│  │  Output partition: [auto-named Segmentation ▼ visible]     │   │
│  └────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
```

## Top combobox — partitions

- `qMRMLNodeComboBox` filtered on `vtkMRMLLiverVolumetryNode`.
- Multiple partitions per scene are supported (e.g., "Resected vs Remnant" + "Custom regional analysis 1" + "Right-anterior watershed").
- `[+]` creates a new empty partition. Default name on first creation: "Resected vs Remnant" (the dominant use case). Per the 2026-05-21 settlement: **empty by default** — no auto-populated categories or seeds.
- `[-]` deletes the current partition (confirmation; deletes the output Segmentation node alongside).
- `[⋮]` exposes rename / advanced properties.

## Categories master table

Flat table — categories don't have sub-entities at the row level (their seeds appear in the detail panel below when selected).

| Column | Affordance |
|--------|-----------|
| Name | Inline-editable. Surgeon-defined ("Resected", "Remnant", "Segment II watershed", "Custom region A"). |
| Color | Click opens color picker; stored on the category's metadata in the volumetry node. |
| Seeds | Count of fiducial points in the category's `vtkMRMLMarkupsFiducialNode`. |
| Actions | `[⋯]` menu: Rename, Change color, Delete. Multi-select for batch delete. |

### Active category radio

The `●` selector in the leftmost column (not shown in the column list above but visually present) marks the active category. The Seeds sub-table below shows the active category's seeds. Switching the active radio swaps the sub-table contents.

## Seeds detail sub-table

Reuses Slicer-core's `qMRMLMarkupsControlPointTableWidget`, wired to the active category's fiducial node. Same affordances as the Stage 3 endpoints sub-table — add, move, delete, jump-to-3D, multi-select.

Per the 2026-05-21 settlement: **seeds are surgeon-placed**. No auto-placement for the Resected/Remnant case (surgeon picks one point on each side of the resection surface manually). This adds friction in the dominant case but keeps the framework primitive simple and predictable.

## Barriers section

```
Resections as barriers:
 ☑ Right hemihepatectomy
 ☑ Tumor 2 wedge
 ☐ Wedge 3 (not Confirmed — disabled)
```

- Lists every resection from Stage 4. Confirmed resections are check-eligible; non-Confirmed are disabled with hint text.
- Per the 2026-05-21 settlement: **all Confirmed resections auto-tick as barriers on Stage 5 entry**. Surgeon unticks any that should not act as a barrier (rare).
- Barriers feed the framework's Fast Marching speed map (1 inside ROI, 0 on rasterised barrier voxels per the 2026-05-15 framework decision).

## Compute section

### ROI selector

`[▼ Liver (resolved via SCT)]` — typically auto-resolved from the canonical Segmentation node's Liver segment (SCT 10200004). Surgeon can override for research workflows.

### Compute trigger

`[Compute partition]` — explicit button. Lazy evaluation (no auto-compute on input change) because Fast Marching is non-trivial and surgeon's input-fiddling shouldn't trigger spurious recomputes.

### Volumes table

Per-category volumes appear after compute:

```
Resected    330 mL   (22 %)
Remnant    1210 mL   (78 %)
```

Percentages are of total liver ROI volume. Sortable column header.

### Output Segmentation node

A `vtkMRMLSegmentationNode` named after the partition (e.g., "Resected vs Remnant — partition"), with one segment per category, color-matched to the category's color. Stock Slicer rendering in 3D + slice views per ADR-0012's deferral of LayerDM display-side migration to v2.1. Surgeon can toggle visibility globally (`▼ visible`).

## What's not in Stage 5

- **No verification card** (the 2026-05-21 settlement dropped it from v2.0).
- **No per-resection volume breakdown** beyond what the partition naturally produces. Per-resection-specific volumes (if needed) come from running multiple partitions with different category configurations.
- **No per-segment intersection with classification** (that's verification-flavoured analytics).
- **No resectogram** — the resectogram view lives in Stage 4 per ADR-0023.
- **No "Continue to Export" button on top** — sidebar navigation handles stage transitions.

## Persistence

Per the 2026-05-21 settlement: multiple partitions persist in `.lrp.json` schema v3 as a list (per partition: name, category names + colors, seed positions, output Segmentation node reference). Per-stage last-selection field stores which partition the surgeon was last viewing. Reload restores both.

## Cross-stage interactions

| Direction | Surface |
|-----------|---------|
| Stage 2 → Stage 5 | Canonical Segmentation provides the ROI (Liver segment). |
| Stage 3 → Stage 5 | Classification combobox (if added — currently not in v2.0 Stage 5 panel; downstream consumers may add it). Per-segment intersection analytics deferred. |
| Stage 4 → Stage 5 | Confirmed resections appear in the Barriers checkbox list (auto-ticked). |
| Stage 5 → Stage 6 | Volumetry partitions persist into `.lrp.json` schema v3 as part of the plan sidecar. |
| Sidebar | Stage 5 state indicator turns ✓ when at least one partition has been computed. |

## See also

- [ADR-0023 §Stage 5][adr-0023]
- [GUI stage flow](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/architecture/gui-stage-flow.md)
- [Stage 4 — Resection Planning](ui-stage-4-resection-planning.md) — supplies Confirmed resections as barriers.
- 2026-05-15 volumetry-framework PKS subnote — algorithm details (Fast Marching with binary speed map, ITK `FastMarchingImageFilter`, barrier rasterisation via `vtkPolyDataToImageStencil`).

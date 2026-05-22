# UI architecture — Stage 3: Vascular Territories

Reference companion to [ADR-0023 §Stage 3][adr-0023]. Captures the
two-tab structure (Couinaud-automatic vs Custom-manual), the
hierarchical centerlines+groupings table with master-detail
endpoints sub-table, and the `qMRMLNodeComboBox`-driven node
management for `vtkMRMLAbstractTerritoriesNode` subclass instances.

[adr-0023]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0023-unified-gui-stage-workflow.md
[territories]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/architecture/territories-class-hierarchy.md

## What this stage does

Produce a partition of the liver parenchyma into anatomical territories — typically Couinaud segments I–VIII, but the framework supports custom partitions. Two surgeon-facing paths share an abstract base class but coexist as different concrete subtypes (see [Territories class hierarchy][territories]):

- **Couinaud (automatic)** tab — calls TotalSegmentator (or another backend if configured) on the source image; produces `vtkMRMLStdCouinaudTerritoriesNode`. Depends only on Stage 1.
- **Custom segments** tab — surgeon defines centerlines (VMTK-extracted from fiducial endpoints) and groups them into segments; produces `vtkMRMLCustomTerritoriesNode`. Depends on Stage 2's vessel segmentation.

Module home: `VascularTerritories/` (renamed from `LiverSegments/`).

## Tab structure

```
┌─ 3. Vascular Territories ──────────────────────────────────────────────┐
│ ┌─[ Couinaud (automatic) ]──[ Custom segments ]──────────────────────┐ │
│ │ <tab-specific content>                                             │ │
│ └────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────┘
```

Both tabs publish into the same scene as separate `vtkMRMLAbstractTerritoriesNode` instances; downstream consumers polymorphically work with either subtype.

## Automatic Couinaud tab

```
┌─[ Couinaud (automatic) ]──[ Custom segments ]──────────────────────┐
│                                                                    │
│ ┌─ Source ─────────────────────────────────────────────────────┐  │
│ │  Backend:    [▼ TotalSegmentator]                            │  │
│ │  Source:     [▼ Portal venous (patient_PV.nrrd)]             │  │
│ │  [Compute]                                                   │  │
│ └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│ ┌─ Result ─────────────────────────────────────────────────────┐  │
│ │  Status: ✓ Computed 2 min ago via TotalSegmentator           │  │
│ │  ┌────────┬───────┬────┐                                     │  │
│ │  │ Segment│ Color │ 👁 │                                     │  │
│ │  ├────────┼───────┼────┤                                     │  │
│ │  │ I      │ ■     │ 👁 │                                     │  │
│ │  │ II     │ ■     │ 👁 │                                     │  │
│ │  │ III    │ ■     │ 👁 │                                     │  │
│ │  │ ⋯                                                          │  │
│ │  └────────┴───────┴────┘                                     │  │
│ └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

- **`[Compute]`** triggers the backend on the Source image. First-use triggers `pip_install` per ADR-0023 lazy-install convention.
- Result table is read-only — segments are auto-derived. Surgeon can toggle visibility per segment (`👁` column) for 3D-overlay inspection.
- No `qMRMLNodeComboBox` in the tab; each compute replaces the previous Auto result (one auto-territory node per scene at a time, unless surgeon explicitly creates more in the Custom tab).

## Custom segments tab

```
┌─[ Couinaud (automatic) ]──[ Custom segments ]──────────────────────────┐
│  Classification: [▼ Manual Couinaud  ] [+][-][⋮]                       │
│  Subdivision:    ◉ Couinaud I-VIII (with IVa/IVb)  ○ Custom            │
│                                                                        │
│  ┌─ Centerlines & groupings ────────────────────────────────────────┐ │
│  │  Name              Color   Endpoints  Actions                    │ │
│  │ ▼ Segment II        ■                  [⋯]                       │ │
│  │     P2-main         ■        5         [↗][×]                    │ │
│  │     P2-accessory ●  ■        3 ⚠       [↗][×]    ← selected      │ │
│  │ ▶ Segment III (1)   ■                  [⋯]                       │ │
│  │ ▶ Segment IV (empty)■                  [⋯]                       │ │
│  │ ▶ Segment V (empty) ■                  [⋯]                       │ │
│  │ ▶ Segment VI (empty)■                  [⋯]                       │ │
│  │ ▶ Segment VII(empty)■                  [⋯]                       │ │
│  │ ▶ Segment VIII(emp.)■                  [⋯]                       │ │
│  │ ▶ Segment I  (empty)■                  [⋯]                       │ │
│  │ ▼ (Unassigned)                                                   │ │
│  │     loose1          ◌        2         [↗][×]                    │ │
│  │ [+ Add centerline]   [+ Add segment]                             │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                        │
│  ┌─ Endpoints of: P2-accessory                  ⚠ stale ────────────┐ │
│  │  qMRMLMarkupsControlPointTableWidget (Slicer-core, reused)       │ │
│  │  #│ Name      │ R (mm)│ A (mm)│ S (mm) │ Vis │ Actions           │ │
│  │  1│ P2-acc-1  │ -23.4 │  18.7 │   5.2  │ 👁  │ [⋯][×]            │ │
│  │  2│ P2-acc-2  │ -19.1 │  14.3 │   7.8  │ 👁  │ [⋯][×]            │ │
│  │  3│ P2-acc-3  │ -15.8 │  10.5 │  10.1  │ 👁  │ [⋯][×]            │ │
│  │  [+ Add endpoint]   [Re-run ExtractCenterline]                   │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                        │
│  [Compute partition]                                                   │
└────────────────────────────────────────────────────────────────────────┘
```

### Top combobox

- `qMRMLNodeComboBox` filtered on `vtkMRMLCustomTerritoriesNode` (the Custom subclass).
- `[+]` creates a new empty manual classification — surgeon names it (defaults to "Manual Couinaud" or "Custom partition").
- `[-]` deletes the current classification.
- `[⋮]` exposes rename / advanced node-property edits.

### Hierarchical table (master)

Two-level tree: group → centerline. CRUD operations per ADR-0023's grilling-pass settlement:

| Operation | Affordance |
|-----------|-----------|
| Add centerline | `[+ Add centerline]` → enters curve-markup placement mode → after Enter, prompt for group assignment → centerline appears in tree. |
| Group centerlines | Drag a centerline across groups, OR `[↗]` opens a dropdown of groups to reassign. |
| Delete centerline | `[×]` on the centerline row → confirmation → MRML node removed. |
| Delete grouping | `[⋯ → Delete grouping]` on the group row → confirmation → group removed; centerlines fall back to `(Unassigned)` (not deleted). |
| Reorder groups | Drag-to-reorder (Custom subdivision only; Couinaud subdivision has fixed I–VIII anatomical order). |

The `(Unassigned)` pseudo-group at the bottom holds centerlines that exist but are not yet part of any segment. Visible-but-dotted/grey in 3D. Doesn't contribute to the partition until assigned.

### Endpoints sub-table (detail)

Reuses Slicer-core's `qMRMLMarkupsControlPointTableWidget`. Shows the control points of the **currently-selected centerline**. Selecting a group row (rather than a centerline) shows a hint "Select a centerline to view its endpoints."

| Operation | Affordance |
|-----------|-----------|
| Add endpoint | `[+ Add endpoint]` → enters fiducial placement mode → new endpoint appends to the centerline's fiducial node. Centerline marked `⚠ stale`. |
| Move endpoint | Edit R / A / S cells directly, OR drag the fiducial in 3D. Centerline marked `⚠ stale`. |
| Delete endpoint | `[×]` per row. Centerline marked `⚠ stale`. |
| Re-extract | `[Re-run ExtractCenterline]` → invokes VMTK on the current endpoint set → updates the centerline polyline node → clears stale flag. |
| Reorder | Drag rows (affects centerline direction if relevant). |

### Stale-state handling

VMTK extraction is non-trivial (seconds). Edits mark the centerline `⚠ stale` rather than auto-re-running. Re-extraction triggers on explicit `[Re-run ExtractCenterline]` or implicitly on `[Compute partition]` (any stale centerlines re-extract first). `[Save]`-equivalent (just scene save, no bespoke button) blocks if anything stale; surgeon clicks Re-run first.

## Behaviour notes

### Subdivision modes (Custom tab)

- **Couinaud I-VIII (with IVa/IVb)** — pre-populated groups Segment I through VIII (10 groups including IVa/IVb split per the verified SCT codes); fixed anatomical order; group rename disabled.
- **Couinaud I-VIII (IV whole)** — 8 groups; IVa/IVb merged into IV.
- **Custom** — surgeon-defined groups; `[+ Add segment]` creates a new empty group with editable name; drag-to-reorder enabled.

### Computation

`[Compute partition]` invokes the volumetry framework's Fast Marching algorithm (per the 2026-05-15 framework decision) with seeds sampled along the assigned centerlines (no barriers). Output: a partition `vtkImageData` + per-segment colors stored on the `vtkMRMLCustomTerritoriesNode`. Warns on `(Unassigned)` non-empty: "N centerlines unassigned — won't contribute. Compute anyway?".

### Centerline data model

Surgeon-facing primitive: endpoints (`vtkMRMLMarkupsFiducialNode`, N≥2 points). VMTK's `ExtractCenterlineLogic.extractCenterline(...)` returns the actual centerline polyline as a `vtkMRMLModelNode` per the existing implementation (NOT a `vtkMRMLMarkupsCurveNode` — that would be a geometric curve through clicks, not a vessel-following centerline). See [ADR-0023 §"Class abstraction for territories"][adr-0023] for the full data-model rationale.

## Cross-stage interactions

| Direction | Surface |
|-----------|---------|
| Stage 1 → Stage 3 (Auto tab) | Source image for backend inference. |
| Stage 2 → Stage 3 (Custom tab) | Portal vein segment is the input to VMTK ExtractCenterline. |
| Stage 3 → Stage 4 | Stage 4's classification-overlay combobox shows both subtypes; surgeon picks which to render. |
| Stage 3 → Stage 5 | Stage 5's per-segment table joins the classification's segments against the resection partition. |
| Sidebar | Stage 3 state indicator turns ✓ when at least one classification exists (either subtype). |

## See also

- [ADR-0023 §Stage 3][adr-0023]
- [Territories class hierarchy][territories]
- [GUI stage flow](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/architecture/gui-stage-flow.md)
- [Stage 2 — Anatomy Definition](ui-stage-2-anatomy-definition.md) — upstream (Manual path).
- [Stage 4 — Resection Planning](ui-stage-4-resection-planning.md) — downstream (classification overlay).

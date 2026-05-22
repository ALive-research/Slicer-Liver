# UI architecture — Stage 6: Export

Reference companion to [ADR-0023 §Stage 6][adr-0023]. Captures the
minimal export panel that lives as a section under the Liver shell
(not a separate scripted module).

[adr-0023]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0023-unified-gui-stage-workflow.md

## What this stage does

Persist the plan and capture screenshots. Three buttons, each a thin wrapper around an existing Slicer mechanism. No bespoke export logic beyond the `.lrp.json` schema v3 storage node.

Module home: section under the `Liver` shell (per the 2026-05-21 settlement — light enough not to warrant a separate scripted module).

## Panel layout

```
┌─ 6. Export ────────────────────────────────────────────────────────┐
│                                                                    │
│  ┌─ Resection plan ─────────────────────────────────────────────┐ │
│  │  Saves all Confirmed resections, their state, init points,   │ │
│  │  classification + volumetry references.                      │ │
│  │                                                              │ │
│  │  Format: .lrp.json (schema v3)                               │ │
│  │  Default path: <scene_dir>/<scene_name>.lrp.json             │ │
│  │  [Export plan…]                                              │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  ┌─ Full scene ─────────────────────────────────────────────────┐ │
│  │  Includes volumes, segmentations, classification, volumetry, │ │
│  │  resections — everything in the scene.                       │ │
│  │                                                              │ │
│  │  Use Slicer's standard File ▸ Save Data, or:                 │ │
│  │  [Save scene…]    (delegates to stock Slicer)                │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  ┌─ Screenshot ─────────────────────────────────────────────────┐ │
│  │  Capture current 3D + slice views.                           │ │
│  │  [Capture views…]   (delegates to Slicer's ScreenCapture)    │ │
│  └──────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
```

## Behaviour notes

### Export plan

- Invokes `vtkMRMLBezierSurfaceStorageNode::WriteData(...)` (the existing storage node from PR #361, upgraded to schema v3 per ADR-0023 §"Persistence" + tracking issue #411).
- Default save path: `<scene_directory>/<scene_name>.lrp.json` — surgeon overrides via the file dialog.
- No auto-save per the 2026-05-21 settlement. Explicit-only.
- Sidecar-only (scene-local node IDs) per the v2.0 stance; cross-machine plan transfer is a deferred v2.1 concern (tracked under issue #415).

### Save scene

- One-click shortcut to Slicer's `File ▸ Save Data` dialog. The shortcut exists for surgeon convenience — Slicer's stock menu also works.
- Saves the full scene (`.mrml` + supporting files for volumes, segmentations, etc.) — independent of the `.lrp.json` export.

### Screenshot

- Invokes Slicer's stock `ScreenCapture` module. The shortcut exists so surgeon doesn't have to navigate to a different module.

## What's NOT in Stage 6 (v2.0)

Per ADR-0023 §"What is NOT in v2.0":

- **PDF report generation** — needs a template + formatting decisions + verification content (which v2.0 doesn't have). Deferred.
- **3D model export (STL / OBJ)** — surgeon uses Slicer's stock Model export for now. AR / intraop integration is its own concern.
- **Plan diff / comparison** between two `.lrp.json` files — research feature; deferred.
- **Auto-save on Confirmed transition** — adds complexity (paths, conflicts) without clear demand; deferred.
- **Cross-machine plan transfer** — `.lrp.json` is sidecar-only in v2.0 (stable-ID resolution is v2.1+).

## Cross-stage interactions

| Direction | Surface |
|-----------|---------|
| Stage 1 → Stage 6 | Scene contains the role-tagged volumes; "Save scene" persists them. |
| Stage 2 → Stage 6 | Canonical Segmentation node persists in the scene save. Not in `.lrp.json` (too large; lives in `.mrml` + sidecar files). |
| Stage 3 → Stage 6 | Classification node references persist in `.lrp.json` schema v3. The classification's own data (labelmap, centerlines, etc.) lives in the scene. |
| Stage 4 → Stage 6 | Confirmed resections — Bezier control polygons, state, init points, margins, name, ordering — all persist in `.lrp.json` schema v3 (the primary content). |
| Stage 5 → Stage 6 | Volumetry partition references persist in `.lrp.json`. Partition output Segmentations live in the scene. |
| Sidebar | Stage 6 state indicator turns ✓ when either `[Export plan]` or `[Save scene]` has been invoked in the current session. |

## Persistence schema (v3) — what `.lrp.json` captures

| Content | Source | Stored as |
|---------|--------|-----------|
| Per-resection name + Safety + Risk margins + state + init points + Bezier control polygon | Stage 4 | Inline (the schema's primary content). |
| Resection list ordering | Stage 4 | List position (ordered). |
| Classification node reference + subtype discriminator | Stage 3 | Scene-local node ID + `subtype` field. |
| Volumetry partition references | Stage 5 | List of scene-local node IDs. |
| Per-stage last-selection | Stages 3, 4, 5 | Field on the schema's `metadata`. |

`.lrp.json` v2 → v3 fallback loader required for backward compatibility (per issue #411).

## See also

- [ADR-0023 §Stage 6][adr-0023]
- [GUI stage flow](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/architecture/gui-stage-flow.md)
- [Stage 4 — Resection Planning](ui-stage-4-resection-planning.md) — primary content source for `.lrp.json`.
- Issue [#411](https://github.com/ALive-research/Slicer-Liver/issues/411) — schema v3 implementation.
- Issue [#415](https://github.com/ALive-research/Slicer-Liver/issues/415) — v2.1 cross-machine plan transfer (deferred).

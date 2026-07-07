# 0032. v2 resection interaction via the LayerDM Pipeline seam

- **Status:** Accepted
- **Date:** 2026-06-25
- **Deciders:** Rafael Palomar
- **Diagrams:** [`Docs/architecture/rendering-pipeline.md`](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/architecture/rendering-pipeline.md)
- **PR:** <filled in on merge>

## Context

The v2 LayerDM render path for the Bézier resection surface is live and
merged (the `LiverBezierSurfacePipeline` → `BezierPlanningRepresentation` →
`vtkOpenGLBezierResectionPolyDataMapper` chain, ADR-0031 distance-map
binding included).  But the *interactive* resection workflow is still
entirely v1: the user places and edits a `vtkMRMLMarkupsBezierSurfaceNode`
through Markups, and the only production code that builds the v2
carrier + plan + display triad is the file loaders.  Closing that gap is
issue #501, which blocks retiring the v1 render.

[ADR-0014](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0014-livermarkups-dissolution.md)
§3 committed the v2 interaction to **a single
`vtkLiverBezierWidget` subclassing `vtkAbstractWidget` directly**, with a
free left-drag / right-drag / right-click event table.  That class was
scaffolded (`LiverResections/VTKWidgets/vtkLiverBezierWidget.{h,cxx}` +
`vtkLiverBezierRepresentation.{h,cxx}`) but never wired into the GUI.

Two facts discovered while planning #501 invalidate the §3 approach:

1. **The LayerDM Pipeline base already owns the interaction seam.**
   `vtkMRMLLayerDMScriptedPipeline` (the base
   `LiverBezierSurfacePipeline` already subclasses) exposes
   `CanProcessInteractionEvent(eventData) -> (bool, distance2)`,
   `ProcessInteractionEvent(eventData) -> bool`, `GetWidgetState()`,
   `GetMouseCursor()`, and `LoseFocus()`.  Interaction routes *through the
   Pipeline that already renders the surface* — the
   [ADR-0013](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0013-layerdm-pipeline-pattern.md)
   §5-clean path, with no per-module DisplayableManager.

2. **The standalone widget fights that path.**
   `vtkLiverBezierRepresentation` owns a *parallel* actor / renderer /
   `vtkPropPicker` stack with its own `RenderOverlay` /
   `RenderOpaqueGeometry`, competing with the Pipeline's render for the
   same surface; it is edit-only (no placement), and its right-drag /
   right-click handlers are TODO no-ops.  Wiring it would mean two render
   stacks for one surface and a second picking path outside the LayerDM
   manager.

So the §3 premise — that v2 interaction needs its own `vtkAbstractWidget`
— no longer holds: the Pipeline is the natural, already-rendering home
for interaction.

## Decision

v2 resection interaction (placement + control-grid editing) is
implemented by **overriding the LayerDM Pipeline's interaction seam on
`LiverBezierSurfacePipeline`** — `CanProcessInteractionEvent` /
`ProcessInteractionEvent` (+ `GetWidgetState` / `LoseFocus` as needed) —
**not** by a standalone `vtkAbstractWidget`.

- The control-grid mutation math (pick → `DisplayToWorld` → write the
  control point) is **lifted from `vtkLiverBezierWidget` into the
  Pipeline**, in Python: `vtkMRMLBezierSurfaceNode::SetControlPoint(row,
  col, x, y, z)` is Python-wrappable (the seam added for #501's
  predecessor), so the math lives in the Python Pipeline per
  [ADR-0004](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0004-python-cpp-boundary.md)
  with no new C++.
- **Editability is state-gated** per
  [ADR-0019](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0019-resection-state-machine.md):
  control points are editable in `Planning`; the Init-mode points freeze
  read-only after the `Init → Planning` commit.
- **Placement** is a Python "Place resection" action (ADR-0004) on the
  Stage-4 shell that mints the carrier + plan + display triad (via the
  logic create-API #501 adds) and seeds a default control grid the user
  then drags — replacing the v1 Markups click-to-place toolbar flow.
- `vtkLiverBezierWidget` and `vtkLiverBezierRepresentation` are
  **retired** once the Pipeline seam carries interaction.

This **supersedes the standalone-widget decision in ADR-0014 §3**.  The
*other* ADR-0014 §3 decision — relocating the four custom OpenGL mappers
to `LiverResections/VTKWidgets/` — stands and is already done; only the
`vtkAbstractWidget` interaction model is replaced here.

## Alternatives considered

### A. Wire the standalone `vtkLiverBezierWidget` (ADR-0014 §3 as written)
Use the scaffolded `vtkAbstractWidget` subclass as the editor.  Rejected:
it owns a competing render/picker stack for a surface the LayerDM
Pipeline already draws (double-draw + a picking path outside the
manager), it is edit-only with no placement, and right-drag / right-click
are unimplemented.  Keeping it would also leave two interaction
authorities for one concept.

### B. A per-module DisplayableManager hosting interaction
Host interaction in a custom `vtkMRMLAbstractDisplayableManager`.
Rejected: [ADR-0013](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0013-layerdm-pipeline-pattern.md)
§5 forbids per-module DisplayableManagers in v2.0.0 — the whole point of
the LayerDM Pipeline pattern is that the upstream LayerDM DM is the only
one, and modules contribute Pipelines.  The Pipeline's
`ProcessInteractionEvent` seam exists precisely so interaction needs no
custom DM.

### C. Keep interaction on Markups
Drive editing through a `vtkSlicerMarkupsWidget`.  Rejected: ADR-0014
dissolves the Markups dependency; the carrier is not a Markups node.

## Consequences

**Easier.** One render + one interaction authority per surface (the
Pipeline); no second renderer/picker; interaction is ADR-0013 §5-clean
with no custom DM; the grid math is Python (testable without GL via
`SetControlPoint`).

**Harder / new seams.**
- `LiverBezierSurfacePipeline` grows interaction overrides; the
  Pipeline now mediates both render and edit (it already observes the
  orchestrating-state node, ADR-0013 §4).
- **Unproven in this repo:** no existing Pipeline overrides the
  interaction seam — the first interaction slice must verify
  `ProcessInteractionEvent` actually fires for the carrier under the live
  LayerDM manager (interactive `:0`), and that focus capture coexists
  with the camera bindings.  If the seam cannot focus-capture, the
  fallback is heavier and this ADR is revisited.
- `vtkLiverBezierWidget` / `vtkLiverBezierRepresentation` are removed (a
  retirement slice), and ADR-0014 §3's illustrative file layout +
  migration-map references to them go stale — superseded here.

**Follow-up.** The migration is sliced under #501 (logic create-API →
Pipeline edit seam → placement → `ResectionPlanningWidget` re-point →
resectogram re-source → round-trip), and only after it lands is the v1
render retirement (#493 slices 3–4) safe.  That retirement is now
executed — see the 2026-07-07 amendment below.

## Conformance

- `LiverBezierSurfacePipeline` overrides `ProcessInteractionEvent` /
  `CanProcessInteractionEvent`; grep for `vtkAbstractWidget` finds **no**
  bezier-surface subclass, and `vtkLiverBezierWidget` survives only in a
  retirement commit.
- No per-module `vtkMRMLAbstractDisplayableManager` subclass is added
  (ADR-0013 §5).
- An invariant test (ADR-0027): a synthesized `vtkMRMLInteractionEventData`
  drag in `Planning` state mutates exactly one control point via
  `SetControlPoint`; the same drag in the post-commit read-only state is a
  no-op.
- Placement + the create flow live in Python (ADR-0004).

## Amendment (2026-07-07): v1 markups Bézier render fully retired

The v2 interactive workflow having landed (the Pipeline interaction seam +
Python placement per §"Decision", plus the #501 slices), the v1 markups
Bézier subsystem is now **fully retired** — a reversal of the earlier
assumption that the v1 node survives for loaders.

**What was assumed before.**
[ADR-0013](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0013-layerdm-pipeline-pattern.md)
and this ADR's original body left the v1 render + node in place so a
legacy `.lrp.fcsv` resection plan could still be migrated on load (the
"keep the legacy Markups path alive" position).

**What changes now.** The following are removed in full:

- the v1 render classes `vtkSlicerBezierSurfaceWidget`,
  `vtkSlicerBezierSurfaceRepresentation3D`, `vtkSlicerBezierSurfaceRepresentation2D`;
- the v1 MRML classes `vtkMRMLMarkupsBezierSurfaceNode` and
  `vtkMRMLMarkupsBezierSurfaceDisplayNode`, and their markups-node /
  display-node registrations;
- the legacy `.lrp.fcsv` migration: the CSV parse vehicle
  `vtkMRMLLiverResectionCSVStorageNode`, the storage node's `ReadFcsv`
  branch, and the reader's `.lrp.fcsv` acceptance.

`vtkBezierSurfaceSource` is **kept** — it is a pure-VTK surface evaluator
the v2 render path (`BezierPlanningRepresentation`,
`FlattenedSurfaceRepresentation`) and `vtkLiverVolumetryLogic` consume; it
is unrelated to the retired v1 node family.

**Rationale.** After the #501 interactive migration, the entire
place/edit/render workflow is on v2; the v1 node has no remaining
producer or consumer.  The maintainer records a negligible v1-scene
install base, so preserving the `.lrp.fcsv` migration is not worth the
carrying cost of a whole disjoint node hierarchy + its CSV parser.

**Consequence.** Legacy `.lrp.fcsv` resection-plan files **no longer
load** — only the v2 `.lrp.json` schema is read and written.  The sole
Bézier render + interaction path is the v2 LayerDM Pipeline
([ADR-0013](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0013-layerdm-pipeline-pattern.md)
§5;
[ADR-0031](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0031-distance-map-input-on-resection-plan.md)).

**Conformance.** The `qSlicerLiverMarkupsModuleTest` registration
invariant is flipped: `vtkMRMLMarkupsBezierSurfaceNode` must NOT be a
registered markups type [test].  A repo grep for the retired class names
resolves only in historical porting-note comments, never in code
[review].

## References

- [ADR-0013](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0013-layerdm-pipeline-pattern.md)
  §4 (Pipeline observes orchestrating state) + §5 (no custom DM; the
  three registration calls).
- [ADR-0014](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0014-livermarkups-dissolution.md)
  §3 — *supersedes* the standalone-widget decision (the mapper relocation
  stands).
- [ADR-0004](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0004-python-cpp-boundary.md)
  — interaction/placement UI in Python.
- [ADR-0019](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0019-resection-state-machine.md)
  — state-gated editability.
- [ADR-0031](0031-distance-map-input-on-resection-plan.md) — distance-map
  input on the plan wrapper (a consumer of this interaction path).
- `SlicerLayerDisplayableManager` `vtkMRMLLayerDMScriptedPipeline` — the
  `Can/ProcessInteractionEvent` seam this decision builds on.
- #501 (the migration this unblocks) · #493 (the render cutover whose
  slices 3–4 follow).

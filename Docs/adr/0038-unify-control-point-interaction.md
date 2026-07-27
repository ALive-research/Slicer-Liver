# 0038. Unify the control-point visualization + interaction across resection and vascular territories

- **Status:** Accepted
- **Date:** 2026-07-16
- **Deciders:** Rafael Palomar
- **Relates to:**
  [ADR-0032](0032-v2-interaction-via-layerdm-pipeline-seam.md) (interaction through the Pipeline seam),
  [ADR-0033](0033-control-polygon-display-aspect.md) (hover discipline + the control-polygon display aspect),
  [ADR-0034](0034-stage2-segments-table.md) (table paradigm),
  [ADR-0037](0037-vascular-territories-off-markups.md) (VascularTerritories off markups, which introduced the duplication);
  and the LayerDM foundation
  [ADR-0013](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0013-layerdm-pipeline-pattern.md) (one Pipeline per display-node type),
  [ADR-0004](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0004-python-cpp-boundary.md).
- **Implementation:** deferred to a follow-up issue (this ADR records the decision + shape; no code lands with it).

## Context

Two modules now render and edit **draggable control points on a
surface**, in the 3D view and the slice views, with the same affordances:

- **Resection** — `ControlPolygonPipeline` (3D) + `SliceControlPolygonPipeline`
  (slice), for the Bezier control grid.
- **VascularTerritories** — `TerritoryPlacementPipeline` (3D) +
  `TerritorySlicePipeline` (slice), for the annotation seeds (added under
  [ADR-0037](0037-vascular-territories-off-markups.md)).

The territory pair was built by **mirroring** the resection pair, so the
overlap is near-verbatim, not incidental:

- the glow-halo hover cue (a private overlay `vtkRenderer` carrying a
  `vtkOutlineGlowPass`) with a yellow-hover / green-grab colour swap;
- the slice projection into XY (`inverse(XYToRAS)`) with distance-graded
  alpha, a signed above/below side tint, and a **hard presence cutoff**
  (2D alpha is unreliable);
- hollow-circle handles + a larger hover ring; the display-space
  pick-radius arbitration (`nearest-point-in-display`);
- the press/move/release **grab** seam (ADR-0033 hover discipline: a bare
  move is declined so the camera is untouched);
- the shared constants (`HALO_HOVER_COLOR` / `HALO_GRAB_COLOR`, handle /
  ring scales, `FADE_DISTANCE_MM`, `HANDLE_MIDTONE_FACTOR`).

Maintaining two copies is already costly: the four LayerDM integration
traps found while making the territory path work in the GUI (one Pipeline
per `(view, display-node type)`; configure-before-`AddNode`;
`UpdatePipeline` fires on `ResetDisplay()` not display `Modified`;
`RequestRender` does not flush mid-`ProcessInteractionEvent`) had to be
paid **again** for territories after resection already had them.

What is **not** shared is the data model: resection has an ordered control
**grid with edges** and Init/Planning state gating; territories have
**unordered per-territory carrier points**, no edges. So a naive
"merge into one class" is wrong — the reusable part is the visualization +
interaction *affordance*, not the data.

## Decision

Extract a **shared control-point interaction/visualization base** — a 3D
base and a slice base — from the mature resection pipelines, and make
VascularTerritories (and future consumers) clients of it. The base owns the
duplicated surface above (glow halo, slice projection + fade + side tint +
presence cutoff, handles + hover ring, pick arbitration, the grab seam, the
shared constants) and the four LayerDM integration invariants, so they are
implemented and fixed **once**.

The base is parameterized by a small **point-provider seam** the consumer
supplies:

- the points to render (world positions) + their per-point base colour;
- whether the points form **edges** (resection: yes; territories: no);
- the write-backs for a drag / delete against the consumer's data model;
- the display-node channel for the shared arm/hover/grab state (ADR-0032/0033).

The base does not know about the control grid or the annotation carrier;
each module keeps its own display-node type + creator (one Pipeline per
type, ADR-0013 §1) and its own data model, wiring them to the base through
the seam.

Direction of extraction: **from resection → base**, because the resection
pipelines are the richer, battle-tested originals (edges, digest gates,
state-machine integration); territories become the second, simpler client.

## Alternatives considered

- **Keep the two copies (status quo).** Rejected — double maintenance; the
  LayerDM-trap tax is already being paid twice, and every future fix would
  diverge.
- **Merge both into a single pipeline class.** Rejected — the data models
  and lifecycle (ordered grid + edges + state machine vs unordered
  per-territory carrier points) differ enough that one class would be a
  parameter soup; the seam-parameterized base is the right factoring.
- **Share only the constants / helpers, not the pipelines.** Rejected as
  insufficient — the bulk of the duplication and the LayerDM traps live in
  the pipeline lifecycle + interaction methods, not the constants.

## Consequences

- The glow/halo/fade/pick/grab behaviour and the four LayerDM invariants
  live in one place; a fix or a UX tweak applies to both modules.
- New control-point consumers (future annotation surfaces) get the
  affordance for free by implementing the point-provider seam.
- It is a **cross-module** change (LiverResections + VascularTerritories)
  touching working interaction code, so it needs a **characterization
  safety net** first — the resection interaction must not regress — and the
  interaction-seam tests are written **once**, against the shared base
  (rather than against the soon-to-be-replaced per-module pipelines).
- Short-term the duplication stands (PR #593 shipped the territory copy);
  this ADR commits the project to converging it, not to doing it now.

## Conformance

- [future] A shared 3D + slice control-point interaction base exists; the
  resection and territory pipelines are thin clients over the
  point-provider seam.
- [future] The four LayerDM integration invariants (one-per-type,
  configure-before-add, ResetDisplay-drives-UpdatePipeline, render-flush in
  the interaction handler) are asserted once on the base.
- [review] The extraction is behaviour-preserving for the resection
  interaction (characterization tests green before + after).
- [review] Each module keeps its own display-node type + creator (ADR-0013
  §1); the base carries no data-model knowledge.

## Implementation amendment (2026-07-27)

The extraction this ADR deferred is now triggered by a **third consumer**:
LiverVolumetry moves its region-growing seed fiducials off Slicer markups
onto the shared base (discharging its
[ADR-0012](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0012-layerdm-migration-v2-scope.md)
obligation via a real off-markups migration, rather than the earlier
"compute-then-display, LayerDM marginal" reading). A third consumer is what
justifies paying the extraction now, so the deferred implementation lands
under this amendment.

### Shared home + names

The base lives in a new Python Lib package **`SlicerLiverInteractionLib`** —
a sibling to `LayerDMLib`, importable by any module's Lib. It is Python
(ADR-0004: interaction/widgets stay Python) and hosts **no** displayable
manager (ADR-0013 §5): it supplies only the Pipeline **base classes** each
module's own creator instantiates, plus the pure-VTK pick and the
display-node state accessors. Each module keeps its own three registration
calls and its own display-node type. New classes drop the `Liver` prefix
(T2.7 convention).

Concrete names (extracted **from resection**, per the Decision's direction):

- **`SurfacePick`** — the pure-VTK ray→closed-surface intersect-nearest +
  closest-point fallback with a lazy MTime-invalidated `vtkCellLocator`.
- **`PointPlacementState`** — the arm/active/module-active/carrier accessors
  on a display node, with the attribute-key namespace parameterized per
  consumer.
- **`SurfacePointPlacementPipeline3D`** / **`SurfacePointPlacementPipelineSlice`**
  — the ADR-0038 3D + slice bases owning the glow halo, slice projection +
  fade + side tint + presence cutoff, handles + hover ring, pick-radius
  arbitration, the grab seam, and the four LayerDM integration invariants.
- **`PointProvider`** — the seam: `iter_points()`, `has_edges()`,
  `add/move/delete`, the display-node channel, **and a swappable pick
  provider** (below).

Resection (`ControlPolygonPipeline` / `SliceControlPolygonPipeline`) and
VascularTerritories (`TerritoryPlacementPipeline` / `TerritorySlicePipeline`)
become thin clients over the seam; both existing characterization suites stay
green unchanged (the [review] conformance point above).

### Base extension: the pick step is swappable (surface vs in-volume)

VascularTerritories and resection place points **on a closed surface**, so
they use `SurfacePick`. LiverVolumetry seeds are **region-growing seeds** —
`vtkLiverVolumetryLogic` converts each seed to a **voxel index**
(`TransformPhysicalPointToIndex`) and grows a `ConnectedThreshold` from it, so
the seed must land **inside** the target region, not on its surface. Snapping
a volumetry seed to a surface would place it on the region boundary and can
mis-seed the grow.

Therefore the pick step is a **provider on the seam**, not a fixed
surface-snap. The base defines the point-placement/edit/delete affordance and
the LayerDM invariants once; the *pick* (world position for a click) is
supplied by the consumer:

- surface consumers (resection, territories) inject `SurfacePick`;
- LiverVolumetry injects an **in-volume / slice-click pick** — placement in a
  slice view resolves the click to the RAS point at the slice plane (an
  interior voxel), which is the natural region-growing-seed UX.

This is the single place volumetry is not a plain client. It does not leak a
volume concept into the base — the base sees only "the consumer's pick
returned this world point"; the surface-vs-volume choice is entirely in the
injected pick provider.

### Consumers ledger

- resection — client (extraction source), surface pick, edges = yes;
- vascular territories — client, surface pick (vessel-visibility-gated),
  edges = no;
- **LiverVolumetry — client, in-volume/slice pick, edges = no** (this
  amendment);
- move-bezier-off-markups (`project_move_bezier_off_markups`) — the designed
  fourth consumer once its own ADR lands (grouped `PointProvider`); the seam
  is shaped to admit it.

### Conformance (this amendment)

- [future] `SlicerLiverInteractionLib` exists with the five names above; the
  resection and territory pipelines are thin clients over the seam.
- [future] The pick step is a seam-injected provider; LiverVolumetry supplies
  an in-volume/slice pick, surface consumers supply `SurfacePick`; the base
  contains no surface-vs-volume branch.
- [review] The refactor is behaviour-preserving for resection **and**
  vascular territories (both characterization suites green, unchanged, both
  harnesses).
- [review] LiverVolumetry's C++ region-grow logic is unchanged (ADR-0015); it
  is fed a transient fiducial built from the seed carrier, and per-seed labels
  round-trip so generated segments keep their names.

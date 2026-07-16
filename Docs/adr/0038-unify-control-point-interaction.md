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

# 0033. Control polygon as a first-class display aspect

- **Status:** Accepted
- **Date:** 2026-07-08
- **Deciders:** Rafael Palomar
- **Supersedes (in part):** the interaction *siting* in
  [ADR-0032](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0032-v2-interaction-via-layerdm-pipeline-seam.md)
  ("the Pipeline now mediates both render and edit" on
  `LiverBezierSurfacePipeline`) and the per-role-glyph rendering notes in
  [ADR-0014](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0014-livermarkups-dissolution.md)
  §3.  ADR-0032's seam *mechanism* (interaction through the LayerDM
  Pipeline overrides — no widget, no custom DisplayableManager) stands
  unchanged; only *which* Pipeline hosts the control-polygon interaction
  moves.
- **PR:** <filled in on merge>

## Context

The first live render of the v2 Planning surface (real anatomy,
2026-07-08) exposed that the **control polygon** — the `Rows × Cols`
control-point handles plus their connecting edges — is not rendered at
all.  The ADR-0032 per-point drag works, but the surgeon drags blind:
`vtkSlicerLiverBezierControlPolygonGeometry.BuildControlPolygonCells`
(the Algorithm-library cells builder) has zero production consumers, and
`BezierPlanningRepresentation` renders only the surface actor (the
shader-drawn *resection grid* is a surface feature and must not be
confused with the control polygon).

Maintainer review of the first fix attempt (rendering the polygon inside
`BezierPlanningRepresentation`) identified three properties that make the
control polygon a first-class display aspect rather than surface
decoration:

1. **Distinct visual properties.** Handle radius / colours / edge styling
   share nothing with the surface's shader fields
   (margins, distance-field colouring, resection grid) — they do not
   belong on `vtkMRMLParametricSurfaceDisplayNode`.
2. **It owns interaction.** The per-point drag targets *handles*, not the
   surface.  Hosting it on the surface Pipeline forces a blanket
   `CanProcessInteractionEvent` claim; a polygon-owned Pipeline can
   return a *real* display-space distance-to-nearest-handle `distance2`,
   giving LayerDM's focus arbitration something meaningful to arbitrate.
3. **Independent visibility.** Showing/hiding the handles must not touch
   the surface — and per-view control (handles in one 3D view, not
   another) falls out of a dedicated display node's `ViewNodeIDs`.

## Decision

The control polygon becomes a first-class display aspect of the
parametric-surface carrier, using MRML's native
one-displayable-many-display-nodes pattern:

1. **`vtkMRMLControlPolygonDisplayNode`** — a new display-node type
   carrying the polygon's visual properties: `HandleRadius` (default 2.5,
   v1 glyph parity), `HandleColor`, `EdgeColor`, `EdgeWidth`.  Base
   `vtkMRMLDisplayNode` provides independent `Visibility` and
   `ViewNodeIDs`.  Registered via `RegisterNodeClass`
   ([ADR-0013](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0013-layerdm-pipeline-pattern.md)
   §5 call 1).
2. **`vtkMRMLBezierSurfaceNode::CreateDefaultDisplayNodes` mints both**
   display nodes — the surface display and the control-polygon display —
   on the same carrier.
3. **`ControlPolygonPipeline`** (Python, `LayerDMLib` base) — created by
   a factory creator keyed on `(vtkMRMLViewNode,
   vtkMRMLControlPolygonDisplayNode)` (ADR-0013 §1: one Pipeline per
   display-node type; §5 call 3).  It renders the handles (plain-VTK
   sphere glyphs over the control grid) and the polygon edges
   (`BuildControlPolygonCells` — the Algorithm-library SSOT shared with
   the v2.1 NURBS sibling per
   [ADR-0018](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0018-nurbs-extension-surface.md)),
   and is state-gated: visible in `Planning` only (hidden through
   `Init` and after `Planning → Confirmed`, preserving ADR-0014's
   Confirmed-hides-polygon behaviour via the
   [ADR-0019](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0019-resection-state-machine.md)
   state machine).
4. **Interaction migrates** (the superseding part): the Planning
   per-point drag — `CanProcessInteractionEvent` /
   `ProcessInteractionEvent` plus the nearest-control-point kernel —
   moves from `LiverBezierSurfacePipeline` to `ControlPolygonPipeline`.
   `CanProcessInteractionEvent` computes the real display-space distance
   to the nearest handle, so focus arbitration works when other
   interactive Pipelines share the view.  The Init-mode placements
   (slicing-plane / distance-spheroid points) are surface/init
   interactions and **stay** on `LiverBezierSurfacePipeline`.
5. **Forward-compatibility:** the v2.1 ring-group manipulation (grouped
   control-point drag) lands on `ControlPolygonPipeline`; the ring
   taxonomy stays in the Algorithm library beside
   `BuildControlPolygonCells`.

## Alternatives considered

### A. Render the polygon inside `BezierPlanningRepresentation`
One Pipeline renders surface + polygon; interaction stays where ADR-0032
put it.  Rejected: conflates two unrelated visual property sets on one
display node; leaves `CanProcessInteractionEvent` as a blanket claim with
no meaningful `distance2`; polygon visibility cannot be controlled
per-view or independently of the surface node's decoration fields.

### B. A standalone `vtkAbstractWidget` for the polygon
Already rejected by ADR-0032 (competing render/picker stack, second
interaction authority).  Nothing here changes that.

### C. Defer entirely to the v2.1 grouped-manipulation work
Rejected: v1 parity requires visible handles in v2.0 — the ADR-0032 drag
is unusable without them.  Only the *grouped* manipulation is v2.1.

## Consequences

**Easier.** Focus arbitration becomes real (distance-based, not
blanket); display concerns separate cleanly; the v2.1 ring-group work
has its natural home; handles can be styled/hidden/per-view'd without
touching the surface.

**Harder / new seams.**
- Two display nodes per carrier: scene IO, `CopyContent`, and the
  create path must handle both (the Pipeline late-binding hook —
  `OnReferenceToDisplayNodeAdded` — already covers the creation-ordering
  race for any number of display nodes).
- The ADR-0032 edit-seam tests migrate from the surface Pipeline to
  `ControlPolygonPipeline`.
- One more registered node class and factory creator (still within
  ADR-0013 §5's three-call contract; no custom DisplayableManager).

## Conformance

- [test] `ControlPolygonPipeline` unit invariants: handles + edges follow
  the control grid; Planning-only visibility; display-node styling
  reaches the actors; `CanProcessInteractionEvent` returns finite
  `distance2` near a handle and declines far away / in non-Planning
  states.
- [test] The migrated edit-seam invariants (drag writes
  `SetControlPoint`) run against `ControlPolygonPipeline`.
- [test] `vtkMRMLControlPolygonDisplayNode` CxxTest: defaults, XML
  round-trip, `CopyContent`.
- [review] `CreateDefaultDisplayNodes` mints both display nodes; the
  surface Pipeline no longer claims Planning-state pointer events.
- [future] Ring-group manipulation (v2.1) extends this Pipeline.

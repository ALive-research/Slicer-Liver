# 0031. Distance-map input lives on the resection-plan wrapper

- **Status:** Accepted
- **Date:** 2026-06-24
- **Deciders:** Rafael Palomar
- **Diagrams:** [`Docs/architecture/target-mrml-node-hierarchy.md`](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/architecture/target-mrml-node-hierarchy.md)
- **PR:** <filled in on merge>

## Context

The v2.0 LayerDM render path for the Bézier resection surface
(`LiverResectionsLib/Representations/BezierPlanningRepresentation.py`,
driving the relocated `vtkOpenGLBezierResectionPolyDataMapper`) is wired
to render the tessellated patch, but it renders **less** than the v1
markups path it is meant to replace. v1's
`vtkSlicerBezierSurfaceRepresentation3D` binds a distance-map 3D texture
(`CreateAndTransferDistanceMapTexture` → `SetDistanceMapTextureObject`),
computes `RasToIjkMatrixT` / `IjkToTextureMatrixT` from that volume, and
sets `ResectionMargin` / `UncertaintyMargin` — so its fragment shader
draws the resection-margin band, the uncertainty band, and the clip-out
discard. The mapper's shader
(`LiverResections/VTKWidgets/vtkOpenGLBezierResectionPolyDataMapper.cxx`)
samples `distanceTexture` unconditionally; with no texture bound and
margins at their `0.0` defaults, every fragment falls through to a flat
resection colour. The margin/uncertainty/clip-out shading is therefore
**lost** until a distance-map volume can be threaded to the v2 mapper.

Replacing v1 cannot proceed until that gap is closed: the gating
visual-regression baseline `BezierSurface4x4Planning` drives the v1 node
with a bound distance map and non-zero margins, so a cutover that cannot
reproduce the bands regresses against its own gate.

Closing the gap requires the v2 node graph to **name** the distance-map
volume so a Representation can resolve it. The v1
`vtkMRMLMarkupsBezierSurfaceNode` weak-referenced the distance map (and
the target model, and the vascular-segments volume) directly on the
surface node. The v2 dissolution
([ADR-0014](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0014-livermarkups-dissolution.md) §"Fourth layer") split the
v1 primitive into *carrier* (`vtkMRMLBezierSurfaceNode` — geometry +
state), *display* (`vtkMRMLParametricSurfaceDisplayNode`), and *storage*,
and lifted the clinical/method concerns onto a fourth **wrapper** layer,
`vtkMRMLResectionPlanNode`. That wrapper already carries the
distance-derived clinical inputs — `SafetyMargin_mm`, `RiskMargin_mm`
(`vtkMRMLResectionPlanNode.h`) — plus the `PlanState` machine and a typed
`geometry` reference to the carrier. The remaining question is purely
**where the distance-map volume reference attaches** on this graph: on
the carrier (v1 parity) or on the wrapper.

## Decision

The distance-map volume reference is a **path-specific input of the
resection plan** and lives on the wrapper
`vtkMRMLResectionPlanNode`, not on the carrier
`vtkMRMLBezierSurfaceNode`.

`vtkMRMLResectionPlanNode` gains a typed node-reference role
`distanceMap` (`GetDistanceMapReferenceRole()` returning `"distanceMap"`,
with `GetDistanceMapVolumeNode()` /
`SetAndObserveDistanceMapVolumeNode(vtkMRMLScalarVolumeNode*)`), sitting
alongside the existing `geometry` role and the `SafetyMargin_mm` /
`RiskMargin_mm` scalars — i.e. **all** distance-shading inputs (the two
margins and the distance volume the bands are measured against) cluster
on the wrapper.

`LiverBezierSurfacePipeline` — which already attaches and observes the
wrapper via `SetResectionNode()` ([ADR-0013](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0013-layerdm-pipeline-pattern.md)
§4) — resolves the distance-map volume and the two margins off the
wrapper at update time and threads them to
`BezierPlanningRepresentation`, which ports v1's
`CreateAndTransferDistanceMapTexture` + RAS/IJK matrix math onto the real
mapper. The carrier (`vtkMRMLBezierSurfaceNode`) keeps geometry + state
only; it gains **no** distance-map reference.

This realises the wrapper-vs-carrier table in
[ADR-0014](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0014-livermarkups-dissolution.md) §"Fourth layer" — *"wrapper:
clinical or method metadata **+ path-specific inputs**"* — for the
distance-map case, and it is the structural prerequisite for the v1
render cutover.

## Alternatives considered

### Alternative A — distance-map reference on the carrier (`vtkMRMLBezierSurfaceNode`)

The v1-parity placement: the surface node weak-references the distance
map directly, mirroring `vtkMRMLMarkupsBezierSurfaceNode`'s
`GetDistanceMapVolumeNode()`, and `BezierPlanningRepresentation.update()`
reads it straight off the data node it is already handed. Fastest path to
the cutover — no wrapper threading.

Rejected: it re-conflates an *input* with the *geometry carrier* — the
exact conflation [ADR-0014](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0014-livermarkups-dissolution.md)
§"Fourth layer" factored out. The distance map is a property of the
resection plan, not of the surface mesh: it is shared across the plan,
re-used by the on-commit ring extraction, and conceptually one of the
inputs that produce the geometry — not a sub-part of it. Putting it on
the carrier would also strand it from the `SafetyMargin_mm` /
`RiskMargin_mm` scalars it is measured against (which already live on the
wrapper), splitting one coherent input set across two layers, and would
duplicate the reference if a plan ever owns more than one surface
carrier. Carrier persistence is also wrapper-rooted and the carrier is
becoming non-storable (ibid.), so an input pinned to the carrier has no
natural persistence home.

### Alternative B — a free `distanceMap` attribute / hard path, no typed reference

Store the distance-map node id as a string attribute on the wrapper (or
the carrier), as the v2.0 stop-gap did for the orphaned clinical fields.

Rejected: a string id is not observed, does not survive scene
id-remapping on load, and gives the Pipeline no `Modified` signal when
the volume changes. A typed `SetAndObserveNodeReferenceID` role is the
Slicer-idiomatic mechanism and the one the wrapper already uses for
`geometry`.

## Consequences

**Easier.** The render cutover (#493) is unblocked: a single typed role
plus the ported texture/matrix math lets `BezierPlanningRepresentation`
reproduce v1's margin/uncertainty/clip-out shading, so the v1 Bézier
render can be removed without a visual-regression. All distance-shading
inputs are co-located on one node, which the Pipeline already observes.

**Harder / new seams.**

- The mapper binds a 3D texture for the first time on the v2 path, so the
  [ADR-0003](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0003-testability-invariant.md) offscreen-render abort guard
  becomes load-bearing on this path and needs an explicit invariant — the
  texture must be realised-then-bound on a live context and deactivated
  after the draw (the v1 representation's `RenderPieceFinish` discipline).
- `LiverBezierSurfacePipeline` must thread the wrapper's distance-map
  volume + margins into the Representation (extending the update
  contract); the carrier-only `update(display_node, data_node)` shape no
  longer carries everything the surface render needs.
- The `BezierSurface4x4Planning` / `BezierSurface4x4Confirmed`
  visual-regression baselines must be re-captured against the v2 path
  (with the distance map bound) before the v1 render is removed, or the
  replay gate locks in the regression.

**Follow-up work.** This ADR covers only the distance-map *input*
placement. The target-model and vascular-segments references v1 also held
on the surface node are out of scope here; if the v2 path comes to need
them on the render side they follow the same wrapper-input rule by
analogy, but each is its own decision. The render cutover itself (disable
+ retire the v1 `vtkSlicerBezierSurfaceWidget` /
`vtkSlicerBezierSurfaceRepresentation3D`) is tracked under #493 and lands
after this reference + its binding.

## Conformance

- `vtkMRMLResectionPlanNode` exposes `GetDistanceMapReferenceRole()` ==
  `"distanceMap"` and `GetDistanceMapVolumeNode()` /
  `SetAndObserveDistanceMapVolumeNode()`; grep
  `GetDistanceMapReferenceRole` should match in
  `LiverResections/MRML/vtkMRMLResectionPlanNode.*` only — **not** in
  `vtkMRMLBezierSurfaceNode.*` (the carrier must stay free of it).
- An invariant test pins that `BezierPlanningRepresentation.update()`
  binds a `distanceTexture` and sets the RAS/IJK matrices on the mapper
  **iff** the wrapper's `distanceMap` reference is populated, and binds
  none when it is absent (the graceful-fallback path this ADR preserves).
- An [ADR-0003](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0003-testability-invariant.md) abort-guard invariant:
  an offscreen render with the distance texture bound must not abort or
  hang.
- The re-captured `BezierSurface4x4Planning` baseline (replay test,
  `LiverResections/Testing/Python/replay_test.py`) must show the margin
  bands — i.e. visually match the retired v1 render.

## References

- [ADR-0014](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0014-livermarkups-dissolution.md) §"Fourth layer:
  clinical/method wrapper; wrapper-vs-carrier pattern" — the
  wrapper-carries-path-specific-inputs rule this ADR applies.
- [ADR-0013](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0013-layerdm-pipeline-pattern.md) §4 — the Pipeline observes
  the orchestrating state node (`SetResectionNode`), the mechanism that
  makes wrapper inputs reachable at render time.
- [ADR-0003](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0003-testability-invariant.md) — offscreen-render abort,
  newly load-bearing once a 3D texture binds on the v2 path.
- [ADR-0019](0019-resection-state-machine.md) — the `PlanState` machine
  the wrapper carries; this Representation is the `Planning` state.
- [ADR-0023](0023-unified-gui-stage-workflow.md) §"Class abstraction for
  surfaces" — the shared `vtkMRMLParametricSurfaceDisplayNode` + the
  carrier abstraction.
- #493 — the render cutover this reference unblocks.
- v1 source for the port:
  `LiverMarkups/VTKWidgets/vtkSlicerBezierSurfaceRepresentation3D.cxx`
  (distance-map texture upload + RAS/IJK matrices).

# 0018. NURBS as a sibling representation; variable-size control polygon

- **Status:** Proposed
- **Date:** 2026-05-18
- **Deciders:** Rafael Palomar
- **Diagrams:**
  - `Docs/architecture/target-mrml-node-hierarchy.md`
  - `Docs/architecture/surface-representation-taxonomy.md`
  - `Docs/architecture/control-grid-grouping.md`
  - `Docs/architecture/rendering-pipeline.md`
- **PR:** _filled in on merge_

## Context

The v2.0.0 Bezier-surface family was designed around a **fixed 4×4
control grid** (16 control points, degree-3 Bernstein basis):

- `vtkMRMLBezierSurfaceNode` exposes a `ControlGridSize = 48` constant
  (`3 * 4 * 4` doubles) and a `GridSize = 4` constant.
- `vtkLiverBezierWidget`'s ring-group taxonomy is named in
  [ADR-0014][adr-0014] §3 as "corners 4 + edges 8 + interior 4" —
  hard-coded counts.
- `vtkLiverBezierFitter` (per [ADR-0015][adr-0015]) instantiates a
  degree-3 Bernstein basis.
- `.lrp.json` v1 schema (per [ADR-0014][adr-0014] §5) encodes
  `controlGrid` as 48 doubles row-major.

d'Albenzio et al's SPIE Medical Imaging 2024 usability study
(*Surgeon-driven design of resection planning interfaces*) positions
NURBS — Non-Uniform Rational B-Splines — as a **valid alternative
representation** to Bezier for surgeon-defined resection surfaces.
The study's clinical motivation: certain anatomies (sharp curvature
transitions, asymmetric resection volumes) are awkward to express
with a degree-3 4×4 Bezier patch but natural with a NURBS surface
of arbitrary control-polygon size and arbitrary local degree.

Crucially: **NURBS requires a control polygon, which can be any
M×N**.  The 4×4 hard-code in the current v2.0.0 data structures is a
specialisation of the more general M×N case — it bakes a representation
choice into types that the architecture is going to want to widen.

The earlier v2.0.0 design discussion (captured in the project's PKS
log under "NURBS future variant") deferred NURBS proper to v2.1 as
"a sibling Representation alongside `BezierPlanningRepresentation`
and a `vtkLiverNurbsFitter` sibling to `vtkLiverBezierFitter`, both
without breaking architectural shape".  That commitment stands; this
ADR makes it explicit + adds the **variable-size-control-polygon
prerequisite** as v2.0.0-in-scope work.

<!--
  Cross-references below use full GitHub URLs because the scaffold
  build (per ADR-0017) explicitly excludes the older ADRs from the
  Sphinx tree via conf.py's exclude_patterns.  Cannot use MyST
  cross-refs ([](file.md)) here until the migration PR lifts those
  exclusions.  Same pattern as ADR-0017.
-->

[adr-0001]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0001-resection-three-node-assembly.md
[adr-0013]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0013-layerdm-pipeline-pattern.md
[adr-0014]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0014-livermarkups-dissolution.md
[adr-0015]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0015-cpp-algorithm-library.md
[adr-0016]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0016-code-style-and-lint.md

## Decision

Adopt **Option A**: commit to variable-size control polygons as a
v2.0.0 architectural extension; defer full NURBS (rational B-spline
basis with explicit knots and weights) to v2.1 as a sibling
representation under a single agreed data-node + Pipeline taxonomy.

The decision splits into four sub-commitments:

### 1. Two control-polygon sizes in v2.0.0: `{3×3, 4×4}` square-only

The `vtkMRMLBezierSurfaceNode` data type carries explicit `Rows` and
`Cols` integer fields (defaulting to `4` and `4`).  For the v2.0.0
release the **valid Bezier sizes are restricted to two square
shapes**:

| Shape   | Corners | Edges | Interior | Total |
|---------|---------|-------|----------|-------|
| **3×3** | 4       | 4     | 1        | 9     |
| **4×4** | 4       | 8     | 4        | 16    |

Both shapes have a natural "corners-edges-interior" three-ring
structure, which matches the project's existing ring-of-control-points
manipulation philosophy ([ADR-0014][adr-0014] §3 widget event
table).  Non-square shapes (3×4, 4×3) break ring symmetry and are
NOT admitted in v2.0.0.  Larger sizes (5×5, 5×7, etc.) are also
not admitted — they are NURBS-territory and arrive with the v2.1
NURBS sibling (see §3 below).

Setter on `vtkMRMLBezierSurfaceNode::SetRows` / `SetCols` validates
`(Rows, Cols) ∈ {(3, 3), (4, 4)}` and emits a `vtkErrorMacro` +
returns without `Modified()` on any other value (mirrors PR #350's
existing rejection pattern for forbidden state transitions).

The `ControlGrid` storage becomes a variable-length array of `3 *
Rows * Cols` doubles — either `27` (3×3 case) or `48` (4×4 case).
Downstream code that previously assumed `48` parameterizes on
`3 * Rows * Cols`:

- **`vtkLiverBezierWidget`** ring-group taxonomy parameterizes on
  the (Rows, Cols) shape:
  - 3×3: corners(4) + edges(4) + interior(1) = 9
  - 4×4: corners(4) + edges(8) + interior(4) = 16
  The right-drag-ring-group event (`TODO(T2.3 right-drag-ring-group)`)
  manipulates whichever ring set is currently selected; the
  manipulation math is the same shape per shape.
- **`vtkLiverBezierFitter`** parameterizes to degree-`(Rows-1)`
  Bernstein basis (degree-2 for 3×3; degree-3 for 4×4).  The Eigen
  normal-equation pseudo-inverse path is unchanged; only the
  basis-matrix shape parameterizes.
- **`.lrp.json` schema** bumps to v2.  v2 carries explicit `rows` +
  `cols` fields alongside `controlGrid: [3 * rows * cols doubles]`.
  v1 files (with implicit 4×4) load via the existing storage node's
  migration path; default `rows = 4, cols = 4` if the fields are
  absent.  Schema v2 validates `(rows, cols) ∈ {(3, 3), (4, 4)}` on
  load + rejects with `vtkErrorMacro` on any other shape.

The 4×4 case stays the **default** because the d'Albenzio study
identifies it as the most common surgeon-facing shape; the
architectural change is admitting the **smaller** 3×3 shape as a
valid alternative, NOT opening to arbitrary M×N.  Arbitrary M×N is
the NURBS v2.1 territory.

### 2. Single data node, parameterized — NOT a parent class

Reject the alternative of introducing a parent `vtkMRMLParametricSurfaceNode`
with `vtkMRMLBezierSurfaceNode` / `vtkMRMLNurbsSurfaceNode` subclasses.
Two reasons:

- The Bezier ↔ NURBS distinction is mathematically real but
  Pipeline-level orthogonal: every Pipeline cares about
  `(controlGrid, rows, cols, state, initMode)` regardless of whether
  the underlying interpolation is Bernstein or B-spline.  A parent
  class fragments the type surface without buying clarity.
- Slicer's MRML convention for "alternative-shape" extensions is a
  sibling node, not a subclass: `vtkMRMLModelNode` is the canonical
  example — no abstract `vtkMRMLGeometryNode` parent above it.
  Subclassing introduces dispatch surfaces (slot lookups by class
  pointer) that complicate the Pipeline registration in [ADR-0013][adr-0013] §5
  call 3.

Concretely:

- **v2.0.0**: `vtkMRMLBezierSurfaceNode` with `Rows`/`Cols` IVars.
  No `vtkMRMLNurbsSurfaceNode` yet.
- **v2.1**: `vtkMRMLNurbsSurfaceNode` lands as a peer of
  `vtkMRMLBezierSurfaceNode`, NOT a subclass.  It carries
  NURBS-specific fields the Bezier node does not: `DegreeU`, `DegreeV`,
  `KnotsU` (variable-length), `KnotsV` (variable-length), `Weights`
  (`Rows * Cols` rational coefficients).  Shared shape — `Rows`,
  `Cols`, `ControlGrid`, `ResectionState`, `InitializationMode` —
  duplicates at the field level; this is acceptable cost for clean
  per-type dispatch.

### 3. Single Pipeline per representation — NOT a polymorphic parent

Sibling Pipelines, not a polymorphic dispatch on a third axis.

- **v2.0.0**: `LiverBezierSurfacePipeline` is the only Pipeline.  It
  handles both `{3×3, 4×4}` Bezier shapes; the geometry generation
  is parameterized but the surface math (Bernstein basis, no weights,
  no knots) is fixed.
- **v2.1**: `LiverNurbsSurfacePipeline` lands as a peer Pipeline
  registered with `vtkMRMLLayerDMPipelineFactory` against
  `vtkMRMLNurbsSurfaceDisplayNode`.  Per [ADR-0013][adr-0013] §5 call 3,
  each Pipeline-creator dispatches on display-node class — so
  `vtkMRMLBezierSurfaceDisplayNode` → BezierPipeline,
  `vtkMRMLNurbsSurfaceDisplayNode` → NurbsPipeline, no class-level
  ambiguity.

Representations follow the same sibling pattern:
`BezierPlanningRepresentation` (v2.0.0) /
`NurbsPlanningRepresentation` (v2.1).  Initialization-mode
Representations (`SlicingPlaneInitRepresentation`,
`DistanceSpheroidInitRepresentation`) are agnostic — the init
points + plane + spheroid are the surgeon's input, independent of
whether the eventual fitted surface is Bezier or NURBS.  These
Representations stay shared; only the post-Init "Planning" surface
Representation differentiates.

### 4. New ADR; light amendments to ADR-0014 §3 and ADR-0015

Two existing ADRs need light amendments:

- **[ADR-0014][adr-0014] §3** — the "4×4 control grid" + "corners 4 + edges 8
  + interior 4" phrasings become "M×N control grid, defaulting to
  4×4" + "corners 4 + edges `2(M-2) + 2(N-2)` + interior `(M-2)(N-2)`".
  The Bezier-specificity language stays — ADR-0014 is the Bezier
  dissolution ADR; NURBS is documented here, in ADR-0018.
- **[ADR-0015][adr-0015]** — extension surface added: the algorithm library
  admits a future `vtkLiverNurbsFitter` sibling.  ADR-0015's
  Eigen-via-ITK-bundle linkage covers both Bezier (degree-`(N-1)`
  Bernstein) and NURBS (B-spline + weights) math.

[ADR-0014][adr-0014] §4's read-only-after-Planning contract from PR #350
is unchanged: still applies to init data only, regardless of
control-polygon size or eventual NURBS extension.

[ADR-0014][adr-0014] §5's `.lrp.json` schema commitment is unchanged in
substance; the schema bumps to v2 with explicit `rows` + `cols`
fields.  v1 files load via the migration path the storage node
already implements (legacy `Curved` mode handling from PR #361
extends naturally to legacy-implicit-4×4 handling).

## Why `{3×3, 4×4}` square-only, not arbitrary M×N in v2.0.0

The d'Albenzio study's variable-control-polygon claim covers the
**NURBS-representation space**, where the control polygon is
genuinely arbitrary.  For v2.0.0 Bezier surfaces, two arguments
favour restricting to two square shapes:

- **Ring-philosophy fit.**  The widget's right-drag-ring-group
  event ([ADR-0014][adr-0014] §3) groups control points by corners /
  edges / interior.  Both 3×3 and 4×4 have all three ring sets
  non-empty; non-square shapes (3×4, 4×3, 5×4, …) lose the corner
  symmetry and the edge-ring is unevenly split between
  row-direction and column-direction edges.  The UX gets messy.
- **Clinical signal.**  d'Albenzio's surgeon-interview data does
  not show evidence that surgeons need M×N > 4×4 for *Bezier*
  surfaces; the demand for arbitrary M×N is paired with the demand
  for the NURBS basis (local-control, knot insertion, conic-section
  reproducibility).  Bezier's degree-`(N-1)` Bernstein basis at large
  N becomes numerically unstable + has zero local control, which is
  the wrong shape for clinical-grade surface fitting at scale.

Two-shape restriction in v2.0.0 + NURBS opens the M×N space in v2.1
is the right phasing.  The architectural surface in `vtkMRMLBezierSurfaceNode`
(`Rows`/`Cols` IVars, parameterized widget + fitter) is unchanged
by the restriction — the runtime validation is the only added
constraint, and it's a single switch statement.

## Why Option A, not full NURBS in v2.0.0

The d'Albenzio study identifies the *valid-representation-space*
extension as the architectural commitment, not "ship NURBS now".  The
v2.0.0 work-in-flight (T2 LiverResections refactor) is already
substantial; admitting variable-size Bezier closes the
type-architecture door on the 4×4 specialisation **without** taking
on the NURBS-evaluation math (de Boor's algorithm, knot-vector
normalisation, rational-vs-polynomial division-by-weight) that a real
NURBS fitter needs.

Risk if v2.0.0 ships only fixed 4×4: every v2.1 NURBS PR has to
re-litigate every field that bakes 4×4 in.  Risk avoided by Option A.

Risk if v2.0.0 ships full NURBS: NURBS evaluation has known
numerical traps (weight degeneracies, knot-vector validation,
periodic-vs-clamped basis) that need their own characterisation-test
suite per [ADR-0003][adr-0003].  That suite is non-trivial; conflating it with
the existing T2 stack work overloads the v2.0.0 release.

[adr-0003]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0003-testability-invariant.md

Option A is the **minimum architectural commitment** that honours
d'Albenzio's mathematical-extensibility claim without scope creep.

## Why a single data type per representation kind, not a parent class

Subclasses are tempting (`vtkMRMLBezierSurfaceNode <:
vtkMRMLParametricSurfaceNode :> vtkMRMLNurbsSurfaceNode`) for sharing
the `Rows`/`Cols`/`ControlGrid`/state-machine fields.  Rejected
because:

- Slicer-core's MRML hierarchy avoids the "geometry-parent" pattern.
  `vtkMRMLModelNode` is a peer of `vtkMRMLMarkupsNode`, not a
  subclass of a common geometry parent.  Sibling consistency
  outweighs DRY-on-fields.
- The Pipeline-factory registration in [ADR-0013][adr-0013] §5 call 3 dispatches
  on **display-node class** (`vtkMRMLBezierSurfaceDisplayNode` vs
  `vtkMRMLNurbsSurfaceDisplayNode`).  A parent class introduces an
  isinstance / SafeDownCast cascade in the creator lambda; sibling
  classes give exact-class dispatch.
- Storage-node duality (`vtkMRMLBezierSurfaceStorageNode` vs
  `vtkMRMLNurbsSurfaceStorageNode`) extends the sibling pattern
  cleanly; a parent would force a polymorphic storage that has to
  branch on subtype anyway.

## Why sibling Pipelines, not a polymorphic third axis

The current Pipeline dispatch is `(ResectionState, InitializationMode)
→ Representation`.  Adding `RepresentationKind` (Bezier/NURBS) as a
third axis would make the slot table 3-dimensional.  Rejected because:

- The Init-mode Representations are agnostic to Bezier-vs-NURBS (init
  data is surgeon input; surface fitting is downstream).  Sharing
  them across two Pipelines is cleaner than maintaining a
  three-axis table where 2/3 of the slots are duplicates.
- The post-Init "Planning" Representation IS Bezier-vs-NURBS-specific
  (different surface generation, different shader uniforms,
  different fitter call).  Sibling Pipelines make this divergence
  explicit at the registration level.
- LayerDM's `vtkMRMLLayerDMPipelineFactory` registration model is
  "one creator per display-node type"; sibling Pipelines map 1:1.

## Consequences

**Positive:**

- v2.0.0 architectural surface admits the NURBS extension without
  retrofit.
- Variable-size Bezier is a legitimate clinical feature in its own
  right (some anatomies need 5×5 or 5×7 control polygons; the 4×4
  specialisation was a v1 limitation, not a deliberate UX decision).
- Schema v2 (`.lrp.json`) carries forward — surgeon plans authored
  with either `{3×3, 4×4}` shape round-trip cleanly; v2.1 schema v3
  will admit larger M×N for the NURBS sibling.
- The ring-group taxonomy generalizes mechanically; T2.3's
  `right-drag-ring-group` event flow inherits the formula.
- d'Albenzio et al. citation lands as a committed architectural
  reference, anchored in ADR-0018 (so it survives future drift).

**Negative:**

- The enabling PR (variable-size code parameterization) touches
  every site that hard-codes `4`, `16`, or `48`.  Substantial but
  mechanical work; characterisation tests from [ADR-0003][adr-0003] catch
  regressions on the 4×4 default.
- Schema v2 introduces a migration path (v1 → v2 implicit 4×4) that
  needs explicit test coverage (parallel to PR #361's legacy
  `.lrp.fcsv` migration).
- The eventual v2.1 NURBS work has a clearer landing zone but ALSO
  more upfront design: deciding the knot-vector representation
  (clamped vs periodic; uniform vs non-uniform), weight encoding
  (per-control-point vs implicit-1.0), and the
  fitter's least-squares formulation (linear in weights vs
  non-linear).  Deferred to a v2.1 ADR.

## Rollout plan

1. **DOC PR — this ADR + 4 architecture diagrams + ADR amendments**
   (this PR):
   - New `Docs/adr/0018-nurbs-extension-surface.md`.
   - New `Docs/architecture/target-mrml-node-hierarchy.md` —
     post-T2 + variable-size + NURBS sibling extension surface.
   - New `Docs/architecture/rendering-pipeline.md` — sequence flow
     from `vtkMRMLLayerDisplayableManager` dispatch through Pipeline,
     Representation, custom mapper, shader uniforms.
   - New `Docs/architecture/surface-representation-taxonomy.md` —
     Bezier ↔ NURBS class taxonomy + mathematical-model contrast.
   - New `Docs/architecture/control-grid-grouping.md` — ring-group
     formula for M×N + example layouts.
   - Light amendment to [ADR-0014][adr-0014] §3 (4×4 → {3×3, 4×4}).
   - Light amendment to [ADR-0015][adr-0015] (extension surface for variable-degree
     Bernstein + future NURBS fitter).
   - `sphinxcontrib-mermaid` added to `requirements-docs.txt` +
     `Docs/conf.py` extensions so the new diagrams render in the
     Sphinx build (the ADR ledger entry compiles, the architecture
     diagrams stay excluded per [ADR-0017][adr-0017]'s scaffold-scope
     `exclude_patterns`).

[adr-0017]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0017-sphinx-readthedocs.md

2. **ENH PR — variable-size code parameterization (Option A enabler)**:
   - `vtkMRMLBezierSurfaceNode`: drop `GridSize = 4`,
     `ControlGridSize = 48` constants; add `Rows`/`Cols` IVars
     (default 4, 4).  Migration in `ReadXMLAttributes`: if `rows` /
     `cols` attributes absent, default to (4, 4).
   - `vtkMRMLBezierSurfaceStorageNode`: schema v2 with explicit
     `rows` + `cols`.  Read path branches on schemaVersion (1 implies
     4×4; 2 reads explicit values).  Write path always emits v2.
   - `vtkLiverBezierWidget` + `vtkLiverBezierRepresentation`:
     ring-group generalization (corners always 4, edges + interior
     compute from `Rows`/`Cols`).
   - `vtkLiverBezierFitter`: degree-`(Rows-1)` × degree-`(Cols-1)`
     Bernstein basis.  Existing tests pin 4×4 behaviour; new tests
     pin 5×4 + 5×5 + non-square cases.
   - Characterisation tests from [ADR-0003][adr-0003] verify the 4×4 path is
     bit-identical to the pre-parameterization output.

3. **v2.1 — full NURBS** (separate ADR, not this one):
   - `vtkMRMLNurbsSurfaceNode` + display + storage sibling trio.
   - `LiverNurbsSurfacePipeline` registered with
     `vtkMRMLLayerDMPipelineFactory` for `vtkMRMLNurbsSurfaceDisplayNode`.
   - `NurbsPlanningRepresentation` siblings `BezierPlanningRepresentation`.
   - `vtkLiverNurbsFitter` siblings `vtkLiverBezierFitter`.
   - `.lrp.json` schema v3 — adds NURBS-specific fields (knots,
     weights, degree-per-axis) when `representationKind == "Nurbs"`.

## Out of scope for this ADR

- Full NURBS implementation.  Deferred to v2.1.
- Periodic / closed B-spline surfaces.  d'Albenzio's study covers
  clamped non-periodic only.
- Trimmed NURBS (NURBS surface with one or more trimming curves).
  Out of v2.0.0 + v2.1 scope; clinical motivation thin.
- Subdivision surfaces (Catmull-Clark, Loop, etc.).  Not in
  d'Albenzio's reference space.

## Cross-references

- [ADR-0001][adr-0001] — the three-node assembly (data + display + storage)
  that this ADR's M×N generalisation extends.
- [ADR-0013][adr-0013] §5 — Pipeline factory registration; the v2.1 NURBS
  sibling Pipeline lands via call 3 with `vtkMRMLNurbsSurfaceDisplayNode`
  as its display-node class.
- [ADR-0014][adr-0014] §3 — Bezier dissolution + 4×4-to-M×N amendment landed
  alongside this ADR.
- [ADR-0015][adr-0015] — algorithm library + extension surface for variable-degree
  Bernstein and the future NURBS fitter.
- [ADR-0016][adr-0016] — code style + lint enforcement; the parameterization
  PR inherits the discipline.
- [ADR-0017][adr-0017] — Sphinx/RTD scaffold; this ADR's architecture
  diagrams use Mermaid via `sphinxcontrib-mermaid`.

## References

- d'Albenzio, G. et al. *Surgeon-driven design of resection planning
  interfaces*. SPIE Medical Imaging 2024.  (Cited as the architectural
  authority for NURBS-as-sibling.)
- [The NURBS Book](https://link.springer.com/book/10.1007/978-3-642-59223-2),
  Piegl & Tiller, 2nd ed., Springer 1996/1997.  (Reference for the
  v2.1 NURBS-evaluation math.)

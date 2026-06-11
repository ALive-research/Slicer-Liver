# 0022. NURBS v2.1 design (data node, schema v3, fitter library, rendering integration)

- **Status:** Accepted (target v2.1)
- **Date:** 2026-05-19
- **Deciders:** Rafael Palomar
- **Diagrams:**
  - `Docs/architecture/target-mrml-node-hierarchy.md` (NURBS sibling node trio)
  - `Docs/architecture/surface-representation-taxonomy.md` (NURBS branch expanded with schema-v3 fields)
  - `Docs/architecture/rendering-pipeline.md` (NURBS evaluator in TES, paired with Bezier per [ADR-0020][adr-0020])
- **PR:** _filled in on merge_

## Context

[ADR-0018][adr-0018] committed NURBS as a **sibling representation**
to Bezier — a peer `vtkMRMLNurbsSurfaceNode` + peer
`LiverNurbsSurfacePipeline` + peer `NurbsPlanningRepresentation` —
**deferred to v2.1**, with v2.0.0 restricted to the two square Bezier
shapes `{3×3, 4×4}`.  That ADR fixed the architectural shape (sibling,
not subclass; sibling Pipeline, not a third dispatch axis) but
deliberately left four concrete pieces unsettled:

- The exact data-node IVar roster (knots, weights, degrees).
- The `.lrp.json` schema shape — how the discriminator between Bezier
  and NURBS lands on disk and how reader/writer compat works.
- The fitter-library choice — [ADR-0015][adr-0015]'s Amendments
  section enumerates the three candidate libraries (custom-atop-Eigen
  / OpenNURBS / CGAL) and **defers the decision to this ADR**.
- The rendering-pipeline integration with [ADR-0020][adr-0020]'s
  tess-shader rewrite — one mapper class with a shader variant, or
  two mapper subclasses sharing an ancestor.

Meanwhile the v2.0.0 work that this ADR builds on landed:

- **State machine** ([ADR-0019][adr-0019]) — `ConfirmedRepresentation`
  is surface-type-agnostic; the trim is a uniform-controlled
  fragment-shader `discard`, not a per-representation feature.
- **Variable-size Bezier enabler** (the v2.0.0 architectural enabler
  for [ADR-0018][adr-0018] §1) — `vtkMRMLBezierSurfaceNode` now
  carries `Rows`/`Cols` IVars with `{3×3, 4×4}` validation.
- **Mapper relocation** — `vtkOpenGLBezierResectionPolyDataMapper`
  lives in `LiverResections/VTKWidgets/` (the v2.1 target directory
  for the paired Bezier+NURBS mapper redesign).
- **Visual-test harness** — characterisation tests against rendered
  surfaces are routine; the NURBS work inherits the infrastructure.
- **Coverage stack** ([ADR-0021][adr-0021]) — diff coverage will be
  visible PR-by-PR on the NURBS work.

ADR-0022 fills in the four details ADR-0018 deferred.  It is a
**design ADR**, not an enabler — no code lands with it; the rollout
plan sequences the v2.1 NURBS deliverables that follow.

<!--
  Cross-references below use full GitHub URLs (same convention as
  ADR-0018 / ADR-0019 / ADR-0020) because the Sphinx scaffold's
  exclude_patterns (per ADR-0017) keep the older ADRs out of the
  toctree; MyST cross-refs would dangle.
-->

[adr-0013]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0013-layerdm-pipeline-pattern.md
[adr-0014]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0014-livermarkups-dissolution.md
[adr-0015]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0015-cpp-algorithm-library.md
[adr-0018]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0018-nurbs-extension-surface.md
[adr-0019]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0019-resection-state-machine.md
[adr-0020]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0020-gpu-tessellation.md
[adr-0021]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0021-coverage-measurement.md
[adr-0003]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0003-testability-invariant.md

## Decision 1 — Data node

Commit on a sibling `vtkMRMLNurbsSurfaceNode` peer to
`vtkMRMLBezierSurfaceNode`, **NOT a subclass** of a shared abstract
parent.  Per [ADR-0018][adr-0018] §"Why a single data type per
representation kind, not a parent class", Slicer-core's MRML
convention is peer nodes (`vtkMRMLModelNode` and `vtkMRMLMarkupsNode`
are peers, not subclasses of a hypothetical `vtkMRMLGeometryNode`);
this ADR continues that convention rather than introducing a shared
abstract `vtkMRMLParametricSurfaceNode` base.  Field-level duplication
between the two trios (`Rows`, `Cols`, `ControlGrid`, `State`,
`InitMode`) is the deliberate cost; the payoff is exact-class
dispatch in the LayerDM Pipeline factory per [ADR-0013][adr-0013] §5
call 3, no SafeDownCast cascade.

### IVar roster

| IVar | Type | Default | Constraints |
|---|---|---|---|
| `Rows` | `unsigned int` | (none — surgeon-chosen) | `Rows ≥ DegreeU + 1` |
| `Cols` | `unsigned int` | (none — surgeon-chosen) | `Cols ≥ DegreeV + 1` |
| `DegreeU` | `unsigned int` | `3` (cubic NURBS) | `2 ≤ DegreeU ≤ 3` in v2.1 |
| `DegreeV` | `unsigned int` | `3` (cubic NURBS) | `2 ≤ DegreeV ≤ 3` in v2.1 |
| `KnotsU` | `std::vector<double>` | clamped-uniform of length `Rows + DegreeU + 1` | non-decreasing |
| `KnotsV` | `std::vector<double>` | clamped-uniform of length `Cols + DegreeV + 1` | non-decreasing |
| `Weights` | `std::vector<double>` (length `Rows * Cols`) | all `1.0` (B-spline / non-rational default) | strictly positive |
| `ControlGrid` | `std::vector<double>` (length `3 * Rows * Cols`) | (none) | same shape as `vtkMRMLBezierSurfaceNode::ControlGrid`, just generally larger |
| `State` | `ResectionState` enum | `Init` | shared with Bezier per [ADR-0019][adr-0019] |
| `InitMode` | `InitializationMode` enum | `SlicingPlane` | shared with Bezier |

Notes:

- **Default degree = 3.**  Cubic NURBS is the surgical-planning
  canonical (matches degree-3 Bezier; matches CAD-industry default;
  Piegl & Tiller's "The NURBS Book" treats it as the standard
  example).  Degree-2 is admitted for ribbon-like surfaces (quadratic
  in one axis, cubic in the other) but the v2.1 UI defaults to 3
  unless the surgeon picks otherwise.
- **Higher-than-degree-3 NURBS** are not admitted in v2.1.  Numerical
  stability of de Boor's recursion degrades at high degree without
  knot-insertion preprocessing; clinical demand for higher degree is
  unclear; deferred to a future ADR.
- **Knots are clamped-uniform by default.**  Per the de Boor
  convention, the first `DegreeU + 1` entries of `KnotsU` are `0.0`
  and the last `DegreeU + 1` entries are `1.0`; the interior knots
  are uniformly spaced.  Same for `KnotsV`.  This makes the
  parametric domain `[0, 1] × [0, 1]` (same as the Bezier patch's
  parametric domain) and gives the surface interpolation at the four
  corners of the control polygon.
- **Weights default to all `1.0`** (the non-rational case).  The
  surface degenerates to a polynomial B-spline; this is the
  numerically safest default.  Per-control-point editable weights
  are reserved for v2.2 UI exposure; v2.1 admits non-uniform weights
  via the storage path (a fitter that estimates weights, or a `.lrp.
  json` that carries non-1.0 weights) but does not expose a UI for
  editing them.

### Sharing with the Bezier node — deliberate non-sharing

We considered a shared abstract `vtkMRMLParametricSurfaceNode` base
that would host `Rows`, `Cols`, `ControlGrid`, `State`, `InitMode`,
and the various Init-mode fields.  **Rejected** for v2.1 — same
reasons [ADR-0018][adr-0018] §2 rejected the parent class:

- The Pipeline factory dispatches on display-node class.  A shared
  parent introduces SafeDownCast cascades; exact-class sibling
  display-nodes give exact dispatch.
- Storage-node duality stays cleaner with two storage classes (one
  per surface type) than with one polymorphic storage class that
  branches on subtype.
- Field-level duplication is contained — five shared fields —
  acceptable cost.

A future v2.2 or v3.0 ADR may revisit this if (a) more surface types
land (T-splines, subdivision surfaces) and (b) the maintenance cost
of duplicated field declarations becomes load-bearing.  For v2.1, the
deliberate non-sharing matches the existing sibling convention.

## Decision 2 — Schema v3

The `.lrp.json` schema bumps from v2 to v3.  Schema-v2 (per
[ADR-0018][adr-0018] §1) added `rows` + `cols` alongside the legacy
`controlGrid`; schema-v3 adds a top-level discriminator and the
NURBS-only fields.

### Discriminator + new fields

```json
{
  "schemaVersion": 3,
  "surfaceType": "Bezier or NURBS — new in v3; defaults to Bezier on v2-implicit reads",
  "rows": 4,
  "cols": 4,
  "controlGrid": ["3 * rows * cols doubles, row-major"],

  "_comment_nurbs_only": "the following fields appear only when surfaceType == NURBS",
  "degreeU": 3,
  "degreeV": 3,
  "knotsU": ["rows + degreeU + 1 doubles, non-decreasing"],
  "knotsV": ["cols + degreeV + 1 doubles, non-decreasing"],
  "weights": ["rows * cols doubles, all positive"]
}
```

### Reader compat matrix

| File schema | `surfaceType` | Reader interpretation |
|---|---|---|
| v1 (no `rows`/`cols`/`surfaceType`) | implicit | 4×4 Bezier per [ADR-0018][adr-0018] §1 migration path |
| v2 (`rows`+`cols`; no `surfaceType`) | implicit `"Bezier"` | Bezier with declared `(rows, cols)` ∈ `{(3,3), (4,4)}` |
| v3 + `surfaceType == "Bezier"` | explicit `"Bezier"` | same as v2 with the discriminator made explicit |
| v3 + `surfaceType == "NURBS"` | explicit `"NURBS"` | full NURBS path; degree + knots + weights consumed |

The writer always emits **schema v3 + the most specific
`surfaceType` + the minimum redundant fields**.  Bezier writes omit
`degreeU`/`degreeV`/`knotsU`/`knotsV`/`weights` (they have no
meaning for the Bernstein basis); NURBS writes include all of them.

### Validation rules per surface type

The storage-node `Read` path runs surface-type-aware validation and
rejects malformed input with `vtkErrorMacro` (no `Modified()`,
matching the rejection convention from the variable-size Bezier
enabler):

- **Bezier** (`surfaceType == "Bezier"` or absent):
  - `(rows, cols) ∈ {(3, 3), (4, 4)}` per [ADR-0018][adr-0018] §1.
  - `len(controlGrid) == 3 * rows * cols`.
- **NURBS** (`surfaceType == "NURBS"`):
  - `2 ≤ degreeU ≤ 3` and `2 ≤ degreeV ≤ 3` (v2.1 degree range).
  - `rows ≥ degreeU + 1` and `cols ≥ degreeV + 1` (non-empty basis).
  - `len(knotsU) == rows + degreeU + 1` and
    `len(knotsV) == cols + degreeV + 1` (de Boor convention).
  - `knotsU` and `knotsV` non-decreasing; clamped at both ends
    (first `degreeU + 1` entries equal each other, last
    `degreeU + 1` entries equal each other; same for V).
  - `len(weights) == rows * cols` and every weight strictly
    positive.
  - `len(controlGrid) == 3 * rows * cols`.

JSON-rejection tests pin every one of these constraints (mirrors
the v2 JSON-rejection test suite from commit
`012c28e — ENH: Add JSON-rejection tests for out-of-range +
controlGrid-length-mismatch`).

## Decision 3 — Fitter library

Adopt **custom-atop-Eigen** for the v2.1 `vtkLiverNurbsFitter`.

[ADR-0015][adr-0015]'s Amendments section enumerates the three
candidates: custom-atop-Eigen, OpenNURBS (BSD-3, McNeel), and CGAL
(license-incompatible — GPL on the relevant packages, viral against
Slicer-Liver's BSD-3).  CGAL is already rejected by [ADR-0015][adr-0015]
on license grounds; the real choice is between custom-atop-Eigen and
OpenNURBS.

### Why custom-atop-Eigen

- **Eigen is already a transitive dependency** of Slicer-Liver via
  ITK's bundled `ITKInternalEigen3` tree (per [ADR-0015][adr-0015]
  §2's build-system addition).  No new external dependency surface
  is introduced.  OpenNURBS would add a fresh transitive dep with
  its own geometry-kernel types that do not interop directly with
  `vtkPolyData`.
- **Full control over the de Boor evaluator** plus the NURBS
  least-squares fitter (basis-times-weights Levenberg-Marquardt
  minimisation if/when rational fitting lands; linear least-squares
  on the basis matrix for the non-rational degenerate case).  The
  v2.1 fitter only needs the subset of NURBS math Slicer-Liver
  exercises — clamped non-periodic surfaces, degree-2 / degree-3,
  fixed-knot least-squares fit.  OpenNURBS's API surface (~50 KLOC,
  full Rhino geometry kernel) is vastly larger than that subset.
- **Mathematically well-documented.**  Piegl & Tiller's "The NURBS
  Book" §2.5 (de Boor recursion), §3.4 (NURBS surface evaluation),
  §9.4 (least-squares surface fitting) cover the v2.1 algorithm
  needs end-to-end.  Implementing that subset directly is a
  bounded ~500-1500 LOC exercise, well-understood, with
  characterisation tests per [ADR-0003][adr-0003] pinning each
  algorithm output to documented numerical tolerance.
- **License clarity.**  Eigen is MPL2 (already accepted in
  Slicer-Liver per [ADR-0015][adr-0015] §2).  No new license
  posture is introduced.  OpenNURBS is BSD-3, which is compatible,
  but the agnosticism cost — none of OpenNURBS's API would be reused
  outside this module — is real.

### Why not OpenNURBS

- **Transitive-dependency footprint.**  OpenNURBS adds ~50 KLOC of
  source to the Slicer-Liver build.  The Slicer extension build
  surface is already substantial; minimising new transitive deps
  honours [ADR-0015][adr-0015] §"Alternatives B/D"'s rejection of
  CGAL/libigl/ITK-mesh on the same grounds.
- **API impedance.**  OpenNURBS exposes its own geometry-kernel
  types (`ON_NurbsSurface`, `ON_3dPoint`, `ON_Mesh`).  Adapting
  between those and Slicer-Liver's `vtkPolyData`/`Eigen::MatrixXd`
  pipeline adds a marshalling seam at every algorithm boundary.
- **Future deprecation risk.**  OpenNURBS is maintained by McNeel
  (Rhino's vendor); long-term support tracks Rhino's commercial
  roadmap, not the OSS community.  Custom-atop-Eigen is fully
  in-tree.

### Why not CGAL

Already rejected by [ADR-0015][adr-0015]'s Amendments section on
licensing.  CGAL's NURBS coverage is incomplete in any case (its
`Polynomial`/`Algebraic_kernel` packages do not provide a
high-level NURBS surface API).  Not re-litigated here.

### Maintenance trade-off

Writing a NURBS fitter from scratch is **maintenance debt**.
Mitigations:

- Characterisation tests per [ADR-0003][adr-0003] pin every algorithm
  output against either (a) a Piegl & Tiller worked example with
  hand-computed expected values, or (b) a pyefd-style reference
  implementation in NumPy (parallel to the v2.0.0 Bezier
  characterisation tests).
- The fitter subset is bounded — de Boor evaluation, clamped-knot
  generation, linear least-squares fit on a fixed basis.  No
  knot-insertion, no degree elevation, no rational fitter in v2.1
  (weights default to `1.0`; the fitter solves the polynomial
  B-spline case).
- If maintenance debt accumulates, the ADR is reversible: swap to
  OpenNURBS in a future v2.2 / v3.0 ADR; the data-node + schema
  contracts above are library-agnostic.

## Decision 4 — Rendering-pipeline integration

Adopt a **single mapper class with a `surfaceType` shader variant**
covering both Bezier and NURBS surfaces, paired with
[ADR-0020][adr-0020]'s tess-shader rewrite.

[ADR-0020][adr-0020] §"Sub-decision 1: Surface tessellation" commits
that the Bezier+NURBS migration to a tess-shader mapper is
**paired** — both representations swap to the tess mapper together
in v2.1, sharing the TES pipeline stage.  This ADR completes that
commitment by picking between two viable architectures:

- **A. One mapper class with conditional TES.**  Single
  `vtkOpenGLParametricSurfaceMapper` (or similar) subclassing
  `vtkOpenGLPolyDataMapper`; a uniform / shader-variant key picks
  between Bernstein (Bezier) and de Boor (NURBS) evaluators in the
  TES stage.  Two TES source variants; one mapper.
- **B. Two mapper subclasses sharing a common ancestor.**
  `vtkOpenGLBezierTessellationMapper` and
  `vtkOpenGLNurbsTessellationMapper` siblings under a common
  `vtkOpenGLParametricSurfaceMapper` base.  Two TES files; two
  mapper classes.

### Choice: Option A

Single mapper class, conditional TES.  Rationale:

- **Matches the polymorphic-data-node design.**  The data-node
  classes are siblings (no shared parent); the rendering surface
  collapses both into a single mapper that picks the basis at
  shader-compile time.  The dispatch lives in the **shader**, not
  in the C++ type hierarchy.
- **Smaller C++ surface area.**  One class to maintain, one set of
  uniform binds, one `ReplaceShaderValues` override.  The TCS / VS
  / FS stages are identical between Bezier and NURBS (per
  [ADR-0020][adr-0020] §"What changes in v2.1" — the fragment shader
  is unchanged from v2.0.0; tess output produces `(u, v)` for the
  FS regardless of how the surface was evaluated).
- **Shader-variant infrastructure is established.**  VTK's
  `ReplaceShaderValues` machinery routinely picks between shader
  variants based on uniform state.  The Bezier-vs-NURBS branch
  joins the existing variant dimensions (grid-overlay on/off,
  trim on/off, distance-map on/off) cleanly.

### Trade-off vs Option B

The single-class approach concentrates complexity in one place.
If the TES variant count grows (T-splines, subdivision surfaces),
the single-mapper TES could become unwieldy and Option B becomes
more attractive.  In v2.1 with two TES variants (Bernstein +
de Boor) the single class is comfortably manageable; the ADR is
reversible if v2.2 adds more representations.

### Display-node trio

Per [ADR-0018][adr-0018] §3 the Pipeline factory dispatches on
**display-node class**.  The mapper is single-class but the
**Pipelines are sibling** — `LiverBezierSurfacePipeline` and
`LiverNurbsSurfacePipeline` — and each Pipeline owns its
representation's mapper instance.  The single mapper class is
parameterised at construction time (`SetSurfaceType(Bezier|NURBS)`);
the Pipeline picks the right value when wiring the Representation.

## Out of scope (v2.1)

- **Trimmed NURBS surfaces.**  Per [ADR-0018][adr-0018]'s "Out of
  scope".  Clinical motivation thin; trimming-curve plumbing through
  the storage + Pipeline + mapper is a separate design exercise.
- **T-splines, Catmull-Clark, Loop, hierarchical NURBS.**  Per
  [ADR-0018][adr-0018].  None of these are in d'Albenzio et al.'s
  reference space.
- **Higher-than-degree-3 NURBS.**  Numerical stability + clinical
  demand both argue for deferring this to a future ADR.
- **Animation / time-varying control points.**  Not in v2.x.
- **Per-control-point editable weights via the v2.1 UI.**  Weights
  default to `1.0`; the storage path can carry non-unit weights (a
  weight-estimating fitter, or a user-authored `.lrp.json`) but the
  v2.1 module widget does not expose a UI for editing them.
  Deferred to v2.2.
- **GPU-side knot-vector storage optimisation.**  v2.1 uploads the
  full knot vector as a uniform array (small — ~`Rows + DegreeU + 1`
  doubles, single-digit kilobytes at most).  Compressed-knot
  indices are out of scope; revisit if profiling shows uniform-
  upload latency.
- **Cross-platform GL-profile compatibility.**  Covered by
  [ADR-0020][adr-0020]'s compatibility-spike requirement — same
  spike validates Bezier and NURBS tess paths together.
- **NURBS curves** (1D, as opposed to surfaces).  Not on the v2.1
  roadmap; would land as a separate `vtkMRMLNurbsCurveNode` family
  if clinical need surfaces.

## What changes in v2.1

| Layer | v2.0.0 (Bezier-only) | v2.1 (Bezier + NURBS sibling) |
|---|---|---|
| MRML node tree | `vtkMRMLBezierSurfaceNode` (+ display + storage) | + `vtkMRMLNurbsSurfaceNode` (+ display + storage); sibling, no shared parent |
| Storage schema | `.lrp.json` v2 (`rows`/`cols`) | `.lrp.json` v3 (`surfaceType` discriminator; +`degreeU`/`degreeV`/`knotsU`/`knotsV`/`weights` when NURBS) |
| Storage reader | accepts v1 (implicit 4×4 Bezier) + v2 (explicit Bezier shape) | additionally accepts v3 (explicit Bezier OR NURBS) |
| Storage writer | emits v2 | always emits v3 + most-specific `surfaceType` + minimum redundant fields |
| Pipeline dispatch table | `(Bezier, state, initMode)` rows | + `(NURBS, state, initMode)` rows — sibling Pipeline, NOT a third dispatch axis |
| Representation set | `BezierPlanningRepresentation`, `ConfirmedRepresentation`, init-mode Reps | + `NurbsPlanningRepresentation`; `ConfirmedRepresentation` + init-mode Reps shared (trim is uniform-controlled, surface-type-independent) |
| Rendering mapper | `vtkOpenGLBezierResectionPolyDataMapper` (CPU Bernstein → `vtkPolyDataMapper`) | Single `vtkOpenGLParametricSurfaceMapper` with `surfaceType` shader variant (Bernstein OR de Boor + weights) — paired migration per [ADR-0020][adr-0020] |
| Algorithm consumers (distance map, resectogram, exports) | CPU `vtkBezierSurfaceSource` | + CPU NURBS evaluator (`vtkLiverNurbsSurfaceSource`, Piegl & Tiller §3.4) — custom-atop-Eigen per Decision 3 |
| Fitter | `vtkLiverBezierFitter` (Eigen, Bernstein) | + `vtkLiverNurbsFitter` (Eigen, de Boor) — sibling under `LiverResections/Algorithm/` per [ADR-0015][adr-0015] |

## Rollout plan

The v2.1 NURBS work sequences as five deliverables, each landing in
its own PR.  Diff-coverage on each PR is visible per
[ADR-0021][adr-0021].

1. **NURBS-1 — Data node + storage.**  `vtkMRMLNurbsSurfaceNode` +
   `vtkMRMLNurbsSurfaceDisplayNode` + `vtkMRMLNurbsSurfaceStorageNode`
   + schema v3 reader/writer.  Round-trip tests for v1/v2/v3
   `.lrp.json` files (v1 → Bezier 4×4 implicit; v2 → Bezier explicit
   shape; v3 → Bezier or NURBS depending on `surfaceType`).
   Surface-type-aware JSON-rejection tests (length mismatches,
   degree out of range, knot-vector length mismatch, non-positive
   weights, non-clamped knots).  Independent of all rendering work.

2. **NURBS-2 — CPU evaluator.**  `vtkLiverNurbsSurfaceSource`
   (sibling to `vtkBezierSurfaceSource`) — custom-atop-Eigen
   de Boor evaluator per Decision 3.  Used by the v2.0.0-style CPU
   rendering fallback + by downstream algorithms (distance map,
   resectogram, exports per [ADR-0015][adr-0015]).
   Characterisation tests against Piegl & Tiller §3.4 worked
   examples; tolerance documented per test case.  Independent of
   the mapper redesign.

3. **NURBS-3 — Pipeline + Representation.**
   `LiverNurbsSurfacePipeline` registered with the LayerDM
   pipeline factory against `vtkMRMLNurbsSurfaceDisplayNode` (per
   [ADR-0013][adr-0013] §5 call 3); `NurbsPlanningRepresentation`
   siblings `BezierPlanningRepresentation`; init-mode + Confirmed
   Reps shared per [ADR-0019][adr-0019].  Wires the new node into
   the v2 LayerDM path.  Depends on NURBS-1 + NURBS-2.

4. **NURBS-4 — Fitter.**  `vtkLiverNurbsFitter` sibling to
   `vtkLiverBezierFitter` under `LiverResections/Algorithm/`.
   Least-squares fit of a clamped-knot non-rational NURBS surface
   to a parameterised ring (same input contract as the Bezier
   fitter; output is a `vtkMRMLNurbsSurfaceNode`-compatible
   control-grid + knot + weight set).  Init→Planning transition
   for the NURBS surface type wires through this.

5. **NURBS-5 — GPU tess mapper (paired with [ADR-0020][adr-0020]
   enabler).**  Single `vtkOpenGLParametricSurfaceMapper` covering
   both Bezier and NURBS via shader variant; tess-shader rewrite
   per [ADR-0020][adr-0020]'s rollout plan.  This is the
   [ADR-0020][adr-0020] enabler PR; it depends on NURBS-1 + NURBS-2
   having pinned the data model + CPU evaluator equivalence (the
   characterisation tests that pin CPU-vs-GPU surface-point
   equality use the CPU evaluator as the reference).

6. **NURBS-6 (optional) — UI exposure.**  Module-widget pickers
   for "create NURBS surface" + degree/size selectors.  Optional
   for v2.1; can slip to v2.1.1 if clinician-validated UX needs
   more iteration time.  Per-control-point weight editing is
   explicitly out of scope here (deferred to v2.2).

## Consequences

**Positive:**

- Full NURBS surface support in v2.1.  Surgeons get smooth
  degree-3 surfaces over non-square control polygons; the
  d'Albenzio et al. clinical motivation lands.
- **Rendering pipeline single-source design.**  Bezier and NURBS
  share the tess mapper, the fragment shader, the trim, the grid
  overlay, the margin colouring — everything in
  [ADR-0020][adr-0020]'s "What does NOT change" list carries
  forward.  One mapper to maintain; one shader-uniform contract.
- **Schema-v3 reader is backward-compatible** to v1 and v2.
  Existing surgeon plans round-trip; new NURBS plans load on any
  future v2.1+ build.
- **Fitter library footprint stays minimal.**  No new external
  dependency; Eigen-via-ITK-bundle stays the algorithm-library
  base.

**Negative:**

- **Larger surface area** — three new MRML node classes, one new
  Pipeline, one new Representation, one new fitter, one new CPU
  evaluator, schema-v3 reader/writer migration, single mapper's
  shader variant.  Roughly 5-10 KLOC of code + tests + docs.
- **Custom-atop-Eigen fitter is maintenance debt.**  Mitigated by
  characterisation testing per [ADR-0003][adr-0003] + bounded
  scope (no knot insertion, no degree elevation, no rational
  fitter in v2.1).  Reversible if maintenance cost exceeds
  benefit.
- **v2.1 release timeline grows.**  Six deliverables (NURBS-1
  through NURBS-6) is substantial; NURBS-5 is paired with
  [ADR-0020][adr-0020]'s tess-shader rewrite which itself depends
  on the compatibility spike.  Realistic v2.1 scope.

## References

- [ADR-0013][adr-0013] — Pipeline / Representation pattern.  The
  new `LiverNurbsSurfacePipeline` slots in via the existing
  factory registration model.
- [ADR-0014][adr-0014] §3 — LiverMarkups dissolution.  The v2
  LayerDM path NURBS lands on.
- [ADR-0015][adr-0015] — C++ algorithm library landscape.  The
  fitter-library decision (Decision 3) references its Amendments
  section directly.
- [ADR-0018][adr-0018] — NURBS-as-sibling + variable-size Bezier.
  The architectural commitment this ADR fills in.
- [ADR-0019][adr-0019] — Resection state machine.  Confirmed
  state is surface-type-agnostic; `ConfirmedRepresentation` is
  shared.
- [ADR-0020][adr-0020] — GPU tessellation.  The NURBS evaluator in
  TES is paired with Bezier here; single-mapper shader variant.
- [ADR-0021][adr-0021] — Coverage measurement.  Diff coverage on
  each of the NURBS-1 through NURBS-6 PRs.

- Piegl, L. & Tiller, W. *The NURBS Book*, 2nd ed., Springer
  1996/1997.  Reference for de Boor's algorithm (§2.5), NURBS
  surface evaluation (§3.4), and least-squares surface fitting
  (§9.4).
- d'Albenzio, G. et al. *Surgeon-driven design of resection
  planning interfaces.*  SPIE Medical Imaging 2024.  Cited via
  [ADR-0018][adr-0018] as the clinical authority for NURBS-as-
  sibling.

# 0020. GPU tessellation of parametric surfaces (v2.1 target)

- **Status:** Proposed (target v2.1)
- **Date:** 2026-05-18
- **Deciders:** Rafael Palomar
- **Diagrams:** N/A (deferred; class diagram lands with the ADR-0020 enabler PR)
- **PR:** _filled in on merge_

## Context

The v2.0.0 rendering path generates Bezier-surface geometry on the
**CPU**:

- An upstream filter (`vtkBezierSurfaceSource` or equivalent)
  evaluates the Bernstein basis on a fixed `(uSteps × vSteps)`
  parametric grid and emits a polygonal `vtkPolyData`.
- The polygonal mesh is uploaded to GPU on every control-point edit
  (192 bytes of control points → re-tessellated to a few hundred
  triangles → re-uploaded).
- The custom mapper
  [`vtkOpenGLBezierResectionPolyDataMapper`](https://github.com/ALive-research/Slicer-Liver/blob/preview/LiverMarkups/VTKWidgets/vtkOpenGLBezierResectionPolyDataMapper.cxx)
  consumes the polygonal mesh, runs **vertex + fragment shaders
  only** (no tessellation shader, no geometry shader), and decorates
  the surface with:
  - parenchyma-trim shader (uniform-controlled `discard` per
    [ADR-0019][adr-0019] `ConfirmedRepresentation`).
  - fragment-shader grid overlay (`tan(uv * π * gridDivisions) >
    thickness`).
  - margin colour stops + uncertainty interpolation (signed-distance
    field sampled from a 3D `distanceTexture`).
  - corner-quadrant markers.

This works.  v2.0.0's T2-mapper-relocation lifts-and-shifts the
legacy mapper into `LiverResections/VTKWidgets/` without changing
its CPU-tessellation shape.

Two architectural pressures push toward GPU tessellation post-v2.0.0:

- **[ADR-0018][adr-0018] §3 — v2.1 NURBS sibling.**  NURBS evaluation is the
  textbook tessellation-shader case: a B-spline control polygon
  (`Rows × Cols` control points) becomes a `GL_PATCHES` primitive;
  the tess control shader (TCS) sets LOD-adaptive tess factors;
  the tess evaluation shader (TES) evaluates de Boor's algorithm at
  each tessellated parametric point.  Building a NURBS-specific
  *CPU* tessellator is a substantial rewrite of math that GPU
  shaders already do natively.
- **Editing latency at higher tessellation density.**  For
  visual-quality reasons (especially at high zoom), surgeons may
  want denser tessellation than the current CPU pipeline gives.
  CPU mesh rebuild on every control-point drag scales linearly with
  triangle count; GPU tessellation pushes the work to the GPU
  pipeline where it's free (per-frame, never recomputed unless
  control points change).

[adr-0013]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0013-layerdm-pipeline-pattern.md
[adr-0014]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0014-livermarkups-dissolution.md
[adr-0015]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0015-cpp-algorithm-library.md
[adr-0018]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0018-nurbs-extension-surface.md
[adr-0019]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0019-resection-state-machine.md

## Decision

**Commit GPU tessellation as a v2.1 target** for the rendering
mapper(s) of both `vtkMRMLBezierSurfaceNode` (the {3×3, 4×4} Bezier
shapes from [ADR-0018][adr-0018]) and the v2.1
`vtkMRMLNurbsSurfaceNode` sibling.

The migration is **paired**: Bezier + NURBS swap to tess-shader
mappers together in v2.1, rather than retrofitting Bezier alone in
v2.0.0.  The shared TES-based design covers both representations
with two slightly different evaluators (Bernstein for Bezier; de
Boor + rational weights for NURBS).

### What changes in v2.1

| Layer                              | v2.0.0 (lift-and-shift)                                  | v2.1 (post-ADR-0020)                                        |
|------------------------------------|----------------------------------------------------------|-------------------------------------------------------------|
| Mapper input                       | Polygonal `vtkPolyData` (CPU-tessellated)                | 16 control points (or `Rows*Cols` for NURBS) as `GL_PATCHES` |
| Primitive type                     | `GL_TRIANGLES` (Slicer-core default)                     | `GL_PATCHES` with `glPatchParameteri(GL_PATCH_VERTICES, ...)` |
| Vertex shader                      | Pass-through + UV coord forwarding                       | Pass-through control point to TCS                            |
| Tess control shader (TCS)          | absent                                                   | New — sets tess factors (LOD-adaptive vs camera distance)    |
| Tess evaluation shader (TES)       | absent                                                   | New — evaluates Bernstein (Bezier) or de Boor (NURBS) at tess point |
| Geometry shader                    | absent                                                   | absent                                                       |
| Fragment shader                    | parenchyma trim + grid overlay + margin colour + corner markers (unchanged) | **identical** to v2.0.0 fragment shader; tess output is the same parametric (u, v) the FS already operates on |
| Mapper class                       | `vtkOpenGLBezierResectionPolyDataMapper` (lift-and-shift)| New subclass managing `GL_PATCHES` primitive + tess-shader injection |
| Custom OpenGL mapper hooks         | `ReplaceShaderValues` (Vertex + Fragment slots)          | `ReplaceShaderValues` + new TCS/TES slots (custom VTK hooks) |

### What does NOT change

- **Pipeline + Representation pattern** ([ADR-0013][adr-0013]).
  The Representation owns its mapper.  Swapping the mapper inside
  `BezierPlanningRepresentation` (and the new
  `NurbsPlanningRepresentation` sibling) is mapper-internal; the
  Pipeline dispatch + widget binding + display node + data node are
  unaffected.
- **Fragment-stage decoration**.  Parenchyma trim, grid overlay,
  margin colour stops, corner-quadrant markers — all stay in the
  fragment shader, unchanged.  Tess output produces the same
  `(u, v)` parametric surface coordinate the FS already operates on.
- **Distance map + Resectogram + downstream algorithms** ([ADR-0015][adr-0015],
  T3).  These consume the surface as CPU `vtkPolyData`.  CPU
  evaluation via `vtkBezierSurfaceSource` stays for those algorithm
  paths; only the rendering mapper moves to GPU.
- **Per-state Representation contract** ([ADR-0019][adr-0019]).
  `ConfirmedRepresentation` continues to share the same mapper as
  `BezierPlanningRepresentation` with `uResectionClipOut` uniform
  flipped — the trim is still a fragment-stage `discard`,
  unaffected by where the tessellation happens.

## Why GPU tessellation (not geometry shader, not status quo)

| Option | Mechanism | OpenGL profile | Trade-off |
|---|---|---|---|
| **A. Status quo** | CPU `vtkBezierSurfaceSource` → `vtkPolyDataMapper` (lift-and-shifted via T2-mapper-relocation) | 3.2+ | Works.  Static LOD.  CPU rebuild on every edit.  Bounded triangle count by what the CPU evaluator emits. |
| **B. GPU tessellation shader** (this ADR's target) | TCS + TES; `GL_PATCHES` primitive | **4.0+** | LOD-adaptive; no CPU rebuild on edit; smooth at any zoom; ~192 bytes uploaded per edit vs MB of triangle mesh.  NURBS-natural. |
| **C. GPU geometry shader** | Single-stage GS; bounded output | 3.2+ | Works on older GL.  Geometry-shader output bounded; less efficient than tess; tessellation is what shaders were designed for.  Rejected. |

GPU tessellation is the textbook answer for parametric surfaces.
Option C is rejected on principle (geometry shaders are general-purpose;
parametric surfaces have a purpose-built shader stage).  Option A is
the v2.0.0 state because the legacy already exists + works; the
question is when (not if) to migrate to B.

## Why v2.1, not v2.0.0

Three pragmatic reasons:

1. **The legacy mapper works.**  T2-mapper-relocation's narrowest
   scope is lift-and-shift; "redesign the mapper" is scope creep on
   an already-substantial v2.0.0 release.
2. **NURBS is the natural pair.**  NURBS evaluation in TES (de Boor's
   algorithm) is the canonical use case for tess shaders.  Doing
   Bezier-tess in v2.0.0 and NURBS-tess in v2.1 means two passes at
   the same design space.  Pairing them in v2.1 amortises the
   mapper-design work over both representations.
3. **Compatibility risk.**  Slicer's VTK supports tess shaders via
   `vtkOpenGLPolyDataMapper`'s shader-modification API, but the
   tess-shader injection path is less battle-tested than VS+FS.
   macOS GL 4.1 has known tess-shader quirks (Apple-deprecated GL
   stack).  A v2.1 spike PR before the enabler PR lets us verify
   VTK's tess plumbing + cross-platform compatibility before
   committing.  The v2.0.0 release path doesn't need that
   investigation gating it.

## What needs to land before the ADR-0020 enabler PR

1. **T2-mapper-relocation merged** (v2.0.0).  The legacy mapper lives
   in `LiverResections/VTKWidgets/` and the relocated trim +
   grid-overlay + margin shaders are stable + reachable from the
   Representations.  This is the v2.0.0 baseline.
2. **[ADR-0018][adr-0018] NURBS-as-sibling merged** + the v2.1 NURBS
   ADR (separate, future) is drafted.  The mapper design depends on
   knowing the NURBS data-node + display-node + Pipeline shape so
   the v2.1 mapper covers both representations from day 1.
3. **Compatibility spike PR.**  A small experimental PR that
   stand-alone tests `glPatchParameteri(GL_PATCH_VERTICES, 16)` +
   TCS/TES + Bernstein evaluation in a Slicer process across
   Linux + macOS + Windows.  If VTK's tess plumbing or
   cross-platform GL profile fails the spike, fall back to a
   custom-OpenGL-context approach (a deeper rewrite than VTK's
   shader-modification API supports).
4. **macOS GL 4.1 quirks.**  Tested patch-vertex-count limits +
   tess factors + Bernstein basis evaluation on Apple Silicon
   (Metal-via-MoltenVK or native GL?).  Decision: if macOS is too
   constrained, gate the GPU-tess path behind a runtime check that
   falls back to CPU tessellation on unsupported platforms.

## Consequences

**Positive:**

- LOD-adaptive Bezier + NURBS rendering.  Close-up view = dense
  triangulation; far view = sparse; the surface stays smooth at any
  zoom.
- Edit latency improves at high tessellation densities.  Currently
  bounded by CPU mesh upload; tess-shader path uploads only the
  control polygon.
- NURBS evaluation lands on its natural shader stage (TES with de
  Boor) instead of needing a CPU implementation of the same math.
- Fragment shader is unchanged — the v2.0.0 work on parenchyma
  trim + grid overlay + margin shading carries forward verbatim.

**Negative:**

- v2.1 enabler PR is non-trivial — custom mapper subclass + TCS +
  TES + draw-call primitive type override.  Multi-week effort.
- macOS GL 4.1 stack is Apple-deprecated.  Future Slicer-core may
  move to Metal-via-MoltenVK or a Vulkan port; tess-shader code
  written for OpenGL 4.0+ may need rewriting at that point.
- Downstream algorithms (distance map, resectogram, exports) still
  need CPU evaluation.  Two evaluators (CPU + GPU) live in
  parallel — they MUST agree on Bernstein semantics.  Either share
  the CPU `vtkBezierSurfaceSource` between rendering's CPU
  fallback and the algorithm path, OR add a characterisation test
  ([ADR-0003][adr-0003]) that pins CPU-vs-GPU surface-point equality
  to numerical tolerance.

[adr-0003]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0003-testability-invariant.md

## Rollout plan (post v2.0.0)

1. **v2.1 NURBS ADR** lands first.  Defines `vtkMRMLNurbsSurfaceNode`
   shape, schema v3 fields (knots, weights, degrees), library choice
   for the fitter (custom-atop-Eigen / OpenNURBS / per
   [ADR-0015][adr-0015]'s landscape).
2. **Compatibility spike PR.**  Validates VTK tess-shader plumbing +
   cross-platform GL profile.
3. **ADR-0020 enabler PR.**  New `vtkOpenGLParametricSurfaceMapper`
   (or similar) subclassing `vtkOpenGLPolyDataMapper` with `GL_PATCHES`
   binding + TCS + TES.  Bezier evaluator in TES; NURBS evaluator
   added in a sibling shader once the NURBS data path lands.
   `BezierPlanningRepresentation` swaps from the lift-and-shifted
   legacy mapper to the new tess mapper.
4. **Architecture diagram update.**  `rendering-pipeline.md` class
   diagram + sequence diagram regenerated to show the
   `GL_PATCHES`-based mapper + TCS/TES.  Compatibility-fallback
   path documented if macOS gates the runtime-tess decision.
5. **Characterisation test.**  Per [ADR-0003][adr-0003], pin the
   GPU-rendered surface's (u, v) → world-space mapping to byte
   equality against the CPU `vtkBezierSurfaceSource` at the
   `vtkLiverBezierFitter`-test tolerance.

## Out of scope for this ADR

- Subdivision surfaces (Catmull-Clark, Loop), T-splines.  Per
  [ADR-0018][adr-0018] §"Out of scope".
- Hardware-accelerated NURBS trimming.  Trimmed NURBS is excluded
  from v2.1 per [ADR-0018][adr-0018].
- Metal / Vulkan port for macOS.  If/when Slicer-core makes that
  move, ADR-0020 gets revisited; until then OpenGL 4.0+ is the
  target.
- CPU-vs-GPU evaluator unification (e.g., emitting a Bernstein
  evaluator from a single source).  Out of scope; characterisation
  testing pins the equality + that's enough.

## Cross-references

- [ADR-0013][adr-0013] — Pipeline / Representation pattern; tess-shader migration is
  mapper-internal to the Representation.
- [ADR-0014][adr-0014] §3 — Bezier dissolution; the legacy mapper this ADR
  eventually replaces.
- [ADR-0015][adr-0015] — algorithm library; the CPU surface evaluator stays
  for downstream algorithms.
- [ADR-0018][adr-0018] §3 — NURBS sibling representation; the v2.1
  enabler PR for this ADR is paired with NURBS landing.
- [ADR-0019][adr-0019] — resection state machine; the parenchyma-trim
  + Confirmed-state shader path is unaffected by the tess migration.

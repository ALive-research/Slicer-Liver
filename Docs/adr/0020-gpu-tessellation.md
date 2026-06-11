# 0020. GPU rendering of parametric surfaces and their widgets (v2.1 target)

- **Status:** Accepted (target v2.1)
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

The same v2.1 mapper-design exercise touches **the widget visuals
that sit alongside the surface**:

- **Control-point sphere glyphs.**  v2.0.0's
  `vtkLiverBezierRepresentation` (T2.3, `LiverResections/VTKWidgets/`)
  instantiates a `vtkSphereSource` per control point — 9 spheres for the 3×3
  Bezier case, 16 for 4×4, ~30 for NURBS shapes.  Each sphere
  uploads a few hundred mesh triangles.  Pixel-perfect spheres at
  any zoom + minimal upload is achievable via **impostor billboards
  with fragment-shader ray-sphere intersection** (one quad per
  point, fragment shader computes the sphere) or
  **instanced sphere mesh rendering** (one sphere mesh stored once
  on GPU + per-instance position/colour/radius vec attributes).
  Neither path needs the geometry shader or tess shader stage;
  both work on OpenGL 3.3+, well below the 4.0+ requirement of
  surface tessellation.
- **Control-polygon connecting lines.**  The visualisation of the
  ring structure (per [ADR-0018][adr-0018] §1: corners 4 + edges
  `2(M-2)+2(N-2)` + interior `(M-2)(N-2)`) typically includes thin
  lines between adjacent control points showing the polygon
  edges.  Core-profile OpenGL deprecates `glLineWidth > 1.0`;
  controllable-thickness lines on modern GL require either
  **geometry-shader tube expansion** (vertex pairs → quad strip)
  or fragment-shader edge-distance shading on a pre-built tube
  mesh.

These three GPU-rendering concerns (surface tessellation,
control-point glyphs, connecting lines) all live in
`LiverResections/VTKWidgets/` post T2-mapper-relocation and are
naturally paired: same Representation lifecycle, same scene
observation, same data-node binding.  Designing them together in
v2.1 avoids three separate mapper-redesign exercises.

[adr-0013]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0013-layerdm-pipeline-pattern.md
[adr-0014]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0014-livermarkups-dissolution.md
[adr-0015]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0015-cpp-algorithm-library.md
[adr-0018]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0018-nurbs-extension-surface.md
[adr-0019]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0019-resection-state-machine.md

## Decision

**Commit a paired GPU-rendering migration as a v2.1 target** covering
three concerns of the parametric-surface visualisation in one
mapper-design exercise:

1. **Surface tessellation** (Bezier + NURBS) via tessellation shaders.
2. **Control-point sphere glyphs** via impostor billboards OR
   instanced sphere meshes.
3. **Control-polygon connecting lines** via geometry-shader tube
   expansion OR a pre-built tube mesh with fragment-shader
   edge shading.

All three target the **same mapper or sibling-mapper set** under
`LiverResections/VTKWidgets/` (post T2-mapper-relocation) and the
**same Representation lifecycle** (`BezierPlanningRepresentation` /
`NurbsPlanningRepresentation` per [ADR-0013][adr-0013] +
[ADR-0018][adr-0018]).

### Sub-decision 1: Surface tessellation

The surface migration is **paired**: Bezier + NURBS swap to
tess-shader mappers together in v2.1, rather than retrofitting
Bezier alone in v2.0.0.  The shared TES-based design covers both
representations with two slightly different evaluators (Bernstein
for Bezier; de Boor + rational weights for NURBS).

### Sub-decision 2: Control-point sphere glyphs

Two viable v2.1 paths (final choice deferred to the enabler PR +
its spike investigation):

- **Impostor billboards** (recommended).  Upload one
  quad per control point (4 verts per sphere × ~16 control points =
  64 verts).  Fragment shader does **ray-sphere intersection** for
  pixel-perfect spheres at any zoom + correct Z-depth.  Per-instance
  attributes: position, radius, colour (one of the three ring-role
  colours per [ADR-0018][adr-0018]).
- **Instanced sphere mesh.**  Pre-built sphere mesh stored once on
  the GPU (say 80 triangles at moderate resolution); per-instance
  attributes shift each instance to its control-point position.
  `vtkOpenGLPolyDataMapper` supports instancing natively via
  `vtkGlyph3DMapper`.  v2.0.0's
  [`vtkLiverBezierRepresentation`](https://github.com/ALive-research/Slicer-Liver/blob/preview/LiverResections/VTKWidgets/vtkLiverBezierRepresentation.cxx)
  uses raw `vtkSphereSource` per glyph — NOT instanced; the v2.1
  migration is from that to one of the two GPU paths above.

**Neither path needs the geometry shader OR the tessellation shader
stage.**  Both work on OpenGL 3.3+, well below the OpenGL 4.0+
profile that surface tessellation requires.  This means widget-glyph
rendering can land independently of (and before) the surface
tessellation if the spike PR uncovers OpenGL 4.0+ compatibility
blockers — there is no shared GPU-feature dependency between the
two sub-decisions.

### Sub-decision 3: Control-polygon connecting lines

The ring-of-control-points visualisation typically includes thin
lines between adjacent control points showing the polygon edges
(per [ADR-0018][adr-0018] §1's corners/edges/interior ring
taxonomy).  Core-profile OpenGL deprecates `glLineWidth > 1.0`, so
controllable-thickness lines on modern GL require GPU-side
expansion:

- **Geometry-shader tube expansion**: vertex pair (line segment) →
  quad-strip cross-section.  OpenGL 3.2+.  Cheap geometry-shader
  work since the input is a small number of line segments (~24
  for 4×4 Bezier ring polygon; fewer for 3×3).
- **Pre-built tube mesh + fragment-shader edge shading**: upload
  the polygon as a thicker tube mesh from CPU; fragment shader
  optionally renders a fade at the tube edges for aesthetics.  No
  geometry-shader stage; more triangles uploaded.

Recommend the geometry-shader path — the line count is small enough
that the per-segment shader cost is negligible, and CPU memory
stays minimal.

### What changes in v2.1

| Layer                              | v2.0.0 (lift-and-shift)                                  | v2.1 (post-ADR-0020)                                        |
|------------------------------------|----------------------------------------------------------|-------------------------------------------------------------|
| **Surface mapper input**           | Polygonal `vtkPolyData` (CPU-tessellated)                | 16 control points (or `Rows*Cols` for NURBS) as `GL_PATCHES` |
| Primitive type (surface)           | `GL_TRIANGLES` (Slicer-core default)                     | `GL_PATCHES` with `glPatchParameteri(GL_PATCH_VERTICES, ...)` |
| Surface vertex shader              | Pass-through + UV coord forwarding                       | Pass-through control point to TCS                            |
| Tess control shader (TCS)          | absent                                                   | New — sets tess factors (LOD-adaptive vs camera distance)    |
| Tess evaluation shader (TES)       | absent                                                   | New — evaluates Bernstein (Bezier) or de Boor (NURBS) at tess point |
| Surface fragment shader            | parenchyma trim + grid overlay + margin colour + corner markers (unchanged) | **identical** to v2.0.0 fragment shader; tess output is the same parametric (u, v) the FS already operates on |
| Surface mapper class               | `vtkOpenGLBezierResectionPolyDataMapper` (lift-and-shift)| New subclass managing `GL_PATCHES` primitive + tess-shader injection |
| **Control-point glyph mechanism**  | One `vtkSphereSource` per control point (CPU-meshed)     | Impostor billboards OR instanced sphere mesh                |
| Glyph fragment shader              | standard mesh lighting                                   | Impostor: ray-sphere intersection + Z-depth correction.  Instanced: unchanged. |
| Glyph per-instance attributes      | (per-actor uniform colour)                               | position, radius, ring-role colour ({corner, edge, interior}) |
| **Connecting-line mechanism**      | `glLineWidth` mesh lines (deprecated on core profile)    | Geometry-shader tube expansion (vertex pair → quad strip)   |
| Custom OpenGL mapper hooks         | `ReplaceShaderValues` (Vertex + Fragment slots)          | `ReplaceShaderValues` + new TCS/TES/GS slots                |

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

## Why these GPU mechanisms vs status quo

Each of the three sub-decisions has its own option space:

### Surface tessellation (sub-decision 1)

| Option | Mechanism | OpenGL profile | Trade-off |
|---|---|---|---|
| **A. Status quo** | CPU `vtkBezierSurfaceSource` → `vtkPolyDataMapper` (lift-and-shifted via T2-mapper-relocation) | 3.2+ | Works.  Static LOD.  CPU rebuild on every edit.  Bounded triangle count by what the CPU evaluator emits. |
| **B. GPU tessellation shader** (this ADR's target) | TCS + TES; `GL_PATCHES` primitive | **4.0+** | LOD-adaptive; no CPU rebuild on edit; smooth at any zoom; ~192 bytes uploaded per edit vs MB of triangle mesh.  NURBS-natural. |
| **C. GPU geometry shader** | Single-stage GS; bounded output | 3.2+ | Works on older GL.  Geometry-shader output bounded; less efficient than tess for surface evaluation; tessellation is what shaders were designed for.  Rejected. |

GPU tessellation is the textbook answer for parametric surfaces.
Option C is rejected on principle (geometry shaders are
general-purpose; parametric surfaces have a purpose-built shader
stage).

### Control-point sphere glyphs (sub-decision 2)

| Option | Mechanism | OpenGL profile | Trade-off |
|---|---|---|---|
| **A. Status quo** | Per-control-point `vtkSphereSource` + standard polygon mapper | 3.2+ | Works.  Tens of meshed sphere actors per representation; per-sphere upload on radius/colour change; fixed mesh resolution = jaggy on close zoom. |
| **B. Impostor billboards** (recommended) | One quad per control point; fragment-shader ray-sphere intersection | 3.3+ | Pixel-perfect at any zoom; minimal upload (~64 verts total); standard "molecular visualisation" pattern.  Picking needs a small ray-sphere routine. |
| **C. Instanced sphere mesh** | Pre-built sphere mesh + per-instance position/colour/radius vec attributes | 3.3+ | Simple; uses standard `vtkGlyph3DMapper`-style instancing.  Slightly less pixel-perfect than impostors; not zoom-adaptive without LOD-mesh switching. |
| **D. Geometry-shader sphere expansion** | Vertex → quad → ray-sphere via GS stage | 3.2+ | Functionally same as B but uses the GS pipeline stage.  Slower on most modern GPUs.  Rejected. |

B is recommended; C is the fallback if VTK's `vtkGlyph3DMapper`
integration is simpler than rolling a custom impostor mapper.
**Neither B nor C requires the geometry shader or tessellation
shader stage** — both run on the existing VS+FS pipeline.  This
means the widget-glyph migration can land independently of (and
on a lower OpenGL profile than) surface tessellation.

### Control-polygon connecting lines (sub-decision 3)

| Option | Mechanism | OpenGL profile | Trade-off |
|---|---|---|---|
| **A. Status quo / `glLineWidth`** | Mesh line segments with `glLineWidth` | core-profile deprecated `> 1.0` | Works but limited; controllable thickness is unreliable on core profile. |
| **B. Geometry-shader tube expansion** (recommended) | Vertex pair → quad-strip cross-section | 3.2+ | Modern controllable thickness; small per-segment cost since segment count is small (~24 for 4×4 ring polygon). |
| **C. Pre-built tube mesh + fragment-shader edge shading** | CPU-meshed thicker tube + FS edge-distance | 3.2+ | No GS stage; more triangles to upload + manage. |

B is recommended.  GS for connecting lines is reasonable (single
GS invocation per line segment is cheap, the input count is
small); for spheres GS is wrong (ray-sphere intersection is purely
fragment-shader work).  This is why the ADR adopts the GS for line
expansion and rejects it for spheres.

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
3. **Compatibility spike PR (surface).**  A small experimental PR
   that stand-alone tests `glPatchParameteri(GL_PATCH_VERTICES, 16)`
   + TCS/TES + Bernstein evaluation in a Slicer process across
   Linux + macOS + Windows.  If VTK's tess plumbing or
   cross-platform GL profile fails the spike, fall back to a
   custom-OpenGL-context approach (a deeper rewrite than VTK's
   shader-modification API supports).
4. **Widget-mapper investigation (glyphs + lines).**  Is VTK's
   `vtkGlyph3DMapper` (or `vtkOpenGLGlyph3DMapper`) instancing
   path sufficient for the control-point glyph migration as-is, or
   does the impostor-billboard variant require a custom subclass
   of `vtkOpenGLPolyDataMapper` (analogous to the surface mapper)?
   Same question for connecting lines: does VTK's
   `vtkOpenGLLineIntegralConvolutionPass` or `vtkTubeFilter`
   already do GS-style line expansion, or do we author a
   `vtkOpenGLBezierControlPolygonMapper` that injects the GS
   ourselves?  Resolving this scopes the enabler PR's surface area.
5. **macOS GL 4.1 quirks.**  Tested patch-vertex-count limits +
   tess factors + Bernstein basis evaluation + geometry-shader
   availability on Apple Silicon (Metal-via-MoltenVK or native GL?).
   Geometry shaders are part of OpenGL 3.2 core, present on
   macOS GL 4.1, but Apple's deprecation makes the long-term path
   uncertain.  Decision: if macOS is too constrained, gate the
   GPU paths behind a runtime check that falls back to the v2.0.0
   CPU/per-sphere/`glLineWidth` approach on unsupported platforms.

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
- **Pixel-perfect control-point spheres at any zoom** via impostor
  billboards (sub-decision 2).  No more polygonal-sphere jaggies
  on close inspection.
- **Modern controllable-thickness connecting lines** via GS tube
  expansion (sub-decision 3).  Works on core-profile OpenGL where
  `glLineWidth > 1.0` is deprecated.

**Negative:**

- v2.1 enabler PR is non-trivial — custom mapper subclass + TCS +
  TES + draw-call primitive type override (surface) + impostor
  or instanced sphere mapper (glyphs) + geometry-shader line
  expansion (connecting lines).  Multi-week effort.
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
2. **Compatibility + widget-mapper spike PR.**  Single spike that
   validates: (a) VTK tess-shader plumbing for the surface,
   (b) `vtkGlyph3DMapper` instancing OR impostor-billboard approach
   for control-point glyphs, (c) geometry-shader tube expansion for
   connecting lines.  All three on Linux + macOS + Windows.  If any
   leg of the spike fails, fall back to the v2.0.0 mechanism for
   that leg only — the three sub-decisions are independently
   gateable.
3. **ADR-0020 enabler PR (surface).**  New
   `vtkOpenGLParametricSurfaceMapper` (or similar) subclassing
   `vtkOpenGLPolyDataMapper` with `GL_PATCHES` binding + TCS + TES.
   Bezier evaluator in TES; NURBS evaluator added in a sibling
   shader once the NURBS data path lands.
   `BezierPlanningRepresentation` swaps from the lift-and-shifted
   legacy mapper to the new tess mapper.
4. **ADR-0020 enabler PR (control-point glyphs).**  Either swap
   `vtkSphereSource`-per-point in `vtkLiverBezierRepresentation` for
   a single `vtkGlyph3DMapper` (instanced low-poly sphere) — if the
   spike accepts the quality at high zoom — OR author a custom
   impostor-billboard mapper that ray-traces a sphere in the
   fragment shader.  Per-instance attributes (centre, radius,
   colour) drive both variants.
5. **ADR-0020 enabler PR (control-polygon lines).**  Replace the
   current `glLineWidth`-based line drawing in
   `vtkLiverBezierRepresentation` with a geometry-shader pass that
   expands each `LINES` primitive into a screen-space quad of
   controllable thickness.  Custom mapper subclass with VS+GS+FS
   injection.
6. **Architecture diagram update.**  `rendering-pipeline.md` class
   diagram + sequence diagram regenerated to show the new mapper
   trio + their TCS/TES/GS stages.  Compatibility-fallback paths
   documented per sub-decision if macOS gates any of them at
   runtime.
7. **Characterisation tests.**  Per [ADR-0003][adr-0003]:
   (a) pin the GPU-rendered surface's (u, v) → world-space mapping
   to byte equality against the CPU `vtkBezierSurfaceSource` at the
   `vtkLiverBezierFitter`-test tolerance;
   (b) pin control-point glyph screen-space centre + apparent
   radius across the impostor/instanced variants;
   (c) pin connecting-line screen-space width to the configured
   line-thickness uniform.

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
- **Resectogram + distance-map rendering.**  Those are 2D
  post-processed views, not the parametric-surface viewport.  Their
  rendering path is unchanged by this ADR.
- **Picking / interaction for impostor-sphere glyphs.**  The v2.0.0
  picker assumes polygonal geometry; impostor billboards have no
  triangles to hit-test against.  If sub-decision 2 lands as
  impostors (vs instanced meshes), a companion picker change is
  needed but it's a separate concern from the rendering decision
  documented here — covered in the enabler PR's design.
- **Choice between impostor vs instanced sphere meshes** for the
  glyphs.  Both are option-B-class wins over status quo; the spike
  picks the winner on quality + portability grounds.  This ADR
  records that one of those two paths is the v2.1 target, not
  which one.

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

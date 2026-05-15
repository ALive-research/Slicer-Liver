# 0015. Lift parameterisation and fitting algorithms from Python to a C++ algorithm library under LiverResections

- **Status:** Proposed
- **Date:** 2026-05-15
- **Deciders:** Rafael Palomar
- **Diagrams:** N/A
- **PR:** _filled in on merge_

## Context

[ADR-0004](0004-python-cpp-boundary.md) commits Slicer-Liver to a sharp
Python/C++ boundary: Python is the default; C++ is reserved for
data-only MRML node classes and for **performance-critical algorithm
libraries** with a profile-justified native-speed need.  ADR-0004 §2
explicitly enumerates the candidate workloads — "Bezier-surface
evaluation, distance-map computation, slicing-contour interpolation,
volumetry integrators, and any custom VTK filters with a demonstrated
per-frame or inner-loop budget" — but does not commit a specific
release to lifting any of them.  This ADR is the first concrete
realisation of that boundary: it picks the resection-surface-fitting
machinery (the algorithms behind the Init→Planning state transition
introduced by [ADR-0014](0014-livermarkups-dissolution.md)) and lifts
them from `Liver/Liver.py` into a new C++ algorithm library.

The Init→Planning transition (per ADR-0014 §2 and
[ADR-0013](0013-layerdm-pipeline-pattern.md) §4) needs a Bezier fit
from a ring on the target liver mesh.  Two flavours, both required for
v2.0.0:

- **SlicingPlane init** — closed planar curve on the liver surface,
  produced by intersecting a user-specified plane with the target
  mesh.  The ring has 4-fold reflective symmetry under the plane;
  the Bezier fit is mostly a corner-correspondence + interpolation
  problem.
- **DistanceSpheroid init** — closed (generally non-planar) curve on
  the liver surface, produced by intersecting a user-specified
  spheroid with the target mesh.  The ring is not symmetric; the
  Bezier fit requires a richer parameterisation step (Elliptic
  Fourier Descriptors or an equivalent harmonic apparatus) before
  the corner correspondence is well-posed.

Today's implementation lives in three Python functions in
`Liver/Liver.py`:

- `fit_bezier_surface` (≈ line 1914) — top-level dispatcher; takes a
  ring + mode and returns the 4×4 control grid.
- `runSurfacefromCurve` (≈ line 1961) — the SlicingPlane path.
- `runSurfacefromEFD` (≈ line 2042) — the DistanceSpheroid path, with
  the EFD parameterisation inlined.

(These line numbers are approximate; the project-log entries flagged
this trio as a suspected-buggy hotspot multiple times during the
2024–2026 development of the module.)  Three pains motivate the lift:

- **Testability.**  The functions run inside Slicer's event loop with
  implicit dependencies on the scene state and the active widget.
  Unit-testing them today requires either standing up a Slicer app
  (slow, flaky, gives up the inner-loop on every iteration) or
  mocking out enough Slicer machinery that the mock surface dwarfs
  the function under test.  Neither matches
  [ADR-0008](0008-testing-strategy.md)'s Unit-layer ambition
  ("Bezier basis evaluation on numpy arrays" — no Slicer, no Qt).
- **Suspected bugs in numerical paths.**  The EFD parameterisation
  and the corner-correspondence step are the most-flagged hotspots
  in the project log; they need to be unit-testable in isolation
  before fixes can land with confidence.  Per
  [ADR-0003](0003-testability-invariant.md), behaviour-changing PRs
  in this area need characterisation tests; the current shape makes
  characterisation expensive.
- **Reuse across the v2.0.0 surface.**  The ring-extraction step
  (plane ∩ mesh, spheroid ∩ mesh) and the Bezier fitter are both
  consumed by the new state-aware Pipeline's three Representations
  (per ADR-0014 §2) and by the T3 Resectogram pipeline downstream.
  A C++ algorithm library with stable VTK-typed inputs and outputs
  is the natural shared surface.

Per ADR-0004 §2, the default for new compute is "Python VTK filter
unless a profile says otherwise".  The fitting algorithms qualify for
the C++ band on **testability** rather than profile-justified speed:
they need to be exercisable in seconds against synthetic input
without Slicer or Qt in the picture, and the C++ + `ctkTest` layer
([ADR-0008](0008-testing-strategy.md) §2's "C++ low-level" row)
provides exactly that.  Native-speed payoff is a secondary benefit;
testability is the load-bearing reason.

## Decision

Slicer-Liver creates a new `LiverResections/Algorithm/` subdirectory
hosting a C++ algorithm library with four `vtkAlgorithm`-style
classes.  The library is pure VTK with **no MRML dependency**, is
Python-wrapped via Slicer's existing VTK wrapping, ships its own C++
test set under `Algorithm/Testing/Cxx/`, and is consumed by the
state-aware LiverResections Pipeline introduced in
[ADR-0014](0014-livermarkups-dissolution.md).  Subdirectory name is
singular `Algorithm/` to match the sibling-directory convention
elsewhere in `LiverResections/` (`Logic/`, `MRML/`, `MRMLDM/`,
`Testing/`).

### 1. Class roster

| Class | Inputs | Output | Used by |
|---|---|---|---|
| `vtkLiverPlaneRingExtractor` | target `vtkPolyData` + plane | ordered ring `vtkPolyData` | `SlicingPlaneInitRepresentation` |
| `vtkLiverSpheroidRingExtractor` | target `vtkPolyData` + spheroid | ordered ring `vtkPolyData` | `DistanceSpheroidInitRepresentation` |
| `vtkLiverContourParameterizer` | ring + mode (corner-mapping / EFD) | parameterised curve | `vtkLiverBezierFitter` |
| `vtkLiverBezierFitter` | parameterised curve | 4×4 grid + ring roles | Init→Planning transition |

All four subclass `vtkPolyDataAlgorithm` (or `vtkAlgorithm` where the
output is not a `vtkPolyData`).  Inputs come in through the standard
VTK pipeline input ports; parameters come in through `Set/Get`
accessors.  No `vtkMRMLNode` reference appears in any of these
classes — MRML lives entirely in the Python orchestration layer
(`LiverBezierSurfacePipeline` and its Representations) that consumes
the algorithm outputs.

The two ring-extractors are **new code**.  The contour parameteriser
and Bezier fitter are **lifts** of the three Python functions
catalogued above:

- `fit_bezier_surface` (top-level dispatcher) → `vtkLiverBezierFitter`.
- `runSurfacefromCurve` (SlicingPlane path) → folded into
  `vtkLiverBezierFitter` via the parameterisation-mode parameter on
  `vtkLiverContourParameterizer` (corner-mapping mode).
- `runSurfacefromEFD` (DistanceSpheroid path) → folded into
  `vtkLiverContourParameterizer` (EFD mode) feeding
  `vtkLiverBezierFitter`.

### 2. Build-system addition

A new `LiverResections/Algorithm/CMakeLists.txt` declares an
`add_library` target (`LiverResectionsAlgorithm` or similar) that
links into `vtkSlicerLiverResectionsModuleLogic` via the existing
module-library wiring.  VTK wrapping is enabled on the new library
so Python consumers reach the classes through the standard
`import vtkSlicerLiverResectionsModuleLogicPython`-style import (or
the module's Python facade, per the scripted-module convention).

### 3. Test layering — C++ low-level plus Python wrapper

Per [ADR-0008](0008-testing-strategy.md) §2:

- **C++ low-level tests** under `LiverResections/Algorithm/Testing/
  Cxx/` exercise each class against synthetic `vtkPolyData` inputs.
  No Slicer import, no Qt, no MRML scene.  These form the *fast
  subset* of CI that a developer can re-run in seconds with
  `ctest -R BezierFitter` for one-shot bug-repro.
- **Python wrapper tests** under `LiverResections/Testing/Python/`
  exercise the wrapping surface — that the parameter setters survive
  Python type-coercion, that the output `vtkPolyData` round-trips
  through `numpy_support` cleanly, and that the four classes compose
  in the pipeline order the Init→Planning transition needs.  These
  run under the pytest scaffold introduced by PR #316.
- **Workflow-layer integration** is owned by the Pipeline tests per
  ADR-0014 step 4, not by this library.  The algorithm library is a
  pure VTK surface; the integration test belongs with the consumer.

### 4. Migration discipline for the three lifted Python functions

Per [ADR-0003](0003-testability-invariant.md), the lift is gated on
characterisation tests of current Python behaviour.  Sequence:

1. **Characterisation first.**  Add pytest cases under
   `LiverResections/Testing/Python/` that drive `fit_bezier_surface`,
   `runSurfacefromCurve`, and `runSurfacefromEFD` against curated
   ring inputs (planar rings for SlicingPlane, synthetic non-planar
   rings for DistanceSpheroid) and assert on the 4×4 control grids
   they return.  Tolerances documented per case.
2. **Lift.**  Implement the C++ classes; invert each characterisation
   test's assertion target from the Python function to the C++ class
   output, requiring bit-equivalence where the numerical apparatus
   permits and a documented numerical tolerance otherwise.
3. **Retire the Python paths.**  Once the C++ paths pass the
   inverted characterisation tests, the three Python functions are
   removed from `Liver/Liver.py` and the Pipeline consumes the C++
   classes directly.  Suspected-bug fixes follow in *separate* PRs
   on the lifted C++ code, each with its own regression test per
   [ADR-0003](0003-testability-invariant.md) §3.

## Alternatives considered

### A. Keep the algorithms in Python

Leave `fit_bezier_surface`, `runSurfacefromCurve`, and
`runSurfacefromEFD` in `Liver/Liver.py`.  Refactor for testability
in-place: extract the math into a pure-Python module, expose a
seam for `numpy`-only unit tests, leave the orchestration in the
scripted module.

**Rejected** because testability is the load-bearing driver of this
ADR, and Python alone does not deliver the full ambition.
[ADR-0008](0008-testing-strategy.md)'s C++ low-level layer (`ctkTest`,
no Slicer import) catches a class of regression — custom VTK
mapper / observer / filter correctness — that pure-Python tests do
not reach.  Lifting the algorithms to C++ puts them in the same test
layer as the custom mappers they feed
([ADR-0014](0014-livermarkups-dissolution.md) §3), which means one
fast `ctest -R Bezier` invocation covers the whole numerical-plus-
rendering path.  The native-speed dividend is also nonzero; it is
just not the primary reason.

### B. External C++ algorithm package (CGAL, libigl)

Adopt CGAL or libigl as the home for the ring extraction, contour
parameterisation, and Bezier fit.  Both libraries are mature,
widely used in geometry processing, and would absorb the EFD-flavour
apparatus naturally.

**Rejected** for two reasons.  First, the algorithms are
liver-specific: the ring extraction's contract is "what the liver
surface looks like under the user's chosen init plane/spheroid",
and the Bezier fit's contract is "what a surgically meaningful
4×4 grid looks like over that ring with ring-role metadata
preserved".  Neither contract sits naturally on a general-purpose
geometry library's API.  Second, adopting CGAL or libigl adds a
required external dependency to the Slicer-Liver build, which is an
(E)-class trigger per [ADR-0007](0007-version-numbering-policy.md);
the dependency cost for a liver-specific algorithm catalogue
outweighs the (modest) code reuse.  The classes belong in-tree.

### C. NumPy/SciPy hybrid (Python orchestration calling vectorised math)

Keep the orchestration in Python but rewrite the math against
NumPy/SciPy: `scipy.interpolate.BSpline` or equivalent for the
Bezier evaluation, NumPy FFT for the EFD path, vectorised ring
operations under NumPy slicing.

**Rejected** because the consumer side is `vtkPolyData` (the
Representations render `vtkActor`s over `vtkPolyDataMapper`s feeding
on the algorithm outputs).  A NumPy/SciPy hybrid forces a
`vtkPolyData ↔ numpy.ndarray` conversion at every pipeline boundary
— either via `vtk.util.numpy_support` (cheap but adds boilerplate at
every consumer) or via a custom marshalling layer (re-introduces the
abstraction the lift is meant to retire).  Staying in the VTK
pipeline (`vtkAlgorithm` style end-to-end) means the algorithm
outputs flow into the Representations' mappers with no marshalling
seam.

### D. ITK filter library

Express the four classes as `itk::ImageToImageFilter` / `itk::Mesh
ToMeshFilter` subclasses, hosted under an `LiverResections/ITK/`
subdirectory and built against the Slicer-bundled ITK.

**Rejected** because ITK is image-centric: its mesh pipeline is a
secondary concern with less maturity than its image-processing core,
and the ring-extraction and Bezier-fitting work is fundamentally a
mesh-and-curve workload.  VTK's `vtkPolyDataAlgorithm` pipeline is
the natural substrate; using ITK here would mean fighting against
ITK's image-first abstractions to express mesh-first operations.
The custom OpenGL mappers ADR-0014 relocates also consume
`vtkPolyData`; keeping the algorithm outputs in the same world is
the path of least friction.

## Consequences

### Easier

- **First concrete realisation of [ADR-0004](0004-python-cpp-boundary.md).**
  The Python/C++ boundary that ADR-0004 commits in principle becomes a
  worked example: four algorithm classes, one CMake target, one
  Python-wrapper test set, one C++ low-level test set.  Future
  C++ algorithm-library work in v2.1.0 (volumetry integrators,
  distance maps for the resectogram texture path) follows the
  template this ADR establishes — same directory shape, same test
  layering, same wrapping convention.
- **`ctest -R BezierFitter` is a one-line bug-repro.**  When a
  surgeon reports an Init→Planning transition that produces a wrong
  resection surface, the C++ low-level tests are the first stop:
  build the curated ring input as a synthetic `vtkPolyData`, drive
  it through `vtkLiverBezierFitter`, assert on the 4×4 grid.  No
  Slicer launch, no event loop, no GUI in the picture; the
  characterisation discipline ADR-0003 mandates becomes cheap
  enough to apply systematically.
- **The four classes compose with the rest of the resection
  Pipeline.**  Per ADR-0014 §2, the three Representations consume
  the algorithm outputs through standard VTK pipeline ports; the
  Pipeline's `update()` re-runs only the algorithm stages whose
  inputs have changed.  No bespoke marshalling between Python and
  the rendering surface.

### Harder

- **Build-system addition: one new `CMakeLists.txt`.**  The
  `LiverResections/Algorithm/CMakeLists.txt` file is new; its
  `add_library` target links into the module logic and is registered
  with the VTK wrapping pipeline.  Small one-time cost, paid in the
  same PR that lands the classes.
- **Regression risk on the three lifted functions.**  The lift
  inverts the characterisation tests from "Python function returns
  this output" to "C++ class returns the same output (within
  documented tolerance)".  Mitigated by the ADR-0003 discipline of
  landing the characterisation tests **first**, in their own commit
  or PR, before the lift commit modifies them.  Numerical tolerance
  is documented per test case where bit-equivalence is not
  achievable (notably the EFD path, where the C++ FFT implementation
  may differ in last-bit accuracy from the Python reference).
- **C++ build-cost for iteration on the algorithm layer.**  Changes
  to the algorithm classes require a Slicer rebuild (10–60 min per
  [ADR-0004](0004-python-cpp-boundary.md)'s catalogue).  Acceptable
  because the algorithms are expected to stabilise after the lift
  and post-lift bug-fixes; the iteration loop for the *consumers*
  (the Pipeline and Representations) stays in Python where ADR-0004
  puts it.

## References

- Related ADRs:
  - [ADR-0001](0001-resection-three-node-assembly.md) — the
    descriptive record of the resection workflow these algorithms
    serve; the Init→Planning transition is the workflow step the
    library exists for.
  - [ADR-0003](0003-testability-invariant.md) — the characterisation
    discipline gating the lift of the three Python functions.
  - [ADR-0004](0004-python-cpp-boundary.md) — the Python/C++
    boundary this ADR is the first concrete realisation of.
  - [ADR-0007](0007-version-numbering-policy.md) — the (E)-class
    trigger considered (and avoided) in Alternative B.
  - [ADR-0008](0008-testing-strategy.md) — the C++ low-level test
    layer the new library plugs into; §2 enumerates the four-layer
    taxonomy.
  - [ADR-0013](0013-layerdm-pipeline-pattern.md) — the Pipeline
    pattern that consumes the library; §4 is the state-aware-
    Pipeline pattern the Init→Planning transition rides on.
  - [ADR-0014](0014-livermarkups-dissolution.md) — the LiverMarkups
    dissolution that this library supports; the three
    Representations consume the four algorithm classes catalogued
    here.

---

*AI-assisted authorship: this pull request was drafted with help from Anthropic's Claude (Opus 4.7, `claude-opus-4-7`) via Claude Code. Plan and brief from the orchestrating Opus 4.7 session per the handoff at `.claude/handoff-2026-05-15-v2-architecture.md`; prose drafted by a Claude Code subagent. Opened for human review before merge.*

# 0040. Poisson Surface Reconstruction from segmentations

- **Status:** Accepted
- **Date:** 2026-09-12
- **Deciders:** Rafael Palomar
- **Relates to:**
  [ADR-0023](0023-unified-gui-stage-workflow.md) (which said PSR "ships
  as a Superbuild external project" — amended here),
  [ADR-0015](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0015-algorithm-library.md)
  (the Algorithm-library home for pure computation),
  [ADR-0004](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0004-python-cpp-boundary.md)
  (the Python/C++ boundary this must cross), and
  [ADR-0039](0039-ai-assisted-development-working-agreements.md)
  (slice discipline).
- **Issue:** #310
- **PR:** _filled in on merge_

## Context

Every surface in Slicer-Liver today comes from marching cubes, via
`CreateClosedSurfaceRepresentation` — the liver model in Stage 2, the
vessel surfaces in VascularTerritories, the highlight geometry. That
path produces the staircase artefacts inherent to thresholding a
labelmap on its voxel lattice.

Poisson Surface Reconstruction (Kazhdan et al.) reconstructs a smooth,
watertight surface from an **oriented point cloud** — points carrying
outward normals. It is the reconstruction the project has wanted since
v1; #310 has tracked it as "desirable for release quality, not
blocking", precisely because marching cubes is adequate and PSR has no
caller waiting on it.

Three things make this the right moment to decide rather than drift:

1. ADR-0023 already commits the project to shipping PSR, and states a
   build shape (`Superbuild external project`) that the repository does
   not have — `CMakeLists.txt` describes Slicer-Liver as "a
   non-SuperBuild leaf extension". The commitment and the tree disagree.
2. The project has prior art that answers the hardest design question,
   and it is about to be lost to time: `RafaelPalomar/PoissonSurfaceReconstruction`
   (2018) carries a working segmentation→oriented-cloud extractor.
3. Two recent defects (#636, #640) were C++ signatures invisible from
   Python. A new C++ dependency consumed from Python walks straight into
   that trap unless the boundary is decided up front.

## Decision

### 1. Wrap current upstream Kazhdan; do not fork Doria's adaptation

The 2018 repository is *"the Poisson Surface Reconstruction by Michael
Kazhdan and Matthew Bolitho adapted to VTK by David Doria"* — a VTK
adapter wrapped around a snapshot of Kazhdan from that era.

Modernising it would mean two simultaneous rewrites: the adapter to
VTK 9, and the core to current Kazhdan (whose API has moved
substantially since). Between them, little of the original would
survive, and we would own a fork's history for nothing.

We therefore build a thin adapter against **current upstream
PoissonRecon**, and treat both `Src/` of the 2018 repository and Doria's
adapter as *reference reading* for how to marshal `vtkPolyData` and
handle normals — not as an ancestor.

### 2. The consumer is segmentation → oriented point cloud → surface

Not "smooth an existing mesh". The extraction goes **straight from the
labelmap's intensity gradient to oriented points**, never building an
intermediate marching-cubes surface, which is what the 2018 example
does and why its normals are principled rather than estimated:

- ITK Sobel operators in x, y and z over the cast labelmap
  (`itkSobelOperator` + `NeighborhoodOperatorImageFilter`);
- the three derivative images give the gradient, which at a labelmap
  boundary *is* the outward normal;
- `ImageMaskSpatialObject` bounds the work to the segment's
  axis-aligned bounding box;
- the cloud is subsampled, then fed to PSR with **depth** as the
  exposed parameter.

That extractor is **ported**, not rewritten from scratch. It is the part
of the 2018 work worth keeping.

### 3. Licence

Upstream PoissonRecon is **MIT** — commercial use, source and binary
redistribution, attribution only. Compatible with this project's BSD-3
with no friction; the obligation is to carry its notice.

Two caveats that shape packaging rather than legality:

- Upstream **vendors zlib, libpng and libjpeg/libjpeg-turbo** in
  `ZLIB/`, `PNG/`, `JPEG/`, `JPEG-turbo/`, which the top-level MIT does
  not cover (each carries its own permissive terms). These exist for
  PSR's *image* I/O and are irrelevant to reconstructing a surface from
  points. **We build `Src/` only, with image I/O disabled, and vendor
  none of them.**
- The 2018 repository carries **no licence file**. Nothing from it lands
  in this project until it has one.

### 4. Build route: a dependency, not a SuperBuild conversion

ADR-0023's "Superbuild external project" is **amended**. Converting this
extension to a SuperBuild touches CI (the pinned
`slicer-build-ubuntu2404` image), build times and packaging — a large
change for one algorithm.

The precedent is already in the tree: **SlicerVMTK is a hard
`EXTENSION_DEPENDS` and Slicer-Liver consumes its SuperBuild libraries
without being one itself** (`CMakeLists.txt` wires
`SlicerVMTK_SuperBuildLib_*` into the launcher paths). PSR takes the
same shape.

The route is chosen in phase 1 against evidence, from:

1. **vendored `Src/` compiled into the Algorithm kit** — preferred if
   the reconstruction path is self-contained;
2. **a separate small extension** Slicer-Liver depends on, mirroring
   SlicerVMTK;
3. a SuperBuild conversion — **only** if 1 and 2 both prove unworkable.

The deciding evidence is whether the non-distributed reconstruction path
builds **without Boost**. Upstream requires Boost for sockets in the
*distributed* client/server variant, which we do not want; if the plain
path is Boost-free, option 1 is open.

### 5. The Python boundary is a first-class deliverable

Per ADR-0004, the computation is C++ and the callers are Python. The
adapter is not done when it compiles and its C++ tests pass — that is
exactly the state #636 and #640 reached while being **invisible from
Python**.

A **Python caller exercising the wrapped entry point** is part of the
definition of done, and signatures are chosen for wrappability
(`vtkPolyData` in/out, scalar parameters; no `std::vector<std::vector<…>>`,
no `std::array` by reference, no `void*`).

## Alternatives considered

**Fork and modernise the 2018 repository.** Rejected: both halves would
be replaced, leaving a fork we maintain for no inherited value.

**Smooth the marching-cubes output instead** (sample points + normals
off the existing mesh). Rejected as the primary path: it estimates
normals from a triangulation that already carries the staircase
artefacts we are trying to remove, where the labelmap gradient gives
them directly. Remains available as a second input mode later.

**VTK's own surface reconstruction** (`vtkSurfaceReconstructionFilter`).
Rejected: not present in this build, and materially lower quality than
screened PSR on noisy medical labelmaps.

**Do nothing.** Legitimate — marching cubes is adequate, #310 is
explicitly non-blocking, and this ADR does not make PSR a release
blocker. What the ADR buys is that the *decision* is recorded before the
prior art is lost.

## Consequences

**Positive**

- Smooth, watertight liver and vessel surfaces without lattice
  artefacts.
- The 2018 extractor is preserved as maintained code rather than an
  unlicensed 2018 snapshot.
- A stale commitment in ADR-0023 is corrected rather than left to
  mislead.

**Negative**

- A new C++ dependency on a template-heavy codebase.
- PSR has parameters (depth chief among them) with no universally right
  value; a depth that flatters one liver oversmooths another. Any
  surgeon-facing exposure needs a considered default and a documented
  range.
- Reconstruction is slower than marching cubes; it is not a drop-in
  replacement for interactive paths.

**Reversibility**

High. PSR is additive — marching cubes stays. Dropping it means
removing one Algorithm entry point and its caller.

## Phasing (ADR-0039 slice discipline)

| Phase | Deliverable | Gate |
| --- | --- | --- |
| 1 | Upstream `Src/` built standalone; Boost-free question answered; build route chosen | evidence recorded on #310 |
| 2 | Ported extractor: segmentation → oriented cloud, as an Algorithm-library entry point | unit tests on a known labelmap |
| 3 | PSR adapter: `vtkPolyData` in/out, depth exposed, **called from Python in a test** | both harnesses |
| 4 | Consumer wired; PSR vs marching cubes on real anatomy | `:0` eyeball |

Phases 1–3 are independently mergeable and land nothing user-visible.

## Conformance

- [test] The PSR entry point is callable from Python — a Python test
  invokes it and asserts on the returned `vtkPolyData`. A C++-only test
  does not discharge this point (#636, #640).
- [test] The extractor produces one oriented point per boundary voxel
  of a known synthetic labelmap, with normals pointing outward.
- [review] No file from `ZLIB/`, `PNG/`, `JPEG/` or `JPEG-turbo/` is
  vendored into this repository.
- [review] Upstream's MIT notice is carried wherever its source is.
- [review] Nothing from `RafaelPalomar/PoissonSurfaceReconstruction`
  lands until that repository carries a licence.
- [future] PSR is offered alongside marching cubes, not as a silent
  replacement: the surface a user gets is the one they chose.

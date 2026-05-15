# 0002. Migrate SlicerLiver from Markups + MRMLDM to SlicerLayerDisplayableManager

- **Status:** Proposed
- **Date:** 2026-05-13
- **Deciders:** Rafael Palomar
- **Diagrams:** [current-mrml-node-hierarchy](../architecture/current-mrml-node-hierarchy.md)
  (target diagram to follow in a separate PR alongside the first module
  migration)
- **PR:** _filled in on merge_
- **Supersedes:** [ADR-0001](0001-resection-three-node-assembly.md)
  (as the target — 0001 stands as descriptive history)

## Context

Slicer-Liver's current displayable manager (DM) and widget architecture
exhibits six structural pains that have accumulated over the 2021–2026
development of the module:

1. **The three-node resection assembly** (documented in ADR-0001) exists
   primarily because interactive 3D editing of the Bezier surface
   requires `vtkMRMLMarkupsNode` inheritance, while persisting the full
   resection state (the 16 control points *and* per-resection metadata
   — margins, colours, grid divisions, references to parent
   segmentation and target structures) demands a dedicated
   `vtkMRMLStorableNode` + `vtkMRMLStorageNode` pair.  Markups' built-in
   serializer is shaped around its point-list schema and cannot carry
   SlicerLiver-specific resection metadata, so we cannot collapse the
   two roles onto a single Markups node.  The result: geometry on a
   Markups node, metadata on a Storable node, with a Logic class
   binding them.

2. **Six `std::map` members in `vtkSlicerLiverResectionsLogic`** maintain
   bidirectional navigation between the three nodes of each resection.
   Header line 153 carries the original author's comment: *"too many
   maps here. We should try to improve the design to avoid this."*  The
   maps are error-prone on node-removal cleanup and would not scale to
   multi-threaded use.

3. **~30 display-related fields leak onto `vtkMRMLLiverResectionNode`**
   (margins, colours, grid divisions, opacity, widget visibility,
   interpolated-margin flags), and are pushed *one-way* into
   `vtkMRMLMarkupsBezierSurfaceDisplayNode` on every `Modified()` event.
   Edits made directly to the display node are silently lost.

4. **The Markups interaction model cannot host the resection workflows
   SlicerLiver actually needs.**  The Bezier control grid is 4×4, and
   surgically meaningful operations group control points into the
   inner 4 vs the border 12 (e.g. right-clicking any inner point
   should let the surgeon translate the inner group as a unit;
   right-clicking a border point should adjust the boundary as a
   unit).  Markups' interaction handler is built around per-point
   semantics with a fixed event vocabulary and no first-class concept
   of point groups, so expressing these operations on top of it is
   awkward and brittle.  The same constraint hampers the other
   resection-definition workflows the module supports — contour
   initialisation + Bezier modification, manual contour creation +
   fitting, 2-point initialisation + fitting — and the alternative
   surface representations (Bezier today, NURBS in progress) that
   each want their own interaction semantics.

5. **`vtkMRMLLiverResectionsDisplayableManager2D`** reimplements
   pipeline instantiation, renderer setup, and camera handling — the
   same boilerplate as every other Slicer DM.

6. **String-based factory instantiation** of DMs prevents shared-service
   injection, complicates testing, and makes future cross-module
   pipelines (e.g. a unified resection-plus-vessels view) awkward.

Kitware released the
[**SlicerLayerDisplayableManager (LayerDM)**](https://github.com/KitwareMedical/SlicerLayerDisplayableManager)
module (available via the Slicer 5.10+ extension manager) which
addresses exactly these structural pains:

- *Centralized pipeline management* — pipelines created and torn down
  automatically; no per-DM boilerplate.
- *Dependency injection via lambda/callback creators* — fine-grained
  control over pipeline construction, services injected at the seam.
- *Modular camera synchronization* — one synchronizer handles cross-view
  cameras, not N per DM.
- *Layer-aware interaction and focus* — prioritised focus across
  pipelines without per-DM custom logic.
- *First-class Python abstract pipeline class* — pipelines authorable in
  Python via `vtkMRMLLayerDMScriptedPipeline` (imported in extension
  mode as `from LayerDMLib import vtkMRMLLayerDMScriptedPipeline`);
  tests are fast; iteration is seconds, not minutes.
- *Pipeline registration via factory + creator API* — replaces the
  string-based DM factory with typed registration.
- *Internally validated*: the same LayerDM architecture has been
  exercised in adjacent project work for resectogram-parallel
  functionalities — first-hand evidence that the framework scales
  past a single pipeline class and that we can build on it without
  hitting unforeseen ceilings.

Critically for SlicerLiver: with LayerDM in place, **the
`vtkMRMLMarkupsNode` inheritance constraint that forced the three-node
assembly disappears**.  An interactive Bezier-surface editing widget
can be registered as a LayerDM pipeline that observes a plain Storable
content node — no Markups inheritance required.

## Decision

We will migrate SlicerLiver's displayable managers and interactive
widgets from the current Markups + MRMLDM architecture to
**SlicerLayerDisplayableManager (LayerDM)** as the target DM framework.
Specifically:

1. **Adopt LayerDM as the only DM framework** for new Slicer-Liver
   widgets.  No new Markups-based geometry nodes; no new MRMLDM
   subclasses.

2. **Migrate the resection-editing pipeline** off Markups +
   `vtkMRMLLiverResectionsDisplayableManager2D` onto a LayerDM pipeline
   that:
   - reads a plain `vtkMRMLLiverResectionNode` (kept Storable, no
     Markups inheritance);
   - renders the Bezier surface and handles 3D interaction;
   - synchronises slice-view cross-sections via LayerDM's camera
     synchronizer.

3. **Collapse the three-node assembly where the Markups constraint
   forced it.**  Geometry (the 16 control points) and metadata (margins,
   colours, refs) merge onto a single content node.  The two-phase
   initialisation (Slicing vs Distance contour) is preserved as a
   *workflow* concern but no longer as a *node* concern — it lives in
   the LayerDM pipeline's state machine, not in a separate MRML node.

4. **Migration proceeds module-by-module**, in this order, each as a
   separate stack of PRs:
   1. `LiverMarkups` → migrate `BezierSurface`, `SlicingContour`,
      `DistanceContour` widgets to LayerDM pipelines.  Resection-side
      code temporarily bridges to the new pipeline while keeping the
      old Markups path alive (feature-flagged).
   2. `LiverResections` → collapse the three-node assembly; the six
      maps in Logic vanish; display fields move to a dedicated
      `vtkMRMLLiverResectionDisplayNode` (still C++, data-only).
   3. `LiverSegments`, `LiverVolumetry` — apply the same patterns.
   4. `Liver` — top-level module re-orchestrated to use the migrated
      submodules.
   5. Remove the feature flag and the legacy code paths.

5. **Unify the language seam, in line with ADR-0004.**  SlicerLiver
   today is a mix of C++ (MRML nodes, displayable managers, Bezier
   evaluation) and Python (resectogram analysis, scripted submodules).
   The migration is an opportunity to put each piece on the correct
   side of the seam rather than leave them scattered: compute-heavy
   or per-frame work moves into VTK filters (C++ when the performance
   budget demands it, Python-bound VTK filters otherwise), while
   business logic, workflow state, and pipeline orchestration live in
   Python LayerDM pipelines.  Existing Python code on the wrong side
   of the seam — and existing C++ code that is really business logic —
   relocates as part of the relevant module's migration PR.

6. **Each migration PR is governed by ADR-0003 (testability invariant)
   and ADR-0004 (Python/C++ boundary)** — characterisation tests land
   *before* the migration commits, and new code lands in Python unless
   it falls inside the C++ boundary defined by ADR-0004.

## Alternatives considered

### A. Incremental improvements to the Markups-based architecture

Keep the architecture, fix the worst pain points individually — collapse
the six maps to MRML node-reference attributes; introduce a dedicated
`vtkMRMLLiverResectionDisplayNode`; refactor
`vtkMRMLLiverResectionsDisplayableManager2D` to deduplicate boilerplate.

**Rejected** because this treats symptoms rather than causes.  The
three-node assembly itself is the structural cause (per ADR-0001), and
it persists for as long as Markups is the only way to get interactive
widgets.  Incremental fixes also leave us coupled to upstream Markups
evolution, which has its own roadmap and breaking-change cadence.
Three of the six pains (Markups interaction rigidity, DM boilerplate,
string-factory) are *upstream architectural debts* — in Markups and
the Slicer DM machinery — that incremental work inside Slicer-Liver
cannot reach.

### B. Custom DM rewrite without adopting LayerDM

Write our own `vtkSlicerLiverDisplayableManagerBase` with shared pipeline
infrastructure, dependency injection, and Python pipelines — addressing
the same pains as LayerDM but without the upstream dependency.

**Rejected** because it reinvents what the Kitware team has already
published, with worse outcomes:

- Years of design thinking (the LayerDM team has worked on these
  problems longer than any Slicer-Liver contributor will);
- No upstream bug fixes flow back to us;
- Other Slicer extensions adopting LayerDM gain features we'd have to
  re-port;
- Integration with Slicer's main camera, focus, and event routing is
  done correctly in LayerDM; reimplementing those is the kind of subtle
  work that only fully reveals its bugs in clinical use.

The only honest reason to take this path would be if LayerDM proved
unsuitable in a non-fixable way — none of the evaluation so far
suggests this.

### C. Ground-up rewrite of SlicerLiver on a new framework

Discard the current module and rebuild from scratch on LayerDM (or some
other framework) without preserving the existing code.

**Rejected** because it discards what works:

- Five years of clinical validation encoded in the current behaviour
  (Bezier evaluation parameters, margin computation, distance-map
  algorithms).
- Years of bug fixes accumulated from real surgical-planning use.
- Every saved `.lrp.fcsv` file in users' archives becomes unreadable
  unless we explicitly support its format in the rewrite anyway.
- The team capacity does not exist to absorb a multi-year cold-start
  while also maintaining clinical service.

A staged migration via this ADR preserves clinical service throughout
and uses `/slicer-review`-grade PR-level discipline to bound regression
risk.

### D. Wait for LayerDM to mature further before adopting

LayerDM is at 1.2.x as of 2026-05-13.  We could wait until 2.x to start
the migration, on the bet that the API stabilises further first.

**Rejected** for two reasons.  First, the longer we wait, the more
Slicer-Liver code accretes inside the Markups-based design, and each
new module raises the migration cost.  Second, adopting LayerDM now
puts us in a position to *influence* its 2.x design with our use cases
rather than receiving the result.  The semver guarantees on 1.x suggest
the public API surface is acceptable to commit against today.

## Consequences

### Easier

- **Testability** dramatically improves: LayerDM pipelines are Python
  classes with a clean abstract base.  Per ADR-0003, a unit test for a
  pipeline is a script that constructs a fake MRML scene, instantiates
  the pipeline, and asserts on its rendering output — no Qt event loop,
  no Slicer app bring-up.
- **Refactor cost drops** by an order of magnitude once a module is
  migrated: editing a Python LayerDM pipeline is seconds; editing a C++
  Markups widget is a Slicer rebuild.
- **The three-node resection assembly collapses** into a single content
  node + a LayerDM pipeline.  ADR-0001's documented complexities (six
  maps, one-way property sync, display-field leak) all disappear at the
  source.
- **Upstream alignment**: other Slicer extensions adopting LayerDM gain
  features we then benefit from automatically.
- **Per-module migration** gives natural review boundaries — each
  module's migration is a self-contained scope with its own
  characterisation tests, target diagram, and PR sequence.

### Harder

- **Backward compatibility with saved `.lrp.fcsv` files**: every clinical
  resection saved today must be readable post-migration.  This requires
  a format-detection branch in the new storage class and a migration
  path from the three-node assembly representation to the single-node
  representation.  Storage tests (per ADR-0003) must cover *both*
  formats during the transition.
- **Two architectures coexist** during the migration.  Each module's
  migration PR sequence must keep the legacy Markups path alive
  (feature-flagged) until the new path is proven; this doubles the
  surface area temporarily.
- **User-facing UX must remain identical** through the migration.  The
  surgical workflow (place initialisation contour → refine Bezier surface
  → adjust margins → save) cannot regress; characterisation tests at
  the UI level may need to be added to pin this (Slicer's
  `qSlicerTestRunner` framework supports widget-level tests).
- **Performance regressions** need to be characterised as inner loops
  are repackaged.  Bezier evaluation and distance-map computation
  stay in C++ (per ADR-0004), but the boundary crossing pattern
  changes; profile-before/after on representative cases is a
  precondition for merging each module's migration.
- **LayerDM is a new dependency** with its own release cadence.
  Slicer-Liver must pin to a known-good LayerDM version and update
  deliberately, not reflexively.

## References

- [SlicerLayerDisplayableManager](https://github.com/KitwareMedical/SlicerLayerDisplayableManager)
  — Kitware-maintained module, Slicer 5.10+.  Local checkout:
  `~/src/SlicerLayerDisplayableManager/`.  Online architecture docs:
  https://slicerlayerdisplayablemanager.readthedocs.io/
  - Pipeline manager:
    `LayerDM/MRMLDM/vtkMRMLLayerDMPipelineManager.{h,cxx}`.
  - Pipeline factory + lambda creators:
    `LayerDM/MRMLDM/vtkMRMLLayerDMPipelineFactory.{h,cxx}` and
    `vtkMRMLLayerDMPipelineCallbackCreator.{h,cxx}`.
  - Camera synchronizer:
    `LayerDM/MRMLDM/vtkMRMLLayerDMCameraSynchronizer.{h,cxx}`.
  - Interaction / focus logic:
    `LayerDM/MRMLDM/vtkMRMLLayerDMInteractionLogic.{h,cxx}`.
  - Python abstract pipeline class:
    `LayerDM/MRMLDM/Python/vtkMRMLLayerDMScriptedPipeline.py`
    (re-exported via `LayerDMLib` for extension consumers; the
    top-level `Python/` directory contains only a 2-line shim).
  - Pipeline interface accepting any `vtkMRMLNode*`:
    `vtkMRMLLayerDMPipelineI::SetDisplayNode` —
    `LayerDM/MRMLDM/vtkMRMLLayerDMPipelineI.h`.  This is what enables
    the Bezier-on-Storable migration without Markups inheritance.
- [ADR-0001 (descriptive predecessor)](0001-resection-three-node-assembly.md)
  — documents the current state and historical rationale that this ADR
  supersedes as the target.
- [`current-mrml-node-hierarchy.md`](../architecture/current-mrml-node-hierarchy.md)
  — the current shape this migration moves away from.
- Future:
  - ADR-0003 (testability invariant) — the safety net that bounds the
    regression risk of this migration.
  - ADR-0004 (Python/C++ boundary) — the implementation-language
    convention that defines where the migrated code lives.
  - `target-mrml-node-hierarchy.md` — the post-migration shape, to be
    drafted alongside the first module migration PR.

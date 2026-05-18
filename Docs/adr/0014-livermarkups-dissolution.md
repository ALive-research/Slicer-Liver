# 0014. Dissolve LiverMarkups; fold interactive resection primitives into LiverResections

- **Status:** Proposed
- **Date:** 2026-05-15
- **Deciders:** Rafael Palomar
- **Diagrams:** N/A (target MRML diagram and per-module UI diagrams land
  alongside the T2 LiverResections migration PR per
  [ADR-0009](0009-ux-and-design-discipline.md); this ADR fixes the
  *shape* those diagrams will record.)
- **PR:** _filled in on merge_

## Amendments

- **2026-05-18 — `{3×3, 4×4}` control polygons + NURBS extension surface (ADR-0018).**
  The v2.0.0 commitment in this ADR consistently refers to "the 4×4
  control grid".  Per [ADR-0018](0018-nurbs-extension-surface.md) §1
  the architectural commitment **admits two Bezier shapes**: 3×3 and
  4×4 (square only).  Both shapes preserve the corners / edges /
  interior ring philosophy:
  - 3×3: corners(4) + edges(4) + interior(1) = 9
  - 4×4: corners(4) + edges(8) + interior(4) = 16
  Per-setter validation on `vtkMRMLBezierSurfaceNode::SetRows` /
  `SetCols` rejects other `(Rows, Cols)` combinations.  Arbitrary
  M×N control polygons remain reserved for the v2.1 NURBS sibling
  representation per [ADR-0018][adr-0018-link] §3.  The widget
  event-table (`vtkLiverBezierWidget`) parameterizes on `(Rows,
  Cols)`; the same ring-of-control-points formula handles both
  shapes.  `.lrp.json` schema v2 carries explicit `rows` + `cols`
  alongside `controlGrid`; v1 files implicit-load as (4, 4); v2
  readers validate `(rows, cols) ∈ {(3, 3), (4, 4)}` and reject
  others.

[adr-0018-link]: 0018-nurbs-extension-surface.md

- **2026-05-16 — rename Bezier-surface MRML classes.**  The `Liver`
  prefix on the Bezier-surface MRML class trio
  (`vtkMRMLLiverBezierSurface{,Display,Storage}Node`) carries no
  semantic weight beyond project-scope decoration, which is already
  encoded by the file path (`LiverResections/MRML/`).  The classes are
  renamed to drop the prefix:
  `vtkMRMLBezierSurfaceNode`, `vtkMRMLBezierSurfaceDisplayNode`,
  `vtkMRMLBezierSurfaceStorageNode`.  The corresponding scene tag
  names (`"LiverBezierSurface"`, `"LiverBezierSurfaceDisplay"`) drop
  the prefix too.  `LiverResection` stays as a compound clinical noun
  — the project's defining concept — and the project-scope-named
  helpers around the Bezier surface (`LiverBezierSurfacePipeline`,
  `vtkLiverBezierWidget`) are unaffected; only the generic-geometric-
  primitive MRML nodes rename.  This amendment updates every
  reference in the ADR text below.

## Context

`LiverMarkups` today is a Markups-derived satellite module that hosts the
interactive primitives the resection-planning workflow uses.  Per the
inventory recorded in the v2.0.0 architecture handoff and visible in
`LiverMarkups/MRML/`, it ships three node pairs:

- `vtkMRMLMarkupsBezierSurfaceNode` (+ display) — the 4×4 control grid
  the surgeon edits in the Planning state; weakrefs the target model,
  distance map, and vascular segments; carries margin/thickness
  doubles.
- `vtkMRMLMarkupsSlicingContourNode` (+ display) — two control points
  defining a plane; the plane ∩ target model produces a ring that
  seeds the Bezier fit.
- `vtkMRMLMarkupsDistanceContourNode` (+ display) — two-or-more
  control points defining a spheroid (position + orientation +
  convexity); the spheroid ∩ target model produces the ring; richer
  parameterisation apparatus required (Elliptic Fourier Descriptors or
  similar).

The two contour nodes register with `SelectionNode` only when
`DeveloperMode` is true (see `vtkSlicerLiverMarkupsLogic::Observe
MRMLScene`); the Bezier surface always registers.  That registration
asymmetry already hints at the workflow-specific role of the contour
nodes — they are **not** independent annotations.  They are **two
alternative initialisation affordances for the same Bezier surface**,
each producing a ring that seeds the same downstream fit.  Calling
them "Markups" obscures that relationship in the data model and forces
each through Markups' point-list-centric machinery.

Two forces push the Bezier surface itself off the `vtkMRMLMarkupsNode`
base:

- **Ring-aware right-click.**  Surgically meaningful operations on the
  4×4 control grid group the points by ring role: corners (4), edges
  (8), interior (4).  Right-clicking any interior point should let the
  surgeon translate the inner ring as a unit; right-clicking a corner
  should grip the outer ring.  Markups' `vtkSlicerMarkupsWidget` is
  built around per-point semantics, owns its own right-click menu via
  `WidgetEventMenu` / `populateContextMenu`, and has no first-class
  concept of point groups.  Expressing the ring grouping on top of
  Markups is brittle and contorts the upstream event vocabulary —
  exactly the constraint catalogued in [ADR-0002](0002-migrate-to-slicerlayerdm.md)
  §4.
- **Per-role glyph rendering.**  The four corner, eight edge, and four
  interior control points each want their own glyph (size, shape,
  colour) so the surgeon can see at a glance which ring they are
  manipulating.  Markups' standard sphere glyph machinery is one
  glyph per node; per-role rendering on top of it is a continuous
  fight against upstream rendering assumptions.  The reusable
  ingredient already lives in the repo: `vtkOpenGLBezierResection
  PolyDataMapper`, `vtkOpenGLSlicingContourPolyDataMapper`,
  `vtkOpenGLDistanceContourPolyDataMapper`, and
  `vtkOpenGLResection2DPolyDataMapper` in `LiverMarkups/VTKWidgets/`.

The state machine that ties these primitives together has, until now,
lived **implicitly in scene contents**: "if a `SlicingContour` node
exists, we are in Initialization with SlicingPlane mode; if a
`DistanceContour` node exists, we are in Initialization with
DistanceSpheroid mode; if a `BezierSurface` node exists, we are in
Planning".  ADR-0013 §4 documents
the brittleness of that pattern: ambiguous scene round-trip mid-
transition, undo/redo crossing node boundaries, every state check is a
scene query.  PR #317's UI baseline at
`Docs/architecture/ui/liver-resections.md` already names the explicit
state machine: `vtkMRMLLiverResectionNode.ResectionState` (`Init` /
`Planning`) and `.InitializationMode` (`SlicingPlane` /
`DistanceSpheroid`).  The migration is the moment to make that
state machine first-class and dispense with the implicit-state-via-
scene-contents pattern altogether.

## Decision

The `LiverMarkups` module is dissolved in v2.0.0.  Its three
interactive primitives relocate into `LiverResections` as **non-Markups
data nodes**, driven by a single state-aware LayerDM Pipeline with
three Representations (per ADR-0013
§4 and §6) and a single custom widget that subclasses
`vtkAbstractWidget` directly.

### 1. Three primitives become non-Markups MRML data nodes in LiverResections

The three Markups-derived nodes relocate as plain `vtkMRMLDisplayable
Node` subclasses (no `vtkMRMLMarkupsNode` inheritance):

- `vtkMRMLBezierSurfaceNode` (+ `vtkMRMLBezierSurfaceDisplayNode`)
  — the 4×4 control grid plus ring-role metadata (which control
  points are corner / edge / interior); weakrefs to target model,
  distance map, vascular segments; the margin/thickness doubles
  previously hosted by `vtkMRMLMarkupsBezierSurfaceNode`.
- `vtkMRMLLiverSlicingPlaneInitNode` (no separate display node — its
  decoration lives on `vtkMRMLBezierSurfaceDisplayNode`'s
  state-conditional Representation) — two control points + plane
  parameters; persisted on the parent resection's data, not a
  separate scene node.
- `vtkMRMLLiverDistanceSpheroidInitNode` (same pattern) — two-or-more
  control points + spheroid parameters.

The two init-mode "nodes" are conceptually struct-shaped subordinate
data carried by the parent `vtkMRMLLiverResectionNode`, not free
MRML nodes.  Their control points persist on the resection's
`.lrp.fcsv` payload with explicit `init_mode` metadata, so a
Planning→Init drop-back recovers them losslessly.

### 2. One LayerDM Pipeline; three state-conditional Representations

Per ADR-0013 §4, a single
`LiverBezierSurfacePipeline` observes its display node *and* the
parent `vtkMRMLLiverResectionNode`'s `ResectionState` /
`InitializationMode` enums.  The Pipeline owns three Representations,
constructed once and reused across state transitions:

- `SlicingPlaneInitRepresentation` — active when `(ResectionState=Init,
  InitializationMode=SlicingPlane)`; renders the two control points,
  the plane, and the ring on the target liver surface.
- `DistanceSpheroidInitRepresentation` — active when `(ResectionState=
  Init, InitializationMode=DistanceSpheroid)`; renders the spheroid
  control points, the spheroid, and the ring.
- `BezierPlanningRepresentation` — active when `(ResectionState=
  Planning, *)`; renders the 4×4 grid with per-role glyphs and the
  fitted Bezier surface.

The Pipeline's `update()` selects the active Representation by the
`(state, mode)` tuple; no add/remove churn on the MRML scene as the
surgeon moves through the workflow.

### 3. Custom widget subclassing vtkAbstractWidget directly

A single `vtkLiverBezierWidget` subclasses `vtkAbstractWidget`
directly — *not* `vtkSlicerMarkupsWidget`.  Free design space:

- **Left-drag** = per-point manipulation (the Markups-equivalent
  semantics).
- **Right-drag** = ring-group translation (corner / edge / interior
  ring of the 4×4 grid moves as a unit).
- **Right-click** = own context menu (ring selection, mode switches,
  init-mode drop-back), free of `vtkSlicerMarkupsWidget::WidgetEvent
  Menu` / `populateContextMenu` constraints.

The four existing custom OpenGL mappers in `LiverMarkups/VTKWidgets/`
relocate to `LiverResections/VTKWidgets/` alongside the widget:

- `vtkOpenGLBezierResectionPolyDataMapper` — the surface.
- `vtkOpenGLSlicingContourPolyDataMapper`,
  `vtkOpenGLDistanceContourPolyDataMapper` — the init-mode rings.
- `vtkOpenGLResection2DPolyDataMapper` — the resectogram-flattened
  surface (carried over into the T3 Resectogram migration; relocated
  here only to keep the migration map clean).

This ADR commits to **relocating** these mappers, **not** to any
specific visual treatment for selected / ring-grouped / per-role
control points.  The selection-feedback design (per-role glyph shapes,
halo overlays around selected points, outline accents, colour
modulation, …) is a UX choice deferred to the T2 implementation
per [ADR-0009](0009-ux-and-design-discipline.md) §3 (design rationale
on every UI-touching PR).  The widget's right-click / right-drag
event-table semantics decided in §3 above are unaffected by that
deferred visual choice.

### 4. Init control points persist as read-only audit data after Init→Planning

After the Init→Planning transition, the init control points (two for
`SlicingPlane` mode, two-or-more for `DistanceSpheroid` mode)
**persist on the parent resection's data as read-only audit data**.
They serve two purposes:

- *Save / load fidelity.*  Round-tripping a resection through the
  storage layer (§5) recovers the geometry that originally seeded the
  Bezier fit — useful for clinical documentation and downstream audit
  ("which ring on which liver mesh produced this resection plan?").
- *UI annotation.*  The resection panel surfaces the originating
  init-mode and its control-point ring as read-only metadata so the
  surgeon can see "what fit produced this geometry".  Display
  treatment deferred to the T2 implementation per
  [ADR-0009](0009-ux-and-design-discipline.md) §3.

**There is no Planning→Init transition.**  Once Planning is reached,
the Bezier 4×4 grid is the sole *editable* representation of the
resection surface.  To re-initialise with a different ring, the
surgeon creates a *new* resection alongside the original (the new
resection runs through its own Init→Planning fit; the original
remains as the prior version).

Rationale: the Bezier grid in Planning may have moved arbitrarily far
from the original init ring; a Planning→Init drop-back would either
silently overwrite the surgeon's planning work or surface a misleading
"this ring is what you started from" affordance that no longer
matches the current geometry.  The current Markups-based workflow
effectively allowed drop-back via persistent `SlicingContour` /
`DistanceContour` nodes in the scene, but the practical clinical value
is dominated by the audit / save-load case, not by editorial
round-trips back to the init ring; the read-only persistence above
captures the former without re-introducing the latter's hazard.

Cost on the data node: 6-12 `double[3]` arrays per resection (18-36
floats).  Negligible.

### 5. Storage — new MRML storage node with JSON on-disk format

A **D-class break** per [ADR-0007](0007-version-numbering-policy.md)
is committed: symmetric round-trip with v1 `.lrp.fcsv` files is no
longer clean.  Already on the v1→v2 ticket and contributes to the
(D) trigger ADR-0007 §"Mapping the v1 → v2 jump" enumerates.

**Storage mechanism**: a new C++ MRML storage node
`vtkMRMLBezierSurfaceStorageNode` reads and writes `.lrp.json`
files — a purpose-built schema for the new data model.

JSON is the on-disk format choice (chosen over XML and over an
extended `.lrp.fcsv`):

- *Inspection-friendly.*  Surgeons and developers can open a
  `.lrp.json` in any text editor and read the resection geometry,
  init metadata, and state-machine fields without specialised tools.
- *Project precedent.*  Slicer's Segmentations module exports JSON
  alongside its segmentation files; aligns Slicer-Liver with that
  convention.
- *Schema-version-friendly.*  A top-level `"schemaVersion"` field
  carries the schema bump explicitly; future migrations are
  versioned.
- *Portability preserved.*  A single `.lrp.json` file carries a
  complete resection plan independent of the parent Slicer scene —
  surgeons can share individual resections between colleagues or
  sessions without round-tripping the entire scene MRML.  This was
  the practical reason the historical `.lrp.fcsv` existed and is
  preserved.

Rejected alternatives:

- *Extended `.lrp.fcsv`.*  Contorts a Markups-derived line-oriented
  CSV-with-comments format to carry structured state; the format was
  designed for fiducial-point lists, not for ring-role metadata +
  init-mode + state machine.
- *JSON sidecar to the scene MRML.*  Introduces split-brain
  geometry/state coordination between the scene `.mrml` and an
  external sidecar without earning the complexity for a tiny
  (~70 doubles total) data payload.

**On-disk fields:**

- The 16 Bezier control points (4×4 grid) with ring-role metadata
  (corner / edge / interior).
- The originating init-mode (`SlicingPlane` or `DistanceSpheroid`)
  and its read-only control points per §4.
- State-machine fields (`ResectionState`, `InitializationMode`) as
  string enums for human readability.
- Margins and decoration that previously lived on the data node
  (those move to the new display node per
  [ADR-0013](0013-layerdm-pipeline-pattern.md) §8, but data and
  display node both serialize through the same per-resection
  save/load path).
- Terminology references per
  [ADR-0011](0011-sct-terminology-dispatch.md) — SCT triples for the
  resection's clinical concept.
- Top-level `"schemaVersion"` field.

**v1 → v2 migration**: the storage class detects the legacy
`.lrp.fcsv` format on load and dispatches a one-way migration into
the new `.lrp.json` layout.  The legacy reader is preserved as a
load-only path for the v2.x cycle; legacy writes are not supported.
Batch conversion of existing `.lrp.fcsv` corpora deferred to a
follow-on migration tool if surgeon demand surfaces.

**File naming**: `.lrp.json` chosen for paradigm continuity
(`.lrp.*` was the historical Slicer-Liver convention) while the new
extension signals the format change.

Schema details — the exact JSON shape, the migration code path, and
any richer metadata (timestamps, surgeon ID, clinical context
fields) the new format could carry — land in the T2 implementation
PR.  v2.0.0 ships the minimal schema covering the dissolution
fields enumerated above.

### 6. Illustrative file layout

```
LiverResections/
  MRML/
    vtkMRMLBezierSurfaceNode.{h,cxx}        # data; 4×4 grid + ring-role + weakrefs
    vtkMRMLBezierSurfaceDisplayNode.{h,cxx} # visibility, opacity, terminology (ADR-0011)
  LiverBezierSurfacePipeline.py                   # LayerDM Pipeline (ADR-0013)
  Representations/
    SlicingPlaneInitRepresentation.py
    DistanceSpheroidInitRepresentation.py
    BezierPlanningRepresentation.py
  VTKWidgets/
    vtkLiverBezierWidget.{h,cxx}                  # subclasses vtkAbstractWidget directly
    vtkOpenGLBezierResectionPolyDataMapper.{h,cxx}    # relocated from LiverMarkups/
  Algorithm/                                      # per ADR-0015
```

`LiverMarkups/` disappears from the v2.0.0 module list entirely.

## Alternatives considered

### A. Keep LiverMarkups; LayerDM display migration only

Migrate the three Markups-derived nodes' *display* path to LayerDM
per [ADR-0002](0002-migrate-to-slicerlayerdm.md) and
ADR-0013, but leave the data
nodes inheriting from `vtkMRMLMarkupsNode` and the interaction layer
on `vtkSlicerMarkupsWidget`.

**Rejected** because ring-aware right-click on the 4×4 grid and
per-role control-point rendering are blocked at the Markups widget
base.  `vtkSlicerMarkupsWidget` owns its right-click menu through
`WidgetEventMenu` / `populateContextMenu` and treats control points
as independent atoms; expressing point groups on top of it is the
same fight ADR-0002 §4 already loses.  The Markups inheritance is the
specific constraint that needs to come off; migrating only the
display path leaves the load-bearing constraint in place.

### B. Move only BezierSurface; keep contours in LiverMarkups

Relocate `vtkMRMLMarkupsBezierSurfaceNode` into LiverResections as a
non-Markups data node (resolving the widget constraint), but keep
`vtkMRMLMarkupsSlicingContourNode` and `vtkMRMLMarkupsDistanceContour
Node` in LiverMarkups as Markups-derived annotation nodes.

**Rejected** because SlicingContour and DistanceContour are not
independent annotations.  They are two alternative initialisation
affordances for the same Bezier surface; both produce a ring on the
target liver mesh that seeds the same Bezier fit.  Keeping them in
LiverMarkups would preserve a module that exists only to host two
data carriers whose entire lifecycle is governed by the resection
workflow — re-entrenching the implicit-state-via-scene-contents
pattern ADR-0013 §4 retires.

### C. Three separate modules for the three primitives

Promote each of the three primitives to its own module
(`LiverBezierSurface`, `LiverSlicingPlaneInit`,
`LiverDistanceSpheroidInit`), each with its own MRML nodes, its own
Pipeline, its own custom widget.

**Rejected** because the three primitives are stations of a single
workflow (Init→Planning for the same resection), not independent
features.  Splitting them across modules multiplies the registration
boilerplate (three module classes, three `Logic` classes, three CMake
targets) for no separation-of-concerns benefit, and forces inter-
module references for what is conceptually one Pipeline with three
state-conditional Representations.  The dissolution of LiverMarkups
into LiverResections is the *opposite* direction: fewer modules for
the workflow they share.

## Consequences

### Easier

- **State machine becomes first-class.**  `ResectionState` and
  `InitializationMode` are typed enums on
  `vtkMRMLLiverResectionNode`, readable in one node access; the
  implicit-state-via-scene-contents pattern (and its undo/redo
  ambiguity) retires.  Scene round-trip in any intermediate state is
  unambiguous.
- **One Pipeline, one widget, one storage class** for the resection
  workflow.  T2 reviewers and `/slicer-review` evaluate the
  interactive surface against a single yardstick instead of three
  separate Markups subclasses.
- **First concrete instantiation of ADR-0013
  and [ADR-0011](0011-sct-terminology-dispatch.md).**  The Pipeline
  consumes SCT triples for colour and label decoration (replacing the
  hardcoded `HepaticContourColor` / `PortalContourColor` constants in
  the current `LiverMarkups` node constructors).  Sets the worked
  example T3 Resectogram reviews against.
- **The migration map simplifies to T2 + T3** per the
  [ADR-0012](0012-layerdm-migration-v2-scope.md) amendment.  One
  fewer migration phase; one fewer module's worth of LayerDM
  pattern-setting; the LiverMarkups → LiverResections cross-reference
  chain disappears.

### Harder

- **D-class compatibility break** per
  [ADR-0007](0007-version-numbering-policy.md): `.lrp.fcsv` schema
  bump for ring-role metadata, init-mode control points, and state-
  machine fields.  Already on the v1→v2 ticket; contributes to the
  (D) trigger ADR-0007 §"Mapping the v1 → v2 jump" enumerates.  The
  storage class detects the v1 layout and dispatches a one-way read
  migration into the v2 layout; v2 writes the v2 layout only.
- **N-class compatibility break** per ADR-0007: the
  `vtkMRMLMarkupsBezierSurfaceNode`, `vtkMRMLMarkupsSlicingContour
  Node`, and `vtkMRMLMarkupsDistanceContourNode` classes go away;
  the `LiverMarkups` module itself goes away.  Three node-class
  renames + one module removal.  Already on the v1→v2 ticket;
  contributes to the (N) trigger.
- **Custom widget infrastructure cost.**  Subclassing
  `vtkAbstractWidget` directly means re-implementing the parts of
  `vtkSlicerMarkupsWidget` Slicer-Liver actually uses (event
  routing, handle representation, picking).  The four custom OpenGL
  mappers relocate intact, but the widget itself is new code in T2.
- **Characterisation tests come first.**  Per
  [ADR-0008](0008-testing-strategy.md) and
  [ADR-0003](0003-testability-invariant.md), the migration is gated
  on characterisation tests pinning current LiverMarkups behaviour:
  display-node lifecycle on scene load, the `DeveloperMode`-
  conditional `SelectionNode` registration filter, `Logic::OnMRML
  SceneNodeAdded` invariants (`SnapMode=Unconstrained`,
  `PropertiesLabelVisibilityOff`), target/distance-map/vascular-
  segments weakref preservation across save/load, and representation
  actor lifetime under display-flag toggles.  Extends the PR #294
  characterisation harness.

## Migration steps

The T2 LiverResections (all-in) phase lands in this order:

1. **Characterisation tests first.**  Extend PR #294's harness to
   cover the five fragile-path candidates enumerated under
   "Harder" above.  These tests pin current `LiverMarkups`
   behaviour and are the regression yardstick for everything
   downstream.
2. **New MRML node types** in `LiverResections/MRML/`:
   `vtkMRMLBezierSurfaceNode`, `vtkMRMLBezierSurfaceDisplayNode`.
   Data-only C++ per [ADR-0004](0004-python-cpp-boundary.md) §1.
3. **State-machine fields** on `vtkMRMLLiverResectionNode`:
   `ResectionState` (`Init`/`Planning`) and `InitializationMode`
   (`SlicingPlane`/`DistanceSpheroid`) as typed enums with
   `Set/Get` accessors, `WriteXML`/`ReadXMLAttributes` plumbing,
   and `Modified()` events on transition.
4. **LiverBezierSurfacePipeline + three Representations** per
   ADR-0013 — Python, observing
   both the display node and `vtkMRMLLiverResectionNode`'s state
   machine.  Ships with the three-tier test set (module test,
   per-Representation unit tests, workflow test using the
   `render_interactive` fixture).
5. **Custom widget** `vtkLiverBezierWidget` (C++, subclasses
   `vtkAbstractWidget` directly) plus relocation of the four custom
   OpenGL mappers from `LiverMarkups/VTKWidgets/` to
   `LiverResections/VTKWidgets/`.
6. **`.lrp.fcsv` schema bump** in the LiverResections storage class:
   v1-format read migration (detect by absence of state-machine
   fields), v2-format read/write, plus a v1→v2 read-migration test
   against curated v1 sample files.
7. **Liver scripted-module "Place resection" button** wires through
   the new state machine: clicking Place creates a
   `vtkMRMLLiverResectionNode` with `ResectionState=Init,
   InitializationMode=SlicingPlane` (default) and activates the
   Pipeline's `SlicingPlaneInitRepresentation`.  Replaces the
   current Markups-toolbar Place flow.
8. **LiverMarkups module removal**: delete `LiverMarkups/`, the
   `qSlicerLiverMarkupsModule` registration, the `add_subdirectory`
   call in the top-level `CMakeLists.txt`, and all inbound
   references in `LiverResections/` and the `Liver/` scripted
   module.  Confirmed clean by a full `ctest` plus a
   `pytest -k livermarkups` sweep returning zero collected tests.
9. **Diagram refresh** per [ADR-0009](0009-ux-and-design-discipline.md):
   the target-MRML-node-hierarchy diagram and the
   `Docs/architecture/ui/liver-resections.md` baseline (landed in
   PR #317) update to reflect the dissolved module and the
   state-aware Pipeline.

## References

- Related ADRs:
  - [ADR-0001](0001-resection-three-node-assembly.md) — the
    descriptive record of the three-node assembly this ADR
    supersedes for the interactive primitives.
  - [ADR-0002](0002-migrate-to-slicerlayerdm.md) — the canonical
    LayerDM migration direction; §4 documents the Markups
    interaction-model ceiling that ADR-0014 finally clears.
  - [ADR-0004](0004-python-cpp-boundary.md) — fixes the language
    band for the new node classes (C++ data-only) and the Pipeline +
    Representations (Python).
  - [ADR-0007](0007-version-numbering-policy.md) — governs the
    D-class (`.lrp.fcsv` schema bump) and N-class (module + node
    removal) breaks under the v1→v2 jump.
  - [ADR-0008](0008-testing-strategy.md) — the characterisation
    discipline and the three-tier test layering applied to the new
    Pipeline.
  - [ADR-0009](0009-ux-and-design-discipline.md) — UI-diagram
    obligation for the migration; the `liver-resections.md`
    baseline lands in PR #317 and updates with this work.
  - [ADR-0011](0011-sct-terminology-dispatch.md) — terminology
    dispatch wires into the new display node for colour, label, and
    badge presentation; replaces the hardcoded contour colours in
    the current `LiverMarkups` constructors.
  - [ADR-0012](0012-layerdm-migration-v2-scope.md) (amended) — the
    v2.0.0 migration map collapses to T2 + T3 in light of this ADR.
  - ADR-0013 — the canonical
    Pipeline + Representation shape this ADR instantiates; §4 is
    the state-aware-Pipeline pattern.
  - [ADR-0015](0015-cpp-algorithm-library.md) — the C++ algorithm
    library under `LiverResections/Algorithm/` that the Init→Planning
    transition consumes.
- Implementation-relevant PRs:
  - PR #294 — `.lrp.fcsv` round-trip characterisation harness;
    extended in step 1 of the migration.
  - PR #315 — SCT terminology assets the new display node consumes.
  - PR #316 — pytest scaffold the three-tier test set lands on.
  - PR #317 — workflow-diagram baseline; this ADR's PR refreshes
    `Docs/architecture/ui/liver-resections.md` against the
    state-aware Pipeline.

---

*AI-assisted authorship: this pull request was drafted with help from Anthropic's Claude (Opus 4.7, `claude-opus-4-7`) via Claude Code. Plan and brief from the orchestrating Opus 4.7 session per the handoff at `.claude/handoff-2026-05-15-v2-architecture.md`; prose drafted by a Claude Code subagent. Opened for human review before merge.*

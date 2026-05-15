# 0014. Dissolve LiverMarkups; fold interactive resection primitives into LiverResections

- **Status:** Proposed
- **Date:** 2026-05-15
- **Deciders:** Rafael Palomar
- **Diagrams:** N/A (target MRML diagram and per-module UI diagrams land
  alongside the T2 LiverResections migration PR per
  [ADR-0009](0009-ux-and-design-discipline.md); this ADR fixes the
  *shape* those diagrams will record.)
- **PR:** _filled in on merge_

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
Planning".  [ADR-0013](0013-layerdm-pipeline-pattern.md) §4 documents
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
three Representations (per [ADR-0013](0013-layerdm-pipeline-pattern.md)
§4 and §6) and a single custom widget that subclasses
`vtkAbstractWidget` directly.

### 1. Three primitives become non-Markups MRML data nodes in LiverResections

The three Markups-derived nodes relocate as plain `vtkMRMLDisplayable
Node` subclasses (no `vtkMRMLMarkupsNode` inheritance):

- `vtkMRMLLiverBezierSurfaceNode` (+ `vtkMRMLLiverBezierSurfaceDisplay
  Node`) — the 4×4 control grid plus ring-role metadata (which
  control points are corner / edge / interior); weakrefs to target
  model, distance map, vascular segments; the margin/thickness
  doubles previously hosted by `vtkMRMLMarkupsBezierSurfaceNode`.
- `vtkMRMLLiverSlicingPlaneInitNode` (no separate display node — its
  decoration lives on `vtkMRMLLiverBezierSurfaceDisplayNode`'s
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

Per [ADR-0013](0013-layerdm-pipeline-pattern.md) §4, a single
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

Per-role glyph rendering wires through the four existing custom OpenGL
mappers in `LiverMarkups/VTKWidgets/` (relocated to `LiverResections/
VTKWidgets/` alongside the widget):

- `vtkOpenGLBezierResectionPolyDataMapper` — the surface.
- `vtkOpenGLSlicingContourPolyDataMapper`,
  `vtkOpenGLDistanceContourPolyDataMapper` — the init-mode rings.
- `vtkOpenGLResection2DPolyDataMapper` — the resectogram-flattened
  surface (carried over into the T3 Resectogram migration; relocated
  here only to keep the migration map clean).

### 4. Init control points persist across Init→Planning

After the Init→Planning transition, the two (SlicingPlane) or
two-or-more (DistanceSpheroid) init control points **persist** on the
parent resection's data.  A Planning→Init drop-back recovers them
losslessly; a save/load round-trip in either state captures the
surgeon's intent across the state boundary.  Cost on the data node is
negligible (a handful of `double[3]` arrays per resection); the
alternative — discarding the init control points at the state
transition — gives up recoverable workflow intent for no payoff.

### 5. Storage rides through LiverResections' .lrp.fcsv with a schema bump

The existing `.lrp.fcsv` storage class (per
[ADR-0001](0001-resection-three-node-assembly.md) §3 and the round-trip
test added in PR #294) absorbs the new fields:

- Ring-role metadata on the 16 Bezier control points (corner / edge /
  interior).
- Init-mode control points (2 for SlicingPlane, ≥2 for
  DistanceSpheroid).
- State-machine fields (`ResectionState`, `InitializationMode`) as
  typed enums.

This is a **D-class break** per [ADR-0007](0007-version-numbering-policy.md)
(symmetric round-trip with v1 `.lrp.fcsv` files is no longer clean);
it is already on the v1→v2 ticket and contributes to the (D) trigger
ADR-0007 §"Mapping the v1 → v2 jump" enumerates.

### 6. Illustrative file layout

```
LiverResections/
  MRML/
    vtkMRMLLiverBezierSurfaceNode.{h,cxx}        # data; 4×4 grid + ring-role + weakrefs
    vtkMRMLLiverBezierSurfaceDisplayNode.{h,cxx} # visibility, opacity, terminology (ADR-0011)
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
[ADR-0013](0013-layerdm-pipeline-pattern.md), but leave the data
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
pattern [ADR-0013](0013-layerdm-pipeline-pattern.md) §4 retires.

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
- **First concrete instantiation of [ADR-0013](0013-layerdm-pipeline-pattern.md)
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
   `vtkMRMLLiverBezierSurfaceNode`, `vtkMRMLLiverBezierSurfaceDisplay
   Node`.  Data-only C++ per [ADR-0004](0004-python-cpp-boundary.md)
   §1.
3. **State-machine fields** on `vtkMRMLLiverResectionNode`:
   `ResectionState` (`Init`/`Planning`) and `InitializationMode`
   (`SlicingPlane`/`DistanceSpheroid`) as typed enums with
   `Set/Get` accessors, `WriteXML`/`ReadXMLAttributes` plumbing,
   and `Modified()` events on transition.
4. **LiverBezierSurfacePipeline + three Representations** per
   [ADR-0013](0013-layerdm-pipeline-pattern.md) — Python, observing
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
  - [ADR-0013](0013-layerdm-pipeline-pattern.md) — the canonical
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

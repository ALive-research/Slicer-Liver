# 0013. The Slicer-Liver LayerDM Pipeline pattern

- **Status:** Proposed
- **Date:** 2026-05-15
- **Deciders:** Rafael Palomar
- **Diagrams:** N/A (target MRML diagram and per-module UI diagrams
  land alongside each migration PR per ADR-0009; this ADR fixes the
  *shape* those diagrams will record).
- **PR:** _filled in on merge_

## Context

[ADR-0002](0002-migrate-to-slicerlayerdm.md) commits Slicer-Liver to
**SlicerLayerDisplayableManager (LayerDM)** as the target displayable-
manager framework.  [ADR-0012](0012-layerdm-migration-v2-scope.md)
scopes the v2.0.0 slice of that migration; the corrected map (per
ADR-0014 and ADR-0015, forthcoming) folds the LiverMarkups dissolution
and BezierSurface relocation into a single **T2 — LiverResections,
all-in** phase, followed by **T3 — Resectogram** (renumbered from the
older T4) and its entangled **distance-map** display path.  Both
module-shaped migrations instantiate the same implementation pattern.
ADR-0002 names LayerDM as the *framework*; ADR-0012 names the
*modules*; what is still missing is the *shape every migration
instantiates*.

Without that shape committed up-front, the first migration (T2
LiverResections) becomes a de facto precedent set by whichever
decisions its author makes under PR pressure, and the next migration
either re-litigates those decisions or copies patterns silently.  The
v2.0.0 cutover is the right moment to fix the shape so both PRs
review against the same yardstick.

The reference points are already in the project's orbit:

- **Kitware's [SlicerLayerDisplayableManager](https://github.com/KitwareMedical/SlicerLayerDisplayableManager)**
  is the upstream framework.  Its core driver
  (`vtkMRMLLayerDMDisplayableManager`) instantiates one *Pipeline*
  per display node it sees in the scene, via the
  `vtkMRMLLayerDMPipelineFactory` + callback-creator API.  The
  Python-authorable base class is `vtkMRMLLayerDMScriptedPipeline`,
  imported in extension mode as
  `from LayerDMLib import vtkMRMLLayerDMScriptedPipeline`
  (see ADR-0002 references).
- **[trame-slicer](https://github.com/KitwareMedical/trame-slicer)**
  exercises the same idea from Python orchestration: `slicer_renderer/`
  carries one Pipeline subclass per renderable node type, each
  observing its node and owning a small set of VTK actor/mapper
  assemblies.  That project is also the source of the
  `render_interactive` fixture pattern adopted in ADR-0008 §3.
- **[SlicerHyperProbe](https://github.com/MESH-Lab/SlicerHyperProbe)**
  — an in-project precedent: `vtkMRMLHyperprobeViewDisplayNode`
  (data-only C++ display node) + `vtkMRMLHyperprobeViewPipeline`
  (the LayerDM Pipeline subclass that decorates it).  Slicer-Liver
  has already used this pair in HyperProbe-parallel work; that
  experience is what ADR-0002 cites as "internally validated".

These three references converge on the same shape: **one Pipeline
per display-node type, with the data node carrying geometry and the
display node carrying decoration**.  This ADR commits Slicer-Liver to
that shape and pins the conventions (naming, file layout, lifecycle,
representation factoring, testability) that the three v2.0.0
migrations will all instantiate.

## Decision

Slicer-Liver adopts the following canonical *LayerDM Pipeline
pattern* for every module migrating under ADR-0012.  The shape is
non-negotiable for the three v2.0.0 migrations; future modules
migrating under ADR-0002's broader direction follow the same shape
unless a superseding ADR records a different choice.

### 1. One Python Pipeline class per display-node type

Each `vtkMRMLLiver<Module>DisplayNode` has exactly one Pipeline
subclass of `vtkMRMLLayerDMScriptedPipeline`.  Pipelines are
**Python**, per [ADR-0004](0004-python-cpp-boundary.md) — they hold
business logic, observe MRML events, and orchestrate VTK
assemblies.  LayerDM's first-class Python API makes this the
natural side of the seam.

The Pipeline-per-display-node contract — *not* per data node — is
the SLDM-native shape: the same data node can be rendered by
multiple Pipelines (e.g. a resection in the 3D view and again,
flattened, in the resectogram side panel), each driven by its own
display node carrying its view-specific decoration.  Pinning to
data nodes would forfeit that compositional axis.

### 2. C++ side stays data-only

The matching `vtkMRMLLiver<Module>DisplayNode` is a **C++ data-only
node** per [ADR-0004](0004-python-cpp-boundary.md) §1: typed fields,
`Set/Get` accessors, `Copy()` / `PrintSelf()` / `WriteXML()` /
`ReadXMLAttributes()`, and `vtkMRMLCopyContent` / `InvokeEvent`
plumbing.  It carries visibility flags, opacity, picked-state
booleans, terminology references, and the small set of decoration
parameters specific to its node type.  It carries **no** VTK
actors, no observers, no rendering logic — those belong in the
Pipeline.

### 3. Pipeline responsibilities

A Slicer-Liver Pipeline subclass:

- **Observes its display node** for `vtkCommand::ModifiedEvent`,
  along with the events LayerDM's base class wires up on the
  associated data node.
- **Owns one or more Representations** (see §6) — the renderable
  VTK assemblies it manages.
- **Wires SCT-terminology dispatch** where its display node
  carries a terminology reference, per
  [ADR-0011](0011-sct-terminology-dispatch.md): colour, label, and
  badge presentation derive from the SCT triple via the project's
  terminology utilities — never from string labels inside the
  Pipeline.
- **Exposes a clean `update()` method** that the LayerDM driver
  calls when the display node, the data node, or the view state
  changes.  `update()` reads current state, reconciles the
  Representations, and returns.  It must be idempotent: calling it
  twice with no state change must be a no-op observationally.

### 4. Pipelines may observe orchestrating-state nodes

A Pipeline's observation set is not limited to its own display node.
When the displayed concept's behaviour depends on a state machine
carried by *another* MRML node (typically the parent module's
orchestrating node — e.g. `vtkMRMLLiverResectionNode`'s
`ResectionState` / `InitializationMode`), the Pipeline observes both:
its own display node *and* the orchestrating-state node.

Representations are the natural unit for *state-conditional
rendering*: a single Pipeline owns multiple Representations, and the
Pipeline's `update()` activates whichever Representation matches the
current `(state, mode)` tuple.  Lifetimes stay simple —
Representations are constructed once when the Pipeline is built and
reused across state transitions, so there is no add/remove churn on
the MRML scene as the user moves through the workflow.

Contrast with the historical pattern where state was carried
*implicitly* by which nodes happened to be in the scene at a given
moment ("if a SlicingContour node exists, we're in Initialization"):
brittle scene round-trip, ambiguous undo/redo, and every state check
is a scene query instead of a typed enum read on a single node.
State-aware Pipelines make the state machine first-class.

### 5. Lifecycle

Pipelines are created and destroyed by LayerDM's
`vtkMRMLLayerDMPipelineManager` via the factory + creator API, not
by hand:

- **Creation** — the module's Logic registers a Pipeline-creating
  callback with `vtkMRMLLayerDMPipelineFactory` at module load.
  When a `vtkMRMLLiver<Module>DisplayNode` is added to the scene,
  LayerDM invokes the creator, which instantiates the Pipeline,
  attaches it to the display node, and adds it to the active
  view's pipeline set.
- **Updates** — the Pipeline observes the display node's
  `ModifiedEvent` and the data node's geometry events; both route
  through its `update()`.
- **Destruction** — removing the display node from the scene tears
  the Pipeline down via the manager.  The Pipeline's
  `cleanup()` releases observers and detaches actors; no manual
  bookkeeping in the module Logic.
- **Scene save/load** — the Pipeline is **not** persisted.  On
  `vtkMRMLScene::EndImportEvent`, LayerDM re-runs the creator
  callback for every restored display node, reconstituting the
  Pipeline from the persisted display- and data-node state.  This
  is the contract that lets data nodes shrink (see §7) without
  breaking round-trip.

### 6. Representations — composable, testable VTK units

A *Representation* is the smallest renderable unit a Pipeline
owns: one VTK actor + its mapper(s) + any per-frame state.
Examples a Pipeline might own:

- A resection-surface mesh Representation (`vtkActor` +
  `vtkPolyDataMapper` over the Bezier output).
- A locator-crosshair Representation in the resectogram view.
- A terminology-driven label badge Representation
  (`vtkBillboardTextActor3D` keyed off the SCT `CodeMeaning`).

Each Representation is a small Python class with a constructor,
an `update(display_node, data_node)` method, and a `cleanup()`
method.  Representations are unit-testable in isolation against
stub nodes — no Pipeline, no LayerDM, no Slicer app required.

Pipelines compose Representations.  When a new module variant
arrives (e.g. a NURBS surface alongside the Bezier surface, per
ADR-0002 §1.4), it ships as a new Representation slotted into the
existing Pipeline, not as a parallel Pipeline class.

### 7. Naming and file layout

| Artefact | Name | Path |
|---|---|---|
| MRML data node (existing or new, C++) | `vtkMRMLLiver<Module>Node` | `Liver<Module>/MRML/` |
| MRML display node (C++ data-only) | `vtkMRMLLiver<Module>DisplayNode` | `Liver<Module>/MRML/` |
| LayerDM Pipeline (Python) | `<Module>Pipeline` | `Liver<Module>/<Module>Pipeline.py` |
| Representations (Python) | `<Concept>Representation` | `Liver<Module>/Representations/<Concept>Representation.py` |
| Pipeline tests | `test_<module>_pipeline.py` | `Liver<Module>/Testing/Python/` |
| Representation tests | `test_<concept>_representation.py` | `Liver<Module>/Testing/Python/` |

The Python module layout mirrors the existing scripted modules
(`LiverVolumetry/LiverVolumetry.py`, `Liver/Liver.py`).  The
`Representations/` subdirectory is new and introduced by the T2
LiverResections PR; subsequent migrations populate it.

### 8. Data nodes shrink — display state leaves the data node

As each module migrates, the ~30 display-related fields that
[ADR-0002](0002-migrate-to-slicerlayerdm.md) §3 documents leaking
onto `vtkMRMLLiverResectionNode` (margins, colours, grid divisions,
opacity, widget visibility, interpolated-margin flags) **move to
the new display node**.  The data node keeps only geometry and
clinically authoritative metadata (terminology refs, references to
parent segmentations and target structures).

This is the structural payoff of the migration.  It is also a
break of `.lrp.fcsv` round-trip for any persisted display state
in the old data-node XML — see Consequences below.

### 9. Testability — one Pipeline test, one Representation test, one workflow test

Per [ADR-0008](0008-testing-strategy.md), every Pipeline subclass
ships **three** tests, one per layer:

- **Module-layer Pipeline test** — `test_<module>_pipeline.py`
  constructs the Pipeline against a stub `vtkMRMLLiver<Module>
  DisplayNode` and stub data node, drives `update()`, and asserts
  on Representation state (visible? colour matches the
  terminology? margin actor present?).  No Qt, no view.
- **Unit-layer Representation tests** — one per Representation
  class, asserting actor/mapper outputs against synthetic input.
  No Slicer scene needed.
- **Workflow-layer integration test** — uses the
  `render_interactive` fixture from
  [ADR-0008](0008-testing-strategy.md) §3 to drive the Pipeline
  end-to-end through a real `vtkMRMLLayerDMDisplayableManager` in
  a real view.  In CI this runs offscreen; with
  `pytest --render-interactive=5` a developer sees the same
  assertions execute on visible pixels.

The T2 LiverResections PR therefore **delivers the "real-view
fixture" deferred by PR #316** — the missing piece of the ADR-0008
test pyramid that the pytest scaffold left as a TODO.

### 10. Pipeline class skeleton (illustrative)

```python
from LayerDMLib import vtkMRMLLayerDMScriptedPipeline
from .Representations import SurfaceRepresentation, MarginRepresentation

class ResectionsPipeline(vtkMRMLLayerDMScriptedPipeline):
    def initialize(self):
        self._surface = SurfaceRepresentation(self.GetRenderer())
        self._margin = MarginRepresentation(self.GetRenderer())

    def update(self):
        display = self.GetDisplayNode()
        data = display.GetDisplayableNode()
        self._surface.update(display, data)
        self._margin.update(display, data)

    def cleanup(self):
        self._surface.cleanup()
        self._margin.cleanup()
```

The base class supplies the renderer handle, observer wire-up, and
the manager-driven creation/destruction.  Full implementation
lands in T2; this skeleton fixes the shape, nothing more.

## Alternatives considered

### A. All-C++ Pipeline

Implement each Pipeline as a C++ subclass of
`vtkMRMLLayerDMPipelineI` rather than `vtkMRMLLayerDMScripted
Pipeline`, mirroring the legacy `vtkMRMLLiverResectionsDisplayable
Manager2D` style but on the LayerDM substrate.

**Rejected** because it violates
[ADR-0004](0004-python-cpp-boundary.md) §2 — Pipeline code is
business logic and orchestration, exactly the Python band.
LayerDM exposes a first-class Python pipeline class precisely so
this kind of code can iterate in seconds; reverting to C++ for
Pipelines forfeits that benefit and pays the refactor-cost penalty
ADR-0004 catalogues.  None of the three v2.0.0 Pipeline workloads
(resection orchestration, resectogram driving, distance-map
texturing) has a profile-justified inner-loop need that would
overrule the Python default.

### B. One Pipeline per data-node type, no display node

Skip the display-node split: have each Pipeline observe the data
node directly, and store decoration (visibility, opacity,
terminology) on the data node.

**Rejected** because it breaks the SLDM contract (per-display-node
Pipeline instantiation via the factory + creator API) and forfeits
the compositional axis that lets multiple Pipelines render the
same data: one resection in 3D *plus* its flattening in the
resectogram side panel cannot share a data node without separate
display nodes carrying view-specific decoration.  It also re-
entrenches the ADR-0002 §3 leak where ~30 display fields live on
the data node — the very pain the migration is meant to retire.

### C. Skip the Pipeline abstraction; inline VTK wiring in the module Logic

Have each module's Logic class create actors/mappers directly,
attach them to the view's renderer, and observe MRML events in
the Logic.  No Pipeline class, no Representation class.

**Rejected** because it recreates the historical "everything in
Logic" problem that [ADR-0002](0002-migrate-to-slicerlayerdm.md)
§2 already documents (the six `std::map` members, the leaked
display fields, the one-way property sync).  The Pipeline
abstraction is the structural fix.  Skipping it would land
LayerDM without absorbing the architectural lesson the migration
is paid for.

### D. Adopt trame-slicer's Pipeline base directly

Subclass trame-slicer's `slicer_renderer/` Pipeline classes
rather than LayerDM's `vtkMRMLLayerDMScriptedPipeline`.

**Deferred.**  trame-slicer is an excellent reference and shares
deep design DNA with LayerDM, but it is a separate project with
its own runtime model (trame server, web-first rendering).
Slicer-Liver's v2.0.0 ships as a desktop Slicer extension; the
Kitware LayerDM base is the right substrate for that runtime.
If trame-slicer ever becomes a Slicer-Liver runtime dependency
— e.g. for a web-deployed surgical-planning surface — revisit
under a follow-up ADR.

## Consequences

### Easier

- **Reviewer load drops after the first migration.**  T2
  LiverResections (all-in, per ADR-0014 forthcoming) instantiates
  the pattern; T3 Resectogram reviews against the same yardstick.
  Once the shape is fixed, the per-PR question reduces to "does
  this Pipeline follow the pattern?" rather than "what is the
  right shape here?".  `/slicer-review` enforces the shape
  mechanically (file layout, naming, three-tier test set).
- **SCT-terminology dispatch lands cleanly inside the Pipeline.**
  Per [ADR-0011](0011-sct-terminology-dispatch.md), the Pipeline
  reads the display node's terminology reference and dispatches
  presentation (colour, label, badge) from the SCT triple — the
  first concrete use of the terminology assets shipped by PR #315.
  Combo-box elimination per ADR-0009 follows as a corollary.
- **Pipeline-per-display-node composes.**  The same resection
  data node renders as a 3D surface Pipeline *and* as a
  resectogram-flattened Pipeline simultaneously, each carrying
  its own decoration.  This is the cross-view-coupled workflow
  ADR-0012 names as the LayerDM payoff.
- **Representations are unit-testable in isolation.**  Each
  Representation has a constructor, an `update()`, a
  `cleanup()`, and no Slicer-app dependency.  Coverage gaps are
  visible at the Representation level, not buried inside an
  end-to-end test.

### Harder

- **Data nodes shrink — `.lrp.fcsv` round-trip breaks for old
  display state.**  Any display fields persisted in the old
  data-node XML must be migrated to the new display node on load.
  This is a **D-class break** per
  [ADR-0007](0007-version-numbering-policy.md) and already
  justifies the v1→v2 jump (see ADR-0012); call it out explicitly
  in the v2.0.0 release notes so it does not surprise consumers
  re-opening legacy scenes.  The storage class (C++ per ADR-0004)
  detects the old format and dispatches a one-way migration into
  the new display-node layout.
- **Every Pipeline must ship its three-tier test set.**  Module
  test, Representation tests, workflow test with
  `render_interactive`.  The pytest scaffold is in place per PR
  #316; the *real-view fixture* the scaffold left as a TODO lands
  in T2 LiverResections and is the precondition for T3.
- **Two architectures coexist during v2.0.0.**  Per
  [ADR-0002](0002-migrate-to-slicerlayerdm.md) Consequences, the
  legacy Markups path stays alive feature-flagged until the
  LayerDM Pipeline path passes characterisation.  Each migration
  PR carries both paths until cut-over; doubled surface area is
  the price of bounded regression risk.
- **Module Logic shrinks but does not disappear.**  Logic still
  owns: factory-callback registration at module load, scene-level
  bookkeeping (responding to `NodeAdded` / `NodeRemoved` if the
  module owns the creation of `vtkMRMLLiver<Module>DisplayNode`
  instances), and any compute that does not belong inside a
  Pipeline.  The six `std::map` members in
  `vtkSlicerLiverResectionsLogic` go away; the Logic itself stays.

## Migration steps unlocked

The two v2.0.0 migration phases under
[ADR-0012](0012-layerdm-migration-v2-scope.md) (as amended by the
design discussion folding LiverMarkups into LiverResections — see
ADR-0014) each instantiate this
pattern once:

1. **T2 — LiverResections (all-in).**  Pattern-setting migration.
   Absorbs the LiverMarkups dissolution: the three Markups-derived
   primitives (BezierSurface + SlicingContour + DistanceContour)
   relocate into LiverResections as non-Markups data nodes.  One
   state-aware Pipeline (per §4 above) owns three state-conditional
   Representations — `SlicingPlaneInitRepresentation`,
   `DistanceSpheroidInitRepresentation`, and
   `BezierPlanningRepresentation` — observing both the display node
   and `vtkMRMLLiverResectionNode`'s `ResectionState` /
   `InitializationMode` enums.  A custom widget subclassing
   `vtkAbstractWidget` directly (not `vtkSlicerMarkupsWidget`) wires
   ring-aware right-click and per-role glyph rendering per
   ADR-0014.  Bezier-fitting and
   ring-extraction algorithms lift to a C++ algorithm library per
   ADR-0015.  Display fields leave
   `vtkMRMLLiverResectionNode` and land on the new
   `vtkMRMLLiverBezierSurfaceDisplayNode` (per §8 above).
   Establishes `Liver<Module>/<Module>Pipeline.py` and the
   `Representations/` subdirectory; delivers the real-view fixture
   deferred by PR #316; provides the worked example T3 reviews
   against.
2. **T3 — Resectogram + distance maps.**  Splits the resectogram
   into its own Pipeline composing the locator-crosshair,
   flattened-surface, and vascular-contour Representations.  The
   distance-map display path folds in along the way — its texture
   is a Representation inside the resectogram Pipeline per ADR-0012
   ("entangled with resectogram texture generation").

ADR-0012 defers the LiverSegments / LiverVolumetry / modelling
LayerDM migrations to v2.1.0; when they land, they instantiate
the same pattern.

## References

- [SlicerLayerDisplayableManager](https://github.com/KitwareMedical/SlicerLayerDisplayableManager)
  — upstream framework.  Pipeline base
  (`vtkMRMLLayerDMScriptedPipeline`), factory + creator API
  (`vtkMRMLLayerDMPipelineFactory`,
  `vtkMRMLLayerDMPipelineCallbackCreator`), and driver
  (`vtkMRMLLayerDMDisplayableManager`).
- [trame-slicer](https://github.com/KitwareMedical/trame-slicer)
  — Python-orchestrated Pipeline pattern in `slicer_renderer/`,
  plus the `render_interactive` fixture pattern adopted by
  ADR-0008.
- [SlicerHyperProbe](https://github.com/MESH-Lab/SlicerHyperProbe)
  — in-project precedent for the data-only-display-node + Python-
  Pipeline split.  See `vtkMRMLHyperprobeViewDisplayNode` +
  `vtkMRMLHyperprobeViewPipeline`.
- Related ADRs:
  - [ADR-0002](0002-migrate-to-slicerlayerdm.md) — the migration
    target this ADR fixes the shape of.
  - [ADR-0004](0004-python-cpp-boundary.md) — the language
    boundary that puts Pipelines in Python and data-only display
    nodes in C++.
  - [ADR-0008](0008-testing-strategy.md) — the three-layer test
    discipline this ADR applies to every Pipeline and
    Representation; T2 delivers the deferred real-view fixture.
  - [ADR-0009](0009-ux-and-design-discipline.md) — UI diagrams
    under `Docs/architecture/ui/<module>.md` and combo-box
    elimination, both downstream of this pattern.
  - [ADR-0011](0011-sct-terminology-dispatch.md) — SCT dispatch
    is where the Pipeline reads the terminology ref off the
    display node and decorates from the triple.
  - [ADR-0012](0012-layerdm-migration-v2-scope.md) — the v2.0.0
    scope this pattern is the implementation shape of.
- Current-state UI baselines: `Docs/architecture/ui/liver-
  resections.md`, `Docs/architecture/ui/liver-segments.md`,
  `Docs/architecture/ui/liver-volumetry.md` (landed in PR #317).

---

*This ADR was drafted with AI assistance (Claude) against the
project's ADR template and the existing 0001–0012 ledger; the
decisions, alternatives, and consequences were reviewed and
adopted by the named decider.  Same authorship convention as
PRs #304, #315, #317, #318.*

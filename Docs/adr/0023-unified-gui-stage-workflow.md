# 0023. Unified GUI — six-stage surgeon workflow

- **Status:** Accepted
- **Date:** 2026-05-21
- **Deciders:** R. Palomar
- **Diagrams:** [`Docs/architecture/gui-stage-flow.md`](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/architecture/gui-stage-flow.md), [`Docs/architecture/territories-class-hierarchy.md`](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/architecture/territories-class-hierarchy.md)
- **PR:** <filled on merge>

## Amendments

- **2026-05-25 — Wrapper-vs-carrier pattern; `.lrp.json` content
  roster trim; territories interface tightening.**  The post-PR #430
  design review introduced the wrapper-vs-carrier pattern (see
  [ADR-0014](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0014-livermarkups-dissolution.md) amendment of the
  same date).  This amendment applies the pattern across §"Class
  abstraction for territories", §"Persistence — `.lrp.json` schema
  v2", and §"Cross-stage dependencies"; supersedes the affected
  paragraphs as follows.

  ### §"Class abstraction for territories" — polymorphic interface
  tightening

  The polymorphic interface tightens to drop the
  `GetLabelMap()` / `GetSegmentationNode()` duality.  Per [ADR-0024](0024-segmentation-orchestration.md)
  §"Output contract", Stage 2 publishes one canonical
  `vtkMRMLSegmentationNode`; the v2.0 territories nodes wrap it via
  a new typed `segments` node-reference role, not their own
  internal labelmap.  Resulting interface:

  ```
  vtkMRMLAbstractTerritoriesNode (abstract, wrapper)
    +virtual GetMethod() : string
    +virtual GetSegments() : vtkStringArray
    +virtual GetSegmentColor(int) : double[3]
    +virtual GetSCTCode(int) : string
    // node refs
    segments → vtkMRMLSegmentationNode  (Slicer-core carrier)
  ```

  `GetLabelMap()` is **dropped** from the interface (callers that
  need a binary labelmap representation reach through
  `GetSegmentationNode()->GetBinaryLabelmapRepresentation(...)`,
  the Slicer-core path).  The `LabelMap` field on
  `vtkMRMLStdCouinaudTerritoriesNode` and
  `vtkMRMLCustomTerritoriesNode` is **dropped** for the same reason.

  Auto-path inputs (`SourceImageRef`, `AIBackendIdentifier`,
  `Subdivision`, `ComputedAt`) and Manual-path inputs
  (`CenterlineRefs`, `EndpointRefs`, `Groupings`, `SegmentNames`)
  stay on the respective concrete subclass.  They are
  *method-specific inputs*, not segment-mask data, and belong on
  the wrapper.

  ### §"Class abstraction for surfaces" (NEW)

  The same wrapper-vs-carrier pattern lands on the resection-surface
  side.  `vtkMRMLResectionPlanNode` is the **clinical wrapper**
  carrying surgeon-facing fields (name, Safety + Risk margins,
  surgical-list ordering, plan state).  The carrier is a new
  abstract data hierarchy that admits Bezier today and NURBS in
  v2.1 ([ADR-0018](0018-nurbs-extension-surface.md)):

  ```
  vtkMRMLAbstractParametricSurfaceNode (abstract, carrier base)
    +unsigned int Rows, Cols
    +double[3 * Rows * Cols] ControlGrid
    +InitMode : SlicingPlane | DistanceSpheroid
    +SlicingPlane subordinate (origin, normal, init points)
    +DistanceSpheroid subordinate (center, radii, init points)
    +virtual GetSurfaceType() : string ("Bezier" | "NURBS")
    +virtual EvaluateSurface(u, v) : vtkPolyData
    // node refs
    TargetOrganModelNodeID
    ↑ inherits
    vtkMRMLBezierSurfaceNode (v2.0, concrete)
    vtkMRMLNurbsSurfaceNode  (v2.1, concrete sibling)
  ```

  Display side stays **flat**: both concrete subclasses reference a
  single shared `vtkMRMLParametricSurfaceDisplayNode` (no abstract
  display base, no per-surface-type display subclass), mirroring the
  Slicer-core `vtkMRMLMarkupsDisplayNode` pattern that serves 8+
  markup data subclasses.

  ### §"Persistence — `.lrp.json` schema v2" — content roster trim

  The original v2 roster carried both plan-level and scene-level
  state in one file.  The 2026-05-25 review separates these: a
  `.lrp.json` carries **plan + its surface only**.  Three scene-level
  entries that the original roster listed are **removed**:

  | Removed from `.lrp.json` | New persistence path |
  |---|---|
  | Classification node reference | Scene-level state; `vtkMRMLAbstractTerritoriesNode` persists via standard MRML.  No reference from any plan |
  | Volumetry partition node references | Scene-level state; `vtkMRMLLiverVolumetryPartitionNode` (v2.1) persists via its own MRML mechanism |
  | Per-stage last-selection | UI state on a scene-singleton (Liver-shell parameter node) |

  Replacement v2 content roster (now plan-rooted, surface-block-
  polymorphic):

  - Plan fields at JSON root: `name`, `safetyMargin_mm`,
    `riskMargin_mm`, `orderIndex`, `state`, `schemaVersion: 2`.
  - `surface: { type: "Bezier" | "NURBS", rows, cols, controlGrid,
    initMode, slicingPlane, distanceSpheroid, …NURBS-only fields when
    type=NURBS }`.
  - `metadata: {}` (reserved for future).

  The reader still admits the old `scene.*` block silently (unknown
  fields ignored) so any test fixture or preview-tracking file
  loads cleanly.  The writer never emits the old `scene.*` block.

  Cross-machine plan transfer (#415) becomes trivially correct: a
  `.lrp.json` carries no scene-node-ID references after this trim.
  The v2.1+ stable-ID resolution scope shrinks from "transfer plans
  + maintain ID stability for classification/partitions" to
  "transfer plans alone."

  ### §"Cross-stage dependencies" — Plan ↔ Territories explicit
  non-reference

  Add the row to the dependency map's narrative: **plans do not
  reference territories or volumetry partitions or stage state**.
  Visual co-existence in the surgeon's view is the only coupling;
  no typed node reference links them.  Multiple plans coexist with
  the same active classification; switching the active
  classification leaves all plans unchanged on disk.

  ### §"Decision" — surface-side data ownership

  `vtkMRMLAbstractParametricSurfaceNode` is **non-storable**
  (`CreateDefaultStorageNode()` returns `nullptr`).  Surface bulk
  data persists through the plan's `vtkMRMLResectionPlanStorageNode`,
  which walks the plan's `geometry` ref on write and reconstructs
  it on read.  This mirrors the Slicer-core Segmentations pattern
  (segments inside a segmentation file rather than per-segment
  storage) and the Markups pattern (control points inside the
  markups file rather than per-point storage).

- **2026-06-08 — User-verified phase contracts deferred to v2.1;
  v2.0 ships advisory indicators only.**  During T5.2-d shell
  implementation a third gating model surfaced: each stage exposes a
  *contract* the surgeon explicitly **verifies** (a human attestation,
  not an automated threshold), and verification **unlocks the
  relevant downstream stages** along the §"Cross-stage dependencies"
  map.  Tabs carry a pass indicator once their contract is fulfilled.

  This is **deferred to v2.1**; v2.0 keeps the advisory
  `✓ / ● / ○` indicators decided in §"Shell composition (Option H)"
  (non-blocking, computed from each stage's `isStageComplete()`
  predicate).  The deferral is recorded here so the idea is not lost
  and so the v2.0 indicator substrate is understood as
  forward-compatible groundwork, not a finished feature.

  ### Why a distinct alternative, not Alternative B or E

  The idea is neither rejected alternative, and must not be conflated
  with them:

  - **Not Alternative B (strict linear wizard).**  B hard-disables
    non-current stages and forces 1→6 order.  This model proposes
    **soft gating**: downstream stages stay reachable (freeform
    navigation, the §"Alternative B" rationale, is preserved) but an
    unverified upstream contract surfaces a warning rather than a
    hard lock.
  - **Not Alternative E (verification card).**  E was rejected because
    *automated* clinical thresholds (remnant % vs threshold, margin
    pass/fail) imply surgical-planning-tool-grade positioning that
    Slicer-Liver does not claim (ADR-0009 IEC 62366 relaxation).  This
    model records a **human** attestation — the surgeon asserts the
    stage is acceptable — making no automated clinical claim.  Whether
    that distinction is sufficient to stay research-tool-grade, or
    whether *any* gating signal re-opens the IEC 62366 positioning
    question, is the central open question for the v2.1 ADR.

  ### Open questions the v2.1 ADR must resolve

  1. **Invalidation / staleness.**  If an upstream stage's data
     changes after its contract was verified, the downstream pass
     state must invalidate — a stale ✓ in a planning tool is worse
     than none.  Requires dependency tracking + MRML observers on the
     actual data, with a re-lock cascade; not just a persisted flag.
  2. **Optional-stage DAG.**  "Not all stages are mandatory" (e.g.
     Stage 3 Auto skips Stage 2 per §"Cross-stage dependencies").  The
     unlock graph must encode skip paths; a wrong edge locks users out
     of a valid workflow.
  3. **Positioning.**  Does human attestation avoid the tool-grade
     repositioning that killed Alternative E, or not?  (ADR-0009.)
  4. **Verification fatigue.**  A per-stage sign-off that becomes a
     rubber-stamp reflex defeats its own safety purpose.
  5. **Persistence + discoverability.**  Where the verified state
     lives (the §"Persistence — `.lrp.json` schema v2" per-stage
     block is the natural home) and how a not-yet-unlocked stage
     explains itself to the surgeon.

  Tracked as [issue #440](https://github.com/ALive-research/Slicer-Liver/issues/440).
  Supersedes nothing in v2.0; the §"What is NOT in v2.0"
  *Verification card* bullet stands.

- **2026-06-09 — Subject Hierarchy management convention.**  The
  §"MRML scene organisation" paragraph commits Slicer-Liver to grouping
  its node types under per-stage Subject-Hierarchy folders, but left the
  *mechanism* implicit — each module open-coded its own
  lookup / lazy-create / reparent dance.  This amendment makes the
  convention explicit and names the shared utility that implements it.

  ### §"Subject Hierarchy management convention" (NEW)

  **Closed four-folder vocabulary.**  Slicer-Liver places its
  programmatically-created nodes under exactly four scene-root
  Subject-Hierarchy folders, one per node-creating stage (Stages 2–5):

  | Stage | Folder name            | Node-creating module  |
  | ----- | ---------------------- | --------------------- |
  | 2     | `Anatomy`              | LiverSegmentation     |
  | 3     | `Vascular Territories` | VascularTerritories   |
  | 4     | `Resections`           | LiverResections       |
  | 5     | `Volumetry`            | LiverVolumetry        |

  The vocabulary is **closed**: the four strings above are the only
  per-stage folder names, mirroring the closed-keyword discipline the
  project applies elsewhere.  Each folder is a **direct child of the
  scene root** (a per-stage folder, not nested in a Patient/Study/Series
  subtree), **created lazily** on the first node's arrival, and **reused**
  thereafter — never one-folder-per-call.

  **Folder names as named constants — single source of truth.**  The
  four strings live in one place: the accessors
  `GetAnatomyFolderName()`, `GetVascularTerritoriesFolderName()`,
  `GetResectionsFolderName()`, `GetVolumetryFolderName()` on the shared
  utility.  Consumers reference the accessors, never string literals, so
  the modules cannot drift apart.

  **Shared utility — `vtkSlicerSubjectHierarchyFolders`.**  A standalone
  wrapped kit `SubjectHierarchyFolders/` centralises the placement logic
  behind one static method:

  ```
  static bool CollectUnderFolder(vtkMRMLScene* scene,
                                 vtkMRMLNode* node,
                                 const char* folderName);
  ```

  It links MRMLCore only (the Subject-Hierarchy node + plugin machinery
  lives there, reachable from a plain `vtkMRMLScene` — no Qt, no
  module-Logic dependency, honouring the
  [ADR-0003](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0003-testability-invariant.md)
  testability invariant and the
  [ADR-0008](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0008-testing-strategy.md)
  §2 "C++ low-level" row).  The kit name carries **no `Liver` prefix**,
  per the closed-vocabulary class-naming convention (the T2.7 rename
  family that dropped the prefix from the Bezier and resection node
  families).  It is a pure `vtkObject` utility, **not** a `vtkMRMLNode`
  subclass.

  **Node placement convention.**  `CollectUnderFolder` is:

  - *Idempotent* — a second call with the same folder name reuses the
    one existing scene-root folder.
  - *Headless-safe* — when the scene has no resolvable Subject-Hierarchy
    node (a missing SH plugin in a headless context) it is a no-op
    returning `false`, so it never breaks the caller's node creation and
    never mints SH machinery behind the caller's back.
  - *Null-argument-safe* — null scene / node / folder name return
    `false` cleanly.

  **Wrapper-only collection.**  Where a stage uses the wrapper-vs-carrier
  split (the 2026-05-25 amendment;
  [ADR-0014](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0014-livermarkups-dissolution.md)),
  only the surgeon-facing **wrapper** node is collected.  The hidden
  `SetHideFromEditors(true)` carriers (e.g. the Bezier/contour carriers
  behind a `vtkMRMLLiverResectionNode`) are deliberately left
  unparented, so the surgeon-facing Subject Hierarchy mirrors the
  editor-visible node set.

  ### ADR-0004 reasoned exception — wrapped C++, not Python-by-default

  [ADR-0004](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0004-python-cpp-boundary.md)
  makes Python the default for orchestration glue.  This utility is a
  **reasoned exception**: it is wrapped C++ because only a wrapped C++
  implementation gives *both* the C++ callers (the VascularTerritories
  and LiverResections module logics, which fire from
  `OnMRMLSceneNodeAdded` in C++) *and* the Python caller
  (LiverSegmentation's `_collectUnderAnatomyFolder`) **one
  binary-identical implementation**.  A Python helper would be
  unreachable from C++, forcing either a second C++ copy (drift risk —
  exactly what this convention exists to prevent) or a C++→Python
  round-trip from inside a scene observer (fragile).  The kit is wrapped
  (`vtkSlicerSubjectHierarchyFoldersPython`) so the Python caller imports
  the same compiled method the C++ callers link.

  **Scope.**  Three active consumers wired now: LiverSegmentation
  (`Anatomy`), VascularTerritories (`Vascular Territories`),
  LiverResections (`Resections`).  LiverVolumetry (`Volumetry`) adoption
  is deferred — it creates no nodes today; the folder name + accessor
  exist so the convention is complete when Stage 5 starts minting nodes.

  ### §Conformance additions

  - [test] The four folder-name accessors on
    `vtkSlicerSubjectHierarchyFolders` return `Anatomy`,
    `Vascular Territories`, `Resections`, `Volumetry` verbatim.
    (`vtkSlicerSubjectHierarchyFoldersTest1` — folder-name constants.)
  - [test] `CollectUnderFolder` places a node under a scene-root folder
    of the given name, lazily created and reused on a second call
    (one folder, not two).
    (`vtkSlicerSubjectHierarchyFoldersTest1` — placement + reuse.)
  - [test] `CollectUnderFolder` returns `false` with no side effect on
    null scene / node / folder name.
    (`vtkSlicerSubjectHierarchyFoldersTest1` — null-argument safety.)
  - [test] The VascularTerritories logic collects territory nodes under
    `Vascular Territories` observably-identically before and after the
    rewrite to the shared utility.
    (`vtkSlicerVascularTerritoriesLogicSubjectHierarchyCharacterizationTest`
    — the equivalence oracle.)
  - [test] The LiverResections wrapper `vtkMRMLLiverResectionNode` lands
    under `Resections`; the hidden Bezier carrier does not.
    (`test_resections_subject_hierarchy_collection.py`, launched-Slicer.)
  - [test] The wrapped `vtkSlicerSubjectHierarchyFolders` is importable +
    callable from Python and Anatomy placement is idempotent through it.
    (`test_liversegmentation_subject_hierarchy_folders_reachability.py`,
    launched-Slicer.)
  - [review] Consumers reference the folder-name accessors, never string
    literals; no module open-codes the lookup / lazy-create / reparent
    dance after wiring.
  - [future] LiverVolumetry adoption (`Volumetry`) lands when Stage 5
    begins creating nodes; until then the accessor exists but no consumer
    calls it.

## Context

Slicer-Liver v2.0.0 was re-scoped on 2026-05-21 from a foundation-only
release (LayerDM migration + style + CI infrastructure) to a user-facing
major leap. The maintainer's framing: *"the v1→v2 transition is the
natural place to introduce user-visible UX change; spreading UX leaps
across v2.0→v2.1 minors understates the version jump from the surgeon's
standpoint."* This is a scheduling discipline, not a versioning-policy
amendment to [ADR-0007](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0007-version-numbering-policy.md) — backend-only
majors remain legitimate.

ADR-0009 commits per-PR UX discipline (Mermaid state-machine diagrams +
design rationale) but does not specify an extension-wide *target design
shape*. ADR-0012 explicitly defers LayerDM migration of `LiverSegments`,
`LiverVolumetry`, and `Modeling` to v2.1.0 — but the surgeon still sees
these modules in v2.0, so their v2.0 UI shape matters.

The current `Liver` scripted module (`Liver/Liver.py` L194–231) is a *de
facto* unified shell: it embeds `DistanceMapsWidget`, `ResectionsWidget`,
`ResectogramWidget`, `LiverSegmentsWidget`, and `LiverVolumetryWidget` in
one vertical layout. Each child module is also independently selectable
via Slicer's module browser. The hidden problem: there is no
*navigation* surface in the shell. Surgeons see a long scroll without a
sense of workflow progression. There is also no extension-wide design
language, so per-module UI evolves without a shared target.

Module names changed during the v2.0 scope discussion: existing
`LiverSegments/` (Couinaud-territory module) is renamed to
`VascularTerritories/`; a new `LiverSegmentation/` module hosts
TotalSegmentator + Kumar-Oram orchestration. `Modeling/`
is dropped as a top-level module — Poisson Surface Reconstruction (PSR)
ships as a Superbuild external project exposed to Python.

Clinical positioning: Slicer-Liver remains a *research-grade
clinical-adjacent extension* (per the 2026-05-14 design discussion and
ADR-0009 §"Medical-device alignment for reference"). v2.0 does **not**
ship a clinical verification gate. Surgeon clinical training and
judgement provide the go/no-go signal; the extension surfaces the data
the surgeon needs to make that judgement.

## Decision

Slicer-Liver v2.0.0 ships a **six-stage surgeon workflow** with a
**unified shell hosting a vertical sidebar** for stage navigation. The
six stages are:

1. **Case Setup** — load DICOM and non-DICOM volumes; assign per-volume role tags (Portal venous, Arterial, Native, Delayed, Other); optional inter-phase registration; arrange the canonical Slicer layout.
2. **Anatomy Definition** (`LiverSegmentation/` — new module) — segment liver, portal vein, hepatic vein, and tumors using per-structure micro-workflows that orchestrate TotalSegmentator + Kumar-Oram (vessels, hosted as a Segment Editor effect per [ADR-0026](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0026-segment-editor-effects.md)) + Segment Editor for manual fixes; scratch-and-accept pattern produces a single canonical Segmentation node. See [ADR-0024](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0024-segmentation-orchestration.md) for the full Stage 2 contract.
3. **Vascular Territories** (`VascularTerritories/` — renamed from `LiverSegments/`) — two-tab structure: *Couinaud (automatic)* one-shot AI compute, and *Custom segments* flexible builder.
4. **Resection Planning** (`LiverResections/`) — resection table with per-row state machine (Init → Planning → Confirmed per [ADR-0019](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0019-resection-state-machine.md)); active-resection detail panel; classification overlay; resectogram view invoked from per-resection detail.
5. **Volumetry** (`LiverVolumetry/`) — flexible seed-and-category partition workbench consuming Confirmed resections as barriers; pure analytical tool, no verification card.
6. **Export** — `.lrp.json` sidecar save via the existing storage node ([T2.5](https://github.com/ALive-research/Slicer-Liver/pull/361)) plus delegation to Slicer's stock `File ▸ Save Data` and `ScreenCapture`. Implemented as a section under the Liver shell, not a separate module.

### Shell composition (Option H)

`Liver/` retains its role as the canonical unified shell. Its widget hosts a vertical sidebar (likely `QToolBox` or a custom `QListWidget`-driven stack) showing all six stages with per-stage state indicators (✓ done / ● current / ○ pending). Clicking a stage entry switches the right-hand content panel to that stage's module widget.

Each per-stage module remains **independently selectable** via Slicer's module browser. Surgeons default to the unified shell; power users and researchers can pick a single module standalone. The Liver shell holds no domain logic — only composition + navigation.

### Class abstraction for territories

Stage 3's Auto and Manual tabs produce genuinely different data models — AI inference produces a labelmap directly; manual labelling produces centerlines (VMTK-extracted from endpoints) grouped into segments. They are unified at the **node-type level**, not the data-model level:

```
vtkMRMLAbstractTerritoriesNode   (abstract base)
  ├── vtkMRMLStdCouinaudTerritoriesNode   (Auto-tab path)
  └── vtkMRMLCustomTerritoriesNode        (Manual-tab path)
```

The abstract base exposes a polymorphic interface (`GetSegments()`, `GetSegmentColor(int)`, `GetLabelMap()`, `GetSegmentationNode()`, `GetMethod()`, `GetSCTCode(int)` — VTK uppercase-Get convention; see [`Docs/architecture/territories-class-hierarchy.md`](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/architecture/territories-class-hierarchy.md) for the full signature). Downstream consumers (Stage 4 classification overlay, Stage 5 volumetry analysis) consume the base class without caring which subtype. Both subtypes coexist in the scene; surgeon switches the active one via Slicer's `qMRMLNodeComboBox`.

The earlier 2026-05-15 volumetry-framework note's claim that "the current resection behaviour is a degenerate case of the framework" is **retracted**. Stage 3 (territories) and Stage 5 (volumetry-partition) are two distinct surgeon-facing problems with two distinct data models. They may share a compute kernel (Fast Marching with sampled seeds) but not a node-level abstraction. The PKS note will be amended.

### Cross-cutting UI conventions

- **`qMRMLNodeComboBox` is the binding primitive** for every node-management surface (classifications, volumetry partitions, etc.). Slicer-native; provides create/select/rename/delete for free.
- **Hierarchical table + master-detail endpoints sub-table** for Stage 3 Manual (groupings → centerlines → endpoints). Reuses `qMRMLMarkupsControlPointTableWidget` from Slicer-core for the endpoints panel.
- **`ctkCollapsibleButton`-organised module widgets**, compact density (Slicer-native), no parallel palette/theme (per [ADR-0010](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0010-accessibility-and-i18n.md)).
- **No custom Slicer layouts** in v2.0 except the resectogram view (registered by `LiverResections/`, invoked from Stage 4).

### Cross-stage dependencies

| Stage | Depends on |
|-------|------------|
| 1     | (nothing) |
| 2     | Stage 1 (a tagged input volume) |
| 3 Auto | Stage 1 only — needs the image with Portal-venous role |
| 3 Manual | Stage 2 — needs vessel segmentation for VMTK ExtractCenterline |
| 4     | Stage 1; classification overlay optional from Stage 3 |
| 5     | Stage 4 (Confirmed resections as barriers); classification optional from Stage 3 |
| 6     | (nothing — exports current scene state) |

The sidebar's per-stage state indicators reflect this dependency map: a stage is "available" when its prerequisites are met. A surgeon taking the Stage 3 Auto path can skip Stage 2's vessel segmentation entirely.

### AI extension dependencies — lazy install

`SlicerLayerDM` (already required per [PR #368](https://github.com/ALive-research/Slicer-Liver/pull/368)) and `SlicerVMTK` (required for centerline extraction in Stage 3 Manual) stay as hard `EXTENSION_DEPENDS`.

`TotalSegmentator` is **not** declared as `EXTENSION_DEPENDS` and is **not** in the Superbuild. It installs lazily via `slicer.util.pip_install(...)` on first surgeon invocation of an AI-driven feature. First-use prompt shows the download size and asks for confirmation. Settings panel under the Liver shell exposes pre-download and re-install affordances for surgeons going offline.

The lazy-pip-install pattern is **only viable for AI tools that consume as a Python package with no external runtime**. Tools that require a separately-running server process — for example MONAILabel, whose Slicer-side widget is a client of a separately-installed MONAILabel server (local Docker, native install, or remote) — cannot follow this pattern. Such tools are out of v2.0 scope. See [ADR-0024](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0024-segmentation-orchestration.md) Alternative H for the MONAILabel-DeepGrow drop + three v2.1+ paths (server-less DeepGrow via pip-`monai`, custom Segment Editor effect per [ADR-0026](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0026-segment-editor-effects.md), or Slicer-stock interactive tools).

Slicer-Liver consumes TotalSegmentator's Python API directly — it does not require the upstream TotalSegmentator *Slicer extension wrapper* to be installed. Surgeon interacts via Slicer-Liver's UI, not via the upstream extension's widget.

### Persistence — `.lrp.json` schema v2

The `.lrp.json` storage (introduced in [PR #361](https://github.com/ALive-research/Slicer-Liver/pull/361), extended for variable-size Bezier in [PR #383](https://github.com/ALive-research/Slicer-Liver/pull/383)) lands a unified schema v2 for the 2026 v2.0.0 release. v1 was preview-only and is not part of the released contract; the reader rejects it. v2 captures v2.0's surgeon-facing state:

- Per-resection name + Safety + Risk margin values.
- Resection list ordering (the surgical-order + locator-precedence semantic).
- Classification node reference (the active `vtkMRMLAbstractTerritoriesNode` per stage's binding).
- Volumetry partition node references (Stage 5 partitions, multiple per scene supported).
- Per-stage last-selection (so reload returns surgeon to where they left off).

References are **scene-local node IDs**. v2.0 supports the *sidecar use case* only — one scene, one `.lrp.json`. Cross-machine plan transfer (atlas-matching, stable-ID resolution) is out of scope; deferred to v2.1+ if a use case emerges.

### MRML scene organisation

Slicer-Liver programmatically manages `vtkMRMLSubjectHierarchyNode` to group its many node types under per-stage folders ("Anatomy", "Vascular Territories", "Resections", "Volumetry"). Node names follow the convention `<Concept>: <Name>` (e.g., `Resection: Right hemihepatectomy`, `Centerline: P2-main`, `Auto Couinaud (2026-05-21)`). Both folder structure and naming conventions are wired by the module logic at node-creation time.

### Distance maps

Distance maps remain **auto-triggered background infrastructure** on Stage 4 entry. The 2026-05-14 commitment to a "manual recompute" UI is honoured via a small `[Recompute]` button in a Stage 4 "Distance maps" section. UI elements that depend on the distance maps (margin shader visualisation on the resection surface, tumor-margin numeric readouts) disable when no maps exist; a status banner directs surgeon to compute.

### What is NOT in v2.0

Several recurring themes are explicitly out-of-scope for v2.0 and tracked for later:

- **Verification card** — no automated go/no-go signal. Slicer-Liver is research-tool-grade. Promoting v2.0+1 to surgical-planning-tool-grade is a future repositioning decision.
- **Multi-classification synchronisation across stages** — Stage 3 / Stage 4 / Stage 5 each carry their own `qMRMLNodeComboBox` binding. Surgeon can have different classifications visible across stages simultaneously. Documented as intentional.
- **Custom palette / theme / icon family** — per ADR-0010.
- **Topology-based vessel auto-classifier** — Stage 3 Auto is AI-only in v2.0; topology-derived clinical labelling is v2.1+.
- **Per-vessel-branch identification** in Stage 5's vessels-cut summary — counts only in v2.0.
- **Cross-machine `.lrp.json` transfer** — sidecar-only for v2.0.
- **Resectogram comparison view** across multiple plans — v2.1+.
- **Atlas matching, comparative analysis, longitudinal review** — research-grade features beyond v2.0.

## Alternatives considered

### Alternative A — Per-module panels with shared design language

Each `Liver*` module retains its own top-level entry in Slicer's module browser; no unified shell. ADR commits a *design grammar* (spacing scale, section ordering, status affordances, icon family) that every module follows.

**Rejected because** it hides the workflow narrative — surgeon perceives five disconnected modules, not one product. Cross-module state needs explicit MRML observer wiring (already partially present, but fragile). The "unified UX leap" promise is partly rhetorical without a shell.

### Alternative B — Strict linear wizard

The Liver shell forces surgeons through Stages 1 → 6 in order, with "Next" / "Previous" buttons, non-current stages hidden or disabled. Mirrors the cleanest surgical-planning workflow tool conventions.

**Rejected because** Slicer's surgeon-researcher user base needs freeform navigation. Researchers may invoke Stage 5 standalone for retrospective volumetry; surgeons revising a plan iterate 3↔4↔5 nonlinearly. The sidebar with state indicators preserves both visibility and freedom of movement.

### Alternative C — Tab bar across the top

Six horizontal tabs at the top of the Liver shell, only the active tab's content visible. Slicer-native via `QTabWidget`.

**Rejected because** horizontal tabs lose progress indication (the state ✓/●/○ glyphs are harder to scan on a horizontal strip than a vertical list). Six labels also fit awkwardly in Slicer's left-panel width. The vertical sidebar reads as a workflow checklist; the tab bar reads as parallel views.

### Alternative D — One-shell-no-modules

Dissolve `LiverSegmentation/`, `VascularTerritories/`, `LiverResections/`, `LiverVolumetry/` as independently-selectable modules; only the `Liver` shell module appears in Slicer's browser.

**Rejected because** it forces surgeons through the shell for tasks that may be more naturally invoked standalone (e.g., a researcher computing Couinaud on a dataset without planning any resection). Per [ADR-0007](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0007-version-numbering-policy.md), removing an independently-selectable module is a MAJOR-version-breaking compatibility surface change — already triggered by the v1→v2 jump on other surfaces, but adds an unnecessary one.

### Alternative E — Verification card retained in Stage 5

Re-introduces a "Verification" card surfacing remnant % vs threshold, tumor margins pass/fail, vessels cut count, and a "Continue to Export" gate with confirm-on-fail.

**Rejected because** automated clinical thresholds imply surgical-planning-tool-grade positioning, which Slicer-Liver does not claim per ADR-0009's IEC 62366 relaxation. A half-baked verification card would over-promise. Re-promotion in v2.0+1 is on the table if the project's clinical positioning shifts.

### Alternative F — Class abstraction unified at the framework level

Force Stage 3 Auto and Manual to share the framework's `vtkMRMLLiverVolumetryNode` data model (fiducial seeds per category). Auto path's labelmap is back-converted into "synthetic" fiducial seeds; Manual path uses fiducials directly.

**Rejected because** Auto's output is a learned labelmap with no anatomical correspondence to portal-branch centerlines; pretending it is the same data is misleading and lossy. The class abstraction (`vtkMRMLAbstractTerritoriesNode` base + two subclasses) is the honest architecture.

## Consequences

### What becomes easier

- Surgeons see a coherent workflow narrative with visible progression.
- Cross-module state is implicit in the stage flow rather than emergent.
- Downstream consumers (Stage 4 overlay, Stage 5 analysis) use polymorphism — no `if territoriesMethod == "..."` branching.
- AI backend churn doesn't force re-installs of Slicer-Liver — lazy `pip_install` lets the extension and its AI deps version independently.
- `.lrp.json` becomes a meaningful per-case sidecar capturing the surgeon's actual workflow state.
- Subject Hierarchy under the surgeon's Data module becomes navigable and self-documenting.

### What becomes harder

- The Liver shell now owns a non-trivial navigation widget — implementation cost.
- Per-stage state-indicator logic must compute correctness (e.g., "has Stage 2 produced a canonical Segmentation?"). Each module exposes a `isComplete()`-like query for the sidebar.
- Two `vtkMRMLAbstractTerritoriesNode` subclasses + a base imply C++ MRML node hierarchy work (per [ADR-0004](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0004-python-cpp-boundary.md) — data nodes are C++).
- `.lrp.json` schema v2 carries the surgeon-facing state in a `resection` block + a scene-wide `scene` block; reader rejects v1 (preview-only, not part of the released contract).
- Subject Hierarchy management code must be wired across every node-creating module — a per-module discipline gate.
- The resectogram custom layout registration is a new mechanism in `LiverResections/`.

### Follow-on work

- **Architecture diagrams** in `Docs/architecture/` — stage flow + dependency map, territories class hierarchy, MRML node landscape.
- **ADR-0024 — Segmentation orchestration** for Stage 2's per-structure micro-workflows (TotalSegmentator + Kumar-Oram Segment Editor effect + Segment Editor manual orchestration). Interactive tumor refinement (e.g., MONAILabel-DeepGrow) is deferred to v2.1+ per ADR-0024 Alternative H.
- **ADR-0025 — Locator architecture** for the resectogram hover→3D + click→reslice interactions, the 1:1 (u,v) mapping insight, and the v2.0/v2.1 scope split.
- **Schema v2 unified surgeon-state** PR for `vtkMRMLBezierSurfaceStorageNode` (`.lrp.json`).
- **Class refactor** PRs for `vtkMRMLAbstractTerritoriesNode` + subclasses + Stage 3 Auto and Manual tab rewiring.
- **`LiverSegments/` → `VascularTerritories/` rename** + content refactor into the framework.
- **`LiverSegmentation/` new module** + lazy-install machinery for TotalSegmentator.
- **Sidebar widget** implementation in `Liver/`.
- **Subject Hierarchy wiring** across every module's node-creation paths.
- **PKS amendments**: walk back the 2026-05-15 framework note's "degenerate case" claim; walk back the 2026-05-14 stitch note's Couinaud-from-Portal-commit auto-trigger.

## Conformance

Reviewable invariants that signal this decision is honoured:

- `Liver/Liver.py` exposes a sidebar widget with six entries matching the six stages.
- `Liver/Liver.py` contains no domain logic — only composition and navigation. Grep: `Liver/Liver.py` should not import any algorithm or compute helpers.
- `vtkMRMLAbstractTerritoriesNode` exists as a C++ base class in `VascularTerritories/MRML/` (or equivalent). Subclasses `vtkMRMLStdCouinaudTerritoriesNode` and `vtkMRMLCustomTerritoriesNode` register via `RegisterNodeClass`.
- `qSlicerLiverResections` Stage 4 detail panel surfaces an `[Open resectogram view]` action per active resection.
- `LiverResections/` registers a custom Slicer layout for the resectogram view.
- The sidebar's per-stage state indicators are driven by a per-stage `isComplete()` query (or equivalent) defined by each stage's module.
- No new module declares `TotalSegmentator` or `MONAILabel` as `EXTENSION_DEPENDS`. The first-use install path is implemented in `LiverSegmentation/Logic/` (and any other AI-consuming module).
- `.lrp.json` schema header reads `"schemaVersion": 2` on writes; reader rejects v1 outright and tolerates absent surgeon-state blocks within v2 via documented defaults.
- Subject Hierarchy folder names "Anatomy", "Vascular Territories", "Resections", "Volumetry" exist after typical workflow use. Grep for `SubjectHierarchyCreateFolder` (or upstream equivalent) in each module's logic.
- The 2026-05-14 stitch and 2026-05-15 framework PKS notes carry "Superseded by ADR-0023" annotations on the relevant claims.

## References

- [ADR-0007 — Version numbering policy](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0007-version-numbering-policy.md). v2.0 is feature-driven, no calendar floor. UX-grouping is scheduling discipline, not a versioning amendment.
- [ADR-0009 — UX and design discipline](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0009-ux-and-design-discipline.md). Per-PR Mermaid + design rationale stays in force; this ADR adds the extension-wide target shape.
- [ADR-0010 — Accessibility and i18n](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0010-accessibility-and-i18n.md). No parallel palette/theme; align with Slicer + contribute upstream.
- [ADR-0011 — SCT terminology dispatch](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0011-sct-terminology-dispatch.md). Per-tool LabelToSCT.json bridges remain the dispatch alphabet. §3 path examples were amended in PR #406 (this ADR's landing PR) to reflect the actual `Resources/Terminology/LabelToSCT/` location.
- [ADR-0012 — LayerDM migration v2.0 scope](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0012-layerdm-migration-v2-scope.md). LiverSegments / LiverVolumetry / Modeling LayerDM migration remains deferred to v2.1.0.
- [ADR-0013 — LayerDM Pipeline pattern](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0013-layerdm-pipeline-pattern.md). Stage 4's resection surfaces and the resectogram each have their own Pipelines.
- [ADR-0014 — LiverMarkups dissolution](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0014-livermarkups-dissolution.md). LiverMarkups module is removed; Bezier-surface widget lives in `LiverResections/`.
- [ADR-0019 — Resection state machine](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0019-resection-state-machine.md). Stage 4's Init → Planning → Confirmed per resection.
- Tracker [issue #305](https://github.com/ALive-research/Slicer-Liver/issues/305) — v2.0.0 release tracker, scope-expansion section.
- The maintainer's design conversation 2026-05-21 (stage-by-stage walkthrough + grilling pass) — captured in the PKS project log [[denote:20260507T130427]].
- The forthcoming **ADR-0024** (Segmentation Orchestration) and **ADR-0025** (Locator Architecture) cover Stage 2 and the resectogram hover/click interactions respectively.

---

*AI-assisted authorship: this ADR was drafted with help from Anthropic's Claude (Opus 4.7, `claude-opus-4-7`) via Claude Code, under the maintainer's iterative design walkthrough + grilling pass.*

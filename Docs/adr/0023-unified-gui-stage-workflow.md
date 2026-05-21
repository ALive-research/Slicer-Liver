# 0023. Unified GUI — six-stage surgeon workflow

- **Status:** Proposed
- **Date:** 2026-05-21
- **Deciders:** R. Palomar
- **Diagrams:** `Docs/architecture/gui-stage-flow.md` (forthcoming), `Docs/architecture/territories-class-hierarchy.md` (forthcoming)
- **PR:** <filled on merge>

## Context

Slicer-Liver v2.0.0 was re-scoped on 2026-05-21 from a foundation-only
release (LayerDM migration + style + CI infrastructure) to a user-facing
major leap. The maintainer's framing: *"the v1→v2 transition is the
natural place to introduce user-visible UX change; spreading UX leaps
across v2.0→v2.1 minors understates the version jump from the surgeon's
standpoint."* This is a scheduling discipline, not a versioning-policy
amendment to [ADR-0007](0007-version-numbering-policy.md) — backend-only
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
TotalSegmentator + MONAILabel + Kumar-Oram orchestration. `Modeling/`
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
2. **Anatomy Definition** (`LiverSegmentation/` — new module) — segment liver, portal vein, hepatic vein, and tumors using per-structure micro-workflows that orchestrate TotalSegmentator + Kumar-Oram (vessels) + MONAILabel-DeepGrow (tumors); scratch-and-accept pattern produces a single canonical Segmentation node.
3. **Vascular Territories** (`VascularTerritories/` — renamed from `LiverSegments/`) — two-tab structure: *Couinaud (automatic)* one-shot AI compute, and *Custom segments* flexible builder.
4. **Resection Planning** (`LiverResections/`) — resection table with per-row state machine (Init → Planning → Confirmed per [ADR-0019](0019-resection-state-machine.md)); active-resection detail panel; classification overlay; resectogram view invoked from per-resection detail.
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

The abstract base exposes a polymorphic interface (`getSegments()`, `getLabelMap()`, `getSegmentationNode()`, `getMethod()`). Downstream consumers (Stage 4 classification overlay, Stage 5 volumetry analysis) consume the base class without caring which subtype. Both subtypes coexist in the scene; surgeon switches the active one via Slicer's `qMRMLNodeComboBox`.

The earlier 2026-05-15 volumetry-framework note's claim that "the current resection behaviour is a degenerate case of the framework" is **retracted**. Stage 3 (territories) and Stage 5 (volumetry-partition) are two distinct surgeon-facing problems with two distinct data models. They may share a compute kernel (Fast Marching with sampled seeds) but not a node-level abstraction. The PKS note will be amended.

### Cross-cutting UI conventions

- **`qMRMLNodeComboBox` is the binding primitive** for every node-management surface (classifications, volumetry partitions, etc.). Slicer-native; provides create/select/rename/delete for free.
- **Hierarchical table + master-detail endpoints sub-table** for Stage 3 Manual (groupings → centerlines → endpoints). Reuses `qMRMLMarkupsControlPointTableWidget` from Slicer-core for the endpoints panel.
- **`ctkCollapsibleButton`-organised module widgets**, compact density (Slicer-native), no parallel palette/theme (per [ADR-0010](0010-accessibility-and-i18n.md)).
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

`TotalSegmentator` and `MONAILabel` are **not** declared as `EXTENSION_DEPENDS` and are **not** in the Superbuild. They install lazily via `slicer.util.pip_install(...)` on first surgeon invocation of an AI-driven feature. First-use prompt shows the download size and asks for confirmation. Settings panel under the Liver shell exposes pre-download and re-install affordances for surgeons going offline.

Slicer-Liver consumes the AI packages' Python APIs directly — it does not require the TotalSegmentator or MONAILabel *Slicer extension wrappers* to be installed. Surgeon interacts via Slicer-Liver's UI, not via the upstream extensions' own widgets.

### Persistence — `.lrp.json` schema v3

The existing `.lrp.json` storage (schema v2 from [PR #383](https://github.com/ALive-research/Slicer-Liver/pull/383)) bumps to v3 to capture v2.0's surgeon-facing state:

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

**Rejected because** it forces surgeons through the shell for tasks that may be more naturally invoked standalone (e.g., a researcher computing Couinaud on a dataset without planning any resection). Per [ADR-0007](0007-version-numbering-policy.md), removing an independently-selectable module is a MAJOR-version-breaking compatibility surface change — already triggered by the v1→v2 jump on other surfaces, but adds an unnecessary one.

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
- Two `vtkMRMLAbstractTerritoriesNode` subclasses + a base imply C++ MRML node hierarchy work (per [ADR-0004](0004-python-cpp-boundary.md) — data nodes are C++).
- `.lrp.json` schema v3 needs a migration loader from v2; load-time fallbacks for missing fields.
- Subject Hierarchy management code must be wired across every node-creating module — a per-module discipline gate.
- The resectogram custom layout registration is a new mechanism in `LiverResections/`.

### Follow-on work

- **Architecture diagrams** in `Docs/architecture/` — stage flow + dependency map, territories class hierarchy, MRML node landscape.
- **ADR-0024 — Segmentation orchestration** for Stage 2's per-structure micro-workflows (TotalSegmentator + Kumar-Oram + MONAILabel + Segment Editor orchestration).
- **ADR-0025 — Locator architecture** for the resectogram hover→3D + click→reslice interactions, the 1:1 (u,v) mapping insight, and the v2.0/v2.1 scope split.
- **Schema v3 migration** PR for `vtkMRMLBezierSurfaceStorageNode` (`.lrp.json`).
- **Class refactor** PRs for `vtkMRMLAbstractTerritoriesNode` + subclasses + Stage 3 Auto and Manual tab rewiring.
- **`LiverSegments/` → `VascularTerritories/` rename** + content refactor into the framework.
- **`LiverSegmentation/` new module** + lazy-install machinery for TotalSegmentator + MONAILabel.
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
- `.lrp.json` schema header reads `"schemaVersion": 3` on writes; reader supports v2-to-v3 fallback loading.
- Subject Hierarchy folder names "Anatomy", "Vascular Territories", "Resections", "Volumetry" exist after typical workflow use. Grep for `SubjectHierarchyCreateFolder` (or upstream equivalent) in each module's logic.
- The 2026-05-14 stitch and 2026-05-15 framework PKS notes carry "Superseded by ADR-0023" annotations on the relevant claims.

## References

- [ADR-0007 — Version numbering policy](0007-version-numbering-policy.md). v2.0 is feature-driven, no calendar floor. UX-grouping is scheduling discipline, not a versioning amendment.
- [ADR-0009 — UX and design discipline](0009-ux-and-design-discipline.md). Per-PR Mermaid + design rationale stays in force; this ADR adds the extension-wide target shape.
- [ADR-0010 — Accessibility and i18n](0010-accessibility-and-i18n.md). No parallel palette/theme; align with Slicer + contribute upstream.
- [ADR-0011 — SCT terminology dispatch](0011-sct-terminology-dispatch.md). Per-tool LabelToSCT.json bridges remain the dispatch alphabet. §3 path examples need a small amendment against `Resources/Terminology/LabelToSCT/` actual location.
- [ADR-0012 — LayerDM migration v2.0 scope](0012-layerdm-migration-v2-scope.md). LiverSegments / LiverVolumetry / Modeling LayerDM migration remains deferred to v2.1.0.
- [ADR-0013 — LayerDM Pipeline pattern](0013-layerdm-pipeline-pattern.md). Stage 4's resection surfaces and the resectogram each have their own Pipelines.
- [ADR-0014 — LiverMarkups dissolution](0014-livermarkups-dissolution.md). LiverMarkups module is removed; Bezier-surface widget lives in `LiverResections/`.
- [ADR-0019 — Resection state machine](0019-resection-state-machine.md). Stage 4's Init → Planning → Confirmed per resection.
- Tracker [issue #305](https://github.com/ALive-research/Slicer-Liver/issues/305) — v2.0.0 release tracker, scope-expansion section.
- The maintainer's design conversation 2026-05-21 (stage-by-stage walkthrough + grilling pass) — captured in the PKS project log [[denote:20260507T130427]].
- The forthcoming **ADR-0024** (Segmentation Orchestration) and **ADR-0025** (Locator Architecture) cover Stage 2 and the resectogram hover/click interactions respectively.

---

*AI-assisted authorship: this ADR was drafted with help from Anthropic's Claude (Opus 4.7, `claude-opus-4-7`) via Claude Code, under the maintainer's iterative design walkthrough + grilling pass.*

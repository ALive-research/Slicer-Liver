# 0026. Segment Editor effects in Slicer-Liver

- **Status:** Accepted
- **Date:** 2026-05-21
- **Deciders:** R. Palomar
- **Diagrams:** inline below.
- **PR:** <filled on merge>

## Context

Slicer-Liver v2.0.0's Stage 2 (Anatomy Definition) ships several
algorithm integrations: TotalSegmentator (consumer), MONAILabel-DeepGrow
(consumer), and Kumar-Oram (internal — see the 2026-05-15 PKS subnote).
The initial ADR-0024 draft placed all three as Python `ToolWrappers/`
invoked by the orchestrator from per-structure cards. Maintainer
review on 2026-05-21 surfaced that Kumar-Oram fits a different Slicer
extension point — **the Segment Editor effect contract**
(`qSlicerSegmentEditorAbstractEffect` and its scripted-Python
companion `AbstractScriptedSegmentEditorEffect`) — substantially
better than a Slicer-Liver-bespoke wrapper.

Kumar-Oram is an **interactive vessel refinement** algorithm:
surgeon places seeds, sees a centerline track update in 3D, adjusts,
re-runs. That is the exact UX pattern Slicer's Segment Editor effect
toolbar was designed for (cf. stock effects: Threshold, Paint, Margin,
GrowFromSeeds, FillBetweenSlices). Implementing it as a Slicer-Liver
wrapper would re-implement Segment Editor's existing chrome (effect
toolbar, in-progress preview, accept/cancel buttons) in our own
module's UI — bespoke UX competing with the Slicer surface surgeons
already know.

Effects also unlock the **upstream-contribution path** that
[ADR-0010](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0010-accessibility-and-i18n.md)
codifies as a guiding principle ("align with Slicer, contribute
upstream"). A well-designed Slicer-Liver effect can land upstream
in Slicer-core's `SegmentEditorEffects` extension or as a standalone
Segment Editor effects extension — reducing maintenance pressure
on Slicer-Liver while benefiting the broader surgical-planning
community.

This pattern is also likely **recurring**. The 2026-05-21 design
discussion already surfaced one candidate (Kumar-Oram); future v2.0+1
and v2.1 work may add others (per-anatomy paint with anatomical
prior, vessel-aware smoothing, distance-map-informed threshold).
Codifying the placement + integration contract now keeps each
future effect from inventing its own integration shape.

## Decision

Slicer-Liver hosts algorithms that fit the **interactive-refinement**
interaction model as **Slicer Segment Editor effects** — concrete
subclasses of `qSlicerSegmentEditorAbstractEffect` (or its scripted
equivalent `AbstractScriptedSegmentEditorEffect`) — rather than as
orchestrator-invoked Python wrappers.

The pattern applies when an algorithm:

1. Operates on a single `vtkMRMLSegmentationNode` segment (input + output are the same segment, refined in place).
2. Has an *interactive* nature (seeds, scribbles, hover, iterative parameter adjustment).
3. Benefits from Segment Editor's existing chrome (effect toolbar, in-progress preview, Accept/Cancel, undo integration).
4. Does NOT need cross-segment or cross-node logic (those belong to the orchestrator or higher-level workflow code).

Algorithms outside this envelope — multi-segment dispatch (TotalSegmentator), workflow orchestration (the Stage 2 orchestrator itself), or display-only logic (LayerDM Pipelines per ADR-0013) — stay in their respective patterns.

### Placement

Effects live **within the orchestration module that hosts the dominant workflow path**, under an `Effects/` subdirectory:

```
<OrchestrationModule>/
├── <OrchestrationModule>.py
├── ToolWrappers/                          # one-shot algorithm wrappers
├── Effects/
│   └── SegmentEditor<EffectName>Effect.py # one effect per file
└── Resources/
```

For v2.0:

```
LiverSegmentation/
├── LiverSegmentation.py
├── ToolWrappers/
│   ├── TotalSegmentator.py
│   ├── MONAILabel.py
│   └── VMTK.py
├── Effects/
│   └── SegmentEditorKumarOramEffect.py
└── Resources/
```

Sibling top-level effects modules (a separate `LiverSegmentEditorEffects/`
or similar) are explicitly **rejected** for v2.0 — co-locating effects
with their dominant-orchestrator parent module keeps the discovery
path tight ("Kumar-Oram refines vessels; vessels live in
LiverSegmentation; the effect lives where vessels live"). Migration
to a sibling module — or upstream — is a future move per the
upstream-contribution path below.

### Hybrid orchestration pattern

Each effect is **standalone-invocable** via Segment Editor's toolbar
(surgeon picks any segment, picks the effect, runs it). The
orchestrator that hosts the effect ALSO surfaces a **convenience
button** in its relevant per-structure card that opens Segment Editor
with the right segment selected and the right effect pre-activated.

```mermaid
flowchart LR
    Card["Orchestrator's<br/>vessel card<br/>(LiverSegmentation)"]
    SE["Segment Editor<br/>(stock Slicer)"]
    Effect["Kumar-Oram<br/>effect"]
    Seg["vtkMRMLSegmentationNode<br/>(vessel segment)"]

    Card -."Refine with Kumar-Oram"<br/>(programmatic open<br/>+ activate effect".-> SE
    SE -- toolbar pick --> Effect
    Effect -- in-place refine --> Seg
    Card -. standalone fallback .-> SE
```

This preserves three properties:

- **Discoverability** — surgeons in the orchestrated flow see the
  "Refine with Kumar-Oram" button in the dominant case.
- **Standalone access** — surgeons can invoke the effect on any
  segment via Segment Editor outside the orchestrated flow
  (preserving the 2026-05-15 noisy-AI-contingency commitment).
- **No bespoke UI duplication** — the effect's in-progress preview,
  parameter inputs, and Accept/Cancel are Segment Editor's standard
  chrome.

### Activation contract

The orchestrator's convenience button calls (in pseudo-code):

```python
segmentEditorWidget = slicer.modules.segmenteditor.widgetRepresentation().self().editor
segmentEditorWidget.setSegmentationNode(vesselSegmentation)
segmentEditorWidget.setCurrentSegmentID(vesselSegmentID)
segmentEditorWidget.setActiveEffectByName("Kumar-Oram")
slicer.util.selectModule("SegmentEditor")
```

The exact API may evolve (Slicer-core occasionally restructures the
Segment Editor widget surface); the contract above is the **stable
intent** — programmatic open + segment-select + effect-activate, then
hand off to Segment Editor's own UI loop.

### Effect implementation convention

Each effect:

- Subclasses `AbstractScriptedSegmentEditorEffect` (Python).
- Lives in a single `SegmentEditor<EffectName>Effect.py` file.
- Names itself (`self.scriptedEffect.name = "Kumar-Oram"`) using the
  surgeon-facing label (not snake_case).
- Provides an icon in `Resources/Icons/` (PNG, per Slicer convention).
- Has its own help-text and parameter-default contract; no shared
  state with the host module's orchestrator beyond the active
  segment.
- Registers itself with the Segment Editor framework at module-load
  time via `slicer.modules.segmenteditor.widgetRepresentation().self().editor.effectsForScriptedEffects()`
  (or the equivalent stable API).

### Lazy dependencies

Effects follow the same lazy-install rule as ToolWrappers per
[ADR-0024](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0024-segmentation-orchestration.md):
if an effect's algorithm needs Python packages not in the Slicer
runtime, it `slicer.util.pip_install`'s them on first activation with
a confirmation prompt. The Kumar-Oram effect inherits its algorithm's
ITK dependencies from Slicer's bundled ITK; no first-use install
expected, but the contract holds for future effects.

### Upstream-contribution path

The `Effects/<EffectName>` source file is **structurally
upstream-ready** from day one:

- No Slicer-Liver-only utility imports beyond what the effect itself
  needs.
- Algorithm code factored into a separable module (effect class glues
  Segment Editor surface to algorithm; algorithm doesn't depend on
  Segment Editor).
- Documentation references no Slicer-Liver-specific surgical-planning
  context — the effect is a *generic vessel refinement effect* that
  *Slicer-Liver* happens to use for portal/hepatic vein refinement.

When an effect matures (v2.1+ candidate decision per maintainer),
the migration path is to lift the file into a Slicer-extension-ready
shape (its own CMakeLists, its own Resources directory) and either:

- contribute upstream to Slicer-core's `SegmentEditorEffects`, or
- ship as a standalone Slicer extension (e.g., `SlicerSegmentEditorVesselEffects`)
  that Slicer-Liver consumes via `EXTENSION_DEPENDS`.

Both paths reduce the file's residency in Slicer-Liver to zero. The
v2.0 placement under `LiverSegmentation/Effects/` is the *temporary
incubation home*.

## Alternatives considered

### Alternative A — Effects as orchestrator-invoked Python wrappers

Treat all v2.0 algorithms (including Kumar-Oram) as `ToolWrappers/`
called by the orchestrator. The wrapper produces a scratch node;
surgeon Accepts to canonical.

**Rejected because** wrappers fit the *one-shot* / *parameter-tuned*
algorithm pattern (TotalSegmentator, MONAILabel-DeepGrow run on a
full input volume). Kumar-Oram's *iterative* / *interactive*
nature — seeds, scribbles, mid-run preview, parameter adjustment —
re-implements Segment Editor's existing chrome inside the orchestrator.
The orchestrator-wrapper pattern stays appropriate for one-shot
algorithms; effects host the interactive ones. See
[ADR-0024 Alternative G](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0024-segmentation-orchestration.md)
for the same call from the orchestrator side.

### Alternative B — Sibling top-level effects module

Ship `LiverSegmentEditorEffects/` (or similar) as a sibling Slicer-
Liver scripted module dedicated to all effects.

**Rejected for v2.0** because effects in v2.0 are sparse (one effect:
Kumar-Oram). A dedicated module would be 95% boilerplate. Co-locating
effects with their dominant-orchestrator parent keeps surgeon
discoverability tight. If the effect count grows past ~3 — or if any
effect migrates upstream — the sibling-module shape becomes a natural
next step.

### Alternative C — Effects as `vtkSlicerModuleLogic` subclasses

Use Slicer's general module-logic pattern instead of the Segment
Editor effect framework.

**Rejected because** module-logic classes are not addressable from
Segment Editor's toolbar — surgeons would not see the effect in the
chrome they expect, undoing the central UX argument for this ADR.

### Alternative D — Standalone Slicer extension from day one

Ship Kumar-Oram as a separate Slicer extension immediately, not
inside Slicer-Liver.

**Rejected for v2.0** because Slicer-Liver is the only consumer in
v2.0; shipping a separate extension adds installation friction and
maintenance overhead without immediate benefit. The
upstream-contribution path stays open for v2.1+ when (a) the effect
matures and (b) a second consumer surfaces.

## Consequences

### What becomes easier

- Slicer surgeons trained on Segment Editor effects work with
  Slicer-Liver effects out of the box — no new chrome to learn.
- The effect's interaction model (toolbar pick + in-place preview +
  Accept/Cancel) is implemented once by Slicer, not re-implemented per
  effect by Slicer-Liver.
- Future effects (per-anatomy paint, vessel-aware smoothing, etc.)
  follow a documented placement convention rather than each inventing
  its own integration shape.
- Upstream contribution is a structural goal of the placement, not a
  retrofit — algorithm code factors out cleanly.

### What becomes harder

- Effect registration / activation API stability across Slicer-core
  versions adds a small surface to monitor. Slicer's effect API has
  evolved historically; Slicer-Liver may need to track the
  `effectsForScriptedEffects()` (or equivalent) call shape across
  upstream rev-bumps.
- The hybrid orchestrator-convenience-button + standalone-effect
  pattern means surgeons can reach the effect via two paths; the UX
  must make both feel native (the orchestrator button isn't a
  "different" Kumar-Oram from Segment Editor's toolbar entry).
- Effect testing requires Slicer's Segment Editor harness rather than
  pure-Python invariant tests; CI implications mostly handled by
  ADR-0008's test-strategy convention.

### Follow-on work

- Implement `LiverSegmentation/Effects/SegmentEditorKumarOramEffect.py`
  as the first effect. Implementation issue follows under the
  v2.0.0 milestone (sub-issue of #409 once that lands).
- Author a small `Docs/architecture/segment-editor-effects.md` if a
  second effect lands and the cross-effect pattern needs visual
  reinforcement. (Out of v2.0 scope for now.)
- Walk back the 2026-05-15 Kumar-Oram PKS subnote
  (`~/pks/fleeting/20260515T102356`) — its "re-implemented as LayerDM
  Pipeline + Python orchestration" framing is superseded by this ADR's
  effect placement. (Done off-tree as part of this PR's authoring
  context.)

## Conformance

Reviewable invariants that signal this decision is honoured:

- `LiverSegmentation/Effects/` exists and contains
  `SegmentEditorKumarOramEffect.py`.
- The effect class subclasses `AbstractScriptedSegmentEditorEffect`
  (Python) — grep for that base class import + subclass relationship.
- The effect registers itself with the Segment Editor framework at
  module-load time — grep for the registration call in
  `LiverSegmentation.py` or its loader.
- The orchestrator's vessel-card "Refine with Kumar-Oram" button
  programmatically activates the effect via the activation contract
  documented above — grep for `setActiveEffectByName("Kumar-Oram")`
  (or the equivalent stable Slicer-core API call) in
  `LiverSegmentation.py`.
- Effect source files contain no Slicer-Liver-specific surgical-
  planning context in algorithm code — algorithm modules factored
  separately; effect class is a thin Segment Editor adapter.
- Effect icon present at `LiverSegmentation/Resources/Icons/KumarOram.png`
  (or equivalent).
- No new `vtkSlicerLiver*` algorithm class for Kumar-Oram in v2.0 —
  the algorithm stays in Python under `Effects/` or a sibling
  `Algorithm/` Python package.

## References

- [ADR-0008 — Testing strategy](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0008-testing-strategy.md). Effect-testing harness conventions.
- [ADR-0010 — Accessibility and i18n](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0010-accessibility-and-i18n.md). "Align with Slicer, contribute upstream" — the principle this ADR realises for the effect-pattern category.
- [ADR-0013 — LayerDM Pipeline pattern](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0013-layerdm-pipeline-pattern.md). Effects are *not* Pipelines; complementary extension point.
- [ADR-0023 — Unified GUI / six-stage surgeon workflow](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0023-unified-gui-stage-workflow.md). Stage 2 surfaces the orchestrator vessel-card from which the effect is invoked.
- [ADR-0024 — Segmentation orchestration](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0024-segmentation-orchestration.md). The orchestrator that hosts the effect (Alternative G of ADR-0024 cross-references this ADR).
- Tracker [issue #305](https://github.com/ALive-research/Slicer-Liver/issues/305) — v2.0.0 release tracker.
- Issue [#311](https://github.com/ALive-research/Slicer-Liver/issues/311) — Kumar-Oram ITK upstream modernization (existing, held). The effect rewrite is the new shape of this work.

---

*AI-assisted authorship: this ADR was drafted with help from Anthropic's Claude (Opus 4.7, `claude-opus-4-7`) via Claude Code, in response to the maintainer's 2026-05-21 direction that Kumar-Oram fits the Segment Editor effect contract rather than the orchestrator-invoked wrapper pattern. The pattern documented here generalises beyond the Kumar-Oram first instance.*

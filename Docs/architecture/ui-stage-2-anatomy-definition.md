# UI architecture — Stage 2: Anatomy Definition

Reference companion to [ADR-0023 §Stage 2][adr-0023] + [ADR-0024
(orchestration)][adr-0024] + [ADR-0026 (Segment Editor effects)][adr-0026].
Captures the per-structure card layout, tool invocation surface, the
scratch + Accept review UX, and the lazy-AI-install integration.

[adr-0023]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0023-unified-gui-stage-workflow.md
[adr-0024]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0024-segmentation-orchestration.md
[adr-0026]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0026-segment-editor-effects.md
[adr-0011]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0011-sct-terminology-dispatch.md

## What this stage does

Segment four anatomical structures (Liver / Portal vein / Hepatic vein / Tumors) using per-structure micro-workflows that orchestrate TotalSegmentator + Kumar-Oram (Segment Editor effect) + Segment Editor for manual fixes. Each structure publishes one segment in the canonical `vtkMRMLSegmentationNode` per [ADR-0011][adr-0011]. Interactive tumor refinement (e.g. MONAILabel-DeepGrow) is deferred to v2.1+ per [ADR-0024][adr-0024] Alternative H — MONAILabel's client/server architecture violates the lazy-pip-install envelope.

Module home: `LiverSegmentation/` (new in v2.0; see ADR-0024).

## Panel layout

```
┌─ 2. Anatomy Definition ────────────────────────────────────────────┐
│                                                                    │
│ ┌─ Checklist ──────────────────────────────────────────────────┐  │
│ │  Liver          ✓   Accepted                                 │  │
│ │  Portal vein    ⋯   Scratch pending review                   │  │
│ │  Hepatic vein   ○   Not started                              │  │
│ │  Tumors (2)     ✓   2 accepted                               │  │
│ └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│ ┌─ Liver ──────────────────────────────────────────────────────┐  │
│ │  Source: [▼ Portal venous (patient_PV.nrrd)]                 │  │
│ │  Tools:  [Run TotalSegmentator]                              │  │
│ │  Scratch: ✓ accepted as canonical                            │  │
│ │  [Edit in Segment Editor]   [Reset to Scratch]               │  │
│ └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│ ┌─ Portal vein ────────────────────────────────────────────────┐  │
│ │  Source: [▼ Portal venous (patient_PV.nrrd)]                 │  │
│ │  Tools:  [Run TotalSegmentator (liver_vessels)]              │  │
│ │  Scratch: ⋯ pending — [Accept] [Reject]                      │  │
│ │  Refinement: [Refine with Kumar-Oram] (opens Segment Editor) │  │
│ │  [Edit in Segment Editor]                                    │  │
│ └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│ ┌─ Tumors ─────────────────────────────────────────────────────┐  │
│ │  Source: [▼ Portal venous (patient_PV.nrrd)]                 │  │
│ │  Tumor list:                                                 │  │
│ │   ▰ Tumor 1   ✓ accepted   [edit][×]                         │  │
│ │   ▰ Tumor 2   ✓ accepted   [edit][×]                         │  │
│ │   [+ Add tumor]                                              │  │
│ │  Tools:  [Run TotalSegmentator (tumor channel)]              │  │
│ │  [Edit in Segment Editor]                                    │  │
│ └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│ [Continue to Vascular Territories ▶]                               │
└────────────────────────────────────────────────────────────────────┘
```

(The Hepatic vein card mirrors Portal vein structurally; collapsed
in the sketch for brevity.)

## Behaviour notes

### Per-structure cards

Each card encapsulates one structure's micro-workflow:

| Structure | Tool chain | Notes |
|-----------|-----------|-------|
| Liver | TotalSegmentator → Segment Editor → Accept | Single-step AI; manual cleanup if needed. |
| Portal vein | TotalSegmentator (`liver_vessels`) → Accept → Kumar-Oram (effect) → Segment Editor | AI mask is the seed for Kumar-Oram refinement. |
| Hepatic vein | TotalSegmentator (`liver_vessels`) → Accept → Kumar-Oram (effect) → Segment Editor | Same chain as Portal vein, dispatched by SCT target. |
| Tumors | TotalSegmentator (tumor channel) → Segment Editor → Accept | Multi-focal via per-tumor sub-list. Interactive AI tumor refinement is deferred to v2.1+ per ADR-0024 Alt H. |

### Scratch + Accept lifecycle (per ADR-0024)

- AI tool-run writes into an orchestrator-private *scratch* `vtkMRMLSegmentationNode`.
- Card surfaces three actions while scratch is pending: **Accept** (copy into canonical, mark structure ✓ in checklist), **Reject** (discard scratch; card returns to "not started" state), **Re-run** (re-invoke the tool with different parameters or source).
- After Accept, the canonical segment is in-place editable via **Edit in Segment Editor** (which opens Segment Editor with that segment selected).
- For vessels, **Refine with Kumar-Oram** opens Segment Editor with the segment selected + the Kumar-Oram effect pre-activated (hybrid pattern per ADR-0026). Surgeon iteratively refines via the effect; on the effect's own Accept, the segment updates in place. No further orchestrator-side Accept needed (Segment Editor's effect Accept *is* the commit).

### Lazy AI install (per ADR-0023 + ADR-0024)

- TotalSegmentator is NOT an `EXTENSION_DEPENDS` entry.
- First click of `[Run TotalSegmentator]` triggers `slicer.util.pip_install` with a confirmation dialog showing the download size + GPU recommendation.
- The lazy-pip-install pattern is bounded to AI tools that consume as a Python package with no external runtime. MONAILabel-DeepGrow (server architecture) is out of v2.0 scope per ADR-0024 Alt H.
- Subsequent calls skip the prompt.
- Install failure: clear error message + manual-segmentation path remains available via Segment Editor.

### Tumor enumeration

- Multi-focal cases: tumor list inside the Tumors card. Each row is one tumor (numbered + untyped per ADR-0023 §"What is NOT in v2.0" + the 2026-05-14 terminology decision).
- Per-tumor actions: `[edit]` opens Segment Editor on that tumor's segment; `[×]` deletes with confirmation. Deletion cascades renumber + flag downstream consumers (Stage 4 margin readouts).
- `[+ Add tumor]` creates an empty tumor segment + invites the surgeon to run TotalSegmentator on the full volume (which will surface all tumors at once) or paint manually via Segment Editor for a single tumor.

### Source dropdown per card

Each card's `Source` dropdown defaults to the volume tagged `Portal venous` in Stage 1's manifest. Surgeon can override per-structure (some tumor types segment better on arterial — researcher use case). Dropdown shows volume name + role tag.

## Cross-stage interactions

| Direction | Surface |
|-----------|---------|
| Stage 1 → Stage 2 | Source dropdowns default to the volume's role tag from Stage 1's manifest. |
| Stage 2 → Stage 3 (Manual path) | The Portal vein segment is the input to Stage 3 Manual's VMTK ExtractCenterline. |
| Stage 2 → Stage 4 | The canonical Segmentation node is the input to Stage 4's distance-map computation (tumor / portal / hepatic). |
| Stage 2 → Stage 5 | The canonical Segmentation provides the ROI (Liver segment) for Stage 5's volumetry framework. |
| Sidebar | Stage 2 state indicator turns ✓ when all four structures have at least one Accepted segment. |

## See also

- [ADR-0023 §Stage 2][adr-0023] — workflow shape.
- [ADR-0024][adr-0024] — orchestrator implementation.
- [ADR-0026][adr-0026] — Segment Editor effects + Kumar-Oram placement.
- [GUI stage flow](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/architecture/gui-stage-flow.md) — Stage 2 in the cross-stage data flow diagram.
- [Stage 1 — Case Setup](ui-stage-1-case-setup.md) — upstream.
- [Stage 3 — Vascular Territories](ui-stage-3-vascular-territories.md) — downstream (Manual path consumes Stage 2's vessel segments).

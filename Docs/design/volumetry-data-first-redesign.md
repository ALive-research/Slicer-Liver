# LiverVolumetry — data-first UI/workflow redesign

- **Status:** Design-of-record (implemented) — seeds-first-class corrected model
- **Date:** 2026-08-05; corrected 2026-08-06 (seeds are first-class)
- **Scope:** `LiverVolumetry/Resources/UI/LiverVolumetryWidget.ui`,
  `LiverVolumetry/LiverVolumetry.py` (panel composition + gating only).
  The C++ logic (`Logic/vtkLiverVolumetryLogic.*`, ADR-0015), the seed
  carrier/display/storage nodes, the LayerDM placement pipelines
  (ADR-0038 amendment), and the seeds table widget are **not** touched
  except where §5 notes a small, invariant-tested logic change.
- **Trigger (maintainer, verbatim):** "I'm still confused about what is
  what in the ui and what is the workflow"; "the show 3d button is in
  between rows: weird alignment"; "there are way too many foldable
  widgets with single widgets inside... not worth it"; "think about the
  data we need to do the work and propose a workflow/design that is
  stunningly simple and effective."
- **Method:** derived from the *data dependencies in the logic*, not
  from the current layout. Supersedes the incremental-alignment track of
  `volumetry-workflow-consistency-critique.md` (its D1–D8 verb/gating
  decisions are kept; its layout is replaced).

---

## 1. What the computation actually needs (read from the logic)

`LiverVolumetryLogic.computeVolume(...)` has exactly **four branches**,
selected silently by which optional inputs happen to exist:

| # | Resections | Seeds | What runs | What the surgeon gets |
|---|-----------|-------|-----------|----------------------|
| B1 | none | none | `SegmentStatistics` over the **whole segmentation** | one row per segment: volume + % of total |
| B2 | none | ≥1 | label-lookup at each seed in the rasterized selection | one row per seed = volume of the **whole segment** the seed sits in |
| B3 | ≥1 | ≥1 | Bezier carriers projected as barriers → `ConnectedThreshold` region-grow per seed | one row per seed = the **piece** bounded by the resection(s), + a total row |
| B4 | ≥1 | none | `ComputeAdvancedPlanningVolumetry` early-returns inside its `if (ROIMarkersList)` guard | **nothing** — silent no-op |

> **Correction (2026-08-06): seeds are a FIRST-CLASS input.** An earlier
> revision of this document retired B2 (seeds without resections) from the UI
> and framed the whole seed workflow as subordinate to resections ("Partition
> by resection"). That framing was **wrong**. The surgeon computes segment
> volumes in **two peer ways** — *tick segments* (B1) OR *place seeds to pick
> regions* (B2) — and resections are an **optional refinement** (B3), not the
> framing. The seeds-without-resections path (B2: a seed measures the whole
> segment/region it sits in) is restored as a valid, first-class workflow. The
> sections below are amended to this corrected model; only the still-true
> removals (reference-volume selector, duplicate total-volume picker,
> module-owned results table) are kept from the earlier revision.

`GenerateSegmentsLabelMap(...)` (the "Generate segments" button) always
needs **seeds**; resections are optional barriers. Each seed's piece
keeps the seed's label; every other foreground voxel becomes label 99 →
segment 0, named **"Remnant"**. Output: a new Segmentation node.

### Data-flow table (input → used by → output)

| Input (widget today) | Used by | Output |
|---|---|---|
| Input segmentation + segment multi-selection (`InputSegmentSelectorWidget`) | rasterized to a labelmap feeding B2/B3/B4 + the seed pick surface; **ignored by B1** (SegmentStatistics reads the whole node) | — |
| Reference volume (`ReferenceVolumeSelector`) | *geometry hint only* for `ExportSegmentsToLabelmapNode`; `None` is legal everywhere (export falls back to the segmentation's own geometry) | — |
| "Total volume segments" (`TargetSegmentationSelectorWidget`) | rasterized → denominator `TargetSegmentationVolume` for the % column | the % column |
| Resection plans, checked (`ResectionTargetNodeComboBox`) | wrapper → `GetGeometryNode()` Bezier carrier (ADR-0014) → projected as region-grow **barriers** (B3, Generate) | bounded pieces |
| Seeds (carrier `vtkMRMLVolumetrySeedsNode`) | pick which piece/segment to measure (B2/B3); name + colour the generated segments | per-seed rows; generated segments |
| Output table (`VolumeTableSelectorWidget`) | destination of `VolumetryTable` rows | volumes table |

### Verified answers to the framing questions

- **Are seeds needed for plain total/remnant volumetry?** For *plain
  per-segment* volumetry (B1): **no** — confirmed. For *remnant-vs-
  resected* volumetry with resections (B3): **yes, today** — a seed is
  the only way to say "measure this piece"; there is no automatic
  both-sides computation. Remnant % requires one seed placed inside the
  intended remnant.
- **What do resection targets contribute?** Not a subtraction: the
  Bezier surfaces are voxelized into the labelmap as **barriers** and
  each seed region-grows up to them. No seeds ⇒ no growth ⇒ B4's silent
  empty result.
- **Contradictions between UI and data (found in this pass):**
  1. Compute is gated on "select at least one segment", but B1 then
     reports **all** segments of the node — the selection is ignored on
     the very path most users hit first.
  2. Compute is gated on a reference volume that **no branch requires**
     (geometry-hint only; `None` works everywhere).
  3. Checking resections without placing a seed passes no gate today
     and computes **nothing** (B4) — the worst confusion generator.
  4. Compute is *not* gated on the output table; a `None` table raises
     `ValueError` in `computeVolume` and leaves the wait cursor stuck.

**Design consequence:** the panel must expose exactly two things — *what
to measure* (segments) and, optionally, *how to split it* (resections +
seeds) — and one primary verb. Everything else in the current panel is
ceremony around inputs the data does not require.

---

## 2. Critique of the current panel (named sins)

Current structure: 1 outer `qMRMLCollapsibleButton` ("Resection
Volumetry") + 6 `ctkCollapsibleGroupBox`es (Input, Reference volume,
Total volume segments, Resection targets, Actions, Seeds, Results) —
five of them wrapping a **single row** each.

| # | Sin | Principle violated | Severity |
|---|---|---|---|
| S1 | 7 foldables, 5 with one widget inside — a database form, not a workflow; every fold is a click tax and hides state | Minimalism; gestalt grouping (grouping that encodes no real relationship) | Blocking |
| S2 | Primary action ambiguous: "Place seeds" sits *above* "Compute volumes" in an "Actions" box, implying seeds are step 1 of the main path — but the 90% path needs no seeds (§1 B1) | Primary-action clarity; progressive disclosure inverted (advanced input promoted, basic path buried) | Blocking |
| S3 | Mode is implicit: the same Compute button silently does B1/B2/B3/B4 depending on hidden state; B4 produces nothing with no message | Visibility of system status; error prevention | Blocking |
| S4 | Show-3D floats at grid (0,3) beside the segment selector, aligning with neither the selector row nor anything else | Alignment/gestalt; the maintainer's explicit complaint | Should-fix |
| S5 | "Input segmentation / segments" vs "Total volume segments" vs "Resection targets": three near-synonym noun phrases with no workflow verbs; a surgeon cannot map them to TLV / FLR concepts | Recognition-over-recall; speak the user's language | Blocking |
| S6 | Reference-volume selector demanded (gates Compute) though the data never needs it (§1 contradiction 2) | Minimalism; error prevention (false precondition) | Should-fix |
| S7 | Output-table selector: the user must *choose a destination node* before seeing a number; `None` default + un-gated ⇒ traceback (§1 contradiction 4) | Recognition-over-recall; safe defaults | Should-fix |
| S8 | Results table appends across runs, mixes denominators, labels a row "TotalVolume of List <transient node name>", and shows "ROI Voxels" (engineer units) | Speak the user's language; minimalism | Should-fix |

The requirements line, verb normalisation (Place seeds / Compute volumes
/ Generate segments), Clear-all, and the carrier-backed seeds table from
the consistency-critique pass are all **kept** — those were correct.
They could not fix S1–S3 because the *shape* of the panel is wrong.

---

## 3. The redesign

### 3.1 Two peer ways to say "what to measure", plus an optional refinement

- **Tick segments (B1).** "How big is the liver / the tumor?" → tick the
  segment(s) → **Compute volumes** → table. Zero seeds, zero ceremony.
- **Place seeds (B2).** "Measure these regions." → **Place seeds** →
  click inside each region you want measured → the same **Compute
  volumes** button emits one row per seed (each = the whole
  segment/region the seed sits in). No resection needed — this is a
  first-class workflow, not subordinate to resections.
- **Refine by resection (B3, optional).** "If I cut along these
  resections, what remains?" (ADR-0023 Stage 5: "seed-and-category
  partition workbench consuming Confirmed resections as barriers") →
  turn on **Refine by resection** → check resection(s) → each seed now
  measures the **piece** bounded by the resection(s) instead of the whole
  region; **Generate segments** materialises the partition as a
  Segmentation.

One primary verb (Compute volumes) serves all three. Ticking segments and
placing seeds are **peers**; the refinement *modifies what a seed
measures* without being a precondition. This removes the S3 hidden-mode
problem by making the refinement a visible, off-by-default choice.

### 3.2 Panel, top to bottom (0 foldables, down from 7)

```
Volumetry
┌───────────────────────────────────────────────────────────────┐
│ Segments   [segmentation node ▾]                  [Show 3D ▾] │   ← one header row
│ [ segment multi-select list (qMRMLSegmentSelectorWidget) ]    │
│                                                               │
│ Seeds                                                         │   ← flat, first-class
│ [ Place seeds ]  [ Clear all ]                                │
│ [ seeds table: swatch · label · delete ]                      │
│ Hint: place a seed in each region you want measured.          │
│                                                               │
│ ☐ Refine by resection                                         │   ← optional, unchecked
│    Resections   [☑ Resection 1  ☐ Resection 2 ▾] (enabled     │
│                  only while the box is checked)               │
│                                                               │
│ [ Generate segments ]                          (shown w/ seeds)│   ← secondary
│ [██████████████  Compute volumes  ██████████████]             │   ← primary, full width
│ Requirements/status line (always visible)                     │
└───────────────────────────────────────────────────────────────┘
```

Layout rules:

- **No outer "Resection Volumetry" collapsible.** Inside the Liver shell
  the stage header already says Volumetry (ADR-0023 sidebar); a second
  headline is noise. (`updateGUIFromParameterNode`'s enable-gate moves
  to the top-level widget.)
- **Section labels are flat bold labels** (`Segments`, `Seeds`), not
  group boxes — the Segment Editor / Data module idiom. Nothing folds:
  seeds are first-class, so they are never hidden behind a fold. The
  optional refinement is a plain labelled **checkbox**, not a collapsible
  wrapping a single row (that was the S1 fold-tax sin).
- **Show 3D** becomes the right-aligned trailing widget of the
  *segmentation node row*, fixed width — same row as the node it acts
  on, resolving S4 by association, not by decoration.
- **Compute volumes** is the panel's single full-width default-styled
  button, last, above the requirements line — the Slicer Apply
  convention. **Generate segments** sits just above it, secondary
  styling, hidden until at least one seed exists (it needs a seed).
- **Refine by resection** is an unchecked-by-default checkbox that
  enables the resection combo; it *never* gates Compute.

### 3.3 Removed inputs (the data said so)

| Removed | Why (data) | Replacement |
|---|---|---|
| Reference-volume selector + group | §1: geometry hint only, `None` legal everywhere | pass `None`; segmentation geometry drives rasterization (OQ2) |
| "Total volume segments" selector + group | duplicate segment picker whose only job is the % denominator | denominator = the **selected input segments** (empty selection = all). One selection, one meaning: "% of what you measured" (OQ3) |
| Output-table selector + Results group | destination-node ceremony before the first number; unsafe `None` | module-owned table node "Volumetry", auto-created on first Compute, shown via the existing `showTable` layout switch (OQ4) |
| Standalone "Actions" group | actions belong where their inputs live | per §3.2 |

### 3.4 Gating truth table (replaces today's false preconditions)

| Action | Enabled when | Requirements line otherwise |
|---|---|---|
| Compute volumes | a segmentation is selected **and** (≥1 segment ticked **or** ≥1 seed placed) | "Select a segmentation, then tick segments or place seeds." |
| Place seeds | a segmentation is selected (pick labelmap needs it) | "Select a segmentation." |
| Generate segments | ≥1 seed placed (resections optional) | "Place at least one seed." (button hidden until a seed exists) |
| Refine by resection (optional; never gates Compute) | when ON, ≥1 resection checked to have effect | "Check a resection to bound the seed regions." |

There is **no** gate that requires a resection to compute. The
seeds-without-resections path (B2) is first-class: a seed alone satisfies
both Compute and Generate. Refine-by-resection is purely optional — when
ON with no resection checked it names the refine requirement (so the
surgeon knows the refinement has no effect yet) but never disables
Compute.

The existing `_actionRequirements` / `_updateRequirementsMessage` /
tooltip trio is kept as the single source of truth; only the predicate
set changes. `_actionRequirements` now returns a fourth `refineUnmet`
list. The C++ branches (B1/B2/B3) stay unchanged (ADR-0015); the earlier
revision's decision to retire B2 from the UI is **reverted** (see the §1
correction and OQ5).

### 3.5 Behaviour polish (recognition over recall)

- **Auto-select** the sole segmentation in the scene (standard Slicer
  module behaviour); with the reference-volume selector gone there is
  nothing else to pick on the basic path.
- **Results table**: cleared and recomputed on every Compute (append
  mixed denominators across runs — S8). Columns renamed to surgeon
  terms: `Region | Volume (mL) | % of total` (drop "ROI Voxels"; the
  total-volume column becomes a single header note or a "Total" row).
  Seed-piece rows use the seed's label; the per-run total row is labeled
  "All pieces", never the transient fiducial's node name. Guard the
  divide-by-zero in the % cell.
- **New-seed default label** "Segment N" (kept from critique D7) so
  generated segments are never blank-named.
- Wait-cursor handling wrapped in try/finally so no failure path leaves
  the cursor stuck.

### 3.6 What explicitly does NOT change

- The seed carrier / display / storage nodes, the
  `PointPlacementState` display-node channel, and the LayerDM pipeline
  registrations (ADR-0038 amendment; ADR-0013 §5 — no custom DM).
- The C++ `vtkLiverVolumetryLogic` algorithms and signatures
  (ADR-0015); §3.5's column rename + row-label fix touch only the
  presentation-shaping code (`VolumetryTable` strings + the Python
  total-row label) and ship behind invariant tests (ADR-0027: red →
  green before implementation).
- The Python-composed panel discipline (ADR-0004), the a11y text rules
  (ADR-0010 — armed-state text cue, colour-never-alone swatches), and
  the non-blocking compute feedback (ADR-0009).
- `isStageComplete` semantics (ADR-0023 Stage-5 soft gate).

---

## 4. Workflow diagrams (ADR-0009 §2)

```mermaid
flowchart LR
  S[Select segmentation] --> B1[Tick segments]
  S --> B2[Place seeds]
  B1 --> C[Compute volumes]
  B2 --> C
  C --> T[Volumes table\nRegion / mL / %]
  B2 -. optional .-> R[Refine by resection:\ncheck resection barriers]
  R --> C
  B2 --> G[Generate segments\n(new Segmentation:\nregions + Remnant)]
```

---

## 5. OPEN QUESTIONS (defaults chosen; plan proceeds on defaults)

- **OQ1 — Seedless both-sides split.** B3 could be extended to
  auto-label *all* connected components after barrier projection, making
  remnant volumetry seed-free (place zero seeds, get every piece). This
  is a real C++ logic change beyond this redesign's scope and changes
  Stage-5 semantics (ADR-0023 calls it a *seed*-and-category workbench).
  **Default: no** — keep seeds as the piece-naming gesture; revisit as a
  v-next enhancement with its own ADR if wanted.
- **OQ2 — Drop the reference-volume input entirely?** Data says yes
  (§1). Risk: a future need to resample volumetry onto a specific
  acquisition grid. **Default: drop the widget**; if grid control ever
  matters, it returns as an Advanced setting, not a precondition.
- **OQ3 — % denominator.** Options: (a) selected input segments
  (default), (b) keep a separate denominator picker, (c) fixed
  "whole segmentation". **Default (a)** — one selection, one meaning;
  the old picker was the single most confusing widget (S5).
- **OQ4 — Module-owned results table vs user-selectable node.**
  **Default: module-owned, auto-created, replace-on-compute.** Users
  who want to keep a run rename the table in Data before recomputing
  (matches Segment Statistics ergonomics).
- **OQ5 — Retire UI reachability of B2 (seeds without resections)?**
  **RESOLVED 2026-08-06: NO — B2 is first-class.** The earlier
  "Default: yes" was wrong (see the §1 correction). Seeds are a peer way
  to pick regions to measure, usable with no resection: a seed alone
  measures the whole region it sits in. The UI reaches B2 whenever a seed
  is placed and Refine-by-resection is off. Resections are fed to the
  compute (routing seeds into B3) *only* when Refine-by-resection is on
  and ≥1 resection is checked.
- **OQ6 — Show 3D: keep or drop?** Not a data input; pure viewing
  convenience. **Default: keep**, right-aligned on the segmentation
  row (it is the one button surgeons reach for constantly in Stage 2).

## 6. Terminology resolved

| Fuzzy (current UI) | Canonical |
|---|---|
| "Input segmentation / segments", "Total volume segments" | **Segments** (what to measure); the % denominator is *the same selection* |
| "Resection targets", "Resection:" | **Partition by resection** (group); **Resections** (the checkable list) — ADR-0023's "partition" vocabulary |
| "region-growing seeds", "ROI markers" | **Seeds** — one seed names one **piece** of the partition; the unseeded rest is the **Remnant** (matches the generated segment name in the logic) |
| "Calculate Volume" / "ROI Volume (cm3)" / "ROI Percentage" | **Compute volumes** / **Volume (mL)** / **% of total** |

## 7. ADR conformance

- **ADR-0004** — panel stays Python-composed; no C++ widget work.
- **ADR-0009** — this document is the §3 design rationale for the
  UI-touching PR; §4 is the workflow diagram.
- **ADR-0010** — requirements line + tooltips remain plain legible
  text; armed state cued by text, never colour alone.
- **ADR-0013/0038** — no custom displayable manager; placement seam and
  display-node state channel untouched.
- **ADR-0015** — C++ algorithm signatures unchanged; only presentation
  strings inside `VolumetryTable` may change (invariant-tested).
- **ADR-0023** — implements the Stage-5 "partition workbench" wording;
  the future partition node, if ever minted, must be
  `vtkMRMLVolumetryPartitionNode` (no `Liver` prefix per the T2.7
  convention — ADR-0023's v2.1 table still shows the old prefixed name
  and should be amended when that node is designed).
- **ADR-0027** — every behaviour change (gating truth table, table
  replace-on-compute, column rename) lands test-first.

# 0034. Stage-2 anatomy segments table, tool registry, and background job queue

- **Status:** Accepted
- **Date:** 2026-07-09
- **Deciders:** Rafael Palomar
- **Diagrams:** table mock inline (§1); no separate diagram file yet
- **PR:** _filled in on merge_

## Context

The 2026-07-09 end-to-end stabilization walkthrough (the maintainer
driving Stage 1 → 6 on real anatomy) surfaced structural UX problems
in Stage 2 (Anatomy Definition) that go beyond polish:

- **Process-major IA vs a data-major mental model.**  The panel is a
  `QTabWidget` of four per-structure cards; after the first run the
  surgeon's question is *what segments exist and in what state*, and
  that global state is invisible without visiting all four tabs.
- **Repetition as a symptom.**  Four containers holding identical
  controls whose only variance is the SCT target means the control
  belongs in a *row* and the parameter is the row.
- **Two interaction grammars for one goal.**  The AI path is
  card-grammar (Run → scratch → Accept/Reject); the import path is a
  separate section with a combo + assignment table that lands directly
  in canonical, skipping review.  Same goal, two rituals, one of which
  bypasses the clinical review boundary.
- **A conditionally-populated table.**  The import assignment table is
  empty and unexplained until a segmentation node is selected —
  a violation of the explainable-state bar
  ([ADR-0009][adr-0009]).
- **Node-level review of a segment-level object.**  Accept/Reject act
  on a scratch *node* while the surgeon reviews a *segment*; the
  scratch/canonical mechanism ([ADR-0024][adr-0024] §"Output
  contract") leaks implementation into the UX.
- **Multiplicity mismatch.**  Tumors are multifocal; one card for N
  lesions is a container mismatch a table absorbs naturally.
- **Ambiguous completion.**  `isStageComplete` is soft (≥ 1 tagged
  segment), so the sidebar flips "done" long before the anatomy is
  complete, and there is no affordance for the surgeon to *state*
  completeness.

Meanwhile the rest of the shell converged on a shared design language
([ADR-0023][adr-0023]): the Stage-4 resection table, the Stage-5
seed/category table, the Stage-3 hierarchical builder — **tables are
the workflow spine; rows are clinical objects; badges and confirm
flags are the contract currency**.  Stage 2 is the one stage speaking
a different language.

Two adjacent developments feed this ADR: the v2.0.0 scope re-baseline
absorbed real AI inference and its UX into v2.0 ([ADR-0012][adr-0012]
Amendments), and the phase-contracts direction (the tracked
user-verified "Validate and next" paradigm) needs a pilot stage.
Finally, a docs/forum research pass established what Slicer actually
supports for background processing from scripted modules (sources in
§5 and References) — the naive patterns are documented traps.

## Decision 1 — One anatomy segments table

Stage 2's panel is a single, always-visible **anatomy segments
table**, pre-seeded with the expected structures *before any data
exists*, so the empty state teaches the goal:

| 👁 | ■ | Structure | Source | Status | Actions |
|---|---|---|---|---|---|
| 👁 | 🟥 | Liver parenchyma | TotalSeg (fast) | ✓ Confirmed | 🔒 ✎ |
| 👁 | 🟦 | Portal vein | — | ○ Missing | ▶ ✎ |
| 👁 | 🟪 | Hepatic vein | TotalSeg | ⟳ Running… | ✕ |
| 👁 | 🟨 | Tumors | imported | ● Review | ✔ ✗ ✎ |

- Rows are pre-seeded from the structure vocabulary (Liver parenchyma,
  Portal vein, Hepatic vein, Tumors — the [ADR-0024][adr-0024] SCT
  set).  Tumors start as a single row (the backend emits one mask);
  per-lesion child rows via island splitting are a later increment.
- Columns: visibility eye + colour swatch (driving the stock
  segmentation display node), structure name, **Source** (which tool /
  import produced it), **Status** (the vocabulary below), and per-row
  actions.
- **Status vocabulary** (exhaustive, rendered as glyph + text, never
  colour alone per [ADR-0010][adr-0010]):
  `○ Missing → ⟳ Running → ● Review → ✓ Confirmed`, plus
  `∅ Marked absent` (an explicit clinical attestation that a structure
  is not present in this case — absence is stated, never inferred from
  a forgotten row) and `✎ Interactive…` (an interactive backend
  session is in progress; see Decision 3).
- The four tabs, the per-tab cards, and the separate import section
  are **retired**.  The QTabWidget disappears.

## Decision 2 — The review contract moves to the segment

Supersedes the review *mechanism* of [ADR-0024][adr-0024] §"Output
contract" (the intent — an explicit human review boundary before
anything counts — is unchanged):

- A backend run or an import lands its segments **directly in the
  canonical node**, tagged `● Review`.  The scratch node disappears
  from the UX; whether a hidden landing node survives internally is an
  implementation choice, not a contract.
- **Confirm is per segment**: a scene-persistent per-segment tag
  (beside the SCT terminology tag) records the surgeon's attestation.
  Confirm (✔ / 🔒) supersedes Accept; Discard (✗) supersedes Reject.
- Only **confirmed** segments count downstream: the stage-completion
  predicate becomes *every row Confirmed or Marked-absent* (replacing
  the soft ≥ 1-tagged-segment predicate), and downstream stages that
  today filter on the SCT tag additionally require the confirm tag.
- **Re-running or editing a confirmed row demotes it to `● Review`** —
  the local staleness rule, and the pilot for the shell-wide
  invalidation cascade the phase-contracts ADR must generalise.
- The import path unifies: importing a loaded segmentation populates
  rows (auto-matched by name via the
  `Resources/Terminology/LabelToSCT/` bridges, [ADR-0011][adr-0011];
  unmatched segments get their Structure assigned by an in-row combo),
  and imported segments arrive as `● Review` — imports no longer skip
  the review boundary.

## Decision 3 — A per-structure tool registry

Multi-backend support is **per structure, not global**: backends are
not interchangeable across structures (an interactive grower makes no
sense for the liver capsule; a vessel refiner applies only to
vessels), so a global backend switch would be a mode the surgeon must
remember.

- A registry maps each structure (SCT code) to an **ordered list of
  applicable tool chains, first entry = default**.  Today's entries:
  liver + portal vein via the fast-capable TotalSegmentator `total`
  task, hepatic vein via the combined `liver_vessels` class (pending
  the Kumar-Oram per-vessel refinement), tumors via `liver_tumor`.
- Each registry entry names: the tool wrapper, its task/parameters,
  the output labels + SCT mapping (the LabelToSCT bridge), a
  **modality flag** — `one-shot` (Run → progress → Review) vs
  `interactive` (hands the surgeon to an interaction surface; the row
  shows `✎ Interactive…` until an explicit done) — and a **preferred
  input role** (defaults to PortalVenous; makes a future per-phase
  input choice a data change, not a redesign).
- New backend = new `ToolWrappers/` wrapper + LabelToSCT bridge +
  registry entries.  The GUI grows menu items for free.

## Decision 4 — Macro and micro gestures over one mechanism

- **Macro:** one primary **"Segment anatomy"** button above the table
  runs the default chain for every `○ Missing` row.  The input volume
  is *context* (the Stage-1 role tag via the existing
  `selectInputVolume` contract), never re-picked here.
- **Micro:** each row's ▶ is a split-button whose menu lists that
  row's registry chains ("TotalSegmentator (default)", "Refine with
  Kumar-Oram", …) for re-runs and alternatives.
- Both gestures enqueue into the same job queue (Decision 5), where
  **coalescing** happens: jobs are keyed on `(task, input volume)`, so
  the macro gesture's four rows collapse into two backend invocations
  (liver + portal vein share `total`; vessels + tumors share
  `liver_vessels`), and one process completion fills multiple rows.

## Decision 5 — Background execution: a main-thread QProcess job queue

Inference runs **in the background, sequentially**, via a small
`SegmentationJobQueue` owning one `qt.QProcess` at a time, driven
entirely from the main thread:

- Event-driven, never captive: process stdout arrives via Qt signals
  into the normal event loop; the row's Status cell renders the
  streamed progress; MRML import of results happens in the `finished`
  handler — main-thread by construction, so no marshalling.
- **Sequential by design**: correct on CPU (the backend saturates all
  cores; parallel inferences thrash), and the queue is where
  coalescing (Decision 4) lives.  Cancellation = `kill()` behind the
  running row's ✕; pending jobs can be dropped.  The queue kills its
  child process on module teardown.
- **PythonQt discipline** (the traps the research pass verified):
  string-signature signal connections (including the enum-typed
  `'finished(int,QProcess::ExitStatus)'`) work; keep Python references
  to BOTH the QProcess and its connected slots (garbage collection of
  either silently drops `finished`), and disconnect in the finish
  handler.  The reference implementation is SlicerParallelProcessing
  (see References).
- **Named anti-patterns** (each verified against docs/forums —
  References): Python `threading` touching MRML/Qt/VTK (main-thread
  only; VTK's Python bindings hold the GIL in Slicer builds);
  `multiprocessing` fork under Qt; the blocking
  `readline` + `processEvents` loop (freezes between output lines, no
  cancel, and `processEvents` inside handlers risks re-entrancy —
  the interim implementation that unblocked the walkthrough is
  explicitly the pattern this queue REPLACES); and mixing scripted-CLI
  execution with QProcess (a running scripted CLI can starve QProcess
  `finished()` signals — do not use both mechanisms in this flow).

## Decision 6 — Validate-and-next seam

Stage 2 is the pilot for the user-verified phase-contract paradigm,
without gating on the contracts ADR:

- The module exposes two things through the stage seam: the completion
  **predicate** (every row Confirmed or Marked-absent) and an
  **explain API** returning the unresolved rows.
- The **shell** owns the "Validate and next" button (stage footer).
  The button is always enabled (a disabled button cannot explain
  itself); on a failed validation the module marks the offending rows
  — **red background PLUS the status glyph and a summary line**
  ("2 structures unresolved — confirm or mark absent"), never colour
  alone ([ADR-0010][adr-0010]) — and the marks clear live as rows
  resolve.
- Stage-level locking (validated stage becomes read-only until an
  explicit unlock, with the downstream invalidation cascade) is
  deliberately OUT of this ADR: it is positioning-relevant and belongs
  to the phase-contracts ADR.  This ADR ships the predicate, the
  explain API, and the row marking those need.

## Alternatives considered

### A. Keep the tabs, polish the cards

Rejected: the repetition, the hidden global state, and the
multiplicity mismatch are structural properties of tab-per-structure,
not polish gaps; and Stage 2 would remain the only stage outside the
shell's table-based design language.

### B. Reuse `qMRMLSegmentsTableView`

Slicer's stock segments table gives visibility/colour/name for free,
but cannot host the Source / Status / Confirm / Actions columns that
carry this design's contract.  A custom table (sibling of the Stage-4
resection table, plausibly sharing a base later) is the committed
shape.  The stock view remains available inside the Segment Editor
(the ✎ path).

### C. Scripted-CLI jobs instead of the QProcess queue

Viable: `slicer.cli.run(wait_for_completion=False)` is asynchronous,
carries the XML progress protocol + `Cancel()`, and Slicer serializes
CLIs one-at-a-time (a feature for a sequential queue).  Rejected
because its gifts land in the wrong place (the stock CLI progress
surface, while this design streams progress into table rows), the
parameter plumbing is temp-file duplication of what the wrappers
already do, and the documented scripted-CLI/QProcess signal-starvation
interaction forbids mixing it with the mechanism the rest of the
design uses.

### D. In-process threads

Rejected on evidence: MRML/Qt/VTK access is main-thread-only, VTK's
Python bindings do not release the GIL in Slicer builds (so threads
buy little even for compute), and `multiprocessing` forks crash under
Qt.  See References.

## Consequences

### Easier

- One interaction grammar for AI, import, and manual paths; global
  anatomy state visible at a glance; multifocality has a home;
  completion is explicit and attestable; Stage 2 joins the shell's
  design language; new AI backends become data (registry entries).
- True background inference: the surgeon keeps working while the
  queue runs; batch segmentation costs two backend calls, not four.

### Harder

- `isStageComplete` semantics change (all-resolved vs ≥ 1-tagged):
  the shell predicate, downstream SCT-tag consumers, and the invariant
  tests move with it.
- The scratch/canonical tests and the card tests retire with the tabs;
  the table, registry, queue, and confirm-tag contracts need their own
  invariant suites (test-first, [ADR-0027][adr-0027]).
- The queue's GC/signal discipline is easy to get wrong; conformance
  review must check it (below).

### Conformance

- [test] Pre-seeded rows exist with `○ Missing` before any data; the
  empty state names the goal.
- [test] A completed job lands segments in the canonical node as
  `● Review` with the SCT tag; only Confirm flips the confirm tag;
  Discard removes the segment.
- [test] Completion predicate: all rows Confirmed/Marked-absent ⇒
  complete; any other status ⇒ incomplete, and the explain API names
  the offending rows.
- [test] Re-run/edit of a confirmed row demotes it to `● Review`.
- [test] The registry covers every seeded structure; each entry names
  wrapper, labels, modality, and preferred input role.
- [test] Queue: jobs sharing `(task, input)` coalesce; jobs run one at
  a time; cancel kills the running process; teardown leaves no child
  process.
- [review] QProcess + slot references are held and disconnected per
  the PythonQt discipline; no `processEvents` inside handlers; no
  scripted-CLI use in this flow.
- [future] Stage-level lock/unlock + downstream invalidation — the
  phase-contracts ADR.
- [future] Per-lesion tumor rows (island splitting); per-chain input
  roles for multi-phase cases; Kumar-Oram vessel refinement chain.

## References

- [ADR-0009][adr-0009] — UX and design discipline (explainable state).
- [ADR-0010][adr-0010] — accessibility (never colour alone).
- [ADR-0011][adr-0011] — SCT terminology dispatch + LabelToSCT bridges.
- [ADR-0012][adr-0012] — v2 scope; the 2026-07-09 re-baseline amendment.
- [ADR-0023][adr-0023] — unified GUI stage workflow (the shell design
  language this ADR joins).
- [ADR-0024][adr-0024] — segmentation orchestration (this ADR
  supersedes its review mechanism and tab UI; its lazy-install,
  terminology, and canonical-singleton decisions stand).
- [ADR-0027][adr-0027] — invariant-test-first.
- Slicer Python FAQ, "Running CLI in the background":
  <https://slicer.readthedocs.io/en/latest/developer_guide/python_faq.html>
- SlicerParallelProcessing (the QProcess reference implementation):
  <https://github.com/pieper/SlicerParallelProcessing>
- Discourse: Python multithreading in Slicer (main-thread rules):
  <https://discourse.slicer.org/t/using-python-multithreading-in-3d-slicer/32299>
- Discourse: asynchronous design pattern (QProcess + stdout progress
  endorsement): <https://discourse.slicer.org/t/asynchronous-design-pattern/40159>
- Discourse: scripted CLI starves QProcess `finished()`:
  <https://discourse.slicer.org/t/running-scripted-cli-prevents-qprocess-from-finishing/26534>
- Discourse: concurrent `processEvents` crashes:
  <https://discourse.slicer.org/t/concurrent-calls-to-slicer-app-processevents-crashing-slicer/9970>

[adr-0009]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0009-ux-and-design-discipline.md
[adr-0010]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0010-accessibility-and-i18n.md
[adr-0011]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0011-sct-terminology-dispatch.md
[adr-0012]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0012-layerdm-migration-v2-scope.md
[adr-0023]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0023-unified-gui-stage-workflow.md
[adr-0024]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0024-segmentation-orchestration.md
[adr-0027]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0027-invariant-test-first-v2-implementation.md

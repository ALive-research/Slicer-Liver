# Design plan — VascularTerritories protect-from-edits + validation

- **Status:** Design proposal (no code) — for maintainer decision
- **Date:** 2026-07-30
- **Scope:** VascularTerritories annotation table + carrier
  (`vtkMRMLCustomTerritoriesNode`), the `feature/territory-usability`
  batch, ADR-0037.
- **Maintainer intent (verbatim):** *"editing seeds risks accidental
  changes; today the only protection is hiding the territory … a lock
  icon in the territory … would it make sense to have the same logic as
  for segmentations? with validation of territories?"*

This plan grounds the ask in (a) how core Slicer actually treats
per-segment protection and status, (b) the current territories code and
ADRs, and (c) named UX heuristics, then lands a staged recommendation.
No code is written here.

## 1. What Slicer actually does (verified against 5.8 source)

Verified in `Modules/Loadable/Segmentations/…` of the pinned Slicer
5.8.1 tree.

### 1a. `qMRMLSegmentsTableView` per-segment controls
Columns are visibility (eye toggle), colour swatch, opacity, name, and
an optional **status** column (plus an optional layer column, off by
default). Visibility and status are **single-click cells**; colour and
opacity open editors; name is inline-editable.

### 1b. Per-segment STATUS — real, and the model to mirror
- Stored as a **`vtkSegment` tag `Segmentation.Status`** (machine-readable
  string), read/written via
  `vtkSlicerSegmentationsModuleLogic::{Get,Set}SegmentStatus`.
- Exhaustive enum: **`NotStarted, InProgress, Completed, Flagged`**
  (`LastStatus` sentinel).
- Surfaced as a status column with **icons**
  (`:Icons/{NotStarted,InProgress,Completed,Flagged}.png`),
  **single-click-to-cycle** (`onSegmentsTableClicked`: `++status`
  wrapping at `LastStatus`; `Flagged → Completed`), and **per-status
  filter buttons** (`setStatusShown`).
- The Segment Editor **auto-sets status** when adding a segment
  (`SetSegmentStatus(addedSegment, status)`); editing an existing segment
  drives the `NotStarted → InProgress` progression through the same tag.

### 1c. Is there a per-segment EDIT-LOCK in core Slicer? **No.**
This is the load-bearing finding. There is **no per-segment lock
affordance** anywhere in `vtkSegment`, `vtkSegmentation`, or
`qMRMLSegmentsTableView`. The only "lock" is a **whole-widget**
read-only flag on `qMRMLSegmentEditorWidget` (`d->Locked`) that disables
add/remove and calls `SegmentsTableView->setReadOnly(true)` for the
*entire* segmentation — with a source comment: *"In the future locked
state may be read from the Segmentation node."* i.e. per-segment lock is
explicitly a **not-yet-existing** idea in Slicer.

What actually protects a segment from accidental edits in Slicer is the
**Segment Editor masking model**, not a lock: `vtkMRMLSegmentEditorNode`
carries `MaskMode` / `MaskSegmentID` / `OverwriteMode` and
`EditAllowedInsideSingleSegment` — you edit the *selected* segment, and
masking constrains where paint lands. Protection is a **consequence of
selection + masking**, plus visibility, plus (advisory) status.

**Conclusion for our ask:** "same logic as segmentations" cleanly gives
us **STATUS** (real, click-to-cycle, icon+text) and **validation**
(status == a Completed-like terminal state). A per-territory **LOCK** is
NOT a Slicer segment affordance — it would be **novel**. That does not
forbid it, but it means the honest "just like Slicer" answer is
*status/validation*, and lock is an *addition* we justify on our own UX
grounds (below), not by appeal to Slicer precedent.

## 2. The three orthogonal states (the core model distinction)

The maintainer already spotted the anti-pattern: **hiding a territory is
being overloaded as "protect it."** Visibility, lock, and
validation-status are three **orthogonal** concepts and must not be
collapsed:

| Concept | Question it answers | Slicer precedent | Today in territories |
|---|---|---|---|
| **Visibility** | Is it drawn / pickable? | eye toggle (real) | exists: `SetTerritoryVisibility`; also gates the pick surface (ADR-0037 slice 5) |
| **Lock (edit-protect)** | Can seeds be added/moved/deleted? | **none per-segment** (novel) | absent — no protection except hide |
| **Validation / status** | Has the surgeon signed this territory off as ready? | per-segment status tag (real) | absent — only a *derived* completeness glyph (⚠/Ready) |

Overloading is a **consistency-with-platform-conventions** and
**recognition-over-recall** failure: a Slicer user reads the eye as "show/
hide," never as "protect." Using hide as protection also has a nasty
coupling in *this* module — ADR-0037 slice 5 makes visibility **gate the
pick surface**, so hiding a territory to protect it *also removes its
vessel system from picking for every other territory's placement*. Hide
is doubly wrong as a protection mechanism here. That is the strongest
argument that lock (or status-as-protect) must be its own axis.

### 2a. Should "validated" imply lock, and/or gate compute?
Three sub-decisions, kept explicit:
- **validated ⇒ auto-lock?** A soft coupling is good UX (error
  prevention + reversibility): reaching the terminal status flips an
  edit-guard that a later edit clears, exactly Slicer's *demote-on-edit*
  rule (#574 / ADR-0034 Decision 2). This gives "protect" for free
  without a separate manual lock gesture — the minimalism win.
- **validated ⇒ gate compute?** The completeness glyph already exists and
  the ≥2-seed-per-structure gate already governs extraction (ADR-0037
  slice 5). Making *validation* (a human attestation) additionally
  required to compute is a **positioning-level** change — that is #440
  territory (IEC 62366, ADR-0009). Do **not** couple validation to
  compute-gating in this batch.
- **lock ⇒ refuse edits.** Whatever carries the guard, the interaction
  consequence is uniform: placement (add-on-click into a locked/validated
  territory), drag-edit of its seeds, per-seed delete, and territory
  delete all **refuse** (with an explaining tooltip, never a silent
  no-op).

## 3. Data-model shape (carrier + storage)

`vtkMRMLCustomTerritoriesNode` already carries independent per-territory
display maps (`TerritoryColors`, `TerritoryLabels`, `TerritoryVisibilities`)
each with a `Get/Set…` pair, XML + `.vta.json` round-trip, and a single
`ModifiedEvent` per write (the pattern is settled; ADR-0037 §Decision 3).
A protection/validation flag follows the **same idiom exactly**:

- **Preferred (mirror Slicer's status tag):** one
  `std::map<std::string,int> TerritoryStatuses` keyed on territory id,
  storing the enum ordinal, defaulting to `NotStarted`. Add
  `SetTerritoryStatus(id,int)` / `GetTerritoryStatus(id)->int`,
  `GetStatusTerritoryIds()`, XML attribute + `.vta.json` field, one
  `ModifiedEvent` per write. **Lock is DERIVED** from status (`Completed
  ⇒ locked`), so no separate stored bool — the minimalism choice, and the
  one that stays byte-for-byte parallel to #574.
- **Alternative (explicit lock bool):** add `TerritoryLocked` bool map
  alongside status. Only needed if the maintainer wants lock *independent*
  of validation (lock a still-incomplete territory). Costs a second
  orthogonal flag and a second storage field.

Both keep the geometry map (`AnnotationPoints`) untouched by a
status/lock write (the display-vs-geometry independence ADR-0014 §Fourth
layer requires). Enum values and the machine-readable strings should
**reuse Slicer's own vocabulary** (`NotStarted/InProgress/Completed/
Flagged`) so the territories table and the #574 segments table speak one
language.

## 4. Table UX (icons/columns, a11y)

The territories panel is a single-column, header-less `QTreeWidget` of
composite row strips (ADR-0037 slice-4). The territory strip today is:
Place · eye · colour · label(QLineEdit, stretch) · completeness-status ·
Remove. Additions:

- A **status control** on the territory strip: a `QToolButton` rendered
  as **icon + short text** (ADR-0010 — never colour/icon alone), whose
  click **cycles** the status exactly like Slicer's status cell
  (`NotStarted → InProgress → Completed → Flagged → …`). Reuse Slicer's
  status icons where the resource resolves, glyph fallback otherwise
  (the existing `_applyEyeIcon` pattern).
- The **derived completeness glyph** stays but is **subordinated** to
  status: completeness (⚠/Ready) is a *machine* readiness hint; status is
  the *human* attestation. Keep both, but the row's authoritative state
  is status. (Consider folding the completeness text into the status
  button's tooltip to avoid two competing indicators — a minimalism
  refinement to review.)
- When a territory is **locked** (derived from `Completed`, per §2a), the
  strip shows a **lock glyph + "Locked"** and the Place toggle, colour,
  label edit, seed deletes, and Remove are **disabled** (greyed, with a
  tooltip: "Territory validated — unlock to edit"). Unlock = cycle status
  off `Completed`. This is Slicer's demote-on-edit made explicit.
- a11y: every state is glyph/icon **plus text** and a tooltip; disabled
  controls keep their label so the state is announced, not merely dimmed
  (ADR-0010, and #574's "never colour alone" conformance).

## 5. Interaction consequences (who refuses what)

The lock guard lives on the **carrier status** and is read at the same
seams that already exist:

- **Placement (add-on-click).** `TerritoryPlacementPipeline` appends to
  the *active* territory via the display-node arm state. A locked active
  territory must refuse the append. The clean guard point: the Place
  toggle **cannot arm** into a locked territory (disabled in the strip),
  and the pipeline additionally checks status before `AddAnnotationPoint`
  (defence in depth, since arm state lives on the display node).
- **Drag-edit / pick.** ADR-0037 §Decision 2 makes drag edit the nearest
  point. The pipeline's drag path must consult the point's territory
  status and decline the relocate on a locked territory (leaving the
  hover highlight, like a declined bare move).
- **Per-seed delete & territory Remove.** `deleteSeed` / `deleteTerritory`
  in the table refuse (button disabled) for a locked territory.
- **Already-handled hygiene (do not re-solve):** deleted-territory and
  active-territory disarm hygiene already exist (`deleteTerritory` clears
  arm state; module-active gate on `exit()`). Locking rides on top of
  these, it does not replace them.

## 6. Design options

### Option A — Lock-only binary (no status vocabulary)
A single per-territory `locked` bool + a lock/unlock toggle in the strip;
locked ⇒ all edits refuse. Simplest; directly answers "a lock icon in the
territory."
- **UX:** strong error-prevention, trivially reversible, minimal states.
- **Cost:** small (one bool map + storage + guards).
- **Against:** does **not** match Slicer ("same logic as segmentations"
  is status, not lock), and does **not** give the *validation* the
  maintainer also asked for. Diverges from #574's status language, so the
  two tables feel like two products.
- **ADR:** an ADR-0037 amendment suffices (no positioning change).

### Option B — Slicer-style 4-state status, `Completed ⇒ locked` (recommended core)
Mirror `qMRMLSegmentsTableView`: per-territory status
(`NotStarted/InProgress/Completed/Flagged`) stored on the carrier,
click-to-cycle icon+text cell, **lock derived** from `Completed`, edits
on a `Completed` territory refuse and demote-on-edit clears it.
- **UX:** best consistency-with-platform (a Slicer user recognises the
  status cell instantly), visibility-of-system-status (review state is
  explicit and persistent), error-prevention via the derived lock,
  reversibility via cycle-off, minimalism (one axis buys both protect and
  validate). Matches #574 exactly so the segments table and territories
  table are one product.
- **Cost:** moderate (status map + storage + status cell + guards +
  invariant tests). Reuses the display-map idiom and Slicer's own
  icons/vocabulary.
- **Against:** four states may be more than territories need (do surgeons
  use `Flagged` on a territory?). Mitigation: ship the full enum for
  #574-consistency but the *only load-bearing* transition is
  reach-`Completed`-to-validate/lock; `Flagged` is a defer marker, free
  to carry.
- **ADR:** an ADR-0037 amendment (status/lock is a display-layer
  attribute + interaction guard, not a positioning change). Cross-
  reference ADR-0034's status vocabulary as the shared source of truth.

### Option C — Lock + separate accept/validate contract tied to #440
Per-territory lock as in A, **plus** a distinct human-attestation
"validate" that participates in the shell-wide phase-contract cascade
(invalidation when upstream anatomy changes, DAG unlock, IEC 62366
positioning).
- **UX:** most powerful; a true clinical review contract.
- **Against:** #440 is **v2.1**, **ADR-gated**, with five unresolved
  questions (invalidation cascade, optional-stage DAG, positioning
  re-open, verification fatigue, persistence). Pulling territory
  validation into that contract is a positioning-level move that
  **cannot** ride the current usability batch (violates
  check-milestone-before-dispatching; #440 stays v2.1 per the 2026-07-09
  re-baseline note).
- **ADR:** requires the #440 ADR, not an amendment. Out of scope for this
  batch.

## 7. Recommendation + staging

**Adopt Option B**, staged so the usability batch ships the protection
the maintainer needs *now* without straying into #440's positioning
change.

- **Ship in the current `feature/territory-usability` batch:**
  1. Carrier `TerritoryStatuses` map (enum reusing Slicer's
     `NotStarted/InProgress/Completed/Flagged`) with XML + `.vta.json`
     round-trip and one `ModifiedEvent` per write — test-first, mirroring
     the existing display-map tests (ADR-0027).
  2. Status cell on the territory strip: click-to-cycle, icon **+** text,
     Slicer status icons with glyph fallback (ADR-0010).
  3. **Derived lock** (`Completed ⇒ locked`): disable Place-arm, colour,
     label, seed-delete, territory-Remove on a locked territory, each with
     an explaining tooltip; pipeline placement/drag guards as defence in
     depth. **Demote-on-edit** clears `Completed → InProgress` (the #574
     staleness rule, locally scoped to this territory).
  4. Invariant tests: cycle order; `Completed` refuses each edit path;
     demote-on-edit; storage round-trip; visibility remains independent of
     lock (the anti-overload pin).

- **Explicitly defer to v2.1 / #440 (do NOT build now):**
  - Coupling validation to **compute-gating** (extraction already gates
    on ≥2 seeds/structure; making human validation a compute
    precondition is positioning-level).
  - Any **cross-stage invalidation cascade** (upstream anatomy change
    demoting a validated territory) — that is #440's dependency-tracking
    question, not a per-territory local rule.
  - A separate `Flagged`-driven senior-review workflow.

- **Consistency with #574 (make the two tables one product):** reuse the
  **same status enum, the same machine-readable strings, and the same
  icons** as `qMRMLSegmentsTableView` / ADR-0034. Where practical, factor
  the status-cell rendering (icon+text+cycle) into a shared helper so the
  segments table and the territories tree render status identically. The
  demote-on-edit rule should read the same in both ADRs.

**Why not A:** it answers "lock icon" literally but abandons the
"validation … same as segmentations" half and drifts from #574's
language. **Why not C now:** it is v2.1, ADR-gated, positioning-level.

## 8. ADR impact

- **ADR-0037 amendment** (new): "Per-territory status + derived edit-lock,"
  recording the carrier status slot, the click-to-cycle status cell, the
  `Completed ⇒ locked` derivation, the edit-refusal seams, and
  demote-on-edit. New ADRs are authored `Status: Accepted` (repo
  convention). Cross-reference ADR-0034 as the status-vocabulary source
  and ADR-0010 for the icon+text rule.
- **No conflict** with ADR-0013 (no custom DM — guards live on the
  carrier + existing Pipeline seam), ADR-0014 (status is a display-layer
  attribute, geometry untouched), or ADR-0004 (the cell is Python-widget
  composition).
- **Boundary flag:** compute-gating and cross-stage invalidation belong to
  **#440 (v2.1, ADR-gated)** and must not be pulled into this amendment.

## 9. Open questions for the maintainer (each with a default)

1. **Lock derived from status, or an independent lock bool?**
   *Default: derived (`Completed ⇒ locked`), Option B* — minimal, matches
   Slicer's demote-on-edit. Choose independent only if you want to lock an
   incomplete territory.
2. **Full 4-state enum, or a 2-state (`Draft/Validated`) subset?**
   *Default: full enum reusing Slicer's* — costs nothing extra and keeps
   the territories and #574 segment tables identical. `Flagged` rides
   along as a defer marker.
3. **Does reaching the status also gate Extract/Compute?**
   *Default: no* — extraction keeps its existing ≥2-seed gate; validation-
   as-compute-gate is #440 positioning-level. Revisit in v2.1.
4. **Keep the derived completeness glyph AND the status cell, or fold
   completeness into the status tooltip?**
   *Default: fold completeness into the status button tooltip* — one
   authoritative row indicator (minimalism); revisit if surgeons want both
   visible.
5. **Should demote-on-edit fire on any edit, or only on geometry edits
   (add/move/delete seed), not on colour/label?**
   *Default: geometry edits only* — colour/label are cosmetic and should
   not invalidate a surgeon's sign-off.

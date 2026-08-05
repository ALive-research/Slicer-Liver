# CRITIC review — LiverVolumetry workflow consistency

- **Status:** Design critique + alignment proposal (no code) — for maintainer decision
- **Date:** 2026-07-30
- **Scope:** `LiverVolumetry/LiverVolumetry.py`, `LiverVolumetryLib/VolumetrySeedsTableWidget.py`,
  `Resources/UI/LiverVolumetryWidget.ui`, `MRML/vtkMRMLVolumetrySeedsNode.h`; judged against
  `VascularTerritories/` (`VascularTerritories.py`, `VascularTerritoriesLib/TerritoriesTableWidget.py`,
  `Docs/design/territory-protection-validation-plan.md`) and the Slicer Segmentations paradigm
  (`qMRMLSegmentsTableView`, Segment Editor).
- **Maintainer intent (verbatim):** *"the volume [volumetry] workflow should not be very different
  from segmentation, vascular territories."*

This grounds the ask in (a) what Slicer's Segmentations module actually does, (b) the in-project
VascularTerritories pattern that volumetry should feel like, and (c) named UX heuristics, then lands
a staged recommendation. No code is written here.

## 1. What the three workflows actually do today

### 1a. Slicer Segmentations paradigm (verified against 5.8.1 source)
`qMRMLSegmentsTableView` (`Modules/Loadable/Segmentations/Widgets/`) exposes five toggleable
columns: **visibility (eye), colour swatch, opacity, name (inline-edit), status** (+ an optional
layer column). Status is a real per-segment tag `Segmentation.Status` with the enum
`NotStarted / InProgress / Completed / Flagged`, surfaced as a **single-click-to-cycle icon cell**;
the Segment Editor auto-sets it on add and demotes-on-edit. The arm/place model: you **Add** a
segment (it becomes the *active/selected* row), then an **effect** (Paint, Draw, region-growing
seeds) becomes active and clicks land in the selected segment. Selection + masking is what protects
a segment — there is **no per-segment lock** in core Slicer.

### 1b. VascularTerritories (the in-project sibling to match — ADR-0037)
Choreography: **input → (per-territory) Place → seed placement → Extract centerlines → Compute map**.
The panel (`TerritoriesTableWidget`) is a Python-composed single-column tree of composite row strips:
per-territory **Place toggle · eye visibility · colour swatch · editable label · completeness status
(glyph+text) · Remove**; seed children carry a **structure swatch+name · Delete**. It has an
input-structures `qMRMLSegmentsTableView`, per-territory + per-seed delete, and — freshly added —
an **affirmative always-visible requirements line** (`_setupRequirementsLabel` /
`_actionRequirements` / `_updateRequirementsMessage`) that enumerates unmet preconditions live and
mirrors them into both action tooltips. Placement arms **exclusively** into the active territory via
state on the shared display node. An incoming plan (`territory-protection-validation-plan.md`) adds a
per-territory **status/lock** cell reusing Slicer's status vocabulary.

### 1c. LiverVolumetry (the subject — ADR-0038 amendment)
Choreography: **input (segmentation + reference volume + segments) → Add region-growing seeds
(toggle) → Compute (Calculate Volume / Generate segments)**. Placement is a single panel-level
`AddSeedsButton` toggle (`onAddSeedsToggled`) arming interior seed placement onto one flat
`vtkMRMLVolumetrySeedsNode` carrier. The `VolumetrySeedsTableWidget` is a flat `QTableWidget` with
**three columns: Colour swatch · Label (editable) · Delete**. The carrier stores Seeds / SeedLabels /
SeedColors — colour + label parity with territories, but **no per-seed visibility and no status**.
Enablement is a bare boolean AND of node selectors (`onVolumetryParameterChanged`); there is **no
requirements/what's-missing surface** anywhere in the module. `Compute` is non-blocking (wait cursor
+ populated table) — that part is already aligned with ADR-0009.

The good news: volumetry already got the hard architectural half right — carrier-is-model table,
colour+label parity, per-seed delete, display-node arm state, ADR-0004 Python panel, graceful
degradation, teardown hygiene. The gaps are UX-surface, not structural.

## 2. Prioritized divergence critique

| # | Divergence (volumetry vs territories/segments) | UX principle violated | Severity | Concrete fix |
|---|---|---|---|---|
| D1 | **No affirmative "what's missing" surface.** Territories now has an always-visible requirements line + action tooltips enumerating unmet preconditions; volumetry's Compute/Generate buttons just sit disabled with no explanation. | Visibility of system status; error prevention; recognition-over-recall | **Blocking** | Add `_setupRequirementsLabel` + `_actionRequirements` + `_updateRequirementsMessage` mirroring territories verbatim. Unmet list for Compute: no reference volume / no segmentation / no segment / no seeds; feed the same strings into both button tooltips. |
| D2 | **Arm affordance wording + model diverge.** One panel-level "Add region-growing seeds" toggle vs territories' per-row exclusive **Place** toggle; the word "seeds" also collides with the *region-growing* seed metaphor without the segment-selection framing Slicer uses. | Consistency with conventions; recognition-over-recall | **Should-fix** | Volumetry seeds are a single flat list (no grouping), so a per-row Place toggle would be a fake hierarchy — keep ONE toggle, but rename to the territory idiom **"Place seeds"** and pair it with the requirements line so its disabled/enabled state self-explains. Mark its armed state visibly (checked + status text), matching the Place-toggle cue. |
| D3 | **No whole-group ("clear all seeds") delete.** Territories has per-seed Delete AND per-territory Remove (removes an empty group too). Volumetry has only per-seed Delete — no way to clear the set in one gesture. | Consistency; user control/efficiency | **Should-fix** | Add a "Clear all seeds" button beside the table (carrier `RemoveNthSeed` loop or a `RemoveAllSeeds` carrier method), the flat-list analogue of territory Remove. |
| D4 | **No status/validation cell.** Segments have a real status column; the territory-protection plan is adding per-group status/lock. Volumetry seeds carry no status and no protect-from-edits. | Consistency with conventions; error prevention | **Nice-to-have (defer)** | Do NOT build a per-seed status now — a single interior region-growing seed is not a signed-off clinical artifact the way a segment/territory is. Keep the axis open by reusing the shared status-cell helper the territory plan proposes IF a per-seed-group notion emerges. See OPEN QUESTION 1. |
| D5 | **No per-seed visibility column — but this is correct.** Segments/territories have an eye toggle; the flat carrier + data-only display node expose only one shared `Visibility`. The table already omits (not fakes) the eye column and documents why. | (none — correct restraint) | **Not a defect** | Leave omitted; the "no colour of the sky" discipline is correctly applied. Revisit only if the carrier grows a per-seed visibility slot. |
| D6 | **Table columns headerful vs territories' header-less composite strips.** Volumetry uses a classic 3-column `QTableWidget` with a header row ("Colour / Label / ""); territories dropped the grid+header for composite row strips. | Consistency (minor) | **Nice-to-have** | Acceptable divergence — the flat list genuinely fits a plain table (the widget docstring argues this correctly). Optionally hide the empty third header label. Do not force the tree idiom onto a flat list. |
| D7 | **Label column lacks the structure-swatch cue territory seed rows carry.** Territory seed rows tint with the structure colour + name (colour-never-alone). Volumetry rows have a per-seed colour swatch the *user* sets, which is arguably clearer — but the placeholder "Seed N label" is generic. | Recognition-over-recall (minor) | **Nice-to-have** | Keep the user-colour swatch (it drives the generated segment colour — load-bearing). Improve the empty-label affordance: default each new seed's label to "Segment N" so the generated-segment naming is never blank. |
| D8 | **Terminology drift across the two modules.** Volumetry: "Add region-growing seeds", "Calculate Volume", "Generate segments based on selected resections and region-growing seeds" (a full sentence on a button). Territories: "Place", "Extract centerlines", "Compute territory map". | Consistency; minimalism | **Should-fix** | Normalise verbs: **"Place seeds"** (arm), **"Compute volumes"** (was Calculate Volume), **"Generate segments"** (drop the sentence — move the detail to the tooltip). One verb family across modules. |

## 3. Alignment design — the target volumetry workflow

A Slicer user who knows Segmentations/Territories should recognise this instantly:

**Choreography (unchanged order, aligned labels):** input (segmentation + reference volume +
segments) → **Place seeds** (armed toggle, requirements-gated) → seed table grows → **Compute
volumes** / **Generate segments**. This is the two/three-step territory rhythm minus Extract
(volumetry has no centerline step — a legitimate, coherent shortening, not a divergence).

**Panel, top to bottom:**
1. Input selectors (unchanged).
2. **Place seeds** toggle (renamed; armed-state visible).
3. **Seeds table** — flat `QTableWidget`, one row per seed: **Colour swatch · Label · Delete**
   (unchanged columns) + a **"Clear all seeds"** button beneath it (D3).
4. **Requirements line** (D1) — always-visible, enumerates unmet preconditions; mirrored into the
   Compute + Generate tooltips. "All requirements met — place seeds, then compute volumes."
5. **Compute volumes** / **Generate segments** buttons (D8 labels).

**Terminology resolved:** Add region-growing seeds → **Place seeds**; Calculate Volume →
**Compute volumes**; the sentence-button → **Generate segments** (detail to tooltip).

**Delete parity:** per-seed Delete (exists) + **Clear all seeds** (new) = the territory
per-seed/per-group pair, adapted to a flat list.

**Status/lock:** NOT extended to per-seed volumetry now (D4). If a "seed set" grouping ever emerges,
adopt the **shared status-cell helper** the territory plan proposes (§4/§7 of that plan) so all three
tables render status identically — but that is out of scope for the eyeball-usability batch.

**a11y (ADR-0010):** the requirements line is legible plain text (never colour alone); the delete/
clear buttons keep text+tooltip; colour swatch stays paired with the label — all already satisfied or
carried by the fixes above.

## 4. Staged recommendation

**Ship now (eyeball-usability batch — pure Python panel work, no MRML/ADR change):**
- D1 requirements line + action tooltips (port territories' `_actionRequirements` idiom). *Highest value.*
- D8 label normalisation (Place seeds / Compute volumes / Generate segments).
- D3 "Clear all seeds".
- D2 armed-state visibility on the single toggle; D7 default seed label.

**Follow-up (small, still no positioning change):**
- D6 header polish; factor the requirements-line helper into a shared module so territories +
  volumetry (and future planning table) share one implementation.

**Defer (v2.1 / ADR-gated):**
- D4 per-seed(-group) status/lock — only if a grouping notion appears; then reuse the territory
  plan's shared status helper and Slicer's status vocabulary. Do not couple any validation to
  compute-gating (that is #440 positioning territory, IEC 62366 — see the territory plan §2a/§6C).

## 5. ADR impact

- **ADR-0009 (UX discipline):** the requirements surface + non-blocking feedback are exactly this
  ADR's concern; D1 brings volumetry into conformance. No amendment needed — it is applying the ADR.
- **ADR-0010 (a11y/i18n):** the new requirements line and normalised labels must be legible
  text + tooltip; already the standing rule. No amendment.
- **ADR-0038 (unify control-point interaction / seeds-off-markups):** the label + Clear-all + toggle
  wording are panel-surface refinements consistent with §Conformance (labels become generated segment
  names). A one-line §Conformance note ("panel mirrors the VascularTerritories requirements-surface +
  delete-parity idiom") is optional, not required.
- **#574 (segment status) / ADR-0034:** relevant ONLY to the deferred D4. If per-seed-group status is
  ever built, it MUST reuse #574's status enum, strings, and icons via the shared helper the territory
  plan proposes — one status language across all three tables.
- **No conflict** with ADR-0013 (no custom DM — all fixes are panel-side), ADR-0014 (no geometry
  touched), or ADR-0004 (Python panel composition).

## 6. OPEN QUESTIONS (each with a default)

1. **Do volumetry seeds ever need status/lock like territories/segments?**
   *Default: NO for v2.0.* A region-growing seed is a transient computation input, not a signed-off
   clinical artifact; status/lock is meaningful for segments and territories because those ARE the
   deliverable. Revisit only if seeds gain a persistent "set" identity.
2. **Keep ONE panel-level Place toggle, or move it into the table like territories' per-row Place?**
   *Default: keep ONE toggle.* The flat seed list has no grouping, so a per-row Place would fabricate
   a hierarchy that does not exist — the table docstring already argues the flat-list case correctly.
   Match territories in *wording and armed-state cue*, not in structure.
3. **Should "Clear all seeds" confirm before wiping?**
   *Default: no modal for ≤ a handful of seeds; rely on reversibility via re-placement.* Add a
   confirm only if seed sets grow large (consistent with Slicer's low-friction delete).
4. **Fold the "region-growing" qualifier out of the button, or keep it for clarity?**
   *Default: drop from the button label ("Place seeds"), keep "region-growing" in the tooltip* — the
   verb family stays consistent with territories while the tooltip preserves the domain meaning.

---
*Grounded in: `qMRMLSegmentsTableView.h` (5.8.1) column set + status enum; `TerritoriesTableWidget.py`
+ `VascularTerritories.py` (`_setupRequirementsLabel` / `_actionRequirements`); `VolumetrySeedsTableWidget.py`
+ `LiverVolumetryWidget.ui` + `vtkMRMLVolumetrySeedsNode.h`; `territory-protection-validation-plan.md`.*

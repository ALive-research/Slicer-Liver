# 0009. UX and design discipline

- **Status:** Accepted
- **Date:** 2026-05-15
- **Deciders:** Rafael Palomar
- **Diagrams:** N/A (this ADR establishes the requirement for per-module
  GUI diagrams under `Docs/architecture/ui/`; the diagrams themselves
  land with the PRs that touch the corresponding UI)
- **PR:** _filled in on merge_

## Context

Slicer-Liver is surgical-planning software used by clinicians.  Its
user interface is not cosmetic surface: a misleading state transition
or an ambiguous control on a resection editor is safety-relevant, not
merely inconvenient.  v2.0.0 — the LayerDM migration tracked by
ADR-0002 — touches substantial UI surface across resection editing,
the resectogram side panel, segmentation, and volumetry.  Whatever
interaction patterns ship with v2.0.0 set the precedent for the
post-migration project.

Today, UX rationale is implicit.  Design choices are visible only in
commit messages and informal discussion; there is no review-blocking
artifact that captures *why* a widget behaves the way it does, no
canonical workflow diagrams kept current, no declared methodology
behind UI decisions.  ADR-0003 establishes a testability invariant for
behaviour; nothing comparable exists for interaction design.

The medical-device usability literature provides useful reference
material — **IEC 62366-1:2015** (usability engineering for medical
devices) and **ISO 9241-210:2019** (human-centred design for
interactive systems).  Slicer-Liver is not currently certified as a
medical device and this ADR does not require formal adherence to
these standards.  They are listed as references that authors and
reviewers may consult.

The v2.0.0 cutover is the right moment to fix this — before the
migration locks in patterns by precedent and before retrofitting
methodology requires unwinding shipped interactions.

## Decision

UX and design discipline becomes a first-class, review-blocking
concern for any PR that touches user-facing behaviour.  Concretely:

### 1. Interface diagrams (Mermaid, in-repo)

Any new or modified interactive widget requires a Mermaid state-machine
diagram committed under `Docs/architecture/ui/<module>.md`.  The
diagram captures: states, transitions, user actions that drive
transitions, and which UI elements are visible/enabled per state.  The
source of truth is in version control.  Figma or other design tools
may be used for mocks; the architectural record stays in the
repository.

### 2. Workflow diagrams per module

Each module with an end-to-end user flow — `LiverResections`,
`LiverSegments`, `LiverVolumetry`, `Liver` — carries one canonical
workflow diagram, kept current as PRs land.  A workflow diagram that
no longer matches the implementation is a review-blocker on the next
PR that touches the module.

### 3. Design rationale per UI-touching PR

The pull-request description explains the design choice and justifies
the pick.  Required content:

- *What* the user-facing change does.
- *Why* this approach was chosen over the alternatives the author
  considered.
- A screenshot or mock of the affected widget, where applicable.

Authors may — but are not required to — draw on established usability
methodology to inform the rationale.  Methodologies that can serve as
a guide:

- Heuristic evaluation against Nielsen's 10 usability heuristics.
- Cognitive walkthrough.
- Contextual inquiry (surgeon shadowing, interview transcripts).
- Wizard-of-Oz prototyping (paper or low-fi).
- Comparative analysis against established surgical-planning tools.

These are references, not gates.  A PR that documents a clear written
rationale without naming a methodology is acceptable.  What is *not*
acceptable is a PR whose rationale is opaque to a future reader.

### 4. Medical-device usability — for reference

The medical-device usability literature is a useful reference even
though Slicer-Liver does not currently pursue medical-device
certification.  Authors and reviewers may consult:

- **IEC 62366-1:2015** — application of usability engineering to
  medical devices.
- **ISO 9241-210:2019** — human-centred design for interactive
  systems.

This ADR does not require adherence to these standards.  It records
that they exist and that informal alignment with their guidance is
encouraged when it costs little.  A future ADR can revisit the
adherence question if the project's regulatory posture changes.

### 5. PR template addition

The pull-request template grows a `## UX impact` section.  For any
UI-touching PR the section is non-empty and contains:

- The state-machine diff (link to updated diagram or inline summary).
- A short design rationale (per §3).
- A screenshot or mock of the affected widget.

For non-UI PRs the section reads `N/A — non-UI change`.  Reviewers
reject PRs that leave the section blank.

### 6. Cross-references

- **Accessibility and internationalisation** are scoped to ADR-0010
  (in flight).  This ADR commits the methodology gate; ADR-0010
  commits the specific accessibility / i18n stance.
- **Terminology-dispatched UIs** (SCT-driven combo-box elimination,
  tracked by ADR-0011 in flight) are an example of a UX simplification
  driven by data-model decisions.  The methodology gate here covers
  the *interaction* side of that simplification; ADR-0011 covers the
  *data-model* side.

## Alternatives considered

### Alternative A — Status quo (implicit UX in PR descriptions)

Leave UX rationale to commit messages and informal discussion, as
today.

**Rejected** because the rationale is invisible to future contributors
and to agentic reviewers (`/slicer-review` reads ADRs, not commit
chatter).  Without a review-blocking artifact, methodology lapses are
silent.  The v2.0.0 migration would lock in undocumented choices that
later contributors would have to reverse-engineer.

### Alternative B — External design tool as source of truth (Figma)

Maintain interaction diagrams and workflow maps in Figma; link from
the repo.

**Rejected** for architectural artifacts.  Figma is excellent for
mocks but couples the architectural record to an external service,
breaks diff-review, and is invisible to text-based agentic review.
Mermaid renders natively on GitHub, diffs cleanly, and lives with the
code it describes.  Figma remains available for mocks linked *from*
the in-repo diagram.

### Alternative C — Defer the discipline to v2.1.0

Land the v2.0.0 LayerDM migration first, then add the methodology
gate.

**Rejected** because the migration is exactly when the discipline
matters most.  Patterns set by precedent during v2.0.0 become the
default for v2.1.0 onward; deferring the gate means the first
discipline-compliant PR is fighting against months of
discipline-free precedent.

### Alternative D — Lightweight checklist with no written rationale

Replace §3 with a tick-box checklist ("considered usability: yes/no")
without requiring a written rationale or interface diagrams.

**Rejected** because the checklist removes the in-repo design record
that §1, §2, and §3 together establish.  The chosen approach already
treats methodology citation as reference rather than gate; removing
the written rationale on top of that would leave no durable artifact
of *why* a UI behaves as it does, which is the failure mode this ADR
exists to fix.

## Consequences

### Easier

- **Design rationale is durable and in-repo.**  A future contributor
  (human or agentic) can read why a UI looks the way it does without
  spelunking commit history.
- **Reviewers have a concrete artifact to evaluate against.**  The
  state-machine diagram and written rationale give the review a
  shared object, not a vibe.
- **References to IEC 62366-1 and ISO 9241-210 are recorded** so that
  if Slicer-Liver later pursues formal usability engineering, the
  pointer is already in the project's decision record.
- **Workflow diagrams stay current** because they're review-blocked.
  Stale architecture documentation — the usual failure mode — is
  caught at the next UI-touching PR.

### Harder

- **~10–20 minutes additional work per UI-touching PR** for diagram
  diff + written rationale.  Bounded; smaller than a citation
  requirement would impose.
- **Written rationale risks becoming shallow.**  Mitigation: reviewers
  expect a real *why*, not a restatement of *what*.  No structural
  enforcement beyond reviewer judgement — this ADR deliberately
  trades a stricter gate for lower per-PR friction.
- **Mermaid becomes a soft documentation dependency.**  GitHub renders
  it natively; offline readers need a Mermaid-aware viewer.  Cost
  judged acceptable.
- **The PR template grows.**  Slightly longer template; reviewers must
  enforce the new section.

## Open questions

Not blocking adoption:

- Where to put style/palette consistency rules (here, in ADR-0010, or
  per-module).  Leaning toward a follow-up ADR after the first LayerDM
  module migration, when the concrete style decisions are visible.
- Whether to require usability-test sessions with surgeons before
  release.  Deferred; capture as a v2.1.0 candidate.

## References

- **IEC 62366-1:2015** — Medical devices — Part 1: Application of
  usability engineering to medical devices.
- **ISO 9241-210:2019** — Ergonomics of human-system interaction —
  Part 210: Human-centred design for interactive systems.
- Nielsen, J. (1994). *10 Usability Heuristics for User Interface
  Design.* Nielsen Norman Group.
- [ADR-0002](0002-migrate-to-slicerlayerdm.md) — the LayerDM
  migration that motivates landing this discipline at v2.0.0.
- [ADR-0003](0003-testability-invariant.md) — the analogous
  review-blocking invariant for behaviour; this ADR is its UX
  counterpart.
- [ADR-0007](0007-version-numbering-policy.md) — version policy under
  which UI workflow changes are MINOR-bump material with release notes.
- [ADR-0008](0008-testing-strategy.md) — workflow-layer tests are
  where the state-machine diagrams of §1 get exercised in CI.
- ADR-0010 (in flight) — accessibility and internationalisation.
- ADR-0011 (in flight) — SCT terminology dispatch and combo-box
  elimination.

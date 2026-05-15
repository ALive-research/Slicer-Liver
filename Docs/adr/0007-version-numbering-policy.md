# 0007. Version-numbering policy

- **Status:** Proposed
- **Date:** 2026-05-15
- **Deciders:** Rafael Palomar
- **Diagrams:** N/A
- **PR:** _filled in on merge_

## Context

Slicer-Liver is currently at `v1.1.0`, with the v2.0.0 SLDM migration
(see ADR-0002) in active design.  The numbers themselves look
SemVer-shaped, but the project has no documented criterion for what
triggers each digit.  In retrospect the implicit rule has been "major
bump when several compatibility surfaces break at once" — sufficient
for the v1 → v2 jump, but vague going forward and hard to apply
consistently across PRs.

A Slicer extension has **five distinct compatibility surfaces** that
upstream consumers (clinicians, downstream extensions, the Slicer
runtime) can break against:

1. **Data format** — `.lrp.fcsv` files persisted by clinicians.  These
   are the most sacred contract; a clinician opening a saved scene from
   a prior version must get the same resection back.
2. **Slicer platform** — the minimum required Slicer version.  A bump
   here means users must upgrade Slicer before installing the new
   release.
3. **Required external extension versions** — LayerDM (per ADR-0002),
   SlicerVMTK, SegmentEditorExtraEffects.  A bump means users must
   upgrade those before installing the new release.
4. **MRML node class names / scene-XML structure** — affects scene
   reload from older versions; affects downstream extensions that
   query the Slicer-Liver MRML hierarchy.
5. **User-visible workflow / UI conventions** — surgeons retraining;
   release-noted but otherwise non-breaking.

A sixth surface — **public C++ API of Loadable modules** — exists in
principle (downstream extensions could depend on
`vtkMRMLLiverResectionNode`, `vtkSlicerLiverResectionsLogic`) but in
practice has no known downstream consumers, so its weight is low.

The policy below assigns each digit explicit triggers across these
surfaces.

## Decision

Slicer-Liver follows **[Semantic Versioning 2.0.0](https://semver.org/)**:
`MAJOR.MINOR.PATCH`, git-tagged as `vMAJOR.MINOR.PATCH` (e.g.
`v2.0.0`).

### MAJOR bump triggers

A MAJOR bump is required when **any one** of the following changes:

- **(D) Data format**: `.lrp.fcsv` files saved by a prior MAJOR no
  longer round-trip cleanly (load → no-op edit → save produces a
  different byte stream that is no longer loadable by the prior MAJOR,
  *or* produces a clinically different resection).  Backward-compatible
  read of older formats is permitted under MINOR; symmetric round-trip
  break is MAJOR.
- **(S) Slicer platform minimum**: the minimum required Slicer version
  bumps.  Even a Slicer-PATCH bump is MAJOR for us if it requires user
  action.
- **(E) Required external extension minimum**: the minimum required
  version of LayerDM, SlicerVMTK, or any other listed dependency bumps
  in a way that requires user action.
- **(N) MRML node hierarchy / scene-XML structure**: an MRML node
  class is renamed, removed, or has its serialization layout change in
  a way that breaks scene reload from a prior MAJOR.  Adding new node
  classes does not trigger MAJOR (those are MINOR); breaking the
  existing ones does.

UI workflow changes (compatibility surface 5) and internal C++ API
changes (surface 6) do **not** trigger MAJOR on their own.  They are
prominently release-noted under MINOR.

### MINOR bump triggers

A MINOR bump applies for backward-compatible additions:

- New modules, new workflows, new commands, new SCT terminology
  entries (per ADR-0001 / 2026-05-14 stitch design).
- New optional dependencies (not required-min bumps).
- New algorithm features alongside existing ones.
- User-visible workflow changes that don't break existing scenes (e.g.
  the v2.0.0 SLDM-driven resectogram side panel).
- Internal C++ API additions (not removals or signature changes on
  consumed methods).
- Performance improvements with no behavioural change beyond speed.

### PATCH bump triggers

A PATCH bump applies for backward-compatible fixes:

- Bug fixes that don't change documented behaviour.
- Documentation-only changes.
- Build-system / CI changes (per ADR-0005).
- Internal refactors that are user-invisible and don't move the C++
  API or MRML hierarchy.

### Pre-release suffixes

**Not used.**  No `-alpha`, `-beta`, or `-rc` tags.  Multi-PR
migrations (e.g. the v2.0.0 SLDM phased migration per ADR-0002) live
on feature branches with internal CI; testers run from the branch SHA.
Only `vMAJOR.MINOR.PATCH` git tags exist on `main` (per ADR-0006).

### Cadence

**Feature-driven.**  Releases are cut when meaningful work lands
(typically: an ADR completes, a migration phase merges, a coherent
feature ships).  No calendar floor; no minimum release frequency.

### Mapping the v1 → v2 jump

For the record, the v2.0.0 milestone is justified across **four** of
the four MAJOR triggers above:

- (D) `.lrp.fcsv` format changes (three-node assembly → single content
  node per ADR-0002).
- (S) Slicer 5.10+ required (LayerDM availability).
- (E) LayerDM becomes a required dependency.
- (N) `vtkMRMLLiverResectionNode` collapses the three-node assembly;
  multiple new node classes (`vtkMRMLLiverResectionDisplayNode`,
  `vtkMRMLLiverVolumetryNode`, `vtkMRMLLiverResectogramDisplayNode`,
  etc.).

## Alternatives considered

### A. CalVer (YYYY.MM[.micro])

Calendar-based versioning where compatibility is implied rather than
encoded in the digits.  Used by Pandas, Black, Ubuntu LTS.

**Rejected** because the most useful question Slicer-Liver consumers
ask — "is this safe to upgrade?" — has a SemVer-encoded answer and no
CalVer-encoded answer.  CalVer fits projects where release timing
matters more than compatibility signalling; Slicer-Liver's audience
(clinicians + downstream extensions) cares about the latter.

### B. Hybrid CalVer + SemVer suffix (e.g. 2026.2.0)

Calendar year + within-year SemVer.

**Rejected** as unnecessarily complex.  The year of release is already
in the git tag's commit date; encoding it in the number costs
discoverability without paying for anything the existing log doesn't
already give.

### C. Strict SemVer — any compatibility surface = MAJOR

Treat *any* of the five surfaces (including UI workflow and internal
C++ API) as MAJOR triggers.

**Rejected** because it would force a MAJOR bump for every UI rework
or internal API tidy, drowning consumers in low-information MAJORs.
The current policy treats persistence + platform as the contract;
internal/UI churn lives at MINOR with release notes.

### D. Permissive SemVer — only data-format breaks trigger MAJOR

Treat the saved file format as the only sacred contract; everything
else (Slicer platform bumps, required dep bumps, MRML structure) rolls
into MINOR.

**Rejected** because Slicer platform bumps and required extension
bumps materially affect users — installing a MINOR version should not
require the user to first upgrade Slicer or another extension.  Those
deserve a MAJOR signal.

### E. Pre-release suffixes (alpha / beta / rc) per SemVer convention

Tag intermediate states during the v2.0.0 migration as
`v2.0.0-alpha.1`, `v2.0.0-beta.1`, `v2.0.0-rc.1` before the final
`v2.0.0`.

**Rejected** because it inflates the tag surface for no testing
benefit beyond what feature-branch CI already provides.  Testers
willing to run pre-release code are equally willing to run a feature
branch SHA; clinicians waiting for a stable release are equally
unwilling to install `-alpha`.

### F. Time-based cadence (quarterly)

Cut releases on a fixed calendar.

**Rejected** because it forces releases even when no meaningful work
has landed, and ties release timing to the calendar rather than to the
work itself.

## Consequences

### Easier

- **Each PR has a deterministic version impact.**  A reviewer can ask:
  does this break D, S, E, or N?  Yes → MAJOR.  Does it add a feature?
  → MINOR.  Bug fix? → PATCH.
- **Release-noting is structured.**  Each release has a categorised
  changelog mapping each commit to one of the trigger categories.
- **Downstream consumers can plan upgrades.**  "MAJOR" means "I must
  read the migration guide before upgrading"; "MINOR" / "PATCH" means
  "drop-in safe".
- **Clinical users get a strong signal.**  Saved scenes from MAJOR N
  are guaranteed loadable on MAJOR N (modulo bugs); scenes from MAJOR
  N-1 may need migration on N.

### Harder

- **Every PR must classify its compatibility surface.**  A reviewer
  checklist (likely under ADR-0003's testability invariant) needs to
  add "version bump justification" alongside "test that pins the
  behaviour".
- **MAJOR migrations require a migration guide.**  Each MAJOR bump
  (v1 → v2, v2 → v3) ships with a documented user-facing migration
  path for `.lrp.fcsv` files and any other broken contracts.
- **MRML node hierarchy is now a versioned contract.**  Renaming a
  node class — even internally — has version implications.  The C++
  policy (ADR-0004, data-only nodes) makes this contract small and
  visible; the MRML class names listed in ADR-0001 and ADR-0002
  become the contractually stable surface.

## References

- [Semantic Versioning 2.0.0](https://semver.org/) — the upstream spec.
- [ADR-0001](0001-resection-three-node-assembly.md) — defines the
  current MRML node hierarchy (the (N) contract surface).
- [ADR-0002](0002-migrate-to-slicerlayerdm.md) — defines the v2.0.0
  SLDM migration that motivates the v1 → v2 bump; the migration plan's
  module ordering aligns naturally with the feature-driven cadence
  here.
- [ADR-0003](0003-testability-invariant.md) — the testability rule
  that makes feature-driven cadence safe (every PR is testable, every
  release is meaningful).
- [ADR-0004](0004-python-cpp-boundary.md) — defines the small,
  visible C++ surface that the (N) compatibility contract covers.
- [ADR-0006](0006-branch-model.md) — defines `main` (Slicer-stable)
  and `preview` (Slicer-preview) as the two long-lived branches; the
  `vMAJOR.MINOR.PATCH` tags this ADR specifies live on `main`.

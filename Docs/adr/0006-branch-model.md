# 0006. Branch model: `master` for Slicer-stable, `preview` for Slicer-preview

- **Status:** Accepted
- **Date:** 2026-05-14
- **Deciders:** Rafael Palomar
- **Diagrams:** N/A
- **PR:** _filled in on merge_
- **Supersedes:** The implicit "gitflow with `develop` + feature branches"
  pattern Slicer-Liver inherited from earlier 3D Slicer extension
  templates.  `develop` was retired in the gitflow cleanup that landed
  alongside [ADR-0005](0005-github-actions-ci.md); the present ADR
  formalises what replaces it.

## Context

Slicer-Liver is distributed via the
[Slicer Extensions Index](https://github.com/Slicer/ExtensionsIndex),
which has a separate branch per Slicer release line.  Each release
line's `SlicerLiver.json` entry pins a `scm_revision` — the
Slicer-Liver branch (or tag, or SHA) to build from for that Slicer
release.

As of this ADR, two release lines are actively served:

- **Slicer stable** — currently 5.10, formal release line.
- **Slicer preview** — `main` branch of the Slicer repository, the
  bleeding edge that becomes the next stable.

These two Slicer release lines have **different APIs**.  Slicer-Liver's
LayerDM migration ([ADR-0002](0002-migrate-to-slicerlayerdm.md))
explicitly tracks upstream Slicer changes that originate in `main`;
some of those changes are not yet in stable.  A *single* Slicer-Liver
branch cannot serve both release lines cleanly once preview-only APIs
appear in the code.

Before this ADR, Slicer-Liver had three long-lived branches
(`develop`, `master`, `preview`) following a gitflow-derived pattern,
but the actual semantics had drifted:

- `develop` was being treated as "the dev branch" but the Slicer
  Extensions Index never pointed at it.
- `master` was the legacy publishing branch (originally master in
  the pre-gitflow era), still pointed at by ExtensionsIndex 5.6 / 5.8.
- `preview` was the publishing branch for **both** Slicer 5.10 stable
  **and** Slicer main / preview — which worked while the APIs were
  close enough but is structurally unsound.

The branch retirement that landed alongside ADR-0005 removed
`develop` cleanly.  This ADR codifies the two-branch model that
remains.

## Decision

Slicer-Liver maintains exactly two long-lived branches.

### Branch responsibilities

| Branch | Slicer release line | ExtensionsIndex entry | Role |
|---|---|---|---|
| `master` | **Stable** (currently 5.10) | `Slicer/ExtensionsIndex/5.10/SlicerLiver.json` → `scm_revision: master` | Production branch served to end-users via Extension Manager on Slicer-stable. |
| `preview` | **Preview** (Slicer `main`) | `Slicer/ExtensionsIndex/main/SlicerLiver.json` → `scm_revision: preview` | Development branch tracking Slicer's bleeding edge; default branch of this repository. |

### Day-to-day workflow

1. **New work targets `preview`.**  Every PR's base is `preview` by
   default (this is also the GitHub-default branch).  The active
   refactor work (LayerDM migration; ADRs 0002–0005) lives on
   `preview` because it tracks upstream Slicer `main` APIs.

2. **Backports to `master` are cherry-picks**, performed when a PR's
   content has been merged on `preview` for at least one to two
   weeks without regressions and remains compatible with Slicer
   stable.  Each backport is a separate PR against `master` whose
   commits cite the original preview commit
   (`git cherry-pick -x` includes the source SHA in the message).

3. **Bug fixes for `master` that are already on `preview`**: cherry-
   pick from `preview` to a fix branch off `master`, open PR.

4. **Bug fixes for `master` not yet on `preview`** (rare): land on
   `master` first, then forward-port to `preview` with a follow-up
   PR.  Tag the forward-port commit message with the original master
   SHA for traceability.

5. **Both branches are protected**.  `preview` requires one approving
   review + code-owner review (per the rule applied during the
   gitflow retirement).  `master` follows the same rule once it
   re-converges with `preview` (this ADR's PR makes that re-convergence
   the moment to apply equivalent protection).

### CI

Initially, **one** CI image (`ghcr.io/alive-research/slicer-build-ubuntu2404`,
pinned to Slicer `main`) builds **both** branches.  This is safe while
`master` ≡ `preview` content-wise (the situation immediately after this
ADR's PR merges and `master` is force-updated to match `preview`).

A **second** image (`...slicer-build-ubuntu2404-stable`, pinned to a
Slicer 5.10.x SHA) is added in a follow-up ADR when — and only when —
the first PR lands on `preview` that uses a Slicer-main-only API and
breaks the stable build of `master`'s CI.  Until that real trigger
appears, building a stable-only image is premature work.

### Legacy Slicer (5.6, 5.8)

The legacy ExtensionsIndex entries on the `5.6` and `5.8` branches —
which currently point `scm_revision: master` — are retired in the
same change set as this ADR (separate upstream PRs against
`Slicer/ExtensionsIndex`).  Reasons:

- Slicer 5.6 (November 2023) and Slicer 5.8 (early 2025) are both
  past their natural support window for active feature development.
- The post-force-update `master` carries content (Qt 6 migration,
  modernised APIs from `9ef780b COMP: Fix compile errors`) that does
  not compile against Slicer 5.6 / 5.8.  Continuing to advertise
  Slicer-Liver as installable on those releases would mean publishing
  a known-broken extension.
- The natural recommendation to legacy-Slicer users is "upgrade
  Slicer."

If support for an older Slicer release is re-introduced later, the
right mechanism is a maintenance branch (e.g. `release/5.10`) cut
from a known-good `master` SHA, with an explicit ADR.

## Alternatives considered

### A. Keep `develop` (full gitflow)

Resurrect the pre-retirement state: `develop` for integration,
`master` for releases, feature branches off `develop`, release
branches between them.

**Rejected** because the original gitflow retirement (alongside
ADR-0005) was driven by hands-on experience that the three-branch
flow with `develop` produced confusion about *which* branch the
ExtensionsIndex actually served (it served `preview`, despite
"develop" sounding like the integration branch).  The two-branch
model is simpler and maps 1:1 to Slicer's two release lines.

### B. Single branch (`preview` only)

Drop `master` entirely.  Point all ExtensionsIndex entries at
`preview`.  Accept that stable Slicer users may see preview-only
features arrive immediately.

**Rejected** because:

- Slicer-stable users include the clinical pilot users this extension
  exists for; landing experimental refactor PRs (e.g. mid-LayerDM-
  migration states) directly into their installable version is
  irresponsible.
- The first preview-only Slicer API that lands on `preview` would
  immediately break Slicer-stable users' installs.
- The cost of maintaining a second branch is one periodic cherry-pick
  per ready-to-stabilise PR — a small ongoing cost for a large gain
  in change isolation.

### C. Develop on `master`, forward-port to `preview`

Make `master` the integration branch; `preview` carries only the
Slicer-main-compatibility patches.

**Rejected** for the same reason the gitflow `develop` retirement
was: the active refactor work (LayerDM migration) tracks Slicer
`main` APIs.  The branch that hosts that work is necessarily
preview-aligned.  Forcing it through `master` first would mean
master would receive code that doesn't yet compile on `master`'s
target Slicer line.

### D. Per-Slicer-release branches (`release/5.10`, `release/5.12`, ...)

A separate branch per Slicer minor release line, cut from `preview`
when each Slicer release goes stable.

**Rejected** as the *default* model — it expands to N branches
linearly with Slicer's release cadence, and most extensions don't
need N-version coverage.  Worth revisiting if a specific Slicer
release ever needs a maintenance branch (a fix backported only to
that release, not to current stable).  At that point, cut the
maintenance branch from a known-good `master` SHA, document with a
new ADR.

## Consequences

### Easier

- **Semantic clarity.**  `master` → stable, `preview` → preview.  A
  contributor reading the repo can predict which Slicer line a
  branch targets without reading further documentation.
- **ExtensionsIndex entries are unambiguous.**  No more "`preview`
  serves both 5.10 and main" confusion.  When a Slicer release
  becomes the new stable, the index entry for it gets pointed at
  `master`; previous-stable's entry can be retired or pinned to a
  legacy SHA.
- **Branch protection makes sense per branch.**  Both protect against
  direct push and require review; CODEOWNERS routes review to the
  maintainer either way.
- **JOSS / SECURITY.md story is coherent.**  The published paper
  links to the repo root, which lands on the default branch
  (`preview`); the SECURITY.md table cleanly describes which branch
  serves which Slicer line.

### Harder

- **Cherry-pick discipline.**  Backports are a routine maintenance
  task that did not exist under the single-branch model.  Mitigation:
  `/slicer-review`-style review automation can flag PRs whose
  content looks stable-suitable and remind the author to file a
  backport.
- **Two-branch CI eventually.**  The single-image-for-both phase
  ends as soon as `preview` and `master` content diverges API-wise.
  At that point a stable-CI-image PR is required; ADR-0005 + this
  ADR scope that follow-up.
- **Diverging history.**  Once cherry-picks accumulate, the two
  branches share a structural shape but not commit-level history.
  `git log master..preview` becomes the canonical "what hasn't been
  backported" query.
- **Force-update of `master` is required once** (the change this ADR's
  PR triggers).  After that, master evolves via normal PR + cherry-
  pick; no more force-updates.

## References

- [ADR-0005](0005-github-actions-ci.md) — the gitflow retirement that
  removed `develop` and made this ADR necessary.
- [SECURITY.md](../../SECURITY.md) — already names the two branches
  per their Slicer release line; this ADR is the canonical source
  for that table.
- [`Slicer/ExtensionsIndex`](https://github.com/Slicer/ExtensionsIndex)
  — the upstream registry whose per-Slicer-release branches drive
  the choice of two long-lived branches here.
- Slicer's own branching pattern (`main` + `release/X.Y` maintenance
  branches) — analogous, with reversed naming convention.

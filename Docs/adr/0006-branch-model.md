# 0006. Branch model: `main` for Slicer-stable, `preview` for Slicer-preview

- **Status:** Accepted
- **Date:** 2026-05-15
- **Deciders:** Rafael Palomar
- **Diagrams:** N/A
- **PR:** _filled in on merge_
- **Supersedes:** The implicit "gitflow with `develop` + feature branches"
  pattern Slicer-Liver inherited from earlier 3D Slicer extension
  templates.  `develop` was retired in the gitflow cleanup that landed
  alongside [ADR-0005](0005-github-actions-ci.md); the present ADR
  formalises what replaces it and, in the same change set, **renames
  the stable branch from `master` to `main`** to align with 3D Slicer
  upstream's own 2022 inclusive-language migration
  ([Slicer Discourse](https://discourse.slicer.org/t/slicer-to-use-more-inclusive-language-in-code/23972),
  [Slicer/Slicer#6277](https://github.com/Slicer/Slicer/pull/6277)).

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
explicitly tracks upstream Slicer changes that originate in Slicer's
`main`; some of those changes are not yet in stable.  A *single*
Slicer-Liver branch cannot serve both release lines cleanly once
preview-only APIs appear in the code.

Before this ADR, Slicer-Liver had three long-lived branches
(`develop`, `master`, `preview`) following a gitflow-derived pattern,
but the actual semantics had drifted:

- `develop` was being treated as "the dev branch" but the Slicer
  Extensions Index never pointed at it.
- `master` was the legacy publishing branch (originally the only
  branch in the pre-gitflow era), still pointed at by ExtensionsIndex
  5.6 / 5.8.
- `preview` was the publishing branch for **both** Slicer 5.10 stable
  **and** Slicer main / preview — which worked while the APIs were
  close enough but is structurally unsound.

The branch retirement that landed alongside ADR-0005 removed
`develop` cleanly.  This ADR codifies the two-branch model that
remains and aligns the remaining stable-branch name with the rest
of the 3D Slicer ecosystem.

## Decision

Slicer-Liver maintains exactly two long-lived branches.

### Branch responsibilities

| Branch | Slicer release line | ExtensionsIndex entry | Role |
|---|---|---|---|
| `main` | **Stable** (currently 5.10) | `Slicer/ExtensionsIndex/5.10/SlicerLiver.json` → `scm_revision: main` | Production branch served to end-users via Extension Manager on Slicer-stable. |
| `preview` | **Preview** (Slicer `main`) | `Slicer/ExtensionsIndex/main/SlicerLiver.json` → `scm_revision: preview` | Development branch tracking Slicer's bleeding edge; default branch of this repository. |

### Branch naming uses inclusive-language convention

The stable branch is named `main`, not `master`.  3D Slicer upstream
itself made this transition in 2022
([Slicer Discourse, "Slicer to use more inclusive language in
code"](https://discourse.slicer.org/t/slicer-to-use-more-inclusive-language-in-code/23972),
[Slicer/Slicer#6277](https://github.com/Slicer/Slicer/pull/6277)),
aligned with GitHub's own default-branch change and the IETF
inclusive-terminology draft.  Slicer-Liver had been on the previous
`master` name only because the original repository pre-dated that
upstream transition.  This ADR completes the alignment.

The rename is one of the change-set steps gated by this ADR (see the
"Migration steps" section below).

### Day-to-day workflow

1. **New work targets `preview`.**  Every PR's base is `preview` by
   default (this is also the GitHub-default branch).  The active
   refactor work (LayerDM migration; ADRs 0002–0005) lives on
   `preview` because it tracks upstream Slicer `main` APIs.

2. **Backports to `main` are cherry-picks**, performed when a PR's
   content has been merged on `preview` for at least one to two
   weeks without regressions and remains compatible with Slicer
   stable.  Each backport is a separate PR against `main` whose
   commits cite the original preview commit
   (`git cherry-pick -x` includes the source SHA in the message).

3. **Bug fixes for `main` that are already on `preview`**: cherry-
   pick from `preview` to a fix branch off `main`, open PR.

4. **Bug fixes for `main` not yet on `preview`** (rare): land on
   `main` first, then forward-port to `preview` with a follow-up
   PR.  Tag the forward-port commit message with the original `main`
   SHA for traceability.

5. **Both branches are protected**.  `preview` requires one approving
   review + code-owner review (per the rule applied during the
   gitflow retirement).  `main` follows the same rule once it
   re-converges with `preview` (this ADR's PR makes that re-convergence
   the moment to apply equivalent protection).

### CI

Initially, **one** CI image (`ghcr.io/alive-research/slicer-build-ubuntu2404`,
pinned to Slicer `main`) builds **both** branches.  This is safe while
`main` ≡ `preview` content-wise (the situation immediately after this
ADR's change set lands — see "Migration steps" — and `main` is force-
updated to match `preview`).

A **second** image (`...slicer-build-ubuntu2404-stable`, pinned to a
Slicer 5.10.x SHA) is added in a follow-up ADR when — and only when —
the first PR lands on `preview` that uses a Slicer-main-only API and
breaks the stable build of `main`'s CI.  Until that real trigger
appears, building a stable-only image is premature work.

### Legacy Slicer (5.6, 5.8)

The legacy ExtensionsIndex entries on the `5.6` and `5.8` branches
— which currently point `scm_revision: master` — are retired in the
same change set as this ADR (separate upstream PRs against
`Slicer/ExtensionsIndex`).  Reasons:

- Slicer 5.6 (November 2023) and Slicer 5.8 (early 2025) are both
  past their natural support window for active feature development.
- The post-rename, post-force-update `main` carries content (Qt 6
  migration, modernised APIs from `9ef780b COMP: Fix compile
  errors`) that does not compile against Slicer 5.6 / 5.8.
  Continuing to advertise Slicer-Liver as installable on those
  releases would mean publishing a known-broken extension.
- GitHub auto-redirects refs after a branch rename, so the legacy
  entries would *technically* keep resolving (`master` → `main`)
  for a while.  But that just papers over the incompatibility; the
  resolved build would still fail.  Retiring the entries makes the
  state explicit.
- The natural recommendation to legacy-Slicer users is "upgrade
  Slicer."

If support for an older Slicer release is re-introduced later, the
right mechanism is a maintenance branch (e.g. `release/5.10`) cut
from a known-good `main` SHA, with an explicit ADR.

### Migration steps (one-time, this ADR's PR is the trigger)

In this order:

1. **Merge this ADR's PR** to `preview`.  The repo content now
   describes the model with the new naming.
2. **Rename the existing `master` branch to `main`** via the GitHub
   API or repo settings.  GitHub transfers the branch-protection rule
   automatically and installs a permanent ref redirect so existing
   `master` references resolve transparently.
3. **Force-update `main` to `preview`'s tip** so both branches start
   from the same content.  This is the one-time force-update; from
   here on `main` evolves only via PR + cherry-pick.
4. **Re-tighten `main`'s branch protection** to disallow force-pushes
   (the only force-push the branch will ever see is step 3 itself).
5. **File the upstream `Slicer/ExtensionsIndex` PRs** that retire
   the `5.6` and `5.8` `SlicerLiver` entries (branches are pre-
   staged on `RafaelPalomar/ExtensionsIndex`).

## Alternatives considered

### A. Keep `develop` (full gitflow)

Resurrect the pre-retirement state: `develop` for integration,
`master`/`main` for releases, feature branches off `develop`, release
branches between them.

**Rejected** because the original gitflow retirement (alongside
ADR-0005) was driven by hands-on experience that the three-branch
flow with `develop` produced confusion about *which* branch the
ExtensionsIndex actually served (it served `preview`, despite
"develop" sounding like the integration branch).  The two-branch
model is simpler and maps 1:1 to Slicer's two release lines.

### B. Single branch (`preview` only)

Drop the stable branch entirely.  Point all ExtensionsIndex entries
at `preview`.  Accept that stable Slicer users may see preview-only
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

### C. Develop on stable, forward-port to `preview`

Make the stable branch the integration branch; `preview` carries only
the Slicer-main-compatibility patches.

**Rejected** for the same reason the gitflow `develop` retirement
was: the active refactor work (LayerDM migration) tracks Slicer
`main` APIs.  The branch that hosts that work is necessarily
preview-aligned.  Forcing it through the stable branch first would
mean stable would receive code that doesn't yet compile on its
target Slicer line.

### D. Per-Slicer-release branches (`release/5.10`, `release/5.12`, …)

A separate branch per Slicer minor release line, cut from `preview`
when each Slicer release goes stable.

**Rejected** as the *default* model — it expands to N branches
linearly with Slicer's release cadence, and most extensions don't
need N-version coverage.  Worth revisiting if a specific Slicer
release ever needs a maintenance branch (a fix backported only to
that release, not to current stable).  At that point, cut the
maintenance branch from a known-good `main` SHA, document with a
new ADR.

### E. Keep `master` as the stable-branch name

Leave the stable branch named `master`, on the grounds that it has
historically been that way, that GitHub's rename-redirect makes
ecosystem disruption minimal, and that the name change has no
*technical* effect.

**Rejected** because:

- Slicer upstream completed the same transition in 2022 with
  [Slicer/Slicer#6277](https://github.com/Slicer/Slicer/pull/6277);
  staying on `master` makes Slicer-Liver the odd one out in the
  ecosystem we publish into.
- The IETF inclusive-terminology draft and GitHub's own default
  ([RFC 8174 update](https://datatracker.ietf.org/doc/draft-ietf-terminology/),
  context [discussed by GitHub in 2020](https://github.blog/2021-09-01-improving-git-protocol-security-github/))
  point in the same direction.
- The change-set required (this ADR's PR) is small relative to the
  ongoing alignment cost of being out of step with upstream.
- The dissenting voice in Slicer's own discussion
  ([@chir.set](https://discourse.slicer.org/t/slicer-to-use-more-inclusive-language-in-code/23972/3))
  argued the change was symbolic; the project lead's position here
  is that small symbolic alignments with the host ecosystem are
  cheap and worth doing once.

## Consequences

### Easier

- **Semantic clarity.**  `main` → stable, `preview` → preview.  A
  contributor reading the repo can predict which Slicer line a
  branch targets without reading further documentation.
- **Ecosystem alignment.**  The branch naming matches Slicer
  upstream's convention; cross-repo tooling that assumes `main` is
  the stable branch (CDash, ExtensionsIndex tooling, `slicer-review`)
  works without per-repo configuration.
- **ExtensionsIndex entries are unambiguous.**  No more "`preview`
  serves both 5.10 and main" confusion.  When a Slicer release
  becomes the new stable, the index entry for it gets pointed at
  `main`; previous-stable's entry can be retired or pinned to a
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
  the `/slicer-review` slash-command (see
  `Docs/architecture/README.md`) can flag PRs whose content looks
  stable-suitable and remind the author to file a backport.
- **Two-branch CI eventually.**  The single-image-for-both phase
  ends as soon as `preview` and `main` content diverges API-wise.
  At that point a stable-CI-image PR is required; ADR-0005 + this
  ADR scope that follow-up.
- **Diverging history.**  Once cherry-picks accumulate, the two
  branches share a structural shape but not commit-level history.
  `git log main..preview` becomes the canonical "what hasn't been
  backported" query.
- **One-time `master` → `main` rename plus force-update of `main`**
  (the change-set this ADR triggers).  After that, `main` evolves
  via normal PR + cherry-pick; no more force-updates.  GitHub's
  permanent ref redirect handles existing `master` references
  (clones, external links) transparently.

## References

- [ADR-0005](0005-github-actions-ci.md) — the gitflow retirement that
  removed `develop` and made this ADR necessary.
- [SECURITY.md](../../SECURITY.md) — names the two branches per their
  Slicer release line; will be refreshed in a follow-up PR to use
  the post-rename names.
- [`Slicer/ExtensionsIndex`](https://github.com/Slicer/ExtensionsIndex)
  — the upstream registry whose per-Slicer-release branches drive
  the choice of two long-lived branches here.
- 3D Slicer's own inclusive-language transition:
  - [Slicer Discourse thread, June 2022](https://discourse.slicer.org/t/slicer-to-use-more-inclusive-language-in-code/23972)
  - [Slicer/Slicer#6277 (implementation PR)](https://github.com/Slicer/Slicer/pull/6277)
- Slicer's branching pattern (`main` + `release/X.Y` maintenance
  branches) — the same naming convention adopted here.

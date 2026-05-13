# 0005. CI runs on every PR via GitHub Actions

- **Status:** Proposed
- **Date:** 2026-05-13
- **Deciders:** Rafael Palomar
- **Diagrams:** N/A
- **PR:** _filled in on merge_

## Context

[ADR-0003](0003-testability-invariant.md) makes "every behaviour-changing
PR carries a test that pins the behaviour" a project invariant.  The
`/slicer-review` test-coverage reviewer enforces this locally, but
*local* enforcement depends on a human running `/slicer-review` before
merging — and the cost of forgetting is the regression landing on
`develop` unobserved.

Three external pressures push the same direction:

- **The LayerDM migration ([ADR-0002](0002-migrate-to-slicerlayerdm.md))
  spans dozens of stacked PRs.**  Without automated CI, any one of
  those PRs can break the storage round-trip
  ([PR #294](https://github.com/ALive-research/Slicer-Liver/pull/294)
  characterisation test) or break compilation on a clean tree, and the
  failure surfaces days later when someone tries to build locally.
- **The contributor base is researcher-heavy** (per [ADR-0004](0004-python-cpp-boundary.md)):
  catching breakage at PR time is the cheapest moment for a contributor
  to fix; catching it later means context loss.
- **Slicer-Liver targets the upstream Slicer ExtensionsIndex.**  When
  the extension is submitted there, the Slicer Dashboard runs CTest
  against it.  Running the same test suite on every PR pre-empts most
  dashboard rejections.

The Slicer-extension ecosystem does **not** have a single canonical CI
container — the wider community has historically deferred to the Slicer
Dashboard, with extension-specific CI handled ad hoc.  Recent extensions
(e.g. `SlicerLayerDisplayableManager`) lean on the new wheel-SDK pattern
(`cibuildwheel`), which fits Python-distributable extensions; Slicer-Liver
is a traditional C++ Loadable-module extension and is a poor fit for
that pattern today.

## Decision

A GitHub Actions workflow at `.github/workflows/ci.yml` runs on every
pull request targeting any branch and on every push to `develop`.  The
workflow defines two jobs:

1. **`docs-lint`** — fast (~30 s), no Slicer dependency.  Validates:
   - All `Docs/architecture/**/*.md` Mermaid fences parse cleanly via
     `@mermaid-js/mermaid-cli`.
   - All internal Markdown links across `Docs/**` resolve (no dead
     references between ADRs / diagrams / READMEs).
   This job catches the kinds of errors that the `/slicer-review`
   style reviewer also flags, but pre-emptively, before review effort.

2. **`build-test`** — slow (~10–30 min once container is warm).  Builds
   Slicer-Liver against a pinned **`slicer-master`** container and runs
   the full CTest suite (the existing C++ tests plus the
   `vtkMRMLLiverResectionStorageRoundTripTest` from PR #294).
   - **Linux only** on the first iteration (Ubuntu 22.04 runner).
   - **Single Slicer version**: slicer-master.  Catches upstream-Slicer
     drift early; cost is acceptable noise when Slicer breaks upstream.
   - Container reference is **TBD-verified-on-first-run**.  The
     `slicer-master`-against-pre-built-Docker pattern is what popular
     Slicer extensions use, but the canonical image name is not
     well-publicised; the first CI run reveals whether the chosen
     reference resolves and what to substitute if not.  When the right
     image is confirmed, this ADR is amended (append-only) to record
     the choice and the rationale.

Failure of either job blocks merge once branch-protection is enabled
on `develop` (a separate, lightweight follow-up PR after CI is proven
green for at least one merge cycle).

## Alternatives considered

### A. Defer all extension testing to the Slicer Dashboard

The Slicer ExtensionsIndex submission process runs CTest on the
extension at submission time and on every Slicer dashboard cycle.

**Rejected** because the dashboard runs only on accepted extensions,
on Slicer's release cadence (days–weeks of latency), and surfaces
failures to the extension maintainer by email rather than as a PR
status check.  None of those match the PR-time feedback loop ADR-0003
requires.  The dashboard remains a complementary signal for *post-merge*
validation; it does not replace per-PR CI.

### B. Self-hosted GitHub Actions runners

Run a self-hosted runner on `alucard` or `einstein` with a pre-built
Slicer tree, eliminating the container-pull cost.

**Rejected** for the first iteration because (a) it introduces a
single-point-of-failure outside GitHub's infrastructure, (b) keeping
the runner's Slicer tree up-to-date is manual operational work, and
(c) GitHub-hosted runners are sufficient for the expected PR
throughput.  Self-hosted may become attractive once CI volume
justifies it; not now.

### C. Build Slicer from source in CI

Each CI run does a full Slicer SuperBuild, then builds Slicer-Liver
against it.

**Rejected** because Slicer SuperBuild takes 60–90 min even with
extensive caching, eats GitHub Actions minute budget, and is brittle
to upstream Slicer build breakages that have nothing to do with
Slicer-Liver.  The pre-built container approach delivers the same
slicer-master coverage in a fraction of the time.

### D. Use a pinned Slicer **release** tarball

Download the latest Slicer 5.x release tarball into each run, cache
it, build against it.

**Rejected** because it ties CI to the release cadence — upstream
Slicer fixes (and breakages) won't reach Slicer-Liver CI until next
release.  For an extension actively tracking the Markups → LayerDM
transition that originates in upstream Slicer, slicer-master is the
right target.  Release-pinned CI may be revisited if upstream churn
becomes prohibitive.

### E. cibuildwheel / wheel-SDK pattern

Adopt the `SlicerLayerDisplayableManager` approach: build the extension
as a pip-installable wheel via `cibuildwheel`.

**Rejected** for now because Slicer-Liver is a traditional Loadable
C++ extension, not a wheel-distributable Python module.  The wheel-SDK
pattern is the right answer for extensions being designed around it
from day one; retrofitting it onto Slicer-Liver is a separate
architectural decision that is not in scope here.  Worth reconsidering
when the LayerDM migration (ADR-0002) is complete and the extension's
distribution model can be re-evaluated.

## Consequences

### Easier

- **PR-time feedback.**  ADR-0003's testability invariant gains
  automated enforcement.  Regressions in the storage round-trip
  (PR #294) or in any other CTest target surface as a red CI badge on
  the offending PR, not as a clinical bug months later.
- **Contributor onboarding.**  A new contributor's first PR gets the
  same automated feedback as a senior maintainer's — no "build it on
  my laptop and tell you in two days" loop.
- **Pre-emptive ExtensionsIndex validation.**  Most issues that would
  have failed on the Slicer Dashboard are caught here first.
- **Documentation gains a safety net.**  The `docs-lint` job catches
  the broken-Mermaid / dead-link class of errors at PR time;
  reviewers stop having to spot them.

### Harder

- **GitHub Actions minute consumption.**  Each `build-test` run will
  consume meaningful minutes; the public-repo allowance covers
  expected PR volume but is not infinite.  When `develop` merges
  accumulate near the budget limit, options are self-hosted runners
  (Alternative B) or skipping the build job on docs-only PRs (path-
  filter optimisation).
- **CI maintenance.**  The workflow becomes another artefact to keep
  current with Slicer-Liver, Slicer-master, and the container
  ecosystem.  Add it to the per-module-migration PR checklist (per
  ADR-0002) — if the migration breaks CI, the migration PR fixes the
  CI alongside the code.
- **Upstream Slicer drift surfaces in our CI.**  When Slicer-master
  breaks (which happens periodically), Slicer-Liver CI will go red
  through no fault of any Slicer-Liver PR.  Mitigation: pin the
  container by digest after the first verified-green run, and bump
  the digest deliberately on a separate "ENH: bump CI container"
  cadence.

## References

- The `/slicer-review` slash-command and its test-coverage reviewer at
  `~/.claude/commands/slicer-review.md` (local enforcement; CI is the
  remote complement).
- [ADR-0002](0002-migrate-to-slicerlayerdm.md) — the migration this CI
  protects.
- [ADR-0003](0003-testability-invariant.md) — the testability invariant
  this CI enforces.
- [ADR-0004](0004-python-cpp-boundary.md) — the language boundary the
  test layer respects (`build-test` runs C++ CTest today; Python self-
  tests join once the Python test infrastructure for this module
  lands).
- [PR #294](https://github.com/ALive-research/Slicer-Liver/pull/294) —
  the first characterisation test the CI is designed to run.
- `SlicerCustomAppTemplate` (Kitware-maintained Slicer custom-app
  starter) — reference for Slicer-extension lint conventions.
- `SlicerLayerDisplayableManager` `cibuildwheel` workflows — reference
  for the wheel-SDK alternative path (Alternative E).

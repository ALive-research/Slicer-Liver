# 0030. Pin the CI Slicer image to a specific build, bump deliberately

- **Status:** Accepted
- **Date:** 2026-06-09
- **Deciders:** Rafael Palomar
- **Diagrams:** N/A
- **PR:** _filled in on merge_

## Context

[ADR-0005](0005-github-actions-ci.md) builds and tests every PR inside
the project-maintained `ghcr.io/alive-research/slicer-build-ubuntu2404`
image (Ubuntu 24.04 + Qt 6.9 + Slicer **main** pre-built, with
SlicerLayerDM baked in per [ADR-0002](0002-migrate-to-slicerlayerdm.md) /
[ADR-0013](0013-layerdm-pipeline-pattern.md)).  Until now both CI jobs
(`build-test` and `coverage`) referenced that image as **`:latest`** — a
rolling tag the `ALive-Docker` repository rebuilds to track Slicer main.

`:latest` couples Slicer-Liver CI to the *instantaneous* state of an
upstream development branch. Two independent development branches —
Slicer main and Slicer-Liver `preview` — advance on their own cadences,
and a rolling tag silently joins them: every PR builds against whatever
Slicer main happened to produce most recently.

This bit us concretely. A `pull_request` run and a `preview` run roughly
50 minutes apart pulled **different** `:latest` images by digest; the
earlier one carried a Slicer-main build whose Python runtime was broken
(`slicer.util` lacked `exit`, the launched application half-initialised),
which manifested downstream as a 1500 s launched-test hang on the PR
while `preview` — pulling the later, healthy `:latest` — passed. The
failure was neither reproducible nor bisectable from the Slicer-Liver
side: the same commit passed or failed depending on *when* it ran.

The same registry already publishes immutable, Slicer-commit-tagged
images (`:main-<sha>`) alongside `:latest`. Pinning is therefore nearly
free — the infrastructure exists; we were simply consuming the moving
tag.

This decision does **not** claim the hang incident was *caused* by the
moving tag in the sense of "pinning would have prevented that bug" — the
bug that surfaced was in Slicer-Liver's own test harness, independently
fixed. Pinning addresses a different, structural problem:
**non-reproducible CI and uncontrolled coupling to upstream churn.**

## Decision

### 1. Pin both CI jobs to a specific `:main-<sha>` build

`build-test` and `coverage` reference
`ghcr.io/alive-research/slicer-build-ubuntu2404:main-<sha>` — a tag that
names the exact Slicer-main commit baked into the image — not `:latest`.
The two jobs are always kept on the **same** pin; they must never drift
onto different Slicer commits. The initial pin is `main-4fb4ac4`
(digest `sha256:549a820f…`), the known-good image the green runs used.

### 2. Bump deliberately, via a dedicated image-bump PR

Advancing the pinned Slicer is an explicit act: a PR that does nothing
but move the `:main-<sha>` tag in both jobs. That PR runs the full
suite against the new Slicer in isolation. If it is red, the breakage
is fixed *in that PR* against the new Slicer — not scattered across
unrelated contributors' PRs. This is the **single place** the two
development branches are reconciled, on Slicer-Liver's cadence.

Cadence is human-chosen (e.g. when a new Slicer feature is needed, or on
a periodic sweep), not automatic. A drifting upstream no longer reaches
contributors except through this gate.

### 3. Smoke-check the pinned image's runtime, fail fast

Each job's "Verify Slicer build tree" stage already asserts the build
*layout* (`SlicerConfig.cmake`, `LayerDisplayableManagerConfig.cmake`).
A companion "Smoke-check pinned Slicer runtime" step asserts the Slicer
*runtime* is sane: `PythonSlicer` imports `slicer.util` and confirms it
carries `exit` and `VTKObservationMixin`. A pinned-but-runtime-broken
image (the exact failure mode above) thus fails loudly at the verify
stage with an ADR-citing message, instead of as a confusing downstream
hang or skip. The check uses `PythonSlicer` (library import, no event
loop) so it is cheap and cannot itself hang.

## Alternatives considered

### Alternative A — Keep `:latest` (status quo)
Rejected. Non-reproducible by construction; a bad upstream push lands on
whichever PR runs in the window, and "passed/failed depending on when it
ran" is the worst kind of CI signal to debug.

### Alternative B — Pin by digest (`@sha256:…`) instead of `:main-<sha>`
A digest is maximally immutable, but opaque: the bump PR diff becomes an
unreadable hash and reviewers lose the Slicer-commit context. The
`:main-<sha>` tag encodes the upstream commit, makes the bump
self-documenting, and is published per-build (not re-tagged) by
ALive-Docker. We record the digest in a comment next to the pin for
auditability, getting most of the immutability benefit without the
opacity. Teams needing strict supply-chain guarantees can switch to the
digest form later without revisiting this decision.

### Alternative C — Auto-bump on a schedule (e.g. weekly Dependabot-style PR)
Defers the reconciliation work but does not remove it, and a scheduled
auto-bump that goes red still blocks the cadence. A human-chosen bump is
simpler for the current contributor base ([ADR-0004](0004-python-cpp-boundary.md))
and keeps the bump tied to an actual need. Revisitable if bump latency
becomes a problem.

## Consequences

### What becomes easier
- CI is reproducible: a commit's result no longer depends on wall-clock
  timing of the upstream image build.
- Upstream Slicer breakage is absorbed deliberately, in one isolated PR,
  rather than surprising unrelated contributors.
- A runtime-broken image fails fast with a clear, ADR-cited message.

### What becomes harder
- New Slicer features/fixes are not picked up until someone bumps the
  pin; the pin can lag upstream. This is the intended trade — controlled
  staleness over uncontrolled churn.
- Two places (both jobs) must be bumped together; the inline comments and
  this ADR call that out, and the bump PR's own CI enforces it.

### Follow-on work
- The runtime smoke could be extended (e.g. a launched-app `mrmlScene`
  probe) if a future drift slips past the `PythonSlicer`-level check.
- If bump latency becomes painful, revisit Alternative C
  (scheduled bump PR) — the pin mechanism here is a prerequisite for it.

## Conformance

- [test/review] Both `build-test` and `coverage` reference the **same**
  `:main-<sha>` pin, never `:latest`. A reviewer rejects a PR that
  reintroduces `:latest` or lets the two jobs diverge.
- [review] Advancing Slicer is a dedicated image-bump PR (only the pin
  changes), reviewed on its own CI; upstream breakage is fixed in that PR.
- [test] Each job runs the "Smoke-check pinned Slicer runtime" step; a
  pinned image whose `slicer.util` lacks `exit`/`VTKObservationMixin`
  fails the job at the verify stage, not downstream.
- [review] The digest is recorded in a comment beside each pin for
  auditability.

## References

- [ADR-0005](0005-github-actions-ci.md) — GitHub Actions CI on every PR
- [ADR-0002](0002-migrate-to-slicerlayerdm.md),
  [ADR-0013](0013-layerdm-pipeline-pattern.md) — why SlicerLayerDM is
  baked into the image
- [ADR-0004](0004-python-cpp-boundary.md) — researcher-heavy contributor
  base (informs the human-bump choice)
- [ADR-0021](0021-coverage-measurement.md) — the non-blocking `coverage`
  job that shares the pinned image

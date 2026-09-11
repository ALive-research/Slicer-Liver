# 0021. Test-coverage measurement (gcovr + coverage.py + Codecov)

- **Status:** Accepted
- **Date:** 2026-05-18
- **Deciders:** Rafael Palomar
- **PR:** _filled in on merge_

## Context

[ADR-0008][adr-0008] commits the project to dual-mode tests
(C++ + Python).  As of v2.0.0 the C++ test surface grew substantially
(state machine, variable-size control polygon, mapper refresh,
visual-regression scaffolding); the Python side grew correspondingly.
Without a coverage signal:

- PRs that add code without exercising it slip through.
- The maintainer has no visible diff-coverage when reviewing.
- [ADR-0003][adr-0003] (characterisation-tests-before-refactor) has no
  automated enforcement — only manual review of test diffs.

We need:

- A free-for-OSS stack that handles C++ + Python in one workflow.
- PR-comment diff-coverage gating (not just an absolute %).
- No third-party service that requires payment or a complex auth
  setup.

[adr-0003]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0003-testability-invariant.md
[adr-0008]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0008-testing-strategy.md
[adr-0017]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0017-sphinx-readthedocs.md

## Decision

Adopt the standard free-for-OSS coverage stack:

- **C++ side:** GCC's built-in `-fprofile-arcs -ftest-coverage` (or
  `--coverage`) instrumented build; `gcovr` to produce a Cobertura
  `coverage-cxx.xml`.
- **Python side:** `coverage.py` via the `pytest-cov` plugin; emits a
  Cobertura `coverage-py.xml`.
- **Aggregation + UI:** **Codecov** (codecov.io), uploaded via
  `codecov/codecov-action@v5` in a parallel CI matrix entry.  Free for
  OSS; OAuth via GitHub; no credit card.  Posts PR comments showing
  the diff coverage line-by-line.

Codecov's primary signal is **diff coverage** (new + modified lines
covered by the PR), not absolute %.  We do not set a hard
absolute-% threshold; ratchet pressure is per-PR.

## Why Codecov over Coveralls

- Codecov has stronger fork/PR support (relevant for community
  contributors).
- More common in C++ projects in 2026.
- Equivalent free-for-OSS terms.
- Tradeoff: both work; the decision is reversible.

## Why no absolute threshold

- Premature gating discourages contributions.
- Coverage % is a vanity metric without behavioural ground truth.
- [ADR-0003][adr-0003]'s characterisation-test-before-refactor rule is
  the load-bearing convention; coverage % is informational.
- The PR comment makes diff coverage visible; the human reviewer
  judges sufficiency.

## Rollout plan

1. ADR-0021 (this PR) lands.
2. CI infra follow-up (sibling PR — opens alongside this one) adds the
   `.codecov.yml`, the coverage matrix entry in `ci.yml`, and any
   image-side dependency (`gcovr` + `pytest-cov` available on the
   runner).
3. Codecov account / OAuth set up by the maintainer (one-time; takes
   2 minutes via the Codecov GH app).
4. First PR after merge triggers the first coverage upload + PR
   comment.
5. Future bumps: tune `.codecov.yml` (status checks, comment template,
   path filters) as the maintainer learns what's noisy.

## Out of scope

- Branch-coverage (line-coverage only for the first cut; branch
  coverage is gcovr-supported but doubles CI runtime).
- Absolute % gates (informational only; revisit per
  [ADR-0008][adr-0008]'s "iterative ratchet").
- Cross-platform coverage runs (Linux only; macOS/Windows out of
  scope until [ADR-0017][adr-0017]'s RTD scope decision is revisited
  for CI).
- Slicer-launcher Python coverage if the wrapped MRML bindings aren't
  reachable from plain pytest (tracked as the visual-test-harness
  infra gap; coverage instrumentation is opt-in per test, so we cover
  what we can today and grow as the bindings become importable).

## Consequences

**Positive:**

- Diff-coverage visible on every PR.
- Catches "wrote it, didn't test it" silently-untested code paths.
- [ADR-0003][adr-0003] enforcement gets a measurable signal.

**Negative:**

- Adds ~6-8 min to CI per PR (coverage matrix entry compiles with
  `-O0 --coverage` and re-runs CTest).
- Codecov is a third-party service; if it goes down or changes terms,
  the gating disappears.  Reversibility: drop the upload step + the
  PR comment; tests still run.
- Coverage % drift on rebases can produce noisy PR comments.

## Configuration traps (learned 2026-09-11)

The whole-tree percentage is only as honest as the upload wiring, and
two settings can corrupt it silently -- no warning, no failed job, just
a wrong number:

- **`flags.<flag>.paths` in `.codecov.yml` DROPS files, it does not
  merely un-flag them.**  A path list that has fallen behind the module
  layout removes those modules from the reported percentage entirely.
  This is the trap that hid `Liver/`, `LiverSegmentation/` and
  `SlicerLiverInteractionLib/` while the coverage job was measuring
  them.  Flag membership should come from the upload, not from a second
  filter that has to be kept in sync with the tree.
- **One `codecov-action` step with `files: a,b` + `flags: x,y` is ONE
  session carrying BOTH flags**, so neither flag isolates its language.
  The tell is `sessions: 1` on a repo with two flags.  Upload once per
  flag.

Because both faults change the *denominator*, they also make the
percentage non-comparable across commits: a docs-only commit can appear
to move coverage by several points.  When a coverage swing has no
plausible cause in the diff, check the file and line totals before
reading it as a test-quality regression.

Any new Python sub-package staged into `qt-scripted-modules/` needs a
`[paths]` alias in `.coveragerc`, or its launched-leg records stay on
build-tree paths and never merge onto the source file.

## References

- [ADR-0003][adr-0003] — Testability invariant.
- [ADR-0008][adr-0008] — Testing strategy (C++ + Python dual mode).
- [ADR-0017][adr-0017] — Sphinx scaffold (similar infrastructure-only
  ADR pattern).
- gcovr docs: <https://gcovr.com/>
- coverage.py docs: <https://coverage.readthedocs.io/>
- Codecov GH Action: <https://github.com/codecov/codecov-action>

---

*AI-assisted authorship: drafted with help from Anthropic's Claude
(Opus 4.7, `claude-opus-4-7`) via Claude Code.*

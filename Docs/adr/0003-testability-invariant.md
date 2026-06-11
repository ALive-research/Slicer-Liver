# 0003. Every behaviour-changing PR carries a test that pins the behaviour

- **Status:** Accepted
- **Date:** 2026-05-13
- **Deciders:** Rafael Palomar
- **Diagrams:** N/A
- **PR:** _filled in on merge_

## Context

The LayerDM migration ([ADR-0002](0002-migrate-to-slicerlayerdm.md)) is
a multi-PR refactor of clinical software with real users.  Without a
discipline that pins behaviour at the PR level, regressions accumulate
invisibly during the most active period of the migration and surface
only when surgeons hit them in clinical use — which is exactly the
wrong feedback loop.

Today's coverage in Slicer-Liver:

- `LiverResections/Testing/Cxx/vtkMRMLLiverResectionNodeTest1.cxx` —
  exerciser for property setters/getters; in-memory only.
- `LiverResections/Testing/Cxx/vtkSlicerLiverResectionsLogicTest1.cxx` —
  add-node/retrieve-by-ID round trip; does not invoke
  `ReadData`/`WriteData`.
- `LiverResections/Testing/Cxx/qSlicerLiverResectionsModuleIntegrationTest.cxx` —
  full Qt/Slicer bring-up; registers widget; does not exercise
  save/reload.
- `LiverMarkups/Testing/Cxx/qSlicerLiverMarkupsModuleTest.cxx` —
  registers markup types; no persistence test.

No test covers the `.lrp.fcsv` round-trip — the safety net that
ADR-0001's Consequences section explicitly identifies as required to
catch reload-ordering regressions.  *This ADR* makes that test a
precondition for the ADR-0002 migration (ADR-0001 itself flags the
need without gating ADR-0002 on it).

Slicer's Python self-test framework is fast, well-supported, and
established in upstream modules (`SegmentEditor`, `SegmentStatistics`,
`SampleData` all use it).  Per [ADR-0004](0004-python-cpp-boundary.md),
Python is the default implementation language for new code; testing
follows the same boundary.

## Decision

Every PR that **modifies the externally-observable behaviour of a class
or pipeline** must include or update, *in the same PR*, a unit or
integration test that pins the behaviour being changed.  Specifically:

1. **For refactors that preserve behaviour** (the common case during
   the LayerDM migration), the test must:
   - Have been added in a prior PR as a *characterisation test* of the
     current behaviour, **OR**
   - Land in this PR as a characterisation test *before* the
     behaviour-changing commit, in the same PR's commit sequence.
   - Pass before and after the refactor.

2. **For new-feature PRs**, the test pins the new behaviour
   intentionally — same-PR, same-commit-sequence, must pass on merge.

3. **For bug-fix PRs**, a regression test reproducing the bug must
   land in the PR and fail without the fix.

4. **Tests live under `<Module>/Testing/`** following the existing
   Slicer-Liver directory convention.  Python tests follow the Slicer
   self-test pattern (`ScriptedLoadableModuleTest` subclass with a
   `runTest()` method).  C++ tests follow CTest + the existing patterns
   in `LiverResections/Testing/Cxx/`.

5. **The `/slicer-review` test-coverage reviewer** enforces the
   "characterisation test before refactor commit" rule for PRs and
   commits tagged `refactor:` (see the reviewer prompt at
   `~/.claude/commands/slicer-review.md`, test-coverage section
   criterion (c)).  New-feature and bug-fix variants of this rule
   are reviewer-judgment until the prompt is widened to cover them
   — until that follow-up lands, human-reviewer approval depends on
   confirming the test exists, was modified appropriately, and
   passed locally before merge.

6. **First debt to retire** (before any LayerDM-migration PR lands):
   - `vtkMRMLLiverResectionStorageRoundTripTest` — create a resection,
     write to `.lrp.fcsv`, clear the scene, reload, assert the
     three-node assembly is intact, refs resolve, properties survive.
     This is the precondition test for the entire ADR-0002 migration.

## Alternatives considered

### A. Tests at the end of the migration

Defer characterisation tests until the LayerDM migration stabilises;
write the test suite once the architecture is settled.

**Rejected** because it produces exactly the failure mode this ADR
exists to prevent.  Regressions accumulate invisibly during the most
active refactor period — the only period when bisecting back to the
introducing commit is cheap.  Once the migration finishes, deferred
tests become "describe the system" rather than "pin the behaviour";
they no longer catch the regressions they were meant to.

### B. Tests only for new code

Characterise only what is added in a PR, not what is changed.

**Rejected** because the LayerDM migration is *mostly* changing
existing code, not adding new code.  This rule would exempt the entire
risky period from the discipline.  Refactoring without coverage is
rewriting without coverage — the failure mode is the same.

### C. Manual QA only — rely on clinical evaluation

Clinical evaluators exercise the workflow after each release; bugs
caught in user feedback drive fixes.

**Rejected** because it doesn't scale and the feedback latency is wrong:

- Clinical evaluators cannot be in the loop for every PR (and even if
  they could be, the cost is unjustifiable).
- Surgical-planning workflows are episodic; regressions in seldom-used
  paths surface months later.
- "Caught by the user" is the most expensive bug-discovery moment;
  surgeon trust in the tool is non-renewable.

### D. CI-enforced coverage gate as the first move

Add a CI gate that blocks PRs without test diffs before writing this
ADR.

**Rejected** as the first move because CI enforcement without the
human convention behind it produces tests that satisfy the gate
without actually pinning behaviour (sentinel asserts, coverage games).
The ADR comes first; the CI gate is a follow-up PR once the
convention is internalised and we can encode the right rules.

## Consequences

### Easier

- **Regressions are caught at PR time**, not in clinical use.  Bisect
  is cheap when the surface area of a PR is small.
- **Refactor confidence**: the LayerDM migration becomes tractable
  because each step has its safety net before the change.
- **PR review becomes faster** — the reviewer's question shifts from
  *"will this break anything"* to *"is the test pinning the right
  thing"*, which is more focused.
- **Onboarding** is cheaper: a new contributor reads a module's
  `Testing/` directory and learns what the module is supposed to do.

### Harder

- **PR overhead increases ~30-50%** for tests.  This is real cost;
  it's the price paid for the safety net.
- **Characterisation tests for legacy code require investment** —
  retroactively writing tests for code that was never test-driven is
  slow and produces tests that are more brittle than test-first code.
  Budget for it as part of each module's migration prep, not as a
  one-off project.
- **Some behaviour is hard to test** — Qt widget interactions,
  threaded callbacks, scene-graph state where the setup machinery is
  itself unstable.  When in doubt, write the test against a stable
  surface (the public API of a class) rather than an unstable internal
  state.
- **Tests can ossify the design** if written too tightly to the
  current implementation.  Mitigate by testing behaviour, not
  structure — pin the externally-observable contract, not the
  internal call graph.

## References

- Slicer self-test pattern:
  `Base/Python/slicer/ScriptedLoadableModule.py` in the Slicer source
  tree (`ScriptedLoadableModuleTest` class).
- Existing Slicer-Liver test files under `LiverResections/Testing/`
  and `LiverMarkups/Testing/`.
- The `/slicer-review` test-coverage reviewer (configured in the
  reviewer's prompt) flags PRs that violate this convention.
- Working Effectively with Legacy Code (Feathers) — the
  characterisation-test discipline this ADR formalises.
- Related: ADR-0002 (the migration this safety net protects) and
  ADR-0004 (Python-first as the test-implementation language).

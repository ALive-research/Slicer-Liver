# 0008. Testing strategy for v2.0.0

- **Status:** Accepted
- **Date:** 2026-05-15
- **Deciders:** Rafael Palomar
- **Diagrams:** N/A
- **PR:** _filled in on merge_

## Context

[ADR-0003](0003-testability-invariant.md) establishes the *what*: every
behaviour-changing PR carries a test that pins the behaviour.  It
deliberately does not prescribe the *how* — leaving framework choice,
test layering, visualisation testing, and CI shape open.  The v2.0.0
SLDM migration (ADR-0002) is large enough that the *how* now needs to
be explicit, both to bound the regression risk of the migration and to
set a sustainable pattern for the post-migration project.

Today's Slicer-Liver test surface (7 files) is heavily C++/CTest with
one Python test.  Coverage targets node property exercisers, logic
add-retrieve, storage round-trip, and module-level integration.  No
fixture infrastructure, no pipeline tests (because no LayerDM
Pipelines exist yet), no characterisation tests for the buggy Bezier
fitting code flagged in the resection refactor work.

Two Kitware-maintained projects are the closest precedents:

- **SlicerLayerDisplayableManager** (= the dependency we adopt per
  ADR-0002) tests in three tiers: package-level pytest (`LayerDM/tests/`),
  Slicer-style Python tests (`LayerDM/Testing/Python/*Test.py`), and C++
  ctkTest under `LayerDM/Testing/Cxx/`.  Tests import `slicer` as a
  Python library; no GUI launch.
- **trame-slicer** runs pure pytest with fixture-heavy `conftest.py`
  (`a_slicer_app`, `a_segmentation_editor`, `a_volume_node`,
  `a_segment_id`, `a_view_factory`, ...) and a session-scoped
  `render_interactive` CLI option that toggles `ShowWindowOn()` on
  view-creating fixtures.  The same test code runs in CI (offscreen,
  exits immediately) and interactively (visible window, server up for
  N seconds — `pytest --render-interactive=5`).

The trame-slicer pattern is the key insight: **the same test serves as
both formal automated regression and interactive developer
exploration**.  No divergence between test code and demo scripts; any
failing CI test can be re-run with a flag to debug visually.

Notably *neither* Kitware project uses pixel-perfect image regression
tests.  They assert behaviour (state of actors, MRML nodes, pipeline
outputs) — pixel comparison is flaky across drivers, Qt versions, and
hardware.

## Decision

v2.0.0 adopts the following testing architecture, applied to new code
and to migration code.  Existing tests stay in place until they need
maintenance or migration; new tests follow this discipline.

### 1. Test framework

- **Python primary**: `pytest`.  All new tests live in
  `Testing/Python/` under each module (or in a shared `tests/`
  directory for cross-module tests).  Slicer is imported as a Python
  library (`from slicer import vtkMRMLLiverResectionNode`), not
  launched as a GUI app.  Per ADR-0004, this is where most new tests
  go.
- **C++ secondary**: `ctkTest` (Qt MOC, `Q_OBJECT`, `private slots`
  pattern).  Used only for genuinely C++-only concerns: custom VTK
  mappers, low-level VTK observers, ITK filter behaviour that can't
  be exercised through Python.  Existing 6 `.cxx` tests remain; new
  C++ tests are added sparingly.
- CTest registers all of these (both pytest invocations and ctkTest
  executables) so a single `ctest` run executes the full suite.

### 2. Layered taxonomy

Four layers, each with explicit conventions:

| Layer | What | Slicer? | Qt? | render_interactive? | Example |
|---|---|---|---|---|---|
| **Unit** | Pure algorithm/math | No | No | N/A | Bezier basis evaluation on numpy arrays |
| **Module** | MRML scene + pipeline behaviour | Yes (import) | No | N/A (no widgets) | `GetSegmentByTerminology` returns the right segment |
| **Workflow** | Widget + scene + Qt interaction | Yes | Yes | **Yes** (default-on) | Resectogram view shows tumor cross-section contours |
| **C++ low-level** | VTK observer correctness, custom mapper output | Yes (link) | Yes (ctkTest) | **Yes** (`widget.show()`-aware) | Picked-point shader uniform updates on cursor move |

### 3. Dual-use mechanism (default-on)

The `render_interactive` mechanism is **default-on for every
view-creating fixture**.  Pattern (mirroring trame-slicer):

```python
# conftest.py
@pytest.fixture(scope="session")
def render_interactive(pytestconfig):
    return float(pytestconfig.getoption("--render-interactive"))

@pytest.fixture
def a_threed_view(a_view_manager, render_interactive):
    view = a_view_manager.create_view(...)
    if render_interactive:
        view.render_window().ShowWindowOn()
    view.interactor().UpdateSize(800, 600)
    yield view
    view.finalize()
```

Same discipline on the ctkTest side: view-creating tests pass an
"interactive" flag into a helper that conditionally calls
`widget.show()` and starts an event loop, vs running offscreen and
exiting after assertions.

Usage:
- CI: `pytest` → offscreen, fast.
- Developer iterating: `pytest --render-interactive=5 -k test_resectogram_widget` → onscreen for 5 seconds, assertions still run on close.
- Bug-repro on failing CI test: `pytest --render-interactive=300 -k test_failing_case` → 5 minutes to dig in.

This is also how *demos* work: there are no demo scripts separate from
tests.

### 4. Visualisation correctness — behaviour-only

Tests assert state of actors, MRML nodes, pipeline outputs.  No
pixel-perfect image regression.

Concrete assertion patterns:

- `assert view.render_window().GetRenderers().GetNumberOfItems() == 2`
- `assert pipeline.GetRenderOrder() == 5`
- `assert segmentation_node.GetSegmentation().GetNumberOfSegments() == 4`
- `assert resection_node.GetState() == vtkMRMLLiverResectionNode.Deformation`
- `assert marker_actor.GetVisibility() == 1`

Visual correctness (does it *look* right) is verified by humans via
the `render_interactive` flag during development and review — not by
the test harness.  Matches Kitware's discipline; avoids flaky
cross-driver pixel diffs.

### 5. Test data — via Slicer's SampleData mechanism

Tests download fixtures via Slicer's existing SampleData download
infrastructure (or a Slicer-Liver companion download server).  No
in-repo NIfTI / DICOM data; no git-LFS overhead.  CI runners must have
network access; downloads are cached between runs.

For tests that don't need realistic data, fixtures programmatically
generate scenes (synthetic Bezier control-point grids, simple vessel
trees) inline in `conftest.py`.

### 6. CI matrix — every PR runs everything

Per ADR-0005, GitHub Actions executes on every PR.  The CI job runs:

1. `pytest` — full Python test suite, offscreen.
2. `pytest --render-interactive=0.1` — full Python test suite, briefly
   onscreen (exercises the onscreen rendering path; catches
   driver/Qt regressions).
3. `ctest` — registered C++ executables, both offscreen and brief
   onscreen variants.

No nightly job needed — the test count is small enough.  When the
suite grows beyond a reasonable PR latency budget (≈15 minutes),
split into PR-fast + nightly-slow tiers.

### 7. Characterisation discipline (expanded from ADR-0003)

Per ADR-0003 already: every behaviour-changing PR ships with a test
that pins behaviour.  This ADR adds:

- **Bug-fix PRs** land a test that *first pins the broken behaviour*
  (`assert wrong_value` — passes on the bug commit), then the fix
  commit *inverts the assertion* (`assert right_value`).  Reviewers
  see the broken state recorded in history; the test catches
  regression.
- For larger migrations (the LayerDM phases per ADR-0002),
  characterisation tests land *before* the migration code: PR N adds
  the pinning test against the old behaviour; PR N+1 implements the
  migration and updates the test if behaviour is intentionally
  changed.

## Alternatives considered

### A. pytest-only — migrate existing C++ tests to Python

All tests become pytest-based.  Existing 6 `.cxx` files are ported via
Slicer's Python bindings; C++ survives only when there's literally no
Python access path.

**Rejected** because some low-level concerns (custom OpenGL mapper
output, VTK observer wire-up) are awkward through Python bindings.
ctkTest is mature, familiar to the Slicer ecosystem, and supports the
dual-use pattern natively via `widget.show()`.  Per-language fit
matters more than unifying the runner.

### B. Pixel-perfect image regression on golden paths

Add a small set of canonical workflow tests that compare rendered PNGs
against baselines, alongside behaviour assertions.

**Rejected** because pixel-perfect regression is flaky across GPU
drivers, OS, Qt versions, anti-aliasing.  Maintaining baselines is its
own labour cost, and broken baselines tend to be silently re-blessed
rather than investigated.  Behaviour assertions + the
`render_interactive` mechanism cover the same ground without the
flakiness tax.  If a specific rendering bug *truly* requires pixel
verification, add a one-off test then; don't institutionalise the
pattern.

### C. In-repo Testing/Data/ + git-LFS for clinical samples

Synthetic + small data committed directly; large clinical CT samples
in git-LFS.

**Rejected** because git-LFS adds infrastructure overhead (contributor
auth, CI clone awareness, storage cost) that the SampleData mechanism
avoids.  SampleData is the Slicer-ecosystem-native way to ship test
volumes; SlicerLiver should use it.  In-repo synthetic stays only for
fixture-generated cases (no separate `Testing/Data/` directory of
committed images).

### D. Tiered CI — PR-fast + nightly-slow

PR runs only fast offscreen tests; nightly runs slow + brief onscreen
+ characterisation against larger SampleData volumes.

**Rejected for now** because the current test count is small enough
to run end-to-end on every PR within a reasonable budget.  Revisit if
the suite ever grows past ≈15 minutes PR latency.

### E. No formal layer naming — trame-slicer-style fixture-driven

No explicit unit/module/workflow/C++ taxonomy; tests are categorised
only by which fixtures they consume.

**Rejected** because the explicit taxonomy makes coverage-gap
reasoning easier ("we have 12 module tests for `LiverResections` but
zero workflow tests").  Trame-slicer is small enough to live without;
SlicerLiver is large enough to benefit from the explicit signal.

## Consequences

### Easier

- **Bug-repro on failing CI** becomes a one-line operation:
  `pytest --render-interactive=300 -k <failing_test>`.  No more
  "can you reproduce locally?" round-trips between maintainer and
  reporter.
- **Demos collapse into tests.**  Every interactive demo of a feature
  is a workflow-layer test; the same code is used to onboard new
  contributors and to validate the feature in CI.
- **Coverage gaps are visible.**  The 4-layer taxonomy lets a reviewer
  ask "does this PR add module-layer coverage?" with a clear answer.
- **Migration safety**: characterisation tests landing *before*
  LayerDM migration PRs (per §7) bound regression risk during the
  multi-phase v2.0.0 work.

### Harder

- **Every view-creating fixture must respect `render_interactive`.**
  ~5–10 LOC per fixture; fixture-author effort is non-zero.
- **CI matrix runs both offscreen and brief onscreen variants.**
  Doubles the rendering surface area exercised per PR; adds a few
  minutes to PR latency.  Acceptable while test count stays small.
- **The SampleData download dependency adds network requirements to
  CI.**  Need to confirm GitHub Actions runners reach the SampleData
  endpoint; cache-between-runs setup needed.
- **Existing C++ tests don't yet follow the dual-use pattern.**  Not
  required to migrate them in v2.0.0 — they continue to work — but
  new C++ tests must adopt the pattern.

## References

- [SemVer 2.0.0](https://semver.org/) — version policy this strategy
  supports (per ADR-0007).
- [ADR-0002](0002-migrate-to-slicerlayerdm.md) — the migration this
  strategy bounds the regression risk of.
- [ADR-0003](0003-testability-invariant.md) — the *what* this ADR
  refines into a *how*.
- [ADR-0004](0004-python-cpp-boundary.md) — Python-by-default rule
  that this strategy implements on the test side.
- [ADR-0005](0005-github-actions-ci.md) — the CI substrate this
  strategy runs on.
- [ADR-0007](0007-version-numbering-policy.md) — the version policy
  that release-notes the test-driven evolution.
- [SlicerLayerDisplayableManager](https://github.com/KitwareMedical/SlicerLayerDisplayableManager)
  — three-tier test layout (`LayerDM/tests/`,
  `LayerDM/Testing/Python/`, `LayerDM/Testing/Cxx/`).
- [trame-slicer](https://github.com/KitwareMedical/trame-slicer) —
  fixture-driven pytest pattern + `render_interactive` mechanism.
  See `tests/conftest.py` for the canonical fixture set.

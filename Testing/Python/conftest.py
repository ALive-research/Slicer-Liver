# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""
Shared pytest scaffolding for Slicer-Liver (per ADR-0008).

This conftest implements the canonical `render_interactive` pattern adopted
from trame-slicer / SlicerLayerDisplayableManager.  The same test code serves
two audiences:

  * **CI / automated regression** — bare ``pytest`` runs offscreen; view
    fixtures never call ``ShowWindowOn()``; the suite completes as fast as
    possible.
  * **Developer interactive exploration** — ``pytest --render-interactive=5``
    yields visible Qt/VTK windows for 5 seconds per view-creating fixture,
    letting a human watch the same assertions execute on real pixels.  No
    parallel demo-script tree to maintain; the test *is* the demo.

The default for ``--render-interactive`` is **0.0** (offscreen).  Rationale:

  * Bare ``pytest`` must be safe for CI.  GitHub Actions runners drive Qt
    via ``QT_QPA_PLATFORM=offscreen`` (see ``.github/workflows/ci.yml``);
    a default-on flag would either hang on a missing DISPLAY or burn
    wall-clock waiting for invisible windows to time out.
  * ADR-0008 §6 specifies that CI explicitly runs the brief-onscreen
    variant by *passing* ``--render-interactive=0.1`` as a separate
    invocation — proving that the default for the bare invocation is OFF.
  * Developers iterating locally pass ``--render-interactive=5`` (or longer
    for bug-repro) by hand.  This matches trame-slicer's convention.

Layered test taxonomy (per ADR-0008 §2):

  * **unit/**     — pure-algorithm tests (no slicer import, no Qt)
  * **module/**   — MRML scene + pipeline behaviour (slicer imported as a
                    library; no Qt widgets)
  * **workflow/** — widget + scene + Qt interaction (consume view fixtures;
                    respect ``render_interactive``)

This scaffold lands the option, the session-scoped ``render_interactive``
fixture, and one example "Slicer-app boot" fixture demonstrating the dual-use
pattern.  The full per-module fixture set (``a_resection_node``,
``a_resectogram_view``, ``a_volumetry_node``, ``a_view_manager``,
``a_segmentation_with_terminology``, ...) lands in follow-up PRs as each
module's test surface migrates — see TODO markers below.

See:
  * Docs/adr/0008-testing-strategy.md  (the canonical strategy)
  * Docs/adr/0003-testability-invariant.md  (the discipline)
  * Docs/adr/0004-python-cpp-boundary.md   (Python-by-default for tests)
"""

from __future__ import annotations

import pytest


# --------------------------------------------------------------------------- #
# CLI option
# --------------------------------------------------------------------------- #

def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the ``--render-interactive`` CLI option.

    The option accepts a float number of seconds for which view-creating
    fixtures should keep a visible window onscreen before tearing down.
    A value of ``0`` (the default) keeps everything offscreen — the
    CI-safe path.

    Examples
    --------
    Bare CI run (offscreen, fast)::

        pytest

    Brief onscreen smoke (CI matrix's second pass, per ADR-0008 §6)::

        pytest --render-interactive=0.1

    Developer interactive run (windows visible for 5 s each)::

        pytest --render-interactive=5

    Bug-repro on a failing case (5 minutes of dwell time)::

        pytest --render-interactive=300 -k test_failing_case
    """
    group = parser.getgroup(
        "slicer-liver",
        "Slicer-Liver testing options (see Docs/adr/0008-testing-strategy.md)",
    )
    group.addoption(
        "--render-interactive",
        action="store",
        type=float,
        default=0.0,
        metavar="SECONDS",
        help=(
            "Keep view-creating fixtures' windows visible for SECONDS "
            "before teardown.  Default 0.0 (offscreen, CI-safe).  Pass a "
            "positive value (e.g. 5) for developer interactive exploration."
        ),
    )


# --------------------------------------------------------------------------- #
# Core fixture: the render_interactive switch
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="session")
def render_interactive(pytestconfig: pytest.Config) -> float:
    """Session-scoped float: seconds to keep view windows visible.

    A value of ``0.0`` means "offscreen, tear down immediately after
    assertions" — the CI default.  A positive value means "show the window
    that long before teardown" — the developer interactive default.

    Every view-creating fixture in this project's test tree must consume
    this fixture and respect its value, e.g.::

        @pytest.fixture
        def a_threed_view(a_view_manager, render_interactive):
            view = a_view_manager.create_view(...)
            if render_interactive:
                view.render_window().ShowWindowOn()
            view.interactor().UpdateSize(800, 600)
            yield view
            if render_interactive:
                view.interactor().Start()  # blocks for `render_interactive` s
            view.finalize()

    See ADR-0008 §3 for the full pattern.
    """
    return float(pytestconfig.getoption("--render-interactive"))


# --------------------------------------------------------------------------- #
# Example application-boot fixture
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="session")
def a_slicer_app():
    """Session-scoped handle to Slicer-imported-as-a-library.

    Per ADR-0004, the test discipline imports Slicer as a Python package
    (``import slicer``) rather than launching the Slicer GUI binary.  Tests
    that need an active MRML scene, the application logic singleton, or any
    Slicer-registered Python utility consume this fixture.

    When Slicer is unavailable (e.g. when running the unit-layer tests in a
    plain Python environment without a built Slicer), the fixture
    ``pytest.skip()``s the consuming test rather than erroring, so the
    scaffold can be exercised in isolation during development of the
    scaffold itself.

    Returns
    -------
    The ``slicer`` module object.  Tests typically destructure ``mrmlScene``,
    ``util``, or specific node classes from it.

    TODO (follow-up PRs):
      * Add fixtures ``a_mrml_scene`` (function-scoped, clears scene
        between tests) and ``a_clean_scene`` (alias kept for trame-slicer
        compatibility).
      * Add ``a_resection_node`` (LiverResections module fixture).
      * Add ``a_resectogram_view`` (LiverResections workflow fixture;
        consumes ``render_interactive``).
      * Add ``a_volumetry_node`` (LiverVolumetry module fixture).
      * Add ``a_view_manager`` (LayerDM view-factory fixture).
    """
    try:
        import slicer  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover — exercised only outside Slicer
        pytest.skip(
            f"slicer module not importable ({exc}); "
            "run this test inside Slicer's Python or via "
            "`Slicer --python-script $(which pytest) -- ...`."
        )
    return slicer


# --------------------------------------------------------------------------- #
# TODO (follow-up PRs) — fixture set to come
# --------------------------------------------------------------------------- #
#
# Per ADR-0008 §2 ("Layered taxonomy") and the trame-slicer precedent,
# the following fixtures land in subsequent PRs:
#
#   a_mrml_scene             — function-scoped clean scene
#   a_view_manager           — LayerDM view factory (workflow layer)
#   a_threed_view            — 3D view; consumes render_interactive
#   a_slice_view             — 2D slice view; consumes render_interactive
#   a_resection_node         — vtkMRMLLiverResectionNode + targets/markups
#   a_resectogram_view       — resectogram widget; consumes render_interactive
#   a_volumetry_node         — vtkMRMLLiverVolumetryNode + computed values
#   a_segmentation_with_terminology
#                            — SegmentationNode + SCT-coded segments
#                              (per ADR-0011 dispatch policy)
#   a_bezier_control_grid    — synthetic control grid for the algorithm
#                              characterisation tests flagged in ADR-0008
#                              §7 (bug-fix-PR pattern)
#
# Each landing PR also wires the module's tests under
# ``Testing/Python/<layer>/`` and updates the layer-specific CMake entries
# in ``Testing/Python/CMakeLists.txt``.

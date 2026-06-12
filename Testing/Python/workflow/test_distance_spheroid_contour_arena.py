# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Dual-mode interactive arena for the DistanceSpheroid contour shader.

This is the user-testing arena the maintainer asked for: an isolated,
minimal-``qSlicerApplication`` view that drives the **production**
``DistanceSpheroidInitRepresentation`` and renders its banded triaxial-
ellipsoid contour (ADR-0014 §2, ADR-0015 §"Stack 4").  The SAME scenario
runs two ways from one test body (ADR-0008 §3 dual-use pattern):

* **offscreen / CI** (``pytest`` default, ``render_interactive == 0``) —
  builds the view offscreen, runs the scenario, asserts the render
  pipeline came up without crashing, then tears down.
* **interactive** (``pytest --render-interactive=SECONDS`` with
  ``SECONDS > 0``) — shows the Qt window and starts the interactor so a
  human can rotate / inspect the banded spheroid for ``SECONDS`` before
  teardown.  "Better than a full-blown Slicer" for eyeballing the shader.

Harness placement (greppable skip reasons, mind #460)
-----------------------------------------------------
The test needs a live ``qSlicerApplication`` (Qt widget + MRML scene +
the registered LiverResections module so ``vtkMRMLBezierSurfaceNode`` is
instantiable and the contour mapper is wrapped onto the ``slicer``
namespace).  Bare ``PythonSlicer -m pytest`` has none of those, so the
test SKIPS CLEANLY there via the shared guards; it EXECUTES under the
launched-Slicer ``pytest_launched`` row (``Testing/Python`` is one of its
roots).  Every skip below prints an explicit, greppable reason — never a
silent skip — per the #460 launched-harness-silently-skips lesson.

Scenario source of truth
-------------------------
The scene + Representation wiring lives in the shared scenario module
``LiverResections/Testing/Python/scenarios/DistanceSpheroidContourShader``
that ``capture_baseline.py`` (interactive baseline) and ``replay_test.py``
(CI visual-regression) also consume.  This arena imports that exact
module so the interactive view, the CI replay, and the human capture all
render the identical scene.

See also
--------
* Docs/adr/0008-testing-strategy.md §3 (the dual-use render_interactive
  pattern), §6 (the CI matrix + launched harness).
* Docs/adr/0014-livermarkups-dissolution.md §2 (the DistanceSpheroidInit
  Representation + triaxial-ellipsoid contour).
"""

from __future__ import annotations

import pathlib
import sys

import pytest

from slicer_pytest_support import (
    import_slicer_or_skip,
    require_mrml_scene,
    require_qt_widget,
)


# Absolute path to the scenario package's parent so the scenario module
# imports under the same ``Python.scenarios.<name>`` dotted path the
# capture / replay drivers use.  Computed from this file's location:
# walk up to the repo root, then into the LiverResections test tree.
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_SCENARIO_PARENT = _REPO_ROOT / "LiverResections" / "Testing"
_SCENARIO_MODULE = "Python.scenarios.DistanceSpheroidContourShader"


def _load_scenario():
    """Import the shared DistanceSpheroidContourShader scenario module."""
    parent = str(_SCENARIO_PARENT)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    import importlib

    return importlib.import_module(_SCENARIO_MODULE)


def _first_renderer(view_widget):
    """Return the live ``vtkRenderer`` of the view widget's render window.

    ``qMRMLThreeDView.renderer()`` is C++-only (not PythonQt-wrapped); reach
    the renderer through the render-window's renderer collection, which is
    plain VTK and fully wrapped.  Same accessor capture_baseline.py uses.
    """
    return view_widget.threeDView().renderWindow().GetRenderers().GetFirstRenderer()


def test_distance_spheroid_contour_arena(render_interactive: float) -> None:
    """Render the production DistanceSpheroid contour; interactive or offscreen.

    The single test body adapts to both modes by branching on
    ``render_interactive`` (ADR-0008 §3) — the offscreen path tears the
    view down immediately, the interactive path shows the window and
    starts the interactor for ``render_interactive`` seconds.
    """
    slicer = import_slicer_or_skip()
    if slicer is None:
        return
    require_mrml_scene()
    require_qt_widget()

    # The scenario builds a vtkMRMLBezierSurfaceNode + drives the
    # production Representation, which resolves the wrapped contour mapper
    # off the ``slicer`` namespace.  ``require_mrml_scene`` above already
    # skipped the no-qSlicerApplication case; this guards the distinct
    # "live scene but the LiverResections module did not register" case
    # (module path missing) with an explicit, greppable skip reason.
    if slicer.mrmlScene.CreateNodeByClass("vtkMRMLBezierSurfaceNode") is None:
        pytest.skip(
            "[arena-skip] vtkMRMLBezierSurfaceNode is not registered -- the "
            "LiverResections module is not on the additional-module-paths.  "
            "Run via the pytest_launched CTest row (Liver/Testing/Python/"
            "CMakeLists.txt supplies the module paths)."
        )

    import qt  # type: ignore[import-not-found]

    scenario = _load_scenario()
    meta = scenario.describe()
    width, height = meta["viewport"]["size"]

    # Build the standalone view.  ``--no-main-window`` has no layout
    # manager, so construct the qMRMLThreeDWidget directly (the same
    # standalone-view pattern capture_baseline.py / replay_test.py use).
    view_widget = slicer.qMRMLThreeDWidget()
    view_widget.setMRMLScene(slicer.mrmlScene)
    view_node = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLViewNode")
    if view_node is None:
        view_node = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLViewNode", "SpheroidArenaView"
        )

    try:
        # Populate the scene + build the Representation BEFORE binding the
        # view node so the data node exists when the displayable-manager
        # group attaches.
        representation = scenario.setup_scene()
        assert representation is not None, (
            "scenario.setup_scene() returned None -- expected the "
            "DistanceSpheroidInitRepresentation handle."
        )

        # First render brings up the GL context + extension loader before
        # the contour mapper touches GL state (capture_baseline.py notes
        # the NULL-glGetError segfault when this ordering is violated).
        if render_interactive:
            view_widget.show()
        view_widget.threeDView().forceRender()
        view_widget.setMRMLViewNode(view_node)

        # Attach the production Representation's actors to the live
        # renderer, then fix camera + viewport (which also enables the
        # contour band on the mapper the Representation owns).
        scenario.attach_to_renderer(_first_renderer(view_widget))
        scenario.setup_camera(view_node)
        scenario.setup_viewport(view_node)

        view_widget.resize(width, height)
        view_widget.threeDView().renderWindow().SetSize(width, height)
        view_widget.threeDView().renderWindow().SetMultiSamples(0)
        view_widget.threeDView().forceRender()

        # Offscreen assertion: the pipeline produced a render window of the
        # requested size with the Representation's spheroid actor attached.
        # This is the "renders without crashing" gate the CI mode needs;
        # the pixel-level comparison is the replay_test.py CTest's job.
        renderer = _first_renderer(view_widget)
        assert renderer is not None, "no live renderer on the view widget"
        spheroid_actor = representation.GetSpheroidActor()
        assert spheroid_actor is not None, (
            "the Representation has no spheroid actor -- VTK pipeline not "
            "constructed (is VTK importable inside this Slicer?)."
        )
        assert renderer.HasViewProp(spheroid_actor), (
            "the Representation's spheroid actor is not attached to the live "
            "renderer -- attach_to_renderer() did not wire it."
        )

        # The mapper the Representation drives must be the production
        # contour mapper with the SSOT quadric bound (not the generic
        # fallback) when running inside a real Slicer.
        mapper = representation.GetSpheroidMapper()
        assert mapper is not None, "the Representation has no spheroid mapper"
        get_quadric = getattr(mapper, "GetSpheroidQuadricCoefficients", None)
        assert get_quadric is not None, (
            "the Representation's spheroid mapper is the generic fallback, "
            "not vtkOpenGLDistanceContourPolyDataMapper -- the relocated "
            "mapper is not wrapped onto the slicer namespace in this build."
        )

        if render_interactive:
            # Interactive arena: keep the window up and let the human drive
            # the camera.  A single-shot timer quits the nested event loop
            # after the requested dwell so the test still terminates under
            # CI's brief-onscreen pass (--render-interactive=0.1).
            interactor = view_widget.threeDView().interactor()
            if interactor is not None:
                loop = qt.QEventLoop()
                qt.QTimer.singleShot(int(render_interactive * 1000), loop.quit)
                interactor.Initialize()
                view_widget.threeDView().forceRender()
                loop.exec_()
    finally:
        # Tear the Representation + widget down so no actor / node survives
        # to process exit and trips vtkDebugLeaks in the launched harness
        # (the LiverResections conftest's _launched_scene_cleanup clears
        # the scene; the standalone widget + Representation are ours).
        try:
            representation.cleanup()
        except Exception:  # noqa: BLE001 -- teardown must not mask a failure
            pass
        view_widget.setMRMLScene(None)
        view_widget.deleteLater()

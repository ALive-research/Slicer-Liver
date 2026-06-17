# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Dual-mode interactive arena for the T3 resectogram appearance.

The user-testing arena for the resectogram: an isolated, minimal-
``qSlicerApplication`` 3D view that builds the deterministic resectogram
scene (the flattened 2D image of the Bezier ``(u, v)`` domain, ADR-0025
§Context) and lets the maintainer eyeball the blur-on/off + non-square
aspect-ratio appearances on a GPU.  The SAME body runs two ways from one
test (ADR-0008 §3 dual-use pattern):

* **offscreen / CI** (``pytest`` default, ``render_interactive == 0``) —
  builds the view offscreen, runs the scenario, asserts the render
  pipeline came up and the resectogram display wiring is in place, then
  tears down.
* **interactive** (``pytest --render-interactive=SECONDS`` with
  ``SECONDS > 0``) — shows the Qt window and starts the interactor so a
  human can inspect the resectogram for ``SECONDS`` before teardown.  Run
  with ``-k`` to pick blur-on / blur-off / non-square.

Harness placement (greppable skip reasons, mind #460)
-----------------------------------------------------
Needs a live ``qSlicerApplication`` (Qt widget + MRML scene + the
registered LiverResections + LiverMarkups modules so the Bezier node + the
resectogram render path are available).  Bare ``PythonSlicer -m pytest``
has none of those, so the test SKIPS CLEANLY there via the shared guards;
it EXECUTES under the launched-Slicer ``pytest_launched`` row.  Every skip
prints an explicit, greppable reason — never a silent skip — per the #460
launched-harness-silently-skips lesson.

Capture-then-rebaseline note
----------------------------
The scenarios first render against the v1 monolith resectogram path (the
legacy ``vtkMRMLMarkupsBezierSurfaceDisplayNode`` resectogram fields), then
re-baseline to the v2.0 ResectogramPipeline at the implementer's go-live
step.  This arena drives whatever path is live; the structural assertions
below are path-agnostic (a 3D renderer + the Bezier node's display nodes),
and the lit-pixel verdict is GPU-gated.

Scenario source of truth
-------------------------
The scene wiring lives in the shared scenario modules under
``LiverResections/Testing/Python/scenarios/Resectogram4x4*`` that
``capture_baseline.py`` (interactive baseline) and ``replay_test.py`` (CI
visual-regression) also consume.  This arena imports those exact modules
so the interactive view, the CI replay, and the human capture all render
the identical scene.

See also
--------
* Docs/adr/0008-testing-strategy.md §3 (the dual-use render_interactive
  pattern), §6 (the CI matrix + launched harness).
* Docs/adr/0013-layerdm-pipeline-pattern.md §6 (the flattened-surface
  Representation owned by the ResectogramPipeline).
* Testing/Python/workflow/test_distance_spheroid_contour_arena.py (the
  arena pattern + the hard-won software-GL / vtkDebugLeaks safety guards
  this file copies).
"""

from __future__ import annotations

import importlib
import pathlib
import sys

import pytest

from slicer_pytest_support import (
    import_slicer_or_skip,
    require_mrml_scene,
    require_qt_widget,
)


# Absolute path to the scenario package's parent so the scenario modules
# import under the same ``Python.scenarios.<name>`` dotted path the
# capture / replay drivers use.  Computed from this file's location: walk
# up to the repo root, then into the LiverResections test tree.
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_SCENARIO_PARENT = _REPO_ROOT / "LiverResections" / "Testing"

# The three T3 resectogram scenarios this arena can render.  Parametrised
# so ``pytest -k NonSquare`` (etc.) picks one for interactive inspection.
_SCENARIOS = (
    "Resectogram4x4BlurOff",
    "Resectogram4x4NonSquareScaling",
    "Resectogram4x4BlurOn",
)


def _load_scenario(name: str):
    """Import a shared resectogram scenario module by name."""
    parent = str(_SCENARIO_PARENT)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    return importlib.import_module(f"Python.scenarios.{name}")


def _first_renderer(view_widget):
    """Return the live ``vtkRenderer`` of the view widget's render window.

    ``qMRMLThreeDView.renderer()`` is C++-only (not PythonQt-wrapped); reach
    the renderer through the render-window's renderer collection, which is
    plain VTK and fully wrapped.  Same accessor capture_baseline.py uses.
    """
    return view_widget.threeDView().renderWindow().GetRenderers().GetFirstRenderer()


def _visible_pixel_count(view_widget) -> int:
    """Count non-background pixels in the view's rendered back buffer.

    Snapshots the GL back buffer with ``vtkWindowToImageFilter`` (the same
    pixel source ``capture_baseline.py`` / ``replay_test.py`` use, so this
    counts exactly the pixels the visual-regression baseline pins) and
    returns how many are non-black (the scenario background is ``(0,0,0)``).
    Channel value > 8 tolerates only single-LSB dithering, not a lit
    fragment.
    """
    import vtk  # type: ignore[import-not-found]
    from vtk.util import numpy_support  # type: ignore[import-not-found]

    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(view_widget.threeDView().renderWindow())
    w2i.SetInputBufferTypeToRGB()
    w2i.ReadFrontBufferOff()
    w2i.SetShouldRerender(0)  # already-rendered back buffer
    w2i.Update()
    scalars = w2i.GetOutput().GetPointData().GetScalars()
    arr = numpy_support.vtk_to_numpy(scalars)
    return int((arr.max(axis=1) > 8).sum())


_SOFTWARE_GL_MARKERS = ("llvmpipe", "softpipe", "swrast", "software rasterizer")


def _software_gl_skip_reason() -> str | None:
    """Return a greppable skip reason on a software-GL stack, else None.

    Brings up a throwaway offscreen ``vtkRenderWindow`` and reads its
    ``ReportCapabilities`` -- the same cheap probe the replay driver
    (``LiverResections/Testing/Python/replay_test.py``) uses.  Probing a
    *throwaway* window before the live view is built keeps this off the
    arena's own (possibly context-failed) render window, and lets the test
    skip BEFORE attempting a render the software stack cannot light.  Any
    probe failure is treated as un-renderable (skip), never a crash.
    """
    import vtk  # type: ignore[import-not-found]

    render_window = None
    try:
        render_window = vtk.vtkRenderWindow()
        render_window.SetOffScreenRendering(1)
        render_window.SetSize(1, 1)
        render_window.SetMultiSamples(0)
        render_window.Render()
        capabilities = (render_window.ReportCapabilities() or "").lower()
    except Exception:  # noqa: BLE001 -- any failure means "cannot render here".
        return "[arena-skip] offscreen GL context could not be created"
    finally:
        if render_window is not None:
            render_window.Finalize()
    match = next((m for m in _SOFTWARE_GL_MARKERS if m in capabilities), None)
    if match is not None:
        return (
            f"[arena-skip] offscreen software GL ({match}) -- the resectogram "
            "render path does not reliably light fragments on a software "
            "rasteriser; the lit-pixel verdict is deferred to a GPU-backed "
            "display."
        )
    return None


@pytest.mark.parametrize("scenario_name", _SCENARIOS)
def test_resectogram_arena(scenario_name: str, render_interactive: float) -> None:
    """Render a T3 resectogram scenario; interactive or offscreen.

    The single body adapts to both modes by branching on
    ``render_interactive`` (ADR-0008 §3) — the offscreen path tears the
    view down immediately after the structural assertions, the interactive
    path shows the window and starts the interactor for
    ``render_interactive`` seconds.

    Parametrised over the three T3 resectogram scenarios so the maintainer
    can ``pytest --render-interactive=N -k <scenario>`` to inspect any one
    on a GPU.
    """
    slicer = import_slicer_or_skip()
    if slicer is None:
        return
    require_mrml_scene()
    require_qt_widget()

    # The scenario builds a vtkMRMLMarkupsBezierSurfaceNode + enables the
    # resectogram strip on its display node.  Guard the distinct "live
    # scene but the modules did not register" case with an explicit,
    # greppable skip reason (module path missing).
    registration_probe = slicer.mrmlScene.CreateNodeByClass(
        "vtkMRMLMarkupsBezierSurfaceNode"
    )
    if registration_probe is None:
        pytest.skip(
            "[arena-skip] vtkMRMLMarkupsBezierSurfaceNode is not registered -- "
            "the LiverResections / LiverMarkups modules are not on the "
            "additional-module-paths.  Run via the pytest_launched CTest row "
            "(Liver/Testing/Python/CMakeLists.txt supplies the module paths)."
        )
    # CreateNodeByClass returns a node with the factory's +1 reference that the
    # caller owns; drop it, or the probe instance survives to process shutdown
    # and trips vtkDebugLeaks (failing the launched harness) even when the test
    # later skips on a software-GL stack.
    registration_probe.UnRegister(None)

    # Software-GL gate (CI's xvfb + llvmpipe): the resectogram render path
    # does not reliably light fragments on a software rasteriser, and the
    # offscreen render itself is unreliable there.  Probe a throwaway context
    # and skip BEFORE building/rendering the live view so the test reports a
    # real, greppable SKIP rather than a false pass or a render crash.  The
    # lit-pixel verdict is on a GPU-backed display.
    software_gl_skip = _software_gl_skip_reason()

    import qt  # type: ignore[import-not-found]

    scenario = _load_scenario(scenario_name)
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
            "vtkMRMLViewNode", "ResectogramArenaView"
        )

    created_nodes = None
    try:
        # Populate the scene (markups Bezier node + distance map + the
        # resectogram-enabled display node).  setup_scene returns the
        # created nodes so nothing leaks through a module global.
        created_nodes = scenario.setup_scene()
        assert created_nodes is not None, (
            "scenario.setup_scene() returned None -- expected the created "
            "node handles (the no-module-globals contract)."
        )
        bezier_node = created_nodes[0]
        assert bezier_node is not None, (
            "scenario.setup_scene() did not return a Bezier node handle."
        )

        # Map the view's GL surface BEFORE binding the view node so the
        # displayable-manager group attaches.  Under
        # ``QT_QPA_PLATFORM=offscreen`` show() is visually a no-op but still
        # maps the OpenGL surface + creates the default light; without it the
        # offscreen back buffer renders empty.  Same show()-then-render
        # ordering capture_baseline.py uses.
        view_widget.show()
        view_widget.threeDView().forceRender()
        view_widget.setMRMLViewNode(view_node)

        scenario.setup_camera(view_node)
        scenario.setup_viewport(view_node)

        # The standalone qMRMLThreeDWidget (no layout manager) does not
        # honour the orphan MRML camera/view nodes the scenario configured,
        # so push the scenario's deterministic camera pose + flat black
        # background straight onto the live renderer -- the same thing
        # capture_baseline.py / replay do -- so the offscreen frame matches
        # the captured baseline and the visible-pixel count reflects lit
        # resectogram fragments, not a non-black gradient.
        renderer = _first_renderer(view_widget)
        camera = renderer.GetActiveCamera()
        camera_spec = meta["camera"]
        camera.SetPosition(*camera_spec["position"])
        camera.SetFocalPoint(*camera_spec["focal_point"])
        camera.SetViewUp(*camera_spec["view_up"])
        camera.SetViewAngle(camera_spec["view_angle"])
        camera.SetClippingRange(*camera_spec["clipping_range"])
        background = meta["viewport"]["background"]
        renderer.SetBackground(*background)
        renderer.SetBackground2(*background)

        view_widget.resize(width, height)
        view_widget.threeDView().renderWindow().SetSize(width, height)
        view_widget.threeDView().renderWindow().SetMultiSamples(0)
        view_widget.threeDView().forceRender()

        # ---- Structural wiring assertions (ALWAYS-ON, path-agnostic) ----
        # These run regardless of the GL stack: a live renderer, the Bezier
        # node's display node, and the resectogram strip enabled on it.
        assert renderer is not None, "no live renderer on the view widget"

        display_node = bezier_node.GetDisplayNode()
        assert display_node is not None, (
            "the Bezier node has no display node -- the scenario did not "
            "create the resectogram display wiring."
        )
        # The resectogram strip must be enabled (the whole point of the
        # scenario).  ShowResection2D lives on the legacy markups display
        # node (the v1 resectogram render path reads it); probe by accessor
        # so the assertion is robust across the v1->v2 display-node
        # migration.
        get_show_2d = getattr(display_node, "GetShowResection2D", None)
        assert get_show_2d is not None, (
            "the resectogram display node has no GetShowResection2D accessor "
            "-- the scenario is not driving a resectogram-capable display "
            "node (ADR-0025 §Context)."
        )
        assert get_show_2d(), (
            "ShowResection2D is OFF on the display node -- the scenario did "
            "not enable the resectogram strip."
        )

        # ---- Lit-pixel verdict (GPU-gated) ----
        # The resectogram render path does not reliably light fragments on a
        # software rasteriser; defer the pixel verdict to a GPU-backed
        # display.  The structural assertions above already ran.
        if software_gl_skip is not None:
            pytest.skip(software_gl_skip)

        try:
            import numpy  # type: ignore[import-not-found]  # noqa: F401
            from vtk.util import numpy_support  # type: ignore[import-not-found]  # noqa: F401
        except ImportError:
            pytest.skip(
                "[arena-skip] numpy / vtk.util.numpy_support unavailable -- "
                "cannot read the rendered back buffer for the visible-pixel "
                "assertion.  Structural wiring above already passed."
            )
        visible = _visible_pixel_count(view_widget)
        # A generous 1 % floor still fails hard on an all-black frame while
        # tolerating the resectogram strip occupying only part of the panel.
        min_visible = int(0.01 * width * height)
        assert visible >= min_visible, (
            f"the resectogram rendered only {visible} lit pixels "
            f"(< {min_visible}) -- the flattened strip is not visibly drawn.  "
            "Expected the live resectogram path to light the (u, v) panel."
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
        # Tear the widget + scene down so no actor / node survives to process
        # exit and trips vtkDebugLeaks in the launched harness (the
        # LiverResections conftest's _launched_scene_cleanup clears the scene;
        # the standalone widget is ours).
        view_widget.setMRMLScene(None)
        view_widget.deleteLater()
        slicer.mrmlScene.Clear(0)

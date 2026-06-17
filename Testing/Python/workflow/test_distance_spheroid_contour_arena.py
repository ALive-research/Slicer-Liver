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


def _visible_pixel_count(view_widget) -> int:
    """Count non-background pixels in the view's rendered back buffer.

    Snapshots the GL back buffer with ``vtkWindowToImageFilter`` (the same
    pixel source ``capture_baseline.py`` / ``replay_test.py`` use, so this
    counts exactly the pixels the visual-regression baseline pins) and
    returns how many are non-black (the scenario background is ``(0,0,0)``;
    the contour band is white at opacity 1).  Channel value > 8 tolerates
    only single-LSB dithering, not a lit fragment.
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
            f"[arena-skip] offscreen software GL ({match}) -- the production "
            "contour fragment shader does not light fragments on a software "
            "rasteriser; the lit-pixel verdict is deferred to a GPU-backed "
            "display."
        )
    return None


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
    registration_probe = slicer.mrmlScene.CreateNodeByClass(
        "vtkMRMLBezierSurfaceNode"
    )
    if registration_probe is None:
        pytest.skip(
            "[arena-skip] vtkMRMLBezierSurfaceNode is not registered -- the "
            "LiverResections module is not on the additional-module-paths.  "
            "Run via the pytest_launched CTest row (Liver/Testing/Python/"
            "CMakeLists.txt supplies the module paths)."
        )
    # CreateNodeByClass returns a node with the factory's +1 reference that the
    # caller owns; drop it, or the probe instance survives to process shutdown
    # and trips vtkDebugLeaks (failing the launched harness) even when the test
    # later skips on a software-GL stack.
    registration_probe.UnRegister(None)

    # Software-GL gate (CI's xvfb + llvmpipe): the custom contour fragment
    # shader does not light fragments on a software rasteriser, and the
    # offscreen render itself is unreliable there -- the same limitation the
    # bezier distance-map render meets.  Probe a throwaway context and skip
    # BEFORE building/rendering the live view so the test reports a real,
    # greppable SKIP rather than a false pass or a render crash.  The
    # lit-pixel verdict is on a GPU-backed display.
    software_gl_skip = _software_gl_skip_reason()
    if software_gl_skip is not None:
        pytest.skip(software_gl_skip)

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

        # Map the view's GL surface BEFORE the first render.  Under
        # ``QT_QPA_PLATFORM=offscreen`` (CI + launched harness) ``show()``
        # is visually a no-op but still maps the OpenGL surface + creates
        # the default light; without it the offscreen back buffer renders
        # empty (no light, unmapped swapchain), which is why the pixel
        # assertion below would otherwise see zero lit fragments.  This is
        # the same show()-then-render ordering capture_baseline.py uses.
        # First render also brings up the GL context + extension loader
        # before the contour mapper touches GL state (capture_baseline.py
        # notes the NULL-glGetError segfault when this ordering is
        # violated).
        view_widget.show()
        view_widget.threeDView().forceRender()
        view_widget.setMRMLViewNode(view_node)

        # Attach the production Representation's actors to the live
        # renderer, then fix camera + viewport (which also enables the
        # contour band on the mapper the Representation owns).
        scenario.attach_to_renderer(_first_renderer(view_widget))
        scenario.setup_camera(view_node)
        scenario.setup_viewport(view_node)

        # The standalone qMRMLThreeDWidget (no layout manager in
        # --no-main-window) does not honour the orphan MRML camera/view
        # nodes the scenario just configured, so the live VTK camera keeps
        # its default pose + the renderer keeps its default GRADIENT
        # background.  Push the scenario's deterministic camera pose and a
        # flat black background straight onto the live renderer -- the same
        # thing capture_baseline.py / replay do -- so (a) the offscreen
        # frame matches the captured baseline pixel-for-pixel and (b) the
        # visible-pixel count below reflects the lit contour fragments, not
        # a non-black gradient that would pass the assertion trivially.
        meta = scenario.describe()
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

        # Offscreen assertion: the pipeline produced a render window of the
        # requested size with the Representation's spheroid actor attached.
        # This is the "renders without crashing" gate the CI mode needs;
        # the pixel-level comparison is the replay_test.py CTest's job.
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

        # Visible-pixel assertion: the contour band must actually draw.
        # The production Representation enables ``ContourVisibility`` once it
        # has a spheroid to show (ADR-0014 §2); the mapper's fragment shader
        # discards every fragment while visibility is off, so a regression
        # that drops the visibility toggle -- or breaks the SSOT quadric so
        # ``abs(F) >= thickness`` everywhere -- renders an all-black frame.
        # Count the lit pixels off the same back buffer the visual baseline
        # pins and require a non-trivial fraction of the triaxial ellipsoid
        # to be banded.  ``numpy`` ships with Slicer; guard the rare absence
        # with an explicit, greppable ``[arena-skip]`` reason (per this
        # module's greppable-skip-reasons convention) rather than a silent
        # pass.
        try:
            import numpy  # type: ignore[import-not-found]  # noqa: F401
            from vtk.util import numpy_support  # type: ignore[import-not-found]  # noqa: F401
        except ImportError:
            pytest.skip(
                "[arena-skip] numpy / vtk.util.numpy_support unavailable -- "
                "cannot read the rendered back buffer for the visible-pixel "
                "assertion.  Pipeline wiring above already passed."
            )
        visible = _visible_pixel_count(view_widget)
        # ~8-9 % of the 800x600 frame is the ellipsoid silhouette at the
        # scenario's fixed camera pose; 1 % (4800 px) is a generous floor
        # that still fails hard on an all-black frame (the pre-fix state).
        min_visible = int(0.01 * width * height)
        assert visible >= min_visible, (
            f"the contour band rendered only {visible} lit pixels "
            f"(< {min_visible}) -- the triaxial ellipsoid is not visibly "
            "drawn.  Expected the production Representation to enable "
            "ContourVisibility and the SSOT quadric to band the surface."
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

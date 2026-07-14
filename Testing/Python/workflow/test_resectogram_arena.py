# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Two-view interactive arena for the T3 resectogram appearance + content.

The user-testing arena for the resectogram.  It builds the deterministic
resectogram scene (the flattened 2D image of the Bezier ``(u, v)`` domain,
ADR-0025 §Context) into TWO isolated, minimal-``qSlicerApplication`` 3D
views and lets the maintainer eyeball the blur-on/off + non-square
aspect-ratio appearances on a GPU:

* a **scene view** — a normal ``vtkMRMLViewNode`` showing the 3D anatomy
  (the parenchyma sphere + the Bezier surface + its markers), and
* the **resectogram view** — the dedicated ``"LiverResectogram"``-tagged
  view (the Hyperprobe custom-layout pattern, ADR-0023 §Stage-4) showing
  ONLY the flattened resectogram strip.

The maintainer chose two physically separate ``qMRMLThreeDWidget`` views
(rather than one shared view) so the 3D anatomy and the flattened strip
never co-mingle in one renderer: per-display-node ``ViewNodeIDs``
restriction binds each display node to exactly one view, and the arena
asserts the renderer-level separation (no anatomy actor in the resectogram
renderer; no strip actor in the scene renderer).

The SAME body runs two ways from one test (ADR-0008 §3 dual-use pattern):

* **offscreen / CI** (``pytest`` default, ``render_interactive == 0``) —
  builds both views offscreen, runs the scenario, asserts the render
  pipeline came up, the resectogram display wiring is in place, the two
  views are separated, and the resectogram view draws the actual margin
  BAND (not just the wireframe grid + border), then tears down.
* **interactive** (``pytest --render-interactive=SECONDS`` with
  ``SECONDS > 0``) — shows both Qt windows and starts the interactors so a
  human can inspect the resectogram for ``SECONDS`` before teardown.  Run
  with ``-k`` to pick blur-on / blur-off / non-square.

The band-content gate (RED-by-design, ADR-0027)
------------------------------------------------
Beyond "any lit pixels", the arena pins a CONTENT invariant: the
resectogram view must render the projected distance-map margin BAND, not
merely the flattened wireframe grid + coloured borders.  The earlier "≥1 %
lit pixels" floor was too lenient — the grid + border alone clear it even
when no texture is bound.  The new metric (``_interior_lit_fraction``)
counts lit pixels in the strip INTERIOR (a margin around the panel edge is
excluded), where a bare grid + border leaves the interior essentially
empty but a textured margin band fills a contiguous interior region.  The
scenario's deterministic 4-component distance map yields a deterministic
band, so the interior-lit fraction is a stable discriminator.

This gate is RED TODAY: ``FlattenedSurfaceRepresentation`` does not bind
the distance-map texture (no ``SetDistanceMapTextureObject`` / ras-ijk
matrices; the T3-e rewrite severed v1's texture path), so the strip
interior is empty (grid + border only).  It goes GREEN once the implementer
binds the distance-map texture so the projected margin band fills the
``(u, v)`` panel interior (ADR-0025 §Context).  The verdict is GPU-gated —
the software-GL rasteriser does not reliably light the band — so it carries
the same software-GL skip the lit-pixel verdict always did; it needs
launched/GPU verification.

Harness placement (greppable skip reasons, mind #460)
-----------------------------------------------------
Needs a live ``qSlicerApplication`` (Qt widget + MRML scene + the
registered LiverResections module so the Bezier node + the
resectogram render path are available).  Bare ``PythonSlicer -m pytest``
has none of those, so the test SKIPS CLEANLY there via the shared guards;
it EXECUTES under the launched-Slicer ``pytest_launched`` row.  Every skip
prints an explicit, greppable reason — never a silent skip — per the #460
launched-harness-silently-skips lesson.

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
* Docs/adr/0023-resection-plan-architecture.md §Stage-4 (the dedicated
  resectogram view as the one custom Slicer layout v2.0 ships).
* Docs/adr/0025-locator-architecture.md §Context (the resectogram is the
  flattened ``(u, v)`` distance-map image).
* Testing/Python/workflow/test_resectogram_pipeline_dispatch.py (the
  ``_first_renderer`` / ``GetAddressAsString`` renderer-ownership identity
  pattern this file reuses for the two-view separation).
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
    plain VTK and fully wrapped.  Same accessor capture_baseline.py and the
    dispatch tests (``test_resectogram_pipeline_dispatch.py``) use.
    """
    return view_widget.threeDView().renderWindow().GetRenderers().GetFirstRenderer()


def _renderer_owns_actor(renderer, actor) -> bool:
    """Whether ``actor`` is in ``renderer``'s actor collection.

    Walks ``GetActors()`` by VTK-object identity (the C++ pointer the
    wrapper reports via ``GetAddressAsString("")``) rather than Python
    ``is`` — PythonQt/VTK can hand back distinct Python wrappers around the
    same C++ ``vtkProp``, so identity must be compared at the C++ level.
    Same identity pattern as ``test_resectogram_pipeline_dispatch.py``.
    """
    if renderer is None or actor is None:
        return False
    target = actor.GetAddressAsString("")
    actors = renderer.GetActors()
    actors.InitTraversal()
    for _ in range(actors.GetNumberOfItems()):
        candidate = actors.GetNextActor()
        if candidate is not None and candidate.GetAddressAsString("") == target:
            return True
    return False


def _renderer_actor_addresses(renderer) -> set[str]:
    """Return the set of C++ actor addresses in ``renderer``.

    The renderer-level companion to ``_renderer_owns_actor`` for the
    two-view separation assertions: snapshots one renderer's actor identity
    set so the other view's actors can be tested for absence by address
    (ADR-0023 §Stage-4 — anatomy and the flattened strip must not co-mingle
    in one renderer).
    """
    addresses: set[str] = set()
    if renderer is None:
        return addresses
    actors = renderer.GetActors()
    actors.InitTraversal()
    for _ in range(actors.GetNumberOfItems()):
        candidate = actors.GetNextActor()
        if candidate is not None:
            addresses.add(candidate.GetAddressAsString(""))
    return addresses


def _lit_mask(view_widget):
    """Return a boolean H×W numpy mask of non-background pixels.

    Snapshots the GL back buffer with ``vtkWindowToImageFilter`` (the same
    pixel source ``capture_baseline.py`` / ``replay_test.py`` use, so this
    reads exactly the pixels the visual-regression baseline pins) and marks
    each pixel whose brightest channel exceeds 8 (the scenario background is
    ``(0,0,0)``; the >8 threshold tolerates only single-LSB dithering, not a
    lit fragment).  Shaped ``(height, width)`` so the band metric can carve
    out an interior region.
    """
    import vtk  # type: ignore[import-not-found]
    from vtk.util import numpy_support  # type: ignore[import-not-found]

    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(view_widget.threeDView().renderWindow())
    w2i.SetInputBufferTypeToRGB()
    w2i.ReadFrontBufferOff()
    w2i.SetShouldRerender(0)  # already-rendered back buffer
    w2i.Update()
    image = w2i.GetOutput()
    cols, rows, _ = image.GetDimensions()
    scalars = image.GetPointData().GetScalars()
    arr = numpy_support.vtk_to_numpy(scalars).reshape(rows, cols, -1)
    return arr.max(axis=2) > 8


def _visible_pixel_count(view_widget) -> int:
    """Count non-background pixels in the view's rendered back buffer.

    The structural lit-pixel floor (any visible fragment).  Distinct from
    the band-content metric below: this only proves the strip drew SOMETHING
    (grid + border qualify); the band metric proves it drew the margin BAND.
    """
    return int(_lit_mask(view_widget).sum())


def _interior_lit_fraction(view_widget, border_frac: float = 0.18) -> float:
    """Return the lit fraction of the panel INTERIOR (the band-content metric).

    The content gate that distinguishes a textured margin band from a bare
    flattened grid + coloured border (ADR-0025 §Context — the resectogram is
    the flattened ``(u, v)`` distance-map image; the band IS the projected
    distance map, not the wireframe).

    Why interior-only discriminates band-from-grid
    -----------------------------------------------
    The flattened-surface Representation always draws the ``(u, v)`` quad
    GRID (a sparse wireframe) and the coloured resection BORDERS (the panel
    edges).  Those clear a whole-frame "≥1 % lit" floor on their own — the
    earlier, too-lenient gate.  But they are confined to the panel PERIMETER
    and the thin grid lines: the panel INTERIOR (everything inside a
    ``border_frac`` margin from each edge) stays dark when no distance-map
    texture is bound.  A bound distance-map texture, by contrast, paints the
    projected margin band as a CONTIGUOUS fill across that interior.  So the
    interior-lit fraction separates the two regimes:

    * grid + border only  → interior fraction ≈ 0 (a few stray grid pixels),
    * textured margin band → interior fraction well above the floor.

    ``border_frac`` (default 0.18) excludes the outer 18 % of the panel on
    every side, leaving a centred interior window safely clear of the
    coloured borders + the outermost grid lines for the scenario's fixed
    camera pose.  The band fills a deterministic region because the
    scenario's 4-component distance map is deterministic.

    Returns the fraction in ``[0, 1]`` of interior pixels that are lit.
    """
    mask = _lit_mask(view_widget)
    rows, cols = mask.shape
    margin_r = int(border_frac * rows)
    margin_c = int(border_frac * cols)
    interior = mask[margin_r : rows - margin_r, margin_c : cols - margin_c]
    if interior.size == 0:
        return 0.0
    return float(interior.sum()) / float(interior.size)


_SOFTWARE_GL_MARKERS = ("llvmpipe", "softpipe", "swrast", "software rasterizer")


def _software_gl_skip_reason() -> str | None:
    """Return a greppable skip reason on a software-GL stack, else None.

    Brings up a throwaway offscreen ``vtkRenderWindow`` and reads its
    ``ReportCapabilities`` -- the same cheap probe the replay driver
    (``LiverResections/Testing/Python/replay_test.py``) uses.  Probing a
    *throwaway* window before the live views are built keeps this off the
    arena's own (possibly context-failed) render windows, and lets the test
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
            "rasteriser; the band-content verdict is deferred to a GPU-backed "
            "display."
        )
    return None


def _build_view_widget(slicer, scene, view_node):
    """Build + map a standalone ``qMRMLThreeDWidget`` bound to ``view_node``.

    ``--no-main-window`` has no layout manager, so construct the
    ``qMRMLThreeDWidget`` directly (the same standalone-view pattern
    capture_baseline.py / replay_test.py and the dispatch fixtures use).
    Maps the GL surface (``show()`` + ``forceRender()``) BEFORE binding the
    view node so the LayerDM displayable-manager group attaches.  Under
    ``QT_QPA_PLATFORM=offscreen`` show() is visually a no-op but still maps
    the OpenGL surface; without it the offscreen back buffer renders empty.
    """
    widget = slicer.qMRMLThreeDWidget()
    widget.setMRMLScene(scene)
    widget.show()
    widget.threeDView().forceRender()
    widget.setMRMLViewNode(view_node)
    return widget


def _apply_camera_and_background(renderer, meta) -> None:
    """Push the scenario's deterministic camera pose + flat background.

    The standalone ``qMRMLThreeDWidget`` (no layout manager) does not honour
    the orphan MRML camera/view nodes the scenario configured, so push the
    scenario's deterministic camera pose + flat black background straight
    onto the live renderer -- the same thing capture_baseline.py / replay do
    -- so the offscreen frame matches the captured baseline and the
    interior-lit fraction reflects lit resectogram fragments, not a
    non-black gradient.
    """
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


def _restrict_display_to_view(display_node, view_node) -> None:
    """Bind ``display_node`` to render in ``view_node`` ONLY.

    Clears any existing view restriction then adds the single target view,
    so the display node's actor is hosted by exactly one view's renderer.
    This is the per-display-node half of the no-overlap contract (ADR-0023
    §Stage-4): anatomy display nodes restricted to the scene view, the
    resectogram display node restricted to the resectogram view.
    """
    if display_node is None or view_node is None:
        return
    display_node.RemoveAllViewNodeIDs()
    display_node.AddViewNodeID(view_node.GetID())


def _collect_anatomy_display_nodes(bezier, parenchyma):
    """Return every anatomy (non-resectogram) display node in the scene.

    The 3D anatomy is the parenchyma sphere model + the Bezier surface +
    its markers; each carries one or more display nodes.  Gather them so the
    arena can restrict ALL of them to the scene view (and, by exclusion,
    keep them out of the resectogram renderer).  The resectogram display
    node (``vtkMRMLResectogramDisplayNode``) is explicitly excluded -- it is
    bound to the resectogram view instead.
    """
    nodes = []
    for owner in (parenchyma, bezier):
        if owner is None:
            continue
        for index in range(owner.GetNumberOfDisplayNodes()):
            display = owner.GetNthDisplayNode(index)
            if display is None:
                continue
            if display.IsA("vtkMRMLResectogramDisplayNode"):
                continue
            nodes.append(display)
    return nodes


@pytest.mark.parametrize("scenario_name", _SCENARIOS)
def test_resectogram_arena(scenario_name: str, render_interactive: float) -> None:
    """Render a T3 resectogram scenario into TWO separated views.

    The single body adapts to both modes by branching on
    ``render_interactive`` (ADR-0008 §3) — the offscreen path tears the
    views down immediately after the structural + separation + band-content
    assertions, the interactive path shows both windows and starts the
    interactors for ``render_interactive`` seconds.

    Two views, no overlap (ADR-0023 §Stage-4)
    -----------------------------------------
    * a **scene view** (plain ``vtkMRMLViewNode``) hosting the 3D anatomy,
      its display nodes restricted to that view, and
    * the dedicated **resectogram view** (the ``"LiverResectogram"`` tagged
      view via ``ResectogramViewManager``) hosting ONLY the flattened strip.

    The arena asserts the renderer-level separation: the resectogram strip
    actor is in the resectogram renderer and ABSENT from the scene renderer,
    and the anatomy actors are absent from the resectogram renderer.

    Band-content gate (RED-by-design, ADR-0027)
    -------------------------------------------
    Beyond "any lit pixels", the resectogram view must draw the projected
    distance-map margin BAND (ADR-0025 §Context), measured as a non-trivial
    interior-lit fraction.  RED TODAY because
    ``FlattenedSurfaceRepresentation`` does not bind the distance-map texture
    (the T3-e rewrite severed v1's texture path), so the strip interior is
    grid-only; GREEN once the implementer binds the texture.  The verdict is
    GPU-gated and needs launched/GPU verification.

    Parametrised over the three T3 resectogram scenarios so the maintainer
    can ``pytest --render-interactive=N -k <scenario>`` to inspect any one
    on a GPU.
    """
    slicer = import_slicer_or_skip()
    if slicer is None:
        return
    require_mrml_scene()
    require_qt_widget()

    # The scenario builds a v2 vtkMRMLBezierSurfaceNode carrier + attaches
    # a vtkMRMLResectogramDisplayNode (the v2.0 ResectogramPipeline carrier;
    # the v1 markups render path is retired -- ADR-0014 §"Dissolution",
    # ADR-0032 §"Consequences").
    # Guard the distinct "live scene but the modules did not register" case
    # with an explicit, greppable skip reason (module path missing).  Probe
    # the resectogram display node specifically -- it is the T3 go-live
    # carrier the registered ResectogramPipeline keys on (ADR-0013 §1/§5).
    registration_probe = slicer.mrmlScene.CreateNodeByClass(
        "vtkMRMLResectogramDisplayNode"
    )
    if registration_probe is None:
        pytest.skip(
            "[arena-skip] vtkMRMLResectogramDisplayNode is not registered -- "
            "the LiverResections module is not on the additional-module-paths. "
            "Run via the pytest_launched CTest row (Liver/Testing/Python/"
            "CMakeLists.txt supplies the module paths)."
        )
    # CreateNodeByClass returns a node with the factory's +1 reference that the
    # caller owns; drop it, or the probe instance survives to process shutdown
    # and trips vtkDebugLeaks (failing the launched harness) even when the test
    # later skips on a software-GL stack.
    registration_probe.UnRegister(None)

    # Software-GL gate (CI's xvfb + llvmpipe): the resectogram render path
    # does not reliably light fragments on a software rasteriser, and the
    # offscreen render itself is unreliable there.  Probe a throwaway context
    # and skip BEFORE building/rendering the live views so the test reports a
    # real, greppable SKIP rather than a false pass or a render crash.  The
    # band-content verdict is on a GPU-backed display.
    software_gl_skip = _software_gl_skip_reason()

    import qt  # type: ignore[import-not-found]

    scenario = _load_scenario(scenario_name)
    meta = scenario.describe()
    width, height = meta["viewport"]["size"]

    # Ensure the upstream LayerDM displayable manager is registered in the
    # 3D-view factory so the standalone views host it and the registered
    # ResectogramPipeline dispatches for the resectogram display node
    # (ADR-0013 §5; idempotent -- RegisterInDefaultViews short-circuits when
    # already present, and the LiverResections module setup() already calls
    # it).  Skip cleanly when SlicerLayerDM is not on the launched path.
    try:
        from slicer import (  # type: ignore[import-not-found]
            vtkMRMLLayerDisplayableManager,
        )
    except ImportError:
        pytest.skip(
            "[arena-skip] vtkMRMLLayerDisplayableManager is not importable -- "
            "the upstream SlicerLayerDM extension is not on the launched path "
            "(issue #460).  Run via pytest_launched with the LayerDM module "
            "paths."
        )
    vtkMRMLLayerDisplayableManager.RegisterInDefaultViews()

    scene_widget = None
    resectogram_widget = None
    try:
        # Populate the scene (v2 Bezier carrier + parenchyma + distance map
        # + the resectogram display node).  setup_scene returns the created
        # nodes so nothing leaks through a module global.  It Clear(0)s the
        # scene first, so create the view nodes AFTER it -- a view node
        # created before would be wiped, leaving the displayable-manager
        # group bound to a node no longer in the scene.
        created_nodes = scenario.setup_scene()
        assert created_nodes is not None, (
            "scenario.setup_scene() returned None -- expected the created "
            "node handles (the no-module-globals contract)."
        )
        bezier = created_nodes[0]
        parenchyma = created_nodes[1]
        assert bezier is not None, (
            "scenario.setup_scene() did not return a Bezier node handle."
        )
        # The v2.0 ResectogramPipeline carrier (ADR-0013 §1): the scenario
        # returns it as the fourth handle.  Its presence in the scene is what
        # drives the registered pipeline to render the flattened strip.
        resectogram_display = created_nodes[3]
        assert resectogram_display is not None, (
            "scenario.setup_scene() did not return a vtkMRMLResectogramDisplayNode "
            "-- the v2.0 ResectogramPipeline has nothing to key on (ADR-0013 §1)."
        )

        # ---- Two view nodes ----
        # The scene view: a normal vtkMRMLViewNode hosting the 3D anatomy.
        # NO resectogram singleton tag, so the tightened ResectogramPipeline
        # creator never fires for it (ADR-0023 §Stage-4).
        scene_view_node = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLViewNode", "ArenaSceneView"
        )

        # The dedicated resectogram view: the production view-manager owns
        # the "LiverResectogram"-tagged singleton view node so the arena and
        # the live module agree on the tag + layout name (ADR-0023 §Stage-4).
        from LiverResectionsLib.ResectogramViewManager import (  # type: ignore[import-not-found]
            ResectogramViewManager,
        )

        resectogram_view_node = ResectogramViewManager().ensureViewNode()

        # ---- No-overlap: restrict each display node to its one view ----
        # Anatomy display nodes (parenchyma + Bezier + markers) render in the
        # scene view ONLY; the resectogram display node renders in the
        # resectogram view ONLY.  ViewNodeIDs is the per-display-node half of
        # the no-overlap contract (ADR-0023 §Stage-4); the renderer-level
        # assertions below verify the consequence.
        anatomy_display_nodes = _collect_anatomy_display_nodes(bezier, parenchyma)
        for display in anatomy_display_nodes:
            _restrict_display_to_view(display, scene_view_node)
        _restrict_display_to_view(resectogram_display, resectogram_view_node)

        # ---- Build + map both standalone views ----
        scene_widget = _build_view_widget(
            slicer, slicer.mrmlScene, scene_view_node
        )
        resectogram_widget = _build_view_widget(
            slicer, slicer.mrmlScene, resectogram_view_node
        )

        scenario.setup_camera(resectogram_view_node)
        scenario.setup_viewport(resectogram_view_node)

        # Push the scenario's deterministic camera + flat background onto the
        # resectogram renderer (the panel the band metric reads).  The scene
        # renderer keeps Slicer's default 3D camera -- the arena does not pin
        # its pixels, only that anatomy actors live there and the strip does
        # not.
        scene_renderer = _first_renderer(scene_widget)
        resectogram_renderer = _first_renderer(resectogram_widget)
        _apply_camera_and_background(resectogram_renderer, meta)

        for widget in (scene_widget, resectogram_widget):
            widget.resize(width, height)
            widget.threeDView().renderWindow().SetSize(width, height)
            widget.threeDView().renderWindow().SetMultiSamples(0)
            widget.threeDView().forceRender()

        # Frame the scene view on the 3D anatomy.  The standalone
        # qMRMLThreeDWidget has no layout manager, so nothing resets-to-fit;
        # without this the default camera sits at the origin and the view
        # shows only the crosshair + a stray glyph instead of the framed
        # parenchyma + Bezier surface.  Actors exist after the render above,
        # so ResetCamera frames them -- but ResetCamera alone leaves the
        # camera looking straight down +z, framing the z=0 planar Bezier
        # surface EDGE-ON ("two collinear planes").  Re-pose it to an
        # elevated 3/4 oblique view AFTER ResetCamera (so the clipping range
        # ResetCamera computed still fits) by orbiting the camera up and
        # around its focal point, then re-fitting.  The surface then reads as
        # a 3D sheet, not a line.  Interactive-only polish: the band metric
        # reads the resectogram renderer, not this one, so the assertions are
        # unaffected.
        scene_renderer.ResetCamera()
        scene_camera = scene_renderer.GetActiveCamera()
        scene_camera.Azimuth(45.0)
        scene_camera.Elevation(35.0)
        scene_camera.OrthogonalizeViewUp()
        scene_renderer.ResetCameraClippingRange()
        _crosshair = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLCrosshairNode")
        if _crosshair is not None:
            _crosshair.SetCrosshairMode(0)  # vtkMRMLCrosshairNode.NoCrosshair
        scene_widget.threeDView().forceRender()

        # ---- Structural wiring assertions (ALWAYS-ON, path-agnostic) ----
        # These run regardless of the GL stack: live renderers, the v2.0
        # resectogram display node with the strip enabled, and a LIVE
        # ResectogramPipeline dispatched for it on the dedicated view.
        assert scene_renderer is not None, "no live renderer on the scene view"
        assert resectogram_renderer is not None, (
            "no live renderer on the resectogram view"
        )

        # The resectogram strip must be enabled (the whole point of the
        # scenario).  ShowResection2D lives on the v2.0
        # vtkMRMLResectogramDisplayNode (the ResectogramPipeline carrier).
        get_show_2d = getattr(resectogram_display, "GetShowResection2D", None)
        assert get_show_2d is not None, (
            "the resectogram display node has no GetShowResection2D accessor "
            "-- the scenario is not driving a resectogram-capable display "
            "node (ADR-0025 §Context)."
        )
        assert get_show_2d(), (
            "ShowResection2D is OFF on the display node -- the scenario did "
            "not enable the resectogram strip."
        )

        # The registered ResectogramPipeline must have dispatched for the
        # display node ON THE DEDICATED VIEW and built a non-empty
        # flattened-surface actor.  This is the T3-e go-live invariant
        # (ADR-0013 §1/§5/§6): a vtkMRMLResectogramDisplayNode in a
        # LayerDM-aware dedicated view yields a live pipeline whose
        # FlattenedSurfaceRepresentation has renderable geometry -- the
        # precondition for the band-content verdict below.
        manager = resectogram_widget.threeDView().displayableManagerByClassName(
            "vtkMRMLLayerDisplayableManager"
        )
        assert manager is not None, (
            "[arena] the resectogram 3D view has no "
            "vtkMRMLLayerDisplayableManager -- the upstream SlicerLayerDM "
            "extension is not loaded on the launched path (issue #460)."
        )
        pipeline = manager.GetNodePipeline(resectogram_display)
        assert pipeline is not None, (
            "no pipeline dispatched for the vtkMRMLResectogramDisplayNode -- "
            "the ResectogramPipeline creator (ADR-0013 §5) did not fire."
        )
        assert type(pipeline).__name__ == "ResectogramPipeline", (
            "the pipeline bound to the resectogram display node is "
            f"{type(pipeline).__name__!r}, not ResectogramPipeline (ADR-0013 §1)."
        )
        flattened = pipeline.GetFlattenedSurfaceRepresentation()
        assert flattened is not None, (
            "the ResectogramPipeline built no FlattenedSurfaceRepresentation "
            "-- OnRendererAdded did not compose the Representations "
            "(ADR-0013 §6)."
        )
        strip_actor = flattened.GetResectionActor2D()
        assert strip_actor is not None and strip_actor.GetMapper() is not None, (
            "the flattened-surface actor / mapper is missing -- the "
            "resectogram strip has nothing to draw."
        )

        # The flattened-surface mapper carries the (u, v) aspect-ratio
        # mapping (MatRatio) the non-square scenario exercises.  Keep the
        # structural reachability check: the mapper must expose the MatRatio
        # accessor so the aspect-ratio path is wired (ADR-0013 §6).  Probe by
        # attribute so the check reads as a wiring assertion, not a value
        # assertion (the value is pinned by the visual-regression baseline).
        mapper = strip_actor.GetMapper()
        assert hasattr(mapper, "GetMatRatio"), (
            "the flattened-surface mapper exposes no GetMatRatio accessor -- "
            "the (u, v) aspect-ratio mapping the non-square scenario pins is "
            "not wired on the resectogram mapper (ADR-0013 §6)."
        )

        # ---- Two-view separation (ALWAYS-ON, renderer identity) ----
        # No overlap: the strip actor lives in the resectogram renderer and
        # NOT in the scene renderer; the anatomy actors live in the scene
        # renderer and NOT in the resectogram renderer (ADR-0023 §Stage-4 --
        # the flattened strip must not bleed into the 3D anatomy view, and
        # the anatomy must not bleed into the flattened panel).
        assert _renderer_owns_actor(resectogram_renderer, strip_actor), (
            "the resectogram strip actor is NOT in the resectogram view's "
            "renderer -- the dedicated Pipeline did not attach it "
            "(ADR-0023 §Stage-4)."
        )
        assert not _renderer_owns_actor(scene_renderer, strip_actor), (
            "the resectogram strip actor is present in the SCENE (anatomy) "
            "renderer -- the flattened strip is bleeding into the 3D anatomy "
            "view (the overlap bug).  Restrict the resectogram display node to "
            "the dedicated view (ADR-0023 §Stage-4)."
        )

        # We have no direct handle to the anatomy vtkActors (they live inside
        # the upstream model / markups displayable managers), so assert the
        # separation by renderer actor-identity SETS: the scene renderer
        # carries the anatomy actors (everything but the strip), and NONE of
        # those identities may appear in the resectogram renderer.
        resectogram_addresses = _renderer_actor_addresses(resectogram_renderer)
        scene_addresses = _renderer_actor_addresses(scene_renderer)
        strip_address = strip_actor.GetAddressAsString("")
        # The scene renderer must carry anatomy actors (the parenchyma sphere
        # at minimum) and none of them may be the strip actor; the
        # resectogram renderer must NOT share any actor identity with the
        # scene renderer's anatomy actors (overlap = a shared address).
        anatomy_addresses = scene_addresses - {strip_address}
        assert anatomy_addresses, (
            "the scene (anatomy) renderer carries no anatomy actors -- the "
            "parenchyma / Bezier surface did not render into the scene view "
            "(restriction bound them to the wrong view?)."
        )
        leaked = anatomy_addresses & resectogram_addresses
        assert not leaked, (
            "anatomy actor(s) leaked into the resectogram renderer "
            f"(shared addresses: {sorted(leaked)}) -- the anatomy and the "
            "flattened strip are co-mingling in one view (the overlap bug).  "
            "Restrict the anatomy display nodes to the scene view "
            "(ADR-0023 §Stage-4)."
        )

        # ---- Band-content verdict (GPU-gated, RED-by-design) ----
        # The resectogram render path does not reliably light fragments on a
        # software rasteriser; defer the pixel verdicts to a GPU-backed
        # display.  The structural + separation assertions above already ran.
        if software_gl_skip is not None:
            pytest.skip(software_gl_skip)

        try:
            import numpy  # type: ignore[import-not-found]  # noqa: F401
            from vtk.util import numpy_support  # type: ignore[import-not-found]  # noqa: F401
        except ImportError:
            pytest.skip(
                "[arena-skip] numpy / vtk.util.numpy_support unavailable -- "
                "cannot read the rendered back buffer for the band-content "
                "assertion.  Structural wiring + separation above already "
                "passed."
            )

        # Structural lit-pixel floor: the strip drew SOMETHING (grid + border
        # qualify).  Kept as the cheap precondition for the band metric.
        visible = _visible_pixel_count(resectogram_widget)
        min_visible = int(0.01 * width * height)
        assert visible >= min_visible, (
            f"the resectogram rendered only {visible} lit pixels "
            f"(< {min_visible}) -- the flattened strip is not visibly drawn at "
            "all.  Expected the live resectogram path to light the (u, v) panel."
        )

        # Band-content gate (the RED pin, ADR-0027): the projected
        # distance-map margin BAND must fill a non-trivial CONTIGUOUS region
        # of the panel INTERIOR, distinguishing it from the bare flattened
        # grid + coloured border (which leave the interior dark).  The
        # scenario's deterministic 4-component distance map yields a
        # deterministic band, so a stable interior-lit-fraction floor
        # separates band-from-grid (ADR-0025 §Context).
        #
        # RED TODAY: FlattenedSurfaceRepresentation does not bind the
        # distance-map texture (no SetDistanceMapTextureObject / ras-ijk
        # matrices; the T3-e rewrite severed v1's texture path), so the
        # interior is grid-only and this fraction is ~0.  GREEN once the
        # implementer binds the distance-map texture so the margin band
        # fills the (u, v) panel interior.  Needs launched/GPU verification.
        interior_fraction = _interior_lit_fraction(resectogram_widget)
        min_interior_fraction = 0.10
        assert interior_fraction >= min_interior_fraction, (
            f"the resectogram panel interior is only {interior_fraction:.3f} "
            f"lit (< {min_interior_fraction}) -- the flattened strip is drawing "
            "the (u, v) GRID + coloured BORDER but NOT the projected "
            "distance-map margin BAND.  The band fills a contiguous interior "
            "region only once FlattenedSurfaceRepresentation binds the "
            "distance-map texture (RED-by-design until that lands; "
            "ADR-0025 §Context)."
        )

        if render_interactive:
            # Interactive arena: keep both windows up and let the human drive
            # the cameras.  A single-shot timer quits the nested event loop
            # after the requested dwell so the test still terminates under
            # CI's brief-onscreen pass (--render-interactive=0.1).
            import vtk  # type: ignore[import-not-found]

            loop = qt.QEventLoop()
            qt.QTimer.singleShot(int(render_interactive * 1000), loop.quit)
            for widget in (scene_widget, resectogram_widget):
                interactor = widget.threeDView().interactor()
                if interactor is not None:
                    interactor.Initialize()
                    widget.threeDView().forceRender()
            # The scene view is the 3D anatomy the maintainer rotates to
            # confirm coherence.  The standalone qMRMLThreeDView's default
            # interactor style does not give plain trackball orbit, so install
            # vtkInteractorStyleTrackballCamera on the scene interactor for the
            # dwell (the resectogram view is a fixed flattened panel -- no
            # rotation wanted there).
            scene_interactor = scene_widget.threeDView().interactor()
            if scene_interactor is not None:
                scene_interactor.SetInteractorStyle(
                    vtk.vtkInteractorStyleTrackballCamera()
                )
            loop.exec_()
    finally:
        # Tear the widgets + scene down so no actor / node survives to process
        # exit and trips vtkDebugLeaks in the launched harness (the
        # LiverResections conftest's _launched_scene_cleanup clears the scene;
        # the standalone widgets are ours).
        for widget in (scene_widget, resectogram_widget):
            if widget is not None:
                widget.setMRMLScene(None)
                widget.deleteLater()
        slicer.mrmlScene.Clear(0)


def _bend_control_points(bezier) -> None:
    """Push the Bezier surface OUT of its planar pose (a coherence mutation).

    The scenario lays the 4x4 control points flat at ``z == 0`` (a planar
    surface).  Lift every control point well off that plane so the
    evaluated ``S(u, v)`` bows — a large, unambiguous geometry change.  The
    flattened resectogram samples the distance field at the real
    ``S(u, v)``, so a coherent (BSPoints-fed) render MUST shift the band; a
    fixed-quad render (the bug) ignores the surface and stays
    pixel-identical.

    Reads/writes the v2 ``vtkMRMLBezierSurfaceNode`` carrier's row-major
    control grid (``GetControlGridVector`` / ``SetControlPoint(row, col,
    x, y, z)``); the v1 markups control-point API is retired (ADR-0014
    §"Dissolution"; ADR-0032 §"Consequences").
    """
    grid = list(bezier.GetControlGridVector())
    rows = 4
    cols = 4
    for row in range(rows):
        for col in range(cols):
            base = (row * cols + col) * 3
            bezier.SetControlPoint(
                row,
                col,
                grid[base + 0],
                grid[base + 1],
                grid[base + 2] + 35.0,
            )



def test_resectogram_blur_engages_pass() -> None:
    """Engaging ``BlurEnabled`` MUST set a Gaussian-blur pass on the pipeline.

    The on/off Gaussian-blur invariant (ADR-0027; ADR-0013 §6): rendering a
    blur-ON resectogram through the real dedicated view + ResectogramPipeline
    must leave a ``vtkGaussianBlurPass`` engaged on the FlattenedSurface
    Representation (its reconcile sets the pass on the view's renderer).

    This asserts the WIRING -- the pass object + that the reconcile engaged it
    -- not rendered pixels.  The pixel-level softening is confirmed by the
    maintainer's eyeball + the captured baseline; a cross-render pixel delta is
    unreliable here because the dedicated resectogram view is a SINGLETON
    shared across launched tests, so a prior widget's render can leak into a
    pixel measurement.  The object wiring reflects THIS pipeline only, so it is
    immune to that contamination.

    GPU-gated: needs a real GL context + the registered LiverResections +
    SlicerLayerDM modules, so it carries the software-GL + registration /
    SlicerLayerDM (#460) skips; it SKIPS CLEANLY otherwise.
    """
    slicer = import_slicer_or_skip()
    if slicer is None:
        return
    require_mrml_scene()
    require_qt_widget()

    registration_probe = slicer.mrmlScene.CreateNodeByClass(
        "vtkMRMLResectogramDisplayNode"
    )
    if registration_probe is None:
        pytest.skip(
            "[arena-skip] vtkMRMLResectogramDisplayNode is not registered -- "
            "the LiverResections module is not on the additional-module-paths. "
            "Run via the pytest_launched CTest row."
        )
    registration_probe.UnRegister(None)

    software_gl_skip = _software_gl_skip_reason()
    if software_gl_skip is not None:
        pytest.skip(software_gl_skip)

    try:
        from slicer import (  # type: ignore[import-not-found]
            vtkMRMLLayerDisplayableManager,
        )
    except ImportError:
        pytest.skip(
            "[arena-skip] vtkMRMLLayerDisplayableManager is not importable -- "
            "the upstream SlicerLayerDM extension is not on the launched path "
            "(issue #460).  Run via pytest_launched with the LayerDM module "
            "paths."
        )
    vtkMRMLLayerDisplayableManager.RegisterInDefaultViews()

    scenario = _load_scenario("Resectogram4x4BlurOn")  # blur ON
    meta = scenario.describe()
    width, height = meta["viewport"]["size"]

    resectogram_widget = None
    try:
        created_nodes = scenario.setup_scene()
        bezier = created_nodes[0]
        parenchyma = created_nodes[1]
        resectogram_display = created_nodes[3]

        from LiverResectionsLib.ResectogramViewManager import (  # type: ignore[import-not-found]
            ResectogramViewManager,
        )

        scene_view_node = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLViewNode", "BlurSceneView"
        )
        resectogram_view_node = ResectogramViewManager().ensureViewNode()
        for display in _collect_anatomy_display_nodes(bezier, parenchyma):
            _restrict_display_to_view(display, scene_view_node)
        _restrict_display_to_view(resectogram_display, resectogram_view_node)

        resectogram_widget = _build_view_widget(
            slicer, slicer.mrmlScene, resectogram_view_node
        )
        scenario.setup_camera(resectogram_view_node)
        scenario.setup_viewport(resectogram_view_node)
        _apply_camera_and_background(_first_renderer(resectogram_widget), meta)
        resectogram_widget.resize(width, height)
        resectogram_widget.threeDView().renderWindow().SetSize(width, height)
        resectogram_widget.threeDView().renderWindow().SetMultiSamples(0)
        resectogram_widget.threeDView().forceRender()

        manager = resectogram_widget.threeDView().displayableManagerByClassName(
            "vtkMRMLLayerDisplayableManager"
        )
        assert manager is not None, (
            "[arena] the resectogram view has no vtkMRMLLayerDisplayableManager "
            "(SlicerLayerDM not loaded; issue #460)."
        )
        pipeline = manager.GetNodePipeline(resectogram_display)
        assert pipeline is not None, (
            "no pipeline dispatched for the resectogram display node "
            "(ADR-0013 §5)."
        )

        # The scenario enabled blur; the pipeline must have reconciled a
        # Gaussian-blur pass onto the flattened-surface Representation.
        assert resectogram_display.GetBlurEnabled(), (
            "the Resectogram4x4BlurOn scenario did not set BlurEnabled."
        )
        flattened = pipeline.GetFlattenedSurfaceRepresentation()
        assert flattened is not None, (
            "the ResectogramPipeline built no FlattenedSurfaceRepresentation "
            "(ADR-0013 §6)."
        )
        assert flattened.IsBlurPassAttached(), (
            "BlurEnabled is true but the FlattenedSurfaceRepresentation did not "
            "engage the blur pass (ADR-0013 §6)."
        )
        blur_pass = flattened.GetBlurPass()
        assert blur_pass is not None and blur_pass.IsA("vtkGaussianBlurPass"), (
            "the engaged blur pass is not a vtkGaussianBlurPass."
        )
    finally:
        if resectogram_widget is not None:
            resectogram_widget.setMRMLScene(None)
            resectogram_widget.deleteLater()
        slicer.mrmlScene.Clear(0)


def test_resectogram_is_coherent_with_surface() -> None:
    """Moving the surface's control points MUST change the flattened render.

    The coherence / reactivity invariant (ADR-0027; ADR-0025 §Context): the
    resectogram is the flattened image of the ACTUAL Bezier surface, so a
    control-point edit that re-shapes ``S(u, v)`` must re-shape the flattened
    distance-map band.  The fixed-quad failure mode (the maintainer-caught
    bug) paints the distance field on a fixed plane regardless of the
    surface, so the render is pixel-identical before/after the edit — this
    test is RED against it and GREEN once the real surface feeds the 2D
    mapper as the ``"BSPoints"`` attribute.

    Single dedicated resectogram view (the band lives there); the scene view
    is irrelevant to coherence so it is not built.  GPU-gated like the band
    metric — the software rasteriser does not reliably light the band.
    """
    slicer = import_slicer_or_skip()
    if slicer is None:
        return
    require_mrml_scene()
    require_qt_widget()

    registration_probe = slicer.mrmlScene.CreateNodeByClass(
        "vtkMRMLResectogramDisplayNode"
    )
    if registration_probe is None:
        pytest.skip(
            "[arena-skip] vtkMRMLResectogramDisplayNode is not registered -- "
            "the LiverResections module is not on the additional-module-paths. "
            "Run via the pytest_launched CTest row."
        )
    registration_probe.UnRegister(None)

    software_gl_skip = _software_gl_skip_reason()
    if software_gl_skip is not None:
        pytest.skip(software_gl_skip)

    try:
        from slicer import (  # type: ignore[import-not-found]
            vtkMRMLLayerDisplayableManager,
        )
    except ImportError:
        pytest.skip(
            "[arena-skip] vtkMRMLLayerDisplayableManager is not importable -- "
            "the upstream SlicerLayerDM extension is not on the launched path "
            "(issue #460).  Run via pytest_launched with the LayerDM module "
            "paths."
        )
    vtkMRMLLayerDisplayableManager.RegisterInDefaultViews()

    try:
        import numpy  # type: ignore[import-not-found]  # noqa: F401
    except ImportError:
        pytest.skip(
            "[arena-skip] numpy unavailable -- cannot read the rendered back "
            "buffer for the coherence assertion."
        )

    scenario = _load_scenario("Resectogram4x4BlurOff")
    meta = scenario.describe()
    width, height = meta["viewport"]["size"]

    resectogram_widget = None
    try:
        created_nodes = scenario.setup_scene()
        bezier = created_nodes[0]
        parenchyma = created_nodes[1]
        resectogram_display = created_nodes[3]

        from LiverResectionsLib.ResectogramViewManager import (  # type: ignore[import-not-found]
            ResectogramViewManager,
        )

        # Restrict the resectogram strip to its dedicated view, and ALL
        # anatomy display nodes (the Bezier surface + markers + parenchyma)
        # to a separate scene view.  Without the anatomy restriction the
        # Bezier surface actor renders into the resectogram view too and
        # MOVES with the control points -- which would let a fixed-quad
        # resectogram (the bug) appear to "change" via the leaked surface
        # actor and mask the non-coherence.  Isolating the resectogram
        # renderer to the strip alone makes the pixel delta attributable to
        # the flattened image only (ADR-0023 §Stage-4).
        scene_view_node = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLViewNode", "CoherenceSceneView"
        )
        resectogram_view_node = ResectogramViewManager().ensureViewNode()
        for display in _collect_anatomy_display_nodes(bezier, parenchyma):
            _restrict_display_to_view(display, scene_view_node)
        _restrict_display_to_view(resectogram_display, resectogram_view_node)

        resectogram_widget = _build_view_widget(
            slicer, slicer.mrmlScene, resectogram_view_node
        )
        scenario.setup_camera(resectogram_view_node)
        scenario.setup_viewport(resectogram_view_node)
        resectogram_renderer = _first_renderer(resectogram_widget)
        _apply_camera_and_background(resectogram_renderer, meta)
        resectogram_widget.resize(width, height)
        resectogram_widget.threeDView().renderWindow().SetSize(width, height)
        resectogram_widget.threeDView().renderWindow().SetMultiSamples(0)
        resectogram_widget.threeDView().forceRender()

        # Interior-only mask: the band lives in the panel interior, so an
        # interior signature isolates the distance-map fill from the fixed
        # grid + border (which do not move when the surface bends).
        before = _lit_mask(resectogram_widget)
        rows, cols = before.shape
        mr, mc = int(0.18 * rows), int(0.18 * cols)
        before_interior = before[mr : rows - mr, mc : cols - mc].copy()

        # Re-shape the surface, then drive the pipeline so the
        # FlattenedSurfaceRepresentation re-feeds BSPoints + re-renders.
        _bend_control_points(bezier)
        manager = resectogram_widget.threeDView().displayableManagerByClassName(
            "vtkMRMLLayerDisplayableManager"
        )
        assert manager is not None, (
            "[arena] the resectogram view has no vtkMRMLLayerDisplayableManager "
            "(SlicerLayerDM not loaded; issue #460)."
        )
        pipeline = manager.GetNodePipeline(resectogram_display)
        assert pipeline is not None, (
            "no pipeline dispatched for the resectogram display node "
            "(ADR-0013 §5)."
        )
        pipeline.UpdatePipeline()
        resectogram_widget.threeDView().forceRender()

        after = _lit_mask(resectogram_widget)
        after_interior = after[mr : rows - mr, mc : cols - mc]

        changed = int(numpy.count_nonzero(before_interior != after_interior))
        # A real coherent render bends the band substantially when the
        # surface domes 35 mm off the plane; require a non-trivial fraction
        # of interior pixels to flip so single-pixel dithering cannot pass.
        min_changed = int(0.01 * before_interior.size)
        assert changed >= min_changed, (
            f"the flattened resectogram changed by only {changed} interior "
            f"pixels (< {min_changed}) when the surface's control points "
            "moved 35 mm off-plane -- the flattened image is NOT tracking the "
            "real surface.  This is the fixed-quad bug: the 2D mapper is "
            "painting the distance field on a fixed plane instead of the real "
            "S(u, v) (feed the surface as the mapper's BSPoints attribute; "
            "ADR-0025 §Context)."
        )
    finally:
        if resectogram_widget is not None:
            resectogram_widget.setMRMLScene(None)
            resectogram_widget.deleteLater()
        slicer.mrmlScene.Clear(0)


def test_resectogram_reacts_to_control_point_edit() -> None:
    """A control-point edit MUST drive the pipeline WITHOUT a manual re-drive.

    The reactivity invariant (ADR-0027; ADR-0023 §Stage-4): editing the
    Bezier surface's control points must propagate to the flattened
    resectogram through the Pipeline's OWN observer chain -- the data-node
    ``PointModifiedEvent`` / ``ModifiedEvent`` observer wired in
    ``ResectogramPipeline.SetDisplayNode`` -> ``_attach_observer``.

    This is the gap ``test_resectogram_is_coherent_with_surface`` does NOT
    cover: that test manually calls ``pipeline.UpdatePipeline()`` after
    bending, so it proves the re-feed renders but says nothing about whether
    a real (mouse-driven) edit auto-triggers it.  Here we bend the surface
    and assert ``GetUpdateCount()`` ADVANCES on its own -- RED if the
    observer never reaches the live pipeline (the dragging-changes-nothing
    failure mode the maintainer caught), GREEN once the observer is attached
    to the data node the user actually edits.

    Does not need GPU: the assertion is on the Python-side update counter,
    not rendered pixels, so it runs even under the software-GL skip.
    """
    slicer = import_slicer_or_skip()
    if slicer is None:
        return
    require_mrml_scene()
    require_qt_widget()

    registration_probe = slicer.mrmlScene.CreateNodeByClass(
        "vtkMRMLResectogramDisplayNode"
    )
    if registration_probe is None:
        pytest.skip(
            "[arena-skip] vtkMRMLResectogramDisplayNode is not registered -- "
            "the LiverResections module is not on the additional-module-paths. "
            "Run via the pytest_launched CTest row."
        )
    registration_probe.UnRegister(None)

    try:
        from slicer import (  # type: ignore[import-not-found]
            vtkMRMLLayerDisplayableManager,
        )
    except ImportError:
        pytest.skip(
            "[arena-skip] vtkMRMLLayerDisplayableManager is not importable -- "
            "the upstream SlicerLayerDM extension is not on the launched path "
            "(issue #460)."
        )
    vtkMRMLLayerDisplayableManager.RegisterInDefaultViews()

    scenario = _load_scenario("Resectogram4x4BlurOff")
    meta = scenario.describe()
    width, height = meta["viewport"]["size"]

    resectogram_widget = None
    try:
        created_nodes = scenario.setup_scene()
        bezier = created_nodes[0]
        resectogram_display = created_nodes[3]

        from LiverResectionsLib.ResectogramViewManager import (  # type: ignore[import-not-found]
            ResectogramViewManager,
        )

        resectogram_view_node = ResectogramViewManager().ensureViewNode()
        _restrict_display_to_view(resectogram_display, resectogram_view_node)

        resectogram_widget = _build_view_widget(
            slicer, slicer.mrmlScene, resectogram_view_node
        )
        scenario.setup_camera(resectogram_view_node)
        scenario.setup_viewport(resectogram_view_node)
        resectogram_widget.resize(width, height)
        resectogram_widget.threeDView().renderWindow().SetSize(width, height)
        resectogram_widget.threeDView().renderWindow().SetMultiSamples(0)
        resectogram_widget.threeDView().forceRender()

        manager = resectogram_widget.threeDView().displayableManagerByClassName(
            "vtkMRMLLayerDisplayableManager"
        )
        assert manager is not None, (
            "[arena] the resectogram view has no vtkMRMLLayerDisplayableManager "
            "(SlicerLayerDM not loaded; issue #460)."
        )
        pipeline = manager.GetNodePipeline(resectogram_display)
        assert pipeline is not None, (
            "no pipeline dispatched for the resectogram display node "
            "(ADR-0013 §5)."
        )

        # Sanity: the pipeline must have resolved the SAME Bezier node the
        # edit targets as its data node, or the observer is on the wrong node
        # and reactivity cannot work regardless of the render path.
        data_node = pipeline.GetDataNode()
        assert data_node is not None, (
            "the ResectogramPipeline resolved no data node -- "
            "SetDisplayNode/GetDisplayableNode returned None (the back-reference "
            "was not established when the pipeline was created)."
        )
        assert data_node.GetID() == bezier.GetID(), (
            f"the ResectogramPipeline's data node is {data_node.GetID()} but the "
            f"edited Bezier node is {bezier.GetID()} -- the PointModifiedEvent "
            "observer is attached to the wrong node."
        )

        before_count = pipeline.GetUpdateCount()
        _bend_control_points(bezier)
        # NO manual pipeline.UpdatePipeline() here -- the observer chain wired
        # in SetDisplayNode / OnRendererAdded must carry the edit on its own.
        after_count = pipeline.GetUpdateCount()

        assert after_count > before_count, (
            f"editing the Bezier control points did NOT advance the pipeline "
            f"update count ({before_count} -> {after_count}) -- the data-node "
            "modification observer never reached UpdatePipeline.  The "
            "resectogram is non-reactive to surface edits (ADR-0027)."
        )
    finally:
        if resectogram_widget is not None:
            resectogram_widget.setMRMLScene(None)
            resectogram_widget.deleteLater()
        slicer.mrmlScene.Clear(0)

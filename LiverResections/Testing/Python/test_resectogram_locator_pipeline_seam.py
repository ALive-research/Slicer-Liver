# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""ResectogramPipeline locator-interaction SEAM (ADR-0032 seam; ADR-0025 Slice C).

This file pins the Pipeline-side glue that turns a resectogram click into a
locator pick: a NEW method on ``ResectogramPipeline`` (ADR-0004 Python), to be
implemented later --

    def _produce_from_display_position(self, display_xy) -> tuple | None

It resolves the seam's four inputs off the LIVE Pipeline state and composes the
already-merged GL-free producer (``ResectogramLocatorProducer``, ADR-0025
§Producer -- the exact 1:1 (u, v) mapping, no picker):

    1. the surface CARRIER  -- ``self.GetDataNode()`` (a vtkMRMLBezierSurfaceNode);
    2. the LOCATOR node     -- ``scene.GetFirstNodeByClass("vtkMRMLLocatorNode")``
                               (v2.0 has exactly one, ADR-0025 §Consumer);
    3. the ``mat_ratio``    -- ``GetFlattenedSurfaceRepresentation()
                               .GetMatRatioApplied()`` (the anisotropic scaling
                               last pushed onto the 2D strip, ADR-0025 §Context);
    4. the ``viewport_size``-- the flattened strip renderer's
                               ``renderWindow.GetSize()``.

It then lazily constructs a ``ResectogramLocatorProducer(surface, locator)`` and
calls ``producer.produce(display_xy, viewport_size, mat_ratio)`` -- which writes
``locator.SetPickedPositionWorld`` and returns the world point.  A degenerate
input (no locator, ``mat_ratio`` None, non-positive viewport, no surface) is a
no-op returning ``None`` and leaving the locator UNTOUCHED.

DISPLAY-COORD CONVENTION
------------------------
``display_xy`` is a VTK DISPLAY-space pixel (BOTTOM-LEFT origin), exactly as
delivered by ``eventData.GetDisplayPosition()`` in the Qt event filter that
sources the click (mirrors ``LiverBezierSurfacePipeline``'s interaction path).
There is NO Qt y-flip at this seam -- the test feeds VTK-convention pixels
directly, so the pixel (64, 192) in a 256x256 viewport is (u, v) = (0.25, 0.75),
consistent with ``test_resectogram_locator_producer.py``'s composition anchor.
The Qt-side y-flip (if any) is the INTERACTION layer's responsibility, verified
on the interactive ``:0`` pass (ADR-0025 §Click-to-reslice) -- OUT of scope here.

WHAT THIS PINS vs THE SIBLING PRODUCER TEST
-------------------------------------------
``test_resectogram_locator_producer.py`` pins the producer CORE (pixel -> uv ->
world -> node) in isolation.  THIS file pins the PIPELINE SEAM: that
``ResectogramPipeline`` resolves the four producer inputs off its own live state
and composes them, reusing the SAME known affine 4x4 control grid + the SAME
pixel(64,192)/viewport(256x256)/ratio(1,1) -> (u,v)=(0.25,0.75) -> world
composition anchor, so the expected world point is already known
((22.5, 7.5, 0.0), x = 30*v, y = 30*u).

WHY LAUNCHED-SLICER / RUN-VS-SKIP
---------------------------------
The wrapped ``vtkMRMLBezierSurfaceNode`` / ``vtkMRMLLocatorNode`` + the
``CreateResectionPlan`` create-API + ``ResectogramPipeline`` (base
``vtkMRMLLayerDMScriptedPipeline`` on ``LayerDMLib``) are reachable only inside a
launched Slicer with the module loaded; a bare ``PythonSlicer -m pytest`` has
``slicer.mrmlScene is None`` and those off the path, so every test SKIPS CLEANLY
via the shared ``slicer_pytest_support`` guards.  All GL-free: no render window
is realised -- the strip's renderer + render window are FAKED (the whole point
of the 1:1 (u, v) mapping vs a picker; ADR-0025 §Producer).

The composition test (invariant 1) is SKIP-PENDING on the seam method's absence
per ADR-0027: once ``_produce_from_display_position`` lands it must ASSERT (not
skip); the skip lifts at the implementation commit.  Verify run-vs-skip in the
CI log -- never trust overall green (the launched harness is
green-but-skipping prone).

See also:
  * Docs/adr/0025-locator-architecture.md §Producer, §Consumer, §Context,
    §Click-to-reslice, §Conformance
  * Docs/adr/0032-v2-interaction-via-layerdm-pipeline-seam.md  (the seam)
  * Docs/adr/0027-invariant-test-first-v2-implementation.md  (RED / skip-pending)
  * Docs/adr/0004-python-cpp-boundary.md   (the seam is Python)
  * Docs/adr/0013-layerdm-pipeline-pattern.md §5, §6
  * LiverResections/LiverResectionsLib/ResectogramPipeline.py
  * LiverResections/LiverResectionsLib/ResectogramLocatorProducer.py
  * LiverResections/Testing/Python/test_resectogram_locator_producer.py
"""

from __future__ import annotations

import pytest

BEZIER_NODE_CLASS = "vtkMRMLBezierSurfaceNode"
LOCATOR_NODE_CLASS = "vtkMRMLLocatorNode"

# The Pipeline entity carrying the seam (ADR-0032 seam; ADR-0025 Slice C).
PIPELINE_MODULE = "LiverResectionsLib.ResectogramPipeline"
PIPELINE_CLASS = "ResectogramPipeline"

# The seam method under test.  Invariant 1 skips-pending on its absence.
SEAM_METHOD = "_produce_from_display_position"

# World-point float tolerance -- same rationale as the sibling producer test:
# the carrier stores double, Bernstein sums accumulate rounding; loose enough
# for the summation, tight enough that a wrong (u, v) ordering / factor fails.
WORLD_TOL = 1e-6


# --------------------------------------------------------------------------- #
# Skip-guards (mirror test_resectogram_locator_producer.py)
# --------------------------------------------------------------------------- #


def _slicer_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _resection_logic_or_skip(slicer):
    """Return ``vtkSlicerLiverResectionsLogic`` with the create-API, or skip."""
    module = getattr(slicer.modules, "liverresections", None)
    if module is None:
        pytest.skip("liverresections module not registered in this build.")
    logic = module.logic()
    if logic is None:
        pytest.skip("liverresections module has no logic singleton.")
    if not hasattr(logic, "CreateResectionPlan"):
        pytest.skip(
            "vtkSlicerLiverResectionsLogic has no CreateResectionPlan -- the "
            "resection-plan create-API is not in this build."
        )
    return logic


def _make_affine_carrier_or_skip(slicer, name):
    """Mint a carrier and seed the KNOWN affine 4x4 control grid.

    IDENTICAL grid to ``test_resectogram_locator_producer.py``:
    ``P[r][c] = (x = c*10, y = r*10, z = 0)`` makes the deg-3 tensor Bezier
    EXACTLY affine in (u, v): ``x = 30*v, y = 30*u, z = 0`` -- so
    ``EvaluateSurface(0.25, 0.75)`` is the hand-computed (22.5, 7.5, 0.0).
    Reused verbatim so the seam's composed world point is already known.
    """
    logic = _resection_logic_or_skip(slicer)
    plan = logic.CreateResectionPlan(name)
    if plan is None:
        pytest.skip("CreateResectionPlan returned None -- carrier not minted.")
    carrier = plan.GetGeometryNode()
    if carrier is None or carrier.GetClassName() != BEZIER_NODE_CLASS:
        pytest.skip(
            "plan geometry node is not a vtkMRMLBezierSurfaceNode carrier -- "
            "cannot exercise EvaluateSurface."
        )
    if not hasattr(carrier, "SetControlPoint"):
        pytest.skip(
            "carrier has no SetControlPoint -- the Python grid seam is not in "
            "this build."
        )
    if not hasattr(carrier, "EvaluateSurface"):
        pytest.skip(
            "carrier has no EvaluateSurface -- the parametric-surface evaluator "
            "is not in this build."
        )
    rows = int(carrier.GetRows())
    cols = int(carrier.GetCols())
    if rows * cols != 16:
        pytest.skip(f"expected a default 4x4 grid, got {rows}x{cols}.")
    for r in range(rows):
        for c in range(cols):
            carrier.SetControlPoint(r, c, float(c) * 10.0, float(r) * 10.0, 0.0)
    return carrier


def _expected_world_for_uv(u, v):
    """The hand-computed world point of the affine grid at (u, v).

    ``x = 30*v, y = 30*u, z = 0`` (see ``_make_affine_carrier_or_skip``); the
    same anchor the sibling producer test uses.  u drives y, v drives x.
    """
    return (30.0 * v, 30.0 * u, 0.0)


def _pipeline_or_skip(slicer):
    """Construct a bare ``ResectogramPipeline`` or skip.

    The Pipeline's base ``vtkMRMLLayerDMScriptedPipeline`` lives on
    ``LayerDMLib`` (reachable only inside a launched Slicer with the extension
    loaded); a bare pytest run cannot import it, so skip cleanly.  The Pipeline
    itself takes a no-arg constructor (the LayerDM contract), so a test can
    build it directly and inject the state the seam reads.
    """
    try:
        module = __import__(PIPELINE_MODULE, fromlist=[PIPELINE_CLASS])
        pipeline_cls = getattr(module, PIPELINE_CLASS)
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"{PIPELINE_CLASS} not importable ({exc!r}) -- the base "
            "vtkMRMLLayerDMScriptedPipeline (LayerDMLib) is off the path in this "
            "environment."
        )
    try:
        return pipeline_cls()
    except Exception as exc:  # pragma: no cover - base-class-dependent
        pytest.skip(
            f"{PIPELINE_CLASS}() not constructable bare ({exc!r}) -- the LayerDM "
            "base needs a launched Slicer."
        )


def _seam_or_skip_pending(pipeline):
    """Return the bound seam method or SKIP-PENDING (ADR-0027).

    RED == the ``_produce_from_display_position`` seam is absent; the skip lifts
    at the implementation commit, at which point the composition test ASSERTS.
    """
    method = getattr(pipeline, SEAM_METHOD, None)
    if not callable(method):
        pytest.skip(
            f"{PIPELINE_CLASS}.{SEAM_METHOD} not present -- the ADR-0032 locator "
            "interaction seam has not landed.  Skip lifts at the implementation "
            "commit (ADR-0027)."
        )
    return method


class _FakeRenderWindow:
    """Minimal render window exposing only ``GetSize`` (GL-free)."""

    def __init__(self, size):
        self._size = tuple(size)

    def GetSize(self):  # noqa: N802 - VTK verb
        return self._size


class _FakeRenderer:
    """Minimal renderer exposing only ``GetRenderWindow`` (GL-free)."""

    def __init__(self, size):
        self._render_window = _FakeRenderWindow(size)

    def GetRenderWindow(self):  # noqa: N802 - VTK verb
        return self._render_window


class _FakeFlattenedRepresentation:
    """Stand-in flattened strip exposing the two inputs the seam reads.

    The seam sources ``mat_ratio`` from ``GetMatRatioApplied()`` and the
    viewport from the strip renderer's render window (``GetRenderer()``).  Both
    are pure accessors -- no GL is touched -- so a fake suffices to pin the
    resolution + composition without a realised render context.
    """

    def __init__(self, mat_ratio, viewport_size):
        self._mat_ratio = mat_ratio
        self._renderer = (
            _FakeRenderer(viewport_size) if viewport_size is not None else None
        )

    def GetMatRatioApplied(self):  # noqa: N802 - VTK verb
        return self._mat_ratio

    def GetRenderer(self):  # noqa: N802 - VTK verb
        return self._renderer


class _FakeInteractionEventData:
    """Minimal interaction event exposing only ``GetDisplayPosition`` (GL-free).

    Mirrors the one accessor ``ProcessInteractionEvent`` reads off the LayerDM
    interaction logic's event data -- the VTK display-space pixel (bottom-left
    origin).  A fake suffices because the resectogram's exact 1:1 (u, v) map
    needs no live camera (unlike the Bezier edit path, which back-projects
    display->world and is therefore :0-only).
    """

    def __init__(self, display_xy, event_type="__leftpress__"):
        self._display_xy = tuple(display_xy)
        # Default to a left-button press -- the seam commits on click only
        # (ADR-0025 click-to-reslice), so the common test fixture is a click.
        if event_type == "__leftpress__":
            import vtk

            event_type = vtk.vtkCommand.LeftButtonPressEvent
        self._event_type = event_type

    def GetDisplayPosition(self):  # noqa: N802 - VTK verb
        return self._display_xy

    def GetType(self):  # noqa: N802 - VTK verb
        return self._event_type


def _inject_state(pipeline, carrier, mat_ratio, viewport_size):
    """Wire the live state the seam reads onto a bare Pipeline.

    ``GetDataNode()`` returns ``self._data_node`` and
    ``GetFlattenedSurfaceRepresentation()`` returns ``self._flattened_surface``
    (both introspection accessors on ``ResectogramPipeline``), so injecting the
    two backing attributes lets the seam resolve the carrier + mat_ratio +
    viewport without driving the full LayerDM renderer lifecycle.  The locator
    is resolved by the seam off the scene (``GetFirstNodeByClass``), so it is
    NOT injected here -- the test adds/omits it in the scene per invariant.
    """
    pipeline._data_node = carrier
    pipeline._flattened_surface = _FakeFlattenedRepresentation(
        mat_ratio, viewport_size
    )
    pipeline._representations_initialised = True


# --------------------------------------------------------------------------- #
# Invariant 1 -- seam composition (skip-pending on the seam method)
# --------------------------------------------------------------------------- #


def test_seam_produces_picked_position_from_display_position():
    """Invariant 1: the seam resolves its four inputs + composes the producer.

    With the Pipeline's data node = the known affine carrier, a resolvable
    vtkMRMLLocatorNode in the scene, a flattened rep returning
    ``mat_ratio = (1.0, 1.0)`` and a strip renderer whose render window is
    256x256, ``_produce_from_display_position((64, 192))`` must:

      * map the VTK display pixel (64, 192) -> (u, v) = (0.25, 0.75) (isotropic,
        bottom-left origin -- no Qt y-flip at this seam);
      * evaluate the carrier at (0.25, 0.75) -> world (22.5, 7.5, 0.0) (the
        SAME anchor the sibling producer test pins);
      * write THAT world point onto the locator node's PickedPositionWorld
        (ADR-0025 §Producer) AND return it.

    Once the seam lands this ASSERTS; until then it skips-pending (ADR-0027).
    """
    slicer = _slicer_or_skip()
    carrier = _make_affine_carrier_or_skip(slicer, "SeamComposePos")
    locator = _single_locator_or_skip(slicer)

    pipeline = _pipeline_or_skip(slicer)
    _inject_state(pipeline, carrier, mat_ratio=(1.0, 1.0), viewport_size=(256, 256))
    seam = _seam_or_skip_pending(pipeline)

    expected = _expected_world_for_uv(0.25, 0.75)  # (22.5, 7.5, 0.0)

    returned = seam((64.0, 192.0))

    assert returned is not None, (
        "_produce_from_display_position() must return the composed world point "
        "for an in-range display position; got None."
    )
    assert tuple(returned) == pytest.approx(expected, abs=WORLD_TOL), (
        f"the seam must compose display (64, 192) -> (u, v) = (0.25, 0.75) -> "
        f"world {expected} (x = 30*v, y = 30*u; VTK bottom-left origin, no Qt "
        f"y-flip); got {tuple(returned)}."
    )
    written = tuple(locator.GetPickedPositionWorld())
    assert written == pytest.approx(expected, abs=WORLD_TOL), (
        "the seam must write the composed world point onto the scene's locator "
        f"node's PickedPositionWorld (ADR-0025 §Producer); got {written}, "
        f"expected {expected}."
    )


# --------------------------------------------------------------------------- #
# Invariant 2 -- degenerate inputs are no-ops returning None
# --------------------------------------------------------------------------- #


def _single_locator_or_skip(slicer):
    """The scene's single locator -- resolved, not minted-anew.

    ``CreateResectionPlan`` now ensures exactly one ``vtkMRMLLocatorNode``
    (ADR-0025 §Consumer), and the seam resolves THAT one via
    ``GetFirstNodeByClass``.  Resolve the same node here (creating one only if
    absent) rather than adding a second the seam would ignore.
    """
    scene = slicer.mrmlScene
    node = scene.GetFirstNodeByClass(LOCATOR_NODE_CLASS)
    if node is None:
        node = scene.AddNewNodeByClass(LOCATOR_NODE_CLASS)
    if node is None:
        pytest.skip(f"{LOCATOR_NODE_CLASS} not registered in this build.")
    return node


def _clear_locators(slicer):
    """Remove every locator node so the 'no locator in scene' path is genuine.

    ``CreateResectionPlan`` ensures one, so a test that needs zero must strip it.
    """
    scene = slicer.mrmlScene
    for _ in range(scene.GetNumberOfNodesByClass(LOCATOR_NODE_CLASS)):
        node = scene.GetFirstNodeByClass(LOCATOR_NODE_CLASS)
        if node is None:
            break
        scene.RemoveNode(node)


def _degenerate_pipeline(slicer, *, with_locator, carrier, mat_ratio, viewport_size):
    """Build the Pipeline + inject the (possibly degenerate) state, plus a
    sentinel-seeded locator (when ``with_locator``) so a leak past the guard is
    caught.  Returns ``(seam, locator_or_None, sentinel)``."""
    pipeline = _pipeline_or_skip(slicer)
    _inject_state(pipeline, carrier, mat_ratio=mat_ratio, viewport_size=viewport_size)
    seam = _seam_or_skip_pending(pipeline)

    locator = None
    sentinel = (11.0, 22.0, 33.0)
    if with_locator:
        locator = _single_locator_or_skip(slicer)
        locator.SetPickedPositionWorld(*sentinel)
    else:
        _clear_locators(slicer)
    return seam, locator, sentinel


def _assert_no_op(returned, locator, sentinel):
    assert returned is None, (
        "a degenerate seam call must return None rather than a bogus world "
        f"point; got {returned!r}."
    )
    if locator is not None:
        after = tuple(locator.GetPickedPositionWorld())
        assert after == pytest.approx(sentinel, abs=WORLD_TOL), (
            "a degenerate seam call must not disturb the locator node's picked "
            f"position; it changed from {sentinel} to {after}."
        )


def test_seam_no_op_when_no_locator_in_scene():
    """Invariant 2a: no vtkMRMLLocatorNode resolvable -> no-op, None.

    ``GetFirstNodeByClass("vtkMRMLLocatorNode")`` returns None, so there is no
    node to write; the seam must return None (nothing to disturb).
    """
    slicer = _slicer_or_skip()
    carrier = _make_affine_carrier_or_skip(slicer, "SeamNoLocator")
    # No locator added to the scene.
    seam, locator, sentinel = _degenerate_pipeline(
        slicer,
        with_locator=False,
        carrier=carrier,
        mat_ratio=(1.0, 1.0),
        viewport_size=(256, 256),
    )
    _assert_no_op(seam((64.0, 192.0)), locator, sentinel)


def test_seam_no_op_when_mat_ratio_none():
    """Invariant 2b: ``GetMatRatioApplied()`` None -> no-op leaving locator.

    Before the strip's first ``update()`` the MatRatio is unresolved (None);
    the seam has no scaling to invert, so it must be a no-op returning None and
    leaving the locator's PickedPositionWorld unchanged.
    """
    slicer = _slicer_or_skip()
    carrier = _make_affine_carrier_or_skip(slicer, "SeamMatRatioNone")
    seam, locator, sentinel = _degenerate_pipeline(
        slicer,
        with_locator=True,
        carrier=carrier,
        mat_ratio=None,
        viewport_size=(256, 256),
    )
    _assert_no_op(seam((64.0, 192.0)), locator, sentinel)


def test_seam_no_op_when_viewport_non_positive():
    """Invariant 2c: a non-positive viewport (0, 0) -> no-op leaving locator.

    A zero-extent render window has no valid pixel -> (u, v) inversion
    (PixelToUV divides by it); the seam must return None and leave the locator's
    PickedPositionWorld unchanged (no false pick fed to the consumer).
    """
    slicer = _slicer_or_skip()
    carrier = _make_affine_carrier_or_skip(slicer, "SeamViewportZero")
    seam, locator, sentinel = _degenerate_pipeline(
        slicer,
        with_locator=True,
        carrier=carrier,
        mat_ratio=(1.0, 1.0),
        viewport_size=(0, 0),
    )
    _assert_no_op(seam((64.0, 192.0)), locator, sentinel)


def test_seam_no_op_when_no_surface():
    """Invariant 2d: no data node / surface carrier -> no-op leaving locator.

    ``GetDataNode()`` is None (no surface to evaluate), so the seam must return
    None and leave the locator's PickedPositionWorld unchanged.
    """
    slicer = _slicer_or_skip()
    seam, locator, sentinel = _degenerate_pipeline(
        slicer,
        with_locator=True,
        carrier=None,
        mat_ratio=(1.0, 1.0),
        viewport_size=(256, 256),
    )
    _assert_no_op(seam((64.0, 192.0)), locator, sentinel)


# --------------------------------------------------------------------------- #
# Invariant 3 -- the interaction-event routing overrides (GL-free)
# --------------------------------------------------------------------------- #


def test_process_interaction_event_drives_the_pick_from_display_position():
    """Invariant 3: ``ProcessInteractionEvent`` routes the event's display
    position through the seam -- writes the locator + returns True.

    ``ProcessInteractionEvent`` reads ``eventData.GetDisplayPosition()`` (VTK
    bottom-left origin) and composes ``_produce_from_display_position``.  A
    successful pick returns True so the LayerDM interaction logic keeps focus.
    Unlike the Bezier edit path, this override is GL-free testable: the exact
    1:1 (u, v) map needs only the viewport size (faked), no live camera.  What
    stays :0-only is whether the interaction logic DISPATCHES the event to this
    override past the embedded view's camera left-button lock (ADR-0032
    pre-registered risk).
    """
    slicer = _slicer_or_skip()
    carrier = _make_affine_carrier_or_skip(slicer, "SeamProcessEvent")
    locator = _single_locator_or_skip(slicer)

    pipeline = _pipeline_or_skip(slicer)
    _inject_state(pipeline, carrier, mat_ratio=(1.0, 1.0), viewport_size=(256, 256))
    _seam_or_skip_pending(pipeline)  # skips-pending until the seam lands

    expected = _expected_world_for_uv(0.25, 0.75)  # (22.5, 7.5, 0.0)
    handled = pipeline.ProcessInteractionEvent(
        _FakeInteractionEventData((64.0, 192.0))
    )
    assert handled is True, (
        "ProcessInteractionEvent must return True when it produced a pick -- the "
        "interaction logic keeps focus on a pipeline that returns True."
    )
    written = tuple(locator.GetPickedPositionWorld())
    assert written == pytest.approx(expected, abs=WORLD_TOL), (
        "ProcessInteractionEvent must route display (64, 192) through the seam "
        f"onto the locator's PickedPositionWorld; got {written}, expected "
        f"{expected}."
    )


def test_can_process_interaction_event_gated_on_data_node():
    """Invariant 4: ``CanProcessInteractionEvent`` claims the event iff a surface
    is displayed (data node present), with ``distance2`` = 0; else declines.

    The flattened strip IS the (u, v) domain, so every in-view pixel maps -- the
    pipeline claims any click once it has a data node, and the strip owns its
    standalone view so ``distance2`` = 0 (no competing pipeline).
    """
    import sys

    slicer = _slicer_or_skip()
    pipeline = _pipeline_or_skip(slicer)
    _seam_or_skip_pending(pipeline)  # skips-pending until the seam lands

    can, distance2 = pipeline.CanProcessInteractionEvent(
        _FakeInteractionEventData((0.0, 0.0))
    )
    assert can is False, (
        "CanProcessInteractionEvent must decline when no surface is displayed "
        "(no data node) -- nothing to pick."
    )
    assert distance2 == pytest.approx(sys.float_info.max)

    carrier = _make_affine_carrier_or_skip(slicer, "SeamCanProcess")
    _inject_state(pipeline, carrier, mat_ratio=(1.0, 1.0), viewport_size=(256, 256))

    can, distance2 = pipeline.CanProcessInteractionEvent(
        _FakeInteractionEventData((10.0, 10.0))
    )
    assert can is True, (
        "CanProcessInteractionEvent must claim the event once a surface is "
        "displayed (the strip maps every in-view pixel)."
    )
    assert distance2 == pytest.approx(0.0)


def test_can_process_declines_mouse_move_commits_on_click_only():
    """Invariant 4b: the seam commits the locator on a LEFT-BUTTON PRESS only,
    never on a mouse-move/hover (ADR-0025 click-to-reslice).

    Without this filter the seam claimed (and processed) every move event, so
    the marker tracked the cursor and parked at the (0, 0) corner on the
    spurious move fired when the cursor left the view.  A move must be declined
    even when a surface is displayed; ``ProcessInteractionEvent`` on a move must
    be a no-op returning ``False``.
    """
    import sys

    import vtk

    slicer = _slicer_or_skip()
    carrier = _make_affine_carrier_or_skip(slicer, "SeamMoveDeclined")
    locator = _single_locator_or_skip(slicer)

    pipeline = _pipeline_or_skip(slicer)
    _inject_state(pipeline, carrier, mat_ratio=(1.0, 1.0), viewport_size=(256, 256))
    _seam_or_skip_pending(pipeline)

    move = _FakeInteractionEventData(
        (10.0, 10.0), event_type=vtk.vtkCommand.MouseMoveEvent
    )
    can, distance2 = pipeline.CanProcessInteractionEvent(move)
    assert can is False, (
        "CanProcessInteractionEvent must DECLINE a mouse-move even with a "
        "surface displayed -- the resectogram commits on click only."
    )
    assert distance2 == pytest.approx(sys.float_info.max)

    handled = pipeline.ProcessInteractionEvent(move)
    assert handled is False, (
        "ProcessInteractionEvent on a mouse-move must be a no-op returning "
        "False -- no locator write on hover."
    )
    written = tuple(locator.GetPickedPositionWorld())
    assert written == pytest.approx((0.0, 0.0, 0.0), abs=WORLD_TOL), (
        "A declined move must leave the locator untouched (still at its unset "
        f"origin); got {written}."
    )


# --------------------------------------------------------------------------- #
# Invariant 5 -- the locator resolver's no-scene guard
# --------------------------------------------------------------------------- #


def test_resolve_locator_node_none_when_surface_has_no_scene():
    """``_resolve_locator_node`` returns None when the surface has no scene.

    A displayed carrier always has a scene in production, so this is the
    defensive guard: a surface whose ``GetScene()`` yields None must resolve to
    no locator, returning before touching the scene API.  Exercises only the
    staticmethod's None-guard -- no ``slicer.mrmlScene``, no wrapped classes --
    but needs ``ResectogramPipeline`` importable (LayerDMLib), so it skips
    cleanly under bare pytest.
    """
    try:
        module = __import__(PIPELINE_MODULE, fromlist=[PIPELINE_CLASS])
        pipeline_cls = getattr(module, PIPELINE_CLASS)
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"{PIPELINE_CLASS} not importable ({exc!r}) -- LayerDMLib is off the "
            "path in this environment."
        )

    class _SurfaceWithoutScene:
        def GetScene(self):  # noqa: N802 - VTK verb
            return None

    assert pipeline_cls._resolve_locator_node(_SurfaceWithoutScene()) is None


# --------------------------------------------------------------------------- #
# Invariant 6 -- press/drag/release continuous reslice
# --------------------------------------------------------------------------- #


def test_drag_reslices_continuously_between_press_and_release():
    """A held button drags the reslice: press grabs, moves keep producing,
    release ends the gesture.

    The click-only seam (invariant 4b) stops HOVER moves from writing the
    locator, but the surgeon dragging around the strip expects the slice to
    follow continuously.  The two compose as a grab: a left-button press
    starts reslicing (and writes the first pick), mouse moves while the
    button is held keep writing, and the release ends the gesture (returns
    False, releasing the interaction focus).  A move after the release is
    declined again -- hover still never reslices.
    """
    import vtk

    slicer = _slicer_or_skip()
    carrier = _make_affine_carrier_or_skip(slicer, "SeamDragReslice")
    locator = _single_locator_or_skip(slicer)

    pipeline = _pipeline_or_skip(slicer)
    _inject_state(pipeline, carrier, mat_ratio=(1.0, 1.0), viewport_size=(256, 256))
    _seam_or_skip_pending(pipeline)

    press = _FakeInteractionEventData((64.0, 64.0))
    assert pipeline.ProcessInteractionEvent(press) is True, "press writes + grabs"
    after_press = tuple(locator.GetPickedPositionWorld())

    move = _FakeInteractionEventData(
        (128.0, 96.0), event_type=vtk.vtkCommand.MouseMoveEvent
    )
    can, _ = pipeline.CanProcessInteractionEvent(move)
    assert can is True, (
        "moves while the button is held must be claimed -- the continuous "
        "drag-reslice gesture."
    )
    assert pipeline.ProcessInteractionEvent(move) is True
    after_move = tuple(locator.GetPickedPositionWorld())
    assert max(abs(a - b) for a, b in zip(after_move, after_press)) > WORLD_TOL, (
        "a drag move must RE-write the locator (continuous reslice); the "
        "pick did not change."
    )

    release = _FakeInteractionEventData(
        (128.0, 96.0), event_type=vtk.vtkCommand.LeftButtonReleaseEvent
    )
    can, _ = pipeline.CanProcessInteractionEvent(release)
    assert can is True, "the ending release is claimed (closes the gesture)"
    assert pipeline.ProcessInteractionEvent(release) is False, (
        "release ends the gesture and releases the focus"
    )

    hover = _FakeInteractionEventData(
        (10.0, 10.0), event_type=vtk.vtkCommand.MouseMoveEvent
    )
    can, _ = pipeline.CanProcessInteractionEvent(hover)
    assert can is False, "hover after release must be declined again (4b)"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

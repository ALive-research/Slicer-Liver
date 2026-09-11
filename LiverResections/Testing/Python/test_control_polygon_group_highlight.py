# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Hover lights the BORDER; grab lights the POINTS.  Never both at once.

The two cues answer different questions:

* the BORDER tracks the GESTURE: cyan hovered, blue held, resting colour
  otherwise.
* the POINTS name a SUBSET: a held RING lights its own members green, in
  the same colour a directly-grabbed point uses.  A held FRAME lights
  none -- it moves every point, so lighting all sixteen distinguishes
  nothing and merely doubles the border cue.  A hovered gesture lights no
  points either; that is the border's job.

Both border colours are cool and both point cues warm, so the channels
stay legible together.  An earlier pass lit every point on hover AND
recoloured the border at the same moment, which read as one confused
signal; these tests pin each channel separately so that cannot return.

HARNESS: launched Slicer (LayerDMLib base; ADR-0027).
"""

from __future__ import annotations

import pytest


def _slicer_or_skip():
    from slicer_pytest_support import import_slicer_or_skip, require_mrml_scene

    require_mrml_scene()
    return import_slicer_or_skip()


def _module_or_skip():
    """The MODULE, not the class the package __init__ rebinds over it."""
    import importlib

    try:
        return importlib.import_module("LiverResectionsLib.ControlPolygonPipeline")
    except Exception as exc:
        pytest.skip(f"ControlPolygonPipeline not importable ({exc!r}) -- ADR-0027.")


def _rig(module, slicer):
    logic = getattr(slicer.modules, "liverresections", None)
    if logic is None:
        pytest.skip("liverresections module not registered (ADR-0027).")
    plan = logic.logic().CreateResectionPlan("GroupHighlightTest")
    if plan is None:
        pytest.skip("CreateResectionPlan returned None (ADR-0027).")
    carrier = plan.GetGeometryNode()

    from LiverResectionsLib.ResectionStateMachine import STATE_PLANNING

    for row in range(4):
        for col in range(4):
            carrier.SetControlPoint(row, col, col * 10.0, 0.0, row * 10.0)
    carrier.SetState(STATE_PLANNING)

    try:
        pipeline = module.ControlPolygonPipeline()
    except Exception as exc:
        pytest.skip(f"pipeline not constructible ({exc!r}) -- ADR-0027.")
    display = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLControlPolygonDisplayNode")
    if display is None or not hasattr(display, "GroupRing0"):
        pytest.skip("display node lacks group targets (ADR-0027).")
    display.SetEdgeColor(1.0, 0.0, 0.0)
    pipeline.SetDisplayNode(display)
    pipeline._data_node = carrier
    pipeline._refresh_geometry()
    return pipeline, display


def _scalar(pipeline, index):
    scalars = pipeline._handles_polydata.GetPointData().GetScalars()
    if scalars is None or index >= scalars.GetNumberOfTuples():
        return None
    return tuple(int(v) for v in scalars.GetTuple3(index))


def _rgb255(colour):
    return tuple(int(c * 255) for c in colour)


def test_ring_grab_lights_exactly_its_members():
    """The lit set must equal the moved set, or the cue lies."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    pipeline, display = _rig(module, slicer)

    display.SetGrabbedGroup(display.GroupRing0 + 1)  # the interior ring: 5, 6, 10, 9
    pipeline._apply_interaction_scalars()

    grab = _rgb255(module.HALO_GRAB_COLOR)
    members = {5, 6, 10, 9}
    for i in range(16):
        lit = _scalar(pipeline, i) == grab
        assert lit is (i in members), (
            f"point {i} lit={lit} but membership={i in members}; the "
            "highlight must name exactly the points the gesture moves."
        )


def test_group_uses_the_same_colours_as_a_single_point():
    """One visual language: a point looks the same however it was picked."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    pipeline, display = _rig(module, slicer)

    display.SetGrabbedControlPoint(5)
    pipeline._apply_interaction_scalars()
    single = _scalar(pipeline, 5)

    display.SetGrabbedControlPoint(-1)
    display.SetGrabbedGroup(display.GroupRing0 + 1)
    pipeline._apply_interaction_scalars()
    as_group = _scalar(pipeline, 5)

    assert single == as_group == _rgb255(module.HALO_GRAB_COLOR)


def test_frame_grab_lights_the_border_but_no_points():
    """The frame moves everything, so no subset is worth naming."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    pipeline, display = _rig(module, slicer)

    display.SetGrabbedGroup(display.GroupFrame)
    pipeline._apply_frame_style()
    pipeline._apply_interaction_scalars()

    assert pipeline._edges_actor.GetProperty().GetColor() == pytest.approx(
        module.FRAME_GRAB_COLOR, abs=1e-3
    )
    grab = _rgb255(module.HALO_GRAB_COLOR)
    assert all(_scalar(pipeline, i) != grab for i in range(16)), (
        "lighting all sixteen points for a whole-polygon drag names no "
        "subset and just repeats what the border already says."
    )


def test_hover_lights_the_border_and_leaves_the_points_alone():
    """Hover answers "what am I pointing at", on the wireframe only."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    pipeline, display = _rig(module, slicer)

    display.SetHoveredGroup(display.GroupFrame)
    display.SetGrabbedGroup(display.GroupNone)
    pipeline._apply_frame_style()
    pipeline._apply_interaction_scalars()

    assert pipeline._edges_actor.GetProperty().GetColor() == pytest.approx(
        module.FRAME_HOVER_COLOR, abs=1e-3
    )
    grab = _rgb255(module.HALO_GRAB_COLOR)
    assert all(_scalar(pipeline, i) != grab for i in range(16)), (
        "hovering an edge must not light the points -- that was the noise "
        "that collided with the border cue."
    )


def test_ring_grab_lights_its_points_and_leaves_the_border_alone():
    """A ring moves its own points, so only they light."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    pipeline, display = _rig(module, slicer)

    # Hover is still set: a press does not clear it, so the handover must
    # be driven by the GRAB state winning, not by hover being absent.
    display.SetHoveredGroup(display.GroupFrame)
    display.SetGrabbedGroup(display.GroupRing0 + 1)
    pipeline._apply_frame_style()
    pipeline._apply_interaction_scalars()

    assert pipeline._edges_actor.GetProperty().GetColor() == pytest.approx(
        (1.0, 0.0, 0.0), abs=1e-3
    ), (
        "a held RING must leave the border alone -- its own points carry "
        "the cue.  Lighting both would say 'the polygon AND these four "
        "points are moving', which is not what the gesture does.  Note "
        "hover is still set here: the border must be driven by the GRAB "
        "state, not merely by hover being absent."
    )

    grab = _rgb255(module.HALO_GRAB_COLOR)
    assert {i for i in range(16) if _scalar(pipeline, i) == grab} == {5, 6, 10, 9}

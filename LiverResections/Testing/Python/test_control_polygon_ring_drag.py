# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""A ring gesture translates ITS OWN points and leaves the rest alone.

The frame drag moves the whole control polygon; a ring drag moves one
ring.  Both apply the SAME delta to every member -- they are rigid
translations, not scales or rotations about a centre.

The invariant that matters is containment: a ring drag must not disturb
a single point outside the ring.  A membership slip would deform the
surface instead of translating part of it, and on a 4x4 the two rings
share no points, so the untouched set is exactly checkable.

HARNESS: launched Slicer.  The pipeline derives from a LayerDMLib base
reachable only inside a launched Slicer (ADR-0027).
"""

from __future__ import annotations

import pytest


def _slicer_or_skip():
    from slicer_pytest_support import import_slicer_or_skip, require_mrml_scene

    require_mrml_scene()
    return import_slicer_or_skip()


def _pipeline_module_or_skip():
    """The MODULE, not the class the package __init__ rebinds over it."""
    import importlib

    try:
        return importlib.import_module("LiverResectionsLib.ControlPolygonPipeline")
    except Exception as exc:
        pytest.skip(f"ControlPolygonPipeline not importable ({exc!r}) -- ADR-0027.")


def _planning_carrier(slicer):
    """A Planning-state carrier with a known, non-degenerate 4x4 grid."""
    logic = getattr(slicer.modules, "liverresections", None)
    if logic is None:
        pytest.skip("liverresections module not registered (ADR-0027).")
    plan = logic.logic().CreateResectionPlan("RingDragTest")
    if plan is None:
        pytest.skip("CreateResectionPlan returned None (ADR-0027).")
    carrier = plan.GetGeometryNode()
    if carrier is None or not hasattr(carrier, "SetControlPoint"):
        pytest.skip("carrier lacks SetControlPoint (ADR-0027).")

    from LiverResectionsLib.ResectionStateMachine import STATE_PLANNING

    # 100mm spacing.  The fake renderer maps 1mm to 1 display pixel, and
    # the point pick radius is 20px -- so a tighter grid would put every
    # edge MIDPOINT inside a handle's radius (at 40mm spacing it lands
    # exactly on it) and "declined on an edge" would be untestable for
    # reasons that say nothing about the code.  A real polygon spans
    # several hundred pixels.
    for row in range(4):
        for col in range(4):
            carrier.SetControlPoint(row, col, float(col) * 100.0, 0.0, float(row) * 100.0)
    carrier.SetState(STATE_PLANNING)
    return carrier


def _pipeline_for(module, slicer, carrier):
    try:
        pipeline = module.ControlPolygonPipeline()
    except Exception as exc:
        pytest.skip(f"pipeline not constructible ({exc!r}) -- ADR-0027.")
    display = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLControlPolygonDisplayNode")
    if display is None or not hasattr(display, "GroupRing0"):
        pytest.skip("display node lacks group targets (ADR-0027).")
    pipeline.SetDisplayNode(display)
    pipeline._data_node = carrier
    return pipeline, display


def _grid(carrier):
    v = carrier.GetControlGridVector()
    return [(v[i * 3], v[i * 3 + 1], v[i * 3 + 2]) for i in range(16)]


@pytest.mark.parametrize(
    ("ring_offset", "expected_members"),
    [
        (0, (0, 1, 2, 3, 7, 11, 15, 14, 13, 12, 8, 4)),  # outer -- resolvable, not pickable
        (1, (5, 6, 10, 9)),  # inner -- the gesture's actual target
    ],
)
def test_ring_drag_moves_only_its_own_points(ring_offset, expected_members):
    slicer = _slicer_or_skip()
    module = _pipeline_module_or_skip()
    carrier = _planning_carrier(slicer)
    pipeline, display = _pipeline_for(module, slicer, carrier)

    before = _grid(carrier)
    group = display.GroupRing0 + ring_offset

    members = pipeline._ring_members(group)
    assert tuple(members) == expected_members

    delta = (3.0, -4.0, 5.0)
    assert pipeline._translate_control_grid(delta, members)

    after = _grid(carrier)
    moved = {i for i in range(16) if after[i] != before[i]}

    assert moved == set(expected_members), (
        "A ring drag must translate exactly its own members; touching a "
        "point outside the ring deforms the surface instead of moving "
        "part of it."
    )
    for i in expected_members:
        assert after[i] == pytest.approx(
            (before[i][0] + delta[0], before[i][1] + delta[1], before[i][2] + delta[2])
        ), "every member moves by the SAME delta -- this is a rigid translation"


def test_frame_group_moves_the_whole_grid():
    """The frame is the affordance; its action stays global."""
    slicer = _slicer_or_skip()
    module = _pipeline_module_or_skip()
    carrier = _planning_carrier(slicer)
    pipeline, display = _pipeline_for(module, slicer, carrier)

    members = pipeline._ring_members(display.GroupFrame)
    assert tuple(members) == tuple(range(16))

    before = _grid(carrier)
    assert pipeline._translate_control_grid((1.0, 2.0, 3.0), members)
    after = _grid(carrier)

    assert all(after[i] != before[i] for i in range(16))


def test_unknown_group_moves_nothing():
    """An unresolvable group yields None, so the drag is a no-op.

    Guards the failure direction: guessing a membership would silently
    deform the surface, which is worse than doing nothing.
    """
    slicer = _slicer_or_skip()
    module = _pipeline_module_or_skip()
    carrier = _planning_carrier(slicer)
    pipeline, display = _pipeline_for(module, slicer, carrier)

    assert pipeline._ring_members(display.GroupRing0 + 99) is None


class _FakeRenderer:
    """Projects the control grid to a known screen layout.

    World (x, 0, z) -> display (x, z), so the 4x4 grid at 10mm spacing
    lands on a 0..30 square and cursor positions can be chosen exactly.
    """

    def __init__(self):
        self._w = (0.0, 0.0, 0.0, 1.0)

    def SetWorldPoint(self, x, y, z, w):  # noqa: N802 - VTK verb
        self._w = (x, y, z, w)

    def WorldToDisplay(self):  # noqa: N802 - VTK verb
        pass

    def GetDisplayPoint(self):  # noqa: N802 - VTK verb
        return (self._w[0], self._w[2], 0.0)


class _FakeEvent:
    def __init__(self, x, y):
        self._xy = (x, y)

    def GetDisplayPosition(self):  # noqa: N802 - VTK verb
        return self._xy


def test_a_right_press_on_a_boundary_point_claims_the_outer_ring():
    """A ring is addressed through its POINTS."""
    slicer = _slicer_or_skip()
    module = _pipeline_module_or_skip()
    carrier = _planning_carrier(slicer)
    pipeline, display = _pipeline_for(module, slicer, carrier)

    renderer = _FakeRenderer()
    # Corner control point 0, at display (0, 0).
    claim = pipeline._ring_pick(renderer, _FakeEvent(0.0, 0.0))
    assert claim is not None, "a boundary point addresses the outer ring"
    assert claim[0] == display.GroupRing0
    assert 0 in pipeline._ring_members(claim[0])


def test_a_right_press_on_an_interior_point_claims_the_interior_ring():
    slicer = _slicer_or_skip()
    module = _pipeline_module_or_skip()
    carrier = _planning_carrier(slicer)
    pipeline, display = _pipeline_for(module, slicer, carrier)

    renderer = _FakeRenderer()
    # Interior control point 5, at display (100, 100).
    claim = pipeline._ring_pick(renderer, _FakeEvent(100.0, 100.0))
    assert claim is not None
    assert claim[0] == display.GroupRing0 + 1
    assert tuple(pipeline._ring_members(claim[0])) == (5, 6, 10, 9)


def test_a_right_press_on_an_edge_is_declined():
    """Edges carry the LEFT-button frame gesture; rings live on points.

    Addressing rings by segment put the outer ring on the border's own
    pixels -- two gestures, one target, no way to aim.  Declining here is
    what keeps them apart.
    """
    slicer = _slicer_or_skip()
    module = _pipeline_module_or_skip()
    carrier = _planning_carrier(slicer)
    pipeline, display = _pipeline_for(module, slicer, carrier)

    renderer = _FakeRenderer()
    # Mid-way along the top border edge: 50px from either corner, well
    # outside the 20px point radius.
    assert pipeline._ring_pick(renderer, _FakeEvent(50.0, 0.0)) is None
    # Mid-way along an interior ring edge, equally clear of its handles.
    assert pipeline._ring_pick(renderer, _FakeEvent(150.0, 100.0)) is None


def test_every_point_belongs_to_exactly_one_ring():
    """The pick is never ambiguous because the rings partition the grid."""
    slicer = _slicer_or_skip()
    module = _pipeline_module_or_skip()
    carrier = _planning_carrier(slicer)
    pipeline, display = _pipeline_for(module, slicer, carrier)

    seen = {}
    for ring_offset in (0, 1):
        for index in pipeline._ring_members(display.GroupRing0 + ring_offset):
            assert index not in seen, f"point {index} is in two rings"
            seen[index] = ring_offset
    assert sorted(seen) == list(range(16))

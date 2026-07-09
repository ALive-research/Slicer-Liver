# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Invariants for the ``ControlPolygonPipeline`` (ADR-0033).

The control polygon is a first-class display aspect: its own display node
(``vtkMRMLControlPolygonDisplayNode``, the carrier's second display node) keys
its own LayerDM Pipeline, which renders the handles + edges and hosts the
Planning per-point drag with a real display-space ``distance2``.

Pins (ADR-0033 §Conformance):

* handles + edges follow the carrier's control grid;
* edge cells come from the (injected) Algorithm builder, once per shape;
* Planning-only visibility, further gated by the display node's Visibility;
* the drag kernel writes ``SetControlPoint`` in Planning and refuses
  otherwise;
* ``CanProcessInteractionEvent`` declines outside Planning / without a
  renderer (the finite-distance2 arbitration path needs a live camera and is
  exercised on the interactive pass);
* the late-binding hook adopts a displayable linked after ``SetDisplayNode``.

These need the wrapped MRML nodes + LayerDMLib, so they run under the
launched ``pytest_launched`` row and skip cleanly under bare pytest.
"""

from __future__ import annotations

import pytest

pytest.importorskip("LayerDMLib")


@pytest.fixture
def pipeline_module():
    import ControlPolygonPipeline as mod

    return mod


@pytest.fixture
def polygon_nodes():
    """A carrier + control-polygon display node pair, linked."""
    import slicer

    scene = slicer.mrmlScene
    data = scene.AddNewNodeByClass("vtkMRMLBezierSurfaceNode")
    display = scene.AddNewNodeByClass("vtkMRMLControlPolygonDisplayNode")
    data.AddAndObserveDisplayNodeID(display.GetID())
    try:
        yield data, display
    finally:
        scene.RemoveNode(display)
        scene.RemoveNode(data)


class _FakeGeometry:
    calls: list = []

    @staticmethod
    def BuildControlPolygonCells(rows, cols):  # noqa: N802 - VTK verb
        import vtk

        _FakeGeometry.calls.append((rows, cols))
        cells = vtk.vtkCellArray()
        for r in range(rows):
            line = vtk.vtkPolyLine()
            line.GetPointIds().SetNumberOfIds(cols)
            for c in range(cols):
                line.GetPointIds().SetId(c, r * cols + c)
            cells.InsertNextCell(line)
        return cells


def _seed_grid(data):
    for r in range(4):
        for c in range(4):
            data.SetControlPoint(r, c, float(c) * 10.0, float(r) * 10.0, 5.0)


def test_handles_and_edges_follow_the_grid(pipeline_module, polygon_nodes):
    """Planning state + seeded grid -> 16 handle points + builder-cells edges."""
    data, display = polygon_nodes
    pipeline = pipeline_module.ControlPolygonPipeline()
    pipeline._control_polygon_geometry = _FakeGeometry
    _FakeGeometry.calls = []
    pipeline.SetDisplayNode(display)

    _seed_grid(data)
    data.SetState(1)  # Planning
    pipeline.UpdatePipeline()

    handles = pipeline.GetHandlesPolyData()
    assert handles.GetNumberOfPoints() == 16
    assert handles.GetPoint(5) == pytest.approx((10.0, 10.0, 5.0))
    edges = pipeline.GetEdgesPolyData()
    assert edges.GetNumberOfPoints() == 16
    assert edges.GetNumberOfLines() == 4
    assert _FakeGeometry.calls == [(4, 4)], "cells built once, with (rows, cols)"
    pipeline.cleanup()


def test_visibility_is_planning_only_and_display_gated(pipeline_module, polygon_nodes):
    """Hidden in Init; visible in Planning; hidden when the display says so."""
    data, display = polygon_nodes
    pipeline = pipeline_module.ControlPolygonPipeline()
    pipeline._control_polygon_geometry = _FakeGeometry
    pipeline.SetDisplayNode(display)

    pipeline.UpdatePipeline()  # Init (default state)
    assert pipeline.GetHandlesActor().GetVisibility() == 0
    assert pipeline.GetEdgesActor().GetVisibility() == 0

    _seed_grid(data)
    data.SetState(1)  # Planning
    pipeline.UpdatePipeline()
    assert pipeline.GetHandlesActor().GetVisibility() == 1
    assert pipeline.GetEdgesActor().GetVisibility() == 1

    display.SetVisibility(False)
    pipeline.UpdatePipeline()
    assert pipeline.GetHandlesActor().GetVisibility() == 0, (
        "the display node's Visibility must hide the polygon independently "
        "of the surface (ADR-0033)."
    )
    pipeline.cleanup()


def test_display_styling_reaches_the_actors(pipeline_module, polygon_nodes):
    """HandleRadius / colors / EdgeWidth flow display node -> actors."""
    data, display = polygon_nodes
    pipeline = pipeline_module.ControlPolygonPipeline()
    pipeline._control_polygon_geometry = _FakeGeometry
    pipeline.SetDisplayNode(display)
    _seed_grid(data)
    data.SetState(1)
    display.SetHandleColor(0.1, 0.2, 0.3)
    display.SetEdgeColor(0.4, 0.5, 0.6)
    display.SetEdgeWidth(3.0)
    pipeline.UpdatePipeline()

    assert pipeline.GetHandlesActor().GetProperty().GetColor() == pytest.approx((0.1, 0.2, 0.3))
    assert pipeline.GetEdgesActor().GetProperty().GetColor() == pytest.approx((0.4, 0.5, 0.6))
    assert pipeline._edges_tube.GetRadius() == pytest.approx(3.0), (
        "EdgeWidth is the edge TUBE radius (world units) -- edges render "
        "as vtkTubeFilter tubes, not GL lines (pixel line width reads "
        "hairline-thin at liver scale)."
    )
    pipeline.cleanup()


def test_drag_kernel_moves_nearest_point_in_planning_only(pipeline_module, polygon_nodes):
    """The GL-free kernel writes SetControlPoint in Planning; refuses in Init."""
    data, display = polygon_nodes
    pipeline = pipeline_module.ControlPolygonPipeline()
    pipeline.SetDisplayNode(display)
    _seed_grid(data)

    # Init: editing refused (ADR-0019).
    assert pipeline._apply_world_point_to_nearest_control_point((1.0, 1.0, 5.0)) is None

    data.SetState(1)  # Planning
    moved = pipeline._apply_world_point_to_nearest_control_point((1.0, 2.0, 5.0))
    assert moved == 0, "the nearest control point (index 0 at origin) moves"
    grid = data.GetControlGridVector()
    assert (grid[0], grid[1], grid[2]) == pytest.approx((1.0, 2.0, 5.0))
    pipeline.cleanup()


def test_can_process_declines_without_planning_or_renderer(pipeline_module, polygon_nodes):
    """Arbitration preconditions: Planning state AND a live renderer."""
    import sys

    data, display = polygon_nodes
    pipeline = pipeline_module.ControlPolygonPipeline()
    pipeline.SetDisplayNode(display)
    _seed_grid(data)

    class _Event:
        def GetDisplayPosition(self):  # noqa: N802 - VTK verb
            return (0.0, 0.0)

    can, d2 = pipeline.CanProcessInteractionEvent(_Event())
    assert can is False and d2 == pytest.approx(sys.float_info.max), "Init declines"

    data.SetState(1)
    can, d2 = pipeline.CanProcessInteractionEvent(_Event())
    assert can is False, "no renderer -> declines (display->world needs a camera)"
    pipeline.cleanup()


def test_late_bound_displayable_is_adopted(pipeline_module):
    """The reference-added hook + UpdatePipeline late-bind the carrier."""
    import slicer

    scene = slicer.mrmlScene
    data = scene.AddNewNodeByClass("vtkMRMLBezierSurfaceNode")
    display = scene.AddNewNodeByClass("vtkMRMLControlPolygonDisplayNode")
    try:
        pipeline = pipeline_module.ControlPolygonPipeline()
        pipeline.SetDisplayNode(display)
        assert pipeline.GetDataNode() is None

        data.AddAndObserveDisplayNodeID(display.GetID())
        pipeline.OnReferenceToDisplayNodeAdded(data, "display")
        assert pipeline.GetDataNode() is data
        pipeline.cleanup()
    finally:
        scene.RemoveNode(display)
        scene.RemoveNode(data)


def test_geometry_edit_requests_render(pipeline_module, polygon_nodes):
    """A control-point edit must request a render; MTime churn must not.

    The observer callback re-runs ``UpdatePipeline`` but historically never
    requested a render, so a Planning drag moved the handles/edges polydata
    while the 3D view stayed frozen until an unrelated render (camera orbit)
    repainted it.  The request is gated on the (state, geometry-digest)
    tuple (the ResectogramPipeline pattern) so a render-induced ``Modified``
    at fixed geometry cannot open a render feedback loop.
    """
    data, display = polygon_nodes
    pipeline = pipeline_module.ControlPolygonPipeline()
    pipeline._control_polygon_geometry = _FakeGeometry
    pipeline.SetDisplayNode(display)
    _seed_grid(data)
    data.SetState(1)  # Planning

    renders = []
    pipeline.RequestRender = lambda: renders.append(1)

    data.SetControlPoint(0, 0, 1.0, 2.0, 3.0)
    assert renders, (
        "a control-point edit must request a render -- without it the "
        "handles freeze mid-drag until an unrelated render repaints them."
    )

    before = len(renders)
    data.Modified()  # no geometry change -- render-churn signature
    assert len(renders) == before, (
        "a Modified at fixed geometry must not re-request a render "
        "(the render feedback-loop guard)."
    )
    pipeline.cleanup()


class _TypedEvent:
    """Interaction event stub carrying a VTK event type + display position."""

    def __init__(self, etype, pos=(0.0, 0.0)):
        self._etype = etype
        self._pos = pos

    def GetType(self):  # noqa: N802 - VTK verb
        return self._etype

    def GetDisplayPosition(self):  # noqa: N802 - VTK verb
        return self._pos


def test_drag_is_press_grab_move_release(pipeline_module, polygon_nodes):
    """The per-point drag is a press/move/release GRAB, not proximity chasing.

    A hover move near a handle must never edit; a left-button press within
    the pick radius grabs ONE handle; moves while grabbed edit THAT handle
    (even if the cursor drifts nearer another one); the release ends the
    grab (returns False so the focus is released) and subsequent hover
    moves are declined again.
    """
    import vtk

    data, display = polygon_nodes
    pipeline = pipeline_module.ControlPolygonPipeline()
    pipeline.SetDisplayNode(display)
    _seed_grid(data)
    data.SetState(1)  # Planning

    # GL-free seams: a live-renderer stand-in + deterministic pick geometry.
    pipeline._safe_get_renderer = lambda: object()
    pipeline._nearest_control_point_in_display = lambda r, e: (5, 4.0)
    pipeline._event_world_at_control_point = lambda r, e, i: (50.0, 60.0, 5.0)

    move = _TypedEvent(vtk.vtkCommand.MouseMoveEvent)
    press = _TypedEvent(vtk.vtkCommand.LeftButtonPressEvent)
    release = _TypedEvent(vtk.vtkCommand.LeftButtonReleaseEvent)

    can, _ = pipeline.CanProcessInteractionEvent(move)
    assert can is False, "a hover move (no grab) must not be claimed"
    assert pipeline.ProcessInteractionEvent(move) is False

    can, d2 = pipeline.CanProcessInteractionEvent(press)
    assert can is True and d2 == pytest.approx(4.0)
    assert pipeline.ProcessInteractionEvent(press) is True, "press begins the grab"

    can, _ = pipeline.CanProcessInteractionEvent(move)
    assert can is True, "moves while grabbed are claimed"
    # The cursor now reads nearer ANOTHER handle -- the grab must stick to 5.
    pipeline._nearest_control_point_in_display = lambda r, e: (0, 1.0)
    assert pipeline.ProcessInteractionEvent(move) is True
    grid = data.GetControlGridVector()
    assert (grid[15], grid[16], grid[17]) == pytest.approx((50.0, 60.0, 5.0)), (
        "the move edits the GRABBED handle (index 5), not the nearest one"
    )
    assert (grid[0], grid[1], grid[2]) == pytest.approx((0.0, 0.0, 5.0)), (
        "handle 0 (now nearest) must be untouched mid-grab"
    )

    can, _ = pipeline.CanProcessInteractionEvent(release)
    assert can is True, "the release while grabbed is claimed (ends the grab)"
    assert pipeline.ProcessInteractionEvent(release) is False, (
        "release ends the grab and releases the focus"
    )

    can, _ = pipeline.CanProcessInteractionEvent(move)
    assert can is False, (
        "after release, hover moves must be declined again -- the "
        "released-mouse-still-edits failure mode."
    )
    pipeline.cleanup()


class _ChurnRenderer:
    def AddActor(self, actor):  # noqa: N802 - VTK verb
        pass

    def RemoveActor(self, actor):  # noqa: N802 - VTK verb
        pass


def test_styling_survives_renderer_churn(pipeline_module, polygon_nodes):
    """Renderer churn must not leave the pipeline displayless.

    The manager's lifecycle removes and re-adds the renderer around
    ``SetDisplayNode`` (and on view rebuilds).  ``OnRendererRemoved`` ->
    ``cleanup()`` clears the node handles; ``OnRendererAdded`` must
    re-derive them from the base's retained display node, or the pipeline
    runs displayless forever and every styling field silently stays at the
    raw VTK defaults (0.5-radius spheres, hairline white lines -- the
    'tiny control points' failure mode observed live).
    """
    data, display = polygon_nodes
    pipeline = pipeline_module.ControlPolygonPipeline()
    pipeline._control_polygon_geometry = _FakeGeometry
    pipeline.SetDisplayNode(display)
    _seed_grid(data)
    data.SetState(1)  # Planning

    renderer = _ChurnRenderer()
    pipeline.OnRendererRemoved(renderer)  # cleanup() clears the node handles
    pipeline.OnRendererAdded(renderer)    # must re-derive + restyle

    assert pipeline.GetDataNode() is data, "the carrier must be re-derived"
    assert pipeline._handle_sphere.GetRadius() == pytest.approx(
        display.GetHandleRadius()
    ), "the display styling must reach the glyph source after the churn"
    assert pipeline._edges_tube.GetRadius() == pytest.approx(
        display.GetEdgeWidth()
    ), "the display styling must reach the edge tubes after the churn"
    pipeline.cleanup()


def test_hover_highlights_nearest_handle(pipeline_module, polygon_nodes):
    """A bare hover near a handle shows the halo; far away hides it.

    Hover detection is a SIDE EFFECT of the arbitration moves the LayerDM
    logic already sends through ``CanProcessInteractionEvent``: the bare
    move is still DECLINED (camera interaction untouched), but the halo
    actor is positioned on the hovered handle and a render is requested --
    exactly once per hover change, not per move event.
    """
    import vtk

    data, display = polygon_nodes
    pipeline = pipeline_module.ControlPolygonPipeline()
    pipeline._control_polygon_geometry = _FakeGeometry
    pipeline.SetDisplayNode(display)
    _seed_grid(data)
    data.SetState(1)  # Planning

    pipeline._safe_get_renderer = lambda: object()
    pipeline._nearest_control_point_in_display = lambda r, e: (5, 4.0)
    renders = []
    pipeline.RequestRender = lambda: renders.append(1)

    move = _TypedEvent(vtk.vtkCommand.MouseMoveEvent)
    can, _ = pipeline.CanProcessInteractionEvent(move)
    assert can is False, "bare hover moves stay declined"
    assert pipeline.GetHaloActor().GetVisibility() == 1, (
        "hovering within the pick radius must show the halo"
    )
    assert tuple(pipeline.GetHaloActor().GetPosition()) == pytest.approx(
        (10.0, 10.0, 5.0)
    ), "the halo sits on the hovered handle (index 5)"
    n = len(renders)
    assert n >= 1, "the hover change requests a render"

    pipeline.CanProcessInteractionEvent(move)  # same hover -- no re-request
    assert len(renders) == n, "an unchanged hover must not re-request renders"

    pipeline._nearest_control_point_in_display = (
        lambda r, e: (None, 1e12)
    )  # cursor far from every handle
    pipeline.CanProcessInteractionEvent(move)
    assert pipeline.GetHaloActor().GetVisibility() == 0, (
        "leaving the pick radius hides the halo"
    )
    pipeline.cleanup()


def test_grab_changes_the_halo_color(pipeline_module, polygon_nodes):
    """Press flips the halo to the grab colour; release restores hover."""
    import vtk

    data, display = polygon_nodes
    pipeline = pipeline_module.ControlPolygonPipeline()
    pipeline.SetDisplayNode(display)
    _seed_grid(data)
    data.SetState(1)
    pipeline._safe_get_renderer = lambda: object()
    pipeline._nearest_control_point_in_display = lambda r, e: (5, 4.0)
    pipeline._event_world_at_control_point = lambda r, e, i: (1.0, 2.0, 5.0)

    press = _TypedEvent(vtk.vtkCommand.LeftButtonPressEvent)
    release = _TypedEvent(vtk.vtkCommand.LeftButtonReleaseEvent)
    assert pipeline.ProcessInteractionEvent(press) is True
    scalars = pipeline._handles_polydata.GetPointData().GetScalars()
    grab = tuple(int(c * 255) for c in pipeline_module.HALO_GRAB_COLOR)
    assert scalars is not None and tuple(scalars.GetTuple3(5)) == pytest.approx(grab), (
        "the grabbed HANDLE itself must take the grab colour (per-point scalar)"
    )
    assert pipeline._handles_mapper.GetScalarVisibility() == 1
    pipeline.ProcessInteractionEvent(release)
    assert pipeline._handles_mapper.GetScalarVisibility() == 0, (
        "release restores the uniform display HandleColor"
    )
    pipeline.cleanup()

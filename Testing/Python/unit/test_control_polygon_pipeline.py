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
    assert pipeline.GetEdgesActor().GetProperty().GetLineWidth() == pytest.approx(3.0)
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

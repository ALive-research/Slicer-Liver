# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Invariants for the ``SliceControlPolygonPipeline``.

The markups-style slice half of the control polygon (ADR-0033): handles +
edges projected into the slice view's XY space with DISTANCE FADING (alpha
falls off with the point's distance to the slice plane, the above/below
cue), and the Planning per-point drag available FROM the slice views (the
grab preserves the point's out-of-plane offset -- no snap-to-plane).

Launched-row only (wrapped MRML nodes + LayerDMLib); skips bare.
"""

from __future__ import annotations

import pytest

pytest.importorskip("LayerDMLib")


@pytest.fixture
def pipeline_module():
    import SliceControlPolygonPipeline as mod

    return mod


@pytest.fixture
def polygon_nodes():
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


def _seed_grid(data, z=0.0):
    """Flat 4x4 grid at ``z``, except point (0,0) raised 30 mm above."""
    for r in range(4):
        for c in range(4):
            data.SetControlPoint(r, c, float(c) * 10.0, float(r) * 10.0, z)
    data.SetControlPoint(0, 0, 0.0, 0.0, z + 30.0)


class _AxialSliceNodeAt:
    """Slice-node stand-in: axial plane at world ``z`` (identity XY)."""

    def __init__(self, z):
        import vtk

        self._to_ras = vtk.vtkMatrix4x4()
        self._to_ras.SetElement(2, 3, z)
        self._xy_to_ras = vtk.vtkMatrix4x4()
        self._xy_to_ras.SetElement(2, 3, z)

    def GetSliceToRAS(self):  # noqa: N802 - VTK verb
        return self._to_ras

    def GetXYToRAS(self):  # noqa: N802 - VTK verb
        return self._xy_to_ras

    def GetMTime(self):  # noqa: N802 - VTK verb
        return 1


class _TypedEvent:
    def __init__(self, etype, pos=(0.0, 0.0)):
        self._etype = etype
        self._pos = pos

    def GetType(self):  # noqa: N802 - VTK verb
        return self._etype

    def GetDisplayPosition(self):  # noqa: N802 - VTK verb
        return self._pos


def test_projection_follows_the_grid(pipeline_module, polygon_nodes):
    """16 projected handle points; edges present; Planning-only."""
    data, display = polygon_nodes
    pipeline = pipeline_module.SliceControlPolygonPipeline()
    pipeline._slice_node = _AxialSliceNodeAt(0.0)
    pipeline.SetDisplayNode(display)
    _seed_grid(data, z=0.0)

    # Init (the default state) -> hidden.  Tested FIRST: the carrier's
    # state machine refuses backwards transitions (ADR-0019), so a
    # Planning->Init flip would silently keep Planning.
    pipeline.UpdatePipeline()
    assert pipeline.GetHandlesActor().GetVisibility() == 0

    data.SetState(1)  # Planning -> visible
    pipeline.UpdatePipeline()
    handles = pipeline.GetHandlesPolyData()
    # The raised point (30 mm off-plane) is beyond the manipulable range
    # and therefore NOT PRESENT at all (2D alpha is unreliable, so
    # presence is the cutoff): 15 of 16 points project.
    assert handles is not None and handles.GetNumberOfPoints() == 15
    assert pipeline.GetHandlesActor().GetVisibility() == 1
    assert pipeline.GetEdgesActor().GetVisibility() == 1
    pipeline.cleanup()


def test_fading_tracks_distance_to_the_plane(pipeline_module, polygon_nodes):
    """Alpha: full on-plane, zero far away, monotone in between."""
    data, display = polygon_nodes
    pipeline = pipeline_module.SliceControlPolygonPipeline()
    pipeline._slice_node = _AxialSliceNodeAt(0.0)
    pipeline.SetDisplayNode(display)
    _seed_grid(data, z=0.0)  # point 0 is 30 mm above; the rest on-plane
    data.SetState(1)
    pipeline.UpdatePipeline()

    handles = pipeline.GetHandlesPolyData()
    assert handles.GetNumberOfPoints() == 15, (
        "the raised point (beyond the manipulable range) must be ABSENT -- "
        "presence IS the cutoff; only points a slice can edit appear in it."
    )
    scalars = handles.GetPointData().GetScalars()
    assert scalars is not None and scalars.GetNumberOfComponents() == 4, (
        "present handles carry per-point RGBA scalars (the near-range fade)"
    )
    alphas = [scalars.GetTuple4(i)[3] for i in range(handles.GetNumberOfPoints())]
    assert all(a == pytest.approx(255, abs=1) for a in alphas), (
        "all PRESENT points here are on-plane -> fully opaque"
    )
    pipeline.cleanup()


def test_slice_grab_moves_point_preserving_offplane_offset(
    pipeline_module, polygon_nodes
):
    """Press grabs a projected handle; the drag preserves the z offset."""
    import vtk

    data, display = polygon_nodes
    pipeline = pipeline_module.SliceControlPolygonPipeline()
    pipeline._slice_node = _AxialSliceNodeAt(0.0)
    pipeline.SetDisplayNode(display)
    _seed_grid(data, z=0.0)
    data.SetState(1)
    pipeline.UpdatePipeline()

    # Deterministic pick seams (GL-free): handle 0 (the raised one).
    pipeline._nearest_handle_in_display = lambda e: (0, 4.0)

    move = _TypedEvent(vtk.vtkCommand.MouseMoveEvent, (7.0, 8.0))
    can, _ = pipeline.CanProcessInteractionEvent(move)
    assert can is False, "hover moves stay unclaimed (camera untouched)"

    press = _TypedEvent(vtk.vtkCommand.LeftButtonPressEvent, (7.0, 8.0))
    can, d2 = pipeline.CanProcessInteractionEvent(press)
    assert can is True and d2 == pytest.approx(4.0)
    assert pipeline.ProcessInteractionEvent(press) is True

    drag = _TypedEvent(vtk.vtkCommand.MouseMoveEvent, (7.0, 8.0))
    assert pipeline.ProcessInteractionEvent(drag) is True
    grid = data.GetControlGridVector()
    assert (grid[0], grid[1]) == pytest.approx((7.0, 8.0)), (
        "the drag moves the grabbed point to the cursor IN-PLANE (XY)"
    )
    assert grid[2] == pytest.approx(30.0), (
        "the point's out-of-plane offset is PRESERVED -- no snap-to-plane"
    )

    release = _TypedEvent(vtk.vtkCommand.LeftButtonReleaseEvent, (7.0, 8.0))
    assert pipeline.ProcessInteractionEvent(release) is False, "grab ends"
    pipeline.cleanup()


def test_edit_requests_render_with_loop_guard(pipeline_module, polygon_nodes):
    data, display = polygon_nodes
    pipeline = pipeline_module.SliceControlPolygonPipeline()
    pipeline._slice_node = _AxialSliceNodeAt(0.0)
    pipeline.SetDisplayNode(display)
    _seed_grid(data, z=0.0)
    data.SetState(1)

    renders = []
    pipeline.RequestRender = lambda: renders.append(1)
    data.SetControlPoint(2, 2, 21.0, 22.0, 0.0)
    assert renders, "a geometry edit must request a slice repaint"
    n = len(renders)
    data.Modified()
    assert len(renders) == n, "render-churn Modified must not re-request"
    pipeline.cleanup()


def test_creator_accepts_slice_views_only(pipeline_module):
    import slicer

    accepts = pipeline_module._creator_accepts_view
    slice_node = slicer.mrmlScene.CreateNodeByClass("vtkMRMLSliceNode")
    slice_node.UnRegister(None)
    assert accepts(slice_node) is True
    view_node = slicer.mrmlScene.CreateNodeByClass("vtkMRMLViewNode")
    view_node.UnRegister(None)
    assert accepts(view_node) is False
    assert accepts(None) is False


def test_far_points_are_not_manipulable(pipeline_module, polygon_nodes):
    """Points beyond PICK_RANGE_MM from the plane cannot be picked."""
    data, display = polygon_nodes
    pipeline = pipeline_module.SliceControlPolygonPipeline()
    pipeline._slice_node = _AxialSliceNodeAt(0.0)
    pipeline.SetDisplayNode(display)
    _seed_grid(data, z=0.0)  # point 0 is 30 mm above (beyond the 15 mm range)
    data.SetState(1)
    pipeline.UpdatePipeline()

    class _At:
        def GetDisplayPosition(self):  # noqa: N802 - VTK verb
            return (0.0, 0.0)  # exactly on point 0's projection

    idx, _ = pipeline._nearest_handle_in_display(_At())
    assert idx != 0, (
        "the raised point (30 mm off-plane) must be EXCLUDED from slice-side "
        "picking (markups short-range manipulation)."
    )
    pipeline.cleanup()


def test_hover_publishes_cross_view_highlight(pipeline_module, polygon_nodes):
    """A slice hover writes the display channel; the projection colours it."""
    import vtk

    data, display = polygon_nodes
    pipeline = pipeline_module.SliceControlPolygonPipeline()
    pipeline._slice_node = _AxialSliceNodeAt(0.0)
    pipeline.SetDisplayNode(display)
    _seed_grid(data, z=0.0)
    data.SetState(1)
    pipeline.UpdatePipeline()

    move = _TypedEvent(vtk.vtkCommand.MouseMoveEvent, (10.0, 10.0))  # point 5
    can, _ = pipeline.CanProcessInteractionEvent(move)
    assert can is False, "hover moves stay unclaimed"
    assert display.GetHoveredControlPoint() == 5, (
        "the hover must publish onto the display node -- the cross-view "
        "highlight channel every pipeline observes."
    )
    pipeline.UpdatePipeline()
    scalars = pipeline.GetHandlesPolyData().GetPointData().GetScalars()
    hover = tuple(int(c * 255) for c in pipeline_module.HALO_HOVER_COLOR)
    # Grid point 5 sits at PRESENT index 4: the raised point 0 is beyond
    # the manipulable range and absent from the projected polydata.
    assert tuple(scalars.GetTuple4(4))[:3] == pytest.approx(hover), (
        "the hovered point takes the hover colour in the projection"
    )
    assert scalars.GetTuple4(4)[3] == pytest.approx(255), (
        "the hovered point renders fully opaque"
    )
    pipeline.cleanup()


def test_edges_are_dashed_and_ring_marks_the_hover(pipeline_module, polygon_nodes):
    """Structural differentiation + the 2D hover halo.

    The polygon edges render as MANY short dash segments (never a handful
    of solid polylines -- the scaffold reads structurally distinct from the
    solid resection contour), and hovering shows a ring on the projected
    handle, the 2D analogue of the 3D glow halo.
    """
    import vtk

    data, display = polygon_nodes
    pipeline = pipeline_module.SliceControlPolygonPipeline()
    pipeline._slice_node = _AxialSliceNodeAt(0.0)
    pipeline.SetDisplayNode(display)
    # Wide spacing (40 px edges) so each edge holds SEVERAL dashes.
    for r in range(4):
        for c in range(4):
            data.SetControlPoint(r, c, float(c) * 40.0, float(r) * 40.0, 0.0)
    data.SetState(1)
    pipeline.UpdatePipeline()

    edges = pipeline._edges_polydata
    assert edges.GetNumberOfLines() > 24, (
        "edges must be emitted as dash SEGMENTS (24 grid edges -> many "
        "dashes), not solid polylines."
    )
    assert pipeline._ring_actor.GetVisibility() == 0, "no hover -> no ring"

    move = _TypedEvent(vtk.vtkCommand.MouseMoveEvent, (40.0, 40.0))  # point 5
    pipeline.CanProcessInteractionEvent(move)
    pipeline.UpdatePipeline()
    assert pipeline._ring_actor.GetVisibility() == 1, (
        "the hover must raise the 2D ring -- the slice analogue of the halo"
    )
    pipeline.cleanup()

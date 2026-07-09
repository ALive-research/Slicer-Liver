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
    assert handles is not None and handles.GetNumberOfPoints() == 16
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

    scalars = pipeline.GetHandlesPolyData().GetPointData().GetScalars()
    assert scalars is not None and scalars.GetNumberOfComponents() == 4, (
        "handles carry per-point RGBA scalars (the fading channel)"
    )
    on_plane_alpha = scalars.GetTuple4(5)[3]
    raised_alpha = scalars.GetTuple4(0)[3]
    assert on_plane_alpha == pytest.approx(255, abs=1), "on-plane = fully opaque"
    assert raised_alpha < on_plane_alpha, (
        "a point 30 mm off-plane must FADE (alpha below the on-plane value)"
    )
    assert raised_alpha <= 255 * (1.0 - 30.0 / pipeline_module.FADE_DISTANCE_MM) + 1 or raised_alpha < 30, (
        "the fade must track distance (30 mm beyond the fade span reads ~0)"
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

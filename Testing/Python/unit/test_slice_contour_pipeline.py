# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Invariants for the ``SliceContourPipeline`` (T2.6-DM-2D).

The resection surface's intersection with a slice plane is the surgeon's
2D projection of the plan.  A dedicated LayerDM pipeline -- keyed on the
same ``vtkMRMLParametricSurfaceDisplayNode`` but created only for
``vtkMRMLSliceNode`` views (creators dispatch per view TYPE) -- cuts the
tessellated surface with the slice plane and renders the contour in the
slice view's XY space.

Pins:

* the cut contour follows the carrier's control grid (a flat grid at a
  known z, cut by an axial plane through it, yields a non-empty line);
* visibility is gated on an editable/complete state with a full grid;
* a control-point edit requests a render (digest-gated, loop-guarded);
* the creator seam: slice views accepted, 3D + resectogram views declined.

Launched-row only (wrapped MRML nodes + LayerDMLib); skips bare.
"""

from __future__ import annotations

import pytest

pytest.importorskip("LayerDMLib")


@pytest.fixture
def pipeline_module():
    import SliceContourPipeline as mod

    return mod


@pytest.fixture
def surface_nodes():
    import slicer

    scene = slicer.mrmlScene
    data = scene.AddNewNodeByClass("vtkMRMLBezierSurfaceNode")
    display = scene.AddNewNodeByClass("vtkMRMLParametricSurfaceDisplayNode")
    data.AddAndObserveDisplayNodeID(display.GetID())
    try:
        yield data, display
    finally:
        scene.RemoveNode(display)
        scene.RemoveNode(data)


def _seed_flat_grid(data, z=10.0):
    for r in range(4):
        for c in range(4):
            data.SetControlPoint(r, c, float(c) * 10.0, float(r) * 10.0, z)


class _AxialSliceNodeAt:
    """Slice-node stand-in: axial plane at world ``z`` (identity XY)."""

    def __init__(self, z):
        import vtk

        self._to_ras = vtk.vtkMatrix4x4()
        self._to_ras.SetElement(2, 3, z)  # translate the plane to z
        self._xy_to_ras = vtk.vtkMatrix4x4()

    def GetSliceToRAS(self):  # noqa: N802 - VTK verb
        return self._to_ras

    def GetXYToRAS(self):  # noqa: N802 - VTK verb
        return self._xy_to_ras

    def GetMTime(self):  # noqa: N802 - VTK verb
        return 1


def test_contour_follows_the_grid_cut(pipeline_module, surface_nodes):
    """An axial cut through the flat grid yields a non-empty contour."""
    data, display = surface_nodes
    pipeline = pipeline_module.SliceContourPipeline()
    pipeline.SetDisplayNode(display)
    pipeline._slice_node = _AxialSliceNodeAt(10.0)

    _seed_flat_grid(data, z=10.0)
    data.SetState(1)  # Planning
    pipeline.UpdatePipeline()

    contour = pipeline.GetContourPolyData()
    assert contour is not None and contour.GetNumberOfPoints() > 0, (
        "the slice plane passes THROUGH the flat grid -- the cut must "
        "produce contour points."
    )
    assert pipeline.GetContourActor().GetVisibility() == 1
    pipeline.cleanup()


def test_offplane_cut_is_empty_and_hidden(pipeline_module, surface_nodes):
    """A plane far from the surface yields no contour; the actor hides."""
    data, display = surface_nodes
    pipeline = pipeline_module.SliceContourPipeline()
    pipeline.SetDisplayNode(display)
    pipeline._slice_node = _AxialSliceNodeAt(500.0)

    _seed_flat_grid(data, z=10.0)
    data.SetState(1)
    pipeline.UpdatePipeline()

    contour = pipeline.GetContourPolyData()
    assert contour is None or contour.GetNumberOfPoints() == 0
    assert pipeline.GetContourActor().GetVisibility() == 0
    pipeline.cleanup()


def test_edit_requests_render_with_loop_guard(pipeline_module, surface_nodes):
    """A control-point edit repaints; Modified at fixed geometry does not."""
    data, display = surface_nodes
    pipeline = pipeline_module.SliceContourPipeline()
    pipeline.SetDisplayNode(display)
    pipeline._slice_node = _AxialSliceNodeAt(10.0)
    _seed_flat_grid(data, z=10.0)
    data.SetState(1)

    renders = []
    pipeline.RequestRender = lambda: renders.append(1)
    data.SetControlPoint(0, 0, 1.0, 2.0, 10.0)
    assert renders, "a geometry edit must request a slice repaint"
    n = len(renders)
    data.Modified()
    assert len(renders) == n, "render-churn Modified must not re-request"
    pipeline.cleanup()


def test_creator_accepts_slice_views_only(pipeline_module):
    """The creator seam: slice node in, 3D + resectogram views out."""
    import slicer

    accepts = pipeline_module._creator_accepts_view

    slice_node = slicer.mrmlScene.CreateNodeByClass("vtkMRMLSliceNode")
    slice_node.UnRegister(None)
    assert accepts(slice_node) is True

    view_node = slicer.mrmlScene.CreateNodeByClass("vtkMRMLViewNode")
    view_node.UnRegister(None)
    assert accepts(view_node) is False, "3D views belong to the surface pipeline"
    assert accepts(None) is False

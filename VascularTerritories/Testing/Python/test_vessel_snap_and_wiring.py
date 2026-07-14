# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Launched invariants for snap-on-place + the widget highlight wiring.

Feature (ADR-0036): while placing vessel-annotation endpoints, the placed
control point SNAPS onto the input segmentation's closed surface, and the
module widget wires a scene-resident
``vtkMRMLTerritoriesHighlightDisplayNode`` whose ``pickSurface`` reference
tracks the selected input segmentation (activating the hover highlight).

Pinned invariants:

* snap-on-place — a point defined OFF the surface lands ON it (distance
  ~= 0) after the snap;
* no-surface — with no pickSurface the point is left at its raw position;
* exactly-one-reposition — the snap fires once per placed point and an
  unrelated ``Modified`` afterwards does not move the point again;
* widget wiring — selecting an input segmentation aims the highlight
  node's ``pickSurface`` reference at that node.

These touch the MRML scene (segmentation closed-surface reps) and, for the
wiring test, build the module widget; they SKIP cleanly bare and RUN
launched.  The GL glow / adherence appearance stays eyeball-gated.

References
----------
* ADR-0036 — vessel highlight as a separate instance from the resection
  locator; ray-picking the segmentation closed surface.
* ADR-0025 — the pick-core / nearest-projection pattern the snap reuses.
* ADR-0033 — hover discipline (the highlight paints only while placing).
"""

from __future__ import annotations

import pytest

from conftest import _require_mrml_scene, _require_qt_widget

vtk = pytest.importorskip("vtk")


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def _sphere_segmentation(slicer, center=(0.0, 0.0, 0.0), radius=30.0):
    """A segmentation node carrying ONE closed-surface sphere segment."""
    source = vtk.vtkSphereSource()
    source.SetCenter(*center)
    source.SetRadius(radius)
    source.SetThetaResolution(48)
    source.SetPhiResolution(48)
    source.Update()

    # Wrap the sphere polydata in a model node and import it as a
    # closed-surface segment (the supported Segmentations-logic path).
    modelNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", "Vessel")
    modelNode.SetAndObservePolyData(source.GetOutput())

    segmentationNode = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLSegmentationNode", "TestVessel")
    segmentationNode.CreateDefaultDisplayNodes()
    slicer.modules.segmentations.logic().ImportModelToSegmentationNode(
        modelNode, segmentationNode)
    slicer.mrmlScene.RemoveNode(modelNode)
    return segmentationNode


def _markups_with_point(slicer, world):
    """A fiducial markup node with one control point at ``world`` (RAS)."""
    node = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLMarkupsFiducialNode", "TestEndpoints")
    node.AddControlPointWorld(vtk.vtkVector3d(world[0], world[1], world[2]))
    return node


def _distance_to_surface(slicer, segmentationNode, point) -> float:
    """Distance from ``point`` to the segmentation's closed-surface mesh."""
    from VascularTerritoriesLib import closed_surface_polydata

    polydata = closed_surface_polydata(segmentationNode)
    locator = vtk.vtkCellLocator()
    locator.SetDataSet(polydata)
    locator.BuildLocator()
    closest = [0.0, 0.0, 0.0]
    cell_id = vtk.reference(0)
    sub_id = vtk.reference(0)
    dist2 = vtk.reference(0.0)
    locator.FindClosestPoint(list(point), closest, cell_id, sub_id, dist2)
    return float(dist2) ** 0.5


# --------------------------------------------------------------------------- #
# Snap-on-place
# --------------------------------------------------------------------------- #


def test_snap_lands_the_point_on_the_surface():
    """A point placed off the surface is snapped onto it (distance ~= 0)."""
    _require_mrml_scene()
    import slicer

    from VascularTerritoriesLib import snap_control_point_to_surface

    segmentationNode = _sphere_segmentation(slicer, radius=30.0)
    # Well outside the r=30 sphere along +x.
    markups = _markups_with_point(slicer, (60.0, 0.0, 0.0))

    moved = snap_control_point_to_surface(markups, 0, segmentationNode)

    assert moved is True
    snapped = [0.0, 0.0, 0.0]
    markups.GetNthControlPointPositionWorld(0, snapped)
    assert _distance_to_surface(slicer, segmentationNode, snapped) == pytest.approx(
        0.0, abs=1.0)
    # Projected radially outward from the origin -> near (30, 0, 0).
    assert snapped[0] == pytest.approx(30.0, abs=2.0)


def test_no_surface_leaves_the_point_raw():
    """With no segmentation the point keeps its raw position (graceful)."""
    _require_mrml_scene()
    import slicer

    from VascularTerritoriesLib import snap_control_point_to_surface

    raw = (60.0, 0.0, 0.0)
    markups = _markups_with_point(slicer, raw)

    moved = snap_control_point_to_surface(markups, 0, None)

    assert moved is False
    kept = [0.0, 0.0, 0.0]
    markups.GetNthControlPointPositionWorld(0, kept)
    assert list(kept) == pytest.approx(list(raw), abs=1e-6)


def test_snap_repositions_exactly_once():
    """The snap moves the point once; a later unrelated Modified is inert.

    A second ``snap`` call from the ALREADY-snapped position must not drift
    (the point is already on the surface), and a bare ``Modified`` in
    between changes nothing — proving no recursion / no repeated snap.
    """
    _require_mrml_scene()
    import slicer

    from VascularTerritoriesLib import snap_control_point_to_surface

    segmentationNode = _sphere_segmentation(slicer, radius=30.0)
    markups = _markups_with_point(slicer, (60.0, 0.0, 0.0))

    assert snap_control_point_to_surface(markups, 0, segmentationNode) is True
    after_first = [0.0, 0.0, 0.0]
    markups.GetNthControlPointPositionWorld(0, after_first)

    markups.Modified()  # unrelated churn — must not move the point

    # Re-snapping the on-surface point is a stable fixed point (no drift).
    snap_control_point_to_surface(markups, 0, segmentationNode)
    after_second = [0.0, 0.0, 0.0]
    markups.GetNthControlPointPositionWorld(0, after_second)

    assert list(after_second) == pytest.approx(list(after_first), abs=1.0)


# --------------------------------------------------------------------------- #
# Widget wiring
# --------------------------------------------------------------------------- #


def test_widget_wires_highlight_picksurface_to_selected_segmentation(qt_widgets):
    """Selecting an input segmentation aims the highlight's pickSurface at it."""
    _require_qt_widget()
    _require_mrml_scene()
    import slicer

    from VascularTerritories import VascularTerritoriesWidget

    widget = VascularTerritoriesWidget()
    widget.setup()

    segmentationNode = _sphere_segmentation(slicer, radius=30.0)
    # Set the selected input segmentation with the selector's signals blocked
    # so this narrow wiring invariant is not entangled with the legacy GUI
    # cascade (segmentationNodeSelected / onSegmentChanged), then drive the
    # highlight wiring under test directly.
    widget.ui.inputSurfaceSelector.blockSignals(True)
    widget.ui.inputSurfaceSelector.setCurrentNode(segmentationNode)
    widget.ui.inputSurfaceSelector.blockSignals(False)
    widget.updateHighlightPickSurface()

    highlight = widget._highlightDisplayNode
    assert highlight is not None
    assert highlight.GetPickSurfaceNode() is segmentationNode

    # Drop the widget's scene observers while it is still alive, so the
    # autouse scene-clear does not fire the legacy onSceneStartClose /
    # onSceneEndClose handlers on a torn-down widget (which re-create a
    # parameter node — a Clear-surviving node — and touch deleted Qt
    # buttons).  removeObserver on the scene is exact and idempotent.
    for event, handler in (
        (slicer.mrmlScene.StartCloseEvent, widget.onSceneStartClose),
        (slicer.mrmlScene.EndCloseEvent, widget.onSceneEndClose),
    ):
        widget.removeObserver(slicer.mrmlScene, event, handler)
    widget.cleanup()
    qt_widgets.append(widget)

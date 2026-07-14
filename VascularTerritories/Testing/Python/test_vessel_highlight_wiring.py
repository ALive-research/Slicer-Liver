# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Launched invariant for the widget's vessel-highlight wiring (ADR-0037).

The module widget wires a scene-resident
``vtkMRMLTerritoriesHighlightDisplayNode`` whose ``pickSurface`` reference
tracks the selected input segmentation, activating the hover highlight.

Placement + snap are NOT here: they live on the LayerDM
``TerritoryPlacementPipeline`` against the annotation carrier, not a markup
observer (ADR-0037 — VascularTerritories off markups).  This file pins only
the surviving hover-highlight wiring; the pipeline placement/edit invariants
live in ``test_territories_placement_pipeline.py``.

Touches the MRML scene + builds the module widget; SKIPS cleanly bare, RUNS
launched.  The GL glow / adherence appearance stays eyeball-gated.

References
----------
* ADR-0037 — VascularTerritories transition off markups.
* ADR-0033 — hover discipline (the highlight paints only while placing).
"""

from __future__ import annotations

import pytest

from conftest import _require_mrml_scene, _require_qt_widget

vtk = pytest.importorskip("vtk")


def _sphere_segmentation(slicer, center=(0.0, 0.0, 0.0), radius=30.0):
    """A segmentation node carrying ONE closed-surface sphere segment."""
    source = vtk.vtkSphereSource()
    source.SetCenter(*center)
    source.SetRadius(radius)
    source.SetThetaResolution(48)
    source.SetPhiResolution(48)
    source.Update()

    modelNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", "Vessel")
    modelNode.SetAndObservePolyData(source.GetOutput())

    segmentationNode = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLSegmentationNode", "TestVessel")
    segmentationNode.CreateDefaultDisplayNodes()
    slicer.modules.segmentations.logic().ImportModelToSegmentationNode(
        modelNode, segmentationNode)
    slicer.mrmlScene.RemoveNode(modelNode)
    return segmentationNode


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
    # onSceneEndClose handlers on a torn-down widget.
    for event, handler in (
        (slicer.mrmlScene.StartCloseEvent, widget.onSceneStartClose),
        (slicer.mrmlScene.EndCloseEvent, widget.onSceneEndClose),
    ):
        widget.removeObserver(slicer.mrmlScene, event, handler)
    widget.cleanup()
    qt_widgets.append(widget)

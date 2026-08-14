# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Show-3D precondition: selecting an input keeps its segment(s) VISIBLE.

The volumetry panel binds ``qMRMLSegmentationShow3DButton`` to the selected
input segmentation.  Show-3D builds the closed-surface representation of the
segmentation's VISIBLE segments, so if selection HID every segment (the prior
behaviour) Show-3D created the surface but nothing rendered -- the reported
"Show 3D shows nothing".

This file pins the fix: after selecting a segmentation the selected segment(s)
are visible (falling back to ALL segments when none is specifically picked), so
Show-3D always has a surface to build -- matching Slicer's own Show-3D
behaviour.

* i1 (launched, widget) -- selecting a segmentation with no specific segment
  selection leaves at least one segment VISIBLE (Show-3D precondition).
* i2 (launched, widget) -- selecting a specific segment makes THAT segment
  visible and hides the rest.

Both need the wrapped node + a live scene + Qt, so they SKIP cleanly bare and
RUN launched (ADR-0027).

See also:
  * Docs/design/volumetry-workflow-consistency-critique.md
  * LiverVolumetry/Testing/Python/test_volumetry_action_enablement.py
"""

from __future__ import annotations

import pytest

vtk = pytest.importorskip("vtk")

SEGMENTATION_CLASS = "vtkMRMLSegmentationNode"


def _slicer_or_skip():
    from conftest import _import_slicer_or_skip, _require_mrml_scene

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _make_widget_or_skip(slicer):
    from conftest import _require_qt_widget

    _require_qt_widget()
    from LiverVolumetry import LiverVolumetryWidget

    # Explicit parent: with parent=None, ScriptedLoadableModuleWidget's
    # __init__ auto-runs setup() (and show()), so the explicit setup()
    # below would run TWICE -- stacking two panels and registering
    # duplicate scene observers that outlive cleanup() (the destroyed-ui
    # 'enabled' storm, feedback_launched_widget_teardown_crash).
    import qt

    widgetParent = qt.QWidget()
    qt.QVBoxLayout(widgetParent)
    widget = LiverVolumetryWidget(widgetParent)
    widget.setup()
    return widget


def _detach_scene_observers(slicer, widget):
    for event, handler in (
        (slicer.mrmlScene.StartCloseEvent, widget.onSceneStartClose),
        (slicer.mrmlScene.EndCloseEvent, widget.onSceneEndClose),
    ):
        try:
            widget.removeObserver(slicer.mrmlScene, event, handler)
        except Exception:  # noqa: BLE001 - best-effort across widget shapes
            pass


def _two_segment_segmentation(slicer, name="Show3DLiver"):
    """A two-segment segmentation so hide/show of a subset is observable."""
    seg = slicer.mrmlScene.AddNewNodeByClass(SEGMENTATION_CLASS, name)
    seg.CreateDefaultDisplayNodes()
    for radius, label in ((20.0, "A"), (12.0, "B")):
        source = vtk.vtkSphereSource()
        source.SetRadius(radius)
        source.SetThetaResolution(16)
        source.SetPhiResolution(16)
        source.Update()
        modelNode = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLModelNode", name + label)
        modelNode.SetAndObservePolyData(source.GetOutput())
        slicer.modules.segmentations.logic().ImportModelToSegmentationNode(modelNode, seg)
        slicer.mrmlScene.RemoveNode(modelNode)
    return seg


def _visible_segment_ids(displayNode):
    array = vtk.vtkStringArray()
    displayNode.GetVisibleSegmentIDs(array)
    return {array.GetValue(i) for i in range(array.GetNumberOfValues())}


def test_selecting_segmentation_leaves_a_segment_visible(qt_widgets):
    """Selecting a segmentation with no picked segment keeps segments VISIBLE.

    The Show-3D precondition: at least one segment must be visible or the
    closed-surface build renders nothing.  Launched (widget); SKIPS bare.
    """
    slicer = _slicer_or_skip()
    widget = _make_widget_or_skip(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)

    seg = _two_segment_segmentation(slicer)
    widget.ui.InputSegmentSelectorWidget.setCurrentNode(seg)
    widget.segmentationNodeSelected()

    displayNode = seg.GetDisplayNode()
    visible = _visible_segment_ids(displayNode)
    assert len(visible) > 0, (
        "selecting a segmentation must leave at least one segment VISIBLE so "
        "Show-3D has a surface to build (the reported 'Show 3D shows nothing' "
        "was the prior hide-all)."
    )


def test_selecting_a_segment_shows_that_segment_and_hides_the_rest(qt_widgets):
    """Picking a specific segment makes THAT segment visible; the rest hidden.

    Launched (widget); SKIPS bare.
    """
    slicer = _slicer_or_skip()
    widget = _make_widget_or_skip(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)

    seg = _two_segment_segmentation(slicer)
    widget.ui.InputSegmentSelectorWidget.setCurrentNode(seg)

    allIDs = list(widget.ui.InputSegmentSelectorWidget.segmentIDs())
    if len(allIDs) < 2:
        pytest.skip("two-segment segmentation not built in this harness (ADR-0027).")
    picked = allIDs[0]
    widget.ui.InputSegmentSelectorWidget.setSelectedSegmentIDs([picked])
    widget.onSegmentChanged()

    displayNode = seg.GetDisplayNode()
    visible = _visible_segment_ids(displayNode)
    assert picked in visible, "the picked segment must be VISIBLE."
    assert visible == {picked}, (
        "only the picked segment must be visible; the rest must be hidden."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

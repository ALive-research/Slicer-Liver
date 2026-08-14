# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Show-3D preserves the segmentation's per-segment display parameters.

FIX D: selecting a segmentation for volumetry (and the Show-3D path that
follows) must toggle ONLY the per-segment VISIBILITY it needs (the Show-3D
precondition pinned by ``test_volumetry_show3d_visibility.py``) and leave the
per-segment COLOUR / OPACITY / other display properties untouched -- the liver
/ vessel colours the user or another module set must survive selection.

* i1 (launched, widget) -- ``segmentationNodeSelected`` leaves every segment's
  colour + 3D opacity exactly as they were before selection (only visibility
  changes).

Needs the wrapped segmentation node + a live scene + Qt, so it SKIPS cleanly
bare and RUNS launched (ADR-0027).

See also:
  * LiverVolumetry/Testing/Python/test_volumetry_show3d_visibility.py -- the
    visibility precondition this complements (visibility MAY change; colour /
    opacity may NOT).
  * Docs/design/volumetry-workflow-consistency-critique.md
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


def _two_segment_segmentation(slicer, name="Show3DPreserve"):
    seg = slicer.mrmlScene.AddNewNodeByClass(SEGMENTATION_CLASS, name)
    seg.CreateDefaultDisplayNodes()
    for radius, label in ((20.0, "A"), (12.0, "B")):
        source = vtk.vtkSphereSource()
        source.SetRadius(radius)
        source.SetThetaResolution(16)
        source.SetPhiResolution(16)
        source.Update()
        modelNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", name + label)
        modelNode.SetAndObservePolyData(source.GetOutput())
        slicer.modules.segmentations.logic().ImportModelToSegmentationNode(modelNode, seg)
        slicer.mrmlScene.RemoveNode(modelNode)
    return seg


def _display_snapshot(displayNode, segmentIDs):
    """The per-segment colour + 3D opacity, so a mutation is observable."""
    snapshot = {}
    for sid in segmentIDs:
        snapshot[sid] = (
            tuple(displayNode.GetSegmentColor(sid)),
            float(displayNode.GetSegmentOpacity3D(sid)),
        )
    return snapshot


def test_selecting_segmentation_preserves_segment_colours_and_opacity(qt_widgets):
    """FIX D: selecting an input leaves per-segment colour + opacity untouched.

    Only visibility may change (the Show-3D precondition); the liver / vessel
    colours + opacities another module or the user set must survive.  Launched
    (widget); SKIPS bare.
    """
    slicer = _slicer_or_skip()
    widget = _make_widget_or_skip(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)

    seg = _two_segment_segmentation(slicer)
    displayNode = seg.GetDisplayNode()
    segmentIDs = list(widget.ui.InputSegmentSelectorWidget.segmentIDs()) if hasattr(
        widget.ui, "InputSegmentSelectorWidget") else []
    if len(segmentIDs) < 2:
        # Fall back to the segmentation's own segment IDs when the selector
        # has not populated in this harness.
        seg_ids = vtk.vtkStringArray()
        seg.GetSegmentation().GetSegmentIDs(seg_ids)
        segmentIDs = [seg_ids.GetValue(i) for i in range(seg_ids.GetNumberOfValues())]
    if len(segmentIDs) < 2:
        pytest.skip("two-segment segmentation not built in this harness (ADR-0027).")

    # Give each segment a DISTINCT non-default colour + opacity so a clobber
    # (a reset to the palette default) is observable.
    displayNode.SetSegmentOpacity3D(segmentIDs[0], 0.37)
    displayNode.SetSegmentColor(segmentIDs[0], 0.11, 0.22, 0.33)
    displayNode.SetSegmentOpacity3D(segmentIDs[1], 0.81)
    displayNode.SetSegmentColor(segmentIDs[1], 0.44, 0.55, 0.66)
    before = _display_snapshot(displayNode, segmentIDs)

    widget.ui.InputSegmentSelectorWidget.setCurrentNode(seg)
    widget.segmentationNodeSelected()

    after = _display_snapshot(displayNode, segmentIDs)
    for sid in segmentIDs:
        beforeColor, beforeOpacity = before[sid]
        afterColor, afterOpacity = after[sid]
        assert afterColor == pytest.approx(beforeColor, abs=1e-6), (
            f"segment {sid}: selecting a segmentation must NOT change its colour "
            "(Show-3D preserves visualization parameters; FIX D)."
        )
        assert afterOpacity == pytest.approx(beforeOpacity, abs=1e-6), (
            f"segment {sid}: selecting a segmentation must NOT change its 3D "
            "opacity (Show-3D preserves visualization parameters; FIX D)."
        )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

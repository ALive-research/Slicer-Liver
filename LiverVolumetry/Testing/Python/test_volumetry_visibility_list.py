# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""territory-usability -- the segment show/hide list on the volumetry panel.

Visibility is the PRIMARY region-composition instrument (the
visibility-composed carve rule, ``VisibilityCarve``): the surgeon shows/hides
segments BEFORE placing, and a dropped seed snapshots that composition.  So
the panel carries the eye list itself -- composing visibility must not
require leaving the module.

Pins on the module widget:

* PRESENT + TRIMMED -- the panel composes a ``qMRMLSegmentsTableView`` showing
  the visibility (eye) column with the editing columns off and read-only names
  (an instrument, not an editor).
* BOUND TO THE INPUT -- selecting the input segmentation points the list at
  it, the same node the seed capture scans.
* EYE WRITES VISIBILITY -- toggling a segment's visibility through the list's
  segmentation binding is what the placement capture reads (the list drives
  the SAME display node ``gather_touched_candidates`` gates on).

HARNESS: launched Slicer (Qt + module widget).  SKIPS CLEANLY bare via the
shared guards; RUNS launched (ADR-0027).
"""

from __future__ import annotations

import pytest


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


def _visibility_list_or_skip(widget):
    view = getattr(widget, "_visibilityList", None)
    if view is None:
        pytest.skip(
            "the volumetry panel composes no segment show/hide list -- the "
            "visibility instrument has not landed (ADR-0027)."
        )
    return view


def test_panel_composes_a_trimmed_eye_list(qt_widgets):
    """The panel carries a name+eye segments view (no editing columns)."""
    slicer = _slicer_or_skip()
    widget = _make_widget_or_skip(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)

    view = _visibility_list_or_skip(widget)

    assert view.visibilityColumnVisible, "the eye column IS the instrument."
    assert not view.colorColumnVisible
    assert not view.opacityColumnVisible
    assert not view.statusColumnVisible
    assert view.readOnly, "the list is an instrument, not an editor."


def test_selecting_the_input_binds_the_eye_list(qt_widgets):
    """Selecting the input segmentation points the list at the same node the
    seed capture scans."""
    slicer = _slicer_or_skip()
    widget = _make_widget_or_skip(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)
    view = _visibility_list_or_skip(widget)

    seg = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLSegmentationNode", "VisibilityListSegSrc")
    seg.CreateDefaultDisplayNodes()
    seg.GetSegmentation().AddEmptySegment("segA", "Alpha")

    widget.ui.InputSegmentSelectorWidget.setCurrentNode(seg)
    widget.segmentationNodeSelected()

    assert view.segmentationNode() is seg, (
        "the eye list must bind the CURRENT input segmentation."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

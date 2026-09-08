# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Resectogram-margins: exactly two margins; the transection line is owned.

The eyeball campaign found a third, automatic "margin": the strip's black
parenchyma-boundary iso-line (and the 3D shader's hard-coded band-C black
ring, removed in the same change).  The bands are exactly the plan's
Safety / Risk pair; the black line is the TRANSECTION CONTOUR -- where the
resection surface exits the organ -- informational, and now owned by the
resectogram display node's ``ShowTransectionContour`` field with a Stage-4
checkbox.

Pins: the display-node field's default (shown) + round-trip; the
Representation threading the field onto the 2D mapper (fake-mapper idiom of
``test_flattened_surface_band_style.py``); the Stage-4 checkbox writing the
ACTIVE carrier's resectogram display node (harness shape of
``test_resection_planning_widget_margin_controls.py``).

Band-C's removal itself is a shader-text change -- verified on the :0
eyeball and by C++ review, not asserted here.
"""

from __future__ import annotations

import pytest

BEZIER_NODE_CLASS = "vtkMRMLBezierSurfaceNode"
RESECTOGRAM_DISPLAY_NODE_CLASS = "vtkMRMLResectogramDisplayNode"
PLAN_NODE_CLASS = "vtkMRMLResectionPlanNode"
VOLUME_NODE_CLASS = "vtkMRMLScalarVolumeNode"
MODULE_NAME = "liverresections"


def _slicer_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _add_or_skip(slicer, node_class):
    node = slicer.mrmlScene.AddNewNodeByClass(node_class)
    if node is None:
        pytest.skip(f"{node_class} not registered in this build.")
    return node


def _require_field_or_skip(display):
    if not hasattr(display, "GetShowTransectionContour"):
        pytest.skip(
            "vtkMRMLResectogramDisplayNode has no ShowTransectionContour -- "
            "the two-margin-bands change has not landed."
        )


def test_transection_contour_defaults_shown_and_round_trips():
    slicer = _slicer_or_skip()
    display = _add_or_skip(slicer, RESECTOGRAM_DISPLAY_NODE_CLASS)
    _require_field_or_skip(display)

    assert display.GetShowTransectionContour() is True, (
        "the transection contour defaults SHOWN (it carries information; "
        "the eyeball finding was the lack of ownership, not the line)."
    )
    display.SetShowTransectionContour(False)
    assert display.GetShowTransectionContour() is False


class _FakeMapper:
    def __init__(self):
        self.show_transection = None
        self.texture_num_comps = None

    def SetShowTransectionContour(self, show):  # noqa: N802 - VTK verb
        self.show_transection = bool(show)

    def SetTextureNumComps(self, value):  # noqa: N802 - VTK verb
        self.texture_num_comps = int(value)


def test_representation_threads_the_toggle():
    slicer = _slicer_or_skip()
    try:
        from LiverResectionsLib.Representations.FlattenedSurfaceRepresentation import (
            FlattenedSurfaceRepresentation,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(f"FlattenedSurfaceRepresentation not importable ({exc!r}).")
    rep = FlattenedSurfaceRepresentation()

    display = _add_or_skip(slicer, RESECTOGRAM_DISPLAY_NODE_CLASS)
    _require_field_or_skip(display)
    data = _add_or_skip(slicer, BEZIER_NODE_CLASS)

    fake = _FakeMapper()
    rep._resection_mapper_2d = fake

    display.SetShowTransectionContour(False)
    rep.update(display, data)
    assert fake.show_transection is False, (
        "the display node's ShowTransectionContour must reach the 2D "
        "mapper's SetShowTransectionContour."
    )
    display.SetShowTransectionContour(True)
    rep.update(display, data)
    assert fake.show_transection is True


def test_stage4_checkbox_writes_the_display_node():
    slicer = _slicer_or_skip()
    from slicer_pytest_support import require_qt_widget, register_widget_for_teardown

    require_qt_widget()
    if getattr(slicer.modules, MODULE_NAME, None) is None:
        pytest.skip(f"'{MODULE_NAME}' module not registered.")
    try:
        from LiverResectionsLib.ResectionPlanningWidget import (
            ResectionPlanningWidget,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(f"ResectionPlanningWidget not importable ({exc!r}).")
    widget = ResectionPlanningWidget()
    widget.setMRMLScene(slicer.mrmlScene)
    register_widget_for_teardown(widget)
    if not hasattr(widget, "transectionContourCheckBox"):
        pytest.skip(
            "ResectionPlanningWidget has no transectionContourCheckBox -- "
            "the two-margin-bands change has not landed."
        )

    plan = _add_or_skip(slicer, PLAN_NODE_CLASS)
    carrier = _add_or_skip(slicer, BEZIER_NODE_CLASS)
    if not hasattr(plan, "SetAndObserveGeometryNode"):
        pytest.skip(f"{PLAN_NODE_CLASS} has no SetAndObserveGeometryNode.")
    plan.SetAndObserveGeometryNode(carrier)
    volume = _add_or_skip(slicer, VOLUME_NODE_CLASS)
    if not hasattr(plan, "SetAndObserveDistanceMapVolumeNode"):
        pytest.skip(f"{PLAN_NODE_CLASS} has no distance-map reference API.")
    plan.SetAndObserveDistanceMapVolumeNode(volume)

    widget.resectionSurfaceComboBox().setCurrentNode(plan)
    display = widget._existingResectogramDisplayNode(carrier)
    if display is None:
        pytest.skip("the drawer did not ensure a resectogram display node.")
    _require_field_or_skip(display)

    widget.transectionContourCheckBox().setChecked(False)
    assert display.GetShowTransectionContour() is False, (
        "the Stage-4 checkbox must write ShowTransectionContour on the "
        "active carrier's resectogram display node."
    )
    widget.transectionContourCheckBox().setChecked(True)
    assert display.GetShowTransectionContour() is True


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))

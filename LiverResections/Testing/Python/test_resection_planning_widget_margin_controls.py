# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Resectogram-margins slice 3 -- Stage-4 margin controls author the plan.

ADR-0023 §Stage-4 puts the margin INPUTS on the resection-planning panel
(margin-dependent controls disable without a distance map, §"UI elements
that depend on the distance maps"); the plan wrapper carries the values
(``SafetyMargin`` / ``RiskMargin``, millimetres -- ADR-0031) and the
carrier's ``vtkMRMLParametricSurfaceDisplayNode`` carries the
``InterpolatedMargins`` band-style flag.  Slices 1-2 made every write
repaint both views; this slice adds the authoring surface: two mm
spinboxes (Safety / Risk), a total-margin readout, and an "Interpolated
margins" checkbox, with the v1 floor-clamp (safety >= risk keeps the
shader's ``lowMargin = safety - risk`` non-negative) and blockSignals
pull-back discipline.

All invariants are widget/MRML state, GPU-free, runnable under the
``--no-main-window`` launched harness.

-- WHY LAUNCHED-SLICER + SKIP-PENDING --

Same harness shape as ``test_resection_planning_widget_v2_repoint.py``
(the guards + teardown registration are shared).  Every test is guarded
on the margin-controls' PRESENCE (``hasattr(widget,
"safetyMarginSpinBox")``), so this lands RED-as-skip and turns green at
the implementation commit (ADR-0027 §Conformance).  Verify run-vs-skip
in the CI log; never trust overall green.

-- NOT PINNED HERE --

The bands actually recolouring on screen is the epic's :0 eyeball
checklist (items 3-6); this file pins only the widget <-> node contract.

See also:
  * Docs/adr/0023-unified-gui-stage-workflow.md §Stage-4 (margin inputs)
  * Docs/adr/0031-distance-map-input-on-resection-plan.md (+ Amendment:
    the field rename this file's API calls follow)
  * Docs/architecture/ui-stage-4-resection-planning.md (inputs-here,
    computed-readouts-in-Stage-5 split)
  * LiverResections/Testing/Python/test_resection_planning_widget_v2_repoint.py
    (the harness shape this clones)
"""

from __future__ import annotations

import pytest

MODULE_NAME = "liverresections"
PLAN_NODE_CLASS = "vtkMRMLResectionPlanNode"
BEZIER_CARRIER_CLASS = "vtkMRMLBezierSurfaceNode"
SURFACE_DISPLAY_CLASS = "vtkMRMLParametricSurfaceDisplayNode"
VOLUME_NODE_CLASS = "vtkMRMLScalarVolumeNode"
VIEW_NODE_CLASS = "vtkMRMLViewNode"


# --------------------------------------------------------------------------- #
# Test isolation -- reclaim the resectogram singleton view node after each
# test (the distance-map-present fixtures run the auto-populate branch, which
# mints the singleton view + camera; both survive scene Clear by design).
# Mirrors test_resection_planning_widget_v2_repoint.py.
# --------------------------------------------------------------------------- #


def _purge_resectogram_singleton_view():
    try:
        import slicer  # type: ignore[import-not-found]
        from LiverResectionsLib.ResectogramViewManager import (  # type: ignore[import-not-found]
            RESECTOGRAM_VIEW_SINGLETON_TAG,
        )
    except Exception:  # pragma: no cover - bare-pytest / import-env dependent
        return
    scene = getattr(slicer, "mrmlScene", None)
    if scene is None:
        return
    stale_views, stale_ids = [], set()
    for index in range(scene.GetNumberOfNodesByClass(VIEW_NODE_CLASS)):
        node = scene.GetNthNodeByClass(index, VIEW_NODE_CLASS)
        if node is not None and node.GetSingletonTag() == RESECTOGRAM_VIEW_SINGLETON_TAG:
            stale_views.append(node)
            stale_ids.add(node.GetID())
    for index in range(scene.GetNumberOfNodesByClass("vtkMRMLCameraNode")):
        camera = scene.GetNthNodeByClass(index, "vtkMRMLCameraNode")
        if camera is not None and camera.GetActiveTag() in stale_ids:
            scene.RemoveNode(camera)
    for node in stale_views:
        scene.RemoveNode(node)


@pytest.fixture(autouse=True)
def _drop_resectogram_singleton_view():
    _purge_resectogram_singleton_view()
    yield
    _purge_resectogram_singleton_view()


# --------------------------------------------------------------------------- #
# Skip-guards
# --------------------------------------------------------------------------- #


def _slicer_or_skip():
    from slicer_pytest_support import import_slicer_or_skip, require_mrml_scene

    require_mrml_scene()
    return import_slicer_or_skip()


def _widget_or_skip(slicer):
    from slicer_pytest_support import require_qt_widget, register_widget_for_teardown

    require_qt_widget()
    if getattr(slicer.modules, MODULE_NAME, None) is None:
        pytest.skip(f"'{MODULE_NAME}' module not registered.")
    try:
        from LiverResectionsLib.ResectionPlanningWidget import (  # type: ignore[import-not-found]
            ResectionPlanningWidget,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(f"ResectionPlanningWidget not importable ({exc!r}).")
    widget = ResectionPlanningWidget()
    widget.setMRMLScene(slicer.mrmlScene)
    return register_widget_for_teardown(widget)


def _require_margin_controls_or_skip(widget):
    """RED gate: the margin controls have not landed yet."""
    if not hasattr(widget, "safetyMarginSpinBox"):
        pytest.skip(
            "ResectionPlanningWidget has no safetyMarginSpinBox() accessor -- "
            "resectogram-margins slice 3 (Stage-4 margin controls) has not "
            "landed."
        )


def _add_or_skip(slicer, node_class):
    node = slicer.mrmlScene.AddNewNodeByClass(node_class)
    if node is None:
        pytest.skip(f"{node_class} not registered in this build.")
    return node


def _wire_plan(slicer, *, with_distance_map, with_surface_display=False):
    """plan --geometry--> carrier (+ optional distance map / display aspect)."""
    plan = _add_or_skip(slicer, PLAN_NODE_CLASS)
    carrier = _add_or_skip(slicer, BEZIER_CARRIER_CLASS)
    if not hasattr(plan, "SetAndObserveGeometryNode"):
        pytest.skip(f"{PLAN_NODE_CLASS} has no SetAndObserveGeometryNode.")
    plan.SetAndObserveGeometryNode(carrier)
    if not (hasattr(plan, "SetSafetyMargin") and hasattr(plan, "SetRiskMargin")):
        pytest.skip(f"{PLAN_NODE_CLASS} has no Safety/Risk margin setters.")
    if with_distance_map:
        volume = _add_or_skip(slicer, VOLUME_NODE_CLASS)
        if not hasattr(plan, "SetAndObserveDistanceMapVolumeNode"):
            pytest.skip(f"{PLAN_NODE_CLASS} has no distance-map reference API.")
        plan.SetAndObserveDistanceMapVolumeNode(volume)
    display = None
    if with_surface_display:
        display = _add_or_skip(slicer, SURFACE_DISPLAY_CLASS)
        carrier.AddAndObserveDisplayNodeID(display.GetID())
    return plan, carrier, display


def _select(widget, plan):
    widget.resectionSurfaceComboBox().setCurrentNode(plan)


def test_margins_group_gates_on_distance_map():
    """The group enables iff the selected plan carries a distance map.

    Three states: no selection -> disabled; plan without map -> disabled;
    attaching the map (the wrapper Modified re-refresh path) -> enabled.
    ADR-0023 §Stage-4 distance-map gate.
    """
    slicer = _slicer_or_skip()
    widget = _widget_or_skip(slicer)
    _require_margin_controls_or_skip(widget)

    group = widget.marginsGroupBox()
    assert not group.enabled, "no selection -> margin controls disabled."

    plan, carrier, _ = _wire_plan(slicer, with_distance_map=False)
    _select(widget, plan)
    assert not group.enabled, "plan without distance map -> still disabled."

    volume = _add_or_skip(slicer, VOLUME_NODE_CLASS)
    plan.SetAndObserveDistanceMapVolumeNode(volume)
    assert group.enabled, (
        "attaching the distance map fires the active-plan observer and must "
        "enable the margin controls."
    )


def test_spinboxes_write_the_plan_margins():
    """The real integrated path: spinbox edits land on the wrapper."""
    slicer = _slicer_or_skip()
    widget = _widget_or_skip(slicer)
    _require_margin_controls_or_skip(widget)

    plan, carrier, _ = _wire_plan(slicer, with_distance_map=True)
    _select(widget, plan)

    widget.safetyMarginSpinBox().setValue(10.0)
    assert abs(plan.GetSafetyMargin() - 10.0) < 1e-9, (
        "the Safety spinbox must write plan.SetSafetyMargin."
    )
    widget.riskMarginSpinBox().setValue(2.0)
    assert abs(plan.GetRiskMargin() - 2.0) < 1e-9, (
        "the Risk spinbox must write plan.SetRiskMargin."
    )


def test_risk_floor_clamps_safety():
    """v1 parity: raising risk floors the safety spinbox and writes through.

    Keeps the shader's ``lowMargin = safety - risk`` non-negative: safety 5
    then risk 8 -> safety minimum climbs to 8, its value clamps to 8, and the
    clamp-raised valueChanged writes the plan.
    """
    slicer = _slicer_or_skip()
    widget = _widget_or_skip(slicer)
    _require_margin_controls_or_skip(widget)

    plan, carrier, _ = _wire_plan(slicer, with_distance_map=True)
    _select(widget, plan)

    widget.safetyMarginSpinBox().setValue(5.0)
    widget.riskMarginSpinBox().setValue(8.0)

    assert abs(widget.safetyMarginSpinBox().minimum - 8.0) < 1e-9, (
        "the safety spinbox minimum must floor at the risk value."
    )
    assert abs(widget.safetyMarginSpinBox().value - 8.0) < 1e-9, (
        "the safety value must clamp up to the floor."
    )
    assert abs(plan.GetSafetyMargin() - 8.0) < 1e-9, (
        "the clamp-raised value must write through to the plan."
    )


def test_total_margin_label_tracks_the_sum():
    slicer = _slicer_or_skip()
    widget = _widget_or_skip(slicer)
    _require_margin_controls_or_skip(widget)

    plan, carrier, _ = _wire_plan(slicer, with_distance_map=True)
    _select(widget, plan)

    widget.safetyMarginSpinBox().setValue(10.0)
    widget.riskMarginSpinBox().setValue(2.0)
    assert widget.totalMarginLabel().text == "12.00 mm", (
        "total label must show safety + risk with the v1 two-decimal format; "
        f"got {widget.totalMarginLabel().text!r}."
    )


def test_interpolated_checkbox_writes_the_display_node():
    """The checkbox writes InterpolatedMargins on the carrier's parametric
    display node -- and the plan gains no new field (colours-on-display
    discipline, target-mrml-node-hierarchy)."""
    slicer = _slicer_or_skip()
    widget = _widget_or_skip(slicer)
    _require_margin_controls_or_skip(widget)

    plan, carrier, display = _wire_plan(
        slicer, with_distance_map=True, with_surface_display=True
    )
    if not hasattr(display, "SetInterpolatedMargins"):
        pytest.skip(f"{SURFACE_DISPLAY_CLASS} has no InterpolatedMargins.")
    _select(widget, plan)

    widget.interpolatedMarginsCheckBox().setChecked(True)
    assert display.GetInterpolatedMargins() is True, (
        "the checkbox must write InterpolatedMargins on the carrier's "
        "parametric-surface display node."
    )
    assert not hasattr(plan, "GetInterpolatedMargins"), (
        "the plan wrapper must NOT grow an InterpolatedMargins field."
    )


def test_selection_pull_back_syncs_without_writing():
    """Selecting a plan pulls its values into the controls with blockSignals
    discipline: the sync itself must not echo a write back (plan MTime
    unchanged by the selection)."""
    slicer = _slicer_or_skip()
    widget = _widget_or_skip(slicer)
    _require_margin_controls_or_skip(widget)

    plan, carrier, display = _wire_plan(
        slicer, with_distance_map=True, with_surface_display=True
    )
    plan.SetSafetyMargin(9.0)
    plan.SetRiskMargin(3.0)
    if hasattr(display, "SetInterpolatedMargins"):
        display.SetInterpolatedMargins(True)
    mtime_before = plan.GetMTime()

    _select(widget, plan)

    assert abs(widget.safetyMarginSpinBox().value - 9.0) < 1e-9
    assert abs(widget.riskMarginSpinBox().value - 3.0) < 1e-9
    if hasattr(display, "GetInterpolatedMargins"):
        assert widget.interpolatedMarginsCheckBox().checked is True
    assert plan.GetMTime() == mtime_before, (
        "the pull-back sync must not write the plan (blockSignals "
        "discipline) -- the plan MTime advanced during selection."
    )


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))

# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Stage 4 explains WHY it is not showing a resectogram (ADR-0009).

Two silences found by the 2026-09 eyeball, both of which read as "the
resectogram is broken":

* a plan minted BEFORE the distance map was computed never picked one up
  -- ``CreateResectionPlan`` auto-attaches only at mint time -- so the
  drawer and margins stayed disabled with no recovery short of
  delete-and-replace (#624);
* a plan still in Init has no fitted surface, so the strip renders a
  near-uniform readout rather than saying the initialization is
  incomplete (#623).

HARNESS: launched Slicer.  Needs the widget, the wrapped plan node and a
live scene, so a bare run SKIPS CLEANLY (ADR-0027).
"""

from __future__ import annotations

import pytest


def _slicer_or_skip():
    from slicer_pytest_support import import_slicer_or_skip, require_mrml_scene

    require_mrml_scene()
    return import_slicer_or_skip()


def _widget_or_skip(slicer):
    import qt

    for child in slicer.util.mainWindow().findChildren(qt.QWidget) if slicer.util.mainWindow() else []:
        if hasattr(child, "_attachExistingDistanceMap"):
            return child
    try:
        from LiverResectionsLib.ResectionPlanningWidget import ResectionPlanningWidget
    except Exception as exc:
        pytest.skip(f"ResectionPlanningWidget not importable ({exc!r}) -- ADR-0027.")
    try:
        widget = ResectionPlanningWidget()
    except Exception as exc:
        pytest.skip(f"widget not constructible ({exc!r}) -- ADR-0027.")
    widget.setMRMLScene(slicer.mrmlScene)
    return widget


def _plan_or_skip(slicer):
    module = getattr(slicer.modules, "liverresections", None)
    if module is None:
        pytest.skip("liverresections module not registered (ADR-0027).")
    plan = module.logic().CreateResectionPlan("ExplainableStateTest")
    if plan is None:
        pytest.skip("CreateResectionPlan returned None (ADR-0027).")
    return plan


def _tagged_distance_map(slicer):
    """A vector volume carrying the tags the auto-attach scan reads."""
    import numpy as np

    node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLVectorVolumeNode", "DistanceMap")
    array = np.zeros((4, 4, 4, 3), dtype="float32")
    slicer.util.updateVolumeFromArray(node, array)
    node.SetAttribute("DistanceMap", "True")
    node.SetAttribute("Computed", "True")
    return node


def test_a_plan_minted_before_the_map_picks_it_up_later():
    """#624: the attach must not be mint-time-only."""
    slicer = _slicer_or_skip()
    widget = _widget_or_skip(slicer)

    # No tagged map in the scene yet, so the plan mints without one.
    plan = _plan_or_skip(slicer)
    if plan.GetDistanceMapVolumeNode() is not None:
        pytest.skip("a tagged map already existed; this case needs a bare scene.")

    _tagged_distance_map(slicer)
    widget._attachExistingDistanceMap(plan)

    assert plan.GetDistanceMapVolumeNode() is not None, (
        "a map computed after the plan was placed must attach on refresh; "
        "otherwise the only recovery is delete-and-replace."
    )


def test_an_untagged_volume_is_not_attached():
    """The predicate must match CreateResectionPlan's exactly."""
    slicer = _slicer_or_skip()
    widget = _widget_or_skip(slicer)
    plan = _plan_or_skip(slicer)

    import numpy as np

    node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLVectorVolumeNode", "NotAMap")
    slicer.util.updateVolumeFromArray(node, np.zeros((4, 4, 4, 3), dtype="float32"))
    node.SetAttribute("DistanceMap", "True")  # tagged, but NOT Computed

    before = plan.GetDistanceMapVolumeNode()
    widget._attachExistingDistanceMap(plan)
    assert plan.GetDistanceMapVolumeNode() is before, (
        "a half-tagged volume must be ignored -- the two attach paths have "
        "to agree or a plan's input depends on when it was created."
    )


def test_the_init_predicate_reports_init_and_tolerates_a_stateless_carrier():
    """#623: the hint's gate, including its defensive fallback."""
    slicer = _slicer_or_skip()
    import importlib

    try:
        module = importlib.import_module(
            "LiverResectionsLib.ResectionPlanningWidget"
        )
    except Exception as exc:
        pytest.skip(f"module not importable ({exc!r}) -- ADR-0027.")

    plan = _plan_or_skip(slicer)
    carrier = plan.GetGeometryNode()
    assert module._safe_is_init(carrier) is True, "a fresh plan starts in Init"

    from LiverResectionsLib.ResectionStateMachine import STATE_PLANNING

    carrier.SetState(STATE_PLANNING)
    assert module._safe_is_init(carrier) is False

    # A carrier without the state API must report NOT-Init, so the
    # resectogram behaves as before rather than hiding on an unreadable
    # state.
    assert module._safe_is_init(object()) is False
    assert module._safe_is_init(None) is False

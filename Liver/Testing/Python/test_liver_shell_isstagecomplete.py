# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""``IsStageComplete()`` contract + semantics for the Liver-shell stages.

This file pins T2 (symbol existence) and T3 (scene-level semantics) of
the T5.2-d planner output.

Per the planner's "State source" decision, the per-stage predicate is
**hybrid**: each module's logic owns the query (since the data model
lives in the module) while the Liver shell observes scene events via
``VTKObservationMixin`` to know when to re-query.  This file pins the
*query-side* contract; the observe-side wiring is exercised by T6 in
``test_liver_shell_sidebar.py``.

Predicate surface per stage:

  Stage 1 (Case Setup)         — ``LiverWidget._stage1IsComplete()``
                                 (shell-owned; ADR-0023 §"Stage 1")
  Stage 2 (Anatomy Definition) — Stage 2 stub strategy: degrade
                                 gracefully when LiverSegmentation
                                 module is absent — predicate must
                                 return ``False`` and not crash.
  Stage 3 (Vascular Territories) — ``vtkSlicerVascularTerritoriesLogic
                                 ::IsStageComplete()``
  Stage 4 (Resection Planning)   — ``vtkSlicerLiverResectionsLogic
                                 ::IsStageComplete()``
  Stage 5 (Volumetry)            — ``LiverVolumetryLogic.isStageComplete()``
                                 (soft-True in v2.0; planner §"Stage 5")
  Stage 6 (Export)               — ``LiverWidget._stage6IsComplete()``
                                 (shell-owned; "last write OK" semantics)

T2 is satisfied by the symbol-existence stubs the test-designer lands
alongside this file (returning ``False``); T3 still red-fails until
``liver-implementer`` writes the predicate bodies.

See also:
  * Docs/adr/0023-unified-gui-stage-workflow.md §"Conformance"
  * Docs/architecture/gui-stage-flow.md §"Per-stage state-indicator semantics"
"""

from __future__ import annotations

import pytest


# --------------------------------------------------------------------------- #
# File-local helpers
# --------------------------------------------------------------------------- #

def _import_slicer_or_skip():
    """Return ``slicer`` or skip the test cleanly."""
    try:
        import slicer  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        pytest.skip(
            f"slicer module not importable ({exc}); "
            "IsStageComplete tests require Slicer's Python."
        )
    return slicer


def _clear_scene():
    """Empty the MRML scene; minimal-scene fixture for per-test isolation."""
    slicer = _import_slicer_or_skip()
    slicer.mrmlScene.Clear(0)


def _resections_logic():
    """Resolve the C++ ``vtkSlicerLiverResectionsLogic`` instance."""
    slicer = _import_slicer_or_skip()
    try:
        return slicer.modules.liverresections.logic()
    except AttributeError as exc:
        pytest.skip(
            f"LiverResections module not available ({exc}); "
            "ensure --additional-module-paths includes LiverResections."
        )


def _territories_logic():
    """Resolve the C++ ``vtkSlicerVascularTerritoriesLogic`` instance."""
    slicer = _import_slicer_or_skip()
    try:
        return slicer.modules.vascularterritories.logic()
    except AttributeError as exc:
        pytest.skip(
            f"VascularTerritories module not available ({exc}); "
            "ensure --additional-module-paths includes VascularTerritories."
        )


def _volumetry_logic():
    """Build a ``LiverVolumetryLogic`` Python instance.

    Skips cleanly outside Slicer (where the bare ``LiverVolumetry``
    module name may resolve to an unrelated site-packages install).
    """
    _import_slicer_or_skip()
    try:
        import LiverVolumetry  # type: ignore[import-not-found]
    except ImportError as exc:
        pytest.skip(
            f"LiverVolumetry not importable ({exc}); "
            "ensure --additional-module-paths includes LiverVolumetry."
        )
    if not hasattr(LiverVolumetry, "LiverVolumetryLogic"):
        pytest.skip(
            "Imported LiverVolumetry lacks LiverVolumetryLogic; the "
            "Slicer scripted module is not on the additional-module-paths."
        )
    return LiverVolumetry.LiverVolumetryLogic()


def _liver_widget():
    """Instantiate a fresh ``LiverWidget`` rooted on a throwaway parent."""
    _import_slicer_or_skip()
    try:
        import qt  # type: ignore[import-not-found]
        import Liver  # type: ignore[import-not-found]
    except ImportError as exc:
        pytest.skip(
            f"Liver scripted module not importable ({exc}); "
            "ensure --additional-module-paths includes Liver/."
        )
    parent = qt.QWidget()
    widget = Liver.LiverWidget(parent)
    widget.setup()
    return widget


# =========================================================================== #
# T2 — Symbol existence per stage
# =========================================================================== #
#
# Per planner output, T2 confirms each per-stage predicate is reachable
# and returns a ``bool``.  Semantics live in T3.  Stubs landed by the
# test-designer alongside this file satisfy T2; the implementer fills in
# the per-stage logic to flip T3 green.


def test_t2_stage1_predicate_exists_on_shell():
    """Stage 1 predicate ``LiverWidget._stage1IsComplete()`` must exist.

    Pins planner output §"IsStageComplete() contract per stage" — Stage
    1 + Stage 6 are Liver-shell-owned.

    Red-fails on ``60c78df``: ``LiverWidget`` has no
    ``_stage1IsComplete`` member.
    """
    widget = _liver_widget()
    assert callable(getattr(widget, "_stage1IsComplete", None)), (
        "LiverWidget._stage1IsComplete() not found."
    )
    result = widget._stage1IsComplete()
    assert isinstance(result, bool), (
        f"_stage1IsComplete() must return bool; got {type(result).__name__}."
    )


def test_t2_stage2_predicate_degrades_gracefully():
    """Stage 2 stub must return ``False`` when LiverSegmentation absent.

    Pins planner output §"Stage 2 stub strategy" (locked decision):
    degrade gracefully when the ``LiverSegmentation`` module is not
    registered.  The shell must not crash; the sidebar entry stays
    disabled-greyed; the predicate returns ``False``.

    Red-fails on ``60c78df``: ``LiverWidget`` has no
    ``_stage2IsComplete`` member.
    """
    widget = _liver_widget()
    assert callable(getattr(widget, "_stage2IsComplete", None)), (
        "LiverWidget._stage2IsComplete() not found."
    )
    # In the v2.0 sidebar, LiverSegmentation module is absent (#409 is
    # a v2.1 deliverable).  Predicate must still resolve cleanly.
    result = widget._stage2IsComplete()
    assert result is False, (
        "Stage 2 predicate must return False while LiverSegmentation "
        "module is absent; the sidebar entry should be disabled-greyed."
    )


def test_t2_stage3_predicate_exists_on_territories_logic():
    """``vtkSlicerVascularTerritoriesLogic::IsStageComplete()`` must exist.

    Pins planner output §"IsStageComplete() contract per stage" —
    Stage 3 lives on the C++ territories logic.  Symbol existence is
    satisfied by the test-designer's stub; semantics in T3.

    Red-fails on ``60c78df``: the method has not been declared on the
    logic header.
    """
    logic = _territories_logic()
    assert hasattr(logic, "IsStageComplete"), (
        "vtkSlicerVascularTerritoriesLogic::IsStageComplete() not bound."
    )
    result = logic.IsStageComplete()
    assert isinstance(result, bool), (
        "IsStageComplete() must return bool (Python-mapped from C++ bool)."
    )


def test_t2_stage4_predicate_exists_on_resections_logic():
    """``vtkSlicerLiverResectionsLogic::IsStageComplete()`` must exist.

    Pins planner output §"IsStageComplete() contract per stage" —
    Stage 4 lives on the C++ resections logic.

    Red-fails on ``60c78df``: the method has not been declared on the
    logic header.
    """
    logic = _resections_logic()
    assert hasattr(logic, "IsStageComplete"), (
        "vtkSlicerLiverResectionsLogic::IsStageComplete() not bound."
    )
    result = logic.IsStageComplete()
    assert isinstance(result, bool)


def test_t2_stage5_predicate_exists_on_volumetry_logic():
    """``LiverVolumetryLogic.isStageComplete()`` must exist.

    Pins planner output §"IsStageComplete() contract per stage" —
    Stage 5 lives on the Python volumetry logic.  Note the
    lower-camelCase (Python convention) vs Stage 3/4's UpperCamelCase
    (VTK convention).

    Red-fails on ``60c78df``: ``LiverVolumetryLogic`` has no
    ``isStageComplete`` method.
    """
    logic = _volumetry_logic()
    assert callable(getattr(logic, "isStageComplete", None))
    result = logic.isStageComplete()
    assert isinstance(result, bool)


def test_t2_stage6_predicate_exists_on_shell():
    """Stage 6 predicate ``LiverWidget._stage6IsComplete()`` must exist.

    Pins planner output §"IsStageComplete() contract per stage" —
    Stage 6 (Export) is Liver-shell-owned; semantics is "last write
    OK" needing a scene-level attribute the shell tracks.

    Red-fails on ``60c78df``: ``LiverWidget`` has no
    ``_stage6IsComplete`` member.
    """
    widget = _liver_widget()
    assert callable(getattr(widget, "_stage6IsComplete", None))
    result = widget._stage6IsComplete()
    assert isinstance(result, bool)


# =========================================================================== #
# T3 — Scene-level semantics per stage (the v2.0-functional stages)
# =========================================================================== #
#
# Per planner output, T3 covers stages 1, 3, 4.  Stage 2 stays stubbed-
# False (covered by T2's graceful-degradation test).  Stage 5 is
# soft-True in v2.0 (no functional gating signal yet).  Stage 6 is
# "last write OK" (needs a scene-level attribute the shell tracks; the
# shell test exercises the read path once the attribute exists).


def test_t3_stage1_semantics_empty_scene_returns_false():
    """Stage 1 predicate must return False on an empty scene.

    Pins ADR-0023 §"Decision" item 1: Stage 1 is "Case Setup — load
    DICOM and non-DICOM volumes; assign per-volume role tags".  Until
    a volume carrying ``LiverRole`` exists, Case Setup is not done.

    Red-fails on ``60c78df``: predicate does not exist.
    """
    _clear_scene()
    widget = _liver_widget()
    assert widget._stage1IsComplete() is False


def test_t3_stage1_semantics_tagged_volume_returns_true():
    """Stage 1 predicate must return True when a volume carries LiverRole.

    Pins planner output §"IsStageComplete() semantics" — Stage 1:
    "Scene with one volume carrying ``LiverRole`` attribute → True."

    Red-fails on ``60c78df``: predicate does not exist.
    """
    slicer = _import_slicer_or_skip()
    _clear_scene()
    widget = _liver_widget()

    volume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode")
    # ``LiverRole`` is the per-volume role tag from ADR-0023 §"Decision"
    # item 1 ("assign per-volume role tags").  Convention pending
    # implementer; the test pins only the attribute presence.
    volume.SetAttribute("LiverRole", "PortalVenous")

    assert widget._stage1IsComplete() is True


def test_t3_stage3_semantics_empty_scene_returns_false():
    """Stage 3 predicate must return False with no territory nodes.

    Pins planner output §"IsStageComplete() semantics" — Stage 3:
    "Scene with no territories → False".

    Red-fails on ``60c78df``: predicate does not exist.
    """
    _clear_scene()
    logic = _territories_logic()
    assert logic.IsStageComplete() is False


def test_t3_stage3_semantics_one_stdcouinaud_returns_true():
    """Stage 3 predicate must return True with one StdCouinaud node.

    Pins planner output §"IsStageComplete() semantics" — Stage 3:
    "Scene with one ``vtkMRMLStdCouinaudTerritoriesNode`` → True."

    Red-fails on ``60c78df``: predicate does not exist.
    """
    slicer = _import_slicer_or_skip()
    _clear_scene()
    logic = _territories_logic()

    slicer.mrmlScene.AddNewNodeByClass("vtkMRMLStdCouinaudTerritoriesNode")
    assert logic.IsStageComplete() is True


def test_t3_stage4_semantics_empty_scene_returns_false():
    """Stage 4 predicate must return False with no resection plans.

    Pins planner output §"IsStageComplete() semantics" — Stage 4:
    "Scene with no plans → False".  Data source per
    Docs/architecture/gui-stage-flow.md §"Module ownership per stage":
    ``GetNodesByClass('vtkMRMLResectionPlanNode')``.

    Red-fails on ``60c78df``: predicate does not exist.
    """
    _clear_scene()
    logic = _resections_logic()
    assert logic.IsStageComplete() is False


def test_t3_stage4_semantics_init_state_returns_false():
    """Stage 4: plan in State == Init keeps stage 'current', not 'done'.

    Pins planner output §"IsStageComplete() semantics" — Stage 4:
    "Scene with ``vtkMRMLResectionPlanNode`` in ``State == Init`` →
    False (lesser state keeps 'current', not 'done')".  State machine
    per ADR-0019 (Init → Planning → Confirmed).

    Red-fails on ``60c78df``: predicate does not exist.
    """
    slicer = _import_slicer_or_skip()
    _clear_scene()
    logic = _resections_logic()

    plan = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLResectionPlanNode")
    # State enum: Init=0, Planning=1, Confirmed=2.  Default is Init.
    plan.SetState(0)
    assert logic.IsStageComplete() is False


def test_t3_stage4_semantics_confirmed_state_returns_true():
    """Stage 4: plan in State == Confirmed flips stage to 'done'.

    Pins planner output §"IsStageComplete() semantics" — Stage 4:
    "Scene with ``vtkMRMLResectionPlanNode`` in ``State == Confirmed``
    → True".

    Red-fails on ``60c78df``: predicate does not exist.
    """
    slicer = _import_slicer_or_skip()
    _clear_scene()
    logic = _resections_logic()

    plan = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLResectionPlanNode")
    plan.SetState(2)  # Confirmed
    assert logic.IsStageComplete() is True

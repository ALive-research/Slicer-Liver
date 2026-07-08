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
# File-local helpers — the launched-Slicer skip-guards are the shared ones
# re-exported by the sibling conftest (canonical bodies in
# Testing/Python/slicer_pytest_support.py).
# --------------------------------------------------------------------------- #

# Re-export under the names this file's call sites already use.
from conftest import (  # type: ignore[import-not-found]  # noqa: E402
    _import_slicer_or_skip,
    _require_mrml_scene as _require_mrml_scene_or_skip,
)


def _clear_scene():
    """Empty the MRML scene; minimal-scene fixture for per-test isolation."""
    _require_mrml_scene_or_skip()
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
    from conftest import _require_qt_widget  # type: ignore[import-not-found]
    _require_qt_widget()

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


def _liver_widget_no_setup():
    """A ``LiverWidget`` WITHOUT ``setup()`` — for tests that only exercise the
    completion predicates.

    ``_stageIsComplete`` reads scene + module state and needs no sidebar/layout,
    so skipping ``setup()`` keeps these tests verifiable headless
    (``--no-main-window``), where ``setup()``'s ``self.layout`` is ``None``.
    """
    from conftest import _require_qt_widget  # type: ignore[import-not-found]
    _require_qt_widget()

    _import_slicer_or_skip()
    try:
        import qt  # type: ignore[import-not-found]
        import Liver  # type: ignore[import-not-found]
    except ImportError as exc:
        pytest.skip(f"Liver scripted module not importable ({exc}).")
    return Liver.LiverWidget(qt.QWidget())


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
    # In the v2.0 sidebar, LiverSegmentation module is absent (the
    # LiverSegmentation work is a v2.1 deliverable).  Predicate must
    # still resolve cleanly.
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
    widget = _liver_widget_no_setup()  # predicate needs no sidebar/layout
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


# =========================================================================== #
# Stage-2 completion ROUTING — the shell delegates row 1 to the module logic
# =========================================================================== #
#
# Contract: ``_stageIsComplete(1)`` must route to the LiverSegmentation module
# logic's ``isStageComplete()`` (true iff a canonical segmentation holds >=1
# SCT-tagged segment), NOT to the always-False ``_stage2IsComplete`` shell
# stub.  The stub survives only as the graceful-degradation answer when the
# module is ABSENT (pinned by ``test_t2_stage2_predicate_degrades_gracefully``
# above, which exercises ``_stage2IsComplete`` directly).
#
# ``_STAGE_MODULE[1] == "liversegmentation"`` already maps row 1 to the module;
# the fix removes the ``1:`` entry from ``_stageIsComplete``'s ``shellPredicate``
# dict so row 1 falls through to the module-logic path.  These tests therefore
# need the ``liversegmentation`` module registered (launched Slicer); they skip
# cleanly bare and when the module is absent.
#
# ADR-0023 §"Per-stage state-indicator semantics" (Stage 2 soft-done);
# ADR-0024 §"Output contract" (single canonical node); test-first per ADR-0027.


def _liversegmentation_logic_or_skip():
    """Resolve the Python ``LiverSegmentationLogic``, or skip.

    Mirrors the sibling module suite's ``_logic_or_skip`` resolution: the
    module must be registered (so the shell's module-logic path can find it)
    AND the Python module importable (so we can drive its own accept/tag seams
    to make ``isStageComplete()`` true).
    """
    slicer = _import_slicer_or_skip()
    module = getattr(slicer.modules, "liversegmentation", None)
    if module is None:
        pytest.skip(
            "'liversegmentation' module not registered -- Stage-2 completion "
            "routes to the shell degrade-gracefully stub; the module-logic "
            "route cannot be exercised.  Ensure --additional-module-paths "
            "includes LiverSegmentation/."
        )
    try:
        import LiverSegmentation  # type: ignore[import-not-found]
    except ImportError as exc:
        pytest.skip(
            f"LiverSegmentation not importable ({exc}); "
            "ensure --additional-module-paths includes LiverSegmentation/."
        )
    return slicer, LiverSegmentation.LiverSegmentationLogic()


def _make_stage2_complete(logic):
    """Land one canonical, SCT-tagged segment so ``isStageComplete()`` is True.

    Uses the orchestrator's own accept/tag seams
    (``getOrCreateCanonicalSegmentation`` + ``tagSegmentWithSct``) rather than a
    hand-built node, so the routing test agrees with the module on what
    "SCT-tagged canonical segment" means — the same construction the module's
    own ``isStageComplete()`` semantics suite uses.
    """
    canonical = logic.getOrCreateCanonicalSegmentation()
    segId = canonical.GetSegmentation().AddEmptySegment("liver", "Liver")
    # Liver parenchyma SNOMED-CT code per ADR-0024 §"Output contract".
    logic.tagSegmentWithSct(canonical, segId, "10200004", "Liver")


def test_stage2_routing_delegates_to_module_logic_when_complete():
    """``_stageIsComplete(1)`` is True when the module logic reports done.

    Pins the Stage-2 routing invariant: with a canonical SCT-tagged
    segmentation in the scene, the shell must return True for row 1 — proving
    it delegated to ``LiverSegmentationLogic.isStageComplete()`` and did NOT
    short-circuit on the always-False ``_stage2IsComplete`` stub.

    RED-as-skip until the fix lands: the current ``shellPredicate`` dict routes
    row 1 to the stub, so this asserts False and fails once reached.  Skips
    cleanly while the module is absent (the degrade-gracefully path).

    ADR-0023 §"Per-stage state-indicator semantics"; ADR-0024 §"Output contract".
    """
    slicer, logic = _liversegmentation_logic_or_skip()
    _clear_scene()
    _make_stage2_complete(logic)

    widget = _liver_widget_no_setup()
    try:
        assert widget._stageIsComplete(1) is True, (
            "_stageIsComplete(1) must delegate to the LiverSegmentation module "
            "logic (True with a canonical SCT-tagged segment), not the "
            "always-False _stage2IsComplete stub."
        )
    finally:
        slicer.mrmlScene.Clear(0)


def test_stage2_routing_false_without_canonical_segment():
    """``_stageIsComplete(1)`` is False with no canonical SCT-tagged segment.

    The module-logic route must still report False on an empty scene (the same
    answer the stub gave), so removing the stub entry does not spuriously flip
    Stage 2 to done.

    ADR-0023 §"Per-stage state-indicator semantics" (soft-done is canonical-only).
    """
    slicer, logic = _liversegmentation_logic_or_skip()  # noqa: F841 — registration gate
    _clear_scene()

    widget = _liver_widget_no_setup()
    assert widget._stageIsComplete(1) is False, (
        "_stageIsComplete(1) must be False with no canonical SCT-tagged "
        "segment (empty scene), whether via the stub or the module-logic route."
    )


def test_stage2_routing_does_not_regress_shell_rows():
    """Rows 0/5 stay shell-owned; the injection override still wins.

    Regression guard for the routing fix: removing the row-1 ``shellPredicate``
    entry must not disturb the shell-owned rows (0 -> ``_stage1IsComplete``,
    5 -> ``_stage6IsComplete``) nor the ``_injectedStageCompletion`` test
    override (``_injectStageCompletionForTesting``), which short-circuits ALL
    rows before any predicate dispatch.

    ADR-0023 §"Shell composition (Option H)"; injection override pinned by
    ``test_state_indicators_reflect_isstagecomplete``.
    """
    slicer = _import_slicer_or_skip()  # noqa: F841 — scene/widget gate
    _clear_scene()
    widget = _liver_widget_no_setup()

    # Shell-owned rows: empty scene -> both False (Stage 1 has no LiverRole
    # volume; Stage 6 has no logged write).  Unaffected by the row-1 change.
    assert widget._stageIsComplete(0) is False
    assert widget._stageIsComplete(5) is False

    # The injection override must still short-circuit every row, including the
    # now-module-routed row 1.
    widget._injectStageCompletionForTesting([True, True, True, True, True, True])
    try:
        for row in range(6):
            assert widget._stageIsComplete(row) is True, (
                f"_injectedStageCompletion must override row {row} regardless "
                "of the per-row routing."
            )
    finally:
        widget._injectStageCompletionForTesting(None)


# =========================================================================== #
# Stage-6 Export — writing a plan flips the completion predicate
# =========================================================================== #
#
# Contract (ADR-0023 §Stage 6): the shell-owned Export writes the resection
# plan (.lrp.json via vtkMRMLResectionPlanStorageNode) and, on success, records
# "last write OK" on the LiverShellState node so _stage6IsComplete flips true.
# The testable seam is the shell's export core (_exportResectionPlan /
# _recordStage6Write); the file dialog + Save button are :0-only.  Tests
# skip-pending until the seam lands (ADR-0027).


def _resection_plan_or_skip():
    """Mint a resection plan via the C++ create-API, or skip."""
    logic = _resections_logic()
    if not hasattr(logic, "CreateResectionPlan"):
        pytest.skip("vtkSlicerLiverResectionsLogic has no CreateResectionPlan.")
    plan = logic.CreateResectionPlan("ExportTest")
    if plan is None:
        pytest.skip("CreateResectionPlan returned None.")
    return plan


def test_stage6_export_writes_plan_and_marks_complete(tmp_path):
    """_exportResectionPlan writes the .lrp.json and flips Stage 6 complete."""
    _clear_scene()
    widget = _liver_widget_no_setup()
    if not hasattr(widget, "_exportResectionPlan"):
        pytest.skip("LiverWidget._exportResectionPlan not present -- Stage-6 "
                    "export seam has not landed (ADR-0027).")
    plan = _resection_plan_or_skip()
    path = str(tmp_path / "plan.lrp.json")

    assert widget._stage6IsComplete() is False
    result = widget._exportResectionPlan(plan, path)
    assert result is True, (
        f"_exportResectionPlan must return True on a successful write; got {result!r}."
    )
    import os
    assert os.path.exists(path), (
        f"_exportResectionPlan must write the .lrp.json to {path}."
    )
    assert widget._stage6IsComplete() is True, (
        "a successful export must record Stage6.LastWriteOK so _stage6IsComplete "
        "flips true (ADR-0023 §Stage 6)."
    )


def test_stage6_record_write_flips_predicate():
    """_recordStage6Write(True/False) drives _stage6IsComplete."""
    _clear_scene()
    widget = _liver_widget_no_setup()
    if not hasattr(widget, "_recordStage6Write"):
        pytest.skip("LiverWidget._recordStage6Write not present (ADR-0027).")

    widget._recordStage6Write(True)
    assert widget._stage6IsComplete() is True
    widget._recordStage6Write(False)
    assert widget._stage6IsComplete() is False


def test_stage6_export_none_plan_is_noop(tmp_path):
    """Exporting no plan is a no-op returning False; Stage 6 stays incomplete."""
    _clear_scene()
    widget = _liver_widget_no_setup()
    if not hasattr(widget, "_exportResectionPlan"):
        pytest.skip("LiverWidget._exportResectionPlan not present (ADR-0027).")
    result = widget._exportResectionPlan(None, str(tmp_path / "none.lrp.json"))
    assert result is False, (
        "_exportResectionPlan(None, ...) must be a no-op returning False."
    )
    assert widget._stage6IsComplete() is False, (
        "a failed/degenerate export must not mark Stage 6 complete."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

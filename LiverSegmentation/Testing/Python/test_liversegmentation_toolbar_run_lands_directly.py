# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""The selection-scoped toolbar Run lands its result directly on the canonical.

ADR-0034 §Amendments: the per-structure cards and the Accept/Reject machinery
are retired.  The Stage-2 gesture surface is a selection-scoped toolbar over
the anatomy segments table; Run resolves the SELECTED row's structure, drives
the backend, and lands the result on the canonical node IMMEDIATELY (the
internal ``accept()`` step) as native ``InProgress`` with the per-segment
source tag — the surgeon's review boundary is the native status cell, not a
node-level Accept.  No scratch node survives the gesture.

Pins:

  * ``segment()`` (logic level) still produces exactly one internal scratch
    node and never touches the canonical itself — the landing is the
    widget's tail step, not a backend side-effect.
  * toolbar Run with the liver row selected -> no surviving scratch node;
    the liver row's canonical segment reads native ``InProgress`` and
    carries the source tag; the placeholder is replaced, not duplicated.
  * Run with no row selected is a no-op with a status-label hint.
  * Run without a Stage-1 PortalVenous volume is refused with the Stage-1
    hint (the ADR-0024 Stage-1/Stage-2 hand-off pin, wording preserved).
  * a FAILED run leaves the canonical untouched and no scratch behind
    (the invariant the retired Reject suite carried).
  * the busy state (progress bar + status + wait cursor) is painted BEFORE
    the blocking backend call, and the landing re-frames the 3D views.

Scene/widget-needing: launched-Slicer harness
(``Liver/Testing/Python/run_pytest_launched.py`` / ``pytest_launched``);
skips cleanly under bare pytest via the shared guards.
"""

from __future__ import annotations

import pytest

MODULE_NAME = "liversegmentation"
ROLE_ATTRIBUTE = "LiverSegmentation.Role"
ROLE_SCRATCH = "scratch"
ROLE_CANONICAL = "canonical"

# SCT type code per ADR-0024 §"Output contract" (confirmed against the
# Resources/Terminology/LabelToSCT/ bridges).  Named so the SCT contract is
# grep-able.
SCT_LIVER_CODE = "10200004"

#: The Stage-1 hand-off hint (pinned verbatim -- ADR-0024 Stage-1/Stage-2
#: hand-off is an explicit precondition, not a silent no-op).
STAGE1_HINT = "Tag a PortalVenous volume in Case Setup (Stage 1) first."


def _orchestrator_or_skip():
    from conftest import _import_slicer_or_skip, _require_mrml_scene

    _require_mrml_scene()
    slicer = _import_slicer_or_skip()
    module = getattr(slicer.modules, MODULE_NAME, None)
    if module is None:
        pytest.skip(
            f"'{MODULE_NAME}' module not registered -- ADR-0024 Stage-2 "
            "surgeon-UI deliverable absent; the Run flow cannot be exercised."
        )
    try:
        import LiverSegmentation  # type: ignore[import-not-found]
    except ImportError as exc:
        pytest.skip(
            f"LiverSegmentation not importable ({exc}); "
            "ensure --additional-module-paths includes LiverSegmentation/."
        )
    return slicer, LiverSegmentation.LiverSegmentationLogic()


def _widget_or_skip(slicer, registry):
    from conftest import _require_qt_widget

    _require_qt_widget()
    try:
        import LiverSegmentation  # type: ignore[import-not-found]
    except ImportError as exc:
        pytest.skip(f"LiverSegmentation not importable ({exc}).")
    widget = LiverSegmentation.LiverSegmentationWidget()
    widget.setup()
    registry.append(widget)
    return widget


def _segmentation_nodes(slicer, role):
    nodes = slicer.util.getNodesByClass("vtkMRMLSegmentationNode")
    return [n for n in nodes if n.GetAttribute(ROLE_ATTRIBUTE) == role]


def _add_input_volume(slicer):
    """Add a Stage-1 PortalVenous-role scalar volume for the orchestrator input.

    Carries real (tiny) image data: the landing tail (``accept()`` ->
    ``ensureDistanceMap``) exports segments against this reference volume,
    and a data-less volume is not a shape Stage 1 can hand off.
    """
    import numpy as np

    volume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode")
    slicer.util.updateVolumeFromArray(volume, np.zeros((8, 8, 8), dtype="int16"))
    volume.SetAttribute("LiverRole", "PortalVenous")
    return volume


def _sct_segment_id(module, canonical, code):
    """The single segment id on ``canonical`` terminology-tagged ``code``."""
    import vtk

    segmentation = canonical.GetSegmentation()
    ids = []
    for segment_id in list(segmentation.GetSegmentIDs()):
        text = vtk.mutable("")
        segmentation.GetSegment(segment_id).GetTag(
            module.TERMINOLOGY_ENTRY_TAG, text
        )
        if f"^{code}^" in str(text):
            ids.append(segment_id)
    assert len(ids) == 1, (
        f"expected exactly one segment tagged ^{code}^; got {ids!r} -- the "
        "landing contract must replace the placeholder, never duplicate it."
    )
    return ids[0]


def _select_structure_row(module, widget, code):
    """Select the ``code`` row in the widget's segments table."""
    table = widget.segmentsTable()
    canonical = table.segmentationNode()
    assert canonical is not None, "setup must have bound the canonical node."
    table.setSelectedSegmentIDs([_sct_segment_id(module, canonical, code)])


def _mock_backend_seam(monkeypatch, logic, record=None):
    """Monkeypatch the backend seam to mint a synthetic SCT-tagged scratch.

    A real TotalSegmentator run is impossible in CI; the invariants under
    test are the toolbar/orchestrator bookkeeping, not inference accuracy.
    ``_runTotalSegmentator`` is the single monkeypatchable seam
    ``segment()`` funnels through (ADR-0024 §"Lazy install").
    """

    def _fake(volume, sctTarget, progressCallback=None):
        if record is not None:
            record.append((volume, str(sctTarget)))
        scratch = logic.createScratchSegmentation()
        seg_id = scratch.GetSegmentation().AddEmptySegment("synthetic", "Synthetic")
        logic.tagSegmentWithSct(scratch, seg_id, sctTarget, "Synthetic")
        return scratch

    monkeypatch.setattr(logic, "_runTotalSegmentator", _fake)


# =========================================================================== #
# Logic level — segment() itself stays scratch-producing and canonical-clean.
# =========================================================================== #


def test_logic_segment_produces_exactly_one_scratch_node(monkeypatch):
    """segment() mints one scratch node and never mints the canonical.

    The landing onto the canonical node is the WIDGET's explicit tail step
    (``accept()`` right after ``segment()`` returns, ADR-0034 §Amendments);
    the backend entry point itself must stay scratch-only so a failure
    mid-run can never half-touch the canonical.
    """
    slicer, orch = _orchestrator_or_skip()
    slicer.mrmlScene.Clear(0)

    volume = _add_input_volume(slicer)
    _mock_backend_seam(monkeypatch, orch)

    scratch = orch.segment(volume, SCT_LIVER_CODE)

    assert scratch is not None and scratch.IsA("vtkMRMLSegmentationNode"), (
        "segment() must return a vtkMRMLSegmentationNode scratch node."
    )
    assert scratch.GetAttribute(ROLE_ATTRIBUTE) == ROLE_SCRATCH, (
        "segment() output must carry role=scratch (ADR-0024 §Terminology)."
    )
    assert len(_segmentation_nodes(slicer, ROLE_SCRATCH)) == 1, (
        "exactly one scratch node must exist after a single segment() call."
    )
    assert len(_segmentation_nodes(slicer, ROLE_CANONICAL)) == 0, (
        "segment() must NOT create the canonical node -- the landing is the "
        "widget's explicit accept() step (ADR-0034 §Amendments)."
    )


# =========================================================================== #
# Toolbar level — select row -> Run -> lands directly.
# =========================================================================== #


def test_toolbar_run_with_selected_row_lands_directly(monkeypatch, qt_widgets):
    """Run with the liver row selected lands the result on the canonical.

    ADR-0034 §Amendments: no Accept button -- ``accept()`` runs immediately
    after ``segment()`` returns.  No scratch node survives; the liver row's
    canonical segment reads native ``InProgress`` ("produced, under
    review") and carries the source tag; the placeholder is replaced in
    place, never duplicated.
    """
    slicer, _orch = _orchestrator_or_skip()
    import LiverSegmentation as module

    slicer.mrmlScene.Clear(0)
    _add_input_volume(slicer)
    widget = _widget_or_skip(slicer, qt_widgets)
    _mock_backend_seam(monkeypatch, widget.logic)
    _select_structure_row(module, widget, SCT_LIVER_CODE)

    widget.onRunSelectedStructure()

    assert len(_segmentation_nodes(slicer, ROLE_SCRATCH)) == 0, (
        "no scratch node may survive the toolbar Run -- the result lands "
        "directly on the canonical node (ADR-0034 §Amendments)."
    )
    canonicals = _segmentation_nodes(slicer, ROLE_CANONICAL)
    assert len(canonicals) == 1, "exactly one canonical node after the landing."
    canonical = canonicals[0]
    assert canonical.GetSegmentation().GetNumberOfSegments() == len(
        module.STRUCTURE_TABS
    ), "the placeholder is replaced in place -- the checklist row count is stable."

    segments_logic = slicer.vtkSlicerSegmentationsModuleLogic
    liver = canonical.GetSegmentation().GetSegment(
        _sct_segment_id(module, canonical, SCT_LIVER_CODE)
    )
    assert segments_logic.GetSegmentStatus(liver) == segments_logic.InProgress, (
        "the landed liver row must read native InProgress -- 'produced, "
        "under review' (ADR-0034 §Amendments)."
    )
    import vtk

    source = vtk.mutable("")
    liver.GetTag(module.SOURCE_TAG, source)
    assert str(source) == module.SOURCE_TOTALSEG, (
        "the landing must stamp the per-segment source tag "
        f"({module.SOURCE_TOTALSEG!r}); got {str(source)!r}."
    )


def test_toolbar_run_without_selection_is_a_noop_with_hint(monkeypatch, qt_widgets):
    """Run with no row selected drives no backend and hints on the label."""
    slicer, _orch = _orchestrator_or_skip()

    slicer.mrmlScene.Clear(0)
    _add_input_volume(slicer)
    widget = _widget_or_skip(slicer, qt_widgets)
    calls: list = []
    _mock_backend_seam(monkeypatch, widget.logic, record=calls)
    widget.segmentsTable().setSelectedSegmentIDs([])

    widget.onRunSelectedStructure()

    assert calls == [], "Run without a selected row must not drive the backend."
    assert len(_segmentation_nodes(slicer, ROLE_SCRATCH)) == 0
    canonical = widget.segmentsTable().segmentationNode()
    segments_logic = slicer.vtkSlicerSegmentationsModuleLogic
    for segment_id in list(canonical.GetSegmentation().GetSegmentIDs()):
        segment = canonical.GetSegmentation().GetSegment(segment_id)
        assert (
            segments_logic.GetSegmentStatus(segment) == segments_logic.NotStarted
        ), "a selection-less Run must leave every checklist row untouched."
    status = widget._statusLabel.text
    assert status and status != "Idle", (
        "a selection-less Run must surface a hint on the shared status "
        f"label; got {status!r}."
    )


def test_toolbar_run_without_portalvenous_volume_is_refused_with_stage1_hint(
    monkeypatch, qt_widgets
):
    """Run with no PortalVenous volume is refused with the Stage-1 hint.

    ADR-0024 Stage-1/Stage-2 hand-off: Stage 2 works on the Stage-1
    PortalVenous volume.  With none tagged, ``selectInputVolume()`` is None;
    Run must NOT hand a None volume to ``segment()`` (no scratch node), and
    must surface the actionable hand-off hint -- wording preserved from the
    retired card flow.
    """
    slicer, _orch = _orchestrator_or_skip()
    import LiverSegmentation as module

    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer, qt_widgets)
    calls: list = []
    _mock_backend_seam(monkeypatch, widget.logic, record=calls)
    _select_structure_row(module, widget, SCT_LIVER_CODE)

    assert widget.logic.selectInputVolume() is None, (
        "precondition: no PortalVenous-role volume exists for this test."
    )

    widget.onRunSelectedStructure()

    assert calls == [], (
        "Run with no PortalVenous volume must NOT call the backend -- no "
        "scratch node may be minted from a None input (ADR-0024 Stage-1/"
        "Stage-2 hand-off precondition)."
    )
    assert len(_segmentation_nodes(slicer, ROLE_SCRATCH)) == 0
    assert widget._statusLabel.text == STAGE1_HINT, (
        "the refusal must surface the Stage-1 hand-off hint verbatim; got "
        f"{widget._statusLabel.text!r}."
    )
    assert widget._progressBar.visible is False, (
        "the progress bar must not be left visible when Run short-circuits."
    )


def test_failed_run_leaves_canonical_untouched(monkeypatch, qt_widgets):
    """A backend failure lands nothing: canonical unchanged, no scratch.

    The invariant the retired Reject suite carried (ADR-0034 §Amendments
    removes Reject; delete/re-run and ``Flagged`` cover its uses): a run
    that fails must leave the canonical node -- and its pre-seeded
    checklist -- exactly as they were, with no scratch debris.
    """
    slicer, _orch = _orchestrator_or_skip()
    import LiverSegmentation as module

    slicer.mrmlScene.Clear(0)
    _add_input_volume(slicer)
    widget = _widget_or_skip(slicer, qt_widgets)

    def _boom(volume, sctTarget, progressCallback=None):
        raise RuntimeError("backend exploded")

    monkeypatch.setattr(widget.logic, "_runTotalSegmentator", _boom)
    _select_structure_row(module, widget, SCT_LIVER_CODE)

    widget.onRunSelectedStructure()

    assert len(_segmentation_nodes(slicer, ROLE_SCRATCH)) == 0, (
        "a failed run must leave no scratch node behind."
    )
    canonicals = _segmentation_nodes(slicer, ROLE_CANONICAL)
    assert len(canonicals) == 1
    canonical = canonicals[0]
    assert canonical.GetSegmentation().GetNumberOfSegments() == len(
        module.STRUCTURE_TABS
    )
    segments_logic = slicer.vtkSlicerSegmentationsModuleLogic
    for segment_id in list(canonical.GetSegmentation().GetSegmentIDs()):
        segment = canonical.GetSegmentation().GetSegment(segment_id)
        assert (
            segments_logic.GetSegmentStatus(segment) == segments_logic.NotStarted
        ), "a failed run must leave every checklist row NotStarted."
    assert "failed" in widget._statusLabel.text.lower(), (
        "the failure must surface on the shared status label; got "
        f"{widget._statusLabel.text!r}."
    )


def test_toolbar_run_paints_busy_state_before_the_blocking_backend_call(
    monkeypatch, qt_widgets
):
    """The busy signal must be VISIBLE before segment() starts blocking.

    Pressing Run gave no processing signal: the busy bar + status were set
    but Qt never repainted before the minutes-long blocking backend call
    (the first repaint came only with the first backend output line, itself
    delayed by the subprocess's slow startup).  The Run handler must set the
    busy state AND flush the event loop BEFORE entering segment(); this pin
    reads the widget's state from INSIDE the (mocked) blocking call.
    """
    slicer, _orch = _orchestrator_or_skip()
    import LiverSegmentation as module

    slicer.mrmlScene.Clear(0)
    _add_input_volume(slicer)
    widget = _widget_or_skip(slicer, qt_widgets)
    _select_structure_row(module, widget, SCT_LIVER_CODE)

    seen = {}

    import qt

    def _blocking_segment(volume, sctTarget, progressCallback=None):
        seen["busy_visible"] = bool(widget._progressBar.visible)
        seen["status"] = str(widget._statusLabel.text)
        seen["wait_cursor"] = qt.QApplication.overrideCursor() is not None
        return None

    monkeypatch.setattr(widget.logic, "segment", _blocking_segment)
    widget.onRunSelectedStructure()

    assert seen.get("busy_visible"), (
        "the busy/progress bar must already be visible when the blocking "
        "backend call starts -- 'no signaling that there is processing'."
    )
    assert seen.get("status"), "a starting status message must already be shown"
    assert "idle" not in seen["status"].lower(), (
        f"the status must signal processing, not {seen['status']!r}."
    )
    assert seen.get("wait_cursor"), (
        "the wait cursor must be active during the blocking backend call "
        "(the v1 setOverrideCursor(WaitCursor) idiom)."
    )
    assert qt.QApplication.overrideCursor() is None, (
        "the wait cursor must be RESTORED after the Run handler returns -- "
        "a stuck spinner outlives the inference otherwise."
    )


def test_toolbar_run_reframes_the_threed_views(monkeypatch, qt_widgets):
    """Landing the first anatomy must re-centre the 3D views.

    The surface model generated on landing sits outside the default camera
    framing -- the surgeon saw an empty/off-centre 3D view until a manual
    re-centre.  The Run handler requests a 3D re-frame
    (``slicer.util.resetThreeDViews``) after the landing.
    """
    slicer, _orch = _orchestrator_or_skip()
    import LiverSegmentation as module

    slicer.mrmlScene.Clear(0)
    _add_input_volume(slicer)
    widget = _widget_or_skip(slicer, qt_widgets)
    _mock_backend_seam(monkeypatch, widget.logic)
    _select_structure_row(module, widget, SCT_LIVER_CODE)

    reframes = []
    monkeypatch.setattr(slicer.util, "resetThreeDViews", lambda: reframes.append(1))

    widget.onRunSelectedStructure()

    assert reframes, (
        "the Run handler must request a 3D-view re-frame after the landing "
        "-- the new anatomy is otherwise outside the camera framing."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

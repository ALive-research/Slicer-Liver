# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""The selection-scoped toolbar Run lands its result directly on the canonical.

ADR-0034 §Amendments: the per-structure cards and the Accept/Reject machinery
are retired.  The Stage-2 gesture surface is a selection-scoped toolbar over
the anatomy segments table; Run enqueues the SELECTED rows into the ADR-0034
§Decision 5 job queue (async — the blocking readline+processEvents path is
retired), and the queue's finish callback lands the result on the canonical
node (the internal ``accept()`` step) as native ``InProgress`` with the
per-segment source tag — the surgeon's review boundary is the native status
cell, not a node-level Accept.  No scratch node survives the gesture.

Pins:

  * ``segment()`` (logic level) still produces exactly one internal scratch
    node and never touches the canonical itself — the synchronous seam other
    consumers pin stays intact beside the queue.
  * toolbar Run with the liver row selected enqueues the structure and — on
    the driven finish callback — no scratch node survives; the liver row's
    canonical segment reads native ``InProgress`` and carries the source
    tag; the placeholder is replaced, not duplicated.  The finish callback
    is driven synchronously (the queue's own mechanics are pinned in
    ``test_liversegmentation_job_queue.py``).
  * Run with no row selected enqueues nothing, with a status-label hint.
  * Run without a Stage-1 PortalVenous volume is refused with the Stage-1
    hint (the ADR-0024 Stage-1/Stage-2 hand-off pin, wording preserved).
  * a FAILED job lands nothing and the targeted rows fall back to their
    pre-enqueue status (the invariant the retired Reject suite carried).
  * the busy surface (indeterminate bar + Cancel + status) shows from the
    enqueue and retires when the queue drains; no blocking loop, no wait
    cursor, the Run button stays live.
  * the landing re-frames the 3D views; the Run button re-labels with the
    table selection.

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

# SCT type codes per ADR-0024 §"Output contract" (confirmed against the
# Resources/Terminology/LabelToSCT/ bridges).  Named so the SCT contract is
# grep-able.
SCT_LIVER_CODE = "10200004"
SCT_PORTAL_VEIN_CODE = "32764006"

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


def _select_structure_rows(module, widget, codes):
    """Select the ``codes`` rows in the widget's segments table."""
    table = widget.segmentsTable()
    canonical = table.segmentationNode()
    assert canonical is not None, "setup must have bound the canonical node."
    table.setSelectedSegmentIDs(
        [_sct_segment_id(module, canonical, code) for code in codes]
    )


def _stub_queue(monkeypatch, widget, record=None):
    """Stub the widget's queue enqueue + backend gate for hermetic gestures.

    The queue's own mechanics (coalescing, sequencing, cancel, shutdown) are
    pinned in ``test_liversegmentation_job_queue.py`` with real stub
    children; here the enqueue is recorded and the finish callback driven
    SYNCHRONOUSLY so the widget contract is exercised without a child
    process or an event-loop wait.  ``_ensureBackend`` is stubbed True so no
    install probe/dialog runs in CI.
    """
    calls = record if record is not None else []

    def _fake_enqueue(task, inputVolumeID, structures):
        calls.append((str(task), str(inputVolumeID), sorted(structures)))
        from LiverSegmentationLib.SegmentationJobQueue import jobKey

        return jobKey(task, inputVolumeID)

    monkeypatch.setattr(widget._jobQueue, "enqueue", _fake_enqueue)
    monkeypatch.setattr(widget, "_ensureBackend", lambda: True)
    return calls


def _mock_import_seam(monkeypatch, widget, code=SCT_LIVER_CODE):
    """Monkeypatch ``importJobOutput`` to mint a synthetic SCT-tagged scratch.

    A real TotalSegmentator run is impossible in CI; the invariants under
    test are the widget/landing bookkeeping, not inference accuracy.
    ``importJobOutput`` is the queue path's single landing seam (the async
    sibling of the retired blocking path's ``_runTotalSegmentator`` seam).
    """

    def _fake(outputDir, structures):
        logic = widget.logic
        scratch = logic.createScratchSegmentation()
        seg_id = scratch.GetSegmentation().AddEmptySegment("synthetic", "Synthetic")
        logic.tagSegmentWithSct(scratch, seg_id, code, "Synthetic")
        return scratch

    monkeypatch.setattr(widget.logic, "importJobOutput", _fake)


def _drive_finish(widget, volume, codes, success, task="total"):
    """Drive the queue's finish callback synchronously for a recorded job."""
    from LiverSegmentationLib.SegmentationJobQueue import jobKey

    widget._onJobFinished(
        jobKey(task, volume.GetID()), set(codes), success, "/nonexistent-out"
    )


# =========================================================================== #
# Logic level — segment() itself stays scratch-producing and canonical-clean.
# =========================================================================== #


def test_logic_segment_produces_exactly_one_scratch_node(monkeypatch):
    """segment() mints one scratch node and never mints the canonical.

    The landing onto the canonical node is the WIDGET's explicit tail step
    (the queue's finish callback, ADR-0034 §Amendments); the backend entry
    point itself must stay scratch-only so a failure mid-run can never
    half-touch the canonical.
    """
    slicer, orch = _orchestrator_or_skip()
    slicer.mrmlScene.Clear(0)

    volume = _add_input_volume(slicer)

    def _fake(volume, sctTarget, progressCallback=None):
        scratch = orch.createScratchSegmentation()
        seg_id = scratch.GetSegmentation().AddEmptySegment("synthetic", "Synthetic")
        orch.tagSegmentWithSct(scratch, seg_id, sctTarget, "Synthetic")
        return scratch

    monkeypatch.setattr(orch, "_runTotalSegmentator", _fake)

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
        "widget's explicit landing step (ADR-0034 §Amendments)."
    )


# =========================================================================== #
# Toolbar level — select row -> Run -> enqueue -> the finish callback lands.
# =========================================================================== #


def test_toolbar_run_with_selected_row_lands_directly(monkeypatch, qt_widgets):
    """Run with the liver row selected enqueues it; the finish lands it.

    ADR-0034 §Amendments: no Accept button -- the queue's finish callback
    runs ``accept()``.  No scratch node survives; the liver row's canonical
    segment reads native ``InProgress`` ("produced, under review") and
    carries the source tag; the placeholder is replaced in place, never
    duplicated.
    """
    slicer, _orch = _orchestrator_or_skip()
    import LiverSegmentation as module

    slicer.mrmlScene.Clear(0)
    volume = _add_input_volume(slicer)
    widget = _widget_or_skip(slicer, qt_widgets)
    calls = _stub_queue(monkeypatch, widget)
    _mock_import_seam(monkeypatch, widget)
    _select_structure_rows(module, widget, [SCT_LIVER_CODE])

    widget.onRunSelectedStructures()

    assert calls == [("total", volume.GetID(), [SCT_LIVER_CODE])], (
        "Run with the liver row selected must enqueue exactly one job for "
        f"the liver's backend task; got {calls!r}."
    )

    _drive_finish(widget, volume, [SCT_LIVER_CODE], success=True)

    assert len(_segmentation_nodes(slicer, ROLE_SCRATCH)) == 0, (
        "no scratch node may survive the landing -- the result lands "
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
    assert "confirm" in widget._statusLabel.text.lower(), (
        "the landing hint must route the surgeon to the status-cell "
        f"confirm; got {widget._statusLabel.text!r}."
    )


def test_toolbar_run_without_selection_is_a_noop_with_hint(monkeypatch, qt_widgets):
    """Run with no row selected enqueues nothing and hints on the label."""
    slicer, _orch = _orchestrator_or_skip()

    slicer.mrmlScene.Clear(0)
    _add_input_volume(slicer)
    widget = _widget_or_skip(slicer, qt_widgets)
    calls = _stub_queue(monkeypatch, widget)
    widget.segmentsTable().setSelectedSegmentIDs([])

    widget.onRunSelectedStructures()

    assert calls == [], "Run without a selected row must not enqueue a job."
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
    Run must NOT enqueue a job (no status flip, no child), and must surface
    the actionable hand-off hint -- wording preserved from the retired card
    flow.
    """
    slicer, _orch = _orchestrator_or_skip()
    import LiverSegmentation as module

    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer, qt_widgets)
    calls = _stub_queue(monkeypatch, widget)
    _select_structure_rows(module, widget, [SCT_LIVER_CODE])

    assert widget.logic.selectInputVolume() is None, (
        "precondition: no PortalVenous-role volume exists for this test."
    )

    widget.onRunSelectedStructures()

    assert calls == [], (
        "Run with no PortalVenous volume must NOT enqueue -- no job may be "
        "minted from a None input (ADR-0024 Stage-1/Stage-2 hand-off "
        "precondition)."
    )
    assert len(_segmentation_nodes(slicer, ROLE_SCRATCH)) == 0
    assert widget._statusLabel.text == STAGE1_HINT, (
        "the refusal must surface the Stage-1 hand-off hint verbatim; got "
        f"{widget._statusLabel.text!r}."
    )
    assert widget._progressBar.visible is False, (
        "the progress bar must not be shown when Run short-circuits."
    )


def test_failed_job_leaves_canonical_untouched(monkeypatch, qt_widgets):
    """A failed job lands nothing: rows fall back, no scratch, no growth.

    The invariant the retired Reject suite carried (ADR-0034 §Amendments
    removes Reject; delete/re-run and ``Flagged`` cover its uses): a job
    that fails must leave the canonical node -- and its pre-seeded
    checklist -- exactly as they were.  The enqueue-time ``InProgress``
    flip is a promise of produced output, so the targeted row falls BACK
    to its pre-enqueue status when the job delivers nothing.
    """
    slicer, _orch = _orchestrator_or_skip()
    import LiverSegmentation as module

    slicer.mrmlScene.Clear(0)
    volume = _add_input_volume(slicer)
    widget = _widget_or_skip(slicer, qt_widgets)
    _stub_queue(monkeypatch, widget)
    _select_structure_rows(module, widget, [SCT_LIVER_CODE])

    widget.onRunSelectedStructures()

    segments_logic = slicer.vtkSlicerSegmentationsModuleLogic
    canonical = widget.segmentsTable().segmentationNode()
    liver = canonical.GetSegmentation().GetSegment(
        _sct_segment_id(module, canonical, SCT_LIVER_CODE)
    )
    assert segments_logic.GetSegmentStatus(liver) == segments_logic.InProgress, (
        "precondition: the enqueue flipped the targeted row to InProgress."
    )

    _drive_finish(widget, volume, [SCT_LIVER_CODE], success=False)

    assert len(_segmentation_nodes(slicer, ROLE_SCRATCH)) == 0, (
        "a failed job must leave no scratch node behind."
    )
    canonicals = _segmentation_nodes(slicer, ROLE_CANONICAL)
    assert len(canonicals) == 1
    assert canonical.GetSegmentation().GetNumberOfSegments() == len(
        module.STRUCTURE_TABS
    )
    for segment_id in list(canonical.GetSegmentation().GetSegmentIDs()):
        segment = canonical.GetSegmentation().GetSegment(segment_id)
        assert (
            segments_logic.GetSegmentStatus(segment) == segments_logic.NotStarted
        ), (
            "a failed job must leave every checklist row NotStarted -- the "
            "enqueue-time flip is restored when nothing lands."
        )
    assert "failed" in widget._statusLabel.text.lower(), (
        "the failure must surface on the shared status label; got "
        f"{widget._statusLabel.text!r}."
    )


def test_toolbar_run_shows_busy_state_until_the_queue_drains(
    monkeypatch, qt_widgets
):
    """The busy surface shows from the enqueue and retires when idle.

    The async path (ADR-0034 §Decision 5) replaces the blocking loop: the
    Run gesture returns immediately with the indeterminate bar + the Cancel
    (✕) affordance visible and a status message; the finish callback
    retires them once the queue is idle.  No wait cursor (nothing blocks)
    and the Run button stays live for further enqueues.
    """
    slicer, _orch = _orchestrator_or_skip()
    import LiverSegmentation as module

    slicer.mrmlScene.Clear(0)
    volume = _add_input_volume(slicer)
    widget = _widget_or_skip(slicer, qt_widgets)
    _stub_queue(monkeypatch, widget)
    _select_structure_rows(module, widget, [SCT_LIVER_CODE])

    widget.onRunSelectedStructures()

    import qt

    # The TEST pumps once: the toolbar was added to an already-shown parent,
    # so its children's layout-activation show is a posted event.  The
    # handlers themselves never pump (ADR-0034 §Decision 5 discipline).
    slicer.app.processEvents()

    assert widget._progressBar.visible, (
        "the busy/progress bar must show as soon as the job is enqueued -- "
        "'no signaling that there is processing going on'."
    )
    assert widget._cancelButton.visible, (
        "the Cancel (✕) affordance must appear while a job is queued/running."
    )
    status = widget._statusLabel.text
    assert status and "idle" not in status.lower(), (
        f"the status must signal processing, not {status!r}."
    )
    assert widget._runButton.enabled, (
        "the Run button stays live -- the async path never blocks the GUI "
        "and further structures can be enqueued."
    )
    assert qt.QApplication.overrideCursor() is None, (
        "no wait cursor -- the blocking-era spinner is retired with the "
        "blocking loop (ADR-0034 §Decision 5)."
    )

    _drive_finish(widget, volume, [SCT_LIVER_CODE], success=False)

    assert widget._progressBar.visible is False, (
        "the busy bar must retire when the queue drains."
    )
    assert widget._cancelButton.visible is False, (
        "the Cancel affordance must retire when the queue drains."
    )


def test_toolbar_run_reframes_the_threed_views(monkeypatch, qt_widgets):
    """Landing the first anatomy must re-centre the 3D views.

    The surface model generated on landing sits outside the default camera
    framing -- the surgeon saw an empty/off-centre 3D view until a manual
    re-centre.  The finish callback requests a 3D re-frame
    (``slicer.util.resetThreeDViews``) after the landing.
    """
    slicer, _orch = _orchestrator_or_skip()
    import LiverSegmentation as module

    slicer.mrmlScene.Clear(0)
    volume = _add_input_volume(slicer)
    widget = _widget_or_skip(slicer, qt_widgets)
    _stub_queue(monkeypatch, widget)
    _mock_import_seam(monkeypatch, widget)
    _select_structure_rows(module, widget, [SCT_LIVER_CODE])

    reframes = []
    monkeypatch.setattr(slicer.util, "resetThreeDViews", lambda: reframes.append(1))

    widget.onRunSelectedStructures()
    _drive_finish(widget, volume, [SCT_LIVER_CODE], success=True)

    assert reframes, (
        "the landing must request a 3D-view re-frame -- the new anatomy is "
        "otherwise outside the camera framing."
    )


def test_run_button_relabels_with_the_selection(qt_widgets):
    """The Run button re-labels live: named row / N structures / disabled.

    ADR-0034 §Amendments selection-scoped toolbar: with one row selected the
    button names the structure; with several it counts them; with none it
    reads "select a structure" and disables.
    """
    slicer, _orch = _orchestrator_or_skip()
    import LiverSegmentation as module

    slicer.mrmlScene.Clear(0)
    _add_input_volume(slicer)
    widget = _widget_or_skip(slicer, qt_widgets)

    widget.segmentsTable().setSelectedSegmentIDs([])
    widget._updateRunButton()
    assert not widget._runButton.enabled, (
        "with no selection the Run button must disable."
    )
    assert "select a structure" in widget._runButton.text.lower()

    _select_structure_rows(module, widget, [SCT_LIVER_CODE])
    widget._updateRunButton()
    assert widget._runButton.enabled
    assert "Liver parenchyma" in widget._runButton.text, (
        "a single selected row must be named on the Run button; got "
        f"{widget._runButton.text!r}."
    )

    _select_structure_rows(module, widget, [SCT_LIVER_CODE, SCT_PORTAL_VEIN_CODE])
    widget._updateRunButton()
    assert "2 structures" in widget._runButton.text, (
        "a multi-selection must be counted on the Run button; got "
        f"{widget._runButton.text!r}."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

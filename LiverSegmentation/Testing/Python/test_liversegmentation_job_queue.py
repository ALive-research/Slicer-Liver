# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""ADR-0034 §Decision 5 — the main-thread QProcess segmentation job queue.

The blocking readline+``processEvents`` run path is retired; inference runs
in the background through ``LiverSegmentationLib.SegmentationJobQueue`` —
one main-thread ``qt.QProcess`` at a time, event-driven, jobs keyed on
``(task, inputVolumeID)`` with structure-set coalescing.

Queue-level pins (real slow stub children via the injectable command
builder — never a real inference):

  * jobs sharing ``(task, input)`` coalesce — two enqueues, ONE child;
  * strictly sequential — the second job starts only after the first ends;
  * ``cancelCurrent()`` kills the running child;
  * ``cancelJob(key)`` on a QUEUED key dequeues it — no child ever spawns,
    the job completes through ``onJobFinished`` with ``success=False``;
    on the RUNNING key it kills the child (the ``cancelCurrent`` route);
  * ``shutdown()`` leaves no child and no pending job.

Widget-contract pins (queue enqueue stubbed; the finish callback driven
synchronously — except the per-job cancel pin, which drives the REAL
queue with a slow stub child):

  * enqueueing leaves every segment status UNTOUCHED — jobs can abort,
    so nothing is promised before output lands; the queued/running state
    is the per-job progress rows' to show;
  * landing writes native ``InProgress`` ("produced, under review") and
    demotes a re-run ``Completed`` same-code row (the staleness rule now
    rides the landing); nothing ever auto-writes ``Completed`` (the
    surgeon ALWAYS confirms via the status cell);
  * multi-select Run enqueues every selected structure, grouped into the
    minimal per-task backend calls;
  * the per-job ✕ on a QUEUED job dequeues it, retires its progress row,
    and leaves every segment status untouched; the running job is
    untouched.

Needs the launched-Slicer harness (Qt event loop + MRML + module); skips
cleanly under bare pytest via the shared guards.
"""

from __future__ import annotations

import os
import time

import pytest

MODULE_NAME = "liversegmentation"

SCT_LIVER_CODE = "10200004"
SCT_PORTAL_VEIN_CODE = "32764006"
SCT_HEPATIC_VEIN_CODE = "8993003"
SCT_MASS_CODE = "4147007"


def _slicer_or_skip():
    from conftest import _import_slicer_or_skip, _require_mrml_scene

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _queue_module_or_skip():
    try:
        from LiverSegmentationLib import SegmentationJobQueue
    except ImportError as exc:
        pytest.skip(f"SegmentationJobQueue not importable ({exc}).")
    return SegmentationJobQueue


def _module_or_skip():
    try:
        import LiverSegmentation  # type: ignore[import-not-found]
    except ImportError as exc:
        pytest.skip(f"LiverSegmentation not importable ({exc}).")
    return LiverSegmentation


def _widget_or_skip(slicer, registry):
    from conftest import _require_qt_widget

    _require_qt_widget()
    if getattr(slicer.modules, MODULE_NAME, None) is None:
        pytest.skip(
            f"'{MODULE_NAME}' module not registered -- ADR-0024 surgeon-UI "
            "deliverable absent."
        )
    module = _module_or_skip()
    widget = module.LiverSegmentationWidget()
    widget.setup()
    registry.append(widget)
    return widget


def _pump_until(slicer, predicate, timeout=15.0):
    """Pump the Qt event loop until ``predicate()`` or timeout.

    The TESTS pump; the queue's own handlers never do (the ADR-0034
    §Decision 5 no-``processEvents``-in-handlers discipline is the
    production-side rule this suite exists to protect).
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        slicer.app.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


class _Events:
    """Recorder for the queue's plain-Python callbacks."""

    def __init__(self):
        self.entries: list = []

    def wire(self, queue):
        queue.onJobStarted = self.started
        queue.onJobOutput = self.output
        queue.onJobFinished = self.finished

    def started(self, key, structures):
        self.entries.append(("started", key, set(structures)))

    def output(self, line):
        self.entries.append(("output", line))

    def finished(self, key, structures, success, outputDir):
        self.entries.append(("finished", key, set(structures), success, outputDir))

    def of(self, kind):
        return [entry for entry in self.entries if entry[0] == kind]


def _stub_builder(record, sleep_seconds):
    """A command builder producing a REAL slow child (observable kill)."""

    def _build(task, inputVolumeID, structures, workdir, outputDir):
        record.append((task, str(inputVolumeID), sorted(structures)))
        return "sleep", [str(sleep_seconds)]

    return _build


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@pytest.fixture
def queue_teardown():
    """Guarantee no stub child outlives a test, whatever it asserted."""
    queues: list = []

    yield queues

    for queue in queues:
        try:
            queue.shutdown()
        except Exception:  # noqa: BLE001 — teardown is best-effort
            pass


# =========================================================================== #
# Queue level — coalescing, sequencing, cancel, shutdown.
# =========================================================================== #


def test_jobs_sharing_task_and_input_coalesce_into_one_child(queue_teardown):
    """Two enqueues on one ``(task, input)`` key -> ONE child, merged set.

    ADR-0034 §Decision 4: coalescing lives in the queue -- an
    already-queued/running key merges the requested structure set into the
    existing job; no duplicate child is spawned.
    """
    slicer = _slicer_or_skip()
    queue_mod = _queue_module_or_skip()

    builds: list = []
    queue = queue_mod.SegmentationJobQueue(
        commandBuilder=_stub_builder(builds, 0.3)
    )
    queue_teardown.append(queue)
    events = _Events()
    events.wire(queue)

    key_first = queue.enqueue("total", "vol-1", [SCT_LIVER_CODE])
    key_second = queue.enqueue("total", "vol-1", [SCT_PORTAL_VEIN_CODE])

    assert key_first == key_second, (
        "the same (task, input) pair must produce the same job key."
    )
    assert _pump_until(slicer, lambda: len(events.of("finished")) == 1), (
        "the coalesced job must finish."
    )
    assert len(builds) == 1, (
        "two enqueues sharing (task, input) must spawn exactly ONE child; "
        f"the command builder ran {len(builds)} time(s)."
    )
    assert len(events.of("started")) == 1, "one job start for the coalesced pair."
    finished = events.of("finished")[0]
    assert finished[2] == {SCT_LIVER_CODE, SCT_PORTAL_VEIN_CODE}, (
        "the finish callback must carry the MERGED structure set; got "
        f"{finished[2]!r}."
    )
    assert not queue.isBusy()


def test_jobs_run_strictly_sequentially(queue_teardown):
    """The second job starts only after the first one finishes.

    ADR-0034 §Decision 5: sequential by design (the backend saturates the
    CPU; parallel inferences thrash) -- one child at a time, the next
    started from the previous job's completion path.
    """
    slicer = _slicer_or_skip()
    queue_mod = _queue_module_or_skip()

    builds: list = []
    queue = queue_mod.SegmentationJobQueue(
        commandBuilder=_stub_builder(builds, 0.3)
    )
    queue_teardown.append(queue)
    events = _Events()
    events.wire(queue)

    key_first = queue.enqueue("total", "vol-1", [SCT_LIVER_CODE])
    key_second = queue.enqueue("liver_vessels", "vol-1", [SCT_MASS_CODE])
    assert key_first != key_second

    assert queue.pendingCount() == 1, (
        "with one child running the second job must WAIT in the queue."
    )
    assert [entry[1] for entry in events.of("started")] == [key_first], (
        "only the first job may have started while it is still running."
    )

    assert _pump_until(slicer, lambda: len(events.of("finished")) == 2), (
        "both jobs must eventually finish."
    )
    ordered = [
        (entry[0], entry[1]) for entry in events.entries if entry[0] != "output"
    ]
    assert ordered == [
        ("started", key_first),
        ("finished", key_first),
        ("started", key_second),
        ("finished", key_second),
    ], (
        "strict sequencing: the second job starts only AFTER the first "
        f"finishes; got {ordered!r}."
    )


def test_cancel_kills_the_running_child(queue_teardown):
    """``cancelCurrent()`` kills the child; the job completes unsuccessfully."""
    slicer = _slicer_or_skip()
    queue_mod = _queue_module_or_skip()

    builds: list = []
    queue = queue_mod.SegmentationJobQueue(commandBuilder=_stub_builder(builds, 30))
    queue_teardown.append(queue)
    events = _Events()
    events.wire(queue)

    queue.enqueue("total", "vol-1", [SCT_LIVER_CODE])
    assert _pump_until(slicer, lambda: queue.currentProcessId() > 0), (
        "the slow child must be observably running before the cancel."
    )
    pid = queue.currentProcessId()
    assert _pid_alive(pid), "precondition: the child process is alive."

    queue.cancelCurrent()

    finished = events.of("finished")
    assert len(finished) == 1, "the cancelled job must complete through onJobFinished."
    assert finished[0][3] is False, "a cancelled job must report success=False."
    assert _pump_until(slicer, lambda: not _pid_alive(pid), timeout=5.0), (
        f"cancel must KILL the running child (pid {pid} still alive)."
    )
    assert not queue.isBusy()


def test_canceljob_dequeues_a_queued_job_without_spawning_a_child(queue_teardown):
    """``cancelJob`` on a QUEUED key dequeues it; no child ever spawns.

    The dequeued job completes through ``onJobFinished`` with
    ``success=False`` and no output directory — the same completion shape
    a failed start uses — while the RUNNING job is untouched.
    """
    slicer = _slicer_or_skip()
    queue_mod = _queue_module_or_skip()

    builds: list = []
    queue = queue_mod.SegmentationJobQueue(commandBuilder=_stub_builder(builds, 30))
    queue_teardown.append(queue)
    events = _Events()
    events.wire(queue)

    key_first = queue.enqueue("total", "vol-1", [SCT_LIVER_CODE])
    key_second = queue.enqueue("liver_vessels", "vol-1", [SCT_MASS_CODE])
    assert _pump_until(slicer, lambda: queue.currentProcessId() > 0)
    pid = queue.currentProcessId()
    assert queue.pendingKeys() == [key_second], (
        "precondition: the second job waits behind the running one."
    )

    assert queue.cancelJob(key_second) is True

    assert queue.pendingCount() == 0, "the queued job must be dequeued."
    finished = events.of("finished")
    assert [(entry[1], entry[3], entry[4]) for entry in finished] == [
        (key_second, False, None)
    ], (
        "the dequeued job must complete through onJobFinished with "
        f"success=False and no output dir; got {finished!r}."
    )
    assert [entry[1] for entry in events.of("started")] == [key_first], (
        "a dequeued job must never start."
    )
    assert len(builds) == 1, "the dequeued job must not spawn a child."
    assert queue.currentKey() == key_first and _pid_alive(pid), (
        "cancelling a QUEUED job must leave the running one untouched."
    )
    assert queue.cancelJob(("no-such-task", "vol-1")) is False, (
        "an unknown key is a no-op."
    )


def test_canceljob_on_the_running_key_kills_the_child(queue_teardown):
    """``cancelJob`` on the RUNNING key takes the ``cancelCurrent`` route."""
    slicer = _slicer_or_skip()
    queue_mod = _queue_module_or_skip()

    builds: list = []
    queue = queue_mod.SegmentationJobQueue(commandBuilder=_stub_builder(builds, 30))
    queue_teardown.append(queue)
    events = _Events()
    events.wire(queue)

    key = queue.enqueue("total", "vol-1", [SCT_LIVER_CODE])
    assert _pump_until(slicer, lambda: queue.currentProcessId() > 0)
    pid = queue.currentProcessId()

    assert queue.cancelJob(key) is True

    finished = events.of("finished")
    assert len(finished) == 1 and finished[0][3] is False, (
        "the cancelled running job must complete with success=False."
    )
    assert _pump_until(slicer, lambda: not _pid_alive(pid), timeout=5.0), (
        f"cancelJob on the running key must KILL the child (pid {pid})."
    )
    assert not queue.isBusy()


def test_shutdown_leaves_no_child_and_no_pending_job(queue_teardown):
    """``shutdown()`` cancels the current job AND drops the pending queue.

    ADR-0034 §Conformance: teardown leaves no child process -- the widget's
    ``cleanup()`` wires this so no inference outlives the module.
    """
    slicer = _slicer_or_skip()
    queue_mod = _queue_module_or_skip()

    builds: list = []
    queue = queue_mod.SegmentationJobQueue(commandBuilder=_stub_builder(builds, 30))
    queue_teardown.append(queue)
    events = _Events()
    events.wire(queue)

    key_first = queue.enqueue("total", "vol-1", [SCT_LIVER_CODE])
    queue.enqueue("liver_vessels", "vol-1", [SCT_MASS_CODE])
    assert _pump_until(slicer, lambda: queue.currentProcessId() > 0)
    pid = queue.currentProcessId()

    queue.shutdown()

    assert queue.pendingCount() == 0, "shutdown must clear every pending job."
    assert not queue.isBusy(), "shutdown must leave the queue idle."
    assert [entry[1] for entry in events.of("started")] == [key_first], (
        "the pending job must NEVER start after shutdown."
    )
    assert _pump_until(slicer, lambda: not _pid_alive(pid), timeout=5.0), (
        f"shutdown must leave no child process (pid {pid} still alive)."
    )
    assert len(builds) == 1, "the dropped pending job must not spawn a child."


# =========================================================================== #
# Widget contract — status-neutral enqueue, landing, multi-select, macro.
# =========================================================================== #


def _add_input_volume(slicer):
    import numpy as np

    volume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode")
    slicer.util.updateVolumeFromArray(volume, np.zeros((8, 8, 8), dtype="int16"))
    volume.SetAttribute("LiverRole", "PortalVenous")
    return volume


def _sct_segment(module, canonical, code):
    import vtk

    segmentation = canonical.GetSegmentation()
    for segment_id in list(segmentation.GetSegmentIDs()):
        text = vtk.mutable("")
        segmentation.GetSegment(segment_id).GetTag(
            module.TERMINOLOGY_ENTRY_TAG, text
        )
        if f"^{code}^" in str(text):
            return segment_id, segmentation.GetSegment(segment_id)
    raise AssertionError(f"no segment tagged ^{code}^")


def _stub_widget_queue(monkeypatch, widget):
    """Record widget->queue enqueues; stub the backend gate; spawn nothing."""
    calls: list = []

    def _fake_enqueue(task, inputVolumeID, structures):
        calls.append((str(task), str(inputVolumeID), sorted(structures)))
        from LiverSegmentationLib.SegmentationJobQueue import jobKey

        return jobKey(task, inputVolumeID)

    monkeypatch.setattr(widget._jobQueue, "enqueue", _fake_enqueue)
    monkeypatch.setattr(widget, "_ensureBackend", lambda: True)
    return calls


def test_enqueue_leaves_segment_statuses_untouched(monkeypatch, qt_widgets):
    """Enqueue writes NO segment status — jobs can abort before producing.

    The status column is the surgeon's channel; a queued/running job shows
    through its progress rows, and the native ``InProgress`` flip happens
    only at LANDING, when produced output actually exists.  A ``Completed``
    row being re-run therefore keeps reading ``Completed`` until its new
    output lands (the staleness demote rides the landing)."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    slicer.mrmlScene.Clear(0)

    _add_input_volume(slicer)
    widget = _widget_or_skip(slicer, qt_widgets)
    calls = _stub_widget_queue(monkeypatch, widget)
    table = widget.segmentsTable()
    canonical = table.segmentationNode()
    segments_logic = slicer.vtkSlicerSegmentationsModuleLogic

    liver_id, liver = _sct_segment(module, canonical, SCT_LIVER_CODE)
    hepatic_id, hepatic = _sct_segment(module, canonical, SCT_HEPATIC_VEIN_CODE)
    # The re-run case: hepatic vein was already confirmed by the surgeon.
    segments_logic.SetSegmentStatus(hepatic, segments_logic.Completed)

    table.setSelectedSegmentIDs([liver_id, hepatic_id])
    widget.onRunSelectedStructures()

    assert calls, "the Run gesture must enqueue."
    assert segments_logic.GetSegmentStatus(liver) == segments_logic.NotStarted, (
        "enqueue must NOT touch a NotStarted target's status -- nothing "
        "was produced yet; the progress row is the running indicator."
    )
    assert segments_logic.GetSegmentStatus(hepatic) == segments_logic.Completed, (
        "enqueue must NOT demote a Completed row -- the staleness demote "
        "happens at landing, when the new output actually arrives."
    )
    assert widget._jobRows, (
        "the queued/running state must be visible through the per-job "
        "progress rows instead of a status write."
    )


def test_landing_keeps_inprogress_never_auto_completed(monkeypatch, qt_widgets):
    """Landing keeps native ``InProgress`` — nothing auto-writes ``Completed``.

    The surgeon ALWAYS confirms manually via the status cell (ADR-0034
    §Amendments Decision 2); a successful landing therefore leaves the row
    "produced, under review", and the stage predicate stays incomplete."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    slicer.mrmlScene.Clear(0)

    volume = _add_input_volume(slicer)
    widget = _widget_or_skip(slicer, qt_widgets)
    _stub_widget_queue(monkeypatch, widget)
    table = widget.segmentsTable()
    canonical = table.segmentationNode()
    segments_logic = slicer.vtkSlicerSegmentationsModuleLogic

    def _fake_import(outputDir, structures):
        logic = widget.logic
        scratch = logic.createScratchSegmentation()
        seg_id = scratch.GetSegmentation().AddEmptySegment("synthetic", "Synthetic")
        logic.tagSegmentWithSct(scratch, seg_id, SCT_LIVER_CODE, "Synthetic")
        return scratch

    monkeypatch.setattr(widget.logic, "importJobOutput", _fake_import)

    liver_id, _liver = _sct_segment(module, canonical, SCT_LIVER_CODE)
    table.setSelectedSegmentIDs([liver_id])
    widget.onRunSelectedStructures()

    from LiverSegmentationLib.SegmentationJobQueue import jobKey

    widget._onJobFinished(
        jobKey("total", volume.GetID()), {SCT_LIVER_CODE}, True, "/nonexistent-out"
    )

    _liver_id, liver = _sct_segment(module, canonical, SCT_LIVER_CODE)
    assert segments_logic.GetSegmentStatus(liver) == segments_logic.InProgress, (
        "the landed row must READ InProgress -- landing never auto-writes "
        "Completed (the surgeon's status-cell confirm is the only writer)."
    )
    assert not widget.logic.isStageComplete(), (
        "no landing may flip the stage predicate -- Completed is the "
        "surgeon's gesture alone."
    )


def test_completed_row_demotes_at_landing_on_rerun(monkeypatch, qt_widgets):
    """Re-running a confirmed structure demotes it to ``InProgress`` at LANDING.

    Enqueue no longer touches statuses, so the staleness rule (new output
    makes a prior confirm stale, ADR-0034 §Decision 2 as amended) fires when
    the re-run's output lands: the previously landed same-code ``Completed``
    row falls back to native ``InProgress`` alongside the newly landed
    row — the surgeon re-reviews both."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    slicer.mrmlScene.Clear(0)

    volume = _add_input_volume(slicer)
    widget = _widget_or_skip(slicer, qt_widgets)
    _stub_widget_queue(monkeypatch, widget)
    table = widget.segmentsTable()
    canonical = table.segmentationNode()
    segments_logic = slicer.vtkSlicerSegmentationsModuleLogic

    # A previously landed + confirmed liver row: provenance-tagged (so the
    # placeholder-replacement path does not apply) and Completed.
    liver_id, liver = _sct_segment(module, canonical, SCT_LIVER_CODE)
    liver.SetTag(module.SOURCE_TAG, module.SOURCE_TOTALSEG)
    segments_logic.SetSegmentStatus(liver, segments_logic.Completed)

    def _fake_import(outputDir, structures):
        logic = widget.logic
        scratch = logic.createScratchSegmentation()
        seg_id = scratch.GetSegmentation().AddEmptySegment("rerun", "Rerun")
        logic.tagSegmentWithSct(scratch, seg_id, SCT_LIVER_CODE, "Rerun")
        return scratch

    monkeypatch.setattr(widget.logic, "importJobOutput", _fake_import)

    table.setSelectedSegmentIDs([liver_id])
    widget.onRunSelectedStructures()
    assert segments_logic.GetSegmentStatus(liver) == segments_logic.Completed, (
        "precondition: the enqueue left the confirmed row untouched."
    )

    from LiverSegmentationLib.SegmentationJobQueue import jobKey

    widget._onJobFinished(
        jobKey("total", volume.GetID()), {SCT_LIVER_CODE}, True, "/nonexistent-out"
    )

    assert segments_logic.GetSegmentStatus(liver) == segments_logic.InProgress, (
        "landing new output for the structure must demote the previously "
        "confirmed same-code row to InProgress -- the staleness rule rides "
        "the landing."
    )


def test_multiselect_run_enqueues_all_selected_grouped_by_task(
    monkeypatch, qt_widgets
):
    """Selecting all four rows enqueues all four structures in TWO per-task
    jobs (liver+portal share ``total``; hepatic+mass share
    ``liver_vessels``) — the minimal backend calls (ADR-0034 §Decision 4)."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    slicer.mrmlScene.Clear(0)

    volume = _add_input_volume(slicer)
    widget = _widget_or_skip(slicer, qt_widgets)
    calls = _stub_widget_queue(monkeypatch, widget)
    table = widget.segmentsTable()
    canonical = table.segmentationNode()

    all_ids = [
        _sct_segment(module, canonical, code)[0]
        for _title, code in module.STRUCTURE_TABS
    ]
    table.setSelectedSegmentIDs(all_ids)
    widget.onRunSelectedStructures()

    assert len(calls) == 2, (
        "four selected structures span two backend tasks -> exactly two "
        f"enqueued jobs; got {calls!r}."
    )
    by_task = {task: set(codes) for task, _vol, codes in calls}
    assert by_task == {
        "total": {SCT_LIVER_CODE, SCT_PORTAL_VEIN_CODE},
        "liver_vessels": {SCT_HEPATIC_VEIN_CODE, SCT_MASS_CODE},
    }, f"per-task grouping mismatch: {by_task!r}."
    assert all(vol == volume.GetID() for _task, vol, _codes in calls), (
        "every job must target the Stage-1 PortalVenous volume."
    )


def test_widget_cancel_of_a_queued_job_leaves_statuses_untouched(
    monkeypatch, qt_widgets, queue_teardown
):
    """The per-job ✕ on a QUEUED job dequeues it; statuses stay untouched.

    Drives the widget's REAL queue with a slow stub child: a multi-select
    Run spawns the ``total`` child and leaves ``liver_vessels`` queued.
    Enqueue wrote no status, so the cancel has nothing to undo: every row
    keeps exactly the status it had before the Run (including a surgeon's
    ``Completed`` confirm).  The cancelled job's progress row retires, its
    child never spawns — while the running job and its row stay
    untouched."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    slicer.mrmlScene.Clear(0)

    volume = _add_input_volume(slicer)
    widget = _widget_or_skip(slicer, qt_widgets)
    queue_teardown.append(widget._jobQueue)
    builds: list = []
    monkeypatch.setattr(widget._jobQueue, "_commandBuilder", _stub_builder(builds, 30))
    monkeypatch.setattr(widget, "_ensureBackend", lambda: True)
    table = widget.segmentsTable()
    canonical = table.segmentationNode()
    segments_logic = slicer.vtkSlicerSegmentationsModuleLogic

    liver_id, liver = _sct_segment(module, canonical, SCT_LIVER_CODE)
    hepatic_id, hepatic = _sct_segment(module, canonical, SCT_HEPATIC_VEIN_CODE)
    # A surgeon-set confirm on the soon-to-be-cancelled structure: the
    # cancel path must not rewrite it (nothing was written at enqueue).
    segments_logic.SetSegmentStatus(hepatic, segments_logic.Completed)
    table.setSelectedSegmentIDs([liver_id, hepatic_id])
    widget.onRunSelectedStructures()

    from LiverSegmentationLib.SegmentationJobQueue import jobKey

    running_key = jobKey("total", volume.GetID())
    queued_key = jobKey("liver_vessels", volume.GetID())
    assert _pump_until(slicer, lambda: widget._jobQueue.currentProcessId() > 0)
    assert widget._jobQueue.currentKey() == running_key
    assert widget._jobQueue.pendingKeys() == [queued_key]
    assert set(widget._jobRows) == {running_key, queued_key}, (
        "one progress row per queued/running job must be on screen."
    )
    assert segments_logic.GetSegmentStatus(hepatic) == segments_logic.Completed, (
        "enqueue must leave the queued structure's status untouched."
    )

    widget._onCancelJob(queued_key)

    assert segments_logic.GetSegmentStatus(hepatic) == segments_logic.Completed, (
        "cancelling the QUEUED job must leave its segment's status exactly "
        "as it was -- enqueue wrote nothing, so there is nothing to restore."
    )
    assert segments_logic.GetSegmentStatus(liver) == segments_logic.NotStarted, (
        "the RUNNING job's segment status is untouched too -- its progress "
        "row is the running indicator."
    )
    assert set(widget._jobRows) == {running_key}, (
        "the dequeued job's progress row must retire; the running one stays."
    )
    assert len(builds) == 1, "the dequeued job must never spawn its child."


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

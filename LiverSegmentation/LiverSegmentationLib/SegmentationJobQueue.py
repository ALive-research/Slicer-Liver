# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Main-thread QProcess job queue for Stage-2 background segmentation.

ADR-0034 §Decision 5: inference runs in the background, strictly
sequentially, via one main-thread ``qt.QProcess`` at a time — event-driven,
never captive.  This module REPLACES the blocking readline +
``processEvents`` run path (the named anti-pattern the interim walkthrough
implementation used).

Contract:

  * Jobs are keyed on ``(task, inputVolumeID)``.  Enqueueing an
    already-queued or already-running key COALESCES: the requested
    structure set merges into the existing job and no duplicate child is
    spawned (ADR-0034 §Decision 4 — the queue is where coalescing lives).
  * Strictly sequential: one child process at a time; the next job starts
    only from the previous job's completion path.
  * PythonQt discipline (ADR-0034 §Decision 5 + §Conformance [review]):
    the queue holds Python references to BOTH the ``qt.QProcess`` and every
    connected slot (bound methods stored on ``self`` — garbage collection
    of either silently drops ``finished``), uses string-signature
    connections, disconnects in the finish handler, and never calls
    ``slicer.app.processEvents()`` inside any handler.
  * Callbacks out are plain Python callables the widget injects:
    ``onJobStarted(key, structures)``, ``onJobOutput(line)``,
    ``onJobFinished(key, structures, success, outputDir)``.  Callback
    exceptions are logged, never allowed to wedge the queue.
  * ``cancelCurrent()`` kills the running child (``kill()``, then a
    ``terminate()`` fallback); ``shutdown()`` cancels the current job AND
    clears the pending queue — wired into the widget's teardown so no
    child outlives the module.

The command builder is injectable (tests substitute a stub child such as
``sleep``); the default reuses the existing
``ToolWrappers.TotalSegmentator`` machinery — same executable, same merged
per-task arguments, same per-structure label-file output layout the
landing path consumes.

``qt`` / ``slicer`` are imported on the call path only, so this module —
like the wrapper it drives — imports purely under bare pytest and the
import-purity child probes.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile


def jobKey(task, inputVolumeID):
    """The queue's coalescing key — shared vocabulary with the widget."""
    return (str(task), str(inputVolumeID))


def buildTotalSegmentatorJobCommand(task, inputVolumeID, structures, workdir, outputDir):
    """Default command builder: the ToolWrappers.TotalSegmentator machinery.

    Exports the input volume into the job's private ``workdir``, resolves
    the backend console script, and merges the coalesced structures into
    one per-task command (``buildCommandForStructures``).  Returns
    ``(program, arguments)`` for ``qt.QProcess.start``.  Raises on any
    missing precondition (no executable, no volume, export failure) — the
    queue converts the raise into a failed-job completion, it never
    half-starts a child.
    """
    import slicer

    from LiverSegmentationLib.ToolWrappers import TotalSegmentator as wrapper

    executable = wrapper.resolveExecutable()
    if executable is None:
        raise wrapper.TotalSegmentatorNotInstalled(
            "TotalSegmentator console script not found; run the install first."
        )
    volume = slicer.mrmlScene.GetNodeByID(str(inputVolumeID))
    if volume is None:
        raise RuntimeError(f"input volume {inputVolumeID!r} is no longer in the scene")
    input_path = os.path.join(workdir, "input.nii.gz")
    if not slicer.util.saveNode(volume, input_path):
        raise RuntimeError("could not export the input volume for inference")
    command = wrapper.buildCommandForStructures(
        executable, input_path, outputDir, sorted(structures), wrapper.detectDevice()
    )
    return command[0], command[1:]


class _Job:
    """One queued backend invocation (a coalescing bucket)."""

    def __init__(self, key, task, inputVolumeID, structures):
        self.key = key
        self.task = task
        self.inputVolumeID = inputVolumeID
        self.structures = set(structures)
        self.workdir = None
        self.outputDir = None
        self.cancelled = False


class SegmentationJobQueue:
    """Strictly sequential, coalescing, main-thread QProcess job queue."""

    def __init__(self, commandBuilder=None):
        self._commandBuilder = commandBuilder or buildTotalSegmentatorJobCommand
        # Callbacks out — plain Python callables the widget injects.
        self.onJobStarted = None
        self.onJobOutput = None
        self.onJobFinished = None
        self._queue: list = []
        self._current = None
        self._process = None
        self._buffer = b""
        # PythonQt discipline: the connected slots are bound methods STORED
        # ON SELF for the connection's lifetime (a re-created bound method
        # is a different object; letting the only reference go silently
        # drops the signal).  Populated on connect, cleared on disconnect.
        self._readyReadSlot = None
        self._finishedSlot = None
        self._errorSlot = None

    #
    # Introspection surface (the widget's busy bar / cancel button and the
    # invariant tests read these; no MRML, no Qt required).
    #

    def isBusy(self) -> bool:
        """True while a child runs or jobs are pending."""
        return self._current is not None or bool(self._queue)

    def pendingCount(self) -> int:
        """Jobs waiting behind the current one."""
        return len(self._queue)

    def currentKey(self):
        """The running job's key, or ``None`` when idle."""
        return self._current.key if self._current is not None else None

    def currentProcessId(self) -> int:
        """OS pid of the running child, or 0 when idle."""
        if self._process is None:
            return 0
        return int(self._process.processId())

    #
    # Enqueue / cancel / shutdown.
    #

    def enqueue(self, task, inputVolumeID, structures):
        """Enqueue (or coalesce) a job; returns its key.

        An already-queued or already-running key merges the requested
        structure set into the existing job — no duplicate child (ADR-0034
        §Decision 4).  A new key appends and, when the queue is idle,
        starts immediately.
        """
        key = jobKey(task, inputVolumeID)
        structures = {str(code) for code in structures}
        if self._current is not None and self._current.key == key:
            self._current.structures |= structures
            return key
        for job in self._queue:
            if job.key == key:
                job.structures |= structures
                return key
        self._queue.append(_Job(key, task, inputVolumeID, structures))
        self._startNext()
        return key

    def cancelCurrent(self):
        """Kill the running child; the queue then advances normally.

        ``kill()`` first (the child is a batch inference — nothing to save),
        with a ``terminate()`` fallback should the hard kill not take.  The
        cancelled job completes through the normal finish path with
        ``success=False``.
        """
        job = self._current
        process = self._process
        if job is None or process is None:
            return
        job.cancelled = True
        process.kill()
        if not process.waitForFinished(3000):
            process.terminate()
            process.waitForFinished(1000)
        # ``waitForFinished`` delivers ``finished`` synchronously; if the
        # signal was somehow lost (already-dead child), complete explicitly.
        if self._current is job:
            self._completeCurrent(success=False)

    def shutdown(self):
        """Cancel the running job and drop every pending one.

        Wired into the widget's ``cleanup()`` so no child process outlives
        the module (ADR-0034 §Conformance: teardown leaves no child).
        Pending jobs are cleared FIRST so the cancel's completion path does
        not start the next one.
        """
        self._queue.clear()
        self.cancelCurrent()

    #
    # Sequential engine — everything below runs on the main thread inside
    # the normal Qt event loop; no handler ever pumps events itself.
    #

    def _startNext(self):
        """Start the next queued job iff no child is running."""
        if self._current is not None:
            return
        while self._queue:
            job = self._queue.pop(0)
            job.workdir = tempfile.mkdtemp(prefix="LiverSegJobQueue-")
            job.outputDir = os.path.join(job.workdir, "out")
            os.makedirs(job.outputDir, exist_ok=True)
            try:
                program, arguments = self._commandBuilder(
                    job.task,
                    job.inputVolumeID,
                    sorted(job.structures),
                    job.workdir,
                    job.outputDir,
                )
            except Exception as exc:  # noqa: BLE001 — any precondition failure
                logging.error("Segmentation job %s could not start: %s", job.key, exc)
                self._fire(
                    self.onJobFinished, job.key, set(job.structures), False, None
                )
                shutil.rmtree(job.workdir, ignore_errors=True)
                continue

            import qt

            process = qt.QProcess()
            process.setProcessChannelMode(qt.QProcess.MergedChannels)
            self._current = job
            self._process = process
            self._buffer = b""
            # String-signature connections with the slot references held on
            # self (the PythonQt discipline this queue exists to encode).
            self._readyReadSlot = self._handleReadyRead
            self._finishedSlot = self._handleFinished
            self._errorSlot = self._handleError
            process.connect("readyReadStandardOutput()", self._readyReadSlot)
            process.connect("finished(int,QProcess::ExitStatus)", self._finishedSlot)
            process.connect("errorOccurred(QProcess::ProcessError)", self._errorSlot)
            self._fire(self.onJobStarted, job.key, set(job.structures))
            logging.info(
                "Segmentation job %s: %s %s", job.key, program, " ".join(arguments)
            )
            process.start(program, arguments)
            return

    @staticmethod
    def _toBytes(raw) -> bytes:
        """PythonQt returns ``QByteArray`` or ``bytes`` depending on version."""
        if isinstance(raw, bytes):
            return raw
        if hasattr(raw, "data"):
            return bytes(raw.data())
        return bytes(raw)

    def _handleReadyRead(self):
        """Stream child output lines to ``onJobOutput`` (event-driven)."""
        if self._process is None:
            return
        self._buffer += self._toBytes(self._process.readAllStandardOutput())
        from LiverSegmentationLib.ToolWrappers.TotalSegmentator import (
            _split_stream_pieces,
        )

        *pieces, self._buffer = _split_stream_pieces(self._buffer)
        for piece in pieces:
            self._fire(self.onJobOutput, piece)

    def _handleFinished(self, exitCode, exitStatus):
        """The child exited: complete the job and advance the queue."""
        import qt

        job = self._current
        success = (
            job is not None
            and not job.cancelled
            and exitStatus == qt.QProcess.NormalExit
            and int(exitCode) == 0
        )
        self._completeCurrent(success=success)

    def _handleError(self, error):
        """A child that never started produces no ``finished`` — complete here."""
        import qt

        if error == qt.QProcess.FailedToStart:
            self._completeCurrent(success=False)

    def _completeCurrent(self, success):
        """Disconnect, report, clean up, then start the next job.

        Idempotent (``finished`` + ``errorOccurred`` can both arrive):
        only the first call for a given job runs the completion.
        """
        job = self._current
        if job is None:
            return
        process = self._process
        self._current = None
        self._process = None
        if process is not None:
            # Flush any output that raced the exit, then disconnect every
            # slot this queue connected (the finish-handler discipline).
            self._buffer += self._toBytes(process.readAllStandardOutput())
            remainder = self._buffer.decode("utf-8", "replace").strip()
            if remainder:
                self._fire(self.onJobOutput, remainder)
            self._buffer = b""
            process.disconnect("readyReadStandardOutput()", self._readyReadSlot)
            process.disconnect(
                "finished(int,QProcess::ExitStatus)", self._finishedSlot
            )
            process.disconnect("errorOccurred(QProcess::ProcessError)", self._errorSlot)
            process.deleteLater()
        self._readyReadSlot = None
        self._finishedSlot = None
        self._errorSlot = None
        try:
            self._fire(
                self.onJobFinished, job.key, set(job.structures), success, job.outputDir
            )
        finally:
            if job.workdir is not None:
                shutil.rmtree(job.workdir, ignore_errors=True)
            self._startNext()

    @staticmethod
    def _fire(callback, *args):
        """Invoke a widget callback; a raising callback must not wedge the queue."""
        if callback is None:
            return
        try:
            callback(*args)
        except Exception:  # noqa: BLE001 — queue integrity over callback errors
            logging.exception("Segmentation job-queue callback failed")

# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

# ruff: noqa: F403, F405  # standard Slicer scripted-module wildcard-import pattern

"""LiverSegmentation — Stage 2 (Anatomy Definition) scripted module.

Hosts the Python orchestrator that sequences per-structure micro-workflows
(liver parenchyma, portal vein, hepatic vein, tumors) per
``Docs/adr/0024-segmentation-orchestration.md``.  The orchestrator:

  * publishes exactly ONE canonical ``vtkMRMLSegmentationNode`` per case,
    flagged via the ``LiverSegmentation.Role`` attribute;
  * lands tool output DIRECTLY on the canonical node as native ``InProgress``
    ("produced, under review"): the internal scratch node a run produces is
    merged and removed in the same gesture (ADR-0034 §Amendments; the
    surgeon's confirm is the stock table's status-cell click to
    ``Completed``, not a node-level Accept);
  * SCT-tags segments via the repo-root
    ``Resources/Terminology/LabelToSCT/`` bridges (ADR-0011);
  * renders with stock ``vtkMRMLSegmentationDisplayNode`` — no per-module
    display node, no LayerDM Pipeline (ADR-0013 / ADR-0002);
  * collects its nodes under the "Anatomy" Subject Hierarchy folder
    (ADR-0023 §Subject-Hierarchy convention).

The Liver shell auto-discovers this module under the Slicer module name
``liversegmentation`` and queries ``isStageComplete()`` on its logic to drive
the Stage-2 sidebar indicator (Python-convention predicate, ADR-0023
§"Per-stage state-indicator semantics"; ``LiverVolumetryLogic`` precedent).
"""

import functools
import logging
import os
import re

import qt
import slicer
import vtk
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin

#
# Orchestrator contract — namespaced node attribute distinguishing the single
# canonical Stage-2 output from per-tool scratch nodes.  Mirrors the
# ``VascularTerritories.VascTerrId`` namespacing precedent.  These are the
# authoritative definitions of the role strings the orchestrator, the Liver
# shell, and the invariant tests agree on (ADR-0024 §Terminology).
#

#: Node attribute discriminating canonical vs scratch segmentation nodes.
ROLE_ATTRIBUTE = "LiverSegmentation.Role"
#: Orchestrator-private pending output, pre-Accept.
ROLE_SCRATCH = "scratch"
#: The single published Stage-2 output downstream stages consume.
ROLE_CANONICAL = "canonical"

# The "Anatomy" Subject Hierarchy folder name is no longer duplicated here:
# the shared vtkSlicerSubjectHierarchyFolders.GetAnatomyFolderName() accessor
# is the single source of truth (ADR-0023 §"Subject Hierarchy management
# convention").

#: Slicer's standard per-segment terminology tag carrying the SCT triple.
TERMINOLOGY_ENTRY_TAG = "TerminologyEntry"
#: SCT coding scheme designator (ADR-0011).
SCT_SCHEME = "SCT"
#: Per-structure SNOMED-CT type codes (ADR-0024 §"Output contract"; resolved
#: through the repo-root Resources/Terminology/LabelToSCT/ bridges, ADR-0011).
SCT_LIVER_CODE = "10200004"
SCT_PORTAL_VEIN_CODE = "32764006"
SCT_HEPATIC_VEIN_CODE = "8993003"
SCT_MASS_CODE = "4147007"

#: Per-structure visual defaults applied when a segment is SCT-tagged (the
#: single funnel both the AI-accept and the import paths pass through).
#: v1 parity: the vessel colours are the v1 display node's canonical
#: contour colours (hepatic (0,151,206)/255, portal (216,101,79)/255); the
#: parenchyma renders TRANSLUCENT (v1 opacity 0.2) so interior structures
#: read; liver/mass colours are the Slicer generic-anatomy values.
STRUCTURE_VISUAL_DEFAULTS = {
    SCT_LIVER_CODE: {"color": (221 / 255.0, 130 / 255.0, 101 / 255.0), "opacity3d": 0.2},
    SCT_PORTAL_VEIN_CODE: {"color": (216 / 255.0, 101 / 255.0, 79 / 255.0), "opacity3d": 1.0},
    SCT_HEPATIC_VEIN_CODE: {"color": (0.0, 151 / 255.0, 206 / 255.0), "opacity3d": 1.0},
    SCT_MASS_CODE: {"color": (144 / 255.0, 238 / 255.0, 144 / 255.0), "opacity3d": 1.0},
}

# --------------------------------------------------------------------------- #
# ADR-0034 §Amendments — the review contract rides the NATIVE per-segment
# status (``vtkSlicerSegmentationsModuleLogic`` ``Segmentation.Status`` tag:
# NotStarted / InProgress / Completed / Flagged).  The retired per-segment
# confirm tag never gained a writer; Completed replaces it.
# --------------------------------------------------------------------------- #

#: Per-segment source tag — which tool / import produced the segment
#: (provenance surfaced via tooltip / the queue's status line, ADR-0034
#: §Amendments; the stock table has no Source column slot).
SOURCE_TAG = "LiverSegmentation.Source"
#: ``SOURCE_TAG`` value for segments the AI accept path lands.
SOURCE_TOTALSEG = "TotalSeg"
#: ``SOURCE_TAG`` value for segments the import-as-canonical path lands.
SOURCE_IMPORTED = "imported"
#: Legacy canonical-node attribute prefix for the retired marked-absent
#: toolbar gesture (``<prefix><sctCode>`` = "1").  The attestation now
#: rides the table's OWN status gesture — an EMPTY segment the surgeon
#: confirms ``Completed`` IS the absence statement (ADR-0034 §Amendments;
#: absence is stated, never inferred from a forgotten row, §Decision 1).
#: The attribute has no writer any more; it is still READ for back-compat
#: with scenes that carry it.
MARKED_ABSENT_ATTRIBUTE_PREFIX = "LiverSegmentation.MarkedAbsent."

#: Row-status vocabulary — derived from the native segment status, rendered
#: as GLYPH + TEXT, never colour alone (ADR-0010).  ``(glyph, text)`` pairs.
STATUS_MISSING = ("○", "Missing")
STATUS_RUNNING = ("⟳", "Running…")
STATUS_REVIEW = ("●", "Review")
STATUS_CONFIRMED = ("✓", "Confirmed")
STATUS_FLAGGED = ("⚑", "Flagged")
STATUS_MARKED_ABSENT = ("∅", "Marked absent")
STATUS_INTERACTIVE = ("✎", "Interactive…")


#: Stage-1 / Stage-2 hand-off: Stage 2 segments the portal-venous-phase
#: volume Stage 1 flags with this attribute (ADR-0024 §"Per-structure
#: micro-workflows").  Single source of truth is the shared role vocabulary
#: that Case Setup (Stage 1) writes; re-exported here for the readers below.
from LiverSegmentationLib.roles import (  # noqa: E402
    LIVER_ROLE_ATTRIBUTE,
    LIVER_ROLE_PORTAL_VENOUS,
)


#: Dotted name the TotalSegmentator wrapper lives under.  The wrapper sits in
#: the ``LiverSegmentationLib`` package — the ``<Module>Lib`` convention every
#: sibling module uses — both in the source tree and as staged into a launched
#: Slicer (CMakeLists ``ctkMacroCompilePythonScript`` target).  The module root
#: carries no ``__init__.py``, so there is no package to shadow and no
#: source-vs-staged name split: one canonical import name everywhere.
_WRAPPER_MODULE_NAME = "LiverSegmentationLib.ToolWrappers.TotalSegmentator"


def _totalSegmentatorWrapper():
    """Return the TotalSegmentator tool-wrapper module.

    Resolved on the call path only, preserving module-import purity (ADR-0024
    §"Lazy install").  Single canonical import name — the same module object
    the invariant tests import and monkeypatch.
    """
    import importlib

    return importlib.import_module(_WRAPPER_MODULE_NAME)


class LiverSegmentation(ScriptedLoadableModule):
    """Stage 2 (Anatomy Definition) scripted module.

    Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "Liver Segmentation"
        self.parent.categories = [""]
        self.parent.dependencies = []
        self.parent.contributors = ["Rafael Palomar (OUS)"]
        self.parent.helpText = """
        Stage 2 (Anatomy Definition): orchestrates per-structure segmentation
        micro-workflows (TotalSegmentator + Segment Editor) into a single
        canonical Segmentation node consumed by downstream stages.
        """
        self.parent.acknowledgementText = """
        Developed through the ALive project (grant nr. 311393).
        """
        # Hidden so it surfaces only inside the Liver shell, not as a separate
        # top-level module (same convention as LiverVolumetry).
        parent.hidden = True


#
# The Stage-2 structure vocabulary, in surgeon-workflow order (ADR-0024
# §"Per-structure micro-workflows").  Each entry pairs the row title with its
# SCT type code; the pre-seeded checklist, the landing contract, and the
# completion predicate all iterate this set (ADR-0034 §Decision 1).  The name
# predates the retired tab UI and is kept grep-stable.
#
STRUCTURE_TABS = (
    ("Liver parenchyma", SCT_LIVER_CODE),
    ("Portal vein", SCT_PORTAL_VEIN_CODE),
    ("Hepatic vein", SCT_HEPATIC_VEIN_CODE),
    ("Tumors", SCT_MASS_CODE),
)


def _findSctSegmentId(segmentationNode, sctCode):
    """The id of the segment SCT-tagged ``sctCode``, or None."""
    if segmentationNode is None:
        return None
    segmentation = segmentationNode.GetSegmentation()
    for segmentId in list(segmentation.GetSegmentIDs()):
        segment = segmentation.GetSegment(segmentId)
        text = vtk.mutable("")
        segment.GetTag(TERMINOLOGY_ENTRY_TAG, text)
        if f"^{sctCode}^" in str(text):
            return segmentId
    return None


def _findSctSegment(segmentationNode, sctCode):
    """The segment SCT-tagged ``sctCode`` on ``segmentationNode``, or None."""
    segmentId = _findSctSegmentId(segmentationNode, sctCode)
    if segmentId is None:
        return None
    return segmentationNode.GetSegmentation().GetSegment(segmentId)


def _segmentIsEmpty(segment):
    """True when a segment carries no voxel data (a checklist placeholder).

    A pre-seeded ``AddEmptySegment`` row holds an empty binary-labelmap
    representation; the async run path flips such placeholders to native
    ``InProgress`` at ENQUEUE (ADR-0034 §Decision 5 staleness rule), so the
    landing contract can no longer key on ``NotStarted`` alone — emptiness
    is what makes a row a replaceable placeholder.
    """
    if segment is None:
        return True
    name = (
        slicer.vtkSegmentationConverter.GetSegmentationBinaryLabelmapRepresentationName()
    )
    labelmap = segment.GetRepresentation(name)
    if labelmap is None:
        return True
    if hasattr(labelmap, "IsEmpty"):
        return bool(labelmap.IsEmpty())
    extent = labelmap.GetExtent()
    return extent[0] > extent[1] or extent[2] > extent[3] or extent[4] > extent[5]


def _segmentTag(segment, tag):
    """A segment tag's value as ``str`` ("" when unset / no segment)."""
    if segment is None:
        return ""
    text = vtk.mutable("")
    segment.GetTag(tag, text)
    return str(text)


def _sctTerminologyTag(code, meaning):
    """The ``TerminologyEntry`` tag value carrying an SCT-coded type triple.

    The serialization every reader in the repo greps (``^<code>^``,
    ADR-0011); :meth:`LiverSegmentationLogic.tagSegmentWithSct` is the
    funnel that applies it together with the visual defaults.
    """
    return (
        "Segmentation category and type - DICOM master list"
        f"~{SCT_SCHEME}^85756007^Tissue"
        f"~{SCT_SCHEME}^{code}^{meaning}"
        "~^^~Anatomic codes - DICOM master list~^^~^^"
    )


def structureStatus(canonicalNode, sctCode):
    """Derive a structure row's status from the canonical-node state.

    The ADR-0034 §Amendments reading — the module-level vocabulary maps the
    NATIVE per-segment status: no segment, or a ``NotStarted`` pre-seeded
    empty placeholder (``ensureExpectedStructures``) -> ``STATUS_MISSING``;
    ``InProgress`` (landed, under review) -> ``STATUS_REVIEW``;
    ``Flagged`` -> ``STATUS_FLAGGED``.  ``Completed`` splits on the data:
    a segment WITH voxel data is the surgeon's confirm
    (``STATUS_CONFIRMED``); an EMPTY ``Completed`` segment is the explicit
    absence attestation (``STATUS_MARKED_ABSENT``) — the surgeon states
    "not present in this case" through the table's own status gesture, no
    dedicated affordance.  The legacy marked-absent attribute is still
    read for back-compat with scenes that carry it.  The transient queue
    states (Running / Interactive) are the job queue's to report, not
    derivable from the node.
    """
    segmentsLogic = slicer.vtkSlicerSegmentationsModuleLogic
    markedAbsent = (
        canonicalNode is not None
        and canonicalNode.GetAttribute(MARKED_ABSENT_ATTRIBUTE_PREFIX + str(sctCode))
        == "1"
    )
    segment = _findSctSegment(canonicalNode, sctCode)
    if segment is None:
        return STATUS_MARKED_ABSENT if markedAbsent else STATUS_MISSING
    status = segmentsLogic.GetSegmentStatus(segment)
    if status == segmentsLogic.InProgress:
        return STATUS_REVIEW
    if status == segmentsLogic.Flagged:
        return STATUS_FLAGGED
    if status == segmentsLogic.Completed:
        if _segmentIsEmpty(segment) or markedAbsent:
            return STATUS_MARKED_ABSENT
        return STATUS_CONFIRMED
    # NotStarted — the pre-seeded empty checklist row.
    return STATUS_MARKED_ABSENT if markedAbsent else STATUS_MISSING


#: The percent token in a backend output line.  TotalSegmentator's nnU-Net
#: progress streams tqdm refreshes (``" 45%|████      | 9/20 ..."``); the
#: leading integer percent is the one recognizable progress datum.
_PROGRESS_PERCENT_RE = re.compile(r"(\d{1,3})\s*%")


def _progressPercent(line):
    """The 0–100 percent parsed from a backend output line, or ``None``.

    Feeds the per-job progress bars: a line carrying a tqdm-style percent
    flips the job's bar determinate; lines without one leave it as it is
    (indeterminate until the first percent arrives).
    """
    match = _PROGRESS_PERCENT_RE.search(str(line))
    if match is None:
        return None
    return max(0, min(100, int(match.group(1))))


class LiverSegmentationWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    """Stage-2 surgeon panel — the anatomy segments table + selection toolbar.

    ADR-0034 §Amendments: the panel is a configured stock
    ``qMRMLSegmentsTableView`` over the single canonical node, minted (or
    adopted) on setup so the pre-seeded four-row checklist is visible the
    moment Stage 2 opens.  A selection-scoped toolbar under the table acts
    on the SELECTED rows: Run TotalSegmentator (enqueues every selected
    structure into the §Decision 5 job queue; results land on the
    canonical node as native ``InProgress`` — no Accept/Reject machinery;
    the surgeon's confirm is the status-cell click) and Edit in Segment
    Editor (interim jump-to-module until the embedded-editor increment).
    Absence is attested through the table's own status gesture — an EMPTY
    row the surgeon sets ``Completed`` reads Marked absent — so the
    toolbar carries no dedicated affordance for it.  Each queued/running
    job shows its OWN progress row (text embedded in the bar, per-job ✕
    cancel) under the toolbar.  Inference runs in the BACKGROUND via the
    main-thread QProcess queue — the GUI stays responsive; no blocking
    readline loop, no ``processEvents`` in handlers.

    A Stage-2-local backend-status row (installed ✓/✗ + Pre-download) surfaces
    the TotalSegmentator install state.  This is intentionally local to
    Stage 2, NOT the Liver-shell settings panel that ADR-0024 §"Lazy install"
    / §Follow-on defers to a sub-affordance of the shell's Stage 6.

    Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent=None):
        self.logic = None
        self._backendStatusLabel = None
        # Load-a-segmentation affordance (the v2.0 no-AI path); built in setup().
        self._loadSegCombo = None
        self._loadSegTable = None
        # Async run path (ADR-0034 §Decision 5): the QProcess job queue plus
        # the widget's per-job bookkeeping — pre-enqueue statuses (restored
        # when a job ends without landing a structure) and one progress row
        # per queued/running job.  Built in setup().
        self._jobQueue = None
        self._pendingJobs = {}
        self._jobRows = {}
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)

    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)

        self.logic = LiverSegmentationLogic()
        self._jobQueue = self._buildJobQueue()

        self.layout.addWidget(self._buildSegmentsTable())
        self.layout.addWidget(self._buildSelectionToolbar())
        self.layout.addWidget(self._buildLoadSegmentationSection())
        self.layout.addWidget(self._buildBackendStatusRow())

        # Keep the table bound to the canonical node across scene changes.
        self.addObserver(
            slicer.mrmlScene, slicer.mrmlScene.NodeAddedEvent, self._onSceneChanged
        )
        self.addObserver(
            slicer.mrmlScene, slicer.mrmlScene.NodeRemovedEvent, self._onSceneChanged
        )

        self.layout.addStretch(1)
        # Opening Stage 2 mints-or-adopts the canonical node (idempotent) so
        # the pre-seeded checklist is on screen immediately — the stock
        # view's "no node selected" empty state never shows (ADR-0034
        # §Decision 1: the empty state teaches the goal).
        self.logic.getOrCreateCanonicalSegmentation()
        self._bindSegmentsTable()
        self._refreshBackendStatus()
        self._updateRunButton()

    def _buildJobQueue(self):
        """Mint the ADR-0034 §Decision 5 job queue with the widget callbacks.

        The queue module is imported on the setup path only (mirroring the
        wrapper discipline) so ``import LiverSegmentation`` stays pure.  The
        callbacks are plain bound methods; the queue holds its own QProcess/
        slot references per the PythonQt discipline.
        """
        from LiverSegmentationLib.SegmentationJobQueue import SegmentationJobQueue

        queue = SegmentationJobQueue()
        queue.onJobStarted = self._onJobStarted
        queue.onJobOutput = self._onJobOutput
        queue.onJobFinished = self._onJobFinished
        return queue

    def _buildSegmentsTable(self):
        """Build the ADR-0034 §Amendments anatomy segments table.

        A configured STOCK ``qMRMLSegmentsTableView`` over the canonical
        node: status column on (the native status-cell single-click cycle
        IS the review gesture), layer column off, filter bar off,
        terminology selector on.  Rows ARE segments — the pre-seeded
        checklist is real empty segments (``ensureExpectedStructures``),
        no parallel bookkeeping.  Segment provenance (the retired Source
        column) lives in the per-segment ``SOURCE_TAG``.
        """
        # Widgets-module PythonQt binding; resolved on the build path only
        # (mirrors the wrapped-class namespace discipline).
        import qSlicerSegmentationsModuleWidgetsPythonQt

        view = qSlicerSegmentationsModuleWidgetsPythonQt.qMRMLSegmentsTableView()
        view.setObjectName("AnatomySegmentsTable")
        view.setMRMLScene(slicer.mrmlScene)
        view.setStatusColumnVisible(True)
        view.setLayerColumnVisible(False)
        view.setFilterBarVisible(False)
        view.setUseTerminologySelector(True)
        # The Run button re-labels live with the table selection (ADR-0034
        # §Amendments: selection-scoped toolbar).  The view's own
        # ``selectionChanged`` carries ``QItemSelection`` arguments PythonQt
        # cannot marshal (a per-emission warning and no reliable delivery),
        # so TWO surfaces cover every gesture: the inner selection model's
        # ``currentChanged`` (keyboard navigation — ``QModelIndex``
        # marshals fine) AND the inner view's ``clicked`` (a ctrl-click
        # deselect of the current row never moves the current index, so
        # ``currentChanged`` alone lags one gesture behind).  Both route
        # into a zero-interval re-resolve from the REAL selection.  The
        # slot references are stored on self for the connections' lifetime
        # (the PythonQt discipline).  Best-effort: a missing surface only
        # costs the live re-label (the gesture handlers re-resolve the
        # selection anyway).
        self._tableSelectionSlot = self._onTableSelectionChanged
        try:
            inner = view.tableWidget()
            inner.selectionModel().connect(
                "currentChanged(QModelIndex,QModelIndex)",
                self._tableSelectionSlot,
            )
            inner.connect("clicked(QModelIndex)", self._tableSelectionSlot)
        except Exception as exc:  # noqa: BLE001 — defensive across versions
            logging.debug("segments-table selection signal unavailable: %s", exc)
        self._segmentsTable = view
        return view

    def segmentsTable(self):  # noqa: N802 - Slicer/Qt verb convention
        return getattr(self, "_segmentsTable", None)

    def _bindSegmentsTable(self):
        """(Re-)bind the segments table to the canonical node, if one exists.

        Pure READ path: binds only when a canonical node is already in the
        scene, else leaves the view's node None — a refresh must never mint
        the canonical node (``getOrCreateCanonicalSegmentation`` is the
        write gesture ``setup()`` performs once, explicitly; ADR-0024
        §"Output contract").
        """
        view = getattr(self, "_segmentsTable", None)
        if view is None or self.logic is None:
            return
        try:
            view.setSegmentationNode(self.logic._findCanonicalSegmentation())
        except ValueError:
            # PythonQt raises when the Qt view was destroyed with a parent
            # tree while this Python widget (and its scene observers) is
            # still alive — e.g. a host shell disposing the composed page.
            # Drop the stale reference; the observers go with cleanup().
            self._segmentsTable = None

    def _buildSelectionToolbar(self):
        """Build the selection-scoped toolbar + the per-job progress list.

        ADR-0034 §Amendments: gestures act on the SELECTED table rows, not
        on per-row button walls.  Run enqueues every selected structure
        (structures sharing a backend task coalesce into one child;
        multi-select covers the run-everything gesture); Edit jumps to the
        Segment Editor on the first selected row (interim until the
        embedded-editor increment).  Absence is attested through the
        table's own status gesture (empty row set ``Completed``), so no
        dedicated button.  Under the buttons, one progress row PER
        queued/running job — the job's text embedded IN its bar, a per-job
        cancel (✕) beside it — plus one shared status label for
        queue/backend lines.
        """
        box = qt.QWidget()
        column = qt.QVBoxLayout(box)
        column.setContentsMargins(0, 0, 0, 0)

        row = qt.QHBoxLayout()
        self._runButton = qt.QPushButton(self._RUN_LABEL_BASE)
        self._editButton = qt.QPushButton("Edit in Segment Editor")
        row.addWidget(self._runButton)
        row.addWidget(self._editButton)
        row.addStretch(1)
        column.addLayout(row)

        self._jobListBox = qt.QWidget()
        self._jobListLayout = qt.QVBoxLayout(self._jobListBox)
        self._jobListLayout.setContentsMargins(0, 0, 0, 0)
        column.addWidget(self._jobListBox)

        self._statusLabel = qt.QLabel("Idle")
        column.addWidget(self._statusLabel)

        self._runButton.connect("clicked()", self.onRunSelectedStructures)
        self._editButton.connect("clicked()", self.onEditInSegmentEditor)
        return box

    #: Run-button label vocabulary (re-labelled live with the selection).
    _RUN_LABEL_BASE = "Run TotalSegmentator"

    def _selectedStructures(self):
        """The selected table rows as ``[(segment, sctCode), ...]``.

        Resolves the stock view's (multi-)selection to the canonical
        segments and the structure-vocabulary SCT codes their
        ``TerminologyEntry`` tags carry, in selection order.  Rows outside
        the vocabulary are skipped.  Empty when nothing is selected —
        callers surface their own hint on the shared status label.
        """
        view = getattr(self, "_segmentsTable", None)
        canonical = view.segmentationNode() if view is not None else None
        if canonical is None:
            return []
        selections = []
        for segmentId in list(view.selectedSegmentIDs()):
            segment = canonical.GetSegmentation().GetSegment(segmentId)
            if segment is None:
                continue
            code = self.logic._expectedCodeForSegment(segment)
            if code is None:
                continue
            selections.append((segment, code))
        return selections

    def _onTableSelectionChanged(self, *_args):
        """Schedule a Run-button re-resolve AFTER the gesture settles.

        The reporting signal (``clicked`` / ``currentChanged``) fires
        mid-gesture, before the selection model reflects a ctrl-click
        deselect; a zero-interval single-shot re-reads the REAL selection
        once the event cascade completes, so the label never lags a
        gesture behind.
        """
        qt.QTimer.singleShot(0, self._updateRunButton)

    def _updateRunButton(self):
        """Re-label the Run button from the REAL current selection."""
        button = getattr(self, "_runButton", None)
        if button is None:
            return
        try:
            selections = self._selectedStructures()
            if not selections:
                button.setText(f"{self._RUN_LABEL_BASE} — select a structure")
                button.setEnabled(False)
            elif len(selections) == 1:
                title = self.logic._structureTitle(selections[0][1])
                button.setText(f"{self._RUN_LABEL_BASE} — {title}")
                button.setEnabled(True)
            else:
                button.setText(
                    f"{self._RUN_LABEL_BASE} — {len(selections)} structures"
                )
                button.setEnabled(True)
        except ValueError:
            # The deferred re-resolve can outlive the Qt widgets (PythonQt
            # raises on a deleted C++ object); nothing left to re-label.
            pass

    def _ensureBackend(self):
        """Backend-availability gate on the Run path (main thread).

        The confirm dialog (lazy install, ADR-0024 §"Lazy install") must run
        on the GUI side BEFORE anything is enqueued — the queue's child knows
        only the console script.  A widget seam so tests stay hermetic.
        """
        return _totalSegmentatorWrapper().ensureBackendInstalled()

    def onRunSelectedStructures(self):
        """Enqueue the AI backend for EVERY selected row (async, ADR-0034 §5).

        The surgeon flow (ADR-0034 §Amendments): select rows -> Run -> each
        targeted row flips to native ``InProgress`` immediately (running a
        structure IS editing it — the staleness rule also demotes a re-run
        ``Completed`` row), the job queue runs the minimal set of backend
        children (structures sharing a task coalesce), and the finish
        callback lands the results on the canonical node.  The GUI stays
        responsive throughout — no blocking loop, no ``processEvents``.
        """
        selections = self._selectedStructures()
        if not selections:
            self._statusLabel.setText("Select a structure row in the table first.")
            return
        volume = self.logic.selectInputVolume()
        if volume is None:
            # No portal-venous working volume tagged in Stage 1 -- do NOT run
            # the backend on None (a silent no-op that reads as success);
            # surface the missing hand-off instead (ADR-0024 Stage-1/Stage-2
            # hand-off).
            self._statusLabel.setText(
                "Tag a PortalVenous volume in Case Setup (Stage 1) first."
            )
            return
        if not self._ensureBackend():
            wrapper = _totalSegmentatorWrapper()
            self._statusLabel.setText(
                "TotalSegmentator is not installed — Run again to install "
                f"({wrapper.TOTALSEGMENTATOR_DOWNLOAD_SIZE}), or use Edit in "
                "Segment Editor."
            )
            return
        self._enqueueStructures([code for _segment, code in selections], volume)

    def _enqueueStructures(self, sctCodes, volume):
        """Group by backend task, flip the rows, and enqueue (ADR-0034 §4/§5).

        Grouping happens HERE (one enqueue per task with the full structure
        set) so a single gesture's structures share one child from the
        start; the queue's key-level coalescing then absorbs repeat gestures
        on an already-queued/running task.  At enqueue every targeted
        segment flips to native ``InProgress`` immediately — running a
        structure is editing it, and a re-run of a ``Completed`` row demotes
        the same way (the staleness rule).  The pre-enqueue status is
        recorded so a job that ends WITHOUT landing a structure restores it.
        """
        from LiverSegmentationLib.SegmentationJobQueue import jobKey

        wrapper = _totalSegmentatorWrapper()
        canonical = self.logic.getOrCreateCanonicalSegmentation()
        segmentsLogic = slicer.vtkSlicerSegmentationsModuleLogic
        byTask = {}
        for code in sctCodes:
            spec = wrapper.INFERENCE_TARGETS.get(str(code))
            if spec is None:
                logging.warning("no backend task for SCT %s; skipped", code)
                continue
            byTask.setdefault(spec["task"], []).append(str(code))
        if not byTask:
            return
        names = []
        for task, taskCodes in byTask.items():
            key = jobKey(task, volume.GetID())
            pending = self._pendingJobs.setdefault(key, {})
            for code in taskCodes:
                segment = _findSctSegment(canonical, code)
                if segment is None:
                    continue
                if code not in pending:
                    pending[code] = segmentsLogic.GetSegmentStatus(segment)
                segmentsLogic.SetSegmentStatus(segment, segmentsLogic.InProgress)
                names.append(self.logic._structureTitle(code))
            self._jobQueue.enqueue(task, volume.GetID(), taskCodes)
            # Busy surface: one progress row per job (text embedded in the
            # bar + per-job cancel); the finish callback retires each row.
            self._ensureJobRow(key)
        self._statusLabel.setText(
            "Queued TotalSegmentator: " + ", ".join(names) + "…"
        )

    #
    # Per-job progress rows — one bar (job text embedded) + one cancel (✕)
    # per queued/running job, retired as each job finishes.
    #

    def _jobLabel(self, key):
        """The text embedded in a job's bar: tool + its structure titles."""
        codes = self._pendingJobs.get(key, {})
        titles = [title for title, code in STRUCTURE_TABS if code in codes]
        return "TotalSegmentator — " + ", ".join(titles or [str(key[0])])

    def _ensureJobRow(self, key):
        """Create (or re-label, on coalescing) the progress row for ``key``.

        The bar starts indeterminate — the backend's tqdm output flips it
        determinate when a percent is parsed (``_onJobOutput``) — with the
        job's text embedded via ``setFormat``.  The per-job ✕ routes to
        ``cancelJob``: dequeue when queued, kill when running.  The
        connected slot is stored for the connection's lifetime (the
        PythonQt discipline the queue encodes).
        """
        label = self._jobLabel(key)
        row = self._jobRows.get(key)
        if row is None:
            box = qt.QWidget()
            layout = qt.QHBoxLayout(box)
            layout.setContentsMargins(0, 0, 0, 0)
            bar = qt.QProgressBar()
            bar.setRange(0, 0)
            bar.setTextVisible(True)
            cancel = qt.QToolButton()
            cancel.setText("✕")
            cancel.setToolTip("Cancel this segmentation job.")
            slot = functools.partial(self._onCancelJob, key)
            cancel.connect("clicked()", slot)
            layout.addWidget(bar, 1)
            layout.addWidget(cancel)
            self._jobListLayout.addWidget(box)
            row = {"box": box, "bar": bar, "cancel": cancel, "slot": slot}
            self._jobRows[key] = row
        row["label"] = label
        bar = row["bar"]
        bar.setFormat(label if bar.maximum == 0 else f"{label} — %p%")

    def _removeJobRow(self, key):
        """Retire a finished/cancelled job's progress row."""
        row = self._jobRows.pop(key, None)
        if row is None:
            return
        try:
            box = row["box"]
            box.setParent(None)
            box.delete()
        except (ValueError, AttributeError):
            # Already reclaimed with a disposed parent tree.
            pass

    def _onCancelJob(self, key):
        """The per-job ✕: dequeue a queued job / kill the running child.

        Both routes complete through the queue's finish path with
        ``success=False``, so ``_onJobFinished`` restores the targeted
        rows' pre-enqueue statuses and retires the job's progress row.
        """
        if self._jobQueue is not None:
            self._jobQueue.cancelJob(key)

    #
    # Queue callbacks (main thread, event-driven — never call
    # slicer.app.processEvents() here; ADR-0034 §Decision 5).
    #

    def _onJobStarted(self, key, structures):
        names = ", ".join(sorted(self.logic._structureTitle(c) for c in structures))
        self._statusLabel.setText(f"Running TotalSegmentator: {names}…")

    def _onJobOutput(self, line):
        """Stream a child output line to the status label + the job's bar.

        The queue is strictly sequential, so output belongs to its current
        job; a line carrying a recognizable percent (the backend's tqdm
        refreshes) flips that job's bar determinate and drives its value —
        the embedded job text stays either way.
        """
        if not line:
            return
        self._statusLabel.setText(str(line)[-80:])
        key = self._jobQueue.currentKey() if self._jobQueue is not None else None
        row = self._jobRows.get(key)
        if row is None:
            return
        percent = _progressPercent(line)
        if percent is None:
            return
        bar = row["bar"]
        if bar.maximum == 0:
            bar.setRange(0, 100)
            bar.setFormat(f"{row['label']} — %p%")
        bar.setValue(percent)

    def _onJobFinished(self, key, structures, success, outputDir):
        """Land a finished job's label files on the canonical node.

        The landing tail of the retired blocking path, now event-driven: the
        produced per-structure label files import into an internal scratch
        (``importJobOutput``) which ``accept()`` merges onto the canonical —
        every landed row reads native ``InProgress`` ("produced, under
        review"); NOTHING ever auto-writes ``Completed``, the surgeon always
        confirms via the status cell (ADR-0034 §Amendments).  Structures the
        job did NOT land (failure, cancel, or a label file the backend never
        produced) fall back to their recorded pre-enqueue status.
        """
        pending = self._pendingJobs.pop(key, {})
        landedCodes = set()
        if success and outputDir:
            scratch = None
            try:
                scratch = self.logic.importJobOutput(outputDir, structures)
            except Exception as exc:  # noqa: BLE001 — surface, never wedge
                logging.error("could not import the job output: %s", exc)
            if scratch is not None:
                segmentation = scratch.GetSegmentation()
                for segmentId in list(segmentation.GetSegmentIDs()):
                    code = self.logic._expectedCodeForSegment(
                        segmentation.GetSegment(segmentId)
                    )
                    if code is not None:
                        landedCodes.add(code)
                self.logic.accept(scratch)
                # The landed surface model sits outside the default camera
                # framing; re-centre the 3D views (GUI-level concern).
                self._reframeThreeDViews()
        self._restoreUnlandedStatuses(pending, landedCodes)
        self._removeJobRow(key)
        if landedCodes:
            self._statusLabel.setText(
                "Landed for review — confirm via the row's status cell."
            )
        elif success:
            self._statusLabel.setText(
                "Segmentation finished but produced no output — see the log."
            )
        else:
            names = ", ".join(
                sorted(self.logic._structureTitle(c) for c in structures)
            )
            self._statusLabel.setText(f"Segmentation failed: {names} — see the log.")

    def _restoreUnlandedStatuses(self, pending, landedCodes):
        """Fall structures a job never landed back to their pre-enqueue status.

        The enqueue-time ``InProgress`` flip is a promise of produced output;
        when the job ends without delivering a structure, the row must not
        keep reading "under review" over unchanged (or absent) data.  Only a
        row still ``InProgress`` is restored — a status the surgeon set in
        the meantime wins.
        """
        canonical = self.logic._findCanonicalSegmentation()
        if canonical is None:
            return
        segmentsLogic = slicer.vtkSlicerSegmentationsModuleLogic
        for code, previousStatus in pending.items():
            if code in landedCodes:
                continue
            segment = _findSctSegment(canonical, code)
            if segment is None:
                continue
            if segmentsLogic.GetSegmentStatus(segment) == segmentsLogic.InProgress:
                segmentsLogic.SetSegmentStatus(segment, previousStatus)

    def _reframeThreeDViews(self):
        """Re-centre the 3D views on the new anatomy; a no-op headless.

        Under ``--no-main-window`` there is no layout manager, so the stock
        helper raises — the re-frame is a pure GUI nicety and must never
        fail the landing/import path.
        """
        try:
            slicer.util.resetThreeDViews()
        except AttributeError:
            logging.debug("3D re-frame skipped: no layout manager (headless).")

    def onEditInSegmentEditor(self):
        """Open the stock Segment Editor on the canonical node.

        Interim jump-to-module until the embedded ``qMRMLSegmentEditorWidget``
        increment lands (ADR-0034 §Amendments).  With a table selection, the
        FIRST selected row becomes the editor's current segment.  Kumar-Oram
        effect pre-activation is out of scope here (ADR-0026 / future).
        """
        canonical = self.logic.getOrCreateCanonicalSegmentation()
        view = getattr(self, "_segmentsTable", None)
        selected = list(view.selectedSegmentIDs()) if view is not None else []
        slicer.util.selectModule("SegmentEditor")
        try:
            editorWidget = slicer.modules.segmenteditor.widgetRepresentation().self()
            editorWidget.editor.setSegmentationNode(canonical)
            if selected:
                editorWidget.editor.setCurrentSegmentID(selected[0])
        except Exception as exc:  # noqa: BLE001 — defensive across Slicer versions
            logging.debug("Could not pre-select canonical node in editor: %s", exc)

    def _buildBackendStatusRow(self):
        """Build the Stage-2-local backend-status + Pre-download row.

        Reflects ``ToolWrappers.TotalSegmentator.ensureBackendInstalled``
        truthiness (installed ✓/✗); Pre-download calls
        ``ensureBackendInstalled(confirm=False)`` and mints no node — the
        click is the surgeon's opt-in (ADR-0024 §"Lazy install").

        NOTE: this row is intentionally local to Stage 2.  ADR-0024
        §"Lazy install" / §Follow-on defers a shell-wide AI-backend settings
        panel (installed-status + pre-download for offline use) to a
        sub-affordance of the Liver shell's Stage 6; this local row migrates
        there when that panel lands.
        """
        row = slicer.util.loadUI(self.resourcePath("UI/BackendStatusRow.ui"))
        ui = slicer.util.childWidgetVariables(row)
        self._backendStatusLabel = ui.BackendStatusLabel
        ui.PreDownloadButton.connect("clicked()", self.onPreDownload)
        return row

    def _buildLoadSegmentationSection(self):
        """Build the "load an existing segmentation" affordance (ADR-0024).

        The v2.0 path to a canonical segmentation WITHOUT in-app AI (deferred to
        v2.1): pick a loaded ``vtkMRMLSegmentationNode``, assign each of its
        segments a structure, and Import -> the logic promotes it to canonical
        and SCT-tags the assigned segments (``importSegmentationAsCanonical``).
        """
        box = slicer.util.loadUI(self.resourcePath("UI/LoadSegmentationSection.ui"))
        ui = slicer.util.childWidgetVariables(box)
        combo = ui.LoadSegmentationComboBox
        # Bind the selector's scene explicitly -- the root is a plain QGroupBox,
        # so there is no qMRMLWidget setMRMLScene to propagate.
        combo.setMRMLScene(slicer.mrmlScene)
        combo.connect("currentNodeChanged(vtkMRMLNode*)", self._onLoadSegmentationSelected)
        table = ui.LoadSegmentationAssignTable
        table.horizontalHeader().setStretchLastSection(True)
        ui.ImportSegmentationButton.connect("clicked()", self._onImportSegmentationAsCanonical)

        self._loadSegCombo = combo
        self._loadSegTable = table
        return box

    def _onLoadSegmentationSelected(self, node):
        """Repopulate the per-segment structure-assignment table."""
        table = self._loadSegTable
        if table is None:
            return
        segmentIds = []
        if node is not None:
            segmentation = node.GetSegmentation()
            segmentIds = list(segmentation.GetSegmentIDs())
        table.setRowCount(len(segmentIds))
        for row, segmentId in enumerate(segmentIds):
            segment = node.GetSegmentation().GetSegment(segmentId)
            name = segment.GetName() if segment is not None else segmentId
            nameItem = qt.QTableWidgetItem(name)
            nameItem.setData(qt.Qt.UserRole, segmentId)
            table.setItem(row, 0, nameItem)

            picker = qt.QComboBox()
            picker.addItem("(skip)", None)
            for title, sctCode in STRUCTURE_TABS:
                picker.addItem(title, sctCode)
            table.setCellWidget(row, 1, picker)

    def _onImportSegmentationAsCanonical(self):
        """Collect the structure assignments and promote the loaded node."""
        combo = self._loadSegCombo
        table = self._loadSegTable
        if combo is None or table is None or self.logic is None:
            return
        node = combo.currentNode()
        if node is None:
            return
        assignments = {}
        for row in range(table.rowCount):
            nameItem = table.item(row, 0)
            picker = table.cellWidget(row, 1)
            if nameItem is None or picker is None:
                continue
            sctCode = picker.itemData(picker.currentIndex)
            if sctCode is None:
                continue  # "(skip)"
            segmentId = nameItem.data(qt.Qt.UserRole)
            meaning = picker.itemText(picker.currentIndex)
            assignments[segmentId] = (sctCode, meaning)
        if not assignments:
            return
        self.logic.importSegmentationAsCanonical(node, assignments)
        # The import promotes an EXISTING node (no NodeAdded/Removed event
        # reaches _onSceneChanged), so re-bind the table explicitly.
        self._bindSegmentsTable()
        # Same re-centre as the toolbar Run's landing: the imported anatomy's
        # surface model lands outside the default camera framing.
        self._reframeThreeDViews()

    def onPreDownload(self):
        """Pre-download the AI backend without minting a node.

        Calls ``ensureBackendInstalled(confirm=False)`` — the click itself is
        the surgeon's opt-in, so no second size dialog — through the module
        reference so the install path stays under ``ToolWrappers/`` (ADR-0024
        §"Lazy install").  Pre-downloading the model is NOT a Run: no
        segmentation node is created.
        """
        _totalSegmentatorWrapper().ensureBackendInstalled(confirm=False)
        self._refreshBackendStatus()

    def _refreshBackendStatus(self):
        if self._backendStatusLabel is None:
            return
        installed = _totalSegmentatorWrapper()._backend_importable()
        glyph = "✓" if installed else "✗"
        state = "installed" if installed else "not installed"
        self._backendStatusLabel.setText(f"AI backend (TotalSegmentator): {glyph} {state}")

    def _onSceneChanged(self, caller=None, event=None):
        self._bindSegmentsTable()

    def cleanup(self):
        # No child process outlives the module: cancel the running job and
        # drop every pending one (ADR-0034 §Decision 5 teardown contract).
        if self._jobQueue is not None:
            self._jobQueue.shutdown()
        self.removeObservers()


class LiverSegmentationLogic(ScriptedLoadableModuleLogic):
    """Stage-2 orchestrator: scratch/canonical lifecycle + SCT dispatch.

    The single canonical-node creation path lives in
    :meth:`getOrCreateCanonicalSegmentation`; scratch nodes are minted by
    :meth:`createScratchSegmentation`; :meth:`accept` merges a scratch node's
    segments into the existing canonical node without minting a second one.
    """

    def __init__(self):
        ScriptedLoadableModuleLogic.__init__(self)

    #
    # Stage-completion predicate (ADR-0023 §"Per-stage state-indicator
    # semantics"; LiverVolumetryLogic.isStageComplete() precedent).
    #

    def isStageComplete(self) -> bool:
        """Return True iff Stage 2 is done: every expected structure Completed.

        ADR-0034 §Amendments: stage completion is the NATIVE per-segment
        status — a canonical node exists and every structure-vocabulary
        entry's segment reads ``Completed`` (the surgeon's status-cell
        confirm).  An EMPTY ``Completed`` segment is the explicit absence
        attestation and counts — absence is stated through the same status
        gesture, never inferred from a forgotten row.  Scratch nodes never
        flip the predicate true (canonical-only read).
        """
        canonical = self._findCanonicalSegmentation()
        if canonical is None:
            return False
        segmentsLogic = slicer.vtkSlicerSegmentationsModuleLogic
        for _title, sctCode in STRUCTURE_TABS:
            segment = _findSctSegment(canonical, sctCode)
            if segment is None:
                return False
            if segmentsLogic.GetSegmentStatus(segment) != segmentsLogic.Completed:
                return False
        return True

    def isStructureAccepted(self, sctCode) -> bool:
        """Return True iff the CANONICAL node holds a LANDED ``sctCode`` segment.

        Logic predicate (its retired consumer was the tab-glyph UI).
        "Landed" reads through the native status (ADR-0034 §Amendments):
        the segment exists AND its status has moved past ``NotStarted`` —
        a pre-seeded empty placeholder (``ensureExpectedStructures``) is
        expected, not accepted.  Canonical-only read (mirroring
        :meth:`_findCanonicalSegmentation`): a scratch node tagged for the
        structure is pending, not landed (ADR-0024 §"Output contract" +
        §Terminology).
        """
        canonical = self._findCanonicalSegmentation()
        segment = _findSctSegment(canonical, sctCode)
        if segment is None:
            return False
        segmentsLogic = slicer.vtkSlicerSegmentationsModuleLogic
        return segmentsLogic.GetSegmentStatus(segment) != segmentsLogic.NotStarted

    #
    # Canonical / scratch surface (ADR-0024 §"Output contract" + §Terminology).
    #

    def getOrCreateCanonicalSegmentation(self):
        """Return the single canonical segmentation node, creating it if absent.

        Idempotent (get-or-create): repeated calls return the SAME node, never
        a second canonical node (ADR-0024 §"Output contract", rejecting
        Alternative B).  Pre-seeds the expected-structure checklist on
        creation AND on adoption of an existing canonical, so loaded scenes
        self-heal (ADR-0034 §Amendments; :meth:`ensureExpectedStructures`).
        """
        canonical = self._findCanonicalSegmentation()
        if canonical is None:
            canonical = self._createSegmentationWithRole(
                ROLE_CANONICAL, "Anatomy: Canonical"
            )
        self.ensureExpectedStructures(canonical)
        return canonical

    def ensureExpectedStructures(self, canonicalNode):
        """Pre-seed the expected-structure checklist as real empty segments.

        ADR-0034 §Amendments: rows ARE segments — for each structure-
        vocabulary entry (``STRUCTURE_TABS``) whose SCT code has no segment
        yet, add an empty segment carrying the SCT terminology tag, the
        vocabulary title as its name, and the structure visual defaults,
        left status-untagged so it reads the native ``NotStarted``.  The
        empty state teaches the goal (ADR-0034 §Decision 1).  Idempotent —
        existing segments (placeholder or landed) are never touched.
        """
        if canonicalNode is None:
            return
        for title, sctCode in STRUCTURE_TABS:
            if _findSctSegmentId(canonicalNode, sctCode) is not None:
                continue
            segmentId = canonicalNode.GetSegmentation().AddEmptySegment("", title)
            self.tagSegmentWithSct(
                canonicalNode, segmentId, sctCode, self._structureMeaning(sctCode)
            )

    def importSegmentationAsCanonical(self, sourceSegmentationNode, assignments):
        """Promote a loaded segmentation to the canonical node, SCT-tagging it.

        The v2.0 path to a canonical segmentation WITHOUT in-app AI (deferred to
        v2.1): the surgeon loads a segmentation and assigns each segment a
        structure.  ``assignments`` maps ``segmentId -> (sctCode, meaning)``.
        Marks ``sourceSegmentationNode`` as THE canonical node (ADR-0024
        §"Output contract" — exactly one; any prior canonical is demoted) and
        SCT-tags each assigned segment via :meth:`tagSegmentWithSct`.  Landed
        segments arrive as native ``InProgress`` with the ``imported`` source
        tag — imports no longer skip the review boundary (ADR-0034
        §Amendments); the surgeon's status-cell confirm to ``Completed`` is
        what :meth:`isStageComplete` counts.  A no-op returning ``None`` when
        the source is missing / not a segmentation, or no assignments are
        given.
        """
        if sourceSegmentationNode is None or not sourceSegmentationNode.IsA(
            "vtkMRMLSegmentationNode"
        ):
            return None
        if not assignments:
            return None

        # Exactly one canonical node: demote any prior canonical before
        # promoting the loaded one.
        existing = self._findCanonicalSegmentation()
        if existing is not None and existing is not sourceSegmentationNode:
            existing.SetAttribute(ROLE_ATTRIBUTE, None)

        sourceSegmentationNode.SetAttribute(ROLE_ATTRIBUTE, ROLE_CANONICAL)
        segmentsLogic = slicer.vtkSlicerSegmentationsModuleLogic
        for segmentId, (code, meaning) in assignments.items():
            self.tagSegmentWithSct(sourceSegmentationNode, segmentId, code, meaning)
            # Landing contract (ADR-0034 §Amendments): every landed segment
            # arrives "produced, under review" and carries its provenance.
            segment = sourceSegmentationNode.GetSegmentation().GetSegment(segmentId)
            segmentsLogic.SetSegmentStatus(segment, segmentsLogic.InProgress)
            segment.SetTag(SOURCE_TAG, SOURCE_IMPORTED)
        # Self-heal the checklist on the adopted canonical: the structures
        # the import did not cover get their pre-seeded empty rows.
        self.ensureExpectedStructures(sourceSegmentationNode)
        # Give the canonical segments a 3D closed-surface representation + make
        # them visible, so the anatomy renders through to Planning (#539) --
        # otherwise the main 3D view is empty entering Stage 4.
        self.ensureSurfaceRepresentation(sourceSegmentationNode)
        # The canonical import is the explicit human action completing Stage 2
        # (ADR-0023 Stage-2 hand-off), so it also computes the composed
        # distance map Stage 4 consumes (ADR-0031: the map is the resection
        # plan's input) -- Planning then opens with the map ready.
        self.ensureDistanceMap(sourceSegmentationNode)
        return sourceSegmentationNode

    #: Downsampling applied to the auto-computed distance map.  A full-res
    #: 4-channel float map of a 512-cubed CT is on the order of a gigabyte;
    #: halving each axis keeps the memory footprint workable while remaining
    #: adequate for the resection shader's margin bands.  A Stage-4 recompute
    #: control can re-expose the choice later (the v1 GUI had a spinbox).
    DISTANCE_MAP_DOWNSAMPLING = 2.0

    #: Name + attribute contract of the auto-computed distance-map volume
    #: (the tags the v1 distance-map selectors filtered on).
    DISTANCE_MAP_NODE_NAME = "DistanceMap"

    def ensureDistanceMap(self, segmentationNode):
        """Compute the composed distance map for the canonical segmentation.

        Resolves the Stage-1 reference volume (``LiverRole='PortalVenous'``,
        via :meth:`selectInputVolume`), resolves-or-creates the tagged
        ``vtkMRMLVectorVolumeNode`` output, and runs the per-channel
        signed-Maurer compute (``LiverSegmentationLib.distance_maps``).
        Returns the output node, or ``None`` when there is nothing to do --
        no segmentation, no reference volume, or no SCT-tagged channel
        resolves (graceful degradation; the canonical import itself must
        never fail on the map).
        """
        if segmentationNode is None:
            return None
        reference = self.selectInputVolume()
        if reference is None:
            return None

        from LiverSegmentationLib import distance_maps

        # Resolve-or-create the single tagged output so a re-import
        # recomputes in place instead of piling up volumes.
        output = None
        for node in slicer.util.getNodesByClass("vtkMRMLVectorVolumeNode"):
            if node.GetAttribute("DistanceMap") == "True":
                output = node
                break
        created = output is None
        if created:
            output = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLVectorVolumeNode", self.DISTANCE_MAP_NODE_NAME
            )

        computed = distance_maps.compute_distance_map_for_segmentation(
            segmentationNode,
            reference,
            output,
            downsampling_rate=self.DISTANCE_MAP_DOWNSAMPLING,
        )
        if computed is None and created:
            # No channel resolved (e.g. no SCT-tagged segments): drop the
            # node we minted rather than leaving an empty untagged shell.
            slicer.mrmlScene.RemoveNode(output)
            return None
        return computed

    def ensureSurfaceRepresentation(self, segmentationNode):
        """Create the 3D closed-surface representation + make it visible.

        Loaded segmentations arrive with only a binary-labelmap representation,
        so the 3D view shows nothing.  Generate the closed-surface
        representation and turn on 3D visibility so the canonical anatomy
        renders (ADR-0023 §Stage 2 hand-off; #539).  Tolerant of a ``None``
        node and of segments lacking a labelmap source (a no-op then).
        """
        if segmentationNode is None:
            return
        # "Closed surface" is the canonical name
        # (vtkSegmentationConverter closed-surface representation).
        segmentationNode.CreateClosedSurfaceRepresentation()
        if segmentationNode.GetDisplayNode() is None:
            segmentationNode.CreateDefaultDisplayNodes()
        displayNode = segmentationNode.GetDisplayNode()
        if displayNode is not None:
            displayNode.SetVisibility(True)
            displayNode.SetVisibility3D(True)

    def createScratchSegmentation(self):
        """Mint an orchestrator-private scratch segmentation node.

        Scratch nodes are also ``vtkMRMLSegmentationNode`` instances but carry
        ``role=scratch``; they hold a tool's pending output until the surgeon
        Accepts (ADR-0024 §Terminology "scratch node").
        """
        return self._createSegmentationWithRole(ROLE_SCRATCH, "Anatomy: Scratch")

    def accept(self, scratch):
        """Merge a scratch node's segments into the canonical node.

        The INTERNAL landing step the toolbar Run drives immediately after
        ``segment()`` returns (ADR-0034 §Amendments: no Accept button; the
        review boundary is the native per-segment status), under the
        ADR-0034 §Amendments landing contract: an
        incoming segment whose SCT code matches a pre-seeded EMPTY
        expected segment REPLACES that placeholder in
        place — same row position, re-applied SCT tag / vocabulary name /
        visual defaults — so the checklist order is stable and no
        duplicate rows accrue.  Every landed segment reads the native
        ``InProgress`` ("produced, under review") and carries its source
        tag.  The canonical-node count is unchanged; the scratch node is
        removed once its segments are copied.
        """
        if scratch is None or not scratch.IsA("vtkMRMLSegmentationNode"):
            raise ValueError("accept() requires a scratch vtkMRMLSegmentationNode")
        if scratch.GetAttribute(ROLE_ATTRIBUTE) != ROLE_SCRATCH:
            raise ValueError("accept() target is not a scratch-role segmentation")

        canonical = self.getOrCreateCanonicalSegmentation()
        scratchSegmentation = scratch.GetSegmentation()
        for segmentId in list(scratchSegmentation.GetSegmentIDs()):
            self._landSegment(
                canonical, scratchSegmentation, segmentId, SOURCE_TOTALSEG
            )
        slicer.mrmlScene.RemoveNode(scratch)
        # The Accept is the AI path's explicit human action growing the
        # canonical node (the import path's twin), so it runs the same two
        # post-merge steps: the 3D closed-surface representation (the main
        # 3D view is otherwise empty entering Stage 4) and the composed
        # distance map Stage 4 consumes (ADR-0031).  Both degrade gracefully
        # when their inputs are absent; the recompute lands the newly
        # accepted segment's channel in place.
        self.ensureSurfaceRepresentation(canonical)
        self.ensureDistanceMap(canonical)
        # Per-segment 3D opacity lives on the DISPLAY NODE and does not
        # travel with the copied segments (colour does): re-apply the
        # structure visual defaults on the CANONICAL node post-merge.
        self.applyVisualDefaults(canonical)
        return canonical

    def _landSegment(self, canonicalNode, sourceSegmentation, segmentId, source):
        """Land one incoming segment on the canonical node.

        The ADR-0034 §Amendments landing contract shared by the accept
        merge loop: when the incoming segment's SCT code matches a
        pre-seeded EMPTY expected segment (no voxel data and no provenance
        source tag — emptiness, not status, marks the replaceable
        placeholder: the async run path flips targeted rows to
        ``InProgress`` at enqueue, ADR-0034 §Decision 5), the placeholder
        is removed, the incoming segment copied in, and the placeholder's
        row position restored via the ``vtkSegmentation`` reorder API (the
        same ``GetSegmentIndex``/``SetSegmentIndex`` pair the stock table's
        move up/down uses).  Returns the landed segment id, or ``None``
        when the copy failed.

        The landed identity — native ``InProgress`` status, the source tag
        (kept when the segment already carries provenance from where it was
        created), and on replacement the re-asserted SCT tag / vocabulary
        title / default colour — is written on the INCOMING segment BEFORE
        the copy: segment tags travel with the deep copy, and a live
        ``qMRMLSegmentsTableView`` bound to the canonical node echoes its
        row state back into segments (``qMRMLSegmentsModel`` itemChanged ->
        ``SetSegmentStatus``), which clobbers a status written in the same
        event cascade as the structural insert.
        """
        segmentsLogic = slicer.vtkSlicerSegmentationsModuleLogic
        canonicalSegmentation = canonicalNode.GetSegmentation()

        incoming = sourceSegmentation.GetSegment(segmentId)
        code = self._expectedCodeForSegment(incoming)

        placeholderIndex = -1
        if code is not None:
            placeholderId = _findSctSegmentId(canonicalNode, code)
            placeholder = (
                canonicalSegmentation.GetSegment(placeholderId)
                if placeholderId is not None
                else None
            )
            # Replaceable = a pre-seeded checklist row: EMPTY (no voxel
            # data) and without provenance (every landed/imported segment
            # carries the source tag; a previously landed empty result must
            # never be silently replaced -- multifocal lesions land as
            # SEPARATE segments sharing one SCT code).
            if (
                placeholder is not None
                and _segmentIsEmpty(placeholder)
                and not _segmentTag(placeholder, SOURCE_TAG)
            ):
                placeholderIndex = canonicalSegmentation.GetSegmentIndex(
                    placeholderId
                )
                canonicalSegmentation.RemoveSegment(placeholderId)

        if placeholderIndex >= 0:
            # Placeholder replacement: re-assert the checklist row identity
            # (SCT tag + vocabulary title + default colour; the 3D opacity
            # is display-node state applyVisualDefaults re-applies on the
            # receiving node post-merge).
            incoming.SetTag(
                TERMINOLOGY_ENTRY_TAG,
                _sctTerminologyTag(code, self._structureMeaning(code)),
            )
            incoming.SetName(self._structureTitle(code))
            defaults = STRUCTURE_VISUAL_DEFAULTS.get(str(code))
            if defaults is not None:
                incoming.SetColor(*defaults["color"])
        segmentsLogic.SetSegmentStatus(incoming, segmentsLogic.InProgress)
        if not _segmentTag(incoming, SOURCE_TAG):
            incoming.SetTag(SOURCE_TAG, source)

        before = set(canonicalSegmentation.GetSegmentIDs())
        canonicalSegmentation.CopySegmentFromSegmentation(
            sourceSegmentation, segmentId
        )
        landedIds = [
            landedId
            for landedId in canonicalSegmentation.GetSegmentIDs()
            if landedId not in before
        ]
        if not landedIds:
            return None
        landedId = landedIds[0]
        if placeholderIndex >= 0:
            canonicalSegmentation.SetSegmentIndex(landedId, placeholderIndex)
        return landedId

    def _expectedCodeForSegment(self, segment):
        """The structure-vocabulary SCT code a segment carries, or ``None``.

        Reads the segment's ``TerminologyEntry`` tag for one of the
        ``STRUCTURE_TABS`` codes (the ``^<code>^`` marker every reader in
        the repo greps).  Segments outside the expected vocabulary land
        as plain appended rows.
        """
        text = _segmentTag(segment, TERMINOLOGY_ENTRY_TAG)
        for _title, code in STRUCTURE_TABS:
            if f"^{code}^" in text:
                return code
        return None

    def _structureTitle(self, sctCode):
        """The structure-vocabulary row title for an SCT code."""
        for title, code in STRUCTURE_TABS:
            if str(code) == str(sctCode):
                return title
        return str(sctCode)

    def applyVisualDefaults(self, segmentationNode):
        """Apply per-structure colour + 3D opacity to every tagged segment.

        Reads each segment's SCT type code back off its ``TerminologyEntry``
        tag and applies ``STRUCTURE_VISUAL_DEFAULTS``.  Idempotent; a no-op
        for untagged segments, unknown codes, or a ``None`` node.  Needed
        wherever segments CHANGE NODES: per-segment opacity is display-node
        state, so a merge (Accept) or import must re-apply it on the
        receiving node.
        """
        if segmentationNode is None:
            return
        if segmentationNode.GetDisplayNode() is None:
            segmentationNode.CreateDefaultDisplayNodes()
        display = segmentationNode.GetDisplayNode()
        segmentation = segmentationNode.GetSegmentation()
        for segmentId in list(segmentation.GetSegmentIDs()):
            segment = segmentation.GetSegment(segmentId)
            text = vtk.mutable("")
            segment.GetTag(TERMINOLOGY_ENTRY_TAG, text)
            for code, defaults in STRUCTURE_VISUAL_DEFAULTS.items():
                if f"^{code}^" in str(text):
                    segment.SetColor(*defaults["color"])
                    if display is not None:
                        display.SetSegmentOpacity3D(segmentId, defaults["opacity3d"])
                    break

    #
    # Per-structure Run (ADR-0024 §"Per-structure micro-workflows").  The
    # toolbar's Run drives the AI backend on the Stage-1 input volume and
    # lands its output in a single internal scratch node; the widget then
    # lands that on the canonical node via accept() in the same gesture
    # (ADR-0034 §Amendments: the review boundary is the native per-segment
    # status, not a node-level Accept — and Reject is removed entirely).
    #

    def selectInputVolume(self):
        """Return the Stage-1 portal-venous-phase working volume, or None.

        Stage 2 segments the volume Stage 1 flags ``LiverRole='PortalVenous'``
        (ADR-0024 Stage-1/Stage-2 hand-off), not an arbitrary scalar volume.
        """
        for node in slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode"):
            if node.GetAttribute(LIVER_ROLE_ATTRIBUTE) == LIVER_ROLE_PORTAL_VENOUS:
                return node
        return None

    def segment(self, volume, sctTarget, progressCallback=None):
        """Run the AI backend for one structure, landing output in scratch.

        The orchestrator-owned entry point the toolbar's Run drives.  All
        TotalSegmentator invocation funnels through the single
        :meth:`_runTotalSegmentator` seam so CI can stub it (a real inference
        needs a multi-GB model + GPU).  ``progressCallback`` receives the
        backend's output lines (the toolbar's status surface).  Returns the
        scratch ``vtkMRMLSegmentationNode`` holding the structure's pending
        output (ADR-0024 §"Output contract") — the widget lands it via
        :meth:`accept` in the same gesture; raises the wrapper's
        ``TotalSegmentatorNotInstalled`` when the backend is unavailable so
        the widget can route the surgeon to the manual path.
        """
        return self._runTotalSegmentator(
            volume, sctTarget, progressCallback=progressCallback
        )

    def _runTotalSegmentator(self, volume, sctTarget, progressCallback=None):
        """The single monkeypatchable backend-invocation seam.

        Kept import-pure: the TotalSegmentator backend is reached only through
        the lazy-install wrapper's call path (ADR-0024 §"Lazy install"), never
        imported at module-import time.  CI stubs this method (or the
        wrapper's ``runInference``) to exercise the Run/landing bookkeeping
        without an inference.

        The real wiring: export the input volume to a temp NIfTI, run the
        backend OUT OF PROCESS (GUI stays alive; progress streams to the
        callback), then import each per-label output file into the scratch
        node as an SCT-tagged segment (the LabelToSCT bridge mapping,
        ADR-0011, mirrored by the wrapper's ``INFERENCE_TARGETS``).
        """
        import shutil
        import tempfile

        wrapper = _totalSegmentatorWrapper()
        if not wrapper.ensureBackendInstalled():
            raise wrapper.TotalSegmentatorNotInstalled(
                "TotalSegmentator backend is not available; use the Segment "
                "Editor manual path or retry the install."
            )

        spec = wrapper.INFERENCE_TARGETS.get(str(sctTarget))
        if spec is None:
            raise ValueError(f"no TotalSegmentator target for SCT {sctTarget!r}")
        meaning = self._structureMeaning(sctTarget)

        workdir = tempfile.mkdtemp(prefix="LiverSegTotalSeg-")
        try:
            input_path = os.path.join(workdir, "input.nii.gz")
            if not slicer.util.saveNode(volume, input_path):
                raise RuntimeError("could not export the input volume for inference")
            output_dir = os.path.join(workdir, "out")
            os.makedirs(output_dir, exist_ok=True)

            wrapper.runInference(
                input_path, output_dir, sctTarget, progress_callback=progressCallback
            )

            scratch = self.createScratchSegmentation()
            imported = 0
            for label in spec["labels"]:
                label_path = os.path.join(output_dir, f"{label}.nii.gz")
                if not os.path.isfile(label_path):
                    continue
                imported += self._importLabelFileAsSegment(
                    scratch, label_path, sctTarget, meaning
                )
            if imported == 0:
                raise RuntimeError(
                    "TotalSegmentator produced no output for "
                    f"{meaning!r} (labels {spec['labels']})."
                )
            # 3D preview so the surgeon can judge the result before Accept.
            self.ensureSurfaceRepresentation(scratch)
            return scratch
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def importJobOutput(self, outputDir, structures):
        """Import a finished queue job's label files into a scratch node.

        The async landing seam (ADR-0034 §Decision 5): the job queue's child
        writes the same per-structure label files ``_runTotalSegmentator``
        consumes (``<outputDir>/<label>.nii.gz`` per the wrapper's
        ``INFERENCE_TARGETS``); this imports every produced file for the
        job's coalesced ``structures`` into ONE internal scratch node —
        SCT-tagged and provenance-stamped by ``_importLabelFileAsSegment``,
        3D preview attached — which the widget lands via :meth:`accept`.
        Returns ``None`` (and leaves no node behind) when nothing was
        produced; missing individual label files are skipped, never fatal
        (a coalesced structure may have joined the job after its child
        started).
        """
        wrapper = _totalSegmentatorWrapper()
        scratch = self.createScratchSegmentation()
        imported = 0
        for code in structures:
            spec = wrapper.INFERENCE_TARGETS.get(str(code))
            if spec is None:
                continue
            meaning = self._structureMeaning(code)
            for label in spec["labels"]:
                label_path = os.path.join(outputDir, f"{label}.nii.gz")
                if not os.path.isfile(label_path):
                    continue
                imported += self._importLabelFileAsSegment(
                    scratch, label_path, code, meaning
                )
        if imported == 0:
            slicer.mrmlScene.RemoveNode(scratch)
            return None
        self.ensureSurfaceRepresentation(scratch)
        return scratch

    def _structureMeaning(self, sctTarget):
        """Human meaning for a structure-vocabulary SCT code."""
        meanings = {
            SCT_LIVER_CODE: "Liver",
            SCT_PORTAL_VEIN_CODE: "Portal vein",
            SCT_HEPATIC_VEIN_CODE: "Hepatic vein",
            SCT_MASS_CODE: "Mass",
        }
        return meanings.get(str(sctTarget), str(sctTarget))

    def _importLabelFileAsSegment(self, scratch, label_path, code, meaning):
        """Import one backend label file into ``scratch``; return segments added."""
        labelmap = slicer.util.loadLabelVolume(label_path)
        if labelmap is None:
            return 0
        try:
            before = scratch.GetSegmentation().GetNumberOfSegments()
            ok = slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(
                labelmap, scratch
            )
            after = scratch.GetSegmentation().GetNumberOfSegments()
            if not ok or after <= before:
                return 0
            for index in range(before, after):
                segment_id = scratch.GetSegmentation().GetNthSegmentID(index)
                segment = scratch.GetSegmentation().GetSegment(segment_id)
                segment.SetName(meaning)
                self.tagSegmentWithSct(scratch, segment_id, code, meaning)
                # Provenance is stamped where the segment is born so it
                # travels with the copy into the canonical node on Accept
                # (ADR-0034 §Amendments source tag).
                segment.SetTag(SOURCE_TAG, SOURCE_TOTALSEG)
            return after - before
        finally:
            slicer.mrmlScene.RemoveNode(labelmap)

    #
    # SCT tagging (ADR-0011 dispatch; bridge under repo-root
    # Resources/Terminology/LabelToSCT/).
    #

    def tagSegmentWithSct(self, segmentationNode, segmentId, code, meaning):
        """Tag ``segmentId`` with an SCT-coded terminology entry.

        Writes the standard ``TerminologyEntry`` segment tag with an SCT triple
        in the type position, which is what :meth:`isStageComplete` and
        downstream stages read.  ADR-0011 owns the label-to-SCT dispatch; this
        helper applies the resolved code.
        """
        segment = segmentationNode.GetSegmentation().GetSegment(segmentId)
        if segment is None:
            raise ValueError(f"no segment '{segmentId}' in segmentation")
        segment.SetTag(TERMINOLOGY_ENTRY_TAG, _sctTerminologyTag(code, meaning))
        # Apply the structure's visual defaults at the same funnel: every
        # tagged segment (AI accept OR import) gets its v1-parity colour, and
        # the parenchyma its translucent 3D opacity, instead of the generic
        # import green.
        defaults = STRUCTURE_VISUAL_DEFAULTS.get(str(code))
        if defaults is not None:
            segment.SetColor(*defaults["color"])
            display = segmentationNode.GetDisplayNode()
            if display is not None:
                display.SetSegmentOpacity3D(segmentId, defaults["opacity3d"])

    #
    # Internal helpers.
    #

    def _createSegmentationWithRole(self, role, name):
        """Add a role-flagged segmentation node under the Anatomy folder.

        Shared scratch/canonical creation path: stock
        ``vtkMRMLSegmentationDisplayNode`` (no per-module display node, ADR-0024
        §Conformance / Alternative A), the ``LiverSegmentation.Role`` attribute,
        and Subject Hierarchy collection.
        """
        node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", name)
        node.SetAttribute(ROLE_ATTRIBUTE, role)
        node.CreateDefaultDisplayNodes()
        self._collectUnderAnatomyFolder(node)
        return node

    def _findCanonicalSegmentation(self):
        """Return the canonical-role segmentation node, or None.

        ``slicer.util.getNodesByClass`` returns a plain Python list (the
        underlying vtkCollection is released for us), avoiding the manual
        ``UnRegister`` dance.
        """
        for node in slicer.util.getNodesByClass("vtkMRMLSegmentationNode"):
            if node.GetAttribute(ROLE_ATTRIBUTE) == ROLE_CANONICAL:
                return node
        return None

    def _collectUnderAnatomyFolder(self, node):
        """Reparent ``node`` under the "Anatomy" Subject Hierarchy folder.

        Per-stage Subject Hierarchy discipline (ADR-0023 §"Subject Hierarchy
        management convention"): each stage collects its nodes under a named
        folder.  Idempotent — reuses the folder if it already exists.  The
        lookup / lazy-create / reparent dance is centralised in the shared
        wrapped-C++ ``vtkSlicerSubjectHierarchyFolders`` utility (ADR-0004
        reasoned exception: wrapped C++ so the C++ module logics and this
        Python caller share one binary-identical implementation).
        Best-effort: a missing SH plugin (headless contexts) makes the
        utility a no-op and must not break node creation.
        """
        try:
            from vtkSlicerSubjectHierarchyFoldersPython import (
                vtkSlicerSubjectHierarchyFolders,
            )
        except ImportError as exc:  # noqa: BLE001 — headless / kit not loaded
            logging.debug("Subject Hierarchy folder utility unavailable: %s", exc)
            return

        vtkSlicerSubjectHierarchyFolders.CollectUnderFolder(
            slicer.mrmlScene,
            node,
            vtkSlicerSubjectHierarchyFolders.GetAnatomyFolderName(),
        )


class LiverSegmentationTest(ScriptedLoadableModuleTest):
    """Slicer self-test entry point.

    Behaviour-pinning invariants live under ``Testing/Python/`` (pytest);
    this class keeps the standard scripted-module self-test surface available.
    """

    def setUp(self):
        slicer.mrmlScene.Clear()

    def runTest(self):
        self.setUp()

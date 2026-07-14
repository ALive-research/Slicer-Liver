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
  * SCT-tags segments with the ADR-0011 structure vocabulary (import
    correspondences are stated explicitly in the Import… dialog — there
    is no auto-match);
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

import ctk
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
#: Per-structure SNOMED-CT type codes (ADR-0024 §"Output contract"; the
#: ADR-0011 structure vocabulary).
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
#: The Import-as combo's default entry — every import correspondence is
#: stated explicitly; an unmapped source segment is skipped, never
#: auto-matched (ADR-0034 §Amendments).
IMPORT_SKIP_LABEL = "— skip —"
#: Suffix annotating an Import-as entry whose checklist row already landed.
#: The entry stays selectable: picking it lands an EXTRA same-code row (the
#: never-overwrite rule) — the multifocal shape.
IMPORT_ALREADY_PRESENT_SUFFIX = " (already present)"
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
STATUS_REVIEW = ("●", "Review")
STATUS_CONFIRMED = ("✓", "Confirmed")
STATUS_FLAGGED = ("⚑", "Flagged")
STATUS_MARKED_ABSENT = ("∅", "Marked absent")

#: Curated effect list for the embedded Segment Editor — the AI-mask-
#: correction set (ADR-0034 §Amendments item 4).  Everything outside this
#: order is hidden (``unorderedEffectsVisible`` off): the embedded editor
#: corrects produced masks; it is not a from-scratch segmentation surface.
EMBEDDED_EDITOR_EFFECTS = ("Paint", "Erase", "Scissors", "Islands", "Smoothing")


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
    representation.  The landing contract keys on emptiness (plus missing
    provenance), never on status: the status column is the surgeon's
    channel — an EMPTY ``Completed`` row is the absence attestation — so
    status cannot mark a row as a replaceable placeholder.

    Emptiness is LABEL-AWARE: pre-seeded segments SHARE one binary-labelmap
    layer (the stock ``AddEmptySegment`` shape), so a content write to one
    segment through the Segment Editor funnel grows the shared image's
    extent for every sharer.  A segment is empty iff NO voxel carries its
    own label value — the object-level extent says nothing about a single
    sharer.
    """
    if segment is None:
        return True
    name = (
        slicer.vtkSegmentationConverter.GetSegmentationBinaryLabelmapRepresentationName()
    )
    labelmap = segment.GetRepresentation(name)
    if labelmap is None:
        return True
    if hasattr(labelmap, "IsEmpty") and labelmap.IsEmpty():
        return True
    extent = labelmap.GetExtent()
    if extent[0] > extent[1] or extent[2] > extent[3] or extent[4] > extent[5]:
        return True
    scalars = labelmap.GetPointData().GetScalars()
    if scalars is None:
        return True
    from vtk.util.numpy_support import vtk_to_numpy

    return not bool((vtk_to_numpy(scalars) == segment.GetLabelValue()).any())


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


def _landedSctSegmentCount(segmentationNode, sctCode):
    """Same-code rows that already LANDED (non-empty or provenance-carrying).

    A pre-seeded checklist placeholder (empty, provenance-free) does not
    count — and neither does the empty-``Completed`` absence attestation:
    "landed" means content arrived (voxels) or a tool/import stamped its
    provenance source tag.  Drives BOTH the Import-as combo's
    "(already present)" annotation and the multifocal title numbering of
    the explicit-correspondence import (ADR-0034 §Amendments).
    """
    if segmentationNode is None:
        return 0
    segmentation = segmentationNode.GetSegmentation()
    count = 0
    for segmentId in list(segmentation.GetSegmentIDs()):
        segment = segmentation.GetSegment(segmentId)
        if f"^{sctCode}^" not in _segmentTag(segment, TERMINOLOGY_ENTRY_TAG):
            continue
        if not _segmentIsEmpty(segment) or _segmentTag(segment, SOURCE_TAG):
            count += 1
    return count


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


class LiverSegmentationWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    """Stage-2 surgeon panel — the anatomy segments table + selection toolbar.

    ADR-0034 §Amendments: the panel is a configured stock
    ``qMRMLSegmentsTableView`` over the single canonical node, minted (or
    adopted) on setup so the pre-seeded four-row checklist is visible the
    moment Stage 2 opens.  A selection-scoped toolbar under the table acts
    on the SELECTED rows: Run TotalSegmentator (enqueues every selected
    structure into the §Decision 5 job queue; results land on the
    canonical node as native ``InProgress`` — no Accept/Reject machinery;
    the surgeon's confirm is the status-cell click) and Edit (expands the
    EMBEDDED ``qMRMLSegmentEditorWidget`` section under the toolbar and
    syncs the selected row — ADR-0034 §Amendments item 4; the editor
    drives its own non-singleton editor node with a curated effect list,
    pinned to the canonical node + the Stage-1 PortalVenous volume).
    Editing a ``Completed`` segment demotes it to ``InProgress`` (the
    §Decision 2 staleness rule, hooked at segmentation level so stock-
    module edits are covered too).
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
        # Async run path (ADR-0034 §Decision 5): the QProcess job queue plus
        # the widget's per-job bookkeeping — the structure codes each job
        # covers (fanned into per-structure progress rows) and one progress
        # box per queued/running job.  Built in setup().
        self._jobQueue = None
        self._pendingJobs = {}
        self._jobRows = {}
        # Embedded Segment Editor (ADR-0034 §Amendments item 4): the stock
        # qMRMLSegmentEditorWidget in a collapsible section, its OWN
        # non-singleton editor node, and the vtkSegmentation currently
        # observed for the demote-on-edit staleness rule.  Built in setup().
        self._embeddedEditor = None
        self._editorSection = None
        self._editorNode = None
        self._observedSegmentation = None
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)

    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)

        self.logic = LiverSegmentationLogic()
        self._jobQueue = self._buildJobQueue()

        self.layout.addWidget(self._buildSegmentsTable())
        self.layout.addWidget(self._buildSelectionToolbar())
        self.layout.addWidget(self._buildEmbeddedEditor())
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
        self._bindEmbeddedEditor()
        self._observeCanonicalSegmentation()
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
            node = self.logic._findCanonicalSegmentation()
            if view.segmentationNode() is node:
                # Already bound — a redundant rebind would churn the
                # view's model (and its selection) on every scene event.
                return
            view.setSegmentationNode(node)
        except ValueError:
            # PythonQt raises when the Qt view was destroyed with a parent
            # tree while this Python widget (and its scene observers) is
            # still alive — e.g. a host shell disposing the composed page.
            # Drop the stale reference; the observers go with cleanup().
            self._segmentsTable = None

    def _buildEmbeddedEditor(self):
        """Build the embedded Segment Editor section (ADR-0034 §Amendments 4).

        A STOCK ``qMRMLSegmentEditorWidget`` inside a ``ctkCollapsibleButton``
        directly under the table/toolbar, COLLAPSED by default (the table is
        the primary surface; Edit is the opt-in gesture) — the MONAILabel /
        SegmentationReview idiom replacing the jump-to-module path.  The
        editor drives its OWN non-singleton ``vtkMRMLSegmentEditorNode`` so
        embedded edits never clobber the stock Segment Editor module's
        singleton state.  Its inputs are PINNED contracts, not user choices:
        the node-selector rows and the switch-to-Segmentations button are
        hidden; ``_bindEmbeddedEditor`` supplies the canonical node + the
        Stage-1 PortalVenous volume.  Effects are the curated AI-mask-
        correction set (``EMBEDDED_EDITOR_EFFECTS``), everything else hidden.
        """
        import qSlicerSegmentationsModuleWidgetsPythonQt

        section = ctk.ctkCollapsibleButton()
        section.text = "Edit selected segment"
        section.setObjectName("EmbeddedEditorSection")
        section.collapsed = True
        column = qt.QVBoxLayout(section)

        editor = qSlicerSegmentationsModuleWidgetsPythonQt.qMRMLSegmentEditorWidget()
        editor.setObjectName("EmbeddedSegmentEditor")
        editor.setMaximumNumberOfUndoStates(10)
        editor.setEffectNameOrder(list(EMBEDDED_EDITOR_EFFECTS))
        editor.unorderedEffectsVisible = False
        editor.setSegmentationNodeSelectorVisible(False)
        editor.setSourceVolumeNodeSelectorVisible(False)
        editor.setSwitchToSegmentationsButtonVisible(False)
        # Row lifecycle belongs to the ANATOMY segments table above; the
        # editor's own add/remove buttons would bypass the pre-seeded
        # checklist contract (ADR-0034 §Amendments).
        editor.setAddRemoveSegmentButtonsVisible(False)
        # The editor embeds its OWN qMRMLSegmentsTableView -- redundant
        # beside the anatomy table that already drives the selection
        # (maintainer live-test finding).  No Q_PROPERTY exposes it, so
        # hide the named child frame (the .ui wraps the view in
        # SegmentsTableResizableFrame; falling back to the view itself
        # keeps this resilient to upstream .ui reshuffles).
        for childName in ("SegmentsTableResizableFrame", "SegmentsTableView"):
            child = editor.findChild(qt.QWidget, childName)
            if child is not None:
                child.setVisible(False)
                break
        # Parameter node BEFORE the scene, so the automatic selections made
        # when the scene lands are stored on OUR node (the stock module's
        # setup order).
        editor.setMRMLSegmentEditorNode(self._ensureEditorParameterNode())
        editor.setMRMLScene(slicer.mrmlScene)
        column.addWidget(editor)

        self._embeddedEditor = editor
        self._editorSection = section
        return section

    def embeddedEditor(self):  # noqa: N802 - Slicer/Qt verb convention
        return getattr(self, "_embeddedEditor", None)

    def embeddedEditorSection(self):  # noqa: N802 - Slicer/Qt verb convention
        return getattr(self, "_editorSection", None)

    def _ensureEditorParameterNode(self):
        """Get-or-mint the embedded editor's OWN parameter node.

        A plain (non-singleton) ``vtkMRMLSegmentEditorNode`` — deliberately
        NOT the stock Segment Editor module's ``SegmentEditor`` singleton, so
        the embedded editor's segmentation/volume/effect state stays private
        (ADR-0034 §Amendments item 4).  Re-minted lazily when a scene close
        reclaimed the previous one (the Edit gesture re-ensures it).
        """
        node = self._editorNode
        if node is not None and node.GetScene() is not None:
            return node
        node = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLSegmentEditorNode", "LiverSegmentationEditor"
        )
        self._editorNode = node
        return node

    def _bindEmbeddedEditor(self):
        """(Re-)pin the embedded editor's inputs from the scene state.

        Pure READ path (the ``_bindSegmentsTable`` discipline): the
        segmentation input is the canonical node when one exists (else
        unbound), the source volume is the Stage-1 PortalVenous working
        volume (``logic.selectInputVolume``) — re-resolved on every scene
        change like the table bind, never minting anything.
        """
        editor = getattr(self, "_embeddedEditor", None)
        if editor is None or self.logic is None:
            return
        try:
            canonical = self.logic._findCanonicalSegmentation()
            if editor.segmentationNode() is not canonical:
                editor.setSegmentationNode(canonical)
            source = self.logic.selectInputVolume()
            if editor.sourceVolumeNode() is not source:
                editor.setSourceVolumeNode(source)
        except ValueError:
            # PythonQt raises when the Qt widget was destroyed with a host
            # parent tree while this Python widget is still alive (the
            # _bindSegmentsTable case); drop the stale references.
            self._embeddedEditor = None
            self._editorSection = None

    def _observeCanonicalSegmentation(self):
        """(Re-)observe the canonical node's segmentation for content edits.

        The demote-on-edit hook (ADR-0034 §Decision 2 staleness rule, as
        amended) rides ``vtkSegmentation::SourceRepresentationModified`` —
        the CONTENT-change event every Segment Editor effect apply funnels
        through (``vtkSegmentationModifier`` invokes it with the segment id
        as call data), covering the embedded editor AND stock-module edits.
        Observing at segmentation level (not the editor) keeps the rule a
        property of the canonical node's data, not of one editing surface.
        Swapped, never stacked, when the canonical node changes.
        """
        node = (
            self.logic._findCanonicalSegmentation() if self.logic is not None else None
        )
        segmentation = node.GetSegmentation() if node is not None else None
        if segmentation is self._observedSegmentation:
            return
        if self._observedSegmentation is not None:
            self.removeObserver(
                self._observedSegmentation,
                slicer.vtkSegmentation.SourceRepresentationModified,
                self._onSegmentContentModified,
            )
        self._observedSegmentation = segmentation
        if segmentation is not None:
            self.addObserver(
                segmentation,
                slicer.vtkSegmentation.SourceRepresentationModified,
                self._onSegmentContentModified,
            )

    def _onSegmentContentModified(self, caller, event, segmentId=None):
        """Demote an edited ``Completed`` segment to ``InProgress``.

        ADR-0034 §Decision 2 (as amended): an edited confirm is stale and
        re-enters review.  ``SourceRepresentationModified`` arrives with the
        modified segment's id as call data on the editor-apply funnel; other
        emitters pass no usable id (a raw representation-object Modified
        forwards null) — those are ignored rather than guessed at, so
        nothing is ever demoted on attribution-free events.  Status-tag
        writes (``SetSegmentStatus`` — including this demotion itself) fire
        only ``SegmentModified``, never this event, so the hook cannot
        recurse.
        """
        if not segmentId:
            return
        segment = caller.GetSegment(segmentId) if caller is not None else None
        if segment is None:
            return
        segmentsLogic = slicer.vtkSlicerSegmentationsModuleLogic
        if segmentsLogic.GetSegmentStatus(segment) != segmentsLogic.Completed:
            return
        segmentsLogic.SetSegmentStatus(segment, segmentsLogic.InProgress)

    # VTK call-data plumbing for the observer above: vtkPythonCommand reads
    # the callback's ``CallDataType`` attribute; ``"string0"`` is its
    # null-terminated-string form (what ``vtk.calldata_type(vtk.VTK_STRING)``
    # would declare).  Set as a plain attribute so module IMPORT stays pure —
    # the import-purity probes stub ``vtk`` without the decorator helper.
    _onSegmentContentModified.CallDataType = "string0"

    def _buildSelectionToolbar(self):
        """Build the selection-scoped toolbar + the per-job progress list.

        ADR-0034 §Amendments: gestures act on the SELECTED table rows, not
        on per-row button walls.  Run enqueues every selected structure
        (structures sharing a backend task coalesce into one child;
        multi-select covers the run-everything gesture); Edit expands the
        embedded Segment Editor section and syncs the first selected row
        into it (§Amendments item 4 — the jump-to-module path is retired);
        Import… opens the minimal source picker routing a loaded
        segmentation through the unified landing path (§Decision 2: the
        import path unifies — the separate load section is retired).
        Absence is attested through the table's own status gesture (empty
        row set ``Completed``), so no dedicated button.  Under the buttons,
        one progress row PER queued/running job — the job's text embedded
        IN its bar, a per-job cancel (✕) beside it — plus one shared status
        label for queue/backend lines.
        """
        box = qt.QWidget()
        column = qt.QVBoxLayout(box)
        column.setContentsMargins(0, 0, 0, 0)

        row = qt.QHBoxLayout()
        self._runButton = qt.QPushButton(self._RUN_LABEL_BASE)
        self._editButton = qt.QPushButton("Edit")
        self._importButton = qt.QPushButton("Import…")
        self._importButton.setObjectName("ImportSegmentationButton")
        self._importButton.setToolTip(
            "Import a loaded segmentation's segments into the anatomy "
            "table (they land under review)."
        )
        row.addWidget(self._runButton)
        row.addWidget(self._editButton)
        row.addWidget(self._importButton)
        row.addStretch(1)
        column.addLayout(row)

        self._jobListBox = qt.QWidget()
        self._jobListLayout = qt.QVBoxLayout(self._jobListBox)
        self._jobListLayout.setContentsMargins(0, 0, 0, 0)
        column.addWidget(self._jobListBox)

        self._statusLabel = qt.QLabel("Idle")
        column.addWidget(self._statusLabel)

        self._runButton.connect("clicked()", self.onRunSelectedStructures)
        self._editButton.connect("clicked()", self.onEditSelectedSegment)
        self._importButton.connect("clicked()", self.onImportSegmentation)
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
        """Schedule a selection re-resolve AFTER the gesture settles.

        The reporting signal (``clicked`` / ``currentChanged``) fires
        mid-gesture, before the selection model reflects a ctrl-click
        deselect; a zero-interval single-shot re-reads the REAL selection
        once the event cascade completes, so neither the Run label nor the
        embedded editor's current segment lags a gesture behind.
        """
        qt.QTimer.singleShot(0, self._onSelectionSettled)

    def _onSelectionSettled(self):
        """Fan the settled selection out to its consumers."""
        self._updateRunButton()
        self._syncEditorToSelection()

    def _syncEditorToSelection(self):
        """Set the embedded editor's current segment from the table selection.

        The FIRST selected row becomes the editor's current segment
        (ADR-0034 §Amendments item 4).  A no-op when nothing is selected
        (the editor keeps its segment) or while the editor is unbound.
        """
        editor = getattr(self, "_embeddedEditor", None)
        view = getattr(self, "_segmentsTable", None)
        if editor is None or view is None:
            return
        try:
            if editor.segmentationNode() is None:
                return
            selected = list(view.selectedSegmentIDs())
            if selected:
                editor.setCurrentSegmentID(selected[0])
        except ValueError:
            # The deferred re-resolve can outlive the Qt widgets (PythonQt
            # raises on a deleted C++ object); nothing left to sync.
            pass

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

        The surgeon flow (ADR-0034 §Amendments): select rows -> Run -> the
        job queue runs the minimal set of backend children (structures
        sharing a task coalesce) and the finish callback lands the results
        on the canonical node.  Segment statuses are NOT touched at enqueue
        — jobs can abort, and the queued/running state is visible through
        the per-job progress rows; the native ``InProgress`` flip (and the
        staleness demote of a re-run ``Completed`` row) happens at LANDING,
        when produced output actually exists.  The GUI stays responsive
        throughout — no blocking loop, no ``processEvents``.
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
        """Group by backend task and enqueue (ADR-0034 §4/§5).

        Grouping happens HERE (one enqueue per task with the full structure
        set) so a single gesture's structures share one child from the
        start; the queue's key-level coalescing then absorbs repeat gestures
        on an already-queued task (a task whose child is already RUNNING
        gets a NEW sequential job — the running command line is frozen).
        Segment statuses are NOT written at enqueue: jobs can be cancelled
        or fail, and nothing was produced yet — the running state is the
        per-job progress rows' to show, and the native ``InProgress`` flip
        happens at LANDING (``_landSegment``).  The covered codes are
        recorded per job so the progress rows fan out one bar per
        structure.

        ORDER MATTERS: the per-job bookkeeping, the progress rows, and the
        "Queued…" line are all put up BEFORE any enqueue.  The command
        builder runs synchronously inside ``enqueue`` (export precondition
        failures raise on the spot), so its failure path re-enters
        ``_onJobFinished`` mid-gesture — the rows must already exist for
        that path to retire, and the gesture's own "Queued…" line must not
        clobber the failure message afterwards.
        """
        from LiverSegmentationLib.SegmentationJobQueue import jobKey

        wrapper = _totalSegmentatorWrapper()
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
            covered = self._pendingJobs.setdefault(key, set())
            for code in taskCodes:
                covered.add(code)
                names.append(self.logic._structureTitle(code))
            # Busy surface: one progress row PER STRUCTURE the job covers
            # (coalesced execution, fanned-out UI); the finish callback
            # retires each structure's row with its own job.
            self._ensureJobRows(key)
        self._statusLabel.setText(
            "Queued TotalSegmentator: " + ", ".join(names) + "…"
        )
        for task, taskCodes in byTask.items():
            self._jobQueue.enqueue(task, volume.GetID(), taskCodes)

    #
    # Per-STRUCTURE progress rows.  The queue coalesces execution (one backend
    # child per (task, input)); the UI fans that single job out to one bar per
    # anatomical structure it covers — each bar names its OWN structure.  A ✕
    # on any structure row cancels the shared underlying job, so its sibling
    # structure rows retire together.  Same-key jobs can OVERLAP (a late Run
    # while the key's child runs rides a second sequential job), so each bar
    # retires with its own job; the key's box goes when the last bar does.
    #

    def _ensureJobRows(self, key):
        """Create (or extend, on coalescing) the per-structure rows for ``key``.

        One bar per structure the job covers — the bar names its structure and
        starts indeterminate; ``_onJobOutput`` renders the parsed stage/percent
        into every sibling bar (they share one backend child).  The per-row ✕
        routes to ``cancelJob`` on the SHARED key: dequeue when queued, kill
        when running — each job's rows retire together with it
        (``_retireJobRows``).  Each connected slot is stored for the
        connection's lifetime (the PythonQt discipline the queue encodes).
        """
        codes = list(self._pendingJobs.get(key, set()))
        job = self._jobRows.get(key)
        if job is None:
            box = qt.QWidget()
            layout = qt.QVBoxLayout(box)
            layout.setContentsMargins(0, 0, 0, 0)
            self._jobListLayout.addWidget(box)
            job = {"box": box, "layout": layout, "rows": {}}
            self._jobRows[key] = job
        # Structure-vocabulary order first, then any code outside it.
        ordered = [code for _title, code in STRUCTURE_TABS if code in codes]
        ordered += [code for code in codes if code not in ordered]
        for code in ordered:
            if code in job["rows"]:
                continue
            title = self.logic._structureTitle(code)
            rowBox = qt.QWidget()
            rowLayout = qt.QHBoxLayout(rowBox)
            rowLayout.setContentsMargins(0, 0, 0, 0)
            bar = qt.QProgressBar()
            bar.setRange(0, 0)
            bar.setTextVisible(True)
            bar.setFormat(title)
            cancel = qt.QToolButton()
            cancel.setText("✕")
            cancel.setToolTip(
                "Cancel this segmentation job (its sibling structures, which "
                "share one backend run, cancel together)."
            )
            slot = functools.partial(self._onCancelJob, key)
            cancel.connect("clicked()", slot)
            rowLayout.addWidget(bar, 1)
            rowLayout.addWidget(cancel)
            job["layout"].addWidget(rowBox)
            job["rows"][code] = {
                "box": rowBox,
                "bar": bar,
                "cancel": cancel,
                "slot": slot,
                "title": title,
            }

    def _removeJobRow(self, key):
        """Retire a finished/cancelled job's rows — every sibling at once."""
        job = self._jobRows.pop(key, None)
        if job is None:
            return
        try:
            box = job["box"]
            box.setParent(None)
            box.delete()
        except (ValueError, AttributeError):
            # Already reclaimed with a disposed parent tree.
            pass

    def _retireJobRows(self, key, structures):
        """Retire ONE finished job's structure bars; keep siblings that live on.

        Same-key jobs can overlap (a late Run while the key's child runs
        rides a second sequential job), so a finished job retires only the
        bars no outstanding same-key job still covers — the late
        structure's bar must outlive the first job's retirement.  The
        key's box goes when its last bar does.
        """
        job = self._jobRows.get(key)
        if job is None:
            return
        stillCovered = (
            self._jobQueue.coveredStructures(key)
            if self._jobQueue is not None
            else set()
        )
        for code in {str(code) for code in structures}:
            if code in stillCovered:
                continue
            row = job["rows"].pop(code, None)
            if row is None:
                continue
            try:
                row["box"].setParent(None)
                row["box"].delete()
            except (ValueError, AttributeError):
                # Already reclaimed with a disposed parent tree.
                pass
        if not job["rows"]:
            self._removeJobRow(key)

    @staticmethod
    def _applyProgress(row, stage, percent):
        """Render a clean ``(stage, percent)`` into ONE structure's bar.

        The bar always leads with the structure's own title; a parsed percent
        flips it determinate ("Portal vein — predicting 45%"), a stage-only
        line renders indeterminate clean text ("Portal vein — saving…").  The
        raw backend text is never shown (it embeds tqdm's bar glyphs).
        """
        bar = row["bar"]
        title = row["title"]
        if percent is None:
            if bar.maximum != 0:
                bar.setRange(0, 0)
            bar.setFormat(f"{title} — {stage}…")
        else:
            if bar.maximum == 0:
                bar.setRange(0, 100)
            bar.setValue(percent)
            bar.setFormat(f"{title} — {stage} %p%")

    def _onCancelJob(self, key):
        """A structure row's ✕: dequeue a queued job / kill the running child.

        The rows fanned from one job all carry the SAME key, so any of their
        ✕ buttons cancels the shared underlying job.  Both routes complete
        through the queue's finish path with ``success=False``, so
        ``_onJobFinished`` retires the job's rows together.  Segment
        statuses are left untouched — nothing was written at enqueue and
        nothing was produced (ADR-0034 §Amendments: the status column is
        the surgeon's channel, not the queue's).
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
        """Distil a child output line to a clean stage/percent on every bar.

        The queue is strictly sequential, so output belongs to its current
        job; its every structure bar shares one backend child, so the parsed
        ``(stage, percent)`` renders identically across the job's sibling
        rows.  Unrecognised backend chatter leaves the bars and the status
        label untouched — the raw tqdm/milestone text is never surfaced.
        """
        if not line:
            return
        stage, percent = _totalSegmentatorWrapper().parseProgressLine(line)
        if stage is None:
            return
        key = self._jobQueue.currentKey() if self._jobQueue is not None else None
        job = self._jobRows.get(key)
        if job is None:
            return
        cleanPercent = "" if percent is None else f" {percent}%"
        titles = ", ".join(row["title"] for row in job["rows"].values())
        self._statusLabel.setText(f"{titles} — {stage}{cleanPercent}")
        for row in job["rows"].values():
            self._applyProgress(row, stage, percent)

    def _onJobFinished(self, key, structures, success, outputDir):
        """Land a finished job's label files on the canonical node.

        The landing tail of the retired blocking path, now event-driven: the
        produced per-structure label files import into an internal scratch
        (``importJobOutput``) which ``accept()`` merges onto the canonical —
        every landed row reads native ``InProgress`` ("produced, under
        review"); NOTHING ever auto-writes ``Completed``, the surgeon always
        confirms via the status cell (ADR-0034 §Amendments).  Structures the
        job did NOT land (failure, cancel, or a label file the backend never
        produced) keep whatever status they had — enqueue wrote nothing, so
        an aborted job has nothing to undo.

        The whole landing (import AND ``accept``) sits inside one try with
        the row retirement in its ``finally``: a raising merge must not
        leave spinning bars, and its scratch node is reclaimed on the spot
        (``accept`` only removes it on success).  Only THIS job's bars
        retire — a still-outstanding same-key job (the late-structure
        sequential child) keeps its own bars alive.
        """
        structures = {str(code) for code in structures}
        stillCovered = (
            self._jobQueue.coveredStructures(key)
            if self._jobQueue is not None
            else set()
        )
        if stillCovered:
            self._pendingJobs[key] = set(stillCovered)
        else:
            self._pendingJobs.pop(key, None)
        landedCodes = set()
        landingFailed = False
        try:
            if success and outputDir:
                scratch = None
                try:
                    scratch = self.logic.importJobOutput(outputDir, structures)
                    if scratch is not None:
                        segmentation = scratch.GetSegmentation()
                        for segmentId in list(segmentation.GetSegmentIDs()):
                            code = self.logic._expectedCodeForSegment(
                                segmentation.GetSegment(segmentId)
                            )
                            if code is not None:
                                landedCodes.add(code)
                        self.logic.accept(scratch)
                        # The landed surface model sits outside the default
                        # camera framing; re-centre the 3D views (GUI-level
                        # concern).
                        self._reframeThreeDViews()
                except Exception as exc:  # noqa: BLE001 — surface, never wedge
                    logging.error("could not land the job output: %s", exc)
                    landingFailed = True
                    landedCodes = set()
                    if scratch is not None and scratch.GetScene() is not None:
                        # ``accept`` removes the scratch on success only; a
                        # failed merge must not leak it into the scene.
                        slicer.mrmlScene.RemoveNode(scratch)
        finally:
            self._retireJobRows(key, structures)
        if landedCodes:
            self._statusLabel.setText(
                "Landed for review — confirm via the row's status cell."
            )
        elif success and not landingFailed:
            self._statusLabel.setText(
                "Segmentation finished but produced no output — see the log."
            )
        else:
            names = ", ".join(
                sorted(self.logic._structureTitle(c) for c in structures)
            )
            self._statusLabel.setText(f"Segmentation failed: {names} — see the log.")

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

    def onEditSelectedSegment(self):
        """Expand the embedded editor and sync the selected row into it.

        The toolbar's Edit gesture (ADR-0034 §Amendments item 4): re-ensure
        the editor's parameter node + pinned inputs (a scene close may have
        reclaimed them), open the collapsible section, and make the FIRST
        selected row the editor's current segment.  Replaces the retired
        jump-to-module path.  Effect pre-activation is out of scope here
        (ADR-0026 / future).
        """
        editor = getattr(self, "_embeddedEditor", None)
        if editor is None:
            return
        self.logic.getOrCreateCanonicalSegmentation()
        try:
            editor.setMRMLSegmentEditorNode(self._ensureEditorParameterNode())
        except ValueError:
            self._embeddedEditor = None
            self._editorSection = None
            return
        self._bindEmbeddedEditor()
        self._observeCanonicalSegmentation()
        section = getattr(self, "_editorSection", None)
        if section is not None:
            section.collapsed = False
        self._syncEditorToSelection()

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

    def _eligibleImportSources(self):
        """The scene's importable segmentation nodes.

        Any plain ``vtkMRMLSegmentationNode`` qualifies; the orchestrator's
        OWN role-carrying nodes never do — the canonical is the landing
        target, and scratch nodes are the AI path's internal carriers
        (``accept()`` is their route, ADR-0024 §Terminology).
        """
        return [
            node
            for node in slicer.util.getNodesByClass("vtkMRMLSegmentationNode")
            if not node.GetAttribute(ROLE_ATTRIBUTE)
        ]

    def onImportSegmentation(self):
        """The toolbar Import… gesture: state the correspondences, land them.

        A modal correspondence dialog (a ``qMRMLNodeComboBox`` over
        segmentation nodes with a per-source-segment mapping table under
        it) in front of the unified landing path (ADR-0034 §Decision 2:
        the import path unifies — one interaction grammar for the AI and
        import routes).  With nothing importable in the scene the gesture
        explains itself on the shared status label instead of opening an
        empty picker (explainable state, ADR-0009).
        """
        eligible = self._eligibleImportSources()
        if not eligible:
            self._statusLabel.setText(
                "No importable segmentation in the scene — load one first "
                "(File ▸ Add Data)."
            )
            return
        dialog, combo, table = self._buildImportDialog()
        try:
            accepted = dialog.exec_() == qt.QDialog.Accepted
            source = combo.currentNode() if accepted else None
            correspondences = (
                self._statedCorrespondences(combo, table) if accepted else {}
            )
        finally:
            combo.setMRMLScene(None)
            # Keep the dialog PARENTED for its deferred deletion:
            # setParent(None) hands the wrapper's ownership to PythonQt,
            # and deleteLater then destroys the same object from the Qt
            # side -- the parentless-widget double-free (crashed live on
            # the first event-loop spin after the import).
            self._importDialogButtons = None
            self._importMappingTable = None
            dialog.deleteLater()
        if source is not None:
            self._importChosenSource(source, correspondences)

    def _buildImportDialog(self):
        """Build the modal import dialog; returns ``(dialog, combo, table)``.

        Split from the gesture so the dialog SHAPE is pinnable headless —
        the live run only adds ``exec_()``.  Under the source picker sits
        the correspondence table: one row per source segment of the picked
        node, its Import-as combo defaulting to the skip entry — NO
        auto-match, no prefill from names or carried terminology tags; the
        surgeon states every correspondence (ADR-0034 §Amendments).  A
        structure whose checklist row already landed is annotated
        "(already present)" and stays selectable (an extra same-code row
        per the never-overwrite rule).  The button box is built empty and
        populated through the ``standardButtons`` property: the
        flags-taking CONSTRUCTOR overload does not marshal through
        PythonQt (the int matched a different overload and produced a
        buttonless box — a live-test finding).
        """
        dialog = qt.QDialog(self.parent)
        dialog.setWindowTitle("Import segmentation")
        column = qt.QVBoxLayout(dialog)
        column.addWidget(
            qt.QLabel("Import the segments of this segmentation for review:")
        )
        combo = slicer.qMRMLNodeComboBox()
        combo.nodeTypes = ["vtkMRMLSegmentationNode"]
        combo.addEnabled = False
        combo.removeEnabled = False
        combo.renameEnabled = False
        combo.noneEnabled = False
        combo.showHidden = False
        combo.setMRMLScene(slicer.mrmlScene)
        # Hide the orchestrator's own nodes (canonical + scratch roles);
        # the proxy-model hidden list is the stock exclusion surface.
        combo.sortFilterProxyModel().hiddenNodeIDs = [
            node.GetID()
            for node in slicer.util.getNodesByClass("vtkMRMLSegmentationNode")
            if node.GetAttribute(ROLE_ATTRIBUTE)
        ]
        column.addWidget(combo)
        column.addWidget(
            qt.QLabel("State what each segment imports as — skipped ones stay put:")
        )
        table = qt.QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Source segment", "Import as"])
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        table.setSelectionMode(qt.QAbstractItemView.NoSelection)
        column.addWidget(table)
        # A BOUND-METHOD slot, table tracked on self: PythonQt holds no
        # reference to a connected lambda, which gets collected with the
        # builder frame and silently never fires again.
        self._importMappingTable = table
        combo.connect(
            "currentNodeChanged(vtkMRMLNode*)", self._onImportSourceChanged
        )
        self._populateImportMappingTable(table, combo.currentNode())
        buttons = qt.QDialogButtonBox()
        buttons.standardButtons = (
            qt.QDialogButtonBox.Ok | qt.QDialogButtonBox.Cancel
        )
        okButton = buttons.button(qt.QDialogButtonBox.Ok)
        if okButton is not None:
            okButton.setDefault(True)
        buttons.connect("accepted()", dialog.accept)
        buttons.connect("rejected()", dialog.reject)
        column.addWidget(buttons)
        self._importDialogButtons = buttons
        return dialog, combo, table

    def _importStructureOptionTitles(self):
        """The Import-as entries, in ``STRUCTURE_TABS`` order.

        A structure whose checklist row already landed (non-empty or
        provenance-carrying) is annotated "(already present)" — still
        selectable: picking it lands an EXTRA same-code row (the
        never-overwrite rule; the multifocal shape).
        """
        canonical = (
            self.logic._findCanonicalSegmentation() if self.logic else None
        )
        titles = []
        for title, code in STRUCTURE_TABS:
            if _landedSctSegmentCount(canonical, code):
                title = f"{title}{IMPORT_ALREADY_PRESENT_SUFFIX}"
            titles.append(title)
        return titles

    def _onImportSourceChanged(self, node):
        """Repopulate the correspondence table when the picker's node changes."""
        table = getattr(self, "_importMappingTable", None)
        if table is not None:
            self._populateImportMappingTable(table, node)

    def _populateImportMappingTable(self, table, sourceNode):
        """Fill the correspondence table for ``sourceNode``'s segments.

        One row per SOURCE segment: [Source segment | Import as].  Every
        combo defaults to the skip entry — the explicit-correspondence
        contract admits no prefill, even when a source name matches the
        vocabulary.  Repopulated whenever the picker's node changes.
        """
        table.setRowCount(0)
        if sourceNode is None or not sourceNode.IsA("vtkMRMLSegmentationNode"):
            table.setProperty("importSourceNodeID", "")
            return
        # Record whose segments the table shows — the accept-time
        # stale-table guard (_statedCorrespondences) keys on it.
        table.setProperty("importSourceNodeID", sourceNode.GetID())
        titles = self._importStructureOptionTitles()
        segmentation = sourceNode.GetSegmentation()
        segmentIds = list(segmentation.GetSegmentIDs())
        table.setRowCount(len(segmentIds))
        for row, segmentId in enumerate(segmentIds):
            item = qt.QTableWidgetItem(segmentation.GetSegment(segmentId).GetName())
            # Read-only name cell; the row's segment id rides UserRole.
            item.setFlags(qt.Qt.ItemIsEnabled)
            item.setData(qt.Qt.UserRole, segmentId)
            table.setItem(row, 0, item)
            rowCombo = qt.QComboBox()
            rowCombo.addItem(IMPORT_SKIP_LABEL)
            for title in titles:
                rowCombo.addItem(title)
            rowCombo.setCurrentIndex(0)
            table.setCellWidget(row, 1, rowCombo)

    def _importTableCorrespondences(self, table):
        """Read the stated mapping off the table: ``{segmentId: sctCode}``.

        Rows left on the skip default are absent.  The combo's entry order
        is fixed (skip + ``STRUCTURE_TABS`` order), so the index — not the
        possibly-annotated text — carries the code.
        """
        correspondences = {}
        for row in range(table.rowCount):
            item = table.item(row, 0)
            rowCombo = table.cellWidget(row, 1)
            if item is None or rowCombo is None:
                continue
            index = rowCombo.currentIndex
            if index <= 0:
                continue
            correspondences[item.data(qt.Qt.UserRole)] = STRUCTURE_TABS[
                index - 1
            ][1]
        return correspondences

    def _statedCorrespondences(self, combo, table):
        """The accepted dialog's mapping — guarded against a stale table.

        The stock picker can swap between IDENTICALLY NAMED nodes without
        emitting any currentNodeChanged, leaving the table showing the
        previous node's segments; their ids must not leak onto the newly
        picked node, so a table/node mismatch reads as all-skip (the
        graceful no-op that keeps the source and explains itself).
        """
        source = combo.currentNode()
        if source is None:
            return {}
        if table.property("importSourceNodeID") != source.GetID():
            return {}
        return self._importTableCorrespondences(table)

    def _importChosenSource(self, source, correspondences):
        """Route the stated correspondences through the unified landing path.

        The consumption rule surfaces here (explainable state, ADR-0009):
        a full mapping consumes the source; any skipped row keeps it and
        the status label says so; an all-skip mapping is a graceful no-op.
        """
        if source is None or self.logic is None:
            return
        total = source.GetSegmentation().GetNumberOfSegments()
        mapped = len(correspondences or {})
        if mapped == 0:
            self._statusLabel.setText(
                "Nothing was imported — every segment was skipped; the "
                "source segmentation was kept."
            )
            return
        canonical = self.logic.importSegmentation(source, correspondences)
        if canonical is None:
            self._statusLabel.setText(
                "Import failed — the source segmentation was left untouched; "
                "see the log."
            )
            return
        # The landing grows the EXISTING canonical node (the source removal
        # does reach _onSceneChanged, but re-bind explicitly rather than
        # ride a side effect).
        self._bindSegmentsTable()
        self._bindEmbeddedEditor()
        self._observeCanonicalSegmentation()
        # Same re-centre as the toolbar Run's landing: the imported anatomy's
        # surface model lands outside the default camera framing.
        self._reframeThreeDViews()
        if mapped < total:
            self._statusLabel.setText(
                f"Imported {mapped} of {total} segments — the source was kept."
            )
        else:
            self._statusLabel.setText(
                "Imported for review — confirm via the row's status cell."
            )

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
        self._bindEmbeddedEditor()
        self._observeCanonicalSegmentation()

    def cleanup(self):
        # No child process outlives the module: cancel the running job and
        # drop every pending one (ADR-0034 §Decision 5 teardown contract).
        if self._jobQueue is not None:
            self._jobQueue.shutdown()
        # Embedded-editor teardown discipline: detach every MRML reference
        # the editor holds BEFORE the Qt tree is disposed, and reclaim its
        # private parameter node — a widget still holding scene nodes at
        # shutdown is the launched-harness teardown-crash family.
        editor = getattr(self, "_embeddedEditor", None)
        if editor is not None:
            try:
                editor.setActiveEffect(None)
                editor.removeViewObservations()
                editor.setSegmentationNode(None)
                editor.setSourceVolumeNode(None)
                editor.setMRMLSegmentEditorNode(None)
                editor.setMRMLScene(None)
            except ValueError:
                # The C++ widget already went down with a host parent tree.
                pass
        self._embeddedEditor = None
        self._editorSection = None
        editorNode = getattr(self, "_editorNode", None)
        if editorNode is not None and editorNode.GetScene() is not None:
            slicer.mrmlScene.RemoveNode(editorNode)
        self._editorNode = None
        self._observedSegmentation = None
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

    def importSegmentation(self, sourceSegmentationNode, correspondences=None):
        """Land the surgeon's stated correspondences on the canonical node.

        The explicit-correspondence import path (ADR-0034 §Decision 2 "the
        import path unifies", as amended): ``correspondences`` maps source
        segment id -> structure-vocabulary SCT code, exactly as stated in
        the Import… dialog — skipped segments are simply absent.  There is
        NO auto-match: neither the source segment's name nor a
        ``TerminologyEntry`` tag it happens to carry routes anything; the
        stated mapping is the only resolution and OVERRIDES any carried
        tag.  The canonical node's IDENTITY is stable — the retired node
        promotion is gone.

        Every mapped segment flows through the SAME :meth:`_landSegment`
        kernel the AI accept path uses, arriving native ``InProgress``
        with the ``imported`` source tag and carrying the EXPECTED
        structure's identity — the vocabulary title as its name, the
        structure visual defaults, the SCT terminology tag.  Several
        source segments may map to ONE structure (the multifocal shape):
        titles number past the first same-code landing ("<Title> 2",
        "<Title> 3"…), counting rows already landed on the canonical node.

        The landing kernel's standing rule replaces a pre-seeded checklist
        placeholder only when it is EMPTY and provenance-free; a row that
        already landed — in particular a surgeon-``Completed`` one — is
        NEVER overwritten or demoted by an import (``demoteStale=False``:
        the demote-on-rerun staleness rule belongs to the AI re-run path):
        the incoming segment lands as an extra same-code row and the
        surgeon decides which to keep.

        The source node is REMOVED only when EVERY source segment was
        mapped (its segments live on in the canonical node); any skipped
        segment keeps the source untouched in the scene.  An empty/absent
        mapping is a graceful no-op returning ``None`` — as are a
        ``None``/segment-less source and the orchestrator's own
        role-carrying nodes, which are refused — and on any landing
        failure the source is kept and ``None`` returned.  A landing also
        runs the canonical post-growth steps the accept path runs: the 3D
        closed-surface representation, the composed distance map Stage 4
        consumes (ADR-0031), and the visual defaults re-apply.
        """
        if sourceSegmentationNode is None or not sourceSegmentationNode.IsA(
            "vtkMRMLSegmentationNode"
        ):
            return None
        if sourceSegmentationNode.GetAttribute(ROLE_ATTRIBUTE):
            # The canonical node cannot import itself; scratch nodes are the
            # AI landing's internal carriers (accept() is their path).
            return None
        sourceSegmentation = sourceSegmentationNode.GetSegmentation()
        segmentIds = list(sourceSegmentation.GetSegmentIDs())
        if not segmentIds:
            return None
        vocabulary = {str(code) for _title, code in STRUCTURE_TABS}
        mapping = {}
        for segmentId, code in (correspondences or {}).items():
            if segmentId not in segmentIds or str(code) not in vocabulary:
                logging.warning(
                    "import correspondence %r -> %r ignored (unknown "
                    "segment or structure code)",
                    segmentId,
                    code,
                )
                continue
            mapping[segmentId] = str(code)
        if not mapping:
            # Everything skipped (or nothing valid to land): a graceful
            # no-op — the source stays untouched in the scene.
            return None

        canonical = self.getOrCreateCanonicalSegmentation()
        landedSoFar = {
            code: _landedSctSegmentCount(canonical, code)
            for code in set(mapping.values())
        }
        try:
            for segmentId in segmentIds:
                code = mapping.get(segmentId)
                if code is None:
                    continue  # stated as skipped: never lands
                # The EXPECTED structure identity rides the incoming
                # segment BEFORE the copy (name and tags travel with it):
                # the stated code's SCT tag + visual defaults through the
                # shared tagging funnel, and the vocabulary title —
                # numbered past the first same-code landing, so the
                # extra-row (never-overwrite) path carries the identity
                # too, not only the kernel's placeholder replacement.
                ordinal = landedSoFar[code]
                title = self._structureTitle(code)
                self.tagSegmentWithSct(
                    sourceSegmentationNode,
                    segmentId,
                    code,
                    self._structureMeaning(code),
                )
                sourceSegmentation.GetSegment(segmentId).SetName(
                    title if ordinal == 0 else f"{title} {ordinal + 1}"
                )
                landedSoFar[code] = ordinal + 1
                landedId = self._landSegment(
                    canonical,
                    sourceSegmentation,
                    segmentId,
                    SOURCE_IMPORTED,
                    demoteStale=False,
                )
                if landedId is None:
                    raise RuntimeError(
                        f"could not copy segment {segmentId!r} into the "
                        "canonical node"
                    )
        except Exception as exc:  # noqa: BLE001 — surface, keep the source
            logging.error(
                "import failed; the source segmentation stays in the "
                "scene: %s",
                exc,
            )
            return None
        if len(mapping) == len(segmentIds):
            # Every segment was mapped: the source is consumed — its
            # segments live on in the canonical node.  Any skipped row
            # keeps it untouched for the surgeon.
            slicer.mrmlScene.RemoveNode(sourceSegmentationNode)
        # The import is an explicit human action growing the canonical node
        # (the accept path's twin), so it runs the same post-merge steps:
        # the 3D closed-surface representation (the main 3D view is
        # otherwise empty entering Stage 4), the composed distance map
        # Stage 4 consumes (ADR-0031), and the per-segment 3D opacity that
        # does not travel with copied segments.
        self.ensureSurfaceRepresentation(canonical)
        self.ensureDistanceMap(canonical)
        self.applyVisualDefaults(canonical)
        return canonical

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

    def _landSegment(
        self, canonicalNode, sourceSegmentation, segmentId, source, demoteStale=True
    ):
        """Land one incoming segment on the canonical node.

        The ADR-0034 §Amendments landing contract shared by the accept
        merge loop AND the unified import path: when the incoming
        segment's SCT code matches a pre-seeded EMPTY expected segment (no
        voxel data and no provenance source tag — emptiness, not status,
        marks the replaceable placeholder: the status column is the
        surgeon's channel), the placeholder is removed, the incoming
        segment copied in, and the placeholder's row position restored via
        the ``vtkSegmentation`` reorder API (the same
        ``GetSegmentIndex``/``SetSegmentIndex`` pair the stock table's
        move up/down uses).  A row that already landed is never replaced:
        the incoming segment lands as an extra same-code row.  Returns the
        landed segment id, or ``None`` when the copy failed.

        Staleness rides the LANDING (ADR-0034 §Decision 2, as amended):
        enqueue/cancel never touch statuses, so a re-run of a confirmed
        structure demotes its previously landed same-code ``Completed``
        row(s) back to native ``InProgress`` here — at the moment new
        produced output for the structure actually arrives.  The demote is
        the AI re-run path's; the import path lands with
        ``demoteStale=False`` so a surgeon-``Completed`` row is never
        touched by an import (the extra row lands beside it and the
        surgeon decides which to keep).

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
            # The staleness demote (see docstring): new output for this
            # structure makes a previously confirmed same-code row stale.
            # AI re-run path only -- an import never demotes.
            siblingIds = (
                list(canonicalSegmentation.GetSegmentIDs()) if demoteStale else []
            )
            for siblingId in siblingIds:
                sibling = canonicalSegmentation.GetSegment(siblingId)
                if self._expectedCodeForSegment(sibling) != code:
                    continue
                if (
                    segmentsLogic.GetSegmentStatus(sibling)
                    == segmentsLogic.Completed
                ):
                    segmentsLogic.SetSegmentStatus(
                        sibling, segmentsLogic.InProgress
                    )
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
    # SCT tagging (the ADR-0011 structure vocabulary).
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

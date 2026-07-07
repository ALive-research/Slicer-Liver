# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

# ruff: noqa: F403, F405  # standard Slicer scripted-module wildcard-import pattern

"""LiverSegmentation — Stage 2 (Anatomy Definition) scripted module.

Hosts the Python orchestrator that sequences per-structure micro-workflows
(liver parenchyma, portal vein, hepatic vein, tumors) per
``Docs/adr/0024-segmentation-orchestration.md``.  The orchestrator:

  * publishes exactly ONE canonical ``vtkMRMLSegmentationNode`` per case,
    flagged via the ``LiverSegmentation.Role`` attribute;
  * holds per-tool output in scratch ``vtkMRMLSegmentationNode``s (same role
    attribute, value ``scratch``) until the surgeon Accepts;
  * merges a scratch node's segments INTO the existing canonical node on
    Accept (singular canonical-creation path; ADR-0024 §"Output contract");
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

import logging

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
# Per-tab confirmation glyphs, reused from the Liver shell idiom
# (``Liver/Liver.py`` ``_INDICATOR_COMPLETE`` / ``_INDICATOR_PENDING``, the
# ✓ / ● / ○ set).  Named here so the per-tab glyph contract stays in lockstep
# with the shell and is grep-able (ADR-0024 surgeon UI).
#
GLYPH_COMPLETE = "✓"  # accepted: canonical node holds this structure's SCT segment
GLYPH_PENDING = "○"   # not yet accepted

#
# The four Stage-2 structure tabs, in surgeon-workflow order (ADR-0024
# §"Per-structure micro-workflows").  Each entry pairs the tab title with the
# SCT type code its Accept lands in the canonical node.
#
STRUCTURE_TABS = (
    ("Liver parenchyma", SCT_LIVER_CODE),
    ("Portal vein", SCT_PORTAL_VEIN_CODE),
    ("Hepatic vein", SCT_HEPATIC_VEIN_CODE),
    ("Tumors", SCT_MASS_CODE),
)


class LiverSegmentationWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    """Stage-2 surgeon panel — a QTabWidget of four per-structure cards.

    Each tab (Liver parenchyma / Portal vein / Hepatic vein / Tumors) hosts a
    reusable card fragment driving the orchestrator end to end: Run
    TotalSegmentator -> scratch, then Accept (merge into the canonical node)
    or Reject (discard scratch), plus Edit-in-Segment-Editor on the canonical
    node (ADR-0024 §"Per-structure micro-workflows").  Each tab label carries
    a confirmation glyph (○ -> ✓) mirroring the Liver-shell idiom; the glyph
    flips once the CANONICAL node holds that structure's SCT-tagged segment
    (``LiverSegmentationLogic.isStructureAccepted``), refreshed on scene change.

    A Stage-2-local backend-status row (installed ✓/✗ + Pre-download) surfaces
    the TotalSegmentator install state.  This is intentionally local to
    Stage 2, NOT the Liver-shell settings panel that ADR-0024 §"Lazy install"
    / §Follow-on defers to a sub-affordance of the shell's Stage 6.

    Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent=None):
        self.logic = None
        self.structureTabs = None
        self._backendStatusLabel = None
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)

    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)

        self.logic = LiverSegmentationLogic()

        self.structureTabs = qt.QTabWidget()
        self.structureTabs.setObjectName("StructureTabs")
        self.structureTabs.setTabPosition(qt.QTabWidget.North)
        for title, sctCode in STRUCTURE_TABS:
            page = self._buildStructureCard(title, sctCode)
            self.structureTabs.addTab(page, f"{GLYPH_PENDING}  {title}")
        self.layout.addWidget(self.structureTabs)

        self.layout.addWidget(self._buildBackendStatusRow())

        # Keep the per-tab glyphs in sync with the canonical-node state.
        self.addObserver(
            slicer.mrmlScene, slicer.mrmlScene.NodeAddedEvent, self._onSceneChanged
        )
        self.addObserver(
            slicer.mrmlScene, slicer.mrmlScene.NodeRemovedEvent, self._onSceneChanged
        )

        self.layout.addStretch(1)
        self._refreshTabGlyphs()
        self._refreshBackendStatus()

    def _buildStructureCard(self, title, sctCode):
        """Build the reusable per-structure card fragment for one tab body.

        Run TotalSegmentator / status / Accept / Reject / Edit-in-Segment-
        Editor (ADR-0024 §"Per-structure micro-workflows").  The card holds
        its own scratch node between Run and Accept/Reject.
        """
        page = qt.QWidget()
        layout = qt.QVBoxLayout(page)

        card = _StructureCard(self, title, sctCode)
        layout.addWidget(card.runButton)
        layout.addWidget(card.statusLabel)
        layout.addWidget(card.progressBar)

        actions = qt.QHBoxLayout()
        actions.addWidget(card.acceptButton)
        actions.addWidget(card.rejectButton)
        actions.addWidget(card.editButton)
        layout.addLayout(actions)
        layout.addStretch(1)
        return page

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
        row = qt.QWidget()
        layout = qt.QHBoxLayout(row)
        self._backendStatusLabel = qt.QLabel()
        layout.addWidget(self._backendStatusLabel)
        layout.addStretch(1)
        preDownload = qt.QPushButton("Pre-download AI backend")
        preDownload.connect("clicked()", self.onPreDownload)
        layout.addWidget(preDownload)
        return row

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
        glyph = GLYPH_COMPLETE if installed else "✗"
        state = "installed" if installed else "not installed"
        self._backendStatusLabel.setText(f"AI backend (TotalSegmentator): {glyph} {state}")

    def _onSceneChanged(self, caller=None, event=None):
        self._refreshTabGlyphs()

    def _refreshTabGlyphs(self):
        """Repaint each tab label's confirmation glyph from the canonical node.

        ○ before that structure's Accept, ✓ after — driven by
        ``LiverSegmentationLogic.isStructureAccepted`` (canonical-only read).
        PythonQt: ``QTabWidget.count`` is a property, not a callable.
        """
        if self.structureTabs is None or self.logic is None:
            return
        for index in range(self.structureTabs.count):
            title, sctCode = STRUCTURE_TABS[index]
            glyph = (
                GLYPH_COMPLETE
                if self.logic.isStructureAccepted(sctCode)
                else GLYPH_PENDING
            )
            self.structureTabs.setTabText(index, f"{glyph}  {title}")

    def cleanup(self):
        self.removeObservers()


class _StructureCard:
    """Per-structure card controller: Run -> scratch -> Accept / Reject / Edit.

    One instance backs one tab body (ADR-0024 §"Per-structure
    micro-workflows").  Holds the card's pending scratch node between Run and
    Accept/Reject; delegates all node lifecycle to the orchestrator.
    """

    def __init__(self, widget, title, sctCode):
        self._widget = widget
        self._sctCode = sctCode
        self._scratch = None

        self.runButton = qt.QPushButton(f"Run TotalSegmentator ({title})")
        self.statusLabel = qt.QLabel("Idle")
        self.progressBar = qt.QProgressBar()
        self.progressBar.setVisible(False)
        self.acceptButton = qt.QPushButton("Accept")
        self.rejectButton = qt.QPushButton("Reject")
        self.editButton = qt.QPushButton("Edit in Segment Editor")
        self.acceptButton.setEnabled(False)
        self.rejectButton.setEnabled(False)

        self.runButton.connect("clicked()", self.onRun)
        self.acceptButton.connect("clicked()", self.onAccept)
        self.rejectButton.connect("clicked()", self.onReject)
        self.editButton.connect("clicked()", self.onEdit)

    def onRun(self):
        volume = self._widget.logic.selectInputVolume()
        self.progressBar.setVisible(True)
        try:
            self._scratch = self._widget.logic.segment(volume, self._sctCode)
        finally:
            self.progressBar.setVisible(False)
        self.statusLabel.setText("Review the result, then Accept or Reject.")
        self.acceptButton.setEnabled(True)
        self.rejectButton.setEnabled(True)

    def onAccept(self):
        if self._scratch is None:
            return
        self._widget.logic.accept(self._scratch)
        self._scratch = None
        self.acceptButton.setEnabled(False)
        self.rejectButton.setEnabled(False)
        self.statusLabel.setText("Accepted.")
        self._widget._refreshTabGlyphs()

    def onReject(self):
        if self._scratch is None:
            return
        self._widget.logic.reject(self._scratch)
        self._scratch = None
        self.acceptButton.setEnabled(False)
        self.rejectButton.setEnabled(False)
        self.statusLabel.setText("Discarded.")

    def onEdit(self):
        """Open the stock Segment Editor on the canonical node.

        Stock Segment Editor on the single canonical segmentation (ADR-0024).
        Kumar-Oram effect pre-activation is out of scope here (ADR-0026 /
        future).
        """
        canonical = self._widget.logic.getOrCreateCanonicalSegmentation()
        slicer.util.selectModule("SegmentEditor")
        try:
            editorWidget = slicer.modules.segmenteditor.widgetRepresentation().self()
            editorWidget.editor.setSegmentationNode(canonical)
        except Exception as exc:  # noqa: BLE001 — defensive across Slicer versions
            logging.debug("Could not pre-select canonical node in editor: %s", exc)


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
        """Return True iff Stage 2 is (soft-)done.

        Soft-done per ADR-0023: the canonical segmentation holds at least ONE
        SCT-tagged segment — NOT "all four structures present".  Scratch nodes
        never flip the predicate true.
        """
        canonical = self._findCanonicalSegmentation()
        if canonical is None:
            return False
        return self._hasSctTaggedSegment(canonical)

    def isStructureAccepted(self, sctCode) -> bool:
        """Return True iff the CANONICAL node holds a segment SCT-tagged ``sctCode``.

        Drives the per-tab confirmation glyph (○ -> ✓) in the surgeon UI.
        Canonical-only read (mirroring :meth:`_findCanonicalSegmentation`):
        a scratch node tagged for the structure is pending, not accepted, so
        the tab stays ○ until that structure's Accept (ADR-0024 §"Output
        contract" + §Terminology).
        """
        canonical = self._findCanonicalSegmentation()
        if canonical is None:
            return False
        return any(str(sctCode) in text for text in self._sctTagTexts(canonical))

    #
    # Canonical / scratch surface (ADR-0024 §"Output contract" + §Terminology).
    #

    def getOrCreateCanonicalSegmentation(self):
        """Return the single canonical segmentation node, creating it if absent.

        Idempotent (get-or-create): repeated calls return the SAME node, never
        a second canonical node (ADR-0024 §"Output contract", rejecting
        Alternative B).
        """
        canonical = self._findCanonicalSegmentation()
        if canonical is not None:
            return canonical
        return self._createSegmentationWithRole(ROLE_CANONICAL, "Anatomy: Canonical")

    def importSegmentationAsCanonical(self, sourceSegmentationNode, assignments):
        """Promote a loaded segmentation to the canonical node, SCT-tagging it.

        The v2.0 path to a canonical segmentation WITHOUT in-app AI (deferred to
        v2.1): the surgeon loads a segmentation and assigns each segment a
        structure.  ``assignments`` maps ``segmentId -> (sctCode, meaning)``.
        Marks ``sourceSegmentationNode`` as THE canonical node (ADR-0024
        §"Output contract" — exactly one; any prior canonical is demoted) and
        SCT-tags each assigned segment via :meth:`tagSegmentWithSct`, so
        :meth:`isStructureAccepted` / :meth:`isStageComplete` report the
        structures.  A no-op returning ``None`` when the source is missing / not
        a segmentation, or no assignments are given.
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
        for segmentId, (code, meaning) in assignments.items():
            self.tagSegmentWithSct(sourceSegmentationNode, segmentId, code, meaning)
        return sourceSegmentationNode

    def createScratchSegmentation(self):
        """Mint an orchestrator-private scratch segmentation node.

        Scratch nodes are also ``vtkMRMLSegmentationNode`` instances but carry
        ``role=scratch``; they hold a tool's pending output until the surgeon
        Accepts (ADR-0024 §Terminology "scratch node").
        """
        return self._createSegmentationWithRole(ROLE_SCRATCH, "Anatomy: Scratch")

    def accept(self, scratch):
        """Merge a scratch node's segments into the canonical node.

        The surgeon-approved promotion (ADR-0024 §Terminology "commit /
        Accept"): the canonical-node count is unchanged; the scratch node's
        segments now live in the canonical node.  The scratch node is removed
        once its segments are copied.
        """
        if scratch is None or not scratch.IsA("vtkMRMLSegmentationNode"):
            raise ValueError("accept() requires a scratch vtkMRMLSegmentationNode")
        if scratch.GetAttribute(ROLE_ATTRIBUTE) != ROLE_SCRATCH:
            raise ValueError("accept() target is not a scratch-role segmentation")

        canonical = self.getOrCreateCanonicalSegmentation()
        canonicalSegmentation = canonical.GetSegmentation()
        scratchSegmentation = scratch.GetSegmentation()
        for segmentId in list(scratchSegmentation.GetSegmentIDs()):
            canonicalSegmentation.CopySegmentFromSegmentation(
                scratchSegmentation, segmentId
            )
        slicer.mrmlScene.RemoveNode(scratch)
        return canonical

    def reject(self, scratch):
        """Discard a scratch node without touching the canonical node.

        The symmetric counterpart of :meth:`accept` (ADR-0024 §Terminology:
        scratch is discardable pending output).  Removing the scratch node
        leaves the canonical node — and its segments — exactly as they were.
        """
        if scratch is None or not scratch.IsA("vtkMRMLSegmentationNode"):
            raise ValueError("reject() requires a scratch vtkMRMLSegmentationNode")
        if scratch.GetAttribute(ROLE_ATTRIBUTE) != ROLE_SCRATCH:
            raise ValueError("reject() target is not a scratch-role segmentation")
        slicer.mrmlScene.RemoveNode(scratch)

    #
    # Per-structure Run (ADR-0024 §"Per-structure micro-workflows").  A card's
    # Run drives the AI backend on the Stage-1 input volume and lands its
    # output in a single scratch node; Run never touches the canonical node
    # (that path is Accept-only, rejecting Alternative D auto-commit).
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

    def segment(self, volume, sctTarget):
        """Run the AI backend for one structure, landing output in scratch.

        The wrapper's ``run()`` was a stub; this is the orchestrator-owned
        entry point a card's Run drives.  All TotalSegmentator invocation
        funnels through the single :meth:`_runTotalSegmentator` seam so CI can
        stub it (a real inference needs a multi-GB model + GPU).  Returns the
        scratch ``vtkMRMLSegmentationNode`` holding the structure's pending
        output (ADR-0024 §"Output contract").
        """
        return self._runTotalSegmentator(volume, sctTarget)

    def _runTotalSegmentator(self, volume, sctTarget):
        """The single monkeypatchable backend-invocation seam.

        Kept import-pure: the TotalSegmentator backend is reached only through
        the lazy-install wrapper's ``run()`` call path (ADR-0024 §"Lazy
        install"), never imported at module-import time.  CI stubs this method
        to exercise the Run/Accept/Reject bookkeeping without an inference.
        """
        _totalSegmentatorWrapper().run()
        # A real backend wiring populates a scratch node from the inference
        # output and SCT-tags it from the LabelToSCT bridge (ADR-0011); the
        # end-to-end inference path lands with the backend integration.
        return self.createScratchSegmentation()

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
        tag = (
            "Segmentation category and type - DICOM master list"
            f"~{SCT_SCHEME}^85756007^Tissue"
            f"~{SCT_SCHEME}^{code}^{meaning}"
            "~^^~Anatomic codes - DICOM master list~^^~^^"
        )
        segment.SetTag(TERMINOLOGY_ENTRY_TAG, tag)

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

    def _sctTagTexts(self, segmentationNode):
        """Yield the SCT-coded terminology-tag text of each tagged segment.

        Segments without a terminology tag are skipped; only tags carrying the
        SCT coding scheme (the discriminator; the type triple uses
        ``SCT^<code>^<meaning>``) are yielded.  Shared read path behind
        :meth:`_hasSctTaggedSegment` and :meth:`isStructureAccepted`.
        """
        segmentation = segmentationNode.GetSegmentation()
        for index in range(segmentation.GetNumberOfSegments()):
            entry = vtk.reference("")
            if not segmentation.GetNthSegment(index).GetTag(
                TERMINOLOGY_ENTRY_TAG, entry
            ):
                continue
            text = str(entry)
            if SCT_SCHEME in text:
                yield text

    def _hasSctTaggedSegment(self, segmentationNode) -> bool:
        """Return True iff any segment carries an SCT-coded terminology tag."""
        return any(True for _ in self._sctTagTexts(segmentationNode))

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

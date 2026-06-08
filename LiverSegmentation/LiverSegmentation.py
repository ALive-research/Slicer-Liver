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

#: Subject Hierarchy folder collecting this stage's nodes (ADR-0023).
ANATOMY_FOLDER_NAME = "Anatomy"

#: Slicer's standard per-segment terminology tag carrying the SCT triple.
TERMINOLOGY_ENTRY_TAG = "TerminologyEntry"
#: SCT coding scheme designator (ADR-0011).
SCT_SCHEME = "SCT"
#: Liver parenchyma SNOMED-CT code (ADR-0024 §"Output contract").
SCT_LIVER_CODE = "10200004"


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


class LiverSegmentationWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    """Stage-2 surgeon UI: per-structure cards driving the orchestrator.

    Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent=None):
        self.logic = None
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)

    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)

        uiWidget = slicer.util.loadUI(self.resourcePath("UI/LiverSegmentation.ui"))
        self.layout.addWidget(uiWidget)
        self.ui = slicer.util.childWidgetVariables(uiWidget)
        uiWidget.setMRMLScene(slicer.mrmlScene)

        # Keep the panel flowing top-to-bottom.
        self.layout.addStretch(1)

        self.logic = LiverSegmentationLogic()

    def cleanup(self):
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
        """Return True iff Stage 2 is (soft-)done.

        Soft-done per ADR-0023: the canonical segmentation holds at least ONE
        SCT-tagged segment — NOT "all four structures present".  Scratch nodes
        never flip the predicate true.
        """
        canonical = self._findCanonicalSegmentation()
        if canonical is None:
            return False
        return self._hasSctTaggedSegment(canonical)

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

    def _hasSctTaggedSegment(self, segmentationNode) -> bool:
        """Return True iff any segment carries an SCT-coded terminology tag."""
        segmentation = segmentationNode.GetSegmentation()
        for index in range(segmentation.GetNumberOfSegments()):
            segment = segmentation.GetNthSegment(index)
            entry = vtk.reference("")
            if not segment.GetTag(TERMINOLOGY_ENTRY_TAG, entry):
                continue
            # SCT coding scheme appearing in the entry is the discriminator;
            # the type triple uses "SCT^<code>^<meaning>".
            if SCT_SCHEME in str(entry):
                return True
        return False

    def _collectUnderAnatomyFolder(self, node):
        """Reparent ``node`` under the "Anatomy" Subject Hierarchy folder.

        Per-module Subject Hierarchy discipline (ADR-0023): each stage collects
        its nodes under a named folder.  Idempotent — reuses the folder if it
        already exists.  Best-effort: a missing SH plugin (headless contexts)
        must not break node creation.
        """
        try:
            shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(
                slicer.mrmlScene
            )
        except Exception as exc:  # noqa: BLE001 — defensive, headless contexts
            logging.debug("Subject Hierarchy unavailable: %s", exc)
            return
        if shNode is None:
            return

        sceneItem = shNode.GetSceneItemID()
        folderItem = shNode.GetItemChildWithName(sceneItem, ANATOMY_FOLDER_NAME)
        if not folderItem:
            folderItem = shNode.CreateFolderItem(sceneItem, ANATOMY_FOLDER_NAME)
        nodeItem = shNode.GetItemByDataNode(node)
        if nodeItem:
            shNode.SetItemParent(nodeItem, folderItem)


class LiverSegmentationTest(ScriptedLoadableModuleTest):
    """Slicer self-test entry point.

    Behaviour-pinning invariants live under ``Testing/Python/`` (pytest);
    this class keeps the standard scripted-module self-test surface available.
    """

    def setUp(self):
        slicer.mrmlScene.Clear()

    def runTest(self):
        self.setUp()

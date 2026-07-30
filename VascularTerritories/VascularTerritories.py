# ==============================================================================
#
#  Distributed under the OSI-approved BSD 3-Clause License.
#
#   Copyright (c) 2022-2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
#
#   Redistribution and use in source and binary forms, with or without
#   modification, are permitted provided that the following conditions
#   are met:
#
#   * Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
#
#   * Redistributions in binary form must reproduce the above copyright
#     notice, this list of conditions and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#
#   * Neither the name of Oslo University Hospital nor the names
#     of Contributors may be used to endorse or promote products derived
#     from this software without specific prior written permission.
#
#   THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
#   "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
#   LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
#   A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
#   HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
#   SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
#   LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
#   DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
#   THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#   (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#   OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
#   This file was originally developed by Ole V. Solberg, Geir A. Tangen, Javier
#   Perez-de-Frutos (SINTEF, Norway) and Rafael Palomar (Oslo University
#   Hospital) through the ALive project (grant nr. 311393).
#
# ==============================================================================

# ruff: noqa: F403, F405  # standard Slicer scripted-module wildcard-import pattern


import os
import logging
import vtk
import qt
import slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin

#
# VascularTerritories
#

class VascularTerritories(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Extract Vascular segments"
    self.parent.categories = [""]
    self.parent.dependencies = []
    self.parent.contributors = ["Ole Vegard Solberg (SINTEF)",
                                "Geir Arne Tangen (SINTEF)",
                                "Rafael Palomar (OUS)",
                                "Javier Pérez de Frutos (SINTEF)"]
    self.parent.helpText = """
    This module provides tools and functionality for extracting vascular liver segments from 3D liver models.
    """
    self.parent.acknowledgementText = """
    """  # TODO: replace with organization, grant and thanks.

    # Register the territory MRML node classes at module-discovery time
    # (before the widget is ever opened) so that ``slicer.mrmlScene
    # .AddNewNodeByClass("vtkMRMLStdCouinaudTerritoriesNode", ...)``
    # works from any test, batch-mode script, or other module's setup
    # callback.  The previous code path created the C++ Logic only in
    # ``VascularTerritoriesWidget.setup()`` (i.e. on first navigation
    # to the module), so ctest Python tests that ran at startup hit
    # "node class not registered" failures even though everything else
    # was wired correctly.
    #
    # We register the class prototypes directly via the scene rather
    # than instantiating ``vtkSlicerVascularTerritoriesLogic`` here --
    # the Widget will create its own Logic instance later and we want
    # to avoid two Logics both observing the scene's ``NodeAddedEvent``
    # (which would double-process the Stage 4 Subject Hierarchy folder
    # placement in ``OnMRMLSceneNodeAdded``).
    if not slicer.app.commandOptions().noMainWindow:
      slicer.app.connect("startupCompleted()", self._registerTerritoryNodeClasses)
    else:
      # ``--no-main-window`` skips Slicer's normal startup sequence so
      # the ``startupCompleted`` signal never fires.  Run the
      # registration immediately so headless / test invocations still
      # have the classes available.
      self._registerTerritoryNodeClasses()

    #Hide module, so that it only shows up in the Liver module, and not as a separate module
    parent.hidden = True

  def _registerTerritoryNodeClasses(self):
    """Instantiate the specialized C++ Logic at module-init time so
    its scene observer is wired before any node is added.

    Without this, the only territory-aware scene observer is the one
    the widget creates in ``setup()`` (i.e. on first navigation to
    the module), so any node added before then -- by ctest, by a
    batch-mode script, or by another module's setup callback -- skips
    the Stage 4 Subject Hierarchy folder placement in
    ``vtkSlicerVascularTerritoriesLogic::OnMRMLSceneNodeAdded``.

    The Logic is stored on the Module class instance to keep it alive
    for the lifetime of the application; on Python-level garbage
    collection the observer would auto-unregister itself.  Two
    instances (this one + the widget's) both observing the scene is
    safe -- ``RegisterNodes`` is idempotent and the SH placement
    code reuses an existing 'Vascular Territories' folder rather
    than creating a duplicate."""
    try:
      from vtkSlicerVascularTerritoriesModuleLogicPython import (
        vtkSlicerVascularTerritoriesLogic,
      )
    except ImportError as exc:
      logging.warning(
        "VascularTerritories: specialized Logic unavailable -- "
        "skipping early node-class registration (%s).  This usually "
        "means the module Logic library failed to build or its "
        "Python wrapping is not on the launcher's "
        "--additional-module-paths.", exc)
      return
    self._cppLogic = vtkSlicerVascularTerritoriesLogic()
    self._cppLogic.SetMRMLScene(slicer.mrmlScene)
    # The specialized Logic is reachable as
    # ``slicer.modules.vascularterritories.self()._cppLogic`` (the scripted
    # module's Python instance).  Do NOT assign it onto the C++ module
    # object -- qSlicerScriptedLoadableModule refuses new attributes, which
    # raised at every startup and left downstream consumers (the Stage-3
    # IsStageComplete contract) resolving the generic scripted logic.

#
# Register sample data sets in Sample Data module
#

class VascularTerritoriesWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent=None):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    self.logic = None
    self._parameterNode = None
    self._updatingGUIFromParameterNode = False
    # Vessel-adhering-highlight wiring (ADR-0037).  A single scene-resident
    # ``vtkMRMLTerritoriesHighlightDisplayNode`` whose ``pickSurface``
    # reference tracks the input segmentation and whose Visibility gates
    # the hover Pipeline's paint (live only during marker placement).
    self._highlightDisplayNode = None
    # The input segmentation's display node the widget observes so hiding a
    # structure hides its extracted centerline(s) (ADR-0037 slice 5).  Tracked
    # so the observer can be re-aimed on an input change and removed in cleanup.
    self._observedSegmentationDisplayNode = None
    ScriptedLoadableModuleWidget.__init__(self, parent)
    VTKObservationMixin.__init__(self)  # needed for parameter node observation

  def setup(self):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.setup(self)

    # Register the LayerDM Pipeline creators (ADR-0013 §5 call 3).  ONE
    # Pipeline per display-node type (ADR-0013 §1): the highlight display node
    # gets exactly ONE 3D pipeline -- ``TerritoryPlacementPipeline``, which
    # renders the placed seeds AND the hover-adhering marker AND handles
    # placement/edit -- plus ONE slice pipeline (``TerritorySlicePipeline``)
    # for the 2D views.  ``VesselHighlightPipeline`` is NOT registered: a
    # second pipeline on the same (view, display) type is never created by
    # LayerDM, which previously shadowed placement (only the marker showed).
    # Registration is idempotent; guarded against an unreachable LayerDMLib.
    self._registerTerritoryPlacementPipeline()
    self._registerTerritorySlicePipeline()

    # Load widget from .ui file (created by Qt Designer)
    uiWidget = slicer.util.loadUI(self.resourcePath('UI/VascularTerritories.ui'))
    self.layout.addWidget(uiWidget)

    # Add a spacer at the botton to keep the UI flowing from top to bottom
    spacerItem = qt.QSpacerItem(0,0, qt.QSizePolicy.Minimum, qt.QSizePolicy.MinimumExpanding)
    self.layout.addSpacerItem(spacerItem)

    self.ui = slicer.util.childWidgetVariables(uiWidget)

    # ADR-0037 Stage-2: the ``endPointsMarkupsSelector`` (CenterlineSegment)
    # markups selector is RETIRED with the annotation-off-markups transition;
    # its entry is dropped from the node-selector list.
    # ADR-0037 §Decision 4: the ``selectedVascularTerritorySegmId`` output
    # selector is RETIRED -- the territory-map output target is DERIVED from
    # the carrier (``TerritoryMapOutput`` role), so its param-node role
    # (``VascularTerritorySegmentation``) drops out of the selector list.
    self.nodeSelectors = [
        (self.ui.inputSurfaceSelector, "InputSurface"),
        ]

    # Set scene in MRML widgets. Make sure that in Qt designer
    # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
    # "setMRMLScene(vtkMRMLScene*)" slot.
    uiWidget.setMRMLScene(slicer.mrmlScene)

    # Create logic class. Logic implements all computations that should be possible to run
    # in batch mode, without a graphical user interface.
    self.logic = VascularTerritoriesLogic()
#    self.ui.parameterNodeSelector.addAttribute("vtkMRMLScriptedModuleNode", "ModuleName", self.moduleName)
    self.setParameterNode(self.logic.getParameterNode())

    # Copy color map
    self.createColorMap()

    # Connections
    self.ui.inputSurfaceSelector.connect('currentNodeChanged(bool)', self.updateParameterNodeFromGUI)
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)
    self.ui.inputSurfaceSelector.connect('currentNodeChanged(bool)', self.segmentationNodeSelected)

    # Vessel-adhering-highlight wiring (ADR-0036 / ADR-0037).  Keep the
    # highlight node's pickSurface aimed at the selected input segmentation.
    # ADR-0037 Stage-2 retires the markups selector + place widget that used
    # to also gate the highlight's visibility on place mode; the surviving
    # invariant is ``updateHighlightPickSurface`` tracking the input
    # segmentation.
    self.ui.inputSurfaceSelector.connect('currentNodeChanged(bool)', self.updateHighlightPickSurface)

    # Input-structure show/hide (ADR-0037 slice 5): a stock segments table so
    # the surgeon can hide the parenchyma / tumour / other vessel system and
    # focus on the vessel tree being annotated.  Composed above the annotation
    # table (pick what's visible, then annotate).
    self._setupStructuresTable()

    # ADR-0037 Stage-2 table (§Decision 3): the annotation table is composed
    # into the panel here, over the annotation carrier + the placement
    # Pipeline (Python-widget composition, ADR-0004).
    self._setupTerritoriesTable()

    # ADR-0037 §Decision 4: an always-visible affirmative requirements surface
    # under the Extract / Compute buttons (Python-composed, ADR-0004; legible
    # a11y text, ADR-0010).  It enumerates the UNMET preconditions live so a
    # disabled action always tells the surgeon what to do next.
    self._setupRequirementsLabel()

    #TODO: Store all GUI settings
    # These connections ensure that whenever user changes some settings on the GUI, that is saved in the MRML scene
    # (in the selected parameter node).
    #        self.ui.inputSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)

    # Buttons
    self.ui.calculateVascularTerritoryMapButton.connect('clicked(bool)', self.onCalculateVascularTerritoryMapButton)
    self.ui.addCenterlineSegmentButton.connect('clicked(bool)', self.onAddCenterlineButton)

    # ADR-0037 §Decision 4 graceful degradation: disable ONLY the extraction
    # action (with an explaining tooltip) when SlicerVMTK is absent; placement
    # + the table stay live (the legacy VMTK-hard-gate on placement is gone).
    self.updateExtractionActionEnablement()

    # Gate the workflow actions on their real preconditions from the start
    # (ADR-0037 §Decision 4): with no input / no extractable structure / no
    # centerline, both actions read disabled (the extraction tooltip is set by
    # updateExtractionActionEnablement above; _updateActionEnablement keeps it).
    self._updateActionEnablement()
    # Make sure parameter node is initialized (needed for module reload)
    self.initializeParameterNode()

  def _registerTerritoryPlacementPipeline(self):
    """Register the annotation placement/edit LayerDM Pipeline creator.

    ADR-0037 §Decision 2 (ADR-0013 §5 call 3).  Idempotent; a missing
    LayerDMLib is a real configuration error under ADR-0002 so it logs at
    ``critical``, but the rest of widget setup continues.
    """
    try:
      from VascularTerritoriesLib import registerTerritoryPlacementPipelineCreator
      if registerTerritoryPlacementPipelineCreator is None:
        raise ImportError("registerTerritoryPlacementPipelineCreator unavailable")
      registerTerritoryPlacementPipelineCreator()
    except ImportError as exc:
      logging.critical(
        "VascularTerritories: annotation placement LayerDM Pipeline creator "
        "not registered (%s) -- annotation placement is disabled in this "
        "session.  Loading the SlicerLayerDisplayableManager extension is "
        "required for the Pipeline path (ADR-0013/0037).", exc)

  def _registerTerritorySlicePipeline(self):
    """Register the slice-view annotation LayerDM Pipeline creator.

    ADR-0037 §2D placement (ADR-0013 §5 call 3): the slice complement of the
    3D placement Pipeline, reusing the SAME shared display-node state so 2D
    and 3D placement stay in lockstep.  Idempotent; a missing LayerDMLib is a
    real configuration error under ADR-0002 so it logs at ``critical``, but
    the rest of widget setup continues.
    """
    try:
      from VascularTerritoriesLib import registerTerritorySlicePipelineCreator
      if registerTerritorySlicePipelineCreator is None:
        raise ImportError("registerTerritorySlicePipelineCreator unavailable")
      registerTerritorySlicePipelineCreator()
    except ImportError as exc:
      logging.critical(
        "VascularTerritories: slice-view annotation LayerDM Pipeline creator "
        "not registered (%s) -- slice-view annotation placement is disabled "
        "in this session.  Loading the SlicerLayerDisplayableManager "
        "extension is required for the Pipeline path (ADR-0013/0037).", exc)

  # ------------------------------------------------------------------ #
  # Vessel-adhering-highlight wiring (ADR-0036)
  # ------------------------------------------------------------------ #
  #
  # Lifecycle choice: ONE persistent, scene-resident
  # ``vtkMRMLTerritoriesHighlightDisplayNode`` is created lazily on first
  # use and reused for the module's lifetime.  Its ``pickSurface``
  # reference tracks the input segmentation selector; the hover Pipeline
  # (VascularTerritoriesLib.VesselHighlightPipeline) paints only when the
  # node is visible.  We gate that Visibility on the endpoints markup being
  # in PLACE MODE, so the adhering marker is live exactly while the surgeon
  # is dropping territory endpoints and never competes with plain camera
  # interaction outside annotation (ADR-0033 hover discipline keeps even
  # the live marker from stealing the move; the visibility gate is the
  # coarser "don't paint at all outside placement" guard).  A persistent
  # data-only node is cheap and leaves no stray live marker: off-surface
  # hover hides the marker, and place-mode-off hides it wholesale.

  def _ensureHighlightDisplayNode(self):
    """Return the scene-resident highlight display node, creating it once.

    ``None`` when the C++ node class is unavailable (a launch without the
    module's MRML library on the path) — the caller degrades gracefully.
    """
    node = self._highlightDisplayNode
    if node is not None and slicer.mrmlScene.IsNodePresent(node):
      return node
    try:
      node = slicer.mrmlScene.CreateNodeByClass("vtkMRMLTerritoriesHighlightDisplayNode")
    except Exception:  # noqa: BLE001 - node class not registered in this launch
      logging.warning(
        "VascularTerritories: vtkMRMLTerritoriesHighlightDisplayNode "
        "unavailable -- vessel highlight disabled this session.")
      return None
    if node is None:
      return None
    node.UnRegister(None)
    node.SetName("Vessel Highlight")
    node.SetVisibility(False)  # off until arming turns it on
    # Configure BEFORE AddNode: LayerDM consults the pipeline creators the
    # moment the node enters the scene, and each created pipeline (3D + every
    # slice) resolves + OBSERVES the annotation carrier at creation.  So the
    # carrier reference (and the pickSurface) must already be on the node --
    # bind them here, pre-add, or a seed placed in one view never repaints the
    # others until they are individually resliced (the ResectogramViewManager
    # "configure before AddNode" precedent).
    carrier = getattr(self, "_annotationCarrier", None)
    if carrier is not None:
      from VascularTerritoriesLib import TerritoryInteractionState as _territoryState
      _territoryState.set_carrier(node, carrier)
    segmentation = self.ui.inputSurfaceSelector.currentNode()
    if segmentation is not None:
      node.SetAndObservePickSurfaceNodeID(segmentation.GetID())
    node = slicer.mrmlScene.AddNode(node)
    self._highlightDisplayNode = node
    return node

  def updateHighlightPickSurface(self, *args):
    """Aim the highlight's pickSurface at the selected input segmentation."""
    node = self._ensureHighlightDisplayNode()
    if node is None:
      return
    segmentation = self.ui.inputSurfaceSelector.currentNode()
    segmentationId = segmentation.GetID() if segmentation is not None else None
    node.SetAndObservePickSurfaceNodeID(segmentationId)

  def _observeInputSegmentationVisibility(self, segmentationNode):
    """Observe the input segmentation's display node for structure show/hide.

    ADR-0037 slice 5: hiding a structure (input segment) via the structures
    table must hide its extracted centerline(s) too.  A widget-level Python
    observer (ADR-0013 §5 -- no displayable manager) on the segmentation's
    display-node ``ModifiedEvent`` re-syncs every ``CenterlineRefs`` model's
    visibility to its structure's visibility.  Re-aimed on every input change;
    the observer is removed in ``cleanup``.  (The seed glyphs follow the same
    show/hide via the pipelines' own ``visibility_mtime`` rebuild.)
    """
    displayNode = segmentationNode.GetDisplayNode() if segmentationNode is not None else None
    previous = self._observedSegmentationDisplayNode
    if previous is displayNode:
      self._syncCenterlineVisibility()
      return
    if previous is not None:
      self.removeObserver(previous, vtk.vtkCommand.ModifiedEvent, self._onSegmentationVisibilityChanged)
    self._observedSegmentationDisplayNode = displayNode
    if displayNode is not None:
      self.addObserver(displayNode, vtk.vtkCommand.ModifiedEvent, self._onSegmentationVisibilityChanged)
    self._syncCenterlineVisibility()

  def _onSegmentationVisibilityChanged(self, caller, event):
    del caller, event
    self._syncCenterlineVisibility()
    # Poke the highlight display node so the LayerDM-driven seed pipelines
    # (3D + slice) re-run UpdatePipeline and re-evaluate per-seed structure
    # visibility -- otherwise the seed glyphs would only repaint on the next
    # interaction / reslice (ADR-0037 slice 5).
    highlight = getattr(self, "_highlightDisplayNode", None)
    if highlight is not None and slicer.mrmlScene.IsNodePresent(highlight):
      highlight.Modified()

  def _syncCenterlineVisibility(self):
    """Gate each ``CenterlineRefs`` model on its TERRITORY and STRUCTURE visibility.

    A centerline shows only if BOTH its owning TERRITORY is visible AND its
    STRUCTURE (input segment) is visible -- hiding either hides the centerline
    (ADR-0037 slice 5):

    * TERRITORY -- the carrier's per-territory ``GetTerritoryVisibility``,
      resolved from the ``Groupings`` map (centerline node ID -> territory id)
      the extraction wired via ``SetGrouping``.  A hidden territory hides all
      of its centerlines (a territory can span structures, so this is keyed on
      the centerline's owning territory, not the structure).
    * STRUCTURE -- the input segmentation display node's per-segment
      visibility (``GetSegmentVisibility``), read off the centerline's
      ``CENTERLINE_STRUCTURE_ATTRIBUTE`` tag.  A centerline with no structure
      tag (single-model input) is not gated on a segment.

    Fires on the segmentation-display-node observer (structure show/hide) and
    the annotation-carrier ``Modified`` (territory show/hide + extraction).
    """
    carrier = getattr(self, "_annotationCarrier", None)
    if carrier is None:
      return
    displayNode = self._observedSegmentationDisplayNode
    attribute = self.logic.CENTERLINE_STRUCTURE_ATTRIBUTE
    for centerlineId in self.logic.getCenterlineReferenceIDs(carrier):
      model = slicer.mrmlScene.GetNodeByID(centerlineId)
      if model is None:
        continue
      modelDisplay = model.GetDisplayNode()
      if modelDisplay is None:
        continue
      # Territory gate: hide the centerline when its owning territory is hidden.
      territoryId = carrier.GetGrouping(centerlineId)
      territoryVisible = (
        bool(carrier.GetTerritoryVisibility(territoryId)) if territoryId else True
      )
      # Structure gate: hide the centerline when its input segment is hidden.
      structureId = model.GetAttribute(attribute)
      structureVisible = (
        bool(displayNode.GetSegmentVisibility(structureId))
        if (displayNode is not None and structureId)
        else True
      )
      modelDisplay.SetVisibility(territoryVisible and structureVisible)

  def _setupStructuresTable(self):
    """Compose a stock ``qMRMLSegmentsTableView`` for input-structure show/hide.

    Visibility-focused: the surgeon hides the parenchyma / tumour / the other
    vessel system to isolate the vessel tree being annotated.  The stock view
    (the Segment Editor's own visibility widget) drives the input
    segmentation's per-segment visibility (3D + 2D); its segmentation node
    tracks the input selector via ``segmentationNodeSelected``.  A launch
    without the widget library degrades gracefully (panel loads without it).
    ADR-0004 (Python-composed panel).
    """
    self._structuresTable = None
    try:
      table = slicer.qMRMLSegmentsTableView()
    except Exception as exc:  # noqa: BLE001 - widget lib unavailable in this launch
      logging.warning(
        "VascularTerritories: structures table unavailable (%s) -- input-"
        "structure show/hide is disabled this session.", exc)
      return
    table.setMRMLScene(slicer.mrmlScene)
    # Keep the name + eye toggle; drop the editing columns so it reads as a
    # focus control, not a segment editor.
    for setter, value in (
        ("setVisibilityColumnVisible", True),
        ("setColorColumnVisible", False),
        ("setOpacityColumnVisible", False),
        ("setStatusColumnVisible", False),
    ):
      fn = getattr(table, setter, None)
      if fn is not None:
        fn(value)
    self._structuresTable = table
    self.layout.addWidget(qt.QLabel("Anatomical structures (show / hide):"))
    self.layout.addWidget(table)

  def _setupTerritoriesTable(self):
    """Compose the ADR-0037 Stage-2 annotation table into the panel.

    The table is a Python-composed custom widget (ADR-0004 / ADR-0037
    §Decision 3) over the annotation carrier + the placement Pipeline.  A
    launch without the module's MRML library or LayerDMLib on the path
    degrades gracefully: the panel loads without the table.
    """
    self._territoriesTable = None
    try:
      from VascularTerritoriesLib import TerritoriesTableWidget
    except ImportError as exc:
      logging.warning(
        "VascularTerritories: annotation table widget unavailable (%s) -- "
        "the Stage-2 table is disabled this session.", exc)
      return
    if TerritoriesTableWidget is None:
      return
    carrier = self._ensureAnnotationCarrier()
    # Re-evaluate the Extract/Compute enablement whenever the carrier changes
    # (a seed added/deleted, a centerline wired): the action gating reads live
    # seed + centerline state (ADR-0037 §Decision 4).  Removed in cleanup.
    if carrier is not None and not self.hasObserver(
        carrier, vtk.vtkCommand.ModifiedEvent, self._onAnnotationCarrierModified):
      self.addObserver(carrier, vtk.vtkCommand.ModifiedEvent, self._onAnnotationCarrierModified)
    # The highlight display node is the SHARED handle: the table writes the
    # arm state / active territory / carrier binding onto it, and the
    # LayerDM-driven placement Pipeline reads them back (the widget cannot
    # reach the manager-owned Pipeline instance directly).  Aim its
    # pickSurface at the current input segmentation so the click-snap + the
    # adhering highlight resolve against the vessel mesh.
    displayNode = self._ensureHighlightDisplayNode()
    self.updateHighlightPickSurface()
    self._territoriesTable = TerritoriesTableWidget(carrier=carrier, displayNode=displayNode)
    # Bind the current input segmentation so seed rows read their structure's
    # colour + name from the start (revised ADR-0037 slice 5, §B3/§B7).
    if hasattr(self._territoriesTable, "setInputSegmentation"):
      self._territoriesTable.setInputSegmentation(self.ui.inputSurfaceSelector.currentNode())
    self.layout.addWidget(self._territoriesTable)

  def _ensureAnnotationCarrier(self):
    """Return the scene-resident annotation carrier, creating it once.

    ``None`` when the C++ node class is unavailable (a launch without the
    module's MRML library on the path) -- the caller degrades gracefully.
    """
    node = getattr(self, "_annotationCarrier", None)
    if node is not None and slicer.mrmlScene.IsNodePresent(node):
      return node
    try:
      node = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLCustomTerritoriesNode", "Vascular Territories Annotation")
    except Exception:  # noqa: BLE001 - node class not registered in this launch
      logging.warning(
        "VascularTerritories: vtkMRMLCustomTerritoriesNode unavailable -- "
        "annotation table disabled this session.")
      return None
    self._annotationCarrier = node
    return node

  def _setupRequirementsLabel(self):
    """Compose the always-visible action-requirements status line (ADR-0004).

    A wrapping ``qt.QLabel`` under the Extract / Compute buttons that
    ``_updateRequirementsMessage`` fills with the live unmet-precondition list.
    Legible plain text (ADR-0010) -- never colour alone.  Degrades gracefully
    (the panel loads without it) if label construction is unavailable.
    """
    self._requirementsLabel = None
    try:
      label = qt.QLabel()
    except Exception as exc:  # noqa: BLE001 - Qt unavailable in this launch
      logging.warning(
        "VascularTerritories: requirements status line unavailable (%s).", exc)
      return
    label.setWordWrap(True)
    label.setObjectName("VascularTerritoriesRequirementsLabel")
    self._requirementsLabel = label
    self.layout.addWidget(label)

  def enableWidgetButtons(self, state):
    # The extraction action additionally requires SlicerVMTK (ADR-0037
    # §Decision 4): never enable it when the extractor is absent, even if the
    # rest of the panel arms.
    extractionState = state and self.logic.extractionActionEnabled()
    self.ui.addCenterlineSegmentButton.setEnabled(extractionState)
    self.ui.calculateVascularTerritoryMapButton.setEnabled(state)
    self.ui.inputSurfaceSelector.setEnabled(state)

  def _updateActionEnablement(self):
    """Gate Extract + Compute on their REAL preconditions (ADR-0037 §Decision 4).

    Replaces the blanket enable-on-any-input: both actions read LIVE state so a
    surgeon cannot click an action that cannot yet run.

    * Extract centerlines: an input segmentation is selected AND SlicerVMTK is
      present (``extractionActionEnabled``) AND at least one territory has a
      STRUCTURE with >=2 seeds -- i.e. something is actually extractable (the
      SAME per-structure grouping the extraction runs on,
      ``territoryStructureSeedCounts``).  The VMTK tooltip survives when the
      extractor is absent.
    * Compute territory map: an input segmentation is selected AND a reference
      volume exists AND at least one centerline has been extracted (the
      carrier's ``CenterlineRefs`` is non-empty).

    Re-evaluated on input-surface change, a carrier ``Modified`` (seeds
    added/deleted), and the end of the extract / compute handlers.
    """
    extractUnmet, computeUnmet = self._actionRequirements()

    self.ui.addCenterlineSegmentButton.setEnabled(not extractUnmet)
    self.ui.calculateVascularTerritoryMapButton.setEnabled(not computeUnmet)

    # Affirmative "what's missing" surface (ADR-0037 §Decision 4, ADR-0010):
    # a live status line under the buttons + a comprehensive tooltip on BOTH
    # buttons enumerate the unmet preconditions, so a disabled action always
    # explains itself rather than reading dead.
    self._updateRequirementsMessage(extractUnmet, computeUnmet)

  def _hasExtractableStructure(self, segmentationNode):
    """True iff some territory has a structure with >=2 seeds (extractable).

    Uses ``territoryStructureSeedCounts`` -- the SAME per-structure grouping the
    extraction path runs on -- so the enablement and the extractor agree on what
    is extractable (ADR-0037 slice 5).
    """
    carrier = getattr(self, "_annotationCarrier", None)
    if carrier is None or segmentationNode is None:
      return False
    for territoryId in carrier.GetAnnotationTerritoryIds():
      counts = self.logic.territoryStructureSeedCounts(carrier, segmentationNode, territoryId)
      if any(count >= 2 for count in counts.values()):
        return True
    return False

  def _actionRequirements(self):
    """The UNMET preconditions for Extract + Compute, as two message lists.

    Reads the SAME live state the enablement gates read (ADR-0037 §Decision 4)
    so the messaging and the enablement cannot diverge -- the enablement is
    simply "the list is empty".  Each entry is a short, actionable,
    platform-neutral instruction (ADR-0010 legible text).

    Returns ``(extractUnmet, computeUnmet)`` -- lists of human-readable
    strings; an empty list means the action can run.
    """
    segmentationNode = self.ui.inputSurfaceSelector.currentNode()
    hasInput = segmentationNode is not None
    vmtkPresent = self.logic.extractionActionEnabled()
    carrier = getattr(self, "_annotationCarrier", None)
    hasVolume = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode") is not None
    hasCenterline = (
      carrier is not None
      and len(self.logic.getCenterlineReferenceIDs(carrier)) > 0
    )

    extractUnmet = []
    if not hasInput:
      extractUnmet.append("Select an input segmentation")
    if not vmtkPresent:
      # Keep the existing VMTK wording (the surgeon may need to install it).
      extractUnmet.append(
        "SlicerVMTK (ExtractCenterline) is not installed")
    if hasInput and not self._hasExtractableStructure(segmentationNode):
      extractUnmet.append("Place at least 2 seeds in a structure")

    computeUnmet = []
    if not hasInput:
      computeUnmet.append("Select an input segmentation")
    if not hasVolume:
      computeUnmet.append("Load a reference volume")
    if not hasCenterline:
      computeUnmet.append("Extract centerlines first")

    return extractUnmet, computeUnmet

  def _updateRequirementsMessage(self, extractUnmet, computeUnmet):
    """Surface the unmet preconditions on the status line + both button tooltips.

    ADR-0037 §Decision 4 affirmative requirements surface (ADR-0004 Python-
    composed, ADR-0010 legible a11y text): an always-visible label under the
    two buttons enumerates what is missing for each action, and BOTH buttons
    carry the same per-action unmet list as a tooltip.  Called on every
    ``_updateActionEnablement`` so the message tracks input / carrier /
    extract-compute changes live.
    """
    extractTip = (
      "Extract centerlines is ready." if not extractUnmet
      else "Extract centerlines needs:\n- " + "\n- ".join(extractUnmet))
    computeTip = (
      "Compute territory map is ready." if not computeUnmet
      else "Compute territory map needs:\n- " + "\n- ".join(computeUnmet))
    self.ui.addCenterlineSegmentButton.setToolTip(extractTip)
    self.ui.calculateVascularTerritoryMapButton.setToolTip(computeTip)

    label = getattr(self, "_requirementsLabel", None)
    if label is None:
      return
    if not extractUnmet and not computeUnmet:
      label.setText("All requirements met -- extract centerlines, then compute the map.")
      return
    lines = []
    if extractUnmet:
      lines.append("To extract centerlines: " + "; ".join(extractUnmet) + ".")
    if computeUnmet:
      lines.append("To compute the territory map: " + "; ".join(computeUnmet) + ".")
    label.setText("\n".join(lines))

  def _onAnnotationCarrierModified(self, caller, event):
    """React to a carrier edit (seeds add/delete, territory show/hide).

    Re-evaluates the Extract/Compute enablement (seed state) AND re-syncs the
    centerline visibility -- a per-territory visibility toggle writes the
    carrier's display slot, so a hidden TERRITORY must hide its centerline(s)
    too (ADR-0037 slice 5).  Deferred while a seed drag is in flight (the same
    grabbing flag the table reads): a drag relocates the grabbed seed per
    mouse-move, and none of this reacts to a coordinate change, so it runs once
    on release -- keeping the drag frame free of scan work (ADR-0037 §Decision 3).
    """
    del caller, event
    node = getattr(self, "_highlightDisplayNode", None)
    if node is not None:
      from VascularTerritoriesLib import TerritoryInteractionState as _territoryState
      if _territoryState.is_grabbing(node):
        return
    self._updateActionEnablement()
    self._syncCenterlineVisibility()

  def segmentationNodeSelected(self):
    self.ui.SegmentationShow3DButton.setEnabled(True)
    segmentationNode = self.ui.inputSurfaceSelector.currentNode()
    self.ui.SegmentationShow3DButton.setSegmentationNode(segmentationNode)
    structures = getattr(self, "_structuresTable", None)
    if structures is not None:
      structures.setSegmentationNode(segmentationNode)
    # Bind the input segmentation to the annotation table too, so each seed row
    # can read its structure's per-segment display colour + name (revised
    # ADR-0037 slice 5, §B3/§B7).
    territoriesTable = getattr(self, "_territoriesTable", None)
    if territoriesTable is not None and hasattr(territoriesTable, "setInputSegmentation"):
      territoriesTable.setInputSegmentation(segmentationNode)
    # Track the input segmentation's display node so hiding a structure hides
    # its extracted centerline(s) too (ADR-0037 slice 5, §concern anatomical
    # show/hide).  Re-aim the observer on every input change.
    self._observeInputSegmentationVisibility(segmentationNode)
    if segmentationNode is None:
      logging.warning('No segmentationNode')
      self._updateActionEnablement()
      return
    displayNode = segmentationNode.GetDisplayNode()
    displayNode.SetOpacity3D(0.3)
    # Gate the workflow actions on their real preconditions (ADR-0037
    # §Decision 4): a selected input alone no longer enables them -- Extract
    # needs an extractable >=2-seed structure, Compute needs a centerline + a
    # reference volume.
    self._updateActionEnablement()

  def createColorMap(self):
#    colorTableNodes = slicer.util.getNodes("SlicerLiverColorMap*")
#    if len(colorTableNodes) == 0:
    logging.info('Load color map from file')
    # Load the node from disk
    p = os.path.join(os.path.dirname(os.path.realpath(__file__)), "Resources/SlicerLiverColorMap.ctbl")
    self.colormap = slicer.modules.colors.logic().LoadColorFile(p)
#      slicer.mrmlScene.AddNode(self.colormap) # Creates the ID #Needed?
#    else:
#      self.colormap = list(colorTableNodes.values())[0] #else not needed?

  def cleanup(self):
    """
    Called when the application closes and the module widget is destroyed.
    """
    table = getattr(self, "_territoriesTable", None)
    if table is not None and hasattr(table, "cleanup"):
      table.cleanup()
    self.removeObservers()

  def enter(self):
    """
    Called each time the user opens this module.
    """
    # ADR-0037 §Decision 2 slice-4 module-active gate: entering auto-arms
    # NOTHING.  Placement is an explicit per-territory Place toggle in the
    # table, so no view claims an add-on-click merely from opening the module.
    # Open the module-active gate (ADR-0037 slice-5 concern #1): the
    # LayerDM-created placement Pipelines read this flag off the shared display
    # node, so an armed click only lands while VascularTerritories is active.
    node = self._ensureHighlightDisplayNode()
    if node is not None:
      from VascularTerritoriesLib import TerritoryInteractionState as _territoryState
      _territoryState.set_module_active(node, True)
    # Make sure parameter node exists and observed
    self.initializeParameterNode()

  def exit(self):
    """
    Called each time the user opens a different module.
    """
    # ADR-0037 §Decision 2 slice-4 module-active gate: disarm placement on the
    # way out so no view claims an add-on-click while VascularTerritories is
    # inactive.  Reuse the table's shared disarm body (clears the display
    # node's armed/active + hides the highlight); the follow-up rebuild
    # re-derives every Place toggle un-checked.
    table = getattr(self, "_territoriesTable", None)
    if table is not None and hasattr(table, "disarm"):
      table.disarm()
    # Close the module-active gate (ADR-0037 slice-5 concern #1): no view
    # claims an add-on-click while VascularTerritories is inactive.
    node = getattr(self, "_highlightDisplayNode", None)
    if node is not None:
      from VascularTerritoriesLib import TerritoryInteractionState as _territoryState
      _territoryState.set_module_active(node, False)
    # Do not react to parameter node changes (GUI wlil be updated when the user enters into the module)
    self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)

  def onSceneStartClose(self, caller, event):
    """
    Called just before the scene is closed.
    """
    # Parameter node will be reset, do not use it anymore
    self.setParameterNode(None)

  def onSceneEndClose(self, caller, event):
    """
    Called just after the scene is closed.
    """
    # The highlight display node + annotation carrier were cleared with the
    # scene; drop the stale handles so the next placement re-creates fresh
    # ones.
    self._highlightDisplayNode = None
    self._annotationCarrier = None
    # If this module is shown while the scene is closed then recreate a new parameter node immediately
    self.initializeParameterNode()

  def initializeParameterNode(self):
    """
    Ensure parameter node exists and observed.
    """
    # Parameter node stores all user choices in parameter values, node selections, etc.
    # so that when the scene is saved and reloaded, these settings are restored.

    self.setParameterNode(self.logic.getParameterNode())

  def setParameterNode(self, inputParameterNode):
    """
    Set and observe parameter node.
    Observation is needed because when the parameter node is changed then the GUI must be updated immediately.
    """
    if inputParameterNode:
      self.logic.setDefaultParameters(inputParameterNode)

    if inputParameterNode == self._parameterNode:
      # No change
      return

    # Unobserve previously selected parameter node and add an observer to the newly selected.
    # Changes of parameter node are observed so that whenever parameters are changed by a script or any other module
    # those are reflected immediately in the GUI.
    if self._parameterNode is not None:
      self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)
    if self._parameterNode is not None:
      self.addObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)
    self._parameterNode = inputParameterNode

    # Initial GUI update
    self.updateGUIFromParameterNode()

  def updateGUIFromParameterNode(self, caller=None, event=None):
    """
    This method is called whenever parameter node is changed.
    The module GUI is updated to show the current state of the parameter node.
    """

    # Disable all sections if no parameternode is selected
    parameterNode = self._parameterNode
    if not slicer.mrmlScene.IsNodePresent(parameterNode):
        parameterNode = None
    self.ui.segmentsCollapsibleButton.enabled = parameterNode is not None
    if parameterNode is None:
        return

    if self._parameterNode is None or self._updatingGUIFromParameterNode:
      return

    # Make sure GUI changes do not call updateParameterNodeFromGUI (it could cause infinite loop)
    self._updatingGUIFromParameterNode = True

    # Update node selectors and sliders
    for nodeSelector, roleName in self.nodeSelectors:
        nodeSelector.setCurrentNode(self._parameterNode.GetNodeReference(roleName))
    # ADR-0037 §Decision 4: the output map target is DERIVED from the carrier,
    # so the compute action gates on an input surface being selected (the
    # two-step flow: select surface -> Extract centerlines -> Compute map),
    # not on a retired output-segmentation selector.
    inputSurfaceNode = self._parameterNode.GetNodeReference("InputSurface")
    if inputSurfaceNode and inputSurfaceNode.IsA("vtkMRMLSegmentationNode"):
        self._updateActionEnablement()

    # All the GUI updates are done
    self._updatingGUIFromParameterNode = False

  def updateParameterNodeFromGUI(self, caller=None, event=None):
    """
    This method is called when the user makes any change in the GUI.
    The changes are saved into the parameter node (so that they are restored when the scene is saved and loaded).
    """

    if self._parameterNode is None or self._updatingGUIFromParameterNode:
      return

    for nodeSelector, roleName in self.nodeSelectors:
      self._parameterNode.SetNodeReferenceID(roleName, nodeSelector.currentNodeID)

    #    wasModified = self._parameterNode.StartModify()  # Modify all properties in a single batch

    #    self._parameterNode.SetNodeReferenceID("InputVolume", self.ui.inputSelector.currentNodeID)
    #    self._parameterNode.SetNodeReferenceID("OutputVolume", self.ui.outputSelector.currentNodeID)

    #    self._parameterNode.EndModify(wasModified)

  def updateExtractionActionEnablement(self):
    """Enable/disable the centerline-extraction action from the VMTK guard.

    ADR-0037 §Decision 4: the extraction action follows
    ``VascularTerritoriesLogic.extractionActionEnabled()`` (the SlicerVMTK
    ``ExtractCenterline`` module guard).  When disabled the button carries an
    explaining tooltip; placement + the table are untouched.
    """
    enabled = self.logic.extractionActionEnabled()
    tooltip = "" if enabled else (
      "Centerline extraction needs the SlicerVMTK extension "
      "(ExtractCenterline), which is not installed.")
    self.ui.addCenterlineSegmentButton.setEnabled(enabled)
    self.ui.addCenterlineSegmentButton.setToolTip(tooltip)

  def onAddCenterlineButton(self):
    self.onAddCenterlineSegment()

  def onAddCenterlineSegment(self):
    # ADR-0037 §Decision 4: the VMTK centerline feed reads the annotation
    # carrier's per-territory points, builds a TRANSIENT fiducial node inside
    # the extraction call, and discards it -- no persistent markups.  When
    # SlicerVMTK is absent the action is disabled upstream, so this only runs
    # with the extractor present.
    if not self.logic.extractionActionEnabled():
      # Belt-and-braces: the action is disabled when VMTK is absent, but
      # guard here too so a programmatic call degrades rather than crashing.
      slicer.util.errorDisplay(
        "Centerline extraction needs the SlicerVMTK extension "
        "(ExtractCenterline), which is not installed (ADR-0037 §Decision 4).")
      return
    carrier = self._ensureAnnotationCarrier()
    if carrier is None:
      return
    surfaceNode = self.ui.inputSurfaceSelector.currentNode()
    slicer.app.pauseRender()
    qt.QApplication.setOverrideCursor(qt.Qt.WaitCursor)
    try:
      self.logic.extractCenterlines(carrier, surfaceNode, "")
    finally:
      slicer.app.resumeRender()
      qt.QApplication.restoreOverrideCursor()
    # Apply the current structure visibility to the freshly-extracted
    # centerlines, and re-gate Compute now that a centerline exists (ADR-0037
    # §Decision 4 + slice 5).
    self._syncCenterlineVisibility()
    # Extracting ends the placement gesture: toggle the Place button off so a
    # stray click after extraction does not drop another seed (ADR-0037).
    self._disarmPlacement()
    self._updateActionEnablement()

  def _disarmPlacement(self):
    """Toggle the active Place button off (disarm) via the table's shared body."""
    table = getattr(self, "_territoriesTable", None)
    if table is not None and hasattr(table, "disarm"):
      table.disarm()

  def onCalculateVascularTerritoryMapButton(self):
    # ADR-0037 §Decision 4: resolve every input from the carrier +
    # inputSurfaceSelector -- the output map target is DERIVED from the
    # carrier (``TerritoryMapOutput`` role), not selected.  The retired
    # ``selectedVascularTerritorySegmId`` selector is gone.
    segmentationNode = self.ui.inputSurfaceSelector.currentNode()
    carrier = self._ensureAnnotationCarrier()
    centerlineModel = self.logic.build_centerline_model(carrier, self.colormap)
    centerlineModelPoints = centerlineModel.GetMesh()
    numberOfPoints = centerlineModelPoints.GetNumberOfPoints()
    refVolumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
    if not refVolumeNode or numberOfPoints < 2:
        # Reachable now that the button enables on input selection: give a
        # legible reason instead of an uncaught error when the surgeon computes
        # before extracting a centerline (or with no reference volume loaded).
        reason = ("no reference volume is loaded" if not refVolumeNode
                  else "no centerline has been extracted yet -- place >=2 seeds "
                       "on a vessel and click 'Extract centerlines' first")
        logging.warning("VascularTerritories: cannot compute the territory map -- %s.", reason)
        slicer.util.warningDisplay(
            f"Cannot compute the territory map: {reason}.",
            windowTitle="Vascular Territories")
        return

    vascularTerritorySegmentationNode = self.logic.ensureTerritoryMapOutput(carrier)
    # The C++ ``calculateVascularTerritoryMap`` reads + re-stamps the target's
    # ``VascularTerritories.SegmentationId``; mirror it onto the centerline
    # model as the pre-transition path did (the derived output already carries
    # the ordinal).
    segmId = vascularTerritorySegmentationNode.GetAttribute("VascularTerritories.SegmentationId")
    centerlineModel.SetAttribute("VascularTerritories.SegmentationId", segmId)

    slicer.app.pauseRender()
    qt.QApplication.setOverrideCursor(qt.Qt.WaitCursor)
    try:
       self.logic.calculateVascularTerritoryMap(vascularTerritorySegmentationNode, refVolumeNode, segmentationNode, centerlineModel, self.colormap)
       # The map output segments come from the labelmap import (named/coloured
       # by the colormap's label values); re-label + re-colour each to the
       # TERRITORY it represents so the map matches the table (ADR-0037).
       self._applyTerritoryNamesAndColors(carrier, vascularTerritorySegmentationNode)
    except ValueError:
        logging.error("Error: Failing when calculating vascular segments")

    slicer.app.resumeRender()
    qt.QApplication.restoreOverrideCursor()
    # Computing the map ends the placement gesture too: toggle Place off.
    self._disarmPlacement()
    # Re-gate the actions post-compute (ADR-0037 §Decision 4).
    self._updateActionEnablement()

  def _applyTerritoryNamesAndColors(self, carrier, mapSegmentationNode):
    """Name + colour the map's segments from their territory's display slot.

    ``calculateVascularTerritoryMap`` imports the classified labelmap, so each
    output segment's label VALUE is the territory's derived 1-based int
    (``TerritoryLabelMap``); its name/colour come from the colormap, not the
    surgeon's territory.  Re-key each segment to its territory and set the
    territory's label + colour so the map reads the same as the table
    (ADR-0037 §Decision 4 / §Decision 1 display slot).
    """
    if carrier is None or mapSegmentationNode is None:
      return
    from VascularTerritoriesLib.TerritoryLabelMap import territory_label_ints
    territoryOrder = list(carrier.GetAnnotationTerritoryIds())
    intToTerritory = {value: tid for tid, value in territory_label_ints(territoryOrder).items()}
    segmentation = mapSegmentationNode.GetSegmentation()
    for i in range(segmentation.GetNumberOfSegments()):
      segment = segmentation.GetNthSegment(i)
      territoryId = intToTerritory.get(int(segment.GetLabelValue()))
      if territoryId is None:
        continue
      label = carrier.GetTerritoryLabel(territoryId) or territoryId
      segment.SetName(label)
      color = carrier.GetTerritoryColor(territoryId)
      if color is not None:
        segment.SetColor(color[0], color[1], color[2])

class _SeedsFirstCenterlineExtractor:
  """Adapt SlicerVMTK's surface-first extractor to a seeds-first call (ADR-0037 §Decision 4).

  The Stage-3 feed drives extraction with the transient seeds node first
  (``extractCenterline(seedsNode, surfacePolyData)``) because the annotation
  carrier is the source of truth.  SlicerVMTK's
  ``ExtractCenterlineLogic.extractCenterline(surfacePolyData,
  endPointsMarkupsNode)`` takes the surface first, so this thin adapter flips
  the argument order.  It is created lazily inside ``getCenterlineLogic`` --
  the invariant tests monkeypatch that seam with their own stub, so the feed's
  transient-node / per-territory lifecycle never depends on SlicerVMTK.
  """

  def __init__(self, vmtkLogic):
    self._vmtkLogic = vmtkLogic

  def extractCenterline(self, seedsNode, surfacePolyData, *args, **kwargs):
    return self._vmtkLogic.extractCenterline(surfacePolyData, seedsNode, *args, **kwargs)


# VascularTerritoriesLogic
#

class VascularTerritoriesLogic(ScriptedLoadableModuleLogic):

  # The carrier node-reference role holding Stage-3 extracted centerline
  # models (ADR-0037 §Decision 4); paired with the ``Groupings`` map keyed on
  # the same centerline node ID.
  CENTERLINE_REFERENCE_ROLE = "CenterlineRefs"

  def __init__(self):
    ScriptedLoadableModuleLogic.__init__(self)

    self._vascularSegmentTupleList = list()
    self._centerlines = list()
    self._inputLabelMap = None
    self._outputLabelMap = None
    self.centerlineProcessingLogic = None

    from vtkSlicerVascularTerritoriesModuleLogicPython import vtkSlicerVascularTerritoriesLogic
    # Create the segmentsclassification logic
    self.scl = vtkSlicerVascularTerritoriesLogic()
    self.scl.SetMRMLScene(slicer.mrmlScene)

  def check_module_Extract_Centerline_installed(self):
    module_name = 'ExtractCenterline'
    return module_name in slicer.util.moduleNames()

  def extractionActionEnabled(self):
    """Whether the centerline-extraction action is enabled (ADR-0037 §Decision 4).

    Mirrors the ``ExtractCenterline`` module guard: True iff SlicerVMTK is
    installed.  When False the widget disables ONLY the extraction action
    (with an explaining tooltip) while placement + the table stay live --
    the legacy VMTK-hard-gate on placement is gone (ADR-0037 §Decision 4).
    """
    return bool(self.check_module_Extract_Centerline_installed())

  def getCenterlineLogic(self):
    """Return the seeds-first centerline extractor adapter (ADR-0037 §Decision 4).

    The Stage-3 feed drives the extractor with the TRANSIENT fiducial node
    first (``extractCenterline(seedsNode, surfacePolyData)``): the annotation
    carrier is the source of truth, so the seeds lead the call.  SlicerVMTK's
    ``ExtractCenterlineLogic.extractCenterline`` takes the surface first, so
    this wraps it in a thin adapter that flips the argument order -- keeping
    the feed's carrier-first convention while driving the real VMTK filter
    correctly.  The adapter is the monkeypatch seam the Stage-3 invariant
    tests replace with a stub, so the feed never depends on SlicerVMTK for
    the transient-node / per-territory lifecycle invariants.
    """
    from ExtractCenterline import ExtractCenterlineLogic
    if self.centerlineProcessingLogic is None:
      self.centerlineProcessingLogic = _SeedsFirstCenterlineExtractor(ExtractCenterlineLogic())
    return self.centerlineProcessingLogic

  def extractCenterlines(self, carrier, surfaceNode, segmentId):
    """Feed the carrier's per-territory annotation points to VMTK (ADR-0037 §Decision 4).

    For each surgeon-named territory carrying points, builds a TRANSIENT
    ``vtkMRMLMarkupsFiducialNode`` from the carrier's ordered points (via the
    pure ``build_seed_payload`` core, preserving the start-endpoint
    ``selected`` convention), runs the centerline extractor over the
    decimated input surface, wires the resulting centerline model into the
    carrier's ``CenterlineRefs`` node-reference role + ``Groupings`` map
    (keyed to the territory id -- the Stage-4 territory-map contract), and
    REMOVES the transient node.  No persistent markups survive (ADR-0037 /
    ADR-0014).  One extractor invocation + one transient node PER TERRITORY,
    never a merged node.

    :param carrier: the ``vtkMRMLCustomTerritoriesNode`` annotation carrier.
    :param surfaceNode: the closed-surface model/segmentation node the
        centerline is extracted over.
    :param segmentId: a single territory id to extract, or the empty string
        to extract every territory carrying points.
    """
    if carrier is None:
      return

    territoryIds = list(carrier.GetAnnotationTerritoryIds())
    if segmentId:
      territoryIds = [tid for tid in territoryIds if tid == segmentId]

    # Revised ADR-0037 slice 5 (multi-system): a territory may own seeds across
    # MULTIPLE disjoint structures (portal + hepatic).  Resolve the per-segment
    # closed surfaces once (each vessel segment is one coherent structure), map
    # each of a territory's seeds to the structure it is nearest, GROUP by
    # structure, and run VMTK ONCE per structure with >=2 seeds.  Portal and
    # hepatic systems are disjoint; the per-structure surface (narrowed to the
    # seed's connected component) keeps a medial path from tunnelling between
    # them.
    structures = self._perSegmentClosedSurfaces(surfaceNode)

    extractor = self.getCenterlineLogic()
    for territoryId in territoryIds:
      count = carrier.GetNumberOfAnnotationPoints(territoryId)
      if count == 0:
        continue
      points = []
      for i in range(count):
        p = carrier.GetNthAnnotationPoint(territoryId, i)
        points.append((p[0], p[1], p[2]))
      # Clear this territory's prior centerline(s) ONCE, before the structure
      # loop, then APPEND one centerline per >=2-seed structure -- so a
      # territory spanning two structures ends with two refs and re-extraction
      # replaces rather than accrues (idempotency; §B4).
      self._clearTerritoryCenterlines(carrier, territoryId)
      for structureKey, structureSurface, structurePoints in self._groupSeedsByStructure(points, structures):
        # A centerline needs at least two endpoints (one inlet + one target);
        # a structure carrying fewer seeds is under-seeded (the same threshold
        # the table flags) and is SKIPPED (the per-structure >=2 gate, §B4).
        if len(structurePoints) < 2:
          continue
        surfacePolyData = self._territorySurface(structureSurface, structurePoints[0])
        self._extractOneTerritory(
          carrier, extractor, surfacePolyData, territoryId, structurePoints, structureKey)

  def _perSegmentClosedSurfaces(self, surfaceNode):
    """The vessel structures as an ordered ``[(segmentId, surface), ...]`` list.

    Mirrors the C++ ``GetVascularSurfacePolyData`` resolution but keeps the
    per-segment SPLIT (each vascular-SCT segment's closed-surface rep) instead
    of merging them: the split is the structure identity the seed->structure
    mapping keys on (revised ADR-0037 slice 5, §B1).  A model node has no
    segment split, so it presents as a single unnamed structure carrying its
    own polydata.  Returns ``[]`` when nothing resolves.
    """
    if surfaceNode is None:
      return []
    try:
      if surfaceNode.IsA("vtkMRMLModelNode"):
        polyData = surfaceNode.GetPolyData()
        if not polyData or polyData.GetNumberOfPoints() == 0:
          return []
        return [("", polyData)]
      if not surfaceNode.IsA("vtkMRMLSegmentationNode"):
        return []
      surfaceNode.CreateClosedSurfaceRepresentation()
      structures = []
      for segId in self.scl.GetVascularSegmentIds(surfaceNode):
        mesh = vtk.vtkPolyData()
        surfaceNode.GetClosedSurfaceRepresentation(segId, mesh)
        if mesh.GetNumberOfPoints() > 0:
          structures.append((segId, mesh))
      return structures
    except Exception:  # noqa: BLE001 - degrade gracefully when resolution fails
      logging.warning(
        "VascularTerritories: per-segment vessel-surface resolution failed -- "
        "the centerline extraction is skipped (no structures to run over).")
      return []

  def _groupSeedsByStructure(self, points, structures):
    """Group a territory's ordered seeds by their nearest structure.

    Maps each seed to its structure via ``SeedStructureMapping.nearest_structure``
    over the per-segment closed surfaces, and returns ``(structureKey,
    structureSurface, points)`` triples in first-seen structure order (revised
    ADR-0037 slice 5, §B4) -- the surface AND the structure key are carried
    through so the caller need neither re-map the first seed nor re-derive the
    key for the centerline structure-id tag.  With no resolvable structures the
    whole territory is treated as one group (single-model input) so a model-node
    surface still extracts.
    """
    if not structures:
      return [(None, None, points)]
    from VascularTerritoriesLib.SeedStructureMapping import nearest_structure
    surfaces = dict(structures)
    grouped = {}
    order = []
    for point in points:
      key = nearest_structure(structures, point)
      if key not in grouped:
        grouped[key] = []
        order.append(key)
      grouped[key].append(point)
    return [(key, surfaces.get(key), grouped[key]) for key in order]

  def territoryStructureSeedCounts(self, carrier, surfaceNode, territoryId):
    """The per-structure seed counts a territory groups on (revised ADR-0037 slice 5).

    Resolves the input surface's per-segment closed surfaces once
    (``_perSegmentClosedSurfaces``), maps each of ``territoryId``'s seeds to its
    nearest structure, and returns ``{structureKey: count}`` -- the SAME
    grouping the extraction path runs on (``_groupSeedsByStructure``).  Reused
    by the extractor's >=2-per-structure gate, the table's under-seeded warning,
    and the widget's Extract-action enablement, so the three cannot diverge on
    which structures are extractable.  Returns ``{}`` when the carrier /
    territory carries no seeds.
    """
    if carrier is None or territoryId is None:
      return {}
    count = carrier.GetNumberOfAnnotationPoints(territoryId)
    if count == 0:
      return {}
    points = [
      tuple(carrier.GetNthAnnotationPoint(territoryId, i)[:3])
      for i in range(count)
    ]
    structures = self._perSegmentClosedSurfaces(surfaceNode)
    counts = {}
    for structureKey, _surface, groupPoints in self._groupSeedsByStructure(points, structures):
      counts[structureKey] = counts.get(structureKey, 0) + len(groupPoints)
    return counts

  def _territorySurface(self, structureSurface, seed):
    """The decimated single connected component of the structure's surface at ``seed``.

    Narrows ``structureSurface`` to the connected component the seed lands on --
    so a segment that accidentally carries two disjoint tubes still feeds VMTK
    one coherent tree (revised ADR-0037 slice 5, §A3/Q2) -- then triangulates +
    decimates THAT component, preserving the triangulate-before-decimate
    ordering ``preprocessAndDecimate`` enforces.  ``None`` when there is no
    structure surface (honest degradation).
    """
    if structureSurface is None or structureSurface.GetNumberOfPoints() == 0:
      return None
    try:
      from VascularTerritoriesLib.VesselConnectivity import connected_component_at
      component = connected_component_at(structureSurface, seed)
      if not component or component.GetNumberOfPoints() == 0:
        return None
      return self.preprocessAndDecimate(component)
    except Exception:  # noqa: BLE001 - degrade gracefully when preprocessing fails
      logging.warning(
        "VascularTerritories: territory-surface preprocessing failed -- the "
        "centerline extraction is skipped (no surface to run over).")
      return None

  def _preprocessedSurface(self, surfaceNode):
    """Return the decimated input-surface polydata, or ``None`` on any failure.

    Kept as the whole-surface decimation seam pinned by the surface-resolution
    invariant (``test_territories_surface_resolution`` i1); the per-territory
    extraction path resolves its own per-structure single-component surface via
    ``_perSegmentClosedSurfaces`` + ``_territorySurface`` (ADR-0037 slice 5).
    """
    if surfaceNode is None:
      return None
    try:
      surfacePolyData = self.polyDataFromNode(surfaceNode, "")
      if not surfacePolyData or surfacePolyData.GetNumberOfPoints() == 0:
        return None
      return self.preprocessAndDecimate(surfacePolyData)
    except Exception:  # noqa: BLE001 - degrade gracefully when preprocessing fails
      logging.warning(
        "VascularTerritories: input-surface preprocessing failed -- the "
        "centerline extraction is skipped (no surface to run over).")
      return None

  def _extractOneTerritory(self, carrier, extractor, surfacePolyData, territoryId, points, structureKey=None):
    """Build a transient fiducial, extract, wire the output, tear the node down.

    A None/empty ``surfacePolyData`` is NOT fed to the extractor: the real
    SlicerVMTK extractor hard-fails on it, so the territory's extraction is
    skipped with a warning (honest degradation, not a silent no-op).  The
    transient-fiducial lifecycle stays intact for the real path.  ``structureKey``
    (the input segment id the seeds grouped on) is carried through to
    ``_wireCenterlineOutput`` so the centerline model can be tagged with its
    structure for the anatomical-structure show/hide follow (ADR-0037 slice 5).
    """
    if surfacePolyData is None or surfacePolyData.GetNumberOfPoints() == 0:
      logging.warning(
        "VascularTerritories: no input surface -- cannot extract the "
        "centerline for territory %s (skipped).", territoryId)
      return
    from VascularTerritoriesLib.TransientVmtkSeeds import build_seed_payload
    payload = build_seed_payload(points)
    seedsNode = self._buildTransientFiducial(payload)
    try:
      # Carrier-first call convention (ADR-0037 §Decision 4); the adapter
      # returned by getCenterlineLogic flips to SlicerVMTK's surface-first
      # signature for the real run.
      result = extractor.extractCenterline(seedsNode, surfacePolyData)
      self._wireCenterlineOutput(carrier, territoryId, result, structureKey)
    finally:
      slicer.mrmlScene.RemoveNode(seedsNode)

  def _buildTransientFiducial(self, payload):
    """Create a throwaway fiducial node from a seed payload (ADR-0037 §Decision 4).

    Adds each ``(x, y, z, selected)`` seed IN ORDER; the inlet (index 0,
    ``selected == False``) becomes the unselected control point SlicerVMTK
    treats as the start endpoint.  The caller REMOVES the node after
    extraction -- no persistent markups (ADR-0037 / ADR-0014).
    """
    node = slicer.mrmlScene.AddNewNodeByClass(
      "vtkMRMLMarkupsFiducialNode", "TerritoryCenterlineSeeds")
    for x, y, z, selected in payload:
      index = node.AddControlPoint(vtk.vtkVector3d(x, y, z))
      node.SetNthControlPointSelected(index, bool(selected))
    return node

  def getCenterlineReferenceIDs(self, carrier):
    """The centerline model node IDs referenced by ``carrier`` (ADR-0037 §Decision 4).

    Reads the ``CenterlineRefs`` node-reference role on the annotation
    carrier -- the clean accessor for the Stage-3 extraction output, keeping
    the wrapper/carrier reference idiom (ADR-0014).  Returns a list in
    reference order.
    """
    role = self.CENTERLINE_REFERENCE_ROLE
    return [carrier.GetNthNodeReferenceID(role, i)
            for i in range(carrier.GetNumberOfNodeReferences(role))]

  #: The centerline model attribute carrying the input SEGMENT (structure) id
  #: the seeds grouped on (ADR-0037 slice 5).  The widget reads it to hide the
  #: centerline when its structure is hidden via the structures table.
  CENTERLINE_STRUCTURE_ATTRIBUTE = "VascularTerritories.StructureSegmentId"

  def _wireCenterlineOutput(self, carrier, territoryId, result, structureKey=None):
    """Wire an extracted centerline into ``CenterlineRefs`` + ``Groupings``.

    Preserves the Stage-4 territory-map contract: the centerline model is
    tagged with the territory id, referenced from the carrier's
    ``CenterlineRefs`` role, and grouped under the territory id in
    ``Groupings`` (centerline node ID -> territory id) so the downstream
    watershed scan resolves it.  A ``None`` result (the extractor stubbed to
    a no-op) wires nothing -- the transient-node lifecycle is unaffected.

    APPEND-only: the territory's PRIOR centerline state is cleared ONCE by the
    ``extractCenterlines`` caller before the per-structure loop, so this method
    only appends.  A territory spanning two structures therefore accrues one
    ref per >=2-seed structure, and re-extraction (which re-clears first)
    replaces rather than accumulates (idempotency; §B4).
    """
    centerlinePolyData = self._centerlinePolyDataFromResult(result)
    if centerlinePolyData is None:
      return
    modelNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", "TerritoryCenterline")
    modelNode.SetAndObserveMesh(centerlinePolyData)
    # Show the extracted centerline so "Extract centerlines" gives immediate
    # visual feedback (the model is otherwise a display-less data node -- the
    # gesture appeared to do nothing).  Coloured by the territory's display
    # slot when set, so a territory's per-structure centerlines read as one.
    modelNode.CreateDefaultDisplayNodes()
    displayNode = modelNode.GetDisplayNode()
    if displayNode is not None:
      displayNode.SetVisibility(True)
      displayNode.SetLineWidth(3)
      try:
        color = carrier.GetTerritoryColor(territoryId)
        if color is not None:
          displayNode.SetColor(color[0], color[1], color[2])
      except Exception:  # noqa: BLE001 - colour is best-effort feedback
        pass
    # ADR-0037 §Decision 4: tag the centerline with the DERIVED labelmap int
    # (from the carrier's territory-id order), not the old string
    # ``VascularTerritories.VascTerrId``.  The scene-scan reader that parsed
    # that string is gone (build_centerline_model now sources the carrier
    # refs), so the redundant string tag + its ``int(...)`` reader retire.
    from VascularTerritoriesLib.TerritoryLabelMap import territory_label_int
    derivedInt = territory_label_int(carrier, territoryId)
    if derivedInt is not None:
      modelNode.SetAttribute("VascularTerritories.VascTerrId", str(derivedInt))
    # Tag with the input SEGMENT (structure) id the seeds grouped on so the
    # widget can hide this centerline when its structure is hidden via the
    # structures table (ADR-0037 slice 5).  A None/empty key (single-model
    # input, no per-segment split) leaves the tag unset -- nothing to follow.
    if structureKey:
      modelNode.SetAttribute(self.CENTERLINE_STRUCTURE_ATTRIBUTE, str(structureKey))
    carrier.AddNodeReferenceID(self.CENTERLINE_REFERENCE_ROLE, modelNode.GetID())
    carrier.SetGrouping(modelNode.GetID(), territoryId)
    return modelNode

  def _clearTerritoryCenterlines(self, carrier, territoryId):
    """Drop ``territoryId``'s prior centerline refs + models + grouping entries.

    Removes every ``CenterlineRefs`` reference grouped under ``territoryId``,
    deletes the referenced model node from the scene, and rebuilds the
    ``Groupings`` map from the surviving references.  ``vtkMRMLCustomTerritories
    Node`` exposes only ``SetGrouping`` / ``ClearGroupings`` (no per-key
    removal), so the map is cleared and repopulated from the references that
    remain -- keeping the ID-keyed grouping map consistent with the refs.
    """
    role = self.CENTERLINE_REFERENCE_ROLE
    # Partition the existing refs in one pass: this territory's prior models
    # are removed from the scene; every other (id -> territory) grouping is
    # snapshotted so the rebuilt map re-uses the ids the cleared map held.
    survivors = []
    for centerlineId in self.getCenterlineReferenceIDs(carrier):
      groupTerritoryId = carrier.GetGrouping(centerlineId)
      if groupTerritoryId == territoryId:
        priorModel = slicer.mrmlScene.GetNodeByID(centerlineId)
        if priorModel is not None:
          slicer.mrmlScene.RemoveNode(priorModel)
      else:
        survivors.append((centerlineId, groupTerritoryId))
    carrier.RemoveNodeReferenceIDs(role)
    carrier.ClearGroupings()
    for centerlineId, groupTerritoryId in survivors:
      carrier.AddNodeReferenceID(role, centerlineId)
      carrier.SetGrouping(centerlineId, groupTerritoryId)

  def _centerlinePolyDataFromResult(self, result):
    """Extract the centerline polydata from an extractor return value.

    SlicerVMTK returns ``(centerlinePolyData, voronoiDiagramPolyData)``; a
    stub may return ``None`` or a bare polydata.  Tolerates each shape.
    """
    if result is None:
      return None
    if isinstance(result, (tuple, list)):
      return result[0] if result else None
    return result

  def setDefaultParameters(self, parameterNode):
    """
    Initialize parameter node with default settings.
    """

  def createCompleteCenterlineModel(self, colormap):
    nodeName = "CenterlineModel"
    completeCenterlineModelNode = slicer.mrmlScene.GetNodeByID(nodeName)
    if completeCenterlineModelNode:
        logging.error('Replacing completeCenterlineModelNode: ' + nodeName)
        slicer.mrmlScene.RemoveNode(completeCenterlineModelNode)

    completeCenterlineModelNode = slicer.mrmlScene.AddNewNodeByClassWithID('vtkMRMLModelNode', nodeName, nodeName)
    dummyPolyData = vtk.vtkPolyData()
    completeCenterlineModelNode.SetAndObservePolyData(dummyPolyData)
    if not completeCenterlineModelNode:
        logging.error('Error: Cannot create node: ' + nodeName)

    completeCenterlineModelNode.CreateDefaultDisplayNodes()
    displayNode = completeCenterlineModelNode.GetDisplayNode()
    displayNode.ScalarVisibilityOn()
    displayNode.SetActiveScalar('SegmentId', 2)
    displayNode.SetScalarRangeFlagFromString('UseColorNodeScalarRange')
    displayNode.SetLineWidth(3)
    completeCenterlineModelNode.GetDisplayNode().SetAndObserveColorNodeID(colormap.GetID())

    return completeCenterlineModelNode

  def build_centerline_model(self, carrier, colormap):
    """Assemble the summed centerline model from the carrier's centerlines.

    ADR-0037 §Decision 4: one carrier == one territory map == all its
    centerlines.  Sources the centerlines from the carrier's ``CenterlineRefs``
    node-reference role (via ``getCenterlineReferenceIDs``) + ``Groupings``
    (centerline node ID -> territory id), NOT the retired
    ``slicer.util.getNodes("*Territory*")`` scene scan or the collapsed
    ``SegmentationId`` int filter.  Each centerline is marked with the DERIVED
    labelmap int (its territory's ``index + 1`` in the carrier's id order) so
    the downstream watershed separates the territories.
    """
    from VascularTerritoriesLib.TerritoryLabelMap import territory_label_ints
    centerlineModel = self.createCompleteCenterlineModel(colormap)
    if carrier is None:
      self.scl.InitializeCenterlineSearchModel(centerlineModel)
      return centerlineModel
    labelInts = territory_label_ints(list(carrier.GetAnnotationTerritoryIds()))
    for centerlineId in self.getCenterlineReferenceIDs(carrier):
      segmentObject = slicer.mrmlScene.GetNodeByID(centerlineId)
      if segmentObject is None or not segmentObject.IsA("vtkMRMLModelNode"):
        continue
      territoryId = carrier.GetGrouping(centerlineId)
      derivedInt = labelInts.get(territoryId)
      if derivedInt is None:
        continue
      self.scl.MarkSegmentWithID(segmentObject, derivedInt)
      self.scl.AddSegmentToCenterlineModel(centerlineModel, segmentObject)
    self.scl.InitializeCenterlineSearchModel(centerlineModel)
    return centerlineModel

  # The carrier node-reference role holding the DERIVED territory-map output
  # segmentation (ADR-0037 §Decision 4): one carrier -> one output map,
  # auto-created + reused rather than selected.
  TERRITORY_MAP_OUTPUT_ROLE = "TerritoryMapOutput"

  def ensureTerritoryMapOutput(self, carrier):
    """Resolve (create + attach, or reuse) the carrier's territory-map output.

    ADR-0037 §Decision 4: the output map target is DERIVED from the carrier,
    not selected -- the carrier's ``TerritoryMapOutput`` node-reference role
    resolves to exactly one ``vtkMRMLSegmentationNode``.  On the first call it
    is minted, attached, and stamped with a per-carrier ordinal in
    ``VascularTerritories.SegmentationId`` (the int the C++
    ``calculateVascularTerritoryMap`` reads + re-stamps).  Subsequent calls
    reuse the same node -- one carrier == one map.  The ordinal is stable per
    carrier and distinct across carriers: it is issued as one past the maximum
    ordinal already stamped on any segmentation in the scene, so two carriers
    never collide.
    """
    if carrier is None:
      return None
    role = self.TERRITORY_MAP_OUTPUT_ROLE
    existing = carrier.GetNodeReference(role)
    if existing is not None and existing.IsA("vtkMRMLSegmentationNode"):
      return existing
    target = slicer.mrmlScene.AddNewNodeByClass(
      "vtkMRMLSegmentationNode", "Vascular Territory Map")
    if target is None:
      return None
    target.SetAttribute(
      "VascularTerritories.SegmentationId", str(self._nextSegmentationOrdinal()))
    carrier.SetNodeReferenceID(role, target.GetID())
    return target

  def _nextSegmentationOrdinal(self):
    """Return one past the max ``SegmentationId`` ordinal stamped in the scene.

    Scanning every segmentation's ``VascularTerritories.SegmentationId`` keeps
    two carriers from colliding: whichever computes second sees the first's
    ordinal and issues the next one (ADR-0037 §Decision 4).
    """
    maxOrdinal = 0
    segmentations = slicer.mrmlScene.GetNodesByClass("vtkMRMLSegmentationNode")
    segmentations.InitTraversal()
    node = segmentations.GetNextItemAsObject()
    while node is not None:
      stamped = node.GetAttribute("VascularTerritories.SegmentationId")
      try:
        maxOrdinal = max(maxOrdinal, int(stamped))
      except (TypeError, ValueError):
        pass
      node = segmentations.GetNextItemAsObject()
    return maxOrdinal + 1

  def calculateVascularTerritoryMap(self, vascularTerritorySegmentationNode, refVolume, segmentation, centerlineModel, colormap):
    self.scl.calculateVascularTerritoryMap(vascularTerritorySegmentationNode, refVolume, segmentation, centerlineModel, colormap)

  def preprocessAndDecimate(self, surfacePolyData):
    processedPolyData = vtk.vtkPolyData()
    self.scl.preprocessAndDecimate(surfacePolyData, processedPolyData)
    return processedPolyData

  def decimateLine(self, polyDataLine):
    decimate = vtk.vtkDecimatePolylineFilter()
    decimate.SetInputData(polyDataLine)
    decimate.SetTargetReduction(.90)
    decimate.Update()
    return decimate.GetOutput()

  #Using code from SlicerExtension-VMTK
  #https://github.com/vmtk/SlicerExtension-VMTK/blob/master/ExtractCenterline/ExtractCenterline.py
  def polyDataFromNode(self, surfaceNode, segmentId):
    if not surfaceNode:
        logging.error("Invalid input surface node")
        return None
    if surfaceNode.IsA("vtkMRMLModelNode"):
        return surfaceNode.GetPolyData()
    elif surfaceNode.IsA("vtkMRMLSegmentationNode"):
        # ``segmentId`` here carries the feed's TERRITORY semantics (or the
        # empty string == "every territory"), NOT a segmentation *segment*
        # id -- so it must never be handed straight to
        # GetClosedSurfaceRepresentation, which would resolve no segment and
        # yield a zero-point mesh.  Converge on the SAME whole-vessel-tree
        # resolution the pick/highlight path uses
        # (VesselHighlightWiring.closed_surface_polydata): every segment's
        # closed surface appended into one mesh, so placement-snap sees the
        # whole vessel surface.  The centerline EXTRACTION path no longer uses
        # this merge -- it groups a territory's seeds by structure and narrows
        # each per-structure surface to the seed's connected component via
        # _perSegmentClosedSurfaces + _territorySurface (ADR-0037 slice 5).
        # ``None`` when the segmentation carries no segment geometry.
        from VascularTerritoriesLib.VesselHighlightWiring import closed_surface_polydata
        return closed_surface_polydata(surfaceNode)
    else:
        logging.error("Unsupported input surface node type")
        return None

class VascularTerritoriesTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  Uses ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear(0)

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_VascularTerritories1()

  def test_VascularTerritories1(self):
    """ Ideally you should have several levels of tests.  At the lowest level
    tests should exercise the functionality of the logic with different inputs
    (both valid and invalid).  At higher levels your tests should emulate the
    way the user would interact with your code and confirm that it still works
    the way you intended.
    One of the most important features of the tests is that it should alert other
    developers when their changes will have an impact on the behavior of your
    module.  For example, if a developer removes a feature that you depend on,
    your test should break so they know that the feature is needed.
    """

    self.delayDisplay("Starting the test")

    # Get/create input data

    # Test the module logic

    VascularTerritoriesLogic()

    self.delayDisplay('Test passed')

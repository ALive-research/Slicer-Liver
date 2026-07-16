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
    self._updatingGUIFromSegmentationNode = False
    # Vessel-adhering-highlight wiring (ADR-0037).  A single scene-resident
    # ``vtkMRMLTerritoriesHighlightDisplayNode`` whose ``pickSurface``
    # reference tracks the input segmentation and whose Visibility gates
    # the hover Pipeline's paint (live only during marker placement).
    self._highlightDisplayNode = None
    ScriptedLoadableModuleWidget.__init__(self, parent)
    VTKObservationMixin.__init__(self)  # needed for parameter node observation

  def setup(self):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.setup(self)

    # ADR-0013 §5 call 3 — register the LayerDM Pipeline creator for the
    # vessel-adhering highlight (``vtkMRMLTerritoriesHighlightDisplayNode``).
    # The Pipeline class is Python (ADR-0004 §1); one Pipeline per
    # display-node type (ADR-0013 §1).  Registration is idempotent (a
    # module-level flag inside the creator).  Guarded: in a launch without
    # the SlicerLayerDisplayableManager extension on the module path,
    # ``LayerDMLib`` is unreachable — log loudly (ADR-0002 makes LayerDM a
    # hard runtime dependency) but let the rest of setup continue.
    self._registerVesselHighlightPipeline()
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
    self.nodeSelectors = [
        (self.ui.inputSurfaceSelector, "InputSurface"),
        (self.ui.selectedVascularTerritorySegmId, "VascularTerritorySegmentation")
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
    self.ui.inputSegmentSelectorWidget.connect('currentSegmentChanged(QString)', self.updateParameterNodeFromGUI)
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)
    self.ui.inputSurfaceSelector.connect('currentNodeChanged(bool)', self.segmentationNodeSelected)
    self.ui.selectedVascularTerritorySegmId.connect('currentNodeChanged(bool)', self.updateParameterNodeFromGUI)
    self.ui.selectedVascularTerritorySegmId.connect('currentNodeChanged(bool)', self.vascular_territory_segmentationNodeSelected)

    # Vessel-adhering-highlight wiring (ADR-0036 / ADR-0037).  Keep the
    # highlight node's pickSurface aimed at the selected input segmentation.
    # ADR-0037 Stage-2 retires the markups selector + place widget that used
    # to also gate the highlight's visibility on place mode; the surviving
    # invariant is ``updateHighlightPickSurface`` tracking the input
    # segmentation.
    self.ui.inputSurfaceSelector.connect('currentNodeChanged(bool)', self.updateHighlightPickSurface)

    # ADR-0037 Stage-2 table (§Decision 3): the annotation table is composed
    # into the panel here, over the annotation carrier + the placement
    # Pipeline (Python-widget composition, ADR-0004).
    self._setupTerritoriesTable()

    self.ui.selectedVascularTerritorySegmId.setNodeTypeLabel('Vascular Territory Segmentation', 'vtkMRMLSegmentationNode')
    self.ui.selectedVascularTerritorySegmId.addAttribute("vtkMRMLSegmentationNode", "VascularTerritories.SegmentationId")

    # Initialize Vascular Territory Segmentation button at widget start-up
#    nodeNameID = 'Vascular_Territory_Segmentation'
#    vasc_terr_segm_node = slicer.mrmlScene.GetNodeByID(nodeNameID)
#    if not vasc_terr_segm_node:
#      vasc_terr_segm_node = slicer.mrmlScene.AddNewNodeByClassWithID('vtkMRMLSegmentationNode', nodeNameID, nodeNameID)
#    self.ui.selectedVascularTerritorySegmId.setCurrentNodeID(nodeNameID)

    #TODO: Store all GUI settings
    # These connections ensure that whenever user changes some settings on the GUI, that is saved in the MRML scene
    # (in the selected parameter node).
    #        self.ui.inputSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)

    # Buttons
    self.ui.calculateVascularTerritoryMapButton.connect('clicked(bool)', self.onCalculateVascularTerritoryMapButton)
    self.ui.addCenterlineSegmentButton.connect('clicked(bool)', self.onAddCenterlineButton)
    self.ui.addSegmentationButton.connect('clicked(bool)', self.onAddSegmentationButton)
    self.ui.ColorPickerButton.connect('colorChanged(QColor)', self.onColorChanged)
    self.ui.showHideButton.connect('clicked(bool)', self.onShowHideButton)

    #self.enableWidgetButtons(False)
    # Make sure parameter node is initialized (needed for module reload)
    self.initializeParameterNode()

  def _registerVesselHighlightPipeline(self):
    """Register the vessel-adhering-highlight LayerDM Pipeline creator.

    ADR-0013 §5 call 3.  Idempotent; a missing LayerDMLib is a real
    configuration error under ADR-0002 so it logs at ``critical``, but the
    rest of widget setup continues.
    """
    try:
      from VascularTerritoriesLib import registerVesselHighlightPipelineCreator
      if registerVesselHighlightPipelineCreator is None:
        raise ImportError("registerVesselHighlightPipelineCreator unavailable")
      registerVesselHighlightPipelineCreator()
    except ImportError as exc:
      logging.critical(
        "VascularTerritories: vessel-adhering-highlight LayerDM Pipeline "
        "creator not registered (%s) -- the highlight is disabled in this "
        "session.  Loading the SlicerLayerDisplayableManager extension is "
        "required for the Pipeline path (ADR-0013).", exc)

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
      node = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLTerritoriesHighlightDisplayNode", "Vessel Highlight")
    except Exception:  # noqa: BLE001 - node class not registered in this launch
      logging.warning(
        "VascularTerritories: vtkMRMLTerritoriesHighlightDisplayNode "
        "unavailable -- vessel highlight disabled this session.")
      return None
    if node is None:
      return None
    node.SetVisibility(False)  # off until place mode turns it on
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
    # The highlight display node is the SHARED handle: the table writes the
    # arm state / active territory / carrier binding onto it, and the
    # LayerDM-driven placement Pipeline reads them back (the widget cannot
    # reach the manager-owned Pipeline instance directly).  Aim its
    # pickSurface at the current input segmentation so the click-snap + the
    # adhering highlight resolve against the vessel mesh.
    displayNode = self._ensureHighlightDisplayNode()
    self.updateHighlightPickSurface()
    self._territoriesTable = TerritoriesTableWidget(carrier=carrier, displayNode=displayNode)
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

  def enableWidgetButtons(self, state):
    self.ui.addSegmentationButton.setEnabled(state)
    self.ui.addCenterlineSegmentButton.setEnabled(state)
    self.ui.calculateVascularTerritoryMapButton.setEnabled(state)
    self.ui.inputSurfaceSelector.setEnabled(state)
    self.ui.vascularTerritoryId.setEnabled(state)
    self.ui.showHideButton.setEnabled(state)

  def segmentationNodeSelected(self):
    self.ui.SegmentationShow3DButton.setEnabled(True)
    segmentationNode = self.ui.inputSurfaceSelector.currentNode()
    self.ui.SegmentationShow3DButton.setSegmentationNode(segmentationNode)
    if segmentationNode is None:
      logging.warning('No segmentationNode')
      return
    displayNode = segmentationNode.GetDisplayNode()
    displayNode.SetOpacity3D(0.3)
    self.updateShowHideButtonText()

  def onShowHideButton(self):
    displayNode, segmentId = self.getDisplayNodeAndSegmentId()
    if displayNode is None:
      return
    if self.ui.showHideButton.isChecked() is True:
      displayNode.SetSegmentVisibility(segmentId, True)
    else:
      displayNode.SetSegmentVisibility(segmentId, False)
    self.updateShowHideButtonText()

  def refreshShowHideButton(self):
    displayNode, segmentId = self.getDisplayNodeAndSegmentId()
    if displayNode is None:
      return
    self.ui.showHideButton.setChecked(displayNode.GetSegmentVisibility(segmentId))
    self.updateShowHideButtonText()

  def getDisplayNodeAndSegmentId(self):
    surface = self.ui.inputSurfaceSelector.currentNode()
    if surface is None:
      return None, None
    displayNode = surface.GetDisplayNode()
    if displayNode is None:
      return None, None
    return displayNode, self.ui.inputSegmentSelectorWidget.currentSegmentID()

  def updateShowHideButtonText(self):
    if self.ui.showHideButton.isChecked() is True:
      self.ui.showHideButton.setText('Hide')
      self.ui.showHideButton.setIcon(qt.QIcon("Icons/VisibleOn.png"))
    else:
      self.ui.showHideButton.setText('Show')
      self.ui.showHideButton.setIcon(qt.QIcon("Icons/VisibleOff.png"))

  def vascular_territory_segmentationNodeSelected(self):
    self._updatingGUIFromSegmentationNode = True
    count = self.ui.selectedVascularTerritorySegmId.nodeCount()
    if count <= 0:
      self.enableWidgetButtons(False)
      self._updatingGUIFromSegmentationNode = False
      return
    else:
      self.enableWidgetButtons(True)

    segmId = self.ui.selectedVascularTerritorySegmId.currentNode().GetAttribute("VascularTerritories.SegmentationId")

    vasc_terr_segmentationNode = self.ui.selectedVascularTerritorySegmId.currentNode()
    vascularTerrSegm = vasc_terr_segmentationNode.GetSegmentation()

    if vasc_terr_segmentationNode is None:
      logging.warning('No vascular territory segmentationNode')
      self._updatingGUIFromSegmentationNode = False
      return
    if not segmId:
      segmId = count
      firstSegmentID = 'Vascular Territory ID 1'
      vascularTerrSegm.AddEmptySegment(firstSegmentID, firstSegmentID)

    vasc_terr_segmentationNode.SetAttribute("VascularTerritories.SegmentationId", str(segmId))

    segmentationNodeName = vasc_terr_segmentationNode.GetName()
    vasc_terr_ID_combox = self.ui.vascularTerritoryId

    if 'Vascular_Territory_Segmentation' in segmentationNodeName:
      self.enableWidgetButtons(True)
    else:
      self.enableWidgetButtons(False)

    self.updateVascTerrList(vasc_terr_ID_combox, vasc_terr_segmentationNode)
    self.ui.vascularTerritoryId.setCurrentIndex(1)
    displayNode = vasc_terr_segmentationNode.GetDisplayNode()
    if displayNode:
      displayNode.SetOpacity3D(0.3)
    self.updateShowHideButtonText()
    # Visualisation of centerline segments
    centerlineSegments = slicer.util.getNodesByClass('vtkMRMLModelNode')
    for centerlineSegment in centerlineSegments:
      SegmIdAttribute = centerlineSegment.GetAttribute("VascularTerritories.SegmentationId")
      if SegmIdAttribute == segmId:
        centerlineSegment.GetDisplayNode().VisibilityOn()
      else:
        centerlineSegment.GetDisplayNode().VisibilityOff()
    # Visualisation of Vascular Territories
    segmentationNodes = slicer.util.getNodesByClass('vtkMRMLSegmentationNode')
    self._updatingGUIFromSegmentationNode = False
    for node in segmentationNodes:
      attribute = node.GetAttribute("VascularTerritories.SegmentationId")
      if attribute is not None:
        if node.GetDisplayNode():
          node.GetDisplayNode().SetAllSegmentsVisibility(False)


  def updateVascTerrList(self, vasc_terr_ID_list, vascular_territory_segm_node):
    segmentNames = []
    segmentIds = vascular_territory_segm_node.GetSegmentation().GetSegmentIDs()
    for id in segmentIds:
      segmentName = vascular_territory_segm_node.GetSegmentation().GetSegment(id).GetName()
      segmentNames.append(segmentName)

    vasc_terr_ID_list.blockSignals(True)
    vasc_terr_ID_list.clear()
    initString = 'Create new territory ID'
    vasc_terr_ID_list.addItem(initString)
    firstSegmentName = 'Vascular Territory ID 1'
    if firstSegmentName not in segmentNames:
      # No vascular territory segmentations
      return
    #Start populating Vascular Territory list
    index = 0
    for nameString in segmentNames:
      index = index+1
      vasc_terr_ID_list.addItem(nameString)
      self.colormap.SetColorName(index, nameString)
      vasc_terr_ID_list.setCurrentIndex(index)
    vasc_terr_ID_list.setCurrentIndex(1)
    vasc_terr_ID_list.blockSignals(False)

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
    # Make sure parameter node exists and observed
    self.initializeParameterNode()

  def exit(self):
    """
    Called each time the user opens a different module.
    """
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
    inputSurfaceNode = self._parameterNode.GetNodeReference("InputSurface")
    if inputSurfaceNode and inputSurfaceNode.IsA("vtkMRMLSegmentationNode"):
        self.ui.inputSegmentSelectorWidget.setCurrentSegmentID(self._parameterNode.GetParameter("InputSegmentID"))
    vascularTerritorySegmNode = self._parameterNode.GetNodeReference("VascularTerritorySegmentation")
    if vascularTerritorySegmNode and vascularTerritorySegmNode.IsA("vtkMRMLSegmentationNode"):
        self.enableWidgetButtons(True)

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

    inputSurfaceNode = self._parameterNode.GetNodeReference("InputSurface")
    if inputSurfaceNode and inputSurfaceNode.IsA("vtkMRMLSegmentationNode"):
        self._parameterNode.SetParameter("InputSegmentID", self.ui.inputSegmentSelectorWidget.currentSegmentID())

    self.ui.inputSegmentSelectorWidget.setCurrentSegmentID(self._parameterNode.GetParameter("InputSegmentID"))
    self.ui.inputSegmentSelectorWidget.setVisible(inputSurfaceNode and inputSurfaceNode.IsA("vtkMRMLSegmentationNode"))

    #    wasModified = self._parameterNode.StartModify()  # Modify all properties in a single batch

    #    self._parameterNode.SetNodeReferenceID("InputVolume", self.ui.inputSelector.currentNodeID)
    #    self._parameterNode.SetNodeReferenceID("OutputVolume", self.ui.outputSelector.currentNodeID)

    #    self._parameterNode.EndModify(wasModified)

  def getPreprocessedPolyData(self):
    surface = self.ui.inputSurfaceSelector.currentNode()
    segmentId = self.ui.inputSegmentSelectorWidget.currentSegmentID()

    inputSurfacePolyData = self.logic.polyDataFromNode(surface, segmentId)
    if not inputSurfacePolyData or inputSurfacePolyData.GetNumberOfPoints() == 0:
        raise ValueError("Valid input surface is required")

    preprocessedPolyData = self.logic.preprocessAndDecimate(inputSurfacePolyData)
    return preprocessedPolyData

  def createCenterlineNode(self, endPointsMarkupsNode):
    nodeName = endPointsMarkupsNode.GetName()
    centerlineModelNode = slicer.mrmlScene.GetNodeByID(nodeName)
    if centerlineModelNode:
      logging.info('Adding to existing centerlineModelNode')
      #slicer.mrmlScene.RemoveNode(centerlineModelNode)
    else:
      centerlineModelNode = slicer.mrmlScene.AddNewNodeByClassWithID('vtkMRMLModelNode', nodeName, nodeName)

    if not centerlineModelNode:
        raise ValueError('Error: Cannot create node: ', nodeName)

    self.logic.copyIndex(endPointsMarkupsNode, centerlineModelNode)
    return centerlineModelNode

  def getCurrentColor(self):
    color = [1, 1, 1, 1]
    index = self.ui.vascularTerritoryId.currentIndex
    if (index > 0):
      self.colormap.GetColor(index, color)
    del color[3:]
    return color

  def getCurrentColorQt(self):
    color = self.getCurrentColor()
    color255 = [int(i * 255) for i in color]
    qtColor = qt.QColor(color255[0], color255[1], color255[2])
    return qtColor

  def useColorFromSelector(self, centerlineModelNode):
    inputColor = self.getCurrentColorQt()
    centerlineModelNode.GetDisplayNode().SetColor(inputColor.redF(), inputColor.greenF(), inputColor.blueF())

  def onColorChanged(self):
    colorIndex = self.ui.vascularTerritoryId.currentIndex
    color = self.ui.ColorPickerButton.color
    if(colorIndex > 0):
      self.colormap.SetColor(colorIndex, color.redF(), color.greenF(), color.blueF()) #Update index color in colormap.

  def onAddCenterlineButton(self):
    self.onAddCenterlineSegment()

  def onAddSegmentationButton(self):
    self.onAddCenterlineSegment(addSegmentationInsteadOfLine = True)

  def onAddCenterlineSegment(self, addSegmentationInsteadOfLine = False):
    # ADR-0037 §Decision 4: the VMTK centerline feed is rewired off Slicer
    # markups onto the annotation carrier in Stage 3 -- the extraction call
    # builds a TRANSIENT fiducial node from the carrier's points inside the
    # call and discards it.  With the Stage-2 markups-selector retirement the
    # legacy markups-sourced feed is gone; the extraction action is inert
    # until the Stage-3 carrier feed lands.
    del addSegmentationInsteadOfLine
    slicer.util.errorDisplay(
      "Centerline extraction from the annotation carrier is not available "
      "yet -- it lands with the VMTK feed transition (ADR-0037 Stage 3).")

  def mergePolydata(self, existingPolyData, newPolyData):
    combinedPolyData = vtk.vtkAppendPolyData()
    combinedPolyData.AddInputData(existingPolyData)
    combinedPolyData.AddInputData(newPolyData)
    combinedPolyData.Update()
    return combinedPolyData.GetOutput()

  def onCalculateVascularTerritoryMapButton(self):
    segmentationNode = self.ui.inputSurfaceSelector.currentNode()
    vascTerrSegmentationId = int(self.ui.selectedVascularTerritorySegmId.currentNode().GetAttribute("VascularTerritories.SegmentationId"))
    centerlineModel = self.logic.build_centerline_model(self.colormap, vascTerrSegmentationId)
    centerlineModelPoints = centerlineModel.GetMesh()
    numberOfPoints = centerlineModelPoints.GetNumberOfPoints()
    refVolumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
    if not (refVolumeNode) or (numberOfPoints<2):
        raise ValueError("Missing inputs to calculate vascular segments")

    slicer.app.pauseRender()
    qt.QApplication.setOverrideCursor(qt.Qt.WaitCursor)
    vascularTerritorySegmentationNode = self.ui.selectedVascularTerritorySegmId.currentNode()
    segmId = vascularTerritorySegmentationNode.GetAttribute("VascularTerritories.SegmentationId")
    centerlineModel.SetAttribute("VascularTerritories.SegmentationId", segmId)

    try:
       self.logic.calculateVascularTerritoryMap(vascularTerritorySegmentationNode, refVolumeNode, segmentationNode, centerlineModel, self.colormap)
    except ValueError:
        logging.error("Error: Failing when calculating vascular segments")


    slicer.app.resumeRender()
    qt.QApplication.restoreOverrideCursor()

# VascularTerritoriesLogic
#

class VascularTerritoriesLogic(ScriptedLoadableModuleLogic):

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

  def getCenterlineLogic(self):
    """
    Get the centerline logic. If the logic wasn't yet instantiated it does it
    """
    from ExtractCenterline import ExtractCenterlineLogic
    if self.centerlineProcessingLogic is None:
      self.centerlineProcessingLogic = ExtractCenterlineLogic()
    return self.centerlineProcessingLogic

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

  def build_centerline_model(self, colormap, vascSegmSelected):
    centerlineModel = self.createCompleteCenterlineModel(colormap)
    centerlineSegmentsDict = slicer.util.getNodes("*Territory*")
    for name, segmentObject in centerlineSegmentsDict.items():
      if segmentObject.GetClassName() == "vtkMRMLModelNode":
        VascTerrId = int(segmentObject.GetAttribute("VascularTerritories.VascTerrId"))
        VascTerrSegmId = int(segmentObject.GetAttribute("VascularTerritories.SegmentationId"))
        if VascTerrSegmId == vascSegmSelected:
          self.scl.MarkSegmentWithID(segmentObject, VascTerrId)
          self.scl.AddSegmentToCenterlineModel(centerlineModel, segmentObject)
    self.scl.InitializeCenterlineSearchModel(centerlineModel)
    return centerlineModel

  def calculateVascularTerritoryMap(self, vascularTerritorySegmentationNode, refVolume, segmentation, centerlineModel, colormap):
    self.scl.calculateVascularTerritoryMap(vascularTerritorySegmentationNode, refVolume, segmentation, centerlineModel, colormap)

  def copyIndex(self, endPointsMarkupsNode, centerlineModelNode):
    centerlineModelNode.SetAttribute("VascularTerritories.VascTerrId", endPointsMarkupsNode.GetAttribute("VascularTerritories.VascTerrId"))

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
        # Segmentation node
        polyData = vtk.vtkPolyData()
        surfaceNode.CreateClosedSurfaceRepresentation()
        surfaceNode.GetClosedSurfaceRepresentation(segmentId, polyData)
        return polyData
    else:
        logging.error

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

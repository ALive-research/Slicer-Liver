# ==============================================================================
#
#  Distributed under the OSI-approved BSD 3-Clause License.
#
#   Copyright (c) 2023-2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
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
#   This file was originally developed by Ruoyan Meng (NTNU) through the
#   ALive project (grant nr. 311393).
#
# ==============================================================================

# ruff: noqa: F403, F405  # standard Slicer scripted-module wildcard-import pattern



import logging
import vtk
import qt
import slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin

# The seed carrier / display node the placement writes to (ADR-0038-amendment
# seeds-off-markups migration); the interaction state rides the display node via
# the shared PointPlacementState namespaced ``LiverVolumetry.*``
# (feedback_layerdm_state_on_display_node).
SEEDS_NODE_CLASS = "vtkMRMLVolumetrySeedsNode"
SEEDS_DISPLAY_NODE_CLASS = "vtkMRMLVolumetrySeedsDisplayNode"
SEEDS_STORAGE_NODE_CLASS = "vtkMRMLVolumetrySeedsStorageNode"
VOLUMETRY_NAMESPACE = "LiverVolumetry"


#
# LiverVolumetry
#

class LiverVolumetry(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Calculate Liver Volumetry"
    self.parent.categories = [""]
    self.parent.dependencies = []
    self.parent.contributors = ["Ruoyan Meng (NTNU)",
                                "Ole Vegard Solberg (SINTEF)",
                                "Geir Arne Tangen (SINTEF)",
                                "Rafael Palomar (OUS)",
                                "Javier Pérez de Frutos (SINTEF)"]
    self.parent.helpText = """
    This module provides tools and functionality for calculating Liver Volumetry.
    """
    self.parent.acknowledgementText = """
    """  # TODO: replace with organization, grant and thanks.

    # Register the seed-carrier MRML node classes at module-discovery time
    # (ADR-0013 §5 call 1) so ``slicer.mrmlScene.AddNewNodeByClass(
    # "vtkMRMLVolumetrySeedsNode", ...)`` works from any test, batch-mode
    # script, or other module's setup callback -- not only after the widget is
    # first opened.  The generic ``vtkLiverVolumetryLogic`` is a plain
    # vtkObject with no scene observer (ADR-0015 keeps it unchanged), so the
    # registration lives here in Python, not in a C++ RegisterNodes.
    if not slicer.app.commandOptions().noMainWindow:
      slicer.app.connect("startupCompleted()", self._registerSeedNodeClasses)
    else:
      # ``--no-main-window`` skips Slicer's normal startup sequence so the
      # ``startupCompleted`` signal never fires; register immediately so
      # headless / test invocations still have the classes available.
      self._registerSeedNodeClasses()

    #Hide module, so that it only shows up in the Liver module, and not as a separate module
    parent.hidden = True

  def _registerSeedNodeClasses(self):
    """Register the seed carrier / display / storage node classes (ADR-0013 §5 call 1).

    Instantiates each wrapped C++ prototype and hands it to
    ``RegisterNodeClass`` so ``AddNewNodeByClass`` resolves it.  A launch
    without the module's MRML library on the path (the class import fails)
    degrades gracefully -- the placement feature is disabled that session.
    """
    try:
      from slicer import (
        vtkMRMLVolumetrySeedsNode,
        vtkMRMLVolumetrySeedsDisplayNode,
        vtkMRMLVolumetrySeedsStorageNode,
      )
    except ImportError as exc:
      logging.warning(
        "LiverVolumetry: seed MRML node classes unavailable (%s) -- seed "
        "placement is disabled this session.  This usually means the module "
        "MRML library failed to build or its Python wrapping is not on the "
        "launcher's --additional-module-paths.", exc)
      return
    scene = slicer.mrmlScene
    for cls in (vtkMRMLVolumetrySeedsNode,
                vtkMRMLVolumetrySeedsDisplayNode,
                vtkMRMLVolumetrySeedsStorageNode):
      scene.RegisterNodeClass(cls())


#
# Register sample data sets in Sample Data module
#
class LiverVolumetryWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
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
    # The scene-resident seed carrier + its shared data-only display node
    # (ADR-0038-amendment): the arm state / carrier binding / pick-surface ride
    # the display node, and the LayerDM-driven placement Pipelines read them
    # back (feedback_layerdm_state_on_display_node).  Created lazily; dropped on
    # scene close.
    self._seedsCarrier = None
    self._seedsDisplayNode = None
    # The carrier-backed seeds table (ADR-0038 §Conformance): one row per seed
    # with an editable label (the generated segment name), a colour swatch, and
    # a delete affordance.  Composed into the panel in ``setup`` and bound to
    # the carrier once it exists; dropped on scene close.
    self._seedsTable = None
    ScriptedLoadableModuleWidget.__init__(self, parent)
    VTKObservationMixin.__init__(self)  # needed for parameter node observation

  def setup(self):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.setup(self)

    # Register the LayerDM Pipeline creators (ADR-0013 §5 call 3): ONE 3D +
    # ONE slice pipeline for the seed display-node type, each wired to the flat
    # volumetry provider + the in-volume pick.  No custom displayable manager
    # (ADR-0013 §5 / feedback_layerdm_no_custom_dm).  Idempotent; guarded
    # against an unreachable LayerDMLib.
    self._registerSeedPlacementPipelines()

    # Load widget from .ui file (created by Qt Designer)
    liverVolumetryWidget = slicer.util.loadUI(self.resourcePath('UI/LiverVolumetryWidget.ui'))
    self.layout.addWidget(liverVolumetryWidget)

    # Add a spacer at the botton to keep the UI flowing from top to bottom
    spacerItem = qt.QSpacerItem(0,0, qt.QSizePolicy.Minimum, qt.QSizePolicy.MinimumExpanding)
    self.layout.addSpacerItem(spacerItem)

    self.ui = slicer.util.childWidgetVariables(liverVolumetryWidget)

    self.nodeSelectors = [
      (self.ui.InputSegmentationSelector, "inputSegmentation")
    ]

    # Set scene in MRML widgets. Make sure that in Qt designer
    # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
    # "setMRMLScene(vtkMRMLScene*)" slot.
    liverVolumetryWidget.setMRMLScene(slicer.mrmlScene)

    # Create logic class. Logic implements all computations that should be possible to run
    # in batch mode, without a graphical user interface.
    self.logic = LiverVolumetryLogic()
    self.setParameterNode(self.logic.getParameterNode())

    # Connections
    self.ui.VolumeTableSelectorWidget.connect('currentNodeChanged(vtkMRMLNode*)', self.onVolumetryParameterChanged)
    self.ui.ReferenceVolumeSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.onVolumetryParameterChanged)
    self.ui.InputSegmentationSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.onVolumetryParameterChanged)
    self.ui.InputSegmentationSelector.connect('currentNodeChanged(bool)', self.updateParameterNodeFromGUI)
    self.ui.InputSegmentationSelector.connect('currentNodeChanged(bool)', self.segmentationNodeSelected)
    self.ui.InputSegmentSelectorWidget.connect('segmentSelectionChanged(QStringList)', self.updateParameterNodeFromGUI)
    self.ui.InputSegmentSelectorWidget.connect('segmentSelectionChanged(QStringList)', self.onSegmentChanged)
    self.ui.InputSegmentSelectorWidget.connect('segmentSelectionChanged(QStringList)', self.onVolumetryParameterChanged)
    self.ui.TargetSegmentationSelectorWidget.connect('segmentSelectionChanged(QStringList)', self.updateParameterNodeFromGUI)
    self.ui.ComputeVolumePushButton.connect('clicked(bool)', self.onComputeAdvancedVolumeButtonClicked)
    self.ui.GenerateSegmentsPushButton.connect('clicked(bool)', self.onGenerateSegmentsButtonClicked)
    self.ui.ResectionTargetNodeComboBox.connect('currentNodeChanged(vtkMRMLNode*)', self.onGenerateSegmentsParameterChanged)
    # ADR-0038-amendment: the ROIMarkersList fiducial selector + place widget
    # are RETIRED; placement is the arm toggle below, driving the seed carrier
    # through the shared base pipeline.
    self.ui.AddSeedsButton.connect('toggled(bool)', self.onAddSeedsToggled)

    # Compose the carrier-backed seeds table into the panel (ADR-0004: the
    # panel is Python).  It is bound to the seed carrier lazily -- the carrier
    # is created on first placement -- so it starts empty and repaints on the
    # carrier's ModifiedEvent once bound.
    self._composeSeedsTable(liverVolumetryWidget)

    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

    self.initializeParameterNode()

  def _registerSeedPlacementPipelines(self):
    """Register the seed placement LayerDM Pipeline creators (ADR-0013 §5 call 3).

    ONE 3D + ONE slice creator for ``vtkMRMLVolumetrySeedsDisplayNode``, each
    returning the shared ``SurfacePointPlacementPipeline*`` base wired to the
    flat volumetry provider + the in-volume pick.  Idempotent; a missing
    LayerDMLib is a real configuration error under ADR-0002 so it logs at
    ``critical``, but the rest of widget setup continues.
    """
    try:
      from LiverVolumetryLib import (
        registerVolumetrySeedPipeline3DCreator,
        registerVolumetrySeedPipelineSliceCreator,
      )
      if registerVolumetrySeedPipeline3DCreator is None:
        raise ImportError("volumetry seed Pipeline creators unavailable")
      registerVolumetrySeedPipeline3DCreator()
      registerVolumetrySeedPipelineSliceCreator()
    except ImportError as exc:
      logging.critical(
        "LiverVolumetry: seed placement LayerDM Pipeline creators not "
        "registered (%s) -- seed placement is disabled in this session.  "
        "Loading the SlicerLayerDisplayableManager extension is required for "
        "the Pipeline path (ADR-0013/0038).", exc)

  def _composeSeedsTable(self, panelWidget):
    """Compose the carrier-backed seeds table into the panel grid (ADR-0004).

    Placed on the free grid row between the Add-seeds toggle and the
    Generate-segments button (the seed list belongs with the seed controls).
    A missing widget class (a launch without the Lib on the path) degrades
    gracefully -- the panel simply omits the table.
    """
    # The package guards the widget import (Qt/ctk unreachable bare), exposing
    # ``None`` when the class could not be built -- degrade to no table.
    from LiverVolumetryLib import VolumetrySeedsTableWidget
    if VolumetrySeedsTableWidget is None:
      logging.warning(
        "LiverVolumetry: VolumetrySeedsTableWidget unavailable -- the seeds "
        "table is omitted this session.")
      return
    self._seedsTable = VolumetrySeedsTableWidget(carrier=None)
    grid = self.ui.ResectionVolumetryGroupWidget.layout()
    if grid is not None and hasattr(grid, "addWidget"):
      # Row 6, colspan 4: between AddSeedsButton (row 5) and
      # GenerateSegmentsPushButton (row 7) in the .ui grid.
      grid.addWidget(self._seedsTable, 6, 0, 1, 4)
    else:
      panelWidget.layout().addWidget(self._seedsTable)

  def _bindSeedsTable(self, carrier):
    """Rebind the seeds table over ``carrier`` (drops the prior observer).

    Re-parents nothing -- only the carrier binding changes -- so the future
    unified planning table can adopt the same rebind seam.
    """
    if self._seedsTable is not None:
      self._seedsTable.setCarrier(carrier)

  # ------------------------------------------------------------------ #
  # Seed carrier + placement arming (ADR-0038-amendment)
  # ------------------------------------------------------------------ #

  def _ensureSeedsCarrier(self):
    """Return the scene-resident seed carrier, creating it once.

    ``None`` when the C++ node class is unavailable (a launch without the
    module's MRML library on the path) -- the caller degrades gracefully.
    """
    node = self._seedsCarrier
    if node is not None and slicer.mrmlScene.IsNodePresent(node):
      return node
    try:
      node = slicer.mrmlScene.AddNewNodeByClass(SEEDS_NODE_CLASS, "Volumetry Seeds")
    except Exception:  # noqa: BLE001 - node class not registered in this launch
      node = None
    if node is None:
      logging.warning(
        "LiverVolumetry: %s unavailable -- seed placement disabled this "
        "session.", SEEDS_NODE_CLASS)
      return None
    self._seedsCarrier = node
    # Bind the freshly-created carrier into the panel's seeds table so labels /
    # colours / deletes edit the same carrier the placement writes to.
    self._bindSeedsTable(node)
    return node

  def _ensureSeedsDisplayNode(self):
    """Return the scene-resident seed display node, creating + binding it once.

    Configures the carrier binding + the pick surface BEFORE AddNode: LayerDM
    consults the Pipeline creators the moment the node enters the scene, and
    each created Pipeline resolves the carrier + labelmap at creation -- so the
    carrier reference (and the pickSurface) must already be on the node
    (the configure-before-AddNode LayerDM discipline).
    """
    node = self._seedsDisplayNode
    if node is not None and slicer.mrmlScene.IsNodePresent(node):
      return node
    try:
      node = slicer.mrmlScene.CreateNodeByClass(SEEDS_DISPLAY_NODE_CLASS)
    except Exception:  # noqa: BLE001 - node class not registered in this launch
      node = None
    if node is None:
      logging.warning(
        "LiverVolumetry: %s unavailable -- seed placement disabled this "
        "session.", SEEDS_DISPLAY_NODE_CLASS)
      return None
    node.UnRegister(None)
    node.SetName("Volumetry Seeds Display")
    node.SetVisibility(True)
    carrier = self._ensureSeedsCarrier()
    if carrier is not None:
      from SlicerLiverInteractionLib.PointPlacementState import PointPlacementState
      PointPlacementState(VOLUMETRY_NAMESPACE).set_carrier(node, carrier)
    self._aimPickSurface(node)
    node = slicer.mrmlScene.AddNode(node)
    self._seedsDisplayNode = node
    return node

  def _aimPickSurface(self, displayNode):
    """Aim the seed display node's pickSurface at the target labelmap surface.

    The in-volume pick resolves interior voxels against the target region's
    labelmap.  The v2.0 target region is the currently selected input
    segmentation; a segmentation node satisfies the pick's labelmap read via
    its binary labelmap representation.  ``None`` clears the reference.
    """
    if displayNode is None or not hasattr(displayNode, "SetAndObservePickSurfaceNodeID"):
      return
    segmentation = self.ui.InputSegmentationSelector.currentNode()
    displayNode.SetAndObservePickSurfaceNodeID(
      segmentation.GetID() if segmentation is not None else None)

  def onAddSeedsToggled(self, armed):
    """Arm / disarm interior seed placement through the shared base pipeline.

    Arming publishes the armed flag onto the shared display node so the
    LayerDM-driven placement Pipelines add an interior seed on the next click;
    disarming clears it.  The state rides the display node, not a Python
    pipeline instance (feedback_layerdm_state_on_display_node).
    """
    node = self._ensureSeedsDisplayNode()
    if node is None:
      return
    self._aimPickSurface(node)
    from SlicerLiverInteractionLib.PointPlacementState import PointPlacementState
    state = PointPlacementState(VOLUMETRY_NAMESPACE)
    state.set_module_active(node, True)
    state.set_armed(node, bool(armed))

  def onGenerateSegmentsParameterChanged(self):
    node3 = self.ui.ReferenceVolumeSelector.currentNode()
    node4 = self.ui.InputSegmentationSelector.currentNode()
    node5 = self.ui.InputSegmentSelectorWidget.selectedSegmentIDs()
    if len(self.ui.InputSegmentSelectorWidget.selectedSegmentIDs()) == 0:
      node5 = None
    hasSeeds = self._seedsCarrier is not None and self._seedsCarrier.GetNumberOfSeeds() > 0
    self.ui.GenerateSegmentsPushButton.setEnabled(hasSeeds and None not in [ node3, node4, node5])

  def onGenerateSegmentsButtonClicked(self):
    resectionNodes = self.getResectionNodes()
    seedsCarrier = self._ensureSeedsCarrier()
    segmentsVolumeNode = slicer.mrmlScene.GetFirstNodeByName("segmentVolumeNode")
    if not segmentsVolumeNode:
      segmentsVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", "segmentVolumeNode")
      segmentationNode = self.ui.InputSegmentationSelector.currentNode()
      refVolumeNode = self.ui.ReferenceVolumeSelector.currentNode()
      segmentationIds = self.ui.InputSegmentSelectorWidget.selectedSegmentIDs()
      slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(segmentationNode, segmentationIds,
                                                                        segmentsVolumeNode, refVolumeNode)

    self.logic.generateSegments(resectionNodes, seedsCarrier, segmentsVolumeNode)
    slicer.mrmlScene.RemoveNode(segmentsVolumeNode)

  def onVolumetryParameterChanged(self):
    node2 = self.ui.ReferenceVolumeSelector.currentNode()
    node3 = self.ui.InputSegmentationSelector.currentNode()
    node4 = self.ui.InputSegmentSelectorWidget.selectedSegmentIDs()
    if len(self.ui.InputSegmentSelectorWidget.selectedSegmentIDs()) == 0:
      node4 = None
    self.ui.ComputeVolumePushButton.setEnabled(None not in [ node2, node3, node4])

  def getResectionNodes(self):
    resectionNodes = vtk.vtkCollection()
    if not self.ui.ResectionTargetNodeComboBox.noneChecked():
      checkedNodes = self.ui.ResectionTargetNodeComboBox.checkedNodes()
      for i in checkedNodes:
        # The checked nodes are now vtkMRMLResectionPlanNode wrappers; their
        # parametric geometry carrier (vtkMRMLBezierSurfaceNode) is the
        # boundary surface used for the volume computation
        # (ADR-0014 wrapper-vs-carrier split).
        bs = i.GetGeometryNode()
        if bs is None:
          continue
        resectionNodes.AddItem(bs)
    else:
      resectionNodes = None
    return resectionNodes

  def onComputeAdvancedVolumeButtonClicked(self):
    """
    This function is for compute volume
    """
    qt.QApplication.setOverrideCursor(qt.Qt.WaitCursor)

    resectionNodes = self.getResectionNodes()

    segmentsVolumeNode = slicer.mrmlScene.GetFirstNodeByName("segmentVolumeNode")
    if not segmentsVolumeNode:
      segmentsVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", "segmentVolumeNode")
      segmentationNode = self.ui.InputSegmentationSelector.currentNode()
      refVolumeNode = self.ui.ReferenceVolumeSelector.currentNode()
      segmentationIds = self.ui.InputSegmentSelectorWidget.selectedSegmentIDs()
      slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(segmentationNode, segmentationIds,
                                                                        segmentsVolumeNode, refVolumeNode)
    #target segments volume node for percentage calculation
    targetSegmentVolumeNode = slicer.mrmlScene.GetFirstNodeByName("targetSegmentVolumeNode")
    if not targetSegmentVolumeNode:
      targetSegmentVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", "targetSegmentVolumeNode")
      segmentationNode = self.ui.InputSegmentationSelector.currentNode()
      refVolumeNode = self.ui.ReferenceVolumeSelector.currentNode()
      segmentationIds = self.ui.TargetSegmentationSelectorWidget.selectedSegmentIDs()
      slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(segmentationNode, segmentationIds,
                                                                        targetSegmentVolumeNode, refVolumeNode)

    seedsCarrier = self._ensureSeedsCarrier()
    outputTable = self.ui.VolumeTableSelectorWidget.currentNode()

    self.logic.computeVolume(segmentsVolumeNode, targetSegmentVolumeNode, self.ui.InputSegmentationSelector.currentNode(), outputTable, seedsCarrier, resectionNodes)

    # The wait cursor (set above) is the in-progress feedback; the
    # populated volumetry table is the result, so no blocking completion
    # dialog is shown (non-blocking feedback, ADR-0009 UX discipline).
    qt.QApplication.restoreOverrideCursor()

    self.showTable(outputTable)
    slicer.mrmlScene.RemoveNode(segmentsVolumeNode)
    slicer.mrmlScene.RemoveNode(targetSegmentVolumeNode)

  def showTable(self, table):
    """
    Switch to a layout where tables are visible and show the selected table
    """
    currentLayout = slicer.app.layoutManager().layout
    layoutWithTable = slicer.modules.tables.logic().GetLayoutWithTable(currentLayout)
    slicer.app.layoutManager().setLayout(layoutWithTable)
    slicer.app.applicationLogic().GetSelectionNode().SetActiveTableID(table.GetID())
    slicer.app.applicationLogic().PropagateTableSelection()

  def segmentationNodeSelected(self):
    self.ui.SegmentationShow3DButton.setEnabled(True)
    segmentationNode = self.ui.InputSegmentationSelector.currentNode()

    if segmentationNode is None:
      logging.warning('No segmentationNode')
      return

    self.ui.SegmentationShow3DButton.setSegmentationNode(segmentationNode)
    displayNode = segmentationNode.GetDisplayNode()
    visibleSegmentIds = vtk.vtkStringArray()
    displayNode.GetVisibleSegmentIDs(visibleSegmentIds)
    for segmentIdIndex in range(visibleSegmentIds.GetNumberOfValues()):
      segmentId = visibleSegmentIds.GetValue(segmentIdIndex)
      displayNode.SetSegmentVisibility(segmentId, False)

  def onSegmentChanged(self):
    if self.ui.InputSegmentationSelector.currentNode() is None:
      return
    if not self.ui.InputSegmentSelectorWidget.selectedSegmentIDs():
      return
    segmentationNode = self.ui.InputSegmentationSelector.currentNode()
    displayNode = segmentationNode.GetDisplayNode()
    segmentIDs = self.ui.InputSegmentSelectorWidget.segmentIDs()
    selectedIDs = self.ui.InputSegmentSelectorWidget.selectedSegmentIDs()
    unselectedIDs = list(set(segmentIDs)-set(selectedIDs))
    for id in selectedIDs:
      displayNode.SetSegmentVisibility(id, True)
    for id in unselectedIDs:
      displayNode.SetSegmentVisibility(id, False)

  def cleanup(self):
    """
    Called when the application closes and the module widget is destroyed.
     """
    # Tear down the seeds table's carrier observer so the parentless widget
    # does not survive to app shutdown holding a MRML observer
    # (feedback_launched_widget_teardown_crash).
    if self._seedsTable is not None:
      self._seedsTable.cleanup()
    self.removeObservers()

  def enter(self):
    """
    Called each time the user opens this module.
    """
    # Open the module-active add-on-click gate (ADR-0038): the LayerDM-created
    # placement Pipelines read this off the shared display node, so an armed
    # click only lands while LiverVolumetry is active.  Entering auto-arms
    # NOTHING -- placement is the explicit Add-seeds toggle.
    self._setModuleActive(True)
    # Make sure parameter node exists and observed
    self.initializeParameterNode()

  def exit(self):
    """
    Called each time the user opens a different module.
    """
    # Disarm placement + close the module-active gate on the way out so no view
    # claims an add-on-click while LiverVolumetry is inactive (ADR-0038).
    node = getattr(self, "_seedsDisplayNode", None)
    if node is not None and slicer.mrmlScene.IsNodePresent(node):
      from SlicerLiverInteractionLib.PointPlacementState import PointPlacementState
      state = PointPlacementState(VOLUMETRY_NAMESPACE)
      state.set_armed(node, False)
      state.set_module_active(node, False)
    if hasattr(self.ui, "AddSeedsButton"):
      self.ui.AddSeedsButton.setChecked(False)
    # Do not react to parameter node changes (GUI wlil be updated when the user enters into the module)
    self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)

  def _setModuleActive(self, active):
    """Open/close the shared display node's module-active add-on-click gate."""
    node = getattr(self, "_seedsDisplayNode", None)
    if node is None or not slicer.mrmlScene.IsNodePresent(node):
      return
    from SlicerLiverInteractionLib.PointPlacementState import PointPlacementState
    PointPlacementState(VOLUMETRY_NAMESPACE).set_module_active(node, bool(active))

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
    # The seed carrier + display node were cleared with the scene; drop the
    # stale handles so the next placement re-creates fresh ones.
    self._seedsCarrier = None
    self._seedsDisplayNode = None
    # Unbind the table from the now-invalid carrier (drops its observer) so it
    # empties and does not observe a scene-cleared node.
    self._bindSeedsTable(None)
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
    self.ui.ResectionVolumetryGroupWidget.enabled = parameterNode is not None
    if parameterNode is None:
      return

    if self._parameterNode is None or self._updatingGUIFromParameterNode:
      return

    # Make sure GUI changes do not call updateParameterNodeFromGUI (it could cause infinite loop)
    self._updatingGUIFromParameterNode = True

    # Update node selectors and sliders
    for nodeSelector, roleName in self.nodeSelectors:
      nodeSelector.setCurrentNode(self._parameterNode.GetNodeReference(roleName))
    inputSegmentationNode = self._parameterNode.GetNodeReference("inputSegmentation")
    if inputSegmentationNode and inputSegmentationNode.IsA("vtkMRMLSegmentationNode"):
      self.ui.InputSegmentSelectorWidget.setCurrentSegmentIDs(self._parameterNode.GetParameter("InputSegmentID"))
      self.ui.TargetSegmentationSelectorWidget.setCurrentSegmentIDs(self._parameterNode.GetParameter("InputSegmentID"))

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

    inputSegmentation = self._parameterNode.GetNodeReference("inputSegmentation")
    self.ui.InputSegmentSelectorWidget.setVisible(inputSegmentation and inputSegmentation.IsA("vtkMRMLSegmentationNode"))
    self.ui.TargetSegmentationSelectorWidget.setVisible(inputSegmentation and inputSegmentation.IsA("vtkMRMLSegmentationNode"))


# LiverVolumetryLogic
#

class LiverVolumetryLogic(ScriptedLoadableModuleLogic):

  def __init__(self):
    ScriptedLoadableModuleLogic.__init__(self)

    from vtkSlicerLiverVolumetryModuleLogicPython import vtkLiverVolumetryLogic
    # Create the vtkLiverVolumetryLogic logic
    self.scl = vtkLiverVolumetryLogic()


  def isStageComplete(self) -> bool:
    """Stage-5 completion predicate for the Liver-shell sidebar (T5.2-d).

    Stage 5 (Volumetry) is a pure analytical workbench with no
    verification card in v2.0 (see ADR-0023 §"Decision" item 5 +
    §"What is NOT in v2.0").  v2.0 ships the *soft* semantics:
    Volumetry is "done" iff Stage 4 (Resection Planning) is done —
    the prerequisites are met, so the surgeon has reached the
    analytical workbench.  A future iteration may add a real gate
    (e.g. "at least one partition computation has been executed")
    once the v2.0 surgeon-facing volumetry surface crystallises.

    Pinned by
    ``Liver/Testing/Python/test_liver_shell_isstagecomplete.py``
    (T2 stage-5 symbol existence + T3 semantics).
    """
    import slicer
    resections = getattr(slicer.modules, "liverresections", None)
    if resections is None:
      return False
    try:
      logic = resections.logic()
    except Exception:  # pragma: no cover — defensive
      return False
    if logic is None or not hasattr(logic, "IsStageComplete"):
      return False
    return bool(logic.IsStageComplete())

  def setDefaultParameters(self, parameterNode):
    """
    Initialize parameter node with default settings.
    """

  def transientFiducialFromSeeds(self, seedsNode):
    """Build a TRANSIENT fiducial from the seed carrier (ADR-0038 §3c).

    Keeps the C++ ``vtkLiverVolumetryLogic`` signatures unchanged (ADR-0015):
    they take a ``vtkMRMLMarkupsFiducialNode*``, so the seeds-off-markups path
    feeds them a transient fiducial built INSIDE the call from the seed carrier,
    with the per-seed LABEL round-tripping into each control-point label so
    ``GenerateSegmentsLabelMap`` still names generated segments correctly.  The
    caller REMOVES the returned node -- no persistent markups survive
    (ADR-0014 §"Fourth layer").  ``None`` when there is no carrier.
    """
    if seedsNode is None:
      return None
    from LiverVolumetryLib import build_transient_fiducial
    return build_transient_fiducial(slicer.mrmlScene, seedsNode)

  def computeVolume(self, segmentsVolumeNode, targetSegmentVolumeNode, segmentationNode, outputTable, seedsNode, resectionNodes):
    statistics = {}
    if outputTable is None:
      raise ValueError("Missing outputTable")

    targetSegmentVolume = 0.0
    if targetSegmentVolumeNode is not None:
      import vtk
      import numpy
      scalars = vtk.util.numpy_support.vtk_to_numpy(targetSegmentVolumeNode.GetImageData().GetPointData().GetScalars())
      spacing = targetSegmentVolumeNode.GetSpacing()
      voxel_count = numpy.count_nonzero(scalars)
      targetSegmentVolume = voxel_count*spacing[0]*spacing[1]*spacing[2]*0.001

    # Build the transient fiducial from the seed carrier once and feed it to the
    # unchanged C++ logic (ADR-0038 §3c); remove it afterwards.
    hasSeeds = seedsNode is not None and seedsNode.GetNumberOfSeeds() > 0
    ROIMarkersList = self.transientFiducialFromSeeds(seedsNode) if hasSeeds else None
    try:
      if resectionNodes is None:
        if ROIMarkersList is None:
          import SegmentStatistics
          segStatLogic = SegmentStatistics.SegmentStatisticsLogic()
          segStatLogic.getParameterNode().SetParameter("Segmentation", segmentationNode.GetID())
          segStatLogic.computeStatistics()
          stats = segStatLogic.getStatistics()
          for segmentId in stats["SegmentIDs"]:
            voxel_count = 0
            volume_cm3 = 0
            if stats[segmentId,"LabelmapSegmentStatisticsPlugin.voxel_count"]:
              voxel_count = stats[segmentId,"LabelmapSegmentStatisticsPlugin.voxel_count"]
              volume_cm3 = stats[segmentId,"LabelmapSegmentStatisticsPlugin.volume_cm3"]
            elif stats[segmentId,"ScalarVolumeSegmentStatisticsPlugin.voxel_count"]:
              voxel_count = stats[segmentId,"ScalarVolumeSegmentStatisticsPlugin.voxel_count"]
              volume_cm3 = stats[segmentId,"ScalarVolumeSegmentStatisticsPlugin.volume_cm3"]
            segmentName = segmentationNode.GetSegmentation().GetSegment(segmentId).GetName()
            statistics[segmentId] = [segmentName, voxel_count, volume_cm3]
            self.scl.VolumetryTable(segmentName, targetSegmentVolume, voxel_count, volume_cm3,outputTable)
        else:
          import vtk
          import numpy
          ROIvalues = self.scl.GetROIPointsLabelValue(segmentsVolumeNode, ROIMarkersList)
          scalars = vtk.util.numpy_support.vtk_to_numpy(segmentsVolumeNode.GetImageData().GetPointData().GetScalars())
          spacing = segmentsVolumeNode.GetSpacing()
          for i, values in enumerate(ROIvalues):
            voxel_count = numpy.count_nonzero(scalars == values)
            volume_cm3 = voxel_count*spacing[0]*spacing[1]*spacing[2]*0.001
            pointLabel = ROIMarkersList.GetNthControlPointLabel(i)
            statistics[pointLabel] = [pointLabel, voxel_count, volume_cm3]
            self.scl.VolumetryTable(pointLabel, targetSegmentVolume, voxel_count, volume_cm3, outputTable)
      else:
        self.scl.ComputeAdvancedPlanningVolumetry(segmentsVolumeNode, outputTable, ROIMarkersList, resectionNodes, targetSegmentVolume)
    finally:
      if ROIMarkersList is not None:
        slicer.mrmlScene.RemoveNode(ROIMarkersList)

  def generateSegments(self, resectionNodes, seedsNode, segmentsVolumeNode):
    ROIMarkersList = self.transientFiducialFromSeeds(seedsNode)
    if ROIMarkersList is None:
      return
    try:
      generatedSegmentsNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
      generatedSegmentsNode.CreateDefaultDisplayNodes()

      self.scl.GenerateSegmentsLabelMap(segmentsVolumeNode, generatedSegmentsNode, resectionNodes, ROIMarkersList)

      seg = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
      slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(generatedSegmentsNode, seg)

      ##set segments label
      seg.GetSegmentation().GetNthSegment(0).SetName("Remnant")
      for i in range(ROIMarkersList.GetNumberOfControlPoints()):
        seg.GetSegmentation().GetNthSegment(i+1).SetName(ROIMarkersList.GetNthFiducialLabel(i))

      slicer.mrmlScene.RemoveNode(generatedSegmentsNode)
    finally:
      slicer.mrmlScene.RemoveNode(ROIMarkersList)

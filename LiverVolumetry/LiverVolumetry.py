# ==============================================================================
#
#  Distributed under the OSI-approved BSD 3-Clause License.
#
#   Copyright (c) Oslo University Hospital. All rights reserved.
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


import os
import unittest
import logging
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin


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

    # Additional initialization step after application startup is complete
    #slicer.app.connect("startupCompleted()", registerSampleData)

    #Hide module, so that it only shows up in the Liver module, and not as a separate module
    parent.hidden = True


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
    ScriptedLoadableModuleWidget.__init__(self, parent)
    VTKObservationMixin.__init__(self)  # needed for parameter node observation

  def setup(self):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.setup(self)

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
    self.ui.ROIMarkersListSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.onGenerateSegmentsParameterChanged)

    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

    self.initializeParameterNode()


  def onGenerateSegmentsParameterChanged(self):
    node2 = self.ui.ROIMarkersListSelector.currentNode()
    node3 = self.ui.ReferenceVolumeSelector.currentNode()
    node4 = self.ui.InputSegmentationSelector.currentNode()
    node5 = self.ui.InputSegmentSelectorWidget.selectedSegmentIDs()
    if len(self.ui.InputSegmentSelectorWidget.selectedSegmentIDs()) == 0: node5 = None
    self.ui.GenerateSegmentsPushButton.setEnabled(None not in [ node2, node3, node4, node5])

  def onGenerateSegmentsButtonClicked(self):
    resectionNodes = self.getResectionNodes()
    ROIMarkersList = self.ui.ROIMarkersListSelector.currentNode()
    segmentsVolumeNode = slicer.mrmlScene.GetFirstNodeByName("segmentVolumeNode")
    if not segmentsVolumeNode:
      segmentsVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", "segmentVolumeNode")
      segmentationNode = self.ui.InputSegmentationSelector.currentNode()
      refVolumeNode = self.ui.ReferenceVolumeSelector.currentNode()
      segmentationIds = self.ui.InputSegmentSelectorWidget.selectedSegmentIDs()
      slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(segmentationNode, segmentationIds,
                                                                        segmentsVolumeNode, refVolumeNode)

    self.logic.generateSegments(resectionNodes, ROIMarkersList, segmentsVolumeNode)
    slicer.mrmlScene.RemoveNode(segmentsVolumeNode)

  def onVolumetryParameterChanged(self):
    node2 = self.ui.ReferenceVolumeSelector.currentNode()
    node3 = self.ui.InputSegmentationSelector.currentNode()
    node4 = self.ui.InputSegmentSelectorWidget.selectedSegmentIDs()
    if len(self.ui.InputSegmentSelectorWidget.selectedSegmentIDs()) == 0: node4 = None
    self.ui.ComputeVolumePushButton.setEnabled(None not in [ node2, node3, node4])

  def getResectionNodes(self):
    resectionNodes = vtk.vtkCollection()
    if not self.ui.ResectionTargetNodeComboBox.noneChecked():
      lvLogic = slicer.modules.liverresections.logic()
      checkedNodes = self.ui.ResectionTargetNodeComboBox.checkedNodes()
      for i in checkedNodes:
        bs = lvLogic.GetBezierFromResection(i)
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

    ROIMarkersList = self.ui.ROIMarkersListSelector.currentNode()
    outputTable = self.ui.VolumeTableSelectorWidget.currentNode()

    self.logic.computeVolume(segmentsVolumeNode, targetSegmentVolumeNode, self.ui.InputSegmentationSelector.currentNode(), outputTable, ROIMarkersList, resectionNodes)

    qt.QApplication.restoreOverrideCursor()
    qt.QMessageBox.information(None, "Information", "The targeted liver volumetry was computed.")

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


# LiverSegmentsLogic
#

class LiverVolumetryLogic(ScriptedLoadableModuleLogic):

  def __init__(self):
    ScriptedLoadableModuleLogic.__init__(self)

    from vtkSlicerLiverVolumetryModuleLogicPython import vtkLiverVolumetryLogic
    # Create the vtkLiverVolumetryLogic logic
    self.scl = vtkLiverVolumetryLogic()


  def setDefaultParameters(self, parameterNode):
    """
    Initialize parameter node with default settings.
    """

  def computeVolume(self, segmentsVolumeNode, targetSegmentVolumeNode, segmentationNode, outputTable, ROIMarkersList, resectionNodes):
    statistics = {}
    if outputTable is None:
      raise ValueError("Missing outputTable")

    targetSegmentVolume = 0.0
    if targetSegmentVolumeNode != None:
      import vtk, numpy
      scalars = vtk.util.numpy_support.vtk_to_numpy(targetSegmentVolumeNode.GetImageData().GetPointData().GetScalars())
      spacing = targetSegmentVolumeNode.GetSpacing()
      voxel_count = numpy.count_nonzero(scalars)
      targetSegmentVolume = voxel_count*spacing[0]*spacing[1]*spacing[2]*0.001

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
        import vtk, numpy
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

  def generateSegments(self, resectionNodes, ROIMarkersList, segmentsVolumeNode):
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
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
#   This file was originally developed by Ruoyan Meng (NTNU), Ole V. Solberg,
#   Geir A. Tangen, Javier Perez-de-Frutos (SINTEF, Norway) and Rafael Palomar
#   (Oslo University Hospital) through the ALive project (grant nr. 311393).
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
    self.ui.InputSegmentationSelector.connect('currentNodeChanged(bool)', self.updateParameterNodeFromGUI)
    self.ui.InputSegmentationSelector.connect('currentNodeChanged(bool)', self.segmentationNodeSelected)
    self.ui.InputSegmentSelectorWidget.connect('segmentSelectionChanged(QStringList)', self.updateParameterNodeFromGUI)
    self.ui.InputSegmentSelectorWidget.connect('segmentSelectionChanged(QStringList)', self.onSegmentChanged)
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)
    # self.ui.ROIMarkersListSelector.connect('nodeAddedByUser(vtkMRMLNode*)', self.newROIMarkersListCreated)

    # self.ui.ResectionTargetNodeComboBox.connect('currentNodeChanged(vtkMRMLNode*)', self.onResectionVolumetryTargetNodeChanged)
    self.ui.ComputeVolumePushButton.connect('clicked(bool)', self.onComputeAdvancedVolumeButtonClicked)

    self.initializeParameterNode()


  def onComputeAdvancedVolumeButtonClicked(self):
    """
    This function is for compute volume
    """
    resectionNodes = vtk.vtkCollection()
    if not self.ui.ResectionTargetNodeComboBox.noneChecked():
      lvLogic = slicer.modules.liverresections.logic()
      checkedNodes = self.ui.ResectionTargetNodeComboBox.checkedNodes()
      for i in checkedNodes:
        bs = lvLogic.GetBezierFromResection(i)
        resectionNodes.AddItem(bs)
    else:
      resectionNodes = None

    segmentsVolumeNode = slicer.mrmlScene.GetFirstNodeByName("segmentVolumeNode")
    if not segmentsVolumeNode:
      segmentsVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", "segmentVolumeNode")
      segmentationNode = self.ui.InputSegmentationSelector.currentNode()
      refVolumeNode = self.ui.ReferenceVolumeSelector.currentNode()
      segmentationIds = self.ui.InputSegmentSelectorWidget.selectedSegmentIDs()
      slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(segmentationNode, segmentationIds,
                                                                        segmentsVolumeNode, refVolumeNode)

    # VascularSegmentsLabelmapVolumeNode = self.ui.VascularSegmentsSelectorWidget.currentNode()
    ROIMarkersList = self.ui.ROIMarkersListSelector.currentNode()
    outputTable = self.ui.VolumeTableSelectorWidget.currentNode()

    self.logic.computeVolume(segmentsVolumeNode, self.ui.InputSegmentationSelector.currentNode(), outputTable, ROIMarkersList, resectionNodes)
    self.showTable(outputTable)
    slicer.mrmlScene.RemoveNode(segmentsVolumeNode)

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
    self.ui.SegmentationShow3DButton.setSegmentationNode(segmentationNode)
    if segmentationNode is None:
      logging.warning('No segmentationNode')
      return
    displayNode = segmentationNode.GetDisplayNode()
    displayNode.SetOpacity(0.5)

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

  def getDisplayNodeAndSegmentId(self):
    segmentation = self.ui.InputSegmentationSelector.currentNode()
    if segmentation is None:
      return None, None
    displayNode = segmentation.GetDisplayNode()
    if displayNode is None:
      return None, None
    return displayNode, self.ui.InputSegmentSelectorWidget.selectedSegmentIDs()


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
    if self.parent.isEntered:
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
    inputSurfaceNode = self._parameterNode.GetNodeReference("inputSegmentation")
    if inputSurfaceNode and inputSurfaceNode.IsA("vtkMRMLSegmentationNode"):
      self.ui.InputSegmentSelectorWidget.setCurrentSegmentIDs(self._parameterNode.GetParameter("InputSegmentID"))

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

  def computeVolume(self, segmentsVolumeNode, segmentationNode, outputTable, ROIMarkersList, resectionNodes):
    statistics = {}
    if outputTable is None:
      raise ValueError("Missing outputTable")

    if resectionNodes is None:
      if ROIMarkersList is None:
        import SegmentStatistics
        segStatLogic = SegmentStatistics.SegmentStatisticsLogic()
        segStatLogic.getParameterNode().SetParameter("Segmentation", segmentationNode.GetID())
        segStatLogic.computeStatistics()
        stats = segStatLogic.getStatistics()
        for segmentId in stats["SegmentIDs"]:
          voxel_count = stats[segmentId,"LabelmapSegmentStatisticsPlugin.voxel_count"]
          volume_cm3 = stats[segmentId,"LabelmapSegmentStatisticsPlugin.volume_cm3"]
          segmentName = segmentationNode.GetSegmentation().GetSegment(segmentId).GetName()
          statistics[segmentId] = [segmentName, voxel_count, volume_cm3]
          self.scl.VolumetryTable(segmentName, 0.0, voxel_count, volume_cm3,outputTable)
      else:
        import vtk, numpy
        ROIvalues = self.scl.GetROIPointsLabelValue(segmentsVolumeNode, ROIMarkersList)
        scalars = vtk.util.numpy_support.vtk_to_numpy(segmentsVolumeNode.GetImageData().GetPointData().GetScalars())
        spacing = segmentsVolumeNode.GetSpacing()
        for i, values in enumerate(ROIvalues):
          voxel_count = numpy.sum(scalars == values)
          volume_cm3 = voxel_count*spacing[0]*spacing[1]*spacing[2]*0.001
          pointLabel = ROIMarkersList.GetNthControlPointLabel(i)
          statistics[pointLabel] = [pointLabel, voxel_count, volume_cm3]
          self.scl.VolumetryTable(pointLabel, 0.0, voxel_count, volume_cm3,outputTable)
    else:
      self.scl.ComputeAdvancedPlanningVolumetry(segmentsVolumeNode,outputTable, ROIMarkersList, resectionNodes)










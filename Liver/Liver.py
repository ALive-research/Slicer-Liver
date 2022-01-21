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
#   This file was originally developed by Rafael Palomar (The Intervention Centre,
#   Oslo University Hospital) and was supported by The Research Council of Norway
#   through the ALive project (grant nr. 311393).
#
# ==============================================================================

import os
import unittest
import logging
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
import numpy as np

#
# Liver
#

class Liver(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Liver"
    self.parent.categories = [""]
    self.parent.dependencies = []
    self.parent.contributors = ["Rafael Palomar (Oslo University Hospital / NTNU)"]

    self.parent.helpText = """
    This module offers tools for making liver resection plans in 3D liver models.
""
    This file was originally developed by Rafael Palomar, Oslo University
    Hospital/NTNU, Ole Vegard Solberg, SINTEF and Geir Arne Tangen, SINTEF. This
    work was funded by The Research Council of Norway through the project ALive
    (grant nr. 311393).
"""

    # Additional initialization step after application startup is complete
    slicer.app.connect("startupCompleted()", registerSampleData)

#
# Register sample data sets in Sample Data module
#

def registerSampleData():
  """
  Add data sets to Sample Data module.
  """
  import SampleData
  iconsPath = os.path.join(os.path.dirname(__file__), 'Resources/Icons')

  # Liver Parenchyma 3D Model dataset
  SampleData.SampleDataLogic.registerCustomSampleDataSource(
    category='Liver',
    sampleName='LiverVolume000',
    thumbnailFileName=os.path.join(iconsPath, 'LiverVolume000.png'),
    uris="https://github.com/ALive-Research/ALiveResearchTestingData/releases/download/SHA256/5df79d9077b1cf2b746ff5cf9268e0bc4d440eb50fa65308b47bde094640458a",
    fileNames='LiverVolume000.nrrd',
    checksums = 'SHA256:5df79d9077b1cf2b746ff5cf9268e0bc4d440eb50fa65308b47bde094640458a',
    nodeNames='LiverVolume000',
    loadFileType='VolumeFile'
  )

  SampleData.SampleDataLogic.registerCustomSampleDataSource(
    category='Liver',
    sampleName='LiverSegmentation000',
    thumbnailFileName=os.path.join(iconsPath, 'LiverSegmentation000.png'),
    uris="https://github.com/ALive-Research/ALiveResearchTestingData/releases/download/SHA256/83c285259a754a76a8d5129142b26d2ac8127360af9ea1e3465c13532651fed5",
    fileNames='LiverSegmentation000.nrrd',
    checksums = 'SHA256:83c285259a754a76a8d5129142b26d2ac8127360af9ea1e3465c13532651fed5',
    nodeNames='LiverSegmentation000',
    loadFileType='SegmentationFile'
  )
#
# LiverWidget
#

class LiverWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):

  def __init__(self, parent=None):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.__init__(self, parent)
    VTKObservationMixin.__init__(self)  # needed for parameter node observation

    self.logic = None
    self._parameterNode = None
    self._updatingGUIFromParameterNode = False
    self._nodeAddedObserverTag = None

    self._inputSegmentationNodeSelector = None
    self._resectionsTableView = None

    self._selectedTumors = str('')

  def setup(self):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.setup(self)

    # Create logic class. Logic implements all computations that should be possible to run
    # in batch mode, without a graphical user interface.
    self.logic = LiverLogic()

    # Create and configure the input segmentation node selector
    self._inputSegmentationNodeSelector = slicer.qMRMLNodeComboBox()
    self._inputSegmentationNodeSelector.nodeTypes = ["vtkMRMLSegmentationNode"]
    self._inputSegmentationNodeSelector.selectNodeUponCreation = True
    self._inputSegmentationNodeSelector.addEnabled = False
    self._inputSegmentationNodeSelector.removeEnabled = False
    self._inputSegmentationNodeSelector.noneEnabled = True
    self._inputSegmentationNodeSelector.noneDisplay = "(Choose active liver segmentation)"
    self._inputSegmentationNodeSelector.showHidden = False
    self._inputSegmentationNodeSelector.setMRMLScene(slicer.mrmlScene)
    self._inputSegmentationNodeSelector.setToolTip("Segmentation to perform planning on.")
    self._inputSegmentationNodeSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
    self.layout.addWidget(self._inputSegmentationNodeSelector)

    # Create and configure segments widget
    import qSlicerSegmentationsModuleWidgetsPythonQt as segmentationWidgets
    self._tumorsTableView = segmentationWidgets.qMRMLSegmentsTableView()
    self._tumorsTableView.setMRMLScene(slicer.mrmlScene)
    self._tumorsTableView.connect("selectionChanged(const QItemSelection&, const QItemSelection&)",self.onSelectionUpdate)
    self.layout.addWidget(self._tumorsTableView)

    # Create and configure the therapy bar
    therapyHBoxLayout = qt.QHBoxLayout()
    self._addResectionPlanePushButton = qt.QPushButton("|")
    self._addResectionPlanePushButton.setEnabled(False)
    self._addResectionPlanePushButton.connect("clicked(bool)", self.onAddResectionPlane)
    self._addResectionContourPushButton = qt.QPushButton("O")
    self._addResectionContourPushButton.setEnabled(False)
    self._addResectionContourPushButton.connect("clicked(bool)", self.onAddResectionContour)
    therapyHBoxLayout.addWidget(self._addResectionPlanePushButton)
    therapyHBoxLayout.addWidget(self._addResectionContourPushButton)
    therapyHBoxLayout.addSpacing(1)
    self.layout.addLayout(therapyHBoxLayout)

    # Create and configure resectionwidgets
    import qSlicerLiverResectionsModuleWidgetsPythonQt as resectionWidgets
    self._resectionsTableView = resectionWidgets.qSlicerLiverResectionsTableView()
    self._resectionsTableView.setMRMLScene(slicer.mrmlScene)
    self.layout.addWidget(self._resectionsTableView)

    # Add vertical spacer
    self.layout.addStretch(1)

    #self._nodeAddedObserverTag = slicer.mrmlScene.AddObserver(slicer.vtkMRMLScene.NodeAddedEvent, self.nodeAddedCallback)

    # Connections

    # These connections ensure that we update parameter node when scene is closed
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

    # This connection listens for new node added.
    # self.addObserver(slicer.mrmlScene, slicer.mrmlScene.NodeAddedEvent, self.onSceneNodeAdded)

    # Make sure parameter node is initialized (needed for module reload)
    self.initializeParameterNode()

    # Enable the use of FXAA (antialiasing)
    if not slicer.app.commandOptions().noMainWindow:
      renderer = slicer.app.layoutManager().threeDWidget(0).threeDView().renderWindow().GetRenderers().GetFirstRenderer()
      renderer.UseFXAAOn()


  def cleanup(self):
    """
    Called when the application closes and the module widget is destroyed.
    """
    self.removeObservers()
    #slicer.mrmlScene.RemoveObserver(self._nodeAddedObserverTag)

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

  @vtk.calldata_type(vtk.VTK_OBJECT)
  def nodeAddedCallback(self, caller, eventId, callData):
    if isinstance(callData, slicer.vtkMRMLMarkupsSlicingContourNode) or\
       isinstance(callData, slicer.vtkMRMLMarkupsDistanceContourNode):

      callData.SetTarget(self.logic.getSelectedTargetLiverModel())

  def onSelectionUpdate(self):
    """
    Called each time a there is a selection change
    """
    selected = self._tumorsTableView.selectedSegmentIDs();
    if len(selected) > 0:
      self._addResectionPlanePushButton.setEnabled(True)
      self._addResectionContourPushButton.setEnabled(True)
    else:
      self._addResectionPlanePushButton.setEnabled(False)
      self._addResectionContourPushButton.setEnabled(False)
    self.updateGUIFromParameterNode()

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

  def onAddResectionPlane(self):
    self.logic.addResectionPlane()


  def onAddResectionContour(self):
    self.logic.addResectionContour()

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

    # Unobserve previously selected parameter node and add an observer to the newly selected.
    # Changes of parameter node are observed so that whenever parameters are changed by a script or any other module
    # those are reflected immediately in the GUI.
    if self._parameterNode is not None:
      self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)
    self._parameterNode = inputParameterNode
    if self._parameterNode is not None:
      self.addObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)

    # Initial GUI update
    self.updateGUIFromParameterNode()

  def updateGUIFromParameterNode(self, caller=None, event=None):
    """
    This method is called whenever parameter node is changed.
    The module GUI is updated to show the current state of the parameter node.
    """
    if self._parameterNode is None or self._updatingGUIFromParameterNode:
      return

    # Make sure GUI changes do not call updateParameterNodeFromGUI (it could cause infinite loop)
    self._updatingGUIFromParameterNode = True

    # Update node selectors and sliders
    self._inputSegmentationNodeSelector.setCurrentNode(self._parameterNode.GetNodeReference("LiverSegmentation"))

    # All the GUI updates are done
    self._updatingGUIFromParameterNode = False

  def updateParameterNodeFromGUI(self, caller=None, event=None):
    """
    This method is called when the user makes any change in the GUI.
    The changes are saved into the parameter node (so that they are restored when the scene is saved and loaded).
    """
    if self._parameterNode is None or self._updatingGUIFromParameterNode:
      return

    wasModified = self._parameterNode.StartModify()  # Modify all properties in a single batch

    self._parameterNode.SetNodeReferenceID("LiverSegmentation", self._inputSegmentationNodeSelector.currentNodeID)
    self._parameterNode.SetParameter("SelectedTumors", ' '.join(self._tumorsTableView.selectedSegmentIDs()))

    self._parameterNode.EndModify(wasModified)

    segmentationNode = slicer.mrmlScene.GetNodeByID(self._inputSegmentationNodeSelector.currentNodeID)
    self._tumorsTableView.setSegmentationNode(segmentationNode)

    self.logic.parameterNodeChanged(self._parameterNode)

  def tumorSelectionChanged(self, selected, deselected):
    self._selectedTumors = self._tumorsTableView.selectedSegmentIDs();
    self.updateParameterNodeFromGUI()
    # segmentationNode = slicer.mrmlScene.GetNodeByID(self._inputSegmentationNodeSelector.currentNodeID)
    # print(selected)

#
# LiverLogic
#

class LiverLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self):
    """
    Called when the logic class is instantiated. Can be used for initializing member variables.
    """
    ScriptedLoadableModuleLogic.__init__(self)

    self._currentSelectedModelNode = None
    self._mapper = None
    self._actor = None
    self._markupsLineNode = None
    self._markupsLineDisplayNode = None

    self._volumeNode = None
    self._segmentationNode = None

    self._selectedTargetLiverModelNode = None

  def setDefaultParameters(self, parameterNode):
    """
    Initialize parameter node with default settings.
    """
    parameterNode.SetNodeReferenceID('LiverSegmentation', None)
    parameterNode.SetParameter('SelectedTumors', str(''))
    pass

  def parameterNodeChanged(self,parameterNode):
    """
    Called when the parameter node has changed
    """
    segmentationNode = parameterNode.GetNodeReference('LiverSegmentation')
    selectedTumors = parameterNode.GetParameter('SelectedTumors')
    print(selectedTumors)

    if segmentationNode is self._segmentationNode:
      return

    if segmentationNode is None:
      return

    self._segmentationNode = segmentationNode
    self._selectedTumors = selectedTumors

    shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
    folderItemID = shNode.CreateFolderItem(shNode.GetSceneItemID(), '3D Models')
    segmentationsLogic = slicer.modules.segmentations.logic()

    self._segmentationNode.CreateDefaultDisplayNodes()
    segmentationDisplayNode = self._segmentationNode.GetDisplayNode()
    segmentationDisplayNode.Visibility3DOff()

    self._segmentationNode.CreateClosedSurfaceRepresentation()
    segmentationsLogic.ExportAllSegmentsToModels(self._segmentationNode, folderItemID)

    liverModelNodes = slicer.mrmlScene.GetNodesByClassByName('vtkMRMLModelNode', 'liver')
    liverModelNodes.UnRegister(None)
    liverModelNode = liverModelNodes.GetItemAsObject(0)
    if liverModelNode is None:
      return

    liverDisplayNode = liverModelNode.GetDisplayNode()
    if liverDisplayNode is None:
      return

    liverDisplayNode.SetOpacity(0.2)

  def getSelectedTargetLiverModel(self):
    return self._selectedTargetLiverModelNode

  def addResectionPlane(self):
    liverModelNodes = slicer.mrmlScene.GetNodesByClassByName('vtkMRMLModelNode', 'liver')
    liverModelNodes.UnRegister(None)
    liverModelNode = liverModelNodes.GetItemAsObject(0)

    if liverModelNode is None:
      return
    if self._segmentationNode is None:
      return
    liverResectionNode = slicer.vtkMRMLLiverResectionNode()
    liverResectionNode.SetScene(slicer.mrmlScene)
    liverResectionNode.SetSegmentationNode(self._segmentationNode)
    liverResectionNode.SetTargetOrgan(liverModelNode)
    liverResectionNode.SetInitialization(liverResectionNode.Flat)
    liverResectionNode.CreateDefaultDisplayNodes()
    slicer.mrmlScene.AddNode(liverResectionNode)

  def addResectionContour(self):
    liverModelNodes = slicer.mrmlScene.GetNodesByClassByName('vtkMRMLModelNode', 'liver')
    liverModelNode.UnRegister(None)
    liverModelNode = liberModelNodes.GetItemAsObject(0)
    tumorModelNodes = slicer.mrmlScene.GetNodesByClassByName('vtkMRMLModelNode', 'tumor1')
    tumorMOdelNodes.UnRegister(0)
    tumorModelNode = tumorModelNodes.GetItemAsObject(0)
    if liverModelNode is None:
      return
    if self._segmentationNode is None:
      return
    liverResectionNode = slicer.vtkMRMLLiverResectionNode()
    liverResectionNode.SetScene(slicer.mrmlScene)
    liverResectionNode.SetSegmentationNode(self._segmentationNode)
    liverResectionNode.SetTargetOrgan(liverModelNode)
    liverResectionNode.AddTargetTumor(tumorModelNode)
    liverResectionNode.SetResectionInitialization(liverResectionNode.Curved)
    liverResectionNode.CreateDefaultDisplayNodes()
    slicer.mrmlScene.AddNode(liverResectionNode)

#
# LiverTest
#

class LiverTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  Uses ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear()

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_Liver1()

  def test_Liver1(self):

    self.delayDisplay("Starting the test")

    # # Get/create input data

    import SampleData
    registerSampleData()
    inputSegmentation = SampleData.downloadSample('LiverSegmentation000')
    self.delayDisplay('Loaded test data set')

    # slicingContourMarkupNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsSlicingContourNode")
    # slicingContourMarkupNode.AddControlPoint(vtk.vtkVector3d(205, 11, 153))
    # slicingContourMarkupNode.AddControlPoint(vtk.vtkVector3d(-92, 11, 94))
    # slicingContourMarkupNode.SetTarget(inputModelNode)

    # distanceContourMarkupNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsDistanceContourNode")
    # distanceContourMarkupNode.AddControlPoint(vtk.vtkVector3d(205, 11, 153))
    # distanceContourMarkupNode.AddControlPoint(vtk.vtkVector3d(-92, 11, 94))
    # distanceContourMarkupNode.SetTarget(inputModelNode)

    # Test the module logic

    logic = LiverLogic()

    # # Test algorithm with non-inverted threshold
    # logic.process(inputVolume, outputVolume, threshold, True)
    # outputScalarRange = outputVolume.GetImageData().GetScalarRange()
    # self.assertEqual(outputScalarRange[0], inputScalarRange[0])
    # self.assertEqual(outputScalarRange[1], threshold)

    # # Test algorithm with inverted threshold
    # logic.process(inputVolume, outputVolume, threshold, False)
    # outputScalarRange = outputVolume.GetImageData().GetScalarRange()
    # self.assertEqual(outputScalarRange[0], inputScalarRange[0])
    # self.assertEqual(outputScalarRange[1], inputScalarRange[1])

    self.delayDisplay('Test passed')

    pass

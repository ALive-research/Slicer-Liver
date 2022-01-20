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
from BranchSplittingLib import *

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

    ########## BRANCH SPLITTING UI ############
    # Parameters Area
    #
    parametersCollapsibleButton = ctk.ctkCollapsibleButton()
    parametersCollapsibleButton.text = "Liver Segments"
    self.layout.addWidget(parametersCollapsibleButton)
    self.layout.addWidget(self._resectionsTableView)

    # Layout within the dummy collapsible button
    parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)

    #
    # input model selector
    #
    self.inputModelSelector = slicer.qMRMLNodeComboBox()
    self.inputModelSelector.nodeTypes = ["vtkMRMLModelNode"]
    self.inputModelSelector.selectNodeUponCreation = False
    self.inputModelSelector.addEnabled = False
    self.inputModelSelector.removeEnabled = False
    self.inputModelSelector.noneEnabled = True
    self.inputModelSelector.showHidden = False
    self.inputModelSelector.showChildNodeTypes = False
    self.inputModelSelector.setMRMLScene( slicer.mrmlScene )
    self.inputModelSelector.setToolTip( "Select reference model to guide the interaction." )
    parametersFormLayout.addRow("Reference Model: ", self.inputModelSelector)

    #
    # input labelmap selector 
    #
    self.inputLabelMapSelector = slicer.qMRMLNodeComboBox()
    self.inputLabelMapSelector.nodeTypes = ["vtkMRMLLabelMapVolumeNode"]
    self.inputLabelMapSelector.selectNodeUponCreation = False
    self.inputLabelMapSelector.addEnabled = False
    self.inputLabelMapSelector.removeEnabled = False
    self.inputLabelMapSelector.noneEnabled = True
    self.inputLabelMapSelector.showHidden = False
    self.inputLabelMapSelector.showChildNodeTypes = False
    self.inputLabelMapSelector.setMRMLScene( slicer.mrmlScene )
    self.inputLabelMapSelector.setToolTip( "Select the input labelmap to perform segment classification." )
    parametersFormLayout.addRow("Input LabelMap: ", self.inputLabelMapSelector)

    #
    # input volume selector
    #
    self.outputLabelMapSelector = slicer.qMRMLNodeComboBox()
    self.outputLabelMapSelector.nodeTypes = ["vtkMRMLLabelMapVolumeNode"]
    self.outputLabelMapSelector.selectNodeUponCreation = True
    self.outputLabelMapSelector.addEnabled = True
    self.outputLabelMapSelector.editEnabled = True
    self.outputLabelMapSelector.renameEnabled = True
    self.outputLabelMapSelector.removeEnabled = True
    self.outputLabelMapSelector.noneEnabled = True
    self.outputLabelMapSelector.showHidden = False
    self.outputLabelMapSelector.showChildNodeTypes = False
    self.outputLabelMapSelector.setMRMLScene( slicer.mrmlScene )
    self.outputLabelMapSelector.setToolTip( "Select the output labelmap to perform segment classification." )
    parametersFormLayout.addRow("Output LabelMap: ", self.outputLabelMapSelector)


    #
    # Add segment button
    #
    self.addSegmentCenterline = qt.QPushButton("Add segment")
    self.layout.addWidget(self.addSegmentCenterline)


    #
    # Segments classificaion button
    #
    self.segmentsClassificationPushButton = qt.QPushButton("Compute segments")
    
    self.layout.addWidget(self.segmentsClassificationPushButton)
    ########## BRANCH SPLITTING UI ############
    
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

    ########## BRANCH SPLITTING SINGALS ############
    self.inputModelSelector.connect("currentNodeChanged(vtkMRMLNode*)",
                                    self.onSelectInputModel)

    self.inputLabelMapSelector.connect("currentNodeChanged(vtkMRMLNode*)",
                                       self.onSelectInputLabelMap)

    self.outputLabelMapSelector.connect("currentNodeChanged(vtkMRMLNode*)",
                                        self.onSelectOutputLabelMap)
    
    self.segmentsClassificationPushButton.connect("clicked()",
                                                  self.onSegmentsClassificationClicked)
    self.addSegmentCenterline.connect("clicked()",
                                       self.onAddSegmentCenterlineClicked)

    ########## BRANCH SPLITTING SINGALS ############

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

  ########## BRANCH SPLITTING SIGNALS FNCS ##########
  def onSelectInputModel(self):
    node = self.inputModelSelector.currentNode()

    if node is not None:
      model = self.inputModelSelector.currentNode().GetPolyData()
      
      if model is not None:
        self.logic.setTargetModel(model)
        self.logic.enablePointerVisibility()
      else:
        self.logic.disablePointerVisibility()

  def onSelectInputLabelMap(self):
    node = self.inputLabelMapSelector.currentNode()
    self.logic.setInputLabelMap(node)
      
  def onSelectOutputLabelMap(self):
    node = self.outputLabelMapSelector.currentNode()
    self.logic.setOutputLabelMap(node)

  def onAddSegmentCenterlineClicked(self):
    self.logic.addObservers()
    self.logic.enablePointerVisibility()

  def onSegmentsClassificationClicked(self):
    self.logic.doSegmentsClassification()
  ########## BRANCH SPLITTING SIGNALS FNCS ##########
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

    ######### BRANCH SPLITTING LOGIC ############
    colorNode = 'vtkMRMLColorTableNodeFileGenericColors.txt'
    self.colors = slicer.mrmlScene.GetNodeByID(colorNode)
    
    # Initialize class variables
    self.fiducialNodes = list()
    self.markerCounter = 0
    self.lastOriginId = None
    self.lastTargetId = None
    self.leftButtonObserver = None
    self.centerlines = list()
    self.inputLabelMap = None
    self.outputLabelMap = None
    self.segmentsCenterlines = list()
    self.targetModel = None

    # Obtain the rendering elements
    layoutManager = slicer.app.layoutManager()
    self.view = layoutManager.threeDWidget(0).threeDView()
    self.interactor = self.view.renderWindow().GetInteractor()
    self.renderer = self.view.renderWindow().GetRenderers().GetItemAsObject(0)

    # Create the helpers
    self.branchPointerHelper = BranchPointerHelper(self.view,
                                                   self.interactor,
                                                   self.renderer)
  ######### BRANCH SPLITTING LOGIC ############
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

    liverModelNode = slicer.mrmlScene.GetNodesByClassByName('vtkMRMLModelNode', 'liver').GetItemAsObject(0)
    if liverModelNode is None:
      return

    liverDisplayNode = liverModelNode.GetDisplayNode()
    if liverDisplayNode is None:
      return

    liverDisplayNode.SetOpacity(0.2)

  def getSelectedTargetLiverModel(self):
    return self._selectedTargetLiverModelNode

  def addResectionPlane(self):
    liverModelNode = slicer.mrmlScene.GetNodesByClassByName('vtkMRMLModelNode', 'liver').GetItemAsObject(0)
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
    liverModelNode = slicer.mrmlScene.GetNodesByClassByName('vtkMRMLModelNode', 'liver').GetItemAsObject(0)
    tumorModelNode = slicer.mrmlScene.GetNodesByClassByName('vtkMRMLModelNode', 'tumor1').GetItemAsObject(0)
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
  
  ####### BRANCH SPLITTING LOGIC #######
  def addObservers(self):
    self.leftButtonObserver = self.interactor.AddObserver("LeftButtonPressEvent",
                                                          self.onMouseLeftButton, 1.0)

  def removeObservers(self):
    if self.leftButtonObserver != None:
      self.interactor.RemoveObserver(self.leftButtonObserver)
      self.leftButtonObserver = None

  def setTargetModel(self, polyData):
    self.branchPointerHelper.setTargetModel(polyData)
    self.targetModel = polyData

  def setInputLabelMap(self, labelMapNode):
    self.inputLabelMap = labelMapNode

  def setOutputLabelMap(self, labelMapNode):
    self.outputLabelMap = labelMapNode
    
  def insertNewFiducialNode(self):
    if self.branchPointerHelper.lastClosest is None:
      return

    # Set up the display
    # displayNode = slicer.vtkMRMLMarkupsDisplayNode()
    # displayNode.SetGlyphScale(5)
    # color = [0,0,0,0]
    # self.colors.GetColor(int(self.markerCounter/2)+1,color)
    # displayNode.SetSelectedColor(color[:3])
    # displayNode.SetColor(color[:3])
    # displayNode.Visibility2DOff()
    # slicer.mrmlScene.AddNode(displayNode)

    # node = slicer.vtkMRMLMarkupsFiducialNode()
    # node.AddFiducialFromArray(self.branchPointerHelper.lastClosest,
    #                           "Origin " + str(len(self.fiducialNodes)+1))
    # node.SetAndObserveDisplayNodeID(displayNode.GetID())
    # node.LockedOn()
    # node.HideFromEditorsOn()

    # slicer.mrmlScene.AddNode(node)

    # self.fiducialNodes.append(node)

    color = [0,0,0,0]
    self.colors.GetColor(len(self.segmentsCenterlines)+1,color)

    centerlineHelper = CenterlineHelper()
    centerlineHelper.inputVesselModel = self.targetModel
    centerlineHelper.segmentId=len(self.segmentsCenterlines)
    centerlineHelper.setColor(color)
    self.lastOriginId = self.branchPointerHelper.lastClosestId
    self.branchPointerHelper.lastClosest = None
    self.markerCounter += 1
    centerlineHelper.appendOriginId(self.branchPointerHelper.lastClosestId)
    self.segmentsCenterlines.append(centerlineHelper)

  def insertNewPosition(self):
    if self.branchPointerHelper.lastClosest is None:
      return

    # node = self.fiducialNodes[-1]
    # node.AddFiducialFromArray(self.branchPointerHelper.lastClosest,
    #                           "End " + str(len(self.fiducialNodes)))

    # color = [0,0,0,0]
    # self.colors.GetColor(int(self.markerCounter/2)+1,color)

    self.lastTargetId = self.branchPointerHelper.lastClosestId
    self.branchPointerHelper.lastClosest = None
    centerlineHelper = self.segmentsCenterlines[-1]
    centerlineHelper.appendTargetId(self.branchPointerHelper.lastClosestId)
    centerlineHelper.update()
    centerline = centerlineHelper.centerline

    # Compute the centerline
    # centerline = self.centerlineHelper.computeCenterline(self.branchPointerHelper.targetModel,
    #                                                      self.lastOriginId,
    #                                                      self.lastTargetId,
    #                                                      int(self.markerCounter/2))

    self.removeObservers()
    self.disablePointerVisibility()

    self.centerlines.append(centerline)

    self.markerCounter += 1

  def removeFiducials(self):
    for i in self.fiducialNodes:
      slicer.mrmlScene.RemoveNode(i.GetDisplayNode())
      slicer.mrmlScene.RemoveNode(i)
    self.branchPointerHelper.lastClosest = None
    self.markerCounter = 0
    self.fiducialNodes = list()

  def onMouseLeftButton(self, obj, event):
    if self.markerCounter % 2 == 0:
      self.insertNewFiducialNode()
    else:
      self.insertNewPosition()

  def enablePointerVisibility(self):
    self.branchPointerHelper.enablePointerVisibility()

  def disablePointerVisibility(self):
    self.branchPointerHelper.disablePointerVisibility()

  def doSegmentsClassification(self):
    appendPolyData = vtk.vtkAppendPolyData()
    for i in range(len(self.centerlines)):
      appendPolyData.AddInputData(self.centerlines[i])
      print("Appending Centerline")
    appendPolyData.Update()

    # This is imported here because vtkSlicerBranchSplittingModuleLogicPython
    # might not be available when this module loads. In here importing happens
    # on user interaction time, when all modules are loaded.
  
    from vtkSlicerBranchSplittingModuleLogicPython import vtkSegmentClassificationLogic

    # Create the segmentsclassification logic
    scl = vtkSegmentClassificationLogic()
    scl.SegmentClassification(appendPolyData.GetOutput(),
                              self.inputLabelMap,
                              self.outputLabelMap)

    # Set the color of the labelmap to the same used here in the logic
    outputLabelMapDisplayNode = self.outputLabelMap.GetDisplayNode()
    if outputLabelMapDisplayNode is None:
      self.outputLabelMap.CreateDefaultDisplayNodes()

    outputLabelMapDisplayNode = self.outputLabelMap.GetDisplayNode()
    outputLabelMapDisplayNode.SetAndObserveColorNodeID(self.colors.GetID())
  ######### BRANCH SPLITTING LOGIC ############

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
  ######## BRANCH SPLITTING TEST ########
    #self.test_BranchSplitting()
  ######## BRANCH SPLITTING TEST ########

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

  ######## BRANCH SPLITTING TEST ########
  def test_BranchSplitting1(self):
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
    #
    # first, get some data
    #
    import SampleData
    SampleData.downloadFromURL(
      nodeNames='FA',
      fileNames='FA.nrrd',
      uris='http://slicer.kitware.com/midas3/download?items=5767',
      checksums='SHA256:12d17fba4f2e1f1a843f0757366f28c3f3e1a8bb38836f0de2a32bb1cd476560')
    self.delayDisplay('Finished with download and loading')

    volumeNode = slicer.util.getNode(pattern="FA")
    logic = BranchSplittingLogic()
    self.assertIsNotNone( logic.hasImageData(volumeNode) )
    self.delayDisplay('Test passed!')
  ######## BRANCH SPLITTING TEST ########

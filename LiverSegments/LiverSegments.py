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
#   This file was originally developed by Ole V. Solberg, Geir A. Tangen, Javier
#   Perez-de-Frutos (SINTEF, Norway) and Rafael Palomar (Oslo University
#   Hospital) through the ALive project (grant nr. 311393).
#
# ==============================================================================

import os
import unittest
import logging
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin

#
# LiverSegments
#

class LiverSegments(ScriptedLoadableModule):
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

    # Additional initialization step after application startup is complete
    #slicer.app.connect("startupCompleted()", registerSampleData)

    #Hide module, so that it only shows up in the Liver module, and not as a separate module
    parent.hidden = True

#
# Register sample data sets in Sample Data module
#

class LiverSegmentsWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
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
    uiWidget = slicer.util.loadUI(self.resourcePath('UI/LiverSegments.ui'))
    self.layout.addWidget(uiWidget)

    # Add a spacer at the botton to keep the UI flowing from top to bottom
    spacerItem = qt.QSpacerItem(0,0, qt.QSizePolicy.Minimum, qt.QSizePolicy.MinimumExpanding)
    self.layout.addSpacerItem(spacerItem)

    self.ui = slicer.util.childWidgetVariables(uiWidget)

    self.nodeSelectors = [
        (self.ui.inputSurfaceSelector, "InputSurface"),
        (self.ui.endPointsMarkupsSelector, "CenterlineSegment"),
        ]

    # Set scene in MRML widgets. Make sure that in Qt designer
    # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
    # "setMRMLScene(vtkMRMLScene*)" slot.
    uiWidget.setMRMLScene(slicer.mrmlScene)

    # Create logic class. Logic implements all computations that should be possible to run
    # in batch mode, without a graphical user interface.
    self.logic = LiverSegmentsLogic()
#    self.ui.parameterNodeSelector.addAttribute("vtkMRMLScriptedModuleNode", "ModuleName", self.moduleName)
    self.setParameterNode(self.logic.getParameterNode())

    # Color number in lookup table
    self.colorNumber = 0

    # Connections
#    self.ui.parameterNodeSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.setParameterNode)
    self.ui.inputSurfaceSelector.connect('currentNodeChanged(bool)', self.updateParameterNodeFromGUI)
    self.ui.inputSegmentSelectorWidget.connect('currentSegmentChanged(QString)', self.updateParameterNodeFromGUI)
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)
    self.ui.endPointsMarkupsSelector.connect('nodeAddedByUser(vtkMRMLNode*)', self.newEndpointsListCreated)

    # These connections ensure that whenever user changes some settings on the GUI, that is saved in the MRML scene
    # (in the selected parameter node).
    #        self.ui.inputSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
    #        self.ui.outputSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
    #        self.ui.imageThresholdSliderWidget.connect("valueChanged(double)", self.updateParameterNodeFromGUI)
    #        self.ui.invertOutputCheckBox.connect("toggled(bool)", self.updateParameterNodeFromGUI)
    #        self.ui.invertedOutputSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)

    # Buttons
    self.ui.addSegmentButton.connect('clicked(bool)', self.onAddSegmentButton)
    self.ui.calculateSegmentsButton.connect('clicked(bool)', self.onCalculateSegmentButton)

    # Make sure parameter node is initialized (needed for module reload)
    self.initializeParameterNode()

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

    # Select default input nodes if nothing is selected yet to save a few clicks for the user
    #      if not self._parameterNode.GetNodeReference("InputVolume"):
    #          firstVolumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
    #        if firstVolumeNode:
    #          self._parameterNode.SetNodeReferenceID("InputVolume", firstVolumeNode.GetID())

  def setParameterNode(self, inputParameterNode):
    """
    Set and observe parameter node.
    Observation is needed because when the parameter node is changed then the GUI must be updated immediately.
    """

    if inputParameterNode:
      self.logic.setDefaultParameters(inputParameterNode)

    # Set parameter node in the parameter node selector widget
#    wasBlocked = self.ui.parameterNodeSelector.blockSignals(True)
#    self.ui.parameterNodeSelector.setCurrentNode(inputParameterNode)
#    self.ui.parameterNodeSelector.blockSignals(wasBlocked)

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
#        self.ui.inputSegmentSelectorWidget.setVisible(True)
#    else:
#        self.ui.inputSegmentSelectorWidget.setVisible(False)


    #    self.ui.inputSelector.setCurrentNode(self._parameterNode.GetNodeReference("InputVolume"))
    #     self.ui.outputSelector.setCurrentNode(self._parameterNode.GetNodeReference("OutputVolume"))

    # Update buttons states and tooltips
    #    if self._parameterNode.GetNodeReference("InputVolume") and self._parameterNode.GetNodeReference("OutputVolume"):
    #      self.ui.applyButton.toolTip = "Compute output volume"
    #      self.ui.applyButton.enabled = True
    #    else:
    #      self.ui.applyButton.toolTip = "Select input and output volume nodes"
    #      self.ui.applyButton.enabled = False

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
    #print("surface: ", surface)
    #print("segmentId: ", segmentId)
    #Using _parameterNode don't work yet
    #inputSurfacePolyData = self.logic.polyDataFromNode(self._parameterNode.GetNodeReference("InputSurface"),
    #                                                   self._parameterNode.GetParameter("InputSegmentID"))

    centerlineProcessingLogic = self.logic.getCenterlineLogic()
    inputSurfacePolyData = centerlineProcessingLogic.polyDataFromNode(surface, segmentId)
    if not inputSurfacePolyData or inputSurfacePolyData.GetNumberOfPoints() == 0:
        raise ValueError("Valid input surface is required")

    preprocessedPolyData = self.logic.preprocessAndDecimate(inputSurfacePolyData)
    return preprocessedPolyData

  def createSegmentName(self, endPointsMarkupsNode):
    nodeName = "CenterlineSegment_" + endPointsMarkupsNode.GetAttribute("SegmentIndex")
    return nodeName

  def createCenterlineNode(self, endPointsMarkupsNode):
    nodeName = self.createSegmentName(endPointsMarkupsNode)
    centerlineModelNode = slicer.mrmlScene.GetNodeByID(nodeName)
    if centerlineModelNode:
      print('Adding to existing centerlineModelNode')
      #print('Replacing centerlineModelNode:', nodeName)
      #slicer.mrmlScene.RemoveNode(centerlineModelNode)
    else:
      centerlineModelNode = slicer.mrmlScene.AddNewNodeByClassWithID('vtkMRMLModelNode', nodeName, nodeName)

    if not centerlineModelNode:
        raise ValueError('Error: Cannot create node: ', nodeName)

    self.logic.copyIndex(endPointsMarkupsNode, centerlineModelNode)
    return centerlineModelNode

  def newEndpointsListCreated(self):
    self.colorNumber += 1
    self.updateSelectorColor()
    self.ui.endPointsMarkupsPlaceWidget.setPlaceModeEnabled(True)

  def updateSelectorColor(self):
    color = self.getCurrentColor()
    color255 = [int(i * 255) for i in color]
    self.ui.endPointsMarkupsPlaceWidget.ColorButton.setColor(qt.QColor(color255[0], color255[1], color255[2]))

  def getCurrentColor(self):
    color = [1, 1, 1, 1]
    colormap = slicer.mrmlScene.GetNodeByID('vtkMRMLColorTableNodeLabels')
    colormap.GetColor(self.colorNumber, color)
    del color[3:]
    return color

  def useColorFromSelector(self, centerlineModelNode):
    inputColor = self.ui.endPointsMarkupsPlaceWidget.ColorButton.color
    centerlineModelNode.GetDisplayNode().SetColor(inputColor.redF(), inputColor.greenF(), inputColor.blueF())

  def onAddSegmentButton(self):
    endPointsMarkupsNode = self.ui.endPointsMarkupsSelector.currentNode()
    self.ui.endPointsMarkupsPlaceWidget.setPlaceModeEnabled(False)
    self.logic.setIndex(endPointsMarkupsNode)

    slicer.app.pauseRender()
    qt.QApplication.setOverrideCursor(qt.Qt.WaitCursor)

    try:
        preprocessedPolyData = self.getPreprocessedPolyData()
    except ValueError:
        print("Error: Preprocessing of polydata fails")
        slicer.app.resumeRender()
        qt.QApplication.restoreOverrideCursor()
        raise

    try:
        centerlineModelNode = self.createCenterlineNode(endPointsMarkupsNode)
    except ValueError:
        print("Error: Failed to generate centerline model")

    try:
        centerlineProcessingLogic = self.logic.getCenterlineLogic()
        centerlinePolyData, voronoiDiagramPolyData = centerlineProcessingLogic.extractCenterline(preprocessedPolyData, endPointsMarkupsNode)

        decimatedCenterlinePolyData = self.logic.decimateLine(centerlinePolyData)
        mergedLines = self.mergePolydata(centerlineModelNode.GetMesh(), decimatedCenterlinePolyData)
        centerlineModelNode.SetAndObserveMesh(mergedLines)

        centerlineModelNode.CreateDefaultDisplayNodes()
        self.useColorFromSelector(centerlineModelNode)
        centerlineModelNode.GetDisplayNode().SetLineWidth(3)
        endPointsMarkupsNode.SetDisplayVisibility(False)
    except ValueError:
        print("Error: Failed to extract centerline")

    slicer.app.resumeRender()
    qt.QApplication.restoreOverrideCursor()

#    observationTag = endPointsMarkupsNode.AddObserver(slicer.vtkMRMLMarkupsNode.PointModifiedEvent,
#        self.onControlPointsModified)

#    self.logic.build_centerline_model(centerlinePolyData, centerlineModelNode.GetID())

#  def onControlPointsModified(self, caller, event):
#    print("onControlPointsModified")
    # New centerline should be calculated
    # The center model (composition of all centerlines) should be updated

  def mergePolydata(self, existingPolyData, newPolyData):
    combinedPolyData = vtk.vtkAppendPolyData()
    combinedPolyData.AddInputData(existingPolyData)
    combinedPolyData.AddInputData(newPolyData)
    combinedPolyData.Update()
    return combinedPolyData.GetOutput()

  def onCalculateSegmentButton(self):
    if self.developerMode is True:
      import time
      startTime = time.time()

    segmentationNode = self.ui.inputSurfaceSelector.currentNode()
    centerlineModel = self.logic.build_centerline_model(segmentationNode)
    refVolumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
    if not (refVolumeNode):
        raise ValueError("Missing inputs to calculate vascular segments")

    slicer.app.pauseRender()
    qt.QApplication.setOverrideCursor(qt.Qt.WaitCursor)

    try:
        self.logic.calculateVascularSegments(refVolumeNode, segmentationNode, centerlineModel)
    except ValueError:
        print("Error: Failing when calculating vascular segments")

    slicer.app.resumeRender()
    qt.QApplication.restoreOverrideCursor()

    if self.developerMode is True:
      stopTime = time.time()
      logging.info(f'Vascular Segments processing completed in {stopTime-startTime:.2f} seconds')


# LiverSegmentsLogic
#

class LiverSegmentsLogic(ScriptedLoadableModuleLogic):

  def __init__(self):
    ScriptedLoadableModuleLogic.__init__(self)

    self._vascularSegmentTupleList = list()
    self._centerlines = list()
    self._inputLabelMap = None
    self._outputLabelMap = None
    self.centerlineProcessingLogic = None
    self.segmentIndex = 0

    from vtkSlicerLiverSegmentsModuleLogicPython import vtkLiverSegmentsLogic
    # Create the segmentsclassification logic
    self.scl = vtkLiverSegmentsLogic()

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

  def getSegmentIndex(self):
    self.segmentIndex += 1
    return self.segmentIndex

  def createCompleteCenterlineModel(self):
    nodeName = "CenterlineModel"
    completeCenterlineModelNode = slicer.mrmlScene.GetNodeByID(nodeName)
    if completeCenterlineModelNode:
        print('Replacing completeCenterlineModelNode: ', nodeName)
        slicer.mrmlScene.RemoveNode(completeCenterlineModelNode)

    completeCenterlineModelNode = slicer.mrmlScene.AddNewNodeByClassWithID('vtkMRMLModelNode', nodeName, nodeName)
    dummyPolyData = vtk.vtkPolyData()
    completeCenterlineModelNode.SetAndObservePolyData(dummyPolyData)
    if not completeCenterlineModelNode:
        print('Error: Cannot create node: ', nodeName)

    completeCenterlineModelNode.CreateDefaultDisplayNodes()
    displayNode = completeCenterlineModelNode.GetDisplayNode()
    displayNode.ScalarVisibilityOn()
    displayNode.SetActiveScalar('SegmentId', 2)
    displayNode.SetScalarRangeFlagFromString('UseColorNodeScalarRange')
    displayNode.SetLineWidth(3)
    colormap = slicer.mrmlScene.GetNodeByID('vtkMRMLColorTableNodeLabels')
    completeCenterlineModelNode.GetDisplayNode().SetAndObserveColorNodeID(colormap.GetID())

    return completeCenterlineModelNode


  def build_centerline_model(self, segmentationNode):
    centerlineModel = self.createCompleteCenterlineModel()
    #centerlineModel is empty - Start filling it with segments
    centerlineSegmentsDict = slicer.util.getNodes("CenterlineSegment*")
    for name, segmentObject in centerlineSegmentsDict.items():
      if segmentObject.GetClassName() == "vtkMRMLModelNode":
        segmentId = int(segmentObject.GetAttribute("SegmentIndex"))
        self.scl.MarkSegmentWithID(segmentObject, segmentId)
        self.scl.AddSegmentToCenterlineModel(centerlineModel, segmentObject)
    self.scl.InitializeCenterlineSearchModel(centerlineModel)
    return centerlineModel

  def calculateVascularSegments(self, refVolume, segmentation, centerlineModel):
    segmentationIds = vtk.vtkStringArray()
    labelmapVolumeNode = slicer.mrmlScene.GetFirstNodeByName("VascularSegments")
    if not labelmapVolumeNode:
        labelmapVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", "VascularSegments")

    # Get voxels tagged as liver
    segmentId = segmentation.GetSegmentation().GetSegmentIdBySegmentName('liver')
    #Check metadata for segmentation
    #segm = vtk.vtkSegmentation()
    segm = segmentation.GetSegmentation()
    numberOfSegments = segm.GetNumberOfSegments()
    print('Number of segments: ', numberOfSegments)
    liverSegm = segm.GetSegment(segmentId)
    print('Segment navn: ', liverSegm.GetName())
    print('Segment Label: ', liverSegm.GetLabelValue())
#    bounds = [0,0,0,0,0,0]
#    refVolume.GetBounds(bounds)
#    origin = refVolume.GetOrigin()
#    print('Segment bounds: ', origin)

    segmentationIds.InsertNextValue(segmentId)
    slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(segmentation, segmentationIds, labelmapVolumeNode, refVolume)

    result = self.scl.SegmentClassificationProcessing(centerlineModel, labelmapVolumeNode)
    if result==0:
        raise ValueError("Corrupt centerline model - Not possible to calculate vascular segments")

    colormap = slicer.mrmlScene.GetNodeByID('vtkMRMLColorTableNodeLabels')
    labelmapVolumeNode.GetDisplayNode().SetAndObserveColorNodeID(colormap.GetID())
    slicer.util.arrayFromVolumeModified(labelmapVolumeNode)

    #Show label map volume
    slicer.util.setSliceViewerLayers(label=labelmapVolumeNode)

  def setIndex(self, endPointsMarkupsNode):
    if not endPointsMarkupsNode:
        raise ValueError("No endPointsMarkupsNode")
    segmentIndex = endPointsMarkupsNode.GetAttribute("SegmentIndex")
    print("SegmentIndex: ", segmentIndex)
    if(segmentIndex == None):
      endPointsMarkupsNode.SetAttribute("SegmentIndex", str(self.getSegmentIndex()))
      segmentIndex = endPointsMarkupsNode.GetAttribute("SegmentIndex")
      print("New segmentIndex: ", segmentIndex)

  def copyIndex(self, endPointsMarkupsNode, centerlineModelNode):
    centerlineModelNode.SetAttribute("SegmentIndex", endPointsMarkupsNode.GetAttribute("SegmentIndex"))

  #Using code from centerlineProcessingLogic.preprocess
  def preprocessAndDecimate(self, surfacePolyData):
    parameters = {}
    inputSurfaceModelNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", "tempInputSurfaceModel")
    inputSurfaceModelNode.SetAndObserveMesh(surfacePolyData)
    parameters["inputModel"] = inputSurfaceModelNode
    outputSurfaceModelNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", "tempDecimatedSurfaceModel")
    parameters["outputModel"] = outputSurfaceModelNode
    parameters["reductionFactor"] = 0.8
    parameters["method"] = "FastQuadric"
    parameters["aggressiveness"] = 4
    decimation = slicer.modules.decimation
    cliNode = slicer.cli.runSync(decimation, None, parameters)
    surfacePolyData = outputSurfaceModelNode.GetPolyData()
    slicer.mrmlScene.RemoveNode(inputSurfaceModelNode)
    slicer.mrmlScene.RemoveNode(outputSurfaceModelNode)
    slicer.mrmlScene.RemoveNode(cliNode)

    surfaceCleaner = vtk.vtkCleanPolyData()
    surfaceCleaner.SetInputData(surfacePolyData)
    surfaceCleaner.Update()

    surfaceTriangulator = vtk.vtkTriangleFilter()
    surfaceTriangulator.SetInputData(surfaceCleaner.GetOutput())
    surfaceTriangulator.PassLinesOff()
    surfaceTriangulator.PassVertsOff()
    surfaceTriangulator.Update()

    normals = vtk.vtkPolyDataNormals()
    normals.SetInputData(surfaceTriangulator.GetOutput())
    normals.SetAutoOrientNormals(1)
    normals.SetFlipNormals(0)
    normals.SetConsistency(1)
    normals.SplittingOff()
    normals.Update()

    return normals.GetOutput()

  def decimateLine(self, polyDataLine):
    decimate = vtk.vtkDecimatePolylineFilter()
    decimate.SetInputData(polyDataLine)
    decimate.SetTargetReduction(.90)
    decimate.Update()
    return decimate.GetOutput()

class LiverSegmentsTest(ScriptedLoadableModuleTest):
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
    self.test_LiverSegments1()

  def test_LiverSegments1(self):
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

    logic = LiverSegmentsLogic()

    self.delayDisplay('Test passed')

import os
import unittest
import logging
import time
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
from ExtractCenterline import ExtractCenterlineLogic

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
    self.centerlineProcessingLogic = None
    self._parameterNode = None
    self._updatingGUIFromParameterNode = False
    ScriptedLoadableModuleWidget.__init__(self, parent)
    VTKObservationMixin.__init__(self)  # needed for parameter node observation
    self._vascularModelForPointSelection = None

  def setup(self):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.setup(self)

    # Load widget from .ui file (created by Qt Designer)
    uiWidget = slicer.util.loadUI(self.resourcePath('UI/LiverSegments.ui'))
    self.layout.addWidget(uiWidget)
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
    self.centerlineProcessingLogic = ExtractCenterlineLogic()
    self.ui.parameterNodeSelector.addAttribute("vtkMRMLScriptedModuleNode", "ModuleName", self.moduleName)
    self.setParameterNode(self.logic.getParameterNode())

    # Color number in lookup table
    self.colorNumber = 0


    # Connections
    self.ui.parameterNodeSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.setParameterNode)
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
    wasBlocked = self.ui.parameterNodeSelector.blockSignals(True)
    self.ui.parameterNodeSelector.setCurrentNode(inputParameterNode)
    self.ui.parameterNodeSelector.blockSignals(wasBlocked)

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
        self.ui.inputSegmentSelectorWidget.setVisible(True)
    else:
        self.ui.inputSegmentSelectorWidget.setVisible(False)


    #    self.ui.inputSelector.setCurrentNode(self._parameterNode.GetNodeReference("InputVolume"))
    #     self.ui.outputSelector.setCurrentNode(self._parameterNode.GetNodeReference("OutputVolume"))
    #    self.ui.invertedOutputSelector.setCurrentNode(self._parameterNode.GetNodeReference("OutputVolumeInverse"))
    #    self.ui.imageThresholdSliderWidget.value = float(self._parameterNode.GetParameter("Threshold"))
    #    self.ui.invertOutputCheckBox.checked = (self._parameterNode.GetParameter("Invert") == "true")

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
    #    self._parameterNode.SetParameter("Threshold", str(self.ui.imageThresholdSliderWidget.value))
    #    self._parameterNode.SetParameter("Invert", "true" if self.ui.invertOutputCheckBox.checked else "false")
    #    self._parameterNode.SetNodeReferenceID("OutputVolumeInverse", self.ui.invertedOutputSelector.currentNodeID)

    #    self._parameterNode.EndModify(wasModified)

  def getPreprocessedPolyData(self):
    surface = self.ui.inputSurfaceSelector.currentNode()
    segmentId = self.ui.inputSegmentSelectorWidget.currentSegmentID()
    #print("surface: ", surface)
    #print("segmentId: ", segmentId)
    #Using _parameterNode don't work yet
    #inputSurfacePolyData = self.logic.polyDataFromNode(self._parameterNode.GetNodeReference("InputSurface"),
    #                                                   self._parameterNode.GetParameter("InputSegmentID"))
    inputSurfacePolyData = self.centerlineProcessingLogic.polyDataFromNode(surface, segmentId)
    if not inputSurfacePolyData or inputSurfacePolyData.GetNumberOfPoints() == 0:
        raise ValueError("Valid input surface is required")

    targetNumberOfPoints = 5000
    decimationAggressiveness = 4
    subdivideInputSurface = 0

    preprocessedPolyData = self.centerlineProcessingLogic.preprocess(inputSurfacePolyData, targetNumberOfPoints, decimationAggressiveness, subdivideInputSurface)
    return preprocessedPolyData

  def createSegmentName(self, endPointsMarkupsNode):
    endpointsName = endPointsMarkupsNode.GetName()
    split = endpointsName.split('_')
    if len(split) > 1:
      index = split[1]
      nodeName = "CenterlineSegment_" + str(index)
    else:
      nodeName = "CenterlineSegment"
    return nodeName

  def createCenterlineNode(self, endPointsMarkupsNode):
    nodeName = self.createSegmentName(endPointsMarkupsNode)
    centerlineModelNode = slicer.mrmlScene.GetNodeByID(nodeName)
    if centerlineModelNode:
      print('Replacing centerlineModelNode:', nodeName)
      slicer.mrmlScene.RemoveNode(centerlineModelNode)

    centerlineModelNode = slicer.mrmlScene.AddNewNodeByClassWithID('vtkMRMLModelNode', nodeName, nodeName)

    if not centerlineModelNode:
      print('Error: Cannot create node: ', nodeName)

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
#    slicer.util.showStatusMessage('Starting calculation', 3000)
    endPointsMarkupsNode = self.ui.endPointsMarkupsSelector.currentNode()
    self.ui.endPointsMarkupsPlaceWidget.setPlaceModeEnabled(False)

    if not endPointsMarkupsNode:
        raise ValueError("No endPointsMarkupsNode")

    preprocessedPolyData = self.getPreprocessedPolyData()

    centerlineModelNode = self.createCenterlineNode(endPointsMarkupsNode)

    centerlinePolyData, voronoiDiagramPolyData = self.centerlineProcessingLogic.extractCenterline(
        preprocessedPolyData, endPointsMarkupsNode)
    centerlineModelNode.SetAndObserveMesh(centerlinePolyData)
    centerlineModelNode.CreateDefaultDisplayNodes()
    self.useColorFromSelector(centerlineModelNode)
    centerlineModelNode.GetDisplayNode().SetLineWidth(3)
    endPointsMarkupsNode.SetDisplayVisibility(False)

#    observationTag = endPointsMarkupsNode.AddObserver(slicer.vtkMRMLMarkupsNode.PointModifiedEvent,
#        self.onControlPointsModified)

#    self.logic.build_centerline_model(centerlinePolyData, centerlineModelNode.GetID())

#  def onControlPointsModified(self, caller, event):
#    print("onControlPointsModified")
    # New centerline should be calculated
    # The center model (composition of all centerlines) should be updated


  def onCalculateSegmentButton(self):
#    vascularSegmentsOutputNode = self.ui.outputSegmentsSelector.currentNode()
#    if not vascularSegmentsOutputNode:
#      raise ValueError("No vascularSegmentsOutputNode")
#    print(vascularSegmentsOutputNode)
#    get volumenode
#    specify metadata for the labelmap
#    or set as reference volume?
    segmentationNode = self.ui.inputSurfaceSelector.currentNode()
    self.logic.build_centerline_model(segmentationNode)
    refVolumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
    if not (refVolumeNode):
        raise ValueError("Missing inputs to calculate vascular segments")

    self.logic.calculateVascularSegments(refVolumeNode, segmentationNode)



# LiverSegmentsLogic
#

class LiverSegmentsLogic(ScriptedLoadableModuleLogic):

  def __init__(self):
    ScriptedLoadableModuleLogic.__init__(self)

    self._vascularSegmentTupleList = list()
    self._centerlines = list()
    self._inputLabelMap = None
    self._outputLabelMap = None

    from vtkSlicerLiverSegmentsModuleLogicPython import vtkSegmentClassificationLogic
    # Create the segmentsclassification logic
    self.scl = vtkSegmentClassificationLogic()

  def setDefaultParameters(self, parameterNode):
    """
    Initialize parameter node with default settings.
    """

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

    return completeCenterlineModelNode


  def build_centerline_model(self, segmentationNode):
    centerlineModel = self.createCompleteCenterlineModel()
    #centerlineModel is empty - Start filling it with segments
    centerlineSegmentsDict = slicer.util.getNodes("CenterlineSegment*")
    segmentId = 0
    for name, segmentObject in centerlineSegmentsDict.items():
        segmentId += 1
        color = segmentObject.GetDisplayNode().GetColor()
        print(name, segmentId, color)
        self.scl.markSegmentWithID(segmentObject, segmentId)
        self.scl.addSegmentToCenterlineModel(centerlineModel, segmentObject)

  def createColorMap(self):
    colorTableNode = slicer.mrmlScene.CreateNodeByClass("vtkMRMLColorTableNode")
    colorTableNode.SetTypeToUser()
    colorTableNode.HideFromEditorsOff()  # make the color table selectable in the GUI outside Colors module
    slicer.mrmlScene.AddNode(colorTableNode); colorTableNode.UnRegister(None)
    largestLabelValue = max([name_value[1] for name_value in segment_names_to_labels])
    colorTableNode.SetNumberOfColors(largestLabelValue + 1)
    colorTableNode.SetNamesInitialised(True) # prevent automatic color name generation

#  def updateColorMap(self, labelValue, color, colorMap):

  def setInputLabelMap(self, labelMapNode):
      self._inputLabelMap = labelMapNode

  def setOutputLabelMap(self, labelMapNode):
      self._outputLabelMap = labelMapNode

  def calculateVascularSegments(self, refVolume, segmentation):
    startTime = time.time()
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

#    self.setOutputLabelMap(labelmapVolumeNode)
    import numpy as np
    labelArray = slicer.util.arrayFromSegmentBinaryLabelmap(segmentation, segmentId, refVolume)
    print('labelArray shape: ', labelArray.shape)
    print('labelArray size: ', labelArray.size)
#    points = np.where(labelArray == 1)
    # Get indexes with non-zero label
#    points = np.nonzero(labelArray)
#    numberOfPoints = len(points[0])
#    print(points)
#    print(points[0][0], points[1][0], points[2][0])
#    print("start gen list")
#    list_of_points = list(zip(points[0], points[1], points[2]))
#    print(len(list_of_points))
#    p=0
#    for i in range(numberOfPoints):
#        coordinate = points[0][i], points[1][i], points[2][i]
#        value = labelArray[coordinate]
#        if value == 0:
#            p = p+1
#            print(coordinate)
#    print(p)
#    bounds = [0,0,0,0,0,0]
#    labelmapVolumeNode.GetBounds(bounds)
#    print('Bounds before : ', bounds)
#    slicer.util.updateVolumeFromArray(labelmapVolumeNode, labelArray)
#    labelmapVolumeNode.GetBounds(bounds)
#    print('Bounds after : ', bounds)

    self.scl.SegmentClassificationProcessing(labelmapVolumeNode)
    stopTime = time.time()
    logging.info(f'calculateVascularSegments processing completed in {stopTime-startTime:.2f} seconds')

#    print(points.shape)
#    print(points)
#    points_z_array = points[:,
#    vol = slicer.util.arrayFromVolume(refVolume)
#    values = vol[points]
#    print(points)
#    print(points.shape)

#    appendPolyData = vtk.vtkAppendPolyData()
#    for i in range(len(self._centerlines)):
#        appendPolyData.AddInputData(self._centerlines[i])
#    appendPolyData.Update()

#    self.scl.SegmentClassification(appendPolyData.GetOutput(),
#                                    labelmapVolumeNode)


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

import os
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
from BranchSplittingLib import *


#
# BranchSplitting
#

class BranchSplitting(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Branch Splitting" 
    self.parent.categories = ["Liver Segments"]
    self.parent.dependencies = []
    self.parent.contributors = ["Rafael Palomar (OUS)"] 
    self.parent.helpText = """
    This is a scriptable module to perform branch splitting of vessels.
    """
    self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """ """ 

#
# BranchSplittingWidget
#

class BranchSplittingWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):

    ScriptedLoadableModuleWidget.__init__(self, parent)

    self.logic = BranchSplittingLogic()

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    # Instantiate and connect widgets ...

    #
    # Parameters Area
    #
    parametersCollapsibleButton = ctk.ctkCollapsibleButton()
    parametersCollapsibleButton.text = "Parameters"
    self.layout.addWidget(parametersCollapsibleButton)

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

    # Add vertical spacer
    self.layout.addStretch(1)

    #
    # Connections signals -- slots
    #
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

  def onReload(self):
    if self.logic:
      self.logic.removeObservers()
      self.logic.disablePointerVisibility()
      self.logic.removeFiducials()
    super().onReload()
  
  def cleanup(self):
    pass

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

  def enter(self):

    """This function determines what happens when the module widget is enabled
    in Slicer"""

    print("enter")

    # self.logic.addObservers()
    # self.logic.enablePointerVisibility()

  def exit(self):
    
    """This function determines what happens when the module widget exited
    (e.g., another module is selected)"""

    print("exit")
    
    self.logic.disablePointerVisibility()
    self.logic.removeObservers()

    
#
# BranchSplittingLogic
#

class BranchSplittingLogic(ScriptedLoadableModuleLogic):

  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self):

    """ This is the constructor. Here 

    (1) The class variables are initialized.
    (2) The visualization pipeline is built
    (3) The observers related to display of pointer indicator and left button press are set"""

    super().__init__(self)

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
      
    
        
class BranchSplittingTest(ScriptedLoadableModuleTest):
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
    self.test_BranchSplitting()

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

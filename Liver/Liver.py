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
    self.parent.title = "Liver"  # TODO: make this more human readable by adding spaces
    self.parent.categories = ["Examples"]  # TODO: set categories (folders where the module shows up in the module selector)
    self.parent.dependencies = []  # TODO: add here list of module names that this module requires
    self.parent.contributors = ["John Doe (AnyWare Corp.)"]  # TODO: replace with "Firstname Lastname (Organization)"
    # TODO: update with short description of the module and a link to online module documentation
    self.parent.helpText = """
This is an example of scripted loadable module bundled in an extension.
See more information in <a href="https://github.com/organization/projectname#Liver">module documentation</a>.
"""
    # TODO: replace with organization, grant and thanks
    self.parent.acknowledgementText = """
This file was originally developed by Jean-Christophe Fillion-Robin, Kitware Inc., Andras Lasso, PerkLab,
and Steve Pieper, Isomics, Inc. and was partially funded by NIH grant 3P41RR013218-12S1.
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
  # It is always recommended to provide sample data for users to make it easy to try the module,
  # but if no sample data is available then this method (and associated startupCompeted signal connection) can be removed.

  # import SampleData
  # iconsPath = os.path.join(os.path.dirname(__file__), 'Resources/Icons')

  # # To ensure that the source code repository remains small (can be downloaded and installed quickly)
  # # it is recommended to store data sets that are larger than a few MB in a Github release.

  # # Liver1
  # SampleData.SampleDataLogic.registerCustomSampleDataSource(
  #   # Category and sample name displayed in Sample Data module
  #   category='Liver',
  #   sampleName='Liver1',
  #   # Thumbnail should have size of approximately 260x280 pixels and stored in Resources/Icons folder.
  #   # It can be created by Screen Capture module, "Capture all views" option enabled, "Number of images" set to "Single".
  #   thumbnailFileName=os.path.join(iconsPath, 'Liver1.png'),
  #   # Download URL and target file name
  #   uris="https://github.com/Slicer/SlicerTestingData/releases/download/SHA256/998cb522173839c78657f4bc0ea907cea09fd04e44601f17c82ea27927937b95",
  #   fileNames='Liver1.nrrd',
  #   # Checksum to ensure file integrity. Can be computed by this command:
  #   #  import hashlib; print(hashlib.sha256(open(filename, "rb").read()).hexdigest())
  #   checksums = 'SHA256:998cb522173839c78657f4bc0ea907cea09fd04e44601f17c82ea27927937b95',
  #   # This node name will be used when the data set is loaded
  #   nodeNames='Liver1'
  # )

  # # Liver2
  # SampleData.SampleDataLogic.registerCustomSampleDataSource(
  #   # Category and sample name displayed in Sample Data module
  #   category='Liver',
  #   sampleName='Liver2',
  #   thumbnailFileName=os.path.join(iconsPath, 'Liver2.png'),
  #   # Download URL and target file name
  #   uris="https://github.com/Slicer/SlicerTestingData/releases/download/SHA256/1a64f3f422eb3d1c9b093d1a18da354b13bcf307907c66317e2463ee530b7a97",
  #   fileNames='Liver2.nrrd',
  #   checksums = 'SHA256:1a64f3f422eb3d1c9b093d1a18da354b13bcf307907c66317e2463ee530b7a97',
  #   # This node name will be used when the data set is loaded
  #   nodeNames='Liver2'
  # )
  pass

#
# LiverWidget
#

class LiverWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent=None):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.__init__(self, parent)
    VTKObservationMixin.__init__(self)  # needed for parameter node observation
    self.logic = None
    self._parameterNode = None
    self._updatingGUIFromParameterNode = False

  def setup(self):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.setup(self)

    # Load widget from .ui file (created by Qt Designer).
    # Additional widgets can be instantiated manually and added to self.layout.
    uiWidget = slicer.util.loadUI(self.resourcePath('UI/Liver.ui'))
    self.layout.addWidget(uiWidget)
    self.ui = slicer.util.childWidgetVariables(uiWidget)

    # Set scene in MRML widgets. Make sure that in Qt designer the top-level qMRMLWidget's
    # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
    # "setMRMLScene(vtkMRMLScene*)" slot.
    uiWidget.setMRMLScene(slicer.mrmlScene)

    # Create logic class. Logic implements all computations that should be possible to run
    # in batch mode, without a graphical user interface.
    self.logic = LiverLogic()

    # Connections

    # These connections ensure that we update parameter node when scene is closed
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

    # This connection listens for new node added.
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.NodeAddedEvent, self.onSceneNodeAdded)

    # These connections ensure that whenever user changes some settings on the GUI, that is saved in the MRML scene
    # (in the selected parameter node).
    self.ui.inputSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)

    # Make sure parameter node is initialized (needed for module reload)
    self.initializeParameterNode()

    # Enable the use of FXAA (antialiasing)
    renderer = slicer.app.layoutManager().threeDWidget(0).threeDView().renderWindow().GetRenderers().GetFirstRenderer()
    renderer.UseFXAAOn()

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

  def onSceneNodeAdded(self, caller, event):
    """
    Called after a node gets added to the MRML scene
    """
    markupsLineNodes = slicer.util.getNodesByClass("vtkMRMLMarkupsLineNode")
    if len(markupsLineNodes) > 0:
      self.logic.setMarkupsLineNode(markupsLineNodes[-1])

  #TODO: create onSceneNodeRemoved to remove observers of the node in case it is the node removed

  def initializeParameterNode(self):
    """
    Ensure parameter node exists and observed.
    """
    # Parameter node stores all user choices in parameter values, node selections, etc.
    # so that when the scene is saved and reloaded, these settings are restored.

    self.setParameterNode(self.logic.getParameterNode())

    # Select default input nodes if nothing is selected yet to save a few clicks for the user
    if not self._parameterNode.GetNodeReference("LiverModel"):
      firstModelNode= slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLModelNode")
      if firstModelNode:
        self._parameterNode.SetNodeReferenceID("LiverModel", firstModelNode.GetID())

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
    self.ui.inputSelector.setCurrentNode(self._parameterNode.GetNodeReference("LiverModel"))

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

    self._parameterNode.SetNodeReferenceID("LiverModel", self.ui.inputSelector.currentNodeID)

    self._parameterNode.EndModify(wasModified)

    self.logic.parameterNodeChanged(self._parameterNode)


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

  def setDefaultParameters(self, parameterNode):
    """
    Initialize parameter node with default settings.
    """
    pass

  def setMarkupsLineNode(self, markupsLineNode):
    """
    Sets the internal markups line node
    """
    self._markupsLineNode = markupsLineNode
    self._markupsLineNode.AddObserver(vtk.vtkCommand.ModifiedEvent, self.onLineNodeModified)

  @vtk.calldata_type(vtk.VTK_OBJECT)
  def onLineNodeModified(self, caller, event):
    """
    Acts on line modified
    """

    if self._markupsLineDisplayNode is None:
      self._markupsLineDisplayNode = self._markupsLineNode.GetDisplayNode()
      self._markupsLineDisplayNode.SetSnapMode(slicer.vtkMRMLMarkupsDisplayNode.SnapModeUnconstrained)

    if self._actor is not None:

      # Compute the normal of the plane
      linePoints = vtk.vtkPoints()
      self._markupsLineNode.GetControlPointPositionsWorld(linePoints)
      if linePoints.GetNumberOfPoints() == 0:
        return

      mapper = self._actor.GetMapper()
      VBOs = mapper.GetVBOs()
      vVBO = VBOs.GetVBO("vertexMC")
      scale = np.asarray(vVBO.GetScale())

      p0 = np.asarray(linePoints.GetPoint(0),dtype=float)
      p1 = np.asarray(linePoints.GetPoint(1),dtype=float)
      pm = (p0 + p1) / 2.0 * scale
      pm = np.append(pm, 1.0)
      normal = (p0 - p1) / np.linalg.norm(p0 - p1)
      normal = np.append(normal, 1.0)

      renderer = slicer.app.layoutManager().threeDWidget(0).threeDView().renderWindow().GetRenderers().GetFirstRenderer()
      camera = renderer.GetActiveCamera()

      # Get the modelview matrix
      modelView = camera.GetModelViewTransformMatrix()

      # Compute a normals matrix
      anorm = vtk.vtkMatrix4x4()
      for i in range(3):
        for j in range(3):
          anorm.SetElement(i,j,modelView.GetElement(i,j))

      fragmentUniforms = self._actor.GetShaderProperty().GetFragmentCustomUniforms()
      fragmentUniforms.SetUniform4f("planePositionMC", pm)
      fragmentUniforms.SetUniform4f("planeNormalMC", normal)


  def parameterNodeChanged(self,parameterNode):
    """
    Called when the parameter node has changed
    """

    # If the node has changed
    modelNode = parameterNode.GetNodeReference("LiverModel")
    if self._currentSelectedModelNode is not modelNode:

      lm = slicer.app.layoutManager()

      for v in range(lm.threeDViewCount):
        td = lm.threeDWidget(v)
        ms = vtk.vtkCollection()
        td.getDisplayableManagers(ms)

        for i in range(ms.GetNumberOfItems()):

          m = ms.GetItemAsObject(i)
          if m.GetClassName() == "vtkMRMLModelDisplayableManager":

            self._actor = m.GetActorByID(modelNode.GetDisplayNode().GetID())

            shaderProperty  = self._actor.GetShaderProperty()

            shaderProperty.AddVertexShaderReplacement(
              "//VTK::PositionVC::Dec",
              True,
              "//VTK::PositionVC::Dec\n"
              "out vec4 vertexMCVSOutput;\n",
              False
            )

            shaderProperty.AddVertexShaderReplacement(
              "//VTK::PositionVC::Impl",
              True,
              "//VTK::PositionVC::Impl\n"
              "vertexMCVSOutput = vertexMC;\n",
              False
            )

            shaderProperty.AddFragmentShaderReplacement(
              "//VTK::PositionVC::Dec",
              True,
              "//VTK::PositionVC::Dec\n"
              "in vec4 vertexMCVSOutput;\n"
              "vec4 fragPositionMC = vertexMCVSOutput;\n",
              False
            )

            shaderProperty.AddFragmentShaderReplacement(
              "//VTK::Color::Impl",
              True,
              "//VTK::Color::Impl\n"
              "  vec3 color1 = vec3(0.0, 1.0 ,0.0);\n"
              "  vec3 color2 = vec3(0.0, 0.0 ,1.0);\n"
              "  vec3 w = -(planePositionMC.xyz*fragPositionMC.w - fragPositionMC.xyz);\n"
              "  float dist = (planeNormalMC.x * w.x + planeNormalMC.y * w.y + planeNormalMC.z * w.z) / sqrt( pow(planeNormalMC.x,2) + pow(planeNormalMC.y,2)+ pow(planeNormalMC.z,2));\n"
              "  if(abs(dist) < 0.05){\n"
              "     ambientColor = ambientIntensity * color1;\n"
              "     diffuseColor = diffuseIntensity * color1;\n"
              "  }\n"
              "  else{\n"
              "     ambientColor = ambientIntensity * color2;\n"
              "     diffuseColor = diffuseIntensity * color2;\n"
              "  }\n" ,
              False
            )

            fragmentUniforms = self._actor.GetShaderProperty().GetFragmentCustomUniforms()
            fragmentUniforms.SetUniform4f("planePositionMC", [0.0,0,0,0.0])
            fragmentUniforms.SetUniform4f("planeNormalMC", ([1,0,0,1]/np.linalg.norm([1.0, 0.0, 0.0])).tolist())

    else:

      print("Same model")




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
    # """ Ideally you should have several levels of tests.  At the lowest level
    # tests should exercise the functionality of the logic with different inputs
    # (both valid and invalid).  At higher levels your tests should emulate the
    # way the user would interact with your code and confirm that it still works
    # the way you intended.
    # One of the most important features of the tests is that it should alert other
    # developers when their changes will have an impact on the behavior of your
    # module.  For example, if a developer removes a feature that you depend on,
    # your test should break so they know that the feature is needed.
    # """

    # self.delayDisplay("Starting the test")

    # # Get/create input data

    # import SampleData
    # registerSampleData()
    # inputVolume = SampleData.downloadSample('Liver1')
    # self.delayDisplay('Loaded test data set')

    # inputScalarRange = inputVolume.GetImageData().GetScalarRange()
    # self.assertEqual(inputScalarRange[0], 0)
    # self.assertEqual(inputScalarRange[1], 695)

    # outputVolume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode")
    # threshold = 100

    # # Test the module logic

    # logic = LiverLogic()

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

    # self.delayDisplay('Test passed')

    pass

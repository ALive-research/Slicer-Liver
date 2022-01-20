import os
import time
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging

#
# DistanceMapsSelfTest
#
class DistanceMapsSelfTest(ScriptedLoadableModule):
  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "DistanceMapsSelfTest"
    self.parent.categories = ["Testing.TestCases"]
    self.parent.dependencies = []
    self.parent.contributors = ["Rafael Palomar (OUS)"]
    self.parent.helpText = """
    This is a self-test to test the computation of distance maps
    from segmentations
    """
    self.parent.acknowledgementText = """
    This file was originally developed by Rafael Palomar (OUS) and was funded by
    the Research Council of Norway (grant nr. 311393).
    """

#
# DistanceMapsSelfTestWidget
#
class DistanceMapsSelfTestWidget(ScriptedLoadableModuleWidget):

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    # Instantiate and connect widgets ...

    # Create and configure the input segmentation node selector
    self._inputSegmentationNodeSelector = slicer.qMRMLNodeComboBox()
    self._inputSegmentationNodeSelector.nodeTypes = ["vtkMRMLSegmentationNode"]
    self._inputSegmentationNodeSelector.selectNodeUponCreation = False
    self._inputSegmentationNodeSelector.addEnabled = False
    self._inputSegmentationNodeSelector.removeEnabled = False
    self._inputSegmentationNodeSelector.noneEnabled = True
    self._inputSegmentationNodeSelector.noneDisplay = "Choose a segmentation node"
    self._inputSegmentationNodeSelector.showHidden = False
    self._inputSegmentationNodeSelector.setMRMLScene(slicer.mrmlScene)
    self._inputSegmentationNodeSelector.setToolTip("Segmentation to perform planning on.")
    self._inputSegmentationNodeSelector.connect("currentNodeChanged(vtkMRMLNode*)",
                                                self.updateParameterNodeFromGUI)

    self.layout.addWidget(self._inputSegmentationNodeSelector)

    # Create and configure the input segmentation node selector
    self._outputLabelMapNodeSelector = slicer.qMRMLNodeComboBox()
    self._outputLabelMapNodeSelector.nodeTypes = ["vtkMRMLLabelMapVolumeNode"]
    self._outputLabelMapNodeSelector.selectNodeUponCreation = True
    self._outputLabelMapNodeSelector.addEnabled = True
    self._outputLabelMapNodeSelector.removeEnabled = True
    self._outputLabelMapNodeSelector.noneEnabled = False
    self._outputLabelMapNodeSelector.noneDisplay = "vtkMRMLLabelMapVolumeNode"
    self._outputLabelMapNodeSelector.showHidden = False
    self._outputLabelMapNodeSelector.setMRMLScene(slicer.mrmlScene)
    self._outputLabelMapNodeSelector.setToolTip("Segmentation to perform planning on.")
    self._outputLabelMapNodeSelector.connect("currentNodeChanged(vtkMRMLNode*)",
                                                self.updateParameterNodeFromGUI)

    self.layout.addWidget(self._outputLabelMapNodeSelector)

    # Add vertical spacer
    self.layout.addStretch(1)

  def cleanup(self):
    pass

  def updateParameterNodeFromGUI(self):
    pass

class DistanceMapsSelfTestLogic(ScriptedLoadableModuleLogic):

  def __init__(self):
    ScriptedLoadableModuleLogic.__init__(self)

  def setUp(self):
    pass

  def test_compute_segment_distance_maps(self, segmentationNode, volumeNode, segment):

    labelNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLabelMapVolumeNode')
    segments = vtk.vtkStringArray()
    segments.InsertNextValue(segment)
    segLogic = slicer.vtkSlicerSegmentationsModuleLogic
    segLogic.ExportSegmentsToLabelmapNode(segmentationNode, segments, labelNode, volumeNode)
    import sitkUtils
    import SimpleITK as sitk
    image = sitkUtils.PullVolumeFromSlicer(labelNode)
    distance = sitk.SignedMaurerDistanceMap(image,False,False,True)
    sitkUtils.PushVolumeToSlicer(distance)



  def run(self, segmentationNode, volumeNode):

    """
    Run the tests
    """
    slicer.util.delayDisplay('Running integration tests for Pluggable Markups')

    self.test_compute_segment_distance_maps(segmentationNode, volumeNode, 'Tumor1')

    logging.info('Test process completed')


class DistanceMapsSelfTestTest(ScriptedLoadableModuleTest):
  """
  This is the test case
  """
  def setUp(self):
    slicer.mrmlScene.Clear()
    # logic = DistanceMapsSelfTestLogic()
    # logic.setUp()

  def runTest(self):
    self.setUp()
    self.test_DistanceMapsSelfTest1()

  def test_DistanceMapsSelfTest1(self):

    self.delayDisplay("Starting the Distance Map Test")

    import SampleData
    inputVolume = SampleData.downloadSample('LiverVolume000')
    inputSegmentation = SampleData.downloadSample('LiverSegmentation000')

    logic = DistanceMapsSelfTestLogic()
    logic.run(inputSegmentation, inputVolume)

    self.delayDisplay('Test passed!')

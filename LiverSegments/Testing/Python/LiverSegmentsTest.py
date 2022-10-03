
import unittest
import vtk, slicer
import LiverSegments
from LiverSegments import LiverSegmentsLogic
from LiverSegments import LiverSegmentsWidget

#Example (RVesselX): https://github.com/R-Vessel-X/SlicerRVXLiverSegmentation/blob/main/RVXLiverSegmentation/RVXLiverSegmentationTest/ExtractVesselStrategyTestCase.py
class LiverSegmentsTestCase(unittest.TestCase):

  def testLogicFunctionsWithEmptyParameters(self):
    logic = LiverSegmentsLogic()

    logic.__init__()
    logic.getCenterlineLogic()
    logic.setDefaultParameters(logic.getParameterNode())

    colormap = slicer.mrmlScene.GetNodeByID('vtkMRMLColorTableNodeLabels')
    logic.createCompleteCenterlineModel(colormap)

    centerlineModel = logic.build_centerline_model(colormap) # Fails in line 156 in vtkLiverSegmentsLogic.cxx

    refVolumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
    segmentation = self.createEmptyvtkMRMLSegmentationNode()
    logic.calculateVascularSegments(refVolume, segmentation, centerlineModel, colormap) # Require build_centerline_model to succeed first

    node1, node2 = self.create2EmptyMarkupsFiducialNodes()
    logic.copyIndex(node1, node2)

    logic.preprocessAndDecimate(vtk.vtkPolyData())
    logic.decimateLine(vtk.vtkPolyData())

  def create2EmptyMarkupsFiducialNodes(self):
    emptyNode = slicer.mrmlScene.CreateNodeByClass("vtkMRMLMarkupsFiducialNode")
    emptyNode2 = slicer.mrmlScene.CreateNodeByClass("vtkMRMLMarkupsFiducialNode")
    #Prevent memory leaks
    emptyNode.UnRegister(None)
    emptyNode2.UnRegister(None)
    return emptyNode, emptyNode2

  def createEmptyvtkMRMLSegmentationNode(self):
    emptyNode = slicer.mrmlScene.CreateNodeByClass("vtkMRMLSegmentationNode")
    emptyNode.UnRegister(None) #Prevent memory leaks
    return emptyNode


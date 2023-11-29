
import logging
import vtk, slicer
from slicer.ScriptedLoadableModule import *
#from slicer.util import TESTING_DATA_URL
import LiverSegments
from LiverSegments import LiverSegmentsLogic
from LiverSegments import LiverSegmentsWidget

class LiverSegmentsTestCase(ScriptedLoadableModuleTest):

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear(0)

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.logicFunctionsWithEmptyParameters()
    self.downloadData()

  def logicFunctionsWithEmptyParameters(self):
    logic = LiverSegmentsLogic()

    logic.__init__()
    logic.getCenterlineLogic()
    logic.setDefaultParameters(logic.getParameterNode())

    colormap = slicer.mrmlScene.GetNodeByID('vtkMRMLColorTableNodeLabels')
    logic.createCompleteCenterlineModel(colormap)
    segmentationId = 1
    centerlineModel = logic.build_centerline_model(colormap, segmentationId)

    refVolumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
    segmentation = self.createEmptyvtkMRMLSegmentationNode()
    segmentationVascular = self.createEmptyvtkMRMLSegmentationNode()
    logic.calculateVascularTerritoryMap(segmentationVascular, refVolumeNode, segmentation, centerlineModel, colormap)

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

  #Use AtlasTests.py as example
  def downloadData(self):
    aliveDataURL ='https://github.com/alive-research/aliveresearchtestingdata/releases/download/'
    downloads = {
        'fileNames': '3D-IRCADb-01_08.nrrd',
        'loadFiles': True,
        #'uris': TESTING_DATA_URL + 'SHA256/2e25b8ce2c70cc2e1acd9b3356d0b1291b770274c16fcd0e2a5b69a4587fbf74',
        'uris': aliveDataURL + 'SHA256/2e25b8ce2c70cc2e1acd9b3356d0b1291b770274c16fcd0e2a5b69a4587fbf74',
        'checksums': 'SHA256:2e25b8ce2c70cc2e1acd9b3356d0b1291b770274c16fcd0e2a5b69a4587fbf74',
    }
    #logging.info(downloads)
    import SampleData
    SampleData.downloadFromURL(**downloads)

#    volumeNode = slicer.util.getNode(pattern='Segment_1')


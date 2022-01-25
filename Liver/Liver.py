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
    Hospital/NTNU, Ole Vegard Solberg, SINTEF, Geir Arne Tangen, SINTEF and
    Javier Pérez de Frutos. This work was funded by The Research Council of
    Norway through the project ALive (grant nr. 311393).
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

  # Liver dataset
  SampleData.SampleDataLogic.registerCustomSampleDataSource(
    category='Liver',
    sampleName='LiverVolume000',
    thumbnailFileName=os.path.join(iconsPath, 'LiverVolume000.png'),
    uris='https://github.com/alive-research/aliveresearchtestingdata/releases/download/SHA256/5df79d9077b1cf2b746ff5cf9268e0bc4d440eb50fa65308b47bde094640458a',
    fileNames='LiverVolume000.nrrd',
    checksums = 'SHA256:5df79d9077b1cf2b746ff5cf9268e0bc4d440eb50fa65308b47bde094640458a',
    nodeNames='LiverVolume000',
    loadFileType='VolumeFile'
  )

  SampleData.SampleDataLogic.registerCustomSampleDataSource(
    category='Liver',
    sampleName='LiverSegmentation000',
    thumbnailFileName=os.path.join(iconsPath, 'LiverSegmentation000.png'),
    uris='https://github.com/alive-research/aliveresearchtestingdata/releases/download/SHA256/56aa9ee4658904dfae5cca514f594fa6c5b490376514358137234e22d57452a4',
    fileNames='LiverSegmentation000.seg.nrrd',
    checksums = 'SHA256:56aa9ee4658904dfae5cca514f594fa6c5b490376514358137234e22d57452a4',
    nodeNames='LiverSegmentation000',
    loadFileType='SegmentationFile'
  )

  SampleData.SampleDataLogic.registerCustomSampleDataSource(
    category='Liver',
    sampleName='DistanceMap000',
    thumbnailFileName=os.path.join(iconsPath, 'DistanceMap000.png'),
    uris='https://github.com/alive-research/aliveresearchtestingdata/releases/download/SHA256/bc003e745c357f49a54b3ac843cd03b7724c3c6b4e35c793cc450875608880f2',
    fileNames='DistanceMap000.nrrd',
    checksums = 'SHA256:bc003e745c357f49a54b3ac843cd03b7724c3c6b4e35c793cc450875608880f2',
    nodeNames='DistanceMap000',
    loadFileType='VolumeFile'
  )

#
# LiverWidget
#

class LiverWidget(ScriptedLoadableModuleWidget):

  def __init__(self, parent=None):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.__init__(self, parent)

    self.logic = None
    self._uiLoader = loader = qt.QUiLoader()

    self.distanceCollapsibleButton = None
    self.tumorLabelMapSelector = None
    self.outputVolumeLabelMapSelector = None
    self.computeDistanceMapPushButton = None

  def setup(self):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.setup(self)

    # Create logic class. Logic implements all computations that should be possible to run
    # in batch mode, without a graphical user interface.
    self.logic = LiverLogic()

    # # Enable the use of FXAA (antialiasing)
    if not slicer.app.commandOptions().noMainWindow:
      renderer = slicer.app.layoutManager().threeDWidget(0).threeDView().renderWindow().GetRenderers().GetFirstRenderer()
      renderer.UseFXAAOn()

    # Instantiate and connect widgets ...
    path = os.path.join(os.path.dirname(__file__), 'Resources', 'UI','qSlicerDistanceMapsComputationWidget.ui')
    qfile = qt.QFile(path)
    qfile.open(qt.QFile.ReadOnly)
    distanceMapsWidget = self._uiLoader.load(qfile)

    # Distance Maps Group
    self.distanceCollapsibleButton = slicer.util.findChild(widget=distanceMapsWidget, name='DistanceMapsCollapsibleButton')
    self.tumorLabelMapSelector = slicer.util.findChild(widget=self.distanceCollapsibleButton, name='TumorLabelMapComboBox')
    self.tumorLabelMapSelector.setMRMLScene(slicer.mrmlScene)
    self.outputVolumeLabelMapSelector = slicer.util.findChild(widget=self.distanceCollapsibleButton, name='OutputVolumeComboBox')
    self.outputVolumeLabelMapSelector.setMRMLScene(slicer.mrmlScene)
    self.computeDistanceMapPushButton = slicer.util.findChild(widget=self.distanceCollapsibleButton, name='ComputeDistanceMapsPushButton')
    self.computeDistanceMapPushButton.connect('clicked()', self.computeDistanceMapPushButtonClicked)

    self.layout.addWidget(distanceMapsWidget)

    spacerItem = qt.QSpacerItem(0,0, qt.QSizePolicy.Minimum, qt.QSizePolicy.MinimumExpanding)
    self.layout.addSpacerItem(spacerItem)

  def computeDistanceMapPushButtonClicked(self):

    tumorLabelMapNode = self.tumorLabelMapSelector.currentNode()
    outputVolumeNode = self.outputVolumeLabelMapSelector.currentNode()

    self.logic.computeDistanceMaps(tumorLabelMapNode, outputVolumeNode)


  def cleanup(self):
    """
    Called when the application closes and the module widget is destroyed.
    """
    pass

  def enter(self):
    """
    Called each time the user opens this module.
    """
    pass

  def exit(self):
    """
    Called each time the user opens a different module.
    """

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

  def computeDistanceMaps(self, tumorNode, outputNode):

    import sitkUtils
    import SimpleITK as sitk
    image = sitkUtils.PullVolumeFromSlicer(tumorNode)
    distance = sitk.SignedMaurerDistanceMap(image,False,False,True)
    logging.debug("Computing Distance Map...")
    sitkUtils.PushVolumeToSlicer(distance, targetNode = outputNode)

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

    self.delayDisplay("Starting distance map computation test")

    liverWidget= slicer.modules.liver.widgetRepresentation()
    distanceCollapsibleButton = slicer.util.findChild(widget=liverWidget, name='DistanceMapsCollapsibleButton')
    tumorLabelMapSelector = slicer.util.findChild(widget=distanceCollapsibleButton, name='TumorLabelMapComboBox')
    outputVolumeLabelMapSelector = slicer.util.findChild(widget=distanceCollapsibleButton, name='OutputVolumeComboBox')
    computeDistanceMapPushButton = slicer.util.findChild(widget=distanceCollapsibleButton, name='ComputeDistanceMapsPushButton')

    self.delayDisplay("Extracting tumor labelmap from segmentation")

    import vtkSegmentationCore as segCore

    labelNode = slicer.vtkMRMLLabelMapVolumeNode()
    slicer.mrmlScene.AddNode(labelNode)
    labelNode.CreateDefaultDisplayNodes()
    outputVolume = slicer.vtkMRMLScalarVolumeNode()
    slicer.mrmlScene.AddNode(outputVolume)
    outputVolume.CreateDefaultDisplayNodes()
    volumeNode = slicer.util.getNode('LiverVolume000')

    segmentationNode = slicer.util.getNode('LiverSegmentation000')
    segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(volumeNode)
    segmentationNode.CreateBinaryLabelmapRepresentation()
    segments = vtk.vtkStringArray()
    segments.InsertNextValue("Tumor1")
    segLogic = slicer.vtkSlicerSegmentationsModuleLogic
    segLogic.ExportSegmentsToLabelmapNode(segmentationNode, segments, labelNode, volumeNode,
                                          segCore.vtkSegmentation.EXTENT_UNION_OF_EFFECTIVE_SEGMENTS_AND_REFERENCE_GEOMETRY)

    self.delayDisplay("Computing distance map")

    tumorLabelMapSelector.setCurrentNode(labelNode)
    outputVolumeLabelMapSelector.setCurrentNode(outputVolume)
    computeDistanceMapPushButton.click()

    self.delayDisplay("Testing difference with groundtruth image")

    import sitkUtils
    import SimpleITK as sitk
    groundTruthVolume = slicer.util.getNode('DistanceMap000')
    groundTruthImage = sitkUtils.PullVolumeFromSlicer(groundTruthVolume)
    distanceMapImage = sitkUtils.PullVolumeFromSlicer(outputVolume)
    differenceImage = sitk.Subtract(groundTruthImage, distanceMapImage)
    statisticsFilter = sitk.StatisticsImageFilter()
    statisticsFilter.Execute(differenceImage)

    self.assertEqual(statisticsFilter.GetMaximum(), 0)
    self.assertEqual(statisticsFilter.GetMaximum(), 0)
    self.assertEqual(statisticsFilter.GetMean(), 0)

    self.delayDisplay("Test passed!")

  def setUp(self):

    slicer.mrmlScene.Clear()

    # Get/create input data
    import SampleData
    registerSampleData()
    inputSegmentation = SampleData.downloadSample('LiverSegmentation000')
    inputVolume= SampleData.downloadSample('LiverVolume000')
    distanceMap = SampleData.downloadSample('DistanceMap000')
    self.delayDisplay('Loaded test data set')

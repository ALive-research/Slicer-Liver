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
#   This file was originally developed by Rafael Palomar (Oslo University
#   Hospital and NTNU) and was supported by The Research Council of Norway
#   through the ALive project (grant nr. 311393).
#
# ==============================================================================

import os
import unittest
import logging
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import numpy as np
import LiverSegments

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
    This module offers tools for computing liver resection plans in 3D liver models.
    ""
    This file was originally developed by Rafael Palomar (Oslo University
    Hospital/NTNU), Ole Vegard Solberg (SINTEF) Geir Arne Tangen, SINTEF and
    Javier Pérez de Frutos (SINTEF). This work was funded by The Research Council of
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

  aliveDataURL ='https://github.com/alive-research/aliveresearchtestingdata/releases/download/'

  # Liver dataset
  SampleData.SampleDataLogic.registerCustomSampleDataSource(
    category ='Liver',
    sampleName ='LiverVolume000',
    thumbnailFileName = os.path.join(iconsPath, 'LiverVolume000.png'),
    uris = aliveDataURL+'SHA256/5df79d9077b1cf2b746ff5cf9268e0bc4d440eb50fa65308b47bde094640458a',
    fileNames ='LiverVolume000.nrrd',
    checksums = 'SHA256:5df79d9077b1cf2b746ff5cf9268e0bc4d440eb50fa65308b47bde094640458a',
    nodeNames ='LiverVolume000',
    loadFileType ='VolumeFile'
  )

  SampleData.SampleDataLogic.registerCustomSampleDataSource(
    category ='Liver',
    sampleName ='LiverSegmentation000',
    thumbnailFileName = os.path.join(iconsPath, 'LiverSegmentation000.png'),
    uris = aliveDataURL+'SHA256/56aa9ee4658904dfae5cca514f594fa6c5b490376514358137234e22d57452a4',
    fileNames ='LiverSegmentation000.seg.nrrd',
    checksums = 'SHA256:56aa9ee4658904dfae5cca514f594fa6c5b490376514358137234e22d57452a4',
    nodeNames ='LiverSegmentation000',
    loadFileType = 'SegmentationFile'
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
    self._currentResectionNode = None

  def setup(self):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.setup(self)

    distanceMapsUI = slicer.util.loadUI(self.resourcePath('UI/DistanceMapsWidget.ui'))
    distanceMapsUI.setMRMLScene(slicer.mrmlScene)
    resectionsUI= slicer.util.loadUI(self.resourcePath('UI/ResectionsWidget.ui'))
    resectionsUI.setMRMLScene(slicer.mrmlScene)

    self.layout.addWidget(distanceMapsUI)
    self.layout.addWidget(resectionsUI)

    self.distanceMapsWidget = slicer.util.childWidgetVariables(distanceMapsUI)
    self.resectionsWidget = slicer.util.childWidgetVariables(resectionsUI)

    # Add LiverSegmentsWidget
    wrapperWidget = slicer.qMRMLWidget()
    wrapperWidget.setLayout(qt.QVBoxLayout())
    wrapperWidget.setMRMLScene(slicer.mrmlScene)
    segemtsWidget = LiverSegments.LiverSegmentsWidget(wrapperWidget)
    segemtsWidget.setup()
    self.layout.addWidget(wrapperWidget)

    # Add a spacer at the botton to keep the UI flowing from top to bottom
    spacerItem = qt.QSpacerItem(0,0, qt.QSizePolicy.Minimum, qt.QSizePolicy.MinimumExpanding)
    self.layout.addSpacerItem(spacerItem)

    # Create logic class. Logic implements all computations that should be possible to run
    # in batch mode, without a graphical user interface.
    self.logic = LiverLogic()

    # # Enable the use of FXAA (antialiasing)
    if not slicer.app.commandOptions().noMainWindow:
      renderer = slicer.app.layoutManager().threeDWidget(0).threeDView().renderWindow().GetRenderers().GetFirstRenderer()
      renderer.UseFXAAOn()

    # Configure uncertainty margin combo box
    self.resectionsWidget.UncertaintyMarginComboBox.addItems(['Custom', 'Max. Spacing', 'RMS Spacing'])

    # Connections
    self.distanceMapsWidget.TumorLabelMapComboBox.connect('currentNodeChanged(vtkMRMLNode*)', self.onDistanceMapParameterChanged)
    self.distanceMapsWidget.ParenchymaLabelMapNodeComboBox.connect('currentNodeChanged(vtkMRMLNode*)', self.onDistanceMapParameterChanged)
    self.distanceMapsWidget.ParenchymaLabelMapNodeComboBox.addAttribute('vtkMRMLScalarVolumeNode', 'DistanceMap', 'True')
    self.distanceMapsWidget.OutputDistanceMapNodeComboBox.connect('currentNodeChanged(vtkMRMLNode*)', self.onDistanceMapParameterChanged)
    self.distanceMapsWidget.OutputDistanceMapNodeComboBox.addAttribute('vtkMRMLScalarVolumeNode', 'DistanceMap', 'True')
    self.distanceMapsWidget.ComputeDistanceMapsPushButton.connect('clicked(bool)', self.onComputeDistanceMapButtonClicked)
    self.resectionsWidget.ResectionNodeComboBox.connect('currentNodeChanged(vtkMRMLNode*)', self.onResectionNodeChanged)
    self.resectionsWidget.DistanceMapNodeComboBox.connect('currentNodeChanged(vtkMRMLNode*)', self.onResectionDistanceMapNodeChanged)
    self.resectionsWidget.DistanceMapNodeComboBox.addAttribute('vtkMRMLScalarVolumeNode', 'DistanceMap', 'True')
    self.resectionsWidget.DistanceMapNodeComboBox.addAttribute('vtkMRMLScalarVolumeNode', 'Computed', 'True')
    self.resectionsWidget.LiverModelNodeComboBox.connect('currentNodeChanged(vtkMRMLNode*)', self.onResectionLiverModelNodeChanged)
    self.resectionsWidget.ResectionColorPickerButton.connect('colorChanged(QColor)', self.onResectionColorChanged)
    self.resectionsWidget.ResectionOpacityDoubleSlider.connect('valueChanged(double)', self.onResectionOpacityChanged)
    self.resectionsWidget.ResectionOpacityDoubleSpinBox.connect('valueChanged(double)', self.onResectionOpacityChanged)
    self.resectionsWidget.ResectionMarginSpinBox.connect('valueChanged(double)', self.onResectionMarginChanged)
    self.resectionsWidget.ResectionMarginColorPickerButton.connect('colorChanged(QColor)', self.onResectionMarginColorChanged)
    self.resectionsWidget.ResectionGridColorPickerButton.connect('colorChanged(QColor)', self.onResectionGridColorChanged)
    self.resectionsWidget.GridDivisionsDoubleSlider.connect('valueChanged(double)', self.onGridDivisionsChanged)
    self.resectionsWidget.GridThicknessDoubleSlider.connect('valueChanged(double)', self.onGridThicknessChanged)
    self.resectionsWidget.ResectionLockCheckBox.connect('stateChanged(int)', self.onResectionLockChanged)
    self.resectionsWidget.UncertaintyMarginSpinBox.connect('valueChanged(double)', self.onUncertaintyMarginChanged)
    self.resectionsWidget.UncertaintyMarginColorPickerButton.connect('colorChanged(QColor)', self.onUncertaintyMarginColorChanged)
    self.resectionsWidget.UncertaintyMarginComboBox.connect('currentIndexChanged(int)', self.onUncertaintyMaginComboBoxChanged)
    self.resectionsWidget.InterpolatedMarginsCheckBox.connect('stateChanged(int)', self.onInterpolatedMarginsChanged)

  def onDistanceMapParameterChanged(self):
    """
    This function is triggered whenever any parameter of the distance maps are changed
    """
    node1 = self.distanceMapsWidget.TumorLabelMapComboBox.currentNode()
    node2 = self.distanceMapsWidget.ParenchymaLabelMapNodeComboBox.currentNode()
    node3 = self.distanceMapsWidget.OutputDistanceMapNodeComboBox.currentNode()
    self.distanceMapsWidget.ComputeDistanceMapsPushButton.setEnabled(None not in [node1, node2, node3])

  def onResectionNodeChanged(self):
    """
    This function is triggered when the resectio node combo box changes. It
    adjust the rest of the UI according to the parameters contained in the node.
    """
    activeResectionNode = self.resectionsWidget.ResectionNodeComboBox.currentNode()

    # If there is an effective change of resection, update other widgets with resection parameters
    if activeResectionNode is not self._currentResectionNode:

      self.resectionsWidget.ResectionParametersGroupBox.setEnabled(activeResectionNode is not None)

      lvLogic = slicer.modules.liverresections.logic()

      if activeResectionNode is not None:

        self.resectionsWidget.LiverModelNodeComboBox.blockSignals(True)
        self.resectionsWidget.LiverModelNodeComboBox.setCurrentNode(activeResectionNode.GetTargetOrganModelNode())
        self.resectionsWidget.LiverModelNodeComboBox.blockSignals(False)

        self.resectionsWidget.DistanceMapNodeComboBox.blockSignals(True)
        self.resectionsWidget.DistanceMapNodeComboBox.setCurrentNode(activeResectionNode.GetDistanceMapVolumeNode())
        self.resectionsWidget.DistanceMapNodeComboBox.blockSignals(False)

        self.resectionsWidget.ResectionColorPickerButton.blockSignals(True)
        color = activeResectionNode.GetResectionColor()
        self.resectionsWidget.ResectionColorPickerButton.setColor(qt.QColor.fromRgbF(color[0], color[1], color[2]))
        self.resectionsWidget.ResectionColorPickerButton.blockSignals(False)

        self.resectionsWidget.ResectionMarginSpinBox.blockSignals(True)
        self.resectionsWidget.ResectionMarginSpinBox.setValue(activeResectionNode.GetResectionMargin())
        self.resectionsWidget.ResectionMarginSpinBox.minimum = activeResectionNode.GetUncertaintyMargin()
        self.resectionsWidget.ResectionMarginSpinBox.blockSignals(False)

        self.resectionsWidget.ResectionMarginColorPickerButton.blockSignals(True)
        color = activeResectionNode.GetResectionMarginColor()
        self.resectionsWidget.ResectionMarginColorPickerButton.setColor(qt.QColor.fromRgbF(color[0], color[1], color[2]))
        self.resectionsWidget.ResectionMarginColorPickerButton.blockSignals(False)

        self.resectionsWidget.ResectionOpacityDoubleSlider.blockSignals(True)
        self.resectionsWidget.ResectionOpacityDoubleSlider.setValue(activeResectionNode.GetResectionOpacity())
        self.resectionsWidget.ResectionOpacityDoubleSlider.blockSignals(False)

        self.resectionsWidget.ResectionOpacityDoubleSpinBox.blockSignals(True)
        self.resectionsWidget.ResectionOpacityDoubleSpinBox.setValue(activeResectionNode.GetResectionOpacity())
        self.resectionsWidget.ResectionOpacityDoubleSpinBox.blockSignals(False)

        self.resectionsWidget.ResectionGridColorPickerButton.blockSignals(True)
        color = activeResectionNode.GetResectionGridColor()
        self.resectionsWidget.ResectionGridColorPickerButton.setColor(qt.QColor.fromRgbF(color[0], color[1], color[2]))
        self.resectionsWidget.ResectionGridColorPickerButton.blockSignals(False)

        self.resectionsWidget.ResectionLockCheckBox.blockSignals(True)
        if (activeResectionNode.GetWidgetVisibility()):
          self.resectionsWidget.ResectionLockCheckBox.setCheckState(0)
        else:
          self.resectionsWidget.ResectionLockCheckBox.setCheckState(2)
        self.resectionsWidget.ResectionLockCheckBox.blockSignals(False)

        self.resectionsWidget.UncertaintyMarginSpinBox.blockSignals(True)
        self.resectionsWidget.UncertaintyMarginSpinBox.setValue(activeResectionNode.GetUncertaintyMargin())
        self.resectionsWidget.UncertaintyMarginSpinBox.blockSignals(False)

        self.resectionsWidget.UncertaintyMarginColorPickerButton.blockSignals(True)
        color = activeResectionNode.GetUncertaintyMarginColor()
        self.resectionsWidget.UncertaintyMarginColorPickerButton.setColor(qt.QColor.fromRgbF(color[0], color[1], color[2]))
        self.resectionsWidget.UncertaintyMarginColorPickerButton.blockSignals(False)

        self.resectionsWidget.ResectionLockCheckBox.blockSignals(True)
        if activeResectionNode.GetWidgetVisibility():
          self.resectionsWidget.ResectionLockCheckBox.setCheckState(0) # Unchecked
        else:
          self.resectionsWidget.ResectionLockCheckBox.setCheckState(2) # Checked
        self.resectionsWidget.ResectionLockCheckBox.blockSignals(False)

        self.resectionsWidget.InterpolatedMarginsCheckBox.blockSignals(True)
        if activeResectionNode.GetInterpolatedMargins():
          self.resectionsWidget.InterpolatedMarginsCheckBox.setCheckState(2) # Checked
        else:
          self.resectionsWidget.InterpolatedMarginsCheckBox.setCheckState(0) # Unchecked
        self.resectionsWidget.InterpolatedMarginsCheckBox.blockSignals(False)

        if activeResectionNode.GetState()  == activeResectionNode.Initialization: # Show initialization
          lvLogic.HideBezierSurfaceMarkupFromResection(self._currentResectionNode)
          lvLogic.HideInitializationMarkupFromResection(self._currentResectionNode)
          lvLogic.ShowInitializationMarkupFromResection(activeResectionNode)
          lvLogic.ShowBezierSurfaceMarkupFromResection(activeResectionNode)

        elif activeResectionNode.GetState() == activeResectionNode.Deformation: # Show bezier surface
          lvLogic.HideInitializationMarkupFromResection(self._currentResectionNode)
          lvLogic.HideBezierSurfaceMarkupFromResection(self._currentResectionNode)
          lvLogic.ShowBezierSurfaceMarkupFromResection(activeResectionNode)
      else:
          lvLogic.HideBezierSurfaceMarkupFromResection(self._currentResectionNode)
          lvLogic.HideInitializationMarkupFromResection(self._currentResectionNode)

    self._currentResectionNode = activeResectionNode

  def onResectionDistanceMapNodeChanged(self):
    """
    This function is called when the resection distance map selector changes
    """
    if self._currentResectionNode is not None:

      distanceMapNode = self.resectionsWidget.DistanceMapNodeComboBox.currentNode()
      self._currentResectionNode.SetDistanceMapVolumeNode(self.resectionsWidget.DistanceMapNodeComboBox.currentNode())
      self.resectionsWidget.ResectionMarginGroupBox.setEnabled(distanceMapNode is not None)
      self.resectionsWidget.UncertaintyMarginGroupBox.setEnabled(distanceMapNode is not None)
      self.resectionsWidget.ResectionPreviewGroupBox.setEnabled(distanceMapNode is not None)

  def onResectionLiverModelNodeChanged(self):
    """
    This function is called when the resection liver model node changes
    """
    if self._currentResectionNode is not None:
      modelNode = self.resectionsWidget.LiverModelNodeComboBox.currentNode()
      self._currentResectionNode.SetTargetOrganModelNode(modelNode)
      self.resectionsWidget.ResectionVisualizationGroupBox.setEnabled(modelNode is not None)
      self.resectionsWidget.GridGroupBox.setEnabled(modelNode is not None)

  def onResectionMarginChanged(self):
    """
    This function is called when the resection margin spinbox changes.
    """
    if self._currentResectionNode is not None:
      self._currentResectionNode.SetResectionMargin(self.resectionsWidget.ResectionMarginSpinBox.value)
      self.updateTotalMargin()

  def onUncertaintyMarginChanged(self):
    """
    This function is called when the resection margin spinbox changes.
    """
    if self._currentResectionNode is not None:
      self._currentResectionNode.SetUncertaintyMargin(self.resectionsWidget.UncertaintyMarginSpinBox.value)
      self.resectionsWidget.ResectionMarginSpinBox.minimum = self._currentResectionNode.GetUncertaintyMargin()
      self.updateTotalMargin()

  def updateTotalMargin(self):
    uncertainty = self._currentResectionNode.GetUncertaintyMargin()
    resection = self._currentResectionNode.GetResectionMargin()
    self.resectionsWidget.TotalMarginLabel.setText('{:.2f} mm'.format(resection+uncertainty))

  def onResectionLockChanged(self):
    """
    This function is called when the resection margin spinbox changes.
    """
    if self._currentResectionNode is not None:
      self._currentResectionNode.SetClipOut(self.resectionsWidget.ResectionLockCheckBox.isChecked())
      self._currentResectionNode.SetWidgetVisibility(not self.resectionsWidget.ResectionLockCheckBox.isChecked())

  def onComputeDistanceMapButtonClicked(self):
    """
    This function is called when the distance map calculation button is pressed
    """
    tumorLabelMapNode = self.distanceMapsWidget.TumorLabelMapComboBox.currentNode()
    parenchymaLabelMapNode = self.distanceMapsWidget.ParenchymaLabelMapNodeComboBox.currentNode()
    outputVolumeNode = self.distanceMapsWidget.OutputDistanceMapNodeComboBox.currentNode()

    slicer.app.pauseRender()
    qt.QApplication.setOverrideCursor(qt.Qt.WaitCursor)
    self.logic.computeDistanceMaps(tumorLabelMapNode, parenchymaLabelMapNode, outputVolumeNode)
    slicer.app.resumeRender()
    qt.QApplication.restoreOverrideCursor()
    slicer.util.showStatusMessage('')

  def onUncertaintyMaginComboBoxChanged(self):
    """
    This function is called whenever the uncertainty combo box is changed
    """
    uncertaintyMode = self.resectionsWidget.UncertaintyMarginComboBox.currentText
    self.resectionsWidget.UncertaintyMarginSpinBox.setEnabled(uncertaintyMode == 'Custom')
    distanceMap = self.resectionsWidget.DistanceMapNodeComboBox.currentNode()

    if uncertaintyMode == 'Max. Spacing':
      if distanceMap is not None:
        maxSpacing = max(distanceMap.GetSpacing())
        self.resectionsWidget.UncertaintyMarginSpinBox.setValue(maxSpacing)

    if uncertaintyMode == 'RMS Spacing':
      if distanceMap is not None:
        rmsSpacing = np.sqrt(np.mean(np.square(distanceMap.GetSpacing())))
        self.resectionsWidget.UncertaintyMarginSpinBox.setValue(rmsSpacing)

  def onInterpolatedMarginsChanged(self):
    """
    This function is called whenever the interpolated contour has changed
    """
    if self._currentResectionNode is not None:
      self._currentResectionNode.SetInterpolatedMargins(self.resectionsWidget.InterpolatedMarginsCheckBox.isChecked())

  def onResectionColorChanged(self):
    """
    This function is called whenever the resection margin color has changed
    """
    if self._currentResectionNode is not None:
      color = self.resectionsWidget.ResectionColorPickerButton.color
      rgbF = [color.redF(),color.greenF(),color.blueF()]
      self._currentResectionNode.SetResectionColor(rgbF)

  def onResectionGridColorChanged(self):
    """
    This function is called whenever the  grid color has changed
    """
    if self._currentResectionNode is not None:
      color = self.resectionsWidget.ResectionGridColorPickerButton.color
      rgbF = [color.redF(),color.greenF(),color.blueF()]
      self._currentResectionNode.SetResectionGridColor(rgbF)

  def onResectionOpacityChanged(self):
    """
    This function is called whenever the resection opacity has changed
    """
    if self._currentResectionNode is not None:
      self._currentResectionNode.SetResectionOpacity(self.resectionsWidget.ResectionOpacityDoubleSpinBox.value)

  def onResectionMarginColorChanged(self):
    """
    This function is called whenever the resection margin color has changed
    """
    if self._currentResectionNode is not None:
      color = self.resectionsWidget.ResectionMarginColorPickerButton.color
      rgbF = [color.redF(),color.greenF(),color.blueF()]
      self._currentResectionNode.SetResectionMarginColor(rgbF)

  def onUncertaintyMarginColorChanged(self):
    """
    This function is called whenever the resection margin color has changed
    """
    if self._currentResectionNode is not None:
      color = self.resectionsWidget.UncertaintyMarginColorPickerButton.color
      rgbF = [color.redF(),color.greenF(),color.blueF()]
      self._currentResectionNode.SetUncertaintyMarginColor(rgbF)

  def onGridDivisionsChanged(self):
    """
    This function is called whenever the resection grid divisions has changed
    """
    if self._currentResectionNode is not None:
      self._currentResectionNode.SetGridDivisions(self.resectionsWidget.GridDivisionsDoubleSlider.value)

  def onGridThicknessChanged(self):
    """
    This function is called whenever the resection grid thickness has changed
    """
    if self._currentResectionNode is not None:
      self._currentResectionNode.SetGridThickness(self.resectionsWidget.GridThicknessDoubleSlider.value)

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
    pass

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

  def computeDistanceMaps(self, tumorNode, parenchymaNode, outputNode):

    if outputNode is not None:
      import sitkUtils
      import SimpleITK as sitk

      # Compute tumor distance map
      tumorImage = sitkUtils.PullVolumeFromSlicer(tumorNode)
      tumorDistanceImage = sitk.SignedMaurerDistanceMap(tumorImage,False,False,True)
      logging.debug("Computing Tumor Distance Map...")

      # Compute tumor distance map
      parenchymaImage = sitkUtils.PullVolumeFromSlicer(parenchymaNode)
      parenchymaDistanceImage = sitk.SignedMaurerDistanceMap(parenchymaImage,False,False,True)
      logging.debug("Computing Parenchyma Distance Map...")

      #Combine distance maps
      compositeDistanceMap = sitk.Compose(tumorDistanceImage,parenchymaDistanceImage)
      sitkUtils.PushVolumeToSlicer(compositeDistanceMap, targetNode = outputNode, className='vtkMRMLVectorVolumeNode')
      outputNode.SetAttribute('DistanceMap', "True");
      outputNode.SetAttribute('Computed', "True");

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

    pass
    # self.delayDisplay("Starting distance map computation test")

    # liverWidget= slicer.modules.liver.widgetRepresentation()
    # distanceCollapsibleButton = slicer.util.findChild(widget=liverWidget, name='DistanceMapsCollapsibleButton')
    # tumorLabelMapSelector = slicer.util.findChild(widget=distanceCollapsibleButton, name='TumorLabelMapComboBox')
    # outputDistanceMapSelector = slicer.util.findChild(widget=distanceCollapsibleButton, name='OutputVolumeComboBox')
    # computeDistanceMapPushButton = slicer.util.findChild(widget=distanceCollapsibleButton, name='ComputeDistanceMapsPushButton')

    # self.delayDisplay("Extracting tumor labelmap from segmentation")

    # import vtkSegmentationCore as segCore

    # labelNode = slicer.vtkMRMLLabelMapVolumeNode()
    # slicer.mrmlScene.AddNode(labelNode)
    # labelNode.CreateDefaultDisplayNodes()
    # outputVolume = slicer.vtkMRMLScalarVolumeNode()
    # slicer.mrmlScene.AddNode(outputVolume)
    # outputVolume.CreateDefaultDisplayNodes()
    # outputVolume.SetAttribute("DistanceMap", "True");
    # volumeNode = slicer.util.getNode('LiverVolume000')

    # segmentationNode = slicer.util.getNode('LiverSegmentation000')
    # segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(volumeNode)
    # segmentationNode.CreateBinaryLabelmapRepresentation()
    # segments = vtk.vtkStringArray()
    # segments.InsertNextValue("Tumor1")
    # segLogic = slicer.vtkSlicerSegmentationsModuleLogic
    # segLogic.ExportSegmentsToLabelmapNode(segmentationNode, segments, labelNode, volumeNode,
    #                                       segCore.vtkSegmentation.EXTENT_UNION_OF_EFFECTIVE_SEGMENTS_AND_REFERENCE_GEOMETRY)

    # self.delayDisplay("Computing distance map")

    # tumorLabelMapSelector.setCurrentNode(labelNode)
    # outputDistanceMapSelector.setCurrentNode(outputVolume)
    # computeDistanceMapPushButton.click()

    # self.delayDisplay("Testing difference with groundtruth image")

    # import sitkUtils
    # import SimpleITK as sitk
    # groundTruthVolume = slicer.util.getNode('DistanceMap000')
    # groundTruthImage = sitkUtils.PullVolumeFromSlicer(groundTruthVolume)
    # distanceMapImage = sitkUtils.PullVolumeFromSlicer(outputVolume)
    # differenceImage = sitk.Subtract(groundTruthImage, distanceMapImage)
    # statisticsFilter = sitk.StatisticsImageFilter()
    # statisticsFilter.Execute(differenceImage)

    # self.assertEqual(statisticsFilter.GetMaximum(), 0)
    # self.assertEqual(statisticsFilter.GetMaximum(), 0)
    # self.assertEqual(statisticsFilter.GetMean(), 0)

    self.delayDisplay("Test passed!")

  def setUp(self):

    slicer.mrmlScene.Clear()

    # Get/create input data
    import SampleData
    registerSampleData()
    inputSegmentation = SampleData.downloadSample('LiverSegmentation000')
    inputVolume= SampleData.downloadSample('LiverVolume000')
    self.delayDisplay('Loaded test data set')

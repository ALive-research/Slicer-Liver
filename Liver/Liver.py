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
#   Hospital and NTNU) and Ruoyan Meng (NTNU), and was supported by The
#   Research Council of Norway through the ALive project (grant nr. 311393).
#
# ==============================================================================

import os
import unittest
import logging
import vtk, qt, ctk, slicer
from vtk.util.numpy_support import vtk_to_numpy, numpy_to_vtk
from slicer.ScriptedLoadableModule import *
import numpy as np
from numpy import size
import LiverSegments
import LiverVolumetry

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

    self.parent.categories = ["IGT"]

    self.parent.dependencies = ["LiverResections", "LiverMarkups", "LiverSegments"]

    self.parent.contributors = ["Rafael Palomar (Oslo University Hospital / NTNU)",
                                "Ole Vegard Solberg (SINTEF)",
                                "Geir Arne Tangen (SINTEF)",
                                "Egidijus Pelanis (Oslo University Hospital)",
                                "Davit Aghayan (Oslo University Hospital)",
                                "Gabriella D'Albenzio (Oslo University Hospital)",
                                "Ruoyan Meng (NTNU)",
                                "Javier Pérez-de-Frutos (SINTEF)",
                                "Héctor Mártinez (Universidad de Córdoba)",
                                "Francisco Javier Rodríguez Lozano (Universidad de Córdoba)",
                                "Joaquín Olivares Bueno (Universidad de Córdoba)",
                                "José Manuel Palomares Muñoz (Universidad de Córdoba)"]

    self.parent.acknowledgementText = """
    This work was funded by The Research Council of
    Norway through the project ALive (grant nr. 311393).
    """
    self.parent.helpText = """
    This module offers tools for liver perfusion analysis and resection planning.
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

  aliveDataURL = 'https://github.com/alive-research/aliveresearchtestingdata/releases/download/'

  # Liver dataset
  SampleData.SampleDataLogic.registerCustomSampleDataSource(
    category='Liver',
    sampleName='LiverVolume000',
    thumbnailFileName=os.path.join(iconsPath, 'LiverVolume000.png'),
    uris=aliveDataURL + 'SHA256/5df79d9077b1cf2b746ff5cf9268e0bc4d440eb50fa65308b47bde094640458a',
    fileNames='LiverVolume000.nrrd',
    checksums='SHA256:5df79d9077b1cf2b746ff5cf9268e0bc4d440eb50fa65308b47bde094640458a',
    nodeNames='LiverVolume000',
    loadFileType='VolumeFile'
  )

  SampleData.SampleDataLogic.registerCustomSampleDataSource(
    category='Liver',
    sampleName='LiverSegmentation000',
    thumbnailFileName=os.path.join(iconsPath, 'LiverSegmentation000.png'),
    uris=aliveDataURL + 'SHA256/56aa9ee4658904dfae5cca514f594fa6c5b490376514358137234e22d57452a4',
    fileNames='LiverSegmentation000.seg.nrrd',
    checksums='SHA256:56aa9ee4658904dfae5cca514f594fa6c5b490376514358137234e22d57452a4',
    nodeNames='LiverSegmentation000',
    loadFileType='SegmentationFile'
  )

  SampleData.SampleDataLogic.registerCustomSampleDataSource(
    category='Liver',
    sampleName='LiverSegments000',
    thumbnailFileName=os.path.join(iconsPath, 'LiverSegments000.png'),
    uris=aliveDataURL + 'SHA256/101d3903a8b27eb2e7ee3ceb8ddd15f288aeb69960a1606db64d5ae3180e251b',
    fileNames='LiverSegments000.seg.nrrd',
    checksums='SHA256:101d3903a8b27eb2e7ee3ceb8ddd15f288aeb69960a1606db64d5ae3180e251b',
    nodeNames='LiverSements000',
    loadFileType='SegmentationFile'
  )

  #if developerMode is True:
  SampleData.SampleDataLogic.registerCustomSampleDataSource(
    category ='Development',
    sampleName ='3D-IRCADb-01_08',
    thumbnailFileName = os.path.join(iconsPath, 'LiverSegmentation000.png'),
    uris = aliveDataURL+'SHA256/2e25b8ce2c70cc2e1acd9b3356d0b1291b770274c16fcd0e2a5b69a4587fbf74',
    fileNames ='3D-IRCADb-01_08.nrrd',
    checksums = 'SHA256:2e25b8ce2c70cc2e1acd9b3356d0b1291b770274c16fcd0e2a5b69a4587fbf74',
    nodeNames ='3D-IRCADb-01_08',
    loadFileType = 'SegmentationFile'
  )

  #if developerMode is True:
  SampleData.SampleDataLogic.registerCustomSampleDataSource(
    category ='Development',
    sampleName ='3D-IRCADb-01_08',
    thumbnailFileName = os.path.join(iconsPath, 'LiverSegmentation000.png'),
    uris = aliveDataURL+'SHA256/2e25b8ce2c70cc2e1acd9b3356d0b1291b770274c16fcd0e2a5b69a4587fbf74',
    fileNames ='3D-IRCADb-01_08.nrrd',
    checksums = 'SHA256:2e25b8ce2c70cc2e1acd9b3356d0b1291b770274c16fcd0e2a5b69a4587fbf74',
    nodeNames ='3D-IRCADb-01_08',
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
    self.numComps = 0
    self._distanceContourNode = None
    self._preprocessedLiverNode = None

  def setup(self):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.setup(self)

    distanceMapsUI = slicer.util.loadUI(self.resourcePath('UI/DistanceMapsWidget.ui'))
    distanceMapsUI.setMRMLScene(slicer.mrmlScene)
    resectionsUI = slicer.util.loadUI(self.resourcePath('UI/ResectionsWidget.ui'))
    resectionsUI.setMRMLScene(slicer.mrmlScene)
    resectogramUI = slicer.util.loadUI(self.resourcePath('UI/ResectogramWidget.ui'))
    resectogramUI.setMRMLScene(slicer.mrmlScene)

    self.layout.addWidget(distanceMapsUI)
    self.layout.addWidget(resectionsUI)
    self.layout.addWidget(resectogramUI)

    self.distanceMapsWidget = slicer.util.childWidgetVariables(distanceMapsUI)
    self.resectionsWidget = slicer.util.childWidgetVariables(resectionsUI)
    self.resectogramWidget = slicer.util.childWidgetVariables(resectogramUI)

    iconsPath = os.path.join(os.path.dirname(__file__), 'Resources/Icons')
    iconStyle = "QCheckBox::indicator:unchecked {{ image: url({0}/SlicerInvisible.png);}}\n QCheckBox::indicator:checked {{ image: url({1}/SlicerVisible.png);}}".format(iconsPath,iconsPath)
    self.resectogramWidget.Grid2DVisibility.setStyleSheet(iconStyle)
    self.resectionsWidget.Grid3DVisibility.setStyleSheet(iconStyle)

    # Add LiverSegmentsWidget
    wrapperWidget = slicer.qMRMLWidget()
    widgetLayout = qt.QVBoxLayout()
    margins = qt.QMargins(0,0,0,0)
    widgetLayout.setContentsMargins(margins)
    wrapperWidget.setLayout(widgetLayout)

    wrapperWidget.setMRMLScene(slicer.mrmlScene)
    segemtsWidget = LiverSegments.LiverSegmentsWidget(wrapperWidget)
    segemtsWidget.setup()
    self.layout.addWidget(wrapperWidget)

    wrapperWidget = slicer.qMRMLWidget()
    wrapperWidget.setLayout(qt.QVBoxLayout())
    wrapperWidget.setMRMLScene(slicer.mrmlScene)
    volumetryWidget = LiverVolumetry.LiverVolumetryWidget(wrapperWidget)
    volumetryWidget.setup()
    self.layout.addWidget(wrapperWidget)

    # Add a spacer at the botton to keep the UI flowing from top to bottom
    spacerItem = qt.QSpacerItem(0, 0, qt.QSizePolicy.Minimum, qt.QSizePolicy.MinimumExpanding)
    self.layout.addSpacerItem(spacerItem)

    # Create logic class. Logic implements all computations that should be possible to run
    # in batch mode, without a graphical user interface.
    self.logic = LiverLogic()

    # # Enable the use of FXAA (antialiasing)
    if not slicer.app.commandOptions().noMainWindow:
      renderer = slicer.app.layoutManager().threeDWidget(
        0).threeDView().renderWindow().GetRenderers().GetFirstRenderer()
      renderer.UseFXAAOn()

    # Configure uncertainty margin combo box
    self.resectionsWidget.UncertaintyMarginComboBox.addItems(['Custom', 'Max. Spacing', 'RMS Spacing'])

    # Connections
    self.distanceMapsWidget.TumorSegmentSelectorWidget.connect('currentSegmentChanged(QString)', self.onDistanceMapParameterChanged)
    self.distanceMapsWidget.ParenchymaSegmentSelectorWidget.connect('currentSegmentChanged(QString)', self.onDistanceMapParameterChanged)
    self.distanceMapsWidget.HepaticSegmentSelectorWidget.connect('currentSegmentChanged(QString)', self.onDistanceMapParameterChanged)
    self.distanceMapsWidget.PortalSegmentSelectorWidget.connect('currentSegmentChanged(QString)', self.onDistanceMapParameterChanged)
    self.distanceMapsWidget.SegmentationSelectorComboBox.addAttribute('vtkMRMLScalarVolumeNode', 'DistanceMap', 'True')
    self.distanceMapsWidget.OutputDistanceMapNodeComboBox.connect('currentNodeChanged(vtkMRMLNode*)', self.onDistanceMapParameterChanged)
    self.distanceMapsWidget.OutputDistanceMapNodeComboBox.addAttribute('vtkMRMLScalarVolumeNode', 'DistanceMap', 'True')
    self.distanceMapsWidget.ComputeDistanceMapsPushButton.connect('clicked(bool)', self.onComputeDistanceMapButtonClicked)
    self.resectionsWidget.CurvedRadioButton.toggled.connect(lambda: self.onRadioButtonState(self.resectionsWidget.CurvedRadioButton))
    self.resectionsWidget.FlatRadioButton.toggled.connect(lambda: self.onRadioButtonState(self.resectionsWidget.FlatRadioButton))
    self.resectionsWidget.ClosedCurveButton.toggled.connect(lambda: self.onRadioButtonState(self.resectionsWidget.ClosedCurveButton))
    self.resectionsWidget.MarkupsResectionCheckBox.toggled.connect(lambda: self.onMarkupsResectionCheckBoxChecked(self.resectionsWidget.MarkupsResectionCheckBox))
    self.resectionsWidget.InitialContourPositionButton.connect('clicked(bool)', self.onDefiningStartingContourPosition)
    self.resectionsWidget.ResectionNodeComboBox.connect('currentNodeChanged(vtkMRMLNode*)', self.onResectionNodeChanged)
    self.resectionsWidget.DistanceMapNodeComboBox.connect('currentNodeChanged(vtkMRMLNode*)', self.onResectionDistanceMapNodeChanged)
    self.resectionsWidget.DistanceMapNodeComboBox.addAttribute('vtkMRMLScalarVolumeNode', 'DistanceMap', 'True')
    self.resectionsWidget.DistanceMapNodeComboBox.addAttribute('vtkMRMLScalarVolumeNode', 'Computed', 'True')
    self.resectionsWidget.LiverSegmentSelectorWidget.connect('currentSegmentChanged(QString)', self.onResectionLiverModelNodeChanged)
    self.resectionsWidget.LiverSegmentSelectorWidget.connect('currentNodeChanged(vtkMRMLNode*)', self.onResectionLiverSegmentationNodeChanged)
    self.resectionsWidget.ResectionColorPickerButton.connect('colorChanged(QColor)', self.onResectionColorChanged)
    self.resectionsWidget.ResectionOpacityDoubleSlider.connect('valueChanged(double)', self.onResectionOpacityChanged)
    self.resectionsWidget.ResectionOpacityDoubleSpinBox.connect('valueChanged(double)', self.onResectionOpacityChanged)
    self.resectionsWidget.ResectionMarginSpinBox.connect('valueChanged(double)', self.onResectionMarginChanged)
    self.resectionsWidget.ResectionMarginColorPickerButton.connect('colorChanged(QColor)', self.onResectionMarginColorChanged)
    self.resectionsWidget.ResectionGridColorPickerButton.connect('colorChanged(QColor)', self.onResectionGridColorChanged)
    self.resectionsWidget.GridDivisionsDoubleSlider.connect('valueChanged(double)', self.onGridDivisionsChanged)
    self.resectionsWidget.GridThicknessDoubleSlider.connect('valueChanged(double)', self.onGridThicknessChanged)
    self.resectionsWidget.Grid3DVisibility.connect('stateChanged(int)', self.onGrid3DVisibilityChanged)
    self.resectionsWidget.ResectionLockCheckBox.connect('stateChanged(int)', self.onResectionLockChanged)
    self.resectionsWidget.UncertaintyMarginSpinBox.connect('valueChanged(double)', self.onUncertaintyMarginChanged)
    self.resectionsWidget.UncertaintyMarginColorPickerButton.connect('colorChanged(QColor)', self.onUncertaintyMarginColorChanged)
    self.resectionsWidget.UncertaintyMarginComboBox.connect('currentIndexChanged(int)', self.onUncertaintyMaginComboBoxChanged)
    self.resectionsWidget.InterpolatedMarginsCheckBox.connect('stateChanged(int)', self.onInterpolatedMarginsChanged)

    self.resectogramWidget.Resection2DCheckBox.connect('stateChanged(int)', self.onResection2DChanged)
    self.resectogramWidget.MirrorDisplayCheckBox.connect('stateChanged(int)', self.onMirrorDisplayCheckBoxChanged)
    self.resectogramWidget.FlexibleBoundaryCheckBox.connect('stateChanged(int)', self.onFlexibleBoundaryCheckBoxChanged)
    self.resectogramWidget.Grid2DVisibility.connect('stateChanged(int)', self.onGrid2DVisibilityChanged)
    self.resectogramWidget.HepaticContourThicknessSpinBox.connect('valueChanged(double)', self.onHepaticContourThicknessChanged)
    self.resectogramWidget.HepaticContourColorPickerButton.connect('colorChanged(QColor)', self.onHepaticContourColorChanged)
    self.resectogramWidget.PortalContourThicknessSpinBox.connect('valueChanged(double)', self.onPortalContourThicknessChanged)
    self.resectogramWidget.PortalContourColorPickerButton.connect('colorChanged(QColor)', self.onPortalContourColorChanged)
    self.resectogramWidget.VascularSegmentsNodeComboBox.connect('currentNodeChanged(vtkMRMLNode*)', self.onVascularSegmentsNodeChanged)
    self.resectogramWidget.ResectogramSizeSliderWidget.connect('valueChanged(double)', self.onResectogramSizeSliderChanged)


  def onRadioButtonState(self, rdbutton):
    """
    This function is triggered whenever the state of Radio Button changes
    """
    activeResectionNode = self.resectionsWidget.ResectionNodeComboBox.currentNode()
    self._distanceContourNode = self.resectionsWidget.DistanceContourComboBox.currentNode()
    segmentationNode = self.resectionsWidget.LiverSegmentSelectorWidget.currentNode()
    parenchymaSegmentId = self.resectionsWidget.LiverSegmentSelectorWidget.currentSegmentID()

    liverNode = segmentationNode.GetClosedSurfaceInternalRepresentation(parenchymaSegmentId)
    lvLogic = slicer.modules.liverresections.logic()
    if liverNode is None:
      segmentationNode.CreateClosedSurfaceRepresentation()
      liverNode = segmentationNode.GetClosedSurfaceInternalRepresentation(parenchymaSegmentId)

    # liverNode = self.logic.preprocessing(segmentationNode, parenchymaSegmentId)
    if rdbutton.isChecked():
      if rdbutton.text == "Curved":
        lvLogic.HideInitializationMarkupFromResection(activeResectionNode)
        lvLogic.HideBezierSurfaceMarkupFromResection(activeResectionNode)
        BezierNode = activeResectionNode.GetBezierSurfaceNode()
        BezierDisplay = BezierNode.GetDisplayNode()
        BezierDisplay.SetGlyphScale(3.0)
        liverNode = activeResectionNode.GetTargetOrganModelNode()
        if self._distanceContourNode is not None:
          self._distanceContourNode.SetDisplayVisibility(True)
          liverPolyData = liverNode.GetPolyData()
          self._preprocessedLiverNode = self.logic.preprocessing(liverPolyData)
          self._distanceContourNode.AddObserver(slicer.vtkMRMLMarkupsNode.PointEndInteractionEvent,
                                               lambda x, y: self.logic.runSurfacefromEFD(activeResectionNode,
                                                                                         self._distanceContourNode,
                                                                                         self._preprocessedLiverNode))
          self._distanceContourNode.AddObserver(slicer.vtkMRMLMarkupsNode.PointModifiedEvent,
                                          self.onDistanceContourStartInteraction)
        else:
          activeResectionNode.SetInitMode(activeResectionNode.Curved)
          activeResectionNode.SetTargetOrganModelNode(liverNode)
          lvLogic.AddResectionContour(activeResectionNode)
          liverPolyData = liverNode.GetPolyData()
          self._preprocessedLiverNode = self.logic.preprocessing(liverPolyData)
          node = slicer.util.getNodesByClass("vtkMRMLMarkupsDistanceContourNode")[-1]
          self.resectionsWidget.DistanceContourComboBox.setCurrentNode(node)
          # self._distanceContourNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLMarkupsDistanceContourNode")
          self._distanceContourNode = self.resectionsWidget.DistanceContourComboBox.currentNode()

          self._distanceContourNode.AddObserver(slicer.vtkMRMLMarkupsNode.PointEndInteractionEvent,
                                        lambda x, y: self.logic.runSurfacefromEFD(activeResectionNode,
                                                                                  self._distanceContourNode,
                                                                                  self._preprocessedLiverNode))
          self._distanceContourNode.AddObserver(slicer.vtkMRMLMarkupsNode.PointModifiedEvent,
                                        self.onDistanceContourStartInteraction)
          BezierNode = activeResectionNode.GetBezierSurfaceNode()
          BezierNode.AddObserver(slicer.vtkMRMLMarkupsNode.PointStartInteractionEvent,
                                 lambda x, y: self.BezierSurfaceModified(self._distanceContourNode))

      elif rdbutton.text == "MarkupClosedCurve":
        self._distanceContourNode = self.resectionsWidget.DistanceContourComboBox.currentNode()
        if self._distanceContourNode is not None:
          self._distanceContourNode.SetDisplayVisibility(False)
        lvLogic.HideInitializationMarkupFromResection(activeResectionNode)
        lvLogic.HideBezierSurfaceMarkupFromResection(activeResectionNode)
      elif rdbutton.text == "Flat":
        lvLogic.ShowInitializationMarkupFromResection(activeResectionNode)
        lvLogic.HideBezierSurfaceMarkupFromResection(activeResectionNode)
        BezierNode = activeResectionNode.GetBezierSurfaceNode()
        BezierDisplay = BezierNode.GetDisplayNode()
        BezierDisplay.SetGlyphScale(3.0)
        if self._distanceContourNode is not None:
          self._distanceContourNode.SetDisplayVisibility(False)
        return

  def onDefiningStartingContourPosition(self):
    # Get liver segmentation data
    liverSegmentationNode = self.resectionsWidget.LiverSegmentSelectorWidget.currentNode()
    liverSegmentId = self.resectionsWidget.LiverSegmentSelectorWidget.currentSegmentID()
    liverPolyData = liverSegmentationNode.GetClosedSurfaceInternalRepresentation(liverSegmentId)

    # Get tumor segmentation data
    tumorSegmentationNode = self.resectionsWidget.TumorSegmentSelectorWidget.currentNode()
    tumorSegmentId = self.resectionsWidget.TumorSegmentSelectorWidget.currentSegmentID()
    tumorPolyData = tumorSegmentationNode.GetClosedSurfaceInternalRepresentation(tumorSegmentId)

    # Get active distance contour node
    activeDistanceContour = self.resectionsWidget.DistanceContourComboBox.currentNode()

    # Calculate center of mass for tumor and liver
    com_tumor = vtk.vtkCenterOfMass()
    com_tumor.SetInputData(tumorPolyData)
    com_tumor.SetUseScalarsAsWeights(False)
    com_tumor.Update()
    center_tumor = np.array(com_tumor.GetCenter())

    com_liver = vtk.vtkCenterOfMass()
    com_liver.SetInputData(liverPolyData)
    com_liver.SetUseScalarsAsWeights(False)
    com_liver.Update()
    center_liver = np.array(com_liver.GetCenter())

    # Calculate the vector between tumor and liver centers
    vector_tumor_to_liver = center_liver - center_tumor

    # Calculate median point between tumor and liver centers
    median_point = np.median(np.array([center_liver, center_tumor]), axis=0)

    # Get camera information
    threedView = slicer.app.layoutManager().threeDWidget(0).threeDView()
    renderer = threedView.renderWindow().GetRenderers().GetFirstRenderer()
    camera = renderer.GetActiveCamera()

    # Calculate cross view vector
    view_up = np.array(camera.GetViewUp())
    view_normal = np.array(camera.GetViewPlaneNormal())
    cross_view = np.cross(view_up, view_normal)

    # Calculate extent and product of vectors
    bounds = liverPolyData.GetBounds()
    extent = (bounds[3] - bounds[2])/np.sqrt(2)
    mag_vector1 = np.linalg.norm(vector_tumor_to_liver)
    mag_vector2 = np.linalg.norm(cross_view)
    v1_u = vector_tumor_to_liver/mag_vector1
    v2_u = cross_view/mag_vector2
    alpha = np.arccos(np.clip(np.dot(v1_u, v2_u), -1.0, 1.0))
    # print('alpha', alpha)

    # Calculate the contour point
    if alpha >= np.pi / 2:
      point = center_tumor - extent * v2_u
    else:
      point = center_tumor + extent * v2_u

    # Set control point positions for the active distance contour
    activeDistanceContour.SetNthControlPointPosition(0, tuple(median_point))
    activeDistanceContour.SetNthControlPointPosition(1, tuple(point))

  def onMarkupsResectionCheckBoxChecked(self, checkbox):

    qt.QApplication.setOverrideCursor(qt.Qt.WaitCursor)

    activeMarkupClosedCurveNode = self.resectionsWidget.MarkupClosedCurveNodeComboBox.currentNode()
    activeResectionNode = self.resectionsWidget.ResectionNodeComboBox.currentNode()
    liverNode = activeResectionNode.GetTargetOrganModelNode()
    # self.logic.setInputCurveNode(activeMarkupClosedCurveNode)
    if checkbox.isChecked():
      activeMarkupClosedCurveNode.AddObserver(slicer.vtkMRMLMarkupsNode.PointEndInteractionEvent,
                                              lambda x, y: self.logic.runSurfacefromCurve(activeResectionNode,
                                                                                          activeMarkupClosedCurveNode,
                                                                                          liverNode))
      activeMarkupClosedCurveNode.AddObserver(slicer.vtkMRMLMarkupsNode.PointModifiedEvent,
                                              self.onDistanceContourStartInteraction)
      qt.QApplication.restoreOverrideCursor()
      qt.QMessageBox.information(None, "Information", "Resection surface initialization finished.")

  def onDistanceMapParameterChanged(self):
    """
    This function is triggered whenever any parameter of the distance maps are changed
    """
    node1 = self.distanceMapsWidget.TumorSegmentSelectorWidget.currentNode()
    node2 = self.distanceMapsWidget.ParenchymaSegmentSelectorWidget.currentNode()
    node3 = self.distanceMapsWidget.HepaticSegmentSelectorWidget.currentNode()
    node4 = self.distanceMapsWidget.PortalSegmentSelectorWidget.currentNode()
    node5 = self.distanceMapsWidget.OutputDistanceMapNodeComboBox.currentNode()
    self.numComps = 4 - [node1, node2, node3, node4, node5].count(None)
    self.distanceMapsWidget.ComputeDistanceMapsPushButton.setEnabled(None not in [node1, node2, node5])


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

        self.resectionsWidget.LiverSegmentSelectorWidget.blockSignals(True)
        self.resectionsWidget.LiverSegmentSelectorWidget.setCurrentNode(None)
        self.resectionsWidget.LiverSegmentSelectorWidget.blockSignals(False)

        self.resectionsWidget.DistanceMapNodeComboBox.blockSignals(True)
        self.resectionsWidget.DistanceMapNodeComboBox.setCurrentNode(activeResectionNode.GetDistanceMapVolumeNode())
        self.resectionsWidget.DistanceMapNodeComboBox.blockSignals(False)

        self.resectogramWidget.VascularSegmentsNodeComboBox.blockSignals(True)
        self.resectogramWidget.VascularSegmentsNodeComboBox.setCurrentNode(activeResectionNode.GetVascularSegmentsVolumeNode())
        self.resectogramWidget.VascularSegmentsNodeComboBox.blockSignals(False)

        self.resectogramWidget.HepaticContourColorPickerButton.blockSignals(True)
        color = activeResectionNode.GetHepaticContourColor()
        self.resectogramWidget.HepaticContourColorPickerButton.setColor(qt.QColor.fromRgbF(color[0], color[1], color[2]))
        self.resectogramWidget.HepaticContourColorPickerButton.blockSignals(False)

        self.resectogramWidget.PortalContourColorPickerButton.blockSignals(True)
        color = activeResectionNode.GetPortalContourColor()
        self.resectogramWidget.PortalContourColorPickerButton.setColor(qt.QColor.fromRgbF(color[0], color[1], color[2]))
        self.resectogramWidget.PortalContourColorPickerButton.blockSignals(False)

        self.resectionsWidget.ResectionColorPickerButton.blockSignals(True)
        color = activeResectionNode.GetResectionColor()
        self.resectionsWidget.ResectionColorPickerButton.setColor(
          qt.QColor.fromRgbF(color[0], color[1], color[2]))
        self.resectionsWidget.ResectionColorPickerButton.blockSignals(False)

        self.resectionsWidget.ResectionMarginSpinBox.blockSignals(True)
        self.resectionsWidget.ResectionMarginSpinBox.setValue(activeResectionNode.GetResectionMargin())
        self.resectionsWidget.ResectionMarginSpinBox.minimum = activeResectionNode.GetUncertaintyMargin()
        self.resectionsWidget.ResectionMarginSpinBox.blockSignals(False)

        self.resectionsWidget.ResectionMarginColorPickerButton.blockSignals(True)
        color = activeResectionNode.GetResectionMarginColor()
        self.resectionsWidget.ResectionMarginColorPickerButton.setColor(
          qt.QColor.fromRgbF(color[0], color[1], color[2]))
        self.resectionsWidget.ResectionMarginColorPickerButton.blockSignals(False)

        self.resectionsWidget.ResectionOpacityDoubleSlider.blockSignals(True)
        self.resectionsWidget.ResectionOpacityDoubleSlider.setValue(activeResectionNode.GetResectionOpacity())
        self.resectionsWidget.ResectionOpacityDoubleSlider.blockSignals(False)

        self.resectionsWidget.ResectionOpacityDoubleSpinBox.blockSignals(True)
        self.resectionsWidget.ResectionOpacityDoubleSpinBox.setValue(activeResectionNode.GetResectionOpacity())
        self.resectionsWidget.ResectionOpacityDoubleSpinBox.blockSignals(False)

        self.resectionsWidget.ResectionGridColorPickerButton.blockSignals(True)
        color = activeResectionNode.GetResectionGridColor()
        self.resectionsWidget.ResectionGridColorPickerButton.setColor(
          qt.QColor.fromRgbF(color[0], color[1], color[2]))
        self.resectionsWidget.ResectionGridColorPickerButton.blockSignals(False)

        self.resectionsWidget.ResectionLockCheckBox.blockSignals(True)
        if (activeResectionNode.GetWidgetVisibility()):
          self.resectionsWidget.ResectionLockCheckBox.setCheckState(0)
        else:
          self.resectionsWidget.ResectionLockCheckBox.setCheckState(2)
        self.resectionsWidget.ResectionLockCheckBox.blockSignals(False)

        self.resectogramWidget.Resection2DCheckBox.blockSignals(True)
        if (activeResectionNode.GetWidgetVisibility()):
          self.resectogramWidget.Resection2DCheckBox.setCheckState(0)
        else:
          self.resectogramWidget.Resection2DCheckBox.setCheckState(2)
        self.resectogramWidget.Resection2DCheckBox.blockSignals(False)

        self.resectogramWidget.FlexibleBoundaryCheckBox.blockSignals(True)
        if (activeResectionNode.GetWidgetVisibility()):
          self.resectogramWidget.FlexibleBoundaryCheckBox.setCheckState(0)
        else:
          self.resectogramWidget.FlexibleBoundaryCheckBox.setCheckState(2)
        self.resectogramWidget.FlexibleBoundaryCheckBox.blockSignals(False)

        self.resectionsWidget.UncertaintyMarginSpinBox.blockSignals(True)
        self.resectionsWidget.UncertaintyMarginSpinBox.setValue(activeResectionNode.GetUncertaintyMargin())
        self.resectionsWidget.UncertaintyMarginSpinBox.blockSignals(False)

        self.resectionsWidget.UncertaintyMarginColorPickerButton.blockSignals(True)
        color = activeResectionNode.GetUncertaintyMarginColor()
        self.resectionsWidget.UncertaintyMarginColorPickerButton.setColor(
          qt.QColor.fromRgbF(color[0], color[1], color[2]))
        self.resectionsWidget.UncertaintyMarginColorPickerButton.blockSignals(False)

        self.resectionsWidget.ResectionLockCheckBox.blockSignals(True)
        if activeResectionNode.GetWidgetVisibility():
          self.resectionsWidget.ResectionLockCheckBox.setCheckState(0)  # Unchecked
        else:
          self.resectionsWidget.ResectionLockCheckBox.setCheckState(2)  # Checked
        self.resectionsWidget.ResectionLockCheckBox.blockSignals(False)

        self.resectionsWidget.InterpolatedMarginsCheckBox.blockSignals(True)
        if activeResectionNode.GetInterpolatedMargins():
          self.resectionsWidget.InterpolatedMarginsCheckBox.setCheckState(2)  # Checked
        else:
          self.resectionsWidget.InterpolatedMarginsCheckBox.setCheckState(0)  # Unchecked
        self.resectionsWidget.InterpolatedMarginsCheckBox.blockSignals(False)

        if activeResectionNode.GetState() == activeResectionNode.Initialization: # Show initialization
          lvLogic.HideBezierSurfaceMarkupFromResection(self._currentResectionNode)
          lvLogic.HideInitializationMarkupFromResection(self._currentResectionNode)
          lvLogic.ShowInitializationMarkupFromResection(activeResectionNode)
          lvLogic.ShowBezierSurfaceMarkupFromResection(activeResectionNode)

        elif activeResectionNode.GetState() == activeResectionNode.Deformation:  # Show bezier surface
          lvLogic.HideInitializationMarkupFromResection(self._currentResectionNode)
          lvLogic.HideBezierSurfaceMarkupFromResection(self._currentResectionNode)
          lvLogic.ShowBezierSurfaceMarkupFromResection(activeResectionNode)
      else:
        lvLogic.HideBezierSurfaceMarkupFromResection(self._currentResectionNode)
        lvLogic.HideInitializationMarkupFromResection(self._currentResectionNode)
        renderers = slicer.app.layoutManager().threeDWidget(0).threeDView().renderWindow().GetRenderers()
        if renderers.GetNumberOfItems() == 5:
          renderers.RemoveItem(4)
        self.resectogramWidget.Resection2DCheckBox.setCheckState(0)
        self.resectogramWidget.Resection2DCheckBox.setEnabled(0)
        self._currentResectionNode.SetShowResection2D(False)

    self._currentResectionNode = activeResectionNode

  def onResectionDistanceMapNodeChanged(self):
    """
    This function is called when the resection distance map selector changes
    """
    if self._currentResectionNode is not None:
      distanceMapNode = self.resectionsWidget.DistanceMapNodeComboBox.currentNode()
      self._currentResectionNode.SetTextureNumComps(self.numComps)
      self._currentResectionNode.SetDistanceMapVolumeNode(distanceMapNode)
      self.resectionsWidget.ResectionMarginGroupBox.setEnabled(distanceMapNode is not None)
      self.resectionsWidget.UncertaintyMarginGroupBox.setEnabled(distanceMapNode is not None)
      self.resectionsWidget.ResectionPreviewGroupBox.setEnabled(distanceMapNode is not None)
      self.resectogramWidget.Resection2DCheckBox.setEnabled(distanceMapNode is not None)

  def onResectionLiverSegmentationNodeChanged(self):
    self.resectionsWidget.LiverSegmentSelectorWidget.blockSignals(True)
    self.resectionsWidget.LiverSegmentSelectorWidget.setCurrentSegmentID('')
    self.resectionsWidget.LiverSegmentSelectorWidget.blockSignals(False)

  def onResectionLiverModelNodeChanged(self):
    """
    This function is called when the resection liver model node changes
    """
    if self._currentResectionNode is not None:
      parenchymaSegmentId = self.resectionsWidget.LiverSegmentSelectorWidget.currentSegmentID()
      if parenchymaSegmentId == '':
        return
      segmentationNode = self.resectionsWidget.LiverSegmentSelectorWidget.currentNode()
      modelPolyData = segmentationNode.GetClosedSurfaceInternalRepresentation(parenchymaSegmentId)
      if modelPolyData is None:
        segmentationNode.CreateClosedSurfaceRepresentation()
        modelPolyData = segmentationNode.GetClosedSurfaceInternalRepresentation(parenchymaSegmentId)
      modelPolyDataCopy = vtk.vtkPolyData()
      modelPolyDataCopy.DeepCopy(modelPolyData)
      modelNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelNode')
      modelNode.CreateDefaultDisplayNodes()
      modelNode.SetHideFromEditors(True)
      modelDisplayNode = modelNode.GetDisplayNode()
      modelDisplayNode.SetOpacity(0.0)
      modelNode.SetAndObservePolyData(modelPolyDataCopy)
      self._currentResectionNode.SetTargetOrganModelNode(modelNode)
      self.resectionsWidget.ResectionVisualizationGroupBox.setEnabled(modelNode is not None)
      self.resectionsWidget.GridGroupBox.setEnabled(modelNode is not None)
      # self.resectionVolumetryWidget.ResectionVolumetryGroupWidget.setEnabled(modelNode is not None)

  def onDistanceContourStartInteraction(self, caller, event):
    """
    This function is called when distance contour start interaction.
    """
    lvLogic = slicer.modules.liverresections.logic()
    lvLogic.HideBezierSurfaceMarkupFromResection(self._currentResectionNode)

  def BezierSurfaceModified(self, distanceNode):
    distanceNode.SetDisplayVisibility(False)

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
    self.resectionsWidget.TotalMarginLabel.setText('{:.2f} mm'.format(resection + uncertainty))

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

    qt.QApplication.setOverrideCursor(qt.Qt.WaitCursor)
    segmentationNode = self.distanceMapsWidget.SegmentationSelectorComboBox.currentNode()
    refVolumeNode = self.distanceMapsWidget.ReferenceVolumeSelector.currentNode()
    tumorSegmentId = self.distanceMapsWidget.TumorSegmentSelectorWidget.currentSegmentID()
    parenchymaSegmentId = self.distanceMapsWidget.ParenchymaSegmentSelectorWidget.currentSegmentID()
    hepaticSegmentId = self.distanceMapsWidget.HepaticSegmentSelectorWidget.currentSegmentID()
    portalSegmentId = self.distanceMapsWidget.PortalSegmentSelectorWidget.currentSegmentID()
    segmentationIds = vtk.vtkStringArray()

    """
    Export labelmaps volumes for the selected segmentations
    """
    tumorLabelmapVolumeNode = slicer.mrmlScene.GetFirstNodeByName("TumorLabelMap")
    if not tumorLabelmapVolumeNode:
      tumorLabelmapVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", "TumorLabelMap")
    parenchymaLabelmapVolumeNode = slicer.mrmlScene.GetFirstNodeByName("ParenchymaLabelMap")
    if not parenchymaLabelmapVolumeNode:
      parenchymaLabelmapVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", "ParenchymaLabelMap")
    hepaticLabelmapVolumeNode = slicer.mrmlScene.GetFirstNodeByName("HepaticLabelMap")
    if not hepaticLabelmapVolumeNode:
      hepaticLabelmapVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", "HepaticLabelMap")
    portalLabelmapVolumeNode = slicer.mrmlScene.GetFirstNodeByName("PortalLabelMap")
    if not portalLabelmapVolumeNode:
      portalLabelmapVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", "PortalLabelMap")

    segmentationIds.Initialize()
    segmentationIds.InsertNextValue(tumorSegmentId)
    slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(segmentationNode, segmentationIds,
                                                                      tumorLabelmapVolumeNode, refVolumeNode)

    segmentationIds.Initialize()
    segmentationIds.InsertNextValue(parenchymaSegmentId)
    slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(segmentationNode, segmentationIds,
                                                                      parenchymaLabelmapVolumeNode, refVolumeNode)

    segmentationIds.Initialize()
    segmentationIds.InsertNextValue(hepaticSegmentId)
    slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(segmentationNode, segmentationIds,
                                                                      hepaticLabelmapVolumeNode, refVolumeNode)

    segmentationIds.Initialize()
    segmentationIds.InsertNextValue(portalSegmentId)
    slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(segmentationNode, segmentationIds,
                                                                      portalLabelmapVolumeNode, refVolumeNode)

    """
    Export model nodes for the selected segmentations
    """
    # segmentationIds.Initialize()
    # segmentationIds.InsertNextValue(tumorSegmentId)
    # segmentationIds.InsertNextValue(parenchymaSegmentId)
    # shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
    # exportFolderItemId = shNode.CreateFolderItem(shNode.GetSceneItemID(), "Liver Models")
    # slicer.app.pauseRender()
    # slicer.modules.segmentations.logic().ExportSegmentsToModels(segmentationNode, segmentationIds,
    #     exportFolderItemId)

    # Hide the models to avoid collition with the 3D representation of segmentations
    # pluginHandler = slicer.qSlicerSubjectHierarchyPluginHandler().instance()
    # folderPlugin = pluginHandler.pluginByName("Folder")
    # folderPlugin.setDisplayVisibility(exportFolderItemId, 0)

    outputVolumeNode = self.distanceMapsWidget.OutputDistanceMapNodeComboBox.currentNode()

    # Center the 3D view
    # layoutManager = slicer.app.layoutManager()
    # threeDWidget = layoutManager.threeDWidget(0)
    # threeDView = threeDWidget.threeDView()
    # threeDView.resetFocalPoint()

    downSamplingRate = self.distanceMapsWidget.DownsamplingRateSpinBox.value
    self.logic.computeDistanceMaps(tumorLabelmapVolumeNode, parenchymaLabelmapVolumeNode, hepaticLabelmapVolumeNode, portalLabelmapVolumeNode, outputVolumeNode, downSamplingRate)

    # slicer.app.resumeRender()
    slicer.mrmlScene.RemoveNode(tumorLabelmapVolumeNode)
    slicer.mrmlScene.RemoveNode(parenchymaLabelmapVolumeNode)
    slicer.mrmlScene.RemoveNode(hepaticLabelmapVolumeNode)
    slicer.mrmlScene.RemoveNode(portalLabelmapVolumeNode)

    #slicer.app.resumeRender()
    qt.QApplication.restoreOverrideCursor()
    qt.QMessageBox.information(None, "Information", "Distance maps computed.")
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
      self._currentResectionNode.SetInterpolatedMargins(
        self.resectionsWidget.InterpolatedMarginsCheckBox.isChecked())

  def onResectionColorChanged(self):
    """
    This function is called whenever the resection margin color has changed
    """
    if self._currentResectionNode is not None:
      color = self.resectionsWidget.ResectionColorPickerButton.color
      rgbF = [color.redF(), color.greenF(), color.blueF()]
      self._currentResectionNode.SetResectionColor(rgbF)

  def onResectionGridColorChanged(self):
    """
    This function is called whenever the  grid color has changed
    """
    if self._currentResectionNode is not None:
      color = self.resectionsWidget.ResectionGridColorPickerButton.color
      rgbF = [color.redF(), color.greenF(), color.blueF()]
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
      rgbF = [color.redF(), color.greenF(), color.blueF()]
      self._currentResectionNode.SetResectionMarginColor(rgbF)

  def onUncertaintyMarginColorChanged(self):
    """
    This function is called whenever the resection margin color has changed
    """
    if self._currentResectionNode is not None:
      color = self.resectionsWidget.UncertaintyMarginColorPickerButton.color
      rgbF = [color.redF(), color.greenF(), color.blueF()]
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

  def onGrid3DVisibilityChanged(self):
    """
    This function is called when the EnableGrid checkbox changes.
    """
    if self._currentResectionNode:
      self._currentResectionNode.SetGrid3DVisibility(self.resectionsWidget.Grid3DVisibility.isChecked())

  def onResection2DChanged(self):
    """
    This function is called when the resection2D checkbox changes.
    """
    if self._currentResectionNode is not None:
      self._currentResectionNode.SetShowResection2D(self.resectogramWidget.Resection2DCheckBox.isChecked())
      if self.distanceMapsWidget.HepaticSegmentSelectorWidget.currentNode():
        self.resectogramWidget.HepaticContourGroupBox.setEnabled(self.resectogramWidget.Resection2DCheckBox.isChecked())
      if self.distanceMapsWidget.PortalSegmentSelectorWidget.currentNode():
        self.resectogramWidget.PortalContourGroupBox.setEnabled(self.resectogramWidget.Resection2DCheckBox.isChecked())
      self.resectogramWidget.VsacularSegmentsGroupBox.setEnabled(self.resectogramWidget.Resection2DCheckBox.isChecked())
      self.resectogramWidget.FlexibleBoundaryCheckBox.setEnabled(self.resectogramWidget.Resection2DCheckBox.isChecked())
      self.resectogramWidget.Grid2DVisibility.setEnabled(self.resectogramWidget.Resection2DCheckBox.isChecked())
      self.resectogramWidget.MirrorDisplayCheckBox.setEnabled(self.resectogramWidget.Resection2DCheckBox.isChecked())
      self.resectogramWidget.ResectogramSizeSliderGroupBox.setEnabled(self.resectogramWidget.Resection2DCheckBox.isChecked())
      renderers = slicer.app.layoutManager().threeDWidget(0).threeDView().renderWindow().GetRenderers()
      if self.resectogramWidget.Resection2DCheckBox.isChecked() == 0 and renderers.GetNumberOfItems() == 5:
        renderers.RemoveItem(4)
    else:
      self._currentResectionNode.SetShowResection2D(not self.resectogramWidget.Resection2DCheckBox.isChecked())

  def onMirrorDisplayCheckBoxChanged(self):
    """
    This function is called when the MirrorDisplay changes.
    """
    if self._currentResectionNode:
      self._currentResectionNode.SetMirrorDisplay(self.resectogramWidget.MirrorDisplayCheckBox.isChecked())
      # renderers = slicer.app.layoutManager().threeDWidget(0).threeDView().renderWindow().GetRenderers()
      # if renderers.GetNumberOfItems() == 5:
      #   renderer2D = renderers.GetItemAsObject(4)
      #   camera2D = renderer2D.GetActiveCamera()
      #   position2D = camera2D.GetPosition();
      #   focalPoint2D = camera2D.GetFocalPoint()
      #   camera2D.SetPosition(position2D[0], position2D[1], -position2D[2])
      #   camera2D.SetFocalPoint(focalPoint2D[0], focalPoint2D[1], -focalPoint2D[2])

  def onFlexibleBoundaryCheckBoxChanged(self):
    """
    This function is called when the EnableFlexibleBoundary checkbox changes.
    """
    if self._currentResectionNode:
      self._currentResectionNode.SetEnableFlexibleBoundary(self.resectogramWidget.FlexibleBoundaryCheckBox.isChecked())

  def onGrid2DVisibilityChanged(self):
    """
    This function is called when the EnableGrid checkbox changes.
    """
    if self._currentResectionNode:
      self._currentResectionNode.SetGrid2DVisibility(self.resectogramWidget.Grid2DVisibility.isChecked())

  def onResectogramSizeSliderChanged(self):
    """
    This function is called when the Resectogram Size Slider changes.
    """
    if self._currentResectionNode:
      if self.resectogramWidget.Resection2DCheckBox.isChecked():
        ymin = self.resectogramWidget.ResectogramSizeSliderWidget.value
        view = slicer.app.layoutManager().threeDWidget(0).threeDView()
        renderers = view.renderWindow().GetRenderers()
        renderer2D = renderers.GetItemAsObject(4)
        renderer2D.SetViewport([0.0, ymin, 0.3, 1.0])
        view.forceRender()

  def onHepaticContourThicknessChanged(self):
    """
    This function is called when the resection margin spinbox changes.
    """
    if self._currentResectionNode is not None:
      self._currentResectionNode.SetHepaticContourThickness(self.resectogramWidget.HepaticContourThicknessSpinBox.value)

  def onPortalContourThicknessChanged(self):
    """
    This function is called when the resection margin spinbox changes.
    """
    if self._currentResectionNode is not None:
      self._currentResectionNode.SetPortalContourThickness(self.resectogramWidget.PortalContourThicknessSpinBox.value)

  def onHepaticContourColorChanged(self):
    """
    This function is called whenever the resection margin color has changed
    """
    if self._currentResectionNode is not None:
      color = self.resectogramWidget.HepaticContourColorPickerButton.color
      rgbF = [color.redF(), color.greenF(), color.blueF()]
      self._currentResectionNode.SetHepaticContourColor(rgbF)

  def onPortalContourColorChanged(self):
    """
    This function is called whenever the resection margin color has changed
    """
    if self._currentResectionNode is not None:
      color = self.resectogramWidget.PortalContourColorPickerButton.color
      rgbF = [color.redF(), color.greenF(), color.blueF()]
      self._currentResectionNode.SetPortalContourColor(rgbF)

  def onVascularSegmentsNodeChanged(self):
    """
    This function is called when the resection distance map selector changes
    """
    if self._currentResectionNode is not None:
      VascularSegmentsNode = self.resectogramWidget.VascularSegmentsNodeComboBox.currentNode()
      self._currentResectionNode.SetVascularSegmentsVolumeNode(VascularSegmentsNode)

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

  def computeDistanceMaps(self, tumorNode, parenchymaNode, hepaticNode, portalNode, outputNode, downSamplingRate=1):

    if outputNode is not None:
      import sitkUtils
      import SimpleITK as sitk

      tumorDistanceImage = None
      parenchymaDistanceImage = None
      hepaticDistanceImage = None
      portalDistanceImage = None

      # Compute tumor distance map
      if tumorNode != None:
        tumorImage = sitkUtils.PullVolumeFromSlicer(tumorNode)
        tumorDistanceImage = sitk.SignedMaurerDistanceMap(tumorImage, False, False, True)
        logging.debug("Computing Tumor Distance Map...")
        # tumorDistanceImageDown =  self.imageResample( tumorDistanceImage, [150,150,150], "linear")

      # Compute parenchyma distance map
      if parenchymaNode != None:
        parenchymaImage = sitkUtils.PullVolumeFromSlicer(parenchymaNode)
        parenchymaDistanceImage = sitk.SignedMaurerDistanceMap(parenchymaImage, False, False, True)
        logging.debug("Computing Parenchyma Distance Map...")
        # parenchymaDistanceImageDown = self.imageResample( parenchymaDistanceImage, [150,150,150], "linear")

      # Compute hepatic distance map
      if hepaticNode != None:
        hepaticImage = sitkUtils.PullVolumeFromSlicer(hepaticNode)
        hepaticDistanceImage = sitk.SignedMaurerDistanceMap(hepaticImage, False, False, True)
        logging.debug("Computing Hepatic Distance Map...")

      # Compute portal distance map
      if portalNode != None:
        portalImage = sitkUtils.PullVolumeFromSlicer(portalNode)
        portalDistanceImage = sitk.SignedMaurerDistanceMap(portalImage, False, False, True)
        logging.debug("Computing Portal Distance Map...")

      #Combine distance maps
      if downSamplingRate != 1:
        imageSize = tumorImage.GetSize()
        newSize = [round(i/downSamplingRate) for i in imageSize]
        tumorDistanceImageDown =  self.imageResample( tumorDistanceImage, [newSize[0],newSize[1],newSize[2]], "linear")
        parenchymaDistanceImageDown = self.imageResample( parenchymaDistanceImage, [newSize[0],newSize[1],newSize[2]], "linear")
        hepaticDistanceImageDown = self.imageResample( hepaticDistanceImage, [newSize[0],newSize[1],newSize[2]], "linear")
        portalDistanceImageDown = self.imageResample( portalDistanceImage, [newSize[0],newSize[1],newSize[2]], "linear")
        compositeDistanceMap = sitk.Compose(*[i for i in [tumorDistanceImageDown, parenchymaDistanceImageDown, hepaticDistanceImageDown, portalDistanceImageDown] if i])
      else:
        compositeDistanceMap = sitk.Compose(*[i for i in [tumorDistanceImage, parenchymaDistanceImage, hepaticDistanceImage, portalDistanceImage] if i])

      sitkUtils.PushVolumeToSlicer(compositeDistanceMap, targetNode = outputNode, className='vtkMRMLVectorVolumeNode')
      outputNode.SetAttribute('DistanceMap', "True");
      outputNode.SetAttribute('Computed', "True");

  def imageResample(self, inputImage, resampledSize, interpolatorType):
    """
    Resampling the Maurer distance map
    """
    if inputImage is not None:
      import SimpleITK as sitk

    outputOrigin = inputImage.GetOrigin()
    outputDirection = inputImage.GetDirection()
    inputSizePixels = inputImage.GetSize()
    inputSpacing = inputImage.GetSpacing()
    inputSize = [inputSpacing[0] * inputSizePixels[0],
                 inputSpacing[1] * inputSizePixels[1],
                 inputSpacing[2] * inputSizePixels[2]]

    outputSpacing = [0.0, 0.0, 0.0]
    outputSpacing[0] = inputSize[0] / float(resampledSize[0])
    outputSpacing[1] = inputSize[1] / float(resampledSize[1])
    outputSpacing[2] = inputSize[2] / float(resampledSize[2])

    NewOutputOrigin = [0.0, 0.0, 0.0]
    NewOutputOrigin[0] = outputOrigin[0] + (outputSpacing[0] / 2.0 - inputSpacing[0] / 2.0) * outputDirection[0];
    NewOutputOrigin[1] = outputOrigin[1] + (outputSpacing[1] / 2.0 - inputSpacing[1] / 2.0) * outputDirection[4];
    NewOutputOrigin[2] = outputOrigin[2] + (outputSpacing[2] / 2.0 - inputSpacing[2] / 2.0) * outputDirection[8];

    if interpolatorType == "linear":
      interpolator = sitk.sitkLinear
    elif interpolatorType == "b-spline":
      interpolator = sitk.sitkBSpline
    elif interpolatorType == "nearest neighbor":
      interpolator = sitk.sitkNearestNeighbor

    imageResampleFilter = sitk.ResampleImageFilter()
    imageResampleFilter.SetInterpolator(interpolator)
    imageResampleFilter.SetOutputOrigin(NewOutputOrigin)
    imageResampleFilter.SetOutputSpacing(outputSpacing)
    imageResampleFilter.SetOutputDirection(outputDirection)
    imageResampleFilter.SetSize(resampledSize)

    resampledImage = imageResampleFilter.Execute(inputImage)

    return resampledImage

  def preprocessing(self, surfacePolyData, targetNumberOfPoints=800000, decimationAggressiveness=2):
    numberOfInputPoints = surfacePolyData.GetNumberOfPoints()

    if numberOfInputPoints == 0:
      raise ValueError("Input surface model is empty")

    elif numberOfInputPoints <= 400000:
      subdiv = vtk.vtkLinearSubdivisionFilter()
      subdiv.SetInputData(surfacePolyData)
      subdiv.SetNumberOfSubdivisions(1)
      subdiv.Update()
      subPolyData = subdiv.GetOutput()

      if subPolyData.GetNumberOfPoints() == 0:
        logging.warning("Mesh subdivision failed. Skip subdivision step.")

      numberOfPoints = subPolyData.GetNumberOfPoints()
      reductionFactor = (numberOfPoints - targetNumberOfPoints) / numberOfPoints
      print('reduction factor',reductionFactor)

      if reductionFactor > 0.0:
        surfacePolyData = self.run_decimation(subPolyData, reductionFactor)
      else:
        surfacePolyData = vtk.vtkPolyData()  # Create an empty vtkPolyData object
        surfacePolyData.DeepCopy(subPolyData)

    preprocessedPolyData = self.process_polydata(surfacePolyData)
    return self.create_model_node(preprocessedPolyData)

  def run_decimation(self, inputPolyData, reductionFactor):
    decimation = vtk.vtkDecimatePro()
    decimation.SetInputData(inputPolyData)
    decimation.SetTargetReduction(reductionFactor)
    decimation.SetPreserveTopology(True)
    decimation.SetFeatureAngle(60.0)
    decimation.SetBoundaryVertexDeletion(False)
    decimation.SetDegree(20)
    decimation.SetMaximumError(0.001)
    decimation.Update()
    return decimation.GetOutput()

  def process_polydata(self, inputPolyData):
    cleaner = vtk.vtkCleanPolyData()
    cleaner.SetInputData(inputPolyData)
    cleaner.Update()

    triangulator = vtk.vtkTriangleFilter()
    triangulator.SetInputData(cleaner.GetOutput())
    triangulator.PassLinesOff()
    triangulator.PassVertsOff()
    triangulator.Update()

    normals = vtk.vtkPolyDataNormals()
    normals.SetInputData(triangulator.GetOutput())
    normals.SetAutoOrientNormals(1)
    normals.SetFlipNormals(0)
    normals.SetConsistency(1)
    normals.SplittingOff()
    normals.Update()

    return normals.GetOutput()

  def create_model_node(self, polyData):
    modelNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelNode')
    modelNode.SetName("PreprocessedLiver")
    modelNode.CreateDefaultDisplayNodes()
    modelDisplayNode = modelNode.GetDisplayNode()
    modelDisplayNode.SetOpacity(0.2)
    modelDisplayNode.Visibility3DOff()
    modelNode.SetAndObservePolyData(polyData)
    return modelNode

  def CreatePolyDataFromCoords(self, coordinates):
    """
    Takes the x, y, and z coordinates of a 3D numpy array and creates a vtkPolyData object
    :param coordinates: 3D numpy array of x,y,z coordinates
    :return: vtkPolyData
    """

    points = vtk.vtkPoints()
    cells = vtk.vtkCellArray()
    polydata = vtk.vtkPolyData()

    for k in range(size(coordinates, 0)):
      point = coordinates[k]
      pointId = points.InsertNextPoint(point[:])
      cells.InsertNextCell(1)
      cells.InsertCellPoint(pointId)

    cells.Modified()
    points.Modified()
    polydata.SetPoints(points)
    polydata.SetVerts(cells)

    return polydata

  def extract_points(self, liverNode, point1, refDist, contourThickness):
    points = liverNode.GetPolyData().GetPoints()
    numberOfPoints = liverNode.GetPolyData().GetNumberOfPoints()
    points = np.array([points.GetPoint(i) for i in range(0, numberOfPoints)])
    dist = np.linalg.norm(points - point1, axis=1)
    final_points = points[np.abs(dist - refDist) < contourThickness]
    return final_points

  def distance(self, P1, P2):
    res = ((P1[0] - P2[0]) ** 2 + (P1[1] - P2[1]) ** 2 + (P1[2] - P2[2]) ** 2) ** 0.5
    return res

  def optimized_path(self, coords, start=None):
    """
    This function finds the nearest point to a point
    coords should be a numpy array
    """
    if start is None:
      start = coords[0]
    pass_by = coords
    path = [start]
    pass_by = np.delete(pass_by, 0, axis=0)
    distances = []
    while pass_by.shape[0] > 0:
      nearest = pass_by[np.argmin(np.linalg.norm(path[-1] - pass_by, axis=1))]
      dist = np.linalg.norm(path[-1] - nearest)
      distances.append(dist)
      path.append(nearest)
      pass_by = np.delete(pass_by, np.argwhere(np.all(pass_by == nearest, axis=1)), axis=0)

    return np.asarray(path), np.asarray(distances)

  def normalize_efd3d(self, coeffs, size_invariant=True, return_transformation=False):
    """ This method should be used when the original coordinates don't need to be preserved, for example for allowing
    comparison between polygons of differing sizes. It implements the normalization procedure in Bose, Paromita. The
    encoding and Fourier descriptors of arbitrary curves in 3-dimensional space. Diss. State University System of
    Florida, 2000.
    This function is a modified 3D version from https://github.com/hbldh/pyefd
    """

    # ToDO: check the affidability of this normalization method for 3D points in case you may want to use it for
    #  other purpose

    A = np.array([
      [coeffs[0, 0], coeffs[0, 1], (coeffs[0, 2] * coeffs[0, 5] - coeffs[0, 4] * coeffs[0, 3])],
      [coeffs[0, 2], coeffs[0, 3], (coeffs[0, 1] * coeffs[0, 4] - coeffs[0, 0] * coeffs[0, 5])],
      [coeffs[0, 4], coeffs[0, 5], (coeffs[0, 0] * coeffs[0, 3] - coeffs[0, 1] * coeffs[0, 2])],
    ]
    )

    inv_A = np.linalg.inv(A)
    # print(inv_A)
    ace_new = []
    bdf_new = []
    for n in range(1, coeffs.shape[0] + 1):
      x = inv_A.dot(
        np.array(
          [
            [coeffs[n - 1, 1]],
            [coeffs[n - 1, 3]],
            [coeffs[n - 1, 5]],
          ]
        ).flatten()
      )
      ace_new.append(x)

      y = inv_A.dot(
        np.array(
          [
            [coeffs[n - 1, 0]],
            [coeffs[n - 1, 2]],
            [coeffs[n - 1, 4]],
          ]
        )
      ).flatten()
      bdf_new.append(y)

    ace_array = np.array(ace_new)
    bdf_array = np.array(bdf_new)
    normalized_coeffs = np.vstack(
      (ace_array[:, 0], bdf_array[:, 0], ace_array[:, 1], bdf_array[:, 1], ace_array[:, 2], bdf_array[:, 2])).T
    # print('ace', ace_array)
    # print('bdf', bdf_array)
    # print('result', normalized_coeffs)

    size = np.sqrt(coeffs[0, 0] ** 2 + coeffs[0, 2] ** 2 + coeffs[0, 4] ** 2)
    if size_invariant:
      # Obtain size-invariance by normalizing.
      coeffs /= np.abs(size)

    if return_transformation:
      return coeffs, size
    else:

      return normalized_coeffs

  def elliptic_fourier_descriptors(self,
                                   contour, order=8, normalize=False, return_transformation=False
                                   ):
    """Calculate elliptical Fourier descriptors for a contour.

    Args:
         contour: A numpy.ndarray contour array of size [M x 3].
         order: The order of Fourier coefficients to calculate.
         normalize: If the coefficients should be normalized.
         return_transformation: If the normalization parametres should be returned. Default is False.

    Returns:
        coeffs: A [order x 6]array of Fourier coefficients and optionally the
        transformation parametres scale, psi_1 (rotation) and theta_1(phase)

    This function is a modified 3D version from https://github.com/hbldh/pyefd

    """
    dxyz = np.diff(contour, axis=0)
    dt = np.sqrt((dxyz ** 2).sum(axis=1))
    t = np.concatenate([([0.0]), np.cumsum(dt)])  # Return the cumulative sum of the elements along a given axis

    T = t[-1]

    phi = (2 * np.pi * t) / T

    orders = np.arange(1, order + 1)
    consts = T / (2 * orders * orders * np.pi * np.pi)
    phi = phi * orders.reshape((order, -1))
    d_cos_phi = np.cos(phi[:, 1:]) - np.cos(phi[:, :-1])
    d_sin_phi = np.sin(phi[:, 1:]) - np.sin(phi[:, :-1])
    a = consts * np.sum((dxyz[:, 0] / dt) * d_cos_phi, axis=1)
    b = consts * np.sum((dxyz[:, 0] / dt) * d_sin_phi, axis=1)
    c = consts * np.sum((dxyz[:, 1] / dt) * d_cos_phi, axis=1)
    d = consts * np.sum((dxyz[:, 1] / dt) * d_sin_phi, axis=1)
    e = consts * np.sum((dxyz[:, 2] / dt) * d_cos_phi, axis=1)
    f = consts * np.sum((dxyz[:, 2] / dt) * d_sin_phi, axis=1)

    coeffs = np.concatenate(
      [
        a.reshape((order, 1)),
        b.reshape((order, 1)),
        c.reshape((order, 1)),
        d.reshape((order, 1)),
        e.reshape((order, 1)),
        f.reshape((order, 1))
      ],
      axis=1,
    )

    if normalize:
      coeffs = self.normalize_efd3d(coeffs, return_transformation=return_transformation)
      # print(coeffs)

    return coeffs

  def inverse_transform(self, coeffs, locus=(0, 0, 0), n_coords=12, harmonic=10):
    '''
    Perform an inverse fourier transform to convert the coefficients back into
    spatial coordinates.
    Implements Kuhl and Giardina method of computing the performing the
    transform for a specified number of harmonics. This code is adapted
    from the pyefd module. See the original paper for more detail:
    Kuhl, FP and Giardina, CR (1982). Elliptic Fourier features of a closed
    contour. Computer graphics and image processing, 18(3), 236-258.
    Args:
        coeffs (numpy.ndarray): A numpy array of shape (harmonic, 6)
            representing the four coefficients for each harmonic computed.
        locus (tuple): The x,y,z coordinates of the centroid of the contour being
            generated. Use calculate_dc_coefficients() to generate the correct
            locus for a shape.
        n_coords (int): The number of coordinate pairs to compute. A larger
            value will result in a more complex shape at the expense of
            increased computational time. Defaults to 300.
        harmonics (int): The number of harmonics to be used to generate
            coordinates, defaults to 10. Must be <= coeffs.shape[0]. Supply a
            smaller value to produce coordinates for a more generalized shape.
    Returns:
        numpy.ndarray: A numpy array of shape (harmonics, 6) representing the
        four coefficients for each harmonic computed.

    This function is a modified 3D version from https://github.com/hbldh/pyefd
    '''

    t = np.linspace(0, 1, n_coords).reshape(1, -1)
    n = np.arange(harmonic).reshape(-1, 1)

    xt = (np.matmul(coeffs[:harmonic, 0].reshape(1, -1),
                    np.cos(2. * (n + 1) * np.pi * t)) +
          np.matmul(coeffs[:harmonic, 1].reshape(1, -1),
                    np.sin(2. * (n + 1) * np.pi * t)) +
          locus[0])

    yt = (np.matmul(coeffs[:harmonic, 2].reshape(1, -1),
                    np.cos(2. * (n + 1) * np.pi * t)) +
          np.matmul(coeffs[:harmonic, 3].reshape(1, -1),
                    np.sin(2. * (n + 1) * np.pi * t)) +
          locus[1])

    zt = (np.matmul(coeffs[:harmonic, 4].reshape(1, -1),
                    np.cos(2. * (n + 1) * np.pi * t)) +
          np.matmul(coeffs[:harmonic, 5].reshape(1, -1),
                    np.sin(2. * (n + 1) * np.pi * t)) +
          locus[2])

    reconstruction = np.stack([xt, yt, zt], axis=1)

    return reconstruction

  def calculate_dc_coefficients(self, contour):
    """ Calculate the :math:`A_0`, :math:`C_0` and :math:`E_0` coefficients of the elliptic Fourier series.
     Args
     numpy.ndarray contour: A contour array of size [M x 3]

     Returns:
        The A_0`, C_0, E_0` coefficients

    This function is a modified 3D version from https://github.com/hbldh/pyefd
    """
    dxyz = np.diff(contour, axis=0)
    dt = np.sqrt((dxyz ** 2).sum(axis=1))
    t = np.concatenate([([0.0]), np.cumsum(dt)])
    T = t[-1]

    xi = np.cumsum(dxyz[:, 0]) - (dxyz[:, 0] / dt) * t[1:]
    A0 = (1 / T) * np.sum(((dxyz[:, 0] / (2 * dt)) * np.diff(t ** 2)) + xi * dt)
    delta = np.cumsum(dxyz[:, 1]) - (dxyz[:, 1] / dt) * t[1:]
    C0 = (1 / T) * np.sum(((dxyz[:, 1] / (2 * dt)) * np.diff(t ** 2)) + delta * dt)
    zi = np.cumsum(dxyz[:, 2]) - (dxyz[:, 2] / dt) * t[1:]
    E0 = (1 / T) * np.sum(((dxyz[:, 2] / (2 * dt)) * np.diff(t ** 2)) + zi * dt)

    # Adding those values to the coefficients to make them relate to true origin.
    return contour[0, 0] + A0, contour[0, 1] + C0, contour[0, 2] + E0

  def Nyquist(self, X):
    """
    The total number of harmonics that can be computed for any outline is equal to half of the total number of
    outline coordinates (i.e. the ‘Nyquist frequency’). len(X)=len(Y)=len(Z)
    Args:
        X (list): A list (or numpy array) of x coordinate values.

    Returns:
        int: The nyquist frequency, expressed as a number of harmonics.
    """
    return len(X) // 2

  def FourierPower(self, coeffs, X, threshold=0.9999):
    '''
    Compute the total Fourier power and find the minium number of harmonics
    required to exceed the threshold fraction of the total power (precisely, total energy spectral density).
    This is a good method for identifying the number of harmonics to use to
    describe a polygon. For more details see:
    C. Costa et al. / Postharvest Biology and Technology 54 (2009) 38-47
    Warning:
        The number of coeffs must be >= the nyquist freqency.
    Args:
        coeffs (numpy.ndarray): A numpy array of shape (n, 6) representing the
            four coefficients for each harmonic computed.
        X (list): A list (or numpy array) of x coordinate values.
        threshold (float): The threshold fraction of the total Fourier power,
            the default is 0.9999.
    Returns:
        int: The number of harmonics required to represent the contour above
        the threshold Fourier power.
    '''
    nyquist = self.Nyquist(X)

    totalPower = 0
    currentPower = 0

    for n in range(nyquist):
      totalPower += ((coeffs[n, 0] ** 2) + (coeffs[n, 1] ** 2) +
                     (coeffs[n, 2] ** 2) + (coeffs[n, 3] ** 2) + (coeffs[n, 4] ** 2) + (coeffs[n, 5] ** 2)) / 3

    for i in range(nyquist):
      currentPower += ((coeffs[i, 0] ** 2) + (coeffs[i, 1] ** 2.) +
                       (coeffs[i, 2] ** 2) + (coeffs[i, 3] ** 2.) + (coeffs[i, 4] ** 2) + (coeffs[i, 5] ** 2)) / 3

      if (currentPower / totalPower) > threshold:
        return i + 1

  def compute_simple_pca(self, poly_data_input):
    """
    Computes Principal Component Analysis of a mesh
    :param poly_data_input: compute PCA of this vtkPolyData
    :return: eigenvector which is the direction for the profile of the contour
    """
    x_array = vtk.vtkDoubleArray()
    x_array.SetNumberOfComponents(1)
    x_array.SetName('x')
    y_array = vtk.vtkDoubleArray()
    y_array.SetNumberOfComponents(1)
    y_array.SetName('y')
    z_array = vtk.vtkDoubleArray()
    z_array.SetNumberOfComponents(1)
    z_array.SetName('z')

    for i in range(0, poly_data_input.GetNumberOfPoints()):
      pt = poly_data_input.GetPoint(i)
      x_array.InsertNextValue(pt[0])
      y_array.InsertNextValue(pt[1])
      z_array.InsertNextValue(pt[2])

    table = vtk.vtkTable()
    table.AddColumn(x_array)
    table.AddColumn(y_array)
    table.AddColumn(z_array)

    pca_stats = vtk.vtkPCAStatistics()

    if vtk.VTK_MAJOR_VERSION <= 5:
      pca_stats.SetInput(table)

    else:
      pca_stats.SetInputData(table)

    pca_stats.SetColumnStatus("x", 1)
    pca_stats.SetColumnStatus("y", 1)
    pca_stats.SetColumnStatus("z", 1)

    pca_stats.RequestSelectedColumns()
    pca_stats.SetDeriveOption(True)
    pca_stats.Update()

    eigenvalues = vtk.vtkDoubleArray()
    pca_stats.GetEigenvalues(eigenvalues)
    eigenvector0 = vtk.vtkDoubleArray()
    pca_stats.GetEigenvector(0, eigenvector0)
    eigenvector1 = vtk.vtkDoubleArray()
    pca_stats.GetEigenvector(1, eigenvector1)
    eigenvector2 = vtk.vtkDoubleArray()
    pca_stats.GetEigenvector(2, eigenvector2)

    eigv0 = [0.0, 0.0, 0.0]
    eigv1 = [0.0, 0.0, 0.0]
    eigv2 = [0.0, 0.0, 0.0]

    for i in range(0, 3):
      eigv0[i] = eigenvector0.GetValue(i)
      eigv1[i] = eigenvector1.GetValue(i)
      eigv2[i] = eigenvector2.GetValue(i)

    eigen_dict = {'eigenvalues': eigenvalues, 'eigenvectors': [eigv0, eigv1, eigv2]}

    eigen_vectors = eigen_dict['eigenvectors']
    eigen_vectors_array = np.asarray(eigen_vectors).reshape(3, -1)
    eigenvalues = np.asarray(eigenvalues).reshape(3, -1)
    # cross = np.cross(eigen_vectors_array[0],eigen_vectors_array[1])

    # TODO: It could be better using a cross product as direction contour's profile
    return eigen_vectors_array[1], eigenvalues[0]

  def project_points_to_plane(self, mesh, origin=None, normal=(0, 0, 1)):
    """
    Project points of this mesh to a plane and find the furthest point to the center of mass.
    Return the max pointID
    """

    # Make plane
    normal = normal / np.linalg.norm(normal)  # MUST HAVE MAGNITUDE OF 1
    plane = vtk.vtkPlane()
    plane.SetOrigin(origin)
    plane.SetNormal(normal)
    projPts = vtk.vtkPoints()
    for i in range(mesh.GetNumberOfPoints()):
      currPoint = mesh.GetPoint(i)
      newPoint = np.zeros(3)
      plane.ProjectPoint(currPoint, newPoint)
      projPts.InsertNextPoint(newPoint)

    projPd = vtk.vtkPolyData()
    projPd.SetPoints(projPts)
    projected_array = vtk_to_numpy(projPd.GetPoints().GetData())

    center = vtk.vtkCenterOfMass()
    center.SetInputDataObject(projPd)
    center.Update()
    center = np.array(center.GetCenter())

    distances = np.linalg.norm(projected_array - center, axis=1)
    max_id = distances.argmax()

    return max_id

  def Unordered2orderedPointCloud(self, positions):

    global newpoints
    N = len(positions)
    listpoints = []

    for x in range(int(N / 2) + 1):
      if N % 2 == 0:
        listpoints.append(positions[x])
        listpoints.append(positions[-x])
        newpoints = np.asarray([listpoints[1:-1]]).squeeze()
      else:
        listpoints.append(positions[x])
        listpoints.append(positions[-x])
        newpoints = np.asarray([listpoints[1:]]).squeeze()

    # pointCloud = CreatePolyDataFromCoords(newpoints)
    xSpline = vtk.vtkKochanekSpline()
    ySpline = vtk.vtkKochanekSpline()
    zSpline = vtk.vtkKochanekSpline()

    pointCloud_list = list()
    final_parametric_spline_list = list()
    parametric_spline_list = list()
    source_spline_list = list()
    final_source_spline_list = list()

    for i in range(N):
      if i % 2 == 0:
        pointCloud_list.append(
          self.CreatePolyDataFromCoords(newpoints[i:i + 2, :]))

        # parametric_spline_list.append(spline)
        parametric_spline_list.append(vtk.vtkParametricSpline())
        source_spline_list.append(vtk.vtkParametricFunctionSource())

    for i in range(len(pointCloud_list)):
      parametric_spline_list[i].SetXSpline(xSpline)
      parametric_spline_list[i].SetYSpline(ySpline)
      parametric_spline_list[i].SetZSpline(zSpline)
      parametric_spline_list[i].SetPoints(pointCloud_list[i].GetPoints())
      # print(i)
      final_parametric_spline_list.append(parametric_spline_list[i])

      source_spline_list[i].SetParametricFunction(final_parametric_spline_list[i])
      source_spline_list[i].SetUResolution(20)
      source_spline_list[i].SetVResolution(20)
      source_spline_list[i].SetWResolution(20)
      source_spline_list[i].SetScalarModeToDistance()
      final_source_spline_list.append(source_spline_list[i])
      final_source_spline_list[i].Update()

    appendFilter = vtk.vtkAppendPolyData()
    for i in range(len(pointCloud_list)):
      appendFilter.AddInputData(final_source_spline_list[i].GetOutput())

    appendFilter.Update()

    spline_lines = appendFilter.GetOutput()
    points = spline_lines.GetPoints().GetData()
    points_array = vtk_to_numpy(points)
    # print("Number of points in the mask: {}".format(spline_lines.GetNumberOfPoints()))

    # newNode = slicer.vtkMRMLModelNode()
    # slicer.mrmlScene.AddNode(newNode)
    # newNode.SetName("MaskPoints")
    # newNode.SetAndObservePolyData(spline_lines)
    # display = slicer.vtkMRMLModelDisplayNode()
    # slicer.mrmlScene.AddNode(display)

    return points_array, spline_lines

  def compute_pca(self, poly_data_input, extent, start=0, stop=500, step=1):
    """
    Computes Principal Component Analysis of a mesh
    :param poly_data_input: compute PCA of this vtkPolyData
    :param extent of the line
    :return: eigenvalues, eigenvectors
    """
    x_array = vtk.vtkDoubleArray()
    x_array.SetNumberOfComponents(1)
    x_array.SetName('x')
    y_array = vtk.vtkDoubleArray()
    y_array.SetNumberOfComponents(1)
    y_array.SetName('y')
    z_array = vtk.vtkDoubleArray()
    z_array.SetNumberOfComponents(1)
    z_array.SetName('z')

    points = vtk.vtkPoints()
    for i in range(start, stop, step):
      # print(i)
      pt = poly_data_input.GetPoint(i)
      x_array.InsertNextValue(pt[0])
      y_array.InsertNextValue(pt[1])
      z_array.InsertNextValue(pt[2])
      points.InsertNextPoint(pt)

    # print(points.GetNumberOfPoints())
    polydata = vtk.vtkPolyData()
    polydata.SetPoints(points)

    com = vtk.vtkCenterOfMass()
    com.SetInputData(polydata)
    com.SetUseScalarsAsWeights(False)
    com.Update()
    center = com.GetCenter()

    table = vtk.vtkTable()
    table.AddColumn(x_array)
    table.AddColumn(y_array)
    table.AddColumn(z_array)

    pca_stats = vtk.vtkPCAStatistics()

    if vtk.VTK_MAJOR_VERSION <= 5:
      pca_stats.SetInput(table)

    else:
      pca_stats.SetInputData(table)

    pca_stats.SetColumnStatus("x", 1)
    pca_stats.SetColumnStatus("y", 1)
    pca_stats.SetColumnStatus("z", 1)

    pca_stats.RequestSelectedColumns()
    pca_stats.SetDeriveOption(True)
    pca_stats.Update()

    eigenvalues = vtk.vtkDoubleArray()
    pca_stats.GetEigenvalues(eigenvalues)
    eigenvector0 = vtk.vtkDoubleArray()
    pca_stats.GetEigenvector(0, eigenvector0)
    eigenvector1 = vtk.vtkDoubleArray()
    pca_stats.GetEigenvector(1, eigenvector1)
    eigenvector2 = vtk.vtkDoubleArray()
    pca_stats.GetEigenvector(2, eigenvector2)

    eigv0 = [0.0, 0.0, 0.0]
    eigv1 = [0.0, 0.0, 0.0]
    eigv2 = [0.0, 0.0, 0.0]

    for i in range(0, 3):
      eigv0[i] = eigenvector0.GetValue(i)
      eigv1[i] = eigenvector1.GetValue(i)
      eigv2[i] = eigenvector2.GetValue(i)

    eigen_dict = {'eigenvalues': eigenvalues, 'eigenvectors': [eigv0, eigv1, eigv2], 'center': [center]}

    # create the line
    eigen_vectors = eigen_dict['eigenvectors']
    eigen_vectors_array = np.asarray(eigen_vectors)
    center1 = np.asarray(eigen_dict['center'])
    line = np.vstack((center1 - eigen_vectors_array[0] * extent, center1 + eigen_vectors_array[0] * extent))
    x1 = np.linspace(line[0, 0], line[1, 0], 20)
    y1 = np.linspace(line[0, 1], line[1, 1], 20)
    z1 = np.linspace(line[0, 2], line[1, 2], 20)
    line1 = np.vstack((x1, y1, z1)).T

    result_dict = {'line': line1, 'eigen_vector': eigen_vectors_array[0], 'center': center1}
    # line1, eigen_vectors_array[0], center1

    return result_dict

  def line3D_afterSlopeAverage(self, center, eigen_average, extent):

    line = np.vstack((center - eigen_average * extent, center + eigen_average * extent))
    x1 = np.linspace(line[0, 0], line[1, 0], 50)
    y1 = np.linspace(line[0, 1], line[1, 1], 50)
    z1 = np.linspace(line[0, 2], line[1, 2], 50)
    line1 = np.vstack((x1, y1, z1)).T

    return line1

  def spline_line_fromClosedCurve(self, curveNode, liverModelNode):
    """
    Computes spline lines from a ClosedMarkupCurve
    :param curve: close curve node, curve = slicer.util.getNode("CC")
    :param liverModelNode: liver 3D Model,  liver = slicer.util.getNode("liver")
    :return: points array of the spline lines and the polydata
    """
    global newpoints
    curveNode.SetAndObserveSurfaceConstraintNode(liverModelNode)

    # Step 1: Resample curve
    resampleNumber = 100
    currentPoints = curveNode.GetCurvePointsWorld()
    newPoints = vtk.vtkPoints()
    sampleDist = curveNode.GetCurveLengthWorld() / (resampleNumber - 1)

    closedCurveOption = 1
    curveNode.ResamplePoints(currentPoints, newPoints, sampleDist, closedCurveOption)

    vector = vtk.vtkVector3d()
    pt = [0, 0, 0]
    resampledCurve = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsClosedCurveNode", "resampledCurveOrig")
    for controlPoint in range(0, newPoints.GetNumberOfPoints()):
      newPoints.GetPoint(controlPoint, pt)
      vector[0] = pt[0]
      vector[1] = pt[1]
      vector[2] = pt[2]
      resampledCurve.AddControlPoint(vector)

    resampledCurve.SetDisplayVisibility(False)
    curveNode.SetDisplayVisibility(True)
    # Step 2: REORDER THE RESAMPLED POINTS ID AND CREATE A POLYDATA.
    # This step will split the points IDS in 2 parts in order to correctly apply the knitting algorithm.
    # get the numpy array in order to split the curve id in two section
    markupsPositions = slicer.util.arrayFromMarkupsControlPoints(resampledCurve)
    # markupsPositions = slicer.util.arrayFromMarkupsCurvePoints(resampledCurve)
    N = len(markupsPositions)
    listpoints = []

    if N % 2 == 0:
      for x in range(int(N / 2) + 1):
        listpoints.append(markupsPositions[x])
        listpoints.append(markupsPositions[-x])
        newpoints = np.asarray([listpoints[1:-1]]).squeeze()
    else:
      for x in range(int(N / 2) + 1):
        listpoints.append(markupsPositions[x])
        listpoints.append(markupsPositions[-x])
        newpoints = np.asarray([listpoints[1:]]).squeeze()

    # Step 3: PIECEWISE SPLINE INTERPOLATION
    xSpline = vtk.vtkKochanekSpline()
    ySpline = vtk.vtkKochanekSpline()
    zSpline = vtk.vtkKochanekSpline()

    pointCloud_list = list()
    final_parametric_spline_list = list()
    parametric_spline_list = list()
    source_spline_list = list()
    final_source_spline_list = list()

    for i in range(N):
      if i % 2 == 0:
        pointCloud_list.append(
          self.CreatePolyDataFromCoords(newpoints[i:i + 2, :]))

        # parametric_spline_list.append(spline)
        parametric_spline_list.append(vtk.vtkParametricSpline())
        source_spline_list.append(vtk.vtkParametricFunctionSource())

    for i in range(len(pointCloud_list)):
      parametric_spline_list[i].SetXSpline(xSpline)
      parametric_spline_list[i].SetYSpline(ySpline)
      parametric_spline_list[i].SetZSpline(zSpline)
      parametric_spline_list[i].SetPoints(pointCloud_list[i].GetPoints())
      # print(i)
      final_parametric_spline_list.append(parametric_spline_list[i])

      source_spline_list[i].SetParametricFunction(final_parametric_spline_list[i])
      source_spline_list[i].SetUResolution(20)
      source_spline_list[i].SetVResolution(20)
      source_spline_list[i].SetWResolution(20)
      source_spline_list[i].SetScalarModeToDistance()
      final_source_spline_list.append(source_spline_list[i])
      final_source_spline_list[i].Update()

    appendFilter = vtk.vtkAppendPolyData()
    for i in range(len(pointCloud_list)):
      appendFilter.AddInputData(final_source_spline_list[i].GetOutput())

    appendFilter.Update()

    spline_lines = appendFilter.GetOutput()
    points = spline_lines.GetPoints().GetData()
    points_array = vtk_to_numpy(points)
    print("Number of points in the mask: {}".format(spline_lines.GetNumberOfPoints()))

    return points_array, spline_lines

  def compute_parametrization(self, points, centripetal=True):
    # Length of the points array
    num_points = len(points)

    # Calculate chord lengths
    cds = np.zeros([num_points + 1, 1])
    # cds = [0.0 for _ in range(num_points + 1)]
    cds[-1] = 1.0
    for i in range(1, num_points):
      distance = np.linalg.norm(points[i, :] - points[i - 1, :], ord=2)
      # distance = linalg.point_distance(points[i], points[i - 1])
      cds[i] = np.sqrt(distance) if centripetal else distance

    # Find the total chord length
    d = sum(cds[1:-1])

    # Divide individual chord lengths by the total chord length
    uk = np.zeros([num_points, 1])
    for i in range(num_points):
      uk[i] = sum(cds[0:i + 1]) / d

    return uk

  def compute_averaging_params_surface(self, points, size_u, size_v):
    """
    Compute knot averaging as recommended in The NURBS Book (2nd Edition), pp.366-367
    :param points: surface point arranged in a grid NxNx3
    :param size_u: number of points on the u-direction
    :param size_v: number of points on the v-direction
    :return:
    """
    # finding params in v direction
    size_u, size_v = points.shape[0:2]
    params_v = []
    for u in range(size_u):
      temp = self.compute_parametrization(points[u]).reshape((1, size_v))
      params_v.append(temp)
    params_v = np.concatenate(params_v, 0)
    # finding params in u direction
    params_v = np.mean(params_v, 0)
    params_u = []
    for v in range(size_v):
      temp = self.compute_parametrization(points[:, v]).reshape((size_u, 1))
      params_u.append(temp)
    params_u = np.concatenate(params_u, 1)

    params_u = np.mean(params_u, 1)
    return params_u, params_v

  def evaluate_basis_bezier(self, t, degree):
    """
    Evaluates basis functions
    """

    # Initialize b vector
    b = np.zeros(degree + 1, dtype=np.float64)
    b[0] = 1
    t1 = 1. - t

    for j in range(1, degree + 1):
      saved = 0
      for k in range(0, j):
        temp = b[k]
        b[k] = saved + t1 * temp
        saved = t * temp

      b[j] = saved

    return b

  def fit_bezier_surface(self, points, basis_u, basis_v):
    """
    Given gridded points and basis functions for u and v, find the control points of a Bézier surface,
    using the pseudo inverse formulation
    """
    # Get the basis functions for u and v
    nu = basis_u
    nv = basis_v

    # Calculate the inverse of transpose(nu) * nu
    u_basis_transpose = np.transpose(nu)
    u_basis_product = np.matmul(u_basis_transpose, nu)
    u_basis_inverse = np.linalg.inv(u_basis_product)

    # Calculate ut_u_inv_u by multiplying u_basis_inverse with transpose(nu)
    ut_u_inv_u = np.matmul(u_basis_inverse, u_basis_transpose)

    # Calculate the inverse of transpose(nv) * nv
    v_basis_transpose = np.transpose(nv)
    v_basis_product = np.matmul(v_basis_transpose, nv)
    v_basis_inverse = np.linalg.inv(v_basis_product)

    # Calculate vt_v_inv_v by multiplying nv with v_basis_inverse
    vt_v_inv_v = np.matmul(nv, v_basis_inverse)

    # Initialize a list to store the control points
    cntrl_points = []

    # Use the pseudo inverse formulation to find the control points
    for i in range(3):
      # Get the current dimension of the points
      points_dimension = points[:, :, i]

      # Calculate the product of ut_u_inv_u * points_dimension * vt_v_inv_v
      points_cntrl = np.matmul(np.matmul(ut_u_inv_u, points_dimension), vt_v_inv_v)

      # Add the control points to the list
      cntrl_points.append(points_cntrl)

    # Convert the list to an array
    cntrl_points = np.array(cntrl_points)

    # Transpose the control points to have shape (N, N, 3)
    cntrl_points = np.transpose(cntrl_points, (1, 2, 0))

    return cntrl_points

  def runSurfacefromCurve(self, resectionNode, curveNode, liverModelNode):

    points_array = self.spline_line_fromClosedCurve(curveNode, liverModelNode)

    # create the extent with pca
    splines_poly = points_array[1]
    first_eigen = self.compute_simple_pca(splines_poly)
    extent_pca = 4 * np.sqrt(first_eigen[1])

    sub_pca = [self.compute_pca(points_array[1], extent_pca / 2, start=21 * i, stop=21 * (i + 1)) for i in
               range(50)]

    # convert a list of dictionaries into a dict of list
    sub_pca_dict = {}
    for k, v in [(key, d[key]) for d in sub_pca for key in d]:
      if k not in sub_pca_dict:
        sub_pca_dict[k] = [v]
      else:
        sub_pca_dict[k].append(v)

    eigen_average_center = np.average(np.vstack(sub_pca_dict['eigen_vector'][4:46]), axis=0)

    # TODo: the slops of the superior and inferior part of the point cloud could affect bezier Surface
    # eigen_average_start = np.average(np.vstack(sub_pca_dict['eigen_vector'][:4]), axis=0)
    # eigen_average_end = np.average(np.vstack(sub_pca_dict['eigen_vector'][46:50]), axis=0)

    # ToDO: Review the need for this: maybe check if there is a resampling function for vtk Spline
    center = sub_pca_dict['center']

    organized_data = np.vstack(
      np.array(
        [self.line3D_afterSlopeAverage(center[i], eigen_average_center, extent_pca / 2) for i in
         range(len(center))]))

    points_grid = organized_data.reshape(50, 50, 3)

    bezier_list_u = list()
    bezier_list_v = list()

    # u = self.compute_parametrization(points_grid[:, 0, 0].reshape(len(points_grid[:, 0, 0]), 1))
    # v = self.compute_parametrization(points_grid[0, :, 0].reshape(len(points_grid[0, :, 0]), 1))

    param_surface = self.compute_averaging_params_surface(points_grid, 50, 50)
    u = param_surface[0].reshape(-1, 1)
    v = param_surface[1].reshape(-1, 1)

    # for u direction

    for i in range(u.shape[0]):
      bezier_basis = self.evaluate_basis_bezier(u[i], 3)
      bezier_list_u.append(bezier_basis)

    bezier_basis_u = np.array(bezier_list_u)

    # for v direction

    for i in range(v.shape[0]):
      bezier_basis = self.evaluate_basis_bezier(v[i], 3)
      bezier_list_v.append(bezier_basis)

    bezier_basis_v = np.array(bezier_list_v)

    ctrl_points = self.fit_bezier_surface(points_grid, bezier_basis_u, bezier_basis_v)

    control_points = ctrl_points.reshape(-1, 3)

    points = vtk.vtkPoints()
    #
    for i in range(0, len(control_points)):
      points.InsertNextPoint(control_points[i])

    # BezierNode = slicer.mrmlScene.GetNthNodeByClass(0, "vtkMRMLMarkupsBezierSurfaceNode")
    # Transfer the control points to the resection node
    BezierNode = resectionNode.GetBezierSurfaceNode()
    BezierNode.RemoveAllControlPoints()
    BezierNode.SetControlPointPositionsWorld(points)
    BezierDisplay = BezierNode.GetDisplayNode()
    BezierDisplay.SetGlyphScale(0.0)
    BezierDisplay.VisibilityOn()
    # BezierDisplay.SetClipOut(True)

  def runSurfacefromEFD(self, resectionNode, distanceNode, liverNode):

    point1 = distanceNode.GetNthControlPointPosition(1)
    lenghtText = distanceNode.GetPropertiesLabelText()
    refDist = float(lenghtText.split('m')[0])
    contourThickness = 0.05

    final_points = self.extract_points(liverNode, point1, refDist, contourThickness)

    # Step 2: order the points according the shape of the contour
    optimazing = self.optimized_path(final_points)
    sorted1 = optimazing[0]
    distances = optimazing[1]
    # print("max", np.max(distances))
    # print("distances", distances)

    for i in range(len(distances)):
      if distances[i] > 30:
        max_id = np.argmax(distances)
        sorted1 = sorted1[0:max_id]

    # Step 3: Calculate the harmonics and 3DEF coefficients in frequency space

    nyquist = self.Nyquist(sorted1[:, 0])
    tmpcoeffs = self.elliptic_fourier_descriptors(sorted1, normalize=False, order=nyquist)
    harmonic = self.FourierPower(tmpcoeffs, sorted1[:, 0], threshold=0.9999)
    # print('harmonic', harmonic)
    efd = self.elliptic_fourier_descriptors(sorted1, normalize=False, order=harmonic)

    # Step 4: Reconstruction in 3D space
    coeffs0 = self.calculate_dc_coefficients(sorted1)
    rec = self.inverse_transform(efd, harmonic=harmonic, locus=coeffs0, n_coords=100)
    squeeze_rec = np.squeeze(rec)
    points = squeeze_rec.T

    poly_contour = self.CreatePolyDataFromCoords(points)

    # Step 5: deciding the starting point
    normal = self.compute_simple_pca(poly_contour)
    origin = np.array(poly_contour.GetCenter())
    length = np.array(poly_contour.GetLength())
    origin -= length
    max_id = self.project_points_to_plane(poly_contour, origin=origin, normal=normal[0])

    poly_points = poly_contour.GetPoints().GetData()
    poly_points = vtk_to_numpy(poly_points)

    new_points = poly_points[max_id:]
    last_part = poly_points[0:max_id]
    organizedPoints = np.vstack((new_points, last_part))

    distanceContourPoints = self.CreatePolyDataFromCoords(organizedPoints)

    # Review the need for this: merging points on the same position
    cleanFilter = vtk.vtkCleanPolyData()
    cleanFilter.SetInputData(distanceContourPoints)
    cleanFilter.ConvertPolysToLinesOn()
    cleanFilter.ConvertStripsToPolysOn()
    cleanFilter.PointMergingOn()
    cleanFilter.Update()
    surfaceFilter = vtk.vtkDataSetSurfaceFilter()
    surfaceFilter.SetInputData(cleanFilter.GetOutput())
    surfaceFilter.Update()

    points = surfaceFilter.GetOutput().GetPoints().GetData()
    organizedPoints = vtk_to_numpy(points)

    points_array = self.Unordered2orderedPointCloud(organizedPoints)

    # print('number of points', points_array[0].shape)
    #
    # create the extent
    origin = np.mean(points_array[0], axis=0)
    euclidian_distance = np.linalg.norm(points_array[0] - origin, axis=1)
    extent = np.max(euclidian_distance)

    # create the extent with pca
    splines_poly = points_array[1]
    first_eigen = self.compute_simple_pca(splines_poly)
    extent_pca = 4 * np.sqrt(first_eigen[1])

    sub_pca = [self.compute_pca(points_array[1], extent_pca / 2, start=21 * i, stop=21 * (i + 1)) for i in
               range(50)]

    # convert a list of dictionaries into a dict of list
    sub_pca_dict = {}
    for k, v in [(key, d[key]) for d in sub_pca for key in d]:
      if k not in sub_pca_dict:
        sub_pca_dict[k] = [v]
      else:
        sub_pca_dict[k].append(v)

    eigen_average_center = np.average(np.vstack(sub_pca_dict['eigen_vector'][4:46]), axis=0)

    # TODo: the slops of the superior and inferior part of the point cloud could affect bezier Surface
    eigen_average_start = np.average(np.vstack(sub_pca_dict['eigen_vector'][:4]), axis=0)
    eigen_average_end = np.average(np.vstack(sub_pca_dict['eigen_vector'][46:50]), axis=0)

    # ToDO: Review the need for this: maybe check if there is a resampling function for vtk Spline
    center = sub_pca_dict['center']

    organized_data = np.vstack(
      np.array(
        [self.line3D_afterSlopeAverage(center[i], eigen_average_center, extent_pca / 2) for i in
         range(len(center))]))

    points_grid = organized_data.reshape(50, 50, 3)

    bezier_list_u = list()
    bezier_list_v = list()

    # u = self.compute_parametrization(points_grid[:, 0, 0].reshape(len(points_grid[:, 0, 0]), 1))
    # v = self.compute_parametrization(points_grid[0, :, 0].reshape(len(points_grid[0, :, 0]), 1))

    param_surface = self.compute_averaging_params_surface(points_grid, 50, 50)
    u = param_surface[0].reshape(-1, 1)
    v = param_surface[1].reshape(-1, 1)

    # for u direction

    for i in range(u.shape[0]):
      bezier_basis = self.evaluate_basis_bezier(u[i], 3)
      bezier_list_u.append(bezier_basis)

    bezier_basis_u = np.array(bezier_list_u)

    # for v direction

    for i in range(v.shape[0]):
      bezier_basis = self.evaluate_basis_bezier(v[i], 3)
      bezier_list_v.append(bezier_basis)

    bezier_basis_v = np.array(bezier_list_v)

    ctrl_points = self.fit_bezier_surface(points_grid, bezier_basis_u, bezier_basis_v)

    control_points = ctrl_points.reshape(-1, 3)
    points = vtk.vtkPoints()
    #
    for i in range(0, len(control_points)):
      points.InsertNextPoint(control_points[i])

    # BezierNode = slicer.mrmlScene.GetNthNodeByClass(0, "vtkMRMLMarkupsBezierSurfaceNode")
    # Transfer the control points to the resection node
    BezierNode = resectionNode.GetBezierSurfaceNode()
    BezierNode.RemoveAllControlPoints()
    BezierNode.SetControlPointPositionsWorld(points)
    BezierDisplay = BezierNode.GetDisplayNode()
    BezierDisplay.VisibilityOn()

    # BezierDisplay.SetClipOut(True)

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
    """
    Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear()

  def runTest(self):
    """
    Run as few or as many tests as needed here.
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
    inputVolume = SampleData.downloadSample('LiverVolume000')
    self.delayDisplay('Loaded test data set')

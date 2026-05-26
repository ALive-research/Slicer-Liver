# ==============================================================================
#
#  Distributed under the OSI-approved BSD 3-Clause License.
#
#   Copyright (c) 2021-2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
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

# ruff: noqa: F403, F405  # standard Slicer scripted-module wildcard-import pattern


import os
import logging
import vtk
import qt
import slicer
from vtk.util.numpy_support import vtk_to_numpy
from slicer.ScriptedLoadableModule import *
import numpy as np
from numpy import size
import VascularTerritories
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

    self.parent.dependencies = ["LiverResections", "LiverMarkups", "VascularTerritories"]

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
    self._uiLoader = qt.QUiLoader()
    self._currentResectionNode = None
    self.numComps = 0
    self._distanceContourNode = None
    self._preprocessedLiverNode = None
    # Liver-shell sidebar (ADR-0023 Option H) — populated in
    # ``_buildShellSidebar`` from ``setup()``.  Kept ``None`` here so
    # any pre-setup call to ``_refreshStageIndicators`` short-circuits
    # cleanly instead of NPE'ing.
    self._stageSidebar = None
    self._contentStack = None
    self._stagePages = []
    self._shellHost = None
    self._injectedStageCompletion = None

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
    iconStyle = f"QCheckBox::indicator:unchecked {{ image: url({iconsPath}/SlicerInvisible.png);}}\n QCheckBox::indicator:checked {{ image: url({iconsPath}/SlicerVisible.png);}}"
    self.resectogramWidget.Grid2DVisibility.setStyleSheet(iconStyle)
    self.resectionsWidget.Grid3DVisibility.setStyleSheet(iconStyle)

    # Add VascularTerritoriesWidget
    wrapperWidget = slicer.qMRMLWidget()
    widgetLayout = qt.QVBoxLayout()
    margins = qt.QMargins(0,0,0,0)
    widgetLayout.setContentsMargins(margins)
    wrapperWidget.setLayout(widgetLayout)

    wrapperWidget.setMRMLScene(slicer.mrmlScene)
    territoriesWidget = VascularTerritories.VascularTerritoriesWidget(wrapperWidget)
    territoriesWidget.setup()
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
    self.resectionsWidget.TotalMarginLabel.setText(f'{resection + uncertainty:.2f} mm')

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

  # ------------------------------------------------------------------ #
  # Liver-shell sidebar — composition + navigation (ADR-0023 Option H)
  #
  # Six stages, each one row in a QListWidget driving a QStackedWidget:
  #
  #   0  Case Setup            (shell-owned)
  #   1  Anatomy Definition    (LiverSegmentation widgetRepresentation;
  #                             gated on issue #409 — disabled until then)
  #   2  Vascular Territories  (VascularTerritories widgetRepresentation)
  #   3  Resection Planning    (LiverResections widgetRepresentation)
  #   4  Volumetry             (LiverVolumetry widgetRepresentation)
  #   5  Export                (shell-owned)
  #
  # Per-row state-indicator semantics (ADR-0023 §"Shell composition"):
  #   ✓  complete  — stage's IsStageComplete() returns True
  #   ●  current   — sidebar's selected row (overrides 'complete')
  #   ○  pending   — neither complete nor current
  #
  # State source is hybrid (T5.2-d planner §"State source"): each
  # module's logic owns the query; the shell observes scene events via
  # VTKObservationMixin and re-runs every predicate on change.
  # ------------------------------------------------------------------ #

  _STAGE_NAMES = (
    "Case Setup",
    "Anatomy Definition",
    "Vascular Territories",
    "Resection Planning",
    "Volumetry",
    "Export",
  )

  _INDICATOR_COMPLETE = "✓"  # check mark
  _INDICATOR_CURRENT = "●"   # filled circle
  _INDICATOR_PENDING = "○"   # empty circle

  def _buildShellSidebar(self):
    """Construct the vertical-sidebar shell (QListWidget + QStackedWidget).

    Idempotent — calling twice replaces the previous widgets cleanly.
    Stages 2-5 surface the cached widgetRepresentation() of their
    owning Slicer module; stages 1 and 6 host shell-owned placeholders.
    Stage 2 (LiverSegmentation) degrades gracefully when the module is
    absent (issue #409): row disabled-greyed; predicate returns False.
    """
    self._stageSidebar = qt.QListWidget()
    self._stageSidebar.setObjectName("LiverShellStageSidebar")
    self._stageSidebar.setSelectionMode(qt.QAbstractItemView.SingleSelection)

    self._contentStack = qt.QStackedWidget()
    self._contentStack.setObjectName("LiverShellContentStack")

    # Reset the test-time injection bag every time we rebuild.
    self._injectedStageCompletion = None
    # Cached module widget references kept here so the lifetime is the
    # shell's, not the QStackedWidget's child-ownership cycle.
    self._stagePages = []

    for index, name in enumerate(self._STAGE_NAMES):
      page, available = self._resolveStagePage(index)
      self._stagePages.append(page)
      self._contentStack.addWidget(page)

      item = qt.QListWidgetItem(f"{self._INDICATOR_PENDING}  {name}")
      if not available:
        # Greyed-disabled signals "module not registered in this build";
        # see Stage 2 graceful-degradation contract (ADR-0023 §Stage 2).
        item.setFlags(item.flags() & ~qt.Qt.ItemIsEnabled)
      self._stageSidebar.addItem(item)

    self._stageSidebar.connect("currentRowChanged(int)", self._onStageRowChanged)

    # Compose the side-by-side layout.  Keep the sidebar narrow so the
    # surgeon-facing content panel gets the bulk of the screen real
    # estate.  Width tuned to fit the longest stage name at the default
    # Slicer font; surgeons read these labels, not scan them.
    sidebarLayout = qt.QHBoxLayout()
    sidebarLayout.setContentsMargins(0, 0, 0, 0)
    self._stageSidebar.setMinimumWidth(180)
    self._stageSidebar.setMaximumWidth(220)
    sidebarLayout.addWidget(self._stageSidebar)
    sidebarLayout.addWidget(self._contentStack, 1)

    self._shellHost = qt.QWidget()
    self._shellHost.setLayout(sidebarLayout)
    self.layout.addWidget(self._shellHost)

    self._stageSidebar.setCurrentRow(0)
    self._refreshStageIndicators()

  def _resolveStagePage(self, index):
    """Return ``(page_widget, is_available)`` for stage ``index``.

    Stages 1 and 6 return shell-owned placeholders; stages 2-5 return
    the cached ``widgetRepresentation()`` of the matching Slicer
    module, or a "module not available" placeholder when the module
    is not registered.
    """
    if index == 0:
      return self._buildStage1Page(), True
    if index == 5:
      return self._buildStage6Page(), True

    moduleName = {
      1: "liversegmentation",
      2: "vascularterritories",
      3: "liverresections",
      4: "livervolumetry",
    }[index]

    module = getattr(slicer.modules, moduleName, None)
    if module is None or not hasattr(module, "widgetRepresentation"):
      return self._buildUnavailablePage(self._STAGE_NAMES[index]), False

    try:
      rep = module.widgetRepresentation()
    except Exception:  # pragma: no cover — surfaces only on broken module loads
      return self._buildUnavailablePage(self._STAGE_NAMES[index]), False

    if rep is None:
      return self._buildUnavailablePage(self._STAGE_NAMES[index]), False
    return rep, True

  def _buildStage1Page(self):
    """Shell-owned Case Setup placeholder (ADR-0023 §Stage 1 / ADR-0029).

    The functional UI for Stage 1 lands in a follow-up task (planner
    §"Stage 1"); for T5.2-d the shell only reserves the page so the
    sidebar contract is satisfied.
    """
    page = qt.QWidget()
    layout = qt.QVBoxLayout(page)
    layout.addWidget(qt.QLabel("Case Setup — load volumes and tag roles (Stage 1)."))
    layout.addStretch(1)
    return page

  def _buildStage6Page(self):
    """Shell-owned Export placeholder (ADR-0023 §Stage 6).

    Real Export UI lands in a follow-up; T5.2-d ships only the page
    placeholder + the "last write OK" predicate.
    """
    page = qt.QWidget()
    layout = qt.QVBoxLayout(page)
    layout.addWidget(qt.QLabel("Export — save the resection plan to disk (Stage 6)."))
    layout.addStretch(1)
    return page

  def _buildUnavailablePage(self, stageName):
    """Placeholder shown when a stage's owning module is not registered."""
    page = qt.QWidget()
    layout = qt.QVBoxLayout(page)
    layout.addWidget(qt.QLabel(
      f"{stageName} — module not available in this build."
    ))
    layout.addStretch(1)
    return page

  def _onStageRowChanged(self, row):
    """Slot for ``QListWidget.currentRowChanged(int)``.

    Dispatches the content stack to the matching page and refreshes
    the per-row indicators (the 'current' marker tracks selection).
    """
    if 0 <= row < self._contentStack.count():
      self._contentStack.setCurrentIndex(row)
    self._refreshStageIndicators()

  # ------------------------------------------------------------------ #
  # Per-stage IsStageComplete() — hybrid: module logic owns the body,
  # the shell merely queries it.  The shell-owned predicates (Stage 1,
  # Stage 6) live here because there is no companion module to delegate
  # to (per planner §"IsStageComplete() contract per stage").
  # ------------------------------------------------------------------ #

  def _stage1IsComplete(self):
    """Stage 1 — done iff at least one volume carries a ``LiverRole`` attribute.

    ADR-0029 §"Stage 1 functional contract" identifies the per-volume
    role tag as Stage 1's commit signal.  Attribute presence (not
    value) is the gate; the surgeon's eyeball judges correctness.
    """
    scene = slicer.mrmlScene
    volumes = scene.GetNodesByClass("vtkMRMLScalarVolumeNode")
    if volumes is None:
      return False
    for i in range(volumes.GetNumberOfItems()):
      node = volumes.GetItemAsObject(i)
      if node is not None and node.GetAttribute("LiverRole"):
        return True
    return False

  def _stage2IsComplete(self):
    """Stage 2 — graceful-degradation stub while LiverSegmentation is absent.

    Per planner §"Stage 2 stub strategy" (locked decision): the
    LiverSegmentation module is a v2.1 deliverable (#409).  Until it
    lands, the predicate returns ``False`` and the sidebar row is
    disabled-greyed.
    """
    return False

  def _stage6IsComplete(self):
    """Stage 6 — done iff the scene has logged a successful plan write.

    The shell tracks "last write OK" via a scene-level attribute
    (``Liver.Stage6.LastWriteOK``) that the Export sub-widget sets on
    successful serialisation.  Absence is treated as "not written
    yet", consistent with the optimistic semantics described in
    ADR-0023 §"Shell composition (Option H)".
    """
    scene = slicer.mrmlScene
    if scene is None:
      return False
    flag = scene.GetAttribute("Liver.Stage6.LastWriteOK")
    return flag == "True"

  def _stageIsComplete(self, row):
    """Return the completion bool for stage ``row``.

    Routes to the per-stage owner: shell methods for rows 0/5,
    module-logic ``IsStageComplete()`` for rows 1-4.  Test mode
    short-circuits via ``_injectedStageCompletion`` (set by
    ``_injectStageCompletionForTesting``).
    """
    injected = getattr(self, "_injectedStageCompletion", None)
    if injected is not None and 0 <= row < len(injected):
      return bool(injected[row])

    if row == 0:
      return self._stage1IsComplete()
    if row == 5:
      return self._stage6IsComplete()

    moduleName = {
      1: "liversegmentation",
      2: "vascularterritories",
      3: "liverresections",
      4: "livervolumetry",
    }.get(row)
    if moduleName is None:
      return False

    if row == 1:
      # Stage 2 stub — LiverSegmentation absent in v2.0.
      return self._stage2IsComplete()

    module = getattr(slicer.modules, moduleName, None)
    if module is None:
      return False
    try:
      logic = module.logic()
    except Exception:  # pragma: no cover — defensive
      return False
    if logic is None:
      return False

    # C++ logic exposes ``IsStageComplete`` (VTK convention);
    # Python logic exposes ``isStageComplete`` (Python convention).
    for attr in ("IsStageComplete", "isStageComplete"):
      query = getattr(logic, attr, None)
      if callable(query):
        try:
          return bool(query())
        except Exception:  # pragma: no cover — defensive
          return False
    return False

  def _stageIndicatorState(self, row):
    """Return ``'complete' | 'current' | 'pending'`` for stage ``row``.

    'current' takes precedence over 'complete' so the surgeon always
    sees which stage is active — even if they've revisited a stage
    they previously completed.  Test contract pinned by
    ``test_state_indicators_reflect_isstagecomplete``.
    """
    if self._stageSidebar is not None and self._stageSidebar.currentRow == row:
      return "current"
    if self._stageIsComplete(row):
      return "complete"
    return "pending"

  def _indicatorGlyph(self, state):
    return {
      "complete": self._INDICATOR_COMPLETE,
      "current": self._INDICATOR_CURRENT,
      "pending": self._INDICATOR_PENDING,
    }.get(state, self._INDICATOR_PENDING)

  def _refreshStageIndicators(self):
    """Re-read per-stage completion + repaint the sidebar labels.

    Cheap to call repeatedly; the predicate side-effects (scene
    iteration) are O(scene-size) per stage but happen at human
    interaction rate.
    """
    if self._stageSidebar is None:
      return
    for row in range(self._stageSidebar.count()):
      state = self._stageIndicatorState(row)
      glyph = self._indicatorGlyph(state)
      name = self._STAGE_NAMES[row]
      item = self._stageSidebar.item(row)
      if item is not None:
        item.setText(f"{glyph}  {name}")

  def _injectStageCompletionForTesting(self, pattern):
    """Mock per-stage completion for invariant tests.

    Pinned by ``test_state_indicators_reflect_isstagecomplete``:
    ``pattern`` is a six-element iterable of booleans; the next
    ``_refreshStageIndicators`` call uses it instead of the real
    predicates.  Pass ``None`` to clear.
    """
    if pattern is None:
      self._injectedStageCompletion = None
      return
    self._injectedStageCompletion = [bool(x) for x in pattern]

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
# Re-exported from the sibling ``_LegacyLiverLogic`` module to preserve the
# historical ``Liver.LiverLogic()`` import path while the orphaned compute
# code moves out of the shell.  Full relocation to the per-stage modules
# tracked in issue #437; see ADR-0023 §"Shell composition (Option H)".
from _LegacyLiverLogic import LiverLogic  # noqa: F401,E402



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

  def setUp(self):  # noqa: F811
    slicer.mrmlScene.Clear()

    # Get/create input data
    import SampleData
    registerSampleData()
    SampleData.downloadSample('LiverSegmentation000')
    SampleData.downloadSample('LiverVolume000')
    self.delayDisplay('Loaded test data set')

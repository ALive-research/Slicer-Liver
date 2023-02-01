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
from vtk.util.numpy_support import vtk_to_numpy, numpy_to_vtk
from slicer.ScriptedLoadableModule import *
import numpy as np
from numpy import size
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
        resectionsUI = slicer.util.loadUI(self.resourcePath('UI/ResectionsWidget.ui'))
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
        self.distanceMapsWidget.TumorSegmentSelectorWidget.connect('currentSegmentChanged(QString)',
                                                                   self.onDistanceMapParameterChanged)
        self.distanceMapsWidget.ParenchymaSegmentSelectorWidget.connect('currentSegmentChanged(QString)',
                                                                        self.onDistanceMapParameterChanged)
        self.distanceMapsWidget.SegmentationSelectorComboBox.addAttribute('vtkMRMLScalarVolumeNode', 'DistanceMap',
                                                                          'True')
        self.distanceMapsWidget.OutputDistanceMapNodeComboBox.connect('currentNodeChanged(vtkMRMLNode*)',
                                                                      self.onDistanceMapParameterChanged)
        self.distanceMapsWidget.OutputDistanceMapNodeComboBox.addAttribute('vtkMRMLScalarVolumeNode', 'DistanceMap',
                                                                           'True')
        self.distanceMapsWidget.ComputeDistanceMapsPushButton.connect('clicked(bool)',
                                                                      self.onComputeDistanceMapButtonClicked)
        self.resectionsWidget.CurvedRadioButton.toggled.connect(
            lambda: self.onRadioButtonState(self.resectionsWidget.CurvedRadioButton))
        self.resectionsWidget.FlatRadioButton.toggled.connect(
            lambda: self.onRadioButtonState(self.resectionsWidget.FlatRadioButton))
        self.resectionsWidget.ResectionNodeComboBox.connect('currentNodeChanged(vtkMRMLNode*)',
                                                            self.onResectionNodeChanged)
        self.resectionsWidget.DistanceMapNodeComboBox.connect('currentNodeChanged(vtkMRMLNode*)',
                                                              self.onResectionDistanceMapNodeChanged)
        self.resectionsWidget.DistanceMapNodeComboBox.addAttribute('vtkMRMLScalarVolumeNode', 'DistanceMap', 'True')
        self.resectionsWidget.DistanceMapNodeComboBox.addAttribute('vtkMRMLScalarVolumeNode', 'Computed', 'True')
        self.resectionsWidget.LiverSegmentSelectorWidget.connect('currentSegmentChanged(QString)',
                                                                 self.onResectionLiverModelNodeChanged)
        self.resectionsWidget.LiverSegmentSelectorWidget.connect('currentNodeChanged(vtkMRMLNode*)',
                                                                 self.onResectionLiverSegmentationNodeChanged)
        self.resectionsWidget.ResectionColorPickerButton.connect('colorChanged(QColor)', self.onResectionColorChanged)
        self.resectionsWidget.ResectionOpacityDoubleSlider.connect('valueChanged(double)',
                                                                   self.onResectionOpacityChanged)
        self.resectionsWidget.ResectionOpacityDoubleSpinBox.connect('valueChanged(double)',
                                                                    self.onResectionOpacityChanged)
        self.resectionsWidget.ResectionMarginSpinBox.connect('valueChanged(double)', self.onResectionMarginChanged)
        self.resectionsWidget.ResectionMarginColorPickerButton.connect('colorChanged(QColor)',
                                                                       self.onResectionMarginColorChanged)
        self.resectionsWidget.ResectionGridColorPickerButton.connect('colorChanged(QColor)',
                                                                     self.onResectionGridColorChanged)
        self.resectionsWidget.GridDivisionsDoubleSlider.connect('valueChanged(double)', self.onGridDivisionsChanged)
        self.resectionsWidget.GridThicknessDoubleSlider.connect('valueChanged(double)', self.onGridThicknessChanged)
        self.resectionsWidget.ResectionLockCheckBox.connect('stateChanged(int)', self.onResectionLockChanged)
        self.resectionsWidget.UncertaintyMarginSpinBox.connect('valueChanged(double)', self.onUncertaintyMarginChanged)
        self.resectionsWidget.UncertaintyMarginColorPickerButton.connect('colorChanged(QColor)',
                                                                         self.onUncertaintyMarginColorChanged)
        self.resectionsWidget.UncertaintyMarginComboBox.connect('currentIndexChanged(int)',
                                                                self.onUncertaintyMaginComboBoxChanged)
        self.resectionsWidget.InterpolatedMarginsCheckBox.connect('stateChanged(int)',
                                                                  self.onInterpolatedMarginsChanged)

    def onRadioButtonState(self, rdbutton):

        activeResectionNode = self.resectionsWidget.ResectionNodeComboBox.currentNode()
        segmentationNode = self.resectionsWidget.LiverSegmentSelectorWidget.currentNode()
        parenchymaSegmentId = self.resectionsWidget.LiverSegmentSelectorWidget.currentSegmentID()
        liverNode = segmentationNode.GetClosedSurfaceInternalRepresentation(parenchymaSegmentId)
        lvLogic = slicer.modules.liverresections.logic()
        if liverNode is None:
            segmentationNode.CreateClosedSurfaceRepresentation()
            liverNode = segmentationNode.GetClosedSurfaceInternalRepresentation(parenchymaSegmentId)

        # liverNode = self.logic.preprocessing(segmentationNode, parenchymaSegmentId)
        if rdbutton.isChecked():
            print(rdbutton.text)
            if rdbutton.text == "Curved":
                lvLogic.HideInitializationMarkupFromResection(activeResectionNode)
                liverNode = activeResectionNode.GetTargetOrganModelNode()
                activeResectionNode.SetInitMode(activeResectionNode.Curved)
                activeResectionNode.SetTargetOrganModelNode(liverNode)
                lvLogic.AddResectionContour(activeResectionNode)
                distanceContourNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLMarkupsDistanceContourNode")
                liverPolyData = liverNode.GetPolyData()
                preprocessedliverNode = self.logic.preprocessing(liverPolyData)
                distanceContourNode.AddObserver(slicer.vtkMRMLMarkupsNode.PointEndInteractionEvent,
                                                lambda x, y: self.logic.runSurfacefromEFD(distanceContourNode, preprocessedliverNode))
                distanceContourNode.AddObserver(slicer.vtkMRMLMarkupsNode.PointModifiedEvent,
                                                self.onDistanceContourStartInteraction)
                # self.logic.runSurfacefromEFD(distanceContourNode, preprocessedliverNode)

            else:
                return

    def onDistanceMapParameterChanged(self):
        """
    This function is triggered whenever any parameter of the distance maps are changed
    """

        node1 = self.distanceMapsWidget.TumorSegmentSelectorWidget.currentNode()
        node2 = self.distanceMapsWidget.ParenchymaSegmentSelectorWidget.currentNode()
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

                self.resectionsWidget.LiverSegmentSelectorWidget.blockSignals(True)
                self.resectionsWidget.LiverSegmentSelectorWidget.setCurrentNode(None)
                self.resectionsWidget.LiverSegmentSelectorWidget.blockSignals(False)

                self.resectionsWidget.DistanceMapNodeComboBox.blockSignals(True)
                self.resectionsWidget.DistanceMapNodeComboBox.setCurrentNode(
                    activeResectionNode.GetDistanceMapVolumeNode())
                self.resectionsWidget.DistanceMapNodeComboBox.blockSignals(False)

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

                if activeResectionNode.GetState() == activeResectionNode.Initialization:  # Show initialization
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

        self._currentResectionNode = activeResectionNode

    def onResectionDistanceMapNodeChanged(self):
        """
    This function is called when the resection distance map selector changes
    """
        if self._currentResectionNode is not None:
            distanceMapNode = self.resectionsWidget.DistanceMapNodeComboBox.currentNode()
            self._currentResectionNode.SetDistanceMapVolumeNode(
                self.resectionsWidget.DistanceMapNodeComboBox.currentNode())
            self.resectionsWidget.ResectionMarginGroupBox.setEnabled(distanceMapNode is not None)
            self.resectionsWidget.UncertaintyMarginGroupBox.setEnabled(distanceMapNode is not None)
            self.resectionsWidget.ResectionPreviewGroupBox.setEnabled(distanceMapNode is not None)

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
            
    def onDistanceContourStartInteraction(self, caller, event):
        lvLogic = slicer.modules.liverresections.logic()
        lvLogic.HideBezierSurfaceMarkupFromResection(self._currentResectionNode)
        # self.observedBezierNode.GetDisplayNode().VisibilityOff()
        # node = slicer.util.getNode("MarkupsBezierSurface")
        # node.GetDisplayNode().VisibilityOff()
        # print(" Also This function is ok")

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
        segmentationIds = vtk.vtkStringArray()

        """
    Export labelmaps volumes for the selected segmentations
    """
        tumorLabelmapVolumeNode = slicer.mrmlScene.GetFirstNodeByName("TumorLabelMap")
        if not tumorLabelmapVolumeNode:
            tumorLabelmapVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", "TumorLabelMap")
        parenchymaLabelmapVolumeNode = slicer.mrmlScene.GetFirstNodeByName("ParenchymaLabelMap")
        if not parenchymaLabelmapVolumeNode:
            parenchymaLabelmapVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode",
                                                                              "ParenchymaLabelMap")

        segmentationIds.Initialize()
        segmentationIds.InsertNextValue(tumorSegmentId)
        slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(segmentationNode, segmentationIds,
                                                                          tumorLabelmapVolumeNode, refVolumeNode)
        segmentationIds.Initialize()
        segmentationIds.InsertNextValue(parenchymaSegmentId)
        slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(segmentationNode, segmentationIds,
                                                                          parenchymaLabelmapVolumeNode, refVolumeNode)

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

        self.logic.computeDistanceMaps(tumorLabelmapVolumeNode, parenchymaLabelmapVolumeNode, outputVolumeNode)
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
            tumorDistanceImage = sitk.SignedMaurerDistanceMap(tumorImage, False, False, True)
            logging.debug("Computing Tumor Distance Map...")

            # Compute tumor distance map
            parenchymaImage = sitkUtils.PullVolumeFromSlicer(parenchymaNode)
            parenchymaDistanceImage = sitk.SignedMaurerDistanceMap(parenchymaImage, False, False, True)
            logging.debug("Computing Parenchyma Distance Map...")

            # Combine distance maps
            compositeDistanceMap = sitk.Compose(tumorDistanceImage, parenchymaDistanceImage)
            sitkUtils.PushVolumeToSlicer(compositeDistanceMap, targetNode=outputNode,
                                         className='vtkMRMLVectorVolumeNode')
            outputNode.SetAttribute('DistanceMap', "True");
            outputNode.SetAttribute('Computed', "True");

    def preprocessing(self, modelPolyData, subdivide=True):

        modelPolyDataCopy = vtk.vtkPolyData()
        modelPolyDataCopy.DeepCopy(modelPolyData)
        modelNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelNode')
        modelNode.CreateDefaultDisplayNodes()
        modelDisplayNode = modelNode.GetDisplayNode()
        modelDisplayNode.SetOpacity(0.2)
        modelDisplayNode.Visibility3DOff()
        modelNode.SetAndObservePolyData(modelPolyDataCopy)
        print(modelNode)

        # subdivision filter
        # new steps for preparation to avoid problems because of connectivity
        if subdivide:
            smooth_loop = vtk.vtkLoopSubdivisionFilter()
            smooth_loop.SetNumberOfSubdivisions(1)
            smooth_loop.SetInputData(modelNode.GetPolyData())
            smooth_loop.Update()
            # liverModelNode.RemoveAllObservers()
            modelNode.SetAndObservePolyData(smooth_loop.GetOutput())
            if smooth_loop.GetOutput().GetNumberOfPoints() == 0:
                logging.warning("Mesh subdivision failed. Skip subdivision step.")
                subdivide = False
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

    def dist3D(self, firstPoint, secPoint):
        sumSq = np.sum(np.square(firstPoint - secPoint))
        return np.sqrt(sumSq)

    def findVectorBetweenTwo3DPoints(self, point1, point2, unitSphere=True):
        finalVector = point2 - point1
        if unitSphere:
            totalDist = self.dist3D(point1, point2)
            unitVector = np.divide(finalVector, totalDist)
            return unitVector

        else:

            return finalVector

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
        # cross = np.cross(eigen_vectors_array[0],eigen_vectors_array[1])

        # TODO: It could be better using a cross product as direction contour's profile
        return eigen_vectors_array[1]

    def project_points_to_plane(self, mesh, origin=None, normal=(0, 0, 1)):
        """Project points of this mesh to a plane and find the furthest point to the center of mass.
            Return the max pointID"""

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

    def runSurfacefromEFD(self, distanceNode, liverNode):

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
            if distances[i] > 20:
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
        rec = self.inverse_transform(efd, harmonic=harmonic, locus=coeffs0, n_coords=80)
        squeeze_rec = np.squeeze(rec)
        points = squeeze_rec.T

        poly_contour = self.CreatePolyDataFromCoords(points)

        # Step 5: deciding the starting point
        normal = self.compute_simple_pca(poly_contour)
        origin = np.array(poly_contour.GetCenter())
        length = np.array(poly_contour.GetLength())
        origin -= length
        max_id = self.project_points_to_plane(poly_contour, origin=origin, normal=normal)

        poly_points = poly_contour.GetPoints().GetData()
        poly_points = vtk_to_numpy(poly_points)

        new_points = poly_points[max_id:]
        last_part = poly_points[0:max_id]
        organizedPoints = np.vstack((new_points, last_part))

        distanceContourPoints = self.CreatePolyDataFromCoords(organizedPoints)

        # Display node
        if slicer.mrmlScene.GetFirstNodeByName("DistanceContour") is not None:
            node = slicer.util.getNode("DistanceContour")
            slicer.mrmlScene.RemoveNode(node)
        else:
            modelNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelNode')
            modelNode.SetName("DistanceContour")
            modelNode.CreateDefaultDisplayNodes()
            modelDisplayNode = modelNode.GetDisplayNode()
            modelDisplayNode.SetOpacity(0.5)
            modelDisplayNode.SetRepresentation(0)
            modelDisplayNode.SetPointSize(5)
            modelDisplayNode.VisibilityOff()
            modelNode.SetAndObservePolyData(distanceContourPoints)



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
        inputVolume = SampleData.downloadSample('LiverVolume000')
        self.delayDisplay('Loaded test data set')


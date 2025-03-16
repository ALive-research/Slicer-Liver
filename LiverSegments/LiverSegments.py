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
#   This file was originally developed by Ole V. Solberg, Geir A. Tangen, Javier
#   Perez-de-Frutos (SINTEF, Norway) and Rafael Palomar (Oslo University
#   Hospital) through the ALive project (grant nr. 311393).
#
# ==============================================================================

import os
import unittest
import logging
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin

#
# LiverSegments
#

class LiverSegments(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Extract Vascular segments"
    self.parent.categories = [""]
    self.parent.dependencies = []
    self.parent.contributors = ["Ole Vegard Solberg (SINTEF)",
                                "Geir Arne Tangen (SINTEF)",
                                "Rafael Palomar (OUS)",
                                "Javier Pérez de Frutos (SINTEF)"]
    self.parent.helpText = """
    This module provides tools and functionality for extracting vascular liver segments from 3D liver models.
    """
    self.parent.acknowledgementText = """
    """  # TODO: replace with organization, grant and thanks.

    # Additional initialization step after application startup is complete
    #slicer.app.connect("startupCompleted()", registerSampleData)

    #Hide module, so that it only shows up in the Liver module, and not as a separate module
    parent.hidden = True

#
# Register sample data sets in Sample Data module
#

class LiverSegmentsWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent=None):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    self.logic = None
    self._parameterNode = None
    self._updatingGUIFromParameterNode = False
    self._updatingGUIFromSegmentationNode = False
    ScriptedLoadableModuleWidget.__init__(self, parent)
    VTKObservationMixin.__init__(self)  # needed for parameter node observation

  def setup(self):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.setup(self)

    # Load widget from .ui file (created by Qt Designer)
    uiWidget = slicer.util.loadUI(self.resourcePath('UI/LiverSegments.ui'))
    self.layout.addWidget(uiWidget)

    # Add a spacer at the botton to keep the UI flowing from top to bottom
    spacerItem = qt.QSpacerItem(0,0, qt.QSizePolicy.Minimum, qt.QSizePolicy.MinimumExpanding)
    self.layout.addSpacerItem(spacerItem)

    self.ui = slicer.util.childWidgetVariables(uiWidget)

    self.nodeSelectors = [
        (self.ui.inputSurfaceSelector, "InputSurface"),
        (self.ui.endPointsMarkupsSelector, "CenterlineSegment"),
        (self.ui.selectedVascularTerritorySegmId, "VascularTerritorySegmentation")
        ]

    # Set scene in MRML widgets. Make sure that in Qt designer
    # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
    # "setMRMLScene(vtkMRMLScene*)" slot.
    uiWidget.setMRMLScene(slicer.mrmlScene)

    # Create logic class. Logic implements all computations that should be possible to run
    # in batch mode, without a graphical user interface.
    self.logic = LiverSegmentsLogic()
#    self.ui.parameterNodeSelector.addAttribute("vtkMRMLScriptedModuleNode", "ModuleName", self.moduleName)
    self.setParameterNode(self.logic.getParameterNode())

    # Copy color map
    self.createColorMap()

    # Connections
    self.ui.inputSurfaceSelector.connect('currentNodeChanged(bool)', self.updateParameterNodeFromGUI)
    self.ui.inputSegmentSelectorWidget.connect('currentSegmentChanged(QString)', self.updateParameterNodeFromGUI)
    self.ui.inputSegmentSelectorWidget.connect('currentSegmentChanged(QString)', self.onSegmentChanged)
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)
    self.ui.endPointsMarkupsSelector.connect('nodeAddedByUser(vtkMRMLNode*)', self.newEndpointsListCreated)
    #self.ui.endPointsMarkupsSelector.connect('nodeAdded(vtkMRMLNode*)', self.newEndpointsListCreated)
    self.ui.inputSurfaceSelector.connect('currentNodeChanged(bool)', self.segmentationNodeSelected)
    self.ui.vascularTerritoryId.connect('currentIndexChanged(int)', self.onVascularTerritoryIdChanged)
    self.ui.selectedVascularTerritorySegmId.connect('currentNodeChanged(bool)', self.updateParameterNodeFromGUI)
    self.ui.selectedVascularTerritorySegmId.connect('currentNodeChanged(bool)', self.vascular_territory_segmentationNodeSelected)

    self.ui.selectedVascularTerritorySegmId.setNodeTypeLabel('Vascular Territory Segmentation', 'vtkMRMLSegmentationNode')
    self.ui.selectedVascularTerritorySegmId.addAttribute("vtkMRMLSegmentationNode", "LiverSegments.SegmentationId")

    #self.onVascularTerritoryIdChanged()
    #self.ui.endPointsMarkupsSelector.setEnabled(False)#Disable selector for now, as the lists are automatically managed

    # Initialize Vascular Territory Segmentation button at widget start-up
#    nodeNameID = 'Vascular_Territory_Segmentation'
#    vasc_terr_segm_node = slicer.mrmlScene.GetNodeByID(nodeNameID)
#    if not vasc_terr_segm_node:
#      vasc_terr_segm_node = slicer.mrmlScene.AddNewNodeByClassWithID('vtkMRMLSegmentationNode', nodeNameID, nodeNameID)
#    self.ui.selectedVascularTerritorySegmId.setCurrentNodeID(nodeNameID)

    #TODO: Store all GUI settings
    # These connections ensure that whenever user changes some settings on the GUI, that is saved in the MRML scene
    # (in the selected parameter node).
    #        self.ui.inputSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)

    # Buttons
    self.ui.calculateVascularTerritoryMapButton.connect('clicked(bool)', self.onCalculateVascularTerritoryMapButton)
    self.ui.addCenterlineSegmentButton.connect('clicked(bool)', self.onAddCenterlineButton)
    self.ui.addSegmentationButton.connect('clicked(bool)', self.onAddSegmentationButton)
    self.ui.ColorPickerButton.connect('colorChanged(QColor)', self.onColorChanged)
    self.ui.showHideButton.connect('clicked(bool)', self.onShowHideButton)

    #self.enableWidgetButtons(False)
    # Make sure parameter node is initialized (needed for module reload)
    self.initializeParameterNode()

  def enableWidgetButtons(self, state):
    self.ui.addSegmentationButton.setEnabled(state)
    self.ui.addCenterlineSegmentButton.setEnabled(state)
    self.ui.calculateVascularTerritoryMapButton.setEnabled(state)
    self.ui.inputSurfaceSelector.setEnabled(state)
    self.ui.vascularTerritoryId.setEnabled(state)
    self.ui.endPointsMarkupsSelector.setEnabled(state)
    self.ui.showHideButton.setEnabled(state)

  def segmentationNodeSelected(self):
    self.ui.SegmentationShow3DButton.setEnabled(True)
    segmentationNode = self.ui.inputSurfaceSelector.currentNode()
    self.ui.SegmentationShow3DButton.setSegmentationNode(segmentationNode)
    if segmentationNode is None:
      logging.warning('No segmentationNode')
      return
    displayNode = segmentationNode.GetDisplayNode()
    displayNode.SetOpacity3D(0.3)
    self.updateShowHideButtonText()

  #Auto create if name/id don't exist. Auto switch if it exists
  def onSegmentChanged(self):
    endPointsMarkupsNode = self.ui.endPointsMarkupsSelector.currentNode()
    if endPointsMarkupsNode is not None:
      endPointsMarkupsNode.SetDisplayVisibility(False)#Hide previous markup points
    if self.ui.inputSurfaceSelector.currentNode() is None:
      return
    if not self.ui.inputSegmentSelectorWidget.currentSegmentID():
      return
    #Check if this is a Vascular Territory Segmentation node
    segmentationNodeAttribute = self.ui.inputSurfaceSelector.currentNode().GetAttribute("LiverSegments.SegmentationId")
    if segmentationNodeAttribute is not None:
      return

    VascSegmIdno = self.ui.selectedVascularTerritorySegmId.currentNode().GetAttribute("LiverSegments.SegmentationId")
    VascTerrIdno = self.ui.vascularTerritoryId.currentIndex
    vesselPointsSelector = self.ui.endPointsMarkupsSelector
    vesselPointsSelector.blockSignals(True)
    vesselPointsSelector.addAttribute("vtkMRMLMarkupsFiducialNode", "LiverSegments.VascTerrId", str(VascTerrIdno))
    vesselPointsSelector.addAttribute("vtkMRMLMarkupsFiducialNode", "LiverSegments.SegmentationId", str(VascSegmIdno))
    vesselPointsSelector.blockSignals(False)

    endPointsMarkupsNode = self.getVesselSegmentfromName()
    if endPointsMarkupsNode is None:
      endPointsMarkupsNode = self.ui.endPointsMarkupsSelector.addNode()
      self.ui.endPointsMarkupsSelector.setCurrentNode(endPointsMarkupsNode)
#    else:
    endPointsMarkupsNode.SetAttribute("LiverSegments.SegmentationId",str(VascSegmIdno))
    endPointsMarkupsNode.SetAttribute("LiverSegments.VascTerrId",str(VascTerrIdno))
#    endPointsMarkupsNode.addAttribute("vtkMRMLMarkupsFiducialNode", "LiverSegments.SegmentationId",str(Idno))

    self.ui.endPointsMarkupsSelector.baseName = self.getVesselSegmentName()
    self.refreshShowHideButton()
    endPointsMarkupsNode.SetDisplayVisibility(True)#Show current markup points

  def onShowHideButton(self):
    displayNode, segmentId = self.getDisplayNodeAndSegmentId()
    if displayNode is None:
      return
    if self.ui.showHideButton.isChecked() is True:
      displayNode.SetSegmentVisibility(segmentId, True)
    else:
      displayNode.SetSegmentVisibility(segmentId, False)
    self.updateShowHideButtonText()

  def refreshShowHideButton(self):
    displayNode, segmentId = self.getDisplayNodeAndSegmentId()
    if displayNode is None:
      return
    self.ui.showHideButton.setChecked(displayNode.GetSegmentVisibility(segmentId))
    self.updateShowHideButtonText()

  def getDisplayNodeAndSegmentId(self):
    surface = self.ui.inputSurfaceSelector.currentNode()
    if surface is None:
      return None, None
    displayNode = surface.GetDisplayNode()
    if displayNode is None:
      return None, None
    return displayNode, self.ui.inputSegmentSelectorWidget.currentSegmentID()

  def updateShowHideButtonText(self):
    if self.ui.showHideButton.isChecked() is True:
      self.ui.showHideButton.setText('Hide')
      self.ui.showHideButton.setIcon(qt.QIcon("Icons/VisibleOn.png"))
    else:
      self.ui.showHideButton.setText('Show')
      self.ui.showHideButton.setIcon(qt.QIcon("Icons/VisibleOff.png"))

  def vascular_territory_segmentationNodeSelected(self):
    self._updatingGUIFromSegmentationNode = True
    count = self.ui.selectedVascularTerritorySegmId.nodeCount()
    if count <= 0:
      self.enableWidgetButtons(False)
      self._updatingGUIFromSegmentationNode = False
      return
    else:
      self.enableWidgetButtons(True)

    segmId = self.ui.selectedVascularTerritorySegmId.currentNode().GetAttribute("LiverSegments.SegmentationId")

    vasc_terr_segmentationNode = self.ui.selectedVascularTerritorySegmId.currentNode()
    vascularTerrSegm = vasc_terr_segmentationNode.GetSegmentation()

    if vasc_terr_segmentationNode is None:
      logging.warning('No vascular territory segmentationNode')
      self._updatingGUIFromSegmentationNode = False
      return
    if not segmId:
      segmId = count
      firstSegmentID = 'Vascular Territory ID 1'
      vascularTerrSegm.AddEmptySegment(firstSegmentID, firstSegmentID)

    vasc_terr_segmentationNode.SetAttribute("LiverSegments.SegmentationId", str(segmId))

    segmentationNodeName = vasc_terr_segmentationNode.GetName()
    vasc_terr_ID_combox = self.ui.vascularTerritoryId

    if 'Vascular_Territory_Segmentation' in segmentationNodeName:
      self.enableWidgetButtons(True)
    else:
      self.enableWidgetButtons(False)

    self.updateVascTerrList(vasc_terr_ID_combox, vasc_terr_segmentationNode)
    self.ui.vascularTerritoryId.setCurrentIndex(1)
    displayNode = vasc_terr_segmentationNode.GetDisplayNode()
    if displayNode:
      displayNode.SetOpacity3D(0.3)
    self.updateShowHideButtonText()
    # Visualisation of centerline segments
    centerlineSegments = slicer.util.getNodesByClass('vtkMRMLModelNode')
    for centerlineSegment in centerlineSegments:
      SegmIdAttribute = centerlineSegment.GetAttribute("LiverSegments.SegmentationId")
      if SegmIdAttribute == segmId:
        centerlineSegment.GetDisplayNode().VisibilityOn()
      else:
        centerlineSegment.GetDisplayNode().VisibilityOff()
    # Visualisation of Vascular Territories
    segmentationNodes = slicer.util.getNodesByClass('vtkMRMLSegmentationNode')
    self._updatingGUIFromSegmentationNode = False
    for node in segmentationNodes:
      attribute = node.GetAttribute("LiverSegments.SegmentationId")
      if attribute != None:
        if node.GetDisplayNode():
          node.GetDisplayNode().SetAllSegmentsVisibility(False)
    self.ui.endPointsMarkupsPlaceWidget.setPlaceModeEnabled(False)


  def updateVascTerrList(self, vasc_terr_ID_list, vascular_territory_segm_node):
    segmentNames = []
    segmentIds = vascular_territory_segm_node.GetSegmentation().GetSegmentIDs()
    for id in segmentIds:
      segmentName = vascular_territory_segm_node.GetSegmentation().GetSegment(id).GetName()
      segmentNames.append(segmentName)

    vasc_terr_ID_list.blockSignals(True)
    vasc_terr_ID_list.clear()
    initString = 'Create new territory ID'
    vasc_terr_ID_list.addItem(initString)
    firstSegmentName = 'Vascular Territory ID 1'
    if firstSegmentName not in segmentNames:
      # No vascular territory segmentations
      return
    #Start populating Vascular Territory list
    index = 0
    for nameString in segmentNames:
      index = index+1
      vasc_terr_ID_list.addItem(nameString)
      self.colormap.SetColorName(index, nameString)
      vasc_terr_ID_list.setCurrentIndex(index)
      self.onSegmentChanged()
    vasc_terr_ID_list.setCurrentIndex(1)
    vasc_terr_ID_list.blockSignals(False)

  def getVesselSegmentfromName(self):
    segmentName = self.getVesselSegmentName()
    for i in range(self.ui.endPointsMarkupsSelector.nodeCount()):
      node = self.ui.endPointsMarkupsSelector.nodeFromIndex(i)
      if segmentName == node.GetName():
        self.ui.endPointsMarkupsSelector.setCurrentNode(node)
        return self.ui.endPointsMarkupsSelector.currentNode()
    logging.info('Found no node called: ' + segmentName)
    return None

  def createColorMap(self):
#    colorTableNodes = slicer.util.getNodes("SlicerLiverColorMap*")
#    if len(colorTableNodes) == 0:
    logging.info('Load color map from file')
    # Load the node from disk
    p = os.path.join(os.path.dirname(os.path.realpath(__file__)), "Resources/SlicerLiverColorMap.ctbl")
    self.colormap = slicer.modules.colors.logic().LoadColorFile(p)
#      slicer.mrmlScene.AddNode(self.colormap) # Creates the ID #Needed?
#    else:
#      self.colormap = list(colorTableNodes.values())[0] #else not needed?

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
    self.initializeParameterNode()

  def initializeParameterNode(self):
    """
    Ensure parameter node exists and observed.
    """
    # Parameter node stores all user choices in parameter values, node selections, etc.
    # so that when the scene is saved and reloaded, these settings are restored.

    self.setParameterNode(self.logic.getParameterNode())

  def setParameterNode(self, inputParameterNode):
    """
    Set and observe parameter node.
    Observation is needed because when the parameter node is changed then the GUI must be updated immediately.
    """
    if inputParameterNode:
      self.logic.setDefaultParameters(inputParameterNode)

    if inputParameterNode == self._parameterNode:
      # No change
      return

    # Unobserve previously selected parameter node and add an observer to the newly selected.
    # Changes of parameter node are observed so that whenever parameters are changed by a script or any other module
    # those are reflected immediately in the GUI.
    if self._parameterNode is not None:
      self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)
    if self._parameterNode is not None:
      self.addObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)
    self._parameterNode = inputParameterNode

    # Initial GUI update
    self.updateGUIFromParameterNode()

  def updateGUIFromParameterNode(self, caller=None, event=None):
    """
    This method is called whenever parameter node is changed.
    The module GUI is updated to show the current state of the parameter node.
    """

    # Disable all sections if no parameternode is selected
    parameterNode = self._parameterNode
    if not slicer.mrmlScene.IsNodePresent(parameterNode):
        parameterNode = None
    self.ui.segmentsCollapsibleButton.enabled = parameterNode is not None
    if parameterNode is None:
        return

    if self._parameterNode is None or self._updatingGUIFromParameterNode:
      return

    # Make sure GUI changes do not call updateParameterNodeFromGUI (it could cause infinite loop)
    self._updatingGUIFromParameterNode = True

    # Update node selectors and sliders
    for nodeSelector, roleName in self.nodeSelectors:
        nodeSelector.setCurrentNode(self._parameterNode.GetNodeReference(roleName))
    inputSurfaceNode = self._parameterNode.GetNodeReference("InputSurface")
    if inputSurfaceNode and inputSurfaceNode.IsA("vtkMRMLSegmentationNode"):
        self.ui.inputSegmentSelectorWidget.setCurrentSegmentID(self._parameterNode.GetParameter("InputSegmentID"))
    vascularTerritorySegmNode = self._parameterNode.GetNodeReference("VascularTerritorySegmentation")
    if vascularTerritorySegmNode and vascularTerritorySegmNode.IsA("vtkMRMLSegmentationNode"):
        self.enableWidgetButtons(True)

    # All the GUI updates are done
    self._updatingGUIFromParameterNode = False

  def updateParameterNodeFromGUI(self, caller=None, event=None):
    """
    This method is called when the user makes any change in the GUI.
    The changes are saved into the parameter node (so that they are restored when the scene is saved and loaded).
    """

    if self._parameterNode is None or self._updatingGUIFromParameterNode:
      return

    for nodeSelector, roleName in self.nodeSelectors:
      self._parameterNode.SetNodeReferenceID(roleName, nodeSelector.currentNodeID)

    inputSurfaceNode = self._parameterNode.GetNodeReference("InputSurface")
    if inputSurfaceNode and inputSurfaceNode.IsA("vtkMRMLSegmentationNode"):
        self._parameterNode.SetParameter("InputSegmentID", self.ui.inputSegmentSelectorWidget.currentSegmentID())

    self.ui.inputSegmentSelectorWidget.setCurrentSegmentID(self._parameterNode.GetParameter("InputSegmentID"))
    self.ui.inputSegmentSelectorWidget.setVisible(inputSurfaceNode and inputSurfaceNode.IsA("vtkMRMLSegmentationNode"))

    #    wasModified = self._parameterNode.StartModify()  # Modify all properties in a single batch

    #    self._parameterNode.SetNodeReferenceID("InputVolume", self.ui.inputSelector.currentNodeID)
    #    self._parameterNode.SetNodeReferenceID("OutputVolume", self.ui.outputSelector.currentNodeID)

    #    self._parameterNode.EndModify(wasModified)

  def getPreprocessedPolyData(self):
    surface = self.ui.inputSurfaceSelector.currentNode()
    segmentId = self.ui.inputSegmentSelectorWidget.currentSegmentID()

    inputSurfacePolyData = self.logic.polyDataFromNode(surface, segmentId)
    if not inputSurfacePolyData or inputSurfacePolyData.GetNumberOfPoints() == 0:
        raise ValueError("Valid input surface is required")

    preprocessedPolyData = self.logic.preprocessAndDecimate(inputSurfacePolyData)
    return preprocessedPolyData

  def createCenterlineNode(self, endPointsMarkupsNode):
    nodeName = endPointsMarkupsNode.GetName()
    centerlineModelNode = slicer.mrmlScene.GetNodeByID(nodeName)
    if centerlineModelNode:
      logging.info('Adding to existing centerlineModelNode')
      #slicer.mrmlScene.RemoveNode(centerlineModelNode)
    else:
      centerlineModelNode = slicer.mrmlScene.AddNewNodeByClassWithID('vtkMRMLModelNode', nodeName, nodeName)

    if not centerlineModelNode:
        raise ValueError('Error: Cannot create node: ', nodeName)

    self.logic.copyIndex(endPointsMarkupsNode, centerlineModelNode)
    return centerlineModelNode

  def getVesselSegmentName(self):
    segmentation = self.ui.inputSegmentSelectorWidget.currentNode().GetSegmentation()
    segmId = self.ui.inputSegmentSelectorWidget.currentSegmentID()
    segment = segmentation.GetSegment(segmId)
    name = 'Segment_' + self.ui.selectedVascularTerritorySegmId.currentNode().GetAttribute("LiverSegments.SegmentationId") \
      + '_Territory_' + str(self.ui.vascularTerritoryId.currentIndex) + '_' + segment.GetName()
    return name

  def newEndpointsListCreated(self):
    #Set baseName, and use this to create new unique names if endPointsMarkupsNode with this name already exist
    newName = self.getVesselSegmentName()
    self.updateSelectorColor()
    if(self.ui.endPointsMarkupsSelector.baseName == newName):
      return
    self.ui.endPointsMarkupsSelector.baseName = newName

    endPointsMarkupsNode = self.ui.endPointsMarkupsSelector.currentNode()
    endPointsMarkupsNode.SetName(newName)
    self.ui.endPointsMarkupsPlaceWidget.setPlaceModeEnabled(True)

  def updateSelectorColor(self):
    color = self.getCurrentColor()
    color255 = [int(i * 255) for i in color]
    self.ui.endPointsMarkupsPlaceWidget.ColorButton.setColor(qt.QColor(color255[0], color255[1], color255[2]))

  def getCurrentColor(self):
    color = [1, 1, 1, 1]
    index = self.ui.vascularTerritoryId.currentIndex
    if (index > 0):
      self.colormap.GetColor(index, color)
    del color[3:]
    return color

  def getCurrentColorQt(self):
    color = self.getCurrentColor()
    color255 = [int(i * 255) for i in color]
    qtColor = qt.QColor(color255[0], color255[1], color255[2])
    return qtColor

  def useColorFromSelector(self, centerlineModelNode):
    inputColor = self.getCurrentColorQt()
    centerlineModelNode.GetDisplayNode().SetColor(inputColor.redF(), inputColor.greenF(), inputColor.blueF())

  def onVascularTerritoryIdChanged(self):
    index = self.ui.vascularTerritoryId.currentIndex
    vascularTerrSegmNode = self.ui.selectedVascularTerritorySegmId.currentNode()
    VascSegmIdno = vascularTerrSegmNode.GetAttribute("LiverSegments.SegmentationId")
    # If the GUI is updating - No action
    if  self._updatingGUIFromSegmentationNode == True:
      return
    #Add new vascular territory ID
    if(index == 0):
      numItems = self.ui.vascularTerritoryId.count
      idString = "Vascular Territory ID " + str(numItems)
      self.ui.vascularTerritoryId.addItem(idString)
      self.ui.vascularTerritoryId.setCurrentIndex(numItems)
      self.ui.endPointsMarkupsPlaceWidget.setPlaceModeEnabled(True)
    else:
      self.ui.endPointsMarkupsPlaceWidget.setPlaceModeEnabled(False)
    #Add new Vascular Territory Segmentation
    segmentName = self.ui.vascularTerritoryId.currentText
    vascularTerrSegm = vascularTerrSegmNode.GetSegmentation()
    numberOfSegments = vascularTerrSegm.GetNumberOfSegments()
    if numberOfSegments < index:
      vascularTerrSegm.AddEmptySegment(segmentName, segmentName)

    #Update color in selector
    self.ui.ColorPickerButton.setColor(self.getCurrentColorQt())
    if(index > 0):
      self.colormap.SetColorName(index, self.ui.vascularTerritoryId.currentText)
      self.onSegmentChanged()#Also generate new vessel segment point lists when changing territory id

    index = self.ui.vascularTerritoryId.currentIndex
    vesselPointsSelector = self.ui.endPointsMarkupsSelector
    vesselPointsSelector.blockSignals(True)
    vesselPointsSelector.addAttribute("vtkMRMLMarkupsFiducialNode", "LiverSegments.VascTerrId", str(index))
    vesselPointsSelector.addAttribute("vtkMRMLMarkupsFiducialNode", "LiverSegments.SegmentationId", str(VascSegmIdno))
    vesselPointsSelector.blockSignals(False)

  def onColorChanged(self):
    colorIndex = self.ui.vascularTerritoryId.currentIndex
    color = self.ui.ColorPickerButton.color
    if(colorIndex > 0):
      self.colormap.SetColor(colorIndex, color.redF(), color.greenF(), color.blueF()) #Update index color in colormap.

  def onAddCenterlineButton(self):
    self.onAddCenterlineSegment()

  def onAddSegmentationButton(self):
    self.onAddCenterlineSegment(addSegmentationInsteadOfLine = True)

  def onAddCenterlineSegment(self, addSegmentationInsteadOfLine = False):
    if not (self.logic.check_module_Extract_Centerline_installed()):
      self.ui.endPointsMarkupsPlaceWidget.setPlaceModeEnabled(False)
      slicer.util.errorDisplay("SlicerVMTK Extension not installed")
      return
    endPointsMarkupsNode = self.ui.endPointsMarkupsSelector.currentNode()
    self.ui.endPointsMarkupsPlaceWidget.setPlaceModeEnabled(False)
    endPointsMarkupsNode.SetAttribute("LiverSegments.VascTerrId", str(self.ui.vascularTerritoryId.currentIndex))
    vascularTerritorySegm = self.ui.selectedVascularTerritorySegmId.currentNode()
    vascularTerritorySegmId = vascularTerritorySegm.GetAttribute("LiverSegments.SegmentationId")
    endPointsMarkupsNode.SetAttribute("LiverSegments.SegmentationId", str(vascularTerritorySegmId))

    slicer.app.pauseRender()
    qt.QApplication.setOverrideCursor(qt.Qt.WaitCursor)

    try:
        preprocessedPolyData = self.getPreprocessedPolyData()
    except ValueError:
        logging.error("Error: Preprocessing of polydata fails")
        slicer.app.resumeRender()
        qt.QApplication.restoreOverrideCursor()
        raise

    try:
        centerlineModelNode = self.createCenterlineNode(endPointsMarkupsNode)
    except ValueError:
        logging.error("Error: Failed to generate centerline model")

    try:
      if(addSegmentationInsteadOfLine):
        mergedLines = self.mergePolydata(centerlineModelNode.GetMesh(), preprocessedPolyData)
      else:
        centerlineProcessingLogic = self.logic.getCenterlineLogic()
        centerlinePolyData, voronoiDiagramPolyData = centerlineProcessingLogic.extractCenterline(preprocessedPolyData, endPointsMarkupsNode)
        decimatedCenterlinePolyData = self.logic.decimateLine(centerlinePolyData)
        mergedLines = self.mergePolydata(centerlineModelNode.GetMesh(), decimatedCenterlinePolyData)

      centerlineModelNode.SetAndObserveMesh(mergedLines)
      centerlineModelNode.SetAttribute("LiverSegments.SegmentationId", str(vascularTerritorySegmId))
      centerlineModelNode.SetAttribute("LiverSegments.VascTerrId", str(self.ui.vascularTerritoryId.currentIndex))

      centerlineModelNode.CreateDefaultDisplayNodes()
      self.useColorFromSelector(centerlineModelNode)
      centerlineModelNode.GetDisplayNode().SetLineWidth(3)
      endPointsMarkupsNode.SetDisplayVisibility(False)
    except ValueError:
      logging.error("Error: Failed to extract centerline")

    slicer.app.resumeRender()
    qt.QApplication.restoreOverrideCursor()

  def mergePolydata(self, existingPolyData, newPolyData):
    combinedPolyData = vtk.vtkAppendPolyData()
    combinedPolyData.AddInputData(existingPolyData)
    combinedPolyData.AddInputData(newPolyData)
    combinedPolyData.Update()
    return combinedPolyData.GetOutput()

  def onCalculateVascularTerritoryMapButton(self):
    if self.developerMode is True:
      import time
      startTime = time.time()

    segmentationNode = self.ui.inputSurfaceSelector.currentNode()
    vascTerrSegmentationId = int(self.ui.selectedVascularTerritorySegmId.currentNode().GetAttribute("LiverSegments.SegmentationId"))
    centerlineModel = self.logic.build_centerline_model(self.colormap, vascTerrSegmentationId)
    centerlineModelPoints = centerlineModel.GetMesh()
    numberOfPoints = centerlineModelPoints.GetNumberOfPoints()
    refVolumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
    if not (refVolumeNode) or (numberOfPoints<2):
        raise ValueError("Missing inputs to calculate vascular segments")

    slicer.app.pauseRender()
    qt.QApplication.setOverrideCursor(qt.Qt.WaitCursor)
    vascularTerritorySegmentationNode = self.ui.selectedVascularTerritorySegmId.currentNode()
    segmId = vascularTerritorySegmentationNode.GetAttribute("LiverSegments.SegmentationId")
    centerlineModel.SetAttribute("LiverSegments.SegmentationId", segmId)

    try:
       self.logic.calculateVascularTerritoryMap(vascularTerritorySegmentationNode, refVolumeNode, segmentationNode, centerlineModel, self.colormap)
    except ValueError:
        logging.error("Error: Failing when calculating vascular segments")


    slicer.app.resumeRender()
    qt.QApplication.restoreOverrideCursor()

    if self.developerMode is True:
      stopTime = time.time()
      logging.info(f'Vascular Segments processing completed in {stopTime-startTime:.2f} seconds')

# LiverSegmentsLogic
#

class LiverSegmentsLogic(ScriptedLoadableModuleLogic):

  def __init__(self):
    ScriptedLoadableModuleLogic.__init__(self)

    self._vascularSegmentTupleList = list()
    self._centerlines = list()
    self._inputLabelMap = None
    self._outputLabelMap = None
    self.centerlineProcessingLogic = None

    from vtkSlicerLiverSegmentsModuleLogicPython import vtkLiverSegmentsLogic
    # Create the segmentsclassification logic
    self.scl = vtkLiverSegmentsLogic()
    self.scl.SetMRMLScene(slicer.mrmlScene)

  def check_module_Extract_Centerline_installed(self):
    module_name = 'ExtractCenterline'
    return module_name in slicer.util.moduleNames()

  def getCenterlineLogic(self):
    """
    Get the centerline logic. If the logic wasn't yet instantiated it does it
    """
    from ExtractCenterline import ExtractCenterlineLogic
    if self.centerlineProcessingLogic is None:
      self.centerlineProcessingLogic = ExtractCenterlineLogic()
    return self.centerlineProcessingLogic

  def setDefaultParameters(self, parameterNode):
    """
    Initialize parameter node with default settings.
    """

  def createCompleteCenterlineModel(self, colormap):
    nodeName = "CenterlineModel"
    completeCenterlineModelNode = slicer.mrmlScene.GetNodeByID(nodeName)
    if completeCenterlineModelNode:
        logging.error('Replacing completeCenterlineModelNode: ' + nodeName)
        slicer.mrmlScene.RemoveNode(completeCenterlineModelNode)

    completeCenterlineModelNode = slicer.mrmlScene.AddNewNodeByClassWithID('vtkMRMLModelNode', nodeName, nodeName)
    dummyPolyData = vtk.vtkPolyData()
    completeCenterlineModelNode.SetAndObservePolyData(dummyPolyData)
    if not completeCenterlineModelNode:
        logging.error('Error: Cannot create node: ' + nodeName)

    completeCenterlineModelNode.CreateDefaultDisplayNodes()
    displayNode = completeCenterlineModelNode.GetDisplayNode()
    displayNode.ScalarVisibilityOn()
    displayNode.SetActiveScalar('SegmentId', 2)
    displayNode.SetScalarRangeFlagFromString('UseColorNodeScalarRange')
    displayNode.SetLineWidth(3)
    completeCenterlineModelNode.GetDisplayNode().SetAndObserveColorNodeID(colormap.GetID())

    return completeCenterlineModelNode

  def build_centerline_model(self, colormap, vascSegmSelected):
    centerlineModel = self.createCompleteCenterlineModel(colormap)
    centerlineSegmentsDict = slicer.util.getNodes("*Territory*")
    for name, segmentObject in centerlineSegmentsDict.items():
      if segmentObject.GetClassName() == "vtkMRMLModelNode":
        VascTerrId = int(segmentObject.GetAttribute("LiverSegments.VascTerrId"))
        VascTerrSegmId = int(segmentObject.GetAttribute("LiverSegments.SegmentationId"))
        if VascTerrSegmId == vascSegmSelected:
          self.scl.MarkSegmentWithID(segmentObject, VascTerrId)
          self.scl.AddSegmentToCenterlineModel(centerlineModel, segmentObject)
    self.scl.InitializeCenterlineSearchModel(centerlineModel)
    return centerlineModel

  def calculateVascularTerritoryMap(self, vascularTerritorySegmentationNode, refVolume, segmentation, centerlineModel, colormap):
    self.scl.calculateVascularTerritoryMap(vascularTerritorySegmentationNode, refVolume, segmentation, centerlineModel, colormap)

  def copyIndex(self, endPointsMarkupsNode, centerlineModelNode):
    centerlineModelNode.SetAttribute("LiverSegments.VascTerrId", endPointsMarkupsNode.GetAttribute("LiverSegments.VascTerrId"))

  def preprocessAndDecimate(self, surfacePolyData):
    processedPolyData = vtk.vtkPolyData()
    self.scl.preprocessAndDecimate(surfacePolyData, processedPolyData)
    return processedPolyData

  def decimateLine(self, polyDataLine):
    decimate = vtk.vtkDecimatePolylineFilter()
    decimate.SetInputData(polyDataLine)
    decimate.SetTargetReduction(.90)
    decimate.Update()
    return decimate.GetOutput()

  #Using code from SlicerExtension-VMTK
  #https://github.com/vmtk/SlicerExtension-VMTK/blob/master/ExtractCenterline/ExtractCenterline.py
  def polyDataFromNode(self, surfaceNode, segmentId):
    if not surfaceNode:
        logging.error("Invalid input surface node")
        return None
    if surfaceNode.IsA("vtkMRMLModelNode"):
        return surfaceNode.GetPolyData()
    elif surfaceNode.IsA("vtkMRMLSegmentationNode"):
        # Segmentation node
        polyData = vtk.vtkPolyData()
        surfaceNode.CreateClosedSurfaceRepresentation()
        surfaceNode.GetClosedSurfaceRepresentation(segmentId, polyData)
        return polyData
    else:
        logging.error

class LiverSegmentsTest(ScriptedLoadableModuleTest):
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
    self.test_LiverSegments1()

  def test_LiverSegments1(self):
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

    # Get/create input data

    # Test the module logic

    logic = LiverSegmentsLogic()

    self.delayDisplay('Test passed')

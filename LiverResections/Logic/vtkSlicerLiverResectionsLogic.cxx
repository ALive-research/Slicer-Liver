/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) Oslo University Hospital. All rights reserved.

  Redistribution and use in source and binary forms, with or without
  modification, are permitted provided that the following conditions
  are met:

  * Redistributions of source code must retain the above copyright
    notice, this list of conditions and the following disclaimer.

  * Redistributions in binary form must reproduce the above copyright
    notice, this list of conditions and the following disclaimer in the
    documentation and/or other materials provided with the distribution.

  * Neither the name of Oslo University Hospital nor the names of Contributors
    may be used to endorse or promote products derived from this
    software without specific prior written permission.

  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
  "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
  A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
  HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
  SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
  LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
  DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
  THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

  This file was originally developed by Rafael Palomar (Oslo University
  Hospital and NTNU) and Ruoyan Meng (NTNU), and was supported by The
  Research Council of Norway through the ALive project (grant nr. 311393).

  ==============================================================================*/

//NOTE: Some of the functions of this file are inspired in vtkSlicerMarkupsLogic

#include "vtkSlicerLiverResectionsLogic.h"
#include "vtkMRMLAbstractLogic.h"
#include "vtkMRMLLiverResectionCSVStorageNode.h"

#include <vtkCommand.h>
#include <vtkMRMLMarkupsSlicingContourNode.h>
#include <vtkMRMLMarkupsSlicingContourDisplayNode.h>
#include <vtkMRMLMarkupsDistanceContourNode.h>
#include <vtkMRMLMarkupsDisplayNode.h>
#include <vtkMRMLLiverResectionNode.h>
#include <vtkMRMLMarkupsBezierSurfaceNode.h>
#include <vtkMRMLMarkupsBezierSurfaceDisplayNode.h>

// MRML includes
#include <vtkMRMLScene.h>
#include <vtkMRMLSelectionNode.h>
#include <vtkMRMLSegmentationNode.h>

// VTK includes
#include <vtkObjectFactory.h>
#include <vtkCollection.h>
#include <vtkSetGet.h>
#include <vtkSmartPointer.h>
#include <vtkIntArray.h>
#include <vtkPlane.h>
#include <vtkCutter.h>
#include <vtkDoubleArray.h>
#include <vtkCenterOfMass.h>
#include <vtkPCAStatistics.h>
#include <vtkPlaneSource.h>
#include <vtkTable.h>
#include <vtkImageData.h>

#include <vtkMRMLMarkupsFiducialNode.h>
#include <vtkMRMLGlyphableVolumeDisplayNode.h>
#include <vtkMRMLTableNode.h>
#include <vtkMRMLLabelMapVolumeNode.h>
#include <itkLabelImageToLabelMapFilter.h>
#include <vtkLabelMapHelper.h>
#include <vtkBezierSurfaceSource.h>
#include <vtkPath.h>

//----------------------------------------------------------------------------
vtkStandardNewMacro(vtkSlicerLiverResectionsLogic);

//---------------------------------------------------------------------------
vtkSlicerLiverResectionsLogic::vtkSlicerLiverResectionsLogic()
{
  //auto node = vtkSmartPointer<vtkMRMLGlyphableVolumeDisplayNode>::New();
}

//---------------------------------------------------------------------------
vtkSlicerLiverResectionsLogic::~vtkSlicerLiverResectionsLogic() = default;

//---------------------------------------------------------------------------
void vtkSlicerLiverResectionsLogic::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);
}

//---------------------------------------------------------------------------
void vtkSlicerLiverResectionsLogic::RegisterNodes()
{
  assert(this->GetMRMLScene() != nullptr);
  vtkMRMLScene *scene = this->GetMRMLScene();

  // Nodes
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLLiverResectionNode>::New());
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLLiverResectionCSVStorageNode>::New());
}

//---------------------------------------------------------------------------
void vtkSlicerLiverResectionsLogic::SetMRMLSceneInternal(vtkMRMLScene * newScene)
{
   vtkNew<vtkIntArray> events;
   events->InsertNextValue(vtkMRMLScene::NodeAddedEvent);
   events->InsertNextValue(vtkMRMLScene::NodeRemovedEvent);
   events->InsertNextValue(vtkMRMLScene::EndBatchProcessEvent);
   this->SetAndObserveMRMLSceneEventsInternal(newScene, events.GetPointer());
}

//---------------------------------------------------------------------------
void vtkSlicerLiverResectionsLogic::ObserveMRMLScene()
{
 this->Superclass::ObserveMRMLScene();
}

//---------------------------------------------------------------------------
void vtkSlicerLiverResectionsLogic::ProcessMRMLNodesEvents(vtkObject *caller,
                                                           unsigned long event,
                                                           void *vtkNotUsed(callData))
{
  // Process slicing initialization
  auto slicingInitializationNode = vtkMRMLMarkupsSlicingContourNode::SafeDownCast(caller);
  if (slicingInitializationNode)
    {
    switch(event)
      {
      case vtkCommand::StartInteractionEvent:
        this->HideBezierSurfaceMarkup(slicingInitializationNode);
        break;

      case vtkCommand::EndInteractionEvent:
        this->UpdateBezierWidgetOnInitialization(slicingInitializationNode);
        break;
      }
    }

  // Process slicing bezier surface
  auto bezierSurfaceNode = vtkMRMLMarkupsBezierSurfaceNode::SafeDownCast(caller);
  if (bezierSurfaceNode && event == vtkCommand::StartInteractionEvent)
    {
    this->HideInitializationMarkup(bezierSurfaceNode);
    auto resectionNode = this->GetResectionFromBezier(bezierSurfaceNode);
    if (resectionNode)
      {
      MRMLNodeModifyBlocker blocker(resectionNode);
      resectionNode->SetState(vtkMRMLLiverResectionNode::Deformation);
      }
    }

  // Process resection node
  auto resectionNode = vtkMRMLLiverResectionNode::SafeDownCast(caller);
  if (resectionNode && event == vtkCommand::ModifiedEvent)
    {
    // Create the resection elements
    if (this->ResectionToInitializationMap.find(resectionNode) == this->ResectionToInitializationMap.end())
      {
      this->CreateInitializationAndResectionMarkups(resectionNode);
      }

    // Update the polydata
    auto initializationNode =  vtkMRMLMarkupsSlicingContourNode::SafeDownCast(this->GetInitializationFromResection(resectionNode));
    if(initializationNode)
      {
        initializationNode->SetTarget(resectionNode->GetTargetOrganModelNode());
      }

    auto bezierSurfaceNode = this->GetBezierFromResection(resectionNode);
    if (bezierSurfaceNode)
      {
      bezierSurfaceNode->SetDistanceMapVolumeNode(resectionNode->GetDistanceMapVolumeNode());
      bezierSurfaceNode->SetVascularSegmentsVolumeNode(resectionNode->GetVascularSegmentsVolumeNode());
      bezierSurfaceNode->SetResectionMargin(resectionNode->GetResectionMargin());
      bezierSurfaceNode->SetUncertaintyMargin(resectionNode->GetUncertaintyMargin());
      bezierSurfaceNode->SetHepaticContourThickness(resectionNode->GetHepaticContourThickness());
      bezierSurfaceNode->SetPortalContourThickness(resectionNode->GetPortalContourThickness());

      auto bezierSurfaceDisplayNode =
        vtkMRMLMarkupsBezierSurfaceDisplayNode::SafeDownCast(bezierSurfaceNode->GetDisplayNode());
      if (bezierSurfaceDisplayNode)
        {
        bezierSurfaceDisplayNode->SetShowResection2D(resectionNode->GetShowResection2D());
        bezierSurfaceDisplayNode->SetMirrorDisplay(resectionNode->GetMirrorDisplay());
        bezierSurfaceDisplayNode->SetEnableFlexibleBoundary(resectionNode->GetEnableFlexibleBoundary());
        bezierSurfaceDisplayNode->SetGrid2DVisibility(resectionNode->GetGrid2DVisibility());
        bezierSurfaceDisplayNode->SetTextureNumComps(resectionNode->GetTextureNumComps());
        bezierSurfaceDisplayNode->SetClipOut(resectionNode->GetClipOut());
        bezierSurfaceDisplayNode->SetWidgetVisibility(resectionNode->GetWidgetVisibility());
        bezierSurfaceDisplayNode->SetInterpolatedMargins(resectionNode->GetInterpolatedMargins());
        bezierSurfaceDisplayNode->SetResectionColor(resectionNode->GetResectionColor());
        bezierSurfaceDisplayNode->SetResectionGridColor(resectionNode->GetResectionGridColor());
        bezierSurfaceDisplayNode->SetResectionMarginColor(resectionNode->GetResectionMarginColor());
        bezierSurfaceDisplayNode->SetUncertaintyMarginColor(resectionNode->GetUncertaintyMarginColor());
        bezierSurfaceDisplayNode->SetResectionOpacity(resectionNode->GetResectionOpacity());
        bezierSurfaceDisplayNode->SetGridDivisions(resectionNode->GetGridDivisions());
        bezierSurfaceDisplayNode->SetGridThickness(resectionNode->GetGridThickness());
        bezierSurfaceDisplayNode->SetGrid3DVisibility(resectionNode->GetGrid3DVisibility());
        bezierSurfaceDisplayNode->SetHepaticContourColor(resectionNode->GetHepaticContourColor());
        bezierSurfaceDisplayNode->SetPortalContourColor(resectionNode->GetPortalContourColor());
        }
      bezierSurfaceNode->SetLocked(!resectionNode->GetWidgetVisibility());
      }
    }
}

//---------------------------------------------------------------------------
void vtkSlicerLiverResectionsLogic::OnMRMLSceneNodeAdded(vtkMRMLNode* node)
{
  Superclass::OnMRMLSceneNodeAdded(node);

  auto resectionNode = vtkMRMLLiverResectionNode::SafeDownCast(node);

  // check for nullptr and target organ
  if (!resectionNode)
    {
    return;
    }

  // Add callbacks dealing with the modification of the resection node. Its
  // modification may trigger changes on the underlying initialization/bezier status
  vtkNew<vtkIntArray> resectionNodeEvents;
  resectionNodeEvents->InsertNextValue(vtkCommand::ModifiedEvent);
  vtkUnObserveMRMLNodeMacro(resectionNode);
  vtkObserveMRMLNodeEventsMacro(resectionNode, resectionNodeEvents.GetPointer());

  if (resectionNode->GetTargetOrganModelNode())
    {
    // Create resection initialization a surface markups.
    this->CreateInitializationAndResectionMarkups(resectionNode);
    }
}

//---------------------------------------------------------------------------
void vtkSlicerLiverResectionsLogic::OnMRMLSceneNodeRemoved(vtkMRMLNode* node)
{
  auto resectionNode = vtkMRMLLiverResectionNode::SafeDownCast(node);

  // check for nullptr and target organ
  if (!resectionNode)
    {
    return;
    }

  vtkMRMLMarkupsNode* initializationNode = nullptr;
  vtkMRMLMarkupsBezierSurfaceNode* bezierSurfaceNode = nullptr;

  auto riMapIt = this->ResectionToInitializationMap.find(resectionNode);
  if (riMapIt != this->ResectionToInitializationMap.end())
    {
    initializationNode = riMapIt->second.GetPointer();
    this->ResectionToInitializationMap.erase(riMapIt);
    }

  auto irMapIt = this->InitializationToResectionMap.find(initializationNode);
  if (irMapIt != this->InitializationToResectionMap.end())
    {
    this->InitializationToResectionMap.erase(irMapIt);
    }

  auto rbMapIt = this->ResectionToBezierMap.find(resectionNode);
  if (rbMapIt != this->ResectionToBezierMap.end())
    {
    bezierSurfaceNode = rbMapIt->second.GetPointer();
    this->ResectionToBezierMap.erase(rbMapIt);
    }

  auto brMapIt = this->BezierToResectionMap.find(bezierSurfaceNode);
  if (brMapIt != this->BezierToResectionMap.end())
    {
    resectionNode = brMapIt->second.GetPointer();
    this->BezierToResectionMap.erase(brMapIt);
    }

  auto ibMapIt = this->InitializationToBezierMap.find(initializationNode);
  if (ibMapIt != this->InitializationToBezierMap.end())
    {
    this->InitializationToBezierMap.erase(ibMapIt);
    }

  auto biMapIt = this->BezierToInitializationMap.find(bezierSurfaceNode);
  if (biMapIt != this->BezierToInitializationMap.end())
    {
    this->BezierToInitializationMap.erase(biMapIt);
    }

  // NOTE: This is a workaround to "delete" the contour from visualization.
  // A better option would be that the markup takes care of this.
  this->HideBezierSurfaceMarkup(initializationNode);

  vtkUnObserveMRMLNodeMacro(bezierSurfaceNode);
  vtkUnObserveMRMLNodeMacro(initializationNode);

  this->GetMRMLScene()->RemoveNode(bezierSurfaceNode);
  this->GetMRMLScene()->RemoveNode(initializationNode);

  Superclass::OnMRMLSceneNodeRemoved(node);
}

//---------------------------------------------------------------------------
vtkMRMLMarkupsSlicingContourNode*
vtkSlicerLiverResectionsLogic::AddResectionPlane(vtkMRMLLiverResectionNode *resectionNode) const
{
  auto mrmlScene = this->GetMRMLScene();
  if (!mrmlScene)
    {
      vtkErrorMacro("Error in AddResectionPlane: no valid MRML scene.");
      return nullptr;
    }

  if (!resectionNode->GetTargetOrganModelNode())
    {
      vtkErrorMacro("Error in AddResectionPlane: invalid internal target parenchyma.");
      return nullptr;
    }

  auto targetParenchymaPolyData = resectionNode->GetTargetOrganModelNode()->GetPolyData();
  if (!targetParenchymaPolyData)
    {
      vtkErrorMacro("Error in AddResectionPlane: target liver model does not contain valid polydata.");
      return nullptr;
    }

  // Computing the position of the initial points
  const double *bounds = targetParenchymaPolyData->GetBounds();
  auto p1 = vtkVector3d(bounds[0],(bounds[3]-bounds[2])/2.0, (bounds[5]-bounds[4])/2.0);
  auto p2 = vtkVector3d(bounds[1],(bounds[3]-bounds[2])/2.0, (bounds[5]-bounds[4])/2.0);

  auto slicingContourNode = vtkMRMLMarkupsSlicingContourNode::SafeDownCast(mrmlScene->AddNewNodeByClass("vtkMRMLMarkupsSlicingContourNode"));
  if (!slicingContourNode)
    {
      vtkErrorMacro("Error in AddResectionPlane: Error creating vtkMRMLMarkupsSlicingContourNode.");
      return nullptr;
    }
  slicingContourNode->CreateDefaultDisplayNodes();
  slicingContourNode->AddControlPoint(p1);
  slicingContourNode->AddControlPoint(p2);
  slicingContourNode->SetTarget(resectionNode->GetTargetOrganModelNode());

  auto slicingContourDisplayNode = vtkMRMLMarkupsSlicingContourDisplayNode::SafeDownCast(slicingContourNode->GetDisplayNode());
  if (!slicingContourDisplayNode)
    {
      vtkErrorMacro("Error in AddResectionPlane: Error getting vtkMRMLMarkupsSlicingContourDisplayNode.");
      return nullptr;
    }
  slicingContourDisplayNode->PropertiesLabelVisibilityOff();
  slicingContourDisplayNode->SetSnapMode(vtkMRMLMarkupsDisplayNode::SnapModeUnconstrained);

  return slicingContourNode;
}

//---------------------------------------------------------------------------
vtkMRMLMarkupsDistanceContourNode*
vtkSlicerLiverResectionsLogic::AddResectionContour(vtkMRMLLiverResectionNode *resectionNode) const
{
  auto mrmlScene = this->GetMRMLScene();
  if (!mrmlScene)
    {
    vtkErrorMacro("Error in AddResectionContour: no valid MRML scene.");
    return nullptr;
    }

  if(!resectionNode)
    {
    vtkErrorMacro("Error in AddResectionContour: no valid resection node.");
    return nullptr;
    }

  if (!resectionNode->GetTargetOrganModelNode())
    {
      vtkErrorMacro("Error in AddResectionContour: no valid target parenchyma node.");
      return nullptr;
    }

  // Computing the position of the initial points
  const double *bounds = resectionNode->GetTargetOrganModelNode()->GetPolyData()->GetBounds();
  auto p1 = vtkVector3d(bounds[0],(bounds[3]-bounds[2])/2.0, (bounds[5]-bounds[4])/2.0);
  auto p2 = vtkVector3d((bounds[1]-bounds[0])/2.0,(bounds[3]-bounds[2])/2.0, (bounds[5]-bounds[4])/2.0);

  auto distanceContourNode = vtkMRMLMarkupsDistanceContourNode::SafeDownCast(mrmlScene->AddNewNodeByClass("vtkMRMLMarkupsDistanceContourNode"));
  if (!distanceContourNode)
    {
      vtkErrorMacro("Error in AddResectionPlane: Error creating vtkMRMLMarkupsDistanceContourNode.");
      return nullptr;
    }

  distanceContourNode->CreateDefaultDisplayNodes();
  distanceContourNode->AddControlPoint(p1);
  distanceContourNode->AddControlPoint(p2);
  distanceContourNode->SetTarget(resectionNode->GetTargetOrganModelNode());

  // auto distanceContourDisplayNode = vtkSmartPointer<vtkMRMLMarkupsDisplayNode>::New();
  // distanceContourDisplayNode->PropertiesLabelVisibilityOff();
  // distanceContourDisplayNode->SetSnapMode(vtkMRMLMarkupsDisplayNode::SnapModeUnconstrained);

  // mrmlScene->AddNode(distanceContourDisplayNode);
  // distanceContourNode->SetAndObserveDisplayNodeID(distanceContourDisplayNode->GetID());
  // mrmlScene->AddNode(distanceContourNode);

  return distanceContourNode;
}

//------------------------------------------------------------------------------
vtkMRMLMarkupsBezierSurfaceNode*
vtkSlicerLiverResectionsLogic::AddBezierSurface(vtkMRMLLiverResectionNode *resectionNode) const
{
  auto mrmlScene = this->GetMRMLScene();
  if (!mrmlScene)
    {
    vtkErrorMacro("Error in AddResectionContour: no valid MRML scene.");
    return nullptr;
    }

  if(!resectionNode)
    {
    vtkErrorMacro("Error in AddResectionContour: no valid resection node.");
    return nullptr;
    }

  auto markupsBezierSurfaceNode =
    vtkMRMLMarkupsBezierSurfaceNode::SafeDownCast(mrmlScene->AddNewNodeByClass("vtkMRMLMarkupsBezierSurfaceNode"));
  if (!markupsBezierSurfaceNode)
    {
    vtkErrorMacro("Error adding a vtkMRMLMarkupsBezierSurfceNode to the scene");
    return nullptr;
    }

  markupsBezierSurfaceNode->SetScene(mrmlScene);

  for (int i = 0; i<4; ++i)
    {
    for (int j = 0; j<4; ++j)
      {
      markupsBezierSurfaceNode->AddControlPoint({10.0f*i, 10.0f*j, 0.0f});
      }
    }

  markupsBezierSurfaceNode->SetHideFromEditors(false);

  auto markupsBezierSurfaceDisplayNode = vtkMRMLMarkupsBezierSurfaceDisplayNode::SafeDownCast(markupsBezierSurfaceNode->GetDisplayNode());
  if (markupsBezierSurfaceDisplayNode)
    {
    markupsBezierSurfaceDisplayNode->SetVisibility(false); // Initially hidden
    markupsBezierSurfaceDisplayNode->SetSnapMode(vtkMRMLMarkupsDisplayNode::SnapModeUnconstrained);
    }

  resectionNode->SetBezierSurfaceNode(markupsBezierSurfaceNode);

  return markupsBezierSurfaceNode;
}

//------------------------------------------------------------------------------
vtkMRMLLiverResectionNode* vtkSlicerLiverResectionsLogic
::GetResectionFromBezier(vtkMRMLMarkupsBezierSurfaceNode* markupsBezierNode) const
{
  auto bezierToResection = this->BezierToResectionMap.find(markupsBezierNode);
  if (bezierToResection == this->BezierToResectionMap.end())
    {
    return nullptr;
    }
  return bezierToResection->second;
}

//------------------------------------------------------------------------------
vtkMRMLLiverResectionNode* vtkSlicerLiverResectionsLogic
::GetResectionFromInitialization(vtkMRMLMarkupsNode* initializationNode) const
{
  auto initializationToResection = this->InitializationToResectionMap.find(initializationNode);
  if (initializationToResection == this->InitializationToResectionMap.end())
    {
    return nullptr;
    }
  return initializationToResection->second;
}
//------------------------------------------------------------------------------
vtkMRMLMarkupsNode* vtkSlicerLiverResectionsLogic
::GetInitializationFromResection(vtkMRMLLiverResectionNode* resectionNode) const
{
  auto resectionToInitialization = this->ResectionToInitializationMap.find(resectionNode);
  if (resectionToInitialization == this->ResectionToInitializationMap.end())
    {
    return nullptr;
    }
  return resectionToInitialization->second;
}

//------------------------------------------------------------------------------
vtkMRMLMarkupsBezierSurfaceNode* vtkSlicerLiverResectionsLogic
::GetBezierFromResection(vtkMRMLLiverResectionNode* resectionNode) const
{
  auto resectionToBezier = this->ResectionToBezierMap.find(resectionNode);
  if (resectionToBezier == this->ResectionToBezierMap.end())
    {
    return nullptr;
    }
  return resectionToBezier->second;
}

//------------------------------------------------------------------------------
vtkMRMLMarkupsBezierSurfaceNode* vtkSlicerLiverResectionsLogic
::GetBezierFromInitialization(vtkMRMLMarkupsNode *initializationNode) const
{
  auto initializationToBezier = this->InitializationToBezierMap.find(initializationNode);
  if (initializationToBezier == this->InitializationToBezierMap.end())
    {
    return nullptr;
    }
  return initializationToBezier->second;
}

//------------------------------------------------------------------------------
vtkMRMLMarkupsNode * vtkSlicerLiverResectionsLogic
::GetInitializationFromBezier(vtkMRMLMarkupsBezierSurfaceNode* markupsBezierNode) const
{
  auto BezierToInitialization = this->BezierToInitializationMap.find(markupsBezierNode);
  if (BezierToInitialization == this->BezierToInitializationMap.end())
    {
    return nullptr;
    }
  return BezierToInitialization->second;
}

//------------------------------------------------------------------------------
void vtkSlicerLiverResectionsLogic::ShowBezierSurfaceMarkupFromResection(vtkMRMLLiverResectionNode* resectionNode) const
{
  auto bezierSurfaceNode = this->GetBezierFromResection(resectionNode);
  if (!bezierSurfaceNode)
    {
    return;
    }

  auto bezierSurfaceDisplayNode = bezierSurfaceNode->GetDisplayNode();
  if (!bezierSurfaceDisplayNode)
    {
    return;
    }

  bezierSurfaceDisplayNode->VisibilityOn();
}

//------------------------------------------------------------------------------
void vtkSlicerLiverResectionsLogic::HideBezierSurfaceMarkupFromResection(vtkMRMLLiverResectionNode* resectionNode) const
{
  auto bezierSurfaceNode = this->GetBezierFromResection(resectionNode);
  if (!bezierSurfaceNode)
    {
    return;
    }

  auto bezierSurfaceDisplayNode = bezierSurfaceNode->GetDisplayNode();
  if (!bezierSurfaceDisplayNode)
    {
    return;
    }

  bezierSurfaceDisplayNode->VisibilityOff();
}

//------------------------------------------------------------------------------
void vtkSlicerLiverResectionsLogic::ShowInitializationMarkupFromResection(vtkMRMLLiverResectionNode* resectionNode) const
{
  auto initializationNode = this->GetInitializationFromResection(resectionNode);
  if (!initializationNode)
    {
    return;
    }

  auto initializationDisplayNode = initializationNode->GetDisplayNode();
  if (!initializationDisplayNode)
    {
    return;
    }

  initializationDisplayNode->VisibilityOn();
}

//------------------------------------------------------------------------------
void vtkSlicerLiverResectionsLogic::HideInitializationMarkupFromResection(vtkMRMLLiverResectionNode* resectionNode) const
{
  auto initializationNode = this->GetInitializationFromResection(resectionNode);
  if (!initializationNode)
    {
    return;
    }

  auto initializationDisplayNode = initializationNode->GetDisplayNode();
  if (!initializationDisplayNode)
    {
    return;
    }

  initializationDisplayNode->VisibilityOff();
}

//------------------------------------------------------------------------------
void vtkSlicerLiverResectionsLogic::ShowBezierSurfaceMarkup(vtkMRMLMarkupsNode* initializationNode) const
{
  auto bezierSurfaceNode = this->GetBezierFromInitialization(initializationNode);
  if (!bezierSurfaceNode)
    {
    return;
    }

  auto bezierSurfaceDisplayNode = bezierSurfaceNode->GetDisplayNode();
  if (!bezierSurfaceDisplayNode)
    {
    return;
    }

  bezierSurfaceDisplayNode->VisibilityOn();
}

//------------------------------------------------------------------------------
void vtkSlicerLiverResectionsLogic::HideBezierSurfaceMarkup(vtkMRMLMarkupsNode* initializationNode) const
{
  auto bezierSurfaceNode = this->GetBezierFromInitialization(initializationNode);
  if (!bezierSurfaceNode)
    {
    return;
    }

  auto bezierSurfaceDisplayNode = bezierSurfaceNode->GetDisplayNode();
  if (!bezierSurfaceDisplayNode)
    {
    return;
    }

  bezierSurfaceDisplayNode->VisibilityOff();
}

// TODO: These functions perhaps could be replaced by SetInitializationMarkupsVisibility(node, bool);
//------------------------------------------------------------------------------
void vtkSlicerLiverResectionsLogic::ShowInitializationMarkup(vtkMRMLMarkupsBezierSurfaceNode* markupsBezierNode) const
{
  auto markupsInitializationNode = this->GetInitializationFromBezier(markupsBezierNode);
  if (!markupsInitializationNode)
    {
    return;
    }

  auto markupsInitializationDisplayNode = markupsInitializationNode->GetDisplayNode();
  if (!markupsInitializationDisplayNode)
    {
    return;
    }

  markupsInitializationDisplayNode->SetVisibility(false);
}

//------------------------------------------------------------------------------
void vtkSlicerLiverResectionsLogic::HideInitializationMarkup(vtkMRMLMarkupsBezierSurfaceNode* markupsBezierNode) const
{
  auto markupsInitializationNode = this->GetInitializationFromBezier(markupsBezierNode);
  if (!markupsInitializationNode)
    {
    return;
    }
  auto markupsInitializationDisplayNode = markupsInitializationNode->GetDisplayNode();
  if (!markupsInitializationDisplayNode)
    {
    return;
    }
  markupsInitializationDisplayNode->SetVisibility(false);
}

//------------------------------------------------------------------------------
void vtkSlicerLiverResectionsLogic::UpdateBezierWidgetOnInitialization(vtkMRMLMarkupsNode* initializationNode)
{
  // Check initialization node
  if (!initializationNode)
    {
    vtkErrorMacro("Error in UpdateBezierWidgetOnInitialization: no initialization node passed");
    return;
    }

  // Check for resection node from initializatio node
  auto initializationToResection =
    this->InitializationToResectionMap.find(initializationNode);
  if (initializationToResection == this->InitializationToResectionMap.end())
    {
    vtkErrorMacro("Error in UpdateBezierWidgetOnInitialization: initialization node does not have a corresponding resection node.");
    return;
    }

  // Check for resection node
  if (!initializationToResection->second)
    {
    vtkErrorMacro("Error in UpdateBezierWidgetOnInitialization: initialization node does not have a valid corresponding resection node.");
    return;
    }

  // Check for target organ model node
  auto parenchymaModelNode = initializationToResection->second->GetTargetOrganModelNode();
  if (!parenchymaModelNode)
    {
    vtkErrorMacro("Error in UpdateBezierWidgetOnInitialization: resection node does not have a valid target organ.");
    return;
    }

  // Check for parenchyma polydata
  if (!parenchymaModelNode->GetPolyData())
    {
    vtkErrorMacro("Error UpdateBezierWidgetOnInitialization: parenchyma model node does not contain poly data.");
    return;
    }

  auto controlPoints =  initializationNode->GetControlPoints();

  // This algorithm is based on NorMIT-Plan
  // https://github.com/TheInterventionCentre/NorMIT-Plan

  double point1[3] = {(*controlPoints)[0]->Position[0],
                      (*controlPoints)[0]->Position[1],
                      (*controlPoints)[0]->Position[2]};
  double point2[3] = {(*controlPoints)[1]->Position[0],
                      (*controlPoints)[1]->Position[1],
                      (*controlPoints)[1]->Position[2]};
  double midPoint[3];
  double normal[3];

  midPoint[0] = (point1[0] + point2[0]) / 2.0;
  midPoint[1] = (point1[1] + point2[1]) / 2.0;
  midPoint[2] = (point1[2] + point2[2]) / 2.0;

  normal[0] = point2[0] - point1[0];
  normal[1] = point2[1] - point1[1];
  normal[2] = point2[2] - point1[2];

  // Cut the parenchyma (generate contour).
  vtkNew<vtkPlane> cuttingPlane;
  cuttingPlane->SetOrigin(midPoint);
  cuttingPlane->SetNormal(normal);
  vtkNew<vtkCutter> cutter;
  cutter->SetInputData(parenchymaModelNode->GetPolyData());
  cutter->SetCutFunction(cuttingPlane.GetPointer());
  cutter->Update();

  vtkPolyData *contour = cutter->GetOutput();

  // Perform Principal Component Analysis
  vtkNew<vtkDoubleArray> xArray;
  xArray->SetNumberOfComponents(1);
  xArray->SetName("x");
  vtkNew<vtkDoubleArray> yArray;
  yArray->SetNumberOfComponents(1);
  yArray->SetName("y");
  vtkNew<vtkDoubleArray> zArray;
  zArray->SetNumberOfComponents(1);
  zArray->SetName("z");

  vtkNew<vtkCenterOfMass> centerOfMass;
  centerOfMass->SetInputData(contour);
  centerOfMass->Update();
  double com[3]={0};
  centerOfMass->GetCenter(com);

  for(unsigned int i=0; i<contour->GetNumberOfPoints(); i++)
    {
    double point[3];
    contour->GetPoint(i, point);
    xArray->InsertNextValue(point[0]);
    yArray->InsertNextValue(point[1]);
    zArray->InsertNextValue(point[2]);
    }

  vtkNew<vtkTable> dataTable;
  dataTable->AddColumn(xArray.GetPointer());
  dataTable->AddColumn(yArray.GetPointer());
  dataTable->AddColumn(zArray.GetPointer());

  vtkNew<vtkPCAStatistics> pcaStatistics;
  pcaStatistics->SetInputData(vtkStatisticsAlgorithm::INPUT_DATA,
                              dataTable.GetPointer());
  pcaStatistics->SetColumnStatus("x", 1);
  pcaStatistics->SetColumnStatus("y", 1);
  pcaStatistics->SetColumnStatus("z", 1);
  pcaStatistics->RequestSelectedColumns();
  pcaStatistics->SetDeriveOption(true);
  pcaStatistics->SetFixedBasisSize(3);
  pcaStatistics->Update();

  vtkNew<vtkDoubleArray> eigenvalues;
  pcaStatistics->GetEigenvalues(eigenvalues.GetPointer());
  vtkNew<vtkDoubleArray> eigenvector1;
  pcaStatistics->GetEigenvector(0, eigenvector1.GetPointer());
  vtkNew<vtkDoubleArray> eigenvector2;
  pcaStatistics->GetEigenvector(1, eigenvector2.GetPointer());
  vtkNew<vtkDoubleArray> eigenvector3;
  pcaStatistics->GetEigenvector(2, eigenvector3.GetPointer());

  double length1 = 4.0*sqrt(pcaStatistics->GetEigenvalue(0,0));
  double length2 = 4.0*sqrt(pcaStatistics->GetEigenvalue(0,1));

  double v1[3] =
    {
      eigenvector1->GetValue(0),
      eigenvector1->GetValue(1),
      eigenvector1->GetValue(2)
    };

  double v2[3] =
    {
      eigenvector2->GetValue(0),
      eigenvector2->GetValue(1),
      eigenvector2->GetValue(2)
    };

  double origin[3] =
    {
      com[0] - v1[0]*length1/2.0 - v2[0]*length2/2.0,
      com[1] - v1[1]*length1/2.0 - v2[1]*length2/2.0,
      com[2] - v1[2]*length1/2.0 - v2[2]*length2/2.0,
    };

  point1[0] = origin[0] + v1[0]*length1;
  point1[1] = origin[1] + v1[1]*length1;
  point1[2] = origin[2] + v1[2]*length1;

  point2[0] = origin[0] + v2[0]*length2;
  point2[1] = origin[1] + v2[1]*length2;
  point2[2] = origin[2] + v2[2]*length2;

  //Create bezier surface according to initial plane
  vtkNew<vtkPlaneSource> planeSource;
  planeSource->SetOrigin(origin);
  planeSource->SetPoint1(point1);
  planeSource->SetPoint2(point2);
  planeSource->SetXResolution(3);
  planeSource->SetYResolution(3);
  planeSource->Update();

  auto initializationToBezier =
    this->InitializationToBezierMap.find(initializationNode);
  if (initializationToBezier == this->InitializationToBezierMap.end())
    {
    vtkErrorMacro("Error UpdateBezierWidgetOnInitialization: Initialization node does not have a corresponding bezier markups node.");
    return;
    }


  auto bezierSurfaceNode = initializationToBezier->second;
  if (!bezierSurfaceNode)
    {
    vtkErrorMacro("Error UpdateBezierWidgetOnInitialization: Initialization node does not have a valid corresponding bezier markups node.");
    return;
    }

  // Transfer the control points to the resection node
  bezierSurfaceNode->RemoveAllControlPoints();
  auto planeControlPoints = planeSource->GetOutput()->GetPoints();
  bezierSurfaceNode->SetControlPointPositionsWorld(planeControlPoints);

  auto bezierDisplayNode = bezierSurfaceNode->GetDisplayNode();
  if (!bezierDisplayNode)
    {
    vtkErrorMacro("Error UpdateBezierWidgetOnInitialization: Bezier markups node does not have a valid display node.");
    return;
    }

  bezierDisplayNode->VisibilityOn();
}

//------------------------------------------------------------------------------
vtkMRMLMarkupsNode* vtkSlicerLiverResectionsLogic::AddInitializationMarkupsNode(vtkMRMLLiverResectionNode* resectionNode) const
{
  vtkMRMLMarkupsNode* initializationMarkupsNode = nullptr;

  switch(resectionNode->GetInitMode())
    {
    case vtkMRMLLiverResectionNode::Curved:
      initializationMarkupsNode = this->AddResectionContour(resectionNode);
      break;

    case vtkMRMLLiverResectionNode::Flat:
      initializationMarkupsNode = this->AddResectionPlane(resectionNode);
      break;
    }

  if (!initializationMarkupsNode)
    {
    return nullptr;
    }

  initializationMarkupsNode->SetHideFromEditors(false);
  initializationMarkupsNode->GetDisplayNode()->SetVisibility(true); // Initially visible

  return initializationMarkupsNode;
}

//------------------------------------------------------------------------------
void vtkSlicerLiverResectionsLogic::CreateInitializationAndResectionMarkups(vtkMRMLLiverResectionNode* resectionNode)
{
  // Create the relevant initialization node
  vtkMRMLMarkupsNode *initializationMarkupsNode = this->AddInitializationMarkupsNode(resectionNode);

  // Register the resection-initialization association
  this->ResectionToInitializationMap[resectionNode] = initializationMarkupsNode;
  this->InitializationToResectionMap[initializationMarkupsNode] = resectionNode;

  // Create the associated bezier surface
  vtkMRMLMarkupsBezierSurfaceNode* markupsBezierNode = this->AddBezierSurface(resectionNode);
  this->ResectionToBezierMap[resectionNode] = markupsBezierNode;
  this->BezierToResectionMap[markupsBezierNode] = resectionNode;

  //Add callbacks dealing with the coordination of the resection representation,
  //this is, whether the resection is visualized as contour, contour + bezier or
  //bezier.
  vtkNew<vtkIntArray> nodeEvents;
  nodeEvents->InsertNextValue(vtkCommand::StartInteractionEvent);
  nodeEvents->InsertNextValue(vtkCommand::EndInteractionEvent);
  vtkUnObserveMRMLNodeMacro(markupsBezierNode);
  vtkUnObserveMRMLNodeMacro(initializationMarkupsNode);
  vtkObserveMRMLNodeEventsMacro(markupsBezierNode, nodeEvents.GetPointer());
  vtkObserveMRMLNodeEventsMacro(initializationMarkupsNode, nodeEvents.GetPointer());

  this->InitializationToBezierMap[initializationMarkupsNode] = markupsBezierNode;
  this->BezierToInitializationMap[markupsBezierNode] = initializationMarkupsNode;
}

//------------------------------------------------------------------------------
char* vtkSlicerLiverResectionsLogic::LoadLiverResection(const std::string& fileName,
                                                   const std::string& nodeName/*=nullptr*/,
                                                   vtkMRMLMessageCollection* userMessages/*=nullptr*/)
{
  if (fileName == "")
    {
    vtkErrorMacro("vtkSlicerLiverResectionsLogic::LoadResections failed: invalid fileName");
    return nullptr;
    }

  // get file extension
  std::string extension = vtkMRMLStorageNode::GetLowercaseExtensionFromFileName(fileName);
  if( extension.empty() )
    {
    vtkErrorMacro("vtkSlicerLiverResectionsLogic::LoadResections failed: no file extension specified: " << fileName);
    return nullptr;
    }

  // if (extension == std::string(".json"))
  //   {
  //   return this->LoadLiverResectionsFromJson(fileName, nodeName, userMessages);
  //   }
  /*else */if (extension == std::string(".fcsv"))
    {
    return this->LoadLiverResectionFromFcsv(fileName, nodeName, userMessages);
    }
  else
    {
    vtkErrorMacro("vtkSlicerLiverResectionsLogic::LoadResections failed: unrecognized file extension in " << fileName);
    return nullptr;
    }
}

//---------------------------------------------------------------------------
char *vtkSlicerLiverResectionsLogic::LoadLiverResectionFromFcsv(const std::string &fileName,
                                                                 const std::string &nodeName /*=nullptr*/,
                                                                 vtkMRMLMessageCollection *userMessages /*=nullptr*/)
{

  if (fileName == "") {
    vtkErrorMacro(
        "LoadLiverResections: null file or markups class name, cannot load");
    return nullptr;
  }

  vtkDebugMacro("LoadLiverResections, file name = "
                << fileName << ", nodeName = " << nodeName);
  // make a storage node and fiducial node and set the file name
  auto storageNode =
      vtkMRMLStorageNode::SafeDownCast(this->GetMRMLScene()->AddNewNodeByClass(
          "vtkMRMLLiverResectionCSVStorageNode"));
  if (!storageNode) {
    vtkErrorMacro("LoadLiverResections: failed to instantiate markups storage "
                  "node by class vtkMRMLLiverResectionsFiducialNode");
    return nullptr;
  }

  std::string newNodeName;
  if (nodeName.length() > 0) {
    newNodeName = nodeName;
  } else {
    newNodeName = this->GetMRMLScene()->GetUniqueNameByString(
        storageNode->GetFileNameWithoutExtension(fileName.c_str()).c_str());
  }
  auto bezierNode = vtkMRMLMarkupsBezierSurfaceNode::SafeDownCast(
      this->GetMRMLScene()->AddNewNodeByClass(
          "vtkMRMLMarkupsBezierSurfaceNode"));
  if (!bezierNode) {
    vtkErrorMacro(
        "LoadLiverResections: failed to instantiate markups bezier node by "
        "class vtkMRMLLiverResectionFiducialNode");
    if (userMessages) {
      userMessages->AddMessages(storageNode->GetUserMessages());
    }
  }
  bezierNode->SetHideFromEditors(true);

  auto markupsNode = vtkMRMLLiverResectionNode::SafeDownCast(
      this->GetMRMLScene()->AddNewNodeByClass("vtkMRMLLiverResectionNode",
                                              newNodeName));
  if (!markupsNode) {
    vtkErrorMacro("LoadLiverResections: failed to instantiate liver "
                  "resection markups node by "
                  "class vtkMRMLLiverResectionsNode");
    if (userMessages) {
      userMessages->AddMessages(storageNode->GetUserMessages());
    }
    this->GetMRMLScene()->RemoveNode(storageNode);
    return nullptr;
    }

    markupsNode->SetBezierSurfaceNode(bezierNode);

    storageNode->SetFileName(fileName.c_str());
    // add the nodes to the scene and set up the observation on the storage node
    markupsNode->SetAndObserveStorageNodeID(storageNode->GetID());

    // read the file
    char *nodeID = nullptr;
    if (storageNode->ReadData(markupsNode))
      {
      nodeID = markupsNode->GetID();
      }
    else
      {
      if (userMessages)
        {
        userMessages->AddMessages(storageNode->GetUserMessages());
        }
      this->GetMRMLScene()->RemoveNode(storageNode);
      this->GetMRMLScene()->RemoveNode(markupsNode);
    }

    return nodeID;
  }

void vtkSlicerLiverResectionsLogic::ComputeAdvancedPlanningVolumetry(vtkCollection* resectionNodes, vtkMRMLScalarVolumeNode* TargetSegmentLabelMap, vtkMRMLTableNode* OutputTableNode, vtkMRMLMarkupsFiducialNode* ROIMarkersList, vtkMRMLLabelMapVolumeNode* VascularSegments) {
  vtkLabelMapHelper::LabelMapType::RegionType TargetSegmentBoundingBox;
  vtkLabelMapHelper::LabelMapType::Pointer TargetSegmentITKImage;
  double spacing[3];
  auto VolumeTable = vtkSmartPointer<vtkTable>::New();

  if (!OutputTableNode)
    {
    vtkErrorMacro(<< "No output table node is assigned,"
                    << "create and choose a table node first");
    return;
    }

  if (this->OutputTableNode != OutputTableNode)
    {
    this->OutputTableNode = vtkSmartPointer<vtkMRMLTableNode>::New();
    this->OutputTableNode = OutputTableNode;
    }

  VolumeTable = this->OutputTableNode->GetTable();

  // Project segment from vtkImage to itkImage
  // need deep copy the label map
  vtkSmartPointer<vtkImageData> TargetSegmentImageDataCopy = vtkSmartPointer<vtkImageData>::New();
  TargetSegmentImageDataCopy->DeepCopy(TargetSegmentLabelMap->GetImageData());
  vtkSmartPointer<vtkMRMLScalarVolumeNode> TargetSegmentLabelMapCopy = vtkSmartPointer<vtkMRMLScalarVolumeNode>::New();
  TargetSegmentLabelMapCopy->CopyOrientation(TargetSegmentLabelMap);
  TargetSegmentLabelMapCopy->SetAndObserveImageData(TargetSegmentImageDataCopy);

  TargetSegmentITKImage = vtkLabelMapHelper::VolumeNodeToItkImage(TargetSegmentLabelMapCopy);
  TargetSegmentBoundingBox = vtkLabelMapHelper::GetBoundingBox(TargetSegmentITKImage);
  spacing[0] = TargetSegmentITKImage->GetSpacing()[0];
  spacing[1] = TargetSegmentITKImage->GetSpacing()[1];
  spacing[2] = TargetSegmentITKImage->GetSpacing()[2];
  auto TargetSegmentVoxels = vtkLabelMapHelper::CountVoxels(TargetSegmentITKImage, TargetSegmentBoundingBox, 1);
  auto TargetSegmentVolume = TargetSegmentVoxels*spacing[0]*spacing[1]*spacing[2]*0.001;

  bool resectionNodeChanged = false;
  auto BezierHR = vtkSmartPointer<vtkBezierSurfaceSource>::New();

  if (this->resectionNodes != resectionNodes and resectionNodes != nullptr)
    {
    this->resectionNodes = resectionNodes;
    resectionNodeChanged = true;
    for (int i = 0; i < resectionNodes->GetNumberOfItems(); i++)
      {
      auto resectionNode = vtkMRMLLiverResectionNode::SafeDownCast(resectionNodes->GetItemAsObject(i));
      auto bezierSurfaceNode = this->GetBezierFromResection(resectionNode);
      auto Res =  GetRes(bezierSurfaceNode, spacing, 300);
      BezierHR = GenerateBezierSurface(Res, bezierSurfaceNode);
      if(i == 0){
        this->ProjectedTargetSegmentImage =
          vtkLabelMapHelper::VolumeNodeToItkImage(TargetSegmentLabelMapCopy, true, false);
        }
      vtkLabelMapHelper::ProjectPointsOntoItkImage(this->ProjectedTargetSegmentImage,
                                                   BezierHR->GetOutput()->GetPoints(),
                                                   7,
                                                   1);
      }
    }

  if (VascularSegments)
    {
    if (this->VascularSegments != VascularSegments)
      {
      this->VascularSegments = vtkSmartPointer<vtkMRMLLabelMapVolumeNode>::New();
      this->VascularSegments = VascularSegments;
      this->itkVascularSegments = nullptr;
      this->itkVascularSegments = vtkLabelMapHelper::VolumeNodeToItkImage(this->VascularSegments, true, false);
      this->itkVascularSegments->SetRequestedRegion(TargetSegmentBoundingBox);
      }
    }

  if (ROIMarkersList)
    {
    int ReplaceValue = 100;
    int TotalCount = 0;
    std::vector<vtkLabelMapHelper::LabelMapType::IndexType> seedIndexLists;
    auto num = ROIMarkersList->GetNumberOfControlPoints();
    vtkSmartPointer<vtkLabelMapHelper> labelMapHelper = vtkSmartPointer<vtkLabelMapHelper>::New();
    for (int i = 0; i < num; i++)
      {
      auto point = ROIMarkersList->GetNthControlPointPosition(i);
      auto pointLabel = ROIMarkersList->GetNthControlPointLabel(i);

      this->connectedThreshold = nullptr;
      if(resectionNodes != nullptr)
        {
        auto seedIndex = GetITKRGSeedIndex(point, this->ProjectedTargetSegmentImage);
        this->connectedThreshold = labelMapHelper->ConnectedThreshold(this->ProjectedTargetSegmentImage, 1, 6, ReplaceValue, seedIndex);
        }

      if(!VascularSegments){
        int CountValues;
        if(resectionNodes != nullptr){
          CountValues = vtkLabelMapHelper::CountVoxels(this->connectedThreshold,TargetSegmentBoundingBox, ReplaceValue);
          }
        else{
          CountValues = TargetSegmentVoxels;
          }
        auto ROIVolume = CountValues*spacing[0]*spacing[1]*spacing[2]*0.001;
        VolumetryTable(pointLabel, TargetSegmentVolume, ROIVolume, VolumeTable);
        TotalCount = TotalCount+CountValues;
        }
      else
        {
        auto seedIndex = GetITKRGSeedIndex(point, this->itkVascularSegments);
        typedef itk::ImageRegionConstIterator<itk::Image<short, 3> > IteratorType;
        IteratorType iterator(this->itkVascularSegments, this->itkVascularSegments->GetRequestedRegion());
        int VascularSegmentCount = 0;
        int LabelValue = this->itkVascularSegments->GetPixel(seedIndex);
        while (!iterator.IsAtEnd())
          {
          auto index = iterator.GetIndex();
          if (iterator.Get() != 0)
            {
            if(this->connectedThreshold){
              if (this->connectedThreshold->GetPixel(index) == ReplaceValue and this->itkVascularSegments->GetPixel(index) == LabelValue)
                {
                VascularSegmentCount++;
                }
              } else {
              if (this->itkVascularSegments->GetPixel(index) == LabelValue)
                {
                VascularSegmentCount++;
                }
              }
            }
          ++iterator;
          }
        auto ROIVolume = VascularSegmentCount*spacing[0]*spacing[1]*spacing[2]*0.001;
        VolumetryTable(pointLabel + "For Vascular Info", TargetSegmentVolume, ROIVolume, VolumeTable);
        TotalCount = TotalCount+VascularSegmentCount;
        }
      }
    auto TotalROIVolume = TotalCount*spacing[0]*spacing[1]*spacing[2]*0.001;
    VolumetryTable("TotalVolume of List "+ std::string(ROIMarkersList->GetName()), TargetSegmentVolume, TotalROIVolume, VolumeTable);
    }
}

vtkSmartPointer<vtkBezierSurfaceSource> vtkSlicerLiverResectionsLogic::GenerateBezierSurface(int Res, vtkMRMLMarkupsBezierSurfaceNode* bezierSurfaceNode){
  if (!bezierSurfaceNode)
    {
    return nullptr;
    }
  auto Bezier = vtkSmartPointer<vtkBezierSurfaceSource>::New();
  Bezier->SetResolution(Res,Res);
  Bezier->SetNumberOfControlPoints(4,4);
  if (bezierSurfaceNode->GetNumberOfControlPoints() == 16)
    {
    auto BezierSurfaceControlPoints = vtkSmartPointer<vtkPoints>::New();
    for (int i=0; i<16; i++)
      {
      double point[3];
      bezierSurfaceNode->GetNthControlPointPosition(i,point);
      BezierSurfaceControlPoints->InsertNextPoint(static_cast<float>(point[0]),
                                                  static_cast<float>(point[1]),
                                                  static_cast<float>(point[2]));
      }
    Bezier->SetControlPoints(BezierSurfaceControlPoints);
    Bezier->Update();
    }
  return Bezier;
}

//get itkImage region growing seed index
itk::Index<3> vtkSlicerLiverResectionsLogic::GetITKRGSeedIndex(double* ROISeedPoint, itk::SmartPointer<itk::Image<short,3>> SourceImage){
  vtkSmartPointer<vtkLabelMapHelper> labelMapHelper = vtkSmartPointer<vtkLabelMapHelper>::New();
  vtkLabelMapHelper::LabelMapType::IndexType seedIndex;
  vtkLabelMapHelper::LabelMapType::PointType seedPoint;
  seedPoint[0] = ROISeedPoint[0];
  seedPoint[1] = ROISeedPoint[1];
  seedPoint[2] = ROISeedPoint[2];
  SourceImage->TransformPhysicalPointToIndex(seedPoint, seedIndex);
  return seedIndex;
}

void vtkSlicerLiverResectionsLogic::VolumetryTable(std::string Properties, double TargetSegmentVolume, double ROIVolume, vtkTable *VolumeTable, int line){
  if(this->OutputTableNode->GetNumberOfColumns() == 0 ){
    auto LabelCol = vtkSmartPointer<vtkStringArray>::New();
    LabelCol->SetName("Properties");
    auto TargetSegmentVolumeCol = vtkSmartPointer<vtkDoubleArray>::New();
    TargetSegmentVolumeCol->SetName("Target Segment Volume");
    auto ROIVolumeCol = vtkSmartPointer<vtkDoubleArray>::New();
    ROIVolumeCol->SetName("ROI Volume");
//    auto RemnantVolumeCol = vtkSmartPointer<vtkDoubleArray>::New();
//    RemnantVolumeCol->SetName("Remnant Volume");
    auto RemnantPercentageCol = vtkSmartPointer<vtkStringArray>::New();
    RemnantPercentageCol->SetName("ROI Percentage");

    LabelCol->InsertNextValue(Properties);
    TargetSegmentVolumeCol->InsertNextValue(TargetSegmentVolume);
    ROIVolumeCol->InsertNextValue(ROIVolume);
//    auto remnant = TargetSegmentVolume - ROIVolume;
//    RemnantVolumeCol->InsertNextValue(remnant);
    RemnantPercentageCol->InsertNextValue(std::to_string(ROIVolume/TargetSegmentVolume * 100)+"%");

    VolumeTable->AddColumn(LabelCol);
    VolumeTable->AddColumn(TargetSegmentVolumeCol);
    VolumeTable->AddColumn(ROIVolumeCol);
//    VolumeTable->AddColumn(RemnantVolumeCol);
    VolumeTable->AddColumn(RemnantPercentageCol);
    }
  else
    {
    line = this->OutputTableNode->GetNumberOfRows();
    VolumeTable->InsertRow(line);
    VolumeTable->GetColumn(0)->SetVariantValue(line, static_cast<vtkStdString>(Properties));
    VolumeTable->GetColumn(1)->SetVariantValue(line,TargetSegmentVolume);
    VolumeTable->GetColumn(2)->SetVariantValue(line,ROIVolume);
//    auto remnant = TargetSegmentVolume - ROIVolume;
//    VolumeTable->GetColumn(3)->SetVariantValue(line,remnant);
    VolumeTable->GetColumn(3)->SetVariantValue(line,static_cast<vtkStdString>(std::to_string(ROIVolume/TargetSegmentVolume * 100)+"%"));
    this->OutputTableNode->Modified();
    }
}

int vtkSlicerLiverResectionsLogic::GetRes(vtkMRMLMarkupsBezierSurfaceNode* bezierSurfaceNode, double space[3], int Steps){
//BezierCurve computation inspired from https://medium.com/geekculture/2d-and-3d-b%C3%A9zier-curves-in-c-499093ef45a9

  std::vector<std::vector<int>> ControlPointsIndexs{{3,6,9,12},{0,5,10,15}};
  double ArcLength[2];

  for (int l = 0; l < 2; l++){
    auto DataArray = vtkSmartPointer<vtkDoubleArray>::New();
    DataArray->SetNumberOfComponents(3);
    DataArray->SetNumberOfTuples(Steps);
    ArcLength[l] = 0.0;
    std::vector<double> bezierCurveX;
    std::vector<double> bezierCurveY;
    std::vector<double> bezierCurveZ;
    std::vector<double> ControlPointsX;
    std::vector<double> ControlPointsY;
    std::vector<double> ControlPointsZ;

    for (int p = 0; p<ControlPointsIndexs[l].size();p++){
      double point[3];
      bezierSurfaceNode->GetNthControlPointPosition(ControlPointsIndexs[l][p],point);
      ControlPointsX.push_back(point[0]);
      ControlPointsY.push_back(point[1]);
      ControlPointsZ.push_back(point[2]);
      }

    for (int i=0; i<Steps; i++){
      double t, point[3];
      t = i / static_cast<double>(Steps - 1);
      point[0] = std::pow((1 - t), 3) * ControlPointsX[0] + 3 * std::pow((1 - t), 2) * t * ControlPointsX[1] + 3 * std::pow((1 - t), 1) * std::pow(t, 2) * ControlPointsX[2] + std::pow(t, 3) * ControlPointsX[3];
      point[1] = std::pow((1 - t), 3) * ControlPointsY[0] + 3 * std::pow((1 - t), 2) * t * ControlPointsY[1] + 3 * std::pow((1 - t), 1) * std::pow(t, 2) * ControlPointsY[2] + std::pow(t, 3) * ControlPointsY[3];
      point[2] = std::pow((1 - t), 3) * ControlPointsZ[0] + 3 * std::pow((1 - t), 2) * t * ControlPointsZ[1] + 3 * std::pow((1 - t), 1) * std::pow(t, 2) * ControlPointsZ[2] + std::pow(t, 3) * ControlPointsZ[3];
      DataArray->SetTuple(i, point);
      }

    for (int i=1; i<Steps; i++){
      double point0[3], point1[3];
      DataArray->GetTuple(i, point1);
      DataArray->GetTuple(i-1, point0);
      double len = sqrt(pow(point0[0]-point1[0], 2.0) + pow(point0[1]-point1[1], 2.0) + pow(point0[2]-point1[2], 2.0));
      ArcLength[l] = ArcLength[l] + len;
      }
    }

  double len = (ArcLength[0]>ArcLength[1]) ? ArcLength[0]:ArcLength[1];
  double min = std::min(space[0], space[1]);
  min = std::min(min, space[2]);
  int res = len/min;

  return res;
}
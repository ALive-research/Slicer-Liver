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

  This file was originally developed by Rafael Palomar (Oslo University,
  Hospital and NTNU) and was supported by The Research Council of Norway
  through the ALive project (grant nr. 311393).

==============================================================================*/

//NOTE: Some of the functions of this file are inspired in vtkSlicerMarkupsLogic

#include "vtkSlicerLiverResectionsLogic.h"
#include "vtkMRMLAbstractLogic.h"

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

//----------------------------------------------------------------------------
vtkStandardNewMacro(vtkSlicerLiverResectionsLogic);

//---------------------------------------------------------------------------
vtkSlicerLiverResectionsLogic::vtkSlicerLiverResectionsLogic()
{

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
    auto bezierSurfaceNode = this->GetBezierFromResection(resectionNode);
    if (bezierSurfaceNode)
      {
      bezierSurfaceNode->SetDistanceMapVolumeNode(resectionNode->GetDistanceMapVolumeNode());
      bezierSurfaceNode->SetDistanceMargin(resectionNode->GetResectionMargin());
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

  auto distanceContourNode = vtkSmartPointer<vtkMRMLMarkupsDistanceContourNode>::New();
  distanceContourNode->AddControlPoint(p1);
  distanceContourNode->AddControlPoint(p2);
  distanceContourNode->SetTarget(resectionNode->GetTargetOrganModelNode());

  auto distanceContourDisplayNode = vtkSmartPointer<vtkMRMLMarkupsDisplayNode>::New();
  distanceContourDisplayNode->PropertiesLabelVisibilityOff();
  distanceContourDisplayNode->SetSnapMode(vtkMRMLMarkupsDisplayNode::SnapModeUnconstrained);

  mrmlScene->AddNode(distanceContourDisplayNode);
  distanceContourNode->SetAndObserveDisplayNodeID(distanceContourDisplayNode->GetID());
  mrmlScene->AddNode(distanceContourNode);

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
  if (bezierSurfaceDisplayNode)
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
    case vtkMRMLLiverResectionNode::Flat:
      initializationMarkupsNode = this->AddResectionPlane(resectionNode);
      break;

    case vtkMRMLLiverResectionNode::Curved:
      initializationMarkupsNode = this->AddResectionContour(resectionNode);
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

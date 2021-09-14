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

  This file was originally developed by Rafael Palomar (The Intervention Centre,
  Oslo University Hospital) and was supported by The Research Council of Norway
  through the ALive project (grant nr. 311393).

==============================================================================*/
#include "vtkSlicerLiverResectionsLogic.h"

#include <vtkMRMLMarkupsSlicingContourNode.h>
#include <vtkMRMLMarkupsDistanceContourNode.h>
#include <vtkMRMLMarkupsDisplayNode.h>
#include <vtkMRMLLiverResectionNode.h>

// MRML includes
#include <vtkMRMLScene.h>
#include <vtkMRMLSelectionNode.h>

// VTK includes
#include <vtkObjectFactory.h>
#include <vtkCollection.h>

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
void vtkSlicerLiverResectionsLogic::ObserveMRMLScene()
{
  if (!this->GetMRMLScene())
    {
    return;
    }

 this->Superclass::ObserveMRMLScene();
}

//---------------------------------------------------------------------------
void vtkSlicerLiverResectionsLogic::OnMRMLSceneNodeAdded(vtkMRMLNode* node)
{
  Superclass::OnMRMLSceneNodeAdded(node);
}


//---------------------------------------------------------------------------
void vtkSlicerLiverResectionsLogic::AddResectionPlane(vtkMRMLModelNode *targetParenchymaModelNode)
{
  auto mrmlScene = this->GetMRMLScene();
  if (!mrmlScene)
    {
      vtkErrorMacro("Error in AddResectionPlane: no valid MRML scene.");
      return;
    }

  if (!targetParenchymaModelNode)
    {
      vtkErrorMacro("Error in AddResectionPlane: invalid internal target parenchyma.");
      return;
    }

  auto targetParenchymaPolyData = targetParenchymaModelNode->GetPolyData();
  if (!targetParenchymaPolyData)
    {
      vtkErrorMacro("Error in AddResectionPlane: target liver model does not contain valid polydata.");
      return;
    }

  // Computing the position of the initial points
  const double *bounds = targetParenchymaPolyData->GetBounds();
  auto p1 = vtkVector3d(bounds[0],(bounds[3]-bounds[2])/2.0, (bounds[5]-bounds[4])/2.0);
  auto p2 = vtkVector3d(bounds[1],(bounds[3]-bounds[2])/2.0, (bounds[5]-bounds[4])/2.0);

  auto slicingContourNode = vtkSmartPointer<vtkMRMLMarkupsSlicingContourNode>::New();
  slicingContourNode->AddControlPoint(p1);
  slicingContourNode->AddControlPoint(p2);
  slicingContourNode->SetTarget(targetParenchymaModelNode);

  auto slicingContourDisplayNode = vtkSmartPointer<vtkMRMLMarkupsDisplayNode>::New();
  slicingContourDisplayNode->PropertiesLabelVisibilityOff();
  slicingContourDisplayNode->SetSnapMode(vtkMRMLMarkupsDisplayNode::SnapModeUnconstrained);

  mrmlScene->AddNode(slicingContourDisplayNode);
  slicingContourNode->SetAndObserveDisplayNodeID(slicingContourDisplayNode->GetID());
  mrmlScene->AddNode(slicingContourNode);
}

//---------------------------------------------------------------------------
void vtkSlicerLiverResectionsLogic::AddResectionContour(vtkMRMLModelNode *targetParenchymaModelNode,
                                                        vtkCollection *targetTumor)
{
  auto mrmlScene = this->GetMRMLScene();
  if (!mrmlScene)
    {
    vtkErrorMacro("Error in AddResectionSlicingContour: no valid MRML scene.");
    return;
    }

  // if (!targetParenchymaModelNode)
  //   {
  //   vtkErrorMacro("Error in AddResectionSlicingContour: no target liver model provided.");
  //   return;
  //   }

  // auto targetParenchymaPolyData = targetParenchymaModelNode->GetPolyData();
  // if (!targetParenchymaPolyData)
  //   {
  //   vtkErrorMacro("Error in AddResectionSlicingContour: target liver model does not contain valid polydata.");
  //   return;
  //   }

  // // Computing the position of the initial points
  // const double *bounds = targetParenchymaPolyData->GetBounds();

  // auto p1 = vtkVector3d(bounds[0],(bounds[3]-bounds[2])/2.0, (bounds[5]-bounds[4])/2.0);
  // auto p2 = vtkVector3d((bounds[1]-bounds[0])/2.0,(bounds[3]-bounds[2])/2.0, (bounds[5]-bounds[4])/2.0);

  // auto distanceContourNode = vtkSmartPointer<vtkMRMLMarkupsDistanceContourNode>::New();
  // distanceContourNode->AddControlPoint(p1);
  // distanceContourNode->AddControlPoint(p2);
  // distanceContourNode->SetTarget(targetParenchymaModelNode);

  // auto distanceContourDisplayNode = vtkSmartPointer<vtkMRMLMarkupsDisplayNode>::New();
  // distanceContourDisplayNode->PropertiesLabelVisibilityOff();
  // distanceContourDisplayNode->SetSnapMode(vtkMRMLMarkupsDisplayNode::SnapModeUnconstrained);

  // mrmlScene->AddNode(distanceContourDisplayNode);
  // distanceContourNode->SetAndObserveDisplayNodeID(distanceContourDisplayNode->GetID());
  // mrmlScene->AddNode(distanceContourNode);

  mrmlScene->AddNewNodeByClass("vtkMRMLLiverResectionNode");

}


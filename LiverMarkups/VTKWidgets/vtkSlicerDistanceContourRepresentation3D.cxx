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

  * Neither the name of Oslo University Hospital nor the names
    of Contributors may be used to endorse or promote products derived
    from this software without specific prior written permission.

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
  Hospital and NTNU) and was supported by The Research Council of Norway
  through the ALive project (grant nr. 311393).

  ==============================================================================*/

#include "vtkSlicerDistanceContourRepresentation3D.h"

#include "vtkMRMLMarkupsDistanceContourNode.h"
#include "vtkMRMLMarkupsDistanceContourDisplayNode.h"
#include "vtkOpenGLDistanceContourPolyDataMapper.h"

// MRML includes
#include <qMRMLThreeDWidget.h>
#include <vtkMRMLDisplayableManagerGroup.h>
#include <vtkMRMLModelDisplayableManager.h>

// Slicer includes
#include <qSlicerApplication.h>
#include <qSlicerLayoutManager.h>

// VTK includes
#include <vtkActor.h>
#include <vtkCollection.h>
#include <vtkMath.h>
#include <vtkOpenGLActor.h>
#include <vtkPolyDataMapper.h>
#include <vtkProperty.h>
#include <vtkShaderProperty.h>
#include <vtkUniforms.h>

#include <cmath>
//------------------------------------------------------------------------------
vtkStandardNewMacro(vtkSlicerDistanceContourRepresentation3D);

//------------------------------------------------------------------------------
vtkSlicerDistanceContourRepresentation3D::vtkSlicerDistanceContourRepresentation3D()
  :Superclass(), Target(nullptr)
{
  this->DistanceContourMapper = vtkSmartPointer<vtkOpenGLDistanceContourPolyDataMapper>::New();
  this->DistanceContourActor = vtkSmartPointer<vtkOpenGLActor>::New();
  this->DistanceContourActor->SetMapper(this->DistanceContourMapper);
  this->SphereSource = vtkSmartPointer<vtkSphereSource>::New();
  this->SphereSource->SetThetaResolution(20);
  this->SphereSource->SetPhiResolution(20);
  this->SphereSource->SetRadius(30);
  this->SphereMapper = vtkSmartPointer<vtkPolyDataMapper>::New();
  this->SphereMapper->SetInputConnection(this->SphereSource->GetOutputPort());
  this->SphereActor = vtkSmartPointer<vtkActor>::New();
  this->SphereActor->SetMapper(this->SphereMapper);
  this->SphereActor->GetProperty()->SetOpacity(0.2);
}

//------------------------------------------------------------------------------
vtkSlicerDistanceContourRepresentation3D::~vtkSlicerDistanceContourRepresentation3D() = default;

//------------------------------------------------------------------------------
void vtkSlicerDistanceContourRepresentation3D::PrintSelf(ostream& os, vtkIndent indent)
{
  Superclass::PrintSelf(os, indent);
}

//----------------------------------------------------------------------
void vtkSlicerDistanceContourRepresentation3D::UpdateFromMRML(vtkMRMLNode* caller, unsigned long event, void *callData /*=nullptr*/)
{

 this->Superclass::UpdateFromMRML(caller, event, callData);

 auto liverMarkupsDistanceContourNode =
   vtkMRMLMarkupsDistanceContourNode::SafeDownCast(this->GetMarkupsNode());
 if (!liverMarkupsDistanceContourNode)
   {
   vtkWarningMacro("Invalid distance contour node.");
   return;
   }

 auto targetModelNode = liverMarkupsDistanceContourNode->GetTarget();

 // // If the target model node has changed -> Reassign the contour shader
 if (targetModelNode != this->Target)
   {
   this->Target = targetModelNode;
   if (this->Target)
     {
     this->DistanceContourMapper->SetInputConnection(this->Target->GetPolyDataConnection());
     }
   }

  auto liverMarkupsDistanceContourDisplayNode =
      vtkMRMLMarkupsDistanceContourDisplayNode::SafeDownCast(
          liverMarkupsDistanceContourNode->GetDisplayNode());

  if (!liverMarkupsDistanceContourDisplayNode) {
    vtkWarningMacro("Invalid vtkMRMLMarkupsDistanceContourDisplayNode.");
    return;
  }

 if (liverMarkupsDistanceContourNode->GetNumberOfControlPoints() != 2)
   {
   return;
   }

 // Recalculate the middle plane and update the shader parameters
 double point1Position[3] = {0.0, 0.0, 0.0};
 double point2Position[3] = {0.0, 0.0, 0.0};

 liverMarkupsDistanceContourNode->GetNthControlPointPosition(0, point1Position);
 liverMarkupsDistanceContourNode->GetNthControlPointPosition(1, point2Position);

 std::array<float, 4> externalPoint = {static_cast<float>(point1Position[0]),
                                       static_cast<float>(point1Position[1]),
                                       static_cast<float>(point1Position[2]), 1.0f};

 std::array<float, 4> referencePoint = {static_cast<float>(point2Position[0]),
                                        static_cast<float>(point2Position[1]),
                                        static_cast<float>(point2Position[2]), 1.0f};

 this->DistanceContourMapper->SetExternalPoint(externalPoint);
 this->DistanceContourMapper->SetReferencePoint(referencePoint);
 this->DistanceContourMapper->SetContourThickness(2.0f);
 this->DistanceContourMapper->SetContourVisibility(true);

 //TODO: Maybe externalPoint and referencePoint should be double to avoid conversions
 this->SphereSource->SetCenter(referencePoint.data()[0],
                               referencePoint.data()[1],
                               referencePoint.data()[2]);
 this->SphereSource->SetRadius(sqrt(vtkMath::Distance2BetweenPoints(externalPoint.data(),
                                                                    referencePoint.data())));


 this->NeedToRenderOn();
}

//----------------------------------------------------------------------
void vtkSlicerDistanceContourRepresentation3D::GetActors(vtkPropCollection *pc) {
  this->Superclass::GetActors(pc);
  this->DistanceContourActor->GetActors(pc);
  this->SphereActor->GetActors(pc);
}

//----------------------------------------------------------------------
void vtkSlicerDistanceContourRepresentation3D::ReleaseGraphicsResources(
    vtkWindow *win) {
  this->Superclass::ReleaseGraphicsResources(win);
  this->DistanceContourActor->ReleaseGraphicsResources(win);
  this->SphereActor->ReleaseGraphicsResources(win);
}

//----------------------------------------------------------------------
int vtkSlicerDistanceContourRepresentation3D::RenderOverlay(
    vtkViewport *viewport) {
  int count = 0;
  count = this->Superclass::RenderOverlay(viewport);
  if (this->DistanceContourActor->GetVisibility()) {
    count += this->DistanceContourActor->RenderOverlay(viewport);
    count += this->SphereActor->RenderOverlay(viewport);
  }
  return count;
}

//-----------------------------------------------------------------------------
int vtkSlicerDistanceContourRepresentation3D::RenderOpaqueGeometry(
    vtkViewport *viewport) {
  int count = 0;
  count = this->Superclass::RenderOpaqueGeometry(viewport);
  if (this->DistanceContourActor->GetVisibility()) {
    count += this->DistanceContourActor->RenderOpaqueGeometry(viewport);
    count += this->SphereActor->RenderOpaqueGeometry(viewport);
  }
  return count;
}

//-----------------------------------------------------------------------------
int vtkSlicerDistanceContourRepresentation3D::RenderTranslucentPolygonalGeometry(
    vtkViewport *viewport) {
  int count = 0;
  count = this->Superclass::RenderTranslucentPolygonalGeometry(viewport);
  if (this->DistanceContourActor->GetVisibility()) {
    // The internal actor needs to share property keys.
    // This ensures the mapper state is consistent and allows depth peeling to
    // work as expected.
    this->DistanceContourActor->SetPropertyKeys(this->GetPropertyKeys());
    count +=
        this->DistanceContourActor->RenderTranslucentPolygonalGeometry(viewport);
  }

  if (this->SphereActor->GetVisibility()) {
    // The internal actor needs to share property keys.
    // This ensures the mapper state is consistent and allows depth peeling to
    // work as expected.
    this->SphereActor->SetPropertyKeys(this->GetPropertyKeys());
    count +=
        this->SphereActor->RenderTranslucentPolygonalGeometry(viewport);
  }
  {
    // The internal actor needs to share property keys.
    // This ensures the mapper state is consistent and allows depth peeling to
    // work as expected.
  }
  return count;
}

//-----------------------------------------------------------------------------
vtkTypeBool
vtkSlicerDistanceContourRepresentation3D::HasTranslucentPolygonalGeometry() {
  if (this->Superclass::HasTranslucentPolygonalGeometry()) {
    return true;
  }
  if (this->DistanceContourActor->GetVisibility() && this->DistanceContourActor->HasTranslucentPolygonalGeometry() ||
    this->SphereActor->GetVisibility() && this->SphereActor->HasTranslucentPolygonalGeometry() ) {
    return true;
  }

  { return true; }
  return false;
}

//----------------------------------------------------------------------
double *vtkSlicerDistanceContourRepresentation3D::GetBounds() {
  vtkBoundingBox boundingBox;
  const std::vector<vtkProp *> actors({this->DistanceContourActor});
  this->AddActorsBounds(boundingBox, actors, Superclass::GetBounds());
  boundingBox.GetBounds(this->Bounds);
  return this->Bounds;
}

//-----------------------------------------------------------------------------
// void vtkSlicerDistanceContourRepresentation3D::UpdateInteractionPipeline()
// {
//   if (!this->MarkupsNode ||
//   this->MarkupsNode->GetNumberOfDefinedControlPoints(true) < 16)
//     {
//     this->InteractionPipeline->Actor->SetVisibility(false);
//     return;
//     }
//   // Final visibility handled by superclass in
//   vtkSlicerMarkupsWidgetRepresentation
//   Superclass::UpdateInteractionPipeline();
// }

//----------------------------------------------------------------------
void vtkSlicerDistanceContourRepresentation3D::UpdateDistanceContourDisplay(vtkMRMLLiverMarkupsDistanceContourNode *node)
{

}

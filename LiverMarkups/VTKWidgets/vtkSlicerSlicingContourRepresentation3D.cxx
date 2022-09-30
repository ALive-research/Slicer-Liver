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

#include "vtkSlicerSlicingContourRepresentation3D.h"

#include "vtkMRMLMarkupsSlicingContourDisplayNode.h"
#include "vtkMRMLMarkupsSlicingContourNode.h"

// MRML includes
#include <qMRMLThreeDWidget.h>
#include <vtkMRMLDisplayableManagerGroup.h>
#include <vtkMRMLModelDisplayableManager.h>

// Slicer includes
#include <qSlicerApplication.h>
#include <qSlicerLayoutManager.h>

// VTK includes
#include <vtkCollection.h>
#include <vtkOpenGLActor.h>
#include <vtkOpenGLVertexBufferObject.h>
#include <vtkShaderProperty.h>
#include <vtkUniforms.h>

//------------------------------------------------------------------------------
vtkStandardNewMacro(vtkSlicerSlicingContourRepresentation3D);

//------------------------------------------------------------------------------
vtkSlicerSlicingContourRepresentation3D::
    vtkSlicerSlicingContourRepresentation3D()
    : Superclass(), Target(nullptr) {
  this->SlicingContourMapper =
      vtkSmartPointer<vtkOpenGLSlicingContourPolyDataMapper>::New();
  this->SlicingContourActor = vtkSmartPointer<vtkOpenGLActor>::New();
  this->SlicingContourActor->SetMapper(this->SlicingContourMapper);
}

//------------------------------------------------------------------------------
vtkSlicerSlicingContourRepresentation3D::
    ~vtkSlicerSlicingContourRepresentation3D() = default;

//------------------------------------------------------------------------------
void vtkSlicerSlicingContourRepresentation3D::PrintSelf(ostream &os,
                                                        vtkIndent indent) {
  Superclass::PrintSelf(os, indent);
}

//----------------------------------------------------------------------
void vtkSlicerSlicingContourRepresentation3D::UpdateFromMRML(
    vtkMRMLNode *caller, unsigned long event, void *callData /*=nullptr*/) {

  this->Superclass::UpdateFromMRML(caller, event, callData);

  auto liverMarkupsSlicingContourNode =
      vtkMRMLMarkupsSlicingContourNode::SafeDownCast(this->GetMarkupsNode());
  if (!liverMarkupsSlicingContourNode) {
    vtkWarningMacro("Invalid slicing contour node.");
    return;
  }

  auto targetModelNode = liverMarkupsSlicingContourNode->GetTarget();

  // If the target model node has changed -> Reassign the contour shader
  if (targetModelNode != this->Target) {
    this->Target = targetModelNode;
    if (this->Target) {
      this->SlicingContourMapper->SetInputConnection(
          this->Target->GetPolyDataConnection());
    }
  }

  auto liverMarkupsSlicingContourDisplayNode =
      vtkMRMLMarkupsSlicingContourDisplayNode::SafeDownCast(
          liverMarkupsSlicingContourNode->GetDisplayNode());

  if (!liverMarkupsSlicingContourDisplayNode) {
    vtkWarningMacro("Invalid vtkMRMLMarkupsSlicingContourDisplayNode.");
    return;
  }

  if (liverMarkupsSlicingContourNode->GetNumberOfControlPoints() != 2) {
    return;
  }

  // Recalculate the middle plane and update the shader parameters
  double point1Position[3] = {1.0f};
  double point2Position[3] = {1.0f};

  liverMarkupsSlicingContourNode->GetNthControlPointPosition(0, point1Position);
  liverMarkupsSlicingContourNode->GetNthControlPointPosition(1, point2Position);

  std::array<float, 4> planePosition = {
      static_cast<float>(point2Position[0] + point1Position[0]) / 2.0f,
      static_cast<float>(point2Position[1] + point1Position[1]) / 2.0f,
      static_cast<float>(point2Position[2] + point1Position[2]) / 2.0f, 1.0f};

  std::array<float, 4> planeNormal = {
      static_cast<float>(point2Position[0] - point1Position[0]),
      static_cast<float>(point2Position[1] - point1Position[1]),
      static_cast<float>(point2Position[2] - point1Position[2]), 1.0f};

  this->SlicingContourMapper->SetPlanePosition(planePosition);
  this->SlicingContourMapper->SetPlaneNormal(planeNormal);
  this->SlicingContourMapper->SetContourThickness(2.0f);
  this->SlicingContourMapper->SetContourVisibility(true);

  this->NeedToRenderOn();
}

//----------------------------------------------------------------------
void vtkSlicerSlicingContourRepresentation3D::GetActors(vtkPropCollection *pc) {
  this->Superclass::GetActors(pc);
  this->SlicingContourActor->GetActors(pc);
}

//----------------------------------------------------------------------
void vtkSlicerSlicingContourRepresentation3D::ReleaseGraphicsResources(
    vtkWindow *win) {
  this->Superclass::ReleaseGraphicsResources(win);
  this->SlicingContourActor->ReleaseGraphicsResources(win);
}

//----------------------------------------------------------------------
int vtkSlicerSlicingContourRepresentation3D::RenderOverlay(
    vtkViewport *viewport) {
  int count = 0;
  count = this->Superclass::RenderOverlay(viewport);
  if (this->SlicingContourActor->GetVisibility()) {
    count += this->SlicingContourActor->RenderOverlay(viewport);
  }
  return count;
}

//-----------------------------------------------------------------------------
int vtkSlicerSlicingContourRepresentation3D::RenderOpaqueGeometry(
    vtkViewport *viewport) {
  int count = 0;
  count = this->Superclass::RenderOpaqueGeometry(viewport);
  if (this->SlicingContourActor->GetVisibility()) {
    count += this->SlicingContourActor->RenderOpaqueGeometry(viewport);
  }
  return count;
}

//-----------------------------------------------------------------------------
int vtkSlicerSlicingContourRepresentation3D::RenderTranslucentPolygonalGeometry(
    vtkViewport *viewport) {
  int count = 0;
  count = this->Superclass::RenderTranslucentPolygonalGeometry(viewport);
  if (this->SlicingContourActor->GetVisibility()) {
    // The internal actor needs to share property keys.
    // This ensures the mapper state is consistent and allows depth peeling to
    // work as expected.
    this->SlicingContourActor->SetPropertyKeys(this->GetPropertyKeys());
    count +=
        this->SlicingContourActor->RenderTranslucentPolygonalGeometry(viewport);
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
vtkSlicerSlicingContourRepresentation3D::HasTranslucentPolygonalGeometry() {
  if (this->Superclass::HasTranslucentPolygonalGeometry()) {
    return true;
  }
  if (this->SlicingContourActor->GetVisibility() &&
      this->SlicingContourActor->HasTranslucentPolygonalGeometry()) {
    return true;
  }
  { return true; }
  return false;
}

//----------------------------------------------------------------------
double *vtkSlicerSlicingContourRepresentation3D::GetBounds() {
  vtkBoundingBox boundingBox;
  const std::vector<vtkProp *> actors({this->SlicingContourActor});
  this->AddActorsBounds(boundingBox, actors, Superclass::GetBounds());
  boundingBox.GetBounds(this->Bounds);
  return this->Bounds;
}

//-----------------------------------------------------------------------------
// void vtkSlicerSlicingContourRepresentation3D::UpdateInteractionPipeline()
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
void vtkSlicerSlicingContourRepresentation3D::UpdateSlicingContourDisplay(vtkMRMLLiverMarkupsSlicingContourNode *node)
{

}

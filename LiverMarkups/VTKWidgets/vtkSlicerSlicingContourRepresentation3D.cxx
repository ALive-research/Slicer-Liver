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

  This file was originally developed by Rafael Palomar (The Intervention Centre,
  Oslo University Hospital) and was supported by The Research Council of Norway
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
#include <vtkOpenGLVertexBufferObject.h>
#include <vtkShaderProperty.h>
#include <vtkUniforms.h>

//------------------------------------------------------------------------------
vtkStandardNewMacro(vtkSlicerSlicingContourRepresentation3D);

//------------------------------------------------------------------------------
vtkSlicerSlicingContourRepresentation3D::vtkSlicerSlicingContourRepresentation3D()
  :Superclass(), Target(nullptr)
{
}

//------------------------------------------------------------------------------
vtkSlicerSlicingContourRepresentation3D::~vtkSlicerSlicingContourRepresentation3D() = default;

//------------------------------------------------------------------------------
void vtkSlicerSlicingContourRepresentation3D::PrintSelf(ostream& os, vtkIndent indent)
{
  Superclass::PrintSelf(os, indent);
}

//----------------------------------------------------------------------
void vtkSlicerSlicingContourRepresentation3D::UpdateFromMRML(vtkMRMLNode* caller, unsigned long event, void *callData /*=nullptr*/)
{

 this->Superclass::UpdateFromMRML(caller, event, callData);

 auto liverMarkupsSlicingContourNode =
   vtkMRMLMarkupsSlicingContourNode::SafeDownCast(this->GetMarkupsNode());
 if (!liverMarkupsSlicingContourNode)
   {
   vtkWarningMacro("Invalid slicing contour node.");
   return;
   }

 auto targetModelNode = liverMarkupsSlicingContourNode->GetTarget();

 // If the target model node has changed -> Reassign the contour shader
 if (targetModelNode != this->Target)
   {
   this->ShaderHelper->SetTargetModelNode(targetModelNode);
   this->ShaderHelper->AttachSlicingContourShader();
   this->Target = targetModelNode;
   }

 auto liverMarkupsSlicingContourDisplayNode =
   vtkMRMLMarkupsSlicingContourDisplayNode::SafeDownCast(liverMarkupsSlicingContourNode->GetDisplayNode());

 if (!liverMarkupsSlicingContourDisplayNode)
   {
   vtkWarningMacro("Invalid vtkMRMLMarkupsSlicingContourDisplayNode.");
   return;
   }

 if (liverMarkupsSlicingContourNode->GetNumberOfControlPoints() != 2)
   {
   return;
   }

 // Recalculate the middle plane and update the shader parameters
 double point1Position[3] = {1.0f};
 double point2Position[3] = {1.0f};

 liverMarkupsSlicingContourNode->GetNthControlPointPosition(0, point1Position);
 liverMarkupsSlicingContourNode->GetNthControlPointPosition(1, point2Position);

 float middlePointPosition[3] = {
   static_cast<float>(point2Position[0] + point1Position[0]) / 2.0f,
   static_cast<float>(point2Position[1] + point1Position[1]) / 2.0f,
   static_cast<float>(point2Position[2] + point1Position[2]) / 2.0f
 };

 float planeNormal[4] = {
   static_cast<float>(point2Position[0] - point1Position[0]),
   static_cast<float>(point2Position[1] - point1Position[1]),
   static_cast<float>(point2Position[2] - point1Position[2]),
   1.0f
 };

 float planeNormalNorm = vtkMath::Normalize(planeNormal);
 planeNormal[0] /= planeNormalNorm;
 planeNormal[1] /= planeNormalNorm;
 planeNormal[2] /= planeNormalNorm;

 auto VBOs = this->ShaderHelper->GetTargetModelVertexVBOs();
 // auto actors = this->ShaderHelper->GetTargetActors();

 for(int index = 0; index < VBOs->GetNumberOfItems(); ++index)
   {
   auto VBO = vtkOpenGLVertexBufferObject::SafeDownCast(VBOs->GetItemAsObject(index));
   if(!VBO)
     {
     vtkErrorMacro("Error: could not retrieve vtkOpenGLVertexBufferObject");
     return;
     }

   //VBO->SetCoordShiftAndScaleMethod(vtkOpenGLVertexBufferObject::AUTO_SHIFT_SCALE);
   auto scale = VBO->GetScale();
   auto shift = VBO->GetShift();

   if (scale.size() != 3  || shift.size() != 3)
     {
     scale.clear();
     scale.push_back(1.0f);scale.push_back(1.0f);scale.push_back(1.0f);
     shift.clear();
     shift.push_back(0.0f);shift.push_back(0.0f);shift.push_back(0.0f);
     return;
     }

   float middlePointPositionScaled[4] = {
     static_cast<float>((middlePointPosition[0] - shift[0]) * scale[0]),
     static_cast<float>((middlePointPosition[1] - shift[1]) * scale[1]),
     static_cast<float>((middlePointPosition[2] - shift[2]) * scale[2]),
     1.0f};

   auto actor = vtkActor::SafeDownCast(this->ShaderHelper->GetTargetActors()->GetItemAsObject(index));
   auto fragmentUniforms = actor->GetShaderProperty()->GetFragmentCustomUniforms();
   fragmentUniforms->SetUniform4f("planePositionMC", middlePointPositionScaled);
   fragmentUniforms->SetUniform4f("planeNormalMC", planeNormal);
   fragmentUniforms->SetUniformf("contourThickness", 2.0f*(scale[0]+scale[1])/2.0f);
   fragmentUniforms->SetUniformi("contourVisibility", liverMarkupsSlicingContourDisplayNode->GetVisibility());
   }

 this->NeedToRenderOn();
}

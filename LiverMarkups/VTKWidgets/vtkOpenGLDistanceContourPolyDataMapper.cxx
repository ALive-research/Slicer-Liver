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

// This module VTK includes
#include "vtkOpenGLDistanceContourPolyDataMapper.h"

// VTK includes
#include <vtkCellData.h>
#include <vtkFloatArray.h>
#include <vtkImageData.h>
#include <vtkMatrix4x4.h>
#include <vtkObjectFactory.h>
#include <vtkOpenGLError.h>
#include <vtkOpenGLRenderWindow.h>
#include <vtkOpenGLVertexBufferObject.h>
#include <vtkOpenGLVertexBufferObjectGroup.h>
#include <vtkPointData.h>
#include <vtkPolyData.h>
#include <vtkProperty.h>
#include <vtkRenderer.h>
#include <vtkSmartPointer.h>
#include <vtkShaderProgram.h>
#include <vtkTextureObject.h>
#include <vtkTransform.h>

//------------------------------------------------------------------------------
class vtkOpenGLDistanceContourPolyDataMapper::vtkInternal
{
public:
  vtkInternal(vtkOpenGLDistanceContourPolyDataMapper* parent)
  : Parent(parent),
    ExternalPoint{0.0f, 0.0f, 0.0f, 1.0f},
    ReferencePoint{1.0f, 0.0f, 0.0f, 1.0f},
    ContourThickness(0.05), ContourVisibility(false)
  { }

  vtkWeakPointer<vtkOpenGLDistanceContourPolyDataMapper> Parent;
  std::array<float, 4> ExternalPoint;
  std::array<float, 4> ReferencePoint;
  float ContourThickness;
  bool ContourVisibility;
};

//------------------------------------------------------------------------------
vtkStandardNewMacro(vtkOpenGLDistanceContourPolyDataMapper);

//------------------------------------------------------------------------------
vtkOpenGLDistanceContourPolyDataMapper::vtkOpenGLDistanceContourPolyDataMapper()
  :Impl(nullptr)
{
  this->Impl = std::make_unique<vtkInternal>(this);
}

//------------------------------------------------------------------------------
vtkOpenGLDistanceContourPolyDataMapper::~vtkOpenGLDistanceContourPolyDataMapper(){}

//------------------------------------------------------------------------------
void vtkOpenGLDistanceContourPolyDataMapper::PrintSelf(ostream& os, vtkIndent indent)
{
   Superclass::PrintSelf(os, indent);
}

//------------------------------------------------------------------------------
void vtkOpenGLDistanceContourPolyDataMapper::BuildBufferObjects(vtkRenderer* ren, vtkActor* act)
{
  Superclass::BuildBufferObjects(ren, act);
}

//------------------------------------------------------------------------------
void vtkOpenGLDistanceContourPolyDataMapper::ReplaceShaderValues(
  std::map<vtkShader::Type, vtkShader*> shaders, vtkRenderer* ren, vtkActor* actor)
{
  std::string VSSource = shaders[vtkShader::Vertex]->GetSource();
  std::string FSSource = shaders[vtkShader::Fragment]->GetSource();

  vtkShaderProgram::Substitute(
    VSSource, "//VTK::PositionVC::Dec",
    "//VTK::PositionVC::Dec\n"
    "out vec4 vertexMCVSOutput;\n"
    "out vec4 vertexWCVSOutput;\n"
    "uniform mat4 uShiftScale;\n");

  vtkShaderProgram::Substitute(
    VSSource, "//VTK::PositionVC::Impl",
    "//VTK::PositionVC::Impl\n"
    "vertexMCVSOutput = vertexMC;\n"
    "vertexWCVSOutput = uShiftScale*vertexMC;\n");

  vtkShaderProgram::Substitute(
    FSSource, "//VTK::PositionVC::Dec",
    "//VTK::PositionVC::Dec\n"
    "in vec4 vertexWCVSOutput;"
    "vec4 fragPositionMC = vertexWCVSOutput;\n");

  vtkShaderProgram::Substitute(
    FSSource, "//VTK::Color::Dec",
    "//VTK::Color::Dec\n"
    "uniform float uContourThickness;\n"
    "uniform int uContourVisibility;\n"
    "uniform vec4 uExternalPointMC;\n"
    "uniform vec4 uReferencePointMC;\n"
    );

  vtkShaderProgram::Substitute(
      FSSource, "//VTK::Color::Impl",
      "//VTK::Color::Impl\n"
      "  vec3 contourColor= vec3(1.0, 1.0 ,1.0);\n"
      "  float refDist= distance(uExternalPointMC, uReferencePointMC);\n"
      "  float dist = distance(uReferencePointMC, fragPositionMC);\n"
      "  if(abs(dist-refDist) < uContourThickness && uContourVisibility != 0){\n"
      "     ambientColor = contourColor;\n"
      "     diffuseColor = contourColor;\n"
      "     opacity = 1.0;\n"
      "  }\n"
      "  else{\n"
      "  discard;\n"
      "  }\n");


  shaders[vtkShader::Vertex]->SetSource(VSSource);
  shaders[vtkShader::Fragment]->SetSource(FSSource);
  Superclass::ReplaceShaderValues(shaders, ren, actor);
}

//------------------------------------------------------------------------------
void vtkOpenGLDistanceContourPolyDataMapper::SetCameraShaderParameters(
    vtkOpenGLHelper &cellBO, vtkRenderer *ren, vtkActor *actor) {
  vtkOpenGLVertexBufferObject *vvbo = this->VBOs->GetVBO("vertexMC");

  // TODO: maybe cache this?
  auto transform = vtkSmartPointer<vtkTransform>::New();
  transform->Identity();
  auto transformMatrix = vtkSmartPointer<vtkMatrix4x4>::New();

  if (vvbo && vvbo->GetCoordShiftAndScaleEnabled()) {
    auto shift = vvbo->GetShift();
    auto scale = vvbo->GetScale();
    transform->Translate(shift[0], shift[1], shift[2]);
    transform->Scale(1.0 / scale[0], 1.0 / scale[1], 1.0 / scale[2]);
    transform->GetTranspose(transformMatrix);
  }

  if (cellBO.Program->IsUniformUsed("uShiftScale")) {
    cellBO.Program->SetUniformMatrix("uShiftScale", transformMatrix);
  }

  Superclass::SetCameraShaderParameters(cellBO, ren, actor);
}

//------------------------------------------------------------------------------
void vtkOpenGLDistanceContourPolyDataMapper::SetMapperShaderParameters(
    vtkOpenGLHelper &cellBO, vtkRenderer *ren, vtkActor *actor) {

  if (cellBO.Program->IsUniformUsed("uExternalPointMC"))
    {
    cellBO.Program->SetUniform4f("uExternalPointMC", this->Impl->ExternalPoint.data());
    }

  if (cellBO.Program->IsUniformUsed("uReferencePointMC"))
    {
    cellBO.Program->SetUniform4f("uReferencePointMC", this->Impl->ReferencePoint.data());
    }

  if (cellBO.Program->IsUniformUsed("uContourThickness"))
    {
    cellBO.Program->SetUniformf("uContourThickness", this->Impl->ContourThickness);
    }

  if (cellBO.Program->IsUniformUsed("uContourVisibility"))
    {
      cellBO.Program->SetUniformi("uContourVisibility",
                                  static_cast<int>(this->Impl->ContourVisibility));
    }

  Superclass::SetMapperShaderParameters(cellBO, ren, actor);
}

//------------------------------------------------------------------------------
std::array<float, 4> vtkOpenGLDistanceContourPolyDataMapper::GetExternalPoint() const
{
  return this->Impl->ExternalPoint;
}

//------------------------------------------------------------------------------
void vtkOpenGLDistanceContourPolyDataMapper::SetExternalPoint(const std::array<float, 4> &externalPoint) {
  this->Impl->ExternalPoint = externalPoint;
  this->Modified();
}

//------------------------------------------------------------------------------
std::array<float, 4> vtkOpenGLDistanceContourPolyDataMapper::GetReferencePoint() const
{
  return this->Impl->ReferencePoint;
}

//------------------------------------------------------------------------------
void vtkOpenGLDistanceContourPolyDataMapper::SetReferencePoint(const std::array<float, 4> &referencePoint) {
  this->Impl->ReferencePoint = referencePoint;
  this->Modified();
}

//------------------------------------------------------------------------------
float vtkOpenGLDistanceContourPolyDataMapper::GetContourThickness() const { return this->Impl->ContourThickness; }

//------------------------------------------------------------------------------
void vtkOpenGLDistanceContourPolyDataMapper::SetContourThickness(float contourThickness) {
  this->Impl->ContourThickness = contourThickness;
  this->Modified();
}

//------------------------------------------------------------------------------
bool vtkOpenGLDistanceContourPolyDataMapper::GetContourVisibility() const { return this->Impl->ContourVisibility; }

//------------------------------------------------------------------------------
void vtkOpenGLDistanceContourPolyDataMapper::SetContourVisibility(bool contourVisibility) {
  this->Impl->ContourVisibility = contourVisibility;
  this->Modified();
}

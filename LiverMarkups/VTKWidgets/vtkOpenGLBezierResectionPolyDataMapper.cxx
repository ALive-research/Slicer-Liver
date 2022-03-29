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
#include "vtkOpenGLBezierResectionPolyDataMapper.h"

// VTK includes
#include <vtkImageData.h>
#include <vtkMatrix4x4.h>
#include <vtkObjectFactory.h>
#include <vtkOpenGLVertexBufferObject.h>
#include <vtkOpenGLVertexBufferObjectGroup.h>
#include <vtkSmartPointer.h>
#include <vtkTextureObject.h>
#include <vtkTransform.h>
#include <vtkShaderProgram.h>
#include <vtkSmartPointer.h>

//------------------------------------------------------------------------------
class vtkOpenGLBezierResectionPolyDataMapper::vtkInternal
{
public:
  vtkInternal(vtkOpenGLBezierResectionPolyDataMapper* parent)
  : Parent(parent), DistanceMapTextureObject(nullptr),
    RasToIjkMatrixT(nullptr), IjkToTextureMatrixT(nullptr),
    ResectionMargin(0.0f), UncertaintyMargin(0.0f),
    ResectionMarginColor({1.0f, 0.0f, 0.0f}),
    UncertaintyMarginColor({1.0f, 1.0f, 0.0f}),
    ResectionColor({1.0f,1.0f, 1.0f}), ResectionOpacity(1.0f),
    InterpolatedMargins(false), ResectionClipOut(false)
  {
    this->RasToIjkMatrixT = vtkSmartPointer<vtkMatrix4x4>::New();
    this->IjkToTextureMatrixT = vtkSmartPointer<vtkMatrix4x4>::New();
  }

  vtkWeakPointer<vtkOpenGLBezierResectionPolyDataMapper> Parent;
  vtkSmartPointer<vtkTextureObject> DistanceMapTextureObject;
  vtkSmartPointer<vtkMatrix4x4> RasToIjkMatrixT;
  vtkSmartPointer<vtkMatrix4x4> IjkToTextureMatrixT;
  float ResectionMargin;
  float UncertaintyMargin;
  float ResectionMarginColor[3];
  float UncertaintyMarginColor[3];
  float ResectionColor[3];
  float ResectionOpacity;
  bool  InterpolatedMargins;
  bool  ResectionClipOut;
};

//------------------------------------------------------------------------------
vtkStandardNewMacro(vtkOpenGLBezierResectionPolyDataMapper);

//------------------------------------------------------------------------------
vtkOpenGLBezierResectionPolyDataMapper::vtkOpenGLBezierResectionPolyDataMapper()
  :Impl(nullptr)
{
  this->Impl = std::make_unique<vtkInternal>(this);
}

//------------------------------------------------------------------------------
vtkOpenGLBezierResectionPolyDataMapper::~vtkOpenGLBezierResectionPolyDataMapper(){}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper::PrintSelf(ostream& os, vtkIndent indent)
{
   Superclass::PrintSelf(os, indent);
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper::ReplaceShaderValues(
  std::map<vtkShader::Type, vtkShader*> shaders, vtkRenderer* ren, vtkActor* actor)
{
  std::string VSSource = shaders[vtkShader::Vertex]->GetSource();
  std::string FSSource = shaders[vtkShader::Fragment]->GetSource();

  vtkShaderProgram::Substitute(
    VSSource, "//VTK::PositionVC::Dec",
    "//VTK::PositionVC::Dec"
    "out vec4 vertexMCVSOutput;\n"
    "out vec4 vertexWCVSOutput;\n"
    "uniform mat4 uShiftScale;\n"
    "uniform mat4 uRasToIjk;\n"
    "uniform mat4 uIjkToTexture;\n");

  vtkShaderProgram::Substitute(
    VSSource, "//VTK::PositionVC::Impl",
    "//VTK::PositionVC::Impl"
    "vertexMCVSOutput = vertexMC;\n"
    "vertexWCVSOutput = uIjkToTexture*uRasToIjk*uShiftScale*vertexMC;\n");

  vtkShaderProgram::Substitute(
    FSSource, "//VTK::PositionVC::Dec",
    "//VTK::PositionVC::Dec"
    "uniform sampler3D distanceTexture;\n"
    "//vec4 fragPositionMC = vertexWCVSOutput;\n");

  vtkShaderProgram::Substitute(
    FSSource, "//VTK::Color::Dec",
    "//VTK::Color::Dec"
    "uniform float uResectionMargin;\n"
    "uniform float uUncertaintyMargin;\n"
    "uniform float uResectionOpacity;\n"
    "uniform vec3 uResectionMarginColor;\n"
    "uniform vec3 uUncertaintyMarginColor;\n"
    "uniform vec3 uResectionColor;\n"
    "uniform int uResectionClipOut;\n"
    "uniform int uInterpolatedMargins;\n"
    "in vec4 vertexWCVSOutput;\n"
    "vec4 fragPositionMC = vertexWCVSOutput;\n");

  vtkShaderProgram::Substitute(
    FSSource, "//VTK::Color::Impl",
    "//VTK::Color::Impl"
    "vec4 dist = texture(distanceTexture, fragPositionMC.xyz);\n"
    "float lowMargin = uResectionMargin - uUncertaintyMargin;\n"
    "float highMargin = uResectionMargin + uUncertaintyMargin;\n"
    "if(uResectionClipOut == 1 && dist[1] > 2.0){\n"
    "  discard;\n"
    "}\n"
    "if(dist[0] < lowMargin){\n"
    "   ambientColor = uResectionMarginColor;\n"
    "   diffuseColor = vec3(0.0);\n"
    "}\n"
    "else if(dist[0] < highMargin-(highMargin-lowMargin)*0.1){\n"
    "  if(uInterpolatedMargins == 0){\n"
    "   ambientColor = uUncertaintyMarginColor;\n"
    "   diffuseColor = vec3(0.0);\n"
    "  }\n"
    "  else{\n"
    "   ambientColor = mix(uResectionMarginColor, uUncertaintyMarginColor, "
    "(dist[0]-lowMargin)/(highMargin-lowMargin));\n"
    "   ambientColor = ambientColor;\n"
    "   diffuseColor = vec3(0.0);\n"
    "  }\n"
    "}\n"
    "else if(dist[0] < highMargin){\n"
    "   ambientColor = vec3(0.0);\n"
    "   diffuseColor = vec3(0.0);\n"
    "}\n"
    "else{\n"
    "  ambientColor = uResectionColor;\n"
    "  diffuseColor = vec3(0.6);\n"
    "}\n",
    "in vec4 vertexMCVSOutput;\n"
    "in vec4 vertexWCVSOutput;\n");

   vtkShaderProgram::Substitute(
    FSSource, "//VTK::Light::Impl",
    "//VTK::Light::Impl"
    "fragOutput0 = vec4(ambientColor + diffuse + specular, uResectionOpacity);\n");

  shaders[vtkShader::Vertex]->SetSource(VSSource);
  shaders[vtkShader::Fragment]->SetSource(FSSource);
  Superclass::ReplaceShaderValues(shaders, ren, actor);
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper::SetCameraShaderParameters(
  vtkOpenGLHelper& cellBO, vtkRenderer* ren, vtkActor* actor)
{
  vtkOpenGLVertexBufferObject* vvbo = this->VBOs->GetVBO("vertexMC");

  // TODO: maybe cache this?
  auto transform = vtkSmartPointer<vtkTransform>::New();
  transform->Identity();
  auto transformMatrix = vtkSmartPointer<vtkMatrix4x4>::New();

  if (vvbo && vvbo->GetCoordShiftAndScaleEnabled())
    {
  auto shift = vvbo->GetShift();
  auto scale = vvbo->GetScale();
  transform->Translate(shift[0], shift[1], shift[2]);
  transform->Scale(1.0/scale[0], 1.0/scale[1], 1.0/scale[2]);
  transform->GetTranspose(transformMatrix);
    }

  if (cellBO.Program->IsUniformUsed("uShiftScale"))
    {
    cellBO.Program->SetUniformMatrix("uShiftScale", transformMatrix);
    }

  Superclass::SetCameraShaderParameters(cellBO, ren, actor);
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper::SetMapperShaderParameters(
  vtkOpenGLHelper& cellBO, vtkRenderer* ren, vtkActor* actor)
{
  if (cellBO.Program->IsUniformUsed("uRasToIjk"))
    {
    cellBO.Program->SetUniformMatrix("uRasToIjk", this->Impl->RasToIjkMatrixT);
    }

  if (cellBO.Program->IsUniformUsed("uIjkToTexture"))
    {
    cellBO.Program->SetUniformMatrix("uIjkToTexture", this->Impl->IjkToTextureMatrixT);
    }

  if (cellBO.Program->IsUniformUsed("uResectionMargin"))
    {
    cellBO.Program->SetUniformf("uResectionMargin", this->Impl->ResectionMargin);
    }

  if (cellBO.Program->IsUniformUsed("uUncertaintyMargin"))
    {
    cellBO.Program->SetUniformf("uUncertaintyMargin", this->Impl->UncertaintyMargin);
    }

  if (cellBO.Program->IsUniformUsed("uInterpolatedMargins"))
    {
    cellBO.Program->SetUniformi("uInterpolatedMargins", this->Impl->InterpolatedMargins);
    }

  if (cellBO.Program->IsUniformUsed("uResectionMarginColor"))
    {
    cellBO.Program->SetUniform3f("uResectionMarginColor", this->Impl->ResectionMarginColor);
    }

  if (cellBO.Program->IsUniformUsed("uUncertaintyMarginColor"))
    {
    cellBO.Program->SetUniform3f("uUncertaintyMarginColor", this->Impl->UncertaintyMarginColor);
    }

  if (cellBO.Program->IsUniformUsed("uResectionColor"))
    {
    cellBO.Program->SetUniform3f("uResectionColor", this->Impl->ResectionColor);
    }

  if (cellBO.Program->IsUniformUsed("uResectionOpacity"))
    {
    cellBO.Program->SetUniformf("uResectionOpacity", this->Impl->ResectionOpacity);
    }

  if (cellBO.Program->IsUniformUsed("uResectionClipOut"))
    {
    cellBO.Program->SetUniformi("uResectionClipOut", this->Impl->ResectionClipOut);
    }

  Superclass::SetMapperShaderParameters(cellBO, ren, actor);
}

//------------------------------------------------------------------------------
vtkTextureObject* vtkOpenGLBezierResectionPolyDataMapper::GetDistanceMapTextureObject() const
{
  return this->Impl->DistanceMapTextureObject;
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper::SetDistanceMapTextureObject(vtkTextureObject* object)
{
  if (this->Impl->DistanceMapTextureObject == object)
    {
    return;
    }

  this->Impl->DistanceMapTextureObject = object;
  if (object)
    {
    object->Register(this);
    }

  this->Modified();
}

//------------------------------------------------------------------------------
vtkMatrix4x4 const* vtkOpenGLBezierResectionPolyDataMapper::GetRasToIjkMatrixT() const
{
  return this->Impl->RasToIjkMatrixT;
}


//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper::SetRasToIjkMatrixT(const vtkMatrix4x4* matrix)
{
  if (matrix == nullptr)
    {
    return;
    }

  this->Impl->RasToIjkMatrixT->DeepCopy(matrix);
  this->Modified();
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper::SetRasToIjkMatrix(const vtkMatrix4x4* matrix)
{
  if (matrix == nullptr)
    {
    return;
    }

  this->Impl->RasToIjkMatrixT->DeepCopy(matrix);
  this->Impl->RasToIjkMatrixT->Transpose();
  this->Modified();
}

//------------------------------------------------------------------------------
vtkMatrix4x4 const* vtkOpenGLBezierResectionPolyDataMapper::GetIjkToTextureMatrixT() const
{
  return this->Impl->IjkToTextureMatrixT;
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper::SetIjkToTextureMatrixT(const vtkMatrix4x4* matrix)
{
  if (matrix == nullptr)
    {
    return;
    }

  this->Impl->IjkToTextureMatrixT->DeepCopy(matrix);
  this->Modified();
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper::SetIjkToTextureMatrix(const vtkMatrix4x4* matrix)
{
  if (matrix == nullptr)
    {
    return;
    }

  this->Impl->IjkToTextureMatrixT->DeepCopy(matrix);
  this->Impl->IjkToTextureMatrixT->Transpose();
  this->Modified();
}
//------------------------------------------------------------------------------
float vtkOpenGLBezierResectionPolyDataMapper::GetResectionMargin() const
{
  return this->Impl->ResectionMargin;
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper::SetResectionMargin(float margin)
{
  this->Impl->ResectionMargin = margin;
  this->Modified();
}

//------------------------------------------------------------------------------
float vtkOpenGLBezierResectionPolyDataMapper::GetUncertaintyMargin() const
{
  return this->Impl->UncertaintyMargin;
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper::SetUncertaintyMargin(float margin)
{
  this->Impl->UncertaintyMargin = margin;
  this->Modified();
}


//------------------------------------------------------------------------------
float const* vtkOpenGLBezierResectionPolyDataMapper::GetResectionMarginColor() const
{
  return this->Impl->ResectionMarginColor;
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper::SetResectionMarginColor(float color[3])
{
  this->Impl->ResectionMarginColor[0] = color[0];
  this->Impl->ResectionMarginColor[1] = color[1];
  this->Impl->ResectionMarginColor[2] = color[2];
  this->Modified();
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper::SetResectionMarginColor(float red, float green, float blue)
{
  this->Impl->ResectionMarginColor[0] = red;
  this->Impl->ResectionMarginColor[1] = green;
  this->Impl->ResectionMarginColor[2] = blue;
  this->Modified();
}

//------------------------------------------------------------------------------
float const* vtkOpenGLBezierResectionPolyDataMapper::GetUncertaintyMarginColor() const
{
  return this->Impl->UncertaintyMarginColor;
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper::SetUncertaintyMarginColor(float color[3])
{
  this->Impl->UncertaintyMarginColor[0] = color[0];
  this->Impl->UncertaintyMarginColor[1] = color[1];
  this->Impl->UncertaintyMarginColor[2] = color[2];
  this->Modified();
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper::SetUncertaintyMarginColor(float red, float green, float blue)
{
  this->Impl->UncertaintyMarginColor[0] = red;
  this->Impl->UncertaintyMarginColor[1] = green;
  this->Impl->UncertaintyMarginColor[2] = blue;
  this->Modified();
}

//------------------------------------------------------------------------------
float const* vtkOpenGLBezierResectionPolyDataMapper::GetResectionColor() const
{
  return this->Impl->ResectionColor;
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper::SetResectionColor(float color[3])
{
  this->Impl->ResectionColor[0] = color[0];
  this->Impl->ResectionColor[1] = color[1];
  this->Impl->ResectionColor[2] = color[2];
  this->Modified();
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper::SetResectionColor(float red, float green, float blue)
{
  this->Impl->ResectionColor[0] = red;
  this->Impl->ResectionColor[1] = green;
  this->Impl->ResectionColor[2] = blue;
  this->Modified();
}

//------------------------------------------------------------------------------
float vtkOpenGLBezierResectionPolyDataMapper::GetResectionOpacity() const
{
  return this->Impl->ResectionOpacity;
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper::SetResectionOpacity(float margin)
{
  this->Impl->ResectionOpacity = margin;
  this->Modified();
}

//------------------------------------------------------------------------------
bool vtkOpenGLBezierResectionPolyDataMapper::GetResectionClipOut() const
{
  return this->Impl->ResectionClipOut;
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper::SetResectionClipOut(bool clipOut)
{
  this->Impl->ResectionClipOut = clipOut;
  this->Modified();
}

//------------------------------------------------------------------------------
bool vtkOpenGLBezierResectionPolyDataMapper::GetInterpolatedMargins() const
{
  return this->Impl->InterpolatedMargins;
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper::SetInterpolatedMargins(bool clipOut)
{
  this->Impl->InterpolatedMargins = clipOut;
  this->Modified();
}

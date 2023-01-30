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

  This file was originally developed by Ruoyan Meng (NTNU) and Rafael
  Palomar (Oslo University Hospital and NTNU) and was supported by The
  Research Council of Norway through the ALive project (grant nr. 311393).

  ==============================================================================*/

#include "vtkOpenGLResection2DPolyDataMapper.h"
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
class vtkOpenGLResection2DPolyDataMapper::vtkInternal
{
 public:
  vtkInternal(vtkOpenGLResection2DPolyDataMapper* parent)
    : Parent(parent), DistanceMapTextureObject(nullptr), VascularSegmentsTextureObject(nullptr),
      RasToIjkMatrixT(nullptr), IjkToTextureMatrixT(nullptr),
      ResectionMargin(0.0f), UncertaintyMargin(0.0f),
      ResectionMarginColor{1.0f, 0.0f, 0.0f},
      UncertaintyMarginColor{1.0f, 1.0f, 0.0f},
      ResectionColor{1.0f,1.0f, 1.0f},
      ResectionGridColor{0.0f,0.0f, 0.0f},
      ResectionOpacity(1.0f),
      InterpolatedMargins(false), ResectionClipOut(false), ShowResection2D(false),
      PortalContourThickness(0.3f), HepaticContourThickness(0.3f),
      PortalContourColor{216.0/255.0f, 101.0/255.0f, 79.0/255.0f},
      HepaticContourColor{0.0f, 151.0/255.0f, 206.0/255.0f},
      TextureNumComps(0)
  {
    this->RasToIjkMatrixT = vtkSmartPointer<vtkMatrix4x4>::New();
    this->IjkToTextureMatrixT = vtkSmartPointer<vtkMatrix4x4>::New();
  }

  vtkWeakPointer<vtkOpenGLResection2DPolyDataMapper> Parent;
  vtkSmartPointer<vtkTextureObject> DistanceMapTextureObject;
  vtkSmartPointer<vtkTextureObject> VascularSegmentsTextureObject;
  vtkSmartPointer<vtkMatrix4x4> RasToIjkMatrixT;
  vtkSmartPointer<vtkMatrix4x4> IjkToTextureMatrixT;
  float ResectionMargin;
  float UncertaintyMargin;
  float ResectionMarginColor[3];
  float UncertaintyMarginColor[3];
  float ResectionColor[3];
  float ResectionGridColor[3];
  float ResectionOpacity;
  bool  InterpolatedMargins;
  bool  ResectionClipOut;
  unsigned int GridDivisions;
  float GridThicknessFactor;
  bool ShowResection2D;
  float PortalContourThickness;
  float HepaticContourThickness;
  float PortalContourColor[3];
  float HepaticContourColor[3];
  int TextureNumComps;
  unsigned int MarkerStyleAvailable;
  float MatRatio[2];
};

//------------------------------------------------------------------------------
vtkStandardNewMacro(vtkOpenGLResection2DPolyDataMapper);


//------------------------------------------------------------------------------
vtkOpenGLResection2DPolyDataMapper::vtkOpenGLResection2DPolyDataMapper()
  :Impl(nullptr)
{
  this->Impl = std::make_unique<vtkInternal>(this);
}

//------------------------------------------------------------------------------
vtkOpenGLResection2DPolyDataMapper::~vtkOpenGLResection2DPolyDataMapper(){}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::PrintSelf(ostream& os, vtkIndent indent)
{
  Superclass::PrintSelf(os, indent);
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::BuildBufferObjects(vtkRenderer* ren, vtkActor* act)
{
  if (this->CurrentInput && this->HaveTCoords(this->CurrentInput))
    {
    auto renWin = vtkOpenGLRenderWindow::SafeDownCast(ren->GetRenderWindow());
    vtkOpenGLVertexBufferObjectCache* cache = renWin->GetVBOCache();
    auto tcoords = this->CurrentInput->GetPointData()->GetTCoords();
    this->VBOs->CacheDataArray("uvCoords", tcoords, cache, VTK_FLOAT);
    if(this->CurrentInput->GetPointData()->GetArray("BSPoints")){
      auto vertexMCBS = this->CurrentInput->GetPointData()->GetArray("BSPoints");
      this->VBOs->CacheDataArray("vertexMCBS", vertexMCBS, cache, VTK_FLOAT);
      }else{
      auto vertexMCBS = this->CurrentInput->GetPoints()->GetData();
      this->VBOs->CacheDataArray("vertexMCBS", vertexMCBS, cache, VTK_FLOAT);
      }
    }
  Superclass::BuildBufferObjects(ren, act);
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::ReplaceShaderValues(
  std::map<vtkShader::Type, vtkShader*> shaders, vtkRenderer* ren, vtkActor* actor)
{
  std::string VSSource = shaders[vtkShader::Vertex]->GetSource();
  std::string FSSource = shaders[vtkShader::Fragment]->GetSource();
  vtkShaderProgram::Substitute(
    VSSource, "//VTK::PositionVC::Dec",
    "//VTK::PositionVC::Dec\n"
    "out vec4 vertexMCVSOutput;\n"
    "out vec4 vertexWCVSOutput;\n"
    "in vec2 uvCoords;\n"
    "out vec2 uvCoordsOutput;\n"

    "uniform mat4 uShiftScaleBS;\n"
    "uniform mat4 uShiftScale;\n"
    "uniform mat4 uRasToIjk;\n"
    "uniform mat4 uIjkToTexture;\n"
    "uniform vec2 uMatRatio;\n"
    "in vec4 vertexMCBS;\n"
    "out vec4 vertexMCVSOutputBS;\n"
    "out vec4 vertexWCVSOutputBS;\n");

  vtkShaderProgram::Substitute(
    VSSource, "//VTK::PositionVC::Impl",
    "//VTK::PositionVC::Impl\n"
    "vertexMCVSOutput = vertexMC;\n"
    "uvCoordsOutput = uvCoords;\n"
    "vertexWCVSOutput = uIjkToTexture*uRasToIjk*uShiftScale*vertexMC;\n"
    "vertexMCVSOutputBS = vertexMCBS;\n"
    "vertexWCVSOutputBS = uIjkToTexture*uRasToIjk*uShiftScaleBS*vertexMCBS;\n"
    "mat4 m = mat4(1.0);\n"
    "m[2][2] = 0.0;\n"
    "m[0][0] = uMatRatio[0];\n"
    "m[1][1] = uMatRatio[1];\n"
    "gl_Position = m * MCDCMatrix * vertexMC;\n");

  vtkShaderProgram::Substitute(
    FSSource, "//VTK::PositionVC::Dec",
    "//VTK::PositionVC::Dec\n"
    "#define M_PI 3.1415926535897932384626433832795\n"
    "uniform sampler3D distanceTexture;\n"
    "uniform sampler3D vesselSegTexture;\n"
    "uniform sampler2D posMarker;\n"
    "//vec4 fragPositionMC = vertexWCVSOutput;\n");

  vtkShaderProgram::Substitute(
    FSSource, "//VTK::Color::Dec",
    "//VTK::Color::Dec\n"
    "uniform vec4 colorChart[8];\n"
    "uniform float uResectionMargin;\n"
    "uniform float uUncertaintyMargin;\n"
    "uniform float uResectionOpacity;\n"
    "uniform vec3 uResectionMarginColor;\n"
    "uniform vec3 uUncertaintyMarginColor;\n"
    "uniform vec3 uResectionColor;\n"
    "uniform vec3 uResectionGridColor;\n"
    "uniform int uResectionClipOut;\n"
    "uniform int uInterpolatedMargins;\n"
    "uniform int uGridDivisions;\n"
    "uniform int uMarkerStyleAvailable;\n"
    "uniform float uGridThickness;\n"
    "in vec2 uvCoordsOutput;\n"
    "in vec4 vertexWCVSOutputBS;\n"
    "vec4 fragPositionMCBS = vertexWCVSOutputBS;\n"
    "uniform vec3 uPortalContourColor;\n"
    "uniform vec3 uHepaticContourColor;\n"
    "uniform int uTextureNumComps;\n"
    "uniform float uPortalContourThickness;\n"
    "uniform float uHepaticContourThickness;\n");

  vtkShaderProgram::Substitute(
    FSSource, "//VTK::Color::Impl",
    "//VTK::Color::Impl\n"
    "vec4 marker = texture(posMarker, uvCoordsOutput);\n"
    "vec4 dist = texture(distanceTexture, fragPositionMCBS.xyz);\n"
    "vec4 vesselBg = texture(vesselSegTexture, fragPositionMCBS.xyz);\n"
    "float lowMargin = uResectionMargin - uUncertaintyMargin;\n"
    "float highMargin = uResectionMargin + uUncertaintyMargin;\n"
    "if(uResectionClipOut == 1 && dist[1] > 2.0){\n"
    "  discard;\n"
    "}\n"


    //hardcode 8 labels color
    "if(vesselBg[0] == 0){\n"
    "  ambientColor = vec3(1.0);\n"
    "  diffuseColor = vec3(0.0);\n"
    "}\n"
    "else if(vesselBg[0] == 1){\n"
    "  ambientColor = vec3(0.2, 0.5, 0.8);\n"
    "  diffuseColor = vec3(0.0);\n"
    "}\n"
    "else if(vesselBg[0] == 2){\n"
    "  ambientColor = vec3(1.0, 0.8, 0.7);\n"
    "  diffuseColor = vec3(0.0);\n"
    "}\n"
    "else if(vesselBg[0] == 3){\n"
    "  ambientColor = vec3(1.0, 1.0, 1.0);\n"
    "  diffuseColor = vec3(0.0);\n"
    "}\n"
    "else if(vesselBg[0] == 4){\n"
    "  ambientColor = vec3(0.4, 0.7, 1.0);\n"
    "  diffuseColor = vec3(0.0);\n"
    "}\n"
    "else if(vesselBg[0] == 5){\n"
    "  ambientColor = vec3(0.9, 0.5, 0.5);\n"
    "  diffuseColor = vec3(0.0);\n"
    "}\n"
    "else if(vesselBg[0] == 6){\n"
    "  ambientColor = vec3(0.5, 0.9, 0.5);\n"
    "  diffuseColor = vec3(0.0);\n"
    "}\n"
    "else if(vesselBg[0] == 7){\n"
    "  ambientColor = vec3(0.5, 0.9, 0.9);\n"
    "  diffuseColor = vec3(0.0);\n"
    "}\n"
    "else if(vesselBg[0] == 8){\n"
    "  ambientColor = vec3(0.9, 0.9, 0.5);\n"
    "  diffuseColor = vec3(0.0);\n"
    "}\n"
    "else{\n"
    "  ambientColor = uResectionColor;\n"
    "  diffuseColor = vec3(0.6);\n"
    "}\n"

    "if(dist[0] < lowMargin){\n"
    "  ambientColor = uResectionMarginColor;\n"
    "  diffuseColor = vec3(0.0);\n"
    "}\n"
    "else if(dist[0] < highMargin-(highMargin-lowMargin)*0.1){\n"
    "  if(uInterpolatedMargins == 0){\n"
    "     ambientColor = uUncertaintyMarginColor;\n"
    "     diffuseColor = vec3(0.0);\n"
    "  }\n"
    "  else{\n"
    "    ambientColor = mix(uResectionMarginColor, uUncertaintyMarginColor, "
    "    (dist[0]-lowMargin)/(highMargin-lowMargin));\n"
    "    ambientColor = ambientColor;\n"
    "    diffuseColor = vec3(0.0);\n"
    "  }\n"
    "}\n"

    "if(tan(uvCoordsOutput.x*M_PI*uGridDivisions)>10.0-uGridThickness || tan(uvCoordsOutput.y*M_PI*uGridDivisions)>10.0-uGridThickness){\n"
    "   ambientColor = uResectionGridColor;\n"
    "   diffuseColor = vec3(0.0);\n"
    "}\n"
    "else{\n"
    "  if(uTextureNumComps > 2){\n"
    "    if( abs(dist[1])<0.5 ){\n"
    "      ambientColor = vec3(0.0,0.0,0.0);\n"
    "      diffuseColor = vec3(0.0);\n"
    "    }\n"
    "    else if( abs(dist[2])<uHepaticContourThickness && dist[1]<10){\n"
    "      ambientColor = uHepaticContourColor;\n"
    "      diffuseColor = vec3(0.0);\n"
    "    }\n"
    "    else if( abs(dist[3])<uPortalContourThickness && dist[1]<10){\n"
    "      ambientColor = uPortalContourColor;\n"
    "      diffuseColor = vec3(0.0);\n"
    "    }\n"
    "  }\n"
    "}\n"

    "if(uMarkerStyleAvailable == 1 && marker.a != 0){\n"
    "  ambientColor = vec3(marker.r,marker.g,marker.b);\n"
    "  diffuseColor = vec3(0.0);\n"
    "}\n"
    );
  vtkShaderProgram::Substitute(
    FSSource, "//VTK::Light::Impl",
    "//VTK::Light::Impl\n"
    "fragOutput0 = vec4(ambientColor+vec3(uvCoordsOutput,0.0)*0.00001 + diffuse + specular, uResectionOpacity);\n");


  shaders[vtkShader::Vertex]->SetSource(VSSource);
  shaders[vtkShader::Fragment]->SetSource(FSSource);
  Superclass::ReplaceShaderValues(shaders, ren, actor);
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::SetCameraShaderParameters(
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

  vtkOpenGLVertexBufferObject* vvbobs = this->VBOs->GetVBO("vertexMCBS");

  // TODO: maybe cache this?
  auto transformBS = vtkSmartPointer<vtkTransform>::New();
  transformBS->Identity();
  auto transformMatrixBS = vtkSmartPointer<vtkMatrix4x4>::New();

  if (vvbobs && vvbobs->GetCoordShiftAndScaleEnabled())
    {
    auto shift = vvbobs->GetShift();
    auto scale = vvbobs->GetScale();
    transformBS->Translate(shift[0], shift[1], shift[2]);
    transformBS->Scale(1.0/scale[0], 1.0/scale[1], 1.0/scale[2]);
    transformBS->GetTranspose(transformMatrixBS);
    }

  if (cellBO.Program->IsUniformUsed("uShiftScaleBS"))
    {
    cellBO.Program->SetUniformMatrix("uShiftScaleBS", transformMatrixBS);
    }


  Superclass::SetCameraShaderParameters(cellBO, ren, actor);
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::SetMapperShaderParameters(
  vtkOpenGLHelper& cellBO, vtkRenderer* ren, vtkActor* actor)
{
  if (cellBO.Program->IsUniformUsed("distanceTexture"))
    {
    cellBO.Program->SetUniformi("distanceTexture", 0);
    }

  if (cellBO.Program->IsUniformUsed("posMarker"))
    {
    cellBO.Program->SetUniformi("posMarker", 15);
    }

  if (cellBO.Program->IsUniformUsed("vesselSegTexture"))
    {
    cellBO.Program->SetUniformi("vesselSegTexture", 1);
    }

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

  if (cellBO.Program->IsUniformUsed("uResectionGridColor"))
    {
    cellBO.Program->SetUniform3f("uResectionGridColor", this->Impl->ResectionGridColor);
    }

  if (cellBO.Program->IsUniformUsed("uResectionOpacity"))
    {
    cellBO.Program->SetUniformf("uResectionOpacity", this->Impl->ResectionOpacity);
    }

  if (cellBO.Program->IsUniformUsed("uResectionClipOut"))
    {
    cellBO.Program->SetUniformi("uResectionClipOut", this->Impl->ResectionClipOut);
    }

  if (cellBO.Program->IsUniformUsed("uGridDivisions"))
    {
    cellBO.Program->SetUniformi("uGridDivisions", this->Impl->GridDivisions);
    }

  if (cellBO.Program->IsUniformUsed("uGridThickness"))
    {
    cellBO.Program->SetUniformf("uGridThickness", this->Impl->GridThicknessFactor);
    }

  if (cellBO.Program->IsUniformUsed("uHepaticContourColor"))
    {
    cellBO.Program->SetUniform3f("uHepaticContourColor", this->Impl->HepaticContourColor);
    }

  if (cellBO.Program->IsUniformUsed("uPortalContourColor"))
    {
    cellBO.Program->SetUniform3f("uPortalContourColor", this->Impl->PortalContourColor);
    }

  if (cellBO.Program->IsUniformUsed("uTextureNumComps"))
    {
    cellBO.Program->SetUniformi("uTextureNumComps", this->Impl->TextureNumComps);
    }

  if (cellBO.Program->IsUniformUsed("uPortalContourThickness"))
    {
    cellBO.Program->SetUniformf("uPortalContourThickness", this->Impl->PortalContourThickness);
    }

  if (cellBO.Program->IsUniformUsed("uHepaticContourThickness"))
    {
    cellBO.Program->SetUniformf("uHepaticContourThickness", this->Impl->HepaticContourThickness);
    }

  if (cellBO.Program->IsUniformUsed("uMarkerStyleAvailable"))
    {
    cellBO.Program->SetUniformi("uMarkerStyleAvailable", this->Impl->MarkerStyleAvailable);
    }

  if (cellBO.Program->IsUniformUsed("uMatRatio"))
    {
    cellBO.Program->SetUniform2f("uMatRatio", this->Impl->MatRatio);
    }

  Superclass::SetMapperShaderParameters(cellBO, ren, actor);
}

//------------------------------------------------------------------------------
vtkTextureObject* vtkOpenGLResection2DPolyDataMapper::GetDistanceMapTextureObject() const
{
  return this->Impl->DistanceMapTextureObject;
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::SetDistanceMapTextureObject(vtkTextureObject* object)
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
vtkTextureObject* vtkOpenGLResection2DPolyDataMapper::GetVascularSegmentsTextureObject() const
{
  return this->Impl->VascularSegmentsTextureObject;
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::SetVascularSegmentsTextureObject(vtkTextureObject* object)
{
  if (this->Impl->VascularSegmentsTextureObject == object)
    {
    return;
    }

  this->Impl->VascularSegmentsTextureObject = object;
  if (object)
    {
    object->Register(this);
    }

  this->Modified();
}

//------------------------------------------------------------------------------
vtkMatrix4x4 const* vtkOpenGLResection2DPolyDataMapper::GetRasToIjkMatrixT() const
{
  return this->Impl->RasToIjkMatrixT;
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::SetRasToIjkMatrixT(const vtkMatrix4x4* matrix)
{
  if (matrix == nullptr)
    {
    return;
    }

  this->Impl->RasToIjkMatrixT->DeepCopy(matrix);
  this->Modified();
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::SetRasToIjkMatrix(const vtkMatrix4x4* matrix)
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
vtkMatrix4x4 const* vtkOpenGLResection2DPolyDataMapper::GetIjkToTextureMatrixT() const
{
  return this->Impl->IjkToTextureMatrixT;
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::SetIjkToTextureMatrixT(const vtkMatrix4x4* matrix)
{
  if (matrix == nullptr)
    {
    return;
    }

  this->Impl->IjkToTextureMatrixT->DeepCopy(matrix);
  this->Modified();
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::SetIjkToTextureMatrix(const vtkMatrix4x4* matrix)
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
float vtkOpenGLResection2DPolyDataMapper::GetResectionMargin() const
{
  return this->Impl->ResectionMargin;
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::SetResectionMargin(float margin)
{
  this->Impl->ResectionMargin = margin;
  this->Modified();
}

//------------------------------------------------------------------------------
float vtkOpenGLResection2DPolyDataMapper::GetUncertaintyMargin() const
{
  return this->Impl->UncertaintyMargin;
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::SetUncertaintyMargin(float margin)
{
  this->Impl->UncertaintyMargin = margin;
  this->Modified();
}


//------------------------------------------------------------------------------
float const* vtkOpenGLResection2DPolyDataMapper::GetResectionMarginColor() const
{
  return this->Impl->ResectionMarginColor;
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::SetResectionMarginColor(float color[3])
{
  this->Impl->ResectionMarginColor[0] = color[0];
  this->Impl->ResectionMarginColor[1] = color[1];
  this->Impl->ResectionMarginColor[2] = color[2];
  this->Modified();
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::SetResectionMarginColor(float red, float green, float blue)
{
  this->Impl->ResectionMarginColor[0] = red;
  this->Impl->ResectionMarginColor[1] = green;
  this->Impl->ResectionMarginColor[2] = blue;
  this->Modified();
}

//------------------------------------------------------------------------------
float const* vtkOpenGLResection2DPolyDataMapper::GetUncertaintyMarginColor() const
{
  return this->Impl->UncertaintyMarginColor;
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::SetUncertaintyMarginColor(float color[3])
{
  this->Impl->UncertaintyMarginColor[0] = color[0];
  this->Impl->UncertaintyMarginColor[1] = color[1];
  this->Impl->UncertaintyMarginColor[2] = color[2];
  this->Modified();
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::SetUncertaintyMarginColor(float red, float green, float blue)
{
  this->Impl->UncertaintyMarginColor[0] = red;
  this->Impl->UncertaintyMarginColor[1] = green;
  this->Impl->UncertaintyMarginColor[2] = blue;
  this->Modified();
}

//------------------------------------------------------------------------------
float const* vtkOpenGLResection2DPolyDataMapper::GetResectionColor() const
{
  return this->Impl->ResectionColor;
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::SetResectionColor(float color[3])
{
  this->Impl->ResectionColor[0] = color[0];
  this->Impl->ResectionColor[1] = color[1];
  this->Impl->ResectionColor[2] = color[2];
  this->Modified();
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::SetResectionColor(float red, float green, float blue)
{
  this->Impl->ResectionColor[0] = red;
  this->Impl->ResectionColor[1] = green;
  this->Impl->ResectionColor[2] = blue;
  this->Modified();
}

//------------------------------------------------------------------------------
float const* vtkOpenGLResection2DPolyDataMapper::GetResectionGridColor() const
{
  return this->Impl->ResectionGridColor;
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::SetResectionGridColor(float color[3])
{
  this->Impl->ResectionGridColor[0] = color[0];
  this->Impl->ResectionGridColor[1] = color[1];
  this->Impl->ResectionGridColor[2] = color[2];
  this->Modified();
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::SetResectionGridColor(float red, float green, float blue)
{
  this->Impl->ResectionGridColor[0] = red;
  this->Impl->ResectionGridColor[1] = green;
  this->Impl->ResectionGridColor[2] = blue;
  this->Modified();
}


//------------------------------------------------------------------------------
float vtkOpenGLResection2DPolyDataMapper::GetResectionOpacity() const
{
  return this->Impl->ResectionOpacity;
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::SetResectionOpacity(float margin)
{
  this->Impl->ResectionOpacity = margin;
  this->Modified();
}

//------------------------------------------------------------------------------
bool vtkOpenGLResection2DPolyDataMapper::GetResectionClipOut() const
{
  return this->Impl->ResectionClipOut;
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::SetResectionClipOut(bool clipOut)
{
  this->Impl->ResectionClipOut = clipOut;
  this->Modified();
}

//------------------------------------------------------------------------------
bool vtkOpenGLResection2DPolyDataMapper::GetInterpolatedMargins() const
{
  return this->Impl->InterpolatedMargins;
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::SetInterpolatedMargins(bool clipOut)
{
  this->Impl->InterpolatedMargins = clipOut;
  this->Modified();
}

//------------------------------------------------------------------------------
unsigned int vtkOpenGLResection2DPolyDataMapper::GetGridDivisions() const
{
  return this->Impl->GridDivisions;
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::SetGridDivisions(unsigned int divisions)
{
  this->Impl->GridDivisions = divisions;
  this->Modified();
}

//------------------------------------------------------------------------------
float vtkOpenGLResection2DPolyDataMapper::GetGridThicknessFactor() const
{
  return this->Impl->GridThicknessFactor;
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::SetGridThicknessFactor(float thickness)
{
  this->Impl->GridThicknessFactor = thickness;
  this->Modified();
}

//------------------------------------------------------------------------------
float const* vtkOpenGLResection2DPolyDataMapper::GetHepaticContourColor() const
{
  return this->Impl->HepaticContourColor;
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::SetHepaticContourColor(float color[3])
{
  this->Impl->HepaticContourColor[0] = color[0];
  this->Impl->HepaticContourColor[1] = color[1];
  this->Impl->HepaticContourColor[2] = color[2];
  this->Modified();
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::SetHepaticContourColor(float red, float green, float blue)
{
  this->Impl->HepaticContourColor[0] = red;
  this->Impl->HepaticContourColor[1] = green;
  this->Impl->HepaticContourColor[2] = blue;
  this->Modified();
}

//------------------------------------------------------------------------------
float const* vtkOpenGLResection2DPolyDataMapper::GetPortalContourColor() const
{
  return this->Impl->PortalContourColor;
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::SetPortalContourColor(float color[3])
{
  this->Impl->PortalContourColor[0] = color[0];
  this->Impl->PortalContourColor[1] = color[1];
  this->Impl->PortalContourColor[2] = color[2];
  this->Modified();
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::SetPortalContourColor(float red, float green, float blue)
{
  this->Impl->PortalContourColor[0] = red;
  this->Impl->PortalContourColor[1] = green;
  this->Impl->PortalContourColor[2] = blue;
  this->Modified();
}

//------------------------------------------------------------------------------
float vtkOpenGLResection2DPolyDataMapper::GetHepaticContourThickness() const
{
  return this->Impl->HepaticContourThickness;
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::SetHepaticContourThickness(float margin)
{
  this->Impl->HepaticContourThickness = margin;
  this->Modified();
}

//------------------------------------------------------------------------------
float vtkOpenGLResection2DPolyDataMapper::GetPortalContourThickness() const
{
  return this->Impl->PortalContourThickness;
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::SetPortalContourThickness(float margin)
{
  this->Impl->PortalContourThickness = margin;
  this->Modified();
}

//------------------------------------------------------------------------------
int vtkOpenGLResection2DPolyDataMapper::GetTextureNumComps() const
{
  return this->Impl->TextureNumComps;
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::SetTextureNumComps(int numComps)
{
  this->Impl->TextureNumComps = numComps;
  this->Modified();
}

//------------------------------------------------------------------------------
//unsigned int const* vtkOpenGLBezierResectionPolyDataMapper::GetMarkerStyleAvailable() const
//{
//  return this->Impl->MarkerStyleAvailable;
//}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::SetMarkerStyleAvailable(unsigned int status)
{
  this->Impl->MarkerStyleAvailable = status;
  this->Modified();
}

//------------------------------------------------------------------------------
float const* vtkOpenGLResection2DPolyDataMapper::GetMatRatio() const
{
  return this->Impl->MatRatio;
}

//------------------------------------------------------------------------------
void vtkOpenGLResection2DPolyDataMapper::SetMatRatio(float matR[2])
{
  this->Impl->MatRatio[0] = matR[0];
  this->Impl->MatRatio[1] = matR[1];
  this->Modified();
}
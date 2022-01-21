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

#include "vtkSlicerShaderHelper.h"

// MRML includes
#include <qMRMLThreeDWidget.h>
#include <vtkMRMLModelDisplayableManager.h>
#include <vtkMRMLModelDisplayNode.h>

// Slicer includes
#include <qSlicerApplication.h>
#include <qSlicerLayoutManager.h>

// VTK includes
#include <vtkActor.h>
#include <vtkCollection.h>
#include <vtkObjectFactory.h>
#include <vtkOpenGLPolyDataMapper.h>
#include <vtkOpenGLVertexBufferObjectGroup.h>
#include <vtkOpenGLVertexBufferObject.h>
#include <vtkShaderProperty.h>
#include <vtkUniforms.h>

//------------------------------------------------------------------------------
vtkStandardNewMacro(vtkSlicerShaderHelper);

//------------------------------------------------------------------------------
vtkSlicerShaderHelper::vtkSlicerShaderHelper()
  :TargetModelNode(nullptr)
{
}

//------------------------------------------------------------------------------
void vtkSlicerShaderHelper::PrintSelf(ostream& os, vtkIndent indent)
{
  Superclass::PrintSelf(os, indent);
}

//------------------------------------------------------------------------------
void vtkSlicerShaderHelper::AttachSlicingContourShader()
{
  vtkNew<vtkCollection> propertiesCollection;
  this->getShaderProperties(propertiesCollection.GetPointer());

  for(int index=0; index<propertiesCollection->GetNumberOfItems(); ++index)
    {
    auto shaderProperty =
      vtkShaderProperty::SafeDownCast(propertiesCollection->GetItemAsObject(index));
    if (!shaderProperty)
      {
      continue;
      }

    shaderProperty->AddVertexShaderReplacement(
      "//VTK::PositionVC::Dec",
      true,
      "//VTK::PositionVC::Dec\n"
      "out vec4 vertexMCVSOutput;\n",
      false
    );

    shaderProperty->AddVertexShaderReplacement(
      "//VTK::PositionVC::Impl",
      true,
      "//VTK::PositionVC::Impl\n"
      "vertexMCVSOutput = vertexMC;\n",
      false
    );

    shaderProperty->AddFragmentShaderReplacement(
      "//VTK::PositionVC::Dec",
      true,
      "//VTK::PositionVC::Dec\n"
      "in vec4 vertexMCVSOutput;\n"
      "vec4 fragPositionMC = vertexMCVSOutput;\n",
      false
    );

    shaderProperty->AddFragmentShaderReplacement(
      "//VTK::Color::Impl",
      true,
      "//VTK::Color::Impl\n"
      "  vec3 contourColor= vec3(1.0, 1.0 ,1.0);\n"
      "  vec3 w = -(planePositionMC.xyz*fragPositionMC.w - fragPositionMC.xyz);\n"
      "  float dist = (planeNormalMC.x * w.x + planeNormalMC.y * w.y + planeNormalMC.z * w.z) / sqrt( pow(planeNormalMC.x,2) + pow(planeNormalMC.y,2)+ pow(planeNormalMC.z,2));\n"
      "  if(abs(dist) < contourThickness && contourVisibility != 0){\n"
      "     ambientColor = contourColor;\n"
      "     diffuseColor = contourColor;\n"
      "     opacity = 1.0;\n"
      "  }\n",
      false
    );

    float position[] = {0.0f, 0.0f, 0.0f, 0.0f};
    float normal[] = {1.0f, 0.0f, 0.0f, 0.0f};

    auto fragmentUniforms = shaderProperty->GetFragmentCustomUniforms();
    fragmentUniforms->SetUniform4f("planePositionMC", position);
    fragmentUniforms->SetUniform4f("planeNormalMC", normal);
    fragmentUniforms->SetUniformf("contourThickness", 0.05);
    fragmentUniforms->SetUniformi("contourVisibility", 0);
    }
}

//------------------------------------------------------------------------------
void vtkSlicerShaderHelper::AttachDistanceContourShader()
{
  vtkNew<vtkCollection> propertiesCollection;
  this->getShaderProperties(propertiesCollection.GetPointer());

  for(int index=0; index<propertiesCollection->GetNumberOfItems(); ++index)
    {
    auto shaderProperty =
      vtkShaderProperty::SafeDownCast(propertiesCollection->GetItemAsObject(index));
    if (!shaderProperty)
      {
      continue;
      }

    shaderProperty->AddVertexShaderReplacement(
      "//VTK::PositionVC::Dec",
      true,
      "//VTK::PositionVC::Dec\n"
      "out vec4 vertexMCVSOutput;\n",
      false
    );

    shaderProperty->AddVertexShaderReplacement(
      "//VTK::PositionVC::Impl",
      true,
      "//VTK::PositionVC::Impl\n"
      "vertexMCVSOutput = vertexMC;\n",
      false
    );

    shaderProperty->AddFragmentShaderReplacement(
      "//VTK::PositionVC::Dec",
      true,
      "//VTK::PositionVC::Dec\n"
      "in vec4 vertexMCVSOutput;\n"
      "vec4 fragPositionMC = vertexMCVSOutput;\n",
      false
    );

    shaderProperty->AddFragmentShaderReplacement(
      "//VTK::Color::Impl",
      true,
      "//VTK::Color::Impl\n"
      "  vec3 contourColor= vec3(1.0, 1.0 ,1.0);\n"
      "  float refDist= distance(externalPointMC, referencePointMC);\n"
      "  float dist = distance(referencePointMC, fragPositionMC);\n"
      "  if(abs(dist-refDist) < contourThickness && contourVisibility != 0){\n"
      "     ambientColor = contourColor;\n"
      "     diffuseColor = contourColor;\n"
      "     opacity = 1.0;\n"
      "  }\n",
      false
    );

    float externalPointMC[] = {0.0f, 0.0f, 0.0f, 0.0f};
    float referencePointMC[] = {0.0f, 0.0f, 0.0f, 0.0f};

    auto fragmentUniforms = shaderProperty->GetFragmentCustomUniforms();
    fragmentUniforms->SetUniform4f("externalPointMC", externalPointMC);
    fragmentUniforms->SetUniform4f("referencePointMC", referencePointMC);
    fragmentUniforms->SetUniformf("contourThickness", 0.05);
    fragmentUniforms->SetUniformi("contourVisibility", 0);
    }
}
//------------------------------------------------------------------------------
void vtkSlicerShaderHelper::getShaderProperties(vtkCollection* propertiesCollection)
{

  if (!this->TargetModelNode)
    {
    vtkWarningMacro("Invalid  model node");
    return;
    }

  if (!propertiesCollection)
    {
    vtkWarningMacro("Invalid  properties collection");
    return;
    }

  auto layoutManager = qSlicerApplication::application()->layoutManager();
  if (!layoutManager)
    {
    vtkWarningMacro("No valid layout manager");
    return;
    }

  for (int threeDViewId = 0; threeDViewId < layoutManager->threeDViewCount(); ++threeDViewId)
    {

    auto threeDWidget = layoutManager->threeDWidget(threeDViewId);
    if (!threeDWidget)
      {
      continue;
      }

    vtkNew<vtkCollection> displayableManagers;
    threeDWidget->getDisplayableManagers(displayableManagers.GetPointer());

    for(int index = 0; index < displayableManagers->GetNumberOfItems(); ++index)
      {

      auto modelDisplayableManager =
        vtkMRMLModelDisplayableManager::SafeDownCast(displayableManagers->GetItemAsObject(index));
      if (!modelDisplayableManager)
        {
        continue;
        }

      auto modelDisplayNode = this->TargetModelNode->GetDisplayNode();
      if (!modelDisplayNode)
        {
        continue;
        }
      auto modelActor =
        vtkActor::SafeDownCast(modelDisplayableManager->GetActorByID(modelDisplayNode->GetID()));
      if (!modelActor)
        {
        continue;
        }

      this->TargetModelActors->AddItem(modelActor);

      auto shaderProperty = modelActor->GetShaderProperty();
      if (!shaderProperty)
        {
        continue;
        }

      // Cache the shader property
      propertiesCollection->AddItem(shaderProperty);

      // NOTE: Query and cache the target model VBOs as they are useful during update in the widget representation

      auto modelMapper = vtkOpenGLPolyDataMapper::SafeDownCast(modelActor->GetMapper());
      if (!modelMapper)
        {
        vtkWarningMacro("Invalid model mapper");
        continue;
        }

      auto modelVBOs = modelMapper->GetVBOs();
      if (!modelVBOs)
        {
        vtkWarningMacro("Invalid model VBOs");
        continue;
        }

      auto modelVertexVBO  = modelVBOs->GetVBO("vertexMC");
      if (!modelVertexVBO)
        {
        vtkWarningMacro("Invalid model vertexMC VBO");
        continue;
        }

      this->TargetModelVertexVBOs->AddItem(modelVertexVBO);
      }
    }
}

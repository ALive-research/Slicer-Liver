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

// This module MRML includes
#include "vtkMRMLLiverResectionNode.h"
#include "vtkMRMLLiverResectionCSVStorageNode.h"

// MRML includes
#include <vtkMRMLScene.h>
#include <vtkMRMLSegmentationNode.h>

// VTK includes
#include <vtkNew.h>
#include <vtkObjectFactory.h>

//--------------------------------------------------------------------------------
vtkMRMLNodeNewMacro(vtkMRMLLiverResectionNode);

//--------------------------------------------------------------------------------
vtkMRMLLiverResectionNode::vtkMRMLLiverResectionNode()
  :TargetOrganModelNode(nullptr), DistanceMapVolumeNode(nullptr), VascularSegmentsVolumeNode(nullptr),
   State(ResectionState::Initialization), InitMode(InitializationMode::Flat),
   ResectionMargin(0.0), UncertaintyMargin(0.0), ClipOut(false), WidgetVisibility(true),
   InterpolatedMargins(false), ResectionColor{1.0f, 1.0f, 1.0f},
   ResectionMarginColor{1.0f, 0.0f, 0.0f}, UncertaintyMarginColor{1.0f, 1.0f, 0.0f},
   ResectionOpacity(1.0f), GridVisibility(false), GridThickness(0.0f), ShowResection2D(false), HepaticContourThickness(0.3f), PortalContourThickness(0.3f),
   HepaticContourColor{0.0f, 151.0/255.0f, 206.0/255.0f}, PortalContourColor{216.0/255.0f, 101.0/255.0f, 79.0/255.0f},
   TextureNumComps(0), EnableFlexibleBoundary(false), MirrorDisplay(false), Grid3DVisibility(true), Grid2DVisibility(false)
{
}

//----------------------------------------------------------------------------
vtkMRMLLiverResectionNode::~vtkMRMLLiverResectionNode() = default;

//----------------------------------------------------------------------------
void vtkMRMLLiverResectionNode::PrintSelf(ostream& os, vtkIndent indent)
{
  Superclass::PrintSelf(os,indent);
}

//-------------------------------------------------------------------------
vtkMRMLStorageNode* vtkMRMLLiverResectionNode::CreateDefaultStorageNode()
{
  vtkMRMLScene* scene = this->GetScene();
  if (scene == nullptr)
    {
    vtkErrorMacro("CreateDefaultStorageNode failed: scene is invalid");
    return nullptr;
    }
  return vtkMRMLStorageNode::SafeDownCast(
    scene->CreateNodeByClass("vtkMRMLLiverResectionCSVStorageNode"));
}

//----------------------------------------------------------------------------
bool vtkMRMLLiverResectionNode::SetInitializationControlPoints(vtkPoints* controlPoints)
{
  if (!controlPoints || controlPoints->GetNumberOfPoints() < 2)
    {
    return false;
    }

  this->InitializationControlPoints->SetPoint(0, controlPoints->GetPoint(0));
  this->InitializationControlPoints->SetPoint(1, controlPoints->GetPoint(1));
  this->Modified();

  return true;
}

//----------------------------------------------------------------------------
bool vtkMRMLLiverResectionNode::SetBezierSurfaceControlPoints(vtkPoints* controlPoints)
{
  if (!controlPoints || controlPoints->GetNumberOfPoints() < 16)
    {
    return false;
    }

  for (int i=0; i<16; ++i)
    {
    this->InitializationControlPoints->SetPoint(i, controlPoints->GetPoint(i));
    }
  this->Modified();

  return true;
}

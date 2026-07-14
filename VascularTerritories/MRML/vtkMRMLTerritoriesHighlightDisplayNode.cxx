/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

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

  This file was originally developed for the Slicer-Liver extension as
  part of the vessel-adhering-highlight feature (ADR-0013 Pipeline
  pattern, ADR-0025 display-node/pipeline template, ADR-0033 hover
  discipline).

==============================================================================*/

// This module MRML includes
#include "vtkMRMLTerritoriesHighlightDisplayNode.h"

// MRML includes
#include <vtkMRMLNodePropertyMacros.h>
#include <vtkMRMLSegmentationNode.h>

// VTK includes
#include <vtkNew.h>
#include <vtkObjectFactory.h>

//------------------------------------------------------------------------------
vtkMRMLNodeNewMacro(vtkMRMLTerritoriesHighlightDisplayNode);

//------------------------------------------------------------------------------
vtkMRMLTerritoriesHighlightDisplayNode::vtkMRMLTerritoriesHighlightDisplayNode()
  // 3 mm reads clearly as an adhering marker on a liver-scale vessel
  // surface without occluding the mesh under it.
  : Adhering(false)
  , Radius(3.0)
{
  this->AdheringPointWorld[0] = 0.0;
  this->AdheringPointWorld[1] = 0.0;
  this->AdheringPointWorld[2] = 0.0;

  // Seed a warm highlight colour on the inherited vtkMRMLDisplayNode
  // Color member; the base node persists Color and Visibility.
  this->SetColor(1.0, 0.6, 0.1);
}

//------------------------------------------------------------------------------
vtkMRMLTerritoriesHighlightDisplayNode::~vtkMRMLTerritoriesHighlightDisplayNode() = default;

//------------------------------------------------------------------------------
void vtkMRMLTerritoriesHighlightDisplayNode::WriteXML(ostream& of, int nIndent)
{
  Superclass::WriteXML(of, nIndent);

  // AdheringPointWorld + Adhering are TRANSIENT (re-derived from the
  // cursor every hover) and are deliberately absent here; only the
  // marker Radius round-trips (Color / Visibility persist on the base).
  vtkMRMLWriteXMLBeginMacro(of);
  vtkMRMLWriteXMLFloatMacro(radius, Radius);
  vtkMRMLWriteXMLEndMacro();
}

//------------------------------------------------------------------------------
void vtkMRMLTerritoriesHighlightDisplayNode::ReadXMLAttributes(const char** atts)
{
  int disabledModify = this->StartModify();

  Superclass::ReadXMLAttributes(atts);

  vtkMRMLReadXMLBeginMacro(atts);
  vtkMRMLReadXMLFloatMacro(radius, Radius);
  vtkMRMLReadXMLEndMacro();

  this->EndModify(disabledModify);
}

//------------------------------------------------------------------------------
void vtkMRMLTerritoriesHighlightDisplayNode::CopyContent(vtkMRMLNode* anode, bool deepCopy /*=true*/)
{
  MRMLNodeModifyBlocker blocker(this);
  Superclass::CopyContent(anode, deepCopy);

  vtkMRMLCopyBeginMacro(anode);
  vtkMRMLCopyFloatMacro(Radius);
  vtkMRMLCopyEndMacro();
}

//------------------------------------------------------------------------------
void vtkMRMLTerritoriesHighlightDisplayNode::SetAndObservePickSurfaceNodeID(const char* segmentationNodeID)
{
  this->SetAndObserveNodeReferenceID(this->GetPickSurfaceReferenceRole(), segmentationNodeID);
}

//------------------------------------------------------------------------------
vtkMRMLSegmentationNode* vtkMRMLTerritoriesHighlightDisplayNode::GetPickSurfaceNode()
{
  return vtkMRMLSegmentationNode::SafeDownCast(this->GetNodeReference(this->GetPickSurfaceReferenceRole()));
}

//------------------------------------------------------------------------------
void vtkMRMLTerritoriesHighlightDisplayNode::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);

  vtkMRMLPrintBeginMacro(os, indent);
  vtkMRMLPrintVectorMacro(AdheringPointWorld, double, 3);
  vtkMRMLPrintBooleanMacro(Adhering);
  vtkMRMLPrintFloatMacro(Radius);
  vtkMRMLPrintEndMacro();
}

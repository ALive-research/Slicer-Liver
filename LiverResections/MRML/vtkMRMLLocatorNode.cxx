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
  part of the v2.0 locator work (see ADR-0025 §"The node").

==============================================================================*/

// This module MRML includes
#include "vtkMRMLLocatorNode.h"
#include "vtkMRMLLocatorDisplayNode.h"

// MRML includes
#include <vtkMRMLNodePropertyMacros.h>
#include <vtkMRMLScene.h>

// VTK includes
#include <vtkNew.h>
#include <vtkObjectFactory.h>
#include <vtkSmartPointer.h>

//------------------------------------------------------------------------------
vtkMRMLNodeNewMacro(vtkMRMLLocatorNode);

//------------------------------------------------------------------------------
vtkMRMLLocatorNode::vtkMRMLLocatorNode()
  : LocatorActive(false)
{
  this->PickedPositionWorld[0] = 0.0;
  this->PickedPositionWorld[1] = 0.0;
  this->PickedPositionWorld[2] = 0.0;
}

//------------------------------------------------------------------------------
vtkMRMLLocatorNode::~vtkMRMLLocatorNode() = default;

//------------------------------------------------------------------------------
void vtkMRMLLocatorNode::CreateDefaultDisplayNodes()
{
  if (vtkMRMLLocatorDisplayNode::SafeDownCast(this->GetDisplayNode()) != nullptr)
  {
    // Display node already exists.
    return;
  }
  if (this->GetScene() == nullptr)
  {
    vtkErrorMacro("vtkMRMLLocatorNode::CreateDefaultDisplayNodes"
                  " failed: scene is invalid");
    return;
  }
  auto displayNode = vtkSmartPointer<vtkMRMLLocatorDisplayNode>::New();
  this->GetScene()->AddNode(displayNode);
  this->SetAndObserveDisplayNodeID(displayNode->GetID());
}

//------------------------------------------------------------------------------
void vtkMRMLLocatorNode::WriteXML(ostream& of, int nIndent)
{
  // Persistence = presence, NOT live position (ADR-0025 §"The node").
  // Only the presence flag is written; PickedPositionWorld is
  // deliberately transient and re-derived from interaction.
  Superclass::WriteXML(of, nIndent);

  vtkMRMLWriteXMLBeginMacro(of);
  vtkMRMLWriteXMLBooleanMacro(locatorActive, LocatorActive);
  vtkMRMLWriteXMLEndMacro();
}

//------------------------------------------------------------------------------
void vtkMRMLLocatorNode::ReadXMLAttributes(const char** atts)
{
  int disabledModify = this->StartModify();
  Superclass::ReadXMLAttributes(atts);

  // Presence only; the live picked position is not read back (it has
  // no XML attribute) and stays at the freshly-constructed default.
  vtkMRMLReadXMLBeginMacro(atts);
  vtkMRMLReadXMLBooleanMacro(locatorActive, LocatorActive);
  vtkMRMLReadXMLEndMacro();

  this->EndModify(disabledModify);
}

//------------------------------------------------------------------------------
void vtkMRMLLocatorNode::CopyContent(vtkMRMLNode* anode, bool deepCopy /*=true*/)
{
  MRMLNodeModifyBlocker blocker(this);
  Superclass::CopyContent(anode, deepCopy);

  // CopyContent follows the vtkMRMLCrosshairNode precedent, which
  // deep-copies its live RAS alongside the persisted presence fields.
  // The presence flag is the ADR-0025 contract; the live position is
  // copied as a convenience for in-memory clones (it is still absent
  // from the XML round-trip).
  vtkMRMLCopyBeginMacro(anode);
  vtkMRMLCopyBooleanMacro(LocatorActive);
  vtkMRMLCopyVectorMacro(PickedPositionWorld, double, 3);
  vtkMRMLCopyEndMacro();
}

//------------------------------------------------------------------------------
void vtkMRMLLocatorNode::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);

  vtkMRMLPrintBeginMacro(os, indent);
  vtkMRMLPrintBooleanMacro(LocatorActive);
  vtkMRMLPrintVectorMacro(PickedPositionWorld, double, 3);
  vtkMRMLPrintEndMacro();
}

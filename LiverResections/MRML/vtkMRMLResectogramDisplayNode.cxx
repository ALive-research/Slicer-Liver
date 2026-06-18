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
  part of the T3 ResectogramPipeline work (see ADR-0013 §1 + §5 and
  ADR-0025 §Context).

==============================================================================*/

// This module MRML includes
#include "vtkMRMLResectogramDisplayNode.h"

// MRML includes
#include <vtkMRMLNodePropertyMacros.h>

// VTK includes
#include <vtkNew.h>
#include <vtkObjectFactory.h>

//------------------------------------------------------------------------------
vtkMRMLNodeNewMacro(vtkMRMLResectogramDisplayNode);

//------------------------------------------------------------------------------
vtkMRMLResectogramDisplayNode::vtkMRMLResectogramDisplayNode()
  : ShowResection2D(false)
  , MirrorDisplay(false)
  , EnableFlexibleBoundary(false)
  , TextureNumComps(0)
  , BlurEnabled(false)
  , BlurRadius(2.0)
{
}

//------------------------------------------------------------------------------
vtkMRMLResectogramDisplayNode::~vtkMRMLResectogramDisplayNode() = default;

//------------------------------------------------------------------------------
void vtkMRMLResectogramDisplayNode::WriteXML(ostream& of, int nIndent)
{
  Superclass::WriteXML(of, nIndent);

  vtkMRMLWriteXMLBeginMacro(of);
  vtkMRMLWriteXMLBooleanMacro(showResection2D, ShowResection2D);
  vtkMRMLWriteXMLBooleanMacro(mirrorDisplay, MirrorDisplay);
  vtkMRMLWriteXMLBooleanMacro(enableFlexibleBoundary, EnableFlexibleBoundary);
  vtkMRMLWriteXMLIntMacro(textureNumComps, TextureNumComps);
  vtkMRMLWriteXMLBooleanMacro(blurEnabled, BlurEnabled);
  vtkMRMLWriteXMLFloatMacro(blurRadius, BlurRadius);
  vtkMRMLWriteXMLEndMacro();
}

//------------------------------------------------------------------------------
void vtkMRMLResectogramDisplayNode::ReadXMLAttributes(const char** atts)
{
  int disabledModify = this->StartModify();

  Superclass::ReadXMLAttributes(atts);

  vtkMRMLReadXMLBeginMacro(atts);
  vtkMRMLReadXMLBooleanMacro(showResection2D, ShowResection2D);
  vtkMRMLReadXMLBooleanMacro(mirrorDisplay, MirrorDisplay);
  vtkMRMLReadXMLBooleanMacro(enableFlexibleBoundary, EnableFlexibleBoundary);
  vtkMRMLReadXMLIntMacro(textureNumComps, TextureNumComps);
  vtkMRMLReadXMLBooleanMacro(blurEnabled, BlurEnabled);
  vtkMRMLReadXMLFloatMacro(blurRadius, BlurRadius);
  vtkMRMLReadXMLEndMacro();

  this->EndModify(disabledModify);
}

//------------------------------------------------------------------------------
void vtkMRMLResectogramDisplayNode::CopyContent(vtkMRMLNode* anode, bool deepCopy /*=true*/)
{
  MRMLNodeModifyBlocker blocker(this);
  Superclass::CopyContent(anode, deepCopy);

  vtkMRMLCopyBeginMacro(anode);
  vtkMRMLCopyBooleanMacro(ShowResection2D);
  vtkMRMLCopyBooleanMacro(MirrorDisplay);
  vtkMRMLCopyBooleanMacro(EnableFlexibleBoundary);
  vtkMRMLCopyIntMacro(TextureNumComps);
  vtkMRMLCopyBooleanMacro(BlurEnabled);
  vtkMRMLCopyFloatMacro(BlurRadius);
  vtkMRMLCopyEndMacro();
}

//------------------------------------------------------------------------------
void vtkMRMLResectogramDisplayNode::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);

  vtkMRMLPrintBeginMacro(os, indent);
  vtkMRMLPrintBooleanMacro(ShowResection2D);
  vtkMRMLPrintBooleanMacro(MirrorDisplay);
  vtkMRMLPrintBooleanMacro(EnableFlexibleBoundary);
  vtkMRMLPrintIntMacro(TextureNumComps);
  vtkMRMLPrintBooleanMacro(BlurEnabled);
  vtkMRMLPrintFloatMacro(BlurRadius);
  vtkMRMLPrintEndMacro();
}

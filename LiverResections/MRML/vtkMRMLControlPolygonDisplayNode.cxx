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
  part of the control-polygon display aspect (see ADR-0033).

==============================================================================*/

// This module MRML includes
#include "vtkMRMLControlPolygonDisplayNode.h"

// MRML includes
#include <vtkMRMLNodePropertyMacros.h>

// VTK includes
#include <vtkNew.h>
#include <vtkObjectFactory.h>

//------------------------------------------------------------------------------
vtkMRMLNodeNewMacro(vtkMRMLControlPolygonDisplayNode);

//------------------------------------------------------------------------------
vtkMRMLControlPolygonDisplayNode::vtkMRMLControlPolygonDisplayNode()
  // HandleRadius matches the retired v1 widget's glyph radius so the v2
  // handles read at the familiar size (ADR-0033).
  : HandleRadius(2.5)
  , HandleColor{ 1.0, 1.0, 1.0 }
  , EdgeColor{ 0.7, 0.7, 0.7 }
  , EdgeWidth(1.0)
{
}

//------------------------------------------------------------------------------
vtkMRMLControlPolygonDisplayNode::~vtkMRMLControlPolygonDisplayNode() = default;

//------------------------------------------------------------------------------
void vtkMRMLControlPolygonDisplayNode::WriteXML(ostream& of, int nIndent)
{
  Superclass::WriteXML(of, nIndent);

  vtkMRMLWriteXMLBeginMacro(of);
  vtkMRMLWriteXMLFloatMacro(handleRadius, HandleRadius);
  vtkMRMLWriteXMLVectorMacro(handleColor, HandleColor, double, 3);
  vtkMRMLWriteXMLVectorMacro(edgeColor, EdgeColor, double, 3);
  vtkMRMLWriteXMLFloatMacro(edgeWidth, EdgeWidth);
  vtkMRMLWriteXMLEndMacro();
}

//------------------------------------------------------------------------------
void vtkMRMLControlPolygonDisplayNode::ReadXMLAttributes(const char** atts)
{
  int disabledModify = this->StartModify();

  Superclass::ReadXMLAttributes(atts);

  vtkMRMLReadXMLBeginMacro(atts);
  vtkMRMLReadXMLFloatMacro(handleRadius, HandleRadius);
  vtkMRMLReadXMLVectorMacro(handleColor, HandleColor, double, 3);
  vtkMRMLReadXMLVectorMacro(edgeColor, EdgeColor, double, 3);
  vtkMRMLReadXMLFloatMacro(edgeWidth, EdgeWidth);
  vtkMRMLReadXMLEndMacro();

  this->EndModify(disabledModify);
}

//------------------------------------------------------------------------------
void vtkMRMLControlPolygonDisplayNode::CopyContent(vtkMRMLNode* anode, bool deepCopy /*=true*/)
{
  MRMLNodeModifyBlocker blocker(this);
  Superclass::CopyContent(anode, deepCopy);

  vtkMRMLCopyBeginMacro(anode);
  vtkMRMLCopyFloatMacro(HandleRadius);
  vtkMRMLCopyVectorMacro(HandleColor, double, 3);
  vtkMRMLCopyVectorMacro(EdgeColor, double, 3);
  vtkMRMLCopyFloatMacro(EdgeWidth);
  vtkMRMLCopyEndMacro();
}

//------------------------------------------------------------------------------
void vtkMRMLControlPolygonDisplayNode::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);

  vtkMRMLPrintBeginMacro(os, indent);
  vtkMRMLPrintFloatMacro(HandleRadius);
  vtkMRMLPrintVectorMacro(HandleColor, double, 3);
  vtkMRMLPrintVectorMacro(EdgeColor, double, 3);
  vtkMRMLPrintFloatMacro(EdgeWidth);
  vtkMRMLPrintEndMacro();
}

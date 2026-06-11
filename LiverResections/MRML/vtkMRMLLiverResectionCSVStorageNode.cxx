/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2021-2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Redistribution and use in source and binary forms, with or without
  modification, are permitted provided that the following conditions
  are met:

  * Redistributions of source code must retain the above copyright
    notice, this list of conditions and the following disclaimer.

  * Redistributions in binary form must reproduce the above copyright
    notice, this list of conditions and the following disclaimer in the
    documentation and/or other materials provided with the distribution.

  * Neither the name of Kitware, Inc. nor the names of Contributors
    may be used to endorse or promote products derived from this
    software without specific prior written permission.

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

#include "vtkMRMLLiverResectionCSVStorageNode.h"
#include "vtkMRMLMarkupsBezierSurfaceNode.h"

// VTK includes
#include <vtkObjectFactory.h>
#include <vtkStringArray.h>

//------------------------------------------------------------------------------
vtkMRMLNodeNewMacro(vtkMRMLLiverResectionCSVStorageNode);

//----------------------------------------------------------------------------
vtkMRMLLiverResectionCSVStorageNode::vtkMRMLLiverResectionCSVStorageNode()
{
  this->DefaultWriteFileExtension = "lrp.fcsv";
  this->FieldDelimiterCharacters = ",";
}

//----------------------------------------------------------------------------
vtkMRMLLiverResectionCSVStorageNode::~vtkMRMLLiverResectionCSVStorageNode() = default;

//----------------------------------------------------------------------------
void vtkMRMLLiverResectionCSVStorageNode::PrintSelf(ostream& os, vtkIndent indent)
{
  Superclass::PrintSelf(os, indent);
}

//----------------------------------------------------------------------------
bool vtkMRMLLiverResectionCSVStorageNode::CanReadInReferenceNode(vtkMRMLNode* refNode)
{
  return refNode != nullptr && refNode->IsA("vtkMRMLMarkupsBezierSurfaceNode");
}

//----------------------------------------------------------------------------
void vtkMRMLLiverResectionCSVStorageNode::InitializeSupportedReadFileTypes()
{
  this->SupportedReadFileTypes->InsertNextValue("Liver Resection Planning CSV (lrp.fcsv)");
}

//----------------------------------------------------------------------------
void vtkMRMLLiverResectionCSVStorageNode::InitializeSupportedWriteFileTypes()
{
  this->SupportedWriteFileTypes->InsertNextValue("Liver Resection Planning CSV (lrp.fcsv)");
}

//----------------------------------------------------------------------------
int vtkMRMLLiverResectionCSVStorageNode::WriteDataInternal(vtkMRMLNode* refNode)
{
  auto bezierSurfaceNode = vtkMRMLMarkupsBezierSurfaceNode::SafeDownCast(refNode);

  if (bezierSurfaceNode == nullptr)
  {
    vtkErrorMacro("WriteDataInternal: input node is not a vtkMRMLMarkupsBezierSurfaceNode");
    return 0;
  }

  return Superclass::WriteDataInternal(bezierSurfaceNode);
}

//----------------------------------------------------------------------------
int vtkMRMLLiverResectionCSVStorageNode::ReadDataInternal(vtkMRMLNode* refNode)
{
  if (!refNode)
  {
    vtkErrorMacro("ReadDataInternal: null reference node!");
    return 0;
  }

  std::string fullName = this->GetFullNameFromFileName();

  if (fullName.empty())
  {
    vtkErrorMacro("vtkMRMLLiverResectionCSVStorageNode: File name not specified");
    return 0;
  }

  // The CSV parse vehicle operates directly on a markups Bezier-surface
  // node -- the v1 ``.lrp.fcsv`` is a 15-column Markups-fiducial CSV, so
  // the superclass reads the control points straight into it.  This
  // parse seam is intentionally independent of the retired v1 resection
  // node family (ADR-0014 §"Fourth layer").
  auto bezierSurfaceNode = vtkMRMLMarkupsBezierSurfaceNode::SafeDownCast(refNode);
  if (!bezierSurfaceNode)
  {
    vtkErrorMacro("vtkMRMLLiverResectionCSVStorageNode: reference node is not a vtkMRMLMarkupsBezierSurfaceNode.");
    return 0;
  }

  return Superclass::ReadDataInternal(bezierSurfaceNode);
}

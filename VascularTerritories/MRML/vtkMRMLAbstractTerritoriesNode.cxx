/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Implementation of the abstract territories base class (ADR-0023
  §"Class abstraction for territories" + the architecture-doc UML at
  Docs/architecture/territories-class-hierarchy.md).  Non-instantiable
  per ``vtkAbstractTypeMacro``; concrete subtypes supply ``New()`` via
  ``vtkStandardNewMacro``.

  Per the 2026-05-25 wrapper-vs-carrier amendment to ADR-0023 the
  abstract base owns a typed ``segments`` node-reference role pointing
  to a canonical ``vtkMRMLSegmentationNode`` (the data carrier).  The
  retired ``GetLabelMap()`` interface entry is replaced by
  ``GetSegmentationNode()`` resolved through the role.

==============================================================================*/

// This module MRML includes
#include "vtkMRMLAbstractTerritoriesNode.h"

// MRML includes
#include <vtkMRMLSegmentationNode.h>

//------------------------------------------------------------------------------
vtkMRMLAbstractTerritoriesNode::vtkMRMLAbstractTerritoriesNode()
{
  // Typed node-reference role to the canonical segmentation carrier.
  // The Slicer-core class-name filter is intentionally not bound here
  // -- consumers downstream do the cast.  Keeping the role name as a
  // constant in the header lets the storage path + Logic share the
  // single literal.
  this->AddNodeReferenceRole(GetSegmentsReferenceRole(), GetSegmentsReferenceRole());
}

//------------------------------------------------------------------------------
vtkMRMLAbstractTerritoriesNode::~vtkMRMLAbstractTerritoriesNode() = default;

//------------------------------------------------------------------------------
void vtkMRMLAbstractTerritoriesNode::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);
}

//------------------------------------------------------------------------------
vtkMRMLSegmentationNode* vtkMRMLAbstractTerritoriesNode::GetSegmentationNode()
{
  return vtkMRMLSegmentationNode::SafeDownCast(this->GetNodeReference(GetSegmentsReferenceRole()));
}

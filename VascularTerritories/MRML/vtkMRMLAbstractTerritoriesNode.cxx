/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Implementation of the abstract territories base class (ADR-0023
  §"Class abstraction for territories" + the architecture-doc UML at
  Docs/architecture/territories-class-hierarchy.md).  Non-instantiable
  per ``vtkAbstractTypeMacro``; concrete subtypes supply ``New()`` via
  ``vtkStandardNewMacro``.

==============================================================================*/

// This module MRML includes
#include "vtkMRMLAbstractTerritoriesNode.h"

//------------------------------------------------------------------------------
vtkMRMLAbstractTerritoriesNode::vtkMRMLAbstractTerritoriesNode() = default;

//------------------------------------------------------------------------------
vtkMRMLAbstractTerritoriesNode::~vtkMRMLAbstractTerritoriesNode() = default;

//------------------------------------------------------------------------------
void vtkMRMLAbstractTerritoriesNode::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);
}

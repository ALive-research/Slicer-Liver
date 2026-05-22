/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Implementation of the abstract territories base class (ADR-0023
  §"Class abstraction for territories" + the architecture-doc UML at
  Docs/architecture/territories-class-hierarchy.md).  ``New()``
  intentionally returns ``nullptr`` — see the header rationale.

==============================================================================*/

// This module MRML includes
#include "vtkMRMLAbstractTerritoriesNode.h"

// VTK includes
#include <vtkObjectFactory.h>

//------------------------------------------------------------------------------
// Runtime sentinel: the abstract base provides a ``New()`` symbol so
// VTK's Python wrapping pipeline resolves it for the exported class,
// but it returns ``nullptr`` to prevent callers from accidentally
// instantiating a partially-initialised territories node.  Concrete
// subclasses ``vtkMRMLStdCouinaudTerritoriesNode`` and
// ``vtkMRMLCustomTerritoriesNode`` supply real ``New()`` bodies via
// ``vtkStandardNewMacro``.
//------------------------------------------------------------------------------
vtkMRMLAbstractTerritoriesNode* vtkMRMLAbstractTerritoriesNode::New()
{
  return nullptr;
}

//------------------------------------------------------------------------------
vtkMRMLAbstractTerritoriesNode::vtkMRMLAbstractTerritoriesNode() = default;

//------------------------------------------------------------------------------
vtkMRMLAbstractTerritoriesNode::~vtkMRMLAbstractTerritoriesNode() = default;

//------------------------------------------------------------------------------
void vtkMRMLAbstractTerritoriesNode::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);
}

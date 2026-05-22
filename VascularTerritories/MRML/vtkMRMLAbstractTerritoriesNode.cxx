/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Stub translation unit for the v2.0.0 territories node base class
  (ADR-0023 §"Class abstraction for territories").  Lives alongside
  the header so the MRML library has something to link against from
  the moment the test-first scaffolding lands; the real method bodies
  are filled in by the follow-up implementer commit per ADR-0027.

==============================================================================*/

// This module MRML includes
#include "vtkMRMLAbstractTerritoriesNode.h"

// VTK includes
#include <vtkObjectFactory.h>

//------------------------------------------------------------------------------
// No vtkStandardNewMacro / vtkMRMLNodeNewMacro: the class is abstract.
// Subclasses ``vtkMRMLStdCouinaudTerritoriesNode`` and
// ``vtkMRMLCustomTerritoriesNode`` supply their own ``New()``.
//------------------------------------------------------------------------------

//------------------------------------------------------------------------------
vtkMRMLAbstractTerritoriesNode::vtkMRMLAbstractTerritoriesNode() = default;

//------------------------------------------------------------------------------
vtkMRMLAbstractTerritoriesNode::~vtkMRMLAbstractTerritoriesNode() = default;

//------------------------------------------------------------------------------
void vtkMRMLAbstractTerritoriesNode::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);
}

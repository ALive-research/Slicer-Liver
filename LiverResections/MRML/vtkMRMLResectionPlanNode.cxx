/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Implementation of vtkMRMLResectionPlanNode — the clinical wrapper
  introduced by the 2026-05-25 wrapper-vs-carrier amendment to
  ADR-0014 §"Fourth layer: clinical/method wrapper" and ADR-0023
  §"Class abstraction for surfaces".

==============================================================================*/

// This module MRML includes
#include "vtkMRMLResectionPlanNode.h"
#include "vtkMRMLResectionPlanStorageNode.h"
#include "vtkMRMLAbstractParametricSurfaceNode.h"

// MRML includes
#include <vtkMRMLNodePropertyMacros.h>

// VTK includes
#include <vtkNew.h>
#include <vtkObjectFactory.h>

// STD includes
#include <cstring>

//------------------------------------------------------------------------------
vtkMRMLNodeNewMacro(vtkMRMLResectionPlanNode);

//------------------------------------------------------------------------------
vtkMRMLResectionPlanNode::vtkMRMLResectionPlanNode()
  : SafetyMargin_mm(0.0)
  , RiskMargin_mm(0.0)
  , OrderIndex(-1)
  , State(PlanState::Init)
{
  // Typed node-reference role to the surface carrier.  The role name
  // is the canonical "geometry" string fixed by
  // GetGeometryReferenceRole().  No content-modified observation is
  // wired here -- the plan's WriteXML only writes the light scalars;
  // surface bulk data persists through the storage node, not through
  // the .mrml XML.
  this->AddNodeReferenceRole(GetGeometryReferenceRole(), GetGeometryReferenceRole());
}

//------------------------------------------------------------------------------
vtkMRMLResectionPlanNode::~vtkMRMLResectionPlanNode() = default;

//------------------------------------------------------------------------------
vtkMRMLStorageNode* vtkMRMLResectionPlanNode::CreateDefaultStorageNode()
{
  return vtkMRMLResectionPlanStorageNode::New();
}

//------------------------------------------------------------------------------
const char* vtkMRMLResectionPlanNode::GetStateAsString(int state)
{
  switch (state)
  {
    case Init: return "Init";
    case Planning: return "Planning";
    case Confirmed: return "Confirmed";
    default: return "Invalid";
  }
}

//------------------------------------------------------------------------------
int vtkMRMLResectionPlanNode::GetStateFromString(const char* name)
{
  if (name == nullptr)
  {
    return -1;
  }
  for (int i = 0; i < PlanState_Last; ++i)
  {
    if (std::strcmp(name, GetStateAsString(i)) == 0)
    {
      return i;
    }
  }
  return -1;
}

//------------------------------------------------------------------------------
vtkMRMLAbstractParametricSurfaceNode* vtkMRMLResectionPlanNode::GetGeometryNode()
{
  return vtkMRMLAbstractParametricSurfaceNode::SafeDownCast(this->GetNodeReference(GetGeometryReferenceRole()));
}

//------------------------------------------------------------------------------
void vtkMRMLResectionPlanNode::SetAndObserveGeometryNode(vtkMRMLAbstractParametricSurfaceNode* surface)
{
  this->SetAndObserveNodeReferenceID(GetGeometryReferenceRole(), surface ? surface->GetID() : nullptr);
}

//------------------------------------------------------------------------------
void vtkMRMLResectionPlanNode::WriteXML(ostream& of, int nIndent)
{
  // Light scalars only -- bulk surface data persists through the
  // storage node per the Markups precedent (vtkMRMLMarkupsNode::WriteXML).
  Superclass::WriteXML(of, nIndent);

  vtkMRMLWriteXMLBeginMacro(of);
  vtkMRMLWriteXMLFloatMacro(safetyMargin_mm, SafetyMargin_mm);
  vtkMRMLWriteXMLFloatMacro(riskMargin_mm, RiskMargin_mm);
  vtkMRMLWriteXMLIntMacro(orderIndex, OrderIndex);
  vtkMRMLWriteXMLEnumMacro(state, State);
  vtkMRMLWriteXMLEndMacro();
}

//------------------------------------------------------------------------------
void vtkMRMLResectionPlanNode::ReadXMLAttributes(const char** atts)
{
  int disabledModify = this->StartModify();
  Superclass::ReadXMLAttributes(atts);

  vtkMRMLReadXMLBeginMacro(atts);
  vtkMRMLReadXMLFloatMacro(safetyMargin_mm, SafetyMargin_mm);
  vtkMRMLReadXMLFloatMacro(riskMargin_mm, RiskMargin_mm);
  vtkMRMLReadXMLIntMacro(orderIndex, OrderIndex);
  vtkMRMLReadXMLEnumMacro(state, State);
  vtkMRMLReadXMLEndMacro();

  this->EndModify(disabledModify);
}

//------------------------------------------------------------------------------
void vtkMRMLResectionPlanNode::CopyContent(vtkMRMLNode* anode, bool deepCopy)
{
  MRMLNodeModifyBlocker blocker(this);
  Superclass::CopyContent(anode, deepCopy);

  vtkMRMLResectionPlanNode* other = vtkMRMLResectionPlanNode::SafeDownCast(anode);
  if (other == nullptr)
  {
    return;
  }
  this->SafetyMargin_mm = other->SafetyMargin_mm;
  this->RiskMargin_mm = other->RiskMargin_mm;
  this->OrderIndex = other->OrderIndex;
  this->State = other->State;
}

//------------------------------------------------------------------------------
void vtkMRMLResectionPlanNode::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);

  vtkMRMLPrintBeginMacro(os, indent);
  vtkMRMLPrintFloatMacro(SafetyMargin_mm);
  vtkMRMLPrintFloatMacro(RiskMargin_mm);
  vtkMRMLPrintIntMacro(OrderIndex);
  vtkMRMLPrintEnumMacro(State);
  vtkMRMLPrintEndMacro();
}

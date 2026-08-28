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
#include "vtkMRMLScalarVolumeNode.h"

// MRML includes
#include <vtkMRMLNodePropertyMacros.h>

// VTK includes
#include <vtkNew.h>
#include <vtkObjectFactory.h>

// STD includes
#include <cstring>
#include <string>

//------------------------------------------------------------------------------
vtkMRMLNodeNewMacro(vtkMRMLResectionPlanNode);

//------------------------------------------------------------------------------
vtkMRMLResectionPlanNode::vtkMRMLResectionPlanNode()
  : SafetyMargin(0.0)
  , RiskMargin(0.0)
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

  // Typed node-reference role to the distance-map scalar volume the
  // resection margins are measured against (ADR-0031).  The distance map
  // is a path-specific input of the plan; per ADR-0014 §"Fourth layer"
  // inputs live on the wrapper, not the surface carrier.  Like the
  // geometry role, no content-modified observation is wired here.
  this->AddNodeReferenceRole(GetDistanceMapReferenceRole(), GetDistanceMapReferenceRole());
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
vtkMRMLScalarVolumeNode* vtkMRMLResectionPlanNode::GetDistanceMapVolumeNode()
{
  return vtkMRMLScalarVolumeNode::SafeDownCast(this->GetNodeReference(GetDistanceMapReferenceRole()));
}

//------------------------------------------------------------------------------
void vtkMRMLResectionPlanNode::SetAndObserveDistanceMapVolumeNode(vtkMRMLScalarVolumeNode* distanceMap)
{
  this->SetAndObserveNodeReferenceID(GetDistanceMapReferenceRole(), distanceMap ? distanceMap->GetID() : nullptr);
}

//------------------------------------------------------------------------------
void vtkMRMLResectionPlanNode::WriteXML(ostream& of, int nIndent)
{
  // Light scalars only -- bulk surface data persists through the
  // storage node per the Markups precedent (vtkMRMLMarkupsNode::WriteXML).
  Superclass::WriteXML(of, nIndent);

  vtkMRMLWriteXMLBeginMacro(of);
  vtkMRMLWriteXMLFloatMacro(safetyMargin, SafetyMargin);
  vtkMRMLWriteXMLFloatMacro(riskMargin, RiskMargin);
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
  vtkMRMLReadXMLFloatMacro(safetyMargin, SafetyMargin);
  vtkMRMLReadXMLFloatMacro(riskMargin, RiskMargin);
  vtkMRMLReadXMLIntMacro(orderIndex, OrderIndex);
  vtkMRMLReadXMLEnumMacro(state, State);
  vtkMRMLReadXMLEndMacro();

  // Legacy scene compatibility: scenes saved before the margin rename
  // carry the unit-suffixed attribute names.  A scene holds either the
  // old or the new names, never both, so order does not matter.
  for (const char** att = atts; att && *att && *(att + 1); att += 2)
  {
    const std::string attName = *att;
    if (attName == "safetyMargin_mm")
    {
      this->SafetyMargin = std::stod(*(att + 1));
    }
    else if (attName == "riskMargin_mm")
    {
      this->RiskMargin = std::stod(*(att + 1));
    }
  }

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
  this->SafetyMargin = other->SafetyMargin;
  this->RiskMargin = other->RiskMargin;
  this->OrderIndex = other->OrderIndex;
  this->State = other->State;
}

//------------------------------------------------------------------------------
void vtkMRMLResectionPlanNode::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);

  vtkMRMLPrintBeginMacro(os, indent);
  vtkMRMLPrintFloatMacro(SafetyMargin);
  vtkMRMLPrintFloatMacro(RiskMargin);
  vtkMRMLPrintIntMacro(OrderIndex);
  vtkMRMLPrintEnumMacro(State);
  vtkMRMLPrintEndMacro();
}

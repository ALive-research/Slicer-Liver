/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Stub translation unit for the v2.0.0 surgeon-custom territories node
  (ADR-0023 §"Class abstraction for territories", Manual-tab path).
  Method bodies deliberately return sentinel values; the follow-up
  implementer commit per ADR-0027 fills in groupings XML round-trip,
  derived-labelmap construction, optional SCT-code tagging, and the
  centerline/endpoint reference lists.

==============================================================================*/

// This module MRML includes
#include "vtkMRMLCustomTerritoriesNode.h"

// VTK includes
#include <vtkObjectFactory.h>

//------------------------------------------------------------------------------
vtkStandardNewMacro(vtkMRMLCustomTerritoriesNode);

//------------------------------------------------------------------------------
vtkMRMLCustomTerritoriesNode::vtkMRMLCustomTerritoriesNode() = default;

//------------------------------------------------------------------------------
vtkMRMLCustomTerritoriesNode::~vtkMRMLCustomTerritoriesNode() = default;

//------------------------------------------------------------------------------
vtkMRMLNode* vtkMRMLCustomTerritoriesNode::CreateNodeInstance()
{
  return vtkMRMLCustomTerritoriesNode::New();
}

//------------------------------------------------------------------------------
void vtkMRMLCustomTerritoriesNode::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);
}

//------------------------------------------------------------------------------
void vtkMRMLCustomTerritoriesNode::ReadXMLAttributes(const char** atts)
{
  // TODO(impl): groupings map + segment names + optional SCT tags
  // round-trip; references via standard MRML reference machinery.
  this->Superclass::ReadXMLAttributes(atts);
}

//------------------------------------------------------------------------------
void vtkMRMLCustomTerritoriesNode::WriteXML(ostream& of, int indent)
{
  // TODO(impl): emit groupings map + segment names + optional SCT tags.
  this->Superclass::WriteXML(of, indent);
}

//------------------------------------------------------------------------------
void vtkMRMLCustomTerritoriesNode::CopyContent(vtkMRMLNode* anode, bool deepCopy)
{
  // TODO(impl): copy Groupings + OptInSCTCodes + LabelMap reference.
  this->Superclass::CopyContent(anode, deepCopy);
}

//------------------------------------------------------------------------------
vtkStringArray* vtkMRMLCustomTerritoriesNode::GetSegments()
{
  // TODO(impl): return the SegmentNames vtkStringArray.
  return nullptr;
}

//------------------------------------------------------------------------------
void vtkMRMLCustomTerritoriesNode::GetSegmentColor(int /*index*/, double rgb[3])
{
  // TODO(impl): derive from the module logic's palette.
  rgb[0] = 0.0;
  rgb[1] = 0.0;
  rgb[2] = 0.0;
}

//------------------------------------------------------------------------------
vtkImageData* vtkMRMLCustomTerritoriesNode::GetLabelMap()
{
  // TODO(impl): return the labelmap held by this node (computed from
  // centerlines + groupings by the module logic).
  return nullptr;
}

//------------------------------------------------------------------------------
vtkMRMLSegmentationNode* vtkMRMLCustomTerritoriesNode::GetSegmentationNode()
{
  // TODO(impl): companion segmentation node reference.
  return nullptr;
}

//------------------------------------------------------------------------------
const char* vtkMRMLCustomTerritoriesNode::GetSCTCode(int index)
{
  auto it = this->OptInSCTCodes.find(index);
  if (it == this->OptInSCTCodes.end())
  {
    return "";
  }
  return it->second.c_str();
}

//------------------------------------------------------------------------------
void vtkMRMLCustomTerritoriesNode::SetGrouping(const std::string& centerlineId,
                                               const std::string& segmentId)
{
  this->Groupings[centerlineId] = segmentId;
  this->Modified();
}

//------------------------------------------------------------------------------
std::string vtkMRMLCustomTerritoriesNode::GetGrouping(const std::string& centerlineId) const
{
  auto it = this->Groupings.find(centerlineId);
  if (it == this->Groupings.end())
  {
    return std::string();
  }
  return it->second;
}

//------------------------------------------------------------------------------
std::size_t vtkMRMLCustomTerritoriesNode::GetNumberOfGroupings() const
{
  return this->Groupings.size();
}

//------------------------------------------------------------------------------
void vtkMRMLCustomTerritoriesNode::ClearGroupings()
{
  this->Groupings.clear();
  this->Modified();
}

//------------------------------------------------------------------------------
void vtkMRMLCustomTerritoriesNode::SetSegmentSCTCode(int index, const std::string& sctCode)
{
  if (sctCode.empty())
  {
    this->OptInSCTCodes.erase(index);
  }
  else
  {
    this->OptInSCTCodes[index] = sctCode;
  }
  this->Modified();
}

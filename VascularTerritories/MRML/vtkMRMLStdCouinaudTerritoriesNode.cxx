/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Stub translation unit for the v2.0.0 standard-Couinaud territories
  node (ADR-0023 §"Class abstraction for territories", Auto-tab path).
  Method bodies returning sentinel values are deliberate -- the
  test-first commit lands the contract and intentionally-failing
  invariants; the follow-up implementer commit per ADR-0027 fills in
  the SCT-code table, segment-name array, colour palette, XML
  serialisation, and the labelmap/segmentation-node references.

==============================================================================*/

// This module MRML includes
#include "vtkMRMLStdCouinaudTerritoriesNode.h"

// VTK includes
#include <vtkObjectFactory.h>

//------------------------------------------------------------------------------
vtkStandardNewMacro(vtkMRMLStdCouinaudTerritoriesNode);

//------------------------------------------------------------------------------
vtkMRMLStdCouinaudTerritoriesNode::vtkMRMLStdCouinaudTerritoriesNode() = default;

//------------------------------------------------------------------------------
vtkMRMLStdCouinaudTerritoriesNode::~vtkMRMLStdCouinaudTerritoriesNode()
{
  this->SetAIBackendIdentifier(nullptr);
  this->SetComputedAt(nullptr);
}

//------------------------------------------------------------------------------
vtkMRMLNode* vtkMRMLStdCouinaudTerritoriesNode::CreateNodeInstance()
{
  return vtkMRMLStdCouinaudTerritoriesNode::New();
}

//------------------------------------------------------------------------------
void vtkMRMLStdCouinaudTerritoriesNode::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);
}

//------------------------------------------------------------------------------
void vtkMRMLStdCouinaudTerritoriesNode::ReadXMLAttributes(const char** atts)
{
  // TODO(impl): wire Subdivision + AIBackendIdentifier + ComputedAt
  // XML attribute parsing via vtkMRMLReadXMLBeginMacro / EndMacro.
  this->Superclass::ReadXMLAttributes(atts);
}

//------------------------------------------------------------------------------
void vtkMRMLStdCouinaudTerritoriesNode::WriteXML(ostream& of, int indent)
{
  // TODO(impl): emit Subdivision + AIBackendIdentifier + ComputedAt.
  this->Superclass::WriteXML(of, indent);
}

//------------------------------------------------------------------------------
void vtkMRMLStdCouinaudTerritoriesNode::CopyContent(vtkMRMLNode* anode, bool deepCopy)
{
  // TODO(impl): copy Subdivision + AIBackendIdentifier + ComputedAt +
  // LabelMap reference.
  this->Superclass::CopyContent(anode, deepCopy);
}

//------------------------------------------------------------------------------
vtkStringArray* vtkMRMLStdCouinaudTerritoriesNode::GetSegments()
{
  // TODO(impl): return the Couinaud segment-name list ordered to match
  // the labelmap (I, II, III, IV-or-IVa, IVb, V, VI, VII, VIII).
  return nullptr;
}

//------------------------------------------------------------------------------
void vtkMRMLStdCouinaudTerritoriesNode::GetSegmentColor(int /*index*/, double rgb[3])
{
  // TODO(impl): map index -> palette entry from
  // Resources/SlicerLiverColorMap.ctbl.
  rgb[0] = 0.0;
  rgb[1] = 0.0;
  rgb[2] = 0.0;
}

//------------------------------------------------------------------------------
vtkImageData* vtkMRMLStdCouinaudTerritoriesNode::GetLabelMap()
{
  // TODO(impl): return the AI-output labelmap held by this node.
  return nullptr;
}

//------------------------------------------------------------------------------
vtkMRMLSegmentationNode* vtkMRMLStdCouinaudTerritoriesNode::GetSegmentationNode()
{
  // TODO(impl): return the companion segmentation node.
  return nullptr;
}

//------------------------------------------------------------------------------
const char* vtkMRMLStdCouinaudTerritoriesNode::GetSCTCode(int /*index*/)
{
  // TODO(impl): index -> SCT code (ADR-0011 §2; the test file
  // vtkMRMLStdCouinaudTerritoriesNodeTest1.cxx pins the full table).
  return "";
}

//------------------------------------------------------------------------------
int vtkMRMLStdCouinaudTerritoriesNode::GetNumberOfSegments()
{
  // TODO(impl): return 8 for I_VIII, 10 for I_VIII_with_IVab.  Stub
  // returns 0 so the invariant test (#9) fails red as required by
  // ADR-0027.
  return 0;
}

/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Implementation of the standard-Couinaud territories node (ADR-0023
  §"Class abstraction for territories", Auto-tab path).  Pins the
  10-code SCT table per ADR-0011 §2, the Subdivision-driven segment
  count, and the XML round-trip for the few IVars the architecture
  doc names.

==============================================================================*/

// This module MRML includes
#include "vtkMRMLStdCouinaudTerritoriesNode.h"

// MRML includes
#include <vtkMRMLNode.h>

// VTK includes
#include <vtkNew.h>
#include <vtkObjectFactory.h>
#include <vtkStringArray.h>

// STD includes
#include <array>
#include <cstring>

namespace
{

// Canonical Couinaud SCT codes per ADR-0011 §2.  The architecture
// doc's Docs/architecture/territories-class-hierarchy.md "SCT
// terminology binding" section is authoritative for the mapping.
constexpr const char* kSCT_I    = "71133005";   // Caudate
constexpr const char* kSCT_II   = "277956007";
constexpr const char* kSCT_III  = "277957003";
constexpr const char* kSCT_IV   = "277958008";
constexpr const char* kSCT_IVa  = "871688003";
constexpr const char* kSCT_IVb  = "871689006";
constexpr const char* kSCT_V    = "277959000";
constexpr const char* kSCT_VI   = "277960005";
constexpr const char* kSCT_VII  = "277961009";
constexpr const char* kSCT_VIII = "277962002";

constexpr std::array<const char*, 8> kCouinaudSCT_8 = {
  kSCT_I, kSCT_II, kSCT_III, kSCT_IV,
  kSCT_V, kSCT_VI, kSCT_VII, kSCT_VIII,
};

constexpr std::array<const char*, 10> kCouinaudSCT_10 = {
  kSCT_I, kSCT_II, kSCT_III,
  kSCT_IVa, kSCT_IVb,
  kSCT_V, kSCT_VI, kSCT_VII, kSCT_VIII,
};

constexpr std::array<const char*, 8> kCouinaudNames_8 = {
  "I", "II", "III", "IV",
  "V", "VI", "VII", "VIII",
};

constexpr std::array<const char*, 10> kCouinaudNames_10 = {
  "I", "II", "III",
  "IVa", "IVb",
  "V", "VI", "VII", "VIII",
};

// Deterministic default palette used when no colour map node is
// bound; Resources/SlicerLiverColorMap.ctbl is the canonical visual
// source for Stage 4 overlay rendering.
constexpr std::array<std::array<double, 3>, 10> kCouinaudPalette = { {
  { 0.7, 0.7, 0.4 }, // I
  { 0.6, 0.2, 0.2 }, // II
  { 0.8, 0.3, 0.3 }, // III
  { 0.2, 0.6, 0.2 }, // IV / IVa
  { 0.2, 0.8, 0.4 }, // IVb
  { 0.2, 0.4, 0.8 }, // V
  { 0.4, 0.5, 0.9 }, // VI
  { 0.8, 0.5, 0.2 }, // VII
  { 0.9, 0.7, 0.3 }, // VIII
  { 0.5, 0.5, 0.5 },
} };

} // namespace

//------------------------------------------------------------------------------
vtkStandardNewMacro(vtkMRMLStdCouinaudTerritoriesNode);

//------------------------------------------------------------------------------
vtkMRMLStdCouinaudTerritoriesNode::vtkMRMLStdCouinaudTerritoriesNode()
{
  this->Segments = vtkSmartPointer<vtkStringArray>::New();
}

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
  os << indent << "Subdivision: " << this->Subdivision << "\n";
  os << indent
     << "AIBackendIdentifier: " << (this->AIBackendIdentifier ? this->AIBackendIdentifier : "(none)") << "\n";
  os << indent
     << "ComputedAt: " << (this->ComputedAt ? this->ComputedAt : "(none)") << "\n";
}

//------------------------------------------------------------------------------
void vtkMRMLStdCouinaudTerritoriesNode::ReadXMLAttributes(const char** atts)
{
  int disabledModify = this->StartModify();
  this->Superclass::ReadXMLAttributes(atts);

  vtkMRMLReadXMLBeginMacro(atts);
  vtkMRMLReadXMLIntMacro(subdivision, Subdivision);
  vtkMRMLReadXMLStringMacro(aiBackendIdentifier, AIBackendIdentifier);
  vtkMRMLReadXMLStringMacro(computedAt, ComputedAt);
  vtkMRMLReadXMLEndMacro();

  this->EndModify(disabledModify);
}

//------------------------------------------------------------------------------
void vtkMRMLStdCouinaudTerritoriesNode::WriteXML(ostream& of, int nIndent)
{
  this->Superclass::WriteXML(of, nIndent);

  vtkMRMLWriteXMLBeginMacro(of);
  vtkMRMLWriteXMLIntMacro(subdivision, Subdivision);
  vtkMRMLWriteXMLStringMacro(aiBackendIdentifier, AIBackendIdentifier);
  vtkMRMLWriteXMLStringMacro(computedAt, ComputedAt);
  vtkMRMLWriteXMLEndMacro();
}

//------------------------------------------------------------------------------
void vtkMRMLStdCouinaudTerritoriesNode::CopyContent(vtkMRMLNode* anode, bool deepCopy)
{
  MRMLNodeModifyBlocker blocker(this);
  this->Superclass::CopyContent(anode, deepCopy);

  auto other = vtkMRMLStdCouinaudTerritoriesNode::SafeDownCast(anode);
  if (!other)
  {
    return;
  }

  vtkMRMLCopyBeginMacro(other);
  vtkMRMLCopyIntMacro(Subdivision);
  vtkMRMLCopyStringMacro(AIBackendIdentifier);
  vtkMRMLCopyStringMacro(ComputedAt);
  vtkMRMLCopyEndMacro();
}

//------------------------------------------------------------------------------
vtkStringArray* vtkMRMLStdCouinaudTerritoriesNode::GetSegments()
{
  // Rebuild on every call so a subdivision change is reflected
  // immediately.  Cheap (≤10 entries) and avoids a stale-cache state
  // bug if a caller forgets to invalidate.
  this->Segments->Initialize();
  if (this->Subdivision == I_VIII_with_IVab)
  {
    for (const char* name : kCouinaudNames_10)
    {
      this->Segments->InsertNextValue(name);
    }
  }
  else
  {
    for (const char* name : kCouinaudNames_8)
    {
      this->Segments->InsertNextValue(name);
    }
  }
  return this->Segments;
}

//------------------------------------------------------------------------------
void vtkMRMLStdCouinaudTerritoriesNode::GetSegmentColor(int index, double rgb[3])
{
  rgb[0] = 0.0;
  rgb[1] = 0.0;
  rgb[2] = 0.0;
  if (index < 0 || index >= static_cast<int>(kCouinaudPalette.size()))
  {
    return;
  }
  rgb[0] = kCouinaudPalette[index][0];
  rgb[1] = kCouinaudPalette[index][1];
  rgb[2] = kCouinaudPalette[index][2];
}

//------------------------------------------------------------------------------
vtkImageData* vtkMRMLStdCouinaudTerritoriesNode::GetLabelMap()
{
  // The Auto path's labelmap is the AI output stored as the node's
  // primary displayable image.  The architecture-doc UML carries
  // ``LabelMap vtkImageData``; until the AI-orchestration logic plugs
  // it in, return nullptr (subclasses-may-return-nullptr is part of
  // the abstract-base contract).
  return nullptr;
}

//------------------------------------------------------------------------------
vtkMRMLSegmentationNode* vtkMRMLStdCouinaudTerritoriesNode::GetSegmentationNode()
{
  // Companion segmentation node is wired by the module Logic when it
  // creates the visualization pipeline.  Returns nullptr until then.
  return nullptr;
}

//------------------------------------------------------------------------------
const char* vtkMRMLStdCouinaudTerritoriesNode::GetSCTCode(int index)
{
  if (this->Subdivision == I_VIII_with_IVab)
  {
    if (index < 0 || index >= static_cast<int>(kCouinaudSCT_10.size()))
    {
      return "";
    }
    return kCouinaudSCT_10[index];
  }
  if (index < 0 || index >= static_cast<int>(kCouinaudSCT_8.size()))
  {
    return "";
  }
  return kCouinaudSCT_8[index];
}

//------------------------------------------------------------------------------
int vtkMRMLStdCouinaudTerritoriesNode::GetNumberOfSegments()
{
  return this->Subdivision == I_VIII_with_IVab ? 10 : 8;
}

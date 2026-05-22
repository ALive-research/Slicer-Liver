/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Implementation of the surgeon-custom territories node (ADR-0023
  §"Class abstraction for territories", Manual-tab path).  Pins the
  Groupings + OptInSCTCodes XML round-trip, the SegmentNames array,
  and the surgeon-opt-in SCT-code tagging machinery.

==============================================================================*/

// This module MRML includes
#include "vtkMRMLCustomTerritoriesNode.h"

// MRML includes
#include <vtkMRMLNode.h>

// VTK includes
#include <vtkObjectFactory.h>
#include <vtkStringArray.h>

// STD includes
#include <cstring>
#include <sstream>
#include <string>

namespace
{

// Compact ``key|value;key|value;…`` XML-attribute encoding for the
// Custom-territories groupings + opt-in SCT codes.  Schema-internal:
// only this class reads it; the .lrp.json schema v3 surfaces the
// same data as JSON (architecture-doc §"Persistence").
constexpr char kPairDelimiter = ';';
constexpr char kFieldDelimiter = '|';

template <typename KeyT>
std::string encodeMap(const std::map<KeyT, std::string>& m)
{
  std::ostringstream out;
  bool first = true;
  for (const auto& kv : m)
  {
    if (!first)
    {
      out << kPairDelimiter;
    }
    first = false;
    out << kv.first << kFieldDelimiter << kv.second;
  }
  return out.str();
}

// Walk the encoded string and call ``onPair(rawKey, value)`` for every
// well-formed entry.  Caller decides how to coerce ``rawKey`` (raw
// std::string vs std::stoi).  Malformed entries are skipped silently
// per MRML's tolerant attribute-parsing convention.
template <typename OnPair>
void walkEncodedMap(const std::string& encoded, OnPair&& onPair)
{
  std::string::size_type cursor = 0;
  while (cursor < encoded.size())
  {
    auto end = encoded.find(kPairDelimiter, cursor);
    if (end == std::string::npos)
    {
      end = encoded.size();
    }
    auto sep = encoded.find(kFieldDelimiter, cursor);
    if (sep != std::string::npos && sep < end)
    {
      onPair(encoded.substr(cursor, sep - cursor), encoded.substr(sep + 1, end - sep - 1));
    }
    cursor = end + 1;
  }
}

} // namespace

//------------------------------------------------------------------------------
vtkStandardNewMacro(vtkMRMLCustomTerritoriesNode);

//------------------------------------------------------------------------------
vtkMRMLCustomTerritoriesNode::vtkMRMLCustomTerritoriesNode()
{
  this->SegmentNames = vtkSmartPointer<vtkStringArray>::New();
}

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
  os << indent << "Groupings: " << this->Groupings.size() << " entries\n";
  os << indent << "OptInSCTCodes: " << this->OptInSCTCodes.size() << " entries\n";
}

//------------------------------------------------------------------------------
void vtkMRMLCustomTerritoriesNode::ReadXMLAttributes(const char** atts)
{
  int disabledModify = this->StartModify();
  this->Superclass::ReadXMLAttributes(atts);

  const char* attName = nullptr;
  const char* attValue = nullptr;
  while (*atts != nullptr)
  {
    attName = *(atts++);
    attValue = *(atts++);
    if (!std::strcmp(attName, "groupings"))
    {
      this->Groupings.clear();
      walkEncodedMap(attValue, [this](std::string key, std::string value) { this->Groupings[std::move(key)] = std::move(value); });
    }
    else if (!std::strcmp(attName, "optInSCTCodes"))
    {
      this->OptInSCTCodes.clear();
      walkEncodedMap(attValue,
                     [this](const std::string& key, std::string value)
                     {
                       try
                       {
                         this->OptInSCTCodes[std::stoi(key)] = std::move(value);
                       }
                       catch (const std::exception&)
                       {
                         // Malformed numeric key — skip silently.
                       }
                     });
    }
    else if (!std::strcmp(attName, "segmentNames"))
    {
      this->SegmentNames->Initialize();
      std::string encoded(attValue);
      std::string::size_type cursor = 0;
      while (cursor < encoded.size())
      {
        auto end = encoded.find(kPairDelimiter, cursor);
        if (end == std::string::npos)
        {
          end = encoded.size();
        }
        this->SegmentNames->InsertNextValue(encoded.substr(cursor, end - cursor));
        cursor = end + 1;
      }
    }
  }

  this->EndModify(disabledModify);
}

//------------------------------------------------------------------------------
void vtkMRMLCustomTerritoriesNode::WriteXML(ostream& of, int nIndent)
{
  this->Superclass::WriteXML(of, nIndent);

  // Compact key|value;key|value;… encoding for Groupings + opt-in SCT
  // codes.  Architecture-doc §"Persistence" — schema-internal form
  // for the MRML XML; .lrp.json schema v3 surfaces the same data as
  // JSON.
  if (!this->Groupings.empty())
  {
    of << " groupings=\"" << this->XMLAttributeEncodeString(encodeMap(this->Groupings).c_str()) << "\"";
  }
  if (!this->OptInSCTCodes.empty())
  {
    of << " optInSCTCodes=\"" << this->XMLAttributeEncodeString(encodeMap(this->OptInSCTCodes).c_str()) << "\"";
  }
  if (this->SegmentNames && this->SegmentNames->GetNumberOfValues() > 0)
  {
    std::ostringstream names;
    for (vtkIdType i = 0; i < this->SegmentNames->GetNumberOfValues(); ++i)
    {
      if (i > 0)
      {
        names << kPairDelimiter;
      }
      names << this->SegmentNames->GetValue(i);
    }
    of << " segmentNames=\"" << this->XMLAttributeEncodeString(names.str().c_str()) << "\"";
  }
}

//------------------------------------------------------------------------------
void vtkMRMLCustomTerritoriesNode::CopyContent(vtkMRMLNode* anode, bool deepCopy)
{
  MRMLNodeModifyBlocker blocker(this);
  this->Superclass::CopyContent(anode, deepCopy);

  auto other = vtkMRMLCustomTerritoriesNode::SafeDownCast(anode);
  if (!other)
  {
    return;
  }

  this->Groupings = other->Groupings;
  this->OptInSCTCodes = other->OptInSCTCodes;
  if (other->SegmentNames)
  {
    this->SegmentNames->DeepCopy(other->SegmentNames);
  }
  // ``std::map`` / ``std::set`` assignment does not tickle VTK's
  // MTime; the MRMLNodeModifyBlocker therefore would not fire
  // Modified on dtor.  Force a notification so observers of this
  // node see the CopyContent.
  this->Modified();
}

//------------------------------------------------------------------------------
vtkStringArray* vtkMRMLCustomTerritoriesNode::GetSegments()
{
  // Returns the surgeon-named segment-label list.  Always non-null
  // per the abstract-base contract; empty if the surgeon has not yet
  // named any segments.
  return this->SegmentNames;
}

//------------------------------------------------------------------------------
void vtkMRMLCustomTerritoriesNode::GetSegmentColor(int /*index*/, double rgb[3])
{
  // Custom segments do not carry a built-in colour palette — the
  // surgeon picks colours via the Stage 3 Manual tab's per-segment
  // colour swatch.  Default to opaque black; the module Logic
  // overwrites this from the chosen colour map.
  rgb[0] = 0.0;
  rgb[1] = 0.0;
  rgb[2] = 0.0;
}

//------------------------------------------------------------------------------
vtkImageData* vtkMRMLCustomTerritoriesNode::GetLabelMap()
{
  // The Manual path's labelmap is computed by the module Logic from
  // centerlines + groupings.  Returns nullptr until the Logic plugs
  // it in (subclasses-may-return-nullptr per the abstract-base
  // contract).
  return nullptr;
}

//------------------------------------------------------------------------------
vtkMRMLSegmentationNode* vtkMRMLCustomTerritoriesNode::GetSegmentationNode()
{
  // Companion segmentation node is wired by the module Logic when it
  // creates the visualization pipeline.  Returns nullptr until then.
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
void vtkMRMLCustomTerritoriesNode::SetGrouping(const std::string& centerlineId, const std::string& segmentId)
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

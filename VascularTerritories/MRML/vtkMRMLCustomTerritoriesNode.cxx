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
#include "vtkMRMLCustomTerritoriesStorageNode.h"

// MRML includes
#include <vtkMRMLNode.h>

// VTK includes
#include <vtkObjectFactory.h>
#include <vtkStringArray.h>

// STD includes
#include <cstring>
#include <iomanip>
#include <set>
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

// Compact encoding for the per-territory annotation points.  Territory
// blocks are separated by ``kPairDelimiter`` (``;``); within a block the
// territory id and its flat coordinate run are separated by
// ``kFieldDelimiter`` (``|``), and the coordinates themselves by
// ``kCoordDelimiter`` (``,``).  Territory ids are surgeon-named and may
// not contain the delimiter characters; this schema-internal form is only
// read by this class (the .vta.json storage surfaces the same data as
// JSON).
constexpr char kCoordDelimiter = ',';

std::string encodeAnnotationPoints(const std::map<std::string, std::vector<std::array<double, 3>>>& points)
{
  std::ostringstream out;
  out << std::setprecision(17);
  bool firstTerritory = true;
  for (const auto& kv : points)
  {
    if (kv.second.empty())
    {
      continue;
    }
    if (!firstTerritory)
    {
      out << kPairDelimiter;
    }
    firstTerritory = false;
    out << kv.first << kFieldDelimiter;
    bool firstCoord = true;
    for (const auto& p : kv.second)
    {
      for (int c = 0; c < 3; ++c)
      {
        if (!firstCoord)
        {
          out << kCoordDelimiter;
        }
        firstCoord = false;
        out << p[c];
      }
    }
  }
  return out.str();
}

void decodeAnnotationPoints(const std::string& encoded, std::map<std::string, std::vector<std::array<double, 3>>>& points)
{
  points.clear();
  walkEncodedMap(encoded,
                 [&points](const std::string& territoryId, const std::string& coords)
                 {
                   std::vector<double> flat;
                   std::istringstream stream(coords);
                   std::string token;
                   while (std::getline(stream, token, kCoordDelimiter))
                   {
                     if (token.empty())
                     {
                       continue;
                     }
                     try
                     {
                       flat.push_back(std::stod(token));
                     }
                     catch (const std::exception&)
                     {
                       // Malformed coordinate — skip silently.
                     }
                   }
                   auto& list = points[territoryId];
                   for (std::size_t i = 0; i + 3 <= flat.size(); i += 3)
                   {
                     list.push_back({ flat[i], flat[i + 1], flat[i + 2] });
                   }
                 });
}

// Compact encoding for the per-territory colour map: ``territoryId|r,g,b``
// blocks separated by ``kPairDelimiter``.  Schema-internal (the .vta.json
// storage surfaces the same data as JSON).
std::string encodeColors(const std::map<std::string, std::array<double, 3>>& colors)
{
  std::ostringstream out;
  out << std::setprecision(17);
  bool first = true;
  for (const auto& kv : colors)
  {
    if (!first)
    {
      out << kPairDelimiter;
    }
    first = false;
    out << kv.first << kFieldDelimiter << kv.second[0] << kCoordDelimiter << kv.second[1] << kCoordDelimiter << kv.second[2];
  }
  return out.str();
}

void decodeColors(const std::string& encoded, std::map<std::string, std::array<double, 3>>& colors)
{
  colors.clear();
  walkEncodedMap(encoded,
                 [&colors](const std::string& territoryId, const std::string& rgb)
                 {
                   std::array<double, 3> value = { 1.0, 1.0, 1.0 };
                   std::istringstream stream(rgb);
                   std::string token;
                   int c = 0;
                   while (c < 3 && std::getline(stream, token, kCoordDelimiter))
                   {
                     try
                     {
                       value[c] = std::stod(token);
                     }
                     catch (const std::exception&)
                     {
                       // Malformed channel — keep the default.
                     }
                     ++c;
                   }
                   colors[territoryId] = value;
                 });
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
  os << indent << "AnnotationPoints: " << this->AnnotationPoints.size() << " territories\n";
  for (const auto& kv : this->AnnotationPoints)
  {
    os << indent.GetNextIndent() << kv.first << ": " << kv.second.size() << " points\n";
  }
  os << indent << "TerritoryColors: " << this->TerritoryColors.size() << " entries\n";
  os << indent << "TerritoryLabels: " << this->TerritoryLabels.size() << " entries\n";
  os << indent << "TerritoryVisibilities: " << this->TerritoryVisibilities.size() << " entries\n";
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
    else if (!std::strcmp(attName, "annotationPoints"))
    {
      decodeAnnotationPoints(attValue, this->AnnotationPoints);
    }
    else if (!std::strcmp(attName, "territoryColors"))
    {
      decodeColors(attValue, this->TerritoryColors);
    }
    else if (!std::strcmp(attName, "territoryLabels"))
    {
      this->TerritoryLabels.clear();
      walkEncodedMap(attValue, [this](std::string key, std::string value) { this->TerritoryLabels[std::move(key)] = std::move(value); });
    }
    else if (!std::strcmp(attName, "territoryVisibilities"))
    {
      this->TerritoryVisibilities.clear();
      walkEncodedMap(attValue, [this](const std::string& key, const std::string& value) { this->TerritoryVisibilities[key] = (value != "0"); });
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
  if (!this->AnnotationPoints.empty())
  {
    of << " annotationPoints=\"" << this->XMLAttributeEncodeString(encodeAnnotationPoints(this->AnnotationPoints).c_str()) << "\"";
  }
  if (!this->TerritoryColors.empty())
  {
    of << " territoryColors=\"" << this->XMLAttributeEncodeString(encodeColors(this->TerritoryColors).c_str()) << "\"";
  }
  if (!this->TerritoryLabels.empty())
  {
    of << " territoryLabels=\"" << this->XMLAttributeEncodeString(encodeMap(this->TerritoryLabels).c_str()) << "\"";
  }
  if (!this->TerritoryVisibilities.empty())
  {
    std::map<std::string, std::string> encodedVis;
    for (const auto& kv : this->TerritoryVisibilities)
    {
      encodedVis[kv.first] = kv.second ? "1" : "0";
    }
    of << " territoryVisibilities=\"" << this->XMLAttributeEncodeString(encodeMap(encodedVis).c_str()) << "\"";
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
  this->AnnotationPoints = other->AnnotationPoints;
  this->TerritoryColors = other->TerritoryColors;
  this->TerritoryLabels = other->TerritoryLabels;
  this->TerritoryVisibilities = other->TerritoryVisibilities;
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

//------------------------------------------------------------------------------
int vtkMRMLCustomTerritoriesNode::AddAnnotationPoint(const std::string& territoryId, double x, double y, double z)
{
  std::vector<std::array<double, 3>>& list = this->AnnotationPoints[territoryId];
  list.push_back({ x, y, z });
  const int index = static_cast<int>(list.size()) - 1;
  this->Modified();
  return index;
}

//------------------------------------------------------------------------------
int vtkMRMLCustomTerritoriesNode::GetNumberOfAnnotationPoints(const std::string& territoryId)
{
  auto it = this->AnnotationPoints.find(territoryId);
  if (it == this->AnnotationPoints.end())
  {
    return 0;
  }
  return static_cast<int>(it->second.size());
}

//------------------------------------------------------------------------------
const double* vtkMRMLCustomTerritoriesNode::GetNthAnnotationPoint(const std::string& territoryId, int i)
{
  this->AnnotationPointScratch[0] = 0.0;
  this->AnnotationPointScratch[1] = 0.0;
  this->AnnotationPointScratch[2] = 0.0;
  auto it = this->AnnotationPoints.find(territoryId);
  if (it != this->AnnotationPoints.end() && i >= 0 && i < static_cast<int>(it->second.size()))
  {
    const std::array<double, 3>& p = it->second[static_cast<std::size_t>(i)];
    this->AnnotationPointScratch[0] = p[0];
    this->AnnotationPointScratch[1] = p[1];
    this->AnnotationPointScratch[2] = p[2];
  }
  return this->AnnotationPointScratch;
}

//------------------------------------------------------------------------------
void vtkMRMLCustomTerritoriesNode::SetNthAnnotationPoint(const std::string& territoryId, int i, double x, double y, double z)
{
  auto it = this->AnnotationPoints.find(territoryId);
  if (it == this->AnnotationPoints.end() || i < 0 || i >= static_cast<int>(it->second.size()))
  {
    return;
  }
  it->second[static_cast<std::size_t>(i)] = { x, y, z };
  this->Modified();
}

//------------------------------------------------------------------------------
bool vtkMRMLCustomTerritoriesNode::RemoveNthAnnotationPoint(const std::string& territoryId, int i)
{
  auto it = this->AnnotationPoints.find(territoryId);
  if (it == this->AnnotationPoints.end() || i < 0 || i >= static_cast<int>(it->second.size()))
  {
    return false;
  }
  it->second.erase(it->second.begin() + i);
  this->Modified();
  return true;
}

//------------------------------------------------------------------------------
void vtkMRMLCustomTerritoriesNode::ClearAnnotationPoints(const std::string& territoryId)
{
  auto it = this->AnnotationPoints.find(territoryId);
  if (it == this->AnnotationPoints.end() || it->second.empty())
  {
    return;
  }
  it->second.clear();
  this->Modified();
}

//------------------------------------------------------------------------------
std::vector<std::string> vtkMRMLCustomTerritoriesNode::GetAnnotationTerritoryIds() const
{
  std::vector<std::string> ids;
  for (const auto& kv : this->AnnotationPoints)
  {
    if (!kv.second.empty())
    {
      ids.push_back(kv.first);
    }
  }
  return ids;
}

//------------------------------------------------------------------------------
void vtkMRMLCustomTerritoriesNode::SetTerritoryColor(const std::string& territoryId, double r, double g, double b)
{
  this->TerritoryColors[territoryId] = { r, g, b };
  this->Modified();
}

//------------------------------------------------------------------------------
const double* vtkMRMLCustomTerritoriesNode::GetTerritoryColor(const std::string& territoryId)
{
  // Default for an unset territory: opaque white (the module's neutral
  // swatch until the surgeon picks a colour).
  this->TerritoryColorScratch[0] = 1.0;
  this->TerritoryColorScratch[1] = 1.0;
  this->TerritoryColorScratch[2] = 1.0;
  auto it = this->TerritoryColors.find(territoryId);
  if (it != this->TerritoryColors.end())
  {
    this->TerritoryColorScratch[0] = it->second[0];
    this->TerritoryColorScratch[1] = it->second[1];
    this->TerritoryColorScratch[2] = it->second[2];
  }
  return this->TerritoryColorScratch;
}

//------------------------------------------------------------------------------
void vtkMRMLCustomTerritoriesNode::SetTerritoryLabel(const std::string& territoryId, const std::string& label)
{
  this->TerritoryLabels[territoryId] = label;
  this->Modified();
}

//------------------------------------------------------------------------------
std::string vtkMRMLCustomTerritoriesNode::GetTerritoryLabel(const std::string& territoryId) const
{
  auto it = this->TerritoryLabels.find(territoryId);
  if (it == this->TerritoryLabels.end())
  {
    return std::string();
  }
  return it->second;
}

//------------------------------------------------------------------------------
void vtkMRMLCustomTerritoriesNode::SetTerritoryVisibility(const std::string& territoryId, bool visible)
{
  this->TerritoryVisibilities[territoryId] = visible;
  this->Modified();
}

//------------------------------------------------------------------------------
bool vtkMRMLCustomTerritoriesNode::GetTerritoryVisibility(const std::string& territoryId) const
{
  auto it = this->TerritoryVisibilities.find(territoryId);
  if (it == this->TerritoryVisibilities.end())
  {
    // An unset territory defaults to visible.
    return true;
  }
  return it->second;
}

//------------------------------------------------------------------------------
std::vector<std::string> vtkMRMLCustomTerritoriesNode::GetDisplayTerritoryIds() const
{
  // Union of the three display maps' keys, deduplicated + deterministically
  // ordered (std::set) so the storage node enumerates the slots stably.
  std::set<std::string> ids;
  for (const auto& kv : this->TerritoryColors)
  {
    ids.insert(kv.first);
  }
  for (const auto& kv : this->TerritoryLabels)
  {
    ids.insert(kv.first);
  }
  for (const auto& kv : this->TerritoryVisibilities)
  {
    ids.insert(kv.first);
  }
  return std::vector<std::string>(ids.begin(), ids.end());
}

//------------------------------------------------------------------------------
vtkMRMLStorageNode* vtkMRMLCustomTerritoriesNode::CreateDefaultStorageNode()
{
  return vtkMRMLCustomTerritoriesStorageNode::New();
}

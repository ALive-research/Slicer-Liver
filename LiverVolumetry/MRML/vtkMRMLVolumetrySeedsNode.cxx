/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Implementation of vtkMRMLVolumetrySeedsNode — the flat, ordered
  region-growing seed carrier for the ADR-0038-amendment seeds-off-markups
  migration (volumetry-seeds-layerdm-plan.md §3a).  See the class docstring
  in the header for the field roster.

==============================================================================*/

// This module MRML includes
#include "vtkMRMLVolumetrySeedsNode.h"
#include "vtkMRMLVolumetrySeedsStorageNode.h"

// VTK includes
#include <vtkObjectFactory.h>

// STD includes
#include <set>

//------------------------------------------------------------------------------
vtkMRMLNodeNewMacro(vtkMRMLVolumetrySeedsNode);

//------------------------------------------------------------------------------
vtkMRMLVolumetrySeedsNode::vtkMRMLVolumetrySeedsNode() = default;

//------------------------------------------------------------------------------
vtkMRMLVolumetrySeedsNode::~vtkMRMLVolumetrySeedsNode() = default;

//------------------------------------------------------------------------------
void vtkMRMLVolumetrySeedsNode::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);
  os << indent << "Seeds: " << this->Seeds.size() << " points\n";
}

//------------------------------------------------------------------------------
void vtkMRMLVolumetrySeedsNode::WriteXML(ostream& of, int nIndent)
{
  // The ordered seeds + labels + colours round-trip through the
  // vtkMRMLVolumetrySeedsStorageNode ``.vsd.json`` document (ADR-0014
  // §"Fourth layer"), not the scene XML; only the base storable
  // attributes persist here.
  Superclass::WriteXML(of, nIndent);
}

//------------------------------------------------------------------------------
void vtkMRMLVolumetrySeedsNode::ReadXMLAttributes(const char** atts)
{
  int disabledModify = this->StartModify();
  Superclass::ReadXMLAttributes(atts);
  this->EndModify(disabledModify);
}

//------------------------------------------------------------------------------
void vtkMRMLVolumetrySeedsNode::CopyContent(vtkMRMLNode* anode, bool deepCopy /*=true*/)
{
  MRMLNodeModifyBlocker blocker(this);
  Superclass::CopyContent(anode, deepCopy);

  vtkMRMLVolumetrySeedsNode* other = vtkMRMLVolumetrySeedsNode::SafeDownCast(anode);
  if (other == nullptr)
  {
    return;
  }
  this->Seeds = other->Seeds;
  this->SeedLabels = other->SeedLabels;
  this->SeedColors = other->SeedColors;
  this->SeedBindings = other->SeedBindings;
  this->SeedVolumes = other->SeedVolumes;
  this->VolumeColors = other->VolumeColors;
  this->VolumeLabels = other->VolumeLabels;
  this->Modified();
}

//------------------------------------------------------------------------------
bool vtkMRMLVolumetrySeedsNode::IsValidIndex(int i) const
{
  return i >= 0 && i < static_cast<int>(this->Seeds.size());
}

//------------------------------------------------------------------------------
int vtkMRMLVolumetrySeedsNode::AddSeed(double x, double y, double z)
{
  this->Seeds.push_back({ x, y, z });
  this->SeedLabels.emplace_back();
  // Module default swatch: opaque white until the caller picks a colour.
  this->SeedColors.push_back({ 1.0, 1.0, 1.0 });
  // Unbound until the placement path resolves a touched candidate.
  this->SeedBindings.emplace_back();
  // Ungrouped until the active-volume placement path assigns a volume.
  this->SeedVolumes.emplace_back();
  const int index = static_cast<int>(this->Seeds.size()) - 1;
  this->Modified();
  return index;
}

//------------------------------------------------------------------------------
int vtkMRMLVolumetrySeedsNode::GetNumberOfSeeds()
{
  return static_cast<int>(this->Seeds.size());
}

//------------------------------------------------------------------------------
const double* vtkMRMLVolumetrySeedsNode::GetNthSeed(int i)
{
  this->SeedScratch[0] = 0.0;
  this->SeedScratch[1] = 0.0;
  this->SeedScratch[2] = 0.0;
  if (this->IsValidIndex(i))
  {
    const std::array<double, 3>& p = this->Seeds[static_cast<std::size_t>(i)];
    this->SeedScratch[0] = p[0];
    this->SeedScratch[1] = p[1];
    this->SeedScratch[2] = p[2];
  }
  return this->SeedScratch;
}

//------------------------------------------------------------------------------
void vtkMRMLVolumetrySeedsNode::SetNthSeed(int i, double x, double y, double z)
{
  if (!this->IsValidIndex(i))
  {
    return;
  }
  this->Seeds[static_cast<std::size_t>(i)] = { x, y, z };
  this->Modified();
}

//------------------------------------------------------------------------------
bool vtkMRMLVolumetrySeedsNode::RemoveNthSeed(int i)
{
  if (!this->IsValidIndex(i))
  {
    return false;
  }
  const std::size_t idx = static_cast<std::size_t>(i);
  // The three parallel vectors shift in lockstep so a seed's label + colour
  // stay bound to its coordinate.
  this->Seeds.erase(this->Seeds.begin() + idx);
  this->SeedLabels.erase(this->SeedLabels.begin() + idx);
  this->SeedColors.erase(this->SeedColors.begin() + idx);
  this->SeedBindings.erase(this->SeedBindings.begin() + idx);
  this->SeedVolumes.erase(this->SeedVolumes.begin() + idx);
  this->Modified();
  return true;
}

//------------------------------------------------------------------------------
void vtkMRMLVolumetrySeedsNode::SetNthSeedLabel(int i, const std::string& label)
{
  if (!this->IsValidIndex(i))
  {
    return;
  }
  this->SeedLabels[static_cast<std::size_t>(i)] = label;
  this->Modified();
}

//------------------------------------------------------------------------------
std::string vtkMRMLVolumetrySeedsNode::GetNthSeedLabel(int i)
{
  if (!this->IsValidIndex(i))
  {
    return std::string();
  }
  return this->SeedLabels[static_cast<std::size_t>(i)];
}

//------------------------------------------------------------------------------
void vtkMRMLVolumetrySeedsNode::SetNthSeedColor(int i, double r, double g, double b)
{
  if (!this->IsValidIndex(i))
  {
    return;
  }
  this->SeedColors[static_cast<std::size_t>(i)] = { r, g, b };
  this->Modified();
}

//------------------------------------------------------------------------------
const double* vtkMRMLVolumetrySeedsNode::GetNthSeedColor(int i)
{
  this->SeedColorScratch[0] = 1.0;
  this->SeedColorScratch[1] = 1.0;
  this->SeedColorScratch[2] = 1.0;
  if (this->IsValidIndex(i))
  {
    const std::array<double, 3>& c = this->SeedColors[static_cast<std::size_t>(i)];
    this->SeedColorScratch[0] = c[0];
    this->SeedColorScratch[1] = c[1];
    this->SeedColorScratch[2] = c[2];
  }
  return this->SeedColorScratch;
}

//------------------------------------------------------------------------------
void vtkMRMLVolumetrySeedsNode::SetNthSeedBinding(int i, const std::string& segmentationNodeID, const std::string& segmentID)
{
  if (!this->IsValidIndex(i))
  {
    return;
  }
  this->SeedBindings[static_cast<std::size_t>(i)] = { segmentationNodeID, segmentID };
  this->Modified();
}

//------------------------------------------------------------------------------
std::string vtkMRMLVolumetrySeedsNode::GetNthSeedBindingSegmentationNodeID(int i)
{
  if (!this->IsValidIndex(i))
  {
    return std::string();
  }
  return this->SeedBindings[static_cast<std::size_t>(i)].first;
}

//------------------------------------------------------------------------------
std::string vtkMRMLVolumetrySeedsNode::GetNthSeedBindingSegmentID(int i)
{
  if (!this->IsValidIndex(i))
  {
    return std::string();
  }
  return this->SeedBindings[static_cast<std::size_t>(i)].second;
}

//------------------------------------------------------------------------------
int vtkMRMLVolumetrySeedsNode::AddSeedToVolume(const std::string& volumeId, double x, double y, double z)
{
  const int index = this->AddSeed(x, y, z);
  // ``AddSeed`` fired Modified already; assign the volume WITHOUT a second
  // event so the placement path reads as ONE atomic add.
  if (this->IsValidIndex(index))
  {
    this->SeedVolumes[static_cast<std::size_t>(index)] = volumeId;
  }
  return index;
}

//------------------------------------------------------------------------------
void vtkMRMLVolumetrySeedsNode::SetNthSeedVolume(int i, const std::string& volumeId)
{
  if (!this->IsValidIndex(i))
  {
    return;
  }
  this->SeedVolumes[static_cast<std::size_t>(i)] = volumeId;
  this->Modified();
}

//------------------------------------------------------------------------------
std::string vtkMRMLVolumetrySeedsNode::GetNthSeedVolume(int i)
{
  if (!this->IsValidIndex(i))
  {
    return std::string();
  }
  return this->SeedVolumes[static_cast<std::size_t>(i)];
}

//------------------------------------------------------------------------------
void vtkMRMLVolumetrySeedsNode::AddVolume(const std::string& volumeId)
{
  if (volumeId.empty())
  {
    return;
  }
  // A display-slot entry makes the volume enumerable before any seed lands.
  // Register the label slot (empty label) if the volume is entirely new so the
  // register is idempotent and observable.
  if (this->VolumeLabels.find(volumeId) == this->VolumeLabels.end() && this->VolumeColors.find(volumeId) == this->VolumeColors.end())
  {
    this->VolumeLabels[volumeId] = std::string();
    this->Modified();
  }
}

//------------------------------------------------------------------------------
std::vector<std::string> vtkMRMLVolumetrySeedsNode::GetVolumeIds()
{
  // Union of the volumes that carry a seed and those that carry a display slot,
  // deduplicated + deterministically ordered (std::set) so the table + storage
  // enumerate the volumes stably.
  std::set<std::string> ids;
  for (const auto& v : this->SeedVolumes)
  {
    if (!v.empty())
    {
      ids.insert(v);
    }
  }
  for (const auto& kv : this->VolumeColors)
  {
    ids.insert(kv.first);
  }
  for (const auto& kv : this->VolumeLabels)
  {
    ids.insert(kv.first);
  }
  return std::vector<std::string>(ids.begin(), ids.end());
}

//------------------------------------------------------------------------------
bool vtkMRMLVolumetrySeedsNode::RemoveVolume(const std::string& volumeId)
{
  if (volumeId.empty())
  {
    return false;
  }
  bool removed = false;
  // Drop every seed assigned to the volume, tail-first so the parallel vectors
  // shift in lockstep (the same erase order ``RemoveNthSeed`` uses).
  for (int i = static_cast<int>(this->Seeds.size()) - 1; i >= 0; --i)
  {
    if (this->SeedVolumes[static_cast<std::size_t>(i)] == volumeId)
    {
      this->Seeds.erase(this->Seeds.begin() + i);
      this->SeedLabels.erase(this->SeedLabels.begin() + i);
      this->SeedColors.erase(this->SeedColors.begin() + i);
      this->SeedBindings.erase(this->SeedBindings.begin() + i);
      this->SeedVolumes.erase(this->SeedVolumes.begin() + i);
      removed = true;
    }
  }
  removed |= (this->VolumeColors.erase(volumeId) > 0);
  removed |= (this->VolumeLabels.erase(volumeId) > 0);
  if (removed)
  {
    this->Modified();
  }
  return removed;
}

//------------------------------------------------------------------------------
void vtkMRMLVolumetrySeedsNode::SetVolumeColor(const std::string& volumeId, double r, double g, double b)
{
  this->VolumeColors[volumeId] = { r, g, b };
  this->Modified();
}

//------------------------------------------------------------------------------
const double* vtkMRMLVolumetrySeedsNode::GetVolumeColor(const std::string& volumeId)
{
  // Default for an unset volume: opaque white (the module's neutral swatch).
  this->VolumeColorScratch[0] = 1.0;
  this->VolumeColorScratch[1] = 1.0;
  this->VolumeColorScratch[2] = 1.0;
  auto it = this->VolumeColors.find(volumeId);
  if (it != this->VolumeColors.end())
  {
    this->VolumeColorScratch[0] = it->second[0];
    this->VolumeColorScratch[1] = it->second[1];
    this->VolumeColorScratch[2] = it->second[2];
  }
  return this->VolumeColorScratch;
}

//------------------------------------------------------------------------------
void vtkMRMLVolumetrySeedsNode::SetVolumeLabel(const std::string& volumeId, const std::string& label)
{
  this->VolumeLabels[volumeId] = label;
  this->Modified();
}

//------------------------------------------------------------------------------
std::string vtkMRMLVolumetrySeedsNode::GetVolumeLabel(const std::string& volumeId)
{
  auto it = this->VolumeLabels.find(volumeId);
  if (it == this->VolumeLabels.end())
  {
    return std::string();
  }
  return it->second;
}

//------------------------------------------------------------------------------
vtkMRMLStorageNode* vtkMRMLVolumetrySeedsNode::CreateDefaultStorageNode()
{
  return vtkMRMLVolumetrySeedsStorageNode::New();
}

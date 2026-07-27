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
vtkMRMLStorageNode* vtkMRMLVolumetrySeedsNode::CreateDefaultStorageNode()
{
  return vtkMRMLVolumetrySeedsStorageNode::New();
}

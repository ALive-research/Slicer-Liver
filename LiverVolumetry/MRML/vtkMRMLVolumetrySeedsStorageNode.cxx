/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Implementation of vtkMRMLVolumetrySeedsStorageNode — the ``.vsd.json``
  storage layer for the volumetry seed carrier (ADR-0038-amendment §3a).
  Mirrors vtkMRMLCustomTerritoriesStorageNode (ADR-0014 §"Fourth layer").
  See the class docstring in the header for the schema.

==============================================================================*/

// This module MRML includes
#include "vtkMRMLVolumetrySeedsStorageNode.h"
#include "vtkMRMLVolumetrySeedsNode.h"

// MRML includes
#include <vtkMRMLJsonElement.h>
#include <vtkMRMLMessageCollection.h>

// VTK includes
#include <vtkNew.h>
#include <vtkObjectFactory.h>
#include <vtkSmartPointer.h>
#include <vtkStringArray.h>

// STD includes
#include <algorithm>
#include <cctype>
#include <string>

//------------------------------------------------------------------------------
vtkMRMLNodeNewMacro(vtkMRMLVolumetrySeedsStorageNode);

//------------------------------------------------------------------------------
vtkMRMLVolumetrySeedsStorageNode::vtkMRMLVolumetrySeedsStorageNode()
{
  this->DefaultWriteFileExtension = "vsd.json";
}

//------------------------------------------------------------------------------
vtkMRMLVolumetrySeedsStorageNode::~vtkMRMLVolumetrySeedsStorageNode() = default;

//------------------------------------------------------------------------------
void vtkMRMLVolumetrySeedsStorageNode::PrintSelf(ostream& os, vtkIndent indent)
{
  Superclass::PrintSelf(os, indent);
  os << indent << "SchemaVersion: " << SchemaVersion << "\n";
}

//------------------------------------------------------------------------------
bool vtkMRMLVolumetrySeedsStorageNode::CanReadInReferenceNode(vtkMRMLNode* refNode)
{
  return refNode != nullptr && refNode->IsA("vtkMRMLVolumetrySeedsNode");
}

//------------------------------------------------------------------------------
bool vtkMRMLVolumetrySeedsStorageNode::CanWriteFromReferenceNode(vtkMRMLNode* refNode)
{
  return refNode != nullptr && refNode->IsA("vtkMRMLVolumetrySeedsNode");
}

//------------------------------------------------------------------------------
void vtkMRMLVolumetrySeedsStorageNode::InitializeSupportedReadFileTypes()
{
  this->SupportedReadFileTypes->InsertNextValue("Volumetry seeds (.vsd.json)");
}

//------------------------------------------------------------------------------
void vtkMRMLVolumetrySeedsStorageNode::InitializeSupportedWriteFileTypes()
{
  this->SupportedWriteFileTypes->InsertNextValue("Volumetry seeds (.vsd.json)");
}

//------------------------------------------------------------------------------
namespace
{
std::string toLower(std::string s)
{
  std::transform(s.begin(), s.end(), s.begin(), [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
  return s;
}

bool endsWithLower(const std::string& path, const std::string& suffix)
{
  if (path.size() < suffix.size())
  {
    return false;
  }
  return toLower(path.substr(path.size() - suffix.size())) == suffix;
}
} // namespace

//------------------------------------------------------------------------------
int vtkMRMLVolumetrySeedsStorageNode::ReadDataInternal(vtkMRMLNode* refNode)
{
  if (refNode == nullptr)
  {
    vtkErrorToMessageCollectionMacro(this->GetUserMessages(), "vtkMRMLVolumetrySeedsStorageNode::ReadDataInternal", "Reading seed carrier failed: null reference node");
    return 0;
  }
  vtkMRMLVolumetrySeedsNode* carrier = vtkMRMLVolumetrySeedsNode::SafeDownCast(refNode);
  if (carrier == nullptr)
  {
    vtkErrorToMessageCollectionMacro(this->GetUserMessages(),
                                     "vtkMRMLVolumetrySeedsStorageNode::ReadDataInternal",
                                     "Reading seed carrier failed: reference node is not a vtkMRMLVolumetrySeedsNode (got '" << refNode->GetClassName() << "')");
    return 0;
  }

  const std::string fullName = this->GetFullNameFromFileName();
  if (fullName.empty())
  {
    vtkErrorToMessageCollectionMacro(this->GetUserMessages(), "vtkMRMLVolumetrySeedsStorageNode::ReadDataInternal", "Reading seed carrier failed: file name not specified");
    return 0;
  }
  if (!endsWithLower(fullName, ".vsd.json") && !endsWithLower(fullName, ".json"))
  {
    vtkErrorToMessageCollectionMacro(this->GetUserMessages(),
                                     "vtkMRMLVolumetrySeedsStorageNode::ReadDataInternal",
                                     "Reading seed carrier failed: unsupported file extension for '" << fullName << "' (expected .vsd.json)");
    return 0;
  }
  return this->ReadJson(fullName, carrier);
}

//------------------------------------------------------------------------------
int vtkMRMLVolumetrySeedsStorageNode::WriteDataInternal(vtkMRMLNode* refNode)
{
  if (refNode == nullptr)
  {
    vtkErrorToMessageCollectionMacro(this->GetUserMessages(), "vtkMRMLVolumetrySeedsStorageNode::WriteDataInternal", "Writing seed carrier failed: null reference node");
    return 0;
  }
  vtkMRMLVolumetrySeedsNode* carrier = vtkMRMLVolumetrySeedsNode::SafeDownCast(refNode);
  if (carrier == nullptr)
  {
    vtkErrorToMessageCollectionMacro(this->GetUserMessages(),
                                     "vtkMRMLVolumetrySeedsStorageNode::WriteDataInternal",
                                     "Writing seed carrier failed: reference node is not a vtkMRMLVolumetrySeedsNode (got '" << refNode->GetClassName() << "')");
    return 0;
  }

  const std::string fullName = this->GetFullNameFromFileName();
  if (fullName.empty())
  {
    vtkErrorToMessageCollectionMacro(this->GetUserMessages(), "vtkMRMLVolumetrySeedsStorageNode::WriteDataInternal", "Writing seed carrier failed: file name not specified");
    return 0;
  }
  if (!endsWithLower(fullName, ".vsd.json") && !endsWithLower(fullName, ".json"))
  {
    vtkErrorToMessageCollectionMacro(this->GetUserMessages(),
                                     "vtkMRMLVolumetrySeedsStorageNode::WriteDataInternal",
                                     "Writing seed carrier failed: unsupported file extension for '" << fullName << "' (expected .vsd.json)");
    return 0;
  }
  return this->WriteJson(fullName, carrier);
}

//------------------------------------------------------------------------------
int vtkMRMLVolumetrySeedsStorageNode::WriteJson(const std::string& filePath, vtkMRMLVolumetrySeedsNode* carrier)
{
  vtkNew<vtkMRMLJsonWriter> writer;
  if (!writer->WriteToFileBegin(filePath.c_str(), nullptr))
  {
    vtkErrorToMessageCollectionMacro(
      this->GetUserMessages(), "vtkMRMLVolumetrySeedsStorageNode::WriteJson", "Writing seed carrier failed: failed to open '" << filePath << "' for writing");
    return 0;
  }

  writer->WriteIntProperty("schemaVersion", SchemaVersion);

  // The stable-ID mint counter: persisted so a reloaded carrier keeps minting
  // PAST every ID this document ever handed out (never-reuse across sessions).
  writer->WriteIntProperty("seedIdCounter", carrier->GetSeedIDCounter());

  // seeds -- an ORDERED array; each element carries the RAS coordinate, the
  // per-seed LABEL (the generated segment name, ADR-0038 §Conformance), and
  // the per-seed display colour.
  writer->WriteArrayPropertyStart("seeds");
  const int nSeeds = carrier->GetNumberOfSeeds();
  for (int i = 0; i < nSeeds; ++i)
  {
    const double* src = carrier->GetNthSeed(i);
    double xyz[3] = { src[0], src[1], src[2] };
    const std::string label = carrier->GetNthSeedLabel(i);
    const double* colorSrc = carrier->GetNthSeedColor(i);
    double color[3] = { colorSrc[0], colorSrc[1], colorSrc[2] };
    const std::string bindingSegmentationNodeID = carrier->GetNthSeedBindingSegmentationNodeID(i);
    const std::string bindingSegmentID = carrier->GetNthSeedBindingSegmentID(i);
    const std::string volume = carrier->GetNthSeedVolume(i);
    vtkNew<vtkStringArray> contextArray;
    carrier->GetNthSeedVisibilityContext(i, contextArray);
    std::vector<std::string> context;
    context.reserve(static_cast<std::size_t>(contextArray->GetNumberOfValues()));
    for (vtkIdType v = 0; v < contextArray->GetNumberOfValues(); ++v)
    {
      context.push_back(contextArray->GetValue(v));
    }

    writer->WriteObjectStart();
    writer->WriteVectorProperty("xyz", xyz, 3);
    // The seed's STABLE identity (minted at AddSeed, never reused): written
    // unconditionally -- identity is core, not an optional decoration.
    writer->WriteStringProperty("id", carrier->GetNthSeedID(i));
    writer->WriteStringProperty("label", label);
    writer->WriteVectorProperty("color", color, 3);
    // The structure binding the seed→label capture resolves
    // (``territory-usability`` §"Seed→label capture"): both empty == unbound,
    // and are only written when present so an unbound seed stays terse.
    if (!bindingSegmentationNodeID.empty() || !bindingSegmentID.empty())
    {
      writer->WriteStringProperty("bindingSegmentationNodeID", bindingSegmentationNodeID);
      writer->WriteStringProperty("bindingSegmentID", bindingSegmentID);
    }
    // The VISIBILITY CONTEXT snapshot (the visibility-composed carve rule,
    // ``VisibilityCarve``): the ordered top-first segment IDs visible at
    // placement.  Empty == no snapshot (legacy: no carve) and is only written
    // when present so an unsnapshotted seed stays terse.
    if (!context.empty())
    {
      writer->WriteStringVectorProperty("visibilityContext", context);
    }
    // The VOLUME group the seed belongs to (``territory-usability``
    // grouped-volumes); empty == ungrouped and only written when present.
    if (!volume.empty())
    {
      writer->WriteStringProperty("volume", volume);
    }
    writer->WriteObjectEnd();
  }
  writer->WriteArrayPropertyEnd();

  // volumes -- the per-volume DISPLAY slots (colour + label) keyed on the
  // volume id, mirroring the territory carrier's per-territory display slots.
  // Enumerated deterministically so the document is stable; an empty (zero-seed)
  // volume rides here alone so its table row survives a round-trip.
  writer->WriteArrayPropertyStart("volumes");
  for (const std::string& volumeId : carrier->GetVolumeIds())
  {
    const double* colorSrc = carrier->GetVolumeColor(volumeId);
    double color[3] = { colorSrc[0], colorSrc[1], colorSrc[2] };
    writer->WriteObjectStart();
    writer->WriteStringProperty("id", volumeId);
    writer->WriteStringProperty("label", carrier->GetVolumeLabel(volumeId));
    writer->WriteVectorProperty("color", color, 3);
    writer->WriteObjectEnd();
  }
  writer->WriteArrayPropertyEnd();

  if (!writer->WriteToFileEnd())
  {
    vtkErrorToMessageCollectionMacro(
      this->GetUserMessages(), "vtkMRMLVolumetrySeedsStorageNode::WriteJson", "Writing seed carrier failed: failed to close '" << filePath << "' after write");
    return 0;
  }
  return 1;
}

//------------------------------------------------------------------------------
int vtkMRMLVolumetrySeedsStorageNode::ReadJson(const std::string& filePath, vtkMRMLVolumetrySeedsNode* carrier)
{
  vtkNew<vtkMRMLJsonReader> reader;
  vtkSmartPointer<vtkMRMLJsonElement> root = vtkSmartPointer<vtkMRMLJsonElement>::Take(reader->ReadFromFile(filePath.c_str()));
  if (root == nullptr)
  {
    vtkErrorToMessageCollectionMacro(this->GetUserMessages(), "vtkMRMLVolumetrySeedsStorageNode::ReadJson", "Reading seed carrier failed: failed to parse '" << filePath << "'");
    return 0;
  }
  if (!root->HasMember("schemaVersion"))
  {
    vtkErrorToMessageCollectionMacro(
      this->GetUserMessages(), "vtkMRMLVolumetrySeedsStorageNode::ReadJson", "Reading seed carrier failed: missing required 'schemaVersion' field in '" << filePath << "'");
    return 0;
  }
  const int schemaVersion = root->GetIntProperty("schemaVersion");
  if (schemaVersion < MinReadableSchemaVersion || schemaVersion > SchemaVersion)
  {
    vtkErrorToMessageCollectionMacro(this->GetUserMessages(),
                                     "vtkMRMLVolumetrySeedsStorageNode::ReadJson",
                                     "Reading seed carrier failed: unsupported schemaVersion " << schemaVersion << " in '" << filePath << "' (this build understands "
                                                                                               << MinReadableSchemaVersion << " through " << SchemaVersion << ")");
    return 0;
  }

  // The read REPLACES the carrier's seed state under a single ModifyBlocker:
  // drop every existing seed so a re-read into a reused sink does not
  // accumulate, then repopulate in document order.  RemoveVolume also clears
  // the per-volume display slots so a reused sink does not retain stale ones.
  MRMLNodeModifyBlocker blocker(carrier);
  for (int i = carrier->GetNumberOfSeeds() - 1; i >= 0; --i)
  {
    carrier->RemoveNthSeed(i);
  }
  for (const std::string& volumeId : carrier->GetVolumeIds())
  {
    carrier->RemoveVolume(volumeId);
  }

  // Restore the stable-ID mint counter FIRST (the setter clamps forward-only,
  // so a reused sink whose counter already ran ahead keeps the larger value —
  // the never-reuse invariant).  A legacy document without the field leaves
  // the counter to grow through the AddSeed mints below.
  if (root->HasMember("seedIdCounter"))
  {
    carrier->SetSeedIDCounter(root->GetIntProperty("seedIdCounter"));
  }

  if (root->HasMember("volumes"))
  {
    vtkSmartPointer<vtkMRMLJsonElement> volumes = vtkSmartPointer<vtkMRMLJsonElement>::Take(root->GetArrayProperty("volumes"));
    if (volumes != nullptr)
    {
      const int nVolumes = volumes->GetArraySize();
      for (int i = 0; i < nVolumes; ++i)
      {
        vtkSmartPointer<vtkMRMLJsonElement> item = vtkSmartPointer<vtkMRMLJsonElement>::Take(volumes->GetArrayItem(i));
        if (item == nullptr || !item->HasMember("id"))
        {
          continue;
        }
        const std::string volumeId = item->GetStringProperty("id");
        if (volumeId.empty())
        {
          continue;
        }
        carrier->AddVolume(volumeId);
        if (item->HasMember("label"))
        {
          carrier->SetVolumeLabel(volumeId, item->GetStringProperty("label"));
        }
        double color[3] = { 1.0, 1.0, 1.0 };
        if (item->GetVectorProperty("color", color, 3))
        {
          carrier->SetVolumeColor(volumeId, color[0], color[1], color[2]);
        }
      }
    }
  }

  if (!root->HasMember("seeds"))
  {
    return 1;
  }
  vtkSmartPointer<vtkMRMLJsonElement> list = vtkSmartPointer<vtkMRMLJsonElement>::Take(root->GetArrayProperty("seeds"));
  if (list == nullptr)
  {
    vtkWarningToMessageCollectionMacro(this->GetUserMessages(), "vtkMRMLVolumetrySeedsStorageNode::ReadJson", "'seeds' present but unreadable in '" << filePath << "'");
    return 1;
  }

  const int nSeeds = list->GetArraySize();
  for (int i = 0; i < nSeeds; ++i)
  {
    vtkSmartPointer<vtkMRMLJsonElement> item = vtkSmartPointer<vtkMRMLJsonElement>::Take(list->GetArrayItem(i));
    if (item == nullptr)
    {
      continue;
    }
    double xyz[3] = { 0.0, 0.0, 0.0 };
    if (!item->GetVectorProperty("xyz", xyz, 3))
    {
      continue;
    }
    const int index = carrier->AddSeed(xyz[0], xyz[1], xyz[2]);
    // Restore the seed's STABLE ID over the freshly-minted one (the protected
    // storage-read seam); a legacy document without ids keeps the mint.
    if (item->HasMember("id"))
    {
      const std::string seedID = item->GetStringProperty("id");
      if (!seedID.empty())
      {
        carrier->SetNthSeedID(index, seedID);
      }
    }
    if (item->HasMember("label"))
    {
      carrier->SetNthSeedLabel(index, item->GetStringProperty("label"));
    }
    double color[3] = { 1.0, 1.0, 1.0 };
    if (item->GetVectorProperty("color", color, 3))
    {
      carrier->SetNthSeedColor(index, color[0], color[1], color[2]);
    }
    if (item->HasMember("bindingSegmentID") || item->HasMember("bindingSegmentationNodeID"))
    {
      const std::string bindingSegmentationNodeID = item->HasMember("bindingSegmentationNodeID") ? item->GetStringProperty("bindingSegmentationNodeID") : std::string();
      const std::string bindingSegmentID = item->HasMember("bindingSegmentID") ? item->GetStringProperty("bindingSegmentID") : std::string();
      carrier->SetNthSeedBinding(index, bindingSegmentationNodeID, bindingSegmentID);
    }
    if (item->HasMember("visibilityContext"))
    {
      std::vector<std::string> context;
      if (item->GetStringVectorProperty("visibilityContext", context))
      {
        vtkNew<vtkStringArray> contextArray;
        for (const std::string& segmentID : context)
        {
          contextArray->InsertNextValue(segmentID);
        }
        carrier->SetNthSeedVisibilityContext(index, contextArray);
      }
    }
    if (item->HasMember("volume"))
    {
      carrier->SetNthSeedVolume(index, item->GetStringProperty("volume"));
    }
  }
  return 1;
}

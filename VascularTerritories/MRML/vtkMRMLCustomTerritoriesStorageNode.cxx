/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Implementation of vtkMRMLCustomTerritoriesStorageNode — the ``.vta.json``
  storage layer for the custom-territories annotation carrier (ADR-0037
  §Decision 1).  Mirrors vtkMRMLResectionPlanStorageNode (ADR-0014
  §"Fourth layer").  See the class docstring in the header for the schema.

==============================================================================*/

// This module MRML includes
#include "vtkMRMLCustomTerritoriesStorageNode.h"
#include "vtkMRMLCustomTerritoriesNode.h"

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
#include <vector>

//------------------------------------------------------------------------------
vtkMRMLNodeNewMacro(vtkMRMLCustomTerritoriesStorageNode);

//------------------------------------------------------------------------------
vtkMRMLCustomTerritoriesStorageNode::vtkMRMLCustomTerritoriesStorageNode()
{
  this->DefaultWriteFileExtension = "vta.json";
}

//------------------------------------------------------------------------------
vtkMRMLCustomTerritoriesStorageNode::~vtkMRMLCustomTerritoriesStorageNode() = default;

//------------------------------------------------------------------------------
void vtkMRMLCustomTerritoriesStorageNode::PrintSelf(ostream& os, vtkIndent indent)
{
  Superclass::PrintSelf(os, indent);
  os << indent << "SchemaVersion: " << SchemaVersion << "\n";
}

//------------------------------------------------------------------------------
bool vtkMRMLCustomTerritoriesStorageNode::CanReadInReferenceNode(vtkMRMLNode* refNode)
{
  return refNode != nullptr && refNode->IsA("vtkMRMLCustomTerritoriesNode");
}

//------------------------------------------------------------------------------
bool vtkMRMLCustomTerritoriesStorageNode::CanWriteFromReferenceNode(vtkMRMLNode* refNode)
{
  return refNode != nullptr && refNode->IsA("vtkMRMLCustomTerritoriesNode");
}

//------------------------------------------------------------------------------
void vtkMRMLCustomTerritoriesStorageNode::InitializeSupportedReadFileTypes()
{
  this->SupportedReadFileTypes->InsertNextValue("Vascular territories annotation (.vta.json)");
}

//------------------------------------------------------------------------------
void vtkMRMLCustomTerritoriesStorageNode::InitializeSupportedWriteFileTypes()
{
  this->SupportedWriteFileTypes->InsertNextValue("Vascular territories annotation (.vta.json)");
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
int vtkMRMLCustomTerritoriesStorageNode::ReadDataInternal(vtkMRMLNode* refNode)
{
  if (refNode == nullptr)
  {
    vtkErrorToMessageCollectionMacro(this->GetUserMessages(), "vtkMRMLCustomTerritoriesStorageNode::ReadDataInternal", "Reading annotation carrier failed: null reference node");
    return 0;
  }
  vtkMRMLCustomTerritoriesNode* carrier = vtkMRMLCustomTerritoriesNode::SafeDownCast(refNode);
  if (carrier == nullptr)
  {
    vtkErrorToMessageCollectionMacro(this->GetUserMessages(),
                                     "vtkMRMLCustomTerritoriesStorageNode::ReadDataInternal",
                                     "Reading annotation carrier failed: reference node is not a vtkMRMLCustomTerritoriesNode (got '" << refNode->GetClassName() << "')");
    return 0;
  }

  const std::string fullName = this->GetFullNameFromFileName();
  if (fullName.empty())
  {
    vtkErrorToMessageCollectionMacro(
      this->GetUserMessages(), "vtkMRMLCustomTerritoriesStorageNode::ReadDataInternal", "Reading annotation carrier failed: file name not specified");
    return 0;
  }
  if (!endsWithLower(fullName, ".vta.json") && !endsWithLower(fullName, ".json"))
  {
    vtkErrorToMessageCollectionMacro(this->GetUserMessages(),
                                     "vtkMRMLCustomTerritoriesStorageNode::ReadDataInternal",
                                     "Reading annotation carrier failed: unsupported file extension for '" << fullName << "' (expected .vta.json)");
    return 0;
  }
  return this->ReadJson(fullName, carrier);
}

//------------------------------------------------------------------------------
int vtkMRMLCustomTerritoriesStorageNode::WriteDataInternal(vtkMRMLNode* refNode)
{
  if (refNode == nullptr)
  {
    vtkErrorToMessageCollectionMacro(this->GetUserMessages(), "vtkMRMLCustomTerritoriesStorageNode::WriteDataInternal", "Writing annotation carrier failed: null reference node");
    return 0;
  }
  vtkMRMLCustomTerritoriesNode* carrier = vtkMRMLCustomTerritoriesNode::SafeDownCast(refNode);
  if (carrier == nullptr)
  {
    vtkErrorToMessageCollectionMacro(this->GetUserMessages(),
                                     "vtkMRMLCustomTerritoriesStorageNode::WriteDataInternal",
                                     "Writing annotation carrier failed: reference node is not a vtkMRMLCustomTerritoriesNode (got '" << refNode->GetClassName() << "')");
    return 0;
  }

  const std::string fullName = this->GetFullNameFromFileName();
  if (fullName.empty())
  {
    vtkErrorToMessageCollectionMacro(
      this->GetUserMessages(), "vtkMRMLCustomTerritoriesStorageNode::WriteDataInternal", "Writing annotation carrier failed: file name not specified");
    return 0;
  }
  if (!endsWithLower(fullName, ".vta.json") && !endsWithLower(fullName, ".json"))
  {
    vtkErrorToMessageCollectionMacro(this->GetUserMessages(),
                                     "vtkMRMLCustomTerritoriesStorageNode::WriteDataInternal",
                                     "Writing annotation carrier failed: unsupported file extension for '" << fullName << "' (expected .vta.json)");
    return 0;
  }
  return this->WriteJson(fullName, carrier);
}

//------------------------------------------------------------------------------
int vtkMRMLCustomTerritoriesStorageNode::WriteJson(const std::string& filePath, vtkMRMLCustomTerritoriesNode* carrier)
{
  vtkNew<vtkMRMLJsonWriter> writer;
  if (!writer->WriteToFileBegin(filePath.c_str(), nullptr))
  {
    vtkErrorToMessageCollectionMacro(
      this->GetUserMessages(), "vtkMRMLCustomTerritoriesStorageNode::WriteJson", "Writing annotation carrier failed: failed to open '" << filePath << "' for writing");
    return 0;
  }

  writer->WriteIntProperty("schemaVersion", SchemaVersion);

  // annotationPoints -- an object keyed by territory id, each mapping to an
  // ORDERED array of [x, y, z] points (ADR-0037 §Decision 1 "ordered ...
  // per territory").
  writer->WriteObjectPropertyStart("annotationPoints");
  {
    for (const std::string& territoryId : carrier->GetAnnotationTerritoryIds())
    {
      const int nPoints = carrier->GetNumberOfAnnotationPoints(territoryId);
      writer->WriteArrayPropertyStart(territoryId);
      for (int i = 0; i < nPoints; ++i)
      {
        const double* src = carrier->GetNthAnnotationPoint(territoryId, i);
        double p[3] = { src[0], src[1], src[2] };
        writer->WriteObjectStart();
        writer->WriteVectorProperty("xyz", p, 3);
        writer->WriteObjectEnd();
      }
      writer->WriteArrayPropertyEnd();
    }
  }
  writer->WriteObjectPropertyEnd();

  // territoryDisplay -- an object keyed by territory id carrying the
  // per-territory display slot (colour / label / visibility) ADR-0037
  // §Decision 3 adds alongside the ordered points.  Independent of the
  // geometry: a territory may carry display attributes without points and
  // vice versa.
  writer->WriteObjectPropertyStart("territoryDisplay");
  {
    for (const std::string& territoryId : carrier->GetDisplayTerritoryIds())
    {
      writer->WriteObjectPropertyStart(territoryId);
      const double* color = carrier->GetTerritoryColor(territoryId);
      double rgb[3] = { color[0], color[1], color[2] };
      writer->WriteVectorProperty("color", rgb, 3);
      writer->WriteStringProperty("label", carrier->GetTerritoryLabel(territoryId));
      writer->WriteBoolProperty("visibility", carrier->GetTerritoryVisibility(territoryId));
      // Per-territory review status (ADR-0037 Amendment "Per-territory status +
      // derived edit-lock"): the machine-readable status STRING, matching
      // Slicer's segment-status strings (ADR-0034).  The lock is derived from
      // it on read, so no separate lock field is persisted.
      writer->WriteStringProperty("status", vtkMRMLCustomTerritoriesNode::GetStatusAsMachineString(carrier->GetTerritoryStatus(territoryId)));
      writer->WriteObjectPropertyEnd();
    }
  }
  writer->WriteObjectPropertyEnd();

  if (!writer->WriteToFileEnd())
  {
    vtkErrorToMessageCollectionMacro(
      this->GetUserMessages(), "vtkMRMLCustomTerritoriesStorageNode::WriteJson", "Writing annotation carrier failed: failed to close '" << filePath << "' after write");
    return 0;
  }
  return 1;
}

//------------------------------------------------------------------------------
int vtkMRMLCustomTerritoriesStorageNode::ReadJson(const std::string& filePath, vtkMRMLCustomTerritoriesNode* carrier)
{
  vtkNew<vtkMRMLJsonReader> reader;
  vtkSmartPointer<vtkMRMLJsonElement> root = vtkSmartPointer<vtkMRMLJsonElement>::Take(reader->ReadFromFile(filePath.c_str()));
  if (root == nullptr)
  {
    vtkErrorToMessageCollectionMacro(
      this->GetUserMessages(), "vtkMRMLCustomTerritoriesStorageNode::ReadJson", "Reading annotation carrier failed: failed to parse '" << filePath << "'");
    return 0;
  }
  if (!root->HasMember("schemaVersion"))
  {
    vtkErrorToMessageCollectionMacro(this->GetUserMessages(),
                                     "vtkMRMLCustomTerritoriesStorageNode::ReadJson",
                                     "Reading annotation carrier failed: missing required 'schemaVersion' field in '" << filePath << "'");
    return 0;
  }
  const int schemaVersion = root->GetIntProperty("schemaVersion");
  if (schemaVersion < MinReadableSchemaVersion || schemaVersion > SchemaVersion)
  {
    vtkErrorToMessageCollectionMacro(this->GetUserMessages(),
                                     "vtkMRMLCustomTerritoriesStorageNode::ReadJson",
                                     "Reading annotation carrier failed: unsupported schemaVersion " << schemaVersion << " in '" << filePath << "' (this build understands "
                                                                                                     << MinReadableSchemaVersion << " through " << SchemaVersion << ")");
    return 0;
  }

  // The read REPLACES the carrier's annotation state under a single
  // ModifyBlocker: clear every territory that already carries points so a
  // re-read into a reused sink does not accumulate, then repopulate.
  MRMLNodeModifyBlocker blocker(carrier);
  for (const std::string& territoryId : carrier->GetAnnotationTerritoryIds())
  {
    carrier->ClearAnnotationPoints(territoryId);
  }

  if (root->HasMember("annotationPoints"))
  {
    vtkSmartPointer<vtkMRMLJsonElement> pointsJson = vtkSmartPointer<vtkMRMLJsonElement>::Take(root->GetObjectProperty("annotationPoints"));
    if (pointsJson == nullptr)
    {
      vtkWarningToMessageCollectionMacro(
        this->GetUserMessages(), "vtkMRMLCustomTerritoriesStorageNode::ReadJson", "'annotationPoints' present but unreadable in '" << filePath << "'");
    }
    else
    {
      const int numberOfTerritories = pointsJson->GetObjectSize();
      for (int t = 0; t < numberOfTerritories; ++t)
      {
        const std::string territoryId = pointsJson->GetObjectPropertyNameByIndex(t);
        if (territoryId.empty())
        {
          continue;
        }
        vtkSmartPointer<vtkMRMLJsonElement> list = vtkSmartPointer<vtkMRMLJsonElement>::Take(pointsJson->GetArrayProperty(territoryId.c_str()));
        if (list == nullptr)
        {
          continue;
        }
        const int nPoints = list->GetArraySize();
        for (int i = 0; i < nPoints; ++i)
        {
          vtkSmartPointer<vtkMRMLJsonElement> item = vtkSmartPointer<vtkMRMLJsonElement>::Take(list->GetArrayItem(i));
          if (item == nullptr)
          {
            continue;
          }
          double p[3] = { 0.0, 0.0, 0.0 };
          if (item->GetVectorProperty("xyz", p, 3))
          {
            carrier->AddAnnotationPoint(territoryId, p[0], p[1], p[2]);
          }
        }
      }
    }
  }

  this->ReadDisplay(root, carrier, filePath);
  return 1;
}

//------------------------------------------------------------------------------
void vtkMRMLCustomTerritoriesStorageNode::ReadDisplay(vtkMRMLJsonElement* root, vtkMRMLCustomTerritoriesNode* carrier, const std::string& filePath)
{
  if (root == nullptr || !root->HasMember("territoryDisplay"))
  {
    return;
  }
  vtkSmartPointer<vtkMRMLJsonElement> displayJson = vtkSmartPointer<vtkMRMLJsonElement>::Take(root->GetObjectProperty("territoryDisplay"));
  if (displayJson == nullptr)
  {
    vtkWarningToMessageCollectionMacro(
      this->GetUserMessages(), "vtkMRMLCustomTerritoriesStorageNode::ReadDisplay", "'territoryDisplay' present but unreadable in '" << filePath << "'");
    return;
  }
  const int numberOfTerritories = displayJson->GetObjectSize();
  for (int t = 0; t < numberOfTerritories; ++t)
  {
    const std::string territoryId = displayJson->GetObjectPropertyNameByIndex(t);
    if (territoryId.empty())
    {
      continue;
    }
    vtkSmartPointer<vtkMRMLJsonElement> entry = vtkSmartPointer<vtkMRMLJsonElement>::Take(displayJson->GetObjectProperty(territoryId.c_str()));
    if (entry == nullptr)
    {
      continue;
    }
    double rgb[3] = { 1.0, 1.0, 1.0 };
    if (entry->GetVectorProperty("color", rgb, 3))
    {
      carrier->SetTerritoryColor(territoryId, rgb[0], rgb[1], rgb[2]);
    }
    if (entry->HasMember("label"))
    {
      carrier->SetTerritoryLabel(territoryId, entry->GetStringProperty("label"));
    }
    if (entry->HasMember("visibility"))
    {
      carrier->SetTerritoryVisibility(territoryId, entry->GetBoolProperty("visibility"));
    }
    if (entry->HasMember("status"))
    {
      // Decode the machine-readable status STRING back to the enum ordinal
      // (ADR-0037 Amendment "Per-territory status + derived edit-lock").  A
      // document without a status field reads back the carrier default
      // (NotStarted), which is additive to the pre-status schema.
      carrier->SetTerritoryStatus(territoryId, vtkMRMLCustomTerritoriesNode::GetStatusFromMachineString(entry->GetStringProperty("status")));
    }
  }
}

/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Implementation of vtkMRMLResectionPlanStorageNode — plan-rooted
  .lrp.json schema v2 (trimmed) per the 2026-05-25 wrapper-vs-carrier
  amendment to ADR-0014 + ADR-0023.  See the class docstring in the
  header and Docs/design/resection-plan-architecture/05-lrp-json-schema.md
  for the schema.

==============================================================================*/

// This module MRML includes
#include "vtkMRMLResectionPlanStorageNode.h"
#include "vtkMRMLResectionPlanNode.h"
#include "vtkMRMLAbstractParametricSurfaceNode.h"
#include "vtkMRMLBezierSurfaceNode.h"

// MRML includes
#include <vtkMRMLJsonElement.h>
#include <vtkMRMLMessageCollection.h>
#include <vtkMRMLScene.h>
#include <vtkMRMLStorageNode.h>

// VTK includes
#include <vtkNew.h>
#include <vtkObjectFactory.h>
#include <vtkSmartPointer.h>
#include <vtkStringArray.h>

// STD includes
#include <algorithm>
#include <cstring>
#include <sstream>
#include <string>
#include <vector>

//------------------------------------------------------------------------------
vtkMRMLNodeNewMacro(vtkMRMLResectionPlanStorageNode);

//------------------------------------------------------------------------------
vtkMRMLResectionPlanStorageNode::vtkMRMLResectionPlanStorageNode()
{
  this->DefaultWriteFileExtension = "lrp.json";
}

//------------------------------------------------------------------------------
vtkMRMLResectionPlanStorageNode::~vtkMRMLResectionPlanStorageNode() = default;

//------------------------------------------------------------------------------
void vtkMRMLResectionPlanStorageNode::PrintSelf(ostream& os, vtkIndent indent)
{
  Superclass::PrintSelf(os, indent);
  os << indent << "SchemaVersion: " << SchemaVersion << "\n";
}

//------------------------------------------------------------------------------
bool vtkMRMLResectionPlanStorageNode::CanReadInReferenceNode(vtkMRMLNode* refNode)
{
  return refNode != nullptr && refNode->IsA("vtkMRMLResectionPlanNode");
}

//------------------------------------------------------------------------------
bool vtkMRMLResectionPlanStorageNode::CanWriteFromReferenceNode(vtkMRMLNode* refNode)
{
  return refNode != nullptr && refNode->IsA("vtkMRMLResectionPlanNode");
}

//------------------------------------------------------------------------------
void vtkMRMLResectionPlanStorageNode::InitializeSupportedReadFileTypes()
{
  this->SupportedReadFileTypes->InsertNextValue("Liver resection plan (.lrp.json)");
}

//------------------------------------------------------------------------------
void vtkMRMLResectionPlanStorageNode::InitializeSupportedWriteFileTypes()
{
  this->SupportedWriteFileTypes->InsertNextValue("Liver resection plan (.lrp.json)");
}

//------------------------------------------------------------------------------
namespace
{
/// Lowercase + tail-match dispatch helper.
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
  const std::string tail = toLower(path.substr(path.size() - suffix.size()));
  return tail == suffix;
}
} // namespace

//------------------------------------------------------------------------------
int vtkMRMLResectionPlanStorageNode::ReadDataInternal(vtkMRMLNode* refNode)
{
  if (refNode == nullptr)
  {
    vtkErrorMacro("ReadDataInternal: null reference node");
    return 0;
  }
  vtkMRMLResectionPlanNode* plan = vtkMRMLResectionPlanNode::SafeDownCast(refNode);
  if (plan == nullptr)
  {
    vtkErrorMacro("ReadDataInternal: reference node is not a vtkMRMLResectionPlanNode (got '" << refNode->GetClassName() << "')");
    return 0;
  }

  const std::string fullName = this->GetFullNameFromFileName();
  if (fullName.empty())
  {
    vtkErrorMacro("ReadDataInternal: file name not specified");
    return 0;
  }

  if (!endsWithLower(fullName, ".lrp.json") && !endsWithLower(fullName, ".json"))
  {
    vtkErrorMacro("ReadDataInternal: unsupported file extension for '" << fullName << "' (expected .lrp.json)");
    return 0;
  }
  return this->ReadJson(fullName, plan);
}

//------------------------------------------------------------------------------
int vtkMRMLResectionPlanStorageNode::WriteDataInternal(vtkMRMLNode* refNode)
{
  if (refNode == nullptr)
  {
    vtkErrorMacro("WriteDataInternal: null reference node");
    return 0;
  }
  vtkMRMLResectionPlanNode* plan = vtkMRMLResectionPlanNode::SafeDownCast(refNode);
  if (plan == nullptr)
  {
    vtkErrorMacro("WriteDataInternal: reference node is not a vtkMRMLResectionPlanNode (got '" << refNode->GetClassName() << "')");
    return 0;
  }

  const std::string fullName = this->GetFullNameFromFileName();
  if (fullName.empty())
  {
    vtkErrorMacro("WriteDataInternal: file name not specified");
    return 0;
  }
  if (!endsWithLower(fullName, ".lrp.json") && !endsWithLower(fullName, ".json"))
  {
    vtkErrorMacro("WriteDataInternal: unsupported file extension for '" << fullName << "' (expected .lrp.json)");
    return 0;
  }
  return this->WriteJson(fullName, plan);
}

//------------------------------------------------------------------------------
int vtkMRMLResectionPlanStorageNode::WriteJson(const std::string& filePath, vtkMRMLResectionPlanNode* plan)
{
  vtkNew<vtkMRMLJsonWriter> writer;
  if (!writer->WriteToFileBegin(filePath.c_str(), nullptr))
  {
    vtkErrorMacro("WriteJson: failed to open '" << filePath << "' for writing");
    return 0;
  }

  writer->WriteIntProperty("schemaVersion", SchemaVersion);

  // Plan-level fields at root -- the document IS the plan (per
  // design 05-lrp-json-schema.md §"Why the JSON document is the plan").
  const char* mrmlName = plan->GetName();
  writer->WriteStringProperty("name", mrmlName ? mrmlName : "");
  writer->WriteDoubleProperty("safetyMargin_mm", plan->GetSafetyMargin_mm());
  writer->WriteDoubleProperty("riskMargin_mm", plan->GetRiskMargin_mm());
  writer->WriteIntProperty("orderIndex", plan->GetOrderIndex());
  writer->WriteStringProperty("state", vtkMRMLResectionPlanNode::GetStateAsString(plan->GetState()));

  // surface block -- polymorphic carrier shape.
  vtkMRMLAbstractParametricSurfaceNode* surface = plan->GetGeometryNode();
  if (surface != nullptr)
  {
    writer->WriteObjectPropertyStart("surface");
    {
      writer->WriteStringProperty("type", surface->GetSurfaceType());
      writer->WriteIntProperty("rows", static_cast<int>(surface->GetRows()));
      writer->WriteIntProperty("cols", static_cast<int>(surface->GetCols()));
      writer->WriteVectorProperty("controlGrid", const_cast<double*>(surface->GetControlGrid()), static_cast<int>(surface->GetControlGridLength()));
      writer->WriteStringProperty("initMode", vtkMRMLAbstractParametricSurfaceNode::GetInitModeAsString(surface->GetInitMode()));

      writer->WriteObjectPropertyStart("slicingPlane");
      {
        double v[3];
        surface->GetSlicingPlaneOrigin(v);
        writer->WriteVectorProperty("origin", v, 3);
        surface->GetSlicingPlaneNormal(v);
        writer->WriteVectorProperty("normal", v, 3);
        double initPointsFlat[6] = { 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 };
        for (int i = 0; i < 2; ++i)
        {
          const double* p = surface->GetSlicingPlaneInitPoint(i);
          if (p == nullptr)
          {
            continue;
          }
          initPointsFlat[i * 3 + 0] = p[0];
          initPointsFlat[i * 3 + 1] = p[1];
          initPointsFlat[i * 3 + 2] = p[2];
        }
        writer->WriteVectorProperty("initPointsFlat", initPointsFlat, 6);
      }
      writer->WriteObjectPropertyEnd();

      writer->WriteObjectPropertyStart("distanceSpheroid");
      {
        double v[3];
        surface->GetDistanceSpheroidCenter(v);
        writer->WriteVectorProperty("center", v, 3);

        writer->WriteObjectPropertyStart("radius");
        writer->WriteDoubleProperty("x", surface->GetDistanceSpheroidRadiusX());
        writer->WriteDoubleProperty("y", surface->GetDistanceSpheroidRadiusY());
        writer->WriteDoubleProperty("z", surface->GetDistanceSpheroidRadiusZ());
        writer->WriteObjectPropertyEnd();

        const int nPoints = surface->GetNumberOfDistanceSpheroidInitPoints();
        writer->WriteIntProperty("numberOfInitPoints", nPoints);
        if (nPoints > 0)
        {
          std::vector<double> flat(static_cast<size_t>(nPoints) * 3, 0.0);
          for (int i = 0; i < nPoints; ++i)
          {
            const double* p = surface->GetDistanceSpheroidInitPoint(i);
            if (p == nullptr)
            {
              continue;
            }
            flat[static_cast<size_t>(i) * 3 + 0] = p[0];
            flat[static_cast<size_t>(i) * 3 + 1] = p[1];
            flat[static_cast<size_t>(i) * 3 + 2] = p[2];
          }
          writer->WriteVectorProperty("initPointsFlat", flat.data(), static_cast<int>(flat.size()));
        }
        else
        {
          writer->WriteArrayPropertyStart("initPointsFlat");
          writer->WriteArrayPropertyEnd();
        }
      }
      writer->WriteObjectPropertyEnd();
    }
    writer->WriteObjectPropertyEnd();
  }
  else
  {
    vtkWarningMacro("WriteJson: plan '" << (mrmlName ? mrmlName : "<unnamed>") << "' has no geometry reference; emitting plan-only document.  The wrapper-vs-carrier pattern admits a plan without a wired surface (e.g. mid-init) -- the reader applies surface-default-construction on re-load.");
  }

  // Reserved-for-future metadata bag.
  writer->WriteObjectPropertyStart("metadata");
  writer->WriteObjectPropertyEnd();

  if (!writer->WriteToFileEnd())
  {
    vtkErrorMacro("WriteJson: failed to close '" << filePath << "' after write");
    return 0;
  }
  return 1;
}

//------------------------------------------------------------------------------
namespace
{
/// RAII guard: flip the Bezier-surface ``LoadingFromXML`` flag on for
/// the duration of a JSON read so the ADR-0014 §4 / ADR-0019 read-only
/// guards on the init-mode setters do not reject the post-Init state
/// values that round-trip through the polymorphic surface block.
class ScopedLoadingFromXML
{
public:
  explicit ScopedLoadingFromXML(vtkMRMLBezierSurfaceNode* node)
    : Node(node)
    , Prev(node != nullptr ? node->GetLoadingFromXML() : false)
  {
    if (this->Node != nullptr)
    {
      this->Node->SetLoadingFromXML(true);
    }
  }
  ~ScopedLoadingFromXML()
  {
    if (this->Node != nullptr)
    {
      this->Node->SetLoadingFromXML(this->Prev);
    }
  }
  ScopedLoadingFromXML(const ScopedLoadingFromXML&) = delete;
  ScopedLoadingFromXML& operator=(const ScopedLoadingFromXML&) = delete;

private:
  vtkMRMLBezierSurfaceNode* Node;
  bool Prev;
};
} // namespace

//------------------------------------------------------------------------------
int vtkMRMLResectionPlanStorageNode::ReadJson(const std::string& filePath, vtkMRMLResectionPlanNode* plan)
{
  vtkNew<vtkMRMLJsonReader> reader;
  vtkSmartPointer<vtkMRMLJsonElement> root = vtkSmartPointer<vtkMRMLJsonElement>::Take(reader->ReadFromFile(filePath.c_str()));
  if (root == nullptr)
  {
    vtkErrorMacro("ReadJson: failed to parse '" << filePath << "'");
    return 0;
  }
  if (!root->HasMember("schemaVersion"))
  {
    vtkErrorMacro("ReadJson: missing required 'schemaVersion' field in '" << filePath << "'");
    return 0;
  }
  const int schemaVersion = root->GetIntProperty("schemaVersion");
  if (schemaVersion < MinReadableSchemaVersion || schemaVersion > SchemaVersion)
  {
    vtkErrorMacro("ReadJson: unsupported schemaVersion " << schemaVersion << " in '" << filePath << "' (this build understands schemaVersion " << MinReadableSchemaVersion
                                                         << " through " << SchemaVersion << ")");
    return 0;
  }

  // Plan-level fields -- defensive HasMember guards per the design's
  // "unknown fields silently ignored" forward-compat rule.
  if (root->HasMember("name"))
  {
    const std::string name = root->GetStringProperty("name");
    if (!name.empty())
    {
      plan->SetName(name.c_str());
    }
  }
  if (root->HasMember("safetyMargin_mm"))
  {
    double value = 0.0;
    if (root->GetDoubleProperty("safetyMargin_mm", value))
    {
      plan->SetSafetyMargin_mm(value);
    }
  }
  if (root->HasMember("riskMargin_mm"))
  {
    double value = 0.0;
    if (root->GetDoubleProperty("riskMargin_mm", value))
    {
      plan->SetRiskMargin_mm(value);
    }
  }
  if (root->HasMember("orderIndex"))
  {
    int value = -1;
    if (root->GetIntProperty("orderIndex", value))
    {
      plan->SetOrderIndex(value);
    }
  }
  if (root->HasMember("state"))
  {
    const std::string s = root->GetStringProperty("state");
    const int code = vtkMRMLResectionPlanNode::GetStateFromString(s.c_str());
    if (code >= 0)
    {
      plan->SetState(code);
    }
    else
    {
      vtkWarningMacro("ReadJson: unknown plan state '" << s << "' in '" << filePath << "' -- leaving plan state at default");
    }
  }

  // surface block -- polymorphic carrier dispatch.
  if (!root->HasMember("surface"))
  {
    // Plan-only document is a valid mid-init shape; nothing more to
    // read.
    return 1;
  }

  vtkSmartPointer<vtkMRMLJsonElement> surfaceJson = vtkSmartPointer<vtkMRMLJsonElement>::Take(root->GetObjectProperty("surface"));
  if (surfaceJson == nullptr)
  {
    vtkWarningMacro("ReadJson: 'surface' block present but unreadable in '" << filePath << "'");
    return 1;
  }

  // Type discriminator drives subclass selection.
  std::string surfaceType;
  if (surfaceJson->HasMember("type"))
  {
    surfaceType = surfaceJson->GetStringProperty("type");
  }
  else
  {
    surfaceType = "Bezier";
  }

  // Resolve / create the surface node.  If the plan already has a
  // wired geometry reference of the right type, populate it in place;
  // otherwise, instantiate a fresh surface in the same scene and wire
  // it.
  vtkMRMLAbstractParametricSurfaceNode* surface = plan->GetGeometryNode();
  vtkMRMLScene* scene = plan->GetScene();
  if (surface == nullptr)
  {
    if (scene == nullptr)
    {
      vtkErrorMacro("ReadJson: plan '" << (plan->GetName() ? plan->GetName() : "<unnamed>") << "' has no scene and no wired geometry surface -- cannot instantiate one for type '" << surfaceType << "'");
      return 0;
    }
    if (surfaceType == "Bezier")
    {
      surface = vtkMRMLBezierSurfaceNode::SafeDownCast(scene->AddNewNodeByClass("vtkMRMLBezierSurfaceNode"));
    }
    else if (surfaceType == "NURBS")
    {
      vtkErrorMacro("ReadJson: 'NURBS' surface type encountered in '" << filePath << "' but the NurbsSurfaceNode class is not registered in the scene (v2.1 feature)");
      return 0;
    }
    else
    {
      vtkErrorMacro("ReadJson: unknown surface type '" << surfaceType << "' in '" << filePath << "'");
      return 0;
    }
    if (surface == nullptr)
    {
      vtkErrorMacro("ReadJson: failed to instantiate surface of type '" << surfaceType << "' for plan '" << (plan->GetName() ? plan->GetName() : "<unnamed>") << "'");
      return 0;
    }
    plan->SetAndObserveGeometryNode(surface);
  }

  // Populate the surface.  The Bezier subclass needs its state-machine
  // guard bypassed for the duration of the read; the ScopedLoadingFromXML
  // RAII handles that.  The cast may yield null for a non-Bezier
  // surface (NURBS in v2.1) -- the guard is a no-op in that case.
  vtkMRMLBezierSurfaceNode* bezier = vtkMRMLBezierSurfaceNode::SafeDownCast(surface);
  ScopedLoadingFromXML loadingGuard(bezier);

  // Shape first -- SetSize re-sizes the control-grid buffer.
  unsigned int rows = surface->GetRows();
  unsigned int cols = surface->GetCols();
  if (surfaceJson->HasMember("rows"))
  {
    rows = static_cast<unsigned int>(surfaceJson->GetIntProperty("rows"));
  }
  if (surfaceJson->HasMember("cols"))
  {
    cols = static_cast<unsigned int>(surfaceJson->GetIntProperty("cols"));
  }
  if (rows != cols || static_cast<int>(rows) < vtkMRMLAbstractParametricSurfaceNode::MinGridSize || static_cast<int>(rows) > vtkMRMLAbstractParametricSurfaceNode::MaxGridSize)
  {
    vtkErrorMacro("ReadJson: invalid surface shape (rows=" << rows << ", cols=" << cols << ") in '" << filePath << "' -- ADR-0018 §1 admits {(3,3), (4,4)} only");
    return 0;
  }
  surface->SetSize(rows);

  // initMode -- enum string converter.
  if (surfaceJson->HasMember("initMode"))
  {
    const std::string s = surfaceJson->GetStringProperty("initMode");
    const int code = vtkMRMLAbstractParametricSurfaceNode::GetInitModeFromString(s.c_str());
    if (code >= 0)
    {
      surface->SetInitMode(code);
    }
  }

  // controlGrid -- 3 * rows * cols doubles row-major.
  if (surfaceJson->HasMember("controlGrid"))
  {
    const unsigned int expected = surface->GetControlGridLength();
    double grid[vtkMRMLAbstractParametricSurfaceNode::MaxControlGridSize];
    if (!surfaceJson->GetVectorProperty("controlGrid", grid, static_cast<int>(expected)))
    {
      vtkErrorMacro("ReadJson: 'controlGrid' must be an array of " << expected << " doubles (3 * rows * cols) in '" << filePath << "'");
      return 0;
    }
    surface->SetControlGrid(grid);
  }

  // slicingPlane subordinate.
  if (surfaceJson->HasMember("slicingPlane"))
  {
    vtkSmartPointer<vtkMRMLJsonElement> sp = vtkSmartPointer<vtkMRMLJsonElement>::Take(surfaceJson->GetObjectProperty("slicingPlane"));
    if (sp != nullptr)
    {
      double v[3];
      if (sp->GetVectorProperty("origin", v, 3))
      {
        surface->SetSlicingPlaneOrigin(v);
      }
      if (sp->GetVectorProperty("normal", v, 3))
      {
        surface->SetSlicingPlaneNormal(v);
      }
      double initFlat[6];
      if (sp->GetVectorProperty("initPointsFlat", initFlat, 6))
      {
        double p0[3] = { initFlat[0], initFlat[1], initFlat[2] };
        double p1[3] = { initFlat[3], initFlat[4], initFlat[5] };
        surface->SetSlicingPlaneInitPoint(0, p0);
        surface->SetSlicingPlaneInitPoint(1, p1);
      }
    }
  }

  // distanceSpheroid subordinate.
  if (surfaceJson->HasMember("distanceSpheroid"))
  {
    vtkSmartPointer<vtkMRMLJsonElement> ds = vtkSmartPointer<vtkMRMLJsonElement>::Take(surfaceJson->GetObjectProperty("distanceSpheroid"));
    if (ds != nullptr)
    {
      double v[3];
      if (ds->GetVectorProperty("center", v, 3))
      {
        surface->SetDistanceSpheroidCenter(v);
      }
      vtkSmartPointer<vtkMRMLJsonElement> rad = vtkSmartPointer<vtkMRMLJsonElement>::Take(ds->GetObjectProperty("radius"));
      if (rad != nullptr)
      {
        double r = 0.0;
        if (rad->GetDoubleProperty("x", r))
        {
          surface->SetDistanceSpheroidRadiusX(r);
        }
        if (rad->GetDoubleProperty("y", r))
        {
          surface->SetDistanceSpheroidRadiusY(r);
        }
        if (rad->GetDoubleProperty("z", r))
        {
          surface->SetDistanceSpheroidRadiusZ(r);
        }
      }
      int nPoints = 0;
      if (ds->HasMember("numberOfInitPoints"))
      {
        nPoints = ds->GetIntProperty("numberOfInitPoints");
      }
      if (nPoints > 0)
      {
        surface->SetNumberOfDistanceSpheroidInitPoints(nPoints);
        std::vector<double> flat(static_cast<size_t>(nPoints) * 3, 0.0);
        if (ds->GetVectorProperty("initPointsFlat", flat.data(), nPoints * 3))
        {
          for (int i = 0; i < nPoints; ++i)
          {
            double p[3] = { flat[static_cast<size_t>(i) * 3 + 0], flat[static_cast<size_t>(i) * 3 + 1], flat[static_cast<size_t>(i) * 3 + 2] };
            surface->SetDistanceSpheroidInitPoint(i, p);
          }
        }
      }
    }
  }

  // The surface picks up its standard display node through Slicer's
  // usual CreateDefaultDisplayNodes path -- triggered by the caller
  // (qSlicerLiverResectionsReader, or whoever drives the load).  The
  // storage node does not synthesise display nodes itself.
  return 1;
}

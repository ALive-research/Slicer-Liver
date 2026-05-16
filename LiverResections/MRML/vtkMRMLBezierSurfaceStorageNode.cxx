/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Redistribution and use in source and binary forms, with or without
  modification, are permitted provided that the following conditions
  are met:

  * Redistributions of source code must retain the above copyright
    notice, this list of conditions and the following disclaimer.

  * Redistributions in binary form must reproduce the above copyright
    notice, this list of conditions and the following disclaimer in the
    documentation and/or other materials provided with the distribution.

  * Neither the name of Oslo University Hospital nor the names
    of Contributors may be used to endorse or promote products derived
    from this software without specific prior written permission.

  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
  "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
  A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
  HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
  SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
  LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
  DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
  THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

  This file was originally developed for the Slicer-Liver extension
  as part of task T2.5 of the v2.0.0 release (LiverResources all-in
  migration; see ADR-0014 §5).

==============================================================================*/

//==============================================================================
// .lrp.json — JSON schema v1
//==============================================================================
//
// One ``.lrp.json`` document per liver resection plan (surgeon-to-
// surgeon plan sharing per ADR-0014 §5).  The current ``schemaVersion``
// is ``1`` — bump in lock-step with any documented extension; the
// reader emits a vtkErrorMacro on unknown versions.
//
//   {
//     "schemaVersion": 1,
//     "state": "Init" | "Planning",
//     "initMode": "SlicingPlane" | "DistanceSpheroid",
//     "controlGrid": [48 doubles in row-major (i, j, k) order],
//     "slicingPlane": {
//       "origin": [3 doubles, RAS],
//       "normal": [3 doubles, RAS],
//       "initPointsFlat": [6 doubles — 2 RAS triplets concat]
//     },
//     "distanceSpheroid": {
//       "center": [3 doubles, RAS],
//       "radius": {"x": double, "y": double, "z": double},
//       "numberOfInitPoints": int,
//       "initPointsFlat": [3*N doubles — N RAS triplets concat]
//     },
//     "metadata": {}
//   }
//
// The ``initPointsFlat`` fields use a flat layout because the
// in-tree ``vtkMRMLJsonWriter`` lacks a key-less nested-array entry
// point.  See the implementation of ``WriteJson`` below for the
// rationale and a ``TODO(T2.5 lrp-json-v2-nested-init-points)``
// marker.
//
// The ``metadata`` object is intentionally empty in v1 and reserved
// for v2's "richer metadata" allowance (timestamps, surgeon ID, …)
// per ADR-0014 §5.
//
//==============================================================================
// Legacy ``.lrp.fcsv`` migration (load-only)
//==============================================================================
//
// The pre-LayerDM ``vtkMRMLLiverResectionCSVStorageNode`` wrote the
// Bezier control points as a standard Slicer markups-fiducial CSV
// (15 columns: id,x,y,z,ow,ox,oy,oz,vis,sel,lock,label,desc,
// associatedNodeID,…).  Header lines start with ``#``.  No state,
// init-mode, plane or spheroid metadata is recorded in the CSV.
//
// Legacy-to-new field mapping
// ----------------------------
//
//   - Legacy 16 Bezier control points (lines, in file order)
//        → new ``controlGrid`` (48 doubles, row-major).  The legacy
//          format is point-major (one full xyz triplet per row); the
//          new format flattens those same 16 triplets row-major into
//          48 doubles, which matches the in-memory representation of
//          ``vtkMRMLBezierSurfaceNode::ControlGrid``.  No re-ordering
//          is needed because both formats walk the (i, j) grid in the
//          same order.
//   - Legacy ``ResectionMargin``, ``UncertaintyMargin``
//        → DROPPED.  These are display-side fields per ADR-0013 §8
//          (display-node split — the new geometry/decoration split
//          carries margins on ``vtkMRMLBezierSurfaceDisplayNode``).
//          They were never serialised by ``vtkMRMLLiverResectionCSVStorageNode``
//          anyway — the CSV only contains the geometry.  Listed here
//          for completeness because the *XML* serialisation of
//          ``vtkMRMLLiverResectionNode`` does carry them; a future
//          MRML-scene migration path will re-route them to the
//          display node.
//   - Legacy ``ResectionState`` (``Initialization`` / ``Deformation``
//     / ``Completed``) → new ``State`` (``Init`` / ``Planning``).
//          Not present in the CSV — defaulted to ``Planning`` because
//          a saved legacy file always represented a populated
//          (post-initialisation) Bezier surface.  Mapping documented
//          here for the future XML-scene migration:
//            ``Initialization`` → ``Init``
//            ``Deformation``    → ``Planning``
//            ``Completed``      → ``Planning``
//   - Legacy ``InitializationMode`` (``Flat`` / ``Curved``) → new
//     ``InitMode`` (``SlicingPlane`` / ``DistanceSpheroid``).
//          Not present in the CSV — defaulted to ``SlicingPlane`` with
//          a vtkWarningMacro flagging the gap.  Documented mapping:
//            ``Flat``   → ``SlicingPlane``
//            ``Curved`` → no clean mapping; legacy "Curved" was a
//                          shaped-but-not-yet-spheroidal init that
//                          predates ADR-0014's spheroid commitment.
//                          For scenes that *do* expose this, the
//                          conservative fall-back is ``SlicingPlane``
//                          (the default) with the audit-data fields
//                          left zero-filled.  Surgeons will need to
//                          re-derive any spheroid parameters by hand.
//   - Init-point / plane / spheroid audit data — none present in
//          legacy CSV.  Fields default-initialise (zeros + the
//          constructor-default ``SlicingPlaneNormal = (0,0,1)``).
//
// ``TODO(T2.7 legacy-scene-migration)`` — wire the legacy-resection-XML
// → new-bezier-node path that consumes the full ``ResectionMargin`` /
// ``UncertaintyMargin`` / state / mode columns from
// ``vtkMRMLLiverResectionNode::ReadXMLAttributes``.  That migration
// lives on the legacy-retirement task, not this storage node.
//==============================================================================

// This module MRML includes
#include "vtkMRMLBezierSurfaceStorageNode.h"
#include "vtkMRMLBezierSurfaceNode.h"

// MRML includes
#include <vtkMRMLJsonElement.h>
#include <vtkMRMLMessageCollection.h>
#include <vtkMRMLStorageNode.h>

// VTK includes
#include <vtkNew.h>
#include <vtkObjectFactory.h>
#include <vtkSmartPointer.h>
#include <vtkStringArray.h>
#include <vtksys/SystemTools.hxx>

// STD includes
#include <algorithm>
#include <array>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

//------------------------------------------------------------------------------
vtkMRMLNodeNewMacro(vtkMRMLBezierSurfaceStorageNode);

//------------------------------------------------------------------------------
vtkMRMLBezierSurfaceStorageNode::vtkMRMLBezierSurfaceStorageNode()
{
  this->DefaultWriteFileExtension = "lrp.json";
}

//------------------------------------------------------------------------------
vtkMRMLBezierSurfaceStorageNode::~vtkMRMLBezierSurfaceStorageNode() = default;

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceStorageNode::PrintSelf(ostream& os, vtkIndent indent)
{
  Superclass::PrintSelf(os, indent);
  os << indent << "SchemaVersion: " << SchemaVersion << "\n";
}

//------------------------------------------------------------------------------
bool vtkMRMLBezierSurfaceStorageNode::CanReadInReferenceNode(vtkMRMLNode* refNode)
{
  return refNode != nullptr && refNode->IsA("vtkMRMLBezierSurfaceNode");
}

//------------------------------------------------------------------------------
bool vtkMRMLBezierSurfaceStorageNode::CanWriteFromReferenceNode(vtkMRMLNode* refNode)
{
  return refNode != nullptr && refNode->IsA("vtkMRMLBezierSurfaceNode");
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceStorageNode::InitializeSupportedReadFileTypes()
{
  // New format first — the file dialog defaults to the first entry.
  this->SupportedReadFileTypes->InsertNextValue("Liver resection plan (.lrp.json)");
  // Legacy CSV — load-only per ADR-0014 §5 (one-way migration).
  this->SupportedReadFileTypes->InsertNextValue("Legacy liver resection plan (.lrp.fcsv)");
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceStorageNode::InitializeSupportedWriteFileTypes()
{
  // ``.lrp.json`` only — legacy writes are explicitly not supported
  // per ADR-0014 §5.  ADR-0007 D-class compatibility break: part of
  // the v2.0.0 MAJOR-bump triggers.
  this->SupportedWriteFileTypes->InsertNextValue("Liver resection plan (.lrp.json)");
}

//------------------------------------------------------------------------------
namespace
{
/// Lowercase an ASCII string in place.  Used to canonicalise the
/// file extension before dispatch.  ``vtksys::SystemTools`` provides
/// ``LowerCase`` but the typed version below keeps the include
/// surface narrower in this file.
std::string toLower(std::string s)
{
  std::transform(s.begin(), s.end(), s.begin(), [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
  return s;
}

/// Return true iff the full path ends with the lower-cased suffix.
/// Used to dispatch ``.lrp.json`` vs ``.lrp.fcsv`` — they share the
/// ``.lrp`` first-half so a plain
/// ``GetLowercaseExtensionFromFileName`` does not distinguish them.
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
int vtkMRMLBezierSurfaceStorageNode::ReadDataInternal(vtkMRMLNode* refNode)
{
  if (refNode == nullptr)
  {
    vtkErrorMacro("ReadDataInternal: null reference node");
    return 0;
  }
  auto* surfaceNode = vtkMRMLBezierSurfaceNode::SafeDownCast(refNode);
  if (surfaceNode == nullptr)
  {
    vtkErrorMacro("ReadDataInternal: reference node is not a vtkMRMLBezierSurfaceNode (got '" << refNode->GetClassName() << "')");
    return 0;
  }

  const std::string fullName = this->GetFullNameFromFileName();
  if (fullName.empty())
  {
    vtkErrorMacro("ReadDataInternal: file name not specified");
    return 0;
  }

  // Dispatch on the file extension.  Both ``.lrp.json`` and
  // ``.lrp.fcsv`` are accepted on read (legacy load-only migration
  // per ADR-0014 §5).  ``.json`` alone is *not* accepted — the
  // ``.lrp`` prefix discriminates Liver resection plans from any
  // other JSON file someone might point the storage node at.
  if (endsWithLower(fullName, ".lrp.json"))
  {
    return this->ReadJson(fullName, surfaceNode);
  }
  if (endsWithLower(fullName, ".lrp.fcsv"))
  {
    return this->ReadLegacyFcsv(fullName, surfaceNode);
  }
  vtkErrorMacro("ReadDataInternal: unsupported file extension for '" << fullName << "' (expected .lrp.json or .lrp.fcsv)");
  return 0;
}

//------------------------------------------------------------------------------
int vtkMRMLBezierSurfaceStorageNode::WriteDataInternal(vtkMRMLNode* refNode)
{
  if (refNode == nullptr)
  {
    vtkErrorMacro("WriteDataInternal: null reference node");
    return 0;
  }
  auto* surfaceNode = vtkMRMLBezierSurfaceNode::SafeDownCast(refNode);
  if (surfaceNode == nullptr)
  {
    vtkErrorMacro("WriteDataInternal: reference node is not a vtkMRMLBezierSurfaceNode (got '" << refNode->GetClassName() << "')");
    return 0;
  }

  const std::string fullName = this->GetFullNameFromFileName();
  if (fullName.empty())
  {
    vtkErrorMacro("WriteDataInternal: file name not specified");
    return 0;
  }

  // Legacy writes are not supported per ADR-0014 §5.  A caller who
  // sets a ``.lrp.fcsv`` storage filename gets an explicit error
  // rather than a silent fall-through to the JSON path with the
  // wrong extension on disk.
  if (endsWithLower(fullName, ".lrp.fcsv"))
  {
    vtkErrorMacro("WriteDataInternal: writing the legacy .lrp.fcsv format is not supported"
                  " (ADR-0014 §5 — load-only migration); save as .lrp.json instead.");
    return 0;
  }
  // Be permissive on the JSON extension — accept either ``.lrp.json``
  // or no recognised extension at all (the latter happens when the
  // caller sets a bare file name and relies on
  // ``DefaultWriteFileExtension``).  Anything that ends ``.json``
  // routes through the new format.
  if (!endsWithLower(fullName, ".lrp.json") && !endsWithLower(fullName, ".json"))
  {
    vtkErrorMacro("WriteDataInternal: unsupported file extension for '" << fullName << "' (expected .lrp.json)");
    return 0;
  }
  return this->WriteJson(fullName, surfaceNode);
}

//------------------------------------------------------------------------------
int vtkMRMLBezierSurfaceStorageNode::WriteJson(const std::string& filePath, vtkMRMLBezierSurfaceNode* surfaceNode)
{
  vtkNew<vtkMRMLJsonWriter> writer;
  // ``WriteToFileBegin`` writes the opening ``{`` and an optional
  // top-level ``@schema`` key when ``schema != nullptr``.  We pass
  // nullptr because the legacy storage nodes in this module did not
  // use a schema URL and there is no public JSON-Schema document for
  // the ``.lrp.json`` format yet (the schema lives in this source
  // file and is governed by the ``SchemaVersion`` integer).
  if (!writer->WriteToFileBegin(filePath.c_str(), nullptr))
  {
    vtkErrorMacro("WriteJson: failed to open '" << filePath << "' for writing");
    return 0;
  }

  writer->WriteIntProperty("schemaVersion", SchemaVersion);
  writer->WriteStringProperty("state", vtkMRMLBezierSurfaceNode::GetStateAsString(surfaceNode->GetState()));
  writer->WriteStringProperty("initMode", vtkMRMLBezierSurfaceNode::GetInitModeAsString(surfaceNode->GetInitMode()));

  // controlGrid — 48 doubles row-major.  ``const_cast`` is necessary
  // because the writer signature takes ``double*`` (it does not
  // mutate; the rapidjson backend treats the buffer as input).
  writer->WriteVectorProperty("controlGrid", const_cast<double*>(surfaceNode->GetControlGrid()), vtkMRMLBezierSurfaceNode::ControlGridSize);

  // slicingPlane sub-object.
  writer->WriteObjectPropertyStart("slicingPlane");
  {
    double v[3];
    surfaceNode->GetSlicingPlaneOrigin(v);
    writer->WriteVectorProperty("origin", v, 3);
    surfaceNode->GetSlicingPlaneNormal(v);
    writer->WriteVectorProperty("normal", v, 3);

    // Flatten the 2 init points to a single 6-double array.  This
    // is a deliberate schema-v1 choice — the conceptual JSON shape
    // is ``[[3 doubles], [3 doubles]]`` but the in-tree
    // ``vtkMRMLJsonWriter`` does not expose a key-less nested-array
    // entry point.  A 6-double flat array is unambiguous given the
    // fixed 2-point SlicingPlane shape (ADR-0014 §1).
    // ``TODO(T2.5 lrp-json-v2-nested-init-points)`` — if the schema
    // ever needs the nested shape, either land a
    // ``WriteArrayItemVector`` helper on ``vtkMRMLJsonWriter`` or
    // drop down to rapidjson directly.
    double initPointsFlat[6];
    for (int i = 0; i < 2; ++i)
    {
      const double* p = surfaceNode->GetSlicingPlaneInitPoint(i);
      initPointsFlat[i * 3 + 0] = p[0];
      initPointsFlat[i * 3 + 1] = p[1];
      initPointsFlat[i * 3 + 2] = p[2];
    }
    writer->WriteVectorProperty("initPointsFlat", initPointsFlat, 6);
  }
  writer->WriteObjectPropertyEnd();

  // distanceSpheroid sub-object.
  writer->WriteObjectPropertyStart("distanceSpheroid");
  {
    double v[3];
    surfaceNode->GetDistanceSpheroidCenter(v);
    writer->WriteVectorProperty("center", v, 3);

    writer->WriteObjectPropertyStart("radius");
    writer->WriteDoubleProperty("x", surfaceNode->GetDistanceSpheroidRadiusX());
    writer->WriteDoubleProperty("y", surfaceNode->GetDistanceSpheroidRadiusY());
    writer->WriteDoubleProperty("z", surfaceNode->GetDistanceSpheroidRadiusZ());
    writer->WriteObjectPropertyEnd();

    // Flatten the variable number of init points to a single
    // 3N-double array for the same reason as the slicingPlane
    // initPoints above.
    const int nPoints = surfaceNode->GetNumberOfDistanceSpheroidInitPoints();
    writer->WriteIntProperty("numberOfInitPoints", nPoints);
    if (nPoints > 0)
    {
      std::vector<double> flat(static_cast<size_t>(nPoints) * 3, 0.0);
      for (int i = 0; i < nPoints; ++i)
      {
        const double* p = surfaceNode->GetDistanceSpheroidInitPoint(i);
        flat[static_cast<size_t>(i) * 3 + 0] = p[0];
        flat[static_cast<size_t>(i) * 3 + 1] = p[1];
        flat[static_cast<size_t>(i) * 3 + 2] = p[2];
      }
      writer->WriteVectorProperty("initPointsFlat", flat.data(), static_cast<int>(flat.size()));
    }
    else
    {
      // Emit an empty array so the reader can detect "explicitly
      // empty" vs "key missing" — rapidjson treats both the same
      // semantically but downstream consumers (e.g. JSON-Schema
      // validators) may not.
      std::array<double, 1> sentinel = { 0.0 };
      (void)sentinel; // unused — see below
      writer->WriteArrayPropertyStart("initPointsFlat");
      writer->WriteArrayPropertyEnd();
    }
  }
  writer->WriteObjectPropertyEnd();

  // metadata — reserved for v2 per ADR-0014 §5.  Emit an empty
  // object so the field is unambiguously "present and empty"
  // rather than absent.
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
int vtkMRMLBezierSurfaceStorageNode::ReadJson(const std::string& filePath, vtkMRMLBezierSurfaceNode* surfaceNode)
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
  if (schemaVersion != SchemaVersion)
  {
    vtkErrorMacro("ReadJson: unsupported schemaVersion " << schemaVersion << " in '" << filePath << "' (this build understands schemaVersion " << SchemaVersion << " only)");
    return 0;
  }

  // State is read LAST — before that, the init-mode subordinate
  // data setters (slicingPlane.*, distanceSpheroid.*) are guarded
  // against post-Planning mutation by the ADR-0014 §4 read-only
  // invariant.  Parsing into a node already-in-Planning would
  // silently drop those fields.  Read into ``pendingState`` here,
  // populate the audit fields, then commit the transition at the
  // end of this method.
  int pendingState = -1;
  if (root->HasMember("state"))
  {
    const std::string s = root->GetStringProperty("state");
    const int code = vtkMRMLBezierSurfaceNode::GetStateFromString(s.c_str());
    if (code < 0)
    {
      vtkErrorMacro("ReadJson: unknown state name '" << s << "' in '" << filePath << "'");
      return 0;
    }
    pendingState = code;
  }
  if (root->HasMember("initMode"))
  {
    const std::string s = root->GetStringProperty("initMode");
    const int code = vtkMRMLBezierSurfaceNode::GetInitModeFromString(s.c_str());
    if (code < 0)
    {
      vtkErrorMacro("ReadJson: unknown initMode name '" << s << "' in '" << filePath << "'");
      return 0;
    }
    surfaceNode->SetInitMode(code);
  }

  // controlGrid — 48 doubles row-major.
  if (root->HasMember("controlGrid"))
  {
    double grid[vtkMRMLBezierSurfaceNode::ControlGridSize];
    if (!root->GetVectorProperty("controlGrid", grid, vtkMRMLBezierSurfaceNode::ControlGridSize))
    {
      vtkErrorMacro("ReadJson: 'controlGrid' must be an array of " << vtkMRMLBezierSurfaceNode::ControlGridSize << " doubles in '" << filePath << "'");
      return 0;
    }
    surfaceNode->SetControlGrid(grid);
  }

  // slicingPlane sub-object.
  if (root->HasMember("slicingPlane"))
  {
    vtkSmartPointer<vtkMRMLJsonElement> sp = vtkSmartPointer<vtkMRMLJsonElement>::Take(root->GetObjectProperty("slicingPlane"));
    if (sp != nullptr)
    {
      double v[3];
      if (sp->GetVectorProperty("origin", v, 3))
      {
        surfaceNode->SetSlicingPlaneOrigin(v);
      }
      if (sp->GetVectorProperty("normal", v, 3))
      {
        surfaceNode->SetSlicingPlaneNormal(v);
      }
      double initFlat[6];
      if (sp->GetVectorProperty("initPointsFlat", initFlat, 6))
      {
        double p0[3] = { initFlat[0], initFlat[1], initFlat[2] };
        double p1[3] = { initFlat[3], initFlat[4], initFlat[5] };
        surfaceNode->SetSlicingPlaneInitPoint(0, p0);
        surfaceNode->SetSlicingPlaneInitPoint(1, p1);
      }
    }
  }

  // distanceSpheroid sub-object.
  if (root->HasMember("distanceSpheroid"))
  {
    vtkSmartPointer<vtkMRMLJsonElement> ds = vtkSmartPointer<vtkMRMLJsonElement>::Take(root->GetObjectProperty("distanceSpheroid"));
    if (ds != nullptr)
    {
      double v[3];
      if (ds->GetVectorProperty("center", v, 3))
      {
        surfaceNode->SetDistanceSpheroidCenter(v);
      }
      vtkSmartPointer<vtkMRMLJsonElement> rad = vtkSmartPointer<vtkMRMLJsonElement>::Take(ds->GetObjectProperty("radius"));
      if (rad != nullptr)
      {
        double r = 0.0;
        if (rad->GetDoubleProperty("x", r))
        {
          surfaceNode->SetDistanceSpheroidRadiusX(r);
        }
        if (rad->GetDoubleProperty("y", r))
        {
          surfaceNode->SetDistanceSpheroidRadiusY(r);
        }
        if (rad->GetDoubleProperty("z", r))
        {
          surfaceNode->SetDistanceSpheroidRadiusZ(r);
        }
      }
      const int nPoints = ds->GetIntProperty("numberOfInitPoints");
      if (nPoints > 0)
      {
        surfaceNode->SetNumberOfDistanceSpheroidInitPoints(nPoints);
        std::vector<double> flat(static_cast<size_t>(nPoints) * 3, 0.0);
        if (ds->GetVectorProperty("initPointsFlat", flat.data(), nPoints * 3))
        {
          for (int i = 0; i < nPoints; ++i)
          {
            double p[3] = { flat[static_cast<size_t>(i) * 3 + 0], flat[static_cast<size_t>(i) * 3 + 1], flat[static_cast<size_t>(i) * 3 + 2] };
            surfaceNode->SetDistanceSpheroidInitPoint(i, p);
          }
        }
      }
    }
  }

  // Commit the state transition last so the init-mode subordinate
  // setters above did not have to fight the ADR-0014 §4 read-only
  // guard.  See the pendingState block at the top of this method.
  if (pendingState >= 0)
  {
    surfaceNode->SetState(pendingState);
  }
  return 1;
}

//------------------------------------------------------------------------------
int vtkMRMLBezierSurfaceStorageNode::ReadLegacyFcsv(const std::string& filePath, vtkMRMLBezierSurfaceNode* surfaceNode)
{
  // Open the file directly — we deliberately do NOT delegate to
  // ``vtkMRMLMarkupsFiducialStorageNode`` because pulling a markups
  // node into existence just to read 16 control points adds a
  // dependency on the Markups module's scene infrastructure for no
  // payoff.  The legacy CSV is a plain RFC-4180-shaped file with
  // header lines starting ``#``; we only need the numeric x/y/z
  // columns.
  std::ifstream stream(filePath);
  if (!stream.is_open())
  {
    vtkErrorMacro("ReadLegacyFcsv: cannot open '" << filePath << "'");
    return 0;
  }

  // Collect (x, y, z) triplets in file order.  The legacy 15-column
  // markups schema places coordinates at fixed columns 1..3 (0-based)
  // — see ``vtkMRMLMarkupsFiducialStorageNode``'s columns header.
  // We tolerate either 14-column or 15-column rows for forward
  // compatibility (the column count drifted across Slicer versions).
  std::vector<std::array<double, 3>> points;
  std::string line;
  while (std::getline(stream, line))
  {
    if (line.empty())
    {
      continue;
    }
    // Skip header / comment lines.
    if (line[0] == '#')
    {
      continue;
    }
    // Tokenise on comma.  The legacy writer always used ``,`` as
    // the field delimiter (see the constructor of
    // ``vtkMRMLLiverResectionCSVStorageNode``).
    std::vector<std::string> tokens;
    std::stringstream ss(line);
    std::string token;
    while (std::getline(ss, token, ','))
    {
      tokens.push_back(token);
    }
    if (tokens.size() < 4)
    {
      // Not a control-point row; skip silently.
      continue;
    }
    try
    {
      const double x = std::stod(tokens[1]);
      const double y = std::stod(tokens[2]);
      const double z = std::stod(tokens[3]);
      points.push_back({ x, y, z });
    }
    catch (const std::exception&)
    {
      // Non-numeric row in coords column — skip silently; the
      // 16-point check at the end is the load-bearing guard.
      continue;
    }
  }

  // ADR-0014 §3 + ADR-0014 §1: a Bezier control grid is 16 points
  // (degree-3 patch).  Reject anything else as malformed.
  constexpr int expectedPointCount = vtkMRMLBezierSurfaceNode::GridSize * vtkMRMLBezierSurfaceNode::GridSize;
  if (static_cast<int>(points.size()) != expectedPointCount)
  {
    vtkErrorMacro("ReadLegacyFcsv: expected " << expectedPointCount << " control points in '" << filePath << "' but found " << points.size());
    return 0;
  }

  // Flatten to the row-major 48-double buffer expected by the
  // surface node's SetControlGrid.  See the file-header comment for
  // the field-mapping rationale.
  std::array<double, vtkMRMLBezierSurfaceNode::ControlGridSize> grid;
  for (int i = 0; i < expectedPointCount; ++i)
  {
    grid[i * 3 + 0] = points[i][0];
    grid[i * 3 + 1] = points[i][1];
    grid[i * 3 + 2] = points[i][2];
  }
  surfaceNode->SetControlGrid(grid.data());

  // State + InitMode: not present in the legacy CSV.  Default to
  // ``Planning`` + ``SlicingPlane`` per the field-mapping table at
  // the top of this file.  A saved-to-disk legacy plan always
  // represented a populated Bezier surface (i.e. post-Initialization),
  // so ``Planning`` is the correct mapping for both
  // ``Deformation`` and ``Completed`` legacy state values.  The
  // ``InitMode`` default exists because the legacy CSV did not
  // discriminate between ``Flat`` and ``Curved`` modes — surgeons
  // who relied on ``Curved`` will need to re-derive any spheroid
  // parameters by hand.
  surfaceNode->SetState(vtkMRMLBezierSurfaceNode::Planning);
  surfaceNode->SetInitMode(vtkMRMLBezierSurfaceNode::SlicingPlane);

  vtkWarningMacro("ReadLegacyFcsv: loaded " << expectedPointCount << " control points from '" << filePath
                                            << "' — state defaulted to Planning, initMode defaulted to SlicingPlane"
                                               " (legacy CSV does not carry these fields; see field-mapping table"
                                               " in vtkMRMLBezierSurfaceStorageNode.cxx). Re-save as .lrp.json to"
                                               " preserve the full field roster going forward.");
  return 1;
}

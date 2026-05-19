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
// .lrp.json — JSON schema v3 (ADR-0022 §"Decision 2 — Schema v3")
//==============================================================================
//
// One ``.lrp.json`` document per liver resection plan (surgeon-to-
// surgeon plan sharing per ADR-0014 §5).  Current writer
// ``schemaVersion`` is ``3`` — bump in lock-step with any documented
// extension; the reader accepts ``MinReadableSchemaVersion``
// (currently ``1``) through ``SchemaVersion`` (currently ``3``).
//
// v3 adds the ``surfaceType`` top-level discriminator and the
// NURBS-specific fields (``degreeU``, ``degreeV``, ``knotsU``,
// ``knotsV``, ``weights``).  Bezier files keep the v2 shape; the
// NURBS path is additive.
//
//   {
//     "schemaVersion": 3,
//     "surfaceType": "Bezier" | "NURBS",  // v3 only; absent → Bezier
//     "state": "Init" | "Planning" | "Confirmed",
//     "initMode": "SlicingPlane" | "DistanceSpheroid",
//     "rows": int,
//     "cols": int,
//     "controlGrid": [3 * rows * cols doubles in row-major (i,j,k) order],
//     // ---- NURBS-only block (only when surfaceType == "NURBS") ----
//     "degreeU": int,                       // 2..3 per ADR-0022
//     "degreeV": int,                       // 2..3 per ADR-0022
//     "knotsU": [rows + degreeU + 1 doubles, non-decreasing, clamped],
//     "knotsV": [cols + degreeV + 1 doubles, non-decreasing, clamped],
//     "weights": [rows * cols doubles, all strictly positive],
//     // ---- Bezier-only init-mode block (Bezier surfaces only) ----
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
// v1 → v2 → v3 reader-compat matrix (ADR-0022 §"Reader compat
// matrix"):
//   - v1 (no ``rows``/``cols``/``surfaceType``) → implicit 4×4 Bezier.
//   - v2 (``rows``+``cols``, no ``surfaceType``) → explicit Bezier
//     with declared shape.
//   - v3 + ``surfaceType == "Bezier"`` → Bezier path with the
//     discriminator made explicit.
//   - v3 + ``surfaceType == "NURBS"`` → full NURBS path; degrees +
//     knots + weights consumed and validated.
//
// Validation per surface type (ADR-0022 §"Validation rules per
// surface type"):
//   - Bezier: ``(rows, cols) ∈ {(3, 3), (4, 4)}`` per ADR-0018 §1;
//     ``len(controlGrid) == 3 * rows * cols``.
//   - NURBS: ``2 ≤ degreeU, degreeV ≤ 3``; ``rows ≥ degreeU + 1``,
//     ``cols ≥ degreeV + 1``; ``len(knotsU) == rows + degreeU + 1``,
//     ``len(knotsV) == cols + degreeV + 1``; ``len(weights) ==
//     rows * cols``, every weight > 0; ``len(controlGrid) == 3 *
//     rows * cols``.
//
// The writer always emits v3 + the most-specific ``surfaceType`` +
// the minimum redundant fields.  A v1 or v2 file round-tripped
// through load + save becomes v3 on disk.
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
#include "vtkMRMLNurbsSurfaceNode.h"

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
  // Per ADR-0022 §"Decision 2 — Schema v3" the storage node serves
  // both Bezier and NURBS data nodes — the on-disk ``surfaceType``
  // discriminator picks the read path inside ``ReadDataInternal``.
  return refNode != nullptr && (refNode->IsA("vtkMRMLBezierSurfaceNode") || refNode->IsA("vtkMRMLNurbsSurfaceNode"));
}

//------------------------------------------------------------------------------
bool vtkMRMLBezierSurfaceStorageNode::CanWriteFromReferenceNode(vtkMRMLNode* refNode)
{
  return refNode != nullptr && (refNode->IsA("vtkMRMLBezierSurfaceNode") || refNode->IsA("vtkMRMLNurbsSurfaceNode"));
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
  auto* bezierNode = vtkMRMLBezierSurfaceNode::SafeDownCast(refNode);
  auto* nurbsNode = vtkMRMLNurbsSurfaceNode::SafeDownCast(refNode);
  if (bezierNode == nullptr && nurbsNode == nullptr)
  {
    vtkErrorMacro("ReadDataInternal: reference node is neither vtkMRMLBezierSurfaceNode nor vtkMRMLNurbsSurfaceNode (got '" << refNode->GetClassName() << "')");
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
  // per ADR-0014 §5).  Legacy ``.lrp.fcsv`` carries Bezier control
  // points only; it predates the NURBS sibling so a NURBS reference
  // node + ``.lrp.fcsv`` is a configuration error.
  if (endsWithLower(fullName, ".lrp.json"))
  {
    if (nurbsNode != nullptr)
    {
      return this->ReadJsonNurbs(fullName, nurbsNode);
    }
    return this->ReadJsonBezier(fullName, bezierNode);
  }
  if (endsWithLower(fullName, ".lrp.fcsv"))
  {
    if (nurbsNode != nullptr)
    {
      vtkErrorMacro("ReadDataInternal: legacy .lrp.fcsv is Bezier-only; cannot load into a vtkMRMLNurbsSurfaceNode ('" << fullName << "')");
      return 0;
    }
    return this->ReadLegacyFcsv(fullName, bezierNode);
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
  auto* bezierNode = vtkMRMLBezierSurfaceNode::SafeDownCast(refNode);
  auto* nurbsNode = vtkMRMLNurbsSurfaceNode::SafeDownCast(refNode);
  if (bezierNode == nullptr && nurbsNode == nullptr)
  {
    vtkErrorMacro("WriteDataInternal: reference node is neither vtkMRMLBezierSurfaceNode nor vtkMRMLNurbsSurfaceNode (got '" << refNode->GetClassName() << "')");
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
  if (nurbsNode != nullptr)
  {
    return this->WriteJsonNurbs(fullName, nurbsNode);
  }
  return this->WriteJsonBezier(fullName, bezierNode);
}

//------------------------------------------------------------------------------
int vtkMRMLBezierSurfaceStorageNode::WriteJsonBezier(const std::string& filePath, vtkMRMLBezierSurfaceNode* surfaceNode)
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
    vtkErrorMacro("WriteJsonBezier: failed to open '" << filePath << "' for writing");
    return 0;
  }

  writer->WriteIntProperty("schemaVersion", SchemaVersion);
  // schemaVersion 3 adds an explicit ``surfaceType`` discriminator
  // per ADR-0022 §"Decision 2 — Schema v3".  Bezier writes never
  // include the NURBS-only fields (``degreeU`` / ``degreeV`` /
  // ``knotsU`` / ``knotsV`` / ``weights``) — those are meaningless
  // for the Bernstein basis.
  writer->WriteStringProperty("surfaceType", "Bezier");
  writer->WriteStringProperty("state", vtkMRMLBezierSurfaceNode::GetStateAsString(surfaceNode->GetState()));
  writer->WriteStringProperty("initMode", vtkMRMLBezierSurfaceNode::GetInitModeAsString(surfaceNode->GetInitMode()));

  // rows + cols — explicit Bezier shape (ADR-0018 §1).
  writer->WriteIntProperty("rows", static_cast<int>(surfaceNode->GetRows()));
  writer->WriteIntProperty("cols", static_cast<int>(surfaceNode->GetCols()));

  // controlGrid — 3 * rows * cols doubles row-major.  ``const_cast``
  // is necessary because the writer signature takes ``double*`` (it
  // does not mutate; the rapidjson backend treats the buffer as
  // input).
  writer->WriteVectorProperty("controlGrid", const_cast<double*>(surfaceNode->GetControlGrid()), static_cast<int>(surfaceNode->GetControlGridLength()));

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
namespace
{
// RAII guard: flip the surface node's ``LoadingFromXML`` flag on for
// the duration of a JSON read, restore it on scope exit (covers early
// returns too).  Mirrors the wrap pattern used in
// ``vtkMRMLBezierSurfaceNode::ReadXMLAttributes`` so JSON deserialisation
// bypasses the ADR-0014 §4 audit-data setters' read-only guards and
// the ADR-0019 ``SetState`` transition matrix the same way XML loads
// do.  Without the bypass a Confirmed-state round-trip fails: the
// fresh sink starts at ``Init`` and ``SetState(Confirmed)`` is
// rejected as an illegal Init→Confirmed transition (the legal path
// is Init→Planning→Confirmed).
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

int vtkMRMLBezierSurfaceStorageNode::ReadJsonBezier(const std::string& filePath, vtkMRMLBezierSurfaceNode* surfaceNode)
{
  ScopedLoadingFromXML loadingGuard(surfaceNode);

  vtkNew<vtkMRMLJsonReader> reader;
  vtkSmartPointer<vtkMRMLJsonElement> root = vtkSmartPointer<vtkMRMLJsonElement>::Take(reader->ReadFromFile(filePath.c_str()));
  if (root == nullptr)
  {
    vtkErrorMacro("ReadJsonBezier: failed to parse '" << filePath << "'");
    return 0;
  }
  if (!root->HasMember("schemaVersion"))
  {
    vtkErrorMacro("ReadJsonBezier: missing required 'schemaVersion' field in '" << filePath << "'");
    return 0;
  }
  const int schemaVersion = root->GetIntProperty("schemaVersion");
  if (schemaVersion < MinReadableSchemaVersion || schemaVersion > SchemaVersion)
  {
    vtkErrorMacro("ReadJsonBezier: unsupported schemaVersion " << schemaVersion << " in '" << filePath << "' (this build understands schemaVersion " << MinReadableSchemaVersion
                                                               << " through " << SchemaVersion << ")");
    return 0;
  }
  // v3 carries an explicit ``surfaceType`` discriminator.  If the
  // file declares NURBS but the reference node is a Bezier node, the
  // caller pointed the wrong storage path at the file — error out
  // rather than silently misinterpreting the data.
  if (schemaVersion >= 3 && root->HasMember("surfaceType"))
  {
    const std::string declared = root->GetStringProperty("surfaceType");
    if (declared != "Bezier")
    {
      vtkErrorMacro("ReadJsonBezier: file declares surfaceType='" << declared << "' but reference node is a vtkMRMLBezierSurfaceNode in '" << filePath << "'");
      return 0;
    }
  }

  // Control-polygon shape (ADR-0018 §1).  v2 files carry explicit
  // ``rows`` + ``cols``; v1 files have neither and the shape is
  // implicit-4×4.  Resolve both schemas to a (rows, cols) pair, then
  // apply via SetSize after validating square + admitted-size.
  unsigned int rows = vtkMRMLBezierSurfaceNode::DefaultGridSize;
  unsigned int cols = vtkMRMLBezierSurfaceNode::DefaultGridSize;
  if (schemaVersion >= 2)
  {
    if (!root->HasMember("rows") || !root->HasMember("cols"))
    {
      vtkErrorMacro("ReadJsonBezier: schemaVersion " << schemaVersion << " requires 'rows' and 'cols' fields in '" << filePath << "'");
      return 0;
    }
    rows = static_cast<unsigned int>(root->GetIntProperty("rows"));
    cols = static_cast<unsigned int>(root->GetIntProperty("cols"));
  }
  if (rows != cols || static_cast<int>(rows) < vtkMRMLBezierSurfaceNode::MinGridSize || static_cast<int>(rows) > vtkMRMLBezierSurfaceNode::MaxGridSize)
  {
    vtkErrorMacro("ReadJsonBezier: invalid (rows=" << rows << ", cols=" << cols << ") in '" << filePath << "' — ADR-0018 §1 admits {(3, 3), (4, 4)} only");
    return 0;
  }
  // SetSize zero-fills the control buffer to match the new shape;
  // the controlGrid payload below populates it.
  surfaceNode->SetSize(rows);

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
    int code = vtkMRMLBezierSurfaceNode::GetStateFromString(s.c_str());
    if (code < 0)
    {
      // ADR-0019 §"Storage / persistence": unknown state values fall
      // back to "Planning" gracefully so a scene authored by a future
      // build that adds a fourth state (e.g. "Approved") still opens
      // in older builds with the surface visible and editable.  The
      // fallback also covers the symmetric forward-compat case for the
      // existing readership: a v3-authored "Confirmed" scene loaded by
      // a build that pre-dates this PR would have read as unknown;
      // adding the fallback here means the same loader behaviour ages
      // gracefully into the next schema bump.
      vtkWarningMacro("ReadJsonBezier: unknown state name '" << s << "' in '" << filePath
                                                             << "' — falling back to Planning"
                                                                " (ADR-0019 forward-compatible default)");
      code = vtkMRMLBezierSurfaceNode::Planning;
    }
    pendingState = code;
  }
  if (root->HasMember("initMode"))
  {
    const std::string s = root->GetStringProperty("initMode");
    const int code = vtkMRMLBezierSurfaceNode::GetInitModeFromString(s.c_str());
    if (code < 0)
    {
      vtkErrorMacro("ReadJsonBezier: unknown initMode name '" << s << "' in '" << filePath << "'");
      return 0;
    }
    surfaceNode->SetInitMode(code);
  }

  // controlGrid — 3 * rows * cols doubles row-major.  Stack buffer
  // is sized to the worst admitted case (``MaxControlGridSize``);
  // the live length is bound to ``surfaceNode->GetControlGridLength()``.
  if (root->HasMember("controlGrid"))
  {
    const unsigned int expected = surfaceNode->GetControlGridLength();
    double grid[vtkMRMLBezierSurfaceNode::MaxControlGridSize];
    if (!root->GetVectorProperty("controlGrid", grid, static_cast<int>(expected)))
    {
      vtkErrorMacro("ReadJsonBezier: 'controlGrid' must be an array of " << expected << " doubles (3 * rows * cols) in '" << filePath << "'");
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
// NURBS read / write paths (ADR-0022 §"Decision 2 — Schema v3").
//
// The implementation deliberately mirrors the Bezier paths above
// rather than factoring into a templatized helper.  The two surface
// types share the schema-version + state + initMode + shape blocks
// but diverge on (a) the validation rules (degree range, knot
// lengths, weights positivity for NURBS; ``{(3,3), (4,4)}`` for
// Bezier) and (b) the per-surface-type field roster (no init-mode
// audit data on NURBS in v2.1 per ADR-0022; the slicingPlane /
// distanceSpheroid sub-objects belong to the Bezier path).  A future
// refactor — paired with the ``vtkMRMLParametricSurfaceNode``
// abstract base flagged in ADR-0022 §"Sharing with the Bezier node
// — deliberate non-sharing" — can collapse the common prefix.
//------------------------------------------------------------------------------

namespace
{
/// RAII guard mirroring the Bezier ``ScopedLoadingFromXML`` above but
/// for ``vtkMRMLNurbsSurfaceNode``.  Flips ``LoadingFromXML`` on for
/// the duration of a JSON read so the ADR-0019 transition-matrix
/// guard does not reject a Confirmed-state file loaded into a fresh
/// (Init) sink.
class ScopedNurbsLoadingFromXML
{
public:
  explicit ScopedNurbsLoadingFromXML(vtkMRMLNurbsSurfaceNode* node)
    : Node(node)
    , Prev(node != nullptr ? node->GetLoadingFromXML() : false)
  {
    if (this->Node != nullptr)
    {
      this->Node->SetLoadingFromXML(true);
    }
  }
  ~ScopedNurbsLoadingFromXML()
  {
    if (this->Node != nullptr)
    {
      this->Node->SetLoadingFromXML(this->Prev);
    }
  }
  ScopedNurbsLoadingFromXML(const ScopedNurbsLoadingFromXML&) = delete;
  ScopedNurbsLoadingFromXML& operator=(const ScopedNurbsLoadingFromXML&) = delete;

private:
  vtkMRMLNurbsSurfaceNode* Node;
  bool Prev;
};
} // namespace

int vtkMRMLBezierSurfaceStorageNode::WriteJsonNurbs(const std::string& filePath, vtkMRMLNurbsSurfaceNode* surfaceNode)
{
  vtkNew<vtkMRMLJsonWriter> writer;
  if (!writer->WriteToFileBegin(filePath.c_str(), nullptr))
  {
    vtkErrorMacro("WriteJsonNurbs: failed to open '" << filePath << "' for writing");
    return 0;
  }

  writer->WriteIntProperty("schemaVersion", SchemaVersion);
  writer->WriteStringProperty("surfaceType", "NURBS");
  writer->WriteStringProperty("state", vtkMRMLNurbsSurfaceNode::GetStateAsString(surfaceNode->GetState()));
  writer->WriteStringProperty("initMode", vtkMRMLNurbsSurfaceNode::GetInitModeAsString(surfaceNode->GetInitMode()));

  writer->WriteIntProperty("rows", static_cast<int>(surfaceNode->GetRows()));
  writer->WriteIntProperty("cols", static_cast<int>(surfaceNode->GetCols()));
  writer->WriteIntProperty("degreeU", static_cast<int>(surfaceNode->GetDegreeU()));
  writer->WriteIntProperty("degreeV", static_cast<int>(surfaceNode->GetDegreeV()));

  // controlGrid + NURBS-specific vector fields.  ``const_cast`` to
  // match the writer signature (input-only; rapidjson backend does
  // not mutate the buffer).
  writer->WriteVectorProperty("controlGrid", const_cast<double*>(surfaceNode->GetControlGrid()), static_cast<int>(surfaceNode->GetControlGridLength()));
  writer->WriteVectorProperty("knotsU", const_cast<double*>(surfaceNode->GetKnotsU()), static_cast<int>(surfaceNode->GetKnotsULength()));
  writer->WriteVectorProperty("knotsV", const_cast<double*>(surfaceNode->GetKnotsV()), static_cast<int>(surfaceNode->GetKnotsVLength()));
  writer->WriteVectorProperty("weights", const_cast<double*>(surfaceNode->GetWeights()), static_cast<int>(surfaceNode->GetWeightsLength()));

  // metadata — reserved per ADR-0014 §5; emit empty for shape parity
  // with the Bezier path so JSON-Schema validators see the same set
  // of top-level keys across surface types.
  writer->WriteObjectPropertyStart("metadata");
  writer->WriteObjectPropertyEnd();

  if (!writer->WriteToFileEnd())
  {
    vtkErrorMacro("WriteJsonNurbs: failed to close '" << filePath << "' after write");
    return 0;
  }
  return 1;
}

//------------------------------------------------------------------------------
int vtkMRMLBezierSurfaceStorageNode::ReadJsonNurbs(const std::string& filePath, vtkMRMLNurbsSurfaceNode* surfaceNode)
{
  ScopedNurbsLoadingFromXML loadingGuard(surfaceNode);

  vtkNew<vtkMRMLJsonReader> reader;
  vtkSmartPointer<vtkMRMLJsonElement> root = vtkSmartPointer<vtkMRMLJsonElement>::Take(reader->ReadFromFile(filePath.c_str()));
  if (root == nullptr)
  {
    vtkErrorMacro("ReadJsonNurbs: failed to parse '" << filePath << "'");
    return 0;
  }
  if (!root->HasMember("schemaVersion"))
  {
    vtkErrorMacro("ReadJsonNurbs: missing required 'schemaVersion' field in '" << filePath << "'");
    return 0;
  }
  const int schemaVersion = root->GetIntProperty("schemaVersion");
  // NURBS files require schemaVersion >= 3 — the ``surfaceType``
  // discriminator only exists in v3.  v1 / v2 files are implicit
  // Bezier; routing them through this path is a configuration
  // error.
  if (schemaVersion < 3 || schemaVersion > SchemaVersion)
  {
    vtkErrorMacro("ReadJsonNurbs: schemaVersion " << schemaVersion << " is not a NURBS-capable schema (need 3..<=" << SchemaVersion << ") in '" << filePath << "'");
    return 0;
  }
  if (!root->HasMember("surfaceType"))
  {
    vtkErrorMacro("ReadJsonNurbs: v3 file missing 'surfaceType' discriminator in '" << filePath << "'");
    return 0;
  }
  const std::string declared = root->GetStringProperty("surfaceType");
  if (declared != "NURBS")
  {
    vtkErrorMacro("ReadJsonNurbs: file declares surfaceType='" << declared << "' but reference node is a vtkMRMLNurbsSurfaceNode in '" << filePath << "'");
    return 0;
  }

  // Shape + degrees — full ADR-0022 §"Validation rules per surface
  // type — NURBS" check.
  if (!root->HasMember("rows") || !root->HasMember("cols") || !root->HasMember("degreeU") || !root->HasMember("degreeV"))
  {
    vtkErrorMacro("ReadJsonNurbs: missing one of {rows, cols, degreeU, degreeV} in '" << filePath << "'");
    return 0;
  }
  const int rowsI = root->GetIntProperty("rows");
  const int colsI = root->GetIntProperty("cols");
  const int degreeUI = root->GetIntProperty("degreeU");
  const int degreeVI = root->GetIntProperty("degreeV");
  if (degreeUI < vtkMRMLNurbsSurfaceNode::MinDegree || degreeUI > vtkMRMLNurbsSurfaceNode::MaxDegree     //
      || degreeVI < vtkMRMLNurbsSurfaceNode::MinDegree || degreeVI > vtkMRMLNurbsSurfaceNode::MaxDegree) //
  {
    vtkErrorMacro("ReadJsonNurbs: invalid degrees (degreeU=" << degreeUI << ", degreeV=" << degreeVI << ") in '" << filePath << "' — ADR-0022 §IVar roster admits {2, 3} only");
    return 0;
  }
  if (rowsI < degreeUI + 1 || colsI < degreeVI + 1)
  {
    vtkErrorMacro("ReadJsonNurbs: invalid (rows=" << rowsI << ", cols=" << colsI << ") for degrees (" << degreeUI << ", " << degreeVI << ") in '" << filePath
                                                  << "' — ADR-0022 §IVar roster requires rows >= degreeU + 1 and cols >= degreeV + 1");
    return 0;
  }
  const unsigned int rows = static_cast<unsigned int>(rowsI);
  const unsigned int cols = static_cast<unsigned int>(colsI);
  const unsigned int degreeU = static_cast<unsigned int>(degreeUI);
  const unsigned int degreeV = static_cast<unsigned int>(degreeVI);

  // Required NURBS-specific arrays.
  if (!root->HasMember("knotsU") || !root->HasMember("knotsV") || !root->HasMember("weights") || !root->HasMember("controlGrid"))
  {
    vtkErrorMacro("ReadJsonNurbs: missing one of {knotsU, knotsV, weights, controlGrid} in '" << filePath << "'");
    return 0;
  }

  const unsigned int expectedKnotsU = rows + degreeU + 1u;
  const unsigned int expectedKnotsV = cols + degreeV + 1u;
  const unsigned int expectedWeights = rows * cols;
  const unsigned int expectedControlGrid = 3u * rows * cols;

  std::vector<double> knotsU(expectedKnotsU, 0.0);
  std::vector<double> knotsV(expectedKnotsV, 0.0);
  std::vector<double> weights(expectedWeights, 0.0);
  std::vector<double> controlGrid(expectedControlGrid, 0.0);

  if (!root->GetVectorProperty("knotsU", knotsU.data(), static_cast<int>(expectedKnotsU)))
  {
    vtkErrorMacro("ReadJsonNurbs: 'knotsU' must be an array of " << expectedKnotsU << " doubles (rows + degreeU + 1) in '" << filePath << "'");
    return 0;
  }
  if (!root->GetVectorProperty("knotsV", knotsV.data(), static_cast<int>(expectedKnotsV)))
  {
    vtkErrorMacro("ReadJsonNurbs: 'knotsV' must be an array of " << expectedKnotsV << " doubles (cols + degreeV + 1) in '" << filePath << "'");
    return 0;
  }
  if (!root->GetVectorProperty("weights", weights.data(), static_cast<int>(expectedWeights)))
  {
    vtkErrorMacro("ReadJsonNurbs: 'weights' must be an array of " << expectedWeights << " doubles (rows * cols) in '" << filePath << "'");
    return 0;
  }
  if (!root->GetVectorProperty("controlGrid", controlGrid.data(), static_cast<int>(expectedControlGrid)))
  {
    vtkErrorMacro("ReadJsonNurbs: 'controlGrid' must be an array of " << expectedControlGrid << " doubles (3 * rows * cols) in '" << filePath << "'");
    return 0;
  }
  // Knot-vector invariants (ADR-0022 §"Validation rules per surface
  // type — NURBS"): non-decreasing, clamped at both ends to
  // ``degree + 1`` equal repeats, in ``[0, 1]``.  Reject malformed
  // knot vectors at the read boundary so a broken file does not
  // reach the data node.
  {
    std::string knotError;
    if (!vtkMRMLNurbsSurfaceNode::ValidateKnotsClampedMonotonic(knotsU, degreeU, knotError))
    {
      vtkErrorMacro("ReadJsonNurbs: invalid 'knotsU' in '" << filePath << "' — " << knotError);
      return 0;
    }
    if (!vtkMRMLNurbsSurfaceNode::ValidateKnotsClampedMonotonic(knotsV, degreeV, knotError))
    {
      vtkErrorMacro("ReadJsonNurbs: invalid 'knotsV' in '" << filePath << "' — " << knotError);
      return 0;
    }
  }
  // Weights must be strictly positive (ADR-0022 §"Validation rules
  // per surface type").  Non-positive weights produce singular
  // rational denominators; reject loudly.
  for (std::size_t i = 0; i < weights.size(); ++i)
  {
    if (!(weights[i] > 0.0))
    {
      vtkErrorMacro("ReadJsonNurbs: weight[" << i << "]=" << weights[i] << " is not strictly positive in '" << filePath << "'");
      return 0;
    }
  }

  // All payloads validated — apply.  Drive the data node through
  // its public setters where possible so any field-level invariant
  // change does not need to be re-implemented here.  The
  // ``SetDegree`` / ``SetSize`` setters regenerate dependent buffers
  // to defaults, so the order matters: shape + degree first, then
  // overwrite knots / weights / controlGrid from the file.
  //
  // To avoid the cross-IVar-invariant rejections in the public
  // setters during the intermediate state (e.g. setting Rows before
  // Cols when both differ), we set the IVars directly on the data
  // node via its file-load-aware code path.  The data node's
  // ``LoadingFromXML`` is already true via ``ScopedNurbsLoadingFrom-
  // XML``; we route the shape change through ``SetSize`` for the
  // square case + manual fall-through for the rectangular case.
  //
  // Simpler implementation: zero the IVars to a sentinel default
  // first (4,4,3,3 — guaranteed valid), then individually grow the
  // axes that need growing.  This avoids the cross-IVar invariant
  // tripping at any intermediate.
  surfaceNode->SetSize(vtkMRMLNurbsSurfaceNode::DefaultGridSize);
  surfaceNode->SetDegree(vtkMRMLNurbsSurfaceNode::DefaultDegree);
  // Grow Rows / Cols / degrees in an order that always keeps the
  // cross-IVar invariant satisfied:
  //   - Drop degrees first (DegreeU + 1 <= current Rows always
  //     holds at default 4 + degree 2 or 3).
  //   - Set Rows + Cols to target.
  //   - Then raise degrees to target if needed.
  if (degreeU < surfaceNode->GetDegreeU())
  {
    surfaceNode->SetDegreeU(degreeU);
  }
  if (degreeV < surfaceNode->GetDegreeV())
  {
    surfaceNode->SetDegreeV(degreeV);
  }
  if (rows != surfaceNode->GetRows())
  {
    surfaceNode->SetRows(rows);
  }
  if (cols != surfaceNode->GetCols())
  {
    surfaceNode->SetCols(cols);
  }
  if (degreeU > surfaceNode->GetDegreeU())
  {
    surfaceNode->SetDegreeU(degreeU);
  }
  if (degreeV > surfaceNode->GetDegreeV())
  {
    surfaceNode->SetDegreeV(degreeV);
  }

  // Overwrite the (now resized) IVars with the file payload.  The
  // public setters re-validate lengths + positivity; redundant with
  // the explicit checks above but defensive against future drift.
  if (!surfaceNode->SetKnotsU(knotsU.data(), knotsU.size()))
  {
    vtkErrorMacro("ReadJsonNurbs: rejected knotsU payload (post-validation drift?) in '" << filePath << "'");
    return 0;
  }
  if (!surfaceNode->SetKnotsV(knotsV.data(), knotsV.size()))
  {
    vtkErrorMacro("ReadJsonNurbs: rejected knotsV payload (post-validation drift?) in '" << filePath << "'");
    return 0;
  }
  if (!surfaceNode->SetWeights(weights.data(), weights.size()))
  {
    vtkErrorMacro("ReadJsonNurbs: rejected weights payload (post-validation drift?) in '" << filePath << "'");
    return 0;
  }
  if (!surfaceNode->SetControlGrid(controlGrid.data()))
  {
    vtkErrorMacro("ReadJsonNurbs: rejected controlGrid payload in '" << filePath << "'");
    return 0;
  }

  // State + InitMode last — same Init-then-Planning-then-Confirmed
  // load order as the Bezier path.
  if (root->HasMember("state"))
  {
    const std::string s = root->GetStringProperty("state");
    int code = vtkMRMLNurbsSurfaceNode::GetStateFromString(s.c_str());
    if (code < 0)
    {
      // Same forward-compatible fallback as the Bezier path.
      vtkWarningMacro("ReadJsonNurbs: unknown state name '" << s << "' in '" << filePath
                                                            << "' — falling back to Planning"
                                                               " (ADR-0019 forward-compatible default)");
      code = vtkMRMLNurbsSurfaceNode::Planning;
    }
    surfaceNode->SetState(code);
  }
  if (root->HasMember("initMode"))
  {
    const std::string s = root->GetStringProperty("initMode");
    const int code = vtkMRMLNurbsSurfaceNode::GetInitModeFromString(s.c_str());
    if (code < 0)
    {
      vtkErrorMacro("ReadJsonNurbs: unknown initMode name '" << s << "' in '" << filePath << "'");
      return 0;
    }
    surfaceNode->SetInitMode(code);
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

  // Legacy ``.lrp.fcsv`` always carries a 4×4 grid (16 control
  // points; the pre-ADR-0018 hard-code).  Force the surface node to
  // the 4×4 shape before populating the buffer so the migration is
  // unambiguous regardless of the node's prior state.
  surfaceNode->SetSize(vtkMRMLBezierSurfaceNode::DefaultGridSize);
  constexpr int expectedPointCount = vtkMRMLBezierSurfaceNode::DefaultGridSize * vtkMRMLBezierSurfaceNode::DefaultGridSize;
  if (static_cast<int>(points.size()) != expectedPointCount)
  {
    vtkErrorMacro("ReadLegacyFcsv: expected " << expectedPointCount << " control points in '" << filePath << "' but found " << points.size());
    return 0;
  }

  // Flatten to the row-major 48-double buffer expected by the
  // surface node's SetControlGrid.  See the file-header comment for
  // the field-mapping rationale.
  std::array<double, vtkMRMLBezierSurfaceNode::MaxControlGridSize> grid;
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

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
  as part of the T2 LiverResections all-in migration (Stack 2 of the
  v2.0.0 release tracker — see ADR-0013 §8 and ADR-0014 §1).

==============================================================================*/

// This module MRML includes
#include "vtkMRMLBezierSurfaceNode.h"
#include "vtkMRMLBezierSurfaceDisplayNode.h"

// MRML includes
#include <vtkMRMLNodePropertyMacros.h>
#include <vtkMRMLScene.h>

// VTK includes
#include <vtkNew.h>
#include <vtkObjectFactory.h>
#include <vtkSmartPointer.h>

// STD includes
#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <sstream>
#include <string>

//------------------------------------------------------------------------------
// Read-only-after-Init guard (ADR-0014 §4 + ADR-0019).
//
// Init-mode subordinate data (slicing-plane / distance-spheroid init
// points + derived plane / spheroid parameters) is mutable while
// ``State == Init`` and becomes read-only audit data the moment the
// node transitions to ``Planning``.  It stays read-only across the
// ``Planning <-> Confirmed`` round-trip introduced by ADR-0019 — the
// audit invariant is "init data is fixed once committed", regardless
// of which post-Init state the node currently sits in.  Every setter
// on that data routes through this macro; if the node is in any
// post-Init state the call emits a ``vtkWarningMacro`` and returns
// without mutating or firing ``Modified()``.
//
// File-local — ``#define``d here and ``#undef``ed at end-of-file so
// the macro does not leak into other translation units.  ``do { …
// } while (0)`` lets the macro sit on a single line at the top of the
// setter body and behave like a statement (early ``return``).
#define LIVER_BEZIER_GUARD_INIT_ONLY(fieldName)                                        \
  do                                                                                   \
  {                                                                                    \
    if (this->State != Init && !this->LoadingFromXML)                                  \
    {                                                                                  \
      vtkWarningMacro("Cannot mutate " #fieldName " after Init->Planning transition"   \
                      " (ADR-0014 §4 / ADR-0019 read-only audit data; current state: " \
                      << GetStateAsString(this->State) << ")");                        \
      return;                                                                          \
    }                                                                                  \
  } while (0)

//------------------------------------------------------------------------------
vtkMRMLNodeNewMacro(vtkMRMLBezierSurfaceNode);

//------------------------------------------------------------------------------
vtkMRMLBezierSurfaceNode::vtkMRMLBezierSurfaceNode()
  : State(ResectionState::Init)
  , InitMode(InitializationMode::SlicingPlane)
  , OrderIndex(-1)
  , Rows(DefaultGridSize)
  , Cols(DefaultGridSize)
  , NumberOfDistanceSpheroidInitPoints(0)
  , DistanceSpheroidRadiusX(0.0)
  , DistanceSpheroidRadiusY(0.0)
  , DistanceSpheroidRadiusZ(0.0)
  , LoadingFromXML(false)
{
  // Default to the v1 4×4 control-grid byte count (48 doubles, all
  // zeroed).  ``SetSize`` / ``SetRows`` / ``SetCols`` resize this
  // buffer in lock-step with the shape change per ADR-0018 §1.
  this->ControlGrid.assign(static_cast<size_t>(3u) * this->Rows * this->Cols, 0.0);

  for (int i = 0; i < 2; ++i)
  {
    for (int j = 0; j < 3; ++j)
    {
      this->SlicingPlaneInitPoints[i][j] = 0.0;
    }
  }
  this->SlicingPlaneOrigin[0] = 0.0;
  this->SlicingPlaneOrigin[1] = 0.0;
  this->SlicingPlaneOrigin[2] = 0.0;
  this->SlicingPlaneNormal[0] = 0.0;
  this->SlicingPlaneNormal[1] = 0.0;
  this->SlicingPlaneNormal[2] = 1.0;

  this->DistanceSpheroidCenter[0] = 0.0;
  this->DistanceSpheroidCenter[1] = 0.0;
  this->DistanceSpheroidCenter[2] = 0.0;
}

//------------------------------------------------------------------------------
vtkMRMLBezierSurfaceNode::~vtkMRMLBezierSurfaceNode() = default;

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::SetState(int state)
{
  // ADR-0019 transition matrix:
  //
  //   Init      -> Planning   allowed (one-way; ADR-0014 §4).
  //   Planning  -> Confirmed  allowed.
  //   Confirmed -> Planning   allowed (round-trip).
  //   Init      -> Confirmed  forbidden (must traverse Planning).
  //   Planning  -> Init       forbidden (ADR-0014 §4).
  //   Confirmed -> Init       forbidden (audit data permanent).
  //
  // Self-assign and any unrecognised int are passed through to the
  // macro-equivalent path so the caller sees identical observability
  // to a plain vtkSetMacro short-circuit.  XML deserialisation is
  // exempt from the transition guard via ``LoadingFromXML`` so a scene
  // serialised with ``state="Confirmed"`` loads into a freshly-default
  // ``Init`` node without tripping the Init -> Confirmed rejection.
  if (state == this->State)
  {
    return;
  }
  if (!this->LoadingFromXML)
  {
    const bool forbidden =                            //
      (this->State == Planning && state == Init)      // ADR-0014 §4
      || (this->State == Confirmed && state == Init)  // ADR-0019
      || (this->State == Init && state == Confirmed); // ADR-0019
    if (forbidden)
    {
      vtkWarningMacro("Resection state transition " << GetStateAsString(this->State) << " -> " << GetStateAsString(state) << " is not permitted (ADR-0019); state left at "
                                                    << GetStateAsString(this->State));
      return;
    }
  }
  this->State = state;
  this->Modified();
}

//------------------------------------------------------------------------------
const char* vtkMRMLBezierSurfaceNode::GetStateAsString(int state)
{
  switch (state)
  {
    case Init: return "Init";
    case Planning: return "Planning";
    case Confirmed: return "Confirmed";
    default: return "Invalid";
  }
}

//------------------------------------------------------------------------------
int vtkMRMLBezierSurfaceNode::GetStateFromString(const char* name)
{
  if (name == nullptr)
  {
    return -1;
  }
  for (int i = 0; i < ResectionState_Last; ++i)
  {
    if (std::strcmp(name, GetStateAsString(i)) == 0)
    {
      return i;
    }
  }
  return -1;
}

//------------------------------------------------------------------------------
const char* vtkMRMLBezierSurfaceNode::GetInitModeAsString(int mode)
{
  switch (mode)
  {
    case SlicingPlane: return "SlicingPlane";
    case DistanceSpheroid: return "DistanceSpheroid";
    default: return "Invalid";
  }
}

//------------------------------------------------------------------------------
int vtkMRMLBezierSurfaceNode::GetInitModeFromString(const char* name)
{
  if (name == nullptr)
  {
    return -1;
  }
  for (int i = 0; i < InitializationMode_Last; ++i)
  {
    if (std::strcmp(name, GetInitModeAsString(i)) == 0)
    {
      return i;
    }
  }
  return -1;
}

//------------------------------------------------------------------------------
bool vtkMRMLBezierSurfaceNode::SetControlGrid(const double* values)
{
  if (values == nullptr)
  {
    return false;
  }
  const size_t length = this->ControlGrid.size();
  std::copy_n(values, length, this->ControlGrid.begin());
  this->Modified();
  return true;
}

//------------------------------------------------------------------------------
// Control-grid shape setters (ADR-0018 §1).
//
// Square only for v2.0.0 — ``SetRows`` / ``SetCols`` reject any
// (Rows, Cols) outside ``{(3, 3), (4, 4)}`` with a ``vtkErrorMacro``
// and no state change.  ``SetSize`` is the convenience entry point
// that sets both axes atomically.
//
// All three resize the underlying ``ControlGrid`` buffer to
// ``3 * Rows * Cols`` doubles and zero-fill on a shape change — per
// ADR-0018 §1, a mid-edit transition discards the in-flight grid
// rather than attempting corner-preservation (simpler semantic;
// surgeons re-seed after the transition).
//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::SetSize(unsigned int n)
{
  if (static_cast<int>(n) < MinGridSize || static_cast<int>(n) > MaxGridSize)
  {
    vtkErrorMacro("SetSize: invalid grid size " << n << "; ADR-0018 §1 admits {" << MinGridSize << ", " << MaxGridSize << "} only — leaving shape at (" << this->Rows << ", "
                                                << this->Cols << ")");
    return;
  }
  if (this->Rows == n && this->Cols == n)
  {
    return;
  }
  this->Rows = n;
  this->Cols = n;
  this->ControlGrid.assign(static_cast<size_t>(3u) * this->Rows * this->Cols, 0.0);
  this->Modified();
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::SetRows(unsigned int rows)
{
  // ADR-0018 §1: square only for v2.0.0.  Reject any value that
  // would leave the node in a non-square state (i.e. rows != Cols
  // unless Cols is about to change too — and the canonical way to
  // change both axes simultaneously is ``SetSize``).
  if (static_cast<int>(rows) < MinGridSize || static_cast<int>(rows) > MaxGridSize)
  {
    vtkErrorMacro("SetRows: invalid Rows " << rows << "; ADR-0018 §1 admits {" << MinGridSize << ", " << MaxGridSize << "} only — leaving Rows at " << this->Rows);
    return;
  }
  if (rows != this->Cols)
  {
    vtkErrorMacro("SetRows: non-square shape (Rows=" << rows << ", Cols=" << this->Cols
                                                     << ") not admitted in v2.0.0 (ADR-0018 §1); use SetSize() to change both axes atomically — leaving Rows at " << this->Rows);
    return;
  }
  if (rows == this->Rows)
  {
    return;
  }
  this->Rows = rows;
  this->ControlGrid.assign(static_cast<size_t>(3u) * this->Rows * this->Cols, 0.0);
  this->Modified();
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::SetCols(unsigned int cols)
{
  if (static_cast<int>(cols) < MinGridSize || static_cast<int>(cols) > MaxGridSize)
  {
    vtkErrorMacro("SetCols: invalid Cols " << cols << "; ADR-0018 §1 admits {" << MinGridSize << ", " << MaxGridSize << "} only — leaving Cols at " << this->Cols);
    return;
  }
  if (cols != this->Rows)
  {
    vtkErrorMacro("SetCols: non-square shape (Rows=" << this->Rows << ", Cols=" << cols
                                                     << ") not admitted in v2.0.0 (ADR-0018 §1); use SetSize() to change both axes atomically — leaving Cols at " << this->Cols);
    return;
  }
  if (cols == this->Cols)
  {
    return;
  }
  this->Cols = cols;
  this->ControlGrid.assign(static_cast<size_t>(3u) * this->Rows * this->Cols, 0.0);
  this->Modified();
}

//------------------------------------------------------------------------------
bool vtkMRMLBezierSurfaceNode::SetSlicingPlaneInitPoint(int index, const double point[3])
{
  if (index < 0 || index > 1 || point == nullptr)
  {
    return false;
  }
  // ADR-0014 §4 / ADR-0019 read-only guard.  Returns false (rather
  // than the macro's plain ``return``) so callers that check the bool
  // see a clear signal that the mutation did not apply, matching the
  // existing "rejected on bad input" return path of this setter.
  // ``LoadingFromXML`` exempts XML deserialisation — see the
  // ``LIVER_BEZIER_GUARD_INIT_ONLY`` macro at the top of this file.
  if (this->State != Init && !this->LoadingFromXML)
  {
    vtkWarningMacro("Cannot mutate SlicingPlaneInitPoint[" << index << "]"
                                                           << " after Init->Planning transition"
                                                           << " (ADR-0014 §4 / ADR-0019 read-only audit data;"
                                                              " current state: "
                                                           << GetStateAsString(this->State) << ")");
    return false;
  }
  this->SlicingPlaneInitPoints[index][0] = point[0];
  this->SlicingPlaneInitPoints[index][1] = point[1];
  this->SlicingPlaneInitPoints[index][2] = point[2];
  this->Modified();
  return true;
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::SetSlicingPlaneOrigin(double x, double y, double z)
{
  LIVER_BEZIER_GUARD_INIT_ONLY(SlicingPlaneOrigin);
  if (this->SlicingPlaneOrigin[0] == x && this->SlicingPlaneOrigin[1] == y && this->SlicingPlaneOrigin[2] == z)
  {
    return;
  }
  this->SlicingPlaneOrigin[0] = x;
  this->SlicingPlaneOrigin[1] = y;
  this->SlicingPlaneOrigin[2] = z;
  this->Modified();
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::SetSlicingPlaneOrigin(const double xyz[3])
{
  this->SetSlicingPlaneOrigin(xyz[0], xyz[1], xyz[2]);
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::SetSlicingPlaneNormal(double x, double y, double z)
{
  LIVER_BEZIER_GUARD_INIT_ONLY(SlicingPlaneNormal);
  if (this->SlicingPlaneNormal[0] == x && this->SlicingPlaneNormal[1] == y && this->SlicingPlaneNormal[2] == z)
  {
    return;
  }
  this->SlicingPlaneNormal[0] = x;
  this->SlicingPlaneNormal[1] = y;
  this->SlicingPlaneNormal[2] = z;
  this->Modified();
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::SetSlicingPlaneNormal(const double xyz[3])
{
  this->SetSlicingPlaneNormal(xyz[0], xyz[1], xyz[2]);
}

//------------------------------------------------------------------------------
const double* vtkMRMLBezierSurfaceNode::GetSlicingPlaneInitPoint(int index) const
{
  if (index < 0 || index > 1)
  {
    return nullptr;
  }
  return this->SlicingPlaneInitPoints[index];
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::SetNumberOfDistanceSpheroidInitPoints(int n)
{
  LIVER_BEZIER_GUARD_INIT_ONLY(NumberOfDistanceSpheroidInitPoints);
  if (n < 0)
  {
    n = 0;
  }
  if (n == this->NumberOfDistanceSpheroidInitPoints)
  {
    return;
  }
  this->NumberOfDistanceSpheroidInitPoints = n;
  this->DistanceSpheroidInitPoints.assign(static_cast<size_t>(n) * 3, 0.0);
  this->Modified();
}

//------------------------------------------------------------------------------
bool vtkMRMLBezierSurfaceNode::SetDistanceSpheroidInitPoint(int index, const double point[3])
{
  if (index < 0 || index >= this->NumberOfDistanceSpheroidInitPoints || point == nullptr)
  {
    return false;
  }
  // ADR-0014 §4 / ADR-0019 read-only guard.  Mirrors the bool-returning
  // rejection path of SetSlicingPlaneInitPoint — see that setter for
  // rationale.
  if (this->State != Init && !this->LoadingFromXML)
  {
    vtkWarningMacro("Cannot mutate DistanceSpheroidInitPoint[" << index << "]"
                                                               << " after Init->Planning transition"
                                                               << " (ADR-0014 §4 / ADR-0019 read-only audit data;"
                                                                  " current state: "
                                                               << GetStateAsString(this->State) << ")");
    return false;
  }
  const size_t base = static_cast<size_t>(index) * 3;
  this->DistanceSpheroidInitPoints[base + 0] = point[0];
  this->DistanceSpheroidInitPoints[base + 1] = point[1];
  this->DistanceSpheroidInitPoints[base + 2] = point[2];
  this->Modified();
  return true;
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::SetDistanceSpheroidCenter(double x, double y, double z)
{
  LIVER_BEZIER_GUARD_INIT_ONLY(DistanceSpheroidCenter);
  if (this->DistanceSpheroidCenter[0] == x && this->DistanceSpheroidCenter[1] == y && this->DistanceSpheroidCenter[2] == z)
  {
    return;
  }
  this->DistanceSpheroidCenter[0] = x;
  this->DistanceSpheroidCenter[1] = y;
  this->DistanceSpheroidCenter[2] = z;
  this->Modified();
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::SetDistanceSpheroidCenter(const double xyz[3])
{
  this->SetDistanceSpheroidCenter(xyz[0], xyz[1], xyz[2]);
}

//------------------------------------------------------------------------------
// Spheroid radii setters.  Each clamps to [0, +inf) — matching the
// pre-refactor ``vtkSetClampMacro`` behaviour — then routes through
// the ADR-0014 §4 read-only guard.  The clamp is applied to the
// argument as the macro did; the guard then either short-circuits or
// commits the clamped value.
void vtkMRMLBezierSurfaceNode::SetDistanceSpheroidRadiusX(double r)
{
  LIVER_BEZIER_GUARD_INIT_ONLY(DistanceSpheroidRadiusX);
  if (r < 0.0)
  {
    r = 0.0;
  }
  if (this->DistanceSpheroidRadiusX == r)
  {
    return;
  }
  this->DistanceSpheroidRadiusX = r;
  this->Modified();
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::SetDistanceSpheroidRadiusY(double r)
{
  LIVER_BEZIER_GUARD_INIT_ONLY(DistanceSpheroidRadiusY);
  if (r < 0.0)
  {
    r = 0.0;
  }
  if (this->DistanceSpheroidRadiusY == r)
  {
    return;
  }
  this->DistanceSpheroidRadiusY = r;
  this->Modified();
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::SetDistanceSpheroidRadiusZ(double r)
{
  LIVER_BEZIER_GUARD_INIT_ONLY(DistanceSpheroidRadiusZ);
  if (r < 0.0)
  {
    r = 0.0;
  }
  if (this->DistanceSpheroidRadiusZ == r)
  {
    return;
  }
  this->DistanceSpheroidRadiusZ = r;
  this->Modified();
}

//------------------------------------------------------------------------------
const double* vtkMRMLBezierSurfaceNode::GetDistanceSpheroidInitPoint(int index) const
{
  if (index < 0 || index >= this->NumberOfDistanceSpheroidInitPoints)
  {
    return nullptr;
  }
  return &this->DistanceSpheroidInitPoints[static_cast<size_t>(index) * 3];
}

//------------------------------------------------------------------------------
namespace
{
/// Helper: serialise N doubles to a space-separated string.
std::string writeDoubles(const double* values, std::size_t n)
{
  std::stringstream ss;
  for (std::size_t i = 0; i < n; ++i)
  {
    if (i > 0)
    {
      ss << " ";
    }
    ss << values[i];
  }
  return ss.str();
}

/// Helper: parse N doubles from a space-separated string.  ``out`` is
/// resized to exactly the number of values successfully parsed.
void readDoubles(const char* text, std::vector<double>& out)
{
  out.clear();
  if (text == nullptr)
  {
    return;
  }
  std::stringstream ss(text);
  double v;
  while (ss >> v)
  {
    out.push_back(v);
  }
}
} // namespace

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::WriteXML(ostream& of, int nIndent)
{
  Superclass::WriteXML(of, nIndent);

  vtkMRMLWriteXMLBeginMacro(of);
  vtkMRMLWriteXMLEnumMacro(state, State);
  vtkMRMLWriteXMLEnumMacro(initMode, InitMode);
  vtkMRMLWriteXMLIntMacro(orderIndex, OrderIndex);
  vtkMRMLWriteXMLIntMacro(rows, Rows);
  vtkMRMLWriteXMLIntMacro(cols, Cols);
  vtkMRMLWriteXMLVectorMacro(slicingPlaneOrigin, SlicingPlaneOrigin, double, 3);
  vtkMRMLWriteXMLVectorMacro(slicingPlaneNormal, SlicingPlaneNormal, double, 3);
  vtkMRMLWriteXMLVectorMacro(distanceSpheroidCenter, DistanceSpheroidCenter, double, 3);
  vtkMRMLWriteXMLFloatMacro(distanceSpheroidRadiusX, DistanceSpheroidRadiusX);
  vtkMRMLWriteXMLFloatMacro(distanceSpheroidRadiusY, DistanceSpheroidRadiusY);
  vtkMRMLWriteXMLFloatMacro(distanceSpheroidRadiusZ, DistanceSpheroidRadiusZ);
  vtkMRMLWriteXMLIntMacro(numberOfDistanceSpheroidInitPoints, NumberOfDistanceSpheroidInitPoints);
  vtkMRMLWriteXMLEndMacro();

  // Free-form payloads (variable / large) emitted as plain attributes
  // outside the macro to keep the macro for fixed-size fields.  The
  // node parses them back in ReadXMLAttributes() unconditionally.
  // Route assembled strings through XMLAttributeEncodeString so any
  // future control-character or quote in the payload is XML-safe
  // (current writeDoubles output is whitespace-and-numeric, so this
  // is defensive — but the discipline matches vtkMRMLNode's own
  // attribute serialisation, cf. vtkMRMLNode.cxx:699).
  of << " controlGrid=\"" << this->XMLAttributeEncodeString(writeDoubles(this->ControlGrid.data(), this->ControlGrid.size())) << "\"";
  of << " slicingPlaneInitPoint0=\"" << this->XMLAttributeEncodeString(writeDoubles(this->SlicingPlaneInitPoints[0], 3)) << "\"";
  of << " slicingPlaneInitPoint1=\"" << this->XMLAttributeEncodeString(writeDoubles(this->SlicingPlaneInitPoints[1], 3)) << "\"";
  if (!this->DistanceSpheroidInitPoints.empty())
  {
    of << " distanceSpheroidInitPoints=\"" << this->XMLAttributeEncodeString(writeDoubles(this->DistanceSpheroidInitPoints.data(), this->DistanceSpheroidInitPoints.size()))
       << "\"";
  }
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::ReadXMLAttributes(const char** atts)
{
  int disabledModify = this->StartModify();

  // ADR-0014 §4 read-only guard is *only* for public-API mutation.
  // XML deserialisation is internal load — temporarily exempt the
  // guards so a scene serialised with ``state="Planning"`` does not
  // reject the subsequent slicing-plane / spheroid attribute reads.
  // Restored before returning regardless of which control path the
  // attribute parser takes.
  const bool wasLoadingFromXML = this->LoadingFromXML;
  this->LoadingFromXML = true;

  Superclass::ReadXMLAttributes(atts);

  vtkMRMLReadXMLBeginMacro(atts);
  vtkMRMLReadXMLEnumMacro(state, State);
  vtkMRMLReadXMLEnumMacro(initMode, InitMode);
  vtkMRMLReadXMLIntMacro(orderIndex, OrderIndex);
  vtkMRMLReadXMLVectorMacro(slicingPlaneOrigin, SlicingPlaneOrigin, double, 3);
  vtkMRMLReadXMLVectorMacro(slicingPlaneNormal, SlicingPlaneNormal, double, 3);
  vtkMRMLReadXMLVectorMacro(distanceSpheroidCenter, DistanceSpheroidCenter, double, 3);
  vtkMRMLReadXMLFloatMacro(distanceSpheroidRadiusX, DistanceSpheroidRadiusX);
  vtkMRMLReadXMLFloatMacro(distanceSpheroidRadiusY, DistanceSpheroidRadiusY);
  vtkMRMLReadXMLFloatMacro(distanceSpheroidRadiusZ, DistanceSpheroidRadiusZ);
  vtkMRMLReadXMLIntMacro(numberOfDistanceSpheroidInitPoints, NumberOfDistanceSpheroidInitPoints);
  vtkMRMLReadXMLEndMacro();

  // ``rows`` / ``cols`` are read manually (NOT via
  // ``vtkMRMLReadXMLIntMacro``) because the macros route through
  // ``Set##propertyName`` and the public ``SetRows`` / ``SetCols``
  // setters reject non-square intermediate states (e.g. rows=3 with
  // cols still at the default 4 — see ADR-0018 §1).  XML load is an
  // internal-load context, exempt from the public-API guard, similar
  // to the ``LoadingFromXML`` exemption around the slicing-plane /
  // spheroid setters.  We collect both values before validating the
  // pair as a unit, then resize the control-grid buffer to match.
  unsigned int parsedRows = this->Rows;
  unsigned int parsedCols = this->Cols;
  bool hasRowsAttr = false;
  bool hasColsAttr = false;
  for (const char** att = atts; att && *att; att += 2)
  {
    const char* name = att[0];
    const char* value = att[1];
    if (value == nullptr)
    {
      continue;
    }
    if (std::strcmp(name, "rows") == 0)
    {
      parsedRows = static_cast<unsigned int>(std::atoi(value));
      hasRowsAttr = true;
    }
    else if (std::strcmp(name, "cols") == 0)
    {
      parsedCols = static_cast<unsigned int>(std::atoi(value));
      hasColsAttr = true;
    }
  }
  (void)hasRowsAttr;
  (void)hasColsAttr;
  // Per ADR-0018 §1: shape must be square and in
  // ``{(3, 3), (4, 4)}``.  Clamp legacy / malformed scenes back to
  // the v1 default so the rest of ReadXMLAttributes keeps a valid
  // buffer to populate.
  if (static_cast<int>(parsedRows) < MinGridSize || static_cast<int>(parsedRows) > MaxGridSize || parsedRows != parsedCols)
  {
    vtkWarningMacro("ReadXMLAttributes: invalid (rows=" << parsedRows << ", cols=" << parsedCols << "); ADR-0018 §1 admits {(3,3), (4,4)} only — falling back to "
                                                        << DefaultGridSize << "x" << DefaultGridSize);
    parsedRows = DefaultGridSize;
    parsedCols = DefaultGridSize;
  }
  this->Rows = parsedRows;
  this->Cols = parsedCols;
  this->ControlGrid.assign(static_cast<size_t>(3u) * this->Rows * this->Cols, 0.0);

  // Free-form payloads — replay the attribute stream a second time so
  // the order of declarations does not matter.  ``Set*`` is not used
  // for the array fields because they do not have macro-generated
  // setters that take a const char*.
  for (const char** att = atts; att && *att; att += 2)
  {
    const char* name = att[0];
    const char* value = att[1];
    if (value == nullptr)
    {
      continue;
    }
    if (std::strcmp(name, "controlGrid") == 0)
    {
      std::vector<double> values;
      const std::string decoded = this->XMLAttributeDecodeString(value);
      readDoubles(decoded.c_str(), values);
      const std::size_t expected = this->ControlGrid.size();
      if (values.size() >= expected)
      {
        std::copy_n(values.begin(), expected, this->ControlGrid.begin());
      }
      else
      {
        // Truncated payload — keep the existing default-init (zero-
        // filled or whatever the caller stashed before ReadXML) and
        // warn loudly so the inconsistency is visible to whoever
        // produced the malformed scene.  Same shape as the warning
        // vtkMRMLPlotSeriesNode emits when a truncated array is
        // encountered on read.
        vtkWarningMacro("Truncated controlGrid attribute; expected " << expected << " doubles (3 * Rows * Cols), got " << values.size() << " — leaving at default");
      }
    }
    else if (std::strcmp(name, "slicingPlaneInitPoint0") == 0 || std::strcmp(name, "slicingPlaneInitPoint1") == 0)
    {
      const int idx = (name[strlen("slicingPlaneInitPoint")] == '0') ? 0 : 1;
      std::vector<double> values;
      const std::string decoded = this->XMLAttributeDecodeString(value);
      readDoubles(decoded.c_str(), values);
      if (values.size() >= 3)
      {
        this->SlicingPlaneInitPoints[idx][0] = values[0];
        this->SlicingPlaneInitPoints[idx][1] = values[1];
        this->SlicingPlaneInitPoints[idx][2] = values[2];
      }
    }
    else if (std::strcmp(name, "distanceSpheroidInitPoints") == 0)
    {
      std::vector<double> values;
      const std::string decoded = this->XMLAttributeDecodeString(value);
      readDoubles(decoded.c_str(), values);
      this->DistanceSpheroidInitPoints = values;
      this->NumberOfDistanceSpheroidInitPoints = static_cast<int>(values.size() / 3);
    }
  }

  // The numberOfDistanceSpheroidInitPoints attribute may have arrived
  // *after* distanceSpheroidInitPoints; if they disagree (e.g. legacy
  // XML wrote a count but no points yet), keep the count in sync with
  // the actual storage so callers do not over-read.
  if (static_cast<size_t>(this->NumberOfDistanceSpheroidInitPoints) * 3 != this->DistanceSpheroidInitPoints.size())
  {
    this->NumberOfDistanceSpheroidInitPoints = static_cast<int>(this->DistanceSpheroidInitPoints.size() / 3);
  }

  this->LoadingFromXML = wasLoadingFromXML;
  this->EndModify(disabledModify);
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::CopyContent(vtkMRMLNode* anode, bool deepCopy /*=true*/)
{
  MRMLNodeModifyBlocker blocker(this);
  Superclass::CopyContent(anode, deepCopy);

  vtkMRMLBezierSurfaceNode* other = vtkMRMLBezierSurfaceNode::SafeDownCast(anode);
  if (other == nullptr)
  {
    vtkErrorMacro("CopyContent: source node is not a vtkMRMLBezierSurfaceNode");
    return;
  }

  this->State = other->State;
  this->InitMode = other->InitMode;
  this->OrderIndex = other->OrderIndex;
  // Shape + buffer in one assignment — ADR-0018 §1.  std::vector
  // copy handles the resize automatically.
  this->Rows = other->Rows;
  this->Cols = other->Cols;
  this->ControlGrid = other->ControlGrid;

  for (int i = 0; i < 2; ++i)
  {
    for (int j = 0; j < 3; ++j)
    {
      this->SlicingPlaneInitPoints[i][j] = other->SlicingPlaneInitPoints[i][j];
    }
  }
  for (int j = 0; j < 3; ++j)
  {
    this->SlicingPlaneOrigin[j] = other->SlicingPlaneOrigin[j];
    this->SlicingPlaneNormal[j] = other->SlicingPlaneNormal[j];
    this->DistanceSpheroidCenter[j] = other->DistanceSpheroidCenter[j];
  }
  this->DistanceSpheroidRadiusX = other->DistanceSpheroidRadiusX;
  this->DistanceSpheroidRadiusY = other->DistanceSpheroidRadiusY;
  this->DistanceSpheroidRadiusZ = other->DistanceSpheroidRadiusZ;
  this->NumberOfDistanceSpheroidInitPoints = other->NumberOfDistanceSpheroidInitPoints;
  this->DistanceSpheroidInitPoints = other->DistanceSpheroidInitPoints;
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::CreateDefaultDisplayNodes()
{
  if (vtkMRMLBezierSurfaceDisplayNode::SafeDownCast(this->GetDisplayNode()) != nullptr)
  {
    // Display node already exists.
    return;
  }
  if (this->GetScene() == nullptr)
  {
    vtkErrorMacro("vtkMRMLBezierSurfaceNode::CreateDefaultDisplayNodes"
                  " failed: scene is invalid");
    return;
  }
  auto displayNode = vtkSmartPointer<vtkMRMLBezierSurfaceDisplayNode>::New();
  this->GetScene()->AddNode(displayNode);
  this->SetAndObserveDisplayNodeID(displayNode->GetID());
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);

  vtkMRMLPrintBeginMacro(os, indent);
  vtkMRMLPrintEnumMacro(State);
  vtkMRMLPrintEnumMacro(InitMode);
  vtkMRMLPrintIntMacro(OrderIndex);
  vtkMRMLPrintIntMacro(Rows);
  vtkMRMLPrintIntMacro(Cols);
  vtkMRMLPrintVectorMacro(SlicingPlaneOrigin, double, 3);
  vtkMRMLPrintVectorMacro(SlicingPlaneNormal, double, 3);
  vtkMRMLPrintVectorMacro(DistanceSpheroidCenter, double, 3);
  vtkMRMLPrintFloatMacro(DistanceSpheroidRadiusX);
  vtkMRMLPrintFloatMacro(DistanceSpheroidRadiusY);
  vtkMRMLPrintFloatMacro(DistanceSpheroidRadiusZ);
  vtkMRMLPrintIntMacro(NumberOfDistanceSpheroidInitPoints);
  vtkMRMLPrintEndMacro();

  os << indent << "ControlGrid (" << this->ControlGrid.size() << " doubles, " << this->Rows << "x" << this->Cols << "): ";
  for (size_t i = 0; i < this->ControlGrid.size(); ++i)
  {
    if (i > 0)
    {
      os << " ";
    }
    os << this->ControlGrid[i];
  }
  os << "\n";
}

//------------------------------------------------------------------------------
// File-local guard macro defined at top — undef at end-of-file so it
// does not leak into other translation units.
#undef LIVER_BEZIER_GUARD_INIT_ONLY

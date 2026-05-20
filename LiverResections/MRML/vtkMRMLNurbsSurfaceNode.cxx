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
  as part of the v2.1 NURBS rollout (NURBS-1 deliverable, see
  ADR-0022 §"Decision 1 — Data node").

==============================================================================*/

// This module MRML includes
#include "vtkMRMLNurbsSurfaceNode.h"

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
vtkMRMLNodeNewMacro(vtkMRMLNurbsSurfaceNode);

//------------------------------------------------------------------------------
vtkMRMLNurbsSurfaceNode::vtkMRMLNurbsSurfaceNode()
  : State(ResectionState::Init)
  , InitMode(InitializationMode::SlicingPlane)
  , Rows(DefaultGridSize)
  , Cols(DefaultGridSize)
  , DegreeU(DefaultDegree)
  , DegreeV(DefaultDegree)
  , LoadingFromXML(false)
{
  // Zero-fill the control grid + all-1.0 weights (non-rational
  // B-spline degenerate case, the safest default per ADR-0022
  // §"Weights default").  Knots default to clamped-uniform via the
  // helper so the (Rows + DegreeU + 1, Cols + DegreeV + 1) lengths
  // stay in sync with the shape / degree IVars.
  this->ControlGrid.assign(static_cast<size_t>(3u) * this->Rows * this->Cols, 0.0);
  this->Weights.assign(static_cast<size_t>(this->Rows) * this->Cols, 1.0);
  this->ResetKnotsToClampedUniform();
}

//------------------------------------------------------------------------------
vtkMRMLNurbsSurfaceNode::~vtkMRMLNurbsSurfaceNode() = default;

//------------------------------------------------------------------------------
void vtkMRMLNurbsSurfaceNode::SetState(int state)
{
  // ADR-0019 transition matrix — same as ``vtkMRMLBezierSurfaceNode``
  // (the matrix is surface-type-agnostic).
  //
  // TODO(ADR-0022 §"Common abstract base"): collapse this duplicate
  // into a shared free-standing helper alongside the state enum once
  // the v2.2 / v3.0 abstract-base refactor lands.
  if (state == this->State)
  {
    return;
  }
  if (!this->LoadingFromXML)
  {
    const bool forbidden =                            //
      (this->State == Planning && state == Init)      //
      || (this->State == Confirmed && state == Init)  //
      || (this->State == Init && state == Confirmed); //
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
const char* vtkMRMLNurbsSurfaceNode::GetStateAsString(int state)
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
int vtkMRMLNurbsSurfaceNode::GetStateFromString(const char* name)
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
const char* vtkMRMLNurbsSurfaceNode::GetInitModeAsString(int mode)
{
  switch (mode)
  {
    case SlicingPlane: return "SlicingPlane";
    case DistanceSpheroid: return "DistanceSpheroid";
    default: return "Invalid";
  }
}

//------------------------------------------------------------------------------
int vtkMRMLNurbsSurfaceNode::GetInitModeFromString(const char* name)
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
// Shape + degree setters (ADR-0022 §"IVar roster").  Each accepts a
// new value only if (a) it is in the admitted range and (b) the
// cross-IVar invariant ``Rows >= DegreeU + 1`` (etc.) holds with the
// new value.  On acceptance, the dependent buffers (knots / weights /
// control grid) are regenerated to defaults — a shape or degree
// change discards the in-flight surface (same convention as
// ``vtkMRMLBezierSurfaceNode::SetSize``).
//------------------------------------------------------------------------------
void vtkMRMLNurbsSurfaceNode::SetRows(unsigned int rows)
{
  if (rows < this->DegreeU + 1u)
  {
    vtkErrorMacro("SetRows: invalid Rows " << rows << "; must satisfy Rows >= DegreeU + 1 (current DegreeU=" << this->DegreeU << ") per ADR-0022 §IVar roster — leaving Rows at "
                                           << this->Rows);
    return;
  }
  if (rows == this->Rows)
  {
    return;
  }
  // ``MRMLNodeModifyBlocker`` suppresses the intermediate
  // ``Modified()`` emitted by ``ResetKnotsToClampedUniform`` so the
  // composite shape change fires ``Modified()`` exactly once on
  // scope exit (ADR-0018 §1 single-fire invariant — same pattern
  // ``CopyContent`` uses below).
  MRMLNodeModifyBlocker blocker(this);
  this->Rows = rows;
  this->ControlGrid.assign(static_cast<size_t>(3u) * this->Rows * this->Cols, 0.0);
  this->Weights.assign(static_cast<size_t>(this->Rows) * this->Cols, 1.0);
  this->ResetKnotsToClampedUniform();
}

//------------------------------------------------------------------------------
void vtkMRMLNurbsSurfaceNode::SetCols(unsigned int cols)
{
  if (cols < this->DegreeV + 1u)
  {
    vtkErrorMacro("SetCols: invalid Cols " << cols << "; must satisfy Cols >= DegreeV + 1 (current DegreeV=" << this->DegreeV << ") per ADR-0022 §IVar roster — leaving Cols at "
                                           << this->Cols);
    return;
  }
  if (cols == this->Cols)
  {
    return;
  }
  MRMLNodeModifyBlocker blocker(this);
  this->Cols = cols;
  this->ControlGrid.assign(static_cast<size_t>(3u) * this->Rows * this->Cols, 0.0);
  this->Weights.assign(static_cast<size_t>(this->Rows) * this->Cols, 1.0);
  this->ResetKnotsToClampedUniform();
}

//------------------------------------------------------------------------------
void vtkMRMLNurbsSurfaceNode::SetSize(unsigned int n)
{
  if (n < this->DegreeU + 1u || n < this->DegreeV + 1u)
  {
    vtkErrorMacro("SetSize: invalid size " << n << "; must satisfy n >= DegreeU+1 (" << (this->DegreeU + 1u) << ") and n >= DegreeV+1 (" << (this->DegreeV + 1u)
                                           << ") per ADR-0022 §IVar roster — leaving shape at (" << this->Rows << ", " << this->Cols << ")");
    return;
  }
  if (this->Rows == n && this->Cols == n)
  {
    return;
  }
  MRMLNodeModifyBlocker blocker(this);
  this->Rows = n;
  this->Cols = n;
  this->ControlGrid.assign(static_cast<size_t>(3u) * this->Rows * this->Cols, 0.0);
  this->Weights.assign(static_cast<size_t>(this->Rows) * this->Cols, 1.0);
  this->ResetKnotsToClampedUniform();
}

//------------------------------------------------------------------------------
void vtkMRMLNurbsSurfaceNode::SetDegreeU(unsigned int degree)
{
  if (static_cast<int>(degree) < MinDegree || static_cast<int>(degree) > MaxDegree)
  {
    vtkErrorMacro("SetDegreeU: invalid degree " << degree << "; ADR-0022 §IVar roster admits {" << MinDegree << ", " << MaxDegree << "} only — leaving DegreeU at "
                                                << this->DegreeU);
    return;
  }
  if (degree + 1u > this->Rows)
  {
    vtkErrorMacro("SetDegreeU: cannot raise DegreeU to " << degree << " when Rows=" << this->Rows << " (need Rows >= DegreeU + 1) per ADR-0022 §IVar roster — leaving DegreeU at "
                                                         << this->DegreeU);
    return;
  }
  if (degree == this->DegreeU)
  {
    return;
  }
  MRMLNodeModifyBlocker blocker(this);
  this->DegreeU = degree;
  this->ResetKnotsToClampedUniform();
}

//------------------------------------------------------------------------------
void vtkMRMLNurbsSurfaceNode::SetDegreeV(unsigned int degree)
{
  if (static_cast<int>(degree) < MinDegree || static_cast<int>(degree) > MaxDegree)
  {
    vtkErrorMacro("SetDegreeV: invalid degree " << degree << "; ADR-0022 §IVar roster admits {" << MinDegree << ", " << MaxDegree << "} only — leaving DegreeV at "
                                                << this->DegreeV);
    return;
  }
  if (degree + 1u > this->Cols)
  {
    vtkErrorMacro("SetDegreeV: cannot raise DegreeV to " << degree << " when Cols=" << this->Cols << " (need Cols >= DegreeV + 1) per ADR-0022 §IVar roster — leaving DegreeV at "
                                                         << this->DegreeV);
    return;
  }
  if (degree == this->DegreeV)
  {
    return;
  }
  MRMLNodeModifyBlocker blocker(this);
  this->DegreeV = degree;
  this->ResetKnotsToClampedUniform();
}

//------------------------------------------------------------------------------
void vtkMRMLNurbsSurfaceNode::SetDegree(unsigned int d)
{
  if (static_cast<int>(d) < MinDegree || static_cast<int>(d) > MaxDegree)
  {
    vtkErrorMacro("SetDegree: invalid degree " << d << "; ADR-0022 §IVar roster admits {" << MinDegree << ", " << MaxDegree << "} only — leaving degrees at (" << this->DegreeU
                                               << ", " << this->DegreeV << ")");
    return;
  }
  if (d + 1u > this->Rows || d + 1u > this->Cols)
  {
    vtkErrorMacro("SetDegree: cannot raise degree to " << d << " with shape (" << this->Rows << ", " << this->Cols << ") — need both axes >= degree + 1 per ADR-0022 §IVar roster"
                                                       << " — leaving degrees at (" << this->DegreeU << ", " << this->DegreeV << ")");
    return;
  }
  if (d == this->DegreeU && d == this->DegreeV)
  {
    return;
  }
  MRMLNodeModifyBlocker blocker(this);
  this->DegreeU = d;
  this->DegreeV = d;
  this->ResetKnotsToClampedUniform();
}

//------------------------------------------------------------------------------
bool vtkMRMLNurbsSurfaceNode::SetControlGrid(const double* values)
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
bool vtkMRMLNurbsSurfaceNode::SetKnotsU(const double* values, std::size_t length)
{
  if (values == nullptr)
  {
    return false;
  }
  if (length != this->GetKnotsULength())
  {
    vtkErrorMacro("SetKnotsU: length mismatch — expected " << this->GetKnotsULength() << " doubles (Rows + DegreeU + 1) but got " << length);
    return false;
  }
  std::vector<double> candidate(values, values + length);
  std::string error;
  if (!ValidateKnotsClampedMonotonic(candidate, this->DegreeU, error))
  {
    vtkErrorMacro("SetKnotsU: " << error);
    return false;
  }
  this->KnotsU = std::move(candidate);
  this->Modified();
  return true;
}

//------------------------------------------------------------------------------
bool vtkMRMLNurbsSurfaceNode::SetKnotsV(const double* values, std::size_t length)
{
  if (values == nullptr)
  {
    return false;
  }
  if (length != this->GetKnotsVLength())
  {
    vtkErrorMacro("SetKnotsV: length mismatch — expected " << this->GetKnotsVLength() << " doubles (Cols + DegreeV + 1) but got " << length);
    return false;
  }
  std::vector<double> candidate(values, values + length);
  std::string error;
  if (!ValidateKnotsClampedMonotonic(candidate, this->DegreeV, error))
  {
    vtkErrorMacro("SetKnotsV: " << error);
    return false;
  }
  this->KnotsV = std::move(candidate);
  this->Modified();
  return true;
}

//------------------------------------------------------------------------------
bool vtkMRMLNurbsSurfaceNode::ValidateKnotsClampedMonotonic(const std::vector<double>& knots, unsigned int degree, std::string& error)
{
  // ADR-0022 §"Validation rules per surface type — NURBS" pins the
  // on-disk knot invariant: non-decreasing, clamped at both ends
  // (``degree + 1`` equal repeats), in ``[0, 1]``.  v2.1 admits
  // clamped-uniform only; OPEN-UNIFORM + other parameterisations are
  // deferred (numerical-stability + clinical-demand reasons noted in
  // the ADR's "Default degree" §).  Length is assumed to have been
  // size-checked by the caller — only monotonicity + clamping +
  // range are verified here.
  const std::size_t n = knots.size();
  const std::size_t needed = static_cast<std::size_t>(degree) + 1u;
  if (n < 2u * needed)
  {
    std::ostringstream oss;
    oss << "knot vector of length " << n << " is too short for degree " << degree << " (need at least " << (2u * needed) << " entries for the clamping repeats)";
    error = oss.str();
    return false;
  }
  // Range — first / last entries must lie in [0, 1].  Combined with
  // the clamping + monotonicity checks below this also pins the
  // whole vector to [0, 1].
  if (!(knots.front() >= 0.0) || !(knots.back() <= 1.0))
  {
    std::ostringstream oss;
    oss << "knot vector out of range — front=" << knots.front() << ", back=" << knots.back() << " (expected within [0, 1] per ADR-0022 §IVar roster)";
    error = oss.str();
    return false;
  }
  // Clamping — the first (degree + 1) entries must all equal
  // knots.front(); the last (degree + 1) entries must all equal
  // knots.back().
  const double startValue = knots.front();
  for (std::size_t i = 0; i < needed; ++i)
  {
    if (knots[i] != startValue)
    {
      std::ostringstream oss;
      oss << "knot vector is not clamped at the start — knots[" << i << "]=" << knots[i] << " differs from knots[0]=" << startValue << " (need " << needed
          << " equal repeats for degree " << degree << ")";
      error = oss.str();
      return false;
    }
  }
  const double endValue = knots.back();
  for (std::size_t i = n - needed; i < n; ++i)
  {
    if (knots[i] != endValue)
    {
      std::ostringstream oss;
      oss << "knot vector is not clamped at the end — knots[" << i << "]=" << knots[i] << " differs from knots[" << (n - 1) << "]=" << endValue << " (need " << needed
          << " equal repeats for degree " << degree << ")";
      error = oss.str();
      return false;
    }
  }
  // Monotonicity — non-decreasing along the full sequence.
  for (std::size_t i = 1; i < n; ++i)
  {
    if (knots[i] < knots[i - 1])
    {
      std::ostringstream oss;
      oss << "knot vector is not non-decreasing — knots[" << i << "]=" << knots[i] << " < knots[" << (i - 1) << "]=" << knots[i - 1];
      error = oss.str();
      return false;
    }
  }
  return true;
}

//------------------------------------------------------------------------------
bool vtkMRMLNurbsSurfaceNode::SetWeights(const double* values, std::size_t length)
{
  if (values == nullptr)
  {
    return false;
  }
  if (length != this->GetWeightsLength())
  {
    vtkErrorMacro("SetWeights: length mismatch — expected " << this->GetWeightsLength() << " doubles (Rows * Cols) but got " << length);
    return false;
  }
  // Every weight must be strictly positive — non-positive weights
  // produce singularities in the NURBS basis (division by zero on
  // the rational denominator).  ADR-0022 §"Validation rules per
  // surface type" pins this invariant explicitly.
  for (std::size_t i = 0; i < length; ++i)
  {
    if (!(values[i] > 0.0))
    {
      vtkErrorMacro("SetWeights: weight at index " << i << " is " << values[i] << "; weights must be strictly positive per ADR-0022 §IVar roster");
      return false;
    }
  }
  this->Weights.assign(values, values + length);
  this->Modified();
  return true;
}

//------------------------------------------------------------------------------
void vtkMRMLNurbsSurfaceNode::ResetKnotsToClampedUniform()
{
  // Clamped-uniform knot vector per de Boor convention:
  //   [0, 0, ..., 0,  k_1, k_2, ..., k_{m-1},  1, 1, ..., 1]
  //   |---degree+1--| |--rows-degree-1 interior--| |---degree+1---|
  //
  // ``rows - degree - 1`` interior knots uniformly spaced in
  // ``(0, 1)`` — k_i = i / (rows - degree).  When ``rows == degree+1``
  // the interior region is empty and the knot vector is just
  // ``degree + 1`` zeros followed by ``degree + 1`` ones (the
  // degree-n Bezier degenerate case of NURBS).
  auto buildKnots = [](unsigned int n, unsigned int degree, std::vector<double>& out)
  {
    const unsigned int knotCount = n + degree + 1u;
    out.assign(knotCount, 0.0);
    // First (degree + 1) entries stay 0.0 (assign initialises them);
    // last (degree + 1) entries to 1.0.
    for (unsigned int i = knotCount - degree - 1u; i < knotCount; ++i)
    {
      out[i] = 1.0;
    }
    // Interior knots, uniformly spaced.  ``denom`` is the step
    // count: from k_0 = 0 to k_{n-degree} = 1 in (n - degree) steps
    // → interior values at i / (n - degree) for i = 1 .. n-degree-1.
    if (n > degree + 1u)
    {
      const unsigned int interiorStart = degree + 1u;
      const unsigned int interiorCount = n - degree - 1u;
      const double denom = static_cast<double>(n - degree);
      for (unsigned int i = 0; i < interiorCount; ++i)
      {
        out[interiorStart + i] = static_cast<double>(i + 1) / denom;
      }
    }
  };
  buildKnots(this->Rows, this->DegreeU, this->KnotsU);
  buildKnots(this->Cols, this->DegreeV, this->KnotsV);
  this->Modified();
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

/// Helper: parse N doubles from a space-separated string.
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
void vtkMRMLNurbsSurfaceNode::WriteXML(ostream& of, int nIndent)
{
  Superclass::WriteXML(of, nIndent);

  vtkMRMLWriteXMLBeginMacro(of);
  vtkMRMLWriteXMLEnumMacro(state, State);
  vtkMRMLWriteXMLEnumMacro(initMode, InitMode);
  vtkMRMLWriteXMLIntMacro(rows, Rows);
  vtkMRMLWriteXMLIntMacro(cols, Cols);
  vtkMRMLWriteXMLIntMacro(degreeU, DegreeU);
  vtkMRMLWriteXMLIntMacro(degreeV, DegreeV);
  vtkMRMLWriteXMLEndMacro();

  // Free-form vector payloads emitted as XML-attribute-encoded
  // strings, mirroring the convention used by
  // ``vtkMRMLBezierSurfaceNode::WriteXML``.
  of << " controlGrid=\"" << this->XMLAttributeEncodeString(writeDoubles(this->ControlGrid.data(), this->ControlGrid.size())) << "\"";
  of << " knotsU=\"" << this->XMLAttributeEncodeString(writeDoubles(this->KnotsU.data(), this->KnotsU.size())) << "\"";
  of << " knotsV=\"" << this->XMLAttributeEncodeString(writeDoubles(this->KnotsV.data(), this->KnotsV.size())) << "\"";
  of << " weights=\"" << this->XMLAttributeEncodeString(writeDoubles(this->Weights.data(), this->Weights.size())) << "\"";
}

//------------------------------------------------------------------------------
void vtkMRMLNurbsSurfaceNode::ReadXMLAttributes(const char** atts)
{
  int disabledModify = this->StartModify();

  // Bypass the ADR-0019 transition guard for the duration of the
  // attribute parse so a scene serialised with ``state="Confirmed"``
  // loads into a freshly-Init sink without rejection.  Same pattern
  // as ``vtkMRMLBezierSurfaceNode::ReadXMLAttributes``.
  const bool wasLoadingFromXML = this->LoadingFromXML;
  this->LoadingFromXML = true;

  Superclass::ReadXMLAttributes(atts);

  vtkMRMLReadXMLBeginMacro(atts);
  vtkMRMLReadXMLEnumMacro(state, State);
  vtkMRMLReadXMLEnumMacro(initMode, InitMode);
  vtkMRMLReadXMLEndMacro();

  // Shape + degree are read manually (not via the
  // ``vtkMRMLReadXMLIntMacro``) for the same reason ``vtkMRMLBezier-
  // SurfaceNode`` reads ``rows`` / ``cols`` manually — XML
  // deserialisation is an internal-load context, exempt from the
  // public-API setter validation that would otherwise reject
  // intermediate cross-IVar states (e.g. setting Rows before Cols
  // when both change).
  unsigned int parsedRows = this->Rows;
  unsigned int parsedCols = this->Cols;
  unsigned int parsedDegU = this->DegreeU;
  unsigned int parsedDegV = this->DegreeV;
  for (const char** att = atts; att && *att; att += 2)
  {
    const char* name = att[0];
    const char* value = att[1];
    if (value == nullptr)
    {
      break;
    }
    if (std::strcmp(name, "rows") == 0)
    {
      parsedRows = static_cast<unsigned int>(std::atoi(value));
    }
    else if (std::strcmp(name, "cols") == 0)
    {
      parsedCols = static_cast<unsigned int>(std::atoi(value));
    }
    else if (std::strcmp(name, "degreeU") == 0)
    {
      parsedDegU = static_cast<unsigned int>(std::atoi(value));
    }
    else if (std::strcmp(name, "degreeV") == 0)
    {
      parsedDegV = static_cast<unsigned int>(std::atoi(value));
    }
  }
  // Lightweight validity check: clamp to defaults if the parsed
  // shape would leave the basis empty.  The storage-node JSON path
  // performs the load-bearing validation; this is the defensive XML
  // fallback for malformed scenes.
  if (static_cast<int>(parsedDegU) < MinDegree || static_cast<int>(parsedDegU) > MaxDegree)
  {
    vtkWarningMacro("ReadXMLAttributes: invalid degreeU=" << parsedDegU << "; falling back to " << DefaultDegree);
    parsedDegU = DefaultDegree;
  }
  if (static_cast<int>(parsedDegV) < MinDegree || static_cast<int>(parsedDegV) > MaxDegree)
  {
    vtkWarningMacro("ReadXMLAttributes: invalid degreeV=" << parsedDegV << "; falling back to " << DefaultDegree);
    parsedDegV = DefaultDegree;
  }
  if (parsedRows < parsedDegU + 1u || parsedCols < parsedDegV + 1u)
  {
    vtkWarningMacro("ReadXMLAttributes: invalid shape (rows=" << parsedRows << ", cols=" << parsedCols << ") for degrees (" << parsedDegU << ", " << parsedDegV
                                                              << "); falling back to defaults");
    parsedRows = DefaultGridSize;
    parsedCols = DefaultGridSize;
    parsedDegU = DefaultDegree;
    parsedDegV = DefaultDegree;
  }
  this->Rows = parsedRows;
  this->Cols = parsedCols;
  this->DegreeU = parsedDegU;
  this->DegreeV = parsedDegV;
  // Resize the IVar buffers in lock-step with the parsed shape.
  // Knots get re-built to clamped-uniform first; the explicit
  // ``knotsU`` / ``knotsV`` payloads below overwrite that default if
  // the attribute is present in the stream.
  this->ControlGrid.assign(static_cast<size_t>(3u) * this->Rows * this->Cols, 0.0);
  this->Weights.assign(static_cast<size_t>(this->Rows) * this->Cols, 1.0);
  this->ResetKnotsToClampedUniform();

  // Free-form payloads — replay the attribute stream so attribute
  // order in the XML does not matter.
  for (const char** att = atts; att && *att; att += 2)
  {
    const char* name = att[0];
    const char* value = att[1];
    if (value == nullptr)
    {
      break;
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
        vtkWarningMacro("Truncated controlGrid attribute; expected " << expected << " doubles (3 * Rows * Cols), got " << values.size() << " — leaving at default");
      }
    }
    else if (std::strcmp(name, "knotsU") == 0)
    {
      std::vector<double> values;
      const std::string decoded = this->XMLAttributeDecodeString(value);
      readDoubles(decoded.c_str(), values);
      if (values.size() == this->GetKnotsULength())
      {
        this->KnotsU = values;
      }
      else
      {
        vtkWarningMacro("knotsU length " << values.size() << " != expected " << this->GetKnotsULength() << " (Rows + DegreeU + 1) — leaving at clamped-uniform default");
      }
    }
    else if (std::strcmp(name, "knotsV") == 0)
    {
      std::vector<double> values;
      const std::string decoded = this->XMLAttributeDecodeString(value);
      readDoubles(decoded.c_str(), values);
      if (values.size() == this->GetKnotsVLength())
      {
        this->KnotsV = values;
      }
      else
      {
        vtkWarningMacro("knotsV length " << values.size() << " != expected " << this->GetKnotsVLength() << " (Cols + DegreeV + 1) — leaving at clamped-uniform default");
      }
    }
    else if (std::strcmp(name, "weights") == 0)
    {
      std::vector<double> values;
      const std::string decoded = this->XMLAttributeDecodeString(value);
      readDoubles(decoded.c_str(), values);
      if (values.size() == this->GetWeightsLength())
      {
        // Defensive positivity check — match the public setter's
        // validation contract.  An invalid payload leaves the
        // default all-1.0 weights in place.
        bool allPositive = true;
        for (double w : values)
        {
          if (!(w > 0.0))
          {
            allPositive = false;
            break;
          }
        }
        if (allPositive)
        {
          this->Weights = values;
        }
        else
        {
          vtkWarningMacro("weights attribute contains non-positive value(s); leaving at default all-1.0");
        }
      }
      else
      {
        vtkWarningMacro("weights length " << values.size() << " != expected " << this->GetWeightsLength() << " (Rows * Cols) — leaving at default all-1.0");
      }
    }
  }

  this->LoadingFromXML = wasLoadingFromXML;
  this->EndModify(disabledModify);
}

//------------------------------------------------------------------------------
void vtkMRMLNurbsSurfaceNode::CopyContent(vtkMRMLNode* anode, bool deepCopy /*=true*/)
{
  MRMLNodeModifyBlocker blocker(this);
  Superclass::CopyContent(anode, deepCopy);

  vtkMRMLNurbsSurfaceNode* other = vtkMRMLNurbsSurfaceNode::SafeDownCast(anode);
  if (other == nullptr)
  {
    // Cross-type sources are rejected — a Bezier source carries no
    // knots / weights / degrees, and a meaningful conversion (Bezier
    // → NURBS or NURBS → Bezier) needs a degree-elevation /
    // approximation pass, not a field-by-field copy.  ADR-0022
    // §"Sharing with the Bezier node — deliberate non-sharing" pins
    // sibling-not-subclass; matching cross-type Copy is rejected by
    // ``vtkMRMLBezierSurfaceNode::CopyContent`` symmetrically.
    vtkErrorMacro("CopyContent: source node is not a vtkMRMLNurbsSurfaceNode (got '" << (anode != nullptr ? anode->GetClassName() : "null") << "')");
    return;
  }

  this->State = other->State;
  this->InitMode = other->InitMode;
  this->Rows = other->Rows;
  this->Cols = other->Cols;
  this->DegreeU = other->DegreeU;
  this->DegreeV = other->DegreeV;
  this->KnotsU = other->KnotsU;
  this->KnotsV = other->KnotsV;
  this->Weights = other->Weights;
  this->ControlGrid = other->ControlGrid;
}

//------------------------------------------------------------------------------
void vtkMRMLNurbsSurfaceNode::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);

  vtkMRMLPrintBeginMacro(os, indent);
  vtkMRMLPrintEnumMacro(State);
  vtkMRMLPrintEnumMacro(InitMode);
  vtkMRMLPrintIntMacro(Rows);
  vtkMRMLPrintIntMacro(Cols);
  vtkMRMLPrintIntMacro(DegreeU);
  vtkMRMLPrintIntMacro(DegreeV);
  vtkMRMLPrintEndMacro();

  auto dumpVector = [&os, &indent](const char* label, const std::vector<double>& v)
  {
    os << indent << label << " (" << v.size() << " doubles): ";
    for (size_t i = 0; i < v.size(); ++i)
    {
      if (i > 0)
      {
        os << " ";
      }
      os << v[i];
    }
    os << "\n";
  };
  dumpVector("KnotsU", this->KnotsU);
  dumpVector("KnotsV", this->KnotsV);
  dumpVector("Weights", this->Weights);
  dumpVector("ControlGrid", this->ControlGrid);
}

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

#ifndef __vtkmrmlnurbssurfacenode_h_
#define __vtkmrmlnurbssurfacenode_h_

#include "vtkSlicerLiverResectionsModuleMRMLExport.h"

// MRML includes
#include <vtkMRMLDisplayableNode.h>

// VTK includes
#include <vtkNew.h>
#include <vtkSetGet.h>

// STD includes
#include <vector>

/**
 * \class vtkMRMLNurbsSurfaceNode
 *
 * \brief Data-only MRML node carrying the geometry of a NURBS-surface
 *        resection plan — sibling of ``vtkMRMLBezierSurfaceNode``.
 *
 * Lands as the NURBS-1 deliverable of ADR-0022 §"Rollout plan".
 * Per ADR-0022 §"Decision 1 — Data node", the NURBS node is a
 * **sibling** of the Bezier node (NOT a subclass of a shared abstract
 * ``vtkMRMLParametricSurfaceNode``).  Field-level duplication between
 * the two trios (``Rows``, ``Cols``, ``ControlGrid``, ``State``,
 * ``InitMode``) is the deliberate cost; the payoff is exact-class
 * dispatch in the LayerDM Pipeline factory per ADR-0013 §5 call 3.
 *
 * \par IVars (ADR-0022 §"Decision 1 — Data node")
 *
 * - ``Rows``, ``Cols`` (``unsigned int``) — control-polygon shape.
 *   Constraints: ``Rows >= DegreeU + 1``, ``Cols >= DegreeV + 1``.
 *   Default ``DefaultGridSize`` (4 — the minimum valid degree-3 grid).
 * - ``DegreeU``, ``DegreeV`` (``unsigned int``) — basis degrees.
 *   Allowed values for v2.1: ``{2, 3}``.  Defaults to 3 (cubic NURBS,
 *   the surgical-planning canonical per ADR-0022 §"Default degree").
 * - ``KnotsU`` (``std::vector<double>``, length ``Rows + DegreeU + 1``)
 *   — knot vector along U.  Default: **clamped-uniform** per the de
 *   Boor convention — ``DegreeU + 1`` zeros at the start, uniformly
 *   spaced interior knots in ``(0, 1)``, ``DegreeU + 1`` ones at the
 *   end.  Surface domain is ``[0, 1] x [0, 1]``; corners are
 *   interpolated.
 * - ``KnotsV`` — symmetric to ``KnotsU`` along V.
 * - ``Weights`` (``std::vector<double>``, length ``Rows * Cols``) —
 *   rational weights.  Default all ``1.0`` (non-rational ↔ B-spline).
 *   Constraint: strictly positive.
 * - ``ControlGrid`` (``std::vector<double>``, length
 *   ``3 * Rows * Cols``) — control polygon, same row-major
 *   ``(row, col) -> flat[row * Cols + col] * 3 + {0, 1, 2}`` layout
 *   as ``vtkMRMLBezierSurfaceNode::ControlGrid``.
 *
 * State machine (``Init`` / ``Planning`` / ``Confirmed``) and
 * ``InitializationMode`` (``SlicingPlane`` / ``DistanceSpheroid``)
 * are duplicated from ``vtkMRMLBezierSurfaceNode`` for v2.1 per
 * ADR-0022 §"Sharing with the Bezier node — deliberate non-sharing".
 *
 * \par Shape-change side effects
 *
 * The shape-change setters — ``SetRows``, ``SetCols``, ``SetSize``,
 * ``SetDegreeU``, ``SetDegreeV``, ``SetDegree`` — regenerate the
 * dependent buffers from defaults on every accepted call:
 *
 *   - ``Weights`` is re-filled with ``1.0`` (the non-rational
 *     B-spline degenerate case — pre-resize weight edits do **not**
 *     survive a shape change).
 *   - ``ControlGrid`` is re-zeroed to the new ``3 * Rows * Cols``
 *     length (matching ``vtkMRMLBezierSurfaceNode``'s
 *     analogous behaviour — a shape change discards the in-flight
 *     surface, on the assumption that a new shape implies a new
 *     surface, not a fitted resample).
 *   - ``KnotsU`` / ``KnotsV`` are regenerated to clamped-uniform
 *     vectors of the new length (``Rows + DegreeU + 1`` resp.
 *     ``Cols + DegreeV + 1``) via ``ResetKnotsToClampedUniform``.
 *
 * Each accepted setter coalesces these dependent mutations into
 * exactly one ``Modified()`` event via ``MRMLNodeModifyBlocker`` so
 * downstream observers see a single shape-change notification per
 * setter call (ADR-0018 §1 single-fire invariant — same convention
 * as ``vtkMRMLBezierSurfaceNode::SetSize``).  Rejected setter calls
 * fire ``Modified()`` zero times.
 *
 * The NURBS-specific ``Weights`` regeneration is the meaningful
 * delta from the Bezier sibling (which regenerates only the
 * ``ControlGrid``).  Consumers that have populated ``Weights`` and
 * then change the shape need to re-issue ``SetWeights`` on the new
 * shape.
 *
 * \par TODO — common abstract base
 *
 * ADR-0022 §"Sharing with the Bezier node — deliberate non-sharing"
 * notes that a future ``vtkMRMLParametricSurfaceNode`` abstract base
 * may collapse the duplicated state-enum + transition-matrix +
 * shared-field declarations.  v2.1 keeps the duplication intentional
 * for sibling exact-class dispatch; v2.2 / v3.0 may revisit.
 */
class VTK_SLICER_LIVERRESECTIONS_MODULE_MRML_EXPORT vtkMRMLNurbsSurfaceNode : public vtkMRMLDisplayableNode
{
public:
  static vtkMRMLNurbsSurfaceNode* New();
  vtkTypeMacro(vtkMRMLNurbsSurfaceNode, vtkMRMLDisplayableNode);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  /// Resection state machine — duplicated from
  /// ``vtkMRMLBezierSurfaceNode::ResectionState`` per ADR-0022
  /// §"Sharing with the Bezier node — deliberate non-sharing".
  /// Same transition matrix as Bezier per ADR-0019 (the matrix is
  /// surface-type-agnostic).
  ///
  /// TODO(ADR-0022 §"Common abstract base"): collapse the state enum
  /// + the SetState transition matrix into a free-standing
  /// ``vtkMRMLParametricSurfaceState`` helper once the v2.2 / v3.0
  /// abstract-base refactor lands.  Out of scope for NURBS-1.
  enum ResectionState
  {
    Init = 0,
    Planning = 1,
    Confirmed = 2,
    ResectionState_Last
  };

  /// Init-mode dispatch — duplicated from
  /// ``vtkMRMLBezierSurfaceNode::InitializationMode``.  Same TODO
  /// applies as for ``ResectionState`` above.
  enum InitializationMode
  {
    SlicingPlane = 0,
    DistanceSpheroid = 1,
    InitializationMode_Last
  };

  /// Default NURBS control-grid side length (``DegreeU + 1`` for the
  /// default cubic degree — i.e. the minimum valid grid size).
  /// Typed ``int`` (matching ``vtkMRMLBezierSurfaceNode::DefaultGridSize``)
  /// for sign-clean iteration idioms at call sites.
  static constexpr int DefaultGridSize = 4;

  /// Default NURBS basis degree.  Per ADR-0022 §"Default degree" —
  /// cubic NURBS is the surgical-planning canonical (matches
  /// degree-3 Bezier; matches CAD-industry default).
  static constexpr int DefaultDegree = 3;

  /// Minimum / maximum NURBS basis degree admitted in v2.1 per
  /// ADR-0022 §"IVar roster".  Higher-than-degree-3 NURBS deferred
  /// to a future ADR (numerical stability + thin clinical demand).
  static constexpr int MinDegree = 2;
  static constexpr int MaxDegree = 3;

  //--------------------------------------------------------------------------
  // MRMLNode methods
  //--------------------------------------------------------------------------
  vtkMRMLNode* CreateNodeInstance() override;

  /// Get node XML tag name (like Volume, Model).  No ``Liver`` prefix
  /// per the convention established by ``vtkMRMLBezierSurfaceNode``
  /// (BezierSurface / NurbsSurface — type names without a module
  /// prefix).
  const char* GetNodeTagName() override { return "NurbsSurface"; }

  /// Read node attributes from XML.
  void ReadXMLAttributes(const char** atts) override;

  /// Write this node's information to a MRML file in XML format.
  void WriteXML(ostream& of, int indent) override;

  /// Copy node content.  Rejects cross-type sources (Bezier source →
  /// NURBS sink) with a ``vtkErrorMacro`` — the two surface types
  /// carry different IVar rosters (degrees, knots, weights are
  /// NURBS-only) and a meaningful cross-type copy needs a fitter, not
  /// a simple field-by-field copy.  Same rejection contract as
  /// ``vtkMRMLBezierSurfaceNode::CopyContent``.
  void CopyContent(vtkMRMLNode* anode, bool deepCopy = true) override;

  //--------------------------------------------------------------------------
  // State machine — same matrix as ``vtkMRMLBezierSurfaceNode`` per
  // ADR-0019 (the matrix is surface-type-agnostic).
  //--------------------------------------------------------------------------

  /// Resection state (Init / Planning / Confirmed).  Persisted in XML.
  /// Transition matrix per ADR-0019: Init→Planning, Planning↔Confirmed
  /// allowed; every other non-self transition rejected with a
  /// ``vtkWarningMacro``.  Self-assign is a no-op.
  vtkGetMacro(State, int);
  void SetState(int state);

  /// Internal flag — set during XML / JSON load so the read path can
  /// bypass the ADR-0019 transition guards and load a serialised
  /// Confirmed-state file into a freshly-Init sink.  Public setter so
  /// the storage node (different translation unit, not a friend) can
  /// drive the flag.  Treat as an internal API.
  vtkGetMacro(LoadingFromXML, bool);
  vtkSetMacro(LoadingFromXML, bool);

  /// Initialization mode (SlicingPlane / DistanceSpheroid).  Mutable
  /// in any state per ADR-0014 §1.
  vtkGetMacro(InitMode, int);
  vtkSetMacro(InitMode, int);

  /// Enum string converters — required by the XML enum macros + the
  /// storage node's JSON dispatch.
  static const char* GetStateAsString(int state);
  static int GetStateFromString(const char* name);
  static const char* GetInitModeAsString(int mode);
  static int GetInitModeFromString(const char* name);

  //--------------------------------------------------------------------------
  // NURBS shape — Rows × Cols control grid plus DegreeU × DegreeV
  // basis, KnotsU + KnotsV vectors, and Weights.
  //
  // Validation enforces:
  //   - 2 ≤ DegreeU, DegreeV ≤ 3 (ADR-0022 §"IVar roster")
  //   - Rows ≥ DegreeU + 1 and Cols ≥ DegreeV + 1 (non-empty basis)
  //   - len(KnotsU) == Rows + DegreeU + 1; symmetric for KnotsV
  //   - len(Weights) == Rows * Cols
  //   - every weight strictly positive
  //
  // Cross-IVar setters route through these validators; a setter that
  // would leave the node in an inconsistent state (e.g. Rows < the
  // current DegreeU + 1) is rejected with ``vtkErrorMacro`` and no
  // ``Modified()`` emission.
  //--------------------------------------------------------------------------

  /// Number of control-grid rows (M).  Default ``DefaultGridSize``.
  /// Must satisfy ``Rows >= DegreeU + 1``; rejected with
  /// ``vtkErrorMacro`` otherwise.  On accepted change, knots /
  /// weights / control grid are regenerated to clamped-uniform /
  /// all-1.0 / zeros respectively (analogous to
  /// ``vtkMRMLBezierSurfaceNode::SetRows`` — a shape change discards
  /// the in-flight grid).
  vtkGetMacro(Rows, unsigned int);
  void SetRows(unsigned int rows);

  /// Number of control-grid columns (N).  Default ``DefaultGridSize``.
  /// Must satisfy ``Cols >= DegreeV + 1``; same regeneration on
  /// accepted change as ``SetRows``.
  vtkGetMacro(Cols, unsigned int);
  void SetCols(unsigned int cols);

  /// Square-grid convenience setter — set both ``Rows`` and ``Cols``
  /// to ``n`` atomically.  Validated against
  /// ``n >= DegreeU + 1 && n >= DegreeV + 1``.  Regenerates knots +
  /// weights + control grid to defaults.
  void SetSize(unsigned int n);

  /// Basis degree along U.  Default ``DefaultDegree`` (3).  Allowed
  /// values for v2.1: ``{MinDegree, MaxDegree}`` = ``{2, 3}``.  Must
  /// also satisfy ``DegreeU + 1 <= Rows`` (non-empty basis); rejected
  /// with ``vtkErrorMacro`` otherwise.  On accepted change, ``KnotsU``
  /// is regenerated to clamped-uniform.
  vtkGetMacro(DegreeU, unsigned int);
  void SetDegreeU(unsigned int degree);

  /// Basis degree along V.  Same validation + regeneration as
  /// ``SetDegreeU``.
  vtkGetMacro(DegreeV, unsigned int);
  void SetDegreeV(unsigned int degree);

  /// Square-degree convenience setter — set both ``DegreeU`` and
  /// ``DegreeV`` to ``d`` atomically.  Validated against
  /// ``{MinDegree, MaxDegree}`` + ``d + 1 <= Rows && d + 1 <= Cols``.
  void SetDegree(unsigned int d);

  /// Per-node control-grid byte count, ``3 * Rows * Cols``.
  unsigned int GetControlGridLength() const { return 3u * this->Rows * this->Cols; }

  /// Expected length of ``KnotsU`` given current ``Rows`` + ``DegreeU``
  /// (de Boor convention: ``Rows + DegreeU + 1``).
  unsigned int GetKnotsULength() const { return this->Rows + this->DegreeU + 1u; }

  /// Expected length of ``KnotsV`` given current ``Cols`` + ``DegreeV``.
  unsigned int GetKnotsVLength() const { return this->Cols + this->DegreeV + 1u; }

  /// Expected length of ``Weights`` given current shape (``Rows * Cols``).
  unsigned int GetWeightsLength() const { return this->Rows * this->Cols; }

  /// Set the control grid from a flat array.  ``values`` must point at
  /// at least ``GetControlGridLength()`` doubles.  Returns true on
  /// success; false on null pointer.
  bool SetControlGrid(const double* values);

  /// Read the control grid as a flat row-major array.  Pointer is
  /// valid until the next shape mutation.
  const double* GetControlGrid() const { return this->ControlGrid.data(); }

  /// Set ``KnotsU`` from a flat array.  ``values`` must point at at
  /// least ``length`` doubles, and ``length`` must equal
  /// ``GetKnotsULength()`` for the current shape.  Returns true on
  /// success; false on null pointer, length mismatch, or invariant
  /// violation.  The setter validates the on-disk invariant
  /// (non-decreasing, clamped at both ends to ``degree + 1`` equal
  /// repeats, in ``[0, 1]``) via ``ValidateKnotsClampedMonotonic`` —
  /// callers passing arbitrary numeric arrays get an explicit rejection
  /// rather than a silently-accepted malformed surface (ADR-0022
  /// §"Validation rules per surface type — NURBS").
  bool SetKnotsU(const double* values, std::size_t length);

  /// Read ``KnotsU`` as a flat array; length is ``GetKnotsULength()``.
  const double* GetKnotsU() const { return this->KnotsU.data(); }
  const std::vector<double>& GetKnotsUVector() const { return this->KnotsU; }

  /// Same as ``SetKnotsU`` for ``KnotsV``.
  bool SetKnotsV(const double* values, std::size_t length);
  const double* GetKnotsV() const { return this->KnotsV.data(); }
  const std::vector<double>& GetKnotsVVector() const { return this->KnotsV; }

  /// Set ``Weights`` from a flat array.  ``length`` must equal
  /// ``GetWeightsLength()`` for the current shape.  Every weight must
  /// be strictly positive; a zero or negative weight rejects the call
  /// with ``vtkErrorMacro`` and no state change.  Returns true on
  /// success; false on null pointer, length mismatch, or invalid
  /// value.
  bool SetWeights(const double* values, std::size_t length);

  /// Read ``Weights`` as a flat array; length is ``GetWeightsLength()``.
  const double* GetWeights() const { return this->Weights.data(); }
  const std::vector<double>& GetWeightsVector() const { return this->Weights; }

  /// Validate that ``knots`` describes a clamped, non-decreasing
  /// vector with values in ``[0, 1]`` — the on-disk invariant for a
  /// clamped-uniform NURBS knot vector per ADR-0022 §"Validation
  /// rules per surface type — NURBS".
  ///
  /// Length is **not** validated here — the caller is expected to
  /// size-check (``knots.size() == axisCount + degree + 1``) before
  /// invoking the helper.  Validation performed:
  ///   - clamping: the first ``degree + 1`` entries are equal AND the
  ///     last ``degree + 1`` entries are equal.
  ///   - monotonicity: ``knots[i] <= knots[i+1]`` for every ``i``.
  ///   - range: ``knots.front() >= 0.0`` AND ``knots.back() <= 1.0``.
  ///
  /// On rejection, ``error`` carries a diagnostic; on success it is
  /// left untouched.  Returns ``true`` iff the vector satisfies every
  /// invariant.  v2.1 admits only clamped-uniform parameterisation
  /// (range pinned to ``[0, 1]``); OPEN-UNIFORM and other
  /// parameterisations are deferred to a future ADR.
  static bool ValidateKnotsClampedMonotonic(const std::vector<double>& knots, unsigned int degree, std::string& error);

  /// Regenerate ``KnotsU`` and ``KnotsV`` to clamped-uniform vectors
  /// from the current ``Rows``, ``Cols``, ``DegreeU``, ``DegreeV``.
  /// De Boor convention: ``DegreeU + 1`` zeros at the start,
  /// ``Rows - DegreeU - 1`` uniformly-spaced interior knots in
  /// ``(0, 1)``, ``DegreeU + 1`` ones at the end (same for V).  Used
  /// by the constructor + by every shape / degree setter to keep
  /// knots consistent on automatic regeneration; also exposed as a
  /// public helper for callers that have edited ``Rows`` / ``Cols``
  /// / degrees directly via the storage layer and want a reset.
  /// Emits ``Modified()``.
  void ResetKnotsToClampedUniform();

protected:
  vtkMRMLNurbsSurfaceNode();
  ~vtkMRMLNurbsSurfaceNode() override;

private:
  vtkMRMLNurbsSurfaceNode(const vtkMRMLNurbsSurfaceNode&) = delete;
  void operator=(const vtkMRMLNurbsSurfaceNode&) = delete;

  /// State / mode enums stored as int (so the standard XML int / enum
  /// macros work).  ``InitMode`` rather than ``InitializationMode``
  /// avoids shadowing the enum of that name inside class scope (same
  /// rationale as ``vtkMRMLBezierSurfaceNode``).
  int State;
  int InitMode;

  /// Control-polygon shape.
  unsigned int Rows;
  unsigned int Cols;

  /// Basis degrees.
  unsigned int DegreeU;
  unsigned int DegreeV;

  /// Knot vectors (clamped-uniform at construction).
  std::vector<double> KnotsU;
  std::vector<double> KnotsV;

  /// Rational weights (all 1.0 at construction → non-rational
  /// B-spline degenerate case).
  std::vector<double> Weights;

  /// Control grid, row-major (row, col) → flat[row * Cols + col] * 3
  /// + {0, 1, 2}.  Same layout as ``vtkMRMLBezierSurfaceNode::ControlGrid``.
  std::vector<double> ControlGrid;

  /// Internal flag — set true during XML / JSON load to bypass the
  /// ADR-0019 transition-matrix guard so a Confirmed-state serialised
  /// file loads into a fresh ``Init`` sink.  Public setter exposed
  /// for the storage node; treat as internal API.
  bool LoadingFromXML;
};

#endif //__vtkmrmlnurbssurfacenode_h_

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

#ifndef __vtkmrmlbeziersurfacenode_h_
#define __vtkmrmlbeziersurfacenode_h_

#include "vtkSlicerLiverResectionsModuleMRMLExport.h"

// MRML includes
#include <vtkMRMLDisplayableNode.h>

// VTK includes
#include <vtkNew.h>
#include <vtkSetGet.h>

// STD includes
#include <vector>

/**
 * \class vtkMRMLBezierSurfaceNode
 *
 * \brief Data-only MRML node carrying the geometry of a Bezier-surface
 *        resection plan, plus the read-only audit trail of the
 *        Init-mode primitive that seeded it.
 *
 * This node is part of the LayerDM Pipeline pattern committed by
 * [ADR-0013](../../Docs/adr/0013-layerdm-pipeline-pattern.md): a
 * \b data-only node carrying geometry and clinically authoritative
 * metadata, paired with a matching ``vtkMRMLBezierSurfaceDisplayNode``
 * that owns all display-side fields (colours, opacity, grid divisions,
 * widget visibility, …).  Decoration leaves the data node entirely
 * (see ADR-0013 §8).
 *
 * The shape of the data is fixed by
 * [ADR-0014 §1](../../Docs/adr/0014-livermarkups-dissolution.md)
 * and [ADR-0018 §1](../../Docs/adr/0018-nurbs-extension-surface.md):
 *
 * - A **Bezier control grid of shape (Rows × Cols)** — the surface's
 *   single editable geometry in the Planning state.  Per ADR-0018 §1
 *   the valid Bezier sizes for v2.0.0 are **square only** and
 *   restricted to ``(Rows, Cols) ∈ {(3, 3), (4, 4)}`` (9 or 16
 *   control points).  Defaults to 4×4 — the pre-ADR-0018 hard-coded
 *   case.  Control points group by ring role per ADR-0014 §3 /
 *   ADR-0018 §1: 4 corners + ``2*(M-2)+2*(N-2)`` edges +
 *   ``(M-2)*(N-2)`` interior.  Storage is row-major in (u, v) order
 *   with 3 doubles per control point.
 * - A **state enum** (``Init`` / ``Planning``) and an
 *   **InitializationMode** enum (``SlicingPlane`` / ``DistanceSpheroid``),
 *   tracked explicitly per ADR-0013 §4 so the implicit-state-via-
 *   scene-contents anti-pattern retires.
 * - **Read-only init-mode subordinate data** per ADR-0014 §4 — once
 *   ``State == Planning``, the originating init points and the
 *   plane / spheroid parameters that produced the Bezier fit persist
 *   as audit data.  *There is no Planning→Init drop-back*: the
 *   read-only data round-trips through storage so the UI can annotate
 *   "what fit produced this geometry", but it is no longer editable.
 *
 * \par MRML node shape
 *
 * Two nodes participate in the Bezier-surface concept:
 *
 *   - ``vtkMRMLBezierSurfaceNode`` (this class) — \b data: the 4×4
 *     control grid, init-mode audit data, state machine.
 *   - ``vtkMRMLBezierSurfaceDisplayNode`` — \b display: all
 *     decoration fields (colours, opacity, grid visibility,
 *     widget visibility, …) per ADR-0013 §8.
 *
 * This is the structural payoff of the LayerDM migration relative to
 * the legacy ``vtkMRMLLiverResectionNode``, which today carries both
 * geometry and ~30 display fields directly.  During v2.0.0 both shapes
 * coexist: the legacy node remains in place for the existing path,
 * the two new nodes carry the LayerDM Pipeline path.  The collapse
 * (LiverMarkups retirement, cross-reference cleanup) is task T2.7 —
 * \b not this PR.
 *
 * \par State enum parity with vtkMRMLLiverResectionNode
 *
 * The legacy ``vtkMRMLLiverResectionNode`` has its own ``ResectionState``
 * (``Initialization`` / ``Deformation`` / ``Completed``) and
 * ``InitializationMode`` (``Flat`` / ``Curved``) enums.  The names
 * carry their pre-LayerDM history; ADR-0014 §1 / PR #317 names the
 * new enums explicitly as ``Init`` / ``Planning`` and
 * ``SlicingPlane`` / ``DistanceSpheroid``.  These are *parallel*
 * during v2.0.0; T2.7 will collapse to the new names everywhere.
 */
class VTK_SLICER_LIVERRESECTIONS_MODULE_MRML_EXPORT vtkMRMLBezierSurfaceNode : public vtkMRMLDisplayableNode
{
public:
  static vtkMRMLBezierSurfaceNode* New();
  vtkTypeMacro(vtkMRMLBezierSurfaceNode, vtkMRMLDisplayableNode);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  /// Resection state machine (per ADR-0013 §4 and ADR-0019).
  ///
  /// Three-state automaton:
  ///
  /// \verbatim
  ///   [*] -> Init -> Planning <-> Confirmed
  /// \endverbatim
  ///
  /// - ``Init``      — node exists, init-mode audit data is editable,
  ///                   the Bezier control grid is not yet fitted.
  /// - ``Planning``  — control polygon is editable, init-mode audit
  ///                   data is read-only (ADR-0014 §4), the full
  ///                   resection surface renders (no parenchyma trim).
  /// - ``Confirmed`` — control polygon is frozen, the parenchyma-trim
  ///                   shader is active (``uResectionClipOut == 1`` on
  ///                   ``vtkOpenGLBezierResectionPolyDataMapper``); the
  ///                   surgeon can revise back to ``Planning``.
  ///
  /// ``SetState`` enforces the transition matrix from ADR-0019:
  ///
  ///   - Init      -> Planning   allowed (one-way per ADR-0014 §4).
  ///   - Planning  -> Confirmed  allowed.
  ///   - Confirmed -> Planning   allowed (round-trip).
  ///   - Init      -> Confirmed  forbidden (must traverse Planning).
  ///   - Planning  -> Init       forbidden (ADR-0014 §4).
  ///   - Confirmed -> Init       forbidden (audit data permanent).
  ///
  /// Forbidden transitions emit a ``vtkWarningMacro`` and reject the
  /// change (mirrors the Planning -> Init rejection precedent set by
  /// the ADR-0014 §4 read-only audit-data rule).
  ///
  /// Enum integer values are pinned explicitly so that a future
  /// reorder or insertion does not silently shift any Python or C++
  /// caller that compares against ``cls.Planning`` as a literal.  XML
  /// serialisation goes through the name-string converter
  /// (``GetStateAsString``) and is independent of these values; the
  /// pinning is purely a defensive measure on the in-memory ABI.
  enum ResectionState
  {
    Init = 0,
    Planning = 1,
    Confirmed = 2,
    ResectionState_Last
  };

  /// Init-mode dispatch (per ADR-0014 §1).
  ///
  /// Integer values pinned for the same reason as ``ResectionState``
  /// above.
  enum InitializationMode
  {
    SlicingPlane = 0,
    DistanceSpheroid = 1,
    InitializationMode_Last
  };

  /// Default Bezier control-grid side length (degree-3 Bernstein
  /// basis — the v1 hard-coded case).  Retained as a literal default
  /// for callers / tests that want the historical 4×4 grid without
  /// instantiating a node first.  Per ADR-0018 §1 the runtime shape
  /// is now carried by the ``Rows`` / ``Cols`` IVars; valid sizes for
  /// v2.0.0 are restricted to the square shapes
  /// ``(Rows, Cols) ∈ {(3, 3), (4, 4)}``.
  ///
  /// Typed ``int`` (rather than ``unsigned int``) so the existing
  /// call-site idiom ``for (int i = 0; i < ControlGridSize; ++i)``
  /// stays sign-clean.  The setter argument types use ``unsigned
  /// int`` to mirror VTK conventions for shape-like parameters.
  static constexpr int DefaultGridSize = 4;

  /// Minimum / maximum Bezier control-grid side length admitted in
  /// v2.0.0 per ADR-0018 §1.  Both ends are inclusive; the runtime
  /// validation in ``SetRows`` / ``SetCols`` / ``SetSize`` rejects
  /// values outside this range.  Larger sizes are NURBS-territory
  /// and arrive with the v2.1 NURBS sibling (ADR-0018 §3).
  static constexpr int MinGridSize = 3;
  static constexpr int MaxGridSize = 4;

  /// Backwards-compatibility alias for the v1 4×4 case.  Existing
  /// callers reading ``GridSize`` as a compile-time literal continue
  /// to see ``4`` (the default).  Per-node runtime shape is now
  /// queried via ``GetRows()`` / ``GetCols()``.
  static constexpr int GridSize = DefaultGridSize;

  /// Maximum number of doubles in the control grid across all
  /// admitted shapes (``MaxGridSize * MaxGridSize * 3 == 48`` —
  /// i.e. the 4×4 case).  Reader code that allocates a stack buffer
  /// for the largest admitted payload uses this constant.  The
  /// **per-node** byte count is ``3 * Rows * Cols`` and is computed
  /// from the IVars via ``GetControlGridLength()`` below.
  static constexpr int MaxControlGridSize = MaxGridSize * MaxGridSize * 3;

  /// Backwards-compatibility alias for the v1 48-double layout.
  /// Existing tests + storage code that reference ``ControlGridSize``
  /// as a compile-time literal continue to see the 4×4 byte count.
  /// Per ADR-0018 §1 the live length is ``3 * Rows * Cols`` and is
  /// available at runtime via ``GetControlGridLength()``.
  static constexpr int ControlGridSize = DefaultGridSize * DefaultGridSize * 3;

  //--------------------------------------------------------------------------
  // MRMLNode methods
  //--------------------------------------------------------------------------
  vtkMRMLNode* CreateNodeInstance() override;

  /// Get node XML tag name (like Volume, Model).
  const char* GetNodeTagName() override { return "BezierSurface"; }

  /// Read node attributes from XML.
  void ReadXMLAttributes(const char** atts) override;

  /// Write this node's information to a MRML file in XML format.
  void WriteXML(ostream& of, int indent) override;

  /// Copy node content (excludes basic data, such as name and node references).
  /// \sa vtkMRMLNode::CopyContent
  void CopyContent(vtkMRMLNode* anode, bool deepCopy = true) override;

  /// Spawn a ``vtkMRMLBezierSurfaceDisplayNode`` and observe it
  /// as this data node's default display node.  No-op if a display
  /// node is already attached.  Requires the data node to be in a
  /// scene; emits an error and returns otherwise.
  void CreateDefaultDisplayNodes() override;

  //--------------------------------------------------------------------------
  // State machine
  //--------------------------------------------------------------------------

  /// Resection state (Init / Planning / Confirmed).  Persisted in XML.
  ///
  /// ``SetState`` enforces the ADR-0019 transition matrix (which
  /// subsumes the ADR-0014 §4 Planning -> Init invariant): the
  /// Init -> Planning, Planning -> Confirmed, and Confirmed -> Planning
  /// transitions are allowed; every other non-self transition is
  /// rejected with a ``vtkWarningMacro``.  Setting the same state is a
  /// no-op (no ``Modified()`` emitted) so the macro-generated
  /// short-circuit semantics are preserved.  See the ``ResectionState``
  /// enum docstring for the full matrix.
  vtkGetMacro(State, int);
  void SetState(int state);

  /// ``LoadingFromXML`` — internal flag that exempts the ADR-0014 §4
  /// audit-data setters and the ADR-0019 ``SetState`` transition
  /// matrix from the public-API guards for the duration of a
  /// scene/storage read.  Set automatically by ``ReadXMLAttributes``;
  /// also set by ``vtkMRMLBezierSurfaceStorageNode::ReadJson`` for
  /// JSON-driven loads so a Confirmed-state ``.lrp.json`` round-trips
  /// into a fresh sink (sink starts at ``Init``; without the bypass,
  /// ``SetState(Confirmed)`` is rejected as an illegal Init→Confirmed
  /// transition).  Public setter so the storage node — which is in a
  /// different translation unit and not a friend — can drive the
  /// flag.  Treat as an internal API: callers other than the storage
  /// reader path should NOT touch it.
  vtkGetMacro(LoadingFromXML, bool);
  vtkSetMacro(LoadingFromXML, bool);

  /// Initialization mode (SlicingPlane / DistanceSpheroid).  Persisted
  /// in XML.  Meaningful for both States: in Init it drives the
  /// active Representation; in Planning it tags which init-mode audit
  /// data was captured.
  ///
  /// The accessors are named ``GetInitMode`` / ``SetInitMode`` —
  /// matching the legacy ``vtkMRMLLiverResectionNode``'s like-named
  /// property — because the property name "InitializationMode" would
  /// collide with the enum of the same name in the wrapping-parser's
  /// view of class scope.  T2.7 will collapse to a single accessor
  /// pair when the legacy node retires.
  vtkGetMacro(InitMode, int);
  vtkSetMacro(InitMode, int);

  /// Enum string converters — required by the XML enum macros.
  /// Named on the property (``State`` / ``InitMode``) so the macros
  /// in WriteXML / ReadXMLAttributes pick them up via the ``##``
  /// concatenation rules they expect.
  static const char* GetStateAsString(int state);
  static int GetStateFromString(const char* name);
  static const char* GetInitModeAsString(int mode);
  static int GetInitModeFromString(const char* name);

  //--------------------------------------------------------------------------
  // Surgeon-facing ordering metadata (ADR-0023 §"Persistence").
  //
  // ``OrderIndex`` is the zero-based position of this resection plan in
  // the surgeon-defined operative sequence.  A sentinel value of
  // ``-1`` means "unordered" (the default for a freshly-created node).
  // The field round-trips through the v2 ``.lrp.json`` storage path
  // (see ``vtkMRMLBezierSurfaceStorageNode.cxx`` schema-header block)
  // and through XML scene serialisation.
  //--------------------------------------------------------------------------

  /// Operative-sequence position (zero-based).  Default ``-1`` =
  /// unordered.  No transition guard — this is an editable surgeon-
  /// facing field independent of the ``State`` machine; the planner
  /// can reorder resections in any state.
  vtkGetMacro(OrderIndex, int);
  vtkSetMacro(OrderIndex, int);

  //--------------------------------------------------------------------------
  // Bezier control grid — (Rows × Cols × 3 row-major)
  //
  // Per ADR-0018 §1 the control-polygon shape is square and chosen
  // from ``(Rows, Cols) ∈ {(3, 3), (4, 4)}``; defaults to 4×4 (the
  // pre-ADR-0018 hard-code).  Storage backed by a ``std::vector``
  // sized ``3 * Rows * Cols`` doubles — 27 for 3×3, 48 for 4×4.
  //--------------------------------------------------------------------------

  /// Number of control-grid rows (M).  Default ``4``.  Per ADR-0018
  /// §1, square only — ``SetRows`` rejects ``Rows != Cols`` and
  /// values outside ``[MinGridSize, MaxGridSize]`` with a
  /// ``vtkErrorMacro`` and no ``Modified()`` emission.  Use
  /// ``SetSize(unsigned int)`` to change both axes simultaneously
  /// (the typical call path).
  vtkGetMacro(Rows, unsigned int);
  void SetRows(unsigned int rows);

  /// Number of control-grid columns (N).  Default ``4``.  Same
  /// constraints as ``SetRows``.
  vtkGetMacro(Cols, unsigned int);
  void SetCols(unsigned int cols);

  /// Square-grid convenience setter — set both ``Rows`` and ``Cols``
  /// to ``n`` atomically.  Validated against
  /// ``[MinGridSize, MaxGridSize]`` per ADR-0018 §1.  Resizes the
  /// internal control-point buffer to ``3 * n * n`` doubles and
  /// resets it to zero (clinical workflow: a size change discards
  /// the in-flight grid and starts fresh; documented in
  /// ADR-0018 §1).  No-op when ``n`` already matches ``Rows`` and
  /// ``Cols`` simultaneously.
  void SetSize(unsigned int n);

  /// Per-node control-grid byte count, i.e. ``3 * Rows * Cols``.
  /// Equals 27 for 3×3 and 48 for 4×4.  Storage code that walks the
  /// flat buffer uses this to bound the loop; the compile-time
  /// ``ControlGridSize`` is the v1 default and is preserved as a
  /// backwards-compatibility alias only.
  unsigned int GetControlGridLength() const { return 3u * this->Rows * this->Cols; }

  /// Set the Bezier control grid from a flat (``3 * Rows * Cols``-
  /// double) array laid out row-major in (u, v) order with 3 doubles
  /// per control point.  Control points group by ring role per
  /// ADR-0018 §1 / ADR-0014 §3: 4 corners + ``2*(M-2)+2*(N-2)``
  /// edges + ``(M-2)*(N-2)`` interior.
  ///
  /// The pointer must reference at least ``GetControlGridLength()``
  /// doubles.  Returns true on success; false on null pointer.
  bool SetControlGrid(const double* values);

  /// Read the Bezier control grid as a flat row-major array.  Length
  /// is ``GetControlGridLength()`` (3 * Rows * Cols).  Valid for the
  /// lifetime of the node, but a subsequent ``SetSize`` /
  /// ``SetRows`` / ``SetCols`` call resizes the underlying buffer
  /// and invalidates previously-returned pointers.
  const double* GetControlGrid() const { return this->ControlGrid.data(); }

  /// Convenience overload — return a const reference to the
  /// ``std::vector`` backing the grid (for C++ callers that prefer
  /// typed iteration over a raw pointer).  Same invalidation
  /// semantics as ``GetControlGrid()``.
  const std::vector<double>& GetControlGridVector() const { return this->ControlGrid; }

  //--------------------------------------------------------------------------
  // Init-mode subordinate data — SlicingPlane (read-only after Init→Planning)
  //
  // Every setter on this block enforces the ADR-0014 §4 read-only
  // invariant: once ``State == Planning``, the originating init data
  // becomes audit-only.  Mutating calls in Planning emit a
  // ``vtkWarningMacro`` and return without changing state or firing
  // ``Modified()``.  See ``SetState`` for the Init→Planning transition
  // contract (one-way).
  //--------------------------------------------------------------------------

  /// Set one of the two SlicingPlane init points.  Index must be 0 or
  /// 1.  Returns true on success; false on out-of-range, null pointer,
  /// or read-only rejection (``State == Planning``, see ADR-0014 §4).
  bool SetSlicingPlaneInitPoint(int index, const double point[3]);

  /// Get a SlicingPlane init point by index (0 or 1).  Returns nullptr
  /// on out-of-range.
  const double* GetSlicingPlaneInitPoint(int index) const;

  /// Plane origin (3 doubles).  Rejected when ``State == Planning``.
  void SetSlicingPlaneOrigin(double x, double y, double z);
  void SetSlicingPlaneOrigin(const double xyz[3]);
  vtkGetVector3Macro(SlicingPlaneOrigin, double);

  /// Plane normal (3 doubles).  Rejected when ``State == Planning``.
  void SetSlicingPlaneNormal(double x, double y, double z);
  void SetSlicingPlaneNormal(const double xyz[3]);
  vtkGetVector3Macro(SlicingPlaneNormal, double);

  //--------------------------------------------------------------------------
  // Init-mode subordinate data — DistanceSpheroid (read-only after
  // Init→Planning).
  //
  // Same ADR-0014 §4 read-only invariant as the SlicingPlane block
  // above.
  //--------------------------------------------------------------------------

  /// Number of DistanceSpheroid init points (2 or more, per ADR-0014 §1).
  /// Defaults to 0 (uninitialised).
  vtkGetMacro(NumberOfDistanceSpheroidInitPoints, int);

  /// Reserve N slots for the DistanceSpheroid init points.  N must be
  /// >= 2 to be semantically meaningful, but lower values (including
  /// 0 for clear-on-load) are accepted to support partial XML reads.
  /// All slots are zero-initialised.  Rejected when
  /// ``State == Planning``.
  void SetNumberOfDistanceSpheroidInitPoints(int n);

  /// Set the DistanceSpheroid init point at ``index``.  Index must be
  /// in [0, GetNumberOfDistanceSpheroidInitPoints()).  Returns true on
  /// success; false on out-of-range, null pointer, or read-only
  /// rejection.
  bool SetDistanceSpheroidInitPoint(int index, const double point[3]);

  /// Get the DistanceSpheroid init point at ``index``.  Returns
  /// nullptr on out-of-range.
  const double* GetDistanceSpheroidInitPoint(int index) const;

  /// Spheroid center (3 doubles).  Rejected when ``State == Planning``.
  void SetDistanceSpheroidCenter(double x, double y, double z);
  void SetDistanceSpheroidCenter(const double xyz[3]);
  vtkGetVector3Macro(DistanceSpheroidCenter, double);

  /// Spheroid radii (each constrained to >= 0).  Three independent
  /// scalars rather than a vector3 because the storage path (ADR-0014
  /// §5) emits them as named JSON fields and the Pipeline reads them
  /// individually for the spheroid quadric.  Rejected when
  /// ``State == Planning``.
  vtkGetMacro(DistanceSpheroidRadiusX, double);
  void SetDistanceSpheroidRadiusX(double r);

  vtkGetMacro(DistanceSpheroidRadiusY, double);
  void SetDistanceSpheroidRadiusY(double r);

  vtkGetMacro(DistanceSpheroidRadiusZ, double);
  void SetDistanceSpheroidRadiusZ(double r);

protected:
  vtkMRMLBezierSurfaceNode();
  ~vtkMRMLBezierSurfaceNode() override;

private:
  vtkMRMLBezierSurfaceNode(const vtkMRMLBezierSurfaceNode&) = delete;
  void operator=(const vtkMRMLBezierSurfaceNode&) = delete;

  /// State / mode enums stored as int (so the standard XML int / enum
  /// macros work).  The ``InitMode`` member is *not* named
  /// ``InitializationMode`` to avoid shadowing the enum of that name
  /// inside class scope (see the GetInitializationMode/
  /// SetInitializationMode accessor pair above).
  int State;
  int InitMode;

  /// Surgeon-facing operative-sequence position.  Default ``-1`` =
  /// unordered (see the accessor docstring above).
  int OrderIndex;

  /// Control-polygon shape (Rows × Cols).  Default 4×4 (the
  /// pre-ADR-0018 hard-coded case).  Per ADR-0018 §1, restricted to
  /// the square shapes ``{(3, 3), (4, 4)}`` for v2.0.0.
  unsigned int Rows;
  unsigned int Cols;

  /// (Rows × Cols × 3) control grid laid out row-major in (u, v).
  /// Sized at construction to ``3 * Rows * Cols`` doubles and
  /// resized in lock-step with ``SetRows`` / ``SetCols`` /
  /// ``SetSize``.
  std::vector<double> ControlGrid;

  /// SlicingPlane init data.  Two points fixed by ADR-0014 §1.
  double SlicingPlaneInitPoints[2][3];
  double SlicingPlaneOrigin[3];
  double SlicingPlaneNormal[3];

  /// DistanceSpheroid init data.  Variable number of points per
  /// ADR-0014 §1 (2-or-more); stored as a flat std::vector to keep
  /// the storage path simple.
  int NumberOfDistanceSpheroidInitPoints;
  std::vector<double> DistanceSpheroidInitPoints;
  double DistanceSpheroidCenter[3];
  double DistanceSpheroidRadiusX;
  double DistanceSpheroidRadiusY;
  double DistanceSpheroidRadiusZ;

  /// Internal flag — set to true for the duration of
  /// ``ReadXMLAttributes`` so the ADR-0014 §4 read-only guards on the
  /// init-mode setters do not reject XML-driven loads of scenes that
  /// already serialise ``state="Planning"`` (the guards apply to
  /// public-API mutation; XML deserialisation is internal load).  The
  /// flag is reset at the end of ``ReadXMLAttributes``.
  bool LoadingFromXML;
};

#endif //__vtkmrmlbeziersurfacenode_h_

/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) Oslo University Hospital. All rights reserved.

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
#include <array>
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
 * [ADR-0014 §1](../../Docs/adr/0014-livermarkups-dissolution.md):
 *
 * - A **4×4 Bezier control grid** (48 doubles, row-major) — the surface's
 *   single editable geometry in the Planning state.  Sixteen control
 *   points (per ADR-0014 §3: corners 4 + edges 8 + interior 4) define
 *   a single degree-3 Bernstein patch.  Matches the legacy
 *   ``vtkMRMLMarkupsBezierSurfaceNode::RequiredNumberOfControlPoints
 *   == 16`` and the corrected degree-3 characterisation landed on
 *   ``preview`` by PR #342.
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

  /// Resection state machine (per ADR-0013 §4).
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

  /// Bezier control-grid side length M (degree-3 Bernstein basis).
  /// Sixteen control points group by ring role per ADR-0014 §3:
  /// 4 corners + 8 edges + 4 interior.  Matches the legacy
  /// ``vtkMRMLMarkupsBezierSurfaceNode::RequiredNumberOfControlPoints
  /// == 16`` and the corrected degree-3 characterisation landed on
  /// ``preview`` by PR #342.
  static constexpr int GridSize = 4;

  /// Total number of doubles in the control grid (M * M * 3 = 48).
  static constexpr int ControlGridSize = GridSize * GridSize * 3;

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

  /// Resection state (Init / Planning).  Persisted in XML.
  ///
  /// ``SetState`` enforces the ADR-0014 §4 one-way invariant: the
  /// Init→Planning transition is allowed, but a Planning→Init drop-back
  /// is rejected (emits a ``vtkWarningMacro`` and leaves ``State``
  /// unchanged).  Setting the same state is a no-op (no ``Modified()``
  /// emitted) so the macro-generated short-circuit semantics are
  /// preserved.
  vtkGetMacro(State, int);
  void SetState(int state);

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
  // Bezier control grid (4×4×3 row-major, 48 doubles, degree-3)
  //--------------------------------------------------------------------------

  /// Set the 4×4 Bezier control grid from a flat (48-double) array
  /// laid out row-major in (u, v) order with 3 doubles per control
  /// point.  Sixteen control points (4 corners + 8 edges + 4 interior
  /// per ADR-0014 §3) define a single degree-3 Bernstein patch.
  ///
  /// The pointer must reference at least ``ControlGridSize`` doubles.
  /// Returns true on success; false on null pointer.
  bool SetControlGrid(const double* values);

  /// Read the 4×4 Bezier control grid as a flat (48-double) row-major
  /// array.  Valid for the lifetime of the node.
  const double* GetControlGrid() const { return this->ControlGrid.data(); }

  /// Convenience overload — return a const reference to the std::array
  /// backing the grid (for C++ callers that prefer typed access).
  const std::array<double, ControlGridSize>& GetControlGridArray() const { return this->ControlGrid; }

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

  /// 4×4×3 control grid laid out row-major in (u, v).
  std::array<double, ControlGridSize> ControlGrid;

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

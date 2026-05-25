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

  This file was originally developed for the Slicer-Liver extension as
  part of the wrapper-vs-carrier amendment to ADR-0014 and ADR-0023
  (2026-05-25); see also ADR-0018 amendment of the same date for the
  data-side abstraction rationale.

==============================================================================*/

#ifndef __vtkmrmlabstractparametricsurfacenode_h_
#define __vtkmrmlabstractparametricsurfacenode_h_

#include "vtkSlicerLiverResectionsModuleMRMLExport.h"

// MRML includes
#include <vtkMRMLDisplayableNode.h>

// VTK includes
#include <vtkSetGet.h>

// STD includes
#include <vector>

class vtkPolyData;

/**
 * \class vtkMRMLAbstractParametricSurfaceNode
 *
 * \brief Abstract base for the parametric-surface family
 *        (vtkMRMLBezierSurfaceNode today, vtkMRMLNurbsSurfaceNode in
 *        v2.1) carrying the field roster the two share plus a
 *        polymorphic dispatch pair.
 *
 * Per the 2026-05-25 wrapper-vs-carrier amendment to
 * [ADR-0023](../../Docs/adr/0023-unified-gui-stage-workflow.md)
 * §"Class abstraction for surfaces" and the corresponding amendment
 * to [ADR-0018](../../Docs/adr/0018-nurbs-extension-surface.md), the
 * data side of the parametric-surface family abstracts under this
 * base.  Bezier and NURBS share:
 *
 *   - Control-polygon shape (``Rows``, ``Cols``, ``ControlGrid``).
 *   - Init-mode dispatch (``InitMode`` enum) and the subordinate
 *     slicing-plane / distance-spheroid audit data.
 *   - The ``TargetOrganModelNodeID`` reference to the parenchyma
 *     model the surface is fitted against.
 *
 * They diverge in:
 *
 *   - The surface evaluator (Bernstein vs rational B-spline) — the
 *     ``EvaluateSurface(u, v)`` polymorphic method.
 *   - NURBS-only fields (``DegreeU``, ``DegreeV``, ``KnotsU``,
 *     ``KnotsV``, ``Weights``) — live on the v2.1 concrete subclass
 *     only.
 *
 * \par Non-instantiable
 *
 * ``vtkAbstractTypeMacro`` — no ``static New()`` is exposed.  The
 * constructor is ``protected``.  Callers reach the family through one
 * of the concrete subclasses.
 *
 * \par Non-storable
 *
 * ``CreateDefaultStorageNode()`` returns nullptr.  The surface's bulk
 * data persists through the wrapping ``vtkMRMLResectionPlanStorageNode``
 * (plan-rooted ``.lrp.json``); the surface has no independent storage
 * path.  See
 * ``Docs/design/resection-plan-architecture/03-storage-ownership.md``
 * §"Why surface is non-storable".
 *
 * \par See also
 *
 *   - ADR-0014 amendment 2026-05-25 §"Fourth layer: clinical/method
 *     wrapper".
 *   - ADR-0023 amendment 2026-05-25 §"Class abstraction for surfaces".
 *   - ADR-0018 amendment 2026-05-25 §"Data-side sibling framing
 *     superseded".
 *   - ``Docs/design/resection-plan-architecture/01-class-hierarchy.md``.
 */
class VTK_SLICER_LIVERRESECTIONS_MODULE_MRML_EXPORT vtkMRMLAbstractParametricSurfaceNode : public vtkMRMLDisplayableNode
{
public:
  vtkAbstractTypeMacro(vtkMRMLAbstractParametricSurfaceNode, vtkMRMLDisplayableNode);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  //--------------------------------------------------------------------------
  // Init-mode dispatch
  //--------------------------------------------------------------------------

  /// Init-mode dispatch.  Drives the active Representation in the
  /// Init phase and tags which init-mode audit data was captured in
  /// the Planning phase.
  enum InitializationMode
  {
    SlicingPlane = 0,
    DistanceSpheroid = 1,
    InitializationMode_Last
  };

  /// Enum string converters (used by the XML enum macros).
  static const char* GetInitModeAsString(int mode);
  static int GetInitModeFromString(const char* name);

  //--------------------------------------------------------------------------
  // Control-polygon shape — admitted sizes per ADR-0018 §1.
  //--------------------------------------------------------------------------

  /// Default Bezier control-grid side length (degree-3 Bernstein
  /// basis — the v1 hard-coded case).
  static constexpr int DefaultGridSize = 4;

  /// Minimum / maximum admitted Bezier control-grid side length per
  /// ADR-0018 §1.  Larger sizes are NURBS-territory.
  static constexpr int MinGridSize = 3;
  static constexpr int MaxGridSize = 4;

  /// Backwards-compatibility alias for the v1 4×4 case.
  static constexpr int GridSize = DefaultGridSize;

  /// Maximum number of doubles in the control grid across all
  /// admitted shapes (4×4 case = 48).  Stack-buffer sizing constant
  /// for reader code; the per-node live length is
  /// ``GetControlGridLength()``.
  static constexpr int MaxControlGridSize = MaxGridSize * MaxGridSize * 3;

  /// Backwards-compatibility alias for the v1 48-double layout.
  static constexpr int ControlGridSize = DefaultGridSize * DefaultGridSize * 3;

  //--------------------------------------------------------------------------
  // Polymorphic dispatch
  //--------------------------------------------------------------------------

  /// Concrete VTK class-name discriminator.  ``"Bezier"`` for
  /// ``vtkMRMLBezierSurfaceNode``; ``"NURBS"`` for the v2.1
  /// ``vtkMRMLNurbsSurfaceNode``.  Never nullptr.  Used by the plan-
  /// storage writer's ``surface.type`` field and by the resection-
  /// table label.
  virtual const char* GetSurfaceType() = 0;

  /// Sample the parametric surface at (u, v) ∈ [0, 1]^2.  Returns a
  /// newly-allocated ``vtkPolyData`` carrying the sampled points (and,
  /// optionally, triangulation).  Caller owns the returned object —
  /// wrap in ``vtkSmartPointer::Take`` to claim ownership.
  ///
  /// Bezier dispatches to a Bernstein polynomial evaluator; NURBS
  /// (v2.1) dispatches to a rational B-spline evaluator.  The
  /// signature is fixed by the polymorphic-interface contract and
  /// must not vary across subclasses.
  virtual vtkPolyData* EvaluateSurface(double u, double v) = 0;

  //--------------------------------------------------------------------------
  // MRMLNode methods
  //--------------------------------------------------------------------------

  /// Non-storable — the surface's bulk data persists through the
  /// wrapping ``vtkMRMLResectionPlanStorageNode``.  See class
  /// docstring §"Non-storable".
  vtkMRMLStorageNode* CreateDefaultStorageNode() override;

  /// Read shared field roster from XML attributes.  Subclasses chain
  /// to ``Superclass::ReadXMLAttributes`` and then add subtype-specific
  /// fields.
  void ReadXMLAttributes(const char** atts) override;

  /// Write shared field roster to XML.  Subclasses chain through
  /// ``Superclass::WriteXML``.
  void WriteXML(ostream& of, int indent) override;

  /// Copy the shared field roster from ``anode``.  Subclasses chain
  /// to ``Superclass::CopyContent`` then copy subtype-specific fields.
  void CopyContent(vtkMRMLNode* anode, bool deepCopy = true) override;

  //--------------------------------------------------------------------------
  // Control-polygon shape (ADR-0018 §1)
  //--------------------------------------------------------------------------

  vtkGetMacro(Rows, unsigned int);
  void SetRows(unsigned int rows);

  vtkGetMacro(Cols, unsigned int);
  void SetCols(unsigned int cols);

  /// Set both ``Rows`` and ``Cols`` atomically.  ADR-0018 §1
  /// validates the value is in ``[MinGridSize, MaxGridSize]``.
  void SetSize(unsigned int n);

  /// Per-node control-grid length, i.e. ``3 * Rows * Cols``.
  unsigned int GetControlGridLength() const { return 3u * this->Rows * this->Cols; }

  /// Set the control grid from a flat ``3 * Rows * Cols`` array.
  /// Pointer must reference at least ``GetControlGridLength()``
  /// doubles.  Returns true on success; false on null pointer.
  bool SetControlGrid(const double* values);

  /// Read the control grid as a flat row-major array.
  const double* GetControlGrid() const { return this->ControlGrid.data(); }

  /// Typed-iteration accessor.
  const std::vector<double>& GetControlGridVector() const { return this->ControlGrid; }

  //--------------------------------------------------------------------------
  // Init-mode subordinate — SlicingPlane
  //--------------------------------------------------------------------------

  bool SetSlicingPlaneInitPoint(int index, const double point[3]);
  const double* GetSlicingPlaneInitPoint(int index) const;

  void SetSlicingPlaneOrigin(double x, double y, double z);
  void SetSlicingPlaneOrigin(const double xyz[3]);
  vtkGetVector3Macro(SlicingPlaneOrigin, double);

  void SetSlicingPlaneNormal(double x, double y, double z);
  void SetSlicingPlaneNormal(const double xyz[3]);
  vtkGetVector3Macro(SlicingPlaneNormal, double);

  //--------------------------------------------------------------------------
  // Init-mode subordinate — DistanceSpheroid
  //--------------------------------------------------------------------------

  vtkGetMacro(NumberOfDistanceSpheroidInitPoints, int);
  void SetNumberOfDistanceSpheroidInitPoints(int n);

  bool SetDistanceSpheroidInitPoint(int index, const double point[3]);
  const double* GetDistanceSpheroidInitPoint(int index) const;

  void SetDistanceSpheroidCenter(double x, double y, double z);
  void SetDistanceSpheroidCenter(const double xyz[3]);
  vtkGetVector3Macro(DistanceSpheroidCenter, double);

  vtkGetMacro(DistanceSpheroidRadiusX, double);
  void SetDistanceSpheroidRadiusX(double r);

  vtkGetMacro(DistanceSpheroidRadiusY, double);
  void SetDistanceSpheroidRadiusY(double r);

  vtkGetMacro(DistanceSpheroidRadiusZ, double);
  void SetDistanceSpheroidRadiusZ(double r);

  //--------------------------------------------------------------------------
  // Init-mode property
  //--------------------------------------------------------------------------

  vtkGetMacro(InitMode, int);
  vtkSetMacro(InitMode, int);

protected:
  vtkMRMLAbstractParametricSurfaceNode();
  ~vtkMRMLAbstractParametricSurfaceNode() override;
  vtkMRMLAbstractParametricSurfaceNode(const vtkMRMLAbstractParametricSurfaceNode&) = delete;
  void operator=(const vtkMRMLAbstractParametricSurfaceNode&) = delete;

  int InitMode;

  unsigned int Rows;
  unsigned int Cols;
  std::vector<double> ControlGrid;

  double SlicingPlaneInitPoints[2][3];
  double SlicingPlaneOrigin[3];
  double SlicingPlaneNormal[3];

  int NumberOfDistanceSpheroidInitPoints;
  std::vector<double> DistanceSpheroidInitPoints;
  double DistanceSpheroidCenter[3];
  double DistanceSpheroidRadiusX;
  double DistanceSpheroidRadiusY;
  double DistanceSpheroidRadiusZ;
};

#endif // __vtkmrmlabstractparametricsurfacenode_h_

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
  v2.0.0 release tracker — see ADR-0014 §3).

==============================================================================*/

#ifndef __vtkliverbezierrepresentation_h_
#define __vtkliverbezierrepresentation_h_

#include "vtkSlicerLiverResectionsModuleVTKWidgetsExport.h"

// VTK includes
#include <vtkSmartPointer.h>
#include <vtkWeakPointer.h>
#include <vtkWidgetRepresentation.h>

class vtkActor;
class vtkMRMLBezierSurfaceNode;
class vtkPolyData;
class vtkPolyDataMapper;
class vtkPropPicker;
class vtkSphereSource;

/**
 * \class vtkLiverBezierRepresentation
 *
 * \brief VTK widget representation paired with ``vtkLiverBezierWidget``.
 *
 * This is the VTK ``vtkWidgetRepresentation``-pattern representation — the
 * geometry the widget draws during interaction (selection highlights,
 * drag previews, the picked control-point glyph).  It is *not* the
 * LayerDM-Pipeline ``BezierPlanningRepresentation``; those two
 * "representation" concepts coexist by accident of vocabulary.
 *
 * The representation observes a ``vtkMRMLBezierSurfaceNode`` for its
 * geometry source (the M×N control grid + init data per ADR-0014 §1
 * and ADR-0018 §1; M = N ∈ {3, 4} for v2.0.0) and exposes a picker
 * that resolves a display-space (X, Y) cursor to a point index in
 * the underlying data node.
 *
 * Per ADR-0014 §3 + ADR-0018 §1, the *pickable* set depends on the
 * data node's ``(State, InitMode)`` tuple:
 *
 *   - ``(Init, SlicingPlane)``  — the two SlicingPlane init points.
 *   - ``(Init, DistanceSpheroid)`` — the DistanceSpheroid init points.
 *   - ``(Planning, *)``  — the ``Rows * Cols`` Bezier control-grid
 *     points (9 for 3×3, 16 for 4×4; ring-group taxonomy: corners 4 +
 *     edges ``2*(M-2)+2*(N-2)`` + interior ``(M-2)*(N-2)``).
 *
 * Init-mode points are not pickable in Planning state; per ADR-0014 §4
 * they are read-only audit data and the widget must not enter a drag
 * substate on them.
 */
class VTK_SLICER_LIVERRESECTIONS_MODULE_VTKWIDGETS_EXPORT vtkLiverBezierRepresentation : public vtkWidgetRepresentation
{
public:
  static vtkLiverBezierRepresentation* New();
  vtkTypeMacro(vtkLiverBezierRepresentation, vtkWidgetRepresentation);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  /// Pickable-primitive role.  The integer-tagged enum is exposed so
  /// ``vtkLiverBezierWidget`` can dispatch on what was hit without
  /// rebuilding the pick result.  ``PickRole_None`` is the sentinel
  /// "miss".
  enum PickRole
  {
    PickRole_None = 0,
    PickRole_ControlPoint = 1,         ///< Bezier M×N grid (state=Planning); ADR-0018 §1.
    PickRole_SlicingPlaneInit = 2,     ///< Two SlicingPlane init points.
    PickRole_DistanceSpheroidInit = 3, ///< DistanceSpheroid init points.
  };

  /// Result of ``Pick(X, Y)`` — role + point index.  The index is
  /// role-relative: control-grid is [0..Rows*Cols-1] (per ADR-0018
  /// §1; 9 or 16 for v2.0.0), slicing-plane init is [0..1],
  /// distance-spheroid init is [0..N) where N is the data node's
  /// ``NumberOfDistanceSpheroidInitPoints``.
  struct PickResult
  {
    int Role{ PickRole_None };
    int Index{ -1 };
  };

  ///@{
  /// Attach / detach the data node this representation tracks.  The
  /// representation observes the node's ``ModifiedEvent`` and rebuilds
  /// its actors on change.  The reference is a vtkWeakPointer to avoid
  /// extending data-node lifetime; the widget owns the strong
  /// reference (TODO(T2-target-mesh-weakref)).
  void SetBezierNode(vtkMRMLBezierSurfaceNode* node);
  vtkMRMLBezierSurfaceNode* GetBezierNode();
  ///@}

  /// Pick at display coordinates ``(X, Y)``.  Returns a ``PickResult``
  /// whose ``Role`` is ``PickRole_None`` on miss.  Picking is gated by
  /// the data node's ``(State, InitMode)`` per ADR-0014 §3 — in
  /// Planning state init-mode points are not pickable, in Init state
  /// the control grid is not pickable.
  PickResult Pick(int X, int Y);

  /// Resolve a display-space (X, Y) cursor to a world-space (RAS) point
  /// on the plane parallel to the camera and passing through the
  /// currently picked point.  Returns ``true`` on success.  Used by
  /// the widget during ``Dragging`` to convert mouse moves into new
  /// point positions.
  bool DisplayToWorld(int X, int Y, const double referenceWorld[3], double worldOut[3]);

  //--------------------------------------------------------------------------
  // vtkWidgetRepresentation interface
  //--------------------------------------------------------------------------
  void BuildRepresentation() override;
  int ComputeInteractionState(int X, int Y, int modify = 0) override;

  /// Renderer set/get is inherited from vtkWidgetRepresentation.

  //--------------------------------------------------------------------------
  // vtkProp interface (forwarded to internal actors).
  //--------------------------------------------------------------------------
  void GetActors(vtkPropCollection* pc) override;
  void ReleaseGraphicsResources(vtkWindow* w) override;
  int RenderOverlay(vtkViewport* viewport) override;
  int RenderOpaqueGeometry(vtkViewport* viewport) override;
  int RenderTranslucentPolygonalGeometry(vtkViewport* viewport) override;
  vtkTypeBool HasTranslucentPolygonalGeometry() override;

protected:
  vtkLiverBezierRepresentation();
  ~vtkLiverBezierRepresentation() override;

  /// Rebuild the internal poly data carrying the currently-pickable
  /// glyph cloud.  Cheap (≤ ``MaxGridSize * MaxGridSize`` = 16
  /// sphere glyphs for the 4×4 case; 9 for 3×3 per ADR-0018 §1);
  /// called from ``BuildRepresentation()``.  Re-instantiates the
  /// per-control-point glyph set on every shape change (the buffer
  /// ``Reset`` above is idempotent across sizes; the glyph count on
  /// the next frame matches the data node's current Rows × Cols).
  /// The control-grid OpenGL mapper from
  /// ``LiverMarkups/VTKWidgets/`` is *not* hosted here — it relocates
  /// in TODO(T2-mapper-relocation) and the LayerDM Pipeline keeps the
  /// surface render path.  This representation only owns the
  /// interaction-time glyph cloud + selection highlight.
  void UpdatePickableGlyphs();

  /// Data node observed for geometry source.  Weak so the data node
  /// can outlive or pre-decease the representation cleanly.
  vtkWeakPointer<vtkMRMLBezierSurfaceNode> BezierNode;

  /// Glyph cloud carrying the currently-pickable points.  Per-point
  /// scalars carry the role + index so a vtkPropPicker hit resolves
  /// directly to a (Role, Index) pair.
  vtkSmartPointer<vtkPolyData> GlyphPolyData;
  vtkSmartPointer<vtkPolyDataMapper> GlyphMapper;
  vtkSmartPointer<vtkActor> GlyphActor;
  vtkSmartPointer<vtkSphereSource> GlyphSource;

  /// Selection-highlight actor — a sphere drawn at the currently
  /// hovered or dragged point.  Visible only when the widget is in
  /// ``Hovering`` or ``Dragging`` substate.  ADR-0014 §3 commits to
  /// no specific visual treatment — this is a minimal placeholder
  /// that survives until per-role glyph design lands in the T2 UX
  /// follow-on per ADR-0009 §3.
  vtkSmartPointer<vtkActor> HighlightActor;
  vtkSmartPointer<vtkSphereSource> HighlightSource;
  vtkSmartPointer<vtkPolyDataMapper> HighlightMapper;

  /// Picker used by ``Pick(X, Y)`` to resolve cursor → point index.
  vtkSmartPointer<vtkPropPicker> Picker;

  /// MTime of the data node at the last ``UpdatePickableGlyphs`` call;
  /// used to short-circuit rebuilds when no geometry-bearing field has
  /// changed.
  vtkMTimeType LastBuildDataMTime;

private:
  vtkLiverBezierRepresentation(const vtkLiverBezierRepresentation&) = delete;
  void operator=(const vtkLiverBezierRepresentation&) = delete;
};

#endif //__vtkliverbezierrepresentation_h_

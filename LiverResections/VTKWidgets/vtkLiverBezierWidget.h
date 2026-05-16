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

#ifndef __vtkliverbezierwidget_h_
#define __vtkliverbezierwidget_h_

#include "vtkSlicerLiverResectionsModuleVTKWidgetsExport.h"

// VTK includes
#include <vtkAbstractWidget.h>
#include <vtkWeakPointer.h>

#include "vtkLiverBezierRepresentation.h"

class vtkMRMLBezierSurfaceNode;

/**
 * \class vtkLiverBezierWidget
 *
 * \brief Custom VTK widget for the Bezier-surface resection planning
 *        workflow.
 *
 * Subclasses ``vtkAbstractWidget`` directly (NOT ``vtkSlicerMarkupsWidget``)
 * so the event table is free of the Markups-widget assumptions
 * documented in ADR-0014 §3.  Owns the explicit event vocabulary:
 *
 *   - **Left-drag** = per-point control-grid manipulation (move a
 *     single control point or init point under the cursor).
 *   - **Right-drag** = ring-group manipulation
 *     (TODO(T2.3 right-drag-ring-group)).
 *   - **Right-click** = own context menu
 *     (TODO(T2.3 right-click-context-menu); the reason for subclassing
 *     vtkAbstractWidget directly rather than vtkSlicerMarkupsWidget,
 *     whose ``WidgetEventMenu`` / ``populateContextMenu`` constrains
 *     the menu shape).
 *
 * The current PR lands the skeleton + left-drag only.  The other two
 * event flows ship in the named TODO follow-ups; the state-machine
 * substates for them are reserved at the enum level but the
 * callbacks are placeholders.
 *
 * The widget observes a ``vtkMRMLBezierSurfaceNode`` and mutates its
 * control grid / init points via ``SetControlGrid`` /
 * ``SetSlicingPlaneInitPoint`` / ``SetDistanceSpheroidInitPoint``.
 * Per ADR-0014 §4 the data node enforces the read-only-after-Planning
 * invariant on init-mode setters; the widget mirrors that by gating
 * pickability through ``vtkLiverBezierRepresentation::Pick`` (which
 * does *not* return init-mode hits in Planning state).
 *
 * \par Test discipline
 *
 * The widget can be exercised standalone (no Slicer scene, no Qt) per
 * ADR-0008 §2; ``vtkLiverBezierWidgetTest1`` drives event dispatch
 * via direct ``SelectAction`` / ``MoveAction`` / ``EndSelectAction``
 * calls on a stub ``vtkRenderWindowInteractor`` (the headless test
 * pattern used by the upstream ``vtkLineWidget2Test1``).
 */
class VTK_SLICER_LIVERRESECTIONS_MODULE_VTKWIDGETS_EXPORT vtkLiverBezierWidget : public vtkAbstractWidget
{
public:
  static vtkLiverBezierWidget* New();
  vtkTypeMacro(vtkLiverBezierWidget, vtkAbstractWidget);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  /// Internal state machine (ADR-0014 §3).  Pin enum values explicitly
  /// so a future reorder does not silently shift downstream test
  /// expectations.
  ///
  /// - ``Start``         — idle, no interaction in flight.
  /// - ``Hovering``      — cursor over a pickable primitive.
  /// - ``Dragging``      — left-mouse held over a pickable point.
  /// - ``GroupDragging`` — right-drag of a ring group
  ///                       (TODO(T2.3 right-drag-ring-group)).
  /// - ``ContextMenu``   — right-click context menu in flight
  ///                       (TODO(T2.3 right-click-context-menu)).
  enum WidgetStateType
  {
    Start = 0,
    Hovering = 1,
    Dragging = 2,
    GroupDragging = 3,
    ContextMenu = 4,
  };

  /// Get / set the widget substate.  Setting Start clears the picked
  /// point cache.
  vtkGetMacro(WidgetState, int);
  void SetWidgetState(int state);

  /// Set / get the representation.  Type-constrains the
  /// ``Superclass::SetWidgetRepresentation`` signature.
  void SetRepresentation(vtkLiverBezierRepresentation* r);
  vtkLiverBezierRepresentation* GetLiverBezierRepresentation();

  /// Attach / detach the data node the widget mutates.  The data node
  /// is also pushed onto the representation so picking stays in sync.
  void SetBezierNode(vtkMRMLBezierSurfaceNode* node);
  vtkMRMLBezierSurfaceNode* GetBezierNode();

  //--------------------------------------------------------------------------
  // vtkAbstractWidget interface
  //--------------------------------------------------------------------------
  void CreateDefaultRepresentation() override;

  /// Standard VTK widget enable/disable; routes the priority observer
  /// add/remove path through ``vtkAbstractWidget::SetEnabled``.
  void SetEnabled(int enabling) override;

  //--------------------------------------------------------------------------
  // Test surface — public so tests can drive event dispatch without
  // an interactor.  ADR-0008 §2 ctkTest scope.
  //--------------------------------------------------------------------------

  /// Begin a left-drag interaction at display ``(X, Y)``.  Returns
  /// true if the press landed on a pickable primitive (advancing the
  /// state machine to ``Dragging``); false otherwise.  Mirrors the
  /// ``LeftButtonPressEvent`` path.
  bool BeginLeftDragAt(int X, int Y);

  /// Update the currently-dragged point to display ``(X, Y)``.  No-op
  /// outside ``Dragging``.  Returns the resolved world-space
  /// coordinate the data node was updated to.
  bool DragTo(int X, int Y, double worldOut[3]);

  /// End the current left-drag.  Resets to ``Start`` substate.
  void EndLeftDrag();

  /// Index of the picked point in the active role (control grid,
  /// SlicingPlane init, DistanceSpheroid init).  -1 when no pick.
  vtkGetMacro(PickedIndex, int);

  /// Role of the picked point.
  vtkGetMacro(PickedRole, int);

protected:
  vtkLiverBezierWidget();
  ~vtkLiverBezierWidget() override;

  /// VTK callback-mapper entry points.  These are the targets the
  /// widget event translator dispatches to; they unpack ``self`` and
  /// route into the instance helpers above.  Each marks the boundary
  /// between the upstream ``vtkAbstractWidget`` callback ABI and the
  /// instance-method test surface.
  static void SelectAction(vtkAbstractWidget* w);
  static void EndSelectAction(vtkAbstractWidget* w);
  static void MoveAction(vtkAbstractWidget* w);
  static void RightSelectAction(vtkAbstractWidget* w);
  static void RightEndSelectAction(vtkAbstractWidget* w);

  /// Write ``world`` back to the data node at the currently picked
  /// (role, index).  Routes through the read-only-after-Planning
  /// guards on the data node per ADR-0014 §4.  Returns the data
  /// node's accept signal (true = mutation landed; false = rejected
  /// or no-op).
  bool ApplyPickedPointWorld(const double world[3]);

  /// Cache the world-space anchor of the currently dragged point so
  /// ``DisplayToWorld`` can keep the cursor's drag plane coherent
  /// across the gesture.
  double DragAnchorWorld[3];

  /// Substate.
  int WidgetState;

  /// Pick result cached from the last successful press.
  int PickedRole;
  int PickedIndex;

  /// Data node the widget mutates.  Held as vtkWeakPointer; the
  /// scene / module owner keeps the strong reference.
  vtkWeakPointer<vtkMRMLBezierSurfaceNode> BezierNode;

private:
  vtkLiverBezierWidget(const vtkLiverBezierWidget&) = delete;
  void operator=(const vtkLiverBezierWidget&) = delete;
};

#endif //__vtkliverbezierwidget_h_

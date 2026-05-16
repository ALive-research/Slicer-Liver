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
  v2.0.0 release tracker — see ADR-0014 §3).

==============================================================================*/

#include "vtkLiverBezierWidget.h"

// MRML includes
#include <vtkMRMLBezierSurfaceNode.h>

// VTK includes
#include <vtkActor.h>
#include <vtkCallbackCommand.h>
#include <vtkCommand.h>
#include <vtkEvent.h>
#include <vtkObjectFactory.h>
#include <vtkRenderWindowInteractor.h>
#include <vtkRenderer.h>
#include <vtkWidgetCallbackMapper.h>
#include <vtkWidgetEvent.h>
#include <vtkWidgetEventTranslator.h>

//------------------------------------------------------------------------------
vtkStandardNewMacro(vtkLiverBezierWidget);

//------------------------------------------------------------------------------
vtkLiverBezierWidget::vtkLiverBezierWidget()
  : WidgetState(Start)
  , PickedRole(vtkLiverBezierRepresentation::PickRole_None)
  , PickedIndex(-1)
{
  this->DragAnchorWorld[0] = 0.0;
  this->DragAnchorWorld[1] = 0.0;
  this->DragAnchorWorld[2] = 0.0;
  this->ManagesCursor = 1;

  // ADR-0014 §3 — explicit event table.  The Markups widget retired by
  // this design hardwired right-click to its own ``WidgetEventMenu``;
  // here right-click maps to a widget-specific event we own.
  //
  // Left-drag = per-point manipulation.  ``Select`` advances to
  // ``Dragging`` on a successful pick; ``EndSelect`` returns to
  // ``Start``; ``Move`` updates the point if Dragging.
  this->CallbackMapper->SetCallbackMethod(vtkCommand::LeftButtonPressEvent, vtkWidgetEvent::Select, this, vtkLiverBezierWidget::SelectAction);
  this->CallbackMapper->SetCallbackMethod(vtkCommand::LeftButtonReleaseEvent, vtkWidgetEvent::EndSelect, this, vtkLiverBezierWidget::EndSelectAction);
  this->CallbackMapper->SetCallbackMethod(vtkCommand::MouseMoveEvent, vtkWidgetEvent::Move, this, vtkLiverBezierWidget::MoveAction);

  // Right-drag / right-click — registered so the event table is
  // *visible* in this PR; the callbacks are no-op placeholders
  // pending TODO(T2.3 right-drag-ring-group) and
  // TODO(T2.3 right-click-context-menu).  Wiring the registrations
  // here means upstream interactor events route into the widget
  // (rather than falling through to the Markups widget or the
  // default 3-D-camera bindings), making the future iterations a
  // pure callback-body edit.
  this->CallbackMapper->SetCallbackMethod(vtkCommand::RightButtonPressEvent, vtkWidgetEvent::Select3D, this, vtkLiverBezierWidget::RightSelectAction);
  this->CallbackMapper->SetCallbackMethod(vtkCommand::RightButtonReleaseEvent, vtkWidgetEvent::EndSelect3D, this, vtkLiverBezierWidget::RightEndSelectAction);
}

//------------------------------------------------------------------------------
vtkLiverBezierWidget::~vtkLiverBezierWidget() = default;

//------------------------------------------------------------------------------
void vtkLiverBezierWidget::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);
  os << indent << "WidgetState: " << this->WidgetState << "\n";
  os << indent << "PickedRole: " << this->PickedRole << "\n";
  os << indent << "PickedIndex: " << this->PickedIndex << "\n";
  os << indent << "BezierNode: " << (this->BezierNode.GetPointer() ? "set" : "(null)") << "\n";
}

//------------------------------------------------------------------------------
void vtkLiverBezierWidget::CreateDefaultRepresentation()
{
  if (!this->WidgetRep)
  {
    vtkNew<vtkLiverBezierRepresentation> rep;
    this->SetRepresentation(rep.GetPointer());
  }
}

//------------------------------------------------------------------------------
void vtkLiverBezierWidget::SetRepresentation(vtkLiverBezierRepresentation* r)
{
  this->Superclass::SetWidgetRepresentation(reinterpret_cast<vtkWidgetRepresentation*>(r));
  if (r && this->BezierNode.GetPointer())
  {
    r->SetBezierNode(this->BezierNode.GetPointer());
  }
}

//------------------------------------------------------------------------------
vtkLiverBezierRepresentation* vtkLiverBezierWidget::GetLiverBezierRepresentation()
{
  return reinterpret_cast<vtkLiverBezierRepresentation*>(this->WidgetRep);
}

//------------------------------------------------------------------------------
void vtkLiverBezierWidget::SetBezierNode(vtkMRMLBezierSurfaceNode* node)
{
  this->BezierNode = node;
  if (auto* rep = this->GetLiverBezierRepresentation())
  {
    rep->SetBezierNode(node);
  }
}

//------------------------------------------------------------------------------
vtkMRMLBezierSurfaceNode* vtkLiverBezierWidget::GetBezierNode()
{
  return this->BezierNode.GetPointer();
}

//------------------------------------------------------------------------------
void vtkLiverBezierWidget::SetEnabled(int enabling)
{
  this->Superclass::SetEnabled(enabling);
}

//------------------------------------------------------------------------------
void vtkLiverBezierWidget::SetWidgetState(int state)
{
  if (state == this->WidgetState)
  {
    return;
  }
  this->WidgetState = state;
  if (state == Start)
  {
    this->PickedRole = vtkLiverBezierRepresentation::PickRole_None;
    this->PickedIndex = -1;
  }
}

//------------------------------------------------------------------------------
bool vtkLiverBezierWidget::BeginLeftDragAt(int X, int Y)
{
  this->CreateDefaultRepresentation();
  auto* rep = this->GetLiverBezierRepresentation();
  if (!rep)
  {
    return false;
  }
  vtkMRMLBezierSurfaceNode* node = this->BezierNode.GetPointer();
  if (!node)
  {
    return false;
  }
  vtkLiverBezierRepresentation::PickResult pick = rep->Pick(X, Y);
  if (pick.Role == vtkLiverBezierRepresentation::PickRole_None)
  {
    return false;
  }

  // ADR-0014 §4 — reject the drag start if the picked role would
  // mutate read-only audit data (init-mode point in Planning state).
  // ``Pick`` already guards against returning init-mode hits in
  // Planning, but the widget keeps a belt-and-braces second check
  // here so a future loosening of ``Pick`` (e.g. for hover-only
  // tooltips on read-only audit points) does not silently re-enable
  // the drag path.
  if (node->GetState() == vtkMRMLBezierSurfaceNode::Planning && pick.Role != vtkLiverBezierRepresentation::PickRole_ControlPoint)
  {
    return false;
  }

  // Cache the anchor world position so ``DragTo`` can project the
  // mouse onto a stable plane parallel to the camera.
  switch (pick.Role)
  {
    case vtkLiverBezierRepresentation::PickRole_ControlPoint:
    {
      const double* grid = node->GetControlGrid();
      this->DragAnchorWorld[0] = grid[pick.Index * 3 + 0];
      this->DragAnchorWorld[1] = grid[pick.Index * 3 + 1];
      this->DragAnchorWorld[2] = grid[pick.Index * 3 + 2];
      break;
    }
    case vtkLiverBezierRepresentation::PickRole_SlicingPlaneInit:
    {
      const double* p = node->GetSlicingPlaneInitPoint(pick.Index);
      if (!p)
      {
        return false;
      }
      this->DragAnchorWorld[0] = p[0];
      this->DragAnchorWorld[1] = p[1];
      this->DragAnchorWorld[2] = p[2];
      break;
    }
    case vtkLiverBezierRepresentation::PickRole_DistanceSpheroidInit:
    {
      const double* p = node->GetDistanceSpheroidInitPoint(pick.Index);
      if (!p)
      {
        return false;
      }
      this->DragAnchorWorld[0] = p[0];
      this->DragAnchorWorld[1] = p[1];
      this->DragAnchorWorld[2] = p[2];
      break;
    }
    default: return false;
  }

  this->PickedRole = pick.Role;
  this->PickedIndex = pick.Index;
  this->WidgetState = Dragging;
  this->InvokeEvent(vtkCommand::StartInteractionEvent, nullptr);
  return true;
}

//------------------------------------------------------------------------------
bool vtkLiverBezierWidget::DragTo(int X, int Y, double worldOut[3])
{
  if (this->WidgetState != Dragging)
  {
    return false;
  }
  auto* rep = this->GetLiverBezierRepresentation();
  if (!rep)
  {
    return false;
  }
  double world[3] = { 0.0, 0.0, 0.0 };
  if (!rep->DisplayToWorld(X, Y, this->DragAnchorWorld, world))
  {
    return false;
  }
  if (!this->ApplyPickedPointWorld(world))
  {
    return false;
  }
  if (worldOut)
  {
    worldOut[0] = world[0];
    worldOut[1] = world[1];
    worldOut[2] = world[2];
  }
  // Advance the anchor — keeps the drag plane stable across long
  // gestures (otherwise the cursor would slowly slide off the original
  // anchor plane as the user moves through Z).
  this->DragAnchorWorld[0] = world[0];
  this->DragAnchorWorld[1] = world[1];
  this->DragAnchorWorld[2] = world[2];
  this->InvokeEvent(vtkCommand::InteractionEvent, nullptr);
  return true;
}

//------------------------------------------------------------------------------
void vtkLiverBezierWidget::EndLeftDrag()
{
  if (this->WidgetState != Dragging)
  {
    return;
  }
  this->SetWidgetState(Start);
  this->InvokeEvent(vtkCommand::EndInteractionEvent, nullptr);
}

//------------------------------------------------------------------------------
bool vtkLiverBezierWidget::ApplyPickedPointWorld(const double world[3])
{
  vtkMRMLBezierSurfaceNode* node = this->BezierNode.GetPointer();
  if (!node || !world)
  {
    return false;
  }
  switch (this->PickedRole)
  {
    case vtkLiverBezierRepresentation::PickRole_ControlPoint:
    {
      if (this->PickedIndex < 0 || this->PickedIndex >= vtkMRMLBezierSurfaceNode::GridSize * vtkMRMLBezierSurfaceNode::GridSize)
      {
        return false;
      }
      // SetControlGrid takes the full 48-double array; copy current,
      // patch the picked point, push back.
      double values[vtkMRMLBezierSurfaceNode::ControlGridSize];
      const double* current = node->GetControlGrid();
      for (int i = 0; i < vtkMRMLBezierSurfaceNode::ControlGridSize; ++i)
      {
        values[i] = current[i];
      }
      values[this->PickedIndex * 3 + 0] = world[0];
      values[this->PickedIndex * 3 + 1] = world[1];
      values[this->PickedIndex * 3 + 2] = world[2];
      return node->SetControlGrid(values);
    }
    case vtkLiverBezierRepresentation::PickRole_SlicingPlaneInit: return node->SetSlicingPlaneInitPoint(this->PickedIndex, world);
    case vtkLiverBezierRepresentation::PickRole_DistanceSpheroidInit: return node->SetDistanceSpheroidInitPoint(this->PickedIndex, world);
    default: return false;
  }
}

//------------------------------------------------------------------------------
void vtkLiverBezierWidget::SelectAction(vtkAbstractWidget* w)
{
  auto* self = static_cast<vtkLiverBezierWidget*>(w);
  if (!self->Interactor)
  {
    return;
  }
  const int X = self->Interactor->GetEventPosition()[0];
  const int Y = self->Interactor->GetEventPosition()[1];
  if (self->BeginLeftDragAt(X, Y))
  {
    // Capture event so the camera-trackball bindings don't fight us.
    self->EventCallbackCommand->SetAbortFlag(1);
  }
}

//------------------------------------------------------------------------------
void vtkLiverBezierWidget::EndSelectAction(vtkAbstractWidget* w)
{
  auto* self = static_cast<vtkLiverBezierWidget*>(w);
  if (self->WidgetState != Dragging)
  {
    return;
  }
  self->EndLeftDrag();
  self->EventCallbackCommand->SetAbortFlag(1);
}

//------------------------------------------------------------------------------
void vtkLiverBezierWidget::MoveAction(vtkAbstractWidget* w)
{
  auto* self = static_cast<vtkLiverBezierWidget*>(w);
  if (!self->Interactor)
  {
    return;
  }
  const int X = self->Interactor->GetEventPosition()[0];
  const int Y = self->Interactor->GetEventPosition()[1];
  if (self->WidgetState == Dragging)
  {
    double world[3] = { 0.0, 0.0, 0.0 };
    self->DragTo(X, Y, world);
    self->EventCallbackCommand->SetAbortFlag(1);
  }
  else
  {
    // Hover update — pick test only, no state change beyond
    // ``Start`` <-> ``Hovering``.
    auto* rep = self->GetLiverBezierRepresentation();
    if (!rep)
    {
      return;
    }
    vtkLiverBezierRepresentation::PickResult hit = rep->Pick(X, Y);
    self->SetWidgetState(hit.Role == vtkLiverBezierRepresentation::PickRole_None ? Start : Hovering);
  }
}

//------------------------------------------------------------------------------
void vtkLiverBezierWidget::RightSelectAction(vtkAbstractWidget* w)
{
  // TODO(T2.3 right-drag-ring-group) — translate / rotate / scale the
  // ring group (corners 4 / edges 8 / interior 4 per ADR-0014 §3) as
  // a unit while right-button is held.
  // TODO(T2.3 right-click-context-menu) — if the right-drag does not
  // exceed the drag threshold, open the widget's own context menu
  // on release.  vtkSlicerMarkupsWidget's ``WidgetEventMenu`` /
  // ``populateContextMenu`` would compete here; the whole point of
  // subclassing vtkAbstractWidget directly is that those bindings do
  // not pre-empt this one.
  static_cast<void>(w);
}

//------------------------------------------------------------------------------
void vtkLiverBezierWidget::RightEndSelectAction(vtkAbstractWidget* w)
{
  // TODO(T2.3 right-drag-ring-group) end-of-gesture cleanup.
  // TODO(T2.3 right-click-context-menu) context-menu launch.
  static_cast<void>(w);
}

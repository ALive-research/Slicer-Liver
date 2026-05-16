/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Tests for vtkLiverBezierWidget and vtkLiverBezierRepresentation —
  the custom widget landed by ADR-0014 §3.  Per ADR-0008 §2 these are
  C++ low-level ctkTest-driver tests: no Slicer scene, no Qt, no
  rendering, no on-screen interactor.

  Coverage:

   - Constructor / SetWidgetState lifecycle
       (Start -> Hovering -> Dragging -> Start).
   - Picking a control point at a known coordinate returns the right
     point index + role.
   - Simulating LeftButtonPress + MouseMove + LeftButtonRelease
     mutates the data node's control grid as expected.
   - Read-only enforcement (ADR-0014 §4): in state=Planning, init-mode
     drag attempts are rejected — the widget must not enter Dragging
     on an init-mode pick when the data node is in Planning.

==============================================================================*/

// LiverResections VTKWidgets includes
#include "vtkLiverBezierRepresentation.h"
#include "vtkLiverBezierWidget.h"

// MRML includes
#include "vtkMRMLBezierSurfaceNode.h"
#include "vtkMRMLCoreTestingMacros.h"

// VTK includes
#include <vtkCamera.h>
#include <vtkGenericOpenGLRenderWindow.h>
#include <vtkNew.h>
#include <vtkRenderer.h>
#include <vtkSmartPointer.h>

// STD includes
#include <cmath>
#include <iostream>

namespace
{

/// Build a renderer + camera oriented so the world plane Z=0 maps to
/// display coordinates with a known scale.  The picker tolerance in
/// vtkLiverBezierRepresentation is in world units; this orientation
/// keeps the test points well separated under that tolerance.
vtkSmartPointer<vtkRenderer> makeRenderer()
{
  vtkSmartPointer<vtkRenderer> renderer = vtkSmartPointer<vtkRenderer>::New();
  renderer->SetViewport(0.0, 0.0, 1.0, 1.0);
  vtkCamera* camera = renderer->GetActiveCamera();
  camera->ParallelProjectionOn();
  camera->SetParallelScale(50.0);
  camera->SetPosition(0.0, 0.0, 100.0);
  camera->SetFocalPoint(0.0, 0.0, 0.0);
  camera->SetViewUp(0.0, 1.0, 0.0);
  camera->SetClippingRange(1.0, 1000.0);
  return renderer;
}

/// Construct a minimal Bezier surface data node in Planning state with
/// a known control grid: every control point lies on the Z=0 plane at
/// the lattice position (col, row) * stride for stride=10.  The 16
/// points are well outside the 5-unit pick tolerance from each other.
vtkSmartPointer<vtkMRMLBezierSurfaceNode> makePlanningNode()
{
  vtkSmartPointer<vtkMRMLBezierSurfaceNode> node = vtkSmartPointer<vtkMRMLBezierSurfaceNode>::New();
  node->SetState(vtkMRMLBezierSurfaceNode::Planning);
  double values[vtkMRMLBezierSurfaceNode::ControlGridSize] = { 0.0 };
  constexpr double stride = 10.0;
  for (int row = 0; row < vtkMRMLBezierSurfaceNode::GridSize; ++row)
  {
    for (int col = 0; col < vtkMRMLBezierSurfaceNode::GridSize; ++col)
    {
      const int i = row * vtkMRMLBezierSurfaceNode::GridSize + col;
      values[i * 3 + 0] = (col - 1.5) * stride;
      values[i * 3 + 1] = (row - 1.5) * stride;
      values[i * 3 + 2] = 0.0;
    }
  }
  node->SetControlGrid(values);
  return node;
}

int testLifecycle()
{
  vtkNew<vtkLiverBezierWidget> widget;
  CHECK_INT(widget->GetWidgetState(), vtkLiverBezierWidget::Start);
  CHECK_INT(widget->GetPickedIndex(), -1);
  CHECK_INT(widget->GetPickedRole(), vtkLiverBezierRepresentation::PickRole_None);

  widget->SetWidgetState(vtkLiverBezierWidget::Hovering);
  CHECK_INT(widget->GetWidgetState(), vtkLiverBezierWidget::Hovering);

  widget->SetWidgetState(vtkLiverBezierWidget::Dragging);
  CHECK_INT(widget->GetWidgetState(), vtkLiverBezierWidget::Dragging);

  widget->SetWidgetState(vtkLiverBezierWidget::Start);
  CHECK_INT(widget->GetWidgetState(), vtkLiverBezierWidget::Start);
  CHECK_INT(widget->GetPickedIndex(), -1);
  CHECK_INT(widget->GetPickedRole(), vtkLiverBezierRepresentation::PickRole_None);

  // CreateDefaultRepresentation must lazily build a representation.
  CHECK_NULL(widget->GetLiverBezierRepresentation());
  widget->CreateDefaultRepresentation();
  CHECK_NOT_NULL(widget->GetLiverBezierRepresentation());
  return EXIT_SUCCESS;
}

int testPickControlPoint()
{
  vtkSmartPointer<vtkMRMLBezierSurfaceNode> node = makePlanningNode();
  vtkSmartPointer<vtkRenderer> renderer = makeRenderer();

  vtkNew<vtkLiverBezierRepresentation> rep;
  rep->SetRenderer(renderer);
  rep->SetBezierNode(node);
  rep->BuildRepresentation();

  // Render-window + interactor get a fake size so display-to-world
  // mapping is deterministic.  No actual rendering occurs.
  // vtkGenericOpenGLRenderWindow is a headless software-only render
  // window — no X / EGL / GLX connection.  It provides the viewport
  // size the renderer needs for display-to-world math (per
  // vtkViewport::GetSize) without triggering the upstream "bad X
  // server connection" warning that vtkXOpenGLRenderWindow emits
  // when DISPLAY is unset.  ADR-0008 §2 ctkTest scope demands no
  // on-screen rendering; this matches that constraint.
  vtkNew<vtkGenericOpenGLRenderWindow> renderWindow;
  renderWindow->SetShowWindow(false);
  renderWindow->AddRenderer(renderer);
  renderWindow->SetSize(400, 400);

  // Drive the active-camera reset so vtkInteractorObserver's
  // display-to-world projector picks up a finite viewport.
  renderer->ResetCameraClippingRange();

  // The control point at (row=2, col=1) sits at world (-5, 5, 0)
  // given stride=10, origin = (col - 1.5)*stride.  Map that to
  // display coordinates via the camera-modelview composition.
  double world[3] = { -5.0, 5.0, 0.0 };
  double display[3] = { 0.0, 0.0, 0.0 };
  // Project world -> display through the renderer's transformation.
  renderer->SetWorldPoint(world[0], world[1], world[2], 1.0);
  renderer->WorldToDisplay();
  double* d = renderer->GetDisplayPoint();
  display[0] = d[0];
  display[1] = d[1];

  vtkLiverBezierRepresentation::PickResult pick = rep->Pick(static_cast<int>(std::round(display[0])), static_cast<int>(std::round(display[1])));
  CHECK_INT(pick.Role, vtkLiverBezierRepresentation::PickRole_ControlPoint);
  // row=2, col=1 -> index 2*4 + 1 = 9
  CHECK_INT(pick.Index, 9);

  // A pick far away from any control point misses.
  vtkLiverBezierRepresentation::PickResult miss = rep->Pick(-1000, -1000);
  CHECK_INT(miss.Role, vtkLiverBezierRepresentation::PickRole_None);
  return EXIT_SUCCESS;
}

int testLeftDragMutatesControlGrid()
{
  vtkSmartPointer<vtkMRMLBezierSurfaceNode> node = makePlanningNode();
  vtkSmartPointer<vtkRenderer> renderer = makeRenderer();

  vtkNew<vtkLiverBezierRepresentation> rep;
  rep->SetRenderer(renderer);
  rep->SetBezierNode(node);
  rep->BuildRepresentation();

  // vtkGenericOpenGLRenderWindow is a headless software-only render
  // window — no X / EGL / GLX connection.  It provides the viewport
  // size the renderer needs for display-to-world math (per
  // vtkViewport::GetSize) without triggering the upstream "bad X
  // server connection" warning that vtkXOpenGLRenderWindow emits
  // when DISPLAY is unset.  ADR-0008 §2 ctkTest scope demands no
  // on-screen rendering; this matches that constraint.
  vtkNew<vtkGenericOpenGLRenderWindow> renderWindow;
  renderWindow->SetShowWindow(false);
  renderWindow->AddRenderer(renderer);
  renderWindow->SetSize(400, 400);
  renderer->ResetCameraClippingRange();

  vtkNew<vtkLiverBezierWidget> widget;
  widget->SetRepresentation(rep);
  widget->SetBezierNode(node);

  // Project control point (row=0, col=0) at world (-15, -15, 0) to
  // display coordinates.
  renderer->SetWorldPoint(-15.0, -15.0, 0.0, 1.0);
  renderer->WorldToDisplay();
  double* d = renderer->GetDisplayPoint();
  const int startX = static_cast<int>(std::round(d[0]));
  const int startY = static_cast<int>(std::round(d[1]));

  CHECK_BOOL(widget->BeginLeftDragAt(startX, startY), true);
  CHECK_INT(widget->GetWidgetState(), vtkLiverBezierWidget::Dragging);
  CHECK_INT(widget->GetPickedRole(), vtkLiverBezierRepresentation::PickRole_ControlPoint);
  CHECK_INT(widget->GetPickedIndex(), 0);

  // Project a new target world coordinate (-12, -10, 0) to display
  // coordinates, then drag the picked point there.
  renderer->SetWorldPoint(-12.0, -10.0, 0.0, 1.0);
  renderer->WorldToDisplay();
  d = renderer->GetDisplayPoint();
  const int endX = static_cast<int>(std::round(d[0]));
  const int endY = static_cast<int>(std::round(d[1]));

  double resolved[3] = { 0.0, 0.0, 0.0 };
  CHECK_BOOL(widget->DragTo(endX, endY, resolved), true);
  CHECK_DOUBLE_TOLERANCE(resolved[0], -12.0, 1e-3);
  CHECK_DOUBLE_TOLERANCE(resolved[1], -10.0, 1e-3);
  CHECK_DOUBLE_TOLERANCE(resolved[2], 0.0, 1e-3);

  // Data node round-trip — control point 0 must have moved.
  const double* grid = node->GetControlGrid();
  CHECK_DOUBLE_TOLERANCE(grid[0], -12.0, 1e-3);
  CHECK_DOUBLE_TOLERANCE(grid[1], -10.0, 1e-3);
  CHECK_DOUBLE_TOLERANCE(grid[2], 0.0, 1e-3);

  // Other control points must not have moved.
  CHECK_DOUBLE_TOLERANCE(grid[3], -5.0, 1e-3); // (row=0, col=1) -> x=-5
  CHECK_DOUBLE_TOLERANCE(grid[4], -15.0, 1e-3);

  widget->EndLeftDrag();
  CHECK_INT(widget->GetWidgetState(), vtkLiverBezierWidget::Start);
  CHECK_INT(widget->GetPickedIndex(), -1);
  return EXIT_SUCCESS;
}

int testReadOnlyEnforcement()
{
  // ADR-0014 §4 — in state=Planning, init-mode points are read-only
  // audit data.  The widget must *not* enter Dragging on an init-mode
  // pick attempt in Planning.  This test seeds init data while in Init,
  // transitions to Planning (legal one-way transition), and asserts a
  // drag attempt at an init-point display coordinate is rejected.
  vtkSmartPointer<vtkMRMLBezierSurfaceNode> node = vtkSmartPointer<vtkMRMLBezierSurfaceNode>::New();
  CHECK_INT(node->GetState(), vtkMRMLBezierSurfaceNode::Init);
  double p0[3] = { -20.0, 0.0, 0.0 };
  double p1[3] = { 20.0, 0.0, 0.0 };
  node->SetSlicingPlaneInitPoint(0, p0);
  node->SetSlicingPlaneInitPoint(1, p1);

  vtkSmartPointer<vtkRenderer> renderer = makeRenderer();
  // vtkGenericOpenGLRenderWindow is a headless software-only render
  // window — no X / EGL / GLX connection.  It provides the viewport
  // size the renderer needs for display-to-world math (per
  // vtkViewport::GetSize) without triggering the upstream "bad X
  // server connection" warning that vtkXOpenGLRenderWindow emits
  // when DISPLAY is unset.  ADR-0008 §2 ctkTest scope demands no
  // on-screen rendering; this matches that constraint.
  vtkNew<vtkGenericOpenGLRenderWindow> renderWindow;
  renderWindow->SetShowWindow(false);
  renderWindow->AddRenderer(renderer);
  renderWindow->SetSize(400, 400);
  renderer->ResetCameraClippingRange();

  vtkNew<vtkLiverBezierRepresentation> rep;
  rep->SetRenderer(renderer);
  rep->SetBezierNode(node);
  rep->BuildRepresentation();

  vtkNew<vtkLiverBezierWidget> widget;
  widget->SetRepresentation(rep);
  widget->SetBezierNode(node);

  // While in Init, picking the slicing-plane init point at world
  // (-20, 0, 0) should succeed and a drag should land.
  renderer->SetWorldPoint(-20.0, 0.0, 0.0, 1.0);
  renderer->WorldToDisplay();
  double* d = renderer->GetDisplayPoint();
  const int X = static_cast<int>(std::round(d[0]));
  const int Y = static_cast<int>(std::round(d[1]));

  CHECK_BOOL(widget->BeginLeftDragAt(X, Y), true);
  CHECK_INT(widget->GetWidgetState(), vtkLiverBezierWidget::Dragging);
  CHECK_INT(widget->GetPickedRole(), vtkLiverBezierRepresentation::PickRole_SlicingPlaneInit);
  CHECK_INT(widget->GetPickedIndex(), 0);
  widget->EndLeftDrag();

  // Transition to Planning — init points are now read-only.
  node->SetState(vtkMRMLBezierSurfaceNode::Planning);
  CHECK_INT(node->GetState(), vtkMRMLBezierSurfaceNode::Planning);

  // The pickable set has changed — re-build the representation so the
  // glyph cloud reflects the new (state, mode) tuple.
  rep->BuildRepresentation();

  // Picking the same display coordinate must *not* return an init-mode
  // hit.  The representation's pick logic gates init-mode points
  // behind state==Init.
  vtkLiverBezierRepresentation::PickResult pick = rep->Pick(X, Y);
  if (pick.Role == vtkLiverBezierRepresentation::PickRole_SlicingPlaneInit)
  {
    std::cerr << "Pick returned init-mode hit in Planning state — read-only "
              << "invariant breach (ADR-0014 §4)\n";
    return EXIT_FAILURE;
  }

  // Attempting to start a left-drag at the same coordinate must
  // either resolve to a control-point pick (different role) or miss.
  // Either way, it must NOT carry the SlicingPlaneInit role.
  const bool started = widget->BeginLeftDragAt(X, Y);
  if (started && widget->GetPickedRole() == vtkLiverBezierRepresentation::PickRole_SlicingPlaneInit)
  {
    std::cerr << "Widget entered Dragging on a SlicingPlaneInit pick in "
              << "Planning state — read-only invariant breach\n";
    return EXIT_FAILURE;
  }
  if (started)
  {
    widget->EndLeftDrag();
  }

  // Belt-and-braces: explicitly attempt the read-only-rejected setter
  // path.  The data node's ADR-0014 §4 guard emits a warning; gate the
  // assertion so the test driver does not count it as a failure.
  TESTING_OUTPUT_ASSERT_WARNINGS_BEGIN();
  double clobber[3] = { -99.0, -99.0, -99.0 };
  CHECK_BOOL(node->SetSlicingPlaneInitPoint(0, clobber), false);
  TESTING_OUTPUT_ASSERT_WARNINGS_END();

  // Init point still carries its pre-Planning value.
  const double* got = node->GetSlicingPlaneInitPoint(0);
  CHECK_NOT_NULL(got);
  CHECK_DOUBLE(got[0], -20.0);
  CHECK_DOUBLE(got[1], 0.0);
  CHECK_DOUBLE(got[2], 0.0);
  return EXIT_SUCCESS;
}

} // namespace

//------------------------------------------------------------------------------
int vtkLiverBezierWidgetTest1(int, char*[])
{
  CHECK_EXIT_SUCCESS(testLifecycle());
  CHECK_EXIT_SUCCESS(testPickControlPoint());
  CHECK_EXIT_SUCCESS(testLeftDragMutatesControlGrid());
  CHECK_EXIT_SUCCESS(testReadOnlyEnforcement());

  std::cout << "vtkLiverBezierWidgetTest1 completed successfully" << std::endl;
  return EXIT_SUCCESS;
}

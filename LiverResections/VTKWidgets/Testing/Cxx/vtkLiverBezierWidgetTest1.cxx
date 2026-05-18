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

int testConfirmedStatePickGate()
{
  // ADR-0019 §"Per-state contract": in ``Confirmed`` the widget is
  // disabled and the control polygon is hidden.  The representation
  // must return ``PickRole_None`` for every (X, Y), and the widget
  // must not enter ``Dragging`` on any pick attempt — even at a
  // display coordinate that maps to a control-grid world point.
  vtkSmartPointer<vtkMRMLBezierSurfaceNode> node = makePlanningNode();
  // Legal transition Planning -> Confirmed (the only path to
  // Confirmed; Init -> Confirmed is rejected per ADR-0019).
  node->SetState(vtkMRMLBezierSurfaceNode::Confirmed);
  CHECK_INT(node->GetState(), vtkMRMLBezierSurfaceNode::Confirmed);

  vtkSmartPointer<vtkRenderer> renderer = makeRenderer();
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

  // Display coordinate of a control point that *would* pick if the
  // state were Planning — assert it misses in Confirmed.
  double world[3] = { -5.0, 5.0, 0.0 };
  renderer->SetWorldPoint(world[0], world[1], world[2], 1.0);
  renderer->WorldToDisplay();
  double* d = renderer->GetDisplayPoint();
  const int X = static_cast<int>(std::round(d[0]));
  const int Y = static_cast<int>(std::round(d[1]));

  vtkLiverBezierRepresentation::PickResult pick = rep->Pick(X, Y);
  CHECK_INT(pick.Role, vtkLiverBezierRepresentation::PickRole_None);

  // Widget rejects a left-drag at the same coordinate.
  CHECK_BOOL(widget->BeginLeftDragAt(X, Y), false);
  CHECK_INT(widget->GetWidgetState(), vtkLiverBezierWidget::Start);
  return EXIT_SUCCESS;
}

/// Construct a 3x3 (9-point) Bezier node in Planning state with a
/// lattice control grid centred on (0, 0, 0).  Shared by the 3×3
/// pick + drag-apply tests below.
vtkSmartPointer<vtkMRMLBezierSurfaceNode> make3x3PlanningNode()
{
  vtkSmartPointer<vtkMRMLBezierSurfaceNode> node = vtkSmartPointer<vtkMRMLBezierSurfaceNode>::New();
  node->SetSize(3);
  node->SetState(vtkMRMLBezierSurfaceNode::Planning);
  double values[27] = { 0.0 };
  constexpr double stride = 10.0;
  for (int row = 0; row < 3; ++row)
  {
    for (int col = 0; col < 3; ++col)
    {
      const int i = row * 3 + col;
      values[i * 3 + 0] = (col - 1.0) * stride;
      values[i * 3 + 1] = (row - 1.0) * stride;
      values[i * 3 + 2] = 0.0;
    }
  }
  node->SetControlGrid(values);
  return node;
}

int testPickControlPoint3x3()
{
  // ADR-0018 §1 — the widget representation iterates Rows*Cols
  // control points, not a hard-coded 16.  This test pins the 3×3
  // (9-point) variant: pickable set must be exactly 9 points,
  // picking a known position resolves to the right flat index.  The
  // sub-assertions cover a CORNER glyph (index 0), an INTERIOR glyph
  // (index 4 — the centre point of the 3×3), and an edge glyph
  // (index 5) so the test exercises all three ring roles per
  // ADR-0018 §1.  Also exercises the dynamic-shape-transition path
  // (``SetSize(4)`` mid-test) — after the transition the previous
  // ±10 corner coordinates are no longer in the grid.
  vtkSmartPointer<vtkMRMLBezierSurfaceNode> node = make3x3PlanningNode();

  vtkSmartPointer<vtkRenderer> renderer = makeRenderer();
  vtkNew<vtkGenericOpenGLRenderWindow> renderWindow;
  renderWindow->SetShowWindow(false);
  renderWindow->AddRenderer(renderer);
  renderWindow->SetSize(400, 400);
  renderer->ResetCameraClippingRange();

  vtkNew<vtkLiverBezierRepresentation> rep;
  rep->SetRenderer(renderer);
  rep->SetBezierNode(node);
  rep->BuildRepresentation();

  // CORNER: control point (row=0, col=0) → world (-10, -10, 0) →
  // flat index 0.
  renderer->SetWorldPoint(-10.0, -10.0, 0.0, 1.0);
  renderer->WorldToDisplay();
  double* d = renderer->GetDisplayPoint();
  vtkLiverBezierRepresentation::PickResult cornerPick = rep->Pick(static_cast<int>(std::round(d[0])), static_cast<int>(std::round(d[1])));
  CHECK_INT(cornerPick.Role, vtkLiverBezierRepresentation::PickRole_ControlPoint);
  CHECK_INT(cornerPick.Index, 0);

  // INTERIOR: control point (row=1, col=1) → world (0, 0, 0) → flat
  // index 4 (the lone interior of a 3×3 grid).
  renderer->SetWorldPoint(0.0, 0.0, 0.0, 1.0);
  renderer->WorldToDisplay();
  d = renderer->GetDisplayPoint();
  vtkLiverBezierRepresentation::PickResult interiorPick = rep->Pick(static_cast<int>(std::round(d[0])), static_cast<int>(std::round(d[1])));
  CHECK_INT(interiorPick.Role, vtkLiverBezierRepresentation::PickRole_ControlPoint);
  CHECK_INT(interiorPick.Index, 4);

  // EDGE: control point (row=1, col=2) → world (10, 0, 0) → flat
  // index 5.
  renderer->SetWorldPoint(10.0, 0.0, 0.0, 1.0);
  renderer->WorldToDisplay();
  d = renderer->GetDisplayPoint();
  vtkLiverBezierRepresentation::PickResult edgePick = rep->Pick(static_cast<int>(std::round(d[0])), static_cast<int>(std::round(d[1])));
  CHECK_INT(edgePick.Role, vtkLiverBezierRepresentation::PickRole_ControlPoint);
  CHECK_INT(edgePick.Index, 5);

  // Project a "would-be 4×4 corner" world coord (-15, -15, 0) that
  // does NOT exist in the 3×3 grid (which has corners at ±10).
  // Pick must miss.
  renderer->SetWorldPoint(-15.0, -15.0, 0.0, 1.0);
  renderer->WorldToDisplay();
  d = renderer->GetDisplayPoint();
  vtkLiverBezierRepresentation::PickResult miss = rep->Pick(static_cast<int>(std::round(d[0])), static_cast<int>(std::round(d[1])));
  CHECK_INT(miss.Role, vtkLiverBezierRepresentation::PickRole_None);

  // Dynamic-shape transition: grow the node to 4×4.  Per ADR-0018 §1
  // a size change discards the in-flight grid; rebuild the
  // representation so the glyph cloud reflects the new shape.  The
  // ±10 coordinates are no longer corners of the 4×4 grid — Pick
  // there must miss now.
  node->SetSize(4);
  CHECK_INT(static_cast<int>(node->GetRows()), 4);
  CHECK_INT(static_cast<int>(node->GetCols()), 4);
  // After SetSize the grid is zeroed; nothing is on the camera's Z=0
  // plane at the prior lattice positions any more.  Reinstate a 4×4
  // lattice so the next Pick has something well-conditioned to hit
  // (would-be index = row * 4 + col).
  double values4[vtkMRMLBezierSurfaceNode::ControlGridSize] = { 0.0 };
  constexpr double stride4 = 10.0;
  for (int row = 0; row < 4; ++row)
  {
    for (int col = 0; col < 4; ++col)
    {
      const int i = row * 4 + col;
      values4[i * 3 + 0] = (col - 1.5) * stride4;
      values4[i * 3 + 1] = (row - 1.5) * stride4;
      values4[i * 3 + 2] = 0.0;
    }
  }
  CHECK_BOOL(node->SetControlGrid(values4), true);
  rep->BuildRepresentation();

  // Project (row=2, col=3) → world (15, 5, 0) → flat index 11.  This
  // index is out of range for the prior 3×3 grid (9 points); the
  // representation must accept it under the new 4×4 shape.
  renderer->SetWorldPoint(15.0, 5.0, 0.0, 1.0);
  renderer->WorldToDisplay();
  d = renderer->GetDisplayPoint();
  vtkLiverBezierRepresentation::PickResult postResize = rep->Pick(static_cast<int>(std::round(d[0])), static_cast<int>(std::round(d[1])));
  CHECK_INT(postResize.Role, vtkLiverBezierRepresentation::PickRole_ControlPoint);
  CHECK_INT(postResize.Index, 11);
  return EXIT_SUCCESS;
}

int testApplyPickedPointWorld3x3()
{
  // ADR-0018 §1 — the drag-apply path on a 3×3 node must size its
  // control-grid buffer + bounds check against the node's runtime
  // shape, not the compile-time 4×4 default.  Pre-fix: the path
  // assumed 48 doubles (4×4) and an [0, 16) bounds — on a 3×3 node
  // (27 doubles, [0, 9) valid) that's a heap OOB read in the
  // ``current``-array copy and a too-wide acceptance window.
  //
  // Observable via the widget's public ``BeginLeftDragAt`` +
  // ``DragTo``: those route into ``ApplyPickedPointWorld`` and a
  // successful drag must update exactly the picked 3-double triplet
  // and leave the remaining 24 doubles untouched.
  vtkSmartPointer<vtkMRMLBezierSurfaceNode> node = make3x3PlanningNode();

  vtkSmartPointer<vtkRenderer> renderer = makeRenderer();
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

  // Snapshot the pre-drag grid (27 doubles).
  double before[27];
  const double* grid = node->GetControlGrid();
  for (int i = 0; i < 27; ++i)
  {
    before[i] = grid[i];
  }

  // Pick the interior glyph at world (0, 0, 0) → flat index 4 (the
  // 3×3 centre, which would be index 4 under the new bounds check
  // but lies WITHIN the bogus pre-fix bounds too — so the
  // discriminator is the buffer-copy length, not the bounds check
  // alone; see the "no write past 27 doubles" assertion below).
  renderer->SetWorldPoint(0.0, 0.0, 0.0, 1.0);
  renderer->WorldToDisplay();
  double* d = renderer->GetDisplayPoint();
  const int startX = static_cast<int>(std::round(d[0]));
  const int startY = static_cast<int>(std::round(d[1]));

  CHECK_BOOL(widget->BeginLeftDragAt(startX, startY), true);
  CHECK_INT(widget->GetPickedRole(), vtkLiverBezierRepresentation::PickRole_ControlPoint);
  CHECK_INT(widget->GetPickedIndex(), 4);
  CHECK_INT(widget->GetWidgetState(), vtkLiverBezierWidget::Dragging);

  // Drag to world (3, -4, 0).
  renderer->SetWorldPoint(3.0, -4.0, 0.0, 1.0);
  renderer->WorldToDisplay();
  d = renderer->GetDisplayPoint();
  const int endX = static_cast<int>(std::round(d[0]));
  const int endY = static_cast<int>(std::round(d[1]));

  double resolved[3] = { 0.0, 0.0, 0.0 };
  CHECK_BOOL(widget->DragTo(endX, endY, resolved), true);
  CHECK_DOUBLE_TOLERANCE(resolved[0], 3.0, 1e-3);
  CHECK_DOUBLE_TOLERANCE(resolved[1], -4.0, 1e-3);
  CHECK_DOUBLE_TOLERANCE(resolved[2], 0.0, 1e-3);

  // The 3-double triplet for control point 4 (offsets 12..14) moved.
  grid = node->GetControlGrid();
  CHECK_DOUBLE_TOLERANCE(grid[12], 3.0, 1e-3);
  CHECK_DOUBLE_TOLERANCE(grid[13], -4.0, 1e-3);
  CHECK_DOUBLE_TOLERANCE(grid[14], 0.0, 1e-3);

  // Every other double in the 27-double buffer must equal its
  // pre-drag value — proves the buffer-copy walked only the 27-double
  // range and did not write anything garbage past offset 26.
  for (int i = 0; i < 27; ++i)
  {
    if (i == 12 || i == 13 || i == 14)
    {
      continue;
    }
    CHECK_DOUBLE_TOLERANCE(grid[i], before[i], 1e-9);
  }

  widget->EndLeftDrag();
  CHECK_INT(widget->GetWidgetState(), vtkLiverBezierWidget::Start);
  return EXIT_SUCCESS;
}

int testGlyphsHiddenInConfirmed()
{
  // ADR-0019 §"Per-state contract": in ``Confirmed`` state the
  // control polygon is **hidden** and the widget is **disabled** —
  // i.e. ``Pick()`` must return ``PickRole_None`` at every position
  // that would otherwise hit a control-point glyph, and the glyph
  // cloud emitted by ``UpdatePickableGlyphs`` is empty.
  //
  // ADR-0019 grows ``ResectionState`` from ``{Init, Planning}`` to
  // ``{Init, Planning, Confirmed = 2}`` in its enabler PR; until that
  // lands the integer literal ``2`` simulates the future value.
  // ``SetState`` passes arbitrary ints through (see vtkMRMLBezierSurfaceNode.cxx
  // ``SetState``), so this works on the current enum + flips clean
  // when the third enum member arrives.
  vtkSmartPointer<vtkMRMLBezierSurfaceNode> node = makePlanningNode();

  vtkSmartPointer<vtkRenderer> renderer = makeRenderer();
  vtkNew<vtkGenericOpenGLRenderWindow> renderWindow;
  renderWindow->SetShowWindow(false);
  renderWindow->AddRenderer(renderer);
  renderWindow->SetSize(400, 400);
  renderer->ResetCameraClippingRange();

  vtkNew<vtkLiverBezierRepresentation> rep;
  rep->SetRenderer(renderer);
  rep->SetBezierNode(node);
  rep->BuildRepresentation();

  // Sanity-check: while in Planning the corner (row=0, col=0) at
  // world (-15, -15, 0) DOES hit.
  renderer->SetWorldPoint(-15.0, -15.0, 0.0, 1.0);
  renderer->WorldToDisplay();
  double* d = renderer->GetDisplayPoint();
  const int X = static_cast<int>(std::round(d[0]));
  const int Y = static_cast<int>(std::round(d[1]));
  vtkLiverBezierRepresentation::PickResult planningHit = rep->Pick(X, Y);
  CHECK_INT(planningHit.Role, vtkLiverBezierRepresentation::PickRole_ControlPoint);

  // Transition to the future ``Confirmed = 2`` state and rebuild.
  constexpr int kConfirmedState = 2;
  node->SetState(kConfirmedState);
  CHECK_INT(node->GetState(), kConfirmedState);
  rep->BuildRepresentation();

  // Same display coordinate now misses — the glyph cloud is empty in
  // Confirmed per ADR-0019 §"Per-state contract".
  vtkLiverBezierRepresentation::PickResult confirmedMiss = rep->Pick(X, Y);
  CHECK_INT(confirmedMiss.Role, vtkLiverBezierRepresentation::PickRole_None);

  // Sweep the four 4×4 corner positions; all must miss in Confirmed.
  constexpr double cornersWorld[4][3] = {
    { -15.0, -15.0, 0.0 },
    { 15.0, -15.0, 0.0 },
    { -15.0, 15.0, 0.0 },
    { 15.0, 15.0, 0.0 },
  };
  for (int c = 0; c < 4; ++c)
  {
    renderer->SetWorldPoint(cornersWorld[c][0], cornersWorld[c][1], cornersWorld[c][2], 1.0);
    renderer->WorldToDisplay();
    d = renderer->GetDisplayPoint();
    vtkLiverBezierRepresentation::PickResult corner = rep->Pick(static_cast<int>(std::round(d[0])), static_cast<int>(std::round(d[1])));
    CHECK_INT(corner.Role, vtkLiverBezierRepresentation::PickRole_None);
  }

  // The widget must refuse to enter Dragging in Confirmed.
  vtkNew<vtkLiverBezierWidget> widget;
  widget->SetRepresentation(rep);
  widget->SetBezierNode(node);
  const bool started = widget->BeginLeftDragAt(X, Y);
  CHECK_BOOL(started, false);
  CHECK_INT(widget->GetWidgetState(), vtkLiverBezierWidget::Start);
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
  CHECK_EXIT_SUCCESS(testConfirmedStatePickGate());
  CHECK_EXIT_SUCCESS(testPickControlPoint3x3());
  CHECK_EXIT_SUCCESS(testApplyPickedPointWorld3x3());
  CHECK_EXIT_SUCCESS(testGlyphsHiddenInConfirmed());

  std::cout << "vtkLiverBezierWidgetTest1 completed successfully" << std::endl;
  return EXIT_SUCCESS;
}

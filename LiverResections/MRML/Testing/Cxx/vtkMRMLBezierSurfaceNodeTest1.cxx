/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Tests for vtkMRMLBezierSurfaceNode — the data-only node landed by
  ADR-0014 §1.  Exercises:

   - defaults (constructor values)
   - State / InitializationMode enum round-trip
   - Bezier control grid round-trip
   - SlicingPlane init-mode subordinate data
   - DistanceSpheroid init-mode subordinate data
   - XML serialize/deserialize via an internal scene snapshot
   - CopyContent / DeepCopy

==============================================================================*/

// MRML includes
#include "vtkMRMLCoreTestingMacros.h"
#include "vtkMRMLBezierSurfaceDisplayNode.h"
#include "vtkMRMLBezierSurfaceNode.h"
#include "vtkMRMLScene.h"

// VTK includes
#include <vtkCallbackCommand.h>
#include <vtkCommand.h>
#include <vtkNew.h>
#include <vtkSmartPointer.h>

// STD includes
#include <cmath>
#include <iostream>
#include <sstream>
#include <string>

namespace
{

int testDefaults()
{
  vtkNew<vtkMRMLBezierSurfaceNode> node;

  CHECK_INT(node->GetState(), vtkMRMLBezierSurfaceNode::Init);
  CHECK_INT(node->GetInitMode(), vtkMRMLBezierSurfaceNode::SlicingPlane);
  CHECK_INT(node->GetNumberOfDistanceSpheroidInitPoints(), 0);
  CHECK_DOUBLE(node->GetDistanceSpheroidRadiusX(), 0.0);
  CHECK_DOUBLE(node->GetDistanceSpheroidRadiusY(), 0.0);
  CHECK_DOUBLE(node->GetDistanceSpheroidRadiusZ(), 0.0);

  // Control grid starts zero-filled.
  const double* grid = node->GetControlGrid();
  for (int i = 0; i < vtkMRMLBezierSurfaceNode::ControlGridSize; ++i)
  {
    CHECK_DOUBLE(grid[i], 0.0);
  }
  double origin[3] = { 1.0, 1.0, 1.0 };
  node->GetSlicingPlaneOrigin(origin);
  CHECK_DOUBLE(origin[0], 0.0);
  CHECK_DOUBLE(origin[1], 0.0);
  CHECK_DOUBLE(origin[2], 0.0);

  double normal[3] = { 0.0, 0.0, 0.0 };
  node->GetSlicingPlaneNormal(normal);
  CHECK_DOUBLE(normal[0], 0.0);
  CHECK_DOUBLE(normal[1], 0.0);
  CHECK_DOUBLE(normal[2], 1.0);

  CHECK_STRING(node->GetNodeTagName(), "BezierSurface");
  return EXIT_SUCCESS;
}

int testEnumRoundTrip()
{
  // Init -> Planning is the canonical forward edge; ADR-0019 adds the
  // Planning <-> Confirmed round-trip on top.  The dedicated
  // ``testInitDataReadOnlyAfterPlanning`` and
  // ``testConfirmedStateTransitions`` sub-tests below characterise the
  // legal transition cycle and every forbidden edge.  Here we just
  // exercise the enum string converters across all three states.
  vtkNew<vtkMRMLBezierSurfaceNode> node;
  node->SetState(vtkMRMLBezierSurfaceNode::Planning);
  CHECK_INT(node->GetState(), vtkMRMLBezierSurfaceNode::Planning);

  vtkNew<vtkMRMLBezierSurfaceNode> nodeInit;
  CHECK_INT(nodeInit->GetState(), vtkMRMLBezierSurfaceNode::Init);

  node->SetInitMode(vtkMRMLBezierSurfaceNode::DistanceSpheroid);
  CHECK_INT(node->GetInitMode(), vtkMRMLBezierSurfaceNode::DistanceSpheroid);

  CHECK_STRING(vtkMRMLBezierSurfaceNode::GetStateAsString(vtkMRMLBezierSurfaceNode::Init), "Init");
  CHECK_STRING(vtkMRMLBezierSurfaceNode::GetStateAsString(vtkMRMLBezierSurfaceNode::Planning), "Planning");
  CHECK_STRING(vtkMRMLBezierSurfaceNode::GetStateAsString(vtkMRMLBezierSurfaceNode::Confirmed), "Confirmed");
  CHECK_INT(vtkMRMLBezierSurfaceNode::GetStateFromString("Init"), vtkMRMLBezierSurfaceNode::Init);
  CHECK_INT(vtkMRMLBezierSurfaceNode::GetStateFromString("Planning"), vtkMRMLBezierSurfaceNode::Planning);
  CHECK_INT(vtkMRMLBezierSurfaceNode::GetStateFromString("Confirmed"), vtkMRMLBezierSurfaceNode::Confirmed);
  CHECK_INT(vtkMRMLBezierSurfaceNode::GetStateFromString("bogus"), -1);

  CHECK_STRING(vtkMRMLBezierSurfaceNode::GetInitModeAsString(vtkMRMLBezierSurfaceNode::SlicingPlane), "SlicingPlane");
  CHECK_STRING(vtkMRMLBezierSurfaceNode::GetInitModeAsString(vtkMRMLBezierSurfaceNode::DistanceSpheroid), "DistanceSpheroid");
  CHECK_INT(vtkMRMLBezierSurfaceNode::GetInitModeFromString("DistanceSpheroid"), vtkMRMLBezierSurfaceNode::DistanceSpheroid);
  CHECK_INT(vtkMRMLBezierSurfaceNode::GetInitModeFromString(nullptr), -1);
  return EXIT_SUCCESS;
}

int testConfirmedStateTransitions()
{
  // ADR-0019 transition matrix:
  //
  //   Init      -> Planning   allowed.
  //   Planning  -> Confirmed  allowed.
  //   Confirmed -> Planning   allowed (round-trip).
  //   Init      -> Confirmed  forbidden.
  //   Planning  -> Init       forbidden (also covered by
  //                            ``testInitDataReadOnlyAfterPlanning``).
  //   Confirmed -> Init       forbidden.
  //
  // Each rejected transition emits a vtkWarningMacro and leaves the
  // state unchanged; advance/non-advance of GetMTime() is the
  // observable proxy.

  // ---- Legal path: Init -> Planning -> Confirmed -> Planning ----
  vtkNew<vtkMRMLBezierSurfaceNode> node;
  CHECK_INT(node->GetState(), vtkMRMLBezierSurfaceNode::Init);

  // Init -> Planning (forward edge).
  vtkMTimeType pre = node->GetMTime();
  node->SetState(vtkMRMLBezierSurfaceNode::Planning);
  CHECK_INT(node->GetState(), vtkMRMLBezierSurfaceNode::Planning);
  if (node->GetMTime() <= pre)
  {
    std::cerr << "Expected MTime advance on Init -> Planning\n";
    return EXIT_FAILURE;
  }

  // Planning -> Confirmed.
  pre = node->GetMTime();
  node->SetState(vtkMRMLBezierSurfaceNode::Confirmed);
  CHECK_INT(node->GetState(), vtkMRMLBezierSurfaceNode::Confirmed);
  if (node->GetMTime() <= pre)
  {
    std::cerr << "Expected MTime advance on Planning -> Confirmed\n";
    return EXIT_FAILURE;
  }

  // Confirmed -> Planning (round-trip).
  pre = node->GetMTime();
  node->SetState(vtkMRMLBezierSurfaceNode::Planning);
  CHECK_INT(node->GetState(), vtkMRMLBezierSurfaceNode::Planning);
  if (node->GetMTime() <= pre)
  {
    std::cerr << "Expected MTime advance on Confirmed -> Planning\n";
    return EXIT_FAILURE;
  }

  // Re-confirm — Planning -> Confirmed again.
  pre = node->GetMTime();
  node->SetState(vtkMRMLBezierSurfaceNode::Confirmed);
  CHECK_INT(node->GetState(), vtkMRMLBezierSurfaceNode::Confirmed);
  if (node->GetMTime() <= pre)
  {
    std::cerr << "Expected MTime advance on second Planning -> Confirmed\n";
    return EXIT_FAILURE;
  }

  // Same-state self-assign is a no-op (no warning, no MTime advance).
  pre = node->GetMTime();
  node->SetState(vtkMRMLBezierSurfaceNode::Confirmed);
  CHECK_INT(node->GetMTime(), pre);

  // ---- Forbidden: Confirmed -> Init ----
  TESTING_OUTPUT_ASSERT_WARNINGS_BEGIN();
  pre = node->GetMTime();
  node->SetState(vtkMRMLBezierSurfaceNode::Init);
  TESTING_OUTPUT_ASSERT_WARNINGS_END();
  CHECK_INT(node->GetState(), vtkMRMLBezierSurfaceNode::Confirmed);
  CHECK_INT(node->GetMTime(), pre);

  // ---- Forbidden: Init -> Confirmed (fresh node) ----
  vtkNew<vtkMRMLBezierSurfaceNode> nodeInit;
  CHECK_INT(nodeInit->GetState(), vtkMRMLBezierSurfaceNode::Init);
  TESTING_OUTPUT_ASSERT_WARNINGS_BEGIN();
  pre = nodeInit->GetMTime();
  nodeInit->SetState(vtkMRMLBezierSurfaceNode::Confirmed);
  TESTING_OUTPUT_ASSERT_WARNINGS_END();
  CHECK_INT(nodeInit->GetState(), vtkMRMLBezierSurfaceNode::Init);
  CHECK_INT(nodeInit->GetMTime(), pre);

  // Audit-data setters stay rejected in Confirmed (per ADR-0019
  // §"Per-state contract": init data is read-only in both Planning
  // and Confirmed).  Drive the node to Confirmed via the legal path
  // and assert the guard fires.
  vtkNew<vtkMRMLBezierSurfaceNode> guarded;
  double origin[3] = { 1.0, 2.0, 3.0 };
  guarded->SetSlicingPlaneOrigin(origin);
  guarded->SetState(vtkMRMLBezierSurfaceNode::Planning);
  guarded->SetState(vtkMRMLBezierSurfaceNode::Confirmed);
  CHECK_INT(guarded->GetState(), vtkMRMLBezierSurfaceNode::Confirmed);

  TESTING_OUTPUT_ASSERT_WARNINGS_BEGIN();
  pre = guarded->GetMTime();
  double clobber[3] = { 99.0, 99.0, 99.0 };
  guarded->SetSlicingPlaneOrigin(clobber);
  TESTING_OUTPUT_ASSERT_WARNINGS_END();
  CHECK_INT(guarded->GetMTime(), pre);
  double readBack[3];
  guarded->GetSlicingPlaneOrigin(readBack);
  CHECK_DOUBLE(readBack[0], 1.0);

  // Control-grid IS editable in Confirmed at the data-node level — the
  // ADR-0019 §"Per-state contract" "control-grid mutable: no
  // (rejected)" row describes the UX-level lockout, enforced by the
  // widget (vtkLiverBezierWidget) and Representation gating, not by
  // the data node's macro setter.  Keeping the data-node setter open
  // preserves round-trippability of scene XML and the
  // Pipeline-driven SetState round-trip pattern (Confirmed ->
  // Planning -> edit -> Confirmed) without a defensive
  // unset/re-set dance.
  pre = guarded->GetMTime();
  double values[vtkMRMLBezierSurfaceNode::ControlGridSize];
  for (int i = 0; i < vtkMRMLBezierSurfaceNode::ControlGridSize; ++i)
  {
    values[i] = static_cast<double>(i);
  }
  guarded->SetControlGrid(values);
  if (guarded->GetMTime() <= pre)
  {
    std::cerr << "Expected SetControlGrid in Confirmed to fire Modified()\n";
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}

int testControlGridRoundTrip()
{
  vtkNew<vtkMRMLBezierSurfaceNode> node;

  // Fill with a structured pattern so any layout bug shows up.
  double values[vtkMRMLBezierSurfaceNode::ControlGridSize];
  for (int i = 0; i < vtkMRMLBezierSurfaceNode::ControlGridSize; ++i)
  {
    values[i] = static_cast<double>(i) * 0.5 + 0.25;
  }
  CHECK_BOOL(node->SetControlGrid(values), true);

  const double* grid = node->GetControlGrid();
  for (int i = 0; i < vtkMRMLBezierSurfaceNode::ControlGridSize; ++i)
  {
    CHECK_DOUBLE(grid[i], values[i]);
  }

  // Null pointer rejected.
  CHECK_BOOL(node->SetControlGrid(nullptr), false);
  // Re-check values were not clobbered.
  for (int i = 0; i < vtkMRMLBezierSurfaceNode::ControlGridSize; ++i)
  {
    CHECK_DOUBLE(node->GetControlGrid()[i], values[i]);
  }
  return EXIT_SUCCESS;
}

int testSlicingPlaneInit()
{
  vtkNew<vtkMRMLBezierSurfaceNode> node;

  double p0[3] = { 1.0, 2.0, 3.0 };
  double p1[3] = { -1.5, 4.0, 7.25 };
  CHECK_BOOL(node->SetSlicingPlaneInitPoint(0, p0), true);
  CHECK_BOOL(node->SetSlicingPlaneInitPoint(1, p1), true);
  CHECK_BOOL(node->SetSlicingPlaneInitPoint(2, p0), false);
  CHECK_BOOL(node->SetSlicingPlaneInitPoint(-1, p0), false);
  CHECK_BOOL(node->SetSlicingPlaneInitPoint(0, nullptr), false);

  const double* got0 = node->GetSlicingPlaneInitPoint(0);
  CHECK_NOT_NULL(got0);
  CHECK_DOUBLE(got0[0], 1.0);
  CHECK_DOUBLE(got0[1], 2.0);
  CHECK_DOUBLE(got0[2], 3.0);

  const double* got1 = node->GetSlicingPlaneInitPoint(1);
  CHECK_NOT_NULL(got1);
  CHECK_DOUBLE(got1[0], -1.5);
  CHECK_DOUBLE(got1[1], 4.0);
  CHECK_DOUBLE(got1[2], 7.25);

  CHECK_NULL(node->GetSlicingPlaneInitPoint(2));

  double origin[3] = { 10.0, 20.0, 30.0 };
  double normal[3] = { 0.0, 1.0, 0.0 };
  node->SetSlicingPlaneOrigin(origin);
  node->SetSlicingPlaneNormal(normal);
  double readBack[3];
  node->GetSlicingPlaneOrigin(readBack);
  CHECK_DOUBLE(readBack[0], 10.0);
  CHECK_DOUBLE(readBack[1], 20.0);
  CHECK_DOUBLE(readBack[2], 30.0);
  node->GetSlicingPlaneNormal(readBack);
  CHECK_DOUBLE(readBack[0], 0.0);
  CHECK_DOUBLE(readBack[1], 1.0);
  CHECK_DOUBLE(readBack[2], 0.0);
  return EXIT_SUCCESS;
}

int testDistanceSpheroidInit()
{
  vtkNew<vtkMRMLBezierSurfaceNode> node;

  node->SetNumberOfDistanceSpheroidInitPoints(3);
  CHECK_INT(node->GetNumberOfDistanceSpheroidInitPoints(), 3);

  double p0[3] = { 0.1, 0.2, 0.3 };
  double p1[3] = { 1.1, 1.2, 1.3 };
  double p2[3] = { 2.1, 2.2, 2.3 };
  CHECK_BOOL(node->SetDistanceSpheroidInitPoint(0, p0), true);
  CHECK_BOOL(node->SetDistanceSpheroidInitPoint(1, p1), true);
  CHECK_BOOL(node->SetDistanceSpheroidInitPoint(2, p2), true);
  // Out-of-range / null rejected.
  CHECK_BOOL(node->SetDistanceSpheroidInitPoint(3, p0), false);
  CHECK_BOOL(node->SetDistanceSpheroidInitPoint(-1, p0), false);
  CHECK_BOOL(node->SetDistanceSpheroidInitPoint(0, nullptr), false);

  for (int i = 0; i < 3; ++i)
  {
    const double* got = node->GetDistanceSpheroidInitPoint(i);
    CHECK_NOT_NULL(got);
    CHECK_DOUBLE(got[0], static_cast<double>(i) + 0.1);
    CHECK_DOUBLE(got[1], static_cast<double>(i) + 0.2);
    CHECK_DOUBLE(got[2], static_cast<double>(i) + 0.3);
  }
  CHECK_NULL(node->GetDistanceSpheroidInitPoint(3));

  double center[3] = { 5.0, 6.0, 7.0 };
  node->SetDistanceSpheroidCenter(center);
  double readBack[3];
  node->GetDistanceSpheroidCenter(readBack);
  CHECK_DOUBLE(readBack[0], 5.0);
  CHECK_DOUBLE(readBack[1], 6.0);
  CHECK_DOUBLE(readBack[2], 7.0);

  node->SetDistanceSpheroidRadiusX(2.5);
  node->SetDistanceSpheroidRadiusY(3.5);
  node->SetDistanceSpheroidRadiusZ(4.5);
  CHECK_DOUBLE(node->GetDistanceSpheroidRadiusX(), 2.5);
  CHECK_DOUBLE(node->GetDistanceSpheroidRadiusY(), 3.5);
  CHECK_DOUBLE(node->GetDistanceSpheroidRadiusZ(), 4.5);

  // Clamp on negative — vtkSetClampMacro pins to >= 0.
  node->SetDistanceSpheroidRadiusX(-1.0);
  CHECK_DOUBLE(node->GetDistanceSpheroidRadiusX(), 0.0);

  // Shrink-and-grow: shrinking to 1 then back to 3 should zero-fill.
  node->SetNumberOfDistanceSpheroidInitPoints(1);
  CHECK_INT(node->GetNumberOfDistanceSpheroidInitPoints(), 1);
  CHECK_NULL(node->GetDistanceSpheroidInitPoint(1));
  node->SetNumberOfDistanceSpheroidInitPoints(3);
  for (int i = 0; i < 3; ++i)
  {
    const double* got = node->GetDistanceSpheroidInitPoint(i);
    CHECK_NOT_NULL(got);
    CHECK_DOUBLE(got[0], 0.0);
    CHECK_DOUBLE(got[1], 0.0);
    CHECK_DOUBLE(got[2], 0.0);
  }
  return EXIT_SUCCESS;
}

int testXMLRoundTrip()
{
  vtkNew<vtkMRMLBezierSurfaceNode> source;
  vtkNew<vtkMRMLScene> scene;
  source->SetScene(scene.GetPointer());

  // Populate Init-mode subordinate data BEFORE transitioning to
  // Planning — per ADR-0014 §4, that data is read-only after the
  // transition and the per-setter guards reject post-Planning
  // mutation.  This test exercises the round-trip; the order matches
  // the production Init→Planning lifecycle.
  source->SetInitMode(vtkMRMLBezierSurfaceNode::DistanceSpheroid);

  double p0[3] = { 1.0, 2.0, 3.0 };
  double p1[3] = { -4.0, 5.0, -6.0 };
  source->SetSlicingPlaneInitPoint(0, p0);
  source->SetSlicingPlaneInitPoint(1, p1);
  double origin[3] = { 7.5, 8.5, 9.5 };
  double normal[3] = { 0.0, 0.0, -1.0 };
  source->SetSlicingPlaneOrigin(origin);
  source->SetSlicingPlaneNormal(normal);

  source->SetNumberOfDistanceSpheroidInitPoints(2);
  double q0[3] = { 11.0, 12.0, 13.0 };
  double q1[3] = { 14.0, 15.0, 16.0 };
  source->SetDistanceSpheroidInitPoint(0, q0);
  source->SetDistanceSpheroidInitPoint(1, q1);
  double center[3] = { 17.0, 18.0, 19.0 };
  source->SetDistanceSpheroidCenter(center);
  source->SetDistanceSpheroidRadiusX(2.0);
  source->SetDistanceSpheroidRadiusY(3.0);
  source->SetDistanceSpheroidRadiusZ(4.0);

  // Now transition to Planning and write the Bezier grid (the only
  // mutable geometry post-transition).  Init-mode data above is now
  // read-only audit data.
  source->SetState(vtkMRMLBezierSurfaceNode::Planning);

  double values[vtkMRMLBezierSurfaceNode::ControlGridSize];
  for (int i = 0; i < vtkMRMLBezierSurfaceNode::ControlGridSize; ++i)
  {
    values[i] = std::sin(static_cast<double>(i) * 0.1);
  }
  source->SetControlGrid(values);

  // Serialize to a string buffer.
  std::ostringstream out;
  source->WriteXML(out, 0);
  const std::string xml = out.str();

  // Parse the attribute string back into a name=value pointer array.
  // WriteXML emits attributes as `name="value"` separated by spaces.
  std::vector<std::string> storage; // owns the parsed strings
  // Naive parser: walks the XML attribute list emitted by WriteXML.
  // This is good enough for the round-trip test; the production load
  // path goes through libxml2, which is not linked into this test.
  std::size_t pos = 0;
  while (pos < xml.size())
  {
    while (pos < xml.size() && std::isspace(xml[pos]))
    {
      ++pos;
    }
    if (pos >= xml.size())
    {
      break;
    }
    const std::size_t eq = xml.find('=', pos);
    if (eq == std::string::npos)
    {
      break;
    }
    std::string name = xml.substr(pos, eq - pos);
    if (eq + 1 >= xml.size() || xml[eq + 1] != '"')
    {
      break;
    }
    const std::size_t valStart = eq + 2;
    const std::size_t valEnd = xml.find('"', valStart);
    if (valEnd == std::string::npos)
    {
      break;
    }
    std::string value = xml.substr(valStart, valEnd - valStart);
    storage.push_back(name);
    storage.push_back(value);
    pos = valEnd + 1;
  }

  std::vector<const char*> atts;
  atts.reserve(storage.size() + 1);
  for (const auto& s : storage)
  {
    atts.push_back(s.c_str());
  }
  atts.push_back(nullptr);

  vtkNew<vtkMRMLBezierSurfaceNode> sink;
  sink->SetScene(scene.GetPointer());
  sink->ReadXMLAttributes(atts.data());

  CHECK_INT(sink->GetState(), source->GetState());
  CHECK_INT(sink->GetInitMode(), source->GetInitMode());

  for (int i = 0; i < vtkMRMLBezierSurfaceNode::ControlGridSize; ++i)
  {
    // Bit-equivalence is not guaranteed across decimal round-trip
    // (ostream<< double uses default precision); a tight tolerance
    // tracks the worst case.  This is the same trade-off Slicer's
    // own vtkMRMLPlotSeriesNode XML serialisation accepts.
    CHECK_DOUBLE_TOLERANCE(sink->GetControlGrid()[i], source->GetControlGrid()[i], 1e-5);
  }

  for (int i = 0; i < 2; ++i)
  {
    const double* a = sink->GetSlicingPlaneInitPoint(i);
    const double* b = source->GetSlicingPlaneInitPoint(i);
    CHECK_NOT_NULL(a);
    CHECK_NOT_NULL(b);
    for (int j = 0; j < 3; ++j)
    {
      CHECK_DOUBLE_TOLERANCE(a[j], b[j], 1e-5);
    }
  }

  double a3[3], b3[3];
  sink->GetSlicingPlaneOrigin(a3);
  source->GetSlicingPlaneOrigin(b3);
  for (int j = 0; j < 3; ++j)
  {
    CHECK_DOUBLE_TOLERANCE(a3[j], b3[j], 1e-5);
  }
  sink->GetSlicingPlaneNormal(a3);
  source->GetSlicingPlaneNormal(b3);
  for (int j = 0; j < 3; ++j)
  {
    CHECK_DOUBLE_TOLERANCE(a3[j], b3[j], 1e-5);
  }

  CHECK_INT(sink->GetNumberOfDistanceSpheroidInitPoints(), source->GetNumberOfDistanceSpheroidInitPoints());
  for (int i = 0; i < sink->GetNumberOfDistanceSpheroidInitPoints(); ++i)
  {
    const double* a = sink->GetDistanceSpheroidInitPoint(i);
    const double* b = source->GetDistanceSpheroidInitPoint(i);
    CHECK_NOT_NULL(a);
    CHECK_NOT_NULL(b);
    for (int j = 0; j < 3; ++j)
    {
      CHECK_DOUBLE_TOLERANCE(a[j], b[j], 1e-5);
    }
  }

  sink->GetDistanceSpheroidCenter(a3);
  source->GetDistanceSpheroidCenter(b3);
  for (int j = 0; j < 3; ++j)
  {
    CHECK_DOUBLE_TOLERANCE(a3[j], b3[j], 1e-5);
  }

  CHECK_DOUBLE_TOLERANCE(sink->GetDistanceSpheroidRadiusX(), source->GetDistanceSpheroidRadiusX(), 1e-5);
  CHECK_DOUBLE_TOLERANCE(sink->GetDistanceSpheroidRadiusY(), source->GetDistanceSpheroidRadiusY(), 1e-5);
  CHECK_DOUBLE_TOLERANCE(sink->GetDistanceSpheroidRadiusZ(), source->GetDistanceSpheroidRadiusZ(), 1e-5);
  return EXIT_SUCCESS;
}

int testDisplayNodeAttachedSceneRoundTrip()
{
  // The data-node reparent to vtkMRMLDisplayableNode (this PR) unlocks
  // a first-class display-node observation chain.  This test exercises
  // the end-to-end round-trip — data node + display node in a scene,
  // mutated, serialised, reloaded — and asserts the reloaded data
  // node still points at a reloaded display node carrying the mutated
  // values.  This is the structural payoff of the reparent and the
  // strongest single signal that the LayerDM Pipeline path will
  // work once T2.2 wires it.
  vtkNew<vtkMRMLScene> scene;
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLBezierSurfaceNode>::New());
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLBezierSurfaceDisplayNode>::New());

  vtkNew<vtkMRMLBezierSurfaceNode> dataNode;
  scene->AddNode(dataNode.GetPointer());
  vtkNew<vtkMRMLBezierSurfaceDisplayNode> displayNode;
  scene->AddNode(displayNode.GetPointer());
  dataNode->AddAndObserveDisplayNodeID(displayNode->GetID());

  // Mutate both nodes with distinctive values.
  dataNode->SetState(vtkMRMLBezierSurfaceNode::Planning);
  dataNode->SetInitMode(vtkMRMLBezierSurfaceNode::DistanceSpheroid);
  double values[vtkMRMLBezierSurfaceNode::ControlGridSize];
  for (int i = 0; i < vtkMRMLBezierSurfaceNode::ControlGridSize; ++i)
  {
    values[i] = static_cast<double>(i) * 0.25 + 0.125;
  }
  dataNode->SetControlGrid(values);

  float colour[3] = { 0.4f, 0.5f, 0.6f };
  displayNode->SetResectionColor(colour);
  displayNode->SetResectionOpacity(0.42f);
  displayNode->SetGridVisibility(true);
  displayNode->SetClipOut(true);

  // Round-trip via the in-memory XML string path (avoids libxml2 +
  // tempfile dance; equivalent to file-based Commit/Connect for the
  // purpose of this test).
  scene->SetSaveToXMLString(1);
  scene->Commit();
  const std::string xml = scene->GetSceneXMLString();
  if (xml.empty())
  {
    std::cerr << "Commit produced empty XML string\n";
    return EXIT_FAILURE;
  }

  vtkNew<vtkMRMLScene> sinkScene;
  sinkScene->RegisterNodeClass(vtkSmartPointer<vtkMRMLBezierSurfaceNode>::New());
  sinkScene->RegisterNodeClass(vtkSmartPointer<vtkMRMLBezierSurfaceDisplayNode>::New());
  sinkScene->SetLoadFromXMLString(1);
  sinkScene->SetSceneXMLString(xml);
  sinkScene->Connect();

  auto* sinkData = vtkMRMLBezierSurfaceNode::SafeDownCast(sinkScene->GetFirstNodeByClass("vtkMRMLBezierSurfaceNode"));
  CHECK_NOT_NULL(sinkData);
  CHECK_INT(sinkData->GetState(), vtkMRMLBezierSurfaceNode::Planning);
  CHECK_INT(sinkData->GetInitMode(), vtkMRMLBezierSurfaceNode::DistanceSpheroid);
  for (int i = 0; i < vtkMRMLBezierSurfaceNode::ControlGridSize; ++i)
  {
    CHECK_DOUBLE_TOLERANCE(sinkData->GetControlGrid()[i], values[i], 1e-5);
  }

  // The display-node reference must have round-tripped through the
  // scene — this is the structural assertion that the reparent
  // bought.
  auto* sinkDisplay = vtkMRMLBezierSurfaceDisplayNode::SafeDownCast(sinkData->GetNthDisplayNode(0));
  CHECK_NOT_NULL(sinkDisplay);
  float rgb[3];
  sinkDisplay->GetResectionColor(rgb);
  CHECK_DOUBLE_TOLERANCE(rgb[0], 0.4f, 1e-5);
  CHECK_DOUBLE_TOLERANCE(rgb[1], 0.5f, 1e-5);
  CHECK_DOUBLE_TOLERANCE(rgb[2], 0.6f, 1e-5);
  CHECK_DOUBLE_TOLERANCE(sinkDisplay->GetResectionOpacity(), 0.42f, 1e-5);
  CHECK_BOOL(sinkDisplay->GetGridVisibility(), true);
  CHECK_BOOL(sinkDisplay->GetClipOut(), true);
  return EXIT_SUCCESS;
}

/// Assert that calling ``setter()`` advances ``node->GetMTime()``.
/// Helper macro so the per-setter scaffolding stays terse.
#define EXPECT_MTIME_ADVANCES(NODE, SETTER_CALL)                                                                                              \
  do                                                                                                                                          \
  {                                                                                                                                           \
    const vtkMTimeType _baseline = (NODE)->GetMTime();                                                                                        \
    SETTER_CALL;                                                                                                                              \
    if ((NODE)->GetMTime() <= _baseline)                                                                                                      \
    {                                                                                                                                         \
      std::cerr << "Expected MTime to advance after " #SETTER_CALL << " (baseline=" << _baseline << ", post=" << (NODE)->GetMTime() << ")\n"; \
      return EXIT_FAILURE;                                                                                                                    \
    }                                                                                                                                         \
  } while (0)

int testModifiedEventsOnSetters()
{
  // ADR-0008 §2 — characterise the Modified() contract on every
  // public setter so a future drift (e.g. a setter that drops its
  // ``this->Modified()`` call) fires a regression here rather than
  // silently breaking observers downstream of the data node.
  //
  // Strategy: for each setter, capture GetMTime() before, call the
  // setter with a value distinct from the current one, assert MTime
  // strictly advanced.  The macro-generated setters
  // (vtkSetMacro / vtkSetVector3Macro / vtkSetClampMacro) emit
  // Modified() only when the new value differs, so we always feed a
  // known-different value.
  vtkNew<vtkMRMLBezierSurfaceNode> node;

  // InitMode is mutable in both states (ADR-0014 §4 tags it on
  // transition); exercise it first.  Default is SlicingPlane.
  EXPECT_MTIME_ADVANCES(node, node->SetInitMode(vtkMRMLBezierSurfaceNode::DistanceSpheroid));

  // SlicingPlane init data — explicit setters and explicit
  // double-x/y/z setters.  Must run while State == Init per
  // ADR-0014 §4.
  double p[3] = { 1.0, 2.0, 3.0 };
  EXPECT_MTIME_ADVANCES(node, node->SetSlicingPlaneInitPoint(0, p));
  double p2[3] = { 4.0, 5.0, 6.0 };
  EXPECT_MTIME_ADVANCES(node, node->SetSlicingPlaneInitPoint(1, p2));
  double origin[3] = { 7.0, 8.0, 9.0 };
  EXPECT_MTIME_ADVANCES(node, node->SetSlicingPlaneOrigin(origin));
  double normal[3] = { 1.0, 0.0, 0.0 };
  EXPECT_MTIME_ADVANCES(node, node->SetSlicingPlaneNormal(normal));

  // DistanceSpheroid init data — explicit setters.  Same lifecycle
  // constraint: pre-transition only.
  EXPECT_MTIME_ADVANCES(node, node->SetNumberOfDistanceSpheroidInitPoints(2));
  double q[3] = { 10.0, 11.0, 12.0 };
  EXPECT_MTIME_ADVANCES(node, node->SetDistanceSpheroidInitPoint(0, q));
  double q2[3] = { 13.0, 14.0, 15.0 };
  EXPECT_MTIME_ADVANCES(node, node->SetDistanceSpheroidInitPoint(1, q2));
  double center[3] = { 16.0, 17.0, 18.0 };
  EXPECT_MTIME_ADVANCES(node, node->SetDistanceSpheroidCenter(center));
  EXPECT_MTIME_ADVANCES(node, node->SetDistanceSpheroidRadiusX(2.5));
  EXPECT_MTIME_ADVANCES(node, node->SetDistanceSpheroidRadiusY(3.5));
  EXPECT_MTIME_ADVANCES(node, node->SetDistanceSpheroidRadiusZ(4.5));

  // State — Init → Planning is the one-way transition (ADR-0014 §4).
  EXPECT_MTIME_ADVANCES(node, node->SetState(vtkMRMLBezierSurfaceNode::Planning));

  // ControlGrid — explicit setter; the Bezier grid is the editable
  // geometry in Planning so MTime must advance here too.
  double values[vtkMRMLBezierSurfaceNode::ControlGridSize];
  for (int i = 0; i < vtkMRMLBezierSurfaceNode::ControlGridSize; ++i)
  {
    values[i] = static_cast<double>(i) + 0.5;
  }
  EXPECT_MTIME_ADVANCES(node, node->SetControlGrid(values));
  return EXIT_SUCCESS;
}

#undef EXPECT_MTIME_ADVANCES

int testCopyContent()
{
  vtkNew<vtkMRMLBezierSurfaceNode> source;
  source->SetInitMode(vtkMRMLBezierSurfaceNode::DistanceSpheroid);

  // Populate Init-mode subordinate data while still in Init; per
  // ADR-0014 §4 this data becomes read-only audit data after the
  // Init→Planning transition below.
  source->SetNumberOfDistanceSpheroidInitPoints(2);
  double q0[3] = { 1.0, 2.0, 3.0 };
  double q1[3] = { 4.0, 5.0, 6.0 };
  source->SetDistanceSpheroidInitPoint(0, q0);
  source->SetDistanceSpheroidInitPoint(1, q1);
  source->SetDistanceSpheroidRadiusX(1.5);
  source->SetDistanceSpheroidRadiusY(2.5);
  source->SetDistanceSpheroidRadiusZ(3.5);

  source->SetState(vtkMRMLBezierSurfaceNode::Planning);

  double values[vtkMRMLBezierSurfaceNode::ControlGridSize];
  for (int i = 0; i < vtkMRMLBezierSurfaceNode::ControlGridSize; ++i)
  {
    values[i] = static_cast<double>(i) + 0.125;
  }
  source->SetControlGrid(values);

  vtkNew<vtkMRMLBezierSurfaceNode> sink;
  sink->CopyContent(source.GetPointer(), /*deepCopy=*/true);

  CHECK_INT(sink->GetState(), source->GetState());
  CHECK_INT(sink->GetInitMode(), source->GetInitMode());
  for (int i = 0; i < vtkMRMLBezierSurfaceNode::ControlGridSize; ++i)
  {
    CHECK_DOUBLE(sink->GetControlGrid()[i], source->GetControlGrid()[i]);
  }
  CHECK_INT(sink->GetNumberOfDistanceSpheroidInitPoints(), 2);
  for (int i = 0; i < 2; ++i)
  {
    const double* a = sink->GetDistanceSpheroidInitPoint(i);
    const double* b = source->GetDistanceSpheroidInitPoint(i);
    CHECK_NOT_NULL(a);
    CHECK_NOT_NULL(b);
    for (int j = 0; j < 3; ++j)
    {
      CHECK_DOUBLE(a[j], b[j]);
    }
  }
  CHECK_DOUBLE(sink->GetDistanceSpheroidRadiusX(), 1.5);
  CHECK_DOUBLE(sink->GetDistanceSpheroidRadiusY(), 2.5);
  CHECK_DOUBLE(sink->GetDistanceSpheroidRadiusZ(), 3.5);

  // Mutating the source must not affect the sink (deep-copy semantics).
  // The source is in Planning so init-data mutation is rejected by the
  // ADR-0014 §4 guard — verify by transitioning a fresh node and
  // confirming the sink stays independent of subsequent edits made
  // pre-transition on a separate source.
  vtkNew<vtkMRMLBezierSurfaceNode> source2;
  source2->SetNumberOfDistanceSpheroidInitPoints(2);
  double override0[3] = { -99.0, -99.0, -99.0 };
  source2->SetDistanceSpheroidInitPoint(0, override0);
  // sink was deep-copied from ``source`` (not ``source2``), so this
  // independence check is trivially true; the meaningful assertion is
  // that the sink's value is the one carried from ``source``.
  CHECK_DOUBLE(sink->GetDistanceSpheroidInitPoint(0)[0], 1.0);
  return EXIT_SUCCESS;
}

int testInitDataReadOnlyAfterPlanning()
{
  // ADR-0014 §4: init-mode subordinate data is read-only audit data
  // after the Init→Planning transition.  Planning→Init drop-back is
  // not permitted.  This test characterises both invariants on every
  // gated setter.
  vtkNew<vtkMRMLBezierSurfaceNode> node;
  CHECK_INT(node->GetState(), vtkMRMLBezierSurfaceNode::Init);

  // Set Init-mode subordinate data while still in Init — every
  // mutation should land.
  double origin[3] = { 1.0, 2.0, 3.0 };
  node->SetSlicingPlaneOrigin(origin);
  double normal[3] = { 0.0, 1.0, 0.0 };
  node->SetSlicingPlaneNormal(normal);
  double p0[3] = { 4.0, 5.0, 6.0 };
  node->SetSlicingPlaneInitPoint(0, p0);
  double p1[3] = { 7.0, 8.0, 9.0 };
  node->SetSlicingPlaneInitPoint(1, p1);

  node->SetNumberOfDistanceSpheroidInitPoints(2);
  double q0[3] = { 10.0, 11.0, 12.0 };
  double q1[3] = { 13.0, 14.0, 15.0 };
  node->SetDistanceSpheroidInitPoint(0, q0);
  node->SetDistanceSpheroidInitPoint(1, q1);
  double center[3] = { 16.0, 17.0, 18.0 };
  node->SetDistanceSpheroidCenter(center);
  node->SetDistanceSpheroidRadiusX(1.5);
  node->SetDistanceSpheroidRadiusY(2.5);
  node->SetDistanceSpheroidRadiusZ(3.5);

  // Read back — everything landed.
  double readBack[3];
  node->GetSlicingPlaneOrigin(readBack);
  CHECK_DOUBLE(readBack[0], 1.0);
  CHECK_DOUBLE(readBack[1], 2.0);
  CHECK_DOUBLE(readBack[2], 3.0);
  CHECK_DOUBLE(node->GetSlicingPlaneInitPoint(0)[0], 4.0);
  CHECK_DOUBLE(node->GetDistanceSpheroidInitPoint(1)[2], 15.0);
  CHECK_DOUBLE(node->GetDistanceSpheroidRadiusX(), 1.5);

  // Forward transition Init → Planning is allowed.
  node->SetState(vtkMRMLBezierSurfaceNode::Planning);
  CHECK_INT(node->GetState(), vtkMRMLBezierSurfaceNode::Planning);

  // Baseline for the "MTime must not advance on a rejected mutation"
  // assertions below.
  const vtkMTimeType baselineMTime = node->GetMTime();

// Helper macro: assert that ``stmt`` does not change ``node``'s
// MTime — i.e. the setter short-circuited.  Inlined into this test
// because the broader EXPECT_MTIME_ADVANCES inverts the polarity.
#define EXPECT_MTIME_UNCHANGED(NODE, STMT)                                                                                       \
  do                                                                                                                             \
  {                                                                                                                              \
    const vtkMTimeType _pre = (NODE)->GetMTime();                                                                                \
    STMT;                                                                                                                        \
    if ((NODE)->GetMTime() != _pre)                                                                                              \
    {                                                                                                                            \
      std::cerr << "Expected MTime not to advance after " #STMT << " (pre=" << _pre << ", post=" << (NODE)->GetMTime() << ")\n"; \
      return EXIT_FAILURE;                                                                                                       \
    }                                                                                                                            \
  } while (0)

  // Every rejected setter below emits a deliberate vtkWarningMacro;
  // wrap the block so the test driver's WITH_VTK_ERROR_OUTPUT_CHECK
  // doesn't count those warnings as a failure.  The matching
  // ``..._END()`` re-arms the warning-as-failure counter and asserts
  // at least one warning fired in the block (so a silent-drop
  // regression also surfaces as a failure here).
  TESTING_OUTPUT_ASSERT_WARNINGS_BEGIN();

  // SlicingPlane mutations rejected post-Planning.
  double clobberOrigin[3] = { 100.0, 200.0, 300.0 };
  EXPECT_MTIME_UNCHANGED(node, node->SetSlicingPlaneOrigin(clobberOrigin));
  EXPECT_MTIME_UNCHANGED(node, node->SetSlicingPlaneOrigin(100.0, 200.0, 300.0));
  double clobberNormal[3] = { 1.0, 0.0, 0.0 };
  EXPECT_MTIME_UNCHANGED(node, node->SetSlicingPlaneNormal(clobberNormal));
  EXPECT_MTIME_UNCHANGED(node, node->SetSlicingPlaneNormal(1.0, 0.0, 0.0));
  double clobberP[3] = { -1.0, -2.0, -3.0 };
  // The bool-returning setter signals rejection via false return.
  CHECK_BOOL(node->SetSlicingPlaneInitPoint(0, clobberP), false);
  CHECK_INT(node->GetMTime(), baselineMTime); // no advance

  // DistanceSpheroid mutations rejected post-Planning.
  EXPECT_MTIME_UNCHANGED(node, node->SetNumberOfDistanceSpheroidInitPoints(5));
  CHECK_INT(node->GetNumberOfDistanceSpheroidInitPoints(), 2); // unchanged

  CHECK_BOOL(node->SetDistanceSpheroidInitPoint(0, clobberP), false);
  EXPECT_MTIME_UNCHANGED(node, node->SetDistanceSpheroidCenter(clobberOrigin));
  EXPECT_MTIME_UNCHANGED(node, node->SetDistanceSpheroidCenter(100.0, 200.0, 300.0));
  EXPECT_MTIME_UNCHANGED(node, node->SetDistanceSpheroidRadiusX(99.0));
  EXPECT_MTIME_UNCHANGED(node, node->SetDistanceSpheroidRadiusY(99.0));
  EXPECT_MTIME_UNCHANGED(node, node->SetDistanceSpheroidRadiusZ(99.0));

  TESTING_OUTPUT_ASSERT_WARNINGS_END();

  // Read back — every Init-mode value is still the one set pre-
  // transition.
  node->GetSlicingPlaneOrigin(readBack);
  CHECK_DOUBLE(readBack[0], 1.0);
  CHECK_DOUBLE(readBack[1], 2.0);
  CHECK_DOUBLE(readBack[2], 3.0);
  node->GetSlicingPlaneNormal(readBack);
  CHECK_DOUBLE(readBack[0], 0.0);
  CHECK_DOUBLE(readBack[1], 1.0);
  CHECK_DOUBLE(readBack[2], 0.0);
  CHECK_DOUBLE(node->GetSlicingPlaneInitPoint(0)[0], 4.0);
  CHECK_DOUBLE(node->GetSlicingPlaneInitPoint(1)[1], 8.0);
  node->GetDistanceSpheroidCenter(readBack);
  CHECK_DOUBLE(readBack[0], 16.0);
  CHECK_DOUBLE(readBack[1], 17.0);
  CHECK_DOUBLE(readBack[2], 18.0);
  CHECK_DOUBLE(node->GetDistanceSpheroidRadiusX(), 1.5);
  CHECK_DOUBLE(node->GetDistanceSpheroidRadiusY(), 2.5);
  CHECK_DOUBLE(node->GetDistanceSpheroidRadiusZ(), 3.5);
  CHECK_DOUBLE(node->GetDistanceSpheroidInitPoint(0)[0], 10.0);
  CHECK_DOUBLE(node->GetDistanceSpheroidInitPoint(1)[2], 15.0);

  // Planning → Init drop-back is rejected (ADR-0014 §4).  State must
  // remain Planning and MTime must not advance.  The rejection emits
  // a vtkWarningMacro — gate the assertion so the test driver does
  // not count it as a failure.
  TESTING_OUTPUT_ASSERT_WARNINGS_BEGIN();
  EXPECT_MTIME_UNCHANGED(node, node->SetState(vtkMRMLBezierSurfaceNode::Init));
  TESTING_OUTPUT_ASSERT_WARNINGS_END();
  CHECK_INT(node->GetState(), vtkMRMLBezierSurfaceNode::Planning);

  // Same-state self-assign is a no-op (no warning, no MTime advance).
  EXPECT_MTIME_UNCHANGED(node, node->SetState(vtkMRMLBezierSurfaceNode::Planning));

  // Control-grid IS editable in Planning — the one mutable geometry
  // per ADR-0013 §4.  This isn't strictly an init-data test but
  // verifies the guard is narrowly scoped to the audit fields.
  double values[vtkMRMLBezierSurfaceNode::ControlGridSize];
  for (int i = 0; i < vtkMRMLBezierSurfaceNode::ControlGridSize; ++i)
  {
    values[i] = static_cast<double>(i);
  }
  const vtkMTimeType pre = node->GetMTime();
  node->SetControlGrid(values);
  if (node->GetMTime() <= pre)
  {
    std::cerr << "Expected MTime to advance after SetControlGrid in "
              << "Planning state\n";
    return EXIT_FAILURE;
  }

  // InitMode is independent of the read-only audit fields and is
  // allowed to change in either state (ADR-0014 §1).  Currently
  // SlicingPlane (default); swap to DistanceSpheroid and verify
  // MTime advances.
  const vtkMTimeType preInitMode = node->GetMTime();
  node->SetInitMode(vtkMRMLBezierSurfaceNode::DistanceSpheroid);
  if (node->GetMTime() <= preInitMode)
  {
    std::cerr << "Expected MTime to advance after SetInitMode in "
              << "Planning state\n";
    return EXIT_FAILURE;
  }
  CHECK_INT(node->GetInitMode(), vtkMRMLBezierSurfaceNode::DistanceSpheroid);

#undef EXPECT_MTIME_UNCHANGED
  return EXIT_SUCCESS;
}

int testVariableSizeControlPolygon()
{
  // ADR-0018 §1 — Bezier control polygon admits exactly two square
  // shapes for v2.0.0: 3×3 (9 points, 27 doubles) and 4×4 (16 points,
  // 48 doubles).  Non-square + out-of-range shapes are rejected with
  // a vtkErrorMacro and no state change.  This test characterises
  // every branch of SetSize / SetRows / SetCols.
  vtkNew<vtkMRMLBezierSurfaceNode> node;

  // Default shape — pre-ADR-0018 4×4 baseline.
  CHECK_INT(static_cast<int>(node->GetRows()), 4);
  CHECK_INT(static_cast<int>(node->GetCols()), 4);
  CHECK_INT(static_cast<int>(node->GetControlGridLength()), 48);

  // Drop to 3×3 via SetSize.  Buffer resizes; MTime advances.
  const vtkMTimeType pre33 = node->GetMTime();
  node->SetSize(3);
  CHECK_INT(static_cast<int>(node->GetRows()), 3);
  CHECK_INT(static_cast<int>(node->GetCols()), 3);
  CHECK_INT(static_cast<int>(node->GetControlGridLength()), 27);
  if (node->GetMTime() <= pre33)
  {
    std::cerr << "Expected MTime to advance after SetSize(3)\n";
    return EXIT_FAILURE;
  }

  // Self-assign is a no-op (no MTime advance).
  const vtkMTimeType preNoop = node->GetMTime();
  node->SetSize(3);
  CHECK_INT(static_cast<int>(node->GetMTime()), static_cast<int>(preNoop));

  // Populate the 3×3 grid + read back.
  double grid33[27];
  for (int i = 0; i < 27; ++i)
  {
    grid33[i] = static_cast<double>(i) + 0.25;
  }
  CHECK_BOOL(node->SetControlGrid(grid33), true);
  const double* readBack = node->GetControlGrid();
  for (int i = 0; i < 27; ++i)
  {
    CHECK_DOUBLE(readBack[i], grid33[i]);
  }

  // Bump back up to 4×4.  Buffer resizes and zero-fills (ADR-0018
  // §1: shape change discards in-flight grid; surgeons re-seed).
  node->SetSize(4);
  CHECK_INT(static_cast<int>(node->GetRows()), 4);
  CHECK_INT(static_cast<int>(node->GetCols()), 4);
  CHECK_INT(static_cast<int>(node->GetControlGridLength()), 48);
  const double* afterResize = node->GetControlGrid();
  for (int i = 0; i < 48; ++i)
  {
    CHECK_DOUBLE(afterResize[i], 0.0);
  }

  // Out-of-range SetSize values are rejected (vtkErrorMacro;
  // gate around the ASSERT_ERRORS counter).
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  const vtkMTimeType preReject = node->GetMTime();
  node->SetSize(2); // below MinGridSize
  node->SetSize(5); // above MaxGridSize
  node->SetSize(0);
  TESTING_OUTPUT_ASSERT_ERRORS_END();
  CHECK_INT(static_cast<int>(node->GetRows()), 4); // unchanged
  CHECK_INT(static_cast<int>(node->GetCols()), 4);
  CHECK_INT(static_cast<int>(node->GetMTime()), static_cast<int>(preReject));

  // SetRows / SetCols also enforce square-only.  From 4×4, calling
  // SetRows(3) attempts a non-square (3, 4) state — rejected.
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  node->SetRows(3);
  node->SetCols(3);
  TESTING_OUTPUT_ASSERT_ERRORS_END();
  CHECK_INT(static_cast<int>(node->GetRows()), 4);
  CHECK_INT(static_cast<int>(node->GetCols()), 4);

  // Out-of-range values on SetRows / SetCols rejected.
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  node->SetRows(5);
  node->SetCols(2);
  TESTING_OUTPUT_ASSERT_ERRORS_END();
  CHECK_INT(static_cast<int>(node->GetRows()), 4);
  CHECK_INT(static_cast<int>(node->GetCols()), 4);

  // Defaults / range constants exposed for callers.
  CHECK_INT(vtkMRMLBezierSurfaceNode::DefaultGridSize, 4);
  CHECK_INT(vtkMRMLBezierSurfaceNode::MinGridSize, 3);
  CHECK_INT(vtkMRMLBezierSurfaceNode::MaxGridSize, 4);
  CHECK_INT(vtkMRMLBezierSurfaceNode::MaxControlGridSize, 48);
  // Back-compat alias for the v1 4×4 case.
  CHECK_INT(vtkMRMLBezierSurfaceNode::GridSize, 4);
  CHECK_INT(vtkMRMLBezierSurfaceNode::ControlGridSize, 48);
  return EXIT_SUCCESS;
}

int testCopyContent3x3()
{
  // CopyContent must propagate Rows / Cols + the resized control
  // grid in one shot — the post-ADR-0018 sibling of testCopyContent
  // for the 3×3 case.  Defensive: a future drift that copies the
  // buffer without first matching the shape would silently truncate
  // or pad.
  vtkNew<vtkMRMLBezierSurfaceNode> source;
  source->SetSize(3);
  double grid33[27];
  for (int i = 0; i < 27; ++i)
  {
    grid33[i] = static_cast<double>(i) * 0.5 + 0.125;
  }
  source->SetState(vtkMRMLBezierSurfaceNode::Planning);
  source->SetControlGrid(grid33);

  vtkNew<vtkMRMLBezierSurfaceNode> sink;
  sink->CopyContent(source.GetPointer(), /*deepCopy=*/true);

  CHECK_INT(static_cast<int>(sink->GetRows()), 3);
  CHECK_INT(static_cast<int>(sink->GetCols()), 3);
  CHECK_INT(static_cast<int>(sink->GetControlGridLength()), 27);
  for (int i = 0; i < 27; ++i)
  {
    CHECK_DOUBLE(sink->GetControlGrid()[i], grid33[i]);
  }
  CHECK_INT(sink->GetState(), vtkMRMLBezierSurfaceNode::Planning);
  return EXIT_SUCCESS;
}

int testCopyContentResizesAcrossShapes()
{
  // ADR-0018 §1 — CopyContent into a sink whose current shape differs
  // from the source must resize the sink before copying the buffer.
  // Sibling of ``testCopyContent3x3``, which only covers the
  // (fresh-sink, 3×3-source) case.  The harder branch — 4×4 sink
  // adopts a 3×3 source — exercises the resize-on-copy path that a
  // naïve buffer-only Copy would silently truncate.
  {
    vtkNew<vtkMRMLBezierSurfaceNode> source;
    source->SetSize(3);
    source->SetState(vtkMRMLBezierSurfaceNode::Planning);
    double grid33[27];
    for (int i = 0; i < 27; ++i)
    {
      grid33[i] = static_cast<double>(i) * 0.5 + 0.0625;
    }
    source->SetControlGrid(grid33);

    vtkNew<vtkMRMLBezierSurfaceNode> sink;
    sink->SetSize(4); // sink starts at 4×4, 48 zeros
    CHECK_INT(static_cast<int>(sink->GetRows()), 4);
    CHECK_INT(static_cast<int>(sink->GetCols()), 4);

    sink->CopyContent(source.GetPointer(), /*deepCopy=*/true);

    CHECK_INT(static_cast<int>(sink->GetRows()), 3);
    CHECK_INT(static_cast<int>(sink->GetCols()), 3);
    CHECK_INT(static_cast<int>(sink->GetControlGridLength()), 27);
    for (int i = 0; i < 27; ++i)
    {
      CHECK_DOUBLE(sink->GetControlGrid()[i], grid33[i]);
    }
  }

  // Inverse: 3×3 sink adopts a 4×4 source — buffer must grow from
  // 27 to 48 and the source values land in their entirety.
  {
    vtkNew<vtkMRMLBezierSurfaceNode> source;
    // Default is 4×4 — populate the full 48-double grid.
    source->SetState(vtkMRMLBezierSurfaceNode::Planning);
    double grid44[48];
    for (int i = 0; i < 48; ++i)
    {
      grid44[i] = static_cast<double>(i) * -0.25 + 1.0;
    }
    source->SetControlGrid(grid44);

    vtkNew<vtkMRMLBezierSurfaceNode> sink;
    sink->SetSize(3); // sink starts at 3×3, 27 zeros
    CHECK_INT(static_cast<int>(sink->GetRows()), 3);
    CHECK_INT(static_cast<int>(sink->GetCols()), 3);

    sink->CopyContent(source.GetPointer(), /*deepCopy=*/true);

    CHECK_INT(static_cast<int>(sink->GetRows()), 4);
    CHECK_INT(static_cast<int>(sink->GetCols()), 4);
    CHECK_INT(static_cast<int>(sink->GetControlGridLength()), 48);
    for (int i = 0; i < 48; ++i)
    {
      CHECK_DOUBLE(sink->GetControlGrid()[i], grid44[i]);
    }
  }
  return EXIT_SUCCESS;
}

/// Minimal observer used by ``testSizeSettersFireModifiedOnce`` —
/// counts ``vtkCommand::ModifiedEvent`` invocations so the test can
/// pin "exactly one Modified() per accepted setter call + zero per
/// rejected setter call".
class ModifiedCounter
{
public:
  static void Callback(vtkObject*, unsigned long, void* clientData, void*) { static_cast<ModifiedCounter*>(clientData)->Count++; }
  int Count = 0;
  void Reset() { this->Count = 0; }
};

int testSizeSettersFireModifiedOnce()
{
  // ADR-0018 §1 — every accepted shape mutation fires ``Modified()``
  // exactly once, and every rejected one fires zero times.  This is
  // the invariant a future setter rewrite (e.g. split into resize +
  // ivar set) could trip without the existing MTime-advance tests
  // catching it.  The MTime non-regression test pins "MTime advanced"
  // — which is also true for a double-fire — but downstream observers
  // counting Modified events would see twice the work.
  vtkNew<vtkMRMLBezierSurfaceNode> node;

  ModifiedCounter counter;
  vtkNew<vtkCallbackCommand> cb;
  cb->SetCallback(&ModifiedCounter::Callback);
  cb->SetClientData(&counter);
  const unsigned long tag = node->AddObserver(vtkCommand::ModifiedEvent, cb.GetPointer());

  // Default is 4×4; SetSize(3) is a real shape change → exactly one
  // Modified.
  counter.Reset();
  node->SetSize(3);
  CHECK_INT(counter.Count, 1);

  // No-op self-assign → zero Modified.
  counter.Reset();
  node->SetSize(3);
  CHECK_INT(counter.Count, 0);

  // Bump back up to 4×4 → exactly one Modified.
  counter.Reset();
  node->SetSize(4);
  CHECK_INT(counter.Count, 1);

  // Rejection paths — out-of-range SetSize values and non-square
  // SetRows / SetCols attempts must not fire Modified.  The rejection
  // emits a ``vtkErrorMacro`` — gate the assertion around the
  // ASSERT_ERRORS counter so the test driver doesn't count those as
  // a failure (and so a future silent-drop regression — error gone —
  // also surfaces here).
  counter.Reset();
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  node->SetSize(5); // above MaxGridSize
  node->SetSize(2); // below MinGridSize
  node->SetRows(3); // non-square attempt: (3, 4)
  node->SetCols(3); // non-square attempt: (4, 3)
  TESTING_OUTPUT_ASSERT_ERRORS_END();
  CHECK_INT(counter.Count, 0);
  CHECK_INT(static_cast<int>(node->GetRows()), 4); // unchanged
  CHECK_INT(static_cast<int>(node->GetCols()), 4);

  node->RemoveObserver(tag);
  return EXIT_SUCCESS;
}

int testXMLRoundTrip3x3()
{
  // ADR-0018 §1 — Rows / Cols round-trip through XML attributes,
  // controlGrid serialises ``3 * Rows * Cols`` doubles.  Mirrors
  // testXMLRoundTrip for the 3×3 case.  Also exercises the v1
  // migration: a serialised attribute stream that omits ``rows`` /
  // ``cols`` defaults to 4×4 on parse.
  vtkNew<vtkMRMLBezierSurfaceNode> source;
  vtkNew<vtkMRMLScene> scene;
  source->SetScene(scene.GetPointer());
  source->SetSize(3);
  source->SetState(vtkMRMLBezierSurfaceNode::Planning);
  double grid33[27];
  for (int i = 0; i < 27; ++i)
  {
    grid33[i] = static_cast<double>(i) * 0.1 - 1.0;
  }
  source->SetControlGrid(grid33);

  std::ostringstream out;
  source->WriteXML(out, 0);
  const std::string xml = out.str();

  // The XML should explicitly carry the rows + cols + controlGrid.
  if (xml.find("rows=\"3\"") == std::string::npos)
  {
    std::cerr << "Expected rows=\"3\" in WriteXML output: " << xml << "\n";
    return EXIT_FAILURE;
  }
  if (xml.find("cols=\"3\"") == std::string::npos)
  {
    std::cerr << "Expected cols=\"3\" in WriteXML output: " << xml << "\n";
    return EXIT_FAILURE;
  }

  // Re-parse via the simple attribute-list walker (same as
  // testXMLRoundTrip — see that test for the parser comment).
  std::vector<std::string> storage;
  std::size_t pos = 0;
  while (pos < xml.size())
  {
    while (pos < xml.size() && std::isspace(xml[pos]))
    {
      ++pos;
    }
    if (pos >= xml.size())
    {
      break;
    }
    const std::size_t eq = xml.find('=', pos);
    if (eq == std::string::npos)
    {
      break;
    }
    std::string name = xml.substr(pos, eq - pos);
    if (eq + 1 >= xml.size() || xml[eq + 1] != '"')
    {
      break;
    }
    const std::size_t valStart = eq + 2;
    const std::size_t valEnd = xml.find('"', valStart);
    if (valEnd == std::string::npos)
    {
      break;
    }
    std::string value = xml.substr(valStart, valEnd - valStart);
    storage.push_back(name);
    storage.push_back(value);
    pos = valEnd + 1;
  }
  std::vector<const char*> atts;
  for (const auto& s : storage)
  {
    atts.push_back(s.c_str());
  }
  atts.push_back(nullptr);

  vtkNew<vtkMRMLBezierSurfaceNode> sink;
  sink->SetScene(scene.GetPointer());
  sink->ReadXMLAttributes(atts.data());

  CHECK_INT(static_cast<int>(sink->GetRows()), 3);
  CHECK_INT(static_cast<int>(sink->GetCols()), 3);
  CHECK_INT(static_cast<int>(sink->GetControlGridLength()), 27);
  for (int i = 0; i < 27; ++i)
  {
    CHECK_DOUBLE_TOLERANCE(sink->GetControlGrid()[i], grid33[i], 1e-5);
  }

  // Legacy-XML migration: synthesise an attribute stream with no
  // ``rows`` / ``cols`` (the pre-ADR-0018 baseline) + a 48-double
  // controlGrid; the node defaults to 4×4.
  std::string legacyXml = " state=\"Planning\" initMode=\"SlicingPlane\" controlGrid=\"";
  std::ostringstream gridSs;
  for (int i = 0; i < 48; ++i)
  {
    if (i > 0)
    {
      gridSs << " ";
    }
    gridSs << (static_cast<double>(i) * 0.01);
  }
  legacyXml += gridSs.str();
  legacyXml += "\"";

  std::vector<std::string> legacyStorage;
  std::size_t lpos = 0;
  while (lpos < legacyXml.size())
  {
    while (lpos < legacyXml.size() && std::isspace(legacyXml[lpos]))
    {
      ++lpos;
    }
    if (lpos >= legacyXml.size())
    {
      break;
    }
    const std::size_t eq = legacyXml.find('=', lpos);
    if (eq == std::string::npos)
    {
      break;
    }
    std::string name = legacyXml.substr(lpos, eq - lpos);
    if (eq + 1 >= legacyXml.size() || legacyXml[eq + 1] != '"')
    {
      break;
    }
    const std::size_t valStart = eq + 2;
    const std::size_t valEnd = legacyXml.find('"', valStart);
    std::string value = legacyXml.substr(valStart, valEnd - valStart);
    legacyStorage.push_back(name);
    legacyStorage.push_back(value);
    lpos = valEnd + 1;
  }
  std::vector<const char*> legacyAtts;
  for (const auto& s : legacyStorage)
  {
    legacyAtts.push_back(s.c_str());
  }
  legacyAtts.push_back(nullptr);

  vtkNew<vtkMRMLBezierSurfaceNode> legacySink;
  legacySink->SetScene(scene.GetPointer());
  legacySink->ReadXMLAttributes(legacyAtts.data());
  CHECK_INT(static_cast<int>(legacySink->GetRows()), 4);
  CHECK_INT(static_cast<int>(legacySink->GetCols()), 4);
  CHECK_DOUBLE_TOLERANCE(legacySink->GetControlGrid()[0], 0.0, 1e-5);
  CHECK_DOUBLE_TOLERANCE(legacySink->GetControlGrid()[47], 0.47, 1e-5);
  return EXIT_SUCCESS;
}

// ----------------------------------------------------------------------------
// testReadXMLNullMidStream
//
// Pins the corrected behaviour of ``ReadXMLAttributes`` when an
// ``atts[]`` array carries a ``nullptr`` value mid-stream.  Both walks
// (rows/cols extraction and the free-form payload pass) have independent
// ``value == nullptr`` guards that now ``continue;`` past the gap rather
// than aborting the walk.  The MRML scene-load path can legitimately
// produce (non-null name, null value) pairs for unset / placeholder
// attributes; the libxml2 outer-loop sentinel is the null *name* slot,
// not the null value slot.  A walk-abort on the value slot would
// silently drop every downstream attribute and violate ADR-0014 §1
// (data-shape contract: a well-formed scene must round-trip).
//
// Historical context: the commit preceding this one pinned the broken
// ``break;``-on-null state (assertions captured the post-default
// fallback values) per the red-then-green test discipline in
// ADR-0008 §7.  The companion BUG commit flips both walks to
// ``continue;`` and these assertions to the corrected values, making
// the fix visible as a test diff.
int testReadXMLNullMidStream()
{
  // The ``ReadXMLAttributes`` walks iterate with the outer condition
  // ``att && *att`` (i.e. terminate when the *name* slot is null —
  // that is the libxml2 sentinel).  The mid-stream-null trigger fires
  // on the *value* slot: a (non-null name, null value) pair must be
  // skipped without aborting the walk so downstream attributes remain
  // observable.  The trigger pattern is therefore
  // ``{"someName", nullptr, "rows", "3", nullptr}`` — name is
  // non-null, value is null, and a valid attribute follows.

  // ---- Walk-1: rows/cols extraction ----
  //
  // Constructor default for ``Cols`` is ``DefaultGridSize == 4``.  We
  // place a (non-null name, null value) pair *before* the ``cols``
  // attribute.  Under the corrected ``continue;`` walk-1 consumes
  // both ``rows="3"`` and ``cols="3"``; the (3, 3) pair passes the
  // ADR-0018 §1 square-shape check and is accepted as-is, so no
  // warning is emitted.
  vtkNew<vtkMRMLBezierSurfaceNode> sinkA;
  const char* attsA[] = { "rows", "3", "placeholder", nullptr, // mid-stream (non-null name, null value) — skipped via ``continue;``
                          "cols", "3",                         // consumed under the corrected walk
                          nullptr };
  sinkA->ReadXMLAttributes(attsA);
  // Corrected-state assertion: walk-1 skipped the null pair and
  // consumed ``cols="3"``; the (3, 3) pair satisfies ADR-0018 §1's
  // closed shape set and ``GetCols()`` reports 3.
  CHECK_INT(static_cast<int>(sinkA->GetCols()), 3);

  // ---- Walk-2: free-form payload ----
  //
  // Same (non-null name, null value) pattern, but placed before
  // ``slicingPlaneInitPoint0``.  Constructor default for
  // ``SlicingPlaneInitPoints[0]`` is ``{0.0, 0.0, 0.0}``.  Under the
  // corrected walk-2 ``continue;`` the init point is read from the
  // post-null attribute.
  vtkNew<vtkMRMLBezierSurfaceNode> sinkB;
  // Build a well-formed 48-double controlGrid payload so the
  // truncated-controlGrid branch does not muddy the assertion —
  // this isolates the mid-stream-null skip as the sole determinant
  // of whether ``slicingPlaneInitPoint0`` is observed post-parse.
  std::ostringstream gridSs;
  for (int i = 0; i < vtkMRMLBezierSurfaceNode::ControlGridSize; ++i)
  {
    if (i > 0)
    {
      gridSs << " ";
    }
    gridSs << "0.0";
  }
  const std::string gridStr = gridSs.str();
  const std::string initPt = "1.0 2.0 3.0";
  const char* attsB[] = { "controlGrid",
                          gridStr.c_str(),
                          "placeholder",
                          nullptr, // mid-stream (non-null name, null value) — skipped via ``continue;``
                          "slicingPlaneInitPoint0",
                          initPt.c_str(), // consumed under the corrected walk
                          nullptr };
  sinkB->ReadXMLAttributes(attsB);
  // Corrected-state assertion: walk-2 skipped the null pair and
  // consumed ``slicingPlaneInitPoint0="1.0 2.0 3.0"``.
  const double* pt = sinkB->GetSlicingPlaneInitPoint(0);
  CHECK_NOT_NULL(pt);
  CHECK_DOUBLE(pt[0], 1.0);
  CHECK_DOUBLE(pt[1], 2.0);
  CHECK_DOUBLE(pt[2], 3.0);
  return EXIT_SUCCESS;
}

// ----------------------------------------------------------------------------
// testCopyCarriesDisplayNodeRef
//
// Pins the existing correct behaviour: after the data-node reparent to
// ``vtkMRMLDisplayableNode`` (ADR-0013 §8 — display-node-reference role
// belongs on the data side of the Pipeline split), the high-level
// ``vtkMRMLNode::Copy`` carries the display-node-reference role from
// source to sink.  Two layers:
//
//   1. Scene-less: the reference *string* survives (no scene-side
//      resolution involved — this isolates the CopyReferences half
//      of Copy()).
//   2. With scene: the reference resolves to a real
//      ``vtkMRMLBezierSurfaceDisplayNode`` of the right class — the
//      end-to-end structural guarantee.
//
// Implementation note: ``CopyContent`` alone does NOT copy node
// references — its inherited body in ``vtkMRMLNode::CopyContent``
// copies Description / Selectable / Attributes only.  References are
// copied by ``vtkMRMLNode::CopyReferences``, which ``Copy()`` calls
// alongside ``CopyContent()``.  An earlier draft of this sub-test
// asserted the role survived ``CopyContent`` directly; CI surfaced
// the assertion as broken and Slicer's ``vtkMRMLNode.cxx`` confirms
// the layering.  The Copy() path is the one users actually invoke
// when copying a node (scenes use it via vtkMRMLScene::CopyNode),
// so it is the right invariant to pin here.
//
// Companion to ``testDisplayNodeAttachedSceneRoundTrip`` (which pins
// the XML round-trip path); this sub-test pins the in-memory Copy
// path.
int testCopyCarriesDisplayNodeRef()
{
  // ---- Layer 1: Scene-less reference-string survival ----
  {
    vtkNew<vtkMRMLBezierSurfaceNode> source;
    vtkNew<vtkMRMLBezierSurfaceNode> sink;
    // Add a literal display-node-ID string; no scene means the role
    // engine cannot resolve it to a real node, but the *role string*
    // is what we want to assert survives the copy.
    const char* displayId = "vtkMRMLBezierSurfaceDisplayNode1";
    source->AddAndObserveDisplayNodeID(displayId);
    sink->Copy(source.GetPointer());
    const char* sinkId = sink->GetNthDisplayNodeID(0);
    CHECK_NOT_NULL(sinkId);
    CHECK_STRING(sinkId, displayId);
  }

  // ---- Layer 2: With-scene resolution ----
  {
    vtkNew<vtkMRMLScene> scene;
    scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLBezierSurfaceNode>::New());
    scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLBezierSurfaceDisplayNode>::New());

    vtkNew<vtkMRMLBezierSurfaceNode> source;
    vtkNew<vtkMRMLBezierSurfaceNode> sink;
    vtkNew<vtkMRMLBezierSurfaceDisplayNode> display;
    scene->AddNode(source.GetPointer());
    scene->AddNode(sink.GetPointer());
    scene->AddNode(display.GetPointer());
    source->AddAndObserveDisplayNodeID(display->GetID());

    sink->Copy(source.GetPointer());

    // The reference must resolve scene-side to the same display node
    // (or at least a node of the right class — Pipeline-pattern
    // structural invariant per ADR-0013 §8).
    vtkMRMLNode* resolved = sink->GetNthDisplayNode(0);
    CHECK_NOT_NULL(resolved);
    vtkMRMLBezierSurfaceDisplayNode* typed = vtkMRMLBezierSurfaceDisplayNode::SafeDownCast(resolved);
    CHECK_NOT_NULL(typed);
  }
  return EXIT_SUCCESS;
}

// ----------------------------------------------------------------------------
// testReadXMLTruncatedControlGridWarns
//
// Pins the existing correct behaviour of the truncated-``controlGrid``
// branch in ``ReadXMLAttributes``: when the attribute payload carries
// fewer than ``3 * Rows * Cols`` doubles, ``vtkMRMLBezierSurfaceNode``
// emits a ``vtkWarningMacro`` and leaves the control grid at its
// default-initialised values (zero-filled by the constructor) rather
// than copying a partial buffer.  Pinned at
// vtkMRMLBezierSurfaceNode.cxx:701-710.  The shape of the warning
// mirrors ``vtkMRMLPlotSeriesNode``'s truncated-array handling — see
// the ADR-0014 §1 data-shape contract.
int testReadXMLTruncatedControlGridWarns()
{
  vtkNew<vtkMRMLBezierSurfaceNode> sink;
  // 10 doubles < 48 expected (3 * 4 * 4); the reader must warn and
  // leave the grid alone.
  const char* atts[] = { "rows", "4", "cols", "4", "controlGrid", "0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 1.0", nullptr };
  TESTING_OUTPUT_ASSERT_WARNINGS_BEGIN();
  sink->ReadXMLAttributes(atts);
  TESTING_OUTPUT_ASSERT_WARNINGS_END();

  // Per the constructor (vtkMRMLBezierSurfaceNode.cxx:108) the
  // default-init ControlGrid is 48 zero-doubles.  A truncated payload
  // must not overwrite any slot.
  CHECK_INT(static_cast<int>(sink->GetRows()), 4);
  CHECK_INT(static_cast<int>(sink->GetCols()), 4);
  CHECK_INT(static_cast<int>(sink->GetControlGridLength()), vtkMRMLBezierSurfaceNode::ControlGridSize);
  const double* grid = sink->GetControlGrid();
  for (int i = 0; i < vtkMRMLBezierSurfaceNode::ControlGridSize; ++i)
  {
    CHECK_DOUBLE(grid[i], 0.0);
  }
  return EXIT_SUCCESS;
}

} // namespace

//------------------------------------------------------------------------------
int vtkMRMLBezierSurfaceNodeTest1(int, char*[])
{
  // Exercise the base-class MRML methods (constructor, getters/setters,
  // Copy, scene registration round-trip).  This catches missing
  // CreateNodeInstance / vtkStandardNewMacro plumbing.
  vtkNew<vtkMRMLScene> scene;
  vtkNew<vtkMRMLBezierSurfaceNode> exerciseNode;
  exerciseNode->SetScene(scene.GetPointer());
  EXERCISE_ALL_BASIC_MRML_METHODS(exerciseNode.GetPointer());

  CHECK_EXIT_SUCCESS(testDefaults());
  CHECK_EXIT_SUCCESS(testEnumRoundTrip());
  CHECK_EXIT_SUCCESS(testControlGridRoundTrip());
  CHECK_EXIT_SUCCESS(testSlicingPlaneInit());
  CHECK_EXIT_SUCCESS(testDistanceSpheroidInit());
  CHECK_EXIT_SUCCESS(testXMLRoundTrip());
  CHECK_EXIT_SUCCESS(testCopyContent());
  CHECK_EXIT_SUCCESS(testModifiedEventsOnSetters());
  CHECK_EXIT_SUCCESS(testDisplayNodeAttachedSceneRoundTrip());
  CHECK_EXIT_SUCCESS(testInitDataReadOnlyAfterPlanning());
  CHECK_EXIT_SUCCESS(testConfirmedStateTransitions());
  CHECK_EXIT_SUCCESS(testVariableSizeControlPolygon());
  CHECK_EXIT_SUCCESS(testCopyContent3x3());
  CHECK_EXIT_SUCCESS(testCopyContentResizesAcrossShapes());
  CHECK_EXIT_SUCCESS(testSizeSettersFireModifiedOnce());
  CHECK_EXIT_SUCCESS(testXMLRoundTrip3x3());
  CHECK_EXIT_SUCCESS(testReadXMLNullMidStream());
  CHECK_EXIT_SUCCESS(testCopyCarriesDisplayNodeRef());
  CHECK_EXIT_SUCCESS(testReadXMLTruncatedControlGridWarns());

  std::cout << "vtkMRMLBezierSurfaceNodeTest1 completed successfully" << std::endl;
  return EXIT_SUCCESS;
}

/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

==============================================================================*/

/**
 * \file vtkMRMLAbstractParametricSurfaceNodeTest1.cxx
 *
 * Test-first scaffolding for the parametric-surface class hierarchy
 * introduced by the 2026-05-25 wrapper-vs-carrier amendment to
 * ADR-0014 (§"Fourth layer: clinical/method wrapper") and ADR-0023
 * (§"Class abstraction for surfaces").  Lands per ADR-0027 (test
 * commit predates implementation).
 *
 * Each test pins one architectural invariant.  Test cases that
 * exercise not-yet-implemented behaviour fail red against the current
 * tree (the abstract base + the carrier-base reparent of
 * ``vtkMRMLBezierSurfaceNode`` have not landed yet); the follow-up
 * implementer commit flips them green.
 *
 * Invariants pinned (each cites its source amendment / design-doc
 * anchor):
 *
 *   1. Abstract base non-instantiable per vtkAbstractTypeMacro.
 *      Compile-time abstractness is the strong guarantee; the runtime
 *      sub-test pins the polymorphic complement -- a concrete
 *      ``vtkMRMLBezierSurfaceNode::New()`` SafeDownCasts to the
 *      abstract base.  Pattern mirrors
 *      vtkMRMLAbstractTerritoriesNodeTest1.cxx invariant 1.
 *      (ADR-0023 amendment §"Class abstraction for surfaces"; design
 *      doc 01-class-hierarchy.md §"Key invariants" bullet 3.)
 *   2. ``CreateDefaultStorageNode()`` returns nullptr on the abstract
 *      base AND on the concrete Bezier subclass -- the surface is
 *      non-storable, persistence flows through the wrapping
 *      ``vtkMRMLResectionPlanNode``'s storage node.
 *      (ADR-0023 amendment §"Decision -- surface-side data
 *      ownership"; design doc 03-storage-ownership.md §"Why surface
 *      is non-storable".)
 *   3. Polymorphic dispatch: ``GetSurfaceType()`` returns the
 *      concrete VTK class name ("Bezier") via base pointer.  v2.1
 *      NURBS sibling will pin "NURBS" via the same dispatch point
 *      (no test authored here -- the sibling class does not exist
 *      yet, see "Out of scope" in this test file's invariant list).
 *      (ADR-0023 amendment §"Class abstraction for surfaces"; design
 *      doc 01-class-hierarchy.md §"Key invariants" + class diagram.)
 *   4. Polymorphic dispatch: ``EvaluateSurface(u, v)`` returns a
 *      non-empty ``vtkPolyData`` via base pointer for the concrete
 *      Bezier subclass.
 *      (ADR-0023 amendment §"Class abstraction for surfaces" -- the
 *      ``+virtual EvaluateSurface(u, v) : vtkPolyData`` entry on the
 *      abstract base.)
 *   5. Shared field roster round-trip through the inheritance chain:
 *      ``Rows``, ``Cols``, ``ControlGrid``, ``InitMode``, plus the
 *      slicing-plane + spheroid subordinates survive ``WriteXML`` +
 *      ``ReadXMLAttributes`` on the concrete Bezier subclass.
 *      Confirms the fields moved up to the abstract base (per the
 *      class diagram) still serialise via the concrete node's
 *      WriteXML chain.
 *      (Design doc 01-class-hierarchy.md class diagram --
 *      ``+unsigned int Rows`` ... ``+InitMode`` block on the abstract
 *      base.)
 *   6. Scene add/remove smoke test for the concrete Bezier subclass
 *      via base-pointer GetNodesByClass filter on the abstract base
 *      class name -- the polymorphic-filter invariant.  Mirrors
 *      vtkMRMLAbstractTerritoriesNodeTest1 invariant 6.
 *      (ADR-0023 amendment §"Class abstraction for surfaces"; design
 *      doc 02-node-references.md §"Multiple plans in scene" -- many
 *      concrete subclasses share the base.)
 *
 * Out of scope for this Test1 (per planner output -- deliverable 1):
 *   - NURBS sibling subclass tests (v2.1 deferred per ADR-0018 §3).
 *   - Plan-side interactions (covered in
 *     vtkMRMLResectionPlanNodeTest1).
 *   - Display-side rename invariants (deliverable 5 -- existing
 *     display tests rewrite in lockstep, no new Test1 authored).
 */

// This module MRML includes -- forward-included so the test driver
// fails red until the implementer lands the new classes.  Per the
// existing test-first convention in
// vtkMRMLAbstractTerritoriesNodeTest1.cxx, these are real includes
// (not forward declarations); the test driver will fail to *compile*
// or *link* against the current tree -- intentional, per
// ADR-0027.
#include "vtkMRMLAbstractParametricSurfaceNode.h"
#include "vtkMRMLBezierSurfaceNode.h"

// MRML includes
#include "vtkMRMLCoreTestingMacros.h"
#include "vtkMRMLScene.h"

// VTK includes
#include <vtkCollection.h>
#include <vtkNew.h>
#include <vtkPolyData.h>
#include <vtkSmartPointer.h>

// STD includes
#include <cctype>
#include <cstring>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

namespace
{

//------------------------------------------------------------------------------
// Naive ``name="value"`` walker mirroring the
// vtkMRMLBezierSurfaceNodeTest1 + vtkMRMLAbstractTerritoriesNodeTest1
// round-trip pattern.  Production load goes through libxml2, which is
// not linked into the ctkTest driver.  Returns the storage vector by
// reference so the c_str() pointers in ``atts`` stay alive for the
// duration of the caller's ReadXMLAttributes call.
std::vector<const char*> buildAttsFromXML(const std::string& xml, std::vector<std::string>& storage)
{
  std::size_t pos = 0;
  while (pos < xml.size())
  {
    while (pos < xml.size() && std::isspace(static_cast<unsigned char>(xml[pos])))
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
    storage.push_back(std::move(name));
    storage.push_back(xml.substr(valStart, valEnd - valStart));
    pos = valEnd + 1;
  }
  std::vector<const char*> atts;
  atts.reserve(storage.size() + 1);
  for (const auto& s : storage)
  {
    atts.push_back(s.c_str());
  }
  atts.push_back(nullptr);
  return atts;
}

//------------------------------------------------------------------------------
// Invariant 1 -- Abstract base is non-instantiable; concrete
// subclasses ARE-A vtkMRMLAbstractParametricSurfaceNode.  Compile-time
// abstractness is enforced by ``vtkAbstractTypeMacro`` on the header
// (any caller that wrote ``vtkMRMLAbstractParametricSurfaceNode::New``
// would fail to compile).  The runtime sub-test pins the complement.
// (ADR-0023 amendment §"Class abstraction for surfaces"; design doc
// 01-class-hierarchy.md §"Key invariants" bullet 3.)
int testAbstractBaseNotInstantiable()
{
  vtkNew<vtkMRMLBezierSurfaceNode> bezier;
  vtkMRMLAbstractParametricSurfaceNode* asBase = vtkMRMLAbstractParametricSurfaceNode::SafeDownCast(bezier.GetPointer());
  CHECK_NOT_NULL(asBase);
  CHECK_BOOL(bezier->IsA("vtkMRMLAbstractParametricSurfaceNode"), true);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 2 -- The surface is non-storable.  Both the abstract base
// (reachable via SafeDownCast) and the concrete Bezier subclass
// return nullptr from ``CreateDefaultStorageNode()``.  Surface bulk
// data persists through the wrapping ``vtkMRMLResectionPlanStorageNode``
// per the wrapper-vs-carrier pattern.
// (ADR-0023 amendment §"Decision -- surface-side data ownership";
// ADR-0014 amendment 2026-05-25 §"Consequences that supersede
// Decision 1 + 5" bullet 2; design doc 03-storage-ownership.md §"Why
// surface is non-storable".)
int testSurfaceIsNonStorable()
{
  vtkNew<vtkMRMLBezierSurfaceNode> bezier;
  vtkSmartPointer<vtkMRMLStorageNode> defaultStorage = vtkSmartPointer<vtkMRMLStorageNode>::Take(bezier->CreateDefaultStorageNode());
  CHECK_NULL(defaultStorage.GetPointer());

  // Reach the same method via the abstract-base pointer to pin the
  // polymorphic side -- a caller iterating
  // ``GetNodesByClass("vtkMRMLAbstractParametricSurfaceNode")`` and
  // calling ``CreateDefaultStorageNode`` should observe nullptr too.
  vtkMRMLAbstractParametricSurfaceNode* asBase = vtkMRMLAbstractParametricSurfaceNode::SafeDownCast(bezier.GetPointer());
  CHECK_NOT_NULL(asBase);
  vtkSmartPointer<vtkMRMLStorageNode> defaultStorageViaBase = vtkSmartPointer<vtkMRMLStorageNode>::Take(asBase->CreateDefaultStorageNode());
  CHECK_NULL(defaultStorageViaBase.GetPointer());
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 3 -- Polymorphic ``GetSurfaceType()`` dispatch through
// the abstract base pointer.  Consumers (the plan-storage writer,
// the resection-table label) rely on this -- no dynamic_cast
// branching.  The Bezier subclass returns "Bezier"; the v2.1 NURBS
// sibling will return "NURBS" (not tested here -- class does not
// exist yet, see "Out of scope" in the file header).
// (ADR-0023 amendment §"Class abstraction for surfaces" --
// ``+virtual GetSurfaceType() : string`` on the abstract base; design
// doc 05-lrp-json-schema.md §"surface.type" discriminator.)
int testPolymorphicSurfaceTypeDispatch()
{
  vtkNew<vtkMRMLBezierSurfaceNode> bezier;
  vtkMRMLAbstractParametricSurfaceNode* basePtr = bezier.GetPointer();
  CHECK_NOT_NULL(basePtr);
  CHECK_STRING(basePtr->GetSurfaceType(), "Bezier");
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 4 -- Polymorphic ``EvaluateSurface(u, v)`` dispatch
// through the abstract base pointer.  The abstract method exists on
// the base; the Bezier subclass evaluates the polynomial; the v2.1
// NURBS sibling will evaluate the rational spline.  Pin: the call
// via base pointer returns a non-empty ``vtkPolyData`` (non-null,
// non-zero point count).  Exact geometry is not part of the
// invariant -- only that the dispatch is wired up and the output is
// substantive.
// (ADR-0023 amendment §"Class abstraction for surfaces" --
// ``+virtual EvaluateSurface(u, v) : vtkPolyData`` on the abstract
// base.)
int testPolymorphicEvaluateSurface()
{
  vtkNew<vtkMRMLBezierSurfaceNode> bezier;
  // Populate a non-trivial control grid so the evaluator has something
  // to sample.  Sample a 4x4 default; the abstract base's
  // ``ControlGrid`` field carries the data once the implementer lands
  // the field-move-up.
  double grid[vtkMRMLBezierSurfaceNode::ControlGridSize];
  for (int i = 0; i < vtkMRMLBezierSurfaceNode::ControlGridSize; ++i)
  {
    grid[i] = static_cast<double>(i) * 0.125;
  }
  bezier->SetControlGrid(grid);

  vtkMRMLAbstractParametricSurfaceNode* basePtr = bezier.GetPointer();
  CHECK_NOT_NULL(basePtr);
  vtkSmartPointer<vtkPolyData> evaluated = vtkSmartPointer<vtkPolyData>::Take(basePtr->EvaluateSurface(0.5, 0.5));
  CHECK_NOT_NULL(evaluated.GetPointer());
  // Non-empty: at least one point comes back.  The exact sample
  // count is left to the implementer -- the invariant is "dispatch
  // produces substantive output", not "the sampler emits N points".
  if (evaluated->GetNumberOfPoints() == 0)
  {
    std::cerr << "EvaluateSurface(0.5, 0.5) returned an empty vtkPolyData\n";
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 5 -- Shared field roster round-trips through the
// inheritance chain.  The fields ``Rows``, ``Cols``, ``ControlGrid``,
// ``InitMode``, and the slicing-plane / spheroid subordinates have
// moved UP to the abstract base per the design's class diagram.  The
// concrete Bezier subclass's WriteXML / ReadXMLAttributes chain
// (through Superclass) must still serialise the full set.  The
// invariant is "no field drops out when the field-move-up lands".
//
// Verifies the round-trip via the same name="value" walker the other
// MRML tests use.  Doubles tolerance: 1e-9 (matches storage-node
// tests).
// (Design doc 01-class-hierarchy.md class diagram --
// ``vtkMRMLAbstractParametricSurfaceNode`` field roster; ADR-0014
// amendment 2026-05-25 §"Consequences" -- surface keeps geometry +
// state.)
int testSharedFieldRosterXMLRoundTrip()
{
  vtkNew<vtkMRMLScene> scene;
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLBezierSurfaceNode>::New());

  vtkNew<vtkMRMLBezierSurfaceNode> source;
  source->SetScene(scene.GetPointer());
  source->SetInitMode(vtkMRMLBezierSurfaceNode::DistanceSpheroid);

  // Populate a structured grid so any layout / serialisation bug
  // shows up.
  double grid[vtkMRMLBezierSurfaceNode::ControlGridSize];
  for (int i = 0; i < vtkMRMLBezierSurfaceNode::ControlGridSize; ++i)
  {
    grid[i] = static_cast<double>(i) * 0.25 + 0.125;
  }
  source->SetControlGrid(grid);

  // SlicingPlane subordinate.
  double origin[3] = { 1.0, 2.0, 3.0 };
  source->SetSlicingPlaneOrigin(origin);
  double normal[3] = { 0.0, 1.0, 0.0 };
  source->SetSlicingPlaneNormal(normal);

  // DistanceSpheroid subordinate.
  source->SetNumberOfDistanceSpheroidInitPoints(2);
  double center[3] = { 11.0, 12.0, 13.0 };
  source->SetDistanceSpheroidCenter(center);
  source->SetDistanceSpheroidRadiusX(2.5);
  source->SetDistanceSpheroidRadiusY(3.5);
  source->SetDistanceSpheroidRadiusZ(4.5);

  std::ostringstream out;
  source->WriteXML(out, 0);
  const std::string xml = out.str();

  vtkNew<vtkMRMLBezierSurfaceNode> sink;
  sink->SetScene(scene.GetPointer());
  std::vector<std::string> storage;
  std::vector<const char*> atts = buildAttsFromXML(xml, storage);
  sink->ReadXMLAttributes(atts.data());

  // Shape fields -- new on the abstract base.
  CHECK_INT(static_cast<int>(sink->GetRows()), static_cast<int>(source->GetRows()));
  CHECK_INT(static_cast<int>(sink->GetCols()), static_cast<int>(source->GetCols()));

  // InitMode round-trip.
  CHECK_INT(sink->GetInitMode(), source->GetInitMode());

  // SlicingPlane subordinate round-trip.
  double a3[3], b3[3];
  sink->GetSlicingPlaneOrigin(a3);
  source->GetSlicingPlaneOrigin(b3);
  for (int j = 0; j < 3; ++j)
  {
    CHECK_DOUBLE_TOLERANCE(a3[j], b3[j], 1e-9);
  }
  sink->GetSlicingPlaneNormal(a3);
  source->GetSlicingPlaneNormal(b3);
  for (int j = 0; j < 3; ++j)
  {
    CHECK_DOUBLE_TOLERANCE(a3[j], b3[j], 1e-9);
  }

  // DistanceSpheroid subordinate round-trip.
  CHECK_INT(sink->GetNumberOfDistanceSpheroidInitPoints(), source->GetNumberOfDistanceSpheroidInitPoints());
  sink->GetDistanceSpheroidCenter(a3);
  source->GetDistanceSpheroidCenter(b3);
  for (int j = 0; j < 3; ++j)
  {
    CHECK_DOUBLE_TOLERANCE(a3[j], b3[j], 1e-9);
  }
  CHECK_DOUBLE_TOLERANCE(sink->GetDistanceSpheroidRadiusX(), source->GetDistanceSpheroidRadiusX(), 1e-9);
  CHECK_DOUBLE_TOLERANCE(sink->GetDistanceSpheroidRadiusY(), source->GetDistanceSpheroidRadiusY(), 1e-9);
  CHECK_DOUBLE_TOLERANCE(sink->GetDistanceSpheroidRadiusZ(), source->GetDistanceSpheroidRadiusZ(), 1e-9);

  // ControlGrid -- the heavy field.  XML round-trip is not the
  // canonical persistence path (storage node carries it) but the
  // WriteXML chain still emits it so the .mrml-only round-trip
  // works for scene snapshots taken mid-edit.  Pin a spot-check on
  // a few entries; the storage-node test pins the full grid.
  CHECK_DOUBLE_TOLERANCE(sink->GetControlGrid()[0], source->GetControlGrid()[0], 1e-9);
  CHECK_DOUBLE_TOLERANCE(sink->GetControlGrid()[vtkMRMLBezierSurfaceNode::ControlGridSize - 1], source->GetControlGrid()[vtkMRMLBezierSurfaceNode::ControlGridSize - 1], 1e-9);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 6 -- Polymorphic GetNodesByClass filter on the abstract
// base.  After RegisterNodeClass on the concrete Bezier subclass, a
// scene's ``GetNodesByClass("vtkMRMLAbstractParametricSurfaceNode")``
// returns the Bezier instance.  Mirrors the territories invariant
// (vtkMRMLAbstractTerritoriesNodeTest1 testPolymorphicNodeClassFilter)
// -- consumers (qMRMLNodeComboBox, the plan-storage writer iterating
// surfaces) rely on the IsA traversal returning both Bezier today
// and NURBS in v2.1 from the same base-class query.
// (ADR-0023 amendment §"Class abstraction for surfaces"; design doc
// 01-class-hierarchy.md class diagram showing both leaves derive
// from the abstract base.)
int testPolymorphicNodeClassFilter()
{
  vtkNew<vtkMRMLScene> scene;
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLBezierSurfaceNode>::New());

  vtkNew<vtkMRMLBezierSurfaceNode> bezier;
  scene->AddNode(bezier.GetPointer());

  // Direct subclass query -- one instance.
  vtkSmartPointer<vtkCollection> bezierNodes = vtkSmartPointer<vtkCollection>::Take(scene->GetNodesByClass("vtkMRMLBezierSurfaceNode"));
  CHECK_INT(bezierNodes->GetNumberOfItems(), 1);

  // Base-class query -- one instance matches via IsA traversal.
  // v2.1 NURBS sibling will lift this count to 2 in scenes that
  // carry both.
  vtkSmartPointer<vtkCollection> baseNodes = vtkSmartPointer<vtkCollection>::Take(scene->GetNodesByClass("vtkMRMLAbstractParametricSurfaceNode"));
  CHECK_INT(baseNodes->GetNumberOfItems(), 1);
  return EXIT_SUCCESS;
}

} // namespace

//------------------------------------------------------------------------------
int vtkMRMLAbstractParametricSurfaceNodeTest1(int, char*[])
{
  vtkNew<vtkMRMLScene> scene;
  vtkNew<vtkMRMLBezierSurfaceNode> exerciseNode;
  exerciseNode->SetScene(scene.GetPointer());
  EXERCISE_ALL_BASIC_MRML_METHODS(exerciseNode.GetPointer());

  CHECK_EXIT_SUCCESS(testAbstractBaseNotInstantiable());
  CHECK_EXIT_SUCCESS(testSurfaceIsNonStorable());
  CHECK_EXIT_SUCCESS(testPolymorphicSurfaceTypeDispatch());
  CHECK_EXIT_SUCCESS(testPolymorphicEvaluateSurface());
  CHECK_EXIT_SUCCESS(testSharedFieldRosterXMLRoundTrip());
  CHECK_EXIT_SUCCESS(testPolymorphicNodeClassFilter());

  std::cout << "vtkMRMLAbstractParametricSurfaceNodeTest1 completed successfully" << std::endl;
  return EXIT_SUCCESS;
}

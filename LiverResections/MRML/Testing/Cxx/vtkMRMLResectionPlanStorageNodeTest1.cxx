/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

==============================================================================*/

/**
 * \file vtkMRMLResectionPlanStorageNodeTest1.cxx
 *
 * Test-first scaffolding for the new plan-rooted ``.lrp.json``
 * storage node introduced by the 2026-05-25 wrapper-vs-carrier
 * amendment to ADR-0014 and ADR-0023.  Replaces the retired
 * vtkMRMLBezierSurfaceStorageNodeTest{1,2}.cxx pair (the storage
 * code itself moves wholesale to ``vtkMRMLResectionPlanStorageNode``;
 * the surface becomes non-storable).  Lands per ADR-0027.
 *
 * Each test pins one architectural invariant.  Assertions fail red
 * against the current tree (the storage node does not exist yet);
 * the follow-up implementer commit flips them green.
 *
 * Invariants pinned (each cites its source amendment / design-doc
 * anchor):
 *
 *   1. ``GetDefaultWriteFileExtension()`` returns ``"lrp.json"`` and
 *      ``GetNodeTagName()`` returns ``"ResectionPlanStorage"``.
 *      (Design doc 03-storage-ownership.md §"Plan node" table
 *      "storage" row; design doc 04-save-load-flows.md flows 1+2.)
 *   2. ``CanRead`` / ``CanWrite`` discrimination -- accepts
 *      ``vtkMRMLResectionPlanNode``; rejects everything else
 *      (Bezier surface, model, nullptr).  The surface is no longer
 *      independently storable.
 *      (ADR-0023 amendment §"Decision -- surface-side data
 *      ownership".)
 *   3. Writer emits ``schemaVersion: 2`` (positive assertion + the
 *      negative assertion that ``"schemaVersion": 3`` is NOT in the
 *      output -- the schema folded back to v2 per commit f6014d1
 *      and stays at 2 for the wrapper-vs-carrier landing).
 *      (Design doc 05-lrp-json-schema.md §"Reader / writer behaviour"
 *      -- writer emits the trimmed shape only; schemaVersion = 2.)
 *   4. Schema-version boundary rejection -- the ``[2, 2]`` closed
 *      interval rejects v1 (low), v3 (high), v99 (far).  Both ends
 *      pinned so a regression that widens the band is caught.
 *      (Design doc 05-lrp-json-schema.md §"Reader / writer behaviour"
 *      first bullet: ``schemaVersion < 2 or > 2`` is rejected.)
 *   5. Plan-rooted round-trip: a plan with the full v2 field roster
 *      + a referenced ``vtkMRMLBezierSurfaceNode`` writes, reads
 *      back, and re-writes byte-stable on the plan fields and the
 *      surface block.
 *      (Design doc 04-save-load-flows.md flow 2 -- single-plan save;
 *      design doc 05-lrp-json-schema.md §"Trimmed shape".)
 *   6. ``surface.type`` discriminator: writer emits ``"Bezier"``;
 *      reader instantiates a ``vtkMRMLBezierSurfaceNode`` on
 *      standalone load.
 *      (Design doc 05-lrp-json-schema.md §"surface.type" + §"v2.1
 *      polymorphic extension preview".)
 *   7. Standalone load: opening a ``.lrp.json`` in a fresh scene
 *      produces both a Plan node AND a Surface node, wired through
 *      the typed ``geometry`` reference.
 *      (Design doc 04-save-load-flows.md flow 3.)
 *   8. Optional-fields defaults: a minimal v2 file (plan name +
 *      surface.type + rows/cols/controlGrid only; no margins, no
 *      orderIndex, no state) loads with documented defaults
 *      (margins=0.0, orderIndex=-1, state="Init").
 *      (Design doc 05-lrp-json-schema.md §"Trimmed shape"
 *      sentinel notes; design doc 01-class-hierarchy.md
 *      ``vtkMRMLResectionPlanNode`` defaults.)
 *   9. ``scene.*`` block forward-compatibility: an old fixture
 *      carrying ``scene.classification`` / ``scene.volumetryPartitions``
 *      / ``scene.stageSelection`` loads cleanly (reader silently
 *      ignores unknown fields).  Writer NEVER emits ``scene.*``.
 *      (Design doc 05-lrp-json-schema.md §"Reader / writer
 *      behaviour" second + third bullets; ADR-0023 amendment
 *      §"Persistence -- .lrp.json schema v2" -- "Reader still
 *      admits the old scene.* block silently".)
 *  10. Surface bulk-data survives round-trip: ``controlGrid``
 *      (3*rows*cols doubles), slicing-plane subordinate (origin,
 *      normal, init points), distance-spheroid subordinate (center,
 *      radii, init points) all come back byte-equivalent.
 *      (Design doc 05-lrp-json-schema.md §"Trimmed shape" --
 *      slicingPlane / distanceSpheroid blocks under surface; design
 *      doc 03-storage-ownership.md surface table.)
 *
 * Invariants intentionally carried forward from
 * vtkMRMLBezierSurfaceStorageNodeTest1.cxx (the retired predecessor):
 *   - JSON round-trip (now plan-rooted)
 *   - schemaVersion mismatch rejection
 *   - CanRead / CanWrite discrimination (now plan-typed)
 *
 * Invariants intentionally DROPPED from the predecessor:
 *   - Legacy .lrp.fcsv migration -- out of scope; tracked as a
 *     follow-up to the resection-plan-architecture work.
 *   - The scene.* classification + volumetry + stageSelection
 *     subtests from the predecessor ``vtkMRMLBezierSurfaceStorageNode``
 *     -- obsolete after the content trim (scene.* removed from the
 *     writer; reader silently ignores).  Invariant 9 above replaces
 *     them with a
 *     forward-compat check.
 */

// This module MRML includes -- forward-included so the test driver
// fails red until the implementer lands the new classes.  Per the
// existing test-first convention; the test driver will fail to
// *compile* or *link* against the current tree -- intentional, per
// ADR-0027.
#include "vtkMRMLResectionPlanNode.h"
#include "vtkMRMLResectionPlanStorageNode.h"
#include "vtkMRMLAbstractParametricSurfaceNode.h"
#include "vtkMRMLBezierSurfaceNode.h"

// MRML includes
#include "vtkMRMLCoreTestingMacros.h"
#include "vtkMRMLModelNode.h"
#include "vtkMRMLScene.h"

// VTK includes
#include <vtkCollection.h>
#include <vtkNew.h>
#include <vtkObjectFactory.h>
#include <vtkSmartPointer.h>
#include <vtksys/SystemTools.hxx>

// STD includes
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>

// Portable getpid -- carry-forward from
// vtkMRMLBezierSurfaceStorageNodeTest1.cxx (the retired
// predecessor); same pid + counter scheme avoids cross-test temp-file
// collisions.
#if defined(_WIN32)
# include <process.h>
# define LIVER_PLAN_GETPID _getpid
#else
# include <unistd.h>
# define LIVER_PLAN_GETPID ::getpid
#endif

namespace
{

/// Test-only subclass that exposes the protected ReadDataInternal /
/// WriteDataInternal forwarders so the defensive guard branches inside
/// each (null refNode, wrong-class refNode, empty filename, unsupported
/// extension) can be exercised directly.  The public
/// ``vtkMRMLStorageNode::ReadData`` / ``::WriteData`` paths catch most
/// of these conditions before delegating; coverage of the local guards
/// requires bypassing the base layer.  Closes the codecov gaps the
/// post-impl /slicer-review pass flagged in vtkMRMLResectionPlanStorageNode.cxx
/// lines 107-167.
class ExposedStorageNode : public vtkMRMLResectionPlanStorageNode
{
public:
  static ExposedStorageNode* New();
  vtkTypeMacro(ExposedStorageNode, vtkMRMLResectionPlanStorageNode);
  int CallReadDataInternal(vtkMRMLNode* refNode) { return this->ReadDataInternal(refNode); }
  int CallWriteDataInternal(vtkMRMLNode* refNode) { return this->WriteDataInternal(refNode); }

protected:
  ExposedStorageNode() = default;
  ~ExposedStorageNode() override = default;
};
vtkStandardNewMacro(ExposedStorageNode);

/// Generate a unique temp file path with the given extension.  Rooted
/// under ``LIVER_BEZIER_STORAGE_TEST_TEMP_DIR`` -- the CMake binary
/// tree's ``Testing/Temporary`` directory.  Macro name carried
/// forward from the predecessor test (same CMake plumbing).
std::string makeTempPath(const std::string& extension)
{
  static int counter = 0;
  ++counter;
  std::ostringstream ss;
  ss << LIVER_BEZIER_STORAGE_TEST_TEMP_DIR << "/vtkMRMLResectionPlanStorageNodeTest1_" << static_cast<long long>(LIVER_PLAN_GETPID()) << "_" << counter << "." << extension;
  return ss.str();
}

/// Populate a Bezier surface node with deterministic, distinctive
/// values touching every surface field the storage node round-trips.
/// Mirrors the ``populate`` helper from the predecessor test --
/// kept file-local per the no-shared-helpers convention.
void populateSurface(vtkMRMLBezierSurfaceNode* node)
{
  node->SetInitMode(vtkMRMLBezierSurfaceNode::DistanceSpheroid);

  double origin[3] = { 1.0, 2.0, 3.0 };
  node->SetSlicingPlaneOrigin(origin);
  double normal[3] = { 0.0, 1.0, 0.0 };
  node->SetSlicingPlaneNormal(normal);
  double p0[3] = { 4.0, 5.0, 6.0 };
  node->SetSlicingPlaneInitPoint(0, p0);
  double p1[3] = { 7.0, 8.0, 9.0 };
  node->SetSlicingPlaneInitPoint(1, p1);

  node->SetNumberOfDistanceSpheroidInitPoints(3);
  double q0[3] = { 10.0, 11.0, 12.0 };
  double q1[3] = { 13.0, 14.0, 15.0 };
  double q2[3] = { 16.0, 17.0, 18.0 };
  node->SetDistanceSpheroidInitPoint(0, q0);
  node->SetDistanceSpheroidInitPoint(1, q1);
  node->SetDistanceSpheroidInitPoint(2, q2);
  double center[3] = { 19.0, 20.0, 21.0 };
  node->SetDistanceSpheroidCenter(center);
  node->SetDistanceSpheroidRadiusX(2.5);
  node->SetDistanceSpheroidRadiusY(3.5);
  node->SetDistanceSpheroidRadiusZ(4.5);

  double grid[vtkMRMLBezierSurfaceNode::ControlGridSize];
  for (int i = 0; i < vtkMRMLBezierSurfaceNode::ControlGridSize; ++i)
  {
    grid[i] = static_cast<double>(i) * 0.125 + 0.0625;
  }
  node->SetControlGrid(grid);
}

/// Populate a plan with deterministic field values.  Plan defaults
/// per invariant 2 of vtkMRMLResectionPlanNodeTest1; this populates
/// the non-default values used in round-trip assertions.
void populatePlan(vtkMRMLResectionPlanNode* plan)
{
  plan->SetName("Right hemihepatectomy");
  plan->SetSafetyMargin(10.0);
  plan->SetRiskMargin(5.0);
  plan->SetOrderIndex(2);
  plan->SetState(vtkMRMLResectionPlanNode::Planning);
}

//------------------------------------------------------------------------------
// Invariant 1 -- Tag name + default extension.  These two values
// drive Slicer's file-format registry (the ``.lrp.json`` file
// extension shows up in File > Save dialogs).
int testDefaultWriteFileExtension()
{
  vtkNew<vtkMRMLResectionPlanStorageNode> storage;
  CHECK_STRING(storage->GetDefaultWriteFileExtension(), "lrp.json");
  CHECK_STRING(storage->GetNodeTagName(), "ResectionPlanStorage");
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 2 -- CanRead / CanWrite discrimination.  The storage
// node accepts the plan; rejects everything else (a Bezier surface
// is NO LONGER independently storable; passing one in must be
// rejected).  Carry-forward from the predecessor's
// ``testCanReadCanWriteDiscrimination`` -- now plan-typed.
int testCanReadCanWriteDiscrimination()
{
  vtkNew<vtkMRMLResectionPlanStorageNode> storage;
  vtkNew<vtkMRMLResectionPlanNode> plan;
  vtkNew<vtkMRMLBezierSurfaceNode> surface;
  vtkNew<vtkMRMLModelNode> model;

  CHECK_BOOL(storage->CanReadInReferenceNode(plan.GetPointer()), true);
  CHECK_BOOL(storage->CanWriteFromReferenceNode(plan.GetPointer()), true);

  // Surface is non-storable after the wrapper-vs-carrier landing --
  // pin the rejection so a future regression that wires a fallback
  // path is caught.
  CHECK_BOOL(storage->CanReadInReferenceNode(surface.GetPointer()), false);
  CHECK_BOOL(storage->CanWriteFromReferenceNode(surface.GetPointer()), false);

  CHECK_BOOL(storage->CanReadInReferenceNode(model.GetPointer()), false);
  CHECK_BOOL(storage->CanWriteFromReferenceNode(model.GetPointer()), false);

  CHECK_BOOL(storage->CanReadInReferenceNode(nullptr), false);
  CHECK_BOOL(storage->CanWriteFromReferenceNode(nullptr), false);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 3 -- Writer emits schemaVersion: 2.  Positive assertion
// + negative assertion against 3 (a write regression that bumps the
// version without an ADR is caught).
int testWriterEmitsSchemaVersion2()
{
  vtkNew<vtkMRMLScene> scene;
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanNode>::New());
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLBezierSurfaceNode>::New());

  vtkNew<vtkMRMLResectionPlanNode> plan;
  vtkNew<vtkMRMLBezierSurfaceNode> surface;
  scene->AddNode(plan.GetPointer());
  scene->AddNode(surface.GetPointer());
  populatePlan(plan.GetPointer());
  populateSurface(surface.GetPointer());
  plan->SetAndObserveGeometryNode(surface.GetPointer());

  const std::string path = makeTempPath("lrp.json");
  vtkNew<vtkMRMLResectionPlanStorageNode> writeStorage;
  writeStorage->SetFileName(path.c_str());
  CHECK_INT(writeStorage->WriteData(plan.GetPointer()), 1);

  std::ifstream f(path);
  std::stringstream ss;
  ss << f.rdbuf();
  const std::string contents = ss.str();

  // Positive assertion -- writer emits schemaVersion: 2.
  if (contents.find("\"schemaVersion\":2") == std::string::npos && contents.find("\"schemaVersion\": 2") == std::string::npos)
  {
    std::cerr << "Expected \"schemaVersion\": 2 in output JSON\n" << contents << "\n";
    return EXIT_FAILURE;
  }
  // Negative assertion -- writer does NOT emit schemaVersion: 3.
  if (contents.find("\"schemaVersion\":3") != std::string::npos || contents.find("\"schemaVersion\": 3") != std::string::npos)
  {
    std::cerr << "Writer regressed -- emitted schemaVersion: 3 (must be 2)\n" << contents << "\n";
    return EXIT_FAILURE;
  }

  vtksys::SystemTools::RemoveFile(path);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 4 -- Schema-version boundary rejection.  The [2, 2]
// closed interval rejects v1 (low), v3 (high), v99 (far).  Each is
// asserted as a vtkErrorMacro.
int testSchemaVersionBoundary()
{
  const int rejectedVersions[] = { 1, 3, 99 };
  for (int version : rejectedVersions)
  {
    const std::string path = makeTempPath("lrp.json");
    {
      std::ofstream ofs(path);
      ofs << "{\n";
      ofs << "  \"schemaVersion\": " << version << ",\n";
      ofs << "  \"name\": \"v" << version << "\",\n";
      ofs << "  \"safetyMargin\": 5.0,\n";
      ofs << "  \"riskMargin\": 2.5,\n";
      ofs << "  \"orderIndex\": 0,\n";
      ofs << "  \"state\": \"Init\",\n";
      ofs << "  \"surface\": { \"type\": \"Bezier\", \"rows\": 4, \"cols\": 4, "
             "\"controlGrid\": [0,0,0,0,0,0,0,0,0,0,0,0,"
             "0,0,0,0,0,0,0,0,0,0,0,0,"
             "0,0,0,0,0,0,0,0,0,0,0,0,"
             "0,0,0,0,0,0,0,0,0,0,0,0] }\n";
      ofs << "}\n";
    }

    vtkNew<vtkMRMLResectionPlanNode> sink;
    vtkNew<vtkMRMLResectionPlanStorageNode> storage;
    storage->SetFileName(path.c_str());

    TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
    CHECK_INT(storage->ReadData(sink.GetPointer()), 0);
    TESTING_OUTPUT_ASSERT_ERRORS_END();

    vtksys::SystemTools::RemoveFile(path);
  }
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 5 -- Plan-rooted round-trip.  Source plan + referenced
// surface; write; read into a fresh sink plan; assert every plan
// field + every surface field round-trips.  This is the canonical
// "v2 is correct" pin.
int testPlanRootedRoundTrip()
{
  vtkNew<vtkMRMLScene> srcScene;
  srcScene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanNode>::New());
  srcScene->RegisterNodeClass(vtkSmartPointer<vtkMRMLBezierSurfaceNode>::New());
  srcScene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanStorageNode>::New());

  vtkNew<vtkMRMLResectionPlanNode> source;
  vtkNew<vtkMRMLBezierSurfaceNode> sourceSurface;
  srcScene->AddNode(source.GetPointer());
  srcScene->AddNode(sourceSurface.GetPointer());
  populatePlan(source.GetPointer());
  populateSurface(sourceSurface.GetPointer());
  source->SetAndObserveGeometryNode(sourceSurface.GetPointer());

  const std::string path = makeTempPath("lrp.json");
  vtkNew<vtkMRMLResectionPlanStorageNode> writeStorage;
  writeStorage->SetFileName(path.c_str());
  CHECK_INT(writeStorage->WriteData(source.GetPointer()), 1);

  // Read into a fresh scene + fresh plan node.  The reader is
  // expected to walk the geometry ref out of the file and either
  // populate an existing surface (if Slicer already created it via
  // .mrml) OR instantiate one (if standalone load).  For this test,
  // pre-create both so the round-trip is in-place.
  vtkNew<vtkMRMLScene> sinkScene;
  sinkScene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanNode>::New());
  sinkScene->RegisterNodeClass(vtkSmartPointer<vtkMRMLBezierSurfaceNode>::New());
  sinkScene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanStorageNode>::New());

  vtkNew<vtkMRMLResectionPlanNode> sinkPlan;
  vtkNew<vtkMRMLBezierSurfaceNode> sinkSurface;
  sinkScene->AddNode(sinkPlan.GetPointer());
  sinkScene->AddNode(sinkSurface.GetPointer());
  sinkPlan->SetAndObserveGeometryNode(sinkSurface.GetPointer());

  vtkNew<vtkMRMLResectionPlanStorageNode> readStorage;
  readStorage->SetFileName(path.c_str());
  CHECK_INT(readStorage->ReadData(sinkPlan.GetPointer()), 1);

  // Plan field round-trip.
  CHECK_DOUBLE_TOLERANCE(sinkPlan->GetSafetyMargin(), source->GetSafetyMargin(), 1e-9);
  CHECK_DOUBLE_TOLERANCE(sinkPlan->GetRiskMargin(), source->GetRiskMargin(), 1e-9);
  CHECK_INT(sinkPlan->GetOrderIndex(), source->GetOrderIndex());
  CHECK_INT(sinkPlan->GetState(), source->GetState());

  // Surface field round-trip (via the geometry ref the reader
  // walked).  The sink surface is the one we pre-wired -- read
  // populates it in place.
  vtkMRMLBezierSurfaceNode* sinkBezier = vtkMRMLBezierSurfaceNode::SafeDownCast(sinkPlan->GetGeometryNode());
  CHECK_NOT_NULL(sinkBezier);
  CHECK_INT(sinkBezier->GetState(), sourceSurface->GetState());
  CHECK_INT(sinkBezier->GetInitMode(), sourceSurface->GetInitMode());
  for (int i = 0; i < vtkMRMLBezierSurfaceNode::ControlGridSize; ++i)
  {
    CHECK_DOUBLE_TOLERANCE(sinkBezier->GetControlGrid()[i], sourceSurface->GetControlGrid()[i], 1e-9);
  }

  vtksys::SystemTools::RemoveFile(path);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 6 -- ``surface.type`` discriminator on write.  Writer
// emits ``"type": "Bezier"`` for a Bezier-referencing plan.  The
// v2.1 NURBS sibling will emit ``"type": "NURBS"`` via the same
// dispatch site (no test authored here -- class does not exist yet,
// see "Out of scope" in the file header).
int testSurfaceTypeDiscriminatorOnWrite()
{
  vtkNew<vtkMRMLScene> scene;
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanNode>::New());
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLBezierSurfaceNode>::New());

  vtkNew<vtkMRMLResectionPlanNode> plan;
  vtkNew<vtkMRMLBezierSurfaceNode> surface;
  scene->AddNode(plan.GetPointer());
  scene->AddNode(surface.GetPointer());
  populatePlan(plan.GetPointer());
  populateSurface(surface.GetPointer());
  plan->SetAndObserveGeometryNode(surface.GetPointer());

  const std::string path = makeTempPath("lrp.json");
  vtkNew<vtkMRMLResectionPlanStorageNode> writeStorage;
  writeStorage->SetFileName(path.c_str());
  CHECK_INT(writeStorage->WriteData(plan.GetPointer()), 1);

  std::ifstream f(path);
  std::stringstream ss;
  ss << f.rdbuf();
  const std::string contents = ss.str();

  if (contents.find("\"type\":\"Bezier\"") == std::string::npos && contents.find("\"type\": \"Bezier\"") == std::string::npos)
  {
    std::cerr << "Writer regression -- surface.type missing or wrong:\n" << contents << "\n";
    return EXIT_FAILURE;
  }
  vtksys::SystemTools::RemoveFile(path);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 7 -- Standalone load.  A fresh scene; the reader walks
// the .lrp.json and produces BOTH a plan node AND a surface node
// wired via the geometry ref.  The surface class is dispatched by
// the ``surface.type`` discriminator -- "Bezier" -> instantiate a
// vtkMRMLBezierSurfaceNode.
//
// The test writes a known-good v2 file then reads it back into an
// empty scene via the storage node's ReadData -- the reader must
// add the surface itself (the predecessor's tests pre-created the
// surface; the wrapper-vs-carrier landing makes this a no-op for
// the caller).
int testStandaloneLoadCreatesSurface()
{
  // First, author a v2 fixture by round-tripping a populated source
  // (separate scene so the original instances are not picked up by
  // the sink scene's GetNodesByClass).
  std::string fixturePath;
  {
    vtkNew<vtkMRMLScene> srcScene;
    srcScene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanNode>::New());
    srcScene->RegisterNodeClass(vtkSmartPointer<vtkMRMLBezierSurfaceNode>::New());

    vtkNew<vtkMRMLResectionPlanNode> plan;
    vtkNew<vtkMRMLBezierSurfaceNode> surface;
    srcScene->AddNode(plan.GetPointer());
    srcScene->AddNode(surface.GetPointer());
    populatePlan(plan.GetPointer());
    populateSurface(surface.GetPointer());
    plan->SetAndObserveGeometryNode(surface.GetPointer());

    fixturePath = makeTempPath("lrp.json");
    vtkNew<vtkMRMLResectionPlanStorageNode> writeStorage;
    writeStorage->SetFileName(fixturePath.c_str());
    CHECK_INT(writeStorage->WriteData(plan.GetPointer()), 1);
  }

  // Fresh sink scene.  Empty plan, no surface yet.
  vtkNew<vtkMRMLScene> sinkScene;
  sinkScene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanNode>::New());
  sinkScene->RegisterNodeClass(vtkSmartPointer<vtkMRMLBezierSurfaceNode>::New());
  sinkScene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanStorageNode>::New());

  vtkNew<vtkMRMLResectionPlanNode> sinkPlan;
  sinkScene->AddNode(sinkPlan.GetPointer());

  vtkNew<vtkMRMLResectionPlanStorageNode> readStorage;
  readStorage->SetFileName(fixturePath.c_str());
  // The storage node is associated with the plan in the scene; add
  // it so the reader can use the scene to instantiate the surface.
  sinkScene->AddNode(readStorage.GetPointer());
  sinkPlan->SetAndObserveStorageNodeID(readStorage->GetID());
  CHECK_INT(readStorage->ReadData(sinkPlan.GetPointer()), 1);

  // After the read, the sink scene must contain a Bezier surface
  // node (the reader instantiated it from surface.type) AND the
  // sink plan's geometry ref must resolve to it.
  vtkSmartPointer<vtkCollection> bezierNodes = vtkSmartPointer<vtkCollection>::Take(sinkScene->GetNodesByClass("vtkMRMLBezierSurfaceNode"));
  if (bezierNodes->GetNumberOfItems() < 1)
  {
    std::cerr << "Standalone load did not instantiate a Bezier surface node\n";
    return EXIT_FAILURE;
  }
  vtkMRMLAbstractParametricSurfaceNode* surfaceViaPlan = sinkPlan->GetGeometryNode();
  CHECK_NOT_NULL(surfaceViaPlan);
  CHECK_BOOL(surfaceViaPlan->IsA("vtkMRMLBezierSurfaceNode"), true);

  vtksys::SystemTools::RemoveFile(fixturePath);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 8 -- Optional-fields defaults.  A minimal v2 file (only
// schemaVersion + surface.type + rows/cols/controlGrid) loads with
// the plan's documented defaults: margins=0.0, orderIndex=-1,
// state="Init".  Pin so a regression that hard-fails on missing
// optional fields is caught.
int testOptionalFieldsDefaults()
{
  const std::string path = makeTempPath("lrp.json");
  {
    std::ofstream ofs(path);
    ofs << "{\n";
    ofs << "  \"schemaVersion\": 2,\n";
    ofs << "  \"surface\": { \"type\": \"Bezier\", \"rows\": 4, \"cols\": 4, "
           "\"controlGrid\": [";
    for (int i = 0; i < 48; ++i)
    {
      if (i > 0)
      {
        ofs << ", ";
      }
      ofs << "0.0";
    }
    ofs << "] }\n";
    ofs << "}\n";
  }

  vtkNew<vtkMRMLScene> scene;
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanNode>::New());
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLBezierSurfaceNode>::New());
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanStorageNode>::New());

  vtkNew<vtkMRMLResectionPlanNode> plan;
  vtkNew<vtkMRMLBezierSurfaceNode> surface;
  scene->AddNode(plan.GetPointer());
  scene->AddNode(surface.GetPointer());
  plan->SetAndObserveGeometryNode(surface.GetPointer());

  vtkNew<vtkMRMLResectionPlanStorageNode> storage;
  storage->SetFileName(path.c_str());
  CHECK_INT(storage->ReadData(plan.GetPointer()), 1);

  CHECK_DOUBLE(plan->GetSafetyMargin(), 0.0);
  CHECK_DOUBLE(plan->GetRiskMargin(), 0.0);
  CHECK_INT(plan->GetOrderIndex(), -1);
  CHECK_INT(plan->GetState(), vtkMRMLResectionPlanNode::Init);

  vtksys::SystemTools::RemoveFile(path);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 9 -- scene.* block forward-compatibility.  A test
// fixture carrying the OLD scene.* blocks loads cleanly; the reader
// silently ignores those fields.  Writer separately does NOT emit
// scene.* on any path (covered by invariant 3's negative assertion
// on the round-trip output -- here we add an explicit absence check
// on the round-trip output).
int testSceneBlockForwardCompat()
{
  // Step A -- reader silently ignores scene.* blocks.
  const std::string path = makeTempPath("lrp.json");
  {
    std::ofstream ofs(path);
    ofs << "{\n";
    ofs << "  \"schemaVersion\": 2,\n";
    ofs << "  \"name\": \"plan-with-scene-block\",\n";
    ofs << "  \"safetyMargin\": 7.0,\n";
    ofs << "  \"riskMargin\": 3.0,\n";
    ofs << "  \"orderIndex\": 1,\n";
    ofs << "  \"state\": \"Planning\",\n";
    ofs << "  \"surface\": { \"type\": \"Bezier\", \"rows\": 4, \"cols\": 4, "
           "\"controlGrid\": [";
    for (int i = 0; i < 48; ++i)
    {
      if (i > 0)
      {
        ofs << ", ";
      }
      ofs << "0.0";
    }
    ofs << "] },\n";
    // The retired-block payload -- old fixtures may still carry it.
    ofs << "  \"scene\": {\n";
    ofs << "    \"classification\": { \"nodeId\": \"vtkMRMLStdCouinaudTerritoriesNode1\", "
           "\"subtype\": \"standard-couinaud\" },\n";
    ofs << "    \"volumetryPartitions\": [],\n";
    ofs << "    \"stageSelection\": { \"current\": 3 }\n";
    ofs << "  }\n";
    ofs << "}\n";
  }

  vtkNew<vtkMRMLScene> scene;
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanNode>::New());
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLBezierSurfaceNode>::New());
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanStorageNode>::New());

  vtkNew<vtkMRMLResectionPlanNode> plan;
  vtkNew<vtkMRMLBezierSurfaceNode> surface;
  scene->AddNode(plan.GetPointer());
  scene->AddNode(surface.GetPointer());
  plan->SetAndObserveGeometryNode(surface.GetPointer());

  vtkNew<vtkMRMLResectionPlanStorageNode> readStorage;
  readStorage->SetFileName(path.c_str());
  // ReadData succeeds: unknown fields are silently dropped per the
  // design.  No error or warning is required (the design says
  // silently).
  CHECK_INT(readStorage->ReadData(plan.GetPointer()), 1);
  CHECK_INT(plan->GetState(), vtkMRMLResectionPlanNode::Planning);
  CHECK_INT(plan->GetOrderIndex(), 1);

  vtksys::SystemTools::RemoveFile(path);

  // Step B -- writer never emits scene.* on the round-trip output.
  // (Complements the negative assertion in
  // testWriterEmitsSchemaVersion2; that test pins schemaVersion's
  // negative -- this one pins scene's.)
  populatePlan(plan.GetPointer());
  const std::string outPath = makeTempPath("lrp.json");
  vtkNew<vtkMRMLResectionPlanStorageNode> writeStorage;
  writeStorage->SetFileName(outPath.c_str());
  CHECK_INT(writeStorage->WriteData(plan.GetPointer()), 1);

  std::ifstream f(outPath);
  std::stringstream ss;
  ss << f.rdbuf();
  const std::string contents = ss.str();
  if (contents.find("\"scene\"") != std::string::npos || contents.find("\"classification\"") != std::string::npos || contents.find("\"volumetryPartitions\"") != std::string::npos
      || contents.find("\"stageSelection\"") != std::string::npos)
  {
    std::cerr << "Writer regression -- emitted scene.* fields (must be absent):\n" << contents << "\n";
    return EXIT_FAILURE;
  }

  vtksys::SystemTools::RemoveFile(outPath);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 10 -- Surface bulk-data full round-trip.  Pins all the
// surface-side fields (control grid, slicing plane subordinate,
// distance spheroid subordinate) byte-equivalent through the plan-
// rooted writer / reader.  Complements invariant 5 (which pins
// plan-side fields + spot-checks the control grid).
int testSurfaceBulkDataRoundTrip()
{
  vtkNew<vtkMRMLScene> scene;
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanNode>::New());
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLBezierSurfaceNode>::New());

  vtkNew<vtkMRMLResectionPlanNode> source;
  vtkNew<vtkMRMLBezierSurfaceNode> sourceSurface;
  scene->AddNode(source.GetPointer());
  scene->AddNode(sourceSurface.GetPointer());
  populatePlan(source.GetPointer());
  populateSurface(sourceSurface.GetPointer());
  source->SetAndObserveGeometryNode(sourceSurface.GetPointer());

  const std::string path = makeTempPath("lrp.json");
  vtkNew<vtkMRMLResectionPlanStorageNode> writeStorage;
  writeStorage->SetFileName(path.c_str());
  CHECK_INT(writeStorage->WriteData(source.GetPointer()), 1);

  // Sink in a fresh scene.
  vtkNew<vtkMRMLScene> sinkScene;
  sinkScene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanNode>::New());
  sinkScene->RegisterNodeClass(vtkSmartPointer<vtkMRMLBezierSurfaceNode>::New());

  vtkNew<vtkMRMLResectionPlanNode> sinkPlan;
  vtkNew<vtkMRMLBezierSurfaceNode> sinkSurface;
  sinkScene->AddNode(sinkPlan.GetPointer());
  sinkScene->AddNode(sinkSurface.GetPointer());
  sinkPlan->SetAndObserveGeometryNode(sinkSurface.GetPointer());

  vtkNew<vtkMRMLResectionPlanStorageNode> readStorage;
  readStorage->SetFileName(path.c_str());
  CHECK_INT(readStorage->ReadData(sinkPlan.GetPointer()), 1);

  vtkMRMLBezierSurfaceNode* sinkBezier = vtkMRMLBezierSurfaceNode::SafeDownCast(sinkPlan->GetGeometryNode());
  CHECK_NOT_NULL(sinkBezier);

  // Control grid byte-equivalent (1e-9 tolerance per Slicer
  // convention).
  for (int i = 0; i < vtkMRMLBezierSurfaceNode::ControlGridSize; ++i)
  {
    CHECK_DOUBLE_TOLERANCE(sinkBezier->GetControlGrid()[i], sourceSurface->GetControlGrid()[i], 1e-9);
  }

  // SlicingPlane subordinate.
  double a3[3], b3[3];
  sinkBezier->GetSlicingPlaneOrigin(a3);
  sourceSurface->GetSlicingPlaneOrigin(b3);
  for (int j = 0; j < 3; ++j)
  {
    CHECK_DOUBLE_TOLERANCE(a3[j], b3[j], 1e-9);
  }
  sinkBezier->GetSlicingPlaneNormal(a3);
  sourceSurface->GetSlicingPlaneNormal(b3);
  for (int j = 0; j < 3; ++j)
  {
    CHECK_DOUBLE_TOLERANCE(a3[j], b3[j], 1e-9);
  }
  for (int i = 0; i < 2; ++i)
  {
    const double* a = sinkBezier->GetSlicingPlaneInitPoint(i);
    const double* b = sourceSurface->GetSlicingPlaneInitPoint(i);
    CHECK_NOT_NULL(a);
    CHECK_NOT_NULL(b);
    for (int j = 0; j < 3; ++j)
    {
      CHECK_DOUBLE_TOLERANCE(a[j], b[j], 1e-9);
    }
  }

  // DistanceSpheroid subordinate.
  CHECK_INT(sinkBezier->GetNumberOfDistanceSpheroidInitPoints(), sourceSurface->GetNumberOfDistanceSpheroidInitPoints());
  for (int i = 0; i < sinkBezier->GetNumberOfDistanceSpheroidInitPoints(); ++i)
  {
    const double* a = sinkBezier->GetDistanceSpheroidInitPoint(i);
    const double* b = sourceSurface->GetDistanceSpheroidInitPoint(i);
    CHECK_NOT_NULL(a);
    CHECK_NOT_NULL(b);
    for (int j = 0; j < 3; ++j)
    {
      CHECK_DOUBLE_TOLERANCE(a[j], b[j], 1e-9);
    }
  }
  sinkBezier->GetDistanceSpheroidCenter(a3);
  sourceSurface->GetDistanceSpheroidCenter(b3);
  for (int j = 0; j < 3; ++j)
  {
    CHECK_DOUBLE_TOLERANCE(a3[j], b3[j], 1e-9);
  }
  CHECK_DOUBLE_TOLERANCE(sinkBezier->GetDistanceSpheroidRadiusX(), sourceSurface->GetDistanceSpheroidRadiusX(), 1e-9);
  CHECK_DOUBLE_TOLERANCE(sinkBezier->GetDistanceSpheroidRadiusY(), sourceSurface->GetDistanceSpheroidRadiusY(), 1e-9);
  CHECK_DOUBLE_TOLERANCE(sinkBezier->GetDistanceSpheroidRadiusZ(), sourceSurface->GetDistanceSpheroidRadiusZ(), 1e-9);

  vtksys::SystemTools::RemoveFile(path);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Phase 1 -- storage-node defensive guard coverage.  Each subtest
// drives one rejection branch in ReadDataInternal / WriteDataInternal
// or the inner WriteJson / ReadJson dispatch.  Source of truth: the
// post-impl /slicer-review synthesis cited
// vtkMRMLResectionPlanStorageNode.cxx lines 107-486 as uncovered
// branches; the subtests below pin each one with a 5-15 line minimum
// reproducer.  Authoring discipline per
// ``Docs/design/resection-plan-architecture/03-storage-ownership.md``
// §"Plan node" (rejection invariants are part of the storage contract).

//------------------------------------------------------------------------------
// Phase 1.1 -- ReadDataInternal rejects a null refNode (defensive
// guard at vtkMRMLResectionPlanStorageNode.cxx line ~107).  Exercised
// via the test-only forwarder; the public ReadData layer catches null
// earlier, so the local guard requires direct invocation.
int testReadDataInternalNullRefNode()
{
  vtkNew<ExposedStorageNode> storage;
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  CHECK_INT(storage->CallReadDataInternal(nullptr), 0);
  TESTING_OUTPUT_ASSERT_ERRORS_END();
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Phase 1.2 -- ReadDataInternal rejects a wrong-class refNode.  The
// guard at line ~112 SafeDownCasts to vtkMRMLResectionPlanNode; a
// vtkMRMLModelNode must fail the cast and trigger the error.
int testReadDataInternalWrongClassRefNode()
{
  vtkNew<ExposedStorageNode> storage;
  vtkNew<vtkMRMLModelNode> model;
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  CHECK_INT(storage->CallReadDataInternal(model.GetPointer()), 0);
  TESTING_OUTPUT_ASSERT_ERRORS_END();
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Phase 1.3 -- ReadDataInternal rejects an empty filename (guard at
// line ~122 after GetFullNameFromFileName).
int testReadDataInternalEmptyFileName()
{
  vtkNew<ExposedStorageNode> storage;
  vtkNew<vtkMRMLResectionPlanNode> plan;
  // Do not SetFileName -- GetFullNameFromFileName returns empty.
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  CHECK_INT(storage->CallReadDataInternal(plan.GetPointer()), 0);
  TESTING_OUTPUT_ASSERT_ERRORS_END();
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Phase 1.4 -- ReadDataInternal rejects an unsupported file extension
// (guard at line ~128 -- only ``.lrp.json`` and ``.json`` admitted).
int testReadDataInternalUnsupportedExtension()
{
  vtkNew<ExposedStorageNode> storage;
  vtkNew<vtkMRMLResectionPlanNode> plan;
  const std::string path = makeTempPath("txt");
  storage->SetFileName(path.c_str());
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  CHECK_INT(storage->CallReadDataInternal(plan.GetPointer()), 0);
  TESTING_OUTPUT_ASSERT_ERRORS_END();
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Phase 1.5 -- WriteDataInternal rejects a null refNode AND a
// wrong-class refNode (symmetric guards at lines ~141 + ~147).
// Bundled per the planner table: both are one-line branches in the
// same writer prologue.
int testWriteDataInternalNullOrWrongClass()
{
  vtkNew<ExposedStorageNode> storage;
  vtkNew<vtkMRMLModelNode> model;
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  CHECK_INT(storage->CallWriteDataInternal(nullptr), 0);
  CHECK_INT(storage->CallWriteDataInternal(model.GetPointer()), 0);
  TESTING_OUTPUT_ASSERT_ERRORS_END();
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Phase 1.6 -- WriteDataInternal rejects an empty filename (guard at
// line ~155, symmetric with the reader).
int testWriteDataInternalEmptyFileName()
{
  vtkNew<ExposedStorageNode> storage;
  vtkNew<vtkMRMLResectionPlanNode> plan;
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  CHECK_INT(storage->CallWriteDataInternal(plan.GetPointer()), 0);
  TESTING_OUTPUT_ASSERT_ERRORS_END();
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Phase 1.7 -- WriteDataInternal rejects an unsupported file extension
// (guard at line ~161, symmetric with the reader's ext check).
int testWriteDataInternalUnsupportedExtension()
{
  vtkNew<ExposedStorageNode> storage;
  vtkNew<vtkMRMLResectionPlanNode> plan;
  const std::string path = makeTempPath("txt");
  storage->SetFileName(path.c_str());
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  CHECK_INT(storage->CallWriteDataInternal(plan.GetPointer()), 0);
  TESTING_OUTPUT_ASSERT_ERRORS_END();
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Phase 1.8 -- ReadJson rejects an unparseable JSON file (guard at
// line ~330 -- ``reader->ReadFromFile`` returns null on syntax error).
int testReadJsonUnparseable()
{
  const std::string path = makeTempPath("lrp.json");
  {
    std::ofstream ofs(path);
    ofs << "{not valid json";
  }
  vtkNew<vtkMRMLScene> scene;
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanNode>::New());
  vtkNew<vtkMRMLResectionPlanNode> plan;
  scene->AddNode(plan.GetPointer());

  vtkNew<vtkMRMLResectionPlanStorageNode> storage;
  storage->SetFileName(path.c_str());
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  CHECK_INT(storage->ReadData(plan.GetPointer()), 0);
  TESTING_OUTPUT_ASSERT_ERRORS_END();
  vtksys::SystemTools::RemoveFile(path);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Phase 1.9 -- ReadJson rejects a minimal JSON document missing the
// required ``schemaVersion`` field (guard at line ~337 -- HasMember
// check).  Pinned per design-doc 05-lrp-json-schema.md §"Reader /
// writer behaviour" first bullet.
int testReadJsonMissingSchemaVersion()
{
  const std::string path = makeTempPath("lrp.json");
  {
    std::ofstream ofs(path);
    ofs << "{\"name\": \"x\"}\n";
  }
  vtkNew<vtkMRMLScene> scene;
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanNode>::New());
  vtkNew<vtkMRMLResectionPlanNode> plan;
  scene->AddNode(plan.GetPointer());

  vtkNew<vtkMRMLResectionPlanStorageNode> storage;
  storage->SetFileName(path.c_str());
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  CHECK_INT(storage->ReadData(plan.GetPointer()), 0);
  TESTING_OUTPUT_ASSERT_ERRORS_END();
  vtksys::SystemTools::RemoveFile(path);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Phase 1.10 -- ReadJson rejects an unknown ``surface.type`` value
// (dispatch fall-through at line ~462; admitted values are "Bezier"
// and "NURBS" per design-doc 05-lrp-json-schema.md §"surface.type").
int testReadJsonUnknownSurfaceType()
{
  const std::string path = makeTempPath("lrp.json");
  {
    std::ofstream ofs(path);
    ofs << "{\n";
    ofs << "  \"schemaVersion\": 2,\n";
    ofs << "  \"surface\": { \"type\": \"Cubic\", \"rows\": 4, \"cols\": 4 }\n";
    ofs << "}\n";
  }
  vtkNew<vtkMRMLScene> scene;
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanNode>::New());
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLBezierSurfaceNode>::New());
  vtkNew<vtkMRMLResectionPlanNode> plan;
  scene->AddNode(plan.GetPointer());

  vtkNew<vtkMRMLResectionPlanStorageNode> storage;
  storage->SetFileName(path.c_str());
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  CHECK_INT(storage->ReadData(plan.GetPointer()), 0);
  TESTING_OUTPUT_ASSERT_ERRORS_END();
  vtksys::SystemTools::RemoveFile(path);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Phase 1.11 -- ReadJson rejects ``surface.type: "NURBS"`` with the
// documented v2.1 deferral message (dispatch arm at line ~452).
// **Valuable** -- pins the explicit v2.1 deferral path; ADR-0018 §3
// + design-doc 05-lrp-json-schema.md §"v2.1 polymorphic extension
// preview".  Regression that ships NURBS prematurely is caught.
int testReadJsonNurbsRejectedV20()
{
  const std::string path = makeTempPath("lrp.json");
  {
    std::ofstream ofs(path);
    ofs << "{\n";
    ofs << "  \"schemaVersion\": 2,\n";
    ofs << "  \"surface\": { \"type\": \"NURBS\", \"rows\": 4, \"cols\": 4 }\n";
    ofs << "}\n";
  }
  vtkNew<vtkMRMLScene> scene;
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanNode>::New());
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLBezierSurfaceNode>::New());
  vtkNew<vtkMRMLResectionPlanNode> plan;
  scene->AddNode(plan.GetPointer());

  vtkNew<vtkMRMLResectionPlanStorageNode> storage;
  storage->SetFileName(path.c_str());
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  CHECK_INT(storage->ReadData(plan.GetPointer()), 0);
  TESTING_OUTPUT_ASSERT_ERRORS_END();
  vtksys::SystemTools::RemoveFile(path);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Phase 1.12 -- ReadJson rejects a plan with a ``surface`` block when
// the plan has neither an existing geometry node nor a scene to
// instantiate one into (guard at line ~440).  Construct the plan
// without adding it to a scene; ReadData via the storage node returns
// 0 with an error.  The empty CanReadInReferenceNode prereq is met
// because Slicer's storage-node base does not require a scene; only
// our inner ReadJson does, for the surface-instantiation step.
int testReadJsonPlanNoSceneNoSurface()
{
  const std::string path = makeTempPath("lrp.json");
  {
    std::ofstream ofs(path);
    ofs << "{\n";
    ofs << "  \"schemaVersion\": 2,\n";
    ofs << "  \"surface\": { \"type\": \"Bezier\", \"rows\": 4, \"cols\": 4, \"controlGrid\": [";
    for (int i = 0; i < 48; ++i)
    {
      if (i > 0)
      {
        ofs << ",";
      }
      ofs << "0.0";
    }
    ofs << "] }\n";
    ofs << "}\n";
  }
  vtkNew<vtkMRMLResectionPlanNode> plan; // intentionally NOT added to any scene
  vtkNew<ExposedStorageNode> storage;
  storage->SetFileName(path.c_str());
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  CHECK_INT(storage->CallReadDataInternal(plan.GetPointer()), 0);
  TESTING_OUTPUT_ASSERT_ERRORS_END();
  vtksys::SystemTools::RemoveFile(path);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Phase 1.13 -- ReadJson rejects an out-of-band or non-square
// rows/cols shape (guard at line ~496 -- ADR-0018 §1 admits {(3,3),
// (4,4)} only).  Use rows=5,cols=5 -- in-band integer but outside the
// admitted set.
int testReadJsonInvalidRowsColsShape()
{
  const std::string path = makeTempPath("lrp.json");
  {
    std::ofstream ofs(path);
    ofs << "{\n";
    ofs << "  \"schemaVersion\": 2,\n";
    ofs << "  \"surface\": { \"type\": \"Bezier\", \"rows\": 5, \"cols\": 5, \"controlGrid\": [] }\n";
    ofs << "}\n";
  }
  vtkNew<vtkMRMLScene> scene;
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanNode>::New());
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLBezierSurfaceNode>::New());
  vtkNew<vtkMRMLResectionPlanNode> plan;
  scene->AddNode(plan.GetPointer());

  vtkNew<vtkMRMLResectionPlanStorageNode> storage;
  storage->SetFileName(path.c_str());
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  CHECK_INT(storage->ReadData(plan.GetPointer()), 0);
  TESTING_OUTPUT_ASSERT_ERRORS_END();
  vtksys::SystemTools::RemoveFile(path);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Phase 1.14 -- ReadJson rejects a wrong-length ``controlGrid`` array
// (guard at line ~522 -- expected 3 * rows * cols doubles).  Fixture
// declares rows=4,cols=4 (expected 48 doubles) and supplies only 10.
int testReadJsonControlGridLengthMismatch()
{
  const std::string path = makeTempPath("lrp.json");
  {
    std::ofstream ofs(path);
    ofs << "{\n";
    ofs << "  \"schemaVersion\": 2,\n";
    ofs << "  \"surface\": { \"type\": \"Bezier\", \"rows\": 4, \"cols\": 4, "
           "\"controlGrid\": [0,0,0,0,0,0,0,0,0,0] }\n";
    ofs << "}\n";
  }
  vtkNew<vtkMRMLScene> scene;
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanNode>::New());
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLBezierSurfaceNode>::New());
  vtkNew<vtkMRMLResectionPlanNode> plan;
  scene->AddNode(plan.GetPointer());

  vtkNew<vtkMRMLResectionPlanStorageNode> storage;
  storage->SetFileName(path.c_str());
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  CHECK_INT(storage->ReadData(plan.GetPointer()), 0);
  TESTING_OUTPUT_ASSERT_ERRORS_END();
  vtksys::SystemTools::RemoveFile(path);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Phase 1.15 -- WriteJson emits a warning and a plan-only document
// when the plan has no geometry reference (branch at line ~271 --
// the ``surface == nullptr`` arm).  Pinned per design-doc
// 04-save-load-flows.md §"Failure modes" -- mid-init plans without a
// surface still serialise; reload recovers the plan with documented
// defaults.
int testWriteJsonPlanWithoutGeometry()
{
  vtkNew<vtkMRMLScene> scene;
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanNode>::New());
  vtkNew<vtkMRMLResectionPlanNode> plan;
  scene->AddNode(plan.GetPointer());
  populatePlan(plan.GetPointer());
  // intentionally NOT setting a geometry node

  const std::string path = makeTempPath("lrp.json");
  vtkNew<vtkMRMLResectionPlanStorageNode> storage;
  storage->SetFileName(path.c_str());
  // The base WriteData layer surfaces a warning for the missing
  // geometry; the write itself still succeeds and the file lands.
  TESTING_OUTPUT_ASSERT_WARNINGS_BEGIN();
  CHECK_INT(storage->WriteData(plan.GetPointer()), 1);
  TESTING_OUTPUT_ASSERT_WARNINGS_END();

  std::ifstream f(path);
  std::stringstream ss;
  ss << f.rdbuf();
  const std::string contents = ss.str();
  if (contents.find("\"surface\"") != std::string::npos)
  {
    std::cerr << "Plan-only write regression -- surface block emitted despite no geometry node:\n" << contents << "\n";
    return EXIT_FAILURE;
  }
  vtksys::SystemTools::RemoveFile(path);
  return EXIT_SUCCESS;
}

} // namespace

//------------------------------------------------------------------------------
//------------------------------------------------------------------------------
// Legacy margin keys -- files written before the margin rename carry the
// unit-suffixed keys; the reader must still populate the fields (writers
// emit only the current keys, pinned by the round-trip invariants above).
int testLegacyMarginKeysStillLoad()
{
  const std::string path = makeTempPath("lrp.json");
  {
    std::ofstream ofs(path);
    ofs << "{\n";
    ofs << "  \"schemaVersion\": 2,\n";
    ofs << "  \"name\": \"legacy-margin-keys\",\n";
    ofs << "  \"safetyMargin_mm\": 9.0,\n";
    ofs << "  \"riskMargin_mm\": 2.0,\n";
    ofs << "  \"orderIndex\": 0,\n";
    ofs << "  \"state\": \"Init\",\n";
    ofs << "  \"surface\": { \"type\": \"Bezier\", \"rows\": 4, \"cols\": 4, "
           "\"controlGrid\": [";
    for (int i = 0; i < 48; ++i)
    {
      if (i > 0)
      {
        ofs << ", ";
      }
      ofs << "0.0";
    }
    ofs << "] }\n";
    ofs << "}\n";
  }

  vtkNew<vtkMRMLScene> scene;
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanNode>::New());
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLBezierSurfaceNode>::New());
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanStorageNode>::New());

  vtkNew<vtkMRMLResectionPlanNode> plan;
  vtkNew<vtkMRMLBezierSurfaceNode> surface;
  scene->AddNode(plan.GetPointer());
  scene->AddNode(surface.GetPointer());
  plan->SetAndObserveGeometryNode(surface.GetPointer());

  vtkNew<vtkMRMLResectionPlanStorageNode> storage;
  storage->SetFileName(path.c_str());

  CHECK_INT(storage->ReadData(plan.GetPointer()), 1);
  CHECK_DOUBLE_TOLERANCE(plan->GetSafetyMargin(), 9.0, 1e-9);
  CHECK_DOUBLE_TOLERANCE(plan->GetRiskMargin(), 2.0, 1e-9);

  vtksys::SystemTools::RemoveFile(path);
  return EXIT_SUCCESS;
}

int vtkMRMLResectionPlanStorageNodeTest1(int, char*[])
{
  vtkNew<vtkMRMLScene> scene;
  vtkNew<vtkMRMLResectionPlanStorageNode> exerciseNode;
  exerciseNode->SetScene(scene.GetPointer());
  EXERCISE_ALL_BASIC_MRML_METHODS(exerciseNode.GetPointer());

  CHECK_EXIT_SUCCESS(testDefaultWriteFileExtension());
  CHECK_EXIT_SUCCESS(testCanReadCanWriteDiscrimination());
  CHECK_EXIT_SUCCESS(testWriterEmitsSchemaVersion2());
  CHECK_EXIT_SUCCESS(testSchemaVersionBoundary());
  CHECK_EXIT_SUCCESS(testPlanRootedRoundTrip());
  CHECK_EXIT_SUCCESS(testSurfaceTypeDiscriminatorOnWrite());
  CHECK_EXIT_SUCCESS(testStandaloneLoadCreatesSurface());
  CHECK_EXIT_SUCCESS(testOptionalFieldsDefaults());
  CHECK_EXIT_SUCCESS(testSceneBlockForwardCompat());
  CHECK_EXIT_SUCCESS(testLegacyMarginKeysStillLoad());
  CHECK_EXIT_SUCCESS(testSurfaceBulkDataRoundTrip());

  // Phase 1 -- defensive guard + JSON dispatch coverage (closes the
  // codecov gaps from the post-impl /slicer-review pass).
  CHECK_EXIT_SUCCESS(testReadDataInternalNullRefNode());
  CHECK_EXIT_SUCCESS(testReadDataInternalWrongClassRefNode());
  CHECK_EXIT_SUCCESS(testReadDataInternalEmptyFileName());
  CHECK_EXIT_SUCCESS(testReadDataInternalUnsupportedExtension());
  CHECK_EXIT_SUCCESS(testWriteDataInternalNullOrWrongClass());
  CHECK_EXIT_SUCCESS(testWriteDataInternalEmptyFileName());
  CHECK_EXIT_SUCCESS(testWriteDataInternalUnsupportedExtension());
  CHECK_EXIT_SUCCESS(testReadJsonUnparseable());
  CHECK_EXIT_SUCCESS(testReadJsonMissingSchemaVersion());
  CHECK_EXIT_SUCCESS(testReadJsonUnknownSurfaceType());
  CHECK_EXIT_SUCCESS(testReadJsonNurbsRejectedV20());
  CHECK_EXIT_SUCCESS(testReadJsonPlanNoSceneNoSurface());
  CHECK_EXIT_SUCCESS(testReadJsonInvalidRowsColsShape());
  CHECK_EXIT_SUCCESS(testReadJsonControlGridLengthMismatch());
  CHECK_EXIT_SUCCESS(testWriteJsonPlanWithoutGeometry());

  std::cout << "vtkMRMLResectionPlanStorageNodeTest1 completed successfully" << std::endl;
  return EXIT_SUCCESS;
}

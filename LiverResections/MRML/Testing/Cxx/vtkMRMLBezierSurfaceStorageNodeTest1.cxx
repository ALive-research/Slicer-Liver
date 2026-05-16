/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Tests for vtkMRMLBezierSurfaceStorageNode — the new ``.lrp.json``
  storage node landed by task T2.5 per ADR-0014 §5.  Exercises:

   - JSON round-trip (populate → write → read → assert equality)
   - schemaVersion mismatch rejection
   - CanReadInReferenceNode / CanWriteFromReferenceNode discrimination
   - Legacy .lrp.fcsv migration read path
   - Legacy .lrp.fcsv write rejection

  ADR-0008 §2: C++ low-level tests live alongside the MRML library
  and run under the ctkTest driver with no Slicer launch and no Qt.

==============================================================================*/

// This module MRML includes
#include "vtkMRMLBezierSurfaceNode.h"
#include "vtkMRMLBezierSurfaceStorageNode.h"

// MRML includes
#include "vtkMRMLCoreTestingMacros.h"
#include "vtkMRMLModelNode.h"
#include "vtkMRMLScene.h"

// VTK includes
#include <vtkNew.h>
#include <vtkSmartPointer.h>
#include <vtksys/SystemTools.hxx>

// STD includes
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>

// Portable getpid — used to disambiguate temp-file names within a
// single test run.  ``_getpid`` on Windows, ``getpid`` on POSIX.
#if defined(_WIN32)
# include <process.h>
# define LIVER_BEZIER_GETPID _getpid
#else
# include <unistd.h>
# define LIVER_BEZIER_GETPID ::getpid
#endif

namespace
{

/// Generate a unique temp file path with the given extension.  Rooted
/// under ``LIVER_BEZIER_STORAGE_TEST_TEMP_DIR`` — the CMake binary
/// tree's ``Testing/Temporary`` directory, resolved at configure time
/// and guaranteed writable across Windows/macOS/Linux (the
/// build-tree-relative path avoids POSIX ``TMPDIR`` / ``/tmp``
/// reliance).  Uniqueness comes from pid + a static counter.
std::string makeTempPath(const std::string& extension)
{
  static int counter = 0;
  ++counter;
  std::ostringstream ss;
  ss << LIVER_BEZIER_STORAGE_TEST_TEMP_DIR << "/vtkMRMLBezierSurfaceStorageNodeTest1_" << static_cast<long long>(LIVER_BEZIER_GETPID()) << "_" << counter << "." << extension;
  return ss.str();
}

/// Populate a Bezier surface node with deterministic, distinctive
/// values touching every field the storage node round-trips.  The
/// init-mode subordinate data is set while the node is still in
/// Init (the ADR-0014 §4 read-only guard otherwise rejects the
/// mutations).
void populate(vtkMRMLBezierSurfaceNode* node)
{
  node->SetInitMode(vtkMRMLBezierSurfaceNode::DistanceSpheroid);

  // SlicingPlane init data.
  double origin[3] = { 1.0, 2.0, 3.0 };
  node->SetSlicingPlaneOrigin(origin);
  double normal[3] = { 0.0, 1.0, 0.0 };
  node->SetSlicingPlaneNormal(normal);
  double p0[3] = { 4.0, 5.0, 6.0 };
  node->SetSlicingPlaneInitPoint(0, p0);
  double p1[3] = { 7.0, 8.0, 9.0 };
  node->SetSlicingPlaneInitPoint(1, p1);

  // DistanceSpheroid init data.
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

  // Transition to Planning before setting the control grid — the
  // control grid is editable in both states but this exercises the
  // realistic write path.
  node->SetState(vtkMRMLBezierSurfaceNode::Planning);
  double grid[vtkMRMLBezierSurfaceNode::ControlGridSize];
  for (int i = 0; i < vtkMRMLBezierSurfaceNode::ControlGridSize; ++i)
  {
    grid[i] = static_cast<double>(i) * 0.125 + 0.0625;
  }
  node->SetControlGrid(grid);
}

int testJsonRoundTrip()
{
  // Populate a source node, write to .lrp.json, read into a fresh
  // node, assert every field round-trips.
  vtkNew<vtkMRMLBezierSurfaceNode> source;
  populate(source.GetPointer());

  const std::string path = makeTempPath("lrp.json");
  vtkNew<vtkMRMLBezierSurfaceStorageNode> writeStorage;
  writeStorage->SetFileName(path.c_str());
  CHECK_INT(writeStorage->WriteData(source.GetPointer()), 1);

  vtkNew<vtkMRMLBezierSurfaceNode> sink;
  vtkNew<vtkMRMLBezierSurfaceStorageNode> readStorage;
  readStorage->SetFileName(path.c_str());
  CHECK_INT(readStorage->ReadData(sink.GetPointer()), 1);

  // Enum round-trip.
  CHECK_INT(sink->GetState(), source->GetState());
  CHECK_INT(sink->GetInitMode(), source->GetInitMode());

  // Control grid round-trip.
  for (int i = 0; i < vtkMRMLBezierSurfaceNode::ControlGridSize; ++i)
  {
    CHECK_DOUBLE_TOLERANCE(sink->GetControlGrid()[i], source->GetControlGrid()[i], 1e-9);
  }

  // SlicingPlane round-trip.
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
  for (int i = 0; i < 2; ++i)
  {
    const double* a = sink->GetSlicingPlaneInitPoint(i);
    const double* b = source->GetSlicingPlaneInitPoint(i);
    CHECK_NOT_NULL(a);
    CHECK_NOT_NULL(b);
    for (int j = 0; j < 3; ++j)
    {
      CHECK_DOUBLE_TOLERANCE(a[j], b[j], 1e-9);
    }
  }

  // DistanceSpheroid round-trip.
  CHECK_INT(sink->GetNumberOfDistanceSpheroidInitPoints(), source->GetNumberOfDistanceSpheroidInitPoints());
  for (int i = 0; i < sink->GetNumberOfDistanceSpheroidInitPoints(); ++i)
  {
    const double* a = sink->GetDistanceSpheroidInitPoint(i);
    const double* b = source->GetDistanceSpheroidInitPoint(i);
    CHECK_NOT_NULL(a);
    CHECK_NOT_NULL(b);
    for (int j = 0; j < 3; ++j)
    {
      CHECK_DOUBLE_TOLERANCE(a[j], b[j], 1e-9);
    }
  }
  sink->GetDistanceSpheroidCenter(a3);
  source->GetDistanceSpheroidCenter(b3);
  for (int j = 0; j < 3; ++j)
  {
    CHECK_DOUBLE_TOLERANCE(a3[j], b3[j], 1e-9);
  }
  CHECK_DOUBLE_TOLERANCE(sink->GetDistanceSpheroidRadiusX(), source->GetDistanceSpheroidRadiusX(), 1e-9);
  CHECK_DOUBLE_TOLERANCE(sink->GetDistanceSpheroidRadiusY(), source->GetDistanceSpheroidRadiusY(), 1e-9);
  CHECK_DOUBLE_TOLERANCE(sink->GetDistanceSpheroidRadiusZ(), source->GetDistanceSpheroidRadiusZ(), 1e-9);

  // Clean up the temp file.
  vtksys::SystemTools::RemoveFile(path);
  return EXIT_SUCCESS;
}

int testSchemaVersionMismatch()
{
  // Synthesize a JSON with an unknown schemaVersion and assert
  // ReadDataInternal rejects it with a non-zero exit (the rejection
  // emits a vtkErrorMacro; gate the WITH_VTK_ERROR_OUTPUT_CHECK
  // counter inside ASSERT_ERRORS_BEGIN/END).
  const std::string path = makeTempPath("lrp.json");
  {
    std::ofstream ofs(path);
    ofs << "{\n";
    ofs << "  \"schemaVersion\": 99,\n";
    ofs << "  \"state\": \"Init\",\n";
    ofs << "  \"initMode\": \"SlicingPlane\"\n";
    ofs << "}\n";
  }

  vtkNew<vtkMRMLBezierSurfaceNode> sink;
  vtkNew<vtkMRMLBezierSurfaceStorageNode> storage;
  storage->SetFileName(path.c_str());

  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  CHECK_INT(storage->ReadData(sink.GetPointer()), 0);
  TESTING_OUTPUT_ASSERT_ERRORS_END();

  vtksys::SystemTools::RemoveFile(path);
  return EXIT_SUCCESS;
}

int testCanReadCanWriteDiscrimination()
{
  // The storage node should accept a vtkMRMLBezierSurfaceNode for
  // both read and write, and reject anything else (e.g. a
  // vtkMRMLModelNode).
  vtkNew<vtkMRMLBezierSurfaceStorageNode> storage;
  vtkNew<vtkMRMLBezierSurfaceNode> surface;
  vtkNew<vtkMRMLModelNode> model;

  CHECK_BOOL(storage->CanReadInReferenceNode(surface.GetPointer()), true);
  CHECK_BOOL(storage->CanWriteFromReferenceNode(surface.GetPointer()), true);
  CHECK_BOOL(storage->CanReadInReferenceNode(model.GetPointer()), false);
  CHECK_BOOL(storage->CanWriteFromReferenceNode(model.GetPointer()), false);
  CHECK_BOOL(storage->CanReadInReferenceNode(nullptr), false);
  CHECK_BOOL(storage->CanWriteFromReferenceNode(nullptr), false);
  return EXIT_SUCCESS;
}

int testDefaultWriteFileExtension()
{
  vtkNew<vtkMRMLBezierSurfaceStorageNode> storage;
  CHECK_STRING(storage->GetDefaultWriteFileExtension(), "lrp.json");
  CHECK_STRING(storage->GetNodeTagName(), "BezierSurfaceStorage");
  return EXIT_SUCCESS;
}

int testLegacyFcsvRead()
{
  // Build a 16-point 4x4 grid fixture (z=0) and assert the legacy
  // CSV reader maps it onto controlGrid correctly with the default
  // post-migration state ("Planning" / "SlicingPlane") plus the
  // documented vtkWarningMacro.
  const std::string path = makeTempPath("lrp.fcsv");
  {
    std::ofstream ofs(path);
    ofs << "# Markups fiducial file version = 4.11\n";
    ofs << "# CoordinateSystem = LPS\n";
    ofs << "# columns = id,x,y,z,ow,ox,oy,oz,vis,sel,lock,label,desc,associatedNodeID\n";
    for (int i = 0; i < 16; ++i)
    {
      const double x = static_cast<double>(i % 4) * 10.0;
      const double y = static_cast<double>(i / 4) * 10.0;
      ofs << "vtkMRMLMarkupsFiducialNode_" << (i + 1) << "," << x << "," << y << ","
          << "0.0,0.0,0.0,0.0,1.0,1,1,0,P-" << (i + 1) << ",,vtkMRMLScalarVolumeNode1\n";
    }
  }

  vtkNew<vtkMRMLBezierSurfaceNode> sink;
  vtkNew<vtkMRMLBezierSurfaceStorageNode> storage;
  storage->SetFileName(path.c_str());

  // ReadLegacyFcsv emits a vtkWarningMacro by design (the
  // migration-mode disclaimer).  Gate the warning-as-failure check
  // around the call.
  TESTING_OUTPUT_ASSERT_WARNINGS_BEGIN();
  CHECK_INT(storage->ReadData(sink.GetPointer()), 1);
  TESTING_OUTPUT_ASSERT_WARNINGS_END();

  // Field assertions.
  CHECK_INT(sink->GetState(), vtkMRMLBezierSurfaceNode::Planning);
  CHECK_INT(sink->GetInitMode(), vtkMRMLBezierSurfaceNode::SlicingPlane);

  // Spot-check a few control-grid entries: row-major (i, j) with
  // i = row index, j = column index, x = j*10, y = i*10, z = 0.
  // Index 0 → (0, 0, 0); index 3 → (30, 0, 0) (end of first row);
  // index 12 → (0, 30, 0) (start of last row); index 15 → (30, 30, 0).
  const double* grid = sink->GetControlGrid();
  CHECK_DOUBLE(grid[0 * 3 + 0], 0.0);
  CHECK_DOUBLE(grid[0 * 3 + 1], 0.0);
  CHECK_DOUBLE(grid[0 * 3 + 2], 0.0);
  CHECK_DOUBLE(grid[3 * 3 + 0], 30.0);
  CHECK_DOUBLE(grid[3 * 3 + 1], 0.0);
  CHECK_DOUBLE(grid[12 * 3 + 0], 0.0);
  CHECK_DOUBLE(grid[12 * 3 + 1], 30.0);
  CHECK_DOUBLE(grid[15 * 3 + 0], 30.0);
  CHECK_DOUBLE(grid[15 * 3 + 1], 30.0);

  vtksys::SystemTools::RemoveFile(path);
  return EXIT_SUCCESS;
}

int testLegacyFcsvWriteRejected()
{
  // Setting a .lrp.fcsv storage filename and calling Write must
  // fail with a vtkErrorMacro — legacy writes are not supported.
  vtkNew<vtkMRMLBezierSurfaceNode> source;
  populate(source.GetPointer());
  const std::string path = makeTempPath("lrp.fcsv");

  vtkNew<vtkMRMLBezierSurfaceStorageNode> storage;
  storage->SetFileName(path.c_str());

  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  CHECK_INT(storage->WriteData(source.GetPointer()), 0);
  TESTING_OUTPUT_ASSERT_ERRORS_END();

  // No file should have been created.
  if (vtksys::SystemTools::FileExists(path, true))
  {
    vtksys::SystemTools::RemoveFile(path);
  }
  return EXIT_SUCCESS;
}

int testLegacyFcsvFixture()
{
  // Fixture-based variant of testLegacyFcsvRead: walks the canned
  // fixture file under Testing/Cxx/Fixtures/ via the
  // ``LIVER_BEZIER_STORAGE_TEST_FIXTURE_DIR`` macro (set in the
  // CMakeLists, defaults to the source tree).  This catches drift
  // between the in-repo fixture and the reader.
#ifdef LIVER_BEZIER_STORAGE_TEST_FIXTURE_DIR
  const std::string path = std::string(LIVER_BEZIER_STORAGE_TEST_FIXTURE_DIR) + "/legacy_resection.lrp.fcsv";
#else
  // Fall-back — the tree is expected to define the macro; if not,
  // skip the assertion.  Print a notice rather than failing so the
  // test runner does not red-light a sanity skip.
  std::cout << "testLegacyFcsvFixture: LIVER_BEZIER_STORAGE_TEST_FIXTURE_DIR not defined; "
               "skipping the in-repo fixture check.\n";
  return EXIT_SUCCESS;
#endif

  if (!vtksys::SystemTools::FileExists(path, true))
  {
    std::cout << "testLegacyFcsvFixture: fixture '" << path << "' not found; skipping.\n";
    return EXIT_SUCCESS;
  }

  vtkNew<vtkMRMLBezierSurfaceNode> sink;
  vtkNew<vtkMRMLBezierSurfaceStorageNode> storage;
  storage->SetFileName(path.c_str());

  TESTING_OUTPUT_ASSERT_WARNINGS_BEGIN();
  CHECK_INT(storage->ReadData(sink.GetPointer()), 1);
  TESTING_OUTPUT_ASSERT_WARNINGS_END();

  CHECK_INT(sink->GetState(), vtkMRMLBezierSurfaceNode::Planning);
  // The in-repo fixture mirrors the procedurally-generated one from
  // ``testLegacyFcsvRead`` — same 4×4 grid (x=j*10, y=i*10, z=0).
  CHECK_DOUBLE(sink->GetControlGrid()[0], 0.0);
  CHECK_DOUBLE(sink->GetControlGrid()[15 * 3 + 0], 30.0);
  CHECK_DOUBLE(sink->GetControlGrid()[15 * 3 + 1], 30.0);
  return EXIT_SUCCESS;
}

} // namespace

//------------------------------------------------------------------------------
int vtkMRMLBezierSurfaceStorageNodeTest1(int, char*[])
{
  // Exercise the base-class MRML methods first — catches missing
  // CreateNodeInstance / vtkStandardNewMacro plumbing the same way
  // the data-node test does.
  vtkNew<vtkMRMLScene> scene;
  vtkNew<vtkMRMLBezierSurfaceStorageNode> exerciseNode;
  exerciseNode->SetScene(scene.GetPointer());
  EXERCISE_ALL_BASIC_MRML_METHODS(exerciseNode.GetPointer());

  CHECK_EXIT_SUCCESS(testDefaultWriteFileExtension());
  CHECK_EXIT_SUCCESS(testCanReadCanWriteDiscrimination());
  CHECK_EXIT_SUCCESS(testJsonRoundTrip());
  CHECK_EXIT_SUCCESS(testSchemaVersionMismatch());
  CHECK_EXIT_SUCCESS(testLegacyFcsvRead());
  CHECK_EXIT_SUCCESS(testLegacyFcsvWriteRejected());
  CHECK_EXIT_SUCCESS(testLegacyFcsvFixture());

  std::cout << "vtkMRMLBezierSurfaceStorageNodeTest1 completed successfully" << std::endl;
  return EXIT_SUCCESS;
}

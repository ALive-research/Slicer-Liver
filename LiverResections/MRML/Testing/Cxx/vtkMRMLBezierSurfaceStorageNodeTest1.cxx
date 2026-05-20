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
#include "vtkMRMLNurbsSurfaceNode.h"
#include "vtkMRMLNurbsSurfaceStorageNode.h"

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

int testConfirmedStateRoundTrip()
{
  // ADR-0019: ``Confirmed`` is the third state and round-trips
  // through .lrp.json the same way Planning does — schemaVersion is
  // unchanged (still 1), only the enum-string set grows.
  vtkNew<vtkMRMLBezierSurfaceNode> source;
  populate(source.GetPointer());
  // ``populate`` leaves the source in Planning; advance to Confirmed
  // for this test.  Planning -> Confirmed is the legal forward edge.
  source->SetState(vtkMRMLBezierSurfaceNode::Confirmed);

  const std::string path = makeTempPath("lrp.json");
  vtkNew<vtkMRMLBezierSurfaceStorageNode> writeStorage;
  writeStorage->SetFileName(path.c_str());
  CHECK_INT(writeStorage->WriteData(source.GetPointer()), 1);

  vtkNew<vtkMRMLBezierSurfaceNode> sink;
  vtkNew<vtkMRMLBezierSurfaceStorageNode> readStorage;
  readStorage->SetFileName(path.c_str());
  CHECK_INT(readStorage->ReadData(sink.GetPointer()), 1);

  CHECK_INT(sink->GetState(), vtkMRMLBezierSurfaceNode::Confirmed);
  // Control grid carried across the round-trip in Confirmed (the
  // serialiser does not gate on state).
  for (int i = 0; i < vtkMRMLBezierSurfaceNode::ControlGridSize; ++i)
  {
    CHECK_DOUBLE_TOLERANCE(sink->GetControlGrid()[i], source->GetControlGrid()[i], 1e-9);
  }

  vtksys::SystemTools::RemoveFile(path);
  return EXIT_SUCCESS;
}

int testUnknownStateFallback()
{
  // ADR-0019 §"Storage / persistence": an unknown ``state`` value
  // falls back to ``Planning`` gracefully — exercises the forward-
  // compatible default for scenes authored by a future build that
  // adds a fourth state (or a build that pre-dates this PR loading
  // a v3-authored "Confirmed" scene, which the test simulates by
  // writing an unknown name directly).
  const std::string path = makeTempPath("lrp.json");
  {
    std::ofstream ofs(path);
    ofs << "{\n";
    ofs << "  \"schemaVersion\": 1,\n";
    ofs << "  \"state\": \"Approved\",\n";
    ofs << "  \"initMode\": \"SlicingPlane\"\n";
    ofs << "}\n";
  }

  vtkNew<vtkMRMLBezierSurfaceNode> sink;
  vtkNew<vtkMRMLBezierSurfaceStorageNode> storage;
  storage->SetFileName(path.c_str());

  // The fallback emits a vtkWarningMacro by design (visible audit
  // trail for the unknown-state degrade).
  TESTING_OUTPUT_ASSERT_WARNINGS_BEGIN();
  CHECK_INT(storage->ReadData(sink.GetPointer()), 1);
  TESTING_OUTPUT_ASSERT_WARNINGS_END();
  CHECK_INT(sink->GetState(), vtkMRMLBezierSurfaceNode::Planning);

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

int testJsonRoundTrip3x3()
{
  // ADR-0018 §1 — 3×3 round-trip.  Writer always emits schema v2
  // with explicit rows + cols (3, 3) and a 27-double controlGrid.
  // Reader resolves rows/cols on parse + matches the controlGrid
  // length.  Mirrors testJsonRoundTrip for the 3×3 case.
  vtkNew<vtkMRMLBezierSurfaceNode> source;
  source->SetSize(3);
  source->SetState(vtkMRMLBezierSurfaceNode::Planning);
  double grid33[27];
  for (int i = 0; i < 27; ++i)
  {
    grid33[i] = static_cast<double>(i) * 0.375 - 0.5;
  }
  source->SetControlGrid(grid33);

  const std::string path = makeTempPath("lrp.json");
  vtkNew<vtkMRMLBezierSurfaceStorageNode> writeStorage;
  writeStorage->SetFileName(path.c_str());
  CHECK_INT(writeStorage->WriteData(source.GetPointer()), 1);

  vtkNew<vtkMRMLBezierSurfaceNode> sink;
  vtkNew<vtkMRMLBezierSurfaceStorageNode> readStorage;
  readStorage->SetFileName(path.c_str());
  CHECK_INT(readStorage->ReadData(sink.GetPointer()), 1);

  CHECK_INT(static_cast<int>(sink->GetRows()), 3);
  CHECK_INT(static_cast<int>(sink->GetCols()), 3);
  CHECK_INT(static_cast<int>(sink->GetControlGridLength()), 27);
  for (int i = 0; i < 27; ++i)
  {
    CHECK_DOUBLE_TOLERANCE(sink->GetControlGrid()[i], grid33[i], 1e-9);
  }

  // Spot-check the on-disk JSON carries the explicit shape +
  // discriminator — per ADR-0022 §"Decision 2 — Schema v3" the
  // writer always emits ``schemaVersion: 3`` + ``surfaceType:
  // "Bezier"`` + explicit ``rows`` / ``cols``.
  std::ifstream f(path);
  std::stringstream ss;
  ss << f.rdbuf();
  const std::string contents = ss.str();
  if (contents.find("\"schemaVersion\":3") == std::string::npos && contents.find("\"schemaVersion\": 3") == std::string::npos)
  {
    std::cerr << "Expected schemaVersion: 3 in output JSON\n" << contents << "\n";
    return EXIT_FAILURE;
  }
  if (contents.find("\"surfaceType\":\"Bezier\"") == std::string::npos && contents.find("\"surfaceType\": \"Bezier\"") == std::string::npos)
  {
    std::cerr << "Expected surfaceType: \"Bezier\" in output JSON\n" << contents << "\n";
    return EXIT_FAILURE;
  }
  if (contents.find("\"rows\":3") == std::string::npos && contents.find("\"rows\": 3") == std::string::npos)
  {
    std::cerr << "Expected \"rows\": 3 in output JSON\n" << contents << "\n";
    return EXIT_FAILURE;
  }

  vtksys::SystemTools::RemoveFile(path);
  return EXIT_SUCCESS;
}

int testJsonReadV1Implicit4x4()
{
  // ADR-0018 §1 — Reader must accept v1 files (no rows / cols
  // fields; implicit 4×4 control polygon) and load them as a 4×4
  // node.  This is the migration path for existing on-disk plans.
  const std::string path = makeTempPath("lrp.json");
  {
    std::ofstream ofs(path);
    ofs << "{\n";
    ofs << "  \"schemaVersion\": 1,\n";
    ofs << "  \"state\": \"Planning\",\n";
    ofs << "  \"initMode\": \"SlicingPlane\",\n";
    ofs << "  \"controlGrid\": [";
    for (int i = 0; i < 48; ++i)
    {
      if (i > 0)
      {
        ofs << ", ";
      }
      ofs << (static_cast<double>(i) * 0.0625);
    }
    ofs << "],\n";
    ofs << "  \"slicingPlane\": { \"origin\": [0, 0, 0], \"normal\": [0, 0, 1], \"initPointsFlat\": [0, 0, 0, 0, 0, 0] },\n";
    ofs << "  \"distanceSpheroid\": { \"center\": [0, 0, 0], \"radius\": {\"x\": 0, \"y\": 0, \"z\": 0}, \"numberOfInitPoints\": 0, \"initPointsFlat\": [] },\n";
    ofs << "  \"metadata\": {}\n";
    ofs << "}\n";
  }

  vtkNew<vtkMRMLBezierSurfaceNode> sink;
  vtkNew<vtkMRMLBezierSurfaceStorageNode> storage;
  storage->SetFileName(path.c_str());
  CHECK_INT(storage->ReadData(sink.GetPointer()), 1);

  // v1 → 4×4 inference.
  CHECK_INT(static_cast<int>(sink->GetRows()), 4);
  CHECK_INT(static_cast<int>(sink->GetCols()), 4);
  CHECK_INT(static_cast<int>(sink->GetControlGridLength()), 48);
  for (int i = 0; i < 48; ++i)
  {
    CHECK_DOUBLE_TOLERANCE(sink->GetControlGrid()[i], static_cast<double>(i) * 0.0625, 1e-9);
  }

  vtksys::SystemTools::RemoveFile(path);
  return EXIT_SUCCESS;
}

int testJsonReadV2InvalidShape()
{
  // ADR-0018 §1 — Reader rejects non-square + out-of-range shapes
  // explicitly.  Crafts a v2 JSON with rows=3, cols=4 (non-square)
  // and confirms the read fails with a vtkErrorMacro.
  const std::string path = makeTempPath("lrp.json");
  {
    std::ofstream ofs(path);
    ofs << "{\n";
    ofs << "  \"schemaVersion\": 2,\n";
    ofs << "  \"state\": \"Init\",\n";
    ofs << "  \"initMode\": \"SlicingPlane\",\n";
    ofs << "  \"rows\": 3,\n";
    ofs << "  \"cols\": 4,\n";
    ofs << "  \"controlGrid\": [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35]\n";
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

int testJsonReadV2OutOfRange()
{
  // ADR-0018 §1 — Reader rejects out-of-range square shapes (the
  // sibling of testJsonReadV2InvalidShape, which pins the non-square
  // branch).  Crafts a v2 JSON with rows=cols=5 (square but outside
  // ``{(3, 3), (4, 4)}``) plus a 75-double controlGrid and confirms
  // the read fails with a vtkErrorMacro before the controlGrid is
  // even parsed.
  const std::string path = makeTempPath("lrp.json");
  {
    std::ofstream ofs(path);
    ofs << "{\n";
    ofs << "  \"schemaVersion\": 2,\n";
    ofs << "  \"state\": \"Init\",\n";
    ofs << "  \"initMode\": \"SlicingPlane\",\n";
    ofs << "  \"rows\": 5,\n";
    ofs << "  \"cols\": 5,\n";
    ofs << "  \"controlGrid\": [";
    for (int i = 0; i < 75; ++i)
    {
      if (i > 0)
      {
        ofs << ", ";
      }
      ofs << static_cast<double>(i);
    }
    ofs << "]\n";
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

int testJsonReadV2ControlGridLengthMismatch()
{
  // ADR-0018 §1 — Reader rejects a v2 file whose ``controlGrid``
  // length does not match ``3 * rows * cols``.  Two sub-cases:
  //   a) shape 4×4 (expects 48), grid 27 doubles → reject
  //   b) shape 3×3 (expects 27), grid 48 doubles → reject
  // Both hit the controlGrid-array-length validation branch in
  // vtkMRMLBezierSurfaceStorageNode::ReadJson (the one that calls
  // ``vtkErrorMacro`` when the array length disagrees with the
  // resolved ``Rows * Cols * 3``).
  {
    const std::string path = makeTempPath("lrp.json");
    {
      std::ofstream ofs(path);
      ofs << "{\n";
      ofs << "  \"schemaVersion\": 2,\n";
      ofs << "  \"state\": \"Init\",\n";
      ofs << "  \"initMode\": \"SlicingPlane\",\n";
      ofs << "  \"rows\": 4,\n";
      ofs << "  \"cols\": 4,\n";
      ofs << "  \"controlGrid\": [";
      for (int i = 0; i < 27; ++i)
      {
        if (i > 0)
        {
          ofs << ", ";
        }
        ofs << static_cast<double>(i);
      }
      ofs << "]\n";
      ofs << "}\n";
    }

    vtkNew<vtkMRMLBezierSurfaceNode> sink;
    vtkNew<vtkMRMLBezierSurfaceStorageNode> storage;
    storage->SetFileName(path.c_str());

    TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
    CHECK_INT(storage->ReadData(sink.GetPointer()), 0);
    TESTING_OUTPUT_ASSERT_ERRORS_END();

    vtksys::SystemTools::RemoveFile(path);
  }

  // Symmetric case: rows=3, cols=3 (expects 27), grid 48 doubles.
  {
    const std::string path = makeTempPath("lrp.json");
    {
      std::ofstream ofs(path);
      ofs << "{\n";
      ofs << "  \"schemaVersion\": 2,\n";
      ofs << "  \"state\": \"Init\",\n";
      ofs << "  \"initMode\": \"SlicingPlane\",\n";
      ofs << "  \"rows\": 3,\n";
      ofs << "  \"cols\": 3,\n";
      ofs << "  \"controlGrid\": [";
      for (int i = 0; i < 48; ++i)
      {
        if (i > 0)
        {
          ofs << ", ";
        }
        ofs << static_cast<double>(i);
      }
      ofs << "]\n";
      ofs << "}\n";
    }

    vtkNew<vtkMRMLBezierSurfaceNode> sink;
    vtkNew<vtkMRMLBezierSurfaceStorageNode> storage;
    storage->SetFileName(path.c_str());

    TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
    CHECK_INT(storage->ReadData(sink.GetPointer()), 0);
    TESTING_OUTPUT_ASSERT_ERRORS_END();

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

//==============================================================================
// v2.1 NURBS sibling tests (ADR-0022 §"Decision 2 — Schema v3" /
// §"Reader compat matrix" / §"Validation rules per surface type").
//==============================================================================

/// Populate a NURBS surface node with deterministic, distinctive
/// values touching every IVar the storage path round-trips.  The
/// shape is rectangular + degrees asymmetric so the test catches any
/// (rows ↔ cols) or (degreeU ↔ degreeV) swap in the read/write path.
void populateNurbs(vtkMRMLNurbsSurfaceNode* node)
{
  // Drop degrees to (2, 3) so the (5, 4) shape is legal — need
  // rows >= degreeU + 1 (5 >= 3) AND cols >= degreeV + 1 (4 >= 4).
  node->SetDegreeU(2);
  // DegreeV stays at default 3.
  node->SetRows(5);
  // SetCols(4) would be the default; do not assert here (this
  // helper is ``void`` — callers check the round-trip post-condition
  // via the public sink getters).

  // Control grid — 3 * 5 * 4 = 60 doubles.
  double grid[60];
  for (int i = 0; i < 60; ++i)
  {
    grid[i] = static_cast<double>(i) * 0.125 + 0.0625;
  }
  node->SetControlGrid(grid);

  // Weights — 5 * 4 = 20 doubles, all positive.
  double weights[20];
  for (int i = 0; i < 20; ++i)
  {
    weights[i] = 0.5 + static_cast<double>(i) * 0.05;
  }
  node->SetWeights(weights, 20);

  // Hand-rolled knot vectors — overwrite the clamped-uniform
  // defaults with a slightly different valid clamped vector to
  // catch any "writer ignores knot edits + emits defaults" bug.
  // KnotsU: length 5 + 2 + 1 = 8.  Clamped at both ends with
  // three interior knots.
  double knotsU[8] = { 0.0, 0.0, 0.0, 0.25, 0.6, 1.0, 1.0, 1.0 };
  node->SetKnotsU(knotsU, 8);
  // KnotsV: length 4 + 3 + 1 = 8.  Clamped at both ends with no
  // interior knots (the degree-3, rows=degree+1 degenerate case).
  double knotsV[8] = { 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0 };
  node->SetKnotsV(knotsV, 8);

  node->SetInitMode(vtkMRMLNurbsSurfaceNode::DistanceSpheroid);
  node->SetState(vtkMRMLNurbsSurfaceNode::Planning);
}

int testJsonRoundTripNurbs()
{
  vtkNew<vtkMRMLNurbsSurfaceNode> source;
  populateNurbs(source.GetPointer());

  const std::string path = makeTempPath("lrp.json");
  vtkNew<vtkMRMLNurbsSurfaceStorageNode> writeStorage;
  writeStorage->SetFileName(path.c_str());
  CHECK_INT(writeStorage->WriteData(source.GetPointer()), 1);

  vtkNew<vtkMRMLNurbsSurfaceNode> sink;
  vtkNew<vtkMRMLNurbsSurfaceStorageNode> readStorage;
  readStorage->SetFileName(path.c_str());
  CHECK_INT(readStorage->ReadData(sink.GetPointer()), 1);

  // Shape + degrees round-trip.
  CHECK_INT(static_cast<int>(sink->GetRows()), 5);
  CHECK_INT(static_cast<int>(sink->GetCols()), 4);
  CHECK_INT(static_cast<int>(sink->GetDegreeU()), 2);
  CHECK_INT(static_cast<int>(sink->GetDegreeV()), 3);
  CHECK_INT(sink->GetState(), vtkMRMLNurbsSurfaceNode::Planning);
  CHECK_INT(sink->GetInitMode(), vtkMRMLNurbsSurfaceNode::DistanceSpheroid);

  // Control grid round-trip (3 * 5 * 4 = 60 doubles).
  for (int i = 0; i < 60; ++i)
  {
    CHECK_DOUBLE_TOLERANCE(sink->GetControlGrid()[i], source->GetControlGrid()[i], 1e-9);
  }

  // Knots + weights round-trip.
  for (unsigned int i = 0; i < sink->GetKnotsULength(); ++i)
  {
    CHECK_DOUBLE_TOLERANCE(sink->GetKnotsU()[i], source->GetKnotsU()[i], 1e-9);
  }
  for (unsigned int i = 0; i < sink->GetKnotsVLength(); ++i)
  {
    CHECK_DOUBLE_TOLERANCE(sink->GetKnotsV()[i], source->GetKnotsV()[i], 1e-9);
  }
  for (unsigned int i = 0; i < sink->GetWeightsLength(); ++i)
  {
    CHECK_DOUBLE_TOLERANCE(sink->GetWeights()[i], source->GetWeights()[i], 1e-9);
  }

  // Spot-check the on-disk JSON for the v3 markers.
  std::ifstream f(path);
  std::stringstream ss;
  ss << f.rdbuf();
  const std::string contents = ss.str();
  if (contents.find("\"schemaVersion\":3") == std::string::npos && contents.find("\"schemaVersion\": 3") == std::string::npos)
  {
    std::cerr << "Expected schemaVersion: 3 in NURBS output JSON\n" << contents << "\n";
    return EXIT_FAILURE;
  }
  if (contents.find("\"surfaceType\":\"NURBS\"") == std::string::npos && contents.find("\"surfaceType\": \"NURBS\"") == std::string::npos)
  {
    std::cerr << "Expected surfaceType: \"NURBS\" in output JSON\n" << contents << "\n";
    return EXIT_FAILURE;
  }
  if (contents.find("\"degreeU\":2") == std::string::npos && contents.find("\"degreeU\": 2") == std::string::npos)
  {
    std::cerr << "Expected degreeU: 2 in output JSON\n" << contents << "\n";
    return EXIT_FAILURE;
  }
  if (contents.find("\"weights\"") == std::string::npos)
  {
    std::cerr << "Expected weights field in output JSON\n" << contents << "\n";
    return EXIT_FAILURE;
  }

  vtksys::SystemTools::RemoveFile(path);
  return EXIT_SUCCESS;
}

int testJsonReadV3BezierExplicit()
{
  // ADR-0022 §"Reader compat matrix": v3 + surfaceType "Bezier"
  // loads via the Bezier path the same as v2 with the discriminator
  // made explicit.  Synthesize a minimal v3 Bezier file and
  // validate.
  const std::string path = makeTempPath("lrp.json");
  {
    std::ofstream ofs(path);
    ofs << "{\n";
    ofs << "  \"schemaVersion\": 3,\n";
    ofs << "  \"surfaceType\": \"Bezier\",\n";
    ofs << "  \"state\": \"Planning\",\n";
    ofs << "  \"initMode\": \"SlicingPlane\",\n";
    ofs << "  \"rows\": 4,\n";
    ofs << "  \"cols\": 4,\n";
    ofs << "  \"controlGrid\": [";
    for (int i = 0; i < 48; ++i)
    {
      if (i > 0)
      {
        ofs << ", ";
      }
      ofs << (static_cast<double>(i) * 0.25);
    }
    ofs << "]\n";
    ofs << "}\n";
  }

  vtkNew<vtkMRMLBezierSurfaceNode> sink;
  vtkNew<vtkMRMLBezierSurfaceStorageNode> storage;
  storage->SetFileName(path.c_str());
  CHECK_INT(storage->ReadData(sink.GetPointer()), 1);

  CHECK_INT(static_cast<int>(sink->GetRows()), 4);
  CHECK_INT(static_cast<int>(sink->GetCols()), 4);
  CHECK_INT(sink->GetState(), vtkMRMLBezierSurfaceNode::Planning);
  for (int i = 0; i < 48; ++i)
  {
    CHECK_DOUBLE_TOLERANCE(sink->GetControlGrid()[i], static_cast<double>(i) * 0.25, 1e-9);
  }

  vtksys::SystemTools::RemoveFile(path);
  return EXIT_SUCCESS;
}

int testJsonReadV3NurbsInvalidDegree()
{
  // ADR-0022 §"Validation rules per surface type — NURBS": degree
  // out of {2, 3} is rejected with vtkErrorMacro.  Cover both
  // edges: degreeU=1 and degreeU=4.
  auto write = [](const std::string& p, int degreeU)
  {
    std::ofstream ofs(p);
    ofs << "{\n";
    ofs << "  \"schemaVersion\": 3,\n";
    ofs << "  \"surfaceType\": \"NURBS\",\n";
    ofs << "  \"state\": \"Init\",\n";
    ofs << "  \"initMode\": \"SlicingPlane\",\n";
    ofs << "  \"rows\": 4,\n";
    ofs << "  \"cols\": 4,\n";
    ofs << "  \"degreeU\": " << degreeU << ",\n";
    ofs << "  \"degreeV\": 3,\n";
    ofs << "  \"knotsU\": [0,0,0,0,1,1,1,1],\n";
    ofs << "  \"knotsV\": [0,0,0,0,1,1,1,1],\n";
    ofs << "  \"weights\": [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],\n";
    ofs << "  \"controlGrid\": [";
    for (int i = 0; i < 48; ++i)
    {
      if (i > 0)
      {
        ofs << ", ";
      }
      ofs << static_cast<double>(i);
    }
    ofs << "]\n";
    ofs << "}\n";
  };

  for (int badDegree : { 1, 4 })
  {
    const std::string path = makeTempPath("lrp.json");
    write(path, badDegree);

    vtkNew<vtkMRMLNurbsSurfaceNode> sink;
    vtkNew<vtkMRMLNurbsSurfaceStorageNode> storage;
    storage->SetFileName(path.c_str());
    TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
    CHECK_INT(storage->ReadData(sink.GetPointer()), 0);
    TESTING_OUTPUT_ASSERT_ERRORS_END();

    vtksys::SystemTools::RemoveFile(path);
  }
  return EXIT_SUCCESS;
}

int testJsonReadV3NurbsInvalidKnotsLength()
{
  // ADR-0022 §"Validation rules per surface type — NURBS":
  // ``len(knotsU) == rows + degreeU + 1`` (8 for the 4×4 / deg 3
  // case).  Send a too-short knotsU and confirm rejection.
  const std::string path = makeTempPath("lrp.json");
  {
    std::ofstream ofs(path);
    ofs << "{\n";
    ofs << "  \"schemaVersion\": 3,\n";
    ofs << "  \"surfaceType\": \"NURBS\",\n";
    ofs << "  \"state\": \"Init\",\n";
    ofs << "  \"initMode\": \"SlicingPlane\",\n";
    ofs << "  \"rows\": 4,\n";
    ofs << "  \"cols\": 4,\n";
    ofs << "  \"degreeU\": 3,\n";
    ofs << "  \"degreeV\": 3,\n";
    ofs << "  \"knotsU\": [0,0,0,1,1,1],\n"; // length 6, not 8
    ofs << "  \"knotsV\": [0,0,0,0,1,1,1,1],\n";
    ofs << "  \"weights\": [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],\n";
    ofs << "  \"controlGrid\": [";
    for (int i = 0; i < 48; ++i)
    {
      if (i > 0)
      {
        ofs << ", ";
      }
      ofs << static_cast<double>(i);
    }
    ofs << "]\n";
    ofs << "}\n";
  }

  vtkNew<vtkMRMLNurbsSurfaceNode> sink;
  vtkNew<vtkMRMLNurbsSurfaceStorageNode> storage;
  storage->SetFileName(path.c_str());
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  CHECK_INT(storage->ReadData(sink.GetPointer()), 0);
  TESTING_OUTPUT_ASSERT_ERRORS_END();

  vtksys::SystemTools::RemoveFile(path);
  return EXIT_SUCCESS;
}

int testJsonReadV3NurbsInvalidWeights()
{
  // ADR-0022 §"Validation rules per surface type — NURBS":
  // - weight must be strictly positive
  // - len(weights) == rows * cols
  // Cover both: a zero / negative entry + a wrong-length array.

  // Sub-case (a): one zero weight.
  {
    const std::string path = makeTempPath("lrp.json");
    {
      std::ofstream ofs(path);
      ofs << "{\n";
      ofs << "  \"schemaVersion\": 3,\n";
      ofs << "  \"surfaceType\": \"NURBS\",\n";
      ofs << "  \"state\": \"Init\",\n";
      ofs << "  \"initMode\": \"SlicingPlane\",\n";
      ofs << "  \"rows\": 4,\n";
      ofs << "  \"cols\": 4,\n";
      ofs << "  \"degreeU\": 3,\n";
      ofs << "  \"degreeV\": 3,\n";
      ofs << "  \"knotsU\": [0,0,0,0,1,1,1,1],\n";
      ofs << "  \"knotsV\": [0,0,0,0,1,1,1,1],\n";
      // Index 7 is zero — a singular weight in NURBS.
      ofs << "  \"weights\": [1,1,1,1,1,1,1,0,1,1,1,1,1,1,1,1],\n";
      ofs << "  \"controlGrid\": [";
      for (int i = 0; i < 48; ++i)
      {
        if (i > 0)
        {
          ofs << ", ";
        }
        ofs << static_cast<double>(i);
      }
      ofs << "]\n";
      ofs << "}\n";
    }

    vtkNew<vtkMRMLNurbsSurfaceNode> sink;
    vtkNew<vtkMRMLNurbsSurfaceStorageNode> storage;
    storage->SetFileName(path.c_str());
    TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
    CHECK_INT(storage->ReadData(sink.GetPointer()), 0);
    TESTING_OUTPUT_ASSERT_ERRORS_END();

    vtksys::SystemTools::RemoveFile(path);
  }

  // Sub-case (b): negative weight.
  {
    const std::string path = makeTempPath("lrp.json");
    {
      std::ofstream ofs(path);
      ofs << "{\n";
      ofs << "  \"schemaVersion\": 3,\n";
      ofs << "  \"surfaceType\": \"NURBS\",\n";
      ofs << "  \"state\": \"Init\",\n";
      ofs << "  \"initMode\": \"SlicingPlane\",\n";
      ofs << "  \"rows\": 4,\n";
      ofs << "  \"cols\": 4,\n";
      ofs << "  \"degreeU\": 3,\n";
      ofs << "  \"degreeV\": 3,\n";
      ofs << "  \"knotsU\": [0,0,0,0,1,1,1,1],\n";
      ofs << "  \"knotsV\": [0,0,0,0,1,1,1,1],\n";
      ofs << "  \"weights\": [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,-0.5],\n";
      ofs << "  \"controlGrid\": [";
      for (int i = 0; i < 48; ++i)
      {
        if (i > 0)
        {
          ofs << ", ";
        }
        ofs << static_cast<double>(i);
      }
      ofs << "]\n";
      ofs << "}\n";
    }

    vtkNew<vtkMRMLNurbsSurfaceNode> sink;
    vtkNew<vtkMRMLNurbsSurfaceStorageNode> storage;
    storage->SetFileName(path.c_str());
    TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
    CHECK_INT(storage->ReadData(sink.GetPointer()), 0);
    TESTING_OUTPUT_ASSERT_ERRORS_END();

    vtksys::SystemTools::RemoveFile(path);
  }

  // Sub-case (c): wrong length (8 instead of 16).
  {
    const std::string path = makeTempPath("lrp.json");
    {
      std::ofstream ofs(path);
      ofs << "{\n";
      ofs << "  \"schemaVersion\": 3,\n";
      ofs << "  \"surfaceType\": \"NURBS\",\n";
      ofs << "  \"state\": \"Init\",\n";
      ofs << "  \"initMode\": \"SlicingPlane\",\n";
      ofs << "  \"rows\": 4,\n";
      ofs << "  \"cols\": 4,\n";
      ofs << "  \"degreeU\": 3,\n";
      ofs << "  \"degreeV\": 3,\n";
      ofs << "  \"knotsU\": [0,0,0,0,1,1,1,1],\n";
      ofs << "  \"knotsV\": [0,0,0,0,1,1,1,1],\n";
      ofs << "  \"weights\": [1,1,1,1,1,1,1,1],\n"; // length 8, not 16
      ofs << "  \"controlGrid\": [";
      for (int i = 0; i < 48; ++i)
      {
        if (i > 0)
        {
          ofs << ", ";
        }
        ofs << static_cast<double>(i);
      }
      ofs << "]\n";
      ofs << "}\n";
    }

    vtkNew<vtkMRMLNurbsSurfaceNode> sink;
    vtkNew<vtkMRMLNurbsSurfaceStorageNode> storage;
    storage->SetFileName(path.c_str());
    TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
    CHECK_INT(storage->ReadData(sink.GetPointer()), 0);
    TESTING_OUTPUT_ASSERT_ERRORS_END();

    vtksys::SystemTools::RemoveFile(path);
  }
  return EXIT_SUCCESS;
}

int testJsonReadV3NurbsInvalidShape()
{
  // ADR-0022 §"Validation rules per surface type — NURBS":
  // rows < degreeU + 1 (or cols < degreeV + 1) leaves the basis
  // empty — rejected.
  const std::string path = makeTempPath("lrp.json");
  {
    std::ofstream ofs(path);
    ofs << "{\n";
    ofs << "  \"schemaVersion\": 3,\n";
    ofs << "  \"surfaceType\": \"NURBS\",\n";
    ofs << "  \"state\": \"Init\",\n";
    ofs << "  \"initMode\": \"SlicingPlane\",\n";
    ofs << "  \"rows\": 3,\n"; // < degreeU + 1 = 4 → invalid
    ofs << "  \"cols\": 4,\n";
    ofs << "  \"degreeU\": 3,\n";
    ofs << "  \"degreeV\": 3,\n";
    ofs << "  \"knotsU\": [0,0,0,0,1,1,1],\n";
    ofs << "  \"knotsV\": [0,0,0,0,1,1,1,1],\n";
    ofs << "  \"weights\": [1,1,1,1,1,1,1,1,1,1,1,1],\n";
    ofs << "  \"controlGrid\": [";
    for (int i = 0; i < 36; ++i)
    {
      if (i > 0)
      {
        ofs << ", ";
      }
      ofs << static_cast<double>(i);
    }
    ofs << "]\n";
    ofs << "}\n";
  }

  vtkNew<vtkMRMLNurbsSurfaceNode> sink;
  vtkNew<vtkMRMLNurbsSurfaceStorageNode> storage;
  storage->SetFileName(path.c_str());
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  CHECK_INT(storage->ReadData(sink.GetPointer()), 0);
  TESTING_OUTPUT_ASSERT_ERRORS_END();

  vtksys::SystemTools::RemoveFile(path);
  return EXIT_SUCCESS;
}

int testWriterAlwaysEmitsV3Bezier()
{
  // ADR-0022 §"Decision 2 — Schema v3": writer always emits v3 +
  // ``surfaceType`` even for the (legacy) 4×4 Bezier case.  Round-
  // trip a default-populated Bezier surface and assert the v3
  // markers are present on disk.
  vtkNew<vtkMRMLBezierSurfaceNode> source;
  source->SetState(vtkMRMLBezierSurfaceNode::Planning);
  double grid[48];
  for (int i = 0; i < 48; ++i)
  {
    grid[i] = static_cast<double>(i);
  }
  source->SetControlGrid(grid);

  const std::string path = makeTempPath("lrp.json");
  vtkNew<vtkMRMLBezierSurfaceStorageNode> storage;
  storage->SetFileName(path.c_str());
  CHECK_INT(storage->WriteData(source.GetPointer()), 1);

  std::ifstream f(path);
  std::stringstream ss;
  ss << f.rdbuf();
  const std::string contents = ss.str();
  if (contents.find("\"schemaVersion\":3") == std::string::npos && contents.find("\"schemaVersion\": 3") == std::string::npos)
  {
    std::cerr << "Expected schemaVersion: 3 in writer output\n" << contents << "\n";
    return EXIT_FAILURE;
  }
  if (contents.find("\"surfaceType\":\"Bezier\"") == std::string::npos && contents.find("\"surfaceType\": \"Bezier\"") == std::string::npos)
  {
    std::cerr << "Expected surfaceType: \"Bezier\" in writer output\n" << contents << "\n";
    return EXIT_FAILURE;
  }
  // NURBS-only fields are absent.
  if (contents.find("degreeU") != std::string::npos)
  {
    std::cerr << "Bezier writer output should NOT contain 'degreeU'\n" << contents << "\n";
    return EXIT_FAILURE;
  }
  if (contents.find("\"weights\"") != std::string::npos)
  {
    std::cerr << "Bezier writer output should NOT contain 'weights'\n" << contents << "\n";
    return EXIT_FAILURE;
  }

  vtksys::SystemTools::RemoveFile(path);
  return EXIT_SUCCESS;
}

int testJsonReadInvalidSurfaceType()
{
  // ADR-0022 §"Decision 2 — Schema v3": ``surfaceType`` is closed at
  // {"Bezier", "NURBS"}.  An unrecognised value (e.g. "Catmull"
  // emitted by a future / third-party tool) must be rejected at the
  // read boundary so the data node never sees a malformed file.
  // ``ReadDataInternal`` dispatches on the reference-node type — both
  // dispatch arms (Bezier path + NURBS path) check the discriminator
  // and reject the foreign value.

  // Sub-case (a): NURBS reference + "Catmull" surfaceType → reject
  // (ReadJsonNurbs rejects any non-"NURBS" value).
  {
    const std::string path = makeTempPath("lrp.json");
    {
      std::ofstream ofs(path);
      ofs << "{\n";
      ofs << "  \"schemaVersion\": 3,\n";
      ofs << "  \"surfaceType\": \"Catmull\",\n";
      ofs << "  \"state\": \"Init\",\n";
      ofs << "  \"initMode\": \"SlicingPlane\",\n";
      ofs << "  \"rows\": 4,\n";
      ofs << "  \"cols\": 4,\n";
      ofs << "  \"degreeU\": 3,\n";
      ofs << "  \"degreeV\": 3,\n";
      ofs << "  \"knotsU\": [0,0,0,0,1,1,1,1],\n";
      ofs << "  \"knotsV\": [0,0,0,0,1,1,1,1],\n";
      ofs << "  \"weights\": [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],\n";
      ofs << "  \"controlGrid\": [";
      for (int i = 0; i < 48; ++i)
      {
        if (i > 0)
        {
          ofs << ", ";
        }
        ofs << static_cast<double>(i);
      }
      ofs << "]\n";
      ofs << "}\n";
    }

    vtkNew<vtkMRMLNurbsSurfaceNode> sink;
    vtkNew<vtkMRMLNurbsSurfaceStorageNode> storage;
    storage->SetFileName(path.c_str());
    TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
    CHECK_INT(storage->ReadData(sink.GetPointer()), 0);
    TESTING_OUTPUT_ASSERT_ERRORS_END();
    vtksys::SystemTools::RemoveFile(path);
  }

  // Sub-case (b): Bezier reference + "Catmull" surfaceType → reject
  // (ReadJsonBezier rejects any non-"Bezier" value).
  {
    const std::string path = makeTempPath("lrp.json");
    {
      std::ofstream ofs(path);
      ofs << "{\n";
      ofs << "  \"schemaVersion\": 3,\n";
      ofs << "  \"surfaceType\": \"Catmull\",\n";
      ofs << "  \"state\": \"Init\",\n";
      ofs << "  \"initMode\": \"SlicingPlane\",\n";
      ofs << "  \"rows\": 4,\n";
      ofs << "  \"cols\": 4,\n";
      ofs << "  \"controlGrid\": [";
      for (int i = 0; i < 48; ++i)
      {
        if (i > 0)
        {
          ofs << ", ";
        }
        ofs << static_cast<double>(i);
      }
      ofs << "]\n";
      ofs << "}\n";
    }

    vtkNew<vtkMRMLBezierSurfaceNode> sink;
    vtkNew<vtkMRMLBezierSurfaceStorageNode> storage;
    storage->SetFileName(path.c_str());
    TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
    CHECK_INT(storage->ReadData(sink.GetPointer()), 0);
    TESTING_OUTPUT_ASSERT_ERRORS_END();
    vtksys::SystemTools::RemoveFile(path);
  }

  // Sub-case (c): missing surfaceType on a v3 file.  Characterises
  // current behaviour — the Bezier path tolerates the absent
  // discriminator and falls through to Bezier-shaped parsing (this
  // matches the legacy v2 path where there was no discriminator at
  // all).  The NURBS path requires the discriminator and rejects.
  {
    const std::string path = makeTempPath("lrp.json");
    {
      std::ofstream ofs(path);
      ofs << "{\n";
      ofs << "  \"schemaVersion\": 3,\n";
      // No "surfaceType" field.
      ofs << "  \"state\": \"Init\",\n";
      ofs << "  \"initMode\": \"SlicingPlane\",\n";
      ofs << "  \"rows\": 4,\n";
      ofs << "  \"cols\": 4,\n";
      ofs << "  \"controlGrid\": [";
      for (int i = 0; i < 48; ++i)
      {
        if (i > 0)
        {
          ofs << ", ";
        }
        ofs << static_cast<double>(i);
      }
      ofs << "]\n";
      ofs << "}\n";
    }

    // Bezier reference — accepted (falls back to Bezier parsing).
    {
      vtkNew<vtkMRMLBezierSurfaceNode> sink;
      vtkNew<vtkMRMLBezierSurfaceStorageNode> storage;
      storage->SetFileName(path.c_str());
      CHECK_INT(storage->ReadData(sink.GetPointer()), 1);
      CHECK_INT(static_cast<int>(sink->GetRows()), 4);
      CHECK_INT(static_cast<int>(sink->GetCols()), 4);
    }
    // NURBS reference — rejected (v3 NURBS files require the
    // discriminator).
    {
      vtkNew<vtkMRMLNurbsSurfaceNode> sink;
      vtkNew<vtkMRMLNurbsSurfaceStorageNode> storage;
      storage->SetFileName(path.c_str());
      TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
      CHECK_INT(storage->ReadData(sink.GetPointer()), 0);
      TESTING_OUTPUT_ASSERT_ERRORS_END();
    }
    vtksys::SystemTools::RemoveFile(path);
  }
  return EXIT_SUCCESS;
}

int testJsonReadV3NurbsControlGridLengthMismatch()
{
  // ADR-0022 §"Validation rules per surface type — NURBS":
  // ``len(controlGrid) == 3 * rows * cols``.  Send a NURBS file with
  // a correctly-sized {rows, cols, degrees, knots, weights} block
  // but a controlGrid of wrong length — must be rejected at the
  // read boundary.  Pairs ``testJsonReadV3NurbsInvalidKnotsLength``
  // (knot length mismatch) + ``testJsonReadV3NurbsInvalidWeights``
  // (weights length / positivity) to cover the third length-mismatch
  // axis the NURBS payload exposes.
  const std::string path = makeTempPath("lrp.json");
  {
    std::ofstream ofs(path);
    ofs << "{\n";
    ofs << "  \"schemaVersion\": 3,\n";
    ofs << "  \"surfaceType\": \"NURBS\",\n";
    ofs << "  \"state\": \"Init\",\n";
    ofs << "  \"initMode\": \"SlicingPlane\",\n";
    ofs << "  \"rows\": 4,\n";
    ofs << "  \"cols\": 4,\n";
    ofs << "  \"degreeU\": 3,\n";
    ofs << "  \"degreeV\": 3,\n";
    ofs << "  \"knotsU\": [0,0,0,0,1,1,1,1],\n";
    ofs << "  \"knotsV\": [0,0,0,0,1,1,1,1],\n";
    ofs << "  \"weights\": [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],\n";
    // controlGrid of length 27 (a 3×3 grid) instead of the expected
    // 48 (a 4×4 grid).
    ofs << "  \"controlGrid\": [";
    for (int i = 0; i < 27; ++i)
    {
      if (i > 0)
      {
        ofs << ", ";
      }
      ofs << static_cast<double>(i);
    }
    ofs << "]\n";
    ofs << "}\n";
  }

  vtkNew<vtkMRMLNurbsSurfaceNode> sink;
  vtkNew<vtkMRMLNurbsSurfaceStorageNode> storage;
  storage->SetFileName(path.c_str());
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  CHECK_INT(storage->ReadData(sink.GetPointer()), 0);
  TESTING_OUTPUT_ASSERT_ERRORS_END();

  vtksys::SystemTools::RemoveFile(path);
  return EXIT_SUCCESS;
}

int testJsonReadV3NurbsInvalidKnotsContent()
{
  // ADR-0022 §"Validation rules per surface type — NURBS": knot
  // vectors must be clamped + monotonic + within ``[0, 1]``.  Pair
  // ``testJsonReadV3NurbsInvalidKnotsLength`` (length) by covering
  // the content invariants — synthesise a length-correct but
  // non-monotonic knotsU and confirm rejection at the read boundary.
  const std::string path = makeTempPath("lrp.json");
  {
    std::ofstream ofs(path);
    ofs << "{\n";
    ofs << "  \"schemaVersion\": 3,\n";
    ofs << "  \"surfaceType\": \"NURBS\",\n";
    ofs << "  \"state\": \"Init\",\n";
    ofs << "  \"initMode\": \"SlicingPlane\",\n";
    ofs << "  \"rows\": 4,\n";
    ofs << "  \"cols\": 4,\n";
    ofs << "  \"degreeU\": 3,\n";
    ofs << "  \"degreeV\": 3,\n";
    // Length-correct (8) but non-monotonic: a 0.7 followed by 0.3
    // in the middle of the (admittedly degenerate, no-interior)
    // knot region.  Also clamping-violating — degree=3 expects 4
    // equal repeats on each end.
    ofs << "  \"knotsU\": [0,0,0,0.7,0.3,1,1,1],\n";
    ofs << "  \"knotsV\": [0,0,0,0,1,1,1,1],\n";
    ofs << "  \"weights\": [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],\n";
    ofs << "  \"controlGrid\": [";
    for (int i = 0; i < 48; ++i)
    {
      if (i > 0)
      {
        ofs << ", ";
      }
      ofs << static_cast<double>(i);
    }
    ofs << "]\n";
    ofs << "}\n";
  }

  vtkNew<vtkMRMLNurbsSurfaceNode> sink;
  vtkNew<vtkMRMLNurbsSurfaceStorageNode> storage;
  storage->SetFileName(path.c_str());
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  CHECK_INT(storage->ReadData(sink.GetPointer()), 0);
  TESTING_OUTPUT_ASSERT_ERRORS_END();

  vtksys::SystemTools::RemoveFile(path);
  return EXIT_SUCCESS;
}

int testNurbsStorageCanReadDiscrimination()
{
  // The NURBS subclass inherits the base's CanRead/CanWrite
  // predicates — both should accept either surface-type reference
  // node (the storage class is unified per ADR-0022; the subclass
  // just changes the node tag name + factory method).
  vtkNew<vtkMRMLNurbsSurfaceStorageNode> storage;
  vtkNew<vtkMRMLNurbsSurfaceNode> nurbs;
  vtkNew<vtkMRMLBezierSurfaceNode> bezier;

  CHECK_BOOL(storage->CanReadInReferenceNode(nurbs.GetPointer()), true);
  CHECK_BOOL(storage->CanWriteFromReferenceNode(nurbs.GetPointer()), true);
  // The base storage class accepts Bezier too — the subclass does
  // not narrow the predicate.  Document this here so future drift
  // is intentional.
  CHECK_BOOL(storage->CanReadInReferenceNode(bezier.GetPointer()), true);
  CHECK_BOOL(storage->CanWriteFromReferenceNode(bezier.GetPointer()), true);
  CHECK_STRING(storage->GetNodeTagName(), "NurbsSurfaceStorage");
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
  CHECK_EXIT_SUCCESS(testConfirmedStateRoundTrip());
  CHECK_EXIT_SUCCESS(testUnknownStateFallback());
  CHECK_EXIT_SUCCESS(testSchemaVersionMismatch());
  CHECK_EXIT_SUCCESS(testLegacyFcsvRead());
  CHECK_EXIT_SUCCESS(testLegacyFcsvWriteRejected());
  CHECK_EXIT_SUCCESS(testLegacyFcsvFixture());
  CHECK_EXIT_SUCCESS(testJsonRoundTrip3x3());
  CHECK_EXIT_SUCCESS(testJsonReadV1Implicit4x4());
  CHECK_EXIT_SUCCESS(testJsonReadV2InvalidShape());
  CHECK_EXIT_SUCCESS(testJsonReadV2OutOfRange());
  CHECK_EXIT_SUCCESS(testJsonReadV2ControlGridLengthMismatch());

  // v2.1 NURBS sibling — schema v3 (ADR-0022 §"Decision 2").
  CHECK_EXIT_SUCCESS(testJsonRoundTripNurbs());
  CHECK_EXIT_SUCCESS(testJsonReadV3BezierExplicit());
  CHECK_EXIT_SUCCESS(testJsonReadV3NurbsInvalidDegree());
  CHECK_EXIT_SUCCESS(testJsonReadV3NurbsInvalidKnotsLength());
  CHECK_EXIT_SUCCESS(testJsonReadV3NurbsInvalidWeights());
  CHECK_EXIT_SUCCESS(testJsonReadV3NurbsInvalidShape());
  CHECK_EXIT_SUCCESS(testJsonReadInvalidSurfaceType());
  CHECK_EXIT_SUCCESS(testJsonReadV3NurbsControlGridLengthMismatch());
  CHECK_EXIT_SUCCESS(testJsonReadV3NurbsInvalidKnotsContent());
  CHECK_EXIT_SUCCESS(testWriterAlwaysEmitsV3Bezier());
  CHECK_EXIT_SUCCESS(testNurbsStorageCanReadDiscrimination());

  std::cout << "vtkMRMLBezierSurfaceStorageNodeTest1 completed successfully" << std::endl;
  return EXIT_SUCCESS;
}

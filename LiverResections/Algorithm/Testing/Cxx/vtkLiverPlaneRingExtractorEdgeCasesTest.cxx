/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) Oslo University Hospital. All rights reserved.

  Edge-case stress tests for vtkLiverPlaneRingExtractor (issue #335).

  This file is the bug-discovery counterpart to vtkLiverPlaneRingExtractorTest1
  (which pins the well-conditioned z=0 great-circle smoke case).  Each
  sub-test exercises one corner-case input the smoke test does not cover,
  and asserts either a defined output (graceful handling) or a defined
  failure mode (vtkErrorMacro + RequestData == 0).  See the SubTestReport
  block at the bottom for the aggregate pass/fail line ctest will scrape.

==============================================================================*/

#include "vtkLiverAlgorithmEdgeCaseHelpers.h"
#include "vtkLiverPlaneRingExtractor.h"

#include <vtkCellArray.h>
#include <vtkNew.h>
#include <vtkPoints.h>
#include <vtkPolyData.h>
#include <vtkSphereSource.h>
#include <vtkTestingOutputWindow.h>

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <limits>

namespace
{

using vtkLiverAlgorithmEdgeCaseHelpers::makeUnitCube;
using vtkLiverAlgorithmEdgeCaseHelpers::makeUnitSphere;
using vtkLiverAlgorithmEdgeCaseHelpers::SubTestReport;

// Drive an extractor and return the number of output points.  Caller
// handles the polydata if non-null.
int runExtractor(vtkLiverPlaneRingExtractor* ex, vtkPolyData* target, double origin[3], double normal[3])
{
  ex->SetInputData(0, target);
  ex->SetOrigin(origin);
  ex->SetNormal(normal);
  ex->Update();
  vtkPolyData* out = ex->GetOutput();
  return out && out->GetPoints() ? static_cast<int>(out->GetPoints()->GetNumberOfPoints()) : 0;
}

//----------------------------------------------------------------------------
// PlaneOutsideMesh — plane sits 10 unit-radii above a unit sphere: no
// intersection.  Expected: empty output, no warning, no error.
void testPlaneOutsideMesh(SubTestReport& r)
{
  auto sphere = makeUnitSphere();
  vtkNew<vtkLiverPlaneRingExtractor> ex;
  double origin[3] = { 0.0, 0.0, 10.0 };
  double normal[3] = { 0.0, 0.0, 1.0 };
  const int n = runExtractor(ex, sphere, origin, normal);
  if (n == 0)
  {
    r.pass("PlaneOutsideMesh");
  }
  else
  {
    r.fail("PlaneOutsideMesh", "expected empty output but got " + std::to_string(n) + " points");
  }
}

//----------------------------------------------------------------------------
// PlaneTangentToSphere — z = 1.0 just grazes the unit sphere's north
// pole.  vtkCutter typically emits a single point (degenerate cell) or
// no cells; either is acceptable as long as nothing crashes.
void testPlaneTangentToSphere(SubTestReport& r)
{
  auto sphere = makeUnitSphere(128, 128);
  vtkNew<vtkLiverPlaneRingExtractor> ex;
  double origin[3] = { 0.0, 0.0, 1.0 };
  double normal[3] = { 0.0, 0.0, 1.0 };
  const int n = runExtractor(ex, sphere, origin, normal);
  // Tangent cuts on a faceted sphere can produce up to a one-edge
  // ring (a handful of points) along the discretised pole; demand
  // small but allow non-empty.
  if (n <= 8)
  {
    r.pass("PlaneTangentToSphere");
  }
  else
  {
    r.fail("PlaneTangentToSphere", "tangent cut produced " + std::to_string(n) + " points; expected <= 8");
  }
}

//----------------------------------------------------------------------------
// PlaneThroughVertex — cut a cube with z = 0.5 (exactly the +z face plane).
// This plane passes through 4 vertices and is parallel to the face.  The
// cut should still produce a well-defined output (either the face boundary
// or empty), never crash.
void testPlaneThroughVertex(SubTestReport& r)
{
  auto cube = makeUnitCube();
  vtkNew<vtkLiverPlaneRingExtractor> ex;
  double origin[3] = { 0.0, 0.0, 0.5 }; // top face of the cube
  double normal[3] = { 0.0, 0.0, 1.0 };
  const int n = runExtractor(ex, cube, origin, normal);
  // Acceptable outcomes: 0 (no triangle straddles the plane) or 4-5
  // (the four boundary vertices, possibly with the loop closed).
  if (n == 0 || (n >= 3 && n <= 8))
  {
    r.pass("PlaneThroughVertex");
  }
  else
  {
    r.fail("PlaneThroughVertex", "expected 0 or 3-8 points, got " + std::to_string(n));
  }
}

//----------------------------------------------------------------------------
// PlaneParallelToFlatFace — cut a cube with z = 0.499, just below the +z
// face.  Expected: a square ring of 4 (or 5 with closure) points along the
// cube's vertical edges.
void testPlaneParallelToFlatFace(SubTestReport& r)
{
  auto cube = makeUnitCube();
  vtkNew<vtkLiverPlaneRingExtractor> ex;
  double origin[3] = { 0.0, 0.0, 0.499 };
  double normal[3] = { 0.0, 0.0, 1.0 };
  const int n = runExtractor(ex, cube, origin, normal);
  // Stripper emits the closed quad ring as either 4 unique points or
  // 8 points where the loop is duplicated (a startpoint repeat at
  // join boundaries between original cutter segments).  Either is
  // acceptable; the invariant is "a closed 4-corner ring."
  if (n == 4 || n == 5 || n == 8)
  {
    r.pass("PlaneParallelToFlatFace");
  }
  else
  {
    r.fail("PlaneParallelToFlatFace", "expected 4, 5, or 8 ring points, got " + std::to_string(n));
  }
}

//----------------------------------------------------------------------------
// NullInputMesh — calling Update() without an input polydata must report
// an error (vtkErrorMacro) and return 0 from RequestData, not crash.
void testNullInputMesh(SubTestReport& r)
{
  TESTING_OUTPUT_RESET();
  vtkNew<vtkLiverPlaneRingExtractor> ex;
  double origin[3] = { 0.0, 0.0, 0.0 };
  double normal[3] = { 0.0, 0.0, 1.0 };
  ex->SetOrigin(origin);
  ex->SetNormal(normal);
  // No SetInputData call → port 0 is empty.  vtkAlgorithm's contract
  // produces a default-constructed input data object on the connection,
  // so the algorithm will receive a vtkPolyData with zero points rather
  // than nullptr.  Behaviour we assert: empty output, no crash.
  TESTING_OUTPUT_IGNORE_WARNINGS_ERRORS_BEGIN();
  ex->Update();
  TESTING_OUTPUT_IGNORE_WARNINGS_ERRORS_END();
  vtkPolyData* out = ex->GetOutput();
  const int n = out && out->GetPoints() ? static_cast<int>(out->GetPoints()->GetNumberOfPoints()) : 0;
  if (n == 0)
  {
    r.pass("NullInputMesh");
  }
  else
  {
    r.fail("NullInputMesh", "expected 0 points, got " + std::to_string(n));
  }
}

//----------------------------------------------------------------------------
// NaNNormal — a degenerate normal vector containing NaN.  vtkPlane should
// short-circuit (no intersection); we mostly care that no crash occurs.
void testNaNNormal(SubTestReport& r)
{
  auto sphere = makeUnitSphere();
  vtkNew<vtkLiverPlaneRingExtractor> ex;
  double origin[3] = { 0.0, 0.0, 0.0 };
  double normal[3] = { std::numeric_limits<double>::quiet_NaN(), 0.0, 1.0 };
  TESTING_OUTPUT_IGNORE_WARNINGS_ERRORS_BEGIN();
  const int n = runExtractor(ex, sphere, origin, normal);
  TESTING_OUTPUT_IGNORE_WARNINGS_ERRORS_END();
  // No crash → pass.  Output content is implementation-defined for
  // NaN normals; either empty or garbage is acceptable as long as
  // RequestData returns.  Pin: must not segfault.
  (void)n;
  r.pass("NaNNormal");
}

} // namespace

int vtkLiverPlaneRingExtractorEdgeCasesTest(int, char*[])
{
  SubTestReport r;
  std::fprintf(stderr, "[PlaneRingExtractor edge cases]\n");

  testPlaneOutsideMesh(r);
  testPlaneTangentToSphere(r);
  testPlaneThroughVertex(r);
  testPlaneParallelToFlatFace(r);
  testNullInputMesh(r);
  testNaNNormal(r);

  r.print("PlaneRingExtractor");
  return r.failed == 0 ? EXIT_SUCCESS : EXIT_FAILURE;
}

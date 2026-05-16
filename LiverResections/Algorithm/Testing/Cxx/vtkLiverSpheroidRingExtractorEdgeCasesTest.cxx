/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) Oslo University Hospital. All rights reserved.

  Edge-case stress tests for vtkLiverSpheroidRingExtractor (issue #335).

  See vtkLiverPlaneRingExtractorEdgeCasesTest.cxx header for the
  reporting / acceptance discipline (defined output OR defined failure
  mode).

==============================================================================*/

#include "vtkLiverAlgorithmEdgeCaseHelpers.h"
#include "vtkLiverSpheroidRingExtractor.h"

#include <vtkCellArray.h>
#include <vtkNew.h>
#include <vtkPoints.h>
#include <vtkPolyData.h>
#include <vtkTestingOutputWindow.h>

#include <cmath>
#include <cstdio>
#include <cstdlib>

namespace
{

using vtkLiverAlgorithmEdgeCaseHelpers::makeUnitSphere;
using vtkLiverAlgorithmEdgeCaseHelpers::SubTestReport;

int runExtractor(vtkLiverSpheroidRingExtractor* ex, vtkPolyData* target, const double center[3], double rx, double ry, double rz)
{
  ex->SetInputData(0, target);
  ex->SetCenter(center[0], center[1], center[2]);
  ex->SetRadiusX(rx);
  ex->SetRadiusY(ry);
  ex->SetRadiusZ(rz);
  ex->Update();
  vtkPolyData* out = ex->GetOutput();
  return out && out->GetPoints() ? static_cast<int>(out->GetPoints()->GetNumberOfPoints()) : 0;
}

//----------------------------------------------------------------------------
// SpheroidEntirelyOutsideMesh — spheroid centred well above the sphere
// with radius too small to reach.  Expected: empty output.
void testSpheroidEntirelyOutsideMesh(SubTestReport& r)
{
  auto sphere = makeUnitSphere();
  vtkNew<vtkLiverSpheroidRingExtractor> ex;
  const double center[3] = { 0.0, 0.0, 10.0 };
  const int n = runExtractor(ex, sphere, center, 0.1, 0.1, 0.1);
  if (n == 0)
  {
    r.pass("SpheroidEntirelyOutsideMesh");
  }
  else
  {
    r.fail("SpheroidEntirelyOutsideMesh", "expected empty, got " + std::to_string(n));
  }
}

//----------------------------------------------------------------------------
// SpheroidEntirelyInsideMesh — tiny spheroid completely inside the unit
// sphere.  The quadric is negative everywhere on the sphere surface, so
// the cutter produces no level-zero cells.
void testSpheroidEntirelyInsideMesh(SubTestReport& r)
{
  auto sphere = makeUnitSphere();
  vtkNew<vtkLiverSpheroidRingExtractor> ex;
  const double center[3] = { 0.0, 0.0, 0.0 };
  const int n = runExtractor(ex, sphere, center, 0.1, 0.1, 0.1);
  if (n == 0)
  {
    r.pass("SpheroidEntirelyInsideMesh");
  }
  else
  {
    r.fail("SpheroidEntirelyInsideMesh", "expected empty, got " + std::to_string(n));
  }
}

//----------------------------------------------------------------------------
// SpheroidTangentToSphere — radius 2.0 spheroid centred so the +x apex
// just touches the unit sphere at (1, 0, 0).  Acceptance: small (or
// zero) output but no crash.
void testSpheroidTangentToSphere(SubTestReport& r)
{
  auto sphere = makeUnitSphere(128, 128);
  vtkNew<vtkLiverSpheroidRingExtractor> ex;
  const double center[3] = { -1.0, 0.0, 0.0 }; // sphere of radius 2.0 from -1 → +1
  const int n = runExtractor(ex, sphere, center, 2.0, 2.0, 2.0);
  if (n <= 16)
  {
    r.pass("SpheroidTangentToSphere");
  }
  else
  {
    r.fail("SpheroidTangentToSphere", "tangent produced " + std::to_string(n) + " points; expected <= 16");
  }
}

//----------------------------------------------------------------------------
// VeryOblateSpheroid — aspect 100:1 (rx = 100, rz = 1).  At origin the
// quadric F = (x² + y²)/10000 + z² - 1.  On the unit sphere x² + y² + z²
// = 1, F reduces to z² − 1 + (1−z²)/10000 ≈ z² − 1, which is zero only
// at z = ±1 (the poles).  vtkCutter picks up the two pole crossings as
// two single-point cells.  Acceptance: extractor returns 0 or 2 points
// (pole tangency on a faceted sphere is ambiguous; either is graceful).
void testVeryOblateSpheroid(SubTestReport& r)
{
  auto sphere = makeUnitSphere();
  vtkNew<vtkLiverSpheroidRingExtractor> ex;
  const double center[3] = { 0.0, 0.0, 0.0 };
  const int n = runExtractor(ex, sphere, center, 100.0, 100.0, 1.0);
  if (n <= 4)
  {
    r.pass("VeryOblateSpheroid");
  }
  else
  {
    r.fail("VeryOblateSpheroid", "100:1 oblate touched at " + std::to_string(n) + " points; expected pole tangency (<= 4)");
  }
}

//----------------------------------------------------------------------------
// VeryProlateSpheroid — aspect 1:100 (rz = 100, rx = ry = 0.01).  Long
// thin needle along z.  Should produce a defined empty output (the
// needle is too thin to touch the unit sphere unless centred inside).
void testVeryProlateSpheroid(SubTestReport& r)
{
  auto sphere = makeUnitSphere();
  vtkNew<vtkLiverSpheroidRingExtractor> ex;
  const double center[3] = { 5.0, 0.0, 0.0 }; // centre off the sphere
  const int n = runExtractor(ex, sphere, center, 0.01, 0.01, 100.0);
  if (n == 0)
  {
    r.pass("VeryProlateSpheroid");
  }
  else
  {
    r.fail("VeryProlateSpheroid", "thin needle off-sphere should be empty, got " + std::to_string(n));
  }
}

//----------------------------------------------------------------------------
// SpheroidExtremeAspect_0p1 — aspect 0.1 (rx = ry = 1.5, rz = 0.1)
// centred on the sphere.  Implicit F = ((x² + y²)/2.25) + 100·z² − 1.
// On a unit sphere where x² + y² = 1 − z², F reduces to
// (1 − z²)/2.25 + 100 z² − 1 ≈ 99·z² − 0.55, which crosses zero near
// z ≈ ±0.0745 — a real intersection ring.  Tests the squashed-spheroid
// path produces a non-trivial output.
void testSpheroidExtremeAspect0p1(SubTestReport& r)
{
  auto sphere = makeUnitSphere(128, 128);
  vtkNew<vtkLiverSpheroidRingExtractor> ex;
  const double center[3] = { 0.0, 0.0, 0.0 };
  const int n = runExtractor(ex, sphere, center, 1.5, 1.5, 0.1);
  if (n >= 10)
  {
    r.pass("SpheroidExtremeAspect_0p1");
  }
  else
  {
    r.fail("SpheroidExtremeAspect_0p1", "expected a non-trivial ring (>=10 pts), got " + std::to_string(n));
  }
}

//----------------------------------------------------------------------------
// NegativeRadius — invalid input.  RequestData must emit vtkErrorMacro
// and return 0; output stays empty.
void testNegativeRadius(SubTestReport& r)
{
  TESTING_OUTPUT_RESET();
  auto sphere = makeUnitSphere();
  vtkNew<vtkLiverSpheroidRingExtractor> ex;
  ex->SetInputData(0, sphere);
  ex->SetCenter(0.0, 0.0, 0.0);
  ex->SetRadiusX(-1.0);
  ex->SetRadiusY(1.0);
  ex->SetRadiusZ(1.0);
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  ex->Update();
  TESTING_OUTPUT_ASSERT_ERRORS_END();
  r.pass("NegativeRadius");
}

//----------------------------------------------------------------------------
// ZeroRadius — radius == 0 is invalid (would divide by zero in the
// quadric coefficient inv2x).  RequestData must emit an error and
// return early.
void testZeroRadius(SubTestReport& r)
{
  TESTING_OUTPUT_RESET();
  auto sphere = makeUnitSphere();
  vtkNew<vtkLiverSpheroidRingExtractor> ex;
  ex->SetInputData(0, sphere);
  ex->SetCenter(0.0, 0.0, 0.0);
  ex->SetRadiusX(0.0);
  ex->SetRadiusY(1.0);
  ex->SetRadiusZ(1.0);
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  ex->Update();
  TESTING_OUTPUT_ASSERT_ERRORS_END();
  r.pass("ZeroRadius");
}

} // namespace

int vtkLiverSpheroidRingExtractorEdgeCasesTest(int, char*[])
{
  SubTestReport r;
  std::fprintf(stderr, "[SpheroidRingExtractor edge cases]\n");

  testSpheroidEntirelyOutsideMesh(r);
  testSpheroidEntirelyInsideMesh(r);
  testSpheroidTangentToSphere(r);
  testVeryOblateSpheroid(r);
  testVeryProlateSpheroid(r);
  testSpheroidExtremeAspect0p1(r);
  testNegativeRadius(r);
  testZeroRadius(r);

  r.print("SpheroidRingExtractor");
  return r.failed == 0 ? EXIT_SUCCESS : EXIT_FAILURE;
}

/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Stack-4 ring-extraction wiring — Constraint 1 (shader/extractor
  parameter consistency) + Constraint 2 (extraction-granularity bound)
  for vtkLiverSpheroidRingExtractor.

  -- WHY THIS TEST IS RED-BY-CONSTRUCTION --

  vtkLiverSpheroidRingExtractorTest1 already verifies that the ring
  points satisfy the spheroid implicit within the mesh-discretisation
  bound (1/8)*max|F''|*h^2.  That test re-derives the implicit
  ((x-cx)/rx)^2 + ... - 1 BY HAND in the test body.

  The drift that Constraint 1 pins is precisely that hand-derivation:
  the GLSL shader transcribes the implicit one way, the extractor's
  RequestData transcribes the same implicit into vtkQuadric's a0..a9
  coefficient form a SECOND way (the off-by-2 bug class on the linear
  terms documented in the class doxygen), and any test that ALSO
  open-codes the formula adds a THIRD transcription.  Three independent
  copies of one surface definition cannot be kept in agreement to
  machine precision by inspection.

  The fix Constraint 1 mandates is a SINGLE-SOURCE-OF-TRUTH coefficient
  builder both paths transcribe FROM:

      static void vtkLiverSpheroidRingExtractor::ComputeQuadricCoefficients(
          const double center[3], double rx, double ry, double rz,
          double a[10]);

  -- the canonical (cx, cy, cz, rx, ry, rz) -> a0..a9 map.  RequestData
  feeds vtkQuadric from it; the parameter->shader adapter (Stack 4) feeds
  the GLSL uniform pack from it; this test evaluates the implicit at the
  extractor's OUTPUT ring points THROUGH it.  When all three read the
  same accessor, "agree to machine precision" is structural, not
  inspected.

  This file does NOT re-open-code the formula.  It calls the accessor.
  Until the implementer adds it, the accessor does not exist, so the
  consistency-checked branch is compiled out behind
  LIVER_SPHEROID_QUADRIC_SSOT (undefined now) and the test returns the
  CTest skip code (125).  RED == skipped-pending until the SSOT lands;
  the skip lifts at the implementation commit.

  Tag: ADR-0003 (algorithm library links no MRML; pure-VTK, no GL
  context needed — the consistency math is CPU-evaluable), ADR-0015
  §Context (the off-by-2 bug-discovery motivation)
  Constraint 1 + Constraint 2.

  Define -DLIVER_SPHEROID_QUADRIC_SSOT once
  vtkLiverSpheroidRingExtractor::ComputeQuadricCoefficients exists.

==============================================================================*/

#include "vtkLiverSpheroidRingExtractor.h"

// VTK includes
#include <vtkCellArray.h>
#include <vtkNew.h>
#include <vtkPoints.h>
#include <vtkPolyData.h>
#include <vtkSphereSource.h>

#include <cmath>
#include <cstdio>
#include <cstdlib>

namespace
{
// CTest skip return code (kept in sync with the SKIP_RETURN_CODE the
// CMakeLists sets on this test).
constexpr int kSkipReturnCode = 125;

#ifdef LIVER_SPHEROID_QUADRIC_SSOT
// Evaluate vtkQuadric's implicit F at p from the a0..a9 coefficient
// vector, using the SAME evaluation order vtkQuadric documents:
//   F = a0 x^2 + a1 y^2 + a2 z^2
//     + a3 xy + a4 yz + a5 xz
//     + a6 x  + a7 y  + a8 z + a9
// (no implicit factor of 2 on the cross/linear terms).  This is the
// single transcription of the *evaluation*; the COEFFICIENTS come from
// the extractor's SSOT accessor, not from this test.
double evalQuadric(const double a[10], const double p[3])
{
  const double x = p[0];
  const double y = p[1];
  const double z = p[2];
  return a[0] * x * x + a[1] * y * y + a[2] * z * z + a[3] * x * y + a[4] * y * z + a[5] * x * z + a[6] * x + a[7] * y + a[8] * z + a[9];
}
#endif

} // namespace

int vtkLiverSpheroidRingExtractorConsistencyTest(int, char*[])
{
#ifndef LIVER_SPHEROID_QUADRIC_SSOT
  std::fprintf(stderr,
               "[SpheroidRingExtractor consistency] SKIP: the "
               "single-source-of-truth coefficient builder "
               "vtkLiverSpheroidRingExtractor::ComputeQuadricCoefficients() "
               "does not exist yet.  Constraint 1 requires the "
               "extractor's RequestData, the Stack-4 parameter->shader "
               "adapter, and this consistency test to all transcribe the "
               "spheroid implicit FROM that one accessor.  Add it and define "
               "-DLIVER_SPHEROID_QUADRIC_SSOT to lift this skip.\n");
  return kSkipReturnCode;
#else
  // Synthetic input identical to vtkLiverSpheroidRingExtractorTest1's so
  // the residual-bound rationale (h ~ 0.1, |F''| ~ 3 => bound ~4e-3)
  // carries over verbatim.
  vtkNew<vtkSphereSource> sphere;
  sphere->SetRadius(1.0);
  sphere->SetCenter(0.0, 0.0, 0.0);
  sphere->SetThetaResolution(64);
  sphere->SetPhiResolution(64);
  sphere->Update();

  const double center[3] = { 0.5, 0.0, 0.0 };
  const double rx = 0.8;
  const double ry = 0.8;
  const double rz = 1.2;

  vtkNew<vtkLiverSpheroidRingExtractor> extractor;
  extractor->SetInputConnection(sphere->GetOutputPort());
  extractor->SetCenter(center[0], center[1], center[2]);
  extractor->SetRadiusX(rx);
  extractor->SetRadiusY(ry);
  extractor->SetRadiusZ(rz);
  extractor->Update();

  vtkPolyData* out = extractor->GetOutput();
  if (!out || !out->GetPoints() || out->GetPoints()->GetNumberOfPoints() == 0)
  {
    std::fprintf(stderr, "[SpheroidRingExtractor consistency] FAIL: empty output\n");
    return EXIT_FAILURE;
  }

  // Constraint 1 — the COEFFICIENTS come from the SSOT accessor that the
  // extractor itself feeds vtkQuadric from.  No third hand-derivation.
  double a[10];
  vtkLiverSpheroidRingExtractor::ComputeQuadricCoefficients(center, rx, ry, rz, a);

  // Constraint 2 — the documented mesh-discretisation residual bound.
  // (1/8)*max|F''|*h^2 with h ~ 0.1 and |F''| ~ 3 gives ~4e-3; allow 1e-2
  // for safety margin, matching vtkLiverSpheroidRingExtractorTest1.
  constexpr double granularityTol = 1e-2;

  const vtkIdType n = out->GetPoints()->GetNumberOfPoints();
  for (vtkIdType i = 0; i < n; ++i)
  {
    double p[3];
    out->GetPoints()->GetPoint(i, p);
    const double residual = evalQuadric(a, p);
    if (std::fabs(residual) > granularityTol)
    {
      std::fprintf(stderr,
                   "[SpheroidRingExtractor consistency] FAIL: ring point %lld "
                   "evaluates to F=%g via the SSOT coefficients, exceeding the "
                   "(1/8)max|F''|h^2 mesh-discretisation bound (tol %g)\n",
                   static_cast<long long>(i),
                   residual,
                   granularityTol);
      return EXIT_FAILURE;
    }
  }
  return EXIT_SUCCESS;
#endif
}

/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  GPU-path / SSOT consistency pin for the distance-spheroid init contour.

  -- WHAT THIS TEST PINS --

  ADR-0014 §2 specifies the DistanceSpheroid init contour as a triaxial
  ellipsoid

      ((x-cx)/rx)^2 + ((y-cy)/ry)^2 + ((z-cz)/rz)^2 = 1

  rendered by vtkOpenGLDistanceContourPolyDataMapper.  Today the mapper's
  shader renders a PLACEHOLDER two-point sphere (uniforms uExternalPointMC
  / uReferencePointMC / uContourThickness / uContourVisibility); the
  node's DistanceSpheroidRadiusX/Y/Z parameters reach NO shader uniform.

  ADR-0015 §"Stack 4" makes the GPU path consume the SAME single source of
  truth the CPU ring extractor uses:

      static void vtkLiverSpheroidRingExtractor::ComputeQuadricCoefficients(
          const double center[3], double rx, double ry, double rz,
          double a[10]);

  -- the canonical (cx, cy, cz, rx, ry, rz) -> vtkQuadric a0..a9 map.  The
  CPU extractor's RequestData already feeds vtkQuadric from it.  The GPU
  mapper must derive the quadric uniform it binds to the fragment shader
  FROM THE SAME accessor, so the rendered surface and the extracted ring
  are provably the SAME surface (the Stack-4 consistency goal).

  This test is the GL-free decisive pin of that consistency: drive the
  mapper with a known (center, rx, ry, rz), read back the coefficient
  vector it WOULD bind as the shader uniform, and assert it equals
  ComputeQuadricCoefficients(center, rx, ry, rz) element-wise within
  tolerance.  No GL context is created and no pixels are produced; the
  consistency is pure CPU arithmetic.  Per ADR-0008 §2 this is a C++
  low-level ctkTest-driver test (no Slicer scene, no Qt, no GL).

  The SSOT stays the single source: this test calls
  ComputeQuadricCoefficients directly, the mapper MUST too.  The test does
  NOT re-open-code the (center, radii) -> a0..a9 formula; a third
  transcription would defeat the purpose.

  -- THE SEAM THE IMPLEMENTER MUST ADD (RED hook) --

  vtkOpenGLDistanceContourPolyDataMapper currently has no spheroid setter
  and no way to read back the quadric it would bind.  The implementer
  adds, on the mapper:

      // Set the triaxial-ellipsoid spheroid the contour renders.  The
      // mapper derives the vtkQuadric a0..a9 coefficient vector for the
      // shader uniform by calling
      // vtkLiverSpheroidRingExtractor::ComputeQuadricCoefficients (the
      // SSOT) -- it does NOT re-derive the formula.
      void SetSpheroid(const double center[3], double rx, double ry, double rz);

      // Read back the a0..a9 coefficient vector the mapper would bind as
      // the spheroid-quadric shader uniform.  CPU-readable mirror of the
      // bound uniform so the GPU path is testable without a GL context.
      void GetSpheroidQuadricCoefficients(double a[10]) const;

  Until that seam exists this file's check is compiled out behind
  LIVER_SPHEROID_GPU_QUADRIC_SSOT (undefined now) and the test returns
  the CTest skip code (125).  RED == skipped-pending; the skip lifts when
  the implementer adds the seam, links
  vtkSlicerLiverResectionsModuleAlgorithm into VTKWidgets, and the
  CMakeLists defines -DLIVER_SPHEROID_GPU_QUADRIC_SSOT on this source.

  Tag: ADR-0014 §2 (triaxial-ellipsoid contour), ADR-0015 §"Stack 4"
  (GPU path consumes the SSOT; render == extract).

==============================================================================*/

// LiverResections VTKWidgets includes (relocation home per ADR-0014 §3)
#include "vtkOpenGLDistanceContourPolyDataMapper.h"

// LiverResections Algorithm includes (the SSOT lives here; ADR-0015
// §"Stack 4").  The test target links vtkSlicerLiverResectionsModuleAlgorithm
// so it can call the canonical coefficient builder directly.
#include "vtkLiverSpheroidRingExtractor.h"

// VTK includes
#include <vtkNew.h>

// STD includes
#include <cmath>
#include <cstdio>
#include <cstdlib>

namespace
{
// CTest skip return code (kept in sync with the SKIP_RETURN_CODE the
// CMakeLists sets on this test).
constexpr int kSkipReturnCode = 125;

} // namespace

//------------------------------------------------------------------------------
int vtkOpenGLDistanceContourMapperSpheroidSSOTTest(int, char*[])
{
#ifndef LIVER_SPHEROID_GPU_QUADRIC_SSOT
  std::fprintf(stderr,
               "[DistanceContourMapper spheroid SSOT] SKIP: the mapper seam "
               "vtkOpenGLDistanceContourPolyDataMapper::SetSpheroid(center, "
               "rx, ry, rz) + GetSpheroidQuadricCoefficients(a[10]) does not "
               "exist yet.  ADR-0014 §2 wants the contour rendered as a "
               "triaxial ellipsoid and ADR-0015 §\"Stack 4\" requires the GPU "
               "path to derive its quadric uniform FROM "
               "vtkLiverSpheroidRingExtractor::ComputeQuadricCoefficients (the "
               "SSOT), so render == extract.  Add the seam, link "
               "vtkSlicerLiverResectionsModuleAlgorithm into VTKWidgets, and "
               "define -DLIVER_SPHEROID_GPU_QUADRIC_SSOT to lift this skip.\n");
  return kSkipReturnCode;
#else
  // Known triaxial spheroid: off-origin centre, three distinct radii, so
  // the placeholder two-point sphere CANNOT accidentally reproduce the
  // expected coefficients (rx != ry != rz, centre != origin).
  const double center[3] = { 0.5, -0.25, 1.0 };
  const double rx = 0.8;
  const double ry = 1.3;
  const double rz = 2.1;

  // The expected coefficients come from the SSOT accessor that the CPU
  // ring extractor itself feeds vtkQuadric from.  No third hand-derivation
  // of the (centre, radii) -> a0..a9 formula in this test.
  double expected[10];
  vtkLiverSpheroidRingExtractor::ComputeQuadricCoefficients(center, rx, ry, rz, expected);

  // Drive the mapper through the public seam.  The mapper MUST derive the
  // bound uniform via the same SSOT accessor (NOT re-derive the formula).
  vtkNew<vtkOpenGLDistanceContourPolyDataMapper> mapper;
  mapper->SetSpheroid(center, rx, ry, rz);

  double bound[10];
  mapper->GetSpheroidQuadricCoefficients(bound);

  // Element-wise equality within tolerance.  Same SSOT on both sides ⇒ the
  // only slack is float<->double round-trip if the uniform is packed as
  // float; 1e-5 covers single-precision packing comfortably.
  constexpr double coeffTol = 1e-5;
  for (int i = 0; i < 10; ++i)
  {
    if (std::fabs(bound[i] - expected[i]) > coeffTol)
    {
      std::fprintf(stderr,
                   "[DistanceContourMapper spheroid SSOT] FAIL: coefficient "
                   "a%d the mapper would bind (%g) differs from the SSOT "
                   "vtkLiverSpheroidRingExtractor::ComputeQuadricCoefficients "
                   "value (%g) beyond tol %g.  The GPU path and the CPU "
                   "extractor would render/extract DIFFERENT surfaces "
                   "(ADR-0015 §\"Stack 4\" consistency goal violated).\n",
                   i,
                   bound[i],
                   expected[i],
                   coeffTol);
      return EXIT_FAILURE;
    }
  }

  std::printf("vtkOpenGLDistanceContourMapperSpheroidSSOTTest completed successfully\n");
  return EXIT_SUCCESS;
#endif
}

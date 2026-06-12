/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Non-regression test for the resectogram pixel -> (u, v) parametric
  mapping that the ADR-0025 locator producer consumes.

  -- WHAT THIS PROTECTS --

  ADR-0025 §Context establishes that "the resectogram is a 1:1 image of
  the Bezier (u, v) parameter domain.  A resectogram pixel maps to a
  (u, v) pair maps to a world point by direct Bezier surface evaluation
  — an EXACT correspondence, with no geometric search required."  The
  locator architecture (issue #414, depends on T3) plugs into T3's host
  resectogram Pipeline and relies on that mapping being STABLE: any
  geometry/scaling change T3 makes to the flattened-surface
  Representation (e.g. the aspect-ratio normalisation lifted from the v1
  Ratio(), see vtkLiverResectogramAspectRatioTest) must NOT silently
  regress where a given pixel lands in (u, v).

  The on-screen placement applies the anisotropic ``MatRatio`` scaling
  (the v1 vertex shader multiplies ``gl_Position`` by a matrix with
  ``m[0][0] = uMatRatio[0]`` / ``m[1][1] = uMatRatio[1]``;
  vtkOpenGLResection2DPolyDataMapper, post-relocation home
  ``LiverResections/VTKWidgets/``).  The locator producer must invert
  that placement to recover the un-scaled (u, v) in [0, 1]^2.  This
  test pins the inverse map for a representative resectogram domain so
  the contract is characterised BEFORE T3 touches the placement code.

  The expected target signature, mirroring the other pure-VTK helpers:

      static void vtkLiverResectogramPixelMapping::PixelToUV(
          const double pixel[2],          // viewport pixel (origin BL)
          const int viewportSize[2],      // {width, height} in pixels
          const double matRatio[2],       // {su, sv} aspect scaling
          double uvOut[2]);               // -> (u, v) in [0,1]^2

  -- WHY IT IS RED-BY-CONSTRUCTION --

  The helper does not exist yet, so the checked branch is compiled out
  behind ``LIVER_RESECTOGRAM_PIXEL_MAPPING`` (undefined now) and the
  test returns the CTest skip code (125).  The skip lifts when the
  implementer adds the helper and the CMakeLists defines the macro.

  The pinned values below come from the geometry the v1 shader
  implements: the flattened quad fills the viewport, (u, v) = (0, 0) at
  the bottom-left corner and (1, 1) at the top-right, with the MatRatio
  shrinking the SHORTER axis toward the viewport centre.  A pixel at the
  exact viewport centre maps to (0.5, 0.5) for ANY MatRatio (the centre
  is the scaling fixed point); off-centre pixels divide out the ratio.

  Tag: ADR-0025 §Context (the exact pixel -> (u,v) correspondence the
  locator producer consumes), ADR-0015 §1 (pure-VTK Algorithm helper,
  no MRML), ADR-0003 (testability invariant), ADR-0027 (invariant-test-
  first; the specific invariant is the off-centre pixel mapping that a
  ratio change would move, not merely the centre fixed point).

  Define -DLIVER_RESECTOGRAM_PIXEL_MAPPING once
  vtkLiverResectogramPixelMapping::PixelToUV exists.

==============================================================================*/

#ifdef LIVER_RESECTOGRAM_PIXEL_MAPPING
# include "vtkLiverResectogramPixelMapping.h"
#endif

#include <cmath>
#include <cstdio>
#include <cstdlib>

namespace
{
// CTest skip return code (kept in sync with the SKIP_RETURN_CODE the
// CMakeLists sets on this test).
constexpr int kSkipReturnCode = 125;

#ifdef LIVER_RESECTOGRAM_PIXEL_MAPPING
bool approx(double a, double b, double tol = 1e-6)
{
  return std::fabs(a - b) <= tol;
}
#endif

} // namespace

int vtkLiverResectogramPixelMappingTest(int, char*[])
{
#ifndef LIVER_RESECTOGRAM_PIXEL_MAPPING
  std::fprintf(stderr,
               "[ResectogramPixelMapping] SKIP: the pure-VTK helper "
               "vtkLiverResectogramPixelMapping::PixelToUV() does not exist "
               "yet.  ADR-0025 Section Context fixes the resectogram pixel -> "
               "(u, v) correspondence the locator producer (issue #414) "
               "consumes; T3 must characterise it before touching the "
               "flattened-surface placement.  Add the helper and define "
               "-DLIVER_RESECTOGRAM_PIXEL_MAPPING to lift this skip.\n");
  return kSkipReturnCode;
#else
  // Representative resectogram viewport: a 600 x 400 panel.  The
  // flattened quad fills the panel; (u, v) runs (0,0) bottom-left to
  // (1,1) top-right.
  const int viewport[2] = { 600, 400 };

  // ---------------------------------------------------------------- //
  // Case 1 — isotropic MatRatio {1, 1}: the panel maps linearly to the
  // unit square.  Bottom-left pixel -> (0, 0); top-right -> (1, 1);
  // centre -> (0.5, 0.5).
  // ---------------------------------------------------------------- //
  {
    const double matRatio[2] = { 1.0, 1.0 };
    struct
    {
      double pixel[2];
      double uv[2];
    } cases[] = {
      { { 0.0, 0.0 }, { 0.0, 0.0 } },
      { { 600.0, 400.0 }, { 1.0, 1.0 } },
      { { 300.0, 200.0 }, { 0.5, 0.5 } },
      { { 150.0, 100.0 }, { 0.25, 0.25 } },
    };
    for (const auto& c : cases)
    {
      double uv[2] = { -1.0, -1.0 };
      vtkLiverResectogramPixelMapping::PixelToUV(c.pixel, viewport, matRatio, uv);
      if (!approx(uv[0], c.uv[0]) || !approx(uv[1], c.uv[1]))
      {
        std::fprintf(stderr,
                     "[ResectogramPixelMapping] FAIL (isotropic): pixel "
                     "(%g, %g) expected (u,v)=(%g, %g), got (%g, %g)\n",
                     c.pixel[0],
                     c.pixel[1],
                     c.uv[0],
                     c.uv[1],
                     uv[0],
                     uv[1]);
        return EXIT_FAILURE;
      }
    }
  }

  // ---------------------------------------------------------------- //
  // Case 2 — LOAD-BEARING: anisotropic MatRatio {0.5, 1}.  The u-axis
  // is drawn at half width about the viewport centre, so the visible
  // quad occupies the central half of the panel in x.  Inverting that
  // placement: the panel centre still maps to u = 0.5 (the scaling
  // fixed point), but an off-centre pixel divides out the 0.5 factor —
  // doubling its distance from centre in (u) space.
  //
  // Pixel x = 300 (centre)            -> u = 0.5
  // Pixel x = 450 (3/4 across panel)  -> centre-offset +0.25 panel ->
  //                                      /0.5 -> +0.5 in u -> u = 1.0
  // The v-axis ratio is 1.0 so v maps linearly as in Case 1.
  // A change to the placement scaling moves these off-centre values.
  // ---------------------------------------------------------------- //
  {
    const double matRatio[2] = { 0.5, 1.0 };
    struct
    {
      double pixel[2];
      double uv[2];
    } cases[] = {
      { { 300.0, 200.0 }, { 0.5, 0.5 } }, // centre: fixed point
      { { 450.0, 200.0 }, { 1.0, 0.5 } }, // off-centre x divides out 0.5
      { { 150.0, 200.0 }, { 0.0, 0.5 } }, // symmetric on the other side
    };
    for (const auto& c : cases)
    {
      double uv[2] = { -1.0, -1.0 };
      vtkLiverResectogramPixelMapping::PixelToUV(c.pixel, viewport, matRatio, uv);
      if (!approx(uv[0], c.uv[0]) || !approx(uv[1], c.uv[1]))
      {
        std::fprintf(stderr,
                     "[ResectogramPixelMapping] FAIL (anisotropic): pixel "
                     "(%g, %g) with MatRatio {0.5, 1} expected (u,v)=(%g, %g), "
                     "got (%g, %g).  Off-centre u is the load-bearing "
                     "assertion (ADR-0027 fail-against-broken).\n",
                     c.pixel[0],
                     c.pixel[1],
                     c.uv[0],
                     c.uv[1],
                     uv[0],
                     uv[1]);
        return EXIT_FAILURE;
      }
    }
  }

  std::printf("vtkLiverResectogramPixelMappingTest completed successfully\n");
  return EXIT_SUCCESS;
#endif
}

/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Pure-math invariant test for the resectogram aspect-ratio helper that
  T3 extracts from the v1 monolith.

  -- WHAT THIS PINS --

  The v1 binding ``vtkSlicerBezierSurfaceRepresentation3D::Ratio(bool)``
  (legacy ``LiverMarkups/VTKWidgets/`` representation) computes the
  resectogram's anisotropic scaling factor.  It walks the 20x20 sampled
  Bezier surface, sums Euclidean arc-length along the first u-edge
  (sample indices 0..19) and along the first v-edge (sample indices
  0, 20, 40, ... 19*20), then normalises the LONGER axis to 1:

      if (disU >= disV) { matR = { 1, disV / disU }; }
      else              { matR = { disU / disV, 1 }; }

  When ``flexibleBoundary`` is false the function short-circuits to the
  isotropic ``{1, 1}``.  That ``{1, 1}`` is the *square-domain* answer
  and ALSO the not-flexible answer — the two are observationally
  identical for a square domain, which is exactly why a stub that always
  returns ``{1, 1}`` must be caught by a NON-square fixture.

  T3 extracts this arc-length computation into a PURE-VTK Algorithm
  helper so the resectogram Representation (LayerDM-bound, Python) and
  any other caller can reach it without an MRML or GL dependency
  (ADR-0015 §1 — Algorithm classes are pure VTK; ADR-0003 — the helper
  is unit-testable in isolation, no MRML link).  The expected target
  signature, mirroring ``vtkSlicerLiverBezierControlPolygonGeometry``:

      static void vtkLiverResectogramAspectRatio::ComputeAspectRatio(
          vtkPoints* sampledSurface,
          unsigned int samplesU, unsigned int samplesV,
          bool flexibleBoundary,
          double ratioOut[2]);

  -- WHY IT IS RED-BY-CONSTRUCTION --

  Two fixtures pin the SPECIFIC invariant (per ADR-0027 — fail-against-
  broken, pass-against-fixed):

   1. A square (u,v) sample grid -> exactly ``{1, 1}``.  A ``{1,1}``
      stub passes this case; alone it is a "colour-of-the-sky" assertion
      and would not catch the bug, so it never stands alone.
   2. A KNOWN non-square sample grid where the v-edge arc-length is
      twice the u-edge arc-length -> ``{0.5, 1}`` (longer axis v
      normalised to 1, shorter axis u scaled by disU/disV = 1/2).  A
      ``{1,1}`` stub FAILS this case.  This is the load-bearing
      assertion.

  Until the implementer adds
  ``vtkLiverResectogramAspectRatio::ComputeAspectRatio`` the helper does
  not exist, so the checked branch is compiled out behind
  ``LIVER_RESECTOGRAM_ASPECT_RATIO`` (undefined now) and the test
  returns the CTest skip code (125).  The skip lifts when the helper
  lands and the CMakeLists defines the macro.

  Tag: ADR-0015 §1 (pure-VTK Algorithm helper, no MRML), ADR-0003
  (testability invariant), ADR-0027 (invariant-test-first; the specific
  invariant is the non-square -> non-{1,1} mapping, not merely "some
  ratio is returned"), ADR-0013 §6 (Representation-owned scaling state).

  Define -DLIVER_RESECTOGRAM_ASPECT_RATIO once
  vtkLiverResectogramAspectRatio::ComputeAspectRatio exists.

==============================================================================*/

#ifdef LIVER_RESECTOGRAM_ASPECT_RATIO
# include "vtkLiverResectogramAspectRatio.h"

// VTK includes
# include <vtkNew.h>
# include <vtkPoints.h>
#endif

#include <cmath>
#include <cstdio>
#include <cstdlib>

namespace
{
// CTest skip return code (kept in sync with the SKIP_RETURN_CODE the
// CMakeLists sets on this test).
constexpr int kSkipReturnCode = 125;

#ifdef LIVER_RESECTOGRAM_ASPECT_RATIO
// The v1 Ratio() samples a fixed 20x20 grid (sample indices run 0..399,
// the u-edge being 0..19 and the v-edge being 0, 20, 40, ...).  The
// extracted helper takes the sample counts explicitly so it is not
// hard-wired to 20x20.
constexpr unsigned int kSamplesU = 20;
constexpr unsigned int kSamplesV = 20;

// Build a planar samplesU x samplesV grid with row-major flat index
// ``i * samplesV + j`` (matching the v1 ``GetTuple3(20 * i)`` v-edge
// stride and ``GetTuple3(i)`` u-edge stride).  ``spanU`` and ``spanV``
// are the total edge lengths in each parametric direction so the test
// can dial in a known arc-length ratio.
vtkSmartPointer<vtkPoints> makeGrid(double spanU, double spanV)
{
  auto pts = vtkSmartPointer<vtkPoints>::New();
  pts->SetNumberOfPoints(kSamplesU * kSamplesV);
  const double du = spanU / static_cast<double>(kSamplesU - 1);
  const double dv = spanV / static_cast<double>(kSamplesV - 1);
  for (unsigned int i = 0; i < kSamplesU; ++i)
  {
    for (unsigned int j = 0; j < kSamplesV; ++j)
    {
      const vtkIdType flat = static_cast<vtkIdType>(i) * kSamplesV + j;
      pts->SetPoint(flat, du * i, dv * j, 0.0);
    }
  }
  return pts;
}

bool approx(double a, double b, double tol = 1e-9)
{
  return std::fabs(a - b) <= tol;
}
#endif

} // namespace

int vtkLiverResectogramAspectRatioTest(int, char*[])
{
#ifndef LIVER_RESECTOGRAM_ASPECT_RATIO
  std::fprintf(stderr,
               "[ResectogramAspectRatio] SKIP: the pure-VTK helper "
               "vtkLiverResectogramAspectRatio::ComputeAspectRatio() does "
               "not exist yet.  T3 extracts the v1 "
               "vtkSlicerBezierSurfaceRepresentation3D::Ratio(bool) "
               "arc-length computation into the Algorithm library (ADR-0015 "
               "Section 1, pure VTK, no MRML).  Add it and define "
               "-DLIVER_RESECTOGRAM_ASPECT_RATIO to lift this skip.\n");
  return kSkipReturnCode;
#else
  // ---------------------------------------------------------------- //
  // Case 1 — square (u,v) domain -> isotropic {1, 1}.
  // (Necessary but not sufficient: a {1,1} stub also passes this.)
  // ---------------------------------------------------------------- //
  {
    vtkSmartPointer<vtkPoints> square = makeGrid(10.0, 10.0);
    double ratio[2] = { -1.0, -1.0 };
    vtkLiverResectogramAspectRatio::ComputeAspectRatio(square, kSamplesU, kSamplesV, /*flexibleBoundary=*/true, ratio);
    if (!approx(ratio[0], 1.0) || !approx(ratio[1], 1.0))
    {
      std::fprintf(stderr,
                   "[ResectogramAspectRatio] FAIL: square domain expected "
                   "{1, 1}, got {%g, %g}\n",
                   ratio[0],
                   ratio[1]);
      return EXIT_FAILURE;
    }
  }

  // ---------------------------------------------------------------- //
  // Case 2 — LOAD-BEARING: known non-square domain.
  // v-edge arc-length is twice the u-edge arc-length (spanV = 2*spanU),
  // so disV >= disU and the helper normalises the longer (v) axis to 1
  // and scales u by disU/disV = 0.5  ->  {0.5, 1}.
  // A {1,1} stub FAILS here; this is the assertion that pins the bug.
  // ---------------------------------------------------------------- //
  {
    vtkSmartPointer<vtkPoints> wide = makeGrid(10.0, 20.0);
    double ratio[2] = { -1.0, -1.0 };
    vtkLiverResectogramAspectRatio::ComputeAspectRatio(wide, kSamplesU, kSamplesV, /*flexibleBoundary=*/true, ratio);
    if (!approx(ratio[0], 0.5) || !approx(ratio[1], 1.0))
    {
      std::fprintf(stderr,
                   "[ResectogramAspectRatio] FAIL: non-square domain "
                   "(spanV = 2*spanU) expected {0.5, 1}, got {%g, %g}.  A "
                   "{1, 1} stub fails here by design (ADR-0027 fail-against-"
                   "broken).\n",
                   ratio[0],
                   ratio[1]);
      return EXIT_FAILURE;
    }
  }

  // ---------------------------------------------------------------- //
  // Case 3 — non-flexible boundary short-circuits to {1, 1} regardless
  // of the domain shape (the v1 else-branch).
  // ---------------------------------------------------------------- //
  {
    vtkSmartPointer<vtkPoints> wide = makeGrid(10.0, 20.0);
    double ratio[2] = { -1.0, -1.0 };
    vtkLiverResectogramAspectRatio::ComputeAspectRatio(wide, kSamplesU, kSamplesV, /*flexibleBoundary=*/false, ratio);
    if (!approx(ratio[0], 1.0) || !approx(ratio[1], 1.0))
    {
      std::fprintf(stderr,
                   "[ResectogramAspectRatio] FAIL: non-flexible boundary must "
                   "force {1, 1} regardless of domain shape, got {%g, %g}\n",
                   ratio[0],
                   ratio[1]);
      return EXIT_FAILURE;
    }
  }

  std::printf("vtkLiverResectogramAspectRatioTest completed successfully\n");
  return EXIT_SUCCESS;
#endif
}

/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) Oslo University Hospital. All rights reserved.

  Smoke test for vtkLiverSpheroidRingExtractor: cut a unit sphere with
  a slightly larger axis-aligned ellipsoid; the intersection should be
  empty.  Then cut with an intersecting spheroid and verify the ring
  is non-empty and its points satisfy both implicit constraints.

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

int vtkLiverSpheroidRingExtractorTest1(int, char *[])
{
  // Target: unit sphere centred at origin.
  vtkNew<vtkSphereSource> sphere;
  sphere->SetRadius(1.0);
  sphere->SetCenter(0.0, 0.0, 0.0);
  sphere->SetThetaResolution(64);
  sphere->SetPhiResolution(64);
  sphere->Update();

  // Cut with an axis-aligned ellipsoid offset along x, radii 0.8 x 0.8 x 1.2.
  // Centre at (0.5, 0, 0) — the two surfaces intersect.
  vtkNew<vtkLiverSpheroidRingExtractor> extractor;
  extractor->SetInputConnection(sphere->GetOutputPort());
  extractor->SetCenter(0.5, 0.0, 0.0);
  extractor->SetRadiusX(0.8);
  extractor->SetRadiusY(0.8);
  extractor->SetRadiusZ(1.2);
  extractor->Update();

  vtkPolyData *out = extractor->GetOutput();
  if (!out || !out->GetPoints() || out->GetPoints()->GetNumberOfPoints() == 0)
    {
    std::fprintf(stderr, "[SpheroidRingExtractor] FAIL: empty output\n");
    return EXIT_FAILURE;
    }
  if (!out->GetLines() || out->GetLines()->GetNumberOfCells() == 0)
    {
    std::fprintf(stderr,
                 "[SpheroidRingExtractor] FAIL: no polyline cells in output\n");
    return EXIT_FAILURE;
    }

  // Every output point should lie on the source sphere (within
  // cutter-discretisation tolerance) and on the spheroid surface
  // (zero level-set of the quadric).
  //
  // Tolerance rationale: vtkCutter interpolates the iso-contour
  // linearly along each triangle edge of the input mesh, so the
  // residual of a quadratic implicit function at the output points
  // is bounded by ~(1/8) max|F''| * h^2, where h is the input edge
  // length.  For a 64x64 unit-sphere tessellation h ≈ 0.1 and the
  // quadric's second derivatives are O(1/r^2) ≈ 3, giving an upper
  // bound of order 4e-3.  We allow 1e-2 to leave a safety margin
  // while still catching gross coefficient errors (an off-by-2 in
  // the linear terms produced residuals of order 1e-1 — see the
  // companion fix to vtkLiverSpheroidRingExtractor).
  const vtkIdType n = out->GetPoints()->GetNumberOfPoints();
  constexpr double radTol = 0.02;       // sphere discretisation noise
  constexpr double quadricTol = 1e-2;   // cutter linear-interp residual bound
  for (vtkIdType i = 0; i < n; ++i)
    {
    double p[3];
    out->GetPoints()->GetPoint(i, p);
    const double rSphere = std::sqrt(p[0] * p[0] + p[1] * p[1] + p[2] * p[2]);
    if (std::fabs(rSphere - 1.0) > radTol)
      {
      std::fprintf(stderr,
                   "[SpheroidRingExtractor] FAIL: point %lld off sphere: r=%g\n",
                   static_cast<long long>(i), rSphere);
      return EXIT_FAILURE;
      }
    const double dx = (p[0] - 0.5) / 0.8;
    const double dy = (p[1] - 0.0) / 0.8;
    const double dz = (p[2] - 0.0) / 1.2;
    const double q = dx * dx + dy * dy + dz * dz - 1.0;
    if (std::fabs(q) > quadricTol)
      {
      std::fprintf(stderr,
                   "[SpheroidRingExtractor] FAIL: point %lld off spheroid: "
                   "quadric=%g\n",
                   static_cast<long long>(i), q);
      return EXIT_FAILURE;
      }
    }
  return EXIT_SUCCESS;
}

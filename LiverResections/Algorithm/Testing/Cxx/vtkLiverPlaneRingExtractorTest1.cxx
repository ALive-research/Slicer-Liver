/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Smoke test for vtkLiverPlaneRingExtractor: cut a unit sphere with the
  z=0 plane, assert the output is a non-empty closed polyline whose
  points all lie on the plane (within numerical tolerance) and on the
  unit sphere (radius 1).

==============================================================================*/

#include "vtkLiverPlaneRingExtractor.h"

// VTK includes
#include <vtkCellArray.h>
#include <vtkNew.h>
#include <vtkPoints.h>
#include <vtkPolyData.h>
#include <vtkSphereSource.h>

#include <cmath>
#include <cstdio>
#include <cstdlib>

int vtkLiverPlaneRingExtractorTest1(int, char *[])
{
  vtkNew<vtkSphereSource> sphere;
  sphere->SetRadius(1.0);
  sphere->SetCenter(0.0, 0.0, 0.0);
  sphere->SetThetaResolution(64);
  sphere->SetPhiResolution(64);
  sphere->Update();

  vtkNew<vtkLiverPlaneRingExtractor> extractor;
  extractor->SetInputConnection(sphere->GetOutputPort());
  extractor->SetOrigin(0.0, 0.0, 0.0);
  extractor->SetNormal(0.0, 0.0, 1.0);
  extractor->Update();

  vtkPolyData *out = extractor->GetOutput();
  if (!out || !out->GetPoints() || out->GetPoints()->GetNumberOfPoints() == 0)
    {
    std::fprintf(stderr, "[PlaneRingExtractor] FAIL: empty output\n");
    return EXIT_FAILURE;
    }
  if (!out->GetLines() || out->GetLines()->GetNumberOfCells() == 0)
    {
    std::fprintf(stderr,
                 "[PlaneRingExtractor] FAIL: no polyline cells in output\n");
    return EXIT_FAILURE;
    }

  // Every point should sit on the z=0 plane and on the unit sphere.
  const vtkIdType n = out->GetPoints()->GetNumberOfPoints();
  // Cutter discretisation tolerance — sphere is faceted with 64x64 quads
  // so the great circle is approximated by a polygon whose vertices may
  // sit just inside the sphere by up to ~1% of the radius.
  constexpr double radTol = 0.02;
  // The cutting plane is exact, but stripper's join can interpolate
  // segment endpoints; ~1e-10 leaves headroom over float32 dust.
  constexpr double planeTol = 1e-10;
  for (vtkIdType i = 0; i < n; ++i)
    {
    double p[3];
    out->GetPoints()->GetPoint(i, p);
    if (std::fabs(p[2]) > planeTol)
      {
      std::fprintf(stderr,
                   "[PlaneRingExtractor] FAIL: point %lld off plane: z=%g\n",
                   static_cast<long long>(i), p[2]);
      return EXIT_FAILURE;
      }
    const double r = std::sqrt(p[0] * p[0] + p[1] * p[1]);
    if (std::fabs(r - 1.0) > radTol)
      {
      std::fprintf(stderr,
                   "[PlaneRingExtractor] FAIL: point %lld off circle: r=%g\n",
                   static_cast<long long>(i), r);
      return EXIT_FAILURE;
      }
    }
  return EXIT_SUCCESS;
}

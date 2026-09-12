/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

==============================================================================*/

// Tests for vtkLiverPoissonSurfaceReconstruction (ADR-0040 phase 3).

#include "vtkLiverPoissonSurfaceReconstruction.h"

#include <vtkCellArray.h>
#include <vtkDataArray.h>
#include <vtkFloatArray.h>
#include <vtkImplicitPolyDataDistance.h>
#include <vtkMath.h>
#include <vtkNew.h>
#include <vtkPointData.h>
#include <vtkPoints.h>
#include <vtkPolyData.h>
#include <vtkSphereSource.h>
#include <vtkTestingOutputWindow.h>

#include <cmath>
#include <iostream>

namespace
{

const double SphereRadius = 50.0;
const double SphereCentre[3] = { 10.0, -20.0, 5.0 };

/// An oriented cloud sampling a sphere, off the origin and at a
/// clinical-ish scale so the test would catch an adapter that only works
/// in PSR's internal normalised cube.
void MakeSphereCloud(vtkPolyData* cloud, int nTheta = 60, int nPhi = 120)
{
  vtkNew<vtkPoints> points;
  vtkNew<vtkFloatArray> normals;
  normals->SetNumberOfComponents(3);
  normals->SetName("Normals");

  for (int i = 1; i < nTheta; i++)
  {
    const double theta = vtkMath::Pi() * i / nTheta;
    for (int j = 0; j < nPhi; j++)
    {
      const double phi = 2.0 * vtkMath::Pi() * j / nPhi;
      const double n[3] = { std::sin(theta) * std::cos(phi), std::sin(theta) * std::sin(phi), std::cos(theta) };
      points->InsertNextPoint(SphereCentre[0] + SphereRadius * n[0], SphereCentre[1] + SphereRadius * n[1], SphereCentre[2] + SphereRadius * n[2]);
      normals->InsertNextTuple3(n[0], n[1], n[2]);
    }
  }

  cloud->SetPoints(points);
  cloud->GetPointData()->SetNormals(normals);
}

bool TestDefaultDepthIsSeven()
{
  const int depth = vtkLiverPoissonSurfaceReconstruction::GetDefaultDepth();
  std::cout << "default depth: " << depth << std::endl;
  if (depth != 7)
  {
    // ADR-0040 §Conformance: 7, not upstream's 8.  Phase 1 measured 8
    // and 9 tracking a CT-resolution liver WORSE than 7, because past a
    // point the extra resolution fits the labelmap's voxel staircase
    // rather than the anatomy.  If this assertion is being changed,
    // fresh measurement belongs in the same commit.
    std::cerr << "FAIL: default depth is " << depth << ", expected 7 (ADR-0040)" << std::endl;
    return false;
  }
  return true;
}

bool TestReconstructsTheSphere()
{
  vtkNew<vtkPolyData> cloud;
  MakeSphereCloud(cloud);

  vtkNew<vtkPolyData> surface;
  if (!vtkLiverPoissonSurfaceReconstruction::Reconstruct(cloud, vtkLiverPoissonSurfaceReconstruction::GetDefaultDepth(), surface))
  {
    std::cerr << "FAIL: Reconstruct returned false on a valid cloud" << std::endl;
    return false;
  }
  if (surface->GetNumberOfPoints() == 0 || surface->GetNumberOfPolys() == 0)
  {
    std::cerr << "FAIL: the reconstruction is empty" << std::endl;
    return false;
  }

  // ------------------------------------------------------------------
  // Direction 1: reconstruction -> analytic sphere.  Closed form, so no
  // tolerance is spent on a locator's approximation.
  // ------------------------------------------------------------------
  double worstOut = 0.0;
  double meanOut = 0.0;
  for (vtkIdType i = 0; i < surface->GetNumberOfPoints(); i++)
  {
    double p[3];
    surface->GetPoint(i, p);
    const double r = std::sqrt(vtkMath::Distance2BetweenPoints(p, SphereCentre));
    const double d = std::abs(r - SphereRadius);
    worstOut = std::max(worstOut, d);
    meanOut += d;
  }
  meanOut /= surface->GetNumberOfPoints();

  // ------------------------------------------------------------------
  // Direction 2: analytic sphere -> reconstruction.  ADR-0040 makes this
  // direction mandatory, and it is the one that matters: direction 1
  // alone cannot see PSR OMITTING a region.  Every point it did produce
  // could sit perfectly on the sphere while half the sphere is missing.
  // ------------------------------------------------------------------
  vtkNew<vtkSphereSource> reference;
  reference->SetCenter(SphereCentre[0], SphereCentre[1], SphereCentre[2]);
  reference->SetRadius(SphereRadius);
  reference->SetThetaResolution(64);
  reference->SetPhiResolution(64);
  reference->Update();

  vtkNew<vtkImplicitPolyDataDistance> distanceToSurface;
  distanceToSurface->SetInput(surface);

  double worstIn = 0.0;
  double meanIn = 0.0;
  vtkPolyData* referenceMesh = reference->GetOutput();
  for (vtkIdType i = 0; i < referenceMesh->GetNumberOfPoints(); i++)
  {
    double p[3];
    referenceMesh->GetPoint(i, p);
    const double d = std::abs(distanceToSurface->EvaluateFunction(p));
    worstIn = std::max(worstIn, d);
    meanIn += d;
  }
  meanIn /= referenceMesh->GetNumberOfPoints();

  std::cout << "sphere: " << surface->GetNumberOfPoints() << " points, " << surface->GetNumberOfPolys() << " polys" << std::endl;
  std::cout << "  recon->analytic  mean " << meanOut << " worst " << worstOut << " mm" << std::endl;
  std::cout << "  analytic->recon  mean " << meanIn << " worst " << worstIn << " mm" << std::endl;

  // 1% of the radius either way.  Both directions share the bound
  // deliberately: a one-sided tolerance is how an omitted region hides.
  const double tolerance = 0.01 * SphereRadius;
  if (worstOut > tolerance || worstIn > tolerance)
  {
    std::cerr << "FAIL: symmetric distance exceeds " << tolerance << " mm" << std::endl;
    return false;
  }
  return true;
}

bool TestNormalsPointOutward()
{
  // Orientation is scale-free, so a coarse reconstruction answers the
  // question a fine one would, faster.
  vtkNew<vtkPolyData> cloud;
  MakeSphereCloud(cloud, 30, 60);

  vtkNew<vtkPolyData> surface;
  if (!vtkLiverPoissonSurfaceReconstruction::Reconstruct(cloud, 6, surface))
  {
    std::cerr << "FAIL: Reconstruct returned false" << std::endl;
    return false;
  }

  vtkDataArray* normals = surface->GetPointData()->GetNormals();
  if (!normals || normals->GetNumberOfTuples() != surface->GetNumberOfPoints())
  {
    std::cerr << "FAIL: the reconstruction carries no per-point normals" << std::endl;
    return false;
  }

  // On a sphere the outward normal is the radial direction, known in
  // closed form.  An INVERTED surface is otherwise indistinguishable
  // from a correct one by position alone -- and it renders black.
  double meanDot = 0.0;
  double worstDot = 1.0;
  for (vtkIdType i = 0; i < surface->GetNumberOfPoints(); i++)
  {
    double p[3];
    surface->GetPoint(i, p);
    double outward[3] = { p[0] - SphereCentre[0], p[1] - SphereCentre[1], p[2] - SphereCentre[2] };
    vtkMath::Normalize(outward);

    double n[3];
    normals->GetTuple(i, n);
    vtkMath::Normalize(n);

    const double dot = vtkMath::Dot(outward, n);
    meanDot += dot;
    worstDot = std::min(worstDot, dot);
  }
  meanDot /= surface->GetNumberOfPoints();

  std::cout << "normals: mean dot " << meanDot << ", worst " << worstDot << std::endl;
  if (meanDot < 0.95)
  {
    std::cerr << "FAIL: normals do not agree with the analytic outward direction" << std::endl;
    return false;
  }
  if (worstDot <= 0.0)
  {
    std::cerr << "FAIL: at least one normal points inward" << std::endl;
    return false;
  }
  return true;
}

bool TestDegenerateInputsYieldAnEmptySurface()
{
  // A COARSE cloud at a shallow depth: this test re-seeds the output
  // before every case, and the accuracy of those seeds is irrelevant --
  // only that they are non-empty.  Reusing the full-resolution fixture
  // here would spend half a minute of CI proving nothing extra.
  vtkNew<vtkPolyData> cloud;
  MakeSphereCloud(cloud, 20, 40);
  const int seedDepth = 5;

  vtkNew<vtkPolyData> surface;
  // Seed the output with a real reconstruction, so the checks below
  // prove the failure paths CLEAR it rather than merely not filling it.
  if (!vtkLiverPoissonSurfaceReconstruction::Reconstruct(cloud, seedDepth, surface))
  {
    std::cerr << "FAIL: could not seed the output" << std::endl;
    return false;
  }
  if (surface->GetNumberOfPoints() == 0)
  {
    std::cerr << "FAIL: seeding produced nothing to clear" << std::endl;
    return false;
  }

  struct Case
  {
    const char* Name;
    vtkPolyData* Cloud;
    int Depth;
  };

  vtkNew<vtkPolyData> emptyCloud;
  vtkNew<vtkPolyData> cloudWithoutNormals;
  {
    vtkNew<vtkPoints> points;
    points->InsertNextPoint(0.0, 0.0, 0.0);
    points->InsertNextPoint(1.0, 0.0, 0.0);
    cloudWithoutNormals->SetPoints(points);
  }

  const Case cases[] = {
    { "null cloud", nullptr, 7 }, { "empty cloud", emptyCloud, 7 }, { "cloud without normals", cloudWithoutNormals, 7 }, { "depth 0", cloud, 0 }, { "depth 15", cloud, 15 },
  };

  for (const Case& c : cases)
  {
    // Each rejection is EXPECTED to warn.  Asserting that -- rather than
    // merely silencing the driver's error-output check -- means a
    // rejection that goes quiet is itself a failure: an invalid input
    // that fails without saying why is the thing that makes a caller
    // hunt for a bug in their own data.
    TESTING_OUTPUT_ASSERT_WARNINGS_BEGIN();
    const bool reconstructed = vtkLiverPoissonSurfaceReconstruction::Reconstruct(c.Cloud, c.Depth, surface);
    TESTING_OUTPUT_ASSERT_WARNINGS_END();
    if (reconstructed)
    {
      std::cerr << "FAIL: " << c.Name << " returned true" << std::endl;
      return false;
    }
    if (surface->GetNumberOfPoints() != 0 || surface->GetNumberOfPolys() != 0)
    {
      std::cerr << "FAIL: " << c.Name << " left " << surface->GetNumberOfPoints() << " stale points" << std::endl;
      return false;
    }
    // Re-seed for the next case, so each one proves the failure path
    // CLEARS a populated output rather than finding it already empty.
    vtkLiverPoissonSurfaceReconstruction::Reconstruct(cloud, seedDepth, surface);
    TESTING_OUTPUT_RESET();
  }

  // A null output must be refused, not crash.
  TESTING_OUTPUT_ASSERT_WARNINGS_BEGIN();
  const bool reconstructedIntoNull = vtkLiverPoissonSurfaceReconstruction::Reconstruct(cloud, 7, nullptr);
  TESTING_OUTPUT_ASSERT_WARNINGS_END();
  if (reconstructedIntoNull)
  {
    std::cerr << "FAIL: a null output returned true" << std::endl;
    return false;
  }

  std::cout << "degenerate inputs: all " << (sizeof(cases) / sizeof(cases[0]) + 1) << " cases rejected with an empty output" << std::endl;
  return true;
}

} // namespace

int vtkLiverPoissonSurfaceReconstructionTest(int, char*[])
{
  if (!TestDefaultDepthIsSeven())
  {
    return EXIT_FAILURE;
  }
  if (!TestReconstructsTheSphere())
  {
    return EXIT_FAILURE;
  }
  if (!TestNormalsPointOutward())
  {
    return EXIT_FAILURE;
  }
  if (!TestDegenerateInputsYieldAnEmptySurface())
  {
    return EXIT_FAILURE;
  }

  std::cout << "vtkLiverPoissonSurfaceReconstructionTest passed" << std::endl;
  return EXIT_SUCCESS;
}

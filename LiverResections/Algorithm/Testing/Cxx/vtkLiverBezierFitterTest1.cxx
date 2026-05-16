/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) Oslo University Hospital. All rights reserved.

  Characterisation test for vtkLiverBezierFitter against the
  Python-pinned EXPECTED_BEZIER_CONTROL_POINTS from
  Testing/Python/unit/test_bezier_characterization.py.

  Re-captured 2026-05-16 at the production-correct Bernstein degree 3
  (4x4 = 16 control points); see vtkLiverAlgorithmTestFixtures.h and
  test_bezier_characterization.py docstrings for the degree-correction
  history.  ADR-0015 §3.

==============================================================================*/

#include "vtkLiverBezierFitter.h"
#include "vtkLiverAlgorithmTestFixtures.h"

// VTK includes
#include <vtkDoubleArray.h>
#include <vtkNew.h>
#include <vtkPoints.h>
#include <vtkPolyData.h>

#include <cstdio>
#include <cstdlib>

int vtkLiverBezierFitterTest1(int, char *[])
{
  using namespace vtkLiverAlgorithmTestFixtures;

  // Loosened from rtol=1e-12 because Eigen's MatrixXd::inverse() may
  // dispatch a different LAPACK kernel from NumPy's np.linalg.inv on
  // the 4x4 case, producing last-bit-of-double differences in the
  // ~1e-15 residuals (per ADR-0015 §Consequences "Numerical tolerance
  // is documented per test case where bit-equivalence is not
  // achievable").  rtol=1e-10 still pins the algebra cleanly while
  // leaving headroom for kernel dispatch noise.  The Python wrapper
  // test continues to assert at rtol=1e-12 against the Python path
  // and parameterises the C++ side at the same relaxed tolerance.
  constexpr double rtol = 1e-10;
  constexpr double atol = 1e-12;

  auto fx = makeBezierFixture();

  vtkNew<vtkDoubleArray> pointsArr;
  pointsArr->SetNumberOfComponents(1);
  pointsArr->SetNumberOfTuples(static_cast<vtkIdType>(fx.points.size()));
  for (size_t i = 0; i < fx.points.size(); ++i)
    {
    pointsArr->SetValue(static_cast<vtkIdType>(i), fx.points[i]);
    }

  vtkNew<vtkDoubleArray> basisU;
  basisU->SetNumberOfComponents(1);
  basisU->SetNumberOfTuples(static_cast<vtkIdType>(fx.basisU.size()));
  for (size_t i = 0; i < fx.basisU.size(); ++i)
    {
    basisU->SetValue(static_cast<vtkIdType>(i), fx.basisU[i]);
    }

  vtkNew<vtkDoubleArray> basisV;
  basisV->SetNumberOfComponents(1);
  basisV->SetNumberOfTuples(static_cast<vtkIdType>(fx.basisV.size()));
  for (size_t i = 0; i < fx.basisV.size(); ++i)
    {
    basisV->SetValue(static_cast<vtkIdType>(i), fx.basisV[i]);
    }

  vtkNew<vtkLiverBezierFitter> fitter;
  fitter->SetNumberOfSamples(4, 4);
  fitter->SetInputPoints(pointsArr);
  fitter->SetBasisU(basisU);
  fitter->SetBasisV(basisV);
  fitter->Update();

  const auto &cps = fitter->GetControlPoints();
  if (cps.size() != static_cast<size_t>(4) * 4 * 3)
    {
    std::fprintf(stderr, "[BezierFitter] FAIL: size %zu != 48\n", cps.size());
    return EXIT_FAILURE;
    }
  if (fitter->GetGridSize() != 4)
    {
    std::fprintf(stderr, "[BezierFitter] FAIL: GridSize %d != 4\n",
                 fitter->GetGridSize());
    return EXIT_FAILURE;
    }

  const auto &expected = expectedBezierControlPoints();
  size_t failIdx = 0;
  if (!allClose(cps.data(), expected.data(), cps.size(), rtol, atol, &failIdx))
    {
    printFailure("BezierFitter", cps.data(), expected.data(), cps.size(),
                 failIdx, rtol, atol);
    return EXIT_FAILURE;
    }

  // Verify the polydata output round-trips the same control points.
  vtkPolyData *out = fitter->GetOutput();
  if (!out || !out->GetPoints() || out->GetPoints()->GetNumberOfPoints() != 16)
    {
    std::fprintf(stderr,
                 "[BezierFitter] FAIL: output polydata missing or wrong size\n");
    return EXIT_FAILURE;
    }
  for (int i = 0; i < 4; ++i)
    {
    for (int j = 0; j < 4; ++j)
      {
      double p[3];
      out->GetPoints()->GetPoint(i * 4 + j, p);
      const size_t base = (i * 4 + j) * 3;
      if (p[0] != cps[base + 0] || p[1] != cps[base + 1] || p[2] != cps[base + 2])
        {
        std::fprintf(stderr,
                     "[BezierFitter] FAIL: polydata point (%d,%d) does not "
                     "match raw control-points vector\n", i, j);
        return EXIT_FAILURE;
        }
      }
    }

  return EXIT_SUCCESS;
}

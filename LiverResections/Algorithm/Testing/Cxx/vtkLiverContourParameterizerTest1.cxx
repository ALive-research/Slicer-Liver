/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Characterisation tests for vtkLiverContourParameterizer in EFD mode,
  pinning the EFD coefficients, the DC triple, and the inverse-transform
  reconstruction against the Python-pinned EXPECTED constants in
  Testing/Python/unit/test_bezier_characterization.py.

==============================================================================*/

#include "vtkLiverContourParameterizer.h"
#include "vtkLiverAlgorithmTestFixtures.h"

// VTK includes
#include <vtkDoubleArray.h>
#include <vtkNew.h>
#include <vtkPoints.h>
#include <vtkPolyData.h>

#include <cstdio>
#include <cstdlib>

namespace
{

int testEFDCoefficients(double rtol, double atol)
{
  using namespace vtkLiverAlgorithmTestFixtures;
  auto contour = makeContourFixture();
  const int nPts = static_cast<int>(contour.size() / 3);
  auto coeffs = vtkLiverContourParameterizer::ComputeEFDCoefficientsRaw(contour.data(), nPts, 8);
  if (coeffs.size() != 48)
  {
    std::fprintf(stderr, "[EFD] FAIL: size %zu != 48\n", coeffs.size());
    return EXIT_FAILURE;
  }
  const auto& expected = expectedEFDCoeffs();
  size_t failIdx = 0;
  if (!allClose(coeffs.data(), expected.data(), 48, rtol, atol, &failIdx))
  {
    printFailure("EFD", coeffs.data(), expected.data(), 48, failIdx, rtol, atol);
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}

int testDC(double rtol, double atol)
{
  using namespace vtkLiverAlgorithmTestFixtures;
  auto contour = makeContourFixture();
  const int nPts = static_cast<int>(contour.size() / 3);
  auto dc = vtkLiverContourParameterizer::ComputeDCCoefficientsRaw(contour.data(), nPts);
  if (dc.size() != 3)
  {
    std::fprintf(stderr, "[DC] FAIL: size %zu != 3\n", dc.size());
    return EXIT_FAILURE;
  }
  auto expected = expectedDC();
  size_t failIdx = 0;
  if (!allClose(dc.data(), expected.data(), 3, rtol, atol, &failIdx))
  {
    printFailure("DC", dc.data(), expected.data(), 3, failIdx, rtol, atol);
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}

int testInverseTransform(double rtol, double atol)
{
  using namespace vtkLiverAlgorithmTestFixtures;
  // Use the *pinned* EFD coefficients so this test isolates the
  // inverse-transform code path from any drift in the forward EFD.
  const auto& coeffs = expectedEFDCoeffs();
  const double locus[3] = { 0.1, 0.2, 0.3 };
  auto recon = vtkLiverContourParameterizer::InverseTransformRaw(coeffs.data(), /*harmonic=*/8, locus, /*nCoords=*/12);
  if (recon.size() != 36)
  {
    std::fprintf(stderr, "[InverseTransform] FAIL: size %zu != 36\n", recon.size());
    return EXIT_FAILURE;
  }
  const auto& expected = expectedInverseTransform();
  size_t failIdx = 0;
  if (!allClose(recon.data(), expected.data(), 36, rtol, atol, &failIdx))
  {
    printFailure("InverseTransform", recon.data(), expected.data(), 36, failIdx, rtol, atol);
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}

int testPipelineEFDMode()
{
  using namespace vtkLiverAlgorithmTestFixtures;
  // Drive the parameterizer through the algorithm pipeline and verify
  // the polydata output contains nCoords points.  The contour is now
  // supplied through the real port-0 vtkPolyData input per ADR-0015 §1
  // (issue #339 rewire) rather than via a member vtkDoubleArray setter.
  auto contour = makeContourFixture();
  const int nPts = static_cast<int>(contour.size() / 3);
  vtkNew<vtkPoints> contourPoints;
  contourPoints->SetDataTypeToDouble();
  contourPoints->SetNumberOfPoints(nPts);
  for (int i = 0; i < nPts; ++i)
  {
    contourPoints->SetPoint(i, contour[i * 3 + 0], contour[i * 3 + 1], contour[i * 3 + 2]);
  }
  vtkNew<vtkPolyData> contourPolyData;
  contourPolyData->SetPoints(contourPoints);

  vtkNew<vtkLiverContourParameterizer> param;
  param->SetMode(vtkLiverContourParameterizer::MODE_EFD);
  param->SetOrder(8);
  param->SetNumberOfReconstructionPoints(12);
  param->UseComputedLocusOff();
  param->SetLocus(0.1, 0.2, 0.3);
  param->SetInputData(contourPolyData);
  param->Update();

  if (param->GetReconstruction().size() != 36)
  {
    std::fprintf(stderr, "[Pipeline] FAIL: reconstruction size %zu != 36\n", param->GetReconstruction().size());
    return EXIT_FAILURE;
  }
  if (!param->GetOutput() || !param->GetOutput()->GetPoints() || param->GetOutput()->GetPoints()->GetNumberOfPoints() != 12)
  {
    std::fprintf(stderr, "[Pipeline] FAIL: output polydata missing or wrong size\n");
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}

} // namespace

int vtkLiverContourParameterizerTest1(int, char*[])
{
  // EFD math is direct closed-form harmonic sums; bit-equivalent to
  // the Python implementation up to last-bit-of-double on the per-segment
  // accumulation order.  rtol=1e-12 is the target; if a platform's
  // libm cos/sin dispatch differs from NumPy's the looser fallback below
  // can be used.  At capture time on x86_64 + glibc, rtol=1e-12 holds.
  constexpr double rtol = 1e-12;
  constexpr double atol = 1e-12;

  if (testEFDCoefficients(rtol, atol) != EXIT_SUCCESS)
  {
    return EXIT_FAILURE;
  }
  if (testDC(rtol, atol) != EXIT_SUCCESS)
  {
    return EXIT_FAILURE;
  }
  if (testInverseTransform(rtol, atol) != EXIT_SUCCESS)
  {
    return EXIT_FAILURE;
  }
  if (testPipelineEFDMode() != EXIT_SUCCESS)
  {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}

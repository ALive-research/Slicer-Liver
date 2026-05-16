/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) Oslo University Hospital. All rights reserved.

  Edge-case stress tests for vtkLiverBezierFitter (issue #335).
  Probes:
    - flat / collinear surface samples (degenerate)
    - high-frequency-oscillation surface samples
    - very few sample points (just enough for 4x4 basis)
    - condition-number observable on the Gram matrix Bu^T Bu

==============================================================================*/

#include "vtkLiverAlgorithmEdgeCaseHelpers.h"
#include "vtkLiverBezierFitter.h"

#include <vtkDoubleArray.h>
#include <vtkNew.h>
#include <vtkPoints.h>
#include <vtkPolyData.h>
#include <vtkTable.h>
#include <vtkTestingOutputWindow.h>

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <vector>

namespace
{

using vtkLiverAlgorithmEdgeCaseHelpers::conditionNumberSPD;
using vtkLiverAlgorithmEdgeCaseHelpers::makeBezierSample;
using vtkLiverAlgorithmEdgeCaseHelpers::SubTestReport;

vtkSmartPointer<vtkPolyData> packPoints(const std::vector<double>& flat, int Nu, int Nv)
{
  vtkSmartPointer<vtkPolyData> poly = vtkSmartPointer<vtkPolyData>::New();
  vtkNew<vtkPoints> pts;
  pts->SetDataTypeToDouble();
  pts->SetNumberOfPoints(static_cast<vtkIdType>(Nu) * Nv);
  for (int i = 0; i < Nu; ++i)
  {
    for (int j = 0; j < Nv; ++j)
    {
      const size_t base = (static_cast<size_t>(i) * Nv + j) * 3;
      pts->SetPoint(static_cast<vtkIdType>(i) * Nv + j, flat[base + 0], flat[base + 1], flat[base + 2]);
    }
  }
  poly->SetPoints(pts);
  return poly;
}

vtkSmartPointer<vtkTable> packBasis(const std::vector<double>& basis, int nRows, int M)
{
  vtkSmartPointer<vtkTable> table = vtkSmartPointer<vtkTable>::New();
  for (int j = 0; j < M; ++j)
  {
    vtkNew<vtkDoubleArray> col;
    col->SetNumberOfComponents(1);
    col->SetNumberOfTuples(nRows);
    for (int i = 0; i < nRows; ++i)
    {
      col->SetValue(i, basis[static_cast<size_t>(i) * M + j]);
    }
    table->AddColumn(col);
  }
  return table;
}

bool runFitter(int Nu, int Nv, const std::vector<double>& points, const std::vector<double>& basisU, const std::vector<double>& basisV, std::vector<double>& outCps)
{
  vtkNew<vtkLiverBezierFitter> fitter;
  fitter->SetNumberOfSamples(Nu, Nv);
  fitter->SetInputData(0, packPoints(points, Nu, Nv));
  fitter->SetInputData(1, packBasis(basisU, Nu, 4));
  fitter->SetInputData(2, packBasis(basisV, Nv, 4));
  fitter->Update();
  outCps = fitter->GetControlPoints();
  return outCps.size() == 48;
}

// Compute Bu^T Bu as a row-major std::vector for condition-number probing.
std::vector<double> gramMatrix(const std::vector<double>& basis, int nRows, int M)
{
  std::vector<double> G(static_cast<size_t>(M) * M, 0.0);
  for (int i = 0; i < M; ++i)
  {
    for (int j = 0; j < M; ++j)
    {
      double s = 0.0;
      for (int k = 0; k < nRows; ++k)
      {
        s += basis[static_cast<size_t>(k) * M + i] * basis[static_cast<size_t>(k) * M + j];
      }
      G[i * M + j] = s;
    }
  }
  return G;
}

//----------------------------------------------------------------------------
// FlatSurface — z(u, v) ≡ 0.  All control points should land on z = 0,
// the planar fit is exact.  Acceptance: |cps[2]| < 1e-12 for every cp.
void testFlatSurface(SubTestReport& r)
{
  std::vector<double> points, basisU, basisV;
  makeBezierSample(4, 4, [](double, double) { return 0.0; }, points, basisU, basisV);
  std::vector<double> cps;
  if (!runFitter(4, 4, points, basisU, basisV, cps))
  {
    r.fail("FlatSurface", "fitter did not produce 48 control values");
    return;
  }
  bool ok = true;
  for (int i = 0; i < 16; ++i)
  {
    if (std::fabs(cps[i * 3 + 2]) > 1e-12)
    {
      ok = false;
      break;
    }
  }
  if (ok)
  {
    r.pass("FlatSurface");
  }
  else
  {
    r.fail("FlatSurface", "non-planar control points on flat input");
  }
}

//----------------------------------------------------------------------------
// CollinearXOnly — z(u, v) = u (depends only on u).  The fit collapses
// to a 1-D Bezier curve along u; columns of the control grid should be
// identical (within tolerance).
void testCollinearXOnly(SubTestReport& r)
{
  std::vector<double> points, basisU, basisV;
  makeBezierSample(4, 4, [](double u, double) { return u; }, points, basisU, basisV);
  std::vector<double> cps;
  if (!runFitter(4, 4, points, basisU, basisV, cps))
  {
    r.fail("CollinearXOnly", "fitter did not produce 48 control values");
    return;
  }
  // For each row i, the z-coordinates of cps[i, 0..3, 2] should match.
  bool ok = true;
  for (int i = 0; i < 4 && ok; ++i)
  {
    const double z0 = cps[(i * 4 + 0) * 3 + 2];
    for (int j = 1; j < 4; ++j)
    {
      if (std::fabs(cps[(i * 4 + j) * 3 + 2] - z0) > 1e-9)
      {
        ok = false;
        break;
      }
    }
  }
  if (ok)
  {
    r.pass("CollinearXOnly");
  }
  else
  {
    r.fail("CollinearXOnly", "rows of z control points not constant");
  }
}

//----------------------------------------------------------------------------
// HighFrequencyOscillation — surface with rapid wiggle that exceeds the
// 4x4 Bernstein basis capacity.  The fit will smooth it heavily;
// acceptance: finite control points (no NaN / Inf), max z within
// the input amplitude bounds.
void testHighFrequencyOscillation(SubTestReport& r)
{
  std::vector<double> points, basisU, basisV;
  const double amp = 0.5;
  makeBezierSample(4, 4, [amp](double u, double v) { return amp * std::cos(20.0 * u) * std::cos(20.0 * v); }, points, basisU, basisV);
  std::vector<double> cps;
  if (!runFitter(4, 4, points, basisU, basisV, cps))
  {
    r.fail("HighFrequencyOscillation", "fitter did not produce 48 control values");
    return;
  }
  bool ok = true;
  for (int i = 0; i < 16; ++i)
  {
    const double z = cps[i * 3 + 2];
    if (!std::isfinite(z) || std::fabs(z) > 10.0 * amp)
    {
      ok = false;
      break;
    }
  }
  if (ok)
  {
    r.pass("HighFrequencyOscillation");
  }
  else
  {
    r.fail("HighFrequencyOscillation", "control points exploded or non-finite");
  }
}

//----------------------------------------------------------------------------
// MinimumSampleCount — 4x4 = 16 samples is *exactly* the minimum for a
// degree-3 Bernstein basis to be invertible.  Verify fit succeeds.
void testMinimumSampleCount(SubTestReport& r)
{
  std::vector<double> points, basisU, basisV;
  makeBezierSample(4, 4, [](double u, double v) { return u * v; }, points, basisU, basisV);
  std::vector<double> cps;
  if (runFitter(4, 4, points, basisU, basisV, cps))
  {
    r.pass("MinimumSampleCount");
  }
  else
  {
    r.fail("MinimumSampleCount", "fitter failed at minimum 4x4");
  }
}

//----------------------------------------------------------------------------
// ConditionNumberProbe — pass an oversampled 8x8 basis (well-conditioned)
// AND a "collapsed" 4x4 basis where two adjacent rows are nearly
// identical (so the Bernstein basis rows become near-linearly-dependent
// → high κ on Bu^T Bu).
//
// Per #335 the current Eigen::MatrixXd::inverse() (PartialPivLU) is the
// textbook unstable form.  The well-conditioned baseline must produce a
// reasonable κ (< 1e6); the collapsed input is expected to flag κ above
// the 1e8 alert threshold.  We DO NOT switch the algorithm to
// JacobiSVD here — characterisation only, see issue #356
// (https://github.com/ALive-research/Slicer-Liver/issues/356) for the
// proposed fix path (LLT/ColPivHouseholderQR on the Gram matrix).
void testConditionNumberProbe(SubTestReport& r)
{
  // Baseline: 8x8 uniform sampling, well-conditioned.
  std::vector<double> points8, basisU8, basisV8;
  makeBezierSample(8, 8, [](double u, double v) { return u * v; }, points8, basisU8, basisV8);
  const std::vector<double> Gu = gramMatrix(basisU8, 8, 4);
  const double kappaBaseline = conditionNumberSPD(Gu, 4);
  std::fprintf(stderr, "    note: baseline 8x8 Bu^T Bu condition number ≈ %.3e\n", kappaBaseline);
  if (!(std::isfinite(kappaBaseline) && kappaBaseline < 1e6))
  {
    r.fail("ConditionNumberProbe", "baseline 8x8 unexpectedly ill-conditioned: κ=" + std::to_string(kappaBaseline));
    return;
  }

  // Degenerate: 4x4 sampling with two collapsed rows.  Bernstein basis
  // at (0, eps, 2*eps, 1) has near-identical first three rows → Gram
  // matrix near-singular.  Build the basis manually.
  std::vector<double> badBasis(4 * 4, 0.0);
  const double samples[4] = { 0.0, 1e-8, 2e-8, 1.0 };
  auto bern = [](double t, double* out)
  {
    const double t1 = 1.0 - t;
    out[0] = t1 * t1 * t1;
    out[1] = 3.0 * t * t1 * t1;
    out[2] = 3.0 * t * t * t1;
    out[3] = t * t * t;
  };
  for (int i = 0; i < 4; ++i)
  {
    double b[4];
    bern(samples[i], b);
    for (int k = 0; k < 4; ++k)
    {
      badBasis[i * 4 + k] = b[k];
    }
  }
  const std::vector<double> Gbad = gramMatrix(badBasis, 4, 4);
  const double kappaBad = conditionNumberSPD(Gbad, 4);
  std::fprintf(stderr, "    note: collapsed-row Bu^T Bu condition number ≈ %.3e (>1e8 expected → sub-issue)\n", kappaBad);
  // Acceptance: condition number flags above threshold OR is +inf.
  // Either is the "this is degenerate; fix the inverse path" signal.
  if (kappaBad > 1e8)
  {
    r.pass("ConditionNumberProbe");
  }
  else
  {
    r.fail("ConditionNumberProbe", "collapsed Gram unexpectedly well-conditioned: κ=" + std::to_string(kappaBad));
  }
}

//----------------------------------------------------------------------------
// SinglePrecisionPoints — drive the fitter with a vtkFloatArray-backed
// vtkPoints; verify the GetPoint(i, p) into a double[3] conversion path
// is clean (i.e. the produced control points match the double-input
// case to within float precision).
void testSinglePrecisionPoints(SubTestReport& r)
{
  std::vector<double> points, basisU, basisV;
  makeBezierSample(4, 4, [](double u, double v) { return u * v; }, points, basisU, basisV);

  // Reference: double pipeline.
  std::vector<double> cpsRef;
  runFitter(4, 4, points, basisU, basisV, cpsRef);

  // Float-backed pipeline.
  vtkSmartPointer<vtkPolyData> poly = vtkSmartPointer<vtkPolyData>::New();
  vtkNew<vtkPoints> pts;
  pts->SetDataTypeToFloat();
  pts->SetNumberOfPoints(16);
  for (int i = 0; i < 4; ++i)
  {
    for (int j = 0; j < 4; ++j)
    {
      const size_t base = (static_cast<size_t>(i) * 4 + j) * 3;
      pts->SetPoint(static_cast<vtkIdType>(i) * 4 + j, static_cast<float>(points[base + 0]), static_cast<float>(points[base + 1]), static_cast<float>(points[base + 2]));
    }
  }
  poly->SetPoints(pts);
  vtkNew<vtkLiverBezierFitter> fitter;
  fitter->SetNumberOfSamples(4, 4);
  fitter->SetInputData(0, poly);
  fitter->SetInputData(1, packBasis(basisU, 4, 4));
  fitter->SetInputData(2, packBasis(basisV, 4, 4));
  fitter->Update();
  const auto& cpsFloat = fitter->GetControlPoints();
  if (cpsFloat.size() != 48)
  {
    r.fail("SinglePrecisionPoints", "no fitted output");
    return;
  }
  bool ok = true;
  for (size_t i = 0; i < 48; ++i)
  {
    if (std::fabs(cpsFloat[i] - cpsRef[i]) > 1e-6)
    {
      ok = false;
      break;
    }
  }
  if (ok)
  {
    r.pass("SinglePrecisionPoints");
  }
  else
  {
    r.fail("SinglePrecisionPoints", "float vs double control points differ by > 1e-6");
  }
}

//----------------------------------------------------------------------------
// MissingBasisPort — call Update() without setting BasisU.  Must trigger
// vtkErrorMacro and short-circuit.
void testMissingBasisPort(SubTestReport& r)
{
  TESTING_OUTPUT_RESET();
  std::vector<double> points, basisU, basisV;
  makeBezierSample(4, 4, [](double u, double v) { return u * v; }, points, basisU, basisV);
  vtkNew<vtkLiverBezierFitter> fitter;
  fitter->SetNumberOfSamples(4, 4);
  fitter->SetInputData(0, packPoints(points, 4, 4));
  // Port 1 deliberately unset.
  fitter->SetInputData(2, packBasis(basisV, 4, 4));
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  fitter->Update();
  TESTING_OUTPUT_ASSERT_ERRORS_END();
  r.pass("MissingBasisPort");
}

//----------------------------------------------------------------------------
// MismatchedBasisColumns — BasisU has 4 columns, BasisV has 3 columns.
// Must error and return 0.
void testMismatchedBasisColumns(SubTestReport& r)
{
  TESTING_OUTPUT_RESET();
  std::vector<double> points, basisU, basisV;
  makeBezierSample(4, 4, [](double u, double v) { return u * v; }, points, basisU, basisV);
  // Truncate basisV to 3 columns per row.
  std::vector<double> basisV3(4 * 3, 0.0);
  for (int i = 0; i < 4; ++i)
  {
    for (int k = 0; k < 3; ++k)
    {
      basisV3[i * 3 + k] = basisV[i * 4 + k];
    }
  }
  vtkNew<vtkLiverBezierFitter> fitter;
  fitter->SetNumberOfSamples(4, 4);
  fitter->SetInputData(0, packPoints(points, 4, 4));
  fitter->SetInputData(1, packBasis(basisU, 4, 4));
  fitter->SetInputData(2, packBasis(basisV3, 4, 3));
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  fitter->Update();
  TESTING_OUTPUT_ASSERT_ERRORS_END();
  r.pass("MismatchedBasisColumns");
}

} // namespace

int vtkLiverBezierFitterEdgeCasesTest(int, char*[])
{
  SubTestReport r;
  std::fprintf(stderr, "[BezierFitter edge cases]\n");

  testFlatSurface(r);
  testCollinearXOnly(r);
  testHighFrequencyOscillation(r);
  testMinimumSampleCount(r);
  testConditionNumberProbe(r);
  testSinglePrecisionPoints(r);
  testMissingBasisPort(r);
  testMismatchedBasisColumns(r);

  r.print("BezierFitter");
  return r.failed == 0 ? EXIT_SUCCESS : EXIT_FAILURE;
}

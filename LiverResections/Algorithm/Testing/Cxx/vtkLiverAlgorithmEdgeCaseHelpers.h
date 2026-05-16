/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) Oslo University Hospital. All rights reserved.

  Shared helpers for the edge-case stress tests (issue #335).  These
  are deliberately separate from vtkLiverAlgorithmTestFixtures.h so the
  bit-equivalence pin against PR #342's Python characterisation stays
  untouched: NEW fixtures + helpers live here; EXPECTED_* constants
  there remain bit-frozen.

  Provides:
   - Sub-test bookkeeping helpers (PASS / FAIL counters, scoped report).
   - Synthetic mesh constructors (sphere, cube, faceted-plate, NaN-poisoned).
   - Synthetic-ring constructors (circle, spiral, degenerate).
   - Condition-number estimator for small dense matrices via the ratio of
     min/max diagonal magnitude after a Cholesky factorisation (sufficient
     for flagging κ > 1e8 on Gram matrices; not a substitute for SVD).

  ADR-0015 §Context (bug-discovery motivation), ADR-0003 (characterisation
  discipline), ADR-0008 (testing strategy).

==============================================================================*/

#ifndef __vtkLiverAlgorithmEdgeCaseHelpers_h_
#define __vtkLiverAlgorithmEdgeCaseHelpers_h_

#include <vtkCellArray.h>
#include <vtkDoubleArray.h>
#include <vtkFloatArray.h>
#include <vtkNew.h>
#include <vtkPoints.h>
#include <vtkPolyData.h>
#include <vtkSmartPointer.h>
#include <vtkSphereSource.h>

#include <cmath>
#include <cstdio>
#include <limits>
#include <string>
#include <vector>

namespace vtkLiverAlgorithmEdgeCaseHelpers
{

constexpr double PI = 3.141592653589793238462643383279502884197;

//------------------------------------------------------------------------------
// Sub-test bookkeeping.  Each edge-case file's entry point owns one of
// these; sub-tests call PASS/FAIL on it and the entry point returns
// EXIT_FAILURE if any FAIL was recorded.
struct SubTestReport
{
  int passed = 0;
  int failed = 0;
  std::vector<std::string> failures;

  void pass(const char* name)
  {
    ++passed;
    std::fprintf(stderr, "  [PASS] %s\n", name);
  }

  void fail(const char* name, const std::string& why)
  {
    ++failed;
    failures.emplace_back(std::string(name) + ": " + why);
    std::fprintf(stderr, "  [FAIL] %s: %s\n", name, why.c_str());
  }

  int total() const { return passed + failed; }

  void print(const char* suite) const
  {
    std::fprintf(stderr, "\n[%s] %d / %d sub-tests passed (%d failed)\n", suite, passed, total(), failed);
    for (const auto& f : failures)
    {
      std::fprintf(stderr, "  - %s\n", f.c_str());
    }
  }
};

//------------------------------------------------------------------------------
// Synthetic mesh: unit sphere with a configurable tessellation density.
inline vtkSmartPointer<vtkPolyData> makeUnitSphere(int theta = 64, int phi = 64, double radius = 1.0)
{
  vtkNew<vtkSphereSource> sphere;
  sphere->SetRadius(radius);
  sphere->SetCenter(0.0, 0.0, 0.0);
  sphere->SetThetaResolution(theta);
  sphere->SetPhiResolution(phi);
  sphere->Update();
  vtkSmartPointer<vtkPolyData> out = vtkSmartPointer<vtkPolyData>::New();
  out->DeepCopy(sphere->GetOutput());
  return out;
}

//------------------------------------------------------------------------------
// A unit cube made of 12 triangles (6 quad faces, 2 tris each), centred at
// origin, side length 1.  Useful for "plane parallel to flat face" / "plane
// through a vertex" tests where a smooth sphere doesn't have a sharp edge.
inline vtkSmartPointer<vtkPolyData> makeUnitCube()
{
  vtkSmartPointer<vtkPolyData> poly = vtkSmartPointer<vtkPolyData>::New();
  vtkNew<vtkPoints> pts;
  pts->SetDataTypeToDouble();
  const double s = 0.5;
  // 8 corner vertices.
  const double coords[8][3] = {
    { -s, -s, -s }, { s, -s, -s }, { s, s, -s }, { -s, s, -s }, { -s, -s, s }, { s, -s, s }, { s, s, s }, { -s, s, s },
  };
  for (int i = 0; i < 8; ++i)
  {
    pts->InsertNextPoint(coords[i][0], coords[i][1], coords[i][2]);
  }
  poly->SetPoints(pts);
  // 6 faces, 2 triangles each — outward normals.
  const vtkIdType faces[12][3] = {
    { 0, 2, 1 }, { 0, 3, 2 }, // z = -s
    { 4, 5, 6 }, { 4, 6, 7 }, // z = +s
    { 0, 1, 5 }, { 0, 5, 4 }, // y = -s
    { 3, 7, 6 }, { 3, 6, 2 }, // y = +s
    { 0, 4, 7 }, { 0, 7, 3 }, // x = -s
    { 1, 2, 6 }, { 1, 6, 5 }, // x = +s
  };
  vtkNew<vtkCellArray> tris;
  for (int i = 0; i < 12; ++i)
  {
    tris->InsertNextCell(3);
    tris->InsertCellPoint(faces[i][0]);
    tris->InsertCellPoint(faces[i][1]);
    tris->InsertCellPoint(faces[i][2]);
  }
  poly->SetPolys(tris);
  return poly;
}

//------------------------------------------------------------------------------
// Wrap a flat (x, y, z) buffer into a vtkPolyData with points (no cells).
// This is the input-port format the post-#349 algorithms accept.
inline vtkSmartPointer<vtkPolyData> makePolyDataFromFlat(const std::vector<double>& flat)
{
  vtkSmartPointer<vtkPolyData> poly = vtkSmartPointer<vtkPolyData>::New();
  vtkNew<vtkPoints> pts;
  pts->SetDataTypeToDouble();
  const int n = static_cast<int>(flat.size() / 3);
  pts->SetNumberOfPoints(n);
  for (int i = 0; i < n; ++i)
  {
    pts->SetPoint(i, flat[i * 3 + 0], flat[i * 3 + 1], flat[i * 3 + 2]);
  }
  poly->SetPoints(pts);
  return poly;
}

//------------------------------------------------------------------------------
// Same as makePolyDataFromFlat but uses a single-precision vtkFloatArray as
// the points backend (cross-cutting #335 row "single-precision input").
inline vtkSmartPointer<vtkPolyData> makePolyDataFromFlatFloat(const std::vector<double>& flat)
{
  vtkSmartPointer<vtkPolyData> poly = vtkSmartPointer<vtkPolyData>::New();
  vtkNew<vtkPoints> pts;
  pts->SetDataTypeToFloat();
  const int n = static_cast<int>(flat.size() / 3);
  pts->SetNumberOfPoints(n);
  for (int i = 0; i < n; ++i)
  {
    pts->SetPoint(i, static_cast<float>(flat[i * 3 + 0]), static_cast<float>(flat[i * 3 + 1]), static_cast<float>(flat[i * 3 + 2]));
  }
  poly->SetPoints(pts);
  return poly;
}

//------------------------------------------------------------------------------
// Closed planar circle in z = 0 with N points (last duplicates first to
// close the loop, matching the Kuhl-Giardina contour convention).
inline std::vector<double> makePlanarCircle(int n, double radius = 1.0, double z = 0.0)
{
  std::vector<double> out(static_cast<size_t>(n + 1) * 3, 0.0);
  for (int k = 0; k < n; ++k)
  {
    const double theta = (2.0 * PI * static_cast<double>(k)) / static_cast<double>(n);
    out[k * 3 + 0] = radius * std::cos(theta);
    out[k * 3 + 1] = radius * std::sin(theta);
    out[k * 3 + 2] = z;
  }
  out[n * 3 + 0] = out[0];
  out[n * 3 + 1] = out[1];
  out[n * 3 + 2] = out[2];
  return out;
}

//------------------------------------------------------------------------------
// A closed contour that wobbles aggressively (high-frequency sine
// modulation) along a base circle.  Sets up the "high-frequency
// oscillation" / "FourierPower 0.9999 truncation" stress fixtures.
inline std::vector<double> makeHighFrequencyContour(int n, int harmonic, double amp = 0.2)
{
  std::vector<double> out(static_cast<size_t>(n + 1) * 3, 0.0);
  for (int k = 0; k < n; ++k)
  {
    const double theta = (2.0 * PI * static_cast<double>(k)) / static_cast<double>(n);
    out[k * 3 + 0] = std::cos(theta) + amp * std::cos(harmonic * theta);
    out[k * 3 + 1] = std::sin(theta) + amp * std::sin(harmonic * theta);
    out[k * 3 + 2] = 0.0;
  }
  out[n * 3 + 0] = out[0];
  out[n * 3 + 1] = out[1];
  out[n * 3 + 2] = out[2];
  return out;
}

//------------------------------------------------------------------------------
// Estimate the 2-norm condition number of a symmetric positive-definite
// matrix via the power iteration on (A) and (A^{-1}).  Returns NaN if
// the matrix is too small or non-PD.  Only used as an *observable*
// (per #335 numerical stability category); the threshold check picks
// up degenerate Gram matrices that the LU inverse will resolve poorly.
inline double conditionNumberSPD(const std::vector<double>& A, int n, int maxIter = 200, double tol = 1e-14)
{
  if (n < 1)
  {
    return std::numeric_limits<double>::quiet_NaN();
  }
  // Power iteration for the largest eigenvalue.
  std::vector<double> b(n, 1.0 / std::sqrt(static_cast<double>(n)));
  double lambdaMax = 0.0;
  for (int it = 0; it < maxIter; ++it)
  {
    std::vector<double> y(n, 0.0);
    for (int i = 0; i < n; ++i)
    {
      for (int j = 0; j < n; ++j)
      {
        y[i] += A[i * n + j] * b[j];
      }
    }
    double norm = 0.0;
    for (int i = 0; i < n; ++i)
    {
      norm += y[i] * y[i];
    }
    norm = std::sqrt(norm);
    if (norm == 0.0)
    {
      return std::numeric_limits<double>::infinity();
    }
    for (int i = 0; i < n; ++i)
    {
      y[i] /= norm;
    }
    const double diff = std::fabs(norm - lambdaMax);
    lambdaMax = norm;
    b = y;
    if (diff < tol * lambdaMax)
    {
      break;
    }
  }
  // Inverse power iteration for the smallest eigenvalue: solve A x = b
  // via Cholesky.  Bail with infinity if the Cholesky factorisation
  // breaks down (matrix not PD → "infinitely ill-conditioned" for our
  // purposes).
  std::vector<double> L(static_cast<size_t>(n) * n, 0.0);
  for (int i = 0; i < n; ++i)
  {
    for (int j = 0; j <= i; ++j)
    {
      double sum = A[i * n + j];
      for (int k = 0; k < j; ++k)
      {
        sum -= L[i * n + k] * L[j * n + k];
      }
      if (i == j)
      {
        if (sum <= 0.0)
        {
          return std::numeric_limits<double>::infinity();
        }
        L[i * n + i] = std::sqrt(sum);
      }
      else
      {
        L[i * n + j] = sum / L[j * n + j];
      }
    }
  }
  // Solve L y = b, then L^T x = y, iteratively.
  std::vector<double> v(n, 1.0 / std::sqrt(static_cast<double>(n)));
  double lambdaMin = 0.0;
  for (int it = 0; it < maxIter; ++it)
  {
    // Forward sub: L y = v.
    std::vector<double> y(n, 0.0);
    for (int i = 0; i < n; ++i)
    {
      double s = v[i];
      for (int k = 0; k < i; ++k)
      {
        s -= L[i * n + k] * y[k];
      }
      y[i] = s / L[i * n + i];
    }
    // Back sub: L^T x = y.
    std::vector<double> x(n, 0.0);
    for (int i = n - 1; i >= 0; --i)
    {
      double s = y[i];
      for (int k = i + 1; k < n; ++k)
      {
        s -= L[k * n + i] * x[k];
      }
      x[i] = s / L[i * n + i];
    }
    double norm = 0.0;
    for (int i = 0; i < n; ++i)
    {
      norm += x[i] * x[i];
    }
    norm = std::sqrt(norm);
    if (norm == 0.0)
    {
      return std::numeric_limits<double>::infinity();
    }
    for (int i = 0; i < n; ++i)
    {
      x[i] /= norm;
    }
    const double diff = std::fabs(1.0 / norm - lambdaMin);
    lambdaMin = 1.0 / norm;
    v = x;
    if (diff < tol * lambdaMin)
    {
      break;
    }
  }
  if (lambdaMin <= 0.0)
  {
    return std::numeric_limits<double>::infinity();
  }
  return lambdaMax / lambdaMin;
}

//------------------------------------------------------------------------------
// Build a uniform 4x4 sample fixture for the Bezier fitter at arbitrary
// surface samples.  Bernstein degree 3.  Mirrors the saddle fixture in
// vtkLiverAlgorithmTestFixtures.h but lets the caller supply a per-vertex
// z(u, v) lambda for the surface profile.
template <typename Fn>
inline void makeBezierSample(int Nu, int Nv, Fn zFn, std::vector<double>& points, std::vector<double>& basisU, std::vector<double>& basisV)
{
  points.assign(static_cast<size_t>(Nu) * Nv * 3, 0.0);
  basisU.assign(static_cast<size_t>(Nu) * 4, 0.0);
  basisV.assign(static_cast<size_t>(Nv) * 4, 0.0);
  std::vector<double> uSamples(Nu), vSamples(Nv);
  for (int i = 0; i < Nu; ++i)
  {
    uSamples[i] = (Nu == 1) ? 0.0 : static_cast<double>(i) / static_cast<double>(Nu - 1);
  }
  for (int j = 0; j < Nv; ++j)
  {
    vSamples[j] = (Nv == 1) ? 0.0 : static_cast<double>(j) / static_cast<double>(Nv - 1);
  }
  auto bern = [](double t, double* out)
  {
    const double t1 = 1.0 - t;
    out[0] = t1 * t1 * t1;
    out[1] = 3.0 * t * t1 * t1;
    out[2] = 3.0 * t * t * t1;
    out[3] = t * t * t;
  };
  for (int i = 0; i < Nu; ++i)
  {
    double b[4];
    bern(uSamples[i], b);
    for (int k = 0; k < 4; ++k)
    {
      basisU[i * 4 + k] = b[k];
    }
  }
  for (int j = 0; j < Nv; ++j)
  {
    double b[4];
    bern(vSamples[j], b);
    for (int k = 0; k < 4; ++k)
    {
      basisV[j * 4 + k] = b[k];
    }
  }
  for (int i = 0; i < Nu; ++i)
  {
    for (int j = 0; j < Nv; ++j)
    {
      const double u = uSamples[i];
      const double v = vSamples[j];
      points[(i * Nv + j) * 3 + 0] = u;
      points[(i * Nv + j) * 3 + 1] = v;
      points[(i * Nv + j) * 3 + 2] = zFn(u, v);
    }
  }
}

} // namespace vtkLiverAlgorithmEdgeCaseHelpers

#endif // __vtkLiverAlgorithmEdgeCaseHelpers_h_

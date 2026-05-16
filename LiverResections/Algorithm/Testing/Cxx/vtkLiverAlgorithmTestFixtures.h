/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) Oslo University Hospital. All rights reserved.

  Shared synthetic fixtures + characterisation-pinned EXPECTED constants
  for the LiverResections/Algorithm C++ tests.  All values transcribed
  verbatim from Testing/Python/unit/test_bezier_characterization.py.

  Bezier fixtures re-captured 2026-05-16 at the production-correct
  Bernstein degree-3 (4x4 = 16 control points): the prior 5x5 / degree-4
  capture inherited from PR #330 did not match what production actually
  runs in LiverLogic.runSurfacefromCurve (Liver/Liver.py:2010) or
  LiverLogic.runSurfacefromEFD (Liver/Liver.py:2163), both of which
  call ``evaluate_basis_bezier(t, 3)``.  The EFD / DC / inverse-transform
  EXPECTED constants below do *not* depend on the Bernstein degree and
  remain as captured 2026-05-15 against NumPy 2.3.1.

==============================================================================*/

#ifndef __vtkLiverAlgorithmTestFixtures_h_
#define __vtkLiverAlgorithmTestFixtures_h_

#include <array>
#include <cmath>
#include <cstdio>
#include <vector>

namespace vtkLiverAlgorithmTestFixtures
{

constexpr double PI = 3.141592653589793238462643383279502884197;

//------------------------------------------------------------------------------
// Bernstein basis B_{3, 0..3}(t) at a single t.
//
// Matches the basis order used by LiverLogic.evaluate_basis_bezier when
// called at degree=3 from the two production callers of
// fit_bezier_surface (see file header for the degree correction note).
inline std::array<double, 4> bernstein3(double t)
{
  const double t1 = 1.0 - t;
  return {
    t1 * t1 * t1,
    3.0 * t * t1 * t1,
    3.0 * t * t * t1,
    t * t * t,
  };
}

//------------------------------------------------------------------------------
// 4x4 saddle-surface fixture: bilinear surface z = u*v on uniform 4x4 (u,v),
// plus matching 4x4 Bernstein-basis matrices.  Mirrors _make_bezier_fixture
// in test_bezier_characterization.py.
struct BezierFixture
{
  std::vector<double> points;   // length 4*4*3
  std::vector<double> basisU;   // length 4*4
  std::vector<double> basisV;   // length 4*4
};

inline BezierFixture makeBezierFixture()
{
  BezierFixture fx;
  fx.points.assign(static_cast<size_t>(4) * 4 * 3, 0.0);
  fx.basisU.assign(static_cast<size_t>(4) * 4, 0.0);
  fx.basisV.assign(static_cast<size_t>(4) * 4, 0.0);
  // np.linspace(0.0, 1.0, 4) -> exact float64 thirds at indices 1, 2.
  const double third = 1.0 / 3.0;
  std::array<double, 4> uSamples = { 0.0, third, 2.0 * third, 1.0 };
  std::array<double, 4> vSamples = { 0.0, third, 2.0 * third, 1.0 };
  for (int i = 0; i < 4; ++i)
    {
    auto bu = bernstein3(uSamples[i]);
    auto bv = bernstein3(vSamples[i]);
    for (int j = 0; j < 4; ++j)
      {
      fx.basisU[i * 4 + j] = bu[j];
      fx.basisV[i * 4 + j] = bv[j];
      }
    }
  for (int i = 0; i < 4; ++i)
    {
    for (int j = 0; j < 4; ++j)
      {
      const double u = uSamples[i];
      const double v = vSamples[j];
      fx.points[(i * 4 + j) * 3 + 0] = u;
      fx.points[(i * 4 + j) * 3 + 1] = v;
      fx.points[(i * 4 + j) * 3 + 2] = u * v;
      }
    }
  return fx;
}

//------------------------------------------------------------------------------
// 30-point closed inclined-ellipse contour, last point repeats first.
// Mirrors _make_contour_fixture in test_bezier_characterization.py.
inline std::vector<double> makeContourFixture()
{
  constexpr int N = 30;
  std::vector<double> out(static_cast<size_t>(N + 1) * 3, 0.0);
  for (int k = 0; k < N; ++k)
    {
    const double theta = (2.0 * PI * static_cast<double>(k))
                         / static_cast<double>(N);
    out[k * 3 + 0] = 3.0 * std::cos(theta) + 0.5 * std::cos(3.0 * theta);
    out[k * 3 + 1] = 2.0 * std::sin(theta) + 0.3 * std::sin(2.0 * theta);
    out[k * 3 + 2] = 1.0 * std::sin(2.0 * theta) + 0.2 * std::cos(theta);
    }
  // Close the loop: last point = first point.
  out[N * 3 + 0] = out[0];
  out[N * 3 + 1] = out[1];
  out[N * 3 + 2] = out[2];
  return out;
}

//------------------------------------------------------------------------------
// EXPECTED_BEZIER_CONTROL_POINTS — shape (4, 4, 3).  Flat row-major
// (i, j, axis).  Captured 2026-05-16 against Bernstein degree 3 (4x4 = 16
// control points), matching production callers.  Transcribed from
// Testing/Python/unit/test_bezier_characterization.py.
inline const std::vector<double> &expectedBezierControlPoints()
{
  static const std::vector<double> EXPECTED = {
    // i=0
    4.6259292692714846e-18, -1.1993149957370571e-18, -5.5479463418562525e-36,
    4.6259292692714869e-18,  3.3333333333333387e-01,  1.5419764230904974e-18,
    4.6259292692714907e-18,  6.6666666666666718e-01,  3.0839528461809933e-18,
    4.6259292692714853e-18,  1.0000000000000002e+00,  4.6259292692714853e-18,
    // i=1
    3.3333333333333365e-01, -1.1993149957370510e-18, -3.9977166524568520e-19,
    3.3333333333333370e-01,  3.3333333333333370e-01,  1.1111111111111140e-01,
    3.3333333333333431e-01,  6.6666666666666785e-01,  2.2222222222222271e-01,
    3.3333333333333370e-01,  1.0000000000000000e+00,  3.3333333333333370e-01,
    // i=2
    6.6666666666666730e-01, -1.1993149957370633e-18, -7.9954333049137040e-19,
    6.6666666666666741e-01,  3.3333333333333437e-01,  2.2222222222222279e-01,
    6.6666666666666863e-01,  6.6666666666666841e-01,  4.4444444444444542e-01,
    6.6666666666666741e-01,  1.0000000000000020e+00,  6.6666666666666741e-01,
    // i=3
    1.0000000000000002e+00, -1.1993149957370633e-18, -1.1993149957370633e-18,
    1.0000000000000009e+00,  3.3333333333333381e-01,  3.3333333333333381e-01,
    1.0000000000000022e+00,  6.6666666666666741e-01,  6.6666666666666741e-01,
    1.0000000000000004e+00,  1.0000000000000004e+00,  1.0000000000000004e+00,
  };
  return EXPECTED;
}

//------------------------------------------------------------------------------
// EXPECTED_EFD_COEFFS — shape (8, 6) flat row-major.
inline const std::vector<double> &expectedEFDCoeffs()
{
  static const std::vector<double> EXPECTED = {
    3.0696780014396787e+00,  5.1239779468424333e-02, -2.9789149140810579e-02,
    1.9514873662662355e+00,  2.2036188853356678e-01,  4.2702746974910076e-02,
   -2.6309229837804714e-02, -6.4267881945438213e-02,  6.6786943662647752e-03,
    2.2418342923058746e-01, -4.0019158286106520e-02,  1.0054240564985091e+00,
    3.5070359011478724e-01,  2.3751119059978693e-02,  5.7765748378587360e-03,
   -3.1926498794324062e-02,  1.8841777989148448e-02, -6.3265267683567286e-02,
   -5.9072088792485336e-02, -2.8677448082430942e-03, -4.4021774738493948e-03,
   -2.4910202986012455e-02, -2.2814268970371837e-03, -3.8266183368038165e-02,
    1.4297493082861342e-02,  3.8157120315777809e-03, -5.1047708828664178e-03,
    3.5915138362602329e-02, -4.0701176860480524e-03, -1.1736870556792744e-02,
   -3.7731670425895304e-03, -2.1498528837345801e-03,  3.2019220293054503e-03,
    4.9367515048579389e-03, -3.1462453950325381e-03,  3.6203948075069090e-02,
    2.7504669785076315e-02,  2.9615241918178881e-03,  3.7673554870742667e-04,
    2.9205527446133943e-03,  5.4285520231319266e-03, -3.6534590699282741e-03,
   -8.0002053361613468e-03, -3.0729534019550858e-03, -4.8578519669361986e-04,
   -3.2105247026203479e-03, -1.4167817826331423e-03,  2.8554590182290700e-03,
  };
  return EXPECTED;
}

//------------------------------------------------------------------------------
// EXPECTED_DC — (A_0, C_0, E_0).
inline std::array<double, 3> expectedDC()
{
  return { 0.1051885444410785, 0.02454548704630012, 0.006326034387983737 };
}

//------------------------------------------------------------------------------
// EXPECTED_INVERSE_TRANSFORM at locus=(0.1, 0.2, 0.3), nCoords=12, harmonic=8.
// Python shape is (1, 3, 12); we store flat (3, 12) row-major as
// [x_0..x_11, y_0..y_11, z_0..z_11].
inline const std::vector<double> &expectedInverseTransform()
{
  static const std::vector<double> EXPECTED = {
    // x[12]
     3.46502906341336292,  2.62631914676115930,  1.06997026875380863,
    -0.15691976181966613, -1.47373468829598275, -3.02584017448850640,
    -3.18716291312130418, -1.69327787626239701, -0.24848273167857418,
     1.08391744585535688,  2.64018222088274346,  3.46502906341336292,
    // y[12]
     0.17625204408791639,  1.39967211550582804,  2.14059855311727887,
     2.10083953176494642,  1.42746946521858908,  0.69220634387038882,
    -0.23353674636938754, -0.97530931821845668, -1.70506186210775468,
    -1.78630424944057942, -1.03682587742876775,  0.17625204408791581,
    // z[12]
     0.49369848849898967,  1.30367892816921649,  1.27201090631539571,
     0.08585781080290544, -0.79477791740439296, -0.55165977874586325,
     0.64330272029724767,  1.13483868058486026,  0.55744055447150265,
    -0.48298935193040421, -0.36140104105945753,  0.49369848849898923,
  };
  return EXPECTED;
}

//------------------------------------------------------------------------------
// allclose helper — numpy-compatible: |a - b| <= atol + rtol * |b|.
inline bool allClose(const double *a, const double *b, size_t n,
                     double rtol, double atol, size_t *failIdx = nullptr)
{
  for (size_t i = 0; i < n; ++i)
    {
    const double diff = std::fabs(a[i] - b[i]);
    if (diff > atol + rtol * std::fabs(b[i]))
      {
      if (failIdx)
        {
        *failIdx = i;
        }
      return false;
      }
    }
  return true;
}

//------------------------------------------------------------------------------
// Print a clear failure diagnostic.
inline void printFailure(const char *name,
                         const double *actual,
                         const double *expected,
                         size_t n,
                         size_t failIdx,
                         double rtol,
                         double atol)
{
  std::fprintf(stderr,
               "[%s] FAIL at flat index %zu/%zu: actual=%.17g expected=%.17g "
               "abs_diff=%.3e (rtol=%.0e atol=%.0e)\n",
               name, failIdx, n, actual[failIdx], expected[failIdx],
               std::fabs(actual[failIdx] - expected[failIdx]), rtol, atol);
}

}  // namespace vtkLiverAlgorithmTestFixtures

#endif  // __vtkLiverAlgorithmTestFixtures_h_

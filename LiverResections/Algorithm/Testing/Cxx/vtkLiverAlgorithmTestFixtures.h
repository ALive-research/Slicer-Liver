/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) Oslo University Hospital. All rights reserved.

  Shared synthetic fixtures + characterisation-pinned EXPECTED constants
  for the LiverResections/Algorithm C++ tests.  All values transcribed
  verbatim from Testing/Python/unit/test_bezier_characterization.py
  (captured 2026-05-15 against NumPy 2.3.1).

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
// Bernstein basis B_{4, 0..4}(t) at a single t.
inline std::array<double, 5> bernstein4(double t)
{
  const double t1 = 1.0 - t;
  return {
    t1 * t1 * t1 * t1,
    4.0 * t * t1 * t1 * t1,
    6.0 * t * t * t1 * t1,
    4.0 * t * t * t * t1,
    t * t * t * t,
  };
}

//------------------------------------------------------------------------------
// 5x5 saddle-surface fixture: bilinear surface z = u*v on uniform 5x5 (u,v),
// plus matching 5x5 Bernstein-basis matrices.  Mirrors _make_bezier_fixture
// in test_bezier_characterization.py.
struct BezierFixture
{
  std::vector<double> points;   // length 5*5*3
  std::vector<double> basisU;   // length 5*5
  std::vector<double> basisV;   // length 5*5
};

inline BezierFixture makeBezierFixture()
{
  BezierFixture fx;
  fx.points.assign(static_cast<size_t>(5) * 5 * 3, 0.0);
  fx.basisU.assign(static_cast<size_t>(5) * 5, 0.0);
  fx.basisV.assign(static_cast<size_t>(5) * 5, 0.0);
  std::array<double, 5> uSamples = { 0.0, 0.25, 0.5, 0.75, 1.0 };
  std::array<double, 5> vSamples = { 0.0, 0.25, 0.5, 0.75, 1.0 };
  for (int i = 0; i < 5; ++i)
    {
    auto bu = bernstein4(uSamples[i]);
    auto bv = bernstein4(vSamples[i]);
    for (int j = 0; j < 5; ++j)
      {
      fx.basisU[i * 5 + j] = bu[j];
      fx.basisV[i * 5 + j] = bv[j];
      }
    }
  for (int i = 0; i < 5; ++i)
    {
    for (int j = 0; j < 5; ++j)
      {
      const double u = uSamples[i];
      const double v = vSamples[j];
      fx.points[(i * 5 + j) * 3 + 0] = u;
      fx.points[(i * 5 + j) * 3 + 1] = v;
      fx.points[(i * 5 + j) * 3 + 2] = u * v;
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
// EXPECTED_BEZIER_CONTROL_POINTS — shape (5, 5, 3).  Flat row-major
// (i, j, axis).
inline const std::vector<double> &expectedBezierControlPoints()
{
  static const std::vector<double> EXPECTED = {
    // i=0
    2.1335056041739302e-17, -3.1679032227310840e-18, -6.7587392791774200e-35,
    2.1335056041739311e-17,  2.4999999999999936e-01,  5.3337640104348109e-18,
    2.1335056041739191e-17,  4.9999999999999800e-01,  1.0667528020869609e-17,
    2.1335056041739308e-17,  7.5000000000000111e-01,  1.6001292031304480e-17,
    2.1335056041739296e-17,  9.9999999999999989e-01,  2.1335056041739296e-17,
    // i=1
    2.5000000000000366e-01, -3.1679032227311156e-18, -7.9197580568278295e-19,
    2.5000000000000372e-01,  2.5000000000000161e-01,  6.2500000000000819e-02,
    2.5000000000000255e-01,  5.0000000000000377e-01,  1.2500000000000114e-01,
    2.5000000000000366e-01,  7.5000000000000733e-01,  1.8750000000000328e-01,
    2.5000000000000361e-01,  1.0000000000000095e+00,  2.5000000000000361e-01,
    // i=2
    4.9999999999999045e-01, -3.1679032227310162e-18, -1.5839516113655116e-18,
    4.9999999999999040e-01,  2.4999999999999487e-01,  1.2499999999999707e-01,
    4.9999999999998856e-01,  4.9999999999998579e-01,  2.4999999999999478e-01,
    4.9999999999999045e-01,  7.4999999999998757e-01,  3.7499999999999245e-01,
    4.9999999999999040e-01,  9.9999999999997924e-01,  4.9999999999999040e-01,
    // i=3
    7.5000000000000355e-01, -3.1679032227311033e-18, -2.3759274170483255e-18,
    7.5000000000000422e-01,  2.5000000000000050e-01,  1.8750000000000042e-01,
    7.5000000000000056e-01,  5.0000000000000244e-01,  3.7500000000000100e-01,
    7.5000000000000411e-01,  7.5000000000000444e-01,  5.6250000000000278e-01,
    7.5000000000000333e-01,  1.0000000000000060e+00,  7.5000000000000333e-01,
    // i=4
    9.9999999999999978e-01, -3.1679032227310833e-18, -3.1679032227310833e-18,
    9.9999999999999967e-01,  2.4999999999999906e-01,  2.4999999999999908e-01,
    9.9999999999999523e-01,  4.9999999999999833e-01,  4.9999999999999833e-01,
    9.9999999999999956e-01,  7.5000000000000000e-01,  7.5000000000000000e-01,
    9.9999999999999967e-01,  9.9999999999999978e-01,  9.9999999999999967e-01,
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

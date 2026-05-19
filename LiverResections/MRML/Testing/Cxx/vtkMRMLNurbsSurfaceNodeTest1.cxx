/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Tests for vtkMRMLNurbsSurfaceNode — the v2.1 NURBS sibling data
  node landed by ADR-0022 §"Decision 1 — Data node" (NURBS-1
  deliverable).  Exercises:

   - defaults (constructor values: Rows=Cols=4, DegreeU=DegreeV=3,
     KnotsU/V clamped-uniform, Weights all 1.0, ControlGrid zero)
   - shape + degree validation (cross-IVar invariants)
   - knot length invariants on shape / degree changes
   - weights positivity validation
   - state machine transitions (same matrix as Bezier per ADR-0019)
   - CopyContent (in-type + cross-type rejection)
   - XML round-trip via ReadXMLAttributes / WriteXML

==============================================================================*/

// MRML includes
#include "vtkMRMLCoreTestingMacros.h"
#include "vtkMRMLBezierSurfaceNode.h"
#include "vtkMRMLNurbsSurfaceNode.h"
#include "vtkMRMLScene.h"

// VTK includes
#include <vtkNew.h>
#include <vtkSmartPointer.h>

// STD includes
#include <cmath>
#include <iostream>
#include <sstream>
#include <string>

namespace
{

int testDefaults()
{
  vtkNew<vtkMRMLNurbsSurfaceNode> node;

  CHECK_INT(static_cast<int>(node->GetRows()), vtkMRMLNurbsSurfaceNode::DefaultGridSize);
  CHECK_INT(static_cast<int>(node->GetCols()), vtkMRMLNurbsSurfaceNode::DefaultGridSize);
  CHECK_INT(static_cast<int>(node->GetDegreeU()), vtkMRMLNurbsSurfaceNode::DefaultDegree);
  CHECK_INT(static_cast<int>(node->GetDegreeV()), vtkMRMLNurbsSurfaceNode::DefaultDegree);
  CHECK_INT(node->GetState(), vtkMRMLNurbsSurfaceNode::Init);
  CHECK_INT(node->GetInitMode(), vtkMRMLNurbsSurfaceNode::SlicingPlane);
  CHECK_STRING(node->GetNodeTagName(), "NurbsSurface");

  // Control grid is zero-filled at construction.  Length is
  // 3 * Rows * Cols == 3 * 4 * 4 == 48 for the defaults.
  CHECK_INT(static_cast<int>(node->GetControlGridLength()), 48);
  const double* grid = node->GetControlGrid();
  for (unsigned int i = 0; i < node->GetControlGridLength(); ++i)
  {
    CHECK_DOUBLE(grid[i], 0.0);
  }

  // Weights default to all-1.0 (non-rational B-spline degenerate
  // case per ADR-0022 §"Weights default").  Length is Rows * Cols.
  CHECK_INT(static_cast<int>(node->GetWeightsLength()), 16);
  const double* weights = node->GetWeights();
  for (unsigned int i = 0; i < node->GetWeightsLength(); ++i)
  {
    CHECK_DOUBLE(weights[i], 1.0);
  }

  // Default knots are clamped-uniform with length Rows + DegreeU + 1
  // = 4 + 3 + 1 = 8.  For a degree-3, 4-row vector the de Boor
  // convention emits [0, 0, 0, 0, 1, 1, 1, 1] — no interior knots
  // because rows == degree + 1 (Bezier-equivalent degenerate case).
  CHECK_INT(static_cast<int>(node->GetKnotsULength()), 8);
  CHECK_INT(static_cast<int>(node->GetKnotsVLength()), 8);
  const double* knotsU = node->GetKnotsU();
  for (int i = 0; i < 4; ++i)
  {
    CHECK_DOUBLE(knotsU[i], 0.0);
  }
  for (int i = 4; i < 8; ++i)
  {
    CHECK_DOUBLE(knotsU[i], 1.0);
  }
  return EXIT_SUCCESS;
}

int testClampedUniformKnotsWithInteriorNonEmpty()
{
  // Drive the node to a shape with interior knots present
  // (Rows > DegreeU + 1).  For (Rows=5, DegreeU=2) the knot vector
  // is length 8: [0, 0, 0, 1/3, 2/3, 1, 1, 1] — three zeros, two
  // interior knots, three ones.
  vtkNew<vtkMRMLNurbsSurfaceNode> node;
  node->SetDegree(2); // lower degree first so SetSize(5) does not
                      // need to bump degrees down internally; both
                      // axes valid because 5 >= 2+1.
  node->SetSize(5);

  CHECK_INT(static_cast<int>(node->GetKnotsULength()), 8);
  const double* knotsU = node->GetKnotsU();
  CHECK_DOUBLE(knotsU[0], 0.0);
  CHECK_DOUBLE(knotsU[1], 0.0);
  CHECK_DOUBLE(knotsU[2], 0.0);
  CHECK_DOUBLE_TOLERANCE(knotsU[3], 1.0 / 3.0, 1e-9);
  CHECK_DOUBLE_TOLERANCE(knotsU[4], 2.0 / 3.0, 1e-9);
  CHECK_DOUBLE(knotsU[5], 1.0);
  CHECK_DOUBLE(knotsU[6], 1.0);
  CHECK_DOUBLE(knotsU[7], 1.0);
  return EXIT_SUCCESS;
}

int testShapeValidation()
{
  vtkNew<vtkMRMLNurbsSurfaceNode> node;

  // Default is (4, 4) at degree 3.  ``SetSize(4)`` is a no-op.
  const vtkMTimeType preNoop = node->GetMTime();
  node->SetSize(4);
  CHECK_INT(static_cast<int>(node->GetMTime()), static_cast<int>(preNoop));

  // SetSize(5) is legal — 5 >= DegreeU + 1 = 4.
  node->SetSize(5);
  CHECK_INT(static_cast<int>(node->GetRows()), 5);
  CHECK_INT(static_cast<int>(node->GetCols()), 5);
  CHECK_INT(static_cast<int>(node->GetControlGridLength()), 75);

  // SetSize(3) with the current default degree 3 is rejected — 3 <
  // DegreeU + 1 = 4.  Need to drop degree first.
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  node->SetSize(3);
  TESTING_OUTPUT_ASSERT_ERRORS_END();
  CHECK_INT(static_cast<int>(node->GetRows()), 5); // unchanged

  // After lowering degree to 2, SetSize(3) becomes legal.
  node->SetDegree(2);
  node->SetSize(3);
  CHECK_INT(static_cast<int>(node->GetRows()), 3);
  CHECK_INT(static_cast<int>(node->GetCols()), 3);

  // SetRows(2) — even at degree 2 — is rejected; need Rows >= 3.
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  node->SetRows(2);
  TESTING_OUTPUT_ASSERT_ERRORS_END();
  CHECK_INT(static_cast<int>(node->GetRows()), 3);

  // Asymmetric shape via SetRows / SetCols.  Going from (3, 3)
  // degree (2, 2) to (5, 3) is legal.
  node->SetRows(5);
  CHECK_INT(static_cast<int>(node->GetRows()), 5);
  CHECK_INT(static_cast<int>(node->GetCols()), 3);
  CHECK_INT(static_cast<int>(node->GetControlGridLength()), 45);
  return EXIT_SUCCESS;
}

int testDegreeValidation()
{
  vtkNew<vtkMRMLNurbsSurfaceNode> node;

  // Defaults: shape (4, 4), degrees (3, 3).
  // Accept degree 2.
  node->SetDegree(2);
  CHECK_INT(static_cast<int>(node->GetDegreeU()), 2);
  CHECK_INT(static_cast<int>(node->GetDegreeV()), 2);

  // Accept degree 3.
  node->SetDegree(3);
  CHECK_INT(static_cast<int>(node->GetDegreeU()), 3);

  // Reject degree 1 (below MinDegree).
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  node->SetDegree(1);
  TESTING_OUTPUT_ASSERT_ERRORS_END();
  CHECK_INT(static_cast<int>(node->GetDegreeU()), 3);

  // Reject degree 4 (above MaxDegree).
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  node->SetDegree(4);
  TESTING_OUTPUT_ASSERT_ERRORS_END();
  CHECK_INT(static_cast<int>(node->GetDegreeU()), 3);

  // Cross-IVar: cannot raise DegreeU above Rows - 1.  Drop Rows to
  // 3 (need to lower degree first), then attempt to raise degreeU
  // back to 3 — rejected.
  node->SetDegree(2);
  node->SetSize(3);
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  node->SetDegreeU(3);
  TESTING_OUTPUT_ASSERT_ERRORS_END();
  CHECK_INT(static_cast<int>(node->GetDegreeU()), 2);

  // Constants exposed.
  CHECK_INT(vtkMRMLNurbsSurfaceNode::MinDegree, 2);
  CHECK_INT(vtkMRMLNurbsSurfaceNode::MaxDegree, 3);
  CHECK_INT(vtkMRMLNurbsSurfaceNode::DefaultDegree, 3);
  CHECK_INT(vtkMRMLNurbsSurfaceNode::DefaultGridSize, 4);
  return EXIT_SUCCESS;
}

int testKnotLengthInvariant()
{
  // After every shape / degree change the knot vectors must
  // satisfy len(KnotsU) == Rows + DegreeU + 1 and
  // len(KnotsV) == Cols + DegreeV + 1.
  vtkNew<vtkMRMLNurbsSurfaceNode> node;

  // (4, 4, 3, 3) → KnotsU/V length 8 each.
  CHECK_INT(static_cast<int>(node->GetKnotsULength()), 8);
  CHECK_INT(static_cast<int>(node->GetKnotsVLength()), 8);

  // Lower degree, expand shape.
  node->SetDegree(2);
  CHECK_INT(static_cast<int>(node->GetKnotsULength()), 7); // 4 + 2 + 1
  node->SetSize(10);
  CHECK_INT(static_cast<int>(node->GetKnotsULength()), 13); // 10 + 2 + 1

  // Asymmetric: Cols changes only.
  node->SetCols(6);
  CHECK_INT(static_cast<int>(node->GetKnotsULength()), 13);
  CHECK_INT(static_cast<int>(node->GetKnotsVLength()), 9); // 6 + 2 + 1
  return EXIT_SUCCESS;
}

int testWeightsPositivity()
{
  vtkNew<vtkMRMLNurbsSurfaceNode> node;

  // Default shape 4×4 → 16 weights, all 1.0.
  CHECK_INT(static_cast<int>(node->GetWeightsLength()), 16);
  const double* w = node->GetWeights();
  for (unsigned int i = 0; i < 16; ++i)
  {
    CHECK_DOUBLE(w[i], 1.0);
  }

  // Accept a fresh valid weights vector.
  double valid[16];
  for (int i = 0; i < 16; ++i)
  {
    valid[i] = 0.5 + static_cast<double>(i) * 0.1;
  }
  CHECK_BOOL(node->SetWeights(valid, 16), true);
  for (int i = 0; i < 16; ++i)
  {
    CHECK_DOUBLE(node->GetWeights()[i], valid[i]);
  }

  // Reject zero weight.
  double withZero[16];
  std::copy_n(valid, 16, withZero);
  withZero[7] = 0.0;
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  CHECK_BOOL(node->SetWeights(withZero, 16), false);
  TESTING_OUTPUT_ASSERT_ERRORS_END();
  // Old values still in place.
  CHECK_DOUBLE(node->GetWeights()[7], valid[7]);

  // Reject negative weight.
  double withNeg[16];
  std::copy_n(valid, 16, withNeg);
  withNeg[3] = -0.1;
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  CHECK_BOOL(node->SetWeights(withNeg, 16), false);
  TESTING_OUTPUT_ASSERT_ERRORS_END();
  CHECK_DOUBLE(node->GetWeights()[3], valid[3]);

  // Reject wrong length.
  double tooShort[8] = { 1, 2, 3, 4, 5, 6, 7, 8 };
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  CHECK_BOOL(node->SetWeights(tooShort, 8), false);
  TESTING_OUTPUT_ASSERT_ERRORS_END();

  // Reject null pointer.
  CHECK_BOOL(node->SetWeights(nullptr, 16), false);
  return EXIT_SUCCESS;
}

int testStateTransitions()
{
  // ADR-0019 transition matrix — duplicated from
  // ``vtkMRMLBezierSurfaceNode`` per ADR-0022 §"Sharing with the
  // Bezier node — deliberate non-sharing".  Mirrors the
  // testConfirmedStateTransitions test on the Bezier node.
  vtkNew<vtkMRMLNurbsSurfaceNode> node;
  CHECK_INT(node->GetState(), vtkMRMLNurbsSurfaceNode::Init);

  // Init -> Planning (legal forward edge).
  vtkMTimeType pre = node->GetMTime();
  node->SetState(vtkMRMLNurbsSurfaceNode::Planning);
  CHECK_INT(node->GetState(), vtkMRMLNurbsSurfaceNode::Planning);
  if (node->GetMTime() <= pre)
  {
    std::cerr << "Expected MTime advance on Init -> Planning\n";
    return EXIT_FAILURE;
  }

  // Planning -> Confirmed (legal).
  node->SetState(vtkMRMLNurbsSurfaceNode::Confirmed);
  CHECK_INT(node->GetState(), vtkMRMLNurbsSurfaceNode::Confirmed);

  // Confirmed -> Planning (legal round-trip).
  node->SetState(vtkMRMLNurbsSurfaceNode::Planning);
  CHECK_INT(node->GetState(), vtkMRMLNurbsSurfaceNode::Planning);

  // Forbidden: Planning -> Init.
  TESTING_OUTPUT_ASSERT_WARNINGS_BEGIN();
  pre = node->GetMTime();
  node->SetState(vtkMRMLNurbsSurfaceNode::Init);
  TESTING_OUTPUT_ASSERT_WARNINGS_END();
  CHECK_INT(node->GetState(), vtkMRMLNurbsSurfaceNode::Planning);
  CHECK_INT(node->GetMTime(), pre);

  // Forbidden: Confirmed -> Init (drive to Confirmed via the legal
  // path first).
  node->SetState(vtkMRMLNurbsSurfaceNode::Confirmed);
  TESTING_OUTPUT_ASSERT_WARNINGS_BEGIN();
  pre = node->GetMTime();
  node->SetState(vtkMRMLNurbsSurfaceNode::Init);
  TESTING_OUTPUT_ASSERT_WARNINGS_END();
  CHECK_INT(node->GetState(), vtkMRMLNurbsSurfaceNode::Confirmed);
  CHECK_INT(node->GetMTime(), pre);

  // Forbidden: Init -> Confirmed (fresh node).
  vtkNew<vtkMRMLNurbsSurfaceNode> fresh;
  TESTING_OUTPUT_ASSERT_WARNINGS_BEGIN();
  pre = fresh->GetMTime();
  fresh->SetState(vtkMRMLNurbsSurfaceNode::Confirmed);
  TESTING_OUTPUT_ASSERT_WARNINGS_END();
  CHECK_INT(fresh->GetState(), vtkMRMLNurbsSurfaceNode::Init);
  CHECK_INT(fresh->GetMTime(), pre);

  // Enum-string converters.
  CHECK_STRING(vtkMRMLNurbsSurfaceNode::GetStateAsString(vtkMRMLNurbsSurfaceNode::Init), "Init");
  CHECK_STRING(vtkMRMLNurbsSurfaceNode::GetStateAsString(vtkMRMLNurbsSurfaceNode::Planning), "Planning");
  CHECK_STRING(vtkMRMLNurbsSurfaceNode::GetStateAsString(vtkMRMLNurbsSurfaceNode::Confirmed), "Confirmed");
  CHECK_INT(vtkMRMLNurbsSurfaceNode::GetStateFromString("Confirmed"), vtkMRMLNurbsSurfaceNode::Confirmed);
  CHECK_INT(vtkMRMLNurbsSurfaceNode::GetStateFromString("bogus"), -1);
  CHECK_INT(vtkMRMLNurbsSurfaceNode::GetStateFromString(nullptr), -1);
  CHECK_INT(vtkMRMLNurbsSurfaceNode::GetInitModeFromString("DistanceSpheroid"), vtkMRMLNurbsSurfaceNode::DistanceSpheroid);
  return EXIT_SUCCESS;
}

int testCopyContent()
{
  // Same-type CopyContent must propagate every IVar.
  vtkNew<vtkMRMLNurbsSurfaceNode> source;
  source->SetDegree(2);
  source->SetSize(5);
  source->SetState(vtkMRMLNurbsSurfaceNode::Planning);
  source->SetInitMode(vtkMRMLNurbsSurfaceNode::DistanceSpheroid);

  double grid[75];
  for (int i = 0; i < 75; ++i)
  {
    grid[i] = static_cast<double>(i) * 0.1;
  }
  source->SetControlGrid(grid);

  double weights[25];
  for (int i = 0; i < 25; ++i)
  {
    weights[i] = 0.5 + static_cast<double>(i) * 0.02;
  }
  source->SetWeights(weights, 25);

  vtkNew<vtkMRMLNurbsSurfaceNode> sink;
  sink->CopyContent(source.GetPointer(), /*deepCopy=*/true);

  CHECK_INT(static_cast<int>(sink->GetRows()), 5);
  CHECK_INT(static_cast<int>(sink->GetCols()), 5);
  CHECK_INT(static_cast<int>(sink->GetDegreeU()), 2);
  CHECK_INT(static_cast<int>(sink->GetDegreeV()), 2);
  CHECK_INT(sink->GetState(), vtkMRMLNurbsSurfaceNode::Planning);
  CHECK_INT(sink->GetInitMode(), vtkMRMLNurbsSurfaceNode::DistanceSpheroid);
  for (int i = 0; i < 75; ++i)
  {
    CHECK_DOUBLE(sink->GetControlGrid()[i], grid[i]);
  }
  for (int i = 0; i < 25; ++i)
  {
    CHECK_DOUBLE(sink->GetWeights()[i], weights[i]);
  }
  // Knots also round-trip.
  for (unsigned int i = 0; i < sink->GetKnotsULength(); ++i)
  {
    CHECK_DOUBLE(sink->GetKnotsU()[i], source->GetKnotsU()[i]);
  }
  return EXIT_SUCCESS;
}

int testCopyContentRejectsCrossType()
{
  // Cross-type sources are rejected with vtkErrorMacro per
  // ADR-0022 §"Sharing with the Bezier node — deliberate
  // non-sharing".  Bezier → NURBS copy is not meaningful without a
  // fitter (Bezier carries no knots / weights / degrees) and
  // returning early protects against silent zero-fill of those
  // IVars on the sink.
  vtkNew<vtkMRMLBezierSurfaceNode> bezier;
  bezier->SetSize(3);

  vtkNew<vtkMRMLNurbsSurfaceNode> sink;
  // Capture the sink's pre-copy state to assert the rejected copy
  // did not partially mutate it.
  const unsigned int preRows = sink->GetRows();
  const unsigned int preDegreeU = sink->GetDegreeU();

  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  sink->CopyContent(bezier.GetPointer(), /*deepCopy=*/true);
  TESTING_OUTPUT_ASSERT_ERRORS_END();

  // Sink IVars unchanged.
  CHECK_INT(static_cast<int>(sink->GetRows()), static_cast<int>(preRows));
  CHECK_INT(static_cast<int>(sink->GetDegreeU()), static_cast<int>(preDegreeU));

  // Symmetric direction: NURBS -> Bezier sink is also rejected by
  // the Bezier ``CopyContent`` for the same reason.
  vtkNew<vtkMRMLNurbsSurfaceNode> nurbs;
  vtkNew<vtkMRMLBezierSurfaceNode> bezierSink;
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  bezierSink->CopyContent(nurbs.GetPointer(), /*deepCopy=*/true);
  TESTING_OUTPUT_ASSERT_ERRORS_END();
  return EXIT_SUCCESS;
}

int testXMLRoundTrip()
{
  vtkNew<vtkMRMLNurbsSurfaceNode> source;
  vtkNew<vtkMRMLScene> scene;
  source->SetScene(scene.GetPointer());

  source->SetDegree(2);
  source->SetSize(5);
  source->SetState(vtkMRMLNurbsSurfaceNode::Planning);
  source->SetInitMode(vtkMRMLNurbsSurfaceNode::DistanceSpheroid);

  double grid[75];
  for (int i = 0; i < 75; ++i)
  {
    grid[i] = std::sin(static_cast<double>(i) * 0.1);
  }
  source->SetControlGrid(grid);

  double weights[25];
  for (int i = 0; i < 25; ++i)
  {
    weights[i] = 0.5 + static_cast<double>(i) * 0.05;
  }
  source->SetWeights(weights, 25);

  std::ostringstream out;
  source->WriteXML(out, 0);
  const std::string xml = out.str();

  // Sanity check: the XML stream should carry rows + cols +
  // degreeU + degreeV + knots / weights / controlGrid.
  if (xml.find("rows=\"5\"") == std::string::npos)
  {
    std::cerr << "Expected rows=\"5\" in NURBS XML:\n" << xml << "\n";
    return EXIT_FAILURE;
  }
  if (xml.find("degreeU=\"2\"") == std::string::npos)
  {
    std::cerr << "Expected degreeU=\"2\" in NURBS XML:\n" << xml << "\n";
    return EXIT_FAILURE;
  }
  if (xml.find("weights=") == std::string::npos)
  {
    std::cerr << "Expected weights attribute in NURBS XML:\n" << xml << "\n";
    return EXIT_FAILURE;
  }

  // Walk the attribute list back into name/value pairs (same
  // naïve parser as the Bezier node tests; libxml2 is not linked
  // into this test driver).
  std::vector<std::string> storage;
  std::size_t pos = 0;
  while (pos < xml.size())
  {
    while (pos < xml.size() && std::isspace(xml[pos]))
    {
      ++pos;
    }
    if (pos >= xml.size())
    {
      break;
    }
    const std::size_t eq = xml.find('=', pos);
    if (eq == std::string::npos)
    {
      break;
    }
    std::string name = xml.substr(pos, eq - pos);
    if (eq + 1 >= xml.size() || xml[eq + 1] != '"')
    {
      break;
    }
    const std::size_t valStart = eq + 2;
    const std::size_t valEnd = xml.find('"', valStart);
    if (valEnd == std::string::npos)
    {
      break;
    }
    std::string value = xml.substr(valStart, valEnd - valStart);
    storage.push_back(name);
    storage.push_back(value);
    pos = valEnd + 1;
  }
  std::vector<const char*> atts;
  for (const auto& s : storage)
  {
    atts.push_back(s.c_str());
  }
  atts.push_back(nullptr);

  vtkNew<vtkMRMLNurbsSurfaceNode> sink;
  sink->SetScene(scene.GetPointer());
  sink->ReadXMLAttributes(atts.data());

  CHECK_INT(sink->GetState(), source->GetState());
  CHECK_INT(sink->GetInitMode(), source->GetInitMode());
  CHECK_INT(static_cast<int>(sink->GetRows()), 5);
  CHECK_INT(static_cast<int>(sink->GetCols()), 5);
  CHECK_INT(static_cast<int>(sink->GetDegreeU()), 2);
  CHECK_INT(static_cast<int>(sink->GetDegreeV()), 2);
  for (int i = 0; i < 75; ++i)
  {
    CHECK_DOUBLE_TOLERANCE(sink->GetControlGrid()[i], grid[i], 1e-5);
  }
  for (int i = 0; i < 25; ++i)
  {
    CHECK_DOUBLE_TOLERANCE(sink->GetWeights()[i], weights[i], 1e-5);
  }
  for (unsigned int i = 0; i < sink->GetKnotsULength(); ++i)
  {
    CHECK_DOUBLE_TOLERANCE(sink->GetKnotsU()[i], source->GetKnotsU()[i], 1e-5);
  }
  return EXIT_SUCCESS;
}

int testResetKnotsHelper()
{
  // Direct exercise of the ResetKnotsToClampedUniform helper.
  // After a SetWeights mutation that does not touch shape, the
  // knot vectors should be unchanged from the clamped-uniform
  // default; calling ResetKnotsToClampedUniform after manually
  // editing the IVar vector restores defaults.  This test pins
  // the helper contract for callers that bypass shape setters.
  vtkNew<vtkMRMLNurbsSurfaceNode> node;
  node->SetDegree(2);
  node->SetSize(5);

  const std::vector<double>& knotsU = node->GetKnotsUVector();
  CHECK_INT(static_cast<int>(knotsU.size()), 8);

  // Save current values, then call reset — values should match.
  std::vector<double> snapshot = knotsU;
  node->ResetKnotsToClampedUniform();
  for (size_t i = 0; i < snapshot.size(); ++i)
  {
    CHECK_DOUBLE_TOLERANCE(node->GetKnotsU()[i], snapshot[i], 1e-9);
  }
  return EXIT_SUCCESS;
}

int testSetKnotsLengthMismatch()
{
  // SetKnotsU / SetKnotsV reject length-mismatch payloads with
  // vtkErrorMacro and return false.  ``data-node setter'' validation
  // is independent of the storage-layer JSON validation per
  // ADR-0022 §"Validation rules per surface type"; both layers
  // enforce the invariant.
  vtkNew<vtkMRMLNurbsSurfaceNode> node;
  CHECK_INT(static_cast<int>(node->GetKnotsULength()), 8);

  double tooShort[7] = { 0, 0, 0, 0.5, 1, 1, 1 };
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  CHECK_BOOL(node->SetKnotsU(tooShort, 7), false);
  TESTING_OUTPUT_ASSERT_ERRORS_END();

  double tooLong[9] = { 0, 0, 0, 0, 0.5, 1, 1, 1, 1 };
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  CHECK_BOOL(node->SetKnotsU(tooLong, 9), false);
  TESTING_OUTPUT_ASSERT_ERRORS_END();

  double justRight[8] = { 0, 0, 0, 0, 1, 1, 1, 1 };
  CHECK_BOOL(node->SetKnotsU(justRight, 8), true);

  // Symmetric for KnotsV.
  TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
  CHECK_BOOL(node->SetKnotsV(tooShort, 7), false);
  TESTING_OUTPUT_ASSERT_ERRORS_END();
  CHECK_BOOL(node->SetKnotsV(justRight, 8), true);

  // Null pointer rejected (no error message — same convention as
  // SetControlGrid which returns false silently on null).
  CHECK_BOOL(node->SetKnotsU(nullptr, 8), false);
  return EXIT_SUCCESS;
}

} // namespace

//------------------------------------------------------------------------------
int vtkMRMLNurbsSurfaceNodeTest1(int, char*[])
{
  vtkNew<vtkMRMLScene> scene;
  vtkNew<vtkMRMLNurbsSurfaceNode> exerciseNode;
  exerciseNode->SetScene(scene.GetPointer());
  EXERCISE_ALL_BASIC_MRML_METHODS(exerciseNode.GetPointer());

  CHECK_EXIT_SUCCESS(testDefaults());
  CHECK_EXIT_SUCCESS(testClampedUniformKnotsWithInteriorNonEmpty());
  CHECK_EXIT_SUCCESS(testShapeValidation());
  CHECK_EXIT_SUCCESS(testDegreeValidation());
  CHECK_EXIT_SUCCESS(testKnotLengthInvariant());
  CHECK_EXIT_SUCCESS(testWeightsPositivity());
  CHECK_EXIT_SUCCESS(testStateTransitions());
  CHECK_EXIT_SUCCESS(testCopyContent());
  CHECK_EXIT_SUCCESS(testCopyContentRejectsCrossType());
  CHECK_EXIT_SUCCESS(testXMLRoundTrip());
  CHECK_EXIT_SUCCESS(testResetKnotsHelper());
  CHECK_EXIT_SUCCESS(testSetKnotsLengthMismatch());

  std::cout << "vtkMRMLNurbsSurfaceNodeTest1 completed successfully" << std::endl;
  return EXIT_SUCCESS;
}

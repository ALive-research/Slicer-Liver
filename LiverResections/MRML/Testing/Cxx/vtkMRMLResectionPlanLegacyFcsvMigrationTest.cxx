/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Redistribution and use in source and binary forms, with or without
  modification, are permitted provided that the following conditions
  are met:

  * Redistributions of source code must retain the above copyright
    notice, this list of conditions and the following disclaimer.

  * Redistributions in binary form must reproduce the above copyright
    notice, this list of conditions and the following disclaimer in the
    documentation and/or other materials provided with the distribution.

  * Neither the name of Oslo University Hospital nor the names
    of Contributors may be used to endorse or promote products derived
    from this software without specific prior written permission.

  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
  "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
  A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
  HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
  SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
  LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
  DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
  THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

==============================================================================*/

/**
 * \file vtkMRMLResectionPlanLegacyFcsvMigrationTest.cxx
 *
 * Test-first scaffolding for the seamless v1 ``.lrp.fcsv`` ->
 * v2 ``.lrp.json`` resection-plan migration.  Pins the "Fork C"
 * red->green invariant: opening a legacy ``.lrp.fcsv`` (16 Bezier
 * control points only) through the v2 plan-storage path must
 * materialise a ``vtkMRMLBezierSurfaceNode`` carrier with the 16
 * control points, wrap it in a ``vtkMRMLResectionPlanNode``, and
 * apply the documented v2 defaults for every field absent from the
 * legacy format.
 *
 * The legacy ``vtkMRMLLiverResectionCSVStorageNode`` stays as the
 * read-only parse vehicle; this test pins the seam where its parse
 * output is lifted into the v2 carrier + wrapper.  Architectural
 * anchors:
 *
 *   - ADR-0014 §"Fourth layer: clinical/method wrapper" + ADR-0023
 *     §"Persistence -- .lrp.json schema v2" -- the wrapper-vs-carrier
 *     split that the migration must produce on load.
 *   - ``Docs/design/resection-plan-architecture/03-storage-ownership.md``
 *     §"Plan node" -- the storage node owns the legacy upgrade seam.
 *   - ``vtkMRMLResectionPlanStorageNode.h`` §"Optional-field tolerance"
 *     -- the documented v2 reader defaults (margins = 0.0,
 *     orderIndex = -1, state = "Init") that every legacy-absent field
 *     falls back to.
 *
 * RED-fail state (intentional, per the test-first convention):
 *   The current ``ReadDataInternal`` rejects any non-``.lrp.json`` /
 *   ``.json`` extension outright (the legacy ``.fcsv`` branch does not
 *   exist yet) and builds the OLD ``vtkMRMLLiverResectionNode`` family,
 *   not a plan node.  Every assertion below therefore fails red against
 *   the current tree; the follow-up implementer commit lands the legacy
 *   branch and flips them green.
 *
 * Fixture decision:
 *   This test consumes the committed static fixture
 *   ``Fixtures/legacy_resection.lrp.fcsv`` (16 points, 4x4 grid,
 *   15-column Markups CSV, LPS) rather than generating one at test
 *   time via the legacy CSV writer.  Rationale: the migration path the
 *   implementer wires is exercised against a byte-for-byte on-disk v1
 *   artefact -- the same shape a real v1 user file has -- so the test
 *   characterises the actual upgrade rather than a writer/reader fixed
 *   point.  Generating via the writer would couple the migration test
 *   to the legacy writer's own correctness; the static fixture decouples
 *   them.  The fixture is reached through the
 *   ``LIVER_BEZIER_STORAGE_TEST_FIXTURE_DIR`` macro already wired by
 *   ``Testing/Cxx/CMakeLists.txt``.
 */

// This module MRML includes -- forward-included so the test driver
// pins the v2 surface/plan/storage API.  The legacy CSV storage node
// is the read-only parse vehicle the migration seam delegates to.
#include "vtkMRMLResectionPlanNode.h"
#include "vtkMRMLResectionPlanStorageNode.h"
#include "vtkMRMLBezierSurfaceNode.h"
#include "vtkMRMLLiverResectionCSVStorageNode.h"

// MRML includes
#include "vtkMRMLCoreTestingMacros.h"
#include "vtkMRMLMessageCollection.h"
#include "vtkMRMLScene.h"

// VTK includes
#include <vtkCollection.h>
#include <vtkNew.h>
#include <vtkSmartPointer.h>
#include <vtksys/SystemTools.hxx>

// STD includes
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>

// Portable getpid -- temp-file collision avoidance, same scheme as the
// sibling vtkMRMLResectionPlanStorageNodeTest1.cxx.
#if defined(_WIN32)
# include <process.h>
# define LIVER_LEGACY_GETPID _getpid
#else
# include <unistd.h>
# define LIVER_LEGACY_GETPID ::getpid
#endif

namespace
{

constexpr int kBezierControlPointCount = 16;
constexpr double kCoordinateTolerance = 1e-6;

/// The 16 control-point coordinates the migrated Bezier carrier must
/// hold, row-major the same way the fixture lists P-1..P-16.
///
/// IMPORTANT -- coordinate system.  The committed fixture
/// ``Fixtures/legacy_resection.lrp.fcsv`` declares
/// ``# CoordinateSystem = LPS``.  The legacy parse vehicle
/// (``vtkMRMLLiverResectionCSVStorageNode`` delegating to the Markups
/// superclass) converts LPS -> the carrier's RAS storage convention on
/// read, which negates X and Y and leaves Z unchanged.  These expected
/// values are therefore the RAS coordinates (fixture LPS with X,Y
/// negated), NOT the raw fcsv columns.  If the implementer's migration
/// seam preserves LPS instead, this assertion is the place that catches
/// it -- the coordinate-system contract is the invariant.  Kept
/// file-local per the no-shared-helpers convention.
const double kFixtureControlPoints[kBezierControlPointCount][3] = { { -0.0, -0.0, 0.0 },  { -10.0, -0.0, 0.0 },  { -20.0, -0.0, 0.0 },  { -30.0, -0.0, 0.0 },
                                                                    { -0.0, -10.0, 0.0 }, { -10.0, -10.0, 0.0 }, { -20.0, -10.0, 0.0 }, { -30.0, -10.0, 0.0 },
                                                                    { -0.0, -20.0, 0.0 }, { -10.0, -20.0, 0.0 }, { -20.0, -20.0, 0.0 }, { -30.0, -20.0, 0.0 },
                                                                    { -0.0, -30.0, 0.0 }, { -10.0, -30.0, 0.0 }, { -20.0, -30.0, 0.0 }, { -30.0, -30.0, 0.0 } };

/// Absolute path to the committed legacy fixture, under the in-source
/// Fixtures/ directory wired by CMake.
std::string fixturePath()
{
  return std::string(LIVER_BEZIER_STORAGE_TEST_FIXTURE_DIR) + "/legacy_resection.lrp.fcsv";
}

/// Generate a unique temp path with the given extension under the
/// CMake binary tree's Testing/Temporary directory.
std::string makeTempPath(const std::string& extension)
{
  static int counter = 0;
  ++counter;
  std::ostringstream ss;
  ss << LIVER_BEZIER_STORAGE_TEST_TEMP_DIR << "/vtkMRMLResectionPlanLegacyFcsvMigrationTest_" << static_cast<long long>(LIVER_LEGACY_GETPID()) << "_" << counter << "."
     << extension;
  return ss.str();
}

/// Read the i-th migrated control point off the carrier's flat control
/// grid (3 * point-index .. +2).  The carrier stores 3 * rows * cols
/// doubles; for a 4x4 grid that is the 48 doubles backing the 16
/// points.
void carrierControlPoint(vtkMRMLBezierSurfaceNode* carrier, int i, double out[3])
{
  const double* grid = carrier->GetControlGrid();
  out[0] = grid[i * 3 + 0];
  out[1] = grid[i * 3 + 1];
  out[2] = grid[i * 3 + 2];
}

//------------------------------------------------------------------------------
// Fork C -- the seamless legacy migration invariant.
//
// Loads the committed legacy ``.lrp.fcsv`` through the v2 plan-storage
// path and asserts the full migration contract:
//
//   1. Control-point equality  -- all 16 control points land on the
//      materialised Bezier carrier matching the fixture (within
//      kCoordinateTolerance).
//   2. Documented defaults     -- every field absent from the legacy
//      format gets the v2 reader default (SafetyMargin_mm == 0.0,
//      RiskMargin_mm == 0.0, OrderIndex == -1, state == Init).
//      Source of truth: vtkMRMLResectionPlanStorageNode.h §"Optional-
//      field tolerance".
//   3. Loud gap                -- the storage node's GetUserMessages()
//      carries a non-empty warning naming margins AND order AND state
//      as defaulted (not just margins).  This is the storage node's own
//      user-message collection, DISTINCT from the Markups-fiducial
//      deprecation warning the fcsv parse emits.
//   4. Round-trip              -- fcsv read -> .lrp.json write preserves
//      the 16 control points value-identically.
int testLegacyFcsvMigratesToPlanWithDefaults()
{
  // RED-fail (not skip): the legacy ``.fcsv`` migration branch does not
  // exist yet, so the ReadData below returns 0 and the first CHECK_INT
  // fails hard against the current tree.  The follow-up implementer
  // commit lands the branch and flips this green.  ctkTest's SIMPLE_TEST
  // driver has no skip primitive; the deliberate red is the signal.

  // --------------------------------------------------------------------------
  // Load the legacy fcsv through the v2 plan-storage path.
  // --------------------------------------------------------------------------
  vtkNew<vtkMRMLScene> scene;
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanNode>::New());
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLBezierSurfaceNode>::New());
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanStorageNode>::New());
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLLiverResectionCSVStorageNode>::New());

  vtkNew<vtkMRMLResectionPlanNode> plan;
  scene->AddNode(plan.GetPointer());

  vtkNew<vtkMRMLResectionPlanStorageNode> storage;
  scene->AddNode(storage.GetPointer());
  storage->SetFileName(fixturePath().c_str());
  plan->SetAndObserveStorageNodeID(storage->GetID());

  // The fcsv parse pulls the Markups-fiducial deprecation warning
  // ("fcsv format is deprecated ... use .mrk.json"); suppress it so
  // CTest's WITH_VTK_ERROR_OUTPUT_CHECK does not flag it.  Precedent:
  // vtkMRMLLiverResectionStorageRoundTripTest.cxx Phase 1.  Note: this
  // suppression is ORTHOGONAL to assertion 3 below -- that asserts the
  // storage node's OWN GetUserMessages collection, not this VTK error
  // stream.
  TESTING_OUTPUT_IGNORE_WARNINGS_ERRORS_BEGIN();
  const int readStatus = storage->ReadData(plan.GetPointer());
  TESTING_OUTPUT_IGNORE_WARNINGS_ERRORS_END();
  CHECK_INT(readStatus, 1);

  // --------------------------------------------------------------------------
  // Assertion 1 -- control-point equality.  The migration must
  // materialise a Bezier carrier wired through the plan's geometry ref.
  // --------------------------------------------------------------------------
  vtkMRMLBezierSurfaceNode* carrier = vtkMRMLBezierSurfaceNode::SafeDownCast(plan->GetGeometryNode());
  CHECK_NOT_NULL(carrier);
  CHECK_INT(static_cast<int>(carrier->GetControlGridLength()), kBezierControlPointCount * 3);
  for (int i = 0; i < kBezierControlPointCount; ++i)
  {
    double p[3] = { 0.0, 0.0, 0.0 };
    carrierControlPoint(carrier, i, p);
    for (int d = 0; d < 3; ++d)
    {
      CHECK_DOUBLE_TOLERANCE(p[d], kFixtureControlPoints[i][d], kCoordinateTolerance);
    }
  }

  // --------------------------------------------------------------------------
  // Assertion 2 -- documented defaults applied for every legacy-absent
  // field.  vtkMRMLResectionPlanStorageNode.h §"Optional-field
  // tolerance".
  // --------------------------------------------------------------------------
  CHECK_DOUBLE(plan->GetSafetyMargin_mm(), 0.0);
  CHECK_DOUBLE(plan->GetRiskMargin_mm(), 0.0);
  CHECK_INT(plan->GetOrderIndex(), -1);
  CHECK_INT(plan->GetState(), vtkMRMLResectionPlanNode::Init);

  // --------------------------------------------------------------------------
  // Assertion 3 -- loud gap.  The storage node's OWN user-message
  // collection carries a non-empty warning naming margins AND order AND
  // state as defaulted (a loud, not silent, upgrade).  Distinct from
  // the fcsv deprecation warning suppressed above.
  // --------------------------------------------------------------------------
  vtkMRMLMessageCollection* messages = storage->GetUserMessages();
  CHECK_NOT_NULL(messages);
  if (messages->GetNumberOfMessages() < 1)
  {
    std::cerr << "Legacy migration did not record any user message -- the upgrade must be loud" << std::endl;
    return EXIT_FAILURE;
  }
  const std::string allMessages = messages->GetAllMessagesAsString();
  const char* mustName[] = { "margin", "order", "state" };
  for (const char* token : mustName)
  {
    if (allMessages.find(token) == std::string::npos)
    {
      std::cerr << "Legacy migration warning must name '" << token << "' as defaulted; got: " << allMessages << std::endl;
      return EXIT_FAILURE;
    }
  }

  // --------------------------------------------------------------------------
  // Assertion 4 -- round-trip.  fcsv read -> .lrp.json write preserves
  // the 16 control points value-identically.  Read the written JSON
  // back into a fresh plan + carrier and compare against the fixture.
  // --------------------------------------------------------------------------
  const std::string jsonPath = makeTempPath("lrp.json");
  vtkNew<vtkMRMLResectionPlanStorageNode> writeStorage;
  writeStorage->SetFileName(jsonPath.c_str());
  CHECK_INT(writeStorage->WriteData(plan.GetPointer()), 1);

  vtkNew<vtkMRMLScene> sinkScene;
  sinkScene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanNode>::New());
  sinkScene->RegisterNodeClass(vtkSmartPointer<vtkMRMLBezierSurfaceNode>::New());
  sinkScene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanStorageNode>::New());

  vtkNew<vtkMRMLResectionPlanNode> sinkPlan;
  vtkNew<vtkMRMLBezierSurfaceNode> sinkCarrier;
  sinkScene->AddNode(sinkPlan.GetPointer());
  sinkScene->AddNode(sinkCarrier.GetPointer());
  sinkPlan->SetAndObserveGeometryNode(sinkCarrier.GetPointer());

  vtkNew<vtkMRMLResectionPlanStorageNode> readStorage;
  readStorage->SetFileName(jsonPath.c_str());
  CHECK_INT(readStorage->ReadData(sinkPlan.GetPointer()), 1);

  vtkMRMLBezierSurfaceNode* roundTripped = vtkMRMLBezierSurfaceNode::SafeDownCast(sinkPlan->GetGeometryNode());
  CHECK_NOT_NULL(roundTripped);
  for (int i = 0; i < kBezierControlPointCount; ++i)
  {
    double p[3] = { 0.0, 0.0, 0.0 };
    carrierControlPoint(roundTripped, i, p);
    for (int d = 0; d < 3; ++d)
    {
      CHECK_DOUBLE_TOLERANCE(p[d], kFixtureControlPoints[i][d], kCoordinateTolerance);
    }
  }

  vtksys::SystemTools::RemoveFile(jsonPath);
  return EXIT_SUCCESS;
}

} // namespace

//------------------------------------------------------------------------------
int vtkMRMLResectionPlanLegacyFcsvMigrationTest(int, char*[])
{
  CHECK_EXIT_SUCCESS(testLegacyFcsvMigratesToPlanWithDefaults());

  std::cout << "vtkMRMLResectionPlanLegacyFcsvMigrationTest completed successfully" << std::endl;
  return EXIT_SUCCESS;
}

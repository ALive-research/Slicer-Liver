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
 * \file vtkMRMLResectionPlanGeometryRefRoundTripTest.cxx
 *
 * CHARACTERIZATION test (GREEN against the current tree) for T2.7-2b.
 *
 * What it pins
 * ------------
 * The plan-to-carrier association survives a ``.lrp.json`` write/read
 * ENTIRELY through the typed ``geometry`` node-ref on
 * ``vtkMRMLResectionPlanNode`` plus the carrier's own persistence -- so
 * that ``vtkMRMLResectionPlanNode::GetGeometryNode()`` resolves the
 * carrier after a standalone load into a fresh scene.  No
 * ``vtkSlicerLiverResectionsLogic`` instance, and no logic-side
 * association map, participates.
 *
 * Why this matters for T2.7-2b
 * ----------------------------
 * The legacy ``vtkSlicerLiverResectionsLogic`` carried SIX bookkeeping
 * maps (``ResectionToBezierMap`` / ``BezierToResectionMap`` and
 * siblings) to recover the resection<->surface association at runtime.
 * T2.7-2b retires those maps; the association is recovered instead from
 * the persisted ``geometry`` node-ref.  This test characterises the
 * surviving mechanism -- the ref round-trips and re-resolves on load
 * with no logic in the loop -- which is the contract that makes the 6
 * maps removable.  A green run says the maps are NOT load-bearing for
 * the association; a future red run surfaces a regression in the ref's
 * persistence.
 *
 * GREEN-not-RED rationale (per the test-first brief): the typed
 * ``geometry`` ref already round-trips on the current tree (the
 * wrapper-vs-carrier landing wired the reader to instantiate the carrier
 * and re-resolve the ref).  Per the maintainer's guidance, an
 * already-satisfied invariant is pinned as an explicit characterization
 * test, not forced red.  This test does NOT assert the absence of the
 * retired node or the maps (no colour-of-the-sky absence lock) -- it
 * pins the positive surviving behaviour.
 *
 * Architectural anchors:
 *   - ADR-0014 §1 wrapper-vs-carrier split + ADR-0023 amendment
 *     §"Wrapper-vs-carrier pattern" -- the plan wrapper references the
 *     carrier through the typed ``geometry`` node-ref; the carrier
 *     persists through the wrapper's storage.
 *   - ``Docs/design/resection-plan-architecture/03-storage-ownership.md``
 *     §"Plan node" -- the storage node walks the ``geometry`` ref out of
 *     the file and re-instantiates the carrier on load.
 *   - ``vtkMRMLResectionPlanNode.h`` §"Node references" --
 *     ``GetGeometryNode()`` is the typed re-resolution accessor.
 *
 * ADR-0003 testability: pure MRML-level test, ctkTest driver, no Slicer
 * launch and no logic library -- the absence of the logic dependency is
 * the POINT (it proves the association needs no logic-side map).
 */

// Module MRML includes -- the v2 plan / carrier / storage triad.
#include "vtkMRMLResectionPlanNode.h"
#include "vtkMRMLResectionPlanStorageNode.h"
#include "vtkMRMLBezierSurfaceNode.h"

// MRML includes
#include "vtkMRMLCoreTestingMacros.h"
#include "vtkMRMLScene.h"

// VTK includes
#include <vtkCollection.h>
#include <vtkNew.h>
#include <vtkSmartPointer.h>
#include <vtksys/SystemTools.hxx>

// STD includes
#include <iostream>
#include <sstream>
#include <string>

// Portable getpid -- temp-file collision avoidance, same scheme as the
// sibling vtkMRMLResectionPlanStorageNodeTest1.cxx.
#if defined(_WIN32)
# include <process.h>
# define LIVER_GEOMREF_GETPID _getpid
#else
# include <unistd.h>
# define LIVER_GEOMREF_GETPID ::getpid
#endif

namespace
{

constexpr double kCoordinateTolerance = 1e-9;

/// Generate a unique temp path with the given extension under the
/// CMake binary tree's Testing/Temporary directory.  File-local per the
/// no-shared-helpers convention.
std::string makeTempPath(const std::string& extension)
{
  static int counter = 0;
  ++counter;
  std::ostringstream ss;
  ss << LIVER_BEZIER_STORAGE_TEST_TEMP_DIR << "/vtkMRMLResectionPlanGeometryRefRoundTripTest_" << static_cast<long long>(LIVER_GEOMREF_GETPID()) << "_" << counter << "."
     << extension;
  return ss.str();
}

//------------------------------------------------------------------------------
// Characterization -- a plan + Bezier carrier written to .lrp.json and
// read back into a FRESH scene with no logic instance re-resolves the
// carrier via GetGeometryNode(), and the carrier's control grid is
// value-identical.  Pins the geometry-ref-only association mechanism
// that makes the 6 legacy logic maps removable (T2.7-2b verdict 2).
// [ADR-0014 §1; ADR-0023 §"Wrapper-vs-carrier pattern"]
int testGeometryRefResolvesCarrierAfterStandaloneLoad()
{
  // --------------------------------------------------------------------------
  // Author a v2 fixture: plan -- geometry --> Bezier carrier.  Distinct
  // control-grid values so the round-trip identity is observable.
  // --------------------------------------------------------------------------
  double grid[vtkMRMLBezierSurfaceNode::ControlGridSize];
  for (int i = 0; i < vtkMRMLBezierSurfaceNode::ControlGridSize; ++i)
  {
    grid[i] = static_cast<double>(i) * 0.25 - 1.5;
  }

  std::string fixturePath;
  {
    vtkNew<vtkMRMLScene> srcScene;
    srcScene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanNode>::New());
    srcScene->RegisterNodeClass(vtkSmartPointer<vtkMRMLBezierSurfaceNode>::New());

    vtkNew<vtkMRMLResectionPlanNode> plan;
    vtkNew<vtkMRMLBezierSurfaceNode> carrier;
    srcScene->AddNode(plan.GetPointer());
    srcScene->AddNode(carrier.GetPointer());
    carrier->SetControlGrid(grid);
    plan->SetAndObserveGeometryNode(carrier.GetPointer());

    // The ref must resolve in the authoring scene before any I/O.
    CHECK_NOT_NULL(plan->GetGeometryNode());

    fixturePath = makeTempPath("lrp.json");
    vtkNew<vtkMRMLResectionPlanStorageNode> writeStorage;
    writeStorage->SetFileName(fixturePath.c_str());
    CHECK_INT(writeStorage->WriteData(plan.GetPointer()), 1);
  }

  // --------------------------------------------------------------------------
  // Standalone load into a fresh scene -- NO logic, NO pre-wired carrier.
  // The reader must instantiate the carrier and re-resolve the geometry
  // ref purely from the persisted file.
  // --------------------------------------------------------------------------
  vtkNew<vtkMRMLScene> sinkScene;
  sinkScene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanNode>::New());
  sinkScene->RegisterNodeClass(vtkSmartPointer<vtkMRMLBezierSurfaceNode>::New());
  sinkScene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanStorageNode>::New());

  vtkNew<vtkMRMLResectionPlanNode> sinkPlan;
  sinkScene->AddNode(sinkPlan.GetPointer());

  vtkNew<vtkMRMLResectionPlanStorageNode> readStorage;
  sinkScene->AddNode(readStorage.GetPointer());
  readStorage->SetFileName(fixturePath.c_str());
  sinkPlan->SetAndObserveStorageNodeID(readStorage->GetID());
  CHECK_INT(readStorage->ReadData(sinkPlan.GetPointer()), 1);

  // The association survived: GetGeometryNode() resolves the carrier,
  // instantiated by the reader from the persisted geometry ref alone.
  vtkMRMLBezierSurfaceNode* roundTripped = vtkMRMLBezierSurfaceNode::SafeDownCast(sinkPlan->GetGeometryNode());
  CHECK_NOT_NULL(roundTripped);

  // Exactly one carrier in the sink scene -- the reader did not duplicate
  // it, and (no logic in the loop) nothing spawned a second one.
  CHECK_INT(sinkScene->GetNumberOfNodesByClass("vtkMRMLBezierSurfaceNode"), 1);

  // The carrier's bulk data round-tripped value-identically.
  CHECK_INT(static_cast<int>(roundTripped->GetControlGridLength()), vtkMRMLBezierSurfaceNode::ControlGridSize);
  const double* roundTrippedGrid = roundTripped->GetControlGrid();
  for (int i = 0; i < vtkMRMLBezierSurfaceNode::ControlGridSize; ++i)
  {
    CHECK_DOUBLE_TOLERANCE(roundTrippedGrid[i], grid[i], kCoordinateTolerance);
  }

  vtksys::SystemTools::RemoveFile(fixturePath);
  return EXIT_SUCCESS;
}

} // namespace

//------------------------------------------------------------------------------
int vtkMRMLResectionPlanGeometryRefRoundTripTest(int, char*[])
{
  CHECK_EXIT_SUCCESS(testGeometryRefResolvesCarrierAfterStandaloneLoad());

  std::cout << "vtkMRMLResectionPlanGeometryRefRoundTripTest completed successfully" << std::endl;
  return EXIT_SUCCESS;
}

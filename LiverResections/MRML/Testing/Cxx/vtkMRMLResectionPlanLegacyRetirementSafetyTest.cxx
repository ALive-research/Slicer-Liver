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
 * \file vtkMRMLResectionPlanLegacyRetirementSafetyTest.cxx
 *
 * CHARACTERIZATION test (Feathers-style) pinning the behaviour that
 * must survive the retirement of the v1 ``vtkMRMLLiverResectionNode``
 * family.  Unlike a RED test-first scaffold, every assertion here is
 * expected GREEN against the CURRENT tree: a green run proves the
 * legacy node is already dead in the production load path, so removing
 * it later is provably safe; a red run surfaces a real dependency that
 * the retirement would break.
 *
 * Why this is the "retirement-safety lock":
 *
 *   The v1 ``vtkMRMLLiverResectionNode`` (+ its display / 2D-DM / CSV
 *   writer) is superseded by the wrapper-vs-carrier pair
 *   ``vtkMRMLResectionPlanNode`` + ``vtkMRMLBezierSurfaceNode``.  The
 *   maintainer decision is a FULL retire: v2 still loads v1
 *   ``.lrp.fcsv`` *data* files (via the migration seam), but NOT v1
 *   *scene* files containing the retired node -- so no scene-alias is
 *   needed.  The only surviving touch-point is the quarantined,
 *   non-registered ``vtkMRMLLiverResectionCSVStorageNode`` used as an
 *   off-scene parse vehicle inside
 *   ``vtkMRMLResectionPlanStorageNode::ReadFcsv``.
 *
 *   These tests pin that the migration produces NO scene-resident
 *   ``vtkMRMLLiverResectionNode`` and does NOT depend on that class
 *   being registered in the working scene.  They constrain the later
 *   retirement PRs (sever the migration's compile-time dependency on
 *   the legacy node; delete the legacy node + dead logic + writer +
 *   2D displayable manager) to stay value-preserving.
 *
 * Architectural anchors:
 *   - ADR-0014 §"Fourth layer: clinical/method wrapper; wrapper-vs-
 *     carrier pattern" -- the retirement of ``vtkMRMLLiverResectionNode``
 *     and the v1 ``.lrp.fcsv`` -> v2 migration that must outlive it.
 *   - ADR-0003 §"testability invariant" -- a behaviour-changing
 *     change (the retirement) carries the test that pins the surviving
 *     behaviour first.
 *   - ``vtkMRMLResectionPlanStorageNode.h`` §"Legacy `.lrp.fcsv`" --
 *     the off-scene parse-vehicle contract this test characterises.
 *   - ``Docs/migrations/v1-to-v2.md`` -- the documented v1->v2 data
 *     upgrade.
 *
 * Relationship to sibling tests (no duplication):
 *   - ``vtkMRMLResectionPlanLegacyFcsvMigrationTest`` already pins the
 *     migration's DATA contract (16 control points, documented
 *     defaults, loud user message, .lrp.json round-trip) and that the
 *     CSV parse vehicle is not added to the scene.  This file does NOT
 *     re-assert any of that; it adds the orthogonal RETIREMENT-SAFETY
 *     invariants: zero scene-resident legacy nodes, and migration
 *     working in a scene where the legacy node class is unregistered.
 */

// This module MRML includes.  The legacy ``vtkMRMLLiverResectionNode``
// header is included ONLY to name its class string in the count
// assertions -- the test never instantiates one.  After the retirement
// PR that deletes the class, the count assertions become a literal
// string-constant check and this include is dropped together with the
// class; see the file header and ADR-0014 §"Fourth layer".
#include "vtkMRMLBezierSurfaceNode.h"
#include "vtkMRMLResectionPlanNode.h"
#include "vtkMRMLResectionPlanStorageNode.h"

// MRML includes
#include "vtkMRMLCoreTestingMacros.h"
#include "vtkMRMLScene.h"

// VTK includes
#include <vtkNew.h>
#include <vtkSmartPointer.h>

// STD includes
#include <cstdlib>
#include <iostream>
#include <string>

namespace
{

/// The retired v1 node's class name, named as a string constant so the
/// assertions stand even after the class header is gone (the retirement
/// PR deletes ``vtkMRMLLiverResectionNode`` but the production scene
/// must still contain zero of them).  Kept file-local per the
/// no-shared-helpers convention.
constexpr const char* kLegacyResectionClass = "vtkMRMLLiverResectionNode";

/// Absolute path to the committed legacy fixture, reusing the macro the
/// sibling migration test wires through CMake.
std::string fixturePath()
{
  return std::string(LIVER_BEZIER_STORAGE_TEST_FIXTURE_DIR) + "/legacy_resection.lrp.fcsv";
}

//------------------------------------------------------------------------------
// Invariant 1 -- retirement-safety: a representative legacy-fcsv load
// through the production plan-storage path leaves ZERO scene-resident
// ``vtkMRMLLiverResectionNode`` instances.  The migration lifts the
// control points into a v2 plan + Bezier carrier; the legacy node is
// only ever an off-scene parse vehicle.  This is the green-now proof
// that the legacy node is already dead in production, so deleting it is
// safe.
// [ADR-0014 §"Fourth layer"; vtkMRMLResectionPlanStorageNode.h
//  §"Legacy `.lrp.fcsv`"]
int testLegacyFcsvLoadCreatesNoLegacyResectionNode()
{
  vtkNew<vtkMRMLScene> scene;
  // Register ONLY the v2 family -- the production registration set the
  // reader/logic path relies on.  The legacy node class is deliberately
  // NOT registered here (it is for invariant 2, but its absence is
  // already meaningful: the load must not need it).
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanNode>::New());
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLBezierSurfaceNode>::New());
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanStorageNode>::New());

  vtkNew<vtkMRMLResectionPlanNode> plan;
  scene->AddNode(plan.GetPointer());

  vtkNew<vtkMRMLResectionPlanStorageNode> storage;
  scene->AddNode(storage.GetPointer());
  storage->SetFileName(fixturePath().c_str());
  plan->SetAndObserveStorageNodeID(storage->GetID());

  // The fcsv parse pulls the Markups-fiducial deprecation warning;
  // suppress it so CTest's WITH_VTK_ERROR_OUTPUT_CHECK does not flag
  // it.  Same precedent as the sibling migration test.
  TESTING_OUTPUT_IGNORE_WARNINGS_ERRORS_BEGIN();
  const int readStatus = storage->ReadData(plan.GetPointer());
  TESTING_OUTPUT_IGNORE_WARNINGS_ERRORS_END();
  CHECK_INT(readStatus, 1);

  // The retirement-safety invariant: no legacy node landed in the
  // scene.  The migration must yield exactly the v2 family.
  CHECK_INT(scene->GetNumberOfNodesByClass(kLegacyResectionClass), 0);
  CHECK_INT(scene->GetNumberOfNodesByClass("vtkMRMLBezierSurfaceNode"), 1);
  CHECK_INT(scene->GetNumberOfNodesByClass("vtkMRMLResectionPlanNode"), 1);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 2 -- registration-independence: the ``.lrp.fcsv`` migration
// succeeds in a scene where ``vtkMRMLLiverResectionNode`` is NOT
// registered.  The parse vehicle inside ReadFcsv is built with vtkNew
// (off-scene), so the migration never asks the scene to instantiate the
// legacy class by name.  Pinning this de-risks the retirement PR that
// severs the migration seam's compile-time dependency on the legacy
// node: the seam was already runtime-independent of scene registration.
// [ADR-0014 §"Fourth layer"; vtkMRMLResectionPlanStorageNode.h
//  §"Legacy `.lrp.fcsv`" -- "built off-scene ... does not depend on the
//  ... node classes being registered"]
int testLegacyFcsvMigrationIndependentOfLegacyRegistration()
{
  vtkNew<vtkMRMLScene> scene;
  // The v2 family only.  Crucially, neither vtkMRMLLiverResectionNode
  // NOR vtkMRMLLiverResectionCSVStorageNode is registered -- the seam
  // must not depend on either being known to this scene.
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanNode>::New());
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLBezierSurfaceNode>::New());
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanStorageNode>::New());

  // Sanity: the legacy class really is unregistered in this scene.
  // (CreateNodeByClass returns null for an unregistered class.)
  vtkSmartPointer<vtkMRMLNode> probe = vtkSmartPointer<vtkMRMLNode>::Take(scene->CreateNodeByClass(kLegacyResectionClass));
  CHECK_NULL(probe);

  vtkNew<vtkMRMLResectionPlanNode> plan;
  scene->AddNode(plan.GetPointer());

  vtkNew<vtkMRMLResectionPlanStorageNode> storage;
  scene->AddNode(storage.GetPointer());
  storage->SetFileName(fixturePath().c_str());
  plan->SetAndObserveStorageNodeID(storage->GetID());

  TESTING_OUTPUT_IGNORE_WARNINGS_ERRORS_BEGIN();
  const int readStatus = storage->ReadData(plan.GetPointer());
  TESTING_OUTPUT_IGNORE_WARNINGS_ERRORS_END();
  // The migration succeeds despite the legacy class being unregistered.
  CHECK_INT(readStatus, 1);

  // It produced the v2 carrier wired under the plan, and -- again --
  // zero scene-resident legacy nodes.
  vtkMRMLBezierSurfaceNode* carrier = vtkMRMLBezierSurfaceNode::SafeDownCast(plan->GetGeometryNode());
  CHECK_NOT_NULL(carrier);
  CHECK_INT(scene->GetNumberOfNodesByClass(kLegacyResectionClass), 0);
  return EXIT_SUCCESS;
}

} // namespace

//------------------------------------------------------------------------------
int vtkMRMLResectionPlanLegacyRetirementSafetyTest(int, char*[])
{
  CHECK_EXIT_SUCCESS(testLegacyFcsvLoadCreatesNoLegacyResectionNode());
  CHECK_EXIT_SUCCESS(testLegacyFcsvMigrationIndependentOfLegacyRegistration());

  std::cout << "vtkMRMLResectionPlanLegacyRetirementSafetyTest completed successfully" << std::endl;
  return EXIT_SUCCESS;
}

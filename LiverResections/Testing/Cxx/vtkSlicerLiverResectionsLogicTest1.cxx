/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2017-2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

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

  This file was originally developed by Rafael Palomar (Oslo University
  Hospital and NTNU) and was supported by The Research Council of Norway
  through the ALive project (grant nr. 311393).

==============================================================================*/

// NOTE: This file is inspired in vtkSlicerMarkupsLogicTest1.cxx from 3D Slicer

// MRML includes
#include "vtkMRMLCoreTestingMacros.h"
#include "vtkMRMLScene.h"

// VTKSlicer includes
#include "vtkSlicerLiverResectionsLogic.h"

// Module MRML includes (create-API triad)
#include "vtkMRMLBezierSurfaceNode.h"
#include "vtkMRMLParametricSurfaceDisplayNode.h"
#include "vtkMRMLResectionPlanNode.h"

// VTK includes
#include <vtkNew.h>
#include <vtkSmartPointer.h>

// STD includes
#include <cstdlib>

namespace
{
void checkAddAndGetNode(vtkSmartPointer<vtkMRMLScene> scene, const char* ClassName)
{
  auto node = scene->GetFirstNodeByClass(ClassName);
  assert(node == nullptr);

  std::string newNodeName = ClassName;
  newNodeName.append("_Test");
  scene->AddNewNodeByClass(ClassName, newNodeName);
  node = scene->GetFirstNodeByClass(ClassName);
  assert(node != nullptr);

  auto node2 = scene->GetNodeByID(node->GetID());
  assert(node2 != nullptr);
  assert(node == node2);
}
} // namespace

int vtkSlicerLiverResectionsLogicTest1(int, char*[])
{
  auto scene = vtkSmartPointer<vtkMRMLScene>::New();

  vtkNew<vtkSlicerLiverResectionsLogic> logic1;

  logic1->SetMRMLScene(scene);

  // LiverResources data / display nodes (ADR-0014 §1) must be
  // registered by ``RegisterNodes()``.  The surface is non-storable
  // per the 2026-05-25 wrapper-vs-carrier amendment; persistence
  // flows through the plan-rooted storage node.
  checkAddAndGetNode(scene, "vtkMRMLBezierSurfaceNode");
  checkAddAndGetNode(scene, "vtkMRMLParametricSurfaceDisplayNode");
  checkAddAndGetNode(scene, "vtkMRMLResectionPlanNode");
  checkAddAndGetNode(scene, "vtkMRMLResectionPlanStorageNode");

  // T2.6-LayerDM — call 2 of ADR-0013 §5's three-call contract is
  // performed in ``qSlicerLiverResectionsModule::setup()`` rather
  // than in the logic, so this logic-only test cannot exercise it
  // directly (no qSlicerApplication instance reachable from a ctkTest
  // logic harness).  The Pipeline-creator registration (call 3) is
  // similarly delegated to ``LiverResectionsLib`` via
  // ``pythonManager()->executeString``.  Coverage for both calls
  // lives in the manual-launch probe + the workflow-layer pytest
  // under ``Testing/Python/workflow/`` (ADR-0008 §3).

  // #501 slice 1 — the logic create-API mints the v2 carrier + plan +
  // display triad interactively, identically to the file loaders (ADR-0032
  // interaction model; ADR-0014 §"Fourth layer" wrapper/carrier; ADR-0031).
  // Pins the structural invariant: a resection-plan wrapper whose geometry
  // reference resolves a Bezier carrier that carries a parametric-surface
  // display node (the LayerDM Pipeline creator matches on that display node),
  // with the plan in the Init state (ADR-0019).
  {
    vtkMRMLResectionPlanNode* plan = logic1->CreateResectionPlan("Resection_CreateApiTest");
    CHECK_NOT_NULL(plan);
    CHECK_NOT_NULL(scene->GetNodeByID(plan->GetID()));

    vtkMRMLBezierSurfaceNode* carrier = vtkMRMLBezierSurfaceNode::SafeDownCast(plan->GetGeometryNode());
    CHECK_NOT_NULL(carrier);
    CHECK_NOT_NULL(vtkMRMLParametricSurfaceDisplayNode::SafeDownCast(carrier->GetDisplayNode()));
    CHECK_INT(plan->GetState(), vtkMRMLResectionPlanNode::Init);
  }

  return EXIT_SUCCESS;
}

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
 * \file vtkSlicerLiverResectionsLogicCarrierStateAdvanceTest.cxx
 *
 * Test-first (RED) scaffolding for T2.7-2b.  Pins the SURVIVING v2
 * behaviour that the legacy-node arm of
 * ``vtkSlicerLiverResectionsLogic::ProcessMRMLNodesEvents`` must be
 * REPLACED by -- it does NOT assert the absence of the retired class.
 *
 * The invariant
 * --------------
 * Today the ``StartInteractionEvent`` arm of ``ProcessMRMLNodesEvents``
 * does: Markups-Bezier ``StartInteractionEvent`` ->
 * ``GetResectionFromBezier`` (a legacy ``BezierToResectionMap`` lookup)
 * -> ``SetState(vtkMRMLLiverResectionNode::Deformation)`` on the legacy
 * resection node.  The whole arm hangs off the legacy node + the 6
 * association maps that T2.7-2b retires.
 *
 * The v2 replacement moves the state transition ONTO THE CARRIER.  The
 * surface carrier ``vtkMRMLBezierSurfaceNode`` already owns the ADR-0019
 * ``ResectionState`` machine, and the legacy ``Deformation`` workflow
 * state maps to the carrier's ``Planning`` state (per the T2.7-2b plan:
 * "legacy Deformation == carrier Planning").  After the rewrite, a
 * Bezier-surface-carrier ``StartInteractionEvent`` routed through
 * ``ProcessMRMLNodesEvents`` must advance the carrier's own state machine
 * ``Init -> Planning`` -- no legacy node, no maps involved.
 *
 * Why this is RED against the current tree
 * ----------------------------------------
 * ``ProcessMRMLNodesEvents`` currently downcasts the interaction caller
 * to ``vtkMRMLMarkupsBezierSurfaceNode`` (the widget node) and to the
 * legacy ``vtkMRMLLiverResectionNode``; it has NO arm that recognises
 * the data-only carrier ``vtkMRMLBezierSurfaceNode``.  A carrier passed
 * as the caller is therefore ignored and stays at ``Init`` -- the first
 * state assertion below fails red.  The 2b rewrite adds the carrier arm
 * and flips this green.
 *
 * Architectural anchors:
 *   - ADR-0019 §"Resection state machine" -- the irreversible
 *     ``Init -> Planning`` transition and its read-only-after-Init
 *     consequence.
 *   - ADR-0014 §1 wrapper-vs-carrier split + ADR-0023 amendment
 *     §"Wrapper-vs-carrier pattern" -- the carrier
 *     (``vtkMRMLBezierSurfaceNode``) owns the geometry + state; the plan
 *     wrapper references it through the typed ``geometry`` node-ref.
 *   - ``LiverBezierSurfacePipeline.py`` §``commit()`` -- the Python
 *     Pipeline seam that drives the same irreversible ``Init -> Planning``
 *     transition; this C++ test pins the node/logic side of the same
 *     contract.
 *
 * Scope note (NO retirement-safety / absence lock): per the maintainer's
 * colour-of-the-sky guidance, this test pins a POSITIVE v2 invariant
 * (the carrier advances) and deliberately does NOT assert "0 legacy
 * nodes" or "migration works without the legacy class registered".
 *
 * ADR-0003 testability: this is a Logic-level test -- it links the
 * module MRML + logic libraries (no Slicer launch, no Qt), matching the
 * sibling ``vtkSlicerLiverResectionsLogicSubjectHierarchyCharacterizationTest``.
 */

// LiverResections Logic + MRML includes
#include "vtkMRMLBezierSurfaceNode.h"
#include "vtkMRMLResectionPlanNode.h"
#include "vtkSlicerLiverResectionsLogic.h"

// MRML includes
#include "vtkMRMLCoreTestingMacros.h"
#include "vtkMRMLScene.h"

// VTK includes
#include <vtkCommand.h>
#include <vtkNew.h>
#include <vtkSmartPointer.h>

// STD includes
#include <iostream>

namespace
{

//------------------------------------------------------------------------------
// Invariant -- a Bezier-surface-CARRIER StartInteractionEvent routed
// through ProcessMRMLNodesEvents advances the carrier's own ADR-0019
// state machine Init -> Planning, replacing the legacy Deformation push
// onto vtkMRMLLiverResectionNode.
//
// RED-fail (not skip): the current ProcessMRMLNodesEvents has no arm for
// the data carrier vtkMRMLBezierSurfaceNode, so the carrier is ignored
// and stays at Init; the first CHECK_INT below fails hard.  The 2b
// rewrite adds the carrier arm and flips this green.  ctkTest's
// SIMPLE_TEST driver has no skip primitive -- the deliberate red is the
// signal.
// [ADR-0019 §"Resection state machine"; T2.7-2b plan verdict 4]
int testCarrierInteractionAdvancesInitToPlanning()
{
  vtkNew<vtkSlicerLiverResectionsLogic> logic;
  vtkNew<vtkMRMLScene> scene;
  // SetMRMLScene runs RegisterNodes + SetMRMLSceneInternal (scene
  // observation), the preconditions for the logic's event handling.
  logic->SetMRMLScene(scene.GetPointer());

  // v2 topology: a plan wrapper referencing the surface carrier via the
  // typed ``geometry`` node-ref (ADR-0014 §1).  No legacy node, no maps.
  vtkNew<vtkMRMLResectionPlanNode> plan;
  vtkNew<vtkMRMLBezierSurfaceNode> carrier;
  scene->AddNode(plan.GetPointer());
  scene->AddNode(carrier.GetPointer());
  plan->SetAndObserveGeometryNode(carrier.GetPointer());

  // Precondition: a freshly-constructed carrier sits in Init.
  CHECK_INT(carrier->GetState(), vtkMRMLBezierSurfaceNode::Init);

  // Drive the interaction seam directly through the public entry point
  // (ProcessMRMLNodesEvents is public on the logic).  The caller is the
  // data CARRIER, not the legacy widget node -- this is the seam the 2b
  // rewrite must recognise.
  logic->ProcessMRMLNodesEvents(carrier.GetPointer(), vtkCommand::StartInteractionEvent, nullptr);

  // The carrier reached via the plan's geometry ref must now be in
  // Planning (legacy Deformation == carrier Planning).
  vtkMRMLBezierSurfaceNode* carrierViaPlan = vtkMRMLBezierSurfaceNode::SafeDownCast(plan->GetGeometryNode());
  CHECK_NOT_NULL(carrierViaPlan);
  CHECK_INT(carrierViaPlan->GetState(), vtkMRMLBezierSurfaceNode::Planning);

  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant -- the carrier advance is IRREVERSIBLE: a second interaction
// must NOT drag the carrier back to Init (one-shot Init -> Planning, per
// ADR-0019).  The carrier's SetState transition matrix already forbids
// Planning -> Init; this pins that the logic seam honours it rather than
// re-issuing a state push that could regress.
//
// RED-fail (not skip): predicated on the carrier reaching Planning in the
// first place, which the current tree never does -- so this fails red on
// the same missing carrier arm.  Green once the rewrite lands the
// idempotent carrier advance.
// [ADR-0019 §"Resection state machine" -- irreversible transition]
int testCarrierAdvanceIsIrreversible()
{
  vtkNew<vtkSlicerLiverResectionsLogic> logic;
  vtkNew<vtkMRMLScene> scene;
  logic->SetMRMLScene(scene.GetPointer());

  vtkNew<vtkMRMLResectionPlanNode> plan;
  vtkNew<vtkMRMLBezierSurfaceNode> carrier;
  scene->AddNode(plan.GetPointer());
  scene->AddNode(carrier.GetPointer());
  plan->SetAndObserveGeometryNode(carrier.GetPointer());

  logic->ProcessMRMLNodesEvents(carrier.GetPointer(), vtkCommand::StartInteractionEvent, nullptr);
  CHECK_INT(carrier->GetState(), vtkMRMLBezierSurfaceNode::Planning);

  // A second interaction must leave the carrier in Planning -- never back
  // to Init.
  logic->ProcessMRMLNodesEvents(carrier.GetPointer(), vtkCommand::StartInteractionEvent, nullptr);
  CHECK_INT(carrier->GetState(), vtkMRMLBezierSurfaceNode::Planning);

  return EXIT_SUCCESS;
}

} // namespace

//------------------------------------------------------------------------------
int vtkSlicerLiverResectionsLogicCarrierStateAdvanceTest(int, char*[])
{
  CHECK_EXIT_SUCCESS(testCarrierInteractionAdvancesInitToPlanning());
  CHECK_EXIT_SUCCESS(testCarrierAdvanceIsIrreversible());

  std::cout << "vtkSlicerLiverResectionsLogicCarrierStateAdvanceTest completed successfully" << std::endl;
  return EXIT_SUCCESS;
}

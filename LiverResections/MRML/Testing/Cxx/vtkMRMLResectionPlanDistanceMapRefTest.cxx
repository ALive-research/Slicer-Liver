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
 * \file vtkMRMLResectionPlanDistanceMapRefTest.cxx
 *
 * Invariant test for ADR-0031: the distance-map volume is a path-specific
 * input of the resection plan and is named by a typed ``distanceMap``
 * node-reference role on ``vtkMRMLResectionPlanNode`` -- NOT on the
 * ``vtkMRMLBezierSurfaceNode`` carrier.
 *
 * What it pins
 * ------------
 *  - The role literal is ``"distanceMap"`` (``GetDistanceMapReferenceRole()``).
 *  - ``SetAndObserveDistanceMapVolumeNode()`` /
 *    ``GetDistanceMapVolumeNode()`` round-trip a ``vtkMRMLScalarVolumeNode``
 *    in-scene: the typed accessor resolves the volume that was set.
 *  - Passing ``nullptr`` clears the reference (the graceful no-distance-map
 *    fallback ADR-0031 preserves).
 *
 * It deliberately does NOT assert the carrier lacks the role (that absence
 * is enforced by the ADR-0031 conformance grep, not a colour-of-the-sky
 * runtime test).
 *
 * ADR-0003 testability: pure MRML-level test, ctkTest driver, no Slicer
 * launch and no logic library.
 *
 * Architectural anchors:
 *   - ADR-0031 -- distance-map input on the resection-plan wrapper.
 *   - ADR-0014 §"Fourth layer" -- wrapper carries path-specific inputs.
 *   - vtkMRMLResectionPlanNode.h §"Node references".
 */

// Module MRML includes
#include "vtkMRMLResectionPlanNode.h"

// MRML includes
#include "vtkMRMLCoreTestingMacros.h"
#include "vtkMRMLScalarVolumeNode.h"
#include "vtkMRMLScene.h"

// VTK includes
#include <vtkNew.h>
#include <vtkSmartPointer.h>

// STD includes
#include <cstring>
#include <iostream>

namespace
{

//------------------------------------------------------------------------------
// The distanceMap reference role round-trips a scalar volume in-scene, and
// the role literal is the canonical "distanceMap" string. [ADR-0031]
int testDistanceMapRefRoundTrip()
{
  // The role literal is the contract the storage node + Pipeline share.
  CHECK_STRING(vtkMRMLResectionPlanNode::GetDistanceMapReferenceRole(), "distanceMap");

  vtkNew<vtkMRMLScene> scene;
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanNode>::New());

  vtkNew<vtkMRMLResectionPlanNode> plan;
  scene->AddNode(plan.GetPointer());

  // No distance map yet -- the typed accessor resolves to nullptr (the
  // graceful fallback ADR-0031 preserves).
  CHECK_NULL(plan->GetDistanceMapVolumeNode());

  vtkNew<vtkMRMLScalarVolumeNode> distanceMap;
  scene->AddNode(distanceMap.GetPointer());
  plan->SetAndObserveDistanceMapVolumeNode(distanceMap.GetPointer());

  // The typed accessor resolves the volume that was set.
  CHECK_POINTER(plan->GetDistanceMapVolumeNode(), distanceMap.GetPointer());

  // Clearing the reference returns to the no-distance-map state.
  plan->SetAndObserveDistanceMapVolumeNode(nullptr);
  CHECK_NULL(plan->GetDistanceMapVolumeNode());

  return EXIT_SUCCESS;
}

} // namespace

//------------------------------------------------------------------------------
int vtkMRMLResectionPlanDistanceMapRefTest(int, char*[])
{
  CHECK_EXIT_SUCCESS(testDistanceMapRefRoundTrip());

  std::cout << "vtkMRMLResectionPlanDistanceMapRefTest completed successfully" << std::endl;
  return EXIT_SUCCESS;
}

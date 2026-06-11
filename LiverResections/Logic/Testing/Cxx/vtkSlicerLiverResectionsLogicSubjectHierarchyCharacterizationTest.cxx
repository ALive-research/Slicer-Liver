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
 * \file vtkSlicerLiverResectionsLogicSubjectHierarchyCharacterizationTest.cxx
 *
 * CHARACTERIZATION test (Feathers-style) pinning the CURRENT
 * Subject-Hierarchy collection behaviour of
 * ``vtkSlicerLiverResectionsLogic::OnMRMLSceneNodeAdded`` -- the wiring
 * that re-parents the surgeon-facing wrapper node under a per-stage
 * "Resections" Subject-Hierarchy folder via
 * ``vtkSlicerSubjectHierarchyFolders::CollectUnderFolder``.
 *
 * Unlike a RED test-first scaffold, this test characterises behaviour
 * that ALREADY SHIPS, so it is expected GREEN against the current
 * ``vtkSlicerLiverResectionsLogic``: a green run verifies the wiring; a
 * red run surfaces a real regression in it.  This converts a
 * previously inspection-only / launched-pytest-skipping assertion into
 * an executing C++ CTest.
 *
 * Behaviour pinned (matches OnMRMLSceneNodeAdded ->
 * vtkSlicerSubjectHierarchyFolders::CollectUnderFolder):
 *
 *   1. A ``vtkMRMLLiverResectionNode`` (the WRAPPER) added to the
 *      logic's observed scene is re-parented under a Subject-Hierarchy
 *      folder named per ``GetResectionsFolderName()`` that is a DIRECT
 *      CHILD of the scene root (scene-root-scoped lookup).
 *      [ADR-0023 §"Subject Hierarchy management convention"]
 *   2. A hidden carrier node (``SetHideFromEditors(true)`` Bezier
 *      surface -- the kind the wrapper-vs-carrier split keeps out of the
 *      Subject-Hierarchy view) is NOT re-parented under "Resections":
 *      only the wrapper is collected.
 *      [ADR-0014 §1 wrapper-vs-carrier split]
 *   3. The folder is lazily created on the first wrapper and REUSED for
 *      the second (exactly one scene-root folder; both wrappers hang off
 *      it).
 *      [ADR-0023 §"Subject Hierarchy management convention"]
 */

// LiverResections Logic + MRML includes
#include "vtkMRMLBezierSurfaceNode.h"
#include "vtkMRMLLiverResectionNode.h"
#include "vtkSlicerLiverResectionsLogic.h"

// SubjectHierarchyFolders includes (single source of truth for the
// folder name -- ADR-0023 §"Subject Hierarchy management convention").
#include "vtkSlicerSubjectHierarchyFolders.h"

// MRML includes
#include "vtkMRMLCoreTestingMacros.h"
#include "vtkMRMLScene.h"
#include "vtkMRMLSubjectHierarchyNode.h"

// VTK includes
#include <vtkNew.h>
#include <vtkSmartPointer.h>

// STD includes
#include <iostream>
#include <string>
#include <vector>

namespace
{

//------------------------------------------------------------------------------
int countSceneRootFoldersNamed(vtkMRMLSubjectHierarchyNode* shNode, const std::string& name)
{
  vtkIdType sceneItem = shNode->GetSceneItemID();
  std::vector<vtkIdType> children;
  shNode->GetItemChildren(sceneItem, children);
  int count = 0;
  for (vtkIdType child : children)
  {
    if (shNode->GetItemName(child) == name)
    {
      ++count;
    }
  }
  return count;
}

//------------------------------------------------------------------------------
// Invariant 1 -- a single wrapper resection node lands under a scene-root
// "Resections" folder via the logic's NodeAdded observer.
// [ADR-0023 §"Subject Hierarchy management convention"]
int testWrapperResectionNodeCollectedUnderFolder()
{
  vtkNew<vtkSlicerLiverResectionsLogic> logic;
  vtkNew<vtkMRMLScene> scene;
  // SetMRMLScene runs RegisterNodes (registers the resection classes)
  // and SetMRMLSceneInternal (observes NodeAddedEvent), the two
  // preconditions for the collector to fire.
  logic->SetMRMLScene(scene.GetPointer());

  const std::string folderName = vtkSlicerSubjectHierarchyFolders::GetResectionsFolderName();

  vtkNew<vtkMRMLLiverResectionNode> resection;
  scene->AddNode(resection.GetPointer());

  vtkMRMLSubjectHierarchyNode* shNode = vtkMRMLSubjectHierarchyNode::GetSubjectHierarchyNode(scene.GetPointer());
  CHECK_NOT_NULL(shNode);

  CHECK_INT(countSceneRootFoldersNamed(shNode, folderName), 1);

  vtkIdType nodeItem = shNode->GetItemByDataNode(resection.GetPointer());
  CHECK_BOOL(nodeItem != vtkMRMLSubjectHierarchyNode::INVALID_ITEM_ID, true);
  vtkIdType parentItem = shNode->GetItemParent(nodeItem);
  CHECK_STD_STRING(shNode->GetItemName(parentItem), folderName);
  // Folder is a direct child of the scene root (scene-root-scoped lookup).
  CHECK_BOOL(shNode->GetItemParent(parentItem) == shNode->GetSceneItemID(), true);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 2 -- a hidden carrier node is NOT re-parented under
// "Resections": only the wrapper is collected (wrapper-vs-carrier split).
// [ADR-0014 §1]
int testHiddenCarrierNotCollectedUnderFolder()
{
  vtkNew<vtkSlicerLiverResectionsLogic> logic;
  vtkNew<vtkMRMLScene> scene;
  logic->SetMRMLScene(scene.GetPointer());

  const std::string folderName = vtkSlicerSubjectHierarchyFolders::GetResectionsFolderName();

  // A hidden carrier -- the kind the wrapper-vs-carrier split keeps out
  // of the Subject-Hierarchy view.  It is not a vtkMRMLLiverResectionNode,
  // so OnMRMLSceneNodeAdded's SafeDownCast guard rejects it.
  vtkNew<vtkMRMLBezierSurfaceNode> carrier;
  carrier->SetHideFromEditors(true);
  scene->AddNode(carrier.GetPointer());

  vtkMRMLSubjectHierarchyNode* shNode = vtkMRMLSubjectHierarchyNode::GetSubjectHierarchyNode(scene.GetPointer());
  CHECK_NOT_NULL(shNode);

  // No "Resections" folder is created for a carrier-only scene, and the
  // carrier is never parented under one.
  CHECK_INT(countSceneRootFoldersNamed(shNode, folderName), 0);

  vtkIdType carrierItem = shNode->GetItemByDataNode(carrier.GetPointer());
  if (carrierItem != vtkMRMLSubjectHierarchyNode::INVALID_ITEM_ID)
  {
    vtkIdType carrierParent = shNode->GetItemParent(carrierItem);
    CHECK_BOOL(shNode->GetItemName(carrierParent) == folderName, false);
  }
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 3 -- the folder is lazily created then REUSED: two wrapper
// resection nodes share exactly one scene-root folder.
// [ADR-0023 §"Subject Hierarchy management convention"]
int testFolderReusedAcrossTwoWrappers()
{
  vtkNew<vtkSlicerLiverResectionsLogic> logic;
  vtkNew<vtkMRMLScene> scene;
  logic->SetMRMLScene(scene.GetPointer());

  const std::string folderName = vtkSlicerSubjectHierarchyFolders::GetResectionsFolderName();

  vtkNew<vtkMRMLLiverResectionNode> first;
  vtkNew<vtkMRMLLiverResectionNode> second;
  scene->AddNode(first.GetPointer());
  scene->AddNode(second.GetPointer());

  vtkMRMLSubjectHierarchyNode* shNode = vtkMRMLSubjectHierarchyNode::GetSubjectHierarchyNode(scene.GetPointer());
  CHECK_NOT_NULL(shNode);

  // The reuse invariant: ONE folder, not two.
  CHECK_INT(countSceneRootFoldersNamed(shNode, folderName), 1);

  vtkIdType firstParent = shNode->GetItemParent(shNode->GetItemByDataNode(first.GetPointer()));
  vtkIdType secondParent = shNode->GetItemParent(shNode->GetItemByDataNode(second.GetPointer()));
  CHECK_BOOL(firstParent == secondParent, true);
  CHECK_STD_STRING(shNode->GetItemName(firstParent), folderName);
  return EXIT_SUCCESS;
}

} // namespace

//------------------------------------------------------------------------------
int vtkSlicerLiverResectionsLogicSubjectHierarchyCharacterizationTest(int, char*[])
{
  CHECK_EXIT_SUCCESS(testWrapperResectionNodeCollectedUnderFolder());
  CHECK_EXIT_SUCCESS(testHiddenCarrierNotCollectedUnderFolder());
  CHECK_EXIT_SUCCESS(testFolderReusedAcrossTwoWrappers());

  std::cout << "vtkSlicerLiverResectionsLogicSubjectHierarchyCharacterizationTest "
               "completed successfully"
            << std::endl;
  return EXIT_SUCCESS;
}

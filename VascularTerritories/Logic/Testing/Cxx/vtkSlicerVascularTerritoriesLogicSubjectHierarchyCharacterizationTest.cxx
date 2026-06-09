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
 * \file vtkSlicerVascularTerritoriesLogicSubjectHierarchyCharacterizationTest.cxx
 *
 * CHARACTERIZATION test (Feathers-style) pinning the CURRENT
 * Subject-Hierarchy collection behaviour of
 * ``vtkSlicerVascularTerritoriesLogic::OnMRMLSceneNodeAdded`` BEFORE the
 * T5.2-f rewrite swaps the inline collector for a
 * ``vtkSlicerSubjectHierarchyFolders::CollectUnderFolder`` call.
 *
 * Per ADR-0003 §"For refactors that preserve behaviour": this test lands
 * BEFORE the behaviour-changing commit and MUST PASS on both the current
 * branch (characterising what the inline collector does) and after the
 * rewrite (proving the utility-backed path is observably equivalent).
 * Per ADR-0027 §"Test target": this is the *preserved-surface* case --
 * the collection behaviour is being preserved, not redesigned, so the
 * test pins the existing contract (unlike the RED tests for the net-new
 * utility kit).
 *
 * Distinct from ``vtkSlicerVascularTerritoriesLogicTest1`` (which pins
 * the algorithm surface) -- this file pins ONLY the scene-organisation
 * behaviour from ADR-0023 §"MRML scene organisation".
 *
 * GREEN-NOW: unlike the RED scaffolds for the new kit, this test passes
 * against the current ``vtkSlicerVascularTerritoriesLogic`` because it
 * characterises code that already exists.
 *
 * Current behaviour pinned (matches the inline collector at
 * vtkSlicerVascularTerritoriesLogic.cxx OnMRMLSceneNodeAdded):
 *
 *   1. A ``vtkMRMLAbstractTerritoriesNode`` added to the logic's observed
 *      scene is re-parented under a Subject-Hierarchy folder named
 *      "Vascular Territories" that is a DIRECT CHILD of the scene root
 *      (scene-root-scoped lookup -- a same-named folder nested elsewhere
 *      is NOT reused).
 *   2. The folder is lazily created on the first territories node and
 *      REUSED for the second (exactly one scene-root folder; both nodes
 *      hang off it).
 *   3. The ``GetItemByDataNode`` auto-create branch: a freshly-added node
 *      whose SH item does not yet exist (or resolves to the scene item)
 *      is given an item under the folder rather than left unparented.
 *
 * The same three facts are what
 * ``vtkSlicerSubjectHierarchyFolders::CollectUnderFolder`` must reproduce
 * once the rewrite lands -- so this characterization is the equivalence
 * oracle for the rewrite (the post-rewrite implementer re-runs it green).
 */

// VascularTerritories Logic + MRML includes
#include "vtkMRMLStdCouinaudTerritoriesNode.h"
#include "vtkSlicerVascularTerritoriesLogic.h"

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

const char* const kFolderName = "Vascular Territories";

//------------------------------------------------------------------------------
int countSceneRootFoldersNamed(vtkMRMLSubjectHierarchyNode* shNode, const char* name)
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
// Invariant 1 + 3 -- a single territories node lands under a scene-root
// "Vascular Territories" folder via the logic's NodeAdded observer.
int testSingleTerritoryNodeCollectedUnderFolder()
{
  vtkNew<vtkSlicerVascularTerritoriesLogic> logic;
  vtkNew<vtkMRMLScene> scene;
  // SetMRMLScene runs RegisterNodes (registers the territories classes)
  // and SetMRMLSceneInternal (observes NodeAddedEvent), the two
  // preconditions for the inline collector to fire.
  logic->SetMRMLScene(scene.GetPointer());

  vtkNew<vtkMRMLStdCouinaudTerritoriesNode> territories;
  scene->AddNode(territories.GetPointer());

  vtkMRMLSubjectHierarchyNode* shNode = vtkMRMLSubjectHierarchyNode::GetSubjectHierarchyNode(scene.GetPointer());
  CHECK_NOT_NULL(shNode);

  CHECK_INT(countSceneRootFoldersNamed(shNode, kFolderName), 1);

  vtkIdType nodeItem = shNode->GetItemByDataNode(territories.GetPointer());
  CHECK_BOOL(nodeItem != vtkMRMLSubjectHierarchyNode::INVALID_ITEM_ID, true);
  vtkIdType parentItem = shNode->GetItemParent(nodeItem);
  CHECK_STD_STRING(shNode->GetItemName(parentItem), std::string(kFolderName));
  // Folder is a direct child of the scene root (scene-root-scoped lookup).
  CHECK_BOOL(shNode->GetItemParent(parentItem) == shNode->GetSceneItemID(), true);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 2 -- the folder is lazily created then REUSED: two territories
// nodes share exactly one scene-root folder.
int testFolderReusedAcrossTwoNodes()
{
  vtkNew<vtkSlicerVascularTerritoriesLogic> logic;
  vtkNew<vtkMRMLScene> scene;
  logic->SetMRMLScene(scene.GetPointer());

  vtkNew<vtkMRMLStdCouinaudTerritoriesNode> first;
  vtkNew<vtkMRMLStdCouinaudTerritoriesNode> second;
  scene->AddNode(first.GetPointer());
  scene->AddNode(second.GetPointer());

  vtkMRMLSubjectHierarchyNode* shNode = vtkMRMLSubjectHierarchyNode::GetSubjectHierarchyNode(scene.GetPointer());
  CHECK_NOT_NULL(shNode);

  // The reuse invariant: ONE folder, not two.
  CHECK_INT(countSceneRootFoldersNamed(shNode, kFolderName), 1);

  vtkIdType firstParent = shNode->GetItemParent(shNode->GetItemByDataNode(first.GetPointer()));
  vtkIdType secondParent = shNode->GetItemParent(shNode->GetItemByDataNode(second.GetPointer()));
  CHECK_BOOL(firstParent == secondParent, true);
  CHECK_STD_STRING(shNode->GetItemName(firstParent), std::string(kFolderName));
  return EXIT_SUCCESS;
}

} // namespace

//------------------------------------------------------------------------------
int vtkSlicerVascularTerritoriesLogicSubjectHierarchyCharacterizationTest(int, char*[])
{
  CHECK_EXIT_SUCCESS(testSingleTerritoryNodeCollectedUnderFolder());
  CHECK_EXIT_SUCCESS(testFolderReusedAcrossTwoNodes());

  std::cout << "vtkSlicerVascularTerritoriesLogicSubjectHierarchyCharacterizationTest "
               "completed successfully"
            << std::endl;
  return EXIT_SUCCESS;
}

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

#include "vtkSlicerSubjectHierarchyFolders.h"

// MRML includes
#include <vtkMRMLNode.h>
#include <vtkMRMLScene.h>
#include <vtkMRMLSubjectHierarchyNode.h>

// VTK includes
#include <vtkObjectFactory.h>

// STD includes
#include <vector>

//------------------------------------------------------------------------------
vtkStandardNewMacro(vtkSlicerSubjectHierarchyFolders);

//------------------------------------------------------------------------------
vtkSlicerSubjectHierarchyFolders::vtkSlicerSubjectHierarchyFolders() = default;

//------------------------------------------------------------------------------
vtkSlicerSubjectHierarchyFolders::~vtkSlicerSubjectHierarchyFolders() = default;

//------------------------------------------------------------------------------
void vtkSlicerSubjectHierarchyFolders::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);
}

//------------------------------------------------------------------------------
const char* vtkSlicerSubjectHierarchyFolders::GetAnatomyFolderName()
{
  return "Anatomy";
}

//------------------------------------------------------------------------------
const char* vtkSlicerSubjectHierarchyFolders::GetVascularTerritoriesFolderName()
{
  return "Vascular Territories";
}

//------------------------------------------------------------------------------
const char* vtkSlicerSubjectHierarchyFolders::GetResectionsFolderName()
{
  return "Resections";
}

//------------------------------------------------------------------------------
const char* vtkSlicerSubjectHierarchyFolders::GetVolumetryFolderName()
{
  return "Volumetry";
}

//------------------------------------------------------------------------------
bool vtkSlicerSubjectHierarchyFolders::CollectUnderFolder(vtkMRMLScene* scene, vtkMRMLNode* node, const char* folderName)
{
  if (!scene || !node || !folderName)
  {
    return false;
  }

  // Headless-safe: resolve the Subject-Hierarchy node without forcing the
  // caller's intent to mint SH machinery behind its back.  When no SH node
  // is resolvable (a missing SH plugin in a headless context) this is a
  // no-op returning false, so node creation upstream is never broken
  // (ADR-0023 §"Subject Hierarchy management convention").
  vtkMRMLSubjectHierarchyNode* shNode = vtkMRMLSubjectHierarchyNode::GetSubjectHierarchyNode(scene);
  if (!shNode)
  {
    return false;
  }

  // ADR-0023 §"Subject Hierarchy management convention": the per-stage
  // folder is created lazily on first arrival and reused thereafter.
  // Scope the lookup to *children of the scene root* so a same-named
  // folder anywhere else in the hierarchy (e.g. inside a
  // Patient/Study/Series subtree) is not silently reused.
  vtkIdType sceneItem = shNode->GetSceneItemID();
  vtkIdType folderItem = vtkMRMLSubjectHierarchyNode::INVALID_ITEM_ID;
  std::vector<vtkIdType> children;
  shNode->GetItemChildren(sceneItem, children);
  for (vtkIdType child : children)
  {
    if (shNode->GetItemName(child) == folderName)
    {
      folderItem = child;
      break;
    }
  }
  if (folderItem == vtkMRMLSubjectHierarchyNode::INVALID_ITEM_ID)
  {
    folderItem = shNode->CreateFolderItem(sceneItem, folderName);
  }

  vtkIdType nodeItem = shNode->GetItemByDataNode(node);
  if (nodeItem == vtkMRMLSubjectHierarchyNode::INVALID_ITEM_ID || nodeItem == 0)
  {
    // SH auto-creates an item the first time GetItemByDataNode is called
    // for a newly-added node; if it has not yet, force it via CreateItem
    // so the re-parenting below has a target.
    shNode->CreateItem(folderItem, node);
  }
  else
  {
    shNode->SetItemParent(nodeItem, folderItem);
  }
  return true;
}

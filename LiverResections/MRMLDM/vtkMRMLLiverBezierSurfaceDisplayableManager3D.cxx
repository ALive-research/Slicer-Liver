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

  This file was originally developed for the Slicer-Liver extension
  as part of the T2 LiverResections all-in migration (Stack 2 of the
  v2.0.0 release tracker — see ADR-0014 §3).

==============================================================================*/

#include "vtkMRMLLiverBezierSurfaceDisplayableManager3D.h"

// LiverResections includes
#include "vtkLiverBezierRepresentation.h"
#include "vtkLiverBezierWidget.h"
#include "vtkMRMLBezierSurfaceNode.h"

// MRML includes
#include <vtkMRMLScene.h>

// VTK includes
#include <vtkNew.h>
#include <vtkObjectFactory.h>
#include <vtkRenderWindowInteractor.h>
#include <vtkRenderer.h>

//-----------------------------------------------------------------------------
vtkStandardNewMacro(vtkMRMLLiverBezierSurfaceDisplayableManager3D);

//-----------------------------------------------------------------------------
vtkMRMLLiverBezierSurfaceDisplayableManager3D::vtkMRMLLiverBezierSurfaceDisplayableManager3D() = default;

//-----------------------------------------------------------------------------
vtkMRMLLiverBezierSurfaceDisplayableManager3D::~vtkMRMLLiverBezierSurfaceDisplayableManager3D()
{
  this->RemoveAllWidgets();
}

//-----------------------------------------------------------------------------
void vtkMRMLLiverBezierSurfaceDisplayableManager3D::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);
  os << indent << "NumberOfWidgets: " << this->Widgets.size() << "\n";
}

//-----------------------------------------------------------------------------
vtkLiverBezierWidget* vtkMRMLLiverBezierSurfaceDisplayableManager3D::GetWidget(vtkMRMLBezierSurfaceNode* node)
{
  if (!node || !node->GetID())
  {
    return nullptr;
  }
  const auto it = this->Widgets.find(node->GetID());
  if (it == this->Widgets.end())
  {
    return nullptr;
  }
  return it->second.GetPointer();
}

//-----------------------------------------------------------------------------
void vtkMRMLLiverBezierSurfaceDisplayableManager3D::SetMRMLSceneInternal(vtkMRMLScene* newScene)
{
  // Tear every widget down before swapping the scene observer chain.
  // The superclass handles the Modified-event observation; the
  // node-level observation runs through OnMRMLSceneNodeAdded /
  // OnMRMLSceneNodeRemoved already provided by the base class via
  // vtkMRMLAbstractLogic.
  this->RemoveAllWidgets();
  this->Superclass::SetMRMLSceneInternal(newScene);

  // Late-attach reconcile: if the DM is wired into a view AFTER the
  // scene is already populated (e.g., second-view attach, late module
  // load), the existing vtkMRMLBezierSurfaceNode instances will not
  // re-fire NodeAddedEvent and OnMRMLSceneEndImport / EndClose will
  // not fire either.  Walk the new scene and create widgets for any
  // pre-existing Bezier surface nodes.  Same loop as
  // OnMRMLSceneEndImport.
  if (!newScene)
  {
    return;
  }
  std::vector<vtkMRMLNode*> existingNodes;
  newScene->GetNodesByClass("vtkMRMLBezierSurfaceNode", existingNodes);
  for (vtkMRMLNode* node : existingNodes)
  {
    if (vtkMRMLBezierSurfaceNode* bezierNode = vtkMRMLBezierSurfaceNode::SafeDownCast(node))
    {
      this->AddBezierSurfaceNode(bezierNode);
    }
  }
}

//-----------------------------------------------------------------------------
void vtkMRMLLiverBezierSurfaceDisplayableManager3D::OnMRMLSceneNodeAdded(vtkMRMLNode* node)
{
  this->Superclass::OnMRMLSceneNodeAdded(node);

  // Match the established Slicer-core DM pattern: during batch
  // processing (scene import / restore) skip per-node widget
  // construction and let OnMRMLSceneEndImport do a single reconcile
  // pass.  Without this guard each imported node creates a widget
  // that EndImport then tears down and re-creates — functionally
  // correct due to ``AddBezierSurfaceNode`` idempotency, but wasteful.
  // Cf. vtkMRMLCameraDisplayableManager, vtkMRMLModelSliceDisplayable
  // Manager, vtkMRMLThreeDReformatDisplayableManager — all guard
  // OnMRMLSceneNodeAdded with this exact check.
  vtkMRMLScene* scene = this->GetMRMLScene();
  if (scene && scene->IsBatchProcessing())
  {
    return;
  }

  vtkMRMLBezierSurfaceNode* bezierNode = vtkMRMLBezierSurfaceNode::SafeDownCast(node);
  if (!bezierNode)
  {
    return;
  }
  this->AddBezierSurfaceNode(bezierNode);
}

//-----------------------------------------------------------------------------
void vtkMRMLLiverBezierSurfaceDisplayableManager3D::OnMRMLSceneNodeRemoved(vtkMRMLNode* node)
{
  vtkMRMLBezierSurfaceNode* bezierNode = vtkMRMLBezierSurfaceNode::SafeDownCast(node);
  if (bezierNode)
  {
    this->RemoveBezierSurfaceNode(bezierNode);
  }
  this->Superclass::OnMRMLSceneNodeRemoved(node);
}

//-----------------------------------------------------------------------------
void vtkMRMLLiverBezierSurfaceDisplayableManager3D::OnMRMLSceneEndImport()
{
  // After scene import, the registry may be stale (nodes loaded from
  // disk did not pass through OnMRMLSceneNodeAdded in BatchProcessing
  // mode for some scene swaps).  Walk the scene and reconcile.
  this->RemoveAllWidgets();
  vtkMRMLScene* scene = this->GetMRMLScene();
  if (!scene)
  {
    return;
  }
  std::vector<vtkMRMLNode*> nodes;
  scene->GetNodesByClass("vtkMRMLBezierSurfaceNode", nodes);
  for (vtkMRMLNode* node : nodes)
  {
    if (vtkMRMLBezierSurfaceNode* bezierNode = vtkMRMLBezierSurfaceNode::SafeDownCast(node))
    {
      this->AddBezierSurfaceNode(bezierNode);
    }
  }
}

//-----------------------------------------------------------------------------
void vtkMRMLLiverBezierSurfaceDisplayableManager3D::OnMRMLSceneEndClose()
{
  this->RemoveAllWidgets();
}

//-----------------------------------------------------------------------------
bool vtkMRMLLiverBezierSurfaceDisplayableManager3D::AddBezierSurfaceNode(vtkMRMLBezierSurfaceNode* node)
{
  if (!node || !node->GetID())
  {
    return false;
  }
  const std::string key(node->GetID());

  // Idempotency: drop any existing widget for this ID first.  Common
  // during EndImport reconcile.
  const auto existing = this->Widgets.find(key);
  if (existing != this->Widgets.end())
  {
    if (existing->second)
    {
      existing->second->SetEnabled(0);
      existing->second->SetRepresentation(nullptr);
      existing->second->SetBezierNode(nullptr);
    }
    this->Widgets.erase(existing);
  }

  vtkRenderer* renderer = this->GetRenderer();
  vtkRenderWindowInteractor* interactor = this->GetInteractor();

  vtkNew<vtkLiverBezierWidget> widget;
  vtkNew<vtkLiverBezierRepresentation> rep;
  if (renderer)
  {
    rep->SetRenderer(renderer);
  }
  widget->SetRepresentation(rep);
  widget->SetBezierNode(node);
  if (interactor)
  {
    widget->SetInteractor(interactor);
    widget->SetEnabled(1);
  }

  this->Widgets[key] = widget;
  return true;
}

//-----------------------------------------------------------------------------
void vtkMRMLLiverBezierSurfaceDisplayableManager3D::RemoveBezierSurfaceNode(vtkMRMLBezierSurfaceNode* node)
{
  if (!node || !node->GetID())
  {
    return;
  }
  const auto it = this->Widgets.find(node->GetID());
  if (it == this->Widgets.end())
  {
    return;
  }
  if (it->second)
  {
    it->second->SetEnabled(0);
    it->second->SetRepresentation(nullptr);
    it->second->SetBezierNode(nullptr);
  }
  this->Widgets.erase(it);
}

//-----------------------------------------------------------------------------
void vtkMRMLLiverBezierSurfaceDisplayableManager3D::RemoveAllWidgets()
{
  for (auto& entry : this->Widgets)
  {
    if (entry.second)
    {
      entry.second->SetEnabled(0);
      entry.second->SetRepresentation(nullptr);
      entry.second->SetBezierNode(nullptr);
    }
  }
  this->Widgets.clear();
}

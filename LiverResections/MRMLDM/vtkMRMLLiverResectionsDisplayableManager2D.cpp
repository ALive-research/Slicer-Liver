/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) Oslo University Hospital. All rights reserved.

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
  Hospital and NTNU) and Ruoyan Meng (NTNU), and was supported by The
  Research Council of Norway through the ALive project (grant nr. 311393).

  ==============================================================================*/


#include "vtkMRMLLiverResectionsDisplayableManager2D.h"
#include "vtkMRMLAbstractSliceViewDisplayableManager.h"

// Module includes
#include "vtkMRMLLiverResectionsDisplayableManagerHelper2D.h"
#include <vtkMRMLLiverResectionNode.h>
#include <vtkMRMLMarkupsBezierSurfaceNode.h>
#include <vtkMRMLMarkupsBezierSurfaceDisplayNode.h>

// MRML includes
#include <vtkMRMLScene.h>
#include <vtkMRMLAbstractLogic.h>
#include <vtkMRMLSliceNode.h>

// VTK includes
#include <vtkRenderer.h>
#include <vtkObjectFactory.h>
#include <vtkNew.h>
#include <vtkCallbackCommand.h>
#include <vtkEventBroker.h>

//-------------------------------------------------------------------------------
vtkStandardNewMacro(vtkMRMLLiverResectionsDisplayableManager2D);

//-------------------------------------------------------------------------------
vtkMRMLLiverResectionsDisplayableManager2D::
vtkMRMLLiverResectionsDisplayableManager2D() {
}

//-------------------------------------------------------------------------------
vtkMRMLLiverResectionsDisplayableManager2D::
~vtkMRMLLiverResectionsDisplayableManager2D() {

}

//-------------------------------------------------------------------------------
void vtkMRMLLiverResectionsDisplayableManager2D::PrintSelf(ostream &os,
                                                           vtkIndent indent) {
  this->Superclass::PrintSelf(os, indent);
}

//-------------------------------------------------------------------------------
void vtkMRMLLiverResectionsDisplayableManager2D::
ProcessMRMLNodesEvents(vtkObject *caller,
                       unsigned long event,
                       void *callData) {

  auto BezierSurfaceNode = vtkMRMLMarkupsBezierSurfaceNode::SafeDownCast(caller);

  if (BezierSurfaceNode)
    {
    if (BezierSurfaceNode->GetNumberOfControlPoints() != 16)
      {
//      vtkErrorMacro("BezierSurfaceNode not ready");
      return;
      }

    auto BezierSurfaceNodeIDC = BezierSurfaceNode->GetID();

    if (event == vtkMRMLMarkupsBezierSurfaceNode::PointModifiedEvent)
      {
      if (BezierSurfaceNode->GetDisplayVisibility())
        {
        auto helper = this->ResectionNodeHelperMap[BezierSurfaceNodeIDC];
        helper->UpdateSurfaceContour(BezierSurfaceNode);
        }
      }

    if (event == vtkCommand::ModifiedEvent)
      {
      if (BezierSurfaceNode->GetDisplayVisibility())
        {
        this->OnMRMLNodeModified(BezierSurfaceNode);
        }
      }
    } else
    {
    Superclass::ProcessMRMLNodesEvents(caller, event, callData);
    }
//
  this->RequestRender();
}

//-------------------------------------------------------------------------------
void vtkMRMLLiverResectionsDisplayableManager2D::
SetMRMLSceneInternal(vtkMRMLScene *newScene) {

  this->OnMRMLSceneEndClose();

  Superclass::SetMRMLSceneInternal(newScene);

  if (newScene)
    {
    auto deferredNodesCallbackCommand = vtkSmartPointer<vtkCallbackCommand>::New();
    deferredNodesCallbackCommand->SetCallback(this->AddDeferredNodes);
    deferredNodesCallbackCommand->SetClientData(this);

    vtkEventBroker *eventBroker = vtkEventBroker::GetInstance();
    eventBroker->AddObservation(this->GetMRMLScene(),
                                vtkMRMLScene::EndBatchProcessEvent,
                                this,
                                deferredNodesCallbackCommand);
    }
}

//-------------------------------------------------------------------------------
void vtkMRMLLiverResectionsDisplayableManager2D::
OnMRMLNodeModified(vtkMRMLNode *node) {
  if (!node)
    {
    vtkErrorMacro("OnMRMLNodeModified: no node set");
    return;
    }

  auto BezierSurfaceNode = vtkMRMLMarkupsBezierSurfaceNode::SafeDownCast(node);
  if (!BezierSurfaceNode)
    {
//    vtkErrorMacro("Could not get BezierSurfaceNode");
    return;
    }
  auto BezierSurfaceNodeIDC = BezierSurfaceNode->GetID();
  auto helper = this->ResectionNodeHelperMap[BezierSurfaceNodeIDC];
  helper->ChangeSurfaceVisibility(BezierSurfaceNode, this->GetRenderer());

  this->RequestRender();
}

//-------------------------------------------------------------------------------
void vtkMRMLLiverResectionsDisplayableManager2D::
OnMRMLSceneNodeAdded(vtkMRMLNode *node) {
  // If no node or no scene, then return
  if (!node || !this->GetMRMLScene())
    {
    return;
    }
  auto sliceNode = this->GetMRMLSliceNode();
  // Check whether the node is a resection node
  auto BezierSurfaceNode = vtkMRMLMarkupsBezierSurfaceNode::SafeDownCast(node);
  if (!BezierSurfaceNode)
    {
//    vtkErrorMacro("Could not get BezierSurfaceNode");
    return;
    }

  std::cout << "Trying to add node to dm 2D:"
            << BezierSurfaceNode->GetName()
            << std::endl;

  // Setup the event listening mechanism
  auto events = vtkSmartPointer<vtkIntArray>::New();
  events->InsertNextValue(vtkCommand::ModifiedEvent);
  events->InsertNextValue(vtkMRMLMarkupsBezierSurfaceNode::PointModifiedEvent);
  events->InsertNextValue(vtkMRMLMarkupsBezierSurfaceNode::PointPositionDefinedEvent);
  vtkUnObserveMRMLNodeMacro(BezierSurfaceNode);
  vtkObserveMRMLNodeEventsMacro(BezierSurfaceNode, events.GetPointer());

  auto BezierSurfaceNodeIDC = BezierSurfaceNode->GetID();
  auto helper = vtkSmartPointer<vtkMRMLLiverResectionsDisplayableManagerHelper2D>::New();
  this->ResectionNodeHelperMap[BezierSurfaceNodeIDC] = helper;
  helper->DisplaySurfaceContour(BezierSurfaceNode, sliceNode, this->GetRenderer());

  //if the scene is still updating, jump out
  if (this->GetMRMLScene()->IsBatchProcessing())
    {
    this->DeferredNodes->AddItem(BezierSurfaceNode);
    return;
    }

  this->RequestRender();
}

//-------------------------------------------------------------------------------
void vtkMRMLLiverResectionsDisplayableManager2D::
OnMRMLSceneNodeRemoved(vtkMRMLNode *node) {
  // Check whether the node is a resection node
  auto BezierSurfaceNode = vtkMRMLMarkupsBezierSurfaceNode::SafeDownCast(node);

  if (!BezierSurfaceNode)
    {
//    vtkErrorMacro("Could not get BezierSurfaceNode");
    return;
    }
  auto BezierSurfaceNodeIDC = BezierSurfaceNode->GetID();
  if (this->ResectionNodeHelperMap.find(BezierSurfaceNodeIDC) == this->ResectionNodeHelperMap.end())
    {
    return;
    }

  auto helper = this->ResectionNodeHelperMap[BezierSurfaceNodeIDC];

  helper->RemoveSurfaceContour(BezierSurfaceNode, this->GetRenderer());

  this->ResectionNodeHelperMap.erase(BezierSurfaceNodeIDC);

  this->Superclass::OnMRMLSceneNodeRemoved(node);

  this->RequestRender();
}

//-------------------------------------------------------------------------------
void vtkMRMLLiverResectionsDisplayableManager2D::OnMRMLSceneEndClose() {

}

//-------------------------------------------------------------------------------
void vtkMRMLLiverResectionsDisplayableManager2D::
AddDeferredNodes(vtkObject * vtkNotUsed(caller),
                 unsigned long vtkNotUsed(event),
                 void *clientData,
                 void * vtkNotUsed(callData)) {
  auto self = static_cast<vtkMRMLLiverResectionsDisplayableManager2D *>(clientData);

  auto sliceNode = self->GetMRMLSliceNode();

  for (int i = 0; i < self->DeferredNodes->GetNumberOfItems(); i++)
    {
    vtkObject *object = self->DeferredNodes->GetItemAsObject(i);
    auto BezierSurfaceNode = vtkMRMLMarkupsBezierSurfaceNode::SafeDownCast(object);

    if (!BezierSurfaceNode)
      {
      return;
      }

    auto BezierSurfaceNodeIDC = BezierSurfaceNode->GetID();
    auto helper = vtkSmartPointer<vtkMRMLLiverResectionsDisplayableManagerHelper2D>::New();

    self->ResectionNodeHelperMap[BezierSurfaceNodeIDC] = helper;

    helper->DisplaySurfaceContour(BezierSurfaceNode, sliceNode, self->GetRenderer());

    self->RequestRender();
    }

  self->DeferredNodes->RemoveAllItems();
}
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

  * Neither the name of Oslo University Hospital nor the names of Contributors
    may be used to endorse or promote products derived from this
    software without specific prior written permission.

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

// NOTE: Some of the functions of this file are inspired in vtkSlicerMarkupsLogic

#include "vtkSlicerLiverResectionsLogic.h"
#include "vtkMRMLAbstractLogic.h"

// SubjectHierarchyFolders utility (ADR-0023 §"Subject Hierarchy
// management convention").
#include "vtkSlicerSubjectHierarchyFolders.h"

// T2 LiverResources data nodes (ADR-0014 §1, §5).  Registered with the
// scene in RegisterNodes() so scene save/load and the Add/Save Data
// dialogs round-trip the new ``vtkMRMLBezierSurfaceNode`` family and
// recognise the new ``.lrp.json`` storage format.
#include "vtkMRMLBezierSurfaceNode.h"
#include "vtkMRMLParametricSurfaceDisplayNode.h"
#include "vtkMRMLResectionPlanNode.h"
#include "vtkMRMLResectionPlanStorageNode.h"

#include <vtkCommand.h>
#include <vtkMRMLMarkupsBezierSurfaceNode.h>

// MRML includes
#include <vtkMRMLScene.h>
#include <vtkMRMLSelectionNode.h>
#include <vtkMRMLSegmentationNode.h>

// VTK includes
#include <vtkObjectFactory.h>
#include <vtkCollection.h>
#include <vtkSetGet.h>
#include <vtkSmartPointer.h>
#include <vtkIntArray.h>
#include <vtkImageData.h>

#include <vtkMRMLGlyphableVolumeDisplayNode.h>
#include <itkLabelImageToLabelMapFilter.h>

//----------------------------------------------------------------------------
vtkStandardNewMacro(vtkSlicerLiverResectionsLogic);

//---------------------------------------------------------------------------
vtkSlicerLiverResectionsLogic::vtkSlicerLiverResectionsLogic()
{
  // auto node = vtkSmartPointer<vtkMRMLGlyphableVolumeDisplayNode>::New();
}

//---------------------------------------------------------------------------
vtkSlicerLiverResectionsLogic::~vtkSlicerLiverResectionsLogic() = default;

//---------------------------------------------------------------------------
void vtkSlicerLiverResectionsLogic::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);
}

//---------------------------------------------------------------------------
bool vtkSlicerLiverResectionsLogic::IsStageComplete()
{
  // Stage-4 completion predicate per ADR-0023 §"Shell composition
  // (Option H)" + ADR-0019 (Resection state machine): the stage is
  // done iff at least one ``vtkMRMLResectionPlanNode`` in the scene
  // reports ``State == Confirmed``.  Init / Planning keep the stage
  // 'current' (not 'done') — surgeons must reach the locked-plan
  // gate before Volumetry / Export light up.
  vtkMRMLScene* scene = this->GetMRMLScene();
  if (!scene)
  {
    return false;
  }
  vtkSmartPointer<vtkCollection> plans = vtkSmartPointer<vtkCollection>::Take(scene->GetNodesByClass("vtkMRMLResectionPlanNode"));
  if (!plans)
  {
    return false;
  }
  for (int i = 0; i < plans->GetNumberOfItems(); ++i)
  {
    auto* plan = vtkMRMLResectionPlanNode::SafeDownCast(plans->GetItemAsObject(i));
    if (plan && plan->GetState() == vtkMRMLResectionPlanNode::Confirmed)
    {
      return true;
    }
  }
  return false;
}

//---------------------------------------------------------------------------
void vtkSlicerLiverResectionsLogic::RegisterNodes()
{
  assert(this->GetMRMLScene() != nullptr);
  vtkMRMLScene* scene = this->GetMRMLScene();

  // T2 LiverResources data nodes (ADR-0014 §1, §5).  The Bezier data
  // node + the shared parametric-surface display node are registered
  // so MRML can instantiate them by class name on scene load.  The
  // surface is non-storable per the wrapper-vs-carrier pattern;
  // persistence flows through the plan storage node below.
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLBezierSurfaceNode>::New());
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLParametricSurfaceDisplayNode>::New());

  // Resection-plan family (2026-05-25 wrapper-vs-carrier amendment to
  // ADR-0014 §"Fourth layer" + ADR-0023 §"Persistence").  The plan
  // node is the clinical wrapper; the storage node is the rooted
  // .lrp.json persistence target.
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanNode>::New());
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanStorageNode>::New());
}

//---------------------------------------------------------------------------
void vtkSlicerLiverResectionsLogic::SetMRMLSceneInternal(vtkMRMLScene* newScene)
{
  vtkNew<vtkIntArray> events;
  events->InsertNextValue(vtkMRMLScene::NodeAddedEvent);
  events->InsertNextValue(vtkMRMLScene::NodeRemovedEvent);
  events->InsertNextValue(vtkMRMLScene::EndBatchProcessEvent);
  this->SetAndObserveMRMLSceneEventsInternal(newScene, events.GetPointer());
}

//---------------------------------------------------------------------------
void vtkSlicerLiverResectionsLogic::ObserveMRMLScene()
{
  this->Superclass::ObserveMRMLScene();
}

//---------------------------------------------------------------------------
void vtkSlicerLiverResectionsLogic::ProcessMRMLNodesEvents(vtkObject* caller, unsigned long event, void* vtkNotUsed(callData))
{
  // Process the surface carrier interaction (ADR-0019 state machine).
  // The data carrier vtkMRMLBezierSurfaceNode owns the resection-state
  // machine (ADR-0014 §1 wrapper-vs-carrier split).  The first
  // interaction advances the carrier Init -> Planning -- the v2
  // replacement for the legacy "Deformation" push that used to land on
  // vtkMRMLLiverResectionNode.  SetState already enforces the
  // irreversible Init -> Planning transition (ADR-0019), so a repeat
  // interaction is a no-op rather than a regression.
  //
  // NOTE: at runtime the Init -> Planning transition is driven by the
  // LayerDM Pipeline commit seam (LiverBezierSurfacePipeline.commit()),
  // NOT by an observer delivering StartInteractionEvent to this arm --
  // the per-node interaction observation was wired inside the retired
  // legacy resection family and went with it.  This arm is the
  // test-pinned C++ mirror of that transition
  // (vtkSlicerLiverResectionsLogicCarrierStateAdvanceTest invokes
  // ProcessMRMLNodesEvents directly).  Do not delete it as dead code,
  // and do not re-add a per-node observer assuming it is the sole
  // runtime driver -- the Pipeline commit seam owns that.
  auto surfaceCarrier = vtkMRMLBezierSurfaceNode::SafeDownCast(caller);
  if (surfaceCarrier && event == vtkCommand::StartInteractionEvent)
  {
    if (surfaceCarrier->GetState() == vtkMRMLBezierSurfaceNode::Init)
    {
      surfaceCarrier->SetState(vtkMRMLBezierSurfaceNode::Planning);
    }
  }
}

//---------------------------------------------------------------------------
void vtkSlicerLiverResectionsLogic::OnMRMLSceneNodeAdded(vtkMRMLNode* node)
{
  Superclass::OnMRMLSceneNodeAdded(node);

  // ADR-0023 §"Subject Hierarchy management convention": collect the
  // surgeon-facing wrapper vtkMRMLResectionPlanNode (the node production
  // creates per ADR-0014's wrapper-vs-carrier split) under the per-stage
  // "Resections" Subject Hierarchy folder (lazily created, reused).  Only
  // the wrapper is collected; the hidden SetHideFromEditors(true)
  // Bezier/contour carriers are deliberately left unparented.
  if (auto resectionPlanNode = vtkMRMLResectionPlanNode::SafeDownCast(node))
  {
    vtkSlicerSubjectHierarchyFolders::CollectUnderFolder(this->GetMRMLScene(), resectionPlanNode, vtkSlicerSubjectHierarchyFolders::GetResectionsFolderName());
  }
}

//---------------------------------------------------------------------------
void vtkSlicerLiverResectionsLogic::OnMRMLSceneNodeRemoved(vtkMRMLNode* node)
{
  Superclass::OnMRMLSceneNodeRemoved(node);
}

//------------------------------------------------------------------------------
char* vtkSlicerLiverResectionsLogic::LoadLiverResection(const std::string& fileName, const std::string& nodeName /*=nullptr*/, vtkMRMLMessageCollection* userMessages /*=nullptr*/)
{
  if (fileName == "")
  {
    vtkErrorMacro("vtkSlicerLiverResectionsLogic::LoadResections failed: invalid fileName");
    return nullptr;
  }

  // get file extension
  std::string extension = vtkMRMLStorageNode::GetLowercaseExtensionFromFileName(fileName);
  if (extension.empty())
  {
    vtkErrorMacro("vtkSlicerLiverResectionsLogic::LoadResections failed: no file extension specified: " << fileName);
    return nullptr;
  }

  // The legacy ``.fcsv`` resection load path retired with
  // vtkMRMLLiverResectionNode (T2.7 resection-rename + LiverMarkups
  // dissolution, ADR-0014).  Migration of pre-T2 ``.fcsv`` scenes is
  // covered by vtkMRMLResectionPlanLegacyFcsvMigrationTest.
  vtkErrorMacro("vtkSlicerLiverResectionsLogic::LoadResections failed: unrecognized file extension in " << fileName);
  return nullptr;
}

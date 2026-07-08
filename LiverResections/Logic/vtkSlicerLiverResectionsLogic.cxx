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
#include "vtkMRMLResectogramDisplayNode.h"
#include "vtkMRMLResectionPlanNode.h"
#include "vtkMRMLResectionPlanStorageNode.h"
#include "vtkMRMLLocatorNode.h"
#include "vtkMRMLLocatorDisplayNode.h"

#include <vtkCommand.h>

// MRML includes
#include <vtkMRMLScene.h>
#include <vtkMRMLScalarVolumeNode.h>
#include <vtkMRMLSelectionNode.h>
#include <vtkMRMLSegmentationNode.h>

#include <string>
#include <vector>

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
vtkMRMLResectionPlanNode* vtkSlicerLiverResectionsLogic::CreateResectionPlan(const char* name)
{
  // Mint the v2 carrier + plan + display triad the interactive workflow
  // needs (ADR-0032; ADR-0014 §"Fourth layer"), mirroring the file loaders'
  // resolve-or-create discipline (vtkMRMLResectionPlanStorageNode::ReadFcsv).
  vtkMRMLScene* scene = this->GetMRMLScene();
  if (scene == nullptr)
  {
    vtkErrorMacro("CreateResectionPlan: no MRML scene is bound");
    return nullptr;
  }

  auto* plan = vtkMRMLResectionPlanNode::SafeDownCast(scene->AddNewNodeByClass("vtkMRMLResectionPlanNode", (name ? name : "Resection")));
  auto* carrier = vtkMRMLBezierSurfaceNode::SafeDownCast(scene->AddNewNodeByClass("vtkMRMLBezierSurfaceNode"));
  if (plan == nullptr || carrier == nullptr)
  {
    vtkErrorMacro("CreateResectionPlan: failed to instantiate the resection node graph");
    return nullptr;
  }

  // The parametric-surface display node (which the LayerDM Pipeline creator
  // matches on, ADR-0013 §5) is minted + observed on the carrier here.
  carrier->CreateDefaultDisplayNodes();

  // Wire the wrapper to the carrier via the typed geometry reference; the
  // Pipeline reverse-resolves the plan from this back-reference (ADR-0031).
  plan->SetAndObserveGeometryNode(carrier);

  // Ensure the cross-view locator node exists so a resectogram click has a
  // node to write and the consumers (shader marker, click-to-reslice) have one
  // to read (ADR-0025 §Consumer: exactly one in v2.0).
  this->EnsureLocatorNode();

  // The Stage-2 canonical import computes a distance-map volume tagged
  // DistanceMap/Computed (the v1 selector contract).  Auto-attach it so
  // Planning opens with the plan's distance-map input ready (ADR-0031: the
  // map lives on the plan wrapper) -- no map in the scene leaves the
  // reference unset, exactly as before.  Untagged vector volumes are ignored.
  std::vector<vtkMRMLNode*> vectorVolumes;
  scene->GetNodesByClass("vtkMRMLVectorVolumeNode", vectorVolumes);
  for (vtkMRMLNode* candidate : vectorVolumes)
  {
    const char* isDistanceMap = candidate->GetAttribute("DistanceMap");
    const char* isComputed = candidate->GetAttribute("Computed");
    if (isDistanceMap && isComputed && std::string(isDistanceMap) == "True" && std::string(isComputed) == "True")
    {
      plan->SetAndObserveDistanceMapVolumeNode(vtkMRMLScalarVolumeNode::SafeDownCast(candidate));
      break;
    }
  }

  // The plan starts in Init (ADR-0019); the control grid is seeded by the
  // placement step, not here.
  return plan;
}

//---------------------------------------------------------------------------
vtkMRMLLocatorNode* vtkSlicerLiverResectionsLogic::EnsureLocatorNode()
{
  vtkMRMLScene* scene = this->GetMRMLScene();
  if (scene == nullptr)
  {
    vtkErrorMacro("EnsureLocatorNode: no MRML scene is bound");
    return nullptr;
  }

  // Resolve-or-create: reuse the single existing locator (ADR-0025 §Consumer:
  // v2.0 has exactly one) rather than minting a second.
  auto* locator = vtkMRMLLocatorNode::SafeDownCast(scene->GetFirstNodeByClass("vtkMRMLLocatorNode"));
  if (locator == nullptr)
  {
    locator = vtkMRMLLocatorNode::SafeDownCast(scene->AddNewNodeByClass("vtkMRMLLocatorNode"));
  }
  if (locator == nullptr)
  {
    vtkErrorMacro("EnsureLocatorNode: failed to instantiate the locator node");
    return nullptr;
  }

  // The display node carries the marker radius (default > 0) + feeds the
  // uLocatorRadius shader uniform; mark the locator active (persisted presence
  // flag, ADR-0025 §"The node").
  locator->CreateDefaultDisplayNodes();
  locator->SetLocatorActive(true);
  return locator;
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

  // T3 ResectogramPipeline display node (ADR-0013 §1 + §5).  The
  // resectogram is the flattened 2D image of the Bezier (u, v) domain
  // (ADR-0025 §Context); it gets its OWN display-node type so the
  // ResectogramPipeline can be keyed on it without sharing
  // vtkMRMLParametricSurfaceDisplayNode (which the 3D Bezier-surface
  // Pipeline owns) — one Pipeline per display-node type (ADR-0013 §1).
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectogramDisplayNode>::New());

  // Resection-plan family (2026-05-25 wrapper-vs-carrier amendment to
  // ADR-0014 §"Fourth layer" + ADR-0023 §"Persistence").  The plan
  // node is the clinical wrapper; the storage node is the rooted
  // .lrp.json persistence target.
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanNode>::New());
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanStorageNode>::New());

  // Locator family (ADR-0025 §"Registration").  The locator is a
  // C++ data-only carrier plus its display node.  Per ADR-0025 the
  // ONLY new wiring is RegisterNodeClass — no new Pipeline, no
  // displayable manager, no factory creator (ADR-0013 §5).
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLLocatorNode>::New());
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLLocatorDisplayNode>::New());
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

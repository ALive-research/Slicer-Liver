/*===============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2022-2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

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

  This file was originally developed by Ole V. Solberg, Geir A. Tangen, Javier
  Perez-de-Frutos (SINTEF, Norway) and Rafael Palomar (Oslo University
  Hospital) through the ALive project (grant nr. 311393).

  ===============================================================================*/

#include "vtkSlicerVascularTerritoriesLogic.h"

// VascularTerritories MRML includes
#include "vtkMRMLAbstractTerritoriesNode.h"
#include "vtkMRMLCustomTerritoriesNode.h"
#include "vtkMRMLStdCouinaudTerritoriesNode.h"

// SubjectHierarchyFolders utility
#include "vtkSlicerSubjectHierarchyFolders.h"

#include <vtkMRMLLabelMapVolumeNode.h>
#include <vtkMRMLSegmentationNode.h>
#include <vtkSegmentation.h>
#include <vtkSegment.h>
#include <vtkMRMLModelNode.h>
#include <vtkMRMLDisplayNode.h>

#include <vtkMRMLScene.h>
#include <vtkSlicerSegmentationsModuleLogic.h>

#include <vtkCollection.h>
#include <vtkObjectFactory.h>
#include <vtkSmartPointer.h>
#include <vtkImageData.h>
#include <vtkImageIterator.h>
#include <vtkKdTreePointLocator.h>
#include <vtkPointSet.h>
#include <vtkPolyData.h>
#include <vtkPointData.h>
#include <vtkStringArray.h>
#include <vtkAppendPolyData.h>
#include <vtkOrientedImageData.h>
#include <vtkMatrix4x4.h>
#include <vtkDecimatePro.h>
#include <vtkCleanPolyData.h>
#include <vtkTriangleFilter.h>
#include <vtkPolyDataNormals.h>
#include <vtkCellData.h>

#include <iostream>

//------------------------------------------------------------------------------
vtkStandardNewMacro(vtkSlicerVascularTerritoriesLogic);

//------------------------------------------------------------------------------
vtkSlicerVascularTerritoriesLogic::vtkSlicerVascularTerritoriesLogic()
{
  this->Locator = vtkSmartPointer<vtkKdTreePointLocator>::New();
}

//------------------------------------------------------------------------------
vtkSlicerVascularTerritoriesLogic::~vtkSlicerVascularTerritoriesLogic() {}

//------------------------------------------------------------------------------
void vtkSlicerVascularTerritoriesLogic::PrintSelf(ostream& os, vtkIndent indent)
{
  Superclass::PrintSelf(os, indent);
}

//------------------------------------------------------------------------------
void vtkSlicerVascularTerritoriesLogic::RegisterNodes()
{
  vtkMRMLScene* scene = this->GetMRMLScene();
  if (!scene)
  {
    vtkErrorMacro("RegisterNodes: no MRML scene attached to the logic.");
    return;
  }

  // ADR-0023 §"Class abstraction for territories" — only the concrete
  // is registered so ``GetNodesByClass("vtkMRMLAbstractTerritoriesNode")``
  // returns instances of both concrete subclasses (the polymorphic
  // node-class filter consumers rely on, per the architecture-doc
  // "Polymorphic interface" section).  The base ``New()`` returns
  // ``nullptr`` by design, but ``RegisterNodeClass`` accepts a
  // pre-constructed sentinel instance built via the concrete subclass.
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLStdCouinaudTerritoriesNode>::New());
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLCustomTerritoriesNode>::New());
}

//------------------------------------------------------------------------------
void vtkSlicerVascularTerritoriesLogic::SetMRMLSceneInternal(vtkMRMLScene* newScene)
{
  // ADR-0023 §"MRML scene organisation": territory nodes get
  // re-parented under the "Vascular Territories" Subject Hierarchy
  // folder in ``OnMRMLSceneNodeAdded`` below, which only fires if
  // the logic actually observes ``NodeAddedEvent``.  The default
  // ``vtkMRMLAbstractLogic::SetMRMLSceneInternal`` plumbs the scene
  // pointer through ``SetObject`` (no event observation), so the SH
  // placement never runs without this override.  Pattern mirrors
  // ``vtkSlicerLiverResectionsLogic::SetMRMLSceneInternal``.
  vtkNew<vtkIntArray> events;
  events->InsertNextValue(vtkMRMLScene::NodeAddedEvent);
  this->SetAndObserveMRMLSceneEventsInternal(newScene, events.GetPointer());
}

//------------------------------------------------------------------------------
void vtkSlicerVascularTerritoriesLogic::OnMRMLSceneNodeAdded(vtkMRMLNode* node)
{
  this->Superclass::OnMRMLSceneNodeAdded(node);

  auto territoryNode = vtkMRMLAbstractTerritoriesNode::SafeDownCast(node);
  if (!territoryNode)
  {
    return;
  }

  vtkMRMLScene* scene = this->GetMRMLScene();
  if (!scene)
  {
    return;
  }

  // ADR-0023 §"Subject Hierarchy management convention" — territory
  // nodes live under the "Vascular Territories" Subject Hierarchy
  // folder, created lazily on first arrival and reused thereafter.  The
  // lookup / lazy-create / scene-root-scoped reparent dance is
  // centralised in the shared vtkSlicerSubjectHierarchyFolders utility
  // so the four node-creating stages stay in lockstep on one
  // binary-identical implementation.
  vtkSlicerSubjectHierarchyFolders::CollectUnderFolder(scene, territoryNode, vtkSlicerSubjectHierarchyFolders::GetVascularTerritoriesFolderName());
}

//------------------------------------------------------------------------------
bool vtkSlicerVascularTerritoriesLogic::IsStageComplete()
{
  // Stage-3 completion predicate per ADR-0023 §"Shell composition
  // (Option H)" + §"Class abstraction for territories": the stage is
  // done iff at least one territories node exists in the scene.  The
  // abstract base ``vtkMRMLAbstractTerritoriesNode`` catches both the
  // Auto-tab ``vtkMRMLStdCouinaudTerritoriesNode`` and the Manual-tab
  // ``vtkMRMLCustomTerritoriesNode`` subclasses with a single
  // ``GetNodesByClass`` call.
  vtkMRMLScene* scene = this->GetMRMLScene();
  if (!scene)
  {
    return false;
  }
  vtkSmartPointer<vtkCollection> nodes = vtkSmartPointer<vtkCollection>::Take(scene->GetNodesByClass("vtkMRMLAbstractTerritoriesNode"));
  return nodes && nodes->GetNumberOfItems() > 0;
}

//------------------------------------------------------------------------------
void vtkSlicerVascularTerritoriesLogic::MarkSegmentWithID(vtkMRMLModelNode* segment, int segmentId)
{
  auto idArray = vtkSmartPointer<vtkIntArray>::New();
  idArray->SetName("segmentId");

  if (!segment) // Allow function to run with nullptr as input
  {
    std::cout << "MarkSegmentWithID Error: No input" << std::endl;
    return;
  }

  auto polydata = segment->GetPolyData();
  int numberOfPoints = polydata->GetNumberOfPoints();
  for (int i = 0; i < numberOfPoints; i++)
  {
    idArray->InsertNextValue(segmentId);
  }
  polydata->GetPointData()->SetScalars(idArray);
}

void vtkSlicerVascularTerritoriesLogic::AddSegmentToCenterlineModel(vtkMRMLModelNode* summedCenterline, vtkMRMLModelNode* segmentCenterline)
{
  if (!summedCenterline || !segmentCenterline) // Allow function to run with nullptr as input
  {
    std::cout << "AddSegmentToCenterlineModel Error: No input" << std::endl;
    return;
  }
  auto segment = segmentCenterline->GetPolyData();
  auto centerlineModel = summedCenterline->GetPolyData();

  auto summedModel = vtkSmartPointer<vtkPolyData>::New();
  auto appendFilter = vtkSmartPointer<vtkAppendPolyData>::New();
  appendFilter->AddInputData(centerlineModel);
  appendFilter->AddInputData(segment);
  summedModel = appendFilter->GetOutput();
  appendFilter->Update();

  summedCenterline->SetAndObservePolyData(summedModel);
}

int vtkSlicerVascularTerritoriesLogic::SegmentClassificationProcessing(vtkMRMLModelNode* centerlineModel, vtkMRMLLabelMapVolumeNode* labelMap)
{
  auto ijkToRas = vtkSmartPointer<vtkMatrix4x4>::New();

  if (!centerlineModel || !labelMap) // Allow function to run with nullptr as input
  {
    std::cout << "SegmentClassificationProcessing Error: No input" << std::endl;
    return 0;
  }

  labelMap->GetIJKToRASMatrix(ijkToRas);

  auto centerlinePolyData = centerlineModel->GetPolyData();
  auto pointData = centerlinePolyData->GetPointData();

  auto centerlineSegmentIDs = vtkIntArray::SafeDownCast(pointData->GetScalars());

  if (centerlineSegmentIDs == nullptr)
  {
    std::cout << "Error: No PointData in centerline model" << std::endl;
    return 0;
  }

  auto imageData = labelMap->GetImageData();
  int extent[6];
  imageData->GetExtent(extent);

  for (int z = extent[4]; z <= extent[5]; z++)
  {
    for (int y = extent[2]; y <= extent[3]; y++)
    {
      for (int x = extent[0]; x <= extent[1]; x++)
      {
        auto label = static_cast<short*>(imageData->GetScalarPointer(x, y, z));
        if (*label == 1)
        {
          double position_IJK[4];
          position_IJK[0] = static_cast<double>(x);
          position_IJK[1] = static_cast<double>(y);
          position_IJK[2] = static_cast<double>(z);
          position_IJK[3] = 1.0f;
          double position_RAS[4];
          ijkToRas->MultiplyPoint(position_IJK, position_RAS);
          double vtkVoxelPoint[3] = { position_RAS[0], position_RAS[1], position_RAS[2] };
          double vtkCenterlinePoint[3];
          vtkIdType id = this->Locator->FindClosestPoint(vtkVoxelPoint);
          centerlinePolyData->GetPoint(id, vtkCenterlinePoint);
          *label = centerlineSegmentIDs->GetTuple1(id);
        }
      }
    }
  }

  return 1;
}

void vtkSlicerVascularTerritoriesLogic::InitializeCenterlineSearchModel(vtkMRMLModelNode* summedCenterline)
{
  this->Locator->Initialize();
  if (!summedCenterline) // Allow function to run with nullptr as input
  {
    std::cout << "InitializeCenterlineSearchModel Error: No input" << std::endl;
    return;
  }
  auto centerlineModel = summedCenterline->GetPolyData();
  this->Locator->SetDataSet(vtkPointSet::SafeDownCast(centerlineModel));
  if (centerlineModel->GetPointData()->GetNumberOfArrays() > 0)
  {
    this->Locator->BuildLocator();
  }
  else
  {
    std::cout << "Error: No PointData in centerline model" << std::endl;
  }
}

//----------------------------------------------------------------------------
std::string vtkSlicerVascularTerritoriesLogic::GetLiverSegmentId(vtkMRMLSegmentationNode* segmentationNode)
{
  if (!segmentationNode)
  {
    return "";
  }
  vtkSegmentation* segmentation = segmentationNode->GetSegmentation();
  if (!segmentation)
  {
    return "";
  }
  // Match the liver by its SNOMED-CT structure code in the TerminologyEntry
  // tag (ADR-0011 liver code), NOT by the segment name -- Stage 2 emits an
  // SCT-tagged canonical segmentation with arbitrary segment names.  Substring
  // match on scheme+code, tolerant of the meaning string (mirrors the Stage-2
  // isStructureAccepted check).
  const std::string liverToken = "SCT^10200004";
  std::vector<std::string> segmentIds;
  segmentation->GetSegmentIDs(segmentIds);
  for (const std::string& segmentId : segmentIds)
  {
    vtkSegment* segment = segmentation->GetSegment(segmentId);
    if (!segment)
    {
      continue;
    }
    std::string tag;
    if (segment->GetTag("TerminologyEntry", tag) && tag.find(liverToken) != std::string::npos)
    {
      return segmentId;
    }
  }
  return "";
}

void vtkSlicerVascularTerritoriesLogic::calculateVascularTerritoryMap(vtkMRMLSegmentationNode* vascularTerritorySegmentationNode,
                                                                      vtkMRMLScalarVolumeNode* refVolume,
                                                                      vtkMRMLSegmentationNode* segmentation,
                                                                      vtkMRMLModelNode* centerlineModel,
                                                                      vtkMRMLColorNode* colormap)
{
  vtkMRMLScene* mrmlScene = this->GetMRMLScene();

  if (!mrmlScene)
  {
    vtkErrorMacro("Error in calculateVascularTerritoryMap: no valid MRML scene.");
  }

  vtkMRMLNode* labelmapNode = mrmlScene->AddNewNodeByClass("vtkMRMLLabelMapVolumeNode");
  vtkMRMLLabelMapVolumeNode* labelmapVolumeNode = vtkMRMLLabelMapVolumeNode::SafeDownCast(labelmapNode);
  auto segmentationIds = vtkSmartPointer<vtkStringArray>::New();

  if (!vascularTerritorySegmentationNode || !segmentation || !colormap)
  {
    std::cout << "calculateVascularTerritoryMap Error: No input" << std::endl;
    return;
  }

  // Get voxels tagged as liver -- resolved by SCT structure tag (ADR-0011),
  // not the segment name, so the Stage-2 SCT-tagged canonical segmentation
  // feeds Stage 3 (ADR-0024 §Output contract).
  std::string segmentId = this->GetLiverSegmentId(segmentation);
  // Check metadata for segmentation
  vtkSegmentation* segm = segmentation->GetSegmentation();
  int numberOfSegments = segm->GetNumberOfSegments();
  std::cout << "Liver segmentId: " << segmentId << " numberOfSegments: " << numberOfSegments << std::endl;

  vtkSegment* liverSegm = segm->GetSegment(segmentId);
  if (liverSegm)
  {
    std::cout << "Segment name: " << liverSegm->GetName() << " Segment label: " << liverSegm->GetLabelValue() << std::endl;
  }

  segmentationIds->InsertNextValue(segmentId);
  vtkSlicerSegmentationsModuleLogic::ExportSegmentsToLabelmapNode(segmentation, segmentationIds, labelmapVolumeNode, refVolume);
  int result = SegmentClassificationProcessing(centerlineModel, labelmapVolumeNode);
  if (result == 0)
  {
    vtkErrorMacro("Corrupt centerline model - Not possible to calculate vascular segments.");
  }
  labelmapVolumeNode->GetDisplayNode()->SetAndObserveColorNodeID(colormap->GetID());
  // slicer.util.arrayFromVolumeModified(labelmapVolumeNode)
  labelmapVolumeNode->Modified(); // Is this enough, or is more of the code in arrayFromVolumeModified needed?
  const char* segmentationId = vascularTerritorySegmentationNode->GetAttribute("VascularTerritories.SegmentationId");
  std::string segmentationIdCopy;
  if (segmentationId)
  {
    segmentationIdCopy = segmentationId;
  }

  vascularTerritorySegmentationNode->Reset(nullptr);
  // ``segmentationId`` is owned by the node's attribute table and has been
  // cleared by Reset(); the re-set below uses the safe ``segmentationIdCopy``.
  vascularTerritorySegmentationNode->CreateDefaultDisplayNodes(); // only needed for display
  vtkSlicerSegmentationsModuleLogic::ImportLabelmapToSegmentationNode(labelmapVolumeNode, vascularTerritorySegmentationNode);
  vascularTerritorySegmentationNode->CreateClosedSurfaceRepresentation();

  if (!segmentationIdCopy.empty())
  {
    vascularTerritorySegmentationNode->SetAttribute("VascularTerritories.SegmentationId", segmentationIdCopy.c_str());
  }
  mrmlScene->RemoveNode(labelmapVolumeNode);
}

void vtkSlicerVascularTerritoriesLogic::preprocessAndDecimate(vtkPolyData* surfacePolyData, vtkPolyData* returnPolyData)
{
  vtkMRMLScene* mrmlScene = this->GetMRMLScene();
  if (!mrmlScene)
  {
    vtkErrorMacro("Error in preprocessAndDecimate: no valid MRML scene.");
  }
  if (!surfacePolyData || (surfacePolyData->GetPointData()->GetNumberOfArrays() == 0 && surfacePolyData->GetCellData()->GetNumberOfArrays() == 0))
  {
    std::cout << "preprocessAndDecimate Error: no input surfacePolyData." << std::endl;
    return;
  }

  vtkSmartPointer<vtkDecimatePro> decimator = vtkSmartPointer<vtkDecimatePro>::New();
  double decimationFactor = 0.8;
  decimator->SetInputData(surfacePolyData);
  decimator->SetFeatureAngle(60);
  decimator->SplittingOff();
  decimator->PreserveTopologyOn();
  decimator->SetMaximumError(1);

  decimator->SetTargetReduction(decimationFactor);
  decimator->Update();

  vtkSmartPointer<vtkCleanPolyData> surfaceCleaner = vtkSmartPointer<vtkCleanPolyData>::New();
  surfaceCleaner->SetInputData(decimator->GetOutput());
  surfaceCleaner->Update();

  vtkSmartPointer<vtkTriangleFilter> surfaceTriangulator = vtkSmartPointer<vtkTriangleFilter>::New();
  surfaceTriangulator->SetInputData(surfaceCleaner->GetOutput());
  surfaceTriangulator->PassLinesOff();
  surfaceTriangulator->PassVertsOff();
  surfaceTriangulator->Update();

  vtkSmartPointer<vtkPolyDataNormals> normals = vtkSmartPointer<vtkPolyDataNormals>::New();
  normals->SetInputData(surfaceTriangulator->GetOutput());
  normals->SetAutoOrientNormals(1);
  normals->SetFlipNormals(0);
  normals->SetConsistency(1);
  normals->SplittingOff();
  normals->Update();

  returnPolyData->ShallowCopy(normals->GetOutput());
}

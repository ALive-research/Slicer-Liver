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

#ifndef __vtkslicervascularterritorieslogic_h_
#define __vtkslicervascularterritorieslogic_h_

#include "vtkSlicerVascularTerritoriesModuleLogicExport.h"

// Slicer include
#include <vtkSlicerModuleLogic.h>

#include <vtkObject.h>
#include <vtkSmartPointer.h>

#include <string>

// Forward delcarations
class vtkKdTreePointLocator;
class vtkMRMLLabelMapVolumeNode;
class vtkMRMLNode;
class vtkMRMLSegmentationNode;
class vtkMRMLModelNode;
class vtkMRMLColorNode;
class vtkMRMLScalarVolumeNode;
class vtkPolyData;

class VTK_SLICER_VASCULARTERRITORIES_MODULE_LOGIC_EXPORT vtkSlicerVascularTerritoriesLogic : public vtkSlicerModuleLogic
{
private:
  vtkSmartPointer<vtkKdTreePointLocator> Locator;

public:
  static vtkSlicerVascularTerritoriesLogic* New();
  vtkTypeMacro(vtkSlicerVascularTerritoriesLogic, vtkSlicerModuleLogic);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  /// Register the v2.0.0 territories MRML node family with the scene
  /// so scene save/load and ``AddNewNodeByClass`` resolve the class
  /// names per ADR-0023 §"Class abstraction for territories".
  void RegisterNodes() override;

  /// Place newly added territory nodes under the "Vascular
  /// Territories" Subject Hierarchy folder (per ADR-0023 §"MRML
  /// scene organisation").  Folder is created lazily on first
  /// territory-node arrival.
  void OnMRMLSceneNodeAdded(vtkMRMLNode* node) override;

protected:
  /// Override to opt-in to ``NodeAddedEvent`` observation -- the
  /// default ``vtkMRMLAbstractLogic::SetMRMLSceneInternal`` uses
  /// ``SetObject`` (no event observation), so ``OnMRMLSceneNodeAdded``
  /// would never fire without this override.  Pattern mirrors
  /// ``vtkSlicerLiverResectionsLogic::SetMRMLSceneInternal``.
  void SetMRMLSceneInternal(vtkMRMLScene* newScene) override;

public:
  /// Stage-3 completion predicate for the Liver-shell sidebar (T5.2-d).
  ///
  /// Returns ``true`` once the scene carries at least one node
  /// derived from ``vtkMRMLAbstractTerritoriesNode`` (Auto-tab
  /// ``vtkMRMLStdCouinaudTerritoriesNode`` or Manual-tab
  /// ``vtkMRMLCustomTerritoriesNode`` — see ADR-0023 §"Class
  /// abstraction for territories").  The Liver shell observes scene
  /// events and re-queries this predicate to refresh its per-stage
  /// state indicator (ADR-0023 §"Shell composition (Option H)").
  ///
  /// Returns ``false`` when no MRML scene is bound or no territories
  /// node has been registered yet.
  virtual bool IsStageComplete();

  void MarkSegmentWithID(vtkMRMLModelNode* segment, int segmentId);
  void AddSegmentToCenterlineModel(vtkMRMLModelNode* summedCenterline, vtkMRMLModelNode* segmentCenterline);
  int SegmentClassificationProcessing(vtkMRMLModelNode* centerlineModel, vtkMRMLLabelMapVolumeNode* labelMap);
  void InitializeCenterlineSearchModel(vtkMRMLModelNode* summedCenterline);
  void calculateVascularTerritoryMap(vtkMRMLSegmentationNode* vascularTerritorySegmentationNode,
                                     vtkMRMLScalarVolumeNode* refVolume,
                                     vtkMRMLSegmentationNode* segmentation,
                                     vtkMRMLModelNode* centerlineModel,
                                     vtkMRMLColorNode* colormap);
  void preprocessAndDecimate(vtkPolyData* surfacePolyData, vtkPolyData* returnPolyData);

  /// Return the segment id of the liver parenchyma in ``segmentationNode``,
  /// resolved by its SNOMED-CT structure tag (ADR-0011 liver code 10200004 in
  /// the segment's ``TerminologyEntry`` tag), NOT by the segment name "liver".
  /// This matches what Stage 2 writes (an SCT-tagged canonical segmentation
  /// with arbitrary segment names).  Empty string when there is no scene / no
  /// segmentation / no SCT-liver-tagged segment.
  std::string GetLiverSegmentId(vtkMRMLSegmentationNode* segmentationNode);

protected:
  vtkSlicerVascularTerritoriesLogic();
  ~vtkSlicerVascularTerritoriesLogic() override;
  vtkSlicerVascularTerritoriesLogic(const vtkSlicerVascularTerritoriesLogic&);
  void operator=(const vtkSlicerVascularTerritoriesLogic&);
};

#endif

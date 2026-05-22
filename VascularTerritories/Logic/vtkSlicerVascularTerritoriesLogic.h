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

public:
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

protected:
  vtkSlicerVascularTerritoriesLogic();
  ~vtkSlicerVascularTerritoriesLogic() override;
  vtkSlicerVascularTerritoriesLogic(const vtkSlicerVascularTerritoriesLogic&);
  void operator=(const vtkSlicerVascularTerritoriesLogic&);
};

#endif

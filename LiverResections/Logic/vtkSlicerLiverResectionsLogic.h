/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2021-2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

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
  Hospital and NTNU) and was supported by The Research Council of Norway
  through the ALive project (grant nr. 311393).

==============================================================================*/

#ifndef __vtkslicerlivermarkupslogic_h_
#define __vtkslicerlivermarkupslogic_h_

#include "vtkSlicerLiverResectionsModuleLogicExport.h"

// Slicer include
#include <vtkSlicerModuleLogic.h>

// VTK includes
#include <vtkWeakPointer.h>
#include <vtkSmartPointer.h>
#include <vtkMRMLMessageCollection.h>
#include <vtkPolyData.h>
#include <vtkMRMLScalarVolumeNode.h>

// STD include
#include <vtkMRMLTableNode.h>
#include <vtkMRMLLabelMapVolumeNode.h>
#include <itkImage.h>

class vtkMRMLResectionPlanNode;

//------------------------------------------------------------------------------
class VTK_SLICER_LIVERRESECTIONS_MODULE_LOGIC_EXPORT vtkSlicerLiverResectionsLogic : public vtkSlicerModuleLogic
{
public:
  static vtkSlicerLiverResectionsLogic* New();
  vtkTypeMacro(vtkSlicerLiverResectionsLogic, vtkSlicerModuleLogic);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  void ProcessMRMLNodesEvents(vtkObject* caller, unsigned long event, void* callData) override;

  /// Set mrml scene
  void SetMRMLSceneInternal(vtkMRMLScene* newScene) override;

  /// Register module MRML nodes
  void RegisterNodes() override;

  /// Stage-4 completion predicate for the Liver-shell sidebar (T5.2-d).
  ///
  /// Returns ``true`` once the scene carries at least one
  /// ``vtkMRMLResectionPlanNode`` whose ``State`` reaches ``Confirmed``
  /// (see ADR-0019 for the state machine).  The Liver shell observes
  /// scene events via ``VTKObservationMixin`` and re-queries this
  /// predicate to refresh its per-stage state indicator
  /// (ADR-0023 §"Shell composition (Option H)").
  ///
  /// Returns ``false`` when no MRML scene is bound or no plan has
  /// reached ``Confirmed``.  T3 stage-4 assertions in
  /// ``Liver/Testing/Python/test_liver_shell_isstagecomplete.py``
  /// pin this contract.
  virtual bool IsStageComplete();

  char* LoadLiverResection(const std::string& fileName, const std::string& nodeName /*=nullptr*/, vtkMRMLMessageCollection* userMessages /*=nullptr*/);

  /// Create a new v2 resection node graph and return the plan wrapper.
  ///
  /// Mints the carrier + plan + display triad the interactive workflow
  /// needs (ADR-0014 §"Fourth layer"; ADR-0032), identically to the file
  /// loaders: a ``vtkMRMLResectionPlanNode`` wrapper whose typed
  /// ``geometry`` reference resolves a freshly-created
  /// ``vtkMRMLBezierSurfaceNode`` carrier carrying a default
  /// ``vtkMRMLParametricSurfaceDisplayNode`` (which the LayerDM Pipeline
  /// creator matches on).  The plan starts in ``Init`` (ADR-0019); the
  /// control grid is seeded by the placement step, not here.  Returns
  /// nullptr when no MRML scene is bound or node instantiation fails.
  vtkMRMLResectionPlanNode* CreateResectionPlan(const char* name = nullptr);

protected:
  vtkSlicerLiverResectionsLogic();
  ~vtkSlicerLiverResectionsLogic() override;

protected:
  void ObserveMRMLScene() override;
  void OnMRMLSceneNodeAdded(vtkMRMLNode* node) override;
  void OnMRMLSceneNodeRemoved(vtkMRMLNode* node) override;

private:
  vtkSlicerLiverResectionsLogic(const vtkSlicerLiverResectionsLogic&) = delete;
  void operator=(const vtkSlicerLiverResectionsLogic&) = delete;
};

#endif // __vtkslicerlivermarkupslogic_h_

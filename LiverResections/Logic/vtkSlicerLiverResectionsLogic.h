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

// STD include
#include <map>

//j------------------------------------------------------------------------------
class vtkMRMLLiverResectionNode;
class vtkMRMLMarkupsNode;
class vtkMRMLMarkupsDistanceContourNode;
class vtkMRMLMarkupsSlicingContourNode;
class vtkMRMLMarkupsBezierSurfaceNode;

//------------------------------------------------------------------------------
class VTK_SLICER_LIVERRESECTIONS_MODULE_LOGIC_EXPORT vtkSlicerLiverResectionsLogic:
  public vtkSlicerModuleLogic
{
public:
  static vtkSlicerLiverResectionsLogic* New();
  vtkTypeMacro(vtkSlicerLiverResectionsLogic, vtkSlicerModuleLogic);
  void PrintSelf(ostream& os, vtkIndent indent) override;


  void ProcessMRMLNodesEvents(vtkObject *caller,
                              unsigned long event,
                              void *callData) override;

  /// Set mrml scene
  void SetMRMLSceneInternal(vtkMRMLScene *newScene) override;

  /// Register module MRML nodes
  void RegisterNodes() override;

  /// Add a new resection using contour initialization using slicing contours initialization
  vtkMRMLMarkupsDistanceContourNode* AddResectionContour(vtkMRMLLiverResectionNode *resectionNode) const;

  /// Add a new resection using planar initialization
  vtkMRMLMarkupsSlicingContourNode* AddResectionPlane(vtkMRMLLiverResectionNode *resectionNode) const;

  void ShowBezierSurfaceMarkupFromResection(vtkMRMLLiverResectionNode* resectionNode) const;
  void HideBezierSurfaceMarkupFromResection(vtkMRMLLiverResectionNode* resectionNode) const;
  void ShowInitializationMarkupFromResection(vtkMRMLLiverResectionNode* resectionNode) const;
  void HideInitializationMarkupFromResection(vtkMRMLLiverResectionNode* resectionNode) const;
  void ShowBezierSurfaceMarkup(vtkMRMLMarkupsNode* markupsInitializationNode) const;
  void HideBezierSurfaceMarkup(vtkMRMLMarkupsNode* markupsInitializationNode) const;
  void ShowInitializationMarkup(vtkMRMLMarkupsBezierSurfaceNode* markupsBezierNode) const;
  void HideInitializationMarkup(vtkMRMLMarkupsBezierSurfaceNode* markupsBezierNode) const;

protected:
  vtkSlicerLiverResectionsLogic();
  ~vtkSlicerLiverResectionsLogic() override;

protected:
  void ObserveMRMLScene() override;
  void OnMRMLSceneNodeAdded(vtkMRMLNode* node) override;
  void OnMRMLSceneNodeRemoved(vtkMRMLNode* node) override;
  void UpdateBezierWidgetOnInitialization(vtkMRMLMarkupsNode* initializationNode);
  void CreateInitializationAndResectionMarkups(vtkMRMLLiverResectionNode* resectionNode);

  /// This function returns a bezier surface node from a provided resection node
  vtkMRMLLiverResectionNode* GetResectionFromBezier(vtkMRMLMarkupsBezierSurfaceNode* resectionNode) const;

  /// This function returns a initialization surface node from a provided resection node
  vtkMRMLLiverResectionNode* GetResectionFromInitialization(vtkMRMLMarkupsNode* resectionNode) const;

  /// This function returns a bezier surface node from a provided resection node
  vtkMRMLMarkupsBezierSurfaceNode* GetBezierFromResection(vtkMRMLLiverResectionNode* resectionNode) const;

  /// This function returns an initialization node from a provided resection node
  vtkMRMLMarkupsNode* GetInitializationFromResection(vtkMRMLLiverResectionNode* resectionNode) const;

  /// This function returns a bezier surface node from a provided initialization node
  vtkMRMLMarkupsBezierSurfaceNode* GetBezierFromInitialization(vtkMRMLMarkupsNode *initializationNode) const;

  /// This function returns an initialization node from a provided bezier surface node
  vtkMRMLMarkupsNode * GetInitializationFromBezier(vtkMRMLMarkupsBezierSurfaceNode* bezierNode) const;

  /// Add a bezier surface markup and set the default properties
  vtkMRMLMarkupsBezierSurfaceNode* AddBezierSurface(vtkMRMLLiverResectionNode *resectionNode) const;

  /// Add the initialization markup of the correct type associated to the provided resection node
  vtkMRMLMarkupsNode* AddInitializationMarkupsNode(vtkMRMLLiverResectionNode* resectionNode) const;

protected:

  /// TODO: Too many maps here. We should try to improve the design to avoid this.

  std::map<vtkSmartPointer<vtkMRMLLiverResectionNode>,
           vtkSmartPointer<vtkMRMLMarkupsNode>> ResectionToInitializationMap;

  std::map<vtkSmartPointer<vtkMRMLMarkupsNode>,
           vtkSmartPointer<vtkMRMLLiverResectionNode>> InitializationToResectionMap;

  std::map<vtkSmartPointer<vtkMRMLLiverResectionNode>,
           vtkSmartPointer<vtkMRMLMarkupsBezierSurfaceNode>> ResectionToBezierMap;

  std::map<vtkSmartPointer<vtkMRMLMarkupsBezierSurfaceNode>,
           vtkSmartPointer<vtkMRMLLiverResectionNode>> BezierToResectionMap;

  std::map<vtkWeakPointer<vtkMRMLMarkupsNode>,
           vtkWeakPointer<vtkMRMLMarkupsBezierSurfaceNode>> InitializationToBezierMap;

  std::map<vtkWeakPointer<vtkMRMLMarkupsBezierSurfaceNode>,
           vtkWeakPointer<vtkMRMLMarkupsNode>> BezierToInitializationMap;

private:
  vtkSlicerLiverResectionsLogic(const vtkSlicerLiverResectionsLogic &) = delete;
  void operator=(const vtkSlicerLiverResectionsLogic&) = delete;
};

#endif // __vtkslicerlivermarkupslogic_h_

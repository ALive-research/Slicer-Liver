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

#ifndef __vtkmrmlliverresectionnode_h_
#define __vtkmrmlliverresectionnode_h_

#include "vtkMRMLMarkupsBezierSurfaceNode.h"
#include "vtkSlicerLiverResectionsModuleMRMLExport.h"

// MRML includes
#include <vtkMRMLModelNode.h>
#include <vtkMRMLSegmentationNode.h>
#include <vtkMRMLScalarVolumeNode.h>

//VTK includes
#include <vtkSetGet.h>
#include <vtkWeakPointer.h>
#include <vtkCollection.h>
#include <vtkPoints.h>

//STD includes
#include <set>
#include <string>

//-----------------------------------------------------------------------------
class VTK_SLICER_LIVERRESECTIONS_MODULE_MRML_EXPORT vtkMRMLLiverResectionNode
: public vtkMRMLStorableNode
{
public:
  static vtkMRMLLiverResectionNode* New();
  vtkTypeMacro(vtkMRMLLiverResectionNode, vtkMRMLStorableNode);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  // Possible resection states
  enum ResectionState
    {
      Initialization=0,
      Deformation,
      Completed
    };

  // Possible initialization modes
  enum InitializationMode
    {
      Flat=0,
      Curved,
    };

  //--------------------------------------------------------------------------------
  // MRMLNode methods
  //--------------------------------------------------------------------------------
  vtkMRMLNode* CreateNodeInstance() override;

  /// Get node XML tag name (like Volume, Model)
  const char* GetNodeTagName() override {return "LiverResection";}

  /// \sa vtkMRMLNode::CopyContent
  vtkMRMLCopyContentDefaultMacro(vtkMRMLLiverResectionNode);

  /// Create default storage node or nullptr if does not have one
  vtkMRMLStorageNode* CreateDefaultStorageNode();


  // TODO: Review the need for this further down the road
  /// Get target lesions identifiers
  // std::set<vtkMRMLModelNode*> GetTargetTumors() const {return this->TargetTumors;}
  // /// Add a new lesion identifier
  // void AddTargetTumor(vtkMRMLModelNode* tumorModel)
  // {this->TargetTumors.insert(tumorModel); this->Modified();}
  // /// Remove a lesion identifier
  // void RemoveTargetTumor(vtkMRMLModelNode* tumorModel)
  // {this->TargetTumors.erase(tumorModel); this->Modified();}

  // TODO: Review the need for this further down the road
  // vtkMRMLSegmentationNode* GetSegmentationNode() const {return this->SegmentationNode;}
  // void SetSegmentationNode(vtkMRMLSegmentationNode *segmentationNode)
  // {this->SegmentationNode = segmentationNode; this->Modified();}

  // Get resection margin
  vtkGetMacro(ResectionMargin, double);
  // Set resection margin
  vtkSetClampMacro(ResectionMargin, double, 0.0, VTK_DOUBLE_MAX);

  // Get resection margin
  vtkGetMacro(UncertaintyMargin, double);
  // Set resection margin
  vtkSetClampMacro(UncertaintyMargin, double, 0.0, VTK_DOUBLE_MAX);

  // Get resection status
  vtkGetMacro(State, ResectionState);
  // Set resection status
  vtkSetMacro(State, ResectionState);

  // Get resection initialization
  vtkGetMacro(InitMode, InitializationMode);
  // Set resection initialization
  vtkSetMacro(InitMode, InitializationMode);

  // Get Target Organ
  vtkMRMLModelNode *GetTargetOrganModelNode() const
  {return this->TargetOrganModelNode;}

  // Set Target Organ
  void SetTargetOrganModelNode(vtkMRMLModelNode *targetOrgan)
  {this->TargetOrganModelNode = targetOrgan; this->Modified();}

  // Get Distance Map
  vtkMRMLScalarVolumeNode*GetDistanceMapVolumeNode() const
  {return this->DistanceMapVolumeNode;}

  // Set Distance Map
  void SetDistanceMapVolumeNode(vtkMRMLScalarVolumeNode* distanceMapVolumeNode)
  {this->DistanceMapVolumeNode = distanceMapVolumeNode; this->Modified();}

  /// This is a function to set the initialization control points as vtkPoints.
  /// Since the expected number of points for the initialization is two, the
  /// function requires at least two points in the vtkPoints provided; if more
  /// points are provided, the points from 2nd onwards will be ignored. The
  /// function returns true if thw points were set correctly, otherwise, it
  /// returns false.
  bool SetInitializationControlPoints(vtkPoints* controlPoints);

  // Get initialization control points
  vtkPoints const* GetInitializationPoints() const
  {return const_cast<vtkPoints const*>(this->InitializationControlPoints.GetPointer());}

  /// This is a function to set the bezier surface control points as vtkPoints.
  /// Since the expected number of points for the bezier is 16, the function
  /// requires at least 16 points in the vtkPoints provided; if more points are
  /// provided, the points from 2nd onwards will be ignored. The function
  /// returns true if thw points were set correctly, otherwise, it returns
  /// false.
  bool SetBezierSurfaceControlPoints(vtkPoints* controlPoints);

  // Get bezier surface control points
  vtkPoints const* GetBezierSurfacePoints() const
  {return const_cast<vtkPoints const*>(this->InitializationControlPoints.GetPointer());}

  // Get bezier control points
  vtkPoints const* GetBezierPoints() const
  {return const_cast<vtkPoints const*>(this->BezierSurfaceControlPoints.GetPointer());}

  // Set the clipout state variable
  vtkSetMacro(ClipOut, bool);

  // Get the clipout state variable
  vtkGetMacro(ClipOut, bool);

  // Set the clipout state variable
  vtkSetMacro(ClipOut, int);

  // Set the widget visibility variable
  vtkSetMacro(WidgetVisibility, bool);

  // Get the widget visibility variable
  vtkGetMacro(WidgetVisibility, bool);

  // Set the widget visibility variable
  vtkSetMacro(WidgetVisibility, int);

  // Get interpolated margins property
  vtkGetMacro(InterpolatedMargins, bool);

  // Set interpolated margins property
  vtkSetMacro(InterpolatedMargins, bool);

  // Set interpolated property
  vtkSetVector3Macro(ResectionColor, float);

  // Get interpolated property
  vtkGetVector3Macro(ResectionColor, float);

  // Set interpolated property
  vtkSetVector3Macro(ResectionGridColor, float);

  // Get interpolated property
  vtkGetVector3Macro(ResectionGridColor, float);

  // Set interpolated margins property
  vtkSetVector3Macro(ResectionMarginColor, float);

  // Get interpolated margins property
  vtkGetVector3Macro(ResectionMarginColor, float);

  // Set interpolated margins property
  vtkSetVector3Macro(UncertaintyMarginColor, float);

  // Get interpolated margins property
  vtkGetVector3Macro(UncertaintyMarginColor, float);

  // Get resection opacity property
  vtkGetMacro(ResectionOpacity, float);

  // Set resection opacity property
  vtkSetClampMacro(ResectionOpacity, float, 0.0f, 1.0f);

  // Get the widget visibility variable
  vtkGetMacro(GridVisibility, bool);

  // Set the widget visibility variable
  vtkSetMacro(GridVisibility, int);

  // Get the widget visibility variable
  vtkGetMacro(GridDivisions, float);

  // Set the widget visibility variable
  vtkSetMacro(GridDivisions, float);

  // Get the widget visibility variable
  vtkGetMacro(GridThickness, float);

  // Set the widget visibility variable
  vtkSetMacro(GridThickness, float);

  // Get bezier surface
  vtkMRMLMarkupsBezierSurfaceNode* GetBezierSurfaceNode() const
  {return this->BezierSurfaceNode;}

  // Set bezier surface
  void SetBezierSurfaceNode(vtkMRMLMarkupsBezierSurfaceNode *node)
  {this->BezierSurfaceNode = node; this->Modified();}


protected:
  vtkMRMLLiverResectionNode();
  ~vtkMRMLLiverResectionNode() override;

private:

  // TODO: Review the need of this further down the road
  // std::set<vtkMRMLModelNode*> TargetTumors;
  // vtkWeakPointer<vtkMRMLSegmentationNode> SegmentationNode;
  vtkWeakPointer<vtkMRMLModelNode> TargetOrganModelNode;
  vtkWeakPointer<vtkMRMLScalarVolumeNode> DistanceMapVolumeNode;
  vtkWeakPointer<vtkMRMLMarkupsBezierSurfaceNode> BezierSurfaceNode;
  ResectionState State;
  InitializationMode InitMode;
  double ResectionMargin; //Resection margin in mm
  double UncertaintyMargin; //Uncertainty margin in mm
  vtkNew<vtkPoints> InitializationControlPoints;
  // TODO: Review the need for this. We already have a pointer to the surface node
  vtkNew<vtkPoints> BezierSurfaceControlPoints;
  bool ClipOut;
  bool WidgetVisibility;
  bool InterpolatedMargins;
  float ResectionColor[3];
  float ResectionGridColor[3];
  float ResectionMarginColor[3];
  float UncertaintyMarginColor[3];
  float ResectionOpacity;
  bool GridVisibility;
  float GridDivisions;
  float GridThickness;

private:
 vtkMRMLLiverResectionNode(const vtkMRMLLiverResectionNode&);
 void operator=(const vtkMRMLLiverResectionNode&);
};

#endif //__vtkmrmlliverresectionnode_h_

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

  This file was originally developed by Rafael Palomar (The Intervention Centre,
  Oslo University Hospital) and was supported by The Research Council of Norway
  through the ALive project (grant nr. 311393).

==============================================================================*/

#ifndef __vtkmrmlliverresectionnode_h_
#define __vtkmrmlliverresectionnode_h_

#include "vtkSlicerLiverResectionsModuleMRMLExport.h"

// MRML includes
#include <vtkMRMLModelNode.h>
#include <vtkMRMLSegmentationNode.h>
#include <vtkMRMLScalarVolumeNode.h>

//VTK includes
#include <vtkWeakPointer.h>
#include <vtkCollection.h>
#include <vtkPoints.h>

//STD includes
#include <set>
#include <string>

//-----------------------------------------------------------------------------
class VTK_SLICER_LIVERRESECTIONS_MODULE_MRML_EXPORT vtkMRMLLiverResectionNode
: public vtkMRMLNode
{
public:
  static vtkMRMLLiverResectionNode* New();
  vtkTypeMacro(vtkMRMLLiverResectionNode, vtkMRMLNode);
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

  // Get Target Organ
  vtkMRMLScalarVolumeNode*GetDistanceMapVolumeNode() const
  {return this->DistanceMapVolume;}

  // Set Target Organ
  void SetDistanceMapVolumeNode(vtkMRMLScalarVolumeNode* distanceMapVolume)
  {this->DistanceMapVolume = distanceMapVolume; this->Modified();}

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

protected:
  vtkMRMLLiverResectionNode();
  ~vtkMRMLLiverResectionNode() override;

private:

  // TODO: Review the need of this further down the road
  // std::set<vtkMRMLModelNode*> TargetTumors;
  // vtkWeakPointer<vtkMRMLSegmentationNode> SegmentationNode;
  vtkWeakPointer<vtkMRMLModelNode> TargetOrganModelNode;
  vtkWeakPointer<vtkMRMLScalarVolumeNode> DistanceMapVolume;
  ResectionState State;
  InitializationMode InitMode;
  double ResectionMargin; //Resection margin in mm
  vtkNew<vtkPoints> InitializationControlPoints;
  vtkNew<vtkPoints> BezierSurfaceControlPoints;

private:
 vtkMRMLLiverResectionNode(const vtkMRMLLiverResectionNode&);
 void operator=(const vtkMRMLLiverResectionNode&);
};

#endif //__vtkmrmlliverresectionnode_h_

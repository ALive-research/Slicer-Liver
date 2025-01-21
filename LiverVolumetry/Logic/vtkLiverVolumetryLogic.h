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

  This file was originally developed by Ruoyan Meng (NTNU), and was
  supported by The Research Council of Norway through the ALive project
  (grant nr. 311393).

  ==============================================================================*/

#ifndef SLICERLIVER_LIVERVOLUMETRY_LOGIC_VTKLIVERVOLUMETRYLOGIC_H_
#define SLICERLIVER_LIVERVOLUMETRY_LOGIC_VTKLIVERVOLUMETRYLOGIC_H_

#include "vtkSlicerLiverVolumetryModuleLogicExport.h"
#include <vtkObject.h>
#include <vtkSmartPointer.h>
#include <itkImage.h>
#include <vtkCollection.h>
#include <vtkTable.h>

class vtkMRMLLabelMapVolumeNode;
class vtkMRMLModelNode;
class vtkMRMLMarkupsBezierSurfaceNode;
class vtkMRMLMarkupsFiducialNode;
class vtkBezierSurfaceSource;
class vtkMRMLLiverResectionNode;
class vtkMRMLTableNode;
class vtkMRMLScalarVolumeNode;
class vtkOrientedImageData;

class VTK_SLICER_LIVERVOLUMETRY_MODULE_LOGIC_EXPORT
vtkLiverVolumetryLogic : public vtkObject {
 private:

 public:
  static vtkLiverVolumetryLogic *New();
 vtkTypeMacro(vtkLiverVolumetryLogic, vtkObject);
  void PrintSelf(ostream &os, vtkIndent indent) override;

 public:

  void ComputeAdvancedPlanningVolumetry(vtkMRMLLabelMapVolumeNode *TargetSegmentLabelMap,
                        vtkMRMLTableNode *OutputTableNode,
                        vtkMRMLMarkupsFiducialNode *ROIMarkersList,
                        vtkCollection *resectionNodes,
                        double TargetSegmentationVolume = 0.0);
  int GetSegmentVoxels(vtkOrientedImageData *TargetSegmentLabelMap);
  std::vector<int> GetROIPointsLabelValue(vtkMRMLLabelMapVolumeNode* TargetSegmentsLabelMap, vtkMRMLMarkupsFiducialNode* ROIMarkersList);
  vtkSmartPointer<vtkBezierSurfaceSource> GenerateBezierSurface(int Res, vtkMRMLMarkupsBezierSurfaceNode *bezierSurfaceNode);
  itk::Index<3> GetITKRGSeedIndex(double *ROISeedPoint, itk::SmartPointer<itk::Image<short, 3>> SourceImage);
  void VolumetryTable(std::string Properties, double TargetSegmentationVolume, int ROIVoxels, double ROIVolume, vtkMRMLTableNode *OutputTableNode);
  int GetRes(vtkMRMLMarkupsBezierSurfaceNode *bezierSurfaceNode, double space[3], int Steps);
  void GetResectionsProjectionITKImage(vtkMRMLLabelMapVolumeNode* SelectedSegmentsLabelMap,vtkCollection* ResectionNodes, int baseValue);
  void GenerateSegmentsLabelMap(vtkMRMLLabelMapVolumeNode* TargetSegmentLabelMapCopy, vtkMRMLLabelMapVolumeNode* newLabelMap,vtkCollection* ResectionNodes, vtkMRMLMarkupsFiducialNode* ROIMarkersList);

 protected:
  itk::SmartPointer<itk::Image<short, 3>> ProjectedTargetSegmentImage;
  itk::SmartPointer<itk::Image<short, 3>> connectedThreshold;
  vtkSmartPointer<vtkCollection> resectionNodes;

 protected:
  vtkLiverVolumetryLogic();
  ~vtkLiverVolumetryLogic() override;
  vtkLiverVolumetryLogic(const vtkLiverVolumetryLogic &);
  void operator=(const vtkLiverVolumetryLogic &);

};

#endif //SLICERLIVER_LIVERVOLUMETRY_LOGIC_VTKLIVERVOLUMETRYLOGIC_H_

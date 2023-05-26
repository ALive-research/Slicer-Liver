//
// Created by ruoyan on 22.05.23.
//

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
                        vtkCollection *resectionNodes);
  int GetSegmentVoxels(vtkOrientedImageData *TargetSegmentLabelMap);
  std::vector<int> GetROIPointsLabelValue(vtkMRMLLabelMapVolumeNode* TargetSegmentsLabelMap, vtkMRMLMarkupsFiducialNode* ROIMarkersList);
  vtkSmartPointer<vtkBezierSurfaceSource> GenerateBezierSurface(int Res, vtkMRMLMarkupsBezierSurfaceNode *bezierSurfaceNode);
  itk::Index<3> GetITKRGSeedIndex(double *ROISeedPoint, itk::SmartPointer<itk::Image<short, 3>> SourceImage);
  void VolumetryTable(std::string Properties, double TargetSegmentationVolume, int ROIVoxels, double ROIVolume, vtkMRMLTableNode *OutputTableNode);
  int GetRes(vtkMRMLMarkupsBezierSurfaceNode *bezierSurfaceNode, double space[3], int Steps);

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

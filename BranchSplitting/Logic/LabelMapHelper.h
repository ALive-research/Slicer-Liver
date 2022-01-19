/*===============================================================================

  Project: Slicer-LiverResectionPlanning
  Module: LabelMapHelper.h

  Contributors:
  - Rafael Palomar <rafael.palomar@rr-research.no>

  Copyright (c) 2015, The Intervention Centre - Oslo University Hospital

  All rights reserved. This is propietary software. In no event shall
  the author be liable for any claim or damages.

  =============================================================================*/
#ifndef __LabelMapHelper_h
#define __LabelMapHelper_h

//ITK includes
#include <itkImage.h>

//Forward declarations
class vtkMRMLScene;
class vtkMRMLScalarVolumeNode;
class vtkCollection;
class vtkMRMLColorTableNode;
class vtkImageData;

//Class declaration
class LabelMapHelper
{
 public:
  LabelMapHelper(){}
  ~LabelMapHelper(){}

  static bool ConvertLabelMapVolumeNodeToItkImage(vtkMRMLScalarVolumeNode* inVolumeNode,
						  typename itk::Image<short, 3>::Pointer outItkImage,
						  bool applyRasToWorldConversion=true,
						  bool applyRasToLpsConversion=true);

  static  bool ConvertItkImageToVtkImageData(typename itk::Image<short, 3>::Pointer inItkImage,
                                             vtkImageData* outVtkImageData, int vtkType);

  static bool ConvertItkImageToLabelMapVolumeNode(typename itk::Image<short, 3>::Pointer inItkImage,
						  vtkMRMLScalarVolumeNode* outVolumeNode,
						  int vtkType,
						  bool applyWorldToRasConversion=true,
						  bool applyLpsToRasConversion=true);

};

#endif

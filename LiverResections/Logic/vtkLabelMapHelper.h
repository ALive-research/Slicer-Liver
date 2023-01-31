/*===============================================================================

  Project: Slicer-LiverResectionPlanning
  Module: vtkLabelMapHelper.h

  Contributors:
  - Rafael Palomar <rafael.palomar@rr-research.no>

  Copyright (c) 2016, The Intervention Centre - Oslo University Hospital

  All rights reserved. This is propietary software. In no event shall
  the author be liable for any claim or damages.

  =============================================================================*/

#ifndef SLICERLIVER_LIVERRESECTIONS_LOGIC_VTKLABELMAPHELPER_H_
#define SLICERLIVER_LIVERRESECTIONS_LOGIC_VTKLABELMAPHELPER_H_

// ITK includes
#include <itkImage.h>
#include <itkConnectedThresholdImageFilter.h>

// VTK includes
#include <vtkObject.h>
#include <vtkSmartPointer.h>

//-------------------------------------------------------------------------------
// Forward declarations
class vtkMRMLScalarVolumeNode;
class vtkImageData;
class vtkMatrix4x4;
class vtkPoints;

//-------------------------------------------------------------------------------
class vtkLabelMapHelper: public vtkObject
{

 public:
  static vtkLabelMapHelper* New();
 vtkTypeMacro(vtkLabelMapHelper, vtkObject);
  void PrintSelf(ostream &os, vtkIndent indent);

  //Type definitions
  typedef itk::Image<short, 3> LabelMapType;
  typedef itk::ConnectedThresholdImageFilter<LabelMapType,LabelMapType>
      ConnectedThresholdType;

  //Description:
  // This function applies a connected threshold algorithm on the specified
  // image and returns a itk::Image::Pointer to the data. The object will keep
  // the data as long as the object is alive, this means that potentially no
  // external copy of the data is needed.
  LabelMapType::Pointer ConnectedThreshold(LabelMapType::Pointer itkImage,
                                           unsigned short lowerBound,
                                           unsigned short upperBound,
                                           unsigned short replacementValue,
                                           LabelMapType::IndexType seedIndex);

  // Description:
  // This function projects a set of points (vtkPoints) onto
  // an itkImage (volume type 'short'). Projection takes projectionValue values
  // with a radius around the projected point. The function returns the number
  // of points effectively projected.
  static unsigned int
  ProjectPointsOntoItkImage(LabelMapType::Pointer itkImage,
                            vtkPoints *points,
                            unsigned short projectionValue,
                            unsigned int radius=0);


  // Description:
  // This function converts the data contained in a vtkMRMLScalarVolume node
  // in a itkImage. The data must be type 'short'. This function does not make
  // any copy of the data, so the original imageData holder must have this into
  // consideration. Physical coordinates to voxel coordinates are preserved in
  // the conversion.
  static LabelMapType::Pointer
  VolumeNodeToItkImage(vtkMRMLScalarVolumeNode *inVolumeNode,
                       bool applyRasToWorld=true,
                       bool applyRasToLps=true);

  // Description:
  // This function converts the vtkImageData
  // in a itkImage. The data must be type 'short'. This function does not make
  // any copy of the data, so the original imageData holder must have this into
  // consideration. Physical coordinates to voxel coordinates are NOT prserved
  // unless they are provided.
  static LabelMapType::Pointer
  vtkImageDataToItkImage(vtkImageData *inImageData,
                         vtkMatrix4x4 *inToRasMatrix=NULL,
                         vtkMatrix4x4 *inToWorldMatrix=NULL,
                         vtkMatrix4x4 *inRasToLpsMatrix=NULL);

  // Description:
  // This function converts itkImage data to vtkImageData. The data must be type
  // 'short'. This function does not make any copy of the data so the original
  // itk data holder must have this into consideration. Physical coordinates to
  // voxel coordinates are NOT preseved, since vtkImageData does not consider
  // this information.
  static vtkSmartPointer<vtkImageData>
  ConvertItkImageToVtkImageData(LabelMapType::Pointer itkImage);

  // Description:
  // This function converts itkImage dat to vtkMRMLScalarVolumeNode. The data
  // must be type 'short'. This function does not make any copy of the data.
  static vtkSmartPointer<vtkMRMLScalarVolumeNode>
  ConvertItkImageToVolumeNode(LabelMapType::Pointer itkImage,
                              bool applyRasToLps=true);

  // Description:
  // This function counts the number of voxels with a particular value in the image.
  static unsigned int CountVoxels(LabelMapType::Pointer itkImage,
                                  LabelMapType::RegionType region,
                                  short label);

  // Description:
  // Assuming a mass of values greater than 0 somewhere in the image, this
  // function computes the bounding box containing these objects.
  static LabelMapType::RegionType
  GetBoundingBox(LabelMapType::Pointer itkImage);

 protected:
  vtkLabelMapHelper();
  ~vtkLabelMapHelper();

 private:
  ConnectedThresholdType::Pointer ConnectedThresholdFilter;
};

#endif //SLICERLIVER_LIVERRESECTIONS_LOGIC_VTKLABELMAPHELPER_H_

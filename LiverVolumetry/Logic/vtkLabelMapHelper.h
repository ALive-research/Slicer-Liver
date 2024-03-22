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
  Hospital and NTNU) and Ruoyan Meng (NTNU), and was supported by The
  Research Council of Norway through the ALive project (grant nr. 311393).

  ==============================================================================*/

#ifndef SLICERLIVER_LIVERRESECTIONS_LOGIC_VTKLABELMAPHELPER_H_
#define SLICERLIVER_LIVERRESECTIONS_LOGIC_VTKLABELMAPHELPER_H_

#include "vtkSlicerLiverVolumetryModuleLogicExport.h"

// ITK includes
#include <itkImage.h>
#include <itkConnectedThresholdImageFilter.h>
#include <itkNeighborhoodConnectedImageFilter.h>

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
class VTK_SLICER_LIVERVOLUMETRY_MODULE_LOGIC_EXPORT
vtkLabelMapHelper: public vtkObject
{

 public:
  static vtkLabelMapHelper* New();
 vtkTypeMacro(vtkLabelMapHelper, vtkObject);
  void PrintSelf(ostream &os, vtkIndent indent) override;

  //Type definitions
  typedef itk::Image<short, 3> LabelMapType;
  typedef itk::ConnectedThresholdImageFilter<LabelMapType,LabelMapType> ConnectedThresholdType;
  typedef itk::NeighborhoodConnectedImageFilter<LabelMapType, LabelMapType> NeighborhoodConnectedThresholdType;

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

  LabelMapType::Pointer NeighborhoodConnectedThreshold(LabelMapType::Pointer itkImage,
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
                            unsigned short projectionValue);


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
  NeighborhoodConnectedThresholdType::Pointer  NeighborhoodConnectedThresholdFilter;

};

#endif //SLICERLIVER_LIVERRESECTIONS_LOGIC_VTKLABELMAPHELPER_H_

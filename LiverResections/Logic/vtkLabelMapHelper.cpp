/*===============================================================================

  Project: Slicer-LiverResectionPlannig
  Module: vtkLabelMapHelper.cxx

  Contributors:
  - Rafael Palomar <rafael.palomar@rr-research.no>

  Copyright (c) 2016, The Intervention Centre - Oslo University Hospital

  All rights reserved. This is propietary software. In no event shall
  the author be liable for any claim or damages.

  =============================================================================*/
#include "vtkLabelMapHelper.h"

// MRML includes
#include <vtkMRMLScalarVolumeNode.h>
#include <vtkMRMLTransformNode.h>

//ITK includes
#include <itkImportImageFilter.h>
#include <itkNeighborhoodIterator.h>
#include <itkImageMaskSpatialObject.h>
#include <itkCastImageFilter.h>

//VTK includes
#include <vtkObjectFactory.h>
#include <vtkMatrix4x4.h>
#include <vtkTransform.h>
#include <vtkImageData.h>
#include <vtkSmartPointer.h>
#include <vtkPoints.h>
#include <vtkImageImport.h>

//------------------------------------------------------------------------------
vtkStandardNewMacro(vtkLabelMapHelper);

//------------------------------------------------------------------------------
vtkLabelMapHelper::vtkLabelMapHelper()
{
  this->ConnectedThresholdFilter = ConnectedThresholdType::New();
}

//------------------------------------------------------------------------------
vtkLabelMapHelper::~vtkLabelMapHelper()
{

}

//------------------------------------------------------------------------------
void vtkLabelMapHelper::PrintSelf(ostream &os, vtkIndent indent)
{

}

//------------------------------------------------------------------------------
vtkLabelMapHelper::LabelMapType::Pointer
vtkLabelMapHelper::
ConnectedThreshold(vtkLabelMapHelper::LabelMapType::Pointer itkImage,
                   unsigned short lowerBound,
                   unsigned short upperBound,
                   unsigned short replacementValue,
                   vtkLabelMapHelper::LabelMapType::IndexType seedIndex)
{
  this->ConnectedThresholdFilter->SetInput(itkImage);
  this->ConnectedThresholdFilter->SetLower(lowerBound);
  this->ConnectedThresholdFilter->SetUpper(upperBound);
  this->ConnectedThresholdFilter->SetReplaceValue(replacementValue);
  this->ConnectedThresholdFilter->SetSeed(seedIndex);
  this->ConnectedThresholdFilter->SetConnectivity(ConnectedThresholdType::FaceConnectivity);
  this->ConnectedThresholdFilter->Update();

  return this->ConnectedThresholdFilter->GetOutput();
}

//------------------------------------------------------------------------------
unsigned int
vtkLabelMapHelper::
ProjectPointsOntoItkImage(vtkLabelMapHelper::LabelMapType::Pointer itkImage,
                          vtkPoints *points,
                          unsigned short projectionValue,
                          unsigned int radius)
{
  // Check for null pointers
  if (itkImage.IsNull())
    {
    std::cerr << "ProjectPointsOntoItkImage: itkImage null pointer"
              << std::endl;
    return 0;
    }
  if (points == NULL)
    {
    std::cerr << "ProjectPointsOntoItkImage: vtkPoints null pointer"
              << std::endl;
    return 0;
    }

  vtkLabelMapHelper::LabelMapType::IndexType index;
  vtkLabelMapHelper::LabelMapType::PointType point;
  vtkLabelMapHelper::LabelMapType::SizeType _radius = {1,1,1};
  typedef itk::NeighborhoodIterator<vtkLabelMapHelper::LabelMapType>
      NeighborhoodIterator;

  NeighborhoodIterator neighborhoodIterator(_radius,
                                            itkImage,
                                            itkImage->GetRequestedRegion());

  unsigned int projectedPoints = 0;
  for(unsigned int i=0; i<points->GetNumberOfPoints(); ++i)
    {
    double coordinates[3];
    points->GetPoint(i, coordinates);
    point[0] = coordinates[0];
    point[1] = coordinates[1];
    point[2] = coordinates[2];

    if (itkImage->TransformPhysicalPointToIndex(point, index))
      {
      ++projectedPoints;
      itkImage->SetPixel(index, projectionValue);
      neighborhoodIterator.SetLocation(index);

      for(unsigned int i =0; i<27; i++)
        {
        bool isInBounds;
        neighborhoodIterator.GetPixel(i, isInBounds);
        if (isInBounds)
          {
          neighborhoodIterator.SetPixel(i, projectionValue);
          }
        }
      }
    }

  return projectedPoints;
}

//------------------------------------------------------------------------------
vtkLabelMapHelper::LabelMapType::Pointer
vtkLabelMapHelper::VolumeNodeToItkImage(vtkMRMLScalarVolumeNode *inVolumeNode,
                                        bool applyRasToWorld,
                                        bool applyRasToLps)
{
  // Check for null pointer
  if (inVolumeNode == NULL)
    {
    std::cerr
        << "VolumeNodetoItkImage: Pointer to vtkMRMLScalarVolumeNode is NULL"
        << std::endl;
    throw 0;
    }

  // Obtain IJK to RAS matrix
  vtkSmartPointer<vtkMatrix4x4> inVolumeToRasTransformMatrix =
      vtkSmartPointer<vtkMatrix4x4>::New();
  inVolumeNode->GetIJKToRASMatrix(inVolumeToRasTransformMatrix);

// Obtain RAS to World transform matrix
  vtkSmartPointer<vtkMatrix4x4> rasToWorldTransformMatrix = 0;

  if (applyRasToWorld)
    {
    rasToWorldTransformMatrix = vtkSmartPointer<vtkMatrix4x4>::New();
    vtkMRMLTransformNode *inTransformNode = inVolumeNode->GetParentTransformNode();
    if (inTransformNode != NULL)
      {
      if (!inTransformNode->IsTransformToWorldLinear())
        {
        std::cerr
            <<  "VolumeNodeToItkImage: world transform is not linear"
            << std::endl;
        throw NULL;
        }
      inTransformNode->GetMatrixTransformToWorld(rasToWorldTransformMatrix);
      }
    }

  // Obtain RSAS to LPS matrix
  vtkSmartPointer<vtkMatrix4x4> rasToLpsTransformMatrix = 0;
  if (applyRasToLps)
    {
    rasToLpsTransformMatrix = vtkSmartPointer<vtkMatrix4x4>::New();
    rasToLpsTransformMatrix->SetElement(0,0,-1.0);
    rasToLpsTransformMatrix->SetElement(1,1,-1.0);
    rasToLpsTransformMatrix->SetElement(2,2, 1.0);
    rasToLpsTransformMatrix->SetElement(3,3, 1.0);
    }

  vtkLabelMapHelper::LabelMapType::Pointer outItkImage =
      vtkLabelMapHelper::vtkImageDataToItkImage(inVolumeNode->GetImageData(),
                                                inVolumeToRasTransformMatrix,
                                                rasToWorldTransformMatrix,
                                                rasToLpsTransformMatrix);

  return outItkImage;
}

//------------------------------------------------------------------------------
vtkLabelMapHelper::LabelMapType::Pointer
vtkLabelMapHelper::vtkImageDataToItkImage(vtkImageData *inImageData,
                                          vtkMatrix4x4 *inToRasMatrix,
                                          vtkMatrix4x4 *rasToWorldMatrix,
                                          vtkMatrix4x4 *rasToLpsMatrix)
{
  // Check for null pointer
  if (inImageData == NULL)
    {
    std::cerr
        << "vtkImageDataToItkImage: Pointer to vtkImageData is NULL"
        << std::endl;
    throw NULL;
    }

  // Check for datatype
  if (sizeof(short) != inImageData->GetScalarSize())
    {
    std::cerr
        << "vtkImageDataToItkImage: input datatype is not VTK_SHORT"
        << std::endl;;
    throw NULL;
    }

  typedef itk::ImportImageFilter<short, 3> ImportFilterType;
  ImportFilterType::Pointer importFilter = ImportFilterType::New();

  // Set orientation (if transformations are given)
  vtkSmartPointer<vtkTransform> coordinatesTransform =
      vtkSmartPointer<vtkTransform>::New();
  coordinatesTransform->Identity();
  coordinatesTransform->PostMultiply();

  // Check for transforms
  if (inToRasMatrix != NULL)
    {
    coordinatesTransform->Concatenate(inToRasMatrix);
    }
  if (rasToWorldMatrix != NULL)
    {
    coordinatesTransform->Concatenate(rasToWorldMatrix);
    }
  if (rasToLpsMatrix != NULL)
    {
    coordinatesTransform->Concatenate(rasToLpsMatrix);
    }

  // Set image spacing
  double spacing[3]={0.0};
  coordinatesTransform->GetScale(spacing);
  if (rasToLpsMatrix != NULL)
    {
    spacing[0] = spacing[0] < 0 ? -spacing[0] : spacing[0];
    spacing[1] = spacing[1] < 0 ? -spacing[1] : spacing[1];
    spacing[2] = spacing[2] < 0 ? -spacing[2] : spacing[2];
    }
  importFilter->SetSpacing(spacing);

  // Set image origin
  double origin[3]={0.0};
  coordinatesTransform->GetPosition(origin);
  importFilter->SetOrigin(origin);

  // Set direction
  vtkSmartPointer<vtkMatrix4x4> inVolumeToWorldTransformMatrix =
      vtkSmartPointer<vtkMatrix4x4>::New();
  coordinatesTransform->GetMatrix(inVolumeToWorldTransformMatrix);

  itk::Matrix<double,3,3> directionMatrix;
  unsigned int col = 0;
  for (col=0; col<3; col++)
    {
    double len = 0;
    unsigned int row = 0;
    for (row=0; row<3; row++)
      {
      len += inVolumeToWorldTransformMatrix->GetElement(row, col) *
          inVolumeToWorldTransformMatrix->GetElement(row, col);
      }
    if (len == 0.0)
      {
      len = 1.0;
      }
    len = sqrt(len);
    for (row=0; row<3; row++)
      {
      directionMatrix[row][col] =
          inVolumeToWorldTransformMatrix->GetElement(row, col)/len;
      }
    }
  importFilter->SetDirection(directionMatrix);

  // Set image extent
  int extent[6] = {0};
  inImageData->GetExtent(extent);
  vtkLabelMapHelper::LabelMapType::SizeType inSize;
  inSize[0] = extent[1] - extent[0] + 1;
  inSize[1] = extent[3] - extent[2] + 1;
  inSize[2] = extent[5] - extent[4] + 1;
  vtkLabelMapHelper::LabelMapType::IndexType start = {0};
  vtkLabelMapHelper::LabelMapType::RegionType region;
  region.SetSize(inSize);
  region.SetIndex(start);
  importFilter->SetRegion(region);

  // Import (itk filter will not have ownership of memory!)
  short *pointerToData = static_cast<short*>(inImageData->GetScalarPointer());
  unsigned int dataSize = inSize[0] * inSize[1] * inSize[2];
  importFilter->SetImportPointer(pointerToData, dataSize, false);
  importFilter->Update();

  return importFilter->GetOutput();
}

//------------------------------------------------------------------------------
vtkSmartPointer<vtkImageData>
vtkLabelMapHelper::ConvertItkImageToVtkImageData(vtkLabelMapHelper::LabelMapType::Pointer itkImage)
{
  vtkLabelMapHelper::LabelMapType::RegionType region =
      itkImage->GetBufferedRegion();
  vtkLabelMapHelper::LabelMapType::SizeType imageSize =
      region.GetSize();
  vtkLabelMapHelper::LabelMapType::SpacingType imageSpacing =
      itkImage->GetSpacing();
  vtkLabelMapHelper::LabelMapType::PointType origin =
      itkImage->GetOrigin();

  int extent[6]={0, (int) imageSize[0]-1,
                 0, (int) imageSize[1]-1,
                 0, (int) imageSize[2]-1};

  vtkSmartPointer<vtkImageImport> imageImport =
      vtkSmartPointer<vtkImageImport>::New();

  imageImport->SetDataScalarType(VTK_SHORT);
  imageImport->SetNumberOfScalarComponents(1);
  imageImport->SetDataSpacing(1,1,1);
  imageImport->SetDataOrigin(0,0,0);
  imageImport->SetWholeExtent(extent);
  imageImport->SetDataExtentToWholeExtent();
  void *dataPointer =static_cast<void*>(itkImage->GetBufferPointer());
  imageImport->SetImportVoidPointer(dataPointer);
  imageImport->Update();

  vtkSmartPointer<vtkImageData> result = imageImport->GetOutput();

  return result;
}

//------------------------------------------------------------------------------
vtkSmartPointer<vtkMRMLScalarVolumeNode>
vtkLabelMapHelper::
ConvertItkImageToVolumeNode(vtkLabelMapHelper::LabelMapType::Pointer itkImage,
                            bool applyLpsToRas)
{
  if (itkImage.IsNull())
    {
    std::cerr << "ConvertItkImageToVolumeNode: itkImage empty pointer"
              << std::endl;
    return NULL;
    }

  vtkSmartPointer<vtkMRMLScalarVolumeNode> outVolumeNode =
      vtkSmartPointer<vtkMRMLScalarVolumeNode>::New();

// Get input image properties
  vtkLabelMapHelper::LabelMapType::RegionType itkRegion =
      itkImage->GetLargestPossibleRegion();
  vtkLabelMapHelper::LabelMapType::PointType itkOrigin =
      itkImage->GetOrigin();
  vtkLabelMapHelper::LabelMapType::SpacingType itkSpacing =
      itkImage->GetSpacing();
  vtkLabelMapHelper::LabelMapType::DirectionType itkDirections =
      itkImage->GetDirection();

  vtkSmartPointer<vtkImageData> outImageData =
      vtkLabelMapHelper::ConvertItkImageToVtkImageData(itkImage);

  if (!outImageData)
    {
    return NULL;
    }


  // Make image properties accessible for VTK
  double origin[3] = {itkOrigin[0], itkOrigin[1], itkOrigin[2]};
  double spacing[3] = {itkSpacing[0], itkSpacing[1], itkSpacing[2]};

  outVolumeNode->SetAndObserveImageData(outImageData);

  // Apply ITK geometry to volume node
  outVolumeNode->SetOrigin(origin);
  outVolumeNode->SetSpacing(spacing);

  double directions[3][3] = {{1.0,0.0,0.0},{0.0,1.0,0.0},{0.0,0.0,1.0}};
  for (unsigned int col=0; col<3; col++)
    {
    for (unsigned int row=0; row<3; row++)
      {
      directions[row][col] = itkDirections[row][col];
      }
    }
  outVolumeNode->SetIJKToRASDirections(directions);

  // Apply LPS to RAS conversion if requested
  if (applyLpsToRas)
    {
    //  LPS (ITK)to RAS (Slicer) transform matrix
    vtkSmartPointer<vtkMatrix4x4> lps2RasTransformMatrix =
        vtkSmartPointer<vtkMatrix4x4>::New();
    lps2RasTransformMatrix->SetElement(0,0,-1.0);
    lps2RasTransformMatrix->SetElement(1,1,-1.0);
    lps2RasTransformMatrix->SetElement(2,2, 1.0);
    lps2RasTransformMatrix->SetElement(3,3, 1.0);

    vtkSmartPointer<vtkMatrix4x4> outVolumeImageToLpsWorldTransformMatrix =
        vtkSmartPointer<vtkMatrix4x4>::New();
    outVolumeNode->GetIJKToRASMatrix(outVolumeImageToLpsWorldTransformMatrix);

    vtkSmartPointer<vtkTransform> imageToWorldTransform =
        vtkSmartPointer<vtkTransform>::New();
    imageToWorldTransform->Identity();
    imageToWorldTransform->PostMultiply();
    imageToWorldTransform->Concatenate(outVolumeImageToLpsWorldTransformMatrix);
    imageToWorldTransform->Concatenate(lps2RasTransformMatrix);

    outVolumeNode->SetIJKToRASMatrix(imageToWorldTransform->GetMatrix());
    }

  return outVolumeNode;
}

//-------------------------------------------------------------------------------
unsigned int
vtkLabelMapHelper::
CountVoxels(vtkLabelMapHelper::LabelMapType::Pointer inItkImage,
            vtkLabelMapHelper::LabelMapType::RegionType region,
            short label)
{

  unsigned int counter =0;
  inItkImage->SetRequestedRegion(region);
  typedef itk::ImageRegionConstIterator<itk::Image<short,3> >IteratorType;
  IteratorType iterator(inItkImage, inItkImage->GetRequestedRegion());
  while(!iterator.IsAtEnd())
    {
    if (iterator.Get() == label)
      {
      ++counter;
      }
    ++iterator;
    }

  return counter;
}

//-------------------------------------------------------------------------------
vtkLabelMapHelper::LabelMapType::RegionType
vtkLabelMapHelper::GetBoundingBox(vtkLabelMapHelper::LabelMapType::Pointer itkImage)
{
  typedef itk::Image<unsigned char,3> CastType;
  typedef itk::CastImageFilter<vtkLabelMapHelper::LabelMapType, CastType>
      CastFilterType;

  CastFilterType::Pointer castFilter = CastFilterType::New();
  castFilter->SetInput(itkImage);
  castFilter->Update();

  typedef itk::ImageMaskSpatialObject<3> ImageMaskSpatialObjectType;
  ImageMaskSpatialObjectType::Pointer imageMaskSpatialObject =
      ImageMaskSpatialObjectType::New();
  imageMaskSpatialObject->SetImage(castFilter->GetOutput());

  return imageMaskSpatialObject->GetAxisAlignedBoundingBoxRegion();
}

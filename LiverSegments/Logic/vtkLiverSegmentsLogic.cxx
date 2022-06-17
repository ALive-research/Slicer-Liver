 /*===============================================================================

   Project: LiverSegments
   Module: vtkSegmentClassificationLogic.cxx

   Copyright (c) 2019,  Oslo University Hospital

   All rights reserved. This is propietary software. In no event shall the author
   be liable for any claim or damages 

   ===============================================================================*/

#include "vtkLiverSegmentsLogic.h"

#include <vtkMRMLLabelMapVolumeNode.h>
#include <vtkMRMLSegmentationNode.h>
#include <vtkMRMLModelNode.h>

#include <vtkObjectFactory.h>
#include <vtkImageData.h>
#include <vtkImageIterator.h>
#include <vtkKdTreePointLocator.h>
#include <vtkPointSet.h>
#include <vtkPolyData.h>
#include <vtkPointData.h>
#include <vtkStringArray.h>
#include <vtkAppendPolyData.h>
#include <vtkOrientedImageData.h>
#include <vtkMatrix4x4.h>

#include <iostream>

//------------------------------------------------------------------------------
vtkStandardNewMacro(vtkLiverSegmentsLogic);

//------------------------------------------------------------------------------
vtkLiverSegmentsLogic::vtkLiverSegmentsLogic()
{

  std::cout << "vtkSegmentClassificationLogic Constructor" << std::endl;
  locator = vtkSmartPointer<vtkKdTreePointLocator>::New();
}

//------------------------------------------------------------------------------
vtkLiverSegmentsLogic::~vtkLiverSegmentsLogic()
{
  
}

//------------------------------------------------------------------------------
void vtkLiverSegmentsLogic::PrintSelf(ostream &os, vtkIndent indent)
{
  Superclass::PrintSelf(os, indent);
}

void vtkLiverSegmentsLogic::SegmentClassification(vtkPolyData *centerlines,
                                                          vtkMRMLLabelMapVolumeNode *labelMap)
{
  std::cout << "vtkSegmentClassificationLogic::SegmentClassification()" << std::endl;
  if (centerlines == nullptr)
    {
      std::cerr << "No centerlines polydata." << std::endl;
      return;
    }

  if (labelMap == nullptr)
    {
      std::cerr << "No label map defined." << std::endl;
      return;
    }

  auto pointData = centerlines->GetPointData();
  auto centerlineSegmentIDs = pointData->GetScalars();

  if(!centerlineSegmentIDs)
  {
      std::cerr << "No segmentIds in pointdata" << std::endl;
  }

  auto locator = vtkSmartPointer<vtkKdTreePointLocator>::New();
  locator->SetDataSet(dynamic_cast<vtkPointSet*>(centerlines));
  locator->BuildLocator();

}

void vtkLiverSegmentsLogic::markSegmentWithID(vtkMRMLModelNode *segment, int segmentId)
{
    vtkSmartPointer<vtkIntArray> idArray = vtkSmartPointer<vtkIntArray>::New();
    idArray->SetName("segmentId");
    vtkSmartPointer<vtkPolyData> polydata = segment->GetPolyData();
    int numberOfPoints = polydata->GetNumberOfPoints();
    for(int i=0;i<numberOfPoints;i++) {
        idArray->InsertNextValue(segmentId);
    }
    polydata->GetPointData()->SetScalars(idArray);
}

void vtkLiverSegmentsLogic::addSegmentToCenterlineModel(vtkMRMLModelNode *summedCenterline, vtkMRMLModelNode *segmentCenterline)
{
    vtkPolyData *segment = segmentCenterline->GetPolyData();
    vtkPolyData *centerlineModel = summedCenterline->GetPolyData();

    vtkSmartPointer<vtkPolyData> summedModel = vtkSmartPointer<vtkPolyData>::New();
    vtkSmartPointer<vtkAppendPolyData> appendFilter = vtkSmartPointer<vtkAppendPolyData>::New();
    appendFilter->AddInputData(centerlineModel);
    appendFilter->AddInputData(segment);
    summedModel = appendFilter->GetOutput();
    appendFilter->Update();

    summedCenterline->SetAndObservePolyData(summedModel);
}

int vtkLiverSegmentsLogic::SegmentClassificationProcessing(vtkMRMLModelNode *centerlineModel, vtkMRMLLabelMapVolumeNode *labelMap)
{
//    vtkSmartPointer<vtkOrientedImageData> liverMap = vtkSmartPointer<vtkOrientedImageData>::New();
//    segmentation->GetBinaryLabelmapRepresentation(Id, liverMap);
     //    vtkSmartPointer<vtkImageData> image = liverMap->GetImageData();
    vtkSmartPointer<vtkMatrix4x4> ijkToRas = vtkSmartPointer<vtkMatrix4x4>::New();
    labelMap->GetIJKToRASMatrix(ijkToRas);

    vtkSmartPointer<vtkPolyData> centerlinePolyData = centerlineModel->GetPolyData();
    vtkSmartPointer<vtkPointData> pointData = centerlinePolyData->GetPointData();

    vtkSmartPointer<vtkIntArray> centerlineSegmentIDs = vtkIntArray::SafeDownCast(pointData->GetScalars());

    if(centerlineSegmentIDs == nullptr) {
        std::cout << "No PointData in Model" << std::endl;
        return -1;
    }

    vtkSmartPointer<vtkImageData> imageData = labelMap->GetImageData();
    const char* scalarType = imageData->GetScalarTypeAsString();
    std::cout << "Scalar type : " << scalarType[0] << scalarType[1] << scalarType[2] <<
              scalarType[3] << scalarType[4] << std::endl;
    int dims[3];
    imageData->GetDimensions(dims);
    std::cout << "Liver Image data dimensions : " << dims[0] << ", " << dims[1] << ", " << dims[2]  << std::endl;
    int extent[6];
    imageData->GetExtent(extent);
    std::cout << "Liver Image data extent : [ " << extent[0] << ", " << extent[1] << ", " << extent[2] << ", " << extent[3]
              << ", " << extent[4] << ", " << extent[5] << "]" << std::endl;

    for (int z=extent[4]; z<=extent[5]; z++)
        for(int y=extent[2]; y<=extent[3]; y++)
            for(int x=extent[0]; x<=extent[1]; x++)
            {
                short *label = (short*)imageData->GetScalarPointer(x,y,z);
                if(*label==1) {
                    double position_IJK[4];
                    position_IJK[0] = static_cast<double>(x);
                    position_IJK[1] = static_cast<double>(y);
                    position_IJK[2] = static_cast<double>(z);
                    position_IJK[3] = 1.0f;
                    double position_RAS[4];
                    ijkToRas->MultiplyPoint(position_IJK, position_RAS);
                    double vtkVoxelPoint[3] = {position_RAS[0], position_RAS[1], position_RAS[2]};
                    double vtkCenterlinePoint[3];
                    vtkIdType id = this->locator->FindClosestPoint(vtkVoxelPoint);
                    centerlinePolyData->GetPoint(id, vtkCenterlinePoint);
                    int index = centerlineSegmentIDs->GetTuple1(id);
                    *label = centerlineSegmentIDs->GetTuple1(id);
                }
            }

    return 0;
}

void vtkLiverSegmentsLogic::initializeCenterlineSearchModel(vtkMRMLModelNode *summedCenterline)
{
    vtkPolyData *centerlineModel = summedCenterline->GetPolyData();
    locator->SetDataSet(dynamic_cast<vtkPointSet*>(centerlineModel));
    locator->BuildLocator();
}



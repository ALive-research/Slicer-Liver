 /*===============================================================================

   Project: LiverSegments
   Module: vtkSegmentClassificationLogic.cxx

   Copyright (c) 2019,  Oslo University Hospital

   All rights reserved. This is propietary software. In no event shall the author
   be liable for any claim or damages 

   ===============================================================================*/

#include "vtkSegmentClassificationLogic.h"

#include <vtkMRMLLabelMapVolumeNode.h>
#include <vtkMRMLSegmentationNode.h>
#include <vtkMRMLModelNode.h>>

#include <vtkObjectFactory.h>
#include <vtkImageData.h>
#include <vtkImageIterator.h>
#include <vtkKdTreePointLocator.h>
#include <vtkPointSet.h>
#include <vtkPolyData.h>
//#include <vtkCellData.h>
#include <vtkPointData.h>
//#include <vtkIntArray.h>
#include <vtkStringArray.h>
#include <vtkAppendPolyData.h>
#include <vtkOrientedImageData.h>

#include <itkImage.h>
#include <itkImageFileWriter.h>
#include <itkImageRegionIteratorWithIndex.h>

#include <iostream>

//------------------------------------------------------------------------------
vtkStandardNewMacro(vtkSegmentClassificationLogic);

//------------------------------------------------------------------------------
vtkSegmentClassificationLogic::vtkSegmentClassificationLogic()
{

  std::cout << "vtkSegmentClassificationLogic Constructor" << std::endl;
  centerlineModel = vtkSmartPointer<vtkPolyData>::New();
}

//------------------------------------------------------------------------------
vtkSegmentClassificationLogic::~vtkSegmentClassificationLogic()
{
  
}

//------------------------------------------------------------------------------
void vtkSegmentClassificationLogic::PrintSelf(ostream &os, vtkIndent indent)
{
  Superclass::PrintSelf(os, indent);
}

void vtkSegmentClassificationLogic::SegmentClassification(vtkPolyData *centerlines,
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
  auto centerlineSegmentIDs = pointData->GetAbstractArray("segmentID");

  if(!centerlineSegmentIDs)
  {
      std::cerr << "No segmentIds in pointdata" << std::endl;
  }

  auto KDTree = vtkSmartPointer<vtkKdTreePointLocator>::New();
  KDTree->SetDataSet(dynamic_cast<vtkPointSet*>(centerlines));
  KDTree->BuildLocator();

//  auto cells = vtkSmartPointer<vtkIdList>::New();

//  // ITK Objects
//  typedef itk::Image<short, 3> LabelMapType;
//  typedef itk::ImageRegionIteratorWithIndex<LabelMapType> LabelMapIteratorType;

//  LabelMapType::Pointer labelMap = LabelMapType::New();


//  // Conversion vtkMRMLLabelMapVolumeNode --> ITKImage
////  LabelMapHelper::ConvertLabelMapVolumeNodeToItkImage(inputLabelMap,
////						      labelMap,
////						      true, false);

//  // Get the ID of the different points in the array
//  auto cellData = centerlines->GetCellData();
//  if (cellData == nullptr)
//    {
//      std::cerr << "No cell data ssociated to the polydata." << std::endl;
//      return;
//    }

//  auto groupIds = vtkIntArray::SafeDownCast(cellData->GetArray("GroupIds"));
//  if (groupIds == nullptr)
//    {
//      std::cerr << "No GroupIds array found in cell data." << std::endl;
//      return;
//    }
  
//  LabelMapIteratorType labelMapIt(labelMap, labelMap->GetRequestedRegion());
//  LabelMapType::IndexType index;
//  LabelMapType::PointType point;

//  // Segments classification loop
//  labelMapIt.GoToBegin();

//  while(!labelMapIt.IsAtEnd())
//    {

//      if (labelMapIt.Get())
//	{
//	  index = labelMapIt.GetIndex();
//	  labelMap->TransformIndexToPhysicalPoint(index, point);

//	  double vtkpoint[3] = {point[0], point[1], point[2]};

//	  vtkIdType id = KDTree->FindClosestPoint(vtkpoint);
//	  centerlines->GetPointCells(id, cells.GetPointer());
//	  labelMapIt.Set(static_cast<short>(groupIds->GetTuple(cells->GetId(0))[0])+1);
//	}
      
//      ++labelMapIt;
//    }


  // Conversion ITKImage --> vtkMRMLLabelMapVolumeNode
//  LabelMapHelper::ConvertItkImageToLabelMapVolumeNode(labelMap,
//  						      outputLabelMap,
//  						      VTK_SHORT,
//						      true, false);

  // typedef itk::ImageFileWriter<LabelMapType> LabelMapFileWriter;
  // LabelMapFileWriter::Pointer writer = LabelMapFileWriter::New();
  // writer->SetInput(labelMap);
  // writer->SetFileName("/tmp/a.nrrd");
  // writer->Update();
}

void vtkSegmentClassificationLogic::markSegmentWithID(vtkMRMLModelNode *segment, int segmentId)
{
    vtkSmartPointer<vtkIntArray> idArray = vtkSmartPointer<vtkIntArray>::New();
    idArray->SetName("segmentId");
    vtkSmartPointer<vtkPolyData> polydata = segment->GetPolyData();
    int numberOfPoints = polydata->GetNumberOfPoints();
    for(int i=0;i<numberOfPoints;i++) {
        idArray->InsertNextTuple1(segmentId);
    }
    polydata->GetPointData()->AddArray(idArray);
}

void vtkSegmentClassificationLogic::addSegmentToCenterlineModel(vtkMRMLModelNode *summedCenterline, vtkMRMLModelNode *segmentCenterline)
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

int vtkSegmentClassificationLogic::SegmentClassificationProcessing(vtkMRMLLabelMapVolumeNode *labelMap)
{
//    vtkSmartPointer<vtkOrientedImageData> liverMap = vtkSmartPointer<vtkOrientedImageData>::New();
//    segmentation->GetBinaryLabelmapRepresentation(Id, liverMap);
     //    vtkSmartPointer<vtkImageData> image = liverMap->GetImageData();
    int p=0;
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
                    p=p+1;
                    *label = 2;
                }
            }

    std::cout << "Number of labelvalues: " << p << std::endl;
    return 0;
}



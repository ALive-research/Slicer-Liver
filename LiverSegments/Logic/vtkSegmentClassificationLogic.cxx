 /*===============================================================================

   Project: LiverSegments
   Module: vtkSegmentClassificationLogic.cxx

   Copyright (c) 2019,  Oslo University Hospital

   All rights reserved. This is propietary software. In no event shall the author
   be liable for any claim or damages 

   ===============================================================================*/

#include "vtkSegmentClassificationLogic.h"

#include <vtkMRMLLabelMapVolumeNode.h>

#include <vtkObjectFactory.h>
#include <vtkImageData.h>
#include <vtkImageIterator.h>
#include <vtkKdTreePointLocator.h>
#include <vtkPointSet.h>
#include <vtkPolyData.h>
#include <vtkCellData.h>
#include <vtkIntArray.h>

#include <itkImage.h>
#include <itkImageFileWriter.h>
#include <itkImageRegionIteratorWithIndex.h>

#include <iostream>

//------------------------------------------------------------------------------
vtkStandardNewMacro(vtkSegmentClassificationLogic);

//------------------------------------------------------------------------------
vtkSegmentClassificationLogic::vtkSegmentClassificationLogic()
{

  std::cout << "Testing !!" << std::endl;
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
  centerlines->Print(std::cout);

  if (labelMap == nullptr)
    {
      std::cerr << "No label map defined." << std::endl;
      return;
    }

//  // VTK objects
//  auto KDTree = vtkSmartPointer<vtkKdTreePointLocator>::New();
//  KDTree->SetDataSet(dynamic_cast<vtkPointSet*>(centerlines));
//  KDTree->BuildLocator();

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


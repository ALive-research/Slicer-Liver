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


#include "vtkLiverVolumetryLogic.h"
#include "vtkLabelMapHelper.h"
#include <vtkBezierSurfaceSource.h>

#include <vtkMRMLSegmentationNode.h>
#include <vtkMRMLMarkupsFiducialNode.h>
#include <vtkMRMLTableNode.h>
#include <vtkMRMLLabelMapVolumeNode.h>
#include <vtkMRMLScene.h>
#include <vtkMRMLScalarVolumeNode.h>
#include <vtkMRMLMarkupsBezierSurfaceNode.h>

#include <vtkImageToImageStencil.h>
#include <vtkObjectFactory.h>
#include <vtkImageData.h>
#include <vtkImageIterator.h>
#include <vtkPointSet.h>
#include <vtkPointData.h>
#include <vtkStringArray.h>
#include <vtkMatrix4x4.h>
#include <vtkIntArray.h>
#include <vtkImageThreshold.h>
#include <vtkImageAccumulate.h>
#include <vtkOrientedImageData.h>
#include <iostream>

//------------------------------------------------------------------------------
vtkStandardNewMacro(vtkLiverVolumetryLogic);

//------------------------------------------------------------------------------
vtkLiverVolumetryLogic::vtkLiverVolumetryLogic()
{
}

//------------------------------------------------------------------------------
vtkLiverVolumetryLogic::~vtkLiverVolumetryLogic()
{
}

void vtkLiverVolumetryLogic::PrintSelf(ostream &os, vtkIndent indent)
{
  Superclass::PrintSelf(os, indent);
}

void vtkLiverVolumetryLogic::ComputeAdvancedPlanningVolumetry(vtkMRMLLabelMapVolumeNode* SelectedSegmentsLabelMap, vtkMRMLTableNode* OutputTableNode, vtkMRMLMarkupsFiducialNode* ROIMarkersList, vtkCollection* ResectionNodes, double TargetSegmentationVolume){

  vtkLabelMapHelper::LabelMapType::Pointer TargetSegmentsITKImage;
  int baseValue = 100;
  double spacing[3];
  SelectedSegmentsLabelMap->GetSpacing(spacing);

  if (!OutputTableNode)
    {
    vtkErrorMacro(<< "No output table node is assigned,"
                    << "create and choose a table node first");
    return;
    }

  if (ResectionNodes){
    // Project SelectedSegmentsLabelMap from vtkImage to itkImage
    // need deep copy the label map

    auto LabelRetrievingOnly = vtkLabelMapHelper::VolumeNodeToItkImage(SelectedSegmentsLabelMap, true, false);

    auto TargetSegmentImageDataCopy = vtkSmartPointer<vtkImageData>::New();
    TargetSegmentImageDataCopy->DeepCopy(SelectedSegmentsLabelMap->GetImageData());
    auto TargetSegmentLabelMapCopy = vtkSmartPointer<vtkMRMLLabelMapVolumeNode>::New();
    TargetSegmentLabelMapCopy->CopyOrientation(SelectedSegmentsLabelMap);
    TargetSegmentLabelMapCopy->SetAndObserveImageData(TargetSegmentImageDataCopy);

    GetResectionsProjectionITKImage(TargetSegmentLabelMapCopy, ResectionNodes, baseValue);

    // region growing for every point in the list
    if (ROIMarkersList){
      int TotalCount = 0;
      vtkSmartPointer<vtkLabelMapHelper> labelMapHelper = vtkSmartPointer<vtkLabelMapHelper>::New();
      for(int i = 0; i<ROIMarkersList->GetNumberOfControlPoints();i++){
        double point[3];
        ROIMarkersList->GetNthControlPointPosition(i, point);
        auto pointLabel = ROIMarkersList->GetNthControlPointLabel(i);
        this->connectedThreshold = nullptr;
        if(this->resectionNodes != nullptr)
          {
          auto seedIndex = GetITKRGSeedIndex(point, LabelRetrievingOnly);
          int LabelValue = LabelRetrievingOnly->GetPixel(seedIndex);
          this->connectedThreshold = labelMapHelper->ConnectedThreshold(this->ProjectedTargetSegmentImage, 1, baseValue-1, baseValue+i, seedIndex);

          typedef itk::ImageRegionConstIterator<itk::Image<short, 3> > IteratorType;
          IteratorType iterator(LabelRetrievingOnly, LabelRetrievingOnly->GetRequestedRegion());
          int CountValues = 0;
          while (!iterator.IsAtEnd())
            {
            auto index = iterator.GetIndex();
            if (iterator.Get() != 0)
              {
              if (this->connectedThreshold->GetPixel(index) == baseValue+i && LabelRetrievingOnly->GetPixel(index) == LabelValue)
                {
                CountValues++;
                }
              }
            ++iterator;
            }
          auto ROIVolume = CountValues*spacing[0]*spacing[1]*spacing[2]*0.001;
          VolumetryTable(pointLabel, TargetSegmentationVolume,CountValues, ROIVolume, OutputTableNode);
          TotalCount = TotalCount+CountValues;
          }
        }
      auto TotalROIVolume = TotalCount*spacing[0]*spacing[1]*spacing[2]*0.001;
      VolumetryTable("TotalVolume of List "+ std::string(ROIMarkersList->GetName()), TargetSegmentationVolume,TotalCount, TotalROIVolume, OutputTableNode);
      }
    }
}

vtkSmartPointer<vtkBezierSurfaceSource> vtkLiverVolumetryLogic::GenerateBezierSurface(int Res, vtkMRMLMarkupsBezierSurfaceNode* bezierSurfaceNode){
  if (!bezierSurfaceNode)
    {
    return nullptr;
    }
  auto Bezier = vtkSmartPointer<vtkBezierSurfaceSource>::New();
  Bezier->SetResolution(Res,Res);
  Bezier->SetNumberOfControlPoints(4,4);
  if (bezierSurfaceNode->GetNumberOfControlPoints() == 16)
    {
    auto BezierSurfaceControlPoints = vtkSmartPointer<vtkPoints>::New();
    for (int i=0; i<16; i++)
      {
      double point[3];
      bezierSurfaceNode->GetNthControlPointPosition(i,point);
      BezierSurfaceControlPoints->InsertNextPoint(static_cast<float>(point[0]),
                                                  static_cast<float>(point[1]),
                                                  static_cast<float>(point[2]));
      }
    Bezier->SetControlPoints(BezierSurfaceControlPoints);
    Bezier->Update();
    }
  return Bezier;
}

//get itkImage region growing seed index
itk::Index<3> vtkLiverVolumetryLogic::GetITKRGSeedIndex(double ROISeedPoint[3], itk::SmartPointer<itk::Image<short,3>> SourceImage){
  vtkSmartPointer<vtkLabelMapHelper> labelMapHelper = vtkSmartPointer<vtkLabelMapHelper>::New();
  vtkLabelMapHelper::LabelMapType::IndexType seedIndex;
  vtkLabelMapHelper::LabelMapType::PointType seedPoint;
  seedPoint[0] = ROISeedPoint[0];
  seedPoint[1] = ROISeedPoint[1];
  seedPoint[2] = ROISeedPoint[2];
  SourceImage->TransformPhysicalPointToIndex(seedPoint, seedIndex);
  return seedIndex;
}

void vtkLiverVolumetryLogic::VolumetryTable(std::string Properties, double TargetSegmentationVolume, int ROIVoxels, double ROIVolume, vtkMRMLTableNode *OutputTableNode){

  auto VolumeTable = OutputTableNode->GetTable();
  if(OutputTableNode->GetNumberOfColumns() == 0 ){
    auto LabelCol = vtkSmartPointer<vtkStringArray>::New();
    LabelCol->SetName("Properties");
    auto TargetSegmentationVolumeCol = vtkSmartPointer<vtkDoubleArray>::New();
    TargetSegmentationVolumeCol->SetName("Target Segmentation Volume");
    auto ROIVoxelsCol = vtkSmartPointer<vtkDoubleArray>::New();
    ROIVoxelsCol->SetName("ROI Voxels");
    auto ROIVolumeCol = vtkSmartPointer<vtkDoubleArray>::New();
    ROIVolumeCol->SetName("ROI Volume (cm3)");
    auto RemnantPercentageCol = vtkSmartPointer<vtkStringArray>::New();
    RemnantPercentageCol->SetName("ROI Percentage");

    LabelCol->InsertNextValue(Properties);
    TargetSegmentationVolumeCol->InsertNextValue(TargetSegmentationVolume);
    ROIVoxelsCol->InsertNextValue(ROIVoxels);
    ROIVolumeCol->InsertNextValue(ROIVolume);
    RemnantPercentageCol->InsertNextValue(std::to_string(ROIVolume/TargetSegmentationVolume * 100)+"%");

    auto VolumeTable = OutputTableNode->GetTable();
    VolumeTable->AddColumn(LabelCol);
    VolumeTable->AddColumn(TargetSegmentationVolumeCol);
    VolumeTable->AddColumn(ROIVoxelsCol);
    VolumeTable->AddColumn(ROIVolumeCol);
    VolumeTable->AddColumn(RemnantPercentageCol);
    }
  else
    {
    int line = OutputTableNode->GetNumberOfRows();
    VolumeTable->InsertRow(line);
    VolumeTable->GetColumn(0)->SetVariantValue(line, static_cast<vtkStdString>(Properties));
    VolumeTable->GetColumn(1)->SetVariantValue(line,TargetSegmentationVolume);
    VolumeTable->GetColumn(2)->SetVariantValue(line,ROIVoxels);
    VolumeTable->GetColumn(3)->SetVariantValue(line,ROIVolume);
    VolumeTable->GetColumn(4)->SetVariantValue(line,static_cast<vtkStdString>(std::to_string(ROIVolume/TargetSegmentationVolume * 100)+"%"));
    OutputTableNode->Modified();
    }
}

int vtkLiverVolumetryLogic::GetRes(vtkMRMLMarkupsBezierSurfaceNode* bezierSurfaceNode, double space[3], int Steps){
//BezierCurve computation inspired from https://medium.com/geekculture/2d-and-3d-b%C3%A9zier-curves-in-c-499093ef45a9

  std::vector<std::vector<int>> ControlPointsIndexs{{3,6,9,12},{0,5,10,15}};
  double ArcLength[2];

  for (int l = 0; l < 2; l++){
    auto DataArray = vtkSmartPointer<vtkDoubleArray>::New();
    DataArray->SetNumberOfComponents(3);
    DataArray->SetNumberOfTuples(Steps);
    ArcLength[l] = 0.0;
    std::vector<double> bezierCurveX;
    std::vector<double> bezierCurveY;
    std::vector<double> bezierCurveZ;
    std::vector<double> ControlPointsX;
    std::vector<double> ControlPointsY;
    std::vector<double> ControlPointsZ;

    for (unsigned int p = 0; p < ControlPointsIndexs[l].size();p++){
      double point[3];
      bezierSurfaceNode->GetNthControlPointPosition(ControlPointsIndexs[l][p],point);
      ControlPointsX.push_back(point[0]);
      ControlPointsY.push_back(point[1]);
      ControlPointsZ.push_back(point[2]);
      }

    for (int i=0; i<Steps; i++){
      double t, point[3];
      t = i / static_cast<double>(Steps - 1);
      point[0] = std::pow((1 - t), 3) * ControlPointsX[0] + 3 * std::pow((1 - t), 2) * t * ControlPointsX[1] + 3 * std::pow((1 - t), 1) * std::pow(t, 2) * ControlPointsX[2] + std::pow(t, 3) * ControlPointsX[3];
      point[1] = std::pow((1 - t), 3) * ControlPointsY[0] + 3 * std::pow((1 - t), 2) * t * ControlPointsY[1] + 3 * std::pow((1 - t), 1) * std::pow(t, 2) * ControlPointsY[2] + std::pow(t, 3) * ControlPointsY[3];
      point[2] = std::pow((1 - t), 3) * ControlPointsZ[0] + 3 * std::pow((1 - t), 2) * t * ControlPointsZ[1] + 3 * std::pow((1 - t), 1) * std::pow(t, 2) * ControlPointsZ[2] + std::pow(t, 3) * ControlPointsZ[3];
      DataArray->SetTuple(i, point);
      }

    for (int i=1; i<Steps; i++){
      double point0[3], point1[3];
      DataArray->GetTuple(i, point1);
      DataArray->GetTuple(i-1, point0);
      double len = sqrt(pow(point0[0]-point1[0], 2.0) + pow(point0[1]-point1[1], 2.0) + pow(point0[2]-point1[2], 2.0));
      ArcLength[l] = ArcLength[l] + len;
      }
    }

  double len = (ArcLength[0]>ArcLength[1]) ? ArcLength[0]:ArcLength[1];
  double min = std::min(space[0], space[1]);
  min = std::min(min, space[2]);
  int res = len/min;

  return res;
}

int vtkLiverVolumetryLogic::GetSegmentVoxels(vtkOrientedImageData *TargetSegmentLabelMap){
  if (TargetSegmentLabelMap){
    int labelValue = 1;
    int backgroundValue = 0;
    auto thresh = vtkSmartPointer<vtkImageThreshold>::New();
    thresh->SetInputData(TargetSegmentLabelMap);
    thresh->ThresholdByLower(0);
    thresh->SetInValue(backgroundValue);
    thresh->SetOutValue(labelValue);
    thresh->SetOutputScalarType(VTK_UNSIGNED_CHAR);
    thresh->Update();

    auto stencil = vtkSmartPointer<vtkImageToImageStencil>::New();
    stencil->SetInputData(thresh->GetOutput());
    stencil->ThresholdByUpper(labelValue);
    stencil->Update();

    auto stat = vtkSmartPointer<vtkImageAccumulate>::New();
    stat->SetInputData(thresh->GetOutput());
    stat->SetStencilData(stencil->GetOutput());
    stat->Update();

    return stat->GetVoxelCount();

    } else {
    return 0;
    }
}

std::vector<int> vtkLiverVolumetryLogic::GetROIPointsLabelValue(vtkMRMLLabelMapVolumeNode* SelectedSegmentsLabelMap, vtkMRMLMarkupsFiducialNode* ROIMarkersList){
  std::vector<int> re;
  vtkLabelMapHelper::LabelMapType::Pointer TargetSegmentsITKImage;
  // Project SelectedSegmentsLabelMap from vtkImage to itkImage
  // need deep copy the label map
  auto TargetSegmentImageDataCopy = vtkSmartPointer<vtkImageData>::New();
  TargetSegmentImageDataCopy->DeepCopy(SelectedSegmentsLabelMap->GetImageData());
  auto TargetSegmentLabelMapCopy = vtkSmartPointer<vtkMRMLLabelMapVolumeNode>::New();
  TargetSegmentLabelMapCopy->CopyOrientation(SelectedSegmentsLabelMap);
  TargetSegmentLabelMapCopy->SetAndObserveImageData(TargetSegmentImageDataCopy);
  TargetSegmentsITKImage = vtkLabelMapHelper::VolumeNodeToItkImage(TargetSegmentLabelMapCopy, true, false);


  if (ROIMarkersList){
    for(int i = 0; i<ROIMarkersList->GetNumberOfControlPoints();i++){
      double point[3];
      ROIMarkersList->GetNthControlPointPosition(i, point);
      auto seedIndex = GetITKRGSeedIndex(point, TargetSegmentsITKImage);
      int LabelValue = TargetSegmentsITKImage->GetPixel(seedIndex);
      re.push_back(LabelValue);
      }
    }

  return re;
}

void vtkLiverVolumetryLogic::GetResectionsProjectionITKImage(vtkMRMLLabelMapVolumeNode* TargetSegmentLabelMapCopy,vtkCollection* ResectionNodes, int baseValue){
  double spacing[3];
  TargetSegmentLabelMapCopy->GetSpacing(spacing);

  auto BezierHR = vtkSmartPointer<vtkBezierSurfaceSource>::New();
  if (this->resectionNodes != ResectionNodes && ResectionNodes != nullptr)
    {
    this->resectionNodes = ResectionNodes;
    for (int i = 0; i < this->resectionNodes->GetNumberOfItems(); i++)
      {
      auto bezierSurfaceNode = vtkMRMLMarkupsBezierSurfaceNode::SafeDownCast(this->resectionNodes->GetItemAsObject(i));
      auto Res =  GetRes(bezierSurfaceNode, spacing, 300);
      if(Res < 500){
        Res  =  500;
        }
      BezierHR = GenerateBezierSurface(Res, bezierSurfaceNode);
      if(i == 0){
        this->ProjectedTargetSegmentImage = vtkLabelMapHelper::VolumeNodeToItkImage(TargetSegmentLabelMapCopy, true, false);
        }
      vtkLabelMapHelper::ProjectPointsOntoItkImage(this->ProjectedTargetSegmentImage,
                                                   BezierHR->GetOutput()->GetPoints(),
                                                   baseValue);
      }
    }
}

void vtkLiverVolumetryLogic::GenerateSegmentsLabelMap(vtkMRMLLabelMapVolumeNode* SelectedSegmentsLabelMap, vtkMRMLLabelMapVolumeNode* GeneratedSegmentsNode,vtkCollection* ResectionNodes, vtkMRMLMarkupsFiducialNode* ROIMarkersList){
  auto ijkras = vtkSmartPointer<vtkMatrix4x4>::New();
  auto ImageOrigin = SelectedSegmentsLabelMap->GetOrigin();
  auto ImageSpacing = SelectedSegmentsLabelMap->GetSpacing();
  SelectedSegmentsLabelMap->GetIJKToRASDirectionMatrix(ijkras);
  GeneratedSegmentsNode->SetOrigin(ImageOrigin);
  GeneratedSegmentsNode->SetSpacing(ImageSpacing);
  GeneratedSegmentsNode->SetIJKToRASDirectionMatrix(ijkras);

  auto ROIlabelvalues = GetROIPointsLabelValue(SelectedSegmentsLabelMap, ROIMarkersList);

  auto SelectedImage = SelectedSegmentsLabelMap->GetImageData();
  auto Newlabelvalue = vtkSmartPointer<vtkIntArray>::New();
  Newlabelvalue->DeepCopy(SelectedImage->GetPointData()->GetArray(0));
  auto NewImage = vtkSmartPointer<vtkImageData>::New();
  NewImage->DeepCopy(SelectedImage);

  if (ResectionNodes){

    int baseValue = 100;
    auto LabelRetrievingOnly = vtkLabelMapHelper::VolumeNodeToItkImage(SelectedSegmentsLabelMap, true, false);

    auto TargetSegmentImageDataCopy = vtkSmartPointer<vtkImageData>::New();
    TargetSegmentImageDataCopy->DeepCopy(SelectedSegmentsLabelMap->GetImageData());
    auto TargetSegmentLabelMapCopy = vtkSmartPointer<vtkMRMLLabelMapVolumeNode>::New();
    TargetSegmentLabelMapCopy->CopyOrientation(SelectedSegmentsLabelMap);
    TargetSegmentLabelMapCopy->SetAndObserveImageData(TargetSegmentImageDataCopy);

    GetResectionsProjectionITKImage(TargetSegmentLabelMapCopy, ResectionNodes, baseValue);

    vtkSmartPointer<vtkLabelMapHelper> labelMapHelper = vtkSmartPointer<vtkLabelMapHelper>::New();
    for(int i = 0; i<ROIMarkersList->GetNumberOfControlPoints();i++){
      double point[3];
      ROIMarkersList->GetNthControlPointPosition(i, point);
      auto pointLabel = ROIMarkersList->GetNthControlPointLabel(i);
      this->connectedThreshold = nullptr;
      if(this->resectionNodes != nullptr)
        {
        auto seedIndex = GetITKRGSeedIndex(point, LabelRetrievingOnly);
        int LabelValue = LabelRetrievingOnly->GetPixel(seedIndex);
        this->connectedThreshold = labelMapHelper->ConnectedThreshold(this->ProjectedTargetSegmentImage, 1, baseValue-1, baseValue+i, seedIndex);

        int Count = 0;
        typedef itk::ImageRegionConstIterator<itk::Image<short, 3> > IteratorType;
        IteratorType iterator(LabelRetrievingOnly, LabelRetrievingOnly->GetRequestedRegion());
        while (!iterator.IsAtEnd())
          {
          auto index = iterator.GetIndex();
          if (iterator.Get() != 0)
            {
            if (this->connectedThreshold->GetPixel(index) == baseValue+i && LabelRetrievingOnly->GetPixel(index) == LabelValue){
              Newlabelvalue->SetTuple1(Count,baseValue+i);
              } else if (Newlabelvalue->GetTuple1(Count) < baseValue) {
              Newlabelvalue->SetTuple1(Count,99);
              }
            }
          ++iterator;
          Count++;
          }
        }
      }
  } else {
    auto LabelValue = SelectedImage->GetPointData()->GetArray(0);
    for (int i = 0; i< LabelValue->GetNumberOfValues(); i ++){
      int v = static_cast<int>(LabelValue->GetTuple(i)[0]);
      if (std::find(ROIlabelvalues.begin(), ROIlabelvalues.end(), v) != ROIlabelvalues.end() || v == 0) {
        Newlabelvalue->SetTuple1(i,v);
        } else {
        Newlabelvalue->SetTuple1(i,99);
        }
    }
  }
  NewImage->GetPointData()->SetScalars(Newlabelvalue);
  GeneratedSegmentsNode->SetAndObserveImageData(NewImage);
}

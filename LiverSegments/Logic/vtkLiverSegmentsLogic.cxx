 /*===============================================================================

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

   This file was originally developed by Ole V. Solberg, Geir A. Tangen, Javier
   Perez-de-Frutos (SINTEF, Norway) and Rafael Palomar (Oslo University
   Hospital) through the ALive project (grant nr. 311393).

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
  this->Locator = vtkSmartPointer<vtkKdTreePointLocator>::New();
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

void vtkLiverSegmentsLogic::MarkSegmentWithID(vtkMRMLModelNode *segment, int segmentId)
{
    auto idArray = vtkSmartPointer<vtkIntArray>::New();
    idArray->SetName("segmentId");
    auto polydata = segment->GetPolyData();
    int numberOfPoints = polydata->GetNumberOfPoints();
    for(int i=0;i<numberOfPoints;i++) {
        idArray->InsertNextValue(segmentId);
    }
    polydata->GetPointData()->SetScalars(idArray);
}

void vtkLiverSegmentsLogic::AddSegmentToCenterlineModel(vtkMRMLModelNode *summedCenterline, vtkMRMLModelNode *segmentCenterline)
{
    auto segment = segmentCenterline->GetPolyData();
    auto centerlineModel = summedCenterline->GetPolyData();

    auto summedModel = vtkSmartPointer<vtkPolyData>::New();
    auto appendFilter = vtkSmartPointer<vtkAppendPolyData>::New();
    appendFilter->AddInputData(centerlineModel);
    appendFilter->AddInputData(segment);
    summedModel = appendFilter->GetOutput();
    appendFilter->Update();

    summedCenterline->SetAndObservePolyData(summedModel);
}

int vtkLiverSegmentsLogic::SegmentClassificationProcessing(vtkMRMLModelNode *centerlineModel, vtkMRMLLabelMapVolumeNode *labelMap)
{
    auto ijkToRas = vtkSmartPointer<vtkMatrix4x4>::New();
    labelMap->GetIJKToRASMatrix(ijkToRas);

    auto centerlinePolyData = centerlineModel->GetPolyData();
    auto pointData = centerlinePolyData->GetPointData();

    auto centerlineSegmentIDs = vtkIntArray::SafeDownCast(pointData->GetScalars());

    if(centerlineSegmentIDs == nullptr) {
        std::cout << "Error: No PointData in centerline model" << std::endl;
        return 0;
    }

    auto imageData = labelMap->GetImageData();
    int extent[6];
    imageData->GetExtent(extent);

    for (int z=extent[4]; z<=extent[5]; z++)
        for(int y=extent[2]; y<=extent[3]; y++)
            for(int x=extent[0]; x<=extent[1]; x++)
            {
                auto label = static_cast<short*>(imageData->GetScalarPointer(x,y,z));
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
                    vtkIdType id = this->Locator->FindClosestPoint(vtkVoxelPoint);
                    centerlinePolyData->GetPoint(id, vtkCenterlinePoint);
                    *label = centerlineSegmentIDs->GetTuple1(id);
                }
            }

    return 1;
}

void vtkLiverSegmentsLogic::InitializeCenterlineSearchModel(vtkMRMLModelNode *summedCenterline)
{
    auto centerlineModel = summedCenterline->GetPolyData();
    this->Locator->Initialize();
    this->Locator->SetDataSet(vtkPointSet::SafeDownCast(centerlineModel));
    this->Locator->BuildLocator();
}



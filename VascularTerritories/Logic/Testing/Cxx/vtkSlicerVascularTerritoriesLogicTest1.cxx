/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2021-2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

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

  This file was originally developed by Ole Vegard Solberg (SINTEF, Norway)
  and was supported by The Research Council of Norway
  through the ALive project (grant nr. 311393).

==============================================================================*/

// Using vtkSlicerColorLogicTest1 as example

// MRMLLogic includes
#include "vtkSlicerVascularTerritoriesLogic.h"

// MRML includes
#include "vtkMRMLCoreTestingMacros.h"
#include "vtkMRMLScene.h"
#include <vtkMRMLLabelMapVolumeNode.h>
#include <vtkMRMLModelNode.h>

// VTK includes
#include "qMRMLWidget.h"
#include <vtkTestingOutputWindow.h>
#include <vtkSphereSource.h>
#include <vtkImageData.h>
#include <vtkCellData.h>
#include <vtkPointData.h>

// VascularTerritories includes
// #include "qSlicerVascularTerritoriesModule.h" //test to try to link to qSlicerVascularTerritoriesModule

// STD includes

using namespace vtkAddonTestingUtilities;
using namespace vtkMRMLCoreTestingUtilities;

//----------------------------------------------------------------------------
namespace
{
int TestDefaults();
int TestFunctionsWithNullInput();
int TestFunctionsWithDummyData();
} // namespace

int vtkSlicerVascularTerritoriesLogicTest1(int vtkNotUsed(argc), char* vtkNotUsed(argv)[])
{
  CHECK_EXIT_SUCCESS(TestDefaults());
  CHECK_EXIT_SUCCESS(TestFunctionsWithNullInput());
  CHECK_EXIT_SUCCESS(TestFunctionsWithDummyData());
  return EXIT_SUCCESS;
}
namespace
{

//----------------------------------------------------------------------------
int TestDefaults()
{
  vtkSlicerVascularTerritoriesLogic* vascularTerritoriesLogic = vtkSlicerVascularTerritoriesLogic::New();
  vascularTerritoriesLogic->Delete();
  return EXIT_SUCCESS;
}

int TestFunctionsWithNullInput()
{
  vtkSlicerVascularTerritoriesLogic* vascularTerritoriesLogic = vtkSlicerVascularTerritoriesLogic::New();

  vascularTerritoriesLogic->MarkSegmentWithID(nullptr, 0);
  vascularTerritoriesLogic->AddSegmentToCenterlineModel(nullptr, nullptr);
  vascularTerritoriesLogic->SegmentClassificationProcessing(nullptr, nullptr);
  vascularTerritoriesLogic->InitializeCenterlineSearchModel(nullptr);

  vtkNew<vtkMRMLScene> scene;
  vascularTerritoriesLogic->SetMRMLScene(scene);
  vascularTerritoriesLogic->calculateVascularTerritoryMap(nullptr, nullptr, nullptr, nullptr, nullptr);
  vascularTerritoriesLogic->preprocessAndDecimate(nullptr, nullptr);

  vascularTerritoriesLogic->Delete();
  return EXIT_SUCCESS;
}

int TestFunctionsWithDummyData()
{
  vtkSlicerVascularTerritoriesLogic* vascularTerritoriesLogic = vtkSlicerVascularTerritoriesLogic::New();
  int segmentId = 1;

  // Init segment
  vtkNew<vtkMRMLModelNode> segment;
  vtkNew<vtkSphereSource> source;
  segment->SetPolyDataConnection(source->GetOutputPort());

  // Create dummy data
  vtkNew<vtkImageData> dummyImageData;
  int size = 1;
  dummyImageData->SetExtent(0, size, 0, size, 0, size);
  dummyImageData->SetSpacing(1, 1, 1);
  dummyImageData->AllocateScalars(VTK_UNSIGNED_CHAR, 1);
  vtkPolyData* spherePolydata = source->GetOutput();

  // Init labelMap
  vtkNew<vtkMRMLLabelMapVolumeNode> labelMap;
  labelMap->SetAndObserveImageData(dummyImageData);

  vascularTerritoriesLogic->MarkSegmentWithID(segment, segmentId);
  vascularTerritoriesLogic->AddSegmentToCenterlineModel(segment, segment);
  vascularTerritoriesLogic->SegmentClassificationProcessing(segment, labelMap);
  vascularTerritoriesLogic->InitializeCenterlineSearchModel(segment);

  vtkNew<vtkMRMLScene> scene;
  vascularTerritoriesLogic->SetMRMLScene(scene);
  vascularTerritoriesLogic->calculateVascularTerritoryMap(nullptr, nullptr, nullptr, nullptr, nullptr);

  vtkSmartPointer<vtkPolyData> returnPolyData = vtkSmartPointer<vtkPolyData>::New();
  vascularTerritoriesLogic->preprocessAndDecimate(spherePolydata, returnPolyData);
  CHECK_BOOL(returnPolyData->GetNumberOfPoints() < spherePolydata->GetNumberOfPoints(), true);
  CHECK_BOOL(returnPolyData->GetNumberOfPolys() < spherePolydata->GetNumberOfPolys(), true);

  vascularTerritoriesLogic->Delete();

  return EXIT_SUCCESS;
}

} // namespace

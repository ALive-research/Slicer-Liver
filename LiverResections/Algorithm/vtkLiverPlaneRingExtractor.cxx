/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) Oslo University Hospital. All rights reserved.

==============================================================================*/

#include "vtkLiverPlaneRingExtractor.h"

// VTK includes
#include <vtkCellArray.h>
#include <vtkCutter.h>
#include <vtkInformation.h>
#include <vtkInformationVector.h>
#include <vtkNew.h>
#include <vtkObjectFactory.h>
#include <vtkPlane.h>
#include <vtkPoints.h>
#include <vtkPolyData.h>
#include <vtkPolyLine.h>
#include <vtkStripper.h>

vtkStandardNewMacro(vtkLiverPlaneRingExtractor);

//------------------------------------------------------------------------------
vtkLiverPlaneRingExtractor::vtkLiverPlaneRingExtractor()
{
  this->Origin[0] = 0.0;
  this->Origin[1] = 0.0;
  this->Origin[2] = 0.0;
  this->Normal[0] = 0.0;
  this->Normal[1] = 0.0;
  this->Normal[2] = 1.0;
  this->SetNumberOfInputPorts(1);
  this->SetNumberOfOutputPorts(1);
}

//------------------------------------------------------------------------------
vtkLiverPlaneRingExtractor::~vtkLiverPlaneRingExtractor() = default;

//------------------------------------------------------------------------------
void vtkLiverPlaneRingExtractor::PrintSelf(ostream &os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);
  os << indent << "Origin: (" << this->Origin[0] << ", "
     << this->Origin[1] << ", " << this->Origin[2] << ")\n";
  os << indent << "Normal: (" << this->Normal[0] << ", "
     << this->Normal[1] << ", " << this->Normal[2] << ")\n";
}

//------------------------------------------------------------------------------
int vtkLiverPlaneRingExtractor::FillInputPortInformation(int /*port*/,
                                                          vtkInformation *info)
{
  info->Set(vtkAlgorithm::INPUT_REQUIRED_DATA_TYPE(), "vtkPolyData");
  return 1;
}

//------------------------------------------------------------------------------
int vtkLiverPlaneRingExtractor::RequestData(vtkInformation *,
                                             vtkInformationVector **inputVector,
                                             vtkInformationVector *outputVector)
{
  vtkInformation *inInfo = inputVector[0]->GetInformationObject(0);
  vtkPolyData *target = vtkPolyData::SafeDownCast(
    inInfo->Get(vtkDataObject::DATA_OBJECT()));
  if (!target)
    {
    vtkErrorMacro(<< "Input target mesh is required.");
    return 0;
    }

  vtkNew<vtkPlane> plane;
  plane->SetOrigin(this->Origin);
  plane->SetNormal(this->Normal);

  vtkNew<vtkCutter> cutter;
  cutter->SetCutFunction(plane);
  cutter->SetInputData(target);
  cutter->GenerateTrianglesOff();
  cutter->Update();

  // Chain segments into ordered polylines.
  vtkNew<vtkStripper> stripper;
  stripper->SetInputConnection(cutter->GetOutputPort());
  stripper->JoinContiguousSegmentsOn();
  stripper->Update();

  vtkInformation *outInfo = outputVector->GetInformationObject(0);
  vtkPolyData *out = vtkPolyData::SafeDownCast(
    outInfo->Get(vtkDataObject::DATA_OBJECT()));
  vtkPolyData *strippedPoly = stripper->GetOutput();
  out->SetPoints(strippedPoly->GetPoints());
  out->SetLines(strippedPoly->GetLines());
  return 1;
}

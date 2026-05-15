/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) Oslo University Hospital. All rights reserved.

==============================================================================*/

#include "vtkLiverSpheroidRingExtractor.h"

// VTK includes
#include <vtkCutter.h>
#include <vtkInformation.h>
#include <vtkInformationVector.h>
#include <vtkNew.h>
#include <vtkObjectFactory.h>
#include <vtkPoints.h>
#include <vtkPolyData.h>
#include <vtkQuadric.h>
#include <vtkStripper.h>

vtkStandardNewMacro(vtkLiverSpheroidRingExtractor);

//------------------------------------------------------------------------------
vtkLiverSpheroidRingExtractor::vtkLiverSpheroidRingExtractor()
  : RadiusX(1.0)
  , RadiusY(1.0)
  , RadiusZ(1.0)
{
  this->Center[0] = 0.0;
  this->Center[1] = 0.0;
  this->Center[2] = 0.0;
  this->SetNumberOfInputPorts(1);
  this->SetNumberOfOutputPorts(1);
}

//------------------------------------------------------------------------------
vtkLiverSpheroidRingExtractor::~vtkLiverSpheroidRingExtractor() = default;

//------------------------------------------------------------------------------
void vtkLiverSpheroidRingExtractor::PrintSelf(ostream &os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);
  os << indent << "Center: (" << this->Center[0] << ", "
     << this->Center[1] << ", " << this->Center[2] << ")\n";
  os << indent << "Radii: (" << this->RadiusX << ", "
     << this->RadiusY << ", " << this->RadiusZ << ")\n";
}

//------------------------------------------------------------------------------
int vtkLiverSpheroidRingExtractor::FillInputPortInformation(int /*port*/,
                                                             vtkInformation *info)
{
  info->Set(vtkAlgorithm::INPUT_REQUIRED_DATA_TYPE(), "vtkPolyData");
  return 1;
}

//------------------------------------------------------------------------------
int vtkLiverSpheroidRingExtractor::RequestData(vtkInformation *,
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
  if (this->RadiusX <= 0.0 || this->RadiusY <= 0.0 || this->RadiusZ <= 0.0)
    {
    vtkErrorMacro(<< "Radii must be positive.");
    return 0;
    }

  // Quadric coefficients for the axis-aligned ellipsoid
  //   ((x-cx)/rx)^2 + ((y-cy)/ry)^2 + ((z-cz)/rz)^2 - 1 = 0
  // Expanding into vtkQuadric form
  //   a0 x^2 + a1 y^2 + a2 z^2 + 2 a3 xy + 2 a4 yz + 2 a5 xz +
  //   2 a6 x + 2 a7 y + 2 a8 z + a9 = 0
  // (the SetCoefficients API is documented in the vtkQuadric header
  // alongside the equation form above).
  const double inv2x = 1.0 / (this->RadiusX * this->RadiusX);
  const double inv2y = 1.0 / (this->RadiusY * this->RadiusY);
  const double inv2z = 1.0 / (this->RadiusZ * this->RadiusZ);
  const double cx = this->Center[0];
  const double cy = this->Center[1];
  const double cz = this->Center[2];
  vtkNew<vtkQuadric> quadric;
  quadric->SetCoefficients(
    inv2x,                       // a0 x^2
    inv2y,                       // a1 y^2
    inv2z,                       // a2 z^2
    0.0,                         // 2 a3 xy
    0.0,                         // 2 a4 yz
    0.0,                         // 2 a5 xz
    -inv2x * cx,                 // 2 a6 x   -> coefficient is -2 cx / rx^2
    -inv2y * cy,                 // 2 a7 y
    -inv2z * cz,                 // 2 a8 z
    inv2x * cx * cx + inv2y * cy * cy + inv2z * cz * cz - 1.0);  // a9

  vtkNew<vtkCutter> cutter;
  cutter->SetCutFunction(quadric);
  cutter->SetInputData(target);
  cutter->GenerateTrianglesOff();
  cutter->Update();

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

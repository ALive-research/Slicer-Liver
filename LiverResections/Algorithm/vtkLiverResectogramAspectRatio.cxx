/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

==============================================================================*/

#include "vtkLiverResectogramAspectRatio.h"

// VTK includes
#include <vtkObjectFactory.h>
#include <vtkPoints.h>

// STD includes
#include <cmath>

vtkStandardNewMacro(vtkLiverResectogramAspectRatio);

namespace
{
// Sum the Euclidean arc-length of the first edge that starts at flat
// index 0 and advances by ``stride`` for ``count`` samples.  The u-edge
// uses stride ``samplesV`` (row to row); the v-edge uses stride 1
// (column to column).
double EdgeArcLength(vtkPoints* points, vtkIdType stride, unsigned int count)
{
  double length = 0.0;
  double prev[3];
  points->GetPoint(0, prev);
  for (unsigned int k = 1; k < count; ++k)
  {
    double curr[3];
    points->GetPoint(stride * static_cast<vtkIdType>(k), curr);
    length += std::sqrt((prev[0] - curr[0]) * (prev[0] - curr[0]) + (prev[1] - curr[1]) * (prev[1] - curr[1]) + (prev[2] - curr[2]) * (prev[2] - curr[2]));
    prev[0] = curr[0];
    prev[1] = curr[1];
    prev[2] = curr[2];
  }
  return length;
}
} // namespace

//------------------------------------------------------------------------------
vtkLiverResectogramAspectRatio::vtkLiverResectogramAspectRatio() = default;

//------------------------------------------------------------------------------
vtkLiverResectogramAspectRatio::~vtkLiverResectogramAspectRatio() = default;

//------------------------------------------------------------------------------
void vtkLiverResectogramAspectRatio::ComputeAspectRatio(vtkPoints* sampledSurface, unsigned int samplesU, unsigned int samplesV, bool flexibleBoundary, double ratioOut[2])
{
  // Non-flexible boundary short-circuits to the isotropic answer (the
  // v1 else-branch).  This is also the square-domain answer.
  if (!flexibleBoundary)
  {
    ratioOut[0] = 1.0;
    ratioOut[1] = 1.0;
    return;
  }

  if (!sampledSurface || samplesU < 2 || samplesV < 2)
  {
    vtkGenericWarningMacro("vtkLiverResectogramAspectRatio::ComputeAspectRatio: "
                           "a sampled surface with at least 2x2 samples is "
                           "required; falling back to the isotropic {1, 1}.");
    ratioOut[0] = 1.0;
    ratioOut[1] = 1.0;
    return;
  }

  // Row-major flat index: sample (i, j) lives at i * samplesV + j.
  // The first u-edge walks i = 0..samplesU-1 at j = 0 (stride samplesV);
  // the first v-edge walks j = 0..samplesV-1 at i = 0 (stride 1).
  const double disU = EdgeArcLength(sampledSurface, static_cast<vtkIdType>(samplesV), samplesU);
  const double disV = EdgeArcLength(sampledSurface, 1, samplesV);

  // Normalise the longer axis to 1 (the v1 Ratio() branch).
  if (disU >= disV)
  {
    ratioOut[0] = 1.0;
    ratioOut[1] = (disU > 0.0) ? disV / disU : 1.0;
  }
  else
  {
    ratioOut[0] = (disV > 0.0) ? disU / disV : 1.0;
    ratioOut[1] = 1.0;
  }
}

//------------------------------------------------------------------------------
void vtkLiverResectogramAspectRatio::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);
}

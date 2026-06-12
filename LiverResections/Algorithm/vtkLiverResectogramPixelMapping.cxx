/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

==============================================================================*/

#include "vtkLiverResectogramPixelMapping.h"

// VTK includes
#include <vtkObjectFactory.h>

vtkStandardNewMacro(vtkLiverResectogramPixelMapping);

namespace
{
// Invert the centre-anchored aspect scaling for one axis.  The flattened
// quad fills the viewport linearly, then matRatio scales it about the
// 0.5 fixed point: linear = 0.5 + ratio * (uv - 0.5).  Inverting:
// uv = 0.5 + (linear - 0.5) / ratio.
double InvertAxis(double pixel, int extent, double ratio)
{
  if (extent <= 0)
  {
    return 0.0;
  }
  const double linear = pixel / static_cast<double>(extent);
  if (ratio == 0.0)
  {
    return linear;
  }
  return 0.5 + (linear - 0.5) / ratio;
}
} // namespace

//------------------------------------------------------------------------------
vtkLiverResectogramPixelMapping::vtkLiverResectogramPixelMapping() = default;

//------------------------------------------------------------------------------
vtkLiverResectogramPixelMapping::~vtkLiverResectogramPixelMapping() = default;

//------------------------------------------------------------------------------
void vtkLiverResectogramPixelMapping::PixelToUV(const double pixel[2], const int viewportSize[2], const double matRatio[2], double uvOut[2])
{
  uvOut[0] = InvertAxis(pixel[0], viewportSize[0], matRatio[0]);
  uvOut[1] = InvertAxis(pixel[1], viewportSize[1], matRatio[1]);
}

//------------------------------------------------------------------------------
void vtkLiverResectogramPixelMapping::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);
}

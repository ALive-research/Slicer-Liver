/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

==============================================================================*/

#include "vtkLiverOrientedPointCloudExtractor.h"

// VTK includes
#include <vtkFloatArray.h>
#include <vtkImageData.h>
#include <vtkMatrix4x4.h>
#include <vtkNew.h>
#include <vtkObjectFactory.h>
#include <vtkPointData.h>
#include <vtkPoints.h>
#include <vtkPolyData.h>

// ITK includes
#include <itkImage.h>
#include <itkImageRegionConstIterator.h>
#include <itkNeighborhoodOperatorImageFilter.h>
#include <itkSobelOperator.h>

// STD includes
#include <algorithm>
#include <cmath>
#include <vector>

namespace
{
using FloatImageType = itk::Image<float, 3>;

//------------------------------------------------------------------------------
// Copy the label's indicator function into a float ITK image.
//
// A copy rather than an itk::ImportImageFilter over the VTK buffer: the
// Sobel convolution needs a float field, the input may be any scalar
// type, and only voxels EQUAL to `label` belong to the object -- a
// multi-label volume must not have its other labels bleed into the
// gradient.
template <typename T>
void FillIndicator(vtkImageData* image, int label, std::vector<float>& out)
{
  const T* src = static_cast<const T*>(image->GetScalarPointer());
  const size_t n = out.size();
  const T wanted = static_cast<T>(label);
  for (size_t i = 0; i < n; ++i)
  {
    out[i] = (src[i] == wanted) ? 1.0f : 0.0f;
  }
}

//------------------------------------------------------------------------------
FloatImageType::Pointer MakeIndicatorImage(vtkImageData* image, int label, bool& ok)
{
  ok = false;
  int dims[3] = { 0, 0, 0 };
  image->GetDimensions(dims);
  if (dims[0] <= 0 || dims[1] <= 0 || dims[2] <= 0)
  {
    return nullptr;
  }
  const size_t count = static_cast<size_t>(dims[0]) * static_cast<size_t>(dims[1]) * static_cast<size_t>(dims[2]);

  // Unit spacing and zero origin deliberately: the gradient is taken in
  // VOXEL space and the caller's ijkToRAS carries the geometry.  Baking
  // spacing in here would scale the normals twice.
  FloatImageType::RegionType region;
  FloatImageType::SizeType size;
  size[0] = dims[0];
  size[1] = dims[1];
  size[2] = dims[2];
  FloatImageType::IndexType start;
  start.Fill(0);
  region.SetSize(size);
  region.SetIndex(start);

  FloatImageType::Pointer indicator = FloatImageType::New();
  indicator->SetRegions(region);
  indicator->Allocate();

  std::vector<float> buffer(count, 0.0f);
  switch (image->GetScalarType())
  {
    vtkTemplateMacro(FillIndicator<VTK_TT>(image, label, buffer));
    default: return nullptr;
  }
  std::copy(buffer.begin(), buffer.end(), indicator->GetBufferPointer());

  ok = true;
  return indicator;
}

//------------------------------------------------------------------------------
FloatImageType::Pointer SobelAlong(FloatImageType::Pointer input, unsigned int direction)
{
  itk::SobelOperator<float, 3> sobel;
  sobel.SetDirection(direction);
  itk::Size<3> radius;
  radius.Fill(1);
  sobel.CreateToRadius(radius);

  using FilterType = itk::NeighborhoodOperatorImageFilter<FloatImageType, FloatImageType>;
  FilterType::Pointer filter = FilterType::New();
  filter->SetOperator(sobel);
  filter->SetInput(input);
  filter->Update();
  FloatImageType::Pointer out = filter->GetOutput();
  out->DisconnectPipeline();
  return out;
}

} // namespace

//------------------------------------------------------------------------------
vtkStandardNewMacro(vtkLiverOrientedPointCloudExtractor);

//------------------------------------------------------------------------------
vtkLiverOrientedPointCloudExtractor::vtkLiverOrientedPointCloudExtractor() = default;

//------------------------------------------------------------------------------
vtkLiverOrientedPointCloudExtractor::~vtkLiverOrientedPointCloudExtractor() = default;

//------------------------------------------------------------------------------
void vtkLiverOrientedPointCloudExtractor::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);
}

//------------------------------------------------------------------------------
bool vtkLiverOrientedPointCloudExtractor::Extract(vtkImageData* labelMap, vtkMatrix4x4* ijkToRAS, int label, vtkIdType maxPoints, vtkPolyData* output)
{
  if (!output)
  {
    return false;
  }
  vtkNew<vtkPoints> points;
  vtkNew<vtkFloatArray> normals;
  normals->SetNumberOfComponents(3);
  normals->SetName("Normals");
  output->SetPoints(points);
  output->GetPointData()->SetNormals(normals);

  if (!labelMap || !ijkToRAS)
  {
    return false;
  }

  bool ok = false;
  FloatImageType::Pointer indicator = MakeIndicatorImage(labelMap, label, ok);
  if (!ok || indicator.IsNull())
  {
    return false;
  }

  FloatImageType::Pointer gx = SobelAlong(indicator, 0);
  FloatImageType::Pointer gy = SobelAlong(indicator, 1);
  FloatImageType::Pointer gz = SobelAlong(indicator, 2);

  int dims[3] = { 0, 0, 0 };
  labelMap->GetDimensions(dims);

  // The EXTENT ORIGIN, which is rarely zero for the images this class is
  // actually given.  A segment's binary labelmap is cropped to its own
  // bounding box, so its extent starts wherever that box does, while the
  // ITK image built above is indexed from 0.  Slicer's image-to-world
  // matrix maps ABSOLUTE voxel indices, so the offset has to be added
  // back before the matrix is applied -- otherwise every point is
  // translated by the extent origin and the cloud lands, intact and
  // correctly shaped, in the wrong place.
  int extent[6] = { 0, 0, 0, 0, 0, 0 };
  labelMap->GetExtent(extent);

  // The normal rotates by the direction part only; translation would
  // move it and scale would skew it.  Columns are normalised so a
  // non-uniform voxel size does not bias the direction.
  double rot[3][3];
  for (int c = 0; c < 3; ++c)
  {
    double norm = 0.0;
    for (int r = 0; r < 3; ++r)
    {
      rot[r][c] = ijkToRAS->GetElement(r, c);
      norm += rot[r][c] * rot[r][c];
    }
    norm = std::sqrt(norm);
    if (norm > 0.0)
    {
      for (int r = 0; r < 3; ++r)
      {
        rot[r][c] /= norm;
      }
    }
  }

  // Two passes: count the boundary, then emit with a stride.  A stride
  // keeps the subsample DETERMINISTIC -- the same labelmap yields the
  // same cloud, so a test can assert on it.
  const float kGradientEpsilon = 1e-3f;
  vtkIdType boundaryCount = 0;
  itk::ImageRegionConstIterator<FloatImageType> itX(gx, gx->GetLargestPossibleRegion());
  itk::ImageRegionConstIterator<FloatImageType> itY(gy, gy->GetLargestPossibleRegion());
  itk::ImageRegionConstIterator<FloatImageType> itZ(gz, gz->GetLargestPossibleRegion());
  for (itX.GoToBegin(), itY.GoToBegin(), itZ.GoToBegin(); !itX.IsAtEnd(); ++itX, ++itY, ++itZ)
  {
    const float m = std::sqrt(itX.Get() * itX.Get() + itY.Get() * itY.Get() + itZ.Get() * itZ.Get());
    if (m > kGradientEpsilon)
    {
      ++boundaryCount;
    }
  }
  if (boundaryCount == 0)
  {
    return false;
  }

  vtkIdType stride = 1;
  if (maxPoints > 0 && boundaryCount > maxPoints)
  {
    stride = (boundaryCount + maxPoints - 1) / maxPoints;
  }

  vtkIdType seen = 0;
  for (itX.GoToBegin(), itY.GoToBegin(), itZ.GoToBegin(); !itX.IsAtEnd(); ++itX, ++itY, ++itZ)
  {
    const float dx = itX.Get();
    const float dy = itY.Get();
    const float dz = itZ.Get();
    const float m = std::sqrt(dx * dx + dy * dy + dz * dz);
    if (m <= kGradientEpsilon)
    {
      continue;
    }
    const bool keep = (seen % stride) == 0;
    ++seen;
    if (!keep)
    {
      continue;
    }

    const FloatImageType::IndexType idx = itX.GetIndex();
    double ijk[4] = { static_cast<double>(idx[0] + extent[0]), static_cast<double>(idx[1] + extent[2]), static_cast<double>(idx[2] + extent[4]), 1.0 };
    double ras[4] = { 0.0, 0.0, 0.0, 0.0 };
    ijkToRAS->MultiplyPoint(ijk, ras);
    points->InsertNextPoint(ras[0], ras[1], ras[2]);

    // Negated: the indicator RISES from 0 outside to 1 inside, so its
    // gradient points INWARD.  PSR wants the outward normal.
    const double nIjk[3] = { -dx / m, -dy / m, -dz / m };
    double nRas[3] = { 0.0, 0.0, 0.0 };
    for (int r = 0; r < 3; ++r)
    {
      nRas[r] = rot[r][0] * nIjk[0] + rot[r][1] * nIjk[1] + rot[r][2] * nIjk[2];
    }
    const double len = std::sqrt(nRas[0] * nRas[0] + nRas[1] * nRas[1] + nRas[2] * nRas[2]);
    if (len > 0.0)
    {
      nRas[0] /= len;
      nRas[1] /= len;
      nRas[2] /= len;
    }
    normals->InsertNextTuple3(nRas[0], nRas[1], nRas[2]);
  }

  return points->GetNumberOfPoints() > 0;
}

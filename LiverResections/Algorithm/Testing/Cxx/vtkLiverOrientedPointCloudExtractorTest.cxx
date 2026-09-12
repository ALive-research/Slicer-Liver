/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, Oslo University Hospital. All rights reserved.

  Tests for ``vtkLiverOrientedPointCloudExtractor`` — the oriented point
  cloud PSR consumes (ADR-0040 §Decision 2).

  The load-bearing property is the NORMAL DIRECTION.  PSR reconstructs
  from orientation; a cloud whose normals point inward reconstructs the
  complement of the object, and a cloud with the right positions but
  wrong orientations fails in a way position-only assertions cannot see.
  So the sphere case checks every normal against the analytic outward
  direction, not merely that normals exist.

  Per ADR-0008 §2: C++ low-level ctkTest-driver tests, no Slicer scene,
  no Qt, no rendering.

==============================================================================*/

#include "vtkLiverOrientedPointCloudExtractor.h"

// VTK includes
#include <vtkDataArray.h>
#include <vtkImageData.h>
#include <vtkMatrix4x4.h>
#include <vtkNew.h>
#include <vtkPointData.h>
#include <vtkPoints.h>
#include <vtkPolyData.h>

// STD includes
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <iostream>

namespace
{

#define LIVER_CHECK(cond, msg)                                             \
  do                                                                       \
  {                                                                        \
    if (!(cond))                                                           \
    {                                                                      \
      std::fprintf(stderr, "[%s:%d] FAIL: %s\n", __FILE__, __LINE__, msg); \
      return EXIT_FAILURE;                                                 \
    }                                                                      \
  } while (0)

//----------------------------------------------------------------------------
// A solid sphere of `label`, centred in a dim^3 volume.
vtkSmartPointer<vtkImageData> MakeSphere(int dim, double radius, int label)
{
  vtkSmartPointer<vtkImageData> image = vtkSmartPointer<vtkImageData>::New();
  image->SetDimensions(dim, dim, dim);
  image->AllocateScalars(VTK_UNSIGNED_CHAR, 1);
  const double c = (dim - 1) / 2.0;
  for (int k = 0; k < dim; ++k)
  {
    for (int j = 0; j < dim; ++j)
    {
      for (int i = 0; i < dim; ++i)
      {
        const double d2 = (i - c) * (i - c) + (j - c) * (j - c) + (k - c) * (k - c);
        unsigned char* v = static_cast<unsigned char*>(image->GetScalarPointer(i, j, k));
        *v = (d2 <= radius * radius) ? static_cast<unsigned char>(label) : 0;
      }
    }
  }
  return image;
}

//----------------------------------------------------------------------------
/// The same sphere, but in an image whose EXTENT STARTS AWAY FROM ZERO.
///
/// This is the shape the class is actually given in production: a
/// segment's binary labelmap is cropped to its own bounding box, so its
/// extent begins wherever that box does.  A zero-based fixture cannot
/// tell a correct index mapping from one that ignores the offset.
vtkSmartPointer<vtkImageData> MakeSphereAtExtent(int dim, double radius, int label, const int origin[3])
{
  vtkSmartPointer<vtkImageData> image = vtkSmartPointer<vtkImageData>::New();
  image->SetExtent(origin[0], origin[0] + dim - 1, origin[1], origin[1] + dim - 1, origin[2], origin[2] + dim - 1);
  image->AllocateScalars(VTK_UNSIGNED_CHAR, 1);
  const double c = (dim - 1) / 2.0;
  for (int k = 0; k < dim; ++k)
  {
    for (int j = 0; j < dim; ++j)
    {
      for (int i = 0; i < dim; ++i)
      {
        const double d2 = (i - c) * (i - c) + (j - c) * (j - c) + (k - c) * (k - c);
        unsigned char* v = static_cast<unsigned char*>(image->GetScalarPointer(i + origin[0], j + origin[1], k + origin[2]));
        *v = (d2 <= radius * radius) ? static_cast<unsigned char>(label) : 0;
      }
    }
  }
  return image;
}

//----------------------------------------------------------------------------
/// The cloud must land at the voxels' ABSOLUTE index position.
///
/// Slicer's image-to-world matrix maps absolute voxel indices, so an
/// extractor that reports indices relative to the extent produces a
/// cloud that is intact, correctly shaped, correctly oriented -- and
/// translated by the extent origin.  Every other assertion in this file
/// still passes in that state, which is exactly how it reached a real
/// liver before being caught by eye.
int TestExtentOriginIsHonoured()
{
  const int dim = 30;
  const double radius = 9.0;
  const int origin[3] = { 100, 50, 20 };

  vtkSmartPointer<vtkImageData> shifted = MakeSphereAtExtent(dim, radius, 1, origin);
  vtkNew<vtkMatrix4x4> identity; // IJK == RAS, so the answer is exact.
  vtkNew<vtkPolyData> cloud;
  if (!vtkLiverOrientedPointCloudExtractor::Extract(shifted, identity, 1, 0, cloud))
  {
    std::cerr << "FAIL: extraction failed on a shifted-extent image" << std::endl;
    return EXIT_FAILURE;
  }

  double bounds[6];
  cloud->GetBounds(bounds);
  const double centre[3] = { (bounds[0] + bounds[1]) / 2.0, (bounds[2] + bounds[3]) / 2.0, (bounds[4] + bounds[5]) / 2.0 };
  const double expected[3] = { origin[0] + (dim - 1) / 2.0, origin[1] + (dim - 1) / 2.0, origin[2] + (dim - 1) / 2.0 };

  std::cout << "extent origin: centre (" << centre[0] << ", " << centre[1] << ", " << centre[2] << "), expected (" << expected[0] << ", " << expected[1] << ", " << expected[2]
            << ")" << std::endl;

  for (int axis = 0; axis < 3; ++axis)
  {
    if (std::abs(centre[axis] - expected[axis]) > 1.0)
    {
      std::cerr << "FAIL: axis " << axis << " off by " << (expected[axis] - centre[axis]) << " -- the extent origin was dropped" << std::endl;
      return EXIT_FAILURE;
    }
  }
  return EXIT_SUCCESS;
}

//----------------------------------------------------------------------------
int TestNormalsPointOutward()
{
  const int dim = 32;
  const double radius = 10.0;
  vtkSmartPointer<vtkImageData> sphere = MakeSphere(dim, radius, 1);
  vtkNew<vtkMatrix4x4> identity;
  vtkNew<vtkPolyData> cloud;

  LIVER_CHECK(vtkLiverOrientedPointCloudExtractor::Extract(sphere, identity, 1, 0, cloud), "extraction of a solid sphere must succeed");

  vtkPoints* pts = cloud->GetPoints();
  vtkDataArray* normals = cloud->GetPointData()->GetNormals();
  LIVER_CHECK(pts && normals, "the cloud carries points and normals");
  LIVER_CHECK(pts->GetNumberOfPoints() > 0, "the cloud is not empty");
  LIVER_CHECK(normals->GetNumberOfTuples() == pts->GetNumberOfPoints(), "one normal per point");

  // Every normal must agree with the analytic outward radial direction.
  // A cloud oriented inward reconstructs the complement of the object.
  const double c = (dim - 1) / 2.0;
  double worstDot = 1.0;
  double meanDot = 0.0;
  for (vtkIdType i = 0; i < pts->GetNumberOfPoints(); ++i)
  {
    double p[3];
    pts->GetPoint(i, p);
    double n[3];
    normals->GetTuple(i, n);

    double r[3] = { p[0] - c, p[1] - c, p[2] - c };
    const double rl = std::sqrt(r[0] * r[0] + r[1] * r[1] + r[2] * r[2]);
    if (rl < 1e-6)
    {
      continue;
    }
    for (int d = 0; d < 3; ++d)
    {
      r[d] /= rl;
    }
    const double dot = n[0] * r[0] + n[1] * r[1] + n[2] * r[2];
    worstDot = std::min(worstDot, dot);
    meanDot += dot;

    const double len = std::sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2]);
    LIVER_CHECK(std::fabs(len - 1.0) < 1e-3, "normals are unit length");
  }
  meanDot /= static_cast<double>(pts->GetNumberOfPoints());

  std::cout << "  sphere: " << pts->GetNumberOfPoints() << " points, mean dot " << meanDot << ", worst " << worstDot << std::endl;

  // Sobel on a voxelised sphere cannot be exact; the mean must be close
  // to 1 and NO normal may point inward.
  LIVER_CHECK(meanDot > 0.95, "normals agree with the analytic outward direction");
  LIVER_CHECK(worstDot > 0.0, "NO normal points inward");
  return EXIT_SUCCESS;
}

//----------------------------------------------------------------------------
int TestSubsamplingIsDeterministicAndBounded()
{
  vtkSmartPointer<vtkImageData> sphere = MakeSphere(32, 10.0, 1);
  vtkNew<vtkMatrix4x4> identity;

  vtkNew<vtkPolyData> full;
  LIVER_CHECK(vtkLiverOrientedPointCloudExtractor::Extract(sphere, identity, 1, 0, full), "full");
  const vtkIdType n = full->GetNumberOfPoints();

  const vtkIdType cap = n / 4;
  vtkNew<vtkPolyData> a;
  vtkNew<vtkPolyData> b;
  LIVER_CHECK(vtkLiverOrientedPointCloudExtractor::Extract(sphere, identity, 1, cap, a), "capped a");
  LIVER_CHECK(vtkLiverOrientedPointCloudExtractor::Extract(sphere, identity, 1, cap, b), "capped b");

  LIVER_CHECK(a->GetNumberOfPoints() <= cap, "the cap is respected");
  LIVER_CHECK(a->GetNumberOfPoints() == b->GetNumberOfPoints(), "same count twice");
  for (vtkIdType i = 0; i < a->GetNumberOfPoints(); ++i)
  {
    double pa[3];
    double pb[3];
    a->GetPoint(i, pa);
    b->GetPoint(i, pb);
    LIVER_CHECK(pa[0] == pb[0] && pa[1] == pb[1] && pa[2] == pb[2], "the subsample is DETERMINISTIC -- a test could not assert on it otherwise");
  }
  std::cout << "  subsample: " << a->GetNumberOfPoints() << " of " << n << " (cap " << cap << ")" << std::endl;
  return EXIT_SUCCESS;
}

//----------------------------------------------------------------------------
int TestGeometryIsAppliedFromTheMatrix()
{
  vtkSmartPointer<vtkImageData> sphere = MakeSphere(32, 10.0, 1);

  vtkNew<vtkMatrix4x4> identity;
  vtkNew<vtkPolyData> plain;
  LIVER_CHECK(vtkLiverOrientedPointCloudExtractor::Extract(sphere, identity, 1, 0, plain), "plain");

  // Anisotropic spacing plus a translation: positions must scale and
  // shift, normals must NOT pick up the translation and must stay unit.
  vtkNew<vtkMatrix4x4> geom;
  geom->Identity();
  geom->SetElement(0, 0, 2.0);
  geom->SetElement(1, 1, 0.5);
  geom->SetElement(2, 2, 1.0);
  geom->SetElement(0, 3, 100.0);
  vtkNew<vtkPolyData> shifted;
  LIVER_CHECK(vtkLiverOrientedPointCloudExtractor::Extract(sphere, geom, 1, 0, shifted), "shifted");

  LIVER_CHECK(plain->GetNumberOfPoints() == shifted->GetNumberOfPoints(), "geometry changes coordinates, not membership");

  double pb[6];
  shifted->GetBounds(pb);
  LIVER_CHECK(pb[0] > 90.0, "the translation reached the points");

  vtkDataArray* normals = shifted->GetPointData()->GetNormals();
  for (vtkIdType i = 0; i < normals->GetNumberOfTuples(); ++i)
  {
    double n[3];
    normals->GetTuple(i, n);
    const double len = std::sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2]);
    LIVER_CHECK(std::fabs(len - 1.0) < 1e-3,
                "normals stay unit under anisotropic spacing -- a translation or a "
                "scale leaking in would skew every one of them");
  }
  return EXIT_SUCCESS;
}

//----------------------------------------------------------------------------
int TestDegenerateInputsYieldAnEmptyCloud()
{
  vtkNew<vtkMatrix4x4> identity;
  vtkNew<vtkPolyData> out;

  LIVER_CHECK(!vtkLiverOrientedPointCloudExtractor::Extract(nullptr, identity, 1, 0, out), "a null image is refused");
  LIVER_CHECK(out->GetNumberOfPoints() == 0, "and leaves the output empty, not stale");

  vtkSmartPointer<vtkImageData> sphere = MakeSphere(16, 5.0, 1);
  vtkNew<vtkPolyData> absent;
  LIVER_CHECK(!vtkLiverOrientedPointCloudExtractor::Extract(sphere, identity, 7, 0, absent), "a label that is not present has no boundary");
  LIVER_CHECK(absent->GetNumberOfPoints() == 0, "and yields an empty cloud, not an exception");

  vtkNew<vtkPolyData> noMatrix;
  LIVER_CHECK(!vtkLiverOrientedPointCloudExtractor::Extract(sphere, nullptr, 1, 0, noMatrix), "a null matrix is refused");
  return EXIT_SUCCESS;
}

//----------------------------------------------------------------------------
int TestOtherLabelsDoNotBleedIn()
{
  // Two concentric shells with different labels.  Extracting the inner
  // one must not see the outer one's boundary: the indicator is built
  // from voxels EQUAL to the label, not merely non-zero.
  const int dim = 40;
  vtkSmartPointer<vtkImageData> image = MakeSphere(dim, 8.0, 1);
  const double c = (dim - 1) / 2.0;
  for (int k = 0; k < dim; ++k)
  {
    for (int j = 0; j < dim; ++j)
    {
      for (int i = 0; i < dim; ++i)
      {
        const double d2 = (i - c) * (i - c) + (j - c) * (j - c) + (k - c) * (k - c);
        unsigned char* v = static_cast<unsigned char*>(image->GetScalarPointer(i, j, k));
        if (d2 > 8.0 * 8.0 && d2 <= 14.0 * 14.0)
        {
          *v = 2;
        }
      }
    }
  }

  vtkNew<vtkMatrix4x4> identity;
  vtkNew<vtkPolyData> inner;
  LIVER_CHECK(vtkLiverOrientedPointCloudExtractor::Extract(image, identity, 1, 0, inner), "inner");

  double b[6];
  inner->GetBounds(b);
  const double maxR = std::max(std::fabs(b[1] - c), std::fabs(b[0] - c));
  std::cout << "  two-label: inner cloud max radius " << maxR << " (inner r=8, outer r=14)" << std::endl;
  LIVER_CHECK(maxR < 12.0,
              "the inner label's cloud must not reach the outer label's boundary -- "
              "a non-zero test instead of an equality test would merge them");
  return EXIT_SUCCESS;
}

} // namespace

//----------------------------------------------------------------------------
int vtkLiverOrientedPointCloudExtractorTest(int, char*[])
{
  if (TestNormalsPointOutward() != EXIT_SUCCESS)
  {
    return EXIT_FAILURE;
  }
  if (TestSubsamplingIsDeterministicAndBounded() != EXIT_SUCCESS)
  {
    return EXIT_FAILURE;
  }
  if (TestGeometryIsAppliedFromTheMatrix() != EXIT_SUCCESS)
  {
    return EXIT_FAILURE;
  }
  if (TestDegenerateInputsYieldAnEmptyCloud() != EXIT_SUCCESS)
  {
    return EXIT_FAILURE;
  }
  if (TestOtherLabelsDoNotBleedIn() != EXIT_SUCCESS)
  {
    return EXIT_FAILURE;
  }
  if (TestExtentOriginIsHonoured() != EXIT_SUCCESS)
  {
    return EXIT_FAILURE;
  }
  std::cout << "vtkLiverOrientedPointCloudExtractorTest passed." << std::endl;
  return EXIT_SUCCESS;
}

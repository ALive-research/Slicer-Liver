/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, Oslo University Hospital. All rights reserved.

  Tests for
  ``vtkSlicerLiverBezierControlPolygonGeometry::BuildRingGroups``
  — the ring decomposition the control-polygon group-drag gestures
  consume (frame translation and per-ring translation).

  Per ADR-0008 §2 these are C++ low-level ctkTest-driver tests with no
  Slicer scene, no Qt, no rendering, no on-screen interactor.  The
  builder is a pure index helper; the test exercises the static method
  directly.

  The load-bearing property is that the rings PARTITION the control
  grid: a ring translates rigidly, so an id appearing in two rings
  would be displaced twice and an id appearing in none would be left
  behind, tearing the surface.  Every case below asserts the partition
  explicitly rather than only checking sizes.

  Coverage:

   - ``(4, 4)``: two rings — outer 12 ids, inner 4 — and the outer ring
     emitted as a CONTIGUOUS closed-path walk, so a caller can draw the
     ring highlight straight from the id order.
   - ``(3, 3)``: two rings — outer 8 ids, and an inner group holding the
     SINGLE centre id.  A one-element rigid-translation group is well
     defined even though it is not a ring geometrically; this pins the
     degenerate shape so a caller presenting a ring affordance cannot be
     surprised by it.
   - Invalid shapes: the ADR-0018 §1 closed-set check rejects them and
     returns an empty ring list, mirroring the sibling
     ``BuildControlPolygonCells``.

==============================================================================*/

// LiverResections Algorithm includes
#include "vtkSlicerLiverBezierControlPolygonGeometry.h"

// VTK includes
#include <vtkTestingOutputWindow.h>
#include <vtkType.h>

// STD includes
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <vector>

namespace
{

#define LIVER_CHECK_INT(actual, expected)                                                                    \
  do                                                                                                         \
  {                                                                                                          \
    const long long _a = static_cast<long long>(actual);                                                     \
    const long long _e = static_cast<long long>(expected);                                                   \
    if (_a != _e)                                                                                            \
    {                                                                                                        \
      std::fprintf(stderr, "[%s:%d] FAIL: %s = %lld; expected %lld\n", __FILE__, __LINE__, #actual, _a, _e); \
      return EXIT_FAILURE;                                                                                   \
    }                                                                                                        \
  } while (0)

//----------------------------------------------------------------------------
// The rings must be a partition of [0, rows * cols): every control point
// in exactly one rigid-translation group.
int CheckPartitions(const std::vector<std::vector<vtkIdType>>& rings, unsigned int rows, unsigned int cols)
{
  std::vector<vtkIdType> flat;
  for (const auto& ring : rings)
  {
    flat.insert(flat.end(), ring.begin(), ring.end());
  }
  std::sort(flat.begin(), flat.end());

  LIVER_CHECK_INT(flat.size(), rows * cols);
  for (unsigned int i = 0; i < rows * cols; ++i)
  {
    LIVER_CHECK_INT(flat[i], i);
  }
  return EXIT_SUCCESS;
}

//----------------------------------------------------------------------------
int TestFourByFour()
{
  const auto rings = vtkSlicerLiverBezierControlPolygonGeometry::BuildRingGroups(4, 4);

  LIVER_CHECK_INT(rings.size(), 2);
  LIVER_CHECK_INT(rings[0].size(), 12);
  LIVER_CHECK_INT(rings[1].size(), 4);

  if (CheckPartitions(rings, 4, 4) != EXIT_SUCCESS)
  {
    return EXIT_FAILURE;
  }

  // The outer ring walks the boundary clockwise from the top-left, so a
  // highlight can consume the order directly as a closed path.
  const std::vector<vtkIdType> expectedOuter = { 0, 1, 2, 3, 7, 11, 15, 14, 13, 12, 8, 4 };
  for (size_t i = 0; i < expectedOuter.size(); ++i)
  {
    LIVER_CHECK_INT(rings[0][i], expectedOuter[i]);
  }

  const std::vector<vtkIdType> expectedInner = { 5, 6, 10, 9 };
  for (size_t i = 0; i < expectedInner.size(); ++i)
  {
    LIVER_CHECK_INT(rings[1][i], expectedInner[i]);
  }

  return EXIT_SUCCESS;
}

//----------------------------------------------------------------------------
int TestThreeByThree()
{
  const auto rings = vtkSlicerLiverBezierControlPolygonGeometry::BuildRingGroups(3, 3);

  LIVER_CHECK_INT(rings.size(), 2);
  LIVER_CHECK_INT(rings[0].size(), 8);

  // The degenerate case: the 3x3 "inner ring" is the single centre point.
  LIVER_CHECK_INT(rings[1].size(), 1);
  LIVER_CHECK_INT(rings[1][0], 4);

  return CheckPartitions(rings, 3, 3);
}

//----------------------------------------------------------------------------
int TestInvalidShapesAreRejected()
{
  const unsigned int invalid[][2] = { { 2, 2 }, { 5, 5 }, { 3, 4 }, { 4, 3 }, { 0, 0 }, { 1, 1 } };
  for (const auto& shape : invalid)
  {
    TESTING_OUTPUT_ASSERT_WARNINGS_BEGIN();
    const auto rings = vtkSlicerLiverBezierControlPolygonGeometry::BuildRingGroups(shape[0], shape[1]);
    TESTING_OUTPUT_ASSERT_WARNINGS_END();
    if (!rings.empty())
    {
      std::fprintf(stderr, "[%s:%d] FAIL: (%u, %u) is outside the ADR-0018 closed set but produced %zu rings\n", __FILE__, __LINE__, shape[0], shape[1], rings.size());
      return EXIT_FAILURE;
    }
  }
  return EXIT_SUCCESS;
}

} // namespace

//----------------------------------------------------------------------------
int vtkSlicerLiverBezierRingGroupsTest(int, char*[])
{
  if (TestFourByFour() != EXIT_SUCCESS)
  {
    return EXIT_FAILURE;
  }
  if (TestThreeByThree() != EXIT_SUCCESS)
  {
    return EXIT_FAILURE;
  }
  if (TestInvalidShapesAreRejected() != EXIT_SUCCESS)
  {
    return EXIT_FAILURE;
  }

  std::cout << "vtkSlicerLiverBezierRingGroupsTest passed." << std::endl;
  return EXIT_SUCCESS;
}

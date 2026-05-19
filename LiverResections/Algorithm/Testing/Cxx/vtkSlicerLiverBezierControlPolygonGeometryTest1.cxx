/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, Oslo University Hospital. All rights reserved.

  Tests for
  ``vtkSlicerLiverBezierControlPolygonGeometry::BuildControlPolygonCells``
  — the dimension-aware control-polygon topology builder introduced
  by the ADR-0018 §1 ``(Rows, Cols) ∈ {(3, 3), (4, 4)}`` widening.

  Per ADR-0008 §2 these are C++ low-level ctkTest-driver tests with no
  Slicer scene, no Qt, no rendering, no on-screen interactor.  The
  builder is a pure VTK-topology helper (returns a populated
  ``vtkCellArray``); the test exercises the static method directly
  without instantiating any MRML or Slicer object.

  Coverage:

   - ``(4, 4)`` shape: 9 closed-quad polylines with stride 4 and the
     row-major point-id pattern.  This is the legacy v1
     ``vtkMRMLMarkupsBezierSurfaceNode`` shape (16 control points,
     always) — see ``UpdateControlPolygonGeometry`` in
     ``vtkSlicerBezierSurfaceRepresentation3D``, which today only ever
     binds to v1 and now delegates to this Algorithm helper.
   - ``(3, 3)`` shape: 4 closed-quad polylines with stride 3.  The
     ADR-0018 §1 variable-size case.  This branch is unreachable from
     the legacy v1 markups node (which has no Rows/Cols IVars and is
     always 4×4); reachable from the v2 ``vtkMRMLBezierSurfaceNode``
     binding hosted by the sibling ``vtkLiverBezierRepresentation`` in
     ``LiverResections/VTKWidgets/``.  The test pins the topology here
     to lock in the dimension-aware shape for both bindings.
   - Invalid shapes (e.g. ``(2, 2)``, ``(5, 5)``, ``(3, 4)``): the
     ADR-0018 §1 closed-set check rejects them and emits an empty
     cell array.  Mirrors the rejection pattern of
     ``vtkMRMLBezierSurfaceNode::SetRows`` / ``SetCols``.

==============================================================================*/

// LiverResections Algorithm includes
#include "vtkSlicerLiverBezierControlPolygonGeometry.h"

// VTK includes
#include <vtkCellArray.h>
#include <vtkIdList.h>
#include <vtkNew.h>
#include <vtkPolyLine.h>
#include <vtkSmartPointer.h>
#include <vtkTestingOutputWindow.h>

// STD includes
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <iostream>

namespace
{

#define LIVER_CHECK_INT(actual, expected) \
  do { \
    const long long _a = static_cast<long long>(actual); \
    const long long _e = static_cast<long long>(expected); \
    if (_a != _e) \
    { \
      std::fprintf(stderr, "[%s:%d] FAIL: %s = %lld; expected %lld\n", \
                   __FILE__, __LINE__, #actual, _a, _e); \
      return EXIT_FAILURE; \
    } \
  } while (0)

#define LIVER_CHECK_NOT_NULL(ptr) \
  do { \
    if ((ptr) == nullptr) \
    { \
      std::fprintf(stderr, "[%s:%d] FAIL: %s is null\n", __FILE__, __LINE__, #ptr); \
      return EXIT_FAILURE; \
    } \
  } while (0)

#define LIVER_CHECK_EXIT_SUCCESS(call) \
  do { \
    const int _r = (call); \
    if (_r != EXIT_SUCCESS) \
    { \
      std::fprintf(stderr, "[%s:%d] FAIL: %s returned %d\n", __FILE__, __LINE__, #call, _r); \
      return EXIT_FAILURE; \
    } \
  } while (0)

/// Expected number of closed-quad cells for an ``(rows, cols)`` lattice:
/// ``(rows - 1) * (cols - 1)``.
constexpr vtkIdType expectedCellCount(unsigned int rows, unsigned int cols)
{
  return static_cast<vtkIdType>((rows - 1) * (cols - 1));
}

/// Verify the cell array carries the row-major closed-quad pattern.
/// Walks every emitted polyline and checks each of its 5 point ids
/// against the ADR-0018 §1 indexing ``i * cols + j``.
int verifyTopology(vtkCellArray* cells, unsigned int rows, unsigned int cols)
{
  LIVER_CHECK_NOT_NULL(cells);
  const vtkIdType expected = expectedCellCount(rows, cols);
  LIVER_CHECK_INT(cells->GetNumberOfCells(), expected);

  vtkNew<vtkIdList> ids;
  cells->InitTraversal();
  for (unsigned int i = 0; i + 1 < rows; ++i)
  {
    for (unsigned int j = 0; j + 1 < cols; ++j)
    {
      const int hasNext = cells->GetNextCell(ids);
      if (!hasNext)
      {
        std::fprintf(stderr, "Cell array exhausted at (i=%u, j=%u); expected %lld cells\n",
                     i, j, static_cast<long long>(expected));
        return EXIT_FAILURE;
      }
      LIVER_CHECK_INT(ids->GetNumberOfIds(), 5);
      // Row-major indexing per ADR-0018 §1: flat = row * cols + col.
      LIVER_CHECK_INT(ids->GetId(0), i * cols + j);
      LIVER_CHECK_INT(ids->GetId(1), i * cols + j + 1);
      LIVER_CHECK_INT(ids->GetId(2), (i + 1) * cols + j + 1);
      LIVER_CHECK_INT(ids->GetId(3), (i + 1) * cols + j);
      LIVER_CHECK_INT(ids->GetId(4), i * cols + j);
    }
  }
  return EXIT_SUCCESS;
}

int test4x4Topology()
{
  // Legacy v1 ``vtkMRMLMarkupsBezierSurfaceNode`` shape — 16 control
  // points, ``(Rows, Cols) = (4, 4)`` implicit.  Expected: 9 closed-quad
  // polylines, point ids spanning [0, 15] with stride 4.
  vtkSmartPointer<vtkCellArray> cells =
    vtkSlicerLiverBezierControlPolygonGeometry::BuildControlPolygonCells(4, 4);
  LIVER_CHECK_EXIT_SUCCESS(verifyTopology(cells, 4, 4));

  // Spot-check: the top-left quad (i=0, j=0) must reference point ids
  // {0, 1, 5, 4, 0}; the bottom-right quad (i=2, j=2) must reference
  // {10, 11, 15, 14, 10}.  Pre-fix code happens to match the 4×4 case
  // (it was hard-coded to stride 4), so this is a regression sentinel
  // rather than a red-on-arrival check.
  cells->InitTraversal();
  vtkNew<vtkIdList> first;
  if (cells->GetNextCell(first) == 0)
  {
    std::fprintf(stderr, "test4x4Topology: cell array empty on first traversal\n");
    return EXIT_FAILURE;
  }
  LIVER_CHECK_INT(first->GetId(0), 0);
  LIVER_CHECK_INT(first->GetId(2), 5);

  // Walk to the last cell (index 8).
  vtkNew<vtkIdList> last;
  for (int c = 0; c < 8; ++c)
  {
    if (cells->GetNextCell(last) == 0)
    {
      std::fprintf(stderr, "test4x4Topology: cell array exhausted at index %d\n", c);
      return EXIT_FAILURE;
    }
  }
  LIVER_CHECK_INT(last->GetId(0), 10);
  LIVER_CHECK_INT(last->GetId(2), 15);
  return EXIT_SUCCESS;
}

int test3x3Topology()
{
  // ADR-0018 §1 ``(3, 3)`` shape — 9 control points, 4 closed-quad
  // polylines, stride 3.  Pre-fix the function was hard-coded to a
  // ``i*4+j`` stride and ``i, j < 3`` outer loops; calling it against
  // a 9-point grid would index id ``(3*4+3) = 15``, which is out of
  // range for a 9-point ``vtkPoints`` (heap OOB on render).  Post-fix
  // the helper indexes ``i*3+j`` and stays within [0, 8].
  vtkSmartPointer<vtkCellArray> cells =
    vtkSlicerLiverBezierControlPolygonGeometry::BuildControlPolygonCells(3, 3);
  LIVER_CHECK_EXIT_SUCCESS(verifyTopology(cells, 3, 3));

  // Spot-check: the top-left quad (i=0, j=0) must reference point ids
  // {0, 1, 4, 3, 0}; the bottom-right quad (i=1, j=1) must reference
  // {4, 5, 8, 7, 4}.  Both are within the [0, 8] valid range of a
  // 9-point control grid — proves the fix.
  cells->InitTraversal();
  vtkNew<vtkIdList> first;
  if (cells->GetNextCell(first) == 0)
  {
    std::fprintf(stderr, "test3x3Topology: cell array empty on first traversal\n");
    return EXIT_FAILURE;
  }
  LIVER_CHECK_INT(first->GetId(0), 0);
  LIVER_CHECK_INT(first->GetId(1), 1);
  LIVER_CHECK_INT(first->GetId(2), 4);
  LIVER_CHECK_INT(first->GetId(3), 3);
  LIVER_CHECK_INT(first->GetId(4), 0);

  // Walk to the last cell (index 3 — total 4 cells for a 3×3 grid).
  vtkNew<vtkIdList> last;
  for (int c = 0; c < 3; ++c)
  {
    if (cells->GetNextCell(last) == 0)
    {
      std::fprintf(stderr, "test3x3Topology: cell array exhausted at index %d\n", c);
      return EXIT_FAILURE;
    }
  }
  LIVER_CHECK_INT(last->GetId(0), 4);
  LIVER_CHECK_INT(last->GetId(1), 5);
  LIVER_CHECK_INT(last->GetId(2), 8);
  LIVER_CHECK_INT(last->GetId(3), 7);

  // Highest point id emitted must be 8 (== 3*3 - 1) — no OOB index
  // past the 9-point control grid.
  cells->InitTraversal();
  vtkNew<vtkIdList> ids;
  vtkIdType maxId = -1;
  while (cells->GetNextCell(ids))
  {
    for (vtkIdType k = 0; k < ids->GetNumberOfIds(); ++k)
    {
      maxId = std::max(maxId, ids->GetId(k));
    }
  }
  LIVER_CHECK_INT(maxId, 8);
  return EXIT_SUCCESS;
}

int testInvalidShapesRejected()
{
  // ADR-0018 §1 — closed set is exactly ``{(3, 3), (4, 4)}``.  Every
  // other ``(rows, cols)`` is rejected.  The helper emits a
  // ``vtkGenericWarningMacro`` and returns an empty cell array.  Gate
  // the warnings so the test driver does not count them as failures.
  TESTING_OUTPUT_ASSERT_WARNINGS_BEGIN();

  // Below the closed set.
  vtkSmartPointer<vtkCellArray> tooSmall =
    vtkSlicerLiverBezierControlPolygonGeometry::BuildControlPolygonCells(2, 2);
  LIVER_CHECK_NOT_NULL(tooSmall);
  LIVER_CHECK_INT(tooSmall->GetNumberOfCells(), 0);

  // Above the closed set — would be NURBS territory per ADR-0018 §3.
  vtkSmartPointer<vtkCellArray> tooBig =
    vtkSlicerLiverBezierControlPolygonGeometry::BuildControlPolygonCells(5, 5);
  LIVER_CHECK_NOT_NULL(tooBig);
  LIVER_CHECK_INT(tooBig->GetNumberOfCells(), 0);

  // Non-square — ADR-0018 §1 admits only square shapes (ring-symmetry
  // constraint).
  vtkSmartPointer<vtkCellArray> nonSquare =
    vtkSlicerLiverBezierControlPolygonGeometry::BuildControlPolygonCells(3, 4);
  LIVER_CHECK_NOT_NULL(nonSquare);
  LIVER_CHECK_INT(nonSquare->GetNumberOfCells(), 0);

  vtkSmartPointer<vtkCellArray> nonSquareT =
    vtkSlicerLiverBezierControlPolygonGeometry::BuildControlPolygonCells(4, 3);
  LIVER_CHECK_NOT_NULL(nonSquareT);
  LIVER_CHECK_INT(nonSquareT->GetNumberOfCells(), 0);

  TESTING_OUTPUT_ASSERT_WARNINGS_END();
  return EXIT_SUCCESS;
}

} // namespace

//------------------------------------------------------------------------------
int vtkSlicerLiverBezierControlPolygonGeometryTest1(int, char*[])
{
  LIVER_CHECK_EXIT_SUCCESS(test4x4Topology());
  LIVER_CHECK_EXIT_SUCCESS(test3x3Topology());
  LIVER_CHECK_EXIT_SUCCESS(testInvalidShapesRejected());

  std::cout << "vtkSlicerLiverBezierControlPolygonGeometryTest1 completed successfully" << std::endl;
  return EXIT_SUCCESS;
}

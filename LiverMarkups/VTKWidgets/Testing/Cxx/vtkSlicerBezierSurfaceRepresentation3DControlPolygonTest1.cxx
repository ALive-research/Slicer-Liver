/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Tests for ``vtkSlicerBezierSurfaceRepresentation3D::BuildControlPolygonCells``
  — the dimension-aware control-polygon topology builder introduced
  by the ADR-0018 §1 ``(Rows, Cols) ∈ {(3, 3), (4, 4)}`` widening.

  Per ADR-0008 §2 these are C++ low-level ctkTest-driver tests: no
  Slicer scene, no Qt, no rendering, no on-screen interactor.  The
  builder is a pure VTK-topology helper (returns a populated
  ``vtkCellArray``); the test exercises it directly without
  instantiating ``vtkSlicerBezierSurfaceRepresentation3D`` (which
  pulls Qt / Slicer dependencies via its constructor).

  Coverage:

   - ``(4, 4)`` shape: 9 closed-quad polylines with stride 4 and the
     row-major point-id pattern.  This is the legacy v1
     ``vtkMRMLMarkupsBezierSurfaceNode`` shape (16 control points,
     always) — see ``UpdateControlPolygonGeometry`` in the
     representation .cxx, which today only ever binds to v1.
   - ``(3, 3)`` shape: 4 closed-quad polylines with stride 3.  The
     ADR-0018 §1 variable-size case.  This branch is unreachable
     from the legacy v1 markups node (which has no Rows/Cols IVars
     and is always 4×4); reachable from the v2
     ``vtkMRMLBezierSurfaceNode`` binding hosted by the sibling
     ``vtkLiverBezierRepresentation`` in ``LiverResections/VTKWidgets/``.
     The test pins the topology here to lock in the dimension-aware
     shape for both bindings.
   - Invalid shapes (e.g. ``(2, 2)``, ``(5, 5)``, ``(3, 4)``): the
     ADR-0018 §1 closed-set check rejects them and emits an empty
     cell array.  Mirrors the rejection pattern of
     ``vtkMRMLBezierSurfaceNode::SetRows`` / ``SetCols``.

==============================================================================*/

// LiverMarkups VTKWidgets includes
#include "vtkSlicerBezierSurfaceRepresentation3D.h"

// MRML includes
#include "vtkMRMLCoreTestingMacros.h"

// VTK includes
#include <vtkCellArray.h>
#include <vtkIdList.h>
#include <vtkNew.h>
#include <vtkPolyLine.h>
#include <vtkSmartPointer.h>

// STD includes
#include <algorithm>
#include <iostream>

namespace
{

/// Expected number of closed-quad cells for an ``(rows, cols)`` lattice:
/// ``(rows - 1) * (cols - 1)``.
constexpr vtkIdType expectedCellCount(unsigned int rows, unsigned int cols)
{
  return static_cast<vtkIdType>((rows - 1) * (cols - 1));
}

/// Verify the cell array carries the row-major closed-quad pattern.
/// Walks every emitted polyline + checks each of its 5 point ids
/// against the ADR-0018 §1 indexing ``i * cols + j``.
int verifyTopology(vtkCellArray* cells, unsigned int rows, unsigned int cols)
{
  CHECK_NOT_NULL(cells);
  const vtkIdType expected = expectedCellCount(rows, cols);
  CHECK_INT(cells->GetNumberOfCells(), expected);

  vtkNew<vtkIdList> ids;
  vtkIdType cellIndex = 0;
  cells->InitTraversal();
  for (unsigned int i = 0; i + 1 < rows; ++i)
  {
    for (unsigned int j = 0; j + 1 < cols; ++j)
    {
      const int hasNext = cells->GetNextCell(ids);
      if (!hasNext)
      {
        std::cerr << "Cell array exhausted at (i=" << i << ", j=" << j
                  << "); expected " << expected << " cells\n";
        return EXIT_FAILURE;
      }
      CHECK_INT(ids->GetNumberOfIds(), 5);
      // Row-major indexing per ADR-0018 §1: flat = row * cols + col.
      CHECK_INT(static_cast<int>(ids->GetId(0)), static_cast<int>(i * cols + j));
      CHECK_INT(static_cast<int>(ids->GetId(1)), static_cast<int>(i * cols + j + 1));
      CHECK_INT(static_cast<int>(ids->GetId(2)), static_cast<int>((i + 1) * cols + j + 1));
      CHECK_INT(static_cast<int>(ids->GetId(3)), static_cast<int>((i + 1) * cols + j));
      CHECK_INT(static_cast<int>(ids->GetId(4)), static_cast<int>(i * cols + j));
      ++cellIndex;
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
    vtkSlicerBezierSurfaceRepresentation3D::BuildControlPolygonCells(4, 4);
  CHECK_EXIT_SUCCESS(verifyTopology(cells, 4, 4));

  // Spot-check: the top-left quad (i=0, j=0) must reference point ids
  // {0, 1, 5, 4, 0}; the bottom-right quad (i=2, j=2) must reference
  // {10, 11, 15, 14, 10}.  Pre-fix code happens to match the 4×4 case
  // (it was hard-coded to stride 4), so this is a regression sentinel
  // rather than a red-on-arrival check.
  cells->InitTraversal();
  vtkNew<vtkIdList> first;
  CHECK_BOOL(cells->GetNextCell(first) != 0, true);
  CHECK_INT(static_cast<int>(first->GetId(0)), 0);
  CHECK_INT(static_cast<int>(first->GetId(2)), 5);

  // Walk to the last cell (index 8).
  vtkNew<vtkIdList> last;
  for (int c = 0; c < 8; ++c)
  {
    CHECK_BOOL(cells->GetNextCell(last) != 0, true);
  }
  CHECK_INT(static_cast<int>(last->GetId(0)), 10);
  CHECK_INT(static_cast<int>(last->GetId(2)), 15);
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
    vtkSlicerBezierSurfaceRepresentation3D::BuildControlPolygonCells(3, 3);
  CHECK_EXIT_SUCCESS(verifyTopology(cells, 3, 3));

  // Spot-check: the top-left quad (i=0, j=0) must reference point ids
  // {0, 1, 4, 3, 0}; the bottom-right quad (i=1, j=1) must reference
  // {4, 5, 8, 7, 4}.  Both are within the [0, 8] valid range of a
  // 9-point control grid — proves the fix.
  cells->InitTraversal();
  vtkNew<vtkIdList> first;
  CHECK_BOOL(cells->GetNextCell(first) != 0, true);
  CHECK_INT(static_cast<int>(first->GetId(0)), 0);
  CHECK_INT(static_cast<int>(first->GetId(1)), 1);
  CHECK_INT(static_cast<int>(first->GetId(2)), 4);
  CHECK_INT(static_cast<int>(first->GetId(3)), 3);
  CHECK_INT(static_cast<int>(first->GetId(4)), 0);

  // Walk to the last cell (index 3 — total 4 cells for a 3×3 grid).
  vtkNew<vtkIdList> last;
  for (int c = 0; c < 3; ++c)
  {
    CHECK_BOOL(cells->GetNextCell(last) != 0, true);
  }
  CHECK_INT(static_cast<int>(last->GetId(0)), 4);
  CHECK_INT(static_cast<int>(last->GetId(1)), 5);
  CHECK_INT(static_cast<int>(last->GetId(2)), 8);
  CHECK_INT(static_cast<int>(last->GetId(3)), 7);

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
  CHECK_INT(static_cast<int>(maxId), 8);
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
    vtkSlicerBezierSurfaceRepresentation3D::BuildControlPolygonCells(2, 2);
  CHECK_NOT_NULL(tooSmall);
  CHECK_INT(tooSmall->GetNumberOfCells(), 0);

  // Above the closed set — would be NURBS territory per ADR-0018 §3.
  vtkSmartPointer<vtkCellArray> tooBig =
    vtkSlicerBezierSurfaceRepresentation3D::BuildControlPolygonCells(5, 5);
  CHECK_NOT_NULL(tooBig);
  CHECK_INT(tooBig->GetNumberOfCells(), 0);

  // Non-square — ADR-0018 §1 admits only square shapes (ring-symmetry
  // constraint).
  vtkSmartPointer<vtkCellArray> nonSquare =
    vtkSlicerBezierSurfaceRepresentation3D::BuildControlPolygonCells(3, 4);
  CHECK_NOT_NULL(nonSquare);
  CHECK_INT(nonSquare->GetNumberOfCells(), 0);

  vtkSmartPointer<vtkCellArray> nonSquareT =
    vtkSlicerBezierSurfaceRepresentation3D::BuildControlPolygonCells(4, 3);
  CHECK_NOT_NULL(nonSquareT);
  CHECK_INT(nonSquareT->GetNumberOfCells(), 0);

  TESTING_OUTPUT_ASSERT_WARNINGS_END();
  return EXIT_SUCCESS;
}

} // namespace

//------------------------------------------------------------------------------
int vtkSlicerBezierSurfaceRepresentation3DControlPolygonTest1(int, char*[])
{
  CHECK_EXIT_SUCCESS(test4x4Topology());
  CHECK_EXIT_SUCCESS(test3x3Topology());
  CHECK_EXIT_SUCCESS(testInvalidShapesRejected());

  std::cout << "vtkSlicerBezierSurfaceRepresentation3DControlPolygonTest1 completed successfully" << std::endl;
  return EXIT_SUCCESS;
}

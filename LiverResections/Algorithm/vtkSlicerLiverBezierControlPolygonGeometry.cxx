/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, Oslo University Hospital. All rights reserved.

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

==============================================================================*/

#include "vtkSlicerLiverBezierControlPolygonGeometry.h"

// VTK includes
#include <vtkCellArray.h>
#include <vtkObjectFactory.h>
#include <vtkPolyLine.h>

vtkStandardNewMacro(vtkSlicerLiverBezierControlPolygonGeometry);

//------------------------------------------------------------------------------
vtkSlicerLiverBezierControlPolygonGeometry::vtkSlicerLiverBezierControlPolygonGeometry() = default;

//------------------------------------------------------------------------------
vtkSlicerLiverBezierControlPolygonGeometry::~vtkSlicerLiverBezierControlPolygonGeometry() = default;

//------------------------------------------------------------------------------
void vtkSlicerLiverBezierControlPolygonGeometry::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);
}

//------------------------------------------------------------------------------
vtkSmartPointer<vtkCellArray> vtkSlicerLiverBezierControlPolygonGeometry::BuildControlPolygonCells(unsigned int rows, unsigned int cols)
{
  vtkSmartPointer<vtkCellArray> planeCells = vtkSmartPointer<vtkCellArray>::New();

  // ADR-0018 §1: the closed set of valid Bezier control-polygon shapes
  // for v2.0.0 is ``{(3, 3), (4, 4)}``.  Reject everything else early —
  // emitting a topology against an out-of-spec ``(rows, cols)`` would
  // produce a malformed control polygon at best and a heap OOB index
  // at worst.  The legacy v1 representation (16 control points,
  // see ``vtkSlicerBezierSurfaceRepresentation3D::UpdateControlPolygonGeometry``)
  // only ever calls this with ``(4, 4)``; the ``(3, 3)`` branch is
  // exercised directly by the unit test in
  // ``LiverResections/Algorithm/Testing/Cxx/`` to pin the dimension-
  // aware shape for the v2 binding that ADR-0018 enables.
  const bool validShape = (rows == 3 && cols == 3) || (rows == 4 && cols == 4);
  if (!validShape)
  {
    vtkGenericWarningMacro("vtkSlicerLiverBezierControlPolygonGeometry::BuildControlPolygonCells:"
                           " (rows, cols) = ("
                           << rows << ", " << cols
                           << ") is outside the"
                              " ADR-0018 §1 closed set {(3, 3), (4, 4)}; returning empty cell array.");
    return planeCells;
  }

  // Emit ``(rows - 1) * (cols - 1)`` closed quad polylines, each with
  // five point ids (last id repeats the first to close the quad).
  // Row-major indexing: point ``(i, j)`` has flat index ``i * cols + j``.
  for (unsigned int i = 0; i + 1 < rows; ++i)
  {
    for (unsigned int j = 0; j + 1 < cols; ++j)
    {
      vtkSmartPointer<vtkPolyLine> polyLine = vtkSmartPointer<vtkPolyLine>::New();
      polyLine->GetPointIds()->SetNumberOfIds(5);
      polyLine->GetPointIds()->SetId(0, i * cols + j);
      polyLine->GetPointIds()->SetId(1, i * cols + j + 1);
      polyLine->GetPointIds()->SetId(2, (i + 1) * cols + j + 1);
      polyLine->GetPointIds()->SetId(3, (i + 1) * cols + j);
      polyLine->GetPointIds()->SetId(4, i * cols + j);
      planeCells->InsertNextCell(polyLine);
    }
  }

  return planeCells;
}

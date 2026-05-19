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

  This file was originally developed for the Slicer-Liver extension as
  the Algorithm-library home of the Bezier control-polygon topology
  builder (per ADR-0015 §1 — pure-VTK helpers that are reachable from
  both the legacy ``LiverMarkups`` representations and the v2
  ``LiverResections`` representations).

==============================================================================*/

#ifndef __vtkSlicerLiverBezierControlPolygonGeometry_h_
#define __vtkSlicerLiverBezierControlPolygonGeometry_h_

#include "vtkSlicerLiverResectionsModuleAlgorithmExport.h"

// VTK includes
#include <vtkObject.h>
#include <vtkSmartPointer.h>

class vtkCellArray;

/**
 * \class vtkSlicerLiverBezierControlPolygonGeometry
 *
 * \brief Pure-VTK builder for the closed-quad cell-array topology of a
 * Bezier control polygon.
 *
 * Centralises the row-major control-polygon topology emission previously
 * duplicated in ``vtkSlicerBezierSurfaceRepresentation3D`` (legacy v1
 * binding under ``LiverMarkups/VTKWidgets/``) and the in-progress v2
 * binding under ``LiverResections/VTKWidgets/``.  Lives in the
 * Algorithm library so both bindings can call it without picking up an
 * MRML or Slicer dependency (per ADR-0015 §1 — Algorithm classes are
 * pure VTK).
 *
 * \par Contract
 *  - ``BuildControlPolygonCells(rows, cols)`` returns a
 *    ``vtkSmartPointer<vtkCellArray>`` populated with
 *    ``(rows - 1) * (cols - 1)`` closed-quad polylines.
 *  - Indexing is row-major: point ``(i, j)`` has flat index
 *    ``i * cols + j``.  Each emitted polyline has 5 ids that close the
 *    quad of lattice cell ``(i, j)``:
 *    ``[i*cols+j, i*cols+j+1, (i+1)*cols+j+1, (i+1)*cols+j, i*cols+j]``.
 *  - Per ADR-0018 §1 the closed set of valid shapes for v2.0.0 is
 *    ``{(3, 3), (4, 4)}``.  Any other ``(rows, cols)`` is rejected
 *    early with a ``vtkGenericWarningMacro`` and the function returns
 *    an empty (but non-null) cell array.  Mirrors the rejection
 *    behaviour of ``vtkMRMLBezierSurfaceNode::SetRows`` /
 *    ``SetCols``.
 *
 * \par MRML invariant
 *  No ``vtkMRMLNode`` references.  Per ADR-0015 §1 the Algorithm
 *  library is pure VTK; this class follows the same invariant so it
 *  remains reachable from both the LayerDM-bound v2 path and the
 *  legacy MRML-bound v1 path without inverting the dependency.
 */
class VTK_SLICER_LIVERRESECTIONS_MODULE_ALGORITHM_EXPORT vtkSlicerLiverBezierControlPolygonGeometry : public vtkObject
{
public:
  static vtkSlicerLiverBezierControlPolygonGeometry* New();
  vtkTypeMacro(vtkSlicerLiverBezierControlPolygonGeometry, vtkObject);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  /// Build the closed-quad ``vtkCellArray`` topology for a
  /// ``rows × cols`` Bezier control polygon, indexed row-major
  /// (``i * cols + j``).  Per ADR-0018 §1 the closed set of valid
  /// shapes is ``{(3, 3), (4, 4)}``; any other ``(rows, cols)``
  /// emits a ``vtkGenericWarningMacro`` and returns an empty cell
  /// array.
  ///
  /// Each emitted polyline carries five point ids closing the quad
  /// of the ``(i, j)`` lattice cell.  The number of cells is
  /// ``(rows - 1) * (cols - 1)`` — four for 3×3, nine for 4×4.
  static vtkSmartPointer<vtkCellArray> BuildControlPolygonCells(unsigned int rows, unsigned int cols);

protected:
  vtkSlicerLiverBezierControlPolygonGeometry();
  ~vtkSlicerLiverBezierControlPolygonGeometry() override;

private:
  vtkSlicerLiverBezierControlPolygonGeometry(const vtkSlicerLiverBezierControlPolygonGeometry&) = delete;
  void operator=(const vtkSlicerLiverBezierControlPolygonGeometry&) = delete;
};

#endif // __vtkSlicerLiverBezierControlPolygonGeometry_h_

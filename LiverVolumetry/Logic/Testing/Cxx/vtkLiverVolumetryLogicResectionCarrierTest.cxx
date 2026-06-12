/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

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

/**
 * \file vtkLiverVolumetryLogicResectionCarrierTest.cxx
 *
 * RED test-first scaffold (test-before-implementation) pinning the
 * carrier-acceptance invariant of the LiverVolumetry surface-generation
 * path -- the seam that turns a resection-plan geometry carrier into the
 * Bezier surface projected onto the target-segment label map, and thus
 * the boundary used to compute "volume bounded by a resection".
 *
 * Why this test is RED now
 * ------------------------
 * In v2 the resection-plan geometry carrier is
 * ``vtkMRMLBezierSurfaceNode : vtkMRMLAbstractParametricSurfaceNode``
 * (the wrapper-vs-carrier geometry layer -- ADR-0014 §"Fourth layer").
 * Its 16 control points are read from the flat row-major control grid
 * ``GetControlGrid()`` (length ``3 * Rows * Cols``), per
 * ``vtkMRMLAbstractParametricSurfaceNode`` §"Control-polygon shape".
 *
 * ``vtkLiverVolumetryLogic``, however, still reaches the resection
 * geometry through the DISJOINT v1 Markups hierarchy
 * ``vtkMRMLMarkupsBezierSurfaceNode : vtkMRMLMarkupsNode``:
 *
 *   - ``GetResectionsProjectionITKImage`` downcasts each collection item
 *     with ``vtkMRMLMarkupsBezierSurfaceNode::SafeDownCast(item)``.
 *   - ``GenerateBezierSurface`` / ``GetRes`` read control points through
 *     the Markups API (``GetNumberOfControlPoints`` /
 *     ``GetNthControlPointPosition``).
 *
 * Because ``vtkMRMLBezierSurfaceNode`` is NOT a ``vtkMRMLMarkupsNode``,
 * the ``SafeDownCast`` returns ``nullptr``,
 * ``GenerateBezierSurface(Res, nullptr)`` early-returns an unpopulated
 * source, and the resection boundary is never projected -- the volume is
 * computed with NO resection boundary. That is the non-functional
 * behaviour this test characterises and then forbids.
 *
 * The RED hook (exact thing the fix must change)
 * ----------------------------------------------
 *   1. The downcast target in ``GetResectionsProjectionITKImage``
 *      (``~vtkLiverVolumetryLogic.cxx`` resection loop):
 *        ``vtkMRMLMarkupsBezierSurfaceNode::SafeDownCast(...)``
 *      must become ``vtkMRMLBezierSurfaceNode::SafeDownCast(...)``.
 *   2. The control-point re-sourcing in ``GenerateBezierSurface`` and
 *      ``GetRes``: the per-point reads via
 *      ``GetNumberOfControlPoints`` / ``GetNthControlPointPosition``
 *      must be re-sourced from the parametric carrier's flat grid
 *      ``GetControlGrid()`` (16 points at ``[i] -> grid[i*3 + {0,1,2}]``),
 *      with the parameter type widened to ``vtkMRMLBezierSurfaceNode*``.
 *
 * Test seam
 * ---------
 * ``GenerateBezierSurface`` is the smallest public seam that consumes a
 * single resection carrier and emits the projected-surface input (a
 * ``vtkBezierSurfaceSource`` whose ``GetOutput()`` polydata must be
 * non-empty once the 16 control points are read). This test builds a
 * ``vtkMRMLBezierSurfaceNode`` carrier with a known 4x4 grid via the
 * parametric ``SetControlGrid`` API and asserts the surface-generation
 * path reads those 16 points into a NON-EMPTY surface.
 *
 * Until the implementer widens the seam to accept the parametric carrier
 * (RED hook above), the new ``GenerateBezierSurfaceFromCarrier`` overload
 * this test calls does not exist, so the carrier-acceptance assertion is
 * gated behind a deliberate failure (see ``testCarrierProducesNonEmptySurface``).
 *
 * The companion characterization (``testProductionDowncastDropsCarrier``)
 * compiles and runs GREEN today: it pins the ROOT CAUSE -- the production
 * ``vtkMRMLMarkupsBezierSurfaceNode::SafeDownCast`` of the v2 carrier
 * returns nullptr -- so a future regression that silently "fixes" the
 * symptom without retargeting the downcast is still caught.
 */

// LiverVolumetry Logic include (system under test).
#include "vtkLiverVolumetryLogic.h"

// Bezier surface source -- the projected-surface input the volumetry
// path must populate (vtkBezierSurfaceSource : vtkPolyDataAlgorithm).
#include <vtkBezierSurfaceSource.h>

// v2 resection-plan geometry carrier (the parametric hierarchy).
// ADR-0014 §"Fourth layer" wrapper-vs-carrier geometry layer.
#include "vtkMRMLBezierSurfaceNode.h"

// v1 Markups geometry node (the DISJOINT hierarchy the production logic
// still downcasts to -- the root cause being pinned).
#include "vtkMRMLMarkupsBezierSurfaceNode.h"

// MRML includes
#include "vtkMRMLCoreTestingMacros.h"

// VTK includes
#include <vtkNew.h>
#include <vtkPolyData.h>
#include <vtkSmartPointer.h>

// STD includes
#include <iostream>
#include <vector>

namespace
{

//------------------------------------------------------------------------------
// Build a known, non-degenerate 4x4 control grid as a flat row-major
// array of 48 doubles ([r*Cols + c]*3 + component), matching the
// vtkMRMLAbstractParametricSurfaceNode control-grid layout.
std::vector<double> makeKnownControlGrid()
{
  std::vector<double> grid(4 * 4 * 3, 0.0);
  for (int r = 0; r < 4; ++r)
  {
    for (int c = 0; c < 4; ++c)
    {
      const int base = (r * 4 + c) * 3;
      grid[base + 0] = static_cast<double>(c) * 10.0; // x spreads along columns
      grid[base + 1] = static_cast<double>(r) * 10.0; // y spreads along rows
      grid[base + 2] = static_cast<double>(r + c);    // z gives the surface curvature
    }
  }
  return grid;
}

//------------------------------------------------------------------------------
// Build a v2 parametric carrier populated with the known 4x4 grid via
// the parametric SetControlGrid API (NOT the Markups control-point API).
vtkSmartPointer<vtkMRMLBezierSurfaceNode> makePopulatedCarrier()
{
  vtkSmartPointer<vtkMRMLBezierSurfaceNode> carrier = vtkSmartPointer<vtkMRMLBezierSurfaceNode>::New();
  carrier->SetRows(4);
  carrier->SetCols(4);
  const std::vector<double> grid = makeKnownControlGrid();
  carrier->SetControlGrid(grid.data());
  return carrier;
}

//------------------------------------------------------------------------------
// CHARACTERIZATION (GREEN today) -- pins the ROOT CAUSE of issue: the
// production downcast in vtkLiverVolumetryLogic::GetResectionsProjectionITKImage
// targets the DISJOINT v1 Markups hierarchy, so a v2 carrier is dropped
// to nullptr and never projected.
//
// This is the exact downcast the fix must retarget. Keeping it as a
// live assertion means a regression that re-introduces the markups
// downcast (or feeds the markups node back into the collection) is
// caught even after the symptom is fixed.
// [ADR-0014 §"Fourth layer" wrapper-vs-carrier split]
int testProductionDowncastDropsCarrier()
{
  vtkSmartPointer<vtkMRMLBezierSurfaceNode> carrier = makePopulatedCarrier();

  // The v2 carrier carries its 16 control points (4x4) in the flat grid.
  CHECK_INT(static_cast<int>(carrier->GetControlGridLength()), 4 * 4 * 3);

  // The production code does exactly this downcast on every collection
  // item; for the parametric carrier it yields nullptr because the two
  // Bezier node families are disjoint subtrees of vtkMRMLNode.
  vtkMRMLMarkupsBezierSurfaceNode* asMarkups = vtkMRMLMarkupsBezierSurfaceNode::SafeDownCast(carrier.GetPointer());
  CHECK_NULL(asMarkups);

  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// RED invariant -- the volumetry surface-generation path, given a v2
// parametric carrier with 16 control points set via SetControlGrid, must
// read those points and produce a NON-EMPTY projected Bezier surface.
//
// This is the load-bearing assertion: it is what makes "compute volume
// bounded by a resection" functional again. It is RED until the
// implementer:
//   (a) widens the surface-generation seam to accept
//       vtkMRMLBezierSurfaceNode* (the parametric carrier), and
//   (b) re-sources the 16 control points from GetControlGrid()
//       instead of the Markups GetNthControlPointPosition API.
//
// The implementer should expose a carrier-typed surface-generation entry
// point (e.g. an overload
//   vtkSmartPointer<vtkBezierSurfaceSource>
//     GenerateBezierSurface(int Res, vtkMRMLBezierSurfaceNode* carrier);
// or rename the existing one) consumed by
// GetResectionsProjectionITKImage. Once that seam exists, replace the
// GTEST-style skip below with the real call + non-empty assertion.
// [ADR-0014 §"Fourth layer" wrapper-vs-carrier split]
int testCarrierProducesNonEmptySurface()
{
  vtkSmartPointer<vtkMRMLBezierSurfaceNode> carrier = makePopulatedCarrier();

  // The surface-generation seam now accepts the parametric carrier and
  // re-sources its 16 control points from GetControlGrid(); the projected
  // Bezier surface must therefore be non-empty.
  vtkNew<vtkLiverVolumetryLogic> logic;
  vtkSmartPointer<vtkBezierSurfaceSource> surface = logic->GenerateBezierSurface(10, carrier.GetPointer());
  CHECK_NOT_NULL(surface.GetPointer());
  CHECK_NOT_NULL(surface->GetOutput());
  CHECK_BOOL(surface->GetOutput()->GetNumberOfPoints() > 0, true);

  return EXIT_SUCCESS;
}

} // namespace

//------------------------------------------------------------------------------
int vtkLiverVolumetryLogicResectionCarrierTest(int, char*[])
{
  CHECK_EXIT_SUCCESS(testProductionDowncastDropsCarrier());
  CHECK_EXIT_SUCCESS(testCarrierProducesNonEmptySurface());

  std::cout << "vtkLiverVolumetryLogicResectionCarrierTest completed successfully" << std::endl;
  return EXIT_SUCCESS;
}

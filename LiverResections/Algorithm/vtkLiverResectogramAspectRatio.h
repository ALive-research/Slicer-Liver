/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  This file was originally developed for the Slicer-Liver extension as
  the Algorithm-library home of the resectogram aspect-ratio helper
  extracted from the v1 ``vtkSlicerBezierSurfaceRepresentation3D::Ratio``
  binding (per ADR-0015 §1 — pure-VTK helpers reachable from both the
  legacy ``LiverMarkups`` representations and the v2 ``LiverResections``
  Pipeline representations, with no MRML or VTKWidgets linkage).

==============================================================================*/

#ifndef __vtkLiverResectogramAspectRatio_h_
#define __vtkLiverResectogramAspectRatio_h_

#include "vtkSlicerLiverResectionsModuleAlgorithmExport.h"

// VTK includes
#include <vtkObject.h>

class vtkPoints;

/**
 * \class vtkLiverResectogramAspectRatio
 *
 * \brief Pure-VTK helper that computes the resectogram's anisotropic
 * aspect-ratio scaling from a sampled Bezier surface.
 *
 * Centralises the arc-length computation previously embedded in
 * ``vtkSlicerBezierSurfaceRepresentation3D::Ratio(bool)`` (legacy v1
 * binding under ``LiverMarkups/VTKWidgets/``).  Lives in the Algorithm
 * library so the LayerDM-bound resectogram Representation and any other
 * caller can reach it without picking up an MRML or OpenGL dependency
 * (per ADR-0015 §1 — Algorithm classes are pure VTK).
 *
 * \par Contract
 *  - ``ComputeAspectRatio(sampledSurface, samplesU, samplesV,
 *    flexibleBoundary, ratioOut)`` walks the sampled surface grid,
 *    indexed row-major (sample ``(i, j)`` has flat index
 *    ``i * samplesV + j``).  It sums the Euclidean arc-length along the
 *    first u-edge (``i`` running ``0..samplesU-1`` at ``j = 0``) and
 *    along the first v-edge (``j`` running ``0..samplesV-1`` at
 *    ``i = 0``), then normalises the LONGER axis to 1:
 *
 *        if (disU >= disV) { ratioOut = { 1, disV / disU }; }
 *        else              { ratioOut = { disU / disV, 1 }; }
 *
 *  - When ``flexibleBoundary`` is false the function short-circuits to
 *    the isotropic ``{1, 1}`` (the v1 else-branch).
 *  - A square domain yields ``{1, 1}`` (disU == disV); this is also the
 *    not-flexible answer, so the two are observationally identical for a
 *    square domain.
 *
 * \par MRML invariant
 *  No ``vtkMRMLNode`` references.  Per ADR-0015 §1 the Algorithm library
 *  is pure VTK; this class follows the same invariant so it remains
 *  reachable from both the LayerDM-bound v2 path and the legacy
 *  MRML-bound v1 path without inverting the dependency.  Per ADR-0013 §6
 *  the resulting scaling is Representation-owned state.
 */
class VTK_SLICER_LIVERRESECTIONS_MODULE_ALGORITHM_EXPORT vtkLiverResectogramAspectRatio : public vtkObject
{
public:
  static vtkLiverResectogramAspectRatio* New();
  vtkTypeMacro(vtkLiverResectogramAspectRatio, vtkObject);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  /// Compute the resectogram's anisotropic aspect-ratio scaling from a
  /// row-major sampled surface grid (sample ``(i, j)`` at flat index
  /// ``i * samplesV + j``).  Sums arc-length along the first u-edge and
  /// first v-edge, then normalises the longer axis to 1.  When
  /// ``flexibleBoundary`` is false, forces the isotropic ``{1, 1}``.
  /// Writes the result into ``ratioOut[2]``.
  static void ComputeAspectRatio(vtkPoints* sampledSurface, unsigned int samplesU, unsigned int samplesV, bool flexibleBoundary, double ratioOut[2]);

protected:
  vtkLiverResectogramAspectRatio();
  ~vtkLiverResectogramAspectRatio() override;

private:
  vtkLiverResectogramAspectRatio(const vtkLiverResectogramAspectRatio&) = delete;
  void operator=(const vtkLiverResectogramAspectRatio&) = delete;
};

#endif // __vtkLiverResectogramAspectRatio_h_

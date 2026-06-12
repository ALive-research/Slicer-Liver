/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  This file was originally developed for the Slicer-Liver extension as
  the Algorithm-library home of the resectogram pixel -> (u, v) mapping
  the ADR-0025 locator producer consumes (per ADR-0015 §1 — pure-VTK
  helpers reachable from the v2 ``LiverResections`` Pipeline
  representations with no MRML or OpenGL linkage).

==============================================================================*/

#ifndef __vtkLiverResectogramPixelMapping_h_
#define __vtkLiverResectogramPixelMapping_h_

#include "vtkSlicerLiverResectionsModuleAlgorithmExport.h"

// VTK includes
#include <vtkObject.h>

/**
 * \class vtkLiverResectogramPixelMapping
 *
 * \brief Pure-VTK helper that inverts the resectogram's on-screen
 * placement to recover the Bezier ``(u, v)`` parameter pair from a
 * viewport pixel.
 *
 * ADR-0025 §Context establishes that the resectogram is a 1:1 image of
 * the Bezier ``(u, v)`` parameter domain: a resectogram pixel maps to a
 * ``(u, v)`` pair maps to a world point by direct Bezier surface
 * evaluation — an exact correspondence, no geometric search.  The
 * locator architecture (issue #414, depends on T3) relies on this
 * mapping being stable.
 *
 * \par Contract
 *  - The flattened quad fills the viewport; ``(u, v) = (0, 0)`` at the
 *    bottom-left corner and ``(1, 1)`` at the top-right.
 *  - The anisotropic ``matRatio`` ``{su, sv}`` scales the quad about the
 *    viewport centre (the v1 vertex shader multiplies ``gl_Position`` by
 *    a matrix with ``m[0][0] = su`` / ``m[1][1] = sv``;
 *    ``vtkOpenGLResection2DPolyDataMapper``, post-relocation home
 *    ``LiverResections/VTKWidgets/``).  ``PixelToUV`` inverts that
 *    placement: a pixel at the viewport centre maps to ``(0.5, 0.5)``
 *    for ANY ratio (the scaling fixed point); off-centre pixels divide
 *    out the ratio.
 *  - For an isotropic ``{1, 1}`` the map is the plain linear
 *    ``u = pixel.x / width``, ``v = pixel.y / height``.
 *
 * \par MRML invariant
 *  No ``vtkMRMLNode`` references.  Per ADR-0015 §1 the Algorithm library
 *  is pure VTK.
 */
class VTK_SLICER_LIVERRESECTIONS_MODULE_ALGORITHM_EXPORT vtkLiverResectogramPixelMapping : public vtkObject
{
public:
  static vtkLiverResectogramPixelMapping* New();
  vtkTypeMacro(vtkLiverResectogramPixelMapping, vtkObject);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  /// Map a viewport ``pixel`` (origin bottom-left) to the Bezier
  /// ``(u, v)`` parameter pair in ``[0, 1]^2``, inverting the
  /// anisotropic ``matRatio`` ``{su, sv}`` placement about the viewport
  /// centre.  ``viewportSize`` is ``{width, height}`` in pixels.  Writes
  /// the result into ``uvOut[2]``.
  static void PixelToUV(const double pixel[2], const int viewportSize[2], const double matRatio[2], double uvOut[2]);

protected:
  vtkLiverResectogramPixelMapping();
  ~vtkLiverResectogramPixelMapping() override;

private:
  vtkLiverResectogramPixelMapping(const vtkLiverResectogramPixelMapping&) = delete;
  void operator=(const vtkLiverResectogramPixelMapping&) = delete;
};

#endif // __vtkLiverResectogramPixelMapping_h_

/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  This file was originally developed for the Slicer-Liver extension as
  the Algorithm-library adapter between VTK and the vendored PoissonRecon
  core (per ADR-0040 — screened Poisson surface reconstruction from a
  segmentation, and ADR-0015 §1 — pure-VTK helpers with no MRML or
  OpenGL linkage).

==============================================================================*/

#ifndef __vtkLiverPoissonSurfaceReconstruction_h_
#define __vtkLiverPoissonSurfaceReconstruction_h_

#include "vtkSlicerLiverResectionsModuleAlgorithmExport.h"

// VTK includes
#include <vtkObject.h>

class vtkPolyData;

/// \brief Screened Poisson surface reconstruction from an oriented point cloud.
///
/// Wraps the vendored PoissonRecon core (Kazhdan; see
/// ``PoissonRecon/README.md``) behind a VTK-shaped, Python-wrappable
/// entry point.  The upstream templates never cross this boundary: the
/// whole point of the adapter is that callers see ``vtkPolyData`` and
/// integers, which is what ADR-0040 §5 requires and what makes the
/// algorithm reachable from the Python that drives this extension
/// (ADR-0004).
///
/// The input is an ORIENTED point cloud -- points plus per-point
/// normals.  Normals are not an optimisation here, they are the signal:
/// Poisson reconstruction solves for the indicator function whose
/// gradient best matches them, so a cloud without normals has nothing to
/// reconstruct from and is rejected rather than guessed at.
/// ``vtkLiverOrientedPointCloudExtractor`` produces clouds in this shape
/// straight from a segmentation.
class VTK_SLICER_LIVERRESECTIONS_MODULE_ALGORITHM_EXPORT vtkLiverPoissonSurfaceReconstruction : public vtkObject
{
public:
  static vtkLiverPoissonSurfaceReconstruction* New();
  vtkTypeMacro(vtkLiverPoissonSurfaceReconstruction, vtkObject);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  /// Octree depth used when a caller does not choose one.
  ///
  /// **7, not upstream's 8.**  Depth is a resolution knob, and past a
  /// point more resolution means fitting the labelmap's own voxel
  /// staircase rather than the anatomy it samples.  On a CT-resolution
  /// liver, depths 8 and 9 tracked the segmentation WORSE than 7 by a
  /// symmetric surface distance (ADR-0040 §"Phase 1 result").  Changing
  /// this is a deliberate edit backed by fresh measurement, not a drift
  /// back toward the upstream default.
  static int GetDefaultDepth();

  /// Reconstruct a closed surface from ``orientedCloud`` into ``output``.
  ///
  /// ``orientedCloud`` must carry point normals; ``depth`` is the octree
  /// depth (see GetDefaultDepth()).  ``output`` receives points, the
  /// reconstructed polygons, and the per-vertex normals the solver
  /// produces -- these come from the fitted implicit function's
  /// gradient, so they describe the SOLVED surface rather than being
  /// re-estimated from the output triangles afterwards.
  ///
  /// Returns false and leaves ``output`` EMPTY on any invalid input: a
  /// null argument, a cloud with no points, a cloud with no normals, or
  /// a depth outside [1, 14].  Empty rather than stale, so a caller that
  /// ignores the return value renders nothing instead of the previous
  /// result.
  static bool Reconstruct(vtkPolyData* orientedCloud, int depth, vtkPolyData* output);

protected:
  vtkLiverPoissonSurfaceReconstruction();
  ~vtkLiverPoissonSurfaceReconstruction() override;

private:
  vtkLiverPoissonSurfaceReconstruction(const vtkLiverPoissonSurfaceReconstruction&) = delete;
  void operator=(const vtkLiverPoissonSurfaceReconstruction&) = delete;
};

#endif // __vtkLiverPoissonSurfaceReconstruction_h_

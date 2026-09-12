/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  This file was originally developed for the Slicer-Liver extension as
  the Algorithm-library home of the oriented-point-cloud extraction that
  feeds Poisson Surface Reconstruction (ADR-0040; ADR-0015 §1 — a pure
  computation helper with no MRML or VTKWidgets linkage).

==============================================================================*/

#ifndef __vtkliverorientedpointcloudextractor_h_
#define __vtkliverorientedpointcloudextractor_h_

#include "vtkSlicerLiverResectionsModuleAlgorithmExport.h"

// VTK includes
#include <vtkObject.h>

class vtkImageData;
class vtkMatrix4x4;
class vtkPolyData;

/// \brief Oriented point cloud from a binary labelmap, for PSR input.
///
/// Poisson Surface Reconstruction consumes points carrying OUTWARD
/// NORMALS.  The normals come from the labelmap's own intensity
/// gradient, not from a triangulated surface: at a labelmap boundary the
/// gradient IS the outward normal, so no intermediate marching-cubes
/// surface is built and the normals do not inherit the staircase
/// artefacts PSR exists to remove (ADR-0040 §Decision 2).
///
/// The gradient is an ITK Sobel operator rather than a raw central
/// difference.  Sobel's built-in smoothing matters on a BINARY mask,
/// where a bare difference gives normals quantised to a handful of
/// lattice directions.
class VTK_SLICER_LIVERRESECTIONS_MODULE_ALGORITHM_EXPORT vtkLiverOrientedPointCloudExtractor : public vtkObject
{
public:
  static vtkLiverOrientedPointCloudExtractor* New();
  vtkTypeMacro(vtkLiverOrientedPointCloudExtractor, vtkObject);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  /// Extract oriented points from ``labelMap`` into ``output``.
  ///
  /// \param labelMap    binary or multi-label volume; voxels equal to
  ///                    ``label`` form the object.
  /// \param ijkToRAS    voxel-to-world matrix; points are emitted in
  ///                    world millimetres and normals are rotated by its
  ///                    direction part (translation and scale removed),
  ///                    so a caller never has to fix them up.
  /// \param label       the label value to extract.
  /// \param maxPoints   upper bound on emitted points; a stride keeps
  ///                    the subsample DETERMINISTIC, so a test asserting
  ///                    on the output is reproducible.  Zero means no
  ///                    limit.
  /// \param output      receives the points plus a float "Normals" array
  ///                    on its point data.
  ///
  /// \return false (leaving ``output`` empty) on a null argument, an
  /// unsupported scalar type, or a label with no boundary — a caller
  /// gets an empty cloud rather than an exception.
  ///
  /// Signature is deliberately wrappable: VTK objects and scalars only.
  /// A PSR entry point unreachable from Python would be useless here,
  /// and this project has shipped that mistake twice (#636, #640).
  static bool Extract(vtkImageData* labelMap, vtkMatrix4x4* ijkToRAS, int label, vtkIdType maxPoints, vtkPolyData* output);

protected:
  vtkLiverOrientedPointCloudExtractor();
  ~vtkLiverOrientedPointCloudExtractor() override;

private:
  vtkLiverOrientedPointCloudExtractor(const vtkLiverOrientedPointCloudExtractor&) = delete;
  void operator=(const vtkLiverOrientedPointCloudExtractor&) = delete;
};

#endif // __vtkliverorientedpointcloudextractor_h_

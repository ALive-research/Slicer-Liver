/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  This file was originally developed for the Slicer-Liver extension
  as part of the T2 LiverResections all-in migration (Stack 1 of the
  v2.0.0 release tracker — see ADR-0015).

==============================================================================*/

#ifndef __vtkLiverSpheroidRingExtractor_h_
#define __vtkLiverSpheroidRingExtractor_h_

#include "vtkSlicerLiverResectionsModuleAlgorithmExport.h"

// VTK includes
#include <vtkPolyDataAlgorithm.h>

/**
 * \class vtkLiverSpheroidRingExtractor
 *
 * \brief Extract the ordered intersection ring of a spheroid (general
 * triaxial ellipsoid) with a target liver mesh.
 *
 * \par Role in the Init→Planning pipeline
 *
 * This class produces a **discrete, ordered ring** suitable for
 * downstream fitting (`vtkLiverContourParameterizer` →
 * `vtkLiverBezierFitter`).  It is the **data-extraction** path —
 * **not** the surgeon-facing visualisation path.
 *
 * The visual contour the surgeon sees during Init mode is rendered
 * by a separate OpenGL mapper that evaluates the implicit surface
 * per-fragment on the GPU
 * (`vtkOpenGLDistanceContourPolyDataMapper`, relocated from
 * `LiverMarkups/VTKWidgets/` per ADR-0014 §3).  The two paths
 * coexist on the same display-node parameters but produce different
 * artefacts:
 *
 *   - Shader: continuous per-fragment rendering, GPU-bound,
 *     per-frame cost.
 *   - This class: discrete `vtkPolyData` ring, CPU-bound, one-shot
 *     cost per state transition.
 *
 * \par Parameter consistency with the shader
 *
 * The shader expands the spheroid implicit as
 * `((x-cx)/rx)² + ((y-cy)/ry)² + ((z-cz)/rz)² = 1` directly in
 * GLSL.  This class expands the same implicit into
 * `vtkQuadric`'s `a0…a9` coefficient form — and `vtkQuadric`
 * evaluates `F = a0·x² + … + a6·x + a7·y + a8·z + a9` with **no**
 * implicit factor of 2 on the linear terms (see `vtkQuadric.h`).
 * Failing to multiply the linear coefficients by 2 produces a
 * subtly wrong surface; see commit `4eba6e1` for the off-by-2 fix
 * that surfaced this constraint.
 *
 * Stack 4 (LayerDM Pipeline + Representations, per ADR-0014 §2)
 * is responsible for ensuring the surgeon-visible contour and the
 * extracted ring describe the same surface — i.e. parameter→shader
 * and parameter→`vtkQuadric` adapters yield mathematically identical
 * implicit surfaces.
 *
 * \par Extraction tolerance — mesh-resolution-bounded
 *
 * The output ring lives on input-mesh edges via linear interpolation
 * inside `vtkCutter`.  The residual `|F(p)|` at output points is
 * bounded by `(1/8) · max|F″| · h²` where `h` is the input mesh edge
 * length.  At typical liver mesh density (`h ≈ 0.1` for a 64×64
 * unit-sphere tessellation, `|F″| ~ 3`), the bound is ~4 × 10⁻³ —
 * orders of magnitude below clinical mm-scale tolerances but
 * orders of magnitude above the bit-equivalence floor the other
 * algorithm-library tests target.  This is the floor of mesh
 * resolution, not a defect to fix.
 *
 * Implementation strategy: use a ``vtkQuadric`` implicit function
 * representing the spheroid as a level set, drive a ``vtkCutter``
 * against the target mesh, then chain segments into an ordered ring
 * via ``vtkStripper``.  The cut is the ring where the quadric
 * evaluates to zero on the mesh surface.
 *
 * Parameters:
 *  - ``Center`` — spheroid centre (RAS).
 *  - ``RadiusX`` / ``RadiusY`` / ``RadiusZ`` — spheroid semi-axes
 *    along the canonical RAS axes.  (General-orientation rotation is
 *    deferred to a future stack; the Init→Planning consumers in
 *    Stack 4 use axis-aligned spheroids per the existing widget.)
 *
 * \par MRML invariant
 *  No ``vtkMRMLNode`` references.  Per ADR-0015.
 */
class VTK_SLICER_LIVERRESECTIONS_MODULE_ALGORITHM_EXPORT vtkLiverSpheroidRingExtractor
  : public vtkPolyDataAlgorithm
{
 public:
  static vtkLiverSpheroidRingExtractor *New();
  vtkTypeMacro(vtkLiverSpheroidRingExtractor, vtkPolyDataAlgorithm);
  void PrintSelf(ostream &os, vtkIndent indent) override;

  vtkSetVector3Macro(Center, double);
  vtkGetVector3Macro(Center, double);

  vtkSetMacro(RadiusX, double);
  vtkGetMacro(RadiusX, double);
  vtkSetMacro(RadiusY, double);
  vtkGetMacro(RadiusY, double);
  vtkSetMacro(RadiusZ, double);
  vtkGetMacro(RadiusZ, double);

 protected:
  vtkLiverSpheroidRingExtractor();
  ~vtkLiverSpheroidRingExtractor() override;

  int FillInputPortInformation(int port, vtkInformation *info) override;
  int RequestData(vtkInformation *,
                  vtkInformationVector **,
                  vtkInformationVector *) override;

 private:
  vtkLiverSpheroidRingExtractor(const vtkLiverSpheroidRingExtractor &) = delete;
  void operator=(const vtkLiverSpheroidRingExtractor &) = delete;

  double Center[3];
  double RadiusX;
  double RadiusY;
  double RadiusZ;
};

#endif  // __vtkLiverSpheroidRingExtractor_h_

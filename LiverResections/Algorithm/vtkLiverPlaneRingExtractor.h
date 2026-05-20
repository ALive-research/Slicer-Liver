/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  This file was originally developed for the Slicer-Liver extension
  as part of the T2 LiverResections all-in migration (Stack 1 of the
  v2.0.0 release tracker — see ADR-0015).

==============================================================================*/

#ifndef __vtkLiverPlaneRingExtractor_h_
#define __vtkLiverPlaneRingExtractor_h_

#include "vtkSlicerLiverResectionsModuleAlgorithmExport.h"

// VTK includes
#include <vtkPolyDataAlgorithm.h>

/**
 * \class vtkLiverPlaneRingExtractor
 *
 * \brief Extract the ordered intersection ring of an oriented plane
 * with a target liver mesh.
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
 * (`vtkOpenGLSlicingContourPolyDataMapper`, relocated from
 * `LiverMarkups/VTKWidgets/` per ADR-0014 §3).  The two paths
 * coexist on the same display-node parameters but produce different
 * artefacts:
 *
 *   - Shader: continuous per-fragment rendering, GPU-bound,
 *     per-frame cost.
 *   - This class: discrete `vtkPolyData` ring, CPU-bound, one-shot
 *     cost per state transition.
 *
 * Stack 4 (LayerDM Pipeline + Representations, per ADR-0014 §2)
 * is responsible for ensuring the same `vtkPlane` parameters reach
 * both the shader and this extractor, so the surgeon-visible
 * contour and the extracted ring describe the same surface.
 *
 * Internally uses ``vtkPlane`` + ``vtkCutter`` to produce the
 * intersection polydata, then ``vtkStripper`` to chain the cut
 * fragments into a closed polyline (cell-array form).  The output is a
 * ``vtkPolyData`` containing the ring points + a single
 * ``vtkPolyLine`` cell encoding the traversal order.
 *
 * Parameters:
 *  - ``Origin`` — point on the cutting plane (RAS).
 *  - ``Normal`` — unit-length plane normal (RAS).
 *
 * \par MRML invariant
 *  No ``vtkMRMLNode`` references.  Per ADR-0015 the algorithm library
 *  is pure VTK; MRML lives in the Python orchestration layer.
 */
class VTK_SLICER_LIVERRESECTIONS_MODULE_ALGORITHM_EXPORT vtkLiverPlaneRingExtractor : public vtkPolyDataAlgorithm
{
public:
  static vtkLiverPlaneRingExtractor* New();
  vtkTypeMacro(vtkLiverPlaneRingExtractor, vtkPolyDataAlgorithm);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  vtkSetVector3Macro(Origin, double);
  vtkGetVector3Macro(Origin, double);

  vtkSetVector3Macro(Normal, double);
  vtkGetVector3Macro(Normal, double);

protected:
  vtkLiverPlaneRingExtractor();
  ~vtkLiverPlaneRingExtractor() override;

  int FillInputPortInformation(int port, vtkInformation* info) override;
  int RequestData(vtkInformation*, vtkInformationVector**, vtkInformationVector*) override;

private:
  vtkLiverPlaneRingExtractor(const vtkLiverPlaneRingExtractor&) = delete;
  void operator=(const vtkLiverPlaneRingExtractor&) = delete;

  double Origin[3];
  double Normal[3];
};

#endif // __vtkLiverPlaneRingExtractor_h_

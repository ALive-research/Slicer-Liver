/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) Oslo University Hospital. All rights reserved.

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

/*=========================================================================

  Program: NorMIT-Plan
  Module: vtkBezierSurfaceSource.h

  Copyright (c) 2017, The Intervention Centre, Oslo University Hospital

  All rights reserved.

  Redistribution and use in source and binary forms, with or without
  modification, are permitted provided that the following conditions are met:

  1. Redistributions of source code must retain the above copyright notice,
  this list of conditions and the following disclaimer.

  2. Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

  3. Neither the name of the copyright holder nor the names of its contributors
  may be used to endorse or promote products derived from this software
  without specific prior written permission.

  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
  FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
  DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
  SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
  OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
  =========================================================================*/
#ifndef __vtkBezierSurfaceSource_h
#define __vtkBezierSurfaceSource_h

#include "vtkSlicerLiverMarkupsModuleVTKWidgetsExport.h"

// VTK includes
#include <vtkFloatArray.h>
#include <vtkPolyDataAlgorithm.h>
#include <vtkSmartPointer.h>

//-------------------------------------------------------------------------------
class vtkPoints;
class vtkPolyData;
class vtkFloatArray;

//------------------------------------------------------------------------------
/**
 * \ingroup ResectionPlanning
 *
 * \brief This class generates the geometry of a Bézier surface
 * of degree \f$m+1\times n+1\f$ where \f$m\f$ and \f$n\f$ are number of control
 * points in the respective parametric directions $u$ and \f$v\f$.
 */
class VTK_SLICER_LIVERMARKUPS_MODULE_VTKWIDGETS_EXPORT vtkBezierSurfaceSource : public vtkPolyDataAlgorithm
{
 public:

  /**
   * Instantiation of object.
   *
   *
   * @return pointer to vtkBezierSurfaceSource newly created.
   */
  static vtkBezierSurfaceSource *New();

  vtkTypeMacro(vtkBezierSurfaceSource, vtkPolyDataAlgorithm);

  /**
   * Print the properties of the object.
   *
   * @param os ouptut stream to print the properties to.
   * @param indent indentation value.
   */
  void PrintSelf(ostream &os, vtkIndent indent) override;

  /**
   * Set the control points.
   *
   * @param points pointer to vtkPoints object containing the
   * coordinates of the control points.
   */
  void SetControlPoints(vtkPoints *points);

  /**
   * Get the control points.
   *
   * @return pointer to vtkPoints object containing the coordinates of
   * the control points.
   */
  vtkSmartPointer<vtkPoints> GetControlPoints() const;

  /**
   * Set the number of control points.
   *
   * @param m number of control points in the parametric u direction.
   * @param n number of control points in the parametric v direction.
   */
  void SetNumberOfControlPoints(unsigned int m, unsigned int n);

  /**
   * Set the resolution of the Bézier surface (number of quads).
   *
   * @param x resolution of the surface in the parametric u direction.
   * @param y resolution of the surface in the parametric v direction.
   */
  void SetResolution(unsigned int x, unsigned int y);

  /**
   * Get the resolution of the Bézier surface (number of quads).
   *
   * @param resolution pointer to int array containing u and v resolution.
   */
  void GetResolution(unsigned int *resolution) const;

  /**
   * Get thre resolution in the parametric direction u (number of quads).
   *
   * @return resolution in parametric direction u.
   */
  unsigned int GetResolutionX() const
  {return this->Resolution[0];}

  /**
   * Get the resolution in the parametric direction v (number of quads).
   *
   * @return resolution in the parametric direction v.
   */
  unsigned int GetResolutionY() const
  {return this->Resolution[1];}

  /**
   * Set the control points to the default values (e.g., lying in a
   * plane of size 1).
   */
  void ResetControlPoints();

  /**
   * Get the number of control poits in the parametric direction u.
   *
   * @return number of control points in the parametric direction u.
   */
  unsigned int GetNumberOfControlPointsX() const
  {return this->NumberOfControlPoints[0];}

  /**
   * Get the number of control poits in the parametric direction v.
   *
   * @return number of control points in the parametric direction v.
   */
  unsigned int GetNumberOfControlPointsY() const
  {return this->NumberOfControlPoints[1];}

 protected:
  vtkBezierSurfaceSource();
  ~vtkBezierSurfaceSource();

  /**
   * Function computing the Bézier surface according to the pipeline
   * architecture of VTK.
   *
   * @return return code.
   */
  int RequestData(vtkInformation *, vtkInformationVector **, vtkInformationVector *) override;

 private:
  vtkBezierSurfaceSource(const vtkBezierSurfaceSource&);  // Not implemented.
  void operator=(const vtkBezierSurfaceSource&);  // Not implemented.

  /**
   * Updates the topology of the mesh representing the Bézier
   * surface. An effective update will happen whenever the resolution
   * of the surface is changed.
   */
  void UpdateTopology();

  /**
   * Computation of the binomial coefficients required for the
   * computation of the Bézier surface. This function is used internally.
   */
  void ComputeBinomialCoefficients();

  /**
   * Computation of the tensor product surface of Bernstein basis (Bézier).
   *
   * @param polyData pointer to vtkPolyData which will hold the Bézier surface.
   */
  void UpdateBezierSurfacePolyData(vtkPolyData *polyData);

  /**
   * Evaluation of Bézier surface.
   *
   * @param points coordinates of control points.
   */
  void EvaluateBezierSurface(vtkPoints *points);

  unsigned int NumberOfControlPoints[2];
  unsigned int Resolution[2];
  double **ControlPoints;
  double *BinomialCoefficientsX;
  double *BinomialCoefficientsY;
  vtkSmartPointer<vtkDoubleArray> DataArray;
  vtkSmartPointer<vtkCellArray> Topology;
  vtkSmartPointer<vtkFloatArray> TCoords;

};

#endif

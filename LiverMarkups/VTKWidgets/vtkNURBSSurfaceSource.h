/*==============================================================================

  Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) Children's Hospital of Philadelphia. All rights reserved.

  Redistribution and use in source and binary forms, with or without
  modification, are permitted provided that the following conditions
  are met:

  * Redistributions of source code must retain the above copyright
    notice, this list of conditions and the following disclaimer.

  * Redistributions in binary form must reproduce the above copyright
    notice, this list of conditions and the following disclaimer in the
    documentation and/or other materials provided with the distribution.

  * Neither the name of Kitware, Inc. nor the names of Contributors
    may be used to endorse or promote products derived from this
    software without specific prior written permission.

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

  This file was originally developed by Csaba Pinter (Pixel Medical /
  Ebatinca).

==============================================================================*/

#ifndef __vtkNURBSSurfaceSource_h
#define __vtkNURBSSurfaceSource_h

#include "vtkSlicerLiverMarkupsModuleVTKWidgetsExport.h"

// GridSurface includes
//#include "vtkMRMLMarkupsGridSurfaceNode.h"  // For the WrapAround enum

// VTK includes
#include <vtkPolyDataAlgorithm.h>

class vtkDoubleArray;
class vtkIdList;

//------------------------------------------------------------------------------
/**
 * \ingroup GridSurfaceMarkups
 *
 * \brief Generate the geometry of a NURBS surface
 */
class VTK_SLICER_LIVERMARKUPS_MODULE_VTKWIDGETS_EXPORT vtkNURBSSurfaceSource : public vtkPolyDataAlgorithm
{
public:
  // Wrap around enum defines if the surface is wrapped around and if yes along which axis
  enum
    {
    NoWrap,
    AlongU,
    AlongV,
    WrapAround_Last
    };

  static const char* GetWrapAroundAsString(int wrapAround);

 public:
  static vtkNURBSSurfaceSource *New();
  vtkTypeMacro(vtkNURBSSurfaceSource, vtkPolyDataAlgorithm);
  void PrintSelf(ostream &os, vtkIndent indent);

  /// Set resolution of the input control point grid (u x v)
  vtkSetVector2Macro(InputResolution, int);
  /// Get resolution of the input control point grid (u x v)
  vtkGetVector2Macro(InputResolution, int);

  
  ///@{
  /// Set/get interpolation degrees
  vtkSetVector2Macro(InterpolationDegrees, unsigned int);
  vtkGetVector2Macro(InterpolationDegrees, unsigned int);
  ///@}

  ///@{
  /// Set/get evaluation delta, which controls the number of surface points. The smaller the delta value, smoother the surface.
  /// The number of interpolated points will be /sa InputResolution / Delta.
  vtkSetMacro(Delta, double);
  vtkGetMacro(Delta, double);
  ///@}

  ///@{
  /// Set/get flag determining whether centripetal parametrization method is used. False by default.
  vtkSetMacro(UseCentripetal, bool);
  vtkBooleanMacro(UseCentripetal, bool);
  vtkGetMacro(UseCentripetal, bool);
  ///@}

  ///@{
  /// Set/get expansion factor. The surface will overreach the edge control points by this fraction of its size. 0 by default.
  vtkSetMacro(ExpansionFactor, double);
  vtkGetMacro(ExpansionFactor, double);
  ///@}

  /// Set/get variable determining whether to connect two opposing edges of the grid
  /// thus creating a cylinder-like surface. Disabled (NoWrap=0) by default.
  /// \sa vtkMRMLMarkupsGridSurfaceNode::WrapAround
  ///@{
  vtkSetMacro(WrapAround, int);
  vtkGetMacro(WrapAround, int);
  ///@}

  /// Set/get variable determining whether to use iterative method for finding the evaluated
  /// parameter space when \sa WrapAround is enabled. Enabled by default.
  ///@{
  vtkSetMacro(IterativeParameterSpaceCalculation, bool);
  vtkBooleanMacro(IterativeParameterSpaceCalculation, bool);
  vtkGetMacro(IterativeParameterSpaceCalculation, bool);
  ///@}

  /// Set/get flag specifying whether a quad mesh is generated instead of a triangle mesh.
  /// Disabled by default.
  ///@{
  vtkSetMacro(GenerateQuadMesh, bool);
  vtkBooleanMacro(GenerateQuadMesh, bool);
  vtkGetMacro(GenerateQuadMesh, bool);
  ///@}
  
protected:
  /// Compute NURBS surface poly data from the input points according to input resolution and degrees
  void ComputeNurbsPolyData(vtkPoints* inputPoints, vtkPolyData* outputPolyData);

  /// Evaluate surface: compute interpolated surface points from control points and knot vectors
  void EvaluateSurface(std::array<double, 4>& linSpace, vtkDoubleArray* uKnots, vtkDoubleArray* vKnots, vtkPoints* controlPoints, vtkPoints* outEvalPoints);
  /// Triangulate evaluated surface points to complete the output surface
  void TriangulateSurface(std::array<double, 4>& linSpace, vtkPolyData* outputPolyData);
  /// Generate quad mesh from the evaluated surface points to produce a surface
  void GenerateQuadMeshSurface(std::array<double, 4>& linSpace, vtkPolyData* outputPolyData);

  /// \brief Compute uk and vl parameter vectors from input points
  /// The data points array has a row size of InputResolution[0] and column size of InputResolution[1] and it is 1-dimensional.
  /// Please refer to The NURBS Book (2nd Edition), pp.366-367 for details on how to compute uk and vl arrays for global surface
  /// interpolation.
  /// Please note that this function is not a direct implementation of Algorithm A9.3 which can be found on The NURBS Book
  /// (2nd Edition), pp.377-378. However, the output is the same.
  /// \param ukParams Output array for uk parameters
  /// \param vkParams Output array for vl parameters
  void ComputeParamsSurface(vtkPoints* inputPoints, vtkDoubleArray* ukParams, vtkDoubleArray* vlParams);
  /// Compute uk parameter array for curves.
  /// Please refer to the Equations 9.4 and 9.5 for chord length parametrization, and Equation 9.6 for centripetal method
  /// on The NURBS Book (2nd Edition), pp.364-365.
  /// \param inputPoints: Input points.
  /// \param pointIndexList: List of point IDs in \sa inputPoints defining the curve to parametrize.
  /// \param parametersArray: Output array for computed parameters.
  void ComputeParamsCurve(vtkPoints* inputPoints, vtkIdList* pointIndexList, vtkDoubleArray* parametersArray);
  /// Compute a knot vector from the parameter list using averaging method.
  /// Please refer to the Equation 9.8 on The NURBS Book (2nd Edition), pp.365 for details.
  void ComputeKnotVector(int degree, int numOfPoints, vtkDoubleArray* params, vtkDoubleArray* outKnotVector);
  /// Build the coefficient matrix for global interpolation.
  /// This function only uses data points to build the coefficient matrix. Please refer to The NURBS Book (2nd Edition),
  /// pp364-370 for details.
  void BuildCoeffMatrix(int degree, vtkDoubleArray* knotVector, vtkDoubleArray* params, vtkPoints* points, double** outCoeffMatrix);

  /// Computes the non-vanishing basis functions for a single parameter.
  /// Implementation of Algorithm A2.2 from The NURBS Book by Piegl & Tiller. Uses recurrence to compute the basis functions,
  /// also known as Cox - de Boor recursion formula.
  void BasisFunction(int degree, vtkDoubleArray* knotVector, int span, double knot, vtkDoubleArray* outBasisFunctions);
  /// Compute the non-vanishing basis functions for a list of parameters.
  /// Wrapper for \sa BasisFunction to process multiple span and knot values. Uses recurrence to compute the basis functions,
  /// also known as Cox - de Boor recursion formula.
  void BasisFunctions(int degree, vtkDoubleArray* knotVector, vtkIntArray* spans, vtkDoubleArray* knots, vtkDoubleArray* outBasisFunctions);
  /// Find the span of a single knot over the knot vector using linear search.
  /// Alternative implementation for the Algorithm A2.1 from The NURBS Book by Piegl & Tiller.
  int FindSpanLinear(int degree, vtkDoubleArray* knotVector, int numControlPoints, double knot);
  /// Find spans of a list of knots over the knot vector.
  /// Wrapper for \sa FindSpanLinear to process multiple knot values.
  void FindSpans(int degree, vtkDoubleArray* knotVector, int numControlPoints, vtkDoubleArray* knots, vtkIntArray* outSpans);

  /// \brief Compute the solution to a system of linear equations.
  /// This function solves Ax = b using LU decomposition. A is a NxN matrix, b is NxM matrix of M column vectors.
  /// Each column of x is a solution for corresponding column of b.
  void LuSolve(double** coeffMatrix, int matrixSize, vtkPoints* points, vtkPoints* outControlPointsR);
  /// LU-Factorization method for solution of linear systems. Decomposes the matrix A such that A = LU.
  void LuDecomposition(double** matrixA, double** matrixL, double** matrixU, int size);
  /// \brief Forward substitution method for the solution of linear systems.
  /// Solves the equation Ly = b using forward substitution method where L is a lower triangular matrix and b is a column matrix.
  void ForwardSubstitution(double** matrixL, double* b, int size, double* outY);
  /// \brief Backward substitution method for the solution of linear systems.
  /// Solves the equation Ux = y using backward substitution method where U is a upper triangular matrix and y is a column matrix.
  void BackwardSubstitution(double** matrixU, double* y, int size, double* outX);
  /// Return a list of evenly spaced numbers over a specified interval.
  void LinSpace(double start, double stop, int numOfSamples, vtkDoubleArray* outSpace);

  /// Convenience function to get point index from input point list with the two (u,v) indices
  unsigned int GetPointIndexUV(int u, int v);
  /// Get effective interpolating grid resolution, which is different than the specified if \sa WrapAround is enabled.
  void GetInterpolatingGridResolution(int (&resolutionUV)[2]);
  /// Get interpolating overlap by which the input points are wrapped around if \sa WrapAround is enabled.
  void GetInterpolatingOverlap(int (&overlapUV)[2]);
  /// Convenience function to allocate NxN matrix
  /// \param m Number of rows
  /// \param n Number of columns. If omitted it is considered a square MxM matrix
  double** AllocateMatrix(int m, int n=0);
  /// Convenience function to delete NxN matrix
  /// \param m Number of rows
  /// \param n Number of columns. If omitted it is considered a square MxM matrix
  void DestructMatrix(double** matrix, int m, int n=0);

  /// Calculate parameter space to evaluate considering \sa ExpansionFactor and \sa WrapAround parameters
  /// \param outLinSpace Linear space array [minU, maxU, minV, maxV]
  void CalculateEvaluatedParameterSpace(std::array<double, 4>& outLinSpace);
  /// Iteratively calculate parameter space to evaluate for \sa WrapAround cases so that meeting triangles do not overlap
  ///TODO: Use knots to be able to do iterative determination due to the instability of the parameter space caused by uneven point spacing
  ///      The knots are used to evauate a series of points in the hypothetical parameter space to find the place where the two ends meet when wrapping around is enabled
  /// \param outLinSpace Linear space array [minU, maxU, minV, maxV]
  void CalculateWrappedAroundParameterSpaceIterative(vtkDoubleArray* uKnots, vtkDoubleArray* vKnots, vtkPoints* controlPoints, std::array<double, 4>& outLinSpace);
  /// Calculate sample size as a function of \sa Delta
  /// \param linSpace The parametric bounds of the evaluated linear space for which we want to calculate the sample size
  /// \param outSampleSize Calculated sample size [sampleSizeU, sampleSizeV]
  void CalculateSampleSize(std::array<double, 4>& linSpace, std::array<unsigned int, 2>& outSampleSize);
  /// Calculate number of samples per grid cell
  int GetNumberOfSamplesPerGridCell();

protected:
  int FillInputPortInformation(int port, vtkInformation* info) override;
  int RequestData(vtkInformation*, vtkInformationVector**, vtkInformationVector*);

protected:
  /// Number of input control points along the u and v directions, respectively
  /// Note: Signed int so that there is no unsigned casting when negative values appear when wrap around is enabled.
  int InputResolution[2] = {4,4};
  /// Degree of the output surface for the u and v directions, respectively
  unsigned int InterpolationDegrees[2] = {3,3};

  /// Evaluation delta.
  /// Controls the number of surface points. The smaller the delta value, smoother the surface.
  /// The number of interpolated points will be /sa InputResolution / Delta.
  double Delta = 0.1;

  /// Activate centripetal parametrization method. Default: false
  bool UseCentripetal = false;

  /// Expansion factor. The surface will overreach the edge control points by this fraction of its size.
  /// Valid values are [0.0, 0.5]. 0 by default.
  double ExpansionFactor = 0.0;

  /// Determine whether to connect two opposing edges of the grid thus creating a cylinder-like surface.
  /// NoWrap: Wrap around is disabled (this is the default)
  /// AlongU: The edge that will be wrapped around is the 'u' edge (for which grid size is determined in the first element \sa InputResolution)
  /// AlongV: The edge that will be wrapped around is the 'v' edge (for which grid size is determined in the second element \sa InputResolution)
  /// \sa vtkMRMLMarkupsGridSurfaceNode::WrapAround
  int WrapAround = vtkNURBSSurfaceSource::NoWrap;

  /// Determine whether use iterative method for finding the evaluated
  /// parameter space when \sa WrapAround is enabled. Enabled by default.
  bool IterativeParameterSpaceCalculation = true;

  /// Flag specifying whether quad mesh will be generated instead of a triangle mesh.
  bool GenerateQuadMesh = false;

 protected:
  vtkNURBSSurfaceSource();
  ~vtkNURBSSurfaceSource();

 private:
  vtkNURBSSurfaceSource(const vtkNURBSSurfaceSource&);  // Not implemented.
  void operator=(const vtkNURBSSurfaceSource&);  // Not implemented.
};

#endif // __vtkNURBSSurfaceSource_h

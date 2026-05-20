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

  This file was originally developed for the Slicer-Liver extension
  as part of the T2 LiverResections all-in migration (Stack 1 of the
  v2.0.0 release tracker — see ADR-0015).

==============================================================================*/

#ifndef __vtkLiverBezierFitter_h_
#define __vtkLiverBezierFitter_h_

#include "vtkSlicerLiverResectionsModuleAlgorithmExport.h"

// VTK includes
#include <vtkPolyDataAlgorithm.h>
#include <vtkSmartPointer.h>

// STD
#include <vector>

class vtkPoints;
class vtkDoubleArray;

/**
 * \class vtkLiverBezierFitter
 *
 * \brief Compute a 4x4 (degree-3) Bezier control-point grid from a
 * gridded sample of surface points and matching Bernstein-basis
 * matrices, using the normal-equation pseudo-inverse formulation.
 *
 * This class is a C++ lift of ``LiverLogic.fit_bezier_surface`` in
 * ``Liver/Liver.py`` (line ~1914).  It is *intentionally bit-equivalent*
 * to the Python implementation: same matmul / inverse algebra in the
 * same order so that the characterisation tests in
 * ``Testing/Python/unit/test_bezier_characterization.py`` continue to
 * hold against the C++ output at ``rtol=1e-12, atol=1e-12``.
 *
 * \par Inputs (real VTK input ports per ADR-0015 §1)
 *  Three explicit input ports — option A from issue #339.  The
 *  alternative (1 port + 2 parameter arrays) was rejected because the
 *  Bernstein-basis matrices are *data* — they're a function of the
 *  sample positions (an input), not a function of the algorithm's
 *  fixed parameters.  Treating them as data on ports lets T2 Stack 4
 *  Representations compose this fitter via ``SetInputConnection`` from
 *  a basis-builder upstream (or supply a static
 *  ``BuildBernsteinBasis``-produced table directly).
 *
 *  - **Port 0 — Points** as ``vtkPolyData``.  ``GetPoints()`` carries
 *    Nu * Nv samples of a surface in 3-D, ordered row-major in u then v
 *    (i.e. point index ``i * Nv + j`` holds sample ``(u_i, v_j)``).
 *    Sized via ``SetNumberOfSamples(Nu, Nv)``.
 *  - **Port 1 — BasisU** as ``vtkTable``.  Nu rows, M columns; row i is
 *    the Bernstein basis evaluated at u-sample i.  M (= Bernstein order
 *    + 1) determines the control-grid side length.  For the canonical
 *    4x4 lift used by the production callers
 *    ``LiverLogic.runSurfacefromCurve`` / ``runSurfacefromEFD`` in
 *    ``Liver/Liver.py``, M = 4 (Bernstein degree 3).
 *  - **Port 2 — BasisV** as ``vtkTable``.  Nv rows, M columns; row i is
 *    the Bernstein basis evaluated at v-sample i.  Must have the same
 *    column count M as BasisU.
 *
 * \par Output
 *  - On port 0, a ``vtkPolyData`` whose ``GetPoints()`` array holds the
 *    M*M control points in row-major (u,v) order.  No cells are
 *    generated; the polydata is a pure point container.  In addition,
 *    the M*M control points are accessible directly as a flat std::vector
 *    via ``GetControlPoints()`` after ``Update()`` for callers that need
 *    the raw grid without going through ``vtk::util::numpy_support``.
 *
 * \par Algebra
 *  Per the Python reference:
 *  \code
 *    ut_u_inv_u = inv(Bu^T Bu) Bu^T
 *    vt_v_inv_v = Bv inv(Bv^T Bv)
 *    cp[i] = ut_u_inv_u * points[:,:,i] * vt_v_inv_v  (per-axis i in {0,1,2})
 *    return transpose(cp, (1, 2, 0))
 *  \endcode
 *  This is the normal-equation form of the pseudo-inverse; for square
 *  non-singular basis matrices it collapses to an exact inverse
 *  (which is why the characterisation EXPECTED values reproduce the
 *  input lattice to ~1e-15 relative error).
 *
 * \par Implementation choice
 *  Uses Eigen's ``Eigen::PartialPivLU::inverse()`` on the small (M x M)
 *  symmetric-positive-definite Gram matrices ``Bu^T Bu`` and ``Bv^T Bv``,
 *  which matches NumPy's ``np.linalg.inv`` semantics on the same
 *  matrices to within floating-point dust (last-bit-of-double, well
 *  under the ``rtol=1e-12`` tolerance the characterisation test
 *  asserts).
 *
 * \par MRML invariant
 *  This class does **not** reference any ``vtkMRMLNode``.  Per ADR-0015
 *  the algorithm library is pure VTK; MRML lives in the Python
 *  orchestration layer that consumes the output.
 */
class VTK_SLICER_LIVERRESECTIONS_MODULE_ALGORITHM_EXPORT vtkLiverBezierFitter : public vtkPolyDataAlgorithm
{
public:
  static vtkLiverBezierFitter* New();
  vtkTypeMacro(vtkLiverBezierFitter, vtkPolyDataAlgorithm);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  /// Set the dimensions of the gridded sample (Nu rows, Nv columns).
  /// The points input must contain Nu*Nv points; BasisU (table on port 1)
  /// must have Nu rows and BasisV (table on port 2) must have Nv rows.
  /// Setter only — gridded sample shape is a parameter per ADR-0015 §1
  /// (an explicit declaration of what shape the input data carries).
  void SetNumberOfSamples(int nu, int nv);
  vtkGetVector2Macro(NumberOfSamples, int);

  /// Fetch the fitted M*M*3 control points as a flat std::vector.
  /// Valid after ``Update()``.  Layout matches the polydata output:
  /// row-major (i, j) order with 3 floats per control point.
  const std::vector<double>& GetControlPoints() const { return this->ControlPoints; }

  /// Convenience: control-grid side length M (= BasisU/BasisV column count).
  /// Zero until ``Update()`` has been called.
  int GetGridSize() const { return this->GridSize; }

  /// Build an (nSamples x (degree+1)) Bernstein-basis matrix evaluated
  /// at the given sample parameters in [0, 1].  Equivalent to the
  /// per-row call sequence
  ///   ``bezier_list_u.append(self.evaluate_basis_bezier(u[i], degree))``
  /// in ``LiverLogic.runSurfacefromCurve``.  The matrix is laid out
  /// row-major: row i is the Bernstein-degree basis evaluated at
  /// ``samples[i]``.  Returned as a vtkDoubleArray of length
  /// ``nSamples * (degree + 1)`` (1 component per value).
  ///
  /// Wrappable from Python via the VTK array surface.
  static vtkSmartPointer<vtkDoubleArray> BuildBernsteinBasis(vtkDoubleArray* samples, int degree);

  /// C++-friendly overload — fill ``out`` (resized to nSamples *
  /// (degree+1)) with the same row-major Bernstein basis.
  static void BuildBernsteinBasisRaw(const double* samples, int nSamples, int degree, std::vector<double>& out);

protected:
  vtkLiverBezierFitter();
  ~vtkLiverBezierFitter() override;

  int FillInputPortInformation(int port, vtkInformation* info) override;
  int RequestData(vtkInformation*, vtkInformationVector**, vtkInformationVector*) override;

private:
  vtkLiverBezierFitter(const vtkLiverBezierFitter&) = delete;
  void operator=(const vtkLiverBezierFitter&) = delete;

  int NumberOfSamples[2];
  int GridSize;
  std::vector<double> ControlPoints;
};

#endif // __vtkLiverBezierFitter_h_

/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) Oslo University Hospital. All rights reserved.

==============================================================================*/

#include "vtkLiverBezierFitter.h"

// VTK includes
#include <vtkDoubleArray.h>
#include <vtkInformation.h>
#include <vtkInformationVector.h>
#include <vtkNew.h>
#include <vtkObjectFactory.h>
#include <vtkPoints.h>
#include <vtkPolyData.h>

// Eigen
#include <Eigen/Core>
#include <Eigen/LU>

// STD
#include <array>
#include <cassert>
#include <vector>

vtkStandardNewMacro(vtkLiverBezierFitter);

//------------------------------------------------------------------------------
vtkLiverBezierFitter::vtkLiverBezierFitter()
  : GridSize(0)
{
  this->NumberOfSamples[0] = 0;
  this->NumberOfSamples[1] = 0;
  this->SetNumberOfInputPorts(0);
  this->SetNumberOfOutputPorts(1);
}

//------------------------------------------------------------------------------
vtkLiverBezierFitter::~vtkLiverBezierFitter() = default;

//------------------------------------------------------------------------------
void vtkLiverBezierFitter::PrintSelf(ostream &os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);
  os << indent << "NumberOfSamples: (" << this->NumberOfSamples[0] << ", "
     << this->NumberOfSamples[1] << ")\n";
  os << indent << "GridSize: " << this->GridSize << "\n";
}

//------------------------------------------------------------------------------
void vtkLiverBezierFitter::SetNumberOfSamples(int nu, int nv)
{
  if (this->NumberOfSamples[0] == nu && this->NumberOfSamples[1] == nv)
    {
    return;
    }
  this->NumberOfSamples[0] = nu;
  this->NumberOfSamples[1] = nv;
  this->Modified();
}

//------------------------------------------------------------------------------
void vtkLiverBezierFitter::SetInputPoints(vtkDoubleArray *points)
{
  if (this->Points.GetPointer() == points)
    {
    return;
    }
  this->Points = points;
  this->Modified();
}

//------------------------------------------------------------------------------
vtkDoubleArray *vtkLiverBezierFitter::GetInputPoints() const
{
  return this->Points;
}

//------------------------------------------------------------------------------
void vtkLiverBezierFitter::SetBasisU(vtkDoubleArray *basisU)
{
  if (this->BasisU.GetPointer() == basisU)
    {
    return;
    }
  this->BasisU = basisU;
  this->Modified();
}

//------------------------------------------------------------------------------
vtkDoubleArray *vtkLiverBezierFitter::GetBasisU() const
{
  return this->BasisU;
}

//------------------------------------------------------------------------------
void vtkLiverBezierFitter::SetBasisV(vtkDoubleArray *basisV)
{
  if (this->BasisV.GetPointer() == basisV)
    {
    return;
    }
  this->BasisV = basisV;
  this->Modified();
}

//------------------------------------------------------------------------------
vtkDoubleArray *vtkLiverBezierFitter::GetBasisV() const
{
  return this->BasisV;
}

//------------------------------------------------------------------------------
// Bernstein basis of given degree at a single parameter t in [0, 1].
// Equivalent to LiverLogic.evaluate_basis_bezier (a deBoor-style
// recurrence; for Bezier curves the deBoor recurrence collapses to the
// Bernstein evaluation).
//------------------------------------------------------------------------------
namespace
{
void evaluateBernstein(double t, int degree, double *out)
{
  // Initialise to (1, 0, ..., 0); deBoor up-sweep.
  for (int k = 0; k <= degree; ++k)
    {
    out[k] = 0.0;
    }
  out[0] = 1.0;
  const double t1 = 1.0 - t;
  for (int j = 1; j <= degree; ++j)
    {
    double saved = 0.0;
    for (int k = 0; k < j; ++k)
      {
      const double tmp = out[k];
      out[k] = saved + t1 * tmp;
      saved = t * tmp;
      }
    out[j] = saved;
    }
}
}  // namespace

//------------------------------------------------------------------------------
void vtkLiverBezierFitter::BuildBernsteinBasisRaw(const double *samples,
                                                    int nSamples,
                                                    int degree,
                                                    std::vector<double> &out)
{
  const int cols = degree + 1;
  out.assign(static_cast<size_t>(nSamples) * cols, 0.0);
  std::vector<double> row(cols);
  for (int i = 0; i < nSamples; ++i)
    {
    evaluateBernstein(samples[i], degree, row.data());
    for (int k = 0; k < cols; ++k)
      {
      out[static_cast<size_t>(i) * cols + k] = row[k];
      }
    }
}

//------------------------------------------------------------------------------
vtkSmartPointer<vtkDoubleArray>
vtkLiverBezierFitter::BuildBernsteinBasis(vtkDoubleArray *samples, int degree)
{
  vtkSmartPointer<vtkDoubleArray> result = vtkSmartPointer<vtkDoubleArray>::New();
  if (!samples)
    {
    return result;
    }
  const int n = static_cast<int>(samples->GetNumberOfTuples()
                                 * samples->GetNumberOfComponents());
  std::vector<double> flat(n);
  for (int i = 0; i < n; ++i)
    {
    flat[i] = samples->GetValue(i);
    }
  std::vector<double> out;
  BuildBernsteinBasisRaw(flat.data(), n, degree, out);
  result->SetNumberOfComponents(1);
  result->SetNumberOfTuples(static_cast<vtkIdType>(out.size()));
  for (size_t i = 0; i < out.size(); ++i)
    {
    result->SetValue(static_cast<vtkIdType>(i), out[i]);
    }
  return result;
}

//------------------------------------------------------------------------------
int vtkLiverBezierFitter::RequestData(vtkInformation *,
                                       vtkInformationVector **,
                                       vtkInformationVector *outputVector)
{
  using Matrix = Eigen::MatrixXd;

  const int nu = this->NumberOfSamples[0];
  const int nv = this->NumberOfSamples[1];

  if (nu <= 0 || nv <= 0)
    {
    vtkErrorMacro(<< "NumberOfSamples must be positive; got ("
                  << nu << ", " << nv << ").");
    return 0;
    }
  if (!this->Points || this->Points->GetNumberOfTuples() * this->Points->GetNumberOfComponents()
      < static_cast<vtkIdType>(nu) * nv * 3)
    {
    vtkErrorMacro(<< "InputPoints array too small for "
                  << nu << "x" << nv << " grid.");
    return 0;
    }
  if (!this->BasisU || !this->BasisV)
    {
    vtkErrorMacro(<< "BasisU and BasisV must be set before Update().");
    return 0;
    }

  // Decode BasisU / BasisV row counts from NumberOfSamples; derive the
  // column count M from the array length.  This matches the Python
  // contract where basis_u has shape (Nu, M) and basis_v has shape (Nv, M).
  const vtkIdType totalU = this->BasisU->GetNumberOfTuples()
                           * this->BasisU->GetNumberOfComponents();
  const vtkIdType totalV = this->BasisV->GetNumberOfTuples()
                           * this->BasisV->GetNumberOfComponents();
  if (totalU % nu != 0 || totalV % nv != 0)
    {
    vtkErrorMacro(<< "BasisU/BasisV size not divisible by Nu/Nv.");
    return 0;
    }
  const int mU = static_cast<int>(totalU / nu);
  const int mV = static_cast<int>(totalV / nv);
  if (mU != mV)
    {
    vtkErrorMacro(<< "BasisU and BasisV must have the same number of columns "
                  << "(got " << mU << " vs " << mV << ").");
    return 0;
    }
  const int M = mU;
  this->GridSize = M;

  // Build Eigen matrices from the flat VTK arrays (row-major decode).
  Matrix Bu(nu, M);
  for (int i = 0; i < nu; ++i)
    {
    for (int j = 0; j < M; ++j)
      {
      Bu(i, j) = this->BasisU->GetValue(i * M + j);
      }
    }
  Matrix Bv(nv, M);
  for (int i = 0; i < nv; ++i)
    {
    for (int j = 0; j < M; ++j)
      {
      Bv(i, j) = this->BasisV->GetValue(i * M + j);
      }
    }

  // Per-axis points matrix (Nu x Nv).
  std::array<Matrix, 3> P;
  for (int axis = 0; axis < 3; ++axis)
    {
    P[axis].resize(nu, nv);
    }
  for (int i = 0; i < nu; ++i)
    {
    for (int j = 0; j < nv; ++j)
      {
      const vtkIdType base = (static_cast<vtkIdType>(i) * nv + j) * 3;
      P[0](i, j) = this->Points->GetValue(base + 0);
      P[1](i, j) = this->Points->GetValue(base + 1);
      P[2](i, j) = this->Points->GetValue(base + 2);
      }
    }

  // Compute the pseudo-inverse normal-equation matrices, in the same
  // order as the Python reference (LiverLogic.fit_bezier_surface):
  //   u_basis_product = Bu^T Bu
  //   u_basis_inverse = inv(u_basis_product)
  //   ut_u_inv_u      = u_basis_inverse * Bu^T
  //   v_basis_product = Bv^T Bv
  //   v_basis_inverse = inv(v_basis_product)
  //   vt_v_inv_v      = Bv * v_basis_inverse
  //   cp[axis]        = ut_u_inv_u * P[axis] * vt_v_inv_v
  //   cp              = transpose(stack(cp), (1, 2, 0))
  const Matrix uBasisProduct = Bu.transpose() * Bu;
  const Matrix uBasisInverse = uBasisProduct.inverse();
  const Matrix utUInvU = uBasisInverse * Bu.transpose();

  const Matrix vBasisProduct = Bv.transpose() * Bv;
  const Matrix vBasisInverse = vBasisProduct.inverse();
  const Matrix vtVInvV = Bv * vBasisInverse;

  // Allocate the flat control-points buffer (M*M*3, row-major (i,j) x axis).
  this->ControlPoints.assign(static_cast<size_t>(M) * M * 3, 0.0);
  for (int axis = 0; axis < 3; ++axis)
    {
    const Matrix cp = utUInvU * P[axis] * vtVInvV;
    assert(cp.rows() == M && cp.cols() == M);
    for (int i = 0; i < M; ++i)
      {
      for (int j = 0; j < M; ++j)
        {
        this->ControlPoints[(static_cast<size_t>(i) * M + j) * 3 + axis] = cp(i, j);
        }
      }
    }

  // Pack into vtkPolyData output.
  vtkInformation *outInfo = outputVector->GetInformationObject(0);
  vtkPolyData *out = vtkPolyData::SafeDownCast(
    outInfo->Get(vtkDataObject::DATA_OBJECT()));
  vtkNew<vtkPoints> outPoints;
  outPoints->SetDataTypeToDouble();
  outPoints->SetNumberOfPoints(static_cast<vtkIdType>(M) * M);
  for (int i = 0; i < M; ++i)
    {
    for (int j = 0; j < M; ++j)
      {
      const size_t base = (static_cast<size_t>(i) * M + j) * 3;
      outPoints->SetPoint(static_cast<vtkIdType>(i) * M + j,
                          this->ControlPoints[base + 0],
                          this->ControlPoints[base + 1],
                          this->ControlPoints[base + 2]);
      }
    }
  out->SetPoints(outPoints);
  return 1;
}

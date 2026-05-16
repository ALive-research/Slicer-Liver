/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) Oslo University Hospital. All rights reserved.

==============================================================================*/

#include "vtkLiverBezierFitter.h"

// VTK includes
#include <vtkAbstractArray.h>
#include <vtkDoubleArray.h>
#include <vtkInformation.h>
#include <vtkInformationVector.h>
#include <vtkNew.h>
#include <vtkObjectFactory.h>
#include <vtkPoints.h>
#include <vtkPolyData.h>
#include <vtkStreamingDemandDrivenPipeline.h>
#include <vtkTable.h>

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
  // Three real input ports per ADR-0015 §1: points (port 0), basisU
  // (port 1), basisV (port 2).  See header for the data-type contract.
  this->SetNumberOfInputPorts(3);
  this->SetNumberOfOutputPorts(1);
}

//------------------------------------------------------------------------------
int vtkLiverBezierFitter::FillInputPortInformation(int port,
                                                    vtkInformation *info)
{
  if (port == 0)
    {
    info->Set(vtkAlgorithm::INPUT_REQUIRED_DATA_TYPE(), "vtkPolyData");
    return 1;
    }
  if (port == 1 || port == 2)
    {
    info->Set(vtkAlgorithm::INPUT_REQUIRED_DATA_TYPE(), "vtkTable");
    return 1;
    }
  return 0;
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
namespace
{
// Decode an Nrows x M vtkTable into an Eigen matrix in the same row /
// column order.  Returns false (and emits an error via vtkErrorMacro on
// the caller) if the row count does not match the configured Nrows or
// if columns are non-numeric.
bool decodeBasisTable(vtkTable *table, int nRows, Eigen::MatrixXd &out,
                      int &outCols, std::string &err)
{
  if (!table)
    {
    err = "basis table is null";
    return false;
    }
  const vtkIdType actualRows = table->GetNumberOfRows();
  const vtkIdType nCols = table->GetNumberOfColumns();
  if (actualRows != nRows)
    {
    err = "basis table row count mismatch";
    return false;
    }
  if (nCols < 1)
    {
    err = "basis table has no columns";
    return false;
    }
  outCols = static_cast<int>(nCols);
  out.resize(nRows, outCols);
  for (vtkIdType j = 0; j < nCols; ++j)
    {
    vtkAbstractArray *col = table->GetColumn(j);
    if (!col || col->GetNumberOfTuples() != actualRows)
      {
      err = "basis table column has wrong tuple count";
      return false;
      }
    for (vtkIdType i = 0; i < actualRows; ++i)
      {
      out(static_cast<int>(i), static_cast<int>(j)) =
        col->GetVariantValue(i).ToDouble();
      }
    }
  return true;
}
}  // namespace

//------------------------------------------------------------------------------
int vtkLiverBezierFitter::RequestData(vtkInformation *,
                                       vtkInformationVector **inputVector,
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

  // Port 0 — Points: vtkPolyData carrying Nu*Nv samples (row-major u, v).
  vtkInformation *pointsInfo = inputVector[0]->GetInformationObject(0);
  vtkPolyData *pointsInput = pointsInfo
    ? vtkPolyData::SafeDownCast(pointsInfo->Get(vtkDataObject::DATA_OBJECT()))
    : nullptr;
  if (!pointsInput || !pointsInput->GetPoints())
    {
    vtkErrorMacro(<< "Input points polydata (port 0) is required.");
    return 0;
    }
  vtkPoints *samplePoints = pointsInput->GetPoints();
  if (samplePoints->GetNumberOfPoints() < static_cast<vtkIdType>(nu) * nv)
    {
    vtkErrorMacro(<< "Input points has "
                  << samplePoints->GetNumberOfPoints()
                  << " entries, expected at least " << (nu * nv)
                  << " for a " << nu << "x" << nv << " grid.");
    return 0;
    }

  // Port 1 — BasisU as vtkTable (Nu rows, M columns).
  vtkInformation *buInfo = inputVector[1]->GetInformationObject(0);
  vtkTable *basisUInput = buInfo
    ? vtkTable::SafeDownCast(buInfo->Get(vtkDataObject::DATA_OBJECT()))
    : nullptr;
  // Port 2 — BasisV as vtkTable (Nv rows, M columns).
  vtkInformation *bvInfo = inputVector[2]->GetInformationObject(0);
  vtkTable *basisVInput = bvInfo
    ? vtkTable::SafeDownCast(bvInfo->Get(vtkDataObject::DATA_OBJECT()))
    : nullptr;
  if (!basisUInput || !basisVInput)
    {
    vtkErrorMacro(<< "BasisU (port 1) and BasisV (port 2) must be set "
                  << "before Update().");
    return 0;
    }

  Matrix Bu;
  Matrix Bv;
  int mU = 0;
  int mV = 0;
  std::string err;
  if (!decodeBasisTable(basisUInput, nu, Bu, mU, err))
    {
    vtkErrorMacro(<< "BasisU (port 1): " << err << " (expected "
                  << nu << " rows).");
    return 0;
    }
  if (!decodeBasisTable(basisVInput, nv, Bv, mV, err))
    {
    vtkErrorMacro(<< "BasisV (port 2): " << err << " (expected "
                  << nv << " rows).");
    return 0;
    }
  if (mU != mV)
    {
    vtkErrorMacro(<< "BasisU and BasisV must have the same number of columns "
                  << "(got " << mU << " vs " << mV << ").");
    return 0;
    }
  const int M = mU;
  this->GridSize = M;

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
      double p[3];
      samplePoints->GetPoint(static_cast<vtkIdType>(i) * nv + j, p);
      P[0](i, j) = p[0];
      P[1](i, j) = p[1];
      P[2](i, j) = p[2];
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

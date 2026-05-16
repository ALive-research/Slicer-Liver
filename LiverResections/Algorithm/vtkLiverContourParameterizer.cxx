/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) Oslo University Hospital. All rights reserved.

==============================================================================*/

#include "vtkLiverContourParameterizer.h"

// VTK includes
#include <vtkDoubleArray.h>
#include <vtkInformation.h>
#include <vtkInformationVector.h>
#include <vtkIntArray.h>
#include <vtkNew.h>
#include <vtkObjectFactory.h>
#include <vtkPointData.h>
#include <vtkPoints.h>
#include <vtkPolyData.h>
#include <vtkSmartPointer.h>

// STD
#include <cmath>
#include <vector>

vtkStandardNewMacro(vtkLiverContourParameterizer);

namespace
{
constexpr double TWO_PI = 6.283185307179586476925286766559005768394;
constexpr double PI = 3.141592653589793238462643383279502884197;
} // namespace

//------------------------------------------------------------------------------
vtkLiverContourParameterizer::vtkLiverContourParameterizer()
  : Mode(MODE_EFD)
  , Order(8)
  , NumberOfReconstructionPoints(12)
  , UseComputedLocus(true)
{
  this->Locus[0] = 0.0;
  this->Locus[1] = 0.0;
  this->Locus[2] = 0.0;
  this->SetNumberOfInputPorts(1);
  this->SetNumberOfOutputPorts(1);
}

//------------------------------------------------------------------------------
vtkLiverContourParameterizer::~vtkLiverContourParameterizer() = default;

//------------------------------------------------------------------------------
void vtkLiverContourParameterizer::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);
  os << indent << "Mode: " << this->Mode << "\n";
  os << indent << "Order: " << this->Order << "\n";
  os << indent << "NumberOfReconstructionPoints: " << this->NumberOfReconstructionPoints << "\n";
  os << indent << "UseComputedLocus: " << this->UseComputedLocus << "\n";
}

//------------------------------------------------------------------------------
int vtkLiverContourParameterizer::FillInputPortInformation(int /*port*/, vtkInformation* info)
{
  info->Set(vtkAlgorithm::INPUT_REQUIRED_DATA_TYPE(), "vtkPolyData");
  return 1;
}

//------------------------------------------------------------------------------
void vtkLiverContourParameterizer::SetLocus(double x, double y, double z)
{
  if (this->Locus[0] == x && this->Locus[1] == y && this->Locus[2] == z)
  {
    return;
  }
  this->Locus[0] = x;
  this->Locus[1] = y;
  this->Locus[2] = z;
  this->Modified();
}

//------------------------------------------------------------------------------
// EFD coefficients via direct closed-form harmonic integration.
// Bit-equivalent to LiverLogic.elliptic_fourier_descriptors (normalize=False).
//
// Python reference:
//   dxyz = np.diff(contour, axis=0)
//   dt = np.sqrt((dxyz**2).sum(axis=1))
//   t = np.concatenate([[0.0], np.cumsum(dt)])
//   T = t[-1]
//   phi = (2 * np.pi * t) / T
//   orders = np.arange(1, order+1)
//   consts = T / (2 * orders^2 * np.pi^2)
//   phi *= orders.reshape(order, -1)
//   d_cos_phi = cos(phi[:, 1:]) - cos(phi[:, :-1])
//   d_sin_phi = sin(phi[:, 1:]) - sin(phi[:, :-1])
//   a = consts * sum((dxyz[:,0]/dt) * d_cos_phi, axis=1)
//   ...
//   coeffs[:, j] = a, b, c, d, e, f
//
// We compute (dx/dt, dy/dt, dz/dt) once per segment and accumulate the
// six sums in a single pass per harmonic, preserving the (over-segments)
// reduction order so the floating-point reduction matches NumPy's.
//------------------------------------------------------------------------------
std::vector<double> vtkLiverContourParameterizer::ComputeEFDCoefficientsRaw(const double* contour, int nPoints, int order)
{
  std::vector<double> result(static_cast<size_t>(order) * 6, 0.0);
  if (nPoints < 2 || order < 1)
  {
    return result;
  }

  // Segment-wise differentials and parameter t.
  const int nSeg = nPoints - 1;
  std::vector<double> dx(nSeg), dy(nSeg), dz(nSeg), dt(nSeg);
  std::vector<double> t(nPoints, 0.0);
  for (int i = 0; i < nSeg; ++i)
  {
    dx[i] = contour[(i + 1) * 3 + 0] - contour[i * 3 + 0];
    dy[i] = contour[(i + 1) * 3 + 1] - contour[i * 3 + 1];
    dz[i] = contour[(i + 1) * 3 + 2] - contour[i * 3 + 2];
    dt[i] = std::sqrt(dx[i] * dx[i] + dy[i] * dy[i] + dz[i] * dz[i]);
    t[i + 1] = t[i] + dt[i];
  }
  const double T = t[nSeg];
  if (T == 0.0)
  {
    return result;
  }

  // phi[k] = 2 * pi * t[k] / T, evaluated per-segment endpoint.
  std::vector<double> phiBase(nPoints);
  for (int k = 0; k < nPoints; ++k)
  {
    phiBase[k] = TWO_PI * t[k] / T;
  }

  // Per-harmonic accumulation.  Per-harmonic constant matches Python:
  //   const_n = T / (2 * n^2 * pi^2)
  for (int n = 1; n <= order; ++n)
  {
    const double cn = T / (2.0 * static_cast<double>(n) * n * PI * PI);
    double a = 0.0, b = 0.0, c = 0.0, d = 0.0, e = 0.0, f = 0.0;
    for (int i = 0; i < nSeg; ++i)
    {
      const double phi0 = n * phiBase[i];
      const double phi1 = n * phiBase[i + 1];
      const double dCos = std::cos(phi1) - std::cos(phi0);
      const double dSin = std::sin(phi1) - std::sin(phi0);
      // Match NumPy element-wise (dxyz[:, k] / dt) precisely: do the
      // division first, then multiply by d_cos/d_sin.  Using a
      // pre-computed 1/dt would introduce a single ulp deviation per
      // segment that compounds across the harmonic sum and could push
      // the tighter rtol=1e-12 characterisation pin off.
      a += (dx[i] / dt[i]) * dCos;
      b += (dx[i] / dt[i]) * dSin;
      c += (dy[i] / dt[i]) * dCos;
      d += (dy[i] / dt[i]) * dSin;
      e += (dz[i] / dt[i]) * dCos;
      f += (dz[i] / dt[i]) * dSin;
    }
    const int row = n - 1;
    result[row * 6 + 0] = cn * a;
    result[row * 6 + 1] = cn * b;
    result[row * 6 + 2] = cn * c;
    result[row * 6 + 3] = cn * d;
    result[row * 6 + 4] = cn * e;
    result[row * 6 + 5] = cn * f;
  }
  return result;
}

//------------------------------------------------------------------------------
// (A_0, C_0, E_0) DC triple.  Python reference (per axis):
//
//   xi    = cumsum(dx) - (dx/dt) * t[1:]
//   A0    = (1/T) * sum( (dx/(2*dt)) * diff(t**2) + xi * dt )
//   ... same for y, z ...
//   return (contour[0,0] + A0, contour[0,1] + C0, contour[0,2] + E0)
//
// We pre-compute the segment quantities once and re-use across axes,
// preserving the same per-segment reduction order so the result matches
// NumPy's sum reduction to within last-bit-of-double.
//------------------------------------------------------------------------------
std::vector<double> vtkLiverContourParameterizer::ComputeDCCoefficientsRaw(const double* contour, int nPoints)
{
  std::vector<double> result(3, 0.0);
  if (nPoints < 2)
  {
    return result;
  }
  const int nSeg = nPoints - 1;
  std::vector<double> dx(nSeg), dy(nSeg), dz(nSeg), dt(nSeg);
  std::vector<double> t(nPoints, 0.0);
  for (int i = 0; i < nSeg; ++i)
  {
    dx[i] = contour[(i + 1) * 3 + 0] - contour[i * 3 + 0];
    dy[i] = contour[(i + 1) * 3 + 1] - contour[i * 3 + 1];
    dz[i] = contour[(i + 1) * 3 + 2] - contour[i * 3 + 2];
    dt[i] = std::sqrt(dx[i] * dx[i] + dy[i] * dy[i] + dz[i] * dz[i]);
    t[i + 1] = t[i] + dt[i];
  }
  const double T = t[nSeg];
  if (T == 0.0)
  {
    result[0] = contour[0];
    result[1] = contour[1];
    result[2] = contour[2];
    return result;
  }
  // diff(t**2): segment i contributes t[i+1]^2 - t[i]^2.
  // cumsum of dx/dy/dz: prefix sum along segments.
  double cumDx = 0.0, cumDy = 0.0, cumDz = 0.0;
  double sumX = 0.0, sumY = 0.0, sumZ = 0.0;
  for (int i = 0; i < nSeg; ++i)
  {
    cumDx += dx[i];
    cumDy += dy[i];
    cumDz += dz[i];
    const double tNext = t[i + 1];
    const double diffT2 = tNext * tNext - t[i] * t[i];
    const double xi = cumDx - (dx[i] / dt[i]) * tNext;
    const double delta = cumDy - (dy[i] / dt[i]) * tNext;
    const double zi = cumDz - (dz[i] / dt[i]) * tNext;
    sumX += (dx[i] / (2.0 * dt[i])) * diffT2 + xi * dt[i];
    sumY += (dy[i] / (2.0 * dt[i])) * diffT2 + delta * dt[i];
    sumZ += (dz[i] / (2.0 * dt[i])) * diffT2 + zi * dt[i];
  }
  const double invT = 1.0 / T;
  result[0] = contour[0] + sumX * invT;
  result[1] = contour[1] + sumY * invT;
  result[2] = contour[2] + sumZ * invT;
  return result;
}

//------------------------------------------------------------------------------
// Inverse EFD transform.  Python reference:
//
//   t = np.linspace(0, 1, n_coords).reshape(1, -1)
//   n = np.arange(harmonic).reshape(-1, 1)
//   xt = matmul(coeffs[:harmonic, 0].reshape(1,-1),
//               cos(2 * (n+1) * pi * t)) +
//        matmul(coeffs[:harmonic, 1].reshape(1,-1),
//               sin(2 * (n+1) * pi * t)) +
//        locus[0]
//   ... same for y (cols 2,3) and z (cols 4,5) ...
//   return np.stack([xt, yt, zt], axis=1)  # shape (1, 3, n_coords)
//
// Output layout matches the Python (1, 3, n_coords) shape: x values
// first (n_coords doubles), then y, then z.  Reduction order: for each
// t_k, sum over harmonics n.  This matches NumPy's matmul-of-row-vector
// reduction direction.
//------------------------------------------------------------------------------
std::vector<double> vtkLiverContourParameterizer::InverseTransformRaw(const double* coeffs, int harmonic, const double locus[3], int nCoords)
{
  std::vector<double> result(static_cast<size_t>(3) * nCoords, 0.0);
  if (harmonic < 1 || nCoords < 1)
  {
    return result;
  }
  // t = linspace(0, 1, nCoords) — NumPy default endpoint=True.
  std::vector<double> ts(nCoords);
  if (nCoords == 1)
  {
    ts[0] = 0.0;
  }
  else
  {
    const double step = 1.0 / static_cast<double>(nCoords - 1);
    for (int k = 0; k < nCoords; ++k)
    {
      ts[k] = step * k;
    }
  }
  for (int k = 0; k < nCoords; ++k)
  {
    double xt = 0.0, yt = 0.0, zt = 0.0;
    const double t = ts[k];
    for (int n = 0; n < harmonic; ++n)
    {
      const double phase = TWO_PI * static_cast<double>(n + 1) * t;
      const double cp = std::cos(phase);
      const double sp = std::sin(phase);
      xt += coeffs[n * 6 + 0] * cp + coeffs[n * 6 + 1] * sp;
      yt += coeffs[n * 6 + 2] * cp + coeffs[n * 6 + 3] * sp;
      zt += coeffs[n * 6 + 4] * cp + coeffs[n * 6 + 5] * sp;
    }
    result[0 * nCoords + k] = xt + locus[0];
    result[1 * nCoords + k] = yt + locus[1];
    result[2 * nCoords + k] = zt + locus[2];
  }
  return result;
}

//------------------------------------------------------------------------------
// Wrappable static overloads — vtkDoubleArray in / vtkDoubleArray out so
// Python callers (and Slicer's VTK Python bindings) can drive the math
// without raw pointer arithmetic.
//------------------------------------------------------------------------------
namespace
{
vtkSmartPointer<vtkDoubleArray> wrap(const std::vector<double>& values)
{
  vtkSmartPointer<vtkDoubleArray> arr = vtkSmartPointer<vtkDoubleArray>::New();
  arr->SetNumberOfComponents(1);
  arr->SetNumberOfTuples(static_cast<vtkIdType>(values.size()));
  for (size_t i = 0; i < values.size(); ++i)
  {
    arr->SetValue(static_cast<vtkIdType>(i), values[i]);
  }
  return arr;
}
std::vector<double> unwrap(vtkDoubleArray* arr)
{
  std::vector<double> out;
  if (!arr)
  {
    return out;
  }
  const vtkIdType n = arr->GetNumberOfTuples() * arr->GetNumberOfComponents();
  out.reserve(static_cast<size_t>(n));
  for (vtkIdType i = 0; i < n; ++i)
  {
    out.push_back(arr->GetValue(i));
  }
  return out;
}
} // namespace

//------------------------------------------------------------------------------
vtkSmartPointer<vtkDoubleArray> vtkLiverContourParameterizer::ComputeEFDCoefficients(vtkDoubleArray* contour, int order)
{
  auto flat = unwrap(contour);
  const int n = static_cast<int>(flat.size() / 3);
  return wrap(ComputeEFDCoefficientsRaw(flat.data(), n, order));
}

//------------------------------------------------------------------------------
vtkSmartPointer<vtkDoubleArray> vtkLiverContourParameterizer::ComputeDCCoefficients(vtkDoubleArray* contour)
{
  auto flat = unwrap(contour);
  const int n = static_cast<int>(flat.size() / 3);
  return wrap(ComputeDCCoefficientsRaw(flat.data(), n));
}

//------------------------------------------------------------------------------
vtkSmartPointer<vtkDoubleArray> vtkLiverContourParameterizer::InverseTransform(vtkDoubleArray* coeffs, int harmonic, double locusX, double locusY, double locusZ, int nCoords)
{
  auto flat = unwrap(coeffs);
  const double locus[3] = { locusX, locusY, locusZ };
  return wrap(InverseTransformRaw(flat.data(), harmonic, locus, nCoords));
}

//------------------------------------------------------------------------------
int vtkLiverContourParameterizer::RequestData(vtkInformation*, vtkInformationVector** inputVector, vtkInformationVector* outputVector)
{
  vtkInformation* inInfo = inputVector[0]->GetInformationObject(0);
  vtkPolyData* inputContour = vtkPolyData::SafeDownCast(inInfo->Get(vtkDataObject::DATA_OBJECT()));
  if (!inputContour || !inputContour->GetPoints())
  {
    vtkErrorMacro(<< "Input contour polydata with points is required on port 0.");
    return 0;
  }
  vtkPoints* inputPoints = inputContour->GetPoints();
  const vtkIdType n64 = inputPoints->GetNumberOfPoints();
  if (n64 < 2)
  {
    vtkErrorMacro(<< "Input contour must contain at least two 3D points; got " << n64 << ".");
    return 0;
  }
  const int n = static_cast<int>(n64);
  const vtkIdType total = static_cast<vtkIdType>(n) * 3;

  // Decode the input ring point-by-point into the flat (x, y, z) buffer
  // the EFD / corner-mapping algorithms operate on.  Preserves traversal
  // order: row i = (x_i, y_i, z_i).
  std::vector<double> contour(static_cast<size_t>(total));
  for (int i = 0; i < n; ++i)
  {
    double p[3];
    inputPoints->GetPoint(i, p);
    contour[i * 3 + 0] = p[0];
    contour[i * 3 + 1] = p[1];
    contour[i * 3 + 2] = p[2];
  }

  vtkInformation* outInfo = outputVector->GetInformationObject(0);
  vtkPolyData* out = vtkPolyData::SafeDownCast(outInfo->Get(vtkDataObject::DATA_OBJECT()));

  this->Coefficients.clear();
  this->DC.clear();
  this->Reconstruction.clear();

  if (this->Mode == MODE_EFD)
  {
    if (this->Order < 1)
    {
      vtkErrorMacro(<< "Order must be >= 1 in EFD mode; got " << this->Order << ".");
      return 0;
    }
    this->Coefficients = ComputeEFDCoefficientsRaw(contour.data(), n, this->Order);
    if (this->UseComputedLocus)
    {
      this->DC = ComputeDCCoefficientsRaw(contour.data(), n);
    }
    else
    {
      this->DC = { this->Locus[0], this->Locus[1], this->Locus[2] };
    }
    const double locusArr[3] = { this->DC[0], this->DC[1], this->DC[2] };
    this->Reconstruction = InverseTransformRaw(this->Coefficients.data(), this->Order, locusArr, this->NumberOfReconstructionPoints);

    // Pack into output polydata: nCoords reconstructed points.
    vtkNew<vtkPoints> outPoints;
    outPoints->SetDataTypeToDouble();
    const int nc = this->NumberOfReconstructionPoints;
    outPoints->SetNumberOfPoints(nc);
    for (int k = 0; k < nc; ++k)
    {
      outPoints->SetPoint(k, this->Reconstruction[0 * nc + k], this->Reconstruction[1 * nc + k], this->Reconstruction[2 * nc + k]);
    }
    out->SetPoints(outPoints);
    return 1;
  }

  // CornerMapping mode: choose 4 equally spaced corner indices around
  // the ring and surface them via point-data scalars.
  vtkNew<vtkPoints> outPoints;
  outPoints->SetDataTypeToDouble();
  outPoints->SetNumberOfPoints(n);
  for (int i = 0; i < n; ++i)
  {
    outPoints->SetPoint(i, contour[i * 3 + 0], contour[i * 3 + 1], contour[i * 3 + 2]);
  }
  out->SetPoints(outPoints);

  vtkNew<vtkIntArray> cornerFlags;
  cornerFlags->SetName("CornerIndices");
  cornerFlags->SetNumberOfComponents(1);
  cornerFlags->SetNumberOfTuples(n);
  for (int i = 0; i < n; ++i)
  {
    cornerFlags->SetValue(i, 0);
  }
  // Four corners at indices 0, n/4, n/2, 3n/4 (mod n).  Same convention
  // used by the SlicingPlane init path's existing Python helper.
  for (int k = 0; k < 4; ++k)
  {
    const int idx = (k * n) / 4;
    cornerFlags->SetValue(idx, k + 1);
  }
  out->GetPointData()->AddArray(cornerFlags);
  return 1;
}

/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  This file was originally developed for the Slicer-Liver extension as
  the Algorithm-library adapter between VTK and the vendored PoissonRecon
  core (per ADR-0040).

==============================================================================*/

#include "vtkLiverPoissonSurfaceReconstruction.h"

// VTK includes -- FIRST, and that order is load-bearing.
//
// Upstream's Array.h defines a function-like macro named `Pointer`.
// VTK's vtkBuffer has a MEMBER named Pointer and initialises it as
// `Pointer(nullptr)`, which the preprocessor happily rewrites to
// `nullptr*`.  Including PoissonRecon first therefore breaks VTK
// headers with an error that names vtkBuffer.h and mentions neither
// PoissonRecon nor a macro.
//
// This is also why the class HEADER includes no PoissonRecon at all --
// only a forward declaration of vtkPolyData.  The macro stays inside
// this translation unit, so nothing that consumes this class can be
// poisoned by it, whatever order IT includes things in.  Keep it that
// way: the moment a PoissonRecon include appears in the header, every
// consumer inherits the trap.
#include <vtkCellArray.h>
#include <vtkDataArray.h>
#include <vtkFloatArray.h>
#include <vtkIdList.h>
#include <vtkNew.h>
#include <vtkObjectFactory.h>
#include <vtkPointData.h>
#include <vtkPoints.h>
#include <vtkPolyData.h>

// STD includes
#include <cmath>
#include <vector>

// Vendored PoissonRecon (see PoissonRecon/README.md), LAST for the
// reason above.  PreProcessor.h precedes the rest -- upstream expects
// it first.
#include "PreProcessor.h"

#include "MyMiscellany.h"
#include "Reconstructors.h"

namespace
{

using Real = float;
constexpr unsigned int Dim = 3;

/// Upstream's octree depth is exponential in memory and time.  1 is the
/// smallest meaningful tree; beyond about 14 a single reconstruction
/// exhausts memory on ordinary hardware.  Rejecting out-of-range values
/// turns a hang or a bad_alloc into a return code.
constexpr int MinDepth = 1;
constexpr int MaxDepth = 14;

/// Feeds vtkPolyData's points and normals to the solver.
///
/// Upstream pulls samples through a stream rather than taking an array,
/// which is what lets this adapter avoid copying the cloud: the solver
/// reads the caller's vtkPolyData in place.
class PolyDataSampleStream : public PoissonRecon::Reconstructor::InputOrientedSampleStream<Real, Dim>
{
public:
  PolyDataSampleStream(vtkPoints* points, vtkDataArray* normals)
    : Points(points)
    , Normals(normals)
  {
  }

  void reset(void) override { this->Index = 0; }

  bool read(PoissonRecon::Point<Real, Dim>& p, PoissonRecon::Point<Real, Dim>& n) override
  {
    if (this->Index >= this->Points->GetNumberOfPoints())
    {
      return false;
    }
    double point[3];
    this->Points->GetPoint(this->Index, point);
    double normal[3];
    this->Normals->GetTuple(this->Index, normal);
    for (unsigned int d = 0; d < Dim; d++)
    {
      p[d] = static_cast<Real>(point[d]);
      n[d] = static_cast<Real>(normal[d]);
    }
    this->Index++;
    return true;
  }

private:
  vtkPoints* Points;
  vtkDataArray* Normals;
  vtkIdType Index = 0;
};

/// Collects level-set vertices, and the gradient the solver reports at
/// each, straight into VTK arrays.
class PolyDataVertexStream : public PoissonRecon::Reconstructor::OutputLevelSetVertexStream<Real, Dim>
{
public:
  PolyDataVertexStream(vtkPoints* points, vtkFloatArray* normals)
    : Points(points)
    , Normals(normals)
  {
  }

  size_t size(void) const override { return static_cast<size_t>(this->Points->GetNumberOfPoints()); }

  size_t write(const PoissonRecon::Point<Real, Dim>& p, const PoissonRecon::Point<Real, Dim>& gradient, const Real&) override
  {
    this->Points->InsertNextPoint(p[0], p[1], p[2]);

    // The solver reports the GRADIENT of the fitted indicator function.
    // The indicator rises from outside to inside, so the gradient points
    // INWARD and the outward normal is its negation -- the same sign
    // convention vtkLiverOrientedPointCloudExtractor applies on the way
    // in, kept consistent so a reconstruction round-trips.
    double normal[3] = { -static_cast<double>(gradient[0]), -static_cast<double>(gradient[1]), -static_cast<double>(gradient[2]) };
    const double length = std::sqrt(normal[0] * normal[0] + normal[1] * normal[1] + normal[2] * normal[2]);
    if (length > 0.0)
    {
      normal[0] /= length;
      normal[1] /= length;
      normal[2] /= length;
    }
    this->Normals->InsertNextTuple3(normal[0], normal[1], normal[2]);

    return static_cast<size_t>(this->Points->GetNumberOfPoints() - 1);
  }

private:
  vtkPoints* Points;
  vtkFloatArray* Normals;
};

/// Collects reconstructed faces into a vtkCellArray.
class PolyDataFaceStream : public PoissonRecon::Reconstructor::OutputFaceStream<2>
{
public:
  PolyDataFaceStream(vtkCellArray* polys)
    : Polys(polys)
  {
  }

  size_t size(void) const override { return static_cast<size_t>(this->Polys->GetNumberOfCells()); }

  size_t write(const std::vector<PoissonRecon::node_index_type>& poly) override
  {
    vtkNew<vtkIdList> ids;
    ids->SetNumberOfIds(static_cast<vtkIdType>(poly.size()));
    for (size_t i = 0; i < poly.size(); i++)
    {
      ids->SetId(static_cast<vtkIdType>(i), static_cast<vtkIdType>(poly[i]));
    }
    this->Polys->InsertNextCell(ids);
    return static_cast<size_t>(this->Polys->GetNumberOfCells() - 1);
  }

private:
  vtkCellArray* Polys;
};

} // namespace

//------------------------------------------------------------------------------
vtkStandardNewMacro(vtkLiverPoissonSurfaceReconstruction);

//------------------------------------------------------------------------------
vtkLiverPoissonSurfaceReconstruction::vtkLiverPoissonSurfaceReconstruction() = default;

//------------------------------------------------------------------------------
vtkLiverPoissonSurfaceReconstruction::~vtkLiverPoissonSurfaceReconstruction() = default;

//------------------------------------------------------------------------------
void vtkLiverPoissonSurfaceReconstruction::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);
  os << indent << "DefaultDepth: " << vtkLiverPoissonSurfaceReconstruction::GetDefaultDepth() << "\n";
}

//------------------------------------------------------------------------------
int vtkLiverPoissonSurfaceReconstruction::GetDefaultDepth()
{
  return 7;
}

//------------------------------------------------------------------------------
bool vtkLiverPoissonSurfaceReconstruction::Reconstruct(vtkPolyData* orientedCloud, int depth, vtkPolyData* output)
{
  if (!output)
  {
    vtkGenericWarningMacro("Reconstruct: no output vtkPolyData given.");
    return false;
  }

  // Clear FIRST, so every failure path below leaves an empty result
  // rather than whatever the caller reconstructed last.
  output->Initialize();

  if (!orientedCloud)
  {
    vtkGenericWarningMacro("Reconstruct: no input point cloud given.");
    return false;
  }
  if (depth < MinDepth || depth > MaxDepth)
  {
    vtkGenericWarningMacro("Reconstruct: depth " << depth << " outside [" << MinDepth << ", " << MaxDepth << "].");
    return false;
  }

  vtkPoints* points = orientedCloud->GetPoints();
  if (!points || points->GetNumberOfPoints() == 0)
  {
    vtkGenericWarningMacro("Reconstruct: the input cloud has no points.");
    return false;
  }

  vtkDataArray* normals = orientedCloud->GetPointData() ? orientedCloud->GetPointData()->GetNormals() : nullptr;
  if (!normals)
  {
    // Not recoverable by estimating normals here: normals recovered from
    // an unstructured cloud have no reliable orientation, and a cloud
    // whose normals point inward reconstructs the COMPLEMENT of the
    // object.  Better to fail than to return a confident inversion.
    vtkGenericWarningMacro("Reconstruct: the input cloud carries no point normals.");
    return false;
  }
  if (normals->GetNumberOfTuples() != points->GetNumberOfPoints())
  {
    vtkGenericWarningMacro("Reconstruct: " << normals->GetNumberOfTuples() << " normals for " << points->GetNumberOfPoints() << " points.");
    return false;
  }

  static const unsigned int FEMSig =
    PoissonRecon::FEMDegreeAndBType<PoissonRecon::Reconstructor::Poisson::DefaultFEMDegree, PoissonRecon::Reconstructor::Poisson::DefaultFEMBoundary>::Signature;
  using FEMSigs = PoissonRecon::IsotropicUIntPack<Dim, FEMSig>;
  using Implicit = PoissonRecon::Reconstructor::Implicit<Real, Dim, FEMSigs>;
  using Solver = PoissonRecon::Reconstructor::Poisson::Solver<Real, Dim, FEMSigs>;

  PoissonRecon::Reconstructor::Poisson::SolutionParameters<Real> solverParams;
  solverParams.verbose = false;
  solverParams.depth = static_cast<unsigned int>(depth);

  PoissonRecon::Reconstructor::LevelSetExtractionParameters extractionParams;
  extractionParams.verbose = false;
  // Upstream defaults this OFF, and with it off the per-vertex gradient
  // handed to the vertex stream is all zeros -- silently, with no error.
  // The normals we hand back depend on it.
  extractionParams.outputGradients = true;

  vtkNew<vtkPoints> outPoints;
  vtkNew<vtkFloatArray> outNormals;
  outNormals->SetNumberOfComponents(3);
  outNormals->SetName("Normals");
  vtkNew<vtkCellArray> outPolys;

  PolyDataSampleStream sampleStream(points, normals);
  Implicit* implicit = Solver::Solve(sampleStream, solverParams);
  if (!implicit)
  {
    vtkGenericWarningMacro("Reconstruct: the solver produced no implicit function.");
    return false;
  }

  {
    PolyDataVertexStream vertexStream(outPoints, outNormals);
    PolyDataFaceStream faceStream(outPolys);
    implicit->extractLevelSet(vertexStream, faceStream, extractionParams);
  }
  delete implicit;

  if (outPoints->GetNumberOfPoints() == 0 || outPolys->GetNumberOfCells() == 0)
  {
    // A cloud can be well-formed and still carry no recoverable surface
    // -- too few points, or normals that cancel.  Report it rather than
    // handing back a valid-but-empty mesh as a success.
    vtkGenericWarningMacro("Reconstruct: the reconstruction is empty.");
    output->Initialize();
    return false;
  }

  output->SetPoints(outPoints);
  output->SetPolys(outPolys);
  output->GetPointData()->SetNormals(outNormals);
  return true;
}

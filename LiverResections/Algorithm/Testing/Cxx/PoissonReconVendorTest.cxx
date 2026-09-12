/*==============================================================================

  Copyright (c) 2026 The Intervention Centre, Oslo University Hospital

  Licensed under the Apache License, Version 2.0 (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.

==============================================================================*/

// Build-integration test for the VENDORED PoissonRecon drop
// (ADR-0040 phase 3).  This does not test any Slicer-Liver class -- there
// is none yet.  It answers the one question the vendor drop itself
// raises: do upstream's headers compile, instantiate and RUN inside
// Slicer's toolchain, as opposed to the standalone g++ invocation phase 1
// proved them under?
//
// The risk being covered is specific to header-only, heavily templated
// C++: the code that breaks is the code that gets instantiated, and
// nothing is instantiated until something asks for it.  A vendor drop can
// sit in the tree looking healthy while being unbuildable, so the drop
// and its first real instantiation belong in the same commit.
//
// Deliberately built against Reconstructors.h ALONE -- no Image.h, no
// PNG/JPEG/ZLIB, no Boost -- so a regression in the exclusion set
// (LiverResections/Algorithm/PoissonRecon/README.md) fails here rather
// than silently pulling a heavyweight dependency into the extension.

#include "PreProcessor.h"

#include "MyMiscellany.h"
#include "Reconstructors.h"

#include <array>
#include <cmath>
#include <cstdio>
#include <map>
#include <utility>
#include <vector>

using Real = float;
static const unsigned int Dim = 3;

namespace
{

// An oriented point cloud sampling a sphere, in upstream's stream form.
// The VTK adapter of phase 3b replaces this with a stream over
// vtkPolyData's points and normals -- same contract, different source.
struct SphereSampleStream : public PoissonRecon::Reconstructor::InputOrientedSampleStream<Real, Dim>
{
  SphereSampleStream(const std::vector<std::array<Real, 6>>& s)
    : Samples(s)
  {
  }
  void reset(void) override { this->Index = 0; }
  bool read(PoissonRecon::Point<Real, Dim>& p, PoissonRecon::Point<Real, Dim>& n) override
  {
    if (this->Index >= this->Samples.size())
    {
      return false;
    }
    for (unsigned int d = 0; d < Dim; d++)
    {
      p[d] = this->Samples[this->Index][d];
      n[d] = this->Samples[this->Index][3 + d];
    }
    this->Index++;
    return true;
  }

protected:
  const std::vector<std::array<Real, 6>>& Samples;
  size_t Index = 0;
};

struct VertexStream : public PoissonRecon::Reconstructor::OutputLevelSetVertexStream<Real, Dim>
{
  VertexStream(std::vector<Real>& v)
    : Vertices(v)
  {
  }
  size_t size(void) const override { return this->Vertices.size() / 3; }
  size_t write(const PoissonRecon::Point<Real, Dim>& p, const PoissonRecon::Point<Real, Dim>&, const Real&) override
  {
    for (unsigned int d = 0; d < Dim; d++)
    {
      this->Vertices.push_back(p[d]);
    }
    return this->Vertices.size() / 3 - 1;
  }

protected:
  std::vector<Real>& Vertices;
};

struct PolygonStream : public PoissonRecon::Reconstructor::OutputFaceStream<2>
{
  PolygonStream(std::vector<std::vector<int>>& f)
    : Faces(f)
  {
  }
  size_t size(void) const override { return this->Faces.size(); }
  size_t write(const std::vector<PoissonRecon::node_index_type>& poly) override
  {
    std::vector<int> face(poly.size());
    for (size_t i = 0; i < poly.size(); i++)
    {
      face[i] = static_cast<int>(poly[i]);
    }
    this->Faces.push_back(face);
    return this->Faces.size() - 1;
  }

protected:
  std::vector<std::vector<int>>& Faces;
};

} // namespace

int PoissonReconVendorTest(int, char*[])
{
  // ---------------------------------------------------------------------
  // An analytic sphere: positions on the surface, normals pointing out.
  // Analytic rather than sampled from a labelmap so the expected answer
  // is known in closed form and the assertions below can be tight.
  // ---------------------------------------------------------------------
  const Real radius = 1.0f;
  std::vector<std::array<Real, 6>> samples;
  const int nTheta = 60;
  const int nPhi = 120;
  for (int i = 1; i < nTheta; i++)
  {
    const double theta = M_PI * i / nTheta;
    for (int j = 0; j < nPhi; j++)
    {
      const double phi = 2.0 * M_PI * j / nPhi;
      const double nx = std::sin(theta) * std::cos(phi);
      const double ny = std::sin(theta) * std::sin(phi);
      const double nz = std::cos(theta);
      samples.push_back(
        { static_cast<Real>(radius * nx), static_cast<Real>(radius * ny), static_cast<Real>(radius * nz), static_cast<Real>(nx), static_cast<Real>(ny), static_cast<Real>(nz) });
    }
  }

  static const unsigned int FEMSig =
    PoissonRecon::FEMDegreeAndBType<PoissonRecon::Reconstructor::Poisson::DefaultFEMDegree, PoissonRecon::Reconstructor::Poisson::DefaultFEMBoundary>::Signature;
  using FEMSigs = PoissonRecon::IsotropicUIntPack<Dim, FEMSig>;
  using Implicit = PoissonRecon::Reconstructor::Implicit<Real, Dim, FEMSigs>;
  using Solver = PoissonRecon::Reconstructor::Poisson::Solver<Real, Dim, FEMSigs>;

  PoissonRecon::Reconstructor::Poisson::SolutionParameters<Real> solverParams;
  solverParams.verbose = false;
  // Depth 6 keeps the test near a second.  ADR-0040 fixes the PRODUCT
  // default at 7 on the phase-1 evidence; this number is a test-runtime
  // choice and carries no architectural weight.
  solverParams.depth = 6;

  PoissonRecon::Reconstructor::LevelSetExtractionParameters extractionParams;
  extractionParams.verbose = false;

  std::vector<Real> vertices;
  std::vector<std::vector<int>> faces;
  {
    SphereSampleStream sampleStream(samples);
    Implicit* implicit = Solver::Solve(sampleStream, solverParams);
    if (!implicit)
    {
      std::cerr << "FAIL: the solver returned no implicit function" << std::endl;
      return EXIT_FAILURE;
    }
    VertexStream vStream(vertices);
    PolygonStream pStream(faces);
    implicit->extractLevelSet(vStream, pStream, extractionParams);
    delete implicit;
  }

  if (vertices.empty() || faces.empty())
  {
    std::cerr << "FAIL: reconstruction produced an empty mesh" << std::endl;
    return EXIT_FAILURE;
  }

  // ---------------------------------------------------------------------
  // The mesh must be the SPHERE, not merely non-empty.  A build that
  // links but mis-instantiates can return a plausible-looking blob; only
  // checking against the analytic radius catches that.
  //
  // PSR reconstructs in a normalised cube and the level set is a smooth
  // approximation, so the radius is checked with a tolerance rather than
  // exactly -- but the SPREAD is what matters: a correct reconstruction
  // has every vertex at essentially the same radius.
  // ---------------------------------------------------------------------
  const size_t nVerts = vertices.size() / 3;
  double cx = 0.0, cy = 0.0, cz = 0.0;
  for (size_t i = 0; i < nVerts; i++)
  {
    cx += vertices[3 * i];
    cy += vertices[3 * i + 1];
    cz += vertices[3 * i + 2];
  }
  cx /= nVerts;
  cy /= nVerts;
  cz /= nVerts;

  double rMin = 1e30, rMax = -1e30, rMean = 0.0;
  for (size_t i = 0; i < nVerts; i++)
  {
    const double dx = vertices[3 * i] - cx;
    const double dy = vertices[3 * i + 1] - cy;
    const double dz = vertices[3 * i + 2] - cz;
    const double r = std::sqrt(dx * dx + dy * dy + dz * dz);
    rMin = std::min(rMin, r);
    rMax = std::max(rMax, r);
    rMean += r;
  }
  rMean /= nVerts;

  std::cout << "vendor smoke: " << nVerts << " vertices, " << faces.size() << " faces" << std::endl;
  std::cout << "  radius min/mean/max = " << rMin << " / " << rMean << " / " << rMax << std::endl;

  // Relative spread, so the assertion does not depend on PSR's internal
  // normalisation of the input cube.
  const double spread = (rMax - rMin) / rMean;
  if (spread > 0.05)
  {
    std::cerr << "FAIL: reconstructed radii spread " << spread << " -- not a sphere" << std::endl;
    return EXIT_FAILURE;
  }

  // ---------------------------------------------------------------------
  // Well-formedness: every face index must address a vertex that exists.
  // An out-of-range index is the classic symptom of an index-width
  // mismatch (node_index_type vs int) between upstream and our build --
  // exactly the kind of thing that differs between the standalone g++ of
  // phase 1 and Slicer's toolchain.
  // ---------------------------------------------------------------------
  for (const std::vector<int>& face : faces)
  {
    if (face.size() < 3)
    {
      std::cerr << "FAIL: degenerate face with " << face.size() << " vertices" << std::endl;
      return EXIT_FAILURE;
    }
    for (const int idx : face)
    {
      if (idx < 0 || static_cast<size_t>(idx) >= nVerts)
      {
        std::cerr << "FAIL: face index " << idx << " out of range (" << nVerts << " vertices)" << std::endl;
        return EXIT_FAILURE;
      }
    }
  }

  // ---------------------------------------------------------------------
  // Closed surface: a sphere sampled all the way round leaves PSR no
  // boundary to leave open, so every edge must be shared by exactly two
  // faces.  This is the assertion that would catch a reconstruction
  // silently truncated at the octree boundary.
  // ---------------------------------------------------------------------
  std::map<std::pair<int, int>, int> edgeUse;
  for (const std::vector<int>& face : faces)
  {
    for (size_t i = 0; i < face.size(); i++)
    {
      const int a = face[i];
      const int b = face[(i + 1) % face.size()];
      edgeUse[{ std::min(a, b), std::max(a, b) }]++;
    }
  }
  size_t nonManifold = 0;
  for (const auto& e : edgeUse)
  {
    if (e.second != 2)
    {
      nonManifold++;
    }
  }
  std::cout << "  edges " << edgeUse.size() << ", not shared by exactly 2 faces: " << nonManifold << std::endl;
  if (nonManifold != 0)
  {
    std::cerr << "FAIL: reconstruction is not a closed surface" << std::endl;
    return EXIT_FAILURE;
  }

  std::cout << "PoissonReconVendorTest passed" << std::endl;
  return EXIT_SUCCESS;
}

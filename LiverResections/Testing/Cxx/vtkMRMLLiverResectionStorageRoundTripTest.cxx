/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) Oslo University Hospital. All rights reserved.

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

==============================================================================*/

// Characterisation test for `vtkMRMLLiverResectionCSVStorageNode` —
// pins today's `.lrp.fcsv` round-trip behaviour so the LayerDM migration
// (ADR-0002) can refactor the storage path without silent regression.
// See ADR-0003 (testability invariant) for why this test exists in the
// state it does, and ADR-0001 Consequences for the reload-ordering
// requirement that motivates it.
//
// Scope (deliberately narrow):
//   The `.lrp.fcsv` format carries ONLY the Bezier surface's control
//   points; the storage node delegates Read/Write to the Markups
//   superclass on `resection->GetBezierSurfaceNode()`.  Resection
//   metadata (margins, colours, `InitializationControlPoints`, refs to
//   parent segmentation / target structures) is persisted through the
//   `.mrml` scene file via `WriteXMLAttributes`, not through
//   `.lrp.fcsv`.  This test therefore pins:
//     1. that the 16 Bezier control points survive `.lrp.fcsv` round-
//        trip with exact coordinate fidelity (within `kCoordinateTolerance`),
//     2. that today's failure modes of the storage class (missing
//        Bezier ref; wrong reference-node type) are preserved, and
//     3. that reading `.lrp.fcsv` does NOT clobber resection-node
//        metadata on the receiving node — a useful negative invariant
//        for the refactor, since the storage class is scoped to the
//        Bezier subnode and must stay that way.
//
//   The full ADR-0003 §6 deliverable — scene-level save/load asserting
//   the three-node assembly is intact, refs resolve, and resection
//   metadata round-trips through `.mrml` — is a separate follow-up
//   test, expected to be written in Python (per ADR-0004) and to use
//   `slicer.util.saveScene` / `loadScene` so it exercises the real
//   production load orchestration.

// MRML includes
#include "vtkMRMLCoreTestingMacros.h"
#include "vtkMRMLScene.h"

// VTKSlicer includes
#include <vtkMRMLLiverResectionNode.h>
#include <vtkMRMLLiverResectionCSVStorageNode.h>
#include <vtkMRMLMarkupsBezierSurfaceNode.h>

// VTK includes
#include <vtkNew.h>
#include <vtkPoints.h>
#include <vtkSmartPointer.h>

// STD includes
#include <cmath>
#include <cstdlib>
#include <sstream>
#include <string>

namespace
{

constexpr int kBezierControlPointCount = 16;
constexpr double kCoordinateTolerance  = 1e-6;

//------------------------------------------------------------------------------
// Build a deterministic 4x4 grid of distinct control points so we can assert
// exact survival across a write/read cycle.
vtkSmartPointer<vtkPoints> MakeDeterministicControlPoints()
{
  auto points = vtkSmartPointer<vtkPoints>::New();
  points->SetNumberOfPoints(kBezierControlPointCount);
  for (int row = 0; row < 4; ++row)
    {
    for (int col = 0; col < 4; ++col)
      {
      const vtkIdType idx = static_cast<vtkIdType>(row * 4 + col);
      // Use coordinates that cannot collide with a default-initialised point.
      const double x = 10.0 + col * 1.5;
      const double y = 20.0 + row * 1.5;
      const double z = 30.0 + (row + col) * 0.25;
      points->SetPoint(idx, x, y, z);
      }
    }
  return points;
}

//------------------------------------------------------------------------------
// Compare two MarkupsBezierSurface nodes by their control-point coordinates.
// Returns true if every control point matches within `kCoordinateTolerance`.
bool ControlPointsMatch(vtkMRMLMarkupsBezierSurfaceNode* a,
                        vtkMRMLMarkupsBezierSurfaceNode* b,
                        std::string& mismatchReason)
{
  if (a == nullptr || b == nullptr)
    {
    mismatchReason = "one or both Bezier nodes are null";
    return false;
    }
  const int countA = a->GetNumberOfControlPoints();
  const int countB = b->GetNumberOfControlPoints();
  if (countA != countB)
    {
    std::ostringstream oss;
    oss << "control point counts differ: a=" << countA << " b=" << countB;
    mismatchReason = oss.str();
    return false;
    }
  if (countA != kBezierControlPointCount)
    {
    std::ostringstream oss;
    oss << "expected " << kBezierControlPointCount
        << " control points, got " << countA;
    mismatchReason = oss.str();
    return false;
    }
  for (int i = 0; i < countA; ++i)
    {
    double pa[3] = { 0.0, 0.0, 0.0 };
    double pb[3] = { 0.0, 0.0, 0.0 };
    a->GetNthControlPointPosition(i, pa);
    b->GetNthControlPointPosition(i, pb);
    for (int d = 0; d < 3; ++d)
      {
      if (std::fabs(pa[d] - pb[d]) > kCoordinateTolerance)
        {
        std::ostringstream oss;
        oss << "control point " << i << " axis " << d
            << " differs: a=" << pa[d] << " b=" << pb[d];
        mismatchReason = oss.str();
        return false;
        }
      }
    }
  return true;
}

//------------------------------------------------------------------------------
// Populate a fresh Bezier node with the deterministic 16-point grid.
// `bezier` is expected to be a freshly-created MarkupsBezierSurface node
// already added to a scene.
void PopulateBezierControlPoints(vtkMRMLMarkupsBezierSurfaceNode* bezier,
                                 vtkPoints* sourcePoints)
{
  // RemoveAllControlPoints is conventional for resetting before population.
  bezier->RemoveAllControlPoints();
  for (vtkIdType i = 0; i < sourcePoints->GetNumberOfPoints(); ++i)
    {
    double p[3] = { 0.0, 0.0, 0.0 };
    sourcePoints->GetPoint(i, p);
    bezier->AddControlPoint(p[0], p[1], p[2]);
    }
}

//------------------------------------------------------------------------------
// Construct a resection + Bezier surface assembly in the given scene.
// Returns the resection node; the Bezier node is reachable via
// `resection->GetBezierSurfaceNode()`.
vtkMRMLLiverResectionNode*
BuildResectionAssembly(vtkMRMLScene* scene, const std::string& tag)
{
  auto resection = vtkMRMLLiverResectionNode::SafeDownCast(
    scene->AddNewNodeByClass("vtkMRMLLiverResectionNode",
                             std::string("Resection_") + tag));
  auto bezier = vtkMRMLMarkupsBezierSurfaceNode::SafeDownCast(
    scene->AddNewNodeByClass("vtkMRMLMarkupsBezierSurfaceNode",
                             std::string("Bezier_") + tag));
  resection->SetBezierSurfaceNode(bezier);
  return resection;
}

} // namespace

//------------------------------------------------------------------------------
int vtkMRMLLiverResectionStorageRoundTripTest(int argc, char* argv[])
{
  // argv[1] is conventionally a writable temp dir; the existing CMake
  // driver passes ${Slicer_BINARY_DIR}/Testing/Temporary via TEMP.  Fall
  // back to "." so the test is still runnable manually.
  const std::string tempDir =
    (argc > 1 && argv[1] != nullptr && argv[1][0] != '\0')
      ? std::string(argv[1])
      : std::string(".");
  const std::string filePath =
    tempDir + "/vtkMRMLLiverResectionStorageRoundTripTest.lrp.fcsv";

  // --------------------------------------------------------------------------
  // Phase 1 — populate, write
  // --------------------------------------------------------------------------
  auto scene = vtkSmartPointer<vtkMRMLScene>::New();
  vtkNew<vtkMRMLLiverResectionNode> resectionRegistrar;
  scene->RegisterNodeClass(resectionRegistrar);
  vtkNew<vtkMRMLLiverResectionCSVStorageNode> storageRegistrar;
  scene->RegisterNodeClass(storageRegistrar);
  vtkNew<vtkMRMLMarkupsBezierSurfaceNode> bezierRegistrar;
  scene->RegisterNodeClass(bezierRegistrar);

  auto resectionA = BuildResectionAssembly(scene, "A");
  CHECK_NOT_NULL(resectionA);
  auto bezierA = resectionA->GetBezierSurfaceNode();
  CHECK_NOT_NULL(bezierA);

  auto sourcePoints = MakeDeterministicControlPoints();
  PopulateBezierControlPoints(bezierA, sourcePoints);
  CHECK_INT(bezierA->GetNumberOfControlPoints(), kBezierControlPointCount);

  auto storage = vtkMRMLLiverResectionCSVStorageNode::SafeDownCast(
    scene->AddNewNodeByClass("vtkMRMLLiverResectionCSVStorageNode",
                             "Storage_A"));
  CHECK_NOT_NULL(storage);
  storage->SetFileName(filePath.c_str());

  const int writeStatus = storage->WriteData(resectionA);
  CHECK_INT(writeStatus, 1);

  // --------------------------------------------------------------------------
  // Phase 2 — clear scene, rebuild assembly, read
  // --------------------------------------------------------------------------
  scene->Clear(/*removeSingletons*/ 1);

  auto resectionB = BuildResectionAssembly(scene, "B");
  CHECK_NOT_NULL(resectionB);
  auto bezierB = resectionB->GetBezierSurfaceNode();
  CHECK_NOT_NULL(bezierB);
  // ADR-0001 Consequences: the Bezier node MUST be pre-constructed and
  // referenced from the resection before ReadDataInternal is called —
  // the storage class delegates I/O via `resection->GetBezierSurfaceNode()`
  // and errors out otherwise.  Pin that ordering with this assertion.
  //
  // NOTE (transitional characterisation, not a target invariant): the
  // LayerDM migration in ADR-0002 §Decision 2-3 explicitly dissolves
  // the requirement that callers pre-attach a Bezier subnode before
  // load — the migrated pipeline reads a plain Storable content node
  // and the storage class is rewritten accordingly.  When that
  // migration lands, this assertion (and the failure-mode probe in
  // Phase 4 that pins the "no Bezier => write fails" rule) is
  // expected to be removed or inverted.  Until then it pins today's
  // behaviour, which is what `/slicer-review` grades the storage-path
  // refactors against.
  CHECK_INT(bezierB->GetNumberOfControlPoints(), 0);

  // Sentinel metadata on resectionB BEFORE ReadData.  The `.lrp.fcsv`
  // format only carries Bezier control points; resection metadata must
  // not be clobbered by a Read.  See header scope comment §3.
  constexpr double kSentinelHepaticThickness = 2.5;
  constexpr double kSentinelPortalThickness  = 1.75;
  const float kSentinelHepaticColor[3] = { 0.10f, 0.20f, 0.30f };
  resectionB->SetHepaticContourThickness(kSentinelHepaticThickness);
  resectionB->SetPortalContourThickness(kSentinelPortalThickness);
  resectionB->SetHepaticContourColor(const_cast<float*>(kSentinelHepaticColor));

  auto storageB = vtkMRMLLiverResectionCSVStorageNode::SafeDownCast(
    scene->AddNewNodeByClass("vtkMRMLLiverResectionCSVStorageNode",
                             "Storage_B"));
  CHECK_NOT_NULL(storageB);
  storageB->SetFileName(filePath.c_str());

  const int readStatus = storageB->ReadData(resectionB);
  CHECK_INT(readStatus, 1);

  // --------------------------------------------------------------------------
  // Phase 3 — assert round-trip preserved the 16 control points and did
  // NOT clobber resection metadata that lives outside the `.lrp.fcsv` scope
  // --------------------------------------------------------------------------
  std::string mismatch;
  if (!ControlPointsMatch(bezierA, bezierB, mismatch))
    {
    std::cerr << "Round-trip mismatch: " << mismatch << std::endl;
    return EXIT_FAILURE;
    }

  // Metadata sentinels survived the Read — the storage class is and must
  // remain scoped to the Bezier subnode.
  CHECK_DOUBLE_TOLERANCE(resectionB->GetHepaticContourThickness(),
                         kSentinelHepaticThickness, kCoordinateTolerance);
  CHECK_DOUBLE_TOLERANCE(resectionB->GetPortalContourThickness(),
                         kSentinelPortalThickness, kCoordinateTolerance);
  {
    float readBack[3] = { 0.0f, 0.0f, 0.0f };
    resectionB->GetHepaticContourColor(readBack);
    for (int d = 0; d < 3; ++d)
      {
      if (std::fabs(readBack[d] - kSentinelHepaticColor[d])
          > kCoordinateTolerance)
        {
        std::cerr << "HepaticContourColor sentinel axis " << d
                  << " clobbered by ReadData: got " << readBack[d]
                  << " expected " << kSentinelHepaticColor[d] << std::endl;
        return EXIT_FAILURE;
        }
      }
  }

  // --------------------------------------------------------------------------
  // Phase 4 — pin the failure modes the storage class guards against
  // --------------------------------------------------------------------------
  // Write must fail when the resection has no Bezier reference.
  auto resectionC = vtkMRMLLiverResectionNode::SafeDownCast(
    scene->AddNewNodeByClass("vtkMRMLLiverResectionNode", "Resection_C"));
  CHECK_NOT_NULL(resectionC);
  // (intentionally do NOT set a Bezier surface node on resectionC)
  auto storageC = vtkMRMLLiverResectionCSVStorageNode::SafeDownCast(
    scene->AddNewNodeByClass("vtkMRMLLiverResectionCSVStorageNode",
                             "Storage_C"));
  storageC->SetFileName(filePath.c_str());
  // Suppress the expected error output during the failure-mode probe so
  // CTest's WITH_VTK_ERROR_OUTPUT_CHECK does not flag it as unexpected.
  TESTING_OUTPUT_IGNORE_WARNINGS_ERRORS_BEGIN();
  const int writeStatusNoBezier = storageC->WriteData(resectionC);
  TESTING_OUTPUT_IGNORE_WARNINGS_ERRORS_END();
  CHECK_INT(writeStatusNoBezier, 0);

  // CanReadInReferenceNode pin: a Bezier-only node should NOT be a valid
  // ReadData target — the storage class requires a Liver resection node.
  CHECK_BOOL(storage->CanReadInReferenceNode(bezierA), false);
  CHECK_BOOL(storage->CanReadInReferenceNode(resectionB), true);

  return EXIT_SUCCESS;
}

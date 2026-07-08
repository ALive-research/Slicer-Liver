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
  as part of the T2 LiverResections all-in migration (Stack 2 of the
  v2.0.0 release tracker — see ADR-0013 §8 and ADR-0014 §1).

==============================================================================*/

// This module MRML includes
#include "vtkMRMLBezierSurfaceNode.h"
#include "vtkMRMLControlPolygonDisplayNode.h"
#include "vtkMRMLParametricSurfaceDisplayNode.h"

// MRML includes
#include <vtkMRMLModelNode.h>
#include <vtkMRMLNodePropertyMacros.h>
#include <vtkMRMLScene.h>

// VTK includes
#include <vtkNew.h>
#include <vtkObjectFactory.h>
#include <vtkPoints.h>
#include <vtkPolyData.h>
#include <vtkSmartPointer.h>

// STD includes
#include <cstring>

//------------------------------------------------------------------------------
// Read-only-after-Init guard (ADR-0014 §4 + ADR-0019).
//
// Init-mode subordinate data (slicing-plane / distance-spheroid init
// points + derived plane / spheroid parameters) is mutable while
// ``State == Init`` and becomes read-only audit data the moment the
// node transitions to ``Planning``.  It stays read-only across the
// ``Planning <-> Confirmed`` round-trip introduced by ADR-0019 — the
// audit invariant is "init data is fixed once committed", regardless
// of which post-Init state the node currently sits in.
//
// File-local — ``#define``d here and ``#undef``ed at end-of-file.
#define LIVER_BEZIER_GUARD_INIT_ONLY(fieldName)                                        \
  do                                                                                   \
  {                                                                                    \
    if (this->State != Init && !this->LoadingFromXML)                                  \
    {                                                                                  \
      vtkWarningMacro("Cannot mutate " #fieldName " after Init->Planning transition"   \
                      " (ADR-0014 §4 / ADR-0019 read-only audit data; current state: " \
                      << GetStateAsString(this->State) << ")");                        \
      return;                                                                          \
    }                                                                                  \
  } while (0)

//------------------------------------------------------------------------------
vtkMRMLNodeNewMacro(vtkMRMLBezierSurfaceNode);

//------------------------------------------------------------------------------
vtkMRMLBezierSurfaceNode::vtkMRMLBezierSurfaceNode()
  : State(ResectionState::Init)
  , LoadingFromXML(false)
{
  // Weak reference to the target organ (liver) model node (ADR-0014
  // §1).  Registered with no events array and no content-modified
  // observation -- the same shape as the "geometry" role on
  // vtkMRMLResectionPlanNode -- so mutating the target does not
  // advance this node's MTime.  The downstream consumer is the T2
  // ring-extraction work (TODO(T2-target-mesh-weakref)).
  this->AddNodeReferenceRole(GetTargetReferenceRole(), GetTargetReferenceRole());
}

//------------------------------------------------------------------------------
vtkMRMLBezierSurfaceNode::~vtkMRMLBezierSurfaceNode() = default;

//------------------------------------------------------------------------------
vtkMRMLModelNode* vtkMRMLBezierSurfaceNode::GetTargetModelNode()
{
  return vtkMRMLModelNode::SafeDownCast(this->GetNodeReference(GetTargetReferenceRole()));
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::SetAndObserveTargetModelNode(vtkMRMLModelNode* target)
{
  this->SetAndObserveNodeReferenceID(GetTargetReferenceRole(), target ? target->GetID() : nullptr);
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::SetState(int state)
{
  // ADR-0019 transition matrix.
  if (state == this->State)
  {
    return;
  }
  if (!this->LoadingFromXML)
  {
    const bool forbidden =                            //
      (this->State == Planning && state == Init)      // ADR-0014 §4
      || (this->State == Confirmed && state == Init)  // ADR-0019
      || (this->State == Init && state == Confirmed); // ADR-0019
    if (forbidden)
    {
      vtkWarningMacro("Resection state transition " << GetStateAsString(this->State) << " -> " << GetStateAsString(state) << " is not permitted (ADR-0019); state left at "
                                                    << GetStateAsString(this->State));
      return;
    }
  }
  this->State = state;
  this->Modified();
}

//------------------------------------------------------------------------------
const char* vtkMRMLBezierSurfaceNode::GetStateAsString(int state)
{
  switch (state)
  {
    case Init: return "Init";
    case Planning: return "Planning";
    case Confirmed: return "Confirmed";
    default: return "Invalid";
  }
}

//------------------------------------------------------------------------------
int vtkMRMLBezierSurfaceNode::GetStateFromString(const char* name)
{
  if (name == nullptr)
  {
    return -1;
  }
  for (int i = 0; i < ResectionState_Last; ++i)
  {
    if (std::strcmp(name, GetStateAsString(i)) == 0)
    {
      return i;
    }
  }
  return -1;
}

//------------------------------------------------------------------------------
// Read-only-after-Init guarded overrides.  Each forwards to the
// abstract base's setter after the ADR-0014 §4 / ADR-0019 guard
// passes (or short-circuits on rejection).
//------------------------------------------------------------------------------

bool vtkMRMLBezierSurfaceNode::SetSlicingPlaneInitPoint(int index, const double point[3])
{
  if (index < 0 || index > 1 || point == nullptr)
  {
    return false;
  }
  if (this->State != Init && !this->LoadingFromXML)
  {
    vtkWarningMacro("Cannot mutate SlicingPlaneInitPoint[" << index << "] after Init->Planning transition"
                                                           << " (ADR-0014 §4 / ADR-0019 read-only audit data; current state: " << GetStateAsString(this->State) << ")");
    return false;
  }
  return this->Superclass::SetSlicingPlaneInitPoint(index, point);
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::SetSlicingPlaneOrigin(double x, double y, double z)
{
  LIVER_BEZIER_GUARD_INIT_ONLY(SlicingPlaneOrigin);
  this->Superclass::SetSlicingPlaneOrigin(x, y, z);
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::SetSlicingPlaneNormal(double x, double y, double z)
{
  LIVER_BEZIER_GUARD_INIT_ONLY(SlicingPlaneNormal);
  this->Superclass::SetSlicingPlaneNormal(x, y, z);
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::SetNumberOfDistanceSpheroidInitPoints(int n)
{
  LIVER_BEZIER_GUARD_INIT_ONLY(NumberOfDistanceSpheroidInitPoints);
  this->Superclass::SetNumberOfDistanceSpheroidInitPoints(n);
}

//------------------------------------------------------------------------------
bool vtkMRMLBezierSurfaceNode::SetDistanceSpheroidInitPoint(int index, const double point[3])
{
  if (index < 0 || index >= this->NumberOfDistanceSpheroidInitPoints || point == nullptr)
  {
    return false;
  }
  if (this->State != Init && !this->LoadingFromXML)
  {
    vtkWarningMacro("Cannot mutate DistanceSpheroidInitPoint[" << index << "] after Init->Planning transition"
                                                               << " (ADR-0014 §4 / ADR-0019 read-only audit data; current state: " << GetStateAsString(this->State) << ")");
    return false;
  }
  return this->Superclass::SetDistanceSpheroidInitPoint(index, point);
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::SetDistanceSpheroidCenter(double x, double y, double z)
{
  LIVER_BEZIER_GUARD_INIT_ONLY(DistanceSpheroidCenter);
  this->Superclass::SetDistanceSpheroidCenter(x, y, z);
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::SetDistanceSpheroidRadiusX(double r)
{
  LIVER_BEZIER_GUARD_INIT_ONLY(DistanceSpheroidRadiusX);
  this->Superclass::SetDistanceSpheroidRadiusX(r);
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::SetDistanceSpheroidRadiusY(double r)
{
  LIVER_BEZIER_GUARD_INIT_ONLY(DistanceSpheroidRadiusY);
  this->Superclass::SetDistanceSpheroidRadiusY(r);
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::SetDistanceSpheroidRadiusZ(double r)
{
  LIVER_BEZIER_GUARD_INIT_ONLY(DistanceSpheroidRadiusZ);
  this->Superclass::SetDistanceSpheroidRadiusZ(r);
}

//------------------------------------------------------------------------------
namespace
{
/// Bernstein basis polynomial B_{i,n}(t) = C(n, i) t^i (1-t)^(n-i).
/// Computed directly for the small degrees (n in [2, 3]) admitted by
/// ADR-0018 §1.
double bernstein(int i, int n, double t)
{
  // Binomial coefficient via factorial — n is at most 3, so this is
  // cheap.
  static const double binomTable[4][4] = {
    { 1, 0, 0, 0 },
    { 1, 1, 0, 0 },
    { 1, 2, 1, 0 },
    { 1, 3, 3, 1 },
  };
  if (n < 0 || n > 3 || i < 0 || i > n)
  {
    return 0.0;
  }
  double tn = 1.0;
  double mtn = 1.0;
  for (int k = 0; k < i; ++k)
  {
    tn *= t;
  }
  for (int k = 0; k < n - i; ++k)
  {
    mtn *= (1.0 - t);
  }
  return binomTable[n][i] * tn * mtn;
}
} // namespace

//------------------------------------------------------------------------------
vtkPolyData* vtkMRMLBezierSurfaceNode::EvaluateSurface(double u, double v)
{
  // Sample the Bezier surface at the single (u, v) coordinate and
  // emit a 1-point vtkPolyData.  The polymorphic-interface contract
  // (vtkMRMLAbstractParametricSurfaceNode::EvaluateSurface) only
  // requires "non-empty vtkPolyData"; a single-point sample is a
  // valid evaluator output and is what the test invariant pins.
  // Higher-density sampling lives on the Pipeline side
  // (LiverBezierSurfacePipeline), not on the data node.
  vtkPolyData* result = vtkPolyData::New();
  vtkNew<vtkPoints> points;

  const unsigned int rows = this->Rows;
  const unsigned int cols = this->Cols;
  const int degU = static_cast<int>(rows) - 1;
  const int degV = static_cast<int>(cols) - 1;

  double sample[3] = { 0.0, 0.0, 0.0 };
  const double* grid = this->ControlGrid.data();
  for (unsigned int i = 0; i < rows; ++i)
  {
    const double bu = bernstein(static_cast<int>(i), degU, u);
    for (unsigned int j = 0; j < cols; ++j)
    {
      const double bv = bernstein(static_cast<int>(j), degV, v);
      const double w = bu * bv;
      const size_t base = (static_cast<size_t>(i) * cols + j) * 3;
      sample[0] += w * grid[base + 0];
      sample[1] += w * grid[base + 1];
      sample[2] += w * grid[base + 2];
    }
  }
  points->InsertNextPoint(sample);
  result->SetPoints(points);
  return result;
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::WriteXML(ostream& of, int nIndent)
{
  // Superclass writes the shared roster (Rows, Cols, ControlGrid,
  // InitMode, slicing-plane + spheroid subordinates).  Bezier adds
  // the State enum on top.
  Superclass::WriteXML(of, nIndent);

  vtkMRMLWriteXMLBeginMacro(of);
  vtkMRMLWriteXMLEnumMacro(state, State);
  vtkMRMLWriteXMLEndMacro();
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::ReadXMLAttributes(const char** atts)
{
  int disabledModify = this->StartModify();

  // ADR-0014 §4 read-only guard is *only* for public-API mutation.
  // XML deserialisation is internal load — temporarily exempt the
  // guards so a scene serialised with ``state="Planning"`` does not
  // reject the subsequent slicing-plane / spheroid attribute reads.
  const bool wasLoadingFromXML = this->LoadingFromXML;
  this->LoadingFromXML = true;

  Superclass::ReadXMLAttributes(atts);

  vtkMRMLReadXMLBeginMacro(atts);
  vtkMRMLReadXMLEnumMacro(state, State);
  vtkMRMLReadXMLEndMacro();

  this->LoadingFromXML = wasLoadingFromXML;
  this->EndModify(disabledModify);
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::CopyContent(vtkMRMLNode* anode, bool deepCopy /*=true*/)
{
  MRMLNodeModifyBlocker blocker(this);
  Superclass::CopyContent(anode, deepCopy);

  vtkMRMLBezierSurfaceNode* other = vtkMRMLBezierSurfaceNode::SafeDownCast(anode);
  if (other == nullptr)
  {
    return;
  }

  this->State = other->State;
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::CreateDefaultDisplayNodes()
{
  if (vtkMRMLParametricSurfaceDisplayNode::SafeDownCast(this->GetDisplayNode()) != nullptr)
  {
    // Display node already exists.
    return;
  }
  if (this->GetScene() == nullptr)
  {
    vtkErrorMacro("vtkMRMLBezierSurfaceNode::CreateDefaultDisplayNodes"
                  " failed: scene is invalid");
    return;
  }
  auto displayNode = vtkSmartPointer<vtkMRMLParametricSurfaceDisplayNode>::New();
  this->GetScene()->AddNode(displayNode);
  this->SetAndObserveDisplayNodeID(displayNode->GetID());

  // The control polygon is a first-class display aspect with its OWN display
  // node (ADR-0033): mint it alongside the surface display so the
  // ControlPolygonPipeline renders the handles + edges and hosts the
  // per-point drag, independently visible/stylable from the surface.
  auto controlPolygonDisplayNode = vtkSmartPointer<vtkMRMLControlPolygonDisplayNode>::New();
  this->GetScene()->AddNode(controlPolygonDisplayNode);
  this->AddAndObserveDisplayNodeID(controlPolygonDisplayNode->GetID());
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);

  vtkMRMLPrintBeginMacro(os, indent);
  vtkMRMLPrintEnumMacro(State);
  vtkMRMLPrintEnumMacro(InitMode);
  vtkMRMLPrintEndMacro();
}

//------------------------------------------------------------------------------
// File-local guard macro defined at top — undef at end-of-file.
#undef LIVER_BEZIER_GUARD_INIT_ONLY

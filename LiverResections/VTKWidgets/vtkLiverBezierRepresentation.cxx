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
  v2.0.0 release tracker — see ADR-0014 §3).

==============================================================================*/

#include "vtkLiverBezierRepresentation.h"

// MRML includes
#include <vtkMRMLBezierSurfaceNode.h>

// VTK includes
#include <vtkActor.h>
#include <vtkCamera.h>
#include <vtkCellArray.h>
#include <vtkInteractorObserver.h>
#include <vtkMath.h>
#include <vtkObjectFactory.h>
#include <vtkPlane.h>
#include <vtkPoints.h>
#include <vtkPolyData.h>
#include <vtkPolyDataMapper.h>
#include <vtkPropCollection.h>
#include <vtkPropPicker.h>
#include <vtkProperty.h>
#include <vtkRenderer.h>
#include <vtkSphereSource.h>
#include <vtkUnsignedCharArray.h>

// STD includes
#include <algorithm>
#include <cmath>

//------------------------------------------------------------------------------
vtkStandardNewMacro(vtkLiverBezierRepresentation);

namespace
{
// Sentinel pick-tolerance in world units.  The widget converts a
// display-space mouse cursor to a world ray via the renderer's camera,
// and a control point counts as picked if the perpendicular world-
// space distance from the ray to the point falls below this threshold.
// Calibrated to match the visual radius of the glyph cloud below.
constexpr double kPickRadiusWorld = 5.0;
constexpr double kGlyphRadius = 2.5;

} // anonymous namespace

//------------------------------------------------------------------------------
vtkLiverBezierRepresentation::vtkLiverBezierRepresentation()
  : LastBuildDataMTime(0)
{
  this->GlyphPolyData = vtkSmartPointer<vtkPolyData>::New();
  vtkNew<vtkPoints> points;
  this->GlyphPolyData->SetPoints(points);
  vtkNew<vtkCellArray> verts;
  this->GlyphPolyData->SetVerts(verts);

  this->GlyphSource = vtkSmartPointer<vtkSphereSource>::New();
  this->GlyphSource->SetRadius(kGlyphRadius);
  this->GlyphSource->SetThetaResolution(8);
  this->GlyphSource->SetPhiResolution(8);

  this->GlyphMapper = vtkSmartPointer<vtkPolyDataMapper>::New();
  // The mapper is here as a placeholder render target; the actual
  // per-role glyph treatment + relocated mapper land in the
  // TODO(T2-mapper-relocation) follow-up.  For the skeleton scope this
  // class only needs the picker + the actor lifecycle to be sound.
  this->GlyphMapper->SetInputConnection(this->GlyphSource->GetOutputPort());
  this->GlyphActor = vtkSmartPointer<vtkActor>::New();
  this->GlyphActor->SetMapper(this->GlyphMapper);
  this->GlyphActor->VisibilityOff();

  this->HighlightSource = vtkSmartPointer<vtkSphereSource>::New();
  this->HighlightSource->SetRadius(kGlyphRadius * 1.4);
  this->HighlightSource->SetThetaResolution(12);
  this->HighlightSource->SetPhiResolution(12);
  this->HighlightMapper = vtkSmartPointer<vtkPolyDataMapper>::New();
  this->HighlightMapper->SetInputConnection(this->HighlightSource->GetOutputPort());
  this->HighlightActor = vtkSmartPointer<vtkActor>::New();
  this->HighlightActor->SetMapper(this->HighlightMapper);
  this->HighlightActor->GetProperty()->SetColor(1.0, 0.85, 0.1);
  this->HighlightActor->VisibilityOff();

  this->Picker = vtkSmartPointer<vtkPropPicker>::New();
}

//------------------------------------------------------------------------------
vtkLiverBezierRepresentation::~vtkLiverBezierRepresentation() = default;

//------------------------------------------------------------------------------
void vtkLiverBezierRepresentation::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);
  os << indent << "BezierNode: " << (this->BezierNode.GetPointer() ? "set" : "(null)") << "\n";
  os << indent << "LastBuildDataMTime: " << this->LastBuildDataMTime << "\n";
}

//------------------------------------------------------------------------------
void vtkLiverBezierRepresentation::SetBezierNode(vtkMRMLBezierSurfaceNode* node)
{
  if (this->BezierNode.GetPointer() == node)
  {
    return;
  }
  this->BezierNode = node;
  this->LastBuildDataMTime = 0;
  this->Modified();
}

//------------------------------------------------------------------------------
vtkMRMLBezierSurfaceNode* vtkLiverBezierRepresentation::GetBezierNode()
{
  return this->BezierNode.GetPointer();
}

//------------------------------------------------------------------------------
void vtkLiverBezierRepresentation::UpdatePickableGlyphs()
{
  vtkMRMLBezierSurfaceNode* node = this->BezierNode.GetPointer();
  vtkPoints* points = this->GlyphPolyData->GetPoints();
  vtkCellArray* verts = this->GlyphPolyData->GetVerts();
  points->Reset();
  verts->Reset();
  if (!node)
  {
    this->GlyphPolyData->Modified();
    return;
  }

  // ADR-0014 §3 + ADR-0019 — pickable set depends on (State, InitMode).
  // In ``Confirmed`` the control polygon is hidden and the widget is
  // disabled (per ADR-0019 §"Per-state contract"), so no points are
  // pickable.  In ``Planning`` the 16 Bezier control-grid points are
  // pickable; in ``Init`` the init-mode subordinate points are.
  const int state = node->GetState();
  const int mode = node->GetInitMode();

  auto pushPoint = [&](double x, double y, double z)
  {
    const vtkIdType id = points->InsertNextPoint(x, y, z);
    verts->InsertNextCell(1, &id);
  };

  if (state == vtkMRMLBezierSurfaceNode::Confirmed)
  {
    // No pickable glyphs in Confirmed — ADR-0019 §"Per-state contract"
    // commits to "control polygon hidden, widget disabled".  The
    // empty glyph cloud below makes ``BuildRepresentation`` hide the
    // glyph actor on the next render pass.
  }
  else if (state == vtkMRMLBezierSurfaceNode::Planning)
  {
    // Per ADR-0018 §1 the per-node Bezier control polygon is
    // ``Rows × Cols`` points (9 for 3×3, 16 for 4×4); query the
    // shape from the data node.  Tear-down of the previous glyph
    // cloud is handled by the ``points->Reset()`` / ``verts->Reset()``
    // above — the cloud size on the next BuildRepresentation()
    // matches the data node's current shape.
    const double* grid = node->GetControlGrid();
    const unsigned int controlPointCount = node->GetRows() * node->GetCols();
    for (unsigned int i = 0; i < controlPointCount; ++i)
    {
      pushPoint(grid[i * 3 + 0], grid[i * 3 + 1], grid[i * 3 + 2]);
    }
  }
  else if (state == vtkMRMLBezierSurfaceNode::Init)
  {
    if (mode == vtkMRMLBezierSurfaceNode::SlicingPlane)
    {
      for (int i = 0; i < 2; ++i)
      {
        const double* p = node->GetSlicingPlaneInitPoint(i);
        if (p)
        {
          pushPoint(p[0], p[1], p[2]);
        }
      }
    }
    else // DistanceSpheroid
    {
      const int n = node->GetNumberOfDistanceSpheroidInitPoints();
      for (int i = 0; i < n; ++i)
      {
        const double* p = node->GetDistanceSpheroidInitPoint(i);
        if (p)
        {
          pushPoint(p[0], p[1], p[2]);
        }
      }
    }
  }
  else
  {
    // Per ADR-0019 §"Per-state contract", in any state other than
    // ``Init`` / ``Planning`` (i.e. the future ``Confirmed = 2``
    // value the enum will grow when ADR-0019's enabler PR lands) the
    // control polygon is **hidden** and the widget is **disabled**.
    // Leave the glyph cloud empty — the ``points->Reset()`` /
    // ``verts->Reset()`` above already cleared it; nothing further to
    // push.  ``BuildRepresentation`` turns the glyph actor invisible
    // when ``GetNumberOfPoints() == 0``, matching the
    // hidden-polygon + disabled-widget invariant.
  }

  this->GlyphPolyData->Modified();
}

//------------------------------------------------------------------------------
void vtkLiverBezierRepresentation::BuildRepresentation()
{
  vtkMRMLBezierSurfaceNode* node = this->BezierNode.GetPointer();
  if (!node)
  {
    this->GlyphActor->VisibilityOff();
    this->HighlightActor->VisibilityOff();
    return;
  }
  const vtkMTimeType nodeMTime = node->GetMTime();
  if (nodeMTime != this->LastBuildDataMTime)
  {
    this->UpdatePickableGlyphs();
    this->LastBuildDataMTime = nodeMTime;
  }
  this->GlyphActor->SetVisibility(this->GlyphPolyData->GetNumberOfPoints() > 0 ? 1 : 0);
}

//------------------------------------------------------------------------------
int vtkLiverBezierRepresentation::ComputeInteractionState(int X, int Y, int /*modify*/)
{
  // The widget owns the substate enum; this method exists to satisfy
  // the vtkWidgetRepresentation contract (returning a non-zero state
  // when the cursor is over a pickable primitive).  A hit returns
  // ``Picked`` (1); a miss returns ``Outside`` (0).
  PickResult res = this->Pick(X, Y);
  this->InteractionState = (res.Role == PickRole_None) ? 0 : 1;
  return this->InteractionState;
}

//------------------------------------------------------------------------------
vtkLiverBezierRepresentation::PickResult vtkLiverBezierRepresentation::Pick(int X, int Y)
{
  PickResult result;
  vtkMRMLBezierSurfaceNode* node = this->BezierNode.GetPointer();
  if (!node)
  {
    return result;
  }
  vtkRenderer* renderer = this->GetRenderer();
  if (!renderer)
  {
    return result;
  }

  // Convert (X, Y) to a world-space ray through the camera.  For the
  // skeleton scope, the picker is a simple nearest-point-on-ray test
  // against the pickable point cloud.  The production widget pairs
  // each glyph with a vtkActor and uses vtkPropPicker, but the cloud
  // is small (≤ 16 points) and the ray test stays trivially correct
  // under headless interactor.
  double nearWorld[4] = { 0.0, 0.0, 0.0, 1.0 };
  double farWorld[4] = { 0.0, 0.0, 0.0, 1.0 };
  vtkInteractorObserver::ComputeDisplayToWorld(renderer, static_cast<double>(X), static_cast<double>(Y), 0.0, nearWorld);
  vtkInteractorObserver::ComputeDisplayToWorld(renderer, static_cast<double>(X), static_cast<double>(Y), 1.0, farWorld);

  double rayOrigin[3] = { nearWorld[0], nearWorld[1], nearWorld[2] };
  double rayDir[3] = { farWorld[0] - nearWorld[0], farWorld[1] - nearWorld[1], farWorld[2] - nearWorld[2] };
  vtkMath::Normalize(rayDir);

  // ADR-0014 §3 + ADR-0019 — pickability is state-gated.  In
  // ``Confirmed`` the widget is disabled, so every (X, Y) is a miss
  // regardless of where the cursor lands.
  const int state = node->GetState();
  const int mode = node->GetInitMode();
  if (state == vtkMRMLBezierSurfaceNode::Confirmed)
  {
    return result;
  }

  // Helper: distance from point to ray.
  auto distanceToRay = [&](const double p[3])
  {
    double op[3] = { p[0] - rayOrigin[0], p[1] - rayOrigin[1], p[2] - rayOrigin[2] };
    const double dot = vtkMath::Dot(op, rayDir);
    double closest[3] = { rayOrigin[0] + dot * rayDir[0], rayOrigin[1] + dot * rayDir[1], rayOrigin[2] + dot * rayDir[2] };
    return std::sqrt(vtkMath::Distance2BetweenPoints(p, closest));
  };

  double bestDist = kPickRadiusWorld;
  if (state == vtkMRMLBezierSurfaceNode::Planning)
  {
    // Per ADR-0018 §1 the pickable control-point set is
    // ``Rows * Cols`` (9 for 3×3, 16 for 4×4).  The index returned
    // in PickResult is grid-flat (i * Cols + j); callers that need
    // (row, col) can recover it via the data node's Rows / Cols.
    const double* grid = node->GetControlGrid();
    const int controlPointCount = static_cast<int>(node->GetRows() * node->GetCols());
    for (int i = 0; i < controlPointCount; ++i)
    {
      const double p[3] = { grid[i * 3 + 0], grid[i * 3 + 1], grid[i * 3 + 2] };
      const double d = distanceToRay(p);
      if (d < bestDist)
      {
        bestDist = d;
        result.Role = PickRole_ControlPoint;
        result.Index = i;
      }
    }
  }
  else if (state == vtkMRMLBezierSurfaceNode::Init) // init-mode points become pickable.
  {
    if (mode == vtkMRMLBezierSurfaceNode::SlicingPlane)
    {
      for (int i = 0; i < 2; ++i)
      {
        const double* p = node->GetSlicingPlaneInitPoint(i);
        if (!p)
        {
          continue;
        }
        const double d = distanceToRay(p);
        if (d < bestDist)
        {
          bestDist = d;
          result.Role = PickRole_SlicingPlaneInit;
          result.Index = i;
        }
      }
    }
    else // DistanceSpheroid
    {
      const int n = node->GetNumberOfDistanceSpheroidInitPoints();
      for (int i = 0; i < n; ++i)
      {
        const double* p = node->GetDistanceSpheroidInitPoint(i);
        if (!p)
        {
          continue;
        }
        const double d = distanceToRay(p);
        if (d < bestDist)
        {
          bestDist = d;
          result.Role = PickRole_DistanceSpheroidInit;
          result.Index = i;
        }
      }
    }
  }
  // else: future ``Confirmed`` state per ADR-0019 §"Per-state contract"
  // — widget is disabled, nothing is pickable.  Fall through and
  // return ``PickRole_None``.

  return result;
}

//------------------------------------------------------------------------------
bool vtkLiverBezierRepresentation::DisplayToWorld(int X, int Y, const double referenceWorld[3], double worldOut[3])
{
  vtkRenderer* renderer = this->GetRenderer();
  if (!renderer || !referenceWorld || !worldOut)
  {
    return false;
  }
  // Project the (X, Y) cursor onto the plane parallel to the camera
  // that passes through the reference world point.  This is the
  // standard VTK widget pattern for converting a 2-D mouse-move into
  // a 3-D point update.
  double cameraFocal[3];
  double cameraPos[3];
  vtkCamera* camera = renderer->GetActiveCamera();
  if (!camera)
  {
    return false;
  }
  camera->GetFocalPoint(cameraFocal);
  camera->GetPosition(cameraPos);
  double planeNormal[3] = { cameraFocal[0] - cameraPos[0], cameraFocal[1] - cameraPos[1], cameraFocal[2] - cameraPos[2] };
  if (vtkMath::Norm(planeNormal) < 1e-9)
  {
    return false;
  }
  vtkMath::Normalize(planeNormal);

  double nearWorld[4] = { 0.0, 0.0, 0.0, 1.0 };
  double farWorld[4] = { 0.0, 0.0, 0.0, 1.0 };
  vtkInteractorObserver::ComputeDisplayToWorld(renderer, static_cast<double>(X), static_cast<double>(Y), 0.0, nearWorld);
  vtkInteractorObserver::ComputeDisplayToWorld(renderer, static_cast<double>(X), static_cast<double>(Y), 1.0, farWorld);
  double rayDir[3] = { farWorld[0] - nearWorld[0], farWorld[1] - nearWorld[1], farWorld[2] - nearWorld[2] };
  vtkMath::Normalize(rayDir);
  double rayOrigin[3] = { nearWorld[0], nearWorld[1], nearWorld[2] };
  double rayFar[3] = { rayOrigin[0] + rayDir[0] * 1.0e6, rayOrigin[1] + rayDir[1] * 1.0e6, rayOrigin[2] + rayDir[2] * 1.0e6 };
  double refCopy[3] = { referenceWorld[0], referenceWorld[1], referenceWorld[2] };
  double t = 0.0;
  if (vtkPlane::IntersectWithLine(rayOrigin, rayFar, planeNormal, refCopy, t, worldOut) == 0)
  {
    return false;
  }
  return true;
}

//------------------------------------------------------------------------------
void vtkLiverBezierRepresentation::GetActors(vtkPropCollection* pc)
{
  if (!pc)
  {
    return;
  }
  pc->AddItem(this->GlyphActor);
  pc->AddItem(this->HighlightActor);
}

//------------------------------------------------------------------------------
void vtkLiverBezierRepresentation::ReleaseGraphicsResources(vtkWindow* w)
{
  this->GlyphActor->ReleaseGraphicsResources(w);
  this->HighlightActor->ReleaseGraphicsResources(w);
}

//------------------------------------------------------------------------------
int vtkLiverBezierRepresentation::RenderOverlay(vtkViewport* viewport)
{
  int count = 0;
  if (this->GlyphActor->GetVisibility())
  {
    count += this->GlyphActor->RenderOverlay(viewport);
  }
  if (this->HighlightActor->GetVisibility())
  {
    count += this->HighlightActor->RenderOverlay(viewport);
  }
  return count;
}

//------------------------------------------------------------------------------
int vtkLiverBezierRepresentation::RenderOpaqueGeometry(vtkViewport* viewport)
{
  this->BuildRepresentation();
  int count = 0;
  if (this->GlyphActor->GetVisibility())
  {
    count += this->GlyphActor->RenderOpaqueGeometry(viewport);
  }
  if (this->HighlightActor->GetVisibility())
  {
    count += this->HighlightActor->RenderOpaqueGeometry(viewport);
  }
  return count;
}

//------------------------------------------------------------------------------
int vtkLiverBezierRepresentation::RenderTranslucentPolygonalGeometry(vtkViewport* viewport)
{
  int count = 0;
  if (this->GlyphActor->GetVisibility())
  {
    count += this->GlyphActor->RenderTranslucentPolygonalGeometry(viewport);
  }
  if (this->HighlightActor->GetVisibility())
  {
    count += this->HighlightActor->RenderTranslucentPolygonalGeometry(viewport);
  }
  return count;
}

//------------------------------------------------------------------------------
vtkTypeBool vtkLiverBezierRepresentation::HasTranslucentPolygonalGeometry()
{
  return this->GlyphActor->HasTranslucentPolygonalGeometry() || this->HighlightActor->HasTranslucentPolygonalGeometry();
}

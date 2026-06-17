/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Implementation of the parametric-surface abstract base
  (vtkMRMLAbstractParametricSurfaceNode).  Non-instantiable per
  vtkAbstractTypeMacro; concrete subclasses (vtkMRMLBezierSurfaceNode
  today, vtkMRMLNurbsSurfaceNode in v2.1) supply New() via
  vtkStandardNewMacro and override GetSurfaceType / EvaluateSurface.

  See ADR-0023 amendment 2026-05-25 §"Class abstraction for surfaces"
  and ADR-0018 amendment 2026-05-25 for the design rationale.

==============================================================================*/

// This module MRML includes
#include "vtkMRMLAbstractParametricSurfaceNode.h"

// MRML includes
#include <vtkMRMLNodePropertyMacros.h>

// VTK includes
#include <vtkNew.h>

// STD includes
#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <string>

//------------------------------------------------------------------------------
vtkMRMLAbstractParametricSurfaceNode::vtkMRMLAbstractParametricSurfaceNode()
  : InitMode(SlicingPlane)
  , Rows(DefaultGridSize)
  , Cols(DefaultGridSize)
  , NumberOfDistanceSpheroidInitPoints(0)
  , DistanceSpheroidRadiusX(0.0)
  , DistanceSpheroidRadiusY(0.0)
  , DistanceSpheroidRadiusZ(0.0)
{
  this->ControlGrid.assign(static_cast<size_t>(3u) * this->Rows * this->Cols, 0.0);

  for (int i = 0; i < 2; ++i)
  {
    for (int j = 0; j < 3; ++j)
    {
      this->SlicingPlaneInitPoints[i][j] = 0.0;
    }
  }
  this->SlicingPlaneOrigin[0] = 0.0;
  this->SlicingPlaneOrigin[1] = 0.0;
  this->SlicingPlaneOrigin[2] = 0.0;
  this->SlicingPlaneNormal[0] = 0.0;
  this->SlicingPlaneNormal[1] = 0.0;
  this->SlicingPlaneNormal[2] = 1.0;

  this->DistanceSpheroidCenter[0] = 0.0;
  this->DistanceSpheroidCenter[1] = 0.0;
  this->DistanceSpheroidCenter[2] = 0.0;
}

//------------------------------------------------------------------------------
vtkMRMLAbstractParametricSurfaceNode::~vtkMRMLAbstractParametricSurfaceNode() = default;

//------------------------------------------------------------------------------
vtkMRMLStorageNode* vtkMRMLAbstractParametricSurfaceNode::CreateDefaultStorageNode()
{
  // Parametric surfaces are non-storable per the wrapper-vs-carrier
  // pattern (ADR-0023 amendment 2026-05-25 §"Decision -- surface-side
  // data ownership").  Persistence flows through the wrapping
  // vtkMRMLResectionPlanStorageNode (.lrp.json).
  return nullptr;
}

//------------------------------------------------------------------------------
const char* vtkMRMLAbstractParametricSurfaceNode::GetInitModeAsString(int mode)
{
  switch (mode)
  {
    case SlicingPlane: return "SlicingPlane";
    case DistanceSpheroid: return "DistanceSpheroid";
    default: return "Invalid";
  }
}

//------------------------------------------------------------------------------
int vtkMRMLAbstractParametricSurfaceNode::GetInitModeFromString(const char* name)
{
  if (name == nullptr)
  {
    return -1;
  }
  for (int i = 0; i < InitializationMode_Last; ++i)
  {
    if (std::strcmp(name, GetInitModeAsString(i)) == 0)
    {
      return i;
    }
  }
  return -1;
}

//------------------------------------------------------------------------------
void vtkMRMLAbstractParametricSurfaceNode::SetSize(unsigned int n)
{
  if (static_cast<int>(n) < MinGridSize || static_cast<int>(n) > MaxGridSize)
  {
    vtkErrorMacro("SetSize: invalid grid size " << n << "; ADR-0018 §1 admits {" << MinGridSize << ", " << MaxGridSize << "} only — leaving shape at (" << this->Rows << ", "
                                                << this->Cols << ")");
    return;
  }
  if (this->Rows == n && this->Cols == n)
  {
    return;
  }
  this->Rows = n;
  this->Cols = n;
  this->ControlGrid.assign(static_cast<size_t>(3u) * this->Rows * this->Cols, 0.0);
  this->Modified();
}

//------------------------------------------------------------------------------
void vtkMRMLAbstractParametricSurfaceNode::SetRows(unsigned int rows)
{
  if (static_cast<int>(rows) < MinGridSize || static_cast<int>(rows) > MaxGridSize)
  {
    vtkErrorMacro("SetRows: invalid Rows " << rows << "; ADR-0018 §1 admits {" << MinGridSize << ", " << MaxGridSize << "} only — leaving Rows at " << this->Rows);
    return;
  }
  if (rows != this->Cols)
  {
    vtkErrorMacro("SetRows: non-square shape (Rows=" << rows << ", Cols=" << this->Cols
                                                     << ") not admitted (ADR-0018 §1); use SetSize() to change both axes atomically — leaving Rows at " << this->Rows);
    return;
  }
  if (rows == this->Rows)
  {
    return;
  }
  this->Rows = rows;
  this->ControlGrid.assign(static_cast<size_t>(3u) * this->Rows * this->Cols, 0.0);
  this->Modified();
}

//------------------------------------------------------------------------------
void vtkMRMLAbstractParametricSurfaceNode::SetCols(unsigned int cols)
{
  if (static_cast<int>(cols) < MinGridSize || static_cast<int>(cols) > MaxGridSize)
  {
    vtkErrorMacro("SetCols: invalid Cols " << cols << "; ADR-0018 §1 admits {" << MinGridSize << ", " << MaxGridSize << "} only — leaving Cols at " << this->Cols);
    return;
  }
  if (cols != this->Rows)
  {
    vtkErrorMacro("SetCols: non-square shape (Rows=" << this->Rows << ", Cols=" << cols
                                                     << ") not admitted (ADR-0018 §1); use SetSize() to change both axes atomically — leaving Cols at " << this->Cols);
    return;
  }
  if (cols == this->Cols)
  {
    return;
  }
  this->Cols = cols;
  this->ControlGrid.assign(static_cast<size_t>(3u) * this->Rows * this->Cols, 0.0);
  this->Modified();
}

//------------------------------------------------------------------------------
bool vtkMRMLAbstractParametricSurfaceNode::SetControlGrid(const double* values)
{
  if (values == nullptr)
  {
    return false;
  }
  const size_t length = this->ControlGrid.size();
  std::copy_n(values, length, this->ControlGrid.begin());
  this->Modified();
  return true;
}

//------------------------------------------------------------------------------
bool vtkMRMLAbstractParametricSurfaceNode::SetSlicingPlaneInitPoint(int index, const double point[3])
{
  if (index < 0 || index > 1 || point == nullptr)
  {
    return false;
  }
  this->SlicingPlaneInitPoints[index][0] = point[0];
  this->SlicingPlaneInitPoints[index][1] = point[1];
  this->SlicingPlaneInitPoints[index][2] = point[2];
  this->Modified();
  return true;
}

//------------------------------------------------------------------------------
const double* vtkMRMLAbstractParametricSurfaceNode::GetSlicingPlaneInitPoint(int index) const
{
  // Returns a 3-double vector (VTK_SIZEHINT(3) on the declaration).  An
  // out-of-range index yields a zero vector rather than nullptr: the
  // Python wrapper unconditionally reads 3 doubles to build the tuple, so
  // a null return would dereference null and crash the interpreter.
  static const double kZeroVec[3] = { 0.0, 0.0, 0.0 };
  if (index < 0 || index > 1)
  {
    vtkWarningMacro("GetSlicingPlaneInitPoint: index " << index << " out of range [0, 1]; returning zero vector");
    return kZeroVec;
  }
  return this->SlicingPlaneInitPoints[index];
}

//------------------------------------------------------------------------------
void vtkMRMLAbstractParametricSurfaceNode::SetSlicingPlaneOrigin(double x, double y, double z)
{
  if (this->SlicingPlaneOrigin[0] == x && this->SlicingPlaneOrigin[1] == y && this->SlicingPlaneOrigin[2] == z)
  {
    return;
  }
  this->SlicingPlaneOrigin[0] = x;
  this->SlicingPlaneOrigin[1] = y;
  this->SlicingPlaneOrigin[2] = z;
  this->Modified();
}

//------------------------------------------------------------------------------
void vtkMRMLAbstractParametricSurfaceNode::SetSlicingPlaneOrigin(const double xyz[3])
{
  this->SetSlicingPlaneOrigin(xyz[0], xyz[1], xyz[2]);
}

//------------------------------------------------------------------------------
void vtkMRMLAbstractParametricSurfaceNode::SetSlicingPlaneNormal(double x, double y, double z)
{
  if (this->SlicingPlaneNormal[0] == x && this->SlicingPlaneNormal[1] == y && this->SlicingPlaneNormal[2] == z)
  {
    return;
  }
  this->SlicingPlaneNormal[0] = x;
  this->SlicingPlaneNormal[1] = y;
  this->SlicingPlaneNormal[2] = z;
  this->Modified();
}

//------------------------------------------------------------------------------
void vtkMRMLAbstractParametricSurfaceNode::SetSlicingPlaneNormal(const double xyz[3])
{
  this->SetSlicingPlaneNormal(xyz[0], xyz[1], xyz[2]);
}

//------------------------------------------------------------------------------
void vtkMRMLAbstractParametricSurfaceNode::SetNumberOfDistanceSpheroidInitPoints(int n)
{
  if (n < 0)
  {
    n = 0;
  }
  if (n == this->NumberOfDistanceSpheroidInitPoints)
  {
    return;
  }
  this->NumberOfDistanceSpheroidInitPoints = n;
  this->DistanceSpheroidInitPoints.assign(static_cast<size_t>(n) * 3, 0.0);
  this->Modified();
}

//------------------------------------------------------------------------------
bool vtkMRMLAbstractParametricSurfaceNode::SetDistanceSpheroidInitPoint(int index, const double point[3])
{
  if (index < 0 || index >= this->NumberOfDistanceSpheroidInitPoints || point == nullptr)
  {
    return false;
  }
  const size_t base = static_cast<size_t>(index) * 3;
  this->DistanceSpheroidInitPoints[base + 0] = point[0];
  this->DistanceSpheroidInitPoints[base + 1] = point[1];
  this->DistanceSpheroidInitPoints[base + 2] = point[2];
  this->Modified();
  return true;
}

//------------------------------------------------------------------------------
const double* vtkMRMLAbstractParametricSurfaceNode::GetDistanceSpheroidInitPoint(int index) const
{
  // Zero vector (not nullptr) for an out-of-range index — see the
  // GetSlicingPlaneInitPoint note: VTK_SIZEHINT(3) makes the wrapper read
  // 3 doubles, so a null return would crash the Python interpreter.
  static const double kZeroVec[3] = { 0.0, 0.0, 0.0 };
  if (index < 0 || index >= this->NumberOfDistanceSpheroidInitPoints)
  {
    vtkWarningMacro("GetDistanceSpheroidInitPoint: index " << index << " out of range [0, " << this->NumberOfDistanceSpheroidInitPoints << "); returning zero vector");
    return kZeroVec;
  }
  return &this->DistanceSpheroidInitPoints[static_cast<size_t>(index) * 3];
}

//------------------------------------------------------------------------------
void vtkMRMLAbstractParametricSurfaceNode::SetDistanceSpheroidCenter(double x, double y, double z)
{
  if (this->DistanceSpheroidCenter[0] == x && this->DistanceSpheroidCenter[1] == y && this->DistanceSpheroidCenter[2] == z)
  {
    return;
  }
  this->DistanceSpheroidCenter[0] = x;
  this->DistanceSpheroidCenter[1] = y;
  this->DistanceSpheroidCenter[2] = z;
  this->Modified();
}

//------------------------------------------------------------------------------
void vtkMRMLAbstractParametricSurfaceNode::SetDistanceSpheroidCenter(const double xyz[3])
{
  this->SetDistanceSpheroidCenter(xyz[0], xyz[1], xyz[2]);
}

//------------------------------------------------------------------------------
void vtkMRMLAbstractParametricSurfaceNode::SetDistanceSpheroidRadiusX(double r)
{
  if (r < 0.0)
  {
    r = 0.0;
  }
  if (this->DistanceSpheroidRadiusX == r)
  {
    return;
  }
  this->DistanceSpheroidRadiusX = r;
  this->Modified();
}

//------------------------------------------------------------------------------
void vtkMRMLAbstractParametricSurfaceNode::SetDistanceSpheroidRadiusY(double r)
{
  if (r < 0.0)
  {
    r = 0.0;
  }
  if (this->DistanceSpheroidRadiusY == r)
  {
    return;
  }
  this->DistanceSpheroidRadiusY = r;
  this->Modified();
}

//------------------------------------------------------------------------------
void vtkMRMLAbstractParametricSurfaceNode::SetDistanceSpheroidRadiusZ(double r)
{
  if (r < 0.0)
  {
    r = 0.0;
  }
  if (this->DistanceSpheroidRadiusZ == r)
  {
    return;
  }
  this->DistanceSpheroidRadiusZ = r;
  this->Modified();
}

//------------------------------------------------------------------------------
void vtkMRMLAbstractParametricSurfaceNode::WriteXML(ostream& of, int nIndent)
{
  // Slim WriteXML per the design's storage-ownership table
  // (``Docs/design/resection-plan-architecture/03-storage-ownership.md``)
  // and the Markups precedent (``vtkMRMLMarkupsNode::WriteXML`` emits
  // three lightweight scalars only).  Bulk fields (``ControlGrid``,
  // ``InitMode``, slicing-plane + spheroid subordinates) persist via
  // the parent plan's storage path (``.lrp.json``); the ``.mrml``
  // carries only the scene-relevant identity metadata.
  //
  // Scene-load without a paired ``.lrp.json`` recovers the surface
  // with default bulk state — degraded but non-crashing, per
  // ``04-save-load-flows.md`` §"Failure modes".
  Superclass::WriteXML(of, nIndent);

  vtkMRMLWriteXMLBeginMacro(of);
  vtkMRMLWriteXMLIntMacro(rows, Rows);
  vtkMRMLWriteXMLIntMacro(cols, Cols);
  vtkMRMLWriteXMLEndMacro();
}

//------------------------------------------------------------------------------
void vtkMRMLAbstractParametricSurfaceNode::ReadXMLAttributes(const char** atts)
{
  int disabledModify = this->StartModify();

  Superclass::ReadXMLAttributes(atts);

  // Read only the slim WriteXML companion: ``rows`` + ``cols``.  All
  // other fields are populated by the storage node when the
  // ``.lrp.json`` loads.  Rows / cols read manually + validated as a
  // pair (the public ``SetRows`` / ``SetCols`` reject non-square
  // intermediate states; XML load is exempt from the public-API guard).
  unsigned int parsedRows = this->Rows;
  unsigned int parsedCols = this->Cols;
  for (const char** att = atts; att && *att; att += 2)
  {
    const char* name = att[0];
    const char* value = att[1];
    if (value == nullptr)
    {
      continue;
    }
    if (std::strcmp(name, "rows") == 0)
    {
      parsedRows = static_cast<unsigned int>(std::atoi(value));
    }
    else if (std::strcmp(name, "cols") == 0)
    {
      parsedCols = static_cast<unsigned int>(std::atoi(value));
    }
  }
  if (static_cast<int>(parsedRows) < MinGridSize || static_cast<int>(parsedRows) > MaxGridSize || parsedRows != parsedCols)
  {
    vtkWarningMacro("ReadXMLAttributes: invalid (rows=" << parsedRows << ", cols=" << parsedCols << "); ADR-0018 §1 admits {(3,3), (4,4)} only — falling back to "
                                                        << DefaultGridSize << "x" << DefaultGridSize);
    parsedRows = DefaultGridSize;
    parsedCols = DefaultGridSize;
  }
  this->Rows = parsedRows;
  this->Cols = parsedCols;
  this->ControlGrid.assign(static_cast<size_t>(3u) * this->Rows * this->Cols, 0.0);

  this->EndModify(disabledModify);
}

//------------------------------------------------------------------------------
void vtkMRMLAbstractParametricSurfaceNode::CopyContent(vtkMRMLNode* anode, bool deepCopy)
{
  MRMLNodeModifyBlocker blocker(this);
  Superclass::CopyContent(anode, deepCopy);

  vtkMRMLAbstractParametricSurfaceNode* other = vtkMRMLAbstractParametricSurfaceNode::SafeDownCast(anode);
  if (other == nullptr)
  {
    return;
  }

  this->InitMode = other->InitMode;
  this->Rows = other->Rows;
  this->Cols = other->Cols;
  this->ControlGrid = other->ControlGrid;

  for (int i = 0; i < 2; ++i)
  {
    for (int j = 0; j < 3; ++j)
    {
      this->SlicingPlaneInitPoints[i][j] = other->SlicingPlaneInitPoints[i][j];
    }
  }
  for (int j = 0; j < 3; ++j)
  {
    this->SlicingPlaneOrigin[j] = other->SlicingPlaneOrigin[j];
    this->SlicingPlaneNormal[j] = other->SlicingPlaneNormal[j];
    this->DistanceSpheroidCenter[j] = other->DistanceSpheroidCenter[j];
  }
  this->DistanceSpheroidRadiusX = other->DistanceSpheroidRadiusX;
  this->DistanceSpheroidRadiusY = other->DistanceSpheroidRadiusY;
  this->DistanceSpheroidRadiusZ = other->DistanceSpheroidRadiusZ;
  this->NumberOfDistanceSpheroidInitPoints = other->NumberOfDistanceSpheroidInitPoints;
  this->DistanceSpheroidInitPoints = other->DistanceSpheroidInitPoints;
}

//------------------------------------------------------------------------------
void vtkMRMLAbstractParametricSurfaceNode::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);

  vtkMRMLPrintBeginMacro(os, indent);
  vtkMRMLPrintEnumMacro(InitMode);
  vtkMRMLPrintIntMacro(Rows);
  vtkMRMLPrintIntMacro(Cols);
  vtkMRMLPrintVectorMacro(SlicingPlaneOrigin, double, 3);
  vtkMRMLPrintVectorMacro(SlicingPlaneNormal, double, 3);
  vtkMRMLPrintVectorMacro(DistanceSpheroidCenter, double, 3);
  vtkMRMLPrintFloatMacro(DistanceSpheroidRadiusX);
  vtkMRMLPrintFloatMacro(DistanceSpheroidRadiusY);
  vtkMRMLPrintFloatMacro(DistanceSpheroidRadiusZ);
  vtkMRMLPrintIntMacro(NumberOfDistanceSpheroidInitPoints);
  vtkMRMLPrintEndMacro();

  os << indent << "ControlGrid (" << this->ControlGrid.size() << " doubles, " << this->Rows << "x" << this->Cols << "): ";
  for (size_t i = 0; i < this->ControlGrid.size(); ++i)
  {
    if (i > 0)
    {
      os << " ";
    }
    os << this->ControlGrid[i];
  }
  os << "\n";
}

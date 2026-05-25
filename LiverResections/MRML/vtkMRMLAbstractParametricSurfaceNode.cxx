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
#include <sstream>
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
  if (index < 0 || index > 1)
  {
    return nullptr;
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
  if (index < 0 || index >= this->NumberOfDistanceSpheroidInitPoints)
  {
    return nullptr;
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
namespace
{
/// Helper: serialise N doubles to a space-separated string.
std::string writeDoubles(const double* values, std::size_t n)
{
  std::stringstream ss;
  for (std::size_t i = 0; i < n; ++i)
  {
    if (i > 0)
    {
      ss << " ";
    }
    ss << values[i];
  }
  return ss.str();
}

/// Helper: parse N doubles from a space-separated string.
void readDoubles(const char* text, std::vector<double>& out)
{
  out.clear();
  if (text == nullptr)
  {
    return;
  }
  std::stringstream ss(text);
  double v;
  while (ss >> v)
  {
    out.push_back(v);
  }
}
} // namespace

//------------------------------------------------------------------------------
void vtkMRMLAbstractParametricSurfaceNode::WriteXML(ostream& of, int nIndent)
{
  Superclass::WriteXML(of, nIndent);

  vtkMRMLWriteXMLBeginMacro(of);
  vtkMRMLWriteXMLEnumMacro(initMode, InitMode);
  vtkMRMLWriteXMLIntMacro(rows, Rows);
  vtkMRMLWriteXMLIntMacro(cols, Cols);
  vtkMRMLWriteXMLVectorMacro(slicingPlaneOrigin, SlicingPlaneOrigin, double, 3);
  vtkMRMLWriteXMLVectorMacro(slicingPlaneNormal, SlicingPlaneNormal, double, 3);
  vtkMRMLWriteXMLVectorMacro(distanceSpheroidCenter, DistanceSpheroidCenter, double, 3);
  vtkMRMLWriteXMLFloatMacro(distanceSpheroidRadiusX, DistanceSpheroidRadiusX);
  vtkMRMLWriteXMLFloatMacro(distanceSpheroidRadiusY, DistanceSpheroidRadiusY);
  vtkMRMLWriteXMLFloatMacro(distanceSpheroidRadiusZ, DistanceSpheroidRadiusZ);
  vtkMRMLWriteXMLIntMacro(numberOfDistanceSpheroidInitPoints, NumberOfDistanceSpheroidInitPoints);
  vtkMRMLWriteXMLEndMacro();

  of << " controlGrid=\"" << this->XMLAttributeEncodeString(writeDoubles(this->ControlGrid.data(), this->ControlGrid.size())) << "\"";
  of << " slicingPlaneInitPoint0=\"" << this->XMLAttributeEncodeString(writeDoubles(this->SlicingPlaneInitPoints[0], 3)) << "\"";
  of << " slicingPlaneInitPoint1=\"" << this->XMLAttributeEncodeString(writeDoubles(this->SlicingPlaneInitPoints[1], 3)) << "\"";
  if (!this->DistanceSpheroidInitPoints.empty())
  {
    of << " distanceSpheroidInitPoints=\"" << this->XMLAttributeEncodeString(writeDoubles(this->DistanceSpheroidInitPoints.data(), this->DistanceSpheroidInitPoints.size()))
       << "\"";
  }
}

//------------------------------------------------------------------------------
void vtkMRMLAbstractParametricSurfaceNode::ReadXMLAttributes(const char** atts)
{
  int disabledModify = this->StartModify();

  Superclass::ReadXMLAttributes(atts);

  vtkMRMLReadXMLBeginMacro(atts);
  vtkMRMLReadXMLEnumMacro(initMode, InitMode);
  vtkMRMLReadXMLVectorMacro(slicingPlaneOrigin, SlicingPlaneOrigin, double, 3);
  vtkMRMLReadXMLVectorMacro(slicingPlaneNormal, SlicingPlaneNormal, double, 3);
  vtkMRMLReadXMLVectorMacro(distanceSpheroidCenter, DistanceSpheroidCenter, double, 3);
  vtkMRMLReadXMLFloatMacro(distanceSpheroidRadiusX, DistanceSpheroidRadiusX);
  vtkMRMLReadXMLFloatMacro(distanceSpheroidRadiusY, DistanceSpheroidRadiusY);
  vtkMRMLReadXMLFloatMacro(distanceSpheroidRadiusZ, DistanceSpheroidRadiusZ);
  vtkMRMLReadXMLIntMacro(numberOfDistanceSpheroidInitPoints, NumberOfDistanceSpheroidInitPoints);
  vtkMRMLReadXMLEndMacro();

  // Rows / cols read manually + validated as a pair (the public
  // SetRows / SetCols reject non-square intermediate states; XML
  // load is exempt from the public-API guard).
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

  // Free-form payloads — replay the attribute stream a second time so
  // the order of declarations does not matter.
  for (const char** att = atts; att && *att; att += 2)
  {
    const char* name = att[0];
    const char* value = att[1];
    if (value == nullptr)
    {
      continue;
    }
    if (std::strcmp(name, "controlGrid") == 0)
    {
      std::vector<double> values;
      const std::string decoded = this->XMLAttributeDecodeString(value);
      readDoubles(decoded.c_str(), values);
      const std::size_t expected = this->ControlGrid.size();
      if (values.size() >= expected)
      {
        std::copy_n(values.begin(), expected, this->ControlGrid.begin());
      }
      else
      {
        vtkWarningMacro("Truncated controlGrid attribute; expected " << expected << " doubles (3 * Rows * Cols), got " << values.size() << " — leaving at default");
      }
    }
    else if (std::strcmp(name, "slicingPlaneInitPoint0") == 0 || std::strcmp(name, "slicingPlaneInitPoint1") == 0)
    {
      const int idx = (name[strlen("slicingPlaneInitPoint")] == '0') ? 0 : 1;
      std::vector<double> values;
      const std::string decoded = this->XMLAttributeDecodeString(value);
      readDoubles(decoded.c_str(), values);
      if (values.size() >= 3)
      {
        this->SlicingPlaneInitPoints[idx][0] = values[0];
        this->SlicingPlaneInitPoints[idx][1] = values[1];
        this->SlicingPlaneInitPoints[idx][2] = values[2];
      }
    }
    else if (std::strcmp(name, "distanceSpheroidInitPoints") == 0)
    {
      std::vector<double> values;
      const std::string decoded = this->XMLAttributeDecodeString(value);
      readDoubles(decoded.c_str(), values);
      this->DistanceSpheroidInitPoints = values;
      this->NumberOfDistanceSpheroidInitPoints = static_cast<int>(values.size() / 3);
    }
  }

  if (static_cast<size_t>(this->NumberOfDistanceSpheroidInitPoints) * 3 != this->DistanceSpheroidInitPoints.size())
  {
    this->NumberOfDistanceSpheroidInitPoints = static_cast<int>(this->DistanceSpheroidInitPoints.size() / 3);
  }

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

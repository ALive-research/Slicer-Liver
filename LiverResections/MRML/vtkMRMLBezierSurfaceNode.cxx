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

  This file was originally developed for the Slicer-Liver extension
  as part of the T2 LiverResections all-in migration (Stack 2 of the
  v2.0.0 release tracker — see ADR-0013 §8 and ADR-0014 §1).

==============================================================================*/

// This module MRML includes
#include "vtkMRMLBezierSurfaceNode.h"
#include "vtkMRMLBezierSurfaceDisplayNode.h"

// MRML includes
#include <vtkMRMLNodePropertyMacros.h>
#include <vtkMRMLScene.h>

// VTK includes
#include <vtkNew.h>
#include <vtkObjectFactory.h>
#include <vtkSmartPointer.h>

// STD includes
#include <algorithm>
#include <cstring>
#include <sstream>
#include <string>

//------------------------------------------------------------------------------
vtkMRMLNodeNewMacro(vtkMRMLBezierSurfaceNode);

//------------------------------------------------------------------------------
vtkMRMLBezierSurfaceNode::vtkMRMLBezierSurfaceNode()
  : State(ResectionState::Init)
  , InitMode(InitializationMode::SlicingPlane)
  , NumberOfDistanceSpheroidInitPoints(0)
  , DistanceSpheroidRadiusX(0.0)
  , DistanceSpheroidRadiusY(0.0)
  , DistanceSpheroidRadiusZ(0.0)
{
  this->ControlGrid.fill(0.0);

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
vtkMRMLBezierSurfaceNode::~vtkMRMLBezierSurfaceNode() = default;

//------------------------------------------------------------------------------
const char* vtkMRMLBezierSurfaceNode::GetStateAsString(int state)
{
  switch (state)
  {
    case Init:     return "Init";
    case Planning: return "Planning";
    default:       return "Invalid";
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
const char* vtkMRMLBezierSurfaceNode::GetInitModeAsString(int mode)
{
  switch (mode)
  {
    case SlicingPlane:     return "SlicingPlane";
    case DistanceSpheroid: return "DistanceSpheroid";
    default:               return "Invalid";
  }
}

//------------------------------------------------------------------------------
int vtkMRMLBezierSurfaceNode::GetInitModeFromString(const char* name)
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
bool vtkMRMLBezierSurfaceNode::SetControlGrid(const double* values)
{
  if (values == nullptr)
  {
    return false;
  }
  std::copy_n(values, ControlGridSize, this->ControlGrid.begin());
  this->Modified();
  return true;
}

//------------------------------------------------------------------------------
bool vtkMRMLBezierSurfaceNode::SetSlicingPlaneInitPoint(int index,
                                                             const double point[3])
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
const double* vtkMRMLBezierSurfaceNode::GetSlicingPlaneInitPoint(int index) const
{
  if (index < 0 || index > 1)
  {
    return nullptr;
  }
  return this->SlicingPlaneInitPoints[index];
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::SetNumberOfDistanceSpheroidInitPoints(int n)
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
bool vtkMRMLBezierSurfaceNode::SetDistanceSpheroidInitPoint(int index,
                                                                 const double point[3])
{
  if (index < 0 || index >= this->NumberOfDistanceSpheroidInitPoints
      || point == nullptr)
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
const double*
vtkMRMLBezierSurfaceNode::GetDistanceSpheroidInitPoint(int index) const
{
  if (index < 0 || index >= this->NumberOfDistanceSpheroidInitPoints)
  {
    return nullptr;
  }
  return &this->DistanceSpheroidInitPoints[static_cast<size_t>(index) * 3];
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

  /// Helper: parse N doubles from a space-separated string.  ``out`` is
  /// resized to exactly the number of values successfully parsed.
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
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::WriteXML(ostream& of, int nIndent)
{
  Superclass::WriteXML(of, nIndent);

  vtkMRMLWriteXMLBeginMacro(of);
  vtkMRMLWriteXMLEnumMacro(state, State);
  vtkMRMLWriteXMLEnumMacro(initMode, InitMode);
  vtkMRMLWriteXMLVectorMacro(slicingPlaneOrigin, SlicingPlaneOrigin, double, 3);
  vtkMRMLWriteXMLVectorMacro(slicingPlaneNormal, SlicingPlaneNormal, double, 3);
  vtkMRMLWriteXMLVectorMacro(distanceSpheroidCenter, DistanceSpheroidCenter, double, 3);
  vtkMRMLWriteXMLFloatMacro(distanceSpheroidRadiusX, DistanceSpheroidRadiusX);
  vtkMRMLWriteXMLFloatMacro(distanceSpheroidRadiusY, DistanceSpheroidRadiusY);
  vtkMRMLWriteXMLFloatMacro(distanceSpheroidRadiusZ, DistanceSpheroidRadiusZ);
  vtkMRMLWriteXMLIntMacro(numberOfDistanceSpheroidInitPoints,
                          NumberOfDistanceSpheroidInitPoints);
  vtkMRMLWriteXMLEndMacro();

  // Free-form payloads (variable / large) emitted as plain attributes
  // outside the macro to keep the macro for fixed-size fields.  The
  // node parses them back in ReadXMLAttributes() unconditionally.
  // Route assembled strings through XMLAttributeEncodeString so any
  // future control-character or quote in the payload is XML-safe
  // (current writeDoubles output is whitespace-and-numeric, so this
  // is defensive — but the discipline matches vtkMRMLNode's own
  // attribute serialisation, cf. vtkMRMLNode.cxx:699).
  of << " controlGrid=\""
     << this->XMLAttributeEncodeString(
          writeDoubles(this->ControlGrid.data(), ControlGridSize))
     << "\"";
  of << " slicingPlaneInitPoint0=\""
     << this->XMLAttributeEncodeString(
          writeDoubles(this->SlicingPlaneInitPoints[0], 3))
     << "\"";
  of << " slicingPlaneInitPoint1=\""
     << this->XMLAttributeEncodeString(
          writeDoubles(this->SlicingPlaneInitPoints[1], 3))
     << "\"";
  if (!this->DistanceSpheroidInitPoints.empty())
  {
    of << " distanceSpheroidInitPoints=\""
       << this->XMLAttributeEncodeString(
            writeDoubles(this->DistanceSpheroidInitPoints.data(),
                         this->DistanceSpheroidInitPoints.size()))
       << "\"";
  }
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::ReadXMLAttributes(const char** atts)
{
  int disabledModify = this->StartModify();

  Superclass::ReadXMLAttributes(atts);

  vtkMRMLReadXMLBeginMacro(atts);
  vtkMRMLReadXMLEnumMacro(state, State);
  vtkMRMLReadXMLEnumMacro(initMode, InitMode);
  vtkMRMLReadXMLVectorMacro(slicingPlaneOrigin, SlicingPlaneOrigin, double, 3);
  vtkMRMLReadXMLVectorMacro(slicingPlaneNormal, SlicingPlaneNormal, double, 3);
  vtkMRMLReadXMLVectorMacro(distanceSpheroidCenter, DistanceSpheroidCenter, double, 3);
  vtkMRMLReadXMLFloatMacro(distanceSpheroidRadiusX, DistanceSpheroidRadiusX);
  vtkMRMLReadXMLFloatMacro(distanceSpheroidRadiusY, DistanceSpheroidRadiusY);
  vtkMRMLReadXMLFloatMacro(distanceSpheroidRadiusZ, DistanceSpheroidRadiusZ);
  vtkMRMLReadXMLIntMacro(numberOfDistanceSpheroidInitPoints,
                         NumberOfDistanceSpheroidInitPoints);
  vtkMRMLReadXMLEndMacro();

  // Free-form payloads — replay the attribute stream a second time so
  // the order of declarations does not matter.  ``Set*`` is not used
  // for the array fields because they do not have macro-generated
  // setters that take a const char*.
  for (const char** att = atts; att && *att; att += 2)
  {
    const char* name = att[0];
    const char* value = att[1];
    if (value == nullptr)
    {
      break;
    }
    if (std::strcmp(name, "controlGrid") == 0)
    {
      std::vector<double> values;
      const std::string decoded = this->XMLAttributeDecodeString(value);
      readDoubles(decoded.c_str(), values);
      if (values.size() >= static_cast<std::size_t>(ControlGridSize))
      {
        std::copy_n(values.begin(), ControlGridSize, this->ControlGrid.begin());
      }
      else
      {
        // Truncated payload — keep the existing default-init (zero-
        // filled or whatever the caller stashed before ReadXML) and
        // warn loudly so the inconsistency is visible to whoever
        // produced the malformed scene.  Same shape as the warning
        // vtkMRMLPlotSeriesNode emits when a truncated array is
        // encountered on read.
        vtkWarningMacro("Truncated controlGrid attribute; expected "
                        << ControlGridSize << " doubles, got "
                        << values.size() << " — leaving at default");
      }
    }
    else if (std::strcmp(name, "slicingPlaneInitPoint0") == 0
             || std::strcmp(name, "slicingPlaneInitPoint1") == 0)
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

  // The numberOfDistanceSpheroidInitPoints attribute may have arrived
  // *after* distanceSpheroidInitPoints; if they disagree (e.g. legacy
  // XML wrote a count but no points yet), keep the count in sync with
  // the actual storage so callers do not over-read.
  if (static_cast<size_t>(this->NumberOfDistanceSpheroidInitPoints) * 3
      != this->DistanceSpheroidInitPoints.size())
  {
    this->NumberOfDistanceSpheroidInitPoints =
      static_cast<int>(this->DistanceSpheroidInitPoints.size() / 3);
  }

  this->EndModify(disabledModify);
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::CopyContent(vtkMRMLNode* anode,
                                                bool deepCopy /*=true*/)
{
  MRMLNodeModifyBlocker blocker(this);
  Superclass::CopyContent(anode, deepCopy);

  vtkMRMLBezierSurfaceNode* other =
    vtkMRMLBezierSurfaceNode::SafeDownCast(anode);
  if (other == nullptr)
  {
    vtkErrorMacro("CopyContent: source node is not a vtkMRMLBezierSurfaceNode");
    return;
  }

  this->State = other->State;
  this->InitMode = other->InitMode;
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
  this->NumberOfDistanceSpheroidInitPoints =
    other->NumberOfDistanceSpheroidInitPoints;
  this->DistanceSpheroidInitPoints = other->DistanceSpheroidInitPoints;
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::CreateDefaultDisplayNodes()
{
  if (vtkMRMLBezierSurfaceDisplayNode::SafeDownCast(this->GetDisplayNode())
      != nullptr)
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
  auto displayNode = vtkSmartPointer<vtkMRMLBezierSurfaceDisplayNode>::New();
  this->GetScene()->AddNode(displayNode);
  this->SetAndObserveDisplayNodeID(displayNode->GetID());
}

//------------------------------------------------------------------------------
void vtkMRMLBezierSurfaceNode::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);

  vtkMRMLPrintBeginMacro(os, indent);
  vtkMRMLPrintEnumMacro(State);
  vtkMRMLPrintEnumMacro(InitMode);
  vtkMRMLPrintVectorMacro(SlicingPlaneOrigin, double, 3);
  vtkMRMLPrintVectorMacro(SlicingPlaneNormal, double, 3);
  vtkMRMLPrintVectorMacro(DistanceSpheroidCenter, double, 3);
  vtkMRMLPrintFloatMacro(DistanceSpheroidRadiusX);
  vtkMRMLPrintFloatMacro(DistanceSpheroidRadiusY);
  vtkMRMLPrintFloatMacro(DistanceSpheroidRadiusZ);
  vtkMRMLPrintIntMacro(NumberOfDistanceSpheroidInitPoints);
  vtkMRMLPrintEndMacro();

  os << indent << "ControlGrid (" << ControlGridSize << " doubles): ";
  for (int i = 0; i < ControlGridSize; ++i)
  {
    if (i > 0)
    {
      os << " ";
    }
    os << this->ControlGrid[i];
  }
  os << "\n";
}

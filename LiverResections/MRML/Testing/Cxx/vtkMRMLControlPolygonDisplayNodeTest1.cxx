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

  This file was originally developed for the Slicer-Liver extension as
  part of the control-polygon display aspect (see ADR-0033).

==============================================================================*/

// LiverResections MRML includes
#include "vtkMRMLControlPolygonDisplayNode.h"

// MRML includes (ctkTest assertion macros)
#include "vtkMRMLCoreTestingMacros.h"
#include <vtkMRMLScene.h>

// VTK includes
#include <vtkNew.h>

// STD includes
#include <cctype>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

// ADR-0033 §Conformance -- the control-polygon display node's accessor
// surface: v1-parity defaults (HandleRadius 2.5), setter round-trips, the
// XML write/read round-trip and CopyContent, mirroring the sibling
// vtkMRMLResectogramDisplayNodeTest1 shape.

namespace
{

int testDefaults()
{
  vtkNew<vtkMRMLControlPolygonDisplayNode> node;

  // HandleRadius sized for a liver-scale scene (v1's 2.5 read too small).
  CHECK_DOUBLE(node->GetHandleRadius(), 6.0);
  double handleColor[3] = { 0.0, 0.0, 0.0 };
  node->GetHandleColor(handleColor);
  CHECK_DOUBLE(handleColor[0], 1.0);
  CHECK_DOUBLE(handleColor[1], 1.0);
  CHECK_DOUBLE(handleColor[2], 1.0);
  double edgeColor[3] = { 0.0, 0.0, 0.0 };
  node->GetEdgeColor(edgeColor);
  CHECK_DOUBLE(edgeColor[0], 1.0);
  CHECK_DOUBLE(edgeColor[1], 0.0);
  CHECK_DOUBLE(edgeColor[2], 0.0);
  CHECK_DOUBLE(node->GetEdgeWidth(), 1.5);

  // Transient cross-view interaction state: nothing hovered/grabbed.
  CHECK_INT(node->GetHoveredControlPoint(), -1);
  CHECK_INT(node->GetGrabbedControlPoint(), -1);

  CHECK_STRING(node->GetNodeTagName(), "ControlPolygonDisplay");
  return EXIT_SUCCESS;
}

int testSettersAndGetters()
{
  vtkNew<vtkMRMLControlPolygonDisplayNode> node;

  node->SetHandleRadius(4.0);
  CHECK_DOUBLE(node->GetHandleRadius(), 4.0);
  node->SetHandleColor(0.1, 0.2, 0.3);
  double handleColor[3] = { 0.0, 0.0, 0.0 };
  node->GetHandleColor(handleColor);
  CHECK_DOUBLE(handleColor[0], 0.1);
  CHECK_DOUBLE(handleColor[1], 0.2);
  CHECK_DOUBLE(handleColor[2], 0.3);
  node->SetEdgeColor(0.4, 0.5, 0.6);
  double edgeColor[3] = { 0.0, 0.0, 0.0 };
  node->GetEdgeColor(edgeColor);
  CHECK_DOUBLE(edgeColor[0], 0.4);
  CHECK_DOUBLE(edgeColor[1], 0.5);
  CHECK_DOUBLE(edgeColor[2], 0.6);
  node->SetEdgeWidth(2.5);
  CHECK_DOUBLE(node->GetEdgeWidth(), 2.5);
  node->SetHoveredControlPoint(5);
  CHECK_INT(node->GetHoveredControlPoint(), 5);
  node->SetGrabbedControlPoint(7);
  CHECK_INT(node->GetGrabbedControlPoint(), 7);
  return EXIT_SUCCESS;
}

int testXMLRoundTrip()
{
  vtkNew<vtkMRMLControlPolygonDisplayNode> source;
  vtkNew<vtkMRMLScene> scene;
  source->SetScene(scene.GetPointer());

  source->SetHandleRadius(4.0);
  source->SetHandleColor(0.1, 0.2, 0.3);
  source->SetEdgeColor(0.4, 0.5, 0.6);
  source->SetEdgeWidth(2.5);

  std::ostringstream out;
  source->WriteXML(out, 0);
  const std::string xml = out.str();

  // Parse name="value" attribute pairs out of the WriteXML output.
  std::vector<std::string> storage;
  std::size_t pos = 0;
  while (pos < xml.size())
  {
    while (pos < xml.size() && std::isspace(static_cast<unsigned char>(xml[pos])))
    {
      ++pos;
    }
    if (pos >= xml.size())
    {
      break;
    }
    const std::size_t eq = xml.find('=', pos);
    if (eq == std::string::npos)
    {
      break;
    }
    std::string name = xml.substr(pos, eq - pos);
    if (eq + 1 >= xml.size() || xml[eq + 1] != '"')
    {
      break;
    }
    const std::size_t valStart = eq + 2;
    const std::size_t valEnd = xml.find('"', valStart);
    if (valEnd == std::string::npos)
    {
      break;
    }
    storage.push_back(name);
    storage.push_back(xml.substr(valStart, valEnd - valStart));
    pos = valEnd + 1;
  }

  std::vector<const char*> atts;
  atts.reserve(storage.size() + 1);
  for (const auto& s : storage)
  {
    atts.push_back(s.c_str());
  }
  atts.push_back(nullptr);

  vtkNew<vtkMRMLControlPolygonDisplayNode> sink;
  sink->SetScene(scene.GetPointer());
  sink->ReadXMLAttributes(atts.data());

  CHECK_DOUBLE_TOLERANCE(sink->GetHandleRadius(), source->GetHandleRadius(), 1e-5);
  double sourceHandle[3] = { 0.0, 0.0, 0.0 };
  double sinkHandle[3] = { 0.0, 0.0, 0.0 };
  source->GetHandleColor(sourceHandle);
  sink->GetHandleColor(sinkHandle);
  for (int i = 0; i < 3; ++i)
  {
    CHECK_DOUBLE_TOLERANCE(sinkHandle[i], sourceHandle[i], 1e-5);
  }
  double sourceEdge[3] = { 0.0, 0.0, 0.0 };
  double sinkEdge[3] = { 0.0, 0.0, 0.0 };
  source->GetEdgeColor(sourceEdge);
  sink->GetEdgeColor(sinkEdge);
  for (int i = 0; i < 3; ++i)
  {
    CHECK_DOUBLE_TOLERANCE(sinkEdge[i], sourceEdge[i], 1e-5);
  }
  CHECK_DOUBLE_TOLERANCE(sink->GetEdgeWidth(), source->GetEdgeWidth(), 1e-5);
  return EXIT_SUCCESS;
}

int testCopyContent()
{
  vtkNew<vtkMRMLControlPolygonDisplayNode> source;
  source->SetHandleRadius(4.0);
  source->SetEdgeWidth(2.5);

  vtkNew<vtkMRMLControlPolygonDisplayNode> sink;
  sink->CopyContent(source.GetPointer(), /*deepCopy=*/true);

  CHECK_DOUBLE(sink->GetHandleRadius(), 4.0);
  CHECK_DOUBLE(sink->GetEdgeWidth(), 2.5);

  // Mutating source must not affect sink (deep-copy semantics).
  source->SetHandleRadius(1.0);
  CHECK_DOUBLE(sink->GetHandleRadius(), 4.0);
  return EXIT_SUCCESS;
}

} // namespace

int vtkMRMLControlPolygonDisplayNodeTest1(int, char*[])
{
  CHECK_EXIT_SUCCESS(testDefaults());
  CHECK_EXIT_SUCCESS(testSettersAndGetters());
  CHECK_EXIT_SUCCESS(testXMLRoundTrip());
  CHECK_EXIT_SUCCESS(testCopyContent());
  return EXIT_SUCCESS;
}

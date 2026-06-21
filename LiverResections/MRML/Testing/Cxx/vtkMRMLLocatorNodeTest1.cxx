/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

==============================================================================*/

/**
 * \file vtkMRMLLocatorNodeTest1.cxx
 *
 * Test-first scaffolding for the v2.0 locator carrier introduced by
 * ADR-0025 §"The node".  Lands per ADR-0027 (invariant-test-first).
 *
 * Each test pins one architectural invariant.  Assertions fail red
 * against the current tree (the class does not exist yet); the
 * follow-up implementer commit flips them green.
 *
 * Invariants pinned:
 *
 *   1. vtkMRMLLocatorNode instantiates via vtkStandardNewMacro and
 *      reports the expected node tag name "Locator".
 *      (ADR-0025 §"The node" -- a single new concrete carrier.)
 *   2. Persistence = presence, NOT live position (ADR-0025
 *      §"The node", mirroring vtkMRMLCrosshairNode).  WriteXML +
 *      ReadXMLAttributes round-trip ``LocatorActive`` (presence)
 *      while the transient ``PickedPositionWorld`` does NOT survive
 *      the XML path -- the fresh node reads back the default position,
 *      not the written one.
 *   3. Copy/CopyContent carries the presence flag.  The XML path is
 *      pinned firmly as the ADR's literal wording; for CopyContent
 *      the deep-copy semantics follow the crosshair precedent, which
 *      DOES copy its live RAS.  Either way the presence flag must
 *      survive CopyContent.
 *   4. CreateDefaultDisplayNodes() creates exactly one
 *      vtkMRMLLocatorDisplayNode and wires it as the display node.
 *      (ADR-0025 §"The node" -- one display node for v2.0.)
 *
 * Out of scope for this Test1:
 *   - The producer -> node -> consumer shader-uniform chain
 *     (ADR-0025 §Conformance, pinned by a separate Algorithm/Logic
 *     test).
 *   - Click-to-reslice SliceToRAS update (separate test).
 */

// This module MRML includes -- forward-included so the test driver
// fails red until the implementer lands the new classes.  Per the
// existing test-first convention; intentional, per ADR-0027.
#include "vtkMRMLLocatorNode.h"
#include "vtkMRMLLocatorDisplayNode.h"

// MRML includes
#include "vtkMRMLCoreTestingMacros.h"
#include "vtkMRMLScene.h"

// VTK includes
#include <vtkNew.h>
#include <vtkSmartPointer.h>

// STD includes
#include <cctype>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

namespace
{

//------------------------------------------------------------------------------
// Naive ``name="value"`` walker mirroring the pattern in
// vtkMRMLResectionPlanNodeTest1.cxx.  Production load goes through
// libxml2, which is not linked into the ctkTest driver.
std::vector<const char*> buildAttsFromXML(const std::string& xml, std::vector<std::string>& storage)
{
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
    storage.push_back(std::move(name));
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
  return atts;
}

//------------------------------------------------------------------------------
// Invariant 1 -- vtkMRMLLocatorNode instantiates cleanly and reports
// its node tag name.
// (ADR-0025 §"The node".)
int testInstantiable()
{
  vtkNew<vtkMRMLLocatorNode> node;
  CHECK_NOT_NULL(node.GetPointer());
  CHECK_STRING(node->GetNodeTagName(), "Locator");
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 2 -- Persistence = presence, NOT live position.  The
// presence flag (LocatorActive) round-trips through WriteXML +
// ReadXMLAttributes; the transient picked world position does NOT.
// This is the literal ADR-0025 contract: "Copy, WriteXML, and
// ReadXMLAttributes round-trip the presence of a locator (and its
// display config), not the live picked position."
// (ADR-0025 §"The node"; vtkMRMLCrosshairNode precedent.)
int testPresencePersistsPositionDoesNot()
{
  vtkNew<vtkMRMLScene> scene;
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLLocatorNode>::New());

  vtkNew<vtkMRMLLocatorNode> source;
  source->SetScene(scene.GetPointer());
  source->SetLocatorActive(true);
  const double picked[3] = { 12.5, -7.25, 33.0 };
  source->SetPickedPositionWorld(picked);

  std::ostringstream out;
  source->WriteXML(out, 0);
  const std::string xml = out.str();

  // The presence attribute must be serialised; the live position
  // must NOT appear in the written XML at all.
  if (xml.find("locatorActive") == std::string::npos && xml.find("LocatorActive") == std::string::npos)
  {
    std::cerr << "WriteXML output missing locatorActive attribute:\n" << xml << "\n";
    return EXIT_FAILURE;
  }
  if (xml.find("pickedPositionWorld") != std::string::npos || xml.find("PickedPositionWorld") != std::string::npos)
  {
    std::cerr << "WriteXML output unexpectedly persisted the live picked position:\n" << xml << "\n";
    return EXIT_FAILURE;
  }

  vtkNew<vtkMRMLLocatorNode> sink;
  sink->SetScene(scene.GetPointer());

  // Capture the fresh node's default position before reading -- the
  // XML read must leave it untouched.
  double defaultPos[3] = { 0.0, 0.0, 0.0 };
  sink->GetPickedPositionWorld(defaultPos);

  std::vector<std::string> storage;
  std::vector<const char*> atts = buildAttsFromXML(xml, storage);
  sink->ReadXMLAttributes(atts.data());

  // Presence round-trips true.
  CHECK_BOOL(sink->GetLocatorActive(), true);

  // Live position did NOT persist: the sink still holds its default,
  // not the source's picked value.
  double readPos[3] = { 0.0, 0.0, 0.0 };
  sink->GetPickedPositionWorld(readPos);
  CHECK_DOUBLE_TOLERANCE(readPos[0], defaultPos[0], 1e-9);
  CHECK_DOUBLE_TOLERANCE(readPos[1], defaultPos[1], 1e-9);
  CHECK_DOUBLE_TOLERANCE(readPos[2], defaultPos[2], 1e-9);
  // And specifically it is NOT the source's picked value.
  if (std::abs(readPos[0] - picked[0]) < 1e-9 && std::abs(readPos[1] - picked[1]) < 1e-9 && std::abs(readPos[2] - picked[2]) < 1e-9)
  {
    std::cerr << "Live picked position leaked through the XML path -- ADR-0025 "
                 "requires presence-only persistence.\n";
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 3 -- CopyContent carries presence.  The XML path
// (invariant 2) is the firmly-pinned ADR contract; CopyContent
// follows the crosshair precedent, which DOES deep-copy its live
// RAS.  We pin only what the ADR fixes: the presence flag survives
// CopyContent.
// (ADR-0025 §"The node"; vtkMRMLCrosshairNode::CopyContent precedent.)
int testCopyContentCarriesPresence()
{
  vtkNew<vtkMRMLLocatorNode> source;
  source->SetLocatorActive(true);
  const double picked[3] = { 1.0, 2.0, 3.0 };
  source->SetPickedPositionWorld(picked);

  vtkNew<vtkMRMLLocatorNode> sink;
  sink->CopyContent(source.GetPointer());

  CHECK_BOOL(sink->GetLocatorActive(), true);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 4 -- CreateDefaultDisplayNodes creates exactly one
// vtkMRMLLocatorDisplayNode and wires it as the node's display node.
// (ADR-0025 §"The node" -- one display node for v2.0.)
int testCreateDefaultDisplayNodes()
{
  vtkNew<vtkMRMLScene> scene;
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLLocatorNode>::New());
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLLocatorDisplayNode>::New());

  vtkNew<vtkMRMLLocatorNode> node;
  scene->AddNode(node.GetPointer());

  node->CreateDefaultDisplayNodes();

  vtkMRMLLocatorDisplayNode* displayNode = vtkMRMLLocatorDisplayNode::SafeDownCast(node->GetDisplayNode());
  CHECK_NOT_NULL(displayNode);

  // Idempotent: a second call does not create a second display node.
  node->CreateDefaultDisplayNodes();
  CHECK_INT(node->GetNumberOfDisplayNodes(), 1);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Display-node sibling invariant -- vtkMRMLLocatorDisplayNode
// round-trips its persisted fields (radius, colour) through the XML
// path and reports its tag name.  Mirrors the
// vtkMRMLResectogramDisplayNode structure.
// (ADR-0025 §"The node" -- radius, colour, visibility.)
int testDisplayNodeRoundTrip()
{
  vtkNew<vtkMRMLScene> scene;
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLLocatorDisplayNode>::New());

  vtkNew<vtkMRMLLocatorDisplayNode> source;
  source->SetScene(scene.GetPointer());
  source->SetRadius(4.5);
  source->SetColor(0.25, 0.5, 0.75);

  std::ostringstream out;
  source->WriteXML(out, 0);
  const std::string xml = out.str();

  vtkNew<vtkMRMLLocatorDisplayNode> sink;
  sink->SetScene(scene.GetPointer());
  std::vector<std::string> storage;
  std::vector<const char*> atts = buildAttsFromXML(xml, storage);
  sink->ReadXMLAttributes(atts.data());

  CHECK_DOUBLE_TOLERANCE(sink->GetRadius(), 4.5, 1e-9);
  double color[3] = { 0.0, 0.0, 0.0 };
  sink->GetColor(color);
  CHECK_DOUBLE_TOLERANCE(color[0], 0.25, 1e-9);
  CHECK_DOUBLE_TOLERANCE(color[1], 0.5, 1e-9);
  CHECK_DOUBLE_TOLERANCE(color[2], 0.75, 1e-9);
  return EXIT_SUCCESS;
}

} // namespace

//------------------------------------------------------------------------------
int vtkMRMLLocatorNodeTest1(int, char*[])
{
  vtkNew<vtkMRMLScene> scene;
  vtkNew<vtkMRMLLocatorNode> exerciseNode;
  exerciseNode->SetScene(scene.GetPointer());
  EXERCISE_ALL_BASIC_MRML_METHODS(exerciseNode.GetPointer());

  CHECK_EXIT_SUCCESS(testInstantiable());
  CHECK_EXIT_SUCCESS(testPresencePersistsPositionDoesNot());
  CHECK_EXIT_SUCCESS(testCopyContentCarriesPresence());
  CHECK_EXIT_SUCCESS(testCreateDefaultDisplayNodes());
  CHECK_EXIT_SUCCESS(testDisplayNodeRoundTrip());

  std::cout << "vtkMRMLLocatorNodeTest1 completed successfully" << std::endl;
  return EXIT_SUCCESS;
}

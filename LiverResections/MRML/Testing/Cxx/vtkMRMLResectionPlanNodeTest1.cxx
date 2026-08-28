/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

==============================================================================*/

/**
 * \file vtkMRMLResectionPlanNodeTest1.cxx
 *
 * Test-first scaffolding for the new clinical-layer node introduced
 * by the 2026-05-25 wrapper-vs-carrier amendment to ADR-0014
 * (§"Fourth layer: clinical/method wrapper") and ADR-0023 (§"Class
 * abstraction for surfaces").  Lands per ADR-0027.
 *
 * Each test pins one architectural invariant.  Assertions fail red
 * against the current tree (the class does not exist yet); the
 * follow-up implementer commit flips them green.
 *
 * Invariants pinned:
 *
 *   1. Plan instantiates via vtkStandardNewMacro and reports the
 *      expected node tag name.
 *      (ADR-0014 amendment 2026-05-25 §"Fourth layer" -- the new
 *      class is concrete and instantiable, unlike the carrier
 *      hierarchy base.)
 *   2. Defaults match the design's documented sentinels:
 *      ``SafetyMargin = 0.0``, ``RiskMargin = 0.0``,
 *      ``OrderIndex = -1`` (sentinel), ``State = Init``,
 *      ``Name = ""``.
 *      (Design doc 01-class-hierarchy.md ``vtkMRMLResectionPlanNode``
 *      class block; design doc 05-lrp-json-schema.md §"orderIndex:
 *      int (sentinel -1)".)
 *   3. Plan-state enum string round-trip across all three legal
 *      states (Init / Planning / Confirmed) -- mirrors ADR-0019 /
 *      vtkMRMLBezierSurfaceNode's enum.  This is the *plan's* state,
 *      not the surface's -- the v2.0 design moves the state
 *      machine UP to the plan per the wrapper-vs-carrier amendment.
 *      (ADR-0014 amendment 2026-05-25 §"Decision" --
 *      ``PlanState : Init | Planning | Confirmed`` on the plan;
 *      ADR-0019 transitions referenced by inheritance.)
 *   4. XML round-trip of every plan field through WriteXML +
 *      ReadXMLAttributes (Markups precedent -- light scalars in
 *      .mrml; storage carries the heavy fields).  Includes ``Name``,
 *      ``SafetyMargin``, ``RiskMargin``, ``OrderIndex``,
 *      ``State``.
 *      (Design doc 03-storage-ownership.md §"Plan node
 *      (vtkMRMLResectionPlanNode)" table -- the WriteXML column for
 *      light scalars.)
 *   5. ``CreateDefaultStorageNode()`` returns a fresh
 *      ``vtkMRMLResectionPlanStorageNode`` instance.  Storable
 *      invariant -- plan is the rooted persistence target.
 *      (ADR-0023 amendment §"Persistence -- .lrp.json schema v2"
 *      -- "plan-rooted, surface-block-polymorphic"; design doc
 *      03-storage-ownership.md storability matrix row 1.)
 *   6. Typed ``geometry`` node-reference role to the abstract
 *      parametric-surface base.  Set via the concrete Bezier
 *      subclass; retrieved through the abstract base
 *      (SafeDownCast); survives scene add/remove without leaking
 *      observers.
 *      (ADR-0023 amendment §"Class abstraction for surfaces" --
 *      ``Plan -- geometry --> Surface`` arrow in the class diagram;
 *      design doc 02-node-references.md §"What references what"
 *      first row.)
 *   7. Copy / CopyContent symmetry: a CopyContent from a populated
 *      source onto a fresh sink reproduces every plan field
 *      (excluding scene-managed identity like NodeID).  Pin pairs
 *      with the XML round-trip to detect divergence between the two
 *      serialisation paths.
 *      (Design doc 01-class-hierarchy.md class diagram -- every
 *      field on the plan must survive both XML and CopyContent.)
 *
 * Out of scope for this Test1 (per planner output -- deliverable 3):
 *   - Plan-to-storage WriteData / ReadData round-trips (covered in
 *     vtkMRMLResectionPlanStorageNodeTest1).
 *   - Plan-Surface state-machine *coupling* (the surface's own
 *     state machine, ADR-0019, is owned by the surface; the plan's
 *     state runs in parallel and the coupling rule lives elsewhere
 *     in the design package, not pinned here).
 *   - Plan-Territories non-reference (an absence-of-feature pin is
 *     captured in 02-node-references.md and is not a test invariant
 *     -- nothing to assert).
 */

// This module MRML includes -- forward-included so the test driver
// fails red until the implementer lands the new class.  Per the
// existing test-first convention; the test driver will fail to
// *compile* or *link* against the current tree -- intentional, per
// ADR-0027.
#include "vtkMRMLResectionPlanNode.h"
#include "vtkMRMLResectionPlanStorageNode.h"
#include "vtkMRMLAbstractParametricSurfaceNode.h"
#include "vtkMRMLBezierSurfaceNode.h"

// MRML includes
#include "vtkMRMLCoreTestingMacros.h"
#include "vtkMRMLScene.h"

// VTK includes
#include <vtkNew.h>
#include <vtkSmartPointer.h>

// STD includes
#include <cctype>
#include <cstring>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

namespace
{

//------------------------------------------------------------------------------
// Naive ``name="value"`` walker mirroring the pattern in
// vtkMRMLBezierSurfaceNodeTest1.cxx +
// vtkMRMLAbstractTerritoriesNodeTest1.cxx.  Production load goes
// through libxml2, which is not linked into the ctkTest driver.
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
// Invariant 1 -- vtkMRMLResectionPlanNode instantiates cleanly via
// vtkStandardNewMacro (not vtkAbstractTypeMacro -- the wrapper IS
// instantiable; the carrier-base is the abstract one).
// (ADR-0014 amendment 2026-05-25 §"Fourth layer".)
int testInstantiable()
{
  vtkNew<vtkMRMLResectionPlanNode> node;
  CHECK_NOT_NULL(node.GetPointer());
  CHECK_STRING(node->GetNodeTagName(), "ResectionPlan");
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 2 -- Default field values match the design's documented
// sentinels.  ``OrderIndex = -1`` is the canonical sentinel used by
// the resection table to detect "no manual ordering set".
// (Design doc 01-class-hierarchy.md ``vtkMRMLResectionPlanNode``
// class block; design doc 05-lrp-json-schema.md §"orderIndex
// (sentinel -1)".)
int testDefaults()
{
  vtkNew<vtkMRMLResectionPlanNode> node;
  CHECK_DOUBLE(node->GetSafetyMargin(), 0.0);
  CHECK_DOUBLE(node->GetRiskMargin(), 0.0);
  CHECK_INT(node->GetOrderIndex(), -1);
  CHECK_INT(node->GetState(), vtkMRMLResectionPlanNode::Init);
  // ``Name`` is a Slicer-core MRML primitive (GetName / SetName on
  // vtkMRMLNode); default is nullptr unless the constructor sets it
  // explicitly.  The design carries ``Name`` as the surgeon-facing
  // string; the plan's constructor is expected to leave it unset
  // (consumers either set it explicitly or read the storage file).
  CHECK_NULL(node->GetName());
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 3 -- Plan state enum + string converters.  The plan's
// state machine peers the surface's ADR-0019 state machine (Init /
// Planning / Confirmed).  Pin: the enum integer values, the string
// converters in both directions, and the default rejection (-1 on
// bogus input -- the Slicer-core convention for from-string sentinel
// failure, mirrors vtkMRMLBezierSurfaceNode::GetStateFromString).
// (ADR-0014 amendment 2026-05-25 §"Decision" --
// ``PlanState : Init | Planning | Confirmed``.)
int testPlanStateEnumRoundTrip()
{
  vtkNew<vtkMRMLResectionPlanNode> node;
  CHECK_INT(node->GetState(), vtkMRMLResectionPlanNode::Init);

  node->SetState(vtkMRMLResectionPlanNode::Planning);
  CHECK_INT(node->GetState(), vtkMRMLResectionPlanNode::Planning);

  node->SetState(vtkMRMLResectionPlanNode::Confirmed);
  CHECK_INT(node->GetState(), vtkMRMLResectionPlanNode::Confirmed);

  CHECK_STRING(vtkMRMLResectionPlanNode::GetStateAsString(vtkMRMLResectionPlanNode::Init), "Init");
  CHECK_STRING(vtkMRMLResectionPlanNode::GetStateAsString(vtkMRMLResectionPlanNode::Planning), "Planning");
  CHECK_STRING(vtkMRMLResectionPlanNode::GetStateAsString(vtkMRMLResectionPlanNode::Confirmed), "Confirmed");

  CHECK_INT(vtkMRMLResectionPlanNode::GetStateFromString("Init"), vtkMRMLResectionPlanNode::Init);
  CHECK_INT(vtkMRMLResectionPlanNode::GetStateFromString("Planning"), vtkMRMLResectionPlanNode::Planning);
  CHECK_INT(vtkMRMLResectionPlanNode::GetStateFromString("Confirmed"), vtkMRMLResectionPlanNode::Confirmed);
  CHECK_INT(vtkMRMLResectionPlanNode::GetStateFromString("bogus"), -1);
  CHECK_INT(vtkMRMLResectionPlanNode::GetStateFromString(nullptr), -1);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 4 -- XML round-trip of plan fields.  Source mutated;
// XML written; sink populated from atts -- every field must come
// back.  This is the .mrml-side of the persistence split: plan
// light scalars live here, surface bulk data lives in .lrp.json.
// (Design doc 03-storage-ownership.md §"Plan node
// (vtkMRMLResectionPlanNode)" table.)
int testXMLRoundTrip()
{
  vtkNew<vtkMRMLScene> scene;
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanNode>::New());

  vtkNew<vtkMRMLResectionPlanNode> source;
  source->SetScene(scene.GetPointer());
  source->SetName("Right hemihepatectomy");
  source->SetSafetyMargin(10.0);
  source->SetRiskMargin(5.0);
  source->SetOrderIndex(2);
  source->SetState(vtkMRMLResectionPlanNode::Planning);

  std::ostringstream out;
  source->WriteXML(out, 0);
  const std::string xml = out.str();

  // Spot-check: the serialised text mentions one of the plan-
  // specific attributes (lower-camelCase per vtkMRMLWriteXMLDoubleMacro)
  // and no longer emits the retired unit-suffixed name.
  if (xml.find("safetyMargin") == std::string::npos)
  {
    std::cerr << "WriteXML output missing safetyMargin attribute:\n" << xml << "\n";
    return EXIT_FAILURE;
  }
  if (xml.find("safetyMargin_mm") != std::string::npos)
  {
    std::cerr << "WriteXML must not emit the legacy safetyMargin_mm attribute:\n" << xml << "\n";
    return EXIT_FAILURE;
  }

  vtkNew<vtkMRMLResectionPlanNode> sink;
  sink->SetScene(scene.GetPointer());
  std::vector<std::string> storage;
  std::vector<const char*> atts = buildAttsFromXML(xml, storage);
  sink->ReadXMLAttributes(atts.data());

  CHECK_DOUBLE_TOLERANCE(sink->GetSafetyMargin(), source->GetSafetyMargin(), 1e-9);
  CHECK_DOUBLE_TOLERANCE(sink->GetRiskMargin(), source->GetRiskMargin(), 1e-9);
  CHECK_INT(sink->GetOrderIndex(), source->GetOrderIndex());
  CHECK_INT(sink->GetState(), source->GetState());

  // Legacy-scene compatibility: attributes written before the margin
  // rename (unit-suffixed names) still populate the fields on read.
  vtkNew<vtkMRMLResectionPlanNode> legacySink;
  legacySink->SetScene(scene.GetPointer());
  const char* legacyAtts[] = { "safetyMargin_mm", "12.5", "riskMargin_mm", "4.5", nullptr };
  legacySink->ReadXMLAttributes(legacyAtts);
  CHECK_DOUBLE_TOLERANCE(legacySink->GetSafetyMargin(), 12.5, 1e-9);
  CHECK_DOUBLE_TOLERANCE(legacySink->GetRiskMargin(), 4.5, 1e-9);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 5 -- CreateDefaultStorageNode returns a fresh
// vtkMRMLResectionPlanStorageNode (the storable side of the
// wrapper-vs-carrier pattern -- the plan IS storable; the surface
// it wraps is not).
// (ADR-0023 amendment §"Persistence -- .lrp.json schema v2";
// design doc 03-storage-ownership.md storability matrix.)
int testCreateDefaultStorageNode()
{
  vtkNew<vtkMRMLResectionPlanNode> node;
  vtkSmartPointer<vtkMRMLStorageNode> storage = vtkSmartPointer<vtkMRMLStorageNode>::Take(node->CreateDefaultStorageNode());
  CHECK_NOT_NULL(storage.GetPointer());
  vtkMRMLResectionPlanStorageNode* planStorage = vtkMRMLResectionPlanStorageNode::SafeDownCast(storage.GetPointer());
  CHECK_NOT_NULL(planStorage);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 6 -- Typed ``geometry`` node-reference role to the
// abstract parametric-surface base.  Set on a concrete Bezier
// subclass; retrieved through the abstract base.  The accessor is
// polymorphic (returns the abstract-base pointer), and the wired
// reference survives scene add/remove without observer leaks.
// (ADR-0023 amendment §"Class abstraction for surfaces" --
// ``Plan -- geometry --> Surface`` in the class diagram; design doc
// 02-node-references.md table row 1.)
int testGeometryNodeReference()
{
  vtkNew<vtkMRMLScene> scene;
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLResectionPlanNode>::New());
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLBezierSurfaceNode>::New());

  vtkNew<vtkMRMLResectionPlanNode> plan;
  vtkNew<vtkMRMLBezierSurfaceNode> bezier;
  scene->AddNode(plan.GetPointer());
  scene->AddNode(bezier.GetPointer());

  // Wire via the typed setter.  The setter accepts the abstract
  // base type so future NURBS instances work via the same call
  // site.
  plan->SetAndObserveGeometryNode(bezier.GetPointer());

  // Retrieved via the typed accessor -- returns the abstract-base
  // pointer.  Consumers SafeDownCast to the concrete subclass when
  // they need type-specific access.
  vtkMRMLAbstractParametricSurfaceNode* surfaceViaPlan = plan->GetGeometryNode();
  CHECK_NOT_NULL(surfaceViaPlan);
  // Polymorphic round-trip: the abstract-base pointer cast back to
  // Bezier returns the same instance.
  vtkMRMLBezierSurfaceNode* bezierFromBase = vtkMRMLBezierSurfaceNode::SafeDownCast(surfaceViaPlan);
  CHECK_NOT_NULL(bezierFromBase);
  CHECK_POINTER(bezierFromBase, bezier.GetPointer());

  // Scene remove -- the reference resolves to nullptr cleanly.
  scene->RemoveNode(bezier.GetPointer());
  vtkMRMLAbstractParametricSurfaceNode* surfaceAfterRemove = plan->GetGeometryNode();
  CHECK_NULL(surfaceAfterRemove);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 7 -- CopyContent symmetry across the field roster.  Pin
// pairs with the XML round-trip (invariant 4) to detect drift
// between Copy and XML codepaths -- a common regression in MRML
// nodes when one is updated without the other.
// (Design doc 01-class-hierarchy.md class diagram covering all
// plan-side fields.)
int testCopyContent()
{
  vtkNew<vtkMRMLResectionPlanNode> source;
  source->SetName("Source plan");
  source->SetSafetyMargin(7.5);
  source->SetRiskMargin(3.25);
  source->SetOrderIndex(4);
  source->SetState(vtkMRMLResectionPlanNode::Confirmed);

  vtkNew<vtkMRMLResectionPlanNode> sink;
  sink->CopyContent(source.GetPointer());

  CHECK_DOUBLE_TOLERANCE(sink->GetSafetyMargin(), 7.5, 1e-9);
  CHECK_DOUBLE_TOLERANCE(sink->GetRiskMargin(), 3.25, 1e-9);
  CHECK_INT(sink->GetOrderIndex(), 4);
  CHECK_INT(sink->GetState(), vtkMRMLResectionPlanNode::Confirmed);
  return EXIT_SUCCESS;
}

} // namespace

//------------------------------------------------------------------------------
int vtkMRMLResectionPlanNodeTest1(int, char*[])
{
  vtkNew<vtkMRMLScene> scene;
  vtkNew<vtkMRMLResectionPlanNode> exerciseNode;
  exerciseNode->SetScene(scene.GetPointer());
  EXERCISE_ALL_BASIC_MRML_METHODS(exerciseNode.GetPointer());

  CHECK_EXIT_SUCCESS(testInstantiable());
  CHECK_EXIT_SUCCESS(testDefaults());
  CHECK_EXIT_SUCCESS(testPlanStateEnumRoundTrip());
  CHECK_EXIT_SUCCESS(testXMLRoundTrip());
  CHECK_EXIT_SUCCESS(testCreateDefaultStorageNode());
  CHECK_EXIT_SUCCESS(testGeometryNodeReference());
  CHECK_EXIT_SUCCESS(testCopyContent());

  std::cout << "vtkMRMLResectionPlanNodeTest1 completed successfully" << std::endl;
  return EXIT_SUCCESS;
}

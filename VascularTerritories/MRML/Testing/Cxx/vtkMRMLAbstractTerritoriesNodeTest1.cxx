/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

==============================================================================*/

/**
 * \file vtkMRMLAbstractTerritoriesNodeTest1.cxx
 *
 * Test-first scaffolding for the vascular-territories class hierarchy
 * (ADR-0023 §"Class abstraction for territories",
 * Docs/architecture/territories-class-hierarchy.md, ADR-0011 SCT
 * terminology dispatch, ADR-0004 Python/C++ boundary).  Lands per
 * ADR-0027 (test commit predates implementation).
 *
 * Each test pins one architectural invariant.  Test cases that exercise
 * not-yet-implemented behaviour fail red against the stub .cxx -
 * intentional; the follow-up implementer commit flips them green.
 *
 * Invariants pinned:
 *
 *   1. Abstract base non-instantiable per vtkAbstractTypeMacro
 *      (Slicer-core convention -- vtkMRMLAbstractViewNode,
 *      vtkMRMLAbstractLayoutNode).  Compile-time non-instantiability;
 *      runtime sub-test pins the polymorphic complement (concrete
 *      SafeDownCast resolves to the abstract base).
 *   2. Both concrete subclasses instantiate via vtkStandardNewMacro.
 *   3. Polymorphic GetMethod() dispatch via base pointer.
 *   4. Std-Couinaud SCT codes pinned to the ADR-0011 table:
 *      8 codes for Subdivision == I_VIII; 9 codes for
 *      I_VIII_with_IVab (IVa+IVb replace IV).
 *   5. Custom-territories GetSCTCode() returns "" by default; non-empty
 *      only after surgeon opt-in.
 *   6. RegisterNodeClass + GetNodesByClass polymorphic filter.
 *   7. Subject Hierarchy folder placement -- module-logic concern;
 *      skipped here, exercised by the Python wrapper test.
 *   8. MRML XML round-trip of Method + key references.
 *   9. Subdivision enum on Std drives GetNumberOfSegments() (8 vs 9).
 *  10. Custom-territories Groupings map round-trips through XML.
 *  11. Typed ``segments`` node-reference role on the abstract base
 *      to a ``vtkMRMLSegmentationNode`` (the Slicer-core canonical
 *      data carrier).  Set on the concrete StdCouinaud subclass;
 *      retrieved via the abstract-base accessor; survives scene
 *      add/remove cleanly.  Per ADR-0023 amendment 2026-05-25
 *      §"Class abstraction for territories" -- polymorphic interface
 *      tightening -- the role belongs on the abstract base so
 *      consumers do not branch on subclass.
 *  12. Interface-tightening pin: ``GetLabelMap()`` is NO LONGER on
 *      the abstract base after the wrapper-vs-carrier landing.
 *      Callers reach a binary labelmap through the segmentation
 *      carrier (``GetSegmentationNode()->GetBinaryLabelmapRepresentation``
 *      / Slicer-core path).  Comment-only pin -- the absence is
 *      verified compile-time by the absence of the symbol; if a
 *      regression re-adds it, this test file flags the drift via
 *      the literal-anchor reference below.  Per ADR-0023 amendment
 *      2026-05-25 §"Class abstraction for territories" --
 *      "GetLabelMap() is dropped from the interface".
 */

// This module MRML includes
#include "vtkMRMLAbstractTerritoriesNode.h"
#include "vtkMRMLCustomTerritoriesNode.h"
#include "vtkMRMLStdCouinaudTerritoriesNode.h"

// MRML includes
#include "vtkMRMLCoreTestingMacros.h"
#include "vtkMRMLModelNode.h"
#include "vtkMRMLScene.h"

// VTK includes
#include <vtkCollection.h>
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
// Naive ``name="value"`` walker mirroring the
// vtkMRMLBezierSurfaceNodeTest1 round-trip pattern.  Production load
// goes through libxml2, which is not linked into the ctkTest driver.
// Returns the storage vector by reference so the c_str() pointers in
// ``atts`` stay alive for the duration of the caller's
// ReadXMLAttributes call.
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
// Invariant 1 -- Abstract base is non-instantiable, but concrete
// subclasses ARE-A ``vtkMRMLAbstractTerritoriesNode``.  Compile-time
// abstractness is enforced by ``vtkAbstractTypeMacro`` on the header
// (any caller that wrote ``vtkMRMLAbstractTerritoriesNode::New()`` or
// ``vtkNew<vtkMRMLAbstractTerritoriesNode>`` would fail to compile).
// This runtime sub-test pins the complement: a ``SafeDownCast`` from a
// concrete instance to the abstract base resolves, and ``IsTypeOf``
// reports the inheritance.  Together with the compile-time guard this
// is the equivalent of the prior runtime-sentinel ``New() -> nullptr``
// check, modulo the abstractness being unforgeable rather than
// trip-on-dereference.
int testAbstractBaseNotInstantiable()
{
  vtkNew<vtkMRMLStdCouinaudTerritoriesNode> couinaud;
  vtkMRMLAbstractTerritoriesNode* asBase = vtkMRMLAbstractTerritoriesNode::SafeDownCast(couinaud.GetPointer());
  CHECK_NOT_NULL(asBase);
  CHECK_BOOL(couinaud->IsA("vtkMRMLAbstractTerritoriesNode"), true);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 2 -- Concrete subclasses instantiate cleanly.  Smoke test
// for the vtkStandardNewMacro plumbing on the two leaf classes.
int testConcreteSubclassesInstantiate()
{
  vtkNew<vtkMRMLStdCouinaudTerritoriesNode> couinaud;
  CHECK_NOT_NULL(couinaud.GetPointer());
  CHECK_STRING(couinaud->GetNodeTagName(), "StdCouinaudTerritories");

  vtkNew<vtkMRMLCustomTerritoriesNode> custom;
  CHECK_NOT_NULL(custom.GetPointer());
  CHECK_STRING(custom->GetNodeTagName(), "CustomTerritories");
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 3 -- polymorphic GetMethod() dispatch via the abstract base
// pointer.  Stage 4 + Stage 5 consumers rely on this -- no dynamic_cast
// branching.  Architecture-doc §"Polymorphic interface".
int testPolymorphicMethodDispatch()
{
  vtkNew<vtkMRMLStdCouinaudTerritoriesNode> couinaud;
  vtkNew<vtkMRMLCustomTerritoriesNode> custom;

  vtkMRMLAbstractTerritoriesNode* basePtr = couinaud.GetPointer();
  CHECK_NOT_NULL(basePtr);
  CHECK_STRING(basePtr->GetMethod(), "standard-couinaud");

  basePtr = custom.GetPointer();
  CHECK_NOT_NULL(basePtr);
  CHECK_STRING(basePtr->GetMethod(), "custom");
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 4 -- Couinaud SCT codes per ADR-0011 §2.  Pinned ordering
// for both Subdivision enum values.
//
// I_VIII (8 segments):
//   index 0 -> I   71133005
//   index 1 -> II  277956007
//   index 2 -> III 277957003
//   index 3 -> IV  277958008
//   index 4 -> V   277959000
//   index 5 -> VI  277960005
//   index 6 -> VII 277961009
//   index 7 -> VIII 277962002
//
// I_VIII_with_IVab (9 segments) splits IV into IVa/IVb at indices 3/4
// and shifts V..VIII to 5..8:
//   index 3 -> IVa  871688003
//   index 4 -> IVb  871689006
//   index 5 -> V    277959000
//   (etc.)
int testStdCouinaudSCTCodes_IVIII()
{
  vtkNew<vtkMRMLStdCouinaudTerritoriesNode> node;
  node->SetSubdivision(vtkMRMLStdCouinaudTerritoriesNode::I_VIII);

  CHECK_STRING(node->GetSCTCode(0), "71133005");
  CHECK_STRING(node->GetSCTCode(1), "277956007");
  CHECK_STRING(node->GetSCTCode(2), "277957003");
  CHECK_STRING(node->GetSCTCode(3), "277958008");
  CHECK_STRING(node->GetSCTCode(4), "277959000");
  CHECK_STRING(node->GetSCTCode(5), "277960005");
  CHECK_STRING(node->GetSCTCode(6), "277961009");
  CHECK_STRING(node->GetSCTCode(7), "277962002");
  // Out-of-range returns empty string -- ADR-0011 §1 says GetSCTCode
  // never returns nullptr.  Note: this is a strong invariant the
  // stub also honours (returns "").
  CHECK_STRING(node->GetSCTCode(8), "");
  CHECK_STRING(node->GetSCTCode(-1), "");
  return EXIT_SUCCESS;
}

int testStdCouinaudSCTCodes_IVIII_with_IVab()
{
  vtkNew<vtkMRMLStdCouinaudTerritoriesNode> node;
  node->SetSubdivision(vtkMRMLStdCouinaudTerritoriesNode::I_VIII_with_IVab);

  CHECK_STRING(node->GetSCTCode(0), "71133005");
  CHECK_STRING(node->GetSCTCode(1), "277956007");
  CHECK_STRING(node->GetSCTCode(2), "277957003");
  CHECK_STRING(node->GetSCTCode(3), "871688003"); // IVa
  CHECK_STRING(node->GetSCTCode(4), "871689006"); // IVb
  CHECK_STRING(node->GetSCTCode(5), "277959000"); // V
  CHECK_STRING(node->GetSCTCode(6), "277960005"); // VI
  CHECK_STRING(node->GetSCTCode(7), "277961009"); // VII
  CHECK_STRING(node->GetSCTCode(8), "277962002"); // VIII
  CHECK_STRING(node->GetSCTCode(9), "");          // out of range
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 5 -- vtkMRMLCustomTerritoriesNode returns "" from
// GetSCTCode by default (no SCT tagging until surgeon opt-in).  This
// is a strong default the stub already honours; flipping it to a
// non-empty value via SetSegmentSCTCode is exercised too so a future
// regression that drops the opt-in mechanism is caught.
int testCustomSCTCodeDefaultsEmpty()
{
  vtkNew<vtkMRMLCustomTerritoriesNode> node;
  CHECK_STRING(node->GetSCTCode(0), "");
  CHECK_STRING(node->GetSCTCode(5), "");
  CHECK_STRING(node->GetSCTCode(-1), "");

  // Surgeon opt-in roundtrip.
  node->SetSegmentSCTCode(2, "277957003");
  CHECK_STRING(node->GetSCTCode(0), "");
  CHECK_STRING(node->GetSCTCode(2), "277957003");

  // Clear via empty-string set returns to default.
  node->SetSegmentSCTCode(2, "");
  CHECK_STRING(node->GetSCTCode(2), "");
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 6 -- after RegisterNodeClass on all three node classes, a
// scene's GetNodesByClass("vtkMRMLAbstractTerritoriesNode") returns
// instances of BOTH concrete subclasses.  This is the polymorphic
// node-class filter consumers rely on (qMRMLNodeComboBox + the
// .lrp.json writer per architecture doc).
int testPolymorphicNodeClassFilter()
{
  vtkNew<vtkMRMLScene> scene;
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLStdCouinaudTerritoriesNode>::New());
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLCustomTerritoriesNode>::New());

  vtkNew<vtkMRMLStdCouinaudTerritoriesNode> couinaud;
  vtkNew<vtkMRMLCustomTerritoriesNode> custom;
  scene->AddNode(couinaud.GetPointer());
  scene->AddNode(custom.GetPointer());

  // Direct subclass queries -- one instance each.
  vtkSmartPointer<vtkCollection> stdNodes = vtkSmartPointer<vtkCollection>::Take(scene->GetNodesByClass("vtkMRMLStdCouinaudTerritoriesNode"));
  CHECK_INT(stdNodes->GetNumberOfItems(), 1);

  vtkSmartPointer<vtkCollection> customNodes = vtkSmartPointer<vtkCollection>::Take(scene->GetNodesByClass("vtkMRMLCustomTerritoriesNode"));
  CHECK_INT(customNodes->GetNumberOfItems(), 1);

  // Base-class query -- both subclasses match.  This is the strong
  // polymorphic-filter invariant; relies on
  // vtkMRMLScene::IsNodeClassRegistered + IsA traversal.
  vtkSmartPointer<vtkCollection> baseNodes = vtkSmartPointer<vtkCollection>::Take(scene->GetNodesByClass("vtkMRMLAbstractTerritoriesNode"));
  CHECK_INT(baseNodes->GetNumberOfItems(), 2);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 8 -- MRML XML round-trip preserves the Method
// discriminator + key state.  Source node mutated; XML written;
// reloaded into a sink; sink's Method matches.  The
// vtkMRMLBezierSurfaceNodeTest1 pattern for in-memory XML round-trip
// is the precedent.
int testStdCouinaudXMLRoundTrip()
{
  vtkNew<vtkMRMLScene> scene;
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLStdCouinaudTerritoriesNode>::New());

  vtkNew<vtkMRMLStdCouinaudTerritoriesNode> source;
  source->SetScene(scene.GetPointer());
  source->SetSubdivision(vtkMRMLStdCouinaudTerritoriesNode::I_VIII_with_IVab);
  source->SetAIBackendIdentifier("TotalSegmentator-2.0.0");
  source->SetComputedAt("2026-05-22T09:00:00Z");

  std::ostringstream of;
  source->WriteXML(of, 0);
  std::string xml = of.str();

  // Spot-check: serialised text mentions the Method discriminator
  // OR an XML attribute that the implementer wires up.  Either is
  // acceptable; the round-trip itself is the strong invariant.
  // (The stub WriteXML emits only the Superclass payload, so this
  // check fails red until the implementer adds the IVar emission.)
  // Slicer's vtkMRMLWriteXMLStringMacro / vtkMRMLWriteXMLIntMacro emit
  // lower-camelCase XML attribute names (first macro arg), not the IVar
  // name.  Search both possibilities for robustness.
  CHECK_BOOL(xml.find("subdivision") != std::string::npos || xml.find("aiBackendIdentifier") != std::string::npos, true);

  vtkNew<vtkMRMLStdCouinaudTerritoriesNode> sink;
  sink->SetScene(scene.GetPointer());

  // Feed the source's attributes into the sink via ReadXMLAttributes.
  // The walker mirrors the vtkMRMLBezierSurfaceNodeTest1 pattern --
  // libxml2 is not linked into the ctkTest driver, so we parse the
  // emitted name="value" stream ourselves.
  std::vector<std::string> storage;
  std::vector<const char*> atts = buildAttsFromXML(xml, storage);
  sink->ReadXMLAttributes(atts.data());

  // Strong round-trip invariants: subtype discriminator + key state
  // survive write/read.
  CHECK_STRING(sink->GetMethod(), "standard-couinaud");
  CHECK_INT(sink->GetSubdivision(), source->GetSubdivision());
  CHECK_STRING(sink->GetAIBackendIdentifier(), source->GetAIBackendIdentifier());
  CHECK_STRING(sink->GetComputedAt(), source->GetComputedAt());
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 9 -- Subdivision enum drives GetNumberOfSegments().
//   I_VIII           -> 8
//   I_VIII_with_IVab -> 9 (IVa + IVb replace IV; V..VIII shift to 5..8)
int testSubdivisionSegmentCount()
{
  vtkNew<vtkMRMLStdCouinaudTerritoriesNode> node;
  node->SetSubdivision(vtkMRMLStdCouinaudTerritoriesNode::I_VIII);
  CHECK_INT(node->GetNumberOfSegments(), 8);

  node->SetSubdivision(vtkMRMLStdCouinaudTerritoriesNode::I_VIII_with_IVab);
  CHECK_INT(node->GetNumberOfSegments(), 9);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 10 -- Custom-territories Groupings map round-trips through
// XML.  Source map set; XML written; reload pulls the map back
// equivalent.  The stub WriteXML/ReadXMLAttributes do not serialise
// the map -- intentionally red against the stub until the
// implementer commit lands.
int testCustomGroupingsRoundTrip()
{
  vtkNew<vtkMRMLScene> scene;
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLCustomTerritoriesNode>::New());

  vtkNew<vtkMRMLCustomTerritoriesNode> source;
  source->SetScene(scene.GetPointer());
  source->SetGrouping("centerline-A", "segment-RAS-1");
  source->SetGrouping("centerline-B", "segment-RAS-2");
  source->SetGrouping("centerline-C", "segment-RAS-1");
  CHECK_INT(static_cast<int>(source->GetNumberOfGroupings()), 3);

  std::ostringstream of;
  source->WriteXML(of, 0);
  std::string xml = of.str();

  // Implementer-pinned attribute name; stub does not emit, so the
  // assertion fails red until the implementer commit.
  CHECK_BOOL(xml.find("Groupings") != std::string::npos || xml.find("grouping") != std::string::npos, true);

  // Sink round-trip with the source's attribute array, using the same
  // name="value" walker as testStdCouinaudXMLRoundTrip.
  vtkNew<vtkMRMLCustomTerritoriesNode> sink;
  sink->SetScene(scene.GetPointer());
  std::vector<std::string> storage;
  std::vector<const char*> atts = buildAttsFromXML(xml, storage);
  sink->ReadXMLAttributes(atts.data());

  CHECK_INT(static_cast<int>(sink->GetNumberOfGroupings()), static_cast<int>(source->GetNumberOfGroupings()));
  // Spot-check that the individual centerline→segment mappings survive.
  CHECK_STD_STRING(sink->GetGrouping("centerline-A"), "segment-RAS-1");
  CHECK_STD_STRING(sink->GetGrouping("centerline-B"), "segment-RAS-2");
  CHECK_STD_STRING(sink->GetGrouping("centerline-C"), "segment-RAS-1");
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 11 -- Typed ``segments`` node-reference role on the
// abstract base.  Per the 2026-05-25 wrapper-vs-carrier amendment to
// ADR-0023 (§"Class abstraction for territories"), the territories
// node references a canonical ``vtkMRMLSegmentationNode`` for its
// segment-mask data via a typed ``segments`` role.  The role is on
// the abstract base so polymorphic consumers do not branch on
// subclass.
//
// Pin shape: set the ref on a concrete StdCouinaud subclass; verify
// the abstract-base accessor returns the same node; remove the
// referent from the scene; verify the role resolves to nullptr
// cleanly (no dangling pointer).
//
// The role uses a stand-in ``vtkMRMLModelNode`` here so this MRML
// kit-level test does not pull in the Slicer-core Segmentations
// kit as a link-time dependency (the role's class-name filter is a
// separate runtime concern, exercised by the module-logic-level
// integration test that has the Segmentations kit available).
int testSegmentsNodeReference()
{
  vtkNew<vtkMRMLScene> scene;
  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLStdCouinaudTerritoriesNode>::New());

  vtkNew<vtkMRMLStdCouinaudTerritoriesNode> territories;
  vtkNew<vtkMRMLModelNode> standInCarrier;
  scene->AddNode(territories.GetPointer());
  scene->AddNode(standInCarrier.GetPointer());

  // The typed setter on the abstract base accepts any vtkMRMLNode
  // pointer (the runtime class-name filter is on the Slicer-core
  // path).  The role name pinned by the design is "segments".  Set
  // via the abstract-base pointer to confirm the role lives there.
  vtkMRMLAbstractTerritoriesNode* asBase = territories.GetPointer();
  asBase->SetAndObserveNodeReferenceID("segments", standInCarrier->GetID());

  // Retrieved via the typed accessor on the abstract base.  The
  // production accessor name is left to the implementer
  // (``GetSegmentsNode`` is the design's natural choice); the
  // round-trip via ``GetNodeReferenceID`` covers the role-name
  // contract regardless.
  const char* refId = asBase->GetNodeReferenceID("segments");
  CHECK_NOT_NULL(refId);
  CHECK_STRING(refId, standInCarrier->GetID());

  // Scene removal of the referent -> the role resolves to nullptr
  // cleanly.
  scene->RemoveNode(standInCarrier.GetPointer());
  const char* refIdAfterRemove = asBase->GetNodeReferenceID("segments");
  // After Remove the role's referenced node should no longer be
  // resolvable.  ``GetNodeReferenceID`` may return either the
  // stale string OR nullptr depending on the Slicer-core role
  // bookkeeping; the strong invariant is the underlying
  // ``GetNodeReference`` returns nullptr (no dangling pointer).
  vtkMRMLNode* refNode = asBase->GetNodeReference("segments");
  CHECK_NULL(refNode);
  (void)refIdAfterRemove;
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 12 -- Interface-tightening pin: ``GetLabelMap()`` is
// dropped from the abstract base after the 2026-05-25
// wrapper-vs-carrier amendment to ADR-0023.  The labelmap
// representation is reached through the segmentation carrier on the
// Slicer-core path
// (``GetSegmentationNode()->GetBinaryLabelmapRepresentation``).
//
// This is a comment-only invariant pin: the absence of
// ``GetLabelMap`` is enforced compile-time by its absence from the
// abstract base's header.  A test that tried to call
// ``asBase->GetLabelMap()`` would fail to compile (the strong
// guarantee).  The runtime sub-test here uses the polymorphic
// interface roster the design DOES commit to (GetSegments,
// GetSegmentColor, GetSCTCode, GetMethod) -- if a future regression
// re-adds GetLabelMap, the in-file comment-anchor reference to
// ADR-0023 §"Class abstraction for territories" surfaces the drift
// in code review.
//
// Reference (load-bearing for grep regression hunts):
//   ADR-0023 amendment 2026-05-25 §"Class abstraction for
//   territories" --
//   "``GetLabelMap()`` is **dropped** from the interface".
int testInterfaceRosterTightened()
{
  vtkNew<vtkMRMLStdCouinaudTerritoriesNode> couinaud;
  vtkMRMLAbstractTerritoriesNode* asBase = couinaud.GetPointer();

  // The methods the design DOES commit to on the abstract base.
  // Call each through the base pointer; the smoke-test goal is "the
  // tightened interface compiles + dispatches", not the values
  // (those are pinned by earlier invariants).
  CHECK_NOT_NULL(asBase->GetSegments());
  double rgb[3] = { 0, 0, 0 };
  asBase->GetSegmentColor(0, rgb);
  (void)rgb;
  CHECK_NOT_NULL(asBase->GetMethod());
  CHECK_NOT_NULL(asBase->GetSCTCode(0));
  return EXIT_SUCCESS;
}

} // namespace

//------------------------------------------------------------------------------
int vtkMRMLAbstractTerritoriesNodeTest1(int, char*[])
{
  // Invariant 1 -- the abstract base class is intentionally not
  // instantiable.  ``vtkMRMLAbstractTerritoriesNode::New()`` is a
  // runtime sentinel that returns nullptr; concrete subclasses are
  // the only entry points to the hierarchy.  See
  // testAbstractBaseNotInstantiable below.
  vtkNew<vtkMRMLScene> scene;
  vtkNew<vtkMRMLStdCouinaudTerritoriesNode> exerciseNode;
  exerciseNode->SetScene(scene.GetPointer());
  EXERCISE_ALL_BASIC_MRML_METHODS(exerciseNode.GetPointer());

  CHECK_EXIT_SUCCESS(testAbstractBaseNotInstantiable());
  CHECK_EXIT_SUCCESS(testConcreteSubclassesInstantiate());
  CHECK_EXIT_SUCCESS(testPolymorphicMethodDispatch());
  CHECK_EXIT_SUCCESS(testStdCouinaudSCTCodes_IVIII());
  CHECK_EXIT_SUCCESS(testStdCouinaudSCTCodes_IVIII_with_IVab());
  CHECK_EXIT_SUCCESS(testCustomSCTCodeDefaultsEmpty());
  CHECK_EXIT_SUCCESS(testPolymorphicNodeClassFilter());
  CHECK_EXIT_SUCCESS(testStdCouinaudXMLRoundTrip());
  CHECK_EXIT_SUCCESS(testSubdivisionSegmentCount());
  CHECK_EXIT_SUCCESS(testCustomGroupingsRoundTrip());
  CHECK_EXIT_SUCCESS(testSegmentsNodeReference());
  CHECK_EXIT_SUCCESS(testInterfaceRosterTightened());

  std::cout << "vtkMRMLAbstractTerritoriesNodeTest1 completed successfully" << std::endl;
  return EXIT_SUCCESS;
}

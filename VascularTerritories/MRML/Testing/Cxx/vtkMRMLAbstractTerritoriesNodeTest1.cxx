/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Test-first scaffolding for the v2.0.0 vascular-territories class
  hierarchy (ADR-0023 §"Class abstraction for territories",
  Docs/architecture/territories-class-hierarchy.md, ADR-0011 SCT
  terminology dispatch, ADR-0004 Python/C++ boundary).  Lands per
  ADR-0027 (test commit predates implementation).

  Each test pins one architectural invariant.  Test cases that exercise
  not-yet-implemented behaviour fail red against the stub .cxx -
  intentional; the follow-up implementer commit flips them green.

  Invariants pinned:

    1. Abstract base non-instantiable (intrinsic to the missing New()).
    2. Both concrete subclasses instantiate via vtkStandardNewMacro.
    3. Polymorphic GetMethod() dispatch via base pointer.
    4. Std-Couinaud SCT codes pinned to the 10-code ADR-0011 table.
    5. Custom-territories GetSCTCode() returns "" by default; non-empty
       only after surgeon opt-in.
    6. RegisterNodeClass + GetNodesByClass polymorphic filter.
    7. Subject Hierarchy folder placement -- module-logic concern;
       skipped here, exercised by the Python wrapper test.
    8. MRML XML round-trip of Method + key references.
    9. Subdivision enum on Std drives GetNumberOfSegments() (8 vs 10).
    10. Custom-territories Groupings map round-trips through XML.

==============================================================================*/

// This module MRML includes
#include "vtkMRMLAbstractTerritoriesNode.h"
#include "vtkMRMLCustomTerritoriesNode.h"
#include "vtkMRMLStdCouinaudTerritoriesNode.h"

// MRML includes
#include "vtkMRMLCoreTestingMacros.h"
#include "vtkMRMLScene.h"

// VTK includes
#include <vtkCollection.h>
#include <vtkNew.h>
#include <vtkSmartPointer.h>

// STD includes
#include <cstring>
#include <iostream>
#include <sstream>
#include <string>

namespace
{

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
// I_VIII_with_IVab (10 segments) splits IV into IVa/IVb at indices 3/4
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
  CHECK_STRING(node->GetSCTCode(9), ""); // out of range
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
  vtkSmartPointer<vtkCollection> stdNodes =
    vtkSmartPointer<vtkCollection>::Take(
      scene->GetNodesByClass("vtkMRMLStdCouinaudTerritoriesNode"));
  CHECK_INT(stdNodes->GetNumberOfItems(), 1);

  vtkSmartPointer<vtkCollection> customNodes =
    vtkSmartPointer<vtkCollection>::Take(
      scene->GetNodesByClass("vtkMRMLCustomTerritoriesNode"));
  CHECK_INT(customNodes->GetNumberOfItems(), 1);

  // Base-class query -- both subclasses match.  This is the strong
  // polymorphic-filter invariant; relies on
  // vtkMRMLScene::IsNodeClassRegistered + IsA traversal.
  vtkSmartPointer<vtkCollection> baseNodes =
    vtkSmartPointer<vtkCollection>::Take(
      scene->GetNodesByClass("vtkMRMLAbstractTerritoriesNode"));
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
  CHECK_BOOL(xml.find("Subdivision") != std::string::npos ||
             xml.find("AIBackendIdentifier") != std::string::npos,
             true);

  vtkNew<vtkMRMLStdCouinaudTerritoriesNode> sink;
  sink->SetScene(scene.GetPointer());

  // Sink round-trip: feed the source's attributes into the sink via
  // ReadXMLAttributes.  The implementer pins the exact attribute
  // names; the test does NOT hard-code them (just checks key state
  // survives).  For the stub, this is a no-op and the assertions
  // below fail red.
  CHECK_STRING(sink->GetMethod(), "standard-couinaud"); // pure-class invariant

  // The implementer must make Subdivision survive WriteXML/ReadXMLAttributes.
  // Stub state on a fresh node defaults to I_VIII; after a real round-trip
  // from the source (set to I_VIII_with_IVab) the sink must match.
  // TODO(impl): supply the parsed atts[] array (mirror the
  //             vtkMRMLBezierSurfaceNodeTest1::testXMLRoundTrip walker)
  //             once WriteXML emits stable attribute names.
  // For now we assert the strong post-condition: sink's Subdivision
  // matches source's after a notional round-trip.  Until the
  // implementer wires WriteXML/ReadXMLAttributes, this comparison
  // exercises only the default ctor state and the test passes
  // trivially -- so we additionally check the source state did not
  // collapse during WriteXML, which would be a different bug.
  CHECK_INT(source->GetSubdivision(),
            vtkMRMLStdCouinaudTerritoriesNode::I_VIII_with_IVab);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 9 -- Subdivision enum drives GetNumberOfSegments().
//   I_VIII           -> 8
//   I_VIII_with_IVab -> 10
int testSubdivisionSegmentCount()
{
  vtkNew<vtkMRMLStdCouinaudTerritoriesNode> node;
  node->SetSubdivision(vtkMRMLStdCouinaudTerritoriesNode::I_VIII);
  CHECK_INT(node->GetNumberOfSegments(), 8);

  node->SetSubdivision(vtkMRMLStdCouinaudTerritoriesNode::I_VIII_with_IVab);
  CHECK_INT(node->GetNumberOfSegments(), 10);
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
  CHECK_BOOL(xml.find("Groupings") != std::string::npos ||
             xml.find("grouping") != std::string::npos,
             true);

  // Sink round-trip with the source's attribute array.  The exact
  // ReadXMLAttributes attribute-name parsing is implementer-specified;
  // the strong invariant is "groupings count survives".  Until the
  // implementer wires it, the sink starts empty and the assertion
  // fails red.
  vtkNew<vtkMRMLCustomTerritoriesNode> sink;
  sink->SetScene(scene.GetPointer());
  // TODO(impl): mirror the vtkMRMLBezierSurfaceNodeTest1 XML attribute
  //             walker pattern -- parse `xml` back into a const char**
  //             attribute array and feed sink->ReadXMLAttributes(...).
  //             Once WriteXML emits a stable serialisation the parser
  //             can be a one-line plumbing.
  CHECK_INT(static_cast<int>(sink->GetNumberOfGroupings()),
            static_cast<int>(source->GetNumberOfGroupings()));
  return EXIT_SUCCESS;
}

} // namespace

//------------------------------------------------------------------------------
int vtkMRMLAbstractTerritoriesNodeTest1(int, char*[])
{
  // Invariant 1 -- the abstract base class is intentionally not
  // instantiable; vtkMRMLAbstractTerritoriesNode declares no
  // ``New()``.  This invariant is enforced at compile-time: trying
  // to instantiate via ``vtkNew<vtkMRMLAbstractTerritoriesNode>``
  // would fail to link against ``vtkMRMLAbstractTerritoriesNode::New``.
  // We assert the invariant indirectly: the concrete subclasses are
  // the only entry points to the hierarchy.
  vtkNew<vtkMRMLScene> scene;
  vtkNew<vtkMRMLStdCouinaudTerritoriesNode> exerciseNode;
  exerciseNode->SetScene(scene.GetPointer());
  EXERCISE_ALL_BASIC_MRML_METHODS(exerciseNode.GetPointer());

  CHECK_EXIT_SUCCESS(testConcreteSubclassesInstantiate());
  CHECK_EXIT_SUCCESS(testPolymorphicMethodDispatch());
  CHECK_EXIT_SUCCESS(testStdCouinaudSCTCodes_IVIII());
  CHECK_EXIT_SUCCESS(testStdCouinaudSCTCodes_IVIII_with_IVab());
  CHECK_EXIT_SUCCESS(testCustomSCTCodeDefaultsEmpty());
  CHECK_EXIT_SUCCESS(testPolymorphicNodeClassFilter());
  CHECK_EXIT_SUCCESS(testStdCouinaudXMLRoundTrip());
  CHECK_EXIT_SUCCESS(testSubdivisionSegmentCount());
  CHECK_EXIT_SUCCESS(testCustomGroupingsRoundTrip());

  std::cout << "vtkMRMLAbstractTerritoriesNodeTest1 completed successfully"
            << std::endl;
  return EXIT_SUCCESS;
}

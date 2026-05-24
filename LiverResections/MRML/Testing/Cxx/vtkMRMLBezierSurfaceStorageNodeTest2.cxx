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

  Invariant test scaffolding for ``.lrp.json`` schema v3 — surfaces the
  v2.0 surgeon-facing state per ADR-0023 §"Persistence".  Per ADR-0027,
  these tests land BEFORE the implementation commit and pin the v3
  design contract; they are expected to FAIL on the current v2 writer
  + reader and to flip to passing once liver-implementer lands the v3
  fields in vtkMRMLBezierSurfaceStorageNode.

  Pinned invariants (ADR-0023 §"Persistence" + the schema-versioning
  convention from the file-header comment in
  vtkMRMLBezierSurfaceStorageNode.cxx):

   - testV3RoundTripFullFields: name + Safety/Risk margins + orderIndex
     + classification + volumetry partition references survive a
     write → read → write cycle.
   - testV2ToV3FallbackDefaults: v2 files load into v3-aware nodes with
     documented defaults (name = MRML display name, margins = 0.0,
     orderIndex = -1, classification absent, volumetry partitions
     empty, stageSelection absent).
   - testV3WriteEmitsSchemaVersion3: the on-disk schemaVersion is 3
     and is not 2.
   - testV3ClassificationSubtypeDiscriminator: scene.classification
     .subtype matches the concrete vtkMRMLAbstractTerritoriesNode
     subclass name (vtkMRMLStdCouinaudTerritoriesNode vs
     vtkMRMLCustomTerritoriesNode), preserving the polymorphic-
     interface discriminator from ADR-0023 §"Class abstraction for
     territories".
   - testV3ReaderAcceptsV3RangeAndRejectsV99: the reader's accepted
     schemaVersion band grows from [1, 2] to [1, 3]; v99 stays
     rejected (the schema-versioning invariant first pinned in
     testSchemaVersionMismatch of Test1).

  ADR-0008 §2: C++ low-level tests live alongside the MRML library
  and run under the ctkTest driver with no Slicer launch and no Qt.

==============================================================================*/

// This module MRML includes
#include "vtkMRMLBezierSurfaceNode.h"
#include "vtkMRMLBezierSurfaceStorageNode.h"

// MRML includes
#include "vtkMRMLCoreTestingMacros.h"
#include "vtkMRMLScene.h"

// VTK includes
#include <vtkNew.h>
#include <vtksys/SystemTools.hxx>

// STD includes
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>

// Portable getpid — mirrors the helper in
// vtkMRMLBezierSurfaceStorageNodeTest1.cxx so the temp-path generator
// stays Windows-portable.
#if defined(_WIN32)
# include <process.h>
# define LIVER_BEZIER_GETPID _getpid
#else
# include <unistd.h>
# define LIVER_BEZIER_GETPID ::getpid
#endif

namespace
{

/// Generate a unique temp file path with the given extension under the
/// CMake binary tree's Testing/Temporary directory (set via the
/// LIVER_BEZIER_STORAGE_TEST_TEMP_DIR macro defined in CMakeLists.txt).
std::string makeTempPath(const std::string& extension)
{
  static int counter = 0;
  ++counter;
  std::ostringstream ss;
  ss << LIVER_BEZIER_STORAGE_TEST_TEMP_DIR << "/vtkMRMLBezierSurfaceStorageNodeTest2_" << static_cast<long long>(LIVER_BEZIER_GETPID()) << "_" << counter << "." << extension;
  return ss.str();
}

/// Read the entire content of a file into a string for substring
/// assertions.  The v3 invariant tests pin JSON shape at the byte
/// level — accessor-based pinning is deferred until liver-implementer
/// lands the v3 in-memory APIs on vtkMRMLBezierSurfaceNode.
std::string slurp(const std::string& path)
{
  std::ifstream f(path);
  std::stringstream ss;
  ss << f.rdbuf();
  return ss.str();
}

/// Substring-or-tolerant-substring search.  rapidjson emits compact
/// JSON (no whitespace around the ``:``); a future ADR may flip the
/// writer to pretty-print.  Accept both shapes so the pin is not
/// sensitive to that choice.
bool contains(const std::string& haystack, const std::string& key, const std::string& value)
{
  // Compact:  "key":value
  // Spaced:   "key": value
  const std::string compact = std::string("\"") + key + "\":" + value;
  const std::string spaced = std::string("\"") + key + "\": " + value;
  return haystack.find(compact) != std::string::npos || haystack.find(spaced) != std::string::npos;
}

/// Populate a Bezier surface node with deterministic v2 fields.
/// Mirrors the populate() helper in
/// vtkMRMLBezierSurfaceStorageNodeTest1.cxx — kept self-contained
/// because the two test translation units do not share helpers.
void populateV2Fields(vtkMRMLBezierSurfaceNode* node)
{
  node->SetInitMode(vtkMRMLBezierSurfaceNode::SlicingPlane);
  double origin[3] = { 1.0, 2.0, 3.0 };
  node->SetSlicingPlaneOrigin(origin);
  double normal[3] = { 0.0, 0.0, 1.0 };
  node->SetSlicingPlaneNormal(normal);
  double p0[3] = { 4.0, 5.0, 6.0 };
  double p1[3] = { 7.0, 8.0, 9.0 };
  node->SetSlicingPlaneInitPoint(0, p0);
  node->SetSlicingPlaneInitPoint(1, p1);
  node->SetState(vtkMRMLBezierSurfaceNode::Planning);
  double grid[vtkMRMLBezierSurfaceNode::ControlGridSize];
  for (int i = 0; i < vtkMRMLBezierSurfaceNode::ControlGridSize; ++i)
  {
    grid[i] = static_cast<double>(i) * 0.0625;
  }
  node->SetControlGrid(grid);
}

/// Populate a Bezier surface node with the v3 surgeon-facing state.
/// The contract per ADR-0023 §"Persistence" is:
///   - name      = node's MRML display name (here "Right hemihepatectomy")
///   - safetyMargin_mm sourced from existing ResectionMargin field
///   - riskMargin_mm   sourced from existing UncertaintyMargin field
///   - orderIndex sourced from a new OrderIndex attribute on
///     vtkMRMLBezierSurfaceNode (sentinel -1 for unordered).
///
/// Until liver-implementer lands the dedicated getters/setters on
/// vtkMRMLBezierSurfaceNode, this helper communicates the intended
/// values via MRML attributes — they are observable to the storage
/// node via the in-tree GetAttribute() surface.  The implementer is
/// free to migrate this populate path to typed accessors once those
/// exist; the byte-level assertions on the emitted JSON do not
/// change.
void populateV3SurgeonState(vtkMRMLBezierSurfaceNode* node)
{
  node->SetName("Right hemihepatectomy");
  // Attribute names match the JSON key vocabulary so the implementer's
  // writer can route the value through either a typed accessor or a
  // GetAttribute() lookup; the test does not commit to either path.
  node->SetAttribute("safetyMargin_mm", "10.0");
  node->SetAttribute("riskMargin_mm", "5.0");
  node->SetAttribute("orderIndex", "0");
}

//------------------------------------------------------------------------------
// Test 1 — v3 round-trip of the full surgeon-facing field roster.
//
// Pinned invariant (ADR-0023 §"Persistence"):
//   A populated v3 file written then re-loaded then re-written carries
//   forward name + safetyMargin_mm + riskMargin_mm + orderIndex +
//   scene.classification + scene.volumetryPartitions with byte-fidelity
//   on the strings and the documented 1e-12 tolerance on the doubles.
//
// This test must FAIL on the current v2 writer (which emits none of the
// new fields).  liver-implementer flips it to PASS by extending
// WriteJson + ReadJson in vtkMRMLBezierSurfaceStorageNode.
//------------------------------------------------------------------------------
int testV3RoundTripFullFields()
{
  vtkNew<vtkMRMLScene> scene;
  vtkNew<vtkMRMLBezierSurfaceNode> source;
  scene->AddNode(source.GetPointer());
  populateV2Fields(source.GetPointer());
  populateV3SurgeonState(source.GetPointer());

  // First write — source → disk.
  const std::string path1 = makeTempPath("lrp.json");
  vtkNew<vtkMRMLBezierSurfaceStorageNode> writeStorage;
  writeStorage->SetFileName(path1.c_str());
  CHECK_INT(writeStorage->WriteData(source.GetPointer()), 1);

  // Read into a fresh sink — same scene so node IDs are stable.
  vtkNew<vtkMRMLBezierSurfaceNode> sink;
  scene->AddNode(sink.GetPointer());
  vtkNew<vtkMRMLBezierSurfaceStorageNode> readStorage;
  readStorage->SetFileName(path1.c_str());
  CHECK_INT(readStorage->ReadData(sink.GetPointer()), 1);

  // Second write — sink → disk.  The byte-level assertions on this
  // file pin the round-trip invariant: if the writer dropped a field
  // on the first hop or the reader dropped it on the second, the
  // re-write will not contain it.
  const std::string path2 = makeTempPath("lrp.json");
  vtkNew<vtkMRMLBezierSurfaceStorageNode> rewriteStorage;
  rewriteStorage->SetFileName(path2.c_str());
  CHECK_INT(rewriteStorage->WriteData(sink.GetPointer()), 1);

  const std::string contents = slurp(path2);

  // resection block — name, safetyMargin_mm, riskMargin_mm, orderIndex.
  // The string assertion is byte-fidelity per the test contract.
  if (contents.find("\"name\":\"Right hemihepatectomy\"") == std::string::npos && contents.find("\"name\": \"Right hemihepatectomy\"") == std::string::npos)
  {
    std::cerr << "testV3RoundTripFullFields: expected \"name\": \"Right hemihepatectomy\" in re-written JSON; got:\n" << contents << "\n";
    return EXIT_FAILURE;
  }
  if (!contains(contents, "safetyMargin_mm", "10.0") && !contains(contents, "safetyMargin_mm", "10"))
  {
    std::cerr << "testV3RoundTripFullFields: expected safetyMargin_mm = 10.0 in re-written JSON; got:\n" << contents << "\n";
    return EXIT_FAILURE;
  }
  if (!contains(contents, "riskMargin_mm", "5.0") && !contains(contents, "riskMargin_mm", "5"))
  {
    std::cerr << "testV3RoundTripFullFields: expected riskMargin_mm = 5.0 in re-written JSON; got:\n" << contents << "\n";
    return EXIT_FAILURE;
  }
  if (!contains(contents, "orderIndex", "0"))
  {
    std::cerr << "testV3RoundTripFullFields: expected orderIndex = 0 in re-written JSON; got:\n" << contents << "\n";
    return EXIT_FAILURE;
  }

  // scene block — classification + volumetryPartitions.  The exact
  // node-ID strings are scene-dependent (vtkMRMLScene allocates them
  // sequentially) so we pin the keys' presence; the per-subtype
  // assertion lives in testV3ClassificationSubtypeDiscriminator.
  if (contents.find("\"scene\"") == std::string::npos)
  {
    std::cerr << "testV3RoundTripFullFields: expected \"scene\" block in re-written JSON; got:\n" << contents << "\n";
    return EXIT_FAILURE;
  }
  if (contents.find("\"classification\"") == std::string::npos)
  {
    std::cerr << "testV3RoundTripFullFields: expected scene.classification in re-written JSON; got:\n" << contents << "\n";
    return EXIT_FAILURE;
  }
  if (contents.find("\"volumetryPartitions\"") == std::string::npos)
  {
    std::cerr << "testV3RoundTripFullFields: expected scene.volumetryPartitions in re-written JSON; got:\n" << contents << "\n";
    return EXIT_FAILURE;
  }

  // resection block presence — sibling of the field-level checks above.
  if (contents.find("\"resection\"") == std::string::npos)
  {
    std::cerr << "testV3RoundTripFullFields: expected \"resection\" block in re-written JSON; got:\n" << contents << "\n";
    return EXIT_FAILURE;
  }

  vtksys::SystemTools::RemoveFile(path1);
  vtksys::SystemTools::RemoveFile(path2);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Test 2 — v2-on-disk → v3-in-memory fallback defaults.
//
// Pinned invariant (ADR-0023 §"Persistence" + the v2→v3 migration
// branch documented in the schema header of
// vtkMRMLBezierSurfaceStorageNode.cxx):
//   A v2 file (no resection/scene blocks) loads cleanly into a
//   v3-aware reader.  The missing v3 fields take documented defaults:
//
//     name                          = the node's MRML display name
//     resection.safetyMargin_mm     = 0.0
//     resection.riskMargin_mm       = 0.0
//     resection.orderIndex          = -1  (sentinel: unordered)
//     scene.classification          = absent  (no reference set)
//     scene.volumetryPartitions     = empty array
//     scene.stageSelection          = absent
//
// The defaults are pinned via a re-write round-trip: after loading the
// v2 file the test re-writes the (now v3-aware) node and asserts the
// emitted JSON carries the documented defaults.  This bypasses the
// need for new in-memory accessors on vtkMRMLBezierSurfaceNode and
// keeps the test focused on the storage-node contract.
//
// This test must FAIL on the current writer (the re-written file is a
// v2 file, not v3; the defaults block is absent).
//------------------------------------------------------------------------------
int testV2ToV3FallbackDefaults()
{
  // Synthesise a minimal valid v2 .lrp.json with no resection/scene
  // blocks — i.e. exactly what the schema-v2 writer (current
  // vtkMRMLBezierSurfaceStorageNode::SchemaVersion) emits.
  const std::string v2Path = makeTempPath("lrp.json");
  {
    std::ofstream ofs(v2Path);
    ofs << "{\n";
    ofs << "  \"schemaVersion\": 2,\n";
    ofs << "  \"state\": \"Planning\",\n";
    ofs << "  \"initMode\": \"SlicingPlane\",\n";
    ofs << "  \"rows\": 4,\n";
    ofs << "  \"cols\": 4,\n";
    ofs << "  \"controlGrid\": [";
    for (int i = 0; i < 48; ++i)
    {
      if (i > 0)
      {
        ofs << ", ";
      }
      ofs << (static_cast<double>(i) * 0.0625);
    }
    ofs << "],\n";
    ofs << "  \"slicingPlane\": { \"origin\": [0, 0, 0], \"normal\": [0, 0, 1], "
           "\"initPointsFlat\": [0, 0, 0, 0, 0, 0] },\n";
    ofs << "  \"distanceSpheroid\": { \"center\": [0, 0, 0], "
           "\"radius\": {\"x\": 0, \"y\": 0, \"z\": 0}, "
           "\"numberOfInitPoints\": 0, \"initPointsFlat\": [] },\n";
    ofs << "  \"metadata\": {}\n";
    ofs << "}\n";
  }

  vtkNew<vtkMRMLScene> scene;
  vtkNew<vtkMRMLBezierSurfaceNode> sink;
  scene->AddNode(sink.GetPointer());
  sink->SetName("LegacyPlanFromV2");

  vtkNew<vtkMRMLBezierSurfaceStorageNode> storage;
  storage->SetFileName(v2Path.c_str());
  CHECK_INT(storage->ReadData(sink.GetPointer()), 1);

  // Re-write and inspect the emitted JSON for the v3 defaults.
  const std::string rewritePath = makeTempPath("lrp.json");
  vtkNew<vtkMRMLBezierSurfaceStorageNode> rewriteStorage;
  rewriteStorage->SetFileName(rewritePath.c_str());
  CHECK_INT(rewriteStorage->WriteData(sink.GetPointer()), 1);

  const std::string contents = slurp(rewritePath);

  // Default name = MRML display name.
  if (contents.find("\"name\":\"LegacyPlanFromV2\"") == std::string::npos && contents.find("\"name\": \"LegacyPlanFromV2\"") == std::string::npos)
  {
    std::cerr << "testV2ToV3FallbackDefaults: expected name default = MRML display name "
                 "(\"LegacyPlanFromV2\") in re-written JSON; got:\n"
              << contents << "\n";
    return EXIT_FAILURE;
  }
  // Default margins = 0.0.
  if (!contains(contents, "safetyMargin_mm", "0.0") && !contains(contents, "safetyMargin_mm", "0"))
  {
    std::cerr << "testV2ToV3FallbackDefaults: expected safetyMargin_mm default = 0.0; got:\n" << contents << "\n";
    return EXIT_FAILURE;
  }
  if (!contains(contents, "riskMargin_mm", "0.0") && !contains(contents, "riskMargin_mm", "0"))
  {
    std::cerr << "testV2ToV3FallbackDefaults: expected riskMargin_mm default = 0.0; got:\n" << contents << "\n";
    return EXIT_FAILURE;
  }
  // Default orderIndex = -1 (sentinel: unordered).
  if (!contains(contents, "orderIndex", "-1"))
  {
    std::cerr << "testV2ToV3FallbackDefaults: expected orderIndex default = -1 (sentinel); got:\n" << contents << "\n";
    return EXIT_FAILURE;
  }
  // scene.classification absent (no nodeId emitted).  We tolerate a
  // null-valued classification block as a valid v3 shape too — the
  // Liver shell that writes the scene.stageSelection block lands in
  // a follow-up; until then a v3 file with all-null stageSelection +
  // absent classification is a valid v3 shape per ADR-0023
  // §"Persistence".
  const bool classificationAbsent = contents.find("\"classification\":null") != std::string::npos || contents.find("\"classification\": null") != std::string::npos
                                    || contents.find("\"classification\"") == std::string::npos;
  if (!classificationAbsent)
  {
    // If the block is present, it MUST NOT carry a populated nodeId
    // (the sink was loaded from a v2 file with no classification).
    if (contents.find("\"nodeId\":\"vtkMRML") != std::string::npos || contents.find("\"nodeId\": \"vtkMRML") != std::string::npos)
    {
      std::cerr << "testV2ToV3FallbackDefaults: expected absent / null classification "
                   "block (no classification was set); got:\n"
                << contents << "\n";
      return EXIT_FAILURE;
    }
  }
  // scene.volumetryPartitions = empty array.  Accept both "absent"
  // and "[]" — the writer's choice between the two is below this
  // test's pinning resolution.
  if (contents.find("\"volumetryPartitions\":[]") == std::string::npos && contents.find("\"volumetryPartitions\": []") == std::string::npos
      && contents.find("\"volumetryPartitions\"") != std::string::npos)
  {
    // Block present but not empty — the v2 source had no partitions.
    std::cerr << "testV2ToV3FallbackDefaults: expected empty volumetryPartitions; got:\n" << contents << "\n";
    return EXIT_FAILURE;
  }

  vtksys::SystemTools::RemoveFile(v2Path);
  vtksys::SystemTools::RemoveFile(rewritePath);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Test 3 — the writer emits schemaVersion = 3 (not 2).
//
// Pinned invariant (ADR-0023 §"Conformance" — "the schema header
// reads schemaVersion: 3 on writes"):
//   Every v3-aware write carries the literal "schemaVersion": 3 in
//   the on-disk JSON.  The v2 marker "schemaVersion": 2 is absent.
//
// This test must FAIL on the current writer (which emits
// "schemaVersion": 2 unconditionally).  liver-implementer flips it
// to PASS by bumping
// vtkMRMLBezierSurfaceStorageNode::SchemaVersion from 2 to 3.
//------------------------------------------------------------------------------
int testV3WriteEmitsSchemaVersion3()
{
  vtkNew<vtkMRMLScene> scene;
  vtkNew<vtkMRMLBezierSurfaceNode> source;
  scene->AddNode(source.GetPointer());
  populateV2Fields(source.GetPointer());
  populateV3SurgeonState(source.GetPointer());

  const std::string path = makeTempPath("lrp.json");
  vtkNew<vtkMRMLBezierSurfaceStorageNode> writeStorage;
  writeStorage->SetFileName(path.c_str());
  CHECK_INT(writeStorage->WriteData(source.GetPointer()), 1);

  const std::string contents = slurp(path);

  // Positive — schemaVersion is 3.
  if (contents.find("\"schemaVersion\":3") == std::string::npos && contents.find("\"schemaVersion\": 3") == std::string::npos)
  {
    std::cerr << "testV3WriteEmitsSchemaVersion3: expected \"schemaVersion\": 3 in JSON; got:\n" << contents << "\n";
    return EXIT_FAILURE;
  }
  // Negative — schemaVersion is NOT 2.  Pins the "writer always
  // emits the current schema" half of the invariant.
  if (contents.find("\"schemaVersion\":2") != std::string::npos || contents.find("\"schemaVersion\": 2") != std::string::npos)
  {
    std::cerr << "testV3WriteEmitsSchemaVersion3: unexpected \"schemaVersion\": 2 in JSON; got:\n" << contents << "\n";
    return EXIT_FAILURE;
  }

  vtksys::SystemTools::RemoveFile(path);
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Test 4 — scene.classification.subtype discriminates between
// vtkMRMLAbstractTerritoriesNode subclasses.
//
// Pinned invariant (ADR-0023 §"Persistence" + §"Class abstraction
// for territories"):
//   The scene.classification.subtype string is the concrete VTK class
//   name of the referent vtkMRMLAbstractTerritoriesNode subclass.
//   Two sub-cases exercise the two extant subclasses landed by the
//   territories class hierarchy: vtkMRMLStdCouinaudTerritoriesNode
//   (Stage 3 Auto path) and vtkMRMLCustomTerritoriesNode (Stage 3
//   Manual path).
//
// Until liver-implementer lands the resection→classification node-
// reference role on vtkMRMLBezierSurfaceNode, the test communicates
// the intended referent's class name via an MRML attribute
// ("classificationSubtype").  The contract on the writer is to emit
// scene.classification.subtype matching that class name regardless of
// whether the implementer routes the value through a typed node
// reference or through the attribute lookup.
//
// This test must FAIL on the current writer (no scene block).
//------------------------------------------------------------------------------
int testV3ClassificationSubtypeDiscriminator()
{
  // Sub-case A — standard Couinaud (Auto path).
  {
    vtkNew<vtkMRMLScene> scene;
    vtkNew<vtkMRMLBezierSurfaceNode> source;
    scene->AddNode(source.GetPointer());
    populateV2Fields(source.GetPointer());
    populateV3SurgeonState(source.GetPointer());
    source->SetAttribute("classificationSubtype", "vtkMRMLStdCouinaudTerritoriesNode");

    const std::string path = makeTempPath("lrp.json");
    vtkNew<vtkMRMLBezierSurfaceStorageNode> writeStorage;
    writeStorage->SetFileName(path.c_str());
    CHECK_INT(writeStorage->WriteData(source.GetPointer()), 1);

    const std::string contents = slurp(path);
    if (contents.find("\"subtype\":\"vtkMRMLStdCouinaudTerritoriesNode\"") == std::string::npos
        && contents.find("\"subtype\": \"vtkMRMLStdCouinaudTerritoriesNode\"") == std::string::npos)
    {
      std::cerr << "testV3ClassificationSubtypeDiscriminator (Auto path): expected "
                   "scene.classification.subtype = \"vtkMRMLStdCouinaudTerritoriesNode\"; got:\n"
                << contents << "\n";
      return EXIT_FAILURE;
    }
    vtksys::SystemTools::RemoveFile(path);
  }

  // Sub-case B — custom Manual path.
  {
    vtkNew<vtkMRMLScene> scene;
    vtkNew<vtkMRMLBezierSurfaceNode> source;
    scene->AddNode(source.GetPointer());
    populateV2Fields(source.GetPointer());
    populateV3SurgeonState(source.GetPointer());
    source->SetAttribute("classificationSubtype", "vtkMRMLCustomTerritoriesNode");

    const std::string path = makeTempPath("lrp.json");
    vtkNew<vtkMRMLBezierSurfaceStorageNode> writeStorage;
    writeStorage->SetFileName(path.c_str());
    CHECK_INT(writeStorage->WriteData(source.GetPointer()), 1);

    const std::string contents = slurp(path);
    if (contents.find("\"subtype\":\"vtkMRMLCustomTerritoriesNode\"") == std::string::npos && contents.find("\"subtype\": \"vtkMRMLCustomTerritoriesNode\"") == std::string::npos)
    {
      std::cerr << "testV3ClassificationSubtypeDiscriminator (Custom path): expected "
                   "scene.classification.subtype = \"vtkMRMLCustomTerritoriesNode\"; got:\n"
                << contents << "\n";
      return EXIT_FAILURE;
    }
    vtksys::SystemTools::RemoveFile(path);
  }
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Test 5 — the schemaVersion-acceptance band is [1, 3]; v99 still
// rejected.
//
// Pinned invariant (the schema-versioning convention in the file
// header of vtkMRMLBezierSurfaceStorageNode.cxx — the
// MinReadableSchemaVersion / SchemaVersion constants):
//   The reader admits files with schemaVersion in
//   [MinReadableSchemaVersion, SchemaVersion].  After v3 lands the
//   upper bound is 3; v99 (or any other out-of-band value) is
//   rejected with a vtkErrorMacro.
//
// This is the v3 extension of testSchemaVersionMismatch from Test1
// (which exercises the v99 rejection against the [1, 2] band).  The
// v99-rejection half of this test passes against the current writer
// (99 is outside both [1, 2] and [1, 3]); the v3-acceptance half
// fails until liver-implementer bumps the SchemaVersion constant.
//------------------------------------------------------------------------------
int testV3ReaderAcceptsV3RangeAndRejectsV99()
{
  // Half (a) — synthesise a v3 file with the minimal v3 shape and
  // assert the reader accepts it.  Pre-implementation this assertion
  // fails because the reader's upper bound is still 2.
  {
    const std::string path = makeTempPath("lrp.json");
    {
      std::ofstream ofs(path);
      ofs << "{\n";
      ofs << "  \"schemaVersion\": 3,\n";
      ofs << "  \"state\": \"Planning\",\n";
      ofs << "  \"initMode\": \"SlicingPlane\",\n";
      ofs << "  \"rows\": 4,\n";
      ofs << "  \"cols\": 4,\n";
      ofs << "  \"controlGrid\": [";
      for (int i = 0; i < 48; ++i)
      {
        if (i > 0)
        {
          ofs << ", ";
        }
        ofs << "0.0";
      }
      ofs << "],\n";
      ofs << "  \"slicingPlane\": { \"origin\": [0, 0, 0], \"normal\": [0, 0, 1], "
             "\"initPointsFlat\": [0, 0, 0, 0, 0, 0] },\n";
      ofs << "  \"distanceSpheroid\": { \"center\": [0, 0, 0], "
             "\"radius\": {\"x\": 0, \"y\": 0, \"z\": 0}, "
             "\"numberOfInitPoints\": 0, \"initPointsFlat\": [] },\n";
      ofs << "  \"resection\": { \"name\": \"\", \"safetyMargin_mm\": 0.0, "
             "\"riskMargin_mm\": 0.0, \"orderIndex\": -1 },\n";
      ofs << "  \"scene\": { \"volumetryPartitions\": [] },\n";
      ofs << "  \"metadata\": {}\n";
      ofs << "}\n";
    }
    vtkNew<vtkMRMLScene> scene;
    vtkNew<vtkMRMLBezierSurfaceNode> sink;
    scene->AddNode(sink.GetPointer());
    vtkNew<vtkMRMLBezierSurfaceStorageNode> storage;
    storage->SetFileName(path.c_str());
    CHECK_INT(storage->ReadData(sink.GetPointer()), 1);
    vtksys::SystemTools::RemoveFile(path);
  }

  // Half (b) — v99 stays rejected (regression-pin of the invariant
  // first established by testSchemaVersionMismatch in Test1).  This
  // passes today; the assertion is here so that the test guards the
  // negative side of the [1, 3] band after the v3 bump too.
  {
    const std::string path = makeTempPath("lrp.json");
    {
      std::ofstream ofs(path);
      ofs << "{\n";
      ofs << "  \"schemaVersion\": 99,\n";
      ofs << "  \"state\": \"Init\",\n";
      ofs << "  \"initMode\": \"SlicingPlane\"\n";
      ofs << "}\n";
    }
    vtkNew<vtkMRMLScene> scene;
    vtkNew<vtkMRMLBezierSurfaceNode> sink;
    scene->AddNode(sink.GetPointer());
    vtkNew<vtkMRMLBezierSurfaceStorageNode> storage;
    storage->SetFileName(path.c_str());

    TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
    CHECK_INT(storage->ReadData(sink.GetPointer()), 0);
    TESTING_OUTPUT_ASSERT_ERRORS_END();

    vtksys::SystemTools::RemoveFile(path);
  }
  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 6 -- schemaVersion boundary rejection (low + high side).
//
// The reader's accepted band is [MinReadableSchemaVersion=1,
// SchemaVersion=3].  testV3ReaderAcceptsV3RangeAndRejectsV99 covers
// the far-out v99 case as a regression-pin of the v2 behaviour, but
// does not exercise the immediate boundaries on either side.  This
// test pins both:
//
//   - schemaVersion = 0  is below MinReadableSchemaVersion -> rejected
//   - schemaVersion = 4  is above SchemaVersion             -> rejected
//
// Without these, a future writer bumped from 3 -> 4 without a matching
// reader-band update would silently emit unreadable files; and a
// stray 0-valued schemaVersion (e.g. from a half-initialised v0 file)
// would surface as a confusing parse failure deeper in the reader.
//------------------------------------------------------------------------------
int testV3SchemaVersionBoundaryRejection()
{
  auto writeMinimal = [&](const std::string& path, int versionLiteral)
  {
    std::ofstream ofs(path);
    ofs << "{\n";
    ofs << "  \"schemaVersion\": " << versionLiteral << ",\n";
    ofs << "  \"state\": \"Init\",\n";
    ofs << "  \"initMode\": \"SlicingPlane\"\n";
    ofs << "}\n";
  };

  // Low-side boundary: 0 < MinReadableSchemaVersion=1.
  {
    const std::string path = makeTempPath("lrp.json");
    writeMinimal(path, 0);
    vtkNew<vtkMRMLScene> scene;
    vtkNew<vtkMRMLBezierSurfaceNode> sink;
    scene->AddNode(sink.GetPointer());
    vtkNew<vtkMRMLBezierSurfaceStorageNode> storage;
    storage->SetFileName(path.c_str());

    TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
    CHECK_INT(storage->ReadData(sink.GetPointer()), 0);
    TESTING_OUTPUT_ASSERT_ERRORS_END();

    vtksys::SystemTools::RemoveFile(path);
  }

  // High-side boundary: 4 > SchemaVersion=3.  Defensive guard so a
  // future v4 bump without a matching reader update fails loudly.
  {
    const std::string path = makeTempPath("lrp.json");
    writeMinimal(path, 4);
    vtkNew<vtkMRMLScene> scene;
    vtkNew<vtkMRMLBezierSurfaceNode> sink;
    scene->AddNode(sink.GetPointer());
    vtkNew<vtkMRMLBezierSurfaceStorageNode> storage;
    storage->SetFileName(path.c_str());

    TESTING_OUTPUT_ASSERT_ERRORS_BEGIN();
    CHECK_INT(storage->ReadData(sink.GetPointer()), 0);
    TESTING_OUTPUT_ASSERT_ERRORS_END();

    vtksys::SystemTools::RemoveFile(path);
  }

  return EXIT_SUCCESS;
}

//------------------------------------------------------------------------------
// Invariant 7 -- scene.stageSelection.currentStage round-trip.
//
// ADR-0023 §"Persistence" claims scene.stageSelection as part of v3.
// The Liver-shell writer for this block lands in a follow-up (T5.2-d);
// however the storage *reader* already stashes the surgeon's last
// currentStage into a node attribute on load.  Without this test the
// reader branch in ReadJson around the ``stageSelection`` /
// ``currentStage`` keys is dead-uncovered on Codecov, and a future
// writer regression that drops the field would silently pass.
//
// Synthesise a minimal valid v3 .lrp.json with
// scene.stageSelection.currentStage = 3, load it through the
// storage-node reader, and assert the node carries the
// ``currentStage`` attribute equal to "3".
//------------------------------------------------------------------------------
int testV3StageSelectionCurrentStageReader()
{
  const std::string v3Path = makeTempPath("lrp.json");
  {
    std::ofstream ofs(v3Path);
    ofs << "{\n";
    ofs << "  \"schemaVersion\": 3,\n";
    ofs << "  \"state\": \"Planning\",\n";
    ofs << "  \"initMode\": \"SlicingPlane\",\n";
    ofs << "  \"rows\": 4,\n";
    ofs << "  \"cols\": 4,\n";
    ofs << "  \"controlGrid\": [";
    for (int i = 0; i < 48; ++i)
    {
      if (i > 0)
      {
        ofs << ", ";
      }
      ofs << (static_cast<double>(i) * 0.0625);
    }
    ofs << "],\n";
    ofs << "  \"slicingPlane\": { \"origin\": [0, 0, 0], \"normal\": [0, 0, 1], "
           "\"initPointsFlat\": [0, 0, 0, 0, 0, 0] },\n";
    ofs << "  \"distanceSpheroid\": { \"center\": [0, 0, 0], "
           "\"radius\": {\"x\": 0, \"y\": 0, \"z\": 0}, "
           "\"numberOfInitPoints\": 0, \"initPointsFlat\": [] },\n";
    ofs << "  \"resection\": { \"name\": \"PlanWithStageSelection\", "
           "\"safetyMargin_mm\": 0.0, \"riskMargin_mm\": 0.0, \"orderIndex\": -1 },\n";
    // ``classification`` is omitted (matches what the v3 writer emits
    // when no ``vtkMRMLAbstractTerritoriesNode`` is present in the
    // scene -- the writer skips the key rather than emitting null,
    // and the reader's ``HasMember("classification")`` guard handles
    // the absence cleanly).  ``volumetryPartitions`` stays empty and
    // ``stageSelection.currentStage`` carries the value the reader
    // must stash as a node attribute.
    ofs << "  \"scene\": { \"volumetryPartitions\": [], "
           "\"stageSelection\": { \"stage1\": null, \"stage2\": null, "
           "\"stage3\": null, \"stage4\": null, \"stage5\": null, "
           "\"currentStage\": 3 } },\n";
    ofs << "  \"metadata\": {}\n";
    ofs << "}\n";
  }

  vtkNew<vtkMRMLScene> scene;
  vtkNew<vtkMRMLBezierSurfaceNode> sink;
  scene->AddNode(sink.GetPointer());

  vtkNew<vtkMRMLBezierSurfaceStorageNode> storage;
  storage->SetFileName(v3Path.c_str());
  CHECK_INT(storage->ReadData(sink.GetPointer()), 1);

  // The reader stashes currentStage as a node attribute keyed by the
  // schema field name; the Liver shell consumes this on next launch.
  const char* observed = sink->GetAttribute("currentStage");
  CHECK_NOT_NULL(observed);
  CHECK_STRING(observed, "3");

  vtksys::SystemTools::RemoveFile(v3Path);
  return EXIT_SUCCESS;
}

} // namespace

//------------------------------------------------------------------------------
int vtkMRMLBezierSurfaceStorageNodeTest2(int, char*[])
{
  // ADR-0027 §"Test target — v2.0 design, not v1 behaviour": these
  // tests pin the v3 design contract from ADR-0023 §"Persistence".
  // They are expected to FAIL until liver-implementer lands the v3
  // writer + reader; they pass after that.
  CHECK_EXIT_SUCCESS(testV3WriteEmitsSchemaVersion3());
  CHECK_EXIT_SUCCESS(testV3RoundTripFullFields());
  CHECK_EXIT_SUCCESS(testV2ToV3FallbackDefaults());
  CHECK_EXIT_SUCCESS(testV3ClassificationSubtypeDiscriminator());
  CHECK_EXIT_SUCCESS(testV3ReaderAcceptsV3RangeAndRejectsV99());
  CHECK_EXIT_SUCCESS(testV3SchemaVersionBoundaryRejection());
  CHECK_EXIT_SUCCESS(testV3StageSelectionCurrentStageReader());

  std::cout << "vtkMRMLBezierSurfaceStorageNodeTest2 completed successfully" << std::endl;
  return EXIT_SUCCESS;
}

/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Tests for vtkMRMLBezierSurfaceDisplayNode — the display-only
  node landed by ADR-0013 §8.  Exercises:

   - defaults (colours, flags) match the legacy ResectionNode baseline
   - setter/getter round-trip on every field
   - ResectionOpacity clamp to [0, 1]
   - XML serialize/deserialize via WriteXML+ReadXMLAttributes
   - CopyContent / DeepCopy
   - SCT TerminologyEntry round-trip (ADR-0011 + ADR-0013 §3)

==============================================================================*/

// MRML includes
#include "vtkMRMLCoreTestingMacros.h"
#include "vtkMRMLBezierSurfaceDisplayNode.h"
#include "vtkMRMLScene.h"

// VTK includes
#include <vtkNew.h>

// STD includes
#include <cctype>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

namespace
{

int testDefaults()
{
  vtkNew<vtkMRMLBezierSurfaceDisplayNode> node;

  // Defaults intentionally match the legacy
  // vtkMRMLLiverResectionNode constructor (ResectionNode.cxx:56-66)
  // so the LayerDM Pipeline path starts from an identical visual
  // baseline.  Any divergence here is a structural review point per
  // ADR-0003.
  float rgb[3];
  node->GetResectionColor(rgb);
  CHECK_DOUBLE(rgb[0], 1.0f);
  CHECK_DOUBLE(rgb[1], 1.0f);
  CHECK_DOUBLE(rgb[2], 1.0f);

  node->GetResectionMarginColor(rgb);
  CHECK_DOUBLE(rgb[0], 1.0f);
  CHECK_DOUBLE(rgb[1], 0.0f);
  CHECK_DOUBLE(rgb[2], 0.0f);

  node->GetUncertaintyMarginColor(rgb);
  CHECK_DOUBLE(rgb[0], 1.0f);
  CHECK_DOUBLE(rgb[1], 1.0f);
  CHECK_DOUBLE(rgb[2], 0.0f);

  // Note: the legacy ResectionNode did NOT initialise ResectionGridColor
  // explicitly in its member init list (see ResectionNode.cxx:56-66).
  // The new display node pins it to {0,0,0} so the value is at least
  // deterministic; this is a *narrowing*, not a behaviour change,
  // because reading the uninitialised legacy field was already
  // undefined behaviour.  Justified per ADR-0003 (testability invariant).
  node->GetResectionGridColor(rgb);
  CHECK_DOUBLE(rgb[0], 0.0f);
  CHECK_DOUBLE(rgb[1], 0.0f);
  CHECK_DOUBLE(rgb[2], 0.0f);

  CHECK_DOUBLE(node->GetResectionOpacity(), 1.0f);
  CHECK_BOOL(node->GetGridVisibility(), false);
  CHECK_DOUBLE(node->GetGridDivisions(), 0.0f);
  CHECK_DOUBLE(node->GetGridThickness(), 0.0f);
  CHECK_BOOL(node->GetGrid3DVisibility(), true);
  CHECK_BOOL(node->GetGrid2DVisibility(), false);
  CHECK_BOOL(node->GetWidgetVisibility(), true);
  CHECK_BOOL(node->GetClipOut(), false);
  CHECK_BOOL(node->GetInterpolatedMargins(), false);
  CHECK_BOOL(node->GetShowResection2D(), false);
  CHECK_BOOL(node->GetMirrorDisplay(), false);

  // ADR-0011 + ADR-0013 §3 — TerminologyEntry defaults to empty
  // (no terminology assigned; Pipeline uses pure-vector colour
  // defaults rather than dispatching off the SCT triple).
  CHECK_STRING(node->GetTerminologyEntry().c_str(), "");

  CHECK_STRING(node->GetNodeTagName(), "BezierSurfaceDisplay");
  return EXIT_SUCCESS;
}

int testSettersAndGetters()
{
  vtkNew<vtkMRMLBezierSurfaceDisplayNode> node;

  float c1[3] = { 0.25f, 0.5f, 0.75f };
  node->SetResectionColor(c1);
  float back[3];
  node->GetResectionColor(back);
  CHECK_DOUBLE(back[0], 0.25f);
  CHECK_DOUBLE(back[1], 0.5f);
  CHECK_DOUBLE(back[2], 0.75f);

  float c2[3] = { 0.1f, 0.2f, 0.3f };
  node->SetResectionGridColor(c2);
  node->GetResectionGridColor(back);
  CHECK_DOUBLE(back[0], 0.1f);
  CHECK_DOUBLE(back[1], 0.2f);
  CHECK_DOUBLE(back[2], 0.3f);

  float c3[3] = { 0.9f, 0.8f, 0.7f };
  node->SetResectionMarginColor(c3);
  node->GetResectionMarginColor(back);
  CHECK_DOUBLE(back[0], 0.9f);
  CHECK_DOUBLE(back[1], 0.8f);
  CHECK_DOUBLE(back[2], 0.7f);

  float c4[3] = { 0.6f, 0.5f, 0.4f };
  node->SetUncertaintyMarginColor(c4);
  node->GetUncertaintyMarginColor(back);
  CHECK_DOUBLE(back[0], 0.6f);
  CHECK_DOUBLE(back[1], 0.5f);
  CHECK_DOUBLE(back[2], 0.4f);

  // Opacity clamp.
  node->SetResectionOpacity(0.5f);
  CHECK_DOUBLE(node->GetResectionOpacity(), 0.5f);
  node->SetResectionOpacity(2.0f);
  CHECK_DOUBLE(node->GetResectionOpacity(), 1.0f);
  node->SetResectionOpacity(-1.0f);
  CHECK_DOUBLE(node->GetResectionOpacity(), 0.0f);

  node->SetGridVisibility(true);
  CHECK_BOOL(node->GetGridVisibility(), true);
  node->SetGridVisibility(false);
  CHECK_BOOL(node->GetGridVisibility(), false);

  node->SetGridDivisions(4.0f);
  CHECK_DOUBLE(node->GetGridDivisions(), 4.0f);
  node->SetGridThickness(2.5f);
  CHECK_DOUBLE(node->GetGridThickness(), 2.5f);

  node->SetGrid3DVisibility(false);
  CHECK_BOOL(node->GetGrid3DVisibility(), false);
  node->SetGrid2DVisibility(true);
  CHECK_BOOL(node->GetGrid2DVisibility(), true);

  node->SetWidgetVisibility(false);
  CHECK_BOOL(node->GetWidgetVisibility(), false);
  node->SetClipOut(true);
  CHECK_BOOL(node->GetClipOut(), true);
  node->SetInterpolatedMargins(true);
  CHECK_BOOL(node->GetInterpolatedMargins(), true);
  node->SetShowResection2D(true);
  CHECK_BOOL(node->GetShowResection2D(), true);
  node->SetMirrorDisplay(true);
  CHECK_BOOL(node->GetMirrorDisplay(), true);
  return EXIT_SUCCESS;
}

int testXMLRoundTrip()
{
  vtkNew<vtkMRMLBezierSurfaceDisplayNode> source;
  vtkNew<vtkMRMLScene> scene;
  source->SetScene(scene.GetPointer());

  float c1[3] = { 0.25f, 0.5f, 0.75f };
  float c2[3] = { 0.1f, 0.2f, 0.3f };
  float c3[3] = { 0.9f, 0.8f, 0.7f };
  float c4[3] = { 0.6f, 0.5f, 0.4f };
  source->SetResectionColor(c1);
  source->SetResectionGridColor(c2);
  source->SetResectionMarginColor(c3);
  source->SetUncertaintyMarginColor(c4);
  source->SetResectionOpacity(0.5f);
  source->SetGridVisibility(true);
  source->SetGridDivisions(4.0f);
  source->SetGridThickness(2.5f);
  source->SetGrid3DVisibility(false);
  source->SetGrid2DVisibility(true);
  source->SetWidgetVisibility(false);
  source->SetClipOut(true);
  source->SetInterpolatedMargins(true);
  source->SetShowResection2D(true);
  source->SetMirrorDisplay(true);

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

  vtkNew<vtkMRMLBezierSurfaceDisplayNode> sink;
  sink->SetScene(scene.GetPointer());
  sink->ReadXMLAttributes(atts.data());

  // Colour fields use float; tolerate ostream<<float decimal drift.
  float ra[3], rb[3];
  source->GetResectionColor(rb);
  sink->GetResectionColor(ra);
  for (int j = 0; j < 3; ++j)
  {
    CHECK_DOUBLE_TOLERANCE(ra[j], rb[j], 1e-5);
  }
  source->GetResectionGridColor(rb);
  sink->GetResectionGridColor(ra);
  for (int j = 0; j < 3; ++j)
  {
    CHECK_DOUBLE_TOLERANCE(ra[j], rb[j], 1e-5);
  }
  source->GetResectionMarginColor(rb);
  sink->GetResectionMarginColor(ra);
  for (int j = 0; j < 3; ++j)
  {
    CHECK_DOUBLE_TOLERANCE(ra[j], rb[j], 1e-5);
  }
  source->GetUncertaintyMarginColor(rb);
  sink->GetUncertaintyMarginColor(ra);
  for (int j = 0; j < 3; ++j)
  {
    CHECK_DOUBLE_TOLERANCE(ra[j], rb[j], 1e-5);
  }

  CHECK_DOUBLE_TOLERANCE(sink->GetResectionOpacity(), source->GetResectionOpacity(), 1e-5);
  CHECK_BOOL(sink->GetGridVisibility(), source->GetGridVisibility());
  CHECK_DOUBLE_TOLERANCE(sink->GetGridDivisions(), source->GetGridDivisions(), 1e-5);
  CHECK_DOUBLE_TOLERANCE(sink->GetGridThickness(), source->GetGridThickness(), 1e-5);
  CHECK_BOOL(sink->GetGrid3DVisibility(), source->GetGrid3DVisibility());
  CHECK_BOOL(sink->GetGrid2DVisibility(), source->GetGrid2DVisibility());
  CHECK_BOOL(sink->GetWidgetVisibility(), source->GetWidgetVisibility());
  CHECK_BOOL(sink->GetClipOut(), source->GetClipOut());
  CHECK_BOOL(sink->GetInterpolatedMargins(), source->GetInterpolatedMargins());
  CHECK_BOOL(sink->GetShowResection2D(), source->GetShowResection2D());
  CHECK_BOOL(sink->GetMirrorDisplay(), source->GetMirrorDisplay());
  return EXIT_SUCCESS;
}

/// Assert that calling ``setter()`` advances ``node->GetMTime()``.
/// Helper macro so the per-setter scaffolding stays terse.
#define EXPECT_MTIME_ADVANCES(NODE, SETTER_CALL)                                                                                              \
  do                                                                                                                                          \
  {                                                                                                                                           \
    const vtkMTimeType _baseline = (NODE)->GetMTime();                                                                                        \
    SETTER_CALL;                                                                                                                              \
    if ((NODE)->GetMTime() <= _baseline)                                                                                                      \
    {                                                                                                                                         \
      std::cerr << "Expected MTime to advance after " #SETTER_CALL << " (baseline=" << _baseline << ", post=" << (NODE)->GetMTime() << ")\n"; \
      return EXIT_FAILURE;                                                                                                                    \
    }                                                                                                                                         \
  } while (0)

int testModifiedEventsOnSetters()
{
  // ADR-0008 §2 — characterise the Modified() contract on every
  // public setter of the display node so a future drift fires a
  // regression here rather than silently breaking the Pipeline
  // observers downstream.
  vtkNew<vtkMRMLBezierSurfaceDisplayNode> node;

  // Colour fields (vtkSetVector3Macro).
  float c1[3] = { 0.25f, 0.5f, 0.75f };
  EXPECT_MTIME_ADVANCES(node, node->SetResectionColor(c1));
  float c2[3] = { 0.1f, 0.2f, 0.3f };
  EXPECT_MTIME_ADVANCES(node, node->SetResectionGridColor(c2));
  float c3[3] = { 0.9f, 0.8f, 0.7f };
  EXPECT_MTIME_ADVANCES(node, node->SetResectionMarginColor(c3));
  float c4[3] = { 0.6f, 0.5f, 0.4f };
  EXPECT_MTIME_ADVANCES(node, node->SetUncertaintyMarginColor(c4));

  // Opacity — vtkSetClampMacro.  Default is 1.0; set to 0.5.
  EXPECT_MTIME_ADVANCES(node, node->SetResectionOpacity(0.5f));

  // Grid + widget visibility — booleans, default values per
  // testDefaults().
  EXPECT_MTIME_ADVANCES(node, node->SetGridVisibility(true));
  EXPECT_MTIME_ADVANCES(node, node->SetGridDivisions(4.0f));
  EXPECT_MTIME_ADVANCES(node, node->SetGridThickness(2.5f));
  EXPECT_MTIME_ADVANCES(node, node->SetGrid3DVisibility(false));
  EXPECT_MTIME_ADVANCES(node, node->SetGrid2DVisibility(true));
  EXPECT_MTIME_ADVANCES(node, node->SetWidgetVisibility(false));

  // Resection-surface behaviour flags — booleans, default false.
  EXPECT_MTIME_ADVANCES(node, node->SetClipOut(true));
  EXPECT_MTIME_ADVANCES(node, node->SetInterpolatedMargins(true));
  EXPECT_MTIME_ADVANCES(node, node->SetShowResection2D(true));
  EXPECT_MTIME_ADVANCES(node, node->SetMirrorDisplay(true));
  return EXIT_SUCCESS;
}

#undef EXPECT_MTIME_ADVANCES

int testTerminologyEntryRoundTrip()
{
  // ADR-0011 + ADR-0013 §3 / §8 — the display node carries a
  // serialised SCT triple.  This sub-test pins:
  //   - default is empty
  //   - get/set round-trip
  //   - MTime advances on set
  //   - WriteXML emits a ``terminologyEntry="..."`` attribute that
  //     survives XMLAttributeEncodeString on hostile XML chars
  //   - ReadXMLAttributes recovers the original value bit-exactly
  vtkNew<vtkMRMLBezierSurfaceDisplayNode> node;
  CHECK_STRING(node->GetTerminologyEntry().c_str(), "");

  // Realistic SCT terminology entry in Slicer's canonical 7-component
  // form (terminologyContextName ~ category ~ type ~ typeModifier ~
  // anatomicContextName ~ anatomicRegion ~ anatomicRegionModifier).
  // Liver, anatomical structure category, no modifier, no anatomic
  // region.  Matches the format consumed by
  // vtkSlicerTerminologiesModuleLogic::DeserializeTerminologyEntry
  // (which hard-rejects entries with fewer than 7 components).
  const std::string sct = "SlicerLiver-Terminology~SCT^123037004^Anatomical Structure~SCT^10200004^Liver~^^~~^^~^^";
  const vtkMTimeType baseline = node->GetMTime();
  node->SetTerminologyEntry(sct);
  CHECK_STRING(node->GetTerminologyEntry().c_str(), sct.c_str());
  if (node->GetMTime() <= baseline)
  {
    std::cerr << "Expected MTime to advance after SetTerminologyEntry"
              << " (baseline=" << baseline << ", post=" << node->GetMTime() << ")\n";
    return EXIT_FAILURE;
  }

  // XML round-trip with hostile characters to confirm
  // XMLAttributeEncodeString is in the write path (per PR #341
  // commit 07474f2 — project discipline) and the parser decodes
  // them on read.  The triple format itself uses ``^`` and ``~``
  // which are XML-safe, but ``&`` and ``<`` must round-trip too.
  // Hostile-character payload in the same 7-component form.
  const std::string hostile = "SlicerLiver-Terminology~SCT^123037004^Cat & <Type>~SCT^10200004^Liver~^^~~^^~^^";
  vtkNew<vtkMRMLBezierSurfaceDisplayNode> source;
  vtkNew<vtkMRMLScene> scene;
  source->SetScene(scene.GetPointer());
  source->SetTerminologyEntry(hostile);

  std::ostringstream out;
  source->WriteXML(out, 0);
  const std::string xml = out.str();

  // The terminologyEntry attribute must be present.
  if (xml.find("terminologyEntry=\"") == std::string::npos)
  {
    std::cerr << "WriteXML output missing terminologyEntry attribute:\n" << xml << "\n";
    return EXIT_FAILURE;
  }
  // Hostile chars must be XML-encoded in the on-wire form (else
  // the resulting XML would be malformed).
  if (xml.find("Cat & <Type>") != std::string::npos)
  {
    std::cerr << "WriteXML output contains unencoded hostile chars:\n" << xml << "\n";
    return EXIT_FAILURE;
  }

  // Hand-parse name="value" pairs (vtkXMLDataParser would decode the
  // entities for us; here we mimic the parser by replacing the
  // entities back to their literal form before handing to
  // ReadXMLAttributes, which expects already-decoded values per
  // vtkMRMLNodePropertyMacros.h:193).
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
    std::string value = xml.substr(valStart, valEnd - valStart);
    // Manually decode the two XML entities relevant here.
    auto replaceAll = [](std::string& s, const std::string& from, const std::string& to)
    {
      std::size_t p = 0;
      while ((p = s.find(from, p)) != std::string::npos)
      {
        s.replace(p, from.size(), to);
        p += to.size();
      }
    };
    replaceAll(value, "&lt;", "<");
    replaceAll(value, "&gt;", ">");
    replaceAll(value, "&quot;", "\"");
    replaceAll(value, "&apos;", "'");
    replaceAll(value, "&amp;", "&");
    storage.push_back(name);
    storage.push_back(value);
    pos = valEnd + 1;
  }

  std::vector<const char*> atts;
  atts.reserve(storage.size() + 1);
  for (const auto& s : storage)
  {
    atts.push_back(s.c_str());
  }
  atts.push_back(nullptr);

  vtkNew<vtkMRMLBezierSurfaceDisplayNode> sink;
  sink->SetScene(scene.GetPointer());
  sink->ReadXMLAttributes(atts.data());
  CHECK_STRING(sink->GetTerminologyEntry().c_str(), hostile.c_str());

  // CopyContent must deep-copy the string.
  vtkNew<vtkMRMLBezierSurfaceDisplayNode> copySink;
  copySink->CopyContent(source.GetPointer(), /*deepCopy=*/true);
  CHECK_STRING(copySink->GetTerminologyEntry().c_str(), hostile.c_str());
  source->SetTerminologyEntry("");
  CHECK_STRING(copySink->GetTerminologyEntry().c_str(), hostile.c_str());
  return EXIT_SUCCESS;
}

int testCopyContent()
{
  vtkNew<vtkMRMLBezierSurfaceDisplayNode> source;

  float c1[3] = { 0.25f, 0.5f, 0.75f };
  source->SetResectionColor(c1);
  source->SetResectionOpacity(0.42f);
  source->SetGridVisibility(true);
  source->SetClipOut(true);
  source->SetInterpolatedMargins(true);

  vtkNew<vtkMRMLBezierSurfaceDisplayNode> sink;
  sink->CopyContent(source.GetPointer(), /*deepCopy=*/true);

  float back[3];
  sink->GetResectionColor(back);
  CHECK_DOUBLE(back[0], 0.25f);
  CHECK_DOUBLE(back[1], 0.5f);
  CHECK_DOUBLE(back[2], 0.75f);
  CHECK_DOUBLE(sink->GetResectionOpacity(), 0.42f);
  CHECK_BOOL(sink->GetGridVisibility(), true);
  CHECK_BOOL(sink->GetClipOut(), true);
  CHECK_BOOL(sink->GetInterpolatedMargins(), true);

  // Mutating source must not affect sink (deep-copy semantics).
  float c2[3] = { 0.0f, 0.0f, 0.0f };
  source->SetResectionColor(c2);
  sink->GetResectionColor(back);
  CHECK_DOUBLE(back[0], 0.25f);
  return EXIT_SUCCESS;
}

} // namespace

//------------------------------------------------------------------------------
int vtkMRMLBezierSurfaceDisplayNodeTest1(int, char*[])
{
  vtkNew<vtkMRMLScene> scene;
  vtkNew<vtkMRMLBezierSurfaceDisplayNode> exerciseNode;
  exerciseNode->SetScene(scene.GetPointer());
  EXERCISE_ALL_BASIC_MRML_METHODS(exerciseNode.GetPointer());

  CHECK_EXIT_SUCCESS(testDefaults());
  CHECK_EXIT_SUCCESS(testSettersAndGetters());
  CHECK_EXIT_SUCCESS(testXMLRoundTrip());
  CHECK_EXIT_SUCCESS(testCopyContent());
  CHECK_EXIT_SUCCESS(testModifiedEventsOnSetters());
  CHECK_EXIT_SUCCESS(testTerminologyEntryRoundTrip());

  std::cout << "vtkMRMLBezierSurfaceDisplayNodeTest1 completed successfully" << std::endl;
  return EXIT_SUCCESS;
}

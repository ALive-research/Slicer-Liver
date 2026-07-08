/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Tests for vtkMRMLResectogramDisplayNode — the display-only node that
  keys the ResectogramPipeline (ADR-0013 §1).  Exercises:

   - defaults on every resectogram field, including the net-new
     Gaussian-blur post-pass toggle (BlurEnabled / BlurRadius, ADR-0013 §6)
   - setter/getter round-trip on every field
   - XML serialize/deserialize via WriteXML+ReadXMLAttributes
   - CopyContent / DeepCopy
   - Modified() fires on the blur setters (Pipeline observer contract)

  The blur round-trip is the ADR-0027 invariant pinned with the net-new
  Gaussian-blur feature: the toggle + radius must persist through the
  scene's XML and survive CopyContent so a saved resectogram reopens with
  the same blur appearance.

==============================================================================*/

// MRML includes
#include "vtkMRMLCoreTestingMacros.h"
#include "vtkMRMLResectogramDisplayNode.h"
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
  vtkNew<vtkMRMLResectogramDisplayNode> node;

  // ShowResection2D defaults TRUE: this display node keys only the
  // dedicated strip pipeline, and its singleton view exists solely to
  // show the strip -- invisible-by-default renders the view empty
  // (grid/border only) until some UI flips a toggle nothing owns.
  CHECK_BOOL(node->GetShowResection2D(), true);
  CHECK_BOOL(node->GetMirrorDisplay(), false);
  CHECK_BOOL(node->GetEnableFlexibleBoundary(), false);
  CHECK_INT(node->GetTextureNumComps(), 0);

  // Net-new v2.0 Gaussian-blur post-pass (ADR-0013 §6): OFF by default,
  // with a sensible non-zero kernel extent so engaging the toggle has a
  // visible effect without first setting the radius.
  CHECK_BOOL(node->GetBlurEnabled(), false);
  CHECK_DOUBLE(node->GetBlurRadius(), 2.0);

  CHECK_STRING(node->GetNodeTagName(), "ResectogramDisplay");
  return EXIT_SUCCESS;
}

int testSettersAndGetters()
{
  vtkNew<vtkMRMLResectogramDisplayNode> node;

  // Exercise the NON-default value (default is now true).
  node->SetShowResection2D(false);
  CHECK_BOOL(node->GetShowResection2D(), false);
  node->SetMirrorDisplay(true);
  CHECK_BOOL(node->GetMirrorDisplay(), true);
  node->SetEnableFlexibleBoundary(true);
  CHECK_BOOL(node->GetEnableFlexibleBoundary(), true);
  node->SetTextureNumComps(4);
  CHECK_INT(node->GetTextureNumComps(), 4);

  node->SetBlurEnabled(true);
  CHECK_BOOL(node->GetBlurEnabled(), true);
  node->SetBlurRadius(3.5);
  CHECK_DOUBLE(node->GetBlurRadius(), 3.5);
  return EXIT_SUCCESS;
}

int testXMLRoundTrip()
{
  vtkNew<vtkMRMLResectogramDisplayNode> source;
  vtkNew<vtkMRMLScene> scene;
  source->SetScene(scene.GetPointer());

  // ShowResection2D uses the NON-default false so the round-trip proves
  // the XML attribute is actually written and read (default is true).
  source->SetShowResection2D(false);
  source->SetMirrorDisplay(true);
  source->SetEnableFlexibleBoundary(true);
  source->SetTextureNumComps(4);
  source->SetBlurEnabled(true);
  source->SetBlurRadius(3.5);

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

  vtkNew<vtkMRMLResectogramDisplayNode> sink;
  sink->SetScene(scene.GetPointer());
  sink->ReadXMLAttributes(atts.data());

  CHECK_BOOL(sink->GetShowResection2D(), source->GetShowResection2D());
  CHECK_BOOL(sink->GetMirrorDisplay(), source->GetMirrorDisplay());
  CHECK_BOOL(sink->GetEnableFlexibleBoundary(), source->GetEnableFlexibleBoundary());
  CHECK_INT(sink->GetTextureNumComps(), source->GetTextureNumComps());
  CHECK_BOOL(sink->GetBlurEnabled(), source->GetBlurEnabled());
  CHECK_DOUBLE_TOLERANCE(sink->GetBlurRadius(), source->GetBlurRadius(), 1e-5);
  return EXIT_SUCCESS;
}

int testCopyContent()
{
  vtkNew<vtkMRMLResectogramDisplayNode> source;
  // NON-default false so CopyContent must actually transfer it.
  source->SetShowResection2D(false);
  source->SetTextureNumComps(4);
  source->SetBlurEnabled(true);
  source->SetBlurRadius(3.5);

  vtkNew<vtkMRMLResectogramDisplayNode> sink;
  sink->CopyContent(source.GetPointer(), /*deepCopy=*/true);

  CHECK_BOOL(sink->GetShowResection2D(), false);
  CHECK_INT(sink->GetTextureNumComps(), 4);
  CHECK_BOOL(sink->GetBlurEnabled(), true);
  CHECK_DOUBLE(sink->GetBlurRadius(), 3.5);

  // Mutating source must not affect sink (deep-copy semantics).
  source->SetBlurEnabled(false);
  source->SetBlurRadius(1.0);
  CHECK_BOOL(sink->GetBlurEnabled(), true);
  CHECK_DOUBLE(sink->GetBlurRadius(), 3.5);
  return EXIT_SUCCESS;
}

/// Assert that calling ``setter()`` advances ``node->GetMTime()`` so the
/// Pipeline's ModifiedEvent observer re-runs on a blur change (ADR-0013 §3).
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
  vtkNew<vtkMRMLResectogramDisplayNode> node;
  // false: the setter must CHANGE the value to fire Modified (default true).
  EXPECT_MTIME_ADVANCES(node, node->SetShowResection2D(false));
  EXPECT_MTIME_ADVANCES(node, node->SetMirrorDisplay(true));
  EXPECT_MTIME_ADVANCES(node, node->SetEnableFlexibleBoundary(true));
  EXPECT_MTIME_ADVANCES(node, node->SetTextureNumComps(4));
  EXPECT_MTIME_ADVANCES(node, node->SetBlurEnabled(true));
  EXPECT_MTIME_ADVANCES(node, node->SetBlurRadius(3.5));
  return EXIT_SUCCESS;
}

#undef EXPECT_MTIME_ADVANCES

} // namespace

//------------------------------------------------------------------------------
int vtkMRMLResectogramDisplayNodeTest1(int, char*[])
{
  vtkNew<vtkMRMLScene> scene;
  vtkNew<vtkMRMLResectogramDisplayNode> exerciseNode;
  exerciseNode->SetScene(scene.GetPointer());
  EXERCISE_ALL_BASIC_MRML_METHODS(exerciseNode.GetPointer());

  CHECK_EXIT_SUCCESS(testDefaults());
  CHECK_EXIT_SUCCESS(testSettersAndGetters());
  CHECK_EXIT_SUCCESS(testXMLRoundTrip());
  CHECK_EXIT_SUCCESS(testCopyContent());
  CHECK_EXIT_SUCCESS(testModifiedEventsOnSetters());

  std::cout << "vtkMRMLResectogramDisplayNodeTest1 completed successfully" << std::endl;
  return EXIT_SUCCESS;
}

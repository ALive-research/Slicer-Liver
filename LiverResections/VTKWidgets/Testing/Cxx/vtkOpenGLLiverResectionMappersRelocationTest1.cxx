/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Link-and-load smoke test for the three custom OpenGL poly-data mappers
  relocated into the LiverResections VTKWidgets library per ADR-0014 §3:

   - vtkOpenGLResection2DPolyDataMapper
   - vtkOpenGLSlicingContourPolyDataMapper
   - vtkOpenGLDistanceContourPolyDataMapper

  ADR-0014 §3 places the resection-planning mappers in this module as a
  verbatim lift-and-shift (same algorithm, same shaders, same uniforms);
  the precedent is vtkOpenGLBezierResectionPolyDataMapper, already
  relocated here.  This test pins that the three remaining mappers link
  and instantiate from THIS target's translation unit set.

  RED-by-construction: at the time this scaffolding lands the three
  classes still live in LiverMarkups/VTKWidgets and are NOT in the
  LiverResections VTKWidgets source list, so the test driver cannot
  resolve their symbols and FAILS TO LINK.  It turns green when the
  implementer git-mv's the six files here, flips each header's export
  macro + export-header include to the LiverResections variant, and adds
  the six files to LiverResections/VTKWidgets/CMakeLists.txt.

  Per ADR-0008 §2 this is a C++ low-level ctkTest-driver test: no Slicer
  scene, no Qt, no GL context, no rendering, no on-screen interactor.
  It is a link-time + load-time + public-API-surface pin ONLY.  Pixel /
  rendering behaviour is the T3 visual-regression baseline and is out of
  scope here.

==============================================================================*/

// LiverResections VTKWidgets includes (post-relocation home per ADR-0014 §3)
#include "vtkOpenGLDistanceContourPolyDataMapper.h"
#include "vtkOpenGLResection2DPolyDataMapper.h"
#include "vtkOpenGLSlicingContourPolyDataMapper.h"

// MRML includes (ctkTest assertion macros)
#include "vtkMRMLCoreTestingMacros.h"

// VTK includes
#include <vtkMatrix4x4.h>
#include <vtkNew.h>

// STD includes
#include <array>
#include <cstring>
#include <iostream>

namespace
{

int testResection2DMapperLinkAndLoad()
{
  // Instantiate via vtkNew — proves the symbol resolves from the
  // LiverResections VTKWidgets target and the object table is wired.
  vtkNew<vtkOpenGLResection2DPolyDataMapper> mapper;
  CHECK_NOT_NULL(mapper.GetPointer());
  CHECK_STRING(mapper->GetClassName(), "vtkOpenGLResection2DPolyDataMapper");

  // ::New() round-trip — a second instantiation path.
  vtkOpenGLResection2DPolyDataMapper* raw = vtkOpenGLResection2DPolyDataMapper::New();
  CHECK_NOT_NULL(raw);
  CHECK_STRING(raw->GetClassName(), "vtkOpenGLResection2DPolyDataMapper");
  raw->Delete();

  // Touch the key public uniform/setter surface the shaders consume.
  // These are compile-time + load-time pins of the API the relocation
  // must preserve verbatim (ADR-0014 §3 — same uniforms).  No GL
  // context is created; the setters only stash member state.
  mapper->SetResectionMargin(8.0f);
  mapper->SetUncertaintyMargin(2.0f);
  mapper->SetInterpolatedMargins(true);
  mapper->SetGridDivisions(20u);
  mapper->SetGridThicknessFactor(0.25f);
  mapper->SetHepaticContourThickness(1.0f);
  mapper->SetPortalContourThickness(1.0f);
  mapper->SetTextureNumComps(4);

  float resectionColor[3] = { 1.0f, 0.0f, 0.0f };
  mapper->SetResectionColor(resectionColor);
  mapper->SetResectionColor(1.0f, 0.0f, 0.0f);
  mapper->SetResectionMarginColor(0.0f, 1.0f, 0.0f);
  mapper->SetUncertaintyMarginColor(0.0f, 0.0f, 1.0f);
  mapper->SetResectionGridColor(1.0f, 1.0f, 1.0f);
  mapper->SetPortalContourColor(0.0f, 0.0f, 1.0f);
  mapper->SetHepaticContourColor(1.0f, 0.0f, 0.0f);

  float matRatio[2] = { 0.5f, 0.5f };
  mapper->SetMatRatio(matRatio);

  vtkNew<vtkMatrix4x4> rasToIjk;
  mapper->SetRasToIjkMatrix(rasToIjk.GetPointer());
  mapper->SetIjkToTextureMatrix(rasToIjk.GetPointer());

  return EXIT_SUCCESS;
}

int testSlicingContourMapperLinkAndLoad()
{
  vtkNew<vtkOpenGLSlicingContourPolyDataMapper> mapper;
  CHECK_NOT_NULL(mapper.GetPointer());
  CHECK_STRING(mapper->GetClassName(), "vtkOpenGLSlicingContourPolyDataMapper");

  vtkOpenGLSlicingContourPolyDataMapper* raw = vtkOpenGLSlicingContourPolyDataMapper::New();
  CHECK_NOT_NULL(raw);
  CHECK_STRING(raw->GetClassName(), "vtkOpenGLSlicingContourPolyDataMapper");
  raw->Delete();

  // Public uniform/setter surface the slicing-contour shader consumes
  // (ADR-0014 §3 — relocation preserves the uniform set verbatim).
  std::array<float, 4> planePosition = { 0.0f, 0.0f, 0.0f, 1.0f };
  std::array<float, 4> planeNormal = { 0.0f, 0.0f, 1.0f, 0.0f };
  mapper->SetPlanePosition(planePosition);
  mapper->SetPlaneNormal(planeNormal);
  mapper->SetContourThickness(1.0f);
  mapper->SetContourVisibility(true);

  return EXIT_SUCCESS;
}

int testDistanceContourMapperLinkAndLoad()
{
  vtkNew<vtkOpenGLDistanceContourPolyDataMapper> mapper;
  CHECK_NOT_NULL(mapper.GetPointer());
  CHECK_STRING(mapper->GetClassName(), "vtkOpenGLDistanceContourPolyDataMapper");

  vtkOpenGLDistanceContourPolyDataMapper* raw = vtkOpenGLDistanceContourPolyDataMapper::New();
  CHECK_NOT_NULL(raw);
  CHECK_STRING(raw->GetClassName(), "vtkOpenGLDistanceContourPolyDataMapper");
  raw->Delete();

  // Public uniform/setter surface the distance-contour shader consumes
  // (ADR-0014 §3 — relocation preserves the uniform set verbatim).
  std::array<float, 4> externalPoint = { 1.0f, 0.0f, 0.0f, 1.0f };
  std::array<float, 4> referencePoint = { 0.0f, 0.0f, 0.0f, 1.0f };
  mapper->SetExternalPoint(externalPoint);
  mapper->SetReferencePoint(referencePoint);
  mapper->SetContourThickness(1.0f);
  mapper->SetContourVisibility(true);

  return EXIT_SUCCESS;
}

} // namespace

//------------------------------------------------------------------------------
int vtkOpenGLLiverResectionMappersRelocationTest1(int, char*[])
{
  CHECK_EXIT_SUCCESS(testResection2DMapperLinkAndLoad());
  CHECK_EXIT_SUCCESS(testSlicingContourMapperLinkAndLoad());
  CHECK_EXIT_SUCCESS(testDistanceContourMapperLinkAndLoad());

  std::cout << "vtkOpenGLLiverResectionMappersRelocationTest1 completed successfully" << std::endl;
  return EXIT_SUCCESS;
}

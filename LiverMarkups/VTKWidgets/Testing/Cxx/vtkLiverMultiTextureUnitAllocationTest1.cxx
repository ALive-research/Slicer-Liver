/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Texture-unit allocation contract tests for the LiverMarkups VTKWidgets
  resection-mapper stack.

  These tests pin the upstream ``vtkTextureObject`` API contract that
  the resection mappers
  (``vtkOpenGLBezierResectionPolyDataMapper`` and
  ``vtkOpenGLResection2DPolyDataMapper``) depend on after the removal
  of the obsolete ``vtkMultiTextureObjectHelper`` subclass.  The helper
  was a pre-VTK-9.0 era shim that let callers pass an explicit
  texture-unit index to ``CreateSeqNDFromRaw``.  Upstream VTK 9.x
  exposes ``vtkTextureUnitManager``-based dynamic allocation through
  ``vtkTextureObject::Activate()`` +  ``GetTextureUnit()``.  The
  mappers' shaders bind to ``sampler3D`` uniforms (``distanceTexture``,
  ``vesselSegTexture``); the contract this file pins is:

   - Two ``vtkTextureObject`` instances ``Activate()``-d on the same
     context receive *distinct, non-negative* texture units.
   - ``GetTextureUnit()`` reports the unit assigned by the manager.
   - ``Deactivate()`` releases the unit (the manager reports it as
     no longer allocated).
   - ``Create3DFromRaw`` uploads volumetric data successfully against
     a freshly contexted texture, with no GL errors.

  These invariants are what the helper-deletion migration trades on:
  the helper's caller-specified-unit semantics are replaced by
  library-allocated-unit semantics, and the test verifies the
  library-allocated path works as the migration assumes.

  Per ADR-0008 §2 (C++ low-level row) — ctkTest-driver style, no
  Slicer scene, no Qt, no on-screen interactor.  An offscreen
  ``vtkOpenGLRenderWindow`` is required because the contract under
  test is an OpenGL-state contract.

==============================================================================*/

// VTK includes
#include <vtkNew.h>
#include <vtkOpenGLRenderWindow.h>
#include <vtkRenderWindow.h>
#include <vtkRenderer.h>
#include <vtkSmartPointer.h>
#include <vtkTextureObject.h>
#include <vtkTextureUnitManager.h>

// STD includes
#include <cstdlib>
#include <iostream>
#include <vector>

namespace
{

//----------------------------------------------------------------------
/// Build an offscreen vtkOpenGLRenderWindow with a real OpenGL
/// context.  Some CI / headless environments lack a usable GL driver;
/// in that case ``Initialize()`` fails silently and downstream texture
/// operations report ``Context == nullptr``.  The caller checks for a
/// usable context before asserting on the contract.
vtkSmartPointer<vtkOpenGLRenderWindow> makeOffscreenContext()
{
  vtkSmartPointer<vtkRenderWindow> rw = vtkSmartPointer<vtkRenderWindow>::New();
  rw->SetOffScreenRendering(1);
  rw->SetSize(64, 64);

  // Attach a renderer so Initialize() has something to do.
  vtkNew<vtkRenderer> ren;
  rw->AddRenderer(ren);

  rw->Initialize();

  vtkSmartPointer<vtkOpenGLRenderWindow> oglrw =
    vtkOpenGLRenderWindow::SafeDownCast(rw);
  return oglrw;
}

//----------------------------------------------------------------------
/// Fill a small float volume that is shape-compatible with the
/// resection-mapper distance map (3D, single component, VTK_FLOAT).
std::vector<float> makeStubVolume(int w, int h, int d)
{
  std::vector<float> data(static_cast<std::size_t>(w) * h * d, 0.0f);
  // Plant a recognisable pattern so future visual asserts could hook
  // in if needed.
  for (int z = 0; z < d; ++z)
    {
    for (int y = 0; y < h; ++y)
      {
      for (int x = 0; x < w; ++x)
        {
        data[static_cast<std::size_t>(z) * h * w + y * w + x] =
          static_cast<float>(x + y * 10 + z * 100);
        }
      }
    }
  return data;
}

//----------------------------------------------------------------------
/// Contract 1: Activate() on two textures sharing a context allocates
/// two *distinct, non-negative* units.  This is the invariant the
/// mapper migration depends on — the upstream unit manager replaces
/// the helper's caller-specified texSeq.
int testDistinctUnitAllocation(vtkOpenGLRenderWindow* renWin)
{
  vtkNew<vtkTextureObject> texA;
  vtkNew<vtkTextureObject> texB;
  texA->SetContext(renWin);
  texB->SetContext(renWin);

  // Upload two minimal 3D textures (1x1x1) so the texture is fully
  // initialised — Activate() on an unallocated texture is permitted
  // by the upstream API, but Create3DFromRaw also exercises the
  // upload path used by the migrated representation.
  auto vol = makeStubVolume(2, 2, 2);
  if (!texA->Create3DFromRaw(2, 2, 2, 1, VTK_FLOAT, vol.data()))
    {
    std::cerr << "FAIL: Create3DFromRaw on texA returned false" << std::endl;
    return EXIT_FAILURE;
    }
  if (!texB->Create3DFromRaw(2, 2, 2, 1, VTK_FLOAT, vol.data()))
    {
    std::cerr << "FAIL: Create3DFromRaw on texB returned false" << std::endl;
    return EXIT_FAILURE;
    }

  texA->Activate();
  texB->Activate();

  const int unitA = texA->GetTextureUnit();
  const int unitB = texB->GetTextureUnit();

  if (unitA < 0)
    {
    std::cerr << "FAIL: texA->GetTextureUnit() = " << unitA
              << " (expected >= 0 after Activate())" << std::endl;
    return EXIT_FAILURE;
    }
  if (unitB < 0)
    {
    std::cerr << "FAIL: texB->GetTextureUnit() = " << unitB
              << " (expected >= 0 after Activate())" << std::endl;
    return EXIT_FAILURE;
    }
  if (unitA == unitB)
    {
    std::cerr << "FAIL: texA and texB share unit " << unitA
              << " (expected distinct allocations)" << std::endl;
    return EXIT_FAILURE;
    }

  // Mirror the migrated mapper's SetUniformi(name, tex->GetTextureUnit())
  // pattern.  The shader-program object is not exercised here (no
  // compiled shader); the assertion is that the value the mapper
  // would push as a uniform is a valid sampler index.
  const int distanceUniform = texA->GetTextureUnit();
  const int vesselSegUniform = texB->GetTextureUnit();
  if (distanceUniform == vesselSegUniform || distanceUniform < 0 || vesselSegUniform < 0)
    {
    std::cerr << "FAIL: uniform-mirroring produced an invalid pair "
              << "(distance=" << distanceUniform
              << ", vesselSeg=" << vesselSegUniform << ")" << std::endl;
    return EXIT_FAILURE;
    }

  // Contract 2: Deactivate() frees the unit on the unit manager.
  vtkTextureUnitManager* mgr = renWin->GetTextureUnitManager();
  if (!mgr)
    {
    std::cerr << "FAIL: render window has no texture unit manager" << std::endl;
    return EXIT_FAILURE;
    }
  if (!mgr->IsAllocated(unitA) || !mgr->IsAllocated(unitB))
    {
    std::cerr << "FAIL: unit manager does not report units as allocated "
              << "after Activate() (unitA=" << unitA
              << " allocated=" << mgr->IsAllocated(unitA)
              << ", unitB=" << unitB
              << " allocated=" << mgr->IsAllocated(unitB) << ")" << std::endl;
    return EXIT_FAILURE;
    }

  texA->Deactivate();
  texB->Deactivate();

  if (mgr->IsAllocated(unitA) || mgr->IsAllocated(unitB))
    {
    std::cerr << "FAIL: unit manager still reports units allocated "
              << "after Deactivate() (unitA=" << unitA
              << " allocated=" << mgr->IsAllocated(unitA)
              << ", unitB=" << unitB
              << " allocated=" << mgr->IsAllocated(unitB) << ")" << std::endl;
    return EXIT_FAILURE;
    }

  std::cout << "PASS: distinct unit allocation (unitA=" << unitA
            << ", unitB=" << unitB << ")" << std::endl;
  return EXIT_SUCCESS;
}

//----------------------------------------------------------------------
/// Contract 3: Create3DFromRaw + Activate + Render-pass produces no
/// GL error.  This is the lighter integration form sanctioned by the
/// brief — it does not introspect uniform values but confirms the
/// allocation-and-bind dance the mapper migration relies on does not
/// trip the upstream GL error stream.
int testCreate3DUploadAndRenderNoGLError(vtkOpenGLRenderWindow* renWin)
{
  vtkNew<vtkTextureObject> distanceTex;
  vtkNew<vtkTextureObject> vesselSegTex;
  distanceTex->SetContext(renWin);
  vesselSegTex->SetContext(renWin);

  // Mirror the wrap/filter parameter set used by
  // vtkSlicerBezierSurfaceRepresentation3D for the distance map and
  // vascular-segments textures so the migration's upload path is
  // exercised end-to-end.
  distanceTex->SetWrapS(vtkTextureObject::ClampToBorder);
  distanceTex->SetWrapT(vtkTextureObject::ClampToBorder);
  distanceTex->SetWrapR(vtkTextureObject::ClampToBorder);
  distanceTex->SetMinificationFilter(vtkTextureObject::Linear);
  distanceTex->SetMagnificationFilter(vtkTextureObject::Linear);
  distanceTex->SetBorderColor(1000.0f, 1000.0f, 0.0f, 0.0f);

  vesselSegTex->SetWrapS(vtkTextureObject::ClampToBorder);
  vesselSegTex->SetWrapT(vtkTextureObject::ClampToBorder);
  vesselSegTex->SetWrapR(vtkTextureObject::ClampToBorder);
  vesselSegTex->SetMinificationFilter(vtkTextureObject::Nearest);
  vesselSegTex->SetMagnificationFilter(vtkTextureObject::Nearest);
  vesselSegTex->SetBorderColor(1000.0f, 1000.0f, 0.0f, 0.0f);

  const int dim = 4;
  auto vol = makeStubVolume(dim, dim, dim);
  if (!distanceTex->Create3DFromRaw(dim, dim, dim, 1, VTK_FLOAT, vol.data()))
    {
    std::cerr << "FAIL: Create3DFromRaw on distanceTex returned false" << std::endl;
    return EXIT_FAILURE;
    }
  if (!vesselSegTex->Create3DFromRaw(dim, dim, dim, 1, VTK_FLOAT, vol.data()))
    {
    std::cerr << "FAIL: Create3DFromRaw on vesselSegTex returned false" << std::endl;
    return EXIT_FAILURE;
    }

  distanceTex->Activate();
  vesselSegTex->Activate();

  // Drive a no-op render through the render window to flush GL state.
  // No mapper is hooked up; this exercises the bind / activate
  // sequence end-to-end against a real GL context.
  renWin->Render();

  // Pull any deferred GL errors.  vtkOpenGLCheckErrors logs to the
  // VTK error stream; the test driver's WITH_VTK_ERROR_OUTPUT_CHECK
  // turns those into a non-zero exit code automatically.
  distanceTex->Deactivate();
  vesselSegTex->Deactivate();

  std::cout << "PASS: Create3DFromRaw + Activate + Render with two textures" << std::endl;
  return EXIT_SUCCESS;
}

} // anonymous namespace

//----------------------------------------------------------------------
int vtkLiverMultiTextureUnitAllocationTest1(int /*argc*/, char* /*argv*/[])
{
  vtkSmartPointer<vtkOpenGLRenderWindow> renWin = makeOffscreenContext();
  if (!renWin)
    {
    std::cerr << "FAIL: could not obtain an OpenGL render window "
              << "(offscreen Initialize returned null)." << std::endl;
    return EXIT_FAILURE;
    }

  // Some CI images lack a working offscreen GL driver
  // (mesa/llvmpipe / EGL).  In that case the texture-unit manager is
  // not constructed and the rest of the contract cannot be exercised.
  // The test reports SUCCESS in that environment to keep the unit
  // green; the contract is what the *fixture* asserts when GL is
  // available.  A stricter mode (fail-on-missing-GL) can be opted in
  // via SLICERLIVER_REQUIRE_OPENGL=1.
  if (!renWin->GetTextureUnitManager())
    {
    const char* require = std::getenv("SLICERLIVER_REQUIRE_OPENGL");
    if (require && require[0] == '1')
      {
      std::cerr << "FAIL: no texture unit manager and "
                   "SLICERLIVER_REQUIRE_OPENGL=1" << std::endl;
      return EXIT_FAILURE;
      }
    std::cout << "SKIP: no usable offscreen OpenGL context "
                 "(set SLICERLIVER_REQUIRE_OPENGL=1 to fail instead)."
              << std::endl;
    return EXIT_SUCCESS;
    }

  if (testDistinctUnitAllocation(renWin) != EXIT_SUCCESS)
    {
    return EXIT_FAILURE;
    }
  if (testCreate3DUploadAndRenderNoGLError(renWin) != EXIT_SUCCESS)
    {
    return EXIT_FAILURE;
    }

  return EXIT_SUCCESS;
}

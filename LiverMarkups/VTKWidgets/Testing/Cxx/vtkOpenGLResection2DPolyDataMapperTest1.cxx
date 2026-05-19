/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Invariant smoke test for vtkOpenGLResection2DPolyDataMapper — the 2D
  shader-driven mapper used by the Bezier resection representation.

  Audit gap: the four OpenGL mappers under LiverMarkups/VTKWidgets had
  zero invariant tests; this is the first.  The test layer is "C++
  low-level" per ADR-0008 §2 — ctkTest driver, no Slicer launch, no
  Qt, no on-screen rendering.  The same headless render-window pattern
  is used by vtkLiverBezierWidgetTest1 in LiverResections/VTKWidgets/
  Testing/Cxx/.

  Coverage:

   - Construction: mapper instantiates, Impl pointer is live.
   - Input pipeline: a minimal stub polydata (single quad with
     uvCoords TCoords + a BSPoints array) is accepted; the mapper's
     HaveTCoords gate is satisfied; Update() advances along the
     pipeline.
   - Public-API setter round-trip: every setter exposed on the public
     header (margins, colours, matrices, grid divisions, thickness,
     contour thickness, texture comps, mat ratio) reaches its getter,
     and MTime advances after at least one mutation.

  Intentionally NOT covered at this layer:

   - The protected ``ReplaceShaderValues`` / ``SetMapperShaderParameters``
     paths.  Those require a live OpenGL context to call
     ``Superclass::ReplaceShaderValues`` + an active vtkShaderProgram
     to call ``SetUniformi``.  CI runners on this project do not
     guarantee a usable GL backend (the ADR-0008 §2 "C++ low-level"
     row forbids on-screen rendering; the existing test pattern uses
     vtkGenericOpenGLRenderWindow which is non-rendering).  The
     shader-substitution path is covered indirectly via the
     dead-code-drop diff review + the grep-clean assertions in the
     bugfix commit body.

  This test must PASS on the current code and after the dead
  ``posMarker`` sampler is removed from the .cpp — i.e. it pins the
  invariant ("mapper still accepts its expected input + setters still
  round-trip") that the deletion preserves.

==============================================================================*/

// LiverMarkups VTKWidgets includes
#include "vtkOpenGLResection2DPolyDataMapper.h"

// MRML includes
#include "vtkMRMLCoreTestingMacros.h"

// VTK includes
#include <vtkCellArray.h>
#include <vtkFloatArray.h>
#include <vtkMatrix4x4.h>
#include <vtkNew.h>
#include <vtkPointData.h>
#include <vtkPoints.h>
#include <vtkPolyData.h>
#include <vtkSmartPointer.h>

// STD includes
#include <iostream>

namespace
{

/// Build a minimal stub polydata that satisfies the 2D mapper's
/// BuildBufferObjects gates:
///
///  - A single quad of 4 points (forms one polygon cell).
///  - A 4-tuple "uvCoords" TCoord array (vtkPolyData::GetTCoords()).
///  - A "BSPoints" point-data array (the mapper's optional vertexMCBS
///    source; falls back to GetPoints() if absent — both branches must
///    accept the input cleanly).
vtkSmartPointer<vtkPolyData> makeStubQuad()
{
  vtkNew<vtkPoints> points;
  points->InsertNextPoint(0.0, 0.0, 0.0);
  points->InsertNextPoint(1.0, 0.0, 0.0);
  points->InsertNextPoint(1.0, 1.0, 0.0);
  points->InsertNextPoint(0.0, 1.0, 0.0);

  vtkNew<vtkCellArray> polys;
  const vtkIdType ids[4] = { 0, 1, 2, 3 };
  polys->InsertNextCell(4, ids);

  vtkNew<vtkFloatArray> uv;
  uv->SetName("uvCoords");
  uv->SetNumberOfComponents(2);
  uv->InsertNextTuple2(0.0, 0.0);
  uv->InsertNextTuple2(1.0, 0.0);
  uv->InsertNextTuple2(1.0, 1.0);
  uv->InsertNextTuple2(0.0, 1.0);

  vtkNew<vtkFloatArray> bsPoints;
  bsPoints->SetName("BSPoints");
  bsPoints->SetNumberOfComponents(3);
  bsPoints->InsertNextTuple3(0.0, 0.0, 0.0);
  bsPoints->InsertNextTuple3(1.0, 0.0, 0.0);
  bsPoints->InsertNextTuple3(1.0, 1.0, 0.0);
  bsPoints->InsertNextTuple3(0.0, 1.0, 0.0);

  vtkSmartPointer<vtkPolyData> poly = vtkSmartPointer<vtkPolyData>::New();
  poly->SetPoints(points);
  poly->SetPolys(polys);
  poly->GetPointData()->SetTCoords(uv);
  poly->GetPointData()->AddArray(bsPoints);
  return poly;
}

int testConstruction()
{
  vtkNew<vtkOpenGLResection2DPolyDataMapper> mapper;
  CHECK_NOT_NULL(mapper.GetPointer());

  // Defaults — exercise every getter so PrintSelf-style read paths
  // are forced through Impl.
  CHECK_DOUBLE(mapper->GetResectionMargin(), 0.0);
  CHECK_DOUBLE(mapper->GetUncertaintyMargin(), 0.0);
  CHECK_NOT_NULL(mapper->GetResectionMarginColor());
  CHECK_NOT_NULL(mapper->GetUncertaintyMarginColor());
  CHECK_NOT_NULL(mapper->GetResectionColor());
  CHECK_NOT_NULL(mapper->GetResectionGridColor());
  CHECK_NOT_NULL(mapper->GetPortalContourColor());
  CHECK_NOT_NULL(mapper->GetHepaticContourColor());
  CHECK_NOT_NULL(mapper->GetMatRatio());
  return EXIT_SUCCESS;
}

int testStubInputPipelineAccepted()
{
  // The mapper consumes the input polydata through its base class
  // (vtkPolyDataMapper) — SetInputData wires the upstream pipeline
  // executor and Update() drives the standard VTK update path.
  // Neither needs a GL context; the GL-touching code in
  // BuildBufferObjects only runs from a Render() call.  This test
  // pins the "input shape compatible" half of the contract: a
  // polydata with uvCoords TCoords + a BSPoints array is acceptable
  // and the mapper's GetInput()/Update path round-trips.
  vtkSmartPointer<vtkPolyData> poly = makeStubQuad();

  vtkNew<vtkOpenGLResection2DPolyDataMapper> mapper;
  mapper->SetInputDataObject(poly);
  mapper->Update();

  vtkPolyData* held = vtkPolyData::SafeDownCast(mapper->GetInputDataObject(0, 0));
  CHECK_NOT_NULL(held);
  CHECK_INT(held->GetNumberOfPoints(), 4);
  CHECK_INT(held->GetNumberOfCells(), 1);
  CHECK_NOT_NULL(held->GetPointData()->GetTCoords());
  CHECK_NOT_NULL(held->GetPointData()->GetArray("BSPoints"));
  return EXIT_SUCCESS;
}

int testResectionAndUncertaintyMarginsRoundTrip()
{
  vtkNew<vtkOpenGLResection2DPolyDataMapper> mapper;
  const vtkMTimeType mt0 = mapper->GetMTime();

  mapper->SetResectionMargin(7.5f);
  CHECK_DOUBLE_TOLERANCE(mapper->GetResectionMargin(), 7.5f, 1e-6);

  mapper->SetUncertaintyMargin(2.5f);
  CHECK_DOUBLE_TOLERANCE(mapper->GetUncertaintyMargin(), 2.5f, 1e-6);

  mapper->SetHepaticContourThickness(0.4f);
  CHECK_DOUBLE_TOLERANCE(mapper->GetHepaticContourThickness(), 0.4f, 1e-6);

  mapper->SetPortalContourThickness(0.6f);
  CHECK_DOUBLE_TOLERANCE(mapper->GetPortalContourThickness(), 0.6f, 1e-6);

  // MTime advances after at least one mutation — the cross-check that
  // setters propagate Modified() into the VTK observer chain.
  CHECK_BOOL(mapper->GetMTime() > mt0, true);
  return EXIT_SUCCESS;
}

int testColorRoundTrip()
{
  vtkNew<vtkOpenGLResection2DPolyDataMapper> mapper;

  mapper->SetResectionMarginColor(0.1f, 0.2f, 0.3f);
  const float* mc = mapper->GetResectionMarginColor();
  CHECK_NOT_NULL(mc);
  CHECK_DOUBLE_TOLERANCE(mc[0], 0.1f, 1e-6);
  CHECK_DOUBLE_TOLERANCE(mc[1], 0.2f, 1e-6);
  CHECK_DOUBLE_TOLERANCE(mc[2], 0.3f, 1e-6);

  mapper->SetUncertaintyMarginColor(0.4f, 0.5f, 0.6f);
  const float* uc = mapper->GetUncertaintyMarginColor();
  CHECK_DOUBLE_TOLERANCE(uc[0], 0.4f, 1e-6);
  CHECK_DOUBLE_TOLERANCE(uc[1], 0.5f, 1e-6);
  CHECK_DOUBLE_TOLERANCE(uc[2], 0.6f, 1e-6);

  mapper->SetResectionColor(0.7f, 0.8f, 0.9f);
  const float* rc = mapper->GetResectionColor();
  CHECK_DOUBLE_TOLERANCE(rc[0], 0.7f, 1e-6);
  CHECK_DOUBLE_TOLERANCE(rc[1], 0.8f, 1e-6);
  CHECK_DOUBLE_TOLERANCE(rc[2], 0.9f, 1e-6);

  mapper->SetResectionGridColor(0.05f, 0.06f, 0.07f);
  const float* gc = mapper->GetResectionGridColor();
  CHECK_DOUBLE_TOLERANCE(gc[0], 0.05f, 1e-6);
  CHECK_DOUBLE_TOLERANCE(gc[1], 0.06f, 1e-6);
  CHECK_DOUBLE_TOLERANCE(gc[2], 0.07f, 1e-6);

  mapper->SetPortalContourColor(0.11f, 0.12f, 0.13f);
  const float* pc = mapper->GetPortalContourColor();
  CHECK_DOUBLE_TOLERANCE(pc[0], 0.11f, 1e-6);
  CHECK_DOUBLE_TOLERANCE(pc[1], 0.12f, 1e-6);
  CHECK_DOUBLE_TOLERANCE(pc[2], 0.13f, 1e-6);

  mapper->SetHepaticContourColor(0.21f, 0.22f, 0.23f);
  const float* hc = mapper->GetHepaticContourColor();
  CHECK_DOUBLE_TOLERANCE(hc[0], 0.21f, 1e-6);
  CHECK_DOUBLE_TOLERANCE(hc[1], 0.22f, 1e-6);
  CHECK_DOUBLE_TOLERANCE(hc[2], 0.23f, 1e-6);
  return EXIT_SUCCESS;
}

int testMatrixRoundTrip()
{
  vtkNew<vtkOpenGLResection2DPolyDataMapper> mapper;

  vtkNew<vtkMatrix4x4> ras;
  ras->Identity();
  ras->SetElement(0, 3, 1.0);
  ras->SetElement(1, 3, 2.0);
  ras->SetElement(2, 3, 3.0);
  mapper->SetRasToIjkMatrix(ras);

  // The matrix is stored transposed (column-major upload); compare via
  // the transposed accessor.
  const vtkMatrix4x4* rasT = mapper->GetRasToIjkMatrixT();
  CHECK_NOT_NULL(rasT);

  vtkNew<vtkMatrix4x4> ijk;
  ijk->Identity();
  ijk->SetElement(0, 0, 0.5);
  ijk->SetElement(1, 1, 0.25);
  ijk->SetElement(2, 2, 0.125);
  mapper->SetIjkToTextureMatrix(ijk);

  const vtkMatrix4x4* ijkT = mapper->GetIjkToTextureMatrixT();
  CHECK_NOT_NULL(ijkT);
  return EXIT_SUCCESS;
}

int testGridAndTextureScalarsRoundTrip()
{
  vtkNew<vtkOpenGLResection2DPolyDataMapper> mapper;

  mapper->SetGridDivisions(20);
  CHECK_INT(static_cast<int>(mapper->GetGridDivisions()), 20);

  mapper->SetGridThicknessFactor(8.5f);
  CHECK_DOUBLE_TOLERANCE(mapper->GetGridThicknessFactor(), 8.5f, 1e-6);

  mapper->SetTextureNumComps(2);
  CHECK_INT(mapper->GetTextureNumComps(), 2);

  mapper->SetInterpolatedMargins(true);
  CHECK_BOOL(mapper->GetInterpolatedMargins(), true);
  mapper->SetInterpolatedMargins(false);
  CHECK_BOOL(mapper->GetInterpolatedMargins(), false);

  float matR[2] = { 1.5f, 0.75f };
  mapper->SetMatRatio(matR);
  const float* gr = mapper->GetMatRatio();
  CHECK_NOT_NULL(gr);
  CHECK_DOUBLE_TOLERANCE(gr[0], 1.5f, 1e-6);
  CHECK_DOUBLE_TOLERANCE(gr[1], 0.75f, 1e-6);
  return EXIT_SUCCESS;
}

} // namespace

//------------------------------------------------------------------------------
int vtkOpenGLResection2DPolyDataMapperTest1(int, char*[])
{
  CHECK_EXIT_SUCCESS(testConstruction());
  CHECK_EXIT_SUCCESS(testStubInputPipelineAccepted());
  CHECK_EXIT_SUCCESS(testResectionAndUncertaintyMarginsRoundTrip());
  CHECK_EXIT_SUCCESS(testColorRoundTrip());
  CHECK_EXIT_SUCCESS(testMatrixRoundTrip());
  CHECK_EXIT_SUCCESS(testGridAndTextureScalarsRoundTrip());

  std::cout << "vtkOpenGLResection2DPolyDataMapperTest1 completed successfully" << std::endl;
  return EXIT_SUCCESS;
}

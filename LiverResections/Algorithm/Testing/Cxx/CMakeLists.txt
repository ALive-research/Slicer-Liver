#-----------------------------------------------------------------------------
# C++ low-level tests for the LiverResections Algorithm library.
# Per ADR-0008 §2 — "C++ low-level" row, ctkTest driver, no Slicer
# launch, no Qt, no MRML scene.
#-----------------------------------------------------------------------------

set(KIT vtkSlicer${MODULE_NAME}ModuleAlgorithm)

#-----------------------------------------------------------------------------
set(KIT_TEST_SRCS
  vtkLiverBezierFitterTest1.cxx
  vtkLiverContourParameterizerTest1.cxx
  vtkLiverPlaneRingExtractorTest1.cxx
  vtkLiverSpheroidRingExtractorTest1.cxx
  vtkLiverBezierFitterEdgeCasesTest.cxx
  vtkLiverContourParameterizerEdgeCasesTest.cxx
  vtkLiverPlaneRingExtractorEdgeCasesTest.cxx
  vtkLiverSpheroidRingExtractorEdgeCasesTest.cxx
  vtkLiverSpheroidRingExtractorConsistencyTest.cxx
  vtkSlicerLiverBezierControlPolygonGeometryTest1.cxx
  )

#-----------------------------------------------------------------------------
slicerMacroConfigureModuleCxxTestDriver(
  NAME ${KIT}
  SOURCES ${KIT_TEST_SRCS}
  INCLUDE_DIRECTORIES
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/..
    ${CMAKE_CURRENT_BINARY_DIR}/..
  WITH_VTK_DEBUG_LEAKS_CHECK
  WITH_VTK_ERROR_OUTPUT_CHECK
  )

SIMPLE_TEST(vtkLiverBezierFitterTest1)
SIMPLE_TEST(vtkLiverContourParameterizerTest1)
SIMPLE_TEST(vtkLiverPlaneRingExtractorTest1)
SIMPLE_TEST(vtkLiverSpheroidRingExtractorTest1)
SIMPLE_TEST(vtkLiverBezierFitterEdgeCasesTest)
SIMPLE_TEST(vtkLiverContourParameterizerEdgeCasesTest)
SIMPLE_TEST(vtkLiverPlaneRingExtractorEdgeCasesTest)
SIMPLE_TEST(vtkLiverSpheroidRingExtractorEdgeCasesTest)
SIMPLE_TEST(vtkSlicerLiverBezierControlPolygonGeometryTest1)

# Stack-4 ring-extraction wiring — Constraint 1 (shader/extractor
# parameter consistency) + Constraint 2 (extraction-granularity bound).
# RED-by-construction: skips (CTest code 125) until the implementer adds
# vtkLiverSpheroidRingExtractor::ComputeQuadricCoefficients() (the
# single-source-of-truth coefficient builder both the extractor and the
# Stack-4 parameter->shader adapter transcribe FROM) and compiles this
# test with -DLIVER_SPHEROID_QUADRIC_SSOT.  See the test file header and
# ADR-0015 §Context.
SIMPLE_TEST(vtkLiverSpheroidRingExtractorConsistencyTest)
set_tests_properties(vtkLiverSpheroidRingExtractorConsistencyTest PROPERTIES
  SKIP_RETURN_CODE 125
  )

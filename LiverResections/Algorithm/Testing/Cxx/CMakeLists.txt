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
  vtkLiverResectogramAspectRatioTest.cxx
  vtkLiverResectogramPixelMappingTest.cxx
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
# The single-source-of-truth coefficient builder
# vtkLiverSpheroidRingExtractor::ComputeQuadricCoefficients() now exists
# (the extractor and the Stack-4 parameter->shader adapter both
# transcribe FROM it), so enable the consistency branch via
# -DLIVER_SPHEROID_QUADRIC_SSOT.  See the test file header and
# ADR-0015 §Context.  SKIP_RETURN_CODE retained so a future build that
# compiles the test without the macro degrades to a skip rather than a
# hard failure.
set_property(SOURCE vtkLiverSpheroidRingExtractorConsistencyTest.cxx
  APPEND PROPERTY COMPILE_DEFINITIONS LIVER_SPHEROID_QUADRIC_SSOT
  )
SIMPLE_TEST(vtkLiverSpheroidRingExtractorConsistencyTest)
set_tests_properties(vtkLiverSpheroidRingExtractorConsistencyTest PROPERTIES
  SKIP_RETURN_CODE 125
  )

# T3 ResectogramPipeline — invariant-test-first scaffolding (ADR-0027).
# Both helpers are extracted/introduced by the eventual T3 implementation;
# until then the checked branch is compiled out behind its compile macro
# and the test returns the CTest skip code (125).  The implementer adds
# the pure-VTK helper (ADR-0015 §1, no MRML) and defines the matching
# macro to lift each skip — see the test-file headers.
#
# vtkLiverResectogramAspectRatioTest pins the v1 Ratio() arc-length math
# (square -> {1,1}; non-square -> non-{1,1}); the highest-value T3
# invariant.  The pure-VTK helper
# vtkLiverResectogramAspectRatio::ComputeAspectRatio() now exists, so the
# active branch is enabled via -DLIVER_RESECTOGRAM_ASPECT_RATIO.
# SKIP_RETURN_CODE retained so a future build that compiles the test
# without the macro degrades to a skip rather than a hard failure.
set_property(SOURCE vtkLiverResectogramAspectRatioTest.cxx
  APPEND PROPERTY COMPILE_DEFINITIONS LIVER_RESECTOGRAM_ASPECT_RATIO
  )
SIMPLE_TEST(vtkLiverResectogramAspectRatioTest)
set_tests_properties(vtkLiverResectogramAspectRatioTest PROPERTIES
  SKIP_RETURN_CODE 125
  )

# vtkLiverResectogramPixelMappingTest pins the ADR-0025 §Context pixel ->
# (u,v) correspondence the locator producer (issue #414) consumes.  The
# pure-VTK helper vtkLiverResectogramPixelMapping::PixelToUV() now exists,
# so the active branch is enabled via -DLIVER_RESECTOGRAM_PIXEL_MAPPING.
set_property(SOURCE vtkLiverResectogramPixelMappingTest.cxx
  APPEND PROPERTY COMPILE_DEFINITIONS LIVER_RESECTOGRAM_PIXEL_MAPPING
  )
SIMPLE_TEST(vtkLiverResectogramPixelMappingTest)
set_tests_properties(vtkLiverResectogramPixelMappingTest PROPERTIES
  SKIP_RETURN_CODE 125
  )

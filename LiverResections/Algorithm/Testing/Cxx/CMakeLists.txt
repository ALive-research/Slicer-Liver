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

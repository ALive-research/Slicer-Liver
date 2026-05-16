#-----------------------------------------------------------------------------
# C++ low-level tests for the LiverResections MRML library.
# Per ADR-0008 §2 — "C++ low-level" row, ctkTest driver, no Slicer
# launch, no Qt.  Mirrors the Algorithm/Testing/Cxx pattern introduced
# in PR #334.
#-----------------------------------------------------------------------------

set(KIT vtkSlicer${MODULE_NAME}ModuleMRML)

#-----------------------------------------------------------------------------
set(KIT_TEST_SRCS
  vtkMRMLLiverBezierSurfaceNodeTest1.cxx
  vtkMRMLLiverBezierSurfaceDisplayNodeTest1.cxx
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

SIMPLE_TEST(vtkMRMLLiverBezierSurfaceNodeTest1)
SIMPLE_TEST(vtkMRMLLiverBezierSurfaceDisplayNodeTest1)

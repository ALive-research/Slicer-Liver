#-----------------------------------------------------------------------------
# C++ low-level tests for the LiverResections VTKWidgets library.
# Per ADR-0008 §2 — "C++ low-level" row, ctkTest driver, no Slicer
# launch, no Qt.  Pattern mirrors the Algorithm/Testing/Cxx and
# MRML/Testing/Cxx subdirectories.
#-----------------------------------------------------------------------------

set(KIT vtkSlicer${MODULE_NAME}ModuleVTKWidgets)

#-----------------------------------------------------------------------------
set(KIT_TEST_SRCS
  vtkLiverBezierWidgetTest1.cxx
  vtkOpenGLLiverResectionMappersRelocationTest1.cxx
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

SIMPLE_TEST(vtkLiverBezierWidgetTest1)
SIMPLE_TEST(vtkOpenGLLiverResectionMappersRelocationTest1)

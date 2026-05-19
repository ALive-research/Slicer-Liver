#-----------------------------------------------------------------------------
# C++ low-level tests for the LiverMarkups VTKWidgets library.
# Per ADR-0008 §2 — "C++ low-level" row, ctkTest driver, no Slicer
# launch, no Qt, no on-screen rendering.  Mirrors the
# LiverResections/VTKWidgets/Testing/Cxx pattern.
#-----------------------------------------------------------------------------

set(KIT vtkSlicer${MODULE_NAME}ModuleVTKWidgets)

#-----------------------------------------------------------------------------
set(KIT_TEST_SRCS
  vtkOpenGLResection2DPolyDataMapperTest1.cxx
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

SIMPLE_TEST(vtkOpenGLResection2DPolyDataMapperTest1)

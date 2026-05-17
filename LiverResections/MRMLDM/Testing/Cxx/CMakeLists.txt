#-----------------------------------------------------------------------------
# C++ low-level tests for the LiverResections MRMLDM library.
# Per ADR-0008 §2 — "C++ low-level" row, ctkTest driver, no Slicer
# launch, no Qt.  Mirrors the VTKWidgets/Testing/Cxx pattern used by
# vtkLiverBezierWidgetTest1.
#-----------------------------------------------------------------------------

set(KIT vtkSlicer${MODULE_NAME}ModuleMRMLDisplayableManager)

#-----------------------------------------------------------------------------
set(KIT_TEST_SRCS
  vtkMRMLLiverBezierSurfaceDisplayableManager3DTest1.cxx
  )

#-----------------------------------------------------------------------------
slicerMacroConfigureModuleCxxTestDriver(
  NAME ${KIT}
  SOURCES ${KIT_TEST_SRCS}
  INCLUDE_DIRECTORIES
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/..
    ${CMAKE_CURRENT_BINARY_DIR}/..
    ${vtkSlicer${MODULE_NAME}ModuleMRML_SOURCE_DIR}
    ${vtkSlicer${MODULE_NAME}ModuleMRML_BINARY_DIR}
    ${vtkSlicer${MODULE_NAME}ModuleVTKWidgets_SOURCE_DIR}
    ${vtkSlicer${MODULE_NAME}ModuleVTKWidgets_BINARY_DIR}
  WITH_VTK_DEBUG_LEAKS_CHECK
  WITH_VTK_ERROR_OUTPUT_CHECK
  )

SIMPLE_TEST(vtkMRMLLiverBezierSurfaceDisplayableManager3DTest1)

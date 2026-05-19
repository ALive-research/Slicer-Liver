#-----------------------------------------------------------------------------
# C++ low-level tests for the LiverMarkups VTKWidgets library.
# Per ADR-0008 §2 — "C++ low-level" row, ctkTest driver, no Slicer
# launch, no Qt.  Mirrors the LiverResections/VTKWidgets/Testing/Cxx
# pattern.
#
# These tests exercise the texture-unit allocation contract pinned by
# the removal of vtkMultiTextureObjectHelper (pre-VTK-9.0 shim).  See
# the test header for the contract.
#-----------------------------------------------------------------------------

set(KIT vtkSlicer${MODULE_NAME}ModuleVTKWidgets)

#-----------------------------------------------------------------------------
set(KIT_TEST_SRCS
  vtkLiverMultiTextureUnitAllocationTest1.cxx
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

SIMPLE_TEST(vtkLiverMultiTextureUnitAllocationTest1)

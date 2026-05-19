#-----------------------------------------------------------------------------
# Distributed under the OSI-approved BSD 3-Clause License.
# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.
# All rights reserved.
#-----------------------------------------------------------------------------
# C++ low-level tests for the LiverMarkups VTKWidgets library.
# Per ADR-0008 §2 — "C++ low-level" row, ctkTest driver, no Slicer
# launch, no Qt.  Mirrors the LiverResections/VTKWidgets/Testing/Cxx
# pattern.
#
# These tests exercise the texture-unit allocation contract relied on
# by the LiverMarkups resection-mapper render path after the pre-VTK-9.0
# texture-unit shim was retired.  See the test header for the contract.
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

# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

#-----------------------------------------------------------------------------
# C++ low-level tests for the VascularTerritories MRML library.
# Per ADR-0008 §2 -- "C++ low-level" row, ctkTest driver, no Slicer
# launch, no Qt.  Mirrors the LiverResections/MRML/Testing/Cxx pattern.
#
# The test file is the test-first artefact landed per ADR-0027 ahead
# of the implementer commit; assertions fail red against the current
# stub .cxx bodies.
#-----------------------------------------------------------------------------

set(KIT vtkSlicerVascularTerritoriesModuleMRML)

#-----------------------------------------------------------------------------
set(KIT_TEST_SRCS
  vtkMRMLAbstractTerritoriesNodeTest1.cxx
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

SIMPLE_TEST(vtkMRMLAbstractTerritoriesNodeTest1)

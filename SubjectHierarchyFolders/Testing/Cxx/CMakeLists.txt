# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

#-----------------------------------------------------------------------------
# C++ low-level test for the standalone Subject-Hierarchy folder utility
# kit ``vtkSlicerSubjectHierarchyFolders`` (T5.2-f programmatic
# Subject-Hierarchy management).
#
# Per ADR-0008 §2 -- "C++ low-level" row, ctkTest driver, no Slicer
# launch, no Qt.  Mirrors VascularTerritories/MRML/Testing/Cxx and
# LiverResections/MRML/Testing/Cxx.
#
# The test file is the test-first artefact landed per ADR-0027 ahead of
# the implementer commit; it fails red because the kit does not yet
# exist.
#
# IMPLEMENTER TODO -- production wiring not done here (test-designer
# writes tests only):
#
#   * Create the kit's production CMake (a sibling of this Testing/ tree,
#     e.g. SubjectHierarchyFolders/CMakeLists.txt) that builds
#     ``vtkSlicerSubjectHierarchyFolders`` as a wrapped VTK/Slicer kit
#     linking MRMLCore only (ADR-0003: a utility, not a MRML node; no Qt,
#     no module-Logic link).  The Python wrapper module
#     ``vtkSlicerSubjectHierarchyFoldersPython`` (imported by the
#     LiverSegmentation consumer + the reachability pytest) is produced
#     by that kit's wrapping.
#   * Add ``add_subdirectory(SubjectHierarchyFolders)`` to the top-level
#     CMakeLists.txt (alongside the LiverResections / VascularTerritories
#     module subdirectories) so the kit + this test get configured.
#   * Confirm the ``KIT`` name + ``slicerMacroConfigureModuleCxxTestDriver``
#     INCLUDE_DIRECTORIES / TARGET_LIBRARIES below resolve once the kit
#     target exists; the test driver must link the kit library.
#
# Until the kit's production CMake + the top-level add_subdirectory land,
# this Testing/Cxx tree is NOT reached by CMake configure (nothing adds
# SubjectHierarchyFolders/), so it does not break the current build.  The
# implementer wires it on the same commit that lands the kit.
#-----------------------------------------------------------------------------

set(KIT vtkSlicerSubjectHierarchyFolders)

#-----------------------------------------------------------------------------
set(KIT_TEST_SRCS
  vtkSlicerSubjectHierarchyFoldersTest1.cxx
  )

#-----------------------------------------------------------------------------
slicerMacroConfigureModuleCxxTestDriver(
  NAME ${KIT}
  SOURCES ${KIT_TEST_SRCS}
  TARGET_LIBRARIES ${KIT}
  INCLUDE_DIRECTORIES
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/..
    ${CMAKE_CURRENT_BINARY_DIR}/..
  WITH_VTK_DEBUG_LEAKS_CHECK
  WITH_VTK_ERROR_OUTPUT_CHECK
  )

SIMPLE_TEST(vtkSlicerSubjectHierarchyFoldersTest1)

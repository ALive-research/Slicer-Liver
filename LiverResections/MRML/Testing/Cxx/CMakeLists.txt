#-----------------------------------------------------------------------------
# C++ low-level tests for the LiverResections MRML library.
# Per ADR-0008 §2 — "C++ low-level" row, ctkTest driver, no Slicer
# launch, no Qt.  Mirrors the Algorithm/Testing/Cxx pattern introduced
# in PR #334.
#-----------------------------------------------------------------------------

set(KIT vtkSlicer${MODULE_NAME}ModuleMRML)

#-----------------------------------------------------------------------------
set(KIT_TEST_SRCS
  vtkMRMLBezierSurfaceNodeTest1.cxx
  vtkMRMLBezierSurfaceDisplayNodeTest1.cxx
  vtkMRMLBezierSurfaceStorageNodeTest1.cxx
  vtkMRMLBezierSurfaceStorageNodeTest2.cxx
  )

#-----------------------------------------------------------------------------
# Pass the in-source Fixtures/ directory through to the test driver so
# the legacy ``.lrp.fcsv`` fixture (committed under
# Testing/Cxx/Fixtures/legacy_resection.lrp.fcsv) is locatable at run
# time.  The macro is consumed by
# ``vtkMRMLBezierSurfaceStorageNodeTest1.cxx`` (task T2.5).
add_definitions(-DLIVER_BEZIER_STORAGE_TEST_FIXTURE_DIR=\"${CMAKE_CURRENT_SOURCE_DIR}/Fixtures\")

#-----------------------------------------------------------------------------
# Pass a writable temp dir (the standard CMake binary-tree temporary
# directory) through to the test driver so the JSON round-trip test
# does not depend on POSIX TMPDIR / /tmp semantics.
file(MAKE_DIRECTORY ${CMAKE_BINARY_DIR}/Testing/Temporary)
add_definitions(-DLIVER_BEZIER_STORAGE_TEST_TEMP_DIR=\"${CMAKE_BINARY_DIR}/Testing/Temporary\")

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
# Test-driver-only cross-link to the VascularTerritories MRML kit so
# the scene-scan classification subtests in
# vtkMRMLBezierSurfaceStorageNodeTest2.cxx can instantiate
# ``vtkMRMLStdCouinaudTerritoriesNode`` / ``vtkMRMLCustomTerritoriesNode``
# directly.  The production storage node never link-time-depends on
# the territories kit — it discovers subclasses via the string-based
# ``vtkMRMLScene::GetNodesByClass("vtkMRMLAbstractTerritoriesNode")``.
# Per ADR-0008 §2, the dep is constrained to the C++ low-level test
# driver.
slicerMacroConfigureModuleCxxTestDriver(
  NAME ${KIT}
  SOURCES ${KIT_TEST_SRCS}
  INCLUDE_DIRECTORIES
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/..
    ${CMAKE_CURRENT_BINARY_DIR}/..
    ${CMAKE_SOURCE_DIR}/VascularTerritories/MRML
    ${CMAKE_BINARY_DIR}/VascularTerritories/MRML
  TARGET_LIBRARIES
    vtkSlicerVascularTerritoriesModuleMRML
  WITH_VTK_DEBUG_LEAKS_CHECK
  WITH_VTK_ERROR_OUTPUT_CHECK
  )

SIMPLE_TEST(vtkMRMLBezierSurfaceNodeTest1)
SIMPLE_TEST(vtkMRMLBezierSurfaceDisplayNodeTest1)
SIMPLE_TEST(vtkMRMLBezierSurfaceStorageNodeTest1)
SIMPLE_TEST(vtkMRMLBezierSurfaceStorageNodeTest2)

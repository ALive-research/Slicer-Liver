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
  vtkMRMLParametricSurfaceDisplayNodeTest1.cxx
  vtkMRMLAbstractParametricSurfaceNodeTest1.cxx
  vtkMRMLResectionPlanNodeTest1.cxx
  vtkMRMLResectionPlanStorageNodeTest1.cxx
  vtkMRMLResectionPlanLegacyFcsvMigrationTest.cxx
  vtkMRMLResectionPlanLegacyRetirementSafetyTest.cxx
  )

#-----------------------------------------------------------------------------
# Pass the in-source Fixtures/ directory through to the test driver.
# Consumed by vtkMRMLResectionPlanLegacyFcsvMigrationTest, which reads
# the committed legacy ``.lrp.fcsv`` fixture through the v2 plan-storage
# migration path.
add_definitions(-DLIVER_BEZIER_STORAGE_TEST_FIXTURE_DIR=\"${CMAKE_CURRENT_SOURCE_DIR}/Fixtures\")

#-----------------------------------------------------------------------------
# Pass a writable temp dir (the standard CMake binary-tree temporary
# directory) through to the test driver so the JSON round-trip tests
# do not depend on POSIX TMPDIR / /tmp semantics.  Macro name carried
# forward from the retired vtkMRMLBezierSurfaceStorageNodeTest{1,2}
# pair -- the new vtkMRMLResectionPlanStorageNodeTest1 consumes it.
file(MAKE_DIRECTORY ${CMAKE_BINARY_DIR}/Testing/Temporary)
add_definitions(-DLIVER_BEZIER_STORAGE_TEST_TEMP_DIR=\"${CMAKE_BINARY_DIR}/Testing/Temporary\")

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

SIMPLE_TEST(vtkMRMLBezierSurfaceNodeTest1)
SIMPLE_TEST(vtkMRMLParametricSurfaceDisplayNodeTest1)
SIMPLE_TEST(vtkMRMLAbstractParametricSurfaceNodeTest1)
SIMPLE_TEST(vtkMRMLResectionPlanNodeTest1)
SIMPLE_TEST(vtkMRMLResectionPlanStorageNodeTest1)
SIMPLE_TEST(vtkMRMLResectionPlanLegacyFcsvMigrationTest)
SIMPLE_TEST(vtkMRMLResectionPlanLegacyRetirementSafetyTest)

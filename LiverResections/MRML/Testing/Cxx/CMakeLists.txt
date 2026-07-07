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
  vtkMRMLResectogramDisplayNodeTest1.cxx
  vtkMRMLAbstractParametricSurfaceNodeTest1.cxx
  vtkMRMLResectionPlanNodeTest1.cxx
  vtkMRMLResectionPlanStorageNodeTest1.cxx
  # Characterization test (T2.7-2b): the plan-to-carrier association
  # round-trips through .lrp.json via the typed "geometry" node-ref alone,
  # re-resolving on a standalone load with no logic instance.  Pins the
  # mechanism that makes the 6 legacy logic association maps removable.
  vtkMRMLResectionPlanGeometryRefRoundTripTest.cxx
  # ADR-0031: the distance-map volume is a path-specific input of the
  # resection plan, named by a typed "distanceMap" node-ref on the plan
  # wrapper (not the carrier).  Pins the role literal + the in-scene
  # set/get round-trip + nullptr-clears.
  vtkMRMLResectionPlanDistanceMapRefTest.cxx
  vtkMRMLLocatorNodeTest1.cxx
  )

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
SIMPLE_TEST(vtkMRMLResectogramDisplayNodeTest1)
SIMPLE_TEST(vtkMRMLAbstractParametricSurfaceNodeTest1)
SIMPLE_TEST(vtkMRMLResectionPlanNodeTest1)
SIMPLE_TEST(vtkMRMLResectionPlanStorageNodeTest1)
SIMPLE_TEST(vtkMRMLResectionPlanGeometryRefRoundTripTest)
SIMPLE_TEST(vtkMRMLResectionPlanDistanceMapRefTest)
SIMPLE_TEST(vtkMRMLLocatorNodeTest1)

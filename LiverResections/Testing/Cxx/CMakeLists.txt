set(KIT qSlicer${MODULE_NAME}Module)

#-----------------------------------------------------------------------------
set(TEMP ${Slicer_BINARY_DIR}/Testing/Temporary)
set(INPUT ${CMAKE_CURRENT_SOURCE_DIR}/../Data/Input)

#-----------------------------------------------------------------------------
set(KIT_TEST_SRCS
  vtkMRMLLiverResectionNodeTest1.cxx
  vtkSlicerLiverResectionsLogicTest1.cxx
  qSlicerLiverResectionsModuleIntegrationTest.cxx
  )

#-----------------------------------------------------------------------------
slicerMacroConfigureModuleCxxTestDriver(
  NAME ${KIT}
  SOURCES ${KIT_TEST_SRCS}
  INCLUDE_DIRECTORIES
    ${qSlicerLiverMarkupsModule_INCLUDE_DIRS}
  TARGET_LIBRARIES
    qSlicerLiverMarkupsModule
  WITH_VTK_DEBUG_LEAKS_CHECK
  WITH_VTK_ERROR_OUTPUT_CHECK
  )

SIMPLE_TEST( vtkMRMLLiverResectionNodeTest1 )
SIMPLE_TEST( vtkSlicerLiverResectionsLogicTest1)
SIMPLE_TEST( qSlicerLiverResectionsModuleIntegrationTest)

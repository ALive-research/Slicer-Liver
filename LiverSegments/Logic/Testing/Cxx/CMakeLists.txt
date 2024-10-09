# set(KIT qSlicer${MODULE_NAME}Module)
set(KIT ${PROJECT_NAME})

#-----------------------------------------------------------------------------
# set(INPUT "${CMAKE_CURRENT_SOURCE_DIR}/../")
# set(TEMP "${Slicer_BINARY_DIR}/Testing/Temporary")

#-----------------------------------------------------------------------------
set(KIT_TEST_SRCS
  vtkSlicerLiverSegmentsLogicTest1.cxx
  )

#-----------------------------------------------------------------------------
slicerMacroConfigureModuleCxxTestDriver(
  NAME ${KIT}
  SOURCES ${KIT_TEST_SRCS}
  TARGET_LIBRARIES
    ${SlicerExecutionModel_EXTRA_EXECUTABLE_TARGET_LIBRARIES}
  WITH_VTK_DEBUG_LEAKS_CHECK
  WITH_VTK_ERROR_OUTPUT_CHECK
  )

# #-----------------------------------------------------------------------------
# slicerMacroConfigureModuleCxxTestDriver(
#   NAME ${KIT}
#   SOURCES ${KIT_TEST_SRCS}
#   # INCLUDE_DIRECTORIES
#     # ${qSlicerLiverSegmentsModule_INCLUDE_DIRS}
#     # ${CMAKE_CURRENT_SOURCE_DIR}/../../Logic/
#     # ${qSlicerLiverSegmentsModuleLogic_INCLUDE_DIRS}
#     # ${vtkSlicerLiverSegmentsModuleLogic_INCLUDE_DIRS}
#     # ${CMAKE_CURRENT_SOURCE_DIR}/../../
#   TARGET_LIBRARIES
#     # ${VTK_LIBRARIES}
#     ${MRML_LIBRARIES}
#     # qSlicerLiverSegmentsModule
#     # vtkSlicerLiverSegmentsModuleLogic
#     # qSlicer${MODULE_NAME}ModuleLogic
#   TESTS_TO_RUN_VAR KIT_TESTS_TO_RUN
#   WITH_VTK_DEBUG_LEAKS_CHECK
#   WITH_VTK_ERROR_OUTPUT_CHECK
#   )

#-----------------------------------------------------------------------------
# Add all the tests
# foreach(test ${KIT_TESTS_TO_RUN})
#   get_filename_component(testname ${test} NAME_WE)
#   simple_test(${testname}
#       -D ${INPUT}
#       -T ${TEMP}
#       #-V Baseline/${testname}.png
#     )
# endforeach()

#-----------------------------------------------------------------------------
simple_test(vtkSlicerLiverSegmentsLogicTest1)


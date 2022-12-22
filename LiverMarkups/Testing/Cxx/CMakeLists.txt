set(KIT qSlicer${MODULE_NAME}Module)

#-----------------------------------------------------------------------------
set(INPUT "${CMAKE_CURRENT_SOURCE_DIR}/../")
set(TEMP "${Slicer_BINARY_DIR}/Testing/Temporary")

#configure_file(
#  ${CMAKE_CURRENT_SOURCE_DIR}/../Data/Input/Fiducials\ List.acsv
#  ${TEMP}/Fiducials\ List.acsv
#  COPYONLY
#  )

#-----------------------------------------------------------------------------
set(KIT_TEST_SRCS
  qSlicerLiverMarkupsModuleTest.cxx
  )

#-----------------------------------------------------------------------------
slicerMacroConfigureModuleCxxTestDriver(
  NAME ${KIT}
  SOURCES ${KIT_TEST_SRCS}
#  TARGET_LIBRARIES qSlicer${MODULE_NAME}ModuleWidgets
  TESTS_TO_RUN_VAR KIT_TESTS_TO_RUN
  WITH_VTK_DEBUG_LEAKS_CHECK
  WITH_VTK_ERROR_OUTPUT_CHECK
  )

#-----------------------------------------------------------------------------
# Add all the tests
foreach(test ${KIT_TESTS_TO_RUN})
  get_filename_component(testname ${test} NAME_WE)
  simple_test(${testname}
      -D ${INPUT}
      -T ${TEMP}
      #-V Baseline/${testname}.png
    )
endforeach()


# set(KIT qSlicer${MODULE_NAME}Module)
set(KIT ${PROJECT_NAME})

#-----------------------------------------------------------------------------
# set(INPUT "${CMAKE_CURRENT_SOURCE_DIR}/../")
# set(TEMP "${Slicer_BINARY_DIR}/Testing/Temporary")

#-----------------------------------------------------------------------------
set(KIT_TEST_SRCS
  vtkSlicerVascularTerritoriesLogicTest1.cxx
  # Liver segment resolved by SCT structure tag (ADR-0011 liver code), NOT the
  # segment name "liver", so the Stage-2 canonical segmentation (SCT-tagged,
  # arbitrary segment names) feeds Stage 3 (ADR-0024 §Output contract).
  vtkSlicerVascularTerritoriesLogicLiverSegmentIdTest.cxx
  # CHARACTERIZATION of the CURRENT Subject-Hierarchy collection
  # behaviour (ADR-0023 §"MRML scene organisation"), landed per
  # ADR-0003 §"refactors that preserve behaviour" / ADR-0027 BEFORE the
  # T5.2-f rewrite swaps the inline collector for the shared
  # vtkSlicerSubjectHierarchyFolders utility.  GREEN on the current
  # branch; stays green after the rewrite (equivalence oracle).
  vtkSlicerVascularTerritoriesLogicSubjectHierarchyCharacterizationTest.cxx
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
#     # ${qSlicerVascularTerritoriesModule_INCLUDE_DIRS}
#     # ${CMAKE_CURRENT_SOURCE_DIR}/../../Logic/
#     # ${qSlicerVascularTerritoriesModuleLogic_INCLUDE_DIRS}
#     # ${vtkSlicerVascularTerritoriesModuleLogic_INCLUDE_DIRS}
#     # ${CMAKE_CURRENT_SOURCE_DIR}/../../
#   TARGET_LIBRARIES
#     # ${VTK_LIBRARIES}
#     ${MRML_LIBRARIES}
#     # qSlicerVascularTerritoriesModule
#     # vtkSlicerVascularTerritoriesModuleLogic
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
simple_test(vtkSlicerVascularTerritoriesLogicTest1)
simple_test(vtkSlicerVascularTerritoriesLogicSubjectHierarchyCharacterizationTest)

set(KIT ${PROJECT_NAME})

#-----------------------------------------------------------------------------
set(KIT_TEST_SRCS
  # CHARACTERIZATION of the CURRENT Subject-Hierarchy collection
  # behaviour of vtkSlicerLiverResectionsLogic::OnMRMLSceneNodeAdded
  # (ADR-0023 §"Subject Hierarchy management convention").  Verifies the
  # wrapper vtkMRMLLiverResectionNode is collected under the per-stage
  # "Resections" folder while hidden carriers are left alone
  # (ADR-0014 §1 wrapper-vs-carrier split).  GREEN against the current
  # logic; a red run surfaces a regression in the wiring.
  vtkSlicerLiverResectionsLogicSubjectHierarchyCharacterizationTest.cxx
  )

#-----------------------------------------------------------------------------
slicerMacroConfigureModuleCxxTestDriver(
  NAME ${KIT}
  SOURCES ${KIT_TEST_SRCS}
  TARGET_LIBRARIES
    ${SlicerExecutionModel_EXTRA_EXECUTABLE_TARGET_LIBRARIES}
    vtkSlicerLiverResectionsModuleMRML
    vtkSlicerSubjectHierarchyFolders
  WITH_VTK_DEBUG_LEAKS_CHECK
  WITH_VTK_ERROR_OUTPUT_CHECK
  )

#-----------------------------------------------------------------------------
simple_test(vtkSlicerLiverResectionsLogicSubjectHierarchyCharacterizationTest)

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
  # RED test-first scaffolding (T2.7-2b): pins the surviving v2 behaviour
  # that the legacy Deformation push in ProcessMRMLNodesEvents must be
  # replaced by -- a Bezier-surface-carrier StartInteractionEvent advances
  # the carrier's own ADR-0019 state machine Init->Planning.  RED against
  # the current tree (no carrier arm); green once the 2b rewrite lands.
  vtkSlicerLiverResectionsLogicCarrierStateAdvanceTest.cxx
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
simple_test(vtkSlicerLiverResectionsLogicCarrierStateAdvanceTest)

set(KIT ${PROJECT_NAME})

#-----------------------------------------------------------------------------
set(KIT_TEST_SRCS
  # RED test-first scaffold for the LiverVolumetry surface-generation
  # carrier-acceptance invariant.  The volumetry logic must read a v2
  # resection-plan geometry carrier (vtkMRMLBezierSurfaceNode, the
  # parametric hierarchy) via its flat GetControlGrid() and project a
  # non-empty Bezier surface -- the boundary for "volume bounded by a
  # resection".  RED until the logic stops downcasting to the disjoint
  # v1 vtkMRMLMarkupsBezierSurfaceNode and re-sources control points.
  # [ADR-0014 §"Fourth layer" wrapper-vs-carrier split]
  vtkLiverVolumetryLogicResectionCarrierTest.cxx
  )

#-----------------------------------------------------------------------------
slicerMacroConfigureModuleCxxTestDriver(
  NAME ${KIT}
  SOURCES ${KIT_TEST_SRCS}
  TARGET_LIBRARIES
    ${SlicerExecutionModel_EXTRA_EXECUTABLE_TARGET_LIBRARIES}
    vtkSlicerLiverVolumetryModuleLogic
    # vtkMRMLBezierSurfaceNode (the v2 parametric carrier) lives in the
    # LiverResections MRML library; the production volumetry logic needs
    # the same link once it is retargeted to the carrier.
    vtkSlicerLiverResectionsModuleMRML
    # vtkMRMLMarkupsBezierSurfaceNode (the disjoint v1 hierarchy whose
    # SafeDownCast drops the carrier) is characterized by the root-cause
    # test; it lives in the LiverMarkups MRML library.
    vtkSlicerLiverMarkupsModuleMRML
  WITH_VTK_DEBUG_LEAKS_CHECK
  WITH_VTK_ERROR_OUTPUT_CHECK
  )

#-----------------------------------------------------------------------------
simple_test(vtkLiverVolumetryLogicResectionCarrierTest)

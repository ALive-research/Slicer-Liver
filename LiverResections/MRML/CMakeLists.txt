project(vtkSlicer${MODULE_NAME}ModuleMRML)

set(KIT ${PROJECT_NAME})

set(${KIT}_EXPORT_DIRECTIVE "VTK_SLICER_${MODULE_NAME_UPPER}_MODULE_MRML_EXPORT")

set(${KIT}_INCLUDE_DIRECTORIES)

set(${KIT}_SRCS
  vtkMRMLLiverResectionNode.h
  vtkMRMLLiverResectionNode.cxx
  vtkMRMLLiverResectionCSVStorageNode.h
  vtkMRMLLiverResectionCSVStorageNode.cxx
  vtkMRMLAbstractParametricSurfaceNode.h
  vtkMRMLAbstractParametricSurfaceNode.cxx
  vtkMRMLBezierSurfaceNode.h
  vtkMRMLBezierSurfaceNode.cxx
  vtkMRMLParametricSurfaceDisplayNode.h
  vtkMRMLParametricSurfaceDisplayNode.cxx
  vtkMRMLBezierSurfaceStorageNode.h
  vtkMRMLBezierSurfaceStorageNode.cxx
  vtkMRMLResectionPlanNode.h
  vtkMRMLResectionPlanNode.cxx
  vtkMRMLResectionPlanStorageNode.h
  vtkMRMLResectionPlanStorageNode.cxx
  )

set(${KIT}_TARGET_LIBRARIES
  vtkSlicerLiverMarkupsModuleMRML
  ${MRML_LIBRARIES}
  )

#-----------------------------------------------------------------------------
SlicerMacroBuildModuleMRML(
  NAME ${KIT}
  EXPORT_DIRECTIVE ${${KIT}_EXPORT_DIRECTIVE}
  INCLUDE_DIRECTORIES ${${KIT}_INCLUDE_DIRECTORIES}
  SRCS ${${KIT}_SRCS}
  TARGET_LIBRARIES ${${KIT}_TARGET_LIBRARIES}
)

#-----------------------------------------------------------------------------
# C++ low-level tests for the MRML node classes (ADR-0008 §2, ctkTest
# driver, no Slicer launch, no Qt).  Sibling-of-source layout matches
# the Algorithm/Testing/Cxx subdirectory introduced in PR #334.
if(BUILD_TESTING)
  add_subdirectory(Testing)
endif()

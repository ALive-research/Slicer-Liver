project(vtkSlicer${MODULE_NAME}ModuleMRML)

set(KIT ${PROJECT_NAME})

set(${KIT}_EXPORT_DIRECTIVE "VTK_SLICER_${MODULE_NAME_UPPER}_MODULE_MRML_EXPORT")

set(${KIT}_INCLUDE_DIRECTORIES
  )

set(${KIT}_SRCS
  vtkMRMLMarkupsSlicingContourNode.h
  vtkMRMLMarkupsSlicingContourNode.cxx
  vtkMRMLMarkupsSlicingContourDisplayNode.h
  vtkMRMLMarkupsSlicingContourDisplayNode.cxx
  vtkMRMLMarkupsDistanceContourNode.h
  vtkMRMLMarkupsDistanceContourNode.cxx
  vtkMRMLMarkupsDistanceContourDisplayNode.h
  vtkMRMLMarkupsDistanceContourDisplayNode.cxx
  vtkMRMLMarkupsBezierSurfaceNode.h
  vtkMRMLMarkupsBezierSurfaceNode.cxx
  vtkMRMLMarkupsBezierSurfaceDisplayNode.h
  vtkMRMLMarkupsBezierSurfaceDisplayNode.cxx
  )

set(${KIT}_TARGET_LIBRARIES
  ${MRML_LIBRARIES}
  vtkSlicerMarkupsModuleMRML
  )

#-----------------------------------------------------------------------------
SlicerMacroBuildModuleMRML(
  NAME ${KIT}
  EXPORT_DIRECTIVE ${${KIT}_EXPORT_DIRECTIVE}
  INCLUDE_DIRECTORIES ${${KIT}_INCLUDE_DIRECTORIES}
  SRCS ${${KIT}_SRCS}
  TARGET_LIBRARIES ${${KIT}_TARGET_LIBRARIES}
  )

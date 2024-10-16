project(vtkSlicer${MODULE_NAME}ModuleLogic)

set(KIT ${PROJECT_NAME})

set(${KIT}_EXPORT_DIRECTIVE "VTK_SLICER_${MODULE_NAME_UPPER}_MODULE_LOGIC_EXPORT")

set(${KIT}_INCLUDE_DIRECTORIES
   ${CMAKE_CURRENT_BINARY_DIR}
   )

set(${KIT}_SRCS
  vtkLiverSegmentsLogic.h
  vtkLiverSegmentsLogic.cxx
  )

set(${KIT}_TARGET_LIBRARIES
  ${VTK_LIBRARIES}
  ${ITK_LIBRARIES}
  MRMLCore
#  MRMLLogic
  vtkSlicerSegmentationsModuleLogic
  )

#---------------------------------
SlicerMacroBuildModuleLogic(
  NAME ${KIT}
  EXPORT_DIRECTIVE ${${KIT}_EXPORT_DIRECTIVE}
  INCLUDE_DIRECTORIES ${${KIT}_INCLUDE_DIRECTORIES}
  SRCS ${${KIT}_SRCS}
  TARGET_LIBRARIES ${${KIT}_TARGET_LIBRARIES}
  )

if(BUILD_TESTING)
  add_subdirectory(Testing)
endif()

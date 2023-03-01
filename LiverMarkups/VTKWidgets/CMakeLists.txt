project(vtkSlicer${MODULE_NAME}ModuleVTKWidgets)

set(KIT ${PROJECT_NAME})

set(${KIT}_EXPORT_DIRECTIVE "VTK_SLICER_${MODULE_NAME_UPPER}_MODULE_VTKWIDGETS_EXPORT")

set(${KIT}_INCLUDE_DIRECTORIES
  ${vtkSlicer${MODULE_NAME}ModuleMRML_SOURCE_DIR}
  ${vtkSlicer${MODULE_NAME}ModuleMRML_BINARY_DIR}
  ${vtkSlicerMarkupsModuleVTKWidgets_INCLUDE_DIRS}
  ${vtkSlicerMarkupsModuleVTKWidgets_INCLUDE_DIRS}
  )

set(${KIT}_SRCS
  vtkSlicerSlicingContourWidget.h
  vtkSlicerSlicingContourWidget.cxx
  vtkOpenGLSlicingContourPolyDataMapper.h
  vtkOpenGLSlicingContourPolyDataMapper.cxx
  vtkOpenGLDistanceContourPolyDataMapper.h
  vtkOpenGLDistanceContourPolyDataMapper.cxx
  vtkSlicerSlicingContourRepresentation3D.h
  vtkSlicerSlicingContourRepresentation3D.cxx
  vtkSlicerSlicingContourRepresentation2D.h
  vtkSlicerSlicingContourRepresentation2D.cxx
  vtkSlicerDistanceContourWidget.h
  vtkSlicerDistanceContourWidget.cxx
  vtkSlicerDistanceContourRepresentation3D.h
  vtkSlicerDistanceContourRepresentation3D.cxx
  vtkSlicerDistanceContourRepresentation2D.h
  vtkSlicerDistanceContourRepresentation2D.cxx
  vtkSlicerBezierSurfaceWidget.h
  vtkSlicerBezierSurfaceWidget.cxx
  vtkSlicerBezierSurfaceRepresentation3D.h
  vtkSlicerBezierSurfaceRepresentation3D.cxx
  vtkSlicerBezierSurfaceRepresentation2D.h
  vtkSlicerBezierSurfaceRepresentation2D.cxx
  vtkBezierSurfaceSource.h
  vtkBezierSurfaceSource.cxx
  vtkSlicerShaderHelper.h
  vtkSlicerShaderHelper.cxx
  vtkOpenGLBezierResectionPolyDataMapper.h
  vtkOpenGLBezierResectionPolyDataMapper.cxx
  vtkOpenGLResection2DPolyDataMapper.cpp
  vtkOpenGLResection2DPolyDataMapper.h
  vtkMultiTextureObjectHelper.cpp
  vtkMultiTextureObjectHelper.h
  )

set(${KIT}_TARGET_LIBRARIES
  vtkSlicer${MODULE_NAME}ModuleMRML
  vtkSlicerMarkupsModuleVTKWidgets
  )

#-----------------------------------------------------------------------------
SlicerMacroBuildModuleLogic(
  NAME ${KIT}
  EXPORT_DIRECTIVE ${${KIT}_EXPORT_DIRECTIVE}
  INCLUDE_DIRECTORIES ${${KIT}_INCLUDE_DIRECTORIES}
  SRCS ${${KIT}_SRCS}
  TARGET_LIBRARIES ${${KIT}_TARGET_LIBRARIES}
  )

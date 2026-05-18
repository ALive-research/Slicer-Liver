project(vtkSlicer${MODULE_NAME}ModuleVTKWidgets)

set(KIT ${PROJECT_NAME})

set(${KIT}_EXPORT_DIRECTIVE "VTK_SLICER_${MODULE_NAME_UPPER}_MODULE_VTKWIDGETS_EXPORT")

set(${KIT}_INCLUDE_DIRECTORIES
  ${vtkSlicer${MODULE_NAME}ModuleMRML_SOURCE_DIR}
  ${vtkSlicer${MODULE_NAME}ModuleMRML_BINARY_DIR}
  ${vtkSlicerMarkupsModuleVTKWidgets_INCLUDE_DIRS}
  ${vtkSlicerMarkupsModuleVTKWidgets_INCLUDE_DIRS}
  # ``vtkSlicerBezierSurfaceRepresentation3D`` still consumes
  # ``vtkOpenGLBezierResectionPolyDataMapper.h``, which now lives in
  # ``LiverResections/VTKWidgets/`` per ADR-0014 §3
  # (T2-mapper-relocation).  Because the top-level CMakeLists
  # processes ``LiverMarkups`` before ``LiverResections``, the
  # ``vtkSlicerLiverResectionsModuleVTKWidgets_SOURCE_DIR`` variable
  # is not yet defined here — use the explicit paths.  The
  # corresponding ``target_link_libraries`` entry below is forward-
  # resolved by CMake at generate time.
  ${CMAKE_SOURCE_DIR}/LiverResections/VTKWidgets
  ${CMAKE_BINARY_DIR}/LiverResections/VTKWidgets
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
  vtkOpenGLResection2DPolyDataMapper.cpp
  vtkOpenGLResection2DPolyDataMapper.h
  vtkMultiTextureObjectHelper.cpp
  vtkMultiTextureObjectHelper.h
  )

set(${KIT}_TARGET_LIBRARIES
  vtkSlicer${MODULE_NAME}ModuleMRML
  vtkSlicerMarkupsModuleVTKWidgets
  # ``vtkOpenGLBezierResectionPolyDataMapper`` now ships from the
  # LiverResections VTKWidgets target (ADR-0014 §3 lift-and-shift).
  # Forward-reference resolved at CMake generate time; the source
  # ordering caveat is documented under INCLUDE_DIRECTORIES above.
  vtkSlicerLiverResectionsModuleVTKWidgets
  )

#-----------------------------------------------------------------------------
SlicerMacroBuildModuleLogic(
  NAME ${KIT}
  EXPORT_DIRECTIVE ${${KIT}_EXPORT_DIRECTIVE}
  INCLUDE_DIRECTORIES ${${KIT}_INCLUDE_DIRECTORIES}
  SRCS ${${KIT}_SRCS}
  TARGET_LIBRARIES ${${KIT}_TARGET_LIBRARIES}
  )

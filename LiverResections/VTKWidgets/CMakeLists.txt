#-----------------------------------------------------------------------------
# LiverResections/VTKWidgets
#
# Custom VTK widget for the Bezier-surface resection-planning workflow.
# Per ADR-0014 §3, ``vtkLiverBezierWidget`` subclasses
# ``vtkAbstractWidget`` directly (NOT ``vtkSlicerMarkupsWidget``) so the
# event table is free of Markups assumptions:
#
#   - Left-drag  = per-point control-grid manipulation.
#   - Right-drag = ring-group manipulation
#                  (TODO(T2.3 right-drag-ring-group)).
#   - Right-click = widget's own context menu
#                   (TODO(T2.3 right-click-context-menu)).
#
# Paired with ``vtkLiverBezierRepresentation`` (a
# ``vtkWidgetRepresentation`` subclass), which owns the interaction-
# time actors (selection highlight, drag preview).
#
# Per ADR-0014 §3, ``vtkOpenGLBezierResectionPolyDataMapper`` lives in
# this module — it relocated here from ``LiverMarkups/VTKWidgets/`` as
# a lift-and-shift (same algorithm, same shaders, same uniforms).
# Subsequent work depends on the relocation: ADR-0019's
# ``ConfirmedRepresentation`` consumes the mapper as-is, and the v2.1
# GPU-tessellation rewrite per ADR-0020 replaces the geometry path in
# this same file.
#-----------------------------------------------------------------------------

project(vtkSlicer${MODULE_NAME}ModuleVTKWidgets)

set(KIT ${PROJECT_NAME})

set(${KIT}_EXPORT_DIRECTIVE "VTK_SLICER_${MODULE_NAME_UPPER}_MODULE_VTKWIDGETS_EXPORT")

set(${KIT}_INCLUDE_DIRECTORIES
  ${vtkSlicer${MODULE_NAME}ModuleMRML_SOURCE_DIR}
  ${vtkSlicer${MODULE_NAME}ModuleMRML_BINARY_DIR}
  )

set(${KIT}_SRCS
  vtkLiverBezierRepresentation.h
  vtkLiverBezierRepresentation.cxx
  vtkLiverBezierWidget.h
  vtkLiverBezierWidget.cxx
  vtkOpenGLBezierResectionPolyDataMapper.h
  vtkOpenGLBezierResectionPolyDataMapper.cxx
  )

set(${KIT}_TARGET_LIBRARIES
  vtkSlicer${MODULE_NAME}ModuleMRML
  ${VTK_LIBRARIES}
  )

#-----------------------------------------------------------------------------
SlicerMacroBuildModuleLogic(
  NAME ${KIT}
  EXPORT_DIRECTIVE ${${KIT}_EXPORT_DIRECTIVE}
  INCLUDE_DIRECTORIES ${${KIT}_INCLUDE_DIRECTORIES}
  SRCS ${${KIT}_SRCS}
  TARGET_LIBRARIES ${${KIT}_TARGET_LIBRARIES}
  )

#-----------------------------------------------------------------------------
# C++ low-level tests for the widget + representation (ADR-0008 §2,
# ctkTest driver, no Slicer launch, no Qt).
if(BUILD_TESTING)
  add_subdirectory(Testing)
endif()

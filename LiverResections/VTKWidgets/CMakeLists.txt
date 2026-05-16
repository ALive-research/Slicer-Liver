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
# time actors (selection highlight, drag preview).  The relocated
# OpenGL surface mappers from ``LiverMarkups/VTKWidgets/`` are
# TODO(T2-mapper-relocation); the LayerDM Pipeline keeps the
# Bezier-surface render path through that follow-on.
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

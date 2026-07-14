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
# Per ADR-0014 §3, the custom OpenGL poly-data mappers for the
# resection-planning workflow live in this module — they relocated here
# from ``LiverMarkups/VTKWidgets/`` as a lift-and-shift (same algorithm,
# same shaders, same uniforms):
#
#   - ``vtkOpenGLBezierResectionPolyDataMapper``
#   - ``vtkOpenGLResection2DPolyDataMapper``
#   - ``vtkOpenGLSlicingContourPolyDataMapper``
#   - ``vtkOpenGLDistanceContourPolyDataMapper``
#
# Subsequent work depends on the relocation: ADR-0019's
# ``ConfirmedRepresentation`` consumes the mappers as-is, and the v2.1
# GPU-tessellation rewrite per ADR-0020 replaces the geometry path in
# the Bezier mapper.
#
# The Bezier tessellation source (``vtkBezierSurfaceSource``) and the
# resectogram texture-upload helper (``vtkMultiTextureObjectHelper``)
# relocated here with the LiverMarkups dissolution (ADR-0014 step 8) —
# the same lift-and-shift discipline as the mappers.  Consumers:
# the LayerDM Representations (surface tessellation + distance-map
# upload) and the LiverVolumetry logic (surface projection).
#-----------------------------------------------------------------------------

project(vtkSlicer${MODULE_NAME}ModuleVTKWidgets)

set(KIT ${PROJECT_NAME})

set(${KIT}_EXPORT_DIRECTIVE "VTK_SLICER_${MODULE_NAME_UPPER}_MODULE_VTKWIDGETS_EXPORT")

set(${KIT}_INCLUDE_DIRECTORIES
  ${vtkSlicer${MODULE_NAME}ModuleMRML_SOURCE_DIR}
  ${vtkSlicer${MODULE_NAME}ModuleMRML_BINARY_DIR}
  # vtkOpenGLDistanceContourPolyDataMapper derives its triaxial-ellipsoid
  # shader uniform from vtkLiverSpheroidRingExtractor::ComputeQuadricCoefficients
  # (the SSOT, ADR-0015 §"Stack 4") — pull in the Algorithm library's
  # headers + binary dir (its generated export header).
  ${vtkSlicer${MODULE_NAME}ModuleAlgorithm_SOURCE_DIR}
  ${vtkSlicer${MODULE_NAME}ModuleAlgorithm_BINARY_DIR}
  )

set(${KIT}_SRCS
  vtkLiverBezierRepresentation.h
  vtkLiverBezierRepresentation.cxx
  vtkLiverBezierWidget.h
  vtkLiverBezierWidget.cxx
  vtkOpenGLBezierResectionPolyDataMapper.h
  vtkOpenGLBezierResectionPolyDataMapper.cxx
  vtkOpenGLResection2DPolyDataMapper.h
  vtkOpenGLResection2DPolyDataMapper.cpp
  vtkOpenGLSlicingContourPolyDataMapper.h
  vtkOpenGLSlicingContourPolyDataMapper.cxx
  vtkOpenGLDistanceContourPolyDataMapper.h
  vtkOpenGLDistanceContourPolyDataMapper.cxx
  vtkBezierSurfaceSource.h
  vtkBezierSurfaceSource.cxx
  vtkMultiTextureObjectHelper.h
  vtkMultiTextureObjectHelper.cpp
  )

set(${KIT}_TARGET_LIBRARIES
  vtkSlicer${MODULE_NAME}ModuleMRML
  # The distance-contour mapper consumes the single-source-of-truth
  # quadric-coefficient builder from the Algorithm library (ADR-0015
  # §"Stack 4").  No cycle: the Algorithm library does NOT link VTKWidgets.
  vtkSlicer${MODULE_NAME}ModuleAlgorithm
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

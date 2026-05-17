project(vtkSlicer${MODULE_NAME}ModuleMRMLDisplayableManager)

set(KIT ${PROJECT_NAME})

set(${KIT}_EXPORT_DIRECTIVE "VTK_SLICER_${MODULE_NAME_UPPER}_MODULE_MRMLDISPLAYABLEMANAGER_EXPORT")

set(${KIT}_INCLUDE_DIRECTORIES
  ${vtkSlicer${MODULE_NAME}ModuleLogic_SOURCE_DIR}
  ${vtkSlicer${MODULE_NAME}ModuleLogic_BINARY_DIR}
  ${vtkSlicer${MODULE_NAME}ModuleMRML_SOURCE_DIR}
  ${vtkSlicer${MODULE_NAME}ModuleMRML_BINARY_DIR}
  ${vtkSlicer${MODULE_NAME}ModuleVTKWidgets_SOURCE_DIR}
  ${vtkSlicer${MODULE_NAME}ModuleVTKWidgets_BINARY_DIR}
  ${vtkSlicerLiverMarkupsModuleVTKWidgets_SOURCE_DIR}
  ${vtkSlicerLiverMarkupsModuleVTKWidgets_BINARY_DIR}
  )

# Per ADR-0014 §6 — the new ``vtkMRMLLiverBezierSurfaceDisplayableManager3D``
# (T2.6-DM) joins the legacy ``vtkMRMLLiverResectionsDisplayableManager2D``
# in this kit.  Both register through the standard
# ``SlicerConfigureDisplayableManagerObjectFactory`` macro so they appear
# in the displayable-manager group for every view they target.
set(displayable_manager_SRCS
  vtkMRMLLiverResectionsDisplayableManager2D.cpp
  vtkMRMLLiverBezierSurfaceDisplayableManager3D.cxx
  )

SlicerConfigureDisplayableManagerObjectFactory(
  TARGET_NAME ${KIT}
  SRCS "${displayable_manager_SRCS}"
  EXPORT_MACRO "${${KIT}_EXPORT_DIRECTIVE}"
  EXPORT_HEADER "${KIT}Export.h"
  OUTPUT_SRCS_VAR displayable_manager_instantiator_SRCS
)

set(${KIT}_SRCS
  ${displayable_manager_instantiator_SRCS}
  ${displayable_manager_SRCS}
  vtkMRMLLiverResectionsDisplayableManagerHelper2D.cpp
  )

# T2.6-DM links against the in-module VTKWidgets kit to spawn
# ``vtkLiverBezierWidget`` / ``vtkLiverBezierRepresentation`` instances
# per (data node, view) pair.
set(${KIT}_TARGET_LIBRARIES
  ${MRML_LIBRARIES}
  vtkSlicer${MODULE_NAME}ModuleLogic
  vtkSlicer${MODULE_NAME}ModuleMRML
  vtkSlicer${MODULE_NAME}ModuleVTKWidgets
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
# C++ low-level tests for the MRMLDM kit (ADR-0008 §2, ctkTest driver,
# no Slicer launch, no Qt).
if(BUILD_TESTING)
  add_subdirectory(Testing)
endif()

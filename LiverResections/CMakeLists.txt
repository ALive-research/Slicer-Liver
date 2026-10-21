
#-----------------------------------------------------------------------------
set(MODULE_NAME LiverResections)
set(MODULE_TITLE ${MODULE_NAME})

string(TOUPPER ${MODULE_NAME} MODULE_NAME_UPPER)

#-----------------------------------------------------------------------------
add_subdirectory(MRML)
add_subdirectory(Algorithm)
add_subdirectory(Logic)
add_subdirectory(VTKWidgets)
# T2.6-LayerDM — Python sub-package installed alongside the loadable
# module.  Hosts the LayerDM Pipeline class + the
# ``registerPipelineCreator`` entry point invoked by ``setup()``
# (ADR-0013 §5 call 3).  Gated on ``Slicer_USE_PYTHONQT`` to match
# the Slicer-core ``${MODULE_NAME}Lib`` convention — a Slicer built
# without PythonQt cannot host the scripted Pipeline anyway.
if(Slicer_USE_PYTHONQT)
  add_subdirectory(LiverResectionsLib)
endif()

#-----------------------------------------------------------------------------
# T2.6-LayerDM — resolve the LayerDM displayable-manager kit
# (ADR-0002, ADR-0013 §5).
#
# When Slicer ships LayerDM as a core module, its target comes from
# ``SlicerTargets.cmake`` and is already defined: there is no package to
# find, and asking for one fails (the extension's
# ``LayerDisplayableManagerConfig.cmake`` does not exist on such a
# Slicer, and the catalog entry has been archived).
#
# Otherwise the extension provides it.  Slicer's launcher-settings block
# calls ``find_package(LayerDisplayableManager QUIET)`` to populate the
# launcher INI, but does not propagate the imported targets into this
# scope, so this scope must find it again.
#
# Either way the kit is named ``vtkSlicerLayerDMModuleMRMLDisplayableManager``
# -- core builds the same kit name the extension did, and SlicerConfig
# exports the matching ``_INCLUDE_DIRS`` variable -- so the link line and
# the include line below are shared verbatim.
if(NOT SLICERLIVER_LAYERDM_IS_CORE)
  find_package(LayerDisplayableManager REQUIRED)
endif()

#-----------------------------------------------------------------------------
set(MODULE_EXPORT_DIRECTIVE "Q_SLICER_QTMODULES_${MODULE_NAME_UPPER}_EXPORT")

# Current_{source,binary} and Slicer_{Libs,Base} already included
set(MODULE_INCLUDE_DIRECTORIES
  ${CMAKE_CURRENT_SOURCE_DIR}/Logic
  ${CMAKE_CURRENT_BINARY_DIR}/Logic
  ${CMAKE_CURRENT_SOURCE_DIR}/MRML
  ${CMAKE_CURRENT_BINARY_DIR}/MRML
  # Populated EITHER WAY, under the same name: by the extension's
  # LayerDisplayableManagerConfig.cmake, or -- when LayerDM is core -- by
  # SlicerConfig.cmake, which sets a
  # vtkSlicer<Module>ModuleMRMLDisplayableManager_INCLUDE_DIRS for every
  # core module.  (Not via the imported target: those carry no
  # INTERFACE_INCLUDE_DIRECTORIES.)  This is why so little else here has
  # to change.
  ${vtkSlicerLayerDMModuleMRMLDisplayableManager_INCLUDE_DIRS}
  )

set(MODULE_SRCS
  qSlicer${MODULE_NAME}Module.cxx
  qSlicer${MODULE_NAME}Module.h
  qSlicer${MODULE_NAME}Reader.h
  qSlicer${MODULE_NAME}Reader.cxx
  )

set(MODULE_MOC_SRCS
  qSlicer${MODULE_NAME}Module.h
  qSlicer${MODULE_NAME}Reader.h
  )

# ADR-0004 — the Stage-4 "Resection Planning" GUI is Python
# (LiverResectionsLib.ResectionPlanningWidget); this loadable module
# ships no C++ widget representation, so there are no module .ui files.
set(MODULE_UI_SRCS
  )

set(MODULE_TARGET_LIBRARIES
  vtkSlicer${MODULE_NAME}ModuleMRML
  vtkSlicer${MODULE_NAME}ModuleLogic
  vtkSlicerLayerDMModuleMRMLDisplayableManager
  )

set(MODULE_RESOURCES
  # Resources/qSlicer${MODULE_NAME}Module.qrc
  )

#-----------------------------------------------------------------------------
slicerMacroBuildLoadableModule(
  NAME ${MODULE_NAME}
  TITLE ${MODULE_TITLE}
  EXPORT_DIRECTIVE ${MODULE_EXPORT_DIRECTIVE}
  INCLUDE_DIRECTORIES ${MODULE_INCLUDE_DIRECTORIES}
  SRCS ${MODULE_SRCS}
  MOC_SRCS ${MODULE_MOC_SRCS}
  UI_SRCS ${MODULE_UI_SRCS}
  TARGET_LIBRARIES ${MODULE_TARGET_LIBRARIES}
  RESOURCES ${MODULE_RESOURCES}
  WITH_GENERIC_TESTS
  )

#-----------------------------------------------------------------------------
if(BUILD_TESTING)
  add_subdirectory(Testing)
endif()


#-----------------------------------------------------------------------------
set(MODULE_NAME LiverResections)
set(MODULE_TITLE ${MODULE_NAME})

string(TOUPPER ${MODULE_NAME} MODULE_NAME_UPPER)

#-----------------------------------------------------------------------------
add_subdirectory(MRML)
add_subdirectory(Algorithm)
add_subdirectory(Logic)
add_subdirectory(MRMLDM)
add_subdirectory(VTKWidgets)
# T2.6-LayerDM — Python sub-package installed alongside the loadable
# module.  Hosts the LayerDM Pipeline class + the
# ``registerPipelineCreator`` entry point invoked by ``setup()``
# (ADR-0013 §5 call 3).
add_subdirectory(LiverResectionsLib)

#-----------------------------------------------------------------------------
# T2.6-LayerDM — consume the upstream LayerDisplayableManager extension
# (ADR-0002, ADR-0013 §5).  ``EXTENSION_DEPENDS`` in the root
# ``CMakeLists.txt`` lists ``LayerDisplayableManager`` (the upstream's
# ``project()`` name); Slicer's launcher-settings block calls
# ``find_package(LayerDisplayableManager QUIET)`` to populate the
# launcher INI, but does not propagate the imported targets to this
# scope.  Call ``find_package`` here too so the
# ``vtkSlicerLayerDMModuleMRMLDisplayableManager`` imported target is
# defined for the ``setup()`` code below to link against.
find_package(LayerDisplayableManager REQUIRED)

#-----------------------------------------------------------------------------
set(MODULE_EXPORT_DIRECTIVE "Q_SLICER_QTMODULES_${MODULE_NAME_UPPER}_EXPORT")

# Current_{source,binary} and Slicer_{Libs,Base} already included
set(MODULE_INCLUDE_DIRECTORIES
  ${CMAKE_CURRENT_SOURCE_DIR}/Logic
  ${CMAKE_CURRENT_BINARY_DIR}/Logic
  ${vtkSlicerLayerDMModuleMRMLDisplayableManager_INCLUDE_DIRS}
  )

set(MODULE_SRCS
  qSlicer${MODULE_NAME}Module.cxx
  qSlicer${MODULE_NAME}Module.h
  qSlicer${MODULE_NAME}Writer.h
  qSlicer${MODULE_NAME}Writer.cxx
  qSlicer${MODULE_NAME}Reader.h
  qSlicer${MODULE_NAME}Reader.cxx
  )

set(MODULE_MOC_SRCS
  qSlicer${MODULE_NAME}Module.h
  qSlicer${MODULE_NAME}Writer.h
  qSlicer${MODULE_NAME}Reader.h
  )

set(MODULE_TARGET_LIBRARIES
  vtkSlicer${MODULE_NAME}ModuleMRML
  vtkSlicer${MODULE_NAME}ModuleLogic
  vtkSlicer${MODULE_NAME}ModuleMRMLDisplayableManager
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

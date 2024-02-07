#-----------------------------------------------------------------------------
set(MODULE_NAME LiverSegments)
string(TOUPPER ${MODULE_NAME} MODULE_NAME_UPPER)

#-----------------------------------------------------------------------------

#-----------------------------------------------------------------------------
set(MODULE_PYTHON_SCRIPTS
  ${MODULE_NAME}.py
  )

set(MODULE_PYTHON_RESOURCES
  Resources/Icons/${MODULE_NAME}.png
  Resources/UI/${MODULE_NAME}.ui
  Resources/SlicerLiverColorMap.ctbl
  )

add_subdirectory(Logic)
#-----------------------------------------------------------------------------
slicerMacroBuildScriptedModule(
  NAME ${MODULE_NAME}
  SCRIPTS ${MODULE_PYTHON_SCRIPTS}
  RESOURCES ${MODULE_PYTHON_RESOURCES}
  WITH_GENERIC_TESTS
  )


# #-----------------------------------------------------------------------------
# set(MODULE_EXPORT_DIRECTIVE "Q_SLICER_QTMODULES_${MODULE_NAME_UPPER}_EXPORT")

# set(MODULE_INCLUDE_DIRECTORIES
#   ${CMAKE_CURRENT_SOURCE_DIR}/Logic
#   ${CMAKE_CURRENT_BINARY_DIR}/Logic
#   )

# #-----------------------------------------------------------------------------
# slicerMacroBuildLoadableModule(
#   NAME ${MODULE_NAME}
#   TITLE ${MODULE_TITLE}
#   EXPORT_DIRECTIVE ${MODULE_EXPORT_DIRECTIVE}
#   INCLUDE_DIRECTORIES ${MODULE_INCLUDE_DIRECTORIES}
#   SRCS ${MODULE_SRCS}
#   MOC_SRCS ${MODULE_MOC_SRCS}
#   UI_SRCS ${MODULE_UI_SRCS}
#   TARGET_LIBRARIES ${MODULE_TARGET_LIBRARIES}
#   RESOURCES ${MODULE_RESOURCES}
#   # WITH_GENERIC_TESTS
#   )

#-----------------------------------------------------------------------------
if(BUILD_TESTING)

  # Register the unittest subclass in the main script as a ctest.
  # Note that the test will also be available at runtime.
  #slicer_add_python_unittest(SCRIPT ${MODULE_NAME}.py)

  # Additional build-time testing
  add_subdirectory(Testing)
endif()

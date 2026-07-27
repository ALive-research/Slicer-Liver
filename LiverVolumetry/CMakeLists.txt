#-----------------------------------------------------------------------------
set(MODULE_NAME LiverVolumetry)
string(TOUPPER ${MODULE_NAME} MODULE_NAME_UPPER)

#-----------------------------------------------------------------------------

#-----------------------------------------------------------------------------
set(MODULE_PYTHON_SCRIPTS
  ${MODULE_NAME}.py
  )

set(MODULE_PYTHON_RESOURCES
  Resources/Icons/${MODULE_NAME}.png
  Resources/UI/${MODULE_NAME}Widget.ui
  )

add_subdirectory(Logic)
#-----------------------------------------------------------------------------
slicerMacroBuildScriptedModule(
  NAME ${MODULE_NAME}
  SCRIPTS ${MODULE_PYTHON_SCRIPTS}
  RESOURCES ${MODULE_PYTHON_RESOURCES}
#  WITH_GENERIC_TESTS
)

#-----------------------------------------------------------------------------
if(BUILD_TESTING)
  # ADR-0038-amendment seeds-off-markups invariant-test scaffolding
  # (SlicerLiverInteractionLib base tests live in that Lib's own Testing
  # tree).  Registers the bare-pytest CTest rows; the wrapped-node /
  # LayerDM-base tests SKIP bare and RUN launched (ADR-0027).
  add_subdirectory(Testing)
endif()

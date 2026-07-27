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

# v2.0.0 MRML kit -- the ADR-0038-amendment seeds-off-markups carrier /
# storage / display node (volumetry-seeds-layerdm-plan.md §3a).  Library
# name is ``vtkSlicerLiverVolumetryModuleMRML`` (matches MODULE_NAME).
# Built first so downstream consumers can link + Python-wrap it (mirrors
# VascularTerritories/CMakeLists.txt).
add_subdirectory(MRML)
add_subdirectory(Logic)

# ADR-0038 client Python Lib: the carrier->transient-fiducial adapter, the flat
# PointProvider adapter, the in-volume slice-click pick, and the LayerDM
# Pipeline creators (volumetry-seeds-layerdm-plan.md §3).  Mirrors
# VascularTerritoriesLib.
add_subdirectory(LiverVolumetryLib)
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

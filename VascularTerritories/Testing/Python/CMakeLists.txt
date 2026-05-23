
#slicer_add_python_unittest(SCRIPT ${MODULE_NAME}ModuleTest.py)

# Opt in to LayerDisplayableManager module loading (see the
# VascularTerritories/MRML/Testing/Python/CMakeLists.txt comment block
# for the rationale).  Without this the Python wrapper test cannot
# resolve ``vtkMRMLLayerDMPipelineI`` from the ``slicer`` namespace
# even though ``PYTHONPATH`` carries the LayerDM Python package.
slicer_add_python_unittest(
  SCRIPT VascularTerritoriesTest.py
  SLICER_ARGS
    --additional-module-paths
    ${LayerDisplayableManager_DIR}/${Slicer_QTLOADABLEMODULES_LIB_DIR}
    ${LayerDisplayableManager_DIR}/${Slicer_QTSCRIPTEDMODULES_LIB_DIR}
)

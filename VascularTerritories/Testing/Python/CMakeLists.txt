
#slicer_add_python_unittest(SCRIPT ${MODULE_NAME}ModuleTest.py)

# Opt in to LayerDisplayableManager + SlicerVMTK module loading (see
# the VascularTerritories/MRML/Testing/Python/CMakeLists.txt comment
# block for the rationale).  Without LayerDM the Python wrapper test
# cannot resolve ``vtkMRMLLayerDMPipelineI`` from the ``slicer``
# namespace.  Without SlicerVMTK's ``ExtractCenterline``, the legacy
# integration suite cannot exercise the centerline computation that
# Stage 3 Manual classification depends on (per ADR-0023).  Both
# extensions are pre-built into the project's
# ``slicer-build-ubuntu2404`` CI image (ALive-Docker layers 5a-5c)
# and exposed via ``LayerDisplayableManager_DIR`` and
# ``SlicerVMTK_DIR`` env vars; ``find_package`` populates the
# matching CMake variables.
slicer_add_python_unittest(
  SCRIPT VascularTerritoriesTest.py
  SLICER_ARGS
    --additional-module-paths
    ${LayerDisplayableManager_DIR}/${Slicer_QTLOADABLEMODULES_LIB_DIR}
    ${LayerDisplayableManager_DIR}/${Slicer_QTSCRIPTEDMODULES_LIB_DIR}
    ${SlicerVMTK_DIR}/${Slicer_QTLOADABLEMODULES_LIB_DIR}
    ${SlicerVMTK_DIR}/${Slicer_QTSCRIPTEDMODULES_LIB_DIR}
)

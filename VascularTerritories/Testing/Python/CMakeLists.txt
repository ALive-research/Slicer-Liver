
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

# ---------------------------------------------------------------------------
# Bare-VTK unit tests (pytest_scaffold family)
# ---------------------------------------------------------------------------
#
# Pure-VTK unit tests for the vessel-adhering-highlight pick core live
# here and run under bare ``PythonSlicer -m pytest`` — no Slicer scene,
# no Qt, no GL (ADR-0003 testability invariant; ADR-0008 §2 unit layer).
# Unlike the launched ``slicer_add_python_unittest`` self-test above,
# these register one bare CTest row per file, mirroring the pattern in
# ``LiverSegmentation/Testing/Python/CMakeLists.txt``.  The same
# skip-if-pytest-absent guard keeps the scaffolding buildable where the
# Slicer Python environment has not yet been provisioned with pytest.
if(NOT Python3_EXECUTABLE)
  message(STATUS
    "Slicer-Liver: Python3_EXECUTABLE not set; "
    "skipping VascularTerritories bare-pytest registration.")
  return()
endif()

execute_process(
  COMMAND "${Python3_EXECUTABLE}" -c "import pytest"
  RESULT_VARIABLE _vascterr_pytest_probe_rc
  OUTPUT_QUIET
  ERROR_QUIET
)

if(NOT _vascterr_pytest_probe_rc EQUAL 0)
  message(STATUS
    "Slicer-Liver: pytest not importable from ${Python3_EXECUTABLE}; "
    "skipping VascularTerritories bare-pytest registration.  Install "
    "pytest in the Slicer Python environment to enable these tests.")
  return()
endif()

set(_vascterr_pytest_files
  # Pure-VTK unit skeletons for the vessel-adhering-highlight pick core.
  # Import-guarded on the not-yet-existing VesselSurfacePick seam; they
  # collect + SKIP-PENDING cleanly bare until the implementer lands
  # VascularTerritoriesLib/VesselSurfacePick.py (ADR-0027).
  test_vessel_surface_pick.py
)

foreach(_pytest_file IN LISTS _vascterr_pytest_files)
  get_filename_component(_test_basename "${_pytest_file}" NAME_WE)
  add_test(
    NAME ${_test_basename}
    COMMAND "${Python3_EXECUTABLE}" -m pytest
      -q
      "${CMAKE_CURRENT_SOURCE_DIR}/${_pytest_file}"
    WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
  )
  set_tests_properties(${_test_basename} PROPERTIES
    LABELS "pytest;VascularTerritories;vessel-highlight"
  )
endforeach()

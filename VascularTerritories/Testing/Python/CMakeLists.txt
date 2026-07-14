
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
  # LayerDM highlight-Pipeline unit invariants (pick integration + the
  # ADR-0033 hover-decline discipline).  Import-guarded on LayerDMLib
  # (reachable only from a launched Slicer); they SKIP bare and RUN
  # launched, mirroring the ControlPolygonPipeline unit suite.
  test_vessel_highlight_pipeline.py
  # Snap-on-place + the widget highlight wiring.  Scene-/widget-needing
  # (segmentation closed-surface reps + the module widget); they SKIP
  # cleanly bare and RUN launched, mirroring the LiverSegmentation suite.
  test_vessel_snap_and_wiring.py
  # ADR-0037 Stage-1 i1/i2 -- the annotation-point carrier on
  # vtkMRMLCustomTerritoriesNode (ordered per-territory points; no markups
  # reference) + its storage round-trip.  The carrier is a WRAPPED C++
  # node, reachable only launched; import-/hasattr-guarded on the
  # not-yet-existing carrier API + storage node, they SKIP-PENDING bare
  # and RUN launched once the seam lands (ADR-0027).
  test_territories_annotation_carrier.py
  # ADR-0037 Stage-1 i3/i4 -- the annotation placement/edit Pipeline
  # (ADR-0032/0033 seam): click adds exactly one surface-snapped point, a
  # bare move is declined (camera untouched), a drag edits the nearest
  # point, delete removes one.  Import-guarded on the not-yet-existing
  # TerritoryPlacementPipeline + LayerDMLib; SKIP bare, RUN launched,
  # mirroring the ControlPolygon/LiverBezier interaction suites (ADR-0027).
  test_territories_placement_pipeline.py
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

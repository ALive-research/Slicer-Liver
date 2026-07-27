# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

# ---------------------------------------------------------------------------
# Bare-VTK unit tests for the ADR-0038 shared control-point interaction base
# (pytest_scaffold family).
# ---------------------------------------------------------------------------
#
# The pure-VTK cores (SurfacePick geometry, PointPlacementState accessors,
# the slice-projection math) run under bare ``PythonSlicer -m pytest`` with
# no Slicer scene, no Qt, no GL (ADR-0003 testability invariant; ADR-0004
# the interaction math is pure Python).  The LayerDM base invariants (the
# 3D placement pipeline + the four LayerDM traps) import LayerDMLib and so
# SKIP bare and RUN launched -- they still register a bare CTest row here
# (they collect + skip cleanly), mirroring the VascularTerritories pattern.
# The same skip-if-pytest-absent guard keeps the scaffolding buildable
# where the Slicer Python environment lacks pytest.

if(NOT Python3_EXECUTABLE)
  message(STATUS
    "Slicer-Liver: Python3_EXECUTABLE not set; "
    "skipping SlicerLiverInteractionLib bare-pytest registration.")
  return()
endif()

execute_process(
  COMMAND "${Python3_EXECUTABLE}" -c "import pytest"
  RESULT_VARIABLE _interaction_pytest_probe_rc
  OUTPUT_QUIET
  ERROR_QUIET
)

if(NOT _interaction_pytest_probe_rc EQUAL 0)
  message(STATUS
    "Slicer-Liver: pytest not importable from ${Python3_EXECUTABLE}; "
    "skipping SlicerLiverInteractionLib bare-pytest registration.")
  return()
endif()

set(_interaction_pytest_files
  # ADR-0038 §"Shared home + names" -- the extracted pure-VTK SurfacePick
  # geometry core (ray->closed-surface nearest + closest-point fallback,
  # lazy MTime-invalidated locator).  Mirrors the VesselSurfacePick origin.
  # Genuinely RUNS bare once SlicerLiverInteractionLib/SurfacePick.py lands
  # (ADR-0027).
  test_surface_pick.py
  # ADR-0038 §"Shared home + names" -- the PointPlacementState display-node
  # accessors with the attribute-key namespace parameterized per consumer.
  # Pure Python over a fake display node; RUNS bare (ADR-0027).
  test_point_placement_state.py
  # ADR-0038 §Context -- the slice-view projection / fade / side tint /
  # presence-cutoff pure math owned by the shared slice base.  Mirrors the
  # TerritorySliceProjection origin; RUNS bare (ADR-0027).
  test_point_placement_pipeline_slice.py
  # ADR-0038 §Decision / §"Base extension" -- the 3D placement base's
  # interaction arbitration against a FAKE flat PointProvider + injected
  # pick (add/drag/delete/decline/no-drift; the base has NO surface-vs-
  # volume branch).  Imports LayerDMLib -> SKIPS bare, RUNS launched.
  test_point_placement_pipeline_3d.py
  # ADR-0038 §Conformance [future] -- the four LayerDM integration traps
  # asserted ONCE on the base (one-per-type; configure-before-add;
  # ResetDisplay-drives-UpdatePipeline; render-flush in the handler).
  # LayerDM machinery -> SKIPS bare, RUNS launched.
  test_layerdm_base_invariants.py
)

foreach(_pytest_file IN LISTS _interaction_pytest_files)
  get_filename_component(_test_basename "${_pytest_file}" NAME_WE)
  add_test(
    NAME ${_test_basename}
    COMMAND "${Python3_EXECUTABLE}" -m pytest
      -q
      "${CMAKE_CURRENT_SOURCE_DIR}/${_pytest_file}"
    WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
  )
  set_tests_properties(${_test_basename} PROPERTIES
    LABELS "pytest;SlicerLiverInteractionLib;interaction-base"
  )
endforeach()

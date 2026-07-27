# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

# ---------------------------------------------------------------------------
# Bare-VTK unit tests for the ADR-0038-amendment LiverVolumetry seeds-off-
# markups migration (pytest_scaffold family).
# ---------------------------------------------------------------------------
#
# The pure carrier->transient-fiducial mapping runs under bare
# ``PythonSlicer -m pytest`` (no scene, no wrapped node -- ADR-0003 / ADR-0004).
# The wrapped-C++-node + LayerDM-base + in-volume-pick + compute tests import
# launched-only machinery and so SKIP bare and RUN launched (the wrapped-
# class-namespace rule + LayerDMLib), still registering a bare CTest row here
# that collects + skips cleanly, mirroring the VascularTerritories pattern.
# The same skip-if-pytest-absent guard keeps the scaffolding buildable where
# the Slicer Python environment lacks pytest.

if(NOT Python3_EXECUTABLE)
  message(STATUS
    "Slicer-Liver: Python3_EXECUTABLE not set; "
    "skipping LiverVolumetry bare-pytest registration.")
  return()
endif()

execute_process(
  COMMAND "${Python3_EXECUTABLE}" -c "import pytest"
  RESULT_VARIABLE _volumetry_pytest_probe_rc
  OUTPUT_QUIET
  ERROR_QUIET
)

if(NOT _volumetry_pytest_probe_rc EQUAL 0)
  message(STATUS
    "Slicer-Liver: pytest not importable from ${Python3_EXECUTABLE}; "
    "skipping LiverVolumetry bare-pytest registration.")
  return()
endif()

set(_volumetry_pytest_files
  # ADR-0038 §Conformance -- the vtkMRMLVolumetrySeedsNode carrier: ordered
  # add/get/delete + per-seed LABEL + colour + storage round-trip.  Wrapped
  # C++ node -> SKIPS bare, RUNS launched (ADR-0027).
  test_volumetry_seed_carrier.py
  # ADR-0038 §Conformance -- the pure carrier->transient-fiducial mapping
  # preserves position + LABEL + order.  Pure Python -> RUNS bare (ADR-0027).
  test_volumetry_seed_transient_fiducial.py
  # ADR-0025/0033 -- vtkMRMLVolumetrySeedsDisplayNode is DATA-ONLY (arm/hover/
  # grab + pickSurface ref + transient point; no rendering).  Wrapped C++
  # node -> SKIPS bare, RUNS launched (ADR-0027).
  test_volumetry_seed_display_node.py
  # ADR-0038 §"Base extension" (OQ4) -- the in-volume/slice pick returns an
  # INTERIOR labelled voxel, NOT a surface snap.  Needs a labelmap volume ->
  # SKIPS bare, RUNS launched (ADR-0027).
  test_volumetry_in_volume_pick.py
  # ADR-0038 §Conformance / ADR-0015 -- the port PRESERVES compute: the
  # carrier-fed transient fiducial yields the SAME label values + segment
  # names as the ROIMarkersList path.  Wrapped C++ logic -> SKIPS bare, RUNS
  # launched (ADR-0027).
  test_volumetry_compute_from_carrier.py
  # ADR-0038 §Decision -- volumetry seed placement through the shared base +
  # the volumetry provider + in-volume pick: click adds one interior seed,
  # drag edits nearest, delete removes one.  LayerDM base + wrapped carrier
  # -> SKIPS bare, RUNS launched (ADR-0027).
  test_volumetry_seed_placement.py
  # ADR-0013 §5 -- the 3 registration calls register the carrier + display
  # node with NO custom displayable manager.  Node registration + LayerDM
  # factory -> SKIPS bare, RUNS launched (ADR-0027).
  test_volumetry_registration_smoke.py
)

foreach(_pytest_file IN LISTS _volumetry_pytest_files)
  get_filename_component(_test_basename "${_pytest_file}" NAME_WE)
  add_test(
    NAME ${_test_basename}
    COMMAND "${Python3_EXECUTABLE}" -m pytest
      -q
      "${CMAKE_CURRENT_SOURCE_DIR}/${_pytest_file}"
    WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
  )
  set_tests_properties(${_test_basename} PROPERTIES
    LABELS "pytest;LiverVolumetry;volumetry-seeds"
  )
endforeach()

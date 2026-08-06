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
  # territory-usability -- the grouped-VOLUMES carrier: per-seed volume id +
  # per-volume display slots + AddSeedToVolume + delete-volume + storage
  # round-trip.  Wrapped C++ node -> SKIPS bare, RUNS launched (ADR-0027).
  test_volumetry_seed_volumes.py
  # territory-usability -- a placed seed is assigned the ACTIVE volume read off
  # the shared display node (the active-territory routing analogue).  Pure
  # Python seam over fakes -> RUNS bare (ADR-0027).
  test_volumetry_active_volume_placement.py
  # territory-usability -- the per-VOLUME seeds table: Add volume, per-volume
  # colour/label/delete, seeds nested under their volume, Place arms into the
  # active volume.  Qt + wrapped carrier -> SKIPS bare, RUNS launched (ADR-0027).
  test_volumetry_volumes_table.py
  # territory-usability -- compute reports ONE row per VOLUME = the union of its
  # DISTINCT bound segments' regions.  Pure aggregation RUNS bare; the driver
  # over a real segmentation SKIPS bare, RUNS launched (ADR-0027).
  test_volumetry_volume_compute.py
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
  # ADR-0038 §"Base extension" -- the pick resolves against the CLICKED
  # voxel's neighbourhood (numpy-vectorized local search; a whole-volume
  # Python scan froze the GUI on clinical-size CTs).  Pure vtkImageData +
  # numpy stub -> RUNS bare (ADR-0027).
  test_volumetry_pick_locality.py
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
  # ADR-0038 §Conformance -- the carrier-backed seeds table: one row per seed,
  # label edit -> SetNthSeedLabel (the generated segment name), colour edit ->
  # SetNthSeedColor, delete -> RemoveNthSeed, observer rebuild + teardown.  Qt
  # + wrapped carrier -> SKIPS bare, RUNS launched (ADR-0027).
  test_volumetry_seeds_table.py
  # Data-first redesign §3.4 -- the gating truth table (seeds-first-class):
  # Compute gates on a segmentation AND (a ticked segment OR a seed); Place
  # gates on a segmentation only; a seed alone (no resection) is a valid B2
  # path enabling Compute + Generate; Refine-by-resection is optional and
  # never blocks Compute; whole-group Clear-all.  Qt widget + wrapped carrier
  # -> SKIPS bare, RUNS launched (ADR-0027).
  test_volumetry_action_enablement.py
  # Data-first redesign §3.5 -- results-table presentation: columns
  # Region | Volume (mL) | % of total (no ROI Voxels; divide-by-zero guard);
  # the partition total row labeled "All pieces".  Wrapped C++ VolumetryTable
  # -> SKIPS bare, RUNS launched (ADR-0027).
  test_volumetry_results_presentation.py
  # Volumetry-workflow-consistency critique -- selecting an input segmentation
  # keeps its selected segment(s) VISIBLE so Show-3D has a surface to build
  # (the reported "Show 3D shows nothing" was the prior hide-all).  Qt widget
  # + wrapped node -> SKIPS bare, RUNS launched (ADR-0027).
  test_volumetry_show3d_visibility.py
  # ADR-0038 §"Consumers ledger" -- the 3D volumetry pipeline RENDERS a glyph
  # per carrier seed (the base only hit-tests; the client draws the spheres),
  # coloured per seed, rebuilt on the carrier Modified.  LayerDM base + wrapped
  # carrier -> SKIPS bare, RUNS launched (ADR-0027).
  test_volumetry_seed_glyph_3d.py
  # ADR-0038 §Decision -- a seed placed in a slice reprojects into the clicked
  # plane at once (the client observes the carrier so the base's reproject
  # fires without a reslice).  LayerDM base + wrapped carrier + slice node ->
  # SKIPS bare, RUNS launched (ADR-0027).
  test_volumetry_slice_reproject.py
  # ``territory-usability`` §"Seed→label capture" -- the pure candidate-
  # resolution rule: touched segments order top-first by layer index and the
  # default binding is the top layer's segment.  Pure Python -> RUNS bare
  # (ADR-0027).
  test_volumetry_seed_target_resolution.py
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

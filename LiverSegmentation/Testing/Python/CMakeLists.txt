# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
#
# Pytest registration for the LiverSegmentation Stage-2 invariant tests.
#
# Test-first scaffolding per Docs/adr/0027-invariant-test-first-v2-implementation.md:
# these RED tests land before the module implementation
# (Docs/adr/0024-segmentation-orchestration.md).  Five files, one CTest entry
# each so failures are isolable (matches Liver/Testing/Python/CMakeLists.txt
# and LiverResections/Testing/Python/CMakeLists.txt):
#
#   * test_liversegmentation_registration.py             (invariant 1)
#     Module registers as `liversegmentation`; logic exposes a callable
#     isStageComplete() returning bool.  Scene-needing (minimal
#     qSlicerApplication); skips cleanly under bare PythonSlicer.
#
#   * test_liversegmentation_isstagecomplete_semantics.py (invariant 2)
#     Stage-2-done semantics (ADR-0034 §Amendments): empty -> False;
#     pre-seeded NotStarted checklist -> False; every structure Completed
#     (incl. the marked-absent empty Completed attestation) -> True;
#     scratch-only -> False.  Scene-needing.
#
#   * test_liversegmentation_single_canonical_node.py     (invariant 3)
#     Exactly ONE canonical vtkMRMLSegmentationNode; Accept merges scratch
#     into it.  Scene-needing.
#
#   * test_liversegmentation_import_purity.py             (invariant 4)
#     No pip_install + no `import totalsegmentator` at module-import time.
#     Pure-Python: no Slicer / Qt / network required.  This is the invariant
#     that lets CI run the suite offline.
#
#   * test_liversegmentation_conformance.py               (invariant 5)
#     Source / CMake greps (no EXTENSION_DEPENDS for TotalSegmentator /
#     MONAILabel; no ToolWrappers/MONAILabel.py; no new vtkMRML*DisplayNode;
#     pip_install only under ToolWrappers/).  Pure-Python.
#
# Stage-2 SURGEON-UI invariants (ADR-0024 §"Per-structure micro-workflows" +
# §"Output contract").  These exercise the orchestrator/UI flow with the
# TotalSegmentator backend MOCKED (a real inference needs a multi-GB model +
# GPU, unavailable in CI), and the scene/widget tests need a launched
# qSlicerApplication -- so they run under the launched-Slicer harness
# (Liver/Testing/Python/run_pytest_launched.py / the `pytest_launched` CTest
# row), NOT the bare-pytest rows.  See Liver/Testing/Python/CMakeLists.txt:
# this module's source dir + Testing/Python root are added to that row's
# --additional-module-paths and test roots.
#
#   * test_liversegmentation_card_run_produces_scratch.py
#     Card Run (mocked backend) -> exactly one scratch node; no premature
#     canonical.  Scene-needing.
#
#   * test_liversegmentation_accept_sct_and_multifocal.py
#     Accept -> single canonical node carrying the correct SCT triple per
#     structure; Tumors lands N separate Mass segments.  Scene-needing.
#
#   * test_liversegmentation_reject_discards_scratch.py
#     Reject -> scratch removed; canonical unchanged.  Scene-needing.
#
#   * test_liversegmentation_structure_accepted_glyph.py
#     isStructureAccepted(sct) (canonical-only read) + per-tab ✓/○ glyph
#     mirroring the Liver-shell idiom.  Scene + widget-needing.
#
#   * test_liversegmentation_backend_status_row.py
#     Stage-2-local backend-status row reflects ensureBackendInstalled;
#     Pre-download calls it confirm=False + mints no node.  The Pre-download
#     hook-purity probe is pure-Python (bare-runnable); the widget assertions
#     are widget-needing.
#
#   * test_liversegmentation_segment_input_selection.py
#     segment() reads the Stage-1 LiverRole='PortalVenous' volume (mocked
#     backend records its volume argument).  Scene-needing.
#
# Same skip-if-pytest-absent pattern as Liver/Testing/Python/CMakeLists.txt
# -- keeps the scaffolding buildable where pytest is not provisioned.

if(NOT BUILD_TESTING)
  return()
endif()

if(NOT Python3_EXECUTABLE)
  message(STATUS
    "Slicer-Liver: Python3_EXECUTABLE not set; "
    "skipping LiverSegmentation pytest registration.")
  return()
endif()

execute_process(
  COMMAND "${Python3_EXECUTABLE}" -c "import pytest"
  RESULT_VARIABLE _liverseg_pytest_probe_rc
  OUTPUT_QUIET
  ERROR_QUIET
)

if(NOT _liverseg_pytest_probe_rc EQUAL 0)
  message(STATUS
    "Slicer-Liver: pytest not importable from ${Python3_EXECUTABLE}; "
    "skipping LiverSegmentation pytest registration.  Install pytest in "
    "the Slicer Python environment to enable these tests.")
  return()
endif()

set(_liverseg_pytest_files
  test_liversegmentation_registration.py
  test_liversegmentation_isstagecomplete_semantics.py
  test_liversegmentation_single_canonical_node.py
  test_liversegmentation_import_purity.py
  test_liversegmentation_conformance.py
  # Stage-2 surgeon-UI invariants (mocked backend; scene/widget tests run
  # green under the launched-Slicer `pytest_launched` row, skip cleanly bare).
  test_liversegmentation_card_run_produces_scratch.py
  test_liversegmentation_accept_sct_and_multifocal.py
  test_liversegmentation_reject_discards_scratch.py
  test_liversegmentation_structure_accepted_glyph.py
  test_liversegmentation_backend_status_row.py
  test_liversegmentation_segment_input_selection.py
  # ADR-0034 increment 1 -- the read-only anatomy segments table:
  # pre-seeded Missing rows + row-status derivation (Missing / Review /
  # Confirmed / Marked-absent) from the canonical node.  Widget-needing
  # (launched `pytest_launched` row); skips cleanly bare.
  test_liversegmentation_segments_table.py
  # SLICE C -- Stage 2 produces the canonical, per-structure-SCT-tagged
  # segmentation by LOADING one (in-app AI deferred to v2.1); pins the
  # importSegmentationAsCanonical logic seam (ADR-0024 §"Output contract",
  # ADR-0011).  Scene-needing (launched `pytest_launched` row); skips cleanly
  # bare.  The vocab-collapse companion (C2) rides the existing pure-Python
  # test_liversegmentation_import_purity.py row.
  test_liversegmentation_import_as_canonical.py
  # T5.2-f -- shared Subject-Hierarchy folder utility reachability +
  # Anatomy placement through vtkSlicerSubjectHierarchyFolders
  # (ADR-0023 §"MRML scene organisation").  Wrapped-C++-from-Python
  # reachability is launched-only; skips cleanly under bare pytest.
  test_liversegmentation_subject_hierarchy_folders_reachability.py
  # #538 -- Stage-2 distance-map computation port.  Pins the PURE SimpleITK
  # core (signed Maurer per channel + compose); runs bare when SimpleITK +
  # NumPy are present, skips cleanly otherwise.  The Slicer-coupled
  # segment-export layer is exercised in the launched harness.
  test_distance_maps.py
  # #539 -- promoting a loaded segmentation to canonical also creates the
  # closed-surface representation + enables 3D visibility, so the anatomy
  # renders through Planning.  Scene-needing (segmentation converter); runs
  # under the launched `pytest_launched` row, skips cleanly bare.
  test_liversegmentation_segment_surface_representation.py
  # #538 trigger -- importing the canonical segmentation also computes the
  # tagged distance map (reference volume from the Stage-1 LiverRole tag;
  # resolve-or-create output; graceful degradation without a reference).
  # Scene-needing (converter + SimpleITK); launched `pytest_launched` row,
  # skips cleanly bare.
  test_liversegmentation_distance_map_on_import.py
)

foreach(_pytest_file IN LISTS _liverseg_pytest_files)
  get_filename_component(_test_basename "${_pytest_file}" NAME_WE)
  add_test(
    NAME ${_test_basename}
    COMMAND "${Python3_EXECUTABLE}" -m pytest
      -q
      "${CMAKE_CURRENT_SOURCE_DIR}/${_pytest_file}"
    WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
  )
  set_tests_properties(${_test_basename} PROPERTIES
    LABELS "pytest;LiverSegmentation;stage2-anatomy"
  )
endforeach()

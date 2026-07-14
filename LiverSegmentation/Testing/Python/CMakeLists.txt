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
#   * test_liversegmentation_toolbar_run_lands_directly.py
#     Selection-scoped toolbar Run (mocked backend) lands the SELECTED
#     row's result directly on the canonical node (native InProgress +
#     source tag; no surviving scratch); no-selection / no-PortalVenous
#     runs are refused with hints; a failed run leaves the canonical
#     untouched (the invariant the retired Reject suite carried).
#     Scene + widget-needing.
#
#   * test_liversegmentation_accept_sct_and_multifocal.py
#     The landing step -> single canonical node carrying the correct SCT
#     triple per structure; Tumors lands N separate Mass segments.
#     Scene-needing.
#
#   * test_liversegmentation_structure_accepted_glyph.py
#     isStructureAccepted(sct) (canonical-only read) logic pins; its
#     tab-glyph consumer retired with the tabs (ADR-0034 §Amendments).
#     Scene-needing.
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
  test_liversegmentation_toolbar_run_lands_directly.py
  test_liversegmentation_accept_sct_and_multifocal.py
  test_liversegmentation_structure_accepted_glyph.py
  test_liversegmentation_backend_status_row.py
  test_liversegmentation_segment_input_selection.py
  # ADR-0034 §Amendments -- the anatomy segments table on Slicer-native
  # primitives: setup mints-and-binds the canonical with its pre-seeded
  # checklist; row-status derivation (Missing / Review / Confirmed /
  # Flagged / Marked-absent) from the native per-segment status; the
  # Mark-absent attestation gesture.  Widget-needing (launched
  # `pytest_launched` row); skips cleanly bare.
  test_liversegmentation_segments_table.py
  # ADR-0034 §Decision 2 -- the import path unifies, as amended: the
  # toolbar Import… gesture opens the explicit-correspondence dialog
  # (one Import-as combo per source segment, skip by default, NO
  # auto-match) and routes the stated mapping through the SAME landing
  # kernel the AI accept path uses (importSegmentation; canonical
  # identity stable; expected-structure identity on landing).  Pins the
  # skip-default/no-prefill table, the "(already present)" annotation,
  # many->1 numbered titles, the never-overwrite rule for
  # landed/Confirmed rows, source-node consumption only on a full
  # mapping, and stock terminology-navigator format recognition
  # (ADR-0011).  Scene/widget-needing (launched `pytest_launched` row);
  # skips cleanly bare.
  test_liversegmentation_import_unified.py
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
  # ADR-0034 §Decision 5 -- the main-thread QProcess job queue replacing the
  # blocking readline+processEvents run path: QUEUED-only (task, input)
  # coalescing (a key matching the RUNNING job rides a NEW sequential child
  # -- the running command line is frozen at start), strict sequencing,
  # cancel reaping the child's whole process tree without a GUI-thread
  # block, shutdown leaving no child (real slow stub children via an
  # injected command builder -- never a real inference), plus the widget
  # contract (enqueue is STATUS-NEUTRAL -- the native InProgress flip and
  # the demote-from-Completed staleness rule both ride the LANDING;
  # landing keeps InProgress; multi-select Run grouped per task -- there is
  # NO Segment-anatomy macro, multi-select Run subsumes it, ADR-0034
  # §Amendments).  Launched `pytest_launched` row; skips cleanly bare.
  test_liversegmentation_job_queue.py
  # ADR-0034 §Amendments item 4 -- the embedded Segment Editor increment:
  # a stock qMRMLSegmentEditorWidget in a collapsed ctkCollapsibleButton
  # under the table (own non-singleton editor node, curated effects,
  # selectors hidden, canonical + PortalVenous pinned); row-selection /
  # Edit-button sync (the jump-to-module path is deleted); and the
  # demote-on-edit staleness rule (content edit to a Completed segment ->
  # InProgress via vtkSegmentation::SourceRepresentationModified; status-
  # tag writes and the pre-seed/landing paths never spuriously demote).
  # Widget-needing (launched `pytest_launched` row); skips cleanly bare.
  test_liversegmentation_embedded_editor.py
  # ADR-0034 §Decision 6 -- the validate-and-next SEAM (the shell's
  # "Validate and next" button itself stays with the phase-contracts work
  # #440; this ships what it needs): the logic's explainStageIncomplete()
  # naming the unsatisfied structures (title + status text), derived
  # through the SAME structureStatus the completion predicate reads so they
  # cannot drift (isStageComplete() iff the explanation is empty); the
  # widget's markUnresolvedRows()/clearUnresolvedMarks() marking mechanism
  # (SELECT the offenders + a glyph+text summary line, never colour alone,
  # ADR-0010 -- the stock model exposes no safe per-row background role);
  # the local "Validate anatomy" affordance; and the LIVE clear (a status
  # flip to Completed / a landing drops the row's mark without re-clicking
  # Validate, riding the existing canonical-segmentation observation with
  # the digest discipline).  Widget-needing (launched `pytest_launched`
  # row); skips cleanly bare.
  test_liversegmentation_validate_seam.py
  # Packaging parity for the LiverSegmentationLib sub-package: every source
  # .py appears in LiverSegmentationLib_PYTHON_SCRIPTS (and no stale
  # entries), or an omitted file silently vanishes from a fresh build and
  # `import LiverSegmentationLib.<name>` fails at runtime.  Same drift class
  # the LiverResectionsLib parity test guards.  Pure-Python; runs bare.
  test_liversegmentationlib_packaging_parity.py
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

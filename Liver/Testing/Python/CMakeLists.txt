# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
#
# Pytest registration for the Liver-shell sidebar tests (T5.2-d).
#
# Three test files exercise the invariants pinned by the T5.2-d
# planner output:
#
#   * test_liver_shell_sidebar.py            (T1, T4, T5, T6)
#     Widget-level: sidebar entries, dispatch, widget identity,
#     state-indicator refresh.
#
#   * test_liver_shell_isstagecomplete.py    (T2, T3)
#     IsStageComplete()  symbol existence + scene-level semantics
#     per stage.  Requires the LiverResections / VascularTerritories
#     / LiverVolumetry modules to be on the additional-module-paths.
#
#   * test_liver_shell_no_domain_imports.py  (T7)
#     Static AST check on Liver/Liver.py; pure-Python, no Slicer
#     required.  Always runnable.
#
# Same skip-if-pytest-absent pattern as Testing/Python/CMakeLists.txt
# and LiverResections/Testing/Python/CMakeLists.txt — keeps the
# scaffolding buildable in environments where pytest hasn't been
# provisioned.

if(NOT BUILD_TESTING)
  return()
endif()

if(NOT Python3_EXECUTABLE)
  message(STATUS
    "Slicer-Liver: Python3_EXECUTABLE not set; "
    "skipping Liver-shell sidebar pytest registration.")
  return()
endif()

execute_process(
  COMMAND "${Python3_EXECUTABLE}" -c "import pytest"
  RESULT_VARIABLE _liver_pytest_probe_rc
  OUTPUT_QUIET
  ERROR_QUIET
)

if(NOT _liver_pytest_probe_rc EQUAL 0)
  message(STATUS
    "Slicer-Liver: pytest not importable from ${Python3_EXECUTABLE}; "
    "skipping Liver-shell sidebar pytest registration.  Install "
    "pytest in the Slicer Python environment to enable these tests.")
  return()
endif()

# Each test file gets its own CTest entry so failures are isolable
# (matches the per-scenario pattern from
# LiverResections/Testing/Python/CMakeLists.txt).
set(_liver_shell_pytest_files
  test_liver_shell_sidebar.py
  test_liver_shell_isstagecomplete.py
  test_liver_shell_no_domain_imports.py
  # Harness-contract + skip-path-preservation guards for the launched-
  # Slicer pytest driver (run_pytest_launched.py).  See ADR-0008 §6.
  test_run_pytest_launched_contract.py
  test_bare_pytest_skip_path_preserved.py
)

foreach(_pytest_file IN LISTS _liver_shell_pytest_files)
  # Drop the .py suffix for the CTest name.
  get_filename_component(_test_basename "${_pytest_file}" NAME_WE)
  add_test(
    NAME ${_test_basename}
    COMMAND "${Python3_EXECUTABLE}" -m pytest
      -q
      "${CMAKE_CURRENT_SOURCE_DIR}/${_pytest_file}"
    WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
  )
  set_tests_properties(${_test_basename} PROPERTIES
    LABELS "pytest;Liver;sidebar-T5.2-d"
  )
endforeach()

# Stage-1 Case-Setup volume-role vocabulary + tagging seam (ADR-0029 §Stage 1;
# ADR-0023 §"Stage 1"; ADR-0004 §"Python/C++ boundary" -- the Qt panel vs the
# pure-Python role seam).  Pins a NEW shared role module
# ``SlicerLiverCommonLib.roles`` importable by BOTH the Liver shell (Case Setup,
# the role WRITER) and LiverSegmentation (Stage 2, the role READER): the fixed
# ``LiverRole`` scene-attribute key + the five machine-stable CamelCase values
# (Native / Arterial / PortalVenous / Delayed / Other, NO spaces) + a
# ``set_volume_role(volume, role) -> bool`` tagging seam (validates the role,
# writes the attribute, no-op-False on an unknown role or a None volume).
# Collapses the vocabulary drift between LiverSegmentation.py's ad-hoc constants
# and the arch doc's spaced labels into one shared module.  Invariant 1 (the
# vocabulary) needs no scene and runs everywhere the module imports; invariants
# 2--3 (tagging + the Stage-1 completion predicate) mint a
# vtkMRMLScalarVolumeNode on the live scene, so they run green under the
# launched-Slicer `pytest_launched` row and SKIP CLEANLY here under bare pytest
# (no slicer.mrmlScene).  GL-free -- only node attributes + a scene-level
# predicate (the body of LiverWidget._stage1IsComplete) are asserted, no view /
# render window.  RED / skip-pending (guards on the SlicerLiverCommonLib.roles
# import + the set_volume_role seam) until the implementer lands the shared
# module (ADR-0027 §Conformance: the skip lifts at the implementation commit).
add_test(
  NAME LiverCaseSetupVolumeRoles
  COMMAND "${Python3_EXECUTABLE}" -m pytest
    -q
    "${CMAKE_CURRENT_SOURCE_DIR}/test_case_setup_volume_roles.py"
  WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
)
set_tests_properties(LiverCaseSetupVolumeRoles PROPERTIES
  LABELS "pytest;module-layer;Liver;case-setup"
)

# --------------------------------------------------------------------------- #
# pytest_launched — same test roots as pytest_scaffold, inside a launched
# Slicer.
# --------------------------------------------------------------------------- #
#
# The bare ``pytest_scaffold`` entries (Testing/Python/CMakeLists.txt) run the
# project pytest tree under bare PythonSlicer: fast, offscreen, and the
# widget-level Liver-shell tests SKIP cleanly via conftest._require_qt_widget.
#
# ``pytest_launched`` is ADDITIVE: it runs the SAME test roots inside a real
# ``qSlicerApplication`` so the widget-level tests actually execute.  Slicer is
# launched via ``--python-script`` against the thin driver
# ``run_pytest_launched.py``, which calls ``pytest.main([...roots...])`` and
# routes the integer exit code through ``slicer.util.exit`` — the
# exit-propagation pattern proven by LiverResections/Testing/Python/
# replay_test.py (``_exit`` helper).  Without that funnel the process would
# hang in Slicer's event loop and report the wrong status (ADR-0008 §6).
#
# Modules are ENABLED (no ``--disable-modules``): the full module set must be
# importable for the widget-level shell tests, so CMake supplies
# ``--additional-module-paths`` pointed at the BUILT module trees (see the
# ``_liver_additional_module_paths`` block below) plus ``--testing`` and the
# generated launcher-settings INI so the loadable modules and their LayerDM
# dependency actually register.
#
# Local-run hint (NOT baked into the COMMAND): when a developer's Slicer Python
# lacks ``highdicom``, pytest collection of the bundled DICOMTID1500Plugin can
# error; pass ``--modules-to-ignore DICOMTID1500Plugin`` locally.  CI's image
# ships ``highdicom``, so the CTest COMMAND omits it to keep the gate honest.

# Probe for the Slicer launcher (same convention as
# LiverResections/Testing/Python/CMakeLists.txt).
if(DEFINED Slicer_LAUNCHER_EXECUTABLE)
  set(_slicer_launcher "${Slicer_LAUNCHER_EXECUTABLE}")
elseif(DEFINED Slicer_EXECUTABLE)
  set(_slicer_launcher "${Slicer_EXECUTABLE}")
else()
  message(STATUS
    "Slicer-Liver: neither Slicer_LAUNCHER_EXECUTABLE nor Slicer_EXECUTABLE "
    "is defined; skipping pytest_launched registration.")
  return()
endif()

# Full in-tree module set for ``--additional-module-paths``, pointed at the
# BUILT per-config module trees rather than the source dirs.  All Liver*
# modules build into the same shared ``qt-loadable-modules`` /
# ``qt-scripted-modules`` trees, so the two built dirs cover every in-tree
# module at once.  Source dirs make a *scripted* module importable but a
# *loadable* (C++) module's Python sub-package (``LiverResectionsLib``, which
# carries the LayerDM Pipelines/Representations) only lands on ``sys.path``
# from the built ``qt-scripted-modules`` tree (ADR-0013 §5) — pointing at
# source is why the launched widget tests silently skipped.
set(_liver_additional_module_paths
  "${CMAKE_BINARY_DIR}/${Slicer_QTSCRIPTEDMODULES_LIB_DIR}"
  "${CMAKE_BINARY_DIR}/${Slicer_QTLOADABLEMODULES_LIB_DIR}"
  # SlicerLayerDisplayableManager dependency: ``LiverResectionsLib``
  # hard-imports ``LayerDMLib`` (ADR-0013 §5, SlicerLayerDM as a hard
  # EXTENSION_DEPENDS), so the LayerDM modules must be registered with the
  # module manager, not merely import-able.  Mirrors VascularTerritories.
  "${LayerDisplayableManager_DIR}/${Slicer_QTLOADABLEMODULES_LIB_DIR}"
  "${LayerDisplayableManager_DIR}/${Slicer_QTSCRIPTEDMODULES_LIB_DIR}"
)

# Same test roots as the bare ``pytest_scaffold`` entries, plus the Stage-2
# surgeon-UI invariant tree: its scene/widget tests SKIP under bare pytest and
# only execute meaningfully inside a launched qSlicerApplication (ADR-0024).
# Root ORDER is load-bearing: pytest prepends every root's conftest dir to
# sys.path at session start, so the LAST-listed root wins any test's plain
# `import conftest`.  LiverSegmentation's tests import their conftest by
# name (23 sites), so its root stays LAST; the Liver shell root -- whose
# tests import the shared slicer_pytest_support instead -- goes first.
set(_launched_test_roots
  # The Liver shell's own suites: widget-level, so they skip under the
  # bare rows -- omitting this root meant they executed NOWHERE in CI
  # and drifted silently (11 failures accumulated unseen).
  "${CMAKE_SOURCE_DIR}/Liver/Testing/Python"
  "${CMAKE_SOURCE_DIR}/Testing/Python"
  "${CMAKE_SOURCE_DIR}/LiverResections/Testing/Python"
  "${CMAKE_SOURCE_DIR}/VascularTerritories/Testing/Python"
  "${CMAKE_SOURCE_DIR}/LiverSegmentation/Testing/Python"
)

add_test(
  NAME pytest_launched
  COMMAND "${_slicer_launcher}"
    --no-main-window
    --no-splash
    # --testing runs against fresh temporary settings so the launcher does NOT
    # inherit the developer's persisted Modules/AdditionalPaths (stale paths to
    # removed build trees otherwise surface as "The shared library was not
    # found." at module registration and the launched tests skip).
    --testing
    # Diagnostic for the #460 launched-registration gap: dumps the module
    # discovery/instantiation/load process so a CI log shows WHICH modules fail
    # (liverresections / liversegmentation / core cameras+segmentations were
    # absent from slicer.modules) and why.  Cheap; remove once #460 is closed.
    # Generated AdditionalLauncherSettings.ini: puts this build's and the
    # SlicerLayerDisplayableManager dependency's library + PYTHONPATH entries on
    # the launcher so the module .so files and their LayerDM-linked dependencies
    # resolve at load time.  Expands to "--launcher-additional-settings <ini>".
    ${Slicer_ADDITIONAL_LAUNCHER_SETTINGS}
    --additional-module-paths ${_liver_additional_module_paths}
    --python-script "${CMAKE_CURRENT_SOURCE_DIR}/run_pytest_launched.py"
    --
    ${_launched_test_roots}
  WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
)
set_tests_properties(pytest_launched PROPERTIES
  LABELS "pytest;launched"
)

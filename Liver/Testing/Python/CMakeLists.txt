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
# ``--additional-module-paths`` for the in-tree modules.
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

# Full in-tree module set for ``--additional-module-paths``.  Each entry is a
# module source dir whose scripted/loadable module Slicer must discover so the
# launched widget-level tests can import it.  Keep in sync with the top-level
# CMakeLists.txt module list.
set(_liver_additional_module_paths
  "${CMAKE_SOURCE_DIR}/Liver"
  "${CMAKE_SOURCE_DIR}/LiverResections"
  "${CMAKE_SOURCE_DIR}/LiverMarkups"
  "${CMAKE_SOURCE_DIR}/LiverVolumetry"
  "${CMAKE_SOURCE_DIR}/VascularTerritories"
)

# Same test roots as the bare ``pytest_scaffold`` entries.
set(_launched_test_roots
  "${CMAKE_SOURCE_DIR}/Testing/Python"
  "${CMAKE_SOURCE_DIR}/LiverResections/Testing/Python"
)

add_test(
  NAME pytest_launched
  COMMAND "${_slicer_launcher}"
    --no-main-window
    --no-splash
    --additional-module-paths ${_liver_additional_module_paths}
    --python-script "${CMAKE_CURRENT_SOURCE_DIR}/run_pytest_launched.py"
    --
    ${_launched_test_roots}
  WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
)
set_tests_properties(pytest_launched PROPERTIES
  LABELS "pytest;launched"
)

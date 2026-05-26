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

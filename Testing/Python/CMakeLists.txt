# CTest registration for the shared pytest scaffold.
# See Docs/adr/0008-testing-strategy.md §6 (CI matrix).
#
# Two CTest entries here register the *same* test tree twice, mirroring
# the CI matrix described in ADR-0008 §6:
#
#   pytest_scaffold                  — bare ``pytest`` (offscreen, fast)
#   pytest_scaffold_render_interactive
#                                    — ``pytest --render-interactive=0.1``
#                                      (briefly onscreen; exercises the
#                                      ShowWindowOn() path)
#
# A third matrix row lives in Liver/Testing/Python/CMakeLists.txt because
# it depends on the Slicer launcher and the in-tree module set:
#
#   pytest_launched                  — the SAME test roots run inside a
#                                      launched ``qSlicerApplication``
#                                      (Slicer ``--python-script`` →
#                                      ``run_pytest_launched.py``).  This
#                                      is ADDITIVE: the widget-level
#                                      Liver-shell tests that SKIP on the
#                                      bare row (conftest._require_qt_widget)
#                                      actually execute here.  pytest's exit
#                                      code is funnelled through
#                                      ``slicer.util.exit`` so a red run
#                                      surfaces as a non-zero process exit
#                                      (fail-closed; ADR-0008 §6).
#
# Both entries are gated on ``Python3_EXECUTABLE`` (provided by Slicer's
# CMake macros) and on the presence of ``pytest`` in the active Python.
# When pytest is not available the entries are skipped at configure time
# rather than failing the build — this keeps the scaffold buildable in
# environments where the pytest dependency hasn't been provisioned yet
# (the slicer-build-ubuntu2404 CI image will need pytest added; tracked
# as a follow-up to this PR — see ALive-Docker).

if(NOT Python3_EXECUTABLE)
  message(STATUS
    "Slicer-Liver: Python3_EXECUTABLE not set; "
    "skipping pytest scaffold registration.")
  return()
endif()

# Probe for pytest in the configured Python.  ``execute_process`` with
# ``RESULT_VARIABLE`` returns 0 when the import succeeds.
execute_process(
  COMMAND "${Python3_EXECUTABLE}" -c "import pytest"
  RESULT_VARIABLE _pytest_probe_rc
  OUTPUT_QUIET
  ERROR_QUIET
)

if(NOT _pytest_probe_rc EQUAL 0)
  message(STATUS
    "Slicer-Liver: pytest not importable from ${Python3_EXECUTABLE}; "
    "skipping pytest scaffold registration.  Install pytest in the "
    "Slicer Python environment to enable these tests.")
  return()
endif()

# ``-q`` keeps the CTest log short on success; ``-ra`` (from pytest.ini)
# still surfaces non-pass summary lines.
add_test(
  NAME pytest_scaffold
  COMMAND "${Python3_EXECUTABLE}" -m pytest
    -q
    "${CMAKE_SOURCE_DIR}/Testing/Python"
  WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
)
set_tests_properties(pytest_scaffold PROPERTIES
  LABELS "pytest;offscreen"
)

add_test(
  NAME pytest_scaffold_render_interactive
  COMMAND "${Python3_EXECUTABLE}" -m pytest
    -q
    --render-interactive=0.1
    "${CMAKE_SOURCE_DIR}/Testing/Python"
  WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
)
set_tests_properties(pytest_scaffold_render_interactive PROPERTIES
  LABELS "pytest;onscreen-brief"
)

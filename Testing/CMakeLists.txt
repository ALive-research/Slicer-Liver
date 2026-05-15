# Shared (cross-module) pytest scaffolding for Slicer-Liver.
# See Docs/adr/0008-testing-strategy.md.
#
# Per-module Slicer self-tests continue to live under
# <Module>/Testing/Python/ and register via ``slicer_add_python_unittest``;
# this directory is the home for shared pytest scaffolding (conftest,
# render_interactive option, cross-module fixtures) and for tests that
# span more than one module.

if(BUILD_TESTING)
  add_subdirectory(Python)
endif()

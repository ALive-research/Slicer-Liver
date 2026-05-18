# Visual-regression test harness for the LiverResections module.
#
# Per ADR-0003 (testability invariant) and ADR-0020 §"Rollout plan"
# §7, the characterisation tests for the v2.0.0 Bezier mapper gate the
# v2.1 GPU-tessellation rewrite.  This file wires the CMake side:
#
#   * Pulls baseline bundle assets (PNG + MRML + camera + viewport JSON)
#     from the ALive-research/ALiveResearchTestingData repository via the
#     ``ExternalData`` CMake module, using 64-byte ``.sha512`` content
#     hash stubs committed under ``Data/Baseline/``.
#   * Registers one CTest entry per visual-regression scenario; each
#     entry invokes Slicer with ``--no-main-window --python-script
#     replay_test.py --test <name>``.
#
# See ``LiverResections/Testing/README.md`` for the capture / upload
# / replay workflow and the rules for bumping the baseline tag.

# ---------------------------------------------------------------------------
# ExternalData wiring
# ---------------------------------------------------------------------------
#
# Slicer's ``UseSlicer.cmake`` pre-populates ``ExternalData_URL_TEMPLATES``
# and ``ExternalData_OBJECT_STORES`` from the Slicer-core defaults
# (see Slicer ``CMake/UseSlicer.cmake.in`` §"ExternalData").  Append our
# ALiveResearchTestingData URL template here so ``DATA{...}`` references in
# ``ExternalData_add_test()`` resolve from the Slicer-Liver release
# bucket first, falling back to the Slicer-core sources for any
# overlap.

if(NOT BUILD_TESTING)
  return()
endif()

# ---------------------------------------------------------------------------
# Opt-in gate for the visual-regression harness.
#
# Default OFF until two preconditions land: (a) the
# ``ALive-research/ALiveResearchTestingData`` release tag holding captured
# baselines, and (b) confirmation that Slicer's launcher exits cleanly
# in the no-baseline path under ``--no-main-window --disable-modules
# --python-script`` (the Qt application event loop has been observed
# to not yield in initial CI runs; triage tracked in the PR).
#
# CI default OFF means scaffolding PRs go green without the CTest
# entries firing; flip to ON locally (or via workflow env override)
# once both preconditions are satisfied.
option(Slicer_Liver_ENABLE_VISUAL_TESTS
  "Enable Slicer-Liver visual-regression CTest entries (requires baselines + clean launcher-exit; see LiverResections/Testing/README.md)."
  OFF)

if(NOT Slicer_Liver_ENABLE_VISUAL_TESTS)
  message(STATUS
    "Slicer-Liver: visual-regression tests gated OFF "
    "(set -DSlicer_Liver_ENABLE_VISUAL_TESTS=ON to enable).")
  return()
endif()

include(ExternalData)

# Slicer-core defaults may already be set; append rather than replace
# so Slicer's MIDAS / GitHub mirrors continue to work for any shared
# fixtures the suite eventually pulls.
list(APPEND ExternalData_URL_TEMPLATES
  # ALiveResearchTestingData follows the SlicerTestingData mirror
  # pattern: one release per hash algorithm (``SHA256``, ``SHA512``,
  # …); release assets are named by their ``<hashsum>`` with no
  # per-purpose prefix; a sibling ``<HASHALGO>.csv`` in the repo root
  # maps ``<hashsum>;<filename>``.  The visual-regression harness
  # uses ``.sha512`` stubs (CMake's ExternalData default for new
  # work) and resolves them against the ``SHA512`` release.
  #
  # When baselines change due to a Slicer/VTK/image bump, the
  # ``.sha512`` stubs under ``Data/Baseline/`` rotate to point at
  # the new hashes; the old assets stay in the ``SHA512`` release
  # (content-addressed; no overwrites).
  "https://github.com/ALive-research/ALiveResearchTestingData/releases/download/%(algo)/%(hash)"
)

# Per-build object store so multiple checkouts on the same machine
# share the downloaded blobs.  Falls back to a build-tree-local store
# when the variable is unset.
if(NOT DEFINED ExternalData_OBJECT_STORES OR ExternalData_OBJECT_STORES STREQUAL "")
  set(ExternalData_OBJECT_STORES "${CMAKE_BINARY_DIR}/ExternalData/Objects")
endif()

set(_baseline_dir "${CMAKE_CURRENT_SOURCE_DIR}/../Data/Baseline")
set(_scenarios_dir "${CMAKE_CURRENT_SOURCE_DIR}/scenarios")

# ---------------------------------------------------------------------------
# CTest registration
# ---------------------------------------------------------------------------
#
# Each scenario gets one CTest entry.  The replay driver
# (``replay_test.py``) loads the named scenario module, sets up the
# scene + camera + viewport, captures a screenshot offscreen, and
# compares pixel-wise against the resolved baseline PNG.

# Probe for the Slicer launcher.  ``Slicer_LAUNCHER_EXECUTABLE`` is
# defined by the parent UseSlicer.cmake when Slicer is found.  Fall
# back to ``Slicer_EXECUTABLE`` for older Slicer trees.
if(DEFINED Slicer_LAUNCHER_EXECUTABLE)
  set(_slicer_launcher "${Slicer_LAUNCHER_EXECUTABLE}")
elseif(DEFINED Slicer_EXECUTABLE)
  set(_slicer_launcher "${Slicer_EXECUTABLE}")
else()
  message(STATUS
    "Slicer-Liver: neither Slicer_LAUNCHER_EXECUTABLE nor Slicer_EXECUTABLE "
    "is defined; skipping LiverBezierVisualTest registration.")
  return()
endif()

# Scenarios participating in the harness.  Add new entries here; each
# name must match a Python module under ``scenarios/`` and a set of
# ``.sha512`` stubs under ``../Data/Baseline/``.
set(_visual_test_scenarios
  BezierSurface4x4Planning
  BezierSurface4x4Confirmed
)

# Bundle extensions per scenario.  ``.png`` is the comparison target;
# ``.mrml`` re-loads the captured scene; ``.camera.json`` / ``.viewport.json``
# carry the deterministic render configuration.  Keep this list in sync
# with the capture driver (``capture_baseline.py``) and the upload
# script (``Scripts/upload_baseline.sh``).
set(_baseline_exts
  png
  mrml
  camera.json
  viewport.json
)

foreach(_scenario IN LISTS _visual_test_scenarios)
  set(_data_args "")
  foreach(_ext IN LISTS _baseline_exts)
    set(_stub "${_baseline_dir}/${_scenario}.${_ext}.sha512")
    if(EXISTS "${_stub}")
      list(APPEND _data_args "DATA{${_stub}}")
    else()
      # Stub not committed yet — the maintainer's first capture session
      # produces it.  Register the test anyway so the wiring shape is
      # exercised by CI; the test driver itself skips with a clear
      # message until the stub lands.
      message(STATUS
        "Slicer-Liver: baseline stub missing for ${_scenario}.${_ext}; "
        "test will skip at runtime until capture lands.")
    endif()
  endforeach()

  set(_testname "LiverBezierVisualTest_${_scenario}")
  ExternalData_add_test(LiverBezierVisualTestData
    NAME ${_testname}
    COMMAND "${_slicer_launcher}"
      --no-main-window
      --no-splash
      --disable-modules
      --python-script "${CMAKE_CURRENT_SOURCE_DIR}/replay_test.py"
      --
      --test ${_scenario}
      --baseline-dir "${_baseline_dir}"
      --scenarios-dir "${_scenarios_dir}"
      ${_data_args}
  )
  set_tests_properties(${_testname} PROPERTIES
    LABELS "visual-regression;LiverResections"
    # CI image and the Slicer launcher both export
    # ``QT_QPA_PLATFORM=offscreen`` already; the env line below is a
    # belt-and-braces safeguard for local runs.
    ENVIRONMENT "QT_QPA_PLATFORM=offscreen"
  )
endforeach()

# Aggregate fetch target.  ``make LiverBezierVisualTestData`` pulls
# every referenced blob without running CTest — useful for warming the
# ExternalData cache before a CI run or before going offline.
ExternalData_add_target(LiverBezierVisualTestData)

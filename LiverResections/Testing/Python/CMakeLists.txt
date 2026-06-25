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
# Harness self-tests (always-on)
# ---------------------------------------------------------------------------
#
# Pure-Python pytest covering the visual-regression harness's own
# helpers (``_has_baseline``, ``_resolve_baseline_png``,
# ``_save_bundle``) and the ``upload_baseline.sh`` bundle-completeness
# pre-flight.  Tracked separately from the visual-regression CTest
# entries below because these tests do not need:
#
#   * the Slicer launcher (they stub ``slicer`` / ``qt`` / ``vtk``
#     into ``sys.modules`` before importing ``capture_baseline``);
#   * captured baselines on the ALiveResearchTestingData release
#     (each test materialises its own fixture under
#     pytest's ``tmp_path``);
#   * the ``SlicerLiver_ENABLE_VISUAL_TESTS`` opt-in gate (which
#     defers the full visual-regression CTest entries until
#     baselines + launcher-exit have been confirmed on CI).
#
# Skipped gracefully when ``pytest`` is not importable from the
# configured Python — same pattern as the cross-module
# ``pytest_scaffold`` entry under ``Testing/Python/CMakeLists.txt``.
# See ADR-0008 §"observability" + issue #387.

if(DEFINED Python3_EXECUTABLE)
  execute_process(
    COMMAND "${Python3_EXECUTABLE}" -c "import pytest"
    RESULT_VARIABLE _liver_resections_pytest_probe_rc
    OUTPUT_QUIET
    ERROR_QUIET
  )
  if(_liver_resections_pytest_probe_rc EQUAL 0)
    add_test(
      NAME LiverResections_harness_self_tests
      COMMAND "${Python3_EXECUTABLE}" -m pytest
        -q
        "${CMAKE_CURRENT_SOURCE_DIR}/test_harness"
      WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
    )
    set_tests_properties(LiverResections_harness_self_tests PROPERTIES
      LABELS "pytest;harness-self-tests;LiverResections"
    )

    # Module-layer invariants for the distance-map computation
    # (ADR-0008 §2; ADR-0023 §"Shell composition (Option H)").  Registered
    # as its own CTest entry rather than swept into the repo-root
    # ``pytest_scaffold`` collection because ``pytest.ini`` scopes
    # ``testpaths`` to ``Testing/Python`` only — ``<Module>/Testing/Python``
    # trees need explicit registration here.  The test imports the
    # ``DistanceMaps`` module and skips cleanly (via
    # ``pytest.importorskip``) when Slicer / SimpleITK are unavailable,
    # so this entry is green on a plain pytest run as well as inside a
    # launched Slicer.
    add_test(
      NAME LiverResections_distance_maps
      COMMAND "${Python3_EXECUTABLE}" -m pytest
        -q
        "${CMAKE_CURRENT_SOURCE_DIR}/test_distance_maps.py"
      WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
    )
    set_tests_properties(LiverResections_distance_maps PROPERTIES
      LABELS "pytest;module-layer;LiverResections"
    )

    # T5.2-f -- Subject-Hierarchy collection invariant (ADR-0023
    # §"MRML scene organisation"): the wrapper vtkMRMLLiverResectionNode
    # collects under a scene-root "Resections" folder; the hidden Bezier
    # carrier does NOT.  Scene + live-NodeAdded-observer needing, so it
    # runs green under the launched-Slicer `pytest_launched` row
    # (Liver/Testing/Python; this dir is already on its test roots) and
    # SKIPS CLEANLY here under bare pytest (no slicer.mrmlScene).  RED /
    # skip-pending until the implementer wires the logic's
    # OnMRMLSceneNodeAdded to vtkSlicerSubjectHierarchyFolders.
    add_test(
      NAME LiverResections_subject_hierarchy_collection
      COMMAND "${Python3_EXECUTABLE}" -m pytest
        -q
        "${CMAKE_CURRENT_SOURCE_DIR}/test_resections_subject_hierarchy_collection.py"
      WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
    )
    set_tests_properties(LiverResections_subject_hierarchy_collection PROPERTIES
      LABELS "pytest;module-layer;LiverResections;subject-hierarchy"
    )

    # Stack-4 ring-extraction wiring -- Constraint 3 (issue-337): ring
    # extraction runs ONCE on the Init->Planning commit transition
    # (ADR-0019), NOT per drag; and the Init Representation consumes the
    # weakref'd target mesh (ADR-0014 §1, GetTargetModelNode()).  Needs the
    # wrapped vtkMRMLBezierSurfaceNode + a real target model + the Pipeline's
    # commit() seam, so it runs green under the launched-Slicer
    # `pytest_launched` row and SKIPS CLEANLY here under bare pytest (no
    # slicer.mrmlScene / commit() seam absent).  RED / skip-pending until the
    # implementer lands the commit boundary + the TODO(T2-target-mesh-weakref)
    # wiring.
    add_test(
      NAME LiverResections_ring_extraction_on_commit
      COMMAND "${Python3_EXECUTABLE}" -m pytest
        -q
        "${CMAKE_CURRENT_SOURCE_DIR}/test_resections_ring_extraction_on_commit.py"
      WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
    )
    set_tests_properties(LiverResections_ring_extraction_on_commit PROPERTIES
      LABELS "pytest;module-layer;LiverResections;ring-extraction"
    )

    # Per-point control-grid setter is Python-wrappable -- vtkMRMLBezierSurfaceNode
    # SetControlPoint(row, col, x, y, z) is reachable from Python (the flat
    # SetControlGrid(const double*) is not) and round-trips via
    # GetControlGridVector.  The grid seam a re-baseline scenario / interaction
    # code uses to position the v2 surface.  Needs the wrapped node, so it runs
    # green under the launched-Slicer `pytest_launched` row and SKIPS CLEANLY
    # here under bare pytest (no slicer.mrmlScene).
    add_test(
      NAME LiverResections_parametric_surface_setcontrolpoint
      COMMAND "${Python3_EXECUTABLE}" -m pytest
        -q
        "${CMAKE_CURRENT_SOURCE_DIR}/test_parametric_surface_setcontrolpoint.py"
      WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
    )
    set_tests_properties(LiverResections_parametric_surface_setcontrolpoint PROPERTIES
      LABELS "pytest;module-layer;LiverResections;parametric-surface"
    )

    # T2-mapper-wiring -- BezierPlanningRepresentation drives the real,
    # relocated vtkOpenGLBezierResectionPolyDataMapper (ADR-0014 §3) rendering
    # the tessellated Bezier patch (vtkBezierSurfaceSource + vtkPolyDataNormals
    # + uvCoords) instead of the placeholder control mesh through a generic
    # vtkPolyDataMapper, and plumbs the display node's colour/grid fields onto
    # the mapper uniforms (ports vtkSlicerBezierSurfaceRepresentation3D).  This
    # is the slice that unblocks the ADR-0025 locator consumer (#489).  Needs
    # the wrapped real mapper + bezier source + vtkMRMLBezierSurfaceNode /
    # vtkMRMLParametricSurfaceDisplayNode, so it runs green under the
    # launched-Slicer `pytest_launched` row and SKIPS CLEANLY here under bare
    # pytest (no slicer.mrmlScene / wrapped widget classes off the path).  GL
    # free -- no render.  RED / skip-pending until the implementer swaps the
    # mapper + ports the tessellation (ADR-0027 §Conformance: the skip lifts at
    # the implementation commit).
    add_test(
      NAME LiverResections_bezier_planning_surface_mapper_wiring
      COMMAND "${Python3_EXECUTABLE}" -m pytest
        -q
        "${CMAKE_CURRENT_SOURCE_DIR}/test_bezier_planning_surface_mapper_wiring.py"
      WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
    )
    set_tests_properties(LiverResections_bezier_planning_surface_mapper_wiring PROPERTIES
      LABELS "pytest;module-layer;LiverResections;mapper-wiring"
    )

    # T3-g3 -- auto-populate of the Stage-4 ResectionPlanningWidget (the Python
    # widget, ADR-0004; ADR-0023 §Stage-4).  Three invariants: (1) the drawer
    # auto-populates iff a vtkMRMLMarkupsBezierSurfaceNode is selected AND
    # GetDistanceMapVolumeNode() is non-null (state-orthogonal, NOT gated on
    # ADR-0019 ResectionState); (2) triggering ensures EXACTLY ONE
    # vtkMRMLResectogramDisplayNode on the surface, idempotent on re-trigger;
    # (3) it ensures the singleton resectogram view node via
    # ResectogramViewManager.ensureViewNode(), idempotent on re-trigger.  The
    # test builds LiverResectionsLib.ResectionPlanningWidget directly under a
    # launched qSlicerApplication, so it runs green under the launched-Slicer
    # `pytest_launched` row (Liver/Testing/Python; this dir is already on its
    # test roots) and SKIPS CLEANLY here under bare pytest (no qt.QWidget /
    # no widget).
    add_test(
      NAME LiverResections_resectogram_open_view_action
      COMMAND "${Python3_EXECUTABLE}" -m pytest
        -q
        "${CMAKE_CURRENT_SOURCE_DIR}/test_resectogram_open_view_action.py"
      WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
    )
    set_tests_properties(LiverResections_resectogram_open_view_action PROPERTIES
      LABELS "pytest;module-layer;LiverResections;resectogram;stage4"
    )

    # T3-g3c -- presentation fixes for the "Open resectogram view" action
    # (ADR-0023 §Stage-4; ADR-0025 §Context; ADR-0013 §5 -- config, no custom
    # DM).  Four invariants extending the g3/g3b ensure+embed surface, all
    # GPU-free: (A) the vtkMRMLResectogramDisplayNode is restricted TO the
    # singleton resectogram view (ViewNodeIDs == [view ID]); (B) the selected
    # surface's own display node(s) are restricted AWAY from that view
    # (owned-anatomy restriction; unknown-anatomy isolation deferred); (C) the
    # view's vtkMRMLCameraNode is PARALLEL projection framed on the flattened
    # (u,v) quad centre; (D) the embedded qMRMLThreeDWidget has Expanding
    # horizontal size policy + a non-trivial minimumHeight so it fills the
    # panel.  A--C run under the launched-Slicer `pytest_launched` row
    # (Liver/Testing/Python; this dir is already on its test roots); D is gated
    # behind a main window (the embed needs a realized GL context) exactly as
    # g3b's embed test is.  SKIPS CLEANLY here under bare pytest (no qt.QWidget
    # / no widget rep).  RED / skip-pending until the implementer lands the
    # display-node restriction + the frameCamera path + the Expanding layout
    # (ADR-0027 §Conformance: the skip lifts at the implementation commit).
    add_test(
      NAME LiverResections_resectogram_open_view_presentation
      COMMAND "${Python3_EXECUTABLE}" -m pytest
        -q
        "${CMAKE_CURRENT_SOURCE_DIR}/test_resectogram_open_view_presentation.py"
      WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
    )
    set_tests_properties(LiverResections_resectogram_open_view_presentation PROPERTIES
      LABELS "pytest;module-layer;LiverResections;resectogram;stage4"
    )

    # T3-g3 -- custom enlarge/restore of the embedded resectogram widget
    # (ADR-0023 §Stage-4).  Slicer's built-in double-click maximize is unusable
    # (it realises a SECOND layout-managed widget on the singleton view node
    # whose LayerDM pipeline never populates the strip), so a double-click
    # reparents the ONE embedded qMRMLThreeDWidget into the central layout
    # viewport and back.  Invariants: enlarge reparents to the viewport, restore
    # reparents back under the drawer, there is never a second widget, and the
    # toggle is idempotent/symmetric.  Main-window-gated (the embed needs a
    # realized GL context), so it runs under the launched-Slicer
    # `pytest_launched` row and SKIPS CLEANLY here under bare pytest.
    add_test(
      NAME LiverResections_resectogram_enlarge_toggle
      COMMAND "${Python3_EXECUTABLE}" -m pytest
        -q
        "${CMAKE_CURRENT_SOURCE_DIR}/test_resectogram_enlarge_toggle.py"
      WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
    )
    set_tests_properties(LiverResections_resectogram_enlarge_toggle PROPERTIES
      LABELS "pytest;module-layer;LiverResections;resectogram;stage4"
    )

    # T3 -- ResectogramPipeline memo-key invariant (ADR-0013 §3 idempotency;
    # the render-storm fix).  The Pipeline keys UpdatePipeline on the
    # control-point geometry digest ALONE, so a render-induced Modified() at
    # fixed geometry short-circuits (no update, no render) while a real
    # control-point edit advances the update count.  Pure module-layer +
    # GPU-free; importorskip("LayerDMLib") so it runs under the launched-Slicer
    # row and SKIPS CLEANLY here under bare pytest.
    add_test(
      NAME LiverResections_resectogram_pipeline_memo_key
      COMMAND "${Python3_EXECUTABLE}" -m pytest
        -q
        "${CMAKE_CURRENT_SOURCE_DIR}/test_resectogram_pipeline_memo_key.py"
      WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
    )
    set_tests_properties(LiverResections_resectogram_pipeline_memo_key PROPERTIES
      LABELS "pytest;module-layer;LiverResections;resectogram;render-storm"
    )
  else()
    message(STATUS
      "Slicer-Liver: pytest not importable from ${Python3_EXECUTABLE}; "
      "skipping LiverResections harness self-tests registration.")
  endif()
else()
  message(STATUS
    "Slicer-Liver: Python3_EXECUTABLE not set; "
    "skipping LiverResections harness self-tests registration.")
endif()

# ---------------------------------------------------------------------------
# Distance-map double-render characterisation test (always-on, launcher-gated)
# ---------------------------------------------------------------------------
#
# Pins the invariant behind the offscreen-render abort observed when a
# vtkMRMLMarkupsBezierSurfaceNode with a 4-component float distance-map is
# rendered twice (ADR-0003 §"Decision").  Unlike the pixel-baseline replay
# entries below, this test has NO ExternalData baseline dependency: it
# asserts only that the SECOND forceRender() completes without aborting and
# leaves the GL context error-free.  It is therefore registered here,
# OUTSIDE the SlicerLiver_ENABLE_VISUAL_TESTS opt-in, but still requires the
# Slicer launcher (it brings up a minimal qSlicerApplication + offscreen 3D
# view, Level 2 per Testing/README.md).
#
# On a software-GL stack the script skips up front via the same probe the
# replay driver uses (ADR-0020 §"Rollout plan"); the real abort/no-abort
# verdict is on a GPU-backed display.
# Registered through Slicer's ``slicer_add_python_test`` (the script-shaped
# sibling of ``slicer_add_python_unittest``) rather than a hand-rolled
# ``add_test``.  The macro supplies the two things a launched test needs to
# load this module:
#   * ``--testing`` — runs against fresh temporary settings, so the launcher
#     never inherits the developer's persisted ``Modules/AdditionalPaths``
#     (which may reference stale/removed build trees and otherwise surface as
#     "The shared library was not found." at module registration); and
#   * ``${Slicer_ADDITIONAL_LAUNCHER_SETTINGS}`` — the generated
#     ``AdditionalLauncherSettings.ini`` that puts this build's and the
#     SlicerLayerDisplayableManager dependency's library paths on the
#     launcher's ``LibraryPaths``/``PYTHONPATH`` so the module ``.so`` and its
#     LayerDM-linked dependencies resolve.
# As with ``VascularTerritories`` (ADR-0023), the LayerDisplayableManager
# loadable+scripted module paths are opted in explicitly so the dependency
# modules are registered with the module manager, not merely import-able.
slicer_add_python_test(
  SCRIPT distancemap_double_render_test.py
  SLICER_ARGS
    --additional-module-paths
    ${LayerDisplayableManager_DIR}/${Slicer_QTLOADABLEMODULES_LIB_DIR}
    ${LayerDisplayableManager_DIR}/${Slicer_QTSCRIPTEDMODULES_LIB_DIR}
)
set_tests_properties(py_distancemap_double_render_test PROPERTIES
  LABELS "visual-regression;LiverResections;distance-map;characterisation"
  ENVIRONMENT "QT_QPA_PLATFORM=offscreen"
  # Same timeout rationale as the replay entries: a stuck offscreen render
  # on a misdetected stack should fail fast rather than hold CI open.
  TIMEOUT 180
  # The script exits 77 when it skips on a software-GL stack (CI's
  # xvfb + llvmpipe).  Mark that as a CTest SKIP so a masked skip is visible
  # as a skip on the dashboard, not an indistinguishable green pass; the real
  # abort/no-abort verdict is on a GPU-backed display.
  SKIP_RETURN_CODE 77
)

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
option(SlicerLiver_ENABLE_VISUAL_TESTS
  "Enable Slicer-Liver visual-regression CTest entries (requires baselines + clean launcher-exit; see LiverResections/Testing/README.md)."
  OFF)

if(NOT SlicerLiver_ENABLE_VISUAL_TESTS)
  message(STATUS
    "Slicer-Liver: visual-regression tests gated OFF "
    "(set -DSlicerLiver_ENABLE_VISUAL_TESTS=ON to enable).")
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
  # DistanceSpheroid init contour (ADR-0014 §2, ADR-0015 §"Stack 4").
  # Drives the production DistanceSpheroidInitRepresentation, which reads
  # a vtkMRMLBezierSurfaceNode and pushes the SSOT quadric onto
  # vtkOpenGLDistanceContourPolyDataMapper.  Both need the LiverResections
  # module REGISTERED (the node class + the wrapped mapper), so the
  # COMMAND below supplies --additional-module-paths rather than
  # --disable-modules.
  DistanceSpheroidContourShader
  # T3 ResectogramPipeline baseline targets (ADR-0027 invariant-test-
  # first).  Each captures against the v1 monolith first, then is
  # re-baselined to the v2.0 ResectogramPipeline.  These replay entries
  # are INERT until the baseline tag is published: no .sha512 stubs are
  # committed under ../Data/Baseline/ (the maintainer's first capture
  # session produces + uploads them to ALiveResearchTestingData), so the
  # replay driver skips each at runtime with a clear log line, and the
  # whole block is additionally gated behind SlicerLiver_ENABLE_VISUAL_TESTS
  # (OFF by default).  The scenario scene-setup bodies
  # (scenarios/Resectogram4x4*.py) are reached only once those baselines
  # land.
  Resectogram4x4BlurOff
  Resectogram4x4NonSquareScaling
  # SPLITTABLE / LAST — blur stays a v2.0 toggle; this baseline lands
  # after the blur-off resectogram baselines are green (maintainer
  # decision).  Listed here so the test surface is complete.
  Resectogram4x4BlurOn
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
  # The replay scenarios drive production code paths that need the
  # LiverResections module REGISTERED (the resection logic singleton, the
  # wrapped vtkMRMLBezierSurfaceNode, and the relocated contour mapper on
  # the ``slicer`` namespace).  Supply the in-tree module path rather than
  # ``--disable-modules`` so ``slicer.modules.liverresections`` and the
  # node / mapper classes resolve at scenario-setup time.
  ExternalData_add_test(LiverBezierVisualTestData
    NAME ${_testname}
    COMMAND "${_slicer_launcher}"
      --no-main-window
      --no-splash
      --additional-module-paths "${CMAKE_SOURCE_DIR}/LiverResections"
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
    # Offscreen GL rendering on a headless/software-GL stack can hang
    # (rather than fail cleanly) if the GL context never comes up; cap
    # each replay so a stuck render fails fast instead of holding the CI
    # job open to its global limit.
    TIMEOUT 180
  )
endforeach()

# Aggregate fetch target.  ``make LiverBezierVisualTestData`` pulls
# every referenced blob without running CTest — useful for warming the
# ExternalData cache before a CI run or before going offline.
ExternalData_add_target(LiverBezierVisualTestData)

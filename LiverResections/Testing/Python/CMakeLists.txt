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

    # Ring-extractor CLASS RESOLUTION -- the Init-mode ring extractors
    # (vtkLiverPlaneRingExtractor / vtkLiverSpheroidRingExtractor) are
    # Algorithm-library classes (ADR-0014 §3), exposed inside a launched Slicer
    # ONLY on vtkSlicerLiverResectionsModuleAlgorithmPython -- NOT on the slicer
    # or vtk namespaces.  Pins that _resolve_extractor_class returns a real class
    # (not None) so run_ring_extraction is not a silent no-op, plus a behavioral
    # smoke: a plane through a sphere centre yields a non-empty ring.  Needs the
    # wrapped Algorithm classes, so it runs under the launched-Slicer
    # `pytest_launched` row and SKIPS CLEANLY here under bare pytest (the
    # Algorithm wrapping is off the path).  GL free -- no render window.
    add_test(
      NAME LiverResections_ring_extractor_resolution
      COMMAND "${Python3_EXECUTABLE}" -m pytest
        -q
        "${CMAKE_CURRENT_SOURCE_DIR}/test_resections_ring_extractor_resolution.py"
      WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
    )
    set_tests_properties(LiverResections_ring_extractor_resolution PROPERTIES
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

    # Custom-OpenGL-mapper wiring -- the sibling Representations that carry a
    # custom shader mapper (DistanceSpheroidInit -> DistanceContour;
    # VascularContour -> DistanceContour + SlicingContour; FlattenedSurface ->
    # Resection2D) drive the REAL relocated mappers (ADR-0014 §3), not the
    # generic vtkPolyDataMapper.  Extends the Bezier surface-mapper invariant;
    # the positive pin makes the no-real-mapper fallback removal safe (ADR-0008
    # §2 -- the no-VTK unit layer the fallback aspired to was never built).
    # Needs the wrapped mappers, so it runs green under the launched-Slicer
    # `pytest_launched` row and SKIPS CLEANLY here under bare pytest (no
    # slicer.mrmlScene / wrapped mapper classes off the path).  GL free.
    add_test(
      NAME LiverResections_custom_mapper_wiring
      COMMAND "${Python3_EXECUTABLE}" -m pytest
        -q
        "${CMAKE_CURRENT_SOURCE_DIR}/test_custom_mapper_wiring.py"
      WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
    )
    set_tests_properties(LiverResections_custom_mapper_wiring PROPERTIES
      LABELS "pytest;module-layer;LiverResections;mapper-wiring"
    )

    # T2 render-cutover slice 1c -- the LayerDM Pipeline reverse-resolves its
    # vtkMRMLResectionPlanNode wrapper from the data node's geometry
    # back-reference (ADR-0031), so the live render path threads the
    # distance-map + margins with no external SetResectionNode caller.  Needs
    # the wrapped plan / carrier / display nodes + the importable Pipeline, so
    # it runs green under the launched-Slicer `pytest_launched` row and SKIPS
    # CLEANLY here under bare pytest (no slicer.mrmlScene / LayerDMLib).
    add_test(
      NAME LiverResections_pipeline_resolves_resection_plan
      COMMAND "${Python3_EXECUTABLE}" -m pytest
        -q
        "${CMAKE_CURRENT_SOURCE_DIR}/test_pipeline_resolves_resection_plan.py"
      WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
    )
    set_tests_properties(LiverResections_pipeline_resolves_resection_plan PROPERTIES
      LABELS "pytest;module-layer;LiverResections;mapper-wiring"
    )

    # #489 locator consumer (Representation half) -- BezierPlanningRepresentation
    # reads a single vtkMRMLLocatorNode's picked world point + its display-node
    # Radius and drives the real vtkOpenGLBezierResectionPolyDataMapper's locator
    # uniforms (uLocatorPosition / uLocatorRadius, ADR-0025 §Rendering) through a
    # new SetLocatorNode seam (mirrors SetResectionPlanNode; NO custom DM, NO new
    # factory -- ADR-0013 §5/§6).  Invariant 1: node position + display radius
    # reach the mapper; invariant 2: no locator node (SetLocatorNode(None)) zeroes
    # uLocatorRadius (the shader off state).  Node -> consumer only; the full
    # producer -> node -> consumer chain (#489) closes when Slice B lands.  Needs
    # the wrapped locator nodes + real mapper + Representation, so it runs green
    # under the launched-Slicer `pytest_launched` row and SKIPS CLEANLY here under
    # bare pytest (no slicer.mrmlScene / wrapped classes off the path).  GL free
    # -- the mapper's uniform accessors need no render window.  RED / skip-pending
    # (guards on the SetLocatorNode + GetLocatorRadius seams) until the implementer
    # lands the consumer (ADR-0027 §Conformance: the skip lifts at the
    # implementation commit).
    add_test(
      NAME LiverResections_bezier_planning_locator_consumer
      COMMAND "${Python3_EXECUTABLE}" -m pytest
        -q
        "${CMAKE_CURRENT_SOURCE_DIR}/test_bezier_planning_locator_consumer.py"
      WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
    )
    set_tests_properties(LiverResections_bezier_planning_locator_consumer PROPERTIES
      LABELS "pytest;module-layer;LiverResections;locator;mapper-wiring"
    )

    # #489 locator consumer (Pipeline half) -- LiverBezierSurfacePipeline resolves
    # the scene's single vtkMRMLLocatorNode (GetFirstNodeByClass; v2.0 has exactly
    # one) and threads it onto the active Representation via SetLocatorNode before
    # update() (mirrors the ADR-0031 SetResectionPlanNode reverse-resolve+thread;
    # ADR-0025 §Consumer, ADR-0013 §6).  Positive: a locator node in the scene ->
    # its display Radius reaches the mapper's uLocatorRadius with no external
    # SetLocatorNode caller; negative: no locator node -> uLocatorRadius stays 0
    # (no false-positive; shader off state).  Node -> consumer only; the full
    # producer -> node -> consumer chain (#489) closes when Slice B lands.  Needs
    # the wrapped locator nodes + real mapper + importable Pipeline, so it runs
    # green under the launched-Slicer `pytest_launched` row and SKIPS CLEANLY here
    # under bare pytest (no slicer.mrmlScene / LayerDMLib).  GL free.  RED /
    # skip-pending (guards on a Representation exposing SetLocatorNode) until the
    # implementer lands the Pipeline resolution + threading (ADR-0027 §Conformance:
    # the skip lifts at the implementation commit).
    add_test(
      NAME LiverResections_pipeline_resolves_locator
      COMMAND "${Python3_EXECUTABLE}" -m pytest
        -q
        "${CMAKE_CURRENT_SOURCE_DIR}/test_pipeline_resolves_locator.py"
      WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
    )
    set_tests_properties(LiverResections_pipeline_resolves_locator PROPERTIES
      LABELS "pytest;module-layer;LiverResections;locator;mapper-wiring"
    )

    # #501 slice 2 -- the v2 resection control-point edit path on the LayerDM
    # Pipeline (ADR-0032: interaction routes through the Pipeline interaction
    # seam, no standalone vtkAbstractWidget).  Pins the GL-free edit kernel
    # _apply_world_point_to_nearest_control_point -- in Planning it moves
    # exactly the nearest control point to the RAS world point via
    # SetControlPoint and returns its flat index (invariants 1+2); in a
    # read-only state past Planning (Confirmed) it is a no-op returning None
    # (invariant 3, ADR-0019 read-only-after-commit).  Plus the
    # ProcessInteractionEvent routing override (invariant 4), skip-pending
    # behind a realized main-window view (display->world needs a renderer/
    # camera; the full routing is verified on the interactive :0 pass per
    # ADR-0032 §Conformance).  Builds the plan/carrier/display triad via the
    # merged logic create-API (CreateResectionPlan, slice 1), so it runs green
    # under the launched-Slicer `pytest_launched` row and SKIPS CLEANLY here
    # under bare pytest (no slicer.mrmlScene / LayerDMLib / create-API).  RED /
    # skip-pending until the implementer lands the edit kernel + the
    # interaction overrides (ADR-0027 §Conformance: the skip lifts at the
    # implementation commit).
    add_test(
      NAME LiverResections_pipeline_control_point_edit
      COMMAND "${Python3_EXECUTABLE}" -m pytest
        -q
        "${CMAKE_CURRENT_SOURCE_DIR}/test_pipeline_control_point_edit.py"
      WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
    )
    set_tests_properties(LiverResections_pipeline_control_point_edit PROPERTIES
      LABELS "pytest;module-layer;LiverResections;interaction"
    )

    # #501 slice 3a -- SlicingPlane Init-mode PLACEMENT on the LayerDM Pipeline
    # (ADR-0032: interaction routes through the Pipeline interaction seam, no
    # standalone vtkAbstractWidget).  Pins the GL-free placement kernel
    # _place_slicing_plane_init_point -- in Init+SlicingPlane it fills the fixed
    # 2-slot SlicingPlaneInitPoints array in order (slot 0 then 1) via
    # SetSlicingPlaneInitPoint and returns the placed index, refusing a third
    # placement (invariants 1+2); it is a no-op returning None outside
    # Init+SlicingPlane (Planning state / DistanceSpheroid mode, invariant 3,
    # ADR-0019); and placement progress resets on SetDisplayNode so a fresh
    # carrier restarts at index 0 (invariant 4).  Plus the ProcessInteractionEvent
    # routing override dispatching Init+SlicingPlane -> placement (invariant 5),
    # skip-pending behind a realized main-window view (display->world plus the
    # camera-coupled origin/normal derivation need a renderer; the full routing is
    # verified on the interactive :0 pass per ADR-0032 §Conformance).  Builds the
    # plan/carrier/display triad via the merged logic create-API
    # (CreateResectionPlan, slice 1), so it runs green under the launched-Slicer
    # `pytest_launched` row and SKIPS CLEANLY here under bare pytest (no
    # slicer.mrmlScene / LayerDMLib / create-API).  RED / skip-pending until the
    # implementer lands the placement kernel + the interaction dispatch (ADR-0027
    # §Conformance: the skip lifts at the implementation commit).
    add_test(
      NAME LiverResections_pipeline_slicing_plane_init_placement
      COMMAND "${Python3_EXECUTABLE}" -m pytest
        -q
        "${CMAKE_CURRENT_SOURCE_DIR}/test_pipeline_slicing_plane_init_placement.py"
      WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
    )
    set_tests_properties(LiverResections_pipeline_slicing_plane_init_placement PROPERTIES
      LABELS "pytest;module-layer;LiverResections;interaction"
    )

    # #501 slice 3b -- DistanceSpheroid Init-mode PLACEMENT on the LayerDM
    # Pipeline (ADR-0032: interaction routes through the Pipeline interaction
    # seam, no standalone vtkAbstractWidget).  Same shape as slice 3a for the
    # other init mode.  Pins the GL-free placement kernel
    # _place_distance_spheroid_init_point -- in Init+DistanceSpheroid it fills
    # the DYNAMICALLY-sized DistanceSpheroidInitPoints array in order (slot 0,
    # 1, ... up to GetNumberOfDistanceSpheroidInitPoints()) via
    # SetDistanceSpheroidInitPoint and returns the placed index, refusing a
    # placement past capacity (invariants 1+2); it is a no-op returning None
    # outside Init+DistanceSpheroid (Planning state / SlicingPlane mode,
    # invariant 3, ADR-0019); and placement progress resets on SetDisplayNode so
    # a fresh carrier restarts at index 0 (invariant 4).  Plus the
    # ProcessInteractionEvent routing override dispatching Init+DistanceSpheroid
    # -> placement (invariant 5), skip-pending behind a realized main-window view
    # (display->world plus the camera-coupled centre/radii derivation need a
    # renderer; the full routing is verified on the interactive :0 pass per
    # ADR-0032 §Conformance).  Builds the plan/carrier/display triad via the
    # merged logic create-API (CreateResectionPlan, slice 1) and sizes the
    # spheroid array while in Init (the capacity setter is Init-guarded), so it
    # runs green under the launched-Slicer `pytest_launched` row and SKIPS
    # CLEANLY here under bare pytest (no slicer.mrmlScene / LayerDMLib /
    # create-API).  RED / skip-pending until the implementer lands the placement
    # kernel + the interaction dispatch (ADR-0027 §Conformance: the skip lifts at
    # the implementation commit).
    add_test(
      NAME LiverResections_pipeline_distance_spheroid_init_placement
      COMMAND "${Python3_EXECUTABLE}" -m pytest
        -q
        "${CMAKE_CURRENT_SOURCE_DIR}/test_pipeline_distance_spheroid_init_placement.py"
      WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
    )
    set_tests_properties(LiverResections_pipeline_distance_spheroid_init_placement PROPERTIES
      LABELS "pytest;module-layer;LiverResections;interaction"
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

    # #501 slice 4 -- re-point the Stage-4 ResectionPlanningWidget (the Python
    # widget, ADR-0004; ADR-0023 §Stage-4) from the v1 markups surface to the v2
    # resection-plan node graph (ADR-0014 §"Fourth layer" wrapper/carrier).
    # Three GPU-free invariants: (1) the active-resection combo offers a
    # vtkMRMLResectionPlanNode WRAPPER and NOT the v1
    # vtkMRMLMarkupsBezierSurfaceNode (nodeTypes re-point); (2) the auto-populate
    # predicate reads the distance map off the WRAPPER
    # (plan.GetDistanceMapVolumeNode(), ADR-0031) -- none selected -> "select"
    # hint, plan without distance map -> "compute" hint, plan WITH distance map
    # -> hint hidden AND exactly one vtkMRMLResectogramDisplayNode ensured on the
    # CARRIER (plan.GetGeometryNode(), a vtkMRMLBezierSurfaceNode), idempotent on
    # repeated refresh; (3) a "Place resection" affordance
    # (placeResectionButton() + onPlaceResection()) mints a plan via the merged
    # logic create-API (CreateResectionPlan, slice 1), adds it to the scene, and
    # selects it in the combo (scene gains a plan + a Bezier carrier).  Builds
    # LiverResectionsLib.ResectionPlanningWidget directly under a launched
    # qSlicerApplication, so it runs green under the launched-Slicer
    # `pytest_launched` row (Liver/Testing/Python; this dir is already on its
    # test roots) and SKIPS CLEANLY here under bare pytest (no qt.QWidget /
    # no widget / no create-API).  Each invariant is additionally guarded on the
    # NEW state's presence (nodeTypes inspection / place-button accessor), so it
    # lands RED-as-skip on the still-v1 build and turns GREEN once slice 4
    # re-points the widget (ADR-0027 §Conformance: the skip lifts at the
    # implementation commit).
    add_test(
      NAME LiverResections_resection_planning_widget_v2_repoint
      COMMAND "${Python3_EXECUTABLE}" -m pytest
        -q
        "${CMAKE_CURRENT_SOURCE_DIR}/test_resection_planning_widget_v2_repoint.py"
      WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
    )
    set_tests_properties(LiverResections_resection_planning_widget_v2_repoint PROPERTIES
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

    # #501 slice 5 -- thread the resection-plan WRAPPER into the resectogram
    # render path (ADR-0031: the distance-map volume + the safety / risk
    # margins are wrapper-owned inputs on vtkMRMLResectionPlanNode; ADR-0013 §5,
    # §6).  Ports the 3D path (LiverBezierSurfacePipeline._resolve_resection_node
    # + BezierPlanningRepresentation.SetResectionPlanNode) into the resectogram
    # path.  This entry pins the PIPELINE half: ResectogramPipeline
    # reverse-resolves the vtkMRMLResectionPlanNode whose GetGeometryNode() is
    # its data node (carrier) and hands it to the FlattenedSurfaceRepresentation
    # via SetResectionPlanNode -- an unowned carrier resolves to None.  Needs
    # the wrapped plan / carrier / resectogram-display nodes + the importable
    # Pipeline (base vtkMRMLLayerDMScriptedPipeline), so it runs green under the
    # launched-Slicer `pytest_launched` row and SKIPS CLEANLY here under bare
    # pytest (no slicer.mrmlScene / LayerDMLib).  RED / skip-pending until the
    # implementer lands the reverse-resolution seam (ADR-0027 §Conformance: the
    # skip lifts at the implementation commit).
    add_test(
      NAME LiverResections_resectogram_pipeline_resolves_resection_plan
      COMMAND "${Python3_EXECUTABLE}" -m pytest
        -q
        "${CMAKE_CURRENT_SOURCE_DIR}/test_resectogram_pipeline_resolves_resection_plan.py"
      WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
    )
    set_tests_properties(LiverResections_resectogram_pipeline_resolves_resection_plan PROPERTIES
      LABELS "pytest;module-layer;LiverResections;resectogram;mapper-wiring"
    )

    # #501 slice 5 -- the REPRESENTATION half: FlattenedSurfaceRepresentation
    # shades off the WRAPPER (ADR-0031), not the carrier.  With a plan wrapper
    # set, update() threads SetResectionMargin(SafetyMargin_mm) +
    # SetUncertaintyMargin(RiskMargin_mm) onto the 2D
    # vtkOpenGLResection2DPolyDataMapper and sources the distance-map volume
    # from plan.GetDistanceMapVolumeNode() (present -> resolved source; absent ->
    # source cleared, graceful fallback, margins still set).  GL-free: a FAKE 2D
    # mapper records the margin scalar-setters + the resolved distance-map source
    # (same mock-mapper idiom as test_bezier_planning_surface_mapper_wiring.py);
    # the real GL 3D-texture upload + the strip render are the :0 eyeball
    # follow-up, NOT asserted here.  Needs the wrapped plan / carrier /
    # resectogram-display / volume nodes, so it runs green under the
    # launched-Slicer `pytest_launched` row and SKIPS CLEANLY here under bare
    # pytest (no slicer.mrmlScene).  RED / skip-pending until the implementer
    # ports the wrapper-shading path (ADR-0027 §Conformance: the skip lifts at
    # the implementation commit).
    add_test(
      NAME LiverResections_flattened_surface_plan_shading
      COMMAND "${Python3_EXECUTABLE}" -m pytest
        -q
        "${CMAKE_CURRENT_SOURCE_DIR}/test_flattened_surface_plan_shading.py"
      WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
    )
    set_tests_properties(LiverResections_flattened_surface_plan_shading PROPERTIES
      LABELS "pytest;module-layer;LiverResections;resectogram;mapper-wiring"
    )

    # #501 slice 6 -- round-trip symmetry guard: the resection-plan WRAPPER's
    # distanceMap volume reference deliberately does NOT persist to .lrp.json in
    # v2.0 (ADR-0031; the distance map is a computed input whose scene-local
    # node ID breaks across reloads -- stable cross-machine references are
    # deferred to v2.1 per Docs/design/resection-plan-architecture/
    # 05-lrp-json-schema.md).  A characterization/creep-guard: green on the
    # current build, it fails a symmetry-minded storage edit that adds the
    # distanceMap ref before the v2.1 stable-ID mechanism exists.  The positive
    # field-by-field round-trip symmetry is pinned by the C++
    # vtkMRMLResectionPlanStorageNodeTest1 (testPlanRootedRoundTrip).
    add_test(
      NAME LiverResections_resection_plan_distance_map_not_persisted
      COMMAND "${Python3_EXECUTABLE}" -m pytest
        -q
        "${CMAKE_CURRENT_SOURCE_DIR}/test_resection_plan_distance_map_not_persisted.py"
      WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
    )
    set_tests_properties(LiverResections_resection_plan_distance_map_not_persisted PROPERTIES
      LABELS "pytest;module-layer;LiverResections;storage;round-trip"
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

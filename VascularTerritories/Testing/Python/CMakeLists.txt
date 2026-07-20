
#slicer_add_python_unittest(SCRIPT ${MODULE_NAME}ModuleTest.py)

# Opt in to LayerDisplayableManager + SlicerVMTK module loading (see
# the VascularTerritories/MRML/Testing/Python/CMakeLists.txt comment
# block for the rationale).  Without LayerDM the Python wrapper test
# cannot resolve ``vtkMRMLLayerDMPipelineI`` from the ``slicer``
# namespace.  Without SlicerVMTK's ``ExtractCenterline``, the legacy
# integration suite cannot exercise the centerline computation that
# Stage 3 Manual classification depends on (per ADR-0023).  Both
# extensions are pre-built into the project's
# ``slicer-build-ubuntu2404`` CI image (ALive-Docker layers 5a-5c)
# and exposed via ``LayerDisplayableManager_DIR`` and
# ``SlicerVMTK_DIR`` env vars; ``find_package`` populates the
# matching CMake variables.
slicer_add_python_unittest(
  SCRIPT VascularTerritoriesTest.py
  SLICER_ARGS
    --additional-module-paths
    ${LayerDisplayableManager_DIR}/${Slicer_QTLOADABLEMODULES_LIB_DIR}
    ${LayerDisplayableManager_DIR}/${Slicer_QTSCRIPTEDMODULES_LIB_DIR}
    ${SlicerVMTK_DIR}/${Slicer_QTLOADABLEMODULES_LIB_DIR}
    ${SlicerVMTK_DIR}/${Slicer_QTSCRIPTEDMODULES_LIB_DIR}
)

# ---------------------------------------------------------------------------
# Bare-VTK unit tests (pytest_scaffold family)
# ---------------------------------------------------------------------------
#
# Pure-VTK unit tests for the vessel-adhering-highlight pick core live
# here and run under bare ``PythonSlicer -m pytest`` — no Slicer scene,
# no Qt, no GL (ADR-0003 testability invariant; ADR-0008 §2 unit layer).
# Unlike the launched ``slicer_add_python_unittest`` self-test above,
# these register one bare CTest row per file, mirroring the pattern in
# ``LiverSegmentation/Testing/Python/CMakeLists.txt``.  The same
# skip-if-pytest-absent guard keeps the scaffolding buildable where the
# Slicer Python environment has not yet been provisioned with pytest.
if(NOT Python3_EXECUTABLE)
  message(STATUS
    "Slicer-Liver: Python3_EXECUTABLE not set; "
    "skipping VascularTerritories bare-pytest registration.")
  return()
endif()

execute_process(
  COMMAND "${Python3_EXECUTABLE}" -c "import pytest"
  RESULT_VARIABLE _vascterr_pytest_probe_rc
  OUTPUT_QUIET
  ERROR_QUIET
)

if(NOT _vascterr_pytest_probe_rc EQUAL 0)
  message(STATUS
    "Slicer-Liver: pytest not importable from ${Python3_EXECUTABLE}; "
    "skipping VascularTerritories bare-pytest registration.  Install "
    "pytest in the Slicer Python environment to enable these tests.")
  return()
endif()

set(_vascterr_pytest_files
  # Pure-VTK unit skeletons for the vessel-adhering-highlight pick core.
  # Import-guarded on the not-yet-existing VesselSurfacePick seam; they
  # collect + SKIP-PENDING cleanly bare until the implementer lands
  # VascularTerritoriesLib/VesselSurfacePick.py (ADR-0027).
  test_vessel_surface_pick.py
  # LayerDM highlight-Pipeline unit invariants (pick integration + the
  # ADR-0033 hover-decline discipline).  Import-guarded on LayerDMLib
  # (reachable only from a launched Slicer); they SKIP bare and RUN
  # launched, mirroring the ControlPolygonPipeline unit suite.
  test_vessel_highlight_pipeline.py
  # Snap-on-place + the widget highlight wiring.  Scene-/widget-needing
  # (segmentation closed-surface reps + the module widget); they SKIP
  # cleanly bare and RUN launched, mirroring the LiverSegmentation suite.
  test_vessel_highlight_wiring.py
  # ADR-0037 Stage-1 i1/i2 -- the annotation-point carrier on
  # vtkMRMLCustomTerritoriesNode (ordered per-territory points; no markups
  # reference) + its storage round-trip.  The carrier is a WRAPPED C++
  # node, reachable only launched; import-/hasattr-guarded on the
  # not-yet-existing carrier API + storage node, they SKIP-PENDING bare
  # and RUN launched once the seam lands (ADR-0027).
  test_territories_annotation_carrier.py
  # ADR-0037 Stage-1 i3/i4 -- the annotation placement/edit Pipeline
  # (ADR-0032/0033 seam): click adds exactly one surface-snapped point, a
  # bare move is declined (camera untouched), a drag edits the nearest
  # point, delete removes one.  Import-guarded on the not-yet-existing
  # TerritoryPlacementPipeline + LayerDMLib; SKIP bare, RUN launched,
  # mirroring the ControlPolygon/LiverBezier interaction suites (ADR-0027).
  test_territories_placement_pipeline.py
  # ADR-0037 Stage-2 -- the annotation TABLE UI (§Decision 3 / §3 table):
  # a Python-composed custom QTableWidget over the carrier, header row per
  # territory + child row per seed; arm-through-the-Pipeline placement into
  # the ACTIVE territory; delete-row/delete-pick convergence; glyph+text
  # completeness (ADR-0010); selector retirement with the highlight wiring
  # surviving and no persisted fiducial.  Needs Qt + the wrapped carrier +
  # LayerDMLib; import-/hasattr-guarded on the not-yet-existing table widget
  # + carrier display slot + Pipeline arm seam, they SKIP-PENDING bare and
  # RUN launched once the seam lands (ADR-0027).
  test_territories_table.py
  # ADR-0037 §2D -- the slice-view territory placement + distance-faded viz
  # (mirrors SliceControlPolygonPipeline, ADR-0033): the projection / signed
  # distance / presence cutoff are pure math and RUN bare against the
  # TerritorySliceProjection helper; the snap / arm-gate / bare-move-decline
  # invariants need LayerDMLib so they SKIP bare and RUN launched, mirroring
  # the 3D placement suite (ADR-0027).
  test_territories_slice_pipeline.py
  # ADR-0037 Stage-3 -- the VMTK centerline feed off the annotation carrier
  # (§Decision 4): the transient-markups builder maps carrier points ->
  # a fiducial payload (same count/coords/ORDER; one inlet at index 0,
  # selected == False); after extraction NO fiducial persists; the
  # extraction action follows the moduleNames() guard (disabled + tooltip
  # when SlicerVMTK absent, placement/table stay live); N territories ->
  # N transient nodes.  The pure builder core RUNS BARE; the lifecycle /
  # guard / per-territory invariants need the module Logic + a live scene
  # so they SKIP-PENDING bare and RUN launched; the REAL extraction wiring
  # is SlicerVMTK-env-gated and skips cleanly off that image (ADR-0027).
  test_territories_vmtk_feed.py
  # ADR-0037 §Decision 3 (slice 2) -- the PANEL modernisation to Python-widget
  # composition (ADR-0004): the table-duplicating v1 selector/place-widget
  # surface (ColorPickerButton / showHideButton / addSegmentationButton /
  # SegmentsWidget / inputSegmentSelectorWidget / vascularTerritoryId) + its
  # handlers retire, while inputSurfaceSelector / SegmentationShow3DButton /
  # the composed TerritoriesTableWidget / the Extract-centerlines action stay
  # re-homed, and the slice-3 map path (Compute territory map +
  # selectedVascularTerritorySegmId) stays FUNCTIONAL.  Builds the module
  # widget so it needs a launched qSlicerApplication; the behavioural
  # assertions guard on the retirement having landed, SKIP-PENDING bare AND
  # while the v1 surface survives, and RUN launched once slice 2 lands
  # (ADR-0027).
  test_territories_widget_panel.py
  # ADR-0037 §Decision 4 (slice 3) -- the territory-map COMPUTE path re-sourced
  # off the getNodes("*Territory*") scene scan + the retired
  # selectedVascularTerritorySegmId selector ONTO the annotation carrier: a
  # deterministic string->int label map (enumerate GetAnnotationTerritoryIds()
  # -> index + 1); build_centerline_model sourcing from CenterlineRefs +
  # Groupings (one carrier == one map == all its centerlines) and marking each
  # centerline with its derived int; the output segmentation DERIVED from the
  # carrier's TerritoryMapOutput role (auto-created + reused, per-carrier-ordinal
  # SegmentationId, no cross-carrier collision); the selector retirement; and
  # the button resolving all inputs from the carrier + inputSurfaceSelector.
  # The pure label-map core RUNS BARE; the carrier-sourcing / derived-output /
  # selector-retirement / button-wiring invariants need the wrapped carrier +
  # module widget + Logic so they SKIP-PENDING bare and RUN launched; the real
  # C++ map run stays eyeball-gated (stubbed here) (ADR-0027).
  test_territories_map_compute.py
  # ADR-0037 §Decision 4 -- the centerline SURFACE-RESOLUTION invariant: a
  # segmentation input's closed surface must be resolved through the real
  # segment(s) (converging on VesselHighlightWiring.closed_surface_polydata,
  # the pick/snap seam), NOT via an empty segment id handed to
  # GetClosedSurfaceRepresentation (which resolves no segment -> zero points
  # -> a silently-degraded None the real SlicerVMTK extractor hard-fails on);
  # and a genuinely empty surface must SKIP extraction, never feed the real
  # extractor a None/empty mesh.  Needs Slicer's segmentation logic + a live
  # scene so it SKIP-PENDS bare and RUNS launched; the VMTK compute itself
  # stays env-/eyeball-gated in test_territories_vmtk_feed.py (ADR-0027).
  # ALSO hosts the ADR-0037 slice-5 (PR-A) vessel-SCT-filter invariant (T1):
  # GetVascularSegmentIds keeps only vascular-SCT-typed segments (Vein
  # SCT^29092000 / Artery SCT^51114001) and excludes the liver (SCT^10200004)
  # and tumour segments, mirroring the GetLiverSegmentId C++ idiom on logic.scl;
  # launched (segmentation infra + wrapped C++ logic), SKIP-PENDING bare + until
  # the resolver lands (ADR-0027).
  test_territories_surface_resolution.py
  # ADR-0037 §Decision 2/3 (slice 4) -- per-territory Place mode + module-active
  # gate + composite-row panel polish.  Placement becomes an EXPLICIT,
  # exclusive, per-territory arm toggle: toggling ON arms THAT territory on the
  # shared display node and un-checks every other territory; toggling OFF
  # disarms; the armed territory's checked state is re-derived from the display
  # node on each rebuild.  The widget's exit() disarms so no view claims an
  # add-on-click while the module is inactive; enter() auto-arms nothing.  The
  # visibility control is an eye-icon QToolButton (not QCheckBox); Add seeds /
  # Done panel buttons retire (done() disarm body survives); an armed click
  # adds one seed child item under the territory.  The panel is a header-less,
  # single-column tree of composite row widgets (a per-row Place / eye / colour
  # / label / status strip; no column grid).  The exclusivity / re-derivation
  # logic drives via the tree + display node; the exit-disarm + click-adds-a-
  # child invariants need a REAL pipeline bound to the SAME display node -- all
  # SKIP-PENDING bare / while the composite-row seam is absent, and RUN launched
  # once the composite-row tree + eye toggle land (ADR-0027).
  test_territories_placemode.py
  # ADR-0037 slice 5 (PR-A, connected-tree seeding) -- the connectivity-recovery
  # invariant.  The compute amendment merged EVERY segment into the VMTK input;
  # real liver data (portal + hepatic are disjoint components) makes merge-all
  # wrong, so a territory's active surface narrows to the single connected
  # component its index-0 seed lands on.  The recovery is a PURE-VTK helper
  # (vtkPolyDataConnectivityFilter in ClosestPointRegion mode; no MRML, no GL):
  # a seed on one of two disjoint spheres recovers ONLY that sphere's component
  # (single region, zero points from the other); two disjoint seeds resolve to
  # different trees; and re-deriving from a NEW index-0 (after first-seed
  # deletion) recovers the SAME component (the reuse-AnnotationPoints[0]
  # persistence decision).  Import-guarded on the not-yet-existing
  # VascularTerritoriesLib/VesselConnectivity.py; the file COLLECTS + SKIP-
  # PENDINGs cleanly bare and genuinely RUNS bare (pure VTK) once the helper
  # lands (ADR-0027).  The vessel-SCT-filter twin (T1) lives launched in
  # test_territories_surface_resolution.py.
  test_territories_connectivity.py
)

foreach(_pytest_file IN LISTS _vascterr_pytest_files)
  get_filename_component(_test_basename "${_pytest_file}" NAME_WE)
  add_test(
    NAME ${_test_basename}
    COMMAND "${Python3_EXECUTABLE}" -m pytest
      -q
      "${CMAKE_CURRENT_SOURCE_DIR}/${_pytest_file}"
    WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
  )
  set_tests_properties(${_test_basename} PROPERTIES
    LABELS "pytest;VascularTerritories;vessel-highlight"
  )
endforeach()


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
  # RUN launched once the seam lands (ADR-0027).  ALSO hosts the post-review
  # refinement guard (green regression): Add Territory arms the new territory
  # (its Place toggle reads checked) but must NOT auto-select its tree row --
  # arming, not selection, is the active-state cue (ADR-0037 §Decision 2
  # slice-4).  This RUNS + PASSES launched now, guarding a re-introduced
  # setCurrentItem.
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
  # ALSO hosts the REVISED slice-5 GROUP-BY-STRUCTURE invariant (i7): a
  # territory with >=2 seeds on TWO structures (vein + artery) yields TWO
  # centerlines, both grouped under the territory; a structure with <2 seeds is
  # SKIPPED (the per-structure >=2 gate).  Launched (module Logic + a real
  # multi-segment segmentation + a stubbed line extractor, so no SlicerVMTK is
  # needed); SKIPS bare (ADR-0027).
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
  # C++ map run stays eyeball-gated (stubbed here) (ADR-0027).  ALSO hosts the
  # post-review refinement guard (green regression): each map-output segment is
  # NAMED + COLOURED for its TERRITORY (GetTerritoryLabel / GetTerritoryColor),
  # keyed by the segment's label value through TerritoryLabelMap
  # (_applyTerritoryNamesAndColors), so the map reads the same as the table
  # (ADR-0037 §Decision 4 / §Decision 1).  Driven against a hand-built map
  # segmentation with known label values, so it RUNS + PASSES launched now.
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
  # ADR-0037 slice 5 (REVISED, multi-system seeding) -- the PER-STRUCTURE
  # connected-component narrow.  The compute amendment merged EVERY segment into
  # the VMTK input; real liver data (portal + hepatic are disjoint) makes
  # merge-all wrong.  The REVISED design drops the single-active-tree LOCK (a
  # territory may straddle disjoint structures; extraction groups by structure),
  # but connectivity SURVIVES for a different job: narrowing each PER-STRUCTURE
  # surface to the connected component of that structure's OWN seed, so a single
  # input segment carrying two disjoint tubes still feeds VMTK one coherent tree
  # (the A3/Q2 edge case).  The recovery is a PURE-VTK helper
  # (vtkPolyDataConnectivityFilter in ClosestPointRegion mode; no MRML, no GL):
  # a seed on one of two disjoint spheres recovers ONLY that sphere's component
  # (single region, zero points from the other).  The retired reuse-index-0
  # persistence test is REMOVED with the lock.  Import-guarded on the
  # not-yet-existing VascularTerritoriesLib/VesselConnectivity.py; the file
  # COLLECTS + SKIP-PENDINGs cleanly bare and genuinely RUNS bare (pure VTK) once
  # the helper lands (ADR-0027).  The vessel-SCT-filter twin (T1) + per-segment
  # closed-surface split (T1d) live launched in
  # test_territories_surface_resolution.py; the seed->structure mapping twin is
  # test_territories_seed_structure.py.
  test_territories_connectivity.py
  # ADR-0037 slice 5 (REVISED, multi-system seeding) -- placement no longer
  # LOCKS a territory to one connected vessel tree.  The landed slice-5 design
  # (first seed defines the active tree, later seeds snap back, the component
  # glows) was clinically wrong: a vascular territory may own seeds across
  # MULTIPLE disjoint structures (portal + hepatic), derived independently and
  # both feeding the one map region.  This suite pins the FLIP: NO STRADDLE-SNAP
  # -- a later add-on-click on a DIFFERENT visible structure STAYS there (two
  # seeds, two structures); the retired active-tree lock+halo (activeTreePolyData
  # / highlightActor / _constrain_to_active_tree / _highlight_tree_actor) are
  # asserted GONE (an absence pin with a credible creep-in path -- the named
  # attributes exist on the landed branch and must be removed); the visibility-
  # gated pick is the only placement constraint (pinned in
  # test_territories_surface_resolution T1c, not here); and the retained
  # module-active + armed gates still decline clicks.  The SUT surface is TWO
  # disjoint spheres (vtkAppendPolyData of two separated vtkSphereSource) wired
  # as the vessels-only pick surface, with the stub-renderer + injected-pick
  # pattern from test_territories_placement_pipeline so clicks map to chosen
  # world points on structure A or structure B.  Needs LayerDMLib + the wrapped
  # carrier + the shared highlight display node; the no-straddle-snap + retired-
  # halo invariants go GREEN when the implementer removes the lock+halo, the
  # module-gate invariants SKIP-PENDING until the pipeline seams land, all RUN
  # launched (ADR-0027).
  test_territories_placemode_constraint.py
  # ADR-0037 slice 5 (REVISED, multi-system seeding) -- the seed->structure
  # mapping (pure-VTK).  Each of a territory's seeds is assigned to the input
  # SEGMENT (structure) whose CLOSED SURFACE it is nearest (portal / hepatic /
  # ...), so a territory may straddle disjoint structures and extraction can
  # group by structure.  The geometry (nearest closed surface to a point) is
  # PURE polydata -> Python (ADR-0004 split): nearest_structure(structures,
  # point) -> key builds one vtkCellLocator per structure surface and returns
  # the nearest structure's key, with a deterministic first-in-order tiebreak on
  # a boundary point (Q3); territory_structure_seed_counts(assignments) groups
  # mapped (seed, structureKey) pairs into {key: count}, the SAME >=2-per-
  # structure gate the extractor (test_territories_vmtk_feed) and the table
  # warning (test_territories_table) read so they agree.  Import-guarded on the
  # not-yet-existing VascularTerritoriesLib/SeedStructureMapping.py; the file
  # COLLECTS + SKIP-PENDINGs cleanly bare and genuinely RUNS bare (pure VTK) once
  # the helper lands (ADR-0027).  The MRML-facing segment->surface/colour
  # resolution rides existing seams, pinned launched in
  # test_territories_surface_resolution (T1d) + test_territories_table.
  test_territories_seed_structure.py
  # ADR-0037 slice 5 -- the Extract + Compute actions GATE ON REAL
  # PRECONDITIONS (§Decision 4).  Extract enables iff an input is selected AND
  # SlicerVMTK is present AND a territory has a STRUCTURE with >=2 seeds (the
  # same per-structure grouping the extractor runs on, via the shared
  # territoryStructureSeedCounts query); Compute enables iff an input is
  # selected AND a reference volume exists AND a centerline has been extracted
  # (CenterlineRefs non-empty).  Needs the wrapped carrier + a live scene (i1
  # also Qt); the shared count query + the widget enablement invariants
  # SKIP-PENDING bare + until the seam lands and RUN launched, reusing the
  # stub-centerline CenterlineRefs idiom so no SlicerVMTK is required (ADR-0027).
  # ALSO hosts the post-review refinement guards (green regression): a
  # successful Extract AND a Compute both DISARM placement (toggle the active
  # Place button off via the table's shared done() body, writing armed=0 onto
  # the shared display node) so a stray click after the action drops no seed
  # (ADR-0037 §Decision 4).  VMTK gate / extractor / C++ map run are stubbed, so
  # these RUN + PASS launched now without SlicerVMTK.
  test_territories_action_enablement.py
  # ADR-0037 slice 5 -- centerlines + seeds FOLLOW the anatomical-structure
  # show/hide.  Hiding a structure (input segment) omits its seeds from the 3D
  # seed glyphs AND the 2D projection (each seed mapped to its nearest structure
  # via SeedStructureMapping, gated on the segment's display visibility) and
  # hides its extracted centerline (tagged with VascularTerritories.
  # StructureSegmentId, synced by a widget-level segmentation-display-node
  # observer -- ADR-0013 §5, no displayable manager); showing restores them.
  # Needs the wrapped carrier + highlight display node + a live multi-segment
  # segmentation (i2 also Qt); SKIP-PENDING bare + until the seams land and RUN
  # launched (ADR-0027).  ALSO hosts the post-review refinement guards (green
  # regression): (a) the seed-repaint TRIGGER -- a SetSegmentVisibility toggle
  # repaints the seed glyphs VIA THE PIPELINE'S OWN OBSERVER (not a direct
  # rebuild call, unlike i1's filter test); (b) SetSegmentVisibility advances the
  # visibility_mtime cache-invalidation key; (c) the hover/grab hit-test
  # (_nearest_point_in_display) excludes a hidden-structure seed even under the
  # cursor; (d) VisibleStructuresCache builds per-structure vtkCellLocators ONCE
  # per visibility MTime and reuses them across seed_visible calls (the hover-
  # perf fix).  All RUN + PASS launched now.
  test_territories_structure_visibility.py
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

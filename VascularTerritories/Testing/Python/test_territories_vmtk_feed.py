# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""ADR-0037 Stage-3 — the VMTK centerline feed off the annotation carrier.

ADR-0037 §Decision 4 rewires the SlicerVMTK ``ExtractCenterline`` feed OFF
Slicer markups ONTO the Stage-1 annotation carrier
(``vtkMRMLCustomTerritoriesNode``).  ``ExtractCenterline`` reads
``GetNthControlPointPosition`` / ``GetNumberOfControlPoints`` and a
per-point *selected* flag (the inlet/root discrimination) off a markups
node; the transition builds a **transient** ``vtkMRMLMarkupsFiducialNode``
from the carrier's ordered per-territory points *inside* the extraction
call — preserving the start-endpoint ``selected`` convention — and
discards it after (no persistent markups node, ADR-0037/0014).  When
SlicerVMTK is absent the module **degrades gracefully**: placement and the
table work; only the extraction action is disabled with an explaining
tooltip (today the module hard-gates placement on VMTK — that coupling
goes away once off markups).

This file pins the Stage-3 increments:

* i1 (BARE) — the TRANSIENT-MARKUPS BUILDER CORE.  A territory's carrier
  points map to a fiducial-shaped payload: same count, same coordinates,
  SAME ORDER; exactly one inlet, at index 0, marked ``selected == False``
  while every other point is ``selected == True`` (the SlicerVMTK
  start/inlet convention).  ADR-0037 §Decision 4 + §Conformance [test]
  "reproduces the carrier points with the start-endpoint ``selected``
  flag".  Pure logic — no SlicerVMTK, no Qt, no live scene — so it RUNS
  BARE against the pure builder-core seam.
* i2 (launched) — SCENE-CLEAN.  After an extraction call NO
  ``vtkMRMLMarkupsFiducialNode`` persists in the scene (the transient node
  was removed).  ADR-0037 §Conformance [review] "no
  ``vtkMRMLMarkupsFiducialNode`` persisted by the annotation path",
  extended to the VMTK path.
* i3 (launched) — GRACEFUL DEGRADATION.  When ``'ExtractCenterline' not in
  moduleNames()`` the extraction ACTION is disabled (with a tooltip) and
  placement + the table remain functional; when present, the action is
  enabled.  ADR-0037 §Decision 4 + §Conformance [test] "extraction is
  disabled (not crashing) when SlicerVMTK is absent while placement still
  works".  Pins the guard/enablement, not an actual VMTK run.
* i4 (launched, SlicerVMTK-env-gated) — the REAL EXTRACTION WIRING.  An
  actual ``ExtractCenterlineLogic`` run over a territory's seeds produces a
  centerline model wired into the carrier's ``CenterlineRefs`` +
  ``Groupings`` under the right territory id (the Stage-4 territory-map
  contract).  This needs SlicerVMTK present, so it SKIPS CLEANLY when
  ``ExtractCenterline`` is absent (CI has no SlicerVMTK on the bare path;
  the launched self-test image does).
* i5 (launched) — PER-TERRITORY INVOCATION.  N territories carrying points
  drive N extraction invocations / N transient nodes (each built + torn
  down), never one merged node — mirroring the legacy per-``VascTerrId``
  grouping.  Asserted by monkeypatching the extraction logic to COUNT
  calls + CAPTURE the fed node, without a real VMTK run.
* i7 (launched) — GROUP BY STRUCTURE (revised slice 5).  A territory carrying
  ≥2 seeds on structure A AND ≥2 on structure B (portal + hepatic) yields TWO
  centerlines — one VMTK run PER ≥2-seed structure — BOTH in ``CenterlineRefs``
  and BOTH grouped under the territory id (the multi-system map region, §B4/§B5).
  A territory with 2 seeds on A but only 1 on B yields exactly ONE centerline
  (A's); the under-seeded structure B is SKIPPED (the per-structure ≥2 gate,
  §B4).  The extractor is stubbed to a small line polydata (via
  ``getCenterlineLogic``) so N models are minted without a real VMTK run — the
  invariant is the group-by-structure invocation shape + the per-structure gate,
  not the geometry.  Red->green (ADR-0027): FAILS against the landed
  single-tree extraction (one centerline per territory, later structures lost)
  and PASSES once extraction groups by structure and appends one centerline per
  ≥2-seed structure.  Launched (module Logic + a real multi-segment
  segmentation + stubbed extractor); SKIPS bare.
* i6 (launched) — RE-EXTRACTION IDEMPOTENCY.  Extracting a territory, then
  RE-EXTRACTING the SAME carrier/territory, leaves EXACTLY ONE
  ``CenterlineRefs`` entry, ONE ``TerritoryCenterline`` model, and a STABLE
  ``Groupings`` count for that territory — the second run REPLACES the
  first, never appends.  The prior centerline model is not orphaned in the
  scene.  ADR-0037 §Decision 4 (the Stage-4 territory-map contract is a
  MAP: one centerline per territory) + §Conformance no-drift.  The
  extractor is stubbed to a small line polydata (via ``getCenterlineLogic``)
  so a model is minted + wired without a real VMTK run.  This is the
  red->green invariant: it FAILS against an append-only
  ``_wireCenterlineOutput`` and PASSES once re-extraction clears the
  territory's prior refs + models before wiring (ADR-0027).

-- SEAM THE IMPLEMENTER MUST PROVIDE (proposed; sharpen at landing) --

The plan pins a BARE-TESTABLE pure builder core with a thin node-creation
wrapper.  i1 exercises the core directly; i2/i5 exercise the wrapper +
teardown; i3 the module-logic guard; i4 the real run.

  * A PURE builder core that maps a territory's ordered points +
    inlet-index to a fiducial-shaped payload WITHOUT a live scene — the
    plan's preferred seam.  Proposed:
    ``VascularTerritoriesLib.TransientVmtkSeeds.build_seed_payload(points,
    inlet_index=0) -> list[(x, y, z, selected: bool)]`` (a pure function
    returning per-point coordinate + ``selected`` tuples, ORDER preserved,
    index 0 marked ``selected == False``, the rest ``selected == True``).
    IMPLEMENTER SEAM PREFERENCE: keep this a pure function so i1 stays
    bare-testable; the ``vtkMRMLMarkupsFiducialNode`` creation
    (add-to-scene → feed → ``RemoveNode``) is a THIN wrapper over the core
    (proposed ``build_transient_fiducial(scene, payload) -> node``), NOT
    the tested unit for the mapping invariant.
  * The module Logic (``VascularTerritoriesLogic``, ADR-0004) drives the
    feed: it reuses the surviving helpers on this branch
    (``check_module_Extract_Centerline_installed`` / ``moduleNames`` guard,
    ``getCenterlineLogic`` lazy ``ExtractCenterlineLogic`` import,
    ``polyDataFromNode`` / ``preprocessAndDecimate`` decimated-surface
    seam), one call per territory.  Proposed entry point:
    ``VascularTerritoriesLogic.extractCenterlines(carrier, surfaceNode,
    segmentId)`` — builds a transient fiducial per territory, runs the
    extractor, wires the output into ``CenterlineRefs`` + ``Groupings``,
    and removes the transient node.
  * The extraction ACTION enablement is derived from the guard: the widget
    disables the action (with a tooltip) when the guard is False.  Proposed
    accessor: a widget/logic ``extractionActionEnabled()`` predicate (or a
    named ``qt.QAction`` reachable off the widget) that mirrors the guard,
    so i3 pins enablement without driving Qt paint.

-- WHY BARE (i1) vs LAUNCHED (i2/i3/i4/i5) --

i1's builder core is pure Python/VTK-value logic (coordinates + a boolean
per point); it needs neither a live ``mrmlScene`` nor SlicerVMTK and RUNS
BARE.  i2/i3/i5 need the module Logic + a live scene (transient-node
lifecycle, the ``moduleNames`` guard, per-territory invocation) reachable
only inside a launched Slicer, so they SKIP CLEANLY bare and RUN launched.
i4 additionally needs SlicerVMTK's ``ExtractCenterline`` module present, so
it SKIPS CLEANLY when the extractor is absent — CI's bare path has no
SlicerVMTK; the launched self-test image (ALive-Docker layers 5a-5c, see
the CMakeLists comment) does.  i6 needs the module Logic + a live scene (the
carrier's ``CenterlineRefs`` + ``Groupings`` map, the minted-model
lifecycle) but NOT SlicerVMTK — the extractor is stubbed via
``getCenterlineLogic`` — so it SKIPS CLEANLY bare and RUNS launched.

-- RUN-VS-SKIP DISCIPLINE (ADR-0027) --

Pre-implementation the builder core, the Logic feed entry point, and the
action-enablement accessor do not exist, so the import / ``hasattr`` guards
skip-pend; the skips lift at the Stage-3 implementation commit.  Under a
launched Slicer, verify run-vs-skip in the CI log once the seam lands —
never trust overall green (the launched harness is green-but-skipping
prone).

See also:
  * Docs/adr/0037-vascular-territories-off-markups.md  (§Decision 4)
  * Docs/adr/0014-livermarkups-dissolution.md  (no persistent markups)
  * Docs/adr/0004-python-cpp-boundary.md  (the feed lives in module Logic)
  * Docs/adr/0027-invariant-test-first.md  (RED / skip-pending discipline)
  * VascularTerritories/MRML/vtkMRMLCustomTerritoriesNode.h  (the carrier)
  * VascularTerritories/Testing/Python/test_territories_annotation_carrier.py
  * VascularTerritories/Testing/Python/conftest.py  (the cleanup fixtures)
"""

from __future__ import annotations

import pytest

vtk = pytest.importorskip("vtk")

CUSTOM_TERRITORIES_CLASS = "vtkMRMLCustomTerritoriesNode"
MARKUPS_FIDUCIAL_CLASS = "vtkMRMLMarkupsFiducialNode"
SEGMENTATION_CLASS = "vtkMRMLSegmentationNode"
EXTRACT_CENTERLINE_MODULE = "ExtractCenterline"

# Carrier API seam (also pinned by test_territories_annotation_carrier.py).
ADD_POINT_METHOD = "AddAnnotationPoint"
COUNT_METHOD = "GetNumberOfAnnotationPoints"
GET_NTH_METHOD = "GetNthAnnotationPoint"

# Stage-3 feed seam (proposed; sharpen at landing).
BUILDER_MODULE = "VascularTerritoriesLib.TransientVmtkSeeds"
BUILD_PAYLOAD_FUNC = "build_seed_payload"
LOGIC_FEED_METHOD = "extractCenterlines"

# Two distinct surgeon-named territory ids used across the tests.
TERRITORY_A = "SegmentVII"
TERRITORY_B = "SegmentVIII"


# --------------------------------------------------------------------------- #
# Skip-guards (mirror the launched-Slicer discipline in conftest.py)
# --------------------------------------------------------------------------- #


def _slicer_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _import_builder_or_skip():
    """Import the PURE transient-seed builder core, or skip-pend (ADR-0027).

    The pure core is the plan's preferred bare-testable seam: a function
    mapping ordered points + inlet-index to fiducial-shaped
    ``(x, y, z, selected)`` tuples with NO live scene.  Skip-pends until
    the Stage-3 builder lands.
    """
    try:
        import importlib

        module = importlib.import_module(BUILDER_MODULE)
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"{BUILDER_MODULE} not importable ({exc!r}) -- the ADR-0037 "
            "Stage-3 transient-seed builder core (§Decision 4) has not "
            "landed.  The skip lifts at the implementation commit (ADR-0027)."
        )
    func = getattr(module, BUILD_PAYLOAD_FUNC, None)
    if func is None:
        pytest.skip(
            f"{BUILDER_MODULE} has no {BUILD_PAYLOAD_FUNC} -- the ADR-0037 "
            "Stage-3 pure builder core has not landed (ADR-0027)."
        )
    return func


def _make_carrier_or_skip(slicer, name="VmtkFeedCarrierTest"):
    node = slicer.mrmlScene.AddNewNodeByClass(CUSTOM_TERRITORIES_CLASS, name)
    if node is None:
        pytest.skip(
            f"{CUSTOM_TERRITORIES_CLASS} not registered -- module Logic "
            "RegisterNodes() must wire this up (launched build)."
        )
    for method in (ADD_POINT_METHOD, COUNT_METHOD, GET_NTH_METHOD):
        if not hasattr(node, method):
            pytest.skip(
                f"{CUSTOM_TERRITORIES_CLASS} has no {method} -- the ADR-0037 "
                "annotation carrier (Stage-1) has not landed (ADR-0027)."
            )
    return node


def _logic_or_skip(slicer):
    """Instantiate the module Logic, or skip-pend on the Stage-3 feed method.

    The feed lives in ``VascularTerritoriesLogic`` (ADR-0004); skip-pends
    until the Stage-3 feed entry point lands.
    """
    try:
        from VascularTerritories import VascularTerritoriesLogic
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(f"VascularTerritoriesLogic not importable ({exc!r}).")
    logic = VascularTerritoriesLogic()
    if not hasattr(logic, LOGIC_FEED_METHOD):
        pytest.skip(
            f"VascularTerritoriesLogic has no {LOGIC_FEED_METHOD} -- the "
            "ADR-0037 Stage-3 VMTK feed entry point (§Decision 4) has not "
            "landed.  The skip lifts at the implementation commit (ADR-0027)."
        )
    return logic


def _count_fiducial_nodes(slicer):
    """Number of ``vtkMRMLMarkupsFiducialNode`` currently in the scene."""
    return slicer.mrmlScene.GetNumberOfNodesByClass(MARKUPS_FIDUCIAL_CLASS)


def _closed_surface_model(slicer):
    """A closed-surface model node the decimated-surface seam can read.

    A unit sphere stands in for the vessel surface: the feed's
    ``polyDataFromNode`` / ``preprocessAndDecimate`` seam takes polydata,
    not a specific anatomy, so any closed surface exercises the wiring.
    """
    source = vtk.vtkSphereSource()
    source.SetRadius(10.0)
    source.SetThetaResolution(32)
    source.SetPhiResolution(32)
    source.Update()
    model = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", "VmtkFeedSurface")
    model.SetAndObservePolyData(source.GetOutput())
    return model


# --------------------------------------------------------------------------- #
# i1 — the pure transient-seed builder core (BARE)
# --------------------------------------------------------------------------- #


def test_builder_preserves_count_coordinates_and_order():
    """i1: the builder reproduces the carrier points 1:1 in placement order.

    Same count, same coordinates, SAME ORDER as the input points — the
    transient fiducial mirrors the carrier's ordered per-territory list
    (ADR-0037 §Decision 4 "builds a transient ... node from the carrier's
    points ... preserving the ... convention").
    """
    build = _import_builder_or_skip()

    pts = [(10.0, 20.0, 30.0), (-5.0, 40.0, 15.0), (1.0, 2.0, 3.0)]
    payload = list(build(pts))

    assert len(payload) == len(pts), (
        f"the builder must emit one seed per carrier point (expected "
        f"{len(pts)}, got {len(payload)})."
    )
    for i, (expected, seed) in enumerate(zip(pts, payload)):
        assert (seed[0], seed[1], seed[2]) == pytest.approx(expected, abs=1e-9), (
            f"seed {i} must reproduce the carrier coordinate in placement order."
        )


def test_builder_marks_exactly_one_inlet_at_index_zero():
    """i1: exactly ONE inlet, at index 0, marked ``selected == False``.

    The SlicerVMTK start/inlet convention is the control point with
    ``selected == False``; every OTHER point is ``selected == True``.
    ADR-0037 §Decision 4 + §Conformance [test] "with the start-endpoint
    ``selected`` flag".
    """
    build = _import_builder_or_skip()

    pts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (3.0, 0.0, 0.0)]
    payload = list(build(pts))

    selected_flags = [bool(seed[3]) for seed in payload]
    inlet_indices = [i for i, sel in enumerate(selected_flags) if sel is False]

    assert inlet_indices == [0], (
        f"exactly one inlet, at index 0 (selected == False), is required; "
        f"got inlet indices {inlet_indices} from flags {selected_flags}."
    )
    assert all(selected_flags[1:]), (
        "every non-inlet point must be selected == True (SlicerVMTK convention)."
    )


def test_builder_single_point_is_the_inlet():
    """i1: a one-point territory yields a single inlet (selected == False).

    A degenerate single-seed territory still marks its one point as the
    inlet — the builder never emits a payload with no inlet (ADR-0037
    §Decision 4).
    """
    build = _import_builder_or_skip()

    payload = list(build([(5.0, 6.0, 7.0)]))

    assert len(payload) == 1
    assert bool(payload[0][3]) is False, (
        "a single-point territory's only point must be the inlet "
        "(selected == False)."
    )


# --------------------------------------------------------------------------- #
# i2 — scene-clean: no transient fiducial survives (launched)
# --------------------------------------------------------------------------- #


def test_extraction_leaves_no_persistent_fiducial(monkeypatch):
    """i2: after an extraction call NO markups fiducial persists in the scene.

    The transient ``vtkMRMLMarkupsFiducialNode`` is built inside the call
    and ``RemoveNode``'d after; the scene's fiducial count returns to its
    pre-call value.  ADR-0037 §Conformance [review] "no
    ``vtkMRMLMarkupsFiducialNode`` persisted by the annotation path",
    extended to the VMTK path.  The extractor itself is monkeypatched to a
    no-op so the invariant is the node LIFECYCLE, not a real VMTK run.
    """
    slicer = _slicer_or_skip()
    logic = _logic_or_skip(slicer)
    carrier = _make_carrier_or_skip(slicer)
    surface = _closed_surface_model(slicer)

    carrier.AddAnnotationPoint(TERRITORY_A, 1.0, 0.0, 0.0)
    carrier.AddAnnotationPoint(TERRITORY_A, 2.0, 0.0, 0.0)

    if not hasattr(logic, "getCenterlineLogic"):
        pytest.skip(
            "VascularTerritoriesLogic has no getCenterlineLogic -- the "
            "ADR-0037 Stage-3 extractor injection seam has not landed."
        )

    # Stub the extractor so no real VMTK run is required; the transient-node
    # lifecycle is what is pinned.
    class _StubExtractor:
        def extractCenterline(self, *args, **kwargs):  # noqa: N802 - VMTK verb
            return None

    monkeypatch.setattr(logic, "getCenterlineLogic", lambda: _StubExtractor())

    before = _count_fiducial_nodes(slicer)
    logic.extractCenterlines(carrier, surface, "")
    after = _count_fiducial_nodes(slicer)

    assert after == before, (
        f"the transient fiducial must be removed after extraction "
        f"(before={before}, after={after}) -- no persistent markups "
        "(ADR-0037 §Conformance [review])."
    )


# --------------------------------------------------------------------------- #
# i3 — graceful degradation: action follows the moduleNames guard (launched)
# --------------------------------------------------------------------------- #


def test_extraction_action_disabled_when_vmtk_absent(monkeypatch):
    """i3: the extraction action is DISABLED (with tooltip) when VMTK is absent.

    When ``'ExtractCenterline' not in moduleNames()`` the extraction action
    is disabled and carries an explaining tooltip; placement + the table
    stay live (the legacy VMTK-hard-gate on placement is gone).  ADR-0037
    §Decision 4 + §Conformance [test] "extraction is disabled (not
    crashing) when SlicerVMTK is absent while placement still works".  The
    ``moduleNames`` guard is monkeypatched so the test does not depend on
    the build's actual SlicerVMTK presence.
    """
    slicer = _slicer_or_skip()
    logic = _logic_or_skip(slicer)

    if not hasattr(logic, "check_module_Extract_Centerline_installed"):
        pytest.skip(
            "VascularTerritoriesLogic has no "
            "check_module_Extract_Centerline_installed -- the ADR-0037 "
            "graceful-degradation guard has not landed (ADR-0027)."
        )
    if not hasattr(logic, "extractionActionEnabled"):
        pytest.skip(
            "VascularTerritoriesLogic has no extractionActionEnabled -- the "
            "ADR-0037 Stage-3 action-enablement accessor (§Decision 4) has "
            "not landed.  The skip lifts at the implementation commit "
            "(ADR-0027)."
        )

    # VMTK ABSENT: the guard reports False -> the action is disabled.
    monkeypatch.setattr(slicer.util, "moduleNames", lambda: [])
    assert logic.extractionActionEnabled() is False, (
        "the extraction action must be DISABLED when ExtractCenterline is "
        "absent from moduleNames() (ADR-0037 §Decision 4)."
    )


def test_extraction_action_enabled_when_vmtk_present(monkeypatch):
    """i3: the extraction action is ENABLED when ``ExtractCenterline`` is present.

    The mirror of the disabled case: with the module present in
    ``moduleNames()`` the guard reports True and the action is enabled.
    ADR-0037 §Decision 4.
    """
    slicer = _slicer_or_skip()
    logic = _logic_or_skip(slicer)

    if not hasattr(logic, "extractionActionEnabled"):
        pytest.skip(
            "VascularTerritoriesLogic has no extractionActionEnabled -- the "
            "ADR-0037 Stage-3 action-enablement accessor has not landed "
            "(ADR-0027)."
        )

    monkeypatch.setattr(
        slicer.util, "moduleNames", lambda: [EXTRACT_CENTERLINE_MODULE]
    )
    assert logic.extractionActionEnabled() is True, (
        "the extraction action must be ENABLED when ExtractCenterline is "
        "present in moduleNames() (ADR-0037 §Decision 4)."
    )


# --------------------------------------------------------------------------- #
# i4 — the real extraction wiring (launched, SlicerVMTK-env-gated)
# --------------------------------------------------------------------------- #


def _require_slicer_vmtk_or_skip(slicer):
    """Skip cleanly when SlicerVMTK's ``ExtractCenterline`` is not present.

    CI's bare path has no SlicerVMTK; only the launched self-test image
    (ALive-Docker layers 5a-5c, see the CMakeLists comment) provides it.
    This env-gated invariant therefore SKIPS CLEANLY off that image.
    """
    if EXTRACT_CENTERLINE_MODULE not in slicer.util.moduleNames():
        pytest.skip(
            "SlicerVMTK's ExtractCenterline is not present -- the real "
            "centerline-extraction wiring (ADR-0037 §Decision 4, i4) is "
            "env-gated and skips cleanly off the SlicerVMTK image."
        )


def test_real_extraction_wires_centerline_into_carrier():
    """i4: a real ``ExtractCenterlineLogic`` run wires output into the carrier.

    Given a territory's seeds over a closed surface, the extraction
    produces a centerline model registered under the carrier's
    ``CenterlineRefs`` with a ``Groupings`` entry mapping it to the SAME
    territory id (the Stage-4 territory-map contract preserved).  ADR-0037
    §Decision 4 + §Conformance [test].  SlicerVMTK-env-gated: SKIPS CLEANLY
    when ``ExtractCenterline`` is absent.
    """
    slicer = _slicer_or_skip()
    _require_slicer_vmtk_or_skip(slicer)
    logic = _logic_or_skip(slicer)
    carrier = _make_carrier_or_skip(slicer)
    surface = _closed_surface_model(slicer)

    if not hasattr(carrier, "GetGrouping") or not hasattr(carrier, "GetNumberOfGroupings"):
        pytest.skip(
            f"{CUSTOM_TERRITORIES_CLASS} has no Groupings API -- the Stage-4 "
            "territory-map contract accessor is unavailable (ADR-0027)."
        )

    if not hasattr(logic, "getCenterlineReferenceIDs"):
        pytest.skip(
            "VascularTerritoriesLogic has no getCenterlineReferenceIDs -- the "
            "ADR-0037 Stage-3 CenterlineRefs accessor seam has not landed "
            "(ADR-0027)."
        )

    # Two inlet-plus-endpoint seeds so the extractor has a start + a target.
    carrier.AddAnnotationPoint(TERRITORY_A, 0.0, 0.0, 10.0)
    carrier.AddAnnotationPoint(TERRITORY_A, 0.0, 0.0, -10.0)

    before_fiducials = _count_fiducial_nodes(slicer)
    logic.extractCenterlines(carrier, surface, "")

    # The transient seed node was torn down: no persistent fiducial survives.
    assert _count_fiducial_nodes(slicer) == before_fiducials, (
        "the transient fiducial must be removed after a real extraction "
        "(ADR-0037 §Conformance [review])."
    )

    # The extraction registered exactly one centerline model under the
    # carrier's CenterlineRefs role.  The accessor seam (ADR-0037 §Decision 4)
    # is the module Logic's getCenterlineReferenceIDs reading the reference
    # role.
    centerlineIds = logic.getCenterlineReferenceIDs(carrier)
    assert len(centerlineIds) == 1, (
        f"a single territory's real extraction must register exactly one "
        f"centerline model in CenterlineRefs (got {centerlineIds})."
    )

    # The Groupings map ties the centerline node ID to the SAME territory id
    # (the Stage-4 territory-map contract preserved).
    assert carrier.GetGrouping(centerlineIds[0]) == TERRITORY_A, (
        "the extracted centerline must be grouped under its territory id "
        f"({TERRITORY_A}); got {carrier.GetGrouping(centerlineIds[0])!r}."
    )

    # The centerline model carries real geometry (a non-empty centerline).
    centerlineModel = slicer.mrmlScene.GetNodeByID(centerlineIds[0])
    assert centerlineModel is not None and centerlineModel.GetMesh() is not None, (
        "the CenterlineRefs entry must resolve to a model node with a mesh."
    )
    assert centerlineModel.GetMesh().GetNumberOfPoints() > 0, (
        "the real extraction must produce a non-empty centerline polydata."
    )


# --------------------------------------------------------------------------- #
# i5 — per-territory invocation: N territories -> N transient nodes (launched)
# --------------------------------------------------------------------------- #


def test_each_territory_drives_its_own_extraction_invocation(monkeypatch):
    """i5: N territories with points -> N extraction calls / N transient nodes.

    The feed builds + tears down ONE transient fiducial per territory and
    invokes the extractor once per territory — never merging all territories
    into a single node — mirroring the legacy per-``VascTerrId`` grouping.
    ADR-0037 §Decision 4.  The extractor is monkeypatched to COUNT calls
    and CAPTURE the fed node's per-call point count, so the invariant is
    the invocation shape, not a real VMTK run.
    """
    slicer = _slicer_or_skip()
    logic = _logic_or_skip(slicer)
    carrier = _make_carrier_or_skip(slicer)
    surface = _closed_surface_model(slicer)

    if not hasattr(logic, "getCenterlineLogic"):
        pytest.skip(
            "VascularTerritoriesLogic has no getCenterlineLogic -- the "
            "ADR-0037 Stage-3 extractor injection seam has not landed."
        )

    # Territory A: 2 seeds; territory B: 3 seeds — distinct counts so the
    # per-call capture can prove the nodes were NOT merged.
    a_pts = [(1.0, 0.0, 0.0), (2.0, 0.0, 0.0)]
    b_pts = [(0.0, 1.0, 0.0), (0.0, 2.0, 0.0), (0.0, 3.0, 0.0)]
    for x, y, z in a_pts:
        carrier.AddAnnotationPoint(TERRITORY_A, x, y, z)
    for x, y, z in b_pts:
        carrier.AddAnnotationPoint(TERRITORY_B, x, y, z)

    captured_counts = []

    class _CountingExtractor:
        def extractCenterline(self, seedsNode, *args, **kwargs):  # noqa: N802 - VMTK verb
            try:
                captured_counts.append(seedsNode.GetNumberOfControlPoints())
            except Exception:  # noqa: BLE001 - capture is best-effort across seams
                captured_counts.append(None)
            return None

    monkeypatch.setattr(logic, "getCenterlineLogic", lambda: _CountingExtractor())

    logic.extractCenterlines(carrier, surface, "")

    assert len(captured_counts) == 2, (
        f"two territories must drive two extraction invocations "
        f"(got {len(captured_counts)}) -- no merged node (ADR-0037 §Decision 4)."
    )
    assert sorted(c for c in captured_counts if c is not None) == [
        len(a_pts),
        len(b_pts),
    ], (
        "each invocation must be fed only its own territory's seeds "
        f"(expected per-call counts {sorted([len(a_pts), len(b_pts)])}, got "
        f"{sorted(c for c in captured_counts if c is not None)}) -- the "
        "transient nodes are per-territory, not merged."
    )


# --------------------------------------------------------------------------- #
# i6 — re-extraction idempotency: one centerline per territory (launched)
# --------------------------------------------------------------------------- #


def _line_polydata():
    """A tiny 2-point line standing in for an extracted centerline.

    Enough geometry that ``_wireCenterlineOutput`` mints + wires a
    ``TerritoryCenterline`` model (a ``None`` result wires nothing), without
    a real VMTK run.
    """
    points = vtk.vtkPoints()
    points.InsertNextPoint(0.0, 0.0, 10.0)
    points.InsertNextPoint(0.0, 0.0, -10.0)
    line = vtk.vtkCellArray()
    line.InsertNextCell(2)
    line.InsertCellPoint(0)
    line.InsertCellPoint(1)
    poly = vtk.vtkPolyData()
    poly.SetPoints(points)
    poly.SetLines(line)
    return poly


def _count_centerline_models(slicer):
    """Number of ``TerritoryCenterline`` model nodes currently in the scene."""
    count = 0
    nodes = slicer.mrmlScene.GetNodesByClass("vtkMRMLModelNode")
    nodes.InitTraversal()
    node = nodes.GetNextItemAsObject()
    while node is not None:
        if node.GetName() == "TerritoryCenterline":
            count += 1
        node = nodes.GetNextItemAsObject()
    return count


def test_re_extraction_replaces_the_territorys_centerline(monkeypatch):
    """i6: re-extracting the SAME territory leaves ONE ref / ONE model / stable grouping.

    ADR-0037 §Decision 4 makes ``CenterlineRefs`` + ``Groupings`` a MAP: one
    centerline per territory.  A first extraction wires one model; a SECOND
    extraction of the SAME carrier/territory must REPLACE it, not append --
    else the carrier accrues duplicate ``CenterlineRefs`` entries, an
    inconsistent ``Groupings`` count, and orphaned prior
    ``TerritoryCenterline`` models linger in the scene (ADR-0037 §Conformance
    no-drift; the Stage-4 territory-map contract).  The extractor is stubbed
    to a small line polydata so a model is minted + wired WITHOUT a real VMTK
    run -- the invariant is the ref/model/grouping bookkeeping, not the
    geometry.

    Red->green (ADR-0027): FAILS against an append-only
    ``_wireCenterlineOutput`` and PASSES once re-extraction clears the
    territory's prior refs + removes its prior model before wiring the new
    one.  Launched-only (module Logic + a live scene); SKIPS bare.
    """
    slicer = _slicer_or_skip()
    logic = _logic_or_skip(slicer)
    carrier = _make_carrier_or_skip(slicer)
    surface = _closed_surface_model(slicer)

    if not hasattr(logic, "getCenterlineLogic"):
        pytest.skip(
            "VascularTerritoriesLogic has no getCenterlineLogic -- the "
            "ADR-0037 Stage-3 extractor injection seam has not landed."
        )
    if not hasattr(logic, "getCenterlineReferenceIDs"):
        pytest.skip(
            "VascularTerritoriesLogic has no getCenterlineReferenceIDs -- the "
            "ADR-0037 Stage-3 CenterlineRefs accessor seam has not landed "
            "(ADR-0027)."
        )
    if not hasattr(carrier, "GetGrouping") or not hasattr(carrier, "GetNumberOfGroupings"):
        pytest.skip(
            f"{CUSTOM_TERRITORIES_CLASS} has no Groupings API -- the Stage-4 "
            "territory-map contract accessor is unavailable (ADR-0027)."
        )

    carrier.AddAnnotationPoint(TERRITORY_A, 0.0, 0.0, 10.0)
    carrier.AddAnnotationPoint(TERRITORY_A, 0.0, 0.0, -10.0)

    # Stub the extractor so a fresh small line is wired per call (no VMTK).
    class _LineExtractor:
        def extractCenterline(self, *args, **kwargs):  # noqa: N802 - VMTK verb
            return _line_polydata()

    monkeypatch.setattr(logic, "getCenterlineLogic", lambda: _LineExtractor())

    # First extraction: one ref, one model, one grouping for the territory.
    logic.extractCenterlines(carrier, surface, "")
    first_ids = logic.getCenterlineReferenceIDs(carrier)
    assert len(first_ids) == 1, (
        f"the first extraction must register exactly one centerline "
        f"(got {first_ids})."
    )
    first_groupings = carrier.GetNumberOfGroupings()

    # Second extraction of the SAME carrier/territory must REPLACE, not append.
    logic.extractCenterlines(carrier, surface, "")
    second_ids = logic.getCenterlineReferenceIDs(carrier)

    assert len(second_ids) == 1, (
        f"re-extracting the same territory must leave EXACTLY ONE "
        f"CenterlineRefs entry, not append (got {second_ids}) -- the "
        "territory-map contract is one centerline per territory (ADR-0037 "
        "§Decision 4)."
    )
    assert carrier.GetGrouping(second_ids[0]) == TERRITORY_A, (
        "the surviving centerline must stay grouped under its territory id "
        f"({TERRITORY_A}); got {carrier.GetGrouping(second_ids[0])!r}."
    )
    assert carrier.GetNumberOfGroupings() == first_groupings, (
        f"the Groupings count for the territory must be STABLE across a "
        f"re-extraction (was {first_groupings}, now "
        f"{carrier.GetNumberOfGroupings()}) -- no duplicate/orphan grouping."
    )
    assert _count_centerline_models(slicer) == 1, (
        "the prior TerritoryCenterline model must be removed on "
        "re-extraction, not orphaned in the scene (ADR-0037 §Conformance "
        f"no-drift); found {_count_centerline_models(slicer)} models."
    )


# --------------------------------------------------------------------------- #
# i7 — group by structure: one centerline per >=2-seed structure (launched)
# --------------------------------------------------------------------------- #
#
# Revised slice 5 (multi-system-territory-plan §B4/§B5): a territory owns seeds
# across possibly-multiple disjoint structures.  Extraction GROUPS the seeds by
# structure and runs VMTK ONCE per structure with >=2 seeds; a structure with
# <2 seeds is skipped.  N centerlines per territory, all grouped under the
# territory id.  These pin the invocation shape + the per-structure gate with a
# stubbed extractor (no SlicerVMTK), over a REAL multi-segment segmentation so
# the seed->structure mapping resolves each seed to a genuine vessel surface.

# Two vessel segments placed far apart so their closed surfaces are disjoint and
# a seed near each maps unambiguously to that structure.
_VEIN_CENTRE = (0.0, 0.0, 0.0)
_ARTERY_CENTRE = (100.0, 0.0, 0.0)
_VESSEL_RADIUS = 10.0

_VEIN_TERMINOLOGY = (
    "Segmentation category and type - 3D Slicer General Anatomy list"
    "~SCT^85756007^Body tissue~SCT^29092000^Vein~^^~Anatomic codes~^^~^^"
)
_ARTERY_TERMINOLOGY = (
    "Segmentation category and type - 3D Slicer General Anatomy list"
    "~SCT^85756007^Body tissue~SCT^51114001^Artery~^^~Anatomic codes~^^~^^"
)


def _add_tagged_vessel(slicer, segmentation, terminology, name, center):
    """Import one closed-surface sphere vessel segment tagged with ``terminology``."""
    source = vtk.vtkSphereSource()
    source.SetCenter(*center)
    source.SetRadius(_VESSEL_RADIUS)
    source.SetThetaResolution(16)
    source.SetPhiResolution(16)
    source.Update()
    modelNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", name)
    modelNode.SetAndObservePolyData(source.GetOutput())
    slicer.modules.segmentations.logic().ImportModelToSegmentationNode(
        modelNode, segmentation)
    slicer.mrmlScene.RemoveNode(modelNode)
    seg = segmentation.GetSegmentation()
    segId = seg.GetNthSegmentID(seg.GetNumberOfSegments() - 1)
    seg.GetSegment(segId).SetTag("TerminologyEntry", terminology)
    return segId


def _two_vessel_segmentation_or_skip(slicer):
    """A segmentation with a Vein + Artery vessel segment (disjoint surfaces)."""
    seg = slicer.mrmlScene.AddNewNodeByClass(SEGMENTATION_CLASS, "VmtkTwoVessels")
    if seg is None:
        pytest.skip("vtkMRMLSegmentationNode not registered (launched build).")
    seg.CreateDefaultDisplayNodes()
    _add_tagged_vessel(slicer, seg, _VEIN_TERMINOLOGY, "VeinModel", _VEIN_CENTRE)
    _add_tagged_vessel(slicer, seg, _ARTERY_TERMINOLOGY, "ArteryModel", _ARTERY_CENTRE)
    return seg


def _points_on_structure(center, n):
    """``n`` distinct genuine-ish points on the sphere of radius _VESSEL_RADIUS."""
    pts = []
    for k in range(n):
        # Spread the points around the sphere so they are distinct.
        offset = (k - (n - 1) / 2.0) * (_VESSEL_RADIUS / max(n, 1))
        pts.append((center[0], center[1] + offset, center[2] + _VESSEL_RADIUS))
    return pts


def _stub_line_extractor(logic, monkeypatch):
    """Stub the extractor so each call mints a fresh small line (no SlicerVMTK)."""
    class _LineExtractor:
        def extractCenterline(self, *args, **kwargs):  # noqa: N802 - VMTK verb
            return _line_polydata()

    monkeypatch.setattr(logic, "getCenterlineLogic", lambda: _LineExtractor())


def test_mixed_system_territory_yields_two_centerlines(monkeypatch):
    """i7: 2 seeds on vein + 2 on artery -> TWO centerlines, both the territory's.

    A territory straddling two disjoint structures runs VMTK once per structure
    (each with >=2 seeds), so it registers TWO ``CenterlineRefs`` entries, BOTH
    grouped under the SAME territory id — both feed the one map region (revised
    ADR-0037 slice 5; multi-system plan §B4/§B5).  The extractor is stubbed to a
    line so two models are minted without SlicerVMTK.  Launched; SKIPS bare.

    Red->green: FAILS against the landed single-tree extraction (one centerline
    per territory), PASSES once extraction groups by structure.
    """
    slicer = _slicer_or_skip()
    logic = _logic_or_skip(slicer)
    carrier = _make_carrier_or_skip(slicer)

    if not hasattr(logic, "getCenterlineLogic"):
        pytest.skip(
            "VascularTerritoriesLogic has no getCenterlineLogic (ADR-0027).")
    if not hasattr(logic, "getCenterlineReferenceIDs"):
        pytest.skip(
            "VascularTerritoriesLogic has no getCenterlineReferenceIDs "
            "(ADR-0027).")
    if not hasattr(carrier, "GetGrouping"):
        pytest.skip(
            f"{CUSTOM_TERRITORIES_CLASS} has no Groupings API (ADR-0027).")

    segmentation = _two_vessel_segmentation_or_skip(slicer)
    for x, y, z in _points_on_structure(_VEIN_CENTRE, 2):
        carrier.AddAnnotationPoint(TERRITORY_A, x, y, z)
    for x, y, z in _points_on_structure(_ARTERY_CENTRE, 2):
        carrier.AddAnnotationPoint(TERRITORY_A, x, y, z)

    _stub_line_extractor(logic, monkeypatch)
    logic.extractCenterlines(carrier, segmentation, "")

    refs = logic.getCenterlineReferenceIDs(carrier)
    assert len(refs) == 2, (
        "a territory with >=2 seeds on TWO structures must yield TWO centerlines "
        f"(one VMTK run per >=2-seed structure); got {refs} (revised ADR-0037 "
        "slice 5, §B4/§B5)."
    )
    for ref in refs:
        assert carrier.GetGrouping(ref) == TERRITORY_A, (
            "both centerlines must be grouped under the SAME territory id "
            f"({TERRITORY_A}) -- both feed the one map region; got "
            f"{carrier.GetGrouping(ref)!r} for {ref}."
        )


def test_under_seeded_structure_is_skipped(monkeypatch):
    """i7: 2 seeds on vein + 1 on artery -> ONE centerline (artery skipped).

    The per-structure ≥2 gate: only a structure with >=2 seeds yields a
    centerline, so a territory with 2 seeds on the vein but only 1 on the artery
    produces exactly ONE ``CenterlineRefs`` entry (the vein's) — the under-seeded
    artery is skipped (revised ADR-0037 slice 5; multi-system plan §B4).  The
    same gate drives the table warning (§B6, pinned in test_territories_table).
    Launched; SKIPS bare.
    """
    slicer = _slicer_or_skip()
    logic = _logic_or_skip(slicer)
    carrier = _make_carrier_or_skip(slicer)

    if not hasattr(logic, "getCenterlineLogic"):
        pytest.skip(
            "VascularTerritoriesLogic has no getCenterlineLogic (ADR-0027).")
    if not hasattr(logic, "getCenterlineReferenceIDs"):
        pytest.skip(
            "VascularTerritoriesLogic has no getCenterlineReferenceIDs "
            "(ADR-0027).")
    if not hasattr(carrier, "GetGrouping"):
        pytest.skip(
            f"{CUSTOM_TERRITORIES_CLASS} has no Groupings API (ADR-0027).")

    segmentation = _two_vessel_segmentation_or_skip(slicer)
    for x, y, z in _points_on_structure(_VEIN_CENTRE, 2):
        carrier.AddAnnotationPoint(TERRITORY_A, x, y, z)
    # Only ONE seed on the artery -- under the >=2 gate.
    single_artery = _points_on_structure(_ARTERY_CENTRE, 1)[0]
    carrier.AddAnnotationPoint(TERRITORY_A, *single_artery)

    _stub_line_extractor(logic, monkeypatch)
    logic.extractCenterlines(carrier, segmentation, "")

    refs = logic.getCenterlineReferenceIDs(carrier)
    assert len(refs) == 1, (
        "a structure with <2 seeds must be SKIPPED (the per-structure >=2 gate) "
        "-- 2 seeds on the vein + 1 on the artery yields ONE centerline (the "
        f"vein's); got {refs} (revised ADR-0037 slice 5, §B4)."
    )
    assert carrier.GetGrouping(refs[0]) == TERRITORY_A, (
        "the single surviving centerline must be grouped under the territory id "
        f"({TERRITORY_A}); got {carrier.GetGrouping(refs[0])!r}."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

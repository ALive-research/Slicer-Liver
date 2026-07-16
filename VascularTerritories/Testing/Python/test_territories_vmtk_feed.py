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
the CMakeLists comment) does.

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


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

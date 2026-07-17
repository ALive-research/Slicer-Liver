# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""ADR-0037 Stage-3 (slice 3) — the territory-map COMPUTE path off the carrier.

ADR-0037 §Decision 4 makes ``CenterlineRefs`` + ``Groupings`` a MAP: one
carrier, one territory map, all its centerlines.  Slice 3 re-sources the
map-compute path (``build_centerline_model`` +
``onCalculateVascularTerritoryMapButton``) OFF the ``slicer.util.getNodes(
"*Territory*")`` scene scan + the retired ``selectedVascularTerritorySegmId``
selector ONTO the annotation carrier (``vtkMRMLCustomTerritoriesNode``), the
same wrapper/carrier idiom Stages 1-3 built (ADR-0014 §"Fourth layer").

Maintainer-locked design pinned here (the planner resolved the crux from the
C++ ``MarkSegmentWithID`` / ``calculateVascularTerritoryMap`` consumers):

* The ``VascTerrId`` int ``vtkSlicerVascularTerritoriesLogic::MarkSegmentWithID``
  stamps into the centerline ``segmentId`` point-scalar is an ARBITRARY
  distinct positive labelmap scalar (NOT SCT / anatomy).  Slice 3 derives it
  DETERMINISTICALLY: enumerate ``carrier.GetAnnotationTerritoryIds()`` (the
  carrier's deterministic id order) -> ``index + 1`` (1-based; 0 = labelmap
  background).  Same territories -> same ints across repeated calls.
* ``build_centerline_model`` iterates the carrier's ``CenterlineRefs`` (via
  ``getCenterlineReferenceIDs``) + ``Groupings`` (centerlineId -> territory
  id), NOT ``getNodes("*Territory*")``.  The old ``SegmentationId`` int filter
  COLLAPSES: one carrier == one map == all its centerlines.  Each extracted
  centerline model is tagged with its DERIVED int (the redundant string
  ``VascularTerritories.VascTerrId`` tag + the ``int(...)`` reader mismatch go
  away).
* The output map target is DERIVED from the carrier, not selected: a carrier
  node-reference role (``TerritoryMapOutput``) -> one
  ``vtkMRMLSegmentationNode``, auto-created if absent, REUSED otherwise.  Its
  ``VascularTerritories.SegmentationId`` int (which the C++
  ``calculateVascularTerritoryMap`` reads + re-stamps on the target) is a
  PER-CARRIER ordinal, stable per carrier, distinct across carriers in one
  scene.
* ``selectedVascularTerritorySegmId`` is RETIRED (its ``.ui`` / param-node /
  ``setup()`` wiring gone).  ``onCalculateVascularTerritoryMapButton`` resolves
  input = ``inputSurfaceSelector``, centerline = carrier (re-sourced
  ``build_centerline_model``), refVolume = as today, target = derived.  The
  C++ ``calculateVascularTerritoryMap(target, refVolume, inputSeg,
  centerlineModel, colormap)`` signature stays intact.

This file pins the slice-3 increments:

* i1 (BARE, pure helper) — STRING->INT MAPPING.  Given a known territory-id
  order, the derived int for each id is its index + 1 (1-based); deterministic
  across two calls (same id -> same int).  The plan's PREFERRED seam is a pure
  helper so this is bare-testable without VMTK / a live scene; it import-guards
  on that helper and SKIP-PENDINGs until it lands.  If the implementer keeps
  the mapping only on a live carrier instead, i1b (launched) covers the same
  invariant read off a real carrier.
* i1b (launched) — the same mapping read off a LIVE carrier via a thin
  live-reader seam (``territory_label_int(carrier, territoryId)``), for when
  the mapping is not extractable as a pure list function.
* i2 (launched, extractor stubbed) — ``build_centerline_model`` SOURCES FROM
  THE CARRIER.  With two territories each carrying a centerline in
  ``CenterlineRefs``, the built model incorporates BOTH via the carrier refs,
  and does NOT depend on a ``*Territory*``-named scene scan (proven by naming
  the centerline models so a ``getNodes("*Territory*")`` scan would MISS them).
  Each centerline is marked with its derived int.
* i3 (launched) — OUTPUT TARGET DERIVED + REUSED.  The first compute creates a
  ``vtkMRMLSegmentationNode`` attached via the carrier's ``TerritoryMapOutput``
  role with a per-carrier-ordinal ``SegmentationId``; a SECOND compute REUSES
  the same node (no second output segmentation minted).  Two distinct carriers
  get DISTINCT ordinals (no collision).
* i4 (launched) — ``selectedVascularTerritorySegmId`` is GONE.  The slice-2
  KEEP-guard in ``test_territories_widget_panel`` is flipped (renamed
  ``test_map_path_selector_retired``) to assert the selector's ABSENCE; the
  button +
  ``onCalculateVascularTerritoryMapButton`` remain but resolve inputs without
  the selector.
* i5 (launched, env/eyeball-gated) — ``onCalculateVascularTerritoryMapButton``
  RESOLVES ALL INPUTS from the carrier + ``inputSurfaceSelector`` (no
  ``selectedVascularTerritorySegmId``).  ``logic.calculateVascularTerritoryMap``
  + ``build_centerline_model``'s classifier calls are stubbed so the wiring is
  observable WITHOUT the real C++ map run (which needs a reference volume +
  real inputs — that stays eyeball-gated).

-- SEAM THE IMPLEMENTER MUST PROVIDE (proposed; sharpen at landing) --

The plan PREFERS a bare-testable pure helper for the string->int mapping so
i1 needs no live scene.  Proposed (mirroring
``VascularTerritoriesLib.TransientVmtkSeeds``):

  * A PURE core mapping an ORDERED territory-id list -> ``{territoryId: int}``
    (1-based, index + 1).  Proposed
    ``VascularTerritoriesLib.TerritoryLabelMap.territory_label_ints(
    territory_ids: list[str]) -> dict[str, int]`` — a pure function, NO live
    carrier.  IMPLEMENTER SEAM PREFERENCE: keep this a pure function so i1
    stays bare-testable; the live read
    (``territory_label_int(carrier, territoryId)`` — enumerate
    ``carrier.GetAnnotationTerritoryIds()`` then index into the pure map) is a
    THIN wrapper, exercised by i1b launched.
  * ``build_centerline_model`` re-sourced onto the carrier.  Proposed
    signature evolution:
    ``VascularTerritoriesLogic.build_centerline_model(carrier, colormap)`` —
    iterate ``getCenterlineReferenceIDs(carrier)`` + ``GetGrouping`` for the
    territory id, derive the int via the label map, ``MarkSegmentWithID`` +
    ``AddSegmentToCenterlineModel`` per centerline, then
    ``InitializeCenterlineSearchModel``.  The old ``(colormap,
    vascSegmSelected)`` scene-scan signature retires.  i2 hasattr-guards on
    the new arity via a keyword probe so it SKIP-PENDINGs cleanly on the old
    signature.
  * The derived output target.  Proposed accessor on the module Logic:
    ``ensureTerritoryMapOutput(carrier) -> vtkMRMLSegmentationNode`` — resolve
    the carrier's ``TerritoryMapOutput`` node-reference role, auto-create +
    attach + stamp a per-carrier-ordinal ``VascularTerritories.SegmentationId``
    if absent, reuse otherwise.  The ordinal is stable per carrier and
    distinct across carriers (proposed: a monotonically-issued scene-wide
    counter, or the carrier's own scene ordinal — the invariant is
    stable-per-carrier + no-collision, NOT a specific numbering scheme).
  * ``onCalculateVascularTerritoryMapButton`` re-wired: input =
    ``inputSurfaceSelector.currentNode()``; carrier =
    ``_ensureAnnotationCarrier()``; centerlineModel =
    ``build_centerline_model(carrier, colormap)``; target =
    ``ensureTerritoryMapOutput(carrier)``; refVolume = as today
    (``GetFirstNodeByClass("vtkMRMLScalarVolumeNode")``).  No
    ``selectedVascularTerritorySegmId`` read anywhere.

-- WHY BARE (i1) vs LAUNCHED (i1b/i2/i3/i4/i5) --

i1's label map is pure Python value logic (an ordered id list -> ints); it
needs neither a live ``mrmlScene`` nor SlicerVMTK and RUNS BARE against the
pure core seam.  i1b/i2/i3/i4/i5 need the wrapped carrier / module widget /
module Logic + a live scene, reachable only inside a launched Slicer, so they
SKIP CLEANLY bare and RUN launched, matching the ``test_territories_*`` idiom.
i5 additionally stubs the C++ ``calculateVascularTerritoryMap`` +
classifier calls: the REAL map run needs a reference volume + real vessel
inputs and stays eyeball-gated (a real-anatomy walkthrough), so i5 pins the
INPUT-RESOLUTION wiring only and SKIP-CLEANs without the real map.

-- RUN-VS-SKIP DISCIPLINE (ADR-0027) --

Pre-implementation the pure label-map core, the re-sourced
``build_centerline_model`` arity, the ``ensureTerritoryMapOutput`` accessor,
and the retired selector do not exist, so the import / ``hasattr`` / signature
guards skip-pend; the skips lift at the slice-3 implementation commit.  Under
a launched Slicer, verify run-vs-skip in the CI log once the seam lands —
never trust overall green (the launched harness is green-but-skipping prone).

See also:
  * Docs/adr/0037-vascular-territories-off-markups.md  (§Decision 4)
  * Docs/adr/0014-livermarkups-dissolution.md  (the wrapper/carrier idiom)
  * Docs/adr/0004-python-cpp-boundary.md  (the compute path lives in Logic)
  * Docs/adr/0027-invariant-test-first.md  (RED / skip-pending discipline)
  * VascularTerritories/MRML/vtkMRMLCustomTerritoriesNode.h  (the carrier +
    GetAnnotationTerritoryIds + Groupings)
  * VascularTerritories/Logic/vtkSlicerVascularTerritoriesLogic.cxx
    (MarkSegmentWithID consumes the int; calculateVascularTerritoryMap reads +
    re-stamps VascularTerritories.SegmentationId on the target)
  * VascularTerritories/Testing/Python/test_territories_vmtk_feed.py  (the
    CenterlineRefs + Groupings + extractor-stub conventions this file reuses)
  * VascularTerritories/Testing/Python/conftest.py  (the cleanup fixtures)
"""

from __future__ import annotations

import pytest

CUSTOM_TERRITORIES_CLASS = "vtkMRMLCustomTerritoriesNode"
SEGMENTATION_CLASS = "vtkMRMLSegmentationNode"

# Carrier API seam (also pinned by test_territories_annotation_carrier.py /
# test_territories_vmtk_feed.py).
ADD_POINT_METHOD = "AddAnnotationPoint"
ANNOTATION_TERRITORY_IDS_METHOD = "GetAnnotationTerritoryIds"

# Slice-3 compute seam (proposed; sharpen at landing).
LABEL_MAP_MODULE = "VascularTerritoriesLib.TerritoryLabelMap"
LABEL_MAP_PURE_FUNC = "territory_label_ints"
LABEL_MAP_LIVE_FUNC = "territory_label_int"
BUILD_MODEL_METHOD = "build_centerline_model"
ENSURE_OUTPUT_METHOD = "ensureTerritoryMapOutput"

# The carrier node-reference role holding the derived output segmentation
# (planner proposal — sharpen at landing).
TERRITORY_MAP_OUTPUT_ROLE = "TerritoryMapOutput"

# The retired selector (slice-2 KEEP-guarded, slice-3 retired).
RETIRED_SELECTOR = "selectedVascularTerritorySegmId"

# Two distinct surgeon-named territory ids used across the tests, in a KNOWN
# order.  ``GetAnnotationTerritoryIds`` returns a deterministic (sorted) id
# order per the carrier header, so the derived ints follow that order.
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


def _import_label_map_module_or_skip():
    """Import the slice-3 territory-label-map seam module, or skip-pend (ADR-0027)."""
    try:
        import importlib

        return importlib.import_module(LABEL_MAP_MODULE)
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"{LABEL_MAP_MODULE} not importable ({exc!r}) -- the ADR-0037 "
            "slice-3 territory-label-map seam (§Decision 4) has not landed.  "
            "The skip lifts at the implementation commit (ADR-0027)."
        )


def _pure_label_map_or_skip():
    """Return the PURE ``territory_label_ints`` core, or skip-pend (ADR-0027).

    The plan's PREFERRED bare-testable seam: an ordered id list -> ints, NO
    live carrier.  Skip-pends if the implementer keeps the mapping only on a
    live carrier (i1b covers that shape launched).
    """
    module = _import_label_map_module_or_skip()
    func = getattr(module, LABEL_MAP_PURE_FUNC, None)
    if func is None:
        pytest.skip(
            f"{LABEL_MAP_MODULE} has no {LABEL_MAP_PURE_FUNC} -- the ADR-0037 "
            "slice-3 PURE label-map core has not landed.  If the mapping is "
            "read only off a live carrier, i1b covers the invariant launched "
            "(ADR-0027)."
        )
    return func


def _logic_or_skip(slicer):
    try:
        from VascularTerritories import VascularTerritoriesLogic
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(f"VascularTerritoriesLogic not importable ({exc!r}).")
    return VascularTerritoriesLogic()


def _make_carrier_or_skip(slicer, name="MapComputeCarrierTest"):
    node = slicer.mrmlScene.AddNewNodeByClass(CUSTOM_TERRITORIES_CLASS, name)
    if node is None:
        pytest.skip(
            f"{CUSTOM_TERRITORIES_CLASS} not registered -- module Logic "
            "RegisterNodes() must wire this up (launched build)."
        )
    for method in (ADD_POINT_METHOD, ANNOTATION_TERRITORY_IDS_METHOD):
        if not hasattr(node, method):
            pytest.skip(
                f"{CUSTOM_TERRITORIES_CLASS} has no {method} -- the ADR-0037 "
                "annotation carrier (Stage-1) has not landed (ADR-0027)."
            )
    return node


def _populate_two_territories(carrier):
    """Give the carrier two territories carrying points in a known order."""
    carrier.AddAnnotationPoint(TERRITORY_A, 0.0, 0.0, 10.0)
    carrier.AddAnnotationPoint(TERRITORY_A, 0.0, 0.0, -10.0)
    carrier.AddAnnotationPoint(TERRITORY_B, 10.0, 0.0, 0.0)
    carrier.AddAnnotationPoint(TERRITORY_B, -10.0, 0.0, 0.0)


# =========================================================================== #
# i1 — string->int mapping: PURE core (BARE)
# =========================================================================== #


def test_label_map_is_one_based_index_in_order():
    """i1: the derived int for a territory id is its order index + 1 (1-based).

    ADR-0037 §Decision 4 (maintainer-locked): enumerate the carrier's
    territory-id order -> ``index + 1``.  0 is reserved for the labelmap
    background, so the first territory maps to 1.  Pure value logic — no live
    scene, no VMTK — so it RUNS BARE against the pure core.
    """
    label_ints = _pure_label_map_or_skip()

    ids = [TERRITORY_A, TERRITORY_B]
    mapping = dict(label_ints(ids))

    assert mapping[ids[0]] == 1, (
        f"the first territory in order must derive int 1 (0 == background); "
        f"got {mapping.get(ids[0])!r}."
    )
    assert mapping[ids[1]] == 2, (
        f"the second territory in order must derive int 2; "
        f"got {mapping.get(ids[1])!r}."
    )
    assert min(mapping.values()) >= 1, (
        "no derived int may be 0 (0 is reserved for the labelmap background)."
    )


def test_label_map_is_deterministic_across_calls():
    """i1: same territory ids in the same order -> same ints across two calls.

    ADR-0037 §Decision 4: "same territories -> same ints across repeated
    calls".  Pins determinism against any set-iteration / dict-ordering
    accident in the pure core.
    """
    label_ints = _pure_label_map_or_skip()

    ids = [TERRITORY_A, TERRITORY_B]
    first = dict(label_ints(ids))
    second = dict(label_ints(ids))

    assert first == second, (
        f"the label map must be deterministic for a fixed id order "
        f"(first={first}, second={second})."
    )


def test_label_map_ints_are_distinct():
    """i1: distinct territories derive distinct ints (usable as labelmap scalars).

    ``MarkSegmentWithID`` stamps the derived int as the centerline's
    ``segmentId`` point-scalar; the downstream watershed needs distinct
    positive labels per territory (ADR-0037 §Decision 4).
    """
    label_ints = _pure_label_map_or_skip()

    ids = [TERRITORY_A, TERRITORY_B, "SegmentV"]
    values = list(dict(label_ints(ids)).values())

    assert len(set(values)) == len(values), (
        f"distinct territories must derive distinct labelmap ints; got {values}."
    )


# =========================================================================== #
# i1b — the same mapping read off a LIVE carrier (launched)
# =========================================================================== #


def test_live_carrier_label_int_matches_annotation_order():
    """i1b: the live-carrier read derives index-in-``GetAnnotationTerritoryIds`` + 1.

    The thin live wrapper (``territory_label_int(carrier, territoryId)``)
    indexes the carrier's ``GetAnnotationTerritoryIds()`` order and returns
    index + 1 — the same invariant as i1, read off a real carrier for when the
    mapping is not extractable as a pure list function (ADR-0037 §Decision 4).
    Launched-only (wrapped carrier); SKIPS bare.
    """
    slicer = _slicer_or_skip()
    module = _import_label_map_module_or_skip()
    live_read = getattr(module, LABEL_MAP_LIVE_FUNC, None)
    if live_read is None:
        pytest.skip(
            f"{LABEL_MAP_MODULE} has no {LABEL_MAP_LIVE_FUNC} -- the ADR-0037 "
            "slice-3 live-carrier label-map reader has not landed (ADR-0027)."
        )

    carrier = _make_carrier_or_skip(slicer)
    _populate_two_territories(carrier)

    ordered_ids = list(carrier.GetAnnotationTerritoryIds())
    for expected_index, territoryId in enumerate(ordered_ids):
        assert live_read(carrier, territoryId) == expected_index + 1, (
            f"territory {territoryId!r} at order index {expected_index} must "
            f"derive int {expected_index + 1}; got "
            f"{live_read(carrier, territoryId)!r}."
        )


# =========================================================================== #
# i2 — build_centerline_model SOURCES FROM THE CARRIER (launched, stubbed)
# =========================================================================== #


def _build_model_carrier_sourced_or_skip(logic, carrier, colormap):
    """Call the re-sourced ``build_centerline_model(carrier, colormap)``.

    Skip-pends unless the method both exists AND accepts the carrier-sourced
    signature: the old ``build_centerline_model(colormap, vascSegmSelected)``
    takes an int filter, not a carrier, so a raw call on the old arity would
    mis-source.  Probes by keyword so the skip is clean on the pre-slice-3
    signature (ADR-0027).
    """
    method = getattr(logic, BUILD_MODEL_METHOD, None)
    if method is None:
        pytest.skip(
            f"VascularTerritoriesLogic has no {BUILD_MODEL_METHOD} "
            "(ADR-0027)."
        )
    try:
        return method(carrier, colormap)
    except TypeError:
        pytest.skip(
            f"{BUILD_MODEL_METHOD} does not accept the carrier-sourced "
            "signature (carrier, colormap) -- the ADR-0037 slice-3 re-source "
            "(§Decision 4) has not landed; the old (colormap, "
            "vascSegmSelected) scene-scan signature survives (ADR-0027)."
        )


def _colormap_or_skip(slicer, logic):
    """A colour node for the centerline model display, or skip-pend.

    ``build_centerline_model`` binds the model's display to a colour node; any
    scene colour node stands in (the invariant is the carrier sourcing, not
    the colours).
    """
    colormap = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLColorTableNode")
    if colormap is None:
        colormap = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLColorTableNode", "MapComputeColorsTest")
    if colormap is None:
        pytest.skip("no vtkMRMLColorTableNode available for the model display.")
    return colormap


def _attach_stub_centerline(slicer, logic, carrier, territoryId, name):
    """Wire a small line model into the carrier's CenterlineRefs + Groupings.

    Uses the node-reference + grouping API directly (NOT the Stage-3
    ``_wireCenterlineOutput`` helper, which names its models "TerritoryCenterline"
    — a name a legacy ``getNodes("*Territory*")`` scan WOULD catch).  The model
    is DELIBERATELY named without "Territory" so such a scan would MISS it,
    proving i2 sources from the carrier refs, not the scan.
    """
    import vtk

    points = vtk.vtkPoints()
    points.InsertNextPoint(0.0, 0.0, 10.0)
    points.InsertNextPoint(0.0, 0.0, -10.0)
    lines = vtk.vtkCellArray()
    lines.InsertNextCell(2)
    lines.InsertCellPoint(0)
    lines.InsertCellPoint(1)
    poly = vtk.vtkPolyData()
    poly.SetPoints(points)
    poly.SetLines(lines)

    model = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", name)
    model.SetAndObserveMesh(poly)

    role = getattr(logic, "CENTERLINE_REFERENCE_ROLE", "CenterlineRefs")
    carrier.AddNodeReferenceID(role, model.GetID())
    if hasattr(carrier, "SetGrouping"):
        carrier.SetGrouping(model.GetID(), territoryId)
    return model


def test_build_centerline_model_sources_from_carrier_refs(monkeypatch):
    """i2: the built model incorporates BOTH carrier-referenced centerlines.

    With two territories each carrying a centerline model in the carrier's
    ``CenterlineRefs``, ``build_centerline_model(carrier, colormap)``
    incorporates BOTH via the carrier refs.  The centerline models are named
    so a legacy ``slicer.util.getNodes("*Territory*")`` scan would MISS them,
    proving the carrier-ref path is used, not the scene scan (ADR-0037
    §Decision 4).  The classifier calls (``AddSegmentToCenterlineModel`` /
    ``InitializeCenterlineSearchModel``) are captured, not run against real
    geometry, so the invariant is the SOURCING, not the C++ append math.
    Launched-only; SKIPS bare.
    """
    slicer = _slicer_or_skip()
    logic = _logic_or_skip(slicer)
    carrier = _make_carrier_or_skip(slicer)
    colormap = _colormap_or_skip(slicer, logic)

    if not hasattr(logic, "getCenterlineReferenceIDs"):
        pytest.skip(
            "VascularTerritoriesLogic has no getCenterlineReferenceIDs -- the "
            "ADR-0037 CenterlineRefs accessor seam has not landed (ADR-0027)."
        )

    _populate_two_territories(carrier)
    # Names WITHOUT "Territory" so a legacy getNodes("*Territory*") scan misses
    # them; the carrier refs are the only path to reach them.
    model_a = _attach_stub_centerline(
        slicer, logic, carrier, TERRITORY_A, "VesselCenterlineAlpha")
    model_b = _attach_stub_centerline(
        slicer, logic, carrier, TERRITORY_B, "VesselCenterlineBeta")

    # Capture which centerline models the classifier is asked to add, without
    # driving the real C++ append.
    added = []
    if hasattr(logic, "scl"):
        monkeypatch.setattr(
            logic.scl,
            "AddSegmentToCenterlineModel",
            lambda summed, segment: added.append(segment),
        )
        monkeypatch.setattr(
            logic.scl, "MarkSegmentWithID", lambda segment, segmentId: None)
        monkeypatch.setattr(
            logic.scl, "InitializeCenterlineSearchModel", lambda model: None)

    _build_model_carrier_sourced_or_skip(logic, carrier, colormap)

    added_ids = {m.GetID() for m in added if m is not None}
    assert model_a.GetID() in added_ids and model_b.GetID() in added_ids, (
        "build_centerline_model must incorporate BOTH carrier-referenced "
        "centerlines (sourced from CenterlineRefs, not a *Territory* scene "
        f"scan); added {added_ids}, expected both "
        f"{{{model_a.GetID()}, {model_b.GetID()}}}."
    )


def test_build_centerline_model_marks_each_with_derived_int(monkeypatch):
    """i2: each carrier centerline is marked with its DERIVED int.

    ``build_centerline_model`` derives the int from the territory-id order
    (index + 1) and passes it to ``MarkSegmentWithID`` per centerline — NOT the
    retired string ``VascularTerritories.VascTerrId`` attribute read (ADR-0037
    §Decision 4).  The mark call is captured so the invariant is the derived
    int, not the C++ point-scalar stamping.  Launched-only; SKIPS bare.
    """
    slicer = _slicer_or_skip()
    logic = _logic_or_skip(slicer)
    carrier = _make_carrier_or_skip(slicer)
    colormap = _colormap_or_skip(slicer, logic)

    if not hasattr(logic, "scl"):
        pytest.skip(
            "VascularTerritoriesLogic has no scl (the C++ classification "
            "logic) -- launched build required (ADR-0027)."
        )
    if not hasattr(logic, "getCenterlineReferenceIDs"):
        pytest.skip(
            "VascularTerritoriesLogic has no getCenterlineReferenceIDs "
            "(ADR-0027)."
        )

    _populate_two_territories(carrier)
    model_a = _attach_stub_centerline(
        slicer, logic, carrier, TERRITORY_A, "VesselCenterlineAlpha")
    model_b = _attach_stub_centerline(
        slicer, logic, carrier, TERRITORY_B, "VesselCenterlineBeta")

    marks = {}
    monkeypatch.setattr(
        logic.scl,
        "MarkSegmentWithID",
        lambda segment, segmentId: marks.__setitem__(segment.GetID(), segmentId),
    )
    monkeypatch.setattr(
        logic.scl, "AddSegmentToCenterlineModel", lambda summed, segment: None)
    monkeypatch.setattr(
        logic.scl, "InitializeCenterlineSearchModel", lambda model: None)

    _build_model_carrier_sourced_or_skip(logic, carrier, colormap)

    # The derived ints follow GetAnnotationTerritoryIds() order (index + 1),
    # mapped onto each territory's centerline via Groupings.
    ordered_ids = list(carrier.GetAnnotationTerritoryIds())
    expected = {territoryId: i + 1 for i, territoryId in enumerate(ordered_ids)}
    grouping_a = carrier.GetGrouping(model_a.GetID())
    grouping_b = carrier.GetGrouping(model_b.GetID())

    assert marks.get(model_a.GetID()) == expected[grouping_a], (
        f"centerline for {grouping_a!r} must be marked with its derived int "
        f"{expected[grouping_a]}; got {marks.get(model_a.GetID())!r}."
    )
    assert marks.get(model_b.GetID()) == expected[grouping_b], (
        f"centerline for {grouping_b!r} must be marked with its derived int "
        f"{expected[grouping_b]}; got {marks.get(model_b.GetID())!r}."
    )
    assert all(v >= 1 for v in marks.values()), (
        "no centerline may be marked with 0 (0 is the labelmap background)."
    )


# =========================================================================== #
# i3 — output target DERIVED from the carrier + REUSED (launched)
# =========================================================================== #


def _ensure_output_or_skip(logic, carrier):
    method = getattr(logic, ENSURE_OUTPUT_METHOD, None)
    if method is None:
        pytest.skip(
            f"VascularTerritoriesLogic has no {ENSURE_OUTPUT_METHOD} -- the "
            "ADR-0037 slice-3 derived-output-target accessor (§Decision 4) has "
            "not landed.  The skip lifts at the implementation commit "
            "(ADR-0027)."
        )
    return method(carrier)


def _first_reference_id(carrier, role):
    """The first node id referenced under ``role`` on ``carrier``, or None."""
    if carrier.GetNumberOfNodeReferences(role) == 0:
        return None
    return carrier.GetNthNodeReferenceID(role, 0)


def test_first_compute_derives_and_attaches_output_segmentation():
    """i3: the first compute mints a segmentation attached via ``TerritoryMapOutput``.

    ADR-0037 §Decision 4: the output map target is DERIVED from the carrier,
    not selected — the carrier's ``TerritoryMapOutput`` node-reference role
    resolves to a ``vtkMRMLSegmentationNode``, auto-created + attached on first
    compute, carrying a per-carrier-ordinal ``VascularTerritories.SegmentationId``
    the C++ ``calculateVascularTerritoryMap`` reads + re-stamps.  Launched-only;
    SKIPS bare.
    """
    slicer = _slicer_or_skip()
    logic = _logic_or_skip(slicer)
    carrier = _make_carrier_or_skip(slicer)

    target = _ensure_output_or_skip(logic, carrier)

    assert target is not None and target.IsA(SEGMENTATION_CLASS), (
        "the derived output target must be a vtkMRMLSegmentationNode "
        f"(got {target!r})."
    )
    attached_id = _first_reference_id(carrier, TERRITORY_MAP_OUTPUT_ROLE)
    assert attached_id == target.GetID(), (
        "the output segmentation must be attached via the carrier's "
        f"{TERRITORY_MAP_OUTPUT_ROLE!r} node-reference role (attached "
        f"{attached_id!r}, target {target.GetID()!r})."
    )
    segm_id = target.GetAttribute("VascularTerritories.SegmentationId")
    assert segm_id is not None and str(segm_id).strip() != "", (
        "the derived target must carry a VascularTerritories.SegmentationId "
        "int (the C++ calculateVascularTerritoryMap reads + re-stamps it)."
    )
    assert str(segm_id).strip().isdigit() or (
        str(segm_id).strip().lstrip("-").isdigit()), (
        f"the SegmentationId ordinal must be an int; got {segm_id!r}."
    )


def test_second_compute_reuses_the_same_output():
    """i3: a SECOND compute REUSES the same output segmentation, mints no second.

    ADR-0037 §Decision 4: one carrier == one map.  Re-computing must resolve
    the SAME ``TerritoryMapOutput`` node, never accrue a second output
    segmentation.  Launched-only; SKIPS bare.
    """
    slicer = _slicer_or_skip()
    logic = _logic_or_skip(slicer)
    carrier = _make_carrier_or_skip(slicer)

    before = slicer.mrmlScene.GetNumberOfNodesByClass(SEGMENTATION_CLASS)
    first = _ensure_output_or_skip(logic, carrier)
    minted = slicer.mrmlScene.GetNumberOfNodesByClass(SEGMENTATION_CLASS) - before

    second = _ensure_output_or_skip(logic, carrier)
    after = slicer.mrmlScene.GetNumberOfNodesByClass(SEGMENTATION_CLASS)

    assert first is not None and second is not None
    assert second.GetID() == first.GetID(), (
        "the second compute must REUSE the same output segmentation "
        f"(first {first.GetID()!r}, second {second.GetID()!r})."
    )
    assert after == before + minted, (
        "the second compute must mint NO additional output segmentation "
        f"(before={before}, after first={before + minted}, after second="
        f"{after})."
    )
    assert carrier.GetNumberOfNodeReferences(TERRITORY_MAP_OUTPUT_ROLE) == 1, (
        "exactly one output segmentation may be attached via "
        f"{TERRITORY_MAP_OUTPUT_ROLE!r} (one carrier == one map)."
    )


def test_two_carriers_get_distinct_ordinals():
    """i3: two distinct carriers derive DISTINCT ``SegmentationId`` ordinals.

    ADR-0037 §Decision 4: two carriers in one scene must not collide — the
    per-carrier ordinal is stable per carrier AND distinct across carriers, so
    the C++ ``calculateVascularTerritoryMap`` re-stamps two different labelmap
    identities.  Launched-only; SKIPS bare.
    """
    slicer = _slicer_or_skip()
    logic = _logic_or_skip(slicer)
    carrier_a = _make_carrier_or_skip(slicer, "MapComputeCarrierA")
    carrier_b = _make_carrier_or_skip(slicer, "MapComputeCarrierB")

    target_a = _ensure_output_or_skip(logic, carrier_a)
    target_b = _ensure_output_or_skip(logic, carrier_b)

    ordinal_a = target_a.GetAttribute("VascularTerritories.SegmentationId")
    ordinal_b = target_b.GetAttribute("VascularTerritories.SegmentationId")

    assert ordinal_a is not None and ordinal_b is not None
    assert ordinal_a != ordinal_b, (
        "two distinct carriers must derive DISTINCT SegmentationId ordinals "
        f"(carrier A {ordinal_a!r}, carrier B {ordinal_b!r}) -- no collision."
    )
    assert target_a.GetID() != target_b.GetID(), (
        "two distinct carriers must resolve to distinct output segmentations."
    )


# =========================================================================== #
# i4 — selectedVascularTerritorySegmId is GONE (launched)
# =========================================================================== #
#
# The slice-2 KEEP-guard in test_territories_widget_panel (flipped + renamed
# test_map_path_selector_retired there) asserts the selector's absence.  This
# test is the
# slice-3-owned home of the removal invariant; it gates on the removal having
# landed so it collects + SKIP-PENDINGs cleanly while the selector survives.


def _make_widget_or_skip(slicer):
    from slicer_pytest_support import require_qt_widget as _require_qt_widget

    _require_qt_widget()
    from VascularTerritories import VascularTerritoriesWidget

    widget = VascularTerritoriesWidget()
    widget.setup()
    return widget


def _detach_scene_observers(slicer, widget):
    for event, handler in (
        (slicer.mrmlScene.StartCloseEvent, widget.onSceneStartClose),
        (slicer.mrmlScene.EndCloseEvent, widget.onSceneEndClose),
    ):
        try:
            widget.removeObserver(slicer.mrmlScene, event, handler)
        except Exception:  # noqa: BLE001 - best-effort across widget shapes
            pass


def _slice3_selector_retired(widget) -> bool:
    """True once ``selectedVascularTerritorySegmId`` is gone from the ui."""
    ui = getattr(widget, "ui", None)
    if ui is None:
        return False
    return not hasattr(ui, RETIRED_SELECTOR)


def test_selected_territory_selector_retired(qt_widgets):
    """i4: ``selectedVascularTerritorySegmId`` is ABSENT after slice 3.

    ADR-0037 §Decision 4 (maintainer-locked): the per-map output selector is
    retired — its ``.ui`` widget, its param-node role, and its ``setup()``
    wiring go.  The Compute-territory-map BUTTON +
    ``onCalculateVascularTerritoryMapButton`` REMAIN, but resolve inputs
    without the selector.  Launched-only; SKIP-PENDINGs while the selector
    survives, RUNS once slice 3 retires it (ADR-0027).
    """
    slicer = _slicer_or_skip()
    widget = _make_widget_or_skip(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)

    if not _slice3_selector_retired(widget):
        pytest.skip(
            "selectedVascularTerritorySegmId still present -- the ADR-0037 "
            "slice-3 selector retirement has not landed (ADR-0027)."
        )

    assert not hasattr(widget.ui, RETIRED_SELECTOR), (
        f"the {RETIRED_SELECTOR!r} selector must be retired (ADR-0037 §Decision 4)."
    )
    # The nodeSelectors registry must no longer carry the retired role.
    node_selectors = getattr(widget, "nodeSelectors", [])
    roles = [role for _selector, role in node_selectors]
    assert "VascularTerritorySegmentation" not in roles, (
        "the retired selector's param-node role (VascularTerritorySegmentation) "
        "must be dropped from nodeSelectors (ADR-0037 §Decision 4)."
    )
    # The button + handler survive.
    assert hasattr(widget.ui, "calculateVascularTerritoryMapButton"), (
        "the Compute-territory-map button must survive slice 3."
    )
    assert hasattr(widget, "onCalculateVascularTerritoryMapButton"), (
        "onCalculateVascularTerritoryMapButton must survive slice 3."
    )


# =========================================================================== #
# i5 — button resolves ALL inputs from carrier + inputSurfaceSelector
#       (launched, env/eyeball-gated — stubbed C++ map run)
# =========================================================================== #


def test_calculate_button_resolves_inputs_without_selector(qt_widgets, monkeypatch):
    """i5: ``onCalculateVascularTerritoryMapButton`` resolves inputs sans selector.

    ADR-0037 §Decision 4: the button resolves input = ``inputSurfaceSelector``,
    centerline = carrier (re-sourced ``build_centerline_model``), refVolume = a
    scene scalar volume, target = the derived ``TerritoryMapOutput`` — NO
    ``selectedVascularTerritorySegmId`` read.  ``logic.calculateVascularTerritoryMap``
    + ``build_centerline_model`` are stubbed so the wiring is OBSERVABLE without
    the real C++ map run (which needs a reference volume + real vessel inputs
    and stays eyeball-gated).  The invariant is the INPUT RESOLUTION: the
    target passed to ``calculateVascularTerritoryMap`` is the carrier-derived
    output, and the input segmentation is ``inputSurfaceSelector``'s node.

    Launched-only; SKIP-PENDINGs while the slice-3 rewire has not landed, and
    SKIP-CLEANs without a scene scalar volume (the button early-returns /
    raises on a missing refVolume today — that path stays eyeball-gated).
    """
    slicer = _slicer_or_skip()
    widget = _make_widget_or_skip(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)

    if not _slice3_selector_retired(widget):
        pytest.skip(
            "selectedVascularTerritorySegmId still present -- the ADR-0037 "
            "slice-3 button rewire has not landed (ADR-0027)."
        )
    if not hasattr(widget.logic, ENSURE_OUTPUT_METHOD):
        pytest.skip(
            f"VascularTerritoriesLogic has no {ENSURE_OUTPUT_METHOD} -- the "
            "slice-3 derived-output accessor has not landed (ADR-0027)."
        )

    import vtk  # noqa: F401 — sphere source lives in the wiring helper
    from test_vessel_highlight_wiring import _sphere_segmentation

    input_segmentation = _sphere_segmentation(slicer, radius=30.0)
    widget.ui.inputSurfaceSelector.setCurrentNode(input_segmentation)

    # A reference scalar volume so the button's refVolume guard passes without
    # a real anatomy import.
    ref_volume = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLScalarVolumeNode", "MapComputeRefVolumeTest")
    image = vtk.vtkImageData()
    image.SetDimensions(4, 4, 4)
    image.AllocateScalars(vtk.VTK_SHORT, 1)
    ref_volume.SetAndObserveImageData(image)

    # Stub the re-sourced build_centerline_model to a model with >= 2 points so
    # the button's numberOfPoints guard passes without a real classifier run.
    def _stub_build(carrier, colormap):
        points = vtk.vtkPoints()
        points.InsertNextPoint(0.0, 0.0, 10.0)
        points.InsertNextPoint(0.0, 0.0, -10.0)
        poly = vtk.vtkPolyData()
        poly.SetPoints(points)
        model = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLModelNode", "MapComputeCenterlineModelTest")
        model.SetAndObserveMesh(poly)
        return model

    monkeypatch.setattr(widget.logic, BUILD_MODEL_METHOD, _stub_build)

    captured = {}

    def _stub_calculate(target, refVolume, inputSeg, centerlineModel, colormap):
        captured["target"] = target
        captured["refVolume"] = refVolume
        captured["inputSeg"] = inputSeg
        captured["centerlineModel"] = centerlineModel

    monkeypatch.setattr(
        widget.logic, "calculateVascularTerritoryMap", _stub_calculate)

    widget.onCalculateVascularTerritoryMapButton()

    assert captured, (
        "onCalculateVascularTerritoryMapButton must reach "
        "calculateVascularTerritoryMap with resolved inputs (ADR-0037 "
        "§Decision 4)."
    )
    assert captured.get("inputSeg") is input_segmentation, (
        "the input segmentation must be resolved from inputSurfaceSelector, "
        "not the retired selector (ADR-0037 §Decision 4)."
    )
    # The target is the carrier-derived TerritoryMapOutput, not a selected node.
    carrier = widget._ensureAnnotationCarrier()
    derived_target_id = _first_reference_id(carrier, TERRITORY_MAP_OUTPUT_ROLE)
    target = captured.get("target")
    assert target is not None and target.IsA(SEGMENTATION_CLASS), (
        "the map target must be a carrier-derived vtkMRMLSegmentationNode."
    )
    assert derived_target_id == target.GetID(), (
        "the map target must be the carrier's derived TerritoryMapOutput, not "
        f"a selected node (derived {derived_target_id!r}, passed "
        f"{target.GetID()!r})."
    )


# --------------------------------------------------------------------------- #
# Liver-segment resolution — the map compute finds the liver region by its
# SNOMED-CT tag (ADR-0011), and fails legibly when no such segment exists.
# --------------------------------------------------------------------------- #

_LIVER_TERMINOLOGY = (
    "Segmentation category and type - 3D Slicer General Anatomy list"
    "~SCT^123037004^Anatomical Structure~SCT^10200004^Liver~^^~Anatomic codes~^^~^^"
)


def _cpp_logic_or_skip(logic):
    """The wrapped C++ ``vtkSlicerVascularTerritoriesLogic`` (``logic.scl``).

    ``GetLiverSegmentId`` lives on the C++ logic, not the Python
    ``VascularTerritoriesLogic`` wrapper -- reach it through ``scl``.
    """
    cpp = getattr(logic, "scl", None)
    if cpp is None or not hasattr(cpp, "GetLiverSegmentId"):
        pytest.skip(
            "vtkSlicerVascularTerritoriesLogic has no GetLiverSegmentId -- the "
            "C++ logic is unavailable on this build (ADR-0027)."
        )
    return cpp


def _one_segment_segmentation(slicer, terminology=None, name="LiverResolveSeg"):
    """A one-segment segmentation, optionally SCT-tagged as liver."""
    import vtk

    source = vtk.vtkSphereSource()
    source.SetRadius(20.0)
    source.Update()
    modelNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", "ResolveModel")
    modelNode.SetAndObservePolyData(source.GetOutput())
    seg = slicer.mrmlScene.AddNewNodeByClass(SEGMENTATION_CLASS, name)
    seg.CreateDefaultDisplayNodes()
    slicer.modules.segmentations.logic().ImportModelToSegmentationNode(modelNode, seg)
    slicer.mrmlScene.RemoveNode(modelNode)
    if terminology is not None:
        segId = seg.GetSegmentation().GetNthSegmentID(0)
        seg.GetSegmentation().GetSegment(segId).SetTag("TerminologyEntry", terminology)
    return seg


def test_liver_segment_resolves_by_sct_tag():
    """``GetLiverSegmentId`` resolves the liver segment by its SCT tag.

    The territory-map compute finds the liver region by the SNOMED-CT liver
    code (ADR-0011), not the segment name.  A tagged segment resolves to a
    non-empty id.  [launched.]
    """
    slicer = _slicer_or_skip()
    logic = _logic_or_skip(slicer)
    cpp = _cpp_logic_or_skip(logic)
    seg = _one_segment_segmentation(slicer, terminology=_LIVER_TERMINOLOGY)

    segId = cpp.GetLiverSegmentId(seg)

    assert segId, (
        "an SCT^10200004-tagged segment must resolve to a non-empty segment id "
        "(ADR-0011)."
    )
    assert seg.GetSegmentation().GetSegment(segId) is not None


def test_liver_segment_unresolved_is_empty_not_a_guess():
    """``GetLiverSegmentId`` returns '' when no liver-tagged segment exists.

    An untagged segmentation must resolve to the empty string (the map compute
    then fails legibly rather than exporting an empty labelmap for an empty
    segment id).  [launched.]
    """
    slicer = _slicer_or_skip()
    logic = _logic_or_skip(slicer)
    cpp = _cpp_logic_or_skip(logic)
    seg = _one_segment_segmentation(slicer, terminology=None)

    assert cpp.GetLiverSegmentId(seg) == "", (
        "an untagged segmentation must resolve to the empty string, not a "
        "guessed segment id (ADR-0011)."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""ADR-0037 Stage-1 — the annotation-point carrier + its storage round-trip.

ADR-0037 transitions VascularTerritories off Slicer markups onto the v2
architecture (the same way ADR-0014 dissolved the resection markups
assembly).  The ordered, surface-snapped annotation points that seeded
VMTK centerline extraction move OFF ``vtkMRMLMarkupsFiducialNode`` ONTO
the existing ``vtkMRMLCustomTerritoriesNode`` — its never-implemented
``EndpointRefs`` markups slot (see the class header) is REPLACED by an
own point carrier, per territory, with a storage-node round-trip
mirroring ``vtkMRMLResectionPlanStorageNode``.  No markups reference
anywhere on the annotation path (ADR-0037 §Decision 1 + §Conformance
[test], ADR-0014 §"Fourth layer").

This file pins the Stage-1 increments and the Stage-2 display-attribute
increment on the SAME carrier:

* i1 — CARRIER STORAGE.  Ordered per-territory annotation points on the
  C++ ``vtkMRMLCustomTerritoriesNode``: add / get-Nth / count / clear;
  grouping BY TERRITORY id; ``Modified`` semantics on mutation; and the
  ABSENCE of any markups-fiducial reference role added by this path.
* i2 — STORAGE ROUND-TRIP.  Writing the carrier's points to a storage
  node and reading them back yields identical ORDERED points per
  territory (mirrors ``vtkMRMLResectionPlanStorageNodeTest1``).
* i5 (Stage 2) — DISPLAY-ATTRIBUTE SLOT.  ADR-0037 §Decision 3 / §3
  table: the table row carries per-territory colour (RGB), display
  label, and visibility.  Stage 2 ADDS these as a per-territoryId slot
  on the SAME carrier, mirroring the ``AnnotationPoints``
  ``std::map<std::string, ...>`` idiom, with XML + ``.vta.json``
  round-trip.  These invariants pin that setting a display attribute
  does NOT alter ``GetNumberOfAnnotationPoints`` or any point coord (the
  display slot and the geometry slot are independent), and that the
  attributes round-trip through storage.

-- SEAM THE IMPLEMENTER MUST PROVIDE (proposed; sharpen at landing) --

The carrier API on ``vtkMRMLCustomTerritoriesNode`` (C++), sharpened
against the header's existing ``SetGrouping``/``GetGrouping`` /
``GetNumberOfGroupings`` / ``ClearGroupings`` std::string-keyed idiom and
the resection carrier's grid-vector accessor idiom:

  * ``AddAnnotationPoint(territoryId: str, x, y, z) -> int`` — appends a
    point to territory ``territoryId``'s ordered list; returns its index
    within that territory.  Fires ONE ``ModifiedEvent``.
  * ``GetNumberOfAnnotationPoints(territoryId: str) -> int`` — count in
    that territory (0 for an unknown territory).
  * ``GetNthAnnotationPoint(territoryId: str, i: int) -> (x, y, z)`` — the
    i-th point in placement order (wrapped as a 3-tuple / double[3]).
  * ``ClearAnnotationPoints(territoryId: str)`` — empties that
    territory's list only; fires ONE ``ModifiedEvent``.

The Auto/Couinaud path (``vtkMRMLStdCouinaudTerritoriesNode``) carries
NO annotation points and is OUT of scope (ADR-0037 §Decision 1).

-- WHY LAUNCHED-SLICER (both increments) --

``vtkMRMLCustomTerritoriesNode`` is a WRAPPED C++ node; its Python
wrapper resolves only inside a launched Slicer with the module loaded
(``slicer.mrmlScene.AddNewNodeByClass`` after the module Logic's
``RegisterNodes``).  A bare ``PythonSlicer -m pytest`` has
``slicer.mrmlScene is None`` and the wrapped class off the path, so
every test here SKIPS CLEANLY via the shared ``slicer_pytest_support``
guards.  The storage round-trip additionally needs the (not-yet-existing)
storage node, so i2 skip-pends on that class's absence (ADR-0027).

-- RUN-VS-SKIP DISCIPLINE (ADR-0027) --

Pre-implementation the carrier API + storage node do not exist, so the
``hasattr`` / ``AddNewNodeByClass``-returns-None guards skip-pend; the
skips lift at the implementation commit.  Under a launched Slicer,
verify run-vs-skip in the CI log once the seam lands — never trust
overall green (the launched harness is green-but-skipping prone).

See also:
  * Docs/adr/0037-vascular-territories-off-markups.md  (the decision)
  * Docs/adr/0014-livermarkups-dissolution.md §"Fourth layer"
  * Docs/adr/0027-invariant-test-first.md  (RED / skip-pending discipline)
  * VascularTerritories/MRML/vtkMRMLCustomTerritoriesNode.h  (the wrapper)
  * LiverResections/MRML/Testing/Cxx/vtkMRMLResectionPlanStorageNodeTest1.cxx
  * VascularTerritories/Testing/Python/conftest.py  (the cleanup fixtures)
"""

from __future__ import annotations

import pytest

CUSTOM_TERRITORIES_CLASS = "vtkMRMLCustomTerritoriesNode"
STORAGE_NODE_CLASS = "vtkMRMLCustomTerritoriesStorageNode"

# The carrier API seam ADR-0037 Stage-1 lands.  Tests skip-pending on
# absence (ADR-0027); the skip lifts at the implementation commit.
ADD_POINT_METHOD = "AddAnnotationPoint"
COUNT_METHOD = "GetNumberOfAnnotationPoints"
GET_NTH_METHOD = "GetNthAnnotationPoint"
CLEAR_METHOD = "ClearAnnotationPoints"

# The per-territory DISPLAY-ATTRIBUTE slot ADR-0037 Stage-2 adds to the
# carrier (colour / label / visibility), mirroring the AnnotationPoints
# std::map idiom.  Tests skip-pending on absence (ADR-0027); the skip
# lifts at the Stage-2 implementation commit.  Method names are PROPOSED;
# sharpen at landing against the header's std::string-keyed idiom.
SET_COLOR_METHOD = "SetTerritoryColor"
GET_COLOR_METHOD = "GetTerritoryColor"
SET_LABEL_METHOD = "SetTerritoryLabel"
GET_LABEL_METHOD = "GetTerritoryLabel"
SET_VISIBILITY_METHOD = "SetTerritoryVisibility"
GET_VISIBILITY_METHOD = "GetTerritoryVisibility"

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


def _make_custom_territories_or_skip(slicer, name="AnnotationCarrierTest"):
    """Mint a ``vtkMRMLCustomTerritoriesNode`` or skip cleanly.

    Skips when the node class is not registered (module Logic
    ``RegisterNodes`` not in this build) and skip-PENDS when the
    annotation-carrier API has not landed yet (ADR-0027).
    """
    node = slicer.mrmlScene.AddNewNodeByClass(CUSTOM_TERRITORIES_CLASS, name)
    if node is None:
        pytest.skip(
            f"{CUSTOM_TERRITORIES_CLASS} not registered -- the module Logic "
            "RegisterNodes() must wire this up (launched build)."
        )
    for method in (ADD_POINT_METHOD, COUNT_METHOD, GET_NTH_METHOD, CLEAR_METHOD):
        if not hasattr(node, method):
            pytest.skip(
                f"{CUSTOM_TERRITORIES_CLASS} has no {method} -- the ADR-0037 "
                "annotation-point carrier (Stage-1 i1) has not landed.  The "
                "skip lifts at the implementation commit (ADR-0027)."
            )
    return node


def _nth(node, territory, i):
    """Return the i-th annotation point of ``territory`` as an (x, y, z) tuple."""
    p = node.GetNthAnnotationPoint(territory, i)
    return (p[0], p[1], p[2])


# --------------------------------------------------------------------------- #
# i1 — carrier storage (launched)
# --------------------------------------------------------------------------- #


def test_add_appends_ordered_points_within_a_territory():
    """i1: add / get-Nth / count preserve PLACEMENT ORDER within a territory.

    Three points added to one territory come back in the order placed,
    each at its exact world position (ADR-0037 §Decision 1 "ordered,
    surface-snapped annotation points").
    """
    slicer = _slicer_or_skip()
    node = _make_custom_territories_or_skip(slicer)

    pts = [(10.0, 20.0, 30.0), (-5.0, 40.0, 15.0), (1.0, 2.0, 3.0)]
    for expected_index, (x, y, z) in enumerate(pts):
        idx = node.AddAnnotationPoint(TERRITORY_A, x, y, z)
        assert idx == expected_index, (
            f"AddAnnotationPoint must return the in-territory index; expected "
            f"{expected_index}, got {idx!r}."
        )

    assert node.GetNumberOfAnnotationPoints(TERRITORY_A) == len(pts)
    for i, expected in enumerate(pts):
        assert _nth(node, TERRITORY_A, i) == pytest.approx(expected, abs=1e-6), (
            f"point {i} must round-trip its world position in placement order."
        )


def test_points_are_grouped_by_territory_id():
    """i1: two territories keep INDEPENDENT ordered lists.

    Points added under territory A must not leak into territory B, and
    each territory's count + ordering is independent (ADR-0037 §Decision
    1 "per territory").
    """
    slicer = _slicer_or_skip()
    node = _make_custom_territories_or_skip(slicer)

    a_pts = [(1.0, 0.0, 0.0), (2.0, 0.0, 0.0)]
    b_pts = [(0.0, 1.0, 0.0), (0.0, 2.0, 0.0), (0.0, 3.0, 0.0)]
    for x, y, z in a_pts:
        node.AddAnnotationPoint(TERRITORY_A, x, y, z)
    for x, y, z in b_pts:
        node.AddAnnotationPoint(TERRITORY_B, x, y, z)

    assert node.GetNumberOfAnnotationPoints(TERRITORY_A) == len(a_pts)
    assert node.GetNumberOfAnnotationPoints(TERRITORY_B) == len(b_pts)
    for i, expected in enumerate(a_pts):
        assert _nth(node, TERRITORY_A, i) == pytest.approx(expected, abs=1e-6)
    for i, expected in enumerate(b_pts):
        assert _nth(node, TERRITORY_B, i) == pytest.approx(expected, abs=1e-6)


def test_clear_empties_only_the_named_territory():
    """i1: clear affects the named territory ONLY, leaving siblings intact."""
    slicer = _slicer_or_skip()
    node = _make_custom_territories_or_skip(slicer)

    node.AddAnnotationPoint(TERRITORY_A, 1.0, 0.0, 0.0)
    node.AddAnnotationPoint(TERRITORY_A, 2.0, 0.0, 0.0)
    node.AddAnnotationPoint(TERRITORY_B, 0.0, 1.0, 0.0)

    node.ClearAnnotationPoints(TERRITORY_A)

    assert node.GetNumberOfAnnotationPoints(TERRITORY_A) == 0, (
        "ClearAnnotationPoints must empty the named territory."
    )
    assert node.GetNumberOfAnnotationPoints(TERRITORY_B) == 1, (
        "ClearAnnotationPoints must NOT touch a sibling territory."
    )


def test_unknown_territory_reports_zero_points():
    """i1: an un-added territory id reports 0 points (no throw)."""
    slicer = _slicer_or_skip()
    node = _make_custom_territories_or_skip(slicer)

    assert node.GetNumberOfAnnotationPoints("NeverAdded") == 0


def test_add_fires_exactly_one_modified():
    """i1: each mutation fires exactly ONE ModifiedEvent.

    Downstream consumers (the table UI, the placement Pipeline's
    reconcile) observe the carrier's ``ModifiedEvent``; a single add must
    fire exactly once so the observers do not over-render (the
    drag-latency lesson from the resection carrier).
    """
    import vtk

    slicer = _slicer_or_skip()
    node = _make_custom_territories_or_skip(slicer)

    events = []
    tag = node.AddObserver(vtk.vtkCommand.ModifiedEvent, lambda c, e: events.append(1))
    try:
        node.AddAnnotationPoint(TERRITORY_A, 1.0, 2.0, 3.0)
    finally:
        node.RemoveObserver(tag)

    assert len(events) == 1, (
        f"AddAnnotationPoint must fire exactly ONE ModifiedEvent; got {len(events)}."
    )


def test_clear_fires_exactly_one_modified():
    """i1: clear fires exactly ONE ModifiedEvent for a non-empty territory."""
    import vtk

    slicer = _slicer_or_skip()
    node = _make_custom_territories_or_skip(slicer)

    node.AddAnnotationPoint(TERRITORY_A, 1.0, 2.0, 3.0)
    node.AddAnnotationPoint(TERRITORY_A, 4.0, 5.0, 6.0)

    events = []
    tag = node.AddObserver(vtk.vtkCommand.ModifiedEvent, lambda c, e: events.append(1))
    try:
        node.ClearAnnotationPoints(TERRITORY_A)
    finally:
        node.RemoveObserver(tag)

    assert len(events) == 1, (
        f"ClearAnnotationPoints must fire exactly ONE ModifiedEvent; got {len(events)}."
    )


def test_no_markups_fiducial_reference_role_on_the_carrier():
    """i1: the annotation path adds NO markups-fiducial node reference.

    ADR-0037 §Decision 1 + §Conformance [review]: "no markups reference
    anywhere" — the carrier replaces the never-implemented ``EndpointRefs``
    markups slot with its OWN point carrier.  This has a credible creep-in
    path (a fallback wire-up back to a fiducial node), so pin its absence
    (per the no-colour-of-the-sky discipline: this is a real regression
    surface, not an arbitrary absence).

    After placing several points, NO node reference on the carrier may
    resolve to a ``vtkMRMLMarkupsFiducialNode``.
    """
    slicer = _slicer_or_skip()
    node = _make_custom_territories_or_skip(slicer)

    node.AddAnnotationPoint(TERRITORY_A, 1.0, 2.0, 3.0)
    node.AddAnnotationPoint(TERRITORY_B, 4.0, 5.0, 6.0)

    for role_index in range(node.GetNumberOfNodeReferenceRoles()):
        role = node.GetNthNodeReferenceRole(role_index)
        for ref_index in range(node.GetNumberOfNodeReferences(role)):
            referenced = node.GetNthNodeReference(role, ref_index)
            assert referenced is None or not referenced.IsA(
                "vtkMRMLMarkupsFiducialNode"
            ), (
                f"the annotation carrier must hold NO markups-fiducial "
                f"reference (role {role!r} resolves one) -- ADR-0037 §Decision 1."
            )


# --------------------------------------------------------------------------- #
# i5 (Stage 2) — per-territory display-attribute slot (launched)
# --------------------------------------------------------------------------- #


def _make_carrier_with_display_or_skip(slicer, name="DisplayAttrCarrierTest"):
    """Mint a carrier exposing the Stage-2 display-attribute slot, or skip-pend.

    Extends ``_make_custom_territories_or_skip`` with the per-territory
    colour / label / visibility accessors ADR-0037 Stage-2 adds; skip-pends
    (ADR-0027) when those accessors have not landed.
    """
    node = _make_custom_territories_or_skip(slicer, name)
    for method in (
        SET_COLOR_METHOD,
        GET_COLOR_METHOD,
        SET_LABEL_METHOD,
        GET_LABEL_METHOD,
        SET_VISIBILITY_METHOD,
        GET_VISIBILITY_METHOD,
    ):
        if not hasattr(node, method):
            pytest.skip(
                f"{CUSTOM_TERRITORIES_CLASS} has no {method} -- the ADR-0037 "
                "Stage-2 per-territory display-attribute slot (§Decision 3 / "
                "§3 table) has not landed.  The skip lifts at the Stage-2 "
                "implementation commit (ADR-0027)."
            )
    return node


def test_display_attributes_store_and_read_back_per_territory():
    """i5: colour / label / visibility store + read back, keyed per territory.

    ADR-0037 §Decision 3 / §3 table: the header row carries a per-territory
    colour swatch, display label, and visibility.  Two territories keep
    INDEPENDENT display attributes (same std::map-keyed idiom as the point
    carrier).
    """
    slicer = _slicer_or_skip()
    node = _make_carrier_with_display_or_skip(slicer)

    node.SetTerritoryColor(TERRITORY_A, 1.0, 0.0, 0.0)
    node.SetTerritoryLabel(TERRITORY_A, "Right anterior")
    node.SetTerritoryVisibility(TERRITORY_A, True)

    node.SetTerritoryColor(TERRITORY_B, 0.0, 0.0, 1.0)
    node.SetTerritoryLabel(TERRITORY_B, "Left lateral")
    node.SetTerritoryVisibility(TERRITORY_B, False)

    color_a = node.GetTerritoryColor(TERRITORY_A)
    assert (color_a[0], color_a[1], color_a[2]) == pytest.approx((1.0, 0.0, 0.0), abs=1e-6)
    assert node.GetTerritoryLabel(TERRITORY_A) == "Right anterior"
    assert bool(node.GetTerritoryVisibility(TERRITORY_A)) is True

    color_b = node.GetTerritoryColor(TERRITORY_B)
    assert (color_b[0], color_b[1], color_b[2]) == pytest.approx((0.0, 0.0, 1.0), abs=1e-6)
    assert node.GetTerritoryLabel(TERRITORY_B) == "Left lateral"
    assert bool(node.GetTerritoryVisibility(TERRITORY_B)) is False


def test_setting_a_display_attribute_does_not_touch_geometry():
    """i5: a display-attribute write leaves point count + coords byte-identical.

    ADR-0037 §Decision 3: the display slot and the geometry slot are
    INDEPENDENT.  A colour / label / visibility edit is a "display slot
    without touching geometry" write — no point added / moved / dropped
    (the same invariant pinned launched by the table's colour/label/vis
    edit test in ``test_territories_table.py``, pinned here at the carrier).
    """
    slicer = _slicer_or_skip()
    node = _make_carrier_with_display_or_skip(slicer)

    pts = [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)]
    for x, y, z in pts:
        node.AddAnnotationPoint(TERRITORY_A, x, y, z)

    before_count = node.GetNumberOfAnnotationPoints(TERRITORY_A)
    before = [_nth(node, TERRITORY_A, i) for i in range(before_count)]

    node.SetTerritoryColor(TERRITORY_A, 0.2, 0.4, 0.6)
    node.SetTerritoryLabel(TERRITORY_A, "Renamed")
    node.SetTerritoryVisibility(TERRITORY_A, False)

    assert node.GetNumberOfAnnotationPoints(TERRITORY_A) == before_count, (
        "a display-attribute write must NOT change the annotation-point count."
    )
    for i, expected in enumerate(before):
        assert _nth(node, TERRITORY_A, i) == pytest.approx(expected, abs=1e-9), (
            f"point {i} must not move on a display-attribute write."
        )


# --------------------------------------------------------------------------- #
# i2 — storage round-trip (launched; needs scene + storage node)
# --------------------------------------------------------------------------- #


def _make_storage_or_skip(slicer):
    """Mint the annotation carrier's storage node or skip-pend (ADR-0027).

    Proposed seam: ``vtkMRMLCustomTerritoriesStorageNode`` mirroring
    ``vtkMRMLResectionPlanStorageNode`` (write the carrier's per-territory
    ordered points to disk + read them back).  Sharpen the class name at
    landing against the territories node family's naming.
    """
    storage = slicer.mrmlScene.AddNewNodeByClass(STORAGE_NODE_CLASS)
    if storage is None:
        pytest.skip(
            f"{STORAGE_NODE_CLASS} not registered -- the ADR-0037 annotation "
            "storage round-trip (Stage-1 i2) has not landed.  The skip lifts "
            "at the implementation commit (ADR-0027)."
        )
    return storage


def _temp_path(slicer, extension):
    """A unique temp file path under Slicer's temporary directory."""
    import os

    temp_dir = slicer.app.temporaryPath
    pid = os.getpid()
    _temp_path.counter = getattr(_temp_path, "counter", 0) + 1
    return os.path.join(
        temp_dir,
        f"territories_annotation_carrier_{pid}_{_temp_path.counter}.{extension}",
    )


def test_carrier_points_round_trip_through_storage():
    """i2: write the carrier's per-territory ordered points; read back identical.

    Mirrors ``vtkMRMLResectionPlanStorageNodeTest1`` (plan-rooted
    round-trip): a source carrier with two territories writes to a
    storage file; a fresh sink carrier reads it back with identical
    ORDERED points per territory (ADR-0037 §Decision 1 + §Conformance
    [test] "stores/round-trips ordered per-territory points").
    """
    import os

    slicer = _slicer_or_skip()
    source = _make_custom_territories_or_skip(slicer, "AnnotationSource")
    storage = _make_storage_or_skip(slicer)

    a_pts = [(1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (3.0, 0.0, 0.0)]
    b_pts = [(0.0, 1.0, 0.0), (0.0, 2.0, 0.0)]
    for x, y, z in a_pts:
        source.AddAnnotationPoint(TERRITORY_A, x, y, z)
    for x, y, z in b_pts:
        source.AddAnnotationPoint(TERRITORY_B, x, y, z)

    path = _temp_path(slicer, "json")
    storage.SetFileName(path)
    assert storage.WriteData(source) == 1, "storage WriteData must succeed."

    try:
        sink = _make_custom_territories_or_skip(slicer, "AnnotationSink")
        read_storage = _make_storage_or_skip(slicer)
        read_storage.SetFileName(path)
        assert read_storage.ReadData(sink) == 1, "storage ReadData must succeed."

        assert sink.GetNumberOfAnnotationPoints(TERRITORY_A) == len(a_pts)
        assert sink.GetNumberOfAnnotationPoints(TERRITORY_B) == len(b_pts)
        for i, expected in enumerate(a_pts):
            assert _nth(sink, TERRITORY_A, i) == pytest.approx(expected, abs=1e-6), (
                f"territory A point {i} must round-trip in placement order."
            )
        for i, expected in enumerate(b_pts):
            assert _nth(sink, TERRITORY_B, i) == pytest.approx(expected, abs=1e-6), (
                f"territory B point {i} must round-trip in placement order."
            )
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_display_attributes_round_trip_through_storage():
    """i5: colour / label / visibility survive a ``.vta.json`` write+read.

    ADR-0037 §Decision 3 adds the display slot "with XML + ``.vta.json``
    round-trip" — the same storage node that persists the ordered points
    also persists the per-territory colour, label, and visibility.  A
    source carrier's display attributes read back identically on a fresh
    sink carrier.
    """
    import os

    slicer = _slicer_or_skip()
    source = _make_carrier_with_display_or_skip(slicer, "DisplaySource")
    storage = _make_storage_or_skip(slicer)

    # At least one point so the territory is enumerable by the storage node.
    source.AddAnnotationPoint(TERRITORY_A, 1.0, 0.0, 0.0)
    source.SetTerritoryColor(TERRITORY_A, 0.1, 0.5, 0.9)
    source.SetTerritoryLabel(TERRITORY_A, "Segment VII")
    source.SetTerritoryVisibility(TERRITORY_A, False)

    path = _temp_path(slicer, "json")
    storage.SetFileName(path)
    assert storage.WriteData(source) == 1, "storage WriteData must succeed."

    try:
        sink = _make_carrier_with_display_or_skip(slicer, "DisplaySink")
        read_storage = _make_storage_or_skip(slicer)
        read_storage.SetFileName(path)
        assert read_storage.ReadData(sink) == 1, "storage ReadData must succeed."

        color = sink.GetTerritoryColor(TERRITORY_A)
        assert (color[0], color[1], color[2]) == pytest.approx((0.1, 0.5, 0.9), abs=1e-6)
        assert sink.GetTerritoryLabel(TERRITORY_A) == "Segment VII"
        assert bool(sink.GetTerritoryVisibility(TERRITORY_A)) is False
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_storage_can_write_custom_territories_only():
    """i2: the storage node accepts the custom-territories carrier; rejects others.

    Mirrors the ``CanRead`` / ``CanWrite`` discrimination pin in
    ``vtkMRMLResectionPlanStorageNodeTest1`` — the storage node is typed
    to the annotation carrier and must reject an unrelated node (e.g. the
    Auto/Couinaud node, which carries no annotation points per ADR-0037
    §Decision 1).
    """
    slicer = _slicer_or_skip()
    carrier = _make_custom_territories_or_skip(slicer)
    storage = _make_storage_or_skip(slicer)

    assert storage.CanWriteFromReferenceNode(carrier) is True, (
        "the storage node must accept the custom-territories carrier."
    )

    couinaud = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLStdCouinaudTerritoriesNode")
    if couinaud is not None:
        assert storage.CanWriteFromReferenceNode(couinaud) is False, (
            "the Auto/Couinaud node carries no annotation points and must be "
            "rejected by the annotation storage node (ADR-0037 §Decision 1)."
        )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

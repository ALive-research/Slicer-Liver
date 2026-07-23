# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""ADR-0037 slice 5 (REVISED) — the seed->structure mapping (pure-VTK).

The revised multi-system design (Docs/design/multi-system-territory-plan.md,
§Part B B1 / B3) assigns each of a territory's seeds to the input SEGMENT
(structure) whose CLOSED SURFACE the seed is nearest — portal, hepatic, ...  A
territory may own seeds across MULTIPLE disjoint structures; the mapping is what
lets extraction group by structure (§B4) and the table colour each seed row by
its structure (§B3).

The geometry (nearest closed surface to a point) is PURE polydata -> Python
(ADR-0004 split); the segment->closed-surface + segment->colour resolution
reads MRML and rides existing seams, pinned launched in
``test_territories_surface_resolution`` (T1d) + ``test_territories_table``.
This file is the BARE invariant for the pure core: it RUNS bare once
``VascularTerritoriesLib/SeedStructureMapping.py`` lands.

* m1 (BARE) — NEAREST STRUCTURE.  Given an ordered ``[(key, surface), ...]`` of
  two DISJOINT sphere structures, a point on structure A's surface maps to A's
  key; a point on B's maps to B's; a point clearly inside/near A maps to A.
* m2 (BARE) — DETERMINISTIC TIEBREAK.  A point EQUIDISTANT to two structures
  (the midpoint between two symmetric spheres) maps to the FIRST structure in
  order — deterministic, order-driven (Q3).  Swapping the order flips the
  result, proving the tiebreak is first-in-order, not geometry-lucky.
* m3 (BARE) — EMPTY / DEGENERATE.  An empty structure list maps to ``None`` (no
  structure to assign); a single-structure list maps every point to that one
  key.
* m4 (BARE) — PER-STRUCTURE SEED COUNTS + THE <2 WARNING GATE.  Given already-
  mapped ``[(seed, structureKey), ...]`` pairs, ``territory_structure_seed_counts``
  groups them into ``{structureKey: count}``; a territory with 2 seeds on A + 1
  on B has a structure (B) with <2 seeds (the warning case, §B3 / §B6), while
  2 on A + 2 on B has none.  This is the SAME gate the extractor uses (§B4) so
  the table warning and the extraction skip agree.

-- SEAM THE IMPLEMENTER MUST PROVIDE (proposed; sharpen at landing) --

A pure-VTK helper module ``VascularTerritoriesLib.SeedStructureMapping`` with:

  * ``nearest_structure(structures, point) -> key | None`` — ``structures`` is
    an ORDERED sequence of ``(key, closed_surface_polydata)`` (``key`` = the
    segment id str); builds a ``vtkCellLocator`` (``FindClosestPoint``) per
    surface and returns the key of the nearest structure to ``point``.  A
    distance tie resolves to the FIRST structure in order (deterministic, Q3).
    ``point`` is a 3-tuple of world floats.  Empty ``structures`` -> ``None``.
  * ``territory_structure_seed_counts(assignments) -> dict[key, int]`` where
    ``assignments`` is a sequence of ``(seed, structureKey)`` pairs (or just
    ``structureKey`` values); returns ``{structureKey: count}``.  Reused by the
    table warning (§B3) and the extractor's ≥2-per-structure gate (§B4) so the
    two agree on which structures are under-seeded.

If the implementer names these differently, update the constants below — the
invariants are nearest-surface assignment + first-in-order tiebreak + the
per-structure count grouping, not the specific spelling.

-- RUN-VS-SKIP DISCIPLINE (ADR-0027) --

Pre-implementation ``SeedStructureMapping`` does not exist, so every test
import-guards and SKIP-PENDINGs cleanly bare; the skips lift at the
implementation commit, at which point m1-m4 RUN bare (pure VTK, no launched
Slicer).

See also:
  * Docs/design/multi-system-territory-plan.md  (§Part B B1/B3/B4)
  * Docs/adr/0037-vascular-territories-off-markups.md
    (§Amendment — connected-tree-constrained centerline seeding (slice 5))
  * Docs/adr/0004-python-cpp-boundary.md  (pure polydata -> Python)
  * Docs/adr/0027-invariant-test-first.md  (RED / skip-pending discipline)
  * VascularTerritories/VascularTerritoriesLib/VesselConnectivity.py  (the
    pure-VTK connectivity sibling)
  * VascularTerritories/Testing/Python/test_territories_surface_resolution.py
    (the launched per-segment closed-surface split, T1d)
  * VascularTerritories/Testing/Python/test_territories_vmtk_feed.py
    (the launched group-by-structure extraction twin)
"""

from __future__ import annotations

import importlib

import pytest

vtk = pytest.importorskip("vtk")

# The pure-VTK seed->structure mapping seam (proposed; sharpen at landing).
MAPPING_MODULE = "VascularTerritoriesLib.SeedStructureMapping"
NEAREST_STRUCTURE_FUNC = "nearest_structure"
STRUCTURE_SEED_COUNTS_FUNC = "territory_structure_seed_counts"

# Two well-separated sphere centres so their meshes never share a point.
CENTER_A = (0.0, 0.0, 0.0)
CENTER_B = (100.0, 0.0, 0.0)
RADIUS = 10.0

# Structure keys stand in for real segment ids (str, per GetVascularSegmentIds).
KEY_A = "Segment_Portal"
KEY_B = "Segment_Hepatic"


# --------------------------------------------------------------------------- #
# Skip-guards (import-guard on the not-yet-existing pure helper; ADR-0027)
# --------------------------------------------------------------------------- #


def _mapping_module_or_skip():
    try:
        return importlib.import_module(MAPPING_MODULE)
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"{MAPPING_MODULE} not importable ({exc!r}) -- the revised ADR-0037 "
            "slice-5 seed->structure mapping helper has not landed.  The skip "
            "lifts at the implementation commit (ADR-0027)."
        )


def _nearest_structure_or_skip():
    module = _mapping_module_or_skip()
    func = getattr(module, NEAREST_STRUCTURE_FUNC, None)
    if func is None:
        pytest.skip(
            f"{MAPPING_MODULE} has no {NEAREST_STRUCTURE_FUNC} -- the revised "
            "ADR-0037 slice-5 seed->structure mapping helper has not landed "
            "(ADR-0027)."
        )
    return func


def _structure_seed_counts_or_skip():
    module = _mapping_module_or_skip()
    func = getattr(module, STRUCTURE_SEED_COUNTS_FUNC, None)
    if func is None:
        pytest.skip(
            f"{MAPPING_MODULE} has no {STRUCTURE_SEED_COUNTS_FUNC} -- the revised "
            "ADR-0037 slice-5 per-structure seed-count query has not landed "
            "(ADR-0027)."
        )
    return func


# --------------------------------------------------------------------------- #
# Pure-VTK fixtures (no Slicer, no MRML, no GL)
# --------------------------------------------------------------------------- #


def _sphere(center, radius=RADIUS):
    source = vtk.vtkSphereSource()
    source.SetCenter(*center)
    source.SetRadius(radius)
    source.SetThetaResolution(16)
    source.SetPhiResolution(16)
    source.Update()
    return source.GetOutput()


def _two_structures():
    """An ordered ``[(KEY_A, sphere_A), (KEY_B, sphere_B)]`` structure list."""
    return [(KEY_A, _sphere(CENTER_A)), (KEY_B, _sphere(CENTER_B))]


def _surface_point_on(sphere_polydata):
    """A genuine surface point on ``sphere_polydata`` (its first mesh point)."""
    return tuple(sphere_polydata.GetPoint(0))


# =========================================================================== #
# m1 — nearest structure (BARE)
# =========================================================================== #


def test_point_on_structure_a_maps_to_a():
    """m1: a point on structure A's surface maps to A's key.

    The seed lands on the portal surface; the mapping assigns it the portal
    segment id (revised ADR-0037 slice 5; multi-system plan §B1).  Pure VTK —
    RUNS bare.
    """
    nearest_structure = _nearest_structure_or_skip()
    structures = _two_structures()
    seed_on_a = _surface_point_on(structures[0][1])

    assert nearest_structure(structures, seed_on_a) == KEY_A, (
        "a seed on structure A's surface must map to A's key "
        "(seed->structure mapping, §B1)."
    )


def test_point_on_structure_b_maps_to_b():
    """m1: a point on structure B's surface maps to B's key.

    The mirror of the A case — the mapping is nearest-surface, not fixed to the
    first structure — so a seed on the hepatic surface maps to hepatic.  Pure
    VTK — RUNS bare.
    """
    nearest_structure = _nearest_structure_or_skip()
    structures = _two_structures()
    seed_on_b = _surface_point_on(structures[1][1])

    assert nearest_structure(structures, seed_on_b) == KEY_B, (
        "a seed on structure B's surface must map to B's key (§B1)."
    )


def test_point_near_a_centre_maps_to_a():
    """m1: a point deep inside/near A maps to A regardless of B's presence.

    A point at A's centre is far closer to A's surface than to B's, so it maps
    to A — a sanity check that the nearest-surface distance drives the
    assignment (§B1).  Pure VTK — RUNS bare.
    """
    nearest_structure = _nearest_structure_or_skip()
    structures = _two_structures()

    assert nearest_structure(structures, CENTER_A) == KEY_A
    assert nearest_structure(structures, CENTER_B) == KEY_B


# =========================================================================== #
# m2 — deterministic first-in-order tiebreak (BARE, Q3)
# =========================================================================== #


def test_boundary_point_tiebreaks_to_first_in_order():
    """m2: a point equidistant to two structures maps to the FIRST in order.

    A seed at the midpoint between two symmetric spheres is equidistant to both
    surfaces; the mapping resolves the tie to the FIRST structure in the ordered
    list (deterministic, Q3).  Swapping the structure order flips the result —
    proving the tiebreak is first-in-order, not a geometry accident.  Pure VTK —
    RUNS bare.
    """
    nearest_structure = _nearest_structure_or_skip()
    structures = _two_structures()
    midpoint = tuple((CENTER_A[k] + CENTER_B[k]) / 2.0 for k in range(3))

    first_a = nearest_structure(structures, midpoint)
    first_b = nearest_structure(list(reversed(structures)), midpoint)

    assert first_a == KEY_A, (
        "an equidistant boundary point must tiebreak to the FIRST structure in "
        f"order (KEY_A); got {first_a!r} (revised ADR-0037 slice 5, Q3)."
    )
    assert first_b == KEY_B, (
        "reversing the order must flip the tiebreak to the new first structure "
        f"(KEY_B); got {first_b!r} -- the tiebreak is first-in-order, not "
        "geometry-lucky (Q3)."
    )


# =========================================================================== #
# m3 — empty / single-structure degenerate cases (BARE)
# =========================================================================== #


def test_empty_structure_list_maps_to_none():
    """m3: no structures -> the mapping returns None (nothing to assign)."""
    nearest_structure = _nearest_structure_or_skip()
    assert nearest_structure([], CENTER_A) is None, (
        "an empty structure list must map to None -- there is no structure to "
        "assign the seed to (§B1)."
    )


def test_single_structure_maps_every_point_to_it():
    """m3: one structure -> every point maps to its key."""
    nearest_structure = _nearest_structure_or_skip()
    structures = [(KEY_A, _sphere(CENTER_A))]
    assert nearest_structure(structures, CENTER_A) == KEY_A
    # A far-away point still maps to the only structure available.
    assert nearest_structure(structures, CENTER_B) == KEY_A, (
        "with a single structure, even a distant seed maps to that one key (§B1)."
    )


# =========================================================================== #
# m4 — per-structure seed counts + the <2 warning gate (BARE)
# =========================================================================== #


def test_structure_seed_counts_group_by_structure():
    """m4: the counts query groups mapped seeds by structure key.

    Given already-mapped ``(seed, structureKey)`` pairs, the query returns
    ``{structureKey: count}`` — the grouping both the extractor's ≥2-per-
    structure gate (§B4) and the table warning (§B3 / §B6) read, so they agree.
    Pure — RUNS bare.
    """
    counts = _structure_seed_counts_or_skip()
    assignments = [
        ((0.0, 0.0, 0.0), KEY_A),
        ((1.0, 0.0, 0.0), KEY_A),
        ((0.0, 1.0, 0.0), KEY_B),
    ]

    grouped = counts(assignments)

    assert dict(grouped) == {KEY_A: 2, KEY_B: 1}, (
        "the per-structure seed counts must group the mapped seeds by structure "
        f"key (expected {{{KEY_A!r}: 2, {KEY_B!r}: 1}}, got {dict(grouped)}) "
        "(§B3/§B4)."
    )


def test_two_plus_one_flags_an_under_seeded_structure():
    """m4: 2 seeds on A + 1 on B leaves B under the ≥2 gate (the warning case).

    A territory with 2 seeds on structure A and 1 on structure B has a touched
    structure (B) with <2 seeds — B cannot yield a centerline, so the territory
    is flagged (§B6) and B is skipped by extraction (§B4).  Pure — RUNS bare.
    """
    counts = _structure_seed_counts_or_skip()
    grouped = counts(
        [
            ((0.0, 0.0, 0.0), KEY_A),
            ((1.0, 0.0, 0.0), KEY_A),
            ((0.0, 1.0, 0.0), KEY_B),
        ]
    )

    under_seeded = [k for k, n in dict(grouped).items() if n < 2]
    assert under_seeded == [KEY_B], (
        "a 2-on-A + 1-on-B territory must flag structure B as under-seeded "
        f"(<2 seeds); got under-seeded {under_seeded} (§B4/§B6)."
    )


def test_two_plus_two_has_no_under_seeded_structure():
    """m4: 2 seeds on A + 2 on B -> every touched structure clears the ≥2 gate.

    A territory evenly seeded across two structures has NO under-seeded
    structure, so it is complete and BOTH structures yield a centerline (§B4 /
    §B5 the mixed-system-two-centerlines case).  Pure — RUNS bare.
    """
    counts = _structure_seed_counts_or_skip()
    grouped = counts(
        [
            ((0.0, 0.0, 0.0), KEY_A),
            ((1.0, 0.0, 0.0), KEY_A),
            ((0.0, 1.0, 0.0), KEY_B),
            ((0.0, 2.0, 0.0), KEY_B),
        ]
    )

    under_seeded = [k for k, n in dict(grouped).items() if n < 2]
    assert under_seeded == [], (
        "a 2-on-A + 2-on-B territory must have NO under-seeded structure -- both "
        f"structures clear the >=2 gate; got under-seeded {under_seeded} "
        "(§B4/§B5)."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

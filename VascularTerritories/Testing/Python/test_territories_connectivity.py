# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""ADR-0037 slice 5 (REVISED) — the per-structure connected-component narrow.

The compute amendment resolved the VMTK input surface by MERGING every
segment; real liver data (parenchyma + portal + hepatic + tumour, one node)
makes merge-all wrong — portal and hepatic veins are DISJOINT connected
components and a medial path tunnelling between them is meaningless.

The REVISED slice-5 design (Docs/design/multi-system-territory-plan.md, §Part A
A3 / Q2) drops the single-active-tree LOCK: a territory may own seeds across
MULTIPLE disjoint structures, and extraction GROUPS by structure and runs VMTK
once per ≥2-seed structure.  ``connected_component_at`` SURVIVES the revision
for a different job — narrowing each PER-STRUCTURE surface to the connected
component of that structure's own seed, so a single input segment that
accidentally carries two DISJOINT tubes still feeds VMTK one coherent tree
(the "structure with disjoint pieces" edge case).  The retired job was the
single-tree lock + its "reuse AnnotationPoints[0]" persistence; that test is
REMOVED (the lock is gone).

The connectivity recovery is a PURE-VTK helper (no MRML scene, no Slicer, no
Qt, no GL): given a surface ``vtkPolyData`` + a seed point, return the single
connected component containing that point (``vtkPolyDataConnectivityFilter`` in
``ClosestPointRegion`` mode).  The plan puts the SCT filter + seed->structure
mapping in the MRML-facing layer (reads segment tags/colours — pinned launched
in ``test_territories_surface_resolution`` + ``test_territories_seed_structure``)
and the connectivity in Python (pure polydata) — a clean ADR-0004 split.  This
file is the core BARE invariant: it RUNS bare once
``VascularTerritoriesLib/VesselConnectivity.py`` lands.

* T2 (BARE) — connectivity picks ONE component.  A polydata of two DISJOINT
  spheres (``vtkAppendPolyData`` of two ``vtkSphereSource`` at separated
  centres); a seed on sphere A returns a component matching sphere A's point
  count / bounds and holding ZERO points from sphere B; a seed on sphere B
  returns B.  The recovered component is a SINGLE connected region
  (``vtkPolyDataConnectivityFilter`` in ``AllRegions`` mode reports exactly 1).
* T3 (BARE) — the PER-STRUCTURE narrow: a segment surface carrying two disjoint
  pieces narrows to the SINGLE piece the structure's seed lands on (the A3/Q2
  edge case), so VMTK never tunnels between the two pieces of one segment.

Red->green (ADR-0027): every test import-guards on the ``VesselConnectivity``
helper and SKIP-PENDINGs cleanly bare until it lands; the skips lift at the
implementation commit, at which point T2/T3 RUN bare (pure VTK, no launched
Slicer needed).

-- SEAM THE IMPLEMENTER MUST PROVIDE (proposed; sharpen at landing) --

A pure-VTK helper module ``VascularTerritoriesLib.VesselConnectivity`` with:

  * ``connected_component_at(polydata, seed) -> vtkPolyData`` — run
    ``vtkPolyDataConnectivityFilter`` with
    ``SetExtractionModeToClosestPointRegion()`` +
    ``SetClosestPoint(seed)`` and return the single connected component
    containing ``seed``.  Pure polydata in / out; no MRML, no Slicer.
    ``seed`` is a 3-tuple / sequence of 3 floats (world coordinates).

If the implementer names the function or module differently, update the two
constants below — the invariant is the SINGLE-COMPONENT recovery (used for the
per-structure narrow), not the specific spelling.

See also:
  * Docs/design/multi-system-territory-plan.md  (§Part A A3/Q2 per-structure narrow)
  * Docs/adr/0037-vascular-territories-off-markups.md
    (§Amendment — connected-tree-constrained centerline seeding (slice 5))
  * Docs/adr/0004-python-cpp-boundary.md  (pure polydata -> Python)
  * Docs/adr/0027-invariant-test-first.md  (RED / skip-pending discipline)
  * VascularTerritories/VascularTerritoriesLib/VesselHighlightWiring.py
    (closed_surface_polydata — the merge-all surface slice 5 supersedes)
  * VascularTerritories/Testing/Python/test_territories_seed_structure.py
    (the seed->structure mapping bare twin)
  * VascularTerritories/Testing/Python/test_territories_surface_resolution.py
    (the launched vessel-SCT-filter twin, T1)
"""

from __future__ import annotations

import pytest

vtk = pytest.importorskip("vtk")

# The pure-VTK connectivity seam (proposed; sharpen at landing).
CONNECTIVITY_MODULE = "VascularTerritoriesLib.VesselConnectivity"
CONNECTED_COMPONENT_FUNC = "connected_component_at"

# Two well-separated sphere centres so their meshes never share a point and
# connectivity keeps them as two disjoint regions.
CENTER_A = (0.0, 0.0, 0.0)
CENTER_B = (100.0, 0.0, 0.0)
RADIUS = 10.0


# --------------------------------------------------------------------------- #
# Skip-guard (import-guard on the not-yet-existing pure helper; ADR-0027)
# --------------------------------------------------------------------------- #


def _connected_component_at_or_skip():
    """Return the pure ``connected_component_at`` helper, or skip-pend (ADR-0027).

    The plan's PREFERRED bare-testable seam: a surface polydata + a seed point
    -> the single connected component containing the seed.  Import-guards on
    the not-yet-existing ``VesselConnectivity`` module so the file COLLECTS +
    SKIP-PENDINGs cleanly bare until PR-A lands; the skip lifts at the
    implementation commit, when the test RUNS bare (pure VTK).
    """
    try:
        import importlib

        module = importlib.import_module(CONNECTIVITY_MODULE)
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"{CONNECTIVITY_MODULE} not importable ({exc!r}) -- the ADR-0037 "
            "slice-5 (PR-A) connectivity-recovery helper has not landed.  The "
            "skip lifts at the implementation commit (ADR-0027)."
        )
    func = getattr(module, CONNECTED_COMPONENT_FUNC, None)
    if func is None:
        pytest.skip(
            f"{CONNECTIVITY_MODULE} has no {CONNECTED_COMPONENT_FUNC} -- the "
            "ADR-0037 slice-5 (PR-A) connectivity-recovery helper has not "
            "landed (ADR-0027)."
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


def _two_disjoint_spheres():
    """A single polydata holding two DISJOINT sphere components (A then B).

    ``vtkAppendPolyData`` concatenates the two meshes into one dataset without
    merging coincident points (there are none — the centres are 100 apart), so
    ``vtkPolyDataConnectivityFilter`` sees exactly two regions.
    """
    sphere_a = _sphere(CENTER_A)
    sphere_b = _sphere(CENTER_B)
    append = vtk.vtkAppendPolyData()
    append.AddInputData(sphere_a)
    append.AddInputData(sphere_b)
    append.Update()
    return append.GetOutput(), sphere_a, sphere_b


def _number_of_regions(polydata):
    """The number of connected regions in ``polydata`` (AllRegions mode)."""
    conn = vtk.vtkPolyDataConnectivityFilter()
    conn.SetInputData(polydata)
    conn.SetExtractionModeToAllRegions()
    conn.Update()
    return conn.GetNumberOfExtractedRegions()


def _points_inside_sphere(polydata, center, radius, tolerance=1.0e-3):
    """Count ``polydata`` points lying on/inside the sphere ``(center, radius)``.

    Used to prove a recovered component holds ZERO points from the OTHER
    sphere — a component-purity check independent of point ordering.
    """
    count = 0
    cx, cy, cz = center
    r2 = (radius + tolerance) ** 2
    for i in range(polydata.GetNumberOfPoints()):
        px, py, pz = polydata.GetPoint(i)
        if (px - cx) ** 2 + (py - cy) ** 2 + (pz - cz) ** 2 <= r2:
            count += 1
    return count


# =========================================================================== #
# T2 — connectivity picks one component (BARE, pure VTK)
# =========================================================================== #


def test_connectivity_recovers_only_seed_component():
    """T2: a seed on sphere A recovers ONLY sphere A's component.

    ``connected_component_at(two_spheres, seed_on_A)`` returns a component with
    sphere A's point count and holding ZERO points inside sphere B — the
    disjoint B system is never fused into A's tree (ADR-0037 slice-5
    Conformance [test]).  Pure VTK — RUNS bare.
    """
    connected_component_at = _connected_component_at_or_skip()
    two_spheres, sphere_a, sphere_b = _two_disjoint_spheres()

    seed_on_a = CENTER_A  # dead centre of sphere A; ClosestPointRegion picks A
    component = connected_component_at(two_spheres, seed_on_a)

    assert component is not None and component.GetNumberOfPoints() > 0, (
        "the recovered component must be a non-empty polydata (ADR-0037 "
        "slice 5)."
    )
    assert component.GetNumberOfPoints() == sphere_a.GetNumberOfPoints(), (
        "the recovered component must match sphere A's point count "
        f"({component.GetNumberOfPoints()} != {sphere_a.GetNumberOfPoints()}) "
        "-- connectivity must not fuse the disjoint B system into A."
    )
    assert _points_inside_sphere(component, CENTER_B, RADIUS) == 0, (
        "the recovered component must hold ZERO points from the DISJOINT "
        "sphere B -- a territory's tree is one connected component (ADR-0037 "
        "slice 5)."
    )


def test_connectivity_recovered_component_is_single_region():
    """T2: the recovered component is a SINGLE connected region.

    Re-running ``vtkPolyDataConnectivityFilter`` in ``AllRegions`` mode over
    the recovered component reports exactly ONE region — the per-extraction
    VMTK surface is a single connected tree, not the two-region merge (ADR-0037
    slice 5, supersedes merge-all).  Pure VTK — RUNS bare.
    """
    connected_component_at = _connected_component_at_or_skip()
    two_spheres, _sphere_a, _sphere_b = _two_disjoint_spheres()

    # Sanity: the input genuinely has two regions (the merge slice 5 fixes).
    assert _number_of_regions(two_spheres) == 2, (
        "the two-sphere fixture must present TWO disjoint regions."
    )

    component = connected_component_at(two_spheres, CENTER_A)

    assert _number_of_regions(component) == 1, (
        "the recovered per-extraction surface must be a SINGLE connected "
        f"region (got {_number_of_regions(component)}) -- this supersedes the "
        "compute amendment's merge-all input (ADR-0037 slice 5)."
    )


def test_connectivity_recovers_the_other_component_for_a_b_seed():
    """T2: a seed on sphere B recovers ONLY sphere B's component.

    The mirror of the A case — the helper is seed-directed, not fixed to the
    first region — so a click on the OTHER system binds to the OTHER tree
    (ADR-0037 slice 5).  Pure VTK — RUNS bare.
    """
    connected_component_at = _connected_component_at_or_skip()
    two_spheres, _sphere_a, sphere_b = _two_disjoint_spheres()

    component = connected_component_at(two_spheres, CENTER_B)

    assert component is not None and component.GetNumberOfPoints() == (
        sphere_b.GetNumberOfPoints()), (
        "a seed on sphere B must recover sphere B's component "
        f"({None if component is None else component.GetNumberOfPoints()} != "
        f"{sphere_b.GetNumberOfPoints()}) (ADR-0037 slice 5)."
    )
    assert _points_inside_sphere(component, CENTER_A, RADIUS) == 0, (
        "the B-seeded component must hold ZERO points from sphere A."
    )


# =========================================================================== #
# T3 — the per-structure narrow: one segment carrying two disjoint pieces
# =========================================================================== #


def test_per_structure_narrow_picks_the_seeds_piece():
    """T3: a segment with TWO disjoint pieces narrows to the seed's piece.

    The revised extraction resolves each structure's closed surface and narrows
    it to the connected component of that structure's OWN seed, so a single
    input segment that accidentally carries two disjoint tubes still feeds VMTK
    ONE coherent tree — a medial path never tunnels between the two pieces (the
    A3/Q2 "structure with disjoint pieces" edge case; multi-system plan §Part A).
    Modelled by the two-sphere fixture standing in for one segment's two pieces:
    a seed on piece A recovers only A, a seed on piece B recovers only B.  Pure
    VTK — RUNS bare.
    """
    connected_component_at = _connected_component_at_or_skip()
    two_pieces, piece_a, piece_b = _two_disjoint_spheres()

    from_a = connected_component_at(two_pieces, CENTER_A)
    from_b = connected_component_at(two_pieces, CENTER_B)

    assert from_a.GetNumberOfPoints() == piece_a.GetNumberOfPoints(), (
        "a seed on piece A must narrow the structure surface to piece A only "
        f"({from_a.GetNumberOfPoints()} != {piece_a.GetNumberOfPoints()})."
    )
    assert from_b.GetNumberOfPoints() == piece_b.GetNumberOfPoints(), (
        "a seed on piece B must narrow to piece B only "
        f"({from_b.GetNumberOfPoints()} != {piece_b.GetNumberOfPoints()})."
    )
    # Each narrowed piece is disjoint from the other — no tunnelling.
    assert _points_inside_sphere(from_a, CENTER_B, RADIUS) == 0, (
        "the A-narrowed surface must carry no points from piece B (no "
        "tunnelling between one segment's disjoint pieces; A3/Q2)."
    )
    assert _points_inside_sphere(from_b, CENTER_A, RADIUS) == 0, (
        "the B-narrowed surface must carry no points from piece A (A3/Q2)."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

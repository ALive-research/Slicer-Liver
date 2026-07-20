# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""ADR-0037 slice 5 (PR-A) — the connected-vessel-tree recovery invariant.

The compute amendment resolved the VMTK input surface by MERGING every
segment; real liver data (parenchyma + portal + hepatic + tumour, one node)
makes merge-all wrong — portal and hepatic veins are DISJOINT connected
components and a medial path tunnelling between them is meaningless.  Slice 5
narrows a territory's active surface to the SINGLE connected component its
first seed lands on (``AnnotationPoints[territory][0]`` is the RESOLVED
connectivity seed, per the ADR's "reuse index-0" persistence decision).

The connectivity recovery is a PURE-VTK helper (no MRML scene, no Slicer, no
Qt, no GL): given a surface ``vtkPolyData`` + a seed point, return the single
connected component containing that point (``vtkPolyDataConnectivityFilter`` in
``ClosestPointRegion`` mode).  The plan puts the SCT filter in C++ (it reads
MRML segment tags — pinned launched in ``test_territories_surface_resolution``)
and the connectivity in Python (pure polydata) — a clean ADR-0004 split.  This
file is the core new-module BARE invariant: it RUNS bare once
``VascularTerritoriesLib/VesselConnectivity.py`` lands.

* T2 (BARE) — connectivity picks ONE component.  A polydata of two DISJOINT
  spheres (``vtkAppendPolyData`` of two ``vtkSphereSource`` at separated
  centres); a seed on sphere A returns a component matching sphere A's point
  count / bounds and holding ZERO points from sphere B; a seed on sphere B
  returns B.  The recovered component is a SINGLE connected region
  (``vtkPolyDataConnectivityFilter`` in ``AllRegions`` mode reports exactly 1).
* T3 (BARE) — two seeds on disjoint components resolve to DIFFERENT active
  trees; the per-extraction surface is a single region (not the merge); and the
  index-0 persistence invariant — deleting the first seed and re-deriving from
  the new index-0 recovers the SAME component (pins the "reuse
  AnnotationPoints[0]" persistence decision, ADR-0037 slice-5 Conformance
  [review]).

Red->green (ADR-0027): every test import-guards on the not-yet-existing
``VesselConnectivity`` helper and SKIP-PENDINGs cleanly bare until it lands;
the skips lift at the PR-A implementation commit, at which point T2/T3 RUN bare
(pure VTK, no launched Slicer needed).

-- SEAM THE IMPLEMENTER MUST PROVIDE (proposed; sharpen at landing) --

A pure-VTK helper module ``VascularTerritoriesLib.VesselConnectivity`` with:

  * ``connected_component_at(polydata, seed) -> vtkPolyData`` — run
    ``vtkPolyDataConnectivityFilter`` with
    ``SetExtractionModeToClosestPointRegion()`` +
    ``SetClosestPoint(seed)`` and return the single connected component
    containing ``seed``.  Pure polydata in / out; no MRML, no Slicer.
    ``seed`` is a 3-tuple / sequence of 3 floats (world coordinates).

If the implementer names the function or module differently, update the two
constants below — the invariants are the SINGLE-COMPONENT recovery + the
index-0 persistence, not the specific spelling.

See also:
  * Docs/adr/0037-vascular-territories-off-markups.md
    (§Amendment — connected-tree-constrained centerline seeding (slice 5))
  * Docs/adr/0004-python-cpp-boundary.md  (pure polydata -> Python)
  * Docs/adr/0027-invariant-test-first.md  (RED / skip-pending discipline)
  * Docs/design/connected-tree-seeding-plan.md  (C2 connectivity helper; T2/T3)
  * VascularTerritories/VascularTerritoriesLib/VesselHighlightWiring.py
    (closed_surface_polydata — the merge-all surface slice 5 supersedes)
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
# T3 — different seeds -> different trees; index-0 persistence (BARE)
# =========================================================================== #


def test_disjoint_seeds_resolve_to_different_trees():
    """T3: seeds on disjoint components recover DIFFERENT (disjoint) trees.

    A territory whose index-0 seed is on A and another whose index-0 seed is on
    B recover disjoint components — no shared points, so the two territories
    never straddle a fused surface (ADR-0037 slice-5 Conformance [test]).
    Pure VTK — RUNS bare.
    """
    connected_component_at = _connected_component_at_or_skip()
    two_spheres, sphere_a, sphere_b = _two_disjoint_spheres()

    tree_a = connected_component_at(two_spheres, CENTER_A)
    tree_b = connected_component_at(two_spheres, CENTER_B)

    assert tree_a.GetNumberOfPoints() == sphere_a.GetNumberOfPoints()
    assert tree_b.GetNumberOfPoints() == sphere_b.GetNumberOfPoints()
    # Disjoint: A's tree carries no B points and vice-versa.
    assert _points_inside_sphere(tree_a, CENTER_B, RADIUS) == 0, (
        "tree A must carry no points from the B system (ADR-0037 slice 5)."
    )
    assert _points_inside_sphere(tree_b, CENTER_A, RADIUS) == 0, (
        "tree B must carry no points from the A system (ADR-0037 slice 5)."
    )


def test_index_zero_persistence_survives_first_seed_deletion():
    """T3: re-deriving from a NEW index-0 recovers the SAME component.

    ADR-0037 slice-5 Conformance [review] (the RESOLVED persistence decision):
    all of a territory's seeds lie on one component, so deleting the FIRST seed
    (leaving a later seed as the new index-0) still recovers the SAME active
    tree — the "reuse AnnotationPoints[0]" identity is stable under index-0
    deletion.  Modelled purely: two seeds that both lie on sphere A recover the
    same component regardless of which is index-0.  Pure VTK — RUNS bare.
    """
    connected_component_at = _connected_component_at_or_skip()
    two_spheres, sphere_a, _sphere_b = _two_disjoint_spheres()

    # Two distinct seeds, BOTH on sphere A (the single-tree constraint holds:
    # every seed of a territory lies on the same component).
    first_seed = (CENTER_A[0] - RADIUS + 1.0, CENTER_A[1], CENTER_A[2])
    later_seed = (CENTER_A[0] + RADIUS - 1.0, CENTER_A[1], CENTER_A[2])

    from_first = connected_component_at(two_spheres, first_seed)
    # After deleting the first seed, the new index-0 is ``later_seed``.
    from_later = connected_component_at(two_spheres, later_seed)

    assert from_first.GetNumberOfPoints() == sphere_a.GetNumberOfPoints(), (
        "the index-0 seed must recover sphere A's whole component."
    )
    assert from_later.GetNumberOfPoints() == from_first.GetNumberOfPoints(), (
        "re-deriving the active tree from the NEW index-0 (after deleting the "
        "first seed) must recover the SAME component -- the reuse-index-0 "
        "identity is stable under first-seed deletion (ADR-0037 slice-5 "
        "Conformance [review])."
    )
    assert _points_inside_sphere(from_later, CENTER_B, RADIUS) == 0, (
        "the re-derived tree must still be A-only, never fused with B."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

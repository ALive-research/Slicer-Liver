# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Seed -> structure mapping for multi-system territories (ADR-0037 slice 5).

A vascular territory may own seeds across MULTIPLE disjoint structures (input
segments): points on the portal vein plus points on the hepatic vein, for
instance.  Each seed belongs to the structure whose CLOSED SURFACE it is
nearest.  That mapping is what lets extraction GROUP a territory's seeds by
structure (one VMTK run per structure with >=2 seeds) and the table colour each
seed row by its structure.

This module is a PURE-VTK helper: no MRML scene, no Slicer, no Qt, no GL — so it
runs on the bare unit layer.  ``vtkCellLocator`` is fully Python-wrapped, so per
the ADR-0004 split the geometry (nearest closed surface to a point) lives in
Python while the segment -> closed-surface + segment -> colour resolution reads
MRML segment state on the C++/Python seams.

See also:
  * Docs/adr/0037-vascular-territories-off-markups.md
    (§Amendment — connected-tree-constrained centerline seeding (slice 5))
  * Docs/adr/0004-python-cpp-boundary.md  (pure polydata -> Python)
  * VascularTerritories/VascularTerritoriesLib/VesselConnectivity.py
    (the per-structure connected-component narrow sibling)
"""

from __future__ import annotations

from typing import Any
from collections.abc import Sequence

import vtk

#: Relative squared-distance tolerance below which two structures count as
#: equidistant; a near-tie keeps the FIRST structure in order (Q3 tiebreak).
#: Tessellated closed surfaces never yield bit-identical distances, so a plain
#: strict-less comparison would let floating-point noise decide the tie.
_TIE_REL_TOL = 1.0e-6


def nearest_structure(structures: Sequence, point: Sequence[float]):
    """The key of the structure whose closed surface is nearest ``point``.

    ``structures`` is an ORDERED sequence of ``(key, closed_surface_polydata)``
    where ``key`` is the segment id (str).  ``point`` is a 3-float world
    coordinate.  Builds a ``vtkCellLocator`` (``FindClosestPoint``) per surface
    and returns the key of the structure with the smallest distance to
    ``point``.  A distance tie resolves to the FIRST structure in order
    (deterministic).  An empty ``structures`` -> ``None``.
    """
    px, py, pz = float(point[0]), float(point[1]), float(point[2])
    best_key = None
    best_distance2 = None
    for key, surface in structures:
        if surface is None or surface.GetNumberOfPoints() == 0:
            continue
        locator = vtk.vtkCellLocator()
        locator.SetDataSet(surface)
        locator.BuildLocator()
        closest = [0.0, 0.0, 0.0]
        cell_id = vtk.reference(0)
        sub_id = vtk.reference(0)
        distance2 = vtk.reference(0.0)
        locator.FindClosestPoint((px, py, pz), closest, cell_id, sub_id, distance2)
        d2 = float(distance2)
        # Only a STRICTLY closer structure (beyond a relative tolerance)
        # displaces the incumbent, so a distance tie -- including the tessellated
        # near-tie of two symmetric surfaces -- keeps the FIRST structure in
        # order (deterministic tiebreak).
        if best_distance2 is None or d2 < best_distance2 * (1.0 - _TIE_REL_TOL):
            best_distance2 = d2
            best_key = key
    return best_key


def territory_structure_seed_counts(assignments: Sequence) -> dict:
    """Group mapped seeds into ``{structureKey: count}``.

    ``assignments`` is a sequence of ``(seed, structureKey)`` pairs (the seed
    itself is ignored — only the structure key matters).  Reused by the table's
    <2-seed warning and the extractor's >=2-per-structure gate, so the two agree
    on which structures are under-seeded.
    """
    counts: dict[Any, int] = {}
    for _seed, structure_key in assignments:
        counts[structure_key] = counts.get(structure_key, 0) + 1
    return counts

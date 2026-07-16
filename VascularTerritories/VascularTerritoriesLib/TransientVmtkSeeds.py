# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""ADR-0037 Stage-3 — the pure transient-seed builder core (VMTK feed).

ADR-0037 §Decision 4 rewires the SlicerVMTK ``ExtractCenterline`` feed OFF
Slicer markups ONTO the annotation carrier
(``vtkMRMLCustomTerritoriesNode``).  ``ExtractCenterline`` reads a
per-control-point *selected* flag off a markups node to discriminate the
inlet (start endpoint) from the target endpoints: the SlicerVMTK
convention is that the ONE unselected control point (``selected == False``)
is the inlet and every other point is ``selected == True``.

This module holds the DEPENDENCY-FREE core of the feed: a pure function
mapping a territory's ordered points + inlet index to the fiducial-shaped
``(x, y, z, selected)`` payload, preserving placement order.  It imports
neither ``slicer`` nor ``vtk`` nor Qt so it stays bare-unit-testable (the
transient ``vtkMRMLMarkupsFiducialNode`` creation lives in the module Logic
as a thin wrapper over this core, ADR-0004).

See also:
  * Docs/adr/0037-vascular-territories-off-markups.md  (§Decision 4)
  * Docs/adr/0014-livermarkups-dissolution.md  (no persistent markups)
"""

from __future__ import annotations


def build_seed_payload(points, inlet_index=0):
    """Map ordered carrier points to a VMTK-fiducial-shaped seed payload.

    Reproduces ``points`` 1:1 in placement ORDER as ``(x, y, z, selected)``
    tuples.  Exactly ONE point — the one at ``inlet_index`` — is marked the
    inlet with ``selected == False``; every other point is
    ``selected == True`` (the SlicerVMTK start/inlet convention that
    ``ExtractCenterline`` reads off the markups node).

    Pure — no live scene, no SlicerVMTK, no Qt — so the mapping invariant is
    bare-unit-testable (ADR-0037 §Decision 4 + §Conformance [test]).

    :param points: iterable of ``(x, y, z)`` coordinate triples in
        placement order.
    :param inlet_index: index of the inlet (start endpoint); defaults to the
        first point (index 0).  A single-point territory therefore yields a
        single inlet.
    :returns: list of ``(x, y, z, selected: bool)`` tuples, one per input
        point, in the SAME order.
    """
    seeds = []
    for index, point in enumerate(points):
        x, y, z = point[0], point[1], point[2]
        selected = index != inlet_index
        seeds.append((float(x), float(y), float(z), selected))
    return seeds

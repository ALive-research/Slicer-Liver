# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Connected-vessel-tree recovery for the centerline feed (ADR-0037 slice 5).

The compute amendment resolved the VMTK input surface by MERGING every
segment; real liver data (parenchyma + portal + hepatic + tumour in one
node) makes merge-all wrong — portal and hepatic veins are DISJOINT connected
components and a medial path tunnelling between them is meaningless.  Slice 5
narrows a territory's active surface to the SINGLE connected component its
first seed lands on (``AnnotationPoints[territory][0]`` is the RESOLVED
connectivity seed, per the ADR's "reuse index-0" persistence decision).

This module is a PURE-VTK helper: no MRML scene, no Slicer, no Qt, no GL — so
it runs on the bare unit layer.  ``vtkPolyDataConnectivityFilter`` is fully
Python-wrapped and has no C++-only dependency, so per the ADR-0004 split the
connectivity (pure polydata) lives in Python while the SCT segment filter (it
reads MRML segment tags) stays on the C++ Logic.

See also:
  * Docs/adr/0037-vascular-territories-off-markups.md
    (§Amendment — connected-tree-constrained centerline seeding (slice 5))
  * Docs/adr/0004-python-cpp-boundary.md
  * VascularTerritories/VascularTerritoriesLib/VesselHighlightWiring.py
    (closed_surface_polydata — the merge-all surface this supersedes)
"""

from __future__ import annotations

from typing import Any
from collections.abc import Sequence

import vtk


def connected_component_at(polydata: Any, seed: Sequence[float]):
    """The single connected component of ``polydata`` containing ``seed``.

    Runs ``vtkPolyDataConnectivityFilter`` in ``ClosestPointRegion`` mode
    seeded at the world coordinate ``seed`` (a sequence of three floats) and
    returns the one connected region whose closest point is nearest ``seed``.
    Disjoint components (e.g. portal vs hepatic vessel systems) are never fused
    into the returned tree.

    Returns ``None`` when ``polydata`` is ``None`` / empty; otherwise a
    ``vtkPolyData`` holding only the seed's component.
    """
    if polydata is None or polydata.GetNumberOfPoints() == 0:
        return None

    connectivity = vtk.vtkPolyDataConnectivityFilter()
    connectivity.SetInputData(polydata)
    connectivity.SetExtractionModeToClosestPointRegion()
    connectivity.SetClosestPoint(seed[0], seed[1], seed[2])
    connectivity.Update()

    # ClosestPointRegion keeps the region's cells but leaves the input's
    # unused points in place; clean the output so the recovered component's
    # point count reflects only its own region (the invariant tests assert on
    # the point count).
    cleaner = vtk.vtkCleanPolyData()
    cleaner.SetInputConnection(connectivity.GetOutputPort())
    cleaner.PointMergingOff()
    cleaner.Update()
    return cleaner.GetOutput()


def nearest_point_on(polydata: Any, point: Sequence[float]):
    """The point of ``polydata`` nearest ``point``, or ``None`` when empty.

    Used by the placement pipelines to re-snap an off-tree later seed onto the
    active connected component (ADR-0037 slice 5, C4).  Pure-VTK
    (``vtkPointLocator``) so it stays on the bare unit layer alongside
    ``connected_component_at``.
    """
    if polydata is None or polydata.GetNumberOfPoints() == 0:
        return None
    locator = vtk.vtkPointLocator()
    locator.SetDataSet(polydata)
    locator.BuildLocator()
    closest_id = locator.FindClosestPoint(point[0], point[1], point[2])
    if closest_id < 0:
        return None
    return tuple(polydata.GetPoint(closest_id))

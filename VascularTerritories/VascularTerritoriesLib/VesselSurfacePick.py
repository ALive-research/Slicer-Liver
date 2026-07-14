# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Pure-VTK pick core for the VascularTerritories vessel-adhering highlight.

Given a closed-surface ``vtkPolyData`` (the input segmentation's mesh)
and a cursor ray in world coordinates, resolve the world point the
highlight should adhere to:

* the ray hits the mesh -> the intersection NEAREST the ray origin,
  lying ON the mesh;
* the ray misses -> the nearest-surface projection of ``fallback_point``;
* there is no mesh at all -> ``None`` (the raw-point fallback is the
  caller's concern).

The pick is backed by a ``vtkCellLocator`` built lazily from the
polydata.  The locator is rebuilt when the polydata's ``MTime`` advances
past the MTime observed at the last build, so an edited/rebuilt segment
mesh is always reflected by the next pick.

This is a pure-VTK unit-layer class: no Slicer, MRML or Qt imports
(ADR-0004 keeps the pick math in Python; ADR-0003 keeps this layer
bare-unit testable).  The locator pattern mirrors the resection pick
core described in ADR-0025.
"""

from __future__ import annotations

import vtk


class VesselSurfacePick:
    """Resolve the adhering world point for a cursor ray over a mesh."""

    def __init__(self, polydata: vtk.vtkPolyData | None) -> None:
        self._polydata = polydata
        self._locator: vtk.vtkCellLocator | None = None
        self._built_mtime: int | None = None

    # ------------------------------------------------------------------ #
    # Locator lifecycle
    # ------------------------------------------------------------------ #
    def _has_surface(self) -> bool:
        return (
            self._polydata is not None
            and self._polydata.GetNumberOfPoints() > 0
            and self._polydata.GetNumberOfCells() > 0
        )

    def _ensure_locator(self) -> vtk.vtkCellLocator | None:
        """Build the locator lazily, rebuilding when the mesh is stale.

        A stale cache is detected by comparing the polydata's current
        ``MTime`` against the MTime observed at the last build; when the
        surface points/cells mutate and the polydata is marked modified,
        the advanced MTime forces a rebuild (ADR-0025 cache invalidation).
        """
        if not self._has_surface():
            self._locator = None
            self._built_mtime = None
            return None

        current_mtime = self._polydata.GetMTime()
        if self._locator is None or self._built_mtime != current_mtime:
            locator = vtk.vtkCellLocator()
            locator.SetDataSet(self._polydata)
            locator.BuildLocator()
            self._locator = locator
            self._built_mtime = current_mtime
        return self._locator

    # ------------------------------------------------------------------ #
    # Pick
    # ------------------------------------------------------------------ #
    def pick(
        self,
        p1: tuple[float, float, float],
        p2: tuple[float, float, float],
        fallback_point: tuple[float, float, float] | None = None,
    ) -> tuple[float, float, float] | None:
        """Return the adhering world point, or ``None`` when there is no mesh.

        ``p1``/``p2`` define the world-space cursor ray (``p1`` is the ray
        origin, near the camera).  ``fallback_point`` is projected onto the
        surface when the ray misses.
        """
        locator = self._ensure_locator()
        if locator is None:
            return None

        hit = self._intersect(locator, p1, p2)
        if hit is not None:
            return hit

        if fallback_point is None:
            return None
        return self._closest(locator, fallback_point)

    @staticmethod
    def _intersect(
        locator: vtk.vtkCellLocator,
        p1: tuple[float, float, float],
        p2: tuple[float, float, float],
    ) -> tuple[float, float, float] | None:
        """Ray/mesh intersection nearest the ray origin ``p1``.

        ``IntersectWithLine`` reports the first intersection along the
        parametric line from ``p1`` to ``p2`` (smallest ``t``), which is
        the hit nearest the ray origin even when the ray folds over the
        mesh twice.
        """
        t = vtk.reference(0.0)
        intersection = [0.0, 0.0, 0.0]
        pcoords = [0.0, 0.0, 0.0]
        sub_id = vtk.reference(0)
        cell_id = vtk.reference(0)
        code = locator.IntersectWithLine(
            list(p1),
            list(p2),
            1e-6,
            t,
            intersection,
            pcoords,
            sub_id,
            cell_id,
        )
        if code == 0:
            return None
        return tuple(intersection)

    @staticmethod
    def _closest(
        locator: vtk.vtkCellLocator,
        point: tuple[float, float, float],
    ) -> tuple[float, float, float]:
        """Nearest point on the surface to ``point``."""
        closest = [0.0, 0.0, 0.0]
        cell_id = vtk.reference(0)
        sub_id = vtk.reference(0)
        dist2 = vtk.reference(0.0)
        locator.FindClosestPoint(list(point), closest, cell_id, sub_id, dist2)
        return tuple(closest)

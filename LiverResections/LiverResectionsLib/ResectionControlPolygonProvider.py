# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""The resection control-polygon ``PointProvider`` adapter (ADR-0038 seam).

ADR-0038 §Decision makes resection the extraction-source client of the
shared ``SurfacePointPlacementPipeline3D`` base over a ``PointProvider``
seam.  This adapter wraps the Bezier carrier's fixed ``Rows x Cols`` control
grid: a resection provider is ``has_edges() == True`` (the grid IS a
connected polygon, unlike the flat territory/volumetry point sets), the
per-point key is the flat row-major index into the grid, and the drag
write-back targets ``vtkMRMLBezierSurfaceNode::SetControlPoint`` gated on the
``Planning`` state (ADR-0019 read-only-after-commit).

The resection-SPECIFIC concerns -- the control grid IS fixed, so ``add_point``
is a no-op (there is no add-on-click; you grab and drag an existing handle),
and the Init/Planning state gating lives on the pipeline's ``_admissible``
override, NOT in the base (ADR-0038 §"What is not shared").  The adapter is
a thin fan-out over a carrier getter (the pipeline supplies a live getter so
the provider always reads the current LayerDM back-reference), mirroring the
``TerritoryPointProvider`` precedent.

Pure Python, no LayerDMLib import -- bare-VTK unit testable (ADR-0003/0004).
"""

from __future__ import annotations

from typing import Any

# Planning-state gate (ADR-0019): the control grid is editable only in
# Planning.  Mirrors the C++ ResectionState enum on vtkMRMLBezierSurfaceNode
# (Init = 0, Planning = 1, Confirmed = 2).
STATE_PLANNING = 1

#: The default per-handle base colour the base renders when the carrier /
#: display node offers none.  White reads as the neutral, un-highlighted
#: handle (the grab/hover cues recolour it live).
DEFAULT_HANDLE_RGB = (1.0, 1.0, 1.0)


class ResectionControlPolygonProvider:
    """Ordered, edged ``PointProvider`` over a Bezier control grid.

    Bound to a carrier getter (and an optional per-point colour getter) so it
    stays a thin fan-out with no state of its own; the flat key is the
    row-major grid index the base uses for a grab / drag.
    """

    def __init__(self, carrier_getter, color_getter=None) -> None:
        self._carrier_getter = carrier_getter
        self._color_getter = color_getter

    def _carrier(self) -> Any | None:
        return self._carrier_getter()

    def _state(self, carrier: Any) -> int | None:
        getter = getattr(carrier, "GetState", None)
        if getter is None:
            return None
        try:
            return int(getter())
        except Exception:  # pragma: no cover - defensive (fake carriers)
            return None

    # -- seam the base READS -------------------------------------------- #

    def iter_points(self):
        """Yield ``(world, base_rgb)`` per control point, row-major.

        The base ``enumerate``s this, so the yielded order fixes the flat
        grid index used as the grab / drag key.
        """
        carrier = self._carrier()
        if carrier is None:
            return
        grid = carrier.GetControlGridVector()
        rows = int(carrier.GetRows())
        cols = int(carrier.GetCols())
        rgb = self._base_rgb()
        for i in range(rows * cols):
            base = i * 3
            world = (grid[base], grid[base + 1], grid[base + 2])
            yield world, rgb

    def _base_rgb(self):
        if self._color_getter is not None:
            try:
                c = self._color_getter()
                return (float(c[0]), float(c[1]), float(c[2]))
            except Exception:  # pragma: no cover - defensive
                pass
        return DEFAULT_HANDLE_RGB

    def has_edges(self) -> bool:
        """The control grid IS a connected polygon (ADR-0038 §Context)."""
        return True

    # -- seam the base WRITES ------------------------------------------- #

    def add_point(self, world) -> Any:
        """No-op: the control grid is FIXED (no add-on-click for resection).

        Resection has no add gesture -- the grid is minted by the plan
        re-fit; you grab and drag an existing handle.  Returning ``None``
        declines any accidental add-on-click at the seam.
        """
        return None

    def move_point(self, key, world) -> None:
        """Move control point ``key`` (flat index) -- Planning-gated (ADR-0019).

        Refuses outside ``Planning`` so a read-only Confirmed carrier cannot
        be edited (the grabbed-index kernel; it never re-picks, so a drag
        cannot hop to another handle mid-gesture).
        """
        carrier = self._carrier()
        if carrier is None or key is None:
            return
        if self._state(carrier) != STATE_PLANNING:
            return
        cols = int(carrier.GetCols())
        carrier.SetControlPoint(
            int(key) // cols,
            int(key) % cols,
            float(world[0]),
            float(world[1]),
            float(world[2]),
        )

    def delete_point(self, key) -> bool:
        """No-op: the control grid is FIXED (no per-handle delete)."""
        return False

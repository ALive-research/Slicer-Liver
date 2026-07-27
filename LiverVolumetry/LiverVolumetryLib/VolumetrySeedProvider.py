# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""The LiverVolumetry ``PointProvider`` adapter (ADR-0038 seam).

ADR-0038 §Decision makes LiverVolumetry the THIRD client of the shared
control-point base over a ``PointProvider`` seam.  Volumetry seeds are a FLAT,
ORDERED, no-edges point set (region-growing seeds; no grouping, no polygon):
so this adapter is the simplest of the three clients -- a thin fan-out over
``vtkMRMLVolumetrySeedsNode`` with the add / drag / delete write-backs
targeting the carrier's ``AddSeed`` / ``SetNthSeed`` / ``RemoveNthSeed`` and
the per-seed colour read from ``GetNthSeedColor``.

There is NO territory grouping and NO vessel-visibility gate here (ADR-0038
§"What is not shared"): the volumetry client contributes only the flat data
model.  The drag / delete key is the placement INDEX (a flat int), which is
exactly what the base's default enumerate-keyed hit-test and slice projection
expect, so this client needs no key-seam override.
"""

from __future__ import annotations

from typing import Any

#: The seed marker's default display colour when the carrier reports none
#: (opaque white matches the carrier's own out-of-range default).
_DEFAULT_SEED_RGB = (1.0, 1.0, 1.0)


class VolumetrySeedProvider:
    """Flat, no-edges ``PointProvider`` over a volumetry seed carrier.

    Bound to a ``vtkMRMLVolumetrySeedsNode`` carrier; keeps no state of its
    own beyond that reference, so the carrier stays the single source of
    truth (the base holds no shadow copy -- ADR-0038 no-drift).
    """

    def __init__(self, carrier: Any) -> None:
        self._carrier = carrier
        # The shared display node the base's arm/hover/grab state rides
        # (feedback_layerdm_state_on_display_node).  The provider itself does
        # not read it, but the placement wiring binds it here for symmetry
        # with the territory client's SetDisplayNode seam.
        self._display_node: Any | None = None

    def SetDisplayNode(self, displayNode: Any) -> None:  # noqa: N802 - VTK verb
        """Bind the shared display node the interaction state rides."""
        self._display_node = displayNode

    def iter_points(self):
        """Yield ``(world, base_rgb)`` per seed, flat in placement order.

        The enumeration order IS the carrier's placement order, so the base's
        enumerate-keyed grab hit-test + slice projection key each seed by its
        placement index -- the key the add / move / delete write-backs expect.
        """
        carrier = self._carrier
        if carrier is None:
            return
        for i in range(carrier.GetNumberOfSeeds()):
            coord = carrier.GetNthSeed(i)
            world = (float(coord[0]), float(coord[1]), float(coord[2]))
            rgb = carrier.GetNthSeedColor(i)
            base_rgb = (float(rgb[0]), float(rgb[1]), float(rgb[2]))
            yield world, base_rgb

    def has_edges(self) -> bool:
        """Volumetry seeds are unordered region-grow seeds -- no edges."""
        return False

    def add_point(self, world) -> Any:
        """Append one seed at ``world``; return its placement index (the key)."""
        carrier = self._carrier
        if carrier is None:
            return None
        return carrier.AddSeed(float(world[0]), float(world[1]), float(world[2]))

    def move_point(self, key, world) -> None:
        """Relocate the index-``key`` seed to ``world`` (a drag edit)."""
        carrier = self._carrier
        if carrier is None or key is None:
            return
        carrier.SetNthSeed(int(key), float(world[0]), float(world[1]), float(world[2]))

    def delete_point(self, key) -> bool:
        """Remove the index-``key`` seed; True iff one was removed."""
        carrier = self._carrier
        if carrier is None or key is None:
            return False
        return bool(carrier.RemoveNthSeed(int(key)))

# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""The VascularTerritories ``PointProvider`` adapter (ADR-0038 seam).

ADR-0038 §Decision makes VascularTerritories a client of the shared
control-point base over a ``PointProvider`` seam.  This adapter fans the
flat ordered point set the base reads out over the carrier's per-territory
grouping (``vtkMRMLCustomTerritoriesNode``): a territory provider is
``has_edges() == False`` (unordered per-territory carrier points, no polygon
edges -- ADR-0038 §Context), with the add / drag / delete write-backs
targeting the carrier's ``AddAnnotationPoint`` / ``SetNthAnnotationPoint`` /
``RemoveNthAnnotationPoint``.

The territory-SPECIFIC concerns -- per-territory grouping, vessel-visibility
gating, the active-territory placement -- stay in ``VascularTerritoriesLib``
(the pipeline + this adapter), NOT in the base (ADR-0038 §"What is not
shared").  ``add_point`` fans into the ACTIVE territory; the per-point key is
a ``(territoryId, index)`` pair the carrier writes round-trip.

Two visibility notions are in play (they genuinely DIFFER, so this adapter
keeps BOTH, matching the #569 behaviour the pipeline's ``_rebuild_seed_actor``
already implements):

* ``carrier.GetTerritoryVisibility(territory)`` -- a territory ROW toggle in
  the table hides that whole territory's seeds;
* the per-seed VESSEL-SEGMENT visibility (``visible_getter``) -- a seed whose
  nearest vessel structure is hidden in the structures table is not drawn.

``iter_points`` gates on BOTH so the base's grab hit-test enumerates exactly
the seeds the pipeline draws -- the ``(territoryId, index)`` keys line up.
"""

from __future__ import annotations

from typing import Any


class TerritoryPointProvider:
    """Flat, no-edges ``PointProvider`` over a custom-territories carrier.

    Bound to resolvers for the carrier, the active territory, and the per-seed
    vessel-visibility gate (the pipeline supplies live getters so the provider
    always reads the shared display node's current binding), so it stays a
    thin fan-out with no state of its own beyond those callables.
    """

    def __init__(self, carrier_getter, territory_getter, visible_getter=None) -> None:
        self._carrier_getter = carrier_getter
        self._territory_getter = territory_getter
        self._visible_getter = visible_getter

    def _carrier(self) -> Any | None:
        return self._carrier_getter()

    def _territory(self) -> str | None:
        return self._territory_getter()

    def _seed_visible(self, point) -> bool:
        """The per-seed vessel-segment visibility gate (``True`` when unwired)."""
        if self._visible_getter is None:
            return True
        return bool(self._visible_getter(point))

    def iter_points(self):
        """Yield ``(world, base_rgb)`` per VISIBLE seed, flat across territories.

        Gates on BOTH the territory-row toggle and the per-seed vessel-segment
        visibility (the #569 semantics), so the enumeration order matches the
        pipeline's ``_rebuild_seed_actor`` -- the base's grab hit-test then
        keys line up with what is drawn.  The per-point colour is the
        territory's display slot colour.
        """
        for _key, payload in self.iter_keyed_points():
            yield payload

    def iter_keyed_points(self):
        """Yield ``((territoryId, index), (world, base_rgb))`` per VISIBLE seed.

        The KEYED companion to ``iter_points`` (the slice base's key seam,
        ADR-0038): the same dual-gated traversal, but each payload carries its
        ``(territoryId, index)`` carrier key so the slice base can store it in
        ``_projected_keys`` (the ``(territoryId, index)`` grab / drag / delete
        round-trips through ``move_point`` / ``delete_point``).  ``iter_points``
        is the key-less projection of this, so BOTH enumerate identically --
        the drawn seeds and their keys always line up.
        """
        carrier = self._carrier()
        if carrier is None:
            return
        for territory in carrier.GetAnnotationTerritoryIds():
            if not bool(carrier.GetTerritoryVisibility(territory)):
                continue
            rgb = carrier.GetTerritoryColor(territory)
            base_rgb = (float(rgb[0]), float(rgb[1]), float(rgb[2]))
            count = carrier.GetNumberOfAnnotationPoints(territory)
            for i in range(count):
                point = carrier.GetNthAnnotationPoint(territory, i)
                if not self._seed_visible(point):
                    continue
                world = (float(point[0]), float(point[1]), float(point[2]))
                yield (territory, i), (world, base_rgb)

    def has_edges(self) -> bool:
        """Territory seeds are unordered per-territory points -- no edges."""
        return False

    def add_point(self, world) -> Any:
        """Append one seed to the ACTIVE territory; return its key."""
        carrier = self._carrier()
        territory = self._territory()
        if carrier is None or territory is None:
            return None
        carrier.AddAnnotationPoint(
            territory, float(world[0]), float(world[1]), float(world[2])
        )
        index = carrier.GetNumberOfAnnotationPoints(territory) - 1
        return (territory, index)

    def move_point(self, key, world) -> None:
        """Relocate the ``(territoryId, index)`` seed to ``world``."""
        carrier = self._carrier()
        if carrier is None or key is None:
            return
        territory, index = key
        carrier.SetNthAnnotationPoint(
            territory, int(index), float(world[0]), float(world[1]), float(world[2])
        )

    def delete_point(self, key) -> bool:
        """Remove the ``(territoryId, index)`` seed; True iff one was removed."""
        carrier = self._carrier()
        if carrier is None or key is None:
            return False
        territory, index = key
        return bool(carrier.RemoveNthAnnotationPoint(territory, int(index)))

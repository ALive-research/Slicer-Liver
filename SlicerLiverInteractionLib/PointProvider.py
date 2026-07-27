# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""The ADR-0038 point-provider seam + the swappable pick provider.

ADR-0038 §Decision parameterizes the shared control-point interaction base
by a small **point-provider seam** the consumer supplies.  The base owns the
generic affordance (add-on-click / drag-to-edit-nearest / delete /
bare-move-decline, the glow halo, the slice projection + fade, the pick
arbitration, the grab seam, the four LayerDM invariants); the consumer's
``PointProvider`` supplies the *data model* -- the points to render, whether
they form edges, and the drag / delete write-backs -- plus the display-node
channel for the shared arm/hover/grab state.

Per the ADR's implementation amendment (2026-07-27) the pick step is ALSO a
provider on the seam (``PickProvider``): surface consumers (resection,
vascular territories) inject a surface pick, an in-volume consumer
(LiverVolumetry) injects a slice-click pick, and the base carries NO
surface-vs-volume branch -- it places at whatever world point the pick
returns.

These are duck-typed protocols, not enforced base classes: the concrete
resection / territory / volumetry adapters implement the same method names
over their own carriers.  They are documented here so the base's contract is
one place, and so a fake provider (the base's characterization test) has a
single shape to satisfy.
"""

from __future__ import annotations

from typing import Any, Protocol
from collections.abc import Iterable

#: A world position + its per-point base colour, as the base reads them.
WorldPoint = tuple[float, float, float]
Rgb = tuple[float, float, float]


class PointProvider(Protocol):
    """The consumer-supplied data model the base reads + writes (ADR-0038).

    Ordered so a drag / delete key is a stable index into ``iter_points()``.
    A resection provider wraps the Bezier control grid (``has_edges()`` True);
    a territory / volumetry provider wraps a flat point set (``has_edges()``
    False).  The consumer keeps every data-model concern -- grouping, vessel
    gating, state-machine gating -- OUT of the base (ADR-0038 §"What is not
    shared"); those live in the concrete adapter's overrides, not here.
    """

    def iter_points(self) -> Iterable[tuple[WorldPoint, Rgb]]:
        """Yield ``(world, base_rgb)`` for every point the base renders."""
        ...

    def has_edges(self) -> bool:
        """True iff the points form a connected polygon (resection grid)."""
        ...

    def add_point(self, world: WorldPoint) -> Any:
        """Append one point at ``world``; return its key (index)."""
        ...

    def move_point(self, key: Any, world: WorldPoint) -> None:
        """Relocate the point identified by ``key`` to ``world``."""
        ...

    def delete_point(self, key: Any) -> bool:
        """Remove the point identified by ``key``; True iff one was removed."""
        ...


class PickProvider(Protocol):
    """The swappable click->world pick step (ADR-0038 §"Base extension").

    The base calls ``pick_for_event`` for a click's world position and places
    at whatever it returns -- there is NO surface-vs-volume branch in the
    base.  ``SurfacePick`` is the surface variant; an in-volume / slice-click
    pick is the volumetry variant.  ``None`` declines the placement (the ray
    missed / no surface), which the base treats as "leave the gesture to the
    camera".
    """

    def pick_for_event(self, renderer: Any, eventData: Any) -> WorldPoint | None:
        """Return the world point for the event's pixel, or ``None`` to decline."""
        ...

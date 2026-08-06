# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""territory-usability -- per-volume segment aggregation for Compute.

Compute reports ONE results row per VOLUME: the union of its seeds' EFFECTIVE
(carved) regions (the visibility-composed carve rule, ``VisibilityCarve``).
Each seed contributes its owning segment MINUS the snapshot segments stacked
above it -- so with Parenchyma + Segment_1 visible at placement, a seed in
Parenchyma outside Segment_1 contributes ``Parenchyma \\ Segment_1``, NOT the
whole parenchyma.  A seed with no snapshot (legacy) contributes its whole
bound segment.

This module holds the PURE aggregation the compute path drives:

* ``distinct_bound_segments_per_volume`` -- the flat owner fold (also the
  grouped-compute gate).
* ``effective_regions_per_volume`` -- the carve-aware fold:
  ``{volumeId: [(ownerSegmentID, contextTuple), ...]}`` with distinct
  (owner, context) pairs in first-seen order; the module Logic rasterizes each
  pair's carved mask and unions them per volume.

Kept side-effect-free (vtk only lazily, for the carrier's string-array
context accessor) so it RUNS BARE (ADR-0027).

References
----------
* territory-usability -- the compute-per-volume + compute-on-carved plan.
* LiverVolumetry/LiverVolumetryLib/VisibilityCarve.py -- the carve rule.
* LiverVolumetry/LiverVolumetry.py -- LiverVolumetryLogic.computeVolumePerVolume
  (the driver that rasterizes each volume's carved-region union).
"""

from __future__ import annotations

from typing import Any

try:  # pragma: no cover - exercised once per import path
    from .VisibilityCarve import read_seed_context
except ImportError:  # top-level import path (the unit layer's sys.path setup)
    from VisibilityCarve import read_seed_context  # type: ignore[no-redef]


def distinct_bound_segments_per_volume(carrier: Any) -> dict[str, list[str]]:
    """Fold the carrier's seeds into ``{volumeId: [distinct bound segmentIDs]}``.

    Walks the seeds in placement order; for each seed with a non-empty volume id
    AND a non-empty bound segment id, records the segment id under its volume,
    keeping the DISTINCT bound segments in first-seen order (so a volume with two
    seeds on the same segment counts that segment ONCE, and a volume with seeds
    on Segment_2 + Segment_3 yields both).  Volumes with no bound seed do not
    appear (there is nothing to measure); ungrouped seeds are skipped (they have
    no volume row).

    Returns a plain dict keyed by volume id; the caller decides the row order.
    """
    per_volume: dict[str, list[str]] = {}
    if carrier is None:
        return per_volume
    count = carrier.GetNumberOfSeeds()
    for i in range(count):
        volumeId = carrier.GetNthSeedVolume(i)
        segmentID = carrier.GetNthSeedBindingSegmentID(i)
        if not volumeId or not segmentID:
            continue
        segments = per_volume.setdefault(volumeId, [])
        if segmentID not in segments:
            segments.append(segmentID)
    return per_volume


def effective_regions_per_volume(carrier: Any) -> dict[str, list[tuple[str, tuple]]]:
    """Fold the seeds into ``{volumeId: [(ownerSegmentID, contextTuple), ...]}``.

    The carve-aware sibling of ``distinct_bound_segments_per_volume``: each
    bound, grouped seed contributes its ``(owning segment, visibility
    snapshot)`` pair -- the seed's reproducible region definition
    (``VisibilityCarve``).  DISTINCT pairs are kept in first-seen order (two
    seeds with the same owner AND the same snapshot count once; the same owner
    under DIFFERENT snapshots counts twice -- they carve differently).  An
    empty snapshot means "the whole owning segment" (legacy semantics).
    Unbound or ungrouped seeds are skipped, as in the flat fold.
    """
    per_volume: dict[str, list[tuple[str, tuple]]] = {}
    if carrier is None:
        return per_volume
    count = carrier.GetNumberOfSeeds()
    for i in range(count):
        volumeId = carrier.GetNthSeedVolume(i)
        segmentID = carrier.GetNthSeedBindingSegmentID(i)
        if not volumeId or not segmentID:
            continue
        entry = (segmentID, tuple(read_seed_context(carrier, i)))
        entries = per_volume.setdefault(volumeId, [])
        if entry not in entries:
            entries.append(entry)
    return per_volume

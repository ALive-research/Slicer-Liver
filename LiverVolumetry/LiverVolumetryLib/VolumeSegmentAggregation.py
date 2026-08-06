# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""territory-usability -- per-volume segment aggregation for Compute.

Compute reports ONE results row per VOLUME: the combined region of the DISTINCT
segments the volume's seeds are bound to (the union of the bound segments'
regions).  A volume whose seeds bind to Segment_2 + Segment_3 measures
``|seg2 ∪ seg3|``.

This module holds the PURE aggregation the compute path drives: reading the
carrier's per-seed volume ids + per-seed structure bindings and folding them
into ``{volumeId: [distinct bound segmentIDs]}``.  Kept as a thin, side-effect-
free helper (no Slicer / no VTK) so it RUNS BARE (ADR-0027) and the voxel-union
volume computation in the module Logic drives it with a rasterizer.

References
----------
* territory-usability -- the compute-per-volume plan (this SUT).
* LiverVolumetry/LiverVolumetry.py -- LiverVolumetryLogic.computeVolumePerVolume
  (the driver that rasterizes each volume's bound-segment union).
"""

from __future__ import annotations

from typing import Any


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

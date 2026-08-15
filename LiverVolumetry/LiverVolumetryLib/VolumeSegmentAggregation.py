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

The SAME per-volume region definition serves BOTH products -- Compute's rows
and Generate's materialised segments -- so the measured mL and the generated
segment are the same region by construction, never two parallel derivations.

This module holds the PURE aggregation both paths drive:

* ``distinct_bound_segments_per_volume`` -- the flat owner fold (also the
  grouped-compute gate).
* ``effective_regions_per_volume`` -- the carve-aware fold:
  ``{volumeId: [(ownerSegmentID, contextTuple), ...]}`` with distinct
  (owner, context) pairs in first-seen order.
* ``carved_masks_per_volume`` -- the shared rasterized fold:
  ``{volumeId: boolean union mask}`` over an INJECTED mask reader, so Compute
  measures ``mask.sum()`` and Generate materialises the very same ``mask``.

Kept side-effect-free (numpy / vtk only lazily, inside the functions that need
them) so it RUNS BARE (ADR-0027).

References
----------
* territory-usability -- the compute-per-volume + compute-on-carved plan.
* LiverVolumetry/LiverVolumetryLib/VisibilityCarve.py -- the carve rule.
* LiverVolumetry/LiverVolumetry.py -- LiverVolumetryLogic.computeVolumePerVolume
  (measures each mask) and LiverVolumetryLogic.generateSegments (materialises
  the same masks as segments).
"""

from __future__ import annotations

from typing import Any

try:  # pragma: no cover - exercised once per import path
    from .VisibilityCarve import (
        carve_effective_mask,
        read_seed_context,
        segments_above,
    )
except ImportError:  # top-level import path (the unit layer's sys.path setup)
    from VisibilityCarve import (  # type: ignore[no-redef]
        carve_effective_mask,
        read_seed_context,
        segments_above,
    )


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


def carved_masks_per_volume(carrier: Any, mask_for_segment: Any, shape: Any) -> dict:
    """Rasterize the fold: ``{volumeId: boolean union of its effective regions}``.

    THE shared region definition behind both volumetry products -- Compute
    counts each mask's voxels into a results row, Generate materialises each
    mask as one segment -- so a volume's measured mL and its generated segment
    are the SAME region by construction (territory-usability).

    ``mask_for_segment(segmentID) -> mask | None`` is injected (the scene side
    passes a reader over one common reference grid,
    ``VisibilityCarve.segment_mask_reader``), which keeps this fold pure and
    bare-testable.  ``shape`` is that grid's array shape: a volume whose owner
    masks are all unreadable still yields an all-False mask (a visible zero),
    never a missing entry.  An unreadable carver carves nothing (best-effort).

    Volumes appear in the carrier's own volume order (the surgeon's row
    order); volumes with no bound, grouped seed do not appear at all.
    """
    import numpy as np

    per_volume = effective_regions_per_volume(carrier)
    # Row order = the order the volumes were added.  Volumes the carrier does
    # not list (or a carrier predating the accessor) fall in behind in
    # first-seen seed order, so an ordering gap never drops a measured volume.
    ordered = []
    if carrier is not None and hasattr(carrier, "GetVolumeIds"):
        ordered = [v for v in carrier.GetVolumeIds() if v in per_volume]
    ordered += [v for v in per_volume if v not in ordered]

    masks: dict = {}
    for volumeId in ordered:
        union = np.zeros(shape, dtype=bool)
        for ownerSegmentID, context in per_volume[volumeId]:
            owner_mask = mask_for_segment(ownerSegmentID)
            if owner_mask is None:
                continue
            above_masks = [
                mask
                for mask in (
                    mask_for_segment(segmentID)
                    for segmentID in segments_above(list(context), ownerSegmentID)
                )
                if mask is not None
            ]
            union |= carve_effective_mask(owner_mask, above_masks)
        masks[volumeId] = union
    return masks

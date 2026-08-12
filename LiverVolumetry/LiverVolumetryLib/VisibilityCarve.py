# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""territory-usability -- the visibility-composed carve rule.

Visibility COMPOSES the region a volumetry seed measures.  The surgeon sets
segment show/hide BEFORE placing; a dropped seed's EFFECTIVE region is the
VISIBLE segment that owns the clicked voxel (top visible layer wins,
``SeedTargetResolution``) MINUS every visible segment stacked ABOVE it
anywhere -- visible layers CARVE each other, and the top-visible layer owns
each voxel.  Canonically (the phantom): with only Parenchyma + Segment_1
visible, a seed in Parenchyma outside Segment_1 measures
``Parenchyma \\ Segment_1``.

The seed records its VISIBILITY CONTEXT at placement -- the ordered
(top-first) list of visible segment IDs -- and that snapshot IS the seed's
reproducible definition (the carrier persists it,
``vtkMRMLVolumetrySeedsNode`` §"Field roster").  Everything downstream
(restore-on-select, the carved-region highlight, compute) re-derives the
carve FROM the snapshot, so re-opening a scene reproduces the same regions
regardless of the live visibility.

This module holds the PURE core (no Slicer / no VTK at import -- the bare
unit layer reaches it, ADR-0027) plus the thin scene-side context gatherer:

* ``order_visible_top_first`` -- the snapshot ordering (descending layer
  index, stable within a layer; the same comparator
  ``resolve_touched_candidates`` uses for the owner pick).
* ``segments_above`` -- the carving set: the context PREFIX before the owner.
* ``carve_effective_mask`` -- owner mask minus the union of the carvers.
* ``apply_visibility_context`` -- restore-on-select: show exactly the
  snapshot's segments.
* ``visible_context`` -- the scene-side gatherer (segmentation + display
  node -> ordered visible segment IDs).

References
----------
* ``territory-usability`` §"Seed→label capture" -- the top-visible-owns rule
  this extends with the carve.
* LiverVolumetry/LiverVolumetryLib/SeedTargetResolution.py -- the owner pick.
* LiverVolumetry/MRML/vtkMRMLVolumetrySeedsNode.h -- the persisted snapshot.
"""

from __future__ import annotations

from typing import Any

try:  # pragma: no cover - exercised once per import path
    from .SeedTargetResolution import resolve_touched_candidates
except ImportError:  # top-level import path (the unit layer's sys.path setup)
    from SeedTargetResolution import resolve_touched_candidates  # type: ignore[no-redef]


def order_visible_top_first(visible: list[tuple[str, int]]) -> list[str]:
    """Order ``(segmentID, layerIndex)`` pairs top-first (the snapshot order).

    Highest layer index leads (drawn on top == carves everything below);
    ties keep input order so the snapshot is deterministic.  Delegates to
    ``resolve_touched_candidates`` -- the LITERAL same comparator as the
    owner pick, so the owner's position in the context is consistent with it
    by construction.
    """
    ordered, _top = resolve_touched_candidates(visible)
    return ordered


def segments_above(context: list[str], ownerSegmentID: str) -> list[str]:
    """The segments that CARVE the owner: the context prefix before it.

    ``context`` is the seed's visibility snapshot, ordered top-first.  The
    carving set is every context segment drawn ABOVE the owner -- i.e. the
    prefix before the owner's position.  An owner absent from the context (a
    legacy seed with no snapshot, or a retarget outside it) carves nothing:
    the effective region falls back to the whole owning segment.
    """
    if ownerSegmentID not in context:
        return []
    return context[: context.index(ownerSegmentID)]


def carve_effective_mask(owner_mask: Any, above_masks: list) -> Any:
    """The effective region: the owner's mask minus the union of the carvers.

    Plain boolean array algebra over same-geometry masks (the caller resamples
    every mask onto ONE reference grid).  Inputs are not mutated; the result
    is a fresh boolean array.
    """
    import numpy as np

    carved = np.asarray(owner_mask, dtype=bool).copy()
    for above in above_masks:
        carved &= ~np.asarray(above, dtype=bool)
    return carved


def segment_mask_reader(segmentationNode: Any, referenceNode: Any) -> Any:
    """A ``mask_for_segment`` reader over a segmentation + reference grid.

    The scene-side companion to ``carved_mask_for_seed``: wraps
    ``slicer.util.arrayFromSegmentBinaryLabelmap`` so every consumer (the
    stripes pipeline, the table's empty-carve cue) resamples onto the SAME
    reference labelmap geometry with the same best-effort semantics -- an
    unreadable segment yields ``None`` (carves nothing), never a raise.
    """

    def _mask(segmentID: str) -> Any:
        try:
            import slicer

            return slicer.util.arrayFromSegmentBinaryLabelmap(
                segmentationNode, segmentID, referenceNode
            )
        except Exception:  # noqa: BLE001 - an unreadable mask carves nothing
            return None

    return _mask


def carved_mask_for_seed(carrier: Any, index: int, mask_for_segment: Any) -> Any:
    """The seed's EFFECTIVE mask: owner minus the snapshot segments above it.

    The ONE owner-minus-above fold every consumer shares (the slice pipeline's
    stripe highlight, the table's empty-carve cue), over an INJECTED
    ``mask_for_segment(segmentID) -> mask | None`` reader so the fold stays
    pure/bare-testable while the scene side supplies
    ``slicer.util.arrayFromSegmentBinaryLabelmap`` on a common reference grid.

    Returns ``None`` for UNKNOWN (missing carrier, unbound seed, or an owner
    whose mask cannot be read) -- distinct from a present-but-EMPTY carve (a
    fully covered owner), which returns an all-False mask the empty-carve cue
    names explicitly.  An unreadable above-mask carves nothing (best-effort).
    """
    if carrier is None or not hasattr(carrier, "GetNthSeedBindingSegmentID"):
        return None
    owner = carrier.GetNthSeedBindingSegmentID(int(index))
    if not owner:
        return None
    owner_mask = mask_for_segment(owner)
    if owner_mask is None:
        return None
    context = read_seed_context(carrier, index)
    above_masks = [
        mask
        for mask in (mask_for_segment(s) for s in segments_above(context, owner))
        if mask is not None
    ]
    return carve_effective_mask(owner_mask, above_masks)


def apply_visibility_context(displayNode: Any, allSegmentIDs: list[str], context: list[str]) -> None:
    """Restore the visibility state to a seed's snapshot (restore-on-select).

    Shows EXACTLY the context's segments and hides the rest, so the view
    flips to the composition that defines the seed.  An empty context (a
    legacy seed with no snapshot) is a NO-OP -- restoring "nothing visible"
    would blank the view, not reproduce a definition.  A missing display node
    degrades to a no-op.
    """
    if displayNode is None or not context:
        return
    wanted = set(context)
    for segmentID in allSegmentIDs:
        displayNode.SetSegmentVisibility(segmentID, segmentID in wanted)


def read_seed_context(carrier: Any, index: int) -> list[str]:
    """The seed's ordered visibility snapshot off the carrier.

    The one place the ``vtkStringArray`` accessor plumbing lives: returns the
    plain ordered id list every consumer (table, pipelines, compute fold)
    works with.  Empty for a missing carrier, a carrier predating the slot,
    an out-of-range index, or a snapshotless seed.
    """
    if carrier is None or not hasattr(carrier, "GetNthSeedVisibilityContext"):
        return []
    import vtk

    ids = vtk.vtkStringArray()
    carrier.GetNthSeedVisibilityContext(int(index), ids)
    return [ids.GetValue(i) for i in range(ids.GetNumberOfValues())]


def write_seed_context(carrier: Any, index: int, context: list[str]) -> None:
    """Store the seed's ordered visibility snapshot on the carrier.

    A no-op for a missing carrier or a carrier predating the slot (an older
    build): the caller's placement still succeeds, the seed just stays
    snapshotless (legacy no-carve semantics).
    """
    if carrier is None or not hasattr(carrier, "SetNthSeedVisibilityContext"):
        return
    import vtk

    ids = vtk.vtkStringArray()
    for segmentID in context:
        ids.InsertNextValue(segmentID)
    carrier.SetNthSeedVisibilityContext(int(index), ids)


def visible_context(segmentationNode: Any, displayNode: Any) -> list[str]:
    """The scene-side snapshot gatherer: ordered visible segment IDs.

    Walks the segmentation's segments, keeps the VISIBLE ones (per the
    segmentation display node; a ``None`` display node counts every segment,
    matching ``gather_touched_candidates``), pairs each with its layer index,
    and returns the top-first order.  Imports nothing heavy: pure attribute
    access over the wrapped nodes.
    """
    if segmentationNode is None or not hasattr(segmentationNode, "GetSegmentation"):
        return []
    segmentation = segmentationNode.GetSegmentation()
    if segmentation is None:
        return []
    visible: list[tuple[str, int]] = []
    for n in range(segmentation.GetNumberOfSegments()):
        segmentID = segmentation.GetNthSegmentID(n)
        if displayNode is not None and hasattr(displayNode, "GetSegmentVisibility"):
            if not displayNode.GetSegmentVisibility(segmentID):
                continue
        visible.append((segmentID, segmentation.GetLayerIndex(segmentID)))
    return order_visible_top_first(visible)

# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""The volumetry seed→label capture resolution rule (``territory-usability``).

When the surgeon drops a seed in a 2D slice, the seed is captured by ONE
structure among the segments overlapping the clicked voxel.  The model is kept
SIMPLE -- no set algebra:

1. Gather the TOUCHED-CANDIDATE set: every VISIBLE segment whose binary
   labelmap covers the clicked voxel (membership read at the single click IJK,
   never a whole-labelmap scan -- see ``gather_touched_candidates``).
2. Default the binding to the TOP layer's segment among the candidates:
   ``vtkSegmentation::GetLayerIndex`` -- the highest layer index is drawn on
   top (confirmed empirically against the phantom, where Tumor is the top
   layer).
3. Offer the OTHER candidates so the surgeon can retarget the binding.

``resolve_touched_candidates`` is the PURE rule (bare-testable, no scene):
given an already-gathered ``(segmentID, layerIndex)`` list it returns the
candidates ordered top-first plus the default (top) segment.
``gather_touched_candidates`` is the thin scene-side reader that builds that
list from a segmentation node + display node at a click voxel; it lives here
so the placement path has one import for the whole capture.

References
----------
* ``territory-usability`` §"Seed→label capture" -- the model above.
* Libs/vtkSegmentationCore/vtkSegmentation.h -- ``GetLayerIndex`` /
  ``GetSegmentIDsForLayer`` / ``GetNumberOfLayers`` (the shared-labelmap
  layering this rule reads).
"""

from __future__ import annotations

from typing import Any


def resolve_touched_candidates(
    touched: list[tuple[str, int]],
) -> tuple[list[str], str | None]:
    """Order the touched candidates top-first and pick the default (top) binding.

    ``touched`` is ``(segmentID, layerIndex)`` for every segment whose binary
    labelmap covers the clicked voxel, in gathering order.  Returns
    ``(orderedSegmentIDs, topSegmentID)``:

    * ``orderedSegmentIDs`` -- the candidates sorted by DESCENDING layer index
      (top drawn last == highest index first), stable within a layer so the
      order never flickers between runs;
    * ``topSegmentID`` -- the first of that order (the default binding), or
      ``None`` when nothing was touched.

    A pure function: no scene, no wrapped node, no numpy.
    """
    if not touched:
        return [], None
    # Stable descending sort by layer index: the highest layer (drawn on top)
    # leads, and ties keep gathering order so the default is deterministic.
    ordered = [seg for seg, _layer in sorted(touched, key=lambda sl: -sl[1])]
    return ordered, ordered[0]


def gather_touched_candidates(segmentationNode: Any, displayNode: Any, ras) -> list[tuple[str, int]]:
    """The visible segments whose binary labelmap covers the RAS point ``ras``.

    Reads the SINGLE voxel value from each VISIBLE segment's binary labelmap
    (never a whole-labelmap scan -- one membership test per visible segment per
    click, ``territory-usability`` §"Seed→label capture" performance note) and
    pairs the hit with the segment's layer index.  Returns ``(segmentID,
    layerIndex)`` in segment order; the caller feeds it to
    ``resolve_touched_candidates``.

    The point is given in RAS and converted to EACH segment's OWN binary-labelmap
    IJK (shared-labelmap layers may sit on different geometries), so the
    membership test is correct even when the layers do not share a grid.

    ``displayNode`` (the SEGMENTATION display node) gates visibility: only
    segments with visibility ON count, so a hidden overlapping structure is
    never silently captured.  A ``None`` display node counts every segment
    (the pick has no visibility opinion).
    """
    if segmentationNode is None or not hasattr(segmentationNode, "GetSegmentation"):
        return []
    import slicer

    segmentation = segmentationNode.GetSegmentation()
    if segmentation is None:
        return []
    touched: list[tuple[str, int]] = []
    for n in range(segmentation.GetNumberOfSegments()):
        segmentID = segmentation.GetNthSegmentID(n)
        if displayNode is not None and hasattr(displayNode, "GetSegmentVisibility"):
            if not displayNode.GetSegmentVisibility(segmentID):
                continue
        if not _ras_is_labelled(slicer, segmentationNode, segmentID, ras):
            continue
        layer = segmentation.GetLayerIndex(segmentID)
        touched.append((segmentID, layer))
    return touched


def _ras_is_labelled(slicer: Any, segmentationNode: Any, segmentID: str, ras) -> bool:
    """True iff the segment's binary labelmap is non-zero at RAS point ``ras``.

    Converts RAS to the SEGMENT's own binary-labelmap IJK (its oriented image
    data carries the geometry) and reads only that ONE voxel -- no whole-array
    scan per click.  A missing labelmap or an out-of-bounds point counts as
    unlabelled.
    """
    import vtk

    try:
        arr = slicer.util.arrayFromSegmentBinaryLabelmap(segmentationNode, segmentID)
    except Exception:  # noqa: BLE001 - a segment without a binary labelmap is simply not touched
        return False
    if arr is None:
        return False
    segment = segmentationNode.GetSegmentation().GetSegment(segmentID)
    if segment is None:
        return False
    labelmap = segment.GetRepresentation("Binary labelmap")
    if labelmap is None or not hasattr(labelmap, "GetImageToWorldMatrix"):
        return False
    world_to_ijk = vtk.vtkMatrix4x4()
    labelmap.GetImageToWorldMatrix(world_to_ijk)
    world_to_ijk.Invert()
    ijk = world_to_ijk.MultiplyPoint([float(ras[0]), float(ras[1]), float(ras[2]), 1.0])
    i, j, k = int(round(ijk[0])), int(round(ijk[1])), int(round(ijk[2]))
    kd, jd, id_ = arr.shape
    if not (0 <= k < kd and 0 <= j < jd and 0 <= i < id_):
        return False
    return bool(arr[k, j, i])

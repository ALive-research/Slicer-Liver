# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""The volumetry in-volume / slice-click pick provider (ADR-0038 §"Base extension").

ADR-0038's implementation amendment (2026-07-27, OQ4) makes the pick step a
SEAM-INJECTED provider on the base, not a fixed surface snap.  LiverVolumetry
seeds are REGION-GROWING seeds: ``vtkLiverVolumetryLogic`` converts each seed
to a voxel index (``TransformPhysicalPointToIndex``) and grows a
``ConnectedThreshold`` from it (ADR-0015), so the seed must land INSIDE the
target region -- on a labelled voxel with labelled neighbours -- not on the
region's surface.  A surface snap would place the seed on the boundary and can
mis-seed the grow.

So the surface consumers (resection, vascular territories) inject a
``SurfacePick``; LiverVolumetry injects THIS in-volume pick.  It resolves a
slice-view click to the interior RAS point of a labelmap volume:

* the pixel is projected to RAS on the slice plane (``XYToRAS``);
* that RAS is mapped to the labelmap's voxel index (``RASToIJK``);
* the index is snapped to the nearest STRICTLY-INTERIOR labelled voxel (a
  labelled voxel whose six axis neighbours are all labelled), so the returned
  RAS lands on a voxel the region-grow can seed.

The base carries NO surface-vs-volume branch (ADR-0038 §"Base extension") -- it
places at whatever world point this provider returns; ``None`` declines the
placement (the click was outside any labelled region).

References
----------
* ADR-0038 -- §"Base extension: the pick step is swappable (surface vs
  in-volume)".
* ADR-0015 -- the region-grow C++ (TransformPhysicalPointToIndex ->
  ConnectedThreshold) the interior seed feeds, unchanged.
* SlicerLiverInteractionLib/SurfacePick.py -- the surface variant this parallels.
"""

from __future__ import annotations

from typing import Any


class InVolumePick:
    """Resolve a slice-view click to an interior labelled voxel's RAS point.

    Bound to a ``vtkMRMLLabelMapVolumeNode``; keeps no cursor state, so a
    (re)aimed labelmap is a fresh binding.  Satisfies both the volumetry
    slice-click seam (``pick_for_slice_event``) and the base's generic pick
    seam (``pick_for_event``), which routes a 3D/slice event through the same
    interior-voxel resolution.
    """

    def __init__(self, labelmap) -> None:
        self._labelmap = labelmap

    # ------------------------------------------------------------------ #
    # The base's generic pick seam (ADR-0038 PickProvider)
    # ------------------------------------------------------------------ #

    def pick_for_event(self, renderer: Any, eventData: Any):
        """The base's click->world seam: return an interior RAS point or ``None``.

        The base calls this for a click; the volumetry pick ignores the
        renderer (the seed is resolved against the labelmap, not the camera)
        and returns the region's interior point.  A slice-aware caller may use
        ``pick_for_slice_event`` directly to honour the clicked pixel.
        """
        del renderer, eventData
        return self._interior_ras()

    # ------------------------------------------------------------------ #
    # The volumetry slice-click seam
    # ------------------------------------------------------------------ #

    def pick_for_slice_event(self, slice_node, display_xy):
        """Resolve a slice-view click to a strictly-interior labelled voxel's RAS.

        With ``display_xy`` set, projects the pixel to RAS on the slice plane
        and snaps to the nearest strictly-interior labelled voxel; with
        ``display_xy`` None (or no slice geometry), returns the region's
        interior centroid.  ``None`` when there is no labelled region.
        """
        seed_ras = None
        if display_xy is not None and slice_node is not None:
            seed_ras = self._xy_to_ras_on_plane(slice_node, display_xy)
        return self._interior_ras(near_ras=seed_ras)

    # ------------------------------------------------------------------ #
    # Interior-voxel resolution
    # ------------------------------------------------------------------ #

    def _interior_ras(self, near_ras=None):
        """The RAS of a strictly-interior labelled voxel, nearest ``near_ras``.

        Scans the labelmap for labelled voxels whose six axis neighbours are
        ALSO labelled (strictly inside, not a boundary face -- ADR-0038
        §"Base extension"), and returns the one whose IJK index is nearest the
        seed index derived from ``near_ras`` (or nearest the labelled bounding-
        box centre when no seed is given).  ``None`` when the region has no
        strictly-interior voxel.
        """
        import vtk

        labelmap = self._labelmap
        if labelmap is None:
            return None
        image = labelmap.GetImageData()
        if image is None:
            return None
        dims = image.GetDimensions()

        # The target seed index: the clicked pixel's voxel, or the labelled
        # bounding-box centre when no pixel is supplied.
        target = None
        if near_ras is not None:
            ras_to_ijk = vtk.vtkMatrix4x4()
            labelmap.GetRASToIJKMatrix(ras_to_ijk)
            ijk = ras_to_ijk.MultiplyPoint([near_ras[0], near_ras[1], near_ras[2], 1.0])
            target = (int(round(ijk[0])), int(round(ijk[1])), int(round(ijk[2])))

        best_index = None
        best_d2 = None
        centre_accum = [0, 0, 0]
        interior_count = 0
        for k in range(1, dims[2] - 1):
            for j in range(1, dims[1] - 1):
                for i in range(1, dims[0] - 1):
                    if image.GetScalarComponentAsDouble(i, j, k, 0) == 0:
                        continue
                    if not self._is_strict_interior(image, i, j, k):
                        continue
                    centre_accum[0] += i
                    centre_accum[1] += j
                    centre_accum[2] += k
                    interior_count += 1
                    if target is not None:
                        d2 = (
                            (i - target[0]) ** 2
                            + (j - target[1]) ** 2
                            + (k - target[2]) ** 2
                        )
                        if best_d2 is None or d2 < best_d2:
                            best_d2 = d2
                            best_index = (i, j, k)
        if interior_count == 0:
            return None

        if best_index is None:
            # No click supplied: use the interior centroid, snapped back to a
            # labelled strictly-interior voxel if the raw centroid missed one.
            centroid = (
                centre_accum[0] // interior_count,
                centre_accum[1] // interior_count,
                centre_accum[2] // interior_count,
            )
            best_index = centroid
            if (
                image.GetScalarComponentAsDouble(*centroid, 0) == 0
                or not self._is_strict_interior(image, *centroid)
            ):
                best_index = self._nearest_interior(image, dims, centroid)
                if best_index is None:
                    return None

        ijk_to_ras = vtk.vtkMatrix4x4()
        labelmap.GetIJKToRASMatrix(ijk_to_ras)
        ras = ijk_to_ras.MultiplyPoint(
            [float(best_index[0]), float(best_index[1]), float(best_index[2]), 1.0]
        )
        return (ras[0], ras[1], ras[2])

    @staticmethod
    def _is_strict_interior(image, i, j, k) -> bool:
        """True iff voxel ``(i, j, k)`` is labelled with all six neighbours labelled."""
        if image.GetScalarComponentAsDouble(i, j, k, 0) == 0:
            return False
        for di, dj, dk in (
            (1, 0, 0),
            (-1, 0, 0),
            (0, 1, 0),
            (0, -1, 0),
            (0, 0, 1),
            (0, 0, -1),
        ):
            if image.GetScalarComponentAsDouble(i + di, j + dj, k + dk, 0) == 0:
                return False
        return True

    def _nearest_interior(self, image, dims, target):
        """The strictly-interior labelled voxel nearest ``target`` (or ``None``)."""
        best_index = None
        best_d2 = None
        for k in range(1, dims[2] - 1):
            for j in range(1, dims[1] - 1):
                for i in range(1, dims[0] - 1):
                    if not self._is_strict_interior(image, i, j, k):
                        continue
                    d2 = (
                        (i - target[0]) ** 2
                        + (j - target[1]) ** 2
                        + (k - target[2]) ** 2
                    )
                    if best_d2 is None or d2 < best_d2:
                        best_d2 = d2
                        best_index = (i, j, k)
        return best_index

    @staticmethod
    def _xy_to_ras_on_plane(slice_node, display_xy):
        """Project a slice-view pixel to RAS on the slice plane (``XYToRAS``)."""
        import vtk

        xy_to_ras = slice_node.GetXYToRAS()
        if xy_to_ras is None:
            return None
        homog = vtk.vtkMatrix4x4()
        homog.DeepCopy(xy_to_ras)
        ras = homog.MultiplyPoint([float(display_xy[0]), float(display_xy[1]), 0.0, 1.0])
        return (ras[0], ras[1], ras[2])

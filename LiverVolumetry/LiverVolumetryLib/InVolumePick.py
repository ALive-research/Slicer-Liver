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
  labelled voxel whose six axis neighbours are all labelled) WITHIN A LOCAL
  NEIGHBOURHOOD of the clicked voxel, so the returned RAS lands on a voxel the
  region-grow can seed.

PERFORMANCE CONTRACT (the interaction runs on the GUI thread): every
resolution is numpy-vectorized over the labelmap scalars -- there is NO
per-voxel Python/VTK-call scan.  A clicked pixel resolves against a bounded
local window (``LOCAL_SEARCH_RADIUS_VOXELS``) around the clicked voxel; only
the no-click centroid path (the 3D generic seam) touches the whole array, and
only through vectorized numpy operations.  A clinical-size CT labelmap
(hundreds of megavoxels) must resolve a click without a perceptible stall.

The base carries NO surface-vs-volume branch (ADR-0038 §"Base extension") -- it
places at whatever world point this provider returns; ``None`` declines the
placement (the click was outside any labelled region, or farther than the
local search radius from any strictly-interior voxel).

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

import numpy as np

#: How far (in voxels, per axis) around the clicked voxel the pick searches
#: for the nearest strictly-interior labelled voxel.  A click farther than
#: this from any interior voxel DECLINES (returns ``None``): snapping to a
#: distant interior voxel would silently seed a region the surgeon did not
#: click, and an unbounded search is what froze the GUI on clinical-size CTs.
LOCAL_SEARCH_RADIUS_VOXELS = 16


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
        and snaps to the nearest strictly-interior labelled voxel within the
        local search radius of the clicked voxel; with ``display_xy`` None (or
        no slice geometry), returns the region's interior centroid.  ``None``
        when there is no reachable labelled interior.
        """
        seed_ras = None
        if display_xy is not None and slice_node is not None:
            seed_ras = self._xy_to_ras_on_plane(slice_node, display_xy)
        return self._interior_ras(near_ras=seed_ras)

    # ------------------------------------------------------------------ #
    # Interior-voxel resolution (numpy-vectorized -- see the module
    # docstring's performance contract)
    # ------------------------------------------------------------------ #

    def _interior_ras(self, near_ras=None):
        """The RAS of a strictly-interior labelled voxel near ``near_ras``.

        A strictly-interior voxel is a labelled voxel whose six axis
        neighbours are ALSO labelled (strictly inside, not a boundary face --
        ADR-0038 §"Base extension").  With ``near_ras`` given, the search is a
        LOCAL neighbourhood test around the clicked voxel (the clicked voxel
        itself when it qualifies, else the nearest interior voxel within
        ``LOCAL_SEARCH_RADIUS_VOXELS``); without it, the interior voxel
        nearest the interior centroid.  ``None`` when nothing qualifies.
        """
        import vtk

        labelmap = self._labelmap
        if labelmap is None:
            return None
        image = labelmap.GetImageData()
        if image is None:
            return None
        labelled = self._labelled_array(image)
        if labelled is None:
            return None

        if near_ras is not None:
            ras_to_ijk = vtk.vtkMatrix4x4()
            labelmap.GetRASToIJKMatrix(ras_to_ijk)
            ijk = ras_to_ijk.MultiplyPoint([near_ras[0], near_ras[1], near_ras[2], 1.0])
            target = (int(round(ijk[0])), int(round(ijk[1])), int(round(ijk[2])))
            best_index = self._nearest_interior_near(labelled, target)
        else:
            best_index = self._interior_centroid(labelled)
        if best_index is None:
            return None

        ijk_to_ras = vtk.vtkMatrix4x4()
        labelmap.GetIJKToRASMatrix(ijk_to_ras)
        ras = ijk_to_ras.MultiplyPoint(
            [float(best_index[0]), float(best_index[1]), float(best_index[2]), 1.0]
        )
        return (ras[0], ras[1], ras[2])

    @staticmethod
    def _labelled_array(image):
        """The image scalars as a boolean labelled mask, indexed ``[k, j, i]``.

        A zero-copy numpy view over the VTK scalars (VTK stores i fastest),
        thresholded to labelled/unlabelled.  ``None`` when the image carries
        no scalars.
        """
        from vtk.util import numpy_support

        scalars = image.GetPointData().GetScalars()
        if scalars is None:
            return None
        dims = image.GetDimensions()
        flat = numpy_support.vtk_to_numpy(scalars)
        if flat.ndim == 2:  # multi-component: the label rides component 0
            flat = flat[:, 0]
        if flat.size != dims[0] * dims[1] * dims[2]:
            return None
        return flat.reshape(dims[2], dims[1], dims[0]) != 0

    @staticmethod
    def _interior_mask(labelled):
        """The strictly-interior mask of ``labelled`` (vectorized 6-neighbour AND).

        Volume-boundary voxels are never strictly interior (no sixth
        neighbour), matching the region-grow's need for a labelled voxel with
        labelled neighbours on all six sides.
        """
        interior = np.zeros_like(labelled)
        interior[1:-1, 1:-1, 1:-1] = (
            labelled[1:-1, 1:-1, 1:-1]
            & labelled[2:, 1:-1, 1:-1]
            & labelled[:-2, 1:-1, 1:-1]
            & labelled[1:-1, 2:, 1:-1]
            & labelled[1:-1, :-2, 1:-1]
            & labelled[1:-1, 1:-1, 2:]
            & labelled[1:-1, 1:-1, :-2]
        )
        return interior

    @classmethod
    def _nearest_interior_near(cls, labelled, target):
        """The strictly-interior voxel ``(i, j, k)`` nearest the clicked ``target``.

        O(1) fast path: the clicked voxel itself when it is strictly interior.
        Otherwise a bounded local window (``LOCAL_SEARCH_RADIUS_VOXELS`` plus a
        one-voxel halo so the neighbour test is exact inside the radius) is
        interior-masked in one vectorized pass and the nearest hit returned.
        ``None`` when no interior voxel lies within the window -- the click is
        declined rather than snapped to a distant region.
        """
        k_dim, j_dim, i_dim = labelled.shape
        i0, j0, k0 = target

        if (
            1 <= i0 < i_dim - 1
            and 1 <= j0 < j_dim - 1
            and 1 <= k0 < k_dim - 1
            and cls._interior_mask(
                labelled[k0 - 1 : k0 + 2, j0 - 1 : j0 + 2, i0 - 1 : i0 + 2]
            )[1, 1, 1]
        ):
            return (i0, j0, k0)

        r = LOCAL_SEARCH_RADIUS_VOXELS + 1  # +1 halo for the neighbour test
        i_lo, i_hi = max(i0 - r, 0), min(i0 + r + 1, i_dim)
        j_lo, j_hi = max(j0 - r, 0), min(j0 + r + 1, j_dim)
        k_lo, k_hi = max(k0 - r, 0), min(k0 + r + 1, k_dim)
        if i_lo >= i_hi or j_lo >= j_hi or k_lo >= k_hi:
            return None  # the click maps entirely outside the volume

        window = labelled[k_lo:k_hi, j_lo:j_hi, i_lo:i_hi]
        hits = np.argwhere(cls._interior_mask(window))  # window-relative (k, j, i)
        if hits.size == 0:
            return None
        absolute = hits + np.array([k_lo, j_lo, i_lo])
        d2 = ((absolute - np.array([k0, j0, i0])) ** 2).sum(axis=1)
        best = absolute[int(np.argmin(d2))]
        return (int(best[2]), int(best[1]), int(best[0]))

    @classmethod
    def _interior_centroid(cls, labelled):
        """The strictly-interior voxel ``(i, j, k)`` nearest the interior centroid.

        The no-click path (the base's generic 3D seam supplies no slice
        pixel): one vectorized interior mask over the whole array, then the
        interior voxel nearest the interior centre of mass.  ``None`` when the
        region has no strictly-interior voxel.
        """
        hits = np.argwhere(cls._interior_mask(labelled))  # (k, j, i)
        if hits.size == 0:
            return None
        centroid = hits.mean(axis=0)
        d2 = ((hits - centroid) ** 2).sum(axis=1)
        best = hits[int(np.argmin(d2))]
        return (int(best[2]), int(best[1]), int(best[0]))

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

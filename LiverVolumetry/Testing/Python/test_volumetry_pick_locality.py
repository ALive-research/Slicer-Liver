# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""The in-volume pick resolves against the CLICKED voxel's neighbourhood.

ADR-0038 §"Base extension" -- performance + locality contract.  The original
interior resolution scanned the WHOLE labelmap voxel-by-voxel in Python (up to
seven wrapped VTK calls per voxel); on a clinical-size CT labelmap (hundreds
of megavoxels) one armed click burned minutes of GUI-thread CPU -- the
application read as frozen.  The pick is now numpy-vectorized and LOCAL:

* a click on a strictly-interior labelled voxel resolves to THAT voxel (O(1)
  neighbourhood test);
* a click on a boundary-face voxel snaps to a nearby interior voxel within
  ``LOCAL_SEARCH_RADIUS_VOXELS`` of the click;
* a click farther than the local radius from any strictly-interior voxel
  DECLINES (``None``) instead of snapping to a distant region;
* the clicked-path resolution stays interactive on a large volume (the
  regression guard for the whole-volume Python scan).

HARNESS: bare ``PythonSlicer -m pytest``.  ``InVolumePick`` reads only
``GetImageData`` + the RAS<->IJK matrices off its bound node, so a plain
Python stub over a ``vtkImageData`` (identity IJK<->RAS) exercises the real
resolution code with no scene and no wrapped MRML node (ADR-0003 / ADR-0027).

References
----------
* ADR-0038 -- §"Base extension: the pick step is swappable (surface vs
  in-volume)".
* ADR-0015 -- the region-grow the interior seed feeds (why the seed must be
  strictly interior).
"""

from __future__ import annotations

import pathlib
import sys
import time

import pytest

vtk = pytest.importorskip("vtk")
np = pytest.importorskip("numpy")

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
for candidate in (
    REPO_ROOT / "LiverVolumetry" / "LiverVolumetryLib",
    REPO_ROOT / "LiverVolumetry",
):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from InVolumePick import LOCAL_SEARCH_RADIUS_VOXELS, InVolumePick  # noqa: E402


class _IdentityLabelmap:
    """A labelmap-node stand-in: image data + identity IJK<->RAS matrices.

    ``InVolumePick`` reads exactly this surface off the bound node, so the
    stub keeps the test bare (no MRML scene) while exercising the real
    resolution code.  Identity matrices make RAS == IJK, so the assertions
    speak voxel indices directly.
    """

    def __init__(self, image) -> None:
        self._image = image

    def GetImageData(self):  # noqa: N802 - VTK-style accessor
        return self._image

    def GetRASToIJKMatrix(self, matrix):  # noqa: N802 - VTK-style accessor
        matrix.Identity()

    def GetIJKToRASMatrix(self, matrix):  # noqa: N802 - VTK-style accessor
        matrix.Identity()


def _labelmap_with_block(dims, block_lo, block_hi, label=3):
    """An identity-geometry labelmap with one solid ``label`` block (inclusive bounds)."""
    from vtk.util import numpy_support

    array = np.zeros((dims[2], dims[1], dims[0]), dtype=np.int16)
    array[
        block_lo[2] : block_hi[2] + 1,
        block_lo[1] : block_hi[1] + 1,
        block_lo[0] : block_hi[0] + 1,
    ] = label
    image = vtk.vtkImageData()
    image.SetDimensions(*dims)
    scalars = numpy_support.numpy_to_vtk(array.ravel(), deep=True)
    image.GetPointData().SetScalars(scalars)
    return _IdentityLabelmap(image)


def test_click_on_a_strictly_interior_voxel_resolves_to_that_voxel():
    """The clicked voxel itself is the seed when it is strictly interior.

    The pick must honour the surgeon's click, not relocate the seed: a click
    on a labelled voxel with six labelled neighbours resolves to EXACTLY that
    voxel (ADR-0038 §"Base extension" -- the neighbourhood test is on the
    clicked voxel).
    """
    labelmap = _labelmap_with_block((20, 20, 20), (6, 6, 6), (14, 14, 14))
    pick = InVolumePick(labelmap)

    world = pick._interior_ras(near_ras=(10.0, 10.0, 10.0))

    assert world == pytest.approx((10.0, 10.0, 10.0)), (
        "a click on a strictly-interior voxel must resolve to the clicked "
        "voxel itself, not a relocated one (ADR-0038 §'Base extension')."
    )


def test_boundary_click_snaps_to_a_nearby_interior_voxel():
    """A boundary-face click snaps to a strictly-interior voxel NEAR the click.

    The 6..14 block's i=6 face voxel is labelled but not strictly interior;
    the snap must land on an interior voxel (all six neighbours labelled)
    within the local search radius of the click -- not the region centroid.
    """
    labelmap = _labelmap_with_block((20, 20, 20), (6, 6, 6), (14, 14, 14))
    pick = InVolumePick(labelmap)

    world = pick._interior_ras(near_ras=(6.0, 10.0, 10.0))

    assert world is not None
    i, j, k = (int(round(c)) for c in world)
    image = labelmap.GetImageData()
    for di, dj, dk in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
        assert image.GetScalarComponentAsDouble(i + di, j + dj, k + dk, 0) != 0, (
            "the snapped seed must be strictly interior (six labelled "
            "neighbours) -- ADR-0038 §'Base extension' / ADR-0015."
        )
    distance = max(abs(i - 6), abs(j - 10), abs(k - 10))
    assert distance <= LOCAL_SEARCH_RADIUS_VOXELS, (
        "the snap must stay within the local search radius of the CLICK -- "
        "not jump to a distant part of the region."
    )


def test_click_far_from_any_interior_voxel_declines():
    """A click beyond the local radius of any interior voxel returns ``None``.

    Snapping a far-away click into the region would silently seed a region
    the surgeon did not click; the base treats ``None`` as a declined
    placement (ADR-0038 §"Base extension").
    """
    dims = (64, 64, 64)
    labelmap = _labelmap_with_block(dims, (40, 40, 40), (50, 50, 50))
    pick = InVolumePick(labelmap)

    world = pick._interior_ras(near_ras=(2.0, 2.0, 2.0))

    assert world is None, (
        "a click farther than LOCAL_SEARCH_RADIUS_VOXELS from any strictly-"
        "interior voxel must DECLINE, not snap across the volume."
    )


def test_clicked_pick_stays_interactive_on_a_large_volume():
    """The clicked-path resolution must not regress to a whole-volume scan.

    On a 256x256x128 labelmap (8.4 megavoxels -- still far smaller than a
    clinical CT) the per-voxel Python scan this replaces took tens of
    seconds; the vectorized local resolution is milliseconds.  The generous
    bound only trips on a reintroduced whole-volume Python loop, not on a
    slow CI machine.
    """
    dims = (256, 256, 128)
    labelmap = _labelmap_with_block(dims, (60, 60, 30), (200, 200, 100))
    pick = InVolumePick(labelmap)

    started = time.monotonic()
    world = pick._interior_ras(near_ras=(61.0, 130.0, 65.0))
    elapsed = time.monotonic() - started

    assert world is not None
    assert elapsed < 5.0, (
        f"clicked-path pick took {elapsed:.1f} s -- the interior resolution "
        "must be a bounded local neighbourhood search, never a per-voxel "
        "Python scan of the whole labelmap (the GUI-thread freeze this pins)."
    )


def test_no_click_centroid_path_still_returns_a_strict_interior_voxel():
    """The no-click path (generic 3D seam) returns a strictly-interior voxel.

    ``pick_for_event`` supplies no slice pixel; the resolution falls back to
    the interior voxel nearest the interior centroid -- still strictly
    interior (the region-grow contract, ADR-0015), and still vectorized.
    """
    labelmap = _labelmap_with_block((20, 20, 20), (6, 6, 6), (14, 14, 14))
    pick = InVolumePick(labelmap)

    world = pick.pick_for_event(renderer=None, eventData=None)

    assert world is not None
    i, j, k = (int(round(c)) for c in world)
    image = labelmap.GetImageData()
    assert image.GetScalarComponentAsDouble(i, j, k, 0) != 0
    for di, dj, dk in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
        assert image.GetScalarComponentAsDouble(i + di, j + dj, k + dk, 0) != 0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

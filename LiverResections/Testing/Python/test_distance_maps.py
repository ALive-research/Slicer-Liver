# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Module-layer invariants for the distance-map computation.

The resection stage's distance-map computation lives in
``LiverResections/LiverResectionsLib/DistanceMaps.py``:
``computeDistanceMaps`` (signed-Maurer distance maps composed across the
tumour / parenchyma / hepatic / portal labels) and its helper
``imageResample`` (SimpleITK ``SignedMaurerDistanceMap`` +
``ResampleImageFilter``).  This test pins that computation's behaviour
on a synthetic labelmap.

It is a Module-layer test per ADR-0008 §2 (MRML scene + pipeline
behaviour; Slicer imported, no Qt widgets, no ``render_interactive``).
Distance maps are pure ITK/numpy on a pushed/pulled volume node, so the
suite runs under a **minimal ``qSlicerApplication``** -- the
wrapper-vs-carrier precedent SlicerLayerDM and trame-slicer use for
MRML-touching system-under-test -- not the full Slicer GUI.

What is pinned
--------------
1. **Output geometry is preserved** when ``downSamplingRate == 1``: the
   composite distance-map volume has the same dimensions, spacing, and
   origin as the input labelmap (the unit-rate path composes the
   per-label signed-Maurer images without resampling).

2. **Signed-distance sign + magnitude at sampled voxels.**  With
   ``squaredDistance=False`` and ``useImageSpacing=True``, a foreground
   voxel reports a **negative** signed distance (inside) and a
   background voxel a **positive** distance equal to the Euclidean gap
   to the nearest foreground voxel in physical (spacing-weighted) units,
   to a tolerance.

3. **``imageResample`` rescales geometry** to a requested voxel count
   while preserving the physical extent (size * spacing).

References
----------
* ADR-0008 §2 -- Module-layer taxonomy (MRML scene + pipeline; Slicer
  imported, no Qt).
* ADR-0023 §"Shell composition (Option H)" -- the no-domain-logic rule
  under which this compute is owned by the resection module, not the
  Liver shell.
* ``LiverResections/LiverResectionsLib/DistanceMaps.py`` -- the module
  under test.
"""

from __future__ import annotations

import math
import pathlib
import sys

import pytest

# --------------------------------------------------------------------------- #
# Repo geometry -- ``DistanceMaps`` lives under the ``<Module>Lib`` install
# convention (same convention as the Representations tree exercised by
# ``Testing/Python/unit/test_distance_spheroid_init_representation.py``).
# This file sits at LiverResections/Testing/Python/, so the repo root is
# three parents up.
# --------------------------------------------------------------------------- #

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
LIB_DIR = REPO_ROOT / "LiverResections" / "LiverResectionsLib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))


# --------------------------------------------------------------------------- #
# Synthetic fixture geometry.
#
# A small anisotropic-spacing labelmap with a single interior foreground
# voxel makes the signed-Maurer output analytically predictable: every
# background voxel's distance is the spacing-weighted Euclidean gap to
# that one foreground voxel.  Anisotropic spacing (so the
# ``useImageSpacing=True`` flag is actually exercised) and a non-zero
# origin (so origin preservation is a meaningful assertion) are both
# deliberate.
# --------------------------------------------------------------------------- #

_DIMS = (7, 7, 7)            # (i, j, k) voxel counts
_SPACING = (1.0, 2.0, 1.5)   # mm; anisotropic on purpose
_ORIGIN = (10.0, -5.0, 3.0)  # mm; non-zero on purpose
_FG_IJK = (3, 3, 3)          # single interior foreground voxel


def _make_labelmap_node():
    """Create a ``vtkMRMLLabelMapVolumeNode`` with one interior foreground voxel.

    Returns the node added to ``slicer.mrmlScene``.  Built with numpy +
    ``slicer.util.updateVolumeFromArray`` so the geometry (dims / spacing
    / origin) is explicit and matches ``_DIMS`` / ``_SPACING`` /
    ``_ORIGIN`` exactly.
    """
    import numpy as np
    import slicer

    node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")

    # numpy array is indexed (k, j, i) -- the Slicer/VTK convention that
    # ``updateVolumeFromArray`` expects.
    arr = np.zeros((_DIMS[2], _DIMS[1], _DIMS[0]), dtype=np.int16)
    arr[_FG_IJK[2], _FG_IJK[1], _FG_IJK[0]] = 1

    slicer.util.updateVolumeFromArray(node, arr)
    node.SetSpacing(*_SPACING)
    node.SetOrigin(*_ORIGIN)
    return node


def _expected_distance_at(ijk):
    """Spacing-weighted Euclidean distance from ``ijk`` to the lone foreground voxel.

    Mirrors the ``SignedMaurerDistanceMap(..., useImageSpacing=True)``
    contract: background voxels carry the positive physical distance to
    the nearest foreground voxel.
    """
    return math.sqrt(
        ((ijk[0] - _FG_IJK[0]) * _SPACING[0]) ** 2
        + ((ijk[1] - _FG_IJK[1]) * _SPACING[1]) ** 2
        + ((ijk[2] - _FG_IJK[2]) * _SPACING[2]) ** 2
    )


# --------------------------------------------------------------------------- #
# Tolerances -- the signed-Maurer transform is exact in physical units for
# isolated foreground voxels, so the magnitude check is tight; a hair of
# slack absorbs any float32 round-trip through the volume node.
# --------------------------------------------------------------------------- #

_ATOL_DISTANCE = 1e-3


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def distance_maps_module():
    """Import ``DistanceMaps``, skipping cleanly when its deps are absent.

    Skips (rather than errors) when Slicer, SimpleITK, or the
    ``DistanceMaps`` module itself is unavailable, so the suite is a
    no-op on a build that lacks the resection module's Python lib.
    """
    pytest.importorskip(
        "slicer",
        reason=(
            "distance-map compute is Module-layer (ADR-0008 §2); "
            "requires a minimal qSlicerApplication / Slicer Python."
        ),
    )
    pytest.importorskip(
        "SimpleITK",
        reason="computeDistanceMaps uses SimpleITK SignedMaurerDistanceMap.",
    )
    return pytest.importorskip(
        "DistanceMaps",
        reason=(
            "LiverResections/LiverResectionsLib/DistanceMaps.py "
            "not importable in this build."
        ),
    )


@pytest.fixture
def mrml_scene_guard():
    """Clear the MRML scene before and after each test.

    Keeps the synthetic labelmap and any pushed output volume from
    leaking across tests when several run in the same launched Slicer.
    """
    slicer = pytest.importorskip("slicer")
    if getattr(slicer, "mrmlScene", None) is None:
        pytest.skip(
            "requires a launched Slicer with an initialized MRML scene; "
            "bare PythonSlicer pytest has no qSlicerApplication, so "
            "scene-dependent distance-map tests run only under the "
            "launched-Slicer pytest harness."
        )
    slicer.mrmlScene.Clear(0)
    yield slicer.mrmlScene
    slicer.mrmlScene.Clear(0)


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #

def test_compute_distance_maps_preserves_output_geometry(
    distance_maps_module, mrml_scene_guard
):
    """Unit-rate distance maps preserve input dims / spacing / origin.

    With ``downSamplingRate == 1`` ``computeDistanceMaps`` composes the
    per-label signed-Maurer images without resampling, so the output
    volume node must report the same dimensions, spacing, and origin as
    the input labelmap.
    """
    import slicer

    label = _make_labelmap_node()
    output = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLVectorVolumeNode")

    distance_maps_module.computeDistanceMaps(
        tumorNode=label,
        parenchymaNode=None,
        hepaticNode=None,
        portalNode=None,
        outputNode=output,
        downSamplingRate=1,
    )

    image = output.GetImageData()
    assert image is not None, "computeDistanceMaps produced no image data"
    assert tuple(image.GetDimensions()) == _DIMS, (
        f"output dims {tuple(image.GetDimensions())} != input dims {_DIMS}"
    )

    out_spacing = output.GetSpacing()
    out_origin = output.GetOrigin()
    for axis in range(3):
        assert out_spacing[axis] == pytest.approx(_SPACING[axis], abs=1e-6), (
            f"spacing axis {axis}: {out_spacing[axis]} != {_SPACING[axis]}"
        )
        assert out_origin[axis] == pytest.approx(_ORIGIN[axis], abs=1e-6), (
            f"origin axis {axis}: {out_origin[axis]} != {_ORIGIN[axis]}"
        )


def test_compute_distance_maps_signed_distance_values(
    distance_maps_module, mrml_scene_guard
):
    """Signed-Maurer sign + magnitude at sampled voxels.

    With ``squaredDistance=False`` and ``useImageSpacing=True`` (the third
    and fourth args to ``SignedMaurerDistanceMap``):

    * the lone foreground voxel reports a non-positive (inside) distance;
    * background voxels report the positive spacing-weighted Euclidean
      gap to that foreground voxel.

    Sampled at a few voxels spanning the axis-aligned and diagonal
    directions so a regression in the distance kernel or in the
    spacing-weighting is visible.
    """
    import numpy as np
    import slicer

    label = _make_labelmap_node()
    output = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLVectorVolumeNode")

    distance_maps_module.computeDistanceMaps(
        tumorNode=label,
        parenchymaNode=None,
        hepaticNode=None,
        portalNode=None,
        outputNode=output,
        downSamplingRate=1,
    )

    # Single tumor channel -> one-component vector volume; pull as
    # (k, j, i[, comp]) numpy and squeeze the trailing component axis.
    dist = slicer.util.arrayFromVolume(output)
    dist = np.asarray(dist, dtype=np.float64)
    if dist.ndim == 4:
        dist = dist[..., 0]

    def sample(ijk):
        return dist[ijk[2], ijk[1], ijk[0]]

    # Foreground voxel: inside the object -> non-positive signed distance.
    assert sample(_FG_IJK) <= 0.0 + _ATOL_DISTANCE, (
        f"foreground voxel reported positive distance {sample(_FG_IJK)}; "
        "expected non-positive (inside)"
    )

    # Background voxels: positive spacing-weighted Euclidean gap.
    for ijk in [(4, 3, 3), (3, 5, 3), (3, 3, 5), (5, 5, 5)]:
        expected = _expected_distance_at(ijk)
        got = sample(ijk)
        assert got == pytest.approx(expected, abs=_ATOL_DISTANCE), (
            f"voxel {ijk}: signed distance {got} != expected {expected}"
        )


def test_image_resample_rescales_geometry(distance_maps_module):
    """``imageResample`` returns a new image at the requested voxel count.

    Exercises the helper directly on a SimpleITK image (no MRML needed):
    a down-sample to a smaller size must preserve the physical extent
    (size * spacing) while changing the per-axis spacing accordingly.
    Pinned independently of ``computeDistanceMaps`` so a regression in
    either is caught.
    """
    import SimpleITK as sitk

    img = sitk.Image(8, 8, 8, sitk.sitkFloat32)
    img.SetSpacing((2.0, 2.0, 2.0))
    img.SetOrigin((0.0, 0.0, 0.0))

    resampled = distance_maps_module.imageResample(img, [4, 4, 4], "linear")

    assert tuple(resampled.GetSize()) == (4, 4, 4)
    # Physical extent (size * spacing) is preserved: 8 * 2.0 == 4 * 4.0.
    for axis in range(3):
        in_extent = img.GetSize()[axis] * img.GetSpacing()[axis]
        out_extent = resampled.GetSize()[axis] * resampled.GetSpacing()[axis]
        assert out_extent == pytest.approx(in_extent, abs=1e-6), (
            f"axis {axis}: extent {out_extent} != input extent {in_extent}"
        )

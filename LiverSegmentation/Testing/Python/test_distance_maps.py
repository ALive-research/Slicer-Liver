# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Invariants for the Stage-2 distance-map computation (issue #538).

Ports the v1 distance-map algorithm into the v2 Anatomy stage: per anatomical
channel (tumour / parenchyma / hepatic / portal) a signed Maurer distance map,
composed into one multi-component volume the resection mappers consume.

These pin the PURE SimpleITK core (``LiverSegmentationLib.distance_maps``),
which needs no Slicer scene -- the Slicer-coupled segment-export + node wiring
is exercised separately in the launched harness.  Skips cleanly when SimpleITK
or NumPy are unavailable.
"""

from __future__ import annotations

import pytest


def _deps_or_skip():
    try:
        import numpy as np  # type: ignore[import-not-found]
        import SimpleITK as sitk  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - env-dependent
        pytest.skip(f"SimpleITK / NumPy unavailable ({exc}).")
    return np, sitk


def _cube_labelmap(np, sitk, size=20, half=4):
    """A binary labelmap with a solid cube of 1s centred in a size^3 volume."""
    arr = np.zeros((size, size, size), dtype=np.uint8)
    c = size // 2
    arr[c - half:c + half, c - half:c + half, c - half:c + half] = 1
    return sitk.GetImageFromArray(arr)


def test_signed_distance_is_negative_inside_positive_outside():
    """Signed Maurer map: inside the label < 0, outside > 0 (v1 flag parity)."""
    np, sitk = _deps_or_skip()
    from LiverSegmentationLib.distance_maps import signed_distance_map

    d = signed_distance_map(_cube_labelmap(np, sitk))
    arr = sitk.GetArrayFromImage(d)
    c = arr.shape[0] // 2
    assert arr[c, c, c] < 0.0, "voxel inside the label must have negative distance"
    assert arr[0, 0, 0] > 0.0, "voxel outside the label must have positive distance"


def test_compose_yields_one_component_per_present_channel():
    """Only the present (non-None) channels compose, in order."""
    np, sitk = _deps_or_skip()
    from LiverSegmentationLib.distance_maps import compose_distance_map

    a = _cube_labelmap(np, sitk)
    b = _cube_labelmap(np, sitk)
    composed = compose_distance_map([a, None, b, None])
    assert composed is not None
    assert composed.GetNumberOfComponentsPerPixel() == 2


def test_compose_returns_none_when_no_channels_present():
    """No channels -> nothing to compose (caller treats as a no-op)."""
    _np, _sitk = _deps_or_skip()
    from LiverSegmentationLib.distance_maps import compose_distance_map

    assert compose_distance_map([None, None, None, None]) is None

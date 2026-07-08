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
    try:
        # LiverSegmentationLib is on the path in the launched harness + when the
        # module dir is staged; the bare CTest row runs from the source root
        # without it, so skip cleanly there (mirrors test_case_setup_volume_roles).
        from LiverSegmentationLib import distance_maps  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - bare-row path
        pytest.skip(
            f"LiverSegmentationLib not importable ({exc}) -- bare pytest row "
            "lacks the module path; runs under the launched harness."
        )
    return np, sitk, distance_maps


def _cube_labelmap(np, sitk, size=20, half=4):
    """A binary labelmap with a solid cube of 1s centred in a size^3 volume."""
    arr = np.zeros((size, size, size), dtype=np.uint8)
    c = size // 2
    arr[c - half:c + half, c - half:c + half, c - half:c + half] = 1
    return sitk.GetImageFromArray(arr)


def test_signed_distance_is_negative_inside_positive_outside():
    """Signed Maurer map: inside the label < 0, outside > 0 (v1 flag parity)."""
    np, sitk, distance_maps = _deps_or_skip()

    d = distance_maps.signed_distance_map(_cube_labelmap(np, sitk))
    arr = sitk.GetArrayFromImage(d)
    c = arr.shape[0] // 2
    assert arr[c, c, c] < 0.0, "voxel inside the label must have negative distance"
    assert arr[0, 0, 0] > 0.0, "voxel outside the label must have positive distance"


def test_compose_yields_one_component_per_present_channel():
    """Only the present (non-None) channels compose, in order."""
    np, sitk, distance_maps = _deps_or_skip()

    a = _cube_labelmap(np, sitk)
    b = _cube_labelmap(np, sitk)
    composed = distance_maps.compose_distance_map([a, None, b, None])
    assert composed is not None
    assert composed.GetNumberOfComponentsPerPixel() == 2


def test_compose_returns_none_when_no_channels_present():
    """No channels -> nothing to compose (caller treats as a no-op)."""
    _np, _sitk, distance_maps = _deps_or_skip()

    assert distance_maps.compose_distance_map([None, None, None, None]) is None

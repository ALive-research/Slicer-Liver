# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""territory-usability -- the carved-region marching-stripes highlight (pure core).

While a seed's row is selected, its effective (carved) region is overlaid in
the 2D slices with slowly marching diagonal stripes (bars moving/filling --
never an opacity blink).  This file pins the PURE pieces (bare, numpy only --
ADR-0027):

* ``stripe_segments`` -- diagonal stripes ``x + y ≡ phase (mod period)``
  clipped to the 2D mask's True runs; advancing the phase translates the
  family (the march); an empty mask yields nothing.
* ``resample_mask_to_plane`` -- the once-per-(seed, slice) 3D->2D cut; the
  per-tick work is stripe_segments alone.
* the ``highlightSeed`` / ``stripePhase`` display-node attribute helpers the
  widget timer and the slice pipelines share
  (``feedback_layerdm_state_on_display_node``).
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np

_LIB = pathlib.Path(__file__).resolve().parents[2] / "LiverVolumetryLib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from CarvedRegionStripes import (  # noqa: E402
    get_highlight_seed,
    get_stripe_phase,
    resample_mask_to_plane,
    set_highlight_seed,
    set_stripe_phase,
    stripe_segments,
)


# --------------------------------------------------------------------------- #
# stripe_segments
# --------------------------------------------------------------------------- #


def test_stripes_lie_on_the_phase_diagonals():
    """Every emitted segment lies on an anti-diagonal ``x+y ≡ phase (mod p)``."""
    mask = np.ones((16, 16), dtype=bool)
    for phase in (0, 3, 7):
        for (x0, y0), (x1, y1) in stripe_segments(mask, period=4, phase=phase):
            assert (x0 + y0) % 4 == phase % 4
            assert (x0 + y0) == (x1 + y1), "a stripe is one anti-diagonal."


def test_phase_translates_the_stripe_family():
    """Advancing the phase yields a DIFFERENT diagonal family (the march)."""
    mask = np.ones((16, 16), dtype=bool)
    at0 = {seg[0][0] + seg[0][1] for seg in stripe_segments(mask, 4, 0)}
    at1 = {seg[0][0] + seg[0][1] for seg in stripe_segments(mask, 4, 1)}
    assert at0 and at1 and at0.isdisjoint(at1)


def test_phase_wraps_modulo_period():
    mask = np.ones((8, 8), dtype=bool)
    assert stripe_segments(mask, 4, 5) == stripe_segments(mask, 4, 1)


def test_stripes_are_clipped_to_the_mask():
    """A masked-out gap splits a stripe into separate runs; nothing is drawn
    outside the region."""
    mask = np.zeros((8, 8), dtype=bool)
    # One anti-diagonal (x+y == 4) with a hole at its middle pixel.
    for x in range(5):
        mask[4 - x, x] = True
    mask[2, 2] = False

    segments = stripe_segments(mask, period=8, phase=4)

    assert len(segments) == 2, "a hole must split the stripe run."
    for (x0, y0), (x1, y1) in segments:
        for x, y in ((x0, y0), (x1, y1)):
            assert mask[int(y), int(x)], "endpoints stay inside the mask."


def test_empty_mask_yields_no_stripes():
    assert stripe_segments(np.zeros((8, 8), dtype=bool), 4, 0) == []


def test_degenerate_period_yields_no_stripes():
    assert stripe_segments(np.ones((4, 4), dtype=bool), 0, 0) == []


# --------------------------------------------------------------------------- #
# resample_mask_to_plane
# --------------------------------------------------------------------------- #


def test_identity_plane_extracts_the_k0_slice():
    """With XY == (i, j) and k == 0, the cut is exactly ``mask[0]``."""
    mask = np.zeros((2, 4, 4), dtype=bool)
    mask[0, 1, 2] = True  # k=0, j=1, i=2
    mask[1, 3, 3] = True  # a different k -- must NOT leak into the cut
    xy_to_ijk = np.eye(4)  # x->i, y->j, plane at k=0

    cut = resample_mask_to_plane(mask, xy_to_ijk, width=4, height=4)

    assert cut.shape == (4, 4)
    assert cut[1, 2], "the k=0 voxel must appear at (x=2, y=1)."
    assert cut.sum() == 1


def test_out_of_bounds_pixels_are_false():
    """A plane larger than the volume pads with False (no wraparound)."""
    mask = np.ones((1, 2, 2), dtype=bool)
    xy_to_ijk = np.eye(4)

    cut = resample_mask_to_plane(mask, xy_to_ijk, width=5, height=5)

    assert cut[:2, :2].all()
    assert not cut[2:, :].any() and not cut[:, 2:].any()


def test_offset_plane_samples_the_translated_voxels():
    """A translation in the affine shifts the sampled window."""
    mask = np.zeros((1, 4, 4), dtype=bool)
    mask[0, 3, 3] = True
    xy_to_ijk = np.eye(4)
    xy_to_ijk[0, 3] = 3.0  # i = x + 3
    xy_to_ijk[1, 3] = 3.0  # j = y + 3

    cut = resample_mask_to_plane(mask, xy_to_ijk, width=4, height=4)

    assert cut[0, 0]
    assert cut.sum() == 1


# --------------------------------------------------------------------------- #
# Highlight state helpers (the widget<->pipeline display-node channel)
# --------------------------------------------------------------------------- #


class _FakeDisplayNode:
    def __init__(self):
        self._attrs: dict = {}

    def SetAttribute(self, key, value):  # noqa: N802 - MRML verb
        self._attrs[key] = value

    def GetAttribute(self, key):  # noqa: N802 - MRML verb
        return self._attrs.get(key)


def test_highlight_seed_round_trips_and_defaults_off():
    display = _FakeDisplayNode()
    assert get_highlight_seed(display) == -1, "default is no highlight."

    set_highlight_seed(display, 3)
    assert get_highlight_seed(display) == 3

    set_highlight_seed(display, -1)
    assert get_highlight_seed(display) == -1


def test_stripe_phase_round_trips_and_defaults_zero():
    display = _FakeDisplayNode()
    assert get_stripe_phase(display) == 0

    set_stripe_phase(display, 7)
    assert get_stripe_phase(display) == 7


def test_state_helpers_tolerate_a_missing_display_node():
    set_highlight_seed(None, 1)
    set_stripe_phase(None, 1)
    assert get_highlight_seed(None) == -1
    assert get_stripe_phase(None) == 0

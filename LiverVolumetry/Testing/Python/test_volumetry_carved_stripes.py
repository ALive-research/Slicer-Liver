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
* the ``HighlightSeedID`` transient-member helpers + the ``STRIPE_TICK_EVENT``
  InvokeEvent tick the widget timer and the slice pipelines share
  (``feedback_layerdm_state_on_display_node``; NEVER a node attribute --
  attributes serialize into the scene XML) + the legacy-attribute sanitation.
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np

_LIB = pathlib.Path(__file__).resolve().parents[2] / "LiverVolumetryLib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from CarvedRegionStripes import (  # noqa: E402
    STRIPE_TICK_EVENT,
    clear_legacy_highlight_attributes,
    get_highlight_seed_id,
    invoke_stripe_tick,
    resample_mask_to_plane,
    set_highlight_seed_id,
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
    """Mimics the display node's transient member + attribute + event API,
    recording every write so the tests can pin WHICH channel was used."""

    def __init__(self):
        self._highlight = ""
        self._attrs: dict = {}
        self.attribute_writes: list = []
        self.invoked_events: list = []

    # -- the transient HighlightSeedID member (never serialized) ---------- #
    def SetHighlightSeedID(self, seedID):  # noqa: N802 - MRML verb
        self._highlight = seedID

    def GetHighlightSeedID(self):  # noqa: N802 - MRML verb
        return self._highlight

    # -- the generic (SERIALIZING) attribute channel ---------------------- #
    def SetAttribute(self, key, value):  # noqa: N802 - MRML verb
        self._attrs[key] = value
        self.attribute_writes.append((key, value))

    def GetAttribute(self, key):  # noqa: N802 - MRML verb
        return self._attrs.get(key)

    def RemoveAttribute(self, key):  # noqa: N802 - MRML verb
        self._attrs.pop(key, None)

    # -- events ------------------------------------------------------------ #
    def InvokeEvent(self, eventId):  # noqa: N802 - VTK verb
        self.invoked_events.append(eventId)


def test_highlight_seed_id_round_trips_and_defaults_off():
    display = _FakeDisplayNode()
    assert get_highlight_seed_id(display) == "", "default is no highlight."

    set_highlight_seed_id(display, "seed_3")
    assert get_highlight_seed_id(display) == "seed_3"

    set_highlight_seed_id(display, "")
    assert get_highlight_seed_id(display) == "", "empty clears."

    set_highlight_seed_id(display, None)
    assert get_highlight_seed_id(display) == "", "None clears too."


def test_highlight_helpers_never_touch_the_attribute_channel():
    """The highlight rides the TRANSIENT member ONLY: ``SetAttribute`` values
    serialize into the scene XML, which is exactly the frozen-orphan-stripes
    bug the member fixes."""
    display = _FakeDisplayNode()

    set_highlight_seed_id(display, "seed_3")
    get_highlight_seed_id(display)

    assert display.attribute_writes == [], (
        "the highlight helpers must NEVER write a node attribute -- "
        "attributes persist into the scene XML."
    )


def test_stripe_tick_fires_the_custom_event_with_no_mrml_write():
    """The march tick is an InvokeEvent (no serialization, no Modified) --
    the SegmentEditorThresholdEffect zero-MRML-writes-per-tick precedent."""
    display = _FakeDisplayNode()

    invoke_stripe_tick(display)
    invoke_stripe_tick(display)

    assert display.invoked_events == [STRIPE_TICK_EVENT, STRIPE_TICK_EVENT]
    assert display.attribute_writes == [], (
        "the per-tick path must carry ZERO attribute writes (no stripePhase "
        "channel remains)."
    )


def test_state_helpers_tolerate_a_missing_display_node():
    set_highlight_seed_id(None, "seed_1")
    invoke_stripe_tick(None)
    assert get_highlight_seed_id(None) == ""
    assert clear_legacy_highlight_attributes(None) is False


def test_legacy_highlight_attributes_are_scrubbed():
    """Sanitation removes BOTH retired attributes and leaves others alone."""
    display = _FakeDisplayNode()
    display.SetAttribute("LiverVolumetry.highlightSeed", "2")
    display.SetAttribute("LiverVolumetry.stripePhase", "7")
    display.SetAttribute("LiverVolumetry.Armed", "1")  # unrelated: must stay

    assert clear_legacy_highlight_attributes(display) is True

    assert display.GetAttribute("LiverVolumetry.highlightSeed") is None
    assert display.GetAttribute("LiverVolumetry.stripePhase") is None
    assert display.GetAttribute("LiverVolumetry.Armed") == "1"
    assert clear_legacy_highlight_attributes(display) is False, (
        "a second pass finds nothing (idempotent)."
    )


# --------------------------------------------------------------------------- #
# Conformance pin: the attribute channel must not creep back in
# --------------------------------------------------------------------------- #


def test_no_attribute_borne_highlight_channel_remains_in_the_module():
    """No LiverVolumetry source writes the retired highlight/phase attributes.

    Grep-level pin: the ONLY residence of the legacy attribute names is the
    sanitation constants in ``CarvedRegionStripes`` itself.  A re-appearance
    anywhere else means the serializing channel crept back.
    """
    module_root = _LIB.parent
    offenders = []
    for source in sorted(module_root.rglob("*.py")):
        if "Testing" in source.parts or source.name == "CarvedRegionStripes.py":
            continue
        text = source.read_text(encoding="utf-8")
        if "LiverVolumetry.highlightSeed" in text or "LiverVolumetry.stripePhase" in text:
            offenders.append(str(source.relative_to(module_root)))
    assert offenders == [], (
        f"the attribute-borne highlight channel crept back into: {offenders}"
    )

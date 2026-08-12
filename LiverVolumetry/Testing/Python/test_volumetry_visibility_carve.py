# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""territory-usability -- the visibility-composed carve rule (pure core).

Visibility COMPOSES the region a volumetry seed measures: the surgeon sets
segment show/hide BEFORE placing, and a dropped seed's EFFECTIVE region is the
VISIBLE segment that owns the clicked voxel (top visible layer wins) MINUS
every visible segment stacked ABOVE it anywhere -- visible layers CARVE each
other, top-visible owns each voxel.

This file pins the PURE core (bare-testable, no scene -- ADR-0027):

* ``segments_above`` -- given the seed's ordered visibility context (top-first)
  and its owning segment, the carving set is the context PREFIX before the
  owner (everything drawn above it).
* ``carve_effective_mask`` -- the effective region is the owner's mask minus
  the union of the carving masks (plain boolean array algebra).

The canonical phantom case is mimicked on synthetic arrays: a 216-voxel
parenchyma block with a 54-voxel sub-segment carves to 162 voxels -- the
216-54=162 mL acceptance number scaled to unit voxels.  The scene-side
gathering (``visible_context``) is exercised against the phantom on :0.
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np

_LIB = pathlib.Path(__file__).resolve().parents[2] / "LiverVolumetryLib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from VisibilityCarve import (  # noqa: E402
    apply_visibility_context,
    carve_effective_mask,
    order_visible_top_first,
    segments_above,
)


# --------------------------------------------------------------------------- #
# segments_above -- the carving set is the context prefix before the owner
# --------------------------------------------------------------------------- #


def test_segments_above_is_the_prefix_before_the_owner():
    """With context [Tumor, Segment_2, Parenchyma] (top-first), a seed owned by
    Segment_2 is carved by Tumor alone."""
    context = ["Tumor", "Segment_2", "Parenchyma"]
    assert segments_above(context, "Segment_2") == ["Tumor"]


def test_top_owner_is_carved_by_nothing():
    context = ["Tumor", "Segment_2", "Parenchyma"]
    assert segments_above(context, "Tumor") == []


def test_bottom_owner_is_carved_by_everything_above():
    context = ["Segment_1", "Parenchyma"]
    assert segments_above(context, "Parenchyma") == ["Segment_1"]


def test_owner_not_in_context_carves_nothing():
    """A retarget outside the snapshot (or a legacy empty context) falls back
    to the whole owning segment -- no carve, never a crash."""
    assert segments_above(["A", "B"], "C") == []
    assert segments_above([], "A") == []


# --------------------------------------------------------------------------- #
# carve_effective_mask -- owner minus the union of the visible-above masks
# --------------------------------------------------------------------------- #


def _phantom_like_masks():
    """Synthetic masks mimicking the phantom's parenchyma + one sub-segment.

    A 6x6x6 parenchyma block (216 voxels == the 216 mL parenchyma at unit
    voxels) with a 3x3x6 sub-segment (54 voxels == the 54 mL Segment_1).
    """
    parenchyma = np.zeros((8, 8, 8), dtype=bool)
    parenchyma[1:7, 1:7, 1:7] = True
    segment_1 = np.zeros((8, 8, 8), dtype=bool)
    segment_1[1:7, 1:4, 1:4] = True
    assert int(parenchyma.sum()) == 216
    assert int(segment_1.sum()) == 54
    return parenchyma, segment_1


def test_carve_subtracts_the_visible_above_segment():
    """Parenchyma (216) with Segment_1 (54) visible above carves to 162 -- the
    216-54=162 mL phantom acceptance case at unit voxels."""
    parenchyma, segment_1 = _phantom_like_masks()

    carved = carve_effective_mask(parenchyma, [segment_1])

    assert int(carved.sum()) == 162
    # The carve is a strict subset of the owner and disjoint from the carver.
    assert not (carved & segment_1).any()
    assert (carved <= parenchyma).all()


def test_carve_with_no_above_is_the_whole_owner():
    parenchyma, _segment_1 = _phantom_like_masks()
    carved = carve_effective_mask(parenchyma, [])
    assert int(carved.sum()) == 216


def test_carve_subtracts_the_union_of_all_above():
    """A fully covered owner carves to ZERO -- the parenchyma-covered-by-all-
    sub-segments case measures nothing."""
    parenchyma, _ = _phantom_like_masks()
    left = np.zeros_like(parenchyma)
    left[1:7, 1:7, 1:4] = True
    right = np.zeros_like(parenchyma)
    right[1:7, 1:7, 4:7] = True

    carved = carve_effective_mask(parenchyma, [left, right])

    assert int(carved.sum()) == 0


def test_carve_does_not_mutate_the_inputs():
    parenchyma, segment_1 = _phantom_like_masks()
    before = parenchyma.copy()
    carve_effective_mask(parenchyma, [segment_1])
    assert (parenchyma == before).all()


def test_partial_overlap_subtracts_only_the_intersection():
    """A carver overlapping the owner only partly removes just the overlap --
    the Segment_2-with-Tumor-visible shape (54 - |tumor∩seg2|)."""
    segment_2 = np.zeros((8, 8, 8), dtype=bool)
    segment_2[1:7, 1:4, 1:4] = True  # 54 voxels
    tumor = np.zeros((8, 8, 8), dtype=bool)
    tumor[1:3, 2:4, 2:4] = True  # 8 voxels, 8 inside segment_2
    tumor[7, 7, 7] = True  # +1 voxel OUTSIDE the owner

    carved = carve_effective_mask(segment_2, [tumor])

    assert int(carved.sum()) == 54 - 8


# --------------------------------------------------------------------------- #
# order_visible_top_first -- the context snapshot ordering
# --------------------------------------------------------------------------- #


def test_order_visible_top_first_sorts_by_descending_layer():
    """The snapshot orders visible segments top-first (highest layer leads),
    stable within a layer -- the same comparator the touched-candidate rule
    uses, so owner-vs-above stays consistent."""
    visible = [("Parenchyma", 0), ("Segment_2", 1), ("Tumor", 2)]
    assert order_visible_top_first(visible) == ["Tumor", "Segment_2", "Parenchyma"]


def test_order_visible_top_first_keeps_input_order_within_a_layer():
    visible = [("Segment_2", 1), ("Segment_3", 1), ("Parenchyma", 0)]
    assert order_visible_top_first(visible) == ["Segment_2", "Segment_3", "Parenchyma"]


def test_order_visible_top_first_empty():
    assert order_visible_top_first([]) == []


# --------------------------------------------------------------------------- #
# apply_visibility_context -- restore-on-select writes visible-iff-in-context
# --------------------------------------------------------------------------- #


class _FakeSegmentationDisplay:
    def __init__(self):
        self.visibility: dict[str, bool] = {}

    def SetSegmentVisibility(self, segmentID, visible):  # noqa: N802 - MRML verb
        self.visibility[segmentID] = bool(visible)


def test_apply_visibility_context_shows_exactly_the_context():
    """Selecting a seed row restores the visibility state to its snapshot:
    every context segment shown, every other segment hidden."""
    display = _FakeSegmentationDisplay()
    all_ids = ["Parenchyma", "Segment_1", "Segment_2", "Tumor"]

    apply_visibility_context(display, all_ids, ["Segment_1", "Parenchyma"])

    assert display.visibility == {
        "Parenchyma": True,
        "Segment_1": True,
        "Segment_2": False,
        "Tumor": False,
    }


def test_apply_visibility_context_with_empty_context_is_a_no_op():
    """A legacy seed with no snapshot must not blank the view."""
    display = _FakeSegmentationDisplay()
    apply_visibility_context(display, ["A", "B"], [])
    assert display.visibility == {}


def test_apply_visibility_context_tolerates_a_missing_display():
    apply_visibility_context(None, ["A"], ["A"])  # must not raise


# --------------------------------------------------------------------------- #
# carved_mask_for_seed -- the shared owner-minus-above fold over an injected
# mask reader (the table's empty-carve cue + the slice pipeline share it)
# --------------------------------------------------------------------------- #


class _FakeSeedCarrier:
    """A seed carrier stub exposing the binding + snapshot readers."""

    def __init__(self, owner: str, context: list[str]):
        self._owner = owner
        self._context = context

    def GetNthSeedBindingSegmentID(self, index):  # noqa: N802 - MRML verb
        return self._owner

    def GetNthSeedVisibilityContext(self, index, ids):  # noqa: N802 - MRML verb
        for segmentID in self._context:
            ids.InsertNextValue(segmentID)


def _mask_reader(masks: dict):
    """A mask-for-segment reader over a dict (None for unknown segments)."""
    return lambda segmentID: masks.get(segmentID)


def test_carved_mask_for_seed_is_owner_minus_the_context_above():
    from VisibilityCarve import carved_mask_for_seed

    owner = np.zeros((4, 4), dtype=bool)
    owner[1:3, 1:3] = True  # 4 voxels
    above = np.zeros((4, 4), dtype=bool)
    above[1, 1:3] = True  # covers 2 of them
    carrier = _FakeSeedCarrier("Parenchyma", ["Segment_1", "Parenchyma"])

    carved = carved_mask_for_seed(
        carrier, 0, _mask_reader({"Parenchyma": owner, "Segment_1": above})
    )

    assert carved is not None and int(carved.sum()) == 2


def test_fully_covered_owner_carves_to_an_EMPTY_mask_not_none():
    """The silent-nothing case the empty-carve cue must name: the owner is
    fully covered by the snapshot segments above it -- the carve exists and
    is EMPTY (distinct from the unknown/None cases below)."""
    from VisibilityCarve import carved_mask_for_seed

    owner = np.ones((3, 3), dtype=bool)
    cover = np.ones((3, 3), dtype=bool)
    carrier = _FakeSeedCarrier("Parenchyma", ["Tumor", "Parenchyma"])

    carved = carved_mask_for_seed(
        carrier, 0, _mask_reader({"Parenchyma": owner, "Tumor": cover})
    )

    assert carved is not None and not carved.any()


def test_unbound_seed_yields_none_not_an_empty_mask():
    """Unbound is UNKNOWN, not empty: the cue must not claim full coverage."""
    from VisibilityCarve import carved_mask_for_seed

    carrier = _FakeSeedCarrier("", ["A"])
    assert carved_mask_for_seed(carrier, 0, _mask_reader({})) is None


def test_owner_without_a_mask_yields_none():
    from VisibilityCarve import carved_mask_for_seed

    carrier = _FakeSeedCarrier("Parenchyma", ["Parenchyma"])
    assert carved_mask_for_seed(carrier, 0, _mask_reader({})) is None


def test_missing_above_mask_carves_nothing_for_that_segment():
    """A context segment whose labelmap cannot be read carves nothing --
    best-effort degradation, never a crash."""
    from VisibilityCarve import carved_mask_for_seed

    owner = np.ones((2, 2), dtype=bool)
    carrier = _FakeSeedCarrier("Parenchyma", ["Gone", "Parenchyma"])

    carved = carved_mask_for_seed(carrier, 0, _mask_reader({"Parenchyma": owner}))

    assert carved is not None and int(carved.sum()) == 4


def test_missing_carrier_yields_none():
    from VisibilityCarve import carved_mask_for_seed

    assert carved_mask_for_seed(None, 0, _mask_reader({})) is None

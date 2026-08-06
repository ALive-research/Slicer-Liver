# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""``territory-usability`` §"Seed→label capture" -- the candidate-resolution rule.

When a volumetry seed is dropped in a 2D slice, the touched-candidate set is
every VISIBLE segment whose binary labelmap covers the clicked voxel, and the
DEFAULT binding is the top layer's segment among them (highest
``GetLayerIndex`` == drawn on top).  ``resolve_touched_candidates`` is the pure
function that expresses that rule over an already-gathered
(segmentID, layerIndex) membership list, so it is BARE-testable with no scene,
no wrapped node, and no GUI (ADR-0027).

The membership gathering itself (reading each visible segment's binary
labelmap value at the click IJK) is exercised against the phantom on :0; this
file pins the ORDERING + top-selection rule the gathering feeds.
"""

from __future__ import annotations

import pathlib
import sys

_LIB = pathlib.Path(__file__).resolve().parents[2] / "LiverVolumetryLib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from SeedTargetResolution import resolve_touched_candidates  # noqa: E402


def test_top_is_highest_layer_index():
    """The default binding is the touched segment on the highest layer.

    Phantom at the tumour centre: Parenchyma(L0), Segment_3(L1), Tumor(L2)
    are all touched; the default is Tumor (top layer).
    """
    touched = [("Parenchyma", 0), ("Segment_3", 1), ("Tumor", 2)]
    candidates, top = resolve_touched_candidates(touched)

    assert top == "Tumor"
    # Candidates ordered top-first so the retarget menu reads top -> bottom.
    assert candidates == ["Tumor", "Segment_3", "Parenchyma"]


def test_single_candidate_is_its_own_top():
    touched = [("Parenchyma", 0)]
    candidates, top = resolve_touched_candidates(touched)
    assert top == "Parenchyma"
    assert candidates == ["Parenchyma"]


def test_no_touched_segments_yields_no_binding():
    """A click off every region resolves no candidates and no default."""
    candidates, top = resolve_touched_candidates([])
    assert candidates == []
    assert top is None


def test_ties_break_deterministically_by_input_order():
    """Two touched segments on the SAME layer keep input order among the tie.

    Overlapping segments can share a layer (the phantom's Segment_1..4 all sit
    on layer 1); the top is still well-defined (first-seen on the max layer) so
    the default never flickers between runs.
    """
    touched = [("Segment_2", 1), ("Segment_3", 1), ("Parenchyma", 0)]
    candidates, top = resolve_touched_candidates(touched)
    assert top == "Segment_2"
    # Higher layer first; within a layer, input order preserved.
    assert candidates == ["Segment_2", "Segment_3", "Parenchyma"]

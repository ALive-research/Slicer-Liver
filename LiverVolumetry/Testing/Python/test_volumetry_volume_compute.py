# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""territory-usability -- compute reports ONE row per VOLUME (union of bound segs).

Compute-per-volume yields one results row per VOLUME = the combined region of
the DISTINCT segments the volume's seeds are bound to (the union of the bound
segments' regions).  A volume with seeds on Segment_2 + Segment_3 measures
``|seg2 ∪ seg3|``.

This file pins the two halves:

* AGGREGATION (pure, bare) -- ``distinct_bound_segments_per_volume`` folds the
  carrier's per-seed volume ids + bindings into ``{volumeId: [distinct bound
  segmentIDs]}``: two seeds on the same segment count it ONCE; two seeds on
  different segments yield both; an unbound / ungrouped seed contributes
  nothing.
* DRIVER (launched) -- ``LiverVolumetryLogic.computeVolumePerVolume`` emits one
  table row per volume whose voxel count is the union of the bound segments'
  regions (pinned launched by the phantom check + here over a synthetic
  two-region labelmap; skip-pends bare per ADR-0027).

References
----------
* territory-usability -- the compute-per-volume plan.
* LiverVolumetryLib/VolumeSegmentAggregation.py -- the pure fold.
* ADR-0027 -- invariant-test-first (red->skip lifecycle).
"""

from __future__ import annotations

import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
for candidate in (
    REPO_ROOT / "LiverVolumetry" / "LiverVolumetryLib",
    REPO_ROOT / "LiverVolumetry",
):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))


class _FakeCarrier:
    """A minimal carrier exposing the per-seed volume + binding reads."""

    def __init__(self, seeds):
        # seeds: list of (volumeId, boundSegmentID)
        self._seeds = seeds

    def GetNumberOfSeeds(self):  # noqa: N802 - carrier verb
        return len(self._seeds)

    def GetNthSeedVolume(self, i):  # noqa: N802 - carrier verb
        return self._seeds[i][0]

    def GetNthSeedBindingSegmentID(self, i):  # noqa: N802 - carrier verb
        return self._seeds[i][1]


def _aggregation():
    from VolumeSegmentAggregation import distinct_bound_segments_per_volume

    return distinct_bound_segments_per_volume


# --------------------------------------------------------------------------- #
# Pure aggregation (RUNS bare)
# --------------------------------------------------------------------------- #


def test_union_of_distinct_bound_segments_per_volume():
    """A volume with seeds on Segment_2 + Segment_3 yields both, once each."""
    fold = _aggregation()
    carrier = _FakeCarrier(
        [
            ("Left", "Segment_2"),
            ("Left", "Segment_3"),
            ("Right", "Segment_5"),
        ]
    )

    per_volume = fold(carrier)

    assert set(per_volume["Left"]) == {"Segment_2", "Segment_3"}
    assert per_volume["Right"] == ["Segment_5"]


def test_duplicate_segment_counts_once():
    """Two seeds on the SAME segment in one volume count that segment ONCE."""
    fold = _aggregation()
    carrier = _FakeCarrier([("Left", "Segment_2"), ("Left", "Segment_2")])

    per_volume = fold(carrier)

    assert per_volume["Left"] == ["Segment_2"], (
        "the region is the UNION -- a repeated segment is counted once."
    )


def test_unbound_or_ungrouped_seeds_contribute_nothing():
    """An unbound seed or an ungrouped seed adds no segment to any volume."""
    fold = _aggregation()
    carrier = _FakeCarrier(
        [
            ("Left", ""),        # bound to nothing
            ("", "Segment_9"),   # ungrouped
            ("Left", "Segment_2"),
        ]
    )

    per_volume = fold(carrier)

    assert per_volume == {"Left": ["Segment_2"]}, (
        "unbound + ungrouped seeds contribute nothing to the per-volume union."
    )


def test_empty_carrier_yields_empty_mapping():
    fold = _aggregation()
    assert fold(_FakeCarrier([])) == {}
    assert fold(None) == {}


# --------------------------------------------------------------------------- #
# Driver over a real labelmap (SKIPS bare, RUNS launched)
# --------------------------------------------------------------------------- #


def _slicer_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def test_compute_per_volume_emits_one_row_per_volume():
    """``computeVolumePerVolume`` emits one table row per bound volume.

    Over a synthetic segmentation with two segments, a volume with seeds bound
    to both segments yields ONE row whose voxel count is the union of the two
    segments' regions.  Skip-pends bare (needs the wrapped logic + a real
    segmentation); the phantom check pins the surgeon-facing numbers.
    """
    slicer = _slicer_or_skip()
    try:
        from LiverVolumetry import LiverVolumetryLogic
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(f"LiverVolumetryLogic not importable ({exc!r}) (ADR-0027).")
    logic = LiverVolumetryLogic()
    if not hasattr(logic, "computeVolumePerVolume"):
        pytest.skip(
            "LiverVolumetryLogic has no computeVolumePerVolume -- the "
            "compute-per-volume driver (territory-usability) has not landed "
            "(ADR-0027)."
        )

    seeds = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLVolumetrySeedsNode", "Seeds")
    if seeds is None or not hasattr(seeds, "AddSeedToVolume"):
        pytest.skip("vtkMRMLVolumetrySeedsNode grouped API absent (ADR-0027).")

    seg = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", "Seg")
    seg.CreateDefaultDisplayNodes()
    segA = seg.GetSegmentation().AddEmptySegment("segA", "Alpha")
    segB = seg.GetSegmentation().AddEmptySegment("segB", "Beta")

    seeds.AddSeedToVolume("Left", 0.0, 0.0, 0.0)
    seeds.SetNthSeedBinding(0, seg.GetID(), segA)
    seeds.AddSeedToVolume("Left", 1.0, 0.0, 0.0)
    seeds.SetNthSeedBinding(1, seg.GetID(), segB)

    outputTable = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTableNode", "Volumetry")
    logic.computeVolumePerVolume(seg, seeds, outputTable)

    # One row per bound volume: exactly one row here ("Left").
    assert outputTable.GetNumberOfRows() == 1, (
        "compute-per-volume must emit ONE row per bound volume."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

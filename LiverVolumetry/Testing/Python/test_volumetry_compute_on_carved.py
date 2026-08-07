# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""territory-usability -- Compute measures the seeds' CARVED regions.

A volume's results row is the UNION of its seeds' EFFECTIVE regions: each
seed's owning segment minus the snapshot segments stacked above it
(``VisibilityCarve``), re-derived from the seed's placement-time visibility
context.  Phantom acceptance (verified on :0): with Parenchyma + Segment_1
visible, a seed in Parenchyma outside Segment_1 measures 216-54 = 162 mL;
a seed inside Segment_2 with Tumor visible measures 54 - |tumor∩seg2| ≈
50.64 mL.

This file pins:

* the PURE carve-aware fold ``effective_regions_per_volume`` -- distinct
  (owner, snapshot) pairs per volume, first-seen order, legacy empty snapshot
  -- BARE over fakes (ADR-0027);
* the LAUNCHED driver ``computeVolumePerVolume`` over a real segmentation --
  the carved union numbers land in the results table (SKIPS bare, RUNS
  launched).
"""

from __future__ import annotations

import pathlib
import sys

import pytest

_LIB = pathlib.Path(__file__).resolve().parents[2] / "LiverVolumetryLib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from VolumeSegmentAggregation import effective_regions_per_volume  # noqa: E402

SEEDS_NODE_CLASS = "vtkMRMLVolumetrySeedsNode"


# --------------------------------------------------------------------------- #
# The pure carve-aware fold (bare)
# --------------------------------------------------------------------------- #


class _FakeCarrier:
    """Seeds as (volumeId, ownerSegmentID, context list) triples."""

    def __init__(self, seeds):
        self._seeds = seeds

    def GetNumberOfSeeds(self):  # noqa: N802 - carrier verb
        return len(self._seeds)

    def GetNthSeedVolume(self, i):  # noqa: N802 - carrier verb
        return self._seeds[i][0]

    def GetNthSeedBindingSegmentID(self, i):  # noqa: N802 - carrier verb
        return self._seeds[i][1]

    def GetNthSeedVisibilityContext(self, i, ids):  # noqa: N802 - carrier verb
        ids.Reset()
        for segmentID in self._seeds[i][2]:
            ids.InsertNextValue(segmentID)


def test_fold_pairs_owner_with_its_snapshot():
    carrier = _FakeCarrier([("V1", "Parenchyma", ["Segment_1", "Parenchyma"])])

    per = effective_regions_per_volume(carrier)

    assert per == {"V1": [("Parenchyma", ("Segment_1", "Parenchyma"))]}


def test_fold_keeps_distinct_owner_snapshot_pairs_once():
    """Two seeds with the same owner + the same snapshot count ONCE; the same
    owner under a DIFFERENT snapshot counts separately (it carves differently)."""
    carrier = _FakeCarrier(
        [
            ("V1", "Parenchyma", ["Segment_1", "Parenchyma"]),
            ("V1", "Parenchyma", ["Segment_1", "Parenchyma"]),  # duplicate
            ("V1", "Parenchyma", ["Parenchyma"]),  # same owner, other snapshot
        ]
    )

    per = effective_regions_per_volume(carrier)

    assert per["V1"] == [
        ("Parenchyma", ("Segment_1", "Parenchyma")),
        ("Parenchyma", ("Parenchyma",)),
    ]


def test_fold_skips_unbound_and_ungrouped_seeds():
    carrier = _FakeCarrier(
        [
            ("", "Parenchyma", ["Parenchyma"]),  # ungrouped
            ("V1", "", ["Parenchyma"]),  # unbound
        ]
    )
    assert effective_regions_per_volume(carrier) == {}


def test_fold_handles_a_legacy_carrier_without_the_context_slot():
    """A carrier predating the snapshot slot folds with empty contexts."""

    class _LegacyCarrier:
        def GetNumberOfSeeds(self):  # noqa: N802
            return 1

        def GetNthSeedVolume(self, i):  # noqa: N802
            return "V1"

        def GetNthSeedBindingSegmentID(self, i):  # noqa: N802
            return "Segment_2"

    per = effective_regions_per_volume(_LegacyCarrier())
    assert per == {"V1": [("Segment_2", ())]}


def test_fold_of_no_carrier_is_empty():
    assert effective_regions_per_volume(None) == {}


# --------------------------------------------------------------------------- #
# The launched driver: carved unions land in the results table
# --------------------------------------------------------------------------- #


def _slicer_or_skip():
    from conftest import _import_slicer_or_skip, _require_mrml_scene

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _make_logic_or_skip():
    try:
        from LiverVolumetry import LiverVolumetryLogic
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(f"LiverVolumetryLogic not importable ({exc!r}).")
    return LiverVolumetryLogic()


def _make_carrier_or_skip(slicer, name="CarvedComputeCarrierTest"):
    node = slicer.mrmlScene.AddNewNodeByClass(SEEDS_NODE_CLASS, name)
    if node is None:
        pytest.skip(f"{SEEDS_NODE_CLASS} not registered (launched build; ADR-0027).")
    if not hasattr(node, "SetNthSeedVisibilityContext"):
        pytest.skip(f"{SEEDS_NODE_CLASS} has no visibility-context slot (ADR-0027).")
    return node


def _make_layered_segmentation(slicer):
    """A parenchyma-like block with a sub-segment on a HIGHER layer.

    Outer segment: 6x6x6 mm at 1 mm spacing (216 voxels == 216 mL at unit
    scale x0.001); inner segment: 3x3x6 (54 voxels) fully inside the outer --
    the phantom's Parenchyma/Segment_1 shape at unit voxels.
    """
    import numpy as np

    segmentation = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLSegmentationNode", "CarvedComputeSegSrc")
    segmentation.CreateDefaultDisplayNodes()

    def _add_segment_from_array(array, name):
        labelmap = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
        slicer.util.updateVolumeFromArray(labelmap, array.astype(np.uint8))
        ok = slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(
            labelmap, segmentation)
        slicer.mrmlScene.RemoveNode(labelmap)
        assert ok
        seg = segmentation.GetSegmentation()
        segmentID = seg.GetNthSegmentID(seg.GetNumberOfSegments() - 1)
        seg.GetSegment(segmentID).SetName(name)
        return segmentID

    outer = np.zeros((8, 8, 8), dtype=np.uint8)
    outer[1:7, 1:7, 1:7] = 1
    inner = np.zeros((8, 8, 8), dtype=np.uint8)
    inner[1:7, 1:4, 1:4] = 1
    outerID = _add_segment_from_array(outer, "Outer")
    innerID = _add_segment_from_array(inner, "Inner")
    return segmentation, outerID, innerID


def _set_context(carrier, index, context):
    import vtk

    ids = vtk.vtkStringArray()
    for segmentID in context:
        ids.InsertNextValue(segmentID)
    carrier.SetNthSeedVisibilityContext(index, ids)


def _column_values(table, name):
    column = None
    for c in range(table.GetNumberOfColumns()):
        if table.GetColumnName(c) == name:
            column = c
            break
    assert column is not None, f"the results table must carry a '{name}' column."
    return [table.GetCellText(r, column) for r in range(table.GetNumberOfRows())]


def test_compute_measures_the_carved_region():
    """A seed owned by Outer with Inner visible above measures 216-54 = 162
    unit-voxels, never the whole 216 (the phantom acceptance shape)."""
    slicer = _slicer_or_skip()
    logic = _make_logic_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    segmentation, outerID, innerID = _make_layered_segmentation(slicer)

    carrier.AddVolume("V1")
    index = carrier.AddSeedToVolume("V1", 5.0, 5.0, 4.0)
    carrier.SetNthSeedBinding(index, segmentation.GetID(), outerID)
    _set_context(carrier, index, [innerID, outerID])

    table = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTableNode", "CarvedComputeTable")
    logic.computeVolumePerVolume(segmentation, carrier, table)

    # One row per bound volume + the trailing explicit Total row (the %
    # denominator made visible, territory-usability).
    assert table.GetNumberOfRows() == 2
    volumes = _column_values(table, "Volume (mL)")
    assert float(volumes[0]) == pytest.approx(162 * 0.001, rel=1e-3), (
        "the row must measure the CARVED region (owner minus visible-above), "
        "not the whole owning segment."
    )
    regions = _column_values(table, "Region")
    assert regions[-1] == f"Total ({segmentation.GetName()})", (
        "the run must end with a Total row NAMING the % denominator (the "
        "whole segmentation on the per-volume path)."
    )
    assert float(volumes[-1]) == pytest.approx(216 * 0.001, rel=1e-3), (
        "the Total row must carry the denominator's own mL (the whole "
        "segmentation region -- Inner lies inside Outer, so 216 unit voxels)."
    )
    percents = _column_values(table, "% of total")
    assert percents[-1].startswith("100"), "the Total row reads 100% of itself."


def test_compute_without_a_snapshot_measures_the_whole_owner():
    """A legacy seed (no snapshot) keeps the whole-bound-segment semantics."""
    slicer = _slicer_or_skip()
    logic = _make_logic_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    segmentation, outerID, _innerID = _make_layered_segmentation(slicer)

    carrier.AddVolume("V1")
    index = carrier.AddSeedToVolume("V1", 5.0, 5.0, 4.0)
    carrier.SetNthSeedBinding(index, segmentation.GetID(), outerID)

    table = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTableNode", "CarvedComputeTable2")
    logic.computeVolumePerVolume(segmentation, carrier, table)

    volumes = _column_values(table, "Volume (mL)")
    assert float(volumes[0]) == pytest.approx(216 * 0.001, rel=1e-3)
    # The trailing explicit Total row is present on this path too.
    regions = _column_values(table, "Region")
    assert regions[-1] == f"Total ({segmentation.GetName()})"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""ADR-0038 (amendment) -- the seed port PRESERVES the volumetry compute.

``volumetry-seeds-layerdm-plan.md`` §3c: the C++ ``vtkLiverVolumetryLogic``
signatures stay unchanged (ADR-0015); the seeds-off-markups migration feeds
them a TRANSIENT ``vtkMRMLMarkupsFiducialNode`` built from the seed carrier.
The invariant that makes the port safe: feeding the logic a transient
fiducial built from the carrier must produce the SAME volumetry table +
segment NAMES as the old ``ROIMarkersList`` fiducial path.

The critical fidelity is the per-seed LABEL -> segment NAME round-trip:
``computeVolume`` reads ``ROIMarkersList.GetNthControlPointLabel(i)`` to
name each table row, and ``generateSegments`` reads
``GetNthFiducialLabel(i)`` to name generated segment ``i``.  If the transient
fiducial drops or reorders labels, the port silently mis-names segments
(``volumetry-seeds-layerdm-plan.md`` §8 -- LABEL fidelity risk).

This file pins the port-preserves-compute invariant by comparing TWO
computes over the SAME geometry + labels:

* a MARKUPS-fed compute (the legacy ``ROIMarkersList`` path -- the
  behaviour-preserving baseline);
* a CARRIER-fed compute (the new path: build the transient fiducial from a
  ``vtkMRMLVolumetrySeedsNode`` and feed the unchanged logic).

The two must produce byte-identical volumetry tables (same row order, same
segment names, same voxel counts / volumes).

HARNESS: launched Slicer.  This drives the wrapped C++
``vtkLiverVolumetryLogic`` (reached via ``LiverVolumetryLogic().scl`` --
imported from ``vtkSlicerLiverVolumetryModuleLogicPython``, NOT plain
``vtk`` / ``slicer``, per the wrapped-class-namespace rule) over a real
labelmap volume + fiducial + table nodes.  A bare
``PythonSlicer -m pytest`` has ``slicer.mrmlScene is None`` so it SKIPS
CLEANLY.

The carrier + the transient-fiducial adapter do not exist yet.  Per
ADR-0027 red->skip the guards skip-pend; the skips lift at the
implementation commit.

References
----------
* ADR-0038 -- §Conformance ([review] "LiverVolumetry's C++ region-grow
  logic is unchanged (ADR-0015); it is fed a transient fiducial built from
  the seed carrier, and per-seed labels round-trip so generated segments
  keep their names").
* ADR-0015 -- the C++ region-grow logic is unchanged (port, not rewrite).
* ADR-0027 -- invariant-test-first (red->skip lifecycle).
* LiverVolumetry/LiverVolumetry.py -- computeVolume / generateSegments (the
  label -> segment-name reads this preserves).
* LiverVolumetry/Logic/vtkLiverVolumetryLogic.h -- GetROIPointsLabelValue /
  VolumetryTable / GenerateSegmentsLabelMap (the fed C++ surface).
"""

from __future__ import annotations

import pathlib
import sys

import pytest

vtk = pytest.importorskip("vtk")

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
for candidate in (
    REPO_ROOT / "LiverVolumetry" / "LiverVolumetryLib",
    REPO_ROOT / "LiverVolumetry",
):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

SEEDS_NODE_CLASS = "vtkMRMLVolumetrySeedsNode"


def _slicer_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _cpp_logic_or_skip():
    """The wrapped C++ ``vtkLiverVolumetryLogic`` (via LiverVolumetryLogic.scl).

    Resolved through the module's wrapped-logic Python module, NOT plain
    ``vtk`` / ``slicer`` (the wrapped-class-namespace rule).
    """
    try:
        from vtkSlicerLiverVolumetryModuleLogicPython import vtkLiverVolumetryLogic
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"vtkLiverVolumetryLogic not importable ({exc!r}) -- the wrapped "
            "LiverVolumetry logic is off the path (needs a launched build)."
        )
    return vtkLiverVolumetryLogic()


def _import_transient_adapter_or_skip():
    """Import the carrier->transient-fiducial adapter, or skip-pend (ADR-0027).

    PROPOSED seam (sharpen at landing): a thin Logic wrapper that builds a
    transient ``vtkMRMLMarkupsFiducialNode`` in the given scene from a
    ``vtkMRMLVolumetrySeedsNode`` (positions + per-seed labels as control
    point labels), returning the node the caller feeds + later removes::

        def build_transient_fiducial(scene, seeds_node) -> markups_node: ...
    """
    try:
        from TransientVolumetrySeeds import build_transient_fiducial
    except ImportError:
        pytest.skip(
            "build_transient_fiducial not importable -- the carrier->transient-"
            "fiducial adapter (plan §3c) has not landed (ADR-0027)."
        )
    return build_transient_fiducial


def _labelmap_two_regions_or_skip(slicer):
    """A labelmap with two labelled regions (values 3 and 5) in a zero field.

    Two interior points -- one in each region -- give two distinct table
    rows so the label->row mapping is observable.
    """
    node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", "Regions")
    if node is None:
        pytest.skip("vtkMRMLLabelMapVolumeNode not registrable (launched build).")
    image = vtk.vtkImageData()
    image.SetDimensions(20, 20, 20)
    image.SetSpacing(1.0, 1.0, 1.0)
    image.AllocateScalars(vtk.VTK_SHORT, 1)
    scalars = image.GetPointData().GetScalars()
    scalars.Fill(0)
    for k in range(20):
        for j in range(20):
            for i in range(20):
                idx = i + 20 * (j + 20 * k)
                if i < 10:
                    scalars.SetTuple1(idx, 3)
                else:
                    scalars.SetTuple1(idx, 5)
    image.Modified()
    node.SetAndObserveImageData(image)
    return node


# The two seeds' geometry + labels, shared by both the markups path and the
# carrier path so the ONLY difference under test is the feed mechanism.
_SEEDS = [
    ((5.0, 10.0, 10.0), "LeftRegion"),   # inside the value-3 region
    ((15.0, 10.0, 10.0), "RightRegion"),  # inside the value-5 region
]


def _markups_fiducial(slicer):
    node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "ROIMarkersList")
    for (x, y, z), label in _SEEDS:
        idx = node.AddControlPoint(vtk.vtkVector3d(x, y, z))
        node.SetNthControlPointLabel(idx, label)
    return node


def _carrier(slicer):
    node = slicer.mrmlScene.AddNewNodeByClass(SEEDS_NODE_CLASS, "Seeds")
    if node is None or not hasattr(node, "AddSeed"):
        pytest.skip(
            f"{SEEDS_NODE_CLASS} / AddSeed not available -- the seed carrier "
            "has not landed (ADR-0027)."
        )
    for (x, y, z), label in _SEEDS:
        idx = node.AddSeed(x, y, z)
        node.SetNthSeedLabel(idx, label)
    return node


def _label_values(cpp_logic, labelmap, fiducial):
    """The per-seed label VALUES the compute reads (GetROIPointsLabelValue)."""
    if not hasattr(cpp_logic, "GetROIPointsLabelValue"):
        pytest.skip("vtkLiverVolumetryLogic has no GetROIPointsLabelValue.")
    return list(cpp_logic.GetROIPointsLabelValue(labelmap, fiducial))


def test_carrier_fed_label_values_match_markups_path():
    """GetROIPointsLabelValue over the transient fiducial == over ROIMarkersList.

    The C++ maps each seed to the labelmap value at its voxel; feeding a
    transient fiducial built from the carrier must return the SAME per-seed
    label values (same positions -> same voxels) as the legacy markups
    node.  This is the geometry half of the port-preserves-compute
    invariant (ADR-0038 §Conformance / ADR-0015).
    """
    slicer = _slicer_or_skip()
    cpp_logic = _cpp_logic_or_skip()
    build_transient = _import_transient_adapter_or_skip()
    labelmap = _labelmap_two_regions_or_skip(slicer)

    markups = _markups_fiducial(slicer)
    baseline = _label_values(cpp_logic, labelmap, markups)

    carrier = _carrier(slicer)
    transient = build_transient(slicer.mrmlScene, carrier)
    ported = _label_values(cpp_logic, labelmap, transient)

    assert ported == baseline, (
        "the carrier-fed transient fiducial must map to the SAME per-seed "
        "label values as ROIMarkersList (ADR-0038 §Conformance / ADR-0015)."
    )


def test_carrier_fed_segment_names_match_seed_labels_in_order():
    """The transient fiducial's control-point labels == the seed labels, in order.

    ``generateSegments`` names generated segment ``i`` from
    ``GetNthFiducialLabel(i)``; the transient fiducial must expose the
    carrier's per-seed labels in placement order so the port names segments
    identically to the markups path.  This is the segment-NAME half of the
    port-preserves-compute invariant -- the ADR-0038 §Conformance "per-seed
    labels round-trip so generated segments keep their names".
    """
    slicer = _slicer_or_skip()
    _cpp_logic_or_skip()
    build_transient = _import_transient_adapter_or_skip()

    carrier = _carrier(slicer)
    transient = build_transient(slicer.mrmlScene, carrier)

    expected = [label for _pos, label in _SEEDS]
    n = transient.GetNumberOfControlPoints()
    assert n == len(expected), "the transient fiducial must carry every seed."
    got = [transient.GetNthControlPointLabel(i) for i in range(n)]
    assert got == expected, (
        "the transient fiducial's control-point labels must equal the seed "
        "labels IN ORDER (segment-name fidelity, ADR-0038 §Conformance)."
    )


def test_volumetry_table_rows_match_between_paths():
    """The populated volumetry table is identical between the two feed paths.

    End-to-end: running the module ``LiverVolumetryLogic.computeVolume`` with
    the markups path vs the carrier path (transient fiducial) yields the SAME
    table -- same row order, same segment-name column, same voxel counts /
    volumes.  This is the top-level port-preserves-compute invariant.

    TODO(implementer): once ``computeVolume`` accepts a carrier (or an
    already-built transient fiducial), drive both paths over the same
    labelmap + table and compare the table cell-by-cell.  Kept as an
    explicit skip until ``computeVolume``'s carrier entry point lands so the
    comparison target is unambiguous.
    """
    _slicer_or_skip()
    _cpp_logic_or_skip()
    pytest.skip(
        "computeVolume's carrier entry point has not landed -- the "
        "table-level comparison target is not yet defined (ADR-0038 "
        "§Conformance; ADR-0027 red->skip).  test_carrier_fed_label_values_"
        "match_markups_path + test_carrier_fed_segment_names_match_seed_labels_"
        "in_order pin the two halves this rolls up."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

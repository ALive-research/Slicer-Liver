# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Results-table presentation invariants (data-first redesign §3.5).

The volumetry results table is renamed to surgeon terms
(``Docs/design/volumetry-data-first-redesign.md`` §3.5):

* columns become ``Region | Volume (mL) | % of total`` -- the engineer-unit
  ``ROI Voxels`` column is dropped and the units read mL, not cm3;
* the ``% of total`` cell guards divide-by-zero (a zero denominator yields a
  safe placeholder, never ``inf`` / ``nan`` / a raised exception);
* the per-run total row is labeled ``All pieces`` -- never the transient
  fiducial node's name (the old ``"TotalVolume of List <node>"`` leak).

These touch ONLY the presentation strings inside ``VolumetryTable`` (the
column names, the % guard) and the Python total-row label -- the C++
algorithm signatures are unchanged (ADR-0015).  They land test-first
(ADR-0027).

HARNESS: launched Slicer.  This drives the wrapped C++
``vtkLiverVolumetryLogic.VolumetryTable`` (imported from
``vtkSlicerLiverVolumetryModuleLogicPython``, NOT plain ``vtk`` / ``slicer``,
per the wrapped-class-namespace rule) over a real ``vtkMRMLTableNode``.  A
bare ``PythonSlicer -m pytest`` has ``slicer.mrmlScene is None`` so it SKIPS
CLEANLY.

See also:
  * Docs/design/volumetry-data-first-redesign.md  (§3.5 behaviour polish, §6
    terminology)
  * LiverVolumetry/Logic/vtkLiverVolumetryLogic.cxx  (VolumetryTable)
  * Docs/adr/0015-*.md  (C++ logic signatures unchanged)
  * Docs/adr/0027-invariant-test-first.md  (RED / skip-pending discipline)
"""

from __future__ import annotations

import pytest

vtk = pytest.importorskip("vtk")

_REGION_COL = "Region"
_VOLUME_COL = "Volume (mL)"
_PERCENT_COL = "% of total"
_ALL_PIECES = "All pieces"


def _slicer_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _cpp_logic_or_skip():
    try:
        from vtkSlicerLiverVolumetryModuleLogicPython import vtkLiverVolumetryLogic
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"vtkLiverVolumetryLogic not importable ({exc!r}) -- the wrapped "
            "LiverVolumetry logic is off the path (needs a launched build)."
        )
    return vtkLiverVolumetryLogic()


def _column_names(tableNode):
    table = tableNode.GetTable()
    return [table.GetColumn(i).GetName() for i in range(table.GetNumberOfColumns())]


def test_result_columns_are_surgeon_terms(qt_widgets=None):
    """§3.5: columns are Region | Volume (mL) | % of total; no ROI Voxels.

    ``VolumetryTable`` seeds the columns on the first row.  The header set
    must be exactly the surgeon-facing names -- the engineer-unit voxel
    column is gone.  Launched; SKIPS bare.
    """
    slicer = _slicer_or_skip()
    logic = _cpp_logic_or_skip()

    tableNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTableNode", "PresentationTable")
    # VolumetryTable(Properties, TargetSegmentationVolume, ROIVoxels, ROIVolume, table)
    logic.VolumetryTable("Segment 1", 100.0, 4200, 42.0, tableNode)

    names = _column_names(tableNode)
    assert _REGION_COL in names, "the region/label column must read 'Region' (§3.5)."
    assert _VOLUME_COL in names, "the volume column must read 'Volume (mL)' (§3.5)."
    assert _PERCENT_COL in names, "the percentage column must read '% of total' (§3.5)."
    assert not any("Voxel" in n for n in names), (
        "the engineer-unit 'ROI Voxels' column must be dropped (§3.5)."
    )
    assert not any("cm3" in n for n in names), (
        "the volume column must read mL, not cm3 (§6 terminology)."
    )


def test_percent_guards_divide_by_zero():
    """§3.5: a zero denominator never yields inf / nan / an exception.

    With ``TargetSegmentationVolume == 0`` the ``% of total`` cell must hold a
    safe placeholder, not ``inf%`` / ``nan%`` / a raised divide.  Launched;
    SKIPS bare.
    """
    slicer = _slicer_or_skip()
    logic = _cpp_logic_or_skip()

    tableNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTableNode", "ZeroDenomTable")
    logic.VolumetryTable("Segment 1", 0.0, 4200, 42.0, tableNode)

    table = tableNode.GetTable()
    names = _column_names(tableNode)
    percentIndex = names.index(_PERCENT_COL)
    cell = str(table.GetColumn(percentIndex).GetValue(0))
    assert "inf" not in cell.lower(), "the % cell must not read inf on a zero denominator."
    assert "nan" not in cell.lower(), "the % cell must not read nan on a zero denominator."


def test_total_row_label_is_all_pieces():
    """§3.5: the per-run partition total row is labeled 'All pieces'.

    The Python compute path names the partition total row; it must read
    ``All pieces``, never the transient fiducial node's name (the old
    ``TotalVolume of List <node>`` leak).  This pins the module-level label
    constant the Python compute path uses.  Launched; SKIPS bare.
    """
    _slicer_or_skip()
    import LiverVolumetry

    assert getattr(LiverVolumetry, "PARTITION_TOTAL_LABEL", None) == _ALL_PIECES, (
        "the partition total row must be labeled 'All pieces' via the module "
        "constant PARTITION_TOTAL_LABEL (§3.5)."
    )


def test_total_row_names_the_selected_segments_denominator():
    """territory-usability: the classic compute ends with an explicit Total row.

    The ``% of total`` denominator used to be implicit (the rasterized input
    selection).  Every ``computeVolume`` run must now END with a Total row
    NAMING that definition -- ``Total (selected segments)`` -- carrying the
    denominator's own mL and 100%, so the surgeon can see what the
    percentages are measured against.  The denominator semantics are
    unchanged.  Launched; SKIPS bare.
    """
    slicer = _slicer_or_skip()
    _cpp_logic_or_skip()  # the module logic wraps the same C++ class
    try:
        from LiverVolumetry import LiverVolumetryLogic, TOTAL_SELECTED_SEGMENTS_LABEL
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(f"LiverVolumetryLogic not importable ({exc!r}).")

    assert TOTAL_SELECTED_SEGMENTS_LABEL == "Total (selected segments)", (
        "the Total row label must NAME the denominator definition."
    )

    # A 20^3 unit-spacing labelmap: value 3 in one half, 5 in the other --
    # 8000 nonzero voxels == 8 mL denominator; one seed in the value-3 half
    # measures 4000 voxels == 4 mL (50%).
    labelmap = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", "TotalRowRegions")
    image = vtk.vtkImageData()
    image.SetDimensions(20, 20, 20)
    image.SetSpacing(1.0, 1.0, 1.0)
    image.AllocateScalars(vtk.VTK_SHORT, 1)
    scalars = image.GetPointData().GetScalars()
    for k in range(20):
        for j in range(20):
            for i in range(20):
                scalars.SetTuple1(i + 20 * (j + 20 * k), 3 if i < 10 else 5)
    image.Modified()
    labelmap.SetAndObserveImageData(image)

    carrier = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLVolumetrySeedsNode", "TotalRowSeeds")
    if carrier is None or not hasattr(carrier, "AddSeed"):
        pytest.skip("vtkMRMLVolumetrySeedsNode not registered (launched build).")
    index = carrier.AddSeed(5.0, 10.0, 10.0)
    carrier.SetNthSeedLabel(index, "LeftRegion")

    table = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTableNode", "TotalRowTable")
    logic = LiverVolumetryLogic()
    logic.computeVolume(labelmap, labelmap, None, table, carrier, None)

    names = _column_names(tableNode=table)
    regionIndex = names.index(_REGION_COL)
    volumeIndex = names.index(_VOLUME_COL)
    percentIndex = names.index(_PERCENT_COL)
    grid = table.GetTable()
    lastRow = table.GetNumberOfRows() - 1
    assert lastRow >= 1, "the seed row + the Total row must both be present."
    assert str(grid.GetColumn(regionIndex).GetValue(lastRow)) == TOTAL_SELECTED_SEGMENTS_LABEL, (
        "the run must END with the explicit Total row naming the denominator."
    )
    assert float(grid.GetColumn(volumeIndex).GetValue(lastRow)) == pytest.approx(8.0, rel=1e-3), (
        "the Total row must carry the denominator's own mL."
    )
    assert str(grid.GetColumn(percentIndex).GetValue(lastRow)).startswith("100"), (
        "the Total row reads 100% of itself."
    )
    # The column itself states the same definition (the header tooltip).
    description = table.GetColumnDescription(_PERCENT_COL)
    assert "selected" in description.lower(), (
        "the '% of total' column description must state the denominator "
        "definition (the selected input segments)."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Python wrapper tests for ``vtkMRMLBezierSurfaceStorageNode``.

ADR-0008 §3 dual-mode discipline: every C++ class reachable from
Python carries a matching Python-side smoke test.  The C++ test
driver (``LiverResections/MRML/Testing/Cxx/vtkMRMLBezierSurfaceStorageNodeTest1.cxx``)
covers the same field roster from C++; this module is the wrapper-
layer check that the storage node is importable, instantiable, and
round-trips through the .lrp.json + .lrp.fcsv paths from the
wrapped surface.

References
----------
* ADR-0008 §3 — dual-mode test discipline.
* ADR-0014 §5 — .lrp.json schema commitment + legacy .lrp.fcsv
  load-only migration.
* ADR-0013 §8 — display-node split (rationale for dropping the
  legacy margin fields on migration).
"""

from __future__ import annotations

import math
import os

import pytest


@pytest.fixture(scope="module")
def mrml_module():
    """Import the wrapped LiverResections MRML module.

    Skips the suite when the C++ MRML library has not been built or
    when pytest runs outside Slicer's bundled Python.  Matches the
    fixture in ``test_bezier_surface_node.py``.
    """
    return pytest.importorskip(
        "vtkSlicerLiverResectionsModuleMRMLPython",
        reason=(
            "vtkSlicerLiverResectionsModuleMRML not built / not on "
            "sys.path; skip the Python-side BezierSurfaceStorageNode "
            "tests."
        ),
    )


def _make_grid():
    """Deterministic 48-double Bezier control grid for round-trip tests."""
    return [math.sin(0.1 * i) + 0.125 * i for i in range(48)]


def _populate(node, mrml_module):
    """Set every storage-relevant field with distinctive values.

    Init-mode subordinate data is set while State==Init (ADR-0014 §4
    read-only guard otherwise rejects the mutations).  We then
    transition to Planning before assigning the control grid, to
    match the realistic write-path order.
    """
    cls = mrml_module.vtkMRMLBezierSurfaceNode
    node.SetInitMode(cls.DistanceSpheroid)

    node.SetSlicingPlaneOrigin([1.0, 2.0, 3.0])
    node.SetSlicingPlaneNormal([0.0, 1.0, 0.0])
    node.SetSlicingPlaneInitPoint(0, [4.0, 5.0, 6.0])
    node.SetSlicingPlaneInitPoint(1, [7.0, 8.0, 9.0])

    node.SetNumberOfDistanceSpheroidInitPoints(3)
    node.SetDistanceSpheroidInitPoint(0, [10.0, 11.0, 12.0])
    node.SetDistanceSpheroidInitPoint(1, [13.0, 14.0, 15.0])
    node.SetDistanceSpheroidInitPoint(2, [16.0, 17.0, 18.0])
    node.SetDistanceSpheroidCenter([19.0, 20.0, 21.0])
    node.SetDistanceSpheroidRadiusX(2.5)
    node.SetDistanceSpheroidRadiusY(3.5)
    node.SetDistanceSpheroidRadiusZ(4.5)

    node.SetState(cls.Planning)

    grid = _make_grid()
    node.SetControlGrid(grid)


# --------------------------------------------------------------------------- #
# Surface — instantiation, basic API
# --------------------------------------------------------------------------- #


def test_storage_construction_and_tag_name(mrml_module):
    storage = mrml_module.vtkMRMLBezierSurfaceStorageNode()
    assert storage is not None
    assert storage.GetNodeTagName() == "BezierSurfaceStorage"
    assert storage.GetDefaultWriteFileExtension() == "lrp.json"


def test_storage_can_read_can_write_discrimination(mrml_module):
    """Both Can*ReferenceNode methods accept the surface node only."""
    storage = mrml_module.vtkMRMLBezierSurfaceStorageNode()
    surface = mrml_module.vtkMRMLBezierSurfaceNode()
    # vtkMRMLModelNode is a sibling MRML node from Slicer core; we
    # rely on it being importable from the wrapped scene module.
    # Use the storage node itself as a "wrong class" stand-in if
    # vtkMRMLModelNode is not available — the rejection still
    # exercises the wrong-class branch.
    storage2 = mrml_module.vtkMRMLBezierSurfaceStorageNode()
    assert storage.CanReadInReferenceNode(surface) is True
    assert storage.CanWriteFromReferenceNode(surface) is True
    assert storage.CanReadInReferenceNode(storage2) is False
    assert storage.CanWriteFromReferenceNode(storage2) is False


# --------------------------------------------------------------------------- #
# .lrp.json round-trip
# --------------------------------------------------------------------------- #


def test_storage_json_round_trip(mrml_module, tmp_path):
    cls = mrml_module.vtkMRMLBezierSurfaceNode

    source = cls()
    _populate(source, mrml_module)

    path = str(tmp_path / "round_trip.lrp.json")
    writer = mrml_module.vtkMRMLBezierSurfaceStorageNode()
    writer.SetFileName(path)
    assert writer.WriteData(source) == 1
    assert os.path.exists(path)

    sink = cls()
    reader = mrml_module.vtkMRMLBezierSurfaceStorageNode()
    reader.SetFileName(path)
    assert reader.ReadData(sink) == 1

    # Enum round-trip.
    assert sink.GetState() == source.GetState()
    assert sink.GetInitMode() == source.GetInitMode()

    # Control grid.
    for i in range(cls.ControlGridSize):
        assert (
            abs(sink.GetControlGrid()[i] - source.GetControlGrid()[i])
            < 1e-9
        )

    # SlicingPlane.
    assert list(sink.GetSlicingPlaneOrigin()) == list(
        source.GetSlicingPlaneOrigin()
    )
    assert list(sink.GetSlicingPlaneNormal()) == list(
        source.GetSlicingPlaneNormal()
    )
    for i in range(2):
        assert list(sink.GetSlicingPlaneInitPoint(i)) == list(
            source.GetSlicingPlaneInitPoint(i)
        )

    # DistanceSpheroid.
    assert (
        sink.GetNumberOfDistanceSpheroidInitPoints()
        == source.GetNumberOfDistanceSpheroidInitPoints()
    )
    for i in range(source.GetNumberOfDistanceSpheroidInitPoints()):
        assert list(sink.GetDistanceSpheroidInitPoint(i)) == list(
            source.GetDistanceSpheroidInitPoint(i)
        )
    assert list(sink.GetDistanceSpheroidCenter()) == list(
        source.GetDistanceSpheroidCenter()
    )
    assert abs(
        sink.GetDistanceSpheroidRadiusX() - source.GetDistanceSpheroidRadiusX()
    ) < 1e-9
    assert abs(
        sink.GetDistanceSpheroidRadiusY() - source.GetDistanceSpheroidRadiusY()
    ) < 1e-9
    assert abs(
        sink.GetDistanceSpheroidRadiusZ() - source.GetDistanceSpheroidRadiusZ()
    ) < 1e-9


def test_storage_json_schema_version_mismatch(mrml_module, tmp_path):
    """A schemaVersion the reader does not know about is rejected."""
    path = tmp_path / "bad_version.lrp.json"
    path.write_text(
        "{\n"
        '  "schemaVersion": 99,\n'
        '  "state": "Init",\n'
        '  "initMode": "SlicingPlane"\n'
        "}\n"
    )
    sink = mrml_module.vtkMRMLBezierSurfaceNode()
    storage = mrml_module.vtkMRMLBezierSurfaceStorageNode()
    storage.SetFileName(str(path))
    # Read should fail (returns 0); error is emitted via vtkErrorMacro
    # — Python wrapper sees the return code.
    assert storage.ReadData(sink) == 0


# --------------------------------------------------------------------------- #
# Legacy .lrp.fcsv migration
# --------------------------------------------------------------------------- #


def test_storage_legacy_fcsv_read(mrml_module, tmp_path):
    """A canned 16-point legacy CSV migrates onto the new node."""
    path = tmp_path / "legacy.lrp.fcsv"
    rows = ["# Markups fiducial file version = 4.11",
            "# CoordinateSystem = LPS",
            "# columns = id,x,y,z,ow,ox,oy,oz,vis,sel,lock,label,desc,associatedNodeID"]
    for i in range(16):
        x = (i % 4) * 10.0
        y = (i // 4) * 10.0
        rows.append(
            f"vtkMRMLMarkupsFiducialNode_{i + 1},{x},{y},0.0,0.0,0.0,0.0,1.0,"
            f"1,1,0,P-{i + 1},,vtkMRMLScalarVolumeNode1"
        )
    path.write_text("\n".join(rows) + "\n")

    cls = mrml_module.vtkMRMLBezierSurfaceNode
    sink = cls()
    storage = mrml_module.vtkMRMLBezierSurfaceStorageNode()
    storage.SetFileName(str(path))
    assert storage.ReadData(sink) == 1

    # Default post-migration mapping (see field-mapping table in
    # vtkMRMLBezierSurfaceStorageNode.cxx).
    assert sink.GetState() == cls.Planning
    assert sink.GetInitMode() == cls.SlicingPlane

    # Spot-check the row-major grid: index 0 → (0, 0, 0);
    # index 15 → (30, 30, 0).
    grid = sink.GetControlGrid()
    assert grid[0] == 0.0
    assert grid[1] == 0.0
    assert grid[2] == 0.0
    assert grid[15 * 3 + 0] == 30.0
    assert grid[15 * 3 + 1] == 30.0
    assert grid[15 * 3 + 2] == 0.0


def test_storage_legacy_fcsv_write_rejected(mrml_module, tmp_path):
    """Writing the legacy CSV extension is not supported."""
    source = mrml_module.vtkMRMLBezierSurfaceNode()
    _populate(source, mrml_module)
    path = tmp_path / "reject.lrp.fcsv"
    storage = mrml_module.vtkMRMLBezierSurfaceStorageNode()
    storage.SetFileName(str(path))
    assert storage.WriteData(source) == 0
    # No file should have been written.
    assert not path.exists()

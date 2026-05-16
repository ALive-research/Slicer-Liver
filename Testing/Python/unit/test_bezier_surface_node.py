"""Python unit tests for ``vtkMRMLBezierSurfaceNode`` and
``vtkMRMLBezierSurfaceDisplayNode`` — T2 Stack 2 / T2.1.

These tests exercise the Python-wrapped surface of the two new MRML
node classes landed by ADR-0014 §1 (data node, init-mode subordinate
data) and ADR-0013 §8 (display-side decoration fields).  They run in
the same dual-mode discipline as
``Testing/Python/unit/test_bezier_characterization.py``: the wrapped
module is the ground truth and the test imports it via
``pytest.importorskip``, so the suite skips cleanly when the C++ side
is not built.

The C++ test driver
(``LiverResections/MRML/Testing/Cxx/vtkMRMLBezierSurfaceNodeTest1.cxx``)
covers the same surface from C++.  Both layers exist because ADR-0008
§3 commits the project to dual-mode tests for any code reachable from
both languages.

References
----------
* ADR-0008 §2 — layered testing taxonomy.
* ADR-0008 §3 — dual-mode (Python wrapper + C++ ctkTest) discipline.
* ADR-0013 §8 — display-node split.
* ADR-0014 §1, §4 — data node shape + init-mode subordinate data.
"""

from __future__ import annotations

import math

import pytest


# --------------------------------------------------------------------------- #
# Module-scoped fixture — import the wrapped MRML module, skipping if it is
# not available (incremental builds where the C++ MRML library has not yet
# been compiled, or pytest invocations outside Slicer's bundled Python).
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def mrml_module():
    """Import the wrapped LiverResections MRML module.

    The wrapped module name follows the convention emitted by
    ``SlicerMacroBuildModuleMRML`` (mirrors
    ``vtkSlicerLiverResectionsModuleAlgorithmPython`` used by
    ``test_bezier_characterization.py``).
    """
    return pytest.importorskip(
        "vtkSlicerLiverResectionsModuleMRMLPython",
        reason=(
            "vtkSlicerLiverResectionsModuleMRML not built / not on "
            "sys.path; skip the Python-side BezierSurfaceNode tests."
        ),
    )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _make_grid():
    """Return 48 doubles laid out row-major (4x4x3, degree-3 patch).

    The grid size matches ADR-0014 §3: 16 control points (4 corners +
    8 edges + 4 interior) for a single degree-3 Bernstein patch.  This
    also matches the legacy ``vtkMRMLMarkupsBezierSurfaceNode::
    RequiredNumberOfControlPoints == 16`` and the corrected degree-3
    characterisation landed by PR #342.
    """
    return [math.sin(0.1 * i) for i in range(48)]


# --------------------------------------------------------------------------- #
# vtkMRMLBezierSurfaceNode — data node
# --------------------------------------------------------------------------- #


def test_node_construction_and_tag_name(mrml_module):
    """The node instantiates and reports the expected XML tag name."""
    node = mrml_module.vtkMRMLBezierSurfaceNode()
    assert node is not None
    assert node.GetNodeTagName() == "BezierSurface"


def test_node_default_state_and_mode(mrml_module):
    """Defaults: State=Init (0), InitializationMode=SlicingPlane (0)."""
    node = mrml_module.vtkMRMLBezierSurfaceNode()
    assert node.GetState() == mrml_module.vtkMRMLBezierSurfaceNode.Init
    assert node.GetInitMode() == (
        mrml_module.vtkMRMLBezierSurfaceNode.SlicingPlane
    )
    # Read-only constants exposed to Python.
    assert mrml_module.vtkMRMLBezierSurfaceNode.GridSize == 4
    assert mrml_module.vtkMRMLBezierSurfaceNode.ControlGridSize == 48


def test_node_state_round_trip(mrml_module):
    """State setter accepts both enum values and round-trips."""
    node = mrml_module.vtkMRMLBezierSurfaceNode()
    node.SetState(mrml_module.vtkMRMLBezierSurfaceNode.Planning)
    assert node.GetState() == mrml_module.vtkMRMLBezierSurfaceNode.Planning
    node.SetState(mrml_module.vtkMRMLBezierSurfaceNode.Init)
    assert node.GetState() == mrml_module.vtkMRMLBezierSurfaceNode.Init


def test_node_initialization_mode_round_trip(mrml_module):
    """InitializationMode setter round-trips through both modes."""
    node = mrml_module.vtkMRMLBezierSurfaceNode()
    node.SetInitMode(
        mrml_module.vtkMRMLBezierSurfaceNode.DistanceSpheroid
    )
    assert node.GetInitMode() == (
        mrml_module.vtkMRMLBezierSurfaceNode.DistanceSpheroid
    )


def test_node_enum_string_converters(mrml_module):
    """Enum<->string converters cover all enum values."""
    cls = mrml_module.vtkMRMLBezierSurfaceNode
    assert cls.GetStateAsString(cls.Init) == "Init"
    assert cls.GetStateAsString(cls.Planning) == "Planning"
    assert cls.GetStateFromString("Init") == cls.Init
    assert cls.GetStateFromString("Planning") == cls.Planning
    assert cls.GetStateFromString("nonsense") == -1

    assert cls.GetInitModeAsString(cls.SlicingPlane) == "SlicingPlane"
    assert (
        cls.GetInitModeAsString(cls.DistanceSpheroid)
        == "DistanceSpheroid"
    )
    assert (
        cls.GetInitModeFromString("DistanceSpheroid")
        == cls.DistanceSpheroid
    )


def test_node_slicing_plane_init_round_trip(mrml_module):
    """Two slicing-plane init points + origin + normal round-trip."""
    node = mrml_module.vtkMRMLBezierSurfaceNode()

    assert node.SetSlicingPlaneInitPoint(0, [1.0, 2.0, 3.0]) is True
    assert node.SetSlicingPlaneInitPoint(1, [-1.0, -2.0, -3.0]) is True
    assert node.SetSlicingPlaneInitPoint(2, [0.0, 0.0, 0.0]) is False

    p0 = node.GetSlicingPlaneInitPoint(0)
    p1 = node.GetSlicingPlaneInitPoint(1)
    assert list(p0) == [1.0, 2.0, 3.0]
    assert list(p1) == [-1.0, -2.0, -3.0]

    node.SetSlicingPlaneOrigin([10.0, 20.0, 30.0])
    assert list(node.GetSlicingPlaneOrigin()) == [10.0, 20.0, 30.0]
    node.SetSlicingPlaneNormal([0.0, 1.0, 0.0])
    assert list(node.GetSlicingPlaneNormal()) == [0.0, 1.0, 0.0]


def test_node_distance_spheroid_init_round_trip(mrml_module):
    """Variable-length spheroid init points + center + radii."""
    node = mrml_module.vtkMRMLBezierSurfaceNode()

    node.SetNumberOfDistanceSpheroidInitPoints(3)
    assert node.GetNumberOfDistanceSpheroidInitPoints() == 3

    for i in range(3):
        node.SetDistanceSpheroidInitPoint(
            i, [float(i), float(i) + 0.1, float(i) + 0.2]
        )
    for i in range(3):
        got = node.GetDistanceSpheroidInitPoint(i)
        assert list(got) == [float(i), float(i) + 0.1, float(i) + 0.2]

    # Out-of-range rejection.
    assert node.SetDistanceSpheroidInitPoint(3, [0.0, 0.0, 0.0]) is False

    node.SetDistanceSpheroidCenter([1.0, 2.0, 3.0])
    assert list(node.GetDistanceSpheroidCenter()) == [1.0, 2.0, 3.0]
    node.SetDistanceSpheroidRadiusX(2.0)
    node.SetDistanceSpheroidRadiusY(3.0)
    node.SetDistanceSpheroidRadiusZ(4.0)
    assert node.GetDistanceSpheroidRadiusX() == 2.0
    assert node.GetDistanceSpheroidRadiusY() == 3.0
    assert node.GetDistanceSpheroidRadiusZ() == 4.0

    # Clamp on negative radius.
    node.SetDistanceSpheroidRadiusX(-1.0)
    assert node.GetDistanceSpheroidRadiusX() == 0.0


def test_node_xml_round_trip_via_scene(mrml_module):
    """End-to-end MRML scene XML round-trip recovers all data fields.

    Uses the real ``vtkMRMLScene::Commit`` / ``Connect`` path, which
    is the production code path; this is the strongest signal that
    the WriteXML / ReadXMLAttributes pair carries the data unchanged.

    Requires Slicer's own ``slicer`` module to be importable so that
    ``slicer.vtkMRMLScene`` is reachable; skips cleanly when running
    in a plain Python.
    """
    slicer = pytest.importorskip(
        "slicer",
        reason=(
            "vtkMRMLScene round-trip requires Slicer's Python; skip when "
            "running outside the Slicer launcher."
        ),
    )

    scene = slicer.vtkMRMLScene()
    scene.RegisterNodeClass(mrml_module.vtkMRMLBezierSurfaceNode())

    source = mrml_module.vtkMRMLBezierSurfaceNode()
    source.SetState(mrml_module.vtkMRMLBezierSurfaceNode.Planning)
    source.SetInitMode(
        mrml_module.vtkMRMLBezierSurfaceNode.DistanceSpheroid
    )
    grid = _make_grid()
    source.SetControlGrid(grid)
    source.SetSlicingPlaneInitPoint(0, [1.0, 2.0, 3.0])
    source.SetSlicingPlaneInitPoint(1, [-4.0, 5.0, -6.0])
    source.SetSlicingPlaneOrigin([7.0, 8.0, 9.0])
    source.SetSlicingPlaneNormal([0.0, 0.0, -1.0])
    source.SetNumberOfDistanceSpheroidInitPoints(2)
    source.SetDistanceSpheroidInitPoint(0, [11.0, 12.0, 13.0])
    source.SetDistanceSpheroidInitPoint(1, [14.0, 15.0, 16.0])
    source.SetDistanceSpheroidCenter([17.0, 18.0, 19.0])
    source.SetDistanceSpheroidRadiusX(2.5)
    source.SetDistanceSpheroidRadiusY(3.5)
    source.SetDistanceSpheroidRadiusZ(4.5)

    scene.AddNode(source)

    # SetSaveToXMLString + Commit + GetXMLString gives a string we
    # can deserialize into a fresh scene.
    import tempfile
    import os
    with tempfile.NamedTemporaryFile(suffix=".mrml", delete=False) as f:
        path = f.name
    try:
        scene.SetURL(path)
        scene.Commit()

        sink_scene = slicer.vtkMRMLScene()
        sink_scene.RegisterNodeClass(mrml_module.vtkMRMLBezierSurfaceNode())
        sink_scene.SetURL(path)
        sink_scene.Connect()

        sink = sink_scene.GetFirstNodeByClass("vtkMRMLBezierSurfaceNode")
        assert sink is not None
        assert sink.GetState() == source.GetState()
        assert sink.GetInitMode() == source.GetInitMode()
        assert sink.GetNumberOfDistanceSpheroidInitPoints() == 2

        # GetControlGrid() returns the underlying ``const double*``;
        # the VTK Python wrapping exposes it as an indexable sequence.
        # If the wrapper ever switches to surfacing a raw memory
        # address (or anything not subscriptable from Python) this
        # assertion will fire and force us to expose a proper Python
        # accessor — silently dropping out of the loop on the first
        # element, as the original test did, would let a degraded
        # round-trip pass unnoticed.
        control_grid = sink.GetControlGrid()
        assert hasattr(control_grid, "__getitem__"), (
            "GetControlGrid() must surface as an indexable sequence from "
            "Python; got " + repr(type(control_grid))
        )
        for i, expected in enumerate(grid):
            assert control_grid[i] == pytest.approx(expected, rel=1e-5, abs=1e-7)

        # Init audit data — independent of how the control-grid pointer
        # wraps.
        sp0 = sink.GetSlicingPlaneInitPoint(0)
        sp1 = sink.GetSlicingPlaneInitPoint(1)
        assert list(sp0) == pytest.approx([1.0, 2.0, 3.0])
        assert list(sp1) == pytest.approx([-4.0, 5.0, -6.0])

        assert list(sink.GetDistanceSpheroidCenter()) == pytest.approx(
            [17.0, 18.0, 19.0]
        )
        assert sink.GetDistanceSpheroidRadiusX() == pytest.approx(2.5)
        assert sink.GetDistanceSpheroidRadiusY() == pytest.approx(3.5)
        assert sink.GetDistanceSpheroidRadiusZ() == pytest.approx(4.5)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def test_node_copy_content(mrml_module):
    """CopyContent produces an independent copy that survives source edits."""
    source = mrml_module.vtkMRMLBezierSurfaceNode()
    source.SetState(mrml_module.vtkMRMLBezierSurfaceNode.Planning)
    source.SetSlicingPlaneOrigin([1.0, 2.0, 3.0])
    source.SetDistanceSpheroidRadiusX(1.5)
    source.SetNumberOfDistanceSpheroidInitPoints(2)
    source.SetDistanceSpheroidInitPoint(0, [1.0, 2.0, 3.0])
    source.SetDistanceSpheroidInitPoint(1, [4.0, 5.0, 6.0])

    sink = mrml_module.vtkMRMLBezierSurfaceNode()
    sink.CopyContent(source, True)

    assert sink.GetState() == mrml_module.vtkMRMLBezierSurfaceNode.Planning
    assert list(sink.GetSlicingPlaneOrigin()) == [1.0, 2.0, 3.0]
    assert sink.GetDistanceSpheroidRadiusX() == 1.5
    assert sink.GetNumberOfDistanceSpheroidInitPoints() == 2

    # Mutate source; sink must remain unchanged.
    source.SetSlicingPlaneOrigin([99.0, 99.0, 99.0])
    assert list(sink.GetSlicingPlaneOrigin()) == [1.0, 2.0, 3.0]


# --------------------------------------------------------------------------- #
# vtkMRMLBezierSurfaceDisplayNode — display node
# --------------------------------------------------------------------------- #


def test_display_construction_and_tag_name(mrml_module):
    """Display node instantiates and reports the expected XML tag name."""
    node = mrml_module.vtkMRMLBezierSurfaceDisplayNode()
    assert node is not None
    assert node.GetNodeTagName() == "BezierSurfaceDisplay"


def test_display_defaults(mrml_module):
    """Defaults match the legacy ResectionNode baseline.

    See vtkMRMLLiverResectionNode.cxx:56-66.  Any divergence is a
    review-point per ADR-0003.
    """
    node = mrml_module.vtkMRMLBezierSurfaceDisplayNode()
    assert list(node.GetResectionColor()) == pytest.approx([1.0, 1.0, 1.0])
    assert list(node.GetResectionMarginColor()) == pytest.approx(
        [1.0, 0.0, 0.0]
    )
    assert list(node.GetUncertaintyMarginColor()) == pytest.approx(
        [1.0, 1.0, 0.0]
    )
    # Narrowing relative to the legacy node, which did not initialise
    # ResectionGridColor in its member init list.  Documented in the
    # display node's doxygen.
    assert list(node.GetResectionGridColor()) == pytest.approx([0.0, 0.0, 0.0])
    assert node.GetResectionOpacity() == pytest.approx(1.0)
    assert node.GetGridVisibility() is False
    assert node.GetGridDivisions() == pytest.approx(0.0)
    assert node.GetGridThickness() == pytest.approx(0.0)
    assert node.GetGrid3DVisibility() is True
    assert node.GetGrid2DVisibility() is False
    assert node.GetWidgetVisibility() is True
    assert node.GetClipOut() is False
    assert node.GetInterpolatedMargins() is False
    assert node.GetShowResection2D() is False
    assert node.GetMirrorDisplay() is False


def test_display_setters_and_clamps(mrml_module):
    """Every setter round-trips; ResectionOpacity clamps to [0, 1]."""
    node = mrml_module.vtkMRMLBezierSurfaceDisplayNode()

    node.SetResectionColor([0.25, 0.5, 0.75])
    assert list(node.GetResectionColor()) == pytest.approx([0.25, 0.5, 0.75])
    node.SetResectionGridColor([0.1, 0.2, 0.3])
    assert list(node.GetResectionGridColor()) == pytest.approx([0.1, 0.2, 0.3])
    node.SetResectionMarginColor([0.9, 0.8, 0.7])
    assert list(node.GetResectionMarginColor()) == pytest.approx(
        [0.9, 0.8, 0.7]
    )
    node.SetUncertaintyMarginColor([0.6, 0.5, 0.4])
    assert list(node.GetUncertaintyMarginColor()) == pytest.approx(
        [0.6, 0.5, 0.4]
    )

    node.SetResectionOpacity(0.5)
    assert node.GetResectionOpacity() == pytest.approx(0.5)
    node.SetResectionOpacity(2.0)
    assert node.GetResectionOpacity() == pytest.approx(1.0)
    node.SetResectionOpacity(-1.0)
    assert node.GetResectionOpacity() == pytest.approx(0.0)

    node.SetGridVisibility(True)
    assert node.GetGridVisibility() is True
    node.SetGridDivisions(4.0)
    assert node.GetGridDivisions() == pytest.approx(4.0)
    node.SetGridThickness(2.5)
    assert node.GetGridThickness() == pytest.approx(2.5)
    node.SetGrid3DVisibility(False)
    assert node.GetGrid3DVisibility() is False
    node.SetGrid2DVisibility(True)
    assert node.GetGrid2DVisibility() is True
    node.SetWidgetVisibility(False)
    assert node.GetWidgetVisibility() is False
    node.SetClipOut(True)
    assert node.GetClipOut() is True
    node.SetInterpolatedMargins(True)
    assert node.GetInterpolatedMargins() is True
    node.SetShowResection2D(True)
    assert node.GetShowResection2D() is True
    node.SetMirrorDisplay(True)
    assert node.GetMirrorDisplay() is True


def test_display_copy_content(mrml_module):
    """CopyContent on the display node produces an independent copy."""
    source = mrml_module.vtkMRMLBezierSurfaceDisplayNode()
    source.SetResectionColor([0.25, 0.5, 0.75])
    source.SetResectionOpacity(0.42)
    source.SetClipOut(True)

    sink = mrml_module.vtkMRMLBezierSurfaceDisplayNode()
    sink.CopyContent(source, True)

    assert list(sink.GetResectionColor()) == pytest.approx([0.25, 0.5, 0.75])
    assert sink.GetResectionOpacity() == pytest.approx(0.42)
    assert sink.GetClipOut() is True

    source.SetResectionColor([0.0, 0.0, 0.0])
    assert list(sink.GetResectionColor()) == pytest.approx([0.25, 0.5, 0.75])


def test_display_terminology_entry_round_trip(mrml_module):
    """SCT terminology field defaults empty and round-trips through set/get.

    Pins the ADR-0011 + ADR-0013 §3 contract from the Python-wrapped
    surface: the display node stores a serialised SCT triple as a
    ``std::string``, defaults to empty (meaning "no terminology
    assigned — Pipeline uses pure-vector defaults"), and round-trips
    via the wrapped setter / getter without mangling separator chars
    (``^``, ``~``).  The CopyContent path must deep-copy so source
    mutation does not leak into a previously-copied sink.

    The XML round-trip is covered by the C++ driver
    (``vtkMRMLBezierSurfaceDisplayNodeTest1.cxx``); we keep this
    Python-side check focused on the wrapped Python surface.
    """
    node = mrml_module.vtkMRMLBezierSurfaceDisplayNode()
    assert node.GetTerminologyEntry() == ""

    sct = "SCT^123037004^Anatomical Structure~SCT^10200004^Liver~^^"
    baseline = node.GetMTime()
    node.SetTerminologyEntry(sct)
    assert node.GetTerminologyEntry() == sct
    assert node.GetMTime() > baseline

    # Separator chars round-trip through the wrapped std::string.
    assert "^" in node.GetTerminologyEntry()
    assert "~" in node.GetTerminologyEntry()

    # CopyContent: deep-copy means later source edits do not bleed
    # into the previously-copied sink.
    sink = mrml_module.vtkMRMLBezierSurfaceDisplayNode()
    sink.CopyContent(node, True)
    assert sink.GetTerminologyEntry() == sct
    node.SetTerminologyEntry("")
    assert sink.GetTerminologyEntry() == sct

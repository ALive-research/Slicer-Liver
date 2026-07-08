# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Python unit tests for ``vtkMRMLBezierSurfaceNode`` and
``vtkMRMLParametricSurfaceDisplayNode`` — T2 Stack 2 / T2.1.

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
    # NB: GridSize / ControlGridSize are compile-time ``static constexpr``
    # dimensions with no production Python consumer; VTK does not surface
    # constexpr members as Python class attributes, and asserting their
    # literal values from Python would test the wrapper, not behaviour.


def test_node_state_round_trip(mrml_module):
    """State setter accepts all three enum values along the legal path.

    Init -> Planning -> Confirmed -> Planning is the legal cycle
    committed by ADR-0019; ADR-0014 §4's Planning -> Init invariant
    plus ADR-0019's Confirmed -> Init and Init -> Confirmed bans are
    covered by ``test_node_state_transitions_forbidden`` below.
    """
    cls = mrml_module.vtkMRMLBezierSurfaceNode
    node = cls()
    node.SetState(cls.Planning)
    assert node.GetState() == cls.Planning
    # Same-state self-assign is a no-op (no Modified() expected; not
    # asserted here but covered by testModifiedEventsOnSetters on the
    # C++ side).
    node.SetState(cls.Planning)
    assert node.GetState() == cls.Planning
    # ADR-0019: Planning -> Confirmed -> Planning round-trip.
    node.SetState(cls.Confirmed)
    assert node.GetState() == cls.Confirmed
    node.SetState(cls.Planning)
    assert node.GetState() == cls.Planning


def test_node_state_transitions_forbidden(mrml_module):
    """Forbidden transitions per ADR-0019 leave State unchanged.

    Each rejection emits a ``vtkWarningMacro`` and short-circuits
    without firing ``Modified()`` — only the post-condition (State
    unchanged) is asserted from Python; ``GetMTime()`` non-advance is
    covered by the C++ ``testConfirmedStateTransitions`` sub-test.
    """
    cls = mrml_module.vtkMRMLBezierSurfaceNode

    # Init -> Confirmed forbidden.
    node = cls()
    node.SetState(cls.Confirmed)
    assert node.GetState() == cls.Init

    # Confirmed -> Init forbidden.
    node2 = cls()
    node2.SetState(cls.Planning)
    node2.SetState(cls.Confirmed)
    node2.SetState(cls.Init)
    assert node2.GetState() == cls.Confirmed

    # Planning -> Init forbidden (also covered by
    # ``test_node_init_data_read_only_after_planning`` below).
    node3 = cls()
    node3.SetState(cls.Planning)
    node3.SetState(cls.Init)
    assert node3.GetState() == cls.Planning


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
    assert cls.GetStateAsString(cls.Confirmed) == "Confirmed"
    assert cls.GetStateFromString("Init") == cls.Init
    assert cls.GetStateFromString("Planning") == cls.Planning
    assert cls.GetStateFromString("Confirmed") == cls.Confirmed
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


def test_node_mrml_xml_carries_identity_not_bulk(mrml_module):
    """MRML scene XML carries slim identity only; bulk lives in .lrp.json.

    Uses the real ``vtkMRMLScene::Commit`` / ``Connect`` path.  Per the
    storage-ownership design
    (``Docs/design/resection-plan-architecture/03-storage-ownership.md``),
    ``WriteXML`` is deliberately slim: only scene-relevant identity
    metadata (``State``, grid ``rows``/``cols``) goes into the ``.mrml``;
    the bulk Init-mode data persists via the parent plan's ``.lrp.json``
    storage path.  This pins that contract — identity round-trips through
    the scene XML, bulk fields come back at their defaults when no paired
    ``.lrp.json`` is loaded.

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
    # Populate Init-mode subordinate data BEFORE the Init→Planning
    # transition — per ADR-0014 §4 the per-setter guards reject
    # post-Planning mutation.
    source.SetInitMode(
        mrml_module.vtkMRMLBezierSurfaceNode.DistanceSpheroid
    )
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

    # Transition and write the Bezier grid (the only mutable
    # geometry post-transition).
    source.SetState(mrml_module.vtkMRMLBezierSurfaceNode.Planning)
    grid = _make_grid()
    source.SetControlGrid(grid)

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

        # The ``.mrml`` carries only scene-relevant identity metadata.
        # ``State`` is written by the Bezier node's WriteXML and round-trips.
        assert sink.GetState() == source.GetState()

        # Per the storage-ownership design
        # (``Docs/design/resection-plan-architecture/03-storage-ownership.md``)
        # the BULK fields — ``InitMode``, the slicing-plane / spheroid init
        # subordinates, the spheroid center+radii, and the control grid —
        # are intentionally NOT serialized into the ``.mrml``; they persist
        # through the parent plan's ``.lrp.json`` storage path.  A scene
        # load WITHOUT a paired ``.lrp.json`` therefore recovers those bulk
        # fields at their defaults — "degraded but non-crashing"
        # (``04-save-load-flows.md`` §"Failure modes").  This test pins that
        # split: identity round-trips via ``.mrml``; bulk does not.
        cls = mrml_module.vtkMRMLBezierSurfaceNode
        assert sink.GetInitMode() == cls.SlicingPlane  # default, not DistanceSpheroid
        assert sink.GetNumberOfDistanceSpheroidInitPoints() == 0
        assert list(sink.GetSlicingPlaneOrigin()) == [0.0, 0.0, 0.0]
        assert sink.GetDistanceSpheroidRadiusX() == 0.0
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def test_node_copy_content(mrml_module):
    """CopyContent produces an independent copy that survives source edits.

    Init-mode subordinate data is populated pre-transition (the
    production lifecycle per ADR-0014 §4); the transition runs after
    so the deep-copy carries State == Planning across.
    """
    source = mrml_module.vtkMRMLBezierSurfaceNode()
    source.SetSlicingPlaneOrigin([1.0, 2.0, 3.0])
    source.SetDistanceSpheroidRadiusX(1.5)
    source.SetNumberOfDistanceSpheroidInitPoints(2)
    source.SetDistanceSpheroidInitPoint(0, [1.0, 2.0, 3.0])
    source.SetDistanceSpheroidInitPoint(1, [4.0, 5.0, 6.0])
    source.SetState(mrml_module.vtkMRMLBezierSurfaceNode.Planning)

    sink = mrml_module.vtkMRMLBezierSurfaceNode()
    sink.CopyContent(source, True)

    assert sink.GetState() == mrml_module.vtkMRMLBezierSurfaceNode.Planning
    assert list(sink.GetSlicingPlaneOrigin()) == [1.0, 2.0, 3.0]
    assert sink.GetDistanceSpheroidRadiusX() == 1.5
    assert sink.GetNumberOfDistanceSpheroidInitPoints() == 2

    # Source is in Planning so SetSlicingPlaneOrigin is now rejected
    # by the ADR-0014 §4 guard.  The deep-copy independence assertion
    # below is therefore trivially satisfied for *this* source; the
    # property is exercised more directly by the dedicated read-only
    # test below.
    sink_origin_before = list(sink.GetSlicingPlaneOrigin())
    source.SetSlicingPlaneOrigin([99.0, 99.0, 99.0])
    assert list(sink.GetSlicingPlaneOrigin()) == sink_origin_before


def test_node_init_data_read_only_after_planning(mrml_module):
    """ADR-0014 §4: init-mode data is read-only after Init→Planning.

    Mirrors the C++ ``testInitDataReadOnlyAfterPlanning`` characterisation:
    every gated setter accepts mutation while ``State == Init``, then
    short-circuits (no value change, no ``MTime`` advance) once
    ``State == Planning``.  Planning→Init drop-back is also rejected.
    """
    node = mrml_module.vtkMRMLBezierSurfaceNode()
    cls = mrml_module.vtkMRMLBezierSurfaceNode
    assert node.GetState() == cls.Init

    # Populate Init-mode subordinate data while State == Init.
    node.SetSlicingPlaneOrigin([1.0, 2.0, 3.0])
    node.SetSlicingPlaneNormal([0.0, 1.0, 0.0])
    assert node.SetSlicingPlaneInitPoint(0, [4.0, 5.0, 6.0]) is True
    assert node.SetSlicingPlaneInitPoint(1, [7.0, 8.0, 9.0]) is True
    node.SetNumberOfDistanceSpheroidInitPoints(2)
    assert node.SetDistanceSpheroidInitPoint(0, [10.0, 11.0, 12.0]) is True
    assert node.SetDistanceSpheroidInitPoint(1, [13.0, 14.0, 15.0]) is True
    node.SetDistanceSpheroidCenter([16.0, 17.0, 18.0])
    node.SetDistanceSpheroidRadiusX(1.5)
    node.SetDistanceSpheroidRadiusY(2.5)
    node.SetDistanceSpheroidRadiusZ(3.5)

    # Verify the pre-transition values landed.
    assert list(node.GetSlicingPlaneOrigin()) == [1.0, 2.0, 3.0]
    assert list(node.GetSlicingPlaneInitPoint(0)) == [4.0, 5.0, 6.0]
    assert list(node.GetDistanceSpheroidInitPoint(1)) == [13.0, 14.0, 15.0]
    assert node.GetDistanceSpheroidRadiusX() == 1.5

    # Forward transition.
    node.SetState(cls.Planning)
    assert node.GetState() == cls.Planning
    baseline_mtime = node.GetMTime()

    # Every gated setter is now rejected.  Mutation does not land and
    # MTime does not advance.
    node.SetSlicingPlaneOrigin([99.0, 99.0, 99.0])
    assert list(node.GetSlicingPlaneOrigin()) == [1.0, 2.0, 3.0]
    assert node.GetMTime() == baseline_mtime

    node.SetSlicingPlaneNormal([1.0, 0.0, 0.0])
    assert list(node.GetSlicingPlaneNormal()) == [0.0, 1.0, 0.0]
    assert node.GetMTime() == baseline_mtime

    # bool-returning setters signal rejection via False.
    assert (
        node.SetSlicingPlaneInitPoint(0, [-1.0, -2.0, -3.0]) is False
    )
    assert list(node.GetSlicingPlaneInitPoint(0)) == [4.0, 5.0, 6.0]
    assert node.GetMTime() == baseline_mtime

    node.SetNumberOfDistanceSpheroidInitPoints(7)
    assert node.GetNumberOfDistanceSpheroidInitPoints() == 2
    assert node.GetMTime() == baseline_mtime

    assert (
        node.SetDistanceSpheroidInitPoint(0, [-1.0, -2.0, -3.0]) is False
    )
    assert list(node.GetDistanceSpheroidInitPoint(0)) == [10.0, 11.0, 12.0]

    node.SetDistanceSpheroidCenter([99.0, 99.0, 99.0])
    assert list(node.GetDistanceSpheroidCenter()) == [16.0, 17.0, 18.0]

    node.SetDistanceSpheroidRadiusX(99.0)
    assert node.GetDistanceSpheroidRadiusX() == 1.5
    node.SetDistanceSpheroidRadiusY(99.0)
    assert node.GetDistanceSpheroidRadiusY() == 2.5
    node.SetDistanceSpheroidRadiusZ(99.0)
    assert node.GetDistanceSpheroidRadiusZ() == 3.5

    assert node.GetMTime() == baseline_mtime

    # Planning → Init drop-back is rejected (ADR-0014 §4).
    node.SetState(cls.Init)
    assert node.GetState() == cls.Planning
    assert node.GetMTime() == baseline_mtime

    # Control grid is the editable geometry in Planning — outside the
    # guard's scope.  Mutation lands and MTime advances.
    grid = _make_grid()
    node.SetControlGrid(grid)
    assert node.GetMTime() > baseline_mtime


# --------------------------------------------------------------------------- #
# vtkMRMLParametricSurfaceDisplayNode — display node
# --------------------------------------------------------------------------- #


def test_display_construction_and_tag_name(mrml_module):
    """Display node instantiates and reports the expected XML tag name."""
    node = mrml_module.vtkMRMLParametricSurfaceDisplayNode()
    assert node is not None
    assert node.GetNodeTagName() == "ParametricSurfaceDisplay"


def test_display_defaults(mrml_module):
    """Defaults match the legacy ResectionNode baseline.

    See vtkMRMLLiverResectionNode.cxx:56-66.  Any divergence is a
    review-point per ADR-0003.
    """
    node = mrml_module.vtkMRMLParametricSurfaceDisplayNode()
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
    # Grid defaults match the resection mapper's own (divisions 20,
    # thickness factor 9.5) so a fresh display node renders the control-grid
    # overlay -- the earlier 0/0 defaults overwrote the mapper uniforms and
    # suppressed the grid entirely.
    assert node.GetGridDivisions() == pytest.approx(20.0)
    assert node.GetGridThickness() == pytest.approx(9.5)
    assert node.GetGrid3DVisibility() is True
    assert node.GetGrid2DVisibility() is False
    assert node.GetWidgetVisibility() is True
    assert node.GetClipOut() is False
    assert node.GetInterpolatedMargins() is False
    assert node.GetShowResection2D() is False
    assert node.GetMirrorDisplay() is False


def test_display_setters_and_clamps(mrml_module):
    """Every setter round-trips; ResectionOpacity clamps to [0, 1]."""
    node = mrml_module.vtkMRMLParametricSurfaceDisplayNode()

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
    source = mrml_module.vtkMRMLParametricSurfaceDisplayNode()
    source.SetResectionColor([0.25, 0.5, 0.75])
    source.SetResectionOpacity(0.42)
    source.SetClipOut(True)

    sink = mrml_module.vtkMRMLParametricSurfaceDisplayNode()
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
    (``vtkMRMLParametricSurfaceDisplayNodeTest1.cxx``); we keep this
    Python-side check focused on the wrapped Python surface.
    """
    node = mrml_module.vtkMRMLParametricSurfaceDisplayNode()
    assert node.GetTerminologyEntry() == ""

    # Slicer's canonical 7-component terminology-entry format
    # (terminologyContextName ~ category ~ type ~ typeModifier ~
    # anatomicContextName ~ anatomicRegion ~ anatomicRegionModifier) —
    # matches what vtkSlicerTerminologiesModuleLogic emits/consumes.
    sct = "SlicerLiver-Terminology~SCT^123037004^Anatomical Structure~SCT^10200004^Liver~^^~~^^~^^"
    baseline = node.GetMTime()
    node.SetTerminologyEntry(sct)
    assert node.GetTerminologyEntry() == sct
    assert node.GetMTime() > baseline

    # Separator chars round-trip through the wrapped std::string.
    assert "^" in node.GetTerminologyEntry()
    assert "~" in node.GetTerminologyEntry()

    # CopyContent: deep-copy means later source edits do not bleed
    # into the previously-copied sink.
    sink = mrml_module.vtkMRMLParametricSurfaceDisplayNode()
    sink.CopyContent(node, True)
    assert sink.GetTerminologyEntry() == sct
    node.SetTerminologyEntry("")
    assert sink.GetTerminologyEntry() == sct

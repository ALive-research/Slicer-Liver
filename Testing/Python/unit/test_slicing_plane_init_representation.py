# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Python unit tests for ``SlicingPlaneInitRepresentation``.

Per ADR-0008 §2 Representations are the smallest unit-testable VTK
assembly and have no Slicer dependency.  Two layers of assertions:

* Pure-Python checks against the introspection helpers
  (``GetCurrentColor``, ``GetCurrentOpacity``, ``GetInputRefreshCount``).

* VTK-mediated checks against the real ``vtkActor`` /
  ``vtkSphereSource`` outputs and the recorded contour-mapper calls.

The plane visualisation is the v1 SHADER contour: the whole target
liver mesh renders through ``vtkOpenGLSlicingContourPolyDataMapper``
and the fragment shader keeps only a band around the plane — the band
IS the plane visualisation; no plane square is ever rendered.  The
wrapped mapper is off the path in the bare-VTK unit layer, so every
construction injects a fake through the ``slicing_contour_mapper``
seam (ADR-0014 §3, the ``FlattenedSurfaceRepresentation`` pattern);
the fake subclasses ``vtk.vtkPolyDataMapper`` so a real
``vtkActor().SetMapper`` accepts it, and records the plane-uniform /
visibility / input-connection calls the tests pin.

References
----------
* ADR-0008 §2 — Representation tests, unit layer.
* ADR-0013 §6 — Representations as composable VTK pipelines.
* ADR-0014 §2 — names this Representation.
* ADR-0014 §3 — the injection seam for relocated wrapped mappers.
* ADR-0014 §4 — init data accessors on the data node.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

vtk = pytest.importorskip(
    "vtk",
    reason=(
        "vtk not importable; the Representation module itself imports "
        "vtk, so the whole suite needs it.  Run inside Slicer's Python "
        "or in any environment where the bundled vtk wheel is on "
        "sys.path."
    ),
)

# --------------------------------------------------------------------------- #
# Repo geometry — Representations live at
# ``LiverResections/LiverResectionsLib/Representations/`` per the
# ``<Module>Lib`` install convention adopted at T2.6-LayerDM.
# --------------------------------------------------------------------------- #

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
PY_DIR = REPO_ROOT / "LiverResections" / "LiverResectionsLib"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))


# --------------------------------------------------------------------------- #
# Test doubles
# --------------------------------------------------------------------------- #


class _FakeSlicingContourMapper(vtk.vtkPolyDataMapper):
    """Recording stand-in for ``vtkOpenGLSlicingContourPolyDataMapper``.

    Subclasses ``vtk.vtkPolyDataMapper`` so a real ``vtkActor`` accepts
    it via ``SetMapper``; the Python-side overrides record the calls
    the Representation is expected to make (plane uniforms, contour
    visibility, mesh input connection) without any GL context.
    """

    def __init__(self) -> None:
        super().__init__()
        self.input_connections: list = []
        self.plane_positions: list[tuple] = []
        self.plane_normals: list[tuple] = []
        self.thickness: float | None = None
        self.visibility_calls: list[bool] = []

    def SetInputConnection(self, conn) -> None:  # noqa: N802 - VTK verb
        self.input_connections.append(conn)

    def SetPlanePositionWorld(self, x, y, z) -> None:  # noqa: N802
        self.plane_positions.append((float(x), float(y), float(z)))

    def SetPlaneNormalWorld(self, x, y, z) -> None:  # noqa: N802
        self.plane_normals.append((float(x), float(y), float(z)))

    def SetContourThickness(self, value) -> None:  # noqa: N802
        self.thickness = float(value)

    def SetContourVisibility(self, value) -> None:  # noqa: N802
        self.visibility_calls.append(bool(value))

    @property
    def visibility(self) -> bool | None:
        """The last visibility written, or ``None`` when never set."""
        return self.visibility_calls[-1] if self.visibility_calls else None


def _sphere_polydata():
    """A small non-empty ``vtkPolyData`` standing in for the liver mesh."""
    source = vtk.vtkSphereSource()
    source.Update()
    return source.GetOutput()


class _StubTargetModel:
    """Minimal target-model double: real polydata behind the model-node
    accessors the Representation feeds the contour mapper from."""

    def __init__(self, polydata=None) -> None:
        self._polydata = polydata if polydata is not None else _sphere_polydata()
        self._producer = vtk.vtkTrivialProducer()
        self._producer.SetOutput(self._polydata)

    def GetPolyData(self):  # noqa: N802 - VTK verb
        return self._polydata

    def GetPolyDataConnection(self):  # noqa: N802 - VTK verb
        return self._producer.GetOutputPort()


class _StubDisplayNode:
    def __init__(
        self,
        color: tuple = (1.0, 1.0, 1.0),
        opacity: float = 1.0,
    ) -> None:
        self.color = color
        self.opacity = opacity

    def GetResectionColor(self):
        return self.color

    def GetResectionOpacity(self) -> float:
        return self.opacity


class _StubDataNode:
    def __init__(
        self,
        origin: tuple = (0.0, 0.0, 0.0),
        normal: tuple = (0.0, 0.0, 1.0),
        init0: tuple = (-5.0, 0.0, 0.0),
        init1: tuple = (5.0, 0.0, 0.0),
        target=None,
    ) -> None:
        self.origin = origin
        self.normal = normal
        self.init0 = init0
        self.init1 = init1
        self.target = target
        # The unseeded default 4x4 grid (the surface preview reads it;
        # all-zero = degenerate = no preview).
        self.grid = tuple(0.0 for _ in range(48))

    def GetControlGridVector(self):
        return self.grid

    def GetSlicingPlaneOrigin(self):
        return self.origin

    def GetSlicingPlaneNormal(self):
        return self.normal

    def GetSlicingPlaneInitPoint(self, index: int):
        if index == 0:
            return self.init0
        if index == 1:
            return self.init1
        return None

    def GetTargetModelNode(self):
        return self.target


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def rep_module():
    """Return a factory constructing the Representation with an injected
    fake contour mapper.

    The wrapped ``vtkOpenGLSlicingContourPolyDataMapper`` is off the path
    in the bare-VTK unit layer (ADR-0008 §2), so each construction injects
    a ``_FakeSlicingContourMapper`` via the ``slicing_contour_mapper`` seam
    (ADR-0014 §3).  Tests read the fake back through the Representation's
    ``GetContourMapper()``.
    """
    from Representations.SlicingPlaneInitRepresentation import (
        SlicingPlaneInitRepresentation,
    )

    def _make(renderer=None):
        return SlicingPlaneInitRepresentation(
            renderer, slicing_contour_mapper=_FakeSlicingContourMapper()
        )

    return _make


# --------------------------------------------------------------------------- #
# Pure-Python assertions
# --------------------------------------------------------------------------- #


def test_representation_construct_with_no_renderer(rep_module):
    """Construct without a renderer — no exception, default state set."""
    rep = rep_module()
    assert rep.GetRenderer() is None
    assert rep.GetCurrentColor() == (1.0, 1.0, 1.0)
    assert rep.GetCurrentOpacity() == pytest.approx(1.0)
    assert rep.GetInputRefreshCount() == 0
    rep.cleanup()


def test_representation_update_with_none_display_falls_back_to_defaults(
    rep_module,
):
    """``update(None, data)`` does not raise — actors stay at defaults."""
    rep = rep_module()
    rep.update(display_node=None, data_node=_StubDataNode())
    assert rep.GetCurrentColor() == (1.0, 1.0, 1.0)
    assert rep.GetCurrentOpacity() == pytest.approx(1.0)
    rep.cleanup()


def test_representation_update_with_none_data_does_not_refresh(rep_module):
    """``update(display, None)`` — colour still applied, refresh counter
    does not advance because there is no geometry to push."""
    rep = rep_module()
    display = _StubDisplayNode(color=(0.2, 0.4, 0.6), opacity=0.8)
    rep.update(display, None)
    assert rep.GetCurrentColor() == pytest.approx((0.2, 0.4, 0.6))
    assert rep.GetInputRefreshCount() == 0
    rep.cleanup()


def test_representation_color_round_trip(rep_module):
    """Mutating the display node's ResectionColor flows through update()."""
    rep = rep_module()
    display = _StubDisplayNode(color=(0.25, 0.5, 0.75))
    data = _StubDataNode()
    rep.update(display, data)
    assert rep.GetCurrentColor() == (0.25, 0.5, 0.75)

    display.color = (0.1, 0.2, 0.3)
    rep.update(display, data)
    assert rep.GetCurrentColor() == (0.1, 0.2, 0.3)
    rep.cleanup()


def test_representation_opacity_round_trip(rep_module):
    """ResectionOpacity flows through update() to the introspection helper."""
    rep = rep_module()
    display = _StubDisplayNode(opacity=0.5)
    rep.update(display, _StubDataNode())
    assert rep.GetCurrentOpacity() == pytest.approx(0.5)
    rep.cleanup()


def test_representation_input_refresh_idempotency(rep_module):
    """The idempotency memo on (origin, normal, init0, init1, target)
    skips a redundant refresh; mutating any of those inputs advances the
    counter.
    """
    rep = rep_module()
    display = _StubDisplayNode()
    data = _StubDataNode(
        origin=(1.0, 2.0, 3.0),
        normal=(0.0, 0.0, 1.0),
        init0=(0.0, 0.0, 0.0),
        init1=(10.0, 0.0, 0.0),
    )
    rep.update(display, data)
    first = rep.GetInputRefreshCount()
    assert first == 1, "first update() with valid geometry must refresh"

    # Re-running update() with the same inputs is a no-op (memoised).
    rep.update(display, data)
    assert rep.GetInputRefreshCount() == first

    # Mutating the origin forces a refresh.
    data.origin = (4.0, 5.0, 6.0)
    rep.update(display, data)
    assert rep.GetInputRefreshCount() == first + 1

    # Mutating the normal forces a refresh.
    data.normal = (1.0, 0.0, 0.0)
    rep.update(display, data)
    assert rep.GetInputRefreshCount() == first + 2

    # Mutating init0 forces a refresh.
    data.init0 = (-1.0, -1.0, -1.0)
    rep.update(display, data)
    assert rep.GetInputRefreshCount() == first + 3

    # Mutating init1 forces a refresh.
    data.init1 = (8.0, 0.0, 0.0)
    rep.update(display, data)
    assert rep.GetInputRefreshCount() == first + 4

    # Swapping the target model forces a refresh (contour re-feed).
    data.target = _StubTargetModel()
    rep.update(display, data)
    assert rep.GetInputRefreshCount() == first + 5
    rep.cleanup()


# --------------------------------------------------------------------------- #
# VTK-mediated assertions
# --------------------------------------------------------------------------- #


def test_representation_construct_builds_actors(rep_module):
    """Construction yields two marker actors + the contour actor/mapper
    pair, with the v1 band thickness preset and the contour hidden."""
    from Representations.SlicingPlaneInitRepresentation import (
        CONTOUR_THICKNESS_WORLD,
    )

    rep = rep_module()
    assert rep.GetMarkerActor(0) is not None
    assert rep.GetMarkerActor(1) is not None
    # Only two marker actors — index 2 is out of range.
    assert rep.GetMarkerActor(2) is None
    assert rep.GetContourActor() is not None
    mapper = rep.GetContourMapper()
    assert mapper is not None
    assert mapper.thickness == pytest.approx(CONTOUR_THICKNESS_WORLD)
    # Hidden until a carrier plane + target mesh arrive.
    assert mapper.visibility is False
    rep.cleanup()
    # After cleanup() actors are released.
    assert rep.GetMarkerActor(0) is None
    assert rep.GetContourActor() is None
    assert rep.GetContourMapper() is None


def test_representation_construct_without_wrapping_degrades_to_markers_only(
    monkeypatch,
):
    """With no injected mapper AND the wrapping off the path (production
    resolver returns ``None``) the Representation still constructs —
    markers only, no contour actor, and updates do not raise."""
    import Representations.SlicingPlaneInitRepresentation as mod

    monkeypatch.setattr(mod, "_resolve_slicing_contour_mapper", lambda: None)
    rep = mod.SlicingPlaneInitRepresentation()
    assert rep.GetContourActor() is None
    assert rep.GetContourMapper() is None

    renderer = vtk.vtkRenderer()
    rep.SetRenderer(renderer)
    # 2 markers (+ the surface PREVIEW actor when the wrapped
    # tessellation source resolves -- launched harness only).
    expected = 2 + (1 if rep.GetSurfacePreviewActor() is not None else 0)
    assert renderer.GetActors().GetNumberOfItems() == expected

    rep.update(_StubDisplayNode(), _StubDataNode(target=_StubTargetModel()))
    assert rep.GetInputRefreshCount() == 1
    rep.cleanup()
    assert renderer.GetActors().GetNumberOfItems() == 0


def test_representation_marker_positions_match_init_points(rep_module):
    """After ``update()`` the marker sphere sources sit at the two init
    points reported by the data node."""
    rep = rep_module()
    data = _StubDataNode(
        origin=(0.0, 0.0, 0.0),
        normal=(0.0, 0.0, 1.0),
        init0=(-7.0, 1.0, 2.0),
        init1=(7.0, -1.0, -2.0),
    )
    rep.update(_StubDisplayNode(), data)

    s0 = rep.GetMarkerSource(0)
    s1 = rep.GetMarkerSource(1)
    assert list(s0.GetCenter()) == pytest.approx([-7.0, 1.0, 2.0])
    assert list(s1.GetCenter()) == pytest.approx([7.0, -1.0, -2.0])
    rep.cleanup()


def test_contour_uniforms_follow_the_carrier_plane(rep_module):
    """After ``update()`` with a target mesh present, the contour mapper
    carries the carrier's plane origin/normal as its world-space uniforms
    and the contour is visible — the shader band IS the plane
    visualisation."""
    rep = rep_module()
    data = _StubDataNode(
        origin=(3.0, 4.0, 5.0),
        normal=(0.0, 1.0, 0.0),
        init0=(-2.0, 4.0, 5.0),
        init1=(2.0, 4.0, 5.0),
        target=_StubTargetModel(),
    )
    rep.update(_StubDisplayNode(), data)

    mapper = rep.GetContourMapper()
    assert mapper.plane_positions[-1] == pytest.approx((3.0, 4.0, 5.0))
    assert mapper.plane_normals[-1] == pytest.approx((0.0, 1.0, 0.0))
    assert mapper.visibility is True
    rep.cleanup()


def test_contour_hidden_without_target(rep_module):
    """No target model (or an empty target mesh) → the contour is hidden
    and no plane uniforms are pushed; the markers still refresh."""
    rep = rep_module()
    rep.update(_StubDisplayNode(), _StubDataNode(target=None))

    mapper = rep.GetContourMapper()
    assert mapper.visibility is False
    assert True not in mapper.visibility_calls
    assert mapper.plane_positions == []
    assert mapper.input_connections == []
    assert rep.GetInputRefreshCount() == 1
    rep.cleanup()

    # Empty target mesh — same hidden outcome.
    rep = rep_module()
    empty_target = _StubTargetModel(polydata=vtk.vtkPolyData())
    rep.update(_StubDisplayNode(), _StubDataNode(target=empty_target))
    mapper = rep.GetContourMapper()
    assert mapper.visibility is False
    assert True not in mapper.visibility_calls
    assert mapper.input_connections == []
    rep.cleanup()


def test_contour_feeds_the_target_mesh_once(rep_module):
    """The target mesh connection is fed to the contour mapper once per
    target (memoised); swapping the target re-feeds it."""
    rep = rep_module()
    target_a = _StubTargetModel()
    data = _StubDataNode(target=target_a)
    rep.update(_StubDisplayNode(), data)

    mapper = rep.GetContourMapper()
    assert len(mapper.input_connections) == 1

    # A geometry change at the SAME target refreshes the uniforms but
    # must not re-feed the mesh connection.
    data.origin = (1.0, 0.0, 0.0)
    rep.update(_StubDisplayNode(), data)
    assert len(mapper.input_connections) == 1
    assert mapper.plane_positions[-1] == pytest.approx((1.0, 0.0, 0.0))

    # Swapping the target re-feeds the connection.
    data.target = _StubTargetModel()
    rep.update(_StubDisplayNode(), data)
    assert len(mapper.input_connections) == 2
    rep.cleanup()


def test_representation_mapper_color_matches_display_node(rep_module):
    """After ``update()`` the marker actor properties carry the display
    node's ResectionColor at full opacity.  The contour band takes no
    actor decoration — its colour is the shader's concern."""
    rep = rep_module()
    display = _StubDisplayNode(color=(0.25, 0.5, 0.75), opacity=0.8)
    rep.update(display, _StubDataNode())

    for i in (0, 1):
        actor = rep.GetMarkerActor(i)
        assert list(actor.GetProperty().GetColor()) == pytest.approx(
            [0.25, 0.5, 0.75]
        )
        assert actor.GetProperty().GetOpacity() == pytest.approx(0.8)
    rep.cleanup()


def test_representation_attach_detach_renderer(rep_module):
    """``SetRenderer(r)`` adds two marker actors + the contour actor = 3;
    ``cleanup()`` removes them all."""
    rep = rep_module()
    renderer = vtk.vtkRenderer()
    assert renderer.GetActors().GetNumberOfItems() == 0

    rep.SetRenderer(renderer)
    # Two markers + the shader contour (+ the surface PREVIEW actor when
    # the wrapped tessellation source resolves -- launched harness only).
    # No plane square — the contour band on the liver IS the plane
    # visualisation.
    expected = 3 + (1 if rep.GetSurfacePreviewActor() is not None else 0)
    assert renderer.GetActors().GetNumberOfItems() == expected

    rep.cleanup()
    assert renderer.GetActors().GetNumberOfItems() == 0

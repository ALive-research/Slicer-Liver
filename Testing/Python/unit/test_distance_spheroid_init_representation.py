# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Python unit tests for ``DistanceSpheroidInitRepresentation`` — T2.2 stack, iteration 3.

Per ADR-0008 §2, Representations are the smallest unit-testable VTK
assembly; they have no Slicer dependency and a small, well-defined
API surface.  These tests construct the Representation with stub
data and display nodes, drive ``update()``, and assert that the
mapper / actor outputs reflect the stubs' contents.

Two layers of assertions:

* Pure-Python checks against the introspection helpers
  (``GetCurrentColor``, ``GetCurrentOpacity``, ``GetInputRefreshCount``).
  These work whether or not VTK is importable, so the test suite
  yields meaningful signal in CI environments where VTK is
  unavailable.

* VTK-mediated checks against the actual ``vtkActor`` /
  ``vtkPolyDataMapper`` / ``vtkParametricEllipsoid`` outputs.  Gated
  on ``pytest.importorskip("vtk")``.

References
----------
* ADR-0008 §2 — Representation tests, unit layer.
* ADR-0013 §6 — Representations as composable VTK pipelines.
* ADR-0014 §2 — names the DistanceSpheroidInit Representation.
* ADR-0014 §4 — data-node accessor surface this Representation reads.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

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
# Stub nodes — minimal API matching ADR-0014 §4's accessor surface on
# vtkMRMLBezierSurfaceNode + its paired display node.
# --------------------------------------------------------------------------- #


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
        center: tuple = (0.0, 0.0, 0.0),
        radius_x: float = 1.0,
        radius_y: float = 1.0,
        radius_z: float = 1.0,
        init_points: tuple = (
            (1.0, 0.0, 0.0),
            (-1.0, 0.0, 0.0),
        ),
    ) -> None:
        self.center = center
        self.radius_x = radius_x
        self.radius_y = radius_y
        self.radius_z = radius_z
        self.init_points = tuple(init_points)

    def GetDistanceSpheroidCenter(self):
        return self.center

    def GetDistanceSpheroidRadiusX(self) -> float:
        return self.radius_x

    def GetDistanceSpheroidRadiusY(self) -> float:
        return self.radius_y

    def GetDistanceSpheroidRadiusZ(self) -> float:
        return self.radius_z

    def GetNumberOfDistanceSpheroidInitPoints(self) -> int:
        return len(self.init_points)

    def GetDistanceSpheroidInitPoint(self, index: int):
        return self.init_points[index]


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def rep_module():
    """Return a factory that constructs the Representation with an injected mapper.

    The custom ``vtkOpenGLDistanceContourPolyDataMapper`` (the spheroid
    contour mapper) is off the path in the bare-VTK unit layer (ADR-0008 §2),
    so production's resolve-or-raise path cannot run here; each construction
    injects a generic ``vtkPolyDataMapper`` instance via the
    ``spheroid_mapper`` seam (ADR-0014 §3).  The sphere-marker mappers are
    genuinely generic and unaffected.
    """
    import vtk

    from Representations.DistanceSpheroidInitRepresentation import (
        DistanceSpheroidInitRepresentation,
    )

    def _make_rep(renderer=None):
        return DistanceSpheroidInitRepresentation(
            renderer, spheroid_mapper=vtk.vtkPolyDataMapper()
        )

    return _make_rep


# --------------------------------------------------------------------------- #
# Pure-Python assertions (run with or without VTK)
# --------------------------------------------------------------------------- #


def test_representation_construct_with_no_renderer(rep_module):
    """Construct without a renderer — no exception, default state set."""
    rep = rep_module()
    assert rep.GetRenderer() is None
    # Defaults match the legacy ResectionNode constructor.
    assert rep.GetCurrentColor() == (1.0, 1.0, 1.0)
    assert rep.GetCurrentOpacity() == pytest.approx(1.0)
    assert rep.GetInputRefreshCount() == 0
    # Markers are data-driven; none until ``update()`` reads the node.
    assert rep.GetMarkerActors() == []
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


def test_representation_update_with_none_data_is_noop(rep_module):
    """``update(display, None)`` does not raise — refresh count unchanged."""
    rep = rep_module()
    display = _StubDisplayNode(color=(0.25, 0.5, 0.75), opacity=0.5)
    rep.update(display, data_node=None)
    # Decoration is still applied even when geometry is unavailable.
    assert rep.GetCurrentColor() == (0.25, 0.5, 0.75)
    assert rep.GetCurrentOpacity() == pytest.approx(0.5)
    # But no input refresh fired.
    assert rep.GetInputRefreshCount() == 0
    rep.cleanup()


def test_representation_color_round_trip(rep_module):
    """Mutating the display node's ResectionColor changes the introspection
    helper after ``update()``."""
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
    """ResectionOpacity flows through ``update()`` to the introspection
    helper."""
    rep = rep_module()
    display = _StubDisplayNode(opacity=0.5)
    rep.update(display, _StubDataNode())
    assert rep.GetCurrentOpacity() == pytest.approx(0.5)
    rep.cleanup()


def test_representation_input_refresh_on_geometry_change(rep_module):
    """Mutating Center / Radii / init points increments the refresh counter."""
    rep = rep_module()
    display = _StubDisplayNode()
    data = _StubDataNode(
        center=(10.0, 0.0, 0.0),
        radius_x=2.0,
        radius_y=3.0,
        radius_z=4.0,
        init_points=((11.0, 0.0, 0.0), (9.0, 0.0, 0.0)),
    )
    rep.update(display, data)
    after_first = rep.GetInputRefreshCount()
    assert after_first == 1, (
        "first update() with a non-default geometry must refresh"
    )

    # Re-running update() with the same inputs is a no-op (memoised).
    rep.update(display, data)
    assert rep.GetInputRefreshCount() == after_first

    # Mutating the Center forces a refresh.
    data.center = (20.0, 0.0, 0.0)
    rep.update(display, data)
    assert rep.GetInputRefreshCount() == after_first + 1

    # Mutating a Radius forces a refresh.
    data.radius_x = 5.0
    rep.update(display, data)
    assert rep.GetInputRefreshCount() == after_first + 2

    # Mutating an init point forces a refresh.
    data.init_points = ((21.0, 0.0, 0.0), (19.0, 0.0, 0.0))
    rep.update(display, data)
    assert rep.GetInputRefreshCount() == after_first + 3
    rep.cleanup()


# --------------------------------------------------------------------------- #
# VTK-mediated assertions
# --------------------------------------------------------------------------- #


@pytest.fixture
def vtk_module():
    """Import the ``vtk`` module or skip the test."""
    return pytest.importorskip(
        "vtk",
        reason=(
            "vtk not importable; skip the VTK-mediated Representation "
            "tests.  Run inside Slicer's Python or in any environment "
            "where the bundled vtk wheel is on sys.path."
        ),
    )


def test_representation_spheroid_color_matches_display_node(
    rep_module, vtk_module
):
    """After ``update()``, the spheroid actor's property carries the
    display node's ResectionColor + ResectionOpacity."""
    rep = rep_module()
    display = _StubDisplayNode(color=(0.25, 0.5, 0.75), opacity=0.42)
    rep.update(display, _StubDataNode())

    spheroid = rep.GetSpheroidActor()
    assert spheroid is not None
    prop_color = spheroid.GetProperty().GetColor()
    assert list(prop_color) == pytest.approx([0.25, 0.5, 0.75])
    assert spheroid.GetProperty().GetOpacity() == pytest.approx(0.42)
    rep.cleanup()


def test_representation_markers_color_matches_display_but_opaque(
    rep_module, vtk_module
):
    """Markers inherit ResectionColor but stay fully opaque (per the
    Representation's docstring — translucent markers would disappear
    against the translucent spheroid)."""
    rep = rep_module()
    display = _StubDisplayNode(color=(0.25, 0.5, 0.75), opacity=0.3)
    data = _StubDataNode(
        init_points=((1.0, 2.0, 3.0), (4.0, 5.0, 6.0), (7.0, 8.0, 9.0))
    )
    rep.update(display, data)

    actors = rep.GetMarkerActors()
    assert len(actors) == 3
    for actor in actors:
        prop_color = actor.GetProperty().GetColor()
        assert list(prop_color) == pytest.approx([0.25, 0.5, 0.75])
        # Full opacity regardless of spheroid translucency.
        assert actor.GetProperty().GetOpacity() == pytest.approx(1.0)
    rep.cleanup()


def test_representation_spheroid_radii_match_data_node(
    rep_module, vtk_module
):
    """The parametric ellipsoid's X / Y / Z radii reflect the data node."""
    rep = rep_module()
    display = _StubDisplayNode()
    data = _StubDataNode(radius_x=2.5, radius_y=3.5, radius_z=4.5)
    rep.update(display, data)

    ellipsoid = rep.GetParametricEllipsoid()
    assert ellipsoid is not None
    assert ellipsoid.GetXRadius() == pytest.approx(2.5)
    assert ellipsoid.GetYRadius() == pytest.approx(3.5)
    assert ellipsoid.GetZRadius() == pytest.approx(4.5)
    rep.cleanup()


def test_representation_marker_count_matches_data_node(
    rep_module, vtk_module
):
    """Marker actor count tracks ``GetNumberOfDistanceSpheroidInitPoints``."""
    rep = rep_module()
    display = _StubDisplayNode()
    points = ((1.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    rep.update(display, _StubDataNode(init_points=points))
    assert len(rep.GetMarkerActors()) == 3


def test_representation_marker_count_grows(rep_module, vtk_module):
    """Increasing init-point count from 2 to 5 grows the marker list."""
    rep = rep_module()
    display = _StubDisplayNode()
    data = _StubDataNode(init_points=((1.0, 0.0, 0.0), (-1.0, 0.0, 0.0)))
    rep.update(display, data)
    assert len(rep.GetMarkerActors()) == 2

    data.init_points = (
        (1.0, 0.0, 0.0),
        (-1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, -1.0, 0.0),
        (0.0, 0.0, 1.0),
    )
    rep.update(display, data)
    assert len(rep.GetMarkerActors()) == 5
    rep.cleanup()


def test_representation_marker_count_shrinks(rep_module, vtk_module):
    """Decreasing init-point count from 5 to 2 shrinks the marker list
    and detaches the removed actors from the renderer."""
    rep = rep_module()
    renderer = vtk_module.vtkRenderer()
    rep.SetRenderer(renderer)
    display = _StubDisplayNode()
    data = _StubDataNode(
        init_points=(
            (1.0, 0.0, 0.0),
            (-1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, -1.0, 0.0),
            (0.0, 0.0, 1.0),
        )
    )
    rep.update(display, data)
    assert len(rep.GetMarkerActors()) == 5
    # 1 spheroid + 5 markers = 6 actors on the renderer.
    assert renderer.GetActors().GetNumberOfItems() == 6

    data.init_points = ((1.0, 0.0, 0.0), (-1.0, 0.0, 0.0))
    rep.update(display, data)
    assert len(rep.GetMarkerActors()) == 2
    # 1 spheroid + 2 markers = 3 actors on the renderer.
    assert renderer.GetActors().GetNumberOfItems() == 3
    rep.cleanup()


def test_representation_marker_centers_match_init_points(
    rep_module, vtk_module
):
    """Each marker's sphere centre matches the corresponding init point."""
    rep = rep_module()
    display = _StubDisplayNode()
    points = ((1.0, 2.0, 3.0), (4.0, 5.0, 6.0), (7.0, 8.0, 9.0))
    rep.update(display, _StubDataNode(init_points=points))

    actors = rep.GetMarkerActors()
    # Reach back to the sphere sources via the introspection — pull
    # them off the mapper's input connection's producer.
    for actor, expected in zip(actors, points):
        mapper = actor.GetMapper()
        # Resolve the upstream vtkSphereSource via the algorithm input.
        producer = mapper.GetInputAlgorithm()
        center = producer.GetCenter()
        assert list(center) == pytest.approx(list(expected))
    rep.cleanup()


def test_representation_attach_detach_renderer(rep_module, vtk_module):
    """``SetRenderer(r)`` adds the spheroid + marker actors; ``cleanup()``
    removes them."""
    rep = rep_module()
    renderer = vtk_module.vtkRenderer()
    assert renderer.GetActors().GetNumberOfItems() == 0

    rep.SetRenderer(renderer)
    # Pre-update: only the spheroid is on the renderer (markers are
    # data-driven and have not been populated yet).
    assert renderer.GetActors().GetNumberOfItems() == 1

    display = _StubDisplayNode()
    data = _StubDataNode(
        init_points=((1.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    )
    rep.update(display, data)
    # 1 spheroid + 3 markers = 4 actors.
    assert renderer.GetActors().GetNumberOfItems() == 4

    rep.cleanup()
    # cleanup() detaches both and the renderer is empty again.
    assert renderer.GetActors().GetNumberOfItems() == 0


def test_representation_idempotent_no_refresh_on_unchanged_inputs(
    rep_module, vtk_module
):
    """A second ``update()`` with unchanged inputs is a no-op — refresh
    count does not advance, polydata is not re-emitted."""
    rep = rep_module()
    display = _StubDisplayNode()
    data = _StubDataNode(
        center=(5.0, 5.0, 5.0),
        radius_x=2.0,
        radius_y=3.0,
        radius_z=4.0,
        init_points=((6.0, 5.0, 5.0), (4.0, 5.0, 5.0)),
    )
    rep.update(display, data)
    after_first = rep.GetInputRefreshCount()
    rep.update(display, data)
    rep.update(display, data)
    assert rep.GetInputRefreshCount() == after_first
    rep.cleanup()


def test_representation_refresh_advances_on_any_input_change(
    rep_module, vtk_module
):
    """Each distinct mutation of the geometry inputs advances the
    counter; ``vtkParametricEllipsoid`` radii follow."""
    rep = rep_module()
    display = _StubDisplayNode()
    data = _StubDataNode(
        center=(0.0, 0.0, 0.0),
        radius_x=1.0,
        radius_y=1.0,
        radius_z=1.0,
        init_points=((1.0, 0.0, 0.0), (-1.0, 0.0, 0.0)),
    )
    rep.update(display, data)
    n = rep.GetInputRefreshCount()

    data.radius_y = 2.0
    rep.update(display, data)
    assert rep.GetInputRefreshCount() == n + 1
    assert rep.GetParametricEllipsoid().GetYRadius() == pytest.approx(2.0)
    rep.cleanup()

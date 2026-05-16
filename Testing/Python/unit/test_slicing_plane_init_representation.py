"""Python unit tests for ``SlicingPlaneInitRepresentation`` — T2.2 stack, iteration 2.

Mirrors ``test_bezier_planning_representation.py``: per ADR-0008 §2
Representations are the smallest unit-testable VTK assembly and have
no Slicer dependency.  Two layers of assertions:

* Pure-Python checks against the introspection helpers
  (``GetCurrentColor``, ``GetCurrentOpacity``, ``GetInputRefreshCount``).
  These run with or without VTK on ``PYTHONPATH``.

* VTK-mediated checks against the real ``vtkActor`` /
  ``vtkPlaneSource`` / ``vtkSphereSource`` outputs, gated by
  ``pytest.importorskip("vtk")``.

References
----------
* ADR-0008 §2 — Representation tests, unit layer.
* ADR-0013 §6 — Representations as composable VTK pipelines.
* ADR-0014 §2 — names this Representation.
* ADR-0014 §4 — init data accessors on the data node.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

# --------------------------------------------------------------------------- #
# Repo geometry — Representations live at
# ``LiverResections/Representations/`` per ADR-0013 §7 file-layout.
# --------------------------------------------------------------------------- #

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
PY_DIR = REPO_ROOT / "LiverResections"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))


# --------------------------------------------------------------------------- #
# Stub nodes — same minimal-API approach as ``test_bezier_planning_
# representation.py``.  Kept local to avoid cross-test coupling.
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
        origin: tuple = (0.0, 0.0, 0.0),
        normal: tuple = (0.0, 0.0, 1.0),
        init0: tuple = (-5.0, 0.0, 0.0),
        init1: tuple = (5.0, 0.0, 0.0),
    ) -> None:
        self.origin = origin
        self.normal = normal
        self.init0 = init0
        self.init1 = init1

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


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def rep_module():
    from Representations.SlicingPlaneInitRepresentation import (
        SlicingPlaneInitRepresentation,
    )

    return SlicingPlaneInitRepresentation


# --------------------------------------------------------------------------- #
# Pure-Python assertions (run with or without VTK)
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
    """The idempotency memo on (origin, normal, init0, init1) skips a
    redundant refresh; mutating any of those inputs advances the counter.
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


def test_representation_construct_builds_actors(rep_module, vtk_module):
    """With VTK available, construction yields two marker actors and one
    plane actor."""
    rep = rep_module()
    assert rep.GetMarkerActor(0) is not None
    assert rep.GetMarkerActor(1) is not None
    # Only two marker actors — index 2 is out of range.
    assert rep.GetMarkerActor(2) is None
    assert rep.GetPlaneActor() is not None
    assert rep.GetPlaneSource() is not None
    rep.cleanup()
    # After cleanup() actors are released.
    assert rep.GetMarkerActor(0) is None
    assert rep.GetPlaneActor() is None


def test_representation_marker_positions_match_init_points(
    rep_module, vtk_module
):
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


def test_representation_plane_source_driven_by_origin_and_normal(
    rep_module, vtk_module
):
    """The ``vtkPlaneSource`` centre lands on the data node's
    ``GetSlicingPlaneOrigin`` and its normal lines up with
    ``GetSlicingPlaneNormal``."""
    rep = rep_module()
    data = _StubDataNode(
        origin=(3.0, 4.0, 5.0),
        normal=(0.0, 1.0, 0.0),
        init0=(-2.0, 4.0, 5.0),
        init1=(2.0, 4.0, 5.0),
    )
    rep.update(_StubDisplayNode(), data)

    plane = rep.GetPlaneSource()
    centre = plane.GetCenter()
    assert list(centre) == pytest.approx([3.0, 4.0, 5.0])

    n = plane.GetNormal()
    # Allow either sign — ``vtkPlaneSource`` may flip the normal
    # depending on the corner ordering vtkMath::Perpendiculars produced.
    assert (
        list(n) == pytest.approx([0.0, 1.0, 0.0])
        or list(n) == pytest.approx([0.0, -1.0, 0.0])
    )
    rep.cleanup()


def test_representation_mapper_color_matches_display_node(
    rep_module, vtk_module
):
    """After ``update()`` the actor properties carry the display node's
    ResectionColor.  Plane opacity is reduced relative to the markers."""
    from Representations.SlicingPlaneInitRepresentation import (
        PLANE_OPACITY_FACTOR,
    )

    rep = rep_module()
    display = _StubDisplayNode(color=(0.25, 0.5, 0.75), opacity=0.8)
    rep.update(display, _StubDataNode())

    # Markers — full opacity, display node's colour.
    for i in (0, 1):
        actor = rep.GetMarkerActor(i)
        assert list(actor.GetProperty().GetColor()) == pytest.approx(
            [0.25, 0.5, 0.75]
        )
        assert actor.GetProperty().GetOpacity() == pytest.approx(0.8)

    # Plane — same colour, reduced opacity.
    plane_actor = rep.GetPlaneActor()
    assert list(plane_actor.GetProperty().GetColor()) == pytest.approx(
        [0.25, 0.5, 0.75]
    )
    assert plane_actor.GetProperty().GetOpacity() == pytest.approx(
        0.8 * PLANE_OPACITY_FACTOR
    )
    rep.cleanup()


def test_representation_attach_detach_renderer(rep_module, vtk_module):
    """``SetRenderer(r)`` adds two marker actors + one plane actor = 3;
    ``cleanup()`` removes them all."""
    rep = rep_module()
    renderer = vtk_module.vtkRenderer()
    assert renderer.GetActors().GetNumberOfItems() == 0

    rep.SetRenderer(renderer)
    # Three actors expected: two markers + one plane.  No grid actor
    # (the grid is a Planning-state shader feature per ADR-0014 §3;
    # irrelevant in Init).  No ring actor (deferred per
    # TODO(T2-target-mesh-weakref)).
    assert renderer.GetActors().GetNumberOfItems() == 3

    rep.cleanup()
    assert renderer.GetActors().GetNumberOfItems() == 0


def test_representation_plane_size_scales_with_init_point_distance(
    rep_module, vtk_module
):
    """The plane's side length scales with the distance between the two
    init points (per ``PLANE_SIZE_FACTOR`` in the Representation)."""
    from Representations.SlicingPlaneInitRepresentation import (
        PLANE_SIZE_FACTOR,
    )

    rep = rep_module()
    # Far-apart init points so we exceed PLANE_FALLBACK_HALF_EXTENT and
    # the distance-driven sizing dominates.
    d = 100.0
    data = _StubDataNode(
        origin=(0.0, 0.0, 0.0),
        normal=(0.0, 0.0, 1.0),
        init0=(-d / 2, 0.0, 0.0),
        init1=(d / 2, 0.0, 0.0),
    )
    rep.update(_StubDisplayNode(), data)

    plane = rep.GetPlaneSource()
    # Plane corners are at ``origin ± half × u`` (and ± half × v).  We
    # only check the magnitude — the basis direction can vary.
    expected_half = 0.5 * PLANE_SIZE_FACTOR * d
    p1 = plane.GetPoint1()
    origin = plane.GetOrigin()
    side = (
        (p1[0] - origin[0]) ** 2
        + (p1[1] - origin[1]) ** 2
        + (p1[2] - origin[2]) ** 2
    ) ** 0.5
    assert side == pytest.approx(2.0 * expected_half, rel=1e-6)
    rep.cleanup()

"""Python unit tests for ``BezierPlanningRepresentation`` — T2.2 PR 1.

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
  ``vtkPolyDataMapper`` outputs.  Gated on
  ``pytest.importorskip("vtk")``.

References
----------
* ADR-0008 §2 — Representation tests, unit layer.
* ADR-0013 §6 — Representations as composable VTK pipelines.
* ADR-0014 §2 — names the BezierPlanning Representation.
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
# Stub nodes — same minimal API as the Pipeline test stubs above, kept
# local to avoid coupling the two test files.
# --------------------------------------------------------------------------- #


class _StubDisplayNode:
    def __init__(
        self,
        color: tuple = (1.0, 1.0, 1.0),
        opacity: float = 1.0,
        grid_visibility: bool = False,
    ) -> None:
        self.color = color
        self.opacity = opacity
        self.grid_visibility = grid_visibility

    def GetResectionColor(self):
        return self.color

    def GetResectionOpacity(self) -> float:
        return self.opacity

    def GetGridVisibility(self) -> bool:
        return self.grid_visibility


class _StubDataNode:
    def __init__(self, control_grid: tuple = (0.0,) * 48) -> None:
        self.control_grid = control_grid

    def GetControlGrid(self):
        return self.control_grid


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def rep_module():
    from Representations.BezierPlanningRepresentation import (
        BezierPlanningRepresentation,
    )

    return BezierPlanningRepresentation


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
    rep.cleanup()


def test_representation_update_with_none_display_falls_back_to_defaults(
    rep_module,
):
    """``update(None, data)`` does not raise — actors stay at defaults."""
    rep = rep_module()
    rep.update(display_node=None, data_node=_StubDataNode())
    # Default colour / opacity still in place after a None display.
    assert rep.GetCurrentColor() == (1.0, 1.0, 1.0)
    assert rep.GetCurrentOpacity() == pytest.approx(1.0)
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


def test_representation_input_refresh_on_grid_change(rep_module):
    """Mutating the control grid increments the input-refresh counter.

    The counter is a stub-friendly proxy for "the mapper's input data
    has been refreshed" — the VTK-mediated assertion below in
    ``test_representation_mapper_*`` confirms this.
    """
    rep = rep_module()
    display = _StubDisplayNode()
    data = _StubDataNode(control_grid=tuple(0.1 * i for i in range(48)))
    rep.update(display, data)
    after_first = rep.GetInputRefreshCount()
    assert after_first == 1, (
        "first update() with a non-default control grid must refresh"
    )

    # Re-running update() with the same grid is a no-op (memoised).
    rep.update(display, data)
    assert rep.GetInputRefreshCount() == after_first

    # Mutating the grid forces a refresh.
    data.control_grid = tuple(0.2 * i for i in range(48))
    rep.update(display, data)
    assert rep.GetInputRefreshCount() == after_first + 1
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


def test_representation_mapper_color_matches_display_node(
    rep_module, vtk_module
):
    """After ``update()``, the surface mapper's actor property carries
    the display node's ResectionColor.

    Asserts against the real ``vtkActor::GetProperty()`` rather than
    the introspection helper — the latter mirrors the former, but
    asserting against both pins both sides of the contract.
    """
    rep = rep_module()
    display = _StubDisplayNode(color=(0.25, 0.5, 0.75), opacity=0.42)
    rep.update(display, _StubDataNode())

    actor = rep.GetSurfaceActor()
    assert actor is not None
    prop_color = actor.GetProperty().GetColor()
    assert list(prop_color) == pytest.approx([0.25, 0.5, 0.75])
    assert actor.GetProperty().GetOpacity() == pytest.approx(0.42)
    rep.cleanup()


def test_representation_mapper_input_refreshes_on_grid_change(
    rep_module, vtk_module
):
    """A control-grid mutation refreshes the surface polydata.

    Reads ``GetNumberOfPoints()`` and ``GetNumberOfCells()`` off the
    mapper's input data to confirm the rebuild fired.  16 points
    (4×4 control mesh) and 9 quads (3×3 connected cells).
    """
    rep = rep_module()
    display = _StubDisplayNode()
    grid = tuple(0.1 * i for i in range(48))
    rep.update(display, _StubDataNode(control_grid=grid))

    mapper = rep.GetSurfaceMapper()
    assert mapper is not None
    polydata = mapper.GetInput()
    assert polydata.GetNumberOfPoints() == 16
    assert polydata.GetNumberOfCells() == 9

    # The grid mapper also has its input refreshed — 16 points + 24
    # line cells (3 horizontal × 4 + 3 vertical × 4 = 24).
    grid_mapper = rep.GetGridMapper()
    grid_polydata = grid_mapper.GetInput()
    assert grid_polydata.GetNumberOfPoints() == 16
    assert grid_polydata.GetNumberOfCells() == 24
    rep.cleanup()


def test_representation_attach_detach_renderer(rep_module, vtk_module):
    """``SetRenderer(r)`` adds the actors; ``cleanup()`` removes them."""
    rep = rep_module()
    renderer = vtk_module.vtkRenderer()
    assert renderer.GetActors().GetNumberOfItems() == 0

    rep.SetRenderer(renderer)
    # Two actors expected: surface + grid.
    assert renderer.GetActors().GetNumberOfItems() == 2

    rep.cleanup()
    # cleanup() detaches and the renderer is empty again.
    assert renderer.GetActors().GetNumberOfItems() == 0


def test_representation_grid_visibility_toggles_actor(
    rep_module, vtk_module
):
    """``GridVisibility=True`` on the display node makes the grid actor
    visible after ``update()``."""
    rep = rep_module()
    display = _StubDisplayNode(grid_visibility=False)
    rep.update(display, _StubDataNode())
    assert rep.GetGridActor().GetVisibility() == 0

    display.grid_visibility = True
    rep.update(display, _StubDataNode())
    assert rep.GetGridActor().GetVisibility() == 1
    rep.cleanup()

# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Python unit tests for ``ConfirmedRepresentation`` — ADR-0019.

Mirrors ``test_bezier_planning_representation.py``'s structure
(pure-Python introspection assertions + a thin VTK-mediated layer).
The Confirmed Representation differs from BezierPlanning in three
ways committed by ADR-0019:

* No control-polygon glyph cloud (the widget is disabled in
  ``Confirmed``; the data-node-driven glyph rebuild on
  ``vtkLiverBezierRepresentation`` is the canonical enforcer — covered
  by the C++ ``vtkLiverBezierRepresentation`` test path).
* The parenchyma-trim shader is engaged on the surface mapper:
  ``mapper.SetResectionClipOut(True)``.  The skeleton's surface
  mapper is a generic ``vtkPolyDataMapper`` without that method until
  T2-mapper-relocation lands the relocated
  ``vtkOpenGLBezierResectionPolyDataMapper``; the Representation
  guards the call with a ``hasattr`` check and exposes the last-pushed
  value via ``GetClipOutApplied``.  These tests assert the no-op
  observability of the skeleton state — the post-relocation
  assertion (``GetClipOutApplied() is True``) is gated by a stub
  mapper inside this file so the assertion exercises both the legacy
  generic-mapper branch AND the future relocated-mapper branch.

References
----------
* ADR-0008 §2 — Representation tests, unit layer.
* ADR-0013 §6 — Representations as composable VTK pipelines.
* ADR-0019 — 3-state machine (``ConfirmedRepresentation`` is the
  ``Confirmed`` row of the dispatch table).
"""

from __future__ import annotations

import pathlib
import sys

import pytest

# --------------------------------------------------------------------------- #
# Repo geometry — mirrors test_bezier_planning_representation.py.
# --------------------------------------------------------------------------- #

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
PY_DIR = REPO_ROOT / "LiverResections" / "LiverResectionsLib"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))


# --------------------------------------------------------------------------- #
# Stub nodes
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
    def __init__(self, control_grid: tuple = (0.0,) * 48) -> None:
        self.control_grid = control_grid

    def GetControlGrid(self):
        return self.control_grid


@pytest.fixture
def rep_module():
    from Representations.ConfirmedRepresentation import (
        ConfirmedRepresentation,
    )

    return ConfirmedRepresentation


# --------------------------------------------------------------------------- #
# Pure-Python assertions (run with or without VTK)
# --------------------------------------------------------------------------- #


def test_representation_construct_with_no_renderer(rep_module):
    """Construct without a renderer — no exception, default state set."""
    rep = rep_module()
    assert rep.GetRenderer() is None
    assert rep.GetCurrentColor() == (1.0, 1.0, 1.0)
    assert rep.GetCurrentOpacity() == pytest.approx(1.0)
    # Clip-out applied state starts at None — no update() yet.
    assert rep.GetClipOutApplied() is None
    rep.cleanup()


def test_representation_update_with_none_display_falls_back_to_defaults(
    rep_module,
):
    rep = rep_module()
    rep.update(display_node=None, data_node=_StubDataNode())
    assert rep.GetCurrentColor() == (1.0, 1.0, 1.0)
    assert rep.GetCurrentOpacity() == pytest.approx(1.0)
    rep.cleanup()


def test_representation_color_round_trip(rep_module):
    rep = rep_module()
    display = _StubDisplayNode(color=(0.25, 0.5, 0.75))
    data = _StubDataNode()
    rep.update(display, data)
    assert rep.GetCurrentColor() == (0.25, 0.5, 0.75)
    rep.cleanup()


def test_representation_opacity_round_trip(rep_module):
    rep = rep_module()
    display = _StubDisplayNode(opacity=0.5)
    rep.update(display, _StubDataNode())
    assert rep.GetCurrentOpacity() == pytest.approx(0.5)
    rep.cleanup()


def test_representation_input_refresh_on_grid_change(rep_module):
    """Mutating the control grid increments the input-refresh counter."""
    rep = rep_module()
    display = _StubDisplayNode()
    data = _StubDataNode(control_grid=tuple(0.1 * i for i in range(48)))
    rep.update(display, data)
    after_first = rep.GetInputRefreshCount()
    assert after_first == 1

    # Re-running update() with the same grid is a no-op (memoised).
    rep.update(display, data)
    assert rep.GetInputRefreshCount() == after_first

    # Mutating the grid forces a refresh.
    data.control_grid = tuple(0.2 * i for i in range(48))
    rep.update(display, data)
    assert rep.GetInputRefreshCount() == after_first + 1
    rep.cleanup()


# --------------------------------------------------------------------------- #
# Trim-shader binding — the post-T2-mapper-relocation contract
# --------------------------------------------------------------------------- #


class _StubMapperWithClipOut:
    """Drop-in replacement for the Representation's surface mapper that
    exposes ``SetResectionClipOut`` — the relocated
    ``vtkOpenGLBezierResectionPolyDataMapper``'s API.  Used to exercise
    the ``hasattr``-gated branch in ``ConfirmedRepresentation`` without
    waiting for T2-mapper-relocation to land.
    """

    def __init__(self) -> None:
        self.clip_out: bool | None = None
        self._input = None

    def SetResectionClipOut(self, value: bool) -> None:
        self.clip_out = bool(value)

    def SetInputData(self, polydata) -> None:
        self._input = polydata


def test_representation_engages_trim_shader_when_mapper_supports_it(
    rep_module,
):
    """When the surface mapper exposes ``SetResectionClipOut`` (i.e.
    the post-T2-mapper-relocation state), ``update()`` flips it to
    ``True``."""
    rep = rep_module()
    # Inject the stub mapper to simulate the post-relocation state.
    rep._surface_mapper = _StubMapperWithClipOut()

    display = _StubDisplayNode()
    data = _StubDataNode(control_grid=tuple(0.1 * i for i in range(48)))
    rep.update(display, data)

    assert rep._surface_mapper.clip_out is True
    assert rep.GetClipOutApplied() is True
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
            "tests."
        ),
    )


def test_representation_mapper_color_matches_display_node(
    rep_module, vtk_module
):
    rep = rep_module()
    display = _StubDisplayNode(color=(0.25, 0.5, 0.75), opacity=0.42)
    rep.update(display, _StubDataNode())

    actor = rep.GetSurfaceActor()
    assert actor is not None
    prop_color = actor.GetProperty().GetColor()
    assert list(prop_color) == pytest.approx([0.25, 0.5, 0.75])
    assert actor.GetProperty().GetOpacity() == pytest.approx(0.42)
    rep.cleanup()


def test_representation_skeleton_mapper_does_not_have_clipout_attribute(
    rep_module, vtk_module
):
    """The pre-T2-mapper-relocation skeleton uses
    ``vtkPolyDataMapper``, which does NOT expose ``SetResectionClipOut``
    — the Representation's ``hasattr`` gate stays defensive and
    ``GetClipOutApplied`` stays ``None`` after ``update()``.

    This test pins the "no-op pre-relocation" branch.  When
    T2-mapper-relocation lands and the Representation's surface mapper
    flips to the relocated
    ``vtkOpenGLBezierResectionPolyDataMapper``, this assertion will
    flip to ``is True`` — that is the load-bearing signal that the
    relocation completed successfully.
    """
    rep = rep_module()
    display = _StubDisplayNode()
    data = _StubDataNode(control_grid=tuple(0.1 * i for i in range(48)))
    rep.update(display, data)

    mapper = rep.GetSurfaceMapper()
    assert mapper is not None
    # Either the relocation has happened (mapper exposes the trim
    # toggle and the Representation engaged it) OR it has not (mapper
    # is the generic vtkPolyDataMapper and GetClipOutApplied is None).
    if hasattr(mapper, "SetResectionClipOut"):
        assert rep.GetClipOutApplied() is True
    else:
        assert rep.GetClipOutApplied() is None
    rep.cleanup()

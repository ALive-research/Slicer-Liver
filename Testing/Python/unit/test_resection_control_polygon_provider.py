# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Seam pins for ``ResectionControlPolygonProvider`` (ADR-0038 §Decision).

Resection is the extraction-source client of the shared
``SurfacePointPlacementPipeline3D`` base; this adapter is the resection
side of the ``PointProvider`` seam over the Bezier control grid.  These
pins fix the RESECTION-specific data-model behaviour the base reads/writes
(ADR-0038 §"What is not shared"):

* ``iter_points`` fans the flat ``Rows x Cols`` grid out in row-major order
  (so the base's ``enumerate`` key IS the flat grid index) with the display
  node's per-handle colour;
* ``has_edges()`` is True (the grid is a connected polygon -- resection,
  not the flat territory/volumetry sets);
* ``move_point`` writes ``SetControlPoint`` ONLY in ``Planning`` (ADR-0019
  read-only-after-commit) and refuses in Init / Confirmed;
* ``add_point`` / ``delete_point`` are no-ops -- the control grid is fixed
  (no add-on-click, no per-handle delete).

Pure Python over a carrier stub -- runs in the bare-VTK unit layer (no
Slicer, no wrapped MRML), so it is the one piece of this refactor that is
GREEN under bare ``PythonSlicer -m pytest``; the pipeline's own
characterization suites need LayerDMLib and are launched-only.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
PY_DIR = REPO_ROOT / "LiverResections" / "LiverResectionsLib"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

import ResectionControlPolygonProvider as mod  # noqa: E402 - after path insert

STATE_INIT = 0
STATE_PLANNING = 1
STATE_CONFIRMED = 2


class _StubCarrier:
    """vtkMRMLBezierSurfaceNode-shaped stub: a flat row-major control grid."""

    def __init__(self, rows=4, cols=4, state=STATE_PLANNING):
        self._rows = rows
        self._cols = cols
        self._state = state
        # A distinct lattice so nearest / ordering is unambiguous.
        self._grid = []
        for r in range(rows):
            for c in range(cols):
                self._grid += [float(c) * 10.0, float(r) * 10.0, 5.0]

    def GetRows(self):  # noqa: N802 - VTK verb
        return self._rows

    def GetCols(self):  # noqa: N802 - VTK verb
        return self._cols

    def GetControlGridVector(self):  # noqa: N802 - VTK verb
        return list(self._grid)

    def GetState(self):  # noqa: N802 - VTK verb
        return self._state

    def SetState(self, state):  # noqa: N802 - VTK verb
        self._state = int(state)

    def SetControlPoint(self, row, col, x, y, z):  # noqa: N802 - VTK verb
        base = (row * self._cols + col) * 3
        self._grid[base] = float(x)
        self._grid[base + 1] = float(y)
        self._grid[base + 2] = float(z)


def _provider(carrier, color_getter=None):
    return mod.ResectionControlPolygonProvider(
        carrier_getter=lambda: carrier, color_getter=color_getter
    )


def test_iter_points_is_row_major_with_colour():
    """The base's enumerate key is the flat row-major grid index."""
    carrier = _StubCarrier()
    provider = _provider(carrier, color_getter=lambda: (0.1, 0.2, 0.3))

    points = list(provider.iter_points())
    assert len(points) == 16, "a 4x4 grid must fan out to 16 points"

    world5, rgb5 = points[5]  # row 1, col 1 on the seeded lattice
    assert world5 == pytest.approx((10.0, 10.0, 5.0)), (
        "point 5 must be the row-major (1, 1) control point"
    )
    assert rgb5 == pytest.approx((0.1, 0.2, 0.3)), (
        "the per-point base colour must be the display node's HandleColor"
    )


def test_iter_points_falls_back_to_neutral_colour():
    """No colour getter -> the neutral white base handle colour."""
    carrier = _StubCarrier()
    provider = _provider(carrier)
    _world, rgb = next(iter(provider.iter_points()))
    assert rgb == pytest.approx(mod.DEFAULT_HANDLE_RGB)


def test_has_edges_is_true():
    """Resection's grid IS a connected polygon (ADR-0038 §Context)."""
    assert _provider(_StubCarrier()).has_edges() is True


def test_move_point_writes_the_grid_in_planning():
    """A drag write relocates exactly the keyed control point in Planning."""
    carrier = _StubCarrier(state=STATE_PLANNING)
    provider = _provider(carrier)

    provider.move_point(5, (1.0, 2.0, 3.0))

    grid = carrier.GetControlGridVector()
    assert (grid[15], grid[16], grid[17]) == pytest.approx((1.0, 2.0, 3.0)), (
        "point 5 (flat index) must move to the world point"
    )
    assert (grid[0], grid[1], grid[2]) == pytest.approx((0.0, 0.0, 5.0)), (
        "no other point may move"
    )


@pytest.mark.parametrize("state", [STATE_INIT, STATE_CONFIRMED])
def test_move_point_refuses_outside_planning(state):
    """ADR-0019 read-only: a move outside Planning writes nothing."""
    carrier = _StubCarrier(state=state)
    provider = _provider(carrier)
    before = carrier.GetControlGridVector()

    provider.move_point(5, (99.0, 99.0, 99.0))

    assert carrier.GetControlGridVector() == before, (
        f"a move in state {state} must be a no-op (ADR-0019)"
    )


def test_add_and_delete_are_no_ops():
    """The control grid is FIXED -- no add-on-click, no per-handle delete."""
    carrier = _StubCarrier(state=STATE_PLANNING)
    provider = _provider(carrier)
    before = carrier.GetControlGridVector()

    assert provider.add_point((1.0, 2.0, 3.0)) is None
    assert provider.delete_point(5) is False
    assert carrier.GetControlGridVector() == before, (
        "add / delete must not mutate the fixed grid"
    )


def test_absent_carrier_is_a_clean_no_op():
    """A null carrier (late binding) yields nothing and writes nothing."""
    provider = mod.ResectionControlPolygonProvider(carrier_getter=lambda: None)
    assert list(provider.iter_points()) == []
    provider.move_point(0, (1.0, 1.0, 1.0))  # must not raise
    assert provider.add_point((1.0, 1.0, 1.0)) is None
    assert provider.delete_point(0) is False


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Ring membership for the control-polygon group-drag gestures.

A group translates RIGIDLY -- every member displaced by the same delta,
then the surface recomputed.  The load-bearing property is therefore
that the rings PARTITION the control grid: an id in two rings would be
displaced twice, an id in none would be left behind, and either tears
the surface.  Sizes alone do not catch that, so the partition is
asserted directly.

HARNESS: pure Python, no Slicer, no VTK, no scene.  RUNS BARE (ADR-0027).
"""

from __future__ import annotations

import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
LIB_DIR = REPO_ROOT / "LiverResections" / "LiverResectionsLib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))


def _rings_or_skip():
    try:
        import ControlPolygonRings
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(f"ControlPolygonRings not importable ({exc!r}) -- ADR-0027.")
    return ControlPolygonRings


@pytest.mark.parametrize(("rows", "cols"), [(4, 4), (3, 3)])
def test_rings_partition_the_control_grid(rows, cols):
    """Every control point belongs to exactly one rigid-translation group."""
    module = _rings_or_skip()
    rings = module.ring_groups(rows, cols)
    flat = [index for ring in rings for index in ring]

    assert sorted(flat) == list(range(rows * cols)), (
        "The rings must partition the grid: a duplicated id is displaced "
        "twice and a missing id is left behind -- either tears the surface."
    )


def test_four_by_four_outer_ring_is_a_clockwise_closed_walk():
    """The order is load-bearing: a highlight draws straight from it."""
    module = _rings_or_skip()
    outer, inner = module.ring_groups(4, 4)

    assert outer == (0, 1, 2, 3, 7, 11, 15, 14, 13, 12, 8, 4), (
        "The outer ring is consumed as a closed path by the ring "
        "highlight; a membership-only change would break the drawing."
    )
    assert inner == (5, 6, 10, 9)


def test_three_by_three_inner_group_is_the_single_centre_point():
    """The degenerate shape, pinned so a ring affordance expects it."""
    module = _rings_or_skip()
    outer, inner = module.ring_groups(3, 3)

    assert len(outer) == 8
    assert inner == (4,), (
        "A 3x3 has no interior ring -- only its centre point.  A "
        "one-element rigid-translation group is valid, but a caller "
        "presenting a ring affordance must expect it."
    )


@pytest.mark.parametrize(
    ("rows", "cols"), [(2, 2), (5, 5), (3, 4), (4, 3), (0, 0), (1, 1)]
)
def test_shapes_outside_the_adr_0018_set_yield_no_rings(rows, cols):
    """Out-of-spec grids render no group affordance rather than raising."""
    module = _rings_or_skip()
    assert module.ring_groups(rows, cols) == ()

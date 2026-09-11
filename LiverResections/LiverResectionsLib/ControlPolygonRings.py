# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Ring membership of a Bezier control polygon, for the group-drag gestures.

A group gesture translates a SET of control points rigidly -- every
member displaced by the same delta, then the surface recomputed.  Two
pipelines need the same memberships: ``ControlPolygonPipeline`` (3D) and
``SliceControlPolygonPipeline`` (its slice-view projection).  They live
here so the two cannot drift apart.

WHY CONSTANTS, NOT A COMPUTED DECOMPOSITION
-------------------------------------------
ADR-0018 §1 admits exactly two control-polygon shapes, ``(3, 3)`` and
``(4, 4)``, and each has exactly two rings -- so the memberships are
fixed.  A general peel-the-lattice algorithm would carry depth
arithmetic and degenerate single-row / single-column branches for shapes
this project does not allow.

WHY PYTHON, NOT THE ALGORITHM LIBRARY
-------------------------------------
The first attempt put this in ``vtkSlicerLiverBezierControlPolygonGeometry``
beside ``BuildControlPolygonCells``.  It returned
``std::vector<std::vector<vtkIdType>>``, which VTK's Python wrapper
SILENTLY SKIPS -- a flat ``std::vector<T>`` of scalars wraps, a nested
one does not.  The build stayed green, the C++ tests passed, and the
method simply did not exist from Python, where both consumers live.
(The same trap as the ``void*`` distance-map upload: compiles, links,
tests green, invisible from Python.)

Should a NURBS control net of arbitrary ``m x n`` ever need computed
rings, that is a C++ API designed against a real requirement -- with a
wrappable signature (``vtkIdList`` out-parameters) and a Python consumer
to prove it.

INDEXING
--------
Row-major, ``(i, j) -> i * cols + j``, matching
``vtkSlicerLiverBezierControlPolygonGeometry::BuildControlPolygonCells``.

Ring 0 is the OUTER ring, listed as a contiguous CLOCKWISE WALK from the
top-left corner, so a ring highlight can consume the order directly as a
closed path instead of re-deriving the traversal.  Ring 1 is the
interior.

A 3x3 grid's inner "ring" is the SINGLE centre point.  A one-element
rigid-translation group is well defined, but it is not a ring in any
geometric sense; a caller presenting a ring affordance should expect it.
The UI only ever produces 4x4 today (the init re-fit always does), but
3x3 is legal under ADR-0018.
"""

from __future__ import annotations

#: (rows, cols) -> tuple of rings, each a tuple of flat row-major ids.
#: Every id appears in exactly one ring: a group translates rigidly, so
#: an id in two rings would be displaced twice and an id in none would be
#: left behind -- either tears the surface.
RING_GROUPS: dict[tuple[int, int], tuple[tuple[int, ...], ...]] = {
    (4, 4): (
        (0, 1, 2, 3, 7, 11, 15, 14, 13, 12, 8, 4),
        (5, 6, 10, 9),
    ),
    (3, 3): (
        (0, 1, 2, 5, 8, 7, 6, 3),
        (4,),
    ),
}


def ring_groups(rows: int, cols: int) -> tuple[tuple[int, ...], ...]:
    """Rings for a ``rows x cols`` control polygon, outermost first.

    Returns an empty tuple for any shape outside the ADR-0018 §1 closed
    set, mirroring ``BuildControlPolygonCells``' rejection rather than
    raising: a pipeline asking about an out-of-spec grid should render no
    group affordance, not fail an interaction callback.
    """
    return RING_GROUPS.get((rows, cols), ())

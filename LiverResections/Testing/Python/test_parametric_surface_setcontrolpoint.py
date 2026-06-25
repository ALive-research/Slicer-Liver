# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""The per-point control-grid setter is callable from Python and round-trips.

Slice 1d exists to give the v2 ``vtkMRMLBezierSurfaceNode`` a Python-settable
control grid: ``SetControlGrid(const double*)`` cannot cross the VTK Python wrap
(a bare ``double*`` surfaces as an opaque pointer), so a scenario / interaction
code cannot position the grid through it.  ``SetControlPoint(row, col, x, y, z)``
takes only scalars and IS wrappable -- this pins that it is reachable from
Python and writes the row-major flat grid read back by ``GetControlGridVector``.

Launched-Slicer pytest (needs the wrapped node); skips cleanly under bare
``PythonSlicer -m pytest``.
"""

from __future__ import annotations

import pytest

BEZIER_NODE_CLASS = "vtkMRMLBezierSurfaceNode"


def _slicer_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def test_set_control_point_callable_from_python_and_round_trips():
    slicer = _slicer_or_skip()
    node = slicer.mrmlScene.AddNewNodeByClass(BEZIER_NODE_CLASS)
    if node is None:
        pytest.skip(f"{BEZIER_NODE_CLASS} not registered in this build.")
    if not hasattr(node, "SetControlPoint"):
        pytest.skip(
            "vtkMRMLBezierSurfaceNode has no SetControlPoint -- the Python "
            "grid seam (slice 1d) has not landed."
        )

    cols = int(node.GetCols())
    assert node.SetControlPoint(1, 2, 1.5, -2.5, 3.0) is True

    grid = node.GetControlGridVector()
    base = (1 * cols + 2) * 3
    assert abs(grid[base + 0] - 1.5) < 1e-9
    assert abs(grid[base + 1] - -2.5) < 1e-9
    assert abs(grid[base + 2] - 3.0) < 1e-9

    # Out-of-range is rejected from Python too.
    assert node.SetControlPoint(int(node.GetRows()), 0, 9.0, 9.0, 9.0) is False


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

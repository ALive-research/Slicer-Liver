# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Harness self-tests for ``replay_test._resolve_baseline_png``.

GAP-1 follow-up from PR #384's /slicer-review synthesis (issue #387).

``_resolve_baseline_png`` is intentionally trivial — it composes
``<baseline_dir> / "<test>.png"``.  The point of the test is to pin
that contract: the resolved path must be a plain ``<test>.png`` under
``baseline_dir``, no algorithm suffix, no nested subdirectory.  If a
future refactor accidentally adds a ``baselines/`` subdir or appends a
hash, the replay driver's ExternalData wiring breaks silently — this
test trips first.

References
----------
* ADR-0008 §"observability" — pure-Python helpers carry self-tests.
* ``CMake/ExternalData`` URL template wiring in
  ``LiverResections/Testing/Python/CMakeLists.txt``.
"""

from __future__ import annotations

import pathlib
import sys


# Sibling-of-tests path injection — same shape as test_has_baseline.py.
_HERE = pathlib.Path(__file__).resolve()
_HARNESS_DIR = _HERE.parent.parent
if str(_HARNESS_DIR) not in sys.path:
    sys.path.insert(0, str(_HARNESS_DIR))

import replay_test  # noqa: E402


def test_resolve_baseline_png_path_composition(tmp_path: pathlib.Path) -> None:
    """The resolved path is ``<baseline_dir> / "<test>.png"``."""
    resolved = replay_test._resolve_baseline_png(tmp_path, "BezierSurface4x4Planning")
    assert resolved == tmp_path / "BezierSurface4x4Planning.png"


def test_resolve_baseline_png_returns_path_object(tmp_path: pathlib.Path) -> None:
    """The helper must return a ``pathlib.Path`` (string concatenation
    would break the ``.exists()`` call in ``_has_baseline``)."""
    resolved = replay_test._resolve_baseline_png(tmp_path, "AnyScenario")
    assert isinstance(resolved, pathlib.Path)


def test_resolve_baseline_png_no_filesystem_side_effects(
    tmp_path: pathlib.Path,
) -> None:
    """Path composition must NOT create the file — that's the capture
    driver's job, not the resolver's.  Pin the read-only contract so a
    future ``.touch()`` accident gets caught."""
    replay_test._resolve_baseline_png(tmp_path, "NeverWritten")
    assert list(tmp_path.iterdir()) == []

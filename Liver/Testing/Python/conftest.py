# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""
Pytest scaffolding scoped to ``Liver/Testing/Python/``.

The canonical project-wide conftest at ``Testing/Python/conftest.py``
lives in a sibling subtree and is therefore NOT auto-discovered by
pytest invocations that target a single file under
``Liver/Testing/Python/...`` (pytest walks UP from the test file to
find ``conftest.py``; siblings aren't visited).

This conftest provides what the new T5.2-d sidebar tests need:

  * **`_require_qt_widget`** — early-skip helper for tests that need
    ``qt.QWidget``.  Bare ``PythonSlicer -m pytest <file>`` invocations
    don't initialise a ``qSlicerApplication``, so PythonQt's ``qt``
    module is importable but lacks the ``QWidget`` class.  Tests that
    need a real Qt widget call this helper at the top of the function
    body and skip cleanly when the harness can't satisfy them.

  * **`_require_mrml_scene`** — early-skip helper for tests that need
    ``slicer.mrmlScene``.  Same shape: ``slicer.mrmlScene`` is a
    ``qSlicerApplication`` runtime attribute, absent under bare
    PythonSlicer.

The brief for T5.2-d called for a "minimal qSlicerApplication
harness".  The test-designer landed pytest-style tests but the CMake
registration invokes bare ``PythonSlicer -m pytest`` -- which is the
existing Slicer-Liver pattern per ADR-0008 §6 and only suits Python-
side testing, NOT widget-level testing.  The full launched-Slicer
harness for the widget-level tests (T1, T4, T5, T6) is tracked as a
follow-up to T5.2-d: see the T5.2-d PR body's "Test plan" note.

Until that follow-up lands, the widget-level tests skip with a
clear message pointing at the launched-Slicer pattern; the
Python-side semantics tests (T2 symbol existence + T7 static AST
check) continue to run under bare PythonSlicer and exercise the
real invariants.
"""

from __future__ import annotations

import pytest


def _require_qt_widget() -> None:
    """Skip the current test if ``qt.QWidget`` is not available.

    Use at the top of any test function that constructs a Qt widget.
    Skips cleanly under bare ``PythonSlicer -m pytest <file>``;
    proceeds when the harness has initialised a ``qSlicerApplication``
    (e.g. via ``Slicer --no-splash --python-script $(which pytest)
    -- <file>``).
    """
    try:
        import qt  # type: ignore[import-not-found]
    except ImportError as exc:
        pytest.skip(
            f"qt module not importable ({exc}); "
            "run from PythonSlicer or a launched Slicer."
        )
        return
    if not hasattr(qt, "QWidget"):
        pytest.skip(
            "qt module is loaded but qt.QWidget is missing -- the test "
            "harness has not initialised a qSlicerApplication.  Re-run "
            "this test from a launched Slicer:\n"
            "  Slicer --no-splash --python-script $(which pytest) -- "
            "<test_file>\n"
            "Bare PythonSlicer -m pytest cannot satisfy widget-level "
            "tests; see the T5.2-d follow-up issue for the launched-"
            "Slicer harness."
        )


def _require_mrml_scene() -> None:
    """Skip the current test if ``slicer.mrmlScene`` is not available.

    Use at the top of any test function that touches the MRML scene.
    Same shape as ``_require_qt_widget``: bare PythonSlicer lacks
    ``slicer.mrmlScene``; a launched Slicer has it.
    """
    try:
        import slicer  # type: ignore[import-not-found]
    except ImportError as exc:
        pytest.skip(
            f"slicer module not importable ({exc}); "
            "run from PythonSlicer or a launched Slicer."
        )
        return
    if not hasattr(slicer, "mrmlScene"):
        pytest.skip(
            "slicer.mrmlScene not available -- bare PythonSlicer does "
            "not initialise a qSlicerApplication.  Run from a launched "
            "Slicer:  Slicer --no-splash --python-script $(which "
            "pytest) -- <test_file>"
        )

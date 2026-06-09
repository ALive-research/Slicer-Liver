# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Shared launched-Slicer pytest skip-guards.

Single source of truth for the early-skip helpers the per-module test
suites use to run the *same* test files under two harnesses (ADR-0008 §1):

  * **bare ``PythonSlicer -m pytest <file>``** — ``slicer`` imports as a
    library but no ``qSlicerApplication`` is initialised, so ``qt.QWidget``
    and ``slicer.mrmlScene`` are absent.  Widget- and scene-level tests
    skip cleanly via these guards; pure-Python tests still run.

  * **launched Slicer** (``run_pytest_launched.py`` driven by
    ``Slicer --no-splash --python-script $(which pytest) -- <file>``) — a
    live ``qSlicerApplication`` is present, so the guards return and the
    widget-/scene-level tests actually execute.

These helpers used to be copy-pasted across the per-module conftests and a
couple of test files (the docstrings literally said "Same shape as
``Liver/Testing/Python/conftest.py``").  They now live here once and are
re-exported by each module conftest under the historical underscore names.

Importable from any subtree because ``pytest.ini`` puts ``Testing/Python``
on ``pythonpath`` (honoured by bare ``pytest`` and by the in-process
``pytest.main()`` the launched driver calls).

See also:
  * Docs/adr/0008-testing-strategy.md §1, §6  (the dual-harness strategy)
"""

from __future__ import annotations

import pytest


def import_slicer_or_skip():
    """Return the ``slicer`` module, or skip the current test cleanly.

    Bare CPython / a plain pytest environment without a built Slicer
    cannot import ``slicer``; the consuming test skips rather than erroring
    so the suite can be exercised in isolation.
    """
    try:
        import slicer  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover — exercised only outside Slicer
        pytest.skip(
            f"slicer module not importable ({exc}); "
            "run from PythonSlicer or a launched Slicer."
        )
        return None
    return slicer


def require_mrml_scene() -> None:
    """Skip the current test if ``slicer.mrmlScene`` is not available.

    Use at the top of any test function that touches the MRML scene.
    Bare ``PythonSlicer`` does not initialise a ``qSlicerApplication`` and
    therefore has no ``slicer.mrmlScene``; a launched Slicer does.
    """
    slicer = import_slicer_or_skip()
    if slicer is None:
        return
    if not hasattr(slicer, "mrmlScene") or slicer.mrmlScene is None:
        pytest.skip(
            "slicer.mrmlScene not available -- bare PythonSlicer does not "
            "initialise a qSlicerApplication.  Run from a launched Slicer:\n"
            "  Slicer --no-splash --python-script $(which pytest) -- <test_file>"
        )


def require_qt_widget() -> None:
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
            "tests; see the launched-Slicer harness (run_pytest_launched.py)."
        )

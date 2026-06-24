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

import sys

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


# --------------------------------------------------------------------------- #
# Widget teardown registry (launched-harness shutdown-crash guard).
#
# Tests build the Stage-4 ResectionPlanningWidget PARENTLESS (production parents
# it into the Liver shell tab, where Qt destroys it before the scene).  A
# parentless widget survives to app shutdown, where its qMRMLNodeComboBox's
# scene wiring tears down in an undefined order vs the scene and crashes
# SlicerApp ("exit abnormally"), failing the launched harness even when every
# test passed.  A test helper registers each widget it builds here; the
# LiverResections conftest's autouse fixture drains + tears them down (cleanup()
# + deleteLater) after each test, while the scene is still alive.
# --------------------------------------------------------------------------- #

_REGISTRY_ATTR = "_liverWidgetTeardownRegistry"


def _teardown_registry():
    """The registry list, stored on the ``slicer`` MODULE (a process singleton).

    NOT a module global of ``slicer_pytest_support``: the multi-root launched
    harness can import this support module as DISTINCT objects (the sibling
    -import collision the conftest notes), splitting a module-global list so a
    widget registered through one import is invisible to a drain through
    another.  ``sys.modules['slicer']`` is singular across every import, so
    hanging the list off it keeps registration + drain on the SAME list.
    Returns ``None`` under bare pytest (no ``slicer``).
    """
    slicer = sys.modules.get("slicer")
    if slicer is None:
        return None
    registry = getattr(slicer, _REGISTRY_ATTR, None)
    if registry is None:
        registry = []
        setattr(slicer, _REGISTRY_ATTR, registry)
    return registry


def register_widget_for_teardown(widget):
    """Register a parentless test-built widget (the real Python instance, so the
    conftest fixture can call its ``cleanup()``) for deterministic teardown."""
    registry = _teardown_registry()
    if registry is not None and widget is not None:
        registry.append(widget)
    return widget


def drain_widgets_for_teardown():
    """Return the registered widgets and clear the registry."""
    registry = _teardown_registry()
    if not registry:
        return []
    widgets = list(registry)
    registry.clear()
    return widgets

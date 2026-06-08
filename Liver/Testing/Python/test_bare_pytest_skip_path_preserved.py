# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Skip-path-preservation invariant for the launched-Slicer harness.

The launched-Slicer pytest path (``run_pytest_launched.py`` driven by
``Slicer --python-script``) is ADDITIVE: it provides a second way to run
the same ``test_liver_shell_*`` files, this time inside a real
``qSlicerApplication`` so the widget-level tests actually execute.

It must NOT alter the existing bare-``PythonSlicer -m pytest`` behaviour,
which is the long-standing Slicer-Liver pattern (ADR-0008 §1): under bare
PythonSlicer the widget-level tests *skip cleanly* via the conftest
``_require_qt_widget`` early-skip helper, while the pure-Python tests
(static AST checks, symbol existence) still *run*.

This file pins that bare-path contract so a future change to the harness
(or the conftest helpers) cannot silently turn a clean skip into a hard
error or a false pass.

Unlike the driver-contract file, these invariants are checkable TODAY --
they describe the pre-existing bare path that the launched path must
preserve.  They are written here so the launched-harness lane owns an
explicit regression guard on the behaviour it is promising to leave
untouched.

Per ADR-0008 §1 (pytest primary; Slicer imported as a library on the
bare path) and the ``conftest._require_qt_widget`` early-skip contract.

See also
--------
* Liver/Testing/Python/conftest.py -- ``_require_qt_widget`` /
  ``_require_mrml_scene``
* Docs/adr/0008-testing-strategy.md §1, §6
"""

from __future__ import annotations

import importlib.util
import os

import pytest


_THIS_DIR = os.path.dirname(__file__)


def _load_conftest():
    """Import the sibling conftest as a module for direct helper access.

    The conftest defines ``_require_qt_widget`` / ``_require_mrml_scene``.
    pytest auto-loads conftest for fixture/hook discovery, but the helpers
    are plain functions the shell tests import explicitly -- so this file
    loads it the same way to assert their skip contract directly.
    """
    conftest_path = os.path.join(_THIS_DIR, "conftest.py")
    assert os.path.isfile(conftest_path), (
        f"Liver-shell conftest not found at {conftest_path}; the bare "
        "pytest skip path depends on its early-skip helpers."
    )
    spec = importlib.util.spec_from_file_location(
        "_liver_shell_conftest_under_test", conftest_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _running_under_launched_slicer() -> bool:
    """True when a ``qSlicerApplication`` with ``qt.QWidget`` is live.

    Distinguishes the launched path (widget-level tests run) from the
    bare path (they skip).  Mirrors the predicate inside
    ``conftest._require_qt_widget``.
    """
    try:
        import qt  # type: ignore[import-not-found]
    except ImportError:
        return False
    return hasattr(qt, "QWidget")


# --------------------------------------------------------------------------- #
# Invariant -- conftest exposes the early-skip helpers.
# --------------------------------------------------------------------------- #

def test_conftest_exposes_require_qt_widget():
    """The bare-path skip contract hinges on ``_require_qt_widget``.

    Pins that the helper the ``test_liver_shell_*`` widget tests rely on
    to skip cleanly under bare PythonSlicer still exists.  The launched
    harness must not remove or rename it -- doing so would convert the
    clean skip into an import-time hard error in the shell tests.

    Per ADR-0008 §1; conftest ``_require_qt_widget`` contract.
    """
    conftest = _load_conftest()
    assert hasattr(conftest, "_require_qt_widget"), (
        "conftest._require_qt_widget missing -- the bare-pytest skip "
        "path for widget-level Liver-shell tests would break."
    )
    assert hasattr(conftest, "_require_mrml_scene"), (
        "conftest._require_mrml_scene missing -- scene-level tests would "
        "lose their clean bare-path skip."
    )


# --------------------------------------------------------------------------- #
# Invariant -- bare path: widget helper skips; launched path: it proceeds.
# --------------------------------------------------------------------------- #

def test_require_qt_widget_skips_on_bare_path_runs_on_launched():
    """``_require_qt_widget`` skips under bare PythonSlicer, proceeds when launched.

    This is the ADDITIVE contract: the *same* helper must

      * raise ``pytest.skip`` (Skipped) under bare ``PythonSlicer -m
        pytest`` -- no ``qSlicerApplication``, so ``qt.QWidget`` absent;
      * return without skipping under a launched Slicer -- the launched
        harness initialises ``qSlicerApplication`` and ``qt.QWidget`` is
        present.

    The launched path therefore EXTENDS coverage (the widget tests now
    run) without rewriting the bare path's skip semantics.

    Per ADR-0008 §1, §6; conftest ``_require_qt_widget`` contract.
    """
    conftest = _load_conftest()

    if _running_under_launched_slicer():
        # Launched path: the helper must NOT skip -- it must return so the
        # widget test body proceeds.  A spurious skip here would mean the
        # launched harness failed to deliver the qSlicerApplication it
        # promises, silently degrading to bare-path behaviour.
        conftest._require_qt_widget()  # must not raise Skipped
        return

    # Bare path: the helper must raise Skipped, cleanly.
    with pytest.raises(pytest.skip.Exception):
        conftest._require_qt_widget()


def test_require_mrml_scene_skips_on_bare_path_runs_on_launched():
    """``_require_mrml_scene`` mirrors the additive contract for scene tests.

    Bare path: ``slicer.mrmlScene`` is absent (no ``qSlicerApplication``)
    -> Skipped.  Launched path: present -> returns and the test proceeds.

    Per ADR-0008 §1, §6; conftest ``_require_mrml_scene`` contract.
    """
    conftest = _load_conftest()

    try:
        import slicer  # type: ignore[import-not-found]

        scene_available = hasattr(slicer, "mrmlScene")
    except ImportError:
        scene_available = False

    if scene_available:
        conftest._require_mrml_scene()  # must not raise Skipped
        return

    with pytest.raises(pytest.skip.Exception):
        conftest._require_mrml_scene()

# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Shared pytest scaffolding for the LiverSegmentation Stage-2 invariant tests.

These tests pin the contract of the net-new ``LiverSegmentation/`` scripted
module (Stage 2 / Anatomy Definition) decided in
``Docs/adr/0024-segmentation-orchestration.md``.  Test-first scaffolding
landed per ``Docs/adr/0027-invariant-test-first-v2-implementation.md``: the
tests below are RED (skip or fail) until the implementer supplies the module.

Two audiences, same skip-clean discipline as the Liver-shell suite
(``Liver/Testing/Python/conftest.py``):

  * **Scene-needing tests** (registration, isStageComplete semantics,
    single-canonical-node) call ``_require_mrml_scene`` and run under a
    minimal ``qSlicerApplication`` (launched Slicer).  Under bare
    ``PythonSlicer -m pytest`` they skip cleanly.

  * **Import-purity + conformance-grep tests** are pure-Python: no Slicer,
    no Qt, no network.  They never call the helpers below.  This is the
    invariant that lets CI exercise the suite without provisioning Slicer.
"""

from __future__ import annotations

import pytest


def _import_slicer_or_skip():
    """Return the ``slicer`` module or skip the current test cleanly."""
    try:
        import slicer  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover — exercised only outside Slicer
        pytest.skip(
            f"slicer module not importable ({exc}); "
            "LiverSegmentation scene tests require Slicer's Python."
        )
        return None
    return slicer


def _require_mrml_scene():
    """Skip the current test if ``slicer.mrmlScene`` is not available.

    Bare ``PythonSlicer`` does not initialise a ``qSlicerApplication`` and
    therefore has no ``slicer.mrmlScene``; a launched Slicer does.  Same
    shape as ``Liver/Testing/Python/conftest.py``.
    """
    slicer = _import_slicer_or_skip()
    if slicer is None:
        return
    if not hasattr(slicer, "mrmlScene") or slicer.mrmlScene is None:
        pytest.skip(
            "slicer.mrmlScene not available -- bare PythonSlicer does not "
            "initialise a qSlicerApplication.  Run from a launched Slicer:\n"
            "  Slicer --no-splash --python-script $(which pytest) -- <test_file>"
        )


def _require_qt_widget():
    """Skip the current test if ``qt.QWidget`` is not available.

    The Stage-2 surgeon-UI tests construct the ``LiverSegmentationWidget``
    (a ``QTabWidget`` of four structure cards) and therefore need a real Qt
    widget surface.  Bare ``PythonSlicer -m pytest <file>`` loads PythonQt's
    ``qt`` module but does NOT initialise a ``qSlicerApplication``, so
    ``qt.QWidget`` is missing; the launched-Slicer harness from
    ``Liver/Testing/Python/run_pytest_launched.py`` (``pytest_launched``)
    has it.  Same shape as ``Liver/Testing/Python/conftest._require_qt_widget``.
    """
    try:
        import qt  # type: ignore[import-not-found]
    except ImportError as exc:
        pytest.skip(
            f"qt module not importable ({exc}); "
            "LiverSegmentation widget tests require a launched Slicer."
        )
        return
    if not hasattr(qt, "QWidget"):
        pytest.skip(
            "qt module is loaded but qt.QWidget is missing -- no "
            "qSlicerApplication.  Run under the launched-Slicer harness "
            "(pytest_launched / run_pytest_launched.py)."
        )

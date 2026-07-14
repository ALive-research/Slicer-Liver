# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Shared pytest scaffolding for the VascularTerritories vessel-highlight tests.

Re-exports the launched-Slicer skip-guards from ``slicer_pytest_support``
(canonical bodies in ``Testing/Python/slicer_pytest_support.py``, on
``sys.path`` via the ``pythonpath`` ini option) under the historical
underscore names, mirroring the LiverSegmentation conftest so the snap /
wiring tests share the same skip-clean discipline: scene-/widget-needing
tests SKIP under bare ``PythonSlicer -m pytest`` and RUN launched.
"""

from __future__ import annotations

import sys

import pytest

from slicer_pytest_support import (  # noqa: F401  (re-exported for `from conftest import ...`)
    import_slicer_or_skip as _import_slicer_or_skip,
    require_mrml_scene as _require_mrml_scene,
    require_qt_widget as _require_qt_widget,
)


def _looks_like_real_slicer(module) -> bool:
    """True iff ``module`` is the genuine launched-Slicer ``slicer`` module."""
    return module is not None and getattr(module, "mrmlScene", None) is not None


def _live_mrml_scene():
    """Return the launched-Slicer ``mrmlScene`` or ``None`` under bare pytest."""
    slicer = sys.modules.get("slicer")
    if not _looks_like_real_slicer(slicer):
        return None
    return slicer.mrmlScene


@pytest.fixture(autouse=True)
def _launched_scene_cleanup():
    """Clear the MRML scene after each launched test.  No-op under bare pytest.

    The launched harness runs the whole tree in ONE ``qSlicerApplication``;
    clearing after each test keeps scratch nodes from accumulating across
    the module's tests.  Unlike the LiverSegmentation guard this does NOT
    assert the node count returns to baseline: VascularTerritories is a
    resident (startup-loaded, hidden) module whose widget re-creates its
    ``vtkMRMLScriptedModuleNode`` parameter-node singleton on the scene's
    close event, so a single scene-managed singleton legitimately survives
    ``Clear(0)`` — it is reclaimed at process exit, not a leak.
    """
    scene = _live_mrml_scene()
    if scene is None:
        yield
        return

    yield
    scene.Clear(0)


@pytest.fixture
def qt_widgets():
    """Register launched-Slicer Qt widgets for disposal after the test.

    A widget-building test appends each widget it constructs; teardown drops
    the module's VTK observers via ``cleanup()`` and disposes the Qt tree so
    no widget survives to shutdown (mirrors the LiverSegmentation idiom).
    """
    registered: list = []

    yield registered

    for widget in registered:
        try:
            cleanup = getattr(widget, "cleanup", None)
            if callable(cleanup):
                cleanup()
            parent = getattr(widget, "parent", None)
            target = parent if parent is not None else widget
            if hasattr(target, "setParent"):
                target.setParent(None)
            if hasattr(target, "delete"):
                target.delete()
            elif hasattr(target, "deleteLater"):
                target.deleteLater()
        except Exception:  # noqa: BLE001 — teardown is best-effort across versions
            pass

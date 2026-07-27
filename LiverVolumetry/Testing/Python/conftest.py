# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Shared pytest scaffolding for the LiverVolumetry seed tests.

Mirrors ``VascularTerritories/Testing/Python/conftest.py``: re-exports the
launched-Slicer skip-guards from ``slicer_pytest_support`` (canonical
bodies in ``Testing/Python/slicer_pytest_support.py``, on ``sys.path`` via
the ``pythonpath`` ini option) and provides the autouse scene-cleanup
fixture so the launched harness clears scratch nodes between tests.

The seed carrier / display node / in-volume pick / compute tests are
launched-Slicer (wrapped C++ nodes + the LayerDM base); the pure
carrier->fiducial mapping runs bare.  The same skip-clean discipline as
VascularTerritories applies: scene-/wrapped-node-needing tests SKIP under
bare ``PythonSlicer -m pytest`` and RUN launched.
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
    clearing after each test keeps scratch labelmaps / carriers / fiducials
    from accumulating across the seed tests (mirrors the VascularTerritories
    guard).
    """
    scene = _live_mrml_scene()
    if scene is None:
        yield
        return

    yield
    scene.Clear(0)

# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Pytest scaffolding for the LiverResections launched-Slicer invariant tests.

The Subject-Hierarchy collection invariant (T5.2-f) is exercised against a
live ``qSlicerApplication`` -- minting a ``vtkMRMLLiverResectionNode`` fires
the module logic's ``OnMRMLSceneNodeAdded`` observer, which (after the
implementer wires the ``vtkSlicerSubjectHierarchyFolders`` utility) collects
the wrapper node under a scene-root "Resections" folder.  That path needs the
real scene + the registered module logic, so the scene-touching tests run
under the launched-Slicer harness (``Liver/Testing/Python/run_pytest_launched.py``
/ the ``pytest_launched`` CTest row) and SKIP CLEANLY under bare
``PythonSlicer -m pytest`` via the shared guards.

Re-exports the shared launched-Slicer skip-guards from
``slicer_pytest_support`` (canonical bodies in
``Testing/Python/slicer_pytest_support.py``, on ``sys.path`` via the
``pythonpath`` ini option) under their historical underscore names, and
carries the same launched-Slicer scene-cleanup hygiene the LiverSegmentation
conftest established (``_launched_scene_cleanup`` -- no MRML node may survive
to process exit, or ``vtkDebugLeaks`` fails the harness).

See also:
  * Docs/adr/0008-testing-strategy.md §1, §6  (dual-harness strategy)
  * Docs/adr/0023-unified-gui-stage-workflow.md §"MRML scene organisation"
  * LiverSegmentation/Testing/Python/conftest.py  (the cleanup-fixture model)
"""

from __future__ import annotations

import os
import sys

import pytest

# Put this directory on ``sys.path`` so a test module here can import a SIBLING
# test module by bare name (e.g. the presentation test imports the shared
# helpers from ``test_resectogram_open_view_action``).  conftest is loaded by
# pytest for every file in this directory under BOTH harnesses; the launched
# harness resolves the sibling via its test roots, but a bare ``PythonSlicer -m
# pytest`` collecting a single file leaves the sibling dir off ``sys.path`` and
# the import ERRORs at collection.  This insertion fixes that without changing
# importmode.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from slicer_pytest_support import (  # noqa: E402,F401  (re-exported for `from conftest import ...`)
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
def _teardown_resection_planning_widgets():
    """Destroy any parentless ResectionPlanningWidget a test built, before the
    scene (and the process) is torn down.

    The Stage-4 widget (``LiverResectionsLib.ResectionPlanningWidget``) is built
    PARENTLESS by the tests; production parents it into the Liver shell tab,
    where Qt destroys it before the scene.  A parentless widget survives to app
    shutdown, where its ``qMRMLNodeComboBox``'s scene wiring tears down in an
    undefined order vs the scene and crashes ``SlicerApp`` ("exit abnormally"),
    failing the launched harness even when every test PASSED.  ``_widget_or_skip``
    registers each widget it builds via
    ``slicer_pytest_support.register_widget_for_teardown``; drain + tear them
    down here (``cleanup()`` releases the combo's scene + the observers/filters,
    then ``deleteLater`` drops the widget) while the scene is still alive.
    No-op under bare pytest / when none were built.
    """
    yield
    try:
        from slicer_pytest_support import drain_widgets_for_teardown
    except Exception:  # pragma: no cover - import-environment dependent
        return
    widgets = drain_widgets_for_teardown()
    if not widgets:
        return
    for widget in widgets:
        try:
            cleanup = getattr(widget, "cleanup", None)
            if callable(cleanup):
                cleanup()
            widget.setParent(None)
            widget.deleteLater()
        except Exception:  # pragma: no cover - defensive teardown
            pass
    slicer = sys.modules.get("slicer")
    if _looks_like_real_slicer(slicer):
        slicer.app.processEvents()


@pytest.fixture(autouse=True)
def _launched_scene_cleanup():
    """Clear the MRML scene after each launched test; assert it stays clean.

    Active only under a launched Slicer (``slicer.mrmlScene`` present); a
    no-op under bare ``PythonSlicer -m pytest``.  Mirrors the LiverSegmentation
    conftest fixture: no scene node may survive to process shutdown and trip
    ``vtkDebugLeaks`` in the launched harness.
    """
    scene = _live_mrml_scene()
    if scene is None:
        yield
        return

    baseline = scene.GetNumberOfNodes()

    yield

    scene.Clear(0)
    remaining = scene.GetNumberOfNodes()
    assert remaining <= baseline, (
        "MRML scene GREW past its pre-test baseline even after Clear(): "
        f"{remaining} node(s) remain vs {baseline} at test start.  A node "
        "Clear() cannot reclaim survives to process shutdown and trips "
        "vtkDebugLeaks, failing the launched harness.  Tear down every node "
        "the test created."
    )

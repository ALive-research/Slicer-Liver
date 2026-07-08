# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""
Pytest scaffolding scoped to ``Liver/Testing/Python/``.

The canonical project-wide conftest at ``Testing/Python/conftest.py``
lives in a sibling subtree and is therefore NOT auto-discovered by
pytest invocations that target a single file under
``Liver/Testing/Python/...`` (pytest walks UP from the test file to
find ``conftest.py``; siblings aren't visited).

This conftest re-exports the shared launched-Slicer skip-guards from
``slicer_pytest_support`` under their historical underscore names:

  * **`_require_qt_widget`** — early-skip helper for tests that need
    ``qt.QWidget``.  Bare ``PythonSlicer -m pytest <file>`` invocations
    don't initialise a ``qSlicerApplication``, so PythonQt's ``qt``
    module is importable but lacks the ``QWidget`` class.

  * **`_require_mrml_scene`** — early-skip helper for tests that need
    ``slicer.mrmlScene`` (a ``qSlicerApplication`` runtime attribute,
    absent under bare PythonSlicer).

The canonical bodies live in ``Testing/Python/slicer_pytest_support.py``,
on ``sys.path`` via the ``pythonpath`` ini option in ``pytest.ini``.  The
underscore aliases here keep the existing ``from conftest import ...``
call sites and the bare-path skip-contract test
(``test_bare_pytest_skip_path_preserved.py``) working unchanged.

Under bare ``PythonSlicer -m pytest`` the widget-/scene-level tests skip
with a clear message pointing at the launched-Slicer pattern; the
Python-side semantics tests (symbol existence + static AST checks)
continue to run and exercise the real invariants (ADR-0008 §1, §6).
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
    """Clear the MRML scene after each launched test; assert it stays clean.

    Active only under a launched Slicer (``slicer.mrmlScene`` present); a no-op
    under bare ``PythonSlicer -m pytest``.  Mirrors the LiverResections /
    LiverSegmentation conftest fixture: no scene node the Case-Setup role tests
    mint (scalar volumes) may survive to process shutdown and trip
    ``vtkDebugLeaks`` in the launched harness (ADR-0008 §6).  The role tests also
    tear down their own volumes in a ``finally``; this fixture is the backstop.
    """
    scene = _live_mrml_scene()
    if scene is None:
        yield
        return

    baseline = scene.GetNumberOfNodes()
    baseline_ids = {
        scene.GetNthNode(i).GetID()
        for i in range(baseline)
        if scene.GetNthNode(i) is not None
    }

    yield

    scene.Clear(0)
    remaining = scene.GetNumberOfNodes()
    # SINGLETON-tagged nodes are scene-owned framework state (module
    # parameter nodes, singleton views): they exist the moment any code
    # touches their module, survive Clear() BY DESIGN, are re-minted by
    # live widgets if removed, and the scene reclaims them at app
    # shutdown -- they cannot trip vtkDebugLeaks.  Only NON-singleton
    # growth indicates a real test leak.
    survivors = [
        scene.GetNthNode(i)
        for i in range(remaining)
        if scene.GetNthNode(i) is not None
        and scene.GetNthNode(i).GetID() not in baseline_ids
        and not scene.GetNthNode(i).GetSingletonTag()
    ]
    named = ", ".join(
        f"{n.GetClassName()}(name={n.GetName()!r})" for n in survivors
    )
    assert not survivors, (
        "MRML scene GREW past its pre-test baseline even after Clear(): "
        f"{len(survivors)} non-singleton node(s) the test created survive.  "
        "A node Clear() cannot reclaim survives to process shutdown and "
        "trips vtkDebugLeaks, failing the launched harness.  Tear down "
        f"every node the test created.  Survivors: [{named}]"
    )

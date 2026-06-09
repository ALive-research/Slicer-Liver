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

import ast
import importlib.util
import os

import pytest


_THIS_DIR = os.path.dirname(__file__)


def _repo_root() -> str:
    """Walk up from this file to the directory holding ``pytest.ini``.

    Anchoring on the ini file (rather than a fixed ``..`` count) keeps the
    tree scan inside *this* checkout.  In a worktree layout the parent of the
    checkout holds sibling worktrees; a hard-coded level count would escape
    into them and miscount guard definitions.
    """
    current = _THIS_DIR
    while True:
        if os.path.isfile(os.path.join(current, "pytest.ini")):
            return current
        parent = os.path.dirname(current)
        if parent == current:  # filesystem root reached
            raise AssertionError(
                "pytest.ini not found walking up from "
                f"{_THIS_DIR}; cannot anchor the dedup tree scan."
            )
        current = parent


_REPO_ROOT = _repo_root()

# The canonical guard names live in the shared support module; the conftests
# re-export them under these underscore aliases.  Single source of truth for
# the dedup invariant below.
_CANONICAL_GUARD_NAMES = (
    "import_slicer_or_skip",
    "require_mrml_scene",
    "require_qt_widget",
)

# Historical underscore aliases that previously named copy-pasted bodies.
# ``_require_mrml_scene_or_skip`` was a thin wrapper around the scene guard.
_GUARD_ALIASES = {
    "_import_slicer_or_skip": "import_slicer_or_skip",
    "_require_mrml_scene": "require_mrml_scene",
    "_require_mrml_scene_or_skip": "require_mrml_scene",
    "_require_qt_widget": "require_qt_widget",
}


def _canonical_for(func_name: str):
    """Map a ``def`` name to its canonical guard, or ``None`` if unrelated.

    Matches both the canonical public names and the historical underscore
    aliases, so a re-definition under either spelling is flagged.
    """
    if func_name in _CANONICAL_GUARD_NAMES:
        return func_name
    return _GUARD_ALIASES.get(func_name)


def _load_conftest():
    """Import the sibling conftest as a module for direct helper access.

    The conftest re-exports ``_require_qt_widget`` / ``_require_mrml_scene``
    from the shared ``slicer_pytest_support`` module.  pytest auto-loads
    conftest for fixture/hook discovery, but the helpers are plain functions
    the shell tests import explicitly -- so this file loads it the same way
    to assert their skip contract (and the dedup identity) directly.
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


# --------------------------------------------------------------------------- #
# Invariant -- the skip-guards are deduplicated onto one shared module.
# --------------------------------------------------------------------------- #
#
# Pins the post-hoc dedup: the launched-Slicer skip-guards used to be
# copy-pasted across the per-module conftests and a couple of test files
# (their docstrings literally said "Same shape as
# ``Liver/Testing/Python/conftest.py``").  These two tests fail against the
# pre-dedup tree (multiple ``def`` bodies) and pass once the guards live in
# ``Testing/Python/slicer_pytest_support.py`` and the conftests re-export them.


def test_skip_guards_defined_exactly_once_in_tree():
    """Each guard body must be defined exactly once across the test tree.

    Walks every ``test_*.py`` and ``conftest.py`` under the repo, parsing
    each for top-level ``def <guard>`` statements.  A guard may be *defined*
    only in the shared support module; everything else must import / re-export
    it.  The canonical names plus their historical underscore aliases are both
    counted -- a stray re-definition under either spelling re-introduces the
    duplication the shared ``slicer_pytest_support`` module exists to remove.

    Red against the pre-dedup tree (``_require_qt_widget`` defined in two
    conftests, ``_require_mrml_scene`` in two, ``_import_slicer_or_skip`` /
    ``_require_mrml_scene_or_skip`` inline in two shell test files); green
    once only ``slicer_pytest_support`` carries the bodies.
    """
    guard_defs = {name: [] for name in _CANONICAL_GUARD_NAMES}

    for dirpath, _dirnames, filenames in os.walk(_REPO_ROOT):
        # Skip build trees and VCS metadata.
        if os.sep + "build" in dirpath or os.sep + ".bare" in dirpath:
            continue
        for filename in filenames:
            is_scanned = (
                filename.startswith("test_")
                or filename == "conftest.py"
                or filename == "slicer_pytest_support.py"
            )
            if not (is_scanned and filename.endswith(".py")):
                continue
            path = os.path.join(dirpath, filename)
            with open(path, encoding="utf-8") as handle:
                tree = ast.parse(handle.read(), filename=path)
            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef):
                    continue
                canonical = _canonical_for(node.name)
                if canonical is not None:
                    guard_defs[canonical].append(os.path.relpath(path, _REPO_ROOT))

    support_rel = os.path.join("Testing", "Python", "slicer_pytest_support.py")
    for name, locations in guard_defs.items():
        assert locations == [support_rel], (
            f"Guard {name!r} must be defined exactly once, in "
            f"{support_rel}; found definitions in {locations}.  The "
            "launched-Slicer skip-guards are deduplicated onto "
            "slicer_pytest_support; conftests re-export, tests import."
        )


def test_conftest_aliases_are_the_shared_objects():
    """Each conftest alias must be the SAME object as the shared guard.

    Re-export, not re-implementation: ``conftest._require_qt_widget`` must be
    ``slicer_pytest_support.require_qt_widget`` (identity), likewise for the
    scene + import guards.  This catches a future maintainer copy-pasting a
    body back into a conftest "just to tweak the message" -- which would pass
    a name-existence check but silently re-fork the contract.
    """
    import slicer_pytest_support  # on sys.path via pytest.ini ``pythonpath``

    conftest = _load_conftest()
    assert conftest._require_qt_widget is slicer_pytest_support.require_qt_widget
    assert conftest._require_mrml_scene is slicer_pytest_support.require_mrml_scene
    assert (
        conftest._import_slicer_or_skip
        is slicer_pytest_support.import_slicer_or_skip
    )

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

import json
import os
import subprocess
import sys

import pytest


# --------------------------------------------------------------------------- #
# Import-purity child runner: stub ``slicer`` in a subprocess, not in-process.
# --------------------------------------------------------------------------- #
#
# The import-purity probes (test_liversegmentation_import_purity,
# test_liversegmentation_backend_status_row) must replace
# ``sys.modules['slicer']`` with a tripwire fake to prove no pip_install / no
# ``import totalsegmentator`` fires at import time.  Doing that in-process
# would poison the shared launched-Slicer interpreter (see the regression
# guard below).  This helper runs the stub + import in a CHILD interpreter and
# returns the child's structured JSON verdict, so the parent's ``sys.modules``
# is never touched.  Both probes supply their own child program (they assert
# different facts) but share this plumbing: module-root-on-PYTHONPATH (the same
# import path the launched harness's ``--additional-module-paths`` supplies)
# plus last-JSON-line parsing.

#: Module source root that makes ``LiverSegmentation`` / ``LiverSegmentationLib``
#: importable.  This conftest sits at ``LiverSegmentation/Testing/Python/`` so
#: the module root (holding ``LiverSegmentation.py`` + the
#: ``LiverSegmentationLib/`` package) is two parents up.
_MODULE_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
)


def run_purity_child(program: str, *args: str, timeout: float = 120.0) -> dict:
    """Run ``program`` in a clean child interpreter; return its JSON verdict.

    ``program`` is Python source executed via ``python -c`` with ``args``
    forwarded as ``sys.argv[1:]``.  The child runs with ``_MODULE_ROOT`` on
    ``PYTHONPATH`` so it can import the targets the same way the launched
    harness does.  The returned dict is parsed from the child's last
    JSON-object stdout line (the verdict), augmented with ``_returncode`` /
    ``_stdout`` / ``_stderr`` for diagnostics.  A child that emits no parseable
    verdict yields ``{"result": None, ...}`` so callers can fail loudly rather
    than pass silently.
    """
    env = {**os.environ}
    env["PYTHONPATH"] = os.pathsep.join(
        [_MODULE_ROOT, env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    proc = subprocess.run(
        [sys.executable, "-c", program, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    verdict: dict = {"result": None}
    for line in reversed(proc.stdout.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and "result" in parsed:
            verdict = parsed
            break
    verdict["_returncode"] = proc.returncode
    verdict["_stdout"] = proc.stdout
    verdict["_stderr"] = proc.stderr
    return verdict


# --------------------------------------------------------------------------- #
# Regression guard: no test may replace the live ``slicer`` / ``slicer.util``.
# --------------------------------------------------------------------------- #
#
# The launched-Slicer harness (``Liver/Testing/Python/run_pytest_launched.py``,
# the ``pytest_launched`` CTest row) runs the WHOLE project pytest tree inside
# ONE long-lived ``qSlicerApplication`` interpreter.  Every test shares that
# interpreter's ``sys.modules``.  A test that swaps a fake ``slicer`` (or
# ``slicer.util``) into ``sys.modules`` to probe import-time behaviour and then
# fails to restore the real module objects POISONS every subsequent test:
#
#   * scene tests see the stub's missing ``mrmlScene`` and skip
#     ("slicer.mrmlScene not available"); and
#   * the driver's ``_exit`` helper calls the stub's missing
#     ``slicer.util.exit`` -> the launched process never quits -> CTest times
#     out.
#
# An import-purity probe MUST therefore stub ``slicer`` inside a child
# interpreter (subprocess), never in the shared parent.  This autouse fixture
# is the tripwire that makes a violation FAIL LOUDLY in the offending test
# instead of silently corrupting the session: it snapshots the live module
# objects' identities before each test and asserts they are unchanged after.
#
# It only asserts when a REAL slicer is present (the launched harness); under
# bare ``PythonSlicer -m pytest`` ``slicer`` may be absent or partial, so the
# guard stands down rather than firing spuriously.


def _looks_like_real_slicer(module) -> bool:
    """True iff ``module`` is the genuine launched-Slicer ``slicer`` module.

    A real launched ``slicer`` exposes ``mrmlScene`` (a qSlicerApplication
    runtime attribute the import-purity stubs never carry).  Bare PythonSlicer
    imports ``slicer`` but without ``mrmlScene``; the stubs are bare
    ``types.ModuleType`` instances.  Keying on ``mrmlScene`` distinguishes the
    one case the guard must protect — the shared launched interpreter — from
    every benign case where it must stand down.
    """
    return module is not None and getattr(module, "mrmlScene", None) is not None


@pytest.fixture(autouse=True)
def _no_slicer_module_leak():
    """Fail any test that replaces the live ``slicer`` / ``slicer.util``.

    Snapshots the live module-object identities before the test and asserts
    in teardown that the test did not swap a fake into ``sys.modules`` and
    leave it there.  Active only when a real launched ``slicer`` is present;
    a no-op otherwise (bare PythonSlicer, or no slicer at all).
    """
    slicer_before = sys.modules.get("slicer")
    util_before = getattr(slicer_before, "util", None)
    guard_active = _looks_like_real_slicer(slicer_before)

    yield

    if not guard_active:
        return

    slicer_after = sys.modules.get("slicer")
    util_after = getattr(slicer_after, "util", None)
    assert slicer_after is slicer_before, (
        "this test replaced the live 'slicer' module in sys.modules and did "
        "not restore it -- a fake-slicer leak poisons every subsequent test "
        "in the shared launched-Slicer interpreter (scene tests skip, the "
        "driver's exit helper cannot quit, CTest times out).  Stub 'slicer' "
        "in a CHILD process (subprocess), never in this shared interpreter."
    )
    assert util_after is util_before, (
        "this test replaced 'slicer.util' and did not restore it -- same "
        "shared-interpreter leak hazard as a swapped 'slicer'.  Probe import "
        "purity in a child process, not in the live interpreter."
    )


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

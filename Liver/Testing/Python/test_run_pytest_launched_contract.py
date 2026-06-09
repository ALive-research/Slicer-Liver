# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Behavioural contract for the launched-Slicer pytest driver.

The driver under test is ``Liver/Testing/Python/run_pytest_launched.py``:
a thin committed script that Slicer runs via ``--python-script``.  It
calls ``pytest.main([...test roots...])``, captures the integer return
code, and routes it through ``slicer.util.exit(code)`` -- the same
exit-propagation pattern proven by
``LiverResections/Testing/Python/replay_test.py`` (``_exit`` helper).

Why the driver exists
---------------------
``Slicer --no-main-window --python-script`` does NOT auto-exit when the
script returns: control falls back into Slicer's QApplication event
loop, which keeps running until something calls ``slicer.app.exit()``.
A plain ``sys.exit()`` / ``pytest.main()`` return is swallowed, so a
naive ``--python-script $(which pytest)`` invocation hangs until the
CTest timeout fires AND reports the wrong status.  The driver closes
that gap by funnelling pytest's exit code through ``slicer.util.exit``.

Invariants pinned here
----------------------
1. **Exit-code propagation.**  A passing pytest target drives the
   driver process to exit 0; a failing target drives it to a non-zero
   exit.  The launched harness must never report green for a red run.

2. **Fail-closed.**  If pytest is unreachable, or collection errors
   (import error in a test module, no tests found where tests were
   expected), the driver must exit non-zero -- never silently 0.  A
   harness that swallows collection failures would let a broken test
   tree pass CI unnoticed.

These invariants are the *harness's own* contract.  They are deliberately
expressed as a subprocess self-test driving the real driver against tiny
throwaway pytest targets, so the assertion is on the observable process
exit code -- exactly what CTest keys off.

Per ADR-0008 §6 (CI matrix -- "every PR runs everything", non-zero on
any failure) and the ``replay_test._exit`` exit-propagation precedent.

Driver presence
---------------
``_require_driver`` hard-fails (not skips) if ``run_pytest_launched.py``
is ever missing, so an accidentally removed or renamed driver surfaces
as a red test rather than a silent skip (ADR-0008 §6 -- every PR runs
everything, non-zero on any failure).

See also
--------
* Docs/adr/0008-testing-strategy.md §1 (pytest primary), §6 (CI matrix)
* LiverResources/Testing/Python/replay_test.py -- ``_exit`` precedent
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
import textwrap
import types

import pytest



# --------------------------------------------------------------------------- #
# Driver location -- single source of truth.
# --------------------------------------------------------------------------- #
#
# The driver is a sibling of this test file in Liver/Testing/Python/.
_DRIVER_PATH = os.path.join(os.path.dirname(__file__), "run_pytest_launched.py")


def _require_driver() -> str:
    """Return the driver path, hard-failing if it is missing.

    FAILS (not skips) when the driver is absent so an accidentally
    removed or renamed driver surfaces as a red test in CI rather than a
    silent skip that would hide the gap.
    """
    assert os.path.isfile(_DRIVER_PATH), (
        f"launched-Slicer pytest driver not found at {_DRIVER_PATH}.  "
        "This test pins the driver's exit-code contract per ADR-0008 §6."
    )
    return _DRIVER_PATH


def _python_executable() -> str:
    """Interpreter used to drive the driver in this self-test.

    The driver's exit-propagation contract is interpreter-agnostic: under
    bare CPython its ``slicer.util.exit`` fallback is ``sys.exit`` (same
    shape as ``replay_test._exit``), so the exit code still surfaces.
    Inside a launched Slicer the same code routes through
    ``slicer.util.exit``.  This self-test runs the cheap CPython path so
    the contract is checkable without spinning up a full Slicer.
    """
    return sys.executable


def _write_pytest_target(tmp_path, body: str, filename: str = "test_target.py") -> str:
    """Materialise a tiny throwaway pytest target and return its path."""
    target = tmp_path / filename
    target.write_text(textwrap.dedent(body), encoding="utf-8")
    return str(target)


def _run_driver(target_path: str):
    """Invoke the driver against ``target_path`` as its sole test root.

    Returns the ``subprocess.CompletedProcess``.  The driver's argv
    contract (how test roots are passed) is finalised by the implementer;
    this self-test passes the test root as a trailing positional argument
    after a ``--`` separator -- the convention used by ``replay_test``
    and ``capture_baseline`` for ``--python-script`` arg slicing.  If the
    implementer settles on a different argv shape, this helper is the one
    place to update.
    """
    driver = _require_driver()
    # Force the driver's sys.exit path so the process exit code is
    # faithful regardless of interpreter.  Under PythonSlicer (CI's
    # sys.executable) ``slicer`` imports but there is no launched event
    # loop, so ``slicer.util.exit`` cannot carry the code out; the real
    # launched harness (pytest_launched) leaves this unset and relies on
    # the event loop.  This self-test pins the propagation *logic*.
    env = {**os.environ, "SLICER_PYTEST_LAUNCHED_FORCE_SYSEXIT": "1"}
    return subprocess.run(
        [_python_executable(), driver, "--", target_path],
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
    )


# --------------------------------------------------------------------------- #
# Invariant 1 -- exit-code propagation.
# --------------------------------------------------------------------------- #

def test_driver_exits_zero_on_passing_target(tmp_path):
    """A passing pytest target must drive the driver to exit 0.

    Pins ADR-0008 §6: the launched harness reports green only when the
    underlying pytest run is green.
    """
    target = _write_pytest_target(
        tmp_path,
        """
        def test_known_pass():
            assert True
        """,
    )
    result = _run_driver(target)
    assert result.returncode == 0, (
        "Driver must exit 0 for a passing pytest target; "
        f"got {result.returncode}.\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def test_driver_exits_nonzero_on_failing_target(tmp_path):
    """A failing pytest target must drive the driver to a non-zero exit.

    Pins ADR-0008 §6: a red pytest run must surface as a non-zero
    process exit so CTest / CI fail.  This is the core anti-regression
    the driver exists to guarantee.
    """
    target = _write_pytest_target(
        tmp_path,
        """
        def test_known_fail():
            assert False, "intentional failure for harness self-test"
        """,
    )
    result = _run_driver(target)
    assert result.returncode != 0, (
        "Driver must exit non-zero for a failing pytest target; "
        f"got {result.returncode}.\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


# --------------------------------------------------------------------------- #
# Invariant 2 -- fail-closed.
# --------------------------------------------------------------------------- #

def test_driver_fails_closed_on_collection_error(tmp_path):
    """A collection error must drive the driver to a non-zero exit.

    A test module that raises on import is the canonical collection
    failure.  pytest returns a non-zero code (``ExitCode.INTERRUPTED`` /
    ``USAGE_ERROR`` family) for this; the driver must propagate it and
    never collapse it to 0.

    Pins ADR-0008 §6 fail-closed posture: a broken test tree must not
    pass CI.
    """
    target = _write_pytest_target(
        tmp_path,
        """
        import this_module_does_not_exist_anywhere  # noqa: F401

        def test_never_reached():
            assert True
        """,
        filename="test_collection_error.py",
    )
    result = _run_driver(target)
    assert result.returncode != 0, (
        "Driver must exit non-zero when a test module fails to import "
        f"(collection error); got {result.returncode}.  A silent 0 here "
        "would let a broken test tree pass CI.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_driver_fails_closed_when_no_tests_collected(tmp_path):
    """An empty test root must NOT be reported as a green run.

    pytest returns ``ExitCode.NO_TESTS_COLLECTED`` (5) when a root it was
    pointed at yields zero tests.  For a launched harness whose entire
    purpose is running a known, non-empty set of test roots, a root that
    suddenly collects nothing signals a broken invocation (wrong path,
    filtered everything out) -- it must surface as non-zero, not 0.

    Pins ADR-0008 §6 fail-closed posture.

    Also pins that pytest's NO_TESTS_COLLECTED (exit 5) is propagated,
    not masked down to 0.
    """
    # An empty directory: a valid root, but pytest collects nothing.
    empty_root = tmp_path / "empty_root"
    empty_root.mkdir()
    result = _run_driver(str(empty_root))
    assert result.returncode != 0, (
        "Driver must exit non-zero when a declared test root collects no "
        f"tests (pytest NO_TESTS_COLLECTED=5); got {result.returncode}.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


# --------------------------------------------------------------------------- #
# Invariant 3 -- never hang on a drifted slicer.util.
# --------------------------------------------------------------------------- #
#
# Regression: ``_exit`` routed the code through ``slicer.util.exit(code)``
# inside a bare ``except ImportError``.  A drifted Slicer image that ships
# a partial ``slicer.util`` with no ``exit`` attribute raised
# ``AttributeError`` -- NOT caught -- so the script aborted while Slicer's
# Qt event loop kept running.  ``pytest_launched`` then hung until the
# 1500 s CTest timeout and reported the wrong status.  ``_exit`` must
# degrade to ``slicer.app.exit`` (the same primitive ``slicer.util.exit``
# uses) so a missing API yields a coded exit, never a hang.

def _import_driver_module():
    """Import ``run_pytest_launched`` as a module (defs only; __main__ guarded)."""
    sys.path.insert(0, os.path.dirname(_require_driver()))
    try:
        return importlib.import_module("run_pytest_launched")
    finally:
        sys.path.pop(0)


def _fake_app():
    """A stand-in qSlicerApplication recording ``exit`` + ``runPythonAndExit``."""
    class _Opts:
        runPythonAndExit = True

    class _App:
        def __init__(self):
            self.exited_with = None
            self.opts = _Opts()

        def commandOptions(self):
            return self.opts

        def exit(self, code):
            self.exited_with = code

    return _App()


def test_exit_uses_slicer_util_exit_when_present(monkeypatch):
    """When ``slicer.util.exit`` exists it is the route taken (app.exit untouched)."""
    monkeypatch.delenv("SLICER_PYTEST_LAUNCHED_FORCE_SYSEXIT", raising=False)
    driver = _import_driver_module()

    recorded = {}
    fake = types.ModuleType("slicer")
    fake.util = types.ModuleType("slicer.util")
    fake.util.exit = lambda code: recorded.setdefault("util_exit", code)
    fake.app = _fake_app()
    monkeypatch.setitem(sys.modules, "slicer", fake)

    driver._exit(0)

    assert recorded.get("util_exit") == 0
    assert fake.app.exited_with is None, "app.exit must not be used when util.exit exists"


def test_exit_falls_back_to_app_exit_when_util_exit_missing(monkeypatch):
    """A ``slicer.util`` with no ``exit`` must degrade, not raise/hang.

    Pins the regression that timed out ``pytest_launched`` for 1500 s.
    The fallback mirrors ``slicer.util.exit``: clear ``runPythonAndExit``
    so Slicer cannot overwrite the code, then ``app.exit(code)``.
    """
    monkeypatch.delenv("SLICER_PYTEST_LAUNCHED_FORCE_SYSEXIT", raising=False)
    driver = _import_driver_module()

    fake = types.ModuleType("slicer")
    fake.util = types.ModuleType("slicer.util")  # deliberately NO exit attribute
    fake.app = _fake_app()
    monkeypatch.setitem(sys.modules, "slicer", fake)

    # Must NOT raise AttributeError and must NOT call sys.exit (no hang, no SystemExit).
    driver._exit(7)

    assert fake.app.exited_with == 7, "code must be carried out through app.exit"
    assert fake.app.opts.runPythonAndExit is False, (
        "runPythonAndExit must be cleared so Slicer does not overwrite the exit code"
    )


def test_exit_falls_back_to_sysexit_when_slicer_unimportable(monkeypatch):
    """No ``slicer`` at all (standalone CPython) still yields a coded exit."""
    monkeypatch.delenv("SLICER_PYTEST_LAUNCHED_FORCE_SYSEXIT", raising=False)
    driver = _import_driver_module()

    # Ensure `import slicer` fails inside _exit.
    monkeypatch.setitem(sys.modules, "slicer", None)  # forces ImportError on import

    with pytest.raises(SystemExit) as excinfo:
        driver._exit(3)
    assert excinfo.value.code == 3

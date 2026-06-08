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

RED STATE
---------
Every test in this file is expected to RED-FAIL until
``run_pytest_launched.py`` is implemented: the driver script does not
yet exist on disk.  The tests assert its presence and fail with a clear
message rather than skipping, so the red state is visible (a skip would
mask the missing driver).  The implementer (``liver-implementer``) turns
them green by landing the driver.

See also
--------
* Docs/adr/0008-testing-strategy.md §1 (pytest primary), §6 (CI matrix)
* LiverResources/Testing/Python/replay_test.py -- ``_exit`` precedent
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap



# --------------------------------------------------------------------------- #
# Driver location -- single source of truth.
# --------------------------------------------------------------------------- #
#
# The driver is a sibling of this test file in Liver/Testing/Python/.
_DRIVER_PATH = os.path.join(os.path.dirname(__file__), "run_pytest_launched.py")


def _require_driver() -> str:
    """Return the driver path, hard-failing if it does not yet exist.

    Deliberately FAILS (not skips) when the driver is absent so the RED
    state is visible in CI.  The whole point of this file is to pin the
    driver's contract before it is written; a skip would hide that the
    driver has not landed.
    """
    assert os.path.isfile(_DRIVER_PATH), (
        f"launched-Slicer pytest driver not found at {_DRIVER_PATH}.  "
        "This test pins the driver's exit-code contract per ADR-0008 §6; "
        "it RED-fails until run_pytest_launched.py is implemented."
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
    return subprocess.run(
        [_python_executable(), driver, "--", target_path],
        capture_output=True,
        text=True,
        timeout=300,
    )


# --------------------------------------------------------------------------- #
# Invariant 1 -- exit-code propagation.
# --------------------------------------------------------------------------- #

def test_driver_exits_zero_on_passing_target(tmp_path):
    """A passing pytest target must drive the driver to exit 0.

    Pins ADR-0008 §6: the launched harness reports green only when the
    underlying pytest run is green.

    RED-fails until run_pytest_launched.py exists.
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

    RED-fails until run_pytest_launched.py exists.
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

    RED-fails until run_pytest_launched.py exists.
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

    RED-fails until run_pytest_launched.py exists.  When green, this also
    pins that the implementer did NOT mask exit code 5 down to 0.
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

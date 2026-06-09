# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Launched-Slicer pytest driver.

Slicer runs this thin script via ``--python-script`` so the project
pytest tree executes inside a live ``qSlicerApplication``.  This is the
ADDITIVE counterpart to the bare ``PythonSlicer -m pytest`` path
(ADR-0008 §1): the same ``test_liver_shell_*`` files run, but now the
widget-level tests actually execute instead of skipping via
``conftest._require_qt_widget``.

Why a driver is needed
----------------------
``Slicer --no-main-window --python-script`` does NOT auto-exit when the
script returns: control falls back into Slicer's QApplication event
loop, which keeps running until something calls ``slicer.app.exit()``.
A plain ``pytest.main()`` return value is therefore swallowed and the
process hangs until the CTest / workflow timeout fires AND reports the
wrong status.  This driver closes that gap by funnelling pytest's
integer exit code through ``slicer.util.exit`` -- the exit-propagation
pattern proven by ``LiverResections/Testing/Python/replay_test.py``
(``_exit`` helper).

Argv contract
-------------
Test roots are passed as trailing positional arguments after a ``--``
separator (the convention used by ``replay_test`` / ``capture_baseline``
for ``--python-script`` arg slicing): everything after the first
``--`` is forwarded verbatim to ``pytest.main`` as the list of roots.

Fail-closed posture (ADR-0008 §6)
---------------------------------
The driver propagates pytest's integer exit code unchanged and never
collapses a non-zero code to 0.  In particular:

* test failure / error -> non-zero (propagated);
* collection / import error -> non-zero (propagated);
* ``NO_TESTS_COLLECTED`` (pytest exit 5) -> non-zero (propagated).

A launched harness whose entire purpose is running a known, non-empty
set of test roots must treat "a declared root collected nothing" as a
broken invocation, not a green run.  Because pytest already returns a
non-zero code for every one of these, faithful propagation IS the
fail-closed guarantee -- the driver must not remap any of them to 0.

See also
--------
* Docs/adr/0008-testing-strategy.md §1, §6
* LiverResources/Testing/Python/replay_test.py -- ``_exit`` precedent
"""

from __future__ import annotations

import os
import sys

# Test-only escape hatch.  The contract self-test
# (test_run_pytest_launched_contract.py) drives this script as a
# subprocess to assert exit-code propagation, but runs it WITHOUT a
# launched QApplication event loop -- under PythonSlicer ``slicer`` is
# importable yet ``slicer.util.exit`` cannot propagate a code with no
# loop to quit.  When this variable is set the driver routes through
# ``sys.exit`` (faithful in any interpreter), so the self-test checks
# the propagation logic deterministically.  The real ``pytest_launched``
# harness leaves it unset and uses ``slicer.util.exit`` (the launched
# event loop carries the code out, per the replay_test precedent).
_FORCE_SYSEXIT_ENV = "SLICER_PYTEST_LAUNCHED_FORCE_SYSEXIT"


def _test_roots(argv: list[str]) -> list[str]:
    """Extract the trailing test roots from the process argv.

    Everything after the first ``--`` separator is the list of pytest
    roots.  When no ``--`` is present (e.g. a developer invokes the
    driver directly with bare positionals), fall back to all positional
    arguments after the script name.  An empty result is left empty:
    ``pytest.main([])`` then collects from the configured ``testpaths``
    in ``pytest.ini``, which is the intended default for an in-tree run.
    """
    if "--" in argv:
        return argv[argv.index("--") + 1:]
    return argv[1:]


def main(argv: list[str] | None = None) -> int:
    """Run pytest against the supplied roots and return its exit code.

    Returns pytest's integer exit code unchanged -- including the
    non-zero ``NO_TESTS_COLLECTED`` (5) and collection-error codes -- so
    the fail-closed contract holds (ADR-0008 §6).
    """
    if argv is None:
        argv = sys.argv

    import pytest

    return int(pytest.main(_test_roots(argv)))


def _exit(code: int) -> None:
    """Terminate the process even when running inside Slicer.

    Inside a launched Slicer a plain ``sys.exit`` is swallowed by the
    interpreter wrapper and the process hangs in the QApplication event
    loop; route through ``slicer.util.exit`` instead.  Fall back to
    ``sys.exit`` for the standalone CPython invocation (the harness
    self-test in ``test_run_pytest_launched_contract.py``, or a local
    lint run).  Same shape as ``replay_test._exit``.

    ``slicer.util.exit`` is preferred, but a drifted Slicer image has
    been observed to ship a partial ``slicer.util`` with no ``exit``
    attribute.  Routing the code through it inside a bare ``except
    ImportError`` let the resulting ``AttributeError`` escape: the
    script aborted while Slicer's Qt event loop kept running, hanging
    until the CTest timeout fired.  So degrade across the same primitive
    ``slicer.util.exit`` itself uses -- clear ``runPythonAndExit`` so
    Slicer does not overwrite our code, then ``app.exit`` -- and only
    then ``sys.exit``, so a missing API yields a coded exit, never a
    hang.
    """
    if os.environ.get(_FORCE_SYSEXIT_ENV) == "1":
        sys.exit(code)
    try:
        import slicer  # type: ignore[import-not-found]
    except ImportError:
        sys.exit(code)
        return

    util_exit = getattr(getattr(slicer, "util", None), "exit", None)
    if callable(util_exit):
        util_exit(code)
        return

    app = getattr(slicer, "app", None)
    if app is not None:
        try:
            app.commandOptions().runPythonAndExit = False
        except Exception:  # noqa: BLE001 -- best-effort; still drive app.exit below
            pass
        app.exit(code)
        return

    sys.exit(code)


if __name__ == "__main__":
    _exit(main())

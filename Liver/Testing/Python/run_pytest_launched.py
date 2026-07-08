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


def _unshadow_pypi_packaging() -> None:
    """Drop a ``slicer`` package dir from ``sys.path`` when it shadows ``packaging``.

    In some Slicer builds the ``slicer`` *package directory itself* lands on
    ``sys.path`` (not merely its parent), so the ``packaging.py`` it bundles
    shadows the real ``site-packages/packaging`` package.  pytest's
    ``_checkversion`` then runs ``from packaging.version import Version`` and
    crashes at startup with ``'packaging' is not a package`` -- which is why a
    launched pytest run could only be exercised on CI, never locally.

    Remove any ``sys.path`` entry that is a ``slicer`` package dir carrying a
    ``packaging.py``, and evict a half-imported single-module ``packaging`` so
    the next import resolves to the real package.  No-op when the shadow is
    absent (e.g. CI), so it is safe everywhere.
    """
    cleaned = [
        p
        for p in sys.path
        if not (
            p
            and os.path.basename(os.path.normpath(p)) == "slicer"
            and os.path.isfile(os.path.join(p, "packaging.py"))
        )
    ]
    if len(cleaned) != len(sys.path):
        sys.path[:] = cleaned
        shadow = sys.modules.get("packaging")
        if shadow is not None and not hasattr(shadow, "__path__"):
            sys.modules.pop("packaging", None)


def main(argv: list[str] | None = None) -> int:
    """Run pytest against the supplied roots and return its exit code.

    Returns pytest's integer exit code unchanged -- including the
    non-zero ``NO_TESTS_COLLECTED`` (5) and collection-error codes -- so
    the fail-closed contract holds (ADR-0008 §6).
    """
    if argv is None:
        argv = sys.argv

    _unshadow_pypi_packaging()
    _sync_slicer_modules_attributes()
    _log_module_registration_snapshot()

    import pytest

    return int(pytest.main(_test_roots(argv)))


def _sync_slicer_modules_attributes() -> None:
    """Populate ``slicer.modules.<name>`` from the module manager (issue #460).

    ``slicer.modules.<name>`` is set by ``slicerqt.setSlicerModules`` via the
    ``moduleManager.moduleLoaded(QString)`` signal (Slicer ``slicerqt.py``).
    That signal-driven Python attribute LAGS in the CI launched harness -- the
    modules are fully registered on the C++ ``moduleManager()`` (verified: all
    modules present) but the ``slicer.modules`` attributes are not yet set when
    the driver runs pytest immediately at ``--python-script`` time.  Tests that
    check ``getattr(slicer.modules, name)`` then skip/fail with a false
    ``'<name>' module not registered``.

    Replicate ``setSlicerModules`` SYNCHRONOUSLY for every registered module --
    a pure ``moduleManager()`` read + ``setattr``, NO ``processEvents`` /
    signal-connect (those crash the harness during startup).  Idempotent: for
    modules whose attribute is already set it re-assigns the same object.
    Best-effort: never raises.
    """
    try:
        import slicer  # type: ignore[import-not-found]

        manager = slicer.app.moduleManager()
        if manager is None:
            return
        for name in manager.modulesNames():
            module = manager.module(name)
            if module is not None:
                setattr(slicer.modules, name.lower(), module)
    except Exception as exc:  # pragma: no cover - best-effort, must not break the run
        print(f"[launched #460] slicer.modules sync skipped: {exc!r}", flush=True)


def _log_module_registration_snapshot() -> None:
    """Print the registered-module set + factory failures (issue #460 diagnostic).

    A pure STATE READ -- no ``processEvents`` / signal-connect (those crash the
    launched harness during startup).  Shows exactly which modules are on
    ``slicer.modules`` at the moment pytest collects, so a CI log reveals why
    launched tests skip ``'<name>' module not registered``.  Best-effort:
    never raises, never blocks the run.  Remove once #460 is understood.
    """
    try:
        import slicer  # type: ignore[import-not-found]

        manager = slicer.app.moduleManager()
        names = sorted(manager.modulesNames()) if manager is not None else []
        print(f"[launched-diag #460] {len(names)} modules registered: {names}", flush=True)

        factory = manager.factoryManager() if manager is not None else None
        for attr in ("ignoredModuleNames", "failedModuleNames"):
            getter = getattr(factory, attr, None)
            if getter is not None:
                print(f"[launched-diag #460] {attr}: {sorted(getter())}", flush=True)
    except Exception as exc:  # pragma: no cover - diagnostic must never break the run
        print(f"[launched-diag #460] snapshot unavailable: {exc!r}", flush=True)


def _exit(code: int) -> None:
    """Terminate the process even when running inside Slicer.

    Inside a launched Slicer a plain ``sys.exit`` is swallowed by the
    interpreter wrapper and the process hangs in the QApplication event
    loop; route through ``slicer.util.exit`` instead.  Fall back to
    ``sys.exit`` for the standalone CPython invocation (the harness
    self-test in ``test_run_pytest_launched_contract.py``, or a local
    lint run).  Same shape as ``replay_test._exit``.
    """
    if os.environ.get(_FORCE_SYSEXIT_ENV) == "1":
        sys.exit(code)
    try:
        import slicer  # type: ignore[import-not-found]

        slicer.util.exit(code)
    except ImportError:
        sys.exit(code)


if __name__ == "__main__":
    _exit(main())

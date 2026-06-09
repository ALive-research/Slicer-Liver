# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Invariant 4 — import-time purity (no pip_install, no totalsegmentator).

ADR-0024 §"Lazy install for AI backends": TotalSegmentator is pip-installed
on FIRST SURGEON INVOCATION, never at import.  This is the invariant that
lets CI run the suite WITHOUT network or a multi-GB model download.

Two import paths must be pure at import time:
  * ``import LiverSegmentation``                      (the module)
  * ``import LiverSegmentationLib.ToolWrappers.TotalSegmentator``  (the wrapper)

Neither may, at import time:
  * call ``slicer.util.pip_install(...)``      -- asserted via a fake
    ``slicer`` whose ``pip_install`` is a tripwire that records (and refuses)
    any call;
  * ``import totalsegmentator``                -- asserted via a ``sys.modules``
    poison sentinel that raises on import.

Process isolation (load-bearing)
--------------------------------
The stubbing — replacing ``sys.modules['slicer']`` / ``slicer.util`` with
fakes and poisoning ``import totalsegmentator`` — runs in a CHILD interpreter
(subprocess), NEVER in this test process.  The launched-Slicer harness
(``Liver/Testing/Python/run_pytest_launched.py``, the ``pytest_launched``
CTest row) runs the whole pytest tree inside ONE long-lived
``qSlicerApplication`` interpreter whose ``sys.modules`` every test shares.  A
fake ``slicer`` left in that shared map poisons every subsequent test (scene
tests lose ``mrmlScene`` and skip; the driver's exit helper cannot find
``slicer.util.exit`` and the launched process hangs to a CTest timeout).
Confining the stub to a child process makes the probe incapable of corrupting
the shared session — the parent's ``slicer`` is never touched.  This mirrors
the subprocess self-test pattern in
``Liver/Testing/Python/test_run_pytest_launched_contract.py``.

Pure-Python child: no Slicer build, no Qt, no network.  A minimal fake
``slicer`` is injected in the child so the scripted-module top-level imports
resolve.

The import-purity INVARIANT is still pinned in full: the child reports a
structured sentinel and a non-zero exit if production code calls
``pip_install`` or imports ``totalsegmentator`` at import time; the parent
asserts on that.  If the target is not importable in the child (no module on
the path — bare ``PythonSlicer`` from the repo root), the child reports a
SKIP sentinel and the parent ``pytest.skip``s cleanly, exactly as before.
"""

from __future__ import annotations

import textwrap

import pytest

# Module-under-test import targets per ADR-0024 §"Module layout".
MODULE_IMPORT = "LiverSegmentation"
WRAPPER_IMPORT = "LiverSegmentationLib.ToolWrappers.TotalSegmentator"

# The AI package that must NOT be imported at module-import time.
FORBIDDEN_PACKAGE = "totalsegmentator"

# Structured sentinels the child prints on its last stdout line.
_RESULT_PURE = "PURE"  # import was inert (no pip_install, no totalsegmentator)
_RESULT_PIP = "PIP_INSTALL_AT_IMPORT"  # pip_install called at import time
_RESULT_FORBIDDEN = "TOTALSEGMENTATOR_AT_IMPORT"  # AI package imported at import
_RESULT_SKIP = "NOT_IMPORTABLE"  # target absent on the child's import path


# The child program: stub ``slicer`` + poison ``totalsegmentator`` IN THE
# CHILD, import the target, and report a structured JSON verdict.  Kept as a
# source string run via ``-c`` so nothing in this parent process ever mutates
# ``sys.modules['slicer']`` (see module docstring).
_CHILD_PROGRAM = textwrap.dedent(
    f"""
    import builtins
    import importlib
    import json
    import sys
    import types

    TARGET = sys.argv[1]
    FORBIDDEN = {FORBIDDEN_PACKAGE!r}

    pip_calls = []

    def _tripwire_pip_install(*args, **kwargs):
        pip_calls.append((args, kwargs))
        raise RuntimeError("pip_install called at import time")

    fake_util = types.ModuleType("slicer.util")
    fake_util.pip_install = _tripwire_pip_install
    fake_slicer = types.ModuleType("slicer")
    fake_slicer.util = fake_util
    fake_slicer.ScriptedLoadableModule = types.ModuleType(
        "slicer.ScriptedLoadableModule"
    )
    sys.modules["slicer"] = fake_slicer
    sys.modules["slicer.util"] = fake_util
    sys.modules["slicer.ScriptedLoadableModule"] = fake_slicer.ScriptedLoadableModule

    real_import = builtins.__import__

    class _ForbiddenImport(Exception):
        pass

    def _guarded_import(name, *args, **kwargs):
        if name.split(".", 1)[0] == FORBIDDEN:
            raise _ForbiddenImport(name)
        return real_import(name, *args, **kwargs)

    builtins.__import__ = _guarded_import
    sys.modules.pop(FORBIDDEN, None)

    def _emit(result, **extra):
        print(json.dumps(dict(result=result, **extra)))

    try:
        module = importlib.import_module(TARGET)
    except _ForbiddenImport as exc:
        _emit({_RESULT_FORBIDDEN!r}, name=str(exc))
        raise SystemExit(2)
    except RuntimeError:
        _emit({_RESULT_PIP!r}, calls=len(pip_calls))
        raise SystemExit(3)
    except ImportError as exc:
        _emit({_RESULT_SKIP!r}, error=str(exc))
        raise SystemExit(0)

    # Guard the bare-pytest namespace-package false positive: a target that
    # resolves to a package directory (``__file__ is None``) rather than the
    # real scripted-module file is "not yet importable", same as before.
    if getattr(module, "__file__", None) is None:
        _emit({_RESULT_SKIP!r}, error="resolved to namespace package")
        raise SystemExit(0)

    if pip_calls:
        _emit({_RESULT_PIP!r}, calls=len(pip_calls))
        raise SystemExit(3)
    if FORBIDDEN in sys.modules:
        _emit({_RESULT_FORBIDDEN!r}, name=FORBIDDEN)
        raise SystemExit(2)
    _emit({_RESULT_PURE!r})
    raise SystemExit(0)
    """
)


@pytest.mark.parametrize("target", [MODULE_IMPORT, WRAPPER_IMPORT])
def test_import_triggers_no_pip_install_and_no_totalsegmentator(target):
    """Importing the module/wrapper triggers no pip_install + no AI import.

    ADR-0024 §"Lazy install for AI backends" + §Conformance: the lazy-install
    code path lives under ``ToolWrappers/`` and fires only on use.  Import
    must be inert.  The stub + import run in a child interpreter so the probe
    cannot poison this (possibly shared launched-Slicer) process.
    """
    # Imported lazily (inside the test body, not at module level) so it binds
    # to THIS directory's conftest: the launched harness imports several
    # per-root ``conftest`` modules under the same bare name, and a top-level
    # import could resolve to a sibling root's conftest.  Same late-import
    # idiom the scene tests use for ``_require_mrml_scene`` etc.
    from conftest import run_purity_child

    verdict = run_purity_child(_CHILD_PROGRAM, target)
    result = verdict.get("result")

    if result == _RESULT_SKIP:
        pytest.skip(
            f"'{target}' not importable in the child ({verdict.get('error')}) "
            "-- ADR-0024 implementer deliverable absent on this import path.  "
            "Import-purity invariant pins behaviour for when the module lands."
        )

    diag = (
        f"\nchild returncode: {verdict.get('_returncode')}"
        f"\nchild stdout:\n{verdict.get('_stdout')}"
        f"\nchild stderr:\n{verdict.get('_stderr')}"
    )

    assert result is not None, (
        f"import-purity child emitted no parseable verdict for '{target}' -- "
        f"it likely crashed before reporting.{diag}"
    )
    assert result != _RESULT_PIP, (
        f"importing '{target}' called slicer.util.pip_install at import time "
        "-- must be zero at import (ADR-0024 §'Lazy install')." + diag
    )
    assert result != _RESULT_FORBIDDEN, (
        f"importing '{target}' pulled in '{FORBIDDEN_PACKAGE}' -- the AI "
        "package must be imported only inside the call path (ADR-0024)." + diag
    )
    assert result == _RESULT_PURE, (
        f"unexpected import-purity verdict for '{target}': {result!r}." + diag
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

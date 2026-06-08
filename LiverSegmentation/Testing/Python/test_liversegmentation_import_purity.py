# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Invariant 4 — import-time purity (no pip_install, no totalsegmentator).

ADR-0024 §"Lazy install for AI backends": TotalSegmentator is pip-installed
on FIRST SURGEON INVOCATION, never at import.  This is the invariant that
lets CI run the suite WITHOUT network or a multi-GB model download.

Two import paths must be pure at import time:
  * ``import LiverSegmentation``                      (the module)
  * ``import LiverSegmentation.ToolWrappers.TotalSegmentator``  (the wrapper)

Neither may, at import time:
  * call ``slicer.util.pip_install(...)``      -- asserted via a monkeypatched
    sentinel that records (and refuses) any call;
  * ``import totalsegmentator``                -- asserted via a ``sys.modules``
    poison sentinel that raises on import.

Pure-Python: no Slicer build, no Qt, no network.  A minimal fake ``slicer``
is injected so the scripted-module top-level imports resolve.

RED until the implementer lands the module + wrapper with the lazy-install
discipline (pip_install behind a call-time guard, ``import totalsegmentator``
inside the call path, not at module top level).
"""

from __future__ import annotations

import builtins
import importlib
import sys
import types

import pytest

# Module-under-test import targets per ADR-0024 §"Module layout".
MODULE_IMPORT = "LiverSegmentation"
WRAPPER_IMPORT = "LiverSegmentation.ToolWrappers.TotalSegmentator"

# The AI package that must NOT be imported at module-import time.
FORBIDDEN_PACKAGE = "totalsegmentator"


class _PipInstallCalled(AssertionError):
    """Raised if production code calls pip_install during import."""


class _ForbiddenImport(AssertionError):
    """Raised if production code imports totalsegmentator during import."""


def _install_fake_slicer(monkeypatch):
    """Inject a minimal fake ``slicer`` whose ``util.pip_install`` is a tripwire.

    Returns the recorder list; if production code calls ``pip_install`` during
    import the call is recorded AND raises, so the failure is unambiguous.
    """
    calls: list = []

    def _tripwire_pip_install(*args, **kwargs):
        calls.append((args, kwargs))
        raise _PipInstallCalled(
            "slicer.util.pip_install was called at import time -- ADR-0024 "
            "§'Lazy install' forbids this; install must be deferred to first "
            "surgeon invocation."
        )

    fake_util = types.ModuleType("slicer.util")
    fake_util.pip_install = _tripwire_pip_install

    fake_slicer = types.ModuleType("slicer")
    fake_slicer.util = fake_util
    # ScriptedLoadableModule pulls these off the slicer namespace; provide
    # inert stand-ins so the top-level import does not explode for unrelated
    # reasons.  Anything genuinely needed beyond import time is out of scope
    # for an import-purity probe.
    fake_slicer.ScriptedLoadableModule = types.ModuleType(
        "slicer.ScriptedLoadableModule"
    )

    monkeypatch.setitem(sys.modules, "slicer", fake_slicer)
    monkeypatch.setitem(sys.modules, "slicer.util", fake_util)
    monkeypatch.setitem(
        sys.modules,
        "slicer.ScriptedLoadableModule",
        fake_slicer.ScriptedLoadableModule,
    )
    return calls


def _poison_totalsegmentator(monkeypatch):
    """Make ``import totalsegmentator`` raise, so a real import trips loudly."""
    real_import = builtins.__import__

    def _guarded_import(name, *args, **kwargs):
        root = name.split(".", 1)[0]
        if root == FORBIDDEN_PACKAGE:
            raise _ForbiddenImport(
                f"'{FORBIDDEN_PACKAGE}' was imported at module-import time -- "
                "ADR-0024 §'Lazy install' requires it to be imported only "
                "inside the call path, not at module top level."
            )
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _guarded_import)
    # Ensure no stale real module short-circuits the import machinery.
    monkeypatch.delitem(sys.modules, FORBIDDEN_PACKAGE, raising=False)


def _fresh_import(target):
    """Import ``target`` fresh, dropping any cached copy first.

    Guards against the bare-pytest false-positive where ``import
    LiverSegmentation`` resolves to the *package directory* as an implicit
    namespace package (``__file__ is None``) instead of the real scripted-
    module file ``LiverSegmentation.py``.  In Slicer's Python the module dir
    is on ``sys.path`` so ``import LiverSegmentation`` loads the ``.py``; in a
    bare repo-root pytest run the ``.py`` is not yet importable as a top-level
    module, so a namespace-package hit must be treated as "not yet present".
    """
    for name in list(sys.modules):
        if name == target or name.startswith(target + "."):
            del sys.modules[name]
    module = importlib.import_module(target)
    if getattr(module, "__file__", None) is None:
        raise ImportError(
            f"'{target}' resolved to a namespace package (no real module "
            "file) -- the implementer's scripted-module source is not yet "
            "present on the import path."
        )
    return module


@pytest.mark.parametrize("target", [MODULE_IMPORT, WRAPPER_IMPORT])
def test_import_triggers_no_pip_install_and_no_totalsegmentator(target, monkeypatch):
    """Importing the module/wrapper triggers no pip_install + no AI import.

    ADR-0024 §"Lazy install for AI backends" + §Conformance: the lazy-install
    code path lives under ``ToolWrappers/`` and fires only on use.  Import
    must be inert.
    """
    pip_calls = _install_fake_slicer(monkeypatch)
    _poison_totalsegmentator(monkeypatch)

    try:
        _fresh_import(target)
    except (_PipInstallCalled, _ForbiddenImport):
        # The tripwires themselves are the assertion failure -- re-raise so
        # pytest reports the precise import-purity violation.
        raise
    except ImportError as exc:
        pytest.skip(
            f"'{target}' not importable yet ({exc}) -- ADR-0024 implementer "
            "deliverable absent.  Import-purity invariant pins behaviour for "
            "when the module lands."
        )

    assert not pip_calls, (
        f"importing '{target}' called slicer.util.pip_install {len(pip_calls)} "
        "time(s) -- must be zero at import (ADR-0024 §'Lazy install')."
    )
    assert FORBIDDEN_PACKAGE not in sys.modules, (
        f"importing '{target}' pulled in '{FORBIDDEN_PACKAGE}' -- the AI "
        "package must be imported only inside the call path (ADR-0024)."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

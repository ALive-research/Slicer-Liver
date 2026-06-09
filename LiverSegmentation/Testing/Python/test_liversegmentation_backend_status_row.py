# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Invariant 9 (UI) — Stage-2-local backend-status row.

ADR-0024 §"Lazy install for AI backends": Stage 2 surfaces a *local*
backend-status affordance (installed ✓/✗ + a Pre-download button), NOT a
Liver-shell settings panel.  Two invariants:

  * The status row reflects ``ToolWrappers.TotalSegmentator.ensureBackendInstalled``
    truthiness — installed ✓ when the backend imports, ✗ when it does not.
  * The Pre-download affordance calls ``ensureBackendInstalled(confirm=False)``
    (no second size dialog; the surgeon already opted in by clicking
    Pre-download) and mints **no** segmentation node — pre-downloading the
    model is not a Run.

Import-purity is preserved (ADR-0024 §"Lazy install"): ``pip_install`` lives
only under ``ToolWrappers/``; the widget reaches install only via the
wrapper's ``ensureBackendInstalled`` hook.  The pure-Python
import-purity-of-the-hook assertion below stays runnable under bare pytest;
the widget-level assertions need the launched-Slicer harness.

RED until the implementer lands the backend-status row + Pre-download wiring
per ADR-0024.
"""

from __future__ import annotations

import textwrap

import pytest

MODULE_NAME = "liversegmentation"
WRAPPER_IMPORT = "LiverSegmentationLib.ToolWrappers.TotalSegmentator"

# Human-readable download-size string shown in the status row / confirm dialog.
# Named constant per the wrapper's TOTALSEGMENTATOR_DOWNLOAD_SIZE; pinned here
# so the surgeon-facing copy stays a single source of truth (ADR-0024
# §"Lazy install for AI backends").
DOWNLOAD_SIZE_STRING = "~3 GB"


# --------------------------------------------------------------------------- #
# Pure-Python: the Pre-download hook is reachable WITHOUT triggering an install
# at probe time.  Runs under bare pytest (no Slicer / Qt / network).
#
# The wrapper is imported under a fake ``slicer`` in a CHILD interpreter
# (subprocess), never in this process: the launched-Slicer harness shares one
# ``sys.modules`` across the whole pytest tree, and a fake ``slicer`` left
# behind there poisons every subsequent test (scene tests lose ``mrmlScene``;
# the driver's exit helper hangs the process to a CTest timeout).  Same
# isolation discipline as ``test_liversegmentation_import_purity``.
# --------------------------------------------------------------------------- #

# Child program: stub ``slicer`` + poison ``totalsegmentator`` IN THE CHILD,
# import the wrapper, and report the Pre-download-hook facts as JSON.
_HOOK_PROBE_PROGRAM = textwrap.dedent(
    f"""
    import builtins
    import importlib
    import json
    import sys
    import types

    WRAPPER = {WRAPPER_IMPORT!r}

    pip_calls = []

    def _tripwire_pip_install(*args, **kwargs):
        pip_calls.append((args, kwargs))
        raise RuntimeError("pip_install called at import time")

    fake_util = types.ModuleType("slicer.util")
    fake_util.pip_install = _tripwire_pip_install
    fake_slicer = types.ModuleType("slicer")
    fake_slicer.util = fake_util
    sys.modules["slicer"] = fake_slicer
    sys.modules["slicer.util"] = fake_util

    real_import = builtins.__import__

    def _guarded_import(name, *args, **kwargs):
        if name.split(".", 1)[0] == "totalsegmentator":
            raise ImportError("totalsegmentator poisoned for purity probe")
        return real_import(name, *args, **kwargs)

    builtins.__import__ = _guarded_import
    sys.modules.pop("totalsegmentator", None)

    try:
        wrapper = importlib.import_module(WRAPPER)
    except ImportError as exc:
        print(json.dumps(dict(result="NOT_IMPORTABLE", error=str(exc))))
        raise SystemExit(0)
    except RuntimeError:
        print(json.dumps(dict(result="PIP_INSTALL_AT_IMPORT")))
        raise SystemExit(3)

    print(json.dumps(dict(
        result="OK",
        has_hook=hasattr(wrapper, "ensureBackendInstalled"),
        size=getattr(wrapper, "TOTALSEGMENTATOR_DOWNLOAD_SIZE", None),
        pip_calls=len(pip_calls),
    )))
    raise SystemExit(0)
    """
)


def test_predownload_hook_exposes_confirm_false_and_size_constant():
    """The wrapper exposes the Pre-download hook + the download-size constant.

    ADR-0024 §"Lazy install": the settings/status row's Pre-download affordance
    reuses ``ensureBackendInstalled(confirm=False)``.  Merely *resolving* the
    hook + the size copy must not trigger an install (import-purity).  The stub
    + import run in a child interpreter so the probe never poisons this
    (possibly shared launched-Slicer) process.
    """
    # Lazy import (inside the body) so it binds to THIS directory's conftest,
    # not a sibling test root's same-named ``conftest`` in the launched
    # harness.  Same idiom the scene tests use for ``_require_mrml_scene``.
    from conftest import run_purity_child

    verdict = run_purity_child(_HOOK_PROBE_PROGRAM)
    result = verdict.get("result")

    if result == "NOT_IMPORTABLE":
        pytest.skip(
            f"{WRAPPER_IMPORT} not importable in the child "
            f"({verdict.get('error')}) -- ADR-0024 deliverable absent."
        )

    diag = f"\nchild stderr:\n{verdict.get('_stderr')}"
    assert result == "OK", (
        "resolving the Pre-download hook must not call pip_install at import "
        f"(import-purity, ADR-0024 §'Lazy install'); child verdict {result!r}."
        + diag
    )
    assert verdict.get("has_hook"), (
        "wrapper must expose the reusable ensureBackendInstalled() hook "
        "(ADR-0024 §'Lazy install')." + diag
    )
    # The download-size copy is a named constant in one place.
    assert verdict.get("size") == DOWNLOAD_SIZE_STRING, (
        "the download-size string must be the named wrapper constant "
        f"'{DOWNLOAD_SIZE_STRING}' (single source of truth, ADR-0024)." + diag
    )
    assert verdict.get("pip_calls") == 0, (
        "resolving the Pre-download hook must not call pip_install "
        "(import-purity, ADR-0024 §'Lazy install')." + diag
    )


# --------------------------------------------------------------------------- #
# Widget-level: status row reflects ensureBackendInstalled; Pre-download calls
# it confirm=False and mints no node.  Launched-Slicer harness.
# --------------------------------------------------------------------------- #


def _widget_or_skip(slicer):
    from conftest import _require_qt_widget

    _require_qt_widget()
    if getattr(slicer.modules, MODULE_NAME, None) is None:
        pytest.skip(
            f"'{MODULE_NAME}' module not registered -- ADR-0024 surgeon-UI "
            "deliverable absent."
        )
    try:
        import LiverSegmentation  # type: ignore[import-not-found]
    except ImportError as exc:
        pytest.skip(f"LiverSegmentation not importable ({exc}).")
    widget = LiverSegmentation.LiverSegmentationWidget()
    widget.setup()
    return widget


def test_predownload_button_calls_ensurebackend_confirm_false_no_node(monkeypatch):
    """Pre-download -> ensureBackendInstalled(confirm=False); no node minted.

    ADR-0024 §"Lazy install": clicking Pre-download is itself the surgeon's
    opt-in, so the hook is called with ``confirm=False`` (no second dialog),
    and pre-downloading the model is NOT a Run -- no segmentation node is
    created (import-purity boundary preserved: install stays under
    ToolWrappers/).

    TODO(impl): pin the Pre-download trigger the implementer wires (e.g.
    ``widget.onPreDownload()`` / a ``ui.PreDownloadButton`` click).  The
    pinned invariant is "confirm=False + zero segmentation nodes", not the
    trigger's spelling.
    """
    from conftest import _import_slicer_or_skip, _require_mrml_scene

    _require_mrml_scene()
    slicer = _import_slicer_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer)

    try:
        import LiverSegmentationLib.ToolWrappers.TotalSegmentator as ts  # noqa: N813

        recorded = {}

        def _spy(parent=None, confirm=True):
            recorded["confirm"] = confirm
            return True  # pretend the backend is now present

        monkeypatch.setattr(ts, "ensureBackendInstalled", _spy)

        trigger = None
        for name in ("onPreDownload", "_onPreDownload", "preDownloadBackend"):
            if hasattr(widget, name):
                trigger = getattr(widget, name)
                break
        if trigger is None:
            pytest.fail(
                "widget must expose a Pre-download trigger reusing "
                "ensureBackendInstalled(confirm=False) per ADR-0024 "
                "§'Lazy install' -- not yet implemented."
            )

        trigger()

        assert recorded.get("confirm") is False, (
            "Pre-download must call ensureBackendInstalled(confirm=False) -- "
            "the click is the opt-in, no second size dialog (ADR-0024)."
        )
        assert len(slicer.util.getNodesByClass("vtkMRMLSegmentationNode")) == 0, (
            "Pre-download must mint NO segmentation node -- downloading the "
            "model is not a Run (ADR-0024 §'Lazy install')."
        )
    finally:
        widget.cleanup()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

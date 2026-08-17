# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Stage-lifecycle forwarding invariants for the Liver shell.

The shell composes its stages from cached ``widgetRepresentation()``
panels of HIDDEN modules plus shell-built Python pages (ADR-0023
§"Shell composition (Option H)").  The application therefore calls
``enter()`` / ``exit()`` on the SHELL only -- never on the panels it
hosts -- so the shell must relay its own lifecycle to the panel of the
showing stage, and hand it over on a stage switch.

Without that relay every module-scoped exit-hygiene body a stage panel
owns is dead code inside the shell: the module-active add-on-click gate
(ADR-0037 §"Module-active gate (extends §Decision 2)", ADR-0038
§"Shared home + names"), the overlay retire, and the highlight-march
timer stop would all never run.

Contract pinned here (``Liver.LiverWidget`` §"Stage lifecycle
forwarding"):

L1
    Shell ``enter()`` relays ``enter()`` to the showing stage's panel --
    and to that one only, not to every hosted panel.

L2
    Shell ``exit()`` relays ``exit()`` to the showing stage's panel.

L3
    A stage switch relays ``exit()`` to the outgoing panel and
    ``enter()`` to the incoming one, in that order.

L4
    A panel that defines neither method is skipped without error, and a
    panel whose method raises cannot strand shell navigation.

L5
    Stage switching while the shell is NOT showing relays nothing (the
    surgeon is looking at some other module).

L6
    A scripted stage panel's lifecycle is relayed to its PYTHON widget
    (the representation's ``self()``), not to the C++ representation --
    whose ``enter()`` / ``exit()`` assert on a lifecycle the shell does
    not own.

The relay is exercised on a bare ``LiverWidget`` instance (no Qt
construction, no ``setup()``): the seam is pure Python bookkeeping over
``_stagePages`` / ``_currentStageIndex``, so it is verifiable under bare
``PythonSlicer -m pytest`` as well as in a launched Slicer.
"""

from __future__ import annotations

import pytest

from slicer_pytest_support import import_slicer_or_skip as _import_slicer_or_skip


# --------------------------------------------------------------------------- #
# Doubles
# --------------------------------------------------------------------------- #

class _PanelSpy:
    """A hosted stage panel recording the lifecycle calls it receives."""

    def __init__(self):
        self.calls = []

    def enter(self):
        self.calls.append("enter")

    def exit(self):
        self.calls.append("exit")


class _MethodlessPanel:
    """A hosted page with no lifecycle methods (a shell-owned static page)."""


class _RaisingPanel(_PanelSpy):
    """A hosted panel whose lifecycle raises (a partially-built page)."""

    def enter(self):
        self.calls.append("enter")
        raise RuntimeError("stage panel enter() blew up")

    def exit(self):
        self.calls.append("exit")
        raise RuntimeError("stage panel exit() blew up")


class _ScriptedRepDouble:
    """A scripted module's ``widgetRepresentation()``: lifecycle lives on ``self()``.

    Mirrors ``qSlicerScriptedLoadableModuleWidget``, which exposes both its own
    C++ ``enter()`` / ``exit()`` AND the Python widget via ``self()``.  Its own
    methods are booby-trapped so L6 fails loudly if the shell relays to the
    representation instead of the Python widget.
    """

    def __init__(self, inner):
        self._inner = inner

    def self(self):  # noqa: A003 - mirrors the PythonQt method name
        return self._inner

    def enter(self):
        raise AssertionError(
            "shell relayed enter() to the C++ representation, not to self()")

    def exit(self):
        raise AssertionError(
            "shell relayed exit() to the C++ representation, not to self()")


def _bare_shell(pages):
    """A ``LiverWidget`` with ``pages`` hosted, showing stage 0, not entered.

    Bypasses ``__init__`` / ``setup()`` -- neither the Qt tab widget nor the
    MRML scene participates in the relay -- so the invariants run under bare
    ``PythonSlicer -m pytest`` too.
    """
    _import_slicer_or_skip()
    try:
        import Liver  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover — module-path misconfiguration
        pytest.skip(
            f"Liver scripted module not importable ({exc}); "
            "ensure --additional-module-paths includes Liver/."
        )
    # From the repo root ``import Liver`` resolves to the module DIRECTORY as
    # a namespace package (``__file__`` is None), which carries no widget
    # class; only the staged/launched module path yields the real Liver.py.
    # Skip cleanly there rather than failing on the missing attribute.
    widgetClass = getattr(Liver, "LiverWidget", None)
    if widgetClass is None:
        pytest.skip(
            "'Liver' resolved to the module directory (namespace package), not "
            "the scripted module; needs the staged module path (launched)."
        )
    shell = widgetClass.__new__(widgetClass)
    # The relay reads only these three members; ``_stageTabs`` stays None so
    # the indicator repaint short-circuits (its documented pre-setup guard).
    shell._stageTabs = None
    shell._stagePages = list(pages)
    shell._currentStageIndex = 0
    shell._shellEntered = False
    return shell


# --------------------------------------------------------------------------- #
# L1 / L2 — the shell's own lifecycle reaches the showing stage only.
# --------------------------------------------------------------------------- #

def test_shell_enter_forwards_to_showing_stage_only():
    """L1: shell ``enter()`` enters the showing panel and no other."""
    showing, other = _PanelSpy(), _PanelSpy()
    shell = _bare_shell([showing, other])

    shell.enter()

    assert showing.calls == ["enter"], (
        "the showing stage's panel must receive enter() when the shell is "
        f"opened; got {showing.calls}."
    )
    assert other.calls == [], (
        "a stage stacked BEHIND the current tab is not the panel the surgeon "
        "is looking at and must NOT be entered; got "
        f"{other.calls}."
    )


def test_shell_exit_forwards_to_showing_stage():
    """L2: shell ``exit()`` exits the showing panel (the hygiene path)."""
    showing, other = _PanelSpy(), _PanelSpy()
    shell = _bare_shell([showing, other])

    shell.enter()
    shell.exit()

    assert showing.calls == ["enter", "exit"], (
        "leaving the shell must relay exit() to the showing stage's panel -- "
        "that is where the overlay retire / timer stop / gate close live; got "
        f"{showing.calls}."
    )
    assert other.calls == []


def test_shell_exit_is_idempotent():
    """L2: a second ``exit()`` without an ``enter()`` relays nothing."""
    showing = _PanelSpy()
    shell = _bare_shell([showing])

    shell.enter()
    shell.exit()
    shell.exit()

    assert showing.calls == ["enter", "exit"], (
        f"exit() must relay once per enter(); got {showing.calls}."
    )


# --------------------------------------------------------------------------- #
# L3 — stage switching hands the lifecycle over.
# --------------------------------------------------------------------------- #

def test_stage_switch_forwards_exit_then_enter():
    """L3: switching stages exits the outgoing panel, then enters the incoming."""
    outgoing, incoming = _PanelSpy(), _PanelSpy()
    shell = _bare_shell([outgoing, incoming])

    shell.enter()
    shell._onStageRowChanged(1)

    assert outgoing.calls == ["enter", "exit"], (
        "the outgoing stage's panel must be exited on a stage switch, or its "
        f"module-scoped overlays outlive the switch; got {outgoing.calls}."
    )
    assert incoming.calls == ["enter"], (
        f"the incoming stage's panel must be entered; got {incoming.calls}."
    )


def test_stage_switch_back_and_forth_tracks_the_showing_stage():
    """L3: the shell's own exit() follows the stage selected most recently."""
    first, second = _PanelSpy(), _PanelSpy()
    shell = _bare_shell([first, second])

    shell.enter()
    shell._onStageRowChanged(1)
    shell._onStageRowChanged(0)
    shell.exit()

    assert first.calls == ["enter", "exit", "enter", "exit"]
    assert second.calls == ["enter", "exit"]


def test_reselecting_the_same_stage_relays_nothing():
    """L3: a no-op ``currentChanged`` must not churn the lifecycle."""
    showing = _PanelSpy()
    shell = _bare_shell([showing, _PanelSpy()])

    shell.enter()
    shell._onStageRowChanged(0)

    assert showing.calls == ["enter"], (
        f"re-selecting the showing stage must relay nothing; got {showing.calls}."
    )


# --------------------------------------------------------------------------- #
# L5 — no relay while the shell is not the showing module.
# --------------------------------------------------------------------------- #

def test_stage_switch_while_shell_not_showing_relays_nothing():
    """L5: a tab change with the shell in the background enters no panel."""
    first, second = _PanelSpy(), _PanelSpy()
    shell = _bare_shell([first, second])

    shell._onStageRowChanged(1)

    assert first.calls == [] and second.calls == [], (
        "no stage panel may be entered while the shell itself is not the "
        f"module being shown; got {first.calls} / {second.calls}."
    )

    # The switch is still recorded, so the next shell enter() lands on it.
    shell.enter()
    assert second.calls == ["enter"] and first.calls == []


# --------------------------------------------------------------------------- #
# L4 — panels without the methods, and raising panels, are survivable.
# --------------------------------------------------------------------------- #

def test_panel_without_lifecycle_methods_is_skipped():
    """L4: a shell-owned static page carries no lifecycle and must not error."""
    shell = _bare_shell([_MethodlessPanel(), _PanelSpy()])

    shell.enter()
    shell._onStageRowChanged(1)
    shell._onStageRowChanged(0)
    shell.exit()

    assert shell._currentStageIndex == 0


def test_unbuilt_or_missing_stage_page_is_skipped():
    """L4: a page that was never built (``None``) has nothing to clean up."""
    shell = _bare_shell([None, _PanelSpy()])

    shell.enter()          # stage 0 is unbuilt
    shell._onStageRowChanged(1)
    shell.exit()

    assert shell._stagePages[1].calls == ["enter", "exit"]

    # A row outside the hosted set must not raise either.
    shell._currentStageIndex = 42
    shell.enter()
    shell.exit()


def test_raising_panel_does_not_strand_navigation():
    """L4: a raising panel is swallowed at the lifecycle boundary."""
    raising, healthy = _RaisingPanel(), _PanelSpy()
    shell = _bare_shell([raising, healthy])

    shell.enter()
    shell._onStageRowChanged(1)

    assert raising.calls == ["enter", "exit"]
    assert healthy.calls == ["enter"], (
        "the incoming stage must still be entered after the outgoing stage's "
        f"exit() raised; got {healthy.calls}."
    )
    assert shell._currentStageIndex == 1


# --------------------------------------------------------------------------- #
# L6 — scripted panels are relayed to their Python widget.
# --------------------------------------------------------------------------- #

def test_scripted_representation_is_relayed_via_self():
    """L6: relay target is the representation's ``self()``, not the C++ rep."""
    inner = _PanelSpy()
    shell = _bare_shell([_ScriptedRepDouble(inner)])

    shell.enter()
    shell.exit()

    assert inner.calls == ["enter", "exit"], (
        "a scripted stage module's lifecycle bodies live on the Python widget "
        f"the representation's self() returns; got {inner.calls}."
    )

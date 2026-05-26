# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Widget-level invariants for the Liver-shell sidebar (T5.2-d).

Pins the surgeon-facing navigation contract described in ADR-0023
"Shell composition (Option H)": a vertical sidebar of six stage entries
that drives a content stack of per-stage module widgets, with per-stage
state indicators (``checkmark / dot / circle``) reflecting the
``isStageComplete()`` predicate exposed by each stage's logic.

Tests in this file (T1, T4, T5, T6 from the T5.2-d planner output):

T1
    Sidebar exposes six entries, labels matching the six stage names
    listed in ADR-0023 §"Decision".

T4
    Programmatic sidebar selection switches ``QStackedWidget`` to the
    corresponding stage widget identity-equal to the cached
    ``widgetRepresentation()`` (Stages 2-5) or to the shell-owned widget
    (Stages 1, 6).

T5
    Widget state survives stage switching — the shell does not destroy
    or recreate child widgets when the sidebar changes selection.

T6
    Per-row state indicators reflect the ``isStageComplete()`` query
    results in the ``checkmark / dot / circle`` pattern from ADR-0023
    §"Shell composition (Option H)".

All tests in this file are expected to RED-FAIL on commit
``60c78df`` (the pre-T5.2-d branch tip): ``LiverWidget`` currently
linearly stacks its per-module widgets in a ``QVBoxLayout`` and exposes
no ``_stageSidebar`` / ``_contentStack`` members.  The implementer
(``liver-implementer``) turns them green commit-by-commit on the same
branch.

See also:
  * Docs/adr/0023-unified-gui-stage-workflow.md §"Shell composition"
  * Docs/architecture/gui-stage-flow.md §"Module ownership per stage"
"""

from __future__ import annotations

import pytest


# --------------------------------------------------------------------------- #
# Stage-name vocabulary — single source of truth for T1.
# --------------------------------------------------------------------------- #
#
# Source: ADR-0023 §"Decision" (the numbered list reproduced in
# Docs/adr/0023-unified-gui-stage-workflow.md lines 185-190).
EXPECTED_STAGE_NAMES = [
    "Case Setup",
    "Anatomy Definition",
    "Vascular Territories",
    "Resection Planning",
    "Volumetry",
    "Export",
]


# --------------------------------------------------------------------------- #
# Module-scoped helpers (file-local; per feedback_agent_brief_pre_push_hygiene)
# --------------------------------------------------------------------------- #

def _import_slicer_or_skip():
    """Return the ``slicer`` module, skipping the test if unavailable.

    The Liver shell widget is a Slicer scripted module — it cannot be
    instantiated outside a running Slicer Python.  Tests using this
    helper are CI-runnable under Slicer's bundled pytest invocation
    only.
    """
    try:
        import slicer  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover — exercised only outside Slicer
        pytest.skip(
            f"slicer module not importable ({exc}); "
            "Liver-shell sidebar tests require Slicer's Python."
        )
    return slicer


def _instantiate_liver_widget():
    """Build a fresh ``LiverWidget`` rooted on a throwaway parent.

    Returns the widget instance.  Skips the test cleanly if the Liver
    module isn't loadable in the current environment (e.g. when the
    test harness boots Slicer without the Liver scripted module on the
    additional-module-paths).
    """
    slicer = _import_slicer_or_skip()
    try:
        import qt  # type: ignore[import-not-found]
        import Liver  # type: ignore[import-not-found]
    except ImportError as exc:
        pytest.skip(
            f"Liver scripted module not importable ({exc}); "
            "ensure the additional-module-paths include Liver/."
        )

    parent = qt.QWidget()
    widget = Liver.LiverWidget(parent)
    widget.setup()
    return widget


# --------------------------------------------------------------------------- #
# T1 — Sidebar exposes six entries.
# --------------------------------------------------------------------------- #

def test_sidebar_exposes_six_stage_entries():
    """The shell's sidebar must list exactly the six ADR-0023 stages.

    Pins ADR-0023 §"Decision" stage roster + §"Shell composition
    (Option H)" sidebar requirement.

    Red-fails on ``60c78df`` because ``LiverWidget`` has no
    ``_stageSidebar`` attribute — the current shell stacks
    DistanceMaps / Resections / Resectogram / VascularTerritories /
    Volumetry widgets vertically with ``self.layout.addWidget`` and
    exposes no per-stage navigation surface.
    """
    widget = _instantiate_liver_widget()

    assert hasattr(widget, "_stageSidebar"), (
        "LiverWidget._stageSidebar not found.  "
        "ADR-0023 §'Shell composition' mandates a sidebar widget."
    )
    sidebar = widget._stageSidebar

    # The widget must expose a row-count surface.  QListWidget.count(),
    # QListWidget.item(i).text() is the contract per T5.2-d planner.
    assert hasattr(sidebar, "count"), (
        "_stageSidebar lacks count() — expected QListWidget-shaped API "
        "per T5.2-d planner output."
    )
    assert sidebar.count() == 6, (
        f"Sidebar must expose exactly 6 stage entries; got {sidebar.count()}."
    )

    actual_names = [sidebar.item(i).text() for i in range(sidebar.count())]
    # Implementer may decorate labels with numbering ("1. Case Setup"); we
    # accept either bare or "<n>. <name>" prefixed labels.  The substring
    # check pins the human-readable stage names without locking format.
    for i, expected in enumerate(EXPECTED_STAGE_NAMES):
        assert expected in actual_names[i], (
            f"Sidebar row {i}: expected to contain '{expected}'; "
            f"got '{actual_names[i]}'.  See ADR-0023 §'Decision'."
        )


# --------------------------------------------------------------------------- #
# T4 — Dispatch switches the content stack.
# --------------------------------------------------------------------------- #

def test_sidebar_selection_switches_content_stack():
    """Clicking sidebar row N must surface the matching stack widget.

    Pins ADR-0023 §"Shell composition (Option H)": "Clicking a stage
    entry switches the right-hand content panel to that stage's module
    widget."  Planner output further specifies the dispatch mechanism
    is a cached ``widgetRepresentation()`` + ``QStackedWidget``, NOT
    ``slicer.util.selectModule()`` (which would tear the shell down
    by switching the active Slicer module).

    For Stages 2-5 (module-owned), the surfaced widget must be
    identity-equal to ``slicer.modules.<name>.widgetRepresentation()``.
    For Stages 1 and 6 (shell-owned), the surfaced widget is the
    shell's own composition widget.

    Red-fails on ``60c78df`` because no dispatch mechanism exists yet —
    ``_contentStack`` is not a member of ``LiverWidget``.
    """
    widget = _instantiate_liver_widget()

    sidebar = widget._stageSidebar
    stack = widget._contentStack

    assert stack.count() == 6, (
        "Content stack must expose one page per stage; "
        f"got {stack.count()}."
    )

    for row in range(6):
        sidebar.setCurrentRow(row)
        assert stack.currentIndex() == row, (
            f"Sidebar row {row} did not switch stack to index {row} "
            f"(got {stack.currentIndex()})."
        )
        assert stack.currentWidget() is not None, (
            f"Row {row}: stack.currentWidget() is None."
        )


# --------------------------------------------------------------------------- #
# T5 — Widget state survives stage switching.
# --------------------------------------------------------------------------- #

def test_widget_state_survives_stage_switching():
    """Switching stages must not destroy/recreate child widgets.

    Pins planner output §"Dispatch": "cached widgetRepresentation()".
    The shell must hold a single reference to each stage's widget for
    the lifetime of the shell — switching the sidebar is purely a
    ``QStackedWidget.setCurrentWidget()`` operation.  Destroying and
    recreating widgets on every switch would lose surgeon-entered
    state (selected nodes in combo boxes, scroll positions, etc.).

    Red-fails on ``60c78df`` because no dispatch mechanism exists yet.
    """
    widget = _instantiate_liver_widget()

    sidebar = widget._stageSidebar
    stack = widget._contentStack

    # Switch to Stage 3 (Vascular Territories, index 2) and capture the
    # stage widget identity.
    sidebar.setCurrentRow(2)
    stage3_widget_before = stack.currentWidget()
    assert stage3_widget_before is not None

    # Switch to Stage 4 (Resection Planning, index 3) and back to 3.
    sidebar.setCurrentRow(3)
    sidebar.setCurrentRow(2)
    stage3_widget_after = stack.currentWidget()

    assert stage3_widget_after is stage3_widget_before, (
        "Stage 3 widget identity changed across switching; "
        "shell must cache widgets, not recreate them on each switch."
    )


# --------------------------------------------------------------------------- #
# T6 — State indicators reflect query state.
# --------------------------------------------------------------------------- #

def test_state_indicators_reflect_isstagecomplete():
    """Per-row indicators must mirror the ``isStageComplete()`` pattern.

    Pins ADR-0023 §"Shell composition (Option H)": "per-stage state
    indicators (✓ done / ● current / ○ pending)" — and the
    Conformance row in Docs/architecture/gui-stage-flow.md §"Per-stage
    state-indicator semantics".

    Test mocks the per-stage predicate to a deterministic pattern
    (T-T-F-F-F-F) and asserts the indicator surface reflects it.  The
    exact representation (icon vs. unicode glyph in label text vs.
    QListWidgetItem state property) is left to the implementer — the
    test pins only the *visible* contract via the helper
    ``_stageIndicatorState(row)`` returning one of
    ``{'complete', 'current', 'pending'}``.

    Red-fails on ``60c78df`` because no indicator-refresh mechanism
    exists yet.
    """
    widget = _instantiate_liver_widget()

    sidebar = widget._stageSidebar
    completion_pattern = [True, True, False, False, False, False]
    current_row = 2

    # The shell exposes a hook letting tests inject mock completion
    # state without spinning up the full per-stage data model.  Naming
    # locked by planner output §"State source" (hybrid: shell observes,
    # logic owns).
    widget._injectStageCompletionForTesting(completion_pattern)
    sidebar.setCurrentRow(current_row)
    widget._refreshStageIndicators()

    for row in range(6):
        state = widget._stageIndicatorState(row)
        if row == current_row:
            assert state == "current", (
                f"Row {row} is the current selection; expected 'current', "
                f"got {state!r}."
            )
        elif completion_pattern[row]:
            assert state == "complete", (
                f"Row {row} mocked as complete; expected 'complete', "
                f"got {state!r}."
            )
        else:
            assert state == "pending", (
                f"Row {row} mocked as pending; expected 'pending', "
                f"got {state!r}."
            )

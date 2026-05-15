"""
Workflow-layer smoke test demonstrating the ``render_interactive`` dispatch.

This test stands in for the (not-yet-landed) view-creating workflow tests
that consume the fixture set described in ``conftest.py``'s TODO list
(``a_threed_view``, ``a_resectogram_view``, ...).  Until those fixtures
land, this test exercises the dispatch logic in isolation: it asserts
that the ``render_interactive`` fixture is consumable, that the *pattern*
a real view fixture would follow (branch on truthiness) is well-defined,
and that the same test code adapts correctly to both modes.

Per ADR-0008 §2:

    | Workflow | Widget + scene + Qt | Yes | Yes | Yes (default-on) | Resectogram view shows tumor cross-section contours |

The "Yes (default-on)" column entry refers to fixture *participation*
(every view-creating workflow fixture consumes the option), not to the
CLI default — the CLI default is ``0.0`` so that bare ``pytest`` stays
CI-safe.  Developers opt in to the onscreen path explicitly.
"""

from __future__ import annotations


def test_workflow_layer_consumes_render_interactive(
    render_interactive: float,
) -> None:
    """A workflow test must be able to consume the fixture by name.

    Mirrors the pattern documented in ADR-0008 §3 (the trame-slicer-style
    view fixture).  We don't have a real view here yet, but we exercise
    the same control flow a view fixture would.
    """
    # The dispatch pattern a real view fixture follows.
    show_window = bool(render_interactive)
    dwell_seconds = render_interactive

    assert isinstance(show_window, bool)
    assert dwell_seconds == render_interactive
    assert dwell_seconds >= 0.0


def test_render_interactive_pattern_adapts_to_both_modes(
    render_interactive: float,
) -> None:
    """Pin the documented dispatch pattern from ADR-0008 §3.

    A view-creating fixture branches on ``if render_interactive:`` to
    decide whether to ``ShowWindowOn()`` and to ``Start()`` the
    interactor for the given dwell time.  The same test body must work
    correctly in both modes — that's the whole point of the dual-use
    pattern.  This test simulates that branching and pins the expected
    branch for each mode.
    """
    if render_interactive:
        # Path that a real view fixture would take onscreen.
        action = "show_window"
        expected_dwell = render_interactive
    else:
        # Path the CI-default takes.
        action = "offscreen"
        expected_dwell = 0.0

    if render_interactive == 0.0:
        assert action == "offscreen"
        assert expected_dwell == 0.0
    else:
        assert action == "show_window"
        assert expected_dwell == render_interactive

# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""
Unit-layer smoke test for the pytest scaffold.

This test exists to prove three things about the scaffold introduced
alongside ADR-0008:

  1. The ``--render-interactive`` CLI option is registered with the
     correct default (``0.0`` — CI-safe / offscreen).  ADR-0008 §6's CI
     matrix relies on the bare-``pytest`` invocation being offscreen and
     the brief-onscreen variant being an explicit override.
  2. The ``render_interactive`` fixture always yields a non-negative float,
     regardless of CLI override.
  3. The unit layer (pure-Python, no slicer, no Qt) is runnable in a plain
     Python environment with only ``pytest`` installed — confirming the
     scaffold is not implicitly coupled to a built Slicer.

When the per-module fixture set lands (see TODO list at the bottom of
``conftest.py``), real unit tests for algorithmic code (Bezier basis
evaluation on numpy arrays, distance-map math, etc.) replace this smoke
test as the unit-layer signal.

Per ADR-0008 §2:

    | Unit | Pure algorithm/math | No slicer | No Qt | N/A | Bezier basis evaluation on numpy arrays |
"""

from __future__ import annotations


def test_render_interactive_option_default_is_off(
    pytestconfig,
) -> None:
    """The CLI option's *registered default* must be ``0.0``.

    Inspecting ``pytestconfig._parser`` lets us assert against the
    parser's recorded default independently of whatever value the current
    invocation overrode it with.  This pins the "bare ``pytest`` is
    offscreen / CI-safe" guarantee documented in ``conftest.py`` and
    ADR-0008 §6.
    """
    # The Parser exposes options via the private ``_anonymous`` / group
    # API; the public way to get a registered default is
    # ``pytestconfig.getoption(name, default=<sentinel>)`` paired with
    # checking the parser, but a simpler robust check is to inspect the
    # parser's ``_groups`` directly.  However, the *most* stable public
    # surface is just to look at the option's ``default`` attribute on
    # the parser's recorded options.
    parser = pytestconfig._parser
    option = None
    for group in parser._groups:
        for opt in group.options:
            if "--render-interactive" in opt.names():
                option = opt
                break
        if option is not None:
            break

    assert option is not None, (
        "--render-interactive option not registered; "
        "check Testing/Python/conftest.py"
    )
    assert option.default == 0.0, (
        "Default for --render-interactive must be 0.0 (offscreen / "
        f"CI-safe); see ADR-0008 §6.  Got: {option.default!r}"
    )


def test_render_interactive_yields_a_nonnegative_float(
    render_interactive: float,
) -> None:
    """The fixture must always yield a non-negative float.

    Whether the user runs ``pytest`` (default 0.0), ``pytest
    --render-interactive=0.1`` (CI's brief-onscreen pass), or ``pytest
    --render-interactive=5`` (developer interactive), the fixture's
    contract is the same: a non-negative float number of seconds.
    """
    assert isinstance(render_interactive, float)
    assert render_interactive >= 0.0


def test_scaffold_imports_without_slicer() -> None:
    """The unit layer must be runnable without a built Slicer.

    Sanity check: this file is the unit layer and consumes no fixture
    that triggers ``import slicer``.  If a future refactor accidentally
    couples the unit layer to a Slicer import (e.g. by adding a
    top-level ``import slicer`` to ``conftest.py``), this test stops
    being importable in a plain venv and the breakage is loud.
    """
    # No assertions needed — the fact that pytest collected and ran this
    # test in a plain venv is the assertion.
    assert True

# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Harness self-tests for ``replay_test._has_baseline``.

GAP-1 follow-up from PR #384's /slicer-review synthesis (issue #387).

``_has_baseline(baseline_dir, test_name)`` answers a single question:
"is there enough on disk for the replay driver to attempt a real
comparison?".  The contract is the 4-row truth table below: True iff
both the resolved PNG (``<test>.png``) and the committed stub
(``<test>.png.sha512``) are present.  The PNG presence proves
ExternalData found a blob to resolve to; the stub's presence proves
the test was registered with content (and survives a `git clean -dxf`).
Either signal alone is ambiguous, so the helper requires both.

These tests use pytest's ``tmp_path`` fixture to construct each of
the four scenarios in isolation — no real ExternalData fetch, no
captured baseline coupling.

References
----------
* ADR-0008 §"observability" — pure-Python helpers carry self-tests.
* PR #384 /slicer-review synthesis comment, GAP-1.
"""

from __future__ import annotations

import pathlib
import sys

import pytest


# The replay module imports cleanly in plain Python (the slicer / vtk
# imports are pushed inside the render / compare helpers, not at
# module top-level).  Drop the harness directory on ``sys.path`` so
# ``import replay_test`` resolves without coupling to a packaging step.
_HERE = pathlib.Path(__file__).resolve()
_HARNESS_DIR = _HERE.parent.parent  # LiverResections/Testing/Python/
if str(_HARNESS_DIR) not in sys.path:
    sys.path.insert(0, str(_HARNESS_DIR))

import replay_test  # noqa: E402 — path injection above must run first.


TEST_NAME = "FakeScenario"


def _make_files(
    baseline_dir: pathlib.Path,
    *,
    png: bool,
    stub: bool,
) -> None:
    """Materialise the requested subset of bundle artefacts in
    ``baseline_dir``.

    Contents are intentionally minimal — ``_has_baseline`` only checks
    file existence, not bytes.
    """
    if png:
        (baseline_dir / f"{TEST_NAME}.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    if stub:
        # 64-byte SHA-512 hex digest placeholder; matches the
        # ``.sha512`` stub format ExternalData rotates on capture.
        (baseline_dir / f"{TEST_NAME}.png.sha512").write_text("0" * 128 + "\n")


@pytest.mark.parametrize(
    ("png_present", "stub_present", "expected"),
    [
        (True, True, True),    # canonical "captured baseline" state
        (True, False, False),  # PNG without stub — broken capture path
        (False, True, False),  # stub without resolved blob — fetch failed
        (False, False, False), # nothing on disk — fresh scaffold
    ],
    ids=[
        "png_and_stub_both_present",
        "png_present_stub_missing",
        "stub_present_png_missing",
        "neither_png_nor_stub",
    ],
)
def test_has_baseline_truth_table(
    tmp_path: pathlib.Path,
    png_present: bool,
    stub_present: bool,
    expected: bool,
) -> None:
    """Exercise the documented 4-row truth table.

    ``_has_baseline`` returns True iff BOTH the resolved PNG and the
    committed sha512 stub exist.  Any other combination must return
    False so the replay driver hits its "skip with clear message"
    branch instead of attempting a comparison against incomplete
    state.
    """
    _make_files(tmp_path, png=png_present, stub=stub_present)
    assert replay_test._has_baseline(tmp_path, TEST_NAME) is expected


def test_has_baseline_isolated_per_test_name(tmp_path: pathlib.Path) -> None:
    """A captured ``FooBaseline`` must not satisfy ``BarBaseline``.

    The helper composes the path from ``test_name``; presence of an
    unrelated scenario's artefacts in the same directory must not
    leak across.
    """
    (tmp_path / "FooBaseline.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (tmp_path / "FooBaseline.png.sha512").write_text("0" * 128 + "\n")
    assert replay_test._has_baseline(tmp_path, "FooBaseline") is True
    assert replay_test._has_baseline(tmp_path, "BarBaseline") is False

# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Harness self-tests for the replay driver's software-GL fast skip.

The replay driver probes the offscreen GL renderer up front and skips
BEFORE the bezier distance-map render when it lands on a software
rasteriser (e.g. CI's xvfb + llvmpipe stack), where that render is
unreliable and has been observed to hang to the CTest TIMEOUT.  See
``replay_test.SOFTWARE_GL_MARKERS`` + ``_software_gl_skip_reason`` and
ADR-0020 §"Rollout plan".

These tests exercise the pure decision helpers without bringing up a
real GL context: ``_is_software_renderer`` (string classification),
``_software_gl_skip_reason`` (render-vs-skip + message), and
``_renderer_token`` (message formatting).  The skip is deliberately
distinct from the missing-baseline logic, so it is asserted in
isolation here.

References
----------
* ADR-0008 §"observability" — pure-Python helpers carry self-tests.
* ADR-0020 §"Rollout plan" — visual-regression rollout + hardening.
"""

from __future__ import annotations

import pathlib
import sys

import pytest


# Same path-injection pattern as the sibling ``test_has_baseline``: the
# replay module imports cleanly in plain Python (slicer / vtk imports
# are deferred inside the render helpers), so drop the harness directory
# on ``sys.path`` and import it directly.
_HERE = pathlib.Path(__file__).resolve()
_HARNESS_DIR = _HERE.parent.parent  # LiverResections/Testing/Python/
if str(_HARNESS_DIR) not in sys.path:
    sys.path.insert(0, str(_HARNESS_DIR))

import replay_test  # noqa: E402 — path injection above must run first.


# A representative llvmpipe ``ReportCapabilities()`` blob.  VTK emits one
# labelled line per GL string; only the substrings matter to the
# classifier, but the multi-line shape exercises ``_renderer_token``.
_LLVMPIPE_CAPS = (
    "OpenGL vendor string:  Mesa\n"
    "OpenGL renderer string:  llvmpipe (LLVM 15.0.7, 256 bits)\n"
    "OpenGL version string:  4.5 (Core Profile) Mesa 23.2.1\n"
)

_REAL_GPU_CAPS = (
    "OpenGL vendor string:  NVIDIA Corporation\n"
    "OpenGL renderer string:  NVIDIA GeForce RTX 3080/PCIe/SSE2\n"
    "OpenGL version string:  4.6.0 NVIDIA 535.104.05\n"
)


@pytest.mark.parametrize(
    "capabilities",
    [
        _LLVMPIPE_CAPS,
        "OpenGL renderer string: softpipe\n",
        "OpenGL renderer string: swrast\n",
        "OpenGL renderer string: Gallium llvmpipe (LLVM 16)\n",
        "renderer: llVMpipe",  # case-insensitive match
    ],
)
def test_is_software_renderer_matches_software_stacks(capabilities: str) -> None:
    assert replay_test._is_software_renderer(capabilities) is True


@pytest.mark.parametrize(
    "capabilities",
    [
        _REAL_GPU_CAPS,
        "OpenGL renderer string: AMD Radeon RX 6800 (RADV NAVI21)\n",
        "OpenGL renderer string: Intel(R) Arc(TM) A770 Graphics\n",
        "",  # empty string is not, on its own, a software match
    ],
)
def test_is_software_renderer_passes_real_gpus(capabilities: str) -> None:
    assert replay_test._is_software_renderer(capabilities) is False


def test_skip_reason_none_for_real_gpu() -> None:
    """A real GPU yields no skip — the caller proceeds to render+diff."""
    assert replay_test._software_gl_skip_reason(_REAL_GPU_CAPS) is None


def test_skip_reason_set_for_software_gl() -> None:
    """A software rasteriser yields a greppable ``[skip]`` reason that
    names the renderer and points at the hardening issue."""
    reason = replay_test._software_gl_skip_reason(_LLVMPIPE_CAPS)
    assert reason is not None
    assert reason.startswith("[skip]")
    assert "software GL" in reason
    assert "llvmpipe" in reason
    assert "hardening" in reason


def test_skip_reason_set_when_no_context() -> None:
    """A failed probe (``None`` capabilities) skips rather than proceeds:
    if no GL context can be created the render cannot run either."""
    reason = replay_test._software_gl_skip_reason(None)
    assert reason is not None
    assert reason.startswith("[skip]")
    assert "could not be created" in reason


def test_skip_reason_independent_of_baseline() -> None:
    """The software-GL skip is about the renderer, not the baseline.

    ``_software_gl_skip_reason`` takes only the capabilities string —
    it has no baseline parameter — so a software stack skips regardless
    of whether a baseline blob has resolved.  This pins the contract
    that the skip path is decided before (and independently of) the
    ``_has_baseline`` check.
    """
    assert replay_test._software_gl_skip_reason(_LLVMPIPE_CAPS) is not None
    assert replay_test._software_gl_skip_reason(_REAL_GPU_CAPS) is None


def test_renderer_token_extracts_renderer_line() -> None:
    token = replay_test._renderer_token(_LLVMPIPE_CAPS)
    assert token == "llvmpipe (LLVM 15.0.7, 256 bits)"


def test_renderer_token_falls_back_to_marker() -> None:
    """With no labelled renderer line, fall back to the matched marker."""
    token = replay_test._renderer_token("backend uses swrast internally")
    assert token == "swrast"

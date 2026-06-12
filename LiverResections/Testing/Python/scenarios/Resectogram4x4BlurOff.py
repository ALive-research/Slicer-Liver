# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Visual-regression scenario: 4x4 resectogram, BLUR OFF, square scaling.

T3 ResectogramPipeline baseline target (ADR-0027 invariant-test-first).
This is the reference resectogram appearance: the flattened parametric
image of a square (u, v) domain Bezier surface, rendered through the T3
ResectogramPipeline's flattened-surface Representation, with the
Gaussian-blur post-pass DISABLED.

Capture-then-rebaseline contract
--------------------------------
Per the T3 plan these baselines capture against the v1 monolith
(``vtkSlicerBezierSurfaceRepresentation3D`` 5th-renderer resectogram)
FIRST, establishing the pixels v2.0 must reproduce, then are RE-BASELINED
to the v2.0 ResectogramPipeline once it lands.  The capture is
maintainer-driven (``capture_baseline.py``); until a ``.sha512`` stub is
committed under ``../Data/Baseline/`` the replay driver skips this
scenario with a clear log line.

Module-layer test, ADR-0008 §2/§3 (workflow row, ``render_interactive``
fixture).  Importable from a pristine ``--no-main-window`` Slicer boot;
``setup_scene`` exercises the production ResectogramPipeline path rather
than hand-building MRML.

References
----------
* ADR-0008 §2/§3 — module/workflow visual-regression discipline +
  capture-then-replay harness.
* ADR-0013 §6 — the flattened-surface Representation owned by the
  ResectogramPipeline.
* ADR-0027 — invariant-test-first; baseline captured before the v2.0
  rewrite, re-baselined after.
"""

from __future__ import annotations

# Shared viewport configuration for the resectogram panel.  The
# resectogram is a 2D flattened image, so a parallel-projection square
# panel is used; the exact numbers are pinned at first capture.
VIEWPORT_WIDTH = 600
VIEWPORT_HEIGHT = 600
BACKGROUND_RGB = (0.0, 0.0, 0.0)
ANTI_ALIASING_FRAMES = 0  # deterministic; AA introduces sub-pixel jitter

# Whether the Gaussian-blur post-pass is engaged.  This scenario pins the
# blur-OFF reference; Resectogram4x4BlurOn pins blur-ON.
BLUR_ENABLED = False

# Square (u, v) domain — control points span equal extents in u and v so
# the aspect-ratio helper yields {1, 1} (no anisotropic squeeze).  This
# is the counterpart to Resectogram4x4NonSquareScaling.
PATCH_HALF_EXTENT_U = 45.0
PATCH_HALF_EXTENT_V = 45.0


def setup_scene():
    """Populate the scene with the blur-off square-domain resectogram fixture.

    TODO(liver-implementer): build the scene via the production
    LiverResections logic + the T3 ResectogramPipeline, mirroring
    ``BezierSurface4x4Planning.setup_scene`` but adding a
    ``vtkMRMLResectogramDisplayNode`` (ADR-0013 §5 KEYING) with
    ``BLUR_ENABLED = False`` and a square (u, v) control-point layout.
    Return the created resection node.
    """
    raise NotImplementedError(
        "Resectogram4x4BlurOff.setup_scene is a T3 baseline target; the "
        "ResectogramPipeline + vtkMRMLResectogramDisplayNode do not exist "
        "yet.  This body is reached only once a baseline .sha512 stub is "
        "committed (see module docstring); until then the replay driver "
        "skips before calling it."
    )


def setup_camera(view_node=None):
    """Fix the resectogram panel's deterministic (parallel) view.

    TODO(liver-implementer): set the parallel-projection pose that frames
    the full flattened [0,1]^2 domain; pin the numbers at first capture.
    """
    raise NotImplementedError(
        "Resectogram4x4BlurOff.setup_camera is a T3 baseline target."
    )


def setup_viewport(view_node=None):
    """Set resectogram panel pixel size, background, anti-aliasing.

    TODO(liver-implementer): mirror ``BezierSurface4x4Planning`` viewport
    fixing (AA off for reproducibility).
    """
    raise NotImplementedError(
        "Resectogram4x4BlurOff.setup_viewport is a T3 baseline target."
    )


def describe() -> dict:
    """Metadata persisted alongside the captured bundle."""
    return {
        "scenario": "Resectogram4x4BlurOff",
        "blur_enabled": BLUR_ENABLED,
        "viewport": {
            "size": [VIEWPORT_WIDTH, VIEWPORT_HEIGHT],
            "background": list(BACKGROUND_RGB),
            "anti_aliasing_frames": ANTI_ALIASING_FRAMES,
        },
    }

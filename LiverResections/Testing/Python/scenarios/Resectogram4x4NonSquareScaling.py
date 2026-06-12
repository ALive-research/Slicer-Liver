# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Visual-regression scenario: 4x4 resectogram, NON-SQUARE aspect scaling.

T3 ResectogramPipeline baseline target (ADR-0027 invariant-test-first).
This scenario is the VISUAL counterpart of the pure-math
``vtkLiverResectogramAspectRatioTest``: it pins the on-screen effect of
the anisotropic ``MatRatio`` scaling for a non-square (u, v) domain — the
longer parametric axis is normalised to fill the panel and the shorter
axis is squeezed by ``shorter/longer``.  A regression in the aspect-ratio
helper (e.g. a stub that always emits ``{1, 1}``) shows up here as a
square render where the baseline is rectangular.

Blur is OFF in this scenario so the only visual variable versus
``Resectogram4x4BlurOff`` is the domain aspect ratio.

Capture-then-rebaseline contract: same as ``Resectogram4x4BlurOff`` —
captured against the v1 monolith first, re-baselined to v2.0.

References
----------
* ADR-0008 §2/§3 — visual-regression harness.
* ADR-0013 §6 — flattened-surface Representation (carries the MatRatio
  scaling state per the maintainer decision).
* ADR-0027 — pairs with ``vtkLiverResectogramAspectRatioTest`` (the
  pure-math pin) as the pixel-level pin of the same invariant.
"""

from __future__ import annotations

VIEWPORT_WIDTH = 600
VIEWPORT_HEIGHT = 600
BACKGROUND_RGB = (0.0, 0.0, 0.0)
ANTI_ALIASING_FRAMES = 0

BLUR_ENABLED = False

# Non-square (u, v) domain — the v extent is twice the u extent, so the
# aspect-ratio helper yields {0.5, 1} (u squeezed to half).  This is the
# pixel-level counterpart of vtkLiverResectogramAspectRatioTest Case 2.
PATCH_HALF_EXTENT_U = 22.5
PATCH_HALF_EXTENT_V = 45.0


def setup_scene():
    """Populate the scene with the non-square-domain resectogram fixture.

    TODO(liver-implementer): lay out the 4x4 control points so the v
    parametric extent is twice the u extent (PATCH_HALF_EXTENT_V =
    2 * PATCH_HALF_EXTENT_U), and add a ``vtkMRMLResectogramDisplayNode``
    with blur OFF.  The rendered panel must show the v1 anisotropic
    squeeze; re-baseline to v2.0 once the ResectogramPipeline lands.
    """
    raise NotImplementedError(
        "Resectogram4x4NonSquareScaling.setup_scene is a T3 baseline target; "
        "reached only once a baseline .sha512 stub is committed."
    )


def setup_camera(view_node=None):
    """Fix the resectogram panel's deterministic (parallel) view."""
    raise NotImplementedError(
        "Resectogram4x4NonSquareScaling.setup_camera is a T3 baseline target."
    )


def setup_viewport(view_node=None):
    """Set resectogram panel pixel size, background, anti-aliasing."""
    raise NotImplementedError(
        "Resectogram4x4NonSquareScaling.setup_viewport is a T3 baseline target."
    )


def describe() -> dict:
    """Metadata persisted alongside the captured bundle."""
    return {
        "scenario": "Resectogram4x4NonSquareScaling",
        "blur_enabled": BLUR_ENABLED,
        "viewport": {
            "size": [VIEWPORT_WIDTH, VIEWPORT_HEIGHT],
            "background": list(BACKGROUND_RGB),
            "anti_aliasing_frames": ANTI_ALIASING_FRAMES,
        },
    }

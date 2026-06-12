# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Visual-regression scenario: 4x4 resectogram, BLUR ON, square scaling.

T3 ResectogramPipeline baseline target (ADR-0027 invariant-test-first).

SPLITTABLE / LAST.  Per the maintainer decision the Gaussian-blur
post-pass stays a v2.0 feature behind a toggle, and this baseline is
explicitly splittable from the rest of T3: if the launched harness
(issue #460) blocks baseline capture, the blur work — and this scenario
— land last, after the blur-OFF resectogram baselines are green.  It
exists now as a placed target so the test surface is complete and the
implementer knows GREEN here is the final T3 step, not a gate on the
core resectogram landing.

It differs from ``Resectogram4x4BlurOff`` only in ``BLUR_ENABLED`` —
same square (u, v) domain, same camera/viewport — so the pixel delta
isolates the blur post-pass.

Capture-then-rebaseline contract: captured against the v1 monolith first
(the v1 resectogram has no blur pass — see the T3 plan: "No
vtkGaussianBlurPass anywhere in tree => blur is net-new"), so the FIRST
baseline for this scenario is captured against the v2.0 path once the
blur toggle exists.  There is no v1 blur appearance to reproduce; this
scenario pins the v2.0 blur-on appearance directly.

References
----------
* ADR-0008 §2/§3 — visual-regression harness.
* ADR-0013 §6 — the blur is a per-frame state on the flattened-surface
  Representation owned by the ResectogramPipeline.
* ADR-0027 — invariant-test-first; this target is splittable/last.
"""

from __future__ import annotations

VIEWPORT_WIDTH = 600
VIEWPORT_HEIGHT = 600
BACKGROUND_RGB = (0.0, 0.0, 0.0)
ANTI_ALIASING_FRAMES = 0

# The one variable that distinguishes this scenario from
# Resectogram4x4BlurOff.
BLUR_ENABLED = True

PATCH_HALF_EXTENT_U = 45.0
PATCH_HALF_EXTENT_V = 45.0


def setup_scene():
    """Populate the scene with the blur-on square-domain resectogram fixture.

    TODO(liver-implementer): identical to ``Resectogram4x4BlurOff`` but
    engage the Gaussian-blur post-pass via the
    ``vtkMRMLResectogramDisplayNode`` blur toggle (ADR-0013 §6 per-frame
    Representation state).  Author/land this LAST per the maintainer's
    splittable-blur decision.
    """
    raise NotImplementedError(
        "Resectogram4x4BlurOn.setup_scene is the SPLITTABLE/LAST T3 baseline "
        "target; reached only once a baseline .sha512 stub is committed."
    )


def setup_camera(view_node=None):
    """Fix the resectogram panel's deterministic (parallel) view."""
    raise NotImplementedError(
        "Resectogram4x4BlurOn.setup_camera is a T3 baseline target."
    )


def setup_viewport(view_node=None):
    """Set resectogram panel pixel size, background, anti-aliasing."""
    raise NotImplementedError(
        "Resectogram4x4BlurOn.setup_viewport is a T3 baseline target."
    )


def describe() -> dict:
    """Metadata persisted alongside the captured bundle."""
    return {
        "scenario": "Resectogram4x4BlurOn",
        "blur_enabled": BLUR_ENABLED,
        "viewport": {
            "size": [VIEWPORT_WIDTH, VIEWPORT_HEIGHT],
            "background": list(BACKGROUND_RGB),
            "anti_aliasing_frames": ANTI_ALIASING_FRAMES,
        },
    }

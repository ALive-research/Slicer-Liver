# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Visual-regression scenario: 4x4 resectogram, NON-SQUARE aspect scaling.

T3 ResectogramPipeline baseline target (ADR-0027 invariant-test-first).
This scenario is the VISUAL counterpart of the pure-math
``vtkLiverResectogramAspectRatioTest``: it pins the on-screen effect of
the anisotropic ``MatRatio`` scaling for a non-square ``(u, v)`` domain —
the longer parametric axis is normalised to fill the panel and the shorter
axis is squeezed by ``shorter/longer``.  A regression in the aspect-ratio
helper (e.g. a stub that always emits ``{1, 1}``) shows up here as a
square render where the baseline is rectangular.

Blur is OFF in this scenario so the only visual variable versus
``Resectogram4x4BlurOff`` is the domain aspect ratio.  The anisotropic
scaling is gated by ``EnableFlexibleBoundary`` on the legacy
``vtkMRMLMarkupsBezierSurfaceDisplayNode`` (drives
``vtkLiverResectogramAspectRatio`` / the v1 ``Ratio(bool)`` toggle), held
ON here so the squeeze is exercised.

Capture-then-rebaseline contract: same as ``Resectogram4x4BlurOff`` —
captured against the v1 monolith first, re-baselined to v2.0.  Until a
``.sha512`` stub lands the replay driver skips this scenario before the
body runs.

This scenario reuses the deterministic scene builders from
``Resectogram4x4BlurOff`` (same package) so the ONLY difference is the
``(u, v)`` footprint — the v extent is twice the u extent — and the
``describe()`` metadata.

References
----------
* ADR-0008 §2/§3 — visual-regression harness.
* ADR-0013 §6 — flattened-surface Representation (carries the MatRatio
  scaling state per the maintainer decision).
* ADR-0025 §Context — the resectogram is the flattened 2D image of the
  Bezier ``(u, v)`` parameter domain.
* ADR-0027 — pairs with ``vtkLiverResectogramAspectRatioTest`` (the
  pure-math pin) as the pixel-level pin of the same invariant.
"""

from __future__ import annotations

import slicer  # type: ignore[import-not-found]

from . import Resectogram4x4BlurOff as _blur_off


VIEWPORT_WIDTH = 600
VIEWPORT_HEIGHT = 600
BACKGROUND_RGB = (0.0, 0.0, 0.0)
ANTI_ALIASING_FRAMES = 0

BLUR_ENABLED = False

# Anisotropic aspect-ratio scaling ON so the non-square domain squeeze is
# applied (the whole point of this scenario).
ENABLE_FLEXIBLE_BOUNDARY = True

# Non-square (u, v) domain — the v extent is twice the u extent, so the
# aspect-ratio helper yields {0.5, 1} (u squeezed to half).  This is the
# pixel-level counterpart of vtkLiverResectogramAspectRatioTest Case 2.
PATCH_HALF_EXTENT_U = 22.5
PATCH_HALF_EXTENT_V = 45.0


def setup_scene():
    """Populate the scene with the non-square-domain resectogram fixture.

    Builds the same parenchyma + distance map + resectogram-enabled markups
    Bezier node as ``Resectogram4x4BlurOff``, but lays the 4x4 control grid
    out so the v parametric extent is twice the u extent
    (``PATCH_HALF_EXTENT_V == 2 * PATCH_HALF_EXTENT_U``) with
    ``EnableFlexibleBoundary`` ON.  The rendered panel shows the v1
    anisotropic squeeze; re-baseline to v2.0 once the ResectogramPipeline
    lands.

    Returns
    -------
    tuple
        ``(bezier_node, parenchyma_model, distance_map_volume)`` — every
        node created, returned (NOT cached in module globals) so the caller
        owns teardown.
    """
    slicer.mrmlScene.Clear(0)
    slicer.modules.liverresections.logic()

    parenchyma = _blur_off._make_synthetic_parenchyma()
    distance_map = _blur_off._make_parenchyma_distance_map(
        sphere_center=_blur_off.SPHERE_CENTER,
        sphere_radius=_blur_off.SPHERE_RADIUS,
    )
    bezier = _blur_off._build_resectogram_bezier(
        half_extent_u=PATCH_HALF_EXTENT_U,
        half_extent_v=PATCH_HALF_EXTENT_V,
        enable_flexible_boundary=ENABLE_FLEXIBLE_BOUNDARY,
        distance_map=distance_map,
    )

    return bezier, parenchyma, distance_map


def setup_camera(view_node=None):
    """Fix the resectogram panel's deterministic (parallel) view.

    Identical pose to ``Resectogram4x4BlurOff`` so the only visual variable
    versus that scenario is the domain aspect ratio.
    """
    _blur_off.setup_camera(view_node)


def setup_viewport(view_node=None):
    """Set resectogram panel pixel size, background, anti-aliasing."""
    _blur_off.setup_viewport(view_node)


def describe() -> dict:
    """Metadata persisted alongside the captured bundle."""
    return {
        "scenario": "Resectogram4x4NonSquareScaling",
        "blur_enabled": BLUR_ENABLED,
        "enable_flexible_boundary": ENABLE_FLEXIBLE_BOUNDARY,
        "patch_half_extent": [PATCH_HALF_EXTENT_U, PATCH_HALF_EXTENT_V],
        "viewport": {
            "size": [VIEWPORT_WIDTH, VIEWPORT_HEIGHT],
            "background": list(BACKGROUND_RGB),
            "anti_aliasing_frames": ANTI_ALIASING_FRAMES,
        },
        "camera": {
            "position": list(_blur_off.CAMERA_POSITION),
            "focal_point": list(_blur_off.CAMERA_FOCAL_POINT),
            "view_up": list(_blur_off.CAMERA_VIEW_UP),
            "parallel_scale": _blur_off.CAMERA_PARALLEL_SCALE,
            "view_angle": _blur_off.CAMERA_VIEW_ANGLE,
            "clipping_range": list(_blur_off.CAMERA_CLIPPING_RANGE),
        },
    }

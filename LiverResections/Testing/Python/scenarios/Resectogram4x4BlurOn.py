# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Visual-regression scenario: 4x4 resectogram, BLUR ON, square scaling.

T3 ResectogramPipeline baseline target (ADR-0027 invariant-test-first).

It builds the SAME deterministic square-domain scene as
``Resectogram4x4BlurOff`` (reusing that module's scene builders, same
package) so the pixel delta between the two baselines isolates the blur
post-pass.  ``BLUR_ENABLED`` is the only configuration that differs — the
blur kernel extent (``BlurRadius``) is left at the display node's default,
matching ``Resectogram4x4BlurOff``, so blur on/off is the single visual
variable.

No v1 blur appearance to reproduce
----------------------------------
The Gaussian-blur post-pass is NET-NEW for v2.0 — there is no blur field
on the legacy ``vtkMRMLMarkupsBezierSurfaceDisplayNode`` and no
``vtkGaussianBlurPass`` anywhere in the v1 tree.  So unlike the blur-OFF /
non-square baselines (captured against the v1 monolith first), this
scenario's baseline is captured against the v2.0 path: the blur toggle
lives on ``vtkMRMLResectogramDisplayNode`` (``BlurEnabled``) and the
flattened-surface Representation attaches a ``vtkGaussianBlurPass`` to a
private overlay renderer when engaged (ADR-0013 §6).  ``setup_scene``
engages blur on the resectogram display node so the rendered strip differs
visibly (softer band) from ``Resectogram4x4BlurOff``.

References
----------
* ADR-0008 §2/§3 — visual-regression harness.
* ADR-0013 §6 — the blur is a per-frame state on the flattened-surface
  Representation owned by the ResectogramPipeline.
* ADR-0027 — invariant-test-first.
"""

from __future__ import annotations

import slicer  # type: ignore[import-not-found]

from . import Resectogram4x4BlurOff as _blur_off


VIEWPORT_WIDTH = 600
VIEWPORT_HEIGHT = 600
BACKGROUND_RGB = (0.0, 0.0, 0.0)
ANTI_ALIASING_FRAMES = 0

# The one variable that distinguishes this scenario from
# Resectogram4x4BlurOff: the net-new v2.0 Gaussian-blur post-pass is
# engaged on the resectogram display node (ADR-0013 §6).  BlurRadius is
# left at the display node's default (matching Resectogram4x4BlurOff) so
# blur on/off is the single visual variable.
BLUR_ENABLED = True

# Same square (u, v) domain + aspect-ratio configuration as
# Resectogram4x4BlurOff so the only intended visual variable is the blur.
ENABLE_FLEXIBLE_BOUNDARY = True
PATCH_HALF_EXTENT_U = 45.0
PATCH_HALF_EXTENT_V = 45.0


def _engage_blur(display_node) -> None:
    """Engage the Gaussian-blur post-pass on the resectogram display node.

    Sets ``BlurEnabled`` on the v2.0 ``vtkMRMLResectogramDisplayNode``
    (ADR-0013 §6); the flattened-surface Representation moves the
    resectogram actor onto a private overlay renderer carrying a
    ``vtkGaussianBlurPass`` in response, softening the strip relative to
    ``Resectogram4x4BlurOff``.  ``BlurRadius`` is left at the display node's
    default so blur on/off is the only visual variable.
    """
    display_node.SetBlurEnabled(True)


def setup_scene():
    """Populate the scene with the blur-on square-domain resectogram fixture.

    Builds the same square-domain resectogram scene as
    ``Resectogram4x4BlurOff`` (reusing its builders) and engages the
    Gaussian-blur post-pass via :func:`_engage_blur` (ADR-0013 §6) so the
    rendered strip differs visibly (softer band) from the blur-OFF baseline.

    Returns
    -------
    tuple
        ``(bezier_node, parenchyma_model, distance_map_volume,
        resectogram_display)`` — every node created, returned (NOT cached in
        module globals) so the caller owns teardown.  The fourth handle is
        the v2.0 ``vtkMRMLResectogramDisplayNode`` the ResectogramPipeline
        keys on.
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
    resectogram_display = _blur_off._attach_resectogram_display_node(
        bezier, enable_flexible_boundary=ENABLE_FLEXIBLE_BOUNDARY
    )

    _engage_blur(resectogram_display)

    return bezier, parenchyma, distance_map, resectogram_display


def setup_camera(view_node=None):
    """Fix the resectogram panel's deterministic (parallel) view."""
    _blur_off.setup_camera(view_node)


def setup_viewport(view_node=None):
    """Set resectogram panel pixel size, background, anti-aliasing."""
    _blur_off.setup_viewport(view_node)


def describe() -> dict:
    """Metadata persisted alongside the captured bundle.

    ``blur`` / ``blur_enabled`` record the scenario's blur-ON configuration;
    ``describe()`` stays a pure, side-effect-free metadata function (the
    replay driver calls it before any scene exists).
    """
    return {
        "scenario": "Resectogram4x4BlurOn",
        "blur": BLUR_ENABLED,
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

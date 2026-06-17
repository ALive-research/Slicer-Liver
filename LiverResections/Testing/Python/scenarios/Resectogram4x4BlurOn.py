# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Visual-regression scenario: 4x4 resectogram, BLUR ON, square scaling.

T3 ResectogramPipeline baseline target (ADR-0027 invariant-test-first).

SPLITTABLE / LAST.  Per the maintainer decision the Gaussian-blur
post-pass stays a v2.0 feature behind a toggle, and this baseline is
explicitly splittable from the rest of T3: if the launched harness
(issue #460) blocks baseline capture, the blur work — and this scenario —
land last, after the blur-OFF resectogram baselines are green.  It exists
now as a placed target so the test surface is complete and the implementer
knows GREEN here is the final T3 step, not a gate on the core resectogram
landing.

It builds the SAME deterministic square-domain scene as
``Resectogram4x4BlurOff`` (reusing that module's scene builders, same
package) so the pixel delta between the two baselines isolates the blur
post-pass.  ``BLUR_ENABLED`` is the only configuration that differs.

No v1 blur appearance to reproduce
----------------------------------
The Gaussian-blur post-pass is NET-NEW for v2.0 — there is no blur field
on the legacy ``vtkMRMLMarkupsBezierSurfaceDisplayNode`` and no
``vtkGaussianBlurPass`` anywhere in the v1 tree (see the T3 plan).  So
unlike the blur-OFF / non-square baselines (captured against the v1
monolith first), this scenario's FIRST baseline is captured against the
v2.0 path once the blur toggle exists on ``vtkMRMLResectogramDisplayNode``
+ the flattened-surface Representation (ADR-0013 §6).  ``setup_scene``
therefore builds the scene but DOES NOT engage blur (no field to set yet);
the implementer wires the blur toggle and re-captures at the go-live step.
``describe()`` records ``blur_enabled = True`` + ``blur_engaged = False``
so the bundle metadata is unambiguous about that pending wiring.

References
----------
* ADR-0008 §2/§3 — visual-regression harness.
* ADR-0013 §6 — the blur is a per-frame state on the flattened-surface
  Representation owned by the ResectogramPipeline.
* ADR-0027 — invariant-test-first; this target is splittable/last.
"""

from __future__ import annotations

import slicer  # type: ignore[import-not-found]

from . import Resectogram4x4BlurOff as _blur_off


VIEWPORT_WIDTH = 600
VIEWPORT_HEIGHT = 600
BACKGROUND_RGB = (0.0, 0.0, 0.0)
ANTI_ALIASING_FRAMES = 0

# The one variable that distinguishes this scenario from
# Resectogram4x4BlurOff.  No field exists on the current display node to
# engage blur (net-new for v2.0); the implementer wires the toggle and
# sets blur_engaged True at the go-live step.
BLUR_ENABLED = True

# Same square (u, v) domain + aspect-ratio configuration as
# Resectogram4x4BlurOff so the only intended visual variable is the blur.
ENABLE_FLEXIBLE_BOUNDARY = True
PATCH_HALF_EXTENT_U = 45.0
PATCH_HALF_EXTENT_V = 45.0


def _engage_blur(display_node) -> bool:
    """Engage the Gaussian-blur post-pass on the resectogram display node.

    Returns True iff a blur toggle was found and set.  The toggle is
    NET-NEW for v2.0 (ADR-0013 §6); until the implementer adds it the
    accessor is absent and this returns False (the scene renders blur-OFF
    and the blur-ON baseline is deferred to the v2.0 go-live capture).
    Probed by name rather than hard-referenced so this scenario imports +
    builds its scene cleanly before the field exists.
    """
    setter = getattr(display_node, "SetEnableResectogramBlur", None)
    if setter is None:
        return False
    setter(True)
    return True


def setup_scene():
    """Populate the scene with the blur-on square-domain resectogram fixture.

    Builds the same square-domain resectogram scene as
    ``Resectogram4x4BlurOff`` (reusing its builders) and attempts to engage
    the blur post-pass via :func:`_engage_blur`.  Until the implementer
    adds the blur toggle (ADR-0013 §6) the engage is a no-op and the scene
    renders blur-OFF; the blur-ON baseline is captured LAST against v2.0.

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

    _engage_blur(bezier.GetDisplayNode())

    return bezier, parenchyma, distance_map


def setup_camera(view_node=None):
    """Fix the resectogram panel's deterministic (parallel) view."""
    _blur_off.setup_camera(view_node)


def setup_viewport(view_node=None):
    """Set resectogram panel pixel size, background, anti-aliasing."""
    _blur_off.setup_viewport(view_node)


def describe() -> dict:
    """Metadata persisted alongside the captured bundle.

    ``blur_enabled`` records the scenario's INTENT (this is the blur-ON
    target).  Whether the net-new blur toggle is actually wired is
    discovered at scene-build time by :func:`_engage_blur`; ``describe()``
    stays a pure, side-effect-free metadata function (the replay driver
    calls it before any scene exists), so it does not probe the live node
    here.
    """
    return {
        "scenario": "Resectogram4x4BlurOn",
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

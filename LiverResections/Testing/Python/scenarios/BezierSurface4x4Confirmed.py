# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Visual-regression scenario: 4x4 Bezier surface in Confirmed state.

Identical fixture to ``BezierSurface4x4Planning`` except parenchyma
trim is ON (``ClipOut`` uniform 1) — only the resected side of the
Bezier surface remains visible after the fragment shader's discard
runs.

The Confirmed-state machine described in ADR-0019 has not landed in
``preview`` HEAD at the time of writing (issue #18 is open).  This
scenario therefore drives the underlying knob directly: the
``ClipOut`` setter on ``vtkMRMLLiverResectionNode`` propagates to the
``uResectionClipOut`` shader uniform in
``vtkOpenGLBezierResectionPolyDataMapper``.  When ADR-0019 lands the
scenario should migrate from the raw setter to
``resection.SetState(resection.Confirmed)`` — see the in-line TODO
inside :func:`setup_scene` for the migration anchor.

References
----------
* ADR-0019 §"Decision" — resection state machine.
* ADR-0020 §"Rollout plan" §7 — Confirmed-state characterisation
  baseline as a regression gate for the v2.1 mapper rewrite.
"""

from __future__ import annotations

# Reuse Planning camera/viewport plus the scene-construction helpers.
# The "two scenarios that differ in one shader uniform" shape is the
# natural decomposition; duplicating the camera + viewport would
# silently drift between the two over time.
from . import BezierSurface4x4Planning as _planning


VIEWPORT_WIDTH = _planning.VIEWPORT_WIDTH
VIEWPORT_HEIGHT = _planning.VIEWPORT_HEIGHT
BACKGROUND_RGB = _planning.BACKGROUND_RGB
ANTI_ALIASING_FRAMES = _planning.ANTI_ALIASING_FRAMES

CAMERA_POSITION = _planning.CAMERA_POSITION
CAMERA_FOCAL_POINT = _planning.CAMERA_FOCAL_POINT
CAMERA_VIEW_UP = _planning.CAMERA_VIEW_UP
CAMERA_PARALLEL_SCALE = _planning.CAMERA_PARALLEL_SCALE
CAMERA_VIEW_ANGLE = _planning.CAMERA_VIEW_ANGLE
CAMERA_CLIPPING_RANGE = _planning.CAMERA_CLIPPING_RANGE


def setup_scene():
    """Build the Planning fixture, then flip ``ClipOut`` to 1.

    Returns
    -------
    vtkMRMLLiverResectionNode
        The same resection node ``BezierSurface4x4Planning`` builds,
        with the Confirmed-state shader uniform engaged.
    """
    resection = _planning.setup_scene()

    # TODO(ADR-0019): when the resection state machine lands (issue #18)
    # replace the next two lines with
    #     resection.SetState(resection.Confirmed)
    # and remove the direct ClipOut/display-node mutation below.  Until
    # then the state enum lacks a Confirmed value, so we drive the
    # underlying uniform directly on both the resection node (for
    # persistence) and the Bezier surface display node (for the live
    # mapper).
    resection.SetClipOut(True)

    bezier = resection.GetBezierSurfaceNode()
    if bezier is not None:
        display = bezier.GetDisplayNode()
        if display is not None:
            # vtkMRMLBezierSurfaceDisplayNode mirrors the resection
            # node's ClipOut — set both so the mapper picks up the
            # value regardless of which observer fires first.
            if hasattr(display, "SetClipOut"):
                display.SetClipOut(True)

    return resection


def setup_camera(view_node=None):
    """Forward to the Planning scenario's camera pose."""
    _planning.setup_camera(view_node)


def setup_viewport(view_node=None):
    """Forward to the Planning scenario's viewport configuration."""
    _planning.setup_viewport(view_node)


def describe() -> dict:
    meta = _planning.describe()
    meta["scenario"] = "BezierSurface4x4Confirmed"
    meta["clip_out"] = True
    return meta

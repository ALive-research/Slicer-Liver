# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Visual-regression scenario: 4x4 Bezier surface in Confirmed state.

Identical fixture to ``BezierSurface4x4Planning`` except parenchyma
trim is ON (``ClipOut`` uniform 1) — only the resected side of the
Bezier surface remains visible after the fragment shader's discard
runs.

In the ``qMRMLThreeDWidget`` replay harness the visible pixels come
from the v2 LayerDM render path (``vtkMRMLBezierSurfaceNode`` +
``vtkMRMLParametricSurfaceDisplayNode`` + the orchestrating
``vtkMRMLResectionPlanNode`` → ``LiverBezierSurfacePipeline`` →
``BezierPlanningRepresentation`` → ``vtkOpenGLBezierResectionPolyDataMapper``).
The only pixel-flipping difference between Planning and Confirmed is the
``ClipOut`` uniform — driven by the ``ClipOut`` flag on the parametric-
surface display node.  This scenario therefore reuses the Planning
fixture and flips ``ClipOut`` on that display node, staying on the
Planning representation (the one that threads the distance map),
mirroring v1's single-representation + uniform model.  Driving the
Confirmed-state representation off the distance map is a separate
follow-on (the ConfirmedRepresentation does not yet thread it).

References
----------
* ADR-0019 §"Per-state contract" — Confirmed-state visual contract
  (control polygon hidden, widget disabled, parenchyma-trim shader
  on).
* ADR-0020 §"Rollout plan" §7 — Confirmed-state characterisation
  baseline as a regression gate for the v2.1 mapper rewrite.
"""

from __future__ import annotations

import slicer  # type: ignore[import-not-found]

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


def setup_scene() -> slicer.vtkMRMLBezierSurfaceNode:
    """Build the Planning fixture, then engage Confirmed-state trim.

    In this render path the Confirmed state differs from Planning by a
    single shader uniform — parenchyma trim — driven by ``ClipOut`` on
    the parametric-surface display node.

    Returns
    -------
    vtkMRMLBezierSurfaceNode
        The same data carrier ``BezierSurface4x4Planning`` builds, with
        the Confirmed-state ``ClipOut`` uniform engaged on its display
        node.
    """
    carrier = _planning.setup_scene()
    carrier.GetDisplayNode().SetClipOut(True)
    return carrier


def setup_camera(view_node: slicer.vtkMRMLViewNode | None = None) -> None:
    """Forward to the Planning scenario's camera pose."""
    _planning.setup_camera(view_node)


def setup_viewport(view_node: slicer.vtkMRMLViewNode | None = None) -> None:
    """Forward to the Planning scenario's viewport configuration."""
    _planning.setup_viewport(view_node)


def describe() -> dict:
    meta = _planning.describe()
    meta["scenario"] = "BezierSurface4x4Confirmed"
    meta["clip_out"] = True
    return meta

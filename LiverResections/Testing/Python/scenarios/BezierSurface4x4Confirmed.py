# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Visual-regression scenario: 4x4 Bezier surface in Confirmed state.

Identical fixture to ``BezierSurface4x4Planning`` except parenchyma
trim is ON (``ClipOut`` uniform 1) — only the resected side of the
Bezier surface remains visible after the fragment shader's discard
runs.

The Confirmed-state machine on the v2 Bezier surface node
(ADR-0019) has not landed in ``preview`` HEAD at the time of
writing.  This scenario therefore drives the underlying knob
directly: the ``ClipOut`` setter on ``vtkMRMLLiverResectionNode``
propagates to the ``uResectionClipOut`` shader uniform in
``vtkOpenGLBezierResectionPolyDataMapper``.  When the v2 state
machine lands the scenario should migrate from the raw setter to
``bezier_v2.SetState(vtkMRMLBezierSurfaceNode.Confirmed)`` — see the
in-line TODO inside :func:`setup_scene` for the migration anchor.

The v1 enum on ``vtkMRMLLiverResectionNode`` is
``{Initialization, Deformation, Completed}`` — it does NOT carry a
``Confirmed`` value; that name belongs to the v2 enum on
``vtkMRMLBezierSurfaceNode`` introduced by ADR-0019.

References
----------
* ADR-0019 — resection state machine (Init/Planning/Confirmed) on
  ``vtkMRMLBezierSurfaceNode``.
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

    # TODO: when the v2 Bezier state machine (ADR-0019) lands, replace
    # the manual ClipOut wiring below with the state-machine call on
    # ``vtkMRMLBezierSurfaceNode``:
    #     bezier_v2.SetState(vtkMRMLBezierSurfaceNode.Confirmed)
    # The v1 enum on ``vtkMRMLLiverResectionNode`` is
    # {Initialization, Deformation, Completed} — it does NOT carry a
    # ``Confirmed`` value; that name belongs to the v2 enum on
    # ``vtkMRMLBezierSurfaceNode`` (ADR-0019).  Until v2 lands we
    # drive the underlying uniform directly: on the resection node
    # (for persistence) and on the live display node of the Bezier
    # surface the LiverResections logic returns (for the running
    # mapper, since the state-machine auto-propagation only fires on
    # ``Initialization → Deformation`` and this scenario stays in
    # ``Initialization``).
    resection.SetClipOut(True)

    # ``vtkSlicerLiverResectionsLogic::AddBezierSurface`` returns a
    # ``vtkMRMLMarkupsBezierSurfaceNode`` (LiverMarkups path) — NOT a
    # ``vtkMRMLBezierSurfaceNode`` (LiverResections path / ADR-0014
    # v2).  Its display node is correspondingly
    # ``vtkMRMLMarkupsBezierSurfaceDisplayNode``, which is a distinct
    # MRML class from ``vtkMRMLBezierSurfaceDisplayNode``.  Both
    # classes happen to expose ``SetClipOut`` so this works
    # polymorphically; we read the display node from whatever the
    # logic returned rather than assume a specific class, so the
    # scenario keeps working when ``AddBezierSurface`` gets retargeted
    # to the v2 path.
    bezier = resection.GetBezierSurfaceNode()
    if bezier is not None:
        display = bezier.GetDisplayNode()
        if display is not None and hasattr(display, "SetClipOut"):
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

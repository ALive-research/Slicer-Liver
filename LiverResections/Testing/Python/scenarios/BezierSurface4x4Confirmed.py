# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Visual-regression scenario: 4x4 Bezier surface in Confirmed state.

Identical fixture to ``BezierSurface4x4Planning`` except parenchyma
trim is ON (``ClipOut`` uniform 1) — only the resected side of the
Bezier surface remains visible after the fragment shader's discard
runs.

Per ADR-0019 (the v2 resection state machine on
``vtkMRMLBezierSurfaceNode``), the Confirmed state is committed via
``vtkMRMLBezierSurfaceNode::SetState(Confirmed)`` — a legal
``Planning -> Confirmed`` transition.  The state-machine API is the
single source of truth for the Confirmed contract; this scenario
exercises it on a v2 data node added to the scene alongside the
Planning fixture.

Non-Pipeline render path — fallback to legacy display-node
``ClipOut``
==============================================================
The state-machine -> trim-shader auto-propagation lives in
``ConfirmedRepresentation`` (LayerDM Pipeline; ADR-0013 §6 +
ADR-0019 §"Per-state contract").  The Pipeline is reachable only via
the LayerDM dispatch; the visual-regression harness renders through a
plain ``qMRMLThreeDWidget`` (see ``replay_test.py``), whose
displayable-manager chain still binds the legacy
``vtkMRMLMarkupsBezierSurfaceNode`` display node.  In that
non-Pipeline context the state change on the v2 data node does NOT
flip the legacy mapper's ``uResectionClipOut`` uniform — so the
explicit ``display.SetClipOut(True)`` push on the markups display node
stays, gated by a ``hasattr`` check to remain robust if
``AddBezierSurface`` is later retargeted to the v2 path.

The v1 enum on ``vtkMRMLLiverResectionNode`` is
``{Initialization, Deformation, Completed}`` — it does NOT carry a
``Confirmed`` value; that name belongs to the v2 enum on
``vtkMRMLBezierSurfaceNode`` (ADR-0019).

References
----------
* ADR-0019 §"Per-state contract" — Confirmed-state visual contract
  (control polygon hidden, widget disabled, parenchyma-trim shader
  on).
* ADR-0019 transition matrix — ``Init -> Planning -> Confirmed`` is
  the legal path; ``Init -> Confirmed`` is rejected.
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


def setup_scene() -> slicer.vtkMRMLNode:
    """Build the Planning fixture, drive the v2 state machine to Confirmed.

    Returns
    -------
    vtkMRMLLiverResectionNode
        The same resection node ``BezierSurface4x4Planning`` builds,
        with the Confirmed-state shader uniform engaged.
    """
    resection = _planning.setup_scene()

    # ADR-0019 §"Per-state contract": the Confirmed state lives on the
    # v2 ``vtkMRMLBezierSurfaceNode`` (data-only LayerDM node), not on
    # the legacy ``vtkMRMLLiverResectionNode``.  Add a v2 data node to
    # the scene and walk it ``Init -> Planning -> Confirmed`` — the
    # transition matrix rejects ``Init -> Confirmed`` directly
    # (forbidden per ADR-0019), so the Planning step is mandatory.
    bezier_v2 = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLBezierSurfaceNode", "VisualTestBezierSurfaceV2"
    )
    bezier_v2.SetState(slicer.vtkMRMLBezierSurfaceNode.Planning)
    bezier_v2.SetState(slicer.vtkMRMLBezierSurfaceNode.Confirmed)

    # Mirror the state on the legacy resection node so the v1 stack's
    # XML round-trip + GUI bindings agree with the v2 state machine.
    # The v1 ``Completed`` enum value is the historical analog of
    # ``Confirmed``; T2.7 (LiverMarkups dissolution) retires the
    # legacy node and the parallel state altogether.
    resection.SetState(resection.Completed)

    # Non-Pipeline fallback (see the module docstring): the legacy
    # ``vtkMRMLMarkupsBezierSurfaceNode`` display node still drives the
    # visible pixels in this harness (plain ``qMRMLThreeDWidget`` render
    # path; the LayerDM ``ConfirmedRepresentation`` is not engaged
    # without the Pipeline).  Push ``ClipOut`` on both the persistence
    # carrier (resection node) and the live display node so the legacy
    # mapper's ``uResectionClipOut`` uniform flips to 1.
    resection.SetClipOut(True)

    return resection


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

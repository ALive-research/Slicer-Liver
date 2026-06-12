# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Visual-regression scenario: the DistanceSpheroid init contour shader.

Renders the banded triaxial-ellipsoid contour produced by the
**production** ``DistanceSpheroidInitRepresentation`` path (per ADR-0014
§2 and ADR-0015 §"Stack 4").  The scenario builds the minimal real MRML
inputs the Representation reads, instantiates the Representation against
a live renderer, and lets the Representation drive
``vtkOpenGLDistanceContourPolyDataMapper`` via ``SetSpheroid`` — the same
call chain the production ``LiverBezierSurfacePipeline`` exercises when it
invokes ``representation.update(display_node, data_node)``.

What drives the Representation
------------------------------
The Representation reads its geometry off a *data node* — a
``vtkMRMLBezierSurfaceNode`` (which inherits the DistanceSpheroid
accessors from ``vtkMRMLAbstractParametricSurfaceNode``):

* ``GetDistanceSpheroidCenter()``       — (cx, cy, cz)
* ``GetDistanceSpheroidRadiusX/Y/Z()``  — the three distinct radii
* ``GetNumberOfDistanceSpheroidInitPoints()`` /
  ``GetDistanceSpheroidInitPoint(i)``   — the surgeon-placed seeds

and decoration off a display node (``GetResectionColor`` /
``GetResectionOpacity``).  The scenario sets a deterministic *triaxial*
spheroid (three distinct radii, off-origin centre) so the rendered
surface is unmistakably an ellipsoid, not an accidental sphere.  The
scenario does **not** call ``SetSpheroid`` on the mapper directly — that
is the whole point of driving the production Representation path:
``DistanceSpheroidInitRepresentation._apply_data_node`` derives the
quadric and pushes it onto the mapper, exactly as production does.

Render-config note (contour visibility)
----------------------------------------
The contour mapper's fragment shader *discards* every fragment unless
its ``uContourVisibility`` uniform is set (default ``false``); the
Representation drives ``SetSpheroid`` but, in the current T2.2 iteration,
does not toggle ``ContourVisibility``.  Contour visibility is a
render-time display concern (like the camera pose and anti-aliasing
state this module also fixes), so ``setup_viewport`` enables it on the
mapper the Representation owns — without touching production logic — so a
human (or the offscreen replay) actually sees the banded iso-surface.
This is documented here because it is the difference between "the band is
visible" and "the surface is wholly discarded".

This module exposes the same trio consumed by ``capture_baseline.py``
and ``replay_test.py``: :func:`setup_scene`, :func:`setup_camera`,
:func:`setup_viewport`, plus :func:`describe`.  ``setup_scene`` returns
the Representation handle so the dual-mode interactive test can attach it
to a live view's renderer.

References
----------
* ADR-0008 §2 — the layered test taxonomy (this is a workflow/visual
  scenario driving the production Representation).
* ADR-0014 §2 — the DistanceSpheroidInit Representation + triaxial-
  ellipsoid contour.
* ADR-0015 §"Stack 4" — the GPU path derives its quadric uniform from
  ``vtkLiverSpheroidRingExtractor::ComputeQuadricCoefficients`` (the
  SSOT), so render == extract.
* ADR-0020 §"Rollout plan" §7 — capture-then-replay visual-regression
  workflow.
"""

from __future__ import annotations

import slicer  # type: ignore[import-not-found]


# --------------------------------------------------------------------------- #
# Render geometry — fixed numerically, never "fit to bounds", so the
# offscreen replay and the interactive capture produce the same pixels
# (see BezierSurface4x4Planning for the same rationale).
# --------------------------------------------------------------------------- #

VIEWPORT_WIDTH = 800
VIEWPORT_HEIGHT = 600
BACKGROUND_RGB = (0.0, 0.0, 0.0)
ANTI_ALIASING_FRAMES = 0  # deterministic; AA introduces sub-pixel jitter

# Deterministic triaxial spheroid.  Off-origin centre + three DISTINCT
# radii so the rendered surface is unambiguously an ellipsoid (a sphere
# could not reproduce this), and so the SSOT quadric the mapper binds is
# the general triaxial case rather than the placeholder unit sphere.
SPHEROID_CENTER = (12.0, -8.0, 4.0)
SPHEROID_RADIUS_X = 30.0
SPHEROID_RADIUS_Y = 45.0
SPHEROID_RADIUS_Z = 20.0

# Two surgeon-placed seed markers (the data node's contract is "two or
# more").  Placed on the long (Y) axis so they read as the implied-
# spheroid endpoints in the rendered view.
SPHEROID_INIT_POINTS = (
    (12.0, -53.0, 4.0),
    (12.0, 37.0, 4.0),
)

# The contour-band half-thickness in model-coordinate quadric-value
# units.  The shader keeps fragments with abs(F(p)) < uContourThickness.
# The Representation renders the ellipsoid SURFACE through the mapper, so
# F(p) ~ 0 across the whole surface; a generous thickness keeps the band
# robust against single-precision quadric round-off so the iso-surface is
# reliably lit rather than flickering on numerical noise.
CONTOUR_THICKNESS = 0.25

# Camera pose: oblique 3D view of the ~90 mm (Y) x 60 mm (X) x 40 mm (Z)
# ellipsoid centred at SPHEROID_CENTER.  Distance / view-angle sized to
# frame the long axis with margin.  Numeric, not reset-to-fit.
CAMERA_POSITION = (140.0, -120.0, 110.0)
CAMERA_FOCAL_POINT = SPHEROID_CENTER
CAMERA_VIEW_UP = (0.0, 0.0, 1.0)
CAMERA_PARALLEL_SCALE = 70.0
CAMERA_VIEW_ANGLE = 45.0
CAMERA_CLIPPING_RANGE = (10.0, 600.0)


# --------------------------------------------------------------------------- #
# Module-level handles so setup_viewport can reach the Representation /
# mapper that setup_scene constructed.  The capture / replay drivers call
# setup_scene() before setup_viewport(), matching this ordering.
# --------------------------------------------------------------------------- #

_representation = None  # DistanceSpheroidInitRepresentation
_data_node = None  # vtkMRMLBezierSurfaceNode
_display_node = None


def _import_representation():
    """Import the production Representation under both package layouts.

    Mirrors the dual-path import in ``LiverBezierSurfacePipeline`` — the
    module is importable as ``LiverResectionsLib.Representations...`` when
    the loadable module is on the path, and as a bare
    ``Representations...`` package in some launched layouts.
    """
    try:
        from LiverResectionsLib.Representations.DistanceSpheroidInitRepresentation import (  # type: ignore[import-not-found]
            DistanceSpheroidInitRepresentation,
        )
    except ImportError:
        from Representations.DistanceSpheroidInitRepresentation import (  # type: ignore[import-not-found,no-redef]
            DistanceSpheroidInitRepresentation,
        )
    return DistanceSpheroidInitRepresentation


def _make_data_node() -> slicer.vtkMRMLNode:
    """Build the real MRML data node the Representation reads.

    ``vtkMRMLBezierSurfaceNode`` carries the DistanceSpheroid accessors
    (inherited from ``vtkMRMLAbstractParametricSurfaceNode``) the
    Representation consumes.  This is the production node type — the
    scenario drives it, the Representation reads it, exactly as the GUI
    flow does.
    """
    node = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLBezierSurfaceNode", "VisualTestDistanceSpheroid"
    )

    node.SetDistanceSpheroidCenter(*SPHEROID_CENTER)
    node.SetDistanceSpheroidRadiusX(SPHEROID_RADIUS_X)
    node.SetDistanceSpheroidRadiusY(SPHEROID_RADIUS_Y)
    node.SetDistanceSpheroidRadiusZ(SPHEROID_RADIUS_Z)

    node.SetNumberOfDistanceSpheroidInitPoints(len(SPHEROID_INIT_POINTS))
    for index, point in enumerate(SPHEROID_INIT_POINTS):
        node.SetDistanceSpheroidInitPoint(index, list(point))

    return node


def _make_display_node() -> slicer.vtkMRMLNode:
    """Build a display node carrying the decoration the Representation reads.

    The Representation reads ``GetResectionColor`` / ``GetResectionOpacity``
    if present; ``vtkMRMLBezierSurfaceDisplayNode`` exposes that surface.
    A plain model display node is the fallback when the resection display
    node class is unavailable — the Representation tolerates a partial
    display node (missing accessors fall back to defaults).
    """
    for class_name in (
        "vtkMRMLBezierSurfaceDisplayNode",
        "vtkMRMLModelDisplayNode",
    ):
        node = slicer.mrmlScene.CreateNodeByClass(class_name)
        if node is not None:
            node.UnRegister(None)
            node.SetName("VisualTestDistanceSpheroidDisplay")
            slicer.mrmlScene.AddNode(node)
            return node
    return None


def setup_scene():
    """Populate the scene and build the production Representation.

    Idempotent under repeated invocation (clears the scene first), so
    capture-side retries start clean.

    Returns
    -------
    DistanceSpheroidInitRepresentation
        The Representation handle, so the interactive / replay driver can
        attach it to a live view's renderer (``SetRenderer``) and trigger
        a render.  Constructed with ``renderer=None`` here because the
        standalone ``qMRMLThreeDWidget`` the drivers build owns the real
        renderer; the driver wires it via ``SetRenderer`` after the GL
        context is up.
    """
    global _representation, _data_node, _display_node

    slicer.mrmlScene.Clear(0)

    _data_node = _make_data_node()
    _display_node = _make_display_node()

    representation_class = _import_representation()
    # renderer=None: the drivers attach the live renderer via
    # attach_to_renderer() once the GL context exists (the contour mapper
    # touches GL state on attach; see capture_baseline.py's first-render-
    # before-bind note).
    _representation = representation_class(renderer=None)

    # Drive the production path: the Representation reads the data node and
    # pushes the SSOT quadric onto the contour mapper via SetSpheroid.
    _representation.update(_display_node, _data_node)

    return _representation


def attach_to_renderer(renderer) -> None:
    """Attach the Representation's actors to a live ``vtkRenderer``.

    Called by the interactive / replay driver once the standalone view's
    GL context is initialised.  Re-runs ``update`` so the contour mapper's
    SSOT quadric is bound after the actors are in the renderer.
    """
    if _representation is None:
        return
    _representation.SetRenderer(renderer)
    _representation.update(_display_node, _data_node)


def setup_camera(view_node=None) -> None:
    """Set the 3D view camera to the scenario's deterministic pose.

    Same numeric-pose discipline as ``BezierSurface4x4Planning`` — camera
    drift is the most common visual-regression false positive, so the pose
    is fixed rather than read from "reset to fit".
    """
    if view_node is None:
        view_node = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLViewNode")
        if view_node is None:
            view_node = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLViewNode", "VisualTestView"
            )

    camera_logic = slicer.modules.cameras.logic()
    camera_node = camera_logic.GetViewActiveCameraNode(view_node)
    if camera_node is None:
        camera_node = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLCameraNode", "VisualTestCamera"
        )
        camera_node.SetActiveTag(view_node.GetID())

    camera_node.SetPosition(*CAMERA_POSITION)
    camera_node.SetFocalPoint(*CAMERA_FOCAL_POINT)
    camera_node.SetViewUp(*CAMERA_VIEW_UP)

    vtk_camera = camera_node.GetCamera()
    vtk_camera.SetParallelScale(CAMERA_PARALLEL_SCALE)
    vtk_camera.SetViewAngle(CAMERA_VIEW_ANGLE)
    vtk_camera.SetClippingRange(*CAMERA_CLIPPING_RANGE)

    camera_node.Modified()


def setup_viewport(view_node=None) -> None:
    """Set viewport size / background / anti-aliasing, and enable the band.

    Anti-aliasing is forced OFF (sub-pixel jitter is hardware-dependent).
    Additionally enables ``ContourVisibility`` + a deterministic
    ``ContourThickness`` on the contour mapper the Representation owns —
    a render-config concern, not production logic (see module docstring).
    Without it the shader discards every fragment and the spheroid is
    invisible.
    """
    if view_node is None:
        view_node = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLViewNode")
    if view_node is not None:
        view_node.SetBackgroundColor(*BACKGROUND_RGB)
        view_node.SetBackgroundColor2(*BACKGROUND_RGB)
        view_node.SetBoxVisible(False)
        view_node.SetAxisLabelsVisible(False)

    # Enable the contour band on the mapper the Representation drives.
    if _representation is not None:
        mapper = _representation.GetSpheroidMapper()
        if mapper is not None:
            set_visibility = getattr(mapper, "SetContourVisibility", None)
            set_thickness = getattr(mapper, "SetContourThickness", None)
            if set_visibility is not None:
                set_visibility(True)
            if set_thickness is not None:
                set_thickness(CONTOUR_THICKNESS)


def describe() -> dict:
    """Return camera / viewport metadata for capture-side bookkeeping."""
    return {
        "scenario": "DistanceSpheroidContourShader",
        "viewport": {
            "size": [VIEWPORT_WIDTH, VIEWPORT_HEIGHT],
            "background": list(BACKGROUND_RGB),
            "anti_aliasing_frames": ANTI_ALIASING_FRAMES,
        },
        "camera": {
            "position": list(CAMERA_POSITION),
            "focal_point": list(CAMERA_FOCAL_POINT),
            "view_up": list(CAMERA_VIEW_UP),
            "parallel_scale": CAMERA_PARALLEL_SCALE,
            "view_angle": CAMERA_VIEW_ANGLE,
            "clipping_range": list(CAMERA_CLIPPING_RANGE),
        },
        "spheroid": {
            "center": list(SPHEROID_CENTER),
            "radii": [SPHEROID_RADIUS_X, SPHEROID_RADIUS_Y, SPHEROID_RADIUS_Z],
            "init_points": [list(p) for p in SPHEROID_INIT_POINTS],
            "contour_thickness": CONTOUR_THICKNESS,
        },
    }

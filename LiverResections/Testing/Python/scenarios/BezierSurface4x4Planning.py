# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Visual-regression scenario: 4x4 Bezier surface in Planning state.

The default v2.0.0 Bezier fixture.  Parenchyma trim is OFF
(``ClipOut`` uniform 0) — the full surface is visible from a
standard 3D viewpoint, with grid overlay and corner markers active.

This module exposes three setup functions consumed identically by
``capture_baseline.py`` (the interactive capture flow) and
``replay_test.py`` (the CI replay flow):

* :func:`setup_scene`     — populates the MRML scene with a target
  parenchyma model and the v2 resection node graph (data carrier +
  parametric-surface display node + the orchestrating resection-plan
  wrapper carrying the shader inputs).  Returns the data carrier so
  callers can drive further per-scenario state.
* :func:`setup_camera`    — sets the 3D view camera to a deterministic
  pose.  Replay tolerance is tight; camera drift is the most common
  source of false positives, so the pose is fixed numerically rather
  than read from "reset to fit".
* :func:`setup_viewport`  — sets render-window pixel size, background
  colour, anti-aliasing.  Same rationale as the camera fixing.

Designed to be importable from a pristine Slicer (``--no-main-window``)
boot; no module GUI bring-up required.  The scene-setup code builds the
v2 node graph the production GUI render path binds — so the test
exercises the production LayerDM Pipeline render path (ADR-0013 §5,
ADR-0031), not the retired v1 Markups path.

References
----------
* ADR-0003 §"Decision" — characterisation tests pin behaviour before
  refactor.
* ADR-0020 §"Rollout plan" §7 — the GPU-tessellation rewrite is gated
  on these baselines passing on the v2.0.0 mapper.
"""

from __future__ import annotations

import numpy as np  # type: ignore[import-not-found]
import slicer  # type: ignore[import-not-found]
import vtk  # type: ignore[import-not-found]
from vtk.util import numpy_support  # type: ignore[import-not-found]


# Standard viewport configuration shared between Planning and Confirmed
# scenarios.  Centralised here because both scenarios use the same
# render geometry; the visible difference is shader-uniform-driven.
VIEWPORT_WIDTH = 800
VIEWPORT_HEIGHT = 600
BACKGROUND_RGB = (0.0, 0.0, 0.0)
ANTI_ALIASING_FRAMES = 0  # deterministic; AA introduces sub-pixel jitter

# Bezier control-polygon footprint.  ``AddBezierSurface`` lays out a
# 4×4 grid at (10*i, 10*j, 0) (spans 0..30 in u, v) — smaller than the
# parenchyma sphere in xy, which makes the bezier-plane / contour-band
# alignment hard to visually verify (the ring ends up outside the patch
# projection).  The scenario re-positions the control points to span
# -30..60 in both u and v, centred on the sphere's xy centre (15, 15)
# and fully enclosing the sphere's z=0 disc (radius 40, extent -25..55).
# This makes "is the contour band coplanar with the bezier at the
# margin offset?" visually checkable.
PATCH_HALF_EXTENT = 45.0        # control points at ±45 in u, v from (15,15)
PATCH_SPACING = 30.0            # 4 control points at -30, 0, 30, 60 → centre 15
PATCH_CENTER_XY = (15.0, 15.0)  # matches sphere centre — see _make_synthetic_parenchyma

# Camera pose: oblique 3D view of the 90x90 mm Bezier surface (after
# the scenario expands the patch).  Focal point is the patch + sphere
# common centre (15, 15, 0).  Distance ~147 mm at a 45° view angle
# gives a ~122 mm vertical frustum extent at the focal plane — fits the
# 90 mm patch plus the 80 mm sphere with margin.  ``parallel_scale`` is
# sized for the same extent in case parallel projection is engaged.
CAMERA_POSITION = (90.0, -75.0, 90.0)
CAMERA_FOCAL_POINT = (15.0, 15.0, 0.0)
CAMERA_VIEW_UP = (0.0, 0.0, 1.0)
CAMERA_PARALLEL_SCALE = 70.0
CAMERA_VIEW_ANGLE = 45.0
CAMERA_CLIPPING_RANGE = (10.0, 500.0)


def _make_parenchyma_distance_map(
    sphere_center: tuple[float, float, float],
    sphere_radius: float,
) -> slicer.vtkMRMLScalarVolumeNode:
    """Synthesise the 4-channel distance-map volume the bezier mapper samples.

    The bezier mapper's fragment shader samples a 4-component 3D distance
    texture at each fragment of the bezier patch::

        vec4 dist = texture(distanceTexture, fragPositionMC.xyz);

    * ``dist[0]`` — signed distance to the parenchyma surface (drives
      the resection-margin band on the bezier patch — fragments with
      ``dist[0] < lowMargin`` get the margin colour).
    * ``dist[1]`` — also parenchyma signed distance.  The bezier
      mapper's ClipOut branch discards fragments where ``dist[1] > 2``
      (the conventional "trim the bezier patch to the parenchyma
      footprint" semantics).  With the bezier patch flat at z=0
      against a sphere centred at z=0, this discards the portions of
      the patch outside the sphere's equatorial disc — making ClipOut
      visually distinct from Planning.
    * ``dist[2]``, ``dist[3]`` — zero (no vascular data in the fixture).

    The texture upload code in ``vtkMultiTextureObjectHelper::
    CreateSeq3DFromRaw`` reads ``width * height * depth * numComps``
    floats from ``imageData->GetScalarPointer()`` — so the image's
    actual component count and the display node's ``TextureNumComps``
    must match.  Both are 4 here.

    Slicer's MRML volume nodes require ``vtkImageData`` to be in IJK
    space (origin (0,0,0), spacing (1,1,1), identity direction); the
    world-coordinate mapping lives on the volume node itself.
    """
    bounds_min = (-40.0, -40.0, -50.0)
    bounds_max = (70.0, 70.0, 50.0)
    spacing = 1.0

    dims = tuple(
        int((bounds_max[i] - bounds_min[i]) / spacing) + 1 for i in range(3)
    )
    nx, ny, nz = dims

    xs = np.arange(nx) * spacing + bounds_min[0]
    ys = np.arange(ny) * spacing + bounds_min[1]
    zs = np.arange(nz) * spacing + bounds_min[2]
    Z, Y, X = np.meshgrid(zs, ys, xs, indexing="ij")

    cx, cy, cz = sphere_center
    parenchyma_dist = (
        np.sqrt((X - cx) ** 2 + (Y - cy) ** 2 + (Z - cz) ** 2) - sphere_radius
    ).astype(np.float32)

    data = np.stack(
        [
            parenchyma_dist,
            parenchyma_dist,
            np.zeros_like(parenchyma_dist),
            np.zeros_like(parenchyma_dist),
        ],
        axis=-1,
    )

    image = vtk.vtkImageData()
    image.SetDimensions(nx, ny, nz)
    image.SetOrigin(0.0, 0.0, 0.0)
    image.SetSpacing(1.0, 1.0, 1.0)

    flat = np.ascontiguousarray(data.reshape(-1, 4))
    arr = numpy_support.numpy_to_vtk(flat, deep=True, array_type=vtk.VTK_FLOAT)
    arr.SetNumberOfComponents(4)
    arr.SetName("DistanceMap")
    image.GetPointData().SetScalars(arr)

    volume_node = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLScalarVolumeNode", "VisualTestDistanceMap"
    )
    volume_node.SetOrigin(*bounds_min)
    volume_node.SetSpacing(spacing, spacing, spacing)
    volume_node.SetAndObserveImageData(image)
    return volume_node


def _make_synthetic_parenchyma() -> slicer.vtkMRMLModelNode:
    """Return a small synthetic liver-parenchyma model.

    The mapper consumes a parenchyma polydata for the trim shader's
    signed-distance lookup; for visual-regression purposes the exact
    organ shape is irrelevant — what matters is that the resection's
    Bezier surface intersects it and the trim/grid/margin shaders
    evaluate against deterministic geometry.

    A sphere centered near the Bezier patch's middle, scaled to a few
    times the patch side length, gives the mapper a usable target.
    """
    sphere = vtk.vtkSphereSource()
    sphere.SetCenter(15.0, 15.0, 0.0)
    sphere.SetRadius(40.0)
    sphere.SetThetaResolution(48)
    sphere.SetPhiResolution(48)
    sphere.Update()

    model = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLModelNode", "VisualTestParenchyma"
    )
    model.SetAndObservePolyData(sphere.GetOutput())
    model.CreateDefaultDisplayNodes()
    display = model.GetDisplayNode()
    display.SetVisibility(True)
    display.SetColor(0.8, 0.6, 0.6)
    display.SetOpacity(0.35)
    return model


def setup_scene() -> slicer.vtkMRMLBezierSurfaceNode:
    """Populate ``slicer.mrmlScene`` with the v2 4x4 Bezier Planning fixture.

    The function clears the scene first so it is idempotent under
    repeated invocation (e.g. across retries in capture_baseline.py).

    The visible pixels in the ``qMRMLThreeDWidget`` replay harness come
    from the v2 LayerDM render path: the data carrier
    ``vtkMRMLBezierSurfaceNode`` + its decoration
    ``vtkMRMLParametricSurfaceDisplayNode`` + the orchestrating
    ``vtkMRMLResectionPlanNode`` (which carries the distance-map volume +
    the safety / risk margins per ADR-0031) → ``LiverBezierSurfacePipeline``
    → ``BezierPlanningRepresentation`` → the real
    ``vtkOpenGLBezierResectionPolyDataMapper``.  The pipeline's creator
    matches the parametric-surface display node; the pipeline
    reverse-resolves the plan from the carrier's ``geometry``
    back-reference (ADR-0031) and threads the distance map + margins onto
    the mapper.

    Returns
    -------
    vtkMRMLBezierSurfaceNode
        The created data carrier; callers reach the display node via
        ``GetDisplayNode()`` to flip per-state uniforms (e.g. the
        Confirmed scenario's ``ClipOut``).
    """
    slicer.mrmlScene.Clear(0)

    # Force-load the LiverResections logic.  In ``--no-main-window``
    # boots, modules are not auto-instantiated until first reference;
    # going through ``slicer.modules`` triggers module load + logic
    # singleton construction — which performs the ADR-0013 §5
    # registration calls (node classes + the LayerDM displayable manager
    # in default views + the Pipeline creator) the v2 render path needs.
    slicer.modules.liverresections.logic()

    _make_synthetic_parenchyma()
    distance_map = _make_parenchyma_distance_map(
        sphere_center=(15.0, 15.0, 0.0),
        sphere_radius=40.0,
    )

    # v2 data carrier + its parametric-surface display node.  The LayerDM
    # Pipeline creator matches on the display node; the carrier is its
    # displayable node (``display.GetDisplayableNode()``), from which the
    # Pipeline derives its data node.
    carrier = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLBezierSurfaceNode", "VisualTestBezier"
    )
    display = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLParametricSurfaceDisplayNode", "VisualTestBezierDisplay"
    )
    carrier.SetAndObserveDisplayNodeID(display.GetID())

    # Position the 4x4 control grid so the patch encloses the parenchyma's
    # z=0 disc — same layout the v1 fixture used (centred on sphere centre
    # (15, 15), spanning -30..60).  ``SetControlPoint`` is the
    # Python-wrappable grid seam; ``(row, col)`` indexes the row-major grid.
    cx, cy = PATCH_CENTER_XY
    base_x = cx - PATCH_HALF_EXTENT
    base_y = cy - PATCH_HALF_EXTENT
    for row in range(4):
        for col in range(4):
            carrier.SetControlPoint(
                row,
                col,
                base_x + PATCH_SPACING * row,
                base_y + PATCH_SPACING * col,
                0.0,
            )

    # Decoration on the display node
    # (vtkMRMLParametricSurfaceDisplayNode).  Unlike v1 there is no
    # ``TextureNumComps`` to set — the v2 mapper derives the component
    # count from the distance-map image itself.  Planning leaves
    # ``ClipOut`` off — the full surface is visible.
    display.SetResectionColor(1.0, 1.0, 1.0)
    display.SetGrid3DVisibility(True)
    display.SetClipOut(False)
    display.SetVisibility(True)

    # The orchestrating plan wrapper carries the path-specific inputs the
    # surface shader needs (ADR-0031): the distance-map volume + the
    # safety / risk margins (the v1 shader inputs that lived on the
    # markups node).  The ``geometry`` reference to the carrier is what
    # lets the Pipeline reverse-resolve this plan from the rendered
    # surface.
    plan = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLResectionPlanNode", "VisualTestResectionPlan"
    )
    plan.SetAndObserveGeometryNode(carrier)
    plan.SetAndObserveDistanceMapVolumeNode(distance_map)
    plan.SetSafetyMargin(10.0)
    plan.SetRiskMargin(2.0)

    # Planning state activates the BezierPlanningRepresentation (the one
    # that threads the distance map).  Confirmed reuses this fixture and
    # flips the display node's ClipOut — it stays on this representation,
    # mirroring v1's single-representation + uniform model.
    carrier.SetState(1)  # vtkMRMLBezierSurfaceNode::Planning

    return carrier


def setup_camera(view_node: slicer.vtkMRMLViewNode | None = None) -> None:
    """Set the 3D view camera to the scenario's deterministic pose.

    Parameters
    ----------
    view_node
        Optional explicit view node; defaults to the singleton
        ``vtkMRMLViewNode`` in the current scene.
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

    # vtkCamera accessors for fields not surfaced on the MRML node.
    vtk_camera = camera_node.GetCamera()
    vtk_camera.SetParallelScale(CAMERA_PARALLEL_SCALE)
    vtk_camera.SetViewAngle(CAMERA_VIEW_ANGLE)
    vtk_camera.SetClippingRange(*CAMERA_CLIPPING_RANGE)

    # Explicit Modified() on the MRML camera node so any observer
    # (e.g. the active 3D view) repositions before the subsequent
    # ``forceRender()`` in the replay flow.  Without it the first
    # frame captured under CI has been observed to use a stale pose
    # (the camera setters above only mutate the underlying
    # ``vtkCamera`` directly; the MRML-level Modified event is what
    # the view manager listens for).
    camera_node.Modified()


def setup_viewport(view_node: slicer.vtkMRMLViewNode | None = None) -> None:
    """Set viewport pixel size, background colour, anti-aliasing.

    Anti-aliasing is forced OFF because multi-sample AA introduces
    sub-pixel jitter that is hardware-dependent — the same Slicer
    build on two different GPUs would produce visibly different
    pixels.  Reproducibility trumps prettiness in the regression
    bundle.
    """
    if view_node is None:
        view_node = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLViewNode")
    if view_node is None:
        return

    view_node.SetBackgroundColor(*BACKGROUND_RGB)
    view_node.SetBackgroundColor2(*BACKGROUND_RGB)
    # Box / axis labels off — they introduce text rendering jitter on
    # different freetype builds.
    view_node.SetBoxVisible(False)
    view_node.SetAxisLabelsVisible(False)


def describe() -> dict:
    """Return a small dict of metadata for capture-side bookkeeping.

    Persisted alongside the captured bundle as the source-of-truth
    record of what camera + viewport values the baseline was captured
    against.  ``replay_test.py`` re-reads this and compares to its own
    runtime values to detect drift between the scenario module and the
    saved bundle.
    """
    return {
        "scenario": "BezierSurface4x4Planning",
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
    }

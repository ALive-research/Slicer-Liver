# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Visual-regression scenario: 4x4 resectogram, BLUR OFF, square scaling.

T3 ResectogramPipeline baseline target (ADR-0027 invariant-test-first).
This is the reference resectogram appearance: the flattened parametric
image of a square ``(u, v)`` domain Bezier surface, rendered with the
resectogram strip enabled and the Gaussian-blur post-pass DISABLED.

Capture contract
----------------
The baseline is captured against the v2.0 ResectogramPipeline render path
(the v1 markups render is retired — ADR-0014 §"Dissolution"; ADR-0032
§"Consequences").  The capture is maintainer-driven
(``capture_baseline.py``); until a ``.sha512`` stub is committed under
``../Data/Baseline/`` the replay driver skips this scenario with a clear
log line, so the body below is reached only at capture time.

Scene shape
-----------
Mirrors ``BezierSurface4x4Planning.setup_scene`` — a synthetic parenchyma
model + a 4-component distance-map volume + a v2 ``vtkMRMLBezierSurfaceNode``
carrier decorated by a ``vtkMRMLParametricSurfaceDisplayNode`` and
orchestrated by a ``vtkMRMLResectionPlanNode`` wrapper (distance map +
margins, ADR-0031) — and additionally attaches a
``vtkMRMLResectogramDisplayNode`` carrying the strip appearance.  The blur
toggle is a ``vtkMRMLResectogramDisplayNode`` field (net-new for v2.0);
this blur-OFF scenario leaves it off, and ``describe()`` records
``blur_enabled = False`` so the bundle metadata is unambiguous.

No module-level scene handles: ``setup_scene`` RETURNS every node it
creates so nothing leaks through a module global (the ``global``
caching pattern trips ``vtkDebugLeaks`` at shutdown).

Module-layer test, ADR-0008 §2/§3 (workflow row, ``render_interactive``
fixture).  Importable from a pristine ``--no-main-window`` Slicer boot.

References
----------
* ADR-0008 §2/§3 — module/workflow visual-regression discipline +
  capture-then-replay harness.
* ADR-0013 §6 — the flattened-surface Representation owned by the
  ResectogramPipeline (the v2.0 render path this baseline migrates to).
* ADR-0025 §Context — the resectogram is the flattened 2D image of the
  Bezier ``(u, v)`` parameter domain.
* ADR-0027 — invariant-test-first; baseline captured before the v2.0
  rewrite, re-baselined after.
"""

from __future__ import annotations

import numpy as np  # type: ignore[import-not-found]
import slicer  # type: ignore[import-not-found]
import vtk  # type: ignore[import-not-found]
from vtk.util import numpy_support  # type: ignore[import-not-found]


# Shared viewport configuration for the resectogram panel.  The
# resectogram is a 2D flattened image, so a parallel-projection square
# panel is used; the exact numbers are pinned at first capture.
VIEWPORT_WIDTH = 600
VIEWPORT_HEIGHT = 600
BACKGROUND_RGB = (0.0, 0.0, 0.0)
ANTI_ALIASING_FRAMES = 0  # deterministic; AA introduces sub-pixel jitter

# Whether the Gaussian-blur post-pass is engaged.  This scenario pins the
# blur-OFF reference; Resectogram4x4BlurOn pins blur-ON.  Blur is not a
# field on the legacy display node, so blur-OFF == the v1 appearance.
BLUR_ENABLED = False

# Whether the anisotropic aspect-ratio scaling is applied.  Square domain
# here, so the aspect-ratio helper yields {1, 1} either way; left ON to
# match the v1 default and the non-square scenario's configuration.
ENABLE_FLEXIBLE_BOUNDARY = True

# Square (u, v) domain — control points span equal extents in u and v so
# the aspect-ratio helper yields {1, 1} (no anisotropic squeeze).  This
# is the counterpart to Resectogram4x4NonSquareScaling.
PATCH_HALF_EXTENT_U = 45.0
PATCH_HALF_EXTENT_V = 45.0
PATCH_CENTER_XY = (15.0, 15.0)

# Parenchyma sphere the distance map is built around — shared centre with
# the patch so the flattened strip samples a deterministic signed
# distance field.
SPHERE_CENTER = (15.0, 15.0, 0.0)
SPHERE_RADIUS = 40.0

# Camera pose for the flattened resectogram panel.  The v2.0
# ResectogramPipeline renders the strip on the FIXED flattened-domain quad
# the Representation owns (the v1 ``BezierPlane`` grid spanning x in
# [-60, 60], y in [0, 120]); frame its centre (0, 60) head-on so the strip
# fills the panel.  Numeric pose, not reset-to-fit (camera drift is the most
# common visual-regression false positive).
CAMERA_POSITION = (0.0, 60.0, 300.0)
CAMERA_FOCAL_POINT = (0.0, 60.0, 0.0)
CAMERA_VIEW_UP = (0.0, 1.0, 0.0)
CAMERA_PARALLEL_SCALE = 70.0
CAMERA_VIEW_ANGLE = 45.0
CAMERA_CLIPPING_RANGE = (10.0, 800.0)


def _make_parenchyma_distance_map(
    sphere_center: tuple[float, float, float],
    sphere_radius: float,
) -> slicer.vtkMRMLScalarVolumeNode:
    """Synthesise the 4-channel distance-map volume the resectogram samples.

    Same construction as ``BezierSurface4x4Planning`` — a 4-component
    signed-distance texture (parenchyma distance in channels 0 and 1,
    zeros in 2 and 3).  The resectogram mapper
    (``vtkOpenGLResection2DPolyDataMapper``) samples this to draw the
    flattened margin band; ``TextureNumComps`` must equal the component
    count (4) on the display node.
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
        "vtkMRMLScalarVolumeNode", "VisualTestResectogramDistanceMap"
    )
    volume_node.SetOrigin(*bounds_min)
    volume_node.SetSpacing(spacing, spacing, spacing)
    volume_node.SetAndObserveImageData(image)
    return volume_node


def _make_synthetic_parenchyma() -> slicer.vtkMRMLModelNode:
    """Return a small synthetic liver-parenchyma model (sphere target)."""
    sphere = vtk.vtkSphereSource()
    sphere.SetCenter(*SPHERE_CENTER)
    sphere.SetRadius(SPHERE_RADIUS)
    sphere.SetThetaResolution(48)
    sphere.SetPhiResolution(48)
    sphere.Update()

    model = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLModelNode", "VisualTestResectogramParenchyma"
    )
    model.SetAndObservePolyData(sphere.GetOutput())
    model.CreateDefaultDisplayNodes()
    display = model.GetDisplayNode()
    display.SetVisibility(True)
    display.SetColor(0.8, 0.6, 0.6)
    display.SetOpacity(0.35)
    return model


def _build_resectogram_bezier(
    half_extent_u: float,
    half_extent_v: float,
    enable_flexible_boundary: bool,
    distance_map: slicer.vtkMRMLScalarVolumeNode,
) -> slicer.vtkMRMLBezierSurfaceNode:
    """Build the v2 Bezier carrier + plan wrapper for the resectogram strip.

    Mirrors ``BezierSurface4x4Planning.setup_scene`` — a v2 data carrier
    ``vtkMRMLBezierSurfaceNode`` decorated by a
    ``vtkMRMLParametricSurfaceDisplayNode``, orchestrated by a
    ``vtkMRMLResectionPlanNode`` wrapper that carries the distance-map
    volume + the safety / risk margins (ADR-0031; ADR-0014 §"Fourth
    layer").  The v1 markups Bezier render path is retired (ADR-0014
    §"Dissolution"; ADR-0032 §"Consequences"); the resectogram is drawn by
    the v2 ResectogramPipeline (ADR-0013 §6) keyed on the
    ``vtkMRMLResectogramDisplayNode`` attached separately.  The
    control-point footprint sets the ``(u, v)`` parametric extents the
    flattened strip maps.

    Returns the created v2 Bezier carrier.
    """
    carrier = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLBezierSurfaceNode", "VisualTestResectogramBezier"
    )
    surface_display = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLParametricSurfaceDisplayNode", "VisualTestResectogramBezierDisplay"
    )
    carrier.SetAndObserveDisplayNodeID(surface_display.GetID())

    # Lay out the 4x4 control grid so the patch's u extent is
    # 2*half_extent_u and its v extent is 2*half_extent_v, centred on the
    # parenchyma sphere's xy centre.  ``SetControlPoint(row, col, x, y, z)``
    # is the Python-wrappable grid seam; u runs along the row, v along the
    # column.
    cx, cy = PATCH_CENTER_XY
    base_x = cx - half_extent_u
    base_y = cy - half_extent_v
    spacing_u = (2.0 * half_extent_u) / 3.0  # 4 control points => 3 spans
    spacing_v = (2.0 * half_extent_v) / 3.0
    for row in range(4):
        for col in range(4):
            carrier.SetControlPoint(
                row,
                col,
                base_x + spacing_u * row,
                base_y + spacing_v * col,
                0.0,
            )

    surface_display.SetClipOut(False)
    surface_display.SetVisibility(True)

    # The orchestrating plan wrapper carries the surface shader's
    # path-specific inputs (ADR-0031): the distance-map volume + the safety
    # / risk margins (the v1 shader inputs that lived on the markups node).
    # The ``geometry`` reference to the carrier lets the ResectogramPipeline
    # reverse-resolve this plan from the rendered surface.
    plan = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLResectionPlanNode", "VisualTestResectogramResectionPlan"
    )
    plan.SetAndObserveGeometryNode(carrier)
    plan.SetAndObserveDistanceMapVolumeNode(distance_map)
    plan.SetSafetyMargin(10.0)
    plan.SetRiskMargin(2.0)

    carrier.SetState(1)  # vtkMRMLBezierSurfaceNode::Planning

    return carrier


def _attach_resectogram_display_node(
    bezier: slicer.vtkMRMLBezierSurfaceNode,
    enable_flexible_boundary: bool,
) -> slicer.vtkMRMLNode:
    """Create + attach the v2.0 ``vtkMRMLResectogramDisplayNode``.

    The dedicated resectogram display node is the v2.0 LayerDM carrier
    (ADR-0013 §1) the registered ``ResectogramPipeline`` keys on: adding it
    as a second display node of the v2 Bezier carrier drives the pipeline's
    ``FlattenedSurfaceRepresentation`` / ``VascularContourRepresentation``
    to render the flattened ``(u, v)`` strip.  Its resectogram fields carry
    the strip appearance (``ShowResection2D`` / ``EnableFlexibleBoundary`` /
    ``TextureNumComps``) — the v1 markups render path is retired (ADR-0014
    §"Dissolution"; ADR-0032 §"Consequences").  ADR-0025 §Context.

    Returns the created display node so the caller owns teardown (the
    no-module-globals contract).
    """
    resectogram_display = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLResectogramDisplayNode", "VisualTestResectogramDisplay"
    )
    resectogram_display.SetShowResection2D(True)
    resectogram_display.SetMirrorDisplay(False)
    resectogram_display.SetEnableFlexibleBoundary(enable_flexible_boundary)
    resectogram_display.SetTextureNumComps(4)
    resectogram_display.SetVisibility(True)
    # Back-reference the Bezier surface so the pipeline's
    # ``GetDisplayableNode()`` resolves the data node feeding MatRatio +
    # the distance-map texture.
    bezier.AddAndObserveDisplayNodeID(resectogram_display.GetID())
    return resectogram_display


def setup_scene():
    """Populate the scene with the blur-off square-domain resectogram fixture.

    Idempotent under repeated invocation (clears the scene first).  Builds
    the v2 resection node graph (carrier + parametric-surface display node
    + resection-plan wrapper) and attaches the resectogram display node;
    the v2.0 ResectogramPipeline renders the flattened strip from these
    inputs (ADR-0013 §6).

    Returns
    -------
    tuple
        ``(bezier_node, parenchyma_model, distance_map_volume,
        resectogram_display)`` — every node the scenario created, returned
        (NOT cached in module globals) so the caller owns teardown and
        nothing survives to ``vtkDebugLeaks``.  The fourth handle is the
        v2.0 ``vtkMRMLResectogramDisplayNode`` the ResectogramPipeline
        keys on.
    """
    slicer.mrmlScene.Clear(0)

    # Force-load the LiverResections logic so the node classes + the
    # resectogram render path are registered (same trigger
    # BezierSurface4x4Planning uses).
    slicer.modules.liverresections.logic()

    parenchyma = _make_synthetic_parenchyma()
    distance_map = _make_parenchyma_distance_map(
        sphere_center=SPHERE_CENTER,
        sphere_radius=SPHERE_RADIUS,
    )
    bezier = _build_resectogram_bezier(
        half_extent_u=PATCH_HALF_EXTENT_U,
        half_extent_v=PATCH_HALF_EXTENT_V,
        enable_flexible_boundary=ENABLE_FLEXIBLE_BOUNDARY,
        distance_map=distance_map,
    )
    resectogram_display = _attach_resectogram_display_node(
        bezier, enable_flexible_boundary=ENABLE_FLEXIBLE_BOUNDARY
    )

    return bezier, parenchyma, distance_map, resectogram_display


def setup_camera(view_node=None):
    """Fix the resectogram panel's deterministic (parallel) view.

    Same numeric-pose discipline as ``BezierSurface4x4Planning`` — the pose
    is fixed rather than read from "reset to fit", because camera drift is
    the most common source of replay false positives.
    """
    if view_node is None:
        view_node = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLViewNode")
        if view_node is None:
            view_node = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLViewNode", "VisualTestResectogramView"
            )

    camera_logic = slicer.modules.cameras.logic()
    camera_node = camera_logic.GetViewActiveCameraNode(view_node)
    if camera_node is None:
        camera_node = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLCameraNode", "VisualTestResectogramCamera"
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


def setup_viewport(view_node=None):
    """Set resectogram panel pixel size, background, anti-aliasing.

    Anti-aliasing forced OFF (sub-pixel jitter is hardware-dependent);
    box / axis labels off (text rendering jitter on different freetype
    builds).  Same rationale as ``BezierSurface4x4Planning``.
    """
    if view_node is None:
        view_node = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLViewNode")
    if view_node is None:
        return

    view_node.SetBackgroundColor(*BACKGROUND_RGB)
    view_node.SetBackgroundColor2(*BACKGROUND_RGB)
    view_node.SetBoxVisible(False)
    view_node.SetAxisLabelsVisible(False)

    # Tag the panel's view as the dedicated resectogram view so the
    # tightened ResectogramPipeline creator (ADR-0023 §Stage-4) dispatches
    # the flattened strip into it -- the tightened creator no longer fires
    # for an untagged view.  Reuse the production tag so the scenario, the
    # arena, and the live module agree on a single value.
    from LiverResectionsLib.ResectogramViewManager import (  # type: ignore[import-not-found]
        RESECTOGRAM_VIEW_SINGLETON_TAG,
    )

    view_node.SetSingletonTag(RESECTOGRAM_VIEW_SINGLETON_TAG)


def describe() -> dict:
    """Metadata persisted alongside the captured bundle."""
    return {
        "scenario": "Resectogram4x4BlurOff",
        "blur_enabled": BLUR_ENABLED,
        "enable_flexible_boundary": ENABLE_FLEXIBLE_BOUNDARY,
        "patch_half_extent": [PATCH_HALF_EXTENT_U, PATCH_HALF_EXTENT_V],
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

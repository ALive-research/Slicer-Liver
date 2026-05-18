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
  parenchyma model, a LiverResection node, and the linked Bezier
  surface node.  Returns the created resection node so callers can
  drive further per-scenario state.
* :func:`setup_camera`    — sets the 3D view camera to a deterministic
  pose.  Replay tolerance is tight; camera drift is the most common
  source of false positives, so the pose is fixed numerically rather
  than read from "reset to fit".
* :func:`setup_viewport`  — sets render-window pixel size, background
  colour, anti-aliasing.  Same rationale as the camera fixing.

Designed to be importable from a pristine Slicer (``--no-main-window``)
boot; no module GUI bring-up required.  The scene-setup code uses
``vtkSlicerLiverResectionsLogic`` — the same logic the GUI invokes —
rather than hand-building MRML, to ensure the test exercises the
production code path.

References
----------
* ADR-0003 §"Decision" — characterisation tests pin behaviour before
  refactor.
* ADR-0020 §"Rollout plan" §7 — the GPU-tessellation rewrite is gated
  on these baselines passing on the v2.0.0 mapper.
"""

from __future__ import annotations

import slicer  # type: ignore[import-not-found]
import vtk  # type: ignore[import-not-found]


# Standard viewport configuration shared between Planning and Confirmed
# scenarios.  Centralised here because both scenarios use the same
# render geometry; the visible difference is shader-uniform-driven.
VIEWPORT_WIDTH = 800
VIEWPORT_HEIGHT = 600
BACKGROUND_RGB = (0.0, 0.0, 0.0)
ANTI_ALIASING_FRAMES = 0  # deterministic; AA introduces sub-pixel jitter

# Camera pose: oblique 3D view of the 30x30 mm Bezier surface generated
# by ``vtkSlicerLiverResectionsLogic::AddBezierSurface`` (4 control
# points per side, 10 mm spacing → control points span 0..30 in u, v).
CAMERA_POSITION = (60.0, -90.0, 70.0)
CAMERA_FOCAL_POINT = (15.0, 15.0, 0.0)
CAMERA_VIEW_UP = (0.0, 0.0, 1.0)
CAMERA_PARALLEL_SCALE = 30.0
CAMERA_VIEW_ANGLE = 30.0
CAMERA_CLIPPING_RANGE = (10.0, 500.0)


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


def setup_scene() -> slicer.vtkMRMLLiverResectionNode:
    """Populate ``slicer.mrmlScene`` with the 4x4 Bezier Planning fixture.

    The function clears the scene first so it is idempotent under
    repeated invocation (e.g. across retries in capture_baseline.py).

    Returns
    -------
    vtkMRMLLiverResectionNode
        The created resection node; callers may further mutate it.
    """
    slicer.mrmlScene.Clear(0)

    # Force-load the LiverResections logic.  In ``--no-main-window``
    # boots, modules are not auto-instantiated until first reference;
    # going through ``slicer.modules`` triggers module load + logic
    # singleton construction.
    logic = slicer.modules.liverresections.logic()

    parenchyma = _make_synthetic_parenchyma()

    resection = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLLiverResectionNode", "VisualTestResection"
    )
    resection.SetTargetOrganModelNode(parenchyma)
    resection.SetResectionMargin(10.0)
    resection.SetUncertaintyMargin(2.0)
    # Planning state — the resection has not been Confirmed; the trim
    # shader's ``ClipOut`` uniform is 0 and the full surface is visible.
    resection.SetState(resection.Initialization)
    resection.SetInitMode(resection.Flat)
    # ClipOut on the resection node mirrors the uniform name in the
    # legacy mapper (``uResectionClipOut``); 0 = no parenchyma discard.
    resection.SetClipOut(False)

    bezier = logic.AddBezierSurface(resection)
    if bezier is None:
        raise RuntimeError(
            "vtkSlicerLiverResectionsLogic::AddBezierSurface returned NULL; "
            "the Bezier surface node could not be created.  Verify the "
            "LiverResections module is registered and the resection node "
            "has a valid target organ."
        )

    # The display node carries the planning-state Bezier surface
    # visibility; turn it on so the mapper runs.
    bezier_display = bezier.GetDisplayNode()
    if bezier_display is not None:
        bezier_display.SetVisibility(True)

    return resection


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

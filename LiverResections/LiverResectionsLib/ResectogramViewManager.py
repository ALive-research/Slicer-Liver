# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Dedicated-view manager for the resectogram concept (`ADR-0023`_ §Stage-4).

The resectogram is the flattened 2D image of the Bezier ``(u, v)``
parameter domain (`ADR-0025`_ §Context).  `ADR-0023`_ §Stage-4 names it
as the ONE custom Slicer layout v2.0 ships: it renders in a dedicated 3D
view, NOT as a sub-viewport of the shared anatomy 3D view (the retired v1
``CoRenderer2D`` path).

``ResectogramViewManager`` owns the dedicated ``vtkMRMLViewNode`` that
carries the resectogram singleton tag.  The view node is a **singleton**:
re-running ``setup()`` (module reload, second open) re-targets the
existing node rather than multiplying view nodes — the singleton-tag
mechanism the Slicer view machinery already enforces.  This mirrors the
SlicerHyperProbe ``HyperprobeViewManager._create_view_node`` precedent:
a private view node with a custom ``LayoutName`` / ``LayoutLabel`` and box
+ axis labels off, so the flattened panel reads as a clean 2D image.

No custom DisplayableManager (`ADR-0013`_ §5; the
``feedback_layerdm_no_custom_dm`` lesson): the dedicated view gets the
upstream LayerDM displayable manager for free via
``RegisterInDefaultViews()``, and the registered ``ResectogramPipeline``
creator — tightened to fire ONLY for the view carrying
``RESECTOGRAM_VIEW_SINGLETON_TAG`` — dispatches the flattened strip into
this view's renderer alone.

References
----------
* `ADR-0013`_ §1, §5 — one Pipeline per display-node type; the three
  registration calls; no custom DisplayableManager.
* `ADR-0023`_ §Stage-4 — the dedicated resectogram view as the one custom
  Slicer layout v2.0 ships.
* `ADR-0025`_ §Context — the resectogram as the flattened ``(u, v)`` image.

.. _ADR-0013: ../../Docs/adr/0013-layerdm-pipeline-pattern.md
.. _ADR-0023: ../../Docs/adr/0023-resection-plan-architecture.md
.. _ADR-0025: ../../Docs/adr/0025-locator-architecture.md
"""

from __future__ import annotations

from typing import Any

# The singleton tag the dedicated resectogram view carries.  The tightened
# ``registerResectogramPipelineCreator().tryCreate`` discriminates the
# dedicated view from every shared 3D anatomy view by this exact value.
# Human-readable, prefix-free (the Hyperprobe custom-view convention,
# ADR-0023 §Stage-4).  The dispatch tests pin the same literal in
# ``Testing/Python/conftest.py`` as RESECTOGRAM_VIEW_SINGLETON_TAG.
RESECTOGRAM_VIEW_SINGLETON_TAG = "LiverResectogram"

# Human-facing layout name / label for the dedicated view.  Reused as the
# Slicer view-node ``LayoutName`` / ``LayoutLabel`` (the Hyperprobe
# precedent uses the bare concept name for both).
_RESECTOGRAM_VIEW_LAYOUT_NAME = "LiverResectogram"
_RESECTOGRAM_VIEW_LAYOUT_LABEL = "Resectogram"

# Flattened-quad camera pose for the dedicated view.  Mirrors
# ``Resectogram4x4BlurOff.setup_camera`` so the production framing, the
# scenario, and the presentation test agree on one pose.  The quad centre
# (the focal point) is the fixed flattened-domain centre the Representation's
# ``BezierPlane`` grid spans (x in [-60, 60], y in [0, 120]) -- (0, 60, 0)
# (ADR-0025 §Context, the flattened (u, v) image).
_RESECTOGRAM_QUAD_CENTRE = (0.0, 60.0, 0.0)
_RESECTOGRAM_CAMERA_DISTANCE = 300.0
_RESECTOGRAM_CAMERA_VIEW_UP = (0.0, 1.0, 0.0)
_RESECTOGRAM_CAMERA_PARALLEL_SCALE = 70.0
_RESECTOGRAM_CAMERA_CLIPPING_RANGE = (10.0, 800.0)


class ResectogramViewManager:
    """Owns the dedicated ``vtkMRMLViewNode`` for the resectogram display.

    Singleton-by-tag: ``ensureViewNode()`` returns the existing tagged view
    node when one is already in the scene, creating it only on first call.
    Constructing the manager is side-effect-free; the view node is created
    lazily on the first ``ensureViewNode()`` so a bare import (e.g. in a
    unit test that only reads the tag constant) does not mutate the scene.
    """

    def __init__(self) -> None:
        self._view_node: Any | None = None

    def ensureViewNode(self) -> Any:  # noqa: N802 - Slicer/Qt verb convention
        """Return the dedicated resectogram view node, creating it once.

        Singleton (re-target, don't multiply) per the dedicated-view
        decision: a second call returns the SAME node.  Resolves an
        already-present tagged node first (e.g. after a scene reload that
        kept the singleton), so the manager never appends a duplicate.
        """
        import slicer  # type: ignore[import-not-found]

        if self._view_node is not None:
            return self._view_node

        existing = self._find_tagged_view_node(slicer)
        if existing is not None:
            self._view_node = existing
            return existing

        view = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLViewNode")
        view.SetName(_RESECTOGRAM_VIEW_LAYOUT_NAME)
        view.SetSingletonTag(RESECTOGRAM_VIEW_SINGLETON_TAG)
        view.SetLayoutName(_RESECTOGRAM_VIEW_LAYOUT_NAME)
        view.SetLayoutLabel(_RESECTOGRAM_VIEW_LAYOUT_LABEL)
        # The flattened panel reads as a clean 2D image: drop the 3D box
        # and axis labels (the Hyperprobe precedent does the same).
        view.SetBoxVisible(False)
        view.SetAxisLabelsVisible(False)
        self._view_node = view
        return view

    def getViewNode(self) -> Any | None:  # noqa: N802 - Slicer/Qt verb convention
        """Return the owned view node, or ``None`` if not yet created."""
        return self._view_node

    def configureView(  # noqa: N802 - Slicer/Qt verb convention
        self, viewNode: Any, displayNode: Any, surface: Any
    ) -> None:
        """Present the flattened strip ALONE in the dedicated view.

        Three configuration planes, none of which need a custom
        DisplayableManager (`ADR-0013`_ §5; the
        ``feedback_layerdm_no_custom_dm`` lesson) -- view-node + display-node
        + camera state only (`ADR-0023`_ §Stage-4):

        * RESTRICT THE STRIP TO THE VIEW.  The
          ``vtkMRMLResectogramDisplayNode`` is restricted via the Slicer
          display-node allowlist to the dedicated view alone, so its
          ViewNodeIDs list is exactly ``[viewNode]`` (an EMPTY list means
          "all views").

        * RESTRICT THE SELECTED SURFACE AWAY FROM THE VIEW.  Each of the
          ``surface``'s OWN (non-resectogram) display nodes is restricted to
          the existing anatomy view(s) and away from the resectogram view, so
          the resection surface's 3D anatomy does not bleed into the flattened
          strip.  UNKNOWN user-loaded anatomy (parenchyma / other nodes) is
          NOT enumerated or isolated here -- that is deferred to the unified
          GUI load step.

        * FRAME THE CAMERA.  The view's camera node is set to PARALLEL
          projection looking straight down the flattened ``(u, v)`` quad,
          mirroring ``Resectogram4x4BlurOff.setup_camera`` (the same numeric
          pose the scenario and the test agree on).

        Idempotent -- re-running re-applies the same state.

        .. _ADR-0013: ../../Docs/adr/0013-layerdm-pipeline-pattern.md
        .. _ADR-0023: ../../Docs/adr/0023-resection-plan-architecture.md
        """
        import slicer  # type: ignore[import-not-found]

        if viewNode is None:
            return

        resectogramViewID = viewNode.GetID()

        if displayNode is not None:
            displayNode.RemoveAllViewNodeIDs()
            displayNode.AddViewNodeID(resectogramViewID)

        self._restrictSurfaceAwayFromView(slicer, surface, resectogramViewID)
        self._frameCamera(slicer, viewNode, displayNode)

    @staticmethod
    def _restrictSurfaceAwayFromView(  # noqa: N802 - Slicer/Qt verb convention
        slicer: Any, surface: Any, resectogramViewID: str
    ) -> None:
        """Restrict ``surface``'s own display nodes away from the strip view.

        Each non-resectogram display node is bound to the current anatomy
        view(s) excluding the resectogram view.  A display node left at the
        default EMPTY ViewNodeIDs ("all views") would still draw in the
        resectogram view, so the list is made NON-EMPTY and the resectogram
        view ID is excluded.  Falls back to binding every anatomy view present
        so the surface stays visible somewhere even when it had no prior
        restriction.
        """
        if surface is None:
            return

        anatomyViewIDs = ResectogramViewManager._anatomyViewNodeIDs(
            slicer, resectogramViewID
        )

        for index in range(surface.GetNumberOfDisplayNodes()):
            display = surface.GetNthDisplayNode(index)
            if display is None or display.IsA("vtkMRMLResectogramDisplayNode"):
                continue

            existing = [
                display.GetNthViewNodeID(i)
                for i in range(display.GetNumberOfViewNodeIDs())
            ]
            # Drop the resectogram view if it was previously allowed; keep any
            # other explicit restriction the surface already carried.
            kept = [
                viewID for viewID in existing if viewID != resectogramViewID
            ]
            target = kept if kept else anatomyViewIDs

            display.RemoveAllViewNodeIDs()
            for viewID in target:
                display.AddViewNodeID(viewID)

    @staticmethod
    def _anatomyViewNodeIDs(  # noqa: N802 - Slicer/Qt verb convention
        slicer: Any, resectogramViewID: str
    ) -> list:
        """Return the IDs of every view node EXCEPT the resectogram view.

        Ensures at least one anatomy view exists to bind the surface to: when
        the only view in the scene is the resectogram view (e.g. a freshly
        cleared scene, or a ``--no-main-window`` boot with no main layout
        view), an anatomy view node is added so the surface can be actively
        restricted to a non-resectogram view -- a default empty ViewNodeIDs
        ("all views") would still draw the surface in the resectogram view.
        """
        scene = slicer.mrmlScene
        ids = []
        count = scene.GetNumberOfNodesByClass("vtkMRMLViewNode")
        for index in range(count):
            node = scene.GetNthNodeByClass(index, "vtkMRMLViewNode")
            if node is None:
                continue
            viewID = node.GetID()
            if viewID != resectogramViewID:
                ids.append(viewID)

        if not ids:
            anatomyView = scene.AddNewNodeByClass(
                "vtkMRMLViewNode", "LiverAnatomyView"
            )
            ids.append(anatomyView.GetID())
        return ids

    @staticmethod
    def _frameCamera(  # noqa: N802 - Slicer/Qt verb convention
        slicer: Any, viewNode: Any, displayNode: Any
    ) -> None:
        """Frame the view camera parallel, looking down the flattened quad.

        Mirrors ``Resectogram4x4BlurOff.setup_camera`` so the production
        framing, the scenario, and the test agree on one pose.  The camera is
        resolved on the VIEW node via the standard cameras-logic accessor (NOT
        the Representation's vestigial ``_resectogram_camera``, which is dead
        and slated for removal).  ``MirrorDisplay`` flips the camera's z sign
        to preserve the mirrored-presentation semantics
        (FlattenedSurfaceRepresentation._pose_overlay_camera).
        """
        camerasModule = getattr(slicer.modules, "cameras", None)
        if camerasModule is None:
            return

        # Frame the camera the view machinery already associates with the
        # view; do NOT mint one ourselves.  A camera node minted here for the
        # SINGLETON resectogram view survives ``vtkMRMLScene.Clear(0)`` (the
        # cameras logic re-pairs it with the surviving singleton view),
        # leaking past test teardown.  When the layout has not yet realised a
        # camera for the view (a pure-headless boot with no render), there is
        # nothing to frame yet -- the embed step that realises the view
        # (showResectogramWidget) brings the camera with it.
        cameraNode = camerasModule.logic().GetViewActiveCameraNode(viewNode)
        if cameraNode is None:
            return

        # The flattened-quad pose.  The quad centre is the focal point; the
        # camera sits straight in front of it on the +z axis (or -z when the
        # display is mirrored) so it looks straight down the (u, v) image.
        focal_x, focal_y, focal_z = _RESECTOGRAM_QUAD_CENTRE
        mirror = bool(
            displayNode is not None
            and hasattr(displayNode, "GetMirrorDisplay")
            and displayNode.GetMirrorDisplay()
        )
        z_sign = -1.0 if mirror else 1.0

        cameraNode.SetFocalPoint(focal_x, focal_y, focal_z)
        cameraNode.SetPosition(
            focal_x, focal_y, focal_z + z_sign * _RESECTOGRAM_CAMERA_DISTANCE
        )
        cameraNode.SetViewUp(*_RESECTOGRAM_CAMERA_VIEW_UP)
        cameraNode.SetParallelProjection(1)

        vtkCamera = cameraNode.GetCamera()
        vtkCamera.SetParallelScale(_RESECTOGRAM_CAMERA_PARALLEL_SCALE)
        vtkCamera.SetClippingRange(*_RESECTOGRAM_CAMERA_CLIPPING_RANGE)

        cameraNode.Modified()

    @staticmethod
    def _find_tagged_view_node(slicer: Any) -> Any | None:
        """Return the scene's resectogram-tagged view node, if any."""
        scene = slicer.mrmlScene
        count = scene.GetNumberOfNodesByClass("vtkMRMLViewNode")
        for index in range(count):
            node = scene.GetNthNodeByClass(index, "vtkMRMLViewNode")
            if (
                node is not None
                and node.GetSingletonTag() == RESECTOGRAM_VIEW_SINGLETON_TAG
            ):
                return node
        return None

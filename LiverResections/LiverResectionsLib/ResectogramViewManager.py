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
.. _ADR-0023: ../../Docs/adr/0023-unified-gui-stage-workflow.md
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

# Flat WHITE background for the PRODUCTION dedicated view (ADR-0023 §Stage-4).
# A flat white panel reads as a clean 2D image, the resectogram presentation
# the maintainer asked for.  This is DELIBERATELY decoupled from the visual-
# regression scenario's ``BACKGROUND_RGB`` (black): the arena's interior-lit-
# fraction / band-content metrics assume a black background (every lit pixel
# is content), so the scenario keeps pushing its own black via the arena's
# ``_apply_camera_and_background``; only this production path goes white.
RESECTOGRAM_VIEW_BACKGROUND_RGB = (1.0, 1.0, 1.0)


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

        # Configure BEFORE AddNode: LayerDM pipeline creators are consulted
        # the moment the node enters the scene, and the surface-family
        # creators exclude this view BY its singleton tag (ADR-0023
        # §Stage-4) -- an add-then-tag order leaks deformable surface
        # pipelines into the flattened strip.
        view = slicer.mrmlScene.CreateNodeByClass("vtkMRMLViewNode")
        view.UnRegister(None)
        view.SetName(_RESECTOGRAM_VIEW_LAYOUT_NAME)
        view.SetSingletonTag(RESECTOGRAM_VIEW_SINGLETON_TAG)
        view.SetLayoutName(_RESECTOGRAM_VIEW_LAYOUT_NAME)
        view.SetLayoutLabel(_RESECTOGRAM_VIEW_LAYOUT_LABEL)
        # The flattened panel reads as a clean 2D image: drop the 3D box
        # and axis labels (the Hyperprobe precedent does the same).
        view.SetBoxVisible(False)
        view.SetAxisLabelsVisible(False)
        view = slicer.mrmlScene.AddNode(view)
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

        * RESTRICT ALL ANATOMY AWAY FROM THE VIEW.  EVERY displayable node's
          (non-resectogram) display nodes in the scene -- the selected
          ``surface`` AND any other anatomy (parenchyma, other models /
          markups / volumes) -- is restricted to the existing anatomy view(s)
          and away from the resectogram view, so no 3D anatomy bleeds into the
          flattened strip.  The standalone embedded ``qMRMLThreeDWidget``
          honours the MRML ViewNodeIDs allowlist (it is the displayable
          managers, not the camera/background, that read it), so this is the
          correct layer for the isolation.  Mirrors the arena's
          ``_restrict_display_to_view`` over every anatomy display node.

        * FRAME THE CAMERA.  The view's camera node is set to PARALLEL
          projection looking straight down the flattened ``(u, v)`` quad,
          mirroring ``Resectogram4x4BlurOff.setup_camera`` (the same numeric
          pose the scenario and the test agree on).

        Idempotent -- re-running re-applies the same state.

        .. _ADR-0013: ../../Docs/adr/0013-layerdm-pipeline-pattern.md
        .. _ADR-0023: ../../Docs/adr/0023-unified-gui-stage-workflow.md
        """
        import slicer  # type: ignore[import-not-found]

        if viewNode is None:
            return

        resectogramViewID = viewNode.GetID()

        if displayNode is not None:
            self._setViewNodeIDsIfChanged(displayNode, [resectogramViewID])

        self._restrictAnatomyAwayFromView(slicer, resectogramViewID)
        self._applyViewNodeBackground(viewNode)
        self._frameCamera(slicer, viewNode, displayNode)

    @staticmethod
    def _applyViewNodeBackground(  # noqa: N802 - Slicer/Qt verb convention
        viewNode: Any,
    ) -> None:
        """Set the MRML view node's flat WHITE background (ADR-0023 §Stage-4).

        The STANDALONE embedded ``qMRMLThreeDWidget`` ignores the view node's
        background (the widget pushes onto its own renderer, see
        ``poseEmbeddedRenderer``).  But the moment the view is handed to the
        Slicer LAYOUT MANAGER -- on a double-click maximize -- the layout-managed
        render reads the BACKGROUND off the MRML view node.  Setting it here (a
        flat white, no gradient) makes a maximized resectogram render correctly
        on white instead of falling back to the default 3D-anatomy blue gradient.

        Idempotent: the view node's ``SetBackgroundColor`` Modifies it even when
        the colour is unchanged, so skip the write when both background colours
        are already the target -- a redundant ``configureView`` then fires no
        view-node ModifiedEvent (one fewer storm leg).
        """
        target = RESECTOGRAM_VIEW_BACKGROUND_RGB
        if (
            tuple(viewNode.GetBackgroundColor()) == target
            and tuple(viewNode.GetBackgroundColor2()) == target
        ):
            return
        viewNode.SetBackgroundColor(*target)
        viewNode.SetBackgroundColor2(*target)

    @staticmethod
    def _restrictAnatomyAwayFromView(  # noqa: N802 - Slicer/Qt verb convention
        slicer: Any, resectogramViewID: str
    ) -> None:
        """Restrict EVERY non-resectogram display node away from the strip view.

        Walks every ``vtkMRMLDisplayableNode`` in the scene and restricts each
        of its non-resectogram display nodes to the anatomy view(s) excluding
        the resectogram view, so no anatomy (the selected surface, the
        parenchyma, or any other loaded node) bleeds into the flattened strip.
        A display node left at the default EMPTY ViewNodeIDs ("all views")
        would still draw in the resectogram view, so the list is made NON-EMPTY
        and the resectogram view ID is excluded.  Falls back to binding every
        anatomy view present so a node with no prior restriction stays visible
        somewhere.  This is the MRML-level half of the no-overlap contract
        (ADR-0023 §Stage-4); the displayable managers honour ViewNodeIDs even
        for the standalone embedded view (unlike the camera/background, which
        it ignores).
        """
        scene = slicer.mrmlScene
        anatomyViewIDs = ResectogramViewManager._anatomyViewNodeIDs(
            slicer, resectogramViewID
        )

        count = scene.GetNumberOfNodesByClass("vtkMRMLDisplayableNode")
        for index in range(count):
            node = scene.GetNthNodeByClass(index, "vtkMRMLDisplayableNode")
            if node is None:
                continue
            for dIndex in range(node.GetNumberOfDisplayNodes()):
                display = node.GetNthDisplayNode(dIndex)
                if display is None or display.IsA("vtkMRMLResectogramDisplayNode"):
                    continue

                existing = [
                    display.GetNthViewNodeID(i)
                    for i in range(display.GetNumberOfViewNodeIDs())
                ]
                # Drop the resectogram view if it was previously allowed; keep
                # any other explicit restriction the node already carried.
                kept = [
                    viewID for viewID in existing if viewID != resectogramViewID
                ]
                target = kept if kept else anatomyViewIDs

                ResectogramViewManager._setViewNodeIDsIfChanged(display, target)

    @staticmethod
    def _setViewNodeIDsIfChanged(  # noqa: N802 - Slicer/Qt verb convention
        display: Any, target: list
    ) -> None:
        """Set a display node's ViewNodeIDs only when they actually differ.

        ``RemoveAllViewNodeIDs`` + ``AddViewNodeID`` each call ``Modified()``
        unconditionally, so re-applying the SAME allowlist still fires the
        display node's ModifiedEvent -- and the resectogram display node's
        ModifiedEvent re-triggers a render, which re-Modified()'s the surface,
        which re-runs ``refreshResectogramDrawer`` -> ``configureView``: the
        maximize render storm's display-node leg (the ~2x display Modifies the
        diagnosis measured).  Skipping the write when the allowlist is already
        the target makes a redundant ``configureView`` Modify nothing, so the
        loop has no fuel.  ``existing == target`` compares order-sensitively;
        the callers always build ``target`` in a stable order so a no-op
        re-apply matches.
        """
        existing = [
            display.GetNthViewNodeID(i)
            for i in range(display.GetNumberOfViewNodeIDs())
        ]
        if existing == list(target):
            return
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

        position = (
            focal_x,
            focal_y,
            focal_z + z_sign * _RESECTOGRAM_CAMERA_DISTANCE,
        )
        vtkCamera = cameraNode.GetCamera()

        # Re-posing the camera node to the SAME pose still fires its
        # ModifiedEvent (each Set* call Modifies, plus the explicit Modified()
        # below), which the view machinery turns into a render -- another leg
        # of the maximize render storm if configureView re-runs every frame.
        # Apply the pose ONLY when it actually differs from the current one, so
        # a redundant configureView leaves the camera untouched and fires no
        # render.
        already_posed = (
            tuple(cameraNode.GetFocalPoint()) == _RESECTOGRAM_QUAD_CENTRE
            and tuple(cameraNode.GetPosition()) == position
            and tuple(cameraNode.GetViewUp()) == _RESECTOGRAM_CAMERA_VIEW_UP
            and cameraNode.GetParallelProjection() == 1
            and vtkCamera.GetParallelScale() == _RESECTOGRAM_CAMERA_PARALLEL_SCALE
            and tuple(vtkCamera.GetClippingRange())
            == _RESECTOGRAM_CAMERA_CLIPPING_RANGE
        )
        if already_posed:
            return

        cameraNode.SetFocalPoint(focal_x, focal_y, focal_z)
        cameraNode.SetPosition(*position)
        cameraNode.SetViewUp(*_RESECTOGRAM_CAMERA_VIEW_UP)
        cameraNode.SetParallelProjection(1)

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

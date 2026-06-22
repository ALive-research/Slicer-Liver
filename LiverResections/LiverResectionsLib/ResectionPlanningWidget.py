# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Stage-4 "Resection Planning" panel (`ADR-0023`_ §Stage-4, `ADR-0004`_).

The panel that selects the active resection surface and auto-populates the
embedded resectogram view.  Per `ADR-0004`_ the GUI lives in Python: this
widget imports the (correctly-Python) ``ResectogramViewManager`` and calls
its wrapped C++ nodes/logic directly -- no ``executeString`` string bridge.

The behaviour mirrors the retired C++ ``qSlicerLiverResectionsModuleWidget``
faithfully:

* AUTO-POPULATE.  Selecting a ``vtkMRMLMarkupsBezierSurfaceNode`` that carries
  a distance map ensures EXACTLY ONE ``vtkMRMLResectogramDisplayNode`` on it,
  runs ``ResectogramViewManager.configureView``, embeds a single
  ``qMRMLThreeDWidget`` bound to the singleton view node, and hides the hint.
  Otherwise the hint is shown with the appropriate explanatory text.
  Edge-triggered on ``(surface identity, hasDistanceMap)`` to avoid the
  render-storm re-populate.
* EMBED.  ONE ``qMRMLThreeDWidget`` (objectName "ResectogramThreeDWidget");
  realize-then-bind so the distance-map 3D texture uploads into a realized GL
  context.
* CAMERA + BACKGROUND.  The standalone embedded widget ignores the MRML view
  node config, so the flattened-quad pose + flat white background are pushed
  onto the renderer directly (``poseEmbeddedRenderer``).
* INTERACTION LOCK.  The camera widget's trackball-rotate translations are
  remapped to ``WidgetEventNone`` so the flat panel cannot be orbited
  (``lockEmbeddedViewInteraction``) -- no custom DisplayableManager
  (`ADR-0013`_ §5).
* REACTIVITY.  The active surface is observed for ``PointModifiedEvent`` ONLY
  (the storm fix) to force a render of the embedded view; a deferred
  initial-render kick shows the strip on auto-populate without an edit.
* CUSTOM ENLARGE.  A left double-click on the embedded view reparents the ONE
  widget into the layout manager's central viewport and back -- Slicer's
  built-in maximize is suppressed (it realises a blank second widget on the
  singleton view node).

References
----------
* `ADR-0004`_ -- GUI widgets are Python; C++ only for data-only MRML nodes +
  profile-justified algorithm libs.
* `ADR-0023`_ §Stage-4 -- the dedicated resectogram view + auto-populate.
* `ADR-0013`_ §5 -- no custom DisplayableManager; config only.
* `ADR-0009`_ -- explainable state (the hint).

.. _ADR-0004: ../../Docs/adr/0004-language-boundary.md
.. _ADR-0009: ../../Docs/adr/0009-ux-and-design-discipline.md
.. _ADR-0013: ../../Docs/adr/0013-layerdm-pipeline-pattern.md
.. _ADR-0023: ../../Docs/adr/0023-unified-gui-stage-workflow.md
"""

from __future__ import annotations

import ctk  # type: ignore[import-not-found]
import qt  # type: ignore[import-not-found]
import slicer  # type: ignore[import-not-found]
import vtk  # type: ignore[import-not-found]

from .ResectogramViewManager import (
    RESECTOGRAM_VIEW_SINGLETON_TAG,
    ResectogramViewManager,
)

# Flattened-quad camera pose + flat background pushed straight onto the
# embedded view's renderer.  The standalone qMRMLThreeDWidget is not managed
# by the layout manager, so it does NOT honour the MRML camera node or the
# view-node background; these are applied at the renderer level (mirroring the
# arena's ``_apply_camera_and_background`` and the proven scenario constants
# in scenarios/Resectogram4x4BlurOff.py).  They frame the FIXED flattened
# (u, v) quad, independent of the resection's patient-space pose.
_RESECTOGRAM_CAMERA_POSITION = (0.0, 60.0, 300.0)
_RESECTOGRAM_CAMERA_FOCAL_POINT = (0.0, 60.0, 0.0)
_RESECTOGRAM_CAMERA_VIEW_UP = (0.0, 1.0, 0.0)
_RESECTOGRAM_CAMERA_PARALLEL_SCALE = 70.0
_RESECTOGRAM_CAMERA_VIEW_ANGLE = 45.0
_RESECTOGRAM_CAMERA_CLIPPING_RANGE = (10.0, 800.0)
# Flat WHITE background for the embedded resectogram renderer (ADR-0023
# §Stage-4): a clean 2D-image panel.  Matches the white the Python
# ResectogramViewManager pushes onto the MRML view node.
_RESECTOGRAM_BACKGROUND_RGB = (1.0, 1.0, 1.0)

_BEZIER_SURFACE_CLASS = "vtkMRMLMarkupsBezierSurfaceNode"
_RESECTOGRAM_DISPLAY_CLASS = "vtkMRMLResectogramDisplayNode"
_VIEW_NODE_CLASS = "vtkMRMLViewNode"

# Minimum embedded-view height so it reads as a square-ish strip panel rather
# than a letterboxed sliver (ADR-0023 §Stage-4 layout).
_EMBEDDED_MIN_HEIGHT_PX = 250


class ResectionPlanningWidget(qt.QWidget):
    """The Stage-4 Resection Planning panel (`ADR-0023`_ §Stage-4).

    Built programmatically (no .ui dependency -- the .ui cannot be cleanly
    loaded from a non-scripted-module Python lib).  Keeps the same objectNames
    as the retired C++ widget for the existing tests + the shell.

    .. _ADR-0023: ../../Docs/adr/0023-unified-gui-stage-workflow.md
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # The active resection surface currently observed for the gating
        # predicate (so computing a distance map re-fires the state update).
        self._activeResectionNode = None
        # The surface currently observed for the resectogram-render hook (its
        # control-point edits repaint the embedded strip).  Distinct from
        # ``_activeResectionNode`` and re-targeted on re-open.
        self._renderObservedNode = None
        # The single embedded view widget bound to the singleton resectogram
        # view node (created once on first open; shown/raised on re-open).
        self._resectogramWidget = None
        # Whether the embedded resectogram widget is currently enlarged into
        # the central layout area.
        self._resectogramEnlarged = False
        # While enlarged, the central viewport the embedded widget was
        # reparented into -- watched for resize so the overlay re-fits.
        self._enlargeHost = None
        # The (surface, hasDistanceMap) the drawer was last populated against
        # -- the render-storm edge-trigger guard.
        self._refreshValid = False
        self._refreshedSurface = None
        self._refreshedHasDistanceMap = False
        # vtkMRMLScene the combo box + embed bind to.
        self._mrmlScene = None
        # The qvtk observer connections, tracked for symmetric removal.
        self._activeNodeObservationTag = None
        self._renderObservationTag = None

        self._setupUi()
        self.refreshResectogramDrawer()

    # ----------------------------------------------------------------------- #
    # Construction.
    # ----------------------------------------------------------------------- #

    def _setupUi(self):
        gridLayout = qt.QGridLayout(self)

        planningButton = ctk.ctkCollapsibleButton()
        planningButton.setObjectName("ResectionPlanningCollapsibleButton")
        planningButton.text = "Resection Planning"
        gridLayout.addWidget(planningButton, 0, 0)

        planningLayout = qt.QGridLayout(planningButton)

        surfaceLabel = qt.QLabel("Resection surface:")
        surfaceLabel.setObjectName("ResectionSurfaceLabel")
        planningLayout.addWidget(surfaceLabel, 0, 0)

        comboBox = slicer.qMRMLNodeComboBox()
        comboBox.setObjectName("ResectionSurfaceComboBox")
        comboBox.nodeTypes = [_BEZIER_SURFACE_CLASS]
        comboBox.noneEnabled = True
        comboBox.addEnabled = False
        comboBox.removeEnabled = False
        comboBox.renameEnabled = True
        planningLayout.addWidget(comboBox, 0, 1)
        self._comboBox = comboBox

        drawer = ctk.ctkCollapsibleButton()
        drawer.setObjectName("ResectogramDrawer")
        drawer.text = "Resectogram"
        planningLayout.addWidget(drawer, 1, 0, 1, 2)
        self._drawer = drawer

        drawerLayout = qt.QGridLayout(drawer)
        hintLabel = qt.QLabel("Select a resection with a computed distance map.")
        hintLabel.setObjectName("ResectogramHintLabel")
        hintLabel.wordWrap = True
        drawerLayout.addWidget(hintLabel, 0, 0)
        self._hintLabel = hintLabel

        comboBox.connect(
            "currentNodeChanged(vtkMRMLNode*)", self.onActiveResectionChanged
        )
        # Expanding the drawer after it auto-populated while collapsed realises
        # the embedded view for the first time; re-render so the strip is
        # visible on expand (the populate-while-collapsed case).
        drawer.connect("contentsCollapsed(bool)", self._onDrawerCollapsed)

    # ----------------------------------------------------------------------- #
    # Public API (the test contract + the shell wiring).
    # ----------------------------------------------------------------------- #

    def setMRMLScene(self, scene):  # noqa: N802 - Slicer/Qt verb convention
        self._mrmlScene = scene
        self._comboBox.setMRMLScene(scene)
        self.refreshResectogramDrawer()

    def mrmlScene(self):  # noqa: N802 - Slicer/Qt verb convention
        return self._mrmlScene

    def resectionSurfaceComboBox(self):  # noqa: N802 - Slicer/Qt verb convention
        return self._comboBox

    def resectogramDrawer(self):  # noqa: N802 - Slicer/Qt verb convention
        return self._drawer

    def resectogramHintLabel(self):  # noqa: N802 - Slicer/Qt verb convention
        return self._hintLabel

    def setActiveResectionNode(self, node):  # noqa: N802 - Slicer/Qt verb convention
        self._comboBox.setCurrentNode(node)

    # ----------------------------------------------------------------------- #
    # Selection -> drawer state.
    # ----------------------------------------------------------------------- #

    def onActiveResectionChanged(self, node):  # noqa: N802 - Slicer/Qt verb convention
        surface = self._asBezierSurface(node)

        # Re-observe the active surface so computing a distance map (which
        # mutates the surface node) re-evaluates the drawer state live -- this
        # is the auto-populate path.
        if self._activeResectionNode is not None and self._activeNodeObservationTag is not None:
            self._activeResectionNode.RemoveObserver(self._activeNodeObservationTag)
        self._activeNodeObservationTag = None
        self._activeResectionNode = surface
        if surface is not None:
            self._activeNodeObservationTag = surface.AddObserver(
                vtk.vtkCommand.ModifiedEvent, self._onActiveResectionModified
            )

        self.refreshResectogramDrawer()

    def _onActiveResectionModified(self, caller, event):
        self.refreshResectogramDrawer()

    def _onDrawerCollapsed(self, collapsed):
        self.scheduleResectogramRender()

    def refreshResectogramDrawer(self):  # noqa: N802 - Slicer/Qt verb convention
        surface = self._asBezierSurface(self._comboBox.currentNode())

        # ADR-0023 §Stage-4 auto-populate predicate: a resectogram is available
        # iff a Bezier surface is selected AND it carries a distance map.
        # State-orthogonal: the predicate does NOT consult the ADR-0019
        # ResectionState.
        hasSurface = surface is not None
        hasDistanceMap = bool(
            hasSurface and surface.GetDistanceMapVolumeNode() is not None
        )
        scene = self._mrmlScene

        # Edge-trigger on the populate-relevant state only.  The active-surface
        # ModifiedEvent observer fires this on EVERY surface modification --
        # including the per-frame re-Modified() a maximize triggers -- but the
        # populate depends only on the selected surface identity + its
        # distance-map presence.  When neither changed, skip the work (a leg of
        # the maximize render storm).  Only short-circuit once a scene is
        # present: a null scene is a transient pre-attach state.
        if (
            scene is not None
            and self._refreshValid
            and surface is self._refreshedSurface
            and hasDistanceMap == self._refreshedHasDistanceMap
        ):
            return
        if scene is not None:
            self._refreshValid = True
            self._refreshedSurface = surface
            self._refreshedHasDistanceMap = hasDistanceMap

        if not hasDistanceMap or scene is None:
            # ADR-0009 §"explainable state": show a hint INSTEAD of an edge-on /
            # blank view, and stop observing any stale surface for render.
            if self._resectogramWidget is not None:
                self._resectogramWidget.hide()
            self.observeSurfaceForRender(None)
            self._hintLabel.text = (
                "Select a resection with a computed distance map."
                if not hasSurface
                else "Compute the distance map for this resection first."
            )
            self._hintLabel.show()
            return

        # Ensure EXACTLY ONE resectogram display node on the surface
        # (idempotent): reuse an existing one, create one only when absent.
        displayNode = self._existingResectogramDisplayNode(surface)
        if displayNode is None:
            displayNode = scene.AddNewNodeByClass(_RESECTOGRAM_DISPLAY_CLASS)
            if displayNode is not None:
                surface.AddAndObserveDisplayNodeID(displayNode.GetID())

        # Ensure the singleton resectogram view node AND present the flattened
        # strip alone in it (display-node + view-node + camera configuration;
        # no custom DisplayableManager, ADR-0013 §5).  Per ADR-0004 the
        # view-manager class is Python and is imported + called DIRECTLY here.
        manager = ResectogramViewManager()
        view = manager.ensureViewNode()
        manager.configureView(view, displayNode, surface)

        # Resolve the just-ensured singleton view node back from the scene by
        # its tag and embed a single qMRMLThreeDWidget bound to it.
        viewNode = scene.GetSingletonNode(
            RESECTOGRAM_VIEW_SINGLETON_TAG, _VIEW_NODE_CLASS
        )
        if viewNode is None:
            return

        # The resectogram is available: hide the explanatory hint and show the
        # view in its place.  showResectogramWidget self-gates on a realized GL
        # context; under --no-main-window the node-ensure + configureView
        # invariants above still ran.
        self._hintLabel.hide()
        self.showResectogramWidget(viewNode)

        # Repaint the embedded strip whenever the selected surface's control
        # points move.
        self.observeSurfaceForRender(surface)

        # Replay the working reactivity path on auto-populate so the strip is
        # visible with NO manual edit.  Defer to the next event-loop turn, once
        # the show/raise has been processed.  Self-gated on a realized GL
        # context: a no-op under --no-main-window.
        qt.QTimer.singleShot(0, self.kickInitialResectogramRender)

    # ----------------------------------------------------------------------- #
    # Embed + framing.
    # ----------------------------------------------------------------------- #

    def kickInitialResectogramRender(self):  # noqa: N802 - Slicer/Qt verb convention
        if self.embeddedThreeDView() is None:
            return

        # Fire the observed surface's Modified() once: this drives the same
        # observer -> UpdatePipeline -> RequestRender path a control-point edit
        # uses, so the Pipeline feeds the flattened-surface geometry on
        # auto-populate rather than waiting for the first manual edit.
        if self._renderObservedNode is not None:
            self._renderObservedNode.Modified()
        self.scheduleResectogramRender()

    def showResectogramWidget(self, viewNode):  # noqa: N802 - Slicer/Qt verb convention
        # Binding the singleton view node to the embedded qMRMLThreeDWidget
        # (setMRMLViewNode) synchronously attaches the LayerDM displayable
        # manager, which uploads the distance-map 3D texture.  That upload
        # needs a REALIZED GL context: under --no-main-window it would
        # hard-crash, so skip the embed there.  The display-node + view-node
        # ensure (the headless invariants) already ran in
        # refreshResectogramDrawer before this call.
        if not self._hasRealizedGLContext():
            return

        # Expand the drawer BEFORE the embedded view is shown/bound.  A widget
        # only realizes its GL context once it is actually MAPPED; a child of a
        # collapsed ctkCollapsibleButton is never mapped, so the distance-map
        # 3D texture upload at setMRMLViewNode lands in an unrealized context.
        if self._drawer.collapsed:
            self._drawer.collapsed = False

        if self._resectogramWidget is None:
            widget = slicer.qMRMLThreeDWidget(self)
            widget.setObjectName("ResectogramThreeDWidget")
            controller = widget.threeDController()
            if controller is not None:
                controller.hide()
            # Fill the drawer rather than sit left-aligned + letterboxed: an
            # Expanding size policy in both axes lets the embedded view claim
            # the drawer width; a non-trivial minimum height makes it read as a
            # square-ish strip panel (ADR-0023 §Stage-4 layout).
            widget.setSizePolicy(qt.QSizePolicy.Expanding, qt.QSizePolicy.Expanding)
            widget.minimumHeight = _EMBEDDED_MIN_HEIGHT_PX
            self._resectogramWidget = widget

            # Place it inside the resectogram drawer, below the hint label
            # (row 1 of the drawer grid), so it fills the drawer width and
            # claims its stretch.
            grid = self._drawer.layout()
            if isinstance(grid, qt.QGridLayout):
                grid.addWidget(widget, 1, 0)
                grid.setRowStretch(1, 1)
            elif grid is not None:
                grid.addWidget(widget)
            widget.setMRMLScene(self._mrmlScene)

            # Realize the GL surface BEFORE binding the view node.  show() maps
            # the now-parented widget inside the expanded drawer, and
            # forceRender() pumps a frame so the OpenGL context is genuinely
            # current; only then does setMRMLViewNode attach the LayerDM
            # displayable manager and upload the distance-map 3D texture INTO a
            # realized context.
            widget.show()
            widget.threeDView().forceRender()
            widget.setMRMLViewNode(viewNode)

            # The embedded view is a FIXED flattened (u, v) image under
            # parallel projection; orbiting or maximizing it is incorrect.
            # Lock both out at the camera widget the view's camera displayable
            # manager already hosts -- a config-only change (no custom
            # DisplayableManager, ADR-0013 §5).
            self.lockEmbeddedViewInteraction()

            # Capture a double-click on the embedded view to toggle the CUSTOM
            # enlarge / restore.  The event filter sits on the GL view widget
            # itself, so it sees the double-click before the view forwards it
            # to VTK -- consuming it there suppresses Slicer's built-in
            # maximize.
            view = widget.threeDView()
            if view is not None:
                view.installEventFilter(self)
        else:
            # Re-open: keep ONE widget; re-target the (singleton) view node and
            # the current scene defensively.
            self._resectogramWidget.setMRMLScene(self._mrmlScene)
            self._resectogramWidget.setMRMLViewNode(viewNode)

        self._resectogramWidget.show()
        self._resectogramWidget.raise_()

        # The standalone embedded view is not managed by the layout manager, so
        # it ignores the MRML camera node + view-node background the Python
        # configureView set.  Push the flattened-quad pose + flat background
        # onto the renderer directly, then repaint.
        self.poseEmbeddedRenderer()

    def embeddedThreeDView(self):  # noqa: N802 - Slicer/Qt verb convention
        if self._resectogramWidget is None or not self._hasRealizedGLContext():
            return None
        return self._resectogramWidget.threeDView()

    def poseEmbeddedRenderer(self):  # noqa: N802 - Slicer/Qt verb convention
        view = self.embeddedThreeDView()
        if view is None:
            return
        renderer = view.renderer()
        if renderer is None:
            return

        # Camera pose onto the renderer's ACTIVE camera (not the MRML camera
        # node, which the standalone view ignores).  Parallel projection
        # framing the fixed flattened (u, v) quad.
        camera = renderer.GetActiveCamera()
        if camera is not None:
            camera.SetPosition(*_RESECTOGRAM_CAMERA_POSITION)
            camera.SetFocalPoint(*_RESECTOGRAM_CAMERA_FOCAL_POINT)
            camera.SetViewUp(*_RESECTOGRAM_CAMERA_VIEW_UP)
            camera.ParallelProjectionOn()
            camera.SetParallelScale(_RESECTOGRAM_CAMERA_PARALLEL_SCALE)
            camera.SetViewAngle(_RESECTOGRAM_CAMERA_VIEW_ANGLE)
            camera.SetClippingRange(*_RESECTOGRAM_CAMERA_CLIPPING_RANGE)

        # Flat background onto the renderer (the blue gradient is the default
        # 3D background the standalone view keeps unless overridden here).
        renderer.SetBackground(*_RESECTOGRAM_BACKGROUND_RGB)
        renderer.SetBackground2(*_RESECTOGRAM_BACKGROUND_RGB)

        view.forceRender()

    def lockEmbeddedViewInteraction(self):  # noqa: N802 - Slicer/Qt verb convention
        view = self.embeddedThreeDView()
        if view is None:
            return

        # The camera widget hosted by the view's camera displayable manager
        # owns the trackball-rotate event translations.  Remap exactly those to
        # WidgetEventNone so the flat panel cannot be orbited, while pan / zoom
        # stay untouched.  The double-click is handled by this widget's event
        # filter (the custom enlarge/restore).  No custom DisplayableManager
        # (ADR-0013 §5): this is a per-view config of the upstream camera
        # widget.
        cameraDM = view.displayableManagerByClassName(
            "vtkMRMLCameraDisplayableManager"
        )
        if cameraDM is None:
            return
        cameraWidget = cameraDM.GetCameraWidget()
        if cameraWidget is None:
            return

        # No 3D rotation.  Drop the left-button rotate-start translations (the
        # bare drag and the markup-placement Alt variant) and the Ctrl-drag
        # spin so a flat 2D panel cannot be orbited.  Pan (Shift / middle drag)
        # and zoom (right drag, Ctrl + Shift drag, mouse wheel) are left intact.
        # The double-click is NOT remapped here: this widget's event filter
        # consumes it at the Qt level (before VTK) to drive the custom
        # enlarge/restore (ADR-0023 §Stage-4).
        idle = cameraWidget.WidgetStateIdle
        none = cameraWidget.WidgetEventNone
        leftPress = vtk.vtkCommand.LeftButtonPressEvent
        cameraWidget.SetEventTranslation(idle, leftPress, vtk.vtkEvent.NoModifier, none)
        cameraWidget.SetEventTranslation(idle, leftPress, vtk.vtkEvent.AltModifier, none)
        cameraWidget.SetEventTranslation(
            idle, leftPress, vtk.vtkEvent.ControlModifier, none
        )

    # ----------------------------------------------------------------------- #
    # Reactivity.
    # ----------------------------------------------------------------------- #

    def observeSurfaceForRender(self, surface):  # noqa: N802 - Slicer/Qt verb convention
        if self._renderObservedNode is surface:
            return

        # Symmetric removal of the prior observer before re-targeting, so a
        # stale surface never repaints the strip.
        if self._renderObservedNode is not None and self._renderObservationTag is not None:
            self._renderObservedNode.RemoveObserver(self._renderObservationTag)
        self._renderObservationTag = None

        self._renderObservedNode = surface
        if surface is not None:
            # Render on the control-point-edit signal ONLY
            # (PointModifiedEvent), NOT the generic ModifiedEvent.  A maximize
            # binds the resectogram view node to two live qMRMLThreeDViews
            # whose renders re-Modified() the surface every frame; a
            # generic-ModifiedEvent->forceRender observer would re-fire a render
            # on each of those render-induced Modifies -- a feedback loop (the
            # maximize render storm).  PointModifiedEvent is the real
            # control-point-edit signal a render does not raise.
            self._renderObservationTag = surface.AddObserver(
                slicer.vtkMRMLMarkupsNode.PointModifiedEvent,
                self._onObservedSurfacePointModified,
            )

    def _onObservedSurfacePointModified(self, caller, event):
        self.scheduleResectogramRender()

    def scheduleResectogramRender(self):  # noqa: N802 - Slicer/Qt verb convention
        # Same realized-GL-context requirement as the embed: forcing a render
        # drives the distance-map texture upload; no live view to repaint
        # without one.
        view = self.embeddedThreeDView()
        if view is not None:
            view.forceRender()

    # ----------------------------------------------------------------------- #
    # Custom enlarge.
    # ----------------------------------------------------------------------- #

    def eventFilter(self, watched, event):  # noqa: N802 - Qt override
        # A LEFT double-click on the embedded view toggles the custom enlarge.
        # Sit on the GL view widget so we see the event before it forwards to
        # the VTK interactor; consuming it suppresses Slicer's built-in
        # maximize.
        if (
            event is not None
            and event.type() == qt.QEvent.MouseButtonDblClick
            and self._resectogramWidget is not None
            and watched is self._resectogramWidget.threeDView()
        ):
            if event.button() == qt.Qt.LeftButton:
                self.toggleResectogramEnlarged()
                return True  # consumed: no built-in maximize

        # Keep the enlarged overlay fitted to the central viewport as it
        # resizes (the overlay is a raw child, not in the viewport's layout, so
        # Qt does not resize it for us).
        if (
            event is not None
            and event.type() == qt.QEvent.Resize
            and self._resectogramEnlarged
            and self._resectogramWidget is not None
            and self._enlargeHost is not None
            and watched is self._enlargeHost
        ):
            self._resectogramWidget.setGeometry(self._enlargeHost.rect)

        return super().eventFilter(watched, event)

    def isResectogramEnlarged(self):  # noqa: N802 - Slicer/Qt verb convention
        return self._resectogramEnlarged

    def toggleResectogramEnlarged(self):  # noqa: N802 - Slicer/Qt verb convention
        if self._resectogramEnlarged:
            self.restoreResectogram()
        else:
            self.enlargeResectogram()

    def enlargeResectogram(self):  # noqa: N802 - Slicer/Qt verb convention
        if self._resectogramWidget is None or self._resectogramEnlarged:
            return

        # Reparent the ONE embedded widget into the layout manager's central
        # viewport.  Built-in maximize is unusable (it realises a blank SECOND
        # widget on the singleton view node whose LayerDM pipeline never
        # populates the strip); reparenting the working widget WITHIN the main
        # window preserves its GL context + distance-map texture.
        layoutManager = slicer.app.layoutManager()
        viewport = layoutManager.viewport() if layoutManager is not None else None
        if viewport is None:
            return

        self._resectogramWidget.setParent(viewport)
        self._resectogramWidget.setGeometry(viewport.rect)
        self._resectogramWidget.show()
        self._resectogramWidget.raise_()

        # Track the viewport for resize-refit + later removal.
        self._enlargeHost = viewport
        viewport.installEventFilter(self)

        self._resectogramEnlarged = True

        # The renderer (camera pose + white background) survives the reparent;
        # pump a frame so the enlarged surface paints immediately.
        view = self._resectogramWidget.threeDView()
        if view is not None:
            view.forceRender()

    def restoreResectogram(self):  # noqa: N802 - Slicer/Qt verb convention
        if self._resectogramWidget is None or not self._resectogramEnlarged:
            return

        # Stop watching the central viewport for resize.
        if self._enlargeHost is not None:
            self._enlargeHost.removeEventFilter(self)
            self._enlargeHost = None

        # Re-home the widget into the drawer grid at (1, 0) -- addWidget
        # reparents it back under the drawer.
        grid = self._drawer.layout()
        if isinstance(grid, qt.QGridLayout):
            grid.addWidget(self._resectogramWidget, 1, 0)
            grid.setRowStretch(1, 1)
        else:
            self._resectogramWidget.setParent(self._drawer)
        self._resectogramWidget.show()

        self._resectogramEnlarged = False

        view = self._resectogramWidget.threeDView()
        if view is not None:
            view.forceRender()

    # ----------------------------------------------------------------------- #
    # Helpers.
    # ----------------------------------------------------------------------- #

    @staticmethod
    def _asBezierSurface(node):
        """Return ``node`` if it is a Bezier surface node, else ``None``."""
        if node is not None and node.IsA(_BEZIER_SURFACE_CLASS):
            return node
        return None

    @staticmethod
    def _existingResectogramDisplayNode(surface):
        """Return the surface's resectogram display node, or ``None``."""
        for index in range(surface.GetNumberOfDisplayNodes()):
            candidate = surface.GetNthDisplayNode(index)
            if candidate is not None and candidate.IsA(_RESECTOGRAM_DISPLAY_CLASS):
                return candidate
        return None

    @staticmethod
    def _hasRealizedGLContext():
        # Mirror the C++ ``hasRealizedGLContext`` (a shown main window backs a
        # realized GL context).  ``slicer.util.mainWindow()`` returns ``None``
        # cleanly under ``--no-main-window`` (the qSlicerApplication accessor
        # raises there instead), so use the util shim the launched harness
        # itself uses.
        return slicer.util.mainWindow() is not None

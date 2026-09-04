# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Stage-4 "Resection Planning" panel (`ADR-0023`_ §Stage-4, `ADR-0004`_).

The panel that selects the active resection surface and auto-populates the
embedded resectogram view.  Per `ADR-0004`_ the GUI lives in Python: this
widget imports the (correctly-Python) ``ResectogramViewManager`` and calls
its wrapped C++ nodes/logic directly -- no ``executeString`` string bridge.

The behaviour mirrors the retired C++ ``qSlicerLiverResectionsModuleWidget``
faithfully:

* AUTO-POPULATE.  Selecting a ``vtkMRMLResectionPlanNode`` WRAPPER whose
  distance map is set (``GetDistanceMapVolumeNode``, on the wrapper per
  `ADR-0031`_) ensures EXACTLY ONE ``vtkMRMLResectogramDisplayNode`` on the
  wrapper's CARRIER (``GetGeometryNode()``, a ``vtkMRMLBezierSurfaceNode``,
  `ADR-0014`_ §"Fourth layer"), runs ``ResectogramViewManager.configureView``,
  embeds a single ``qMRMLThreeDWidget`` bound to the singleton view node, and
  hides the hint.  Otherwise the hint is shown with the appropriate explanatory
  text.  Edge-triggered on ``(plan identity, hasDistanceMap)`` to avoid the
  render-storm re-populate.  A "Place resection" button mints a fresh plan
  graph via the logic create-API (`ADR-0032`_) and selects it.
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
* REACTIVITY.  The carrier is observed for ``ModifiedEvent`` (its only
  control-point-edit signal -- it is not a markups node) to force a render of
  the embedded view; a deferred initial-render kick shows the strip on
  auto-populate without an edit.  The v1 storm-free variant (markups
  ``PointModifiedEvent``) has no carrier equivalent; the storm-free guard is a
  GL-coupled concern verified on the interactive ``:0`` probe (`ADR-0032`_).
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
* `ADR-0014`_ §"Fourth layer" -- the wrapper/carrier split.
* `ADR-0031`_ -- the distance map lives on the resection-plan wrapper.
* `ADR-0032`_ -- v2 interaction + the logic create-API for placement.

.. _ADR-0004: ../../Docs/adr/0004-python-cpp-boundary.md
.. _ADR-0009: ../../Docs/adr/0009-ux-and-design-discipline.md
.. _ADR-0013: ../../Docs/adr/0013-layerdm-pipeline-pattern.md
.. _ADR-0014: ../../Docs/adr/0014-livermarkups-dissolution.md
.. _ADR-0023: ../../Docs/adr/0023-unified-gui-stage-workflow.md
.. _ADR-0031: ../../Docs/adr/0031-distance-map-input-on-resection-plan.md
.. _ADR-0032: ../../Docs/adr/0032-v2-interaction-via-layerdm-pipeline-seam.md
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
# (u, v) quad, independent of the resection's patient-space pose.  The camera
# looks straight down -Z at the flattened quad (which lies in the Z=0 plane)
# with +Y up; the position/focal are only a DIRECTION seed -- ResetCamera()
# repositions + sets the parallel scale to FIT the quad to whatever viewport
# the strip currently occupies (drawer or enlarged central area), so the strip
# fills the view rather than sitting at a fixed scale with wide margins.
_RESECTOGRAM_CAMERA_POSITION = (0.0, 0.0, 1.0)
_RESECTOGRAM_CAMERA_FOCAL_POINT = (0.0, 0.0, 0.0)
_RESECTOGRAM_CAMERA_VIEW_UP = (0.0, 1.0, 0.0)
# Fill factor applied after ResetCamera: ResetCamera fits the quad's bounding
# SPHERE (leaving the square quad with diagonal-vs-side slack), so zoom in past
# the fit to make the quad occupy as much of the view as possible.  Tuned by
# eyeball; <1.42 (the square half-diagonal/half-side ratio) keeps the quad's
# (u, v) border fully visible.
_RESECTOGRAM_CAMERA_FILL_ZOOM = 1.35
# Flat WHITE background for the embedded resectogram renderer (ADR-0023
# §Stage-4): a clean 2D-image panel.  Matches the white the Python
# ResectogramViewManager pushes onto the MRML view node.
_RESECTOGRAM_BACKGROUND_RGB = (1.0, 1.0, 1.0)

# The Stage-4 combo selects the v2 resection-plan WRAPPER (ADR-0014 §"Fourth
# layer").  The distance map is read off the wrapper (ADR-0031); the resectogram
# display node + the render observation land on the wrapper's CARRIER
# (``GetGeometryNode()``, a ``vtkMRMLBezierSurfaceNode``).
_RESECTION_PLAN_CLASS = "vtkMRMLResectionPlanNode"
_BEZIER_CARRIER_CLASS = "vtkMRMLBezierSurfaceNode"
_RESECTOGRAM_DISPLAY_CLASS = "vtkMRMLResectogramDisplayNode"
_SURFACE_DISPLAY_CLASS = "vtkMRMLParametricSurfaceDisplayNode"
_VIEW_NODE_CLASS = "vtkMRMLViewNode"
# The logic module whose create-API (``CreateResectionPlan``) the Place button
# calls to mint a fresh plan + carrier + display triad (ADR-0032).
_LOGIC_MODULE_NAME = "liverresections"
_DEFAULT_RESECTION_NAME = "Resection"

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
        # The click-to-reslice consumer (ADR-0025 §Click-to-reslice): a plain
        # Python observer (ADR-0013 §5 -- not a Pipeline/DM) that watches the
        # scene's single vtkMRMLLocatorNode and reslices the orthogonal slice to
        # the picked point.  This widget owns its lifetime.
        self._locatorReslicer = None
        # The single long-lived view manager for the dedicated resectogram
        # view.  ONE instance per widget: the manager attaches the default-deny
        # scene + slice-display observers, so a fresh manager per drawer
        # refresh would stack a new observer set on every re-open.  This
        # widget owns its lifetime (detached in cleanup()).
        self._resectogramViewManager = None

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
        comboBox.nodeTypes = [_RESECTION_PLAN_CLASS]
        comboBox.noneEnabled = True
        comboBox.addEnabled = False
        comboBox.removeEnabled = False
        comboBox.renameEnabled = True
        planningLayout.addWidget(comboBox, 0, 1)
        self._comboBox = comboBox

        # "Place resection" mints a fresh v2 plan graph (wrapper + carrier +
        # display) via the logic create-API and selects it (ADR-0032; ADR-0019
        # starts the plan in Init so the placement step seeds the grid).
        placeButton = qt.QPushButton("Place resection")
        placeButton.setObjectName("PlaceResectionButton")
        planningLayout.addWidget(placeButton, 1, 0, 1, 2)
        self._placeButton = placeButton
        placeButton.connect("clicked()", self.onPlaceResection)

        # Margin inputs (ADR-0023 §Stage-4): the plan wrapper's Safety / Risk
        # scalars (millimetres, ADR-0031) plus the display node's
        # InterpolatedMargins band-style flag.  Disabled until the selected
        # plan carries a distance map -- the same gate as the drawer, since
        # without the map the shader has no band to draw.  Computed READOUTS
        # (achieved margins, volumes) stay in Stage 5; these are inputs.
        marginsGroup = ctk.ctkCollapsibleGroupBox()
        marginsGroup.setObjectName("ResectionMarginsGroupBox")
        marginsGroup.title = "Resection margins"
        marginsGroup.enabled = False
        planningLayout.addWidget(marginsGroup, 2, 0, 1, 2)
        self._marginsGroup = marginsGroup

        marginsForm = qt.QFormLayout(marginsGroup)

        safetySpinBox = slicer.qMRMLSpinBox()
        safetySpinBox.setObjectName("SafetyMarginSpinBox")
        safetySpinBox.quantity = "millimeters"
        safetySpinBox.minimum = 0.0
        safetySpinBox.maximum = 100.0
        safetySpinBox.singleStep = 1.0
        marginsForm.addRow("Safety margin:", safetySpinBox)
        self._safetyMarginSpinBox = safetySpinBox

        riskSpinBox = slicer.qMRMLSpinBox()
        riskSpinBox.setObjectName("RiskMarginSpinBox")
        riskSpinBox.quantity = "millimeters"
        riskSpinBox.minimum = 0.0
        riskSpinBox.maximum = 100.0
        riskSpinBox.singleStep = 0.5
        marginsForm.addRow("Risk margin (±):", riskSpinBox)
        self._riskMarginSpinBox = riskSpinBox

        totalMarginLabel = qt.QLabel("0.00 mm")
        totalMarginLabel.setObjectName("TotalMarginLabel")
        marginsForm.addRow("Total margin:", totalMarginLabel)
        self._totalMarginLabel = totalMarginLabel

        interpolatedCheckBox = qt.QCheckBox("Interpolated margins")
        interpolatedCheckBox.setObjectName("InterpolatedMarginsCheckBox")
        marginsForm.addRow(interpolatedCheckBox)
        self._interpolatedMarginsCheckBox = interpolatedCheckBox

        safetySpinBox.connect("valueChanged(double)", self.onSafetyMarginChanged)
        riskSpinBox.connect("valueChanged(double)", self.onRiskMarginChanged)
        interpolatedCheckBox.connect(
            "toggled(bool)", self.onInterpolatedMarginsToggled
        )

        drawer = ctk.ctkCollapsibleButton()
        drawer.setObjectName("ResectogramDrawer")
        drawer.text = "Resectogram"
        planningLayout.addWidget(drawer, 3, 0, 1, 2)
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
        # The margin spinboxes need the scene for the unit framework (the mm
        # suffix comes from the scene's unit nodes).
        self._safetyMarginSpinBox.setMRMLScene(scene)
        self._riskMarginSpinBox.setMRMLScene(scene)
        self._updateLocatorReslicer(scene)
        self.refreshResectogramDrawer()

    def _updateLocatorReslicer(self, scene):  # noqa: N802 - internal
        """Own the click-to-reslice consumer's lifetime (ADR-0025 §Click-to-reslice).

        Rebuilds the ``LocatorReslicer`` against the current scene (tearing down
        any prior one) and drops it on a null scene.  The reslicer resolves the
        single locator at construction; ``refreshResectogramDrawer`` re-resolves
        it later so a locator created after the widget still gets observed.
        """
        if self._locatorReslicer is not None:
            self._locatorReslicer.cleanup()
            self._locatorReslicer = None
        if scene is None:
            return
        try:
            from LiverResectionsLib.LocatorReslicer import LocatorReslicer
        except Exception:  # pragma: no cover - surfaces only when the lib is absent
            return
        self._locatorReslicer = LocatorReslicer(scene)

    def mrmlScene(self):  # noqa: N802 - Slicer/Qt verb convention
        return self._mrmlScene

    def resectionSurfaceComboBox(self):  # noqa: N802 - Slicer/Qt verb convention
        return self._comboBox

    def resectogramDrawer(self):  # noqa: N802 - Slicer/Qt verb convention
        return self._drawer

    def resectogramHintLabel(self):  # noqa: N802 - Slicer/Qt verb convention
        return self._hintLabel

    def marginsGroupBox(self):  # noqa: N802 - Slicer/Qt verb convention
        return self._marginsGroup

    def safetyMarginSpinBox(self):  # noqa: N802 - Slicer/Qt verb convention
        return self._safetyMarginSpinBox

    def riskMarginSpinBox(self):  # noqa: N802 - Slicer/Qt verb convention
        return self._riskMarginSpinBox

    def totalMarginLabel(self):  # noqa: N802 - Slicer/Qt verb convention
        return self._totalMarginLabel

    def interpolatedMarginsCheckBox(self):  # noqa: N802 - Slicer/Qt verb convention
        return self._interpolatedMarginsCheckBox

    def placeResectionButton(self):  # noqa: N802 - Slicer/Qt verb convention
        return self._placeButton

    def setActiveResectionNode(self, node):  # noqa: N802 - Slicer/Qt verb convention
        self._comboBox.setCurrentNode(node)

    def onPlaceResection(self):  # noqa: N802 - Slicer/Qt verb convention
        """Mint a fresh v2 resection plan graph and select it.

        Delegates to the logic create-API (``CreateResectionPlan``), which mints
        the wrapper + carrier + carrier display triad and wires the geometry
        reference (ADR-0032; ADR-0014 §"Fourth layer").  The fresh plan starts in
        Init (ADR-0019); the placement step seeds the control grid.  Selecting it
        drives the combo -> ``onActiveResectionChanged`` -> drawer path.
        """
        logic = self._resectionLogic()
        if logic is None or not hasattr(logic, "CreateResectionPlan"):
            return
        # HARD GATE (v1 parity + ADR-0009 explainable state): without an
        # Accepted liver there is no target mesh, no auto-seed, and no
        # contour -- refuse to mint a dead origin-grid resection and name
        # the missing Stage-2 hand-off instead.
        from LiverResectionsLib.TargetModel import (
            ensure_target_model,
            has_canonical_liver,
        )

        if not has_canonical_liver():
            self._hintLabel.setText(
                "Accept a liver segmentation in Anatomy (Stage 2) first."
            )
            self._hintLabel.show()
            return
        plan = logic.CreateResectionPlan(_DEFAULT_RESECTION_NAME)
        if plan is not None:
            # Attach the hidden liver target model (ADR-0014 §1 weakref):
            # the slicing-plane init contour and the commit-boundary ring
            # extraction cut THIS mesh.
            ensure_target_model(plan)
            self.setActiveResectionNode(plan)

    @staticmethod
    def _resectionLogic():
        """Return the LiverResections module logic singleton, or ``None``."""
        module = getattr(slicer.modules, _LOGIC_MODULE_NAME, None)
        if module is None:
            return None
        return module.logic()

    # ----------------------------------------------------------------------- #
    # Selection -> drawer state.
    # ----------------------------------------------------------------------- #

    def onActiveResectionChanged(self, node):  # noqa: N802 - Slicer/Qt verb convention
        plan = self._asResectionPlan(node)

        # Re-observe the active plan WRAPPER so attaching a distance map (which
        # mutates the wrapper, ADR-0031) re-evaluates the drawer state live --
        # this is the auto-populate path.
        if self._activeResectionNode is not None and self._activeNodeObservationTag is not None:
            self._activeResectionNode.RemoveObserver(self._activeNodeObservationTag)
        self._activeNodeObservationTag = None
        self._activeResectionNode = plan
        if plan is not None:
            self._activeNodeObservationTag = plan.AddObserver(
                vtk.vtkCommand.ModifiedEvent, self._onActiveResectionModified
            )

        self.refreshResectogramDrawer()

    def _onActiveResectionModified(self, caller, event):
        self.refreshResectogramDrawer()

    # ----------------------------------------------------------------------- #
    # Margin controls (ADR-0023 §Stage-4; scalars on the plan wrapper per
    # ADR-0031, InterpolatedMargins on the carrier's parametric display node).
    # The slices' pipeline observers make every write repaint both views, so
    # these slots only author MRML state -- no render plumbing here.
    # ----------------------------------------------------------------------- #

    def onSafetyMarginChanged(self, value):  # noqa: N802 - Slicer/Qt verb convention
        plan = self._activeResectionNode
        if plan is None:
            return
        plan.SetSafetyMargin(float(value))
        self._updateTotalMarginLabel()

    def onRiskMarginChanged(self, value):  # noqa: N802 - Slicer/Qt verb convention
        plan = self._activeResectionNode
        if plan is None:
            return
        plan.SetRiskMargin(float(value))
        # v1 floor-clamp: safety >= risk keeps the shader's
        # ``lowMargin = safety - risk`` non-negative.  Raising the minimum can
        # clamp the safety value, whose valueChanged then writes the plan --
        # deliberately, so the visible value and the node never diverge.
        self._safetyMarginSpinBox.minimum = float(value)
        self._updateTotalMarginLabel()

    def onInterpolatedMarginsToggled(self, checked):  # noqa: N802 - Slicer/Qt verb convention
        plan = self._activeResectionNode
        carrier = plan.GetGeometryNode() if plan is not None else None
        display = self._parametricSurfaceDisplayNode(carrier)
        if display is not None:
            display.SetInterpolatedMargins(bool(checked))

    def _updateTotalMarginLabel(self):
        plan = self._activeResectionNode
        total = (
            plan.GetSafetyMargin() + plan.GetRiskMargin()
            if plan is not None
            else 0.0
        )
        self._totalMarginLabel.text = f"{total:.2f} mm"

    def _syncMarginControls(self, plan, hasDistanceMap):  # noqa: N802 - internal
        """Pull the selected plan's margin state into the controls.

        blockSignals discipline: the sync must never echo a write back onto
        the node (an external / scripted margin edit routes here through the
        active-plan observer, and a write-back would ping-pong).  Cheap and
        idempotent, so it runs on every drawer refresh -- including the
        edge-trigger-short-circuited ones, which is exactly what keeps the
        controls current when only the margins changed.
        """
        controls = (
            self._safetyMarginSpinBox,
            self._riskMarginSpinBox,
            self._interpolatedMarginsCheckBox,
        )
        for control in controls:
            control.blockSignals(True)
        try:
            if plan is not None:
                # Floor before value, so the value never clamps spuriously.
                self._safetyMarginSpinBox.minimum = plan.GetRiskMargin()
                self._safetyMarginSpinBox.setValue(plan.GetSafetyMargin())
                self._riskMarginSpinBox.setValue(plan.GetRiskMargin())
            display = self._parametricSurfaceDisplayNode(
                plan.GetGeometryNode() if plan is not None else None
            )
            if display is not None:
                self._interpolatedMarginsCheckBox.setChecked(
                    bool(display.GetInterpolatedMargins())
                )
        finally:
            for control in controls:
                control.blockSignals(False)
        self._marginsGroup.enabled = bool(hasDistanceMap)
        self._updateTotalMarginLabel()

    def _onDrawerCollapsed(self, collapsed):
        self.scheduleResectogramRender()

    def refreshResectogramDrawer(self):  # noqa: N802 - Slicer/Qt verb convention
        # Re-resolve the locator the click-to-reslice consumer observes BEFORE
        # the distance-map guards below (a locator minted after the widget --
        # e.g. by CreateResectionPlan on Place -- must get observed regardless of
        # whether the resectogram is drawable yet).
        if self._locatorReslicer is not None:
            self._locatorReslicer.refresh()

        plan = self._asResectionPlan(self._comboBox.currentNode())
        # The strip actors, the resectogram display node, and the render
        # observation all live on the plan's CARRIER (ADR-0014 §"Fourth layer");
        # the distance map is read off the WRAPPER (ADR-0031).
        carrier = plan.GetGeometryNode() if plan is not None else None

        # ADR-0023 §Stage-4 auto-populate predicate: a resectogram is available
        # iff a resection PLAN is selected AND its WRAPPER carries a distance map
        # (ADR-0031).  State-orthogonal: the predicate does NOT consult the
        # ADR-0019 ResectionState.
        hasPlan = plan is not None
        hasDistanceMap = bool(
            hasPlan and carrier is not None and plan.GetDistanceMapVolumeNode() is not None
        )
        scene = self._mrmlScene

        # Margin controls sync BEFORE the edge-trigger short-circuit below:
        # a margin-only edit (spinbox, script, undo) changes neither the plan
        # identity nor the distance-map presence, yet the controls + total
        # label must still track it.
        self._syncMarginControls(plan, hasDistanceMap)

        # Edge-trigger on the populate-relevant state only.  The active-plan
        # ModifiedEvent observer fires this on EVERY wrapper modification --
        # including the per-frame re-Modified() a maximize triggers -- but the
        # populate depends only on the selected plan identity + its distance-map
        # presence.  When neither changed, skip the work (a leg of the maximize
        # render storm).  Only short-circuit once a scene is present: a null
        # scene is a transient pre-attach state.
        if (
            scene is not None
            and self._refreshValid
            and plan is self._refreshedSurface
            and hasDistanceMap == self._refreshedHasDistanceMap
        ):
            return
        if scene is not None:
            self._refreshValid = True
            self._refreshedSurface = plan
            self._refreshedHasDistanceMap = hasDistanceMap

        if not hasDistanceMap or scene is None:
            # ADR-0009 §"explainable state": show a hint INSTEAD of an edge-on /
            # blank view, and stop observing any stale carrier for render.
            if self._resectogramWidget is not None:
                self._resectogramWidget.hide()
            self.observeSurfaceForRender(None)
            self._hintLabel.text = (
                "Select a resection with a computed distance map."
                if not hasPlan
                else "Compute the distance map for this resection first."
            )
            self._hintLabel.show()
            return

        # Ensure EXACTLY ONE resectogram display node on the CARRIER
        # (idempotent, ADR-0014 §"Fourth layer"): reuse an existing one, create
        # one only when absent.
        displayNode = self._existingResectogramDisplayNode(carrier)
        if displayNode is None:
            displayNode = scene.AddNewNodeByClass(_RESECTOGRAM_DISPLAY_CLASS)
            if displayNode is not None:
                carrier.AddAndObserveDisplayNodeID(displayNode.GetID())

        # Ensure the singleton resectogram view node AND present the flattened
        # strip alone in it (display-node + view-node + camera configuration;
        # no custom DisplayableManager, ADR-0013 §5).  Per ADR-0004 the
        # view-manager class is Python and is imported + called DIRECTLY here.
        if self._resectogramViewManager is None:
            self._resectogramViewManager = ResectogramViewManager()
        manager = self._resectogramViewManager
        view = manager.ensureViewNode()
        manager.configureView(view, displayNode, carrier)

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

        # Repaint the embedded strip whenever the carrier's control points move.
        self.observeSurfaceForRender(carrier)

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
        # qMRMLThreeDView does not expose a ``renderer()`` accessor to Python
        # (unlike the C++ class), so resolve the main (layer-0) renderer through
        # the render window -- the camera pose + flat background must land on the
        # renderer the strip actors live in, or the fixed (u, v) quad renders
        # off-frame and the panel shows only the background.
        renderer = None
        renderWindow = view.renderWindow()
        renderers = renderWindow.GetRenderers() if renderWindow is not None else None
        if renderers is not None:
            renderers.InitTraversal()
            for _ in range(renderers.GetNumberOfItems()):
                candidate = renderers.GetNextItem()
                if candidate is not None and candidate.GetLayer() == 0:
                    renderer = candidate
                    break
        if renderer is None:
            return

        # Camera pose onto the renderer's ACTIVE camera (not the MRML camera
        # node, which the standalone view ignores).  Seed the head-on -Z view
        # direction + parallel projection, then ResetCamera() to FIT the
        # flattened (u, v) quad to the CURRENT viewport -- so the strip fills the
        # view in whichever it participates (drawer or enlarged central area),
        # not a fixed scale with wide margins.  ResetCamera fits visible-prop
        # bounds: the anatomy is isolated (vis=0) so only the strip is fitted.
        camera = renderer.GetActiveCamera()
        if camera is not None:
            camera.SetFocalPoint(*_RESECTOGRAM_CAMERA_FOCAL_POINT)
            camera.SetPosition(*_RESECTOGRAM_CAMERA_POSITION)
            camera.SetViewUp(*_RESECTOGRAM_CAMERA_VIEW_UP)
            camera.ParallelProjectionOn()
            renderer.ResetCamera()
            # Zoom past the bounding-sphere fit so the quad maximally occupies
            # the view (pan/zoom remain available to the user from here).
            camera.Zoom(_RESECTOGRAM_CAMERA_FILL_ZOOM)

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
        # stale carrier never repaints the strip.
        if self._renderObservedNode is not None and self._renderObservationTag is not None:
            self._renderObservedNode.RemoveObserver(self._renderObservationTag)
        self._renderObservationTag = None

        self._renderObservedNode = surface
        if surface is not None:
            # The v2 carrier (vtkMRMLBezierSurfaceNode) is not a markups node and
            # fires only the generic ModifiedEvent on a control-point edit, so
            # observe that.  The v1 storm-free path hooked the markups
            # PointModifiedEvent to dodge the maximize feedback loop (a render
            # re-Modified() the surface every frame); the equivalent storm-free
            # guard on the carrier's ModifiedEvent is a GL-coupled concern
            # verified on the interactive :0 probe (ADR-0032 §Conformance), not
            # this headless path.
            self._renderObservationTag = surface.AddObserver(
                vtk.vtkCommand.ModifiedEvent,
                self._onObservedSurfacePointModified,
            )

    def _onObservedSurfacePointModified(self, caller, event):
        self.scheduleResectogramRender()

    def showEvent(self, event):  # noqa: N802 - Qt override
        # Re-entering the module re-shows this panel with the embedded GL
        # view's last frame discarded -- the strip reads BLACK until the
        # next render request.  Kick one after the show has been processed
        # (same one-turn deferral as the initial auto-populate kick).
        # QWidget's own showEvent is a no-op, so no super chaining needed.
        qt.QTimer.singleShot(0, self.scheduleResectogramRender)

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
            # Re-fit so the strip keeps filling the resized central viewport.
            self.poseEmbeddedRenderer()

        # Unhandled: do NOT filter the event out.  Return False rather than
        # delegating to ``super().eventFilter`` -- PythonQt's QWidget does not
        # expose ``eventFilter`` via ``super()`` (it raises AttributeError), and
        # the Qt contract for an event filter is simply "False = pass through".
        return False

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

        # Re-fit the camera to the (now much larger) central viewport so the
        # strip fills it, then paint.  poseEmbeddedRenderer ends with a render.
        self.poseEmbeddedRenderer()

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

        # Re-fit the camera to the drawer viewport so the strip fills it again.
        self.poseEmbeddedRenderer()

    def cleanup(self):  # noqa: N802 - Slicer/Qt verb convention
        """Drop every observer + event filter this widget placed on objects that
        outlive it, so none fire into a destroyed widget.

        Mirrors the retired C++ widget's destructor (which removed the enlarge
        event filters) plus the qvtkConnect auto-disconnect (which dropped the
        VTK node observers).  Safe to call more than once.

        In production the widget is parented into the Liver shell's tab and is
        destroyed BEFORE the scene (so qMRMLNodeComboBox cleans its own scene
        wiring); call this when tearing the widget down OUT of that order
        (module reload, or a parentless test widget) so the combo box releases
        the scene before the scene is freed -- otherwise the combo's scene
        observer fires into freed memory at app shutdown.
        """
        if self._comboBox is not None:
            self._comboBox.setMRMLScene(None)
        # The click-to-reslice consumer's locator observer (on a scene node that
        # outlives this panel) -- detach symmetrically.
        if self._locatorReslicer is not None:
            self._locatorReslicer.cleanup()
            self._locatorReslicer = None
        # The view manager's default-deny observers (on the scene + slice
        # display nodes, both of which outlive this panel).
        if self._resectogramViewManager is not None:
            self._resectogramViewManager.cleanup()
            self._resectogramViewManager = None
        # VTK node observers (on scene nodes that outlive this panel).
        if self._activeResectionNode is not None and self._activeNodeObservationTag is not None:
            self._activeResectionNode.RemoveObserver(self._activeNodeObservationTag)
        self._activeNodeObservationTag = None
        self.observeSurfaceForRender(None)  # symmetric removal of the render observer

        # Event filters: the enlarge viewport (owned by the layout manager, which
        # long outlives this widget) and the embedded view.
        if self._enlargeHost is not None:
            self._enlargeHost.removeEventFilter(self)
            self._enlargeHost = None
        if self._resectogramWidget is not None:
            view = self._resectogramWidget.threeDView()
            if view is not None:
                view.removeEventFilter(self)

    # ----------------------------------------------------------------------- #
    # Helpers.
    # ----------------------------------------------------------------------- #

    @staticmethod
    def _asResectionPlan(node):
        """Return ``node`` if it is a resection-plan wrapper node, else ``None``."""
        if node is not None and node.IsA(_RESECTION_PLAN_CLASS):
            return node
        return None

    @staticmethod
    def _parametricSurfaceDisplayNode(carrier):
        """The carrier's parametric-surface display aspect, or ``None``.

        The band-style home (InterpolatedMargins, margin colours) shared with
        the 3D path -- the sibling of the resectogram display node on the same
        carrier (Docs/architecture/target-mrml-node-hierarchy.md).
        """
        if carrier is None:
            return None
        for index in range(carrier.GetNumberOfDisplayNodes()):
            candidate = carrier.GetNthDisplayNode(index)
            if candidate is not None and candidate.IsA(_SURFACE_DISPLAY_CLASS):
                return candidate
        return None

    @staticmethod
    def _existingResectogramDisplayNode(carrier):
        """Return the carrier's resectogram display node, or ``None``."""
        if carrier is None:
            return None
        for index in range(carrier.GetNumberOfDisplayNodes()):
            candidate = carrier.GetNthDisplayNode(index)
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

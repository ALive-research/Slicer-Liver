# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""LayerDM Pipeline for vessel-annotation placement + edit (ADR-0037).

ADR-0037 §Decision 2 routes vessel-annotation placement and edit through
the LayerDM scripted Pipeline's interaction seam (ADR-0032 / ADR-0033),
reusing the already-built ``VesselSurfacePick`` (ray-onto-surface) and the
adhering highlight.  There is NO markup place mode and NO annotation state
machine (ADR-0037 §Decision 2 + §Alternatives) --
add-on-click / drag-to-edit / delete-from-table is the whole lifecycle:

* a CLICK claims the gesture and adds EXACTLY ONE surface-snapped point to
  the carrier's active territory (on the mesh, distance ~= 0);
* a DRAG (press-near-a-point + move) edits the NEAREST existing point;
* a BARE MOVE is DECLINED (``CanProcessInteractionEvent`` returns
  ``(False, +inf)``) so the camera is untouched (ADR-0033) -- beyond
  raising the adhering highlight as a side effect;
* DELETE removes EXACTLY ONE point;
* an unrelated ``Modified`` causes no drift.

The point storage lives on ``vtkMRMLCustomTerritoriesNode`` (the carrier
pinned by ``test_territories_annotation_carrier.py``); this Pipeline
WRITES to it via the interaction seam, mirroring ``ControlPolygonPipeline``
/ ``LiverBezierSurfacePipeline`` (the resection interaction seams).

The pick geometry itself is pure-VTK and covered bare by
``test_vessel_surface_pick.py``; here the invariants are the arbitration
(claim click / claim grabbed drag / decline bare move), the exactly-one
mutation per gesture, and the nearest-point edit selection.
"""

from __future__ import annotations

import sys
from typing import Any

import vtk

from LayerDMLib import vtkMRMLLayerDMScriptedPipeline as _PipelineBase

try:  # pragma: no cover - exercised once per import path
    from .VesselSurfacePick import VesselSurfacePick
    from .VesselHighlightWiring import vascular_surface_polydata
except ImportError:  # top-level import path (the unit layer's sys.path setup)
    from VesselSurfacePick import VesselSurfacePick  # type: ignore[no-redef]
    from VesselHighlightWiring import vascular_surface_polydata  # type: ignore[no-redef]

#: Display-space pick radius for grabbing an existing point, in pixels
#: (mirrors ``ControlPolygonPipeline.CONTROL_POINT_PICK_RADIUS_PX``).  A
#: press within this radius of a placed point grabs it for a drag; a press
#: outside it (but over the surface) adds a new point.
POINT_PICK_RADIUS_PX = 20.0

#: Hover/grab cue colours + halo scale, shared with the resection surface
#: control points (ControlPolygonPipeline): hover = yellow, grab = green, and
#: the glow halo is a slightly larger sphere (blurred by vtkOutlineGlowPass).
HALO_HOVER_COLOR = (1.0, 0.9, 0.2)
HALO_GRAB_COLOR = (0.3, 1.0, 0.4)
HALO_HOVER_SCALE = 1.6

#: Interaction state lives on the shared highlight DISPLAY NODE, not on the
#: Pipeline instance: LayerDM owns the Pipeline instance lifecycle (it creates
#: its own per view), so the widget/table can only reach the Pipeline the
#: manager drives THROUGH the display node both sides hold.  This is still
#: "pipeline-managed" (ADR-0037 §Decision 2) — the state is read by the
#: Pipeline, not by a Slicer interaction node / mouse mode.  The accessors
#: live in the dependency-free ``TerritoryInteractionState`` module so the
#: table can share them without the LayerDMLib import.
try:  # pragma: no cover - exercised once per import path
    from . import TerritoryInteractionState as _state
except ImportError:  # top-level import path (the unit layer's sys.path setup)
    import TerritoryInteractionState as _state  # type: ignore[no-redef]

_REGISTERED = False


class TerritoryPlacementPipeline(_PipelineBase):
    """Places + edits the annotation points of a custom-territories carrier.

    Created by LayerDM's manager via the creator registered by
    ``registerTerritoryPlacementPipelineCreator()``; keyed on
    ``vtkMRMLTerritoriesHighlightDisplayNode`` (the annotation-interaction
    display node), reusing the adhering highlight's pick core.
    """

    def __init__(self) -> None:
        super().__init__()
        self.SetPythonObject(self)

        self._display_node: Any | None = None
        self._renderer: Any | None = None
        self._observer_tags: dict = {}
        self._observed_node_refs: list = []

        # The carrier + the active territory the placement writes into.
        self._carrier: Any | None = None
        self._territory_id: str | None = None

        # Stage-2 arming (ADR-0037 §Decision 3).  An armed click appends one
        # seed to the ACTIVE territory; a disarmed click adds nothing.  In
        # production the arm state + active territory + carrier all live on the
        # shared highlight DISPLAY NODE (read by ``GetActiveTerritory`` /
        # ``IsArmed`` / ``_get_carrier``) so the widget/table reach the
        # manager-driven Pipeline; these instance fields are the BARE-unit
        # fallback (no display node).  It is still pipeline-managed, not a
        # Slicer interaction node / mouse mode.
        self._active_territory: str | None = None
        self._armed: bool = False

        # Injectable pick core (bare unit layer feeds a known surface); in
        # production ``_ensure_pick`` builds it from the display node's
        # pickSurface.
        self._pick: VesselSurfacePick | None = None

        # (territory id, in-territory index) of the point currently GRABBED
        # by a press/move/release drag -- None when no drag is in flight.
        self._drag_target: tuple[str, int] | None = None

        # Carrier currently observed for the seed-glyph rebuild (production
        # resolves it from the display node, so the bare ``SetCarrier`` bind is
        # not the only path); tracked to avoid double-observing.
        self._observed_carrier: Any | None = None

        # -- placed-seed rendering (ADR-0037 §Decision 2): the persistent
        # markers for the carrier's annotation points, glyphed as spheres and
        # coloured per territory from the carrier's display slot.  One actor
        # for the whole point set; rebuilt on any carrier Modified.
        self._seed_points = vtk.vtkPoints()
        self._seed_colors = vtk.vtkUnsignedCharArray()
        self._seed_colors.SetNumberOfComponents(3)
        self._seed_colors.SetName("SeedColors")
        self._seed_polydata = vtk.vtkPolyData()
        self._seed_polydata.SetPoints(self._seed_points)
        self._seed_polydata.GetPointData().SetScalars(self._seed_colors)
        self._seed_sphere = vtk.vtkSphereSource()
        self._seed_sphere.SetPhiResolution(12)
        self._seed_sphere.SetThetaResolution(12)
        self._seed_sphere.SetRadius(2.2)
        self._seed_glyph = vtk.vtkGlyph3D()
        self._seed_glyph.SetInputData(self._seed_polydata)
        self._seed_glyph.SetSourceConnection(self._seed_sphere.GetOutputPort())
        self._seed_glyph.SetScaleModeToDataScalingOff()
        self._seed_glyph.SetColorModeToColorByScalar()
        self._seed_mapper = vtk.vtkPolyDataMapper()
        self._seed_mapper.SetInputConnection(self._seed_glyph.GetOutputPort())
        # Interpret the per-glyph uchar[3] scalars as RGB directly.  Without
        # ScalarVisibilityOn + UsePointData the mapper falls back to the LUT
        # (which maps the 3-component array to near-black) -- the spheres then
        # render invisible against the dark 3D background.
        self._seed_mapper.SetScalarModeToUsePointData()
        self._seed_mapper.ScalarVisibilityOn()
        self._seed_mapper.SetColorModeToDirectScalars()
        self._seed_actor = vtk.vtkActor()
        self._seed_actor.SetMapper(self._seed_mapper)

        # -- hover-adhering MARKER: the sphere that clings to the surface under
        # the cursor.  This pipeline is the SINGLE 3D pipeline for the
        # highlight display-node type (ADR-0013 §1, one Pipeline per type), so
        # it renders the hover marker ITSELF rather than relying on a second
        # pipeline on the same type (which LayerDM would not create).
        self._marker_sphere = vtk.vtkSphereSource()
        self._marker_sphere.SetPhiResolution(16)
        self._marker_sphere.SetThetaResolution(16)
        self._marker_sphere.SetRadius(3.0)
        self._marker_mapper = vtk.vtkPolyDataMapper()
        self._marker_mapper.SetInputConnection(self._marker_sphere.GetOutputPort())
        self._marker_actor = vtk.vtkActor()
        self._marker_actor.SetMapper(self._marker_mapper)
        self._marker_actor.GetProperty().SetColor(1.0, 0.6, 0.1)
        self._marker_actor.SetVisibility(False)

        # -- edit hover GLOW halo: a blurred glow around the seed under the
        # cursor (yellow), swapping to green while grabbed, so the surgeon
        # knows a marker is about to move -- the ControlPolygonPipeline glow
        # cue.  Rendered in a private overlay renderer carrying a
        # vtkOutlineGlowPass (the blur-to-halo pass); degrades to a plain
        # sphere when the pass class is unavailable.
        self._hover_target: tuple[str, int] | None = None
        self._halo_renderer: Any | None = None
        self._halo_sphere = vtk.vtkSphereSource()
        self._halo_sphere.SetPhiResolution(16)
        self._halo_sphere.SetThetaResolution(16)
        self._halo_sphere.SetRadius(self._seed_sphere.GetRadius() * HALO_HOVER_SCALE)
        self._halo_mapper = vtk.vtkPolyDataMapper()
        self._halo_mapper.SetInputConnection(self._halo_sphere.GetOutputPort())
        self._halo_actor = vtk.vtkActor()
        self._halo_actor.SetMapper(self._halo_mapper)
        self._halo_actor.GetProperty().SetColor(*HALO_HOVER_COLOR)
        self._halo_actor.SetVisibility(False)

    # ------------------------------------------------------------------ #
    # Wiring seams (unit + production)
    # ------------------------------------------------------------------ #

    def SetPickCore(self, pick: VesselSurfacePick | None) -> None:  # noqa: N802 - VTK verb
        """Inject the ``VesselSurfacePick`` over the target surface (unit seam)."""
        self._pick = pick

    def _ensure_pick(self) -> VesselSurfacePick | None:
        """Build the pick core against the display node's ``pickSurface`` mesh.

        Production (LayerDM-created) instances resolve the surface from the
        shared display node exactly as ``VesselHighlightPipeline`` does, so
        the click-snap and the hover marker adhere to the same mesh with no
        injection.  A test-injected ``self._pick`` short-circuits this for the
        bare unit layer.
        """
        if self._pick is not None:
            return self._pick
        display = self._display_node
        if display is None:
            return None
        segmentation = display.GetPickSurfaceNode()
        if segmentation is None:
            return None
        # Vessels-only: the cursor snaps to a vessel, never the liver
        # parenchyma or a tumour (ADR-0037 slice 5).
        polydata = vascular_surface_polydata(segmentation)
        if polydata is None:
            return None
        self._pick = VesselSurfacePick(polydata)
        return self._pick

    def SetCarrier(self, carrier: Any, territoryId: str) -> None:  # noqa: N802 - VTK verb
        """Bind the ``vtkMRMLCustomTerritoriesNode`` carrier + active territory.

        Instance-field binding for the BARE unit layer (no display node).  In
        production the carrier is resolved from the display node's reference
        (``_get_carrier``); this direct bind is the unit seam that keeps the
        edit math GL- and scene-free.

        Observation goes through ``_ensure_carrier_observed`` (the single
        ``_observed_carrier`` dedupe key), NOT a direct attach here -- else a
        later ``_ensure_carrier_observed`` resolving the same carrier would
        add a SECOND ModifiedEvent observer (double rebuild per Modified).
        """
        self._carrier = carrier
        self._territory_id = territoryId
        self._ensure_carrier_observed()

    def GetCarrier(self) -> Any | None:  # noqa: N802 - VTK verb
        return self._get_carrier()

    def _get_carrier(self) -> Any | None:
        """The carrier in effect: the display node's reference, else the bound one.

        Production (LayerDM-created) instances resolve the carrier from the
        shared display node so the widget/table and the manager-driven
        Pipeline agree; the bare unit layer (no display node) falls back to
        the directly-bound ``SetCarrier`` carrier.
        """
        carrier = _state.get_carrier(self._display_node)
        if carrier is not None:
            return carrier
        return self._carrier

    # ------------------------------------------------------------------ #
    # Active-territory + arm seam (Stage 2, ADR-0037 §Decision 3)
    # ------------------------------------------------------------------ #

    def SetActiveTerritory(self, territoryId: str | None) -> None:  # noqa: N802 - VTK verb
        """Set the territory an armed click appends into (the ACTIVE one)."""
        if self._display_node is not None:
            _state.set_active_territory(self._display_node, territoryId)
        self._active_territory = territoryId

    def GetActiveTerritory(self) -> str | None:  # noqa: N802 - VTK verb
        if self._display_node is not None:
            return _state.get_active_territory(self._display_node)
        return self._active_territory

    def Arm(self) -> None:  # noqa: N802 - VTK verb
        """Enable add-on-click into the active territory ("Add Territory" / "Add seeds")."""
        if self._display_node is not None:
            _state.set_armed(self._display_node, True)
        self._armed = True

    def Disarm(self) -> None:  # noqa: N802 - VTK verb
        """Disable add-on-click ("Done" / Esc).  A click then adds nothing."""
        if self._display_node is not None:
            _state.set_armed(self._display_node, False)
        self._armed = False

    def IsArmed(self) -> bool:  # noqa: N802 - VTK verb
        if self._display_node is not None:
            return _state.is_armed(self._display_node)
        return self._armed

    def _placement_territory(self) -> str | None:
        """The territory a click appends into: the active one, else the bound one."""
        active = self.GetActiveTerritory()
        if active is not None:
            return active
        return self._territory_id

    def _safe_get_renderer(self) -> Any | None:
        return self._renderer

    # ------------------------------------------------------------------ #
    # LayerDM lifecycle
    # ------------------------------------------------------------------ #

    def SetDisplayNode(self, displayNode: Any) -> None:  # noqa: N802 - VTK verb
        super().SetDisplayNode(displayNode)
        self._display_node = displayNode
        # A (re)attached display node can carry a different pickSurface /
        # carrier: force both to re-resolve (the highlight-Pipeline precedent).
        self._pick = None
        self._ensure_carrier_observed()

    def OnRendererAdded(self, renderer: Any) -> None:  # noqa: N802 - VTK verb
        try:
            self._renderer = renderer
            if renderer is not None:
                renderer.AddActor(self._seed_actor)
                renderer.AddActor(self._marker_actor)
            self._attach_halo_renderer(renderer)
            # Renderer churn cleared the display handle; re-derive it from the
            # base's retained display node (the ControlPolygonPipeline
            # re-attach precedent) so the carrier + seed glyphs come back.
            if self._display_node is None:
                display = self.GetDisplayNode()
                if display is not None:
                    self.SetDisplayNode(display)
            self._ensure_carrier_observed()
            self._rebuild_seed_actor()
            self._reconcile_highlight()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    def OnRendererRemoved(self, renderer: Any) -> None:  # noqa: N802 - VTK verb
        try:
            if renderer is not None:
                renderer.RemoveActor(self._seed_actor)
                renderer.RemoveActor(self._marker_actor)
            self._detach_halo_renderer()
            self._renderer = None
            self.cleanup()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    def _attach_halo_renderer(self, renderer: Any) -> None:
        """Build the private glow overlay on ``renderer``'s window.

        A dedicated overlay ``vtkRenderer`` (camera shared with the view
        renderer) carries the halo actor and a ``vtkOutlineGlowPass`` -- the
        blur-to-halo pass -- so qMRMLThreeDView's SetPass(nullptr) reset on the
        VIEW renderer never clobbers it (the ControlPolygonPipeline
        precedent).  Degrades to the plain halo sphere when the pass class or
        the render window is unavailable (bare unit layer).
        """
        window = getattr(renderer, "GetRenderWindow", None)
        window = window() if window is not None else None
        if window is None or self._halo_renderer is not None:
            return
        try:
            overlay = vtk.vtkRenderer()
            overlay.SetLayer(max(1, window.GetNumberOfLayers()))
            window.SetNumberOfLayers(overlay.GetLayer() + 1)
            overlay.InteractiveOff()
            overlay.SetActiveCamera(renderer.GetActiveCamera())
            overlay.AddActor(self._halo_actor)
            glow = getattr(vtk, "vtkOutlineGlowPass", None)
            steps = getattr(vtk, "vtkRenderStepsPass", None)
            if glow is not None and steps is not None:
                glow_pass = glow()
                glow_pass.SetDelegatePass(steps())
                overlay.SetPass(glow_pass)
            window.AddRenderer(overlay)
            self._halo_renderer = overlay
        except Exception:  # pragma: no cover - defensive (fake renderers)
            self._halo_renderer = None

    def _detach_halo_renderer(self) -> None:
        overlay = self._halo_renderer
        self._halo_renderer = None
        if overlay is None:
            return
        try:
            window = overlay.GetRenderWindow()
            if window is not None:
                window.RemoveRenderer(overlay)
        except Exception:  # pragma: no cover - defensive
            pass

    def cleanup(self) -> None:
        for node in list(self._observed_node_refs):
            self._detach_observer(node)
        self._carrier = None
        self._observed_carrier = None
        self._drag_target = None
        self._hover_target = None
        self._halo_actor.SetVisibility(False)

    def _ensure_carrier_observed(self) -> None:
        """Observe the in-effect carrier so seed glyphs track its edits.

        Production resolves the carrier from the display node (never via
        ``SetCarrier``), so the seed-glyph rebuild needs its own observer
        attach; re-attaches when the resolved carrier changes.
        """
        carrier = self._get_carrier()
        if carrier is self._observed_carrier:
            return
        if self._observed_carrier is not None:
            self._detach_observer(self._observed_carrier)
        self._observed_carrier = carrier
        if carrier is not None:
            self._attach_observer(carrier)

    def UpdatePipeline(self) -> None:  # noqa: N802 - VTK verb
        """LayerDM's re-sync hook (display-node Modified).

        The display node is added to the scene (LayerDM creates this pipeline)
        BEFORE the table binds the carrier reference onto it, so the carrier is
        not resolvable at creation.  This hook fires when the reference IS set,
        so it is where the seed-glyph observer finally attaches -- without it a
        seed placed from a SLICE view never repaints the 3D glyphs.
        """
        try:
            self._ensure_carrier_observed()
            self._rebuild_seed_actor()
            self._reconcile_highlight()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    def _reconcile_highlight(self) -> None:
        """Sync the hover-marker sphere to the shared display node's adhering state.

        The single 3D pipeline renders the cross-view hover marker: shown at
        ``AdheringPointWorld`` when the display node is adhering + visible
        (published by a hover in ANY view), hidden otherwise.
        """
        display = self._display_node
        if display is None or not hasattr(display, "GetAdhering"):
            self._marker_actor.SetVisibility(False)
            return
        try:
            self._marker_sphere.SetRadius(float(display.GetRadius()))
        except Exception:  # pragma: no cover - defensive
            pass
        try:
            color = display.GetColor()
            self._marker_actor.GetProperty().SetColor(color[0], color[1], color[2])
        except Exception:  # pragma: no cover - defensive
            pass
        adhering = bool(display.GetAdhering()) and bool(display.GetVisibility())
        self._marker_actor.SetVisibility(adhering)
        if adhering:
            point = display.GetAdheringPointWorld()
            self._marker_actor.SetPosition(point[0], point[1], point[2])

    # ------------------------------------------------------------------ #
    # Interaction — placement / edit (ADR-0032 / ADR-0033)
    # ------------------------------------------------------------------ #

    def CanProcessInteractionEvent(self, eventData: Any):  # noqa: N802 - VTK verb
        """Return ``(canProcess, distance2)`` for the LayerDM focus logic.

        * A LEFT-BUTTON PRESS within ``POINT_PICK_RADIUS_PX`` of an existing
          point is claimed with the REAL squared display distance (grab a
          point for a drag).
        * A LEFT-BUTTON PRESS over the surface but away from any point is
          claimed (add-on-click); its arbitration value is the pick radius
          squared so a nearer grabbable interaction still wins.
        * While a point is GRABBED, moves and the release are claimed
          unconditionally (the grab owns the gesture).
        * A BARE MOVE is DECLINED (``(False, +inf)``) so the camera is
          untouched (ADR-0033); it only raises the adhering highlight as a
          side effect.
        """
        try:
            renderer = self._safe_get_renderer()
            if renderer is None:
                return False, sys.float_info.max
            etype = _event_type(eventData)

            if self._drag_target is not None:
                if etype in (
                    vtk.vtkCommand.MouseMoveEvent,
                    vtk.vtkCommand.LeftButtonReleaseEvent,
                ):
                    return True, 0.0
                return False, sys.float_info.max

            if etype == vtk.vtkCommand.MouseMoveEvent:
                # Bare hover (ADR-0033: side-effect repaint, DECLINE so the
                # camera is untouched).  Over an existing seed -> glow halo on
                # it (about-to-move cue) + suppress the placement preview; over
                # empty surface -> raise the adhering placement preview.
                territory, index, distance2 = self._nearest_point_in_display(renderer, eventData)
                if (
                    territory is not None
                    and index is not None
                    and distance2 <= POINT_PICK_RADIUS_PX * POINT_PICK_RADIUS_PX
                ):
                    self._set_hover((territory, index))
                    self._clear_adhering()
                else:
                    self._set_hover(None)
                    self._raise_highlight(renderer, eventData)
                self._reconcile_highlight()
                self.RequestRender()
                return False, sys.float_info.max

            if etype != vtk.vtkCommand.LeftButtonPressEvent:
                return False, sys.float_info.max

            _territory, _index, distance2 = self._nearest_point_in_display(renderer, eventData)
            if distance2 <= POINT_PICK_RADIUS_PX * POINT_PICK_RADIUS_PX:
                # Press near an existing point -> grab it for a drag (an edit
                # gesture; independent of the arm state).
                return True, distance2

            # Add-on-click requires an armed pipeline (ADR-0037 §Decision 3):
            # a disarmed press away from any point leaves the gesture to the
            # camera.
            if not self.IsArmed():
                return False, sys.float_info.max

            # Press away from any point: claim only when the ray hits the
            # surface (add-on-click); otherwise leave the press to the camera.
            if self._event_world_on_surface(renderer, eventData) is None:
                return False, sys.float_info.max
            return True, POINT_PICK_RADIUS_PX * POINT_PICK_RADIUS_PX
        except Exception:  # pragma: no cover - C++ boundary must never raise
            return False, sys.float_info.max

    def ProcessInteractionEvent(self, eventData: Any) -> bool:  # noqa: N802 - VTK verb
        """Drive add-on-click / drag-to-edit (ADR-0037 §Decision 2)."""
        try:
            renderer = self._safe_get_renderer()
            if renderer is None:
                self._drag_target = None
                return False
            etype = _event_type(eventData)

            if self._drag_target is None:
                if etype != vtk.vtkCommand.LeftButtonPressEvent:
                    return False
                territory, index, distance2 = self._nearest_point_in_display(renderer, eventData)
                if territory is not None and index is not None and distance2 <= POINT_PICK_RADIUS_PX * POINT_PICK_RADIUS_PX:
                    # Grab the existing point for a drag (edit gesture): swap the
                    # glow halo + the seed to the grab colour (green).
                    self._drag_target = (territory, index)
                    self._position_halo()
                    self._rebuild_seed_actor()
                    self.RequestRender()
                    return True
                # Add-on-click requires an armed pipeline (ADR-0037
                # §Decision 3): a disarmed click adds nothing.  Read the
                # display-node-backed arm state (the table writes it there),
                # NOT the instance flag.
                if not self.IsArmed():
                    return False
                # Snap to the surface and add exactly one point to the active
                # territory.
                world = self._event_world_on_surface(renderer, eventData)
                if world is None:
                    return False
                self._add_point(world)
                # Repaint immediately: the carrier observer's RequestRender does
                # not flush a frame mid-interaction (the slice-pipeline lesson).
                self._rebuild_seed_actor()
                self.RequestRender()
                return True

            if etype == vtk.vtkCommand.LeftButtonReleaseEvent:
                self._drag_target = None
                # Gesture over: drop the grab colour (fall back to hover/none).
                self._position_halo()
                self._rebuild_seed_actor()
                self.RequestRender()
                return False  # release the focus

            if etype == vtk.vtkCommand.MouseMoveEvent:
                world = self._event_world_on_surface(renderer, eventData)
                if world is None:
                    return True  # keep the grab; this move just didn't resolve
                self._relocate_grabbed_point(world)
                # Track the grabbed seed under the drag + repaint immediately.
                self._position_halo()
                self._rebuild_seed_actor()
                self.RequestRender()
                return True

            return False
        except Exception:  # pragma: no cover - C++ boundary must never raise
            return False

    def DeleteAnnotationPoint(self, territoryId: str, index: int) -> bool:  # noqa: N802 - VTK verb
        """Remove EXACTLY ONE annotation point (delete-from-table end).

        ADR-0037 §Decision 2 "delete removes one point"; the tail shifts up
        in order.  Returns True iff a point was removed.
        """
        carrier = self._get_carrier()
        if carrier is None:
            return False
        return bool(carrier.RemoveNthAnnotationPoint(territoryId, int(index)))

    # ------------------------------------------------------------------ #
    # Carrier writes
    # ------------------------------------------------------------------ #

    def _add_point(self, world: Any) -> None:
        carrier = self._get_carrier()
        territory = self._placement_territory()
        if carrier is None or territory is None:
            return
        carrier.AddAnnotationPoint(territory, float(world[0]), float(world[1]), float(world[2]))

    def _relocate_grabbed_point(self, world: Any) -> None:
        carrier = self._get_carrier()
        target = self._drag_target
        if carrier is None or target is None:
            return
        territory, index = target
        carrier.SetNthAnnotationPoint(territory, int(index), float(world[0]), float(world[1]), float(world[2]))

    # ------------------------------------------------------------------ #
    # Geometry seams (monkeypatched in the unit layer)
    # ------------------------------------------------------------------ #

    def _event_world_on_surface(self, renderer: Any, eventData: Any):
        """Snap the event pixel onto the surface via ``VesselSurfacePick``.

        Builds the cursor ray by unprojecting the event pixel at the near +
        far clipping depths, feeds it to the injected pick core, and returns
        the surface-snapped world point (``None`` on a miss / no surface).
        The unit layer injects the result directly, keeping the edit math
        GL-free.
        """
        pick = self._ensure_pick()
        if pick is None:
            return None
        ray = self._cursor_ray(renderer, eventData)
        if ray is None:
            return None
        p1, p2 = ray
        return pick.pick(p1, p2)

    def _nearest_point_in_display(self, renderer: Any, eventData: Any):
        """``(territoryId, index, distance2)`` of the point nearest the pixel.

        Scans the carrier's active territory's points, projects each to
        display, and returns the nearest with its REAL squared display
        distance (LayerDM arbitration).  ``(None, None, +inf)`` when there
        is no carrier / territory / point.
        """
        carrier = self._get_carrier()
        territory = self._placement_territory()
        if carrier is None or territory is None:
            return None, None, sys.float_info.max
        count = carrier.GetNumberOfAnnotationPoints(territory)
        if count == 0:
            return None, None, sys.float_info.max
        try:
            ex, ey = eventData.GetDisplayPosition()
        except Exception:  # pragma: no cover - defensive (fake events)
            return None, None, sys.float_info.max

        best_index = None
        best_d2 = sys.float_info.max
        for i in range(count):
            point = carrier.GetNthAnnotationPoint(territory, i)
            renderer.SetWorldPoint(point[0], point[1], point[2], 1.0)
            renderer.WorldToDisplay()
            dx, dy, _dz = renderer.GetDisplayPoint()
            d2 = (dx - ex) ** 2 + (dy - ey) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best_index = i
        if best_index is None:
            return None, None, sys.float_info.max
        return territory, best_index, best_d2

    def _cursor_ray(self, renderer: Any, eventData: Any):
        """The world-space cursor ray ``(p1, p2)`` for the event pixel."""
        try:
            ex, ey = eventData.GetDisplayPosition()
        except Exception:  # pragma: no cover - defensive
            return None
        p1 = self._display_to_world(renderer, ex, ey, 0.0)
        p2 = self._display_to_world(renderer, ex, ey, 1.0)
        if p1 is None or p2 is None:
            return None
        return p1, p2

    @staticmethod
    def _display_to_world(renderer: Any, ex: float, ey: float, z: float):
        """Unproject display pixel ``(ex, ey)`` at normalized depth ``z``."""
        try:
            renderer.SetDisplayPoint(float(ex), float(ey), float(z))
            renderer.DisplayToWorld()
            wx, wy, wz, ww = renderer.GetWorldPoint()
        except Exception:  # pragma: no cover - defensive
            return None
        if ww == 0.0:
            return None
        return (wx / ww, wy / ww, wz / ww)

    def _raise_highlight(self, renderer: Any, eventData: Any) -> None:
        """Publish the hover-adhering point onto the display node, if any.

        The annotation placement shares the vessel-adhering highlight: a
        bare hover resolves the surface point under the cursor and writes it
        onto the (data-only) highlight display node, exactly as
        ``VesselHighlightPipeline`` does.  Change-gated so the hover does not
        storm ``Modified``.  A no-op when no display node / surface is wired.
        """
        display = self._display_node
        if display is None or not hasattr(display, "SetAdhering"):
            return
        world = self._event_world_on_surface(renderer, eventData)
        adhering = world is not None
        changed = False
        if bool(display.GetAdhering()) != adhering:
            display.SetAdhering(adhering)
            changed = True
        if adhering:
            current = display.GetAdheringPointWorld()
            if tuple(current) != (world[0], world[1], world[2]):
                display.SetAdheringPointWorld(world[0], world[1], world[2])
                changed = True
        if changed:
            display.Modified()

    def _clear_adhering(self) -> None:
        """Retire the placement preview (cursor is over a seed, not empty surface)."""
        display = self._display_node
        if display is None or not hasattr(display, "SetAdhering"):
            return
        if bool(display.GetAdhering()):
            display.SetAdhering(False)
            display.Modified()

    def _set_hover(self, target: tuple[str, int] | None) -> None:
        """Glow-halo the seed under the cursor (``None`` clears the hover)."""
        if target == self._hover_target:
            return
        self._hover_target = target
        self._position_halo()
        self._rebuild_seed_actor()

    def _position_halo(self) -> None:
        """Place the glow halo on the grabbed (green) or hovered (yellow) seed."""
        target = self._drag_target or self._hover_target
        carrier = self._get_carrier()
        show = False
        if target is not None and carrier is not None:
            territory, index = target
            if 0 <= index < carrier.GetNumberOfAnnotationPoints(territory):
                point = carrier.GetNthAnnotationPoint(territory, index)
                self._halo_actor.SetPosition(point[0], point[1], point[2])
                colour = HALO_GRAB_COLOR if self._drag_target is not None else HALO_HOVER_COLOR
                self._halo_actor.GetProperty().SetColor(*colour)
                show = True
        self._halo_actor.SetVisibility(show)

    # ------------------------------------------------------------------ #
    # Observers (reconcile) + plumbing
    # ------------------------------------------------------------------ #

    def _attach_observer(self, node: Any) -> None:
        if node is None or not hasattr(node, "AddObserver"):
            return
        tag = node.AddObserver("ModifiedEvent", self._on_node_modified)
        self._observer_tags.setdefault(id(node), []).append(tag)
        if node not in self._observed_node_refs:
            self._observed_node_refs.append(node)

    def _detach_observer(self, node: Any) -> None:
        if node is None:
            return
        for tag in self._observer_tags.pop(id(node), []):
            try:
                node.RemoveObserver(tag)
            except Exception:  # pragma: no cover - defensive
                pass
        try:
            self._observed_node_refs.remove(node)
        except ValueError:
            pass

    def _on_node_modified(self, caller: Any, event: str) -> None:
        """Reconcile on a carrier ``Modified`` -- idempotent, no drift.

        The placement Pipeline holds no shadow copy of the point set: the
        carrier IS the source of truth, so a reconcile driven by an
        unrelated ``Modified`` (a table repaint, a colour change) reads the
        carrier and repaints without adding / moving / dropping any point
        (ADR-0037 §Conformance no-drift).
        """
        del caller, event
        try:
            self._rebuild_seed_actor()
            self.RequestRender()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    # ------------------------------------------------------------------ #
    # Placed-seed rendering (ADR-0037 §Decision 2)
    # ------------------------------------------------------------------ #

    def _rebuild_seed_actor(self) -> None:
        """Rebuild the seed-glyph point set from the carrier, coloured per territory.

        The carrier is the source of truth: read every visible territory's
        points, glyph each as a sphere tinted with the territory's display
        colour (ADR-0037 §Decision 1 display slot).  A no-op-safe rebuild — an
        empty carrier clears the glyphs.
        """
        self._seed_points.Reset()
        self._seed_colors.Reset()
        self._seed_colors.SetNumberOfComponents(3)
        grab_rgb = tuple(int(c * 255) for c in HALO_GRAB_COLOR)
        hover_rgb = tuple(int(c * 255) for c in HALO_HOVER_COLOR)
        carrier = self._get_carrier()
        if carrier is not None:
            for territory in carrier.GetAnnotationTerritoryIds():
                if not bool(carrier.GetTerritoryVisibility(territory)):
                    continue
                rgb = carrier.GetTerritoryColor(territory)
                base = (
                    int(max(0.0, min(1.0, rgb[0])) * 255),
                    int(max(0.0, min(1.0, rgb[1])) * 255),
                    int(max(0.0, min(1.0, rgb[2])) * 255),
                )
                count = carrier.GetNumberOfAnnotationPoints(territory)
                for i in range(count):
                    point = carrier.GetNthAnnotationPoint(territory, i)
                    self._seed_points.InsertNextPoint(point[0], point[1], point[2])
                    key = (territory, i)
                    if key == self._drag_target:
                        self._seed_colors.InsertNextTuple3(*grab_rgb)  # grabbed: green
                    elif key == self._hover_target:
                        self._seed_colors.InsertNextTuple3(*hover_rgb)  # hovered: yellow
                    else:
                        self._seed_colors.InsertNextTuple3(*base)
        self._seed_points.Modified()
        self._seed_colors.Modified()
        self._seed_polydata.Modified()


def _event_type(eventData: Any) -> int:  # noqa: N803 - VTK arg name
    """The VTK event-type id off ``eventData``."""
    return int(eventData.GetType())


def registerTerritoryPlacementPipelineCreator() -> None:  # noqa: N802 - project convention
    """Register the ``TerritoryPlacementPipeline`` creator with LayerDM.

    Idempotent (module-level flag), mirroring
    ``registerVesselHighlightPipelineCreator``.  The creator matches
    ``(vtkMRMLViewNode, vtkMRMLTerritoriesHighlightDisplayNode)`` -- the 3D
    views only; annotation placement is a 3D-surface interaction (ADR-0013
    §5 call 3).  Rendering + interaction route through this scripted
    Pipeline + its creator, never a custom displayable manager (ADR-0013
    §5).
    """
    global _REGISTERED
    if _REGISTERED:
        return

    from slicer import (  # type: ignore[import-not-found]
        vtkMRMLLayerDMPipelineFactory,
        vtkMRMLLayerDMPipelineScriptedCreator,
        vtkMRMLTerritoriesHighlightDisplayNode,
        vtkMRMLViewNode,
    )

    def tryCreate(viewNode, node):
        try:
            if not isinstance(viewNode, vtkMRMLViewNode):
                return None
            if not isinstance(node, vtkMRMLTerritoriesHighlightDisplayNode):
                return None
            return TerritoryPlacementPipeline()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            return None

    creator = vtkMRMLLayerDMPipelineScriptedCreator()
    creator.SetPythonCallback(tryCreate)
    vtkMRMLLayerDMPipelineFactory.GetInstance().AddPipelineCreator(creator)
    _REGISTERED = True

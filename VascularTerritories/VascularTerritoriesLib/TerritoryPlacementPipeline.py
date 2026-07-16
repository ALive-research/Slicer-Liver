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
except ImportError:  # top-level import path (the unit layer's sys.path setup)
    from VesselSurfacePick import VesselSurfacePick  # type: ignore[no-redef]

#: Display-space pick radius for grabbing an existing point, in pixels
#: (mirrors ``ControlPolygonPipeline.CONTROL_POINT_PICK_RADIUS_PX``).  A
#: press within this radius of a placed point grabs it for a drag; a press
#: outside it (but over the surface) adds a new point.
POINT_PICK_RADIUS_PX = 20.0

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
        # seed to the ACTIVE territory; a disarmed click adds nothing.  The
        # arm state lives HERE (pipeline-managed), not on the interaction
        # node -- there is no Slicer mouse mode.  The active territory
        # overrides the ``SetCarrier`` binding for placement.
        self._active_territory: str | None = None
        self._armed: bool = False

        # Injectable pick core (bare unit layer feeds a known surface).
        self._pick: VesselSurfacePick | None = None

        # (territory id, in-territory index) of the point currently GRABBED
        # by a press/move/release drag -- None when no drag is in flight.
        self._drag_target: tuple[str, int] | None = None

    # ------------------------------------------------------------------ #
    # Wiring seams (unit + production)
    # ------------------------------------------------------------------ #

    def SetPickCore(self, pick: VesselSurfacePick | None) -> None:  # noqa: N802 - VTK verb
        """Inject the ``VesselSurfacePick`` over the target surface."""
        self._pick = pick

    def SetCarrier(self, carrier: Any, territoryId: str) -> None:  # noqa: N802 - VTK verb
        """Bind the ``vtkMRMLCustomTerritoriesNode`` carrier + active territory."""
        if self._carrier is not None:
            self._detach_observer(self._carrier)
        self._carrier = carrier
        self._territory_id = territoryId
        if carrier is not None:
            self._attach_observer(carrier)

    def GetCarrier(self) -> Any | None:  # noqa: N802 - VTK verb
        return self._carrier

    # ------------------------------------------------------------------ #
    # Active-territory + arm seam (Stage 2, ADR-0037 §Decision 3)
    # ------------------------------------------------------------------ #

    def SetActiveTerritory(self, territoryId: str | None) -> None:  # noqa: N802 - VTK verb
        """Set the territory an armed click appends into (the ACTIVE one)."""
        self._active_territory = territoryId

    def GetActiveTerritory(self) -> str | None:  # noqa: N802 - VTK verb
        return self._active_territory

    def Arm(self) -> None:  # noqa: N802 - VTK verb
        """Enable add-on-click into the active territory ("Add Territory" / "Add seeds")."""
        self._armed = True

    def Disarm(self) -> None:  # noqa: N802 - VTK verb
        """Disable add-on-click ("Done" / Esc).  A click then adds nothing."""
        self._armed = False

    def IsArmed(self) -> bool:  # noqa: N802 - VTK verb
        return self._armed

    def _placement_territory(self) -> str | None:
        """The territory a click appends into: the active one, else the bound one."""
        if self._active_territory is not None:
            return self._active_territory
        return self._territory_id

    def _safe_get_renderer(self) -> Any | None:
        return self._renderer

    # ------------------------------------------------------------------ #
    # LayerDM lifecycle
    # ------------------------------------------------------------------ #

    def SetDisplayNode(self, displayNode: Any) -> None:  # noqa: N802 - VTK verb
        super().SetDisplayNode(displayNode)
        self._display_node = displayNode

    def OnRendererAdded(self, renderer: Any) -> None:  # noqa: N802 - VTK verb
        try:
            self._renderer = renderer
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    def OnRendererRemoved(self, renderer: Any) -> None:  # noqa: N802 - VTK verb
        del renderer
        try:
            self._renderer = None
            self.cleanup()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    def cleanup(self) -> None:
        for node in list(self._observed_node_refs):
            self._detach_observer(node)
        self._carrier = None
        self._drag_target = None

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
                # Bare hover: raise the highlight as a SIDE EFFECT and
                # DECLINE -- camera moves stay unclaimed (ADR-0033).
                self._raise_highlight(renderer, eventData)
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
            if not self._armed:
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
                    # Grab the existing point for a drag (edit gesture).
                    self._drag_target = (territory, index)
                    return True
                # Add-on-click requires an armed pipeline (ADR-0037
                # §Decision 3): a disarmed click adds nothing.
                if not self._armed:
                    return False
                # Snap to the surface and add exactly one point to the active
                # territory.
                world = self._event_world_on_surface(renderer, eventData)
                if world is None:
                    return False
                self._add_point(world)
                return True

            if etype == vtk.vtkCommand.LeftButtonReleaseEvent:
                self._drag_target = None
                return False  # gesture over -- release the focus

            if etype == vtk.vtkCommand.MouseMoveEvent:
                world = self._event_world_on_surface(renderer, eventData)
                if world is None:
                    return True  # keep the grab; this move just didn't resolve
                self._relocate_grabbed_point(world)
                return True

            return False
        except Exception:  # pragma: no cover - C++ boundary must never raise
            return False

    def DeleteAnnotationPoint(self, territoryId: str, index: int) -> bool:  # noqa: N802 - VTK verb
        """Remove EXACTLY ONE annotation point (delete-from-table end).

        ADR-0037 §Decision 2 "delete removes one point"; the tail shifts up
        in order.  Returns True iff a point was removed.
        """
        carrier = self._carrier
        if carrier is None:
            return False
        return bool(carrier.RemoveNthAnnotationPoint(territoryId, int(index)))

    # ------------------------------------------------------------------ #
    # Carrier writes
    # ------------------------------------------------------------------ #

    def _add_point(self, world: Any) -> None:
        carrier = self._carrier
        territory = self._placement_territory()
        if carrier is None or territory is None:
            return
        carrier.AddAnnotationPoint(territory, float(world[0]), float(world[1]), float(world[2]))

    def _relocate_grabbed_point(self, world: Any) -> None:
        carrier = self._carrier
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
        pick = self._pick
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
        carrier = self._carrier
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
            self.RequestRender()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass


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

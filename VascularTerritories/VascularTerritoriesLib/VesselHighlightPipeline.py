# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""LayerDM Pipeline for the vessel-adhering highlight (ADR-0013, ADR-0033).

While a vessel-annotation marker is being placed, this Pipeline paints a
marker glyph that clings to the input segmentation's closed-surface mesh
under the cursor, and hides it off-surface.  It is the ADR-0013 Pipeline
pattern applied to a genuine interaction need, keyed on
``vtkMRMLTerritoriesHighlightDisplayNode`` (one Pipeline per display-node
type, ADR-0013 §1).

Design (mirrors the LiverResections precedents):

* ADR-0033 hover discipline (ControlPolygonPipeline): a bare mouse move is
  claimed as a SIDE EFFECT of ``CanProcessInteractionEvent`` — the adhering
  marker is repositioned/hidden there — but the call DECLINES the move
  (returns ``False``) so camera interaction stays untouched.
* World<->Display back-projection (``LiverBezierSurfacePipeline``): the
  cursor ray is built by unprojecting the event pixel at two depths (near
  + far clipping planes) via the renderer, giving ``p1``->``p2`` in world
  space.
* The ray + the segmentation's closed-surface polydata feed the pure-VTK
  ``VesselSurfacePick`` core (ADR-0025 pick pattern); the picked point is
  the adhering marker position, hidden when the pick misses.
* The picked point is published onto the DATA-ONLY display node
  (``AdheringPointWorld`` / ``Adhering``, ADR-0013 §5 no-logic-on-node);
  the marker actor and a digest-gated ``RequestRender`` follow.

The GL glow/adherence appearance is eyeball-gated (not headless-testable);
the pick integration, the decline-on-bare-move contract, and the marker
position are the pinned invariants.
"""

from __future__ import annotations

import sys
from typing import Any

import vtk

from LayerDMLib import vtkMRMLLayerDMScriptedPipeline as _PipelineBase

try:  # pragma: no cover - exercised once per import path
    from .VesselSurfacePick import VesselSurfacePick
    from .VesselHighlightWiring import vascular_surface_polydata, visibility_mtime as _visibility_mtime
except ImportError:  # top-level import path (the unit layer's sys.path setup)
    from VesselSurfacePick import VesselSurfacePick  # type: ignore[no-redef]
    from VesselHighlightWiring import vascular_surface_polydata, visibility_mtime as _visibility_mtime  # type: ignore[no-redef]

_REGISTERED = False


class VesselHighlightPipeline(_PipelineBase):
    """Paints the vessel-adhering marker under the cursor (hover-driven).

    Created by LayerDM's manager via the creator registered by
    ``registerVesselHighlightPipelineCreator()``; keyed on
    ``vtkMRMLTerritoriesHighlightDisplayNode``.
    """

    def __init__(self) -> None:
        super().__init__()
        self.SetPythonObject(self)

        self._display_node: Any | None = None
        self._renderer: Any | None = None
        self._observer_tags: dict = {}
        self._observed_node_refs: list = []

        # Injectable pick core (bare unit layer feeds a known surface);
        # rebuilt when the display node is (re)attached, since that is
        # where the pickSurface reference can change.  ``_pick_injected``
        # marks a test-injected core (never rebuilt); the production core is
        # rebuilt when segment visibility changes (``_pick_surface_mtime``).
        self._pick: VesselSurfacePick | None = None
        self._pick_injected: bool = False
        self._pick_surface_mtime: int | None = None

        # Last adhering (point, on-surface) a render was requested for —
        # the digest gate that keeps a fixed cursor from storming renders.
        self._last_render_key: tuple | None = None

        # -- marker: a sphere glyph adhering to the surface -------------- #
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

    # ------------------------------------------------------------------ #
    # LayerDM lifecycle
    # ------------------------------------------------------------------ #

    def SetDisplayNode(self, displayNode: Any) -> None:  # noqa: N802 - VTK verb
        if self._display_node is not None:
            self._detach_observer(self._display_node)

        super().SetDisplayNode(displayNode)

        self._display_node = displayNode
        if displayNode is not None:
            self._attach_observer(displayNode)
        # Force a pick-core rebuild against the (possibly new) surface.
        self._pick = None

    def OnRendererAdded(self, renderer: Any) -> None:  # noqa: N802 - VTK verb
        try:
            self._renderer = renderer
            if renderer is not None:
                renderer.AddActor(self._marker_actor)
            # Renderer churn cleared the display handle; re-derive it from
            # the base's retained display node so styling does not silently
            # fall back to VTK defaults (the ControlPolygonPipeline
            # re-attach precedent).
            if self._display_node is None:
                display = self.GetDisplayNode()
                if display is not None:
                    self.SetDisplayNode(display)
            self.UpdatePipeline()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    def OnRendererRemoved(self, renderer: Any) -> None:  # noqa: N802 - VTK verb
        try:
            if renderer is not None:
                renderer.RemoveActor(self._marker_actor)
            self._renderer = None
            self.cleanup()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    def UpdatePipeline(self) -> None:  # noqa: N802 - VTK verb
        """Sync the marker actor to the display node's adhering state."""
        try:
            self._reconcile()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    def _reconcile(self) -> None:
        display = self._display_node
        if display is None:
            self._marker_actor.SetVisibility(False)
            return
        try:
            self._marker_sphere.SetRadius(float(display.GetRadius()))
        except Exception:  # pragma: no cover - defensive
            pass
        color = display.GetColor()
        self._marker_actor.GetProperty().SetColor(color[0], color[1], color[2])

        adhering = bool(display.GetAdhering()) and bool(display.GetVisibility())
        self._marker_actor.SetVisibility(adhering)
        if adhering:
            point = display.GetAdheringPointWorld()
            self._marker_actor.SetPosition(point[0], point[1], point[2])

    def cleanup(self) -> None:
        for node in list(self._observed_node_refs):
            self._detach_observer(node)
        self._display_node = None
        self._pick = None
        self._marker_actor.SetVisibility(False)

    # ------------------------------------------------------------------ #
    # Interaction — the hover (ADR-0033 discipline)
    # ------------------------------------------------------------------ #

    def CanProcessInteractionEvent(self, eventData: Any):  # noqa: N802 - VTK verb
        """Return ``(canProcess, distance2)`` for the LayerDM focus logic.

        A bare mouse move updates the adhering marker as a SIDE EFFECT and
        DECLINES (returns ``False``, distance ``float_info.max``) so the
        camera manipulation the move belongs to is untouched (ADR-0033).
        No other event is claimed: the highlight is a passive hover cue.
        """
        try:
            renderer = self._safe_get_renderer()
            if renderer is None:
                return False, sys.float_info.max
            if _event_type(eventData) == vtk.vtkCommand.MouseMoveEvent:
                self._update_highlight(renderer, eventData)
            return False, sys.float_info.max
        except Exception:  # pragma: no cover - C++ boundary must never raise
            return False, sys.float_info.max

    def ProcessInteractionEvent(self, eventData: Any) -> bool:  # noqa: N802 - VTK verb
        """Never claims a gesture — the highlight is a passive hover cue."""
        del eventData
        return False

    def _update_highlight(self, renderer: Any, eventData: Any) -> None:
        """Resolve the adhering point under the cursor and publish it.

        Builds the cursor ray by unprojecting the event pixel at the near
        and far clipping depths, feeds it to the pick core against the
        referenced segmentation's closed surface, and writes the result
        (point + on/off-surface flag) onto the data-only display node.  An
        absent surface hides the marker.
        """
        display = self._display_node
        if display is None:
            return
        pick = self._ensure_pick()
        if pick is None:
            self._publish(adhering=False, point=None)
            return
        ray = self._cursor_ray(renderer, eventData)
        if ray is None:
            self._publish(adhering=False, point=None)
            return
        p1, p2 = ray
        # Off-surface hover hides the marker: no fallback projection, so
        # the cue reads honestly as "the cursor is on the mesh" (ADR-0033).
        world = pick.pick(p1, p2)
        self._publish(adhering=world is not None, point=world)

    def _publish(self, adhering: bool, point: Any) -> None:
        """Write the adhering state onto the display node (change-gated)."""
        display = self._display_node
        if display is None:
            return
        changed = False
        if bool(display.GetAdhering()) != adhering:
            display.SetAdhering(adhering)
            changed = True
        if adhering and point is not None:
            current = display.GetAdheringPointWorld()
            if tuple(current) != (point[0], point[1], point[2]):
                display.SetAdheringPointWorld(point[0], point[1], point[2])
                changed = True
        if changed:
            display.Modified()

    def _cursor_ray(self, renderer: Any, eventData: Any):
        """The world-space cursor ray ``(p1, p2)`` for the event pixel.

        ``p1`` (near clipping depth) is the ray origin toward the camera;
        ``p2`` (far clipping depth) is deeper into the scene.  ``None`` on
        an unresolvable back-projection.
        """
        try:
            ex, ey = eventData.GetDisplayPosition()
        except Exception:  # pragma: no cover - defensive (fake events)
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

    # ------------------------------------------------------------------ #
    # Pick-core lifecycle
    # ------------------------------------------------------------------ #

    def _ensure_pick(self) -> VesselSurfacePick | None:
        """Build the pick core against the referenced segmentation's mesh.

        Resolves the display node's ``pickSurface`` segmentation, ensures a
        closed-surface representation, and rebuilds the pick core when the
        referenced node's segment VISIBILITY changes (tracked via the display
        node MTime).  ``None`` when no surface is wired.  A test-injected
        ``self._pick`` short-circuits this in the bare unit layer.
        """
        if self._pick_injected:
            return self._pick
        display = self._display_node
        if display is None:
            return None
        segmentation = display.GetPickSurfaceNode()
        if segmentation is None:
            return None
        mtime = _visibility_mtime(segmentation)
        if self._pick is not None and mtime == self._pick_surface_mtime:
            return self._pick
        # Shared surface-resolution seam (VesselHighlightWiring): the hover
        # Pipeline and the snap-on-place path resolve the pick target the same
        # way -- VISIBLE vessels only, so hover never lights up the parenchyma,
        # a tumour, or a hidden vessel (ADR-0037 slice 5).
        self._pick = None
        self._pick_surface_mtime = mtime
        polydata = vascular_surface_polydata(segmentation)
        if polydata is None:
            return None
        self._pick = VesselSurfacePick(polydata)
        return self._pick

    # ------------------------------------------------------------------ #
    # Introspection (unit tests) + plumbing
    # ------------------------------------------------------------------ #

    def GetMarkerActor(self) -> Any:  # noqa: N802 - VTK verb
        return self._marker_actor

    def SetPickCore(self, pick: VesselSurfacePick | None) -> None:  # noqa: N802 - VTK verb
        """Inject a pick core (bare unit layer seam)."""
        self._pick = pick
        self._pick_injected = pick is not None

    def _safe_get_renderer(self) -> Any | None:
        return self._renderer

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
        """Re-sync the marker and repaint when the adhering state changed.

        The render request is gated on the (adhering, point) tuple actually
        changing (the ControlPolygonPipeline digest pattern): a hover that
        moves the marker repaints, a render-induced ``Modified`` at fixed
        state does not — no render feedback loop.
        """
        del caller, event
        try:
            self.UpdatePipeline()
            display = self._display_node
            adhering = bool(display.GetAdhering()) if display is not None else False
            point = tuple(display.GetAdheringPointWorld()) if display is not None else ()
            render_key = (adhering, point if adhering else ())
            if render_key == self._last_render_key:
                return
            self._last_render_key = render_key
            self.RequestRender()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass


def _event_type(eventData: Any) -> int:  # noqa: N803 - VTK arg name
    """The VTK event-type id off ``eventData``."""
    return int(eventData.GetType())


def registerVesselHighlightPipelineCreator() -> None:  # noqa: N802 - project convention
    """Register the ``VesselHighlightPipeline`` creator with LayerDM.

    Idempotent (module-level flag), mirroring
    ``registerControlPolygonPipelineCreator``.  The creator matches
    ``(vtkMRMLViewNode, vtkMRMLTerritoriesHighlightDisplayNode)`` — the 3D
    views only; the highlight is a 3D-surface interaction (ADR-0013 §5
    call 3).
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
            return VesselHighlightPipeline()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            return None

    creator = vtkMRMLLayerDMPipelineScriptedCreator()
    creator.SetPythonCallback(tryCreate)
    vtkMRMLLayerDMPipelineFactory.GetInstance().AddPipelineCreator(creator)
    _REGISTERED = True

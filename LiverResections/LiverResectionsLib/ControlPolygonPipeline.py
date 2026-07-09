# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""LayerDM Pipeline for the parametric surface's control polygon (ADR-0033).

The control polygon -- the ``Rows x Cols`` control-point handles plus their
connecting edges -- is a first-class display aspect of the Bezier carrier,
keyed on its OWN display node (``vtkMRMLControlPolygonDisplayNode``, the
carrier's second display node) per ADR-0013 §1: one Pipeline per display-node
type.  This Pipeline:

* renders the handles (plain-VTK sphere glyphs over the control grid) and the
  polygon edges (``vtkSlicerLiverBezierControlPolygonGeometry.
  BuildControlPolygonCells`` -- the Algorithm-library SSOT shared with the
  v2.1 NURBS sibling per ADR-0018);
* is state-gated: visible in ``Planning`` only (ADR-0019 state machine;
  preserves the Confirmed-hides-polygon behaviour of ADR-0014);
* HOSTS the Planning per-point drag (ADR-0033 supersedes the ADR-0032 siting
  on ``LiverBezierSurfacePipeline``): ``CanProcessInteractionEvent`` returns
  the real display-space distance to the nearest handle, so LayerDM's focus
  arbitration has something meaningful to arbitrate.

The Init-mode placements (slicing-plane / distance-spheroid points) are
surface/init interactions and stay on ``LiverBezierSurfacePipeline``.
"""

from __future__ import annotations

from typing import Any

import vtk

from LayerDMLib import vtkMRMLLayerDMScriptedPipeline as _PipelineBase

# State constants + safe accessors shared with the sibling Pipeline (single
# source within this package; the integers mirror the C++ enum on
# vtkMRMLBezierSurfaceNode).
try:  # pragma: no cover - exercised once per import path
    from .LiverBezierSurfacePipeline import (
        STATE_PLANNING,
        _safe_get_mtime,
        _safe_get_state,
    )
except ImportError:  # top-level import path (the unit layer's sys.path setup)
    from LiverBezierSurfacePipeline import (  # type: ignore[no-redef]
        STATE_PLANNING,
        _safe_get_mtime,
        _safe_get_state,
    )

#: The Algorithm-library cells builder (reachable only via the
#: vtkSlicerLiverResectionsModuleAlgorithmPython wrapping inside a launched
#: Slicer -- NOT on the ``slicer``/``vtk`` namespaces).
CONTROL_POLYGON_GEOMETRY_CLASS = "vtkSlicerLiverBezierControlPolygonGeometry"

#: Display-space pick radius for the per-point drag, in pixels (the ADR-0032
#: value, unchanged by the ADR-0033 re-siting).
CONTROL_POINT_PICK_RADIUS_PX = 20.0

#: Halo colours: warm hover cue vs the distinct GRABBED (active-drag) cue.
HALO_HOVER_COLOR = (1.0, 0.9, 0.2)
HALO_GRAB_COLOR = (0.3, 1.0, 0.4)
#: Halo radius scale vs the handle: hover ring vs the larger GRAB ring
#: (the size jump reads even where the glow blur washes the hue out).
HALO_HOVER_SCALE = 1.35
HALO_GRAB_SCALE = 1.9

#: World-space dash pattern for the polygon edge tubes -- the same
#: dashed-scaffold language the slice projections use, so the control
#: polygon reads consistently across every view.
DASH_LENGTH_MM = 6.0
GAP_LENGTH_MM = 4.0

_REGISTERED = False


def _resolve_control_polygon_geometry() -> Any | None:
    """Resolve the wrapped Algorithm cells-builder class, or ``None``.

    Algorithm-library classes are exposed ONLY on the
    ``vtkSlicerLiverResectionsModuleAlgorithmPython`` wrapping (never on the
    ``slicer`` / ``vtk`` namespaces).  ``None`` in the bare-VTK unit layer,
    where tests inject a fake via the ``_control_polygon_geometry`` seam.
    """
    try:
        import vtkSlicerLiverResectionsModuleAlgorithmPython as algorithm
    except ImportError:
        return None
    return getattr(algorithm, CONTROL_POLYGON_GEOMETRY_CLASS, None)


class ControlPolygonPipeline(_PipelineBase):
    """Renders + edits the control polygon of a parametric surface carrier.

    Created by LayerDM's manager via the creator registered by
    ``registerControlPolygonPipelineCreator()``; keyed on
    ``vtkMRMLControlPolygonDisplayNode`` (ADR-0033).
    """

    def __init__(self) -> None:
        super().__init__()
        self.SetPythonObject(self)

        self._display_node: Any | None = None
        self._data_node: Any | None = None
        self._renderer: Any | None = None
        self._observer_tags: dict = {}
        self._observed_node_refs: list = []

        # Injectable Algorithm-builder seam (bare-VTK unit layer); resolved
        # lazily from the wrapping on first use in production.
        self._control_polygon_geometry: Any | None = None
        #: (rows, cols) the current edge cells were built for.
        self._edge_cells_shape: tuple | None = None

        self._last_update_key: Any | None = None
        self._update_count = 0

        # Last (state, geometry-digest) a render was requested for — the
        # observer callback's render-request gate (see ``_on_node_modified``).
        self._last_render_key: tuple | None = None

        # Flat row-major index of the handle currently GRABBED by the
        # press/move/release gesture — None when no drag is in flight.
        self._drag_index: int | None = None

        # -- handles: control-point sphere glyphs ------------------------- #
        self._handles_polydata = vtk.vtkPolyData()
        self._handles_polydata.SetPoints(vtk.vtkPoints())
        self._handle_sphere = vtk.vtkSphereSource()
        self._handle_sphere.SetPhiResolution(12)
        self._handle_sphere.SetThetaResolution(12)
        self._handles_glyph = vtk.vtkGlyph3D()
        self._handles_glyph.SetInputData(self._handles_polydata)
        self._handles_glyph.SetSourceConnection(self._handle_sphere.GetOutputPort())
        self._handles_glyph.ScalingOff()
        self._handles_mapper = vtk.vtkPolyDataMapper()
        self._handles_mapper.SetInputConnection(self._handles_glyph.GetOutputPort())
        self._handles_actor = vtk.vtkActor()
        self._handles_actor.SetMapper(self._handles_mapper)

        # -- edges: the control polygon ----------------------------------- #
        # Rendered as world-space TUBES, not GL lines: line width is a pixel
        # quantity that reads hairline-thin over a liver-scale scene, while
        # a tube shares the handles' world metric (the display node's
        # EdgeWidth is the tube radius in mm).
        self._edges_polydata = vtk.vtkPolyData()
        self._edges_polydata.SetPoints(vtk.vtkPoints())
        self._edges_tube = vtk.vtkTubeFilter()
        self._edges_tube.SetInputData(self._edges_polydata)
        self._edges_tube.SetNumberOfSides(12)
        self._edges_mapper = vtk.vtkPolyDataMapper()
        self._edges_mapper.SetInputConnection(self._edges_tube.GetOutputPort())
        self._edges_actor = vtk.vtkActor()
        self._edges_actor.SetMapper(self._edges_mapper)

        # Hidden until a Planning-state carrier arrives.
        self._handles_actor.SetVisibility(False)
        self._edges_actor.SetVisibility(False)

        # -- hover halo: glow highlight for the handle under the cursor --- #
        # A slightly larger sphere on a PRIVATE overlay renderer carrying a
        # vtkOutlineGlowPass (the blur-to-halo pass).  The overlay renderer
        # is required because qMRMLThreeDView resets SetPass(nullptr) on the
        # view renderer on every view-node ModifiedEvent (the resectogram
        # blur-pass precedent).  Hover state is fed by the arbitration
        # moves CanProcessInteractionEvent already receives -- bare moves
        # stay declined, so camera interaction is untouched.
        self._hover_index: int | None = None
        self._halo_sphere = vtk.vtkSphereSource()
        self._halo_sphere.SetPhiResolution(16)
        self._halo_sphere.SetThetaResolution(16)
        self._halo_mapper = vtk.vtkPolyDataMapper()
        self._halo_mapper.SetInputConnection(self._halo_sphere.GetOutputPort())
        self._halo_actor = vtk.vtkActor()
        self._halo_actor.SetMapper(self._halo_mapper)
        self._halo_actor.GetProperty().SetColor(*HALO_HOVER_COLOR)
        self._halo_actor.SetVisibility(False)
        self._halo_renderer: Any | None = None

    # ------------------------------------------------------------------ #
    # LayerDM lifecycle
    # ------------------------------------------------------------------ #

    def SetDisplayNode(self, displayNode: Any) -> None:  # noqa: N802 - VTK verb
        """Attach the display node, derive the data node, wire observers."""
        if self._display_node is not None:
            self._detach_observer(self._display_node)
        if self._data_node is not None:
            self._detach_observer(self._data_node)

        super().SetDisplayNode(displayNode)

        self._display_node = displayNode
        self._data_node = None
        if displayNode is not None:
            getter = getattr(displayNode, "GetDisplayableNode", None)
            if getter is not None:
                self._data_node = getter()
            self._attach_observer(displayNode)
            if self._data_node is not None:
                self._attach_observer(self._data_node)
        self._last_update_key = None

    def OnReferenceToDisplayNodeAdded(self, fromNode: Any, role: Any = None) -> None:  # noqa: N802 - VTK verb
        """Adopt the displayable when it links to our display node late.

        Same late-binding contract as the sibling surface Pipeline: the
        production creation ordering hands ``SetDisplayNode`` a display node
        whose displayable link does not exist yet; the LayerDM manager calls
        this hook at the exact link moment with ``fromNode`` == the carrier.
        """
        if self._data_node is None and fromNode is not None and fromNode is not self._display_node:
            self._data_node = fromNode
            self._attach_observer(fromNode)
            self._last_update_key = None
        self.UpdatePipeline()

    def OnRendererAdded(self, renderer: Any) -> None:  # noqa: N802 - VTK verb
        self._renderer = renderer
        if renderer is not None:
            renderer.AddActor(self._edges_actor)
            renderer.AddActor(self._handles_actor)
        # ``OnRendererRemoved`` -> ``cleanup()`` cleared the node handles;
        # re-derive them from the base's retained display node, or the
        # renderer churn leaves the pipeline displayless forever and every
        # styling field silently stays at the raw VTK defaults (the
        # tiny-handles / hairline-white-edges failure mode).  Mirrors the
        # ResectogramPipeline's OnRendererAdded re-attach.
        if self._display_node is None:
            base_getter = getattr(self, "GetDisplayNode", None)
            display = base_getter() if base_getter is not None else None
            if display is not None:
                self.SetDisplayNode(display)
        self._attach_halo_renderer(renderer)
        self._last_update_key = None
        self.UpdatePipeline()

    def _attach_halo_renderer(self, renderer: Any) -> None:
        """Build the private glow overlay on ``renderer``'s window.

        A dedicated overlay ``vtkRenderer`` (camera shared with the view
        renderer) carries the halo actor and a ``vtkOutlineGlowPass`` -- the
        blur-to-halo pass -- so qMRMLThreeDView's SetPass(nullptr) reset on
        the VIEW renderer never clobbers it (the resectogram blur-pass
        precedent).  Degrades to the plain halo sphere when the pass class
        or the render window is unavailable (bare unit layer).
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

    def OnRendererRemoved(self, renderer: Any) -> None:  # noqa: N802 - VTK verb
        if renderer is not None:
            try:
                renderer.RemoveActor(self._handles_actor)
                renderer.RemoveActor(self._edges_actor)
            except Exception:  # pragma: no cover - defensive
                pass
        self._renderer = None
        self.cleanup()

    def UpdatePipeline(self) -> None:  # noqa: N802 - VTK verb
        """Reconcile handles + edges against the carrier grid and display."""
        # Late-bind the data node (creation-ordering tolerance; see
        # OnReferenceToDisplayNodeAdded).
        if self._data_node is None and self._display_node is not None:
            getter = getattr(self._display_node, "GetDisplayableNode", None)
            displayable = getter() if getter is not None else None
            if displayable is not None:
                self._data_node = displayable
                self._attach_observer(displayable)
                self._last_update_key = None

        state = _safe_get_state(self._data_node)
        key = (
            state,
            _safe_get_mtime(self._data_node),
            _safe_get_mtime(self._display_node),
        )
        if key == self._last_update_key:
            return
        self._last_update_key = key
        self._update_count += 1

        visible = self._compute_visibility(state)
        self._handles_actor.SetVisibility(visible)
        self._edges_actor.SetVisibility(visible)
        if visible:
            self._refresh_geometry()
        self._apply_display_node()
        self._apply_interaction_scalars()
        self._sync_halo_from_channel(visible)

    def cleanup(self) -> None:
        for node in list(self._observed_node_refs):
            self._detach_observer(node)
        self._display_node = None
        self._data_node = None
        self._drag_index = None
        self._hover_index = None
        self._halo_actor.SetVisibility(False)
        self._detach_halo_renderer()

    # ------------------------------------------------------------------ #
    # Interaction -- the Planning per-point drag (ADR-0033, ex ADR-0032)
    # ------------------------------------------------------------------ #

    def CanProcessInteractionEvent(self, eventData: Any):  # noqa: N802 - VTK verb
        """Return ``(canProcess, distance2)`` for the LayerDM focus logic.

        The per-point edit is a press/move/release GRAB, not proximity
        chasing: without a grab, only a LEFT-BUTTON PRESS within
        ``CONTROL_POINT_PICK_RADIUS_PX`` of a handle is claimed (with the
        real squared display distance as the arbitration value, ADR-0033);
        while a handle is grabbed, mouse moves and the ending release are
        claimed unconditionally (distance2 0 -- the grab owns the gesture).
        A hover move never edits: claiming bare moves made a released mouse
        keep deforming the surface on mere proximity.
        """
        import sys

        if _safe_get_state(self._data_node) != STATE_PLANNING:
            self._drag_index = None  # a state flip mid-gesture drops the grab
            return False, sys.float_info.max
        renderer = self._safe_get_renderer()
        if renderer is None:
            self._drag_index = None
            return False, sys.float_info.max

        etype = _event_type(eventData)
        if self._drag_index is not None:
            if etype in (
                vtk.vtkCommand.MouseMoveEvent,
                vtk.vtkCommand.LeftButtonReleaseEvent,
            ):
                return True, 0.0
            return False, sys.float_info.max

        if etype == vtk.vtkCommand.MouseMoveEvent:
            # Bare hover: update the halo highlight as a SIDE EFFECT of the
            # arbitration call and decline -- camera moves stay unclaimed.
            idx, distance2 = self._nearest_control_point_in_display(renderer, eventData)
            within = (
                idx is not None
                and distance2 <= CONTROL_POINT_PICK_RADIUS_PX * CONTROL_POINT_PICK_RADIUS_PX
            )
            self._set_hover(idx if within else None)
            return False, sys.float_info.max
        if etype != vtk.vtkCommand.LeftButtonPressEvent:
            return False, sys.float_info.max
        _, distance2 = self._nearest_control_point_in_display(renderer, eventData)
        if distance2 <= CONTROL_POINT_PICK_RADIUS_PX * CONTROL_POINT_PICK_RADIUS_PX:
            return True, distance2
        return False, sys.float_info.max

    def _set_hover(self, index: int | None) -> None:
        """Show/move the halo on handle ``index`` (``None`` hides it).

        Idempotent per hover change: repositions the halo, syncs its radius
        to the handle glyphs (scaled up so the glow reads as a ring), and
        requests exactly one render when the hovered handle actually
        changed.
        """
        if index == self._hover_index:
            return
        self._hover_index = index
        self._publish_interaction_state(hovered=(-1 if index is None else index))
        if index is None:
            self._halo_actor.SetVisibility(False)
        else:
            carrier = self._data_node
            grid_getter = getattr(carrier, "GetControlGridVector", None) if carrier else None
            if grid_getter is None:
                return
            try:
                grid = grid_getter()
                base = int(index) * 3
                self._halo_sphere.SetRadius(self._handle_sphere.GetRadius() * HALO_HOVER_SCALE)
                self._halo_actor.SetPosition(grid[base], grid[base + 1], grid[base + 2])
                self._halo_actor.SetVisibility(True)
            except Exception:  # pragma: no cover - defensive
                return
        request_render = getattr(self, "RequestRender", None)
        if request_render is not None:
            try:
                request_render()
            except Exception:  # pragma: no cover - defensive (stub bases)
                pass

    def _publish_interaction_state(self, hovered=None, grabbed=None) -> None:
        """Write hover/grab onto the DISPLAY node (cross-view channel).

        Every pipeline observing the control-polygon display node -- the 3D
        one and the slice projections -- highlights the same point,
        whichever view the cursor is in (the markups active-control-point
        convention).  Writes only on change so mouse moves do not storm
        Modified events.  ``None`` leaves a channel untouched; use -1 to
        clear.
        """
        display = self._display_node
        if display is None:
            return
        try:
            if hovered is not None:
                value = -1 if hovered == -1 else int(hovered)
                if display.GetHoveredControlPoint() != value:
                    display.SetHoveredControlPoint(value)
            if grabbed is not None:
                value = -1 if grabbed == -1 else int(grabbed)
                if display.GetGrabbedControlPoint() != value:
                    display.SetGrabbedControlPoint(value)
        except Exception:  # pragma: no cover - defensive (stub displays)
            return

    def _sync_halo_from_channel(self, polygon_visible: bool) -> None:
        """Drive the glow halo from the display-node interaction channel.

        The channel is the single source of truth, so a hover raised in a
        SLICE view shows the same 3D halo a local hover does; the grabbed
        point wins over a hover, and the halo repositions on every carrier
        reconcile (drags move the point under it).
        """
        display = self._display_node
        try:
            hovered = display.GetHoveredControlPoint() if display is not None else -1
            grabbed = display.GetGrabbedControlPoint() if display is not None else -1
        except Exception:  # pragma: no cover - defensive (stub displays)
            hovered, grabbed = -1, -1
        target = grabbed if grabbed >= 0 else hovered
        if not polygon_visible or target < 0:
            self._halo_actor.SetVisibility(False)
            return
        carrier = self._data_node
        grid_getter = getattr(carrier, "GetControlGridVector", None) if carrier else None
        if grid_getter is None:
            return
        try:
            grid = grid_getter()
            base = int(target) * 3
            if len(grid) < base + 3:
                return
            self._halo_sphere.SetRadius(self._handle_sphere.GetRadius() * HALO_HOVER_SCALE)
            self._halo_actor.SetPosition(grid[base], grid[base + 1], grid[base + 2])
            self._halo_actor.SetVisibility(True)
        except Exception:  # pragma: no cover - defensive
            return

    def _apply_interaction_scalars(self) -> None:
        """Colour the hovered/grabbed HANDLES from the display-node state.

        Derives per-point glyph scalars from the display node's
        HoveredControlPoint / GrabbedControlPoint, so highlights raised in
        OTHER views (the slice projections) colour this 3D view too.
        """
        display = self._display_node
        try:
            hovered = display.GetHoveredControlPoint() if display is not None else -1
            grabbed = display.GetGrabbedControlPoint() if display is not None else -1
        except Exception:  # pragma: no cover - defensive (stub displays)
            hovered, grabbed = -1, -1
        try:
            points = self._handles_polydata.GetPoints()
            n = points.GetNumberOfPoints() if points is not None else 0
            base = [int(c * 255) for c in self._handles_actor.GetProperty().GetColor()]
            grab = [int(c * 255) for c in HALO_GRAB_COLOR]
            hover = [int(c * 255) for c in HALO_HOVER_COLOR]
            colors = vtk.vtkUnsignedCharArray()
            colors.SetNumberOfComponents(3)
            colors.SetName("HandleColors")
            for i in range(n):
                rgb = grab if i == grabbed else (hover if i == hovered else base)
                colors.InsertNextTuple3(*rgb)
            self._handles_polydata.GetPointData().SetScalars(colors)
            self._handles_glyph.SetColorModeToColorByScalar()
            self._handles_mapper.SetColorModeToDirectScalars()
            self._handles_mapper.SetScalarVisibility(grabbed >= 0 or hovered >= 0)
            self._handles_polydata.Modified()
        except Exception:  # pragma: no cover - defensive
            return

    def GetHaloActor(self) -> Any:  # noqa: N802 - VTK verb
        return self._halo_actor

    def ProcessInteractionEvent(self, eventData: Any) -> bool:  # noqa: N802 - VTK verb
        """Drive the press/move/release grab (Planning edit).

        Press within the pick radius grabs the nearest handle and returns
        True (the interaction logic keeps focus on a pipeline that returns
        True); moves while grabbed edit THE GRABBED handle -- not whichever
        is momentarily nearest -- so the gesture cannot hop between points;
        the release clears the grab and returns False, releasing the focus.
        """
        renderer = self._safe_get_renderer()
        if renderer is None:
            self._drag_index = None
            return False
        if _safe_get_state(self._data_node) != STATE_PLANNING:
            self._drag_index = None
            return False

        etype = _event_type(eventData)

        if self._drag_index is None:
            if etype != vtk.vtkCommand.LeftButtonPressEvent:
                return False
            idx, distance2 = self._nearest_control_point_in_display(renderer, eventData)
            if (
                idx is None
                or distance2 > CONTROL_POINT_PICK_RADIUS_PX * CONTROL_POINT_PICK_RADIUS_PX
            ):
                return False
            self._drag_index = idx
            self._publish_interaction_state(grabbed=idx)
            self._apply_interaction_scalars()
            hover, self._hover_index = idx, None
            self._set_hover(hover)  # halo jumps to the grabbed handle
            world = self._event_world_at_control_point(renderer, eventData, idx)
            if world is not None:
                self._apply_world_point_to_control_point(idx, world)
            return True

        if etype == vtk.vtkCommand.LeftButtonReleaseEvent:
            self._drag_index = None
            self._publish_interaction_state(grabbed=-1)
            self._apply_interaction_scalars()
            self._set_hover(None)
            return False  # grab over -- release the focus

        if etype == vtk.vtkCommand.MouseMoveEvent:
            world = self._event_world_at_control_point(
                renderer, eventData, self._drag_index
            )
            if world is None:
                return True  # keep the grab; this move just didn't resolve
            self._apply_world_point_to_control_point(self._drag_index, world)
            hover, self._hover_index = self._drag_index, None
            self._set_hover(hover)  # halo follows the grabbed handle
            return True

        return False

    def _apply_world_point_to_control_point(self, index: int, world: Any) -> bool:
        """Move the carrier's control point ``index`` to RAS ``world``.

        The grabbed-index write kernel: unlike the nearest-point kernel it
        never re-picks, so a drag cannot hop to another handle mid-gesture.
        Refuses outside ``Planning`` (ADR-0019).
        """
        carrier = self._data_node
        if carrier is None or _safe_get_state(carrier) != STATE_PLANNING:
            return False
        cols_getter = getattr(carrier, "GetCols", None)
        set_point = getattr(carrier, "SetControlPoint", None)
        if None in (cols_getter, set_point):
            return False
        try:
            cols = int(cols_getter())
            set_point(
                int(index) // cols,
                int(index) % cols,
                float(world[0]),
                float(world[1]),
                float(world[2]),
            )
        except Exception:  # pragma: no cover - defensive
            return False
        return True

    def _apply_world_point_to_nearest_control_point(self, world: Any) -> int | None:
        """Move the carrier's nearest control point to RAS ``world``.

        The GL-free interaction kernel (ADR-0032 mechanics, re-sited here by
        ADR-0033): finds the carrier's control point nearest ``world``, moves
        it via ``SetControlPoint``, and returns its flat row-major index.  A
        no-op returning ``None`` when the carrier is absent or not in
        ``Planning`` (ADR-0019).
        """
        carrier = self._data_node
        if carrier is None or _safe_get_state(carrier) != STATE_PLANNING:
            return None
        rows_getter = getattr(carrier, "GetRows", None)
        cols_getter = getattr(carrier, "GetCols", None)
        grid_getter = getattr(carrier, "GetControlGridVector", None)
        set_point = getattr(carrier, "SetControlPoint", None)
        if None in (rows_getter, cols_getter, grid_getter, set_point):
            return None
        try:
            rows = int(rows_getter())
            cols = int(cols_getter())
            grid = grid_getter()
            wx, wy, wz = float(world[0]), float(world[1]), float(world[2])
        except Exception:  # pragma: no cover - defensive
            return None

        best_idx = None
        best_d2 = None
        for i in range(rows * cols):
            dx = grid[i * 3 + 0] - wx
            dy = grid[i * 3 + 1] - wy
            dz = grid[i * 3 + 2] - wz
            d2 = dx * dx + dy * dy + dz * dz
            if best_d2 is None or d2 < best_d2:
                best_d2 = d2
                best_idx = i
        if best_idx is None:
            return None
        set_point(best_idx // cols, best_idx % cols, wx, wy, wz)
        return best_idx

    def _nearest_control_point_in_display(self, renderer: Any, eventData: Any):
        """``(flat_index, distance2)`` of the handle nearest the event pixel."""
        import sys

        carrier = self._data_node
        grid_getter = getattr(carrier, "GetControlGridVector", None) if carrier else None
        cols_getter = getattr(carrier, "GetCols", None) if carrier else None
        rows_getter = getattr(carrier, "GetRows", None) if carrier else None
        if None in (grid_getter, cols_getter, rows_getter):
            return None, sys.float_info.max
        try:
            grid = grid_getter()
            rows = int(rows_getter())
            cols = int(cols_getter())
            ex, ey = eventData.GetDisplayPosition()
        except Exception:  # pragma: no cover - defensive
            return None, sys.float_info.max

        best_idx = None
        best_d2 = sys.float_info.max
        for i in range(rows * cols):
            renderer.SetWorldPoint(grid[i * 3 + 0], grid[i * 3 + 1], grid[i * 3 + 2], 1.0)
            renderer.WorldToDisplay()
            dx, dy, _dz = renderer.GetDisplayPoint()
            d2 = (dx - ex) ** 2 + (dy - ey) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best_idx = i
        return best_idx, best_d2

    def _event_world_at_control_point(self, renderer: Any, eventData: Any, idx: int):
        """Back-project the event pixel onto control point ``idx``'s depth."""
        carrier = self._data_node
        grid_getter = getattr(carrier, "GetControlGridVector", None) if carrier else None
        cols_getter = getattr(carrier, "GetCols", None) if carrier else None
        if None in (grid_getter, cols_getter):
            return None
        try:
            grid = grid_getter()
            ex, ey = eventData.GetDisplayPosition()
            renderer.SetWorldPoint(grid[idx * 3 + 0], grid[idx * 3 + 1], grid[idx * 3 + 2], 1.0)
            renderer.WorldToDisplay()
            _dx, _dy, dz = renderer.GetDisplayPoint()
            renderer.SetDisplayPoint(float(ex), float(ey), dz)
            renderer.DisplayToWorld()
            wx, wy, wz, ww = renderer.GetWorldPoint()
        except Exception:  # pragma: no cover - defensive
            return None
        if ww == 0.0:
            return None
        return (wx / ww, wy / ww, wz / ww)

    # ------------------------------------------------------------------ #
    # Geometry + styling
    # ------------------------------------------------------------------ #

    def _compute_visibility(self, state: Any) -> bool:
        """Planning-only, further gated by the display node's Visibility."""
        if state != STATE_PLANNING:
            return False
        display = self._display_node
        vis_getter = getattr(display, "GetVisibility", None) if display else None
        if vis_getter is not None:
            try:
                return bool(vis_getter())
            except Exception:  # pragma: no cover - defensive
                return True
        return True

    def _refresh_geometry(self) -> None:
        """Rebuild handle points + polygon edges from the carrier grid."""
        carrier = self._data_node
        grid_getter = getattr(carrier, "GetControlGridVector", None) if carrier else None
        if grid_getter is None:
            grid_getter = getattr(carrier, "GetControlGrid", None) if carrier else None
        if grid_getter is None:
            return
        rows = int(getattr(carrier, "GetRows", lambda: 4)())
        cols = int(getattr(carrier, "GetCols", lambda: 4)())
        try:
            raw = grid_getter()
            points = vtk.vtkPoints()
            points.SetNumberOfPoints(rows * cols)
            for i in range(rows * cols):
                points.SetPoint(i, float(raw[i * 3]), float(raw[i * 3 + 1]), float(raw[i * 3 + 2]))
        except Exception:  # pragma: no cover - defensive
            return

        self._handles_polydata.SetPoints(points)
        self._handles_polydata.Modified()

        # DASHED edge tubes: the Algorithm builder stays the topology SSOT
        # (which points connect), but each of its polyline runs is emitted
        # as world-space dash segments before tubing -- the same dashed-
        # scaffold language the slice projections use.
        shape = (rows, cols)
        if shape != self._edge_cells_shape:
            geometry = self._control_polygon_geometry
            if geometry is None:
                geometry = _resolve_control_polygon_geometry()
                self._control_polygon_geometry = geometry
            if geometry is not None:
                cells = geometry.BuildControlPolygonCells(rows, cols)
                if cells is not None:
                    self._edge_cells = cells
                    self._edge_cells_shape = shape
        self._rebuild_dashed_edges(points)
        self._edges_polydata.Modified()

    def _rebuild_dashed_edges(self, points: Any) -> None:
        """Emit the builder's polylines as world-space dash segments."""
        cells = getattr(self, "_edge_cells", None)
        if cells is None:
            return
        dash_points = vtk.vtkPoints()
        dash_lines = vtk.vtkCellArray()
        try:
            cells.InitTraversal()
            ids = vtk.vtkIdList()
            while cells.GetNextCell(ids):
                for k in range(ids.GetNumberOfIds() - 1):
                    a = points.GetPoint(ids.GetId(k))
                    b = points.GetPoint(ids.GetId(k + 1))
                    length = sum((b[j] - a[j]) ** 2 for j in range(3)) ** 0.5
                    if length <= 0.0:
                        continue
                    period = DASH_LENGTH_MM + GAP_LENGTH_MM
                    t = 0.0
                    while t < length:
                        t_end = min(t + DASH_LENGTH_MM, length)
                        f0, f1 = t / length, t_end / length
                        i0 = dash_points.InsertNextPoint(
                            *(a[j] + (b[j] - a[j]) * f0 for j in range(3))
                        )
                        i1 = dash_points.InsertNextPoint(
                            *(a[j] + (b[j] - a[j]) * f1 for j in range(3))
                        )
                        seg = vtk.vtkLine()
                        seg.GetPointIds().SetId(0, i0)
                        seg.GetPointIds().SetId(1, i1)
                        dash_lines.InsertNextCell(seg)
                        t += period
        except Exception:  # pragma: no cover - defensive
            return
        self._edges_polydata.SetPoints(dash_points)
        self._edges_polydata.SetLines(dash_lines)

    def _apply_display_node(self) -> None:
        """Push the display node's styling onto the actors."""
        display = self._display_node
        radius_getter = getattr(display, "GetHandleRadius", None) if display else None
        if radius_getter is not None:
            try:
                self._handle_sphere.SetRadius(float(radius_getter()))
            except Exception:  # pragma: no cover - defensive
                pass
        handle_color = getattr(display, "GetHandleColor", None) if display else None
        if handle_color is not None:
            try:
                c = handle_color()
                self._handles_actor.GetProperty().SetColor(float(c[0]), float(c[1]), float(c[2]))
            except Exception:  # pragma: no cover - defensive
                pass
        edge_color = getattr(display, "GetEdgeColor", None) if display else None
        if edge_color is not None:
            try:
                c = edge_color()
                self._edges_actor.GetProperty().SetColor(float(c[0]), float(c[1]), float(c[2]))
            except Exception:  # pragma: no cover - defensive
                pass
        edge_width = getattr(display, "GetEdgeWidth", None) if display else None
        if edge_width is not None:
            try:
                self._edges_tube.SetRadius(float(edge_width()))
            except Exception:  # pragma: no cover - defensive
                pass

    # ------------------------------------------------------------------ #
    # Introspection (unit tests) + plumbing
    # ------------------------------------------------------------------ #

    def GetDataNode(self) -> Any | None:  # noqa: N802 - VTK verb
        return self._data_node

    def GetHandlesActor(self) -> Any:  # noqa: N802 - VTK verb
        return self._handles_actor

    def GetEdgesActor(self) -> Any:  # noqa: N802 - VTK verb
        return self._edges_actor

    def GetHandlesPolyData(self) -> Any:  # noqa: N802 - VTK verb
        return self._handles_polydata

    def GetEdgesPolyData(self) -> Any:  # noqa: N802 - VTK verb
        return self._edges_polydata

    def GetUpdateCount(self) -> int:  # noqa: N802 - VTK verb
        return self._update_count

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
        """Re-run ``UpdatePipeline`` and repaint when the geometry changed.

        The render request is gated on the (state, control-point geometry
        digest) tuple actually changing (the ResectogramPipeline pattern):
        a Planning drag advances the digest and repaints the handles live;
        a render-induced ``Modified`` at fixed geometry does not re-request,
        so no render feedback loop.
        """
        del caller, event
        self.UpdatePipeline()

        display = self._display_node
        try:
            interaction = (
                display.GetHoveredControlPoint() if display is not None else -1,
                display.GetGrabbedControlPoint() if display is not None else -1,
            )
        except Exception:  # pragma: no cover - defensive (stub displays)
            interaction = (-1, -1)
        render_key = (
            _safe_get_state(self._data_node),
            _control_points_digest(self._data_node),
            interaction,
        )
        if render_key == self._last_render_key:
            return
        self._last_render_key = render_key

        request_render = getattr(self, "RequestRender", None)
        if request_render is not None:
            try:
                request_render()
            except Exception:  # pragma: no cover - defensive (stub bases)
                pass


def _event_type(eventData: Any) -> int | None:  # noqa: N803 - VTK arg name
    """Read the VTK event-type id off ``eventData`` defensively.

    ``None`` for events lacking ``GetType`` (stubs) or on a read failure —
    the callers then decline, so the grab state machine never raises from
    the interaction hot path.
    """
    getter = getattr(eventData, "GetType", None)
    if getter is None:
        return None
    try:
        return int(getter())
    except Exception:  # pragma: no cover - defensive
        return None


def _control_points_digest(node: Any) -> tuple:
    """Digest of the carrier's control-point positions (render-request gate).

    Mirrors the ResectogramPipeline's memo digest: a control-point edit
    changes the digest, a render-induced ``Modified`` at fixed geometry does
    not — the discrimination that keeps drags repainting live while blocking
    a render feedback loop.  Empty tuple for nodes missing the grid accessor
    (stubs) or on a read failure.
    """
    if node is None:
        return ()
    grid_getter = getattr(node, "GetControlGridVector", None)
    if grid_getter is None:
        return ()
    try:
        grid = grid_getter()
        usable = len(grid) - (len(grid) % 3)
        return tuple(
            (grid[base], grid[base + 1], grid[base + 2])
            for base in range(0, usable, 3)
        )
    except Exception:  # pragma: no cover - defensive
        return ()


def registerControlPolygonPipelineCreator() -> None:  # noqa: N802 - project convention
    """Register the ``ControlPolygonPipeline`` creator with LayerDM.

    Idempotent (module-level flag), mirroring ``registerPipelineCreator``.
    The creator matches ``(vtkMRMLViewNode, vtkMRMLControlPolygonDisplayNode)``
    and EXCLUDES the resectogram singleton view: that view is owned solely by
    the ResectogramPipeline (its strip + locator click seam), and leaking
    surface-family pipelines into it puts interactive actors where they do
    not belong.
    """
    global _REGISTERED
    if _REGISTERED:
        return

    from slicer import (  # type: ignore[import-not-found]
        vtkMRMLControlPolygonDisplayNode,
        vtkMRMLLayerDMPipelineFactory,
        vtkMRMLLayerDMPipelineScriptedCreator,
        vtkMRMLViewNode,
    )

    try:
        from .ResectogramViewManager import RESECTOGRAM_VIEW_SINGLETON_TAG
    except ImportError:  # pragma: no cover - top-level import path
        from ResectogramViewManager import (  # type: ignore[no-redef]
            RESECTOGRAM_VIEW_SINGLETON_TAG,
        )

    def tryCreate(viewNode, node):
        if not isinstance(viewNode, vtkMRMLViewNode):
            return None
        tag_getter = getattr(viewNode, "GetSingletonTag", None)
        if tag_getter is not None and tag_getter() == RESECTOGRAM_VIEW_SINGLETON_TAG:
            return None
        if not isinstance(node, vtkMRMLControlPolygonDisplayNode):
            return None
        return ControlPolygonPipeline()

    creator = vtkMRMLLayerDMPipelineScriptedCreator()
    creator.SetPythonCallback(tryCreate)
    vtkMRMLLayerDMPipelineFactory.GetInstance().AddPipelineCreator(creator)
    _REGISTERED = True

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
        self._edges_polydata = vtk.vtkPolyData()
        self._edges_polydata.SetPoints(vtk.vtkPoints())
        self._edges_mapper = vtk.vtkPolyDataMapper()
        self._edges_mapper.SetInputData(self._edges_polydata)
        self._edges_actor = vtk.vtkActor()
        self._edges_actor.SetMapper(self._edges_mapper)

        # Hidden until a Planning-state carrier arrives.
        self._handles_actor.SetVisibility(False)
        self._edges_actor.SetVisibility(False)

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
        self._last_update_key = None
        self.UpdatePipeline()

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

    def cleanup(self) -> None:
        for node in list(self._observed_node_refs):
            self._detach_observer(node)
        self._display_node = None
        self._data_node = None

    # ------------------------------------------------------------------ #
    # Interaction -- the Planning per-point drag (ADR-0033, ex ADR-0032)
    # ------------------------------------------------------------------ #

    def CanProcessInteractionEvent(self, eventData: Any):  # noqa: N802 - VTK verb
        """Return ``(canProcess, distance2)`` for the LayerDM focus logic.

        Claims the event iff the carrier is editable (``Planning``,
        ADR-0019) and the cursor is within ``CONTROL_POINT_PICK_RADIUS_PX``
        of a handle in display space.  ``distance2`` is the real squared
        display distance to the nearest handle -- the meaningful arbitration
        value ADR-0033 moves here for.
        """
        import sys

        if _safe_get_state(self._data_node) != STATE_PLANNING:
            return False, sys.float_info.max
        renderer = self._safe_get_renderer()
        if renderer is None:
            return False, sys.float_info.max
        _, distance2 = self._nearest_control_point_in_display(renderer, eventData)
        if distance2 <= CONTROL_POINT_PICK_RADIUS_PX * CONTROL_POINT_PICK_RADIUS_PX:
            return True, distance2
        return False, sys.float_info.max

    def ProcessInteractionEvent(self, eventData: Any) -> bool:  # noqa: N802 - VTK verb
        """Move the nearest control point to the cursor (Planning edit).

        Returns True iff geometry changed (the interaction logic keeps focus
        on a pipeline that returns True).
        """
        renderer = self._safe_get_renderer()
        if renderer is None:
            return False
        if _safe_get_state(self._data_node) != STATE_PLANNING:
            return False
        idx, distance2 = self._nearest_control_point_in_display(renderer, eventData)
        if idx is None or distance2 > CONTROL_POINT_PICK_RADIUS_PX * CONTROL_POINT_PICK_RADIUS_PX:
            return False
        world = self._event_world_at_control_point(renderer, eventData, idx)
        if world is None:
            return False
        return self._apply_world_point_to_nearest_control_point(world) is not None

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
        self._edges_polydata.SetPoints(points)

        shape = (rows, cols)
        if shape != self._edge_cells_shape:
            geometry = self._control_polygon_geometry
            if geometry is None:
                geometry = _resolve_control_polygon_geometry()
                self._control_polygon_geometry = geometry
            if geometry is not None:
                cells = geometry.BuildControlPolygonCells(rows, cols)
                if cells is not None:
                    self._edges_polydata.SetLines(cells)
                    self._edge_cells_shape = shape
        self._edges_polydata.Modified()

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
                self._edges_actor.GetProperty().SetLineWidth(float(edge_width()))
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

        render_key = (
            _safe_get_state(self._data_node),
            _control_points_digest(self._data_node),
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

# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Slice-view control polygon: fading projection + slice-side editing.

The markups-style slice half of the control polygon (ADR-0033): the
``Rows x Cols`` handles and their connecting edges are projected into the
slice view's XY space (``inverse(XYToRAS)``, the SliceContourPipeline
convention) with DISTANCE FADING -- per-point alpha falls off linearly
with the point's distance to the slice plane, the above/below visual cue
markups users expect -- and the Planning per-point drag is available FROM
the slice views: press grabs the nearest projected handle, the drag moves
it in-plane at the cursor while PRESERVING its out-of-plane offset (no
snap-to-plane), release ends the gesture.

Keyed on ``vtkMRMLControlPolygonDisplayNode`` for ``vtkMRMLSliceNode``
views only (creators dispatch per view type; the 3D control-polygon
creator accepts only ``vtkMRMLViewNode``) -- ADR-0013 §1 keying stays
disjoint per (view-type, display-type) pair.
"""

from __future__ import annotations

from typing import Any

import vtk

from LayerDMLib import vtkMRMLLayerDMScriptedPipeline as _PipelineBase

try:  # pragma: no cover - exercised once per import path
    from .LiverBezierSurfacePipeline import (
        STATE_PLANNING,
        _safe_get_state,
    )
    from .ControlPolygonPipeline import (
        CONTROL_POINT_PICK_RADIUS_PX,
        HALO_GRAB_COLOR,
        HALO_HOVER_COLOR,
        _control_points_digest,
        _event_type,
    )
except ImportError:  # top-level import path (the unit layer's sys.path setup)
    from LiverBezierSurfacePipeline import (  # type: ignore[no-redef]
        STATE_PLANNING,
        _safe_get_state,
    )
    from ControlPolygonPipeline import (  # type: ignore[no-redef]
        CONTROL_POINT_PICK_RADIUS_PX,
        HALO_GRAB_COLOR,
        HALO_HOVER_COLOR,
        _control_points_digest,
        _event_type,
    )

_REGISTERED = False

#: Distance (mm) over which the projection fades to fully transparent --
#: the above/below-the-plane cue.  On-plane points render fully opaque.
FADE_DISTANCE_MM = 30.0

#: Only control points within this plane distance are MANIPULABLE from a
#: slice view (the markups short-range convention); visibility fades to
#: zero at FADE_DISTANCE_MM regardless.
PICK_RANGE_MM = 15.0


def _creator_accepts_view(viewNode: Any) -> bool:  # noqa: N803 - VTK arg name
    """True iff ``viewNode`` is a slice view (this pipeline's home)."""
    if viewNode is None:
        return False
    is_a = getattr(viewNode, "IsA", None)
    if is_a is None:
        return False
    try:
        return bool(is_a("vtkMRMLSliceNode"))
    except Exception:  # pragma: no cover - defensive
        return False


class SliceControlPolygonPipeline(_PipelineBase):
    """Projected, fading, slice-editable control polygon."""

    def __init__(self) -> None:
        super().__init__()
        self.SetPythonObject(self)

        self._display_node: Any | None = None
        self._data_node: Any | None = None
        self._slice_node: Any | None = None
        self._renderer: Any | None = None
        self._observer_tags: dict = {}
        self._observed_node_refs: list = []
        self._last_update_key: tuple | None = None
        self._last_render_key: tuple | None = None
        #: Flat row-major index of the grabbed handle (slice-side gesture).
        self._drag_index: int | None = None
        #: XY-space positions of the projected handles (pick arbitration).
        self._projected_xy: list = []
        #: Per-point |distance| to the slice plane (the pick-range gate).
        self._plane_distances: list = []

        # Handles: projected points as 2D cross glyphs with RGBA fading.
        self._handles_polydata = vtk.vtkPolyData()
        self._handles_polydata.SetPoints(vtk.vtkPoints())
        self._handle_glyph_source = vtk.vtkGlyphSource2D()
        self._handle_glyph_source.SetGlyphTypeToCircle()
        self._handle_glyph_source.FilledOff()
        self._handle_glyph_source.SetScale(8.0)
        self._handles_glyph = vtk.vtkGlyph2D()
        self._handles_glyph.SetInputData(self._handles_polydata)
        self._handles_glyph.SetSourceConnection(
            self._handle_glyph_source.GetOutputPort()
        )
        self._handles_glyph.SetColorModeToColorByScalar()
        self._handles_glyph.ScalingOff()
        self._handles_mapper = vtk.vtkPolyDataMapper2D()
        self._handles_mapper.SetInputConnection(self._handles_glyph.GetOutputPort())
        self._handles_actor = vtk.vtkActor2D()
        self._handles_actor.SetMapper(self._handles_mapper)
        self._handles_actor.SetVisibility(False)

        # Edges: projected polygon lines with per-vertex RGBA fading.
        self._edges_polydata = vtk.vtkPolyData()
        self._edges_polydata.SetPoints(vtk.vtkPoints())
        self._edges_mapper = vtk.vtkPolyDataMapper2D()
        self._edges_mapper.SetInputData(self._edges_polydata)
        self._edges_actor = vtk.vtkActor2D()
        self._edges_actor.SetMapper(self._edges_mapper)
        self._edges_actor.GetProperty().SetLineWidth(2.0)
        self._edges_actor.SetVisibility(False)

    # ------------------------------------------------------------------ #
    # LayerDM lifecycle
    # ------------------------------------------------------------------ #

    def SetViewNode(self, viewNode: Any) -> None:  # noqa: N802 - VTK verb
        super().SetViewNode(viewNode)
        # Observe the slice node OURSELVES (the stale-trace lesson from the
        # contour sibling): reslicing must re-project + re-fade.
        if self._slice_node is not None:
            self._detach_observer(self._slice_node)
        self._slice_node = viewNode
        if viewNode is not None:
            self._attach_observer(viewNode)
        self._last_update_key = None

    def SetDisplayNode(self, displayNode: Any) -> None:  # noqa: N802 - VTK verb
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

    def OnReferenceToDisplayNodeAdded(self, fromNode: Any, role: Any = None) -> None:  # noqa: N802
        if self._data_node is None and fromNode is not None and fromNode is not self._display_node:
            self._data_node = fromNode
            self._attach_observer(fromNode)
            self._last_update_key = None
        self.UpdatePipeline()

    def OnRendererAdded(self, renderer: Any) -> None:  # noqa: N802 - VTK verb
        self._renderer = renderer
        if renderer is not None:
            renderer.AddActor2D(self._edges_actor)
            renderer.AddActor2D(self._handles_actor)
        if self._display_node is None:
            base_getter = getattr(self, "GetDisplayNode", None)
            display = base_getter() if base_getter is not None else None
            if display is not None:
                self.SetDisplayNode(display)
        self._last_update_key = None
        self.UpdatePipeline()

    def OnRendererRemoved(self, renderer: Any) -> None:  # noqa: N802 - VTK verb
        if renderer is not None:
            try:
                renderer.RemoveActor2D(self._handles_actor)
                renderer.RemoveActor2D(self._edges_actor)
            except Exception:  # pragma: no cover - defensive
                pass
        self._renderer = None
        self.cleanup()

    def cleanup(self) -> None:
        for node in list(self._observed_node_refs):
            self._detach_observer(node)
        self._display_node = None
        self._data_node = None
        self._drag_index = None
        self._handles_actor.SetVisibility(False)
        self._edges_actor.SetVisibility(False)

    # ------------------------------------------------------------------ #
    # Reconciliation
    # ------------------------------------------------------------------ #

    def UpdatePipeline(self) -> None:  # noqa: N802 - VTK verb
        state = _safe_get_state(self._data_node)
        key = (
            state,
            _control_points_digest(self._data_node),
            self._slice_matrix_digest(self._slice_node),
            _safe_get_mtime(self._display_node),
        )
        if key == self._last_update_key:
            return
        self._last_update_key = key

        visible = state == STATE_PLANNING and self._reproject()
        self._handles_actor.SetVisibility(bool(visible))
        self._edges_actor.SetVisibility(bool(visible))

    def _reproject(self) -> bool:
        """Project handles + edges into XY with distance fading."""
        carrier = self._data_node
        slice_node = self._slice_node
        if carrier is None or slice_node is None:
            return False
        grid_getter = getattr(carrier, "GetControlGridVector", None)
        rows_getter = getattr(carrier, "GetRows", None)
        cols_getter = getattr(carrier, "GetCols", None)
        if None in (grid_getter, rows_getter, cols_getter):
            return False
        try:
            grid = grid_getter()
            rows, cols = int(rows_getter()), int(cols_getter())
            if len(grid) < rows * cols * 3:
                return False

            to_ras = slice_node.GetSliceToRAS()
            origin = [to_ras.GetElement(r, 3) for r in range(3)]
            normal = [to_ras.GetElement(r, 2) for r in range(3)]
            norm = sum(n * n for n in normal) ** 0.5 or 1.0
            normal = [n / norm for n in normal]

            ras_to_xy = vtk.vtkMatrix4x4()
            ras_to_xy.DeepCopy(slice_node.GetXYToRAS())
            ras_to_xy.Invert()

            display = self._display_node
            handle_rgb = [255, 255, 255]
            edge_rgb = [255, 0, 0]
            if display is not None:
                try:
                    handle_rgb = [int(c * 255) for c in display.GetHandleColor()]
                    edge_rgb = [int(c * 255) for c in display.GetEdgeColor()]
                except Exception:  # pragma: no cover - defensive
                    pass

            points = vtk.vtkPoints()
            handle_rgba = vtk.vtkUnsignedCharArray()
            handle_rgba.SetNumberOfComponents(4)
            edge_rgba = vtk.vtkUnsignedCharArray()
            edge_rgba.SetNumberOfComponents(4)
            hovered, grabbed = self._interaction_state()
            hover_rgb = [int(c * 255) for c in HALO_HOVER_COLOR]
            grab_rgb = [int(c * 255) for c in HALO_GRAB_COLOR]
            self._projected_xy = []
            self._plane_distances = []
            for i in range(rows * cols):
                x, y, z = grid[i * 3], grid[i * 3 + 1], grid[i * 3 + 2]
                xy = ras_to_xy.MultiplyPoint((x, y, z, 1.0))
                w = xy[3] or 1.0
                px, py = xy[0] / w, xy[1] / w
                points.InsertNextPoint(px, py, 0.0)
                self._projected_xy.append((px, py))
                distance = abs(
                    sum(n * (p - o) for n, p, o in zip(normal, (x, y, z), origin))
                )
                self._plane_distances.append(distance)
                alpha = max(0.0, 1.0 - distance / FADE_DISTANCE_MM)
                if i == grabbed:
                    # Cross-view highlight: full alpha, grab colour.
                    handle_rgba.InsertNextTuple4(*grab_rgb, 255)
                elif i == hovered:
                    handle_rgba.InsertNextTuple4(*hover_rgb, 255)
                else:
                    handle_rgba.InsertNextTuple4(*handle_rgb, int(alpha * 255))
                edge_rgba.InsertNextTuple4(*edge_rgb, int(alpha * 255))

            self._handles_polydata.SetPoints(points)
            self._handles_polydata.GetPointData().SetScalars(handle_rgba)
            self._handles_polydata.Modified()

            edge_points = vtk.vtkPoints()
            edge_points.DeepCopy(points)
            lines = vtk.vtkCellArray()
            for r in range(rows):
                line = vtk.vtkPolyLine()
                line.GetPointIds().SetNumberOfIds(cols)
                for c in range(cols):
                    line.GetPointIds().SetId(c, r * cols + c)
                lines.InsertNextCell(line)
            for c in range(cols):
                line = vtk.vtkPolyLine()
                line.GetPointIds().SetNumberOfIds(rows)
                for r in range(rows):
                    line.GetPointIds().SetId(r, r * cols + c)
                lines.InsertNextCell(line)
            self._edges_polydata.SetPoints(edge_points)
            self._edges_polydata.SetLines(lines)
            self._edges_polydata.GetPointData().SetScalars(edge_rgba)
            self._edges_polydata.Modified()
            return True
        except Exception:  # pragma: no cover - defensive
            return False

    @staticmethod
    def _slice_matrix_digest(slice_node: Any) -> tuple:
        if slice_node is None:
            return ()
        try:
            m = slice_node.GetXYToRAS()
            s = slice_node.GetSliceToRAS()
            return tuple(
                round(mat.GetElement(r, c), 6)
                for mat in (m, s)
                for r in range(4)
                for c in range(4)
            )
        except Exception:  # pragma: no cover - defensive
            return ()

    # ------------------------------------------------------------------ #
    # Interaction -- the slice-side per-point drag (ADR-0033)
    # ------------------------------------------------------------------ #

    def CanProcessInteractionEvent(self, eventData: Any):  # noqa: N802 - VTK verb
        import sys

        if _safe_get_state(self._data_node) != STATE_PLANNING:
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
            # Bare hover: publish the cross-view highlight and decline.
            idx, distance2 = self._nearest_handle_in_display(eventData)
            within = (
                idx is not None
                and distance2 <= CONTROL_POINT_PICK_RADIUS_PX * CONTROL_POINT_PICK_RADIUS_PX
            )
            self._publish_interaction_state(hovered=(idx if within else -1))
            return False, sys.float_info.max
        if etype != vtk.vtkCommand.LeftButtonPressEvent:
            return False, sys.float_info.max
        _, distance2 = self._nearest_handle_in_display(eventData)
        if distance2 <= CONTROL_POINT_PICK_RADIUS_PX * CONTROL_POINT_PICK_RADIUS_PX:
            return True, distance2
        return False, sys.float_info.max

    def ProcessInteractionEvent(self, eventData: Any) -> bool:  # noqa: N802 - VTK verb
        if _safe_get_state(self._data_node) != STATE_PLANNING:
            self._drag_index = None
            return False
        etype = _event_type(eventData)

        if self._drag_index is None:
            if etype != vtk.vtkCommand.LeftButtonPressEvent:
                return False
            idx, distance2 = self._nearest_handle_in_display(eventData)
            if (
                idx is None
                or distance2 > CONTROL_POINT_PICK_RADIUS_PX * CONTROL_POINT_PICK_RADIUS_PX
            ):
                return False
            self._drag_index = idx
            self._publish_interaction_state(grabbed=idx)
            return True

        if etype == vtk.vtkCommand.LeftButtonReleaseEvent:
            self._drag_index = None
            self._publish_interaction_state(grabbed=-1)
            return False

        if etype == vtk.vtkCommand.MouseMoveEvent:
            self._move_grabbed_to(eventData)
            return True
        return False

    def _nearest_handle_in_display(self, eventData: Any):
        """``(flat_index, distance2)`` of the projected handle nearest the pixel.

        Slice-view display coordinates coincide with the XY space the
        projection lives in (the slice renderer's convention), so the
        arbitration compares the event pixel against ``_projected_xy``.
        """
        import sys

        try:
            ex, ey = eventData.GetDisplayPosition()
        except Exception:  # pragma: no cover - defensive
            return None, sys.float_info.max
        best_idx, best_d2 = None, sys.float_info.max
        for i, (px, py) in enumerate(self._projected_xy):
            # Markups short-range convention: points beyond PICK_RANGE_MM
            # from the plane are not manipulable from this slice.
            if i < len(self._plane_distances) and self._plane_distances[i] > PICK_RANGE_MM:
                continue
            d2 = (px - ex) ** 2 + (py - ey) ** 2
            if d2 < best_d2:
                best_idx, best_d2 = i, d2
        return best_idx, best_d2

    def _move_grabbed_to(self, eventData: Any) -> None:
        """Move the grabbed point to the cursor IN-PLANE, offset preserved."""
        carrier = self._data_node
        slice_node = self._slice_node
        idx = self._drag_index
        if carrier is None or slice_node is None or idx is None:
            return
        try:
            ex, ey = eventData.GetDisplayPosition()
            xy_to_ras = slice_node.GetXYToRAS()
            ras = xy_to_ras.MultiplyPoint((float(ex), float(ey), 0.0, 1.0))
            w = ras[3] or 1.0
            in_plane = [ras[0] / w, ras[1] / w, ras[2] / w]

            to_ras = slice_node.GetSliceToRAS()
            origin = [to_ras.GetElement(r, 3) for r in range(3)]
            normal = [to_ras.GetElement(r, 2) for r in range(3)]
            norm = sum(n * n for n in normal) ** 0.5 or 1.0
            normal = [n / norm for n in normal]

            grid = carrier.GetControlGridVector()
            current = (grid[idx * 3], grid[idx * 3 + 1], grid[idx * 3 + 2])
            # Signed out-of-plane offset of the point BEFORE the move.
            offset = sum(n * (p - o) for n, p, o in zip(normal, current, origin))
            target = [ip + n * offset for ip, n in zip(in_plane, normal)]

            cols = int(carrier.GetCols())
            carrier.SetControlPoint(
                idx // cols, idx % cols, target[0], target[1], target[2]
            )
        except Exception:  # pragma: no cover - defensive
            return

    # ------------------------------------------------------------------ #
    # Introspection
    # ------------------------------------------------------------------ #

    def GetDataNode(self) -> Any | None:  # noqa: N802 - VTK verb
        return self._data_node

    def GetHandlesPolyData(self) -> Any:  # noqa: N802 - VTK verb
        return self._handles_polydata

    def GetHandlesActor(self) -> Any:  # noqa: N802 - VTK verb
        return self._handles_actor

    def GetEdgesActor(self) -> Any:  # noqa: N802 - VTK verb
        return self._edges_actor

    # ------------------------------------------------------------------ #
    # Observers
    # ------------------------------------------------------------------ #

    def _attach_observer(self, node: Any) -> None:
        if node is None or not hasattr(node, "AddObserver"):
            return
        tag = node.AddObserver("ModifiedEvent", self._on_node_modified)
        self._observer_tags.setdefault(id(node), []).append(tag)
        if node not in self._observed_node_refs:
            self._observed_node_refs.append(node)

    def _detach_observer(self, node: Any) -> None:
        for tag in self._observer_tags.pop(id(node), []):
            try:
                node.RemoveObserver(tag)
            except Exception:  # pragma: no cover - defensive
                pass
        try:
            self._observed_node_refs.remove(node)
        except ValueError:
            pass

    def _interaction_state(self) -> tuple:
        """(hovered, grabbed) read off the display node; (-1, -1) sans it."""
        display = self._display_node
        try:
            return (
                display.GetHoveredControlPoint() if display is not None else -1,
                display.GetGrabbedControlPoint() if display is not None else -1,
            )
        except Exception:  # pragma: no cover - defensive (stub displays)
            return (-1, -1)

    def _publish_interaction_state(self, hovered=None, grabbed=None) -> None:
        """Write hover/grab onto the display node (cross-view channel)."""
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

    def _on_node_modified(self, caller: Any, event: str) -> None:
        del caller, event
        self.UpdatePipeline()

        render_key = (
            _safe_get_state(self._data_node),
            _control_points_digest(self._data_node),
            self._slice_matrix_digest(self._slice_node),
            self._interaction_state(),
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


def _safe_get_mtime(node: Any) -> int:
    if node is None:
        return 0
    getter = getattr(node, "GetMTime", None)
    if getter is None:
        return 0
    try:
        return int(getter())
    except Exception:  # pragma: no cover - defensive
        return 0


# --------------------------------------------------------------------------- #
# Pipeline-creator registration — ADR-0013 §5 call 3 (slice-view half)
# --------------------------------------------------------------------------- #


def registerSliceControlPolygonPipelineCreator() -> None:  # noqa: N802 - project convention
    """Register the slice-view control-polygon creator with LayerDM.

    Accepts ``(vtkMRMLSliceNode, vtkMRMLControlPolygonDisplayNode)`` pairs
    only -- the slice complement of the 3D control-polygon creator.
    Idempotent via the module-level flag.
    """
    global _REGISTERED
    if _REGISTERED:
        return

    from slicer import (  # type: ignore[import-not-found]
        vtkMRMLControlPolygonDisplayNode,
        vtkMRMLLayerDMPipelineFactory,
        vtkMRMLLayerDMPipelineScriptedCreator,
    )

    def tryCreate(viewNode, node):
        if not _creator_accepts_view(viewNode):
            return None
        if not isinstance(node, vtkMRMLControlPolygonDisplayNode):
            return None
        return SliceControlPolygonPipeline()

    creator = vtkMRMLLayerDMPipelineScriptedCreator()
    creator.SetPythonCallback(tryCreate)
    vtkMRMLLayerDMPipelineFactory.GetInstance().AddPipelineCreator(creator)
    _REGISTERED = True

# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Slice-view control polygon: fading projection + slice-side editing.

The markups-style slice half of the control polygon (ADR-0033): the
``Rows x Cols`` handles and their connecting edges are projected into the
slice view's XY space (``inverse(XYToRAS)``) with DISTANCE FADING -- the
above/below visual cue markups users expect -- and the Planning per-point
drag is available FROM the slice views: press grabs the nearest projected
handle, the drag moves it in-plane at the cursor while PRESERVING its
out-of-plane offset (no snap-to-plane), release ends the gesture.

The generic slice affordance -- the projection/fade/side-tint/presence, the
hollow-circle handles + hover ring, and the grab-seam arbitration -- is the
shared ``SurfacePointPlacementPipelineSlice`` base's (ADR-0038 §Decision):
resection is the extraction-source client over the ``PointProvider`` seam.
This pipeline keeps the RESECTION-specific parts as narrow overrides
(ADR-0038 §"What is not shared"): the dashed edge scaffold, the Init/Planning
state gate, the control-point-depth-offset-preserving drag, and the
cross-view highlight channel on the display node.

Keyed on ``vtkMRMLControlPolygonDisplayNode`` for ``vtkMRMLSliceNode``
views only (creators dispatch per view type; the 3D control-polygon
creator accepts only ``vtkMRMLViewNode``) -- ADR-0013 §1 keying stays
disjoint per (view-type, display-type) pair.
"""

from __future__ import annotations

from typing import Any

import vtk

# The shared slice-view placement/edit base (ADR-0038 §Decision): resection
# is the extraction-source client of ``SurfacePointPlacementPipelineSlice``
# over the PointProvider seam.  The base drives the generic grab/drag/release
# arbitration + the projection/fade/side/presence + the handles/ring; this
# pipeline keeps the resection data model (the control grid + dashed edges),
# the Init/Planning gate, and the offset-preserving drag as overrides.
try:  # pragma: no cover - exercised once per import path
    from SlicerLiverInteractionLib.SurfacePointPlacementPipelineSlice import (
        SurfacePointPlacementPipelineSlice as _PipelineBase,
        HALO_HOVER_COLOR,  # noqa: F401 - the projection hover-colour the char suite reads off this module
        POINT_PICK_RADIUS_PX as CONTROL_POINT_PICK_RADIUS_PX,
        _event_type,  # noqa: F401 - the slice event-type helper (imported from the base, ADR-0038)
    )
    from SlicerLiverInteractionLib import SlicePointProjection as _proj
except ImportError:  # bare / top-level path: add the sibling Lib dir to sys.path
    import pathlib
    import sys as _sys

    _shared_lib = pathlib.Path(__file__).resolve().parents[2] / "SlicerLiverInteractionLib"
    if str(_shared_lib) not in _sys.path:
        _sys.path.insert(0, str(_shared_lib))
    from SurfacePointPlacementPipelineSlice import (  # type: ignore[no-redef]
        SurfacePointPlacementPipelineSlice as _PipelineBase,
        HALO_HOVER_COLOR,  # noqa: F401 - the projection hover-colour the char suite reads off this module
        POINT_PICK_RADIUS_PX as CONTROL_POINT_PICK_RADIUS_PX,
        _event_type,  # noqa: F401 - the slice event-type helper (imported from the base, ADR-0038)
    )
    import SlicePointProjection as _proj  # type: ignore[no-redef]

try:  # pragma: no cover - exercised once per import path
    from .LiverBezierSurfacePipeline import (
        STATE_PLANNING,
        _safe_get_state,
    )
    from .ControlPolygonPipeline import (
        _control_points_digest,
    )
    from .ResectionControlPolygonProvider import ResectionControlPolygonProvider
except ImportError:  # top-level import path (the unit layer's sys.path setup)
    from LiverBezierSurfacePipeline import (  # type: ignore[no-redef]
        STATE_PLANNING,
        _safe_get_state,
    )
    from ControlPolygonPipeline import (  # type: ignore[no-redef]
        _control_points_digest,
    )
    from ResectionControlPolygonProvider import (  # type: ignore[no-redef]
        ResectionControlPolygonProvider,
    )

_REGISTERED = False

#: Dash pattern for the polygon edges (XY pixels): the SCAFFOLD reads
#: dashed, the solid slice contour is the RESULT -- a structural
#: differentiation, not colour-only.
DASH_LENGTH_PX = 8.0
GAP_LENGTH_PX = 5.0

#: The default edge colour when the display node offers none.
DEFAULT_EDGE_RGB = (255, 0, 0)


def _creator_accepts_view(viewNode: Any) -> bool:  # noqa: N803 - VTK arg name
    """True iff ``viewNode`` is a slice view (this pipeline's home).

    Part of the creator callback: LayerDM invokes it for every
    ``(view, node)`` pair, so it must never raise.
    """
    try:
        return viewNode is not None and bool(viewNode.IsA("vtkMRMLSliceNode"))
    except Exception:  # pragma: no cover - C++ boundary must never raise
        return False


class SliceControlPolygonPipeline(_PipelineBase):
    """Projected, fading, slice-editable control polygon.

    A thin client of ``SurfacePointPlacementPipelineSlice``: the base owns the
    handle projection/fade/side/presence + the grab-seam arbitration + the
    hover ring, this pipeline supplies the resection ``PointProvider`` and the
    resection-specific edges / state gate / offset-preserving drag.
    """

    def __init__(self) -> None:
        # The base seeds the handle + ring actors, the projection bookkeeping
        # (``_projected_keys`` / ``_projected_xy`` / ``_plane_distances``), the
        # grab key (``_drag_key``), and calls ``SetPythonObject``.
        super().__init__()

        self._data_node: Any | None = None
        self._last_update_key: tuple | None = None
        self._last_render_key: tuple | None = None

        # Wire the ADR-0038 seam: the base reads the control grid via this
        # provider (grid IS a connected polygon -> has_edges True).  The
        # provider reads the carrier live through a getter so it always sees
        # the current LayerDM back-reference; the handle colour is the display
        # node's HandleColor when it offers one.
        self.SetProvider(
            ResectionControlPolygonProvider(
                carrier_getter=lambda: self._data_node,
                color_getter=self._current_handle_rgb,
            )
        )

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
    # LayerDM lifecycle -- resection data-node observation (base hooks)
    # ------------------------------------------------------------------ #

    def _before_display_node_change(self) -> None:
        if self._data_node is not None:
            self._detach_observer(self._data_node)

    def _after_display_node_set(self) -> None:
        display = self._display_node
        self._data_node = None
        if display is not None:
            self._data_node = display.GetDisplayableNode()
            if self._data_node is not None:
                self._attach_observer(self._data_node)
        self._last_update_key = None

    def OnReferenceToDisplayNodeAdded(self, fromNode: Any, role: Any = None) -> None:  # noqa: N802
        try:
            if self._data_node is None and fromNode is not None and fromNode is not self._display_node:
                self._data_node = fromNode
                self._attach_observer(fromNode)
                self._last_update_key = None
            self.UpdatePipeline()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    def _add_actors(self, renderer: Any) -> None:
        renderer.AddActor2D(self._edges_actor)
        super()._add_actors(renderer)

    def _remove_actors(self, renderer: Any) -> None:
        renderer.RemoveActor2D(self._edges_actor)
        super()._remove_actors(renderer)

    def OnRendererAdded(self, renderer: Any) -> None:  # noqa: N802 - VTK verb
        super().OnRendererAdded(renderer)
        self._last_update_key = None

    def cleanup(self) -> None:
        super().cleanup()
        self._data_node = None
        self._edges_actor.SetVisibility(False)

    # ------------------------------------------------------------------ #
    # Reconciliation -- resection state gate + change-key memo
    # ------------------------------------------------------------------ #

    def _reconcile(self) -> None:
        """Gate the base reproject on the Planning state + the change memo."""
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
        if not visible:
            # The ring is driven by the hover channel inside _reproject; a
            # hover live at the moment the carrier leaves Planning would
            # otherwise strand the ring over no handles.
            self._ring_actor.SetVisibility(False)

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
    # Base extension hooks -- the resection specifics (ADR-0038)
    # ------------------------------------------------------------------ #

    def _slice_admissible(self) -> bool:
        """Gate the base's arbitration on the Planning state (ADR-0019)."""
        return _safe_get_state(self._data_node) == STATE_PLANNING

    def _interaction_state(self) -> tuple:
        """(hovered, grabbed) read off the display node; (-1, -1) sans it."""
        display = self._display_node
        return (
            display.GetHoveredControlPoint() if display is not None else -1,
            display.GetGrabbedControlPoint() if display is not None else -1,
        )

    def _edge_base_rgb(self):
        """The display node's EdgeColor (0..255) -- the dashed scaffold's hue."""
        display = self._display_node
        if display is not None:
            try:
                return [int(c * 255) for c in display.GetEdgeColor()]
            except Exception:  # pragma: no cover - defensive
                pass
        return list(DEFAULT_EDGE_RGB)

    def _reproject_edges(self, all_xy: list, all_present: list, edge_rgba: Any) -> None:
        """Emit the grid edges as DASHED XY segments (structural scaffold).

        Manual dash segmentation (GL line stipple is not portable): each grid
        edge is emitted as alternating dash segments, so the scaffold reads
        structurally distinct from the solid resection contour.  Runs are
        gated on EITHER endpoint being present so a visible point never floats
        without its scaffold (the tint/fade along the run shows the far end
        receding).
        """
        carrier = self._data_node
        if carrier is None:
            return
        try:
            rows, cols = int(carrier.GetRows()), int(carrier.GetCols())
        except Exception:  # pragma: no cover - defensive
            return
        if len(all_xy) < rows * cols:
            return

        dash_points = vtk.vtkPoints()
        dash_rgba = vtk.vtkUnsignedCharArray()
        dash_rgba.SetNumberOfComponents(4)
        dash_lines = vtk.vtkCellArray()

        def _edge_pairs():
            for r in range(rows):
                for c in range(cols - 1):
                    yield r * cols + c, r * cols + c + 1
            for c in range(cols):
                for r in range(rows - 1):
                    yield r * cols + c, (r + 1) * cols + c

        for a, b in _edge_pairs():
            if not (all_present[a] or all_present[b]):
                continue  # both endpoints absent: no scaffold here
            ax, ay = all_xy[a]
            bx, by = all_xy[b]
            ca = edge_rgba.GetTuple4(a)
            cb = edge_rgba.GetTuple4(b)
            length = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
            if length <= 0.0:
                continue
            period = DASH_LENGTH_PX + GAP_LENGTH_PX
            t = 0.0
            while t < length:
                t_end = min(t + DASH_LENGTH_PX, length)
                f0, f1 = t / length, t_end / length
                i0 = dash_points.InsertNextPoint(
                    ax + (bx - ax) * f0, ay + (by - ay) * f0, 0.0
                )
                i1 = dash_points.InsertNextPoint(
                    ax + (bx - ax) * f1, ay + (by - ay) * f1, 0.0
                )
                for f, _i in ((f0, i0), (f1, i1)):
                    dash_rgba.InsertNextTuple4(*[
                        int(ca[k] + (cb[k] - ca[k]) * f) for k in range(4)
                    ])
                seg = vtk.vtkLine()
                seg.GetPointIds().SetId(0, i0)
                seg.GetPointIds().SetId(1, i1)
                dash_lines.InsertNextCell(seg)
                t += period
        self._edges_polydata.SetPoints(dash_points)
        self._edges_polydata.SetLines(dash_lines)
        self._edges_polydata.GetPointData().SetScalars(dash_rgba)
        self._edges_polydata.Modified()

    def _on_grab(self, key: Any) -> None:
        """Publish the grab onto the cross-view highlight channel."""
        self._publish_interaction_state(grabbed=key)

    def _on_release(self) -> None:
        """Drop the grab from the cross-view highlight channel."""
        self._publish_interaction_state(grabbed=-1)

    def _on_bare_move_decline(self, eventData: Any) -> None:
        """Publish the cross-view hover highlight on a declined bare move."""
        idx, distance2 = self._nearest_handle_in_display(eventData)
        within = (
            idx is not None
            and distance2 <= CONTROL_POINT_PICK_RADIUS_PX * CONTROL_POINT_PICK_RADIUS_PX
        )
        self._publish_interaction_state(hovered=(idx if within else -1))

    def _move_grabbed_to(self, eventData: Any) -> None:
        """Move the grabbed point to the cursor IN-PLANE, offset preserved."""
        carrier = self._data_node
        slice_node = self._slice_node
        idx = self._drag_key
        if carrier is None or slice_node is None or idx is None:
            return
        try:
            ex, ey = eventData.GetDisplayPosition()
            in_plane = _proj.xy_to_ras_on_plane(slice_node, ex, ey)
            frame = _proj.slice_frame(slice_node)
            if in_plane is None or frame is None:
                return
            origin, normal = frame

            grid = carrier.GetControlGridVector()
            current = (grid[idx * 3], grid[idx * 3 + 1], grid[idx * 3 + 2])
            # Signed out-of-plane offset of the point BEFORE the move.
            offset = _proj.signed_distance(origin, normal, current)
            target = [ip + n * offset for ip, n in zip(in_plane, normal)]

            cols = int(carrier.GetCols())
            carrier.SetControlPoint(
                idx // cols, idx % cols, target[0], target[1], target[2]
            )
        except Exception:  # pragma: no cover - defensive
            return

    def _publish_interaction_state(self, hovered=None, grabbed=None) -> None:
        """Write hover/grab onto the display node (cross-view channel)."""
        display = self._display_node
        if display is None:
            return
        if hovered is not None:
            value = -1 if hovered == -1 else int(hovered)
            if display.GetHoveredControlPoint() != value:
                display.SetHoveredControlPoint(value)
        if grabbed is not None:
            value = -1 if grabbed == -1 else int(grabbed)
            if display.GetGrabbedControlPoint() != value:
                display.SetGrabbedControlPoint(value)

    def _current_handle_rgb(self):
        """The display node's HandleColor (the provider's per-point base rgb).

        ``None`` -> the provider falls back to its neutral white; a fake
        display node without ``GetHandleColor`` degrades the same way.
        """
        display = self._display_node
        getter = getattr(display, "GetHandleColor", None) if display else None
        if getter is None:
            return None
        try:
            c = getter()
            return (float(c[0]), float(c[1]), float(c[2]))
        except Exception:  # pragma: no cover - defensive (fake display nodes)
            return None

    # ------------------------------------------------------------------ #
    # Introspection
    # ------------------------------------------------------------------ #

    def GetDataNode(self) -> Any | None:  # noqa: N802 - VTK verb
        return self._data_node

    def GetEdgesActor(self) -> Any:  # noqa: N802 - VTK verb
        return self._edges_actor

    # ------------------------------------------------------------------ #
    # Observer render-loop guard (resection change memo)
    # ------------------------------------------------------------------ #

    def _on_node_modified(self, caller: Any, event: str) -> None:
        del caller, event
        try:
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
            self.RequestRender()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass


def _safe_get_mtime(node: Any) -> int:
    """``GetMTime()`` as an int; 0 when no node is attached."""
    if node is None:
        return 0
    return int(node.GetMTime())


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

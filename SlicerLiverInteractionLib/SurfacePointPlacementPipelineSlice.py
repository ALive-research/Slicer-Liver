# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""The shared slice-view control-point placement/edit base (ADR-0038).

ADR-0038 §Decision extracts a shared slice-view interaction/visualization
base (the slice complement of ``SurfacePointPlacementPipeline3D``) from the
mature resection slice pipeline; resection, VascularTerritories and
LiverVolumetry become clients over the ``PointProvider`` seam.  The base
owns the GENERIC slice affordance and NOTHING data-model specific
(ADR-0038 §"What is not shared"):

* the projection of the provider's points into the slice view's XY space,
  the distance-graded alpha fade, the signed above/below side tint, and the
  HARD presence cutoff (2D alpha is unreliable) -- all via the pure-math
  ``SlicePointProjection`` helper (ADR-0038 §Context);
* hollow-circle HANDLE glyphs (grab targets) + a larger hover/grab RING
  glyph (the 2D analogue of the 3D glow halo);
* the grab seam + ``Can/ProcessInteractionEvent`` arbitration: a press near
  a projected handle grabs it for a drag, a bare move is DECLINED
  (``(False, +inf)``) so the camera is untouched (ADR-0033 hover
  discipline), a grabbed move/release is claimed unconditionally;
* the slice-node observation so reslicing re-projects, and the four LayerDM
  integration invariants (renderer churn re-attach etc.).

The concrete clients subclass this base, keep their pinned interaction
seams, and re-inject their data-model + gating through narrow overrides --
resection's edges/dashed scaffold, its Init/Planning gate, and its
control-point-depth-offset-preserving drag -- none of which bleed into the
base (ADR-0038 §"What is not shared").

This is a LayerDM scripted Pipeline (imports LayerDMLib, reachable only
inside a launched Slicer with the module loaded); ADR-0004 keeps the
interaction math in Python; ADR-0013 §5 keeps it a Pipeline base, NOT a
displayable manager.
"""

from __future__ import annotations

import sys
from typing import Any

import vtk

from LayerDMLib import vtkMRMLLayerDMScriptedPipeline as _PipelineBase

try:  # pragma: no cover - exercised once per import path
    from . import SlicePointProjection as _proj
except ImportError:  # top-level import path (the unit layer's sys.path setup)
    import SlicePointProjection as _proj  # type: ignore[no-redef]

#: Display-space pick radius (XY pixels) for grabbing an existing projected
#: handle -- the shared value the resection + territory slice clients carried.
POINT_PICK_RADIUS_PX = 20.0

#: Hover / grab cue colours shared across every slice-projected control
#: surface (ADR-0038 §Context): hover = yellow, grab = green.
HALO_HOVER_COLOR = (1.0, 0.9, 0.2)
HALO_GRAB_COLOR = (0.3, 1.0, 0.4)

#: Slice handle / hover-ring glyph diameters (XY pixels).  Larger than the
#: default markups glyphs: the handles are grab targets, and the ring must
#: read as a halo AROUND one.
HANDLE_GLYPH_SCALE_PX = 13.0
RING_GLYPH_SCALE_PX = 20.0

#: Mid-tone factor applied to a base handle colour before tinting: a pure
#: white base leaves no headroom for the lighter-above tint -- pulling the
#: base toward mid-tone makes BOTH tint directions visible.
HANDLE_MIDTONE_FACTOR = 0.78


def _event_type(eventData: Any) -> int:  # noqa: N803 - VTK arg name
    """The VTK event-type id off ``eventData`` (never-raise boundaries only)."""
    return int(eventData.GetType())


class SurfacePointPlacementPipelineSlice(_PipelineBase):
    """Generic projected, fading, slice-editable control-point surface.

    Concrete consumers subclass this and supply a ``PointProvider``; the base
    carries no data-model knowledge (ADR-0038).  Edges, a state gate, and a
    depth-preserving drag are client concerns injected through the extension
    hooks below.
    """

    def __init__(self) -> None:
        super().__init__()
        self.SetPythonObject(self)

        self._display_node: Any | None = None
        self._slice_node: Any | None = None
        self._renderer: Any | None = None
        self._observer_tags: dict = {}
        self._observed_node_refs: list = []

        # The consumer's data model (ADR-0038 seam).
        self._provider: Any | None = None

        #: Key of the projected handle currently GRABBED by a press/move/
        #: release drag; None when no drag is in flight.  The key is whatever
        #: the provider's ``iter_points`` enumeration yields (flat index).
        self._drag_key: Any | None = None

        #: XY-space positions of the PRESENT projected handles (pick
        #: arbitration) and their parallel keys + |distance| to the plane.
        self._projected_keys: list = []
        self._projected_xy: list = []
        self._plane_distances: list = []

        # Handles: projected points as hollow-circle 2D glyphs with RGBA fade.
        self._handles_polydata = vtk.vtkPolyData()
        self._handles_polydata.SetPoints(vtk.vtkPoints())
        self._handle_glyph_source = vtk.vtkGlyphSource2D()
        self._handle_glyph_source.SetGlyphTypeToCircle()
        self._handle_glyph_source.FilledOff()
        self._handle_glyph_source.SetScale(HANDLE_GLYPH_SCALE_PX)
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

        # Hover ring: the 2D analogue of the 3D glow halo -- a larger hollow
        # circle on the hovered/grabbed projected handle.
        self._ring_polydata = vtk.vtkPolyData()
        self._ring_polydata.SetPoints(vtk.vtkPoints())
        self._ring_glyph_source = vtk.vtkGlyphSource2D()
        self._ring_glyph_source.SetGlyphTypeToCircle()
        self._ring_glyph_source.FilledOff()
        self._ring_glyph_source.SetScale(RING_GLYPH_SCALE_PX)
        self._ring_glyph = vtk.vtkGlyph2D()
        self._ring_glyph.SetInputData(self._ring_polydata)
        self._ring_glyph.SetSourceConnection(self._ring_glyph_source.GetOutputPort())
        self._ring_glyph.ScalingOff()
        self._ring_mapper = vtk.vtkPolyDataMapper2D()
        self._ring_mapper.SetInputConnection(self._ring_glyph.GetOutputPort())
        self._ring_actor = vtk.vtkActor2D()
        self._ring_actor.SetMapper(self._ring_mapper)
        self._ring_actor.GetProperty().SetLineWidth(2.0)
        self._ring_actor.SetVisibility(False)

    # ------------------------------------------------------------------ #
    # Seam wiring
    # ------------------------------------------------------------------ #

    def SetProvider(self, provider: Any) -> None:  # noqa: N802 - VTK verb
        """Inject the consumer's ``PointProvider`` (data model seam)."""
        self._provider = provider

    def GetProvider(self) -> Any | None:  # noqa: N802 - VTK verb
        return self._provider

    def _safe_get_renderer(self) -> Any | None:
        return self._renderer

    # ------------------------------------------------------------------ #
    # LayerDM lifecycle
    # ------------------------------------------------------------------ #

    def SetViewNode(self, viewNode: Any) -> None:  # noqa: N802 - VTK verb
        super().SetViewNode(viewNode)
        # Observe the slice node OURSELVES (the stale-trace lesson): reslicing
        # must re-project + re-fade.
        if self._slice_node is not None:
            self._detach_observer(self._slice_node)
        self._slice_node = viewNode
        if viewNode is not None:
            self._attach_observer(viewNode)

    def SetDisplayNode(self, displayNode: Any) -> None:  # noqa: N802 - VTK verb
        if self._display_node is not None:
            self._detach_observer(self._display_node)
        self._before_display_node_change()

        super().SetDisplayNode(displayNode)
        self._display_node = displayNode
        if displayNode is not None:
            self._attach_observer(displayNode)
        self._after_display_node_set()

    def OnRendererAdded(self, renderer: Any) -> None:  # noqa: N802 - VTK verb
        try:
            self._renderer = renderer
            if renderer is not None:
                self._add_actors(renderer)
            if self._display_node is None:
                display = self.GetDisplayNode()
                if display is not None:
                    self.SetDisplayNode(display)
            # Re-attach the slice-node observer too: cleanup() detached it
            # with the rest, and the view node is not re-set after churn --
            # without this, reslicing stops reprojecting (the stale-trace bug,
            # round two).
            if self._slice_node is not None:
                self._attach_observer(self._slice_node)
            self.UpdatePipeline()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    def OnRendererRemoved(self, renderer: Any) -> None:  # noqa: N802 - VTK verb
        try:
            if renderer is not None:
                self._remove_actors(renderer)
            self._renderer = None
            self.cleanup()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    def _add_actors(self, renderer: Any) -> None:
        """Add the base + client actors to ``renderer`` (client extends)."""
        renderer.AddActor2D(self._handles_actor)
        renderer.AddActor2D(self._ring_actor)

    def _remove_actors(self, renderer: Any) -> None:
        """Remove the base + client actors from ``renderer`` (client extends)."""
        renderer.RemoveActor2D(self._handles_actor)
        renderer.RemoveActor2D(self._ring_actor)

    def cleanup(self) -> None:
        for node in list(self._observed_node_refs):
            self._detach_observer(node)
        self._display_node = None
        self._drag_key = None
        self._handles_actor.SetVisibility(False)
        self._ring_actor.SetVisibility(False)

    # ------------------------------------------------------------------ #
    # Reconcile
    # ------------------------------------------------------------------ #

    def UpdatePipeline(self) -> None:  # noqa: N802 - VTK verb
        try:
            self._reconcile()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    def _reconcile(self) -> None:
        """``UpdatePipeline``'s body -- plain attribute access throughout.

        The base body is deliberately thin: the client owns the gate + the
        change-key memo (its data model decides what a repaint depends on),
        so it overrides ``_reconcile`` and calls ``_reproject`` when its gate
        admits.  This base default reprojects unconditionally -- the flat
        clients (territories, volumetry) have no state gate.
        """
        visible = self._reproject()
        self._handles_actor.SetVisibility(bool(visible))
        if not visible:
            self._ring_actor.SetVisibility(False)

    def _reproject(self) -> bool:
        """Project the provider's points into XY with distance fading.

        Owns the generic handle projection + fade + side tint + presence
        cutoff + hover/grab highlight + ring (ADR-0038 §Context).  After the
        per-point handle loop it calls the ``_reproject_edges`` hook so a
        client with edges (resection's dashed scaffold) draws them from the
        base's per-point bookkeeping WITHOUT the base knowing the topology.
        """
        self._projected_keys = []
        self._projected_xy = []
        self._plane_distances = []
        provider = self._provider
        slice_node = self._slice_node
        if provider is None or slice_node is None:
            return False

        frame = _proj.slice_frame(slice_node)
        ras_to_xy = _proj.inverse_xy_to_ras(slice_node)
        if frame is None or ras_to_xy is None:
            return False
        origin, normal = frame

        hovered, grabbed = self._interaction_state()
        hover_rgb = [int(c * 255) for c in HALO_HOVER_COLOR]
        grab_rgb = [int(c * 255) for c in HALO_GRAB_COLOR]

        # Full parallel arrays over EVERY provider point (present or not), so
        # the edge hook can gate a run on either endpoint's presence.
        all_xy: list = []
        all_present: list = []
        edge_rgba = vtk.vtkUnsignedCharArray()
        edge_rgba.SetNumberOfComponents(4)

        edge_base = self._edge_base_rgb()

        # Present handles only carry into the rendered polydata (presence IS
        # the cutoff: a point beyond the range is ABSENT, not faded to zero).
        handle_points = vtk.vtkPoints()
        handle_rgba = vtk.vtkUnsignedCharArray()
        handle_rgba.SetNumberOfComponents(4)

        try:
            for key, (world, base_rgb) in enumerate(provider.iter_points()):
                xy = _proj.apply_matrix_xy(ras_to_xy, world)
                signed = _proj.signed_distance(origin, normal, world)
                present = _proj.is_present(signed)
                all_xy.append(xy)
                all_present.append(present)

                alpha = int(_proj.fade_alpha(signed) * 255)
                if key == grabbed:
                    hue4 = (grab_rgb[0], grab_rgb[1], grab_rgb[2], 255)
                elif key == hovered:
                    hue4 = (hover_rgb[0], hover_rgb[1], hover_rgb[2], 255)
                else:
                    handle_mid = [int(c * 255 * HANDLE_MIDTONE_FACTOR) for c in base_rgb]
                    tint = _proj.side_tint(handle_mid, signed)
                    hue4 = (tint[0], tint[1], tint[2], alpha)

                if edge_base is not None:
                    etint = _proj.side_tint(edge_base, signed)
                    edge_rgba.InsertNextTuple4(etint[0], etint[1], etint[2], alpha)

                if present:
                    handle_points.InsertNextPoint(xy[0], xy[1], 0.0)
                    handle_rgba.InsertNextTuple4(*hue4)
                    self._projected_keys.append(key)
                    self._projected_xy.append((xy[0], xy[1]))
                    self._plane_distances.append(abs(signed))
        except Exception:  # pragma: no cover - defensive
            return False

        self._handles_polydata.SetPoints(handle_points)
        self._handles_polydata.GetPointData().SetScalars(handle_rgba)
        self._handles_polydata.Modified()

        self._reproject_edges(all_xy, all_present, edge_rgba)
        self._update_ring(hovered, grabbed)
        return True

    def _update_ring(self, hovered: Any, grabbed: Any) -> None:
        """Show the hover/grab ring on the grabbed (green) or hovered (yellow)
        handle -- only when that point is PRESENT in this slice.

        The highlight must not surface a point the plane cannot reach (a
        grab raised in the 3D view over an out-of-range handle), so the ring
        rides the PRESENT projection, not the raw channel index.
        """
        target = grabbed if _index_ok(grabbed) else hovered
        pts = vtk.vtkPoints()
        show = False
        if _index_ok(target) and target in self._projected_keys:
            idx = self._projected_keys.index(target)
            px, py = self._projected_xy[idx]
            pts.InsertNextPoint(px, py, 0.0)
            colour = HALO_GRAB_COLOR if _index_ok(grabbed) else HALO_HOVER_COLOR
            self._ring_actor.GetProperty().SetColor(*colour)
            show = True
        self._ring_polydata.SetPoints(pts)
        self._ring_polydata.Modified()
        self._ring_actor.SetVisibility(show)

    # ------------------------------------------------------------------ #
    # Interaction -- the slice-side grab / drag (ADR-0033)
    # ------------------------------------------------------------------ #

    def CanProcessInteractionEvent(self, eventData: Any):  # noqa: N802 - VTK verb
        """Return ``(canProcess, distance2)`` for the LayerDM focus logic.

        * a grabbed move/release is claimed unconditionally;
        * a bare move is DECLINED (``(False, +inf)``) so the camera is
          untouched (ADR-0033); the hover cue is published as a SIDE EFFECT
          of the declined bare move via ``_on_bare_move_decline``;
        * a press within ``POINT_PICK_RADIUS_PX`` of a projected handle is
          claimed with the REAL squared display distance (grab for a drag).

        The ``_slice_admissible`` gate hook (default ``True``) lets a client
        veto the whole arbitration on its own data-model state -- resection's
        Planning gate rides here, NOT as a branch in this base.
        """
        try:
            if not self._slice_admissible():
                self._drag_key = None  # a state flip mid-gesture drops the grab
                return False, sys.float_info.max
            etype = _event_type(eventData)

            if self._drag_key is not None:
                if etype in (
                    vtk.vtkCommand.MouseMoveEvent,
                    vtk.vtkCommand.LeftButtonReleaseEvent,
                ):
                    return True, 0.0
                return False, sys.float_info.max

            if etype == vtk.vtkCommand.MouseMoveEvent:
                # Bare hover: publish the cross-view highlight and DECLINE.
                self._on_bare_move_decline(eventData)
                return False, sys.float_info.max

            if etype != vtk.vtkCommand.LeftButtonPressEvent:
                return False, sys.float_info.max

            key, distance2 = self._nearest_handle_in_display(eventData)
            if key is not None and distance2 <= POINT_PICK_RADIUS_PX * POINT_PICK_RADIUS_PX:
                return True, distance2
            return False, sys.float_info.max
        except Exception:  # pragma: no cover - C++ boundary must never raise
            return False, sys.float_info.max

    def ProcessInteractionEvent(self, eventData: Any) -> bool:  # noqa: N802 - VTK verb
        """Drive the slice-side grab-to-edit-nearest (ADR-0038 §Decision).

        The generic press-grab / move / release skeleton is here; each phase
        calls a client hook (``_on_grab`` / ``_move_grabbed_to`` /
        ``_on_release``) so the client contributes its data-model side effects
        -- the offset-preserving in-plane move, the grab colour, the ring --
        WITHOUT re-implementing the arbitration (ADR-0038 §"What is not
        shared").
        """
        try:
            if not self._slice_admissible():
                self._drag_key = None
                return False
            etype = _event_type(eventData)

            if self._drag_key is None:
                if etype != vtk.vtkCommand.LeftButtonPressEvent:
                    return False
                key, distance2 = self._nearest_handle_in_display(eventData)
                if (
                    key is None
                    or distance2 > POINT_PICK_RADIUS_PX * POINT_PICK_RADIUS_PX
                ):
                    return False
                self._drag_key = key  # grab for a drag (edit gesture)
                self._on_grab(key)
                return True

            if etype == vtk.vtkCommand.LeftButtonReleaseEvent:
                self._drag_key = None
                self._on_release()
                return False  # gesture over -- release the focus

            if etype == vtk.vtkCommand.MouseMoveEvent:
                self._move_grabbed_to(eventData)
                return True
            return False
        except Exception:  # pragma: no cover - C++ boundary must never raise
            return False

    def _nearest_handle_in_display(self, eventData: Any):
        """``(key, distance2)`` of the PROJECTED handle nearest the event pixel.

        Slice-view display coordinates coincide with the XY space the
        projection lives in (the slice renderer's convention), so the
        arbitration compares the event pixel against ``_projected_xy``.  A
        handle beyond the presence cutoff is not projected, so it is
        inherently unpickable (markups short-range manipulation).
        """
        try:
            ex, ey = eventData.GetDisplayPosition()
        except Exception:  # pragma: no cover - defensive (fake events)
            return None, sys.float_info.max
        best_key = None
        best_d2 = sys.float_info.max
        for key, (px, py) in zip(self._projected_keys, self._projected_xy):
            d2 = (px - ex) ** 2 + (py - ey) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best_key = key
        return best_key, best_d2

    # ------------------------------------------------------------------ #
    # Client extension hooks (no data-model knowledge in the base;
    # ADR-0038 §"What is not shared").  All no-ops / permissive by default.
    # ------------------------------------------------------------------ #

    def _slice_admissible(self) -> bool:
        """Veto hook for a client's own gate (default: always admit).

        A client whose data model gates interaction (resection's Planning
        gate, ADR-0019) overrides this; the base carries no such gate.
        """
        return True

    def _before_display_node_change(self) -> None:
        """Called before the display node is swapped (default no-op)."""

    def _after_display_node_set(self) -> None:
        """Called after a new display node is attached (default no-op)."""

    def _interaction_state(self) -> tuple:
        """``(hovered, grabbed)`` for the projection highlight (default none).

        A client backing a cross-view highlight channel (the display node's
        Hovered/Grabbed control point) overrides this to feed the projection
        the same highlight every view shows.
        """
        return -1, -1

    def _edge_base_rgb(self):
        """The edge base colour (0..255) for the dashed scaffold, or ``None``.

        ``None`` (the default) means the client draws no edges -- the flat
        territory/volumetry point sets.  A client with a connected polygon
        (resection's control grid) returns the edge colour so the base
        computes the per-point side-tinted edge RGBA it feeds the edge hook.
        """
        return None

    def _reproject_edges(self, all_xy: list, all_present: list, edge_rgba: Any) -> None:
        """Draw the connecting edges from the base's per-point bookkeeping.

        Default no-op (the flat clients have no edges).  ``all_xy`` /
        ``all_present`` are the FULL parallel arrays over every provider
        point (present or not) so a client can gate an edge run on either
        endpoint's presence; ``edge_rgba`` holds the base's per-point
        side-tinted edge colours (empty when ``_edge_base_rgb`` is ``None``).
        """

    def _on_grab(self, key: Any) -> None:
        """Called right after the base grabs ``key`` on a press (default no-op)."""

    def _on_release(self) -> None:
        """Called right after the base clears the grab on release (default no-op)."""

    def _on_bare_move_decline(self, eventData: Any) -> None:
        """Called on a DECLINED bare move (default no-op -- the hover cue seam)."""

    def _move_grabbed_to(self, eventData: Any) -> None:
        """Relocate the grabbed handle to the cursor (default no-op).

        A client overrides this with its data-model write-back: resection
        moves the control point IN-PLANE preserving its out-of-plane offset
        (no snap-to-plane); a surface client snaps along the slice normal.
        """

    # ------------------------------------------------------------------ #
    # Introspection
    # ------------------------------------------------------------------ #

    def GetHandlesPolyData(self) -> Any:  # noqa: N802 - VTK verb
        return self._handles_polydata

    def GetHandlesActor(self) -> Any:  # noqa: N802 - VTK verb
        return self._handles_actor

    def GetRingActor(self) -> Any:  # noqa: N802 - VTK verb
        return self._ring_actor

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
        """Reconcile on a carrier / slice ``Modified`` -- reproject + render.

        The base holds no shadow copy of the point set: the provider IS the
        source of truth, so a reconcile driven by an unrelated ``Modified``
        reprojects without adding / moving / dropping any point.  The client
        overrides this to add its render-request loop guard.
        """
        del caller, event
        try:
            self.UpdatePipeline()
            self.RequestRender()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass


def _index_ok(value: Any) -> bool:
    """True iff ``value`` is a usable (non-negative) highlight index."""
    return isinstance(value, int) and value >= 0

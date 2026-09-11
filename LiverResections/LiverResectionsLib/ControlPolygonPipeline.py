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

# The shared 3D placement/edit base (ADR-0038 §Decision): resection is the
# extraction-source client of ``SurfacePointPlacementPipeline3D`` over the
# PointProvider + swappable-pick seam.  The base drives the generic
# add/grab/drag/release arbitration; this pipeline keeps the resection data
# model (the control grid + edges), the Init/Planning gate, and the
# control-point-depth drag as overrides (ADR-0038 §"What is not shared").
try:  # pragma: no cover - exercised once per import path
    from SlicerLiverInteractionLib.SurfacePointPlacementPipeline3D import (
        SurfacePointPlacementPipeline3D as _PipelineBase,
    )
except ImportError:  # bare / top-level path: add the sibling Lib dir to sys.path
    import pathlib
    import sys as _sys

    _shared_lib = pathlib.Path(__file__).resolve().parents[2] / "SlicerLiverInteractionLib"
    if str(_shared_lib) not in _sys.path:
        _sys.path.insert(0, str(_shared_lib))
    from SurfacePointPlacementPipeline3D import (  # type: ignore[no-redef]
        SurfacePointPlacementPipeline3D as _PipelineBase,
    )

# State constants + safe accessors shared with the sibling Pipeline (single
# source within this package; the integers mirror the C++ enum on
# vtkMRMLBezierSurfaceNode).
try:  # pragma: no cover - exercised once per import path
    from . import ResectionStateMachine as _machine
    from .LiverBezierSurfacePipeline import (
        STATE_INIT,
        STATE_PLANNING,
        _safe_get_mtime,
        _safe_get_state,
    )
    from .ResectionControlPolygonProvider import ResectionControlPolygonProvider
except ImportError:  # top-level import path (the unit layer's sys.path setup)
    import ResectionStateMachine as _machine  # type: ignore[no-redef]
    from LiverBezierSurfacePipeline import (  # type: ignore[no-redef]
        STATE_INIT,
        STATE_PLANNING,
        _safe_get_mtime,
        _safe_get_state,
    )
    from ResectionControlPolygonProvider import (  # type: ignore[no-redef]
        ResectionControlPolygonProvider,
    )

#: The Algorithm-library cells builder (reachable only via the
#: vtkSlicerLiverResectionsModuleAlgorithmPython wrapping inside a launched
#: Slicer -- NOT on the ``slicer``/``vtk`` namespaces).
CONTROL_POLYGON_GEOMETRY_CLASS = "vtkSlicerLiverBezierControlPolygonGeometry"

#: Display-space pick radius for the per-point drag, in pixels (the ADR-0032
#: value, unchanged by the ADR-0033 re-siting).
CONTROL_POINT_PICK_RADIUS_PX = 20.0

#: Halo colours: warm hover cue vs the distinct GRABBED (active-drag) cue.
#: The grab cue is carried by the HANDLE colour (per-point glyph scalars),
#: not by a larger halo -- the glow blur washes a halo hue out.
HALO_HOVER_COLOR = (1.0, 0.9, 0.2)
HALO_GRAB_COLOR = (0.3, 1.0, 0.4)
#: Pick radius (display pixels) within which a press grabs the FRAME.
#: Wider than the handle radius: the frame is a thin tube, and the
#: gesture is coarse (translate everything) so a generous target costs
#: nothing -- the group pick is asked BEFORE the point pick, but only
#: claims when no handle is closer (see _group_pick).
FRAME_PICK_RADIUS_PX = 10.0

#: Border colour while a group gesture is HOVERED (never while grabbed).
#:
#: Cool against the warm resting border: the edge default is pure RED and
#: both point cues are warm, so a warm highlight is invisible against it
#: -- an orange first attempt read as no change at all.
FRAME_HOVER_COLOR = (0.25, 0.9, 1.0)

#: Border colour while a group gesture is HELD.  Distinct from the hover
#: cyan so the border keeps saying which state it is in, and cool like it
#: so neither competes with the warm point cues.
FRAME_GRAB_COLOR = (0.1, 0.45, 1.0)


#: Halo radius scale vs the handle sphere.
HALO_HOVER_SCALE = 1.35

#: World-space dash pattern for the polygon edge tubes -- the same
#: dashed-scaffold language the slice projections use, so the control
#: polygon reads consistently across every view.  The gap is deliberately
#: wide relative to the tube diameter (~3 mm): world-space gaps close up
#: optically at low zoom / glancing angles, which read as a solid line.
DASH_LENGTH_MM = 7.0
GAP_LENGTH_MM = 7.0

_REGISTERED = False


def _ring_groups(rows: int, cols: int):
    """Ring membership for the group gestures, or ``()`` when unavailable.

    Imported lazily and defensively: the Representations stay
    independently importable, and a missing module must degrade to "no
    group affordance" rather than breaking an interaction callback.
    """
    try:
        from ControlPolygonRings import ring_groups
    except Exception:
        try:
            from LiverResectionsLib.ControlPolygonRings import ring_groups
        except Exception:
            return ()
    return ring_groups(int(rows), int(cols))


def _point_segment_distance2(px: float, py: float, start, end) -> float:
    """Squared distance from ``(px, py)`` to the SEGMENT ``start``-``end``.

    Clamped to the segment, so the ends do not attract picks that belong
    to the neighbouring edge.  A degenerate (zero-length) segment reduces
    to the point distance.
    """
    ax, ay = start
    bx, by = end
    vx, vy = bx - ax, by - ay
    length2 = vx * vx + vy * vy
    if length2 <= 0.0:
        return (px - ax) ** 2 + (py - ay) ** 2
    t = ((px - ax) * vx + (py - ay) * vy) / length2
    t = max(0.0, min(1.0, t))
    cx, cy = ax + t * vx, ay + t * vy
    return (px - cx) ** 2 + (py - cy) ** 2


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
        # The base seeds ``_display_node`` / ``_renderer`` / ``_drag_key`` /
        # ``_provider`` / ``_pick_provider`` and calls ``SetPythonObject``.
        super().__init__(namespace="ResectionControlPolygon")

        self._data_node: Any | None = None
        self._observer_tags: dict = {}
        self._observed_node_refs: list = []

        # Wire the ADR-0038 seam: the base reads/writes the control grid via
        # this provider (grid IS a connected polygon -> has_edges True).  The
        # provider reads the carrier live through a getter so it always sees
        # the current LayerDM back-reference; the handle colour is the display
        # node's HandleColor when it offers one.
        self.SetProvider(
            ResectionControlPolygonProvider(
                carrier_getter=lambda: self._data_node,
                color_getter=self._current_handle_rgb,
            )
        )
        # No pick provider: resection has no add-on-click (the grid is fixed,
        # so the base's armed-add branch is dead here), and the drag target
        # is the grabbed handle's depth via the ``_event_world`` override --
        # never the surface pick.  Leaving the base's pick provider None makes
        # the add branch decline, which is the intended resection behaviour.

        # Injectable Algorithm-builder seam (bare-VTK unit layer); resolved
        # lazily from the wrapping on first use in production.
        self._control_polygon_geometry: Any | None = None
        #: Edge topology from the Algorithm builder + the (rows, cols) it
        #: was built for.
        #: Cursor world position the running frame drag is anchored at.
        self._group_anchor_world: Any | None = None
        #: Whether the cursor last sat on the frame (render-change gate).
        self._frame_hovered = False
        self._edge_cells: Any | None = None
        self._edge_cells_shape: tuple | None = None

        self._last_update_key: Any | None = None
        self._update_count = 0

        # Last (state, geometry-digest) a render was requested for — the
        # observer callback's render-request gate (see ``_on_node_modified``).
        self._last_render_key: tuple | None = None

        # The grabbed handle's flat index lives on the base's ``_drag_key``
        # (seeded by the base's ``__init__``); this pipeline reads it in the
        # ``_event_world`` drag override.

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
            self._data_node = displayNode.GetDisplayableNode()
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
        try:
            if self._data_node is None and fromNode is not None and fromNode is not self._display_node:
                self._data_node = fromNode
                self._attach_observer(fromNode)
                self._last_update_key = None
            self.UpdatePipeline()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    def OnRendererAdded(self, renderer: Any) -> None:  # noqa: N802 - VTK verb
        try:
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
                display = self.GetDisplayNode()
                if display is not None:
                    self.SetDisplayNode(display)
            self._attach_halo_renderer(renderer)
            self._last_update_key = None
            self.UpdatePipeline()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

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
        try:
            if renderer is not None:
                renderer.RemoveActor(self._handles_actor)
                renderer.RemoveActor(self._edges_actor)
            self._renderer = None
            self.cleanup()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    def UpdatePipeline(self) -> None:  # noqa: N802 - VTK verb
        """Reconcile handles + edges against the carrier grid and display."""
        try:
            self._reconcile()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    def _reconcile(self) -> None:
        """``UpdatePipeline``'s body — plain attribute access throughout."""
        # Late-bind the data node (creation-ordering tolerance; see
        # OnReferenceToDisplayNodeAdded).
        if self._data_node is None and self._display_node is not None:
            displayable = self._display_node.GetDisplayableNode()
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
        self._drag_key = None  # the base's grab bookkeeping
        self._hover_index = None
        self._halo_actor.SetVisibility(False)
        self._detach_halo_renderer()

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
    # Interaction -- the Planning per-point drag (ADR-0033, ex ADR-0032)
    #
    # The generic add/grab/drag/release arbitration is the shared base's
    # (ADR-0038 §Decision).  This pipeline contributes only the
    # RESECTION-specific parts through the base's extension hooks
    # (ADR-0038 §"What is not shared"): the Init/Planning gate
    # (``_admissible``), the control-point-depth drag target
    # (``_event_world``), the display-distance scan over the grid
    # (``_nearest_point_in_display``), and the Init->Planning commit + grab
    # colour + hover halo (``_on_grab`` / ``_on_drag`` / ``_on_release`` /
    # ``_on_bare_move_decline``).  ``CanProcessInteractionEvent`` /
    # ``ProcessInteractionEvent`` themselves are NOT overridden here -- the
    # base drives them.
    # ------------------------------------------------------------------ #

    def _admissible(self) -> bool:
        """Gate the base's arbitration on the resection state machine.

        Overrides the base's permissive default so the Init/Planning gate
        (ADR-0019 / ADR-0035) lives in the client, not in the base
        (ADR-0038 §"What is not shared").
        """
        return self._interaction_admissible()

    def _nearest_point_in_display(self, renderer: Any, eventData: Any):
        """Delegate the base's nearest-point scan to the grid scan.

        The base scans the provider's ``iter_points``; resection keeps the
        control-grid scan as its own seam so the characterization suite can
        pin it independently (``_nearest_control_point_in_display``).  Same
        ``(index, distance2)`` contract.
        """
        return self._nearest_control_point_in_display(renderer, eventData)

    def _event_world(self, renderer: Any, eventData: Any):
        """Back-project onto the GRABBED control point's depth (resection drag).

        Overrides the base's surface-snap default: a control-point drag
        follows the cursor on the grabbed handle's camera-facing plane, not
        the picked surface (ADR-0033).  ``None`` (no grab / unresolved)
        keeps the grab alive without moving anything.
        """
        # A GROUP drag has no grabbed point: the gesture translates the
        # whole set, so it follows the cursor on the plane through the
        # grid's CENTROID.  Without this the base resolves no world
        # position, claims the move (the camera stays put, which is why the
        # gesture looks dead rather than absent) and never calls the drag
        # hook.
        if self._group_drag is not None:
            return self._event_world_at_grid_centroid(renderer, eventData)

        idx = self._drag_key
        if idx is None:
            return None
        return self._event_world_at_control_point(renderer, eventData, idx)

    def _on_bare_move_decline(self, renderer: Any, eventData: Any) -> None:
        """Raise/clear the hover halo on a declined bare move (side effect)."""
        idx, distance2 = self._nearest_control_point_in_display(renderer, eventData)
        within = (
            idx is not None
            and distance2 <= CONTROL_POINT_PICK_RADIUS_PX * CONTROL_POINT_PICK_RADIUS_PX
        )
        self._set_hover(idx if within else None)

        # Frame hover: only when no handle owns the cursor, mirroring the
        # pick arbitration so the cue cannot promise a gesture the press
        # would not deliver.
        frame_hovered = False
        if not within and self._interaction_admissible():
            frame_d2 = self._frame_distance2_in_display(renderer, eventData)
            frame_hovered = (
                frame_d2 is not None and frame_d2 <= FRAME_PICK_RADIUS_PX**2
            )
        display_node = self._display_node
        group = (
            getattr(display_node, "GroupFrame", 0) if display_node is not None else 0
        )
        # Request a render when the frame hover CHANGES.  _set_hover
        # early-returns on an unchanged handle index and renders nothing,
        # so leaving the frame (with no handle involved) restyled the actor
        # and never flushed it -- the border stayed lit after the cursor
        # had gone.
        if frame_hovered != self._frame_hovered:
            self._frame_hovered = frame_hovered
            self._publish_group_state(hovered=group if frame_hovered else None)
            self._apply_frame_style()
            self._apply_interaction_scalars()
            self.RequestRender()

    def _on_grab(self, key: Any, renderer: Any, eventData: Any) -> None:
        """The resection grab: Init->Planning commit + grab colour + halo.

        The FIRST grab of a candidate surface in Init advances the carrier
        to Planning (the v1 first-surface-grab commit -- no button; raised
        through the state machine's single-writer discipline, ADR-0035,
        BEFORE the Planning-gated write so the very gesture is admitted).
        """
        if _safe_get_state(self._data_node) == STATE_INIT:
            _machine.request(self._data_node, _machine.EVENT_SURFACE_GRABBED)
        self._publish_interaction_state(grabbed=key)
        self._apply_interaction_scalars()
        self._hover_index = None
        self._set_hover(key)  # halo jumps to the grabbed handle
        # v1 parity: the press itself relocates the grabbed handle to the
        # cursor (the base's move-only default would defer this to the first
        # drag move).
        world = self._event_world_at_control_point(renderer, eventData, key)
        if world is not None:
            self._apply_world_point_to_control_point(key, world)

    def _on_drag(self, key: Any) -> None:
        """The halo follows the grabbed handle during the drag."""
        self._hover_index = None
        self._set_hover(key)

    # ------------------------------------------------------------------ #
    # Group gestures (ADR-0038 seam).  The FRAME drag translates the whole
    # control polygon rigidly -- every control point by the same delta --
    # and the surface follows because it is regenerated from the grid.
    # ------------------------------------------------------------------ #

    def _group_pick(self, renderer: Any, eventData: Any, etype: Any):
        """Claim a press as a group gesture, routed by BUTTON.

        * LEFT on any polygon edge -> the whole polygon translates.
        * RIGHT on a control POINT -> the ring containing that point
          translates.  Right on an edge is declined: edges carry the frame
          gesture, and addressing rings by point keeps the two off each
          other's pixels.

        Both decline when a handle owns the press.  The base asks this
        before the point pick, so without that check grabbing a corner
        would move a group instead of editing the point under the cursor.
        """
        if not self._interaction_admissible():
            return None
        if etype == vtk.vtkCommand.RightButtonPressEvent:
            return self._ring_pick(renderer, eventData)
        if etype != vtk.vtkCommand.LeftButtonPressEvent:
            return None

        frame_d2 = self._frame_distance2_in_display(renderer, eventData)
        if frame_d2 is None or frame_d2 > FRAME_PICK_RADIUS_PX**2:
            return None

        # PRECEDENCE, not proximity.  Boundary control points lie ON the
        # frame, so near a handle both distances are ~0 and comparing them
        # raw let sub-pixel noise decide -- a press on a corner handle
        # sometimes translated the whole polygon.  A handle owns any press
        # inside ITS OWN radius, full stop; the frame is only consulted
        # when no handle is in range.  This is the same rule the hover cue
        # applies, so the highlight can no longer promise a gesture the
        # press would not deliver.
        _idx, handle_d2 = self._nearest_control_point_in_display(renderer, eventData)
        if handle_d2 <= CONTROL_POINT_PICK_RADIUS_PX**2:
            return None  # a handle owns this press

        display_node = self._display_node
        group = (
            display_node.GroupFrame
            if display_node is not None and hasattr(display_node, "GroupFrame")
            else 0
        )
        return group, frame_d2

    def _ring_pick(self, renderer: Any, eventData: Any):
        """Claim a RIGHT press on a CONTROL POINT, for the ring it belongs to.

        A ring is addressed through its POINTS, not its segments.  The
        polygon's edges already carry the left-button frame gesture, and
        the outer ring's segments ARE those edges -- so picking by segment
        put two gestures on identical pixels with no way to aim at either.
        Picking by point removes the overlap entirely:

          * right on a control point -> the ring containing it translates
            (boundary point -> outer ring; interior point -> interior ring)
          * right anywhere else, edges included -> declined, and the view
            keeps its own right-button behaviour

        Every point belongs to exactly one ring (the memberships partition
        the grid), so the press is never ambiguous.
        """
        carrier = self._data_node
        if carrier is None:
            return None
        rings = _ring_groups(int(carrier.GetRows()), int(carrier.GetCols()))
        if not rings:
            return None

        try:
            index, distance2 = self._nearest_control_point_in_display(
                renderer, eventData
            )
        except Exception:  # pragma: no cover - rendererless stand-ins
            return None
        if index is None or distance2 > CONTROL_POINT_PICK_RADIUS_PX**2:
            return None

        display_node = self._display_node
        ring0 = (
            getattr(display_node, "GroupRing0", 1) if display_node is not None else 1
        )
        for ring_index, ring in enumerate(rings):
            if index in ring:
                return int(ring0) + ring_index, distance2
        return None

    def _ring_members(self, group: Any):
        """Flat control-point indices the group ``group`` translates.

        ``GroupFrame`` is the whole grid -- the frame is the affordance,
        its action is global -- while a ring group is just that ring.
        Returns ``None`` when the group does not resolve, so a caller
        moves nothing rather than guessing.
        """
        carrier = self._data_node
        if carrier is None:
            return None
        display_node = self._display_node
        frame = getattr(display_node, "GroupFrame", 0) if display_node else 0
        ring0 = getattr(display_node, "GroupRing0", 1) if display_node else 1

        rows = int(carrier.GetRows())
        cols = int(carrier.GetCols())
        if group == frame:
            return tuple(range(rows * cols))

        rings = _ring_groups(rows, cols)
        ring_index = int(group) - int(ring0)
        if 0 <= ring_index < len(rings):
            return tuple(rings[ring_index])
        return None

    def _on_group_grab(self, group: Any, renderer: Any, eventData: Any) -> None:
        """Anchor the drag at the cursor's world position."""
        self._group_anchor_world = self._event_world(renderer, eventData)
        # Drop any per-POINT hover before the group cue takes over.  The
        # handle halo is raised whenever the cursor is within a handle's
        # 20px radius, which near an edge it usually is -- so without this
        # a stray handle stayed lit through the whole group drag,
        # independently of the group cue and looking exactly like the
        # gesture was touching that point.
        self._set_hover(None)
        self._publish_group_state(grabbed=group)
        self._apply_frame_style()
        self._apply_interaction_scalars()
        self.RequestRender()

    def _on_group_drag(self, group: Any, world: Any) -> None:
        """Translate every control point by the cursor's delta.

        The anchor advances each move, so the delta is incremental: the
        polygon tracks the cursor without accumulating the rounding that
        an absolute origin would.
        """
        anchor = getattr(self, "_group_anchor_world", None)
        if anchor is None or world is None:
            return
        delta = (world[0] - anchor[0], world[1] - anchor[1], world[2] - anchor[2])
        members = self._ring_members(group)
        if members is None:
            return
        if self._translate_control_grid(delta, members):
            self._group_anchor_world = world

    def _on_group_release(self, group: Any) -> None:
        """End the gesture; the grid keeps the translation."""
        self._group_anchor_world = None
        # Drop the hover flag too: the cursor may have left the frame during
        # the drag, and the next bare move must be free to re-evaluate
        # rather than compare against a stale True.
        self._frame_hovered = False
        self._publish_group_state(grabbed=None, hovered=None)
        self._apply_frame_style()
        self._apply_interaction_scalars()
        self.RequestRender()

    def _translate_control_grid(self, delta, members=None) -> bool:
        """Displace ``members`` (default: every control point) by ``delta``.

        One write per point through the carrier's own setter, so the
        carrier raises its usual modified events and the surface, the
        slice projection and the resectogram all follow from one gesture.
        """
        carrier = self._data_node
        if carrier is None or _safe_get_state(carrier) != STATE_PLANNING:
            return False
        rows = int(carrier.GetRows())
        cols = int(carrier.GetCols())
        grid = carrier.GetControlGridVector()

        # ONE Modified for the whole translation.  SetControlPoint fires its
        # own Modified, so writing 16 points unbatched re-tessellated the
        # surface and reconciled every pipeline 16 times PER MOUSE MOVE --
        # the drag tracked the cursor correctly but crawled.  The batch is
        # the same idiom the state machine uses for its re-fit.
        if members is None:
            members = range(rows * cols)

        was_modifying = carrier.StartModify()
        try:
            for i in members:
                carrier.SetControlPoint(
                    i // cols,
                    i % cols,
                    grid[i * 3 + 0] + delta[0],
                    grid[i * 3 + 1] + delta[1],
                    grid[i * 3 + 2] + delta[2],
                )
        finally:
            carrier.EndModify(was_modifying)
        return True

    def _frame_distance2_in_display(self, renderer: Any, eventData: Any):
        """Squared display distance from the event pixel to ANY polygon edge.

        Every lattice segment counts, interior ones included: the polygon
        reads as a single object, so grabbing any part of its wireframe
        translates the whole thing.  Restricting this to the outer ring
        left the interior segments inert and, with handles owning a 20px
        radius, squeezed the grabbable band to the middle of each boundary
        edge.

        Distance is to the SEGMENTS, not the vertices -- measuring to
        vertices would leave the middle of a long edge unpickable.
        """
        carrier = self._data_node
        if carrier is None:
            return None
        rows = int(carrier.GetRows())
        cols = int(carrier.GetCols())
        if rows <= 0 or cols <= 0:
            return None

        grid = carrier.GetControlGridVector()

        # Project the whole grid once; the segment walk below reuses it.
        # A renderer that cannot project means NO GROUP CLAIM, not a broken
        # arbitration: the press falls through to the point path.  The
        # bare unit layer substitutes a rendererless stand-in, and a
        # gesture that cannot be aimed should never swallow a press that
        # the per-point drag can still service.
        try:
            ex, ey = eventData.GetDisplayPosition()
            screen = []
            for i in range(rows * cols):
                renderer.SetWorldPoint(
                    grid[i * 3 + 0], grid[i * 3 + 1], grid[i * 3 + 2], 1.0
                )
                renderer.WorldToDisplay()
                dx, dy, _dz = renderer.GetDisplayPoint()
                screen.append((dx, dy))
        except Exception:  # pragma: no cover - rendererless stand-ins
            return None

        best = None
        for r in range(rows):
            for c in range(cols):
                here = screen[r * cols + c]
                if c + 1 < cols:  # segment to the right
                    d2 = _point_segment_distance2(
                        float(ex), float(ey), here, screen[r * cols + c + 1]
                    )
                    if best is None or d2 < best:
                        best = d2
                if r + 1 < rows:  # segment downward
                    d2 = _point_segment_distance2(
                        float(ex), float(ey), here, screen[(r + 1) * cols + c]
                    )
                    if best is None or d2 < best:
                        best = d2
        return best

    def _apply_frame_style(self) -> None:
        """Colour the BORDER: cyan on hover, blue while the FRAME is held.

        The highlight names what MOVES, so exactly one channel lights per
        gesture:

        * HOVER          -- border cyan.  Says what you are pointing at.
        * FRAME held     -- border blue; the polygon is what is moving.
        * RING held      -- border UNCHANGED; the ring's own points light
          instead (see _apply_interaction_scalars), because they are what
          is moving.

        Lighting both for a ring said "the polygon and these four points",
        which is not what the gesture does.  Both border colours are COOL
        against the warm resting red and the warm point cues, so whichever
        channel is live stays legible.
        """
        display_node = self._display_node
        if display_node is None or not hasattr(display_node, "GetHoveredGroup"):
            return
        none_group = getattr(display_node, "GroupNone", -1)

        frame_group = getattr(display_node, "GroupFrame", 0)
        grabbed_group = display_node.GetGrabbedGroup()
        # The border lights for the FRAME gesture only.  The cue names what
        # MOVES: the frame moves the polygon, so the polygon lights; a ring
        # moves its own points, so those light instead (see
        # _apply_interaction_scalars) and the border stays out of it.
        grabbed_frame = grabbed_group == frame_group
        # ANY grab silences the hover cue.  A press does not clear hover, so
        # without this a ring drag left the border sitting on its cyan hover
        # colour -- still highlighted, just in the other colour, which is
        # exactly the "both channels lit" the ring case is meant to avoid.
        any_grab = grabbed_group != none_group
        hovered = not any_grab and display_node.GetHoveredGroup() != none_group

        prop = self._edges_actor.GetProperty()
        if grabbed_frame:
            prop.SetColor(*FRAME_GRAB_COLOR)
            return
        if hovered:
            prop.SetColor(*FRAME_HOVER_COLOR)
            return
        getter = getattr(display_node, "GetEdgeColor", None)
        if getter is not None:
            try:
                c = getter()
                prop.SetColor(float(c[0]), float(c[1]), float(c[2]))
            except Exception:  # pragma: no cover - defensive
                pass

    def _publish_group_state(self, hovered=..., grabbed=...) -> None:
        """Write group hover/grab onto the SHARED display node.

        On the node, not this instance: LayerDM does not drive a Python
        pipeline's attributes, so a frame hovered in one view would not
        light the frame in the others.
        """
        display_node = self._display_node
        if display_node is None or not hasattr(display_node, "SetHoveredGroup"):
            return
        none_value = getattr(display_node, "GroupNone", -1)
        if hovered is not ...:
            value = none_value if hovered is None else int(hovered)
            if display_node.GetHoveredGroup() != value:
                display_node.SetHoveredGroup(value)
        if grabbed is not ...:
            value = none_value if grabbed is None else int(grabbed)
            if display_node.GetGrabbedGroup() != value:
                display_node.SetGrabbedGroup(value)

    def _on_release(self) -> None:
        """Drop the grab colour + halo when the base clears the grab."""
        self._publish_interaction_state(grabbed=-1)
        self._apply_interaction_scalars()
        self._set_hover(None)

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
            if carrier is None:
                return
            grid = carrier.GetControlGridVector()
            base = int(index) * 3
            self._halo_sphere.SetRadius(self._handle_sphere.GetRadius() * HALO_HOVER_SCALE)
            self._halo_actor.SetPosition(grid[base], grid[base + 1], grid[base + 2])
            self._halo_actor.SetVisibility(True)
        self.RequestRender()

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
        if hovered is not None:
            value = -1 if hovered == -1 else int(hovered)
            if display.GetHoveredControlPoint() != value:
                display.SetHoveredControlPoint(value)
        if grabbed is not None:
            value = -1 if grabbed == -1 else int(grabbed)
            if display.GetGrabbedControlPoint() != value:
                display.SetGrabbedControlPoint(value)

    def _sync_halo_from_channel(self, polygon_visible: bool) -> None:
        """Drive the glow halo from the display-node interaction channel.

        The channel is the single source of truth, so a hover raised in a
        SLICE view shows the same 3D halo a local hover does; the grabbed
        point wins over a hover, and the halo repositions on every carrier
        reconcile (drags move the point under it).
        """
        display = self._display_node
        hovered = display.GetHoveredControlPoint() if display is not None else -1
        grabbed = display.GetGrabbedControlPoint() if display is not None else -1
        target = grabbed if grabbed >= 0 else hovered
        if not polygon_visible or target < 0:
            self._halo_actor.SetVisibility(False)
            return
        carrier = self._data_node
        if carrier is None:
            return
        grid = carrier.GetControlGridVector()
        base = int(target) * 3
        if len(grid) < base + 3:
            return
        self._halo_sphere.SetRadius(self._handle_sphere.GetRadius() * HALO_HOVER_SCALE)
        self._halo_actor.SetPosition(grid[base], grid[base + 1], grid[base + 2])
        self._halo_actor.SetVisibility(True)

    def _apply_interaction_scalars(self) -> None:
        """Colour the hovered/grabbed HANDLES from the display-node state.

        Derives per-point glyph scalars from the display node's
        HoveredControlPoint / GrabbedControlPoint, so highlights raised in
        OTHER views (the slice projections) colour this 3D view too.
        """
        display = self._display_node
        hovered = display.GetHoveredControlPoint() if display is not None else -1
        grabbed = display.GetGrabbedControlPoint() if display is not None else -1

        # A GROUP gesture highlights the points it will MOVE, not the whole
        # wireframe.  Lighting the border told the user a gesture was armed
        # but not which points it would take -- and for a ring that is the
        # only thing worth knowing, since the ring's members are the
        # difference between the gestures.
        none_group = getattr(display, "GroupNone", -1) if display is not None else -1
        group_grabbed = (
            display.GetGrabbedGroup() if display is not None else none_group
        )
        group_hovered = (
            display.GetHoveredGroup() if display is not None else none_group
        )
        # A held RING lights its members; a held FRAME lights none.
        #
        # The point cue exists to name a SUBSET.  The frame moves every
        # control point, so lighting all sixteen distinguishes nothing and
        # just doubles up on the border cue already saying "a gesture is
        # running".  A ring is the case where the subset is the whole
        # question, and that is where the points earn their colour.
        #
        # Hover lights no points at all -- that is the border's job.
        frame_group = getattr(display, "GroupFrame", 0) if display is not None else 0
        group_members = frozenset(
            self._ring_members(group_grabbed) or ()
            if group_grabbed != none_group and group_grabbed != frame_group
            else ()
        )
        _ = group_hovered

        points = self._handles_polydata.GetPoints()
        n = points.GetNumberOfPoints() if points is not None else 0
        base = [int(c * 255) for c in self._handles_actor.GetProperty().GetColor()]
        grab = [int(c * 255) for c in HALO_GRAB_COLOR]
        hover = [int(c * 255) for c in HALO_HOVER_COLOR]
        # A highlighted control point looks the SAME however it was
        # selected: the cue means "this point is affected", and that does
        # not change because a group picked it rather than a direct hover.
        # The border keeps its own cyan/blue cue for "a group gesture is
        # armed" -- that is a statement about the wireframe, not a point.
        group_rgb = grab
        colors = vtk.vtkUnsignedCharArray()
        colors.SetNumberOfComponents(3)
        colors.SetName("HandleColors")
        for i in range(n):
            if i in group_members:
                rgb = group_rgb
            elif i == grabbed:
                rgb = grab
            elif i == hovered:
                rgb = hover
            else:
                rgb = base
            colors.InsertNextTuple3(*rgb)
        self._handles_polydata.GetPointData().SetScalars(colors)
        self._handles_glyph.SetColorModeToColorByScalar()
        self._handles_mapper.SetColorModeToDirectScalars()
        self._handles_mapper.SetScalarVisibility(
            grabbed >= 0 or hovered >= 0 or bool(group_members)
        )
        self._handles_polydata.Modified()

    def GetHaloActor(self) -> Any:  # noqa: N802 - VTK verb
        return self._halo_actor

    def _apply_world_point_to_control_point(self, index: int, world: Any) -> bool:
        """Move the carrier's control point ``index`` to RAS ``world``.

        The grabbed-index write kernel: unlike the nearest-point kernel it
        never re-picks, so a drag cannot hop to another handle mid-gesture.
        Refuses outside ``Planning`` (ADR-0019).
        """
        carrier = self._data_node
        if carrier is None or _safe_get_state(carrier) != STATE_PLANNING:
            return False
        cols = int(carrier.GetCols())
        carrier.SetControlPoint(
            int(index) // cols,
            int(index) % cols,
            float(world[0]),
            float(world[1]),
            float(world[2]),
        )
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
        rows = int(carrier.GetRows())
        cols = int(carrier.GetCols())
        grid = carrier.GetControlGridVector()
        wx, wy, wz = float(world[0]), float(world[1]), float(world[2])

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
        carrier.SetControlPoint(best_idx // cols, best_idx % cols, wx, wy, wz)
        return best_idx

    def _nearest_control_point_in_display(self, renderer: Any, eventData: Any):
        """``(flat_index, distance2)`` of the handle nearest the event pixel."""
        import sys

        carrier = self._data_node
        if carrier is None:
            return None, sys.float_info.max
        grid = carrier.GetControlGridVector()
        rows = int(carrier.GetRows())
        cols = int(carrier.GetCols())
        ex, ey = eventData.GetDisplayPosition()

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

    def _event_world_at_grid_centroid(self, renderer: Any, eventData: Any):
        """Back-project the event pixel onto the control grid's centroid depth.

        The depth reference for a GROUP gesture.  A rigid translation has
        no single grabbed point to take depth from, and picking one member
        arbitrarily would make the polygon swing differently depending on
        which edge was grabbed.  The centroid keeps the motion the same
        whichever part of the frame the cursor holds.
        """
        carrier = self._data_node
        if carrier is None:
            return None
        try:
            rows = int(carrier.GetRows())
            cols = int(carrier.GetCols())
            grid = carrier.GetControlGridVector()
            count = rows * cols
            if count <= 0:
                return None
            cx = sum(grid[i * 3 + 0] for i in range(count)) / count
            cy = sum(grid[i * 3 + 1] for i in range(count)) / count
            cz = sum(grid[i * 3 + 2] for i in range(count)) / count

            ex, ey = eventData.GetDisplayPosition()
            renderer.SetWorldPoint(cx, cy, cz, 1.0)
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

    def _event_world_at_control_point(self, renderer: Any, eventData: Any, idx: int):
        """Back-project the event pixel onto control point ``idx``'s depth.

        The try/except is FLOW, not a guard: a move that fails to resolve
        returns ``None`` so the caller keeps the grab alive.
        """
        carrier = self._data_node
        if carrier is None:
            return None
        try:
            grid = carrier.GetControlGridVector()
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

    def _interaction_admissible(self) -> bool:
        """True when the polygon may claim/process gestures.

        Planning, or the Init candidate phase (ADR-0035: candidate
        raised by a drop's re-fit, no plane-handle drag in flight).
        The first Init-phase press is the Init -> Planning commit.
        """
        state = _safe_get_state(self._data_node)
        if state == STATE_PLANNING:
            return True
        return state == STATE_INIT and _machine.candidate_active(self._data_node)

    def _compute_visibility(self, state: Any) -> bool:
        """Planning, or the Init CANDIDATE phase; display-Visibility gated.

        The candidate phase is v1's composite loop: a release re-fit
        raised the candidate surface and no plane-handle drag is in
        flight — the polygon shows (and is grabbable) alongside the init
        handles + contour, and its first grab commits Init -> Planning.
        """
        if state == STATE_PLANNING:
            pass
        elif state == STATE_INIT and _machine.candidate_active(self._data_node):
            pass
        else:
            return False
        display = self._display_node
        if display is None:
            return True
        return bool(display.GetVisibility())

    def _refresh_geometry(self) -> None:
        """Rebuild handle points + polygon edges from the carrier grid."""
        carrier = self._data_node
        if carrier is None:
            return
        raw = carrier.GetControlGridVector()
        rows = int(carrier.GetRows())
        cols = int(carrier.GetCols())
        points = vtk.vtkPoints()
        points.SetNumberOfPoints(rows * cols)
        for i in range(rows * cols):
            points.SetPoint(i, float(raw[i * 3]), float(raw[i * 3 + 1]), float(raw[i * 3 + 2]))

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
        cells = self._edge_cells
        if cells is None:
            # No topology yet: clear rather than render stale content --
            # a leftover solid line must never masquerade as the scaffold.
            self._edges_polydata.SetPoints(vtk.vtkPoints())
            self._edges_polydata.SetLines(vtk.vtkCellArray())
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

        # Re-assert the group highlight LAST.  The block above restores the
        # display node's own edge colour on every reconcile, and a drag
        # reconciles on each move -- so without this the highlight was
        # repainted away the moment the gesture it belongs to did any work.
        self._apply_frame_style()

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
        try:
            self.UpdatePipeline()

            display = self._display_node
            interaction = (
                display.GetHoveredControlPoint() if display is not None else -1,
                display.GetGrabbedControlPoint() if display is not None else -1,
            )
            render_key = (
                _safe_get_state(self._data_node),
                _control_points_digest(self._data_node),
                interaction,
                # The Init phase gates the polygon's visibility (ADR-0035
                # candidate) -- a phase flip must repaint this view even
                # when the flip came from the OTHER pipeline's gesture.
                _machine.phase_token(self._data_node),
            )
            if render_key == self._last_render_key:
                return
            self._last_render_key = render_key

            self.RequestRender()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass


def _control_points_digest(node: Any) -> tuple:
    """Digest of the carrier's control-point positions (render-request gate).

    Mirrors the ResectogramPipeline's memo digest: a control-point edit
    changes the digest, a render-induced ``Modified`` at fixed geometry does
    not — the discrimination that keeps drags repainting live while blocking
    a render feedback loop.  Empty tuple when no carrier is attached.
    """
    if node is None:
        return ()
    grid = node.GetControlGridVector()
    usable = len(grid) - (len(grid) % 3)
    return tuple(
        (grid[base], grid[base + 1], grid[base + 2])
        for base in range(0, usable, 3)
    )


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
        try:
            if not isinstance(viewNode, vtkMRMLViewNode):
                return None
            if viewNode.GetSingletonTag() == RESECTOGRAM_VIEW_SINGLETON_TAG:
                return None
            if not isinstance(node, vtkMRMLControlPolygonDisplayNode):
                return None
            return ControlPolygonPipeline()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            return None

    creator = vtkMRMLLayerDMPipelineScriptedCreator()
    creator.SetPythonCallback(tryCreate)
    vtkMRMLLayerDMPipelineFactory.GetInstance().AddPipelineCreator(creator)
    _REGISTERED = True

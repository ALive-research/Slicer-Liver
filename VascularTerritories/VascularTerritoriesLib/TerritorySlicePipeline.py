# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Slice-view LayerDM Pipeline for vessel-annotation placement + viz (ADR-0037).

The 2D-slice complement of ``TerritoryPlacementPipeline``: the SAME arm
state / active territory / carrier live on the shared highlight display
node (``TerritoryInteractionState``), so 2D and 3D placement stay in
lockstep -- an armed click in a slice view appends one surface-snapped seed
to the ACTIVE territory, exactly as an armed click in a 3D view does.

ADR-0038 §Decision makes this a thin CLIENT of the shared
``SurfacePointPlacementPipelineSlice`` base: the base DRIVES the generic
grab-to-edit-nearest / armed add-on-click / bare-move-decline arbitration
(``Can/ProcessInteractionEvent``) AND the generic projection/fade/side-tint/
presence + hollow-circle handles + hover ring; this client contributes ONLY
the territory-SPECIFIC concerns through the base's extension hooks (ADR-0038
§"What is not shared"):

* per-territory grouping + active-territory routing (the ``add_point`` fan
  into the active territory, on ``TerritoryPointProvider`` + this pipeline);
* the key seam override (``_iter_keyed_points`` -> ``(territoryId, index)``
  keys) so the base's projection stores the carrier key each seed round-trips
  through;
* vessel-visibility gating -- a hidden vessel surface is not pickable and a
  hidden seed is neither grabbable nor drawn -- via ``_ensure_pick`` over the
  visibility-filtered ``vascular_surface_polydata`` and the
  ``VisibleStructuresCache``-backed ``seed_visible`` filter in the projection;
* the vessel-adhering cross-view hover marker (the ``_highlight_actor``
  preview + the shared display node's AdheringPointWorld channel), and the
  per-segment seed show/hide -- none of which bleed into the base.

Mirrors ``LiverResectionsLib.SliceControlPolygonPipeline`` (ADR-0033): the
carrier's annotation points are projected into the slice view's XY space
(``inverse(XYToRAS)``) with DISTANCE FADING, a signed above/below SIDE
TINT, and a HARD presence cutoff (2D alpha is unreliable) -- all owned by the
shared base.  Rendering rebuilds on a carrier ``Modified`` and on slice
reslice (the slice node is observed).

Keyed on ``(vtkMRMLSliceNode, vtkMRMLTerritoriesHighlightDisplayNode)`` --
the slice-view half of the annotation placement (the 3D creator accepts
only ``vtkMRMLViewNode``).  ADR-0013 §5 keeps the (view-type, display-type)
keying disjoint per pair; rendering + interaction route through this
scripted Pipeline + its creator, never a custom displayable manager.
"""

from __future__ import annotations

from typing import Any

import vtk

# The shared slice-view placement/edit base (ADR-0038 §Decision): territories
# is the vessel-gated client of ``SurfacePointPlacementPipelineSlice`` over the
# PointProvider + swappable-pick seam.  The base drives the generic
# grab/drag/release + armed add-on-click arbitration AND the projection/fade/
# side/presence + handles/ring; this pipeline keeps the per-territory grouping,
# the vessel-visibility gating, and the cross-view adhering marker as overrides
# (ADR-0038 §"What is not shared").
try:  # pragma: no cover - exercised once per import path
    from SlicerLiverInteractionLib.SurfacePointPlacementPipelineSlice import (
        SurfacePointPlacementPipelineSlice as _PipelineBase,
        POINT_PICK_RADIUS_PX,
        HALO_HOVER_COLOR,
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
        POINT_PICK_RADIUS_PX,
        HALO_HOVER_COLOR,
    )
    import SlicePointProjection as _proj  # type: ignore[no-redef]

try:  # pragma: no cover - exercised once per import path
    from .VesselSurfacePick import VesselSurfacePick
    from .VesselHighlightWiring import (
        vascular_surface_polydata,
        visibility_mtime as _visibility_mtime,
        VisibleStructuresCache as _VisibleStructuresCache,
    )
    from .TerritoryPointProvider import TerritoryPointProvider
    from . import TerritoryInteractionState as _state
except ImportError:  # top-level import path (the unit layer's sys.path setup)
    from VesselSurfacePick import VesselSurfacePick  # type: ignore[no-redef]
    from VesselHighlightWiring import (  # type: ignore[no-redef]
        vascular_surface_polydata,
        visibility_mtime as _visibility_mtime,
        VisibleStructuresCache as _VisibleStructuresCache,
    )
    from TerritoryPointProvider import (  # type: ignore[no-redef]
        TerritoryPointProvider,
    )
    import TerritoryInteractionState as _state  # type: ignore[no-redef]

_REGISTERED = False

#: Adhering-placement preview glyph diameter (XY pixels): the hover marker is a
#: hollow-circle HANDLE preview, styled like a seed handle (not a crosshair).
HANDLE_GLYPH_SCALE_PX = 13.0


def _creator_accepts_view(viewNode: Any) -> bool:  # noqa: N803 - VTK arg name
    """True iff ``viewNode`` is a slice view (this pipeline's home).

    Part of the creator callback: LayerDM invokes it for every
    ``(view, node)`` pair, so it must never raise.
    """
    try:
        return viewNode is not None and bool(viewNode.IsA("vtkMRMLSliceNode"))
    except Exception:  # pragma: no cover - C++ boundary must never raise
        return False


class TerritorySlicePipeline(_PipelineBase):
    """Projected, fading, slice-editable territory annotation seeds.

    A thin client of ``SurfacePointPlacementPipelineSlice``: the base owns the
    handle projection/fade/side/presence + the grab-seam + armed add-on-click
    arbitration + the hover ring, this pipeline supplies the territory data
    model (the active-territory fan), the vessel-visibility gating, and the
    cross-view adhering marker.
    """

    def __init__(self) -> None:
        # The base seeds ``_display_node`` / ``_slice_node`` / ``_renderer`` /
        # ``_drag_key`` / ``_provider`` / ``_pick_provider``, the handle + ring
        # actors, the projection bookkeeping (``_projected_keys`` /
        # ``_projected_xy`` / ``_plane_distances``), and calls
        # ``SetPythonObject``.  The ``"TerritoryPlacement"`` namespace is inert
        # here: the arm / active-territory / carrier accessors are OVERRIDDEN to
        # ride the shared highlight display node via ``TerritoryInteractionState``
        # (the 3D client's precedent), so 2D and 3D stay in lockstep.
        super().__init__(namespace="TerritoryPlacement")

        self._observed_carrier: Any | None = None
        # The pickSurface segmentation's display node, observed so a
        # structures-table show/hide reprojects the 2D seeds (a visibility
        # change modifies the segmentation display node, not the carrier;
        # ADR-0037 slice 5).
        self._observed_pick_display: Any | None = None

        # Injectable pick core (bare unit layer feeds a known surface); in
        # production ``_ensure_pick`` builds it from the display node's
        # pickSurface (the ``TerritoryPlacementPipeline`` precedent), rebuilt
        # when segment visibility changes (``_pick_surface_mtime``).
        self._pick: VesselSurfacePick | None = None
        self._pick_injected: bool = False
        self._pick_surface_mtime: int | None = None

        # Per-segment vessel structures (segId, surface, visible) for the
        # projected-seed show/hide follow (ADR-0037 slice 5), cached by the
        # display node's visibility MTime (the ``_ensure_pick`` pattern).
        self._structures = _VisibleStructuresCache()

        # (territory id, in-territory index) of the seed under the cursor (the
        # hover grab affordance), None when the cursor is over none.  The
        # grabbed seed is the base's ``_drag_key`` (aliased below), so there is
        # ONE grab source of truth (the base's field).
        self._hover_target: tuple[str, int] | None = None

        # Wire the ADR-0038 seams:
        #  * the data model -- the base reads/projects the carrier seeds via
        #    this provider (flat, no edges -- territory seeds are unordered),
        #    dual-gated on the territory-row toggle + the per-seed vessel-
        #    segment visibility (re-read through this pipeline so a unit-layer
        #    monkeypatch of ``_seed_visible`` is honoured);
        #  * the click->world pick -- routed through ``_pick_world`` ->
        #    ``_snap_event_to_surface`` (the vessel-visibility-gated surface
        #    snap, the unit-layer + placemode-test monkeypatch seam), NOT a
        #    surface-vs-volume branch in the base (ADR-0038 §"Base extension").
        self.SetProvider(
            TerritoryPointProvider(
                carrier_getter=self._get_carrier,
                territory_getter=self._placement_territory,
                visible_getter=lambda point: self._seed_visible(point),
            )
        )
        self.SetPickProvider(_TerritorySlicePick(self))

        # Seed HANDLES: the base's ``_handles_actor`` IS this pipeline's seed
        # actor (the base's projection populates it -- hollow-circle 2D glyphs
        # with the SliceControlPolygonPipeline RGBA side-tint + distance fade).
        # Alias it (+ the polydata) so the introspection seams the territory
        # suite reads (``_seed_actor`` / ``_seed_polydata``) resolve to the
        # base's single source of truth.
        self._handles_actor.GetProperty().SetLineWidth(2.0)
        self._seed_actor = self._handles_actor
        self._seed_polydata = self._handles_polydata

        # Adhering-placement PREVIEW: a hollow-circle handle (yellow, the hover
        # colour) at the shared display node's AdheringPointWorld projected into
        # THIS slice -- where an armed click would drop a seed.  Published by
        # whichever view the cursor is in, so it shows in every view at once
        # (ADR-0033 cross-view cue).  Territory-specific, so it is NOT a base
        # actor; built WITH its mapper (a mapperless vtkActor2D crashes under
        # GL, per the construction contract).
        self._highlight_polydata = vtk.vtkPolyData()
        self._highlight_polydata.SetPoints(vtk.vtkPoints())
        self._highlight_glyph_source = vtk.vtkGlyphSource2D()
        self._highlight_glyph_source.SetGlyphTypeToCircle()
        self._highlight_glyph_source.FilledOff()
        self._highlight_glyph_source.SetScale(HANDLE_GLYPH_SCALE_PX)
        self._highlight_glyph = vtk.vtkGlyph2D()
        self._highlight_glyph.SetInputData(self._highlight_polydata)
        self._highlight_glyph.SetSourceConnection(self._highlight_glyph_source.GetOutputPort())
        self._highlight_glyph.ScalingOff()
        self._highlight_mapper = vtk.vtkPolyDataMapper2D()
        self._highlight_mapper.SetInputConnection(self._highlight_glyph.GetOutputPort())
        self._highlight_actor = vtk.vtkActor2D()
        self._highlight_actor.GetProperty().SetLineWidth(2.0)
        self._highlight_actor.GetProperty().SetColor(*HALO_HOVER_COLOR)
        self._highlight_actor.SetMapper(self._highlight_mapper)
        self._highlight_actor.SetVisibility(False)

    # ------------------------------------------------------------------ #
    # Grab bookkeeping -- the base's ``_drag_key`` IS the grabbed
    # ``(territoryId, index)`` (the key the projection stores); the rendering
    # reads it through this alias so there is one source of truth.
    # ------------------------------------------------------------------ #

    @property
    def _drag_target(self) -> tuple[str, int] | None:
        return self._drag_key

    @_drag_target.setter
    def _drag_target(self, value: tuple[str, int] | None) -> None:
        self._drag_key = value

    # ------------------------------------------------------------------ #
    # Wiring seams (unit + production)
    # ------------------------------------------------------------------ #

    def SetPickCore(self, pick: VesselSurfacePick | None) -> None:  # noqa: N802 - VTK verb
        """Inject the ``VesselSurfacePick`` over the target surface (unit seam)."""
        self._pick = pick
        self._pick_injected = pick is not None

    def _ensure_pick(self) -> VesselSurfacePick | None:
        """Build the pick core against the display node's ``pickSurface`` mesh.

        Production instances resolve the surface from the shared display node
        exactly as ``TerritoryPlacementPipeline`` does, so the 2D and 3D snaps
        adhere to the SAME mesh (and both drop a hidden vessel from collision
        detection on a visibility change).  A test-injected ``self._pick``
        short-circuits this for the bare unit layer.
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
        # Visible vessels only (ADR-0037 slice 5): the cursor snaps to a vessel
        # you can see, never the parenchyma, a tumour, or a hidden vessel.
        self._pick = None
        self._pick_surface_mtime = mtime
        polydata = vascular_surface_polydata(segmentation)
        if polydata is None:
            return None
        self._pick = VesselSurfacePick(polydata)
        return self._pick

    def _visible_structures(self) -> list:
        """The per-segment vessel structures ``[(segId, surface, visible)]``.

        Resolved + cached via the shared ``VisibleStructuresCache`` from the
        display node's ``pickSurface`` (the ``TerritoryPlacementPipeline``
        seam); ``[]`` under a test-injected pick -> seeds are never hidden bare.
        """
        return self._structures.resolve(self._display_node)

    def _seed_visible(self, point: Any) -> bool:
        """True iff ``point``'s nearest vessel structure is visible.

        The vessel-visibility gate (ADR-0037 slice 5) the provider's keyed
        traversal consults, so a hidden vessel's seeds are neither drawn nor
        grabbable (the base projects exactly the provider's points).  The REAL
        seed-visibility notion (vessel SEGMENT visibility via
        ``VisibleStructuresCache``), NOT a territory-row toggle (ADR-0037
        slice 5).
        """
        return self._structures.seed_visible(self._display_node, point)

    def _get_carrier(self) -> Any | None:
        """The carrier the shared display node binds (the 3D-pipeline seam)."""
        return _state.get_carrier(self._display_node)

    def _placement_territory(self) -> str | None:
        """The territory an armed click appends into (the ACTIVE one)."""
        return _state.get_active_territory(self._display_node)

    def SetActiveTerritory(self, territoryId: str | None) -> None:  # noqa: N802 - VTK verb
        """Set the territory an armed slice click appends into (the ACTIVE one)."""
        _state.set_active_territory(self._display_node, territoryId)

    # ------------------------------------------------------------------ #
    # Arm / module-active gate -- OVERRIDE the base's PointPlacementState
    # accessors so the territory client rides the shared highlight display node
    # via ``TerritoryInteractionState`` (the 3D client's precedent), which also
    # carries the active territory + the carrier reference; 2D and 3D placement
    # stay in lockstep (ADR-0037 §Decision 3).
    # ------------------------------------------------------------------ #

    def IsArmed(self) -> bool:  # noqa: N802 - VTK verb
        return _state.is_armed(self._display_node)

    def SetModuleActive(self, active: bool) -> None:  # noqa: N802 - VTK verb
        """Open/close the module-active add-on-click gate (concern #1).

        Mirrors ``TerritoryPlacementPipeline``: a slice add-on-click is declined
        while the owning module is inactive, independent of the armed flag.
        Rides the shared display node in production, the instance field bare.
        """
        if self._display_node is not None:
            _state.set_module_active(self._display_node, bool(active))
        self._module_active = bool(active)

    def IsModuleActive(self) -> bool:  # noqa: N802 - VTK verb
        if self._display_node is not None:
            return _state.is_module_active(self._display_node)
        return self._module_active

    # ------------------------------------------------------------------ #
    # LayerDM lifecycle (base hooks + territory observers)
    # ------------------------------------------------------------------ #

    def _after_display_node_set(self) -> None:
        # A (re)attached display node can carry a different pickSurface /
        # carrier: force the pick to re-resolve (the highlight-Pipeline
        # precedent), then re-observe the carrier + pickSurface.
        self._pick = None
        self._ensure_carrier_observed()
        self._ensure_pick_surface_observed()

    def _add_actors(self, renderer: Any) -> None:
        super()._add_actors(renderer)
        renderer.AddActor2D(self._highlight_actor)

    def _remove_actors(self, renderer: Any) -> None:
        super()._remove_actors(renderer)
        renderer.RemoveActor2D(self._highlight_actor)

    def OnRendererAdded(self, renderer: Any) -> None:  # noqa: N802 - VTK verb
        super().OnRendererAdded(renderer)
        try:
            self._ensure_carrier_observed()
            self._reconcile_highlight()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    def UpdatePipeline(self) -> None:  # noqa: N802 - VTK verb
        """LayerDM's re-sync hook: reproject the seeds + repaint the highlight.

        LayerDM's manager owns the display-node observation and calls this when
        the pipeline's display node is Modified (a hover-published adhering
        point from ANY view, an arm/visibility change).  Also (re)attaches the
        carrier observer: the display node is added to the scene (LayerDM
        creates this pipeline) BEFORE the table binds the carrier reference
        onto it, so the carrier is not resolvable at creation.  This hook fires
        when the reference IS set, so it is where the seed-tracking observer
        finally attaches.
        """
        try:
            self._ensure_carrier_observed()
            self._ensure_pick_surface_observed()
            self._reconcile()
            self._reconcile_highlight()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    def cleanup(self) -> None:
        super().cleanup()
        self._observed_carrier = None
        self._observed_pick_display = None
        self._hover_target = None
        self._highlight_actor.SetVisibility(False)

    def _ensure_carrier_observed(self) -> None:
        """Observe the in-effect carrier so seed glyphs track its edits."""
        carrier = self._get_carrier()
        if carrier is self._observed_carrier:
            return
        if self._observed_carrier is not None:
            self._detach_observer(self._observed_carrier)
        self._observed_carrier = carrier
        if carrier is not None:
            self._attach_observer(carrier)

    def _ensure_pick_surface_observed(self) -> None:
        """Observe the pickSurface segmentation's display node for visibility.

        A segment show/hide modifies the segmentation display node (not the
        carrier); observe it so the 2D seeds reproject -- dropping/restoring a
        hidden structure's seeds -- via ``_on_node_modified`` (which reprojects
        for any non-display-node caller).  Idempotent; re-attaches on change.
        """
        display = self._display_node
        segmentation = (display.GetPickSurfaceNode()
                        if display is not None and hasattr(display, "GetPickSurfaceNode")
                        else None)
        seg_display = segmentation.GetDisplayNode() if segmentation is not None else None
        if seg_display is self._observed_pick_display:
            return
        if self._observed_pick_display is not None:
            self._detach_observer(self._observed_pick_display)
        self._observed_pick_display = seg_display
        if seg_display is not None:
            self._attach_observer(seg_display)

    # ------------------------------------------------------------------ #
    # Base extension hooks -- the territory specifics (ADR-0038)
    # ------------------------------------------------------------------ #

    def _iter_keyed_points(self):
        """Yield ``((territoryId, index), world, base_rgb)`` per visible seed.

        The key seam override (ADR-0038): delegate to the provider's keyed
        traversal so the base's projection stores each seed's carrier key --
        the ``(territoryId, index)`` pair the grab / drag / delete write-backs
        round-trip through ``move_point`` / ``delete_point``.  The projected
        keys ``GetProjectedKeys`` returns are then the territory keys the suite
        asserts (e.g. ``[(TERRITORY_A, 0)]``), not flat ints.
        """
        provider = self._provider
        if provider is None:
            return
        for key, (world, base_rgb) in provider.iter_keyed_points():
            yield key, world, base_rgb

    def _interaction_state(self) -> tuple:
        """``(hovered, grabbed)`` for the projection highlight.

        Feeds the base's projection the same hover/grab targets the seeds must
        recolour to (yellow hover / green grab): the cursor's hover seed +
        the base's grabbed key.  ``None`` targets simply never match a
        projected key, so no seed lights up (the base's default-off sentinel).
        """
        return self._hover_target, self._drag_key

    def _pick_world(self, eventData: Any):
        """Route the base's armed add-on-click through the vessel surface snap.

        Overrides the base's default pick delegate so the SINGLE snap seam is
        ``_snap_event_to_surface`` (the unit-layer + placemode-test monkeypatch
        target), keeping the vessel-visibility-gated surface snap the only
        placement constraint (no straddle-snap; revised ADR-0037 slice 5).
        """
        return self._snap_event_to_surface(eventData)

    def _add_point(self, world: Any) -> None:
        """Fan the armed click into the ACTIVE territory + repaint this slice.

        Overrides the base's plain provider ``add_point`` only to repaint this
        slice immediately (a carrier-observer RequestRender does not flush a
        frame mid-interaction, so the seed would otherwise only appear on the
        next reslice).  The per-territory grouping itself is the provider's
        concern -- it appends into ``_placement_territory``.
        """
        provider = self._provider
        if provider is not None:
            provider.add_point((world[0], world[1], world[2]))
        self._reproject()
        self.RequestRender()

    def _on_grab(self, key: Any) -> None:
        """Grab an existing seed: recolour it green + ring, immediately."""
        self._reproject()
        self.RequestRender()

    def _on_release(self) -> None:
        """Gesture over: drop the grab colour + ring."""
        self._reproject()
        self.RequestRender()

    def _move_grabbed_to(self, eventData: Any) -> None:
        """Relocate the grabbed seed to the surface snap, then repaint.

        The slice drag follows the cursor on the picked vessel surface (the
        same snap the add uses), writing back through the provider so the
        ``(territoryId, index)`` key round-trips; a missed snap keeps the grab
        (no move).
        """
        world = self._snap_event_to_surface(eventData)
        if world is None:
            return
        provider = self._provider
        if provider is not None and self._drag_key is not None:
            provider.move_point(self._drag_key, (world[0], world[1], world[2]))
        self._reproject()
        self.RequestRender()

    def _on_bare_move_decline(self, eventData: Any) -> None:
        """Raise the cross-view hover cue on a declined bare move (ADR-0033).

        Over an existing handle -> mark it the hover target (yellow ring, grab
        affordance) + clear the placement preview; over empty surface -> publish
        the adhering point so the placement preview follows the cursor in every
        view.  Repaints THIS slice directly -- it must not wait on the
        cross-view update path.  A declined bare move, so the camera is
        untouched.
        """
        key, distance2 = self._nearest_handle_in_display(eventData)
        if key is not None and distance2 <= POINT_PICK_RADIUS_PX * POINT_PICK_RADIUS_PX:
            self._hover_target = key
            self._clear_highlight()
        else:
            self._hover_target = None
            self._publish_highlight(eventData)
        self._reproject()
        self._reconcile_highlight()
        self.RequestRender()

    def DeleteAnnotationPoint(self, territoryId: str, index: int) -> bool:  # noqa: N802 - VTK verb
        """Remove EXACTLY ONE seed via the carrier (the shared deletion path)."""
        carrier = self._get_carrier()
        if carrier is None:
            return False
        return bool(carrier.RemoveNthAnnotationPoint(territoryId, int(index)))

    # ------------------------------------------------------------------ #
    # Snap (the vessel surface pick along the slice normal)
    # ------------------------------------------------------------------ #

    def _snap_event_to_surface(self, eventData: Any, use_fallback: bool = True):
        """Snap a slice-view pixel onto the vessel surface along the normal.

        Resolves the pixel to RAS ON the slice plane (``XYToRAS``), casts a
        ray ALONG THE SLICE NORMAL through it, and feeds it to
        ``VesselSurfacePick`` -> the surface-snapped world point (``None`` on
        a miss / no surface).  Kept GL-free (the unit layer injects the pick
        result), unlike the 3D pipeline's camera-ray unprojection.

        ``use_fallback`` (placement) lands the in-plane RAS point when the
        normal ray misses, so an armed click still drops a seed on the plane;
        the hover highlight passes ``use_fallback=False`` so it hides
        off-surface (the 3D ``VesselHighlightPipeline`` honest-cue convention).
        """
        pick = self._ensure_pick()
        if pick is None:
            return None
        try:
            ex, ey = eventData.GetDisplayPosition()
        except Exception:  # pragma: no cover - defensive (fake events)
            return None
        ras = _proj.xy_to_ras_on_plane(self._slice_node, ex, ey)
        if ras is None:
            return None
        ray = _proj.normal_ray(self._slice_node, ras)
        if ray is None:
            return None
        p1, p2 = ray
        return pick.pick(p1, p2, fallback_point=(ras if use_fallback else None))

    # ------------------------------------------------------------------ #
    # Cross-view adhering highlight (publish on hover / render the marker)
    # ------------------------------------------------------------------ #

    def _publish_highlight(self, eventData: Any) -> None:
        """Publish the cursor's surface point onto the shared display node.

        A bare hover in this slice resolves the vessel-surface point under the
        cursor (along the slice normal, no in-plane fallback) and writes it
        onto the data-only highlight display node, so EVERY view's Pipeline
        paints the adhering marker there (the cross-view hover cue).
        Change-gated so the hover does not storm ``Modified``.
        """
        display = self._display_node
        if display is None or not hasattr(display, "SetAdhering"):
            return
        world = self._snap_event_to_surface(eventData, use_fallback=False)
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

    def _clear_highlight(self) -> None:
        """Clear the shared adhering point (cursor is over a handle, not empty surface).

        Publishing ``adhering=False`` retires the placement preview in EVERY
        view so it does not compete with the grab ring on the hovered handle.
        """
        display = self._display_node
        if display is None or not hasattr(display, "SetAdhering"):
            return
        if bool(display.GetAdhering()):
            display.SetAdhering(False)
            display.Modified()

    def _reconcile_highlight(self) -> None:
        """Project the shared adhering point into this slice as the hover marker.

        Reads the data-only display node (the adhering point + flags any view
        published) and shows a hollow-circle handle PREVIEW (yellow, the hover
        colour) at its projection.  Unlike the seeds, the preview is a TRANSIENT
        cue and is NOT distance-culled: the surface point under the cursor sits
        at the vessel's depth (a radius OFF the slice plane along the normal),
        so a presence cutoff would hide it in the very slice being hovered.
        """
        display = self._display_node
        slice_node = self._slice_node
        points = vtk.vtkPoints()
        show = False
        try:
            if (
                display is not None
                and slice_node is not None
                and bool(display.GetAdhering())
                and bool(display.GetVisibility())
            ):
                ras_to_xy = _proj.inverse_xy_to_ras(slice_node)
                if ras_to_xy is not None:
                    world = display.GetAdheringPointWorld()
                    xy = _proj.apply_matrix_xy(ras_to_xy, world)
                    points.InsertNextPoint(xy[0], xy[1], 0.0)
                    show = True
        except Exception:  # pragma: no cover - defensive
            show = False
        self._highlight_polydata.SetPoints(points)
        self._highlight_polydata.Modified()
        self._highlight_actor.SetVisibility(show)

    # ------------------------------------------------------------------ #
    # Introspection (unit seams)
    # ------------------------------------------------------------------ #

    def GetSeedActor(self) -> Any:  # noqa: N802 - VTK verb
        return self._seed_actor

    def GetSeedPolyData(self) -> Any:  # noqa: N802 - VTK verb
        return self._seed_polydata

    # ------------------------------------------------------------------ #
    # Observers -- reproject on a carrier / slice Modified; repaint the marker
    # only on a display-node Modified (the cross-view adhering channel).
    # ------------------------------------------------------------------ #

    def _on_node_modified(self, caller: Any, event: str) -> None:
        """Reconcile on a carrier / slice ``Modified`` -- reproject + render.

        The Pipeline holds no shadow copy of the seed set: the carrier IS the
        source of truth, so a reconcile driven by an unrelated ``Modified``
        (a table repaint, a colour change) reprojects without adding / moving
        / dropping any seed (ADR-0037 §Conformance no-drift).  A display-node
        Modified is (almost always) an adhering-point / visibility change from
        a hover in SOME view: repaint the marker only, keeping the per-hover
        cost off the full seed reprojection.
        """
        del event
        try:
            if caller is not self._display_node:
                self._reproject()
            self._reconcile_highlight()
            self.RequestRender()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass


class _TerritorySlicePick:
    """The base's pick provider, delegating to the pipeline's surface snap.

    The base places a click at whatever world the pick returns (ADR-0038
    §"Base extension" -- no surface-vs-volume branch).  Territories' pick is
    the vessel-visibility-gated surface snap, which also stays the unit-layer +
    placemode-test monkeypatch seam (``_snap_event_to_surface``): this adapter
    forwards the base's ``pick_for_event`` to it so both the production pick and
    the injected test double flow through one place.
    """

    def __init__(self, pipeline) -> None:
        self._pipeline = pipeline

    def pick_for_event(self, eventData: Any):
        # Re-read through the pipeline so a unit-layer monkeypatch of
        # ``_snap_event_to_surface`` is always honoured.
        return self._pipeline._snap_event_to_surface(eventData)


def registerTerritorySlicePipelineCreator() -> None:  # noqa: N802 - project convention
    """Register the ``TerritorySlicePipeline`` creator with LayerDM.

    Idempotent (module-level flag), mirroring
    ``registerTerritoryPlacementPipelineCreator``.  The creator matches
    ``(vtkMRMLSliceNode, vtkMRMLTerritoriesHighlightDisplayNode)`` -- the
    slice views only; the 3D placement creator accepts only
    ``vtkMRMLViewNode``, so the (view-type, display-type) keying stays
    disjoint (ADR-0013 §1).  Rendering + interaction route through this
    scripted Pipeline + its creator, never a custom displayable manager
    (ADR-0013 §5).
    """
    global _REGISTERED
    if _REGISTERED:
        return

    from slicer import (  # type: ignore[import-not-found]
        vtkMRMLLayerDMPipelineFactory,
        vtkMRMLLayerDMPipelineScriptedCreator,
        vtkMRMLTerritoriesHighlightDisplayNode,
    )

    def tryCreate(viewNode, node):
        try:
            if not _creator_accepts_view(viewNode):
                return None
            if not isinstance(node, vtkMRMLTerritoriesHighlightDisplayNode):
                return None
            return TerritorySlicePipeline()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            return None

    creator = vtkMRMLLayerDMPipelineScriptedCreator()
    creator.SetPythonCallback(tryCreate)
    vtkMRMLLayerDMPipelineFactory.GetInstance().AddPipelineCreator(creator)
    _REGISTERED = True

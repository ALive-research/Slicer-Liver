# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Slice-view LayerDM Pipeline for vessel-annotation placement + viz (ADR-0037).

The 2D-slice complement of ``TerritoryPlacementPipeline``: the SAME arm
state / active territory / carrier live on the shared highlight display
node (``TerritoryInteractionState``), so 2D and 3D placement stay in
lockstep -- an armed click in a slice view appends one surface-snapped seed
to the ACTIVE territory, exactly as an armed click in a 3D view does.

Mirrors ``LiverResectionsLib.SliceControlPolygonPipeline`` (ADR-0033): the
carrier's annotation points are projected into the slice view's XY space
(``inverse(XYToRAS)``) with DISTANCE FADING, a signed above/below SIDE
TINT, and a HARD presence cutoff (2D alpha is unreliable).  Rendering
rebuilds on a carrier ``Modified`` and on slice reslice (the slice node is
observed).

Placement (ADR-0037 §2D snap):

* a BARE MOVE is DECLINED (``(False, +inf)``, ADR-0033) -- the camera is
  untouched;
* an armed LEFT-BUTTON PRESS over the slice resolves the pixel to RAS ON
  the plane (``XYToRAS``), casts a ray ALONG THE SLICE NORMAL (both
  directions), feeds it to ``VesselSurfacePick`` -> the surface-snapped
  seed is added to the ACTIVE territory;
* a press near an existing PROJECTED seed within the pick radius grabs it
  for a drag; the drag relocates along the slice-normal snap;
* a disarmed press away from any seed leaves the gesture to the camera;
* DELETE converges on the carrier's ``RemoveNthAnnotationPoint`` (the one
  deletion path the table + the 3D pick-delete share).

Keyed on ``(vtkMRMLSliceNode, vtkMRMLTerritoriesHighlightDisplayNode)`` --
the slice-view half of the annotation placement (the 3D creator accepts
only ``vtkMRMLViewNode``).  ADR-0013 §5 keeps the (view-type, display-type)
keying disjoint per pair; rendering + interaction route through this
scripted Pipeline + its creator, never a custom displayable manager.
"""

from __future__ import annotations

import sys
from typing import Any

import vtk

from LayerDMLib import vtkMRMLLayerDMScriptedPipeline as _PipelineBase

try:  # pragma: no cover - exercised once per import path
    from .VesselSurfacePick import VesselSurfacePick
    from .VesselHighlightWiring import closed_surface_polydata
    from . import TerritoryInteractionState as _state
    from . import TerritorySliceProjection as _proj
except ImportError:  # top-level import path (the unit layer's sys.path setup)
    from VesselSurfacePick import VesselSurfacePick  # type: ignore[no-redef]
    from VesselHighlightWiring import closed_surface_polydata  # type: ignore[no-redef]
    import TerritoryInteractionState as _state  # type: ignore[no-redef]
    import TerritorySliceProjection as _proj  # type: ignore[no-redef]

_REGISTERED = False

#: Display-space pick radius (XY pixels) for grabbing an existing projected
#: seed (mirrors ``TerritoryPlacementPipeline.POINT_PICK_RADIUS_PX``).
POINT_PICK_RADIUS_PX = 20.0

#: Seed glyph diameter (XY pixels) -- a grab target larger than a default
#: markups glyph (the slice-control-polygon convention).
SEED_GLYPH_SCALE_PX = 12.0


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
    """Projected, fading, slice-editable territory annotation seeds."""

    def __init__(self) -> None:
        super().__init__()
        self.SetPythonObject(self)

        self._display_node: Any | None = None
        self._slice_node: Any | None = None
        self._renderer: Any | None = None
        self._observer_tags: dict = {}
        self._observed_node_refs: list = []
        self._observed_carrier: Any | None = None

        # Injectable pick core (bare unit layer feeds a known surface); in
        # production ``_ensure_pick`` builds it from the display node's
        # pickSurface (the ``TerritoryPlacementPipeline`` precedent).
        self._pick: VesselSurfacePick | None = None

        # Projected-seed bookkeeping (pick arbitration): parallel lists of
        # (territoryId, index) keys, their XY positions, and |distance| to
        # the slice plane -- rebuilt on every reproject.
        self._projected_keys: list = []
        self._projected_xy: list = []
        self._plane_distances: list = []

        # (territory id, in-territory index) of the projected seed currently
        # GRABBED by a press/move/release drag -- None when no drag.
        self._drag_target: tuple[str, int] | None = None

        # Seed glyphs: projected points as 2D circle glyphs with RGBA fading.
        self._seed_polydata = vtk.vtkPolyData()
        self._seed_polydata.SetPoints(vtk.vtkPoints())
        self._seed_glyph_source = vtk.vtkGlyphSource2D()
        self._seed_glyph_source.SetGlyphTypeToCircle()
        self._seed_glyph_source.FilledOn()
        self._seed_glyph_source.SetScale(SEED_GLYPH_SCALE_PX)
        self._seed_glyph = vtk.vtkGlyph2D()
        self._seed_glyph.SetInputData(self._seed_polydata)
        self._seed_glyph.SetSourceConnection(self._seed_glyph_source.GetOutputPort())
        self._seed_glyph.SetColorModeToColorByScalar()
        self._seed_glyph.ScalingOff()
        self._seed_mapper = vtk.vtkPolyDataMapper2D()
        self._seed_mapper.SetInputConnection(self._seed_glyph.GetOutputPort())
        self._seed_actor = vtk.vtkActor2D()
        self._seed_actor.SetMapper(self._seed_mapper)
        self._seed_actor.SetVisibility(False)

    # ------------------------------------------------------------------ #
    # Wiring seams (unit + production)
    # ------------------------------------------------------------------ #

    def SetPickCore(self, pick: VesselSurfacePick | None) -> None:  # noqa: N802 - VTK verb
        """Inject the ``VesselSurfacePick`` over the target surface (unit seam)."""
        self._pick = pick

    def _ensure_pick(self) -> VesselSurfacePick | None:
        """Build the pick core against the display node's ``pickSurface`` mesh.

        Production instances resolve the surface from the shared display node
        exactly as ``TerritoryPlacementPipeline`` does, so the 2D and 3D snaps
        adhere to the SAME mesh.  A test-injected ``self._pick`` short-circuits
        this for the bare unit layer.
        """
        if self._pick is not None:
            return self._pick
        display = self._display_node
        if display is None:
            return None
        segmentation = display.GetPickSurfaceNode()
        if segmentation is None:
            return None
        polydata = closed_surface_polydata(segmentation)
        if polydata is None:
            return None
        self._pick = VesselSurfacePick(polydata)
        return self._pick

    def _get_carrier(self) -> Any | None:
        """The carrier the shared display node binds (the 3D-pipeline seam)."""
        return _state.get_carrier(self._display_node)

    def _placement_territory(self) -> str | None:
        """The territory an armed click appends into (the ACTIVE one)."""
        return _state.get_active_territory(self._display_node)

    def _is_armed(self) -> bool:
        return _state.is_armed(self._display_node)

    def _safe_get_renderer(self) -> Any | None:
        return self._renderer

    # ------------------------------------------------------------------ #
    # LayerDM lifecycle
    # ------------------------------------------------------------------ #

    def SetViewNode(self, viewNode: Any) -> None:  # noqa: N802 - VTK verb
        super().SetViewNode(viewNode)
        # Observe the slice node OURSELVES: reslicing must re-project + re-fade
        # (the SliceControlPolygonPipeline stale-trace lesson).
        if self._slice_node is not None:
            self._detach_observer(self._slice_node)
        self._slice_node = viewNode
        if viewNode is not None:
            self._attach_observer(viewNode)

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
                renderer.AddActor2D(self._seed_actor)
            # Renderer churn cleared the display handle; re-derive it from the
            # base's retained display node (the reattach precedent).
            if self._display_node is None:
                display = self.GetDisplayNode()
                if display is not None:
                    self.SetDisplayNode(display)
            self._ensure_carrier_observed()
            self._reproject()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    def OnRendererRemoved(self, renderer: Any) -> None:  # noqa: N802 - VTK verb
        try:
            if renderer is not None:
                renderer.RemoveActor2D(self._seed_actor)
            self._renderer = None
            self.cleanup()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    def cleanup(self) -> None:
        for node in list(self._observed_node_refs):
            self._detach_observer(node)
        self._observed_carrier = None
        self._drag_target = None
        self._seed_actor.SetVisibility(False)

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

    # ------------------------------------------------------------------ #
    # Rendering (viz) -- fading projection into the slice XY
    # ------------------------------------------------------------------ #

    def _reproject(self) -> bool:
        """Project every visible territory's seeds into XY with distance fading.

        Reads the carrier (the source of truth), projects each seed via
        ``inverse(XYToRAS)``, fades alpha by its |distance| to the slice
        plane, applies the signed above/below side tint over the
        per-territory colour, and drops seeds beyond the HARD presence cutoff
        (2D alpha unreliable).  Populates the pick-arbitration bookkeeping.
        """
        self._projected_keys = []
        self._projected_xy = []
        self._plane_distances = []
        carrier = self._get_carrier()
        slice_node = self._slice_node
        if carrier is None or slice_node is None:
            self._seed_actor.SetVisibility(False)
            return False

        # Hoist the slice frame + the inverse XYToRAS out of the per-seed loop
        # (the SliceControlPolygonPipeline convention): resolving them once
        # keeps the reproject O(seeds), not O(seeds) matrix inversions.
        frame = _proj.slice_frame(slice_node)
        ras_to_xy = _proj.inverse_xy_to_ras(slice_node)
        if frame is None or ras_to_xy is None:
            self._seed_actor.SetVisibility(False)
            return False
        origin, normal = frame

        points = vtk.vtkPoints()
        rgba = vtk.vtkUnsignedCharArray()
        rgba.SetNumberOfComponents(4)
        rgba.SetName("SeedColors")
        try:
            for territory in carrier.GetAnnotationTerritoryIds():
                if not bool(carrier.GetTerritoryVisibility(territory)):
                    continue
                base = self._territory_rgb(carrier, territory)
                count = carrier.GetNumberOfAnnotationPoints(territory)
                for i in range(count):
                    point = carrier.GetNthAnnotationPoint(territory, i)
                    signed = _proj.signed_distance(origin, normal, point)
                    if not _proj.is_present(signed):
                        continue  # HARD presence cutoff
                    xy = _proj.apply_matrix_xy(ras_to_xy, point)
                    tint = _proj.side_tint(base, signed)
                    alpha = int(_proj.fade_alpha(signed) * 255)
                    points.InsertNextPoint(xy[0], xy[1], 0.0)
                    rgba.InsertNextTuple4(tint[0], tint[1], tint[2], alpha)
                    self._projected_keys.append((territory, i))
                    self._projected_xy.append((xy[0], xy[1]))
                    self._plane_distances.append(abs(signed))
        except Exception:  # pragma: no cover - defensive
            self._seed_actor.SetVisibility(False)
            return False

        self._seed_polydata.SetPoints(points)
        self._seed_polydata.GetPointData().SetScalars(rgba)
        self._seed_polydata.Modified()
        self._seed_actor.SetVisibility(points.GetNumberOfPoints() > 0)
        return True

    @staticmethod
    def _territory_rgb(carrier: Any, territory: str) -> list:
        """The territory's base display colour as an ``[r, g, b]`` 0..255 list."""
        try:
            rgb = carrier.GetTerritoryColor(territory)
            return [int(max(0.0, min(1.0, c)) * 255) for c in (rgb[0], rgb[1], rgb[2])]
        except Exception:  # pragma: no cover - defensive
            return [255, 255, 255]

    # ------------------------------------------------------------------ #
    # Interaction -- placement / slice-side edit (ADR-0032 / ADR-0033)
    # ------------------------------------------------------------------ #

    def CanProcessInteractionEvent(self, eventData: Any):  # noqa: N802 - VTK verb
        """Return ``(canProcess, distance2)`` for the LayerDM focus logic.

        Mirrors ``TerritoryPlacementPipeline`` on the slice: a press near a
        projected seed grabs it (real squared distance); an armed press over
        the slice claims add-on-click (pick-radius squared); a grabbed
        move/release is claimed unconditionally; a bare move is DECLINED
        (``(False, +inf)``) so the camera is untouched (ADR-0033).
        """
        try:
            if self._safe_get_renderer() is None:
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
                return False, sys.float_info.max  # bare hover: camera untouched

            if etype != vtk.vtkCommand.LeftButtonPressEvent:
                return False, sys.float_info.max

            _key, distance2 = self._nearest_seed_in_display(eventData)
            if distance2 <= POINT_PICK_RADIUS_PX * POINT_PICK_RADIUS_PX:
                return True, distance2  # grab a seed for a drag (edit gesture)

            # Add-on-click requires an armed pipeline (ADR-0037 §Decision 3):
            # a disarmed press away from any seed leaves it to the camera.
            if not self._is_armed():
                return False, sys.float_info.max
            if self._snap_event_to_surface(eventData) is None:
                return False, sys.float_info.max
            return True, POINT_PICK_RADIUS_PX * POINT_PICK_RADIUS_PX
        except Exception:  # pragma: no cover - C++ boundary must never raise
            return False, sys.float_info.max

    def ProcessInteractionEvent(self, eventData: Any) -> bool:  # noqa: N802 - VTK verb
        """Drive add-on-click / drag-to-edit from a slice view (ADR-0037 §2D)."""
        try:
            if self._safe_get_renderer() is None:
                self._drag_target = None
                return False
            etype = _event_type(eventData)

            if self._drag_target is None:
                if etype != vtk.vtkCommand.LeftButtonPressEvent:
                    return False
                key, distance2 = self._nearest_seed_in_display(eventData)
                if key is not None and distance2 <= POINT_PICK_RADIUS_PX * POINT_PICK_RADIUS_PX:
                    self._drag_target = key  # grab for a drag (edit gesture)
                    return True
                if not self._is_armed():
                    return False  # a disarmed click adds nothing
                world = self._snap_event_to_surface(eventData)
                if world is None:
                    return False
                self._add_point(world)
                return True

            if etype == vtk.vtkCommand.LeftButtonReleaseEvent:
                self._drag_target = None
                return False  # gesture over -- release the focus

            if etype == vtk.vtkCommand.MouseMoveEvent:
                world = self._snap_event_to_surface(eventData)
                if world is None:
                    return True  # keep the grab; this move just didn't resolve
                self._relocate_grabbed_point(world)
                return True

            return False
        except Exception:  # pragma: no cover - C++ boundary must never raise
            return False

    def DeleteAnnotationPoint(self, territoryId: str, index: int) -> bool:  # noqa: N802 - VTK verb
        """Remove EXACTLY ONE seed via the carrier (the shared deletion path)."""
        carrier = self._get_carrier()
        if carrier is None:
            return False
        return bool(carrier.RemoveNthAnnotationPoint(territoryId, int(index)))

    # ------------------------------------------------------------------ #
    # Snap + carrier writes
    # ------------------------------------------------------------------ #

    def _snap_event_to_surface(self, eventData: Any):
        """Snap a slice-view pixel onto the vessel surface along the normal.

        Resolves the pixel to RAS ON the slice plane (``XYToRAS``), casts a
        ray ALONG THE SLICE NORMAL through it, and feeds it to
        ``VesselSurfacePick`` -> the surface-snapped world point (``None`` on
        a miss / no surface).  Kept GL-free (the unit layer injects the pick
        result), unlike the 3D pipeline's camera-ray unprojection.
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
        # Fall back to the in-plane RAS point when the normal ray misses the
        # surface, so an armed click still lands a seed on the plane.
        return pick.pick(p1, p2, fallback_point=ras)

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

    def _nearest_seed_in_display(self, eventData: Any):
        """``((territoryId, index) | None, distance2)`` of the nearest projected seed.

        Slice-view display coordinates coincide with the XY projection space
        (the slice renderer convention), so the arbitration compares the
        event pixel against ``_projected_xy``.  A seed at / beyond the
        presence cutoff is not projected, so it is inherently unpickable.
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
    # Introspection (unit seams)
    # ------------------------------------------------------------------ #

    def GetSeedActor(self) -> Any:  # noqa: N802 - VTK verb
        return self._seed_actor

    def GetSeedPolyData(self) -> Any:  # noqa: N802 - VTK verb
        return self._seed_polydata

    def GetProjectedKeys(self) -> list:  # noqa: N802 - VTK verb
        return list(self._projected_keys)

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

        The Pipeline holds no shadow copy of the seed set: the carrier IS the
        source of truth, so a reconcile driven by an unrelated ``Modified``
        (a table repaint, a colour change) reprojects without adding / moving
        / dropping any seed (ADR-0037 §Conformance no-drift).
        """
        del caller, event
        try:
            self._reproject()
            self.RequestRender()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass


def _event_type(eventData: Any) -> int:  # noqa: N803 - VTK arg name
    """The VTK event-type id off ``eventData``."""
    return int(eventData.GetType())


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

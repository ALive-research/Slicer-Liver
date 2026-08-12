# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""LayerDM Pipeline creators for volumetry seed placement (ADR-0038 / ADR-0013 §5).

ADR-0038 §Decision makes LiverVolumetry a thin CLIENT of the shared
control-point base: the base DRIVES the generic add-on-click / drag-to-edit-
nearest / delete / bare-move-decline arbitration
(``SurfacePointPlacementPipeline3D`` / ``...Slice``), and this module supplies
ONLY the volumetry-specific wiring through the base's injected seams -- the
flat ``VolumetrySeedProvider`` (data model) + the ``InVolumePick``
(``ADR-0038 §"Base extension"`` -- the in-volume/slice pick, not a surface
snap).  There is NO territory grouping and NO vessel gating (ADR-0038 §"What
is not shared"): volumetry is the simplest of the three clients.

The interaction state (arm / carrier / pick-surface) rides the SHARED
``vtkMRMLVolumetrySeedsDisplayNode`` via the base's ``PointPlacementState``
(namespaced ``LiverVolumetry.*``), NOT the Python pipeline instance LayerDM
does not drive (``feedback_layerdm_state_on_display_node``).  So the LayerDM-
created pipelines resolve the carrier + the labelmap from the display node at
creation and re-resolve on ``UpdatePipeline`` (the display node is added to the
scene before the widget binds the carrier reference).

Two creators, keyed disjointly (ADR-0013 §1 -- one pipeline per (view, type)):

* ``(vtkMRMLViewNode, vtkMRMLVolumetrySeedsDisplayNode)`` -> the 3D pipeline;
* ``(vtkMRMLSliceNode, vtkMRMLVolumetrySeedsDisplayNode)`` -> the slice pipeline.

Rendering + interaction route through these scripted Pipelines + their
creators, NEVER a custom displayable manager (ADR-0013 §5 /
``feedback_layerdm_no_custom_dm``).

References
----------
* ADR-0038 -- §Decision (client-of-the-base seam) + §"Base extension"
  (in-volume pick) + §"Consumers ledger" (LiverVolumetry client).
* ADR-0013 §1/§5 -- one pipeline per (view, type); the 3 registration calls;
  no custom displayable manager.
* VascularTerritoriesLib/TerritoryPlacementPipeline.py -- the client-of-the-base
  wiring idiom this mirrors (minus the territory grouping + vessel gating).
"""

from __future__ import annotations

from typing import Any

import vtk

# The shared 3D + slice placement/edit bases (ADR-0038 §Decision): volumetry is
# the flat, ungated client over the PointProvider + swappable-pick seam.
try:  # pragma: no cover - exercised once per import path
    from SlicerLiverInteractionLib.SurfacePointPlacementPipeline3D import (
        SurfacePointPlacementPipeline3D as _Pipeline3DBase,
    )
    from SlicerLiverInteractionLib.SurfacePointPlacementPipelineSlice import (
        SurfacePointPlacementPipelineSlice as _PipelineSliceBase,
    )
    from SlicerLiverInteractionLib.PointPlacementState import PointPlacementState
except ImportError:  # bare / top-level path: add the sibling Lib dir to sys.path
    import pathlib
    import sys as _sys

    _shared_lib = pathlib.Path(__file__).resolve().parents[2] / "SlicerLiverInteractionLib"
    if str(_shared_lib) not in _sys.path:
        _sys.path.insert(0, str(_shared_lib))
    from SurfacePointPlacementPipeline3D import (  # type: ignore[no-redef]
        SurfacePointPlacementPipeline3D as _Pipeline3DBase,
    )
    from SurfacePointPlacementPipelineSlice import (  # type: ignore[no-redef]
        SurfacePointPlacementPipelineSlice as _PipelineSliceBase,
    )
    from PointPlacementState import PointPlacementState  # type: ignore[no-redef]

# The shared slice-projection math (RAS interior point -> slice XY): the
# placement-preview cursor rides the SAME projection the base's handles do,
# so the preview glyph sits exactly where a placed seed's handle would.
try:  # pragma: no cover - exercised once per import path
    from SlicerLiverInteractionLib import SlicePointProjection as _proj
except ImportError:  # bare / top-level path: the sibling Lib is already on sys.path
    import SlicePointProjection as _proj  # type: ignore[no-redef]

try:  # pragma: no cover - exercised once per import path
    from .VolumetrySeedProvider import VolumetrySeedProvider
    from .InVolumePick import InVolumePick
    from .SeedTargetResolution import (
        gather_touched_candidates,
        resolve_touched_candidates,
    )
    from .VisibilityCarve import (
        carved_mask_for_seed,
        visible_context,
        write_seed_context,
    )
    from .CarvedRegionStripes import (
        STRIPE_PERIOD_PX,
        get_highlight_seed,
        get_stripe_phase,
        resample_mask_to_plane,
        stripe_segments,
    )
except ImportError:  # top-level import path (the unit layer's sys.path setup)
    from VolumetrySeedProvider import VolumetrySeedProvider  # type: ignore[no-redef]
    from InVolumePick import InVolumePick  # type: ignore[no-redef]
    from SeedTargetResolution import (  # type: ignore[no-redef]
        gather_touched_candidates,
        resolve_touched_candidates,
    )
    from VisibilityCarve import (  # type: ignore[no-redef]
        carved_mask_for_seed,
        visible_context,
        write_seed_context,
    )
    from CarvedRegionStripes import (  # type: ignore[no-redef]
        STRIPE_PERIOD_PX,
        get_highlight_seed,
        get_stripe_phase,
        resample_mask_to_plane,
        stripe_segments,
    )

#: The base namespace for the volumetry arm/carrier/pick state on the shared
#: display node (matches the display node's ``LiverVolumetry.*`` attribute
#: channel; vtkMRMLVolumetrySeedsDisplayNode header §"Field roster").
VOLUMETRY_NAMESPACE = "LiverVolumetry"

#: The placement-preview cursor colour (yellow, the shared hover hue): a
#: hollow ring that tracks the cursor over a seedable interior voxel BEFORE
#: the click, the slice analogue of the territory adhering marker.
PREVIEW_CURSOR_COLOR = (1.0, 0.9, 0.2)

#: The preview cursor glyph diameter (XY pixels): a touch smaller than a
#: placed handle so the "about to place" cue reads as a cursor, not a handle.
PREVIEW_GLYPH_SCALE_PX = 11.0

#: The placed-seed sphere radius (mm) in the 3D view.  Matches the territory
#: seed-glyph radius (TerritoryPlacementPipeline) so the two seed families read
#: at the same scale; volumetry seeds are independent glyph actors, NOT tied to
#: any liver/model surface, so they are visible with no model shown.
SEED_SPHERE_RADIUS_MM = 2.2

#: Opaque-white fallback when a seed carries no per-point colour (matches the
#: carrier's own out-of-range default in ``VolumetrySeedProvider``).
_DEFAULT_SEED_RGB = (1.0, 1.0, 1.0)

_REGISTERED_3D = False
_REGISTERED_SLICE = False


def _carrier_from_display(displayNode: Any):
    """The seed carrier the shared display node binds (``LiverVolumetry.carrier``)."""
    state = PointPlacementState(VOLUMETRY_NAMESPACE)
    return state.get_carrier(displayNode)


def _labelmap_from_display(displayNode: Any):
    """The target labelmap the in-volume pick resolves against (``pickSurface``)."""
    if displayNode is None or not hasattr(displayNode, "GetPickSurfaceNode"):
        return None
    return displayNode.GetPickSurfaceNode()


def _wire_provider_and_pick(pipeline: Any, displayNode: Any) -> None:
    """(Re)resolve the flat provider + the in-volume pick from the display node.

    Shared by the 3D + slice pipelines: the display node enters the scene
    before the widget binds the carrier reference, so both re-run this on
    ``UpdatePipeline`` (fired when the reference is set) to pick up the bound
    carrier + labelmap.
    """
    provider = VolumetrySeedProvider(_carrier_from_display(displayNode))
    provider.SetDisplayNode(displayNode)
    pipeline.SetProvider(provider)
    labelmap = _labelmap_from_display(displayNode)
    pipeline.SetPickProvider(InVolumePick(labelmap) if labelmap is not None else None)


class VolumetrySeedPipeline3D(_Pipeline3DBase):
    """The 3D volumetry seed RENDERING pipeline (a thin base client).

    Created by LayerDM's manager for ``(vtkMRMLViewNode,
    vtkMRMLVolumetrySeedsDisplayNode)``.  Wires the flat volumetry provider +
    the in-volume pick from the shared display node.

    Volumetry seeds are IN-VOLUME (interior-voxel) points, so PLACING one on a
    surface in a 3D view is not a valid gesture: the 3D pipeline renders the
    placed-seed glyphs but NEVER places -- placement is the slice pipeline's
    job (the in-volume pick resolves a slice click to an interior voxel).  The
    3D view declines add-on-click by reporting ITSELF disarmed
    (``IsArmed`` -> False), which drops the base's add branch in both
    ``Can/ProcessInteractionEvent`` while leaving grab-drag editing + rendering
    intact; the shared armed flag (read by the slice pipeline) is untouched.

    RENDERING (the seed glyphs): the base's 3D pipeline iterates the provider
    only for hit-testing; it draws nothing.  So this client mirrors the
    territory client's ``_rebuild_seed_actor`` pattern -- a ``vtkPolyData`` of
    seed points glyphed by a ``vtkSphereSource`` into a ``vtkActor``, coloured
    per the provider's per-point colour -- to make each placed seed visible in
    the 3D view.  The glyph actor is an INDEPENDENT overlay (not tied to any
    liver/model surface), so the seeds show even with no model loaded.  It is
    added on ``OnRendererAdded`` and rebuilt on any carrier ``Modified``.
    """

    def __init__(self) -> None:
        super().__init__(namespace=VOLUMETRY_NAMESPACE)

        self._observer_tags: dict = {}
        self._observed_node_refs: list = []
        # The carrier currently observed for the seed-glyph rebuild; production
        # resolves it from the display node (the direct provider bind is not the
        # only path), so the observer is (re)attached through
        # ``_ensure_carrier_observed`` and deduped on this reference.
        self._observed_carrier: Any | None = None

        # -- placed-seed rendering (mirrors TerritoryPlacementPipeline): one
        # actor for the whole seed set, glyphed as spheres, coloured per seed
        # from the provider.  Rebuilt on any carrier Modified.
        self._seed_points = vtk.vtkPoints()
        self._seed_colors = vtk.vtkUnsignedCharArray()
        self._seed_colors.SetNumberOfComponents(3)
        self._seed_colors.SetName("SeedColors")
        self._seed_polydata = vtk.vtkPolyData()
        self._seed_polydata.SetPoints(self._seed_points)
        self._seed_polydata.GetPointData().SetScalars(self._seed_colors)
        self._seed_sphere = vtk.vtkSphereSource()
        self._seed_sphere.SetPhiResolution(12)
        self._seed_sphere.SetThetaResolution(12)
        self._seed_sphere.SetRadius(SEED_SPHERE_RADIUS_MM)
        self._seed_glyph = vtk.vtkGlyph3D()
        self._seed_glyph.SetInputData(self._seed_polydata)
        self._seed_glyph.SetSourceConnection(self._seed_sphere.GetOutputPort())
        self._seed_glyph.SetScaleModeToDataScalingOff()
        self._seed_glyph.SetColorModeToColorByScalar()
        self._seed_mapper = vtk.vtkPolyDataMapper()
        self._seed_mapper.SetInputConnection(self._seed_glyph.GetOutputPort())
        # Interpret the per-glyph uchar[3] scalars as RGB directly.  Without
        # ScalarVisibilityOn + UsePointData the mapper falls back to the LUT
        # (which maps the 3-component array to near-black), so the spheres
        # render invisible against the dark 3D background (the territory
        # seed-glyph lesson, feedback_layerdm_state_on_display_node).
        self._seed_mapper.SetScalarModeToUsePointData()
        self._seed_mapper.ScalarVisibilityOn()
        self._seed_mapper.SetColorModeToDirectScalars()
        self._seed_actor = vtk.vtkActor()
        self._seed_actor.SetMapper(self._seed_mapper)

    def IsArmed(self) -> bool:  # noqa: N802 - VTK verb
        """A 3D view never arms for placement (in-volume seeds are slice-placed).

        Overrides the shared-display-node arm gate for THIS view only: placing
        a seed on a surface in 3D is invalid (the seed must land on an interior
        labelled voxel), so the 3D pipeline's add-on-click branch is dead by
        construction.  The slice pipeline reads the real armed flag off the
        shared display node and still places.  Grab-drag of an existing seed is
        gated BEFORE the arm check in the base, so 3D editing is unaffected.
        """
        return False

    def SetDisplayNode(self, displayNode: Any) -> None:  # noqa: N802 - VTK verb
        super().SetDisplayNode(displayNode)
        self._display_node = displayNode
        self._rewire()
        self._ensure_carrier_observed()

    def OnRendererAdded(self, renderer: Any) -> None:  # noqa: N802 - VTK verb
        try:
            self._renderer = renderer
            if renderer is not None:
                renderer.AddActor(self._seed_actor)
            if self._display_node is None:
                display = self.GetDisplayNode()
                if display is not None:
                    self.SetDisplayNode(display)
            self._rewire()
            self._ensure_carrier_observed()
            self._rebuild_seed_actor()
            self.RequestRender()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    def OnRendererRemoved(self, renderer: Any) -> None:  # noqa: N802 - VTK verb
        try:
            if renderer is not None:
                renderer.RemoveActor(self._seed_actor)
            self._renderer = None
            for node in list(self._observed_node_refs):
                self._detach_observer(node)
            self._observed_carrier = None
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    def UpdatePipeline(self) -> None:  # noqa: N802 - VTK verb
        try:
            self._rewire()
            # LayerDM fires this when the carrier reference is finally set on the
            # display node (added to the scene before the widget binds it), so
            # this is where the seed-glyph observer attaches -- without it a seed
            # placed from a SLICE view never repaints the 3D glyphs.
            self._ensure_carrier_observed()
            self._rebuild_seed_actor()
            self.RequestRender()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    def _rewire(self) -> None:
        """(Re)resolve the provider + pick from the shared display node."""
        _wire_provider_and_pick(self, self._display_node)

    # ------------------------------------------------------------------ #
    # Seed-glyph rendering (mirrors TerritoryPlacementPipeline, minus the
    # territory grouping + vessel-visibility gate -- volumetry is flat)
    # ------------------------------------------------------------------ #

    def _rebuild_seed_actor(self) -> None:
        """Rebuild the seed-glyph point set from the provider, coloured per seed.

        The carrier (via the provider) is the source of truth: read every
        seed's world + per-point colour through ``iter_points`` and glyph each
        as a sphere.  A no-op-safe rebuild -- an empty carrier clears the
        glyphs.  Holds no shadow copy of the point set (ADR-0038 no-drift): a
        rebuild driven by an unrelated ``Modified`` re-reads the provider and
        adds / moves / drops nothing.
        """
        self._seed_points.Reset()
        self._seed_colors.Reset()
        self._seed_colors.SetNumberOfComponents(3)
        provider = self._provider
        if provider is not None:
            for world, base_rgb in provider.iter_points():
                self._seed_points.InsertNextPoint(world[0], world[1], world[2])
                rgb = base_rgb if base_rgb is not None else _DEFAULT_SEED_RGB
                self._seed_colors.InsertNextTuple3(
                    int(max(0.0, min(1.0, rgb[0])) * 255),
                    int(max(0.0, min(1.0, rgb[1])) * 255),
                    int(max(0.0, min(1.0, rgb[2])) * 255),
                )
        self._seed_points.Modified()
        self._seed_colors.Modified()
        self._seed_polydata.Modified()

    def GetSeedActor(self) -> Any:  # noqa: N802 - VTK verb
        """The seed-glyph actor (the placed-seed spheres); introspection seam."""
        return self._seed_actor

    def GetSeedPolyData(self) -> Any:  # noqa: N802 - VTK verb
        """The seed-glyph point set (one point per rendered seed)."""
        return self._seed_polydata

    # ------------------------------------------------------------------ #
    # Carrier observation (the seed-glyph rebuild trigger)
    # ------------------------------------------------------------------ #

    def _ensure_carrier_observed(self) -> None:
        """Observe the in-effect carrier so the seed glyphs track its edits.

        The provider resolves the carrier from the display node, so the glyph
        rebuild needs its own ModifiedEvent observer; (re)attaches when the
        resolved carrier changes, idempotent otherwise.
        """
        carrier = _carrier_from_display(self._display_node)
        if carrier is self._observed_carrier:
            return
        if self._observed_carrier is not None:
            self._detach_observer(self._observed_carrier)
        self._observed_carrier = carrier
        if carrier is not None:
            self._attach_observer(carrier)

    def _attach_observer(self, node: Any) -> None:
        if node is None or not hasattr(node, "AddObserver"):
            return
        tag = node.AddObserver("ModifiedEvent", self._on_seed_carrier_modified)
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

    def _on_seed_carrier_modified(self, caller: Any, event: str) -> None:
        """Rebuild + repaint the seed glyphs on a carrier ``Modified``.

        Repaint immediately: a carrier ``Modified`` fired synchronously inside
        a slice-view placement does not flush a 3D frame on its own (the
        RequestRender mid-interaction discipline), so the glyph must be rebuilt
        and a render requested here for the just-placed seed to show in 3D.
        """
        del caller, event
        try:
            self._rebuild_seed_actor()
            self.RequestRender()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass


class VolumetrySeedPipelineSlice(_PipelineSliceBase):
    """The slice volumetry seed placement pipeline (a thin base client).

    Created by LayerDM's manager for ``(vtkMRMLSliceNode,
    vtkMRMLVolumetrySeedsDisplayNode)``.  The slice analogue of the 3D pipeline:
    an armed slice click routes through the in-volume pick's slice-click seam so
    the seed lands on an interior labelled voxel of the target region.
    """

    def __init__(self) -> None:
        super().__init__(namespace=VOLUMETRY_NAMESPACE)

        # Carrier currently observed for the reproject-on-edit trigger.  The
        # shared slice base observes only the SLICE node + the display node
        # (reslice re-projection), NOT the carrier -- so a seed placed in the
        # slice fires the carrier's Modified with nobody listening, and the
        # handle does not project onto the clicked plane until a reslice.  This
        # client observes the carrier itself (the TerritorySlicePipeline
        # precedent) so a just-placed seed reprojects immediately.
        self._observed_carrier: Any | None = None

        # Placement-preview cursor: a hollow ring that tracks the cursor over a
        # seedable interior voxel BEFORE the click, so the surgeon sees where a
        # seed would land (the slice analogue of the territory adhering marker;
        # the base's hover ring only highlights EXISTING handles, so an empty
        # slice showed no placement cue at all -- the reported "no cursor").
        self._preview_polydata = vtk.vtkPolyData()
        self._preview_polydata.SetPoints(vtk.vtkPoints())
        self._preview_glyph_source = vtk.vtkGlyphSource2D()
        self._preview_glyph_source.SetGlyphTypeToCircle()
        self._preview_glyph_source.FilledOff()
        self._preview_glyph_source.SetScale(PREVIEW_GLYPH_SCALE_PX)
        self._preview_glyph = vtk.vtkGlyph2D()
        self._preview_glyph.SetInputData(self._preview_polydata)
        self._preview_glyph.SetSourceConnection(
            self._preview_glyph_source.GetOutputPort()
        )
        self._preview_glyph.ScalingOff()
        self._preview_mapper = vtk.vtkPolyDataMapper2D()
        self._preview_mapper.SetInputConnection(self._preview_glyph.GetOutputPort())
        self._preview_actor = vtk.vtkActor2D()
        self._preview_actor.SetMapper(self._preview_mapper)
        self._preview_actor.GetProperty().SetColor(*PREVIEW_CURSOR_COLOR)
        self._preview_actor.GetProperty().SetLineWidth(2.0)
        self._preview_actor.SetVisibility(False)

        # Carved-region marching-stripes highlight (CarvedRegionStripes): while
        # a seed's row is SELECTED the widget publishes highlightSeed +
        # stripePhase onto the shared display node; this pipeline cuts the
        # seed's EFFECTIVE (carved) region to the slice plane once and redraws
        # only the stripe family each phase tick.  Diagonal LINES through a
        # 2D mapper -- the reliable slice-overlay primitive (2D RGBA fills are
        # not; the slice-polygon presence-cutoff lesson).
        self._stripes_polydata = vtk.vtkPolyData()
        self._stripes_polydata.SetPoints(vtk.vtkPoints())
        self._stripes_mapper = vtk.vtkPolyDataMapper2D()
        self._stripes_mapper.SetInputData(self._stripes_polydata)
        self._stripes_actor = vtk.vtkActor2D()
        self._stripes_actor.SetMapper(self._stripes_mapper)
        self._stripes_actor.GetProperty().SetLineWidth(3.0)
        self._stripes_actor.SetVisibility(False)
        # (key, mask) caches: the 3D carve keyed on the seed + node MTimes, the
        # 2D cut keyed on the carve key + the slice pose + view size.  The
        # phase tick hits both caches and only rebuilds the stripe lines.
        self._carve3d_cache: tuple | None = None
        self._mask2d_cache: tuple | None = None

    def _after_display_node_set(self) -> None:
        _wire_provider_and_pick(self, self._display_node)
        self._ensure_carrier_observed()

    def OnRendererAdded(self, renderer: Any) -> None:  # noqa: N802 - VTK verb
        # The base re-attaches the slice-node observer after renderer churn but
        # not the carrier (it does not know this client observes one), so
        # re-observe here too or a post-churn placement stops reprojecting.
        super().OnRendererAdded(renderer)
        try:
            self._ensure_carrier_observed()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    def UpdatePipeline(self) -> None:  # noqa: N802 - VTK verb
        # LayerDM fires this when the carrier reference is finally set on the
        # display node (added to the scene before the widget binds it), so the
        # reproject observer attaches here as well as in ``_after_display_node_set``.
        try:
            self._ensure_carrier_observed()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass
        super().UpdatePipeline()
        # The stripe highlight rides the same display-node ModifiedEvent tick:
        # the widget's phase timer writes stripePhase, which lands here.
        try:
            self._update_stripes()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            self._stripes_actor.SetVisibility(False)

    def cleanup(self) -> None:
        # The base detaches every observed node here (renderer churn); drop the
        # carrier dedupe key too so ``_ensure_carrier_observed`` re-attaches on
        # the next renderer add rather than believing it is still observed.
        super().cleanup()
        self._observed_carrier = None

    def _ensure_carrier_observed(self) -> None:
        """Observe the in-effect carrier so a placed seed reprojects at once.

        The provider resolves the carrier from the display node, so the
        reproject needs its own ModifiedEvent observer; (re)attaches when the
        resolved carrier changes, idempotent otherwise.  The base's shared
        ``_on_node_modified`` handles the ModifiedEvent -- it reprojects (via
        ``UpdatePipeline`` -> ``_reconcile`` -> ``_reproject``), sets the
        handles-actor visibility, and requests a render -- so a seed placed in
        the clicked plane shows WITHOUT a reslice.
        """
        carrier = _carrier_from_display(self._display_node)
        if carrier is self._observed_carrier:
            return
        if self._observed_carrier is not None:
            self._detach_observer(self._observed_carrier)
        self._observed_carrier = carrier
        if carrier is not None:
            self._attach_observer(carrier)

    def _add_actors(self, renderer: Any) -> None:
        super()._add_actors(renderer)
        renderer.AddActor2D(self._stripes_actor)
        renderer.AddActor2D(self._preview_actor)

    def _remove_actors(self, renderer: Any) -> None:
        super()._remove_actors(renderer)
        renderer.RemoveActor2D(self._stripes_actor)
        renderer.RemoveActor2D(self._preview_actor)

    def _on_bare_move_decline(self, eventData: Any) -> None:
        """Raise the placement-preview cursor on a declined bare move (ADR-0033).

        The base DECLINES a bare move (camera untouched) and returns WITHOUT a
        render, and a bare hover mutates no observed node -- so a placement cue
        is computed but never flushed unless this hook requests a render itself
        (the same mid-interaction ``RequestRender`` the territory
        ``_on_bare_move_decline`` follows).  Without it the surgeon gets no
        cursor/marker while placing seeds -- the reported regression.

        The preview only shows while ARMED (the add-on-click mode): a disarmed
        slice hover is edit-only, and the base's hover ring already cues the
        grab target, so a placement preview would be misleading there.
        """
        try:
            self._update_preview_cursor(eventData)
        finally:
            self.RequestRender()

    def _update_preview_cursor(self, eventData: Any) -> None:
        """Position the preview ring at the cursor's seedable interior voxel.

        Resolves the cursor through the SAME in-volume slice pick a click uses,
        then projects that interior RAS to the slice XY so the ring sits where
        the placed seed's handle would.  Hidden when disarmed, off any region,
        or beyond the local search radius (the pick declines) -- so the cursor
        cue truthfully tracks where a click WOULD place a seed.
        """
        show = False
        points = vtk.vtkPoints()
        if self.IsArmed() and self.IsModuleActive():
            world = self._pick_world(eventData)
            slice_node = self._slice_node
            if world is not None and slice_node is not None:
                xy = _proj.project_ras_to_xy(slice_node, world)
                if xy is not None:
                    points.InsertNextPoint(xy[0], xy[1], 0.0)
                    show = True
        self._preview_polydata.SetPoints(points)
        self._preview_polydata.Modified()
        self._preview_actor.SetVisibility(show)

    def _pick_world(self, eventData: Any):
        """Route the armed slice click through the in-volume slice-click pick.

        The base's default calls ``pick_for_event(eventData)``, but the
        in-volume pick resolves a slice click against the labelmap
        (``pick_for_slice_event(slice_node, display_xy)``), so this override
        supplies the slice node + the event pixel -- keeping the interior-voxel
        seed the only placement (ADR-0038 §"Base extension").
        """
        pick = self._pick_provider
        if pick is None:
            return None
        try:
            display_xy = eventData.GetDisplayPosition()
        except Exception:  # pragma: no cover - defensive (fake events)
            display_xy = None
        return pick.pick_for_slice_event(self._slice_node, display_xy)

    def _add_point(self, world: Any) -> None:
        """Add the seed, route it to the active volume, then capture its binding.

        Overrides the base's add write-back: after the flat provider appends
        the seed at ``world`` (the interior RAS the in-volume pick resolved),
        (1) assign it to the ACTIVE VOLUME read off the shared display node
        (``territory-usability`` grouped-volumes -- the active-territory routing
        analogue), and (2) resolve the touched-candidate set at that RAS against
        the structure-source segmentation and bind the new seed to the TOP
        layer's segment (``territory-usability`` §"Seed→label capture").  A seed
        placed with no active volume stays ungrouped; one placed off every
        visible segment stays unbound -- the placement still succeeds either
        way.
        """
        super()._add_point(world)
        carrier = self._provider.carrier() if self._provider is not None else None
        if carrier is not None:
            self._assign_active_volume(carrier.GetNumberOfSeeds() - 1)
        self._capture_binding(world)

    def _assign_active_volume(self, index: int) -> None:
        """Assign the ``index``-th seed to the ACTIVE volume on the display node.

        The active-volume id rides the shared display node via the base's
        ``PointPlacementState`` active slot (the same channel the territory
        client uses for its active territory), so the widget publishes it and
        the LayerDM-created pipeline reads it at placement time.  A no-op for an
        out-of-range index, a missing carrier, or no active volume set (the seed
        stays ungrouped).
        """
        if index < 0:
            return
        carrier = self._provider.carrier() if self._provider is not None else None
        if carrier is None:
            return
        volumeId = PointPlacementState(VOLUMETRY_NAMESPACE).get_active(self._display_node)
        if volumeId:
            carrier.SetNthSeedVolume(index, volumeId)

    def _capture_binding(self, world: Any) -> None:
        """Bind the LAST-placed seed to the top touched segment at ``world`` RAS.

        Reads the touched candidates from the structure-source segmentation
        (one voxel per visible segment) and stores ``(segmentationNodeID,
        topSegmentID)`` on the carrier's last seed, plus the segment's name as
        the seed LABEL so the a11y text names the caught structure (never
        colour/animation alone, ADR-0010).  Best-effort: any resolution miss
        leaves the seed unbound.

        Alongside the binding, the seed's VISIBILITY CONTEXT is snapshotted:
        the ordered (top-first) segment IDs visible at placement (the
        visibility-composed carve rule, ``VisibilityCarve``).  The snapshot IS
        the seed's reproducible definition -- restore-on-select, the carved
        highlight, and compute all re-derive the effective region from it.
        """
        carrier = self._provider.carrier() if self._provider is not None else None
        if carrier is None:
            return
        index = carrier.GetNumberOfSeeds() - 1
        if index < 0:
            return
        segmentationNode = self._structure_source_from_display()
        if segmentationNode is None:
            return
        displayNode = segmentationNode.GetDisplayNode()
        self._snapshot_visibility_context(carrier, index, segmentationNode, displayNode)
        touched = gather_touched_candidates(segmentationNode, displayNode, world)
        _ordered, top = resolve_touched_candidates(touched)
        if top is None:
            return
        carrier.SetNthSeedBinding(index, segmentationNode.GetID(), top)
        segment = segmentationNode.GetSegmentation().GetSegment(top)
        if segment is not None and not carrier.GetNthSeedLabel(index):
            carrier.SetNthSeedLabel(index, segment.GetName())

    @staticmethod
    def _snapshot_visibility_context(carrier: Any, index: int, segmentationNode: Any, displayNode: Any) -> None:
        """Record the placement-time visibility snapshot on the seed.

        Best-effort: a carrier without the context slot (an older build) or a
        gather failure leaves the seed snapshotless (legacy no-carve
        semantics) -- the placement still succeeds.
        """
        try:
            write_seed_context(carrier, index, visible_context(segmentationNode, displayNode))
        except Exception:  # pragma: no cover - snapshot must never break placement
            pass

    def _structure_source_from_display(self):
        """The structure-source segmentation the seed→label capture scans."""
        display = self._display_node
        if display is None or not hasattr(display, "GetStructureSourceNode"):
            return None
        return display.GetStructureSourceNode()

    # ------------------------------------------------------------------ #
    # Carved-region marching-stripes highlight (CarvedRegionStripes)
    # ------------------------------------------------------------------ #

    def _update_stripes(self) -> None:
        """Redraw the highlighted seed's carved region as marching stripes.

        Reads the highlight index + stripe phase off the shared display node
        (the widget's timer channel).  The carved 3D mask and its slice-plane
        cut are cached; a phase tick only rebuilds the stripe line family --
        the cheap per-tick path.
        """
        show = False
        index = get_highlight_seed(self._display_node)
        if index >= 0:
            mask2d = self._carved_mask_2d(index)
            if mask2d is not None:
                phase = get_stripe_phase(self._display_node)
                segments = stripe_segments(mask2d, STRIPE_PERIOD_PX, phase)
                if segments:
                    self._build_stripe_lines(segments)
                    self._stripes_actor.GetProperty().SetColor(*self._stripe_rgb(index))
                    show = True
        self._stripes_actor.SetVisibility(show)

    def _carved_mask_3d(self, index: int):
        """The seed's EFFECTIVE region as a boolean mask on the pick labelmap grid.

        Owner segment minus the snapshot segments above it (``VisibilityCarve``),
        every mask resampled onto the pick-surface labelmap geometry so the
        carve is same-grid boolean algebra.  Cached on the seed + the carrier /
        source / reference MTimes; ``None`` when the seed is unbound or the
        nodes are not wired.
        """
        carrier = _carrier_from_display(self._display_node)
        source = self._structure_source_from_display()
        reference = _labelmap_from_display(self._display_node)
        if carrier is None or source is None or reference is None:
            return None
        owner = carrier.GetNthSeedBindingSegmentID(index)
        if not owner:
            return None
        key = (index, carrier.GetMTime(), source.GetMTime(), reference.GetMTime())
        if self._carve3d_cache is not None and self._carve3d_cache[0] == key:
            return self._carve3d_cache[1]

        import slicer

        def _segment_mask(segmentID):
            try:
                arr = slicer.util.arrayFromSegmentBinaryLabelmap(source, segmentID, reference)
            except Exception:  # noqa: BLE001 - a segment without a labelmap carves nothing
                return None
            return arr

        carved = carved_mask_for_seed(carrier, index, _segment_mask)
        if carved is None:
            return None
        self._carve3d_cache = (key, carved)
        return carved

    def _carved_mask_2d(self, index: int):
        """The carved mask cut to THIS view's slice plane (cached per pose)."""
        mask3d = self._carved_mask_3d(index)
        slice_node = self._slice_node
        reference = _labelmap_from_display(self._display_node)
        if mask3d is None or slice_node is None or reference is None:
            return None
        ras_to_ijk = vtk.vtkMatrix4x4()
        reference.GetRASToIJKMatrix(ras_to_ijk)
        xy_to_ijk = vtk.vtkMatrix4x4()
        vtk.vtkMatrix4x4.Multiply4x4(ras_to_ijk, slice_node.GetXYToRAS(), xy_to_ijk)
        dims = slice_node.GetDimensions()
        affine = tuple(
            xy_to_ijk.GetElement(r, c) for r in range(4) for c in range(4)
        )
        key = (self._carve3d_cache[0] if self._carve3d_cache else None, affine, dims[0], dims[1])
        if self._mask2d_cache is not None and self._mask2d_cache[0] == key:
            return self._mask2d_cache[1]

        import numpy as np

        matrix = np.array(affine, dtype=float).reshape(4, 4)
        mask2d = resample_mask_to_plane(mask3d, matrix, int(dims[0]), int(dims[1]))
        self._mask2d_cache = (key, mask2d)
        return mask2d

    def _build_stripe_lines(self, segments: list) -> None:
        """Rebuild the stripe polydata from the clipped segment endpoints."""
        points = vtk.vtkPoints()
        lines = vtk.vtkCellArray()
        for (x0, y0), (x1, y1) in segments:
            if x0 == x1 and y0 == y1:
                # A single-pixel run: pad along the stripe so it still draws.
                x1, y1 = x0 + 0.5, y0 - 0.5
            a = points.InsertNextPoint(x0, y0, 0.0)
            b = points.InsertNextPoint(x1, y1, 0.0)
            lines.InsertNextCell(2)
            lines.InsertCellPoint(a)
            lines.InsertCellPoint(b)
        self._stripes_polydata.SetPoints(points)
        self._stripes_polydata.SetLines(lines)
        self._stripes_polydata.Modified()

    def _stripe_rgb(self, index: int):
        """The highlight hue: the seed's VOLUME colour, else its own colour."""
        carrier = _carrier_from_display(self._display_node)
        if carrier is None:
            return _DEFAULT_SEED_RGB
        volumeId = (
            carrier.GetNthSeedVolume(index)
            if hasattr(carrier, "GetNthSeedVolume")
            else ""
        )
        if volumeId and hasattr(carrier, "GetVolumeColor"):
            rgb = carrier.GetVolumeColor(volumeId)
            return (rgb[0], rgb[1], rgb[2])
        rgb = carrier.GetNthSeedColor(index)
        return (rgb[0], rgb[1], rgb[2])

    def GetStripesActor(self) -> Any:  # noqa: N802 - VTK verb
        """The carved-region stripes actor (introspection seam)."""
        return self._stripes_actor


def registerVolumetrySeedPipeline3DCreator() -> None:  # noqa: N802 - project convention
    """Register the 3D volumetry seed placement creator with LayerDM (ADR-0013 §5).

    Idempotent (module-level flag).  Matches ``(vtkMRMLViewNode,
    vtkMRMLVolumetrySeedsDisplayNode)`` -- the 3D views only; the slice creator
    accepts only ``vtkMRMLSliceNode``, so the (view-type, display-type) keying
    stays disjoint (ADR-0013 §1).  No custom displayable manager (ADR-0013 §5).
    """
    global _REGISTERED_3D
    if _REGISTERED_3D:
        return

    from slicer import (  # type: ignore[import-not-found]
        vtkMRMLLayerDMPipelineFactory,
        vtkMRMLLayerDMPipelineScriptedCreator,
        vtkMRMLVolumetrySeedsDisplayNode,
        vtkMRMLViewNode,
    )

    def tryCreate(viewNode, node):
        try:
            if not isinstance(viewNode, vtkMRMLViewNode):
                return None
            if not isinstance(node, vtkMRMLVolumetrySeedsDisplayNode):
                return None
            return VolumetrySeedPipeline3D()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            return None

    creator = vtkMRMLLayerDMPipelineScriptedCreator()
    creator.SetPythonCallback(tryCreate)
    vtkMRMLLayerDMPipelineFactory.GetInstance().AddPipelineCreator(creator)
    _REGISTERED_3D = True


def registerVolumetrySeedPipelineSliceCreator() -> None:  # noqa: N802 - project convention
    """Register the slice volumetry seed placement creator with LayerDM (ADR-0013 §5).

    Idempotent (module-level flag).  Matches ``(vtkMRMLSliceNode,
    vtkMRMLVolumetrySeedsDisplayNode)`` -- the slice views only; the 3D creator
    accepts only ``vtkMRMLViewNode`` (ADR-0013 §1).  No custom displayable
    manager (ADR-0013 §5).
    """
    global _REGISTERED_SLICE
    if _REGISTERED_SLICE:
        return

    from slicer import (  # type: ignore[import-not-found]
        vtkMRMLLayerDMPipelineFactory,
        vtkMRMLLayerDMPipelineScriptedCreator,
        vtkMRMLVolumetrySeedsDisplayNode,
    )

    def tryCreate(viewNode, node):
        try:
            if viewNode is None or not viewNode.IsA("vtkMRMLSliceNode"):
                return None
            if not isinstance(node, vtkMRMLVolumetrySeedsDisplayNode):
                return None
            return VolumetrySeedPipelineSlice()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            return None

    creator = vtkMRMLLayerDMPipelineScriptedCreator()
    creator.SetPythonCallback(tryCreate)
    vtkMRMLLayerDMPipelineFactory.GetInstance().AddPipelineCreator(creator)
    _REGISTERED_SLICE = True

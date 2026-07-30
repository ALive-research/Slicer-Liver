# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""LayerDM Pipeline for vessel-annotation placement + edit (ADR-0037/0038).

ADR-0037 §Decision 2 routes vessel-annotation placement and edit through
the LayerDM scripted Pipeline's interaction seam (ADR-0032 / ADR-0033),
reusing the already-built ``VesselSurfacePick`` (ray-onto-surface) and the
adhering highlight.  There is NO markup place mode and NO annotation state
machine (ADR-0037 §Decision 2 + §Alternatives) --
add-on-click / drag-to-edit / delete-from-table is the whole lifecycle:

* a CLICK claims the gesture and adds EXACTLY ONE surface-snapped point to
  the carrier's active territory (on the mesh, distance ~= 0);
* a DRAG (press-near-a-point + move) edits the NEAREST existing point;
* a BARE MOVE is DECLINED (``CanProcessInteractionEvent`` returns
  ``(False, +inf)``) so the camera is untouched (ADR-0033) -- beyond
  raising the adhering highlight as a side effect;
* DELETE removes EXACTLY ONE point;
* an unrelated ``Modified`` causes no drift.

ADR-0038 §Decision makes this a thin CLIENT of the shared
``SurfacePointPlacementPipeline3D`` base: the base DRIVES the generic
add-on-click / drag-to-edit-nearest / delete / bare-move-decline
arbitration (``Can/ProcessInteractionEvent``), and this client contributes
ONLY the territory-SPECIFIC concerns through the base's extension hooks
(ADR-0038 §"What is not shared"):

* per-territory grouping + active-territory routing (the ``add_point`` fan
  into the active territory, on ``TerritoryPointProvider`` + this pipeline);
* vessel-visibility gating -- a hidden vessel surface is not pickable and a
  hidden seed is neither grabbable nor drawn -- via ``_ensure_pick`` over
  the visibility-filtered ``vascular_surface_polydata`` and the
  ``VisibleStructuresCache``-backed ``seed_visible`` filter in the hit-test
  and the seed-glyph rebuild;
* the vessel hover-adhering marker, the glow halo, the slice-jump, and the
  per-segment seed show/hide -- none of which bleed into the base.

The point storage lives on ``vtkMRMLCustomTerritoriesNode`` (the carrier
pinned by ``test_territories_annotation_carrier.py``); this Pipeline WRITES
to it via the provider seam.
"""

from __future__ import annotations

import sys
from typing import Any

import vtk

# The shared 3D placement/edit base (ADR-0038 §Decision): territories is the
# flat, vessel-gated client of ``SurfacePointPlacementPipeline3D`` over the
# PointProvider + swappable-pick seam.  The base drives the generic
# add/grab/drag/release arbitration; this pipeline keeps the per-territory
# grouping, the vessel-visibility gating, and the hover/marker/halo cues as
# overrides (ADR-0038 §"What is not shared").
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

try:  # pragma: no cover - exercised once per import path
    from .VesselSurfacePick import VesselSurfacePick
    from .VesselHighlightWiring import (
        vascular_surface_polydata,
        visibility_mtime as _visibility_mtime,
        VisibleStructuresCache as _VisibleStructuresCache,
    )
    from .TerritoryPointProvider import TerritoryPointProvider
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

#: Display-space pick radius for grabbing an existing point, in pixels
#: (mirrors the base's ``POINT_PICK_RADIUS_PX``).  A press within this radius
#: of a placed point grabs it for a drag; a press outside it (but over the
#: surface) adds a new point.
POINT_PICK_RADIUS_PX = 20.0

#: Hover/grab cue colours + halo scale, shared with the resection surface
#: control points (ControlPolygonPipeline): hover = yellow, grab = green, and
#: the glow halo is a slightly larger sphere (blurred by vtkOutlineGlowPass).
HALO_HOVER_COLOR = (1.0, 0.9, 0.2)
HALO_GRAB_COLOR = (0.3, 1.0, 0.4)
HALO_HOVER_SCALE = 1.6

#: Interaction state lives on the shared highlight DISPLAY NODE, not on the
#: Pipeline instance: LayerDM owns the Pipeline instance lifecycle (it creates
#: its own per view), so the widget/table can only reach the Pipeline the
#: manager drives THROUGH the display node both sides hold.  This is still
#: "pipeline-managed" (ADR-0037 §Decision 2) — the state is read by the
#: Pipeline, not by a Slicer interaction node / mouse mode.  The accessors
#: live in the dependency-free ``TerritoryInteractionState`` module so the
#: table can share them without the LayerDMLib import.
try:  # pragma: no cover - exercised once per import path
    from . import TerritoryInteractionState as _state
except ImportError:  # top-level import path (the unit layer's sys.path setup)
    import TerritoryInteractionState as _state  # type: ignore[no-redef]

_REGISTERED = False


class TerritoryPlacementPipeline(_PipelineBase):
    """Places + edits the annotation points of a custom-territories carrier.

    Created by LayerDM's manager via the creator registered by
    ``registerTerritoryPlacementPipelineCreator()``; keyed on
    ``vtkMRMLTerritoriesHighlightDisplayNode`` (the annotation-interaction
    display node), reusing the adhering highlight's pick core.

    A thin client of ``SurfacePointPlacementPipeline3D``: the base drives the
    arbitration, this class supplies the territory data model + vessel gating.
    """

    def __init__(self) -> None:
        # The base seeds ``_display_node`` / ``_renderer`` / ``_drag_key`` /
        # ``_provider`` / ``_pick_provider`` and calls ``SetPythonObject``.
        super().__init__(namespace="TerritoryPlacement")

        self._observer_tags: dict = {}
        self._observed_node_refs: list = []

        # The carrier + the active territory the placement writes into.
        self._carrier: Any | None = None
        self._territory_id: str | None = None

        # Wire the ADR-0038 seams:
        #  * the data model -- the base reads/writes the carrier points via
        #    this provider (flat, no edges -- territory seeds are unordered);
        #  * the click->world pick -- delegated to ``_event_world_on_surface``
        #    so the base's add-on-click routes through the vessel-visibility-
        #    gated surface snap (and the unit layer's monkeypatch), NOT a
        #    surface-vs-volume branch in the base (ADR-0038 §"Base extension").
        self.SetProvider(
            TerritoryPointProvider(
                carrier_getter=self._get_carrier,
                territory_getter=self._placement_territory,
                # Re-read through the pipeline so a unit-layer monkeypatch of
                # ``_seed_visible`` is honoured and the vessel-visibility gate
                # stays a single source of truth (the hit-test + seed rebuild
                # consult the same method).
                visible_getter=lambda point: self._seed_visible(point),
            )
        )
        self.SetPickProvider(_TerritorySurfacePick(self))

        # Stage-2 arming (ADR-0037 §Decision 3).  An armed click appends one
        # seed to the ACTIVE territory; a disarmed click adds nothing.  In
        # production the arm state + active territory + carrier all live on the
        # shared highlight DISPLAY NODE (read by ``GetActiveTerritory`` /
        # ``IsArmed`` / ``_get_carrier``) so the widget/table reach the
        # manager-driven Pipeline; the base's instance fields are the
        # BARE-unit fallback (no display node).  It is still pipeline-managed,
        # not a Slicer interaction node / mouse mode.
        self._active_territory: str | None = None

        # Injectable pick core (bare unit layer feeds a known surface); in
        # production ``_ensure_pick`` builds it from the display node's
        # pickSurface.  ``_pick_injected`` distinguishes a test-injected core
        # (never rebuilt) from a production-built one (rebuilt when segment
        # visibility changes, tracked by ``_pick_surface_mtime``).
        self._pick: VesselSurfacePick | None = None
        self._pick_injected: bool = False
        self._pick_surface_mtime: int | None = None

        # Per-segment vessel structures (segId, surface, visible) for the
        # seed-glyph show/hide follow (ADR-0037 slice 5), cached by the display
        # node's visibility MTime so a show/hide repaints the seeds without
        # re-running the closed-surface split per event (kept cheap, mirroring
        # ``_ensure_pick``).
        self._structures = _VisibleStructuresCache()

        # Carrier currently observed for the seed-glyph rebuild (production
        # resolves it from the display node, so the bare ``SetCarrier`` bind is
        # not the only path); tracked to avoid double-observing.
        self._observed_carrier: Any | None = None

        # The pickSurface segmentation's DISPLAY node, observed so a
        # segment-visibility toggle in the structures table repaints the seed
        # glyphs (the seed filter is visibility-aware, but a visibility change
        # modifies the SEGMENTATION display node -- not the carrier -- so the
        # glyph rebuild needs its own trigger; ADR-0037 slice 5).
        self._observed_pick_display: Any | None = None

        # -- placed-seed rendering (ADR-0037 §Decision 2): the persistent
        # markers for the carrier's annotation points, glyphed as spheres and
        # coloured per territory from the carrier's display slot.  One actor
        # for the whole point set; rebuilt on any carrier Modified.
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
        self._seed_sphere.SetRadius(2.2)
        self._seed_glyph = vtk.vtkGlyph3D()
        self._seed_glyph.SetInputData(self._seed_polydata)
        self._seed_glyph.SetSourceConnection(self._seed_sphere.GetOutputPort())
        self._seed_glyph.SetScaleModeToDataScalingOff()
        self._seed_glyph.SetColorModeToColorByScalar()
        self._seed_mapper = vtk.vtkPolyDataMapper()
        self._seed_mapper.SetInputConnection(self._seed_glyph.GetOutputPort())
        # Interpret the per-glyph uchar[3] scalars as RGB directly.  Without
        # ScalarVisibilityOn + UsePointData the mapper falls back to the LUT
        # (which maps the 3-component array to near-black) -- the spheres then
        # render invisible against the dark 3D background.
        self._seed_mapper.SetScalarModeToUsePointData()
        self._seed_mapper.ScalarVisibilityOn()
        self._seed_mapper.SetColorModeToDirectScalars()
        self._seed_actor = vtk.vtkActor()
        self._seed_actor.SetMapper(self._seed_mapper)

        # -- hover-adhering MARKER: the sphere that clings to the surface under
        # the cursor.  This pipeline is the SINGLE 3D pipeline for the
        # highlight display-node type (ADR-0013 §1, one Pipeline per type), so
        # it renders the hover marker ITSELF rather than relying on a second
        # pipeline on the same type (which LayerDM would not create).
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

        # -- edit hover GLOW halo: a blurred glow around the seed under the
        # cursor (yellow), swapping to green while grabbed, so the surgeon
        # knows a marker is about to move -- the ControlPolygonPipeline glow
        # cue.  Rendered in a private overlay renderer carrying a
        # vtkOutlineGlowPass (the blur-to-halo pass); degrades to a plain
        # sphere when the pass class is unavailable.
        self._hover_target: tuple[str, int] | None = None
        self._halo_renderer: Any | None = None
        self._halo_sphere = vtk.vtkSphereSource()
        self._halo_sphere.SetPhiResolution(16)
        self._halo_sphere.SetThetaResolution(16)
        self._halo_sphere.SetRadius(self._seed_sphere.GetRadius() * HALO_HOVER_SCALE)
        self._halo_mapper = vtk.vtkPolyDataMapper()
        self._halo_mapper.SetInputConnection(self._halo_sphere.GetOutputPort())
        self._halo_actor = vtk.vtkActor()
        self._halo_actor.SetMapper(self._halo_mapper)
        self._halo_actor.GetProperty().SetColor(*HALO_HOVER_COLOR)
        self._halo_actor.SetVisibility(False)

    # ------------------------------------------------------------------ #
    # Grab bookkeeping -- the base's ``_drag_key`` IS the grabbed
    # ``(territoryId, index)`` (the key ``_nearest_key_in_display`` returns);
    # the rendering reads it through this alias so there is one source of
    # truth (the base's field), not a shadow copy.
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

        Production (LayerDM-created) instances resolve the surface from the
        shared display node exactly as ``VesselHighlightPipeline`` does, so
        the click-snap and the hover marker adhere to the same mesh with no
        injection.  A test-injected ``self._pick`` (``SetPickCore``)
        short-circuits this for the bare unit layer.

        The production pick is rebuilt when segment VISIBILITY changes (tracked
        via the display node's MTime), so hiding a vessel in the structures
        table removes it from collision detection live -- the cursor can only
        snap to a visible vessel (ADR-0037 slice 5).
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
        # Visible vessels only: the cursor snaps to a vessel you can see, never
        # the liver parenchyma, a tumour, or a hidden vessel (ADR-0037 slice 5).
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
        display node's ``pickSurface`` (ADR-0037 slice 5); ``[]`` under a
        test-injected pick (no segmentation) -> seeds are never hidden bare.
        """
        return self._structures.resolve(self._display_node)

    def _seed_visible(self, point: Any) -> bool:
        """True iff ``point``'s nearest vessel structure is visible.

        The vessel-visibility gate (ADR-0037 slice 5) the provider's
        ``iter_points`` and this pipeline's hit-test + seed-glyph rebuild all
        consult, so a hidden vessel's seeds are neither drawn nor grabbable.
        This is the REAL #569 seed-visibility notion (vessel SEGMENT
        visibility via ``VisibleStructuresCache``), NOT a territory-row toggle.
        """
        return self._structures.seed_visible(self._display_node, point)

    def SetCarrier(self, carrier: Any, territoryId: str) -> None:  # noqa: N802 - VTK verb
        """Bind the ``vtkMRMLCustomTerritoriesNode`` carrier + active territory.

        Instance-field binding for the BARE unit layer (no display node).  In
        production the carrier is resolved from the display node's reference
        (``_get_carrier``); this direct bind is the unit seam that keeps the
        edit math GL- and scene-free.

        Observation goes through ``_ensure_carrier_observed`` (the single
        ``_observed_carrier`` dedupe key), NOT a direct attach here -- else a
        later ``_ensure_carrier_observed`` resolving the same carrier would
        add a SECOND ModifiedEvent observer (double rebuild per Modified).
        """
        self._carrier = carrier
        self._territory_id = territoryId
        self._ensure_carrier_observed()

    def GetCarrier(self) -> Any | None:  # noqa: N802 - VTK verb
        return self._get_carrier()

    def _get_carrier(self) -> Any | None:
        """The carrier in effect: the display node's reference, else the bound one.

        Production (LayerDM-created) instances resolve the carrier from the
        shared display node so the widget/table and the manager-driven
        Pipeline agree; the bare unit layer (no display node) falls back to
        the directly-bound ``SetCarrier`` carrier.
        """
        carrier = _state.get_carrier(self._display_node)
        if carrier is not None:
            return carrier
        return self._carrier

    # ------------------------------------------------------------------ #
    # Active-territory + arm seam (Stage 2, ADR-0037 §Decision 3)
    #
    # These OVERRIDE the base's ``PointPlacementState``-backed arm gate: the
    # territory client rides the shared highlight display node via
    # ``TerritoryInteractionState`` (which also carries the active territory +
    # the carrier reference), so the widget/table reach the manager-driven
    # Pipeline through the display node all three hold (ADR-0037 §Decision 3).
    # ------------------------------------------------------------------ #

    def SetActiveTerritory(self, territoryId: str | None) -> None:  # noqa: N802 - VTK verb
        """Set the territory an armed click appends into (the ACTIVE one)."""
        if self._display_node is not None:
            _state.set_active_territory(self._display_node, territoryId)
        self._active_territory = territoryId

    def GetActiveTerritory(self) -> str | None:  # noqa: N802 - VTK verb
        if self._display_node is not None:
            return _state.get_active_territory(self._display_node)
        return self._active_territory

    def Arm(self) -> None:  # noqa: N802 - VTK verb
        """Enable add-on-click into the active territory ("Add Territory" / "Add seeds")."""
        if self._display_node is not None:
            _state.set_armed(self._display_node, True)
        self._armed = True

    def Disarm(self) -> None:  # noqa: N802 - VTK verb
        """Disable add-on-click ("Done" / Esc).  A click then adds nothing."""
        if self._display_node is not None:
            _state.set_armed(self._display_node, False)
        self._armed = False

    def IsArmed(self) -> bool:  # noqa: N802 - VTK verb
        if self._display_node is not None:
            return _state.is_armed(self._display_node)
        return self._armed

    def SetModuleActive(self, active: bool) -> None:  # noqa: N802 - VTK verb
        """Open/close the module-active add-on-click gate (concern #1).

        The owning module's ``enter()`` / ``exit()`` flips this; an add-on-click
        is declined while inactive, independent of the armed flag.  Rides the
        shared display node in production, the instance field bare.
        """
        if self._display_node is not None:
            _state.set_module_active(self._display_node, bool(active))
        self._module_active = bool(active)

    def IsModuleActive(self) -> bool:  # noqa: N802 - VTK verb
        if self._display_node is not None:
            return _state.is_module_active(self._display_node)
        return self._module_active

    def _placement_territory(self) -> str | None:
        """The territory a click appends into: the active one, else the bound one."""
        active = self.GetActiveTerritory()
        if active is not None:
            return active
        return self._territory_id

    # ------------------------------------------------------------------ #
    # LayerDM lifecycle
    # ------------------------------------------------------------------ #

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
                renderer.AddActor(self._seed_actor)
                renderer.AddActor(self._marker_actor)
            # The edit-hover grab halo renders in a private glow overlay (its
            # vtkOutlineGlowPass survives qMRMLThreeDView's SetPass reset).
            self._attach_halo_renderer(renderer)
            # Renderer churn cleared the display handle; re-derive it from the
            # base's retained display node (the ControlPolygonPipeline
            # re-attach precedent) so the carrier + seed glyphs come back.
            if self._display_node is None:
                display = self.GetDisplayNode()
                if display is not None:
                    self.SetDisplayNode(display)
            self._ensure_carrier_observed()
            self._rebuild_seed_actor()
            self._reconcile_highlight()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    def OnRendererRemoved(self, renderer: Any) -> None:  # noqa: N802 - VTK verb
        try:
            if renderer is not None:
                renderer.RemoveActor(self._seed_actor)
                renderer.RemoveActor(self._marker_actor)
            self._detach_halo_renderer()
            self._renderer = None
            self.cleanup()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    def _attach_halo_renderer(self, renderer: Any) -> None:
        """Build the private glow overlay on ``renderer``'s window.

        A dedicated overlay ``vtkRenderer`` (camera shared with the view
        renderer) carries the halo actor and a ``vtkOutlineGlowPass`` -- the
        blur-to-halo pass -- so qMRMLThreeDView's SetPass(nullptr) reset on the
        VIEW renderer never clobbers it (the ControlPolygonPipeline
        precedent).  Degrades to the plain halo sphere when the pass class or
        the render window is unavailable (bare unit layer).
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

    def cleanup(self) -> None:
        for node in list(self._observed_node_refs):
            self._detach_observer(node)
        self._carrier = None
        self._observed_carrier = None
        self._observed_pick_display = None
        self._drag_key = None  # the base's grab bookkeeping
        self._hover_target = None
        self._halo_actor.SetVisibility(False)

    def _ensure_carrier_observed(self) -> None:
        """Observe the in-effect carrier so seed glyphs track its edits.

        Production resolves the carrier from the display node (never via
        ``SetCarrier``), so the seed-glyph rebuild needs its own observer
        attach; re-attaches when the resolved carrier changes.
        """
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

        A segment show/hide modifies the segmentation's DISPLAY node; observe
        it so the seed glyphs repaint (dropping/restoring a hidden structure's
        seeds) without a carrier edit.  Re-attaches when the resolved display
        node changes; idempotent.
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

    def UpdatePipeline(self) -> None:  # noqa: N802 - VTK verb
        """LayerDM's re-sync hook (display-node Modified).

        The display node is added to the scene (LayerDM creates this pipeline)
        BEFORE the table binds the carrier reference onto it, so the carrier is
        not resolvable at creation.  This hook fires when the reference IS set,
        so it is where the seed-glyph observer finally attaches -- without it a
        seed placed from a SLICE view never repaints the 3D glyphs.
        """
        try:
            self._ensure_carrier_observed()
            self._ensure_pick_surface_observed()
            self._rebuild_seed_actor()
            self._reconcile_highlight()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    def _reconcile_highlight(self) -> None:
        """Sync the hover-marker sphere to the shared display node's adhering state.

        The single 3D pipeline renders the cross-view hover marker: shown at
        ``AdheringPointWorld`` when the display node is adhering + visible
        (published by a hover in ANY view), hidden otherwise.
        """
        display = self._display_node
        if display is None or not hasattr(display, "GetAdhering"):
            self._marker_actor.SetVisibility(False)
            return
        # Attach the segment-visibility observer once the pickSurface is wired
        # (idempotent) so a later structures-table show/hide repaints the seeds.
        self._ensure_pick_surface_observed()
        try:
            self._marker_sphere.SetRadius(float(display.GetRadius()))
        except Exception:  # pragma: no cover - defensive
            pass
        try:
            color = display.GetColor()
            self._marker_actor.GetProperty().SetColor(color[0], color[1], color[2])
        except Exception:  # pragma: no cover - defensive
            pass
        adhering = bool(display.GetAdhering()) and bool(display.GetVisibility())
        self._marker_actor.SetVisibility(adhering)
        if adhering:
            point = display.GetAdheringPointWorld()
            self._marker_actor.SetPosition(point[0], point[1], point[2])
            # Follow the hovered vessel point: reslice the 2D views to the
            # adhering point WHILE AIMING (not just on the click), so the slice
            # marker tracks the cursor over the vessel in 3D (ADR-0037 slice 5).
            self._jump_slices_to_world(point)

    # ------------------------------------------------------------------ #
    # Interaction -- client extension hooks (ADR-0038 §"What is not shared")
    #
    # The generic add-on-click / drag-to-edit-nearest / delete / bare-move-
    # decline arbitration is the base's; this pipeline contributes only the
    # TERRITORY-specific parts through the base's hooks: the vessel-gated grab
    # hit-test (``_nearest_key_in_display``), the surface-snap drag target
    # (``_event_world``), the per-territory grouping click (``_add_point`` +
    # the provider), the bare-move hover/adhering cue
    # (``_on_bare_move_decline``), and the grab/drag/release halo + seed
    # recolour (``_on_grab`` / ``_on_drag`` / ``_on_release``).
    # ``Can/ProcessInteractionEvent`` themselves are NOT overridden -- the base
    # drives them.
    # ------------------------------------------------------------------ #

    def _nearest_key_in_display(self, renderer: Any, eventData: Any):
        """Repack the territory hit-test into the base's ``(key, distance2)``.

        The base's grab seam expects a 2-tuple whose ``key`` round-trips through
        the provider's ``move_point`` / ``delete_point``.  The territory key is
        a ``(territoryId, index)`` PAIR, so this override consults the vessel-
        gated ``_nearest_point_in_display`` (which stays a 3-tuple the unit
        layer monkeypatches) and repacks it -- without touching the base's
        arbitration bodies (ADR-0038 §"What is not shared").
        """
        territory, index, distance2 = self._nearest_point_in_display(renderer, eventData)
        if territory is None or index is None:
            return None, sys.float_info.max
        return (territory, index), distance2

    def _event_world(self, renderer: Any, eventData: Any):
        """The drag target: the vessel-visibility-gated surface snap.

        Overrides the base's default (which would call the injected pick): the
        territory drag follows the cursor on the picked vessel surface via
        ``_event_world_on_surface`` (the seam the unit layer monkeypatches).
        """
        return self._event_world_on_surface(renderer, eventData)

    def _add_point(self, world: Any) -> None:
        """The add-on-click fan into the ACTIVE territory + the slice jump.

        Overrides the base's plain provider ``add_point`` so a territory click
        also reslices the 2D views onto the placed seed (ADR-0025 mirror) --
        the per-territory grouping itself is the provider's concern (it appends
        into ``_placement_territory``).
        """
        provider = self._provider
        if provider is not None:
            provider.add_point((world[0], world[1], world[2]))
        # A seed placed in a 3D view leaves the 2D slices on whatever plane
        # they were showing, so the projected slice marker floats off the
        # seed's anatomy; reslice every slice plane onto the seed (mirrors
        # LocatorReslicer, ADR-0025) so the 2D views show the slice through it.
        self._jump_slices_to_world(world)
        # Repaint immediately: the carrier observer's RequestRender does not
        # flush a frame mid-interaction (the slice-pipeline lesson).
        self._rebuild_seed_actor()

    def _on_grab(self, key: Any, renderer: Any, eventData: Any) -> None:
        """Grab an existing seed: swap the glow halo + seed to green.

        Publish a "drag in flight" flag on the shared display node so the
        table observer defers its expensive full rebuild until the drag ends
        (each drag move relocates the seed via ``SetNthAnnotationPoint``, which
        fires the carrier ``Modified`` -- without the flag the whole tree would
        rebuild per frame; ADR-0037 §Decision 3).
        """
        if self._display_node is not None:
            _state.set_grabbing(self._display_node, True)
        self._position_halo()
        self._rebuild_seed_actor()

    def _on_drag(self, key: Any) -> None:
        """Track the grabbed seed under the drag + repaint immediately."""
        self._position_halo()
        self._rebuild_seed_actor()

    def _on_release(self) -> None:
        """Gesture over: drop the grab colour (fall back to hover/none).

        Clear the "drag in flight" flag FIRST, then fire ONE carrier
        ``Modified`` so the table's deferred observer runs a single full
        rebuild reflecting the final seed positions (ADR-0037 §Decision 3).
        """
        if self._display_node is not None:
            _state.set_grabbing(self._display_node, False)
        self._position_halo()
        self._rebuild_seed_actor()
        carrier = _state.get_carrier(self._display_node)
        if carrier is not None:
            carrier.Modified()

    def _on_bare_move_decline(self, renderer: Any, eventData: Any) -> None:
        """Raise the hover cue on a declined bare move (ADR-0033 side effect).

        Over an existing seed -> glow halo on it (about-to-move cue) + suppress
        the placement preview; over empty surface -> raise the adhering
        placement preview.  A declined bare move, so the camera is untouched.
        """
        territory, index, distance2 = self._nearest_point_in_display(renderer, eventData)
        if (
            territory is not None
            and index is not None
            and distance2 <= POINT_PICK_RADIUS_PX * POINT_PICK_RADIUS_PX
        ):
            self._set_hover((territory, index))
            self._clear_adhering()
        else:
            self._set_hover(None)
            self._raise_highlight(renderer, eventData)
        self._reconcile_highlight()
        # The base's bare-move arbitration DECLINES (returns without a render),
        # and a bare hover mutates no observed node, so nothing else flushes a
        # frame: request one HERE or the adhering marker / glow halo is computed
        # but never painted (the mid-interaction RequestRender discipline the
        # sibling ControlPolygonPipeline hover path also follows).  Without it
        # the vessel highlight never appears on hover.
        self.RequestRender()

    def DeleteAnnotationPoint(self, territoryId: str, index: int) -> bool:  # noqa: N802 - VTK verb
        """Remove EXACTLY ONE annotation point (delete-from-table end).

        ADR-0037 §Decision 2 "delete removes one point"; the tail shifts up
        in order.  Returns True iff a point was removed.  Routes through the
        provider's delete write-back (the base's ``DeletePoint`` seam) so the
        key contract matches the grab / drag path.
        """
        return bool(self.DeletePoint((territoryId, int(index))))

    # ------------------------------------------------------------------ #
    # Geometry seams (monkeypatched in the unit layer)
    # ------------------------------------------------------------------ #

    def _event_world_on_surface(self, renderer: Any, eventData: Any):
        """Snap the event pixel onto the surface via ``VesselSurfacePick``.

        Builds the cursor ray by unprojecting the event pixel at the near +
        far clipping depths, feeds it to the injected pick core, and returns
        the surface-snapped world point (``None`` on a miss / no surface).
        The unit layer injects the result directly, keeping the edit math
        GL-free.
        """
        pick = self._ensure_pick()
        if pick is None:
            return None
        ray = self._cursor_ray(renderer, eventData)
        if ray is None:
            return None
        p1, p2 = ray
        return pick.pick(p1, p2)

    def _nearest_point_in_display(self, renderer: Any, eventData: Any):
        """``(territoryId, index, distance2)`` of the point nearest the pixel.

        Scans the carrier's active territory's points, projects each to
        display, and returns the nearest with its REAL squared display
        distance (LayerDM arbitration).  ``(None, None, +inf)`` when there
        is no carrier / territory / point.  A hidden-structure seed is not
        drawn, so it must not be a hover/grab target either -- skipped via the
        ``seed_visible`` gate (ADR-0037 slice 5).
        """
        carrier = self._get_carrier()
        territory = self._placement_territory()
        if carrier is None or territory is None:
            return None, None, sys.float_info.max
        count = carrier.GetNumberOfAnnotationPoints(territory)
        if count == 0:
            return None, None, sys.float_info.max
        try:
            ex, ey = eventData.GetDisplayPosition()
        except Exception:  # pragma: no cover - defensive (fake events)
            return None, None, sys.float_info.max

        best_index = None
        best_d2 = sys.float_info.max
        for i in range(count):
            point = carrier.GetNthAnnotationPoint(territory, i)
            # A hidden-structure seed is not drawn, so it must not be a
            # hover/grab target either -- skip it (ADR-0037 slice 5).
            if not self._seed_visible(point):
                continue
            renderer.SetWorldPoint(point[0], point[1], point[2], 1.0)
            renderer.WorldToDisplay()
            dx, dy, _dz = renderer.GetDisplayPoint()
            d2 = (dx - ex) ** 2 + (dy - ey) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best_index = i
        if best_index is None:
            return None, None, sys.float_info.max
        return territory, best_index, best_d2

    def _cursor_ray(self, renderer: Any, eventData: Any):
        """The world-space cursor ray ``(p1, p2)`` for the event pixel."""
        try:
            ex, ey = eventData.GetDisplayPosition()
        except Exception:  # pragma: no cover - defensive
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

    def _raise_highlight(self, renderer: Any, eventData: Any) -> None:
        """Publish the hover-adhering point onto the display node, if any.

        The annotation placement shares the vessel-adhering highlight: a
        bare hover resolves the surface point under the cursor and writes it
        onto the (data-only) highlight display node, exactly as
        ``VesselHighlightPipeline`` does.  Change-gated so the hover does not
        storm ``Modified``.  A no-op when no display node / surface is wired.
        """
        display = self._display_node
        if display is None or not hasattr(display, "SetAdhering"):
            return
        world = self._event_world_on_surface(renderer, eventData)
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

    def _clear_adhering(self) -> None:
        """Retire the placement preview (cursor is over a seed, not empty surface)."""
        display = self._display_node
        if display is None or not hasattr(display, "SetAdhering"):
            return
        if bool(display.GetAdhering()):
            display.SetAdhering(False)
            display.Modified()

    def _set_hover(self, target: tuple[str, int] | None) -> None:
        """Glow-halo the seed under the cursor (``None`` clears the hover)."""
        if target == self._hover_target:
            return
        self._hover_target = target
        self._position_halo()
        self._rebuild_seed_actor()

    def _position_halo(self) -> None:
        """Place the glow halo on the grabbed (green) or hovered (yellow) seed."""
        target = self._drag_target or self._hover_target
        carrier = self._get_carrier()
        show = False
        if target is not None and carrier is not None:
            territory, index = target
            if 0 <= index < carrier.GetNumberOfAnnotationPoints(territory):
                point = carrier.GetNthAnnotationPoint(territory, index)
                self._halo_actor.SetPosition(point[0], point[1], point[2])
                colour = HALO_GRAB_COLOR if self._drag_target is not None else HALO_HOVER_COLOR
                self._halo_actor.GetProperty().SetColor(*colour)
                show = True
        self._halo_actor.SetVisibility(show)

    def _jump_slices_to_world(self, world: Any) -> None:
        """Offset every slice view's plane onto ``world`` (JumpSliceByOffsetting).

        Translates each plane along its OWN normal (orientation preserved), so
        the 2D views reslice to the placed seed.  A no-op (never raising) when
        the scene or the jump API is unavailable.
        """
        if world is None:
            return
        scene = self._display_node.GetScene() if self._display_node is not None else None
        if scene is None:
            carrier = self._get_carrier()
            scene = carrier.GetScene() if carrier is not None else None
        if scene is None:
            return
        for i in range(scene.GetNumberOfNodesByClass("vtkMRMLSliceNode")):
            slice_node = scene.GetNthNodeByClass(i, "vtkMRMLSliceNode")
            jump = getattr(slice_node, "JumpSliceByOffsetting", None)
            if jump is not None:
                jump(float(world[0]), float(world[1]), float(world[2]))

    # ------------------------------------------------------------------ #
    # Observers (reconcile) + plumbing
    # ------------------------------------------------------------------ #

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
        """Reconcile on a carrier ``Modified`` -- idempotent, no drift.

        The placement Pipeline holds no shadow copy of the point set: the
        carrier IS the source of truth, so a reconcile driven by an
        unrelated ``Modified`` (a table repaint, a colour change) reads the
        carrier and repaints without adding / moving / dropping any point
        (ADR-0037 §Conformance no-drift).
        """
        del caller, event
        try:
            self._rebuild_seed_actor()
            self.RequestRender()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    # ------------------------------------------------------------------ #
    # Placed-seed rendering (ADR-0037 §Decision 2)
    # ------------------------------------------------------------------ #

    def _rebuild_seed_actor(self) -> None:
        """Rebuild the seed-glyph point set from the carrier, coloured per territory.

        The carrier is the source of truth: read every visible territory's
        points, glyph each as a sphere tinted with the territory's display
        colour (ADR-0037 §Decision 1 display slot).  A seed whose STRUCTURE
        (nearest input segment) is hidden via the structures table is OMITTED,
        so hiding a vessel hides its seeds live (ADR-0037 slice 5).  A
        no-op-safe rebuild — an empty carrier clears the glyphs.
        """
        self._seed_points.Reset()
        self._seed_colors.Reset()
        self._seed_colors.SetNumberOfComponents(3)
        grab_rgb = tuple(int(c * 255) for c in HALO_GRAB_COLOR)
        hover_rgb = tuple(int(c * 255) for c in HALO_HOVER_COLOR)
        carrier = self._get_carrier()
        if carrier is not None:
            for territory in carrier.GetAnnotationTerritoryIds():
                if not bool(carrier.GetTerritoryVisibility(territory)):
                    continue
                rgb = carrier.GetTerritoryColor(territory)
                base = (
                    int(max(0.0, min(1.0, rgb[0])) * 255),
                    int(max(0.0, min(1.0, rgb[1])) * 255),
                    int(max(0.0, min(1.0, rgb[2])) * 255),
                )
                count = carrier.GetNumberOfAnnotationPoints(territory)
                for i in range(count):
                    point = carrier.GetNthAnnotationPoint(territory, i)
                    # Omit a seed whose structure is hidden (ADR-0037 slice 5);
                    # cached per-structure locators keep this O(log n) per seed.
                    if not self._seed_visible(point):
                        continue
                    self._seed_points.InsertNextPoint(point[0], point[1], point[2])
                    key = (territory, i)
                    if key == self._drag_target:
                        self._seed_colors.InsertNextTuple3(*grab_rgb)  # grabbed: green
                    elif key == self._hover_target:
                        self._seed_colors.InsertNextTuple3(*hover_rgb)  # hovered: yellow
                    else:
                        self._seed_colors.InsertNextTuple3(*base)
        self._seed_points.Modified()
        self._seed_colors.Modified()
        self._seed_polydata.Modified()


class _TerritorySurfacePick:
    """The base's pick provider, delegating to the pipeline's surface snap.

    The base places a click at whatever world the injected pick returns
    (ADR-0038 §"Base extension" -- no surface-vs-volume branch).  Territories'
    pick is the vessel-visibility-gated surface snap, which also stays the
    unit-layer monkeypatch seam (``_event_world_on_surface``): this adapter
    forwards the base's ``pick_for_event`` to it so both the production pick
    and the injected test double flow through one place.
    """

    def __init__(self, pipeline) -> None:
        self._pipeline = pipeline

    def pick_for_event(self, renderer: Any, eventData: Any):
        # Re-read through the pipeline so a unit-layer monkeypatch of
        # ``_event_world_on_surface`` is always honoured (the add + drag paths
        # then share one surface-snap seam).
        return self._pipeline._event_world_on_surface(renderer, eventData)


def registerTerritoryPlacementPipelineCreator() -> None:  # noqa: N802 - project convention
    """Register the ``TerritoryPlacementPipeline`` creator with LayerDM.

    Idempotent (module-level flag), mirroring
    ``registerVesselHighlightPipelineCreator``.  The creator matches
    ``(vtkMRMLViewNode, vtkMRMLTerritoriesHighlightDisplayNode)`` -- the 3D
    views only; annotation placement is a 3D-surface interaction (ADR-0013
    §5 call 3).  Rendering + interaction route through this scripted
    Pipeline + its creator, never a custom displayable manager (ADR-0013
    §5).
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
            return TerritoryPlacementPipeline()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            return None

    creator = vtkMRMLLayerDMPipelineScriptedCreator()
    creator.SetPythonCallback(tryCreate)
    vtkMRMLLayerDMPipelineFactory.GetInstance().AddPipelineCreator(creator)
    _REGISTERED = True

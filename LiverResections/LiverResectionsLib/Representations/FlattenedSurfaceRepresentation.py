# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Representation that owns the resectogram's flattened-surface assembly.

The resectogram is the flattened 2D image of the Bezier ``(u, v)``
parameter domain (ADR-0025 §Context).  In the v1 monolith
``vtkSlicerBezierSurfaceRepresentation3D`` this assembly is the 2D path:
a ``BezierPlane`` source feeding the
``vtkOpenGLResection2DPolyDataMapper`` (relocated home
``LiverResections/VTKWidgets/``), rendered through a private
``ResectogramCamera`` into a dedicated overlay renderer, with the
distance-map texture bound to the mapper and the anisotropic
``MatRatio`` scaling applied.

This Representation is the v2.0 LayerDM-bound home of that assembly per
ADR-0013 §6 (Representations are composable VTK pipelines).  It owns:

* the ``BezierPlane`` flattened-quad source,
* the 2D resection mapper + actor,
* the ``ResectogramCamera``,
* the distance-map texture binding, and
* the ``MatRatio`` aspect-ratio scaling, computed via the pure-VTK
  ``vtkLiverResectogramAspectRatio`` helper (Algorithm library,
  ADR-0015 §1) rather than re-deriving the v1 ``Ratio(bool)`` math.

Gaussian-blur post-pass (net-new, v2.0)
---------------------------------------
The resectogram display node carries a ``BlurEnabled`` on/off flag (no
legacy counterpart).  When it is true this Representation moves the
resectogram actor onto a PRIVATE overlay ``vtkRenderer`` it owns and sets
a ``vtkGaussianBlurPass`` on that renderer; when false it detaches the
pass and overlay, leaving the non-blur path byte-identical to the
pre-blur appearance.  The overlay renderer (rather than the dedicated
resectogram view's main renderer) carries the pass because
``qMRMLThreeDView`` resets ``SetPass(nullptr)`` on every view-node
ModifiedEvent and would clobber a pass set on the main renderer.  The
blur is a GPU render-pass on a renderer the Representation owns — NOT
pure-VTK math — so it lives here and not in the ADR-0015 §1 Algorithm
library.  The toggle is live: it reconciles on every ``update()`` (the
Pipeline's display-node MTime path), so a ``BlurEnabled`` change engages
or disengages the pass without rebuilding the assembly (ADR-0013 §6).

Scope
-----
This Representation COMPOSES the assembly, wires the display-node fields
it consumes, and binds the distance-map 3D texture + ras/ijk matrices on
the 2D mapper so the flattened ``(u, v)`` quad samples the distance field
and paints the projected margin band (ADR-0025 §Context).  The
aspect-ratio math is routed through the extracted Algorithm helper.

The flattened quad fed to the 2D mapper as its INPUT geometry is the
fixed planar ``(u, v)`` domain — that defines the OUTPUT rectangle.  The
real surface enters as the mapper's ``"BSPoints"`` point-data array (the
``vertexMCBS`` shader attribute): the data node's evaluated Bezier
surface ``S(u, v)`` positions, sampled at the quad's resolution so the
arrays align vertex-for-vertex.  The mapper transforms ``BSPoints``
through ras→ijk→texture to sample the distance field at the REAL surface
position, so the flattened image is coherent with the 3D surface and
re-renders when the control points move (ADR-0025 §Context; the v1
``BezierPlane->GetPointData()->AddArray(BezierSurfaceSourcePoints)``
feed).  Without ``BSPoints`` the mapper falls back to the flat quad's own
vertices and paints the distance field on a fixed plane — the
non-coherent / non-reactive fixed-quad failure mode.

The relocated 2D mapper (``vtkOpenGLResection2DPolyDataMapper``) is a
custom wrapped-C++ class reachable only inside a Slicer process; it is
injected, not silently discovered (ADR-0014 §3).  In production the
``resection_mapper_2d`` constructor argument is ``None`` and this
Representation resolves the real wrapped class (raising if it is off the
path — a real misconfiguration must not degrade to a shader-less generic
mapper); the bare-VTK unit layer (ADR-0008 §2) injects a generic
``vtkPolyDataMapper`` instance.  The flattened-quad SOURCE is NOT custom:
``vtkBezierSurfaceSource`` is preferred but degrades to base VTK's
``vtkPlaneSource`` (always present), and the distance-map texture /
aspect-ratio helpers stay behind soft import guards.

References
----------
* `ADR-0013`_ §6 — Representations as composable VTK pipelines.
* `ADR-0015`_ §1 — Algorithm-library pure-VTK helpers
  (``vtkLiverResectogramAspectRatio``).
* `ADR-0025`_ §Context — the resectogram is a 1:1 image of the Bezier
  ``(u, v)`` parameter domain.

.. _ADR-0013: ../../../Docs/adr/0013-layerdm-pipeline-pattern.md
.. _ADR-0015: ../../../Docs/adr/0015-cpp-algorithm-library.md
.. _ADR-0025: ../../../Docs/adr/0025-locator-architecture.md
"""

from __future__ import annotations

from typing import Any

import vtk


# --------------------------------------------------------------------------- #
# Overlay-renderer layer for the resectogram (matches the v1 monolith's
# RENDERER_LAYER for the 2D co-renderer).
# --------------------------------------------------------------------------- #

RESECTOGRAM_RENDERER_LAYER = 1

# Flattened-quad geometry for the resectogram domain.  The resectogram is
# the flattened 2D image of the Bezier ``(u, v)`` parameter domain
# (ADR-0025 §Context); the strip is drawn on a FIXED flat quad — the same
# planar 4x4 control grid + 20x20 tessellation the v1 monolith
# ``vtkSlicerBezierSurfaceRepresentation3D`` poses its ``BezierPlane`` from
# — NOT the data node's 3D surface.  The data node feeds the distance-map
# texture and the ``MatRatio`` squeeze, not this quad's vertices.
_FLATTENED_QUAD_RESOLUTION = (20, 20)
_FLATTENED_QUAD_CONTROL_GRID = tuple(
    (x, row * 40.0, 0.0)
    for row in range(4)
    for x in (-60.0, -20.0, 20.0, 60.0)
)


class FlattenedSurfaceRepresentation:
    """VTK assembly for the resectogram's flattened surface.

    Constructor
    -----------
    ``FlattenedSurfaceRepresentation(renderer=None, *, resection_mapper_2d=None)``

    * ``renderer`` — the ``vtkRenderer`` the resectogram actor is added
      to.  Optional; ``None`` is supported for unit tests (the actor
      exists but is unrendered).
    * ``resection_mapper_2d`` — the custom 2D-mapper INSTANCE (dependency
      injection, ADR-0014 §3).  ``None`` (production) resolves the real
      ``vtkOpenGLResection2DPolyDataMapper``, raising if it is off the
      path.  An injected instance (bare-VTK unit layer, ADR-0008 §2) is
      used as-is.  The flattened-quad source is not affected.

    Public methods
    --------------
    * ``update(display_node, data_node)`` — reads decoration from the
      display node (``ShowResection2D`` / ``MirrorDisplay`` /
      ``EnableFlexibleBoundary`` / ``TextureNumComps`` / ``BlurEnabled``),
      geometry from the data node, recomputes ``MatRatio`` through the
      Algorithm helper, reconciles the resectogram actor, and engages /
      disengages the Gaussian-blur post-pass.  Tolerant of ``None``
      arguments.
    * ``cleanup()`` — detaches the actor from the renderer and releases
      the VTK pipeline.

    Introspection (used by unit tests)
    ----------------------------------
    * ``GetResectionMapper2D()`` / ``GetResectionActor2D()`` — the 2D
      mapper + actor pair, or ``None`` when VTK is absent.
    * ``GetResectogramCamera()`` — the private overlay camera.
    * ``GetMatRatioApplied()`` — last ``MatRatio`` pushed onto the 2D
      mapper, or ``None`` before the first ``update()`` / when the
      mapper does not expose ``SetMatRatio``.
    * ``GetBlurPass()`` / ``GetBlurOverlayRenderer()`` /
      ``IsBlurPassAttached()`` — the Gaussian-blur post-pass, the private
      overlay renderer hosting it, and whether blur is currently engaged.
    """

    def __init__(
        self,
        renderer: Any | None = None,
        *,
        resection_mapper_2d: Any | None = None,
    ) -> None:
        self._renderer: Any | None = None

        self._bezier_plane: Any | None = None
        self._resection_mapper_2d: Any | None = None
        self._resection_actor_2d: Any | None = None
        self._resectogram_camera: Any | None = None

        # Gaussian-blur post-pass (net-new v2.0, on/off toggle, ADR-0013 §6).
        # The blur is a GPU render-pass set DIRECTLY on the resectogram view's
        # renderer (the one this Representation drew the strip into) — it blurs
        # the already-correct flattened image.  An earlier private-overlay-
        # renderer variant (to dodge ``qMRMLThreeDView`` resetting
        # ``SetPass(nullptr)`` on view-node ModifiedEvent) mis-rendered: the 2D
        # mapper's distance-map texture + shader did not survive being
        # relocated onto a second renderer, so only the grid/border drew.  The
        # dedicated resectogram view has a FIXED camera (no orbit), so its view
        # node is not modified during steady-state display; ``_reconcile_blur_pass``
        # re-sets the pass on every ``update()`` (data/display edit) right
        # before the render, so the clobber does not bite in practice.  Blur-off
        # clears the pass, leaving the non-blur appearance unchanged.
        self._blur_pass: Any | None = None
        self._blur_attached: bool = False

        # The distance-map volume node the bound texture was built from.
        # ``None`` until the first ``update()`` with a distance map binds
        # one; used purely as the idempotency key so the texture is rebuilt
        # only when the volume changes.  The texture OBJECT itself is owned
        # SOLELY by the 2D mapper's ``vtkSmartPointer`` (C++) — this
        # Representation deliberately keeps NO Python reference to it, so it
        # dies with the mapper at view teardown rather than outliving the
        # C++ pipeline on the Python heap (a vtkDebugLeaks trip).
        self._distance_map_volume: Any | None = None

        # The orchestrating ``vtkMRMLResectionPlanNode`` wrapper, set by the
        # ResectogramPipeline via ``SetResectionPlanNode`` (ADR-0031).  It
        # carries the distance-shading input set the flattened strip reads --
        # the distance-map volume AND the safety / risk margins -- none of
        # which live on the carrier (ADR-0014 §"Fourth layer").
        self._resection_plan_node: Any | None = None

        # Last MatRatio pushed onto the 2D mapper.  ``None`` until the
        # first ``update()`` runs OR the mapper does not expose
        # ``SetMatRatio`` (generic-mapper fallback path).
        self._mat_ratio_applied: tuple[float, float] | None = None

        # Memoised input — same idempotency strategy as
        # ConfirmedRepresentation.
        self._last_surface_signature: tuple | None = None
        self._input_refresh_count: int = 0

        self._build_vtk_pipeline(resection_mapper_2d)

        if renderer is not None:
            self.SetRenderer(renderer)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def SetRenderer(self, renderer: Any | None) -> None:
        """Attach the resectogram actor to ``renderer``."""
        if self._renderer is not None and self._renderer is not renderer:
            self._detach_blur_pass(self._renderer)
            self._detach_actors(self._renderer)
        self._renderer = renderer
        if renderer is not None:
            self._attach_actors(renderer)

    def GetRenderer(self) -> Any | None:
        return self._renderer

    def SetResectionPlanNode(self, plan_node: Any | None) -> None:  # noqa: N802 - VTK verb
        """Attach the orchestrating ``vtkMRMLResectionPlanNode`` wrapper.

        The ResectogramPipeline calls this before ``update()`` so the flattened
        strip can read its distance-shading input set -- the distance-map volume
        AND the safety / risk margins -- off the wrapper (ADR-0031), mirroring
        the 3D ``BezierPlanningRepresentation``.  ``None`` clears it (the
        no-distance-map fallback).
        """
        self._resection_plan_node = plan_node

    def update(self, display_node: Any | None, data_node: Any | None) -> None:
        """Reconcile the resectogram against the current display + data nodes.

        Tolerant of ``None`` arguments — when either node is missing the
        actor falls back to invisible / default state.
        """
        self._apply_display_node(display_node)
        self._apply_data_node(display_node, data_node)
        self._pose_overlay_camera(display_node)
        self._reconcile_blur_pass(display_node)

    def cleanup(self) -> None:
        """Detach actors from the renderer and drop the VTK pipeline."""
        # Drop the distance-map texture off the mapper so the mapper's
        # vtkSmartPointer (the texture's sole owner) releases it (the v1
        # clear-on-teardown discipline; avoids a stale sampler3D bind).
        mapper = self._resection_mapper_2d
        if mapper is not None:
            unbind = getattr(mapper, "SetDistanceMapTextureObject", None)
            if unbind is not None:
                try:
                    unbind(None)
                except Exception:  # pragma: no cover - defensive
                    pass
        self._distance_map_volume = None

        if self._renderer is not None:
            self._detach_blur_pass(self._renderer)
            self._detach_actors(self._renderer)
            self._renderer = None
        self._bezier_plane = None
        self._resection_mapper_2d = None
        self._resection_actor_2d = None
        self._resectogram_camera = None

        # ``_detach_blur_pass`` above already cleared the pass off the renderer
        # when blur was engaged; drop the pass object too.
        self._blur_pass = None
        self._blur_attached = False

    # ------------------------------------------------------------------ #
    # Introspection — used by the unit-layer tests
    # ------------------------------------------------------------------ #

    def GetResectionMapper2D(self) -> Any | None:
        return self._resection_mapper_2d

    def GetResectionActor2D(self) -> Any | None:
        return self._resection_actor_2d

    def GetResectogramCamera(self) -> Any | None:
        return self._resectogram_camera

    def GetBezierPlane(self) -> Any | None:
        return self._bezier_plane

    def GetMatRatioApplied(self) -> tuple[float, float] | None:
        return self._mat_ratio_applied

    def GetInputRefreshCount(self) -> int:
        return self._input_refresh_count

    def GetBlurPass(self) -> Any | None:
        """The ``vtkGaussianBlurPass``, or ``None`` before it is built."""
        return self._blur_pass

    def IsBlurPassAttached(self) -> bool:
        """Whether the blur pass is currently set on the renderer.

        The blur invariant the arena + unit layers pin: blur is engaged when
        ``BlurEnabled`` is true and disengaged when false.
        """
        return self._blur_attached

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _build_vtk_pipeline(self, resection_mapper_2d: Any | None) -> None:
        """Construct the flattened-quad source, 2D mapper, actor + camera.

        The 2D mapper is injected, not silently discovered (ADR-0014 §3): a
        ``None`` argument (production) resolves the real relocated
        ``vtkOpenGLResection2DPolyDataMapper``, raising if it is off the path;
        an injected instance (bare-VTK unit layer, ADR-0008 §2) is used as-is.

        The flattened-quad source is NOT custom: ``vtkBezierSurfaceSource`` is
        preferred but degrades to base VTK's ``vtkPlaneSource`` (always
        present), so it keeps its resolve-or-fallback shape.
        """
        self._bezier_plane = _make_flattened_quad_source()
        _initialise_flattened_quad(self._bezier_plane)

        mapper = (
            resection_mapper_2d
            if resection_mapper_2d is not None
            else _make_resection_mapper_2d()
        )
        if self._bezier_plane is not None and hasattr(mapper, "SetInputConnection"):
            mapper.SetInputConnection(self._bezier_plane.GetOutputPort())
        self._resection_mapper_2d = mapper

        self._resection_actor_2d = vtk.vtkActor()
        self._resection_actor_2d.SetMapper(self._resection_mapper_2d)
        self._resection_actor_2d.SetVisibility(False)

        self._resectogram_camera = vtk.vtkCamera()

    def _attach_actors(self, renderer: Any) -> None:
        if self._resection_actor_2d is not None and hasattr(renderer, "AddActor"):
            renderer.AddActor(self._resection_actor_2d)

    def _detach_actors(self, renderer: Any) -> None:
        if self._resection_actor_2d is not None and hasattr(renderer, "RemoveActor"):
            try:
                renderer.RemoveActor(self._resection_actor_2d)
            except Exception:  # pragma: no cover - defensive
                pass

    def _apply_display_node(self, display_node: Any | None) -> None:
        """Push resectogram decoration fields onto the 2D mapper + actor."""
        show_2d = _safe_get_bool(display_node, "GetShowResection2D", default=False)
        texture_num_comps = _safe_get_int(
            display_node, "GetTextureNumComps", default=0
        )

        if self._resection_actor_2d is not None:
            self._resection_actor_2d.SetVisibility(bool(show_2d))

        mapper = self._resection_mapper_2d
        if mapper is not None:
            setter = getattr(mapper, "SetTextureNumComps", None)
            if setter is not None:
                setter(texture_num_comps)

    def _apply_data_node(
        self, display_node: Any | None, data_node: Any | None
    ) -> None:
        """Push the real surface onto the 2D mapper, then recompute the
        anisotropic ``MatRatio`` via the Algorithm helper.

        The data node's evaluated Bezier surface ``S(u, v)`` is pushed onto
        the 2D mapper's input as the ``"BSPoints"`` point-data array (the
        ``vertexMCBS`` shader attribute), so the flattened image samples the
        distance field at the REAL surface position — coherent with the 3D
        view and reactive to control-point edits (ADR-0025 §Context).  When
        the data node exposes only an explicit sampled-surface points object
        (the unit-test stub path), that is used directly.

        The ``MatRatio`` math is NOT re-derived here — it is routed
        through the extracted pure-VTK ``vtkLiverResectogramAspectRatio``
        helper (ADR-0015 §1), with ``flexibleBoundary`` taken from the
        display node's ``EnableFlexibleBoundary`` field.
        """
        flexible = _safe_get_bool(
            display_node, "GetEnableFlexibleBoundary", default=False
        )

        # Prefer an explicit sampled-surface points object (unit-test stub);
        # otherwise evaluate S(u, v) from the data node's Bezier control
        # points (the real markups-node path inside Slicer).
        sampled = _safe_get_sampled_surface(data_node)
        if sampled is None:
            sampled = self._evaluate_surface_points(data_node)

        signature = _surface_signature(sampled, flexible)
        if signature != self._last_surface_signature:
            self._last_surface_signature = signature
            self._input_refresh_count += 1

        self._push_surface_onto_mapper_input(sampled)
        self._apply_mat_ratio(sampled, flexible)
        self._apply_distance_map_texture(display_node, data_node)

    def _evaluate_surface_points(self, data_node: Any | None) -> Any | None:
        """Return the data node's evaluated Bezier surface ``S(u, v)`` points.

        Reads the markups node's 16 control points and feeds a
        ``vtkBezierSurfaceSource`` at the flattened quad's resolution so the
        evaluated grid aligns vertex-for-vertex with the quad the 2D mapper
        renders (the v1 ``BezierSurfaceSource`` feed).  Returns ``None`` when
        VTK / the source is unavailable, the data node carries no control
        points, or the legacy 16-point grid is not yet complete — the caller
        then degrades to the prior fixed-quad fallback (no crash).
        """
        if data_node is None:
            return None

        control_points = _read_control_points(data_node)
        if control_points is None:
            return None

        source = _make_flattened_quad_source()
        set_resolution = getattr(source, "SetResolution", None)
        set_control_points = getattr(source, "SetControlPoints", None)
        if set_resolution is None or set_control_points is None:
            return None  # generic vtkPlaneSource fallback — no Bezier eval
        try:
            set_resolution(*_FLATTENED_QUAD_RESOLUTION)
            set_control_points(control_points)
            source.Update()
            output = source.GetOutput()
            points = output.GetPoints()
        except Exception:  # pragma: no cover - defensive
            return None
        if points is None or points.GetNumberOfPoints() == 0:
            return None
        return points

    def _push_surface_onto_mapper_input(self, sampled: Any | None) -> None:
        """Push ``sampled`` onto the 2D mapper input as the ``"BSPoints"`` array.

        Adds (or replaces) the ``"BSPoints"`` point-data array on the
        flattened quad's output — the mapper's optional ``vertexMCBS``
        attribute (the REAL surface ``S(u, v)`` positions).  The mapper
        transforms these through ras→ijk→texture to sample the distance
        field at the real surface, making the flattened image coherent with
        the 3D surface (the v1
        ``BezierPlane->GetPointData()->AddArray(BezierSurfaceSourcePoints)``
        feed).  No-op when the quad source, the sampled surface, or the
        point-data array (the bare-VTK stub-points path) is unavailable — the
        mapper then falls back to the flat quad's own vertices.
        """
        plane = self._bezier_plane
        if plane is None or sampled is None:
            return
        get_data = getattr(sampled, "GetData", None)
        if get_data is None:
            return  # stub points object (unit tests) — no vtkPoints array
        try:
            if hasattr(plane, "Update"):
                plane.Update()
            output = plane.GetOutput()
            point_data = output.GetPointData()
            surface_array = get_data()
        except Exception:  # pragma: no cover - defensive
            return
        if point_data is None or surface_array is None:
            return
        # ``AddArray`` replaces an existing same-named array, so naming the
        # surface array "BSPoints" and adding it both installs and refreshes
        # the mapper's optional vertexMCBS attribute on every update.
        surface_array.SetName("BSPoints")
        point_data.AddArray(surface_array)

    def _apply_mat_ratio(self, sampled: Any | None, flexible: bool) -> None:
        """Compute + push the resectogram aspect-ratio scaling.

        Delegates the arc-length math to
        ``vtkLiverResectogramAspectRatio::ComputeAspectRatio`` (Algorithm
        library) — the skeleton must not re-derive the v1 ``Ratio(bool)``
        computation.  When the helper or the sampled surface is
        unavailable (bare-VTK pytest path), falls back to the isotropic
        ``{1, 1}`` so the actor still has a defined scaling.
        """
        mapper = self._resection_mapper_2d
        if mapper is None:
            return
        setter = getattr(mapper, "SetMatRatio", None)
        if setter is None:
            return

        ratio = self._compute_aspect_ratio(sampled, flexible)
        if ratio is None:
            return
        setter(list(ratio))
        self._mat_ratio_applied = (float(ratio[0]), float(ratio[1]))

    def _apply_resection_margins(self, mapper: Any) -> None:
        """Thread the wrapper's resection / uncertainty margins onto the mapper.

        Per ADR-0031 the safety + risk margins are path-specific inputs carried
        by the ``vtkMRMLResectionPlanNode`` wrapper, alongside the distance-map
        volume, as one distance-shading input set.  Ports the margin block of
        the 3D ``BezierPlanningRepresentation._apply_resection_plan``: push
        ``GetSafetyMargin_mm`` -> ``SetResectionMargin`` and ``GetRiskMargin_mm``
        -> ``SetUncertaintyMargin``.  A no-op when no plan is wired or on the
        generic fallback mapper (the getattr guards).
        """
        plan = self._resection_plan_node
        if plan is None:
            return
        safety = getattr(plan, "GetSafetyMargin_mm", None)
        risk = getattr(plan, "GetRiskMargin_mm", None)
        set_resection = getattr(mapper, "SetResectionMargin", None)
        set_uncertainty = getattr(mapper, "SetUncertaintyMargin", None)
        if safety is not None and set_resection is not None:
            set_resection(float(safety()))
        if risk is not None and set_uncertainty is not None:
            set_uncertainty(float(risk()))

    def _apply_distance_map_texture(
        self, display_node: Any | None, data_node: Any | None
    ) -> None:
        """Bind the distance-map 3D texture + ras/ijk matrices on the mapper.

        Ports the v1 monolith
        ``vtkSlicerBezierSurfaceRepresentation3D::CreateAndTransferDistanceMapTexture``
        and the ras/ijk matrix feed (severed by the T3-e rewrite): the
        flattened ``(u, v)`` quad samples the distance field through the
        mapper's ``sampler3D`` to paint the projected margin band
        (ADR-0025 §Context).  Without this only the wireframe grid +
        coloured border draw.

        Re-binds only when the distance-map volume changes (idempotent
        per ADR-0013 §3) and degrades safely: no distance map, no mapper
        ``SetDistanceMapTextureObject``, no renderer/GL context, or no
        ``TextureObject`` helper all leave the grid/border render intact
        and drop any stale texture from the mapper rather than sampling a
        volume that is gone.
        """
        mapper = self._resection_mapper_2d
        if mapper is None:
            return

        # Thread the wrapper's resection / uncertainty margins onto the 2D
        # mapper FIRST (ADR-0031): they are valid plan state independent of the
        # distance-map texture (the shader simply has no band to draw until a
        # texture is bound), so they must be set even on the no-distance-map /
        # deferred-GL paths below.  Mirrors BezierPlanningRepresentation.
        self._apply_resection_margins(mapper)

        bind = getattr(mapper, "SetDistanceMapTextureObject", None)
        if bind is None:
            return  # generic-mapper fallback (bare-VTK path) — no sampler3D

        already_bound = self._mapper_has_distance_map_texture(mapper)
        # Source the distance-map volume from the WRAPPER (ADR-0031), NOT the
        # data node / carrier — the distance map is a wrapper-owned input of
        # the resection plan (ADR-0014 §"Fourth layer").
        volume = _safe_call_getter(self._resection_plan_node, "GetDistanceMapVolumeNode")
        if volume is self._distance_map_volume and already_bound:
            return  # unchanged + already bound — idempotent (ADR-0013 §3)

        image_data = _safe_call_getter(volume, "GetImageData")
        if image_data is None:
            # No distance map (or no image data): drop any stale texture so
            # the mapper falls back to its no-distance-map path instead of
            # sampling a volume that is gone (the v1 warning branch).
            bind(None)
            self._distance_map_volume = volume
            return

        # The display node's TextureNumComps defaults to 0 (unset); fall back
        # to the image's own component count so both the upload and the
        # shader's uTextureNumComps branch (>2 selects the multi-channel
        # margin-band path) see the real value.
        num_comps = _safe_get_int(display_node, "GetTextureNumComps", default=0)
        if num_comps <= 0:
            num_comps = image_data.GetNumberOfScalarComponents()
        texture = self._create_distance_map_texture(image_data, num_comps)
        if texture is None:
            # The GL render window is not live yet (texture build deferred):
            # record the SOURCED (wrapper) volume so the sourced layer is
            # observable, but leave the texture unbound so a later update --
            # once the window exists -- retries the bind (``already_bound``
            # stays False, so the idempotency guard above does not short it).
            bind(None)
            self._distance_map_volume = volume
            return

        # Hand the texture to the mapper's vtkSmartPointer and drop the
        # local reference: the mapper is now its sole owner (no Python
        # attribute survives to outlive the C++ teardown).
        self._distance_map_volume = volume
        bind(texture)
        set_comps = getattr(mapper, "SetTextureNumComps", None)
        if set_comps is not None:
            set_comps(int(num_comps))
        self._apply_distance_map_matrices(volume, image_data)
        del texture

    def _mapper_has_distance_map_texture(self, mapper: Any) -> bool:
        """Whether the mapper currently holds a distance-map texture object.

        The idempotency probe: the texture object is owned solely by the
        mapper, so "already bound" is read off the mapper rather than a
        Python attribute (which is deliberately not retained).  Tolerant of
        the generic-mapper fallback that lacks the accessor.
        """
        getter = getattr(mapper, "GetDistanceMapTextureObject", None)
        if getter is None:
            return False
        try:
            return getter() is not None
        except Exception:  # pragma: no cover - defensive
            return False

    def _create_distance_map_texture(
        self, image_data: Any, num_comps: int
    ) -> Any | None:
        """Build the 3D distance-map texture object from ``image_data``.

        Mirrors the v1 ``CreateAndTransferDistanceMapTexture`` body: a
        ``vtkMultiTextureObjectHelper`` contexted on the renderer's
        OpenGL render window, clamp-to-border wrapping, linear filtering,
        and ``CreateSeq3DFromRaw`` from the volume's scalar pointer with
        the display node's ``TextureNumComps`` component count.  Returns
        ``None`` (caller drops the texture) when the helper class or the
        render window is unavailable.
        """
        helper_factory = _import_texture_object_helper()
        if helper_factory is None:
            return None
        render_window = self._render_window()
        if render_window is None:
            return None
        # This bind runs OUTSIDE the render pass (Representation.update()), so
        # the GL context must be made current explicitly -- and before the
        # window's first render there is no usable context at all (the
        # vtkOpenGLState texture-format table is empty, so the upload fails
        # noisily).  Probe with MakeCurrent/IsCurrent: not-current after the
        # attempt means not-yet-realized -> return None so the caller's
        # deferred path retries on a later update.  NOTE: GetInitialized() is
        # NOT a usable gate here -- a Qt-managed vtkGenericOpenGLRenderWindow
        # never sets it (Qt owns the context) and it would defer forever.
        make_current = getattr(render_window, "MakeCurrent", None)
        if make_current is not None:
            try:
                make_current()
            except Exception:  # pragma: no cover - defensive
                return None
        is_current = getattr(render_window, "IsCurrent", None)
        if is_current is not None and not is_current():
            return None
        # The display node's TextureNumComps defaults to 0 (unset) and the
        # workflow never writes it; a 0-component upload fails format
        # resolution deterministically.  The image knows its own count.
        if int(num_comps) <= 0:
            num_comps = image_data.GetNumberOfScalarComponents()
        try:
            texture = helper_factory()
            texture.SetContext(render_window)
            clamp = getattr(texture, "ClampToBorder", None)
            linear = getattr(texture, "Linear", None)
            if clamp is not None:
                texture.SetWrapS(clamp)
                texture.SetWrapT(clamp)
                texture.SetWrapR(clamp)
            if linear is not None:
                texture.SetMinificationFilter(linear)
                texture.SetMagnificationFilter(linear)
            texture.SetBorderColor(1000.0, 1000.0, 0.0, 0.0)
            dimensions = image_data.GetDimensions()
            # A VTK upload failure is NOT a Python exception: check the
            # boolean result.  Handing a failed texture to the caller binds
            # it, and the already-bound idempotency guard then blocks every
            # retry -- the resectogram stays white for the session.
            if not texture.CreateSeq3DFromRaw(
                dimensions[0],
                dimensions[1],
                dimensions[2],
                int(num_comps),
                vtk.VTK_FLOAT,
                image_data.GetScalarPointer(),
                0,
            ):
                return None
        except Exception:  # pragma: no cover - defensive
            return None
        return texture

    def _apply_distance_map_matrices(self, volume: Any, image_data: Any) -> None:
        """Push the ras→ijk + ijk→texture transposed matrices on the mapper.

        The v1 feed: the volume's RAS→IJK matrix (transposed for the
        shader's column-major uniform) maps the flattened quad's RAS
        position into the distance-map voxel grid, and a per-dimension
        ``1/N`` scale (transposed) normalises voxel indices into the
        ``[0, 1]`` texture domain the ``sampler3D`` reads.  No-op when the
        mapper lacks the transposed-matrix setters.
        """
        mapper = self._resection_mapper_2d
        set_ras = getattr(mapper, "SetRasToIjkMatrixT", None)
        set_ijk = getattr(mapper, "SetIjkToTextureMatrixT", None)
        if set_ras is None or set_ijk is None:
            return
        try:
            ras_to_ijk_t = vtk.vtkMatrix4x4()
            volume.GetRASToIJKMatrix(ras_to_ijk_t)
            ras_to_ijk_t.Transpose()

            dimensions = image_data.GetDimensions()
            scaling = vtk.vtkTransform()
            scaling.Scale(
                1.0 / dimensions[0], 1.0 / dimensions[1], 1.0 / dimensions[2]
            )
            ijk_to_texture_t = vtk.vtkMatrix4x4()
            scaling.GetTranspose(ijk_to_texture_t)
        except Exception:  # pragma: no cover - defensive
            return
        set_ras(ras_to_ijk_t)
        set_ijk(ijk_to_texture_t)

    def _render_window(self) -> Any | None:
        """Return the renderer's OpenGL render window, or ``None``.

        The ``vtkMultiTextureObjectHelper`` must be contexted on a live
        GL render window before ``CreateSeq3DFromRaw`` allocates the GPU
        texture.  Returns ``None`` (no renderer, or the renderer has no
        window yet) so the texture build is skipped until a window exists.
        """
        renderer = self._renderer
        if renderer is None or not hasattr(renderer, "GetRenderWindow"):
            return None
        try:
            return renderer.GetRenderWindow()
        except Exception:  # pragma: no cover - defensive
            return None

    def _compute_aspect_ratio(
        self, sampled: Any | None, flexible: bool
    ) -> tuple[float, float] | None:
        """Return ``{su, sv}`` via the Algorithm helper, or ``{1, 1}``.

        Not-flexible (or missing sampled surface) short-circuits to the
        isotropic ``{1, 1}`` — matching the v1 ``Ratio`` else-branch — so
        no ``vtkPoints`` is required for that path.
        """
        if not flexible or sampled is None:
            return (1.0, 1.0)

        helper = _import_aspect_ratio_helper()
        if helper is None:
            return (1.0, 1.0)

        samples_u, samples_v = _sampled_surface_resolution(sampled)
        ratio_out = [0.0, 0.0]
        try:
            helper.ComputeAspectRatio(sampled, samples_u, samples_v, True, ratio_out)
        except Exception:  # pragma: no cover - defensive
            return (1.0, 1.0)
        return (float(ratio_out[0]), float(ratio_out[1]))

    def _pose_overlay_camera(self, display_node: Any | None) -> None:
        """Pose the resectogram's private overlay camera.

        Reproduces the v1 ``ResectogramPlaneCenter`` pose: looks straight
        down the flattened quad from its centre, with ``MirrorDisplay``
        flipping the camera's z sign so the resectogram can be presented
        mirrored to a partner display (ADR-0025 §Context).  No-op when the
        camera or the quad source is unavailable (bare-VTK pytest path).
        """
        camera = self._resectogram_camera
        plane = self._bezier_plane
        if camera is None or plane is None:
            return
        if not hasattr(camera, "SetPosition"):
            return

        bounds = _quad_source_bounds(plane)
        if bounds is None:
            return

        mirror = _safe_get_bool(display_node, "GetMirrorDisplay", default=False)
        z_sign = 1.0 if mirror else -1.0

        center_x = (bounds[0] + bounds[1]) / 2.0
        center_y = (bounds[2] + bounds[3]) / 2.0
        center_z = z_sign * 100.0

        camera.SetPosition(center_x, center_y, center_z * 3.0)
        camera.SetFocalPoint(center_x, center_y, center_z)

    # ------------------------------------------------------------------ #
    # Gaussian-blur post-pass (ADR-0013 §6 — net-new v2.0 on/off toggle).
    # ------------------------------------------------------------------ #

    def _reconcile_blur_pass(self, display_node: Any | None) -> None:
        """Engage / disengage the Gaussian-blur post-pass per ``BlurEnabled``.

        The blur is a GPU render-pass on a renderer the Representation owns
        (ADR-0013 §6) — NOT pure-VTK math, so it stays here rather than in the
        Algorithm library (ADR-0015 §1, which has no GL context).  Live
        toggle: this runs on every ``update()`` so a ``BlurEnabled`` flip
        reconciles the pass without rebuilding the assembly — the
        ``vtkSetMacro(BlurEnabled, bool)`` ``Modified()`` advances the display
        node's MTime, which ``ResectogramPipeline.UpdatePipeline`` already
        keys on, so no new observer is needed.  No-op when VTK or the renderer
        is unavailable (bare-VTK pytest path).
        """
        renderer = self._renderer
        if renderer is None:
            return
        if not hasattr(renderer, "SetPass"):
            return

        enabled = _safe_get_bool(display_node, "GetBlurEnabled", default=False)
        radius = _safe_get_float(display_node, "GetBlurRadius", default=2.0)

        if enabled:
            self._attach_blur_pass(renderer, radius)
        else:
            self._detach_blur_pass(renderer)

    def _attach_blur_pass(self, renderer: Any, radius: float) -> None:
        """Set the ``vtkGaussianBlurPass`` on the resectogram view's renderer.

        The pass (wrapping a ``vtkRenderStepsPass`` delegate) blurs the strip
        the Representation already drew into ``renderer`` — no actor is moved,
        so the textured distance-map band + grid + border all blur together
        (relocating the actor onto a second renderer dropped the mapper's
        distance-map texture, leaving only the grid).  Idempotent: re-engaging
        reuses the same pass object and just re-sets it (cheap, and re-asserts
        the pass should ``qMRMLThreeDView`` have cleared it on a view edit).
        """
        if self._blur_pass is None:
            self._blur_pass = _make_gaussian_blur_pass()
            if self._blur_pass is None:
                return
        _apply_blur_radius(self._blur_pass, radius)
        try:
            renderer.SetPass(self._blur_pass)
        except Exception:  # pragma: no cover - defensive
            return
        self._blur_attached = True

    def _detach_blur_pass(self, renderer: Any) -> None:
        """Clear the blur pass off the renderer (restore the forward path).

        Leaves the non-blur appearance identical to a path that never engaged
        blur.  A no-op when blur was never engaged.
        """
        if not self._blur_attached:
            return
        if renderer is not None and hasattr(renderer, "SetPass"):
            try:
                renderer.SetPass(None)
            except Exception:  # pragma: no cover - defensive
                pass
        self._blur_attached = False


# --------------------------------------------------------------------------- #
# Helpers — small, self-contained per ADR-0013 §6 (Representations are
# independently importable).
# --------------------------------------------------------------------------- #


def _make_flattened_quad_source() -> Any | None:
    """Return the flattened-quad source feeding the 2D mapper.

    Prefers the ``vtkBezierSurfaceSource`` the v1 monolith uses for the
    ``BezierPlane`` (reachable in a Slicer process); falls back to a
    generic ``vtkPlaneSource`` so the skeleton stays importable.
    """
    factory = getattr(vtk, "vtkBezierSurfaceSource", None)
    if factory is None:
        try:  # pragma: no cover — exercised inside Slicer
            from slicer import vtkBezierSurfaceSource as factory  # type: ignore[no-redef]
        except Exception:
            factory = None
    if factory is not None:
        return factory()
    return vtk.vtkPlaneSource()


def _initialise_flattened_quad(plane: Any | None) -> None:
    """Tessellate the fixed flattened-domain quad on ``plane``.

    Feeds the planar 4x4 control grid + 20x20 resolution the v1 monolith
    poses ``BezierPlane`` from, then runs the source so its output carries
    the strip geometry the 2D mapper renders.  A no-op on the generic
    ``vtkPlaneSource`` fallback (which lacks ``SetControlPoints``); that
    source already emits a unit quad sufficient for the bare-VTK unit
    tests, which do not assert lit pixels.
    """
    if plane is None:
        return
    set_resolution = getattr(plane, "SetResolution", None)
    set_control_points = getattr(plane, "SetControlPoints", None)
    if set_resolution is None or set_control_points is None:
        return
    set_resolution(*_FLATTENED_QUAD_RESOLUTION)
    points = vtk.vtkPoints()
    for x, y, z in _FLATTENED_QUAD_CONTROL_GRID:
        points.InsertNextPoint(x, y, z)
    set_control_points(points)
    if hasattr(plane, "Update"):
        plane.Update()


def _quad_source_bounds(plane: Any) -> tuple | None:
    """Return the flattened quad's ``(xmin, xmax, ymin, ymax, zmin, zmax)``.

    Updates the source pipeline first (the v1 ``ResectogramPlaneCenter``
    reads ``BezierPlane->GetOutput()->GetBounds()``).  Returns ``None``
    defensively when the source does not expose a bounded output.
    """
    try:
        if hasattr(plane, "Update"):
            plane.Update()
        output = plane.GetOutput()
        bounds = output.GetBounds()
    except Exception:  # pragma: no cover - defensive
        return None
    if bounds is None or len(bounds) < 6:
        return None
    return tuple(float(b) for b in bounds)


def _make_resection_mapper_2d() -> Any:
    """Return the resectogram's 2D mapper instance, or raise.

    Resolves the relocated ``vtkOpenGLResection2DPolyDataMapper``
    (``LiverResections/VTKWidgets/``, reachable in a Slicer process).
    Raises ``RuntimeError`` when it is off the path — a real
    misconfiguration in production (ADR-0014 §3) must fail loudly rather
    than degrade to a shader-less generic mapper.  Bare-VTK unit tests
    (ADR-0008 §2) avoid this path by injecting a mapper instance instead.
    """
    factory = _import_wrapped_class("vtkOpenGLResection2DPolyDataMapper")
    if factory is None:
        raise RuntimeError(
            "vtkOpenGLResection2DPolyDataMapper is not reachable from the "
            "'vtk' or 'slicer' namespace.  It is a wrapped-C++ class relocated "
            "to LiverResections/VTKWidgets/ (ADR-0014 §3) and available only "
            "inside a launched Slicer with the module loaded.  Inject a mapper "
            "instance for bare-VTK unit tests (ADR-0008 §2)."
        )
    return factory()


def _make_gaussian_blur_pass() -> Any | None:
    """Return a ``vtkGaussianBlurPass`` wrapping the default forward pass.

    The standard VTK render-pass composition: a ``vtkRenderStepsPass`` (the
    default sequence a renderer runs) becomes the blur pass's delegate, so the
    resectogram strip is rendered first and the Gaussian blur is applied to
    the result.  Returns ``None`` when either render-pass class is unavailable
    (older VTK / bare environment), leaving the renderer on its default
    forward pass.
    """
    blur_factory = getattr(vtk, "vtkGaussianBlurPass", None)
    steps_factory = getattr(vtk, "vtkRenderStepsPass", None)
    if blur_factory is None or steps_factory is None:
        return None
    blur_pass = blur_factory()
    delegate = steps_factory()
    if hasattr(blur_pass, "SetDelegatePass"):
        blur_pass.SetDelegatePass(delegate)
    return blur_pass


def _apply_blur_radius(blur_pass: Any, radius: float) -> None:
    """Push the kernel extent onto the blur pass, if it is configurable.

    ``vtkGaussianBlurPass`` derives its kernel from the framebuffer it renders
    into and does not expose a public radius setter on every VTK version; the
    radius is consumed where the API allows it (best-effort) and otherwise
    ignored.  The load-bearing visible difference is the on/off toggle, not
    the radius — ``BlurRadius`` stays a dormant display-node field.
    """
    if blur_pass is None:
        return
    setter = getattr(blur_pass, "SetKernelRadius", None) or getattr(
        blur_pass, "SetRadius", None
    )
    if setter is not None:
        try:
            setter(float(radius))
        except Exception:  # pragma: no cover - defensive
            pass


def _import_wrapped_class(name: str) -> Any | None:
    """Return a wrapped VTK/Slicer class by name, or ``None``.

    Reachable from a Slicer process via the ``vtk`` or ``slicer``
    namespace; returns ``None`` in a bare-VTK pytest run where the wrapped
    class is not importable, so the calling branch degrades gracefully.
    """
    factory = getattr(vtk, name, None)
    if factory is not None:
        return factory
    try:  # pragma: no cover — exercised inside Slicer
        import slicer  # type: ignore[import-not-found]

        return getattr(slicer, name, None)
    except Exception:
        return None


def _import_aspect_ratio_helper() -> Any | None:
    """Return the ``vtkLiverResectogramAspectRatio`` helper class, or ``None``.

    Named seam (unit tests monkeypatch it to inject a stub helper) over
    the generic ``_import_wrapped_class``.
    """
    return _import_wrapped_class("vtkLiverResectogramAspectRatio")


def _import_texture_object_helper() -> Any | None:
    """Return the ``vtkMultiTextureObjectHelper`` class, or ``None``.

    The helper (``LiverMarkups/VTKWidgets/``) wraps ``vtkTextureObject``
    with the ``CreateSeq3DFromRaw`` upload the resectogram distance map
    needs.  A named seam over ``_import_wrapped_class`` for symmetry with
    the aspect-ratio helper.
    """
    return _import_wrapped_class("vtkMultiTextureObjectHelper")


def _safe_call_getter(node: Any | None, getter_name: str) -> Any | None:
    """Return ``node.<getter_name>()`` defensively, or ``None``.

    Tolerant of a missing node, a missing accessor (stub nodes in unit
    tests), or a raising getter.  Used to read the distance-map volume off
    the data node (``GetDistanceMapVolumeNode`` — the same source the
    scenario sets via ``SetDistanceMapVolumeNode``) and the volume's
    ``GetImageData``.
    """
    if node is None:
        return None
    getter = getattr(node, getter_name, None)
    if getter is None:
        return None
    try:
        return getter()
    except Exception:  # pragma: no cover - defensive
        return None


def _sampled_surface_resolution(sampled: Any) -> tuple[int, int]:
    """Best-effort ``(samplesU, samplesV)`` for a sampled surface grid.

    The v1 ``Ratio`` walks a 20×20 sampled grid; default to that when the
    points object does not carry an explicit resolution.
    """
    default = 20
    try:
        n = int(sampled.GetNumberOfPoints())
    except Exception:
        return (default, default)
    if n <= 0:
        return (default, default)
    side = int(round(n**0.5))
    if side * side == n:
        return (side, side)
    return (default, default)


def _read_control_points(data_node: Any | None) -> Any | None:
    """Return the data node's Bezier control points as a ``vtkPoints``.

    Reads the v2 ``vtkMRMLBezierSurfaceNode`` carrier's 16-point ``(4, 4)``
    control grid from the flat row-major vector ``GetControlGridVector``
    (length ``3 * 16`` = 48; ADR-0014 §"Fourth layer", ADR-0018 §1).  The v1
    markups control-point API is retired (ADR-0014 §"Dissolution"; ADR-0032
    §"Consequences").  Returns ``None`` defensively when the accessor is
    absent (stub data nodes), the grid is incomplete (< 16 defined points,
    mid-placement), or a read raises — the caller then keeps the fixed-quad
    fallback.
    """
    if data_node is None:
        return None
    grid_getter = getattr(data_node, "GetControlGridVector", None)
    if grid_getter is None:
        return None
    try:
        grid = grid_getter()
    except Exception:  # pragma: no cover - defensive
        return None
    if len(grid) != 16 * 3:  # the 16-point invariant (the only fed grid)
        return None
    points = vtk.vtkPoints()
    try:
        for index in range(16):
            base = index * 3
            points.InsertNextPoint(
                float(grid[base]), float(grid[base + 1]), float(grid[base + 2])
            )
    except Exception:  # pragma: no cover - defensive
        return None
    return points


def _surface_signature(sampled: Any | None, flexible: bool) -> tuple:
    """Return an idempotency signature for ``sampled`` + ``flexible``.

    For a ``vtkPoints`` surface the signature folds in the point count and
    the coordinate ``MTime`` (a stub points object that lacks ``GetMTime``
    falls back to ``id``), so a control-point edit that re-evaluates the
    surface bumps the signature and the refresh counter — the reactivity the
    pipeline-level ``Modified`` observer triggers a re-``update()`` for.
    """
    if sampled is None:
        return (None, bool(flexible))
    count_getter = getattr(sampled, "GetNumberOfPoints", None)
    mtime_getter = getattr(sampled, "GetMTime", None)
    count = None
    if count_getter is not None:
        try:
            count = int(count_getter())
        except Exception:  # pragma: no cover - defensive
            count = None
    if mtime_getter is not None:
        try:
            return (count, int(mtime_getter()), bool(flexible))
        except Exception:  # pragma: no cover - defensive
            pass
    return (id(sampled), count, bool(flexible))


def _safe_get_sampled_surface(data_node: Any | None) -> Any | None:
    """Return the sampled-surface ``vtkPoints`` off the data node, if any.

    Reads a small set of conventional accessors defensively; returns
    ``None`` when none are present (stub data nodes in unit tests).
    """
    if data_node is None:
        return None
    for name in ("GetSampledSurfacePoints", "GetSurfacePoints"):
        getter = getattr(data_node, name, None)
        if getter is None:
            continue
        try:
            value = getter()
        except Exception:  # pragma: no cover - defensive
            continue
        if value is not None:
            return value
    return None


def _safe_get_bool(node: Any | None, getter_name: str, *, default: bool) -> bool:
    if node is None:
        return default
    getter = getattr(node, getter_name, None)
    if getter is None:
        return default
    try:
        return bool(getter())
    except Exception:  # pragma: no cover - defensive
        return default


def _safe_get_int(node: Any | None, getter_name: str, *, default: int) -> int:
    if node is None:
        return default
    getter = getattr(node, getter_name, None)
    if getter is None:
        return default
    try:
        return int(getter())
    except Exception:  # pragma: no cover - defensive
        return default


def _safe_get_float(node: Any | None, getter_name: str, *, default: float) -> float:
    if node is None:
        return default
    getter = getattr(node, getter_name, None)
    if getter is None:
        return default
    try:
        return float(getter())
    except Exception:  # pragma: no cover - defensive
        return default

# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Representation active in ``(ResectionState=Planning, *)``.

Renders the 4×4 Bezier control grid (per ADR-0014 §3: corners 4 +
edges 8 + interior 4) and the fitted Bezier surface, driven by the
``vtkMRMLBezierSurfaceNode`` data node (geometry) and the paired
``vtkMRMLParametricSurfaceDisplayNode`` (decoration).

Scope of this skeleton
----------------------
The first T2.2 stack iteration ships the Representation class
constructed by ``LiverBezierSurfacePipeline.initialize()`` and
exercised by direct Python instantiation in unit tests.  Full
integration with Slicer's LayerDM framework happens at T2.6.

Surface mapper (T2-mapper-wiring)
---------------------------------
Per ADR-0014 §3 the four custom OpenGL mappers relocated from
``LiverMarkups/VTKWidgets/`` to ``LiverResections/VTKWidgets/``.  Inside a
launched Slicer this Representation drives the relocated, real
``vtkOpenGLBezierResectionPolyDataMapper`` over the tessellated Bernstein
patch built by ``vtkBezierSurfaceSource`` + ``vtkPolyDataNormals`` (the same
pipeline shape v1's ``vtkSlicerBezierSurfaceRepresentation3D`` assembled),
including the ``uvCoords`` the mapper's vertex shader reads and the
display-node colour / grid uniforms.

The custom mapper is injected, not silently discovered (ADR-0014 §3).  In
production the ``surface_mapper`` constructor argument is left ``None`` and
this Representation resolves the real wrapped class (raising loudly if it is
off the path — a real misconfiguration must NOT degrade to a shader-less
generic mapper).  The bare-VTK unit layer (ADR-0008 §2), where the wrapped
classes are unreachable, injects a generic ``vtkPolyDataMapper`` instance
explicitly; that source-less path renders the raw control mesh over a plain
``vtkPolyData`` so the structural / colour bookkeeping stays testable.

The RAS/IJK transform matrices and the distance-map 3D texture binding are
NOT wired here: the v2 ``vtkMRMLBezierSurfaceNode`` carries no distance-map
reference (the v1 markups node did), so there is no node-level source to
thread, and the fragment shader degrades gracefully when no ``distanceTexture``
is bound.  Those wait on a follow-on that gives the v2 node a distance-map
reference.

Renderer attachment
-------------------
The Representation's actors are added to the renderer when one is
supplied (``renderer`` constructor arg, or via ``SetRenderer()``).
When ``renderer`` is ``None`` — as in the unit-layer tests — the
actors exist but are not in any scene; ``update()`` still writes
their colour / opacity / input data from the display node.  This
matches the testability discipline of ADR-0008 §2 (unit-layer tests
have no Slicer / no view).

References
----------
* `ADR-0011`_ — SCT terminology dispatch.  The Pipeline reads the
  ``TerminologyEntry`` field off the display node and derives
  colour / label / badge from the SCT triple; at this stack
  iteration the Representation honours the pure-vector
  ``ResectionColor`` etc. fields, falling through to terminology-
  driven colour resolution when the terminology helper lands
  (TODO marker below).
* `ADR-0013`_ §6 — Representations as composable VTK pipelines.
* `ADR-0014`_ §3 — mapper relocation.

.. _ADR-0011: ../../../Docs/adr/0011-sct-terminology-dispatch.md
.. _ADR-0013: ../../../Docs/adr/0013-layerdm-pipeline-pattern.md
.. _ADR-0014: ../../../Docs/adr/0014-livermarkups-dissolution.md
"""

from __future__ import annotations

from typing import Any

import vtk


# --------------------------------------------------------------------------- #
# Default colour / opacity values — carried forward from the v1
# resection defaults so the Pipeline path starts from an identical
# visual baseline.  Display nodes carry these as float[3] in [0,1].
# --------------------------------------------------------------------------- #

DEFAULT_RESECTION_COLOR = (1.0, 1.0, 1.0)
DEFAULT_RESECTION_OPACITY = 1.0

# The relocated real surface mapper + the Bezier tessellation source (ADR-0014
# §3).  Both are wrapped-C++ classes reachable only inside a launched Slicer.
# In production (no injected mapper) ``_require_vtk_class`` resolves them or
# raises — there is no silent generic fallback.  The bare-VTK unit layer
# injects a generic mapper instead (ADR-0008 §2).
REAL_SURFACE_MAPPER_CLASS = "vtkOpenGLBezierResectionPolyDataMapper"
BEZIER_SURFACE_SOURCE_CLASS = "vtkBezierSurfaceSource"

# Tessellation resolution of the Bezier patch, carried forward verbatim from
# the v1 ``vtkSlicerBezierSurfaceRepresentation3D`` ctor (``SetResolution(20,
# 20)``) so the rendered surface matches the legacy visual baseline.
BEZIER_SURFACE_RESOLUTION = 20


class BezierPlanningRepresentation:
    """VTK assembly for the Planning-state Bezier surface.

    Constructor
    -----------
    ``BezierPlanningRepresentation(renderer=None, *, surface_mapper=None)``

    * ``renderer`` — the ``vtkRenderer`` the actors are added to.
      Optional; ``None`` is supported for unit tests (the actors
      exist but are unrendered).
    * ``surface_mapper`` — a custom-mapper INSTANCE (dependency
      injection, ADR-0014 §3).  ``None`` (production) resolves the real
      ``vtkOpenGLBezierResectionPolyDataMapper`` + ``vtkBezierSurfaceSource``
      pipeline, raising if either wrapped class is off the path.  An
      injected instance (bare-VTK unit layer, ADR-0008 §2) drives a
      source-less pipeline over a plain ``vtkPolyData``.

    Public methods
    --------------
    * ``update(display_node, data_node)`` — reads decoration from the
      display node, geometry from the data node, and reconciles the
      mapper / actor pair.  Tolerant of ``None`` arguments — turns the
      actor invisible in those cases.
    * ``cleanup()`` — detaches the actor from the renderer and releases
      the VTK pipeline.

    Grid rendering
    --------------
    The control grid is **not** rendered as a separate actor.  Per
    ADR-0014 §3 the ``vtkOpenGLBezierResectionPolyDataMapper`` overlays the
    grid as a fragment-shader feature on the *surface* mapper itself, drawing
    it procedurally via ``uGridDivisions`` / ``uGridThickness`` /
    ``uResectionGridColor`` uniforms tested against ``uvCoordsOutput``.  The
    Representation renders only the surface actor and plumbs the display node's
    ``Grid3DVisibility`` / ``GridDivisions`` / ``GridThickness`` /
    ``ResectionGridColor`` fields onto those uniforms in
    ``_apply_mapper_display_fields`` (gated on grid visibility, v1 parity).

    Introspection (used by unit tests)
    ----------------------------------
    * ``GetSurfaceActor()`` — the ``vtkActor`` rendering the surface,
      or ``None`` if VTK is not importable.
    * ``GetSurfaceMapper()`` — the surface mapper.
    * ``GetCurrentColor()`` — the (r, g, b) triple last written to the
      surface mapper's property.  Returns the default when VTK is
      absent or no ``update()`` has fired.
    * ``GetCurrentOpacity()`` — the opacity last written.
    """

    def __init__(
        self, renderer: Any | None = None, *, surface_mapper: Any | None = None
    ) -> None:
        self._renderer: Any | None = None

        # The VTK objects the Representation owns.  ``None`` in the
        # pure-Python testing path.  On the real path the surface is the
        # tessellated Bezier patch (``_surface_source`` -> ``_surface_normals``
        # -> mapper); on the bare-VTK fallback it is the raw control mesh
        # carried directly in ``_surface_polydata``.
        self._surface_source: Any | None = None
        self._surface_normals: Any | None = None
        self._surface_polydata: Any | None = None
        self._surface_mapper: Any | None = None
        self._surface_actor: Any | None = None

        # Last-written colour / opacity — exposed as a stub-friendly
        # introspection surface for unit tests that cannot construct
        # real VTK objects.
        self._current_color: tuple[float, float, float] = DEFAULT_RESECTION_COLOR
        self._current_opacity: float = DEFAULT_RESECTION_OPACITY

        # Memoised input — used by ``update()`` to detect whether the
        # control grid has been refreshed since the last call.
        self._last_grid_signature: tuple | None = None

        # Bookkeeping for unit tests: how many times the mapper input
        # has been refreshed.  Tests assert that a control-grid mutation
        # bumps this counter.
        self._input_refresh_count: int = 0

        # The orchestrating ``vtkMRMLResectionPlanNode`` wrapper, set by the
        # Pipeline via ``SetResectionPlanNode`` (ADR-0031).  It carries the
        # distance-map volume + the resection / uncertainty margins the
        # surface shader needs — path-specific inputs that live on the
        # wrapper, not the carrier.  ``None`` until the Pipeline wires it.
        self._resection_plan_node: Any | None = None

        # The cross-view locator node (ADR-0025).  The consumer reads its
        # picked world point + the display-node radius and drives the surface
        # mapper's ``uLocatorPosition`` / ``uLocatorRadius`` uniforms; ``None``
        # (or a zero radius) is the marker-off state.
        self._locator_node: Any | None = None

        self._build_vtk_pipeline(surface_mapper)

        if renderer is not None:
            self.SetRenderer(renderer)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def SetRenderer(self, renderer: Any | None) -> None:
        """Attach the Representation's actors to ``renderer``.

        Detaches from any previously-set renderer first.
        """
        if self._renderer is not None and self._renderer is not renderer:
            self._detach_actors(self._renderer)
        self._renderer = renderer
        if renderer is not None:
            self._attach_actors(renderer)

    def GetRenderer(self) -> Any | None:
        return self._renderer

    def SetResectionPlanNode(self, plan_node: Any | None) -> None:
        """Attach the orchestrating ``vtkMRMLResectionPlanNode`` wrapper.

        The Pipeline calls this before ``update()`` so the Representation can
        read the distance-map volume + the resection / uncertainty margins
        off the wrapper (ADR-0031) and thread them onto the real mapper.
        ``None`` clears it (the no-distance-map fallback).
        """
        self._resection_plan_node = plan_node

    def SetLocatorNode(self, locator_node: Any | None) -> None:
        """Attach the cross-view ``vtkMRMLLocatorNode`` (ADR-0025).

        The Pipeline resolves the scene's single locator node and calls this
        before ``update()`` so the consumer can drive the surface shader's
        locator marker.  ``None`` clears it (marker off).
        """
        self._locator_node = locator_node

    def update(
        self, display_node: Any | None, data_node: Any | None
    ) -> None:
        """Reconcile the actors against the current display + data nodes.

        Tolerant of ``None`` arguments — when either node is missing
        the actors fall back to invisible / default state instead of
        raising.
        """
        # No-op when VTK is unavailable; the colour / opacity stubs
        # below still update so the introspection helpers report
        # consistent values for tests that drive ``update()`` without
        # VTK.
        self._apply_display_node(display_node)
        self._apply_data_node(data_node)
        # Thread the wrapper's distance-map volume + margins onto the real
        # mapper (ADR-0031).  No-op on the generic fallback mapper / when no
        # plan node is wired.
        self._apply_resection_plan(self._resection_plan_node)
        # Drive the locator marker uniforms off the locator node (ADR-0025).
        self._apply_locator()

    def _apply_locator(self) -> None:
        """Thread the locator node's picked point + radius onto the mapper.

        Reads ``GetPickedPositionWorld`` off the ``vtkMRMLLocatorNode`` and the
        ``Radius`` off its display node, driving the surface mapper's
        ``uLocatorPosition`` / ``uLocatorRadius`` uniforms (ADR-0025 §Rendering).
        ``uLocatorRadius == 0`` is the marker-off state: used when no locator
        node is wired.  A no-op on the generic fallback mapper (the getattr
        guards) so the bare-VTK unit layer, which injects a plain
        ``vtkPolyDataMapper``, still constructs + updates.
        """
        mapper = self._surface_mapper
        if mapper is None:
            return
        set_position = getattr(mapper, "SetLocatorPosition", None)
        set_radius = getattr(mapper, "SetLocatorRadius", None)
        if set_position is None or set_radius is None:
            return  # generic fallback mapper — no locator uniforms

        node = self._locator_node
        if node is None:
            set_radius(0.0)  # marker off
            return

        position = node.GetPickedPositionWorld()
        set_position(float(position[0]), float(position[1]), float(position[2]))

        display_node = node.GetDisplayNode()
        radius = display_node.GetRadius() if display_node is not None else 0.0
        # Gesture-scoped marker: the display's base Visibility is the
        # switch (press shows, release hides); invisible pushes radius 0.
        visible = bool(display_node.GetVisibility()) if display_node is not None else False
        set_radius(float(radius) if visible else 0.0)

    def cleanup(self) -> None:
        """Detach actors from the renderer and drop the VTK pipeline."""
        if self._renderer is not None:
            self._detach_actors(self._renderer)
            self._renderer = None
        # Drop strong references so VTK can free the resources.
        self._surface_source = None
        self._surface_normals = None
        self._surface_polydata = None
        self._surface_mapper = None
        self._surface_actor = None
        self._resection_plan_node = None
        self._locator_node = None

    # ------------------------------------------------------------------ #
    # Introspection — used by the unit-layer tests
    # ------------------------------------------------------------------ #

    def GetSurfaceActor(self) -> Any | None:
        return self._surface_actor

    def GetSurfaceMapper(self) -> Any | None:
        return self._surface_mapper

    def GetSurfacePolyData(self) -> Any | None:
        """Return the surface polydata the mapper renders.

        On the real path this is the tessellated Bezier patch emitted by the
        normals filter (one point per resolution cell, with per-point normals
        and the ``uvCoords`` TCoords the mapper's vertex shader reads); on the
        bare-VTK fallback it is the raw control mesh.  ``None`` when VTK is
        absent or no ``update()`` has materialised geometry.
        """
        if self._surface_normals is not None:
            return self._surface_normals.GetOutput()
        return self._surface_polydata

    def GetCurrentColor(self) -> tuple[float, float, float]:
        return self._current_color

    def GetCurrentOpacity(self) -> float:
        return self._current_opacity

    def GetInputRefreshCount(self) -> int:
        return self._input_refresh_count

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _build_vtk_pipeline(self, surface_mapper: Any | None) -> None:
        """Construct the surface actor.

        Called from ``__init__``.

        Production path (``surface_mapper is None``): resolve the relocated
        ``vtkOpenGLBezierResectionPolyDataMapper`` + ``vtkBezierSurfaceSource``
        wrapped classes (ADR-0014 §3), raising loudly if either is off the path
        — a real misconfiguration must not silently render shader-less.  The
        mapper renders the tessellated Bernstein patch built by
        ``vtkBezierSurfaceSource`` + ``vtkPolyDataNormals`` — the same pipeline
        shape the v1 ``vtkSlicerBezierSurfaceRepresentation3D`` ctor assembled.
        The source emits the 2-component ``uvCoords`` (TCoords) the mapper's
        vertex shader reads; the grid is a fragment-shader feature on that
        mapper driven by ``GridDivisions`` / ``GridThickness`` /
        ``ResectionGridColor`` uniforms (plumbed in ``_apply_display_node``),
        NOT a separate actor.

        Injected path (``surface_mapper`` given, bare-VTK unit layer per
        ADR-0008 §2): the wrapped classes are off the path, so the caller
        injects a generic mapper instance.  It is fed a plain ``vtkPolyData``
        (source-less) carrying the raw control mesh, keeping the Representation
        constructible and the colour bookkeeping testable.
        """
        if surface_mapper is None:
            mapper_class = _require_vtk_class(REAL_SURFACE_MAPPER_CLASS)
            source_class = _require_vtk_class(BEZIER_SURFACE_SOURCE_CLASS)
            self._surface_source = source_class()
            self._surface_source.SetResolution(
                BEZIER_SURFACE_RESOLUTION, BEZIER_SURFACE_RESOLUTION
            )
            self._surface_normals = vtk.vtkPolyDataNormals()
            self._surface_normals.SetInputConnection(
                self._surface_source.GetOutputPort()
            )
            self._surface_mapper = mapper_class()
            self._surface_mapper.SetInputConnection(
                self._surface_normals.GetOutputPort()
            )
        else:
            self._surface_polydata = vtk.vtkPolyData()
            self._surface_mapper = surface_mapper
            self._surface_mapper.SetInputData(self._surface_polydata)

        self._surface_actor = vtk.vtkActor()
        self._surface_actor.SetMapper(self._surface_mapper)
        # Sensible defaults so a freshly-constructed Representation is
        # not visually surprising before the first ``update()``.
        self._surface_actor.GetProperty().SetColor(*DEFAULT_RESECTION_COLOR)
        self._surface_actor.GetProperty().SetOpacity(DEFAULT_RESECTION_OPACITY)

    def _attach_actors(self, renderer: Any) -> None:
        if self._surface_actor is not None and hasattr(renderer, "AddActor"):
            renderer.AddActor(self._surface_actor)

    def _detach_actors(self, renderer: Any) -> None:
        if self._surface_actor is not None and hasattr(
            renderer, "RemoveActor"
        ):
            try:
                renderer.RemoveActor(self._surface_actor)
            except Exception:  # pragma: no cover - defensive
                pass

    def _apply_display_node(self, display_node: Any | None) -> None:
        """Push decoration fields onto the actors.

        Tolerant of ``None`` / partial display nodes — falls back to
        defaults.
        """
        if display_node is None:
            color = DEFAULT_RESECTION_COLOR
            opacity = DEFAULT_RESECTION_OPACITY
        else:
            color_getter = getattr(display_node, "GetResectionColor", None)
            opacity_getter = getattr(
                display_node, "GetResectionOpacity", None
            )

            color = (
                _as_color_tuple(color_getter())
                if color_getter is not None
                else DEFAULT_RESECTION_COLOR
            )
            opacity = (
                float(opacity_getter())
                if opacity_getter is not None
                else DEFAULT_RESECTION_OPACITY
            )

        self._current_color = color
        self._current_opacity = opacity

        # TODO(ADR-0011): when the display node's TerminologyEntry is
        # populated, derive the colour / label / badge from the SCT
        # triple via the project's terminology utilities, overriding
        # the pure-vector ResectionColor above.  The terminology
        # helper API lands in T2.4; this Representation is the first
        # consumer.  Until then we honour the pure-vector fields,
        # which matches today's LiverResectionNode behaviour.

        if self._surface_actor is not None:
            prop = self._surface_actor.GetProperty()
            prop.SetColor(*color)
            prop.SetOpacity(opacity)

        # Drive the real mapper's fragment-shader uniforms from the display
        # node — porting vtkSlicerBezierSurfaceRepresentation3D::
        # UpdateBezierSurfaceDisplay.  The Bezier shader colours the surface
        # from ``uResectionColor`` / ``uResectionOpacity`` (not the actor
        # property) and draws the grid procedurally from ``uGridDivisions`` /
        # ``uGridThickness`` against the ``uvCoords``; grid visibility is a
        # shader feature on the surface mapper, NOT a separate actor.  No-op on
        # the generic fallback mapper (the getattr guards below).
        self._apply_mapper_display_fields(display_node, color, opacity)

    def _apply_data_node(self, data_node: Any | None) -> None:
        """Push the (Rows×Cols) control grid onto the surface mapper.

        Per ADR-0018 §1 the control-polygon shape is selected per node
        from ``(Rows, Cols) ∈ {(3, 3), (4, 4)}``; this method reads the
        shape from the node and walks the flat array accordingly so the
        Representation works on both shapes without assuming the 4×4
        default.
        """
        if data_node is None:
            return

        # Read ``GetControlGridVector`` (``const std::vector<double>&`` ->
        # a Python tuple), NOT ``GetControlGrid`` (``const double*``): VTK
        # cannot wrap a bare pointer return into an indexable buffer — from
        # Python it surfaces as an opaque pointer-string (``'_..._p_double'``)
        # whose ``[0]`` is the character ``'_'``, not a coordinate.  The
        # vector accessor round-trips cleanly.

        # Resolve (rows, cols) from the node — required to size the
        # iteration over the flat control-grid return; the array-length
        # check below catches any drift.
        rows = int(data_node.GetRows())
        cols = int(data_node.GetCols())
        control_count = rows * cols
        flat_length = 3 * control_count

        raw = data_node.GetControlGridVector()
        if raw is None:
            return

        # Materialise to a tuple of ``flat_length`` floats for
        # memoisation.  The wrapped sequence may not implement ``__hash__``;
        # tuple it for the signature comparison.  An ``IndexError`` /
        # ``TypeError`` here means the underlying buffer is shorter
        # than ``3 * Rows * Cols`` — a shape-drift bug worth surfacing,
        # not silently swallowing.
        try:
            flat = tuple(float(raw[i]) for i in range(flat_length))
        except (IndexError, TypeError):
            # Either the buffer is shorter than ``3 * Rows * Cols``
            # (shape drift — investigate the data node) or the VTK
            # Python wrapping returned a non-indexable pointer-like
            # object.  Defer the refresh either way; do not paper over.
            return

        signature = flat
        if signature == self._last_grid_signature:
            return  # no geometry change, no refresh
        self._last_grid_signature = signature
        self._input_refresh_count += 1

        points = _make_points_from_flat(flat, control_count)
        if self._surface_source is not None:
            # Real path: drive the Bezier surface source with the control
            # grid; it tessellates the Bernstein patch and emits the
            # ``uvCoords`` (TCoords) the mapper's vertex shader consumes.
            self._feed_bezier_source(points, rows, cols)
        else:
            # Bare-VTK fallback: the "surface" is the raw control mesh
            # (``control_count`` points + ``(rows-1)*(cols-1)`` quads) so the
            # generic mapper has something to draw and the colour bookkeeping
            # stays exercised in the unit layer.
            self._refresh_surface_polydata(points, rows, cols)

    def _feed_bezier_source(self, points: Any, rows: int, cols: int) -> None:
        """Push the control grid into the Bezier source and tessellate.

        The source iterates its control-point array row-major as
        ``i * cols + j`` (matching the node's row-major ``GetControlGrid``),
        so its control-point shape must equal the node's ``(rows, cols)`` for
        the indices to line up.  ``Update()`` materialises the patch + TCoords
        and the normals filter adds per-point normals, so ``GetSurfacePolyData``
        returns renderable geometry without a render pass — the same eager
        update the v1 representation did (``BezierSurfaceSource->Update()``).
        """
        source = self._surface_source
        if source is None:
            return
        set_ncp = getattr(source, "SetNumberOfControlPoints", None)
        if set_ncp is not None:
            set_ncp(rows, cols)
        source.SetControlPoints(points)
        source.Update()
        if self._surface_normals is not None:
            self._surface_normals.Update()

    def _apply_mapper_display_fields(
        self, display_node: Any | None, color: tuple, opacity: float
    ) -> None:
        """Push the display node's decoration onto the real mapper's uniforms.

        Ports ``vtkSlicerBezierSurfaceRepresentation3D::UpdateBezierSurfaceDisplay``.
        A no-op on the generic fallback mapper, which has no ``SetResection*``
        surface — there the colour rides on the actor property set by the
        caller.  Margin SCALARS (``SetResectionMargin`` / ``SetUncertaintyMargin``)
        are not pushed here — they are plan-wrapper state
        (``SafetyMargin_mm`` / ``RiskMargin_mm``, ADR-0031) threaded by
        ``_apply_resection_plan``; this method pushes only the display node's
        decoration (colours, flags, grid).
        """
        mapper = self._surface_mapper
        if mapper is None:
            return
        set_color = getattr(mapper, "SetResectionColor", None)
        if set_color is None:
            return  # generic fallback mapper — nothing to push to a shader
        set_color(float(color[0]), float(color[1]), float(color[2]))
        set_opacity = getattr(mapper, "SetResectionOpacity", None)
        if set_opacity is not None:
            set_opacity(float(opacity))

        if display_node is None:
            return

        _push_color3(
            mapper, "SetResectionGridColor",
            getattr(display_node, "GetResectionGridColor", None),
        )
        _push_color3(
            mapper, "SetResectionMarginColor",
            getattr(display_node, "GetResectionMarginColor", None),
        )
        _push_color3(
            mapper, "SetUncertaintyMarginColor",
            getattr(display_node, "GetUncertaintyMarginColor", None),
        )
        _push_bool(
            mapper, "SetResectionClipOut",
            getattr(display_node, "GetClipOut", None),
        )
        _push_bool(
            mapper, "SetInterpolatedMargins",
            getattr(display_node, "GetInterpolatedMargins", None),
        )

        # Grid divisions / thickness, gated on 3D-grid visibility exactly as
        # v1 did: when the grid is hidden, zero the divisions so the fragment
        # shader draws no grid lines.
        grid_visible = True
        vis_getter = getattr(display_node, "GetGrid3DVisibility", None)
        if vis_getter is not None:
            try:
                grid_visible = bool(vis_getter())
            except Exception:  # pragma: no cover - defensive
                grid_visible = True

        set_divisions = getattr(mapper, "SetGridDivisions", None)
        set_thickness = getattr(mapper, "SetGridThicknessFactor", None)
        if grid_visible:
            div_getter = getattr(display_node, "GetGridDivisions", None)
            thick_getter = getattr(display_node, "GetGridThickness", None)
            if set_divisions is not None and div_getter is not None:
                set_divisions(int(div_getter()))
            if set_thickness is not None and thick_getter is not None:
                set_thickness(float(thick_getter()))
        else:
            if set_divisions is not None:
                set_divisions(0)
            if set_thickness is not None:
                set_thickness(0.0)

    def _apply_resection_plan(self, plan_node: Any | None) -> None:
        """Thread the wrapper's distance map + margins onto the real mapper.

        Per ADR-0031 the distance-map volume + the resection / uncertainty
        margins are path-specific inputs carried by the
        ``vtkMRMLResectionPlanNode`` wrapper.  This ports v1's
        ``UpdateFromMRML`` distance-map block
        (``vtkSlicerBezierSurfaceRepresentation3D``): set the margins, and
        when a distance-map volume with image data is present, hand the image
        to the mapper (which builds + binds the 3D texture in C++ at render
        time — the ``void*`` upload cannot cross the Python wrap) and compute
        the RAS->IJK and IJK->texture matrices from the volume geometry.  When
        no distance map is wired, clear the image and reset the matrices to
        identity (the graceful no-distance-map fallback the shader supports).

        A no-op on the generic fallback mapper (the getattr guard).
        """
        mapper = self._surface_mapper
        if mapper is None or not hasattr(mapper, "SetDistanceMapImageData"):
            return  # generic fallback mapper — no distance-map shader surface

        # Margins are plan fields, meaningful independent of the distance map
        # (the shader simply has no band to draw without a bound texture).
        if plan_node is not None:
            safety = getattr(plan_node, "GetSafetyMargin_mm", None)
            risk = getattr(plan_node, "GetRiskMargin_mm", None)
            if safety is not None:
                mapper.SetResectionMargin(float(safety()))
            if risk is not None:
                mapper.SetUncertaintyMargin(float(risk()))

        volume = None
        if plan_node is not None:
            getter = getattr(plan_node, "GetDistanceMapVolumeNode", None)
            if getter is not None:
                volume = getter()

        image = volume.GetImageData() if volume is not None else None
        if image is None:
            # No distance map: drop the texture source and reset the
            # transforms so MRML state and GL state cannot diverge.
            mapper.SetDistanceMapImageData(None)
            mapper.SetRasToIjkMatrix(_identity_matrix())
            mapper.SetIjkToTextureMatrix(_identity_matrix())
            return

        mapper.SetDistanceMapImageData(image)

        # RAS->IJK straight off the volume; the mapper transposes internally.
        ras_to_ijk = vtk.vtkMatrix4x4()
        volume.GetRASToIJKMatrix(ras_to_ijk)
        mapper.SetRasToIjkMatrix(ras_to_ijk)

        # IJK->texture is the 1/dimensions scaling (texture coords are
        # normalised), matching v1's scaling transform.
        dimensions = image.GetDimensions()
        scaling = vtk.vtkTransform()
        scaling.Scale(
            1.0 / dimensions[0] if dimensions[0] else 1.0,
            1.0 / dimensions[1] if dimensions[1] else 1.0,
            1.0 / dimensions[2] if dimensions[2] else 1.0,
        )
        ijk_to_texture = vtk.vtkMatrix4x4()
        scaling.GetMatrix(ijk_to_texture)
        mapper.SetIjkToTextureMatrix(ijk_to_texture)

    def _refresh_surface_polydata(self, points: Any, rows: int, cols: int) -> None:
        polydata = self._surface_polydata
        if polydata is None:
            return
        polydata.SetPoints(points)

        cells = vtk.vtkCellArray()
        # Connect the (rows×cols) control mesh into
        # ((rows-1)×(cols-1)) quads.  ``ids`` indexes the flat
        # ``0..control_count-1`` point array laid out row-major in
        # (u, v).
        for v in range(rows - 1):
            for u in range(cols - 1):
                quad = vtk.vtkQuad()
                quad.GetPointIds().SetId(0, v * cols + u)
                quad.GetPointIds().SetId(1, v * cols + (u + 1))
                quad.GetPointIds().SetId(2, (v + 1) * cols + (u + 1))
                quad.GetPointIds().SetId(3, (v + 1) * cols + u)
                cells.InsertNextCell(quad)
        polydata.SetPolys(cells)
        polydata.Modified()

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _identity_matrix() -> Any:
    """A fresh 4x4 identity ``vtkMatrix4x4`` (reset transform for the
    no-distance-map fallback)."""
    m = vtk.vtkMatrix4x4()
    m.Identity()
    return m


def _require_vtk_class(name: str) -> Any:
    """Resolve a wrapped-C++ VTKWidgets class by name from ``slicer``, or raise.

    The relocated mapper + the Bezier surface source are wrapped into Slicer's
    ``slicer`` namespace (ADR-0014 §3).  Raises ``RuntimeError`` when a class is
    absent — a real misconfiguration in production must fail loudly rather than
    degrade to a shader-less generic mapper.  Bare-VTK unit tests (ADR-0008 §2)
    avoid this path by injecting a mapper instance instead.
    """
    try:
        import slicer
    except ImportError:
        slicer = None
    cls = getattr(slicer, name, None) if slicer is not None else None
    if cls is None:
        raise RuntimeError(
            f"{name} is not reachable from the 'slicer' namespace. "
            "It is a wrapped-C++ class relocated to LiverResections/VTKWidgets/ "
            "(ADR-0014 §3) and available only inside a launched Slicer with the "
            "module loaded.  Inject a mapper instance for bare-VTK unit tests "
            "(ADR-0008 §2)."
        )
    return cls


def _push_color3(mapper: Any, setter_name: str, getter: Any | None) -> None:
    """Read a 3-vector from ``getter`` and push it to ``mapper.<setter_name>``.

    No-op when either the getter or the mapper setter is absent (the generic
    fallback mapper) — keeps the plumbing tolerant of partial display nodes.
    """
    if getter is None:
        return
    setter = getattr(mapper, setter_name, None)
    if setter is None:
        return
    try:
        c = getter()
        setter(float(c[0]), float(c[1]), float(c[2]))
    except Exception:  # pragma: no cover - defensive
        pass


def _push_bool(mapper: Any, setter_name: str, getter: Any | None) -> None:
    """Read a bool from ``getter`` and push it to ``mapper.<setter_name>``."""
    if getter is None:
        return
    setter = getattr(mapper, setter_name, None)
    if setter is None:
        return
    try:
        setter(bool(getter()))
    except Exception:  # pragma: no cover - defensive
        pass


def _as_color_tuple(raw: Any) -> tuple[float, float, float]:
    """Coerce a colour accessor's return value to ``(r, g, b)``.

    Accepts list, tuple, or VTK-wrapped sequence; clamps to [0, 1] and
    falls back to white on parse failure.
    """
    try:
        r = max(0.0, min(1.0, float(raw[0])))
        g = max(0.0, min(1.0, float(raw[1])))
        b = max(0.0, min(1.0, float(raw[2])))
        return (r, g, b)
    except Exception:
        return DEFAULT_RESECTION_COLOR


def _make_points_from_flat(flat: tuple, control_count: int) -> Any:
    """Build a ``vtkPoints`` from a row-major control grid.

    ``flat`` has length ``3 * control_count``; the resulting
    ``vtkPoints`` has ``control_count`` points (9 for 3×3, 16 for 4×4
    per ADR-0018 §1).
    """
    points = vtk.vtkPoints()
    points.SetNumberOfPoints(control_count)
    for i in range(control_count):
        x = flat[i * 3 + 0]
        y = flat[i * 3 + 1]
        z = flat[i * 3 + 2]
        points.SetPoint(i, x, y, z)
    return points

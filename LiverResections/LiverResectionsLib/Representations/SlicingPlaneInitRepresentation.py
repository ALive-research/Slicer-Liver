# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Representation active in ``(ResectionState=Init, InitMode=SlicingPlane)``.

Renders the surgeon-placed *SlicingPlane* initialisation geometry per
ADR-0014 §2: the two init points that seed the plane and the live
shader contour that visualises the plane on the liver surface.  Driven
by the ``vtkMRMLBezierSurfaceNode`` data node (geometry:
``GetSlicingPlaneOrigin``, ``GetSlicingPlaneNormal``,
``GetSlicingPlaneInitPoint(0|1)``, target liver mesh:
``GetTargetModelNode``) and the paired
``vtkMRMLParametricSurfaceDisplayNode`` (decoration: ``GetResectionColor``,
``GetResectionOpacity``).

Scope of this skeleton — T2.2 stack iteration 2
-----------------------------------------------
This is the second T2.2 iteration: the *SlicingPlaneInit*
Representation slot on ``LiverBezierSurfacePipeline``.  The first
iteration landed ``BezierPlanningRepresentation``; this iteration
mirrors its pattern (soft VTK gate, ``update`` /
``cleanup`` lifecycle, idempotency memo, introspection helpers for
unit tests).

Three pieces of geometry per ADR-0014 §2
----------------------------------------
1. **Two control-point markers** — small ``vtkSphereSource`` glyphs,
   transformed to ``GetSlicingPlaneInitPoint(0)`` and
   ``GetSlicingPlaneInitPoint(1)``.  Full opacity, takes the display
   node's ``ResectionColor``.
2. **The live shader contour** — v1 parity: no plane square is ever
   rendered.  The whole target liver mesh renders through the
   relocated ``vtkOpenGLSlicingContourPolyDataMapper`` whose fragment
   shader keeps only a band of ``CONTOUR_THICKNESS_WORLD`` world units
   around the plane and discards everything else — the visible band on
   the liver surface IS the plane's visualisation.  Shader-based per
   the maintainer's requirement (no CPU cutter substitute).  Driven by
   ``GetSlicingPlaneOrigin`` / ``GetSlicingPlaneNormal`` pushed as the
   mapper's world-space plane uniforms, and fed the target mesh from
   ``GetTargetModelNode`` (ADR-0014 §1).
3. **Ring on the target liver mesh** — produced on the Init->Planning
   commit boundary by ``run_ring_extraction``: the Pipeline's
   ``commit()`` resolves the weakref'd target liver mesh
   (ADR-0014 §1, ``vtkMRMLBezierSurfaceNode::GetTargetModelNode()``)
   and hands it here, where a ``vtkLiverPlaneRingExtractor`` is fed
   the target mesh + origin + normal to produce the ordered
   intersection ring.  Per-frame visual feedback during Init is the
   shader's job; the discrete CPU ring is one-shot per resection
   (ADR-0019).

Contour-mapper injection seam
-----------------------------
Per ADR-0014 §3 the contour mapper is injected, not silently
discovered (mirrors ``FlattenedSurfaceRepresentation``'s
``resection_mapper_2d`` seam): an injected instance (the bare-VTK unit
layer, ADR-0008 §2) is used as-is; ``None`` (production) resolves the
wrapped ``vtkOpenGLSlicingContourPolyDataMapper``.  Unlike the
resectogram's resolve-or-raise, an unreachable wrapping degrades
gracefully — the contour is a decoration, so the Representation simply
renders the markers only (the bare unit layer must still construct).

Renderer attachment
-------------------
Same discipline as ``BezierPlanningRepresentation``: all actors are
created on ``__init__`` (when VTK is importable); ``SetRenderer``
attaches them; ``cleanup`` detaches and drops strong refs.  When
``renderer`` is ``None`` (the unit-test path) the actors exist but
are unrendered.  Per ADR-0008 §2 unit-layer tests have no Slicer /
no view.

No grid actor
-------------
Unlike ``BezierPlanningRepresentation`` (which lives in
``state=Planning``), this Representation does NOT render the Bezier
4×4 control grid.  In ``state=Init`` there is no fitted surface yet —
only the plane definition.  The grid is a shader feature on the
Planning surface mapper per ADR-0014 §3 and is irrelevant here.

References
----------
* `ADR-0013`_ §4 — Pipeline pattern, state-conditional dispatch.
* `ADR-0013`_ §6 — Representations as composable VTK pipelines.
* `ADR-0014`_ §2 — names this Representation.
* `ADR-0014`_ §4 — init data persists as read-only audit data after
  Init→Planning; the data node's
  ``GetSlicingPlaneOrigin`` / ``GetSlicingPlaneNormal`` /
  ``GetSlicingPlaneInitPoint(i)`` accessors honour that contract.

.. _ADR-0013: ../../../Docs/adr/0013-layerdm-pipeline-pattern.md
.. _ADR-0014: ../../../Docs/adr/0014-livermarkups-dissolution.md
"""

from __future__ import annotations

from typing import Any

import vtk


# --------------------------------------------------------------------------- #
# Default colour / opacity values — carried forward from the v1
# resection defaults so the Init-state visual baseline matches the
# Planning Representation's defaults.
# --------------------------------------------------------------------------- #

DEFAULT_RESECTION_COLOR = (1.0, 1.0, 1.0)
DEFAULT_RESECTION_OPACITY = 1.0

# Marker-sphere radius (world units).  Sized for the typical liver
# bounding box (~150 mm) so the markers are visible without occluding
# the plane.  A perceptual rather than physical choice; refine when
# the design rationale of ADR-0009 §3 is applied.
MARKER_RADIUS = 6.0  # matches the Planning control-point sphere radius

#: Base + grabbed colours for the Init handles -- the SAME visual grammar
#: as the Planning control points (white handles; the grabbed one turns
#: the grab green).  Values mirror ControlPolygonPipeline's handle default
#: and HALO_GRAB_COLOR (kept in sync by the interaction pins).
HANDLE_BASE_COLOR = (1.0, 1.0, 1.0)
HANDLE_GRAB_COLOR = (0.3, 1.0, 0.4)

# Half-width (world units) of the shader contour band kept around the
# slicing plane — the v1 band half-width.  The fragment shader discards
# every liver fragment farther than this from the plane, so the
# surviving band on the liver surface IS the plane's visualisation.
CONTOUR_THICKNESS_WORLD = 2.0


class SlicingPlaneInitRepresentation:
    """VTK assembly for the (Init, SlicingPlane) state.

    Constructor
    -----------
    ``SlicingPlaneInitRepresentation(renderer=None, *,
    slicing_contour_mapper=None)``

    * ``renderer`` — the ``vtkRenderer`` the actors are added to.
      Optional; ``None`` is supported for unit tests (the actors
      exist but are unrendered).
    * ``slicing_contour_mapper`` — the shader contour mapper INSTANCE
      (dependency injection per ADR-0014 §3).  ``None`` (production)
      resolves the wrapped ``vtkOpenGLSlicingContourPolyDataMapper``;
      when the wrapping is off the path (the bare-VTK unit layer) the
      Representation degrades to markers only — no contour actor.

    Public methods
    --------------
    * ``update(display_node, data_node)`` — reads decoration from the
      display node, plane / init-point geometry from the data node,
      and reconciles mappers / actors.  Tolerant of ``None`` arguments.
    * ``cleanup()`` — detaches actors from the renderer and releases
      the VTK pipeline.

    Introspection (used by unit tests)
    ----------------------------------
    * ``GetMarkerActor(i)`` — the ``vtkActor`` rendering init point
      ``i`` (0 or 1).  ``None`` when VTK is not importable.
    * ``GetContourActor()`` — the ``vtkActor`` rendering the shader
      contour band (``None`` when no contour mapper is available).
    * ``GetContourMapper()`` — the contour mapper instance.
    * ``GetCurrentColor()`` — last colour written.
    * ``GetCurrentOpacity()`` — last opacity written.
    * ``GetInputRefreshCount()`` — counter bumped each time the contour
      / marker geometry is rebuilt from a *changed* data node.
    """

    def __init__(
        self,
        renderer: Any | None = None,
        *,
        slicing_contour_mapper: Any | None = None,
    ) -> None:
        self._renderer: Any | None = None

        # VTK objects owned by the Representation.  ``None`` in the
        # pure-Python testing path.
        self._marker_sources: list[Any] = []  # vtkSphereSource × 2
        self._marker_mappers: list[Any] = []  # vtkPolyDataMapper × 2
        self._marker_actors: list[Any] = []  # vtkActor × 2

        # Shader contour band on the liver surface — ``None`` when the
        # wrapped mapper is unreachable (bare unit layer): markers only.
        self._contour_mapper: Any | None = None
        self._contour_actor: Any | None = None

        # Last target model fed to the contour mapper — memoised so the
        # mesh connection is pushed once per target, not per update.
        self._contour_target: Any | None = None

        # Last-written colour / opacity — exposed for stub-friendly
        # introspection.
        self._current_color: tuple[float, float, float] = DEFAULT_RESECTION_COLOR
        self._current_opacity: float = DEFAULT_RESECTION_OPACITY

        # Idempotency memo on (origin, normal, init0, init1, target id).
        # The Pipeline already memoises (state, initMode, dataMTime,
        # displayMTime); this second memo guards against redundant VTK
        # pipeline rebuilds when the Pipeline's coarse-grained key
        # changes but the SlicingPlane subset of the data node is
        # unchanged.
        self._last_input_signature: tuple | None = None

        # Bookkeeping for unit tests — bumped on a real refresh.
        self._input_refresh_count: int = 0

        # Last data node seen by ``update`` — the on-commit ring
        # extraction reads the SlicingPlane geometry off it
        # (``run_ring_extraction``).
        self._data_node: Any | None = None

        # The extracted intersection ring (``vtkPolyData``) produced on
        # the Init->Planning commit, or ``None`` before commit.
        self._ring_polydata: Any | None = None

        # Index of the Init handle currently grabbed (the control-point
        # grab-colour cue), or ``None``.
        self._grabbed_handle: int | None = None

        self._build_vtk_pipeline(slicing_contour_mapper)

        if renderer is not None:
            self.SetRenderer(renderer)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def SetRenderer(self, renderer: Any | None) -> None:
        """Attach the Representation's actors to ``renderer``."""
        if self._renderer is not None and self._renderer is not renderer:
            self._detach_actors(self._renderer)
        self._renderer = renderer
        if renderer is not None:
            self._attach_actors(renderer)

    def GetRenderer(self) -> Any | None:
        return self._renderer

    def update(
        self, display_node: Any | None, data_node: Any | None
    ) -> None:
        """Reconcile the actors against the current display + data nodes.

        Tolerant of ``None`` arguments — falls back to default colour /
        opacity without raising.
        """
        self._apply_display_node(display_node)
        self._apply_data_node(data_node)

    def SetGrabbedHandle(self, index: int | None) -> None:
        """Colour handle ``index`` with the grab cue (``None`` restores).

        The SAME visual grammar as the Planning control points: the
        grabbed handle turns the grab green, the rest stay white.
        """
        self._grabbed_handle = index
        for i, actor in enumerate(self._marker_actors):
            color = HANDLE_GRAB_COLOR if i == index else HANDLE_BASE_COLOR
            actor.GetProperty().SetColor(*color)

    def run_ring_extraction(self, target_model: Any | None) -> Any | None:
        """Extract the plane/target intersection ring on the commit boundary.

        Consume site for ``TODO(T2-target-mesh-weakref)``: the Pipeline's
        ``commit()`` resolves the weakref'd target organ model
        (ADR-0014 §1, ``GetTargetModelNode()``) and hands it here.  This
        constructs a ``vtkLiverPlaneRingExtractor``, feeds it the target
        mesh's ``vtkPolyData`` plus the SlicingPlane origin + normal off
        the data node, and stores the resulting ordered ring.  Returns
        the ring ``vtkPolyData`` (or ``None`` when extraction cannot run).
        """
        if target_model is None:
            return None
        polydata = _model_polydata(target_model)
        if polydata is None:
            return None

        origin = _read_vec3(self._data_node, "GetSlicingPlaneOrigin")
        normal = _read_vec3(self._data_node, "GetSlicingPlaneNormal")
        if origin is None or normal is None:
            return None

        extractor_class = _resolve_extractor_class("vtkLiverPlaneRingExtractor")
        if extractor_class is None:
            return None
        extractor = extractor_class()
        extractor.SetInputData(polydata)
        extractor.SetOrigin(*origin)
        extractor.SetNormal(*normal)
        extractor.Update()
        self._ring_polydata = extractor.GetOutput()
        return self._ring_polydata

    def GetRingPolyData(self) -> Any | None:
        """The intersection ring produced by the last
        ``run_ring_extraction`` — or ``None`` before commit."""
        return self._ring_polydata

    def cleanup(self) -> None:
        """Detach actors from the renderer and drop the VTK pipeline.

        Detach FIRST, then drop the references — releasing the handles
        before removal would strand the actors on the renderer.
        """
        if self._renderer is not None:
            self._detach_actors(self._renderer)
            self._renderer = None
        # Drop strong refs so VTK can free the resources.
        self._marker_sources = []
        self._marker_mappers = []
        self._marker_actors = []
        self._contour_mapper = None
        self._contour_actor = None
        self._contour_target = None

    # ------------------------------------------------------------------ #
    # Introspection — used by the unit-layer tests
    # ------------------------------------------------------------------ #

    def GetMarkerActor(self, index: int) -> Any | None:
        if 0 <= index < len(self._marker_actors):
            return self._marker_actors[index]
        return None

    def GetMarkerSource(self, index: int) -> Any | None:
        if 0 <= index < len(self._marker_sources):
            return self._marker_sources[index]
        return None

    def GetContourActor(self) -> Any | None:
        return self._contour_actor

    def GetContourMapper(self) -> Any | None:
        return self._contour_mapper

    def GetCurrentColor(self) -> tuple[float, float, float]:
        return self._current_color

    def GetCurrentOpacity(self) -> float:
        return self._current_opacity

    def GetInputRefreshCount(self) -> int:
        return self._input_refresh_count

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _build_vtk_pipeline(self, slicing_contour_mapper: Any | None) -> None:
        """Construct the marker actors + the shader contour actor.

        Called from ``__init__``.  The contour mapper is injected, not
        silently discovered (ADR-0014 §3): an injected instance (the
        bare-VTK unit layer) is used as-is; ``None`` (production)
        resolves the wrapped ``vtkOpenGLSlicingContourPolyDataMapper``.
        When neither is available the contour actor is skipped — the
        Representation degrades to markers only.
        """
        # Two marker spheres — one per init point.
        for _ in range(2):
            sphere = vtk.vtkSphereSource()
            sphere.SetRadius(MARKER_RADIUS)
            sphere.SetPhiResolution(12)
            sphere.SetThetaResolution(12)
            sphere.SetCenter(0.0, 0.0, 0.0)
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(sphere.GetOutputPort())
            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            actor.GetProperty().SetColor(*HANDLE_BASE_COLOR)
            actor.GetProperty().SetOpacity(DEFAULT_RESECTION_OPACITY)
            self._marker_sources.append(sphere)
            self._marker_mappers.append(mapper)
            self._marker_actors.append(actor)

        # Live shader contour — the plane's visualisation (v1 parity:
        # the whole liver mesh renders through the contour mapper whose
        # fragment shader keeps only the band around the plane; no
        # plane square is ever rendered).
        self._contour_mapper = (
            slicing_contour_mapper
            if slicing_contour_mapper is not None
            else _resolve_slicing_contour_mapper()
        )
        if self._contour_mapper is not None:
            self._contour_mapper.SetContourThickness(CONTOUR_THICKNESS_WORLD)
            self._contour_mapper.SetContourVisibility(False)
            self._contour_actor = vtk.vtkActor()
            self._contour_actor.SetMapper(self._contour_mapper)

    def _attach_actors(self, renderer: Any) -> None:
        if not hasattr(renderer, "AddActor"):
            return
        for actor in self._marker_actors:
            renderer.AddActor(actor)
        if self._contour_actor is not None:
            renderer.AddActor(self._contour_actor)

    def _detach_actors(self, renderer: Any) -> None:
        if not hasattr(renderer, "RemoveActor"):
            return
        for actor in self._marker_actors:
            try:
                renderer.RemoveActor(actor)
            except Exception:  # pragma: no cover — defensive
                pass
        if self._contour_actor is not None:
            try:
                renderer.RemoveActor(self._contour_actor)
            except Exception:  # pragma: no cover — defensive
                pass

    def _apply_display_node(self, display_node: Any | None) -> None:
        """Record decoration fields; markers keep the HANDLE grammar.

        The init handles follow the Planning control-point visual grammar
        (white base / grab green at full opacity, the
        ``vtkMRMLControlPolygonDisplayNode`` defaults) — NOT the resection
        decoration.  ``ResectionColor``/``Opacity`` are still read into the
        introspection accessors for the commit-time surface, but a mid-drag
        ``update()`` must never squash the grab cue with them.
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
        # populated, derive the colour from the SCT triple via the
        # project's terminology utilities (overriding the pure-vector
        # ResectionColor above).  The terminology helper API lands in
        # T2.4; this Representation is among its first consumers.

        for i, actor in enumerate(self._marker_actors):
            prop = actor.GetProperty()
            handle_color = (
                HANDLE_GRAB_COLOR
                if i == self._grabbed_handle
                else HANDLE_BASE_COLOR
            )
            prop.SetColor(*handle_color)
            prop.SetOpacity(1.0)

    def _apply_data_node(self, data_node: Any | None) -> None:
        """Pull plane + init-point geometry and the target model off the
        data node and push them through the marker sphere centres + the
        shader contour mapper.
        """
        if data_node is None:
            return
        self._data_node = data_node

        origin = _read_vec3(data_node, "GetSlicingPlaneOrigin")
        normal = _read_vec3(data_node, "GetSlicingPlaneNormal")
        init0 = _read_init_point(data_node, 0)
        init1 = _read_init_point(data_node, 1)
        target = data_node.GetTargetModelNode()

        if origin is None or normal is None or init0 is None or init1 is None:
            # Any missing field is treated as "not enough geometry to
            # render yet" — the actors retain their previous geometry
            # (so a transient ``Modified()`` mid-update doesn't blank
            # the view) and the refresh counter does not advance.
            return

        grid = data_node.GetControlGridVector()
        grid_digest = tuple(grid[:48]) if grid is not None and len(grid) >= 48 else None
        signature = (
            origin,
            normal,
            init0,
            init1,
            id(target) if target is not None else None,
            # The seeded 4x4 grid drives the surface PREVIEW; without it
            # in the memo a drag-release re-fit would never refresh.
            grid_digest,
        )
        if signature == self._last_input_signature:
            return  # no geometry change, no refresh
        self._last_input_signature = signature
        self._input_refresh_count += 1

        self._refresh_marker_positions(init0, init1)
        self._refresh_contour(origin, normal, target)

    def _refresh_marker_positions(
        self,
        init0: tuple[float, float, float],
        init1: tuple[float, float, float],
    ) -> None:
        if len(self._marker_sources) < 2:
            return
        self._marker_sources[0].SetCenter(*init0)
        self._marker_sources[1].SetCenter(*init1)

    def _refresh_contour(
        self,
        origin: tuple[float, float, float],
        normal: tuple[float, float, float],
        target: Any | None,
    ) -> None:
        """Drive the shader contour from origin + normal + target mesh.

        The contour mapper renders the WHOLE target liver mesh; its
        fragment shader keeps only the ``CONTOUR_THICKNESS_WORLD`` band
        around the plane.  Without a target (or with an empty target
        mesh) there is nothing to band — the contour is hidden.  The
        mesh connection is fed once per target (memoised on
        ``self._contour_target``); the plane uniforms are pushed on
        every refresh.  The carrier's stored normal is unit-length and
        the shader normalises anyway, so no renormalisation here.
        """
        if self._contour_mapper is None:
            return

        polydata = target.GetPolyData() if target is not None else None
        if polydata is None or polydata.GetNumberOfPoints() == 0:
            self._contour_mapper.SetContourVisibility(False)
            return

        if target is not self._contour_target:
            self._contour_mapper.SetInputConnection(
                target.GetPolyDataConnection()
            )
            self._contour_target = target

        self._contour_mapper.SetPlanePositionWorld(*origin)
        self._contour_mapper.SetPlaneNormalWorld(*normal)
        self._contour_mapper.SetContourVisibility(True)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


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


def _read_vec3(
    node: Any, getter_name: str
) -> tuple[float, float, float] | None:
    """Read a 3-tuple accessor (e.g. ``GetSlicingPlaneOrigin``) off ``node``.

    Returns ``None`` when the accessor is missing or its return value
    cannot be coerced to three floats.
    """
    getter = getattr(node, getter_name, None)
    if getter is None:
        return None
    try:
        raw = getter()
    except Exception:  # pragma: no cover — defensive
        return None
    if raw is None:
        return None
    try:
        return (float(raw[0]), float(raw[1]), float(raw[2]))
    except Exception:
        return None


def _read_init_point(
    node: Any, index: int
) -> tuple[float, float, float] | None:
    """Read ``GetSlicingPlaneInitPoint(index)`` off ``node``."""
    getter = getattr(node, "GetSlicingPlaneInitPoint", None)
    if getter is None:
        return None
    try:
        raw = getter(index)
    except Exception:  # pragma: no cover — defensive
        return None
    if raw is None:
        return None
    try:
        return (float(raw[0]), float(raw[1]), float(raw[2]))
    except Exception:
        return None


def _resolve_slicing_contour_mapper() -> Any | None:
    """Return a wrapped ``vtkOpenGLSlicingContourPolyDataMapper`` instance,
    or ``None``.

    The contour mapper lives in ``LiverResections/VTKWidgets/`` and is
    exposed only on the module's VTKWidgets Python wrapping (ADR-0014 §3)
    — NOT on the ``slicer`` or ``vtk`` namespaces.  Lazily imported so
    this module stays importable where the wrapping is off the path (the
    bare-VTK unit layer); the contour is a decoration, so absence
    degrades to a markers-only Representation rather than raising.
    """
    try:
        import vtkSlicerLiverResectionsModuleVTKWidgetsPython as widgets
    except ImportError:
        return None
    factory = getattr(widgets, "vtkOpenGLSlicingContourPolyDataMapper", None)
    if factory is None:
        return None
    return factory()


def _resolve_extractor_class(name: str) -> Any | None:
    """Resolve a wrapped-C++ ring-extractor class by name, or ``None``.

    The ring extractors live in ``LiverResections/Algorithm/`` and are exposed
    only on the module's Algorithm Python wrapping (ADR-0014 §3) — NOT on the
    ``slicer`` or ``vtk`` namespaces.  Lazily imported so this module stays
    importable where the wrapping is off the path (the bare-VTK unit layer);
    the caller then declines to extract rather than raising.
    """
    try:
        import vtkSlicerLiverResectionsModuleAlgorithmPython as algorithm
    except ImportError:
        return None
    return getattr(algorithm, name, None)


def _model_polydata(target_model: Any | None) -> Any | None:
    """Return the ``vtkPolyData`` carried by a model node, or the
    argument itself when it is already a ``vtkPolyData``.

    The weakref'd target (ADR-0014 §1) is a ``vtkMRMLModelNode``; its
    surface mesh is reached via ``GetPolyData()``.  Tolerating a bare
    ``vtkPolyData`` keeps the consume site usable from lower-level
    tests that hand in a mesh directly.
    """
    if target_model is None:
        return None
    getter = getattr(target_model, "GetPolyData", None)
    if getter is None:
        # Already a vtkPolyData (or a mesh-shaped object).
        return target_model
    try:
        return getter()
    except Exception:  # pragma: no cover — defensive
        return None

# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Representation active in ``(ResectionState=Init, InitMode=SlicingPlane)``.

Renders the surgeon-placed *SlicingPlane* initialisation geometry per
ADR-0014 §2: the two init points that seed the plane and the plane
visualisation itself.  Driven by the ``vtkMRMLBezierSurfaceNode`` data
node (geometry: ``GetSlicingPlaneOrigin``, ``GetSlicingPlaneNormal``,
``GetSlicingPlaneInitPoint(0|1)``) and the paired
``vtkMRMLBezierSurfaceDisplayNode`` (decoration: ``GetResectionColor``,
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
2. **The plane visualisation** — a ``vtkPlaneSource`` driven by
   ``GetSlicingPlaneOrigin`` (centre) + ``GetSlicingPlaneNormal``
   (orientation).  Sized to a square ~2× the distance between the two
   init points, centred on the plane origin.  Reduced opacity (the
   display node's ``ResectionOpacity`` is multiplied by
   ``PLANE_OPACITY_FACTOR`` so the plane reads as a transparent
   reference surface and does not occlude the underlying liver).
3. **Ring on the target liver mesh** — DEFERRED.  The
   ``vtkLiverPlaneRingExtractor`` consumer needs the target liver
   mesh, which is reached through a (not-yet-landed) weakref on
   ``vtkMRMLBezierSurfaceNode``.  See
   ``TODO(T2-target-mesh-weakref)`` in ``_build_vtk_pipeline`` for
   the exact wiring once the data node gains a
   ``TargetOrganModelNode`` reference per ADR-0014 §1.

Mapper relocation
-----------------
Per ADR-0014 §3 the relocated ``vtkOpenGLSlicingContourPolyDataMapper``
is the eventual replacement for the plane visualisation mapper used
here.  Today the relocation has not landed; this skeleton uses the
generic ``vtkPolyDataMapper`` + ``vtkActor`` pair.  Marked with
``TODO(T2-mapper-relocation)`` at the construction point so the swap
is mechanical.

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

# --------------------------------------------------------------------------- #
# VTK is a soft dependency — mirrors the pattern in
# ``BezierPlanningRepresentation``.  When ``vtk`` is not importable the
# Representation can still be constructed; ``update()`` then writes the
# colour / opacity stubs without building any VTK pipeline, which is
# enough for the smoke-level unit tests.  See ADR-0008 §2.
# --------------------------------------------------------------------------- #

try:  # pragma: no cover — exercised inside Slicer / when VTK is available
    import vtk

    _HAS_VTK = True
except ImportError:  # pragma: no cover — pure-Python path
    vtk = None  # type: ignore[assignment]
    _HAS_VTK = False


# --------------------------------------------------------------------------- #
# Default colour / opacity values — mirror the legacy
# ``vtkMRMLLiverResectionNode`` constructor so the Init-state visual
# baseline matches the Planning Representation's defaults.
# --------------------------------------------------------------------------- #

DEFAULT_RESECTION_COLOR = (1.0, 1.0, 1.0)
DEFAULT_RESECTION_OPACITY = 1.0

# Marker-sphere radius (world units).  Sized for the typical liver
# bounding box (~150 mm) so the markers are visible without occluding
# the plane.  A perceptual rather than physical choice; refine when
# the design rationale of ADR-0009 §3 is applied.
MARKER_RADIUS = 1.5

# The plane is drawn at a reduced opacity relative to the display
# node's ``ResectionOpacity`` so it reads as a transparent reference
# surface and does not occlude the underlying liver in 3D views.
PLANE_OPACITY_FACTOR = 0.35

# Size factor — the plane is rendered as a square whose side length is
# ``PLANE_SIZE_FACTOR`` × the distance between the two init points,
# centred on the plane origin.  Provides a "sensible size" per the
# T2.2 iteration-2 brief.  Refined when ADR-0009 §3's UX rationale is
# applied to this Representation.
PLANE_SIZE_FACTOR = 2.0

# Fallback plane half-extent (world units) used when the two init
# points are coincident — without it the plane visualisation would
# collapse to a degenerate point.
PLANE_FALLBACK_HALF_EXTENT = 25.0


class SlicingPlaneInitRepresentation:
    """VTK assembly for the (Init, SlicingPlane) state.

    Constructor
    -----------
    ``SlicingPlaneInitRepresentation(renderer=None)``

    * ``renderer`` — the ``vtkRenderer`` the actors are added to.
      Optional; ``None`` is supported for unit tests (the actors
      exist but are unrendered).

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
    * ``GetPlaneActor()`` — the ``vtkActor`` rendering the plane
      visualisation.
    * ``GetPlaneSource()`` — the underlying ``vtkPlaneSource``.
    * ``GetCurrentColor()`` — last colour written.
    * ``GetCurrentOpacity()`` — last opacity written.
    * ``GetInputRefreshCount()`` — counter bumped each time the plane
      / marker geometry is rebuilt from a *changed* data node.
    """

    def __init__(self, renderer: Any | None = None) -> None:
        self._renderer: Any | None = None

        # VTK objects owned by the Representation.  ``None`` in the
        # pure-Python testing path.
        self._marker_sources: list[Any] = []  # vtkSphereSource × 2
        self._marker_mappers: list[Any] = []  # vtkPolyDataMapper × 2
        self._marker_actors: list[Any] = []  # vtkActor × 2

        self._plane_source: Any | None = None
        self._plane_mapper: Any | None = None
        self._plane_actor: Any | None = None

        # Last-written colour / opacity — exposed for stub-friendly
        # introspection.
        self._current_color: tuple[float, float, float] = DEFAULT_RESECTION_COLOR
        self._current_opacity: float = DEFAULT_RESECTION_OPACITY

        # Idempotency memo on (origin, normal, init0, init1, displayMTime).
        # The Pipeline already memoises (state, initMode, dataMTime,
        # displayMTime); this second memo guards against redundant VTK
        # pipeline rebuilds when the Pipeline's coarse-grained key
        # changes but the SlicingPlane subset of the data node is
        # unchanged.
        self._last_input_signature: tuple | None = None

        # Bookkeeping for unit tests — bumped on a real refresh.
        self._input_refresh_count: int = 0

        # TODO(T2-mapper-relocation): swap the generic
        # ``vtk.vtkPolyDataMapper`` used for the plane visualisation
        # with ``vtkOpenGLSlicingContourPolyDataMapper`` once the four
        # custom mappers are relocated from ``LiverMarkups/VTKWidgets/``
        # to ``LiverResections/VTKWidgets/`` per ADR-0014 §3.  The
        # public API of this Representation does not change — only
        # the plane mapper's concrete type.
        #
        # TODO(T2-target-mesh-weakref): once ``vtkMRMLBezierSurfaceNode``
        # gains a weakref to its ``TargetOrganModelNode`` (per ADR-0014
        # §1's data-node design), construct a ``vtkLiverPlaneRing
        # Extractor``, feed it the target mesh + origin + normal, and
        # render its polyline output as a ring actor here.  The
        # extractor already exists at
        # ``LiverResections/Algorithm/vtkLiverPlaneRingExtractor.{h,cxx}``;
        # only the data-node hook is missing.  Without the target
        # mesh, this Representation cannot construct the ring; the
        # ring slot is therefore omitted entirely in this iteration
        # rather than left as a dangling empty actor.
        if _HAS_VTK:
            self._build_vtk_pipeline()

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

    def cleanup(self) -> None:
        """Detach actors from the renderer and drop the VTK pipeline."""
        if self._renderer is not None:
            self._detach_actors(self._renderer)
            self._renderer = None
        # Drop strong refs so VTK can free the resources.
        self._marker_sources = []
        self._marker_mappers = []
        self._marker_actors = []
        self._plane_source = None
        self._plane_mapper = None
        self._plane_actor = None

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

    def GetPlaneActor(self) -> Any | None:
        return self._plane_actor

    def GetPlaneMapper(self) -> Any | None:
        return self._plane_mapper

    def GetPlaneSource(self) -> Any | None:
        return self._plane_source

    def GetCurrentColor(self) -> tuple[float, float, float]:
        return self._current_color

    def GetCurrentOpacity(self) -> float:
        return self._current_opacity

    def GetInputRefreshCount(self) -> int:
        return self._input_refresh_count

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _build_vtk_pipeline(self) -> None:
        """Construct the marker + plane actors.

        Called from ``__init__`` only when ``vtk`` is importable.
        """
        assert vtk is not None  # for the type-checker — gated by _HAS_VTK

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
            actor.GetProperty().SetColor(*DEFAULT_RESECTION_COLOR)
            actor.GetProperty().SetOpacity(DEFAULT_RESECTION_OPACITY)
            self._marker_sources.append(sphere)
            self._marker_mappers.append(mapper)
            self._marker_actors.append(actor)

        # Plane visualisation.
        #
        # TODO(T2-mapper-relocation): once the four custom mappers land
        # in ``LiverResections/VTKWidgets/`` per ADR-0014 §3, swap the
        # ``vtk.vtkPolyDataMapper`` below for
        # ``vtkOpenGLSlicingContourPolyDataMapper``.  That mapper carries
        # the slicing-contour shader treatment that the legacy
        # LiverMarkups path used; today we use the generic mapper so
        # the Representation remains independent of the mapper
        # relocation work.
        self._plane_source = vtk.vtkPlaneSource()
        self._plane_mapper = vtk.vtkPolyDataMapper()
        self._plane_mapper.SetInputConnection(
            self._plane_source.GetOutputPort()
        )
        self._plane_actor = vtk.vtkActor()
        self._plane_actor.SetMapper(self._plane_mapper)
        self._plane_actor.GetProperty().SetColor(*DEFAULT_RESECTION_COLOR)
        self._plane_actor.GetProperty().SetOpacity(
            DEFAULT_RESECTION_OPACITY * PLANE_OPACITY_FACTOR
        )

    def _attach_actors(self, renderer: Any) -> None:
        if not hasattr(renderer, "AddActor"):
            return
        for actor in self._marker_actors:
            renderer.AddActor(actor)
        if self._plane_actor is not None:
            renderer.AddActor(self._plane_actor)

    def _detach_actors(self, renderer: Any) -> None:
        if not hasattr(renderer, "RemoveActor"):
            return
        for actor in self._marker_actors:
            try:
                renderer.RemoveActor(actor)
            except Exception:  # pragma: no cover — defensive
                pass
        if self._plane_actor is not None:
            try:
                renderer.RemoveActor(self._plane_actor)
            except Exception:  # pragma: no cover — defensive
                pass

    def _apply_display_node(self, display_node: Any | None) -> None:
        """Push decoration fields onto the actors.

        Marker actors take the colour at full opacity; the plane actor
        takes the colour at reduced opacity (``PLANE_OPACITY_FACTOR``).
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

        for actor in self._marker_actors:
            prop = actor.GetProperty()
            prop.SetColor(*color)
            prop.SetOpacity(opacity)
        if self._plane_actor is not None:
            prop = self._plane_actor.GetProperty()
            prop.SetColor(*color)
            prop.SetOpacity(opacity * PLANE_OPACITY_FACTOR)

    def _apply_data_node(self, data_node: Any | None) -> None:
        """Pull plane + init-point geometry off the data node and
        push it through the marker sphere centres + plane source.
        """
        if data_node is None:
            return

        origin = _read_vec3(data_node, "GetSlicingPlaneOrigin")
        normal = _read_vec3(data_node, "GetSlicingPlaneNormal")
        init0 = _read_init_point(data_node, 0)
        init1 = _read_init_point(data_node, 1)

        if origin is None or normal is None or init0 is None or init1 is None:
            # Any missing field is treated as "not enough geometry to
            # render yet" — the actors retain their previous geometry
            # (so a transient ``Modified()`` mid-update doesn't blank
            # the view) and the refresh counter does not advance.
            return

        signature = (origin, normal, init0, init1)
        if signature == self._last_input_signature:
            return  # no geometry change, no refresh
        self._last_input_signature = signature
        self._input_refresh_count += 1

        if not _HAS_VTK:
            return

        self._refresh_marker_positions(init0, init1)
        self._refresh_plane(origin, normal, init0, init1)

    def _refresh_marker_positions(
        self,
        init0: tuple[float, float, float],
        init1: tuple[float, float, float],
    ) -> None:
        if len(self._marker_sources) < 2:
            return
        self._marker_sources[0].SetCenter(*init0)
        self._marker_sources[1].SetCenter(*init1)

    def _refresh_plane(
        self,
        origin: tuple[float, float, float],
        normal: tuple[float, float, float],
        init0: tuple[float, float, float],
        init1: tuple[float, float, float],
    ) -> None:
        """Drive the ``vtkPlaneSource`` from origin + normal.

        Builds a square plane of side ``PLANE_SIZE_FACTOR × |init0 -
        init1|``, centred on ``origin``, oriented to ``normal``.
        Falls back to ``PLANE_FALLBACK_HALF_EXTENT`` when the two init
        points are coincident (would otherwise yield a degenerate
        plane).
        """
        if self._plane_source is None:
            return
        assert vtk is not None

        plane = self._plane_source

        # Half-extent: half the side length.
        d = _distance(init0, init1)
        half = max(
            0.5 * PLANE_SIZE_FACTOR * d, PLANE_FALLBACK_HALF_EXTENT
        )

        # Construct a basis (u, v) in the plane.  vtkMath::Perpendiculars
        # returns two unit vectors perpendicular to ``normal`` and to
        # each other.  Falls back to a manual orthonormal pair if the
        # helper is unavailable.
        n = _normalise(normal)
        if n is None:
            return
        u, v = _plane_basis(n)

        cx, cy, cz = origin
        plane.SetOrigin(
            cx - half * u[0] - half * v[0],
            cy - half * u[1] - half * v[1],
            cz - half * u[2] - half * v[2],
        )
        plane.SetPoint1(
            cx + half * u[0] - half * v[0],
            cy + half * u[1] - half * v[1],
            cz + half * u[2] - half * v[2],
        )
        plane.SetPoint2(
            cx - half * u[0] + half * v[0],
            cy - half * u[1] + half * v[1],
            cz - half * u[2] + half * v[2],
        )
        plane.SetCenter(cx, cy, cz)
        plane.SetNormal(n[0], n[1], n[2])


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


def _distance(
    a: tuple[float, float, float], b: tuple[float, float, float]
) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    dz = a[2] - b[2]
    return (dx * dx + dy * dy + dz * dz) ** 0.5


def _normalise(
    v: tuple[float, float, float],
) -> tuple[float, float, float] | None:
    n = (v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) ** 0.5
    if n == 0.0:
        return None
    return (v[0] / n, v[1] / n, v[2] / n)


def _plane_basis(
    n: tuple[float, float, float],
) -> tuple[
    tuple[float, float, float], tuple[float, float, float]
]:
    """Return two unit vectors (u, v) perpendicular to ``n`` and to each other.

    Used to lay out the ``vtkPlaneSource`` corners around the plane
    origin.  Pure Python (no VTK dependency) so the basis is
    computable in the no-VTK testing path.
    """
    # Pick a non-parallel reference axis.
    ax, ay, az = abs(n[0]), abs(n[1]), abs(n[2])
    if ax <= ay and ax <= az:
        ref = (1.0, 0.0, 0.0)
    elif ay <= ax and ay <= az:
        ref = (0.0, 1.0, 0.0)
    else:
        ref = (0.0, 0.0, 1.0)

    # u = normalise(ref × n)
    u_raw = (
        ref[1] * n[2] - ref[2] * n[1],
        ref[2] * n[0] - ref[0] * n[2],
        ref[0] * n[1] - ref[1] * n[0],
    )
    u = _normalise(u_raw) or (1.0, 0.0, 0.0)

    # v = n × u (already unit by construction)
    v = (
        n[1] * u[2] - n[2] * u[1],
        n[2] * u[0] - n[0] * u[2],
        n[0] * u[1] - n[1] * u[0],
    )
    return u, v

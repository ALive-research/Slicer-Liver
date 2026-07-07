# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Representation active in ``(ResectionState=Init, InitMode=DistanceSpheroid)``.

Renders the geometry that supports the **DistanceSpheroid** init mode
(per ADR-0014 §2) — the alternative initialisation path where the
surgeon places a variable number of seed points (two or more, per the
data node's contract) that imply an axis-aligned spheroid (``Center``,
``RadiusX``, ``RadiusY``, ``RadiusZ``); the planning surface is then
the intersection of that spheroid with the target liver mesh.

Scope of this iteration (T2.2 iteration 3)
------------------------------------------
This is the third iteration of the T2.2 stack.  The Representation
class is constructed by ``LiverBezierSurfacePipeline.initialize()``
and exercised by direct Python instantiation in unit tests.  Full
integration with Slicer's LayerDM framework happens at T2.6.

Three pieces of geometry per ADR-0014 §2:

1. **Variable-N control-point markers** — small sphere actors at each
   surgeon-placed init point.  The actor list grows / shrinks
   dynamically as ``GetNumberOfDistanceSpheroidInitPoints()`` changes.
2. **Spheroid visualisation** — a translucent axis-aligned spheroid
   (``vtkParametricEllipsoid`` with ``XRadius`` / ``YRadius`` /
   ``ZRadius`` translated to the spheroid centre).  Axis-aligned only,
   per ``vtkLiverSpheroidRingExtractor``'s header — general-orientation
   rotation is deferred and tracked as a future task.
3. **Ring on target mesh** — produced on the Init->Planning commit
   boundary by ``run_ring_extraction``: the Pipeline's ``commit()``
   resolves the weakref'd target liver mesh
   (ADR-0014 §1, ``vtkMRMLBezierSurfaceNode::GetTargetModelNode()``)
   and hands it here, where a ``vtkLiverSpheroidRingExtractor`` is fed
   the target mesh + ``Center`` + ``Radii`` to produce the ordered
   intersection ring.  Per-frame visual feedback during Init is the
   shader's job; the discrete CPU ring is one-shot per resection
   (ADR-0019).

Per ADR-0014 §3 the four custom OpenGL mappers — including
``vtkOpenGLDistanceContourPolyDataMapper`` — relocate from
``LiverMarkups/VTKWidgets/`` to ``LiverResections/VTKWidgets/``.  The
relocation has not landed yet; this Representation uses the generic
``vtkPolyDataMapper`` + ``vtkActor`` pair until the relocation
completes, at which point the spheroid mapper field flips to
``vtkOpenGLDistanceContourPolyDataMapper`` *without changing the
Representation's public API*.  Marked with
``TODO(T2-mapper-relocation)`` at the construction point.

Renderer attachment
-------------------
Mirrors ``BezierPlanningRepresentation``: when ``renderer`` is
provided, all actors are added to it; ``None`` is supported for unit
tests (the actors exist but are unrendered).  Per ADR-0008 §2 unit-
layer tests have no Slicer / no view.

References
----------
* `ADR-0011`_ — SCT terminology dispatch.
* `ADR-0013`_ §6 — Representations as composable VTK pipelines.
* `ADR-0014`_ §2 — names the DistanceSpheroidInit Representation.
* `ADR-0014`_ §3 — mapper relocation.
* `ADR-0014`_ §4 — data-node read-only-after-Planning rules + the
  accessor surface this Representation reads.

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

# Small visual radius for the surgeon-placed seed markers.  Independent
# of the spheroid radii (which come from the data node).  Picked to be
# visible at typical liver-scale RAS coordinates; the eventual
# decoration plumbing on the display node may expose this as a tunable.
DEFAULT_MARKER_RADIUS = 2.0


class DistanceSpheroidInitRepresentation:
    """VTK assembly for the Init-state, DistanceSpheroid-mode geometry.

    Constructor
    -----------
    ``DistanceSpheroidInitRepresentation(renderer=None)``

    * ``renderer`` — the ``vtkRenderer`` the actors are added to.
      Optional; ``None`` is supported for unit tests (the actors
      exist but are unrendered).

    Public methods
    --------------
    * ``update(display_node, data_node)`` — reads decoration from the
      display node, geometry from the data node, and reconciles the
      marker / spheroid mapper-actor pairs.  Tolerant of ``None``
      arguments — turns the actors invisible / no-op in those cases.
    * ``cleanup()`` — detaches all actors from the renderer and
      releases the VTK pipeline.

    Marker handling
    ---------------
    The number of surgeon-placed init points is variable (two or
    more, per ``vtkMRMLBezierSurfaceNode``'s contract).  Marker
    actors are tracked in a Python list — when the count grows on a
    later ``update()``, new actors are constructed (and attached to
    the current renderer if one is set); when the count shrinks, the
    superfluous actors are detached and their strong refs dropped so
    VTK can free the resources.

    Ring rendering
    --------------
    Ring rendering is **deferred** — see the module docstring and
    ``TODO(T2-target-mesh-weakref)`` in ``_apply_data_node``.

    Introspection (used by unit tests)
    ----------------------------------
    * ``GetMarkerActors()`` — list of ``vtkActor`` rendering the
      seed markers, or an empty list if VTK is not importable.
    * ``GetSpheroidActor()`` — the ``vtkActor`` rendering the
      translucent spheroid, or ``None``.
    * ``GetSpheroidMapper()`` — the spheroid mapper.
    * ``GetParametricEllipsoid()`` — the ``vtkParametricEllipsoid``
      driving the spheroid mapper (so tests can read its ``XRadius``
      / ``YRadius`` / ``ZRadius`` back).
    * ``GetCurrentColor()`` — the (r, g, b) triple last written.
    * ``GetCurrentOpacity()`` — the opacity last written.
    * ``GetInputRefreshCount()`` — bumps each time ``update()``
      observes a change in (Center, Radii, init points, displayMTime).
    """

    def __init__(self, renderer: Any | None = None) -> None:
        self._renderer: Any | None = None

        # The VTK pipeline objects the Representation owns.  ``None`` in
        # the pure-Python testing path.
        self._parametric_ellipsoid: Any | None = None
        self._parametric_function_source: Any | None = None
        self._spheroid_polydata_filter: Any | None = None
        self._spheroid_mapper: Any | None = None
        self._spheroid_actor: Any | None = None

        # Marker actors — list grows / shrinks with
        # GetNumberOfDistanceSpheroidInitPoints().  Each entry is a
        # (sphere_source, mapper, actor) triple so the geometry can be
        # mutated in place (centre + radius) without rebuilding the
        # pipeline.
        self._marker_entries: list[tuple[Any, Any, Any]] = []

        # Last-written colour / opacity — exposed as a stub-friendly
        # introspection surface for unit tests that cannot construct
        # real VTK objects.
        self._current_color: tuple[float, float, float] = DEFAULT_RESECTION_COLOR
        self._current_opacity: float = DEFAULT_RESECTION_OPACITY

        # Memoised input signature — see ``_apply_data_node`` for the
        # invariant.
        self._last_input_signature: tuple | None = None

        # Bookkeeping for unit tests: how many times the spheroid /
        # marker pipeline has been refreshed.  Tests assert that a
        # data-node mutation bumps this counter.
        self._input_refresh_count: int = 0

        # Last data node seen by ``update`` — the on-commit ring
        # extraction reads the spheroid geometry off it
        # (``run_ring_extraction``).
        self._data_node: Any | None = None

        # The extracted intersection ring (``vtkPolyData``) produced on
        # the Init->Planning commit, or ``None`` before commit.
        self._ring_polydata: Any | None = None

        # TODO(T2-mapper-relocation): swap ``vtk.vtkPolyDataMapper`` for
        # ``vtkOpenGLDistanceContourPolyDataMapper`` once the four
        # custom mappers are relocated from ``LiverMarkups/VTKWidgets/``
        # to ``LiverResections/VTKWidgets/`` per ADR-0014 §3.  The
        # public API of this Representation does not change — only the
        # spheroid mapper field's concrete type.
        self._build_vtk_pipeline()

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

    def update(
        self, display_node: Any | None, data_node: Any | None
    ) -> None:
        """Reconcile the actors against the current display + data nodes.

        Tolerant of ``None`` arguments — when either node is missing
        the actors fall back to invisible / default state instead of
        raising.
        """
        self._apply_display_node(display_node)
        self._apply_data_node(data_node)

    def run_ring_extraction(self, target_model: Any | None) -> Any | None:
        """Extract the spheroid/target intersection ring on the commit boundary.

        Consume site for ``TODO(T2-target-mesh-weakref)``: the Pipeline's
        ``commit()`` resolves the weakref'd target organ model
        (ADR-0014 §1, ``GetTargetModelNode()``) and hands it here.  This
        constructs a ``vtkLiverSpheroidRingExtractor``, feeds it the
        target mesh's ``vtkPolyData`` plus the axis-aligned spheroid
        ``Center`` + ``Radii`` off the data node, and stores the ordered
        ring.  Returns the ring ``vtkPolyData`` (or ``None`` when
        extraction cannot run).
        """
        if target_model is None:
            return None
        polydata = _model_polydata(target_model)
        if polydata is None:
            return None

        center_getter = getattr(self._data_node, "GetDistanceSpheroidCenter", None)
        rx_getter = getattr(self._data_node, "GetDistanceSpheroidRadiusX", None)
        ry_getter = getattr(self._data_node, "GetDistanceSpheroidRadiusY", None)
        rz_getter = getattr(self._data_node, "GetDistanceSpheroidRadiusZ", None)
        if None in (center_getter, rx_getter, ry_getter, rz_getter):
            return None
        try:
            center = _as_xyz_tuple(center_getter())
            rx = float(rx_getter())
            ry = float(ry_getter())
            rz = float(rz_getter())
        except Exception:  # pragma: no cover — defensive
            return None

        extractor_class = _resolve_extractor_class("vtkLiverSpheroidRingExtractor")
        if extractor_class is None:
            return None
        extractor = extractor_class()
        extractor.SetInputData(polydata)
        extractor.SetCenter(*center)
        extractor.SetRadiusX(rx)
        extractor.SetRadiusY(ry)
        extractor.SetRadiusZ(rz)
        extractor.Update()
        self._ring_polydata = extractor.GetOutput()
        return self._ring_polydata

    def GetRingPolyData(self) -> Any | None:
        """The intersection ring produced by the last
        ``run_ring_extraction`` — or ``None`` before commit."""
        return self._ring_polydata

    def cleanup(self) -> None:
        """Detach actors from the renderer and drop the VTK pipeline."""
        if self._renderer is not None:
            self._detach_actors(self._renderer)
            self._renderer = None
        # Drop strong references so VTK can free the resources.
        self._parametric_ellipsoid = None
        self._parametric_function_source = None
        self._spheroid_polydata_filter = None
        self._spheroid_mapper = None
        self._spheroid_actor = None
        self._marker_entries = []

    # ------------------------------------------------------------------ #
    # Introspection — used by the unit-layer tests
    # ------------------------------------------------------------------ #

    def GetMarkerActors(self) -> list[Any]:
        return [entry[2] for entry in self._marker_entries]

    def GetSpheroidActor(self) -> Any | None:
        return self._spheroid_actor

    def GetSpheroidMapper(self) -> Any | None:
        return self._spheroid_mapper

    def GetParametricEllipsoid(self) -> Any | None:
        return self._parametric_ellipsoid

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
        """Construct the spheroid pipeline.

        Marker actors are built lazily on demand (the count is data-
        driven; see ``_resize_markers``).

        The spheroid surface is rendered by
        ``vtkOpenGLDistanceContourPolyDataMapper`` (relocated to
        ``LiverResections/VTKWidgets/`` per ADR-0014 §3).  Its fragment
        shader bands the triaxial-ellipsoid implicit whose quadric
        coefficients are derived from the single source of truth
        (``vtkLiverSpheroidRingExtractor::ComputeQuadricCoefficients``,
        ADR-0015 §"Stack 4") so the rendered surface matches the
        on-commit CPU-extracted ring.  ``_apply_data_node`` pushes the
        (centre, radii) onto the mapper via ``SetSpheroid``.

        When the relocated mapper is not on the path (a plain non-Slicer
        VTK build used by the unit-layer tests) the pipeline falls back
        to a generic ``vtkPolyDataMapper`` so the Representation still
        constructs and the marker/colour bookkeeping stays testable.
        """
        # Spheroid pipeline ---------------------------------------------------
        self._parametric_ellipsoid = vtk.vtkParametricEllipsoid()
        # Sensible default radii so a freshly-constructed Representation
        # is not visually surprising before the first ``update()``.
        self._parametric_ellipsoid.SetXRadius(1.0)
        self._parametric_ellipsoid.SetYRadius(1.0)
        self._parametric_ellipsoid.SetZRadius(1.0)

        self._parametric_function_source = vtk.vtkParametricFunctionSource()
        self._parametric_function_source.SetParametricFunction(
            self._parametric_ellipsoid
        )

        # Translate the parametric output to the spheroid centre.  The
        # parametric source emits geometry around the origin; the data
        # node's Center is RAS world coordinates.  A transform filter
        # composes them.
        self._spheroid_polydata_filter = vtk.vtkTransformPolyDataFilter()
        self._spheroid_transform = vtk.vtkTransform()
        self._spheroid_transform.Identity()
        self._spheroid_polydata_filter.SetTransform(self._spheroid_transform)
        self._spheroid_polydata_filter.SetInputConnection(
            self._parametric_function_source.GetOutputPort()
        )

        mapper_class = _resolve_extractor_class(
            "vtkOpenGLDistanceContourPolyDataMapper"
        )
        if mapper_class is not None:
            self._spheroid_mapper = mapper_class()
        else:
            # Non-Slicer VTK build (unit-layer tests): the relocated
            # mapper is not wrapped onto the path.  A generic mapper keeps
            # the pipeline constructible; the triaxial banding is a no-op
            # there but the marker/colour bookkeeping is still exercised.
            self._spheroid_mapper = vtk.vtkPolyDataMapper()
        self._spheroid_mapper.SetInputConnection(
            self._spheroid_polydata_filter.GetOutputPort()
        )
        self._spheroid_actor = vtk.vtkActor()
        self._spheroid_actor.SetMapper(self._spheroid_mapper)
        self._spheroid_actor.GetProperty().SetColor(*DEFAULT_RESECTION_COLOR)
        self._spheroid_actor.GetProperty().SetOpacity(DEFAULT_RESECTION_OPACITY)

    def _make_marker_entry(self) -> tuple[Any, Any, Any]:
        """Construct one ``(sphere_source, mapper, actor)`` triple."""
        sphere = vtk.vtkSphereSource()
        sphere.SetRadius(DEFAULT_MARKER_RADIUS)
        sphere.SetCenter(0.0, 0.0, 0.0)
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(sphere.GetOutputPort())
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        # Markers render at full opacity regardless of the display
        # node's ResectionOpacity (which gates spheroid translucency
        # only).  Colour is updated by ``_apply_display_node``.
        actor.GetProperty().SetColor(*DEFAULT_RESECTION_COLOR)
        actor.GetProperty().SetOpacity(1.0)
        return (sphere, mapper, actor)

    def _resize_markers(self, n: int) -> None:
        """Grow or shrink the marker list to ``n`` entries.

        Newly-added actors are attached to the current renderer (if any)
        and inherit the most recently applied colour.  Removed actors
        are detached and their strong refs dropped.
        """
        current = len(self._marker_entries)
        if n == current:
            return
        if n > current:
            # Grow.
            for _ in range(n - current):
                entry = self._make_marker_entry()
                # Inherit current colour so newly-spawned markers don't
                # flash white before the next display-node read.
                entry[2].GetProperty().SetColor(*self._current_color)
                self._marker_entries.append(entry)
                if self._renderer is not None and hasattr(
                    self._renderer, "AddActor"
                ):
                    self._renderer.AddActor(entry[2])
        else:
            # Shrink — pop from the tail.
            for _ in range(current - n):
                _sphere, _mapper, actor = self._marker_entries.pop()
                if self._renderer is not None and hasattr(
                    self._renderer, "RemoveActor"
                ):
                    try:
                        self._renderer.RemoveActor(actor)
                    except Exception:  # pragma: no cover - defensive
                        pass
                # The triple goes out of scope here — VTK frees the
                # resources on garbage collection.

    def _attach_actors(self, renderer: Any) -> None:
        if not hasattr(renderer, "AddActor"):
            return
        if self._spheroid_actor is not None:
            renderer.AddActor(self._spheroid_actor)
        for _sphere, _mapper, actor in self._marker_entries:
            renderer.AddActor(actor)

    def _detach_actors(self, renderer: Any) -> None:
        if not hasattr(renderer, "RemoveActor"):
            return
        if self._spheroid_actor is not None:
            try:
                renderer.RemoveActor(self._spheroid_actor)
            except Exception:  # pragma: no cover - defensive
                pass
        for _sphere, _mapper, actor in self._marker_entries:
            try:
                renderer.RemoveActor(actor)
            except Exception:  # pragma: no cover - defensive
                pass

    def _apply_display_node(self, display_node: Any | None) -> None:
        """Push decoration fields onto the actors.

        Tolerant of ``None`` / partial display nodes — falls back to
        defaults.  Colour applies to spheroid + markers; opacity
        applies to the (translucent) spheroid only — markers stay at
        full opacity to remain visible against the translucent volume.
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
        # the pure-vector ResectionColor above.  The terminology helper
        # API lands in T2.4; this Representation will follow
        # ``BezierPlanningRepresentation``'s adopting pattern when it
        # does.

        if self._spheroid_actor is not None:
            prop = self._spheroid_actor.GetProperty()
            prop.SetColor(*color)
            prop.SetOpacity(opacity)
        for _sphere, _mapper, actor in self._marker_entries:
            actor.GetProperty().SetColor(*color)
            # Markers stay at full opacity (see method docstring).

    def _apply_data_node(self, data_node: Any | None) -> None:
        """Push (Center, Radii, init points) onto the spheroid + markers.

        The on-commit ring extraction (``run_ring_extraction``)
        constructs a ``vtkLiverSpheroidRingExtractor`` fed with the
        weakref'd target mesh (ADR-0014 §1, ``GetTargetModelNode()``)
        plus (Center, RadiusX, RadiusY, RadiusZ).  The axis-aligned-
        spheroid constraint matches the extractor's contract (its
        header notes that general-orientation rotation is deferred to
        a later stack iteration).  Per-frame visual feedback is the
        shader's job; the discrete ring is produced once, on the
        Init->Planning commit boundary (ADR-0019).
        """
        if data_node is None:
            return
        self._data_node = data_node

        center_getter = getattr(data_node, "GetDistanceSpheroidCenter", None)
        rx_getter = getattr(data_node, "GetDistanceSpheroidRadiusX", None)
        ry_getter = getattr(data_node, "GetDistanceSpheroidRadiusY", None)
        rz_getter = getattr(data_node, "GetDistanceSpheroidRadiusZ", None)
        n_getter = getattr(
            data_node, "GetNumberOfDistanceSpheroidInitPoints", None
        )
        point_getter = getattr(data_node, "GetDistanceSpheroidInitPoint", None)

        if center_getter is None or rx_getter is None or ry_getter is None or rz_getter is None:
            return

        try:
            center = _as_xyz_tuple(center_getter())
            rx = float(rx_getter())
            ry = float(ry_getter())
            rz = float(rz_getter())
        except Exception:  # pragma: no cover - defensive
            return

        if n_getter is not None and point_getter is not None:
            try:
                n = int(n_getter())
            except Exception:  # pragma: no cover - defensive
                n = 0
            init_points: tuple[tuple[float, float, float], ...] = tuple(
                _as_xyz_tuple(point_getter(i)) for i in range(max(0, n))
            )
        else:
            init_points = ()

        signature = (center, rx, ry, rz, init_points)
        if signature == self._last_input_signature:
            return  # idempotent short-circuit
        self._last_input_signature = signature
        self._input_refresh_count += 1

        # Spheroid: push radii into the parametric ellipsoid + recenter
        # via the transform filter.
        if self._parametric_ellipsoid is not None:
            self._parametric_ellipsoid.SetXRadius(rx)
            self._parametric_ellipsoid.SetYRadius(ry)
            self._parametric_ellipsoid.SetZRadius(rz)
        if self._spheroid_transform is not None:
            self._spheroid_transform.Identity()
            self._spheroid_transform.Translate(center[0], center[1], center[2])
            self._spheroid_transform.Modified()
        if self._parametric_function_source is not None:
            self._parametric_function_source.Modified()

        # Drive the contour shader: push (centre, radii) onto the mapper
        # so its fragment shader bands the triaxial-ellipsoid implicit
        # whose quadric coefficients come from the SSOT (ADR-0015
        # §"Stack 4").  Mirrors how vtkLiverBezierSurfacePipeline sets its
        # grid/margin uniforms.  No-op on the generic fallback mapper.
        set_spheroid = getattr(self._spheroid_mapper, "SetSpheroid", None)
        if set_spheroid is not None:
            set_spheroid(list(center), rx, ry, rz)

        # Make the banded contour visible.  The mapper defaults to hidden
        # and its fragment shader discards every fragment while visibility
        # is off, so without this the placed spheroid never renders.
        # Enabling it here -- once the representation has a spheroid to
        # show -- is what actually draws the triaxial ellipsoid.  No-op on
        # the generic fallback mapper.
        set_contour_visibility = getattr(self._spheroid_mapper, "SetContourVisibility", None)
        if set_contour_visibility is not None:
            set_contour_visibility(True)

        # Markers: resize the actor list, then update each sphere's
        # centre.
        self._resize_markers(len(init_points))
        for entry, point in zip(self._marker_entries, init_points):
            sphere, _mapper, _actor = entry
            sphere.SetCenter(point[0], point[1], point[2])
            sphere.Modified()


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


def _as_xyz_tuple(raw: Any) -> tuple[float, float, float]:
    """Coerce a 3-component accessor's return value to ``(x, y, z)``.

    Accepts list, tuple, or VTK-wrapped sequence; falls back to
    ``(0, 0, 0)`` on parse failure.
    """
    try:
        return (float(raw[0]), float(raw[1]), float(raw[2]))
    except Exception:
        return (0.0, 0.0, 0.0)


def _resolve_extractor_class(name: str) -> Any | None:
    """Resolve a VTK-wrapped ring-extractor class by name.

    The Algorithm-library classes are wrapped into Slicer's ``slicer``
    namespace (``SlicerMacroBuildModuleLogic`` Python wrapping); the
    plain ``vtk`` module is the fallback for non-Slicer VTK builds.
    Returns ``None`` when neither namespace exposes the class.
    """
    for module_name in ("slicer", "vtk"):
        try:
            module = __import__(module_name)
        except ImportError:
            continue
        cls = getattr(module, name, None)
        if cls is not None:
            return cls
    return None


def _model_polydata(target_model: Any | None) -> Any | None:
    """Return the ``vtkPolyData`` carried by a model node, or the
    argument itself when it is already a ``vtkPolyData``.

    The weakref'd target (ADR-0014 §1) is a ``vtkMRMLModelNode``; its
    surface mesh is reached via ``GetPolyData()``.
    """
    if target_model is None:
        return None
    getter = getattr(target_model, "GetPolyData", None)
    if getter is None:
        return target_model
    try:
        return getter()
    except Exception:  # pragma: no cover — defensive
        return None

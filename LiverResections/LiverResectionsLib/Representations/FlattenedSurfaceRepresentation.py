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

Scope of this skeleton
----------------------
Per the T3 bounded slice this skeleton COMPOSES the assembly and wires
the display-node fields it consumes, but it does NOT yet sever the
assembly out of the v1 monolith (that is a separate follow-up; until
then the monolith remains the live 2D renderer) and it does NOT add the
Gaussian-blur pass (a later v2.0 toggle).  The aspect-ratio math is
routed through the extracted Algorithm helper; the Gaussian-blur hook
is intentionally absent.

The VTK objects are soft dependencies — same pattern as
``ConfirmedRepresentation``: a pure-Python pytest run skips the VTK-only
branches, while a Slicer process (or any environment with VTK on
``PYTHONPATH``) exercises the full pipeline.  The relocated 2D mapper
(``vtkOpenGLResection2DPolyDataMapper``) and the ``vtkBezierSurfaceSource``
are reachable only inside a Slicer process, so their use is gated behind
``hasattr`` / import guards and the generic VTK fallbacks keep the
skeleton importable everywhere.

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

# --------------------------------------------------------------------------- #
# VTK is a soft dependency (see module docstring).
# --------------------------------------------------------------------------- #

try:  # pragma: no cover — exercised inside Slicer / when VTK is available
    import vtk

    _HAS_VTK = True
except ImportError:  # pragma: no cover — pure-Python path
    vtk = None  # type: ignore[assignment]
    _HAS_VTK = False


# --------------------------------------------------------------------------- #
# Overlay-renderer layer for the resectogram (matches the v1 monolith's
# RENDERER_LAYER for the 2D co-renderer).
# --------------------------------------------------------------------------- #

RESECTOGRAM_RENDERER_LAYER = 1


class FlattenedSurfaceRepresentation:
    """VTK assembly for the resectogram's flattened surface.

    Constructor
    -----------
    ``FlattenedSurfaceRepresentation(renderer=None)``

    * ``renderer`` — the ``vtkRenderer`` the resectogram actor is added
      to.  Optional; ``None`` is supported for unit tests (the actor
      exists but is unrendered).

    Public methods
    --------------
    * ``update(display_node, data_node)`` — reads decoration from the
      display node (``ShowResection2D`` / ``MirrorDisplay`` /
      ``EnableFlexibleBoundary`` / ``TextureNumComps``), geometry from
      the data node, recomputes ``MatRatio`` through the Algorithm
      helper, and reconciles the resectogram actor.  Tolerant of
      ``None`` arguments.
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
    """

    def __init__(self, renderer: Any | None = None) -> None:
        self._renderer: Any | None = None

        self._bezier_plane: Any | None = None
        self._resection_mapper_2d: Any | None = None
        self._resection_actor_2d: Any | None = None
        self._resectogram_camera: Any | None = None

        # Last MatRatio pushed onto the 2D mapper.  ``None`` until the
        # first ``update()`` runs OR the mapper does not expose
        # ``SetMatRatio`` (generic-mapper fallback path).
        self._mat_ratio_applied: tuple[float, float] | None = None

        # Memoised input — same idempotency strategy as
        # ConfirmedRepresentation.
        self._last_surface_signature: tuple | None = None
        self._input_refresh_count: int = 0

        if _HAS_VTK:
            self._build_vtk_pipeline()

        if renderer is not None:
            self.SetRenderer(renderer)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def SetRenderer(self, renderer: Any | None) -> None:
        """Attach the resectogram actor to ``renderer``."""
        if self._renderer is not None and self._renderer is not renderer:
            self._detach_actors(self._renderer)
        self._renderer = renderer
        if renderer is not None:
            self._attach_actors(renderer)

    def GetRenderer(self) -> Any | None:
        return self._renderer

    def update(self, display_node: Any | None, data_node: Any | None) -> None:
        """Reconcile the resectogram against the current display + data nodes.

        Tolerant of ``None`` arguments — when either node is missing the
        actor falls back to invisible / default state.
        """
        self._apply_display_node(display_node)
        self._apply_data_node(display_node, data_node)

    def cleanup(self) -> None:
        """Detach actors from the renderer and drop the VTK pipeline."""
        if self._renderer is not None:
            self._detach_actors(self._renderer)
            self._renderer = None
        self._bezier_plane = None
        self._resection_mapper_2d = None
        self._resection_actor_2d = None
        self._resectogram_camera = None

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

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _build_vtk_pipeline(self) -> None:
        """Construct the flattened-quad source, 2D mapper, actor + camera.

        Prefers the relocated ``vtkOpenGLResection2DPolyDataMapper`` and
        ``vtkBezierSurfaceSource`` (reachable inside a Slicer process);
        falls back to a generic ``vtkPolyDataMapper`` + ``vtkPlaneSource``
        so the skeleton stays importable in a bare VTK environment.  The
        public API is invariant across the fallback — only the concrete
        mapper / source types flip.
        """
        assert vtk is not None  # gated by _HAS_VTK

        self._bezier_plane = _make_flattened_quad_source()

        mapper = _make_resection_mapper_2d()
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
        """Push the sampled surface onto the quad source, then recompute
        the anisotropic ``MatRatio`` via the Algorithm helper.

        The ``MatRatio`` math is NOT re-derived here — it is routed
        through the extracted pure-VTK ``vtkLiverResectogramAspectRatio``
        helper (ADR-0015 §1), with ``flexibleBoundary`` taken from the
        display node's ``EnableFlexibleBoundary`` field.
        """
        flexible = _safe_get_bool(
            display_node, "GetEnableFlexibleBoundary", default=False
        )

        sampled = _safe_get_sampled_surface(data_node)
        signature = (id(sampled) if sampled is not None else None, bool(flexible))
        if signature != self._last_surface_signature:
            self._last_surface_signature = signature
            self._input_refresh_count += 1

        self._apply_mat_ratio(sampled, flexible)

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
    if not _HAS_VTK:
        return None
    factory = getattr(vtk, "vtkBezierSurfaceSource", None)
    if factory is not None:
        return factory()
    return vtk.vtkPlaneSource()


def _make_resection_mapper_2d() -> Any:
    """Return the resectogram's 2D mapper.

    Prefers the relocated ``vtkOpenGLResection2DPolyDataMapper``
    (``LiverResections/VTKWidgets/``, reachable in a Slicer process);
    falls back to a generic ``vtkPolyDataMapper``.
    """
    assert vtk is not None
    factory = getattr(vtk, "vtkOpenGLResection2DPolyDataMapper", None)
    if factory is None:
        try:  # pragma: no cover — exercised inside Slicer
            from slicer import vtkOpenGLResection2DPolyDataMapper as factory  # type: ignore[no-redef]
        except Exception:
            factory = None
    if factory is not None:
        return factory()
    return vtk.vtkPolyDataMapper()


def _import_aspect_ratio_helper() -> Any | None:
    """Return the ``vtkLiverResectogramAspectRatio`` helper class.

    Reachable from a Slicer process via the ``slicer`` namespace or the
    wrapped Algorithm module.  Returns ``None`` in a bare-VTK pytest run
    where the wrapped class is not importable.
    """
    if _HAS_VTK:
        factory = getattr(vtk, "vtkLiverResectogramAspectRatio", None)
        if factory is not None:
            return factory
    try:  # pragma: no cover — exercised inside Slicer
        from slicer import vtkLiverResectogramAspectRatio  # type: ignore[import-not-found]

        return vtkLiverResectogramAspectRatio
    except Exception:
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

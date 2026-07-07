# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Representation that owns the resectogram's vascular-contour overlays.

The resectogram draws the hepatic / portal vascular contours on top of
the flattened surface so the surgeon can read vessel proximity in the
2D ``(u, v)`` image (ADR-0025 §Context).  In the v1 monolith those
overlays are driven by two custom mappers — the distance-contour mapper
and the slicing-contour mapper — relocated into
``LiverResections/VTKWidgets/`` (``vtkOpenGLDistanceContourPolyDataMapper``
and ``vtkOpenGLSlicingContourPolyDataMapper``).

This Representation is the v2.0 LayerDM-bound home of that overlay per
ADR-0013 §6 (Representations are composable VTK pipelines).  It wraps
the two contour mappers + their actors and reconciles their visibility
against the resectogram display node.

Scope of this skeleton
----------------------
Per the T3 bounded slice this skeleton COMPOSES the contour overlays and
wires the display-node fields it consumes, but it does NOT yet sever the
overlays out of the v1 monolith (a separate follow-up).  The two contour
mappers are custom wrapped-C++ classes reachable only inside a Slicer
process; they are injected, not silently discovered (ADR-0014 §3).  In
production the ``distance_contour_mapper`` / ``slicing_contour_mapper``
constructor arguments are ``None`` and this Representation resolves the
real wrapped classes (raising if either is off the path — a real
misconfiguration must not degrade to a shader-less generic mapper).  The
bare-VTK unit layer (ADR-0008 §2) injects generic ``vtkPolyDataMapper``
instances.

References
----------
* `ADR-0013`_ §6 — Representations as composable VTK pipelines.
* `ADR-0014`_ §3 — mapper relocation (the contour mappers now live
  under ``LiverResections/VTKWidgets/``).
* `ADR-0025`_ §Context — the resectogram and its vascular overlays.

.. _ADR-0013: ../../../Docs/adr/0013-layerdm-pipeline-pattern.md
.. _ADR-0014: ../../../Docs/adr/0014-livermarkups-dissolution.md
.. _ADR-0025: ../../../Docs/adr/0025-locator-architecture.md
"""

from __future__ import annotations

from typing import Any

import vtk


class VascularContourRepresentation:
    """VTK assembly for the resectogram's vascular-contour overlays.

    Constructor
    -----------
    ``VascularContourRepresentation(renderer=None, *,
    distance_contour_mapper=None, slicing_contour_mapper=None)``

    * ``renderer`` — the ``vtkRenderer`` the contour actors are added
      to.  Optional; ``None`` is supported for unit tests.
    * ``distance_contour_mapper`` / ``slicing_contour_mapper`` — the two
      custom contour-mapper INSTANCES (dependency injection, ADR-0014
      §3).  ``None`` (production) resolves the real
      ``vtkOpenGLDistanceContourPolyDataMapper`` /
      ``vtkOpenGLSlicingContourPolyDataMapper``, raising if either is off
      the path.  Injected instances (bare-VTK unit layer, ADR-0008 §2)
      are used as-is.

    Public methods
    --------------
    * ``update(display_node, data_node)`` — reconciles the contour
      actors' visibility against the display node's ``ShowResection2D``
      field.  Tolerant of ``None`` arguments.
    * ``cleanup()`` — detaches the actors and releases the VTK pipeline.

    Introspection (used by unit tests)
    ----------------------------------
    * ``GetDistanceContourMapper()`` / ``GetSlicingContourMapper()`` —
      the two contour mappers, or ``None`` when VTK is absent.
    * ``GetDistanceContourActor()`` / ``GetSlicingContourActor()`` —
      the matching actors.
    """

    def __init__(
        self,
        renderer: Any | None = None,
        *,
        distance_contour_mapper: Any | None = None,
        slicing_contour_mapper: Any | None = None,
    ) -> None:
        self._renderer: Any | None = None

        self._distance_contour_mapper: Any | None = None
        self._distance_contour_actor: Any | None = None
        self._slicing_contour_mapper: Any | None = None
        self._slicing_contour_actor: Any | None = None

        self._update_count: int = 0

        self._build_vtk_pipeline(distance_contour_mapper, slicing_contour_mapper)

        if renderer is not None:
            self.SetRenderer(renderer)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def SetRenderer(self, renderer: Any | None) -> None:
        """Attach the contour actors to ``renderer``."""
        if self._renderer is not None and self._renderer is not renderer:
            self._detach_actors(self._renderer)
        self._renderer = renderer
        if renderer is not None:
            self._attach_actors(renderer)

    def GetRenderer(self) -> Any | None:
        return self._renderer

    def update(self, display_node: Any | None, data_node: Any | None) -> None:
        """Reconcile the contour overlays against the current node set.

        Pushes the flattened-strip polydata (the same strip the
        ``FlattenedSurfaceRepresentation`` draws — the contours are
        computed over it) into both contour mappers, then reconciles the
        actors' visibility against ``ShowResection2D``.  Tolerant of
        ``None`` arguments and of data nodes that do not yet expose the
        strip accessor.
        """
        self._apply_strip_input(data_node)

        show = _safe_get_bool(display_node, "GetShowResection2D", default=False)
        for actor in (self._distance_contour_actor, self._slicing_contour_actor):
            if actor is not None:
                actor.SetVisibility(bool(show))
        self._update_count += 1

    def cleanup(self) -> None:
        """Detach actors from the renderer and drop the VTK pipeline."""
        if self._renderer is not None:
            self._detach_actors(self._renderer)
            self._renderer = None
        self._distance_contour_mapper = None
        self._distance_contour_actor = None
        self._slicing_contour_mapper = None
        self._slicing_contour_actor = None

    # ------------------------------------------------------------------ #
    # Introspection — used by the unit-layer tests
    # ------------------------------------------------------------------ #

    def GetDistanceContourMapper(self) -> Any | None:
        return self._distance_contour_mapper

    def GetSlicingContourMapper(self) -> Any | None:
        return self._slicing_contour_mapper

    def GetDistanceContourActor(self) -> Any | None:
        return self._distance_contour_actor

    def GetSlicingContourActor(self) -> Any | None:
        return self._slicing_contour_actor

    def GetUpdateCount(self) -> int:
        return self._update_count

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _build_vtk_pipeline(
        self,
        distance_contour_mapper: Any | None,
        slicing_contour_mapper: Any | None,
    ) -> None:
        """Construct the two contour mappers + their actors.

        Each mapper is injected, not silently discovered (ADR-0014 §3): a
        ``None`` argument (production) resolves the real relocated
        ``vtkOpenGLDistanceContourPolyDataMapper`` /
        ``vtkOpenGLSlicingContourPolyDataMapper``, raising if it is off the
        path; an injected instance (bare-VTK unit layer, ADR-0008 §2) is
        used as-is.
        """
        self._distance_contour_mapper = (
            distance_contour_mapper
            if distance_contour_mapper is not None
            else _make_contour_mapper("vtkOpenGLDistanceContourPolyDataMapper")
        )
        self._distance_contour_actor = vtk.vtkActor()
        self._distance_contour_actor.SetMapper(self._distance_contour_mapper)
        self._distance_contour_actor.SetVisibility(False)

        self._slicing_contour_mapper = (
            slicing_contour_mapper
            if slicing_contour_mapper is not None
            else _make_contour_mapper("vtkOpenGLSlicingContourPolyDataMapper")
        )
        self._slicing_contour_actor = vtk.vtkActor()
        self._slicing_contour_actor.SetMapper(self._slicing_contour_mapper)
        self._slicing_contour_actor.SetVisibility(False)

    def _apply_strip_input(self, data_node: Any | None) -> None:
        """Feed the flattened-strip polydata into both contour mappers.

        The vascular contours are computed over the SAME flattened strip
        the surface Representation draws (ADR-0025 §Context), so both
        mappers take that polydata as their input.  No-op when the data
        node is absent or does not yet expose the strip accessor (stub
        data nodes in unit tests; the monolith-sever follow-up wires the
        live carrier).
        """
        strip = _safe_get_strip_polydata(data_node)
        if strip is None:
            return
        for mapper in (self._distance_contour_mapper, self._slicing_contour_mapper):
            if mapper is None:
                continue
            setter = getattr(mapper, "SetInputData", None)
            if setter is not None:
                setter(strip)

    def _attach_actors(self, renderer: Any) -> None:
        if not hasattr(renderer, "AddActor"):
            return
        for actor in (self._distance_contour_actor, self._slicing_contour_actor):
            if actor is not None:
                renderer.AddActor(actor)

    def _detach_actors(self, renderer: Any) -> None:
        if not hasattr(renderer, "RemoveActor"):
            return
        for actor in (self._distance_contour_actor, self._slicing_contour_actor):
            if actor is not None:
                try:
                    renderer.RemoveActor(actor)
                except Exception:  # pragma: no cover - defensive
                    pass


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _make_contour_mapper(class_name: str) -> Any:
    """Return a relocated contour mapper instance by class name, or raise.

    The custom contour mappers are reachable from a Slicer process via the
    ``vtk`` module (wrapped) or the ``slicer`` namespace.  Raises
    ``RuntimeError`` when neither namespace exposes the class — a real
    misconfiguration in production (ADR-0014 §3) must fail loudly rather
    than degrade to a shader-less generic mapper.  Bare-VTK unit tests
    (ADR-0008 §2) avoid this path by injecting a mapper instance instead.
    """
    factory = _require_vtk_class(class_name)
    return factory()


def _require_vtk_class(name: str) -> Any:
    """Resolve a wrapped-C++ class by name from ``vtk`` then ``slicer``, or raise."""
    factory = getattr(vtk, name, None)
    if factory is None:
        try:  # pragma: no cover — exercised inside Slicer
            import slicer

            factory = getattr(slicer, name, None)
        except Exception:
            factory = None
    if factory is None:
        raise RuntimeError(
            f"{name} is not reachable from the 'vtk' or 'slicer' namespace. "
            "It is a wrapped-C++ class relocated to LiverResections/VTKWidgets/ "
            "(ADR-0014 §3) and available only inside a launched Slicer with the "
            "module loaded.  Inject a mapper instance for bare-VTK unit tests "
            "(ADR-0008 §2)."
        )
    return factory


def _safe_get_strip_polydata(data_node: Any | None) -> Any | None:
    """Return the flattened-strip ``vtkPolyData`` off the data node, if any.

    Reads a small set of conventional accessors defensively; returns
    ``None`` when none are present (stub data nodes in unit tests).
    """
    if data_node is None:
        return None
    for name in ("GetResectogramStripPolyData", "GetStripPolyData"):
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

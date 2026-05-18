# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Representation active in ``(ResectionState=Confirmed, *)`` per ADR-0019.

Renders the fitted Bezier surface as a "clean view" — control polygon
hidden, widget disabled, and the parenchyma-trim shader on the
surface mapper so the bit of the resection plane exterior to the
liver parenchyma does not render.  Round-trippable: a transition back
to ``Planning`` returns to ``BezierPlanningRepresentation`` and the
control polygon reappears.

Scope of this skeleton
----------------------
Per ADR-0019 §"Rollout plan" item 3, the parenchyma-trim mapper
relocates from ``LiverMarkups/VTKWidgets/`` into
``LiverResections/VTKWidgets/`` on a separate ENH PR
(``T2-mapper-relocation``).  Until that relocation lands, the
relocated ``vtkOpenGLBezierResectionPolyDataMapper`` is not the
Representation's surface-mapper field — this skeleton uses the
generic ``vtkPolyDataMapper`` for parity with the sibling
``BezierPlanningRepresentation`` and routes the trim-shader call
defensively (``hasattr`` check on ``SetResectionClipOut``).  The
public API of this Representation does not change when the
relocation completes; only the mapper field's concrete type flips.

Per-state visual contract (ADR-0019 §"Per-state contract")
----------------------------------------------------------
The full reference matrix lives in
``Docs/architecture/resection-state-machine.md``.  Relevant rows for
this Representation:

* Control polygon visible        — **no**.
* Widget enabled                 — **no**.
* Init markers visible           — no.
* Bezier surface visible         — **yes** (trimmed to liver parenchyma).
* Grid-overlay shader            — **off**.
* Parenchyma-trim shader         — **on** (``uResectionClipOut == 1``).

References
----------
* `ADR-0013`_ §6 — Representations as composable VTK pipelines.
* `ADR-0014`_ §3 — mapper relocation.
* `ADR-0019`_ — 3-state machine (this Representation is the
  ``Confirmed`` row of the dispatch table).

.. _ADR-0013: ../../../Docs/adr/0013-layerdm-pipeline-pattern.md
.. _ADR-0014: ../../../Docs/adr/0014-livermarkups-dissolution.md
.. _ADR-0019: ../../../Docs/adr/0019-resection-state-machine.md
"""

from __future__ import annotations

from typing import Any

# --------------------------------------------------------------------------- #
# VTK is a soft dependency — same pattern as BezierPlanningRepresentation: a
# pure-Python pytest run skips the VTK-only branches, while a Slicer process
# (or an environment with VTK on PYTHONPATH) exercises the full pipeline.
# --------------------------------------------------------------------------- #

try:  # pragma: no cover — exercised inside Slicer / when VTK is available
    import vtk

    _HAS_VTK = True
except ImportError:  # pragma: no cover — pure-Python path
    vtk = None  # type: ignore[assignment]
    _HAS_VTK = False


# --------------------------------------------------------------------------- #
# Default colour / opacity values — matched to BezierPlanningRepresentation so
# the visual transition Planning <-> Confirmed only differs in the trim shader
# and widget visibility, not in the surface colour.
# --------------------------------------------------------------------------- #

DEFAULT_RESECTION_COLOR = (1.0, 1.0, 1.0)
DEFAULT_RESECTION_OPACITY = 1.0


class ConfirmedRepresentation:
    """VTK assembly for the Confirmed-state Bezier surface.

    Constructor
    -----------
    ``ConfirmedRepresentation(renderer=None)``

    * ``renderer`` — the ``vtkRenderer`` the actors are added to.
      Optional; ``None`` is supported for unit tests (the actors
      exist but are unrendered).

    Public methods
    --------------
    * ``update(display_node, data_node)`` — reads decoration from the
      display node, geometry from the data node, applies the trim
      shader on the mapper (when available), and reconciles the
      surface actor.  Tolerant of ``None`` arguments.
    * ``cleanup()`` — detaches the actor from the renderer and releases
      the VTK pipeline.

    Trim shader binding
    -------------------
    The relocated ``vtkOpenGLBezierResectionPolyDataMapper`` exposes
    ``SetResectionClipOut(bool)``.  ``ConfirmedRepresentation`` sets
    it to ``True`` on every ``update()`` while
    ``BezierPlanningRepresentation`` leaves it at the constructor
    default (``False``).  Until the relocation lands the surface
    mapper is a generic ``vtkPolyDataMapper`` without that method —
    the call is gated by a ``hasattr`` check so the Representation
    survives the in-between state without crashing.

    Introspection (used by unit tests)
    ----------------------------------
    * ``GetSurfaceActor()`` / ``GetSurfaceMapper()`` — the actor +
      mapper pair, or ``None`` when VTK is absent.
    * ``GetCurrentColor()`` / ``GetCurrentOpacity()`` — the values last
      written to the actor property; stubs for tests without VTK.
    * ``GetClipOutApplied()`` — last ``SetResectionClipOut`` call's
      argument (``True`` when the relocated mapper accepted the call,
      ``None`` when the mapper does not expose the method).
    """

    def __init__(self, renderer: Any | None = None) -> None:
        self._renderer: Any | None = None

        self._surface_polydata: Any | None = None
        self._surface_mapper: Any | None = None
        self._surface_actor: Any | None = None

        self._current_color: tuple[float, float, float] = DEFAULT_RESECTION_COLOR
        self._current_opacity: float = DEFAULT_RESECTION_OPACITY

        # Tracks the last ``SetResectionClipOut`` value the
        # Representation pushed onto the surface mapper.  ``None``
        # until the first ``update()`` runs OR the mapper does not
        # expose ``SetResectionClipOut`` (skeleton state pre-mapper-
        # relocation).  Exposed via ``GetClipOutApplied`` for unit
        # tests that assert the trim toggle fires.
        self._clip_out_applied: bool | None = None

        # Memoised input — same idempotency strategy as
        # BezierPlanningRepresentation.
        self._last_grid_signature: tuple | None = None
        self._input_refresh_count: int = 0

        # TODO(T2-mapper-relocation): swap ``vtk.vtkPolyDataMapper`` for
        # ``vtkOpenGLBezierResectionPolyDataMapper`` once the four
        # custom mappers are relocated from
        # ``LiverMarkups/VTKWidgets/`` to ``LiverResections/VTKWidgets/``
        # per ADR-0014 §3.  The public API of this Representation does
        # not change — only the mapper field's concrete type.  The
        # relocated mapper exposes ``SetResectionClipOut(bool)`` (see
        # ``vtkOpenGLBezierResectionPolyDataMapper.h``); the
        # ``hasattr`` gate in ``_apply_data_node`` flips on
        # automatically once the swap happens.
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
        """Reconcile the actor against the current display + data nodes.

        Tolerant of ``None`` arguments — when either node is missing
        the actor falls back to invisible / default state.
        """
        self._apply_display_node(display_node)
        self._apply_data_node(data_node)

    def cleanup(self) -> None:
        """Detach actors from the renderer and drop the VTK pipeline."""
        if self._renderer is not None:
            self._detach_actors(self._renderer)
            self._renderer = None
        self._surface_polydata = None
        self._surface_mapper = None
        self._surface_actor = None

    # ------------------------------------------------------------------ #
    # Introspection — used by the unit-layer tests
    # ------------------------------------------------------------------ #

    def GetSurfaceActor(self) -> Any | None:
        return self._surface_actor

    def GetSurfaceMapper(self) -> Any | None:
        return self._surface_mapper

    def GetCurrentColor(self) -> tuple[float, float, float]:
        return self._current_color

    def GetCurrentOpacity(self) -> float:
        return self._current_opacity

    def GetClipOutApplied(self) -> bool | None:
        """Last value pushed to the surface mapper's
        ``SetResectionClipOut`` — ``True`` once the relocated mapper
        accepts the trim toggle, ``None`` while the skeleton's generic
        mapper does not expose the method (pre-mapper-relocation).
        """
        return self._clip_out_applied

    def GetInputRefreshCount(self) -> int:
        return self._input_refresh_count

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _build_vtk_pipeline(self) -> None:
        """Construct the surface actor.

        TODO(T2-mapper-relocation): swap the generic
        ``vtkPolyDataMapper`` for ADR-0014 §3's relocated
        ``vtkOpenGLBezierResectionPolyDataMapper`` and wire the
        trim-shader uniform feed from the display node's ``ClipOut``
        field.  The mapper exposes ``SetResectionClipOut(bool)`` today
        on the legacy mapper at
        ``LiverMarkups/VTKWidgets/vtkOpenGLBezierResectionPolyDataMapper.cpp``
        (relocated by T2-mapper-relocation); see
        ``vtkOpenGLBezierResectionPolyDataMapper.h`` for the full
        uniform surface.
        """
        assert vtk is not None  # gated by _HAS_VTK

        self._surface_polydata = vtk.vtkPolyData()
        self._surface_mapper = vtk.vtkPolyDataMapper()
        self._surface_mapper.SetInputData(self._surface_polydata)
        self._surface_actor = vtk.vtkActor()
        self._surface_actor.SetMapper(self._surface_mapper)
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
        """Push decoration fields onto the actor."""
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

        if self._surface_actor is not None:
            prop = self._surface_actor.GetProperty()
            prop.SetColor(*color)
            prop.SetOpacity(opacity)

    def _apply_data_node(self, data_node: Any | None) -> None:
        """Push the 4×4 control grid onto the surface mapper, then
        engage the parenchyma-trim shader uniform.

        The Bezier control grid is the editable geometry in
        ``Planning`` and the frozen geometry in ``Confirmed``; this
        Representation reads the same field — ``Confirmed`` only
        differs from ``Planning`` in the shader-side trim, the absence
        of the control-polygon glyphs, and the disabled widget.  All
        three differences live outside this method.
        """
        if data_node is None:
            return

        grid_getter = getattr(data_node, "GetControlGrid", None)
        if grid_getter is None:
            return

        try:
            raw = grid_getter()
        except Exception:  # pragma: no cover - defensive
            return
        if raw is None:
            return

        try:
            flat = tuple(float(raw[i]) for i in range(48))
        except Exception:
            return

        signature = flat
        if signature == self._last_grid_signature:
            # Geometry unchanged; still re-apply the trim toggle in
            # case the mapper was reset out from under us between
            # update() calls.
            self._apply_trim_shader()
            return
        self._last_grid_signature = signature
        self._input_refresh_count += 1

        if not _HAS_VTK:
            return

        points = _make_points_from_flat(flat)
        self._refresh_surface_polydata(points)
        self._apply_trim_shader()

    def _refresh_surface_polydata(self, points: Any) -> None:
        assert vtk is not None
        polydata = self._surface_polydata
        if polydata is None:
            return
        polydata.SetPoints(points)

        cells = vtk.vtkCellArray()
        for v in range(3):
            for u in range(3):
                quad = vtk.vtkQuad()
                quad.GetPointIds().SetId(0, v * 4 + u)
                quad.GetPointIds().SetId(1, v * 4 + (u + 1))
                quad.GetPointIds().SetId(2, (v + 1) * 4 + (u + 1))
                quad.GetPointIds().SetId(3, (v + 1) * 4 + u)
                cells.InsertNextCell(quad)
        polydata.SetPolys(cells)
        polydata.Modified()

    def _apply_trim_shader(self) -> None:
        """Push the parenchyma-trim toggle onto the surface mapper.

        Gated by ``hasattr`` because the skeleton's surface mapper is
        a generic ``vtkPolyDataMapper`` until T2-mapper-relocation
        swaps it for the relocated
        ``vtkOpenGLBezierResectionPolyDataMapper``.  Until then the
        call is a no-op observationally (``self._clip_out_applied``
        stays ``None``).
        """
        mapper = self._surface_mapper
        if mapper is None:
            return
        setter = getattr(mapper, "SetResectionClipOut", None)
        if setter is None:
            return
        setter(True)
        self._clip_out_applied = True


# --------------------------------------------------------------------------- #
# Helpers — small + shared semantically with BezierPlanningRepresentation
# but duplicated locally to keep each Representation self-contained per
# ADR-0013 §6 (Representations are independently importable).
# --------------------------------------------------------------------------- #


def _as_color_tuple(raw: Any) -> tuple[float, float, float]:
    """Coerce a colour accessor's return value to ``(r, g, b)``."""
    try:
        r = max(0.0, min(1.0, float(raw[0])))
        g = max(0.0, min(1.0, float(raw[1])))
        b = max(0.0, min(1.0, float(raw[2])))
        return (r, g, b)
    except Exception:
        return DEFAULT_RESECTION_COLOR


def _make_points_from_flat(flat: tuple) -> Any:
    """Build a ``vtkPoints`` from a 48-double row-major control grid."""
    assert vtk is not None
    points = vtk.vtkPoints()
    points.SetNumberOfPoints(16)
    for i in range(16):
        x = flat[i * 3 + 0]
        y = flat[i * 3 + 1]
        z = flat[i * 3 + 2]
        points.SetPoint(i, x, y, z)
    return points

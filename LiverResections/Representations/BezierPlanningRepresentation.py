"""Representation active in ``(ResectionState=Planning, *)``.

Renders the 4×4 Bezier control grid (per ADR-0014 §3: corners 4 +
edges 8 + interior 4) and the fitted Bezier surface, driven by the
``vtkMRMLBezierSurfaceNode`` data node (geometry) and the paired
``vtkMRMLBezierSurfaceDisplayNode`` (decoration).

Scope of this skeleton
----------------------
This is the **first PR of the T2.2 stack**.  The Representation
class is constructed by ``LiverBezierSurfacePipeline.initialize()``
and exercised by direct Python instantiation in unit tests.  Full
integration with Slicer's LayerDM framework happens at T2.6.

Per ADR-0014 §3 the four custom OpenGL mappers
(``vtkOpenGLBezierResectionPolyDataMapper``,
``vtkOpenGLSlicingContourPolyDataMapper``,
``vtkOpenGLDistanceContourPolyDataMapper``,
``vtkOpenGLResection2DPolyDataMapper``) **relocate** from
``LiverMarkups/VTKWidgets/`` to ``LiverResections/VTKWidgets/``.  The
relocation has not landed yet in this branch (it is part of the
broader T2 cohort, not the T2.2 stack); this Representation uses
the generic ``vtkPolyDataMapper`` + ``vtkActor`` pair until that
relocation completes, at which point the surface mapper field will
flip to ``vtkOpenGLBezierResectionPolyDataMapper`` *without changing
the Representation's public API*.  Marked with ``TODO(T2-mapper-
relocation)`` at the construction point so the swap is mechanical.

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
  colour / label / badge from the SCT triple; for this PR the
  Representation honours the pure-vector ``ResectionColor`` etc.
  fields, falling through to terminology-driven colour resolution
  when the terminology helper lands (TODO marker below).
* `ADR-0013`_ §6 — Representations as composable VTK pipelines.
* `ADR-0014`_ §3 — mapper relocation.

.. _ADR-0011: ../../../Docs/adr/0011-sct-terminology-dispatch.md
.. _ADR-0013: ../../../Docs/adr/0013-layerdm-pipeline-pattern.md
.. _ADR-0014: ../../../Docs/adr/0014-livermarkups-dissolution.md
"""

from __future__ import annotations

from typing import Any

# --------------------------------------------------------------------------- #
# VTK is a soft dependency — when running in a plain Python without VTK on
# ``PYTHONPATH``, the import below fails and the unit tests that need a
# real mapper skip via ``pytest.importorskip("vtk")``.  The Representation
# can still be constructed (the lazy ``_get_vtk()`` returns ``None``); its
# ``update()`` then becomes a no-op for the missing VTK case, which is
# enough for the smoke-level tests.
# --------------------------------------------------------------------------- #

try:  # pragma: no cover — exercised inside Slicer / when VTK is available
    import vtk

    _HAS_VTK = True
except ImportError:  # pragma: no cover — pure-Python path
    vtk = None  # type: ignore[assignment]
    _HAS_VTK = False


# --------------------------------------------------------------------------- #
# Default colour / opacity values — mirror the legacy
# ``vtkMRMLLiverResectionNode`` constructor (see its .cxx, lines 56-66) so
# the Pipeline path starts from an identical visual baseline.  Display
# nodes carry these as float[3] in [0,1].
# --------------------------------------------------------------------------- #

DEFAULT_RESECTION_COLOR = (1.0, 1.0, 1.0)
DEFAULT_RESECTION_OPACITY = 1.0


class BezierPlanningRepresentation:
    """VTK assembly for the Planning-state Bezier surface.

    Constructor
    -----------
    ``BezierPlanningRepresentation(renderer=None)``

    * ``renderer`` — the ``vtkRenderer`` the actors are added to.
      Optional; ``None`` is supported for unit tests (the actors
      exist but are unrendered).

    Public methods
    --------------
    * ``update(display_node, data_node)`` — reads decoration from the
      display node, geometry from the data node, and reconciles the
      mapper / actor pair.  Tolerant of ``None`` arguments — turns the
      actor invisible in those cases.
    * ``cleanup()`` — detaches the actor from the renderer and releases
      the VTK pipeline.

    Introspection (used by unit tests)
    ----------------------------------
    * ``GetSurfaceActor()`` — the ``vtkActor`` rendering the surface,
      or ``None`` if VTK is not importable.
    * ``GetSurfaceMapper()`` — the surface mapper.
    * ``GetGridActor()`` — the actor rendering the 4×4 grid as
      line segments.
    * ``GetGridMapper()`` — the grid mapper.
    * ``GetCurrentColor()`` — the (r, g, b) triple last written to the
      surface mapper's property.  Returns the default when VTK is
      absent or no ``update()`` has fired.
    * ``GetCurrentOpacity()`` — the opacity last written.
    """

    def __init__(self, renderer: Any | None = None) -> None:
        self._renderer: Any | None = None

        # The four VTK objects the Representation owns.  ``None`` in
        # the pure-Python testing path.
        self._surface_polydata: Any | None = None
        self._surface_mapper: Any | None = None
        self._surface_actor: Any | None = None
        self._grid_polydata: Any | None = None
        self._grid_mapper: Any | None = None
        self._grid_actor: Any | None = None

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

        # TODO(T2-mapper-relocation): swap ``vtk.vtkPolyDataMapper`` for
        # ``vtkOpenGLBezierResectionPolyDataMapper`` once the four custom
        # mappers are relocated from ``LiverMarkups/VTKWidgets/`` to
        # ``LiverResections/VTKWidgets/`` per ADR-0014 §3.  The public
        # API of this Representation does not change — only the mapper
        # field's concrete type.
        if _HAS_VTK:
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
        # No-op when VTK is unavailable; the colour / opacity stubs
        # below still update so the introspection helpers report
        # consistent values for tests that drive ``update()`` without
        # VTK.
        self._apply_display_node(display_node)
        self._apply_data_node(data_node)

    def cleanup(self) -> None:
        """Detach actors from the renderer and drop the VTK pipeline."""
        if self._renderer is not None:
            self._detach_actors(self._renderer)
            self._renderer = None
        # Drop strong references so VTK can free the resources.
        self._surface_polydata = None
        self._surface_mapper = None
        self._surface_actor = None
        self._grid_polydata = None
        self._grid_mapper = None
        self._grid_actor = None

    # ------------------------------------------------------------------ #
    # Introspection — used by the unit-layer tests
    # ------------------------------------------------------------------ #

    def GetSurfaceActor(self) -> Any | None:
        return self._surface_actor

    def GetSurfaceMapper(self) -> Any | None:
        return self._surface_mapper

    def GetGridActor(self) -> Any | None:
        return self._grid_actor

    def GetGridMapper(self) -> Any | None:
        return self._grid_mapper

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
        """Construct the surface + grid actors.

        Called from ``__init__`` only when ``vtk`` is importable.
        """
        assert vtk is not None  # for the type-checker — gated by _HAS_VTK

        # Surface side ------------------------------------------------
        self._surface_polydata = vtk.vtkPolyData()
        self._surface_mapper = vtk.vtkPolyDataMapper()
        self._surface_mapper.SetInputData(self._surface_polydata)
        self._surface_actor = vtk.vtkActor()
        self._surface_actor.SetMapper(self._surface_mapper)
        # Sensible defaults so a freshly-constructed Representation is
        # not visually surprising before the first ``update()``.
        self._surface_actor.GetProperty().SetColor(*DEFAULT_RESECTION_COLOR)
        self._surface_actor.GetProperty().SetOpacity(DEFAULT_RESECTION_OPACITY)

        # Grid side ---------------------------------------------------
        self._grid_polydata = vtk.vtkPolyData()
        self._grid_mapper = vtk.vtkPolyDataMapper()
        self._grid_mapper.SetInputData(self._grid_polydata)
        self._grid_actor = vtk.vtkActor()
        self._grid_actor.SetMapper(self._grid_mapper)
        self._grid_actor.GetProperty().SetColor(0.0, 0.0, 0.0)
        # Hidden by default — the display node's ``GridVisibility`` flag
        # turns it on (mirrors the legacy ResectionNode constructor).
        self._grid_actor.SetVisibility(False)

    def _attach_actors(self, renderer: Any) -> None:
        if self._surface_actor is not None and hasattr(renderer, "AddActor"):
            renderer.AddActor(self._surface_actor)
        if self._grid_actor is not None and hasattr(renderer, "AddActor"):
            renderer.AddActor(self._grid_actor)

    def _detach_actors(self, renderer: Any) -> None:
        if self._surface_actor is not None and hasattr(
            renderer, "RemoveActor"
        ):
            try:
                renderer.RemoveActor(self._surface_actor)
            except Exception:  # pragma: no cover - defensive
                pass
        if self._grid_actor is not None and hasattr(renderer, "RemoveActor"):
            try:
                renderer.RemoveActor(self._grid_actor)
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
            grid_visible = False
        else:
            color_getter = getattr(display_node, "GetResectionColor", None)
            opacity_getter = getattr(
                display_node, "GetResectionOpacity", None
            )
            grid_getter = getattr(display_node, "GetGridVisibility", None)

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
            grid_visible = (
                bool(grid_getter()) if grid_getter is not None else False
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

        if self._grid_actor is not None:
            self._grid_actor.SetVisibility(bool(grid_visible))

    def _apply_data_node(self, data_node: Any | None) -> None:
        """Push the 4×4 control grid onto the surface / grid mappers."""
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

        # Materialise to a tuple of 48 floats for memoisation.  The
        # wrapped ``const double*`` from C++ may surface as a sequence
        # that does not implement ``__hash__``; tuple it for the
        # signature comparison.
        try:
            flat = tuple(float(raw[i]) for i in range(48))
        except Exception:
            # Some VTK Python wrappings return a raw pointer-like object
            # that is not indexable — defer the input refresh until a
            # proper accessor lands.  Tracked as TODO below.
            return

        signature = flat
        if signature == self._last_grid_signature:
            return  # no geometry change, no refresh
        self._last_grid_signature = signature
        self._input_refresh_count += 1

        if not _HAS_VTK:
            return

        # Rebuild the surface and grid polydata from the 4×4 control
        # mesh.  For the skeleton the "surface" is the raw 4×4 mesh
        # itself (16 points + 9 quads); the fitted Bernstein patch will
        # be substituted in when the relocated
        # ``vtkOpenGLBezierResectionPolyDataMapper`` is wired up per
        # ADR-0014 §3 (see the TODO at construction time).
        points = _make_points_from_flat(flat)
        self._refresh_surface_polydata(points)
        self._refresh_grid_polydata(points)

    def _refresh_surface_polydata(self, points: Any) -> None:
        assert vtk is not None
        polydata = self._surface_polydata
        if polydata is None:
            return
        polydata.SetPoints(points)

        cells = vtk.vtkCellArray()
        # Connect the 4×4 control mesh into 3×3 quads.  ``ids`` indexes
        # the flat 0..15 point array laid out row-major in (u, v).
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

    def _refresh_grid_polydata(self, points: Any) -> None:
        assert vtk is not None
        polydata = self._grid_polydata
        if polydata is None:
            return
        polydata.SetPoints(points)

        lines = vtk.vtkCellArray()
        # Horizontal edges (3 per row × 4 rows).
        for v in range(4):
            for u in range(3):
                line = vtk.vtkLine()
                line.GetPointIds().SetId(0, v * 4 + u)
                line.GetPointIds().SetId(1, v * 4 + (u + 1))
                lines.InsertNextCell(line)
        # Vertical edges (3 per column × 4 columns).
        for u in range(4):
            for v in range(3):
                line = vtk.vtkLine()
                line.GetPointIds().SetId(0, v * 4 + u)
                line.GetPointIds().SetId(1, (v + 1) * 4 + u)
                lines.InsertNextCell(line)
        polydata.SetLines(lines)
        polydata.Modified()


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

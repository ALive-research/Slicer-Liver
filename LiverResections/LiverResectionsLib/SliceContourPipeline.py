# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""LayerDM Pipeline projecting the resection surface onto slice views.

The resection surface intersected with a slice plane is a CONTOUR -- the
surgeon's 2D projection of the plan (the T2 render cutover's deferred
slice-view half).  This Pipeline is keyed on the same
``vtkMRMLParametricSurfaceDisplayNode`` the 3D surface Pipeline owns, but
its creator accepts ``vtkMRMLSliceNode`` views ONLY (LayerDM creators
dispatch per view TYPE; the 3D creator declines slice nodes, this one
declines everything else) -- ADR-0013 §1 keying stays disjoint per
(view-type, display-type) pair.

Composition: the carrier's control grid feeds a ``vtkBezierSurfaceSource``
tessellation, a ``vtkCutter`` slices it with the plane from the slice
node's ``SliceToRAS`` (origin = 4th column, normal = 3rd), and the RAS
contour is transformed by ``inverse(XYToRAS)`` into the slice view's XY
space for a ``vtkActor2D`` -- the coordinate convention slice-view
displayable managers render in.

Lifecycle mirrors the sibling pipelines (no-arg ctor; SetDisplayNode
derives the carrier + observers; OnRendererAdded re-derives after churn;
digest-gated RequestRender on edits).
"""

from __future__ import annotations

from typing import Any

import vtk

from LayerDMLib import vtkMRMLLayerDMScriptedPipeline as _PipelineBase

try:  # pragma: no cover - exercised once per import path
    from .LiverBezierSurfacePipeline import (
        STATE_CONFIRMED,
        STATE_PLANNING,
        _control_points_digest,
        _safe_get_state,
    )
except ImportError:  # top-level import path (the unit layer's sys.path setup)
    from LiverBezierSurfacePipeline import (  # type: ignore[no-redef]
        STATE_CONFIRMED,
        STATE_PLANNING,
        _control_points_digest,
        _safe_get_state,
    )

_REGISTERED = False


def _resolve_surface_source() -> Any | None:
    """The wrapped ``vtkBezierSurfaceSource``, or ``None`` off-path."""
    try:
        import vtkSlicerLiverResectionsModuleVTKWidgetsPython as widgets

        cls = getattr(widgets, "vtkBezierSurfaceSource", None)
        if cls is not None:
            return cls
    except ImportError:
        pass
    try:
        import slicer

        return getattr(slicer, "vtkBezierSurfaceSource", None)
    except Exception:  # pragma: no cover - defensive
        return None


def _creator_accepts_view(viewNode: Any) -> bool:  # noqa: N803 - VTK arg name
    """True iff ``viewNode`` is a slice view (this pipeline's home).

    Part of the creator callback: LayerDM invokes it for every
    ``(view, node)`` pair, so it must never raise.
    """
    try:
        return viewNode is not None and bool(viewNode.IsA("vtkMRMLSliceNode"))
    except Exception:  # pragma: no cover - C++ boundary must never raise
        return False


class SliceContourPipeline(_PipelineBase):
    """Renders the surface/slice-plane intersection contour in XY space."""

    def __init__(self) -> None:
        super().__init__()
        self.SetPythonObject(self)

        self._display_node: Any | None = None
        self._data_node: Any | None = None
        self._slice_node: Any | None = None
        self._renderer: Any | None = None
        self._observer_tags: dict = {}
        self._observed_node_refs: list = []
        self._last_update_key: tuple | None = None
        self._last_render_key: tuple | None = None
        #: Geometry digest of the LAST tessellation feed: pose-only recuts
        #: (reslicing) reuse the cached patch instead of re-tessellating.
        self._last_fed_geometry: tuple | None = None

        # RAS-space assembly: tessellated patch -> plane cut.
        self._surface_source: Any | None = None  # lazy (wrapped class)
        self._cut_plane = vtk.vtkPlane()
        self._cutter = vtk.vtkCutter()
        self._cutter.SetCutFunction(self._cut_plane)

        # XY-space presentation: RAS contour -> inverse(XYToRAS) -> 2D actor.
        self._xy_transform = vtk.vtkTransform()
        self._transform_filter = vtk.vtkTransformPolyDataFilter()
        self._transform_filter.SetTransform(self._xy_transform)
        self._contour_mapper = vtk.vtkPolyDataMapper2D()
        self._contour_actor = vtk.vtkActor2D()
        self._contour_actor.SetMapper(self._contour_mapper)
        self._contour_actor.GetProperty().SetColor(1.0, 0.0, 0.0)
        self._contour_actor.GetProperty().SetLineWidth(2.0)
        self._contour_actor.SetVisibility(False)

    # ------------------------------------------------------------------ #
    # LayerDM lifecycle
    # ------------------------------------------------------------------ #

    def SetViewNode(self, viewNode: Any) -> None:  # noqa: N802 - VTK verb
        super().SetViewNode(viewNode)
        # Observe the slice node OURSELVES: reslicing modifies the slice
        # node, and without this observer the contour keeps rendering the
        # stale cut (the digest keys on the pose but nothing re-runs the
        # reconciliation).
        if self._slice_node is not None:
            self._detach_observer(self._slice_node)
        self._slice_node = viewNode
        if viewNode is not None:
            self._attach_observer(viewNode)
        self._last_update_key = None

    def SetDisplayNode(self, displayNode: Any) -> None:  # noqa: N802 - VTK verb
        if self._display_node is not None:
            self._detach_observer(self._display_node)
        if self._data_node is not None:
            self._detach_observer(self._data_node)

        super().SetDisplayNode(displayNode)
        self._display_node = displayNode
        self._data_node = None
        if displayNode is not None:
            self._data_node = displayNode.GetDisplayableNode()
            self._attach_observer(displayNode)
            if self._data_node is not None:
                self._attach_observer(self._data_node)
        self._last_update_key = None

    def OnReferenceToDisplayNodeAdded(self, fromNode: Any, role: Any = None) -> None:  # noqa: N802
        try:
            if self._data_node is None and fromNode is not None and fromNode is not self._display_node:
                self._data_node = fromNode
                self._attach_observer(fromNode)
                self._last_update_key = None
            self.UpdatePipeline()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    def OnRendererAdded(self, renderer: Any) -> None:  # noqa: N802 - VTK verb
        try:
            self._renderer = renderer
            if renderer is not None:
                renderer.AddActor2D(self._contour_actor)
            # Re-derive after renderer churn (cleanup clears the node handles).
            if self._display_node is None:
                display = self.GetDisplayNode()
                if display is not None:
                    self.SetDisplayNode(display)
            # Re-attach the slice-node observer too: cleanup() detached it with
            # the rest, and the view node is not re-set after churn -- without
            # this, reslicing stops recutting (the stale-trace bug, round two).
            if self._slice_node is not None:
                self._attach_observer(self._slice_node)
            self._last_update_key = None
            self.UpdatePipeline()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    def OnRendererRemoved(self, renderer: Any) -> None:  # noqa: N802 - VTK verb
        try:
            if renderer is not None:
                renderer.RemoveActor2D(self._contour_actor)
            self._renderer = None
            self.cleanup()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    def cleanup(self) -> None:
        for node in list(self._observed_node_refs):
            self._detach_observer(node)
        self._display_node = None
        self._data_node = None
        self._contour_actor.SetVisibility(False)

    # ------------------------------------------------------------------ #
    # Reconciliation
    # ------------------------------------------------------------------ #

    def UpdatePipeline(self) -> None:  # noqa: N802 - VTK verb
        try:
            self._reconcile()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    def _reconcile(self) -> None:
        """``UpdatePipeline``'s body — plain attribute access throughout."""
        slice_node = self._slice_node
        state = _safe_get_state(self._data_node)
        key = (
            state,
            _control_points_digest(self._data_node),
            self._slice_matrix_digest(slice_node),
        )
        if key == self._last_update_key:
            return
        self._last_update_key = key

        visible = state in (STATE_PLANNING, STATE_CONFIRMED)
        contour = self._recompute_contour(slice_node) if visible else None
        has_points = contour is not None and contour.GetNumberOfPoints() > 0
        self._contour_actor.SetVisibility(bool(visible and has_points))

    def _recompute_contour(self, slice_node: Any) -> Any | None:
        """Tessellate, cut with the slice plane, transform into XY."""
        carrier = self._data_node
        if carrier is None or slice_node is None:
            return None
        source_cls = _resolve_surface_source()
        if source_cls is None:
            return None
        try:
            grid = carrier.GetControlGridVector()
            if len(grid) < 48:
                return None
            if self._surface_source is None:
                self._surface_source = source_cls()
                self._surface_source.SetResolution(20, 20)
            geometry = _control_points_digest(carrier)
            if geometry != self._last_fed_geometry:
                # Feed (and re-tessellate) ONLY on real geometry change: a
                # fresh vtkPoints always marks the source modified, so an
                # unconditional feed re-tessellated the full patch on every
                # pose-only recut -- three pipelines x every reslice event.
                points = vtk.vtkPoints()
                for base in range(0, 48, 3):
                    points.InsertNextPoint(grid[base], grid[base + 1], grid[base + 2])
                self._surface_source.SetControlPoints(points)
                self._last_fed_geometry = geometry

            to_ras = slice_node.GetSliceToRAS()
            self._cut_plane.SetOrigin(
                to_ras.GetElement(0, 3), to_ras.GetElement(1, 3), to_ras.GetElement(2, 3)
            )
            self._cut_plane.SetNormal(
                to_ras.GetElement(0, 2), to_ras.GetElement(1, 2), to_ras.GetElement(2, 2)
            )
            self._cutter.SetInputConnection(self._surface_source.GetOutputPort())

            xy_to_ras = vtk.vtkMatrix4x4()
            xy_to_ras.DeepCopy(slice_node.GetXYToRAS())
            xy_to_ras.Invert()
            self._xy_transform.SetMatrix(xy_to_ras)
            self._transform_filter.SetInputConnection(self._cutter.GetOutputPort())
            self._transform_filter.Update()
            output = self._transform_filter.GetOutput()
            self._contour_mapper.SetInputConnection(self._transform_filter.GetOutputPort())
            return output
        except Exception:  # pragma: no cover - defensive
            return None

    @staticmethod
    def _slice_matrix_digest(slice_node: Any) -> tuple:
        """A value digest of the slice pose (reslicing must recut)."""
        if slice_node is None:
            return ()
        try:
            m = slice_node.GetXYToRAS()
            s = slice_node.GetSliceToRAS()
            return tuple(
                round(mat.GetElement(r, c), 6)
                for mat in (m, s)
                for r in range(4)
                for c in range(4)
            )
        except Exception:  # pragma: no cover - defensive
            return ()

    # ------------------------------------------------------------------ #
    # Introspection
    # ------------------------------------------------------------------ #

    def GetDataNode(self) -> Any | None:  # noqa: N802 - VTK verb
        return self._data_node

    def GetContourActor(self) -> Any:  # noqa: N802 - VTK verb
        return self._contour_actor

    def GetContourPolyData(self) -> Any | None:  # noqa: N802 - VTK verb
        try:
            return self._transform_filter.GetOutput()
        except Exception:  # pragma: no cover - defensive
            return None

    # ------------------------------------------------------------------ #
    # Observers
    # ------------------------------------------------------------------ #

    def _attach_observer(self, node: Any) -> None:
        if node is None or not hasattr(node, "AddObserver"):
            return
        tag = node.AddObserver("ModifiedEvent", self._on_node_modified)
        self._observer_tags.setdefault(id(node), []).append(tag)
        if node not in self._observed_node_refs:
            self._observed_node_refs.append(node)

    def _detach_observer(self, node: Any) -> None:
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
        """Reconcile + repaint when the visible inputs actually changed."""
        del caller, event
        try:
            self.UpdatePipeline()

            render_key = (
                _safe_get_state(self._data_node),
                _control_points_digest(self._data_node),
                self._slice_matrix_digest(self._slice_node),
            )
            if render_key == self._last_render_key:
                return
            self._last_render_key = render_key
            self.RequestRender()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass


# --------------------------------------------------------------------------- #
# Pipeline-creator registration — ADR-0013 §5 call 3 (slice-view half)
# --------------------------------------------------------------------------- #


def registerSliceContourPipelineCreator() -> None:  # noqa: N802 - project convention
    """Register the ``SliceContourPipeline`` creator with LayerDM.

    Accepts ``(vtkMRMLSliceNode, vtkMRMLParametricSurfaceDisplayNode)``
    pairs only -- the slice-view complement of the 3D surface creator's
    3D-only gating.  Idempotent via the module-level flag.
    """
    global _REGISTERED
    if _REGISTERED:
        return

    from slicer import (  # type: ignore[import-not-found]
        vtkMRMLLayerDMPipelineFactory,
        vtkMRMLLayerDMPipelineScriptedCreator,
        vtkMRMLParametricSurfaceDisplayNode,
    )

    def tryCreate(viewNode, node):
        if not _creator_accepts_view(viewNode):
            return None
        if not isinstance(node, vtkMRMLParametricSurfaceDisplayNode):
            return None
        return SliceContourPipeline()

    creator = vtkMRMLLayerDMPipelineScriptedCreator()
    creator.SetPythonCallback(tryCreate)
    vtkMRMLLayerDMPipelineFactory.GetInstance().AddPipelineCreator(creator)
    _REGISTERED = True

# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""LayerDM Pipeline creators for volumetry seed placement (ADR-0038 / ADR-0013 §5).

ADR-0038 §Decision makes LiverVolumetry a thin CLIENT of the shared
control-point base: the base DRIVES the generic add-on-click / drag-to-edit-
nearest / delete / bare-move-decline arbitration
(``SurfacePointPlacementPipeline3D`` / ``...Slice``), and this module supplies
ONLY the volumetry-specific wiring through the base's injected seams -- the
flat ``VolumetrySeedProvider`` (data model) + the ``InVolumePick``
(``ADR-0038 §"Base extension"`` -- the in-volume/slice pick, not a surface
snap).  There is NO territory grouping and NO vessel gating (ADR-0038 §"What
is not shared"): volumetry is the simplest of the three clients.

The interaction state (arm / carrier / pick-surface) rides the SHARED
``vtkMRMLVolumetrySeedsDisplayNode`` via the base's ``PointPlacementState``
(namespaced ``LiverVolumetry.*``), NOT the Python pipeline instance LayerDM
does not drive (``feedback_layerdm_state_on_display_node``).  So the LayerDM-
created pipelines resolve the carrier + the labelmap from the display node at
creation and re-resolve on ``UpdatePipeline`` (the display node is added to the
scene before the widget binds the carrier reference).

Two creators, keyed disjointly (ADR-0013 §1 -- one pipeline per (view, type)):

* ``(vtkMRMLViewNode, vtkMRMLVolumetrySeedsDisplayNode)`` -> the 3D pipeline;
* ``(vtkMRMLSliceNode, vtkMRMLVolumetrySeedsDisplayNode)`` -> the slice pipeline.

Rendering + interaction route through these scripted Pipelines + their
creators, NEVER a custom displayable manager (ADR-0013 §5 /
``feedback_layerdm_no_custom_dm``).

References
----------
* ADR-0038 -- §Decision (client-of-the-base seam) + §"Base extension"
  (in-volume pick) + §"Consumers ledger" (LiverVolumetry client).
* ADR-0013 §1/§5 -- one pipeline per (view, type); the 3 registration calls;
  no custom displayable manager.
* VascularTerritoriesLib/TerritoryPlacementPipeline.py -- the client-of-the-base
  wiring idiom this mirrors (minus the territory grouping + vessel gating).
"""

from __future__ import annotations

from typing import Any

import vtk

# The shared 3D + slice placement/edit bases (ADR-0038 §Decision): volumetry is
# the flat, ungated client over the PointProvider + swappable-pick seam.
try:  # pragma: no cover - exercised once per import path
    from SlicerLiverInteractionLib.SurfacePointPlacementPipeline3D import (
        SurfacePointPlacementPipeline3D as _Pipeline3DBase,
    )
    from SlicerLiverInteractionLib.SurfacePointPlacementPipelineSlice import (
        SurfacePointPlacementPipelineSlice as _PipelineSliceBase,
    )
    from SlicerLiverInteractionLib.PointPlacementState import PointPlacementState
except ImportError:  # bare / top-level path: add the sibling Lib dir to sys.path
    import pathlib
    import sys as _sys

    _shared_lib = pathlib.Path(__file__).resolve().parents[2] / "SlicerLiverInteractionLib"
    if str(_shared_lib) not in _sys.path:
        _sys.path.insert(0, str(_shared_lib))
    from SurfacePointPlacementPipeline3D import (  # type: ignore[no-redef]
        SurfacePointPlacementPipeline3D as _Pipeline3DBase,
    )
    from SurfacePointPlacementPipelineSlice import (  # type: ignore[no-redef]
        SurfacePointPlacementPipelineSlice as _PipelineSliceBase,
    )
    from PointPlacementState import PointPlacementState  # type: ignore[no-redef]

# The shared slice-projection math (RAS interior point -> slice XY): the
# placement-preview cursor rides the SAME projection the base's handles do,
# so the preview glyph sits exactly where a placed seed's handle would.
try:  # pragma: no cover - exercised once per import path
    from SlicerLiverInteractionLib import SlicePointProjection as _proj
except ImportError:  # bare / top-level path: the sibling Lib is already on sys.path
    import SlicePointProjection as _proj  # type: ignore[no-redef]

try:  # pragma: no cover - exercised once per import path
    from .VolumetrySeedProvider import VolumetrySeedProvider
    from .InVolumePick import InVolumePick
except ImportError:  # top-level import path (the unit layer's sys.path setup)
    from VolumetrySeedProvider import VolumetrySeedProvider  # type: ignore[no-redef]
    from InVolumePick import InVolumePick  # type: ignore[no-redef]

#: The base namespace for the volumetry arm/carrier/pick state on the shared
#: display node (matches the display node's ``LiverVolumetry.*`` attribute
#: channel; vtkMRMLVolumetrySeedsDisplayNode header §"Field roster").
VOLUMETRY_NAMESPACE = "LiverVolumetry"

#: The placement-preview cursor colour (yellow, the shared hover hue): a
#: hollow ring that tracks the cursor over a seedable interior voxel BEFORE
#: the click, the slice analogue of the territory adhering marker.
PREVIEW_CURSOR_COLOR = (1.0, 0.9, 0.2)

#: The preview cursor glyph diameter (XY pixels): a touch smaller than a
#: placed handle so the "about to place" cue reads as a cursor, not a handle.
PREVIEW_GLYPH_SCALE_PX = 11.0

_REGISTERED_3D = False
_REGISTERED_SLICE = False


def _carrier_from_display(displayNode: Any):
    """The seed carrier the shared display node binds (``LiverVolumetry.carrier``)."""
    state = PointPlacementState(VOLUMETRY_NAMESPACE)
    return state.get_carrier(displayNode)


def _labelmap_from_display(displayNode: Any):
    """The target labelmap the in-volume pick resolves against (``pickSurface``)."""
    if displayNode is None or not hasattr(displayNode, "GetPickSurfaceNode"):
        return None
    return displayNode.GetPickSurfaceNode()


def _wire_provider_and_pick(pipeline: Any, displayNode: Any) -> None:
    """(Re)resolve the flat provider + the in-volume pick from the display node.

    Shared by the 3D + slice pipelines: the display node enters the scene
    before the widget binds the carrier reference, so both re-run this on
    ``UpdatePipeline`` (fired when the reference is set) to pick up the bound
    carrier + labelmap.
    """
    provider = VolumetrySeedProvider(_carrier_from_display(displayNode))
    provider.SetDisplayNode(displayNode)
    pipeline.SetProvider(provider)
    labelmap = _labelmap_from_display(displayNode)
    pipeline.SetPickProvider(InVolumePick(labelmap) if labelmap is not None else None)


class VolumetrySeedPipeline3D(_Pipeline3DBase):
    """The 3D volumetry seed placement pipeline (a thin base client).

    Created by LayerDM's manager for ``(vtkMRMLViewNode,
    vtkMRMLVolumetrySeedsDisplayNode)``.  Wires the flat volumetry provider +
    the in-volume pick from the shared display node; the base drives the
    add/grab/drag/delete arbitration.
    """

    def __init__(self) -> None:
        super().__init__(namespace=VOLUMETRY_NAMESPACE)

    def SetDisplayNode(self, displayNode: Any) -> None:  # noqa: N802 - VTK verb
        super().SetDisplayNode(displayNode)
        self._display_node = displayNode
        self._rewire()

    def OnRendererAdded(self, renderer: Any) -> None:  # noqa: N802 - VTK verb
        try:
            self._renderer = renderer
            if self._display_node is None:
                display = self.GetDisplayNode()
                if display is not None:
                    self.SetDisplayNode(display)
            self._rewire()
            self.RequestRender()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    def UpdatePipeline(self) -> None:  # noqa: N802 - VTK verb
        try:
            self._rewire()
            self.RequestRender()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass

    def _rewire(self) -> None:
        """(Re)resolve the provider + pick from the shared display node."""
        _wire_provider_and_pick(self, self._display_node)


class VolumetrySeedPipelineSlice(_PipelineSliceBase):
    """The slice volumetry seed placement pipeline (a thin base client).

    Created by LayerDM's manager for ``(vtkMRMLSliceNode,
    vtkMRMLVolumetrySeedsDisplayNode)``.  The slice analogue of the 3D pipeline:
    an armed slice click routes through the in-volume pick's slice-click seam so
    the seed lands on an interior labelled voxel of the target region.
    """

    def __init__(self) -> None:
        super().__init__(namespace=VOLUMETRY_NAMESPACE)

        # Placement-preview cursor: a hollow ring that tracks the cursor over a
        # seedable interior voxel BEFORE the click, so the surgeon sees where a
        # seed would land (the slice analogue of the territory adhering marker;
        # the base's hover ring only highlights EXISTING handles, so an empty
        # slice showed no placement cue at all -- the reported "no cursor").
        self._preview_polydata = vtk.vtkPolyData()
        self._preview_polydata.SetPoints(vtk.vtkPoints())
        self._preview_glyph_source = vtk.vtkGlyphSource2D()
        self._preview_glyph_source.SetGlyphTypeToCircle()
        self._preview_glyph_source.FilledOff()
        self._preview_glyph_source.SetScale(PREVIEW_GLYPH_SCALE_PX)
        self._preview_glyph = vtk.vtkGlyph2D()
        self._preview_glyph.SetInputData(self._preview_polydata)
        self._preview_glyph.SetSourceConnection(
            self._preview_glyph_source.GetOutputPort()
        )
        self._preview_glyph.ScalingOff()
        self._preview_mapper = vtk.vtkPolyDataMapper2D()
        self._preview_mapper.SetInputConnection(self._preview_glyph.GetOutputPort())
        self._preview_actor = vtk.vtkActor2D()
        self._preview_actor.SetMapper(self._preview_mapper)
        self._preview_actor.GetProperty().SetColor(*PREVIEW_CURSOR_COLOR)
        self._preview_actor.GetProperty().SetLineWidth(2.0)
        self._preview_actor.SetVisibility(False)

    def _after_display_node_set(self) -> None:
        _wire_provider_and_pick(self, self._display_node)

    def _add_actors(self, renderer: Any) -> None:
        super()._add_actors(renderer)
        renderer.AddActor2D(self._preview_actor)

    def _remove_actors(self, renderer: Any) -> None:
        super()._remove_actors(renderer)
        renderer.RemoveActor2D(self._preview_actor)

    def _on_bare_move_decline(self, eventData: Any) -> None:
        """Raise the placement-preview cursor on a declined bare move (ADR-0033).

        The base DECLINES a bare move (camera untouched) and returns WITHOUT a
        render, and a bare hover mutates no observed node -- so a placement cue
        is computed but never flushed unless this hook requests a render itself
        (the same mid-interaction ``RequestRender`` the territory
        ``_on_bare_move_decline`` follows).  Without it the surgeon gets no
        cursor/marker while placing seeds -- the reported regression.

        The preview only shows while ARMED (the add-on-click mode): a disarmed
        slice hover is edit-only, and the base's hover ring already cues the
        grab target, so a placement preview would be misleading there.
        """
        try:
            self._update_preview_cursor(eventData)
        finally:
            self.RequestRender()

    def _update_preview_cursor(self, eventData: Any) -> None:
        """Position the preview ring at the cursor's seedable interior voxel.

        Resolves the cursor through the SAME in-volume slice pick a click uses,
        then projects that interior RAS to the slice XY so the ring sits where
        the placed seed's handle would.  Hidden when disarmed, off any region,
        or beyond the local search radius (the pick declines) -- so the cursor
        cue truthfully tracks where a click WOULD place a seed.
        """
        show = False
        points = vtk.vtkPoints()
        if self.IsArmed() and self.IsModuleActive():
            world = self._pick_world(eventData)
            slice_node = self._slice_node
            if world is not None and slice_node is not None:
                xy = _proj.project_ras_to_xy(slice_node, world)
                if xy is not None:
                    points.InsertNextPoint(xy[0], xy[1], 0.0)
                    show = True
        self._preview_polydata.SetPoints(points)
        self._preview_polydata.Modified()
        self._preview_actor.SetVisibility(show)

    def _pick_world(self, eventData: Any):
        """Route the armed slice click through the in-volume slice-click pick.

        The base's default calls ``pick_for_event(eventData)``, but the
        in-volume pick resolves a slice click against the labelmap
        (``pick_for_slice_event(slice_node, display_xy)``), so this override
        supplies the slice node + the event pixel -- keeping the interior-voxel
        seed the only placement (ADR-0038 §"Base extension").
        """
        pick = self._pick_provider
        if pick is None:
            return None
        try:
            display_xy = eventData.GetDisplayPosition()
        except Exception:  # pragma: no cover - defensive (fake events)
            display_xy = None
        return pick.pick_for_slice_event(self._slice_node, display_xy)


def registerVolumetrySeedPipeline3DCreator() -> None:  # noqa: N802 - project convention
    """Register the 3D volumetry seed placement creator with LayerDM (ADR-0013 §5).

    Idempotent (module-level flag).  Matches ``(vtkMRMLViewNode,
    vtkMRMLVolumetrySeedsDisplayNode)`` -- the 3D views only; the slice creator
    accepts only ``vtkMRMLSliceNode``, so the (view-type, display-type) keying
    stays disjoint (ADR-0013 §1).  No custom displayable manager (ADR-0013 §5).
    """
    global _REGISTERED_3D
    if _REGISTERED_3D:
        return

    from slicer import (  # type: ignore[import-not-found]
        vtkMRMLLayerDMPipelineFactory,
        vtkMRMLLayerDMPipelineScriptedCreator,
        vtkMRMLVolumetrySeedsDisplayNode,
        vtkMRMLViewNode,
    )

    def tryCreate(viewNode, node):
        try:
            if not isinstance(viewNode, vtkMRMLViewNode):
                return None
            if not isinstance(node, vtkMRMLVolumetrySeedsDisplayNode):
                return None
            return VolumetrySeedPipeline3D()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            return None

    creator = vtkMRMLLayerDMPipelineScriptedCreator()
    creator.SetPythonCallback(tryCreate)
    vtkMRMLLayerDMPipelineFactory.GetInstance().AddPipelineCreator(creator)
    _REGISTERED_3D = True


def registerVolumetrySeedPipelineSliceCreator() -> None:  # noqa: N802 - project convention
    """Register the slice volumetry seed placement creator with LayerDM (ADR-0013 §5).

    Idempotent (module-level flag).  Matches ``(vtkMRMLSliceNode,
    vtkMRMLVolumetrySeedsDisplayNode)`` -- the slice views only; the 3D creator
    accepts only ``vtkMRMLViewNode`` (ADR-0013 §1).  No custom displayable
    manager (ADR-0013 §5).
    """
    global _REGISTERED_SLICE
    if _REGISTERED_SLICE:
        return

    from slicer import (  # type: ignore[import-not-found]
        vtkMRMLLayerDMPipelineFactory,
        vtkMRMLLayerDMPipelineScriptedCreator,
        vtkMRMLVolumetrySeedsDisplayNode,
    )

    def tryCreate(viewNode, node):
        try:
            if viewNode is None or not viewNode.IsA("vtkMRMLSliceNode"):
                return None
            if not isinstance(node, vtkMRMLVolumetrySeedsDisplayNode):
                return None
            return VolumetrySeedPipelineSlice()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            return None

    creator = vtkMRMLLayerDMPipelineScriptedCreator()
    creator.SetPythonCallback(tryCreate)
    vtkMRMLLayerDMPipelineFactory.GetInstance().AddPipelineCreator(creator)
    _REGISTERED_SLICE = True

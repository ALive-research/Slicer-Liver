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

    def _after_display_node_set(self) -> None:
        _wire_provider_and_pick(self, self._display_node)

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

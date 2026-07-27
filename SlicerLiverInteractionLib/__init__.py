# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Shared control-point interaction base (ADR-0038).

A Python Lib package (ADR-0004) hosting the interaction/visualization base
each module's LayerDM Pipeline creator instantiates; it hosts NO
displayable manager (ADR-0013 §5) and carries no data-model knowledge.
The ``Liver`` prefix is dropped on every class here (T2.7 convention).

Currently landed (ADR-0038 extraction):

* ``SurfacePick`` -- the pure-VTK ray->closed-surface intersect-nearest +
  closest-point fallback with a lazy MTime-invalidated ``vtkCellLocator``.
* ``PointPlacementState`` -- the arm/active/module-active/carrier accessors
  on a display node, with the attribute-key namespace parameterized per
  consumer.
* ``SlicePointProjection`` -- the pure-math slice-view projection / fade /
  side-tint / presence-cutoff (the slice base's geometry half).
* ``PointProvider`` / ``PickProvider`` -- the seam protocols the consumer
  supplies (data model + swappable click->world pick).

The Pipeline base classes (``SurfacePointPlacementPipeline3D`` /
``SurfacePointPlacementPipelineSlice``) import LayerDMLib and so are NOT
eagerly imported here (LayerDMLib is reachable only inside a launched
Slicer); a consumer imports them by module path, mirroring how the
resection / territory pipelines import ``LayerDMLib`` directly.
"""

from __future__ import annotations

from .SurfacePick import SurfacePick
from .PointPlacementState import PointPlacementState
from . import SlicePointProjection
from .PointProvider import PointProvider, PickProvider

__all__ = [
    "SurfacePick",
    "PointPlacementState",
    "SlicePointProjection",
    "PointProvider",
    "PickProvider",
]

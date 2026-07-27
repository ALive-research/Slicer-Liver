# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Shared control-point interaction base (ADR-0038).

A Python Lib package (ADR-0004) hosting the interaction/visualization base
each module's LayerDM Pipeline creator instantiates; it hosts NO
displayable manager (ADR-0013 §5) and carries no data-model knowledge.
The ``Liver`` prefix is dropped on every class here (T2.7 convention).

Currently landed (ADR-0038 extraction, first slice):

* ``SurfacePick`` -- the pure-VTK ray->closed-surface intersect-nearest +
  closest-point fallback with a lazy MTime-invalidated ``vtkCellLocator``.
* ``PointPlacementState`` -- the arm/active/module-active/carrier accessors
  on a display node, with the attribute-key namespace parameterized per
  consumer.

The Pipeline base classes + the ``PointProvider`` seam land in a later
slice of the extraction.
"""

from __future__ import annotations

from .SurfacePick import SurfacePick
from .PointPlacementState import PointPlacementState

__all__ = [
    "SurfacePick",
    "PointPlacementState",
]

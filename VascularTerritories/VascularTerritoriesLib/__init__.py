# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""VascularTerritories Python sub-package.

Hosts the pure-Python pieces of the vessel-adhering-highlight feature.
The pick core (``VesselSurfacePick``) is the pure-VTK snap math
(ADR-0004); later increments add the LayerDM highlight pipeline.
"""

from __future__ import annotations

from .VesselSurfacePick import VesselSurfacePick

__all__ = ["VesselSurfacePick"]

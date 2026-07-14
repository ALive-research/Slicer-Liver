# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""VascularTerritories Python sub-package.

Hosts the pure-Python pieces of the vessel-adhering-highlight feature.
The pick core (``VesselSurfacePick``) is the pure-VTK snap math
(ADR-0004); later increments add the LayerDM highlight pipeline.
"""

from __future__ import annotations

from .VesselSurfacePick import VesselSurfacePick
from .VesselHighlightWiring import (
    closed_surface_polydata,
)

# The LayerDM highlight Pipeline import depends on LayerDMLib (reachable
# only from a launched Slicer with the SlicerLayerDisplayableManager
# extension on the path); guard it so the bare unit layer can still import
# the package for the pure-VTK pick core alone (the ControlPolygonPipeline
# precedent).
try:
    from .VesselHighlightPipeline import (
        VesselHighlightPipeline,
        registerVesselHighlightPipelineCreator,
    )
except ImportError:  # pragma: no cover - LayerDMLib unreachable bare
    VesselHighlightPipeline = None
    registerVesselHighlightPipelineCreator = None

# The annotation placement/edit Pipeline (ADR-0037 §Decision 2) has the same
# LayerDMLib dependency; guard it the same way.
try:
    from .TerritoryPlacementPipeline import (
        TerritoryPlacementPipeline,
        registerTerritoryPlacementPipelineCreator,
    )
except ImportError:  # pragma: no cover - LayerDMLib unreachable bare
    TerritoryPlacementPipeline = None
    registerTerritoryPlacementPipelineCreator = None

__all__ = [
    "VesselSurfacePick",
    "closed_surface_polydata",
    "VesselHighlightPipeline",
    "registerVesselHighlightPipelineCreator",
    "TerritoryPlacementPipeline",
    "registerTerritoryPlacementPipelineCreator",
]

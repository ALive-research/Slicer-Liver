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

# The Stage-3 transient VMTK-seed builder core (ADR-0037 §Decision 4) is
# dependency-free (no slicer/vtk/Qt) so it imports unconditionally alongside
# the pure pick core.
from .TransientVmtkSeeds import build_seed_payload

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

# The slice-view annotation Pipeline (ADR-0037 §2D placement) is the slice
# complement of the placement Pipeline; same LayerDMLib dependency, guarded
# the same way.
try:
    from .TerritorySlicePipeline import (
        TerritorySlicePipeline,
        registerTerritorySlicePipelineCreator,
    )
except ImportError:  # pragma: no cover - LayerDMLib unreachable bare
    TerritorySlicePipeline = None
    registerTerritorySlicePipelineCreator = None

# The Stage-2 annotation table widget (ADR-0037 §Decision 3) needs Qt
# (``qt.QTableWidget``); guard it so the bare unit layer can still import the
# package for the pure-VTK pick core alone.
try:
    from .TerritoriesTableWidget import TerritoriesTableWidget
except (ImportError, AttributeError):  # pragma: no cover - Qt unreachable bare
    # A bare ``PythonSlicer -m pytest`` provides a ``qt`` stub without
    # ``qt.Qt``; the module-scope ``qt.Qt.UserRole`` read then raises
    # ``AttributeError`` (not ``ImportError``).  Guard both so the pure
    # builder core (ADR-0037 §Decision 4) stays importable bare.
    TerritoriesTableWidget = None

__all__ = [
    "VesselSurfacePick",
    "closed_surface_polydata",
    "build_seed_payload",
    "VesselHighlightPipeline",
    "registerVesselHighlightPipelineCreator",
    "TerritoryPlacementPipeline",
    "registerTerritoryPlacementPipelineCreator",
    "TerritorySlicePipeline",
    "registerTerritorySlicePipelineCreator",
    "TerritoriesTableWidget",
]

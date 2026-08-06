# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""LiverVolumetry Python sub-package (ADR-0038 seeds-off-markups client).

Hosts the pure-Python pieces of the volumetry seeds-off-markups migration:
the carrier->transient-fiducial adapter (the C++ compute is fed a transient
fiducial built from the seed carrier, ADR-0015 unchanged), the flat
``VolumetrySeedProvider`` (the ADR-0038 PointProvider adapter), the in-volume
slice-click pick (ADR-0038 §"Base extension"), and the LayerDM Pipeline creator
registrations (ADR-0013 §5, no custom displayable manager).
"""

from __future__ import annotations

# The pure carrier->transient-fiducial adapter (ADR-0038 §Conformance) is
# dependency-free at the mapping core (no slicer/vtk/Qt at import), so it imports
# unconditionally -- the bare unit layer reaches ``build_fiducial_payload``.
from .TransientVolumetrySeeds import (
    build_fiducial_payload,
    build_transient_fiducial,
    seeds_from_carrier,
)

# The flat PointProvider adapter + the in-volume pick are pure Python (vtk is
# imported lazily inside the pick's methods), so they import unconditionally too.
from .VolumetrySeedProvider import VolumetrySeedProvider
from .InVolumePick import InVolumePick

# The seed->label capture resolution rule (``territory-usability``): the pure
# ordering function is dependency-free and the scene-side gatherer imports
# slicer/vtk lazily, so this imports unconditionally (the bare unit layer
# reaches ``resolve_touched_candidates``).
from .SeedTargetResolution import (
    gather_touched_candidates,
    resolve_touched_candidates,
)

# The visibility-composed carve rule (territory-usability): the pure ordering /
# carving / restore functions are dependency-free (numpy lazily inside the mask
# carve) and the scene-side context gatherer is plain attribute access, so this
# imports unconditionally (the bare unit layer reaches the carve core).
from .VisibilityCarve import (
    apply_visibility_context,
    carve_effective_mask,
    order_visible_top_first,
    segments_above,
    visible_context,
)

# The carved-region marching-stripes highlight (territory-usability): the
# stripe geometry / plane cut / highlight-state helpers are pure numpy +
# attribute access, so this imports unconditionally (the bare unit layer
# reaches the stripe core).
from .CarvedRegionStripes import (
    HIGHLIGHT_SEED_ATTRIBUTE,
    STRIPE_PERIOD_PX,
    STRIPE_PHASE_ATTRIBUTE,
    STRIPE_TICK_MS,
    get_highlight_seed,
    get_stripe_phase,
    resample_mask_to_plane,
    set_highlight_seed,
    set_stripe_phase,
    stripe_segments,
)

# The per-volume segment aggregation (territory-usability compute-per-volume) is
# a pure, side-effect-free fold over the carrier, so it imports unconditionally
# (the bare unit layer reaches ``distinct_bound_segments_per_volume``).
from .VolumeSegmentAggregation import (
    distinct_bound_segments_per_volume,
    effective_regions_per_volume,
)

# The LayerDM Pipeline creators depend on the shared base (LayerDMLib, reachable
# only from a launched Slicer with the SlicerLayerDisplayableManager extension on
# the path); guard them so the bare unit layer can still import the package for
# the pure cores alone (the VascularTerritoriesLib precedent).
try:
    from .VolumetrySeedPipeline import (
        VolumetrySeedPipeline3D,
        VolumetrySeedPipelineSlice,
        registerVolumetrySeedPipeline3DCreator,
        registerVolumetrySeedPipelineSliceCreator,
    )
except ImportError:  # pragma: no cover - LayerDMLib unreachable bare
    VolumetrySeedPipeline3D = None
    VolumetrySeedPipelineSlice = None
    registerVolumetrySeedPipeline3DCreator = None
    registerVolumetrySeedPipelineSliceCreator = None

# The carrier-backed seeds table (ADR-0038 §Conformance) is a Python-composed
# Qt widget (ADR-0004), so it imports ``qt`` / ``ctk`` at module load; those
# resolve only inside a launched Slicer.  Guard the import so the bare unit
# layer can still reach the pure cores above (the VolumetrySeedPipeline
# precedent).
try:
    from .VolumetrySeedsTableWidget import VolumetrySeedsTableWidget
except (ImportError, AttributeError):  # pragma: no cover - Qt/ctk unreachable bare
    # Bare ``qt`` imports but lacks ``qt.QWidget`` (no qSlicerApplication), so
    # the class body raises AttributeError, not ImportError -- catch both so
    # the pure cores above stay importable bare (the VascularTerritoriesLib
    # precedent).
    VolumetrySeedsTableWidget = None

__all__ = [
    "build_fiducial_payload",
    "build_transient_fiducial",
    "seeds_from_carrier",
    "VolumetrySeedProvider",
    "InVolumePick",
    "gather_touched_candidates",
    "resolve_touched_candidates",
    "apply_visibility_context",
    "carve_effective_mask",
    "order_visible_top_first",
    "segments_above",
    "visible_context",
    "HIGHLIGHT_SEED_ATTRIBUTE",
    "STRIPE_PERIOD_PX",
    "STRIPE_PHASE_ATTRIBUTE",
    "STRIPE_TICK_MS",
    "get_highlight_seed",
    "get_stripe_phase",
    "resample_mask_to_plane",
    "set_highlight_seed",
    "set_stripe_phase",
    "stripe_segments",
    "distinct_bound_segments_per_volume",
    "effective_regions_per_volume",
    "VolumetrySeedPipeline3D",
    "VolumetrySeedPipelineSlice",
    "registerVolumetrySeedPipeline3DCreator",
    "registerVolumetrySeedPipelineSliceCreator",
    "VolumetrySeedsTableWidget",
]

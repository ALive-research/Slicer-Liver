# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Compatibility re-export of the shared ``SlicePointProjection`` math.

ADR-0038 §Context named the slice projection into XY (``inverse(XYToRAS)``),
the distance-graded alpha, the signed above/below side tint, and the HARD
presence cutoff as duplicated surface -- carried near-verbatim here and in
``LiverResectionsLib.SliceControlPolygonPipeline``.  The extraction hoisted
that math into ``SlicerLiverInteractionLib.SlicePointProjection``; this
module now re-exports it so existing call sites (``TerritorySlicePipeline``)
and the territory characterization suite keep working unchanged (the
extraction is behaviour-preserving -- ADR-0038 [review]).

The dual import mirrors the ``<Module>Lib`` idiom: the installed/built tree
stages ``SlicerLiverInteractionLib`` alongside this package; the bare unit
layer sets ``sys.path`` to the individual Lib dir, so a sibling-directory
fallback keeps the shared core importable there too.
"""

from __future__ import annotations

try:
    from SlicerLiverInteractionLib.SlicePointProjection import (  # noqa: F401
        FADE_DISTANCE_MM,
        PICK_RANGE_MM,
        SIDE_TINT_MAX,
        apply_matrix_xy,
        fade_alpha,
        inverse_xy_to_ras,
        is_present,
        normal_ray,
        project_ras_to_xy,
        side_tint,
        signed_distance,
        signed_distance_to_slice,
        slice_frame,
        xy_to_ras_on_plane,
    )
except ImportError:  # bare unit layer: add the sibling Lib dir to sys.path
    import pathlib
    import sys

    _shared_lib = pathlib.Path(__file__).resolve().parents[2] / "SlicerLiverInteractionLib"
    if str(_shared_lib) not in sys.path:
        sys.path.insert(0, str(_shared_lib))
    from SlicePointProjection import (  # type: ignore[no-redef]  # noqa: F401
        FADE_DISTANCE_MM,
        PICK_RANGE_MM,
        SIDE_TINT_MAX,
        apply_matrix_xy,
        fade_alpha,
        inverse_xy_to_ras,
        is_present,
        normal_ray,
        project_ras_to_xy,
        side_tint,
        signed_distance,
        signed_distance_to_slice,
        slice_frame,
        xy_to_ras_on_plane,
    )

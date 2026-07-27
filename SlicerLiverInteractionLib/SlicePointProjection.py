# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Pure-math slice projection for surface control points (ADR-0038).

The slice-view control-point base (``SurfacePointPlacementPipelineSlice``)
projects a consumer's control points into a slice view's XY space, fades
them by their distance to the slice plane, applies a signed above/below
side tint, and casts a snap ray along the slice normal.  Those operations
are pure geometry given a slice node exposing ``GetXYToRAS`` /
``GetSliceToRAS`` (4x4 ``vtkMatrix4x4``) -- no LayerDM, no GL, no Slicer
scene -- so they live here as module-level functions the bare unit layer
can exercise directly (the ``SurfacePick`` pure-VTK-helper split
precedent).

ADR-0038 §Context names the slice projection into XY (``inverse(XYToRAS)``),
the distance-graded alpha, the signed above/below side tint, and the HARD
presence cutoff (2D alpha is unreliable) as the surface the base owns.  The
resection slice pipeline (``SliceControlPolygonPipeline``, ADR-0033) and the
vascular-territories slice pipeline (``TerritorySlicePipeline``, ADR-0037)
carried near-verbatim copies of this math; this module is the single source
they now both share (``TerritorySliceProjection`` re-exports it).

Imports ``vtk`` only (for the matrix arithmetic); the slice node is passed
in and duck-typed.
"""

from __future__ import annotations

from typing import Any

#: Distance (mm) over which the projection fades to fully transparent --
#: the above/below-the-plane cue.  Short by design: only control points
#: NEAR the plane are present in a slice at all.
FADE_DISTANCE_MM = 15.0

#: Presence == visibility: a point at / beyond ``FADE_DISTANCE_MM`` is
#: absent (2D alpha is unreliable, so presence is a HARD cutoff, not a
#: faded-to-zero alpha -- the ADR-0033 slice-polygon rule).
PICK_RANGE_MM = FADE_DISTANCE_MM

#: Maximum lightness shift for the above/below-plane cue: points ABOVE the
#: plane tint toward white, below toward black, graded by distance.
#: Sign-neutral, so it composes with any per-point colour and stays
#: colourblind-legible.
SIDE_TINT_MAX = 0.55


def slice_frame(slice_node: Any):
    """``(origin, unit_normal)`` of the slice plane in RAS, or ``None``.

    Reads the slice-to-RAS matrix's translation (origin) + normalized
    third column (plane normal).  ``None`` when no slice node / matrix.
    """
    if slice_node is None:
        return None
    try:
        to_ras = slice_node.GetSliceToRAS()
    except Exception:  # pragma: no cover - defensive (fake nodes)
        return None
    if to_ras is None:
        return None
    origin = [to_ras.GetElement(r, 3) for r in range(3)]
    normal = [to_ras.GetElement(r, 2) for r in range(3)]
    norm = sum(n * n for n in normal) ** 0.5 or 1.0
    normal = [n / norm for n in normal]
    return origin, normal


def signed_distance(origin, normal, point) -> float:
    """Signed distance (mm) from ``point`` to a plane ``(origin, unit normal)``.

    Positive on the ``+normal`` side, negative on the other.  The per-point
    primitive the reproject loop calls after resolving the frame ONCE.
    """
    return sum(n * (p - o) for n, p, o in zip(normal, point, origin))


def signed_distance_to_slice(slice_node: Any, point) -> float:
    """Signed distance (mm) from ``point`` (RAS) to the slice plane.

    Positive ABOVE the plane (along the slice normal), negative below.
    ``+inf`` when the slice frame cannot be resolved.  Convenience wrapper
    resolving the frame per call -- for a loop, resolve ``slice_frame`` once
    and call :func:`signed_distance`.
    """
    frame = slice_frame(slice_node)
    if frame is None:
        return float("inf")
    return signed_distance(frame[0], frame[1], point)


def inverse_xy_to_ras(slice_node: Any):
    """The slice's ``inverse(XYToRAS)`` as a ``vtkMatrix4x4``, or ``None``.

    Resolved ONCE per reproject and reused for every point (the
    ``SliceControlPolygonPipeline`` convention).
    """
    if slice_node is None:
        return None
    try:
        import vtk

        ras_to_xy = vtk.vtkMatrix4x4()
        ras_to_xy.DeepCopy(slice_node.GetXYToRAS())
        ras_to_xy.Invert()
    except Exception:  # pragma: no cover - defensive (fake nodes)
        return None
    return ras_to_xy


def apply_matrix_xy(ras_to_xy, point):
    """Map an RAS ``point`` through a pre-built ``inverse(XYToRAS)`` to XY."""
    xy = ras_to_xy.MultiplyPoint((point[0], point[1], point[2], 1.0))
    w = xy[3] or 1.0
    return xy[0] / w, xy[1] / w


def project_ras_to_xy(slice_node: Any, point):
    """Project an RAS ``point`` into the slice view's XY space, or ``None``.

    Uses ``inverse(XYToRAS)`` -- the slice-view display coordinates coincide
    with this XY space (the slice renderer convention, shared with
    ``SliceControlPolygonPipeline``).  Convenience wrapper building the
    inverse per call -- for a loop, build it once via
    :func:`inverse_xy_to_ras` and call :func:`apply_matrix_xy`.
    """
    ras_to_xy = inverse_xy_to_ras(slice_node)
    if ras_to_xy is None:
        return None
    return apply_matrix_xy(ras_to_xy, point)


def xy_to_ras_on_plane(slice_node: Any, ex: float, ey: float):
    """Resolve a slice-view pixel ``(ex, ey)`` to its RAS point ON the plane.

    ``XYToRAS`` maps the in-plane pixel (z=0) straight onto the slice
    plane, so this is the click's landing point before the normal-ray snap.
    ``None`` when the matrix cannot be read.
    """
    if slice_node is None:
        return None
    try:
        xy_to_ras = slice_node.GetXYToRAS()
        ras = xy_to_ras.MultiplyPoint((float(ex), float(ey), 0.0, 1.0))
    except Exception:  # pragma: no cover - defensive (fake nodes)
        return None
    w = ras[3] or 1.0
    return ras[0] / w, ras[1] / w, ras[2] / w


def normal_ray(slice_node: Any, ras_point, extent_mm: float = 1000.0):
    """A world ray ``(p1, p2)`` through ``ras_point`` ALONG the slice normal.

    Casts from ``ras_point + extent * normal`` to ``ras_point - extent *
    normal`` so a surface pick can snap the point onto the surface the slice
    cuts (ADR-0038 §"Base extension"; the pick step is swappable).  ``None``
    when the slice frame cannot be resolved.
    """
    frame = slice_frame(slice_node)
    if frame is None:
        return None
    _origin, normal = frame
    p1 = tuple(ras_point[i] + normal[i] * extent_mm for i in range(3))
    p2 = tuple(ras_point[i] - normal[i] * extent_mm for i in range(3))
    return p1, p2


def is_present(distance_mm: float) -> bool:
    """True iff a point at ``|distance_mm|`` is present in the slice.

    The HARD presence cutoff (2D alpha unreliable): a point at / beyond
    ``PICK_RANGE_MM`` is absent -- not faded-to-zero (ADR-0033).
    """
    return abs(distance_mm) < PICK_RANGE_MM


def fade_alpha(distance_mm: float) -> float:
    """Linear fade [0, 1] of a point by ``|distance_mm|`` to the plane."""
    return max(0.0, 1.0 - abs(distance_mm) / FADE_DISTANCE_MM)


def side_tint(rgb, signed_distance: float):
    """Blend ``rgb`` toward white (above the plane) or black (below).

    The signed above/below cue shared across every slice-projected control
    surface (ADR-0038 §Context).
    """
    fraction = min(1.0, abs(signed_distance) / FADE_DISTANCE_MM) * SIDE_TINT_MAX
    target = 255 if signed_distance > 0 else 0
    return [int(c + (target - c) * fraction) for c in rgb]

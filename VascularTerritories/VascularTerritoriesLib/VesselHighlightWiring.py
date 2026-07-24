# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Shared surface-resolution seam for the vessel highlight (ADR-0037).

:func:`closed_surface_polydata` resolves a segmentation node's whole
closed-surface mesh as one ``vtkPolyData`` (the pick target) — the single
seam shared by the hover ``VesselHighlightPipeline`` and the
``TerritoryPlacementPipeline``, so neither duplicates the
representation-building logic (mirrors the module's ``polyDataFromNode``
precedent).  Placement + snap live on the LayerDM
``TerritoryPlacementPipeline`` against the annotation carrier, not a
markup observer (ADR-0037).

Imports ``vtk`` only; Slicer-aware through duck typing (the segmentation
node is passed in), so it is unit-testable without a GUI widget.
"""

from __future__ import annotations

from typing import Any

import vtk


# Vascular segment SCT *type* codes -- mirror ``vtkSlicerVascularTerritoriesLogic``
# ``VascularTypeTokens`` so the Python pick surface and the C++ extraction surface
# agree on what a "vessel" is: Vein / Artery, the broad concepts the real data
# uses (category Tissue) rather than portal/hepatic-specific codes (ADR-0011).
VASCULAR_TYPE_TOKENS = ("SCT^29092000", "SCT^51114001")


def _segment_is_vascular(segment: Any) -> bool:
    """True when the segment's ``TerminologyEntry`` type is a vascular concept."""
    if segment is None:
        return False
    ref = vtk.reference("")
    if not segment.GetTag("TerminologyEntry", ref):
        return False
    term = str(ref)
    return any(token in term for token in VASCULAR_TYPE_TOKENS)


def visibility_mtime(segmentation: Any) -> int:
    """The segmentation display node's MTime (bumps on a segment-visibility toggle).

    The pick pipelines cache the vessels-only surface; they compare this MTime
    to know when to rebuild so a hide/show in the structures table takes effect
    live.  Returns ``0`` when there is no display node (nothing to invalidate on).
    """
    try:
        display = segmentation.GetDisplayNode() if segmentation is not None else None
        return int(display.GetMTime()) if display is not None else 0
    except Exception:  # pragma: no cover - C++ boundary must never raise
        return 0


def _segment_is_visible(display_node: Any, segment_id: str) -> bool:
    """True when ``segment_id`` is shown on ``display_node`` (or no display node).

    A missing display node means visibility is unknown -- treat as visible so
    placement never silently dies when the display handle is unavailable.
    """
    if display_node is None:
        return True
    getter = getattr(display_node, "GetSegmentVisibility", None)
    if getter is None:
        return True
    return bool(getter(segment_id))


def _append_closed_surfaces(segmentation: Any, predicate):
    """Append the closed surfaces of the segments passing ``predicate``.

    ``predicate=None`` appends every segment; otherwise ``predicate`` is called
    ``predicate(segment, segment_id)``.  Returns ``None`` on any failure or when
    no segment contributes geometry (the caller treats ``None`` as "no surface").
    """
    if segmentation is None:
        return None
    try:
        segmentation.CreateClosedSurfaceRepresentation()
        seg = segmentation.GetSegmentation()
        ids = vtk.vtkStringArray()
        seg.GetSegmentIDs(ids)
        append = vtk.vtkAppendPolyData()
        for i in range(ids.GetNumberOfValues()):
            segment_id = ids.GetValue(i)
            if predicate is not None and not predicate(seg.GetSegment(segment_id), segment_id):
                continue
            mesh = vtk.vtkPolyData()
            segmentation.GetClosedSurfaceRepresentation(segment_id, mesh)
            if mesh.GetNumberOfPoints() > 0:
                append.AddInputData(mesh)
        if append.GetNumberOfInputConnections(0) == 0:
            return None
        append.Update()
        return append.GetOutput()
    except Exception:  # pragma: no cover - defensive (unbuilt reps, C++ boundary)
        return None


def closed_surface_polydata(segmentation: Any):
    """The segmentation's whole closed-surface mesh as one ``vtkPolyData``.

    Appends EVERY segment.  Retained for callers that legitimately need the
    whole surface; the pick/snap path uses :func:`vascular_surface_polydata`
    so the cursor never snaps to the liver parenchyma or a tumour (ADR-0037).
    """
    return _append_closed_surfaces(segmentation, None)


def per_segment_vascular_surfaces(segmentation: Any) -> list:
    """The vascular segments as ``[(segId, closed_surface, visible)]``.

    Mirrors the extractor's ``_perSegmentClosedSurfaces`` split (each
    vascular-SCT segment's closed-surface rep) plus each segment's live
    VISIBILITY on the display node.  The seed pipelines use it to map each seed
    to its nearest STRUCTURE and omit seeds whose structure is hidden -- so
    hiding a vessel in the structures table hides its seeds live (ADR-0037
    slice 5).  Returns ``[]`` when nothing resolves (a model node, an unbuilt
    rep, or the C++ boundary raising).
    """
    if segmentation is None or not hasattr(segmentation, "GetSegmentation"):
        return []
    display_node = segmentation.GetDisplayNode()
    try:
        segmentation.CreateClosedSurfaceRepresentation()
        seg = segmentation.GetSegmentation()
        ids = vtk.vtkStringArray()
        seg.GetSegmentIDs(ids)
        surfaces = []
        for i in range(ids.GetNumberOfValues()):
            segment_id = ids.GetValue(i)
            if not _segment_is_vascular(seg.GetSegment(segment_id)):
                continue
            mesh = vtk.vtkPolyData()
            segmentation.GetClosedSurfaceRepresentation(segment_id, mesh)
            if mesh.GetNumberOfPoints() == 0:
                continue
            surfaces.append(
                (segment_id, mesh, _segment_is_visible(display_node, segment_id))
            )
        return surfaces
    except Exception:  # pragma: no cover - defensive (unbuilt reps, C++ boundary)
        return []


class VisibleStructuresCache:
    """Per-pipeline cache of a display node's per-segment vessel structures.

    Resolves the ``[(segId, surface, visible)]`` structures from a highlight
    display node's ``pickSurface`` and caches them by the segmentation's
    visibility MTime, so a show/hide repaints seeds without re-running the
    closed-surface split per event (ADR-0037 slice 5).  Shared by the 3D
    ``TerritoryPlacementPipeline`` and 2D ``TerritorySlicePipeline`` seed
    filters so neither duplicates the resolution + cache.  Returns ``[]`` when
    no segmentation is wired (a test-injected pick) -> seeds are never hidden
    bare.
    """

    def __init__(self) -> None:
        self._surfaces: list | None = None
        self._mtime: int | None = None

    def resolve(self, display_node: Any) -> list:
        if display_node is None or not hasattr(display_node, "GetPickSurfaceNode"):
            return []
        segmentation = display_node.GetPickSurfaceNode()
        if segmentation is None:
            return []
        mtime = visibility_mtime(segmentation)
        if self._surfaces is not None and mtime == self._mtime:
            return self._surfaces
        self._surfaces = per_segment_vascular_surfaces(segmentation)
        self._mtime = mtime
        return self._surfaces


def seed_structure_visible(per_segment_surfaces: list, point: Any) -> bool:
    """True when ``point``'s nearest structure is VISIBLE (or maps to none).

    ``per_segment_surfaces`` is the ``[(segId, surface, visible)]`` list from
    :func:`per_segment_vascular_surfaces`.  The point is mapped to its nearest
    structure exactly as extraction groups it
    (``SeedStructureMapping.nearest_structure``), and the seed is shown iff that
    structure is visible.  With no resolvable structures (a model-node input, an
    unbuilt rep) the seed is treated as visible -- the show/hide follow has
    nothing to gate on, so placement is never silently swallowed (ADR-0037
    slice 5).
    """
    if not per_segment_surfaces:
        return True
    keyed = [(segId, surface) for segId, surface, _visible in per_segment_surfaces]
    visible_by_id = {segId: visible for segId, _surface, visible in per_segment_surfaces}
    # nearest_structure lives in the pure SeedStructureMapping helper; import it
    # lazily so this module stays dependency-light for its other callers.
    try:
        from .SeedStructureMapping import nearest_structure
    except ImportError:  # top-level import path (the unit layer's sys.path setup)
        from SeedStructureMapping import nearest_structure  # type: ignore[no-redef]
    key = nearest_structure(keyed, point)
    if key is None:
        return True
    return bool(visible_by_id.get(key, True))


def vascular_surface_polydata(segmentation: Any):
    """The pick/snap surface: VISIBLE, vascular-SCT-typed segments only.

    Appends a segment iff it is BOTH (a) vascular -- its ``TerminologyEntry``
    type is a vessel concept (:data:`VASCULAR_TYPE_TOKENS`), so the parenchyma
    (liver ``SCT^10200004``) and tumours are excluded -- AND (b) VISIBLE on the
    segmentation's display node.  Hiding a vessel (e.g. via the panel's
    structures table) therefore removes it from collision detection: the cursor
    can only snap to a vessel you can see, so hiding the hepatic system lets a
    click land on the portal even where they overlap (ADR-0037 slice 5).  The
    connectivity + highlight share this surface, so a hidden tree drops out of
    all three.  ``None`` when no visible vessel contributes.
    """
    display_node = segmentation.GetDisplayNode() if segmentation is not None else None

    def _visible_vascular(segment, segment_id):
        return _segment_is_vascular(segment) and _segment_is_visible(display_node, segment_id)

    return _append_closed_surfaces(segmentation, _visible_vascular)

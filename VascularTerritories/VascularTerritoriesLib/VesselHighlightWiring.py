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

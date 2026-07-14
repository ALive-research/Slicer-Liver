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


def closed_surface_polydata(segmentation: Any):
    """The segmentation's whole closed-surface mesh as one ``vtkPolyData``.

    Creates the closed-surface representation if absent and appends every
    segment so the pick/snap sees the whole vessel tree.  Returns ``None``
    on any failure or an empty segmentation (the caller treats ``None`` as
    "no surface").
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
            mesh = vtk.vtkPolyData()
            segmentation.GetClosedSurfaceRepresentation(ids.GetValue(i), mesh)
            if mesh.GetNumberOfPoints() > 0:
                append.AddInputData(mesh)
        if append.GetNumberOfInputConnections(0) == 0:
            return None
        append.Update()
        return append.GetOutput()
    except Exception:  # pragma: no cover - defensive (unbuilt reps, C++ boundary)
        return None

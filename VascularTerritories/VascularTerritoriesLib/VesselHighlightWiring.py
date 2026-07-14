# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Widget-side wiring for the vessel-adhering highlight (ADR-0013, ADR-0036).

Two responsibilities the module widget delegates here so they stay unit
testable outside the Qt/GUI shell:

* :func:`closed_surface_polydata` — resolve a segmentation node's whole
  closed-surface mesh as one ``vtkPolyData`` (the pick target).  This is
  the single surface-resolution seam shared by the hover Pipeline and the
  snap-on-place path, so neither duplicates the representation-building
  logic (mirrors the module's ``polyDataFromNode`` precedent).
* :func:`snap_control_point_to_surface` — rewrite a just-placed markup
  control point onto the referenced segmentation's surface (the snap the
  widget triggers on ``PointPositionDefinedEvent``).  Off-surface clicks
  fall to the nearest-surface projection; a raw (un-snapped) point is
  kept only when there is no mesh at all.  The reposition is guarded so
  it fires exactly once per placed point and does not recurse on the
  ``Modified`` its own rewrite emits.

The snap re-uses the pure-VTK ``VesselSurfacePick`` core (ADR-0025); the
highlight is a SEPARATE instance from the resection locator (ADR-0036),
not ``vtkMRMLLocatorNode``.

This module imports ``vtk`` only; it is Slicer-aware only through duck
typing (the segmentation/markup nodes are passed in), so the snap logic is
launched-testable against a real scene without a GUI widget.
"""

from __future__ import annotations

from typing import Any

import vtk

try:  # pragma: no cover - exercised once per import path
    from .VesselSurfacePick import VesselSurfacePick
except ImportError:  # top-level import path (the unit layer's sys.path setup)
    from VesselSurfacePick import VesselSurfacePick  # type: ignore[no-redef]


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


def snap_control_point_to_surface(markupsNode, pointIndex, segmentation) -> bool:  # noqa: N803 - VTK/Slicer arg names
    """Snap ``markupsNode``'s control point ``pointIndex`` onto the surface.

    The just-placed point's world position is projected onto
    ``segmentation``'s closed surface (nearest-surface projection; a ray is
    not available at placement time, so the projection path of the pick
    core is used with the raw point as the fallback).  When there is NO
    surface (no segmentation, or an empty/failed mesh) the point is left at
    its raw position — graceful degradation, the pick core's contract.

    Returns ``True`` when the point was moved, ``False`` when it was left
    raw.  The caller (the widget's ``PointPositionDefinedEvent`` observer)
    owns the re-entrancy latch; this function performs exactly one
    ``SetNthControlPointPositionWorld`` and never re-enters, so a single
    net reposition per placed point is guaranteed.
    """
    if markupsNode is None or pointIndex is None or pointIndex < 0:
        return False
    if pointIndex >= markupsNode.GetNumberOfControlPoints():
        return False

    polydata = closed_surface_polydata(segmentation)
    if polydata is None:
        return False

    raw = [0.0, 0.0, 0.0]
    markupsNode.GetNthControlPointPositionWorld(pointIndex, raw)
    raw_point = (raw[0], raw[1], raw[2])

    pick = VesselSurfacePick(polydata)
    # No cursor ray at placement time: feed a degenerate ray (the point to
    # itself) so the pick misses and falls to the nearest-surface
    # projection of the raw point — the snap target.
    snapped = pick.pick(raw_point, raw_point, fallback_point=raw_point)
    if snapped is None:
        return False

    markupsNode.SetNthControlPointPositionWorld(
        pointIndex, snapped[0], snapped[1], snapped[2]
    )
    return True

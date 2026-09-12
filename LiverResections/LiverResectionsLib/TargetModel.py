# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Target-organ model wiring: canonical liver segment -> carrier weakref.

The slicing-plane initialization and the commit-boundary ring extraction
consume the carrier's weakref'd target mesh (ADR-0014 §1,
``vtkMRMLBezierSurfaceNode.GetTargetModelNode()``).  This module owns the
workflow wire that ATTACHES it: resolve the Stage-2 CANONICAL
segmentation, find its SCT-tagged liver segment, mint a hidden
``vtkMRMLModelNode`` from the segment's closed surface (the v1
target-organ-model pattern: invisible plumbing, not scene furniture),
and set it as the plan carrier's weak ``target`` reference.

Cross-module contract note: the canonical-role attribute and the SCT
liver code are the SHARED Stage-2 vocabulary (ADR-0024 §Terminology /
ADR-0011) read here as attribute/tag literals — LiverResections does not
import LiverSegmentationLib (no cross-module Python dependency; the
contract is the scene data).
"""

from __future__ import annotations

from typing import Any

import slicer  # type: ignore[import-not-found]
import vtk

#: Stage-2 canonical-role attribute (ADR-0024 §Terminology).
_CANONICAL_ROLE_ATTRIBUTE = "LiverSegmentation.Role"
_CANONICAL_ROLE_VALUE = "canonical"
#: SCT type code for the liver parenchyma (ADR-0011 vocabulary).
_SCT_LIVER_CODE = "10200004"
#: Attribute tagging the minted hidden model so re-runs resolve it.
_TARGET_MODEL_ATTRIBUTE = "LiverResections.TargetModel"


def has_canonical_liver() -> bool:
    """True iff a canonical segmentation holds a liver segment WITH VOXELS.

    The Place guard's predicate: without it there is no target mesh, no
    auto-seed, and no contour -- Place must refuse instead of minting a
    dead resection (v1 parity: AddResectionPlane errored on a missing
    target organ model).

    The tag alone does not carry that guarantee.  Stage 2 pre-seeds its
    checklist with ``AddEmptySegment`` rows that already carry their
    terminology tags, and the Liver shell builds every stage panel on
    module open -- so a liver-tagged but EMPTY segment exists from the
    first frame, before anything has been segmented.  Matching on the tag
    alone unlocked Place immediately and minted exactly the dead
    resection this guard exists to prevent: ``ensure_target_model``
    returned ``None``, the auto-seed bailed on zero points, and the user
    was left with a selected plan that rendered nothing and reported
    nothing.
    """
    node, segment_id = _find_canonical_liver_segment()
    if node is None:
        return False
    return not _segment_is_empty(node, segment_id)


def ensure_target_model(
    plan_node: Any,
    method: str | None = None,
    depth: int | None = None,
) -> Any | None:
    """Attach the hidden liver target model to ``plan_node``'s carrier.

    Resolve-or-mint (idempotent): an already-attached target with live
    geometry is reused.  Returns the model node, or ``None`` when there
    is nothing to wire (no plan/carrier, no canonical segmentation, no
    SCT-tagged liver segment) — a graceful no-op, mirroring the sibling
    ensure* helpers.

    ``method`` selects how the segment becomes a mesh
    (``SegmentSurface.surface_methods()``).  ``None`` means marching
    cubes, so callers that do not care keep exactly the behaviour they
    had before ADR-0040: offering Poisson reconstruction must not change
    what anyone gets without asking.
    """
    if plan_node is None:
        return None
    carrier = plan_node.GetGeometryNode()
    if carrier is None:
        return None

    existing = carrier.GetTargetModelNode()
    if (
        existing is not None
        and existing.GetPolyData() is not None
        and existing.GetPolyData().GetNumberOfPoints() > 0
    ):
        return existing

    segmentation_node, segment_id = _find_canonical_liver_segment()
    if segmentation_node is None:
        return None

    from LiverResectionsLib import SegmentSurface

    polydata = SegmentSurface.segment_surface(
        segmentation_node,
        segment_id,
        method=SegmentSurface.METHOD_MARCHING_CUBES if method is None else method,
        depth=depth,
    )
    if polydata is None or polydata.GetNumberOfPoints() == 0:
        return None

    model = _resolve_or_mint_model()
    model.SetAndObservePolyData(polydata)
    carrier.SetAndObserveTargetModelNode(model)
    return model


def _find_canonical_liver_segment() -> tuple:
    """Return ``(segmentationNode, segmentId)`` for the canonical liver."""
    for node in slicer.util.getNodesByClass("vtkMRMLSegmentationNode"):
        if node.GetAttribute(_CANONICAL_ROLE_ATTRIBUTE) != _CANONICAL_ROLE_VALUE:
            continue
        segmentation = node.GetSegmentation()
        for segment_id in list(segmentation.GetSegmentIDs()):
            text = vtk.mutable("")
            segmentation.GetSegment(segment_id).GetTag("TerminologyEntry", text)
            if f"^{_SCT_LIVER_CODE}^" in str(text):
                return node, segment_id
    return None, None


def _segment_is_empty(segmentation_node: Any, segment_id: str) -> bool:
    """True when ``segment_id`` carries no voxel of its OWN label value.

    Emptiness must be LABEL-AWARE.  Stage 2's pre-seeded segments SHARE a
    single binary-labelmap layer (the stock ``AddEmptySegment`` shape), so
    landing content on one sharer grows the shared image's extent for
    every sharer.  The object-level extent therefore says nothing about
    whether THIS segment holds anything -- only a scan for its own label
    value does.

    Cheap by construction: the binary labelmap is the segmentation's
    master representation, so this reads what is already in memory.  It
    deliberately does NOT go through ``_liver_closed_surface``, which
    would run a closed-surface conversion on every enablement check.

    The Stage-2 sibling (``LiverSegmentation._segmentIsEmpty``) applies
    the same rule; per this module's cross-module contract note the
    shared vocabulary is scene data, not a Python import, so the logic is
    restated here rather than imported.
    """
    if segmentation_node is None or not segment_id:
        return True
    segment = segmentation_node.GetSegmentation().GetSegment(segment_id)
    if segment is None:
        return True

    name = slicer.vtkSegmentationConverter.GetSegmentationBinaryLabelmapRepresentationName()
    labelmap = segment.GetRepresentation(name)
    if labelmap is None:
        return True
    if hasattr(labelmap, "IsEmpty") and labelmap.IsEmpty():
        return True
    extent = labelmap.GetExtent()
    if extent[0] > extent[1] or extent[2] > extent[3] or extent[4] > extent[5]:
        return True
    scalars = labelmap.GetPointData().GetScalars()
    if scalars is None:
        return True

    from vtk.util.numpy_support import vtk_to_numpy

    return not bool((vtk_to_numpy(scalars) == segment.GetLabelValue()).any())


def _liver_closed_surface(segmentation_node: Any, segment_id: str) -> Any | None:
    """A deep-copied closed-surface polydata for ``segment_id``.

    Kept as a thin alias: the implementation moved to ``SegmentSurface``
    when a second extraction method joined it, and marching cubes has no
    claim to being the unqualified meaning of "the surface" any more.
    """
    from LiverResectionsLib import SegmentSurface

    return SegmentSurface.marching_cubes_surface(segmentation_node, segment_id)


def _resolve_or_mint_model() -> Any:
    """The single tagged hidden model node (resolve-or-create)."""
    for node in slicer.util.getNodesByClass("vtkMRMLModelNode"):
        if node.GetAttribute(_TARGET_MODEL_ATTRIBUTE) == "True":
            return node
    model = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLModelNode", "LiverResectionTargetOrgan"
    )
    model.SetAttribute(_TARGET_MODEL_ATTRIBUTE, "True")
    # v1 parity: invisible plumbing — hidden from editors, never rendered.
    model.SetHideFromEditors(True)
    model.CreateDefaultDisplayNodes()
    display = model.GetDisplayNode()
    if display is not None:
        display.SetVisibility(False)
    return model

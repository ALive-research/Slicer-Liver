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


def ensure_target_model(plan_node: Any) -> Any | None:
    """Attach the hidden liver target model to ``plan_node``'s carrier.

    Resolve-or-mint (idempotent): an already-attached target with live
    geometry is reused.  Returns the model node, or ``None`` when there
    is nothing to wire (no plan/carrier, no canonical segmentation, no
    SCT-tagged liver segment) — a graceful no-op, mirroring the sibling
    ensure* helpers.
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

    polydata = _liver_closed_surface(segmentation_node, segment_id)
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


def _liver_closed_surface(segmentation_node: Any, segment_id: str) -> Any | None:
    """A deep-copied closed-surface polydata for ``segment_id``."""
    polydata = segmentation_node.GetClosedSurfaceInternalRepresentation(segment_id)
    if polydata is None:
        segmentation_node.CreateClosedSurfaceRepresentation()
        polydata = segmentation_node.GetClosedSurfaceInternalRepresentation(
            segment_id
        )
    if polydata is None:
        return None
    # Deep copy (the v1 pattern): the working mesh must not alias the
    # segmentation's internal representation, which conversions rebuild.
    copied = vtk.vtkPolyData()
    copied.DeepCopy(polydata)
    return copied


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

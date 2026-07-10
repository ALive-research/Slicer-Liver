# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Target-organ model wiring: canonical liver segment -> carrier weakref.

The commit-boundary ring extraction consumes the carrier's weakref'd
target mesh (``GetTargetModelNode()``, ADR-0014 §1) — but nothing in the
workflow ever ATTACHED it, so the slicing-plane initialization had no
liver to cut (the origin-grid symptom).  v1 parity: a hidden model is
minted from the parenchyma's closed surface and referenced by the
resection; v2 derives it from the CANONICAL segmentation's SCT-tagged
liver segment (the Stage-2 hand-off) and attaches it to the plan's
carrier.
"""

from __future__ import annotations

import pytest

SCT_LIVER_CODE = "10200004"


def _slicer_or_skip():
    from slicer_pytest_support import import_slicer_or_skip, require_mrml_scene

    require_mrml_scene()
    return import_slicer_or_skip()


def _target_model_module():
    try:
        from LiverResectionsLib import TargetModel
    except Exception:
        pytest.skip("LiverResectionsLib.TargetModel not importable (pending impl).")
    return TargetModel


def _canonical_with_liver_segment(slicer):
    """A canonical-role segmentation holding one SCT-tagged liver segment."""
    import numpy as np

    labelmap = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
    array = np.zeros((16, 16, 16), dtype="uint8")
    array[4:12, 4:12, 4:12] = 1
    slicer.util.updateVolumeFromArray(labelmap, array)

    node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
    slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(
        labelmap, node
    )
    slicer.mrmlScene.RemoveNode(labelmap)
    node.SetAttribute("LiverSegmentation.Role", "canonical")
    segment_id = node.GetSegmentation().GetNthSegmentID(0)
    segment = node.GetSegmentation().GetSegment(segment_id)
    segment.SetTag(
        "TerminologyEntry",
        "Segmentation category and type - DICOM master list"
        "~SCT^85756007^Tissue"
        f"~SCT^{SCT_LIVER_CODE}^Liver"
        "~^^~Anatomic codes - DICOM master list~^^~^^",
    )
    return node


def _plan_or_skip(slicer):
    logic_module = getattr(slicer.modules, "liverresections", None)
    if logic_module is None:
        pytest.skip("liverresections module not registered.")
    logic = logic_module.logic()
    plan = logic.CreateResectionPlan()
    if plan is None:
        pytest.skip("CreateResectionPlan returned None in this build.")
    return plan


def test_ensure_target_model_attaches_hidden_liver_mesh():
    """The plan's carrier gains a weakref'd model minted from the liver segment."""
    slicer = _slicer_or_skip()
    slicer.mrmlScene.Clear(0)
    TargetModel = _target_model_module()

    canonical = _canonical_with_liver_segment(slicer)
    plan = _plan_or_skip(slicer)

    model = TargetModel.ensure_target_model(plan)

    assert model is not None and model.IsA("vtkMRMLModelNode"), (
        "ensure_target_model must mint a vtkMRMLModelNode from the canonical "
        "liver segment (the Stage-2 hand-off)."
    )
    assert model.GetPolyData() is not None and model.GetPolyData().GetNumberOfPoints() > 0, (
        "the target model must carry the liver's closed-surface geometry."
    )
    carrier = plan.GetGeometryNode()
    assert carrier.GetTargetModelNode() is model, (
        "the model must be attached to the carrier's weak target reference "
        "(ADR-0014 §1) -- the mesh commit()'s ring extraction consumes."
    )
    # v1 parity: the working mesh is INVISIBLE plumbing, not scene furniture.
    assert model.GetHideFromEditors(), "the target model hides from editors"
    display = model.GetDisplayNode()
    assert display is None or not display.GetVisibility(), (
        "the target model must not render (v1: opacity-0 hidden model)."
    )
    assert canonical is not None  # fixture liveness


def test_ensure_target_model_is_idempotent():
    """A second call reuses the attached model instead of minting another."""
    slicer = _slicer_or_skip()
    slicer.mrmlScene.Clear(0)
    TargetModel = _target_model_module()

    _canonical_with_liver_segment(slicer)
    plan = _plan_or_skip(slicer)

    first = TargetModel.ensure_target_model(plan)
    count_after_first = slicer.mrmlScene.GetNumberOfNodesByClass("vtkMRMLModelNode")
    second = TargetModel.ensure_target_model(plan)

    assert second is first, "the attached target model must be reused"
    assert (
        slicer.mrmlScene.GetNumberOfNodesByClass("vtkMRMLModelNode")
        == count_after_first
    ), "no second model node may be minted"


def test_ensure_target_model_without_canonical_is_a_noop():
    """No canonical segmentation -> None, and the carrier stays untargeted."""
    slicer = _slicer_or_skip()
    slicer.mrmlScene.Clear(0)
    TargetModel = _target_model_module()

    plan = _plan_or_skip(slicer)
    model = TargetModel.ensure_target_model(plan)

    assert model is None
    assert plan.GetGeometryNode().GetTargetModelNode() is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""The Place gate demands liver VOXELS, not just a liver-tagged row.

``has_canonical_liver()`` is the Place button's enablement predicate, and
its docstring states the contract it must honour: *"without it there is
no target mesh, no auto-seed, and no contour -- Place must refuse instead
of minting a dead resection"*.

Matching on the SCT terminology tag alone does not honour it.  Stage 2
pre-seeds its checklist with ``AddEmptySegment`` rows that ALREADY carry
their terminology tags (``ensureExpectedStructures``), and the Liver
shell builds every stage panel on module open -- so a liver-tagged but
EMPTY segment exists from the first frame, before anything is segmented.
A tag-only predicate therefore unlocks Place immediately;
``ensure_target_model`` then finds no polydata and returns ``None``, the
auto-seed bails on zero points, and the user gets a created, selected
plan with no handles, no contour and no message.

Emptiness is LABEL-AWARE: pre-seeded segments SHARE one binary-labelmap
layer, so writing content to one sharer grows the shared extent for all
of them.  A segment is empty iff NO voxel carries its own label value --
the object-level extent says nothing about a single sharer.  (The Stage-2
sibling ``_segmentIsEmpty`` documents the same trap; the contract between
the modules is scene data, not a Python import.)

HARNESS: launched Slicer.  Needs a live scene plus the segmentations
logic, so a bare ``PythonSlicer -m pytest`` SKIPS CLEANLY (ADR-0027).
"""

from __future__ import annotations

import pytest

SCT_LIVER_CODE = "10200004"

_TERMINOLOGY = (
    "Segmentation category and type - DICOM master list"
    "~SCT^85756007^Tissue"
    f"~SCT^{SCT_LIVER_CODE}^Liver"
    "~^^~Anatomic codes - DICOM master list~^^~^^"
)


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


def _canonical_node(slicer):
    """A canonical-role segmentation with no segments yet."""
    node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
    node.SetAttribute("LiverSegmentation.Role", "canonical")
    return node


def _add_tagged_empty_liver(node):
    """Stage 2's pre-seeded placeholder: tagged, no voxels."""
    segment_id = node.GetSegmentation().AddEmptySegment("", "Liver parenchyma")
    node.GetSegmentation().GetSegment(segment_id).SetTag(
        "TerminologyEntry", _TERMINOLOGY
    )
    return segment_id


def _fill_liver_voxels(slicer, node, segment_id):
    """Land real voxels on an existing tagged segment."""
    import numpy as np

    labelmap = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
    array = np.zeros((16, 16, 16), dtype="uint8")
    array[4:12, 4:12, 4:12] = 1
    slicer.util.updateVolumeFromArray(labelmap, array)
    slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(
        labelmap, node
    )
    slicer.mrmlScene.RemoveNode(labelmap)
    # The import lands a NEW segment; move the tag onto it and drop the
    # placeholder, which is what a real Stage-2 landing does.
    segmentation = node.GetSegmentation()
    for candidate in list(segmentation.GetSegmentIDs()):
        if candidate == segment_id:
            continue
        segmentation.GetSegment(candidate).SetTag("TerminologyEntry", _TERMINOLOGY)
        segmentation.RemoveSegment(segment_id)
        return candidate
    return segment_id


def test_tagged_but_empty_liver_does_not_unlock_place():
    """The Stage-2 placeholder must NOT satisfy the Place gate.

    This is the whole bug: the checklist row exists from module open, so
    a tag-only predicate mints a dead resection on the first click.
    """
    slicer = _slicer_or_skip()
    target_model = _target_model_module()

    node = _canonical_node(slicer)
    _add_tagged_empty_liver(node)

    assert target_model.has_canonical_liver() is False, (
        "A liver-tagged segment with NO voxels is Stage 2's pre-seeded "
        "placeholder, not a segmented liver.  Place must stay disabled: "
        "ensure_target_model would return None and the auto-seed would "
        "bail, leaving a selected plan that renders nothing."
    )


def test_liver_with_voxels_unlocks_place():
    """Once the row holds voxels the gate opens (the positive case)."""
    slicer = _slicer_or_skip()
    target_model = _target_model_module()

    node = _canonical_node(slicer)
    segment_id = _add_tagged_empty_liver(node)
    _fill_liver_voxels(slicer, node, segment_id)

    assert target_model.has_canonical_liver() is True, (
        "A liver-tagged segment holding voxels is exactly what Place "
        "needs; the gate must not over-tighten and refuse real anatomy."
    )


def test_no_canonical_segmentation_keeps_place_shut():
    """The pre-existing refusal path is unchanged by the emptiness rule."""
    slicer = _slicer_or_skip()
    target_model = _target_model_module()
    assert slicer is not None

    assert target_model.has_canonical_liver() is False

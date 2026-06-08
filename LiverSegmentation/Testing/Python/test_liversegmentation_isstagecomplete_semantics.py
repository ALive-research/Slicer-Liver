# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Invariant 2 — isStageComplete() scene semantics (SOFT Stage-2-done).

ADR-0023 §"Per-stage state-indicator semantics" (the soft-done line at
``Docs/adr/0023-unified-gui-stage-workflow.md``) defines Stage 2 as done iff
the canonical segmentation holds at least ONE SCT-tagged segment — NOT "all
four structures present".  ADR-0024 §"Output contract" names the single
canonical ``vtkMRMLSegmentationNode`` distinguished from per-tool scratch
nodes; scratch nodes must not flip the predicate true.

Scratch-vs-canonical is distinguished by a namespaced node attribute
(``LiverSegmentation.Role`` = ``scratch`` | ``canonical``), following the
``VascularTerritories.VascTerrId`` attribute precedent in
``VascularTerritories/VascularTerritories.py``.

The three pinned semantics:
  * empty scene                      -> False
  * canonical seg + >=1 SCT segment  -> True
  * scratch-only (no canonical)      -> False

RED until the implementer lands the predicate body per ADR-0024 / ADR-0023.
Scene-needing: runs under a minimal qSlicerApplication.
"""

from __future__ import annotations

import pytest

MODULE_NAME = "liversegmentation"

# Namespaced role attribute + its two values.  The implementer's module owns
# the authoritative definition of these strings; the test pins the contract
# the orchestrator and the Liver shell agree on.  Mirrors the
# ``VascularTerritories.VascTerrId`` namespacing precedent.
ROLE_ATTRIBUTE = "LiverSegmentation.Role"
ROLE_SCRATCH = "scratch"
ROLE_CANONICAL = "canonical"

# Liver parenchyma SNOMED-CT code per ADR-0024 §"Output contract".
SCT_LIVER_CODE = "10200004"


def _logic_or_skip():
    from conftest import _import_slicer_or_skip, _require_mrml_scene

    _require_mrml_scene()
    slicer = _import_slicer_or_skip()
    module = getattr(slicer.modules, MODULE_NAME, None)
    if module is None:
        pytest.skip(
            f"'{MODULE_NAME}' module not registered -- ADR-0024 implementer "
            "deliverable absent; predicate semantics cannot be exercised yet."
        )
    return slicer, module.logic()


def _add_segmentation_with_role(slicer, role):
    """Add a ``vtkMRMLSegmentationNode`` flagged with the role attribute."""
    node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
    node.SetAttribute(ROLE_ATTRIBUTE, role)
    return node


# Slicer's standard per-segment terminology tag name.  A segment is
# "SCT-tagged" when this tag carries a terminology entry whose type triple
# uses the SCT coding scheme.
TERMINOLOGY_ENTRY_TAG = "TerminologyEntry"


def _add_sct_tagged_segment(node):
    """Add one liver-parenchyma SCT-tagged segment to ``node``.

    TODO(impl): once the orchestrator exposes its SCT-tagging helper, prefer
    that path so this test exercises the production tagging code rather than a
    test-local approximation.  ADR-0011 owns the SCT dispatch surface, and the
    predicate under test must agree with the orchestrator on what "SCT-tagged"
    means.
    """
    segmentation = node.GetSegmentation()
    segmentId = segmentation.AddEmptySegment("liver", "Liver")
    segment = segmentation.GetSegment(segmentId)
    # Minimal SCT triple on the segment terminology tag (Liver 10200004).
    tag = (
        "Segmentation category and type - DICOM master list"
        "~SCT^85756007^Tissue"
        f"~SCT^{SCT_LIVER_CODE}^Liver"
        "~^^~Anatomic codes - DICOM master list~^^~^^"
    )
    segment.SetTag(TERMINOLOGY_ENTRY_TAG, tag)
    return segmentId


def test_isstagecomplete_false_on_empty_scene():
    """Empty scene -> Stage 2 is NOT done.

    ADR-0023 §"Per-stage state-indicator semantics": no canonical
    segmentation means the surgeon has not produced anatomy yet.
    """
    slicer, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    assert logic.isStageComplete() is False, (
        "isStageComplete() must be False on an empty scene."
    )


def test_isstagecomplete_true_on_canonical_with_one_sct_segment():
    """Canonical seg + >=1 SCT-tagged segment -> Stage 2 done (SOFT).

    ADR-0023 soft-done semantics: ONE SCT-tagged segment in the canonical
    node suffices, NOT all four structures.  ADR-0024 §"Output contract"
    names the single canonical node.
    """
    slicer, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    canonical = _add_segmentation_with_role(slicer, ROLE_CANONICAL)
    _add_sct_tagged_segment(canonical)
    assert logic.isStageComplete() is True, (
        "isStageComplete() must be True once a canonical (role-flagged) "
        "segmentation holds at least one SCT-tagged segment (soft-done per "
        "ADR-0023)."
    )


def test_isstagecomplete_false_for_scratch_only():
    """Scratch-only nodes (no canonical) do NOT flip the predicate true.

    ADR-0024 §Terminology + §"Output contract": scratch nodes are
    orchestrator-private pending output; only the canonical node satisfies
    Stage 2.  The role attribute is the discriminator.
    """
    slicer, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    scratch = _add_segmentation_with_role(slicer, ROLE_SCRATCH)
    _add_sct_tagged_segment(scratch)
    assert logic.isStageComplete() is False, (
        "isStageComplete() must stay False when only scratch-role "
        "segmentations exist -- scratch is pre-Accept and not canonical."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

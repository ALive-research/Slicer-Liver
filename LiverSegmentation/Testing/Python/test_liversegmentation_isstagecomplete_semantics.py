# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Invariant 2 — isStageComplete() scene semantics (all structures Completed).

ADR-0034 §Amendments (Decision 2 amended) replaces the soft ">=1 SCT-tagged
segment" predicate: Stage 2 is complete iff a canonical segmentation node
exists AND every structure-vocabulary entry's segment reads the NATIVE
``Completed`` status (``vtkSlicerSegmentationsModuleLogic``
``Segmentation.Status`` tag — the surgeon's status-cell confirm).  An EMPTY
``Completed`` segment is the explicit absence attestation (the surgeon's
status gesture on a structure with no data) and counts — no node attribute
required.  Scratch nodes never flip the predicate true (ADR-0024 §"Output
contract": the role attribute is the discriminator).

The pinned semantics:
  * empty scene                                     -> False
  * canonical, pre-seeded NotStarted checklist      -> False
  * all four structures Completed                   -> True
  * three Completed + one EMPTY Completed
    (the absence attestation, attribute-free)       -> True
  * scratch-only (no canonical)                     -> False

Scene-needing: runs under a minimal qSlicerApplication.
"""

from __future__ import annotations

import pytest

MODULE_NAME = "liversegmentation"

# Namespaced role attribute + its two values.  The module owns the
# authoritative definitions; the test pins the contract the orchestrator and
# the Liver shell agree on.
ROLE_ATTRIBUTE = "LiverSegmentation.Role"
ROLE_SCRATCH = "scratch"
ROLE_CANONICAL = "canonical"


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
    # ``module.logic()`` returns the generic C++ scripted logic, not the
    # Python orchestrator; instantiate the Python logic directly (same
    # resolution as the Liver-shell ``_volumetry_logic()`` precedent).
    try:
        import LiverSegmentation  # type: ignore[import-not-found]
    except ImportError as exc:
        pytest.skip(
            f"LiverSegmentation not importable ({exc}); "
            "ensure --additional-module-paths includes LiverSegmentation/."
        )
    return slicer, LiverSegmentation, LiverSegmentation.LiverSegmentationLogic()


def _expected_segments(module, canonical):
    """``{sctCode: vtkSegment}`` for every structure-vocabulary entry."""
    return {
        code: module._findSctSegment(canonical, code)
        for _title, code in module.STRUCTURE_TABS
    }


def test_isstagecomplete_false_on_empty_scene():
    """Empty scene -> Stage 2 is NOT done (no canonical node exists)."""
    slicer, _module, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    assert logic.isStageComplete() is False, (
        "isStageComplete() must be False on an empty scene."
    )


def test_isstagecomplete_false_on_preseeded_notstarted_checklist():
    """The pre-seeded canonical (all rows native NotStarted) is NOT done.

    ADR-0034 §Amendments: the checklist placeholders state the GOAL; only
    the surgeon's Completed confirms count.  This retires the soft
    ">=1 SCT-tagged segment" reading, under which the four tagged
    placeholders would have flipped the stage done at creation.
    """
    slicer, _module, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    logic.getOrCreateCanonicalSegmentation()
    assert logic.isStageComplete() is False, (
        "a freshly pre-seeded canonical (four terminology-tagged EMPTY "
        "NotStarted segments) must NOT count as Stage-2 done (ADR-0034 "
        "§Amendments predicate: every structure Completed)."
    )


def test_isstagecomplete_true_when_every_structure_completed():
    """All four structure segments Completed -> Stage 2 done."""
    slicer, module, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    canonical = logic.getOrCreateCanonicalSegmentation()

    segments_logic = slicer.vtkSlicerSegmentationsModuleLogic
    for code, segment in _expected_segments(module, canonical).items():
        assert segment is not None, f"pre-seeded segment missing for {code}"
        segments_logic.SetSegmentStatus(segment, segments_logic.Completed)

    assert logic.isStageComplete() is True, (
        "isStageComplete() must be True once every structure-vocabulary "
        "segment reads native Completed (ADR-0034 §Amendments)."
    )


def test_isstagecomplete_counts_empty_completed_absence_attestation():
    """Three Completed + one EMPTY Completed (the attestation) -> done.

    The explicit absence attestation (ADR-0034 §Amendments): an EMPTY
    segment the surgeon confirms ``Completed`` through the table's native
    status gesture IS the stated "not present in this case" and satisfies
    the predicate — no node attribute involved.  Short of that status the
    empty row still blocks.
    """
    slicer, module, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    canonical = logic.getOrCreateCanonicalSegmentation()
    segments_logic = slicer.vtkSlicerSegmentationsModuleLogic

    segments = _expected_segments(module, canonical)
    for code, segment in segments.items():
        if code == module.SCT_MASS_CODE:
            continue
        segments_logic.SetSegmentStatus(segment, segments_logic.Completed)

    # The tumors row is still the untouched empty placeholder: not attested.
    assert logic.isStageComplete() is False, (
        "an empty row still NotStarted must block the stage -- absence is "
        "STATED via the status gesture, never inferred from a forgotten row."
    )

    segments_logic.SetSegmentStatus(
        segments[module.SCT_MASS_CODE], segments_logic.Completed
    )
    assert logic.isStageComplete() is True, (
        "an EMPTY Completed segment is the explicit absence attestation and "
        "must count WITHOUT any marked-absent attribute (ADR-0034 "
        "§Amendments)."
    )


def test_isstagecomplete_false_for_scratch_only():
    """Scratch-only nodes (no canonical) do NOT flip the predicate true.

    ADR-0024 §Terminology + §"Output contract": scratch nodes are
    orchestrator-private pending output; only the canonical node satisfies
    Stage 2, whatever statuses its segments carry.
    """
    slicer, module, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)

    scratch = logic.createScratchSegmentation()
    segments_logic = slicer.vtkSlicerSegmentationsModuleLogic
    for title, code in module.STRUCTURE_TABS:
        seg_id = scratch.GetSegmentation().AddEmptySegment(title, title)
        logic.tagSegmentWithSct(scratch, seg_id, code, title)
        segments_logic.SetSegmentStatus(
            scratch.GetSegmentation().GetSegment(seg_id),
            segments_logic.Completed,
        )

    assert logic.isStageComplete() is False, (
        "isStageComplete() must stay False when only scratch-role "
        "segmentations exist -- scratch is pre-Accept and not canonical."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

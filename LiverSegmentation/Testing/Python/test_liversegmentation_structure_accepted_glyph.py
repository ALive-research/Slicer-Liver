# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""isStructureAccepted(sct) — the canonical-only landed-structure predicate.

The orchestrator method ``isStructureAccepted(<sct target>)`` reads the
CANONICAL node ONLY (role-filtered, like ``_findCanonicalSegmentation``):
a structure counts as landed once its canonical segment's NATIVE status has
moved past ``NotStarted`` (ADR-0034 §Amendments — a pre-seeded empty
placeholder is expected, not accepted).  Scratch nodes must never flip the
predicate (canonical-only read), per ADR-0024 §"Output contract" +
§Terminology.

The predicate's original consumer — the per-tab confirmation glyph — retired
with the tab UI (ADR-0034 §Amendments: the panel is the stock segments table;
the native status column carries the review state).  The logic pins stay: the
predicate remains part of the orchestrator surface.

Scene-needing: launched-Slicer harness (``pytest_launched``); skips cleanly
under bare pytest via the shared guards.
"""

from __future__ import annotations

import pytest

MODULE_NAME = "liversegmentation"
ROLE_ATTRIBUTE = "LiverSegmentation.Role"
ROLE_SCRATCH = "scratch"
ROLE_CANONICAL = "canonical"
TERMINOLOGY_ENTRY_TAG = "TerminologyEntry"

# SCT type codes per ADR-0024 §"Output contract".
SCT_LIVER_CODE = "10200004"
SCT_PORTAL_VEIN_CODE = "32764006"
SCT_HEPATIC_VEIN_CODE = "8993003"
SCT_MASS_CODE = "4147007"


def _logic_or_skip():
    from conftest import _import_slicer_or_skip, _require_mrml_scene

    _require_mrml_scene()
    slicer = _import_slicer_or_skip()
    module = getattr(slicer.modules, MODULE_NAME, None)
    if module is None:
        pytest.skip(
            f"'{MODULE_NAME}' module not registered -- ADR-0024 Stage-2 "
            "surgeon-UI deliverable absent; isStructureAccepted cannot be "
            "exercised yet."
        )
    try:
        import LiverSegmentation  # type: ignore[import-not-found]
    except ImportError as exc:
        pytest.skip(
            f"LiverSegmentation not importable ({exc}); "
            "ensure --additional-module-paths includes LiverSegmentation/."
        )
    return slicer, LiverSegmentation.LiverSegmentationLogic()


def _add_canonical_with_sct(slicer, orch, code, meaning):
    """LAND one SCT-tagged segment on the canonical node via ``accept()``.

    Drives the production landing path (scratch -> Accept) rather than
    hand-tagging a canonical segment: under ADR-0034 §Amendments "accepted"
    reads through the native segment status (a landed segment is
    ``InProgress``; a pre-seeded empty placeholder stays ``NotStarted`` and
    does NOT count), so the fixture must land, not merely tag.
    """
    scratch = orch.createScratchSegmentation()
    segId = scratch.GetSegmentation().AddEmptySegment(meaning, meaning)
    orch.tagSegmentWithSct(scratch, segId, code, meaning)
    return orch.accept(scratch)


def test_isstructureaccepted_false_before_accept():
    """No canonical segment for a structure -> isStructureAccepted is False.

    ADR-0024 §"Output contract": a structure is "accepted" only once the
    canonical node carries a segment SCT-tagged for it.  Empty scene -> every
    structure is unaccepted.
    """
    slicer, orch = _logic_or_skip()
    slicer.mrmlScene.Clear(0)

    if not hasattr(orch, "isStructureAccepted"):
        pytest.fail(
            "orchestrator must expose isStructureAccepted(sctTarget) reading "
            "the canonical node only, to drive the per-tab confirmation glyph "
            "(ADR-0024 §'Output contract') -- not yet implemented."
        )
    for code in (
        SCT_LIVER_CODE,
        SCT_PORTAL_VEIN_CODE,
        SCT_HEPATIC_VEIN_CODE,
        SCT_MASS_CODE,
    ):
        assert orch.isStructureAccepted(code) is False, (
            f"isStructureAccepted({code}) must be False on an empty scene."
        )


def test_isstructureaccepted_true_after_that_structures_accept():
    """Canonical holds the structure's SCT segment -> isStructureAccepted True.

    ADR-0024 §"Output contract": once Accept lands a Portal-vein-tagged
    segment in the canonical node, isStructureAccepted(32764006) is True while
    the other structures remain False (per-structure, not global).
    """
    slicer, orch = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    if not hasattr(orch, "isStructureAccepted"):
        pytest.fail(
            "orchestrator must expose isStructureAccepted(sctTarget) "
            "(ADR-0024 §'Output contract') -- not yet implemented."
        )

    _add_canonical_with_sct(slicer, orch, SCT_PORTAL_VEIN_CODE, "Portal vein")

    assert orch.isStructureAccepted(SCT_PORTAL_VEIN_CODE) is True, (
        "isStructureAccepted must be True once the canonical node holds that "
        "structure's SCT-tagged segment (ADR-0024 §'Output contract')."
    )
    assert orch.isStructureAccepted(SCT_LIVER_CODE) is False, (
        "isStructureAccepted is per-structure: accepting Portal vein must not "
        "flip Liver parenchyma to accepted."
    )


def test_isstructureaccepted_ignores_scratch_only_state():
    """A scratch-only SCT segment must NOT mark the structure accepted.

    ADR-0024 §Terminology + §"Output contract": the predicate is a
    canonical-only read (mirroring ``_findCanonicalSegmentation``).  A scratch
    node tagged for a structure is pending, not accepted, so the tab stays ○.
    """
    slicer, orch = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    for name in ("isStructureAccepted", "createScratchSegmentation", "tagSegmentWithSct"):
        if not hasattr(orch, name):
            pytest.fail(
                f"orchestrator missing '{name}' per ADR-0024 -- not yet "
                "implemented."
            )

    scratch = orch.createScratchSegmentation()
    segId = scratch.GetSegmentation().AddEmptySegment("liver", "Liver")
    orch.tagSegmentWithSct(scratch, segId, SCT_LIVER_CODE, "Liver")

    assert orch.isStructureAccepted(SCT_LIVER_CODE) is False, (
        "a scratch-only SCT segment must not mark the structure accepted -- "
        "isStructureAccepted reads the canonical node only (ADR-0024 "
        "§Terminology)."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

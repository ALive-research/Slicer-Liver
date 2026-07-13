# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Invariant 6 (UI) — Accept SCT-tags into the one canonical node;
multi-focal tumors land N separate Mass segments.

ADR-0024 §"Output contract": the canonical ``vtkMRMLSegmentationNode`` holds
one SCT-tagged segment per structure (Liver 10200004; Portal vein 32764006;
Hepatic vein 8993003; Mass 4147007).  Accept is a pure merge that:

  * keeps the canonical-node count at exactly ONE (rejecting Alternative B
    per-target nodes);
  * lands segment(s) carrying the correct SCT triple for the structure the
    row represents — the SCT tags come from the LabelToSCT.json bridge at
    Run (ADR-0011); the orchestrator's tag loop applies them.

**Multi-focal tumors (decided):** landing the Tumors result yields **N
separate SCT-`Mass` segments** in the one canonical node (per-lesion
identity), NOT a single merged tumor segment.  ADR-0024 §"Per-structure
micro-workflows" Tumors row: "Multi-focal supported (N tumors per case)".

Scene-needing: launched-Slicer harness (``pytest_launched``).
RED until the implementer lands the SCT-tagging Accept path per ADR-0024.
"""

from __future__ import annotations

import pytest

MODULE_NAME = "liversegmentation"
ROLE_ATTRIBUTE = "LiverSegmentation.Role"
ROLE_SCRATCH = "scratch"
ROLE_CANONICAL = "canonical"
TERMINOLOGY_ENTRY_TAG = "TerminologyEntry"

# SCT type codes per ADR-0024 §"Output contract", confirmed against the
# Resources/Terminology/LabelToSCT/ bridges.
SCT_LIVER_CODE = "10200004"
SCT_PORTAL_VEIN_CODE = "32764006"
SCT_HEPATIC_VEIN_CODE = "8993003"
SCT_MASS_CODE = "4147007"


def _orchestrator_or_skip():
    from conftest import _import_slicer_or_skip, _require_mrml_scene

    _require_mrml_scene()
    slicer = _import_slicer_or_skip()
    module = getattr(slicer.modules, MODULE_NAME, None)
    if module is None:
        pytest.skip(
            f"'{MODULE_NAME}' module not registered -- ADR-0024 Stage-2 "
            "surgeon-UI deliverable absent; Accept flow cannot be exercised."
        )
    try:
        import LiverSegmentation  # type: ignore[import-not-found]
    except ImportError as exc:
        pytest.skip(
            f"LiverSegmentation not importable ({exc}); "
            "ensure --additional-module-paths includes LiverSegmentation/."
        )
    return slicer, LiverSegmentation.LiverSegmentationLogic()


def _canonical_nodes(slicer):
    nodes = slicer.util.getNodesByClass("vtkMRMLSegmentationNode")
    return [n for n in nodes if n.GetAttribute(ROLE_ATTRIBUTE) == ROLE_CANONICAL]


def _segment_carries_sct(segment, code):
    """Return True iff ``segment``'s terminology tag carries SCT ``code``."""
    import vtk

    entry = vtk.reference("")
    if not segment.GetTag(TERMINOLOGY_ENTRY_TAG, entry):
        return False
    text = str(entry)
    return "SCT" in text and code in text


def _canonical_segments_with_sct(slicer, code):
    """Count canonical-node segments carrying SCT ``code``."""
    canonical = _canonical_nodes(slicer)
    if not canonical:
        return 0
    segmentation = canonical[0].GetSegmentation()
    return sum(
        1
        for i in range(segmentation.GetNumberOfSegments())
        if _segment_carries_sct(segmentation.GetNthSegment(i), code)
    )


def test_accept_lands_correct_sct_triple_per_structure():
    """Accepting a structure's scratch lands a segment with that SCT triple.

    ADR-0024 §"Output contract": the canonical node holds one SCT-tagged
    segment per structure.  Here Portal vein -> SCT 32764006 in the single
    canonical node, and the canonical-node count stays 1.

    TODO(impl): if the implementer exposes a higher-level
    ``acceptStructure(scratch, sctTarget)`` that both merges and SCT-tags,
    drive it here.  The pinned invariant is "after Accept the canonical node
    carries a segment with the structure's SCT code", however the tag is
    applied (Run-time tagging via the LabelToSCT bridge per ADR-0011, or an
    Accept-time tag pass).
    """
    slicer, orch = _orchestrator_or_skip()
    slicer.mrmlScene.Clear(0)

    for name in ("createScratchSegmentation", "accept", "tagSegmentWithSct"):
        if not hasattr(orch, name):
            pytest.fail(
                f"orchestrator missing '{name}' -- SCT-tagging Accept surface "
                "required by ADR-0024 §'Output contract' not yet implemented."
            )

    scratch = orch.createScratchSegmentation()
    segId = scratch.GetSegmentation().AddEmptySegment("portal", "Portal vein")
    # SCT tags originate from the LabelToSCT bridge at Run (ADR-0011); the
    # orchestrator applies them via tagSegmentWithSct.
    orch.tagSegmentWithSct(scratch, segId, SCT_PORTAL_VEIN_CODE, "Portal vein")

    orch.accept(scratch)

    assert len(_canonical_nodes(slicer)) == 1, (
        "Accept must keep exactly one canonical node (ADR-0024 §'Output "
        "contract', rejecting Alternative B per-target nodes)."
    )
    assert _canonical_segments_with_sct(slicer, SCT_PORTAL_VEIN_CODE) == 1, (
        "the canonical node must hold one segment carrying the Portal-vein "
        f"SCT code {SCT_PORTAL_VEIN_CODE} after Accept (ADR-0024 §'Output "
        "contract')."
    )


def test_tumors_accept_lands_n_separate_mass_segments():
    """Multi-focal tumors -> N separate SCT-Mass segments, not one merged.

    Decided multi-focal behaviour (ADR-0024 §"Per-structure micro-workflows"
    Tumors row, "Multi-focal supported (N tumors per case)"): Accept on the
    Tumors landing preserves per-lesion identity by landing N separate
    SCT-``Mass`` (4147007) segments in the one canonical node — the SCT-tag
    loop tags each tumor sub-label individually rather than merging them.

    TODO(impl): the synthetic scratch here stands in for a TotalSegmentator
    multi-focal tumor mask split into per-lesion sub-labels.  Drive the
    implementer's multi-focal Accept path (each tumor sub-label -> its own
    Mass-tagged segment) once it exists; the pinned invariant is the
    per-lesion segment count, NOT a merged single Mass segment.
    """
    slicer, orch = _orchestrator_or_skip()
    slicer.mrmlScene.Clear(0)

    for name in ("createScratchSegmentation", "accept", "tagSegmentWithSct"):
        if not hasattr(orch, name):
            pytest.fail(
                f"orchestrator missing '{name}' -- multi-focal tumor Accept "
                "surface required by ADR-0024 not yet implemented."
            )

    n_lesions = 3
    scratch = orch.createScratchSegmentation()
    for lesion in range(n_lesions):
        segId = scratch.GetSegmentation().AddEmptySegment(
            f"tumor_{lesion}", f"Tumor {lesion}"
        )
        orch.tagSegmentWithSct(scratch, segId, SCT_MASS_CODE, "Mass")

    orch.accept(scratch)

    assert len(_canonical_nodes(slicer)) == 1, (
        "multi-focal Accept must still keep one canonical node."
    )
    assert _canonical_segments_with_sct(slicer, SCT_MASS_CODE) == n_lesions, (
        f"landing the Tumors result must yield {n_lesions} SEPARATE SCT-Mass "
        f"({SCT_MASS_CODE}) segments (per-lesion identity), NOT a single "
        "merged tumor segment (ADR-0024 §'Per-structure micro-workflows', "
        "multi-focal decided behaviour)."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

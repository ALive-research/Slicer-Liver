# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""SLICE C — Stage 2 produces a canonical, SCT-tagged segmentation by LOADING.

In v2.0 the in-app AI backend is deferred to v2.1 (ADR-0024 §"Lazy install for
AI backends"): the surgeon-usable path for Stage 2 is to LOAD an existing
segmentation (from disk / a prior tool) and promote it to the case's single
canonical ``vtkMRMLSegmentationNode``, SCT-tagging each structure so downstream
stages can dispatch on the code (ADR-0011; ADR-0024 §"Output contract").

This pins the new logic seam ``importSegmentationAsCanonical`` on
``LiverSegmentationLogic``:

    importSegmentationAsCanonical(self, sourceSegmentationNode, assignments)
        -> canonicalNode | None

where ``assignments`` maps ``segmentId -> (sctCode, meaning)``.  The observable
contract (NOT the internal mechanism — promote-in-place vs copy is the
implementer's call, see the module note) is:

  * afterwards the single canonical node (the one ``_findCanonicalSegmentation``
    returns, role attribute ``canonical``) holds one SCT-tagged segment per
    assignment;
  * ``isStructureAccepted(sctCode)`` is True for each assigned structure;
  * ``isStageComplete()`` is True (soft-done, ADR-0023 §"Per-stage
    state-indicator semantics": >=1 SCT-tagged canonical segment);
  * a degenerate call (empty ``assignments`` or ``None`` source) is a no-op
    that does NOT flip Stage 2 complete and does not raise.

Fixtures are built through the module's OWN seams — a source segmentation node
minted via ``getOrCreateCanonicalSegmentation`` is unavailable pre-promotion,
so the source is a plain scene ``vtkMRMLSegmentationNode`` with
``AddEmptySegment`` segments, mirroring the ``AddEmptySegment`` construction the
isstagecomplete-semantics + accept suites use.  The SCT codes match ADR-0024
§"Output contract" (Liver 10200004; Portal vein 32764006).

Scene-needing: launched-Slicer harness (``pytest_launched``).  SKIP-PENDING on
the not-yet-implemented ``importSegmentationAsCanonical`` (RED before impl,
green after); skips cleanly under bare ``PythonSlicer -m pytest``.
"""

from __future__ import annotations

import pytest

MODULE_NAME = "liversegmentation"
ROLE_ATTRIBUTE = "LiverSegmentation.Role"
ROLE_CANONICAL = "canonical"

# SCT type codes per ADR-0024 §"Output contract", confirmed against the
# Resources/Terminology/LabelToSCT/ bridges.
SCT_LIVER_CODE = "10200004"
SCT_PORTAL_VEIN_CODE = "32764006"

# The logic seam this slice introduces (skip-pending until implemented).
IMPORT_SEAM = "importSegmentationAsCanonical"


def _logic_or_skip():
    from conftest import _import_slicer_or_skip, _require_mrml_scene

    _require_mrml_scene()
    slicer = _import_slicer_or_skip()
    module = getattr(slicer.modules, MODULE_NAME, None)
    if module is None:
        pytest.skip(
            f"'{MODULE_NAME}' module not registered -- ADR-0024 Stage-2 "
            "deliverable absent; the load-as-canonical flow cannot be exercised."
        )
    try:
        import LiverSegmentation  # type: ignore[import-not-found]
    except ImportError as exc:
        pytest.skip(
            f"LiverSegmentation not importable ({exc}); "
            "ensure --additional-module-paths includes LiverSegmentation/."
        )
    return slicer, LiverSegmentation.LiverSegmentationLogic()


def _require_seam(logic):
    """SKIP-PENDING until the load-as-canonical seam lands (RED before impl)."""
    if not hasattr(logic, IMPORT_SEAM):
        pytest.skip(
            f"LiverSegmentationLogic.{IMPORT_SEAM}() not implemented -- SLICE C "
            "load-as-canonical deliverable absent (ADR-0024 §'Output "
            "contract').  This invariant pins its observable contract for when "
            "it lands."
        )


def _source_segmentation(slicer, labels):
    """Mint a plain (un-roled) source segmentation with named empty segments.

    Stands in for a loaded-from-disk segmentation the surgeon promotes.  Built
    through ``AddEmptySegment`` the same way the isstagecomplete-semantics +
    accept suites construct their fixtures.  Returns ``(node, {label: segId})``.
    """
    node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", "Loaded")
    segmentation = node.GetSegmentation()
    ids = {label: segmentation.AddEmptySegment(label, label) for label in labels}
    return node, ids


def test_import_single_structure_makes_stage_complete_and_accepted():
    """C1a — loading a liver segment + assigning SCT 10200004 completes Stage 2.

    ADR-0024 §"Output contract" + ADR-0023 soft-done: promoting a loaded
    segmentation whose liver segment is assigned SCT ``10200004`` yields a
    canonical node with one SCT-tagged segment, so ``isStructureAccepted`` for
    the liver code and ``isStageComplete`` are both True.
    """
    slicer, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    _require_seam(logic)

    source, ids = _source_segmentation(slicer, ["liver"])
    assignments = {ids["liver"]: (SCT_LIVER_CODE, "Liver")}

    canonical = logic.importSegmentationAsCanonical(source, assignments)

    assert canonical is not None, (
        "importSegmentationAsCanonical must return the canonical node when "
        "given a source + non-empty assignments (ADR-0024 §'Output contract')."
    )
    assert canonical.GetAttribute(ROLE_ATTRIBUTE) == ROLE_CANONICAL, (
        "the returned node must carry the canonical role attribute -- it is "
        "THE single Stage-2 output downstream stages consume."
    )
    assert logic.isStructureAccepted(SCT_LIVER_CODE) is True, (
        f"isStructureAccepted({SCT_LIVER_CODE}) must be True after the liver "
        "segment is promoted + SCT-tagged (ADR-0011 dispatch key)."
    )
    assert logic.isStageComplete() is True, (
        "isStageComplete() must be True once the canonical node holds one "
        "SCT-tagged segment (ADR-0023 soft-done)."
    )


def test_import_multiple_structures_accepts_each_and_completes_stage():
    """C1b — assigning liver + portal vein accepts both; Stage 2 completes.

    ADR-0024 §"Output contract": one SCT-tagged segment per structure in the
    single canonical node.  Loading a segmentation with liver + portal-vein
    segments and assigning SCT ``10200004`` / ``32764006`` makes
    ``isStructureAccepted`` True for BOTH, and ``isStageComplete`` True.
    """
    slicer, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    _require_seam(logic)

    source, ids = _source_segmentation(slicer, ["liver", "portal"])
    assignments = {
        ids["liver"]: (SCT_LIVER_CODE, "Liver"),
        ids["portal"]: (SCT_PORTAL_VEIN_CODE, "Portal vein"),
    }

    logic.importSegmentationAsCanonical(source, assignments)

    assert logic.isStructureAccepted(SCT_LIVER_CODE) is True, (
        f"liver SCT {SCT_LIVER_CODE} must be accepted after multi-structure "
        "import (ADR-0024 §'Output contract')."
    )
    assert logic.isStructureAccepted(SCT_PORTAL_VEIN_CODE) is True, (
        f"portal-vein SCT {SCT_PORTAL_VEIN_CODE} must be accepted after "
        "multi-structure import (ADR-0024 §'Output contract')."
    )
    assert logic.isStageComplete() is True, (
        "isStageComplete() must be True with >=1 SCT-tagged canonical segment "
        "(ADR-0023 soft-done)."
    )


def test_import_degenerate_is_noop_and_does_not_complete_stage():
    """C1c — empty assignments / None source is a no-op; Stage 2 stays incomplete.

    A degenerate promotion must NOT flip Stage 2 complete (ADR-0023 soft-done
    is >=1 SCT-tagged canonical segment) and must NOT raise -- an accidental
    empty load cannot silently satisfy the stage.
    """
    slicer, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    _require_seam(logic)

    # None source.
    result_none = logic.importSegmentationAsCanonical(None, {})
    assert logic.isStageComplete() is False, (
        "a None-source import must not complete Stage 2 (ADR-0023 soft-done)."
    )

    # Empty assignments over a real source: nothing gets SCT-tagged.
    source, _ = _source_segmentation(slicer, ["liver"])
    result_empty = logic.importSegmentationAsCanonical(source, {})
    assert logic.isStageComplete() is False, (
        "an empty-assignments import must not complete Stage 2 -- no segment "
        "carries an SCT tag (ADR-0023 soft-done; ADR-0024 §'Output contract')."
    )

    # The degenerate return shape is the implementer's call (None or an empty
    # canonical node); the pinned invariant is the no-op on completion, not the
    # return value.  Reference the results so a stricter contract can assert on
    # them later without an unused-variable lint.
    assert result_none is None or result_none.IsA("vtkMRMLSegmentationNode")
    assert result_empty is None or result_empty.IsA("vtkMRMLSegmentationNode")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

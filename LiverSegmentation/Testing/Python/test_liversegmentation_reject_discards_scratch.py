# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Invariant 7 (UI) — Reject discards the scratch node; canonical unchanged.

ADR-0024 §"Per-structure micro-workflows" + §Terminology ("scratch node" is
orchestrator-private pending output): the per-card *Reject* affordance throws
away the scratch ``vtkMRMLSegmentationNode`` without touching the canonical
node.  Reject is the symmetric counterpart of Accept — Accept merges scratch
into canonical, Reject drops scratch and leaves canonical exactly as it was.

Scene-needing: launched-Slicer harness (``pytest_launched``).
RED until the implementer lands the card Reject path per ADR-0024.
"""

from __future__ import annotations

import pytest

MODULE_NAME = "liversegmentation"
ROLE_ATTRIBUTE = "LiverSegmentation.Role"
ROLE_SCRATCH = "scratch"
ROLE_CANONICAL = "canonical"
SCT_LIVER_CODE = "10200004"


def _orchestrator_or_skip():
    from conftest import _import_slicer_or_skip, _require_mrml_scene

    _require_mrml_scene()
    slicer = _import_slicer_or_skip()
    module = getattr(slicer.modules, MODULE_NAME, None)
    if module is None:
        pytest.skip(
            f"'{MODULE_NAME}' module not registered -- ADR-0024 Stage-2 "
            "surgeon-UI deliverable absent; Reject flow cannot be exercised."
        )
    try:
        import LiverSegmentation  # type: ignore[import-not-found]
    except ImportError as exc:
        pytest.skip(
            f"LiverSegmentation not importable ({exc}); "
            "ensure --additional-module-paths includes LiverSegmentation/."
        )
    return slicer, LiverSegmentation.LiverSegmentationLogic()


def _segmentation_nodes(slicer, role):
    nodes = slicer.util.getNodesByClass("vtkMRMLSegmentationNode")
    return [n for n in nodes if n.GetAttribute(ROLE_ATTRIBUTE) == role]


def test_reject_removes_scratch_and_leaves_canonical_untouched():
    """Reject drops the scratch node; the canonical node is unchanged.

    ADR-0024 §Terminology: scratch is pending output the surgeon can discard.
    After Reject no scratch node remains, and the canonical node's segment
    count is exactly what it was before the rejected Run.

    TODO(impl): pin the implementer's Reject accessor name (e.g.
    ``reject(scratch)`` / ``discardScratch(scratch)``).  The pinned invariant
    is "scratch gone, canonical untouched", independent of the spelling.
    """
    slicer, orch = _orchestrator_or_skip()
    slicer.mrmlScene.Clear(0)

    reject = None
    for name in ("reject", "discardScratch"):
        if hasattr(orch, name):
            reject = getattr(orch, name)
            break
    if reject is None or not hasattr(orch, "createScratchSegmentation"):
        pytest.fail(
            "orchestrator must expose a per-card Reject path "
            "(e.g. reject(scratch) / discardScratch(scratch)) plus "
            "createScratchSegmentation per ADR-0024 §'Per-structure "
            "micro-workflows' -- not yet implemented."
        )

    # Establish a canonical node with a known segment to assert it is untouched.
    canonical = orch.getOrCreateCanonicalSegmentation()
    canonical.GetSegmentation().AddEmptySegment("liver", "Liver")
    before = canonical.GetSegmentation().GetNumberOfSegments()

    scratch = orch.createScratchSegmentation()
    scratch.GetSegmentation().AddEmptySegment("synthetic", "Synthetic")

    reject(scratch)

    assert len(_segmentation_nodes(slicer, ROLE_SCRATCH)) == 0, (
        "Reject must remove the scratch node (ADR-0024 §Terminology: scratch "
        "is discardable pending output)."
    )
    assert len(_segmentation_nodes(slicer, ROLE_CANONICAL)) == 1, (
        "Reject must not touch the canonical node count."
    )
    assert canonical.GetSegmentation().GetNumberOfSegments() == before, (
        "Reject must leave the canonical node's segments unchanged."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

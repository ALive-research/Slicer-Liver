# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Invariant 3 — exactly ONE canonical vtkMRMLSegmentationNode per case.

ADR-0024 §"Output contract" + §Conformance: Stage 2 publishes a single
canonical ``vtkMRMLSegmentationNode``; scratch nodes are also
``vtkMRMLSegmentationNode`` instances but flagged as scratch via the
``LiverSegmentation.Role`` attribute.  The canonical-creation path is
singular, and Accept merges a scratch node's segments INTO the existing
canonical node rather than minting a second canonical node.

This rejects Alternative B (per-target nodes) and Alternative D (auto-commit
with no scratch/Accept) from ADR-0024.

RED until the implementer lands the orchestrator per ADR-0024.
Scene-needing: runs under a minimal qSlicerApplication.
"""

from __future__ import annotations

import pytest

MODULE_NAME = "liversegmentation"
ROLE_ATTRIBUTE = "LiverSegmentation.Role"
ROLE_SCRATCH = "scratch"
ROLE_CANONICAL = "canonical"


def _orchestrator_or_skip():
    """Resolve the Stage-2 orchestrator (the module logic).

    Skips when the module is absent so the scaffold stays green pre-impl.
    """
    from conftest import _import_slicer_or_skip, _require_mrml_scene

    _require_mrml_scene()
    slicer = _import_slicer_or_skip()
    module = getattr(slicer.modules, MODULE_NAME, None)
    if module is None:
        pytest.skip(
            f"'{MODULE_NAME}' module not registered -- ADR-0024 orchestrator "
            "deliverable absent; canonical-node singularity cannot be "
            "exercised yet."
        )
    return slicer, module.logic()


def _canonical_nodes(slicer):
    """Return all segmentation nodes flagged canonical via the role attribute."""
    nodes = slicer.util.getNodesByClass("vtkMRMLSegmentationNode")
    return [n for n in nodes if n.GetAttribute(ROLE_ATTRIBUTE) == ROLE_CANONICAL]


def test_orchestrator_publishes_exactly_one_canonical_node():
    """Repeated canonical-node access yields the SAME single node.

    ADR-0024 §"Output contract": one canonical ``vtkMRMLSegmentationNode``
    per case.  The orchestrator's canonical-node accessor must be idempotent
    (get-or-create), never minting a second canonical node.

    TODO(impl): replace ``getOrCreateCanonicalSegmentation`` with the actual
    orchestrator accessor name if it differs; the invariant (singular
    canonical path) is what is pinned, not the spelling.
    """
    slicer, orch = _orchestrator_or_skip()
    slicer.mrmlScene.Clear(0)

    if not hasattr(orch, "getOrCreateCanonicalSegmentation"):
        pytest.fail(
            "orchestrator must expose a singular get-or-create canonical-node "
            "accessor (e.g. getOrCreateCanonicalSegmentation) per ADR-0024 "
            "§'Output contract' -- not yet implemented."
        )

    first = orch.getOrCreateCanonicalSegmentation()
    second = orch.getOrCreateCanonicalSegmentation()
    assert first is not None
    assert first.IsA("vtkMRMLSegmentationNode")
    assert first.GetID() == second.GetID(), (
        "canonical-node accessor minted a second node -- the canonical "
        "creation path must be singular (ADR-0024 §'Output contract')."
    )
    assert len(_canonical_nodes(slicer)) == 1, (
        "exactly one canonical (role=canonical) segmentation node must exist."
    )


def test_accept_merges_scratch_into_existing_canonical():
    """Accept merges scratch segments into the canonical node, not a new one.

    ADR-0024 §Terminology ("commit / Accept") + Alternative B rejection:
    after Accept the scene still holds exactly ONE canonical node; the
    scratch node's segment(s) now live in it.

    TODO(impl): adjust ``createScratchSegmentation`` / ``accept`` accessor
    names to match the orchestrator surface; the pinned invariant is that
    Accept does not increase the canonical-node count.
    """
    slicer, orch = _orchestrator_or_skip()
    slicer.mrmlScene.Clear(0)

    needed = ("getOrCreateCanonicalSegmentation", "createScratchSegmentation", "accept")
    missing = [name for name in needed if not hasattr(orch, name)]
    if missing:
        pytest.fail(
            "orchestrator missing scratch/Accept surface "
            f"({', '.join(missing)}) per ADR-0024 §Terminology -- not yet "
            "implemented."
        )

    canonical = orch.getOrCreateCanonicalSegmentation()
    scratch = orch.createScratchSegmentation()
    assert scratch.GetAttribute(ROLE_ATTRIBUTE) == ROLE_SCRATCH, (
        "scratch node must carry role=scratch (ADR-0024 §Terminology)."
    )
    scratch.GetSegmentation().AddEmptySegment("liver", "Liver")

    orch.accept(scratch)

    assert len(_canonical_nodes(slicer)) == 1, (
        "Accept must merge into the existing canonical node, not create a "
        "second one (ADR-0024 §Terminology 'commit / Accept')."
    )
    assert canonical.GetSegmentation().GetNumberOfSegments() >= 1, (
        "the canonical node must hold the merged segment(s) after Accept."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
